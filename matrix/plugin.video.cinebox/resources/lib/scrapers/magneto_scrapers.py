# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xbmcvfs
import sys
import os
import threading
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """Scraper Magneto following the Stremio standard required by Cinebox."""
    streams = []
    try:
        # 1. Finds the path of the Magneto module
        try:
            magneto_path = xbmcvfs.translatePath('special://home/addons/script.module.magneto/lib')
        except AttributeError:
            magneto_path = xbmc.translatePath('special://home/addons/script.module.magneto/lib')

        if not os.path.exists(magneto_path):
            return streams

        if magneto_path not in sys.path:
            sys.path.append(magneto_path)

        try:
            import magneto
        except ImportError:
            return streams
        
        # 2. Prepare data for Magneto
        data = {
            'title': item_data.get('title') if item_data else 'Video',
            'year': str(item_data.get('year')) if item_data else '',
            'imdb': imdb_id,
            'tmdb': item_data.get('tmdb_id') if item_data else '',
            'aliases': [],
        }
        
        if media_type == 'tvshow':
            data['tvshowtitle'] = data['title']
            data['season'] = str(season)
            data['episode'] = str(episode)
            if item_data and item_data.get('episode_title'):
                data['title'] = item_data.get('episode_title')

        # 3. Get qualified providers
        magneto_sources = magneto.sources()
        if not magneto_sources:
            return streams

        # 4. Run scrapers in parallel
        all_results = []
        lock = threading.Lock()
        threads = []
        
        def run_source(s_class):
            if cancel_event and cancel_event.is_set():
                return
            try:
                s_obj = s_class()
                res = s_obj.sources(data, {})
                if res:
                    with lock:
                        all_results.extend(res)
            except:
                pass

        for name, source_class in magneto_sources:
            if cancel_event and cancel_event.is_set():
                break
            t = threading.Thread(target=run_source, args=(source_class,))
            t.start()
            threads.append(t)
            
        for t in threads:
            if cancel_event and cancel_event.is_set():
                # We can't kill threads in Python easily, but we can stop waiting
                break
            t.join(timeout=15)
            
        # 5. Converts to the STREMIO standard (which Cinebox loves)
        for s in all_results:
            url = s.get('url')
            if not url: continue
            
            name = s.get('name', 'Source Magneto')
            quality = s.get('quality', 'HD')
            size = s.get('size', '')
            if size == 'N/A': size = ''
            seeders = s.get('seeders', 0)
            provider = s.get('provider', 'Magneto')
            
            # Cinebox extracts information from the 'title' field using regex.
            # Format: "File Name\n👤 Seeders | ⚙️ Provider | Quality | Size"
            stremio_title = f"{name}\n👤 {seeders} | ⚙️ {provider} | {quality} | {size}"
            
            stream = {
                'name': f"Magneto\n{provider}",
                'title': stremio_title,
                'url': url,
                'provider': provider,
                'hoster': 'Magneto'
            }
            
            # If it's torrent, Cinebox likes infoHash
            if url.startswith('magnet:'):
                import re
                hash_match = re.search(r'btih:([a-fA-F0-9]{40})', url)
                if hash_match:
                    stream['infoHash'] = hash_match.group(1)
            
            # Essential field for Cinebox not to discard the item
            stream['release_title'] = name
            
            streams.append(stream)
            
    except Exception as e:
        xbmc.log(f"[Magneto-Scraper] Error: {e}", xbmc.LOGERROR)
        logger.scraper_error("Magneto", f"Error: {e}")
        
    if streams:
        logger.scraper_sources("Magneto", len(streams), streams[:3] if streams else [])
        
    return streams
