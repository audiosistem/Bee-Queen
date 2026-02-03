
# -*- coding: utf-8 -*-
import sys
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import json
import re
# from .db import db
from .utils import create_video_item
from . import scrapers
from .dialogs import DialogSelecaoFontes
from .resolver import CineboxResolverWindow
from urllib.parse import urlencode, unquote_plus, quote_plus
import urllib.request
import re
import threading
import time
import subprocess




# --- Essential Settings ---
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON = xbmcaddon.Addon()
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def get_url(**kwargs):
    """Creates a plugin URL for an action."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

# --- Language Mapping (if you still need it) ---
FLAG_TO_LANG = { '🇧🇷': 'BR', '🇵🇹': 'PT', '🇺🇸': 'EN', '🇬🇧': 'EN', '🇪🇸': 'ES', 'RO': 'RO'}
def extract_languages_from_title(title: str):
    languages = []
    flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', title)
    for flag in flags:
        lang = FLAG_TO_LANG.get(flag)
        if lang and lang not in languages:
            languages.append(lang)
    return languages if languages else ['N/A']

def parse_stream_title(title):
    """Extracts title details from the Torrentio source."""
    details = {}
    details['release_title'] = title.split('\n')[0].strip()
    size_match = re.search(r'\[\s*(\d+\.?\d*\s*(GB|MB))\s*\]', title, re.IGNORECASE)
    if size_match: details['size'] = size_match.group(1)
    peers_match = re.search(r'👤\s*(\d+)', title)
    if peers_match: details['peers'] = peers_match.group(1)
    provider_match = re.search(r'⚙️\s*([^\n]+)', title)
    if provider_match: details['provider'] = provider_match.group(1).strip()
    return details
    
def show_main_menu(menu_structure):
    """Creates and displays main menu items on the screen."""
    xbmcplugin.setPluginCategory(HANDLE, 'Main Menu')
    fanart_addon = ADDON.getAddonInfo('fanart')
    

    for item in menu_structure:

        li = xbmcgui.ListItem(label=item['title'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        # --- BLOCK ADDED TO SHOW ICON ---
        from .icons import get_icon_url
        icon = item.get('icon')
        if icon:
            # Supports IMDb icon IDs
            if isinstance(icon, str) and len(icon) < 15 and not icon.endswith('.png'):
                # It's an icon ID, converts to URL
                icon_url = get_icon_url(icon)
                li.setArt({'thumb': icon_url, 'icon': icon_url})
            else:
                # It's a local path
                li.setArt({'thumb': icon, 'icon': icon})
        # None
        
        # Add Plot/Description if exists
        plot = item.get('plot', '')
        if plot:
            li.setInfo('video', {'plot': plot})
        
        # Arctic Fuse 2 uses properties to identify special menus
        if item['action'] == 'favorites_menu':
            li.setProperty('IsSpecial', 'true')
            
        url = get_url(action=item['action'])
        
        # ✅ FIX: If the action is to open settings, it should not be treated as a folder
        is_folder = True
        if item['action'] == 'open_settings':
            is_folder = False
            
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)
        
    # Finalizes the directory so that the items appear on the screen.
    xbmcplugin.endOfDirectory(HANDLE)
    
# In navigation.py

def show_my_list_menu():
    xbmcplugin.setPluginCategory(HANDLE, "My List")
    fanart_addon = ADDON.getAddonInfo('fanart')
    # Some skins like Arctic Fuse 2 prefer 'movies' or 'tvshows' to render widgets correctly
    # but since this is a folder menu, we'll use 'files' or leave the default if 'folder' fails.
    xbmcplugin.setContent(HANDLE, 'files')

    items = [
        ("Movies", get_url(action="favorites_movies"), 'DefaultMovies.png'),
        ("TV Shows", get_url(action="favorites_tvshows"), 'DefaultTVShows.png')
    ]

    for label, url, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': icon, 'thumb': icon})
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        # Add properties that modern skins use to identify content type
        li.setProperty('IsPlayable', 'false')
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def show_favorite_movies():
    xbmcplugin.setPluginCategory(HANDLE, "My List • Movies")
    xbmcplugin.setContent(HANDLE, 'movies')

    try:
        from .db.db import db_instance
        favorites = db_instance.get_favorites_by_type('movie')

        if not favorites:
            xbmcgui.Dialog().notification("My List", "No movies found", xbmcgui.NOTIFICATION_INFO)
            return xbmcplugin.endOfDirectory(HANDLE, False)

        for item in favorites:
            from .movies import _create_movie_item_tuple
            url, li, is_folder = _create_movie_item_tuple(item)
            # Force mediatype to ensure skin recognizes
            li.setInfo('video', {'mediatype': 'movie'})
            # Extra property for modern skins
            li.setProperty('mediatype', 'movie')
            xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)
    except Exception as e:
        xbmc.log(f"[Cinebox] Error listing favorite movies: {e}", xbmc.LOGERROR)

    xbmcplugin.endOfDirectory(HANDLE)

def show_favorite_tvshows():
    xbmcplugin.setPluginCategory(HANDLE, "My List • TV Shows")
    xbmcplugin.setContent(HANDLE, 'tvshows')

    try:
        from .db.db import db_instance
        favorites = db_instance.get_favorites_by_type('tvshow')

        if not favorites:
            xbmcgui.Dialog().notification("My List", "No series found", xbmcgui.NOTIFICATION_INFO)
            return xbmcplugin.endOfDirectory(HANDLE, False)

        for item in favorites:
            from .tvshows import _create_show_tuple
            url, li, is_folder = _create_show_tuple(item)
            # Force mediatype and ensure series are treated as folders if necessary
            li.setInfo('video', {'mediatype': 'tvshow'})
            # Extra property for modern skins
            li.setProperty('mediatype', 'tvshow')
            
            # Arctic Fuse 2 and other modern skins require series to be folders to open seasons
            # If the URL is not a details URL, it MUST be a folder
            if 'action=show_details' not in url:
                is_folder = True
                
            xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)
    except Exception as e:
        xbmc.log(f"[Cinebox] Error listing favorite series: {e}", xbmc.LOGERROR)

    xbmcplugin.endOfDirectory(HANDLE)



   
    
def _fetch_json_from_url(url):
    """✅ OPTIMIZED: Helper function to download a JSON from a URL."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept-Encoding': 'gzip, deflate'  # ✅ NEW: Compression
        })
        # ✅ OPTIMIZATION: Timeout reduced from 15s to 8s
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        xbmc.log(f"[ERROR] Failed to fetch JSON from {url}: {e}", xbmc.LOGERROR)
    return None


