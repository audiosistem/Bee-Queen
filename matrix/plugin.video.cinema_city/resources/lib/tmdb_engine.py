# -*- coding: utf-8 -*-
import json, urllib.request, urllib.parse, re, hashlib, time, os, xbmcvfs, xbmcaddon, xbmc
import api_config

# Definire CACHE_DIR global
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
        clean_name = re.split(r'[\(\[]', raw)[0].replace('.', ' ').strip()
        tmdb_id_match = re.search(r'(?:tmdb-|tmdbid=)(\d+)', raw)
        
        if tmdb_id_match:
            t_id = tmdb_id_match.group(1)
            t_url = f"{api_config.BASE_URL}/{m_type}/{t_id}?api_key={api_config.API_KEY}&language=en-US&append_to_response=external_ids"
        else:
            t_url = f"{api_config.BASE_URL}/search/{m_type}?api_key={api_config.API_KEY}&query={urllib.parse.quote(clean_name)}&language=en-US"
        
        d = get_tmdb_json(t_url)
        res = {}
        if d:
            if 'results' in d and len(d['results']) > 0:
                temp_id = d['results'][0]['id']
                t_url_ext = f"{api_config.BASE_URL}/{m_type}/{temp_id}?api_key={api_config.API_KEY}&append_to_response=external_ids"
                res = get_tmdb_json(t_url_ext)
            elif 'id' in d:
                res = d

        if not res or 'id' not in res:
            return {'f': f, 'tmdb_id': None, 'imdb_id': None, 'title': raw, 'plot': '', 'poster': '', 'fanart': '', 'date': '0000-00-00', 'rating': 0}

        imdb_id = res.get('external_ids', {}).get('imdb_id') or res.get('imdb_id', '')
        img_prefix = api_config.IMG_BASE if api_config.IMG_BASE.endswith('/') else api_config.IMG_BASE + '/'
        date_k = 'release_date' if m_type == 'movie' else 'first_air_date'
        
        return {
            'f': f, 'tmdb_id': res.get('id'), 'imdb_id': imdb_id,
            'title': res.get('title') or res.get('name') or raw,
            'plot': res.get('overview', ''), 'rating': res.get('vote_average', 0),
            'poster': f"{img_prefix}{res.get('poster_path')}" if res.get('poster_path') else "",
            'fanart': f"{img_prefix}{res.get('backdrop_path')}" if res.get('backdrop_path') else "",
            'date': res.get(date_k, '0000-00-00')
        }
    except:
        return {'f': f, 'tmdb_id': None, 'imdb_id': None, 'title': f, 'plot': '', 'poster': '', 'fanart': '', 'date': '0000-00-00', 'rating': 0}
