#!/usr/bin/env python

import flask
import sqlite3

from contextlib import closing

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
    with app.test_request_context():
        app.preprocess_request()
        result = db_query(*pargs, **kwargs)
    return result

@app.before_request
def before_request():
    flask.g.db = db_connect()

@app.teardown_request
def teardown_request(dummy_arg=None):
    flask.g.db.close()

@app.route('/')
def list_langs():
    langs = db_query('SELECT id, full_name FROM languages')
    return '<br/>'.join('<a href="%s">%s</a>' % \
        (flask.url_for('list_series', language_id=lang['id']), lang['full_name']) \
            for lang in langs)

@app.route('/series/<int:language_id>')
def list_series(language_id):
    series = db_query('SELECT * FROM series')
    return '<br/>'.join(
        '<a href="%s">%s</a>' % \
            (flask.url_for('series_feed', series_id=s['id'], language_id=language_id), \
                s['title']) for s in series)

@app.route('/feed/<int:series_id>/<int:language_id>')
def series_feed(series_id, language_id):
    updates = db_query('SELECT * FROM updates WHERE series_id = ? AND language_id = ? ORDER BY rss_ts DESC LIMIT 25',
        (series_id, language_id))
    return '<pre>' + \
        '</pre><br /><pre>'.join(repr(update) for update in updates) + \
        '</pre>'

if __name__ == '__main__':
    app.run()
