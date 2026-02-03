# -*- coding: utf-8 -*-
# resources/lib/scrapers/stremio.py - OPTIMIZED VERSION

import requests
import xbmc
import urllib.parse
from .session import USER_AGENT
from .utils import get_anime_search_patterns
from ..debug_logger import logger

def scrape(provider_url, is_configurable, imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """Unified and optimized Stremio Scraper."""
    
    # None
    # 1. VALIDATION AND STANDARDIZATION
    # None
    if not provider_url:
        return []
    
    # Normalizes the base URL (removes manifest.json if present)
    base_url = provider_url.replace('/manifest.json', '').rstrip('/')
    
    # Normalize season/episode ONLY if they are not None
    season = _safe_int(season)
    episode = _safe_int(episode)
    
    # Validates minimum requirements
    if not imdb_id and "animezey" not in base_url.lower():
        xbmc.log(f"[Stremio] Sem IMDB ID para {base_url}", xbmc.LOGDEBUG)
        return []
    
    # None
    # 2. CONSTRUCTION OF ENDPOINTS
    # None
    endpoints = _build_endpoints(media_type, imdb_id, season, episode)
    
    # If we don't have IMDB, we try text search if the provider supports it (ex: Jackett/Torrentio via search)
    # But most Stremio addons require ID.
    # We will add support for searching by original title if IMDB fails or as an add-on.
    
    if not endpoints and not item_data:
        xbmc.log(f"[Stremio] No valid endpoint for {media_type}", xbmc.LOGWARNING)
        return []
    
    # None
    # 3. TORRENTIO SETUP
    # None
    config_prefix = ""
    if is_configurable:
        try:
            from ..utils import build_torrentio_config_string
            config_prefix = build_torrentio_config_string()
        except Exception as e:
            xbmc.log(f"[Stremio] Config error: {e}", xbmc.LOGDEBUG)
    
    # None
    # 4. SEARCH AND DEDUPLICATION
    # None
    streams = []
    seen_ids = set()
    
    # Add search by title if it's Torrentio and we don't have results by ID
    if "torrentio" in base_url.lower() and not endpoints:
        search_query = item_data.get('original_title') or item_data.get('title')
        if search_query:
            if media_type == 'tvshow':
                query = f"{search_query} S{int(season):02d}E{int(episode):02d}"
            else:
                year = item_data.get('year', '')
                query = f"{search_query} {year}"
            endpoints.append(f"/stream/{media_type}/{urllib.parse.quote(query)}.json")

    for endpoint in endpoints:
        if cancel_event and cancel_event.is_set():
            break
            
        if config_prefix:
            url = f"{base_url}/{config_prefix}{endpoint}"
        else:
            url = f"{base_url}{endpoint}"
        
        # Fix for double slash URLs
        url = url.replace('//stream', '/stream')
        
        found = _fetch_streams(url)
        if not found:
            continue
        
        # Deduplicate and add release_title
        for stream in found:
            stream_id = stream.get('url') or stream.get('infoHash')
            
            if stream_id and stream_id in seen_ids:
                continue
            
            # Add release title if it doesn't exist
            if 'release_title' not in stream:
                # Attempts to extract the actual title of the file from Stremio's 'title' or 'description' field
                raw_title = stream.get('title', '') or stream.get('description', '')
                if raw_title:
                    # Take the first line, which is usually the file name
                    file_name = raw_title.split('\n')[0].strip()
                    if file_name and len(file_name) > 5:
                        stream['release_title'] = file_name
                
                # Fallback if failed to extract a valid filename
                if 'release_title' not in stream:
                    stream['release_title'] = _generate_release_title(
                        item_data, media_type, season, episode
                    )
            
            streams.append(stream)
            
            if stream_id:
                seen_ids.add(stream_id)
    
    provider_name = base_url.split('/')[2]
    xbmc.log(f"[Stremio] {len(streams)} streams de {provider_name}", xbmc.LOGINFO)
    logger.scraper_sources(provider_name, len(streams), streams[:3] if streams else [])
    return streams


# ==========================================================
# AUXILIARY FUNCTIONS (INTERNAL)
# ==========================================================

def _safe_int(value):
    """Converts to int safely."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        xbmc.log(f"[Stremio] Invalid conversion: {value}", xbmc.LOGDEBUG)
        return None


def _build_endpoints(media_type, imdb_id, season, episode):
    """Builds list of endpoints to try."""
    endpoints = []
    
    if media_type == 'movie':
        if imdb_id:
            endpoints.append(f"/stream/movie/{imdb_id}.json")
    
    elif media_type == 'tvshow':
        if season is None or episode is None:
            return []
        
        if not imdb_id:
            return []
        
        # Uses anime search patterns (e.g. S01:E01, S1:E1)
        from .utils import get_anime_search_patterns
        patterns = get_anime_search_patterns(season, episode)
        
        for s, e in patterns:
            endpoints.append(f"/stream/series/{imdb_id}:{s}:{e}.json")
    
    return endpoints


def _fetch_streams(url):
    """Makes request and returns list of streams."""
    provider_name = url.split('/')[2]
    try:
        xbmc.log(f"[Stremio] Requisitando: {url}", xbmc.LOGINFO)
        logger.network(url, method='GET')
        response = requests.get(
            url, 
            headers={'User-Agent': USER_AGENT}, 
            timeout=10
        )
        logger.network(url, method='GET', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
        xbmc.log(f"[Stremio] Resposta de {url}: Status {response.status_code}", xbmc.LOGINFO)
        response.raise_for_status()
        
        data = response.json()
        streams = data.get('streams', [])
        
        if streams:
            xbmc.log(f"[Stremio] ✓ {len(streams)} em {url.split('/')[-1]}", xbmc.LOGDEBUG)
        
        return streams
        
    except requests.Timeout:
        xbmc.log(f"[Stremio] Timeout: {url}", xbmc.LOGWARNING)
        logger.scraper_error(provider_name, "Timeout", url)
    except requests.RequestException as e:
        xbmc.log(f"[Stremio] HTTP Error: {e}", xbmc.LOGDEBUG)
        logger.scraper_error(provider_name, f"HTTP Error: {e}", url)
    except ValueError:
        xbmc.log(f"[Stremio] Invalid JSON: {url}", xbmc.LOGWARNING)
        logger.scraper_error(provider_name, "Invalid JSON", url)
    except Exception as e:
        xbmc.log(f"[Stremio] Unexpected error: {e}", xbmc.LOGERROR)
        logger.scraper_error(provider_name, f"Unexpected Error: {e}", url)
    
    return []


def _generate_release_title(item_data, media_type, season, episode):
    """Generates default release title."""
    if not item_data:
        if media_type == 'tvshow' and season is not None and episode is not None:
            return f"S{season:02d}E{episode:02d}"
        return "Unknown"
    
    title = item_data.get('title', 'Unknown')
    
    if media_type == 'tvshow' and season is not None and episode is not None:
        return f"{title} S{season:02d}E{episode:02d}"
    
    return title
