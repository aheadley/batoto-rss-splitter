#!/usr/bin/env python

import datetime

from splitter import db_query, noapp_db

def clean_db(older_than=30):
    ts = datetime.datetime.now() - datetime.timedelta(older_than)
    noapp_db(db_query, 'DELETE FROM updates WHERE DATETIME(rss_ts) < ?',
        (ts.strftime('%Y-%m-%d %H:%M:%S'),))

if __name__ == '__main__':
    import sys

    args = dict(enumerate(sys.argv))
    clean_db(int(args.get(1, '30')))
