# -*- coding: utf-8 -*-
"""One folder for a mixed Trakt, MDBList, or TMDb list.

Movies, shows, and episodes stay in the list's own order. One sort covers the
whole list. The skin view follows whichever type has the most items on the page.
"""
from __future__ import absolute_import

from six.moves import urllib_parse

_CONTENT = {
    'movie': 'movies',
    'tvshow': 'tvshows',
    'episode': 'episodes',
}


def _majority(rows):
    counts = {'movies': 0, 'tvshows': 0, 'episodes': 0}
    for row in rows or []:
        content = _CONTENT.get((row or {}).get('_kind'))
        if content:
            counts[content] += 1
    if not any(counts.values()):
        return 'movies'
    return max(('movies', 'tvshows', 'episodes'), key=lambda key: counts[key])


def _extended_trakt_url(url):
    split = urllib_parse.urlsplit(url)
    query = dict(urllib_parse.parse_qsl(split.query))
    query['extended'] = 'full'
    encoded = urllib_parse.urlencode(query).replace('%2C', ',')
    return urllib_parse.urlunsplit((split.scheme, split.netloc, split.path, encoded, ''))


def _trakt_kind(item):
    kind = str((item or {}).get('type') or '').lower()
    if kind in ('movie', 'show', 'season', 'episode'):
        return kind
    if isinstance(item.get('movie'), dict):
        return 'movie'
    if isinstance(item.get('episode'), dict):
        return 'episode'
    if isinstance(item.get('show'), dict):
        return 'show'
    return ''


def show_mixed(rows, page_base, next_query, cache_to_disc=False):
    """Page a combined list and paint it as one directory."""
    import sys
    from resources.lib.indexers import episodes
    from resources.lib.indexers import movies
    from resources.lib.indexers import tvshows
    from resources.lib.modules import control
    from resources.lib.modules import views
    base, page = control.list_page(page_base)
    page_rows = control.page_items(list(rows or []), page, base)
    syshandle = int(sys.argv[1])
    if not page_rows:
        control.infoDialog('That list is empty.', sound=True)
        control.content(syshandle, 'movies')
        control.directory(syshandle, cacheToDisc=cache_to_disc)
        return
    for index, row in enumerate(page_rows):
        try:
            row['_page'] = index
        except Exception:
            pass
    groups = {'movie': [], 'tvshow': [], 'episode': []}
    for row in page_rows:
        kind = row.get('_kind')
        if kind in groups:
            groups[kind].append(row)
    bucket = []
    if groups['movie']:
        indexer = movies.movies()
        indexer.list = groups['movie']
        indexer._list_key = base
        indexer.cacheToDisc = False
        indexer.worker()
        indexer.movieDirectory(indexer.list, bucket=bucket)
    if groups['tvshow']:
        indexer = tvshows.tvshows()
        indexer.list = groups['tvshow']
        indexer._list_key = base
        indexer.cacheToDisc = False
        indexer.worker()
        indexer.tvshowDirectory(indexer.list, bucket=bucket)
    if groups['episode']:
        episodes.episodes().episodeDirectory(groups['episode'], bucket=bucket)
    bucket.sort(key=lambda entry: entry[0])
    for _order, item_url, listitem, is_folder in bucket:
        control.addItem(handle=syshandle, url=item_url, listitem=listitem, isFolder=is_folder)
    nxt = ''
    for row in page_rows:
        if row.get('next'):
            nxt = row['next']
            break
    if nxt:
        icon = control.addonNext()
        fanart = control.addonFanart()
        link = '%s?%s&url=%s' % (sys.argv[0], next_query, urllib_parse.quote_plus(nxt))
        try:
            item = control.item(label='[I]Next Page[/I]', offscreen=True)
        except Exception:
            item = control.item(label='[I]Next Page[/I]')
        item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon, 'fanart': fanart})
        control.addItem(handle=syshandle, url=link, listitem=item, isFolder=True)
    content = _majority(page_rows)
    control.content(syshandle, content)
    control.directory(syshandle, cacheToDisc=cache_to_disc)
    if bucket:
        views.setView(content)


def open_trakt_mixed(url):
    """Open a Trakt list that contains more than one of movie, show, and episode."""
    from resources.lib.indexers import episodes
    from resources.lib.indexers import movies
    from resources.lib.indexers import tvshows
    from resources.lib.modules import control
    from resources.lib.modules import shelf_sort
    from resources.lib.modules import trakt
    base, _page = control.list_page(url)
    raw = trakt.getTraktAsJsonPaged(_extended_trakt_url(base)) or []
    movies_src, shows_src, episodes_src = [], [], []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row['_mix'] = index
        kind = _trakt_kind(row)
        if kind == 'movie':
            movies_src.append(row)
        elif kind == 'episode':
            episodes_src.append(row)
        elif kind in ('show', 'season'):
            shows_src.append(row)
    combined = []
    if movies_src:
        indexer = movies.movies()
        combined.extend(indexer.trakt_list(base, indexer.trakt_user, payload=movies_src) or [])
    if shows_src:
        indexer = tvshows.tvshows()
        combined.extend(indexer.trakt_list(base, indexer.trakt_user, payload=shows_src) or [])
    if episodes_src:
        indexer = episodes.episodes()
        combined.extend(indexer.trakt_list(base, indexer.trakt_user, payload=episodes_src) or [])
    combined = [row for row in combined if isinstance(row, dict) and row.get('_kind')]
    combined.sort(key=lambda row: row.get('_mix', 0))
    combined = trakt.filter_shelf_exclusions(combined, base)
    shelf = shelf_sort.trakt_shelf_from_url(base)
    combined = shelf_sort.sort_items(
        combined, 'trakt', 'mixed', shelf, sortable=shelf_sort.TRAKT_SORTABLE)
    show_mixed(combined, url, 'action=trakt_mixed', cache_to_disc=False)


