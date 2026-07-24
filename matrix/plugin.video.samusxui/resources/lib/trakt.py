# -*- coding: utf-8 -*-

import time
import json
import os
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

_addon = xbmcaddon.Addon('plugin.video.samusxui')
_BASE = 'https://api.trakt.tv'
_DEFAULT_CLIENT_ID = 'f0b9cd2de131c900f5bb03a0a5776342'


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _get(key):
    return _addon.getSetting(key) or ''


def _set(key, value):
    _addon.setSetting(key, str(value))


def _headers(auth=False):
    client_id = _get('trakt_client_id') or _DEFAULT_CLIENT_ID
    h = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': client_id,
    }
    if auth:
        token = _get('trakt_access_token')
        if token:
            h['Authorization'] = f'Bearer {token}'
    return h


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request_paged(endpoint, params=None, auth=False):
    """GET cu suport paginare; returnează (items, page_count)."""
    try:
        import requests
        url    = f'{_BASE}{endpoint}'
        kwargs = {'headers': _headers(auth), 'timeout': 15}
        if params:
            kwargs['params'] = params
        resp = requests.get(url, **kwargs)
        if resp.status_code in (200, 201):
            page_count = int(resp.headers.get('X-Pagination-Page-Count', 1))
            return resp.json() if resp.content else [], page_count
        xbmc.log(f"[Trakt] GET {endpoint} → {resp.status_code}", xbmc.LOGERROR)
        return [], 1
    except Exception as e:
        xbmc.log(f"[Trakt] _request_paged {endpoint}: {e}", xbmc.LOGERROR)
        return [], 1


def _request(method, endpoint, data=None, auth=False, params=None):
    try:
        import requests
        url = f'{_BASE}{endpoint}'
        kwargs = {'headers': _headers(auth), 'timeout': 15}
        if params:
            kwargs['params'] = params
        if data is not None:
            kwargs['json'] = data

        if method == 'GET':
            resp = requests.get(url, **kwargs)
        elif method == 'POST':
            resp = requests.post(url, **kwargs)
        else:
            return None

        if resp.status_code in (200, 201):
            return resp.json() if resp.content else True
        if resp.status_code == 204:
            return True
        xbmc.log(f"[Trakt] {method} {endpoint} → {resp.status_code}", xbmc.LOGERROR)
        return None
    except Exception as e:
        xbmc.log(f"[Trakt] request {endpoint}: {e}", xbmc.LOGERROR)
        return None


def rating_for_tmdb(tmdb_id, media='movie'):
    """Public Trakt rating for a TMDb id, unauthenticated."""
    trakt_type = 'show' if media in ('tv', 'tvshow', 'show') else 'movie'
    data = _request(
        'GET',
        f'/search/tmdb/{tmdb_id}',
        params={'type': trakt_type, 'extended': 'full'},
    )
    if not isinstance(data, list):
        return 0
    for item in data:
        payload = item.get(trakt_type) or {}
        try:
            return float(payload.get('rating') or 0)
        except Exception:
            return 0
    return 0


# ---------------------------------------------------------------------------
# Auth — device code flow
# ---------------------------------------------------------------------------

def is_authenticated():
    token = _get('trakt_access_token')
    expires = float(_get('trakt_expires_at') or 0)
    return bool(token) and time.time() < expires


def authenticate():
    """Start device code flow. Shows dialog with code and polls for token."""
    client_id = _get('trakt_client_id') or _DEFAULT_CLIENT_ID
    client_secret = _get('trakt_client_secret')

    if not client_secret:
        xbmcgui.Dialog().ok(
            'Trakt — Autentificare',
            'Completează [B]trakt_client_id[/B] și [B]trakt_client_secret[/B] în setările addon-ului.\n'
            'Creează o aplicație pe [B]trakt.tv/oauth/applications[/B].'
        )
        return False

    data = _request('POST', '/oauth/device/code', data={'client_id': client_id})
    if not data:
        xbmcgui.Dialog().notification('Trakt', 'Eroare la inițierea autentificării', xbmcgui.NOTIFICATION_ERROR)
        return False

    device_code = data['device_code']
    user_code = data['user_code']
    verify_url = data['verification_url']
    expires_in = data.get('expires_in', 600)
    interval = data.get('interval', 5)

    xbmcgui.Dialog().ok(
        'Trakt — Autentificare',
        f'Accesează [B]{verify_url}[/B] și introdu codul:\n\n'
        f'[B][COLOR yellow]{user_code}[/COLOR][/B]\n\n'
        f'(Codul expiră în {expires_in // 60} minute)'
    )

    pd = xbmcgui.DialogProgress()
    pd.create('Trakt', f'Aștept autentificare... cod: [B]{user_code}[/B]')

    deadline = time.time() + expires_in
    while time.time() < deadline:
        if pd.iscanceled():
            pd.close()
            return False
        elapsed = expires_in - int(deadline - time.time())
        pd.update(min(99, int(elapsed * 100 / expires_in)), f'Aștept autentificare... cod: {user_code}')
        time.sleep(interval)

        token_data = _request('POST', '/oauth/device/token', data={
            'code': device_code,
            'client_id': client_id,
            'client_secret': client_secret,
        })
        if token_data and isinstance(token_data, dict) and token_data.get('access_token'):
            pd.close()
            _set('trakt_access_token', token_data['access_token'])
            _set('trakt_refresh_token', token_data.get('refresh_token', ''))
            _set('trakt_expires_at', str(time.time() + token_data.get('expires_in', 7776000)))
            xbmcgui.Dialog().notification('Trakt', 'Autentificat cu succes!', xbmcgui.NOTIFICATION_INFO, 3000)
            return True

    pd.close()
    xbmcgui.Dialog().notification('Trakt', 'Autentificare expirată', xbmcgui.NOTIFICATION_WARNING)
    return False


