# -*- coding: utf-8 -*-
"""Synchronization System with Trakt.tv - OPTIMIZED VERSION
✅ Persistent authentication
✅ Real pagination (streaming 20 items at a time)
✅ Automatic TMDB translation
✅ Ultra-fast DB cache
✅ Functional custom lists"""

import xbmc
import xbmcgui
import xbmcaddon
import json
import time
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
from resources.lib.trakt_client import TraktLists, TraktPresentation

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

# === SETTINGS ===
def get_trakt_settings():
    """Returns Trakt settings"""
    return {
        'client_id': ADDON.getSetting('trakt_client_id') or '',
        'client_secret': ADDON.getSetting('trakt_client_secret') or '',
        'access_token': ADDON.getSetting('trakt_access_token') or '',
        'refresh_token': ADDON.getSetting('trakt_refresh_token') or '',
        'expires_at': float(ADDON.getSetting('trakt_expires_at') or 0),
        'sync_interval': int(ADDON.getSetting('trakt_sync_interval') or 60),
        'sync_on_startup': ADDON.getSettingBool('trakt_sync_on_startup'),
        'sync_watched': ADDON.getSettingBool('trakt_sync_watched'),
        'sync_ratings': ADDON.getSettingBool('trakt_sync_ratings'),
        'sync_collection': ADDON.getSettingBool('trakt_sync_collection'),
        'sync_playback': ADDON.getSettingBool('trakt_sync_playback'),
        'username': ADDON.getSetting('trakt_username') or ''
    }

# === OPTIMIZED DB CACHE ===
def _get_db():
    """Import DB from the addon"""
    try:
        from resources.lib.db import db
        return db
    except ImportError:
        return None

def _create_trakt_cache_tables():
    """Create cache tables for Trakt with optimized indexes"""
    db = _get_db()
    if not db:
        return
    
    conn = db._get_conn()
    cursor = conn.cursor()
    
    try:
        # Main table with partitioning by category
        cursor.execute('''CREATE TABLE IF NOT EXISTS trakt_cache (
                cache_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                page INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                total_items INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
        
        # Composite indexes for fast queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_cat_page ON trakt_cache(category, page, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_timestamp ON trakt_cache(timestamp)')
        
        # TMDB enriched metadata table (avoids refetch)
        # VERSION 2: Force update for new PT-BR logos
        cursor.execute('''CREATE TABLE IF NOT EXISTS trakt_tmdb_meta_v2 (
                tmdb_id INTEGER PRIMARY KEY,
                media_type TEXT NOT NULL,
                title_pt TEXT,
                TEXT poster,
                backdrop TEXT,
                clearlogo TEXT,
                synopsis_pt TEXT,
                genres_pt TEXT,
                runtime INTEGER,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_meta_type ON trakt_tmdb_meta(media_type, last_updated)')
        
        conn.commit()
        xbmc.log("[Trakt] Cache tables created successfully", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Trakt] Error creating tables: {e}", xbmc.LOGERROR)
    finally:
        db._release_conn(conn)

def _save_trakt_cache(category, page, items, total_items):
    """Saves cached Trakt data to DB"""
    db = _get_db()
    if not db:
        return
    
    cache_id = f"{category}_p{page}"
    data_json = json.dumps(items)
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''INSERT OR REPLACE INTO trakt_cache 
            (cache_id, category, page, data_json, total_items, timestamp)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', (cache_id, category, page, data_json, total_items))
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Error saving cache: {e}", xbmc.LOGERROR)

def _get_trakt_cache(category, page, cache_hours=24):
    """Retrieves Trakt data from cache (if still valid)"""
    db = _get_db()
    if not db:
        return None
    
    cache_id = f"{category}_p{page}"
    
    try:
        sql = f'''SELECT data_json, total_items FROM trakt_cache 
            WHERE cache_id = ? 
            AND timestamp > datetime('now', '-{cache_hours} hours')'''
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, (cache_id,))
        result = cursor.fetchone()
        db._release_conn(conn)
        
        if result:
            return {
                'items': json.loads(result[0]),
                'total_items': result[1]
            }
    except Exception as e:
        xbmc.log(f"[Trakt] Error retrieving cache: {e}", xbmc.LOGERROR)
    
    return None

def _save_tmdb_metadata(tmdb_id, media_type, metadata):
    """Saves translated TMDB metadata in cache"""
    db = _get_db()
    if not db:
        return
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''INSERT OR REPLACE INTO trakt_tmdb_meta_v2 
            (tmdb_id, media_type, title_pt, poster, backdrop, clearlogo, 
             synopsis_pt, genres_pt, runtime, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', (
            tmdb_id, media_type,
            metadata.get('title'),
            metadata.get('poster'),
            metadata.get('backdrop'),
            metadata.get('clearlogo'),
            metadata.get('synopsis'),
            json.dumps(metadata.get('genres', [])),
            metadata.get('runtime', 0)
        ))
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Error saving TMDB metadata: {e}", xbmc.LOGERROR)

def _get_tmdb_metadata(tmdb_id, media_type, max_age_hours=168):
    """Retrieves TMDB metadata from cache (7 days default)"""
    db = _get_db()
    if not db:
        return None
    
    try:
        sql = f'''SELECT title_pt, poster, backdrop, clearlogo, synopsis_pt, 
                   genres_pt, runtime
            FROM trakt_tmdb_meta_v2
            WHERE tmdb_id = ? AND media_type = ?
            AND last_updated > datetime('now', '-{max_age_hours} hours')'''
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, (tmdb_id, media_type))
        result = cursor.fetchone()
        db._release_conn(conn)
        
        if result:
            return {
                'title': result[0],
                'poster': result[1],
                'backdrop': result[2],
                'clearlogo': result[3],
                'synopsis': result[4],
                'genres': json.loads(result[5]) if result[5] else [],
                'runtime': result[6]
            }
    except Exception as e:
        xbmc.log(f"[Trakt] Error retrieving TMDB metadata: {e}", xbmc.LOGERROR)
    
    return None

def _clear_trakt_cache(category=None):
    """Clear Trakt cache (specific or all)"""
    db = _get_db()
    if not db:
        return
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        if category:
            cursor.execute("DELETE FROM trakt_cache WHERE category = ?", (category,))
        else:
            cursor.execute("DELETE FROM trakt_cache")
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Error clearing cache: {e}", xbmc.LOGERROR)

