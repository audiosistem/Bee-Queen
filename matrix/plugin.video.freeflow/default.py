# -*- coding: utf-8 -*-
"""
Free Flow - Kodi Video Addon
Author: Chains
Reads directories/items from thechains24.com text feeds, resolves links via
ResolveURL, and enriches missing artwork via TMDB. Uses a background service
(service.py) to keep an index of every item so we can offer:
  - "My Free Flow" (top of root) - Trakt-powered menus and personal lists.
  - "What's New" - items added since the last scan, with the feed each one
    came from.
  - "Search" - universal search across the whole tree.
"""
import os
import sys
import time
import urllib.parse as urlparse

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_ICON = os.path.join(ADDON_PATH, 'icon.png')
ADDON_FANART = os.path.join(ADDON_PATH, 'fanart.jpg')

sys.path.insert(0, os.path.join(ADDON_PATH, 'resources', 'lib'))
import feed  # noqa: E402
import trakt  # noqa: E402
import debug as dbg  # noqa: E402
import resolvers as ffresolvers  # noqa: E402
import downloads as ffdownloads  # noqa: E402

try:
    import resolveurl
except Exception:
    resolveurl = None

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE_URL = sys.argv[0] if len(sys.argv) > 0 else ''


SPLASH_DURATION_MS = 4000


def show_splash():
    """Display the fanart full-screen for 4 seconds on addon launch."""
    if ADDON.getSetting('show_splash').lower() != 'true':
        return
    win = None
    try:
        win = xbmcgui.WindowDialog()
        bg = xbmcgui.ControlImage(0, 0, 1280, 720, ADDON_FANART,
                                  aspectRatio=2)
        win.addControl(bg)
        win.show()
        xbmc.Monitor().waitForAbort(SPLASH_DURATION_MS / 1000.0)
    except Exception as e:
        log('splash error: %s' % e, xbmc.LOGERROR)
    finally:
        try:
            if win is not None:
                win.close()
        except Exception:
            pass


def log(msg, level=xbmc.LOGINFO):
    try:
        xbmc.log('[%s] %s' % (ADDON_ID, msg), level)
    except Exception:
        pass


def build_url(query):
    return BASE_URL + '?' + urlparse.urlencode(query)


def make_list_item(title, thumb, fanart, plot):
    li = xbmcgui.ListItem(label=title)
    li.setArt({'thumb': thumb, 'icon': thumb, 'poster': thumb,
               'fanart': fanart})
    try:
        import re as _re
        clean = _re.sub(r'\[/?[A-Z]+[^\]]*\]', '', title)
        li.setInfo('video', {'title': clean, 'plot': plot})
    except Exception:
        pass
    return li


def add_play_item(entry_dict, title_label=None, extra_plot=''):
    """Render a playable item (one of feed.walk_tree's dicts or parser output)."""
    title = title_label or entry_dict.get('title', 'Unknown')
    thumb = entry_dict.get('thumbnail') or ADDON_ICON
    fanart = entry_dict.get('fanart') or ADDON_FANART
    plot = entry_dict.get('plot') or entry_dict.get('summary') or ''
    if extra_plot:
        plot = (extra_plot + '\n\n' + plot).strip()
    sublinks = list(entry_dict.get('sublinks') or [])
    # Fallback: some feeds (episodes) use a single <link> instead of <sublink>
    if not sublinks:
        single = entry_dict.get('link') or ''
        if single:
            sublinks = [single]
    if not sublinks:
        return False

    if not entry_dict.get('thumbnail') or not entry_dict.get('fanart'):
        cleaned = feed.clean_title(entry_dict.get('title', ''))
        poster, fart, overview = feed.tmdb_lookup(cleaned)
        if poster and not entry_dict.get('thumbnail'):
            thumb = poster
        if fart and not entry_dict.get('fanart'):
            fanart = fart
        if overview and not plot:
            plot = overview

    li = make_list_item(title, thumb, fanart, plot)
    li.setProperty('IsPlayable', 'true')
    url_q = build_url({
        'mode': 'play',
        'title': entry_dict.get('title', title),
        'sublinks': '|'.join(sublinks),
        'thumb': thumb,
        'fanart': fanart,
        'plot': plot,
    })
    # Context menu: Download
    try:
        dl_q = build_url({
            'mode': 'download',
            'title': entry_dict.get('title', title),
            'sublinks': '|'.join(sublinks),
            'thumb': thumb,
            'fanart': fanart,
        })
        li.addContextMenuItems(
            [('[COLOR orange]Download to device[/COLOR]',
              'RunPlugin(%s)' % dl_q)],
            replaceItems=False)
    except Exception:
        pass
    xbmcplugin.addDirectoryItem(HANDLE, url_q, li, isFolder=False)
    return True


# ---------------- root listing ---------------- #

