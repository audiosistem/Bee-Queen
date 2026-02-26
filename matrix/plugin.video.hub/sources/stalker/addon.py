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

def add_dir(name, params, icon=None):
    url = get_url(**params)
    list_item = xbmcgui.ListItem(label=name)
    if icon:
        list_item.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=True)

def add_item(name, params, icon=None, plot=None):
    url = get_url(**params)
    list_item = xbmcgui.ListItem(label=name)
    info_labels = {'Title': name}
    if plot:
        info_labels['plot'] = plot
    list_item.setInfo(type='Video', infoLabels=info_labels)
    list_item.setProperty('IsPlayable', 'true')
    if icon:
        list_item.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=False)

def clean_title(title):
    # Remove any characters that are not word characters, whitespace, or basic punctuation.
    cleaned_title = re.sub(r'[^\w\s\-.:]', '', title)
    # Clean up whitespace
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def read_profiles():
    logger.debug("[stalker] Calling read_profiles")
    # Try to read from cache first
    if xbmcvfs.exists(STALKER_PASTEBIN_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(STALKER_PASTEBIN_CACHE_FILE)
            if (time.time() - cache_mod_time) < STALKER_PASTEBIN_CACHE_DURATION:
                with xbmcvfs.File(STALKER_PASTEBIN_CACHE_FILE, 'rb') as f:
                    encoded_data = f.read()
                    return decode_data(encoded_data)
        except (IOError, ValueError, OSError):
            logger.debug("[stalker] Cache invalid or corrupted, proceeding to fetch.")
            pass # Cache invalid or corrupted, proceed to fetch

    # Fetch from pastebin
    try:
        # Use a requests session if available, otherwise direct call
        try:
            session = requests.Session()
            response = session.get(STALKER_PASTEBIN_PROFILES_URL, timeout=10)
        except NameError: # requests.Session might not be defined if not imported globally
            response = requests.get(STALKER_PASTEBIN_PROFILES_URL, timeout=10)

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
        
        # Use regex to find all Stalker IPTV entries
        # Pattern: Portal URL followed by " MAC : " and then the MAC address
        stalker_pattern = r"(https?://[^\s]+?)\s+MAC\s+:\s+([0-9A-Fa-f:]{17})"
        
        for match in re.finditer(stalker_pattern, content):
            portal_url_part = match.group(1) # Captured portal URL
            mac_address = match.group(2) # Captured MAC address

            parsed_url = urlparse(portal_url_part)
            portal_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            profile_name = parsed_url.netloc # Use domain:port as profile name

            profiles.append({
                "name": profile_name,
                "portal_url": portal_url,
                "mac_address": mac_address
            })
        
        # Cache the fetched profiles
        try:
            with xbmcvfs.File(STALKER_PASTEBIN_CACHE_FILE, 'wb') as f:
                encoded_data = encode_data(profiles)
                f.write(encoded_data)
            logger.debug("[stalker] Stalker profiles cached successfully.")
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache Stalker profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch Stalker profiles from pastebin: {e}", xbmcgui.NOTIFICATION_ERROR)
        logger.error(f"[stalker] Failed to fetch Stalker profiles: {e}", exc_info=True)
        return []

def write_profiles(profiles):
    logger.debug(f"[stalker] Calling write_profiles with profiles: {profiles}")
    # This function is no longer used for writing profiles, as they come from pastebin.
    # It will be kept as a placeholder or removed if not needed elsewhere.
    # For now, it will just return False to prevent any writes.
    xbmcgui.Dialog().notification('Info', 'Stalker Profile writing is disabled.', xbmcgui.NOTIFICATION_INFO)
    return False

def list_profiles():
    logger.debug("[stalker] Calling list_profiles")
    xbmcplugin.setPluginCategory(_HANDLE, "Profiles")
    profiles = read_profiles()
    active_profile_portal = _ADDON.getSetting('stalker_portal_url')
    active_profile_mac = _ADDON.getSetting('stalker_mac_address') # Get active MAC

    if not profiles:
        xbmcgui.Dialog().notification('Info', 'No Stalker profiles found from pastebin.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    for profile in profiles:
        name = profile.get('name')
        display_name = name
        # Check both portal_url and mac_address
        if (profile.get('portal_url') == active_profile_portal and
            profile.get('mac_address') == active_profile_mac):
            display_name += " (Active)"
        add_dir(display_name, {'mode': 'switch_profile', 'portal_url': profile['portal_url'], 'mac_address': profile['mac_address']})

    # Removed add/remove profile options as per user request
    # add_dir("[+ Add New Profile]", {'mode': 'add_profile'})
    # if profiles:
    #     add_dir("[- Remove a Profile]", {'mode': 'remove_profile'})

    # Add force refresh link
    add_dir("[Force Refresh Stalker Profiles]", {'mode': 'force_refresh_stalker_profiles'})

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
    if xbmcvfs.exists(STALKER_PASTEBIN_CACHE_FILE):
        try:
            xbmcvfs.delete(STALKER_PASTEBIN_CACHE_FILE)
            xbmcgui.Dialog().notification('Success', 'Stalker profile cache cleared. Refreshing...', xbmcgui.NOTIFICATION_INFO)
        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to clear Stalker cache: {e}', xbmcgui.NOTIFICATION_ERROR)
            logger.error(f"[stalker] Error clearing cache: {e}", exc_info=True)
    else:
        xbmcgui.Dialog().notification('Info', 'No Stalker profile cache found. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker)')

def switch_profile(portal_url, mac_address):
    logger.debug(f"[stalker] Calling switch_profile with portal_url: {portal_url}, mac_address: {mac_address}")
    profiles = read_profiles()
    profile_to_activate = next((p for p in profiles if p.get('portal_url') == portal_url and p.get('mac_address') == mac_address), None)

    if profile_to_activate:
        _ADDON.setSetting('stalker_portal_url', profile_to_activate['portal_url'])
        _ADDON.setSetting('stalker_mac_address', profile_to_activate['mac_address'])
        xbmcgui.Dialog().notification('Profile Switched', f"Activated profile: {profile_to_activate['name']}", xbmcgui.NOTIFICATION_INFO)
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=stalker)') # Refresh the menu to show the main menu
    else:
        xbmcgui.Dialog().notification('Error', 'Could not find profile to activate.', xbmcgui.NOTIFICATION_ERROR)

def list_categories():
    logger.debug("[stalker] Calling list_categories")
    """ List the main categories """
    logger.debug("Listing categories")
    xbmcplugin.setContent(_HANDLE, 'videos')
    add_dir('Manage Profiles', {'mode': 'list_profiles'})
    add_dir('Search', {'mode': 'search'})
    categories = [
        {'name': 'Live TV', 'mode': 'list_genres'},
        {'name': 'Movies', 'mode': 'list_vod_categories'},
        {'name': 'Series', 'mode': 'list_series_categories'}
    ]
    for category in categories:
        list_item = xbmcgui.ListItem(label=category['name'])
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
                url = get_url(mode='list_channels', genre_id=genre['id'])
                xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
    except Exception as e:
        logger.error(f"Error listing genres: {e}", exc_info=True)
        xbmcgui.Dialog().ok('Stalker Player', f'Error listing genres: {e}')
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
            url = get_url(mode='search_movies', query=query)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
            list_item = xbmcgui.ListItem(label=f"Search Series for: {query}")
            url = get_url(mode='search_series', query=query)
            xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, isFolder=True)
            list_item = xbmcgui.ListItem(label=f"Search Live TV for: {query}")
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
    elif mode == 'add_profile':
        add_profile()
    elif mode == 'remove_profile':
        remove_profile()
    elif mode == 'switch_profile':
        portal_url = params.get('portal_url')
        mac_address = params.get('mac_address')
        if portal_url and mac_address:
            switch_profile(portal_url, mac_address)
        else:
            logger.error("[stalker] Missing portal_url or mac_address for switch_profile.")
            xbmcgui.Dialog().notification('Error', 'Missing profile details.', xbmcgui.NOTIFICATION_ERROR)
    elif mode == 'force_refresh_stalker_profiles': # NEW
        force_refresh_stalker_profiles() # NEW
    elif mode == 'list_genres':
        list_genres()
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