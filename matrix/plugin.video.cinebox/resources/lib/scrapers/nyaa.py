# -*- coding: utf-8 -*-
import requests
import xbmc
import re
import urllib.parse
from .session import USER_AGENT
from .utils import get_anime_search_patterns
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """NYAA Scraper for Cinemabox."""
    if not item_data:
        return []

    title = item_data.get('title')
    if not title:
        return []

    search_title = re.sub(r'[^A-Za-z0-9\s\.-]+', ' ', title).strip()
    original_title = item_data.get('original_title')
    search_orig = re.sub(r'[^A-Za-z0-9\s\.-]+', ' ', original_title).strip() if original_title else None
    
    streams = []
    seen_hashes = set()
    
    patterns = get_anime_search_patterns(season, episode) if media_type == 'tvshow' else [(None, item_data.get('year'))]
    
    base_url = "https://nyaa.si"
    
    for s, e in patterns:
        queries = []
        if media_type == 'tvshow':
            queries.append(f"{search_title} S{int(s):02d}E{int(e):02d}")
            if search_orig and search_orig != search_title:
                queries.append(f"{search_orig} S{int(s):02d}E{int(e):02d}")
        else:
            queries.append(f"{search_title} {e}")
            if search_orig and search_orig != search_title:
                queries.append(f"{search_orig} {e}")

        for query in queries:
            if cancel_event and cancel_event.is_set():
                break
            url = f"{base_url}/?f=0&c=1_0&q={urllib.parse.quote(query)}&s=seeders&o=desc"
        
        try:
            logger.network(url, method='GET')
            response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10)
            logger.network(url, method='GET', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
            if response.status_code != 200:
                continue
                
            html = response.text
            items = re.findall(r'<tr class="[^"]*">.*?<td [^>]*>.*?<a href="/view/\d+" title="([^"]+)">.*?</a>.*?</td>.*?<td [^>]*>.*?<a href="(magnet:\?xt=urn:btih:([^&]+)[^"]*)">.*?</a>.*?</td>.*?<td [^>]*>([^<]+)</td>.*?<td [^>]*>([^<]+)</td>', html, re.S)
            
            for name, magnet, info_hash, size, seeders in items:
                if cancel_event and cancel_event.is_set():
                    break
                if info_hash in seen_hashes:
                    continue
                
                try:
                    s_count = int(seeders)
                except:
                    s_count = 0
                    
                streams.append({
                    'name': name,
                    'title': f"{name}\n👤 {s_count} 💾 {size} ⚙️ NYAA",
                    'url': magnet,
                    'infoHash': info_hash,
                    'quality': 'HD',
                    'provider': 'NYAA',
                    'release_title': name,
                    'seeders': s_count,
                    'size': size
                })
                seen_hashes.add(info_hash)
                
        except Exception as e:
            xbmc.log(f"[NYAA] Error fetching {query}: {e}", xbmc.LOGDEBUG)
            logger.scraper_error("NYAA", f"Search Error: {e}", url)
            
        if streams:
            xbmc.log(f"[NYAA] Sucesso: {len(streams)} resultados encontrados para {query}.", xbmc.LOGINFO)
            # If you already found results for this pattern, you don't need to try the next query
            break
            
    if streams:
        logger.scraper_sources("NYAA", len(streams), streams[:3] if streams else [])
            
    return streams
