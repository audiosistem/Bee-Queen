# -*- coding: utf-8 -*-
"""Common helpers for Vidscr addon."""
import sys
import os
import json
from urllib.parse import urlencode, parse_qsl, quote_plus

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_VERSION = ADDON.getAddonInfo('version')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

if not xbmcvfs.exists(PROFILE_PATH):
    xbmcvfs.mkdirs(PROFILE_PATH)

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE_URL = sys.argv[0] if sys.argv else 'plugin://plugin.video.vidscr/'

ICON = os.path.join(ADDON_PATH, 'icon.png')
FANART = os.path.join(ADDON_PATH, 'fanart.jpg')
MENU_ICON_DIR = os.path.join(ADDON_PATH, 'resources', 'menu_icons')


# action -> menu-icon stem mapping. Anything not in this table falls back
# to the addon's main icon. Drop a same-named PNG into
# resources/menu_icons/ to override any placeholder.
_ACTION_ICON_MAP = {
    # Root
    'movies_root':       'movies',
    'tv_root':           'tv',
    'search_root':       'search',
    'my_lists':          'my_lists',
    'open_settings':     'settings',
    'continue_watching': 'continue',
    'on_deck':           'on_deck',
    'history_hub':       'history',

    # Movies submenu
    'movies_new':       'movies_new',
    'movies_trending':  'movies_trending',
    'movies_popular':   'movies_popular',
    'movies_top':       'movies_top',
    'movies_upcoming':  'movies_upcoming',
    'movies_oscars':    'movies_oscars',
    'franchises_root':  'franchises',
    'franchise_view':   'franchises',
    'directors_root':   'directors',
    'director_view':    'directors',
    'movies_decades':   'decades',
    'movies_by_decade': 'decades',
    'movies_keywords':  'keywords',
    'movies_by_keyword':'keywords',
    'movies_genres':    'genres',
    'movies_by_genre':  'genres',
    'people_root':      'actors',
    'person_view':      'actors',
    'movies_studios':   'studios',
    'movies_by_studio': 'studios',
    'ambient_mode':     'ambient',

    # TV submenu
    'tv_calendar':      'tv_new',
    'tv_premieres':     'tv_premieres',
    'tv_trending':      'tv_trending',
    'tv_airing_today':  'tv_airing',
    'tv_on_air':        'tv_on_air',
    'tv_popular':       'tv_popular',
    'tv_top':           'tv_top',
    'tv_collections':   'tv_collections',
    'tv_collection_view':'tv_collections',
    'tv_genres':        'tv_genres',
    'tv_by_genre':      'tv_genres',
    'tv_networks':      'tv_networks',
    'tv_by_network':    'tv_networks',

    # Search submenu
    'search_movie':     'search_movie',
    'search_tv':        'search_tv',
    'search_person':    'search_person',
    'search_multi':     'search_multi',

    # My Lists root
    'trakt_mylists':    'trakt',
    'trakt_auth':       'trakt',
    'simkl_mylists':    'simkl',
    'simkl_auth':       'simkl',
    'bingebase_mylists':'bingebase',
    'bingebase_auth':   'bingebase',
    'bingebase_notice': 'bingebase',

    # Trakt subfolders (kind-based — also handled by _kind_icon below)
    'trakt_list':                'trakt',  # overridden by kind
    'trakt_history':             'history',
    'trakt_my_ratings':          'ratings',
    'trakt_personal_lists':      'personal',
    'trakt_personal_list_view':  'personal',
    'trakt_personal_list_view_type': 'personal',

    # SIMKL subfolders
    'simkl_list':       'simkl',          # overridden by kind

    # Bingebase subfolders
    'bingebase_watched': 'bb_watched',
}


# kind -> icon stem (used for trakt_list / simkl_list where the action
# is the same but the kind differentiates them).
_KIND_ICON_MAP = {
    'recommendations': 'recommendations',
    'watchlist':       'watchlist',
    'collection':      'collection',
    'favorites':       'favorites',
    'plantowatch':     'plantowatch',
    'completed':       'completed',
    'hold':            'hold',
    'dropped':         'dropped',
}


def menu_icon(action=None, kind=None):
    """Return the absolute path of the placeholder icon for an action+kind,
    falling back to the addon's main icon."""
    stem = None
    if kind and kind in _KIND_ICON_MAP:
        stem = _KIND_ICON_MAP[kind]
    elif action and action in _ACTION_ICON_MAP:
        stem = _ACTION_ICON_MAP[action]
    if stem:
        p = os.path.join(MENU_ICON_DIR, stem + '.png')
        if os.path.exists(p):
            return p
    return ICON


