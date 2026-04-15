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
import hashlib
import random

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

MENU_ICONS = {
    'list_profiles': 'DefaultNetwork.png',
    'list_favorite_profiles': 'DefaultFavourites.png',
    'force_refresh_profiles': 'DefaultAddonUpdates.png',
    'open_search_menu': 'DefaultAddonsSearch.png',
    'search_items': 'DefaultAddonsSearch.png',
    'verify_romanian_channels': 'DefaultAddonLibrary.png',
    'list_romanian_categories': 'DefaultTVShows.png',
}

def log_debug(message):
    xbmc.log(f"[xtream] {message}", level=xbmc.LOGINFO)

def describe_payload(payload, limit=300):
    try:
        if isinstance(payload, dict):
            preview = {
                'type': 'dict',
                'keys': list(payload.keys())[:10],
            }
            text = json.dumps(preview, ensure_ascii=True)
        elif isinstance(payload, list):
            sample = payload[:2]
            text = json.dumps({'type': 'list', 'len': len(payload), 'sample': sample}, ensure_ascii=True)
        else:
            text = json.dumps({'type': type(payload).__name__, 'value': str(payload)}, ensure_ascii=True)
    except Exception:
        text = repr(payload)

    if len(text) > limit:
        return text[:limit] + '...'
    return text

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

XTREAM_PROFILES_URL = 'https://github.com/michaz1988/michaz1988.github.io/releases/download/EPG/xtreamlist.json'
XTREAM_JSON_CACHE_FILE = os.path.join(PROFILE_DIR, 'xtream_profiles_json_cache.json')
XTREAM_PASTEBIN_CACHE_FILE = os.path.join(PROFILE_DIR, 'xtream_profiles_pastebin_cache.json')
PROFILES_CACHE_DURATION = 3600 # 1 hour in seconds
XTREAM_RO_STATUS_FILE = os.path.join(PROFILE_DIR, 'xtream_ro_status.json')
XTREAM_FAVORITES_FILE = os.path.join(PROFILE_DIR, 'xtream_favorites.json')
SERVER_URL = ADDON.getSetting('xtreme_url')
USERNAME = ADDON.getSetting('xtreme_username')
PASSWORD = ADDON.getSetting('xtreme_password')
RE_BOX_CHARS = re.compile(r"[\u2500-\u259F\u2500-\u257F]")
RE_CATEGORY_PREFIX = re.compile(r"^[\|\-\s]+ro[\|\s\:\-\[\(]?", re.IGNORECASE)

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

def get_profile_api_url(server_url, username, password, action=None, params=None):
    if not server_url:
        return None

    base = f"{server_url}/player_api.php?username={username}&password={password}"
    if action:
        base += f"&action={action}"
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
def get_profile_source_mode():
    return ADDON.getSetting('xtreme_profile_source') or '0'

