"""Run from the repo root: python -m pytest -q"""

import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'hirer-backend'))

# keep test runs out of the real data and cache folders (must be set before the app is imported)
_tmp = tempfile.mkdtemp(prefix='hirer-tests-')
os.environ['HIRER_DATA_DIR'] = os.path.join(_tmp, 'data')
os.environ['HIRER_CACHE_DIR'] = os.path.join(_tmp, 'cache')
