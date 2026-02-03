# resources/lib/tmdb_api.py
# -*- coding: utf-8 -*-
import requests
import xbmc
import xbmcaddon
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from .db import db

ADDON = xbmcaddon.Addon()
TMDB_API_KEY = ADDON.getSetting("tmdb_api")
TMDB_LANG = ADDON.getSetting("tmdb_language") or "en-US"
BASE_URL = "https://api.themoviedb.org/3"

# --- IMAGE SETTINGS ---
IMG_POSTER = "https://image.tmdb.org/t/p/w500"
IMG_BACKDROP = "https://image.tmdb.org/t/p/original"

# --- REUSABLE SESSION (BIG IMPROVEMENT) ---
# Reusing HTTP connections is MUCH faster than creating new ones with each request
_session = None
_request_cache = {}  # In-memory cache for repeated requests
_cache_max_size = 100

def get_session():
    """Returns a reusable HTTP session with OPTIMIZED connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        # ✅ OPTIMIZATION: Larger pool and retry with backoff
        from requests.adapters import Retry
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=30,  # ⬆️ Increased from 20 to 30
            pool_maxsize=30,      # ⬆️ Increased from 20 to 30
            max_retries=retry_strategy,
            pool_block=False
        )
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
        # ✅ OPTIMIZATION: Adds gzip compression
        _session.headers.update({
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    return _session

def _get_cached_request(url, params):
    """✅ NEW: In-memory cache for repeated requests."""
    cache_key = f"{url}_{str(sorted(params.items()))}"
    if cache_key in _request_cache:
        return _request_cache[cache_key]
    return None

def _set_cached_request(url, params, data):
    """✅ NEW: Saves request in memory cache."""
    global _request_cache
    cache_key = f"{url}_{str(sorted(params.items()))}"
    # Limit cache size
    if len(_request_cache) >= _cache_max_size:
        # Removes 20% of oldest items (simple FIFO)
        keys_to_remove = list(_request_cache.keys())[:_cache_max_size // 5]
        for k in keys_to_remove:
            del _request_cache[k]
    _request_cache[cache_key] = data

# --- GENRE MAPS (Unified) ---
GENRES_MAP = {
    'movie': {28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History", 27: "Terror", 10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Science fiction", 10770: "Cinema TV", 53: "Suspense", 10752: "War", 37: "Western"},
    'tv': {10759: 'Action and Adventure', 16: 'Animation', 35: 'Comedy', 80: 'Crime', 99: 'Documentary', 18: 'Drama', 10751: 'Family', 10762: 'Kids', 9648: 'Mystery', 10763: 'News', 10764: 'reality show', 10765: 'Science Fiction and Fantasy', 10766: 'Novel', 10767: 'Talk Show', 10768: 'War and Politics', 37: 'Western'}
}

# --- INTERNAL FUNCTIONS (Helpers) ---

def _normalize_item(item, media_type, extra=None):
    """Standardizes fields for films and series in one place."""
    is_movie = media_type == 'movie'
    extra = extra or {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'collection': ''}
    
    g_ids = item.get('genre_ids', [])
    g_map = GENRES_MAP.get('movie' if is_movie else 'tv', {})
    g_names = [g_map.get(gid) for gid in g_ids if gid in g_map]

    backdrop = item.get('backdrop_path')
    
    # Extracts information from the collection (for movies only)
    collection_name = extra.get('collection', '')
    if not collection_name and is_movie:
        collection_info = item.get('belongs_to_collection')
        if collection_info:
            collection_name = collection_info.get('name', '')
        
    # If you don't have a collection yet, check if the title suggests one (e.g. "Harry Potter and...")
    # But TMDB is generally good at this. The important thing is to make sure it is not None.
    if collection_name is None:
        collection_name = ''
    
    return {
        'tmdb_id': item.get('id'),
        'imdb_id': extra.get('imdb_id'),
        'title': item.get('title' if is_movie else 'name'),
        'original_title': item.get('original_title' if is_movie else 'original_name'),
        'genres': g_names or [g.get('name') for g in item.get('genres', [])],
        'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
        'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'fanart': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'clearlogo': extra.get('clearlogo'),
        'providers': extra.get('providers'),
        'synopsis': item.get('overview', ''),
        'year': (item.get('release_date' if is_movie else 'first_air_date') or '0000')[:4],
        'rating': item.get('vote_average', 0.0),
        'runtime': extra.get('runtime', 0),
        'collection': collection_name,
        'media_type': 'movie' if is_movie else 'tvshow'
    }

def _fetch_tmdb_extra(item, media_type):
    """Searches logos, providers and external IDs in a single hit (for Threads)."""
    tmdb_id = item.get('id')
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "append_to_response": "external_ids,images,watch/providers",
        "include_image_language": "en,ro,pt,null"
    }
    try:
        # USES REUSABLE SESSION + OPTIMIZED TIMEOUT
        res = get_session().get(url, params=params, timeout=2.5).json()
        logos = res.get('images', {}).get('logos', [])
        clearlogo_path = ''
        if logos:
            # 1. Try to find PT-BR
            en_logo = next((l for l in logos if l.get('iso_639_1') == 'en'), None)
            clearlogo_path = en_logo['file_path'] if en_logo else logos[0]['file_path']
        watch = res.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        
        # Extracts information from the collection (for movies only)
        collection_name = ''
        if media_type == 'movie':
            collection_info = res.get('belongs_to_collection')
            collection_name = collection_info.get('name') if collection_info else ''
        
        return {
            'imdb_id': res.get('external_ids', {}).get('imdb_id', ''),
            'clearlogo': f"{IMG_POSTER}{clearlogo_path}" if clearlogo_path else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'runtime': res.get('runtime', 0) if media_type == 'movie' else 0,
            'collection': collection_name
        }
    except Exception as e:
        xbmc.log(f"[TMDB] Error extra {tmdb_id}: {str(e)}", xbmc.LOGDEBUG)
        return {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'collection': ''}

def _fetch_extras_batch(items, media_type):
    """CRITICAL OPTIMIZATION: Search for extras in parallel with better control.
    Uses ThreadPoolExecutor more efficiently."""
    if not items:
        return []
    
    # ✅ OPTIMIZATION: Dynamic workers based on list size
    max_workers = min(8, max(3, len(items) // 4))  # Between 3 and 8 workers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks keeping order
        future_to_index = {
            executor.submit(_fetch_tmdb_extra, item, media_type): idx 
            for idx, item in enumerate(items)
        }
        
        # Initialize list with None to maintain order
        results = [None] * len(items)
        
        # Collects results as they complete (faster)
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result(timeout=5)
            except Exception as e:
                xbmc.log(f"[TMDB] Timeout/error in extra: {e}", xbmc.LOGDEBUG)
                results[idx] = {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}
        
        # Fill in any missing results
        for i in range(len(results)):
            if results[i] is None:
                results[i] = {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}
        
        return results

# --- PUBLIC LISTING FUNCTIONS ---

def fetch_trending(media_type='movie', page=1):
    """Generic function for trending films or series - OPTIMIZED."""
    cache_key = f"trending_{media_type}_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: 
        return cached

    url = f"{BASE_URL}/trending/{media_type}/day"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        # USES SESSION + OPTIMIZED TIMEOUT
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])

        # DEBUG: Check if the IDs are correct
        xbmc.log(f"[TMDB DEBUG] Trending IDs: {[item.get('id') for item in data]}", xbmc.LOGDEBUG)
        
        # OPTIMIZATION: Only search for extras if really necessary
        extra_results = _fetch_extras_batch(data, media_type)
        
        # DEBUG: Check extra IDs
        xbmc.log(f"[TMDB DEBUG] Extras IDs: {[extra.get('imdb_id', 'NO_ID') for extra in extra_results]}", xbmc.LOGDEBUG)

        # Normalizes the final result
        results = []
        for item, extra in zip(data, extra_results):
            # Security check
            if item.get('id') and extra.get('imdb_id'):
                # You can add verification here
                pass
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)
            
            # DEBUG: Log to identify problems
            xbmc.log(f"[TMDB DEBUG] Item {item.get('id')} -> {normalized.get('title')}", xbmc.LOGDEBUG)

        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Trending {media_type}: {str(e)}", xbmc.LOGERROR)
        return []

# Wrappers to maintain compatibility
def fetch_trending_movies(page=1): 
    return fetch_trending('movie', page)

def fetch_trending_tvshows(page=1): 
    return fetch_trending('tv', page)

def fetch_popular_movies(page=1):
    """Search popular movies."""
    cache_key = f"popular_movies_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/movie/popular"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG, "region": "US"}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Popular Movies Error: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_top_rated_movies(page=1):
    """Search for top-rated movies."""
    cache_key = f"top_rated_movies_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/movie/top_rated"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG, "region": "US"}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Top Rated Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_now_playing_movies(page=1):
    """Search for films showing in cinemas."""
    cache_key = f"now_playing_movies_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/movie/now_playing"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG, "region": "US"}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Now Playing Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_popular_tvshows(page=1):
    """Search for popular series."""
    cache_key = f"popular_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/tv/popular"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Popular TV Error: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_top_rated_tvshows(page=1):
    """Search for better rated series."""
    cache_key = f"top_rated_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/tv/top_rated"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Top Rated TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_airing_today_tvshows(page=1):
    """Search for series that air today."""
    cache_key = f"airing_today_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    url = f"{BASE_URL}/tv/airing_today"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Airing Today TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_on_the_air_tvshows(page=1):
    """Search for series that are on air (this week)."""
    cache_key = f"on_the_air_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    url = f"{BASE_URL}/tv/on_the_air"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error On The Air TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_upcoming_movies(page=1):
    """Search for soon-to-be-released movies using the official upcoming endpoint."""
    cache_key = f"upcoming_movies_v2_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    # The /movie/upcoming endpoint is more reliable for what the user wants
    url = f"{BASE_URL}/movie/upcoming"
    params = {
        "api_key": TMDB_API_KEY, 
        "page": page, 
        "language": TMDB_LANG, 
        "region": "US"
    }
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        
        # If it fails or comes up empty, try via discover as a fallback
        if not data:
            from datetime import datetime, timedelta
            now = datetime.now().strftime('%Y-%m-%d')
            future = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            return fetch_discover('movie', page=page, 
                                 **{'primary_release_date.gte': now,
                                    'primary_release_date.lte': future,
                                    'sort_by': 'popularity.desc'})

        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Upcoming Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_upcoming_tvshows(page=1):
    """Search for series that are about to premiere or with new episodes."""
    cache_key = f"upcoming_tvshows_v2_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    # For TV, we use discover filtering by series that premiere from today
    from datetime import datetime, timedelta
    now = datetime.now().strftime('%Y-%m-%d')
    future = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
    
    try:
        # TV Shows Coming Soon, Sorted by Popularity to Avoid Junk
        results = fetch_discover('tv', page=page, 
                                **{'first_air_date.gte': now,
                                   'first_air_date.lte': future,
                                   'sort_by': 'popularity.desc'})
        
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Upcoming TV: {str(e)}", xbmc.LOGERROR)
        return []

def search_tmdb(query, page=1):
    """Unified search (Movies and TV Shows) - OPTIMIZED."""
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY, 
        "query": query, 
        "language": TMDB_LANG, 
        "page": page,
        "include_adult": "false"
    }
    
    try:
        # USE SESSION
        r = get_session().get(url, params=params, timeout=5)
        data = r.json().get('results', [])
        
        # Filter only what interests you
        filtered = [i for i in data if i.get('media_type') in ['movie', 'tv']]

        # CRITICAL: For searching, extras are less important
        # You can even disable it if you want maximum speed
        extra_results = _fetch_extras_batch(filtered[:10], None)  # Limits to first 10
        extra_results += [{'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}] * (len(filtered) - 10)

        return [
            _normalize_item(item, item['media_type'], extra) 
            for item, extra in zip(filtered, extra_results)
        ]
        
    except Exception as e:
        xbmc.log(f"[TMDB SEARCH] Error: {str(e)}", xbmc.LOGERROR)
        return []

# --- LOCAL POPULARITY FUNCTIONS ---

def update_local_popularity():
    """Synchronizes popularity - OPTIMIZED."""
    _sync_popularity('movie', db.get_all_movie_ids_set(), db.update_popularity_bulk)
    _sync_popularity('tv', db.get_all_tvshow_ids_set(), db.update_tv_popularity_bulk)

def _sync_popularity(media_type, local_ids, update_func):
    """Auxiliary logic to download popularity - OPTIMIZED."""
    if not local_ids: 
        return
    
    popular_tmdb = []
    
    # OPTIMIZATION: Parallel page search
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for p in range(1, 4):
            url = f"{BASE_URL}/{media_type}/popular"
            params = {"api_key": TMDB_API_KEY, "page": p}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                popular_tmdb.extend(r.json().get('results', []))
            except:
                continue

    # Filters only the ones we have at the local bank
    updates = [
        {'tmdb_id': i['id'], 'popularity': i['popularity']} 
        for i in popular_tmdb if i['id'] in local_ids
    ]

    if updates:
        update_func(updates)
        xbmc.log(f"[Cinebox] Popularity of {len(updates)} {media_type}s updated.", xbmc.LOGINFO)

# --- DETAIL FUNCTIONS (INDEXER/DB) ---

def get_movie_details(tmdb_id):
    """Search complete details of a movie - OPTIMIZED."""
    url = f"{BASE_URL}/movie/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "append_to_response": "external_ids,images,credits,watch/providers",
        "include_image_language": "en,ro,pt,null"
    }
    
    try:
        # USE SESSION
        r = get_session().get(url, params=params, timeout=8)
        item = r.json()
        
        logos = item.get('images', {}).get('logos', [])
        clearlogo_path = ''
        if logos:
            en_logo = next((l for l in logos if l.get('iso_639_1') == 'en'), None)
            clearlogo_path = en_logo['file_path'] if en_logo else logos[0]['file_path']
        watch = item.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        
        # Extracts information from the collection
        collection_info = item.get('belongs_to_collection')
        collection_name = collection_info.get('name') if collection_info else ''
        
        return {
            'tmdb_id': item.get('id'),
            'imdb_id': item.get('external_ids', {}).get('imdb_id'),
            'title': item.get('title'),
            'original_title': item.get('original_title'),
            'year': item.get('release_date', '0000')[:4],
            'rating': item.get('vote_average', 0.0),
            'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}" if item.get('backdrop_path') else '',
            'synopsis': item.get('overview', ''),
            'runtime': item.get('runtime', 0),
            'popularity': item.get('popularity', 0.0),
            'revenue': item.get('revenue', 0),
            'collection': collection_name,
            'genres': [g.get('name') for g in item.get('genres', [])],
            'clearlogo': f"{IMG_POSTER}{clearlogo_path}" if clearlogo_path else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'popularity_updated': None,
            'cast': [c.get('name') for c in item.get('credits', {}).get('cast', [])[:5]],
            'directors': [c.get('name') for c in item.get('credits', {}).get('crew', []) if c.get('job') == 'Director']
        }
    except Exception as e:
        xbmc.log(f"[TMDB API] Movie details error {tmdb_id}: {str(e)}", xbmc.LOGERROR)
        return None

def _enrich_seasons_with_images(seasons, tmdb_id):
    """Simplified: Just ensures that the basic data exists."""
    if not seasons:
        return []
    
    for season in seasons:
        if 'poster_path' in season and season['poster_path']:
            season['poster'] = f"{IMG_POSTER}{season['poster_path']}"
        # TMDB does not provide backdrops for individual seasons
        # The backdrop will be defined by the series on tvshows.py
    return seasons

def fetch_show_details(tmdb_id):
    """Fetches complete details of a series - OPTIMIZED."""
    if not tmdb_id: 
        return None
        
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "append_to_response": "external_ids,images,credits",
        "include_image_language": "en,ro,pt,null"
    }
    
    try:
        # USE SESSION
        response = get_session().get(url, params=params, timeout=8)
        response.raise_for_status()
        show_data = response.json()
        
        seasons_raw = show_data.get('seasons', [])
        logos = show_data.get('images', {}).get('logos', [])
        clearlogo_path = ''
        if logos:
            en_logo = next((l for l in logos if l.get('iso_639_1') == 'en'), None)
            clearlogo_path = en_logo['file_path'] if en_logo else logos[0]['file_path']
        
        return {
            'tmdb_id': show_data.get('id'),
            'clearlogo': f"{IMG_POSTER}{clearlogo_path}" if clearlogo_path else '',
            'imdb_id': show_data.get('external_ids', {}).get('imdb_id'),
            'title': show_data.get('name'),
            'original_title': show_data.get('original_name'),
            'year': show_data.get('first_air_date', '')[:4],
            'poster': f"{IMG_POSTER}{show_data.get('poster_path')}" if show_data.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{show_data.get('backdrop_path')}" if show_data.get('backdrop_path') else '',
            'synopsis': show_data.get('overview'),
            'popularity': show_data.get('popularity'),
            'rating': show_data.get('vote_average'),
            'certification': show_data.get('content_ratings', {}).get('results', [{}])[0].get('rating', 'N/A'),
            'genres': [g.get('name') for g in show_data.get('genres', [])], 
            'number_of_seasons': show_data.get('number_of_seasons', 0),
            'number_of_episodes': show_data.get('number_of_episodes', 0),
            'status': show_data.get('status'),
            'tagline': show_data.get('tagline'),
            'seasons_data': show_data.get('seasons', []),
            'cast': [c.get('name') for c in show_data.get('credits', {}).get('cast', [])[:5]],
            'created_by': [c.get('name') for c in show_data.get('created_by', [])]
        }
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Failed to fetch details from the series {tmdb_id}: {e}", xbmc.LOGERROR)
        return None

def fetch_tvshows_list(list_type, page=1):
    """Search simple series lists - OPTIMIZED."""
    endpoint_map = {
        'popular': 'tv/popular',
        'top_rated': 'tv/top_rated',
        'on_the_air': 'tv/on_the_air',
        'trending': 'trending/tv/week' 
    }
    endpoint = endpoint_map.get(list_type, 'tv/popular')
    url = f"{BASE_URL}/{endpoint}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
    
    try:
        # USE SESSION
        response = get_session().get(url, params=params, timeout=5)
        data = response.json()
        
        normalized_shows = []
        for show in data.get('results', []):
            g_ids = show.get('genre_ids', [])
            g_names = [GENRES_MAP['tv'].get(gid, 'Unknown') for gid in g_ids]
            
            normalized_shows.append({
                'tmdb_id': show.get('id'),
                'title': show.get('name'),
                'original_title': show.get('original_name'),
                'year': show.get('first_air_date', '')[:4],
                'poster': f"{IMG_POSTER}{show.get('poster_path')}" if show.get('poster_path') else '',
                'backdrop': f"{IMG_BACKDROP}{show.get('backdrop_path')}" if show.get('backdrop_path') else '',
                'synopsis': show.get('overview'),
                'popularity': show.get('popularity'),
                'rating': show.get('vote_average'),
                'genres': g_names
            })
        return normalized_shows
        
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Failed to fetch list {list_type}: {e}", xbmc.LOGERROR)
        return []

@lru_cache(maxsize=128)
def get_collection_art(collection_name):
    """Search for collection art - OPTIMIZED with CACHE."""
    url = f"{BASE_URL}/search/collection"
    params = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        results = r.json().get('results', [])
        if results:
            poster = results[0].get('poster_path')
            backdrop = results[0].get('backdrop_path')
            return {
                'poster': f"{IMG_BACKDROP}{poster}" if poster else '',
                'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else ''
            }
    except:
        pass
    return None

def fetch_popular_movies_pages(pages=5):
    """Search popular pages - OPTIMIZED."""
    all_movies = []
    
    # OPTIMIZATION: Parallel search
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for page in range(1, pages + 1):
            url = f"{BASE_URL}/movie/popular"
            params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                data = r.json().get('results', [])
                for item in data:
                    all_movies.append({
                        'tmdb_id': item.get('id'),
                        'title': item.get('title'),
                        'original_title': item.get('original_title'),
                        'year': item.get('release_date', '0000')[:4],
                        'rating': item.get('vote_average'),
                        'poster': f"{IMG_POSTER}{item.get('poster_path')}",
                        'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}",
                        'synopsis': item.get('overview'),
                        'popularity': item.get('popularity'),
                        'popularity_updated': None
                    })
            except:
                continue
                
    return all_movies

def get_tvshow_seasons(tmdb_id):
    """Search seasons of a series - OPTIMIZED."""
    if not tmdb_id:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        seasons = data.get('seasons', [])
        
        formatted_seasons = []
        for season in seasons:
            formatted_seasons.append({
                'season_number': season.get('season_number', 0),
                'name': season.get('name', ''),
                'overview': season.get('overview', ''),
                'poster_path': season.get('poster_path', ''),
                'air_date': season.get('air_date', ''),
                'episode_count': season.get('episode_count', 0),
                'vote_average': season.get('vote_average', 0.0)
            })
        
        return formatted_seasons
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Error fetching seasons {tmdb_id}: {e}", xbmc.LOGERROR)
        return []

def get_season_episodes(tmdb_id, season_number):
    """Search episodes from a season - OPTIMIZED."""
    if not tmdb_id or season_number is None:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}/season/{season_number}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        episodes = data.get('episodes', [])
        
        formatted_episodes = []
        for episode in episodes:
            formatted_episodes.append({
                'episode_number': episode.get('episode_number', 0),
                'name': episode.get('name', ''),
                'overview': episode.get('overview', ''),
                'still_path': episode.get('still_path', ''),
                'air_date': episode.get('air_date', ''),
                'vote_average': episode.get('vote_average', 0.0),
                'runtime': episode.get('runtime', 0)
            })
        
        return formatted_episodes
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Error fetching episodes {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []
def fetch_anime_discover(media_type='tv', page=1, **kwargs):
    """Specific function for Discover de Animes using the keyword 210024."""
    kwargs['with_keywords'] = '210024'
    return fetch_discover(media_type, page, **kwargs)

def fetch_discover(media_type='movie', page=1, **kwargs):
    """Generic function for Discover (Genres, Years, etc.) - OPTIMIZED."""
    cache_key = f"discover_{media_type}_p{page}_{json.dumps(kwargs, sort_keys=True)}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: 
        return cached

    url = f"{BASE_URL}/discover/{media_type}"
    params = {
        "api_key": TMDB_API_KEY, 
        "page": page, 
        "language": TMDB_LANG,
        "sort_by": "popularity.desc",
        "include_adult": "false"
    }
    params.update(kwargs)
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        
        extra_results = _fetch_extras_batch(data, media_type)
        
        results = []
        for item, extra in zip(data, extra_results):
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)

        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Error Discover {media_type}: {str(e)}", xbmc.LOGERROR)
        return []

def get_genres_list(media_type='movie'):
    """Returns the official TMDB genre list."""
    url = f"{BASE_URL}/genre/{media_type}/list"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    try:
        r = get_session().get(url, params=params, timeout=3)
        return r.json().get('genres', [])
    except:
        return []

def get_collection_art(collection_name):
    """Search for artwork from a collection by name in TMDB."""
    url = f"{BASE_URL}/search/collection"
    params = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    try:
        r = get_session().get(url, params=params, timeout=3)
        results = r.json().get('results', [])
        if results:
            col = results[0]
            return {
                'poster': f"{IMG_POSTER}{col.get('poster_path')}" if col.get('poster_path') else '',
                'backdrop': f"{IMG_BACKDROP}{col.get('backdrop_path')}" if col.get('backdrop_path') else ''
            }
    except:
        pass
    return None

def get_collection_movies(collection_name):
    """Search all films in a collection by name in TMDB."""
    # 1. Search for the collection ID
    url_search = f"{BASE_URL}/search/collection"
    params_search = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url_search, params=params_search, timeout=5)
        results = r.json().get('results', [])
        if not results:
            return []
        
        collection_id = results[0].get('id')
        if not collection_id:
            return []
            
        # 2. Fetch the collection details (which contains the movies)
        url_details = f"{BASE_URL}/collection/{collection_id}"
        params_details = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
        
        r_details = get_session().get(url_details, params=params_details, timeout=5)
        collection_data = r_details.json()
        parts = collection_data.get('parts', [])
        
        if not parts:
            return []
            
        # 3. Search for extras for each film in the collection (optional, but recommended to have imdb_id)
        extra_results = _fetch_extras_batch(parts, 'movie')
        
        results = []
        for item, extra in zip(parts, extra_results):
            normalized = _normalize_item(item, 'movie', extra)
            # Ensures the collection name is correct
            normalized['collection'] = collection_name
            results.append(normalized)
            
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Error fetching movies from the collection {collection_name}: {e}", xbmc.LOGERROR)
        return []

def fetch_popular_collections(page=1):
    """Massively searches popular collections.
    Explore multiple pages of popular movies to extract collections."""
    page = int(page)
    collections = {}
    
    # For each page requested by the user, we will look at 4 TMDB pages
    # We increased it to 4 to ensure we have enough items after filtering
    start_tmdb_page = ((page - 1) * 4) + 1
    end_tmdb_page = start_tmdb_page + 4
    
    try:
        # 1. Search movies from multiple pages in parallel
        all_movies = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for p in range(start_tmdb_page, end_tmdb_page):
                url_pop = f"{BASE_URL}/movie/popular"
                params_pop = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": p}
                futures.append(executor.submit(get_session().get, url_pop, params=params_pop, timeout=5))
            
            for future in as_completed(futures):
                try:
                    res = future.result().json()
                    all_movies.extend(res.get('results', []))
                except:
                    continue

        if not all_movies:
            return []

        # 2. Extract unique movie IDs
        unique_movies = {m['id']: m for m in all_movies if m.get('id')}.values()
        
        # 3. Batch search extras to find out which ones belong to collections
        movie_list = list(unique_movies)[:100] # Increased to 100
        extra_results = _fetch_extras_batch(movie_list, 'movie')
        
        for item, extra in zip(movie_list, extra_results):
            col_name = extra.get('collection')
            if col_name:
                # Strict normalization to avoid duplicates
                norm_name = col_name.strip().lower()
                if norm_name not in collections:
                    # Search for art from the collection (with internal cache from get_collection_art)
                    art = get_collection_art(col_name)
                    collections[norm_name] = {
                        'collection': col_name,
                        'poster': art['poster'] if art else '',
                        'backdrop': art['backdrop'] if art else ''
                    }
        
        # Sort by name
        sorted_collections = sorted(collections.values(), key=lambda x: x['collection'])
        
        # ✅ GLOBAL FILTERING OF DUPLICATES BETWEEN PAGES
        # We use a temporary cache in the database to know what has already been displayed
        from .db.db import db_instance as db
        final_collections = []
        
        # Extra normalization to remove common words that cause false duplicates
        def super_norm(n):
            import re
            n = n.lower()
            n = re.sub(r' - collection| - saga| collection| saga| collection| anthology| trilogy', '', n)
            return n.strip()

        for col in sorted_collections:
            name = col['collection']
            snorm = super_norm(name)
            
            # Checks if it has already been shown in this session (using the database cache as a flag)
            cache_key = f"col_shown_{snorm}"
            if page == 1:
                # On page 1, we always show and mark
                db.save_collection_meta(cache_key, "1", "")
                final_collections.append(col)
            else:
                # On other pages, we only show it if it is not in the cache
                if not db.get_collection_meta(cache_key):
                    db.save_collection_meta(cache_key, "1", "")
                    final_collections.append(col)
                
        return final_collections

    except Exception as e:
        xbmc.log(f"[TMDB API] Massive error fetching collections: {e}", xbmc.LOGERROR)
        return []

def update_local_popularity():
    return True