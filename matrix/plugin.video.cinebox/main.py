# -*- coding: utf-8 -*-
import sys
import os
from urllib.parse import parse_qsl

# ============ ESSENTIAL IMPORTS ============
import xbmcgui
import xbmc
import xbmcaddon

# Global variables
HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")

# ============ INITIALIZE AUTOMATIC SCROBBLER ============
_SCROBBLER = None

def _init_scrobbler():
    """Initializes the Trakt automatic scrobble monitor"""
    global _SCROBBLER
    if _SCROBBLER is not None:
        return _SCROBBLER
    
    try:
        if ADDON.getSettingBool('trakt_auto_scrobble'):
            from resources.lib.trakt_sync import TraktScrobbler
            _SCROBBLER = TraktScrobbler()
            xbmc.log("[Cinebox] Trakt Scrobbler started", xbmc.LOGINFO)
            return _SCROBBLER
    except Exception as e:
        xbmc.log(f"[Cinebox] Error initializing Scrobbler: {e}", xbmc.LOGERROR)
    
    return None


# ============ OPTIMIZED CACHE SYSTEM ============
_MODULE_CACHE = {}
_MODULE_CACHE_MAX = 20  # ✅ NEW: Module cache limit
_JSON_CACHE = {}
_ACTION_HANDLERS = {}  # ✅ NEW: Compiled handlers cache

def _get_module(name):
    """Ultra-fast lazy loading with module caching"""
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]
    
    try:
        if name == 'movies':
            from resources.lib import movies as mod
        elif name == 'tvshows':
            from resources.lib import tvshows as mod
        elif name == 'navigation':
            from resources.lib import navigation as mod
        elif name == 'extras_dialog':
            from resources.lib import extras_dialog as mod
        elif name == 'indexer':
            from resources.lib import indexer as mod
        elif name == 'favorites':
            from resources.lib import favorites as mod
        elif name == 'db':
            from resources.lib.db import db as mod
        elif name == 'constants':
            from resources.lib import constants as mod
        elif name == 'xbmcplugin':
            import xbmcplugin as mod
        elif name == 'donation_window':
            from resources.lib.donation_window import DonationDialog as mod
        elif name == 'trakt_sync':
            from resources.lib import trakt_sync as mod
        elif name == 'library':
            from resources.lib import library as mod
        else:
            return None
        
        # ✅ OPTIMIZATION: Limit module cache size
        if len(_MODULE_CACHE) >= _MODULE_CACHE_MAX:
            # Remove least used modules (simple approach: remove first inserted)
            first_key = next(iter(_MODULE_CACHE))
            del _MODULE_CACHE[first_key]
        
        _MODULE_CACHE[name] = mod
        return mod
    except ImportError as e:
        xbmc.log(f"[Cinebox] Error importing {name}: {e}", xbmc.LOGERROR)
        return None

def _parse_json(data):
    """Smart JSON cache with memory limit"""
    if not data:
        return {}
    
    if data in _JSON_CACHE:
        return _JSON_CACHE[data]
    
    try:
        from urllib.parse import unquote_plus
        import json
        parsed = json.loads(unquote_plus(data))
        
        # Limit cache to 50 entries
        if len(_JSON_CACHE) > 50:
            _JSON_CACHE.clear()
        
        _JSON_CACHE[data] = parsed
        return parsed
    except:
        return {}

def _end_dir(success=True):
    """Quick helper for endOfDirectory"""
    xbmcplugin = _get_module('xbmcplugin')
    if xbmcplugin:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=success)

