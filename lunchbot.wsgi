import logging
import sys

sys.path.insert(0, "/var/www/html/lunchbot")
logging.basicConfig(level=logging.INFO)

from backend import app as application  # noqa: E402, F401
