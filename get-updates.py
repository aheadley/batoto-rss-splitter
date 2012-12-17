#!/usr/bin/env python

import feedparser
import re
from flask import g
from splitter import app, db_connect, db_query as _db_query

def db_query(*pargs, **kwargs):
    with app.test_request_context():
        app.preprocess_request()
        result = _db_query(*pargs, **kwargs)
    return result

class Updater(object):
    """
    """

    PATTERN_DESC = re.compile(
        r'^(?P<series>.*) - (?P<lang>[A-Z][a-z]+) - '
            '(?P<chapter>(?:Vol\.[\d.]+ )?Ch\.[\d.]+):? '
            '(?P<chapter_title>.*)$')

    def __init__(self, feed_url):
        self._feed_url = feed_url
        self._feed = None

    def update(self):
        data = [(entry, self.PATTERN_DESC.match(entry.title).groupdict())
            for entry in self._get_feed().entries]

        series = list(set(e[1]['series'] for e in data))
        langs = list(set(e[1]['lang'] for e in data))
        for s in series:
            db_query('INSERT INTO series (title) VALUES (?)',
                (s,))
        for l in langs:
            db_query('INSERT INTO languages (full_name, short_code) VALUES (?, ?)',
                (l, l.lower()[:3]))
        print db_query('SELECT * FROM series')


    def _get_feed(self):
        if self._feed is None:
            self._feed = feedparser.parse(self._feed_url)
        return self._feed


if __name__ == '__main__':
    import os
    import sys

    feed_url = os.environ.get('BATOTO_FEED_URL',
        'http://www.batoto.net/recent_rss')
    try:
        feed_url = sys.argv[1]
    except IndexError:
        pass
    updater = Updater(feed_url)
    updater.update()
