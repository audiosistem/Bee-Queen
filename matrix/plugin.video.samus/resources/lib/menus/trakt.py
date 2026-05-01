# -*- coding: utf-8 -*-

import sys
import xbmc
import xbmcgui
import xbmcplugin
import threading
from urllib.parse import urlencode, quote
from resources.lib import trakt as trakt_api
from resources.lib.utils import get_icon_path, build_item, build_item_list, build_item_tvshow, build_item_tvshow_list
from resources.lib.tmdb import movies as tmdb_movies
from resources.lib.tmdb import tv as tmdb_tv
from resources.lib.tmdb.api import get_genre_map

handle = int(sys.argv[1])

IMG_BASE = 'https://image.tmdb.org/t/p/w500'
FANART_BASE = 'https://image.tmdb.org/t/p/original'


def menu():
    xbmcplugin.setPluginCategory(handle, 'Trakt')

    items = [
        ('Trending Filme',   'trakt_trending_movies',   'trending'),
        ('Populare Filme',   'trakt_popular_movies',    'popular'),
        ('Urmărite Filme',   'trakt_watched_movies',    'popular'),
        ('Trending Seriale', 'trakt_trending_shows',    'trending'),
        ('Populare Seriale', 'trakt_popular_shows',     'popular'),
        ('Urmărite Seriale', 'trakt_watched_shows',     'popular'),
    ]

    if trakt_api.is_authenticated():
        items += [
            ('Watchlist Filme',        'trakt_watchlist_movies',        'favorite'),
            ('Watchlist Seriale',      'trakt_watchlist_shows',         'favorite'),
            ('Istoricul meu',          'trakt_history_movies',          'popular'),
            ('Recomandate Filme',      'trakt_recommendations_movies',  'popular'),
            ('Recomandate Seriale',    'trakt_recommendations_shows',   'popular'),
        ]

        li = xbmcgui.ListItem('Deconectare Trakt')
        li.setArt({'thumb': get_icon_path('trakt'), 'icon': get_icon_path('trakt')})
        xbmcplugin.addDirectoryItem(
            handle, f'{sys.argv[0]}?action=trakt_logout', li, isFolder=False
        )
    else:
        li = xbmcgui.ListItem('Autentificare Trakt')
        li.setArt({'thumb': get_icon_path('trakt'), 'icon': get_icon_path('trakt')})
        xbmcplugin.addDirectoryItem(
            handle, f'{sys.argv[0]}?action=trakt_auth', li, isFolder=False
        )

    items += [
        ('Liste',  'trakt_lists',  'popular'),
    ]

    for label, action, icon in items:
        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': get_icon_path(icon), 'icon': get_icon_path(icon)})
        xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action={action}', li, isFolder=True)

    xbmcplugin.endOfDirectory(handle)


