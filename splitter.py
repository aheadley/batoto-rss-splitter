#!/usr/bin/env python

import flask
import sqlite3

from contextlib import closing

app = flask.Flask(__name__)
app.config.from_envvar('SPLITTER_SETTINGS', silent=True)

def db_connect():
    return sqlite3.connect(app.config['DATABASE'])

def db_init():
    with closing(db_connect()) as db:
        with app.open_resource('data/schema.sql') as schema_file:
            db.cursor().executescript(schema_file.read())
        db.commit()

def db_query(query, args=(), single_result=False):
    cursor = flask.g.db.execute(query, args)
    results = [dict((cursor.description[i][0], value)
        for i, value in enumerate(row)) for row in cursor.fetchall()]
    return (results[0] if results else None) if single_result else results

@app.before_request
def before_request():
    flask.g.db = db_connect()

@app.teardown_request
def teardown_request(x):
    flask.g.db.close()

@app.route('/')
def list_series():
    series = db_query('SELECT * FROM series')
    return '<pre>' + \
        '</pre><br /><pre>'.join(repr(s) for s in series) + \
        '</pre>'


@app.route('/series/<int:series_id>/<int:language_id>')
def series_feed(series_id, language_id):
    updates = db_query('SELECT * FROM updates WHERE series_id = ? AND language_id = ?',
        (series_id, language_id))
    return '<pre>' + \
        '</pre><br /><pre>'.join(repr(update) for update in updates) + \
        '</pre>'

if __name__ == '__main__':
    app.run()
