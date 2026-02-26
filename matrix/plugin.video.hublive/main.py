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
from urllib.parse import parse_qsl, urlencode, quote_plus
import uuid
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


def search_channels():
    """Search for channels by name."""
    # Get user input for search term
    kb = xbmc.Keyboard('', 'Search Channels')
    kb.doModal()
    if not kb.isConfirmed():
        return

    search_term = kb.getText().strip()
    if not search_term:
        return

    # Read all channels from M3U
    addon_path = _ADDON.getAddonInfo('path')
    m3u_file = os.path.join(addon_path, 'premium.txt')

    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not read premium.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    # Extract all channels
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
            # Extract group-title and tvg-logo using more flexible regex
            group_title_match = re.search(r'group-title\s*=\s*"?([^"",]*)"?,?', line, re.IGNORECASE)
            tvg_logo_match = re.search(r'tvg-logo\s*=\s*["\'"]([^"\'"]*)["\'"]', line, re.IGNORECASE)
            
            # Find the last comma in the line to separate attributes from the channel name
            last_comma_pos = line.rfind(',')
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1:].strip()
            else:
                channel_name = 'Unknown Channel'
            
            group_title = group_title_match.group(1) if group_title_match else 'Uncategorized'
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ''

            # Map category name
            group_title = map_category_name(group_title)

            # Get the next line which should be the URL
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith('#'):
                    # Extract stream ID from URL - look for stream= followed by digits
                    stream_id_match = re.search(r'stream=(\d+)', url_line)
                    if stream_id_match:
                        stream_id = stream_id_match.group(1)
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'url': url_line
                        })
        i += 1

    # Filter channels based on search term
    search_term_lower = search_term.lower()
    matching_channels = [ch for ch in channels if search_term_lower in ch['name'].lower()]

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
            li.setArt({'thumb': channel['logo'], 'icon': channel['logo']})

        li.setProperty('IsPlayable', 'true')

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            plot = format_epg_tooltip(epg_items)
            li.setInfo('video', {'plot': plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}"

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=li, isFolder=False)

    # Show a message if no results found
    if not matching_channels:
        li = xbmcgui.ListItem(label=f'[COLOR red]No channels found for "{search_term}"[/COLOR]')
        li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url='', listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)


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
    'RO| CANALE DE CINEMA': 'Filme',
    'RO| CANALE DE DIVERTISMENT': 'Divertisment',
    'RO| CANALE DE SPORT': 'Sport',
    'RO| CANALE DOCUMENTARE': 'Documentare',
    'RO| CANALE GENERALE': 'Generale',
    'RO| CANALE MUZICALE': 'Muzica',
    'RO| CANALE PENTRU COPII': 'Pentru Copii',
    'RO| FOCUS SAT VIP': 'Focus Sat'
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
_mac_list_cache = {'macs': [], 'timestamp': 0}
_MAC_CACHE_TTL = 3600  # 1 hour in seconds
_ONLINE_MAC_URL = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/_tools/mac'

def fetch_mac_list_online():
    """Fetch MAC addresses from online source."""
    try:
        xbmc.log("[MAC] Fetching MAC list from online source", level=xbmc.LOGINFO)
        response = requests.get(_ONLINE_MAC_URL, timeout=10)
        response.raise_for_status()
        mac_list = [line.strip() for line in response.text.split('\n') if line.strip()]
        xbmc.log(f"[MAC] Successfully fetched {len(mac_list)} MACs from online source", level=xbmc.LOGINFO)
        return mac_list
    except Exception as e:
        xbmc.log(f"[MAC] Failed to fetch online MAC list: {e}", level=xbmc.LOGWARNING)
        return None

