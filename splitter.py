#!/usr/bin/env python

import sqlite3
import xml.etree.cElementTree as ET

from cStringIO import StringIO
from contextlib import closing

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

def load_xml_dom():
    with app.open_resource('data/feed-template.xml') as rss_tpl:
        rss_doc = rss_tpl.read() % (app.config['BATOTO_FEED_URL'],
            app.config['BATOTO_FEED_URL'])
        rss_dom = ET.fromstring(rss_doc)
    return rss_dom

def add_update_to_dom(dom, update, series, lang):
    item = ET.SubElement(dom, 'item')
    title = '%s - %s - %s: %s' % \
        (series, lang, update['chapter'], update['chapter_title'])
    pub_date = update['rss_ts']
    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'link').text = update['link']
    ET.SubElement(item, 'guid').text = update['rss_hash']
    ET.SubElement(item, 'pubDate').text = pub_date
    ET.SubElement(item, 'description').text = title

@app.route('/feed/<int:series_id>/<int:language_id>')
def series_feed(series_id, language_id):
    updates = db_query('SELECT * FROM updates WHERE series_id = ? AND language_id = ? ORDER BY rss_ts DESC LIMIT 25',
        (series_id, language_id))
    series = db_query('SELECT title FROM series WHERE id = ?',
        (series_id,), single_result=True)['title']
    lang = db_query('SELECT full_name FROM languages WHERE id = ?',
        (language_id,), single_result=True)['full_name']
    root = load_xml_dom()

    for update in updates:
        add_update_to_dom(root[0], update, series, lang)

    resp = flask.make_response(ET.tostring(root, encoding='utf-8'), 200)
    resp.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return resp

if __name__ == '__main__':
    app.run()
