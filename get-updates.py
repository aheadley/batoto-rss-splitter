#!/usr/bin/env python

import re
import time
import hashlib
import logging
import sys

import feedparser

from splitter import app, noapp_db_query as db_query

class Updater(object):
    """
    """

    PATTERN_DESC = re.compile(
        r'^(?P<series>.*) - (?P<lang>[A-Z][a-z]+) - '
            '(?P<chapter>(?:Vol\.[\d.]+ )?Ch\.(?:Part )?[\d.]+):? '
            '(?P<chapter_title>.*)$')

    def __init__(self, app):
        self._feed_url = app.config['BATOTO_FEED_URL']
        self._feed = None
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)
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
        self._logger.addHandler(handler)

    def update(self, skip_last_hash=False):
        self._logger.debug('Running update...')
        data = ((entry, self.PATTERN_DESC.match(entry.title).groupdict())
            for entry in self._get_feed().entries)

        if skip_last_hash:
            self._logger.debug('Skipping last update hash...')
            last_hash = None
        else:
            last_hash_result = db_query('SELECT rss_hash FROM updates ORDER BY creation_ts DESC LIMIT 1',single_result=True)
            last_hash = last_hash_result['rss_hash'] if last_hash_result is not None else None
        self._logger.debug('Using last hash: %s', str(last_hash))
        for (entry, data) in self._iterate_feed(last_hash):
            self._logger.debug('Checking entry: %s', data)
            series_id = db_query('SELECT id FROM series WHERE title = ?',
                    (data['series'],), True)
            if series_id is None:
                db_query('INSERT INTO series (title) VALUES (?)',
                    (data['series'],))
                series_id = db_query('SELECT id FROM series WHERE title = ?',
                            (data['series'],), True).get('id')
                self._logger.info('Added new series: %s', data['series'])
            else:
                series_id = series_id['id']
            lang_id = db_query('SELECT id FROM languages WHERE full_name = ?',
                    (data['lang'],), True)
            if lang_id is None:
                db_query('INSERT INTO languages (full_name, short_code) VALUES (?, ?)',
                    (data['lang'], data['lang'].lower()[:3]))
                lang_id = db_query('SELECT id FROM languages WHERE full_name = ?',
                        (data['lang'],), True).get('id')
                self._logger.info('Added new language: %s', data['lang'])
            else:
                lang_id = lang_id['id']
            if db_query('SELECT id FROM updates WHERE rss_hash = ?',
                    (self._get_entry_hash(entry),), True) is None:
                db_query('INSERT INTO updates \
                            (series_id, language_id, rss_hash, rss_ts, chapter, chapter_title, link, data) \
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (series_id, lang_id, self._get_entry_hash(entry), self._get_timestamp(entry.published_parsed),
                        data['chapter'], data['chapter_title'],
                        entry['link'], ''))
                self._logger.debug('Added update: %s', repr(data))
        self._logger.debug('Finished checking updates...')

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
                    self._logger.warning('Entry failed pattern check: %s', entry.title)

    def _get_feed(self):
        if self._feed is None:
            self._feed = feedparser.parse(self._feed_url)
        return self._feed

if __name__ == '__main__':
    args = dict(enumerate(sys.argv))
    updater = Updater(app)
    updater.update(skip_last_hash=bool(args.get(1, False)))
