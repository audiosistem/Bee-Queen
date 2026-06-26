# -*- coding: utf-8 -*-
"""My Lists — aggregates private lists from enabled tracking services
(Trakt, SIMKL, Bingebase).

Only reachable when at least one tracking integration is enabled in settings.
"""
import xbmcgui
import xbmcplugin

from .common import (HANDLE, ICON, FANART, add_dir, end_directory,
                     get_setting_bool, notify, log)
from . import tmdb as T
from . import listing as L
from . import trakt as TR
from . import simkl as SK
from . import bingebase as BB


# ---------------- gate ----------------

def any_tracking_enabled():
    """True if ANY tracker is enabled in settings (authenticated or not)."""
    return (get_setting_bool('trakt_enabled')
            or get_setting_bool('simkl_enabled')
            or get_setting_bool('bingebase_enabled'))


# ---------------- root ----------------

def my_lists_root():
    art = {'icon': ICON, 'fanart': FANART}

    if get_setting_bool('trakt_enabled'):
        if TR.is_authenticated():
            add_dir('[B]Trakt[/B] — My Lists', {'action': 'trakt_mylists'}, art=art,
                    plot='Your Trakt watchlist, collection, favorites, personal lists and recommendations.')
        else:
            add_dir('[COLOR FFFFA726]Trakt — not authenticated (tap to sign in)[/COLOR]',
                    {'action': 'trakt_auth'}, art=art,
                    plot='Authenticate with Trakt to show your Trakt lists here.')

    if get_setting_bool('simkl_enabled'):
        if SK.is_authenticated():
            add_dir('[B]SIMKL[/B] — My Lists', {'action': 'simkl_mylists'}, art=art,
                    plot='Your SIMKL Plan-to-Watch / Completed / On-Hold / Dropped lists.')
        else:
            add_dir('[COLOR FFFFA726]SIMKL — not authenticated (tap to sign in)[/COLOR]',
                    {'action': 'simkl_auth'}, art=art,
                    plot='Authenticate with SIMKL to show your SIMKL lists here.')

    if get_setting_bool('bingebase_enabled'):
        if BB.is_authenticated():
            add_dir('[B]Bingebase[/B] — My Watched',
                    {'action': 'bingebase_mylists'}, art=art,
                    plot='Movies and episodes you have marked watched on '
                         'Bingebase. Bingebase only exposes watched-history '
                         '— no public watchlist / favourites API.')
        else:
            add_dir('[COLOR FFFFA726]Bingebase — not authenticated (tap to sign in)[/COLOR]',
                    {'action': 'bingebase_auth'}, art=art,
                    plot='Authenticate with Bingebase to show your synced '
                         'watched history here.')

    end_directory(content='')


# ---------------- ID resolution ----------------

def _resolve_to_tmdb(obj, media):
    """Given a Trakt/SIMKL {ids:{tmdb,imdb,...}} object, return a full TMDB
    details dict (so L.list_movies / L.list_tv can render it with play links)."""
    if not obj:
        return None
    ids = obj.get('ids') or {}
    tmdb_id = ids.get('tmdb')
    imdb_id = ids.get('imdb')
    try:
        if tmdb_id:
            return T.movie_details(tmdb_id) if media == 'movie' else T.tv_details(tmdb_id)
        if imdb_id:
            f = T._get('/find/%s' % imdb_id, {'external_source': 'imdb_id'}, ttl=86400) or {}
            arr = f.get('movie_results' if media == 'movie' else 'tv_results') or []
            if arr:
                first = arr[0].get('id')
                if first:
                    return T.movie_details(first) if media == 'movie' else T.tv_details(first)
    except Exception as e:
        log('mylists resolve error: %s' % e)
    return None


def _render(results, media, next_action=None, next_params=None, page=1):
    wrapper = {'results': results}
    if next_action:
        wrapper['page'] = page
        wrapper['total_pages'] = page + 1
    if media == 'movie':
        L.list_movies(wrapper, next_action=next_action, next_params=next_params)
    else:
        L.list_tv(wrapper, next_action=next_action, next_params=next_params)


