#!/usr/bin/env python

import sqlite3
import time
import logging
import datetime
import re
import hashlib
import sys

import feedparser
import flask

app = flask.Flask(__name__)
app.config.from_envvar('SPLITTER_SETTINGS', silent=True)

noapp_logger = logging.getLogger(__name__)
noapp_logger.setLevel(logging.DEBUG)


class DatabaseException(Exception): pass
class DataNotFound(DatabaseException): pass
class InvalidQuery(DatabaseException): pass

class SqliteManager(object):
    def __init__(self, db_name):
        self._conn = sqlite3.connect(db_name)

    @property
    def cursor(self):
        return self._conn.cursor()

    @property
    def last_insert_rowid(self):
        result = self.query('SELECT last_insert_rowid()', single_result=True)
        if result is None:
            raise InvalidQuery()
        else:
            return result['last_insert_rowid()']

    @property
    def changes(self):
        result = self.query('SELECT changes()', single_result=True)
        if result is None:
            raise InvalidQuery()
        else:
            return result['changes()']

    def close(self):
        self._conn.close()

    def query(self, query, args=(), single_result=False, commit=True):
        noapp_logger.debug('Running query "%s" with: %r', query, args)
        cursor = self._conn.execute(query, args)
        if commit:
            self.commit()
        results = [dict((cursor.description[i][0], value) \
                for i,value in enumerate(row)) \
            for row in cursor.fetchall()]
        if single_result:
            if results:
                return results[0]
            else:
                return None
        else:
            return results

    def executescript(self, handle):
        self.cursor.executescript(handle.read())
        self.commit()

    def commit(self):
        self._conn.commit()

class SplitterDataManager(object):
    SCRIPT_DROP_SCHEMA  = 'data/drop-schema.sql'
    SCRIPT_LOAD_SCHEMA  = 'data/create-schema.sql'

    TABLE_LANG          = 'languages'
    TABLE_SERIES        = 'series'
    TABLE_UPDATES       = 'updates'

    def __init__(self, db):
        self.db = db

    def close(self):
        self.db.close()

    def import_schema(self, drop_first=False):
        if drop_first:
            with app.open_resource(self.SCRIPT_DROP_SCHEMA) as schema_file:
                self.db.executescript(schema_file)
        with app.open_resource(self.SCRIPT_LOAD_SCHEMA) as schema_file:
            self.db.executescript(schema_file)

    def get_all_langs(self):
        return self.db.query('SELECT * FROM languages ORDER BY full_name',
            commit=False)

    def get_lang(self, short_code=None, full_name=None):
        query = 'SELECT * FROM languages WHERE %s = ?'
        if short_code is not None:
            query = query % 'short_code'
            param = short_code
        elif full_name is not None:
            query = query % 'full_name'
            param = full_name
        else:
            raise InvalidQuery()
        result = self.db.query(query, (param,), single_result=True, commit=False)
        if result is None:
            raise DataNotFound()
        else:
            return result

    def get_all_series(self):
        return self.db.query('SELECT * FROM series ORDER BY title',
            commit=False)

    def get_series_title(self, id):
        result = self.db.query('SELECT title FROM series WHERE id = ?',
            (id,), commit=False, single_result=True)
        if result is None:
            raise DataNotFound()
        else:
            return result['title']

    def get_series_id(self, title):
        result = self.db.query('SELECT id FROM series WHERE title = ?',
            (title,), commit=False, single_result=True)
        if result is None:
            raise DataNotFound()
        else:
            return result['id']

    def get_all_updates(self):
        return self.db.query('SELECT * FROM updates ORDER BY DATETIME(rss_ts) DESC',
            single_result=False, commit=False)

    def get_updates(self, lang_id, series_id, limit=25):
        result = self.db.query('SELECT * FROM updates WHERE language_id = ? \
                AND series_id = ? ORDER BY DATETIME(rss_ts) DESC LIMIT ?',
            (lang_id, series_id, limit), commit=False)
        return result

    def get_last_update(self):
        result = self.db.query('SELECT * FROM updates ORDER BY DATETIME(creation_ts) DESC LIMIT 1',
            commit=False, single_result=True)
        if result is None:
            raise DataNotFound()
        else:
            return result

    def get_update_by_hash(self, rss_hash):
        return self.db.query('SELECT rss_hash FROM updates WHERE rss_hash = ?',
            (rss_hash,), commit=False, single_result=True)

    def add_series(self, title):
        self.db.query('INSERT INTO series (title) VALUES (?)',
            (title,), commit=True)
        return self.db.last_insert_rowid

    def add_lang(self, full_name, short_code):
        self.db.query('INSERT INTO languages (full_name, short_code) VALUES (?, ?)',
            (full_name, short_code), commit=True)
        return self.db.last_insert_rowid

    def add_update(self, series_id, lang_id, rss_hash, rss_ts, chapter, chapter_title,
                    link, data):
        self.db.query('INSERT INTO updates \
                    (series_id, language_id, rss_hash, rss_ts, chapter, chapter_title, link, data) \
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (series_id, lang_id, rss_hash, rss_ts, chapter, chapter_title, link, data),
            commit=True)
        return self.db.last_insert_rowid

    def clean_updates(self, older_than=30):
        ts = datetime.datetime.now() - datetime.timedelta(older_than)
        self.db.query('DELETE FROM updates WHERE DATETIME(rss_ts) < DATETIME(?)',
            (ts.strftime('%Y-%m-%d %H:%M:%S'),))
        return self.db.changes

