################################################################################
#      Copyright (C) 2019 drinfernoo                                           #
#                                                                              #
#  This Program is free software; you can redistribute it and/or modify        #
#  it under the terms of the GNU General Public License as published by        #
#  the Free Software Foundation; either version 2, or (at your option)         #
#  any later version.                                                          #
################################################################################

import xbmc
import xbmcgui
import os
import time
from xml.etree import ElementTree

from resources.libs.common.config import CONFIG
from resources.libs.common import logging
from resources.libs.common import tools

# Ordinea de procesare pentru add-on-urile tale
ORDER = ['pov', 'umbrella', 'fen', 'luc_kodi', 'tmdbmovies', 'tmdbhelper']

TRAKTID = {
    'pov': {
        'name'     : 'POV',
        'plugin'   : 'plugin.video.pov',
        'saved'    : 'pov',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.pov'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.pov', 'pov.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.pov', 'pov_fanart.jpg'),
        'file'     : os.path.join(CONFIG.TRAKTFOLD, 'pov_trakt'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.pov', 'settings.xml'),
        'default'  : 'trakt_user', # Sursa: settings.xml
        'data'     : ['trakt.token', 'trakt.refresh', 'trakt_user', 'trakt.expires'], # Sursa: settings.xml
        'activate' : 'RunPlugin(plugin://plugin.video.pov/?action=authTrakt)'},
    'umbrella': {
        'name'     : 'Umbrella',
        'plugin'   : 'plugin.video.umbrella',
        'saved'  : 'umbrella',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.TRAKTFOLD, 'umbrella_trakt'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.umbrella', 'settings.xml'),
        'default'  : 'trakt.user.name',
        'data'     : ['trakt.user.token', 'trakt.user.name', 'trakt.token.expires', 'trakt.refreshtoken'],
        'activate' : 'RunPlugin(plugin://plugin.video.umbrella/?action=authTrakt)'},
'fen': {
        'name'     : 'Fen',
        'plugin'   : 'plugin.video.fen',
        'saved'    : 'fen',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.fen'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_fanart.png'),
        'file'     : os.path.join(CONFIG.TRAKTFOLD, 'fen_trakt'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.fen', 'settings.xml'),
        'default'  : 'trakt.user',
        'data'     : ['trakt.user', 'trakt.token', 'trakt.refresh', 'trakt.expires'],
        'activate' : 'RunPlugin(plugin://plugin.video.fen/?action=authTrakt)'},
'luc_kodi': {
        'name'     : 'Luc Kodi',
        'plugin'   : 'plugin.video.luc_kodi',
        'saved'    : 'luc_kodi',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.TRAKTFOLD, 'luc_kodi_trakt'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.luc_kodi', 'settings.xml'),
        'default'  : 'trakt.username',
        'data'     : ['trakt.username', 'trakt.token', 'trakt.refresh', 'trakt.expires'],
        'activate' : 'RunPlugin(plugin://plugin.video.luc_kodi/?action=authTrakt)'},
    'tmdbmovies': {
        'name'     : 'TMDb Movies',
        'plugin'   : 'plugin.video.tmdbmovies',
        'saved'    : 'tmdbmovies',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.tmdbmovies'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.tmdbmovies', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.tmdbmovies', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.TRAKTFOLD, 'tmdbmovies_trakt'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.tmdbmovies', 'settings.xml'),
        'default'  : 'trakt_status',
        'data'     : ['trakt_status'],
        'activate' : 'RunPlugin(plugin://plugin.video.tmdbmovies/?action=authTrakt)'},
'tmdbhelper': {
        'name'     : 'TMDb Helper',
        'plugin'   : 'plugin.video.themoviedb.helper',
        'saved'    : 'tmdbhelper',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.TRAKTFOLD, 'tmdbhelper_trakt'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.themoviedb.helper', 'settings.xml'),
        'default'  : 'trakt_token',
        'data'     : ['trakt_token', 'trakt.user', 'trakt_watchedindicators'],
        'activate' : 'RunScript(plugin.video.themoviedb.helper, authenticate_trakt)'},
}

def trakt_user(who):
    user = None
    if who in TRAKTID:
        if os.path.exists(TRAKTID[who]['path']):
            try:
                add = tools.get_addon_by_id(TRAKTID[who]['plugin'])
                user = add.getSetting(TRAKTID[who]['default'])
            except:
                return None
    return user

