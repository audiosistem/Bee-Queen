# -*- coding: utf-8 -*-
import sys
import os
from urllib.parse import parse_qsl, urlencode, urlparse
import xbmcgui
import xbmcplugin
import xbmcaddon
import logging
import json
import xbmc, xbmcvfs
import re
import time
import requests
import zlib
import base64
import hashlib
import random

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



from .stalker_kodi import StalkerPortal

_URL = 'plugin://plugin.video.hub/'
_HANDLE = int(sys.argv[1])
_ADDON = xbmcaddon.Addon()
PROFILE_DIR = os.path.join(xbmcvfs.translatePath(_ADDON.getAddonInfo('profile')), 'stalker')
if not xbmcvfs.exists(PROFILE_DIR):
    xbmcvfs.mkdirs(PROFILE_DIR)
PROFILES_FILE = os.path.join(PROFILE_DIR, 'profiles.json')

def get_pastebin_url():
    pastebin_url_file = os.path.join(xbmcvfs.translatePath(_ADDON.getAddonInfo('path')), 'pastebin_url.txt')
    if xbmcvfs.exists(pastebin_url_file):
        with xbmcvfs.File(pastebin_url_file, 'r') as f:
            encoded_data = f.read()
            reversed_data = encoded_data[::-1]
            decoded_data = base64.b64decode(reversed_data)
            decompressed_data = zlib.decompress(decoded_data)
            data = json.loads(decompressed_data.decode('utf-8'))
            return data['url']
    return ""

STALKER_PASTEBIN_PROFILES_URL = get_pastebin_url()
STALKER_PASTEBIN_CACHE_FILE = os.path.join(PROFILE_DIR, 'stalker_pastebin_profiles_cache.json')
STALKER_PASTEBIN_CACHE_DURATION = 3600 # 1 hour in seconds
STALKER_VALID_MACS_URL = 'https://raw.githubusercontent.com/staycanuca/hub/refs/heads/main/valid_macs.json'
STALKER_VALID_MACS_CACHE_FILE = os.path.join(PROFILE_DIR, 'stalker_valid_macs_cache.json')
STALKER_VALID_MACS_CACHE_DURATION = 3600 # 1 hour in seconds
STALKER_RO_STATUS_FILE = os.path.join(PROFILE_DIR, 'stalker_ro_status.json')
STALKER_FAVORITES_FILE = os.path.join(PROFILE_DIR, 'stalker_favorites.json')
RE_BOX_CHARS = re.compile(r"[\u2500-\u259F\u2500-\u257F]")
RE_CATEGORY_PREFIX = re.compile(r"^[\|\-\s]+ro[\|\s\:\-\[\(]?", re.IGNORECASE)

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

def read_cached_data(cache_file, cache_duration):
    if not xbmcvfs.exists(cache_file):
        return None

    try:
        cache_mod_time = os.path.getmtime(cache_file)
        if (time.time() - cache_mod_time) >= cache_duration:
            return None
        with xbmcvfs.File(cache_file, 'rb') as f:
            encoded_data = f.read()
            return decode_data(encoded_data)
    except (IOError, ValueError, OSError):
        return None

def write_cached_data(cache_file, data):
    with xbmcvfs.File(cache_file, 'wb') as f:
        encoded_data = encode_data(data)
        f.write(encoded_data)

def get_url(**kwargs):
    """ Create a URL for a plugin route """
    # Ensure 'action' is the first parameter
    action_param = kwargs.pop('action', 'stalker') # Get action, default to 'stalker'
    
    # Encode the rest of the parameters
    query_string = urlencode(kwargs)
    
    # Construct the URL with action first
    if query_string:
        return f'{_URL}?action={action_param}&{query_string}'
    else:
        return f'{_URL}?action={action_param}'

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

def get_setting(key):
    """ Get a setting value """
    return _ADDON.getSetting(key)

def get_stalker_menu_icon(params=None, name=None):
    params = params or {}
    mode = params.get('mode', '')
    label = (name or '').lower()

    icon_map = {
        'list_profiles': 'DefaultNetwork.png',
        'list_favorite_profiles': 'DefaultFavourites.png',
        'verify_romanian_channels': 'DefaultAddonLibrary.png',
        'search': 'DefaultAddonsSearch.png',
        'search_movies': 'DefaultAddonsSearch.png',
        'search_series': 'DefaultAddonsSearch.png',
        'search_channels': 'DefaultAddonsSearch.png',
        'list_genres': 'DefaultTVShows.png',
        'list_romanian_genres': 'DefaultTVShows.png',
        'list_vod_categories': 'DefaultMovies.png',
        'list_series_categories': 'DefaultAddonVideo.png',
        'force_refresh_stalker_profiles': 'DefaultAddonUpdates.png',
        'switch_profile': 'DefaultNetwork.png',
        'select_profile_group': 'DefaultNetwork.png',
        'add_profile_to_favorites': 'DefaultFavourites.png',
        'remove_profile_from_favorites': 'DefaultFavourites.png',
        'add_favorite_from_group': 'DefaultFavourites.png',
    }
    if mode in icon_map:
        return icon_map[mode]

    if 'profile' in label:
        return 'DefaultNetwork.png'
    if 'favorite' in label:
        return 'DefaultFavourites.png'
    if 'search' in label or 'cauta' in label:
        return 'DefaultAddonsSearch.png'
    if 'movie' in label or 'film' in label:
        return 'DefaultMovies.png'
    if 'series' in label or 'serial' in label:
        return 'DefaultAddonVideo.png'
    if 'live' in label or 'tv' in label or 'canale romania' in label:
        return 'DefaultTVShows.png'
    if 'setari' in label or 'settings' in label:
        return 'DefaultAddonService.png'
    if 'refresh' in label or 'verifica' in label:
        return 'DefaultAddonUpdates.png'
    return 'DefaultFolder.png'