# ============ ACTION MAPPING - OPTIMIZED ============
_ACTIONS = {
    
    # == TRAKT.TV ===
    'list_trakt_watchlist': ('trakt_sync', 'list_trakt_watchlist', False, None),
    'list_trakt_collection': ('trakt_sync', 'list_trakt_collection', False, None),
    'list_trakt_watched': ('trakt_sync', 'list_trakt_watched', False, None),

    # === TRAKT MOVIES ===
    'trakt_movies_trending': ('trakt_sync', 'trakt_movies_trending', True, None),
    'trakt_movies_popular': ('trakt_sync', 'trakt_movies_popular', True, None),
    'trakt_movies_most_watched': ('trakt_sync', 'trakt_movies_most_watched', True, None),
    'trakt_movies_most_collected': ('trakt_sync', 'trakt_movies_most_collected', True, None),
    'trakt_movies_most_anticipated': ('trakt_sync', 'trakt_movies_most_anticipated', True, None),
    'trakt_movies_box_office': ('trakt_sync', 'trakt_movies_box_office', True, None),
    'trakt_movies_top_rated': ('trakt_sync', 'trakt_movies_top_rated', True, None),
    
    # === TRAKT TV SHOWS ===
    'trakt_tv_trending': ('trakt_sync', 'trakt_tv_trending', True, None),
    'trakt_tv_popular': ('trakt_sync', 'trakt_tv_popular', True, None),
    'trakt_tv_most_watched': ('trakt_sync', 'trakt_tv_most_watched', True, None),
    'trakt_tv_most_collected': ('trakt_sync', 'trakt_tv_most_collected', True, None),
    'trakt_tv_most_anticipated': ('trakt_sync', 'trakt_tv_most_anticipated', True, None),
    'trakt_tv_top_rated': ('trakt_sync', 'trakt_tv_top_rated', True, None),
    'trakt_tv_recommended': ('trakt_sync', 'trakt_tv_recommended', True, None),
    
    # === MOVIES ===
    'list_genres': ('movies', 'list_genres', False, None),
    'list_years': ('movies', 'list_years', False, None),
    'list_movies_by_genre': ('movies', 'list_movies_by_genre', True, ['genre_id', 'genre_name']),
    'list_movies_by_year': ('movies', 'list_movies_by_year', True, ['year']),
    'list_movies_by_rating': ('movies', 'list_movies_by_rating', True, None),
    'list_movies_by_popularity': ('movies', 'list_movies_by_popularity', True, None),
    'list_movies_top_rated': ('movies', 'list_movies_top_rated', True, None),
    'list_movies_now_playing': ('movies', 'list_movies_now_playing', True, None),
    'list_upcoming_movies': ('movies', 'list_upcoming_movies', True, None),
    'list_4k_movies': ('movies', 'list_4k_movies', True, None),
    'list_collections': ('movies', 'list_collections', True, None),
    'list_movies_by_collection': ('movies', 'list_movies_by_collection', True, ['collection']),
    'list_recently_added_movies': ('movies', 'list_recently_added_movies', True, None),
    'list_movies_by_revenue': ('movies', 'list_movies_by_revenue', True, None),
    'list_movies_by_provider': ('movies', 'list_movies_by_provider', True, ['provider']),
    'list_trending_movies': ('movies', 'list_trending_movies', True, None),
    
    # === TV SHOWS ===
    'list_tvshows_genres': ('tvshows', 'list_tvshows_genres', False, None),
    'list_tvshows_years': ('tvshows', 'list_tvshows_years', False, None),
    'list_tvshows_by_year': ('tvshows', 'list_tvshows_by_year', True, ['year']),
    'list_providers': ('tvshows', 'list_providers', False, None),
    'list_upcoming_tvshows': ('tvshows', 'list_upcoming_tvshows', True, None),
    'list_trending_tvshows': ('tvshows', 'list_trending_tvshows', True, None),
    'list_tvshows_by_genre': ('tvshows', 'list_tvshows_by_genre', True, ['genre_id', 'genre_name']),
    'list_recently_added_tvshows': ('tvshows', 'list_recently_added_tvshows', True, None),
    'list_tvshows_by_popularity': ('tvshows', 'list_tvshows_by_popularity', True, None),
    'list_tvshows_top_rated': ('tvshows', 'list_tvshows_top_rated', True, None),
    'list_tvshows_airing_today': ('tvshows', 'list_tvshows_airing_today', True, None),
    'list_tvshows_on_the_air': ('tvshows', 'list_tvshows_on_the_air', True, None),
    'list_tvshows_by_provider': ('tvshows', 'list_tvshows_by_provider', True, ['provider']),
    'list_animes': ('tvshows', 'list_animes', False, None),
    'list_kids_tvshows': ('tvshows', 'list_kids_tvshows', True, None),
    
    # === ANIMES ===
    'list_anime_popular': ('tvshows', 'list_anime_popular', True, None),
    'list_anime_recent': ('tvshows', 'list_anime_recent', True, None),
    'list_anime_on_the_air': ('tvshows', 'list_anime_on_the_air', True, None),
    'list_anime_years': ('tvshows', 'list_anime_years', False, None),
    'list_anime_by_year': ('tvshows', 'list_anime_by_year', True, ['year']),
    'list_anime_genres': ('tvshows', 'list_anime_genres', False, None),
    'list_anime_by_genre': ('tvshows', 'list_anime_by_genre', True, ['genre_id', 'genre_name']),
    'trakt_anime_trending': ('trakt_sync', 'trakt_anime_trending', True, None),
    'trakt_anime_most_watched': ('trakt_sync', 'trakt_anime_most_watched', True, None),
    
    # === STREAMING ===
    'list_streaming_platforms_movies': ('movies', 'list_streaming_platforms', False, None),
    'list_streaming_platforms_tvshows': ('tvshows', 'list_streaming_platforms', False, None),
    'list_movies_by_streaming': ('movies', 'list_movies_by_streaming', True, ['provider_id', 'provider_name', 'region']),
    'list_tvshows_by_streaming': ('tvshows', 'list_tvshows_by_streaming', True, ['provider_id', 'provider_name', 'region']),
}

