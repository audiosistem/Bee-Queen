import xbmcgui, xbmcplugin, xbmcvfs, xbmcaddon, json, urllib.request, urllib.parse, hashlib, time, os
import api_config
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

def list_movies(handle, base_url, page, query=None):
    xbmcplugin.setContent(handle, 'movies')
    page = int(page)
    if query:
        url = f"{api_config.BASE_URL}/search/movie?api_key={api_config.API_KEY}&language=en-US&query={urllib.parse.quote(query)}&page={page}"
    else:
        url = f"{api_config.BASE_URL}/movie/popular?api_key={api_config.API_KEY}&language=en-US&page={page}"
    
    data = get_tmdb_json(url)
    if not data or 'results' not in data: return xbmcplugin.endOfDirectory(handle)

    for item in data.get('results', []):
        name = item.get('title')
        tmdb_id = item.get('id')
        if not name or not tmdb_id: continue

        li = xbmcgui.ListItem(label=name)
        
        art = {}
        if item.get('poster_path'):
            img = f"{api_config.IMG_BASE}{item.get('poster_path')}"
            art.update({'poster': img, 'thumb': img, 'icon': img})
        if item.get('backdrop_path'):
            art['fanart'] = f"{api_config.IMG_BASE}{item.get('backdrop_path')}"
        li.setArt(art)
        
        info = li.getVideoInfoTag()
        info.setTitle(name)
        info.setPlot(item.get('overview', 'Fără descriere disponibilă.'))
        try:
            rating = float(item.get('vote_average', 0))
            info.setRating(rating)
        except:
            pass
        info.setVotes(item.get('vote_count', 0))
        info.setOriginalTitle(item.get('original_title', ''))
        info.setMediaType('movie')
        
        year_str = item.get('release_date', '')
        if year_str:
            try: info.setYear(int(year_str[:4]))
            except: pass
        
        u = f"{base_url}?action=play&tmdb_id={tmdb_id}&type=movie&title={urllib.parse.quote(name)}"
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(handle, u, li, False)
            
    if page < data.get('total_pages', 1):
        # Modificare pentru a păstra parametrul query în URL-ul paginii următoare
        q_param = f"&query={urllib.parse.quote(query)}" if query else ""
        next_url = f"{base_url}?action=movies&page={page + 1}{q_param}"
        xbmcplugin.addDirectoryItem(handle, next_url, xbmcgui.ListItem(label="[COLOR yellow]>>> Pagina Următoare[/COLOR]"), True)
    xbmcplugin.endOfDirectory(handle)