def set_list_item_art(list_item, icon):
    if not icon:
        return
    list_item.setArt({
        'thumb': icon,
        'icon': icon,
        'fanart': icon,
        'poster': icon,
        'banner': icon,
        'landscape': icon,
    })

def add_dir(name, params, icon=None):
    url = get_url(**params)
    list_item = xbmcgui.ListItem(label=name)
    icon = icon or get_stalker_menu_icon(params, name)
    set_list_item_art(list_item, icon)
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=True)

def add_action_item(name, params, icon=None, is_folder=False, context_menu=None):
    url = get_url(**params)
    list_item = xbmcgui.ListItem(label=name)
    list_item.setProperty('IsPlayable', 'false')
    icon = icon or get_stalker_menu_icon(params, name)
    set_list_item_art(list_item, icon)
    if context_menu:
        list_item.addContextMenuItems(context_menu)
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=is_folder)

def add_item(name, params, icon=None, plot=None):
    url = get_url(**params)
    list_item = xbmcgui.ListItem(label=name)
    info_labels = {'Title': name}
    if plot:
        info_labels['plot'] = plot
    list_item.setInfo(type='Video', infoLabels=info_labels)
    list_item.setProperty('IsPlayable', 'true')
    set_list_item_art(list_item, icon)
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=False)

def clean_title(title):
    # Remove any characters that are not word characters, whitespace, or basic punctuation.
    cleaned_title = re.sub(r'[^\w\s\-.:]', '', title)
    # Clean up whitespace
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def get_profile_source_mode():
    return _ADDON.getSetting('stalker_profile_source') or '0'

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
        title = clean_category_title(cat.get("title", "")).strip()
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

def get_active_profile_key(portal_url=None, mac_address=None):
    portal_value = portal_url or _ADDON.getSetting('stalker_portal_url')
    mac_value = mac_address or _ADDON.getSetting('stalker_mac_address')
    if not portal_value or not mac_value:
        return None
    raw_key = f"{portal_value}|{mac_value}"
    return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

def load_ro_status_cache():
    if not xbmcvfs.exists(STALKER_RO_STATUS_FILE):
        return {}

    try:
        with xbmcvfs.File(STALKER_RO_STATUS_FILE, 'r') as f:
            raw_data = f.read()
        if not raw_data:
            return {}
        return json.loads(raw_data)
    except (ValueError, TypeError):
        return {}

def save_ro_status_cache(cache_data):
    with xbmcvfs.File(STALKER_RO_STATUS_FILE, 'w') as f:
        f.write(json.dumps(cache_data))

def get_active_profile_ro_status():
    profile_key = get_active_profile_key()
    if not profile_key:
        return None
    return load_ro_status_cache().get(profile_key)

def load_favorite_profiles():
    if not xbmcvfs.exists(STALKER_FAVORITES_FILE):
        return []

    try:
        with xbmcvfs.File(STALKER_FAVORITES_FILE, 'r') as f:
            raw_data = f.read()
        if not raw_data:
            return []
        data = json.loads(raw_data)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []

def save_favorite_profiles(favorites):
    with xbmcvfs.File(STALKER_FAVORITES_FILE, 'w') as f:
        f.write(json.dumps(favorites))

def get_profile_favorite_key(portal_url, mac_address):
    return get_active_profile_key(portal_url, mac_address)

def is_profile_favorite(portal_url, mac_address, favorites=None):
    favorites = favorites if favorites is not None else load_favorite_profiles()
    favorite_key = get_profile_favorite_key(portal_url, mac_address)
    return any(
        favorite.get('favorite_key') == favorite_key
        for favorite in favorites
    )

def build_profile_favorite_entry(portal_url, mac_address, name=None):
    parsed = urlparse(portal_url or '')
    return {
        'favorite_key': get_profile_favorite_key(portal_url, mac_address),
        'portal_url': portal_url,
        'mac_address': mac_address,
        'name': name or parsed.hostname or parsed.netloc or portal_url,
        'dns': parsed.hostname or parsed.netloc or portal_url,
        'added_at': int(time.time()),
    }

def get_current_profile_favorite_context_menu():
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    if not portal_url or not mac_address:
        return []

    favorites = load_favorite_profiles()
    if is_profile_favorite(portal_url, mac_address, favorites):
        return [('Remove Playlist from Favorite', f'RunPlugin({get_url(mode="remove_profile_from_favorites", portal_url=portal_url, mac_address=mac_address)})')]
    return [('Add Playlist to Favorite', f'RunPlugin({get_url(mode="add_profile_to_favorites", portal_url=portal_url, mac_address=mac_address)})')]

def get_group_profiles(group_dns):
    profiles = read_profiles()
    return [
        profile for profile in profiles
        if get_profile_dns(profile).lower() == (group_dns or '').lower()
    ]

def choose_profile_from_group(group_dns, heading):
    matching_profiles = get_group_profiles(group_dns)
    if not matching_profiles:
        xbmcgui.Dialog().notification('Error', 'Could not find MACs for this portal.', xbmcgui.NOTIFICATION_ERROR)
        return None

    if len(matching_profiles) == 1:
        return matching_profiles[0]

    labels = []
    active_profile_portal = _ADDON.getSetting('stalker_portal_url')
    active_profile_mac = _ADDON.getSetting('stalker_mac_address')
    for profile in matching_profiles:
        mac_address = profile.get('mac_address', 'Unknown MAC')
        portal_url = profile.get('portal_url', '')
        parsed = urlparse(portal_url)
        port_suffix = f":{parsed.port}" if parsed.port else ""
        label = f"{mac_address} [{parsed.scheme}://{parsed.hostname or parsed.netloc}{port_suffix}]"
        if (
            profile.get('portal_url') == active_profile_portal and
            profile.get('mac_address') == active_profile_mac
        ):
            label += " (Active)"
        labels.append(label)

    selected_index = xbmcgui.Dialog().select(heading, labels)
    if selected_index < 0:
        return None
    return matching_profiles[selected_index]

