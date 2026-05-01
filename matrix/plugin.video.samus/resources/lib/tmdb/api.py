### resources/lib/tmdb/api.py
import json
import xbmcaddon
import xbmc
import requests

addon = xbmcaddon.Addon()
API_KEY = addon.getSetting('api_key')
REGION_VALUES = ['RO', 'US', 'GB', 'DE', 'FR', 'All']
LANGUAGE = addon.getSetting('language') or 'ro'

BASE_URL = 'https://api.themoviedb.org/3/'

# TTL-uri cache
TTL_LIST    = 24 * 3600        # 24h — pagini de listare (popular, trending, genuri)
TTL_DETAILS = 7  * 24 * 3600  # 7 zile — detalii film/serial
TTL_SHORT   = 6  * 3600       # 6h — similar, recomandate

def _sync_language():
    """Șterge cache-ul TMDb dacă limba s-a schimbat față de ultima rulare."""
    from resources.lib import db
    stored = db.cache_get('samus:meta:language', ttl=float('inf'))
    if stored != LANGUAGE:
        db.cache_clear()
        db.cache_set('samus:meta:language', LANGUAGE)

_sync_language()


def tmdb_request(endpoint, params={}):
    region_index = int(addon.getSetting('provider_region') or 0)
    region = REGION_VALUES[region_index]

    params['api_key'] = API_KEY
    if 'language' not in params:
        params['language'] = LANGUAGE
    if addon.getSettingBool('use_adult'):
        params['include_adult'] = 'true'

    if region != 'All' and 'watch_region' not in params:
        params['watch_region'] = region

    try:
        url = BASE_URL + endpoint
        xbmc.log(f'[TMDb Request] {url} | {params}', xbmc.LOGDEBUG)
        response = requests.get(url, params=params, timeout=10)
        if response.ok:
            return response.json()
        else:
            xbmc.log(f'[TMDb Error] HTTP {response.status_code}: {response.text}', xbmc.LOGERROR)
            return {}
    except Exception as e:
        xbmc.log(f'[TMDb Exception] {e}', xbmc.LOGERROR)
        return {}


def tmdb_cached(endpoint, params=None, ttl=TTL_LIST):
    """tmdb_request cu cache SQLite. Cacheul folosește endpoint + params ca cheie."""
    from resources.lib import db
    p = dict(params or {})
    p.pop('api_key', None)
    if 'language' not in p:
        p['language'] = LANGUAGE
    key = f"tmdb:{endpoint}:{json.dumps(p, sort_keys=True)}"
    cached = db.cache_get(key, ttl)
    if cached is not None:
        xbmc.log(f'[TMDb Cache HIT] {endpoint}', xbmc.LOGDEBUG)
        return cached
    data = tmdb_request(endpoint, p)
    if data:
        db.cache_set(key, data)
    return data


def get_external_ids(tmdb_id, media_type='movie'):
    """Returnează imdb_id printr-un endpoint dedicat, lightweight."""
    endpoint = f'{media_type}/{tmdb_id}/external_ids'
    data = tmdb_cached(endpoint, {}, ttl=TTL_DETAILS)
    return data.get('imdb_id')


_genre_cache = {}

def get_genre_map(media_type='movie'):
    """Returnează {genre_id: genre_name} cu cache în memorie."""
    if media_type in _genre_cache:
        return _genre_cache[media_type]
    endpoint = 'genre/movie/list' if media_type == 'movie' else 'genre/tv/list'
    data = tmdb_cached(endpoint, {}, ttl=TTL_DETAILS)
    mapping = {g['id']: g['name'] for g in data.get('genres', [])}
    _genre_cache[media_type] = mapping
    return mapping