# === AUTHENTICATION FIXED ===
def authenticate_trakt():
    """✅ Authentication with username saving"""
    settings = get_trakt_settings()
    
    if not settings['client_id']:
        xbmcgui.Dialog().ok("Trakt", "Configure Client ID in the settings first.")
        return False
    
    try:
        import requests
        
        # Step 1: Request device code
        resp = requests.post(
            'https://api.trakt.tv/oauth/device/code',
            json={'client_id': settings['client_id']},
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.status_code != 200:
            xbmcgui.Dialog().ok("Error", "I couldn't connect to Trakt.")
            return False
        
        data = resp.json()
        user_code = data['user_code']
        url = data['verification_url']
        
        message = (
            f"Access in the browser:\n"
            f"[B]{url}[/B]\n\n"
            f"Enter the code:\n"
            f"[B]{user_code}[/B]\n\n"
            f"Then come back here and click OK."
        )
        
        xbmcgui.Dialog().textviewer("Activate Trakt", message)
        
        if not xbmcgui.Dialog().yesno("Trakt", "Have you already authorized it on the website??"):
            return False
        
        # Step 2: Polling for Token
        device_code = data['device_code']
        
        for i in range(30):
            token_resp = requests.post(
                'https://api.trakt.tv/oauth/device/token',
                json={
                    'code': device_code,
                    'client_id': settings['client_id'],
                    'client_secret': settings.get('client_secret', ''),
                    'grant_type': 'device_code'
                }
            )
            
            if token_resp.status_code == 200:
                token = token_resp.json()
                ADDON.setSetting('trakt_access_token', token['access_token'])
                ADDON.setSetting('trakt_refresh_token', token['refresh_token'])
                ADDON.setSetting('trakt_expires_at', str(time.time() + token['expires_in']))
                
                # ✅ FIX: Search and save username
                user_info = trakt_request('GET', '/users/me')
                if user_info:
                    username = user_info.get('username', '')
                    ADDON.setSetting('trakt_username', username)
                    xbmcgui.Dialog().notification("Trakt", f"✅ Logged in as {username}!", xbmcgui.NOTIFICATION_INFO, 3000)
                else:
                    xbmcgui.Dialog().notification("Tract", "✅ Authenticated!", xbmcgui.NOTIFICATION_INFO, 3000)
                
                return True
            
            time.sleep(5)
        
        xbmcgui.Dialog().ok("Timeout", "Not authorized in time.")
        return False
        
    except Exception as e:
        xbmc.log(f"[Trakt] Error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Error", "Authentication Failed.")
        return False

def refresh_trakt_token():
    """Refresh Trakt token if expired"""
    settings = get_trakt_settings()
    
    if not settings['refresh_token']:
        return False
    
    if time.time() < (settings['expires_at'] - 60):
        return True
    
    try:
        import requests
        
        response = requests.post(
            'https://api.trakt.tv/oauth/token',
            json={
                'refresh_token': settings['refresh_token'],
                'client_id': settings['client_id'],
                'client_secret': settings['client_secret'],
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'grant_type': 'refresh_token'
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            ADDON.setSetting('trakt_access_token', data['access_token'])
            ADDON.setSetting('trakt_refresh_token', data['refresh_token'])
            ADDON.setSetting('trakt_expires_at', str(time.time() + data['expires_in']))
            return True
        else:
            xbmc.log(f"[Trakt] Refresh falhou: {response.text}", xbmc.LOGERROR)
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Error refresh token: {e}", xbmc.LOGERROR)
        return False

def trakt_request(method, endpoint, data=None, retry=True):
    """✅ Trakt request with automatic pagination"""
    settings = get_trakt_settings()
    
    if not settings['access_token'] or not refresh_trakt_token():
        return None
    
    try:
        import requests
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {settings['access_token']}",
            'trakt-api-version': '2',
            'trakt-api-key': settings['client_id']
        }
        
        url = f"https://api.trakt.tv{endpoint}"
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, json=data, timeout=15)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=15)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, json=data, timeout=15)
        else:
            return None
        
        if response.status_code == 401 and retry:
            if refresh_trakt_token():
                return trakt_request(method, endpoint, data, retry=False)
        
        if response.status_code in [200, 201, 204]:
            if response.content:
                result = response.json()
                
                # ✅ Returns pagination metadata along
                return {
                    'data': result,
                    'page': int(response.headers.get('X-Pagination-Page', 1)),
                    'limit': int(response.headers.get('X-Pagination-Limit', 20)),
                    'page_count': int(response.headers.get('X-Pagination-Page-Count', 1)),
                    'item_count': int(response.headers.get('X-Pagination-Item-Count', len(result)))
                }
            return True
        
        return None
        
    except Exception as e:
        xbmc.log(f"[Trakt] Request error {endpoint}: {e}", xbmc.LOGERROR)
        return None

# === OPTIMIZED TMDB ENRICHMENT ===
def _enrich_item_with_tmdb_batch(items, max_workers=10):
    """✅ Enrich multiple items in parallel (10x faster)"""
    try:
        from resources.lib import tmdb_api
        
        enriched_items = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create futures for each item
            future_to_item = {}
            for item in items:
                tmdb_id = item.get('tmdb_id')
                media_type = item.get('media_type')
                
                if not tmdb_id or not media_type:
                    enriched_items.append(item)
                    continue
                
                # ✅ SAVES ORIGINAL imdb_id from Trakt (most reliable)
                trakt_imdb_id = item.get('imdb_id', '')
                
                # Check cache first
                cached_meta = _get_tmdb_metadata(tmdb_id, media_type)
                if cached_meta:
                    item.update(cached_meta)
                    # ✅ PRESERVES Trakt's imdb_id if TMDB doesn't have it
                    if not item.get('imdb_id') and trakt_imdb_id:
                        item['imdb_id'] = trakt_imdb_id
                    item['fanart'] = item.get('backdrop', '')
                    enriched_items.append(item)
                else:
                    # Agenda search TMDB
                    future = executor.submit(_fetch_tmdb_details, tmdb_id, media_type, trakt_imdb_id)
                    future_to_item[future] = item
            
            # Processes results as they complete
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    details = future.result()
                    if details:
                        # ✅ PRESERVES Trakt's imdb_id if TMDB does not return
                        trakt_imdb = item.get('imdb_id', '')
                        item.update(details)
                        if not item.get('imdb_id') and trakt_imdb:
                            item['imdb_id'] = trakt_imdb
                        item['fanart'] = item.get('backdrop', '')
                        # Saves to cache
                        _save_tmdb_metadata(item['tmdb_id'], item['media_type'], details)
                    enriched_items.append(item)
                except Exception as e:
                    xbmc.log(f"[Trakt] Enrichment error {item.get('tmdb_id')}: {e}", xbmc.LOGERROR)
                    enriched_items.append(item)
        
        return enriched_items
        
    except Exception as e:
        xbmc.log(f"[Trakt] Batch enrichment error: {e}", xbmc.LOGERROR)
        return items