def read_profiles_from_pastebin():
    logger.debug("[stalker] Calling read_profiles_from_pastebin")
    cached_profiles = read_cached_data(STALKER_PASTEBIN_CACHE_FILE, STALKER_PASTEBIN_CACHE_DURATION)
    if cached_profiles is not None:
        return cached_profiles

    try:
        session = requests.Session()
        response = session.get(STALKER_PASTEBIN_PROFILES_URL, timeout=10)
        response.raise_for_status()
        content = decode_remote_data(response.text.strip())

        try:
            data_json = json.loads(content)
            content = data_json.get("data", "")
        except (json.JSONDecodeError, TypeError):
            pass

        profiles = []
        stalker_pattern = r"(https?://[^\s]+?)\s+MAC\s+:\s+([0-9A-Fa-f:]{17})"

        for match in re.finditer(stalker_pattern, content):
            portal_url_part = match.group(1)
            mac_address = match.group(2)

            parsed_url = urlparse(portal_url_part)
            portal_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            profile_name = parsed_url.hostname or parsed_url.netloc

            profiles.append({
                "name": profile_name,
                "portal_url": portal_url,
                "mac_address": mac_address,
                "source": "pastebin"
            })

        try:
            write_cached_data(STALKER_PASTEBIN_CACHE_FILE, profiles)
            logger.debug("[stalker] Stalker profiles cached successfully.")
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache Stalker profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch Stalker profiles from pastebin: {e}", xbmcgui.NOTIFICATION_ERROR)
        logger.error(f"[stalker] Failed to fetch Stalker profiles: {e}", exc_info=True)
        return []

def read_profiles_from_valid_macs():
    logger.debug("[stalker] Calling read_profiles_from_valid_macs")
    cached_profiles = read_cached_data(STALKER_VALID_MACS_CACHE_FILE, STALKER_VALID_MACS_CACHE_DURATION)
    if cached_profiles is not None:
        return cached_profiles

    try:
        session = requests.Session()
        response = session.get(STALKER_VALID_MACS_URL, timeout=15)
        response.raise_for_status()
        data = response.json()

        profiles = []
        for server in data.get('servers', []):
            if str(server.get('type', 'stalker')).lower() != 'stalker':
                continue

            portal_url = str(server.get('portal_url', '')).strip()
            if not portal_url:
                continue

            parsed_url = urlparse(portal_url)
            profile_name = parsed_url.hostname or server.get('name') or parsed_url.netloc

            for mac_address in server.get('macs', []):
                mac_address = str(mac_address).strip()
                if not mac_address:
                    continue

                profiles.append({
                    "name": profile_name,
                    "portal_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
                    "mac_address": mac_address,
                    "source": "valid_macs"
                })

        try:
            write_cached_data(STALKER_VALID_MACS_CACHE_FILE, profiles)
            logger.debug("[stalker] Valid MACs profiles cached successfully.")
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache Valid MACs profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch Stalker profiles from Valid MACs JSON: {e}", xbmcgui.NOTIFICATION_ERROR)
        logger.error(f"[stalker] Failed to fetch Valid MACs profiles: {e}", exc_info=True)
        return []
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        xbmcgui.Dialog().notification('Error', f"Invalid Valid MACs JSON format: {e}", xbmcgui.NOTIFICATION_ERROR)
        logger.error(f"[stalker] Invalid Valid MACs JSON format: {e}", exc_info=True)
        return []

def read_profiles():
    logger.debug("[stalker] Calling read_profiles")
    profile_source_mode = get_profile_source_mode()
    if profile_source_mode == '1':
        return read_profiles_from_pastebin()
    return read_profiles_from_valid_macs()

def write_profiles(profiles):
    logger.debug(f"[stalker] Calling write_profiles with profiles: {profiles}")
    # This function is no longer used for writing profiles, as they come from pastebin.
    # It will be kept as a placeholder or removed if not needed elsewhere.
    # For now, it will just return False to prevent any writes.
    xbmcgui.Dialog().notification('Info', 'Stalker Profile writing is disabled.', xbmcgui.NOTIFICATION_INFO)
    return False

def get_profile_dns(profile):
    portal_url = profile.get('portal_url', '')
    parsed = urlparse(portal_url)
    return (parsed.hostname or profile.get('name') or parsed.netloc or portal_url or 'Unknown').strip()

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