def _mdblist_sequence(payload):
    items = [item for item in (payload.get('items') or []) if isinstance(item, dict)]
    if items:
        return list(enumerate(items))
    sequence = []
    order = 0
    for key in ('movies', 'shows', 'seasons', 'episodes'):
        for item in payload.get(key) or []:
            if isinstance(item, dict):
                sequence.append((order, item))
                order += 1
    return sequence


def mdblist_mixed_rows(list_id, list_type='user'):
    from resources.lib.modules import cache
    from resources.lib.modules import mdblist
    payload = cache.get(mdblist._list_payload, mdblist._LIST_CACHE_HOURS, list_type, list_id) or {}
    if not isinstance(payload, dict):
        return []
    rows = []
    for order, item in _mdblist_sequence(payload):
        side = mdblist._item_side(item)
        if side == 'movie':
            row = mdblist._directory_row(item, 'movies')
            kind = 'movie'
        elif side == 'tv':
            row = mdblist._directory_row(item, 'shows')
            kind = 'tvshow'
        elif side == 'episode':
            row = mdblist._episode_directory_row(item)
            kind = 'episode'
        else:
            continue
        if not row:
            continue
        row['_mix'] = order
        row['_kind'] = kind
        rows.append(row)
    return rows


def _tmdb_page_url(url, page):
    split = urllib_parse.urlsplit(str(url or ''))
    query = dict(urllib_parse.parse_qsl(split.query))
    query['page'] = str(page)
    return urllib_parse.urlunsplit((split.scheme, split.netloc, split.path, urllib_parse.urlencode(query), ''))


def _tmdb_list_items(url):
    """Every movie and show in a TMDb list, in list order. One fetch for both types."""
    from resources.lib.modules import client
    from resources.lib.modules import tmdb_utils
    collected = []
    seen = set()
    order = 0
    page_url = _tmdb_page_url(url, 1)
    for _guard in range(40):
        try:
            result = client.scrapePage(page_url, headers=tmdb_utils.list_fetch_headers(page_url), timeout='30').json()
        except Exception:
            break
        if not isinstance(result, dict):
            break
        items = result.get('results') or result.get('items') or result.get('parts') or []
        if not items:
            break
        for raw in items:
            media_type, item = tmdb_utils.unwrap_tmdb_list_item(raw)
            if media_type not in ('movie', 'tv') or not isinstance(item, dict):
                continue
            tmdb = str(item.get('id') or '')
            key = (media_type, tmdb)
            if not tmdb or tmdb == '0' or key in seen:
                continue
            seen.add(key)
            stamped = dict(item)
            stamped['media_type'] = media_type
            stamped['_mix'] = order
            order += 1
            collected.append(stamped)
        try:
            page = int(result.get('page') or 1)
            total = int(result.get('total_pages') or page)
        except Exception:
            break
        if page >= total:
            break
        page_url = _tmdb_page_url(url, page + 1)
    return collected


def open_tmdb_mixed(url):
    """Open a TMDb list that contains both movies and shows."""
    from resources.lib.indexers import movies
    from resources.lib.indexers import tvshows
    from resources.lib.modules import control
    from resources.lib.modules import tmdb_utils
    base, _page = control.list_page(url)
    raw = _tmdb_list_items(base)
    movies_src = [row for row in raw if row.get('media_type') == 'movie']
    shows_src = [row for row in raw if row.get('media_type') == 'tv']
    combined = []
    if movies_src:
        indexer = movies.movies()
        combined.extend(indexer.tmdb_list(base, payload=movies_src) or [])
    if shows_src:
        indexer = tvshows.tvshows()
        combined.extend(indexer.tmdb_list(base, payload=shows_src) or [])
    combined = [row for row in combined if isinstance(row, dict) and row.get('_kind')]
    combined.sort(key=lambda row: row.get('_mix', 0))
    combined = tmdb_utils.apply_my_shelf_sort(combined, base, 'mixed')
    show_mixed(combined, url, 'action=tmdb_mixed', cache_to_disc=False)


def open_mdblist_mixed(list_type, list_id, name=None, url=None):
    from resources.lib.modules import shelf_sort
    list_type = list_type if list_type in ('user', 'external') else 'user'
    key = 'mdblist_list_%s_%s' % (list_type, list_id)
    rows = mdblist_mixed_rows(list_id, list_type)
    rows.sort(key=lambda row: row.get('_mix', 0))
    shelf = shelf_sort.personal_shelf_key(list_id)
    rows = shelf_sort.sort_items(
        rows, 'mdblist', 'mixed', shelf, sortable=shelf_sort.MDBLIST_SORTABLE)
    next_query = 'action=mdblist_list_open&list_type=%s&list_id=%s&name=%s' % (
        list_type, list_id, urllib_parse.quote_plus(name or 'List'))
    show_mixed(rows, url or key, next_query, cache_to_disc=False)
