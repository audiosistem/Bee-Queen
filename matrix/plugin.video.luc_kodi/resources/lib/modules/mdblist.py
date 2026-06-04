# -*- coding: utf-8 -*-
"""
    luc_kodi Add-on
    MDBList integration module — watchlist, user lists, top lists, API client
    Mirrors the trakt.py pattern so navigator/menus can use it identically.
"""

import requests
from resources.lib.modules import control
from resources.lib.modules import log_utils

BASE_URL = 'https://api.mdblist.com'

getSetting = control.setting
setSetting = control.setSetting


# ---------------------------------------------------------------------------
# Credentials helpers
# ---------------------------------------------------------------------------

def getMDBListCredentials():
    """Return (apikey, base_url) or (None, None) if not configured."""
    apikey = getSetting('mdblist.apikey').strip()
    url    = getSetting('mdblist.url').strip().rstrip('/')
    if not url:
        url = BASE_URL
    if apikey:
        return apikey, url
    return None, None


def getMDBListCredentialsInfo():
    """True if apikey is set and MDBList is enabled."""
    apikey, _ = getMDBListCredentials()
    return bool(apikey and getSetting('mdblist.enable') == 'true')


# ---------------------------------------------------------------------------
# Low-level request
# ---------------------------------------------------------------------------

def _get(endpoint, params=None, timeout=15):
    """Authenticated GET → parsed JSON or None on error."""
    apikey, base_url = getMDBListCredentials()
    if not apikey:
        return None
    url = base_url + endpoint
    p = {'apikey': apikey}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_utils.log('MDBList GET %s failed: %s' % (endpoint, e), level=log_utils.LOGWARNING)
        return None