def _get_action_handler(action):
    """
    ✅ NEW FUNCTION: Returns pre-compiled handler
    Avoids repeated lookups in the _ACTIONS dictionary
    """
    if action in _ACTION_HANDLERS:
        return _ACTION_HANDLERS[action]
    
    config = _ACTIONS.get(action)
    if not config:
        return None
    
    module_name, method_name, needs_page, extra_params = config
    
    # Create handler as tuple (faster than dict)
    handler = (module_name, method_name, needs_page, extra_params)
    _ACTION_HANDLERS[action] = handler
    
    return handler

def _handle_generic_action(action, params):
    """OPTIMIZED Generic Handler - FIXED for pagination"""
    handler = _get_action_handler(action)
    if not handler:
        return False
    
    module_name, method_name, needs_page, extra_params = handler
    
    # Load module (cached)
    mod = _get_module(module_name)
    if not mod:
        return False
    
    # Get method (cached by Python)
    method = getattr(mod, method_name, None)
    if not method:
        return False
    
    # Assemble args - FIXED
    args = []
    
    if extra_params:
        for param in extra_params:
            val = params.get(param, '')
            # Convert year to int if necessary
            if param == 'year':
                val = int(val) if val and val != '' else 0
            args.append(val)
    
    # Add page as argument (respecting order if region exists)
    if needs_page:
        page_val = params.get('page', '1')
        try:
            page_int = int(page_val) if page_val else 1
        except (ValueError, TypeError):
            page_int = 1
        args.append(page_int)
    
    # Execute method with unpacked args
    try:
        method(*args)
        return True
    except Exception as e:
        xbmc.log(f"[Cinebox] Error executing {module_name}.{method_name}: {e}", xbmc.LOGERROR)
        return False

def _handle_show_details(params):
    """Optimized handler for details"""
    data = _parse_json(params.get('data', ''))
    if not data:
        return False
    
    nav = _get_module('navigation')
    if nav:
        nav.show_details(data)
        return True
    return False

def _handle_list_seasons(params):
    """Optimized handler for seasons"""
    tv = _get_module('tvshows')
    if tv:
        tv.list_seasons(params.get('tvshow_tmdb_id'))
        return True
    return False

def _handle_list_episodes(params):
    """Optimized handler for episodes"""
    tv = _get_module('tvshows')
    if tv:
        tv.list_episodes(
            params.get('tvshow_tmdb_id'),
            int(params.get('season_number', 1))
        )
        return True
    return False

def _handle_favorites(action, params):
    """Optimized handler for favorites"""
    fav = _get_module('favorites')
    if not fav:
        return False
    
    if action == 'add_to_favorites':
        fav.add_item_to_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'remove_from_favorites':
        fav.remove_item_from_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'favorites_menu':
        nav = _get_module('navigation')
        if nav:
            nav.show_my_list_menu()
    elif action == 'favorites_movies':
        nav = _get_module('navigation')
        if nav:
            nav.show_favorite_movies()
    elif action == 'favorites_tvshows':
        nav = _get_module('navigation')
        if nav:
            nav.show_favorite_tvshows()
    else:
        return False
    
    return True

