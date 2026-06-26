"""Minimal Kodi-control shim used by the extras helper modules.

Original upstream had a sprawling control.py exposing settings, paths,
notifications, dialogs, OAuth client keys etc. The extras helpers only
touch a handful of those — anything that matters for stream resolution.
We forward the relevant pieces to vidscr's existing ``common`` module
and stub out the rest so the helper code stays diff-clean.
"""
from __future__ import annotations

import os

import xbmcaddon
import xbmcvfs
import xbmcgui

try:
    import xbmc as _xbmc
except Exception:
    _xbmc = None

from ... import common as _common

ADDON = xbmcaddon.Addon()
addonInfo = ADDON.getAddonInfo

dialog = xbmcgui.Dialog()
infoDialog = lambda message, heading='', icon='', time=3000: \
    dialog.notification(heading or addonInfo('name'), message, icon, time)
notification = lambda heading='', message='', icon='', time=3000: \
    dialog.notification(heading or addonInfo('name'), message, icon, time)

dataPath = xbmcvfs.translatePath(addonInfo('profile'))
settingsFile = os.path.join(dataPath, 'settings.xml')


def setting(key):
    """Read a vidscr setting. Helper modules query ad-hoc keys like
    ``mod.domains`` / ``sourcefilter.and`` etc — these don't exist on
    vidscr so we just return the default (the caller already does
    ``setting(...) or 'true'`` everywhere)."""
    try:
        return ADDON.getSetting(key) or ''
    except Exception:
        return ''


def setSetting(key, value):
    try:
        ADDON.setSetting(key, str(value))
    except Exception:
        pass


def lang(_id):
    return ''


def log(msg, level=1):
    _common.log('[extras] %s' % msg)


sleep = _xbmc.sleep if _xbmc else (lambda ms: None)


def get_plugin_url():
    return ''


def transPath(path):
    try:
        return xbmcvfs.translatePath(path)
    except Exception:
        return path


legalfilename = lambda f: f