# ---------------- Trakt ----------------

def trakt_mylists():
    if not TR.is_authenticated():
        notify('Trakt: not authenticated')
        end_directory(''); return
    art = {'icon': ICON, 'fanart': FANART}
    add_dir('[B]Recommended for You — Movies[/B]',
            {'action': 'trakt_list', 'kind': 'recommendations', 'media': 'movie', 'page': '1'}, art=art,
            plot='Personalised movie recommendations from Trakt based on your watch history and ratings.')
    add_dir('[B]Recommended for You — Shows[/B]',
            {'action': 'trakt_list', 'kind': 'recommendations', 'media': 'tv', 'page': '1'}, art=art,
            plot='Personalised TV show recommendations from Trakt based on your watch history and ratings.')
    add_dir('Watchlist — Movies', {'action': 'trakt_list', 'kind': 'watchlist', 'media': 'movie', 'page': '1'}, art=art)
    add_dir('Watchlist — Shows',  {'action': 'trakt_list', 'kind': 'watchlist', 'media': 'tv', 'page': '1'}, art=art)
    add_dir('Collection — Movies', {'action': 'trakt_list', 'kind': 'collection', 'media': 'movie', 'page': '1'}, art=art)
    add_dir('Collection — Shows',  {'action': 'trakt_list', 'kind': 'collection', 'media': 'tv', 'page': '1'}, art=art)
    add_dir('Favorites — Movies', {'action': 'trakt_list', 'kind': 'favorites', 'media': 'movie', 'page': '1'}, art=art)
    add_dir('Favorites — Shows',  {'action': 'trakt_list', 'kind': 'favorites', 'media': 'tv', 'page': '1'}, art=art)
    add_dir('[B]My Watched History — Movies[/B]',
            {'action': 'trakt_history', 'media': 'movie', 'page': '1'}, art=art,
            plot='Movies you have marked as watched on Trakt, most recently watched first.')
    add_dir('[B]My Watched History — Shows[/B]',
            {'action': 'trakt_history', 'media': 'tv', 'page': '1'}, art=art,
            plot='TV shows you have marked as watched on Trakt, most recently watched first.')
    add_dir('My Ratings — Movies',
            {'action': 'trakt_my_ratings', 'media': 'movie', 'page': '1'}, art=art,
            plot='Movies you have rated on Trakt.')
    add_dir('My Ratings — Shows',
            {'action': 'trakt_my_ratings', 'media': 'tv', 'page': '1'}, art=art,
            plot='TV shows you have rated on Trakt.')
    add_dir('[B]My Personal Lists[/B]', {'action': 'trakt_personal_lists'}, art=art,
            plot='User-created lists on your Trakt account.')
    end_directory(content='')


def _trakt_path(kind, media):
    plural = 'movies' if media == 'movie' else 'shows'
    if kind == 'watchlist':
        return '/sync/watchlist/%s' % plural
    if kind == 'collection':
        return '/sync/collection/%s' % plural
    if kind == 'favorites':
        return '/users/me/favorites/%s' % plural
    if kind == 'recommendations':
        return '/recommendations/%s' % plural
    return '/sync/watchlist/%s' % plural