def _handle_trakt(action, params):
    """COMPLETE Trakt handler - with individual actions"""
    
    # Main Menu - no import needed
    if action == 'trakt_main_menu':
        nav = _get_module('navigation')
        const = _get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_MENU)
        return True

    # ✅ LAZY IMPORT only for actions that actually need it
    trakt = _get_module('trakt_sync')
    if not trakt:
        return False
    
    # ============================================
    # ✅ INDIVIDUAL ACTIONS (CONTEXT MENU)
    # ============================================
    
    tmdb_id = params.get('tmdb_id')
    media_type = params.get('media_type')
    page = int(params.get('page', 1))
    
    # Direct mapping of actions to functions in trakt_sync.py
    trakt_actions = {
        'trakt_movies_trending': lambda: trakt.trakt_movies_trending(page),
        'trakt_movies_popular': lambda: trakt.trakt_movies_popular(page),
        'trakt_movies_most_watched': lambda: trakt.trakt_movies_most_watched(page),
        'trakt_movies_most_collected': lambda: trakt.trakt_movies_most_collected(page),
        'trakt_movies_most_anticipated': lambda: trakt.trakt_movies_most_anticipated(page),
        'trakt_movies_box_office': lambda: trakt.trakt_movies_box_office(page),
        'trakt_movies_top_rated': lambda: trakt.trakt_movies_top_rated(page),
        'trakt_tv_trending': lambda: trakt.trakt_tv_trending(page),
        'trakt_tv_popular': lambda: trakt.trakt_tv_popular(page),
        'trakt_tv_most_watched': lambda: trakt.trakt_tv_most_watched(page),
        'trakt_tv_most_collected': lambda: trakt.trakt_tv_most_collected(page),
        'trakt_tv_most_anticipated': lambda: trakt.trakt_tv_most_anticipated(page),
        'trakt_tv_top_rated': lambda: trakt.trakt_tv_top_rated(page),
        'trakt_tv_recommended': lambda: trakt.trakt_tv_recommended(page),
        'trakt_anime_trending': lambda: trakt.trakt_anime_trending(page),
        'trakt_anime_most_watched': lambda: trakt.trakt_anime_most_watched(page),
    }

    if action in trakt_actions:
        return trakt_actions[action]()

    if action == 'trakt_add_collection':
        if tmdb_id and media_type:
            trakt.trakt_add_to_collection(tmdb_id, media_type)
        return True
    
    if action == 'trakt_remove_collection':
        if tmdb_id and media_type:
            trakt.trakt_remove_from_collection(tmdb_id, media_type)
        return True
    
    if action == 'trakt_mark_watched':
        if tmdb_id and media_type:
            trakt.trakt_mark_as_watched(tmdb_id, media_type)
        return True
    
    if action == 'trakt_remove_watched':
        if tmdb_id and media_type:
            trakt.trakt_remove_watched(tmdb_id, media_type)
        return True
    
    if action == 'trakt_add_watchlist':
        if tmdb_id and media_type:
            trakt.trakt_add_to_watchlist(tmdb_id, media_type)
        return True
    
    if action == 'trakt_remove_watchlist':
        if tmdb_id and media_type:
            trakt.trakt_remove_from_watchlist(tmdb_id, media_type)
        return True
    
    if action == 'trakt_rate':
        if tmdb_id and media_type:
            trakt.trakt_rate_item(tmdb_id, media_type)
        return True
    
    # ============================================
    # AUTH AND STATUS
    # ============================================
    
    if action == 'trakt_auth':
        settings = trakt.get_trakt_settings()
        if settings.get('access_token'):
            trakt.show_trakt_status()
        else:
            trakt.authenticate_trakt()
        return True
    
    if action == 'trakt_status':
        trakt.show_trakt_status()
        return True
    
    # ============================================
    # LISTING MENUS
    # ============================================
    
    if action == 'trakt_watchlist_menu':
        trakt.show_trakt_watchlist_items(page)
        return True
    
    if action == 'trakt_collection_menu':
        trakt.show_trakt_collection_items(page)
        return True
    
    if action == 'trakt_watched_menu':
        trakt.show_trakt_watched_items(page)
        return True
    
    if action == 'trakt_trending_menu':
        trakt.show_trakt_trending_items(page)
        return True
    
    if action == 'trakt_popular_menu':
        trakt.show_trakt_popular_items(page)
        return True
    
    # Custom Lists
    if action == 'trakt_lists_menu':
        trakt.show_trakt_custom_lists()
        return True
    
    if action == 'trakt_list_items':
        list_id = params.get('list_id')
        trakt.show_trakt_list_items(list_id, page)
        return True
    
    # ============================================
    # SYNC
    # ============================================
    
    if action == 'trakt_full_sync':
        trakt.full_bidirectional_sync()
        return True
    
    if action == 'trakt_sync_to_trakt':
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt", "Sending data...")
        trakt.sync_local_to_trakt(progress)
        progress.close()
        return True
    
    if action == 'trakt_sync_from_trakt':
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt", "Importing data...")
        trakt.sync_trakt_to_local(progress)
        progress.close()
        return True
    
    if action == 'trakt_sync':
        direction = params.get('direction', 'both')
        trakt.full_sync_with_trakt(direction)
        return True
    
    if action == 'trakt_clear_cache':
        trakt.clear_trakt_cache()
        return True
    
    if action == 'trakt_toggle_scrobble':
        current = ADDON.getSettingBool('trakt_auto_scrobble')
        ADDON.setSettingBool('trakt_auto_scrobble', not current)
        status = "activated ✅" if not current else "deactivated ❌"
        xbmcgui.Dialog().notification("Trakt Scrobbler", f"Automatic Scrobble {status}", xbmcgui.NOTIFICATION_INFO, 3000)
        return True
    
    if action == 'trakt_public_lists':
        trakt.show_trakt_public_lists_menu()
        return True
    
    if action == 'trakt_public_category':
        trakt.show_trakt_public_category(params.get('category'))
        return True
    
    if action == 'trakt_public_list':
        category = params.get('category')
        media_type = params.get('media_type')
        trakt.show_trakt_public_list(category, media_type, page)
        return True
    
    return False