class Updater(object):
    PATTERN_DESC = re.compile(
        r'^(?P<series>.*) - (?P<lang>[A-Z][a-z]+) - '
            '(?P<chapter>(?:Vol\.[\d.]+ )?Ch\.[\d\w.]+(?: \d+)?):? '
            '(?P<chapter_title>.+)$')

    def __init__(self):
        self._feed_url = app.config['BATOTO_FEED_URL']
        self._feed = None
        self.dbm = get_data_manager()

    def update(self, skip_last_hash=False):
        noapp_logger.debug('Running update...')

        if skip_last_hash:
            noapp_logger.debug('Skipping last update hash...')
            last_hash = None
        else:
            try:
                last_hash = self.dbm.get_last_update()['rss_hash']
            except DataNotFound:
                last_hash = None
        noapp_logger.debug('Using last hash: %s', str(last_hash))

        for (entry, data) in self._iterate_feed(last_hash):
            noapp_logger.debug('Checking entry: %s', data)
            try:
                series_id = self.dbm.get_series_id(data['series'])
            except DataNotFound:
                series_id = self.dbm.add_series(data['series'])
                noapp_logger.info('Added new series: %s', data['series'])

            try:
                lang_id = self.dbm.get_lang(full_name=data['lang'])['id']
            except DataNotFound:
                lang_id = self.dbm.add_lang(short_code=data['lang'].lower()[:3],
                    full_name=data['lang'])

            entry_hash = self._get_entry_hash(entry)
            if self.dbm.get_update_by_hash(entry_hash) is None:
                update_data = ''
                self.dbm.add_update(series_id, lang_id, entry_hash,
                    self._get_timestamp(entry.published_parsed), data['chapter'],
                    data['chapter_title'], entry['link'], update_data)
                noapp_logger.debug('Added update: %s', repr(data))
        noapp_logger.debug('Finished checking updates...')

    def _get_entry_hash(self, entry):
        return self._hash(entry.title, entry.guid)

    def _hash(self, *args):
        return hashlib.sha1(app.config['SECRET_KEY'] + ':' + \
            (u'|'.join(args)).encode('utf-8')).hexdigest()

    def _get_timestamp(self, time_spec):
        return time.strftime('%Y-%m-%d %H:%M:%S', time_spec)

    def _iterate_feed(self, last_hash):
        for entry in self._get_feed().entries:
            if last_hash is not None and self._get_entry_hash(entry) == last_hash:
                break
            else:
                match = self.PATTERN_DESC.search(entry.title)
                if match:
                    yield entry, match.groupdict()
                else:
                    noapp_logger.warning('Entry failed pattern check: %s', entry.title)

    def _get_feed(self):
        if self._feed is None:
            self._feed = feedparser.parse(self._feed_url)
        return self._feed