def _show_movie_list(items_raw, page, next_action, normalize_fn):
    """Generic renderer for a list of Trakt movie items."""
    if not items_raw:
        xbmcgui.Dialog().notification('Trakt', 'Nicio sursă de date', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return

    xbmcplugin.setContent(handle, 'movies')
    genre_map = get_genre_map('movie')

    for raw in items_raw:
        item = normalize_fn(raw)
        if not item.get('tmdb_id'):
            continue
        try:
            full = tmdb_movies.get_movie_details(item['tmdb_id'])
            li = build_item(full) if full else build_item_list(item, genre_map)
        except Exception:
            li = build_item_list(item, genre_map)
        li.setProperty('IsPlayable', 'true')
        url = f"{sys.argv[0]}?action=play_movie&tmdb_id={item['tmdb_id']}"
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=False)

    next_page = page + 1
    next_url = f"{sys.argv[0]}?{urlencode({'action': next_action, 'page': next_page})}"
    next_li = xbmcgui.ListItem(f'Pagina {next_page} →')
    next_li.setArt({'thumb': get_icon_path('next'), 'icon': get_icon_path('next')})
    xbmcplugin.addDirectoryItem(handle, next_url, next_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def _show_tvshow_list(items_raw, page, next_action, normalize_fn):
    """Generic renderer for a list of Trakt show items."""
    if not items_raw:
        xbmcgui.Dialog().notification('Trakt', 'Nicio sursă de date', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return

    xbmcplugin.setContent(handle, 'tvshows')
    genre_map = get_genre_map('tv')

    for raw in items_raw:
        item = normalize_fn(raw)
        if not item.get('tmdb_id'):
            continue
        try:
            full = tmdb_tv.get_tv_details(item['tmdb_id'])
            li = build_item_tvshow(full) if full else build_item_tvshow_list(item, genre_map)
        except Exception:
            li = build_item_tvshow_list(item, genre_map)
        url = f"{sys.argv[0]}?action=tv_details&id={item['tmdb_id']}"
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)

    next_page = page + 1
    next_url = f"{sys.argv[0]}?{urlencode({'action': next_action, 'page': next_page})}"
    next_li = xbmcgui.ListItem(f'Pagina {next_page} →')
    next_li.setArt({'thumb': get_icon_path('next'), 'icon': get_icon_path('next')})
    xbmcplugin.addDirectoryItem(handle, next_url, next_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


# ---------------------------------------------------------------------------
# Public movie lists
# ---------------------------------------------------------------------------

def show_trending_movies(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Trending Filme')
    data = trakt_api.get_trending_movies(page=page)
    _show_movie_list(data, page, 'trakt_trending_movies', trakt_api.normalize_movie)


def show_popular_movies(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Populare Filme')
    data = trakt_api.get_popular_movies(page=page)
    # popular endpoint returns items directly (not wrapped)
    _show_movie_list(data, page, 'trakt_popular_movies', lambda x: trakt_api.normalize_movie({'movie': x}) if 'ids' in x else trakt_api.normalize_movie(x))


def show_watched_movies(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Urmărite Filme')
    data = trakt_api.get_most_watched_movies(page=page)
    _show_movie_list(data, page, 'trakt_watched_movies', trakt_api.normalize_movie)


def show_watchlist_movies(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Watchlist Filme')
    if not trakt_api.is_authenticated():
        xbmcgui.Dialog().notification('Trakt', 'Autentificare necesară', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    data = trakt_api.get_watchlist_movies(page=page)
    _show_movie_list(data, page, 'trakt_watchlist_movies', trakt_api.normalize_movie)


def show_history_movies(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Istoricul meu')
    if not trakt_api.is_authenticated():
        xbmcgui.Dialog().notification('Trakt', 'Autentificare necesară', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    data = trakt_api.get_history_movies(page=page)
    _show_movie_list(data, page, 'trakt_history_movies', trakt_api.normalize_movie)


# ---------------------------------------------------------------------------
# Public show lists
# ---------------------------------------------------------------------------

def show_trending_shows(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Trending Seriale')
    data = trakt_api.get_trending_shows(page=page)
    _show_tvshow_list(data, page, 'trakt_trending_shows', trakt_api.normalize_show)


def show_popular_shows(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Populare Seriale')
    data = trakt_api.get_popular_shows(page=page)
    _show_tvshow_list(data, page, 'trakt_popular_shows', lambda x: trakt_api.normalize_show({'show': x}) if 'ids' in x else trakt_api.normalize_show(x))


def show_watched_shows(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Urmărite Seriale')
    data = trakt_api.get_most_watched_shows(page=page)
    _show_tvshow_list(data, page, 'trakt_watched_shows', trakt_api.normalize_show)


def show_watchlist_shows(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Watchlist Seriale')
    if not trakt_api.is_authenticated():
        xbmcgui.Dialog().notification('Trakt', 'Autentificare necesară', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    data = trakt_api.get_watchlist_shows(page=page)
    _show_tvshow_list(data, page, 'trakt_watchlist_shows', trakt_api.normalize_show)


# ---------------------------------------------------------------------------
# Recommendations (authenticated)
# ---------------------------------------------------------------------------

def show_recommendations_movies():
    xbmcplugin.setPluginCategory(handle, 'Trakt — Recomandate Filme')
    if not trakt_api.is_authenticated():
        xbmcgui.Dialog().notification('Trakt', 'Autentificare necesară', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    data = trakt_api.get_recommendations_movies()
    # recommendations endpoint returns a plain list of movie objects
    _show_movie_list(
        data, 1, 'trakt_recommendations_movies',
        lambda x: trakt_api.normalize_movie({'movie': x}) if 'ids' in x else trakt_api.normalize_movie(x),
    )


def show_recommendations_shows():
    xbmcplugin.setPluginCategory(handle, 'Trakt — Recomandate Seriale')
    if not trakt_api.is_authenticated():
        xbmcgui.Dialog().notification('Trakt', 'Autentificare necesară', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    data = trakt_api.get_recommendations_shows()
    _show_tvshow_list(
        data, 1, 'trakt_recommendations_shows',
        lambda x: trakt_api.normalize_show({'show': x}) if 'ids' in x else trakt_api.normalize_show(x),
    )


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

def _extract_list_meta(raw):
    """Normalize a list object from trending/popular/search responses."""
    lst = raw.get('list') or raw
    user = lst.get('user') or {}
    ids = lst.get('ids') or {}
    return {
        'name': lst.get('name', ''),
        'description': lst.get('description', ''),
        'item_count': lst.get('item_count', 0),
        'likes': lst.get('likes', 0),
        'slug': ids.get('slug', ''),
        'username': (user.get('ids') or {}).get('slug') or user.get('username', ''),
    }


def _add_list_directory_item(meta):
    count = meta['item_count']
    label = meta['name']
    if count:
        label += f'  [{count}]'
    li = xbmcgui.ListItem(label=label)
    li.setArt({'thumb': get_icon_path('popular'), 'icon': get_icon_path('popular')})
    info = li.getVideoInfoTag()
    info.setPlot(meta['description'])
    url = f"{sys.argv[0]}?{urlencode({'action': 'trakt_list_items', 'username': meta['username'], 'list_id': meta['slug'], 'list_name': meta['name']})}"
    xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)


def _show_lists(raw_items, page, next_action, next_extra=None):
    if not raw_items:
        xbmcgui.Dialog().notification('Trakt', 'Nicio listă găsită', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    for raw in raw_items:
        meta = _extract_list_meta(raw)
        if not meta['username'] or not meta['slug']:
            continue
        _add_list_directory_item(meta)
    next_page = page + 1
    p = dict(next_extra or {})
    p.update({'action': next_action, 'page': next_page})
    next_li = xbmcgui.ListItem(f'Pagina {next_page} →')
    next_li.setArt({'thumb': get_icon_path('next'), 'icon': get_icon_path('next')})
    xbmcplugin.addDirectoryItem(handle, f"{sys.argv[0]}?{urlencode(p)}", next_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_lists_menu():
    xbmcplugin.setPluginCategory(handle, 'Trakt — Liste')
    folders = [
        ('Trending Liste',  'trakt_trending_lists',  'trending'),
        ('Populare Liste',  'trakt_popular_lists',   'popular'),
    ]
    if trakt_api.is_authenticated():
        folders.insert(0, ('Listele mele', 'trakt_my_lists', 'favorite'))
    for label, action, icon in folders:
        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': get_icon_path(icon), 'icon': get_icon_path(icon)})
        xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action={action}', li, isFolder=True)
    li = xbmcgui.ListItem('Caută Liste')
    li.setArt({'thumb': get_icon_path('search'), 'icon': get_icon_path('search')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=trakt_search_lists', li, isFolder=False)
    xbmcplugin.endOfDirectory(handle)


def show_trending_lists(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Trending Liste')
    data = trakt_api.get_trending_lists(page=page)
    _show_lists(data, page, 'trakt_trending_lists')


def show_popular_lists(page=1):
    xbmcplugin.setPluginCategory(handle, 'Trakt — Populare Liste')
    data = trakt_api.get_popular_lists(page=page)
    _show_lists(data, page, 'trakt_popular_lists')


def show_my_lists():
    xbmcplugin.setPluginCategory(handle, 'Trakt — Listele mele')
    if not trakt_api.is_authenticated():
        xbmcgui.Dialog().notification('Trakt', 'Autentificare necesară', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    data = trakt_api.get_my_lists()
    if not data:
        xbmcgui.Dialog().notification('Trakt', 'Nicio listă găsită', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(handle)
        return
    for lst in data:
        meta = _extract_list_meta(lst)
        if not meta['slug']:
            continue
        if not meta['username']:
            meta['username'] = 'me'
        _add_list_directory_item(meta)
    xbmcplugin.endOfDirectory(handle)


def search_lists(query, page=1):
    xbmcplugin.setPluginCategory(handle, f'Trakt — Liste: {query}')
    data = trakt_api.search_lists(query, page=page)
    _show_lists(data, page, 'trakt_search_lists_results', {'query': query})


def _render_list_items(data, username, list_id, list_name, page):
    """Randează items-urile unei liste Trakt în directorul curent."""
    has_movies = any(item.get('type') == 'movie' for item in data)
    has_shows  = any(item.get('type') == 'show'  for item in data)
    if has_movies and not has_shows:
        xbmcplugin.setContent(handle, 'movies')
    elif has_shows and not has_movies:
        xbmcplugin.setContent(handle, 'tvshows')

    movie_genre_map = get_genre_map('movie')
    tv_genre_map    = get_genre_map('tv')

    for item in data:
        itype = item.get('type')
        if itype == 'movie':
            m = trakt_api.normalize_movie(item)
            if not m.get('tmdb_id'):
                continue
            try:
                full = tmdb_movies.get_movie_details(m['tmdb_id'])
                li = build_item(full) if full else build_item_list(m, movie_genre_map)
            except Exception:
                li = build_item_list(m, movie_genre_map)
            li.setProperty('IsPlayable', 'true')
            url = f"{sys.argv[0]}?action=play_movie&tmdb_id={m['tmdb_id']}"
            xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=False)
        elif itype == 'show':
            s = trakt_api.normalize_show(item)
            if not s.get('tmdb_id'):
                continue
            try:
                full = tmdb_tv.get_tv_details(s['tmdb_id'])
                li = build_item_tvshow(full) if full else build_item_tvshow_list(s, tv_genre_map)
            except Exception:
                li = build_item_tvshow_list(s, tv_genre_map)
            url = f"{sys.argv[0]}?action=tv_details&id={s['tmdb_id']}"
            xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)

    next_page = page + 1
    next_url = f"{sys.argv[0]}?{urlencode({'action': 'trakt_list_items', 'username': username, 'list_id': list_id, 'list_name': list_name, 'page': next_page})}"
    next_li = xbmcgui.ListItem(f'Pagina {next_page} →')
    next_li.setArt({'thumb': get_icon_path('next'), 'icon': get_icon_path('next')})
    xbmcplugin.addDirectoryItem(handle, next_url, next_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def _list_item_ids(items):
    """Set de ID-uri unice pentru compararea cache-urilor."""
    ids = set()
    for item in (items or []):
        itype = item.get('type')
        obj   = item.get(itype) or {}
        tmdb  = (obj.get('ids') or {}).get('tmdb')
        if tmdb:
            ids.add((itype, tmdb))
    return ids


def show_list_items(username, list_id, list_name, page=1):
    xbmcplugin.setPluginCategory(handle, list_name or 'Listă Trakt')

    cached = trakt_api.read_list_cache(username, list_id, page)

    if cached and cached.get('items'):
        # Servim din cache imediat
        _render_list_items(cached['items'], username, list_id, list_name, page)

        # Background refresh doar dacă cache-ul e suficient de vechi
        if not trakt_api.cache_needs_refresh(cached):
            return

        def _bg_refresh():
            fresh = trakt_api.get_list_items(username, list_id, page=page)
            if not fresh:
                return
            old_ids   = _list_item_ids(cached['items'])
            new_ids   = _list_item_ids(fresh)
            new_items = new_ids - old_ids
            if new_items or len(fresh) != len(cached['items']):
                trakt_api.write_list_cache(username, list_id, page, fresh)
                if new_items:
                    xbmcgui.Dialog().notification(
                        'Trakt',
                        f'{len(new_items)} element(e) noi în listă. Apasă F5.',
                        xbmcgui.NOTIFICATION_INFO, 5000,
                    )

        threading.Thread(target=_bg_refresh, daemon=True).start()
    else:
        # Fără cache: fetch normal, stocăm, randăm
        data = trakt_api.get_list_items(username, list_id, page=page)
        if not data:
            xbmcgui.Dialog().notification('Trakt', 'Lista este goală', xbmcgui.NOTIFICATION_WARNING)
            xbmcplugin.endOfDirectory(handle)
            return
        trakt_api.write_list_cache(username, list_id, page, data)
        _render_list_items(data, username, list_id, list_name, page)
