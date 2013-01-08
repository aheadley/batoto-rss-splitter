#!/usr/bin/env python

import os
import sys

venv_activate_script = os.path.abspath(os.path.join(
    os.environ['VENV_SITE_DIR'],
    'bin/activate_this.py'))

execfile(venv_activate_script, __file__=venv_activate_script)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from splitter import app as application
