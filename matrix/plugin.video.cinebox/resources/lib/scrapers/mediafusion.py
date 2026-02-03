# -*- coding: utf-8 -*-
import urllib.request as urllib2
import urllib.parse
import json
import xbmc
import re
import gzip
from io import BytesIO
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None):
    """Mediafusion Scraper for Cinemabox."""
    base_url = "https://mediafusion.elfhosted.com"
    
    endpoints = []
    if imdb_id:
        if media_type == 'movie':
            endpoints.append(f"/stream/movie/{imdb_id}.json")
        elif media_type == 'tvshow':
            endpoints.append(f"/stream/series/{imdb_id}:{season}:{episode}.json")

    streams = []
    seen_hashes = set()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'encoded_user_data': 'eyJlbmFibGVfY2F0YWxvZ3MiOiBmYWxzZSwgIm1heF9zdHJlYW1zX3Blcl9yZXNvbHV0aW9uIjogOTksICJ0b3JyZW50X3NvcnRpbmdfcHJpb3JpdHkiOiBbXSwgImNlcnRpZmljYXRpb25fZmlsdGVyIjogWyJEaXNhYmxlIl0sICJudWRpdHlfZmlsdGVyIjogWyJEaXNhYmxlIl19'
    }
    
    # Add search by title if we don't have IMDB or as a complement
    if not imdb_id or not endpoints:
        search_query = item_data.get('original_title') or item_data.get('title')
        if search_query:
            year = item_data.get('year')
            if media_type == 'tvshow':
                query = f"{search_query} S{int(season):02d}E{int(episode):02d}"
            else:
                query = f"{search_query} {year}"
            endpoints.append(f"/stream/{media_type}/{urllib.parse.quote(query)}.json")

    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        # Fix for double slash URLs
        url = url.replace('//stream', '/stream')
        try:
            xbmc.log(f"[Mediafusion] Buscando via urllib2: {url}", xbmc.LOGINFO)
            logger.network(url, method='GET')
            req = urllib2.Request(url, headers=headers)
            with urllib2.urlopen(req, timeout=15) as response:
                xbmc.log(f"[Mediafusion] Resposta de {url}: Status {response.getcode()}", xbmc.LOGINFO)
                logger.network(url, method='GET', status=response.getcode(), response="OK" if response.getcode() == 200 else "Error")
                
                data_raw = response.read()
                if response.info().get('Content-Encoding') == 'gzip':
                    data_raw = gzip.GzipFile(fileobj=BytesIO(data_raw)).read()
                data = json.loads(data_raw.decode('utf-8'))
            
            found = data.get('streams', [])
            for stream in found:
                info_hash = stream.get('infoHash')
                if not info_hash:
                    url_field = stream.get('url', '')
                    hash_match = re.search(r'\b([a-fA-F0-9]{40})\b', url_field)
                    if hash_match:
                        info_hash = hash_match.group(1)
                
                if not info_hash:
                    continue
                
                info_hash = info_hash.lower()
                if info_hash in seen_hashes:
                    continue
                
                name = stream.get('title', '').split('\n')[0] or stream.get('name', '')
                quality = '720p'
                if '2160p' in name.lower() or '4k' in name.lower(): quality = '4K'
                elif '1080p' in name.lower(): quality = '1080p'
                
                streams.append({
                    'name': name,
                    'title': f"{name}\n[COLOR red]HOSTER:[/COLOR] Mediafusion",
                    'url': stream.get('url') or f"magnet:?xt=urn:btih:{info_hash}",
                    'infoHash': info_hash,
                    'quality': quality,
                    'provider': 'Mediafusion',
                    'release_title': name,
                    'type': 'torrent'
                })
                seen_hashes.add(info_hash)
                
        except Exception as e:
            xbmc.log(f"[Mediafusion] Error fetching {url}: {e}", xbmc.LOGERROR)
            logger.scraper_error("Mediafusion", f"Search Error: {e}", url)
            
    return streams