def list_profiles():
    logger.debug("[stalker] Calling list_profiles")
    xbmcplugin.setPluginCategory(_HANDLE, "Profiles")
    xbmcplugin.setContent(_HANDLE, 'files')
    profiles = read_profiles()
    profile_source_mode = get_profile_source_mode()
    active_profile_portal = _ADDON.getSetting('stalker_portal_url')
    active_profile_mac = _ADDON.getSetting('stalker_mac_address') # Get active MAC
    favorite_profiles = load_favorite_profiles()

    if not profiles:
        profile_source_mode = get_profile_source_mode()
        source_label = 'Valid MACs JSON' if profile_source_mode != '1' else 'pastebin'
        xbmcgui.Dialog().notification('Info', f'No Stalker profiles found from {source_label}.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    source_label = 'Valid MACs JSON' if profile_source_mode != '1' else 'Pastebin Profiles'
    add_action_item(f"[Source] {source_label} - {len(profiles)} MACs", {'mode': 'list_profiles'})

    grouped_profiles = group_profiles_by_dns(profiles)

    for group in grouped_profiles:
        dns = group['dns']
        group_profiles = group['profiles']
        is_active_group = any(
            profile.get('portal_url') == active_profile_portal and
            profile.get('mac_address') == active_profile_mac
            for profile in group_profiles
        )

        if len(group_profiles) == 1:
            profile = group_profiles[0]
            display_name = dns
            if is_active_group:
                display_name += " (Active)"
            portal_url = profile['portal_url']
            mac_address = profile['mac_address']
            if is_profile_favorite(portal_url, mac_address, favorite_profiles):
                context_menu = [('Remove from Favorite', f'RunPlugin({get_url(mode="remove_profile_from_favorites", portal_url=portal_url, mac_address=mac_address)})')]
            else:
                context_menu = [('Add to Favorite', f'RunPlugin({get_url(mode="add_profile_to_favorites", portal_url=portal_url, mac_address=mac_address)})')]
            add_action_item(
                display_name,
                {'mode': 'switch_profile', 'portal_url': portal_url, 'mac_address': mac_address},
                context_menu=context_menu,
            )
            continue

        display_name = f"{dns} ({len(group_profiles)} MACs)"
        if is_active_group:
            display_name += " (Active)"
        add_action_item(
            display_name,
            {'mode': 'select_profile_group', 'group_dns': dns},
            context_menu=[('Add MAC to Favorite', f'RunPlugin({get_url(mode="add_favorite_from_group", group_dns=dns)})')]
        )

    # Removed add/remove profile options as per user request
    # add_dir("[+ Add New Profile]", {'mode': 'add_profile'})
    # if profiles:
    #     add_dir("[- Remove a Profile]", {'mode': 'remove_profile'})

    # Add force refresh link
    add_action_item("[Force Refresh Stalker Profiles]", {'mode': 'force_refresh_stalker_profiles'})

    xbmcplugin.endOfDirectory(_HANDLE)

def list_favorite_profiles():
    logger.debug("[stalker] Calling list_favorite_profiles")
    xbmcplugin.setPluginCategory(_HANDLE, "Favorite")
    xbmcplugin.setContent(_HANDLE, 'files')
    favorites = load_favorite_profiles()
    active_profile_portal = _ADDON.getSetting('stalker_portal_url')
    active_profile_mac = _ADDON.getSetting('stalker_mac_address')

    if not favorites:
        xbmcgui.Dialog().notification('Info', 'No favorite playlists found.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    favorites = sorted(favorites, key=lambda item: ((item.get('dns') or '').lower(), (item.get('mac_address') or '').lower()))
    for favorite in favorites:
        portal_url = favorite.get('portal_url', '')
        mac_address = favorite.get('mac_address', '')
        dns = favorite.get('dns') or favorite.get('name') or portal_url
        display_name = f"{dns} - {mac_address}"
        if portal_url == active_profile_portal and mac_address == active_profile_mac:
            display_name += " (Active)"

        add_action_item(
            display_name,
            {'mode': 'switch_profile', 'portal_url': portal_url, 'mac_address': mac_address},
            context_menu=[('Remove from Favorite', f'RunPlugin({get_url(mode="remove_profile_from_favorites", portal_url=portal_url, mac_address=mac_address, refresh_mode="favorites")})')]
        )

    xbmcplugin.endOfDirectory(_HANDLE)


def add_profile():
    logger.debug("[stalker] Calling add_profile")
    xbmcgui.Dialog().notification('Info', 'Adding new Stalker profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def remove_profile():
    logger.debug("[stalker] Calling remove_profile")
    xbmcgui.Dialog().notification('Info', 'Removing Stalker profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def force_refresh_stalker_profiles():
    logger.debug("[stalker] Calling force_refresh_stalker_profiles")
    cache_files = [STALKER_PASTEBIN_CACHE_FILE, STALKER_VALID_MACS_CACHE_FILE]
    cleared_any = False
    for cache_file in cache_files:
        if not xbmcvfs.exists(cache_file):
            continue
        try:
            xbmcvfs.delete(cache_file)
            cleared_any = True
        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to clear Stalker cache: {e}', xbmcgui.NOTIFICATION_ERROR)
            logger.error(f"[stalker] Error clearing cache: {e}", exc_info=True)
            return

    if cleared_any:
        xbmcgui.Dialog().notification('Success', 'Stalker profile caches cleared. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification('Info', 'No Stalker profile cache found. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker)')

def select_profile_group(group_dns):
    logger.debug(f"[stalker] Calling select_profile_group with group_dns: {group_dns}")
    selected_profile = choose_profile_from_group(group_dns, f"Select MAC - {group_dns}")
    if not selected_profile:
        xbmc.executebuiltin('Container.Refresh')
        return

    switch_profile(selected_profile['portal_url'], selected_profile['mac_address'])

def add_profile_to_favorites(portal_url, mac_address, refresh_mode='profiles'):
    logger.debug(f"[stalker] Calling add_profile_to_favorites with portal_url: {portal_url}, mac_address: {mac_address}")
    if not portal_url or not mac_address:
        xbmcgui.Dialog().notification('Error', 'Missing profile details.', xbmcgui.NOTIFICATION_ERROR)
        return

    favorites = load_favorite_profiles()
    if is_profile_favorite(portal_url, mac_address, favorites):
        xbmcgui.Dialog().notification('Info', 'Playlist already in Favorite.', xbmcgui.NOTIFICATION_INFO)
    else:
        parsed = urlparse(portal_url)
        favorites.append(build_profile_favorite_entry(portal_url, mac_address, parsed.hostname or parsed.netloc))
        save_favorite_profiles(favorites)
        xbmcgui.Dialog().notification('Favorite', 'Playlist added to Favorite.', xbmcgui.NOTIFICATION_INFO)

    target = 'favorites' if refresh_mode == 'favorites' else 'profiles'
    if target == 'favorites':
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker&mode=list_profiles)')

def remove_profile_from_favorites(portal_url, mac_address, refresh_mode='profiles'):
    logger.debug(f"[stalker] Calling remove_profile_from_favorites with portal_url: {portal_url}, mac_address: {mac_address}")
    favorite_key = get_profile_favorite_key(portal_url, mac_address)
    favorites = load_favorite_profiles()
    filtered = [favorite for favorite in favorites if favorite.get('favorite_key') != favorite_key]

    if len(filtered) == len(favorites):
        xbmcgui.Dialog().notification('Info', 'Playlist was not in Favorite.', xbmcgui.NOTIFICATION_INFO)
    else:
        save_favorite_profiles(filtered)
        xbmcgui.Dialog().notification('Favorite', 'Playlist removed from Favorite.', xbmcgui.NOTIFICATION_INFO)

    target = 'favorites' if refresh_mode == 'favorites' else 'profiles'
    if target == 'favorites':
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker&mode=list_profiles)')

def add_favorite_from_group(group_dns):
    logger.debug(f"[stalker] Calling add_favorite_from_group with group_dns: {group_dns}")
    selected_profile = choose_profile_from_group(group_dns, f"Add Favorite - {group_dns}")
    if not selected_profile:
        xbmc.executebuiltin('Container.Refresh')
        return

    add_profile_to_favorites(selected_profile.get('portal_url'), selected_profile.get('mac_address'))

def validate_stalker_profile(portal_url, mac_address):
    dp = xbmcgui.DialogProgress()
    dp.create('Stalker Player', 'Verific profilul selectat...')

    try:
        dp.update(15, 'Testez handshake-ul portalului...')
        with StalkerPortal(portal_url, mac_address) as portal:
            genres = portal.get_itv_categories()
            if not genres:
                return False, 'No Live TV categories found.'

            dp.update(45, 'Incarc categorii si canale pentru test...')
            candidate_channels = []
            shuffled_genres = list(genres)
            random.shuffle(shuffled_genres)

            for genre in shuffled_genres[:3]:
                genre_id = genre.get('id')
                if not genre_id:
                    continue

                channels = portal.get_channels_in_category(genre_id)
                if not channels:
                    continue

                valid_channels = [
                    channel for channel in channels
                    if isinstance(channel, dict) and channel.get('cmd') and channel.get('id')
                ]
                if valid_channels:
                    candidate_channels.extend(valid_channels[:5])
                    break

            if not candidate_channels:
                return False, 'No test channels available for this portal.'

            random.shuffle(candidate_channels)
            test_candidates = candidate_channels[:3]

            for index, channel in enumerate(test_candidates, start=1):
                dp.update(60 + (index * 10), f"Generez link random {index}/{len(test_candidates)}...")
                stream_url = portal.get_stream_link(channel.get('cmd'), channel.get('id'))
                if stream_url:
                    logger.debug(f"[stalker] Validation succeeded with channel: {channel.get('name')}")
                    return True, None

        return False, 'Random stream link generation failed.'
    except Exception as e:
        logger.error(f"[stalker] Validation error: {e}", exc_info=True)
        return False, str(e)
    finally:
        dp.close()

def switch_profile(portal_url, mac_address):
    logger.debug(f"[stalker] Calling switch_profile with portal_url: {portal_url}, mac_address: {mac_address}")
    profiles = read_profiles()
    profile_to_activate = next((p for p in profiles if p.get('portal_url') == portal_url and p.get('mac_address') == mac_address), None)

    if not profile_to_activate and portal_url and mac_address:
        parsed = urlparse(portal_url)
        profile_to_activate = {
            'portal_url': portal_url,
            'mac_address': mac_address,
            'name': parsed.hostname or parsed.netloc or portal_url,
        }

    if not profile_to_activate:
        xbmcgui.Dialog().notification('Error', 'Could not find profile to activate.', xbmcgui.NOTIFICATION_ERROR)
        return

    is_valid, failure_reason = validate_stalker_profile(
        profile_to_activate['portal_url'],
        profile_to_activate['mac_address'],
    )
    if not is_valid:
        xbmcgui.Dialog().notification(
            'Stalker Player',
            f'Profile check failed: {failure_reason or "Unknown error"}',
            xbmcgui.NOTIFICATION_ERROR
        )
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker&mode=list_profiles)')
        return

    _ADDON.setSetting('stalker_portal_url', profile_to_activate['portal_url'])
    _ADDON.setSetting('stalker_mac_address', profile_to_activate['mac_address'])
    xbmcgui.Dialog().notification('Profile Switched', f"Activated profile: {profile_to_activate['name']}", xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker)') # Refresh the menu to show the main menu

def verify_romanian_channels():
    logger.debug("[stalker] Calling verify_romanian_channels")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    if not portal_url or not mac_address:
        xbmcgui.Dialog().ok('Stalker Player', 'Please configure Portal URL and MAC Address in addon settings.')
        return

    dp = xbmcgui.DialogProgress()
    dp.create('Stalker Player', 'Verific categorii Live TV pentru canale romanesti...')

    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            genres = portal.get_itv_categories()
            romanian_categories = get_romanian_categories(genres)

        cache_data = load_ro_status_cache()
        cache_data[get_active_profile_key(portal_url, mac_address)] = {
            'has_ro_channels': bool(romanian_categories),
            'category_count': len(romanian_categories),
            'checked_at': int(time.time()),
        }
        save_ro_status_cache(cache_data)

        if romanian_categories:
            xbmcgui.Dialog().notification(
                'Stalker Player',
                f'Gasite {len(romanian_categories)} categorii Live TV cu canale RO.',
                xbmcgui.NOTIFICATION_INFO
            )
        else:
            xbmcgui.Dialog().notification(
                'Stalker Player',
                'Nu au fost gasite categorii Live TV cu canale RO.',
                xbmcgui.NOTIFICATION_INFO
            )
    except Exception as e:
        logger.error(f"Error verifying Romanian channels: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error verifying Romanian channels: {e}')
    finally:
        dp.close()

    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker)')

def list_categories():
    logger.debug("[stalker] Calling list_categories")
    """ List the main categories """
    logger.debug("Listing categories")
    xbmcplugin.setPluginCategory(_HANDLE, "Main Menu")
    xbmcplugin.setContent(_HANDLE, 'files')
    add_dir('Manage Profiles', {'mode': 'list_profiles'})
    add_dir('Favorite', {'mode': 'list_favorite_profiles'})
    add_action_item('Verifica Canale Romania', {'mode': 'verify_romanian_channels'})
    add_dir('Search', {'mode': 'search'})
    ro_status = get_active_profile_ro_status() or {}
    categories = [
        {'name': 'Live TV', 'mode': 'list_genres'},
        {'name': 'Movies', 'mode': 'list_vod_categories'},
        {'name': 'Series', 'mode': 'list_series_categories'}
    ]
    if ro_status.get('has_ro_channels'):
        categories.insert(1, {'name': 'Canale Romania', 'mode': 'list_romanian_genres'})
    for category in categories:
        list_item = xbmcgui.ListItem(label=category['name'])
        icon = get_stalker_menu_icon({'mode': category['mode']}, category['name'])
        set_list_item_art(list_item, icon)
        url = get_url(mode=category['mode'])
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    xbmcplugin.endOfDirectory(_HANDLE)

def list_genres():
    """ List genres for Live TV """
    logger.debug("Listing genres")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    if not portal_url or not mac_address:
        xbmcgui.Dialog().ok('Stalker Player', 'Please configure Portal URL and MAC Address in addon settings.')
        return

    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            genres = portal.get_itv_categories()
            logger.debug(f"Got genres: {genres}")
            if not genres:
                xbmcgui.Dialog().ok('Stalker Player', 'No genres found. Please check your portal URL and MAC address.')
                return
            for genre in genres:
                list_item = xbmcgui.ListItem(label=genre['title'])
                set_list_item_art(list_item, 'DefaultTVShows.png')
                url = get_url(mode='list_channels', genre_id=genre['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing genres: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing genres: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_romanian_genres():
    """List only Romanian genres for Live TV."""
    logger.debug("Listing Romanian genres")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    if not portal_url or not mac_address:
        xbmcgui.Dialog().ok('Stalker Player', 'Please configure Portal URL and MAC Address in addon settings.')
        return

    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            genres = portal.get_itv_categories()
            romanian_genres = get_romanian_categories(genres)
            logger.debug(f"Got Romanian genres: {romanian_genres}")
            if not romanian_genres:
                xbmcgui.Dialog().ok('Stalker Player', 'No Romanian Live TV categories found.')
                return
            for genre in romanian_genres:
                list_item = xbmcgui.ListItem(label=genre['title'])
                set_list_item_art(list_item, 'DefaultTVShows.png')
                url = get_url(mode='list_channels', genre_id=genre['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing Romanian genres: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing Romanian genres: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_channels(genre_id):
    """ List channels for a specific genre """
    logger.debug(f"Listing channels for genre_id: {genre_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            channels = portal.get_channels_in_category(genre_id)
            logger.debug(f"Got channels: {channels}")
            if not channels:
                xbmcgui.Dialog().ok('Stalker Player', 'No channels found in this genre.')
                return
            for channel in channels:
                list_item = xbmcgui.ListItem(label=channel['name'])
                list_item.setProperty('IsPlayable', 'true')
                channel_icon = channel.get('logo') or 'DefaultTVShows.png'
                set_list_item_art(list_item, channel_icon)
                list_item.addContextMenuItems(get_current_profile_favorite_context_menu())
                url = get_url(mode='play', cmd=channel['cmd'], stream_id=channel['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=False)
    except Exception as e:
        logger.error(f"Error listing channels: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing channels: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_vod_categories():
    logger.debug("[stalker] Calling list_vod_categories")
    """ List VOD categories """
    logger.debug("Listing VOD categories")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    if not portal_url or not mac_address:
        xbmcgui.Dialog().ok('Stalker Player', 'Please configure Portal URL and MAC Address in addon settings.')
        return

    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            categories = portal.get_vod_categories()
            logger.debug(f"Got VOD categories: {categories}")
            if not categories:
                xbmcgui.Dialog().ok('Stalker Player', 'No VOD categories found.')
                return
            for category in categories:
                list_item = xbmcgui.ListItem(label=category['title'])
                set_list_item_art(list_item, 'DefaultMovies.png')
                url = get_url(mode='list_vod', category_id=category['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing VOD categories: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing VOD categories: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_vod(category_id):
    """ List VOD items for a specific category """
    logger.debug(f"Listing VOD items for category_id: {category_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            vod_items = portal.get_vod_in_category(category_id)
            logger.debug(f"Got VOD items: {vod_items}")
            if not vod_items:
                xbmcgui.Dialog().ok('Stalker Player', 'No VOD items found in this category.')
                return
            for item in vod_items:
                list_item = xbmcgui.ListItem(label=item['name'])
                list_item.setInfo('video', {'title': item['name'], 'plot': item.get('description'), 'year': item.get('year')})
                list_item.setProperty('IsPlayable', 'true')
                item_icon = item.get('screenshot_uri') or item.get('cover') or 'DefaultMovies.png'
                set_list_item_art(list_item, item_icon)
                url = get_url(mode='play_vod', movie_id=item['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=False)
    except Exception as e:
        logger.error(f"Error listing VOD items: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing VOD items: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_series_categories():
    """ List Series categories """
    logger.debug("Listing Series categories")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    if not portal_url or not mac_address:
        xbmcgui.Dialog().ok('Stalker Player', 'Please configure Portal URL and MAC Address in addon settings.')
        return

    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            categories = portal.get_series_categories()
            logger.debug(f"Got Series categories: {categories}")
            if not categories:
                xbmcgui.Dialog().ok('Stalker Player', 'No Series categories found.')
                return
            for category in categories:
                list_item = xbmcgui.ListItem(label=category['title'])
                set_list_item_art(list_item, 'DefaultAddonVideo.png')
                url = get_url(mode='list_series', category_id=category['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing Series categories: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing Series categories: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_series(category_id):
    """ List series for a specific category """
    logger.debug(f"Listing series for category_id: {category_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            series_items = portal.get_series_in_category(category_id)
            logger.debug(f"Got series items: {series_items}")
            if not series_items:
                xbmcgui.Dialog().ok('Stalker Player', 'No series found in this category.')
                return
            for item in series_items:
                list_item = xbmcgui.ListItem(label=item['name'])
                list_item.setInfo('video', {'title': item['name'], 'plot': item.get('description'), 'year': item.get('year')})
                item_icon = item.get('screenshot_uri') or item.get('cover') or 'DefaultAddonVideo.png'
                set_list_item_art(list_item, item_icon)
                movie_id = item['id'].split(':')[0]
                url = get_url(mode='list_seasons', movie_id=movie_id)
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing series: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing series: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_seasons(movie_id):
    """ List seasons for a series """
    logger.debug(f"Listing seasons for movie_id: {movie_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            seasons = portal.get_seasons(movie_id)
            logger.debug(f"Got seasons: {seasons}")
            if not seasons:
                xbmcgui.Dialog().ok('Stalker Player', 'No seasons found for this series.')
                return
            for season in seasons:
                list_item = xbmcgui.ListItem(label=season['name'])
                set_list_item_art(list_item, 'DefaultAddonVideo.png')
                url = get_url(mode='list_episodes', movie_id=movie_id, season_id=season['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing seasons: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing seasons: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def list_episodes(movie_id, season_id):
    """ List episodes for a season """
    logger.debug(f"Listing episodes for movie_id: {movie_id}, season_id: {season_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            season_data = portal.get_episodes(movie_id, season_id)
            logger.debug(f"Got season data: {season_data}")
            if not season_data:
                xbmcgui.Dialog().ok('Stalker Player', 'No episodes found for this season.')
                return

            if isinstance(season_data, list) and len(season_data) > 0:
                episodes_list = season_data[0].get('series', [])
                season_cmd = season_data[0].get('cmd')
                if not episodes_list:
                    xbmcgui.Dialog().ok('Stalker Player', 'No episodes found for this season.')
                    return

                for episode_num in episodes_list:
                    episode_name = f"Episode {episode_num}"
                    list_item = xbmcgui.ListItem(label=episode_name)
                    list_item.setProperty('IsPlayable', 'true')
                    set_list_item_art(list_item, 'DefaultAddonVideo.png')
                    url = get_url(mode='play_series', cmd=season_cmd, episode_num=episode_num)
                    xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=False)
            else:
                xbmcgui.Dialog().ok('Stalker Player', 'No episodes found for this season.')

    except Exception as e:
        logger.error(f"Error listing episodes: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing episodes: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def play(cmd, stream_id):
    """ Play a video """
    logger.debug(f"Playing cmd: {cmd}, stream_id: {stream_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            stream_url = portal.get_stream_link(cmd, stream_id)
            logger.debug(f"Got stream url: {stream_url}")
            if stream_url:
                play_item = xbmcgui.ListItem(path=stream_url)
                xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
            else:
                xbmcgui.Dialog().ok('Stalker Player', 'Failed to get stream URL.')
    except Exception as e:
        logger.error(f"Error playing stream: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error playing stream: {e}')

def search():
    """ Search for a query """
    keyboard = xbmc.Keyboard('', 'Search')
    keyboard.doModal()
    if keyboard.isConfirmed():
        query = keyboard.getText()
        if query:
            xbmcplugin.setContent(_HANDLE, 'videos')
            list_item = xbmcgui.ListItem(label=f"Search Movies for: {query}")
            set_list_item_art(list_item, 'DefaultAddonsSearch.png')
            url = get_url(mode='search_movies', query=query)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
            list_item = xbmcgui.ListItem(label=f"Search Series for: {query}")
            set_list_item_art(list_item, 'DefaultAddonsSearch.png')
            url = get_url(mode='search_series', query=query)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
            list_item = xbmcgui.ListItem(label=f"Search Live TV for: {query}")
            set_list_item_art(list_item, 'DefaultAddonsSearch.png')
            url = get_url(mode='search_channels', query=query)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    xbmcplugin.endOfDirectory(_HANDLE)

def search_movies(query):
    """ Search for movies """
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            results = portal.search_vod(query)
            if not results:
                xbmcgui.Dialog().ok('Stalker Player', 'No movies found.')
                return
            for item in results:
                list_item = xbmcgui.ListItem(label=item['name'])
                list_item.setInfo('video', {'title': item['name'], 'plot': item.get('description'), 'year': item.get('year')})
                list_item.setProperty('IsPlayable', 'true')
                item_icon = item.get('screenshot_uri') or item.get('cover') or 'DefaultMovies.png'
                set_list_item_art(list_item, item_icon)
                url = get_url(mode='play_vod', movie_id=item['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=False)
    except Exception as e:
        logger.error(f"Error searching movies: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error searching movies: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def search_series(query):
    """ Search for series """
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            results = portal.search_series(query)
            if not results:
                xbmcgui.Dialog().ok('Stalker Player', 'No series found.')
                return
            for item in results:
                list_item = xbmcgui.ListItem(label=item['name'])
                list_item.setInfo('video', {'title': item['name'], 'plot': item.get('description'), 'year': item.get('year')})
                item_icon = item.get('screenshot_uri') or item.get('cover') or 'DefaultAddonVideo.png'
                set_list_item_art(list_item, item_icon)
                movie_id = item['id'].split(':')[0]
                url = get_url(mode='list_seasons', movie_id=movie_id)
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error searching series: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error searching series: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def search_channels(query):
    """ Search for channels """
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            results = portal.search_itv(query)
            if not results:
                xbmcgui.Dialog().ok('Stalker Player', 'No channels found.')
                return
            for item in results:
                list_item = xbmcgui.ListItem(label=item['name'])
                list_item.setProperty('IsPlayable', 'true')
                channel_icon = item.get('logo') or 'DefaultTVShows.png'
                set_list_item_art(list_item, channel_icon)
                list_item.addContextMenuItems(get_current_profile_favorite_context_menu())
                url = get_url(mode='play', cmd=item['cmd'], stream_id=item['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=False)
    except Exception as e:
        logger.error(f"Error searching channels: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error searching channels: {e}')
    xbmcplugin.endOfDirectory(_HANDLE)

def play_series(cmd, episode_num):
    """ Play a series episode """
    logger.debug(f"Playing episode number: {episode_num} with cmd: {cmd}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            stream_url = portal.get_series_stream_url(cmd, episode_num)
            logger.debug(f"Got series stream url: {stream_url}")
            if stream_url:
                play_item = xbmcgui.ListItem(path=stream_url)
                xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
            else:
                xbmcgui.Dialog().ok('Stalker Player', 'Failed to get series stream URL.')
    except Exception as e:
        logger.error(f"Error playing series stream: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error playing series stream: {e}')

def play_vod(movie_id):
    """ Play a VOD item """
    logger.debug(f"Playing VOD item with movie_id: {movie_id}")
    portal_url = get_setting('stalker_portal_url')
    mac_address = get_setting('stalker_mac_address')
    try:
        with StalkerPortal(portal_url, mac_address) as portal:
            stream_url = portal.get_vod_stream_url(movie_id)
            logger.debug(f"Got VOD stream url: {stream_url}")
            if stream_url:
                play_item = xbmcgui.ListItem(path=stream_url)
                xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
            else:
                xbmcgui.Dialog().ok('Stalker Player', 'Failed to get VOD stream URL.')
    except Exception as e:
        logger.error(f"Error playing VOD stream: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error playing VOD stream: {e}')

def router(params):
    logger.debug(f"[stalker] params: {params}")
    """ Router function that calls other functions
        depending on the provided paramstring """
    mode = params.get('mode')
    logger.debug(f"Routing mode: {mode} with params: {params}")
    if mode is None:
        if not _ADDON.getSetting('stalker_portal_url'):
            profiles = read_profiles() # Read profiles to check if any exist
            if profiles:
                # Activate the first profile by default if no portal URL is set
                switch_profile(profiles[0]['portal_url'], profiles[0]['mac_address'])
            else:
                list_profiles() # If no profiles, still show list_profiles (which will show "No profiles found")
        else:
            list_categories()
    elif mode == 'list_profiles':
        list_profiles()
    elif mode == 'list_favorite_profiles':
        list_favorite_profiles()
    elif mode == 'add_profile':
        add_profile()
    elif mode == 'remove_profile':
        remove_profile()
    elif mode == 'add_profile_to_favorites':
        add_profile_to_favorites(params.get('portal_url'), params.get('mac_address'), params.get('refresh_mode', 'profiles'))
    elif mode == 'remove_profile_from_favorites':
        remove_profile_from_favorites(params.get('portal_url'), params.get('mac_address'), params.get('refresh_mode', 'profiles'))
    elif mode == 'add_favorite_from_group':
        add_favorite_from_group(params.get('group_dns'))
    elif mode == 'switch_profile':
        portal_url = params.get('portal_url')
        mac_address = params.get('mac_address')
        if portal_url and mac_address:
            switch_profile(portal_url, mac_address)
        else:
            logger.error("[stalker] Missing portal_url or mac_address for switch_profile.")
            xbmcgui.Dialog().notification('Error', 'Missing profile details.', xbmcgui.NOTIFICATION_ERROR)
    elif mode == 'select_profile_group':
        select_profile_group(params.get('group_dns'))
    elif mode == 'force_refresh_stalker_profiles': # NEW
        force_refresh_stalker_profiles() # NEW
    elif mode == 'verify_romanian_channels':
        verify_romanian_channels()
    elif mode == 'list_genres':
        list_genres()
    elif mode == 'list_romanian_genres':
        list_romanian_genres()
    elif mode == 'list_channels':
        list_channels(params['genre_id'])
    elif mode == 'list_vod_categories':
        list_vod_categories()
    elif mode == 'list_vod':
        list_vod(params['category_id'])
    elif mode == 'list_series_categories':
        list_series_categories()
    elif mode == 'list_series':
        list_series(params['category_id'])
    elif mode == 'list_seasons':
        list_seasons(params['movie_id'])
    elif mode == 'list_episodes':
        list_episodes(params['movie_id'], params['season_id'])
    elif mode == 'play':
        play(params['cmd'], params['stream_id'])
    elif mode == 'play_vod':
        play_vod(params['movie_id'])
    elif mode == 'play_series':
        play_series(params['cmd'], params['episode_num'])
    elif mode == 'search':
        search()
    elif mode == 'search_movies':
        search_movies(params['query'])
    elif mode == 'search_series':
        search_series(params['query'])
    elif mode == 'search_channels':
        search_channels(params['query'])

if __name__ == '__main__':
    router(dict(parse_qsl(sys.argv[2][1:])))
