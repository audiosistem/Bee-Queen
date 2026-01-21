# -*- coding: utf-8 -*-
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import requests
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

import api_config
import tmdb_engine

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

base_path = f'special://profile/addon_data/{ADDON_ID}/cache/'

CACHE_DIR = xbmcvfs.translatePath(base_path)

if not xbmcvfs.exists(CACHE_DIR):
    xbmcvfs.mkdirs(CACHE_DIR)

def get_tmdb_json(url):
    h = hashlib.md5(url.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{h}.json")
    if xbmcvfs.exists(cache_file):
        try:
            stats = xbmcvfs.Stat(cache_file)
            if (time.time() - stats.st_mtime()) < 43200:
                with xbmcvfs.File(cache_file, 'r') as f: return json.loads(f.read())
        except: pass
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            with xbmcvfs.File(cache_file, 'w') as f: f.write(json.dumps(data))
            return data
    except: return {}

def fetch_single_item(f, m_type):
    try:
        raw = urllib.parse.unquote(f).rstrip('/')
        # 1. Curățăm numele pentru o căutare precisă
        # Elimină tot ce este între paranteze sau acolade (an, id-uri greșite etc.)
        clean_name = re.split(r'[\(\[\{\}]', raw)[0].replace('.', ' ').strip()
        
        # 2. Extragem ID-ul scris în folder (chiar dacă suspectăm că e greșit)
        tmdb_id_match = re.search(r'(?:tmdb-|tmdbid=)(\d+)', raw)
        extracted_id = int(tmdb_id_match.group(1)) if tmdb_id_match else None
        
        res = None
        
        # PASUL A: Verificăm dacă ID-ul din folder este valid pentru tipul curent (m_type)
        if extracted_id:
            t_url = f"{api_config.BASE_URL}/{m_type}/{extracted_id}?api_key={api_config.API_KEY}&language=en-US&append_to_response=external_ids"
            temp_res = get_tmdb_json(t_url)
            if temp_res and 'id' in temp_res:
                res = temp_res

        # PASUL B: Dacă ID-ul a fost greșit (ex: ID de film în folder de seriale), CĂUTĂM după nume
        if not res:
            # Căutăm direct în categoria corectă (movie sau tv) definită de m_type
            s_url = f"{api_config.BASE_URL}/search/{m_type}?api_key={api_config.API_KEY}&query={urllib.parse.quote(clean_name)}&language=en-US"
            search_data = get_tmdb_json(s_url)
            
            if search_data and search_data.get('results'):
                # TMDB returnează mai multe rezultate. Îl luăm pe primul care se potrivește numelui,
                # deoarece filtrarea pe m_type (movie/tv) este deja făcută de URL-ul de search.
                best_match = search_data['results'][0]
                final_id = best_match.get('id')
                
                # Luăm datele complete pentru ID-ul corect găsit
                full_url = f"{api_config.BASE_URL}/{m_type}/{final_id}?api_key={api_config.API_KEY}&append_to_response=external_ids"
                res = get_tmdb_json(full_url)

        # 3. Construim rezultatul final cu datele corectate
        if res and 'id' in res:
            imdb_id = res.get('external_ids', {}).get('imdb_id') or res.get('imdb_id')
            img_prefix = api_config.IMG_BASE
            if not img_prefix.endswith('/'): img_prefix += '/'
            
            # Determinăm data în funcție de tip
            date_val = res.get('release_date') if m_type == 'movie' else res.get('first_air_date')
            
            return {
                'f': f, 
                'tmdb_id': res.get('id'), # Aici va fi ID-ul corect (de serial dacă ești în TV)
                'imdb_id': imdb_id,
                'title': res.get('title') or res.get('name') or clean_name,
                'plot': res.get('overview', ''), 
                'rating': res.get('vote_average', 0),
                'poster': f"{img_prefix}{res.get('poster_path')}" if res.get('poster_path') else "",
                'fanart': f"{img_prefix}{res.get('backdrop_path')}" if res.get('backdrop_path') else "",
                'date': date_val if date_val else '0000-00-00'
            }
        
        # 4. Fallback dacă nu găsim nimic nici prin search
        return {
            'f': f, 'tmdb_id': extracted_id, 'imdb_id': None, 'title': clean_name,
            'plot': '', 'poster': '', 'fanart': '', 'date': '0000-00-00', 'rating': 0
        }

    except Exception as e:
        xbmc.log(f"[Cinema City] Eroare procesare {f}: {str(e)}", xbmc.LOGERROR)
        return {'f': f, 'tmdb_id': None, 'title': raw, 'plot': '', 'poster': '', 'fanart': '', 'date': '0000-00-00', 'rating': 0}

def create_numeric_timestamp(date_str):
    """Transformă '24-Sep-2025 18:34' în '202509241834'"""
    if not date_str: return "0"
    try:
        months = {
            'Jan':'01', 'Feb':'02', 'Mar':'03', 'Apr':'04', 'May':'05', 'Jun':'06',
            'Jul':'07', 'Aug':'08', 'Sep':'09', 'Oct':'10', 'Nov':'11', 'Dec':'12'
        }
        p = date_str.replace(':', '-').replace(' ', '-').split('-')
        zi = p[0].zfill(2)
        luna = months.get(p[1], '01')
        an = p[2]
        ora = p[3].zfill(2)
        minut = p[4].zfill(2)
        return an + luna + zi + ora + minut
    except:
        return "0"

def process_server(handle, base_url, params, s_url, m_type, cache_name):
    xbmcplugin.setContent(handle, 'movies' if m_type == 'movie' else 'tvshows')
    page = int(params.get('page', '1'))
    addon = xbmcaddon.Addon()
    
    PROFILE_PATH = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    CACHE_DIR = os.path.join(PROFILE_PATH, 'server_cache').replace('\\', '/')
    
    STRUCTURE_CACHE = os.path.join(CACHE_DIR, f"{cache_name}.json").replace('\\', '/')
    NEWS_CACHE = os.path.join(CACHE_DIR, f"news_{cache_name}.json").replace('\\', '/')
    RES_PATH = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo('path')), 'resources', 'lib', 'json_default', f"{cache_name}.json").replace('\\', '/')

    if not xbmcvfs.exists(CACHE_DIR):
        xbmcvfs.mkdirs(CACHE_DIR)

    # 1. COPIERE DIN DEFAULT (Am eliminat TIME_CACHE)
    if not xbmcvfs.exists(STRUCTURE_CACHE) and xbmcvfs.exists(RES_PATH):
        xbmcvfs.copy(RES_PATH, STRUCTURE_CACHE)
        if not xbmcvfs.exists(NEWS_CACHE): 
            # Notă: Dacă nu ai un default pt news, poți copia tot RES_PATH sau lăsa gol
            xbmcvfs.copy(RES_PATH, NEWS_CACHE)

    items = []
    is_news = "list_news" in params.get('action', '')
    current_db = NEWS_CACHE if is_news else STRUCTURE_CACHE

    exists_local = xbmcvfs.exists(current_db)

    try:
        if exists_local:
            with xbmcvfs.File(current_db, 'r') as f:
                raw_data = f.read()
                if raw_data:
                    c_json = json.loads(raw_data)
                    items = c_json.get('items', c_json) if isinstance(c_json, dict) else c_json
            xbmc.log(f"[Cinema City] Incarcat din: {current_db}", xbmc.LOGINFO)
        
        elif not is_news:
            xbmc.log(f"[Cinema City] Verificam serverul pentru {cache_name}...", xbmc.LOGINFO)
            r = requests.get(s_url, headers={'User-Agent': 'CinemaCity/2.0'}, timeout=10)
            if r.status_code == 200:
                curr_hash = hashlib.md5(r.text.encode()).hexdigest()
                
                rows = re.findall(r'href="([^?][^"]+/)"[^>]*>.*?</a>\s+([\w-]+\s[\d:]+)', r.text)
                valid_folders = [{'f': f, 's_date': d} for f, d in rows if f not in ['/', '../']]
                
                def worker(entry):
                    res = fetch_single_item(entry['f'], m_type)
                    if res:
                        res['server_date'] = entry['s_date']
                        res['time_stamp'] = create_numeric_timestamp(entry['s_date'])
                    return res

                with ThreadPoolExecutor(max_workers=5) as executor:
                    unsorted = [i for i in list(executor.map(worker, valid_folders)) if i]
                
                # --- LOGICA NOUĂ: FĂRĂ FILE_TIME ---
                
                # 1. Sortăm pentru NEWS (după time_stamp) și actualizăm news_cache
                # Trimitem lista sortată direct către manage_news
                new_items_by_time = sorted(unsorted, key=lambda x: str(x.get('time_stamp', '0')), reverse=True)
                manage_news(NEWS_CACHE, new_items_by_time, [])

                # 2. Sortăm pentru STRUCTURĂ (după Data Lansare) și salvăm
                items = sorted(unsorted, key=lambda x: x.get('date', '0000-00-00'), reverse=True)
                with xbmcvfs.File(STRUCTURE_CACHE, 'w') as f: 
                    f.write(json.dumps({'hash': curr_hash, 'items': items}, indent=2))

    except Exception as e:
        xbmc.log(f"[Cinema City] Eroare: {str(e)}", xbmc.LOGWARNING)
    
    # Restul codului pentru afișare în Kodi (directory items)...

      
    if not items:
        xbmc.log(f"[Cinema City] Niciun item găsit în {current_db}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle)
        return

    try:
        subset = items[(page-1)*20 : page*20]
        for e in subset:
            full_date = ""
            raw_date = e.get('date', '0000-00-00')
            if raw_date and raw_date != '0000-00-00' and '-' in raw_date:
                d = raw_date.split('-')
                full_date = f" [COLOR orange]({d[2]}-{d[1]}-{d[0]})[/COLOR]"
            
            li = xbmcgui.ListItem(label=f"{e.get('title', 'Necunoscut')}{full_date}")
            li.setArt({'poster': e.get('poster'), 'fanart': e.get('fanart'), 'thumb': e.get('poster')})
            
            info = li.getVideoInfoTag()
            info.setTitle(e.get('title', ''))
            info.setPlot(e.get('plot', ''))
            info.setRating(float(e.get('rating', 0)))
            info.setMediaType('movie' if m_type == 'movie' else 'tvshow')
            if raw_date != '0000-00-00': info.setPremiered(raw_date)           
            imdb_id = e.get('imdb_id', '')
            action = 'list_server_seasons' if m_type == 'tv' else 'list_movie_files'
            u = f"{base_url}?action={action}&tv_id={e.get('tmdb_id')}&imdb={imdb_id}"
            u += f"&url={urllib.parse.quote(s_url+e.get('f', ''))}"
            u += f"&title={urllib.parse.quote(e.get('title', ''))}"
            u += f"&poster={urllib.parse.quote(e.get('poster', ''))}"
            u += f"&fanart={urllib.parse.quote(e.get('fanart', ''))}"
            u += f"&plot={urllib.parse.quote(e.get('plot', ''))}"
            
            xbmcplugin.addDirectoryItem(handle, u, li, True)
                
        if len(items) > page*20:
            next_url = f"{base_url}?action={params['action']}&page={page+1}"
            for k, v in params.items():
                if k not in ['action', 'page']: next_url += f"&{k}={v}"
            xbmcplugin.addDirectoryItem(handle, next_url, xbmcgui.ListItem(label="[COLOR yellow]>>> Pagina Următoare[/COLOR]"), True)
            
    except Exception as e:
        xbmc.log(f"EROARE AFIȘARE: {str(e)}", xbmc.LOGERROR)
        
    xbmcplugin.endOfDirectory(handle)

# -*- coding: utf-8 -*-
import json, xbmcvfs, xbmc

def manage_news(news_file, new_items, old_items):
    """
    Actualizează fișierul de noutăți cu TOATE elementele, sortate după time_stamp.
    """
    # 1. Citim ce aveam salvat anterior
    existing_news = []
    if xbmcvfs.exists(news_file):
        try:
            with xbmcvfs.File(news_file, 'r') as f:
                raw = f.read()
                if raw: existing_news = json.loads(raw)
        except: existing_news = []

    # 2. Extragem ID-urile vechi pentru notificare
    old_ids = {str(x.get('tmdb_id')) for x in old_items if x.get('tmdb_id')}
    news_ids = {str(x.get('tmdb_id')) for x in existing_news if x.get('tmdb_id')}
    
    # 3. Luăm TOATE titlurile de pe server (fără limitare la 40)
    # Și le sortăm după time_stamp descrescător (cele mai mari/recente valori primele)
    all_server_items = sorted(
        new_items, 
        key=lambda x: str(x.get('time_stamp', '0')), 
        reverse=True
    )
    
    # 4. Numărăm titlurile noi
    new_found_count = 0
    for item in all_server_items:
        t_id = str(item.get('tmdb_id'))
        if t_id not in old_ids and t_id not in news_ids:
            new_found_count += 1

    # 5. Curățăm datele (eliminăm câmpul 'age')
    for item in all_server_items:
        if "age" in item:
            del item["age"]

    # 6. Salvăm fișierul complet
    try:
        with xbmcvfs.File(news_file, 'w') as f:
            f.write(json.dumps(all_server_items, indent=2))
            
        if new_found_count > 0:
            xbmc.log(f"[Cinema City] Update: Am gasit {new_found_count} titluri noi.", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Cinema City] Eroare scriere news: {str(e)}", xbmc.LOGERROR)

    return all_server_items



def list_server_seasons(handle, base_url, params):
    xbmcplugin.setContent(handle, 'seasons')
    tv_id = params.get('tv_id')
    tv_title = params.get('title')
    imdb_id = params.get('imdb', '')

    raw_url = params.get('s_url') or params.get('url')
    if not raw_url:
        return xbmcplugin.endOfDirectory(handle)
    s_url = urllib.parse.unquote(raw_url)
    
    url_tmdb = f"{api_config.BASE_URL}/tv/{tv_id}?api_key={api_config.API_KEY}&language=en-US"
    data = get_tmdb_json(url_tmdb)
    
    show_fanart = f"{api_config.IMG_BASE}{data.get('backdrop_path')}" if data.get('backdrop_path') else ""
    show_poster = f"{api_config.IMG_BASE}{data.get('poster_path')}" if data.get('poster_path') else ""

    for s in data.get('seasons', []):
        s_num = s.get('season_number')
        if s_num == 0: continue # Sărim peste Speciale
        
        name = s.get('name')
        li = xbmcgui.ListItem(label=name)
        
        # Imaginea sezonului (sau a serialului dacă sezonul n-are poster)
        season_poster = f"{api_config.IMG_BASE}{s.get('poster_path')}" if s.get('poster_path') else show_poster
        
        # Setăm arta pentru interfață
        li.setArt({
            'poster': season_poster, 
            'thumb': season_poster, 
            'fanart': show_fanart
        })
        
        info = li.getVideoInfoTag()
        info.setTitle(name)
        info.setPlot(s.get('overview', ''))
        info.setMediaType('season')
        if imdb_id:
            info.setUniqueID(imdb_id, "imdb")
            info.setIMDBNumber(imdb_id)
            
        season_folder = f"Season {int(s_num):02d}/"
        full_season_url = s_url + season_folder if s_url.endswith('/') else s_url + "/" + season_folder
        
        # --- MODIFICARE CRITICĂ: Trimitem poster și fanart către list_server_episodes ---
        u = f"{base_url}?action=list_server_episodes&tv_id={tv_id}&season_num={s_num}"
        u += f"&s_url={urllib.parse.quote(full_season_url)}"
        u += f"&title={urllib.parse.quote(tv_title)}"
        u += f"&poster={urllib.parse.quote(season_poster)}"
        u += f"&fanart={urllib.parse.quote(show_fanart)}"
        u += f"&imdb={imdb_id or ''}"
        
        xbmcplugin.addDirectoryItem(handle, u, li, True)
        
    xbmcplugin.endOfDirectory(handle)

def list_server_episodes(handle, base_url, params):
    xbmcplugin.setContent(handle, 'episodes')
    tv_id = params.get('tv_id')
    s_num = params.get('season_num')
    tv_title = params.get('title')
    s_url = urllib.parse.unquote(params.get('s_url'))
    imdb_id = params.get('imdb')
    
    # PRELUĂM posterul și fanart-ul serialului primite de la nivelul Sezon/Serial
    show_poster = params.get('poster', '')
    show_fanart = params.get('fanart', '')
    
    url = f"{api_config.BASE_URL}/tv/{tv_id}/season/{s_num}?api_key={api_config.API_KEY}&language=en-US"
    data = get_tmdb_json(url)
    
    for ep in data.get('episodes', []):
        ep_num = ep.get('episode_number')
        air_date = ep.get('air_date', '')  # Extragem data lansării
        name = f"{ep_num}. {ep.get('name')}"
        
        li = xbmcgui.ListItem(label=name)
        # Thumb-ul episodului (imaginea din episod)
        still_img = f"{api_config.IMG_BASE}{ep.get('still_path')}" if ep.get('still_path') else show_poster
        
        # Setăm arta pentru listă
        li.setArt({
            'thumb': still_img, 
            'poster': show_poster, 
            'fanart': show_fanart
        })
        
        info = li.getVideoInfoTag()
        info.setTitle(name)
        info.setPlot(ep.get('overview', ''))
        info.setMediaType('episode')
        info.setSeason(int(s_num))
        info.setEpisode(int(ep_num))
        
        # ADAUGARE DATA LANSARE
        if air_date:
            info.setPremiered(air_date)
        
        if imdb_id:
            info.setUniqueID(imdb_id, "imdb")
            info.setIMDBNumber(imdb_id)
            
        pattern = f"S{int(s_num):02d}E{int(ep_num):02d}"
        
        # CONSTRUCȚIE URL: Pasăm posterul, fanart-ul și plot-ul către list_episode_files
        u = f"{base_url}?action=list_episode_files"
        u += f"&url={urllib.parse.quote(s_url)}"
        u += f"&pattern={pattern}"
        u += f"&title={urllib.parse.quote(tv_title + ' - ' + name if tv_title else name)}"
        u += f"&poster={urllib.parse.quote(show_poster)}"
        u += f"&fanart={urllib.parse.quote(show_fanart)}"
        u += f"&plot={urllib.parse.quote(ep.get('overview', ''))}"
        u += f"&imdb={imdb_id or ''}"
        
        xbmcplugin.addDirectoryItem(handle, u, li, True)
        
    xbmcplugin.endOfDirectory(handle)


def list_episode_files(handle, base_url, params):
    # IMPORTANT: Schimbăm în 'episodes' pentru a activa metadatele în player
    xbmcplugin.setContent(handle, 'episodes')
    
    folder_url = urllib.parse.unquote(params.get('url', ''))
    pattern = params.get('pattern', '')
    imdb_id = params.get('imdb', '')
    
    # Preluăm metadatele de la pasul anterior (Sezoane)
    show_title = params.get('title', '')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    plot = params.get('plot', '')
    
    import re
    s_val, e_val = 0, 0
    match = re.search(r'S(\d+)E(\d+)', pattern, re.I)
    if match:
        s_val, e_val = int(match.group(1)), int(match.group(2))

    try:
        r = requests.get(folder_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        regex = r'href="([^"]*' + re.escape(pattern) + r'[^"]+\.(?:mkv|mp4|avi|mov))".*?\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2}\s+(\d+)'
        matches = re.findall(regex, r.text, re.I | re.S)
        
        for link, size in matches:
            try:
                s_float = float(size)
                display_size = f" [COLOR cyan][{s_float / (1024**3):.2f} GB][/COLOR]" if s_float > 1024**3 else f" [COLOR cyan][{s_float / (1024**2):.2f} MB][/COLOR]"
            except:
                display_size = ""
            
            clean_name = urllib.parse.unquote(link)
            
            # Eticheta listei rămâne numele fișierului
            li = xbmcgui.ListItem(label=f"{clean_name}{display_size}")
            
            # SETĂM ARTA (Posterul serialului)
            li.setArt({
                'poster': poster,
                'thumb': poster,
                'fanart': fanart,
                'icon': poster
            })
            
            info = li.getVideoInfoTag()
            # Titlul în player va fi: "Nume Serial - S01E01" sau numele fișierului
            info.setTitle(f"{show_title} - {pattern}" if show_title else clean_name)
            info.setPlot(plot)
            info.setMediaType('episode')
            if s_val: info.setSeason(s_val)
            if e_val: info.setEpisode(e_val)
            if imdb_id:
                info.setUniqueID(imdb_id, "imdb")
                info.setIMDBNumber(imdb_id)
                
            li.setProperty('IsPlayable', 'true')
            
            # CONSTRUCȚIE URL COMPLETĂ CĂTRE PLAYER
            u = f"{base_url}?action=play_direct"
            u += f"&url={urllib.parse.quote(folder_url + link)}"
            u += f"&title={urllib.parse.quote(show_title + ' - ' + pattern if show_title else clean_name)}"
            u += f"&poster={urllib.parse.quote(poster)}"
            u += f"&fanart={urllib.parse.quote(fanart)}"
            u += f"&plot={urllib.parse.quote(plot)}"
            u += f"&imdb={imdb_id or ''}"
            
            xbmcplugin.addDirectoryItem(handle, u, li, False)
    except Exception as e: 
        xbmc.log(f"EROARE EPISODE FILES: {str(e)}", xbmc.LOGERROR)
        
    xbmcplugin.endOfDirectory(handle)


def list_movie_files(handle, base_url, params):
    xbmcplugin.setContent(handle, 'files')
    folder_url = urllib.parse.unquote(params.get('url'))
    # Preluăm TOATE metadatele primite de la process_server
    movie_title = params.get('title')
    imdb_id = params.get('imdb')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    plot = params.get('plot', '')

    try:
        r = requests.get(folder_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        # Regex-ul tău pentru fișiere și mărime
        matches = re.findall(r'href="([^"]+\.(?:mkv|mp4|avi|mov))".*?\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2}\s+(\d+)', r.text, re.I | re.S)
        
        for link, size in matches:
            try:
                s_val = float(size)
                display_size = f" [COLOR cyan][{s_val / (1024**3):.2f} GB][/COLOR]" if s_val > 0 else ""
            except:
                display_size = ""

            clean_filename = urllib.parse.unquote(link)
            # Label-ul rămâne numele fișierului + mărime, dar titlul intern va fi cel TMDB
            li = xbmcgui.ListItem(label=f"{clean_filename}{display_size}")
            
            # SETĂM ARTA (Posterul) și aici, pentru a se vedea în listă
            li.setArt({'poster': poster, 'fanart': fanart, 'thumb': poster})
            
            info = li.getVideoInfoTag()
            # IMPORTANT: Folosim titlul de la TMDB, nu numele fișierului
            info.setTitle(movie_title if movie_title else clean_filename)
            info.setPlot(plot)
            if imdb_id:
                info.setUniqueID(imdb_id, "imdb")
                info.setIMDBNumber(imdb_id)

            li.setProperty('IsPlayable', 'true')
            
            # --- MODIFICARE CHEIE: Trimitem TOȚI parametrii către play_direct ---
            u = f"{base_url}?action=play_direct"
            u += f"&url={urllib.parse.quote(folder_url + link)}"
            u += f"&title={urllib.parse.quote(movie_title or clean_filename)}"
            u += f"&poster={urllib.parse.quote(poster)}"
            u += f"&fanart={urllib.parse.quote(fanart)}"
            u += f"&plot={urllib.parse.quote(plot)}"
            u += f"&imdb={imdb_id or ''}"
            
            xbmcplugin.addDirectoryItem(handle, u, li, False)
    except Exception as e:
        xbmc.log(f"[Cinema City] Eroare listare fișiere: {str(e)}", xbmc.LOGERROR)
        
    xbmcplugin.endOfDirectory(handle)

def play_direct(handle, params):
    # 1. Preluăm URL-ul și metadatele
    video_url = urllib.parse.unquote(params.get('url'))
    imdb_id = params.get('imdb')
    title = urllib.parse.unquote(params.get('title', 'Video'))
    poster = urllib.parse.unquote(params.get('poster', ''))
    fanart = urllib.parse.unquote(params.get('fanart', ''))
    plot = urllib.parse.unquote(params.get('plot', ''))
    
    # Curățăm URL-ul (spații -> %20)
    safe_url = video_url.replace(' ', '%20')

    # 2. Creăm ListItem (offscreen=True este mai rapid pentru redare directă)
    li = xbmcgui.ListItem(label=title, path=safe_url)
    
    # 3. SETĂM IMAGINILE
    li.setArt({
        'poster': poster,
        'thumb': poster,
        'fanart': fanart,
        'icon': poster
    })
    
    # 4. Setăm InfoTag (Compatibil Kodi 20, 21 Omega și versiunile 2026+)
    info = li.getVideoInfoTag()
    info.setTitle(title)
    info.setPlot(plot)
    info.setMediaType('movie')
    
    # Adăugăm ID-ul IMDB
    if imdb_id and str(imdb_id).lower() != 'none' and imdb_id != '':
        full_imdb = imdb_id if str(imdb_id).startswith('tt') else f"tt{imdb_id}"
        info.setIMDBNumber(full_imdb)
        info.setUniqueID(full_imdb, "imdb")

    # Extragem anul din titlu
    year_match = re.search(r'(\d{4})', title)
    if year_match:
        info.setYear(int(year_match.group(1)))

    # --- LOGICĂ PLAYER (HLS vs MP4/MKV/HEVC) ---
    # Verificăm dacă este HLS (.m3u8). Dacă sunt MP4/MKV/HEVC, sărim peste asta.
    if '.m3u8' in safe_url.lower() or params.get('filetype') == 'hls':
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        # User-Agent-ul previne erorile 403 Forbidden pe stream-uri live
        li.setProperty('inputstream.adaptive.stream_headers', 'User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    # 5. Marcăm ca redabil
    li.setProperty('IsPlayable', 'true')
    
    # Trimitem URL-ul final către Kodi
    xbmcplugin.setResolvedUrl(handle, True, li)


def list_f4k(h, b, p): process_server(h, b, p, "http://69.154.203.11:8008/4kmovies/", "movie", "f4k_struct")
def list_s4k(h, b, p): process_server(h, b, p, "http://69.154.203.11:8008/4ktvshows/", "tv", "s4k_struct")
def list_fs(h, b, p):  process_server(h, b, p, "http://69.154.203.11:8008/movies/", "movie", "fs_struct")
def list_ss(h, b, p):  process_server(h, b, p, "http://69.154.203.11:8008/tvshows/", "tv", "ss_struct")
# Acțiuni pentru NOUTĂȚI (ianuarie 2026)
def list_news_f4k(h, b, p): process_server(h, b, p, "http://69.154.203.11:8008/4kmovies/", "movie", "f4k_struct")
def list_news_s4k(h, b, p): process_server(h, b, p, "http://69.154.203.11:8008/4ktvshows/", "tv", "s4k_struct")
def list_news_fs(h, b, p):  process_server(h, b, p, "http://69.154.203.11:8008/movies/", "movie", "fs_struct")
def list_news_ss(h, b, p):  process_server(h, b, p, "http://69.154.203.11:8008/tvshows/", "tv", "ss_struct")



def search_hybrid(handle, base_url, params, m_type):
    # 1. Dialog Input
    query = xbmcgui.Dialog().input('Caută Film/Serial...', type=xbmcgui.INPUT_ALPHANUM)
    if not query: return

    # Configurare căi cache
    ADDON = xbmcaddon.Addon()
    ADDON_ID = ADDON.getAddonInfo('id')
    CACHE_DIR = xbmcvfs.translatePath(f'special://profile/addon_data/{ADDON_ID}/server_cache/')

    # 2. Locații scanare (Mapăm fișierul local și URL-ul de server)
    if m_type == 'movie':
        scan_locations = [
            {"q": "HD", "url": "http://69.154.203.11:8008/movies/", "file": "fs_struct.json"},
            {"q": "4K", "url": "http://69.154.203.11:8008/4kmovies/", "file": "f4k_struct.json"}
        ]
    else:
        scan_locations = [
            {"q": "HD", "url": "http://69.154.203.11:8008/tvshows/", "file": "ss_struct.json"},
            {"q": "4K", "url": "http://69.154.203.11:8008/4ktvshows/", "file": "s4k_struct.json"}
        ]

    server_map = {} 
    for loc in scan_locations:
        found_local = False
        file_path = os.path.join(CACHE_DIR, loc['file'])
        
        if xbmcvfs.exists(file_path):
            try:
                with xbmcvfs.File(file_path, 'r') as f:
                    data_json = json.loads(f.read())
                    if data_json and "items" in data_json:
                        for item in data_json['items']:
                            tid = str(item.get('tmdb_id', '')).strip()
                            if tid:
                                if tid not in server_map: server_map[tid] = []
                                server_map[tid].append({"quality": loc['q'], "full_path": loc['url'] + item['f']})
                        found_local = True
            except: pass

        if not found_local:
            try:
                r = requests.get(loc['url'], timeout=10)
                matches = re.findall(r'href=["\']([^"\'>]*(?:tmdb-|tmdbid=)(\d+)[^"\'>]*)["\']', r.text)
                for folder_url, tmdb_id in matches:
                    tid = str(tmdb_id).strip()
                    if tid not in server_map: server_map[tid] = []
                    server_map[tid].append({"quality": loc['q'], "full_path": loc['url'] + folder_url})
            except: continue

    # 3. Căutare TMDB (2 pagini)
    all_results = []
    for page in range(1, 3):
        t_url = f"{api_config.BASE_URL}/search/{m_type}?api_key={api_config.API_KEY}&query={urllib.parse.quote(query)}&page={page}&language=en-US"
        data = get_tmdb_json(t_url)
        if data and data.get('results'): all_results.extend(data['results'])
        if not data or data.get('total_pages', 1) < page: break

    xbmcplugin.setContent(handle, 'movies' if m_type == 'movie' else 'tvshows')
    items_added = 0
    processed_ids = set()

    for item in all_results:
        t_id = str(item.get('id')).strip()
        if t_id in processed_ids: continue
        processed_ids.add(t_id)
        
        if t_id in server_map:
            sources = server_map[t_id]
            title = item.get('title') or item.get('name')
            original_title = item.get('original_title') or item.get('original_name')
            plot = item.get('overview', 'Fără descriere.')
            poster = f"{api_config.IMG_BASE}{item.get('poster_path')}" if item.get('poster_path') else ""
            fanart = f"{api_config.IMG_BASE}{item.get('backdrop_path')}" if item.get('backdrop_path') else ""
            rating = item.get('vote_average', 0.0)
            # Extragere an (YYYY)
            release_date = item.get('release_date') or item.get('first_air_date') or ""
            year = int(release_date.split('-')[0]) if '-' in release_date else 0
            
            # Luăm ID-ul IMDB
            imdb_id = ""
            try:
                ext_url = f"{api_config.BASE_URL}/{m_type}/{t_id}/external_ids?api_key={api_config.API_KEY}"
                ext_data = get_tmdb_json(ext_url)
                imdb_id = ext_data.get('imdb_id', '')
            except: pass

            for s in sources:
                color = "gold" if s['quality'] == "4K" else "green"
                label = f"[COLOR {color}][{s['quality']}][/COLOR] {title}"
                if year: label += f" [COLOR grey]({year})[/COLOR]"
                
                li = xbmcgui.ListItem(label=label)
                li.setArt({'poster': poster, 'thumb': poster, 'fanart': fanart, 'banner': fanart})
                
                # Populăm toate metadatele disponibile în VideoInfoTag
                info = li.getVideoInfoTag()
                info.setTitle(title)
                info.setOriginalTitle(original_title)
                info.setPlot(plot)
                info.setYear(year)
                info.setRating(rating)
                info.setPremiered(release_date)
                info.setMediaType('movie' if m_type == 'movie' else 'tvshow')
                
                if imdb_id:
                    info.setUniqueID(imdb_id, "imdb")
                    info.setIMDBNumber(imdb_id)
                
                # Parametri URL extenși cu toate datele TMDB pentru acțiunea următoare
                q_params = {
                    'action': 'list_server_seasons' if m_type == 'tv' else 'list_movie_files',
                    'url': s['full_path'],
                    'title': title,
                    'year': year,
                    'imdb': imdb_id,
                    'tmdb': t_id,
                    'poster': poster,
                    'fanart': fanart,
                    'plot': plot,
                    'rating': rating,
                    'm_type': m_type,
                    'quality': s['quality']
                }
                
                u = f"{base_url}?" + urllib.parse.urlencode(q_params)
                xbmcplugin.addDirectoryItem(handle, u, li, True)
                items_added += 1

    if items_added == 0:
        xbmcgui.Dialog().ok("Cinema City", "Nicio potrivire găsită pe server.")

    xbmcplugin.endOfDirectory(handle)