def search(query=None, page=1):
    page = int(page)
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE

    # 1. Search input
    if not query:
        keyboard = xbmc.Keyboard('', 'Search Movie or Series')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            query = keyboard.getText().strip()
        else:
            return

    if not query:
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Searching: {query}')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'movies')

    from .tmdb_api import search_tmdb
    from .movies import _create_movie_item_tuple
    from .tvshows import _create_show_tuple
    # from .db import db

    items = []
    used_tmdb_ids = set()

    # 2. LOCAL SEARCH (without breaking subscription)
    try:
        from .db.db import db_instance
        local_results = db_instance.search_items(query)
    except Exception as e:
        xbmc.log(f"[Cinebox] Error search local: {e}", xbmc.LOGERROR)
        local_results = []

    # local manual paging
    local_page = local_results[offset: offset + PAGE_SIZE]

    for item in local_page:
        tmdb_id = item.get('tmdb_id')
        if tmdb_id:
            used_tmdb_ids.add(str(tmdb_id))

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    # 3. TMDB SEARCH (complementary)
    tmdb_results = search_tmdb(query, page=page) or []

    for item in tmdb_results:
        tmdb_id = str(item.get('id'))
        if tmdb_id in used_tmdb_ids:
            continue

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    if not items:
        xbmcgui.Dialog().notification("Search", f'Nothing found for "{query}"')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))

    # 4. Next page
    if len(items) >= PAGE_SIZE:
        next_url = get_url(
            action='search',
            query=query,
            page=page + 1
        )
        li = xbmcgui.ListItem(label='[COLOR red]Next Page >>[/COLOR]')
        li.setArt({'thumb': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)



# --- Providers with Priority Order ---
PROVIDERS = {
    "Brazuca": {
        "url": "https://94c8cb9f702d-brazuca-torrents.baby-beamup.club",
        "configurable": False,
        "priority": 1  # 🥇 FIRST - Brazuca
    },
    "AnimeZey": {
        "url": "https://1.animezey23112022.workers.dev", 
        "configurable": False, 
        "priority": 3  # 🥇 FIRST - AnimeZey
    },

    "SkyFlix": {
        "url": "https://da5f663b4690-skyflixfork16.baby-beamup.club",
        "configurable": False, 
        "priority": 1  # 🥈 SECOND - SkyFlix
    },
    "Torrentio": {
        "url": "https://torrentio.strem.fun",
        "configurable": True,
        "priority": 2  # 🥈 SECOND - Torrentio
    },
    "TorrentsDB": {
        "url": "https://torrentsdb.com",
        "configurable": False,
        "priority": 2  # Torrent - TorrentsDB
    },
    "ICV": {
        "url": "https://icv.stremio.dpdns.org/eyJ0bWRiX2tleSI6IjU0NjJmNzg0NjlmM2Q4MGJmNTIwMTY0NTI5NGMxNmU0IiwidXNlX2NvcnNhcm9uZXJvIjp0cnVlLCJ1c2VfdWluZGV4IjpmYWxzZSwidXNlX2tuYWJlbiI6dHJ1ZSwidXNlX3RvcnJlbnRnYWxheHkiOmZhbHNlLCJ1c2VfdG9ycmVudGlvIjp0cnVlLCJ1c2VfbWVkaWFmdXNpb24iOnRydWUsInVzZV9jb21ldCI6dHJ1ZSwidXNlX3JhcmJnIjp0cnVlLCJmdWxsX2l0YSI6ZmFsc2UsImRiX29ubHkiOmZhbHNlLCJ1c2VfZ2xvYmFsX2NhY2hlIjp0cnVlfQ==/manifest.json",
        "configurable": False,
        "priority": 2  # Torrent - ICV
    },
    "WebStreamr": {
        "url": "https://webstreamr.hayd.uk",
        "configurable": False,
        "priority": 1  # Direct Link - WebStreamr
    },
    "ComandoTop": {
        "url": "https://comandofilmestop.site",
        "configurable": False,
        "priority": 3  # 🥉 THIRD - ComandoTop
    },

    "UIndex": {
        "url": "https://uindex.org",
        "configurable": False,
        "priority": 6
    },
    "Perflix": {
        "url": "https://da5f663b4690-skyflixfork16.baby-beamup.club",
        "configurable": False,
        "priority": 2
    },
    "Nyaa": {
        "url": "https://nyaa.si",
        "configurable": False,
        "priority": 10
    },
    "StarckFilmes": {
        "url": "https://www.starckfilmes-v8.com",
        "configurable": False,
        "priority": 3
    },
    "BaixarFilmes": {
        "url": "https://baixafilmestorrent.org",
        "configurable": False,
        "priority": 3
    },
    "Magneto": {
        "url": "magneto",
        "configurable": False,
        "priority": 1
    }
}





# --- 1. SUPPORT FUNCTIONS (THEY MUST COME FIRST) ---

def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
    """Accurately extracts title languages ​​and returns compatible text indicators."""
    if not titulo: return '[COLOR grey]N/A[/COLOR]'
    t = titulo.lower()
    
    # Colored text indicators for better visualization
    tags = {
        'EN-US': '[COLOR green][EN][/COLOR]',
        'PT-BR': '[COLOR green][BR][/COLOR]',
        'DUAL': '[COLOR yellow][DUAL][/COLOR]',
        'LEG': '[COLOR white][EN][/COLOR]',
        'ITA': '[COLOR cyan][IT][/COLOR]',
        'SPA': '[COLOR orange][ES][/COLOR]',
        'FRE': '[COLOR blue][FR][/COLOR]',
        'GER': '[COLOR grey][DE][/COLOR]',
        'JAP': '[COLOR pink][JP][/COLOR]'
    }

    # 1. Original/English Audio Terms Check
    is_original = any(x in t for x in ['english', '.eng.', ' eng ', 'original', 'subbed', 'legendado', '.leg.', ' subs '])
    
    # 2. Checking dubbing/Portuguese/dual terms
    is_dubbed = any(x in t for x in ['dublado', '.dub.', ' dub ', 'portugues', 'Portuguese', 'pt-br', 'pt-pt', ' pt ', ' pt-pt ', 'nacional', 'portugal']) or '🇧🇷' in titulo or '🇵🇹' in titulo
    is_dual = any(x in t for x in ['dual', 'multi', 'tri-audio'])

    # 3. Decision logic by Provider and Title
    
    # Providers that are usually PT-BR
    provedores_br = ['SkyFlix', 'Brazuca', 'ComandoTop', 'AnimeZey', 'WebStreamr', 'Fonte Local']
    
    # Special case: Italian (ICV)
    if provider == 'ICV' or '.ita.' in t or ' italiano ' in t:
        if is_original or is_dual: return f"{tags['ITA']}{tags['LEG']} DUAL"
        return f"{tags['ITA']} ITA"

    # If it is DUAL, we mark it as DUAL regardless of the provider
    if is_dual:
        return f"{tags['DUAL']} DUAL"
    
    # If it is a Brazilian provider, the priority is PT-BR unless it explicitly says English
    if provider in provedores_br:
        if is_original and not is_dubbed:
            return f"{tags['LEG']} LEG"
        # If not explicitly original, we assume PT-BR for Brazilian sites
        return f"{tags['PT-BR']} PT-BR"

    # If it is an international provider (Torrentio, etc.)
    if is_dubbed:
        return f"{tags['PT-BR']} PT-BR"
    
    # Other specific languages
    if 'spa' in t or 'castellano' in t: return f"{tags['SPA']} SPA"
    if 'fre' in t or 'french' in t: return f"{tags['FRE']} FRE"
    if 'ger' in t or 'german' in t: return f"{tags['GER']} GER"
    if 'jap' in t or 'japanese' in t: return f"{tags['JAP']} JAP"
    
    # BLOCKING UNWANTED LANGUAGES (Polish, Indian, Russian, etc.)
    # If you encounter any of these terms, we mark it as BLOCKED for complete disposal
    # Adding more specific terms for Polish and other European languages
    blocked_terms = [
        'hindi', 'tamil', 'telugu', 'kannada', 'malayalam', 'punjabi', 'bengali', 'urdu', 'marathi', 
        'gujarati', 'bhojpuri', 'assamese', 'odia', 'sanskrit', 'nepali', 'sinhala', 'russian', 'rus', 
        'chinese', 'chi', 'kor', 'korean', 'polish', 'polski', 'poland', 'polska', '.pl.', ' pl ', 
        'lektor', 'dubbing', 'napisy', 'pl-dub', 'pl-sub', 'czech', 'hungarian', 'bulgarian', 
        'turkish', 'arabic', 'hebrew', 'nordic', 'swedish', 'danish', 'norwegian', 'finnish'
    ]
    
    # If it is a Brazilian provider, we are more permissive with generic terms
    # But if it is Torrentio/Internacional, the blocking is strict
    if any(x in t for x in blocked_terms):
        # Exception: If the title also clearly contains PT-BR or DUBBED, we may allow
        # but for Polish (lektor/pl) the blocking must be absolute
        if any(x in t for x in ['lektor', 'polski', 'pl-dub', 'pl-sub', '.pl.', ' pl ']):
            return 'BLOCKED'
        
        # If it is not explicitly PT-BR, it blocks
        if not is_dubbed and not is_dual:
            return 'BLOCKED'
    
    # Standard for Torrentio and other international
    # If we get here and it's not a BR provider, and we don't detect anything, we mark it as LEG
    # But if the title is too strange or has flags from other countries, we block it
    if provider not in provedores_br and not is_original and not is_dubbed:
        # If it has flags from other countries (except US/UK/BR/PT/RO), it blocks
        other_flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', titulo)
        for flag in other_flags:
            if flag not in ['🇧🇷', '🇵🇹', '🇺🇸', '🇬🇧', 'RO']:
                return 'BLOCKED'
                
    return f"{tags['LEG']} LEG"

def get_color_seeders(val, stream_type):
    if stream_type == 'Direct' or val == 999:
        return "[COLOR cyan]LINK DIRECT[/COLOR]", 999
    try:
        v = int(val)
        # ✅ CHANGE: Color set to yellow as requested
        color = "yellow"
        return f"[COLOR {color}]{v}[/COLOR]", v
    except:
        return "[COLOR grey]S:0[/COLOR]", 0

def get_color_quality(q):
    q = q.upper()
    if '4K' in q or '2160P' in q: return f"[COLOR gold]{q}[/COLOR]", 4
    if '1080P' in q: return f"[COLOR blue]{q}[/COLOR]", 3
    if '720P' in q: return f"[COLOR orange]{q}[/COLOR]", 2
    return f"[COLOR grey]{q}[/COLOR]", 1

def extrair_codec_hdr(raw_title):
    t = raw_title.lower()

    source = ""
    if any(x in t for x in ['web-dl', 'webdl', 'webrip']):
        source = "web-dl"
    elif any(x in t for x in ['bluray', 'blu-ray', 'bdrip', 'bdremux']):
        source = "bluray"
    elif 'hdrip' in t:
        source = "hdrip"
    elif 'dvdrip' in t:
        source = "dvdrip"
    elif '3d' in t:
        source = "3d"
    elif 'cam' in t:
        source = "cam"
    elif re.search(r'\bts\b', t):
        source = "ts"

    codec = ""
    if any(x in t for x in ('h265', 'x265', 'hevc')):
        codec = "HEVC"
    elif any(x in t for x in ('h264', 'x264', 'avc')):
        codec = "AVC"

    hdr = ""
    if 'hdr' in t:
        hdr = "HDR"
    elif '10bit' in t or '10-bit' in t:
        hdr = "10bit"

    return codec, hdr, source



def extrair_audio(raw_title):
    t = raw_title.lower()

    canais = ""
    if re.search(r'7[\.\s]?1', t):
        canais = "7.1"
    elif re.search(r'5[\.\s]?1', t):
        canais = "5.1"
    elif re.search(r'2[\.\s]?0', t):
        canais = "2.0"

    codec = ""
    if 'atmos' in t:
        codec = "Atmos"
    elif 'truehd' in t:
        codec = "TrueHD"
    elif 'dts' in t:
        codec = "DTS"
    elif 'dd+' in t or 'eac3' in t:
        codec = "DD+"
    elif 'ac3' in t or 'dd5' in t:
        codec = "AC3"
    elif 'aac' in t:
        codec = "AAC"
    elif 'mp3' in t:
        codec = "MP3"

    return " ".join(x for x in (codec, canais) if x)


def validar_episodio_no_titulo(titulo, season, episode):
    """Validates that the file title contains the requested season and episode."""
    if not season or not episode:
        return True
        
    t = titulo.lower()
    s = int(season)
    e = int(episode)
    
    # ✅ 1. STRICT SEASON VALIDATION
    # If the title contains "S02" and we ask for "S01", it must be discarded IMMEDIATELY
    # We look for patterns S\d+ or Season \d+ or Season \d+
    # We use findall to grab all season mentions and make sure NONE conflicts
    seasons_found = re.findall(r'(?:s|season|temporada|t|temp\.?)\s*(\d+)', t)
    if seasons_found:
        # If you found any seasons, ALL of them must be correct or the title must be discarded
        # This prevents "The Pitt S02E06" from being accepted for Season 1
        if not any(int(found_s) == s for found_s in seasons_found):
            return False

    # ✅ 2. EPISODE VALIDATION
    # Common patterns: S01E05, 1x05, S1E5, 01x05, etc.
    # We add \b to ensure the number is exact (prevents E06 from accepting E061)
    patterns = [
        r's%02de%02d\b' % (s, e),
        r's%de%02d\b' % (s, e),
        r's%de%d\b' % (s, e),
        r'%02dx%02d\b' % (s, e),
        r'%dx%02d\b' % (s, e),
        r'%dx%d\b' % (s, e),
        r'season\s*%d\s*episode\s*%d\b' % (s, e),
        r'episode\s*0?%d\b' % e,
        r'episodio\s*0?%d\b' % e,
        r'ep\s*0?%d\b' % e
    ]
    
    for pattern in patterns:
        if re.search(pattern, t):
            # Extra check: if it found an episode pattern, it ensures there is no OTHER conflicting episode
            # Ex: "S01E05-E06" accepts both 5 and 6. But "S01E05" does not accept 6.
            all_eps = re.findall(r'(?:e|ep|episode|episode|x)\s*(\d+)', t)
            if all_eps:
                if any(int(found_e) == e for found_e in all_eps):
                    return True
                else:
                    return False
            return True
            
    # ✅ 3. PACK CHECK / FULL SEASON
    # If the title says "Complete Season" or just "S01", we accept it if there is no episode conflict
    season_patterns = [
        r's%02d\b' % s,
        r's%d\b' % s,
        r'season\s*%02d\b' % s,
        r'season\s*%d\b' % s,
        r'temporada\s*%02d\b' % s,
        r'temporada\s*%d\b' % s,
        r't%02d\b' % s,
        r't%d\b' % s
    ]
    
    for pattern in season_patterns:
        if re.search(pattern, t):
            # If you found the season, check to make sure it isn't pointing to ANOTHER episode
            other_ep = re.search(r'(?:e|ep|episode|episode|x)\s*(\d+)', t)
            if other_ep:
                if int(other_ep.group(1)) == e:
                    return True
                else:
                    return False # It's another episode in the same season
            return True # It's a pack for the correct season
            
    return False


# --- 2. MAIN FUNCTION ---

def find_and_play_sources(item_data, autoplay=None, season=None, episode=None):
    import time

    media_type = item_data.get('media_type')
    imdb_id = item_data.get('imdb_id')
    
    # ✅ FIX: Ensures season and episode are extracted from item_data if not passed
    if season is None: season = item_data.get('season')
    if episode is None: episode = item_data.get('episode')

    if not media_type:
        xbmcgui.Dialog().ok("Error", "Insufficient data.")
        return

    # =========================================================================
    # 1. STREAM PROCESSING (UNCHANGED)
    # =========================================================================
    def process_single_stream(stream, is_local=False, p_name='Source Location', p_priority=999):
        # Support for Magneto and other external scrapers
        hoster_name = stream.get('hoster', p_name)
        provider_name = stream.get('provider', p_name)
        
        # ✅ EPISODE VALIDATION (To avoid false results on unreleased episodes)
        if media_type == 'tvshow' and season and episode:
            # ✅ IMPORTANT: Prioritizes the release_title (real file name) for validation
            # Some scrapers put the series title in the 'title', which misleads validation
            raw_title_to_check = stream.get('release_title') or stream.get('title') or stream.get('name') or ""
            
            if not validar_episodio_no_titulo(raw_title_to_check, season, episode):
                # If it is a torrent provider, validation is mandatory
                is_torrent_check = "elementum" in (stream.get('url') or "") or stream.get('server_name', '').upper() == 'TORRENT' or re.match(r'^[a-fA-F0-9]{40}$', stream.get('url') or "") or (stream.get('url') or "").startswith('magnet:')
                
                if is_torrent_check:
                    xbmc.log(f"[Cinebox] ❌ Result discarded (Episode does not match): {raw_title_to_check}", xbmc.LOGINFO)
                    return None

        # If the stream already has a specific hoster (like Viper, Coco, etc.), we use it
        # Otherwise, we use the name of the provider that initiated the search (p_name)
        if 'hoster' in stream:
            hoster_name = stream['hoster']
            provider_name = stream.get('provider', hoster_name)

        url = stream.get('url') or stream.get('infoHash')
        if not url:
            return None

        # ✅ GET THE RAW TITLE FOR LANGUAGE DETECTION (VERY IMPORTANT)
        raw_title = stream.get('title') or stream.get('name') or ""
        
        # ✅ DETECTS LANGUAGE IN THE RAW TITLE BEFORE ANY CLEANING
        idiomas_detectados = extrair_idiomas_do_titulo(raw_title, stream.get('extras', []), provider_name)
        
        # ✅ CRITICAL BLOCK: If the language is marked as BLOCKED, we ignore the source completely
        if idiomas_detectados == 'BLOCKED':
            return None

        # Prioritize release_title if it exists and is valid for display
        if stream.get('release_title') and len(stream['release_title']) > 5:
            display_title = stream['release_title']
        else:
            display_title = raw_title
    
        # Display title cleanup (display_title)
        display_title = re.sub(r'👤\s*\d+', '', display_title)
        display_title = re.sub(r'S:\s*\d+', '', display_title)
        display_title = re.sub(r'\[\s*\d+\.?\d*\s*(?:GB|MB)\s*\]', '', display_title, flags=re.IGNORECASE)
        display_title = re.sub(r'⚙️\s*[^\n]+$', '', display_title)
        display_title = ' '.join(display_title.split()).strip()
    
        if len(display_title) > 80:
            display_title = display_title[:77] + '...'
    
        if not display_title:
            nome_base = item_data.get('title') or 'Video'
            ano = item_data.get('year') or ''
            if item_data.get('season') and item_data.get('episode'):
                s = str(item_data['season']).zfill(2)
                e = str(item_data['episode']).zfill(2)
                display_title = f"{nome_base} S{s}E{e}"
            else:
                display_title = f"{nome_base} ({ano})" if ano else nome_base

        if is_local:
            is_torrent = "elementum" in url or stream.get('server_name', '').upper() == 'TORRENT'
            stype = 'Torrent' if is_torrent else 'Direct'
        else:
            stype = stream.get('type', 'Direct')
            if re.match(r'^[a-fA-F0-9]{40}$', url) or url.startswith('magnet:'):
                stype = 'Torrent'
            if provider_name == 'WebStreamr':
                stype = 'Direct'

        # Attempts to extract seeders from several common formats (👤, S:, Seeds:, Sementes:)
        # Torrentio usually uses 👤 followed by the number of peers/seeds
        # We also check the 'name' and 'description' field that Stremio uses
        text_to_check = f"{raw_title} {stream.get('name', '')} {stream.get('description', '')}"
        
        # DEBUG LOG FOR SEEDS
        if provider_name == 'Torrentio' or '👤' in text_to_check:
            clean_text = text_to_check.replace('\n', ' ')
            xbmc.log("[Cinebox DEBUG] Provider: %s | Text: %s" % (provider_name, clean_text), xbmc.LOGINFO)
        
        # ✅ IMPROVEMENT: More comprehensive regex to capture seeds in different formats
        # 1. Search for user icon or common labels followed by number
        seed_match = re.search(r'(?:👤|S:|Seeds:|Sementes:|Seeders:)\s*(\d+)', text_to_check, re.IGNORECASE)
        
        if not seed_match:
            # 2. Search by number followed by common labels (ex: "10 Seeds")
            seed_match = re.search(r'(\d+)\s*(?:Seeds|Sementes|Seeders)', text_to_check, re.IGNORECASE)
            
        if not seed_match:
            # 3. Search for common Torrentio/Stremio pattern in descriptions: "👤 10" or "S: 10"
            # Sometimes the icon is stuck to the number
            seed_match = re.search(r'👤(\d+)', text_to_check)

        # ✅ GET THE FINAL VALUE OF SEEDS
        if seed_match:
            s_val_raw = seed_match.group(1)
        else:
            # Fallback for direct dictionary fields
            s_val_raw = stream.get('seeders', stream.get('seeds', stream.get('s', 0)))
            
        # Ensures that s_val is a valid number to avoid errors in int(s_val)
        try:
            s_val = int(s_val_raw)
        except:
            s_val = 0
            
        if stype == 'Direct':
            s_val = 999

        # ✅ IMPROVEMENT: More robust Size extraction
        size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB|GiB|MiB))', text_to_check, re.IGNORECASE)
        if not size_match:
            # Try format without space: "1.5GB"
            size_match = re.search(r'(\d+(?:\.\d+)?(?:GB|MB|GiB|MiB))', text_to_check, re.IGNORECASE)
            
        size_str = size_match.group(1) if size_match else stream.get('size', '')
        if size_str == 'N/A': size_str = ''

        # ✅ IMPROVEMENT: More comprehensive quality extraction
        q_match = re.search(r'(4K|2160p|1080p|720p|480p|SD)', raw_title, re.IGNORECASE)
        if not q_match:
            # Try the full text if you didn't find it in the title
            q_match = re.search(r'(4K|2160p|1080p|720p|480p|SD)', text_to_check, re.IGNORECASE)
            
        q_str = q_match.group(1).upper() if q_match else str(stream.get('quality', 'HD')).upper()

        codec, hdr, source = extrair_codec_hdr(raw_title)
        audio = extrair_audio(raw_title)
        video_info = " ".join(x for x in (codec, hdr, audio) if x)

        seed_label, seed_score = get_color_seeders(s_val, stype)
        qual_label, qual_score = get_color_quality(q_str)

        # FINAL PROCESSING LOG
        xbmc.log("[Cinebox DEBUG] Final Result -> Title: %s | Seeds: %s | Score: %s" % (display_title, s_val, seed_score), xbmc.LOGINFO)

        return {
            'url': url,
            'display_title': display_title,
            'raw_title': raw_title,
            'quality_label': qual_label,
            'seeders_label': seed_label,
            'size': size_str,
            'provider': provider_name,
            'hoster': hoster_name,
            'languages': idiomas_detectados,

            # PNG PROPERTIES
            'codec': codec.lower() if codec else '',
            'hdr': hdr.lower() if hdr else '',
            'audio': audio.lower() if audio else '',
            'source': source,

            # text fallback
            'video_info': video_info,

            # ordering
            'p_priority': p_priority,
            'q_score': qual_score,
            's_score': int(s_val),
            'seeders': int(s_val)
        }

    # =========================================================================
    # 2. BUSY DIALOG + SMART THREADS
    # =========================================================================
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')

    provider_results = {}
    completed = 0
    lock = threading.Lock()

    start_time = time.time()
    pDialog = None

    # Variable to signal cancellation for threads
    cancel_event = threading.Event()

    def fetch_thread(name, data):
        nonlocal completed
        try:
            # We pass the cancel_event to the scraper if it supports it,
            # Or do we just check before starting?
            if cancel_event.is_set(): return
            
            found = scrapers.scrape_provider_sources(name, data, item_data, cancel_event)
            
            if cancel_event.is_set(): return
            
            if found:
                with lock:
                    provider_results[name] = found
        except:
            pass
        finally:
            with lock:
                completed += 1

    # Name normalization to match settings.xml
    def is_provider_enabled(name):
        # Manual mapping to ensure names match settings.xml
        mapping = {
            "ComandoTop": "comandotop",
            "Mico-Leão": "mico-leão",

            "SkyFlix": "skyflix",
            "Brazuca": "brazuca",
            "Torrentio": "torrentio",
            "UIndex": "uindex",
            "Perflix": "perflix",
            "Nyaa": "nyaa",
            "StarckFilmes": "starckfilmes",
            "AnimeZey": "animezey",
            "Magneto": "magneto"
        }
        setting_id = f"provider.{mapping.get(name, name.lower())}.enabled"
        enabled = ADDON.getSettingBool(setting_id)
        xbmc.log(f"[Cinebox] Checking provider {name} ({setting_id}): {enabled}", xbmc.LOGINFO)
        return enabled

    active_providers = [
        (n, d) for n, d in PROVIDERS.items()
        if is_provider_enabled(n)
    ]

    threads = []
    total_threads = len(active_providers)
    

    for name, data in active_providers:
        if name != 'AnimeZey' and not imdb_id:
            with lock:
                completed += 1
            continue

        t = threading.Thread(target=fetch_thread, args=(name, data))
        t.start()
        threads.append(t)

    # Monitoring Loop
    # We've increased the maximum wait time to 60 seconds to give external scrapers time
    cancelled_by_user = False
    while completed < total_threads and (time.time() - start_time) < 60:
        elapsed = time.time() - start_time

        # Creates BG progress only if it takes time
        if elapsed > 0.7 and not pDialog:
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create("CINEBOX [COLOR red]TrainAgain[/COLOR]", "[COLOR yellow]Searching for sources on the servers...[/COLOR]")

        if pDialog:
            # Calculates percentage proportional to time: if it completed 50% of the threads, it shows 50%
            # If no thread has completed, use time as a fallback
            if total_threads > 0:
                completed_percent = int((completed / total_threads) * 100)
            else:
                completed_percent = 0
            
            # If threads have completed, use this percentage, otherwise use time as a fallback
            if completed_percent > 0:
                percent = min(completed_percent, 99)
            else:
                # Fallback: 1% every 0.3 seconds if no thread has completed yet
                percent = min(int((elapsed / 0.3) * 1), 99)
            
            pDialog.update(
                percent,
                message="[COLOR yellow]Searching for sources on the servers...[/COLOR]"
            )
        
        # ✅ FIXED: Checks if the user canceled via Dialog or if the busy window was closed
        # On Kodi, DialogProgressBG has iscanceled() which returns True if the user canceled
        if xbmc.Monitor().abortRequested():
            xbmc.log("[Cinebox] Cancellation detected by the user (abortRequested)", xbmc.LOGINFO)
            cancel_event.set()
            cancelled_by_user = True
            break
        
        # Checks if DialogProgressBG has been canceled
        if pDialog:
            try:
                if pDialog.iscanceled():
                    xbmc.log("[Cinebox] Cancellation detected by the user (DialogProgressBG.iscanceled)", xbmc.LOGINFO)
                    cancel_event.set()
                    cancelled_by_user = True
                    break
            except:
                pass
        
        # Additionally, check whether the busy window was closed by the user (manual cancellation)
        if not xbmcgui.Window(10000).getProperty('busydialognocancel.active') == 'true' and elapsed > 1.0:
             # If the window disappeared and we didn't finish, it was probably canceled
             # Note: busydialognocancel is not easily detectable, but abortRequested() covers most cases.
             pass

        xbmc.sleep(100)

    # ✅ FIXED: If canceled, wait for threads with short timeout
    if cancelled_by_user:
        xbmc.log("[Cinebox] Waiting for threads with short timeout(2s)...", xbmc.LOGINFO)
        for t in threads:
            t.join(timeout=2.0)  # Wait a maximum of 2 seconds per thread
    else:
        # Wait normally if it has not been canceled
        for t in threads:
            t.join()

    if pDialog:
        # Updates to 100% before closing
        pDialog.update(100, message="[COLOR yellow]Searching for sources on the servers...[/COLOR]")
        xbmc.log("[Cinebox] Server search completed: 100%", xbmc.LOGINFO)
        time.sleep(0.3)  # Shows 100% for a brief moment
        pDialog.close()

    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    
    # FIXED: If it was cancelled, it returns immediately without showing dialog
    if cancelled_by_user:
        xbmc.log("[Cinebox] Search canceled by the user, ending find_and_play_sources", xbmc.LOGINFO)
        # NEW: Clear playlist and stop player
        try:
            # Clear Kodi playlist
            xbmc.executebuiltin('Playlist.Clear')
            xbmc.log("[Cinebox] Playlist.Clear executed", xbmc.LOGINFO)
            time.sleep(0.3)
            # For the player completely
            xbmc.executebuiltin('PlayerControl(stop)')
            xbmc.log("[Cinebox] PlayerControl(stop) executed", xbmc.LOGINFO)
            time.sleep(0.5)
            # Returns False to indicate failure
            xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=False, listitem=xbmcgui.ListItem())
            xbmc.log("[Cinebox] setResolvedUrl(succeeded=False) called", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] Error stopping player: {e}", xbmc.LOGWARNING)
        return

    # =========================================================================
    # 3. CONSOLIDATION (UNCHANGED)
    # =========================================================================
    final_list = []
    seen_urls = set()

    for s in item_data.get('streams', []):
        p = process_single_stream(s, is_local=True)
        if p:
            # Extra security check for blocking
            if p.get('languages') == 'BLOCKED':
                continue
            final_list.append(p)
            seen_urls.add(p['url'])

    for name, data in active_providers:
        if name in provider_results:
            xbmc.log(f"[Cinebox] Adding {len(provider_results[name])} provider results {name}", xbmc.LOGINFO)
            for s in provider_results[name]:
                p = process_single_stream(s, False, name, data.get('priority', 999))
                if p:
                    # Extra security check for blocking
                    if p.get('languages') == 'BLOCKED':
                        xbmc.log(f"[Cinebox] 🚫 Blocked source (Unwanted language): {p.get('display_title')}", xbmc.LOGINFO)
                        continue
                    if p['url'] not in seen_urls:
                        final_list.append(p)
                        seen_urls.add(p['url'])

    if not final_list:
        xbmcgui.Dialog().notification("Cinebox", "No sources found on servers.", xbmcgui.NOTIFICATION_INFO, 5000)
        # ✅ DEFINITE FIX: Prevents "Playback failed" when there are no sources
        try:
            xbmc.executebuiltin('PlayerControl(stop)')
            xbmc.executebuiltin('Playlist.Clear')
            fake_item = xbmcgui.ListItem(path="")
            fake_item.setProperty('IsPlayable', 'false')
            xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=True, listitem=fake_item)
            xbmc.log("[Cinebox] No source: setResolvedUrl(succeeded=True) with an empty item to avoid an error", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] Error completing empty search: {e}", xbmc.LOGWARNING)
        return

    final_list.sort(key=lambda x: (x['p_priority'], -x['q_score'], -x['s_score']))

    # =========================================================================
    # 4. DIALOGUE / AUTOPLAY (UNCHANGED)
    # =========================================================================
    url_escolhida = None

    # Checks whether Autoplay should be applied for this media type
    should_autoplay = False
    
    # ✅ PRIORITY: If autoplay was passed via parameter (TMDbHelper), use it
    if autoplay is not None:
        should_autoplay = True if str(autoplay).lower() == 'true' else False
    
    # Otherwise, use the addon configuration
    elif xbmcaddon.Addon().getSettingBool('playback.autoplay'):
        _addon = xbmcaddon.Addon()
        autoplay_type = _addon.getSetting('playback.autoplay_type')
        if autoplay_type == 'Both':
            should_autoplay = True
        elif autoplay_type == 'Movies' and media_type == 'movie':
            should_autoplay = True
        elif autoplay_type == 'TV Shows' and (media_type == 'tvshow' or media_type == 'episode' or media_type == 'tvshow'):
            should_autoplay = True

    if should_autoplay:
        _addon = xbmcaddon.Addon()
        # 1. Maximum Resolution Filter
        max_res = _addon.getSetting('playback.max_resolution').upper()
        res_map = {'4K': 4, '1080P': 3, '720P': 2, 'SD': 1}
        max_score = res_map.get(max_res, 3)
        
        filtered_res = [s for s in final_list if s['q_score'] <= max_score]
        if not filtered_res: filtered_res = final_list # Fallback if nothing is left
        
        # 2. Language Priority Filter
        lang_priority = _addon.getSetting('playback.language_priority') # 'Dubbed' or 'Subtitled'
        
        # Separate the list into language categories
        # The blockage has already been done during extraction (continue), but we guarantee it here too
        filtered_res_clean = [s for s in filtered_res if s['languages'] != 'BLOCKED']
        
        # If there is nothing left after blocking, we use the original list as a last resort (security fallback)
        if not filtered_res_clean:
            filtered_res_clean = filtered_res
        
        dublados = [s for s in filtered_res_clean if ('PT-BR' in s['languages'] or 'DUAL' in s['languages'])]
        legendados = [s for s in filtered_res_clean if 'LEG' in s['languages'] and 'PT-BR' not in s['languages'] and 'DUAL' not in s['languages']]
        
        # For 'other', we include what's left (other allowed languages ​​like EN, ES, etc.)
        outros = [s for s in filtered_res_clean if s not in dublados and s not in legendados]
        
        if lang_priority == 'Dubbed':
            ordered_autoplay = dublados + legendados + outros
        else:
            ordered_autoplay = legendados + dublados + outros
            
        if ordered_autoplay:
            url_escolhida = ordered_autoplay[0]['url']
            xbmc.log(f"[Cinebox] Autoplay selected: {ordered_autoplay[0]['display_title']} (Res: {max_res}, Priority: {lang_priority})", xbmc.LOGINFO)
        else:
            url_escolhida = final_list[0]['url']
            xbmc.log(f"[Cinebox] Autoplay: Sorting failed, using first available source", xbmc.LOGINFO)
    else:
        labels = [
            f"{s['quality_label']} | {s['languages']} | {s['seeders_label']} | {s['size']} | {s['provider']}"
            for s in final_list
        ]

        try:
            from resources.lib.dialogs import DialogSelecaoFontes
            dialog = DialogSelecaoFontes(
                'dialog_cinebox_fullscreen.xml',
                ADDON.getAddonInfo('path'),
                fontes=final_list,
                item_data=item_data
            )
            dialog.doModal()
            # NEW: Checks if it has been canceled
            if dialog.cancelled:
                xbmc.log("[Cinebox] Selection dialog was canceled, closing", xbmc.LOGINFO)
                # ✅ DEFINITIVE FIX: Prevents "Playback failed" when canceling
                try:
                    # 1. For any ongoing reproduction attempt
                    xbmc.executebuiltin('PlayerControl(stop)')
                    xbmc.executebuiltin('Playlist.Clear')
                    
                    # 2. Creates a fake ListItem that appears valid but has no URL
                    # This tricks Kodi into thinking playback is "completed" or "skipped" without error
                    fake_item = xbmcgui.ListItem(path="")
                    fake_item.setProperty('IsPlayable', 'false')
                    
                    # 3. Report success to Kodi to suppress the error dialog
                    xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=True, listitem=fake_item)
                    xbmc.log("[Cinebox] Clean cancellation: setResolvedUrl(succeeded=True) with empty item", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[Cinebox] Error in clean cancellation: {e}", xbmc.LOGWARNING)
                url_escolhida = None
            else:
                url_escolhida = dialog.escolha
            del dialog
        except:
            sel = xbmcgui.Dialog().select(
                f"Fontes: {final_list[0]['display_title']}", labels
            )
            if sel >= 0:
                url_escolhida = final_list[sel]['url']

    # =========================================================================
    # 5. RESOLVE
    # =========================================================================
    if url_escolhida:
        # ✅ FIX: Ensures that the series clearlogo is passed to the resolver
        if item_data.get('media_type') == 'tvshow' and not item_data.get('clearlogo'):
            if item_data.get('tvshow.clearlogo'):
                item_data['clearlogo'] = item_data['tvshow.clearlogo']

        resolver = CineboxResolverWindow(
            "resolver_window.xml",
            ADDON.getAddonInfo('path'),
            "Default",
            "1080i",
            source_url=url_escolhida,
            item_data=item_data,
            handle=int(sys.argv[1])
        )
        resolver.doModal()
        return # Prevents code from continuing to Kodi's default playback


def play_url(url, item_info):
    """Function to play a URL, treating Torrents (Elementum) with selection
    episode automatic and direct links with headers (AnimeZey)."""
    if not url:
        return

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Cinebox] Error: Script called without a valid handle: {e}", xbmc.LOGERROR)
        return

    final_url = url
    is_torrent = False

    # --- 1. Torrent Logic ---
    if url.startswith('magnet:'):
        is_torrent = True
        magnet_uri = url
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        is_torrent = True
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    elif 'elementum' in url:
        is_torrent = True
        magnet_uri = url

    if is_torrent:
        if magnet_uri.startswith('plugin://'):
            final_url = magnet_uri
        else:
            encoded_uri = urllib.parse.quote_plus(magnet_uri)
            media_type = item_info.get('media_type')
            tmdb_id = item_info.get('tmdb_id')
            
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"

            # Logic for series
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                
                # ✅ FIX: Ensures that the series clearlogo is passed to the resolver
                if not item_info.get('clearlogo') and item_info.get('tvshow.clearlogo'):
                    item_info['clearlogo'] = item_info['tvshow.clearlogo']
                
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
                    xbmc.log(f"[Cinebox] Building Elementum link (S/E Series): {final_url}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Cinebox] Building Elementum Link (Series): {final_url}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Cinebox] Building Elementum Link (Movie): {final_url}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[Cinebox] Solving direct link: {final_url}", xbmc.LOGINFO)

    # --- 2. Create the ListItem ---
    play_item = xbmcgui.ListItem(path=final_url)

    # --- 3. Metadata ---
    info_labels = {
        'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year': item_info.get('year'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'season': item_info.get('season'),
        'episode': item_info.get('episode'),
        'tvshowtitle': item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype': item_info.get('media_type', 'video'),
        'imdbnumber': item_info.get('imdb_id'),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'genre': " / ".join(item_info.get('genres', [])),
    }
    play_item.setInfo('video', info_labels)
    
    play_item.setArt({
        'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster': item_info.get('poster') or '',
        'fanart': item_info.get('backdrop') or '',
    })

    # --- 4. Headers Logic for AnimeZey ---
    animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
    if not is_torrent and any(domain in final_url.lower() for domain in animezey_domains):
        
        play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
        play_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')

        referer_header = final_url
        headers_str = (
            f"Referer={referer_header}\r\n"
            f"User-Agent={USER_AGENT}\r\n"
        )
        play_item.setProperty('inputstream.ffmpegdirect.headers', headers_str)

    # --- 5. Resolve the URL ---
    play_item.setProperty('IsPlayable', 'true')
    play_item.setContentLookup(False)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)
    
    # --- ✅ 6. ELEMENTUM AND SCROBBLE MONITORING ---
    def monitor_playback_and_elementum():
        player = xbmc.Player()
        is_elementum = "plugin.video.elementum" in final_url
        start_time = time.time()
        
        # Monitors playback start and closes Elementum dialogs
        while not player.isPlaying():
            if xbmc.Monitor().abortRequested():
                xbmc.log("[Cinebox] Abort detected in navigation.py, killing Elementum", xbmc.LOGINFO)
                if is_elementum:
                    try:
                        subprocess.run(['pkill', '-f', 'elementum'], timeout=2)
                    except:
                        pass
                    try:
                        subprocess.run(['killall', 'elementum'], timeout=2)
                    except:
                        pass
                return
            
            if time.time() - start_time > 120: # Timeout 2 min
                break
                
            if is_elementum:
                # Do not close dialogs here if CineboxResolverWindow is active
                # Closing will be handled by the custom resolution window
                xbmc.executebuiltin('Dialog.Close(10101, true)')
                xbmc.executebuiltin('Dialog.Close(10151, true)')
            
            xbmc.sleep(500)
            
        # If the scrobble is active, monitoring continues
        if ADDON.getSettingBool('trakt_auto_scrobble'):
            _delayed_trakt_scrobble(item_info)

    threading.Thread(target=monitor_playback_and_elementum, daemon=True).start()