def trakt_it(do, who):
    if not os.path.exists(CONFIG.ADDON_DATA):
        os.makedirs(CONFIG.ADDON_DATA)
    if not os.path.exists(CONFIG.TRAKTFOLD):
        os.makedirs(CONFIG.TRAKTFOLD)
    if who == 'all':
        for log in ORDER:
            if os.path.exists(TRAKTID[log]['path']):
                try:
                    update_trakt(do, log)
                except:
                    pass
            else:
                logging.log('[Trakt Data] {0} is not installed'.format(TRAKTID[log]['name']), level=xbmc.LOGERROR)
        CONFIG.set_setting('traktnextsave', tools.get_date(days=3, formatted=True))
    else:
        if who in TRAKTID and os.path.exists(TRAKTID[who]['path']):
            update_trakt(do, who)

def clear_saved(who, over=False):
    if who == 'all':
        for trakt in TRAKTID:
            clear_saved(trakt, True)
    elif who in TRAKTID:
        file = TRAKTID[who]['file']
        if os.path.exists(file):
            os.remove(file)
            logging.log_notify("[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, TRAKTID[who]['name']),
                               '[COLOR {0}]Trakt Data: Removed![/COLOR]'.format(CONFIG.COLOR2),
                               2000,
                               TRAKTID[who]['icon'])
        CONFIG.set_setting(TRAKTID[who]['saved'], '')
    if not over:
        xbmc.executebuiltin('Container.Refresh()')

def update_trakt(do, who):
    file = TRAKTID[who]['file']
    settings = TRAKTID[who]['settings']
    data = TRAKTID[who]['data']
    addonid = tools.get_addon_by_id(TRAKTID[who]['plugin'])
    saved = TRAKTID[who]['saved']
    default = TRAKTID[who]['default']
    name = TRAKTID[who]['name']
    icon = TRAKTID[who]['icon']

    if do == 'update':
        user = addonid.getSetting(default)
        if user:
            try:
                root = ElementTree.Element(saved)
                for setting in data:
                    trakt = ElementTree.SubElement(root, 'trakt')
                    id_node = ElementTree.SubElement(trakt, 'id')
                    id_node.text = setting
                    val_node = ElementTree.SubElement(trakt, 'value')
                    val_node.text = addonid.getSetting(setting)
                tree = ElementTree.ElementTree(root)
                tree.write(file)
                CONFIG.set_setting(saved, user)
                logging.log('Trakt Data Saved for {0}'.format(name), level=xbmc.LOGINFO)
            except Exception as e:
                logging.log("[Trakt Data] Unable to Update {0} ({1})".format(who, str(e)), level=xbmc.LOGERROR)
    elif do == 'restore':
        if os.path.exists(file):
            try:
                tree = ElementTree.parse(file)
                root = tree.getroot()
                for setting in root.findall('trakt'):
                    sid = setting.find('id').text
                    sval = setting.find('value').text
                    addonid.setSetting(sid, sval)
                user = addonid.getSetting(default)
                CONFIG.set_setting(saved, user)
                logging.log('Trakt Data Restored for {0}'.format(name), level=xbmc.LOGINFO)
            except Exception as e:
                logging.log("[Trakt Data] Unable to Restore {0} ({1})".format(who, str(e)), level=xbmc.LOGERROR)
    xbmc.executebuiltin('Container.Refresh()')

def auto_update(who):
    if who == 'all':
        for log in TRAKTID:
            if os.path.exists(TRAKTID[log]['path']):
                auto_update(log)
    elif who in TRAKTID and os.path.exists(TRAKTID[who]['path']):
        u = trakt_user(who)
        su = CONFIG.get_setting(TRAKTID[who]['saved'])
        if u and (su == '' or not u == su):
            trakt_it('update', who)
        elif u:
            trakt_it('update', who)

def import_list(who):
    if who == 'all':
        for log in TRAKTID:
            import_list(log)
    elif who in TRAKTID and os.path.exists(TRAKTID[who]['file']):
        file = TRAKTID[who]['file']
        addonid = tools.get_addon_by_id(TRAKTID[who]['plugin'])
        tree = ElementTree.parse(file)
        root = tree.getroot()
        for setting in root.findall('trakt'):
            sid = setting.find('id').text
            sval = setting.find('value').text
            addonid.setSetting(sid, sval)
        logging.log_notify("[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, TRAKTID[who]['name']),
                           '[COLOR {0}]Trakt Data: Imported![/COLOR]'.format(CONFIG.COLOR2))

def activate_trakt(who):
    if who in TRAKTID and os.path.exists(TRAKTID[who]['path']):
        act = TRAKTID[who]['activate']
        if act == '':
            tools.get_addon_by_id(TRAKTID[who]['plugin']).openSettings()
        else:
            xbmc.executebuiltin(act)
        
        check = 0
        while not trakt_user(who) and check < 30:
            check += 1
            time.sleep(10)
    xbmc.executebuiltin('Container.Refresh()')