import sys
import time
import re
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import requests
import xbmcvfs
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, parse_qs
import json
import zlib
import base64
import logging

# Set a common User-Agent to avoid being blocked
HEADERS = {'User-Agent': 'VLC/3.0.20 (Windows; x86_64)'}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Addon specific information
ADDON = xbmcaddon.Addon()
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = 'plugin://plugin.video.hub/'
PROFILE_DIR = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')), 'xtremeiptvplayer')
if not xbmcvfs.exists(PROFILE_DIR):
    xbmcvfs.mkdirs(PROFILE_DIR)

# Settings
def get_pastebin_url():
    pastebin_url_file = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo('path')), 'pastebin_url.txt')
    if xbmcvfs.exists(pastebin_url_file):
        with xbmcvfs.File(pastebin_url_file, 'r') as f:
            encoded_data = f.read()
            reversed_data = encoded_data[::-1]
            decoded_data = base64.b64decode(reversed_data)
            decompressed_data = zlib.decompress(decoded_data)
            data = json.loads(decompressed_data.decode('utf-8'))
            return data['url']
    return ""

PASTEBIN_PROFILES_URL = get_pastebin_url()
PASTEBIN_CACHE_FILE = os.path.join(PROFILE_DIR, 'pastebin_profiles_cache.json')
PASTEBIN_CACHE_DURATION = 3600 # 1 hour in seconds
SERVER_URL = ADDON.getSetting('xtreme_url')
USERNAME = ADDON.getSetting('xtreme_username')
PASSWORD = ADDON.getSetting('xtreme_password')

def build_url(query):
    # Ensure 'action' is the first parameter
    action_param = query.pop('action', 'xtremeiptvplayer') # Get action, default to 'xtremeiptvplayer'
    
    # Encode the rest of the parameters
    query_string = urlencode(query)
    
    # Construct the URL with action first
    if query_string:
        return f"{BASE_URL}?action={action_param}&{query_string}"
    else:
        return f"{BASE_URL}?action={action_param}"

def get_api_url(action, params=None):
    # Allow empty username/password if SERVER_URL is present.
    # This assumes some Xtream IPTV servers might not require authentication,
    # or that the username/password are optional for certain actions.
    if not SERVER_URL: # SERVER_URL is still mandatory
        return None
    
    # Use the settings directly, as they are updated by switch_profile
    current_username = ADDON.getSetting('xtreme_username')
    current_password = ADDON.getSetting('xtreme_password')

    base = f"{SERVER_URL}/player_api.php?username={current_username}&password={current_password}&action={action}"
    if params:
        base += "&" + urlencode(params)
    return base

def decode_remote_data(encoded_data):
    try:
        # encoded_data is a string from response.text
        reversed_data = encoded_data[::-1]
        decoded_bytes = base64.b64decode(reversed_data)
        decompressed_bytes = zlib.decompress(decoded_bytes)
        return decompressed_bytes.decode('utf-8')
    except Exception:
        # If decoding fails, assume it's plain text
        return encoded_data

def encode_data(data):
    json_data = json.dumps(data, indent=4)
    compressed_data = zlib.compress(json_data.encode('utf-8'))
    encoded_data = base64.b64encode(compressed_data)
    return encoded_data[::-1]

def decode_data(encoded_data):
    reversed_data = encoded_data[::-1]
    decoded_data = base64.b64decode(reversed_data)
    decompressed_data = zlib.decompress(decoded_data)
    return json.loads(decompressed_data.decode('utf-8'))

def encode_xml_data(data):
    compressed_data = zlib.compress(data)
    encoded_data = base64.b64encode(compressed_data)
    return encoded_data[::-1]

def decode_xml_data(encoded_data):
    reversed_data = encoded_data[::-1]
    decoded_data = base64.b64decode(reversed_data)
    return zlib.decompress(decoded_data)