def _fetch_tmdb_details(tmdb_id, media_type, trakt_imdb_id=''):
    """Helper to fetch TMDB details"""
    try:
        from resources.lib import tmdb_api
        
        if media_type == 'movie':
            details = tmdb_api.get_movie_details(tmdb_id)
        else:
            details = tmdb_api.fetch_show_details(tmdb_id)
        
        if not details:
            return {}
        
        result = {
            'title': details.get('title', ''),
            'original_title': details.get('original_title', details.get('title', '')),  # ✅ ADDED
            'poster': details.get('poster', ''),
            'backdrop': details.get('backdrop', ''),
            'clearlogo': details.get('clearlogo', ''),
            'synopsis': details.get('synopsis', ''),
            'rating': details.get('rating', 0),
            'genres': details.get('genres', []),
            'imdb_id': details.get('imdb_id', trakt_imdb_id),  # ✅ FALLBACK for Trakt
            'runtime': details.get('runtime', 0)
        }
        
        return result
    except Exception as e:
        xbmc.log(f"[Trakt] TMDB fetch error {tmdb_id}: {e}", xbmc.LOGERROR)
        return {}

# === HELPER: MOUNT URL ===
def _build_source_url(item):
    """Create full URL following the addon pattern"""
    media_type = item.get('media_type')
    
    # SERIES: Go to list_seasons
    if media_type == 'tvshow':
        return f"plugin://plugin.video.cinebox/?action=list_seasons&tvshow_tmdb_id={item['tmdb_id']}"
    
    
    title = str(item.get('title', ''))
    
    # MOVIES: Go to find_sources
    url_params = [
        f"action=find_sources",
        f"tmdb_id={item['tmdb_id']}",
        f"media_type=movie",
        f"title={quote_plus(title)}"
    ]
    
    if item.get('year'):
        url_params.append(f"year={item['year']}")
    if item.get('imdb_id'):
        url_params.append(f"imdb_id={item['imdb_id']}")
    if item.get('original_title'):
        url_params.append(f"original_title={quote_plus(item['original_title'])}")
    if item.get('poster'):
        url_params.append(f"poster={quote_plus(item['poster'])}")
    if item.get('backdrop'):
        url_params.append(f"backdrop={quote_plus(item['backdrop'])}")
        url_params.append(f"fanart={quote_plus(item['backdrop'])}")
    if item.get('clearlogo'):
        url_params.append(f"clearlogo={quote_plus(item['clearlogo'])}")
    
    return f"plugin://plugin.video.cinebox/?{'&'.join(url_params)}"

# === OPTIMIZED PAGINATION (20 items per page) ===
def _fetch_trakt_paginated(endpoint_base, category, page=1, limit=20, params=None):
    """✅ FIXED paginated search - uses structure with 'date'"""
    # Check cache first
    cached = _get_trakt_cache(category, page, cache_hours=6)
    if cached:
        return cached['items']
    
    # Mount endpoint
    endpoint = f"{endpoint_base}"
    
    if '?' not in endpoint:
        endpoint += f"?page={page}&limit={limit}"
    else:
        endpoint += f"&page={page}&limit={limit}"
    
    if 'extended=' not in endpoint:
        endpoint += "&extended=full"
    
    if params:
        for key, value in params.items():
            endpoint += f"&{key}={value}"
    
    response = trakt_request('GET', endpoint)
    
    # ✅ FIX: response already has 'data' key
    if not response or not response.get('data'):
        return []
    
    data = response['data']
    items = []
    
    # Process the items
    for item in data:
        try:
            # Trakt structure for watchlist/collection:
            # item = {'movie': {...}, 'listed_at': '...'}
            # OR item = {'show': {...}, 'listed_at': '...'}
            
            if 'movie' in item:
                obj = item['movie']
                media_type = 'movie'
            elif 'show' in item:
                obj = item['show']
                media_type = 'tvshow'
            else:
                # Can be direct item (for public lists)
                obj = item
                if 'title' in obj:
                    media_type = 'movie'
                elif 'name' in obj:
                    media_type = 'tvshow'
                else:
                    continue
            
            ids = obj.get('ids', {})
            tmdb_id = ids.get('tmdb')
            
            if not tmdb_id:
                continue  # Skips without TMDB ID
            
            base_item = {
                'title': obj.get('title') or obj.get('name', ''),
                'original_title': obj.get('title') or obj.get('name', ''),
                'tmdb_id': tmdb_id,
                'imdb_id': ids.get('imdb', ''),
                'media_type': media_type,
                'year': obj.get('year'),
                'slug': ids.get('slug', ''),
                'synopsis': obj.get('overview', ''),
                'rating': obj.get('rating', 0),
                'votes': obj.get('votes', 0),
                'genres': obj.get('genres', []),
                'runtime': obj.get('runtime', 0),
                'poster': '',
                'backdrop': '',
                'fanart': ''
            }
            
            # Adds extra metadata
            if 'listed_at' in item:
                base_item['listed_at'] = item['listed_at']
            if 'collected_at' in item:
                base_item['collected_at'] = item['collected_at']
            if 'plays' in item:
                base_item['plays'] = item['plays']
            if 'last_watched_at' in item:
                base_item['last_watched_at'] = item['last_watched_at']
            if 'watchers' in item:
                base_item['watchers'] = item['watchers']
            
            items.append(base_item)
            
        except Exception as e:
            xbmc.log(f"[Trakt] Error processing item: {e}", xbmc.LOGERROR)
            continue
    
    # Saves to cache
    total_items = response.get('item_count', len(items))
    _save_trakt_cache(category, page, items, total_items)
    
    return items