def _handle_navigation(action, params):
    """Optimized handler for navigation"""
    nav = _get_module('navigation')
    if not nav:
        return False
    
    if action == 'view_debug_log':
        if hasattr(nav, 'view_debug_log'):
            nav.view_debug_log()
        return True
        
    if action == 'export_debug_log':
        if hasattr(nav, 'export_debug_log'):
            nav.export_debug_log()
        return True
        
    if action == 'clear_debug_log':
        if hasattr(nav, 'clear_debug_log'):
            nav.clear_debug_log()
        return True

    if action == 'search':
        nav.search(params.get('query'), params.get('page', '1'))
        return True
    
    if action == 'find_sources':
        item_data = {
            'tmdb_id': params.get('tmdb_id', ''),
            'imdb_id': params.get('imdb_id', ''),
            'media_type': params.get('media_type', ''),
            'title': params.get('title', ''),
            'original_title': params.get('original_title', ''),
            'year': params.get('year', ''),
            'clearlogo': params.get('clearlogo', ''),
            'fanart': params.get('fanart', ''),
            'backdrop': params.get('backdrop', ''),
            'poster': params.get('poster', ''),
            'season': params.get('season'),
            'episode': params.get('episode')
        }
        nav.find_and_play_sources(
            item_data,
            autoplay=params.get('autoplay'),
            season=params.get('season'),
            episode=params.get('episode')
        )
        return True
    
    if action == 'play_item_direct':
        item_data = _parse_json(params.get('data', ''))
        if item_data:
            # ✅ CORRECTION: Respects the addon's autoplay setting
            autoplay_setting = ADDON.getSettingBool('playback.autoplay')
            nav.find_and_play_sources(item_data, autoplay=autoplay_setting)
        return True
    
    if action == 'find_and_play_episode':
        item_data = _parse_json(params.get('item_data', ''))
        if item_data:
            # ✅ CORRECTION: Respects the addon's autoplay setting
            autoplay_setting = ADDON.getSettingBool('playback.autoplay')
            nav.find_and_play_sources(
                item_data,
                autoplay=autoplay_setting,
                season=params.get('season'),
                episode=params.get('episode')
            )
        return True
    
    return False