def root():
    # 0) My Free Flow - very top
    if trakt.is_authenticated():
        mf_label = ('[COLORdarkorange][B]My Trakt[/B][/COLOR]  -  '
                    'Trakt menus, watchlist & custom lists')
    else:
        mf_label = ('[COLORdarkorange][B]My Trakt[/B][/COLOR]  -  '
                    'Connect Trakt to enable')
    li = make_list_item(
        mf_label, ADDON_ICON, ADDON_FANART,
        'Trakt-powered hub: Trending / Popular / Anticipated, '
        'Watchlist, Collection, History, Liked Lists and your own '
        'Custom Lists with full add / remove / create support.')
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'mode': 'myfreeflow'}),
                                li, isFolder=True)

    # 1) What's New
    new_items = feed.load_json(feed.new_path(), [])
    known = feed.load_json(feed.known_path(), {})
    last_scan = known.get('_last_scan')
    when = ''
    if last_scan:
        try:
            when = ' (last scan ' + time.strftime(
                '%H:%M', time.localtime(last_scan)) + ')'
        except Exception:
            when = ''
    wn_label = '[COLORdarkorange][B]What\'s New[/B][/COLOR] - %d new%s' % (
        len(new_items), when)
    li = make_list_item(wn_label, ADDON_ICON, ADDON_FANART,
                        'Items added since the background scanner started. '
                        'Auto-refreshes every 30 seconds.')
    xbmcplugin.addDirectoryItem(HANDLE,
                                build_url({'mode': 'whatsnew'}),
                                li, isFolder=True)

    # 2) Live root from MAIN DIR
    code, text, _ = feed.http_get(feed.ROOT_URL)
    entries = feed.parse_feed(text) if code == 200 else []
    for e in entries:
        if e['kind'] != 'dir':
            continue
        title = e.get('title') or 'Unknown'
        thumb = e.get('thumbnail') or ADDON_ICON
        fanart = e.get('fanart') or ADDON_FANART
        plot = e.get('summary') or ''
        link = e.get('link') or ''
        if not link:
            continue
        li = make_list_item(title, thumb, fanart, plot)
        xbmcplugin.addDirectoryItem(
            HANDLE, build_url({'mode': 'list', 'url': link}),
            li, isFolder=True)

    # 3) Search
    total_indexed = sum(1 for k in known if not k.startswith('_'))
    s_label = '[COLORghostwhite][B]Search[/B][/COLOR] - %d items indexed' % total_indexed
    li = make_list_item(s_label, ADDON_ICON, ADDON_FANART,
                        'Universal search across every feed indexed by the '
                        'background scanner.')
    xbmcplugin.addDirectoryItem(HANDLE,
                                build_url({'mode': 'search'}),
                                li, isFolder=True)

    # 4) Link Checker
    lc_label = '[COLORdarkorange][B]Link Checker[/B][/COLOR]'
    li = make_list_item(
        lc_label, ADDON_ICON, ADDON_FANART,
        'Scans every sublink in the indexed tree, detects dead/removed '
        'videos, and shows you exactly which section and host each broken '
        'link belongs to.')
    xbmcplugin.addDirectoryItem(HANDLE,
                                build_url({'mode': 'linkcheck'}),
                                li, isFolder=True)

    # 5) Downloads
    dl_items = ffdownloads.load_state()
    dl_label = ('[COLORdarkorange][B]Downloads[/B][/COLOR] - %d saved'
                % len(dl_items))
    li = make_list_item(
        dl_label, ADDON_ICON, ADDON_FANART,
        'Files you have saved to your device with the context-menu '
        '"Download to device" option. Play them offline or remove them.')
    xbmcplugin.addDirectoryItem(HANDLE,
                                build_url({'mode': 'downloads'}),
                                li, isFolder=True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------- list a remote feed ---------------- #

def listing(url):
    code, text, _ = feed.http_get(url)
    entries = feed.parse_feed(text) if code == 200 else []

    if not entries:
        xbmcgui.Dialog().notification(ADDON_NAME, 'No entries found',
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    for entry in entries:
        title = entry.get('title') or 'Unknown'
        thumb = entry.get('thumbnail') or ADDON_ICON
        fanart = entry.get('fanart') or ADDON_FANART
        plot = entry.get('summary') or ''

        if entry['kind'] == 'dir':
            link = entry.get('link') or ''
            if not link:
                continue
            li = make_list_item(title, thumb, fanart, plot)
            xbmcplugin.addDirectoryItem(
                HANDLE, build_url({'mode': 'list', 'url': link}),
                li, isFolder=True)
        else:
            d = {
                'title': title,
                'sublinks': entry.get('sublinks', []),
                'link': entry.get('link', ''),
                'thumbnail': entry.get('thumbnail', ''),
                'fanart': entry.get('fanart', ''),
                'plot': plot,
            }
            add_play_item(d)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------- What's New ---------------- #

def whats_new():
    items = feed.load_json(feed.new_path(), [])
    if not items:
        li = make_list_item(
            '[I]Nothing new yet. The scanner runs every 30 seconds.[/I]',
            ADDON_ICON, ADDON_FANART,
            'New items will appear here automatically as soon as they are '
            'added to any chains24 feed.')
        xbmcplugin.addDirectoryItem(HANDLE, build_url({'mode': 'root'}),
                                    li, isFolder=True)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items.sort(key=lambda x: x.get('first_seen', 0), reverse=True)
    now = time.time()
    for it in items:
        title = it.get('title', 'Unknown')
        parent = it.get('parent_title', 'Free Flow')
        age = max(0, int(now - it.get('first_seen', now)))
        if age < 60:
            ago = '%ds ago' % age
        elif age < 3600:
            ago = '%dm ago' % (age // 60)
        else:
            ago = '%dh ago' % (age // 3600)
        label = '[COLOR gold][NEW][/COLOR] %s  [COLOR grey]- in %s - %s[/COLOR]' % (
            title, parent, ago)
        extra = 'Found in: %s\nAdded: %s' % (parent, ago)
        add_play_item(it, title_label=label, extra_plot=extra)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------- Search ---------------- #

def search():
    kb = xbmcgui.Dialog().input('Search Free Flow', type=xbmcgui.INPUT_ALPHANUM)
    if not kb:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    q = kb.lower().strip()

    known = feed.load_json(feed.known_path(), {})
    matches = []
    for k, v in known.items():
        if k.startswith('_'):
            continue
        if q in (v.get('title', '') or '').lower():
            matches.append(v)

    if not matches:
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'No matches for "%s"' % kb,
            xbmcgui.NOTIFICATION_INFO, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    matches.sort(key=lambda x: x.get('title', '').lower())
    matches = matches[:300]
    for it in matches:
        title = it.get('title', 'Unknown')
        parent = it.get('parent_title', '')
        label = '%s  [COLOR grey]- %s[/COLOR]' % (title, parent)
        add_play_item(it, title_label=label,
                      extra_plot='Found in: ' + parent)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------- My Free Flow / Trakt ---------------- #

def _add_dir(label, params, plot=''):
    li = make_list_item(label, ADDON_ICON, ADDON_FANART, plot)
    xbmcplugin.addDirectoryItem(HANDLE, build_url(params), li, isFolder=True)


def myfreeflow():
    """Top-level My Free Flow menu."""
    if not trakt.is_authenticated():
        _add_dir('[COLORblue][B]Authorise Trakt[/B][/COLOR]',
                 {'mode': 'trakt_auth'},
                 'Sign in to Trakt to unlock Trending, Watchlist, '
                 'Collection, History and your custom lists.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    user = trakt.whoami() or 'Trakt'
    _add_dir('[COLOR darkorange]Signed in as[/COLOR] [B]%s[/B]'
             '   [COLOR grey](Sign out)[/COLOR]' % user,
             {'mode': 'trakt_signout'}, 'Tap to sign out of Trakt.')

    _add_dir('[B]Trending Movies[/B]',
             {'mode': 'trakt_cat', 'cat': 'trending', 'media': 'movies'})
    _add_dir('[B]Trending Shows[/B]',
             {'mode': 'trakt_cat', 'cat': 'trending', 'media': 'shows'})
    _add_dir('[B]Popular Movies[/B]',
             {'mode': 'trakt_cat', 'cat': 'popular', 'media': 'movies'})
    _add_dir('[B]Popular Shows[/B]',
             {'mode': 'trakt_cat', 'cat': 'popular', 'media': 'shows'})
    _add_dir('[B]Anticipated Movies[/B]',
             {'mode': 'trakt_cat', 'cat': 'anticipated', 'media': 'movies'})
    _add_dir('[B]Anticipated Shows[/B]',
             {'mode': 'trakt_cat', 'cat': 'anticipated', 'media': 'shows'})
    _add_dir('[B]Recommended Movies[/B]',
             {'mode': 'trakt_cat', 'cat': 'recommendations',
              'media': 'movies'})
    _add_dir('[B]Recommended Shows[/B]',
             {'mode': 'trakt_cat', 'cat': 'recommendations',
              'media': 'shows'})

    _add_dir('[COLOR gold][B]Watchlist - Movies[/B][/COLOR]',
             {'mode': 'trakt_cat', 'cat': 'watchlist', 'media': 'movies'})
    _add_dir('[COLOR gold][B]Watchlist - Shows[/B][/COLOR]',
             {'mode': 'trakt_cat', 'cat': 'watchlist', 'media': 'shows'})
    _add_dir('[COLOR gold][B]Collection - Movies[/B][/COLOR]',
             {'mode': 'trakt_cat', 'cat': 'collection', 'media': 'movies'})
    _add_dir('[COLOR gold][B]Collection - Shows[/B][/COLOR]',
             {'mode': 'trakt_cat', 'cat': 'collection', 'media': 'shows'})
    _add_dir('[COLOR gold][B]History - Movies[/B][/COLOR]',
             {'mode': 'trakt_cat', 'cat': 'history', 'media': 'movies'})
    _add_dir('[COLOR gold][B]History - Shows[/B][/COLOR]',
             {'mode': 'trakt_cat', 'cat': 'history', 'media': 'shows'})

    _add_dir('[COLOR deepskyblue][B]My Lists[/B][/COLOR]',
             {'mode': 'trakt_mylists'},
             'Your personal Trakt lists. Use the context menu to '
             'create, rename or delete a list.')
    _add_dir('[COLOR deepskyblue][B]Liked Lists[/B][/COLOR]',
             {'mode': 'trakt_likedlists'},
             'Lists you have liked on Trakt.')

    _add_dir('[COLOR cyan][B]Search Trakt[/B][/COLOR]',
             {'mode': 'trakt_search'},
             'Search Trakt and add items directly to your lists.')

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_auth_flow():
    ok = trakt.device_authorize(abort_cb=lambda: xbmc.Monitor().abortRequested())
    if ok:
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'Trakt connected',
            xbmcgui.NOTIFICATION_INFO, 4000)
    else:
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'Trakt sign-in cancelled or failed',
            xbmcgui.NOTIFICATION_WARNING, 5000)
    xbmc.executebuiltin('Container.Refresh')


def trakt_signout():
    if xbmcgui.Dialog().yesno(ADDON_NAME, 'Sign out of Trakt?'):
        trakt.sign_out()
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'Signed out',
            xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin('Container.Refresh')


def _find_local_match(title, year=None):
    """Search the indexed tree for a title -> return item dict or None."""
    if not title:
        return None
    known = feed.load_json(feed.known_path(), {})
    q = feed.clean_title(title).lower()
    if not q:
        q = title.lower()
    best = None
    for k, v in known.items():
        if k.startswith('_'):
            continue
        t = (v.get('title', '') or '').lower()
        if not t:
            continue
        if q in t or t in q:
            # prefer year-matching titles when available
            if year and str(year) in (v.get('title', '') or ''):
                return v
            best = best or v
    return best


def _trakt_play_item(media, title, year, trakt_id, tmdb_id, overview):
    """Render a Trakt media object as a list item with full context menu."""
    # TMDB artwork lookup (cleaned title) for richer posters
    poster, fanart, _ov = feed.tmdb_lookup(title) if title else (None, None, '')
    thumb = poster or ADDON_ICON
    art_fanart = fanart or ADDON_FANART
    plot = overview or ''
    label = title + (' (%d)' % year if year else '')

    # If we have a local match, link goes to play; otherwise show "no source"
    match = _find_local_match(title, year)
    li = make_list_item(label, thumb, art_fanart, plot)
    if match:
        sublinks = match.get('sublinks') or []
        url_q = build_url({
            'mode': 'play',
            'title': title,
            'sublinks': '|'.join(sublinks),
            'thumb': thumb,
            'fanart': art_fanart,
            'plot': plot,
        })
        li.setProperty('IsPlayable', 'true')
        is_folder = False
    else:
        # Tapping searches Free Flow for the title
        url_q = build_url({'mode': 'trakt_searchlocal', 'title': title})
        is_folder = True

    # Context menu
    cm = []
    if trakt_id:
        cm.append(('Add to Watchlist',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'wl_add', 'media': media,
                       'trakt_id': trakt_id, 'title': title})))
        cm.append(('Remove from Watchlist',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'wl_rem', 'media': media,
                       'trakt_id': trakt_id, 'title': title})))
        cm.append(('Add to Collection',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'col_add', 'media': media,
                       'trakt_id': trakt_id, 'title': title})))
        cm.append(('Remove from Collection',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'col_rem', 'media': media,
                       'trakt_id': trakt_id, 'title': title})))
        cm.append(('Mark as Watched',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'hist_add', 'media': media,
                       'trakt_id': trakt_id, 'title': title})))
        cm.append(('Add to Custom List...',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'list_add_pick', 'media': media,
                       'trakt_id': trakt_id, 'title': title})))
        cm.append(('Create New List...',
                   'RunPlugin(%s)' % build_url({
                       'mode': 'trakt_action',
                       'action': 'list_create'})))
    if cm:
        try:
            li.addContextMenuItems(cm, replaceItems=False)
        except Exception:
            pass

    xbmcplugin.addDirectoryItem(HANDLE, url_q, li, isFolder=is_folder)


