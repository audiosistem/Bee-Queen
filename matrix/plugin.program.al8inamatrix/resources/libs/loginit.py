################################################################################
#      Copyright (C) 2019 drinfernoo                                           #
#                                                                              #
#  This Program is free software; you can redistribute it and/or modify        #
#  it under the terms of the GNU General Public License as published by        #
#  the Free Software Foundation; either version 2, or (at your option)         #
#  any later version.                                                          #
#                                                                              #
#  This Program is distributed in the hope that it will be useful,             #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the                #
#  GNU General Public License for more details.                                #
#                                                                              #
#  You should have received a copy of the GNU General Public License           #
#  along with XBMC; see the file COPYING.  If not, write to                    #
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.       #
#  http://www.gnu.org/copyleft/gpl.html                                        #
################################################################################

import xbmc
import xbmcgui

import os
import time

from xml.etree import ElementTree

from resources.libs.common.config import CONFIG
from resources.libs.common import logging
from resources.libs.common import tools

ORDER = ['fanart-tmdbhelper', 'omdb-tmdbhelper', 'tmdb-pov', 'tmdb-luckodi', 'fanart-luckodi', 'tmdb-umbrella', 'fanart-umbrella', 'tmdb-fen', 'omdb-fen', 'login-youtube']

LOGINID = {
    'fanart-tmdbhelper': {
        'name'     : 'Fanart.tv - TheMovieDb Helper',
        'saved'    : 'fanart-tmdbhelper',
        'plugin'   : 'plugin.video.themoviedb.helper',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'tmdbhelper_fanart'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.themoviedb.helper', 'settings.xml'),
        'default'  : 'fanarttv_clientkey',
        'data'     : ['fanarttv_clientkey'],
        'activate' : ''},
    'omdb-tmdbhelper': {
        'name'     : 'OMDb - TheMovieDb Helper',
        'saved'    : 'omdb-tmdbhelper',
        'plugin'   : 'plugin.video.themoviedb.helper',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.themoviedb.helper', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'tmdbhelper_omdb'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.themoviedb.helper', 'settings.xml'),
        'default'  : 'omdb_apikey',
        'data'     : ['omdb_apikey'],
        'activate' : ''},
    'tmdb-pov': {
        'name'     : 'TMDb - Pov',
        'saved'    : 'tmdb-pov',
        'plugin'   : 'plugin.video.pov',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.pov'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.pov', 'pov.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.pov', 'pov_fanart.png'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'pov_tmdb'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.pov', 'settings.xml'),
        'default'  : 'tmdb_api',
        'data'     : ['tmdb_api'],
        'activate' : ''},
    'tmdb-luckodi': {
        'name'     : 'TMDb - Luc Kodi',
        'saved'    : 'tmdb-luckodi',
        'plugin'   : 'plugin.video.luc_kodi',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'luckodi_tmdb'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.luc_kodi', 'settings.xml'),
        'default'  : 'tmdb.api.key',
        'data'     : ['tmdb.api.key'],
        'activate' : ''},
    'fanart-luckodi': {
        'name'     : 'Fanart TV - Luc Kodi',
        'saved'    : 'fanart-luckodi',
        'plugin'   : 'plugin.video.luc_kodi',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'luckodi_fanart'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.luc_kodi', 'settings.xml'),
        'default'  : 'fanart_tv.api_key',
        'data'     : ['fanart_tv.api_key'],
        'activate' : ''},
    'tmdb-umbrella': {
        'name'     : 'TMDb - Umbrella',
        'saved'    : 'tmdb-umbrella',
        'plugin'   : 'plugin.video.umbrella',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'umbrella_tmdb'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.umbrella', 'settings.xml'),
        'default'  : 'tmdb.apikey',
        'data'     : ['tmdb.apikey', 'tmdbusername', 'tmdbpassword'],
        'activate' : ''},
    'fanart-umbrella': {
        'name'     : 'Fanart TV - Umbrella',
        'saved'    : 'fanart-umbrella',
        'plugin'   : 'plugin.video.umbrella',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'umbrella_fanart'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.umbrella', 'settings.xml'),
        'default'  : 'fanart_tv.api_key',
        'data'     : ['fanart_tv.api_key'],
        'activate' : ''},
    'tmdb-fen': {
        'name'     : 'TMDb - Fen',
        'saved'    : 'tmdb-fen',
        'plugin'   : 'plugin.video.fen',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.fen'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_fanart.png'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'fen_tmdb'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.fen', 'settings.xml'),
        'default'  : 'tmdb_api',
        'data'     : ['tmdb_api'],
        'activate' : ''},
    'omdb-fen': {
        'name'     : 'OMDb - Fen',
        'saved'    : 'omdb-fen',
        'plugin'   : 'plugin.video.fen',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.fen'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_fanart.png'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'fen_omdb'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.fen', 'settings.xml'),
        'default'  : 'omdb_api',
        'data'     : ['omdb_api'],
        'activate' : ''},
    'login-youtube': {
        'name'     : 'Personal API - YouTube',
        'saved'    : 'login-youtube',
        'plugin'   : 'plugin.video.youtube',
        'path'     : os.path.join(CONFIG.ADDONS, 'plugin.video.youtube'),
        'icon'     : os.path.join(CONFIG.ADDONS, 'plugin.video.youtube', 'resources/media/icon.png'),
        'fanart'   : os.path.join(CONFIG.ADDONS, 'plugin.video.youtube', 'resources/media/fanart.jpg'),
        'file'     : os.path.join(CONFIG.LOGINFOLD, 'youtube_login'),
        'settings' : os.path.join(CONFIG.ADDON_DATA, 'plugin.video.youtube', 'settings.xml'),
        'default'  : 'youtube.api.key',
        'data'     : ['youtube.api.enable', 'youtube.api.key', 'youtube.api.id', 'youtube.api.secret'],
        'activate' : ''}
}