def _post(endpoint, json_data=None, timeout=15):
    """Authenticated POST → parsed JSON or None."""
    apikey, base_url = getMDBListCredentials()
    if not apikey:
        return None
    url = base_url + endpoint
    try:
        r = requests.post(url, params={'apikey': apikey}, json=json_data or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_utils.log('MDBList POST %s failed: %s' % (endpoint, e), level=log_utils.LOGWARNING)
        return None


def _delete(endpoint, json_data=None, timeout=15):
    """Authenticated DELETE → parsed JSON or None."""
    apikey, base_url = getMDBListCredentials()
    if not apikey:
        return None
    url = base_url + endpoint
    try:
        r = requests.delete(url, params={'apikey': apikey}, json=json_data or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_utils.log('MDBList DELETE %s failed: %s' % (endpoint, e), level=log_utils.LOGWARNING)
        return None


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def getWatchlistMovies():
    """Return list of movie dicts {title, year, imdb, tmdb} from watchlist."""
    data = _get('/watchlist/items')
    if not data:
        return []
    items = []
    for m in (data.get('movies') or []):
        try:
            items.append({
                'title':  m.get('title', ''),
                'year':   str(m.get('release_year', '')),
                'imdb':   str(m.get('imdb_id', '')),
                'tmdb':   str(m.get('tmdb_id', '')) if m.get('tmdb_id') else '',
                'tvdb':   '',
                'rank':   m.get('rank', 9999),
            })
        except Exception:
            log_utils.error()
    items.sort(key=lambda x: x.get('rank', 9999))
    return items


def getWatchlistShows():
    """Return list of show dicts {title, year, imdb, tmdb, tvdb} from watchlist."""
    data = _get('/watchlist/items')
    if not data:
        return []
    items = []
    for s in (data.get('shows') or []):
        try:
            items.append({
                'title':  s.get('title', ''),
                'year':   str(s.get('release_year', '')),
                'imdb':   str(s.get('imdb_id', '')),
                'tmdb':   str(s.get('tmdb_id', '')) if s.get('tmdb_id') else '',
                'tvdb':   str(s.get('tvdb_id', '')) if s.get('tvdb_id') else '',
                'rank':   s.get('rank', 9999),
            })
        except Exception:
            log_utils.error()
    items.sort(key=lambda x: x.get('rank', 9999))
    return items


def addToWatchlist(imdb_id, media_type):
    """Add a movie or show to the user watchlist. media_type: 'movie' | 'show'"""
    payload = {media_type: {'ids': {'imdb': imdb_id}}}
    result  = _post('/watchlist/items', json_data=payload)
    return result is not None


def removeFromWatchlist(imdb_id, media_type):
    """Remove a movie or show from the user watchlist."""
    payload = {media_type: {'ids': {'imdb': imdb_id}}}
    result  = _delete('/watchlist/items', json_data=payload)
    return result is not None


# ---------------------------------------------------------------------------
# User lists
# ---------------------------------------------------------------------------

def getUserLists():
    """Return list of user's own lists [{id, name, slug, mediatype, items, dynamic}]."""
    data = _get('/lists/user')
    if not data:
        return []
    if isinstance(data, list):
        return data
    return []


def getListItems(list_id, media_type=None):
    """
    Fetch items from a specific list.
    Returns (movies_list, shows_list) where each element is a dict
    with title, year, imdb, tmdb, tvdb.
    If media_type is 'movie' or 'show', only that type is returned (as flat list).
    """
    data = _get('/lists/%s/items' % list_id)
    if not data:
        return [], []

    def _build_movie(m):
        return {
            'title': m.get('title', ''),
            'year':  str(m.get('release_year', '')),
            'imdb':  str(m.get('imdb_id', '')),
            'tmdb':  str(m.get('tmdb_id', '')) if m.get('tmdb_id') else '',
            'tvdb':  '',
            'rank':  m.get('rank', 9999),
        }

    def _build_show(s):
        return {
            'title': s.get('title', ''),
            'year':  str(s.get('release_year', '')),
            'imdb':  str(s.get('imdb_id', '')),
            'tmdb':  str(s.get('tmdb_id', '')) if s.get('tmdb_id') else '',
            'tvdb':  str(s.get('tvdb_id', '')) if s.get('tvdb_id') else '',
            'rank':  s.get('rank', 9999),
        }

    movies = sorted([_build_movie(m) for m in (data.get('movies') or [])], key=lambda x: x['rank'])
    shows  = sorted([_build_show(s)  for s in (data.get('shows')  or [])], key=lambda x: x['rank'])

    # MDBList sometimes returns TV shows inside the movies[] array with mediatype='show'.
    # This happens for mixed lists or when the list was configured as type 'both'.
    # Detect this and move those items to shows list.
    if media_type == 'show' and not shows:
        show_from_movies = []
        for m in (data.get('movies') or []):
            if str(m.get('mediatype', '')).lower() in ('show', 'tv', 'tvshow', 'series'):
                show_from_movies.append(_build_show(m))
        if show_from_movies:
            shows = sorted(show_from_movies, key=lambda x: x['rank'])

    if media_type == 'movie':
        return movies, []
    if media_type == 'show':
        return [], shows
    return movies, shows


# ---------------------------------------------------------------------------
# Top / trending / search lists
# ---------------------------------------------------------------------------

def getTopLists():
    """Return top public lists sorted by Trakt likes."""
    data = _get('/lists/top')
    if isinstance(data, list):
        return data
    return []


def searchLists(query):
    """Search public lists by title. Returns list of list dicts."""
    data = _get('/search/lists', params={'s': query})
    if isinstance(data, list):
        return data
    return []


# ---------------------------------------------------------------------------
# Media info / ID resolution
# ---------------------------------------------------------------------------

def getMediaInfo(imdb_id):
    """Fetch full info + ratings for a title by IMDb ID."""
    return _get('/', params={'i': imdb_id})


def resolveShowIds(ids_dict):
    """
    Given a dict of available IDs (tmdb, imdb, tvdb, …), resolve the tvdb ID
    if it's missing by querying the MDBList API.
    Returns the (possibly enriched) ids_dict.
    """
    if 'tvdb' in ids_dict and ids_dict['tvdb']:
        return ids_dict
    try:
        if ids_dict.get('tmdb'):
            data = _get('/tm/%s' % ids_dict['tmdb'])
        elif ids_dict.get('imdb'):
            data = _get('/', params={'i': ids_dict['imdb']})
        else:
            return ids_dict
        if data:
            remote_ids = data.get('ids') or {}
            tvdb = remote_ids.get('tvdb') or data.get('tvdb_id')
            if tvdb:
                ids_dict['tvdb'] = str(tvdb)
            if not ids_dict.get('imdb'):
                imdb = remote_ids.get('imdb')
                if imdb:
                    ids_dict['imdb'] = str(imdb)
    except Exception as e:
        log_utils.log('MDBList resolveShowIds failed: %s' % e, level=log_utils.LOGWARNING)
    return ids_dict


# ---------------------------------------------------------------------------
# Context-menu helpers (called from router)
# ---------------------------------------------------------------------------

def manager(name, imdb, media_type):
    """
    Show a dialog to add/remove from MDBList watchlist.
    media_type: 'movie' | 'show'
    """
    items  = [control.lang(40201), control.lang(40202)]  # Add / Remove
    select = control.selectDialog(items, control.lang(40200))
    if select == 0:
        ok = addToWatchlist(imdb, media_type)
        msg = control.lang(40203) if ok else control.lang(40205)
        control.notification(title='MDBList', message=msg)
        control.refresh()
    elif select == 1:
        ok = removeFromWatchlist(imdb, media_type)
        msg = control.lang(40204) if ok else control.lang(40205)
        control.notification(title='MDBList', message=msg)
        control.refresh()


# ---------------------------------------------------------------------------
# Continue Watching  (reads from service.luc_kodi.mdblist local DB)
# ---------------------------------------------------------------------------

def _get_progress_db_path():
    """Resolve the path to the service's progress.db regardless of platform."""
    import xbmcvfs
    folder = xbmcvfs.translatePath(
        'special://profile/addon_data/service.luc_kodi.mdblist'
    )
    import os
    return os.path.join(folder, 'progress.db')


def _read_progress(media_type: str) -> list:
    """
    Read in-progress items from the service's SQLite DB.
    Returns list of dicts already in the format movies.py/episodes.py expect.
    """
    import sqlite3
    import xbmcvfs
    db_path = _get_progress_db_path()
    if not xbmcvfs.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        rows = cur.execute(
            '''SELECT type, imdb, tmdb, tvdb, title, tvshowtitle,
                      season, episode_num, duration, progress_pct, paused_at
               FROM progress WHERE type=? ORDER BY paused_at DESC''',
            (media_type,),
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                'type':        r['type'],
                'imdb':        r['imdb']        or '',
                'tmdb':        r['tmdb']        or '',
                'tvdb':        r['tvdb']        or '',
                'title':       r['title']       or '',
                'originaltitle': r['title']     or '',
                'tvshowtitle': r['tvshowtitle'] or '',
                'season':      int(r['season'])      if (r['season']      or '').isdigit() else 0,
                'episode':     int(r['episode_num']) if (r['episode_num'] or '').isdigit() else 0,
                'duration':    int(r['duration'])    if (r['duration']    or '').isdigit() else 0,
                'progress':    r['progress_pct'] or '0',
                'paused_at':   r['paused_at']   or '',
                'next':        '',
            })
        return result
    except Exception as exc:
        log_utils.log('MDBList _read_progress failed: %s' % exc, level=log_utils.LOGWARNING)
        return []


def _fetch_server_paused() -> tuple:
    """
    Fetch 'Recently Paused' items directly from MDBList's server.

    MDBList stores paused scrobbles server-side (visible at /users/*/activity/).
    The GET /scrobble endpoint mirrors Trakt's GET /sync/playback.

    Response structure (Trakt-compatible):
      {
        "movies": [{"movie": {"ids": {...}, "title": "...", "year": ...},
                    "progress": 3.0, "paused_at": "2026-..."}],
        "shows":  [{"show": {"ids": {...}, "title": "..."},
                    "episode": {"season": 2, "number": 1, "title": "..."},
                    "progress": 1.0, "paused_at": "2026-..."}]
      }

    Returns (movies_list, episodes_list) already normalised to our format.
    """
    data = _get('/scrobble')
    if not data or not isinstance(data, dict):
        return [], []

    movies   = []
    episodes = []

    for m in (data.get('movies') or []):
        try:
            mv   = m.get('movie') or m
            ids  = mv.get('ids') or {}
            pct  = m.get('progress', 0)
            if pct <= 0 or pct >= 85:
                continue
            movies.append({
                'type':          'movie',
                'imdb':          str(ids.get('imdb')  or ''),
                'tmdb':          str(ids.get('tmdb')  or '') if ids.get('tmdb')  else '',
                'tvdb':          '',
                'title':         mv.get('title', ''),
                'originaltitle': mv.get('title', ''),
                'tvshowtitle':   '',
                'year':          str(mv.get('year', '')),
                'season':        0,
                'episode':       0,
                'duration':      int((mv.get('runtime') or 0)) * 60,
                'progress':      str(round(float(pct), 2)),
                'paused_at':     m.get('paused_at', ''),
                'next':          '',
            })
        except Exception:
            pass

    for ep in (data.get('shows') or []):
        try:
            sh   = ep.get('show') or {}
            epd  = ep.get('episode') or {}
            ids  = sh.get('ids') or {}
            pct  = ep.get('progress', 0)
            if pct <= 0 or pct >= 85:
                continue
            episodes.append({
                'type':          'episode',
                'imdb':          str(ids.get('imdb')  or ''),
                'tmdb':          str(ids.get('tmdb')  or '') if ids.get('tmdb')  else '',
                'tvdb':          str(ids.get('tvdb')  or '') if ids.get('tvdb')  else '',
                'title':         epd.get('title', ''),
                'originaltitle': epd.get('title', ''),
                'tvshowtitle':   sh.get('title', ''),
                'year':          str(sh.get('year', '')),
                'season':        int(epd.get('season') or 0),
                'episode':       int(epd.get('number') or 0),
                'duration':      int((epd.get('runtime') or sh.get('runtime') or 0)) * 60,
                'progress':      str(round(float(pct), 2)),
                'paused_at':     ep.get('paused_at', ''),
                'next':          '',
            })
        except Exception:
            pass

    return movies, episodes


def _merge_progress(server_items: list, local_items: list) -> list:
    """
    Merge server and local DB items, de-duplicating by (imdb/tmdb, season, episode).
    Server items take precedence (more up-to-date progress).
    """
    seen = set()
    merged = []
    for item in server_items + local_items:
        key = (
            item.get('imdb') or item.get('tmdb') or item.get('tvdb'),
            item.get('season', 0),
            item.get('episode', 0),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return sorted(merged, key=lambda k: k.get('paused_at', ''), reverse=True)


def getContinueMovies() -> list:
    """
    Return in-progress movies.
    Primary source: MDBList server (GET /scrobble).
    Fallback/supplement: local service DB (progress.db).
    """
    server_movies, _ = _fetch_server_paused()
    local_movies     = _read_progress('movie')
    if server_movies:
        return _merge_progress(server_movies, local_movies)
    return local_movies


def getContinueEpisodes() -> list:
    """
    Return in-progress episodes.
    Primary source: MDBList server (GET /scrobble).
    Fallback/supplement: local service DB (progress.db).
    """
    _, server_eps = _fetch_server_paused()
    local_eps     = _read_progress('episode')
    if server_eps:
        return _merge_progress(server_eps, local_eps)
    return local_eps


# ---------------------------------------------------------------------------
# Public top lists filtered by mediatype
# ---------------------------------------------------------------------------

def getTopMovieLists() -> list:
    """Top public lists that contain movies."""
    all_lists = getTopLists()
    return [l for l in all_lists if l.get('mediatype') in ('movie', 'both', '')]


def getTopShowLists() -> list:
    """Top public lists that contain TV shows."""
    all_lists = getTopLists()
    return [l for l in all_lists if l.get('mediatype') in ('show', 'both', '')]


# ---------------------------------------------------------------------------
# Other user's public lists
# ---------------------------------------------------------------------------

def getUserListsByName(username: str) -> list:
    """
    Return public lists for any MDBList user by username.
    Endpoint: GET /lists/user/{username}?apikey=KEY
    """
    if not username:
        return []
    data = _get('/lists/user/%s' % username.strip())
    if isinstance(data, list):
        return data
    return []


def getListItemsFromUrl(mdblist_url: str) -> tuple:
    """
    Fetch items from a mdblist.com URL.
    Accepts:
      - https://mdblist.com/lists/{user}/{slug}/
      - https://mdblist.com/lists/{user}/{slug}/json/
    Returns (movies_list, shows_list) in our normalised format.
    Falls back to public JSON endpoint (no API key needed).
    """
    import re
    mdblist_url = mdblist_url.strip().rstrip('/')
    # Extract username/slug
    m = re.search(r'mdblist\.com/lists/([^/]+)/([^/]+)', mdblist_url)
    if not m:
        return [], []
    username, slug = m.group(1), m.group(2)

    # Try with API key first (returns the same /lists/{id}/items format)
    # We need the list ID — find it via the user's list index
    user_lists = getUserListsByName(username)
    list_id = None
    for lst in user_lists:
        if lst.get('slug') == slug:
            list_id = lst.get('id')
            break

    if list_id:
        return getListItems(list_id)

    # Fallback: public JSON endpoint (no API key, works for public lists)
    try:
        import requests as _req
        r = _req.get('https://mdblist.com/lists/%s/%s/json/' % (username, slug), timeout=15)
        r.raise_for_status()
        data = r.json()

        def _b(item):
            return {
                'title': item.get('title', ''),
                'year':  str(item.get('release_year') or item.get('year') or ''),
                'imdb':  str(item.get('imdb_id') or item.get('imdb') or ''),
                'tmdb':  str(item.get('tmdb_id') or item.get('tmdb') or '') if (item.get('tmdb_id') or item.get('tmdb')) else '',
                'tvdb':  str(item.get('tvdb_id') or item.get('tvdb') or '') if (item.get('tvdb_id') or item.get('tvdb')) else '',
                'rank':  item.get('rank', 9999),
            }

        if isinstance(data, list):
            movies = sorted([_b(i) for i in data if not i.get('tvdb_id')], key=lambda x: x['rank'])
            shows  = sorted([_b(i) for i in data if i.get('tvdb_id')],     key=lambda x: x['rank'])
            return movies, shows

        movies = sorted([_b(m) for m in (data.get('movies') or [])], key=lambda x: x['rank'])
        shows  = sorted([_b(s) for s in (data.get('shows')  or [])], key=lambda x: x['rank'])
        return movies, shows
    except Exception as exc:
        log_utils.log('getListItemsFromUrl failed: %s' % exc, level=log_utils.LOGWARNING)
        return [], []
