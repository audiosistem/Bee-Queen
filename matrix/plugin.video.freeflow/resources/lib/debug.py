# -*- coding: utf-8 -*-
"""Comprehensive debug logger for Free Flow.

Writes to:
  1. Kodi's main log via xbmc.log() at LOGINFO/LOGWARNING/LOGERROR.
  2. A dedicated debug file at:
        special://profile/addon_data/plugin.video.freeflow/debug.log
     This file is also surfaced through Settings -> "View Debug Log".

The debug logger is ENABLED BY DEFAULT (settings.xml) so the user (and any
support thread) can copy a meaningful trace without having to flip Kodi's
"Enable debug logging" master switch first.
"""
import json
import os
import sys
import time
import threading
import traceback

try:
    import xbmc
    import xbmcvfs
    import xbmcaddon
except Exception:  # offline tests
    xbmc = xbmcvfs = xbmcaddon = None


_LOCK = threading.Lock()
_TAG = '[plugin.video.freeflow]'
_MAX_BYTES = 512 * 1024  # rotate at ~512 KB
_BACKUP = 1


def _profile_dir():
    if xbmcvfs is None:
        p = os.path.join('/tmp', 'plugin.video.freeflow')
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass
        return p
    p = xbmcvfs.translatePath(
        'special://profile/addon_data/plugin.video.freeflow/')
    if not xbmcvfs.exists(p):
        xbmcvfs.mkdirs(p)
    return p


def log_path():
    return os.path.join(_profile_dir(), 'debug.log')


def is_enabled():
    """Debug logging master toggle (default True)."""
    if xbmcaddon is None:
        return True
    try:
        v = xbmcaddon.Addon().getSetting('debug_logging')
        if v is None or v == '':
            return True  # default ON
        return v.lower() == 'true'
    except Exception:
        return True


def _kodi_level(level):
    if xbmc is None:
        return 1
    table = {
        'DEBUG': xbmc.LOGDEBUG,
        'INFO': xbmc.LOGINFO,
        'WARN': xbmc.LOGWARNING,
        'ERROR': xbmc.LOGERROR,
    }
    return table.get(level, xbmc.LOGINFO)


def _rotate_if_needed(path):
    try:
        if os.path.exists(path) and os.path.getsize(path) > _MAX_BYTES:
            backup = path + '.1'
            try:
                if os.path.exists(backup):
                    os.remove(backup)
            except Exception:
                pass
            try:
                os.rename(path, backup)
            except Exception:
                pass
    except Exception:
        pass


def dlog(msg, level='INFO', component='general'):
    """Single entry point. Writes to both Kodi log and our file log."""
    if not is_enabled():
        return
    try:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        line = '%s [%s] [%s] %s' % (ts, level.upper(), component, msg)

        # 1) Kodi log (always tagged so user can grep it)
        if xbmc is not None:
            try:
                xbmc.log('%s %s' % (_TAG, line), _kodi_level(level))
            except Exception:
                pass

        # 2) File log (rotated)
        with _LOCK:
            path = log_path()
            _rotate_if_needed(path)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
    except Exception:
        # never raise from logger
        pass


def dump_exception(component='general', context=''):
    """Log the current exception with full traceback."""
    try:
        tb = traceback.format_exc()
    except Exception:
        tb = '(no traceback)'
    dlog('EXCEPTION %s\n%s' % (context, tb), level='ERROR',
         component=component)


def truncate(s, n=400):
    if s is None:
        return ''
    s = str(s)
    return s if len(s) <= n else s[:n] + '...(+%d)' % (len(s) - n)


def dump_http(method, url, status, headers=None, body_preview='',
              elapsed_ms=None, component='http'):
    parts = ['%s %s -> %s' % (method, truncate(url, 220), status)]
    if elapsed_ms is not None:
        parts.append('%.0fms' % elapsed_ms)
    if headers:
        try:
            keys = sorted(list(headers.keys()))[:10]
            parts.append('hdrs=' + ','.join(keys))
        except Exception:
            pass
    if body_preview:
        parts.append('body=' + truncate(body_preview, 300))
    dlog(' | '.join(parts),
         level='INFO' if (isinstance(status, int) and 200 <= status < 400)
                else 'WARN',
         component=component)


def session_banner(reason=''):
    """Write a clear marker so users can tell where each run starts."""
    if not is_enabled():
        return
    try:
        addon = xbmcaddon.Addon() if xbmcaddon is not None else None
        ver = addon.getAddonInfo('version') if addon else '?'
        py = sys.version.replace('\n', ' ')
        plat = ''
        try:
            plat = xbmc.getInfoLabel('System.BuildVersion') if xbmc else ''
        except Exception:
            pass
        dlog('=' * 60, component='session')
        dlog('Free Flow %s starting | reason=%s' % (ver, reason),
             component='session')
        dlog('Python: %s' % py, component='session')
        if plat:
            dlog('Kodi: %s' % plat, component='session')
        dlog('Profile: %s' % _profile_dir(), component='session')
        dlog('Debug log: %s' % log_path(), component='session')
        dlog('=' * 60, component='session')
    except Exception:
        dump_exception('session')


def safe_dump(obj, label='', max_chars=600, component='dump'):
    """Best-effort json dump of any object for diagnostics."""
    try:
        s = json.dumps(obj, default=str, ensure_ascii=False)
    except Exception:
        s = repr(obj)
    dlog('%s%s' % ((label + ': ') if label else '', truncate(s, max_chars)),
         component=component)