def logout():
    _set('trakt_access_token', '')
    _set('trakt_refresh_token', '')
    _set('trakt_expires_at', '0')
    xbmcgui.Dialog().notification('Trakt', 'Deconectat', xbmcgui.NOTIFICATION_INFO, 3000)


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------

def get_trending_movies(page=1, limit=30):
    return _request('GET', '/movies/trending', params={'page': page, 'limit': limit, 'extended': 'full'})


def get_popular_movies(page=1, limit=30):
    return _request('GET', '/movies/popular', params={'page': page, 'limit': limit, 'extended': 'full'})


def get_most_watched_movies(period='weekly', page=1, limit=30):
    return _request('GET', f'/movies/watched/{period}', params={'page': page, 'limit': limit, 'extended': 'full'})


# ---------------------------------------------------------------------------
# Paginated variants — returnează (items, page_count)
# ---------------------------------------------------------------------------

def trending_movies_paged(page=1, limit=30):
    return _request_paged('/movies/trending',
                          {'page': page, 'limit': limit, 'extended': 'full'})


def trending_shows_paged(page=1, limit=30):
    return _request_paged('/shows/trending',
                          {'page': page, 'limit': limit, 'extended': 'full'})


def watchlist_movies_paged(page=1, limit=30):
    if not is_authenticated():
        return [], 1
    return _request_paged('/sync/watchlist/movies',
                          {'page': page, 'limit': limit, 'extended': 'full'},
                          auth=True)


def watchlist_shows_paged(page=1, limit=30):
    if not is_authenticated():
        return [], 1
    return _request_paged('/sync/watchlist/shows',
                          {'page': page, 'limit': limit, 'extended': 'full'},
                          auth=True)


def get_trending_shows(page=1, limit=30):
    return _request('GET', '/shows/trending', params={'page': page, 'limit': limit, 'extended': 'full'})


def get_popular_shows(page=1, limit=30):
    return _request('GET', '/shows/popular', params={'page': page, 'limit': limit, 'extended': 'full'})


def get_most_watched_shows(period='weekly', page=1, limit=30):
    return _request('GET', f'/shows/watched/{period}', params={'page': page, 'limit': limit, 'extended': 'full'})


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

def get_watchlist_movies(page=1, limit=30):
    if not is_authenticated():
        return None
    return _request('GET', '/sync/watchlist/movies', auth=True,
                    params={'page': page, 'limit': limit, 'extended': 'full'})


def get_watchlist_shows(page=1, limit=30):
    if not is_authenticated():
        return None
    return _request('GET', '/sync/watchlist/shows', auth=True,
                    params={'page': page, 'limit': limit, 'extended': 'full'})


def get_history_movies(page=1, limit=30):
    if not is_authenticated():
        return None
    return _request('GET', '/sync/history/movies', auth=True,
                    params={'page': page, 'limit': limit, 'extended': 'full'})


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_movie(item):
    """Extract movie dict with tmdb_id from a Trakt response item."""
    movie = item.get('movie') or item  # trending wraps in {'movie': {...}, 'watchers': N}
    ids = movie.get('ids', {})
    return {
        'tmdb_id': ids.get('tmdb'),
        'imdb_id': ids.get('imdb', ''),
        'title': movie.get('title', ''),
        'year': movie.get('year'),
        'overview': movie.get('overview', ''),
        'rating': movie.get('rating', 0),
        'poster_path': '',   # Trakt doesn't return poster; will use TMDb
        'backdrop_path': '',
        'media_type': 'movie',
    }


def normalize_show(item):
    """Extract show dict with tmdb_id from a Trakt response item."""
    show = item.get('show') or item
    ids = show.get('ids', {})
    return {
        'tmdb_id': ids.get('tmdb'),
        'imdb_id': ids.get('imdb', ''),
        'title': show.get('title', ''),
        'year': show.get('year'),
        'overview': show.get('overview', ''),
        'rating': show.get('rating', 0),
        'poster_path': '',
        'backdrop_path': '',
        'media_type': 'tvshow',
    }


