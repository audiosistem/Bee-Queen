# -*- coding: utf-8 -*-
import xbmcgui, xbmcaddon, xbmcplugin, xbmcvfs, json, urllib.request, urllib.parse, api_config, hashlib, time, os

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

def list_tvshows(handle, base_url, page, query=None):
    xbmcplugin.setContent(handle, 'tvshows')
    page = int(page)
    url = f"{api_config.BASE_URL}/search/tv" if query else f"{api_config.BASE_URL}/tv/popular"
    url += f"?api_key={api_config.API_KEY}&language=en-US&page={page}"
    if query: url += f"&query={urllib.parse.quote(query)}"
    
    data = get_tmdb_json(url)
    for item in data.get('results', []):
        name = item.get('name')
        tv_id = item.get('id')
        li = xbmcgui.ListItem(label=name)
        
        # Artă
        art = {'poster': f"{api_config.IMG_BASE}{item.get('poster_path')}", 
               'fanart': f"{api_config.IMG_BASE}{item.get('backdrop_path')}"}
        li.setArt(art)
        
        # Info
        info = li.getVideoInfoTag()
        info.setTitle(name)
        info.setPlot(item.get('overview', ''))
        info.setMediaType('tvshow')
        
        u = f"{base_url}?action=list_seasons&tv_id={tv_id}&title={urllib.parse.quote(name)}"
        xbmcplugin.addDirectoryItem(handle, u, li, True)

    # Paginație pentru căutare/popular
    if data.get('total_pages', 1) > page:
        q_param = f"&query={urllib.parse.quote(query)}" if query else ""
        next_url = f"{base_url}?action=tvshows&page={page + 1}{q_param}"
        xbmcplugin.addDirectoryItem(handle, next_url, xbmcgui.ListItem(label="[COLOR yellow]>>> Pagina Următoare[/COLOR]"), True)
        
    xbmcplugin.endOfDirectory(handle)

def list_seasons(handle, base_url, tv_id, tv_title):
    xbmcplugin.setContent(handle, 'seasons')
    url = f"{api_config.BASE_URL}/tv/{tv_id}?api_key={api_config.API_KEY}&language=en-US"
    data = get_tmdb_json(url)
    fanart = f"{api_config.IMG_BASE}{data.get('backdrop_path')}"
    
    for s in data.get('seasons', []):
        s_num = s.get('season_number')
        li = xbmcgui.ListItem(label=s.get('name'))
        
        img = f"{api_config.IMG_BASE}{s.get('poster_path')}" if s.get('poster_path') else fanart
        li.setArt({'poster': img, 'thumb': img, 'fanart': fanart})
        
        info = li.getVideoInfoTag()
        info.setTitle(s.get('name'))
        info.setPlot(s.get('overview', ''))
        info.setMediaType('season')
        
        u = f"{base_url}?action=list_episodes&tv_id={tv_id}&season_num={s_num}&title={urllib.parse.quote(tv_title)}"
        xbmcplugin.addDirectoryItem(handle, u, li, True)
    xbmcplugin.endOfDirectory(handle)

def list_episodes(handle, base_url, tv_id, season_num, tv_title):
    xbmcplugin.setContent(handle, 'episodes')
    url = f"{api_config.BASE_URL}/tv/{tv_id}/season/{season_num}?api_key={api_config.API_KEY}&language=en-US"
    data = get_tmdb_json(url)
    
    for ep in data.get('episodes', []):
        name = f"{ep.get('episode_number')}. {ep.get('name')}"
        li = xbmcgui.ListItem(label=name)
        
        img = f"{api_config.IMG_BASE}{ep.get('still_path')}" if ep.get('still_path') else ""
        li.setArt({'thumb': img, 'poster': img, 'fanart': img})
        
        info = li.getVideoInfoTag()
        info.setTitle(name)
        info.setPlot(ep.get('overview', ''))
        info.setMediaType('episode')
        
        u = f"{base_url}?action=play&tmdb_id={tv_id}&type=tv&season={season_num}&episode={ep.get('episode_number')}&title={urllib.parse.quote(tv_title)}"
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(handle, u, li, False)
    xbmcplugin.endOfDirectory(handle)