# --- Profile/Account Management ---
def read_profiles():
    # Try to read from cache first
    if xbmcvfs.exists(PASTEBIN_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(PASTEBIN_CACHE_FILE)
            if (time.time() - cache_mod_time) < PASTEBIN_CACHE_DURATION:
                with xbmcvfs.File(PASTEBIN_CACHE_FILE, 'r') as f:
                    encoded_data = f.read()
                    return decode_data(encoded_data.encode('utf-8'))
        except (IOError, ValueError, OSError, zlib.error):
            pass # Cache invalid or corrupted, proceed to fetch

    # Fetch from pastebin
    try:
        response = SESSION.get(PASTEBIN_PROFILES_URL, timeout=10)
        response.raise_for_status()
        content = decode_remote_data(response.text.strip()) # Get entire content as a single string

        # Try to parse the content as JSON, as it might be wrapped
        try:
            data_json = json.loads(content)
            content = data_json.get("data", "")
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON or not a string, use the content as is
            pass

        profiles = []
        
        # Use regex to find all Xtream IPTV entries
        # Pattern: full Xtream IPTV URL with username, password, type, and output
        xtream_pattern = r"(https?://[^\s]+?/get.php\?username=[^\s]+?&password=[^\s]+)"
        
        for match in re.finditer(xtream_pattern, content):
            full_url = match.group(1) # Captured full URL
            
            parsed_url = urlparse(full_url)
            server_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            query_params = parse_qs(parsed_url.query)
            
            username = query_params.get('username', [''])[0]
            password = query_params.get('password', [''])[0]

            profile_name = f"{parsed_url.netloc} ({username})" # Use domain:port (username) as the profile name
            profiles.append({
                "name": profile_name,
                "server": server_base_url,
                "user": username,
                "pass": password
            })
        
        # Cache the fetched profiles
        try:
            with xbmcvfs.File(PASTEBIN_CACHE_FILE, 'w') as f:
                encoded_data = encode_data(profiles)
                f.write(encoded_data.decode('utf-8'))
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache pastebin profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch profiles from pastebin: {e}", xbmcgui.NOTIFICATION_ERROR)
        return []


def write_profiles(profiles):
    # This function is no longer used for writing profiles, as they come from pastebin.
    # It will be kept as a placeholder or removed if not needed elsewhere.
    # For now, it will just return False to prevent any writes.
    xbmcgui.Dialog().notification('Info', 'Profile writing is disabled.', xbmcgui.NOTIFICATION_INFO)
    return False

def list_profiles():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Profiles")
    profiles = read_profiles()
    active_profile_server = ADDON.getSetting('xtreme_url')
    active_profile_user = ADDON.getSetting('xtreme_username')

    if not profiles:
        xbmcgui.Dialog().notification('Info', 'No profiles found from pastebin.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    for profile in profiles:
        name = profile.get('name')
        display_name = name
        # Check if the server URL matches, as user/pass might be empty
        if profile.get('server') == active_profile_server and profile.get('user') == active_profile_user:
            display_name += " (Active)"
        
        url = build_url({'mode': 'switch_profile', 'name': name})
        li = xbmcgui.ListItem(display_name)

        # Construct the m3u_plus_url and add context menu
        server = profile.get('server', '')
        user = profile.get('user', '')
        pwd = profile.get('pass', '')
        if server and user and pwd:
            m3u_plus_url = f"{server}/get.php?username={user}&password={pwd}&type=m3u_plus"
            command = f"RunPlugin({build_url({'mode': 'add_to_pvr', 'url': m3u_plus_url})})"
            li.addContextMenuItems([('Add to PVR IPTV Simple Client', command)])

        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)

    # Removed add/remove profile options as per user request
    # add_dir("[+ Add New Profile]", {'mode': 'add_profile'})
    # if profiles:
    #     add_dir("[- Remove a Profile]", {'mode': 'remove_profile'})

    # NEW: Add force refresh link
    add_dir("[Force Refresh Profiles]", {'mode': 'force_refresh_profiles'})

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def add_profile():
    xbmcgui.Dialog().notification('Info', 'Adding new profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def remove_profile():
    xbmcgui.Dialog().notification('Info', 'Removing profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def force_refresh_profiles():
    if xbmcvfs.exists(PASTEBIN_CACHE_FILE):
        try:
            xbmcvfs.delete(PASTEBIN_CACHE_FILE)
            xbmcgui.Dialog().notification('Success', 'Profile cache cleared. Refreshing...', xbmcgui.NOTIFICATION_INFO)
        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to clear cache: {e}', xbmcgui.NOTIFICATION_ERROR)
    else:
        xbmcgui.Dialog().notification('Info', 'No profile cache found. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer)')

def switch_profile(name):
    profiles = read_profiles()
    profile_to_activate = next((p for p in profiles if p.get('name') == name), None)

    if profile_to_activate:
        ADDON.setSetting('xtreme_url', profile_to_activate['server'])
        ADDON.setSetting('xtreme_username', profile_to_activate['user'])
        ADDON.setSetting('xtreme_password', profile_to_activate['pass'])
        xbmcgui.Dialog().notification('Profile Switched', f"Activated profile: {name}", xbmcgui.NOTIFICATION_INFO)
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer)') # Refresh the menu to show the main menu
    else:
        xbmcgui.Dialog().notification('Error', 'Could not find profile to activate.', xbmcgui.NOTIFICATION_ERROR)

def restart_pvr_addon(addon_id):
    """
    Restarts a PVR addon by disabling and then re-enabling it.

    Args:
        addon_id (str): The ID of the addon to restart (e.g., "pvr.iptvsimple").
    """
    # Disable the addon
    json_request_disable = {
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {
            "addonid": addon_id,
            "enabled": False
        },
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(json_request_disable))
    xbmc.log(f"Disabled addon: {addon_id}", level=xbmc.LOGINFO)

    # Wait a moment for the change to take effect
    time.sleep(2)

    # Enable the addon
    json_request_enable = {
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {
            "addonid": addon_id,
            "enabled": True
        },
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(json_request_enable))
    xbmc.log(f"Enabled addon: {addon_id}", level=xbmc.LOGINFO)
    xbmc.log(f"Restarted PVR addon: {addon_id}", level=xbmc.LOGINFO)

def add_to_pvr(m3u_url):
    dialog = xbmcgui.Dialog()
    
    pvr_simple_userdata_path = xbmcvfs.translatePath('special://userdata/addon_data/pvr.iptvsimple/')
    
    # List all instance-settings-X.xml files
    instance_files = []
    try:
        # xbmcvfs.listdir returns (dirs, files)
        all_files_in_dir = xbmcvfs.listdir(pvr_simple_userdata_path)
        for f in all_files_in_dir[1]: # [1] contains files
            if f.startswith('instance-settings-') and f.endswith('.xml'):
                instance_files.append(os.path.join(pvr_simple_userdata_path, f))
    except Exception as e:
        logging.error(f"PVR DEBUG: Error listing instance files: {e}")
        dialog.notification("PVR IPTV Simple Client", "Could not list instance settings files.", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    if not instance_files:
        dialog.notification("PVR IPTV Simple Client", "No PVR IPTV Simple Client instances found to configure.", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    # Ask user if they want to clear previous URL
    clear_previous = dialog.yesno("PVR IPTV Simple Client", "Do you want to clear the currently configured playlist in PVR IPTV Simple Client before adding this one?")
    
    configured_any = False
    for instance_file_path in instance_files:
        try:
            # Parse the XML file
            tree = ET.parse(instance_file_path)
            root = tree.getroot()

            # Set m3uPathType to remote (value='1')
            m3u_path_type_setting = root.find(".//setting[@id='m3uPathType']")
            if m3u_path_type_setting is not None:
                m3u_path_type_setting.text = '1'
            else:
                # If not found, create it (unlikely for standard settings)
                m3u_path_type_type_setting = ET.SubElement(root, 'setting', id='m3uPathType')
                m3u_path_type_setting.text = '1'

            # Set m3uUrl
            m3u_url_setting = root.find(".//setting[@id='m3uUrl']")
            if m3u_url_setting is not None:
                if clear_previous:
                    m3u_url_setting.text = '' # Clear it first
                m3u_url_setting.text = m3u_url # Set new URL
            else:
                # If not found, create it
                m3u_url_setting = ET.SubElement(root, 'setting', id='m3uUrl')
                m3u_url_setting.text = m3u_url
            
            # Write back the modified XML
            tree.write(instance_file_path, encoding='utf-8', xml_declaration=True)
            configured_any = True

        except Exception as e:
            logging.error(f"PVR DEBUG: Error configuring instance file {instance_file_path}: {e}")
            dialog.notification("PVR IPTV Simple Client", f"Failed to configure instance: {os.path.basename(instance_file_path)}", xbmcgui.NOTIFICATION_ERROR, 3000)
            continue # Try next file

    if configured_any:
        # Refresh PVR
        restart_pvr_addon('pvr.iptvsimple')
        dialog.notification("PVR IPTV Simple Client", "Playlist updated and PVR restarted.", xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        dialog.notification("PVR IPTV Simple Client", "No PVR IPTV Simple Client instances were configured.", xbmcgui.NOTIFICATION_ERROR, 3000)

# EPG Settings
EPG_CACHE_FILE = os.path.join(PROFILE_DIR, 'epg.xml')
EPG_CACHE_DURATION = 3600  # 1 hour in seconds

# --- EPG Functions ---

def get_epg_data():
    """Manages fetching and caching of the EPG data."""
    if not os.path.exists(PROFILE_DIR):
        os.makedirs(PROFILE_DIR)

    cache_expired = True
    if xbmcvfs.exists(EPG_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(EPG_CACHE_FILE)
            if (time.time() - cache_mod_time) < EPG_CACHE_DURATION:
                cache_expired = False
        except OSError:
            pass # File might not be fully written, treat as expired

    if cache_expired:
        epg_url = f"{SERVER_URL}/xmltv.php?username={USERNAME}&password={PASSWORD}"
        try:
            response = SESSION.get(epg_url, timeout=20)
            response.raise_for_status()
            with xbmcvfs.File(EPG_CACHE_FILE, 'wb') as f:
                encoded_epg_data = encode_xml_data(response.content)
                f.write(encoded_epg_data)
        except (requests.RequestException, IOError) as e:
            xbmcgui.Dialog().notification('EPG Error', f"Failed to download EPG: {e}", xbmcgui.NOTIFICATION_ERROR)
            return None

    return parse_epg_xml()

def _parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y%m%d%H%M%S %z')
    except (ValueError, TypeError):
        # fallback for dates without timezone
        try:
            return datetime.strptime(date_str, '%Y%m%d%H%M%S')
        except (ValueError, TypeError):
            return None

def parse_epg_xml():
    """Parses the cached EPG XML file and returns current program info."""
    if not xbmcvfs.exists(EPG_CACHE_FILE):
        return None

    try:
        with xbmcvfs.File(EPG_CACHE_FILE, 'rb') as f:
            encoded_xml_data = f.read()
            xml_data = decode_xml_data(encoded_xml_data).decode('utf-8')
        
        root = ET.fromstring(xml_data)
        epg_programs = {}
        now_utc = datetime.now(timezone.utc)

        for prog in root.findall('programme'):
            channel_id = prog.get('channel')
            start_str = prog.get('start')
            stop_str = prog.get('stop')
            title_elem = prog.find('title')

            if not all([channel_id, start_str, stop_str, title_elem is not None]):
                continue

            start_time = _parse_date(start_str)
            stop_time = _parse_date(stop_str)

            if not all([start_time, stop_time]):
                continue

            if start_time <= now_utc < stop_time:
                title = title_elem.text
                epg_programs[channel_id] = title

        return epg_programs
    except (ET.ParseError, IOError) as e:
        xbmcgui.Dialog().notification('EPG Error', f"Failed to parse EPG data: {e}", xbmcgui.NOTIFICATION_ERROR)
        return None

# --- End EPG Functions ---

def main_menu():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Main Menu")
    add_dir('Manage Profiles', {'mode': 'list_profiles'})
    add_dir('Search', {'mode': 'open_search_menu'})
    add_dir('Live TV', {'mode': 'list_categories', 'type': 'live'})
    add_dir('VOD', {'mode': 'list_categories', 'type': 'vod'})
    add_dir('Series', {'mode': 'list_categories', 'type': 'series'})
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def list_categories(category_type):
    action = f"get_{category_type}_categories"
    api_url = get_api_url(action)
    if not api_url:
        return
    
    try:
        response = SESSION.get(api_url, timeout=15)
        response.raise_for_status()
        categories = response.json()
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    xbmcplugin.setPluginCategory(ADDON_HANDLE, category_type.title())
    for category in categories:
        params = {'mode': 'list_items', 'type': category_type, 'category_id': category['category_id']}
        add_dir(category['category_name'], params)
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def list_items(item_type, category_id):
    epg_data = None
    if item_type == 'live':
        epg_data = get_epg_data()

    if item_type == 'series':
        action = 'get_series'
    else:
        action = f"get_{item_type}_streams"
    api_url = get_api_url(action, {'category_id': category_id})
    if not api_url:
        return

    try:
        response = SESSION.get(api_url, timeout=15)
        response.raise_for_status()
        items = response.json()
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    if not isinstance(items, list):
        xbmcgui.Dialog().notification('API Error', f"Unexpected response for {item_type} streams.", xbmcgui.NOTIFICATION_ERROR)
        return

    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Items")
    for item in items:
        if not isinstance(item, dict):
            continue
        if item_type == 'series':
            series_id = item.get('series_id')
            params = {'mode': 'list_episodes', 'series_id': series_id}
            add_dir(item['name'], params, item.get('cover'))
        else:
            plot = None
            if epg_data and item_type == 'live':
                epg_id = item.get('epg_channel_id')
                if epg_id and epg_id in epg_data:
                    plot = epg_data[epg_id]

            stream_id = item.get('stream_id')
            extension = item.get('container_extension', 'ts') # Default to .ts for live
            params = {'mode': 'play', 'type': item_type, 'stream_id': stream_id, 'extension': extension}
            add_item(item['name'], params, item.get('stream_icon'), plot=plot)
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def list_episodes(series_id):
    api_url = get_api_url('get_series_info', {'series_id': series_id})
    if not api_url:
        return

    try:
        response = SESSION.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Episodes")
    
    episodes_by_season = data.get('episodes', {})
    if isinstance(episodes_by_season, dict):
        for season_number, season_episodes in episodes_by_season.items():
            if not isinstance(season_episodes, list):
                continue

            for episode in season_episodes:
                if not isinstance(episode, dict):
                    continue

                stream_id = episode.get('id')
                title = episode.get('title')
                extension = episode.get('container_extension')
                icon = episode.get('info', {}).get('movie_image')

                if not all([stream_id, title, extension]):
                    continue

                params = {'mode': 'play', 'type': 'series', 'stream_id': stream_id, 'extension': extension}
                s_num = episode.get('season', 0)
                e_num = episode.get('episode_num', 0)
                full_title = f"{s_num}x{e_num} - {title}"
                add_item(full_title, params, icon)

    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def clean_title(title):
    # Remove any characters that are not word characters, whitespace, or basic punctuation.
    cleaned_title = re.sub(r'[^\w\s\-.:]', '', title)
    # Clean up whitespace
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def play_stream(stream_type, stream_id, extension):
    path_segment = 'movie' if stream_type == 'vod' else stream_type
    cache_buster = int(time.time())
    play_url = f"{SERVER_URL}/{path_segment}/{USERNAME}/{PASSWORD}/{stream_id}.{extension}?_={cache_buster}"
    
    li = xbmcgui.ListItem(path=play_url + '|' + urlencode(HEADERS))
    li.setInfo(type='Video', infoLabels={'Title': 'Playing Stream'})
    xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, listitem=li)

def add_dir(name, params, icon=None):
    clean_name = clean_title(name)
    url = build_url(params)
    li = xbmcgui.ListItem(clean_name)
    if icon:
        li.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)

def add_item(name, params, icon=None, plot=None):
    clean_name = clean_title(name)
    url = build_url(params)
    li = xbmcgui.ListItem(clean_name)
    info_labels = {'Title': clean_name}
    if plot:
        info_labels['plot'] = plot
    li.setInfo(type='Video', infoLabels=info_labels)
    li.setProperty('IsPlayable', 'true')
    if icon:
        li.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=False)

def open_search_menu():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Search")
    add_dir('Search Movies', {'mode': 'search_items', 'type': 'vod'})
    add_dir('Search Series', {'mode': 'search_items', 'type': 'series'})
    add_dir('Search Live TV', {'mode': 'search_items', 'type': 'live'})
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def search_items(item_type):
    """Searches all content for a given type."""
    dialog = xbmcgui.Dialog()
    query = dialog.input(f'Search {item_type.title()}', type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        return

    if item_type == 'series':
        action = 'get_series'
    else:
        action = f"get_{item_type}_streams"

    api_url = get_api_url(action)
    if not api_url:
        return

    try:
        response = SESSION.get(api_url, timeout=30)
        response.raise_for_status()
        items = response.json()
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    xbmcplugin.setPluginCategory(ADDON_HANDLE, f"Search Results for '{query}'")
    found_items = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        
        name = item.get('name', '')
        if query.lower() in name.lower():
            found_items += 1
            if item_type == 'series':
                series_id = item.get('series_id')
                params = {'mode': 'list_episodes', 'series_id': series_id}
                add_dir(item['name'], params, item.get('cover'))
            else:
                stream_id = item.get('stream_id')
                # Determine extension based on type
                if item_type == 'live':
                    extension = item.get('container_extension', 'ts')
                    play_type = 'live'
                else: # VOD
                    extension = item.get('container_extension', 'mp4')
                    play_type = 'movie'
                
                params = {'mode': 'play', 'type': play_type, 'stream_id': stream_id, 'extension': extension}
                add_item(item['name'], params, item.get('stream_icon'))
    
    if found_items == 0:
        xbmcgui.Dialog().notification('Search', 'No results found.', xbmcgui.NOTIFICATION_INFO)

    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def router(params):
    mode = params.get('mode')

    # If no mode is set, decide where to go.
    if mode is None:
        # If no server is configured in settings, go to profile manager.
        if not ADDON.getSetting('xtreme_url'):
            profiles = read_profiles() # Read profiles to check if any exist
            if profiles:
                # Activate the first profile by default if no server is set
                switch_profile(profiles[0]['name'])
            else:
                list_profiles() # If no profiles, still show list_profiles (which will show "No profiles found")
        else:
            main_menu()
    elif mode == 'list_profiles':
        list_profiles()
    elif mode == 'add_profile':
        add_profile()
    elif mode == 'remove_profile':
        remove_profile()
    elif mode == 'switch_profile':
        switch_profile(params['name'])
    elif mode == 'add_to_pvr':
        add_to_pvr(params['url'])
    elif mode == 'force_refresh_profiles':
        force_refresh_profiles()
    elif mode == 'open_search_menu':
        open_search_menu()
    elif mode == 'search_items':
        search_items(params['type'])
    elif mode == 'list_categories':
        list_categories(params['type'])
    elif mode == 'list_items':
        list_items(params['type'], params['category_id'])
    elif mode == 'list_episodes':
        list_episodes(params['series_id'])
    elif mode == 'play':
        play_stream(params['type'], params['stream_id'], params.get('extension'))

if __name__ == '__main__':
    router(dict(parse_qsl(sys.argv[2][1:])))
