batoto-rss-splitter
===================

Split Batoto updates RSS feed into per-series feeds.

## Usage

There are two parts to this, the updater (``get-updates.py``) which should run
as a cronjob and populates the database with series, languages, and rss updates,
and the Flask app (``splitter.py``).

First, create the config file by copying ``config.py.example`` to ``<whatever>.py``
and change and values as needed, then set the ``SPLITTER_SETTINGS`` env var to
the name of the new config file:
~~~~
$ export SPLITTER_SETTINGS=splitter_config.py
~~~~

Create the database:
~~~~
$ python create-db.py
~~~~

Populate the database for the first time:
~~~~
$ python get-updates.py
~~~~

Then run set get-updates.py to run as cronjob, and run the ``splitter.py`` app,
it should work via WSGI (haven't actually tested this) or you can just run the dev server:
~~~~
$ python splitter.py
 * Running on http://127.0.0.1:5000/
~~~~

Then visit http://localhost:5000/ in your browser.