def trakt_list(kind, media, page=1):
    """Render a Trakt list (watchlist / collection / favorites / recommendations).

    Pages of 100 items each — the picker has a Next/Prev page row so the
    full list (rogermae has 945 movies + 480 shows) is always reachable.
    """
    if kind == 'recommendations':
        # /recommendations endpoint doesn't paginate by page — it returns
        # a fixed list of ~100. Honour that.
        data = TR._get(_trakt_path(kind, media),
                       params={'limit': 100}) or []
    else:
        # Honest 100-per-page pagination — Trakt silently caps higher limits.
        data = TR._get(_trakt_path(kind, media),
                       params={'limit': 100, 'page': page}) or []
    results = []
    for it in data:
        obj = it.get('movie') if media == 'movie' else it.get('show')
        if obj is None and kind == 'recommendations':
            obj = it
        det = _resolve_to_tmdb(obj, media)
        if det:
            results.append(det)
    has_next = len(data) >= 100 and kind != 'recommendations'
    if not results:
        if kind == 'recommendations':
            notify('Trakt: watch and rate more titles to unlock recommendations', time=5000)
        else:
            notify('Trakt: list is empty')
        end_directory(''); return
    if page > 1:
        add_dir('<< Previous Page (Page %d)' % (page - 1),
                {'action': 'trakt_list', 'kind': kind, 'media': media, 'page': str(page - 1)},
                art={'icon': ICON, 'fanart': FANART})
    _render(results, media,
            next_action='trakt_list' if has_next else None,
            next_params={'kind': kind, 'media': media} if has_next else None,
            page=page)


def trakt_history(media, page=1):
    """Watched history from Trakt — most recently watched first."""
    limit = 100
    plural = 'movies' if media == 'movie' else 'shows'
    data = TR._get('/users/me/history/%s' % plural,
                   params={'limit': limit, 'page': page}) or []
    seen_ids = set()
    results = []
    for it in data:
        obj = it.get('movie') if media == 'movie' else it.get('show')
        if not obj:
            continue
        ids = obj.get('ids') or {}
        uid = ids.get('tmdb') or ids.get('imdb')
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        det = _resolve_to_tmdb(obj, media)
        if det:
            results.append(det)
    has_next = len(data) >= limit
    if not results:
        notify('Trakt: no watch history yet')
        end_directory(''); return
    if page > 1:
        add_dir('<< Previous Page (Page %d)' % (page - 1),
                {'action': 'trakt_history', 'media': media, 'page': str(page - 1)},
                art={'icon': ICON, 'fanart': FANART})
    _render(results, media,
            next_action='trakt_history' if has_next else None,
            next_params={'media': media} if has_next else None,
            page=page)


def trakt_my_ratings(media, page=1):
    """Titles the user has rated on Trakt — highest rating first."""
    limit = 100
    plural = 'movies' if media == 'movie' else 'shows'
    data = TR._get('/users/me/ratings/%s' % plural,
                   params={'limit': limit, 'page': page}) or []
    results = []
    for it in data:
        obj = it.get('movie') if media == 'movie' else it.get('show')
        det = _resolve_to_tmdb(obj, media)
        if det:
            # Embed user rating into the item so Kodi can display it.
            det['_trakt_rating'] = it.get('rating')
            results.append(det)
    has_next = len(data) >= limit
    if not results:
        notify('Trakt: no ratings yet')
        end_directory(''); return
    if page > 1:
        add_dir('<< Previous Page (Page %d)' % (page - 1),
                {'action': 'trakt_my_ratings', 'media': media, 'page': str(page - 1)},
                art={'icon': ICON, 'fanart': FANART})
    _render(results, media,
            next_action='trakt_my_ratings' if has_next else None,
            next_params={'media': media} if has_next else None,
            page=page)


def trakt_personal_lists():
    data = TR._get('/users/me/lists') or []
    if not data:
        notify('Trakt: no personal lists')
        end_directory(''); return
    for lst in data:
        name = lst.get('name') or 'List'
        slug = (lst.get('ids') or {}).get('slug') or lst.get('id')
        count = lst.get('item_count') or 0
        if slug is None:
            continue
        add_dir('%s (%d)' % (name, count),
                {'action': 'trakt_personal_list_view', 'slug': slug},
                plot=lst.get('description') or '')
    end_directory(content='')