def get_random_mac_from_file():
    """Get a random MAC address from online source (with fallback to local mac.txt file)"""
    global _mac_list_cache

    current_time = time.time()

    # Check if we have a valid cached MAC list
    if _mac_list_cache['macs'] and (current_time - _mac_list_cache['timestamp']) < _MAC_CACHE_TTL:
        xbmc.log("[MAC] Using cached MAC list", level=xbmc.LOGDEBUG)
        return random.choice(_mac_list_cache['macs'])

    # Try to fetch from online source first
    mac_list = fetch_mac_list_online()

    if mac_list and len(mac_list) > 0:
        # Cache the online MAC list
        _mac_list_cache['macs'] = mac_list
        _mac_list_cache['timestamp'] = current_time
        return random.choice(mac_list)

    # Fallback to local mac.txt file
    xbmc.log("[MAC] Falling back to local mac.txt file", level=xbmc.LOGINFO)
    addon_path = _ADDON.getAddonInfo('path')
    mac_file = os.path.join(addon_path, 'mac.txt')

    try:
        with open(mac_file, 'r') as f:
            mac_list = [line.strip() for line in f.readlines() if line.strip()]

        if mac_list:
            # Cache the local MAC list too
            _mac_list_cache['macs'] = mac_list
            _mac_list_cache['timestamp'] = current_time
            return random.choice(mac_list)
        else:
            xbmcgui.Dialog().notification('Error', 'MAC list is empty', xbmcgui.NOTIFICATION_ERROR)
            return None
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not read mac.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
        return None