def play_url(url, item_info):
    """Function to play a URL, treating Torrents (Elementum) with selection
    episode automatic and direct links with headers (AnimeZey)."""
    if not url:
        return

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Cinebox] Error: Script called without a valid handle: {e}", xbmc.LOGERROR)
        return

    final_url = url
    is_torrent = False

    # --- 1. Torrent Logic ---
    if url.startswith('magnet:'):
        is_torrent = True
        magnet_uri = url
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        is_torrent = True
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    elif 'elementum' in url:
        is_torrent = True
        magnet_uri = url

    if is_torrent:
        if magnet_uri.startswith('plugin://'):
            final_url = magnet_uri
        else:
            encoded_uri = urllib.parse.quote_plus(magnet_uri)
            media_type = item_info.get('media_type')
            tmdb_id = item_info.get('tmdb_id')
            
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"

            # Logic for series
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                
                # ✅ FIX: Ensures that the series clearlogo is passed to the resolver
                if not item_info.get('clearlogo') and item_info.get('tvshow.clearlogo'):
                    item_info['clearlogo'] = item_info['tvshow.clearlogo']
                
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
                    xbmc.log(f"[Cinebox] Building Elementum link (S/E Series): {final_url}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Cinebox] Building Elementum Link (Series): {final_url}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Cinebox] Building Elementum Link (Movie): {final_url}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[Cinebox] Solving direct link: {final_url}", xbmc.LOGINFO)

    # --- 2. Create the ListItem ---
    play_item = xbmcgui.ListItem(path=final_url)

    # --- 3. Metadata ---
    info_labels = {
        'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year': item_info.get('year'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'season': item_info.get('season'),
        'episode': item_info.get('episode'),
        'tvshowtitle': item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype': item_info.get('media_type', 'video'),
        'imdbnumber': item_info.get('imdb_id'),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'genre': " / ".join(item_info.get('genres', [])),
    }
    play_item.setInfo('video', info_labels)
    
    play_item.setArt({
        'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster': item_info.get('poster') or '',
        'fanart': item_info.get('backdrop') or '',
    })

    # --- 4. Headers Logic for AnimeZey ---
    animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
    if not is_torrent and any(domain in final_url.lower() for domain in animezey_domains):
        
        play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
        play_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')

        referer_header = final_url
        headers_str = (
            f"Referer={referer_header}\r\n"
            f"User-Agent={USER_AGENT}\r\n"
        )
        play_item.setProperty('inputstream.ffmpegdirect.headers', headers_str)

    # --- 5. Resolve the URL ---
    play_item.setProperty('IsPlayable', 'true')
    play_item.setContentLookup(False)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)
    
    # --- ✅ 6. ELEMENTUM AND SCROBBLE MONITORING ---
    def monitor_playback_and_elementum():
        player = xbmc.Player()
        is_elementum = "plugin.video.elementum" in final_url
        start_time = time.time()
        
        # Monitors playback start and closes Elementum dialogs
        while not player.isPlaying():
            if xbmc.Monitor().abortRequested():
                xbmc.log("[Cinebox] Abort detected in navigation.py, killing Elementum", xbmc.LOGINFO)
                if is_elementum:
                    try:
                        subprocess.run(['pkill', '-f', 'elementum'], timeout=2)
                    except:
                        pass
                    try:
                        subprocess.run(['killall', 'elementum'], timeout=2)
                    except:
                        pass
                return
            
            if time.time() - start_time > 120: # Timeout 2 min
                break
                
            if is_elementum:
                # Do not close dialogs here if CineboxResolverWindow is active
                # Closing will be handled by the custom resolution window
                xbmc.executebuiltin('Dialog.Close(10101, true)')
                xbmc.executebuiltin('Dialog.Close(10151, true)')
            
            xbmc.sleep(500)
            
        # If the scrobble is active, monitoring continues
        if ADDON.getSettingBool('trakt_auto_scrobble'):
            _delayed_trakt_scrobble(item_info)

    threading.Thread(target=monitor_playback_and_elementum, daemon=True).start()


