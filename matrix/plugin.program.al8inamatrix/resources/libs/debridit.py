import xbmc, xbmcgui, os
from xml.etree import ElementTree
from resources.libs.common.config import CONFIG
from resources.libs.common import logging, tools

# Am pus TOATE cheile pe care le cauta Wizard-ul tau original
ORDER = ['ad', 'pm', 'urlrd', 'fenrd', 'umbrellard', 'povrd', 'luc_kodird']

DEBRIDID = {
    'ad': {'name': 'AllDebrid', 'plugin': 'script.module.resolveurl', 'saved': 'ad', 'path': '', 'icon': '', 'fanart': '', 'file': os.path.join(CONFIG.DEBRIDFOLD, 'ad'), 'default': '', 'data': [], 'activate': ''},
    'pm': {'name': 'Premiumize', 'plugin': 'script.module.resolveurl', 'saved': 'pm', 'path': '', 'icon': '', 'fanart': '', 'file': os.path.join(CONFIG.DEBRIDFOLD, 'pm'), 'default': '', 'data': [], 'activate': ''},
    'urlrd': {'name': 'URLResolver', 'plugin': 'script.module.urlresolver', 'saved': 'urlrd', 'path': '', 'icon': '', 'fanart': '', 'file': os.path.join(CONFIG.DEBRIDFOLD, 'url_rd'), 'default': '', 'data': [], 'activate': ''},
    'fenrd': {
        'name': 'Fen RD', 'plugin': 'plugin.video.fen', 'saved': 'fenrd',
        'path': os.path.join(CONFIG.ADDONS, 'plugin.video.fen'),
        'icon': os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_icon.png'),
        'fanart': os.path.join(CONFIG.ADDONS, 'plugin.video.fen', 'resources/media/fen_fanart.jpg'),
        'file': os.path.join(CONFIG.DEBRIDFOLD, 'fen_rd'), 'default': 'rd.token',
        'data': ['rd.account_id', 'rd.token', 'rd.client_id', 'rd.refresh', 'rd.secret', 'rd.enabled'],
        'activate': 'RunPlugin(plugin://plugin.video.fen/?mode=real_debrid.authenticate)'
    },
    'umbrellard': {
        'name': 'Umbrella RD', 'plugin': 'plugin.video.umbrella', 'saved': 'umbrellard',
        'path': os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella'),
        'icon': os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'icon.png'),
        'fanart': os.path.join(CONFIG.ADDONS, 'plugin.video.umbrella', 'fanart.png'),
        'file': os.path.join(CONFIG.DEBRIDFOLD, 'umbrella_rd'), 'default': 'realdebridtoken',
        'data': ['realdebridtoken', 'realdebridusername', 'realdebrid.clientid', 'realdebridrefresh', 'realdebridsecret', 'realdebrid.enable'],
        'activate': 'RunPlugin(plugin://plugin.video.umbrella/?action=authRealDebrid)'
    },
    'povrd': {
        'name': 'POV RD', 'plugin': 'plugin.video.pov', 'saved': 'povrd',
        'path': os.path.join(CONFIG.ADDONS, 'plugin.video.pov'),
        'icon': os.path.join(CONFIG.ADDONS, 'plugin.video.pov', 'pov.png'),
        'fanart': os.path.join(CONFIG.ADDONS, 'plugin.video.pov', 'pov_fanart.jpg'),
        'file': os.path.join(CONFIG.DEBRIDFOLD, 'pov_rd'), 'default': 'rd.token',
        'data': ['rd.username', 'rd.token', 'rd.client_id', 'rd.refresh', 'rd.secret'],
        'activate': 'RunPlugin(plugin://plugin.video.pov/?mode=real_debrid.authenticate)'
    },
    'luc_kodird': {
        'name': 'Luckodi RD', 'plugin': 'plugin.video.luc_kodi', 'saved': 'luc_kodird',
        'path': os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi'),
        'icon': os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'icon.png'),
        'fanart': os.path.join(CONFIG.ADDONS, 'plugin.video.luc_kodi', 'fanart.jpg'),
        'file': os.path.join(CONFIG.DEBRIDFOLD, 'luckodi_rd'), 'default': 'realdebrid.token',
        'data': ['realdebrid.token', 'realdebrid.username', 'realdebrid.client_id', 'realdebrid.refresh', 'realdebrid.secret', 'realdebrid.enable'],
        'activate': 'RunPlugin(plugin://plugin.video.luc_kodi/?mode=real_debrid.authenticate)'
    }
}

def debrid_user(who):
    if who in DEBRIDID and DEBRIDID[who]['plugin'] != '' and DEBRIDID[who]['default'] != '':
        try:
            addon = tools.get_addon_by_id(DEBRIDID[who]['plugin'])
            return addon.getSetting(DEBRIDID[who]['default'])
        except: return ''
    return ''

def debrid_it(do, who):
    if not os.path.exists(CONFIG.DEBRIDFOLD): os.makedirs(CONFIG.DEBRIDFOLD)
    if who == 'all':
        for item in ORDER: update_debrid(do, item)
    elif who in DEBRIDID: update_debrid(do, who)

def update_debrid(do, who):
    if who not in DEBRIDID or DEBRIDID[who]['plugin'] == '' or DEBRIDID[who]['data'] == []: return
    info = DEBRIDID[who]
    try:
        addon = tools.get_addon_by_id(info['plugin'])
        if do == 'update':
            root = ElementTree.Element(info['saved'])
            for s_id in info['data']:
                item = ElementTree.SubElement(root, 'debrid')
                ElementTree.SubElement(item, 'id').text = s_id
                ElementTree.SubElement(item, 'value').text = addon.getSetting(s_id)
            ElementTree.ElementTree(root).write(info['file'])
            CONFIG.set_setting(info['saved'], addon.getSetting(info['default']))
        elif do == 'restore' and os.path.exists(info['file']):
            tree = ElementTree.parse(info['file'])
            for setting in tree.getroot().findall('debrid'):
                addon.setSetting(setting.find('id').text, setting.find('value').text)
    except: pass

def clear_saved(who, over=False):
    if who == 'all':
        for d in ORDER: clear_saved(d, True)
    elif who in DEBRIDID and DEBRIDID[who]['file'] != '':
        if os.path.exists(DEBRIDID[who]['file']): os.remove(DEBRIDID[who]['file'])
        CONFIG.set_setting(DEBRIDID[who]['saved'], '')
    if not over: xbmc.executebuiltin('Container.Refresh()')

def activate_debrid(who):
    if who in DEBRIDID and DEBRIDID[who]['plugin'] != '':
        act = DEBRIDID[who]['activate']
        if act == '': tools.get_addon_by_id(DEBRIDID[who]['plugin']).openSettings()
        else: xbmc.executebuiltin(act)