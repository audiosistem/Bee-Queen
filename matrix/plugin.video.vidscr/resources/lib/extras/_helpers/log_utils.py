"""Minimal logging shim used by the extras helpers.

Originally a 100-line file with explicit upstream branding and changelog
plumbing — replaced with a thin forward to vidscr's ``common.log``."""
from ... import common as _common

LOGDEBUG = 0
LOGINFO = 1
LOGNOTICE = 1
LOGWARNING = 2
LOGERROR = 4
LOGFATAL = 5
LOGNONE = 6


def log(msg, level=1):
    try:
        _common.log('[ext] %s' % msg)
    except Exception:
        pass


def error(msg, level=4):
    log(msg, level)
