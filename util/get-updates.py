#!/usr/bin/env python

import feedparser
import re

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
        for entry in self._get_feed().entries:
            print self.PATTERN_DESC.match(entry.title).groupdict()

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