def login_user(who):
    user = None
    if LOGINID[who]:
        if os.path.exists(LOGINID[who]['path']):
            try:
                add = tools.get_addon_by_id(LOGINID[who]['plugin'])
                user = add.getSetting(LOGINID[who]['default'])
            except:
                pass
    return user


def login_it(do, who):
    if not os.path.exists(CONFIG.ADDON_DATA):
        os.makedirs(CONFIG.ADDON_DATA)
    if not os.path.exists(CONFIG.LOGINFOLD):
        os.makedirs(CONFIG.LOGINFOLD)
    if who == 'all':
        for log in ORDER:
            if os.path.exists(LOGINID[log]['path']):
                try:
                    addonid = tools.get_addon_by_id(LOGINID[log]['plugin'])
                    default = LOGINID[log]['default']
                    user = addonid.getSetting(default)
                    
                    update_login(do, log)
                except:
                    pass
            else:
                logging.log('[Login Info] {0}({1}) is not installed'.format(LOGINID[log]['name'], LOGINID[log]['plugin']), level=xbmc.LOGERROR)
        CONFIG.set_setting('loginnextsave', tools.get_date(days=3, formatted=True))
    else:
        if LOGINID[who]:
            if os.path.exists(LOGINID[who]['path']):
                update_login(do, who)
        else:
            logging.log('[Login Info] Invalid Entry: {0}'.format(who), level=xbmc.LOGERROR)


def clear_saved(who, over=False):
    if who == 'all':
        for login in LOGINID:
            clear_saved(login,  True)
    elif LOGINID[who]:
        file = LOGINID[who]['file']
        if os.path.exists(file):
            os.remove(file)
            logging.log_notify('[COLOR {0}]{1}[/COLOR]'.format(CONFIG.COLOR1, LOGINID[who]['name']),
                               '[COLOR {0}]Login Info: Removed![/COLOR]'.format(CONFIG.COLOR2),
                               2000,
                               LOGINID[who]['icon'])
        CONFIG.set_setting(LOGINID[who]['saved'], '')
    if not over:
        xbmc.executebuiltin('Container.Refresh()')