def _personal_list_items(slug):
    """Return ALL items on a personal Trakt list (auto-paginated).

    Trakt caps each request at 100 items even when you ask for more,
    which is exactly the bug rogermae hit: a 480-item personal list
    returned only ~2 shows / ~99 movies because we made a single un-paged
    request and Trakt sliced it to 100 entries. ``get_all_paginated``
    walks every page until empty so the entire list is rendered.
    """
    return TR.get_all_paginated('/users/me/lists/%s/items' % slug,
                                 per_page=100, hard_cap=10000)


def trakt_personal_list_view(slug):
    data = _personal_list_items(slug)
    movies, shows = [], []
    for it in data:
        t = it.get('type')
        if t == 'movie':
            m = _resolve_to_tmdb(it.get('movie'), 'movie')
            if m: movies.append(m)
        elif t == 'show':
            s = _resolve_to_tmdb(it.get('show'), 'tv')
            if s: shows.append(s)
    if movies and not shows:
        _render(movies, 'movie'); return
    if shows and not movies:
        _render(shows, 'tv'); return
    if not movies and not shows:
        notify('Trakt: list is empty')
        end_directory(''); return
    # mixed list
    art = {'icon': ICON, 'fanart': FANART}
    add_dir('— Movies (%d) —' % len(movies),
            {'action': 'trakt_personal_list_view_type', 'slug': slug, 'media': 'movie'}, art=art)
    add_dir('— Shows (%d) —' % len(shows),
            {'action': 'trakt_personal_list_view_type', 'slug': slug, 'media': 'tv'}, art=art)
    end_directory(content='')


def trakt_personal_list_view_type(slug, media):
    data = _personal_list_items(slug)
    want = 'movie' if media == 'movie' else 'show'
    results = []
    for it in data:
        if it.get('type') != want:
            continue
        det = _resolve_to_tmdb(it.get(want), media)
        if det:
            results.append(det)
    _render(results, media)


# ---------------- SIMKL ----------------

def simkl_mylists():
    if not SK.is_authenticated():
        notify('SIMKL: not authenticated')
        end_directory(''); return
    art = {'icon': ICON, 'fanart': FANART}
    add_dir('Plan to Watch — Movies', {'action': 'simkl_list', 'kind': 'plantowatch', 'media': 'movie'}, art=art)
    add_dir('Plan to Watch — Shows',  {'action': 'simkl_list', 'kind': 'plantowatch', 'media': 'tv'}, art=art)
    add_dir('Plan to Watch — Anime',  {'action': 'simkl_list', 'kind': 'plantowatch', 'media': 'anime'}, art=art)
    add_dir('Completed — Movies', {'action': 'simkl_list', 'kind': 'completed', 'media': 'movie'}, art=art)
    add_dir('Completed — Shows',  {'action': 'simkl_list', 'kind': 'completed', 'media': 'tv'}, art=art)
    add_dir('Completed — Anime',  {'action': 'simkl_list', 'kind': 'completed', 'media': 'anime'}, art=art)
    add_dir('On Hold — Shows',    {'action': 'simkl_list', 'kind': 'hold', 'media': 'tv'}, art=art)
    add_dir('On Hold — Anime',    {'action': 'simkl_list', 'kind': 'hold', 'media': 'anime'}, art=art)
    add_dir('Dropped — Shows',    {'action': 'simkl_list', 'kind': 'dropped', 'media': 'tv'}, art=art)
    add_dir('Dropped — Anime',    {'action': 'simkl_list', 'kind': 'dropped', 'media': 'anime'}, art=art)
    end_directory(content='')


def simkl_list(kind, media):
    # media: movie | tv | anime   (anime rendered as tv)
    if media == 'movie':
        plural = 'movies'
    elif media == 'anime':
        plural = 'anime'
    else:
        plural = 'shows'
    data = SK._get('/sync/all-items/%s' % plural,
                   params={'extended': 'full', 'status': kind}) or {}
    arr = data.get(plural) or []
    render_media = 'movie' if media == 'movie' else 'tv'
    results = []
    for it in arr:
        obj = it.get('movie') or it.get('show') or it.get('anime')
        det = _resolve_to_tmdb(obj, render_media)
        if det:
            results.append(det)
    if not results:
        notify('SIMKL: list is empty')
    _render(results, render_media)