# ---------------------------------------------------------------------------
# Scrobbling
# ---------------------------------------------------------------------------

def scrobble(action, media_type, tmdb_id, progress, season=None, episode=None):
    """
    action: 'start' | 'pause' | 'stop'
    progress: 0-100 float
    Trakt marks as watched automatically when stop progress > 80.
    """
    if not is_authenticated():
        return None
    if media_type == 'movie':
        body = {'movie': {'ids': {'tmdb': tmdb_id}}, 'progress': progress}
    else:
        body = {
            'show': {'ids': {'tmdb': tmdb_id}},
            'episode': {'season': season, 'number': episode},
            'progress': progress,
        }
    result = _request('POST', f'/scrobble/{action}', data=body, auth=True)
    xbmc.log(f'[Trakt] scrobble/{action} tmdb={tmdb_id} progress={progress:.1f}% → {result}', xbmc.LOGDEBUG)
    return result


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def add_to_watchlist(media_type, tmdb_id):
    if not is_authenticated():
        return None
    if media_type == 'movie':
        body = {'movies': [{'ids': {'tmdb': tmdb_id}}]}
    else:
        body = {'shows': [{'ids': {'tmdb': tmdb_id}}]}
    return _request('POST', '/sync/watchlist', data=body, auth=True)


def remove_from_watchlist(media_type, tmdb_id):
    if not is_authenticated():
        return None
    if media_type == 'movie':
        body = {'movies': [{'ids': {'tmdb': tmdb_id}}]}
    else:
        body = {'shows': [{'ids': {'tmdb': tmdb_id}}]}
    return _request('POST', '/sync/watchlist/remove', data=body, auth=True)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def get_recommendations_movies(limit=20):
    if not is_authenticated():
        return None
    return _request('GET', '/recommendations/movies', auth=True,
                    params={'limit': limit, 'extended': 'full'})


def get_recommendations_shows(limit=20):
    if not is_authenticated():
        return None
    return _request('GET', '/recommendations/shows', auth=True,
                    params={'limit': limit, 'extended': 'full'})


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

def search_lists(query, page=1, limit=20):
    return _request('GET', '/search/list', params={
        'query': query, 'page': page, 'limit': limit,
    })


def get_trending_lists(page=1, limit=20):
    return _request('GET', '/lists/trending', params={'page': page, 'limit': limit})


def get_popular_lists(page=1, limit=20):
    return _request('GET', '/lists/popular', params={'page': page, 'limit': limit})


def get_list_items(username, list_id, page=1, limit=30):
    return _request('GET', f'/users/{username}/lists/{list_id}/items',
                    params={'page': page, 'limit': limit, 'extended': 'full'},
                    auth=is_authenticated())


def list_items_paged(username, list_id, page=1, limit=30):
    return _request_paged(f'/users/{username}/lists/{list_id}/items',
                          {'page': page, 'limit': limit, 'extended': 'full'},
                          auth=is_authenticated())


def get_my_lists():
    if not is_authenticated():
        return None
    return _request('GET', '/users/me/lists', auth=True)


def search_movies_shows_paged(query, page=1, limit=30):
    return _request_paged('/search/movie,show',
                          {'query': query, 'page': page, 'limit': limit, 'extended': 'full'})


# ---------------------------------------------------------------------------
# List item cache
# ---------------------------------------------------------------------------

_MIN_REFRESH_AGE = 300  # nu re-fetch dacă cache-ul e mai nou de 5 minute


def _cache_dir():
    path = xbmcvfs.translatePath(
        'special://userdata/addon_data/plugin.video.samusxui/trakt_cache/'
    )
    os.makedirs(path, exist_ok=True)
    return path


def _cache_file(username, list_id, page):
    safe = f"{username}_{list_id}_p{page}".replace('/', '_')
    return os.path.join(_cache_dir(), f'list_{safe}.json')


def read_list_cache(username, list_id, page):
    try:
        path = _cache_file(username, list_id, page)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        xbmc.log(f'[Trakt] read_list_cache: {e}', xbmc.LOGWARNING)
        return None


def write_list_cache(username, list_id, page, items):
    try:
        path = _cache_file(username, list_id, page)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'items': items, 'cached_at': time.time()}, f)
    except Exception as e:
        xbmc.log(f'[Trakt] write_list_cache: {e}', xbmc.LOGWARNING)


def cache_needs_refresh(cached):
    """True dacă cache-ul e suficient de vechi pentru a merita un re-fetch."""
    if not cached:
        return True
    return time.time() - cached.get('cached_at', 0) > _MIN_REFRESH_AGE
