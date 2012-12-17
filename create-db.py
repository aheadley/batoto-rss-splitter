#!/usr/bin/env python

from splitter import db_init

if __name__ == '__main__':
    import sys

    args = dict(enumerate(sys.argv))
    db_init(bool(args.get(1, False)))
