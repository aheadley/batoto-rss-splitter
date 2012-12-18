#!/usr/bin/env python

import sqlite3

from cStringIO import StringIO
from contextlib import closing
import time

import flask

app = flask.Flask(__name__)
app.config.from_envvar('SPLITTER_SETTINGS', silent=True)

def db_connect():
    return sqlite3.connect(app.config['DATABASE'])

def db_init(drop=False):
    with closing(db_connect()) as db:
        if drop:
            with app.open_resource('data/drop-schema.sql') as schema_file:
                db.cursor().executescript(schema_file.read())
        with app.open_resource('data/schema.sql') as schema_file:
            db.cursor().executescript(schema_file.read())
        db.commit()

def db_query(query, args=(), single_result=False, commit=True):
    cursor = flask.g.db.execute(query, args)
    if commit:
        db_commit()
    results = [dict((cursor.description[i][0], value)
        for i, value in enumerate(row)) for row in cursor.fetchall()]
    return (results[0] if results else None) if single_result else results

def db_commit():
    return flask.g.db.commit()

def noapp_db(func, *pargs, **kwargs):
    with app.test_request_context():
        app.preprocess_request()
        result = func(*pargs, **kwargs)
    return result

def noapp_db_query(*pargs, **kwargs):
    return noapp_db(db_query, *pargs, **kwargs)

@app.before_request
def before_request():
    flask.g.db = db_connect()

@app.teardown_request
def teardown_request(dummy_arg=None):
    flask.g.db.close()

@app.route('/')
def list_langs():
    langs = db_query('SELECT * FROM languages ORDER BY full_name')
    return flask.render_template('lang.html', langs=((lang, flask.url_for('list_series', lang=lang['short_code'])) for lang in langs))

@app.route('/series/<lang>/')
def list_series(lang):
    series = db_query('SELECT * FROM series ORDER BY title')
    return flask.render_template('series.html',
        series=((s, flask.url_for('series_feed', series_id=s['id'], lang=lang)) for s in series))

@app.route('/feed/<lang>/<int:series_id>')
def series_feed(lang, series_id):
    lang_id = db_query('SELECT id FROM languages WHERE short_code = ?',
        (lang,), single_result=True)['id']
    updates = db_query('SELECT * FROM updates WHERE series_id = ? AND language_id = ? ORDER BY rss_ts DESC LIMIT 25',
        (series_id, lang_id))
    series = db_query('SELECT title FROM series WHERE id = ?',
        (series_id,), single_result=True)['title']
    lang = db_query('SELECT full_name FROM languages WHERE id = ?',
        (lang_id,), single_result=True)['full_name']

    resp = flask.make_response(flask.render_template('feed.xml',
        updates=((
                update,
                '%s - %s - %s: %s' % (series, lang, update['chapter'],
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
    if app.config['DEBUG']:
        app.run()
    else:
        app.run(use_reloader=True, threaded=True)