def _delayed_trakt_scrobble(item_info):
    """Monitor playback and scroll when finished (Elementum compatible)"""
    import time
    
    xbmc.log("[Trakt Scrobble] Starting monitoring...", xbmc.LOGINFO)
    
    # Wait for player to start (max 30s)
    player_started = False
    for i in range(30):
        if xbmc.Player().isPlaying():
            player_started = True
            xbmc.log(f"[Trakt Scrobble] Player detected after {i}s", xbmc.LOGINFO)
            break
        time.sleep(1)
    
    if not player_started:
        xbmc.log("[Trakt Scrobble] Timeout: player did not start in 30s", xbmc.LOGWARNING)
        return
    
    player = xbmc.Player()
    media_type = item_info.get('media_type')
    tmdb_id = item_info.get('tmdb_id')
    
    if not tmdb_id:
        xbmc.log("[Trakt Scrobble] No TMDB ID, aborting", xbmc.LOGWARNING)
        return
    
    # Wait for playback to finish
    start_time = time.time()
    total_time = 0
    last_position = 0
    
    try:
        # Monitor while playing
        while player.isPlaying():
            try:
                total_time = player.getTotalTime()
                last_position = player.getTime()
            except:
                pass
            time.sleep(5)
        
        # Calculates actual progress
        elapsed = time.time() - start_time
        
        if total_time > 0:
            # Use the highest position reached
            progress = (max(last_position, elapsed) / total_time) * 100
        else:
            # Fallback: if you watched more than 5 minutes, consider it valid
            progress = 100 if elapsed > 300 else 0
        
        xbmc.log(f"[Trakt Scrobble] Progress: {progress:.1f}% (time: {elapsed:.0f}s, duration: {total_time:.0f}s)", xbmc.LOGINFO)
        
        # Only mark if you watched at least 80% OR more than 15 minutes
        if progress < 80 and elapsed < 900:
            xbmc.log(f"[Trakt Scrobble] Insufficient progress ({progress:.0f}%), not scoring", xbmc.LOGINFO)
            return
        
        # Mark as watched on Trakt
        from resources.lib.trakt_sync import trakt_request
        
        if media_type == 'movie':
            payload = {
                'movies': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'watched_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                }]
            }
            desc = item_info.get('title', 'Film')
            
        elif media_type == 'tvshow':
            season = item_info.get('season')
            episode = item_info.get('episode')
            
            if not season or not episode:
                xbmc.log("[Trakt Scrobble] Series without S/E, aborting", xbmc.LOGWARNING)
                return
            
            payload = {
                'shows': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'seasons': [{
                        'number': int(season),
                        'episodes': [{
                            'number': int(episode),
                            'watched_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                        }]
                    }]
                }]
            }
            desc = f"{item_info.get('title', 'Series')} S{str(season).zfill(2)}E{str(episode).zfill(2)}"
        else:
            xbmc.log(f"[Trakt Scrobble] Tipo desconhecido: {media_type}", xbmc.LOGWARNING)
            return
        
        # Send to Trakt
        response = trakt_request('POST', '/sync/history', payload)
        
        if response:
            xbmc.log(f"[Trakt Scrobble] ✅ Marcado como assistido: {desc}", xbmc.LOGINFO)
            xbmcgui.Dialog().notification("Trakt", f"✅ {desc}", xbmcgui.NOTIFICATION_INFO, 2000)
        else:
            xbmc.log(f"[Trakt Scrobble] ❌ Falha ao marcar: {desc}", xbmc.LOGERROR)
        
    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Error during monitoring: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def view_debug_log():
    """Displays debug log content in a dialog."""
    from .debug_logger import logger
    content = logger.get_log_content(1000)
    xbmcgui.Dialog().textviewer("Cinebox Debug Log", content)

def clear_debug_log():
    """Clears the log file de debug."""
    from .debug_logger import logger
    if logger.clear_log():
        xbmcgui.Dialog().notification("Cinebox", "Log cleared successfully!")
    else:
        xbmcgui.Dialog().notification("Cinebox", "Error cleaning log!", xbmcgui.NOTIFICATION_ERROR)

def export_debug_log():
    """Exports the debug log to a folder chosen by the user."""
    from .debug_logger import logger
    import xbmcvfs
    
    if not os.path.exists(logger.log_file):
        xbmcgui.Dialog().ok("Cinebox", "No log to export.")
        return

    export_path = xbmcgui.Dialog().browse(3, 'Choose folder to export log', 'files')
    if export_path:
        dest = os.path.join(export_path, 'cinebox_debug_export.log')
        if xbmcvfs.copy(logger.log_file, dest):
            xbmcgui.Dialog().ok("Cinebox", f"Log exportado com sucesso para:\n{dest}")
        else:
            xbmcgui.Dialog().ok("Cinebox", "Error exporting log.")