# ---------------- Bingebase ----------------

def bingebase_mylists():
    """Folder shown only when Bingebase is enabled + authenticated.

    Bingebase's public Kodi API only exposes ``/api/v1/kodi/export`` for
    watched-history — there is no watchlist / favourites / personal-list
    endpoint. So we surface exactly that: synced watched movies and
    synced watched episodes (grouped by show)."""
    if not BB.is_authenticated():
        notify('Bingebase: not authenticated')
        end_directory(''); return
    art = {'icon': ICON, 'fanart': FANART}
    add_dir('[B]Synced Watched — Movies[/B]',
            {'action': 'bingebase_watched', 'media': 'movie'}, art=art,
            plot='Movies recorded as watched by Bingebase '
                 '(includes scrobbles pushed from vidscr).')
    add_dir('[B]Synced Watched — Shows[/B]',
            {'action': 'bingebase_watched', 'media': 'tv'}, art=art,
            plot='TV shows with at least one episode watched on Bingebase '
                 '(grouped by show).')
    end_directory(content='')


def bingebase_watched(media):
    """Render the user's Bingebase watched movies or shows."""
    if not BB.is_authenticated():
        notify('Bingebase: not authenticated')
        end_directory(''); return
    data = BB.export_history() or {}
    movies = data.get('movies') or []
    eps = data.get('episodes') or []

    results = []
    if media == 'movie':
        seen = set()
        for m in movies:
            uids = m.get('uniqueIds') or {}
            tmdb_id = uids.get('tmdb') or uids.get('Tmdb')
            imdb_id = uids.get('imdb') or uids.get('Imdb')
            key = tmdb_id or imdb_id
            if not key or key in seen:
                continue
            seen.add(key)
            det = _resolve_to_tmdb({'ids': {'tmdb': tmdb_id, 'imdb': imdb_id}},
                                    'movie')
            if det:
                results.append(det)
    else:
        # Group episodes by show.
        seen = set()
        for ep in eps:
            show = ep.get('show') or {}
            uids = show.get('uniqueIds') or {}
            tmdb_id = uids.get('tmdb') or uids.get('Tmdb')
            imdb_id = uids.get('imdb') or uids.get('Imdb')
            key = tmdb_id or imdb_id or show.get('title')
            if not key or key in seen:
                continue
            seen.add(key)
            det = _resolve_to_tmdb({'ids': {'tmdb': tmdb_id, 'imdb': imdb_id}},
                                    'tv')
            if det:
                results.append(det)

    if not results:
        notify('Bingebase: no watched history yet')
        end_directory(''); return
    _render(results, media)


def bingebase_notice():
    xbmcgui.Dialog().ok(
        'Bingebase — custom lists',
        'Bingebase\'s public API currently only exposes watched-history '
        'import/export. Watchlists and personal lists are not yet available '
        'through the API.\n\n'
        'You can still use Bingebase to scrobble your playback activity '
        '(enable "Scrobble playback to Bingebase" in settings).')
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False,
                              updateListing=False, cacheToDisc=False)


# ---------------- Context-menu add / remove ----------------

def _trackers_enabled_and_auth():
    """Returns dict of available trackers: trakt, simkl."""
    out = {}
    if get_setting_bool('trakt_enabled') and TR.is_authenticated():
        out['trakt'] = True
    if get_setting_bool('simkl_enabled') and SK.is_authenticated():
        out['simkl'] = True
    return out


