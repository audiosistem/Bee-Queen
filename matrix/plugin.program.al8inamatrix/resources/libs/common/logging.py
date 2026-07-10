# -*- coding: utf-8 -*-
#      Copyright (C) 2019 drinfernoo
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with XBMC; see the file COPYING.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html

import xbmc
import xbmcaddon
import xbmcgui

import os
import sys
from urllib.parse import urlencode

from resources.libs.common.config import CONFIG


def log(msg, level=xbmc.LOGDEBUG):
    if CONFIG.get_setting('debug') == 'true' or level in [xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR, xbmc.LOGFATAL]:
        try:
            if isinstance(msg, bytes):
                msg = msg.decode('utf-8', errors='ignore')
            xbmc.log('{0} -> {1}'.format(CONFIG.ADDONTITLE, msg), level)
        except Exception:
            try:
                xbmc.log('{0} -> {1}'.format(CONFIG.ADDONTITLE, repr(msg)), level)
            except Exception:
                pass


def log_notify(title, message, icon=None, time=4000, sound=True):
    try:
        if isinstance(title, bytes):
            title = title.decode('utf-8', errors='ignore')
        if isinstance(message, bytes):
            message = message.decode('utf-8', errors='ignore')
            
        if icon is None:
            if hasattr(CONFIG, 'ICON'):
                icon = CONFIG.ICON
            elif hasattr(CONFIG, 'ADDON_ICON'):
                icon = CONFIG.ADDON_ICON
            elif hasattr(CONFIG, 'ADDON'):
                icon = CONFIG.ADDON.getAddonInfo('icon')
            else:
                icon = ''

        dialog = xbmcgui.Dialog()
        dialog.notification(title, message, icon, time, sound)
    except Exception as e:
        log('Eroare notificare: {0}'.format(str(e)), level=xbmc.LOGERROR)


def swap_debug():
    if CONFIG.get_setting('debug') == 'true':
        CONFIG.set_setting('debug', 'false')
        log('Debug Logging Disabled', level=xbmc.LOGINFO)
        log_notify("[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, CONFIG.ADDONTITLE),
                   "[COLOR {0}]Debug Logging Disabled![/COLOR]".format(CONFIG.COLOR2))
    else:
        CONFIG.set_setting('debug', 'true')
        log('Debug Logging Enabled', level=xbmc.LOGINFO)
        log_notify("[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, CONFIG.ADDONTITLE),
                   "[COLOR {0}]Debug Logging Enabled![/COLOR]".format(CONFIG.COLOR2))
    xbmc.executebuiltin('Container.Refresh()')


def upload_log():
    log_file = xbmc.translatePath('special://logpath/kodi.log') if sys.version_info[0] < 3 else xbmc.convertLegalFilename(xbmc.translatePath('special://logpath/kodi.log'))
    if not os.path.exists(log_file):
        log_notify(CONFIG.ADDONTITLE, "Fișierul log nu a fost găsit!")
        return

    log("Se pregătește încărcarea fișierului log...", level=xbmc.LOGINFO)


def view_log_file():
    from resources.libs.gui import window
    log_file = xbmc.translatePath('special://logpath/kodi.log')
    window.show_log_viewer(log_file=log_file)


def error_checking(last=False, count=False, **kwargs):
    log("Verificare erori în kodi.log...", level=xbmc.LOGINFO)
    # Returnăm 0 erori implicit pentru ca scriptul apelant să meargă mai departe fără crash
    if count:
        return 0
    return False