def _handle_menu(action, params):
    """Optimized handler for menus"""
    const = _get_module('constants')
    if not const:
        return False
    
    if action == 'movies_menu':
        movies = _get_module('movies')
        if movies:
            movies.show_movies_menu(const.MOVIES_MENU)
            return True
    
    if action == 'tvshows_menu':
        tv = _get_module('tvshows')
        if tv:
            tv.show_tvshows_menu(const.TVSHOWS_MENU)
            return True
            
    if action == 'streaming_menu':
        nav = _get_module('navigation')
        if nav:
            nav.show_main_menu(const.STREAMING_MENU)
            return True
    
    if action == 'tools_menu':
        nav = _get_module('navigation')
        if nav:
            nav.show_main_menu(const.TOOLS_MENU)
            return True
    
    return False

def _handle_library(action, params):
    """OPTIMIZED Library handler - Lazy import"""
    
    # Menu doesn't need import
    if action == 'library_menu':
        win = xbmcgui.Window(10000)
        warned = win.getProperty("cinebox.library.warning")
        
        if not warned:
            ok = xbmcgui.Dialog().yesno(
                "Library (Experimental)",
                "Function in testing. Recommended for advanced users only!\n\nDo you wish to continue?"
            )
            if not ok:
                return False
            win.setProperty("cinebox.library.warning", "true")
        
        # ✅ LAZY IMPORT only here
        lib = _get_module('library')
        if lib and hasattr(lib, 'show_library_menu'):
            lib.show_library_menu()
            return True
        return False
    
    # ✅ LAZY IMPORT only for actions that need it
    lib = _get_module('library')
    if not lib:
        return False
    
    db = _get_module('db')
    
    if action == 'library_add':
        tmdb_id = params.get('tmdb_id')
        media_type = params.get('media_type')
        
        if tmdb_id and media_type and db:
            if media_type == 'movie':
                item_data = db.get_movie_by_id(tmdb_id)
                if item_data and hasattr(lib, 'add_movie_to_library'):
                    lib.add_movie_to_library(item_data)
            
            elif media_type == 'tvshow':
                item_data = db.get_tvshow_by_id(tmdb_id)
                if item_data and xbmcgui.Dialog().yesno("Add", f"Add {item_data.get('title')}?"):
                    if hasattr(lib, 'add_tvshow_to_library'):
                        lib.add_tvshow_to_library(item_data)
                    if xbmcgui.Dialog().yesno("Kodi", "Update library now?"):
                        if hasattr(lib, 'update_kodi_library'):
                            lib.update_kodi_library(media_type)
        return True
    
    if action == 'library_remove':
        tmdb_id = params.get('tmdb_id')
        media_type = params.get('media_type')
        if tmdb_id and media_type and xbmcgui.Dialog().yesno("Remove", "Do you want to remove this from the library?"):
            if hasattr(lib, 'remove_from_library'):
                lib.remove_from_library(tmdb_id, media_type)
        return True
    
    if action == 'library_update':
        if hasattr(lib, 'update_kodi_library'):
            lib.update_kodi_library(params.get('media_type', 'video'))
        return True
    
    if action == 'library_add_all_movies':
        if hasattr(lib, 'add_all_movies_to_library'):
            lib.add_all_movies_to_library()
        return True
    
    if action == 'library_add_all_tvshows':
        if hasattr(lib, 'add_all_tvshows_to_library'):
            lib.add_all_tvshows_to_library()
        return True
    
    if action == 'library_stats':
        if hasattr(lib, 'get_library_stats'):
            stats = lib.get_library_stats()
            xbmcgui.Dialog().ok("Statistics", f"Movies: {stats['movies']}\nShows: {stats['tvshows']}\nEpisodes: {stats['episodes']}")
        return True
    
    return False

# ============ MAIN ROUTER - ULTRA OPTIMIZED ============

