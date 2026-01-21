# -*- coding: utf-8 -*-
import os
import requests
import xbmcaddon
import xbmcvfs
import xbmc
import shutil
import time

# Inițializare Addon
addon = xbmcaddon.Addon()
profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
subs_path = os.path.join(profile_path, 'subs').replace('\\', '/')

def setup_subs_folder():
    """Funcție adăugată pentru a fi văzută de fișierul principal"""
    if os.path.exists(subs_path):
        try:
            shutil.rmtree(subs_path)
            xbmc.log(f"[WyzieSub] Folderul {subs_path} a fost sters.", xbmc.LOGINFO)
        except: pass
    time.sleep(0.5)
    if not os.path.exists(subs_path):
        try: os.makedirs(subs_path)
        except: pass

# Preluăm setările conform settings.xml-ului tău
SUB_FORMAT = 'srt'
BASE_URL = 'https://sub.wyzie.ru/search'

def search_subtitles(imdb_id, season=None, episode=None):
    subtitles_list = []
    
    # Mapare pentru ID-ul tău: subtitles_language (Romana|Engleza)
    lang_pref = addon.getSetting('subtitles_language')
    lang = "ro" if "Romana" in lang_pref or not lang_pref else "en"

    params = {
        'id': imdb_id,
        'language': lang,
        'format': SUB_FORMAT
    }

    if season and episode:
        params['season'] = str(season)
        params['episode'] = str(episode)

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        if response.ok:
            data = response.json()
            if isinstance(data, dict):
                if 'url' in data: subtitles_list.append(data)
            elif isinstance(data, list):
                subtitles_list.extend(data)
    except: pass

    return subtitles_list

def download_subtitle(sub, folder_path):
    try:
        url = sub.get('url')
        if not url: return ''

        media_name = sub.get('media', 'video')
        lang = sub.get('language', 'ro')
        fmt = sub.get('format', 'srt')
        timestamp = int(time.time() * 100) % 10000 
        
        filename = f"{media_name}.{lang}.{timestamp}.{fmt}"
        safe_filename = "".join(c for c in filename if c not in r'\/:*?"<>|')
        path = os.path.join(folder_path, safe_filename).replace('\\', '/')

        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            return path
    except: pass
    return ''
