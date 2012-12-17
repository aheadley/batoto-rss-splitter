#!/usr/bin/env python

import feedparser
import re
import time
import hashlib
import json
import pickle
from splitter import noapp_db_query as db_query
#from splitter import noapp_db, db_query, db_commit

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
        data = ((entry, self.PATTERN_DESC.match(entry.title).groupdict())
            for entry in self._get_feed().entries)

        last_hash = db_query('SELECT rss_hash FROM updates ORDER BY creation_ts DESC LIMIT 1',single_result=True).get('rss_hash', None)

        for (entry, data) in self._iterate_feed(last_hash):
            db_query('INSERT OR IGNORE INTO series (title) VALUES (?)',
                (data['series'],))
            db_query('INSERT OR IGNORE INTO languages (full_name, short_code) VALUES (?, ?)',
                (data['lang'], data['lang'].lower()[:3]))
            series_id = db_query('SELECT id FROM series WHERE title = ?',
                    (data['series'],), True)['id']
            lang_id = db_query('SELECT id FROM languages WHERE full_name = ?',
                    (data['lang'],), True)['id']
            db_query('INSERT OR IGNORE INTO updates \
                        (series_id, language_id, rss_hash, rss_ts, chapter, chapter_title, link, data) \
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (series_id, lang_id, self._get_entry_hash(entry), self._get_timestamp(entry.published_parsed),
                    data['chapter'], data['chapter_title'],
                    entry['link'], ''), commit=False)

    def _get_entry_hash(self, entry):
        return self._hash(entry.title, entry.guid,
            self._get_timestamp(entry.published_parsed))

    def _hash(self, *args):
        return hashlib.sha1((u'|'.join(args)).encode('utf-8')).hexdigest()

    def _get_timestamp(self, time_spec):
        return time.strftime('%Y-%m-%d %H:%M:%S', time_spec)

    def _iterate_feed(self, last_hash):
        for entry in self._get_feed().entries:
            if last_hash is not None and self._get_entry_hash(entry) == last_hash:
                break
            else:
                yield entry, self.PATTERN_DESC.match(entry.title).groupdict()

    def _get_feed(self):
        if self._feed is None:
            self._feed = feedparser.parse(self._feed_url)
        return self._feed


if __name__ == '__main__':
    import sys
    from splitter import app

    feed_url = app.config['BATOTO_FEED_URL']
    try:
        feed_url = sys.argv[1]
    except IndexError:
        pass
    updater = Updater(feed_url)
    updater.update()