def router():
    """Main Router - OPTIMIZED"""
    # Parse parameters
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')
    
    # ============ AUTO-HEAL: DISABLED ============
    # Removed empty catalog message upon entry as requested.
    pass
    
    # ============ ADDON ROOT ============
    if not action:
        nav = _get_module('navigation')
        const = _get_module('constants')
        
        if nav and const:
            nav.show_main_menu(const.MAIN_MENU)
            return _end_dir(True)
        else:
            xbmc.log("[Cinebox] Error loading main menu", xbmc.LOGERROR)
            return _end_dir(False)
    
    # ============ CATEGORY-BASED OPTIMIZED ROUTING ============
    
    # ✅ Generic actions (most common, tested first)
    if _handle_generic_action(action, params):
        return _end_dir()
    
    # ✅ Details
    if action == 'show_details':
        return _end_dir(_handle_show_details(params))
    
    # ✅ Shows (special cases)
    if action == 'list_seasons':
        return _end_dir(_handle_list_seasons(params))
    
    if action == 'list_episodes':
        return _end_dir(_handle_list_episodes(params))
    
    # ✅ Favorites
    if action in ('add_to_favorites', 'remove_from_favorites', 'favorites_menu', 'favorites_movies', 'favorites_tvshows'):
        return _end_dir(_handle_favorites(action, params))
    
    # ✅ Trakt
    if action.startswith('trakt_'):
        return _end_dir(_handle_trakt(action, params))
    
    # ✅ Navigation and Debug
    if action in ('search', 'find_sources', 'play_item_direct', 'find_and_play_episode', 'view_debug_log', 'export_debug_log', 'clear_debug_log'):
        result = _handle_navigation(action, params)
        
        # Dacă acțiunea este 'find_sources', ieșim fără să apelăm _end_dir
        # pentru a permite setResolvedUrl să funcționeze corect.
        if action == 'find_sources':
            return result
            
        return _end_dir(result)
    
    # ✅ Menus
    if action in ('movies_menu', 'tvshows_menu', 'tools_menu', 'streaming_menu'):
        return _end_dir(_handle_menu(action, params))
    
    if action == 'list_collections':
        movies = _get_module('movies')
        if movies:
            movies.list_collections(params.get('page', '1'))
            return _end_dir(True)
    
    # ✅ Library
    if action.startswith('library_'):
        return _end_dir(_handle_library(action, params))
    
    if action == 'show_donation':
        DonationDialog = _get_module('donation_window')
        if DonationDialog:
            DonationDialog("DonationDialog.xml", ADDON_PATH, "Default", "1080i").doModal()
        return _end_dir()
    
    if action == 'open_settings':
        xbmc.executebuiltin('Addon.OpenSettings(plugin.video.cinebox)')
        return _end_dir()
    
    if action == 'show_changelog':
        import xbmcvfs
        from resources.lib.dialog.changelog_dialog import ChangelogDialog
        
        changelog_path = xbmcvfs.translatePath(os.path.join(ADDON_PATH, "changelog.txt"))
        
        text = "Changelog not found."
        if xbmcvfs.exists(changelog_path):
            f = xbmcvfs.File(changelog_path)
            text = f.read()
            f.close()
        
        dialog = ChangelogDialog(
            "ChangelogDialog.xml",
            ADDON_PATH,
            "Default",
            "1080i",
            heading="Changelog — Cinebox",
            text=text
        )
        dialog.doModal()
        del dialog
        return _end_dir()
    
    # ✅ NEW: Update Catalog
    if action == 'update_catalog':
        indexer = _get_module('indexer')
        if indexer:
            indexer.run_indexer()
        return _end_dir()

    # ✅ NEW: Configure External Scrapers
    if action == 'configure_external_scrapers':
        try:
            from resources.lib.dialogs import configure_external_scrapers
        except ImportError:
            from resources.lib import dialogs
            configure_external_scrapers = dialogs.configure_external_scrapers
        
        configure_external_scrapers()
        return _end_dir()
    
    # ============ ACTION NOT FOUND ============
    xbmc.log(f"[Cinebox] Unknown action: {action}", xbmc.LOGWARNING)
    return _end_dir(False)

if __name__ == '__main__':
    # Ensure it doesn't show changelog or initial messages
    # ADDON.setSetting('first_run_extras', 'done')
    
    try:
        _init_scrobbler()
        router()
    except Exception as e:
        xbmc.log(f"[Cinebox] CRITICAL ERROR: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        _end_dir(False)