def get_setting(key, default=''):
    val = ADDON.getSetting(key)
    return val if val else default


def get_setting_bool(key, default=False):
    val = ADDON.getSetting(key)
    if not val:
        return default
    return val.lower() in ('true', '1', 'yes')


def get_setting_int(key, default=0):
    try:
        return int(ADDON.getSetting(key))
    except (ValueError, TypeError):
        return default


DEBUG_LOG_PATH = os.path.join(PROFILE_PATH, 'vidscr_debug.log')
_MAX_LOG_BYTES = 256 * 1024  # 256 KB rolling


def log(msg, level=xbmc.LOGINFO):
    try:
        xbmc.log('[Vidscr] %s' % msg, level)
    except Exception:
        pass
    # Also mirror to an addon-local debug log when debug_log is enabled,
    # so the user can view it directly from the addon settings without
    # hunting through kodi.log.
    try:
        if get_setting_bool('debug_log'):
            import datetime
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            line = '[%s] %s\n' % (ts, msg)
            # Rotate if too big
            if os.path.exists(DEBUG_LOG_PATH) and os.path.getsize(DEBUG_LOG_PATH) > _MAX_LOG_BYTES:
                try:
                    with open(DEBUG_LOG_PATH, 'rb') as f:
                        f.seek(-_MAX_LOG_BYTES // 2, 2)
                        tail = f.read()
                    with open(DEBUG_LOG_PATH, 'wb') as f:
                        f.write(tail)
                except Exception:
                    pass
            with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(line)
    except Exception:
        pass


def clear_debug_log():
    try:
        if os.path.exists(DEBUG_LOG_PATH):
            os.remove(DEBUG_LOG_PATH)
    except Exception:
        pass


def read_debug_log():
    try:
        if not os.path.exists(DEBUG_LOG_PATH):
            return ''
        with open(DEBUG_LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return 'Error reading log: %s' % e


def build_url(**kwargs):
    return '%s?%s' % (BASE_URL, urlencode({k: v for k, v in kwargs.items() if v is not None}))


def parse_params():
    qs = sys.argv[2][1:] if len(sys.argv) > 2 else ''
    return dict(parse_qsl(qs))


def notify(message, heading=None, icon=None, time=4000):
    xbmcgui.Dialog().notification(heading or ADDON_NAME, message, icon or ICON, time)


def keyboard(heading='Search'):
    kb = xbmc.Keyboard('', heading)
    kb.doModal()
    if kb.isConfirmed():
        return kb.getText()
    return ''


def end_directory(content='videos', sort_methods=None, cache_to_disc=True):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    if sort_methods:
        for sm in sort_methods:
            xbmcplugin.addSortMethod(HANDLE, sm)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache_to_disc)


def add_dir(label, params, info=None, art=None, is_folder=True, context=None, plot=None):
    li = xbmcgui.ListItem(label=label)
    # Auto-pick a menu icon based on the action (+ kind, for trakt/simkl
    # list variants). Caller can still override by passing a NON-default
    # ``art={'icon': '<path>', ...}`` dict; passing the addon's main ICON
    # path counts as "no override" so the auto-pick still wins.
    auto_icon = menu_icon(action=params.get('action'), kind=params.get('kind'))
    item_art = {'icon': auto_icon, 'thumb': auto_icon, 'fanart': FANART}
    if art:
        for k, v in art.items():
            if not v:
                continue
            # The default-icon-as-override case: caller wrote
            # ``art={'icon': ICON}`` (the legacy pattern, before we had
            # per-key placeholders). Skip those so auto-pick stays.
            if k in ('icon', 'thumb') and v == ICON:
                continue
            item_art[k] = v
    li.setArt(item_art)
    info_dict = {'title': label}
    if plot:
        info_dict['plot'] = plot
    if info:
        info_dict.update(info)
    try:
        li.setInfo('video', info_dict)
    except Exception:
        pass
    if not is_folder:
        li.setProperty('IsPlayable', 'true')
    if context:
        li.addContextMenuItems(context, replaceItems=False)
    url = build_url(**params)
    xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)


def cache_path(name):
    return os.path.join(PROFILE_PATH, name)