def read_profiles_from_json():
    # Try to read from cache first
    if xbmcvfs.exists(XTREAM_JSON_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(XTREAM_JSON_CACHE_FILE)
            if (time.time() - cache_mod_time) < PROFILES_CACHE_DURATION:
                with xbmcvfs.File(XTREAM_JSON_CACHE_FILE, 'r') as f:
                    encoded_data = f.read()
                    return decode_data(encoded_data.encode('utf-8'))
        except (IOError, ValueError, OSError, zlib.error):
            pass # Cache invalid or corrupted, proceed to fetch

    # Fetch from xtream JSON source
    try:
        response = SESSION.get(XTREAM_PROFILES_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        profiles = []
        seen = set()

        for source in data.get('urls', []):
            server_base_url = str(source.get('url', '')).strip().rstrip('/')
            if not server_base_url:
                continue

            parsed_url = urlparse(server_base_url)
            server_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            region = str(source.get('region', '')).strip()

            for credentials in source.get('userpasses', []):
                username = str(credentials.get('user', '')).strip()
                password = str(credentials.get('pass', '')).strip()
                if not username or not password:
                    continue

                profile_key = (server_base_url.lower(), username.lower())
                if profile_key in seen:
                    continue
                seen.add(profile_key)

                profile_name = f"{parsed_url.netloc} ({username})"
                profiles.append({
                    "name": profile_name,
                    "server": server_base_url,
                    "user": username,
                    "pass": password,
                    "region": region,
                })

        # Cache the fetched profiles
        try:
            with xbmcvfs.File(XTREAM_JSON_CACHE_FILE, 'w') as f:
                encoded_data = encode_data(profiles)
                f.write(encoded_data.decode('utf-8'))
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache Xtream profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except (requests.exceptions.RequestException, ValueError, TypeError, json.JSONDecodeError) as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch profiles from Xtream JSON: {e}", xbmcgui.NOTIFICATION_ERROR)
        return []

def read_profiles_from_pastebin():
    if xbmcvfs.exists(XTREAM_PASTEBIN_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(XTREAM_PASTEBIN_CACHE_FILE)
            if (time.time() - cache_mod_time) < PROFILES_CACHE_DURATION:
                with xbmcvfs.File(XTREAM_PASTEBIN_CACHE_FILE, 'r') as f:
                    encoded_data = f.read()
                    return decode_data(encoded_data.encode('utf-8'))
        except (IOError, ValueError, OSError, zlib.error):
            pass

    try:
        response = SESSION.get(get_pastebin_url(), timeout=10)
        response.raise_for_status()
        content = decode_remote_data(response.text.strip())

        try:
            data_json = json.loads(content)
            content = data_json.get("data", "")
        except (json.JSONDecodeError, TypeError):
            pass

        profiles = []
        seen = set()
        xtream_pattern = r"(https?://[^\s]+?/get.php\?username=[^\s]+?&password=[^\s]+)"

        for match in re.finditer(xtream_pattern, content):
            full_url = match.group(1)
            parsed_url = urlparse(full_url)
            server_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            query_params = parse_qs(parsed_url.query)

            username = query_params.get('username', [''])[0].strip()
            password = query_params.get('password', [''])[0].strip()
            if not username or not password:
                continue

            profile_key = (server_base_url.lower(), username.lower())
            if profile_key in seen:
                continue
            seen.add(profile_key)

            profile_name = f"{parsed_url.netloc} ({username})"
            profiles.append({
                "name": profile_name,
                "server": server_base_url,
                "user": username,
                "pass": password,
                "region": "",
            })

        try:
            with xbmcvfs.File(XTREAM_PASTEBIN_CACHE_FILE, 'w') as f:
                encoded_data = encode_data(profiles)
                f.write(encoded_data.decode('utf-8'))
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache legacy Xtream profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except (requests.exceptions.RequestException, ValueError, TypeError, json.JSONDecodeError) as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch profiles from legacy pastebin: {e}", xbmcgui.NOTIFICATION_ERROR)
        return []

def read_profiles():
    profile_source_mode = get_profile_source_mode()
    if profile_source_mode == '1':
        return read_profiles_from_pastebin()
    return read_profiles_from_json()


def write_profiles(profiles):
    # This function is no longer used for writing profiles, as they come from pastebin.
    # It will be kept as a placeholder or removed if not needed elsewhere.
    # For now, it will just return False to prevent any writes.
    xbmcgui.Dialog().notification('Info', 'Profile writing is disabled.', xbmcgui.NOTIFICATION_INFO)
    return False

def get_profile_dns(profile):
    server_url = profile.get('server', '')
    parsed = urlparse(server_url)
    return (parsed.hostname or profile.get('name') or parsed.netloc or server_url or 'Unknown').strip()

def group_profiles_by_dns(profiles):
    grouped = {}
    for profile in profiles:
        dns = get_profile_dns(profile)
        dns_key = dns.lower()
        if dns_key not in grouped:
            grouped[dns_key] = {'dns': dns, 'profiles': []}
        grouped[dns_key]['profiles'].append(profile)

    grouped_list = list(grouped.values())
    grouped_list.sort(key=lambda group: (-len(group['profiles']), group['dns'].lower()))
    return grouped_list

def get_group_profiles(group_dns):
    profiles = read_profiles()
    matching_profiles = [
        profile for profile in profiles
        if get_profile_dns(profile).lower() == (group_dns or '').lower()
    ]
    matching_profiles.sort(key=lambda profile: (profile.get('user') or '').lower())
    return matching_profiles

def choose_profile_from_group(group_dns, heading):
    matching_profiles = get_group_profiles(group_dns)
    if not matching_profiles:
        xbmcgui.Dialog().notification('Error', 'Could not find users for this portal.', xbmcgui.NOTIFICATION_ERROR)
        return None

    if len(matching_profiles) == 1:
        return matching_profiles[0]

    active_profile_server = ADDON.getSetting('xtreme_url')
    active_profile_user = ADDON.getSetting('xtreme_username')
    labels = []
    for profile in matching_profiles:
        server_url = profile.get('server', '')
        parsed = urlparse(server_url)
        port_suffix = f":{parsed.port}" if parsed.port else ""
        username = profile.get('user') or 'Unknown User'
        label = f"{username} [{parsed.scheme}://{parsed.hostname or parsed.netloc}{port_suffix}]"
        if profile.get('server') == active_profile_server and profile.get('user') == active_profile_user:
            label += " (Active)"
        labels.append(label)

    selected_index = xbmcgui.Dialog().select(heading, labels)
    if selected_index < 0:
        return None
    return matching_profiles[selected_index]

def list_profiles():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Profiles")
    profiles = read_profiles()
    active_profile_server = ADDON.getSetting('xtreme_url')
    active_profile_user = ADDON.getSetting('xtreme_username')
    profile_source_mode = get_profile_source_mode()
    favorite_profiles = load_favorite_profiles()

    if not profiles:
        source_label = 'Legacy Pastebin' if profile_source_mode == '1' else 'Xtream JSON'
        xbmcgui.Dialog().notification('Info', f'No profiles found from {source_label}.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    source_label = 'Legacy Pastebin' if profile_source_mode == '1' else 'Xtream JSON'
    add_dir(f"[Source] {source_label} - {len(profiles)} users", {'mode': 'list_profiles'}, icon='DefaultNetwork.png')

    grouped_profiles = group_profiles_by_dns(profiles)

    for group in grouped_profiles:
        dns = group['dns']
        group_profiles = group['profiles']
        is_active_group = any(
            profile.get('server') == active_profile_server and
            profile.get('user') == active_profile_user
            for profile in group_profiles
        )

        display_name = dns
        if len(group_profiles) > 1:
            display_name += f" ({len(group_profiles)} users)"
        if is_active_group:
            display_name += " (Active)"

        url = build_url({'mode': 'select_profile_group', 'group_dns': dns})
        li = xbmcgui.ListItem(display_name)
        li.setArt({'icon': 'DefaultNetwork.png', 'thumb': 'DefaultNetwork.png'})
        context_menu = [
            ('Add user to PVR IPTV Simple Client', f'RunPlugin({build_url({"mode": "add_group_to_pvr", "group_dns": dns})})')
        ]

        if len(group_profiles) == 1:
            profile = group_profiles[0]
            server = profile.get('server', '')
            user = profile.get('user', '')
            if is_profile_favorite(server, user, favorite_profiles):
                context_menu.insert(0, ('Remove from Favorite', f'RunPlugin({build_url({"mode": "remove_profile_from_favorites", "server": server, "user": user})})'))
            else:
                context_menu.insert(0, ('Add to Favorite', f'RunPlugin({build_url({"mode": "add_profile_to_favorites", "server": server, "user": user, "password": profile.get("pass", ""), "name": profile.get("name", "")})})'))
        else:
            context_menu.insert(0, ('Add User to Favorite', f'RunPlugin({build_url({"mode": "add_favorite_from_group", "group_dns": dns})})'))

        li.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)

    # Removed add/remove profile options as per user request
    # add_dir("[+ Add New Profile]", {'mode': 'add_profile'})
    # if profiles:
    #     add_dir("[- Remove a Profile]", {'mode': 'remove_profile'})

    # NEW: Add force refresh link
    add_dir("[Force Refresh Profiles]", {'mode': 'force_refresh_profiles'}, icon='DefaultAddonUpdates.png')

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def add_profile():
    xbmcgui.Dialog().notification('Info', 'Adding new profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def remove_profile():
    xbmcgui.Dialog().notification('Info', 'Removing profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def force_refresh_profiles():
    cache_files = [XTREAM_JSON_CACHE_FILE, XTREAM_PASTEBIN_CACHE_FILE]
    cleared_any = False
    for cache_file in cache_files:
        if not xbmcvfs.exists(cache_file):
            continue
        try:
            xbmcvfs.delete(cache_file)
            cleared_any = True
        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to clear cache: {e}', xbmcgui.NOTIFICATION_ERROR)
            return

    if cleared_any:
        xbmcgui.Dialog().notification('Success', 'Profile caches cleared. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification('Info', 'No profile cache found. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer)')

def list_favorite_profiles():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Favorite")
    favorites = load_favorite_profiles()
    active_profile_server = ADDON.getSetting('xtreme_url')
    active_profile_user = ADDON.getSetting('xtreme_username')

    if not favorites:
        xbmcgui.Dialog().notification('Info', 'No favorite playlists found.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    favorites = sorted(favorites, key=lambda item: ((item.get('dns') or '').lower(), (item.get('user') or '').lower()))
    for favorite in favorites:
        server = favorite.get('server', '')
        user = favorite.get('user', '')
        password = favorite.get('pass', '')
        dns = favorite.get('dns') or favorite.get('name') or server
        display_name = f"{dns} - {user}"
        if server == active_profile_server and user == active_profile_user:
            display_name += " (Active)"

        li = xbmcgui.ListItem(display_name)
        li.setProperty('IsPlayable', 'false')
        li.setArt({'icon': 'DefaultFavourites.png', 'thumb': 'DefaultFavourites.png'})
        li.addContextMenuItems([
            ('Remove from Favorite', f'RunPlugin({build_url({"mode": "remove_profile_from_favorites", "server": server, "user": user, "refresh_mode": "favorites"})})')
        ])
        url = build_url({'mode': 'switch_profile', 'server': server, 'user': user, 'password': password, 'name': favorite.get('name', '')})
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def add_profile_to_favorites(server_url, username, password, name=None, refresh_mode='profiles'):
    if not server_url or not username:
        xbmcgui.Dialog().notification('Error', 'Missing profile details.', xbmcgui.NOTIFICATION_ERROR)
        return

    favorites = load_favorite_profiles()
    if is_profile_favorite(server_url, username, favorites):
        xbmcgui.Dialog().notification('Info', 'Playlist already in Favorite.', xbmcgui.NOTIFICATION_INFO)
    else:
        favorites.append(build_profile_favorite_entry(server_url, username, password, name))
        save_favorite_profiles(favorites)
        xbmcgui.Dialog().notification('Favorite', 'Playlist added to Favorite.', xbmcgui.NOTIFICATION_INFO)

    if refresh_mode == 'favorites':
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer&mode=list_profiles)')

def remove_profile_from_favorites(server_url, username, refresh_mode='profiles'):
    favorite_key = get_profile_favorite_key(server_url, username)
    favorites = load_favorite_profiles()
    filtered = [favorite for favorite in favorites if favorite.get('favorite_key') != favorite_key]

    if len(filtered) == len(favorites):
        xbmcgui.Dialog().notification('Info', 'Playlist was not in Favorite.', xbmcgui.NOTIFICATION_INFO)
    else:
        save_favorite_profiles(filtered)
        xbmcgui.Dialog().notification('Favorite', 'Playlist removed from Favorite.', xbmcgui.NOTIFICATION_INFO)

    if refresh_mode == 'favorites':
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer&mode=list_profiles)')

def add_favorite_from_group(group_dns):
    selected_profile = choose_profile_from_group(group_dns, f"Add Favorite - {group_dns}")
    if not selected_profile:
        xbmc.executebuiltin('Container.Refresh')
        return

    add_profile_to_favorites(
        selected_profile.get('server'),
        selected_profile.get('user'),
        selected_profile.get('pass'),
        selected_profile.get('name'),
    )

def select_profile_group(group_dns):
    selected_profile = choose_profile_from_group(group_dns, f"Select User - {group_dns}")
    if not selected_profile:
        xbmc.executebuiltin('Container.Refresh')
        return

    switch_profile(selected_profile.get('name'))

def add_group_to_pvr(group_dns):
    selected_profile = choose_profile_from_group(group_dns, f"Add to PVR - {group_dns}")
    if not selected_profile:
        xbmc.executebuiltin('Container.Refresh')
        return

    server = selected_profile.get('server', '')
    user = selected_profile.get('user', '')
    pwd = selected_profile.get('pass', '')
    if not server or not user or not pwd:
        xbmcgui.Dialog().notification('Error', 'Missing server credentials for selected user.', xbmcgui.NOTIFICATION_ERROR)
        return

    m3u_plus_url = f"{server}/get.php?username={user}&password={pwd}&type=m3u_plus"
    add_to_pvr(m3u_plus_url)

def build_xtream_stream_url(server_url, username, password, stream_type, stream_id, extension):
    path_segment = 'movie' if stream_type == 'vod' else stream_type
    return f"{server_url}/{path_segment}/{username}/{password}/{stream_id}.{extension}"

def test_xtream_stream_url(stream_url):
    response = None
    try:
        response = SESSION.get(stream_url, timeout=10, stream=True, allow_redirects=False)
        return response.status_code in (200, 206, 301, 302, 303, 307, 308)
    except requests.RequestException:
        return False
    finally:
        if response is not None:
            response.close()

def validate_xtream_profile(server_url, username, password):
    dp = xbmcgui.DialogProgress()
    dp.create('Xtream IPTV', 'Verific profilul selectat...')

    try:
        dp.update(15, 'Testez player_api...')
        auth_url = get_profile_api_url(server_url, username, password)
        if not auth_url:
            return False, 'Missing server URL.'

        auth_response = SESSION.get(auth_url, timeout=15)
        auth_response.raise_for_status()
        auth_data = auth_response.json()

        if not isinstance(auth_data, dict):
            return False, 'Invalid player_api response.'

        user_info = auth_data.get('user_info')
        if isinstance(user_info, dict) and str(user_info.get('auth', '1')) not in ('1', 'True', 'true'):
            return False, 'player_api authentication failed.'

        dp.update(45, 'Incarc streamuri pentru test...')
        candidate_streams = []
        stream_sources = [
            ('get_live_streams', 'live', 'ts'),
            ('get_vod_streams', 'vod', 'mp4'),
        ]

        for action, stream_type, default_extension in stream_sources:
            stream_api_url = get_profile_api_url(server_url, username, password, action)
            response = SESSION.get(stream_api_url, timeout=20)
            response.raise_for_status()
            items = response.json()
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                stream_id = item.get('stream_id')
                if not stream_id:
                    continue
                extension = item.get('container_extension') or default_extension
                candidate_streams.append({
                    'stream_type': stream_type,
                    'stream_id': stream_id,
                    'extension': extension,
                    'name': item.get('name') or str(stream_id),
                })

            if candidate_streams:
                break

        if not candidate_streams:
            return False, 'No test streams available for this profile.'

        random.shuffle(candidate_streams)
        test_candidates = candidate_streams[:3]

        for index, candidate in enumerate(test_candidates, start=1):
            dp.update(60 + (index * 10), f"Testez stream random {index}/{len(test_candidates)}...")
            stream_url = build_xtream_stream_url(
                server_url,
                username,
                password,
                candidate['stream_type'],
                candidate['stream_id'],
                candidate['extension'],
            )
            if test_xtream_stream_url(stream_url):
                log_debug(f"Xtream profile validation succeeded with stream '{candidate['name']}'")
                return True, None

        return False, 'Random stream test failed.'
    except (requests.RequestException, ValueError, TypeError) as e:
        log_debug(f"Xtream profile validation error: {e}")
        return False, str(e)
    finally:
        dp.close()

def switch_profile(name=None, server_url=None, username=None, password=None):
    profiles = read_profiles()
    profile_to_activate = None

    if name:
        profile_to_activate = next((p for p in profiles if p.get('name') == name), None)

    if not profile_to_activate and server_url and username:
        profile_to_activate = next(
            (p for p in profiles if p.get('server') == server_url and p.get('user') == username),
            None
        )

    if not profile_to_activate and server_url and username:
        parsed = urlparse(server_url)
        profile_to_activate = {
            'name': name or f"{parsed.netloc} ({username})",
            'server': server_url,
            'user': username,
            'pass': password or '',
        }

    if not profile_to_activate:
        xbmcgui.Dialog().notification('Error', 'Could not find profile to activate.', xbmcgui.NOTIFICATION_ERROR)
        return

    is_valid, failure_reason = validate_xtream_profile(
        profile_to_activate['server'],
        profile_to_activate['user'],
        profile_to_activate['pass'],
    )
    if not is_valid:
        xbmcgui.Dialog().notification(
            'Xtream IPTV',
            f'Profile check failed: {failure_reason or "Unknown error"}',
            xbmcgui.NOTIFICATION_ERROR
        )
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer&mode=list_profiles)')
        return

    ADDON.setSetting('xtreme_url', profile_to_activate['server'])
    ADDON.setSetting('xtreme_username', profile_to_activate['user'])
    ADDON.setSetting('xtreme_password', profile_to_activate['pass'])
    xbmcgui.Dialog().notification('Profile Switched', f"Activated profile: {profile_to_activate['name']}", xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer)') # Refresh the menu to show the main menu

def clean_category_title(title):
    if not title:
        return ""

    cleaned = RE_BOX_CHARS.sub("", str(title))
    cleaned = cleaned.replace("✰", "")
    cleaned = cleaned.strip(r"|-[]:() ")
    return cleaned.strip()

def get_romanian_categories(server_categories):
    if not server_categories:
        return []

    romanian_prefixes = [
        "ro",
        "ro|",
        "ro :",
        "ro-",
        "ro ",
        "ro\u2503",
        "ro\u2502",
        "ro\u2551",
        "ro\u2550",
        "ro\u2588",
        "\u2503ro",
        "\u2502ro",
        "\u2551ro",
        "\u2550ro",
        "\u2588ro",
        "ro[",
        "ro]",
        "[ro]",
        "[ro[",
        "ro(",
        "ro)",
        "ro:",
        "|eu| romania",
        "romania",
        "roumanie",
        "romanie",
        "✰ romania",
        "✰romania",
    ]

    romanian_cats = []
    prefixes_lower = [prefix.lower() for prefix in romanian_prefixes]

    for cat in server_categories:
        title = clean_category_title(cat.get("category_name") or cat.get("title") or "").strip()
        title_lower = title.lower()

        is_romanian = False
        for prefix in prefixes_lower:
            if title_lower.startswith(prefix):
                is_romanian = True
                break

        if not is_romanian and RE_CATEGORY_PREFIX.match(title_lower):
            is_romanian = True

        if not is_romanian and title_lower.startswith("ro"):
            if len(title_lower) == 2 or title_lower[2] in " |:-":
                is_romanian = True

        if is_romanian:
            romanian_cats.append(cat)

    return romanian_cats

def get_active_profile_key(server_url=None, username=None):
    server_value = server_url or ADDON.getSetting('xtreme_url')
    user_value = username or ADDON.getSetting('xtreme_username')
    if not server_value or not user_value:
        return None

    raw_key = f"{server_value}|{user_value}"
    return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

def load_ro_status_cache():
    if not xbmcvfs.exists(XTREAM_RO_STATUS_FILE):
        return {}

    try:
        with xbmcvfs.File(XTREAM_RO_STATUS_FILE, 'r') as f:
            raw_data = f.read()
        if not raw_data:
            return {}
        return json.loads(raw_data)
    except (ValueError, TypeError):
        return {}

def save_ro_status_cache(cache_data):
    with xbmcvfs.File(XTREAM_RO_STATUS_FILE, 'w') as f:
        f.write(json.dumps(cache_data))

def get_active_profile_ro_status():
    profile_key = get_active_profile_key()
    if not profile_key:
        return None
    return load_ro_status_cache().get(profile_key)

def load_favorite_profiles():
    if not xbmcvfs.exists(XTREAM_FAVORITES_FILE):
        return []

    try:
        with xbmcvfs.File(XTREAM_FAVORITES_FILE, 'r') as f:
            raw_data = f.read()
        if not raw_data:
            return []
        data = json.loads(raw_data)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []

def save_favorite_profiles(favorites):
    with xbmcvfs.File(XTREAM_FAVORITES_FILE, 'w') as f:
        f.write(json.dumps(favorites))

def get_profile_favorite_key(server_url, username):
    return get_active_profile_key(server_url, username)

def is_profile_favorite(server_url, username, favorites=None):
    favorites = favorites if favorites is not None else load_favorite_profiles()
    favorite_key = get_profile_favorite_key(server_url, username)
    return any(
        favorite.get('favorite_key') == favorite_key
        for favorite in favorites
    )

def build_profile_favorite_entry(server_url, username, password, name=None):
    parsed = urlparse(server_url or '')
    dns = parsed.hostname or parsed.netloc or server_url
    return {
        'favorite_key': get_profile_favorite_key(server_url, username),
        'server': server_url,
        'user': username,
        'pass': password,
        'name': name or dns,
        'dns': dns,
        'added_at': int(time.time()),
    }

def normalize_category_list(raw_categories):
    log_debug(f"normalize_category_list payload={describe_payload(raw_categories)}")

    if isinstance(raw_categories, list):
        normalized = [category for category in raw_categories if isinstance(category, dict)]
        log_debug(f"normalize_category_list list -> {len(normalized)} dict entries")
        return normalized

    if isinstance(raw_categories, dict):
        for key in ('categories', 'live_categories', 'vod_categories', 'series_categories'):
            nested = raw_categories.get(key)
            if isinstance(nested, list):
                normalized = [category for category in nested if isinstance(category, dict)]
                log_debug(f"normalize_category_list nested key '{key}' -> {len(normalized)} dict entries")
                return normalized

        dict_values = [value for value in raw_categories.values() if isinstance(value, dict)]
        if dict_values:
            log_debug(f"normalize_category_list dict values -> {len(dict_values)} dict entries")
            return dict_values

    log_debug("normalize_category_list -> 0 entries")
    return []

def verify_romanian_channels():
    api_url = get_api_url('get_live_categories')
    if not api_url:
        xbmcgui.Dialog().ok('Xtream IPTV', 'Please configure a portal and user first.')
        return

    dp = xbmcgui.DialogProgress()
    dp.create('Xtream IPTV', 'Verific categorii Live TV pentru canale romanesti...')

    try:
        response = SESSION.get(api_url, timeout=15)
        response.raise_for_status()
        raw_categories = response.json()
        log_debug(f"verify_romanian_channels raw categories={describe_payload(raw_categories)}")
        categories = normalize_category_list(raw_categories)
        romanian_categories = get_romanian_categories(categories)

        cache_data = load_ro_status_cache()
        profile_key = get_active_profile_key()
        if profile_key:
            cache_data[profile_key] = {
                'has_ro_channels': bool(romanian_categories),
                'category_count': len(romanian_categories),
                'checked_at': int(time.time()),
            }
            save_ro_status_cache(cache_data)

        if romanian_categories:
            xbmcgui.Dialog().notification(
                'Xtream IPTV',
                f'Gasite {len(romanian_categories)} categorii Live TV cu canale RO.',
                xbmcgui.NOTIFICATION_INFO
            )
        else:
            xbmcgui.Dialog().notification(
                'Xtream IPTV',
                'Nu au fost gasite categorii Live TV cu canale RO.',
                xbmcgui.NOTIFICATION_INFO
            )
    except (requests.RequestException, ValueError, TypeError) as e:
        xbmcgui.Dialog().ok('Xtream IPTV', f'Error verifying Romanian channels: {e}')
    finally:
        dp.close()

    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=xtremeiptvplayer)')

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
    add_dir('Manage Profiles', {'mode': 'list_profiles'}, icon='DefaultNetwork.png')
    add_dir('Favorite', {'mode': 'list_favorite_profiles'}, icon='DefaultFavourites.png')
    add_dir('Verifica Canale Romania', {'mode': 'verify_romanian_channels'}, icon='DefaultAddonLibrary.png')
    add_dir('Search', {'mode': 'open_search_menu'}, icon='DefaultAddonsSearch.png')
    ro_status = get_active_profile_ro_status() or {}
    add_dir('Live TV', {'mode': 'list_categories', 'type': 'live'}, icon='DefaultTVShows.png')
    if ro_status.get('has_ro_channels'):
        add_dir('Canale Romania', {'mode': 'list_romanian_categories'}, icon='DefaultTVShows.png')
    add_dir('VOD', {'mode': 'list_categories', 'type': 'vod'}, icon='DefaultMovies.png')
    add_dir('Series', {'mode': 'list_categories', 'type': 'series'}, icon='DefaultAddonVideo.png')
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def list_categories(category_type):
    action = f"get_{category_type}_categories"
    api_url = get_api_url(action)
    if not api_url:
        return
    
    try:
        response = SESSION.get(api_url, timeout=15)
        response.raise_for_status()
        raw_categories = response.json()
        log_debug(f"list_categories({category_type}) raw categories={describe_payload(raw_categories)}")
        categories = normalize_category_list(raw_categories)
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    if not categories:
        log_debug(f"list_categories({category_type}) no usable categories after normalization")
        xbmcgui.Dialog().notification('API Error', f"Unexpected response for {category_type} categories.", xbmcgui.NOTIFICATION_ERROR)
        return

    xbmcplugin.setPluginCategory(ADDON_HANDLE, category_type.title())
    for category in categories:
        category_id = category.get('category_id')
        category_name = category.get('category_name') or category.get('title') or 'Unknown'
        if not category_id:
            continue
        params = {'mode': 'list_items', 'type': category_type, 'category_id': category_id}
        if category_type == 'live':
            icon = 'DefaultTVShows.png'
        elif category_type == 'vod':
            icon = 'DefaultMovies.png'
        else:
            icon = 'DefaultAddonVideo.png'
        add_dir(category_name, params, icon=icon)
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def list_romanian_categories():
    api_url = get_api_url('get_live_categories')
    if not api_url:
        xbmcgui.Dialog().ok('Xtream IPTV', 'Please configure a portal and user first.')
        return

    try:
        response = SESSION.get(api_url, timeout=15)
        response.raise_for_status()
        raw_categories = response.json()
        log_debug(f"list_romanian_categories raw categories={describe_payload(raw_categories)}")
        categories = normalize_category_list(raw_categories)
        romanian_categories = get_romanian_categories(categories)
    except (requests.RequestException, ValueError, TypeError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    if not romanian_categories:
        xbmcgui.Dialog().ok('Xtream IPTV', 'No Romanian Live TV categories found.')
        return

    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Canale Romania")
    for category in romanian_categories:
        category_id = category.get('category_id')
        category_name = category.get('category_name') or category.get('title') or 'Unknown'
        if not category_id:
            continue
        params = {'mode': 'list_items', 'type': 'live', 'category_id': category_id}
        add_dir(category_name, params, icon='DefaultTVShows.png')
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
        log_debug(f"list_items({item_type}, {category_id}) raw items={describe_payload(items)}")
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('API Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return

    if not isinstance(items, list):
        log_debug(f"list_items({item_type}, {category_id}) unexpected items payload")
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
    
    playback_method = ADDON.getSettingInt('xtreme_playback_method') # 0: Default, 1: Adaptive, 2: FFmpeg

    # InputStream Adaptive
    if playback_method == 1:
        li = xbmcgui.ListItem(path=play_url)
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        li.setMimeType('application/vnd.apple.mpegurl')

        manifest_retries = ADDON.getSetting('xtreme_adaptive_manifest_retries')
        segment_retries = ADDON.getSetting('xtreme_adaptive_segment_retries')
        max_buffer = ADDON.getSetting('xtreme_adaptive_max_buffer_size')

        if manifest_retries:
            li.setProperty('inputstream.adaptive.manifest_load_retries', manifest_retries)
        if segment_retries:
            li.setProperty('inputstream.adaptive.segment_load_retries', segment_retries)
        if max_buffer:
            max_buffer_bytes = str(int(max_buffer) * 1024 * 1024)
            li.setProperty('inputstream.adaptive.max_buffer_size', max_buffer_bytes)
    # InputStream FFmpeg Direct
    elif playback_method == 2:
        li = xbmcgui.ListItem(path=play_url)
        li.setProperty('inputstream', 'inputstream.ffmpegdirect')
        li.setProperty('inputstream.ffmpegdirect.reconnect', '1')

        probesize = ADDON.getSetting('xtreme_ffmpeg_probesize')
        analyzeduration = ADDON.getSetting('xtreme_ffmpeg_analyzeduration')
        timeout = ADDON.getSetting('xtreme_ffmpeg_timeout')

        if probesize:
            li.setProperty('inputstream.ffmpegdirect.probesize', probesize)
        if analyzeduration:
            li.setProperty('inputstream.ffmpegdirect.analyzeduration', analyzeduration)
        if timeout:
            li.setProperty('inputstream.ffmpegdirect.timeout', timeout)
    # Default
    else:
        li = xbmcgui.ListItem(path=play_url + '|' + urlencode(HEADERS))

    li.setInfo(type='Video', infoLabels={'Title': 'Playing Stream'})
    xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, listitem=li)

def add_dir(name, params, icon=None):
    clean_name = clean_title(name)
    url = build_url(params)
    li = xbmcgui.ListItem(clean_name)
    if not icon:
        mode = params.get('mode')
        item_type = params.get('type')
        if mode in MENU_ICONS:
            icon = MENU_ICONS[mode]
        elif item_type == 'live':
            icon = 'DefaultTVShows.png'
        elif item_type == 'vod':
            icon = 'DefaultMovies.png'
        elif item_type == 'series':
            icon = 'DefaultAddonVideo.png'
        else:
            icon = 'DefaultFolder.png'
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
    if not icon:
        item_type = params.get('type')
        if item_type == 'live':
            icon = 'DefaultTVShows.png'
        elif item_type in ('movie', 'vod'):
            icon = 'DefaultMovies.png'
        elif item_type == 'series':
            icon = 'DefaultAddonVideo.png'
        else:
            icon = 'DefaultVideo.png'
    li.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=False)

def open_search_menu():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Search")
    add_dir('Search Movies', {'mode': 'search_items', 'type': 'vod'}, icon='DefaultAddonsSearch.png')
    add_dir('Search Series', {'mode': 'search_items', 'type': 'series'}, icon='DefaultAddonsSearch.png')
    add_dir('Search Live TV', {'mode': 'search_items', 'type': 'live'}, icon='DefaultAddonsSearch.png')
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

def search_items(item_type):
    """Searches all content for a given type."""
    dialog = xbmcgui.Dialog()
    query = dialog.input(f'Search {item_type.title()}', type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
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
        if not ADDON.getSetting('xtreme_url'):
            list_profiles()
        else:
            main_menu()
    elif mode == 'list_profiles':
        list_profiles()
    elif mode == 'list_favorite_profiles':
        list_favorite_profiles()
    elif mode == 'add_profile':
        add_profile()
    elif mode == 'remove_profile':
        remove_profile()
    elif mode == 'select_profile_group':
        select_profile_group(params.get('group_dns'))
    elif mode == 'switch_profile':
        switch_profile(
            params.get('name'),
            params.get('server'),
            params.get('user'),
            params.get('password'),
        )
    elif mode == 'add_to_pvr':
        add_to_pvr(params['url'])
    elif mode == 'add_group_to_pvr':
        add_group_to_pvr(params.get('group_dns'))
    elif mode == 'add_profile_to_favorites':
        add_profile_to_favorites(
            params.get('server'),
            params.get('user'),
            params.get('password'),
            params.get('name'),
            params.get('refresh_mode', 'profiles'),
        )
    elif mode == 'remove_profile_from_favorites':
        remove_profile_from_favorites(
            params.get('server'),
            params.get('user'),
            params.get('refresh_mode', 'profiles'),
        )
    elif mode == 'add_favorite_from_group':
        add_favorite_from_group(params.get('group_dns'))
    elif mode == 'force_refresh_profiles':
        force_refresh_profiles()
    elif mode == 'verify_romanian_channels':
        verify_romanian_channels()
    elif mode == 'open_search_menu':
        open_search_menu()
    elif mode == 'search_items':
        search_items(params['type'])
    elif mode == 'list_categories':
        list_categories(params['type'])
    elif mode == 'list_romanian_categories':
        list_romanian_categories()
    elif mode == 'list_items':
        list_items(params['type'], params['category_id'])
    elif mode == 'list_episodes':
        list_episodes(params['series_id'])
    elif mode == 'play':
        play_stream(params['type'], params['stream_id'], params.get('extension'))

if __name__ == '__main__':
    router(dict(parse_qsl(sys.argv[2][1:])))
