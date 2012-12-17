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

@app.before_request
def before_request():
    flask.g.db = db_connect()

@app.teardown_request
def teardown_request():
    flask.g.db.close()

@app.route('/')
def list_series():
    pass

@app.route('/series/<int:series_id>')
def series_feed(series_id):
    pass

if __name__ == '__main__':
    app.run()