def get_data_manager():
    return SplitterDataManager(SqliteManager(app.config['DATABASE']))

@app.before_request
def before_request():
    flask.g.db = get_data_manager()

@app.teardown_request
def teardown_request(dummy_arg=None):
    flask.g.db.close()
    flask.g.db = None

@app.route('/about')
def about():
    return flask.render_template('about.html')

@app.route('/')
def list_langs():
    return flask.render_template('lang.html', langs=flask.g.db.get_all_langs())

@app.route('/series/<lang>/')
def list_series(lang):
    try:
        lang_id = flask.g.db.get_lang(short_code=lang)
    except DataNotFound:
        flask.abort(404)
    return flask.render_template('series.html',
        series=flask.g.db.get_all_series(), lang=lang)

@app.route('/feed/<lang_code>/<int:series_id>')
def series_feed(lang_code, series_id):
    dbm = flask.g.db
    try:
        lang = dbm.get_lang(short_code=lang_code)
        updates = dbm.get_updates(lang_id=lang['id'], series_id=series_id)
        series = dbm.get_series_title(series_id)
    except DataNotFound:
        flask.abort(404)
    app.logger.debug('Generating feed for "%s" with %d entries',
        series, len(updates))
    resp = flask.make_response(flask.render_template('feed.xml',
        updates=((
                update,
                '%s - %s - %s: %s' % (series, lang['full_name'], update['chapter'],
                    update['chapter_title']),
                time.strftime('%a, %d %b %Y %H:%M:%S +0000',
                    time.strptime(update['rss_ts'], '%Y-%m-%d %H:%M:%S'))) \
            for update in updates
        ),
        series_title=series
    ))
    resp.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return resp

if __name__ == '__main__':
    from optparse import OptionParser

    def mode_run(args, opts):
        if app.config['DEBUG']:
            app.run()
        else:
            app.run(use_reloader=True, threaded=True)

    def mode_fetch_updates(args, opts):
        updater = Updater()
        updater.update(skip_last_hash=opts.force)

    def mode_create_db(args, opts):
        noapp_logger.info('Creating database...')
        get_data_manager().import_schema(opts.force)

    def mode_clean_db(args, opts):
        try:
            older_than = int(args[0])
        except IndexError:
            older_than = 30
        noapp_logger.info('Removing updates older than %d days...', older_than)
        changes = get_data_manager().clean_updates(older_than)
        noapp_logger.info('Removed %d updates', changes)

    modes = {
        'run': mode_run,
        'fetch-updates': mode_fetch_updates,
        'create-db': mode_create_db,
        'clean-db': mode_clean_db,
    }

    parser = OptionParser()
    parser.add_option('-m', '--mode',
        action='store', choices=list(modes.iterkeys()),
        default='run',
        help='Action to run')
    parser.add_option('-d', '--debug',
        action='store_' + ('false' if app.config['DEBUG'] else 'true'),
        default=app.config['DEBUG'],
        help='Flip debug switch on or off')
    parser.add_option('-f', '--force',
        action='store_true', default=False,
        help='Force the given action, actual results are action dependent')
    parser.add_option('-u', '--rss-url',
        action='store', default=app.config['BATOTO_FEED_URL'],
        help='Override the configured feed URL')

    (opts, args) = parser.parse_args()
    app.config['DEBUG'] = opts.debug
    app.config['BATOTO_FEED_URL'] = opts.rss_url

try:
    handler = logging.handles.StreamHandler
except AttributeError:
    handler = logging.StreamHandler
handler = handler(sys.stderr)
if app.config['DEBUG']:
    handler.setLevel(logging.DEBUG)
else:
    handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter(
    '[%(asctime)s][%(filename)s:%(lineno)d][%(levelname)s]: %(message)s',
    '%Y-%m-%d %H:%M:%S'))
noapp_logger.addHandler(handler)

if not app.config['DEBUG']:
    try:
        handler = logging.handlers.StreamHandler
    except AttributeError:
        handler = logging.StreamHandler
    handler = handler()
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

if __name__ == '__main__':
    modes[opts.mode](args, opts)
