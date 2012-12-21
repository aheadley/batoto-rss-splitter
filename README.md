batoto-rss-splitter
===================

Split Batoto updates RSS feed into per-series feeds.

## Usage

The main script is ``splitter.py``, which can be run in different "modes":

  - ``fetch-updates``: Pulls data into the database from the Batoto RSS feed,
  should be run periodically (cronjob recommended). If run with ``--force`` it
  will ignore the last update and re-check all visible updates in the feed
  - ``run``: Runs the Flask app which displays the data from the database
  - ``clean-db``: Removes updates from the database older than x days (default is
  30, overridable as an arg to the command)
  - ``create-db``: Imports the database schema, creating the database. If run with
  ``--force`` it will drop the database first

First, create the config file by copying ``config.py.example`` to ``<whatever>.py``
and change and values as needed, then set the ``SPLITTER_SETTINGS`` env var to
the name of the new config file:
~~~~
$ export SPLITTER_SETTINGS=splitter_config.py
~~~~

Create the database:
~~~~
$ python splitter.py -m create-db
~~~~

Populate the database for the first time:
~~~~
$ python splitter.py -m fetch-updates
~~~~

You should then make the fetch-updates command run as a cronjob so the database
continues to get new updates. You can then run the Flask app (the default mode),
it should work via WSGI (haven't actually tested this) or you can just run the
dev server:
~~~~
$ python splitter.py
 * Running on http://127.0.0.1:5000/
~~~~

Then visit http://localhost:5000/ in your browser.
