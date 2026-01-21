# -*- coding: utf-8 -*-
import os, json, xbmc, xbmcgui, xbmcvfs, xbmcaddon, requests, re, hashlib, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
DATA_STORAGE = xbmcvfs.translatePath(os.path.join('special://profile/addon_data/', ADDON_ID, 'server_cache'))

if not xbmcvfs.exists(DATA_STORAGE):
    xbmcvfs.mkdirs(DATA_STORAGE)

SERVERS = {
    "f4k_struct": ("http://69.154.203.11:8008/4kmovies/", "movie"),
    "s4k_struct": ("http://69.154.203.11:8008/4ktvshows/", "tv"),
    "fs_struct":  ("http://69.154.203.11:8008/movies/", "movie"),
    "ss_struct":  ("http://69.154.203.11:8008/tvshows/", "tv")
}

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

def manage_news(news_file, sorted_by_server, cache_name):
    """Salvează TOATE noutățile și verifică după ID sau Titlu dacă ID-ul lipsește"""
    existing_news = []
    if xbmcvfs.exists(news_file):
        try:
            with xbmcvfs.File(news_file, 'r') as f:
                raw = f.read()
                if raw: existing_news = json.loads(raw)
        except: pass

    # 1. Creăm un set de referință cu ce avem deja salvat
    # Folosim ID-ul dacă există, altfel Titlul.
    def get_unique_key(item):
        t_id = item.get('tmdb_id')
        if t_id and str(t_id).strip():
            return f"ID_{str(t_id).strip()}"
        return f"TITLE_{str(item.get('title', '')).strip()}"

    old_keys = {get_unique_key(x) for x in existing_news}
    
    # 2. Numărăm noutățile din lista de pe server (verificăm tot ce vine nou)
    new_found_count = 0
    for item in sorted_by_server:
        current_key = get_unique_key(item)
        if current_key not in old_keys:
            new_found_count += 1

    # 3. Curățăm datele (eliminăm câmpul 'age' din toată lista)
    for item in sorted_by_server:
        if "age" in item:
            del item["age"]

    # 4. SALVĂM TOATE ELEMENTELE (fără limită, sortate după time_stamp)
    try:
        with xbmcvfs.File(news_file, 'w') as f:
            f.write(json.dumps(sorted_by_server, indent=2).encode('utf-8'))
        
        # 5. Notificare dacă am găsit noutăți (bazat pe ID sau Titlu)
        if new_found_count > 0:
            xbmcgui.Dialog().notification(
                "Cinema City 2026", 
                f"S-au găsit {new_found_count} titluri noi în {cache_name.upper()}!", 
                xbmcgui.NOTIFICATION_INFO, 
                5000
            )
            xbmc.log(f"[Cinema City] Noutati: {new_found_count} titluri noi detectate pentru {cache_name}", xbmc.LOGINFO)
    except: pass

def update_all_databases():
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("Cinema City 2026", "Actualizare baze de date și noutăți?"):
        return

    try:
        import addon_logic
    except ImportError:
        sys.path.append(xbmcvfs.translatePath(os.path.join(ADDON.getAddonInfo('path'), 'resources', 'lib')))
        import addon_logic

    progress = xbmcgui.DialogProgress()
    progress.create("Cinema City", "Sincronizare server...")
    headers = {'User-Agent': 'CinemaCity/2.0 (2026)'}

    for i, (key, (url, m_type)) in enumerate(SERVERS.items()):
        if progress.iscanceled(): break
        progress.update(int((i / len(SERVERS)) * 100), f"Procesare: {key.upper()}")
        
        try:
            r = requests.get(url, timeout=15, headers=headers)
            if r.status_code != 200: continue
            
            save_path = os.path.join(DATA_STORAGE, f"{key}.json")
            news_path = os.path.join(DATA_STORAGE, f"news_{key}.json")

            rows = re.findall(r'href="([^?][^"]+/)"[^>]*>.*?</a>\s+([\w-]+\s[\d:]+)', r.text)
            valid_folders = [{'f': f, 's_date': d} for f, d in rows if f not in ['/', '../']]

            def process(entry):
                item = addon_logic.fetch_single_item(entry['f'], m_type)
                if item: 
                    item['server_date'] = entry['s_date']
                    item['time_stamp'] = create_numeric_timestamp(entry['s_date'])
                return item

            with ThreadPoolExecutor(max_workers=5) as exec:
                results = [f.result() for f in [exec.submit(process, e) for e in valid_folders] if f.result()]

            # 1. SORTARE CRONOLOGICĂ (Pentru News)
            # Folosim str() pentru a asigura sortarea corectă a timestamp-ului numeric
            time_list = sorted(results, key=lambda x: str(x.get('time_stamp', '0')), reverse=True)

            # 2. GESTIONARE NOUTĂȚI (Salvare în news_*.json fără limită de 40)
            manage_news(news_path, time_list, key)

            # 3. GENERARE CACHE PRINCIPAL (Sortat după data lansării)
            final_list = sorted(results, key=lambda x: x.get('date', '0000-00-00'), reverse=True)
            with xbmcvfs.File(save_path, 'w') as f:
                f.write(json.dumps({'hash': hashlib.md5(r.text.encode()).hexdigest(), 'items': final_list}, indent=2).encode('utf-8'))
                
        except Exception as e:
            xbmc.log(f"EROARE {key}: {str(e)}", xbmc.LOGERROR)

    progress.close()
    dialog.notification("Cinema City", "Actualizare completă!", xbmcgui.NOTIFICATION_INFO, 4000)