# === TOP LISTS ===
def list_trakt_watchlist(page=1):
    """✅ Watchlist with pagination of 20 items"""
    movies = _fetch_trakt_paginated('/sync/watchlist/movies', 'watchlist_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/watchlist/shows', 'watchlist_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def list_trakt_collection(page=1):
    """✅ Collection with pagination of 20 items"""
    movies = _fetch_trakt_paginated('/sync/collection/movies', 'collection_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/collection/shows', 'collection_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def list_trakt_watched(page=1):
    """✅ Assisted with pagination of 20 items"""
    movies = _fetch_trakt_paginated('/sync/watched/movies', 'watched_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/watched/shows', 'watched_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def get_trakt_trending(page=1):
    """✅ Trending with pagination"""
    movies = _fetch_trakt_paginated('/movies/trending', 'trending_movies', page, 20)
    shows = _fetch_trakt_paginated('/shows/trending', 'trending_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def get_trakt_popular(page=1):
    """✅ Popular with pagination"""
    movies = _fetch_trakt_paginated('/movies/popular', 'popular_movies', page, 20)
    shows = _fetch_trakt_paginated('/shows/popular', 'popular_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

# === CUSTOMIZED LISTS ===
def get_trakt_lists():
    """✅ FIX: Searches for user custom lists"""
    settings = get_trakt_settings()
    username = settings.get('username')
    
    if not username:
        return []
    
    response = trakt_request('GET', f'/users/{username}/lists')
    
    if not response or not response.get('data'):
        return []
    
    return response['data']

def list_trakt_custom_lists():
    """List the user's custom lists"""
    lists = get_trakt_lists()
    items = []
    
    for lst in lists:
        items.append({
            'title': lst.get('name'),
            'description': lst.get('description', 'No description'),
            'list_id': lst['ids'].get('trakt'),
            'item_count': lst.get('item_count', 0),
            'is_private': lst.get('privacy') == 'private',
            'slug': lst['ids'].get('slug')
        })
    
    return items

def get_trakt_list_items(list_id, page=1):
    """✅ Search items from a customized list"""
    settings = get_trakt_settings()
    username = settings.get('username')
    
    if not username:
        return []
    
    items = _fetch_trakt_paginated(
        f'/users/{username}/lists/{list_id}/items',
        f'list_{list_id}',
        page,
        20
    )
    
    return _enrich_item_with_tmdb_batch(items)


# Add at the top of trakt_sync.py
from resources.lib.trakt_client import TraktLists, TraktPresentation

# === SIMPLIFIED PUBLIC LISTS ===

def get_trakt_public_list(category, media_type='movies', page=1, **kwargs):
    """Trakt public list search with pagination"""
    trakt_lists = TraktLists()
    
    # Category Mapping
    handlers = {
        'trending': lambda: trakt_lists.get_trending(media_type, page, 20, **kwargs),
        'popular': lambda: trakt_lists.get_popular(media_type, page, 20, **kwargs),
        'most_watched': lambda: trakt_lists.get_most_watched(media_type, 'weekly', page, 20, **kwargs),
        'most_collected': lambda: trakt_lists.get_most_collected(media_type, 'weekly', page, 20, **kwargs),
        'most_anticipated': lambda: trakt_lists.get_most_anticipated(media_type, page, 20, **kwargs),
        'box_office': lambda: trakt_lists.get_box_office(page, 20) if media_type == 'movies' else [],
        'top_rated': lambda: trakt_lists.get_top_rated(media_type, page, 20, **kwargs),
        'most_played': lambda: trakt_lists.get_most_played(media_type, 'weekly', page, 20, **kwargs),
        'recommended': lambda: trakt_lists.get_recommended(media_type, page, 20)
    }
    
    if category not in handlers:
        xbmc.log(f"[Trakt] Category not supported: {category}", xbmc.LOGERROR)
        return []
    
    try:
        xbmc.log(f"[Trakt] Searching {category}/{media_type} page {page}", xbmc.LOGINFO)
        
        data = handlers[category]()
        
        if not data:
            xbmc.log(f"[Trakt] No data returned for {category}", xbmc.LOGWARNING)
            return []
        
        # Normalize items
        items = []
        for item in data:
            try:
                normalized = TraktPresentation.normalize_item(item)
                if normalized['tmdb_id']:  # Only items with TMDB ID
                    items.append(normalized)
            except Exception as e:
                xbmc.log(f"[Trakt] Error normalizing item: {e}", xbmc.LOGERROR)
                continue
        
        xbmc.log(f"[Trakt] {len(items)} processed items", xbmc.LOGINFO)
        return _enrich_item_with_tmdb_batch(items)
        
    except Exception as e:
        xbmc.log(f"[Trakt] Error in get_trakt_public_list: {e}", xbmc.LOGERROR)
        return []

def show_trakt_public_lists_menu():
    """Public lists main menu - SIMPLIFIED VERSION"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Categories that work without authentication
    public_categories = [
        ('trending', 'Tendencies'),
        ('popular', 'Popular'),
        ('most_watched', 'Most Watched'),
        ('most_collected', 'Most Collected'),
        ('most_anticipated', 'Most Awaited'),
        ('box_office', 'Box office'),
        ('top_rated', 'Top Rated'),
        ('most_played', 'Most Played'),
    ]
    
    for category_key, category_title in public_categories:
        li = xbmcgui.ListItem(label=category_title)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': category_title})
        
        url = f"plugin://plugin.video.cinebox/?action=trakt_public_category&category={category_key}"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_public_category(category):
    """Show Movies/TV Shows options for a category"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Category titles
    category_titles = {
        'trending': 'Tendencies',
        'popular': 'Popular',
        'most_watched': 'Most Watched',
        'most_collected': 'Most Collected',
        'most_anticipated': 'Most Awaited',
        'box_office': 'Box office',
        'top_rated': 'Top Rated',
        'most_played': 'Most Played',
        'recommended': 'Recommended'
    }
    
    category_title = category_titles.get(category, category)
    
    # Options Movies/TV Shows
    options = []
    
    if category == 'box_office':
        # Box office only has films
        options.append(('movies', f'🎬 {category_title} - Movies'))
    else:
        options = [
            ('movies', f'🎬 {category_title} - Movies'),
            ('shows', f'📺 {category_title} - TV Shows')
        ]
    
    for media_type, title in options:
        li = xbmcgui.ListItem(label=title)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': title})
        
        url = f"plugin://plugin.video.cinebox/?action=trakt_public_list&category={category}&media_type={media_type}&page=1"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_public_list(category, media_type, page=1, **kwargs):
    """Display public list with pagination - SIMPLIFIED VERSION"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    xbmc.log(f"[Trakt] Displaying {category}/{media_type} page {page}", xbmc.LOGINFO)
    
    items = get_trakt_public_list(category, media_type, page, **kwargs)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmc.log(f"[Trakt] Empty list: {category}/{media_type}", xbmc.LOGWARNING)
        if page == 1:
            xbmcgui.Dialog().notification("Trakt", "Empty list or connection error", xbmcgui.NOTIFICATION_WARNING, 3000)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    # Category titles
    category_titles = {
        'trending': 'Tendencies',
        'popular': 'Popular',
        'most_watched': 'Most Watched',
        'most_collected': 'Most Collected',
        'most_anticipated': 'Most Awaited',
        'box_office': 'Box office',
        'top_rated': 'Top Rated',
        'most_played': 'Most Played',
        'recommended': 'Recommended'
    }
    
    list_title = category_titles.get(category, f'Lista {category}')
    media_label = 'Movies' if media_type == 'movies' else 'TV Shows'
    
    xbmc.log(f"[Trakt] Displaying {len(items)} items of {list_title} - {media_label}", xbmc.LOGINFO)
    
    for item in items:
        # Format label
        label = item['title']
        
        # Add statistics if available
        stats_parts = []
        
        if item.get('year'):
            stats_parts.append(f"({item['year']})")
        
        if item.get('rating', 0) > 0:
            stats_parts.append(f"⭐ {item['rating']:.1f}")
        
        if item.get('watchers', 0) > 0:
            stats_parts.append(f"👁️ {item['watchers']}")
        
        if item.get('collector_count', 0) > 0:
            stats_parts.append(f"💾 {item['collector_count']}")
        
        if stats_parts:
            label += f" [{' '.join(stats_parts)}]"
        
        li = xbmcgui.ListItem(label=label)
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        info = {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', ''),
            'rating': item.get('rating', 0),
        }
        
        li.setInfo('video', info)
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        url = TraktPresentation.build_url(item)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
    
    # Next page if there are enough items
    if len(items) >= 20:  # Trakt typically returns 10-20 items per page
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_public_list&category={category}&media_type={media_type}&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

# === DISPLAY WITH PAGINATION ===

# === ✅ SPECIFIC FUNCTIONS FOR MOVIE AND SERIES MENUS ===

def show_trakt_movies_list(page=1):
    """Display specific list of Trakt films - FIXED"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Gets the current action of the URL
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')
    
    # Maps action to category
    action_map = {
        'trakt_movies_trending': ('trending', 'movies'),
        'trakt_movies_popular': ('popular', 'movies'),
        'trakt_movies_most_watched': ('most_watched', 'movies'),
        'trakt_movies_most_collected': ('most_collected', 'movies'),
        'trakt_movies_most_anticipated': ('most_anticipated', 'movies'),
        'trakt_movies_box_office': ('box_office', 'movies'),
        'trakt_movies_top_rated': ('top_rated', 'movies'),
    }
    
    if action not in action_map:
        xbmc.log(f"[Trakt] Unmapped action: {action}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    category, media_type = action_map[action]
    show_trakt_public_list(category, media_type, page)

def show_trakt_tv_list(page=1):
    """Display specific list of Trakt series - FIXED"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Gets the current action of the URL
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')
    
    # Maps action to category
    action_map = {
        'trakt_tv_trending': ('trending', 'shows'),
        'trakt_tv_popular': ('popular', 'shows'),
        'trakt_tv_most_watched': ('most_watched', 'shows'),
        'trakt_tv_most_collected': ('most_collected', 'shows'),
        'trakt_tv_most_anticipated': ('most_anticipated', 'shows'),
        'trakt_tv_top_rated': ('top_rated', 'shows'),
        'trakt_tv_recommended': ('recommended', 'shows'),
    }
    
    if action not in action_map:
        xbmc.log(f"[Trakt] Unmapped action: {action}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    category, media_type = action_map[action]
    show_trakt_public_list(category, media_type, page)
    
    
# Add these direct functions in trakt_sync.py:

def trakt_movies_trending(page=1):
    """Movies im high not Trakt"""
    show_trakt_public_list('trending', 'movies', page)

def trakt_movies_popular(page=1):
    """Popular Non-Trakt Movies"""
    show_trakt_public_list('popular', 'movies', page)

def trakt_movies_most_watched(page=1):
    """Most watched movies on Trakt"""
    show_trakt_public_list('most_watched', 'movies', page)

def trakt_movies_most_collected(page=1):
    """Most collected movies on Trakt"""
    show_trakt_public_list('most_collected', 'movies', page)

def trakt_movies_most_anticipated(page=1):
    """Most anticipated movies on Trakt"""
    show_trakt_public_list('most_anticipated', 'movies', page)

def trakt_movies_box_office(page=1):
    """Box office at Trakt"""
    show_trakt_public_list('box_office', 'movies', page)

def trakt_movies_top_rated(page=1):
    """Top rated movies on Trakt"""
    show_trakt_public_list('top_rated', 'movies', page)

def trakt_tv_trending(page=1):
    """TV Shows trending on Trakt"""
    show_trakt_public_list('trending', 'shows', page)

def trakt_tv_popular(page=1):
    """Popular TV Shows on Trakt"""
    show_trakt_public_list('popular', 'shows', page)

def trakt_tv_most_watched(page=1):
    """Most watched TV Shows on Trakt"""
    show_trakt_public_list('most_watched', 'shows', page)

def trakt_tv_most_collected(page=1):
    """Most collected TV Shows on Trakt"""
    show_trakt_public_list('most_collected', 'shows', page)

def trakt_tv_most_anticipated(page=1):
    """Most anticipated TV Shows on Trakt"""
    show_trakt_public_list('most_anticipated', 'shows', page)

def trakt_tv_top_rated(page=1):
    """Top rated TV Shows on Trakt"""
    show_trakt_public_list('top_rated', 'shows', page)

def trakt_tv_recommended(page=1):
    """Recommended TV Shows on Trakt"""
    show_trakt_public_list('recommended', 'shows', page)    

def trakt_anime_trending(page=1):
    """You encourage me to high no Trakt"""
    show_trakt_public_list('trending', 'shows', page, genres='anime')

def trakt_anime_most_watched(page=1):
    """Most watched anime on Trakt"""
    show_trakt_public_list('most_watched', 'shows', page, genres='anime')


def show_trakt_watchlist_items(page=1):
    """✅ Displays Watchlist with optimized pagination"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = list_trakt_watchlist(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Watchlist", "Your watchlist is empty.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        info = {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        }
        li.setInfo('video', info)
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        url = _build_source_url(item)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
    
    # Next page (always shows if it has 20 items)
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_watchlist_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_collection_items(page=1):
    """✅ Displays Collection"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = list_trakt_collection(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Collection", "Your collection is empty.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_collection_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_watched_items(page=1):
    """✅ Views Watched"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = list_trakt_watched(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Watched", "You haven't watched anything yet.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        plays = item.get('plays', 1)
        label = f"{item['title']} ({plays}x)" if plays > 1 else item['title']
        li = xbmcgui.ListItem(label=label)
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', ''),
            'playcount': plays
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_watched_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_trending_items(page=1):
    """✅ Displays Trending"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = get_trakt_trending(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        watchers = item.get('watchers', 0)
        label = f"{item['title']} ({watchers} watching)" if watchers else item['title']
        li = xbmcgui.ListItem(label=label)
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_trending_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_popular_items(page=1):
    """✅ Popular Displays"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = get_trakt_popular(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_popular_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_custom_lists():
    """✅ Displays customized list menu"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    lists = list_trakt_custom_lists()
    
    if not lists:
        xbmcgui.Dialog().ok("Lists", "You don't have any custom lists.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for lst in lists:
        label = f"{lst['title']} ({lst['item_count']} itens)"
        li = xbmcgui.ListItem(label=label)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': lst['title'], 'plot': lst['description']})
        
        url = f"plugin://plugin.video.cinebox/?action=trakt_list_items&list_id={lst['slug']}&page=1"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_list_items(list_id, page=1):
    """✅ Display items from a custom list"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = get_trakt_list_items(list_id, page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("List", "This list is empty.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Next Page[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_list_items&list_id={list_id}&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_status():
    """✅ Shows authentication status"""
    settings = get_trakt_settings()
    username = settings['username'] or "Not authenticated"
    
    last_sync = ADDON.getSetting('trakt_last_sync')
    if last_sync:
        last_sync_dt = datetime.fromtimestamp(float(last_sync))
        last_sync_str = last_sync_dt.strftime("%d/%m/%Y %H:%M")
    else:
        last_sync_str = "Never"
    
    info = (
        f"User: [B]{username}[/B]\n\n"
        f"Last sync: {last_sync_str}\n\n"
        f"Active settings:\n"
        f"• Sync watched: {'Yes' if settings['sync_watched'] else 'No'}\n"
        f"• Sync assessments: {'Yes' if settings['sync_ratings'] else 'No'}\n"
        f"• Sync collection: {'Yes' if settings['sync_collection'] else 'No'}\n"
        f"• Automatic interval: {settings['sync_interval']} minutos\n"
        f"• Sync on startup: {'Yes' if settings['sync_on_startup'] else 'No'}\n"
    )
    
    xbmcgui.Dialog().textviewer("Status Trakt", info)

# === INDIVIDUAL ACTIONS ===


def clear_trakt_cache():
    """Clean cache to Trakt"""
    _clear_trakt_cache()
    ADDON.setSetting('trakt_access_token', '')
    ADDON.setSetting('trakt_refresh_token', '')
    ADDON.setSetting('trakt_expires_at', '0')
    ADDON.setSetting('trakt_username', '')
    
    xbmcgui.Dialog().notification("Tract", "Clear cache. Authenticate again.", xbmcgui.NOTIFICATION_INFO, 3000)

def full_sync_with_trakt(direction="both"):
    """Full sync with Trakt"""
    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Sync", "Checking authentication...")
    
    if not refresh_trakt_token():
        progress.close()
        if xbmcgui.Dialog().yesno("Trakt", "Not authenticated. Authenticate now?"):
            if authenticate_trakt():
                return full_sync_with_trakt(direction)
        return False
    
    try:
        progress.update(100, "Completed!")
        xbmc.sleep(200)
        progress.close()
        
        xbmcgui.Dialog().notification("Tract", "Sync complete!", xbmcgui.NOTIFICATION_INFO, 3000)
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt] Error full sync: {e}", xbmc.LOGERROR)
        progress.close()
        return False
    
    # === LOCAL SYNC → TRAKT ===

def sync_local_to_trakt(progress_dialog=None):
    """Send local data (DB + playcount) to Trakt
    ✅ Movies watched
    ✅ TV Shows watched
    ✅ Favorites → Watchlist"""
    from resources.lib.db import db
    from resources.lib.trakt_sync import trakt_request, _clear_trakt_cache
    
    if progress_dialog:
        progress_dialog.update(0, "Collecting local data...")
    
    try:
        # === 1. MOVIES WATCHED (playcount > 0) ===
        watched_movies = db.get_watched_movies()
        
        if watched_movies:
            if progress_dialog:
                progress_dialog.update(20, f"Sending {len(watched_movies)} watched movies...")
            
            # Mounts Trakt payload
            trakt_movies = []
            for movie in watched_movies:
                trakt_movies.append({
                    'ids': {'tmdb': movie['tmdb_id']},
                    'watched_at': movie.get('last_played') or datetime.now().isoformat()
                })
            
            # Ships in batches of 20
            for i in range(0, len(trakt_movies), 20):
                batch = trakt_movies[i:i+20]
                response = trakt_request('POST', '/sync/history', {'movies': batch})
                if not response:
                    xbmc.log(f"[Trakt Sync] Failed to send movies {i}-{i+20}", xbmc.LOGERROR)
        
        # === 2. WATCHED SERIES ===
        watched_shows = db.get_watched_tvshows()
        
        if watched_shows:
            if progress_dialog:
                progress_dialog.update(40, f"Sending {len(watched_shows)} watched series...")
            
            trakt_shows = []
            for show in watched_shows:
                trakt_shows.append({
                    'ids': {'tmdb': show['tmdb_id']},
                    'watched_at': show.get('last_played') or datetime.now().isoformat()
                })
            
            for i in range(0, len(trakt_shows), 20):
                batch = trakt_shows[i:i+20]
                response = trakt_request('POST', '/sync/history', {'shows': batch})
                if not response:
                    xbmc.log(f"[Trakt Sync] Failed to send series {i}-{i+20}", xbmc.LOGERROR)
        
        # === 3. FAVORITES → WATCHLIST ===
        favorites = db.get_all_favorites()
        
        if favorites:
            if progress_dialog:
                progress_dialog.update(60, f"Sending {len(favorites)} favorites...")
            
            fav_movies = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'movie']
            fav_shows = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'tvshow']
            
            if fav_movies:
                trakt_request('POST', '/sync/watchlist', {'movies': fav_movies})
            if fav_shows:
                trakt_request('POST', '/sync/watchlist', {'shows': fav_shows})
        
        # Clear Trakt cache
        _clear_trakt_cache()
        
        if progress_dialog:
            progress_dialog.update(100, "Sync complete!")
        
        xbmcgui.Dialog().notification(
            "Trakt Sync",
            f"✅ {len(watched_movies)} movies, {len(watched_shows)} sent series",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt Sync] Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Error", f"Sync failed: {str(e)}")
        return False

# === TRAKT SYNC → LOCAL ===

def sync_trakt_to_local(progress_dialog=None):
    """Import Trakt data to local
    ✅ Mark films/series as watched
    ✅ Add watchlist to favorites
    ✅ Synchronizes playback progress"""
    from resources.lib.db import db
    from resources.lib.trakt_sync import trakt_request
    
    if progress_dialog:
        progress_dialog.update(0, "Fetching data from Trakt...")
    
    try:
        # === 1. IMPORTS MOVIES WATCHED ===
        watched_movies_response = trakt_request('GET', '/sync/watched/movies?extended=full')
        
        if watched_movies_response and watched_movies_response.get('data'):
            watched_movies = watched_movies_response['data']
            
            if progress_dialog:
                progress_dialog.update(20, f"Importing {len(watched_movies)} movies...")
            
            for item in watched_movies:
                movie = item.get('movie', {})
                tmdb_id = movie['ids'].get('tmdb')
                plays = item.get('plays', 1)
                last_watched = item.get('last_watched_at')
                
                if tmdb_id:
                    # Checks if movie exists in local DB
                    local_movie = db.get_movie_by_id(tmdb_id)
                    if local_movie:
                        # Update playcount
                        db.update_movie_playcount(tmdb_id, plays, last_watched)
        
        # === 2. MATTER WATCHED SERIES ===
        watched_shows_response = trakt_request('GET', '/sync/watched/shows?extended=full')
        
        if watched_shows_response and watched_shows_response.get('data'):
            watched_shows = watched_shows_response['data']
            
            if progress_dialog:
                progress_dialog.update(40, f"Importing {len(watched_shows)} series...")
            
            for item in watched_shows:
                show = item.get('show', {})
                tmdb_id = show['ids'].get('tmdb')
                last_watched = item.get('last_watched_at')
                
                if tmdb_id:
                    local_show = db.get_tvshow_by_id(tmdb_id)
                    if local_show:
                        # TODO: Import watched episodes in detail
                        db.update_tvshow_playcount(tmdb_id, last_watched)
        
        # === 3. MATTER WATCHLIST → FAVORITES ===
        watchlist_movies_response = trakt_request('GET', '/sync/watchlist/movies')
        watchlist_shows_response = trakt_request('GET', '/sync/watchlist/shows')
        
        if progress_dialog:
            progress_dialog.update(60, "Importing watchlist...")
        
        if watchlist_movies_response and watchlist_movies_response.get('data'):
            for item in watchlist_movies_response['data']:
                movie = item.get('movie', {})
                tmdb_id = movie['ids'].get('tmdb')
                if tmdb_id and db.get_movie_by_id(tmdb_id):
                    db.add_to_favorites(tmdb_id, 'movie')
        
        if watchlist_shows_response and watchlist_shows_response.get('data'):
            for item in watchlist_shows_response['data']:
                show = item.get('show', {})
                tmdb_id = show['ids'].get('tmdb')
                if tmdb_id and db.get_tvshow_by_id(tmdb_id):
                    db.add_to_favorites(tmdb_id, 'tvshow')
        
        if progress_dialog:
            progress_dialog.update(100, "Import completed!")
        
        xbmcgui.Dialog().notification("Trakt Sync", "✅ Data imported successfully",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt Import] Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Error", f"Import failed: {str(e)}")
        return False

# === AUTOMATIC SYNC WHEN WATCHING ===

class TraktScrobbler(xbmc.Player):
    """Monitor that automatically syncs when you watch something
    ✅ Real-time scrobble
    ✅ Mark as watched at the end
    ✅ Synchronizes progress (pause/resume)"""
    
    def __init__(self):
        super(TraktScrobbler, self).__init__()
        self.current_item = None
        self.start_time = None
        self.scrobbled = False
    
    def onPlayBackStarted(self):
        """Called when playback starts"""
        try:
            from resources.lib.trakt_sync import trakt_request, get_trakt_settings
            
            settings = get_trakt_settings()
            if not settings.get('access_token'):
                return  # Trakt not configured
            
            # Gets information about the current item
            if not self.isPlayingVideo():
                return
            
            info = self.getVideoInfoTag()
            tmdb_id = info.getUniqueID('tmdb')
            imdb_id = info.getIMDBNumber()
            
            if not tmdb_id:
                return
            
            # Detects type (movie or episode)
            media_type = info.getMediaType()
            
            if media_type == 'movie':
                self.current_item = {
                    'type': 'movie',
                    'tmdb_id': tmdb_id,
                    'progress': 0,
                    'duration': self.getTotalTime()
                }
                
                # Scrobble start
                trakt_request('POST', '/scrobble/start', {
                    'movie': {'ids': {'tmdb': int(tmdb_id)}},
                    'progress': 0
                })
                
            elif media_type == 'episode':
                season = info.getSeason()
                episode = info.getEpisode()
                
                self.current_item = {
                    'type': 'episode',
                    'tmdb_id': tmdb_id,
                    'season': season,
                    'episode': episode,
                    'progress': 0,
                    'duration': self.getTotalTime()
                }
                
                # Scrobble start
                trakt_request('POST', '/scrobble/start', {
                    'show': {'ids': {'tmdb': int(tmdb_id)}},
                    'episode': {
                        'season': season,
                        'number': episode
                    },
                    'progress': 0
                })
            
            self.start_time = time.time()
            self.scrobbled = False
            
            xbmc.log(f"[Trakt Scrobble] Started: {self.current_item}", xbmc.LOGINFO)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Error onStart: {e}", xbmc.LOGERROR)
    
    def onPlayBackStopped(self):
        """Called when playback stops"""
        self._scrobble_stop()
    
    def onPlayBackEnded(self):
        """Called when playback ends"""
        self._scrobble_stop(completed=True)
    
    def _scrobble_stop(self, completed=False):
        """Send scrobble stop/pause to Trakt"""
        try:
            from resources.lib.trakt_sync import trakt_request
            
            if not self.current_item or self.scrobbled:
                return
            
            # Calculates progress
            if self.start_time:
                elapsed = time.time() - self.start_time
                progress = min(100, int((elapsed / self.current_item['duration']) * 100))
            else:
                progress = 0
            
            # Consider assisted if it exceeds 80%
            if progress >= 80:
                completed = True
            
            # Mount payload
            if self.current_item['type'] == 'movie':
                payload = {
                    'movie': {'ids': {'tmdb': int(self.current_item['tmdb_id'])}},
                    'progress': progress
                }
            else:
                payload = {
                    'show': {'ids': {'tmdb': int(self.current_item['tmdb_id'])}},
                    'episode': {
                        'season': self.current_item['season'],
                        'number': self.current_item['episode']
                    },
                    'progress': progress
                }
            
            # Send scrobble
            endpoint = '/scrobble/stop' if completed else '/scrobble/pause'
            trakt_request('POST', endpoint, payload)
            
            self.scrobbled = True
            
            # Update local DB
            if completed:
                from resources.lib.db import db
                if self.current_item['type'] == 'movie':
                    db.mark_movie_as_watched(self.current_item['tmdb_id'])
                
                xbmc.log(f"[Trakt Scrobble] Marked as watched: {self.current_item['tmdb_id']}", xbmc.LOGINFO)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Error onStop: {e}", xbmc.LOGERROR)

# === FULL BIDIRECTIONAL SYNC ===

def full_bidirectional_sync():
    """Full synchronization in both directions
    1. Local → Trakt (assisted sends)
    2. Trakt → Local (imports watchlist)"""
    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Sync Complete", "Starting...")
    
    try:
        # Check authentication
        from resources.lib.trakt_sync import refresh_trakt_token
        if not refresh_trakt_token():
            progress.close()
            xbmcgui.Dialog().ok("Error", "You are not signed in to Trakt.")
            return False
        
        # Step 1: Location → Trakt
        progress.update(10, "Sending local data to Trakt...")
        sync_local_to_trakt(progress)
        
        xbmc.sleep(1000)
        
        # Step 2: Trakt → Location
        progress.update(50, "Importing data from Trakt...")
        sync_trakt_to_local(progress)
        
        progress.update(100, "Synchronization completed!")
        xbmc.sleep(200)
        progress.close()
        
        # Save timestamp
        ADDON.setSetting('trakt_last_sync', str(time.time()))
        
        xbmcgui.Dialog().ok(
            "Trakt Sync",
            "Two-way synchronization completed!\n\n"
            "✅ Local data sent\n"
            "✅ Imported watchlist\n"
            "✅ Synchronized history"
        )
        
        return True
        
    except Exception as e:
        progress.close()
        xbmc.log(f"[Trakt Full Sync] Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Error", f"Sync failed:\n{str(e)}")
        return False

# === SYNC MENU ===

def show_sync_menu():
    """Sync options menu"""
    options = [
        "Full Synchronization (Local ↔ Trakt)",
        "Send Local Data → Trakt",
        "Import Trakt Data → Local",
        "Clear Cache e Re-sync",
        "Set Up Automatic Scrobble"
    ]
    
    choice = xbmcgui.Dialog().select("Trakt Sync", options)
    
    if choice == 0:
        full_bidirectional_sync()
    elif choice == 1:
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt Sync", "Sending...")
        sync_local_to_trakt(progress)
        progress.close()
    elif choice == 2:
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt Sync", "Importing...")
        sync_trakt_to_local(progress)
        progress.close()
    elif choice == 3:
        from resources.lib.trakt_sync import _clear_trakt_cache
        _clear_trakt_cache()
        full_bidirectional_sync()
    elif choice == 4:
        current = ADDON.getSettingBool('trakt_auto_scrobble')
        ADDON.setSettingBool('trakt_auto_scrobble', not current)
        status = "enabled" if not current else "disabled"
        xbmcgui.Dialog().notification("Trakt", f"Automatic scrobble {status}", xbmcgui.NOTIFICATION_INFO, 2000)

# === INTEGRATION WITH ADDON ===

def init_trakt_scrobbler():
    """Initializes the automatic scrobble monitor"""
    if ADDON.getSettingBool('trakt_auto_scrobble'):
        scrobbler = TraktScrobbler()
        xbmc.log("[Trakt] Scrobbler initialized", xbmc.LOGINFO)
        return scrobbler
    return None

# === INITIALIZATION ===
_create_trakt_cache_tables()