def handshake(portal_url, mac):
    """Perform handshake with Stalker portal to get a session token."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
        'X-User-Agent': 'Model: MAG250; Link: WiFi',
    }
    cookies = {'mac': mac}
    url = f"{portal_url}/portal.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('js', {}).get('token')
    except requests.exceptions.RequestException as e:
        xbmc.log(f'[EPG] Handshake failed: {e}', level=xbmc.LOGWARNING)
        return None

# Token cache to avoid handshake for every channel
_token_cache = {'token': None, 'mac': None, 'timestamp': 0}
_TOKEN_TTL = 600  # 10 minutes

# Token provider for EPG Manager with caching
def epg_token_provider():
    """Provide token, headers, and cookies for EPG requests with caching."""
    global _token_cache

    portal_url = _ADDON.getSetting('portal_url')
    current_time = time.time()

    # Check if we have a valid cached token
    if (_token_cache['token'] and _token_cache['mac'] and
        (current_time - _token_cache['timestamp']) < _TOKEN_TTL):
        xbmc.log(f"[EPG] Using cached token (age: {int(current_time - _token_cache['timestamp'])}s)", level=xbmc.LOGDEBUG)

        headers = {
            'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
            'X-User-Agent': 'Model: MAG250; Link: WiFi',
        }

        cookies = {
            'mac': _token_cache['mac'],
            'token': _token_cache['token']
        }

        return _token_cache['token'], headers, cookies

    # Need fresh token
    xbmc.log("[EPG] Fetching fresh token", level=xbmc.LOGINFO)
    mac = get_random_mac_from_file()

    if not mac:
        xbmc.log("[EPG] Failed to get MAC address", level=xbmc.LOGWARNING)
        return None, {}, {}

    token = handshake(portal_url, mac)

    if not token:
        xbmc.log("[EPG] Failed to get token from handshake", level=xbmc.LOGWARNING)
        return None, {}, {}

    # Cache the token
    _token_cache['token'] = token
    _token_cache['mac'] = mac
    _token_cache['timestamp'] = current_time

    xbmc.log(f"[EPG] Cached new token: {token[:10]}...", level=xbmc.LOGINFO)

    headers = {
        'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
        'X-User-Agent': 'Model: MAG250; Link: WiFi',
    }

    cookies = {
        'mac': mac,
        'token': token
    }

    return token, headers, cookies

# Initialize EPG Manager AFTER defining token provider (only if enabled)
# Optimized settings for faster EPG fetching with parallel workers
epg_manager = None
if is_epg_enabled():
    epg_manager = EpgManager(
        mode='stalker',
        base_url=_ADDON.getSetting('portal_url'),
        callback=epg_callback,
        token_provider=epg_token_provider,
        connect_timeout=10.0,    # Increased timeout for connection
        read_timeout=30.0,      # Increased timeout for reading
        max_retries=3,          # Retry 3 times on failure
        backoff_factor=1.0,     # More aggressive backoff
        cache_ttl=1800.0,       # 30 minutes cache
        max_items_default=10,
        num_workers=10          # Process 10 channels in parallel
    )


# Favorites file
FAVORITES_FILE = os.path.join(xbmcvfs.translatePath(_ADDON.getAddonInfo('profile')), 'favorites.json')

def list_favorites():
    """List favorite channels."""
    # Add "Change MAC" button at the top
    change_mac_button = xbmcgui.ListItem(label="[COLOR orange]Change MAC Address[/COLOR]")
    change_mac_button.setArt({'icon': 'DefaultIconInfo.png', 'thumb': 'DefaultIconInfo.png'})
    change_mac_url = f"{_BASE_URL}?mode=change_mac&category=favorites"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=change_mac_url, listitem=change_mac_button, isFolder=False)

    try:
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
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
        li.setArt({'thumb': fav.get('logo', ''), 'icon': fav.get('logo', '')})
        li.setProperty('IsPlayable', 'true')

        url = f"{_BASE_URL}?mode=play&stream_id={fav['stream_id']}&name={quote_plus(fav['name'])}"

        # Context menu to remove from favorites
        li.addContextMenuItems([
            ('Remove from Favorites', f'RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={fav["stream_id"]})')
        ])

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)

def add_to_favorites(stream_id, name, logo):
    """Add a channel to favorites."""
    try:
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []

    if not any(fav['stream_id'] == stream_id for fav in favorites):
        favorites.append({'stream_id': stream_id, 'name': name, 'logo': logo})
        with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
            json.dump(favorites, f)
        xbmcgui.Dialog().notification('Favorites', f'{name} added to favorites', xbmcgui.NOTIFICATION_INFO, 2000)
    else:
        xbmcgui.Dialog().notification('Favorites', f'{name} is already in favorites', xbmcgui.NOTIFICATION_INFO, 2000)

def remove_from_favorites(stream_id):
    """Remove a channel from favorites."""
    try:
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    favorites = [fav for fav in favorites if fav['stream_id'] != stream_id]

    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites, f)
    xbmcgui.Dialog().notification('Favorites', 'Channel removed from favorites', xbmcgui.NOTIFICATION_INFO, 2000)
    xbmc.executebuiltin('Container.Refresh')

def get_params():
    """Get the plugin parameters"""
    paramstring = sys.argv[2][1:]
    return dict(parse_qsl(paramstring))

def list_channels():
    """List channel categories first, then channels if a category is selected."""
    addon_path = _ADDON.getAddonInfo('path')
    m3u_file = os.path.join(addon_path, 'premium.txt')
    
    # Check if we're viewing a specific category
    params = get_params()
    selected_category = params.get('category')

    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not read premium.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
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
            group_title_match = re.search(r'group-title\s*=\s*"?([^"",]*)"?,?', line, re.IGNORECASE)
            tvg_logo_match = re.search(r'tvg-logo\s*=\s*["\'"]([^"\'"]*)["\'"]', line, re.IGNORECASE)
            
            # Find the last comma in the line to separate attributes from the channel name
            last_comma_pos = line.rfind(',')
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1:].strip()
            else:
                channel_name = 'Unknown Channel'
            
            group_title = group_title_match.group(1) if group_title_match else 'Uncategorized'
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ''

            # Map category name
            group_title = map_category_name(group_title)

            # Get the next line which should be the URL
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith('#'):
                    # Extract stream ID from URL - look for stream= followed by digits
                    stream_id_match = re.search(r'stream=(\d+)', url_line)
                    if stream_id_match:
                        stream_id = stream_id_match.group(1)
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'url': url_line
                        })
        
        i += 1
    
    # Debug output
    xbmc.log(f"[DEBUG] Found {len(channels)} channels across {len(set([ch['group'] for ch in channels]))} categories", level=xbmc.LOGDEBUG)
    
    # If a category is selected, list channels in that category
    if selected_category:
        list_channels_in_category(channels, selected_category)
    else:
        # List all available categories
        list_categories(channels)

def list_categories(channels):
    """List all available channel categories with Get Full EPG button."""
    # Add "Search" button at the top
    search_button = xbmcgui.ListItem(label="[COLOR yellow]Cauta[/COLOR]")
    search_button.setArt({'icon': 'DefaultAddonsSearch.png', 'thumb': 'DefaultAddonsSearch.png'})
    search_button_url = f"{_BASE_URL}?mode=search"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=search_button_url, listitem=search_button, isFolder=True)

    # Add "Favorites" button at the top
    favorites_button = xbmcgui.ListItem(label="[COLOR gold]Favorite[/COLOR]")
    favorites_button.setArt({'icon': 'DefaultFavourites.png', 'thumb': 'DefaultFavourites.png'})
    favorites_button_url = f"{_BASE_URL}?mode=favorites"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=favorites_button_url, listitem=favorites_button, isFolder=True)
    
    # Add "Get Full EPG" button at the top (only if EPG is enabled)
    if is_epg_enabled():
        epg_button = xbmcgui.ListItem(label="[COLOR yellow]Get Full EPG[/COLOR]")
        epg_button.setArt({'icon': 'DefaultAddonPVRClient.png', 'thumb': 'DefaultAddonPVRClient.png'})
        epg_button_url = f"{_BASE_URL}?mode=get_full_epg"
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
        category_url = f"{_BASE_URL}?category={quote_plus(category)}"

        xbmcplugin.addDirectoryItem(handle=_HANDLE, url=category_url, listitem=li, isFolder=True)

    # Add Settings link at the end
    settings_item = xbmcgui.ListItem(label="[COLOR cyan]Settings[/COLOR]")
    settings_item.setArt({'icon': 'DefaultAddonService.png', 'thumb': 'DefaultAddonService.png'})
    settings_url = f"{_BASE_URL}?mode=settings"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=settings_url, listitem=settings_item, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)


def list_channels_in_category(all_channels, selected_category):
    """List channels within a specific category."""
    # Load favorites to check which channels are already favorited
    try:
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []
    favorite_stream_ids = [fav['stream_id'] for fav in favorites]

    # Filter channels by the selected category
    channels_in_category = [ch for ch in all_channels if ch['group'] == selected_category]

    # Add "Change MAC" button at the top
    change_mac_button = xbmcgui.ListItem(label="[COLOR orange]Change MAC Address[/COLOR]")
    change_mac_button.setArt({'icon': 'DefaultIconInfo.png', 'thumb': 'DefaultIconInfo.png'})
    change_mac_url = f"{_BASE_URL}?mode=change_mac&category={quote_plus(selected_category)}"
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=change_mac_url, listitem=change_mac_button, isFolder=False)

    # Only load and request EPG if enabled
    if is_epg_enabled() and epg_manager:
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
            li.setArt({'thumb': channel['logo'], 'icon': channel['logo']})

        li.setProperty('IsPlayable', 'true')

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            plot = format_epg_tooltip(epg_items)
            li.setInfo('video', {'plot': plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}"

        # Add context menu for favorites
        context_menu = []
        if channel['stream_id'] in favorite_stream_ids:
            context_menu.append(('Remove from Favorites', f'RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={channel["stream_id"]})'))
        else:
            context_menu.append(('Add to Favorites', f'RunPlugin({_BASE_URL}?mode=add_to_favorites&stream_id={channel["stream_id"]}&name={quote_plus(channel["name"])}&logo={quote_plus(channel["logo"])})'))
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
    addon_path = _ADDON.getAddonInfo('path')
    m3u_file = os.path.join(addon_path, 'premium.txt')

    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not read premium.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    # Extract all channels
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
            group_title_match = re.search(r'group-title\s*=\s*"?([^",]*)"?,?', line, re.IGNORECASE)
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


def change_mac(category=None):
    """Change to a new random MAC address and clear token cache."""
    global _token_cache

    # Get a new random MAC from file
    new_mac = get_random_mac_from_file()
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


def play_stream(stream_id, name):
    """Get the token and MAC dynamically and resolve the URL for a single stream."""
    portal_url = _ADDON.getSetting('portal_url')
    if not portal_url:
        xbmcgui.Dialog().notification('Error', 'Portal URL is not set in settings.', xbmcgui.NOTIFICATION_ERROR)
        return

    # Get a random MAC address from the file (as requested)
    random_mac = get_random_mac_from_file()
    if not random_mac:
        return

    # Perform handshake to get a fresh token from the server for each request
    session_token = handshake(portal_url, random_mac)
    if not session_token:
        xbmcgui.Dialog().notification('Error', 'Failed to get a session token.', xbmcgui.NOTIFICATION_ERROR)
        return

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
        returned_cmd = link_data.get('js', {}).get('cmd')

        if returned_cmd:
            play_token_match = re.search(r'play_token=([a-zA-Z0-9]+)', returned_cmd)
            if play_token_match:
                play_token = play_token_match.group(1)
                final_url = f"{portal_url}/play/live.php?mac={random_mac}&stream={stream_id}&extension=ts&play_token={play_token}"
                play_item = xbmcgui.ListItem(path=final_url)
                xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
            else:
                 xbmcgui.Dialog().notification('Error', 'Could not extract play_token.', xbmcgui.NOTIFICATION_ERROR)
        else:
            xbmcgui.Dialog().notification('Error', 'create_link did not return a command.', xbmcgui.NOTIFICATION_ERROR)

    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f'Failed to create link: {e}', xbmcgui.NOTIFICATION_ERROR)

def router(params):
    """Router function"""
    mode = params.get('mode')
    if mode is None:
        list_channels()
    elif mode == 'play':
        play_stream(params['stream_id'], params['name'])
    elif mode == 'get_full_epg':
        get_full_epg()
    elif mode == 'search':
        corrected_search_channels()
    elif mode == 'change_mac':
        change_mac(params.get('category'))
    elif mode == 'settings':
        _ADDON.openSettings()
    elif mode == 'favorites':
        list_favorites()
    elif mode == 'add_to_favorites':
        add_to_favorites(params['stream_id'], params['name'], params.get('logo', ''))
    elif mode == 'remove_from_favorites':
        remove_from_favorites(params['stream_id'])

    # Only stop epg_manager if it exists
    if epg_manager:
        epg_manager.stop()

def corrected_search_channels():
    """Search for channels by name."""
    # Load favorites to check which channels are already favorited
    try:
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []
    favorite_stream_ids = [fav['stream_id'] for fav in favorites]

    # Get user input for search term
    kb = xbmc.Keyboard('', 'Search Channels')
    kb.doModal()
    if not kb.isConfirmed():
        # User cancelled - show empty directory to allow back navigation
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    search_term = kb.getText().strip()
    if not search_term:
        # Empty search - show empty directory
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    # Read all channels from M3U
    addon_path = _ADDON.getAddonInfo('path')
    m3u_file = os.path.join(addon_path, 'premium.txt')

    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        xbmcgui.Dialog().notification('Error', f'Could not read premium.txt: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    # Extract all channels
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:') or '#EXTINF:' in line.upper():
            # Extract group-title and tvg-logo using more flexible regex
            group_title_match = re.search(r'group-title\s*=\s*"?([^",]*)"?,?', line, re.IGNORECASE)
            tvg_logo_match = re.search(r'tvg-logo\s*=\s*["\'"]([^"\'"]*)["\'"]', line, re.IGNORECASE)
            
            # Find the last comma in the line to separate attributes from the channel name
            last_comma_pos = line.rfind(',')
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1:].strip()
            else:
                channel_name = 'Unknown Channel'
            
            group_title = group_title_match.group(1) if group_title_match else 'Uncategorized'
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ''

            # Map category name
            group_title = map_category_name(group_title)

            # Get the next line which should be the URL
            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith('#'):
                    # Extract stream ID from URL - look for stream= followed by digits
                    stream_id_match = re.search(r'stream=(\d+)', url_line)
                    if stream_id_match:
                        stream_id = stream_id_match.group(1)
                        channels.append({
                            'name': channel_name,
                            'group': group_title,
                            'logo': tvg_logo,
                            'stream_id': stream_id,
                            'url': url_line
                        })
        i += 1

    # Filter channels based on search term
    search_term_lower = search_term.lower()
    matching_channels = [ch for ch in channels if search_term_lower in ch['name'].lower()]

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
            li.setArt({'thumb': channel['logo'], 'icon': channel['logo']})

        li.setProperty('IsPlayable', 'true')

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel['stream_id'] in epg_data:
            epg_items = epg_data[channel['stream_id']]
            plot = format_epg_tooltip(epg_items)
            li.setInfo('video', {'plot': plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}"

        # Add context menu for favorites
        context_menu = []
        if channel['stream_id'] in favorite_stream_ids:
            context_menu.append(('Remove from Favorites', f'RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={channel["stream_id"]})'))
        else:
            context_menu.append(('Add to Favorites', f'RunPlugin({_BASE_URL}?mode=add_to_favorites&stream_id={channel["stream_id"]}&name={quote_plus(channel["name"])}&logo={quote_plus(channel["logo"])})'))
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