# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs
import sys
import os
import threading
import re
from resources.lib.config_manager import get_enabled_scraper
from resources.lib.debug_logger import logger

def get_module_display_name(module_id):
    """Gets the friendly name of the module from addon.xml"""
    try:
        try:
            addons_path = xbmcvfs.translatePath('special://home/addons/')
        except AttributeError:
            addons_path = xbmc.translatePath('special://home/addons/')
        
        addon_xml = os.path.join(addons_path, module_id, 'addon.xml')
        if os.path.exists(addon_xml):
            with open(addon_xml, 'r', encoding='utf-8') as f:
                content = f.read()
                name_match = re.search(r'name="([^"]+)"', content)
                if name_match:
                    return name_match.group(1)
    except:
        pass
    
    return module_id

def scrape_module(module_id, imdb_id, media_type, season, episode, item_data, cancel_event=None):
    """Performs scraping on a specific module.
    Returns list of streams found."""
    streams = []
    try:
        xbmc.log(f"[External-Scraper] Starting module scrape: {module_id}", xbmc.LOGINFO)
        logger.scraper(module_id, f"Iniciando scrape - IMDB: {imdb_id}, Tipo: {media_type}")
        
        # Find the module
        try:
            addons_path = xbmcvfs.translatePath('special://home/addons/')
        except AttributeError:
            addons_path = xbmc.translatePath('special://home/addons/')
        
        # Try multiple common paths to Kodi addons lib folder
        possible_paths = [
            os.path.join(addons_path, module_id, 'lib'),
            os.path.join(addons_path, module_id),
            os.path.join(addons_path, module_id, 'resources', 'lib')
        ]
        
        module_path = None
        for p in possible_paths:
            if os.path.exists(p):
                module_path = p
                break
        
        if not module_path:
            xbmc.log(f"[External-Scraper] No library paths found for {module_id}", xbmc.LOGERROR)
            logger.scraper_error(module_id, f"Path not found in: {possible_paths}")
            return streams
            
        xbmc.log(f"[External-Scraper] Usando caminho: {module_path}", xbmc.LOGINFO)
        
        if module_path not in sys.path:
            sys.path.insert(0, module_path) # Insert at the beginning to prioritize the correct module
        
        # Extract module name
        mod_name = module_id.split('.')[-1]
        xbmc.log(f"[External-Scraper] Module name: {mod_name}", xbmc.LOGINFO)
        
        # Import the module
        module = None
        try:
            xbmc.log(f"[External-Scraper] Tentando importar: {mod_name}", xbmc.LOGINFO)
            module = __import__(mod_name)
            xbmc.log(f"[External-Scraper] Module imported successfully", xbmc.LOGINFO)
        except ImportError as e:
            xbmc.log(f"[External-Scraper] ImportError ao importar {mod_name}: {e}", xbmc.LOGERROR)
            logger.scraper_error(module_id, f"ImportError: {e}")
            try:
                import importlib.util
                init_file = os.path.join(module_path, "__init__.py")
                xbmc.log(f"[External-Scraper] Tentando importar via spec: {init_file}", xbmc.LOGINFO)
                spec = importlib.util.spec_from_file_location(mod_name, init_file)
                if spec:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    xbmc.log(f"[External-Scraper] Module imported via spec successfully", xbmc.LOGINFO)
            except Exception as e2:
                xbmc.log(f"[External-Scraper] Error when importing via spec: {e2}", xbmc.LOGERROR)
                return streams
        
        if not module:
            xbmc.log(f"[External-Scraper] Unable to import {mod_name}", xbmc.LOGERROR)
            return streams
        
        # Check if you have a sources function
        if not hasattr(module, 'sources'):
            xbmc.log(f"[External-Scraper] {mod_name} no function'sources'", xbmc.LOGERROR)
            return streams
        
        # Prepare data with aliases to improve search
        title = item_data.get('title') if item_data else 'Video'
        original_title = item_data.get('original_title') or title
        year = str(item_data.get('year')) if item_data else ''
        
        # Generate aliases (title variations to improve search in PT-BR and EN)
        aliases = []
        if title:
            aliases.append(title)
            if year: aliases.append(f"{title} {year}")
            
        if original_title and original_title != title:
            aliases.append(original_title)
            if year: aliases.append(f"{original_title} {year}")
            
        # Add variations with dots (common in torrents)
        if title:
            aliases.append(title.replace(' ', '.'))
        if original_title:
            aliases.append(original_title.replace(' ', '.'))
        
        data = {
            'title': title,
            'year': year,
            'imdb': imdb_id or '',
            'tmdb': str(item_data.get('tmdb_id', '')) if item_data else '',
            'tvdb': str(item_data.get('tvdb_id', '')) if item_data else '',
            'original_title': original_title,
            'originaltitle': original_title,
            'premiered': item_data.get('premiered', '') if item_data else '',
            'aliases': list(set(aliases)), # Remove duplicates
        }
        
        if media_type == 'tvshow':
            data['tvshowtitle'] = data['title']
            data['season'] = str(season)
            data['episode'] = str(episode)
            if item_data and item_data.get('episode_title'):
                data['title'] = item_data.get('episode_title')
        
        xbmc.log(f"[External-Scraper] Dados preparados: {data}", xbmc.LOGINFO)
        
        # Get sources
        try:
            external_sources = module.sources()
            xbmc.log(f"[External-Scraper] Sources obtidas: {len(external_sources) if external_sources else 0}", xbmc.LOGINFO)
            logger.scraper(module_id, f"Sources obtidas: {len(external_sources) if external_sources else 0}")
        except Exception as e:
            xbmc.log(f"[External-Scraper] Error getting sources: {e}", xbmc.LOGERROR)
            logger.scraper_error(module_id, f"Error getting sources: {e}")
            return streams
        
        if not external_sources:
            xbmc.log(f"[External-Scraper] Nenhuma source encontrada", xbmc.LOGWARNING)
            return streams
        
        # Get module friendly name
        module_display_name = get_module_display_name(module_id)
        xbmc.log(f"[External-Scraper] Module name: {module_display_name}", xbmc.LOGINFO)
        
        # Run in parallel
        all_results = []
        lock = threading.Lock()
        threads = []
        
        def run_source(s_class, retry_count=0):
            if cancel_event and cancel_event.is_set():
                return
            max_retries = 2
            try:
                s_obj = s_class()
                res = s_obj.sources(data, {})
                if res:
                    with lock:
                        all_results.extend(res)
                    xbmc.log(f"[External-Scraper] Source retornou {len(res)} resultados", xbmc.LOGINFO)
                    logger.scraper(module_id, f"Source retornou {len(res)} resultados")
                else:
                    # Do not retry if nothing is returned (it is legitimate to have no results)
                    xbmc.log(f"[External-Scraper] Source returned no results (normal)", xbmc.LOGINFO)
            except Exception as e:
                error_msg = str(e)
                # Detailed error log
                xbmc.log(f"[External-Scraper] Error in source (attempt {retry_count + 1}): {error_msg}", xbmc.LOGERROR)
                logger.scraper_error(module_id, f"Error in source: {error_msg}")
                
                # If it is a log_utils error, do not try to retry (internal scraper bug)
                if 'log_utils' in error_msg:
                    xbmc.log(f"[External-Scraper] log_utils error detected - skipping source with bug", xbmc.LOGWARNING)
                    return
                
                # For other errors, try retry
                if retry_count < max_retries:
                    try:
                        run_source(s_class, retry_count + 1)
                    except:
                        pass
        
        xbmc.log(f"[External-Scraper] Iniciando {len(external_sources)} threads", xbmc.LOGINFO)
        for name, source_class in external_sources:
            if cancel_event and cancel_event.is_set():
                break
            t = threading.Thread(target=run_source, args=(source_class,))
            t.start()
            threads.append(t)
        
        # Wait for threads with a total timeout of 60s
        import time
        start_time = time.time()
        max_wait = 60
        
        for t in threads:
            if cancel_event and cancel_event.is_set():
                break
            elapsed = time.time() - start_time
            remaining = max(1, max_wait - elapsed)
            t.join(timeout=remaining)
        
        # Check threads that are still active
        active_threads = sum(1 for t in threads if t.is_alive())
        if active_threads > 0:
            xbmc.log(f"[External-Scraper] {active_threads} threads still active after timeout", xbmc.LOGWARNING)
        
        xbmc.log(f"[External-Scraper] Total de resultados: {len(all_results)}", xbmc.LOGINFO)
        logger.scraper_sources(module_id, len(all_results), all_results[:3] if all_results else [])
        
            # Convert to CINEBOX standard
        for s in all_results:
            url = s.get('url')
            if not url: continue
            
            name = s.get('name', f'Fonte {module_display_name}')
            quality = s.get('quality', 'HD')
            size = s.get('size', '')
            if size == 'N/A': size = ''
            seeders = s.get('seeders', 0)
            
            # The specific provider that the scraper found (e.g. YTS, 1337x, RARBG)
            real_provider = s.get('provider', module_display_name)
            
            stremio_title = f"{name}\n👤 {seeders} | ⚙️ {real_provider} | {quality} | {size}"
            
            stream = {
                'name': f"{module_display_name}\n{real_provider}",
                'title': stremio_title,
                'url': url,
                'release_title': name,
                'provider': real_provider,
                'hoster': module_display_name
            }
            
            if url.startswith('magnet:'):
                hash_match = re.search(r'btih:([a-fA-F0-9]{40})', url)
                if hash_match:
                    stream['infoHash'] = hash_match.group(1)
            
            streams.append(stream)
    
    except Exception as e:
        xbmc.log(f"[External-Scraper] General error: {e}", xbmc.LOGERROR)
        logger.scraper_error(module_id, f"General error: {e}")
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    
    xbmc.log(f"[External-Scraper] Retornando {len(streams)} streams", xbmc.LOGINFO)
    logger.scraper(module_id, f"Retornando {len(streams)} streams finais")
    return streams

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """Runs the enabled external scraper."""
    # Clear module cache to avoid using old version
    import sys
    modules_to_remove = [m for m in sys.modules.keys() if 'magneto' in m.lower() or 'viper' in m.lower() or 'coco' in m.lower()]
    for mod in modules_to_remove:
        if mod in sys.modules:
            del sys.modules[mod]
    
    enabled_scraper_id = get_enabled_scraper()
    
    xbmc.log(f"[External-Scraper] Scraper habilitado: {enabled_scraper_id}", xbmc.LOGINFO)
    
    if not enabled_scraper_id or enabled_scraper_id == 'script.module.magneto':
        xbmc.log("[External-Scraper] No external scraper selected or using default.", xbmc.LOGINFO)
        return []
    
    xbmc.log(f"[External-Scraper] Executando Scraper Universal: {enabled_scraper_id}", xbmc.LOGINFO)
    
    # Try to run the selected module
    if enabled_scraper_id == 'script.module.jackett':
        from .jackett import scrape as jackett_scrape
        streams = jackett_scrape(imdb_id, media_type, season, episode, item_data, cancel_event)
    else:
        streams = scrape_module(enabled_scraper_id, imdb_id, media_type, season, episode, item_data, cancel_event)
    
    xbmc.log(f"[External-Scraper] Retornou {len(streams)} fontes", xbmc.LOGINFO)
    return streams
