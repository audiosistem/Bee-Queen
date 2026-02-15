import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import requests
import random
import re
import os
import json
import time
from urllib.parse import parse_qsl, urlencode, quote_plus, quote
import uuid
import hashlib
import string
from epg import EpgManager, format_epg_tooltip

# EPG data store
epg_data = {}

# EPG Cache management
EPG_CACHE_FILE = None
EPG_CACHE_TTL = 1800  # 30 minutes in seconds

def get_epg_cache_file():
    """Get the EPG cache file path."""
    global EPG_CACHE_FILE
    if EPG_CACHE_FILE is None:
        # Get Kodi's special path and translate it to real filesystem path
        addon_profile_path = xbmcaddon.Addon().getAddonInfo('profile')
        # Use xbmcvfs.translatePath (or xbmc.translatePath for older Kodi versions)
        try:
            addon_path = xbmcvfs.translatePath(addon_profile_path)
        except:
            # Fallback for older Kodi versions
            addon_path = xbmc.translatePath(addon_profile_path)

        if not os.path.exists(addon_path):
            os.makedirs(addon_path)
        EPG_CACHE_FILE = os.path.join(addon_path, 'epg_cache.json')
    return EPG_CACHE_FILE

def load_epg_cache():
    """Load EPG data from cache file."""
    cache_file = get_epg_cache_file()
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                current_time = time.time()

                # Load only non-expired entries
                for stream_id, cache_entry in cache_data.items():
                    timestamp = cache_entry.get('timestamp', 0)
                    if current_time - timestamp < EPG_CACHE_TTL:
                        # Convert datetime strings back to datetime objects
                        items = cache_entry.get('items', [])
                        for item in items:
                            if item.get('start_dt'):
                                from datetime import datetime
                                item['start_dt'] = datetime.fromisoformat(item['start_dt'])
                            if item.get('end_dt'):
                                from datetime import datetime
                                item['end_dt'] = datetime.fromisoformat(item['end_dt'])
                        epg_data[stream_id] = items

                xbmc.log(f"[EPG] Loaded {len(epg_data)} channels from cache", level=xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[EPG] Failed to load cache: {e}", level=xbmc.LOGWARNING)

def save_epg_cache():
    """Save EPG data to cache file."""
    cache_file = get_epg_cache_file()
    try:
        cache_data = {}
        current_time = time.time()

        for stream_id, items in epg_data.items():
            # Convert datetime objects to ISO format strings for JSON
            serializable_items = []
            for item in items:
                serializable_item = item.copy()
                if item.get('start_dt'):
                    serializable_item['start_dt'] = item['start_dt'].isoformat()
                if item.get('end_dt'):
                    serializable_item['end_dt'] = item['end_dt'].isoformat()
                serializable_items.append(serializable_item)

            cache_data[stream_id] = {
                'timestamp': current_time,
                'items': serializable_items
            }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)

        xbmc.log(f"[EPG] Saved {len(cache_data)} channels to cache", level=xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[EPG] Failed to save cache: {e}", level=xbmc.LOGWARNING)

def get_current_program(epg_items):
    """Extract the current program name from EPG items."""
    if not epg_items:
        return None

    from datetime import datetime
    now = datetime.now()

    for item in epg_items:
        start_dt = item.get("start_dt")
        end_dt = item.get("end_dt")

        if start_dt and end_dt:
            if start_dt <= now < end_dt:
                # Current program
                name = item.get("name") or item.get("title") or ""
                return name.strip()

    # If no current program, return the next upcoming one
    for item in epg_items:
        start_dt = item.get("start_dt")
        if start_dt and now < start_dt:
            name = item.get("name") or item.get("title") or ""
            return f"Next: {name.strip()}"

    return None


def epg_callback(channel_key, items):
    xbmc.log(f"[DEBUG] EPG callback for channel {channel_key} with {len(items)} items. Data: {items}", level=xbmc.LOGDEBUG)
    epg_data[channel_key] = items

# Plugin specific variables
_ADDON = xbmcaddon.Addon()
_HANDLE = int(sys.argv[1])
_BASE_URL = sys.argv[0]

# Check if EPG is enabled
def is_epg_enabled():
    """Check if EPG is enabled in settings."""
    return _ADDON.getSetting('epg_enabled') == 'true'

# Category mapping and sorting
CATEGORY_MAPPING = {
    # Server 1
    'RO| CANALE DE CINEMA': 'Filme',
    'RO| CANALE DE DIVERTISMENT': 'Divertisment',
    'RO| CANALE DE SPORT': 'Sport',
    'RO| CANALE DOCUMENTARE': 'Documentare',
    'RO| CANALE GENERALE': 'Generale',
    'RO| CANALE MUZICALE': 'Muzica',
    'RO| CANALE PENTRU COPII': 'Pentru Copii',
    'RO| FOCUS SAT VIP': 'Focus Sat',
    # Server 2
    'RO : ROMAINE': 'Generale',
    'RO : COPİİ': 'Pentru Copii',
    'RO : DOCU & REALITATE': 'Documentare',
    'RO : MUZICÄ': 'Muzica',
    'RO : SPORT': 'Sport',
    'RO : FILM': 'Filme'
}

# Custom sort order for categories
CATEGORY_ORDER = [
    'Generale',
    'Divertisment',
    'Sport',
    'Filme',
    'Documentare',
    'Muzica',
    'Pentru Copii',
    'Focus Sat'
]

# Category icons (using Kodi's built-in icons)
CATEGORY_ICONS = {
    'Generale': 'DefaultTVShows.png',
    'Divertisment': 'DefaultMusicVideos.png',
    'Sport': 'DefaultAddonGame.png',
    'Filme': 'DefaultMovies.png',
    'Documentare': 'DefaultAddonPVRClient.png',
    'Muzica': 'DefaultMusicAlbums.png',
    'Pentru Copii': 'DefaultAddonGame.png',
    'Focus Sat': 'DefaultAddonService.png'
}

def map_category_name(original_name):
    """Map original category name to display name."""
    return CATEGORY_MAPPING.get(original_name, original_name)

def get_category_icon(category_name):
    """Get icon for a category."""
    return CATEGORY_ICONS.get(category_name, 'DefaultFolder.png')

def get_category_sort_key(category_name):
    """Get sort key for a category. Returns index in CATEGORY_ORDER or 999 for unmapped."""
    try:
        return CATEGORY_ORDER.index(category_name)
    except ValueError:
        return 999  # Put unmapped categories at the end

# MAC list cache
_mac_list_cache = {}
_MAC_CACHE_TTL = 3600  # 1 hour in seconds
_ONLINE_MAC_URL = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/mac'
_ONLINE_MAC_URL_SERVER2 = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/mac2'
_ONLINE_MAC_URL_SERVER3 = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/mac3'

_PREMIUM_URL = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/premium.txt'
_MAG_URL = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/mag.txt'
_S3_URL = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/s3.txt'
_M3U_CACHE = {}
_M3U_CACHE_TTL = 3600  # 1 hour

def get_m3u_lines(server='server1'):
    global _M3U_CACHE
    if server == 'server1':
        url = _PREMIUM_URL
    elif server == 'server2':
        url = _MAG_URL
    else:
        url = _S3_URL

    current_time = time.time()
    
    if server in _M3U_CACHE and (current_time - _M3U_CACHE[server]['timestamp'] < _M3U_CACHE_TTL):
        xbmc.log(f"[DEBUG] Using cached M3U for {server}", level=xbmc.LOGINFO)
        return _M3U_CACHE[server]['lines']

    try:
        xbmc.log(f"[DEBUG] Fetching M3U from {url}", level=xbmc.LOGINFO)
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8' 
        lines = response.text.splitlines()
        
        _M3U_CACHE[server] = {
            'lines': lines,
            'timestamp': current_time
        }
        return lines
    except Exception as e:
        xbmc.log(f"[ERROR] Failed to fetch M3U from {url}: {e}", level=xbmc.LOGERROR)
        raise e

def fetch_mac_list_online(server='server1'):
    """Fetch MAC addresses from online source."""
    if server == 'server1':
        url = _ONLINE_MAC_URL
    elif server == 'server2':
        url = _ONLINE_MAC_URL_SERVER2
    else:
        url = _ONLINE_MAC_URL_SERVER3

    try:
        xbmc.log(f"[MAC] Fetching MAC list from {url}", level=xbmc.LOGINFO)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        mac_list = [line.strip() for line in response.text.split() if line.strip()]
        xbmc.log(f"[MAC] Successfully fetched {len(mac_list)} MACs from {url}", level=xbmc.LOGINFO)
        return mac_list
    except Exception as e:
        xbmc.log(f"[MAC] Failed to fetch online MAC list: {e}", level=xbmc.LOGWARNING)
        return None

def get_random_mac_from_file(server='server1'):
    """Get a random MAC address from online source (with fallback to local mac file)"""
    global _mac_list_cache

    current_time = time.time()

    # Check if we have a valid cached MAC list
    if server in _mac_list_cache and (current_time - _mac_list_cache[server]['timestamp']) < _MAC_CACHE_TTL:
        xbmc.log(f"[MAC] Using cached MAC list for {server}", level=xbmc.LOGDEBUG)
        return random.choice(_mac_list_cache[server]['macs'])

    # Try to fetch from online source first
    mac_list = fetch_mac_list_online(server)

    if mac_list and len(mac_list) > 0:
        # Cache the online MAC list
        if server not in _mac_list_cache:
            _mac_list_cache[server] = {'macs': [], 'timestamp': 0}
        _mac_list_cache[server]['macs'] = mac_list
        _mac_list_cache[server]['timestamp'] = current_time
        return random.choice(mac_list)

    # Fallback to local mac file
    if server == 'server1':
        mac_file_name = 'mac.txt'
    elif server == 'server2':
        mac_file_name = 'mac2.txt'
    else:
        mac_file_name = 'mac3.txt'
        
    xbmc.log(f"[MAC] Falling back to local {mac_file_name} file", level=xbmc.LOGINFO)
    addon_path = _ADDON.getAddonInfo('path')
    mac_file = os.path.join(addon_path, mac_file_name)

    try:
        with open(mac_file, 'r') as f:
            mac_list = [line.strip() for line in f.read().split() if line.strip()]

        if mac_list:
            # Cache the local MAC list too
            if server not in _mac_list_cache:
                _mac_list_cache[server] = {'macs': [], 'timestamp': 0}
            _mac_list_cache[server]['macs'] = mac_list
            _mac_list_cache[server]['timestamp'] = current_time
            return random.choice(mac_list)
        else:
            xbmcgui.Dialog().notification('Error', 'MAC list is empty', xbmcgui.NOTIFICATION_ERROR)
            return None
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not read {mac_file_name}: {e}', xbmcgui.NOTIFICATION_ERROR)
        return None

def handshake(portal_url, mac, server='server1'):
    """Perform handshake with Stalker portal to get a session token."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
        'X-User-Agent': 'Model: MAG250; Link: WiFi',
    }
    cookies = {'mac': mac}

    # Ensure no trailing slash
    portal_url = portal_url.rstrip('/')
    
    # The correct path is /portal.php for these types of servers.
    url = f"{portal_url}/portal.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"

    try:
        xbmc.log(f'[Handshake] Requesting: {url} with MAC: {mac}', level=xbmc.LOGDEBUG)
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check if response is a dict (expected) or list (error)
        if isinstance(data, dict):
            js_data = data.get('js', {})
            if isinstance(js_data, dict):
                token = js_data.get('token')
                if token:
                    return token
                else:
                    xbmc.log(f'[Handshake] No token in response. js data: {js_data}', level=xbmc.LOGWARNING)
                    return None
            elif isinstance(js_data, list):
                xbmc.log(f'[Handshake] Server returned error list: {js_data}', level=xbmc.LOGWARNING)
                return None
            else:
                xbmc.log(f'[Handshake] Unexpected js data type: {type(js_data)}', level=xbmc.LOGWARNING)
                return None
        elif isinstance(data, list):
            xbmc.log(f'[Handshake] Server returned error list at root level: {data}', level=xbmc.LOGWARNING)
            return None

        xbmc.log(f'[Handshake] Unexpected response format: {type(data)}', level=xbmc.LOGWARNING)
        return None
    except requests.exceptions.RequestException as e:
        xbmc.log(f'[Handshake] Request failed: {e}', level=xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log(f'[Handshake] Error: {e}', level=xbmc.LOGWARNING)
        return None

# Token cache to avoid handshake for every channel
# Keyed by server name: 'server1': {...}, 'server2': {...}
_token_cache = {}
_TOKEN_TTL = 600  # 10 minutes

def make_token_provider(server_name, portal_url):
    """Factory to create a token provider bound to a specific server."""
    
    def provider():
        global _token_cache

        current_time = time.time()
        
        # Initialize cache for this server if needed
        if server_name not in _token_cache:
            _token_cache[server_name] = {'token': None, 'mac': None, 'timestamp': 0}
        
        cache_entry = _token_cache[server_name]

        # Check if we have a valid cached token
        if (cache_entry['token'] and cache_entry['mac'] and
            (current_time - cache_entry['timestamp']) < _TOKEN_TTL):
            # xbmc.log(f"[EPG] Using cached token for {server_name}", level=xbmc.LOGDEBUG)

            headers = {
                'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
                'X-User-Agent': 'Model: MAG250; Link: WiFi',
            }

            cookies = {
                'mac': cache_entry['mac'],
                'token': cache_entry['token']
            }

            return cache_entry['token'], headers, cookies

        # Need fresh token
        xbmc.log(f"[EPG] Fetching fresh token for {server_name} ({portal_url})", level=xbmc.LOGINFO)
        mac = get_random_mac_from_file(server_name)

        if not mac:
            xbmc.log(f"[EPG] Failed to get MAC address for {server_name}", level=xbmc.LOGWARNING)
            return None, {}, {}

        # Perform handshake
        token = handshake(portal_url, mac, server=server_name)

        if not token:
            xbmc.log(f"[EPG] Failed to get token from handshake for {server_name}", level=xbmc.LOGWARNING)
            return None, {}, {}

        # Cache the token
        _token_cache[server_name]['token'] = token
        _token_cache[server_name]['mac'] = mac
        _token_cache[server_name]['timestamp'] = current_time

        xbmc.log(f"[EPG] Cached new token for {server_name}: {token[:10]}...", level=xbmc.LOGINFO)

        headers = {
            'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
            'X-User-Agent': 'Model: MAG250; Link: WiFi',
        }

        cookies = {
            'mac': mac,
            'token': token
        }

        return token, headers, cookies
        
    return provider

def get_server_details(server):
    """Return (portal_url, mac_file_key) for a given server."""
    try:
        lines = get_m3u_lines(server)
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract portal URL from the first valid URL found in the file
                match = re.match(r'(https?://[^/]+)', line)
                if match:
                    return match.group(1), server
    except Exception as e:
        xbmc.log(f"[ERROR] Failed to get portal URL for {server}: {e}", level=xbmc.LOGERROR)

    return "", server

# Initialize EPG Manager (will be reconfigured dynamically)
epg_manager = None
if is_epg_enabled():
    # Initial dummy config, will be reconfigured on list_channels
    portal_url, _ = get_server_details('server1')
    epg_manager = EpgManager(
        mode='stalker',
        base_url=portal_url,
        callback=epg_callback,
        token_provider=lambda: (None, {}, {}), # Dummy provider
        connect_timeout=10.0,
        read_timeout=30.0,
        max_retries=3,
        backoff_factor=1.0,
        cache_ttl=1800.0,
        max_items_default=10,
        num_workers=10
    )


# Favorites file
FAVORITES_FILE = os.path.join(xbmcvfs.translatePath(_ADDON.getAddonInfo('profile')), 'favorites_{server}.json')

def list_favorites(server='server1'):
    """List favorite channels."""
    # Add "Change MAC" button at the top
    change_mac_button = xbmcgui.ListItem(label="[COLOR orange]Change MAC Address[/COLOR]")
    change_mac_button.setArt({'icon': 'DefaultIconInfo.png', 'thumb': 'DefaultIconInfo.png'})
    change_mac_url = f"{_BASE_URL}?mode=change_mac&category=favorites&server={server}"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=change_mac_url, listitem=change_mac_button, isFolder=False)

    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []

    if not favorites:
        li = xbmcgui.ListItem(label="[COLOR yellow]No favorite channels.[/COLOR]")
        li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url='', listitem=li, isFolder=False)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    for fav in favorites:
        li = xbmcgui.ListItem(label=fav['name'])
        logo = fav.get('logo', '')
        if logo:
            logo = quote(logo, safe=':/?&=')
        li.setArt({'thumb': logo, 'icon': logo})
        li.setProperty('IsPlayable', 'true')

        url = f"{_BASE_URL}?mode=play&stream_id={fav['stream_id']}&name={quote_plus(fav['name'])}&server={server}"

        # Context menu to remove from favorites
        li.addContextMenuItems([
            ('Remove from Favorites', f'RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={fav["stream_id"]}&server={server})')
        ])

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)

def add_to_favorites(stream_id, name, logo, server='server1'):
    """Add a channel to favorites."""
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []

    if not any(fav['stream_id'] == stream_id for fav in favorites):
        favorites.append({'stream_id': stream_id, 'name': name, 'logo': logo})
        with open(favorites_file, 'w', encoding='utf-8') as f:
            json.dump(favorites, f)
        xbmcgui.Dialog().notification('Favorites', f'{name} added to favorites', xbmcgui.NOTIFICATION_INFO, 2000)
    else:
        xbmcgui.Dialog().notification('Favorites', f'{name} is already in favorites', xbmcgui.NOTIFICATION_INFO, 2000)

def remove_from_favorites(stream_id, server='server1'):
    """Remove a channel from favorites."""
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    favorites = [fav for fav in favorites if fav['stream_id'] != stream_id]

    with open(favorites_file, 'w', encoding='utf-8') as f:
        json.dump(favorites, f)
    xbmcgui.Dialog().notification('Favorites', 'Channel removed from favorites', xbmcgui.NOTIFICATION_INFO, 2000)
    xbmc.executebuiltin('Container.Refresh')

def get_params():
    """Get the plugin parameters"""""
    paramstring = sys.argv[2][1:]
    return dict(parse_qsl(paramstring))

def list_channels(server='server1'):
    """List channel categories first, then channels if a category is selected."""
    xbmc.log(f"[DEBUG] Loading channels for {server}", level=xbmc.LOGINFO)
    
    # Check if we're viewing a specific category
    params = get_params()
    selected_category = params.get('category')

    try:
        lines = get_m3u_lines(server)
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not fetch channels: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    # Extract channel information (EXTINF lines and corresponding URLs)
    channels = []
    
    # Iterate through lines in pairs: EXTINF line and URL line
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this line starts with #EXTINF (case insensitive check)
        if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
            # Extract group-title and tvg-logo using more flexible regex
            group_title_match = re.search(r'group-title="?([^",]*)"?', line, re.IGNORECASE)
            tvg_logo_match = re.search(r'tvg-logo=["\']([^"\']*)["\']', line, re.IGNORECASE)
            
            # Find the last comma in the line to separate attributes from the channel name
            last_comma_pos = line.rfind(',')
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1:].strip()
            else:
                channel_name = 'Unknown Channel'
            
            # For Server 2 and 3, clean non-alphanumeric characters from channel title
            if server in ['server2', 'server3']:
                channel_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', channel_name)
                channel_name = ' '.join(channel_name.split())
            
            group_title = group_title_match.group(1).strip() if group_title_match else 'Uncategorized'
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ''

            # Map category name
            group_title = map_category_name(group_title)
            
            # For Server 2 and 3, clean non-alphanumeric characters from category title
            if server in ['server2', 'server3']:
                group_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', group_title)
                group_title = ' '.join(group_title.split())

            # Get the next line which should be the URL
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith('#'):
                    # Extract stream ID from URL - look for stream= followed by digits
                    real_stream_id = None
                    real_id_match = re.search(r'stream=(\d+)', url_line)
                    if real_id_match:
                        real_stream_id = real_id_match.group(1)

                    if server == 'server2':
                        # For Server 2, always use s2_ prefix with index
                        stream_id = f"s2_{len(channels)}"
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'ch_id': real_stream_id, # Real ID for EPG
                            'url': url_line
                        })
                    elif server == 'server3':
                        # For Server 3, use s3_ prefix with index
                        stream_id = f"s3_{len(channels)}"
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'ch_id': real_stream_id, # Real ID for EPG
                            'url': url_line
                        })
                    else:
                        # Server 1 format: stream=12345
                        if real_stream_id:
                            stream_id = real_stream_id
                            channels.append({
                                'name': channel_name,
                                'group': group_title,
                                'logo': tvg_logo,
                                'stream_id': stream_id,
                                'ch_id': real_stream_id,
                                'url': url_line
                            })

        i += 1

    xbmc.log(f"[DEBUG] Found {len(channels)} channels for {server}", level=xbmc.LOGINFO)
    
    # If a category is selected, list channels in that category
    if selected_category:
        list_channels_in_category(channels, selected_category, server=server)
    else:
        # List all available categories
        list_categories(channels, server=server)

def list_categories(channels, server='server1'):
    """List all available channel categories with Get Full EPG button."""
    # Add "Search" button at the top
    search_button = xbmcgui.ListItem(label="[COLOR yellow]Cauta[/COLOR]")
    search_button.setArt({'icon': 'DefaultAddonsSearch.png', 'thumb': 'DefaultAddonsSearch.png'})
    search_button_url = f"{_BASE_URL}?mode=search&server={server}"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=search_button_url, listitem=search_button, isFolder=True)

    # Add "Favorites" button at the top
    favorites_button = xbmcgui.ListItem(label="[COLOR gold]Favorite[/COLOR]")
    favorites_button.setArt({'icon': 'DefaultFavourites.png', 'thumb': 'DefaultFavourites.png'})
    favorites_button_url = f"{_BASE_URL}?mode=favorites&server={server}"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=favorites_button_url, listitem=favorites_button, isFolder=True)
    
    # Add "Get Full EPG" button at the top (only if EPG is enabled and on server 1)
    if is_epg_enabled() and server == 'server1':
        epg_button = xbmcgui.ListItem(label="[COLOR yellow]Get Full EPG[/COLOR]")
        epg_button.setArt({'icon': 'DefaultAddonPVRClient.png', 'thumb': 'DefaultAddonPVRClient.png'})
        epg_button_url = f"{_BASE_URL}?mode=get_full_epg&server={server}"
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=epg_button_url, listitem=epg_button, isFolder=False)

    # Get unique categories (already mapped in list_channels)
    categories = list(set([channel['group'] for channel in channels]))

    # Sort categories by custom order
    categories.sort(key=get_category_sort_key)

    for category in categories:
        # Create a list item for this category
        li = xbmcgui.ListItem(label=category)

        # Get icon for this category
        icon = get_category_icon(category)
        li.setArt({'icon': icon, 'thumb': icon})

        # Create URL to navigate to this category
        category_url = f"{_BASE_URL}?category={quote_plus(category)}&server={server}"

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=category_url, listitem=li, isFolder=True)

    # Add Settings link at the end
    settings_item = xbmcgui.ListItem(label="[COLOR cyan]Settings[/COLOR]")
    settings_item.setArt({'icon': 'DefaultAddonService.png', 'thumb': 'DefaultAddonService.png'})
    settings_url = f"{_BASE_URL}?mode=settings&server={server}"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=settings_url, listitem=settings_item, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)


def list_channels_in_category(all_channels, selected_category, server='server1'):
    """List channels within a specific category."""
    # Load favorites to check which channels are already favorited
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []
    favorite_stream_ids = [fav['stream_id'] for fav in favorites]

    # Filter channels by the selected category
    channels_in_category = [ch for ch in all_channels if ch['group'] == selected_category]

    # Add "Change MAC" button at the top
    change_mac_button = xbmcgui.ListItem(label="[COLOR orange]Change MAC Address[/COLOR]")
    change_mac_button.setArt({'icon': 'DefaultIconInfo.png', 'thumb': 'DefaultIconInfo.png'})
    change_mac_url = f"{_BASE_URL}?mode=change_mac&category={quote_plus(selected_category)}&server={server}"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=change_mac_url, listitem=change_mac_button, isFolder=False)

    # Only load and request EPG if enabled
    if is_epg_enabled() and epg_manager:
        # Reconfigure EPG Manager for the current server
        portal_url, server_key = get_server_details(server)
        token_provider = make_token_provider(server_key, portal_url)
        
        epg_manager.reconfigure(base_url=portal_url, token_provider=token_provider)
        
        # Load EPG cache first
        load_epg_cache()

        xbmc.log(f"[EPG] Category '{selected_category}' has {len(channels_in_category)} channels", level=xbmc.LOGINFO)

        # Count how many channels already have EPG from cache
        channels_with_cached_epg = sum(1 for ch in channels_in_category if ch['stream_id'] in epg_data)
        xbmc.log(f"[EPG] {channels_with_cached_epg}/{len(channels_in_category)} channels have cached EPG", level=xbmc.LOGINFO)

        # Request EPG data for ALL channels in the category
        for channel in channels_in_category:
            epg_manager.request(channel, size=10)

        # Calculate adaptive timeout based on number of channels and cache coverage
        num_channels = len(channels_in_category)
        cache_coverage = channels_with_cached_epg / num_channels if num_channels > 0 else 0

        if cache_coverage >= 0.8:
            # Good cache, wait less
            max_wait_time = min(10000, num_channels * 200)  # 200ms per channel, max 10s
            xbmc.log(f"[EPG] Good cache coverage ({cache_coverage:.0%}), waiting {max_wait_time}ms", level=xbmc.LOGINFO)
        else:
            # Need fresh EPG, estimate ~500ms per channel for network fetch
            max_wait_time = min(45000, num_channels * 500)  # 500ms per channel, max 45s
            xbmc.log(f"[EPG] Fetching fresh EPG, waiting up to {max_wait_time}ms", level=xbmc.LOGINFO)

        wait_interval = 300   # Check every 300ms
        waited = 0
        last_count = channels_with_cached_epg

        while waited < max_wait_time:
            xbmc.sleep(wait_interval)
            waited += wait_interval

            # Check how many channels have EPG data
            channels_with_epg = sum(1 for ch in channels_in_category if ch['stream_id'] in epg_data)

            # Log progress if changed
            if channels_with_epg != last_count:
                xbmc.log(f"[EPG] Progress: {channels_with_epg}/{num_channels} channels ({waited}ms elapsed)", level=xbmc.LOGINFO)
                last_count = channels_with_epg

            # Exit only if no progress for 5 seconds
            if waited >= 5000 and channels_with_epg == channels_with_cached_epg:
                xbmc.log(f"[EPG] No new EPG after 5s, proceeding with {channels_with_epg}/{num_channels}", level=xbmc.LOGINFO)
                break

        # Final count
        final_count = sum(1 for ch in channels_in_category if ch['stream_id'] in epg_data)
        final_coverage = final_count / num_channels if num_channels > 0 else 0
        xbmc.log(f"[EPG] Final: {final_count}/{num_channels} channels ({final_coverage:.0%}) have EPG", level=xbmc.LOGINFO)

        # Save updated EPG to cache
        save_epg_cache()

    # Create list items with EPG data
    for channel in channels_in_category:
        # Build channel label with current program
        channel_label = channel['name']

        # Add current program to label if EPG available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            current_prog = get_current_program(epg_items)
            if current_prog:
                channel_label = f"{channel['name']} - {current_prog}"

        li = xbmcgui.ListItem(label=channel_label)

        # Set thumbnail from tvg-logo if available
        if channel['logo']:
            # Skip logos from known problematic domains
            problematic_domains = ['picon.nxtbox.tv', 'picon.tivi-ott.net']
            if any(domain in channel['logo'] for domain in problematic_domains):
                li.setArt({'thumb': 'DefaultVideo.png', 'icon': 'DefaultVideo.png'})
            else:
                safe_logo = quote(channel['logo'], safe=':/?&=')
                li.setArt({'thumb': safe_logo, 'icon': safe_logo})

        li.setProperty('IsPlayable', 'true')

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            plot = format_epg_tooltip(epg_items)
            li.setInfo('video', {'plot': plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}&server={server}"

        # Add context menu for favorites
        context_menu = []
        if channel['stream_id'] in favorite_stream_ids:
            context_menu.append(('Remove from Favorites', f'RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={channel["stream_id"]}&server={server})'))
        else:
            context_menu.append(('Add to Favorites', f'RunPlugin({_BASE_URL}?mode=add_to_favorites&stream_id={channel["stream_id"]}&name={quote_plus(channel["name"] )}&logo={quote_plus(channel["logo"])}&server={server})'))
        li.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)

def get_full_epg():
    """Fetch EPG for ALL channels from M3U file with progress dialog."""
    # Check if EPG is enabled
    if not is_epg_enabled() or not epg_manager:
        xbmcgui.Dialog().notification('EPG Disabled', 'Enable EPG in addon settings', xbmcgui.NOTIFICATION_INFO)
        return

    # Load existing cache first
    load_epg_cache()

    # Read all channels from M3U
    try:
        lines = get_m3u_lines('server1')
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not fetch premium.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    # Extract all channels
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
            group_title_match = re.search(r'group-title="?([^",]*)"?', line, re.IGNORECASE)
            last_comma_pos = line.rfind(',')
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1:].strip()
            else:
                channel_name = 'Unknown Channel'

            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith('#'):
                    stream_id_match = re.search(r'stream=(\d+)', url_line)
                    if stream_id_match:
                        stream_id = stream_id_match.group(1)
                        channels.append({
                            'name': channel_name,
                            'stream_id': stream_id,
                        })
        i += 1

    total_channels = len(channels)
    xbmc.log(f"[EPG] Get Full EPG: Found {total_channels} channels", level=xbmc.LOGINFO)

    if total_channels == 0:
        xbmcgui.Dialog().notification('EPG', 'No channels found!', xbmcgui.NOTIFICATION_WARNING)
        return

    # Count how many already cached
    channels_with_cached_epg = sum(1 for ch in channels if ch['stream_id'] in epg_data)
    xbmc.log(f"[EPG] {channels_with_cached_epg}/{total_channels} channels already have cached EPG", level=xbmc.LOGINFO)

    # Create progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('Fetching Full EPG', f'Requesting EPG for {total_channels} channels...')

    # Request EPG for all channels
    for idx, channel in enumerate(channels):
        if progress.iscanceled():
            xbmc.log("[EPG] User cancelled full EPG fetch", level=xbmc.LOGINFO)
            progress.close()
            return

        epg_manager.request(channel, size=10)

        # Update progress every 10 channels
        if (idx + 1) % 10 == 0:
            percent = int(((idx + 1) / total_channels) * 30)  # 30% for requesting
            progress.update(percent, f'Requested EPG for {idx + 1}/{total_channels} channels...')

    progress.update(30, f'Waiting for EPG data from server...')

    # Calculate timeout based on total channels
    # Estimate ~400ms per channel with optimizations to allow more time for EPG download
    max_wait_time = min(300000, total_channels * 400)  # Max 300 seconds (5 minutes)
    wait_interval = 500  # Check every 500ms
    waited = 0
    last_count = channels_with_cached_epg

    xbmc.log(f"[EPG] Waiting up to {max_wait_time}ms for {total_channels} channels", level=xbmc.LOGINFO)

    while waited < max_wait_time:
        if progress.iscanceled():
            xbmc.log("[EPG] User cancelled full EPG fetch during wait", level=xbmc.LOGINFO)
            progress.close()
            save_epg_cache()
            return

        xbmc.sleep(wait_interval)
        waited += wait_interval

        # Check progress
        channels_with_epg = sum(1 for ch in channels if ch['stream_id'] in epg_data)

        # Update progress dialog (30% to 95%)
        progress_percent = 30 + int(((channels_with_epg / total_channels) * 65))
        coverage_percent = int((channels_with_epg / total_channels) * 100)
        progress.update(
            progress_percent,
            f'Received EPG for {channels_with_epg}/{total_channels} channels ({coverage_percent}%)\nElapsed: {waited // 1000}s / {max_wait_time // 1000}s'
        )

        # Log progress if changed
        if channels_with_epg != last_count:
            xbmc.log(f"[EPG] Full EPG Progress: {channels_with_epg}/{total_channels} ({coverage_percent}%) - {waited}ms elapsed", level=xbmc.LOGINFO)
            last_count = channels_with_epg

        # Exit only if no progress for 10 seconds
        if waited >= 10000 and channels_with_epg == channels_with_cached_epg:
            xbmc.log(f"[EPG] No new EPG after 10s, finishing with {channels_with_epg}/{total_channels}", level=xbmc.LOGINFO)
            break

    # Final save
    progress.update(95, 'Saving EPG to cache...')
    save_epg_cache()

    # Final stats
    final_count = sum(1 for ch in channels if ch['stream_id'] in epg_data)
    final_coverage = int((final_count / total_channels) * 100)

    progress.update(100, f'Complete! EPG for {final_count}/{total_channels} channels ({final_coverage}%)')
    xbmc.sleep(1500)  # Show final message for 1.5 seconds
    progress.close()

    xbmc.log(f"[EPG] Full EPG fetch complete: {final_count}/{total_channels} ({final_coverage}%)", level=xbmc.LOGINFO)
    xbmcgui.Dialog().notification(
        'EPG Complete',
        f'Got EPG for {final_count}/{total_channels} channels ({final_coverage}%)',
        xbmcgui.NOTIFICATION_INFO,
        3000
    )

def generate_random_mac():
    """Generate a random MAC address in the format 00:1A:79:XX:XX:XX"""
    # Using the same manufacturer prefix as existing MACs in the file
    prefix = "00:1A:79"
    # Generate 3 random bytes for the last part
    suffix = ':'.join([f'{random.randint(0, 255):02X}' for _ in range(3)])
    return f"{prefix}:{suffix}"


def change_mac(category=None, server='server1'):
    """Change to a new random MAC address and clear token cache."""
    global _token_cache

    # Get a new random MAC from file
    new_mac = get_random_mac_from_file(server)
    if not new_mac:
        xbmcgui.Dialog().notification('Error', 'Failed to get new MAC address', xbmcgui.NOTIFICATION_ERROR)
        return

    # Clear token cache to force new handshake with new MAC
    _token_cache['token'] = None
    _token_cache['mac'] = None
    _token_cache['timestamp'] = 0

    xbmc.log(f"[MAC] Changed to new MAC: {new_mac}", level=xbmc.LOGINFO)
    xbmcgui.Dialog().notification('MAC Changed', f'New MAC: {new_mac}', xbmcgui.NOTIFICATION_INFO, 3000)

    # Refresh the category view if we came from a category
    if category:
        xbmc.executebuiltin(f'Container.Refresh')


def play_stream(stream_id, name, server='server1'):
    """Get the token and MAC dynamically and resolve the URL for a single stream."""
    # Get portal URL from remote file
    portal_url, _ = get_server_details(server)

    # Use server parameter to determine logic
    if server == 'server2':
        xbmc.log(f"--- SERVER 2 PLAYBACK START: {name} ---", level=xbmc.LOGINFO)
        
        # Server 2: Get URL template from mag.txt and replace placeholders
        xbmc.log(f"[Server 2] Step 1: Fetching M3U content for Server 2", level=xbmc.LOGINFO)

        try:
            lines = get_m3u_lines('server2')
            xbmc.log(f"[Server 2] Step 1a: Successfully fetched {len(lines)} lines from M3U.", level=xbmc.LOGINFO)

            # Find the channel by index (extract index from stream_id)
            if stream_id.startswith('s2_'):
                channel_index = int(stream_id.split('_')[1])
            else:
                # Fallback: search by name if stream_id is not index-based
                # (This shouldn't happen with our recent list_channels change)
                channel_index = -1
                
            xbmc.log(f"[Server 2] Step 2: Searching for channel at index {channel_index}.", level=xbmc.LOGINFO)
            channel_count = 0

            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
                    # Get next line which should be the URL
                    if i + 1 < len(lines):
                        url_line = lines[i + 1].strip()
                        if url_line and not url_line.startswith('#'):
                            if channel_count == channel_index or (channel_index == -1 and name in line):
                                xbmc.log(f"[Server 2] Step 2a: Found channel template URL: {url_line}", level=xbmc.LOGINFO)
                                
                                # Found our channel! Extract stream ID from URL
                                stream_id_match = re.search(r'stream=(\d+)', url_line)
                                if stream_id_match:
                                    actual_stream_id = stream_id_match.group(1)
                                    xbmc.log(f"[Server 2] Step 3: Extracted Stream ID: {actual_stream_id}", level=xbmc.LOGINFO)

                                    # Perform handshake to get token
                                    # Extract portal URL from the URL template
                                    portal_match = re.match(r'(https?://[^/]+)', url_line)
                                    if portal_match:
                                        server2_portal_url = portal_match.group(1)
                                        xbmc.log(f"[Server 2] Step 4: Extracted Portal URL: {server2_portal_url}", level=xbmc.LOGINFO)

                                        # Try up to 3 different MACs
                                        for mac_attempt in range(3):
                                            xbmc.log(f"--- Starting MAC Attempt {mac_attempt + 1}/3 ---", level=xbmc.LOGINFO)
                                            
                                            random_mac = get_random_mac_from_file(server)
                                            if not random_mac:
                                                xbmc.log("[Server 2] Step 5: Failed to get a random MAC address.", level=xbmc.LOGERROR)
                                                return
                                            xbmc.log(f"[Server 2] Step 5: Using MAC Address: {random_mac}", level=xbmc.LOGINFO)

                                            # Get session token via handshake
                                            xbmc.log("[Server 2] Step 6: Performing handshake...", level=xbmc.LOGINFO)
                                            session_token = handshake(server2_portal_url, random_mac, server='server2')
                                            if not session_token:
                                                xbmc.log(f"[Server 2] Step 6a: Handshake failed for MAC {random_mac}, trying another...", level=xbmc.LOGWARNING)
                                                continue
                                            xbmc.log(f"[Server 2] Step 6a: Handshake successful. Session token: {session_token[:10]}...", level=xbmc.LOGINFO)

                                            # Create link to get play token
                                            headers = {
                                                'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
                                                'X-User-Agent': 'Model: MAG250; Link: WiFi',
                                            }
                                            create_link_url = f"{server2_portal_url}/portal.php?action=create_link&type=itv&cmd={actual_stream_id}&JsHttpRequest=1-xml"
                                            xbmc.log(f"[Server 2] Step 7: Requesting create_link URL: {create_link_url}", level=xbmc.LOGINFO)
                                            cookies = {'mac': random_mac, 'token': session_token}

                                            try:
                                                response = requests.get(create_link_url, headers=headers, cookies=cookies, timeout=10)
                                                response.raise_for_status()
                                                link_data = response.json()
                                                xbmc.log(f"[Server 2] Step 8: Received create_link response: {link_data}", level=xbmc.LOGINFO)

                                                if not isinstance(link_data, dict):
                                                    xbmc.log(f"[Server 2] Unexpected response type: {type(link_data)}", level=xbmc.LOGWARNING)
                                                    continue

                                                js_data = link_data.get('js', {})
                                                
                                                if isinstance(js_data, list):
                                                    xbmc.log(f"[Server 2] Step 9: js_data is a list (likely empty/error): {js_data}", level=xbmc.LOGWARNING)
                                                    continue
                                                    
                                                returned_cmd = js_data.get('cmd')

                                                if returned_cmd:
                                                    xbmc.log(f"[Server 2] Step 9: Found 'cmd' field: {returned_cmd}", level=xbmc.LOGINFO)
                                                    play_token_match = re.search(r'play_token=([a-zA-Z0-9]+)', returned_cmd)
                                                    if play_token_match:
                                                        play_token = play_token_match.group(1)
                                                        xbmc.log(f"[Server 2] Step 10: Extracted play_token: {play_token}", level=xbmc.LOGINFO)
                                                        
                                                        # Replace placeholders in the original URL from mag.txt
                                                        final_url = url_line.replace('MACPH', random_mac).replace('TOKENPH', play_token)
                                                        xbmc.log(f"[Server 2] Step 11: Constructed final URL from template: {final_url}", level=xbmc.LOGINFO)

                                                        # Add User-Agent and X-User-Agent to the final URL
                                                        headers_str = urlencode({
                                                            'User-Agent': headers['User-Agent'],
                                                            'X-User-Agent': headers['X-User-Agent']
                                                        })
                                                        final_url_with_ua = f"{final_url}|{headers_str}"
                                                        xbmc.log(f"[Server 2] Step 12: Appending Headers. Final URL for player: {final_url_with_ua}", level=xbmc.LOGINFO)

                                                        play_item = xbmcgui.ListItem(path=final_url_with_ua)
                                                        xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
                                                        xbmc.log(f"--- SERVER 2 PLAYBACK SUCCESS ---", level=xbmc.LOGINFO)
                                                        return  # SUCCESS!
                                                    else:
                                                        xbmc.log(f"[Server 2] No play_token in response, trying another MAC...", level=xbmc.LOGWARNING)
                                                        continue  # Try next MAC
                                                else:
                                                    xbmc.log(f"[Server 2] No cmd in response, trying another MAC...", level=xbmc.LOGWARNING)
                                                    continue  # Try next MAC

                                            except requests.exceptions.RequestException as e:
                                                xbmc.log(f"[Server 2] Request for create_link failed: {e}, trying another MAC...", level=xbmc.LOGWARNING)
                                                continue  # Try next MAC
                                            except Exception as e:
                                                xbmc.log(f"[Server 2] Error processing create_link response: {e}", level=xbmc.LOGWARNING)
                                                continue # Try next MAC

                                        # All MAC attempts failed
                                        xbmc.log("--- All MAC address attempts failed for Server 2 ---", level=xbmc.LOGERROR)
                                        xbmcgui.Dialog().notification('Error', 'All MAC addresses rejected by Server 2. Try again later.', xbmcgui.NOTIFICATION_ERROR)
                                        return
                                    else:
                                        xbmcgui.Dialog().notification('Error', 'Could not extract portal URL from mag.txt', xbmcgui.NOTIFICATION_ERROR)
                                        return
                                else:
                                    xbmcgui.Dialog().notification('Error', 'Could not extract stream ID from URL', xbmcgui.NOTIFICATION_ERROR)
                                    return
                            channel_count += 1

            xbmcgui.Dialog().notification('Error', 'Channel not found in mag.txt', xbmcgui.NOTIFICATION_ERROR)
            return

        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to load mag.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
            return

    elif server == 'server3':
        xbmc.log(f"--- SERVER 3 PLAYBACK START: {name} ---", level=xbmc.LOGINFO)
        
        try:
            lines = get_m3u_lines('server3')
            
            # Extract index if stream_id is index-based
            if stream_id.startswith('s3_'):
                channel_index = int(stream_id.split('_')[1])
            else:
                channel_index = -1

            channel_count = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
                    if i + 1 < len(lines):
                        url_line = lines[i + 1].strip()
                        if url_line and not url_line.startswith('#') and 'MACPH' in url_line:
                            if channel_count == channel_index or (channel_index == -1 and name in line):
                                # Found channel template
                                stream_id_match = re.search(r'stream=(\d+)', url_line)
                                if stream_id_match:
                                    actual_stream_id = stream_id_match.group(1)
                                    
                                    # Extract portal URL
                                    portal_match = re.match(r'(https?://[^/]+)', url_line)
                                    if portal_match:
                                        server3_portal_url = portal_match.group(1)
                                        
                                        # Try up to 3 MACs
                                        for mac_attempt in range(3):
                                            random_mac = get_random_mac_from_file('server3')
                                            if not random_mac: break
                                            
                                            # Handshake
                                            session_token = handshake(server3_portal_url, random_mac, server='server3')
                                            if not session_token: continue
                                            
                                            # Create Link Request
                                            headers = {
                                                'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
                                                'X-User-Agent': 'Model: MAG250; Link: WiFi',
                                            }
                                            create_link_url = f"{server3_portal_url}/portal.php?action=create_link&type=itv&cmd={actual_stream_id}&JsHttpRequest=1-xml"
                                            cookies = {'mac': random_mac, 'token': session_token}
                                            
                                            try:
                                                response = requests.get(create_link_url, headers=headers, cookies=cookies, timeout=10)
                                                response.raise_for_status()
                                                link_data = response.json()
                                                
                                                # Check response structure
                                                if isinstance(link_data, dict):
                                                    js_data = link_data.get('js', {})
                                                    if isinstance(js_data, dict):
                                                        returned_cmd = js_data.get('cmd')
                                                        if returned_cmd:
                                                            play_token_match = re.search(r'play_token=([a-zA-Z0-9]+)', returned_cmd)
                                                            if play_token_match:
                                                                play_token = play_token_match.group(1)
                                                                
                                                                # Construct final URL
                                                                # Start with the template from playlist
                                                                final_url = url_line.replace('MACPH', random_mac)
                                                                
                                                                # Add play_token if not present (Server 3 doesn't have TOKENPH)
                                                                if 'play_token=' not in final_url:
                                                                    final_url += f"&play_token={play_token}"
                                                                
                                                                # Add User-Agent and X-User-Agent to the final URL
                                                                headers_str = urlencode({
                                                                    'User-Agent': headers['User-Agent'],
                                                                    'X-User-Agent': headers['X-User-Agent']
                                                                })
                                                                final_url_with_ua = f"{final_url}|{headers_str}"
                                                                
                                                                play_item = xbmcgui.ListItem(path=final_url_with_ua)
                                                                xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
                                                                return
                                            except:
                                                pass
                                        
                                        xbmcgui.Dialog().notification('Error', 'Server 3: All MACs failed', xbmcgui.NOTIFICATION_ERROR)
                                        return
                            channel_count += 1
            xbmcgui.Dialog().notification('Error', 'Channel not found in s3.txt', xbmcgui.NOTIFICATION_ERROR)
            return
        except Exception as e:
             xbmcgui.Dialog().notification('Error', f'Failed Server 3: {e}', xbmcgui.NOTIFICATION_ERROR)
             return

    # Server 1: Try up to 3 MACs
    if not portal_url:
        xbmcgui.Dialog().notification('Error', 'Could not find portal URL for Server 1 in premium.txt', xbmcgui.NOTIFICATION_ERROR)
        return

    for mac_attempt in range(3):
        random_mac = get_random_mac_from_file(server)
        if not random_mac:
            return

        xbmc.log(f"[Server1] Attempt {mac_attempt + 1}/3 with MAC: {random_mac}", level=xbmc.LOGINFO)

        # Perform handshake to get a fresh token from the server for each request
        session_token = handshake(portal_url, random_mac)
        if not session_token:
            xbmc.log(f"[Server1] Handshake failed for MAC {random_mac}, trying another...", level=xbmc.LOGWARNING)
            continue

        headers = {
            'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
            'X-User-Agent': 'Model: MAG250; Link: WiFi',
        }
        create_link_url = f"{portal_url}/portal.php?type=itv&action=create_link&cmd={stream_id}&JsHttpRequest=1-xml"
        cookies = {'mac': random_mac, 'token': session_token}

        try:
            response = requests.get(create_link_url, headers=headers, cookies=cookies, timeout=10)
            response.raise_for_status()
            link_data = response.json()

            # Check if response is a dict (expected) or list (error)
            if isinstance(link_data, dict):
                js_data = link_data.get('js', {})
                if isinstance(js_data, dict):
                    returned_cmd = js_data.get('cmd')
                elif isinstance(js_data, list):
                    xbmc.log(f"[Server1] MAC {random_mac} rejected (empty list), trying another...", level=xbmc.LOGWARNING)
                    continue  # Try next MAC
                else:
                    xbmc.log(f"[Server1] Unexpected js data type: {type(js_data)}", level=xbmc.LOGWARNING)
                    continue  # Try next MAC
            elif isinstance(link_data, list):
                xbmc.log(f"[Server1] MAC {random_mac} rejected (root level list), trying another...", level=xbmc.LOGWARNING)
                continue  # Try next MAC
            else:
                xbmc.log(f"[Server1] Unexpected response type: {type(link_data)}", level=xbmc.LOGWARNING)
                continue  # Try next MAC

            if returned_cmd:
                play_token_match = re.search(r'play_token=([a-zA-Z0-9]+)', returned_cmd)
                if play_token_match:
                    play_token = play_token_match.group(1)
                    final_url = f"{portal_url}/play/live.php?mac={random_mac}&stream={stream_id}&extension=ts&play_token={play_token}"
                    xbmc.log(f"[Server1] Successfully playing with MAC: {random_mac}", level=xbmc.LOGINFO)
                    play_item = xbmcgui.ListItem(path=final_url)
                    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
                    return  # SUCCESS!
                else:
                    xbmc.log(f"[Server1] No play_token in response, trying another MAC...", level=xbmc.LOGWARNING)
                    continue  # Try next MAC
            else:
                xbmc.log(f"[Server1] No cmd in response, trying another MAC...", level=xbmc.LOGWARNING)
                continue  # Try next MAC

        except requests.exceptions.RequestException as e:
            xbmc.log(f"[Server1] Request failed: {e}, trying another MAC...", level=xbmc.LOGWARNING)
            continue  # Try next MAC

    # All MAC attempts failed
    xbmcgui.Dialog().notification('Error', 'All MAC addresses rejected by server. Try again later.', xbmcgui.NOTIFICATION_ERROR)
def router(params):
    """Router function"""
    server = params.get('server')
    if server is None:
        server_selection = _ADDON.getSetting('server_selection')
        if server_selection == '0':
            server = 'server1'
        elif server_selection == '1':
            server = 'server2'
        elif server_selection == '2':
            server = 'server3'
        else:
            server = 'all'
    
    params['server'] = server

    mode = params.get('mode')

    if server == 'all' and mode is None:
        li = xbmcgui.ListItem(label='Server 1 RO')
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=f'{_BASE_URL}?server=server1', listitem=li, isFolder=True)
        li = xbmcgui.ListItem(label='Server 2 RO')
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=f'{_BASE_URL}?server=server2', listitem=li, isFolder=True)
        li = xbmcgui.ListItem(label='Server 3 RO')
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=f'{_BASE_URL}?server=server3', listitem=li, isFolder=True)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    if mode is None:
        list_channels(server=server)
    elif mode == 'play':
        play_stream(params['stream_id'], params['name'], server=server)
    elif mode == 'get_full_epg':
        get_full_epg()
    elif mode == 'search':
        corrected_search_channels(server=server)
    elif mode == 'change_mac':
        change_mac(params.get('category'), server=server)
    elif mode == 'settings':
        _ADDON.openSettings()
        xbmc.executebuiltin('Container.Refresh')
    elif mode == 'favorites':
        list_favorites(server=server)
    elif mode == 'add_to_favorites':
        add_to_favorites(params['stream_id'], params['name'], params.get('logo', ''), server=server)
    elif mode == 'remove_from_favorites':
        remove_from_favorites(params['stream_id'], server=server)

    # Only stop epg_manager if it exists
    if epg_manager:
        epg_manager.stop()


def corrected_search_channels(server='server1'):
    """Search for channels by name."""
    # Load favorites to check which channels are already favorited
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []
    favorite_stream_ids = [fav['stream_id'] for fav in favorites]

    # Get user input for search term
    kb = xbmc.Keyboard('', 'Search Channels')
    kb.doModal()
    if not kb.isConfirmed():
        # User cancelled. Explicitly navigate back to the category list for the current server.
        xbmc.executebuiltin(f"Container.Update({_BASE_URL}?server={server})")
        # End the current script cleanly after starting the new navigation action.
        xbmcplugin.endOfDirectory(_HANDLE, succeeded=False)
        return

    search_term = kb.getText().strip()
    if not search_term:
        # Empty search - show empty directory
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    # Read all channels from M3U
    try:
        lines = get_m3u_lines(server)
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not fetch channels: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    # Extract all channels
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
            # Extract group-title and tvg-logo using more flexible regex
            group_title_match = re.search(r'group-title="?([^",]*)"?', line, re.IGNORECASE)
            tvg_logo_match = re.search(r'tvg-logo=["\']([^"\']*)["\']', line, re.IGNORECASE)
            
            # Find the last comma in the line to separate attributes from the channel name
            last_comma_pos = line.rfind(',')
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1:].strip()
            else:
                channel_name = 'Unknown Channel'
            
            # For Server 2 and 3, clean non-alphanumeric characters from channel title
            if server in ['server2', 'server3']:
                channel_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', channel_name)
                channel_name = ' '.join(channel_name.split())
            
            group_title = group_title_match.group(1) if group_title_match else 'Uncategorized'
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ''

            # Map category name
            group_title = map_category_name(group_title)
            
            # For Server 2 and 3, clean non-alphanumeric characters from category title
            if server in ['server2', 'server3']:
                group_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', group_title)
                group_title = ' '.join(group_title.split())

            # Get the next line which should be the URL
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith('#'):
                    # Extract stream ID from URL - look for stream= followed by digits
                    real_stream_id = None
                    real_id_match = re.search(r'stream=(\d+)', url_line)
                    if real_id_match:
                        real_stream_id = real_id_match.group(1)

                    if server == 'server2':
                        # For Server 2, always use s2_ prefix with index
                        stream_id = f"s2_{len(channels)}"
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'ch_id': real_stream_id, # Real ID for EPG
                            'url': url_line
                        })
                    elif server == 'server3':
                        # For Server 3, use s3_ prefix with index
                        stream_id = f"s3_{len(channels)}"
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'ch_id': real_stream_id, # Real ID for EPG
                            'url': url_line
                        })
                    else:
                        # Server 1 format: stream=12345
                        if real_stream_id:
                            stream_id = real_stream_id
                            channels.append({
                                'name': channel_name,
                                'group': group_title,
                                'logo': tvg_logo,
                                'stream_id': stream_id,
                                'ch_id': real_stream_id,
                                'url': url_line
                            })
        i += 1

    # Filter channels based on search term
    search_term_lower = search_term.lower()
    matching_channels = [ch for ch in channels if search_term_lower in ch['name'].lower()]

    # Reconfigure and fetch EPG for search results if enabled
    if is_epg_enabled() and epg_manager and matching_channels:
        portal_url, server_key = get_server_details(server)
        token_provider = make_token_provider(server_key, portal_url)
        epg_manager.reconfigure(base_url=portal_url, token_provider=token_provider)
        
        load_epg_cache()
        # Only request for displayed items to save bandwidth
        for ch in matching_channels[:20]: # Limit to top 20 for speed
            epg_manager.request(ch, size=5)
            
        # Give a short time for EPG to populate
        time.sleep(1.0)
        save_epg_cache()

    # Create list items for matching channels
    for channel in matching_channels:
        # Build channel label with current program
        channel_label = channel['name']

        # Add current program to label if EPG available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            current_prog = get_current_program(epg_items)
            if current_prog:
                channel_label = f"{channel['name']} - {current_prog}"

        li = xbmcgui.ListItem(label=channel_label)

        # Set thumbnail from tvg-logo if available
        if channel['logo']:
            # Skip logos from known problematic domains
            problematic_domains = ['picon.nxtbox.tv', 'picon.tivi-ott.net']
            if any(domain in channel['logo'] for domain in problematic_domains):
                li.setArt({'thumb': 'DefaultVideo.png', 'icon': 'DefaultVideo.png'})
            else:
                safe_logo = quote(channel['logo'], safe=':/?&=')
                li.setArt({'thumb': safe_logo, 'icon': safe_logo})

        li.setProperty('IsPlayable', 'true')

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            plot = format_epg_tooltip(epg_items)
            li.setInfo('video', {'plot': plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}&server={server}"

        # Add context menu for favorites
        context_menu = []
        if channel['stream_id'] in favorite_stream_ids:
            context_menu.append(('Remove from Favorites', f'RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={channel["stream_id"]}&server={server})'))
        else:
            context_menu.append(('Add to Favorites', f'RunPlugin({_BASE_URL}?mode=add_to_favorites&stream_id={channel["stream_id"]}&name={quote_plus(channel["name"] )}&logo={quote_plus(channel["logo"])}&server={server})'))
        li.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=li, isFolder=False)

    # Show a message if no results found
    if not matching_channels:
        li = xbmcgui.ListItem(label=f'[COLOR red]No channels found for "{search_term}"[/COLOR]')
        li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url='', listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)


if __name__ == '__main__':
    router(get_params())