def _list_options(action):
    """Return list of (label, service, key) pairs for add/remove dialogs.

    For Trakt we also enumerate the user's personal lists so the picker
    can add/remove directly into them — without going through "My Lists".
    Each personal-list entry has ``key`` shaped as ``personal:<slug>``."""
    avail = _trackers_enabled_and_auth()
    opts = []
    if 'trakt' in avail:
        opts.append(('Trakt — Watchlist', 'trakt', 'watchlist'))
        opts.append(('Trakt — Collection', 'trakt', 'collection'))
        opts.append(('Trakt — Favorites', 'trakt', 'favorites'))
        try:
            for lst in TR.get_personal_lists():
                name = lst.get('name') or 'List'
                slug = (lst.get('ids') or {}).get('slug') or lst.get('id')
                if not slug:
                    continue
                opts.append(('Trakt — %s' % name, 'trakt',
                             'personal:%s' % slug))
        except Exception as e:
            log('mylists: personal-list enum failed %s' % e)
    if 'simkl' in avail:
        opts.append(('SIMKL — Plan to Watch', 'simkl', 'plantowatch'))
        opts.append(('SIMKL — Completed', 'simkl', 'completed'))
        opts.append(('SIMKL — On Hold', 'simkl', 'hold'))
        opts.append(('SIMKL — Dropped', 'simkl', 'dropped'))
    return opts


def tracker_add_dialog(media_type, tmdb_id=None, imdb_id=None, title=''):
    opts = _list_options('add')
    if not opts:
        notify('No authenticated trackers — please sign in first', time=4000)
        return
    idx = xbmcgui.Dialog().select('Add to list', [o[0] for o in opts])
    if idx < 0:
        return
    label, service, key = opts[idx]
    ok = False
    if service == 'trakt':
        if key.startswith('personal:'):
            slug = key.split(':', 1)[1]
            ok = TR.add_to_personal_list(slug, media_type,
                                          tmdb_id=tmdb_id, imdb_id=imdb_id)
        else:
            ok = TR.add_to_list(key, media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    elif service == 'simkl':
        ok = SK.add_to_list(key, media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if ok:
        notify('Added to %s' % label, time=3000)
    else:
        notify('Add to %s failed — see Settings → %s → token status'
               % (label, 'Trakt' if service == 'trakt' else 'SIMKL'), time=5000)


def tracker_remove_dialog(media_type, tmdb_id=None, imdb_id=None, title=''):
    opts = _list_options('remove')
    if not opts:
        notify('No authenticated trackers — please sign in first', time=4000)
        return
    idx = xbmcgui.Dialog().select('Remove from list', [o[0] for o in opts])
    if idx < 0:
        return
    label, service, key = opts[idx]
    ok = False
    if service == 'trakt':
        if key.startswith('personal:'):
            slug = key.split(':', 1)[1]
            ok = TR.remove_from_personal_list(slug, media_type,
                                               tmdb_id=tmdb_id, imdb_id=imdb_id)
        else:
            ok = TR.remove_from_list(key, media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    elif service == 'simkl':
        ok = SK.remove_from_list(key, media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if ok:
        notify('Removed from %s' % label, time=3000)
    else:
        notify('Remove from %s failed — see Settings → %s → token status'
               % (label, 'Trakt' if service == 'trakt' else 'SIMKL'), time=5000)


def context_menu_entries(media_type, tmdb_id=None, imdb_id=None, title=''):
    """Build context-menu tuples for movie / show rows.
    Returns empty list when no tracker is enabled+authenticated."""
    from .common import build_url
    if not _trackers_enabled_and_auth():
        return []
    entries = []
    params = {'action': 'tracker_add', 'media_type': media_type}
    if tmdb_id is not None:
        params['tmdb_id'] = tmdb_id
    if imdb_id:
        params['imdb_id'] = imdb_id
    if title:
        params['title'] = title
    entries.append(('[B]+ Add to list…[/B]', 'RunPlugin(%s)' % build_url(**params)))
    params['action'] = 'tracker_remove'
    entries.append(('[B]− Remove from list…[/B]', 'RunPlugin(%s)' % build_url(**params)))
    return entries