def update_login(do, who):
    file = LOGINID[who]['file']
    settings = LOGINID[who]['settings']
    data = LOGINID[who]['data']
    addonid = tools.get_addon_by_id(LOGINID[who]['plugin'])
    saved = LOGINID[who]['saved']
    default = LOGINID[who]['default']
    user = addonid.getSetting(default)
    suser = CONFIG.get_setting(saved)
    name = LOGINID[who]['name']
    icon = LOGINID[who]['icon']

    if do == 'update':
        if not user == '':
            try:
                root = ElementTree.Element(saved)
                
                for setting in data:
                    login = ElementTree.SubElement(root, 'login')
                    id = ElementTree.SubElement(login, 'id')
                    id.text = setting
                    value = ElementTree.SubElement(login, 'value')
                    value.text = addonid.getSetting(setting)
                  
                tree = ElementTree.ElementTree(root)
                tree.write(file)
                
                user = addonid.getSetting(default)
                CONFIG.set_setting(saved, user)
                
                logging.log('Login Data Saved for {0}'.format(name), level=xbmc.LOGINFO)
            except Exception as e:
                logging.log("[Login Data] Unable to Update {0} ({1})".format(who, str(e)), level=xbmc.LOGERROR)
        else:
            logging.log('Login Data Not Registered for {0}'.format(name))
    elif do == 'restore':
        if os.path.exists(file):
            tree = ElementTree.parse(file)
            root = tree.getroot()
            
            try:
                for setting in root.findall('login'):
                    id = setting.find('id').text
                    value = setting.find('value').text
                    addonid.setSetting(id, value)
                    
                user = addonid.getSetting(default)
                CONFIG.set_setting(saved, user)
                logging.log('Login Data Restored for {0}'.format(name), level=xbmc.LOGINFO)
            except Exception as e:
                logging.log("[Login Info] Unable to Restore {0} ({1})".format(who, str(e)), level=xbmc.LOGERROR)
        else:
            logging.log('Login Data Not Found for {0}'.format(name))
    elif do == 'clearaddon':
        logging.log('{0} SETTINGS: {1}'.format(name, settings), level=xbmc.LOGDEBUG)
        if os.path.exists(settings):
            try:
                tree = ElementTree.parse(settings)
                root = tree.getroot()
                
                for setting in root.findall('setting'):
                    if setting.attrib['id'] in data:
                        logging.log('Removing Setting: {0}'.format(setting.attrib))
                        root.remove(setting)
                            
                tree.write(settings)
                
                logging.log_notify("[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, name),
                                   '[COLOR {0}]Addon Data: Cleared![/COLOR]'.format(CONFIG.COLOR2),
                                   2000,
                                   icon)
            except Exception as e:
                logging.log("[Trakt Data] Unable to Clear Addon {0} ({1})".format(who, str(e)), level=xbmc.LOGERROR)
    xbmc.executebuiltin('Container.Refresh()')


def auto_update(who):
    if who == 'all':
        for log in LOGINID:
            if os.path.exists(LOGINID[log]['path']):
                auto_update(log)
    elif LOGINID[who]:
        if os.path.exists(LOGINID[who]['path']):
            u = login_user(who)
            su = CONFIG.get_setting(LOGINID[who]['saved'])
            n = LOGINID[who]['name']
            if not u or u == '':
                return
            elif su == '':
                login_it('update', who)
            elif not u == su:
                dialog = xbmcgui.Dialog()

                if dialog.yesno(CONFIG.ADDONTITLE,
                                    "Would you like to save the [COLOR {0}]Login Info[/COLOR] for [COLOR {1}]{2}[/COLOR]?".format(CONFIG.COLOR2, CONFIG.COLOR1, n),
                                    "Addon: [COLOR springgreen][B]{0}[/B][/COLOR]".format(u),
                                    "Saved:[/COLOR] [COLOR red][B]{0}[/B][/COLOR]".format(su) if not su == '' else 'Saved:[/COLOR] [COLOR red][B]None[/B][/COLOR]',
                                    yeslabel="[B][COLOR springgreen]Save Data[/COLOR][/B]",
                                    nolabel="[B][COLOR red]No Cancel[/COLOR][/B]"):
                    login_it('update', who)
            else:
                login_it('update', who)


def import_list(who):
    if who == 'all':
        for log in LOGINID:
            if os.path.exists(LOGINID[log]['file']):
                import_list(log)
    elif LOGINID[who]:
        if os.path.exists(LOGINID[who]['file']):
            file = LOGINID[who]['file']
            addonid = tools.get_addon_by_id(LOGINID[who]['plugin'])
            saved = LOGINID[who]['saved']
            default = LOGINID[who]['default']
            suser = CONFIG.get_setting(saved)
            name = LOGINID[who]['name']
            
            tree = ElementTree.parse(file)
            root = tree.getroot()
            
            for setting in root.findall('login'):
                id = setting.find('id').text
                value = setting.find('value').text
            
                addonid.setSetting(id, value)

            logging.log_notify("[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, name),
                       '[COLOR {0}]Login Data: Imported![/COLOR]'.format(CONFIG.COLOR2))


def activate_login(who):
    if LOGINID[who]:
        if os.path.exists(LOGINID[who]['path']):
            act = LOGINID[who]['activate']
            addonid = tools.get_addon_by_id(LOGINID[who]['plugin'])
            if act == '':
                addonid.openSettings()
            else:
                xbmc.executebuiltin(LOGINID[who]['activate'])
        else:
            dialog = xbmcgui.Dialog()

            dialog.ok(CONFIG.ADDONTITLE, '{0} is not currently installed.'.format(LOGINID[who]['name']))
    else:
        xbmc.executebuiltin('Container.Refresh()')
        return

    check = 0
    while not login_user(who) or login_user(who) == "":
        if check == 30:
            break
        check += 1
        time.sleep(10)
    xbmc.executebuiltin('Container.Refresh()')