def trakt_category(cat, media):
    """media: 'movies' or 'shows'."""
    if cat == 'trending':
        sc, data = trakt.trending(media)
    elif cat == 'popular':
        sc, data = trakt.popular(media)
    elif cat == 'anticipated':
        sc, data = trakt.anticipated(media)
    elif cat == 'recommendations':
        sc, data = trakt.recommendations(media)
    elif cat == 'watchlist':
        sc, data = trakt.watchlist(media)
    elif cat == 'collection':
        sc, data = trakt.collection(media)
    elif cat == 'history':
        sc, data = trakt.history(media)
    else:
        sc, data = 0, []

    if sc != 200 or not isinstance(data, list):
        xbmcgui.Dialog().notification(ADDON_NAME, 'Trakt error %s' % sc,
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    items = trakt.normalize(data)
    media_singular = 'movie' if media == 'movies' else 'show'
    for it in items:
        # Some categories (popular) return flat objects without media key
        m = it['media'] or media_singular
        _trakt_play_item(m, it['title'], it.get('year'),
                         it.get('trakt_id'), it.get('tmdb_id'),
                         it.get('overview', ''))

    xbmcplugin.setContent(HANDLE,
                          'movies' if media == 'movies' else 'tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_searchlocal(title):
    """Find a Trakt title within the indexed Free Flow library."""
    known = feed.load_json(feed.known_path(), {})
    q = feed.clean_title(title).lower() or title.lower()
    matches = []
    for k, v in known.items():
        if k.startswith('_'):
            continue
        t = (v.get('title', '') or '').lower()
        if not t:
            continue
        if q in t or t in q or any(w in t for w in q.split() if len(w) > 3):
            matches.append(v)

    if not matches:
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'No Free Flow source for "%s"' % title,
            xbmcgui.NOTIFICATION_INFO, 5000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    matches.sort(key=lambda x: x.get('title', '').lower())
    for it in matches[:200]:
        parent = it.get('parent_title', '')
        label = '%s  [COLOR grey]- %s[/COLOR]' % (
            it.get('title', 'Unknown'), parent)
        add_play_item(it, title_label=label,
                      extra_plot='Found in: ' + parent)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_search():
    kb = xbmcgui.Dialog().input('Search Trakt', type=xbmcgui.INPUT_ALPHANUM)
    if not kb:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    sc, data = trakt.search(kb)
    if sc != 200 or not isinstance(data, list):
        xbmcgui.Dialog().notification(ADDON_NAME, 'Trakt search error',
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    items = trakt.normalize(data)
    for it in items:
        _trakt_play_item(it['media'], it['title'], it.get('year'),
                         it.get('trakt_id'), it.get('tmdb_id'),
                         it.get('overview', ''))
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_mylists():
    sc, data = trakt.my_lists()
    if sc != 200 or not isinstance(data, list):
        xbmcgui.Dialog().notification(ADDON_NAME,
                                      'Could not load lists (%s)' % sc,
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Always show "Create new list" entry
    li = make_list_item(
        '[COLOR lime][B]+ Create New List[/B][/COLOR]',
        ADDON_ICON, ADDON_FANART,
        'Prompt for a name and create a new private list on Trakt.')
    cm = [('Create New List...',
           'RunPlugin(%s)' % build_url({'mode': 'trakt_action',
                                        'action': 'list_create'}))]
    li.addContextMenuItems(cm, replaceItems=False)
    xbmcplugin.addDirectoryItem(HANDLE,
                                build_url({'mode': 'trakt_action',
                                           'action': 'list_create'}),
                                li, isFolder=False)

    for lst in data:
        if not isinstance(lst, dict):
            continue
        name = lst.get('name', 'Untitled')
        ids = lst.get('ids', {}) or {}
        list_id = ids.get('trakt') or ids.get('slug')
        owner = (lst.get('user', {}) or {}).get('ids', {}).get('slug', 'me')
        count = lst.get('item_count', 0)
        label = '%s  [COLOR grey](%d items)[/COLOR]' % (name, count)
        li = make_list_item(label, ADDON_ICON, ADDON_FANART,
                            lst.get('description', '') or '')
        cm = [
            ('Delete List',
             'RunPlugin(%s)' % build_url({
                 'mode': 'trakt_action', 'action': 'list_delete',
                 'list_id': list_id, 'name': name})),
            ('Create New List...',
             'RunPlugin(%s)' % build_url({
                 'mode': 'trakt_action', 'action': 'list_create'})),
        ]
        li.addContextMenuItems(cm, replaceItems=False)
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'mode': 'trakt_listitems',
                       'user': owner, 'list_id': list_id}),
            li, isFolder=True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_likedlists():
    sc, data = trakt.liked_lists()
    if sc != 200 or not isinstance(data, list):
        xbmcgui.Dialog().notification(ADDON_NAME, 'Trakt error %s' % sc,
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    for entry in data:
        lst = entry.get('list', {}) if isinstance(entry, dict) else {}
        name = lst.get('name', 'Untitled')
        ids = lst.get('ids', {}) or {}
        list_id = ids.get('trakt') or ids.get('slug')
        owner = (lst.get('user', {}) or {}).get('ids', {}).get('slug', '')
        count = lst.get('item_count', 0)
        label = '%s  [COLOR grey]by %s (%d items)[/COLOR]' % (
            name, owner, count)
        li = make_list_item(label, ADDON_ICON, ADDON_FANART,
                            lst.get('description', '') or '')
        if owner and list_id:
            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'mode': 'trakt_listitems',
                           'user': owner, 'list_id': list_id}),
                li, isFolder=True)
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_listitems(user, list_id):
    sc, data = trakt.list_items(user, list_id)
    if sc != 200 or not isinstance(data, list):
        xbmcgui.Dialog().notification(ADDON_NAME, 'List error %s' % sc,
                                      xbmcgui.NOTIFICATION_WARNING, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    items = trakt.normalize(data)
    for it in items:
        # Add a "Remove from this list" context menu item too
        media = it['media']
        label = it['title'] + (' (%d)' % it['year'] if it.get('year') else '')
        poster, fanart, _ov = feed.tmdb_lookup(it['title']) \
            if it['title'] else (None, None, '')
        li = make_list_item(label, poster or ADDON_ICON,
                            fanart or ADDON_FANART, it.get('overview', ''))
        match = _find_local_match(it['title'], it.get('year'))
        if match:
            sublinks = match.get('sublinks') or []
            url_q = build_url({
                'mode': 'play', 'title': it['title'],
                'sublinks': '|'.join(sublinks),
                'thumb': poster or ADDON_ICON,
                'fanart': fanart or ADDON_FANART,
                'plot': it.get('overview', ''),
            })
            li.setProperty('IsPlayable', 'true')
            is_folder = False
        else:
            url_q = build_url({'mode': 'trakt_searchlocal',
                               'title': it['title']})
            is_folder = True
        cm = [
            ('Remove from this List',
             'RunPlugin(%s)' % build_url({
                 'mode': 'trakt_action', 'action': 'list_remove_item',
                 'list_id': list_id, 'media': media,
                 'trakt_id': it.get('trakt_id'), 'title': it['title']})),
            ('Add to Watchlist',
             'RunPlugin(%s)' % build_url({
                 'mode': 'trakt_action', 'action': 'wl_add',
                 'media': media, 'trakt_id': it.get('trakt_id'),
                 'title': it['title']})),
            ('Add to Collection',
             'RunPlugin(%s)' % build_url({
                 'mode': 'trakt_action', 'action': 'col_add',
                 'media': media, 'trakt_id': it.get('trakt_id'),
                 'title': it['title']})),
            ('Add to Another List...',
             'RunPlugin(%s)' % build_url({
                 'mode': 'trakt_action', 'action': 'list_add_pick',
                 'media': media, 'trakt_id': it.get('trakt_id'),
                 'title': it['title']})),
        ]
        li.addContextMenuItems(cm, replaceItems=False)
        xbmcplugin.addDirectoryItem(HANDLE, url_q, li, isFolder=is_folder)
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_action(params):
    """Handle add/remove/create context-menu actions."""
    action = params.get('action', '')
    media = params.get('media', 'movie')
    trakt_id = params.get('trakt_id')
    title = params.get('title', '')

    def _toast(msg, ok=True):
        xbmcgui.Dialog().notification(
            ADDON_NAME, msg,
            xbmcgui.NOTIFICATION_INFO if ok
            else xbmcgui.NOTIFICATION_WARNING, 3500)

    try:
        if action == 'wl_add':
            sc, _ = trakt.add_to_watchlist(media, trakt_id)
            _toast('Added to Watchlist: %s' % title, sc in (200, 201))
        elif action == 'wl_rem':
            sc, _ = trakt.remove_from_watchlist(media, trakt_id)
            _toast('Removed from Watchlist: %s' % title, sc in (200, 201))
        elif action == 'col_add':
            sc, _ = trakt.add_to_collection(media, trakt_id)
            _toast('Added to Collection: %s' % title, sc in (200, 201))
        elif action == 'col_rem':
            sc, _ = trakt.remove_from_collection(media, trakt_id)
            _toast('Removed from Collection: %s' % title, sc in (200, 201))
        elif action == 'hist_add':
            sc, _ = trakt.add_to_history(media, trakt_id)
            _toast('Marked watched: %s' % title, sc in (200, 201))
        elif action == 'list_create':
            name = xbmcgui.Dialog().input('New list name',
                                          type=xbmcgui.INPUT_ALPHANUM)
            if not name:
                return
            desc = xbmcgui.Dialog().input(
                'Description (optional)', type=xbmcgui.INPUT_ALPHANUM)
            sc, _ = trakt.create_list(name, desc or '')
            _toast('Created list: %s' % name, sc in (200, 201))
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'list_delete':
            list_id = params.get('list_id')
            name = params.get('name', '')
            if xbmcgui.Dialog().yesno(ADDON_NAME,
                                      'Delete list "%s"?' % name):
                sc, _ = trakt.delete_list(list_id)
                _toast('Deleted: %s' % name, sc in (200, 201, 204))
                xbmc.executebuiltin('Container.Refresh')
        elif action == 'list_add_pick':
            sc, lists = trakt.my_lists()
            if sc != 200 or not isinstance(lists, list) or not lists:
                # offer to create on the fly
                if xbmcgui.Dialog().yesno(
                        ADDON_NAME,
                        'You have no lists. Create one now?'):
                    name = xbmcgui.Dialog().input(
                        'New list name', type=xbmcgui.INPUT_ALPHANUM)
                    if not name:
                        return
                    sc2, created = trakt.create_list(name)
                    if sc2 in (200, 201) and isinstance(created, dict):
                        new_id = (created.get('ids', {}) or {}).get('trakt')
                        if new_id:
                            sc3, _ = trakt.add_to_list(new_id, media,
                                                      trakt_id)
                            _toast('Added "%s" to %s' % (title, name),
                                   sc3 in (200, 201))
                return
            labels = ['+ Create New List...']
            for lst in lists:
                labels.append('%s  (%d items)' % (
                    lst.get('name', 'Untitled'),
                    lst.get('item_count', 0)))
            idx = xbmcgui.Dialog().select('Add "%s" to list' % title, labels)
            if idx < 0:
                return
            if idx == 0:
                name = xbmcgui.Dialog().input(
                    'New list name', type=xbmcgui.INPUT_ALPHANUM)
                if not name:
                    return
                sc2, created = trakt.create_list(name)
                if sc2 in (200, 201) and isinstance(created, dict):
                    new_id = (created.get('ids', {}) or {}).get('trakt')
                    if new_id:
                        sc3, _ = trakt.add_to_list(new_id, media, trakt_id)
                        _toast('Added "%s" to %s' % (title, name),
                               sc3 in (200, 201))
            else:
                target = lists[idx - 1]
                tid = (target.get('ids', {}) or {}).get('trakt')
                if tid:
                    sc3, _ = trakt.add_to_list(tid, media, trakt_id)
                    _toast('Added "%s" to %s' % (
                        title, target.get('name', '')),
                        sc3 in (200, 201))
        elif action == 'list_remove_item':
            list_id = params.get('list_id')
            sc, _ = trakt.remove_from_list(list_id, media, trakt_id)
            _toast('Removed: %s' % title, sc in (200, 201))
            xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        log('trakt_action error: %s' % e, xbmc.LOGERROR)
        _toast('Action failed', False)


# ---------------- Link Checker ---------------- #

def link_check():
    known = feed.load_json(feed.known_path(), {})
    pairs = []
    for k, v in known.items():
        if k.startswith('_'):
            continue
        for sl in v.get('sublinks', []) or []:
            if sl:
                pairs.append((v, sl))

    if not pairs:
        progress_live = xbmcgui.DialogProgressBG()
        progress_live.create('Free Flow', 'Building link list (first run)...')
        try:
            items = feed.walk_tree()
        finally:
            progress_live.close()
        for it in items:
            for sl in it.get('sublinks', []) or []:
                if sl:
                    pairs.append((it, sl))

    if not pairs:
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'No links indexed yet - try again in a moment',
            xbmcgui.NOTIFICATION_INFO, 5000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    total = len(pairs)
    monitor = xbmc.Monitor()
    pdialog = xbmcgui.DialogProgressBG()
    pdialog.create('Free Flow Link Check',
                   'Checking %d links...' % total)

    results = []
    completed = 0

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(feed.check_link, sl): (it, sl)
                       for it, sl in pairs}
            for fut in as_completed(futures):
                if monitor.abortRequested():
                    break
                it, sl = futures[fut]
                try:
                    alive, reason = fut.result()
                except Exception as e:
                    alive, reason = False, str(e)[:80]
                results.append({
                    'title': it.get('title', ''),
                    'parent_title': it.get('parent_title', ''),
                    'parent_url': it.get('parent_url', ''),
                    'thumbnail': it.get('thumbnail', ''),
                    'fanart': it.get('fanart', ''),
                    'plot': it.get('plot', ''),
                    'sublinks': it.get('sublinks', []),
                    'url': sl,
                    'host': feed.host_of(sl),
                    'alive': alive,
                    'reason': reason,
                })
                completed += 1
                pct = int(completed * 100 / total)
                try:
                    pdialog.update(pct, 'Free Flow Link Check',
                                   '%d / %d - %s' % (completed, total,
                                                     feed.host_of(sl)))
                except Exception:
                    pass
    finally:
        try:
            pdialog.close()
        except Exception:
            pass

    feed.write_text_report(results)

    dead = [r for r in results if not r['alive']]
    alive_count = len(results) - len(dead)

    xbmcgui.Dialog().notification(
        ADDON_NAME,
        'Checked %d  -  %d dead  /  %d alive' % (len(results), len(dead),
                                                  alive_count),
        xbmcgui.NOTIFICATION_INFO, 6000)

    summary_label = ('[COLOR red][B]%d DEAD[/B][/COLOR]  '
                     '[COLOR lime]%d alive[/COLOR]  -  Report: %s'
                     % (len(dead), alive_count, feed.report_path()))
    summary_plot = ('Full report saved to:\n%s\n\nUse the View Report entry '
                    'below to read the full text on-screen.'
                    % feed.report_path())
    li = make_list_item(summary_label, ADDON_ICON, ADDON_FANART, summary_plot)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'mode': 'linkreport'}),
                                li, isFolder=True)

    if not dead:
        li = make_list_item('[COLOR lime]All links are alive[/COLOR]',
                            ADDON_ICON, ADDON_FANART,
                            'No dead links detected on this scan.')
        xbmcplugin.addDirectoryItem(HANDLE, build_url({'mode': 'root'}),
                                    li, isFolder=True)
    else:
        host_counts = {}
        for r in dead:
            host_counts[r['host']] = host_counts.get(r['host'], 0) + 1
        for host, n in sorted(host_counts.items(), key=lambda x: -x[1]):
            label = ('[COLOR orange]Host:[/COLOR] %s  -  '
                     '[COLOR red]%d dead[/COLOR]' % (host, n))
            li = make_list_item(label, ADDON_ICON, ADDON_FANART,
                                'Dead links on host: ' + host)
            li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(
                HANDLE, build_url({'mode': 'noop'}), li, isFolder=False)

        dead_sorted = sorted(dead, key=lambda r: (r['parent_title'] or '',
                                                  r['title'] or ''))
        for r in dead_sorted:
            label = ('[COLOR red][DEAD][/COLOR] %s  '
                     '[COLOR grey]- %s - in %s[/COLOR]'
                     % (r['title'], r['host'], r['parent_title']))
            extra = ('Section: %s\nHost: %s\nReason: %s\nLink: %s'
                     % (r['parent_title'], r['host'], r['reason'], r['url']))
            d = {
                'title': r['title'],
                'sublinks': r['sublinks'],
                'thumbnail': r['thumbnail'],
                'fanart': r['fanart'],
                'plot': r['plot'],
            }
            add_play_item(d, title_label=label, extra_plot=extra)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def show_last_report():
    import os as _os
    path = feed.report_path()
    if not _os.path.exists(path):
        xbmcgui.Dialog().notification(
            ADDON_NAME, 'No report yet - run Link Checker first',
            xbmcgui.NOTIFICATION_INFO, 4000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        text = 'Error reading report: %s' % e
    xbmcgui.Dialog().textviewer('Free Flow - Link Report', text)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


# ---------------- play ---------------- #

def play(params):
    title = params.get('title', 'Free Flow')
    thumb = params.get('thumb', ADDON_ICON)
    fanart = params.get('fanart', ADDON_FANART)
    plot = params.get('plot', '')
    sublinks = [s for s in params.get('sublinks', '').split('|') if s]

    if not sublinks:
        xbmcgui.Dialog().notification(ADDON_NAME, 'No sources',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        return

    if len(sublinks) == 1:
        chosen = sublinks[0]
    else:
        labels = [urlparse.urlparse(s).netloc or s for s in sublinks]
        idx = xbmcgui.Dialog().select('Choose source', labels)
        if idx < 0:
            return
        chosen = sublinks[idx]

    resolved = chosen
    resolver_log = lambda m: log('resolvers: %s' % m, xbmc.LOGINFO)  # noqa: E731
    # 1) Built-in Free Flow resolvers (ddownload.com etc)
    try:
        if ffresolvers.can_resolve(chosen):
            r = ffresolvers.resolve(chosen, log=resolver_log)
            if r:
                resolved = r
    except Exception as e:
        log('ffresolvers error: %s' % e, xbmc.LOGERROR)

    # 2) Fallback to script.module.resolveurl
    if resolved == chosen and resolveurl is not None:
        try:
            hmf = resolveurl.HostedMediaFile(
                url=chosen, title=title,
                include_disabled=False, include_universal=True)
            if hmf.valid_url():
                r = hmf.resolve()
                if r:
                    resolved = r
            else:
                r = resolveurl.resolve(chosen)
                if r:
                    resolved = r
        except Exception as e:
            log('resolveurl error: %s' % e, xbmc.LOGERROR)

    if not resolved:
        _maybe_warn_ddownload(chosen)
        xbmcgui.Dialog().notification(ADDON_NAME, 'Could not resolve link',
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        return

    li = xbmcgui.ListItem(label=title, path=resolved)
    li.setArt({'thumb': thumb, 'poster': thumb, 'fanart': fanart})
    try:
        li.setInfo('video', {'title': title, 'plot': plot})
    except Exception:
        pass
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def _maybe_warn_ddownload(url):
    """If the failing URL is a ddownload free link, explain why and how
    to fix it (premium API key)."""
    try:
        if not ffresolvers.can_resolve(url):
            return
        has_key = bool((ADDON.getSetting('ddl_api_key') or '').strip())
        if has_key:
            msg = ('ddownload premium API did not return a link. '
                   'Check your API key is valid and the file still exists.')
        else:
            msg = ('ddownload.com now uses a Cloudflare Turnstile captcha '
                   'on free downloads which cannot be solved from Kodi. '
                   'Add a premium API key in Free Flow settings > Downloads '
                   'to resolve these links automatically.')
        xbmcgui.Dialog().ok(ADDON_NAME, msg)
    except Exception:
        pass


# ---------------- Downloads ---------------- #

def downloads_list():
    items = ffdownloads.load_state()
    if not items:
        li = make_list_item(
            '[I]No downloads yet. Use context menu -> '
            'Download to device on any item.[/I]',
            ADDON_ICON, ADDON_FANART,
            'Download folder: ' + ffdownloads.get_download_folder())
        xbmcplugin.addDirectoryItem(HANDLE, build_url({'mode': 'root'}),
                                    li, isFolder=True)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items.sort(key=lambda x: x.get('added', 0), reverse=True)
    for it in items:
        title = it.get('title') or it.get('filename') or 'Download'
        fp = it.get('filepath', '')
        exists = os.path.exists(fp) if fp else False
        size_mb = (it.get('bytes') or it.get('total_bytes') or 0) / 1048576.0
        when = ''
        try:
            when = time.strftime('%Y-%m-%d %H:%M',
                                 time.localtime(it.get('added', 0)))
        except Exception:
            pass
        status = ('[COLOR lime]ON DEVICE[/COLOR]' if exists
                  else '[COLOR red]MISSING[/COLOR]')
        label = '%s  [COLOR grey]- %.1f MB - %s - %s[/COLOR]' % (
            title, size_mb, when, status)
        plot = ('File: %s\nSource: %s\nSize: %.1f MB\nDownloaded: %s'
                % (fp, it.get('source_url', ''), size_mb, when))
        thumb = it.get('thumb') or ADDON_ICON
        fanart = it.get('fanart') or ADDON_FANART
        li = make_list_item(label, thumb, fanart, plot)
        li.setProperty('IsPlayable', 'true')
        play_path = fp if exists else build_url({
            'mode': 'download_missing', 'filepath': fp})
        cm = [
            ('[COLOR red]Delete[/COLOR] (file + entry)',
             'RunPlugin(%s)' % build_url({
                 'mode': 'download_delete', 'filepath': fp, 'keep': '0'})),
            ('Remove from list (keep file)',
             'RunPlugin(%s)' % build_url({
                 'mode': 'download_delete', 'filepath': fp, 'keep': '1'})),
            ('Re-download',
             'RunPlugin(%s)' % build_url({
                 'mode': 'download',
                 'title': title,
                 'sublinks': it.get('source_url', ''),
                 'thumb': thumb, 'fanart': fanart})),
        ]
        li.addContextMenuItems(cm, replaceItems=False)
        xbmcplugin.addDirectoryItem(
            HANDLE, play_path, li, isFolder=False)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.endOfDirectory(HANDLE)


def download_action(params):
    """Pick source (if multi) then kick off a download."""
    title = params.get('title') or 'Free Flow download'
    thumb = params.get('thumb', '')
    fanart = params.get('fanart', '')
    sublinks = [s for s in (params.get('sublinks', '') or '').split('|')
                if s]
    if not sublinks:
        xbmcgui.Dialog().notification(ADDON_NAME, 'No source to download',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        return

    if len(sublinks) == 1:
        chosen = sublinks[0]
    else:
        labels = [urlparse.urlparse(s).netloc or s for s in sublinks]
        idx = xbmcgui.Dialog().select('Download - choose source', labels)
        if idx < 0:
            return
        chosen = sublinks[idx]

    def _dlog(msg):
        log('download: %s' % msg, xbmc.LOGINFO)

    ffdownloads.download(chosen, title, thumb=thumb, fanart=fanart,
                         log=_dlog)
    xbmc.executebuiltin('Container.Refresh')


def download_delete(params):
    fp = params.get('filepath', '')
    keep = params.get('keep', '0') == '1'
    if not fp:
        return
    if not xbmcgui.Dialog().yesno(
            ADDON_NAME,
            ('Remove entry from list?\n(file will be kept)' if keep
             else 'Delete this file from your device?'),
            os.path.basename(fp)):
        return
    ffdownloads.remove_entry(fp, delete_file=not keep)
    xbmcgui.Dialog().notification(
        ADDON_NAME, 'Removed' if keep else 'Deleted',
        xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin('Container.Refresh')


def download_missing(filepath):
    xbmcgui.Dialog().ok(
        ADDON_NAME,
        'File not found on device:\n' + (filepath or ''),
        'Use the context menu to remove it or re-download.')


# ---------------- router ---------------- #

def router(paramstring):
    params = dict(urlparse.parse_qsl(paramstring.lstrip('?')))
    mode = params.get('mode')
    dbg.session_banner(reason='router mode=%s' % (mode or 'root'))
    dbg.dlog('router params=%s' % params, level='DEBUG', component='router')
    try:
        _route(mode, params)
    except Exception:
        dbg.dump_exception('router', context='mode=%s' % mode)
        try:
            xbmcgui.Dialog().notification(
                ADDON_NAME, 'Error - see Debug Log',
                xbmcgui.NOTIFICATION_ERROR, 4000)
        except Exception:
            pass
        try:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        except Exception:
            pass


def _route(mode, params):
    if not mode:
        show_splash()
    if mode == 'list':
        listing(params.get('url', feed.ROOT_URL))
    elif mode == 'play':
        play(params)
    elif mode == 'whatsnew':
        whats_new()
    elif mode == 'search':
        search()
    elif mode == 'linkcheck':
        link_check()
    elif mode == 'linkreport':
        show_last_report()
    elif mode == 'myfreeflow':
        myfreeflow()
    elif mode == 'trakt_auth':
        trakt_auth_flow()
    elif mode == 'trakt_signout':
        trakt_signout()
    elif mode == 'trakt_cat':
        trakt_category(params.get('cat', ''), params.get('media', 'movies'))
    elif mode == 'trakt_search':
        trakt_search()
    elif mode == 'trakt_searchlocal':
        trakt_searchlocal(params.get('title', ''))
    elif mode == 'trakt_mylists':
        trakt_mylists()
    elif mode == 'trakt_likedlists':
        trakt_likedlists()
    elif mode == 'trakt_listitems':
        trakt_listitems(params.get('user', ''), params.get('list_id', ''))
    elif mode == 'trakt_action':
        trakt_action(params)
    elif mode == 'view_debuglog':
        view_debug_log()
    elif mode == 'clear_debuglog':
        clear_debug_log()
    elif mode == 'downloads':
        downloads_list()
    elif mode == 'download':
        download_action(params)
    elif mode == 'download_delete':
        download_delete(params)
    elif mode == 'download_missing':
        download_missing(params.get('filepath', ''))
    elif mode == 'noop':
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
    else:
        root()


def view_debug_log():
    path = dbg.log_path()
    if not os.path.exists(path):
        xbmcgui.Dialog().notification(ADDON_NAME, 'No debug log yet',
                                      xbmcgui.NOTIFICATION_INFO, 3000)
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        if len(text) > 60000:
            text = '... (truncated - showing last 60 KB) ...\n' + text[-60000:]
    except Exception as e:
        text = 'Error reading debug log: %s' % e
    xbmcgui.Dialog().textviewer('Free Flow - Debug Log', text)


def clear_debug_log():
    path = dbg.log_path()
    try:
        if os.path.exists(path):
            os.remove(path)
        backup = path + '.1'
        if os.path.exists(backup):
            os.remove(backup)
        xbmcgui.Dialog().notification(ADDON_NAME, 'Debug log cleared',
                                      xbmcgui.NOTIFICATION_INFO, 3000)
    except Exception as e:
        dbg.dlog('clear_debug_log error: %s' % e, level='ERROR',
                 component='log')


if __name__ == '__main__':
    router(sys.argv[2] if len(sys.argv) > 2 else '')
