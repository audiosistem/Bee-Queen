import logging
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import json
import os
import re
from urllib.parse import urlparse, urlencode, parse_qsl
import requests
import time
import zlib
import base64
import logging
import xml.etree.ElementTree as ET

# Addon specific information
ADDON = xbmcaddon.Addon()
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = 'plugin://plugin.video.hub/'
PROFILE_DIR = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')), 'm3uplayer')
if not xbmcvfs.exists(PROFILE_DIR):
    xbmcvfs.mkdirs(PROFILE_DIR)

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

M3U_PASTEBIN_PROFILES_URL = get_pastebin_url()
M3U_PASTEBIN_CACHE_FILE = os.path.join(PROFILE_DIR, 'm3u_pastebin_profiles_cache.json')
M3U_PASTEBIN_CACHE_DURATION = 3600 # 1 hour in seconds

# --- Helper Functions ---
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

def build_url(query):
    # Ensure 'action' is the first parameter
    action_param = query.pop('action', 'm3uplayer') # Get action, default to 'm3uplayer'
    
    # Encode the rest of the parameters
    query_string = urlencode(query)
    
    # Construct the URL with action first
    if query_string:
        return f"{BASE_URL}?action={action_param}&{query_string}"
    else:
        return f"{BASE_URL}?action={action_param}"


def get_first_pvr_simple_instance_id():
    try:
        query = {
            "jsonrpc": "2.0",
            "method": "Addons.GetAddons",
            "params": {
                "type": "xbmc.pvrclient",
                "properties": ["instanceid"],
                "enabled": True # Only get enabled instances
            },
            "id": 1
        }
        response_str = xbmc.executeJSONRPC(json.dumps(query))
        response_json = json.loads(response_str)
        if "result" in response_json and "addons" in response_json["result"]:
            for addon in response_json["result"]["addons"]:
                if addon.get("addonid") == "pvr.iptvsimple" and addon.get("instanceid"):
                    logging.warning(f"PVR DEBUG: Found active instance ID: {addon['instanceid']}")
                    return addon["instanceid"]
        logging.warning("PVR DEBUG: No active PVR IPTV Simple Client instance found via JSON-RPC.")
        return None
    except Exception as e:
        logging.error(f"PVR DEBUG: Error getting instance ID: {e}")
        return None

def add_dir(name, params, icon='DefaultFolder.png', is_folder=True):
    url = build_url(params)
    li = xbmcgui.ListItem(clean_title(name))
    li.setArt({'icon': icon, 'thumb': icon})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=is_folder)

def end_of_directory():
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def clean_title(title):
    # Remove any characters that are not alphanumeric, underscore, hyphen, or space.
    cleaned_title = re.sub(r'[^\w\-\s]', '', title)
    # Clean up multiple spaces
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

# --- M3U List Management ---
M3U_LISTS_FILE = os.path.join(PROFILE_DIR, 'm3u_lists.json')

def read_m3u_lists():
    if xbmcvfs.exists(M3U_PASTEBIN_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(M3U_PASTEBIN_CACHE_FILE)
            if (time.time() - cache_mod_time) < M3U_PASTEBIN_CACHE_DURATION:
                with xbmcvfs.File(M3U_PASTEBIN_CACHE_FILE, 'rb') as f:
                    encoded_data = f.read()
                    return decode_data(encoded_data)
        except (IOError, ValueError, OSError):
            pass

    try:
        response = requests.get(M3U_PASTEBIN_PROFILES_URL, timeout=10)
        response.raise_for_status()
        content = decode_remote_data(response.text.strip())

        # Try to parse the content as JSON, as it might be wrapped
        try:
            data_json = json.loads(content)
            content = data_json.get("data", "")
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON or not a string, use the content as is
            pass

        profiles = []
        
        # Updated regex to find all "LinieM3U" lines
        pattern = re.compile(r"^LinieM3U\s+(https?://[^\s]+)(?:\s+Denumire:\s*([^\s]+))?(?:\s+Img:\s*(https?://[^\s]+))?", re.MULTILINE)
        
        for match in pattern.finditer(content):
            url, denumire, img = match.groups()
            
            # Set default name if "Denumire" is not found
            name = denumire.strip() if denumire else f"LinieM3U {len(profiles) + 1}"
            
            profiles.append({
                "name": name,
                "url": url.strip(),
                "icon": img.strip() if img else ""
            })
            
        # Cache the fetched profiles
        try:
            with xbmcvfs.File(M3U_PASTEBIN_CACHE_FILE, 'wb') as f:
                encoded_data = encode_data(profiles)
                f.write(encoded_data)
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache M3U profiles: {e}', xbmcgui.NOTIFICATION_ERROR)
            
        return profiles

    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch M3U profiles from pastebin: {e}", xbmcgui.NOTIFICATION_ERROR)
        return []

def write_m3u_lists(m3u_lists):
    # This function is no longer used for writing profiles, as they come from pastebin.
    # It will be kept as a placeholder or removed if not needed elsewhere.
    # For now, it will just return False to prevent any writes.
    xbmcgui.Dialog().notification('Info', 'M3U List writing is disabled.', xbmcgui.NOTIFICATION_INFO)
    return False

def list_m3u_lists_menu():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Manage M3U Lists")
    m3u_lists = read_m3u_lists()

    if not m3u_lists:
        xbmcgui.Dialog().notification('Info', 'No M3U lists found from pastebin.', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    for idx, m3u_list in enumerate(m3u_lists):
        name = m3u_list.get('name', f"List {idx+1}")
        icon = m3u_list.get('icon', '')
        
        url = build_url({'mode': 'select_m3u_list', 'list_index': idx})
        li = xbmcgui.ListItem(clean_title(name))
        li.setArt({'icon': icon, 'thumb': icon})
        
        # Add context menu item
        m3u_url = m3u_list.get('url', '')
        if m3u_url:
            command = f"RunPlugin({build_url({'mode': 'add_to_pvr', 'url': m3u_url})})"
            li.addContextMenuItems([('Add to PVR IPTV Simple Client', command)])
            
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)

    # Removed add/remove list options as per user request
    # add_dir("[+ Add New M3U List]", {'mode': 'add_m3u_list'})
    # if m3u_lists:
    #     add_dir("[- Remove M3U List]", {'mode': 'remove_m3u_list'})

    # Add force refresh link
    add_dir("[Force Refresh M3U Lists]", {'mode': 'force_refresh_m3u_lists'})

    end_of_directory()

def add_m3u_list():
    xbmcgui.Dialog().notification('Info', 'Adding new M3U lists is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def remove_m3u_list():
    xbmcgui.Dialog().notification('Info', 'Removing M3U lists is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def force_refresh_m3u_lists():
    if xbmcvfs.exists(M3U_PASTEBIN_CACHE_FILE):
        try:
            xbmcvfs.delete(M3U_PASTEBIN_CACHE_FILE)
            xbmcgui.Dialog().notification('Success', 'M3U list cache cleared. Refreshing...', xbmcgui.NOTIFICATION_INFO)
        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to clear M3U cache: {e}', xbmcgui.NOTIFICATION_ERROR)
    else:
        xbmcgui.Dialog().notification('Info', 'No M3U list cache found. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    
    # Refresh the current container to re-read profiles from pastebin
    xbmc.executebuiltin("Container.Refresh")

def restart_pvr_addon(addon_id):
    '''
    Restarts a PVR addon by disabling and then re-enabling it.

    Args:
        addon_id (str): The ID of the addon to restart (e.g., "pvr.iptvsimple").
    '''
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
        # Perform hard reset
        restart_pvr_addon('pvr.iptvsimple')
        dialog.notification("PVR IPTV Simple Client", "Playlist updated and PVR restarted.", xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        dialog.notification("PVR IPTV Simple Client", "No PVR IPTV Simple Client instances were configured.", xbmcgui.NOTIFICATION_ERROR, 3000)

# --- M3U Parsing and Display ---
def parse_m3u(m3u_url):
    channels = []
    try:
        if m3u_url.startswith('http://') or m3u_url.startswith('https://'):
            response = requests.get(m3u_url, timeout=10)
            response.raise_for_status()
            content = response.text
        else: # Local file
            with xbmcvfs.File(m3u_url, 'r') as f:
                content = f.read()

        lines = content.splitlines()
        current_channel = {}
        for line in lines:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                # Extract attributes and title
                match = re.search(r'#EXTINF:(-?\d+)\s*(.*?),(.*)', line)
                if match:
                    duration = match.group(1)
                    attributes_str = match.group(2)
                    title = match.group(3)

                    current_channel = {
                        'title': title,
                        'duration': duration,
                        'group_title': 'Other', # Default group
                        'tvg_id': '',
                        'tvg_logo': '',
                        'url': ''
                    }

                    # Parse attributes
                    attrs = re.findall(r'([\w-]+)="([^"]*)"', attributes_str)
                    for key, value in attrs:
                        if key == 'group-title':
                            current_channel['group_title'] = value
                        elif key == 'tvg-id':
                            current_channel['tvg_id'] = value
                        elif key == 'tvg-logo':
                            current_channel['tvg_logo'] = value
            elif line and not line.startswith('#'):
                # This is the URL for the current channel
                if current_channel:
                    current_channel['url'] = line
                    channels.append(current_channel)
                    current_channel = {} # Reset for next channel
    except Exception as e:
        xbmcgui.Dialog().notification('M3U Error', f"Failed to parse M3U: {e}", xbmcgui.NOTIFICATION_ERROR)
    return channels

def select_m3u_list(list_index):
    m3u_lists = read_m3u_lists()
    if 0 <= list_index < len(m3u_lists):
        selected_list = m3u_lists[list_index]
        m3u_url = selected_list['url']
        list_name = selected_list['name']
        
        xbmcplugin.setPluginCategory(ADDON_HANDLE, list_name)
        
        channels = parse_m3u(m3u_url)
        if not channels:
            xbmcgui.Dialog().notification('Info', 'No channels found or failed to parse M3U.', xbmcgui.NOTIFICATION_INFO)
            end_of_directory()
            return

        # Group channels by group-title
        groups = {}
        for channel in channels:
            group = channel.get('group_title', 'Other')
            if group not in groups:
                groups[group] = []
            groups[group].append(channel)

        # Add "All Channels" option
        add_dir("All Channels", {'mode': 'list_channels', 'list_index': list_index, 'group': 'all'})

        # Add "Search" option
        add_dir("Search", {'mode': 'open_search_menu', 'list_index': list_index}, is_folder=False)

        # Add group folders
        for group_name in sorted(groups.keys()):
            add_dir(group_name, {'mode': 'list_channels', 'list_index': list_index, 'group': group_name})
        
        end_of_directory()
    else:
        xbmcgui.Dialog().notification('Error', 'Invalid M3U list selected.', xbmcgui.NOTIFICATION_ERROR)
        end_of_directory()

def list_channels(list_index, group='all'):
    m3u_lists = read_m3u_lists()
    if not (0 <= list_index < len(m3u_lists)):
        xbmcgui.Dialog().notification('Error', 'Invalid M3U list.', xbmcgui.NOTIFICATION_ERROR)
        end_of_directory()
        return

    selected_list = m3u_lists[list_index]
    channels = parse_m3u(selected_list['url'])

    if not channels:
        xbmcgui.Dialog().notification('Info', 'No channels found.', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    display_channels = []
    if group == 'all':
        display_channels = channels
        xbmcplugin.setPluginCategory(ADDON_HANDLE, f"{selected_list['name']} - All Channels")
    else:
        display_channels = [c for c in channels if c.get('group_title') == group]
        xbmcplugin.setPluginCategory(ADDON_HANDLE, f"{selected_list['name']} - {clean_title(group)}")

    for channel in display_channels:
        li = xbmcgui.ListItem(clean_title(channel['title']))
        li.setInfo(type='Video', infoLabels={'title': clean_title(channel['title'])})
        li.setProperty('IsPlayable', 'true')
        if channel['tvg_logo']:
            li.setArt({'icon': channel['tvg_logo'], 'thumb': channel['tvg_logo']})
        
        # Add context menu for channel info (optional)
        # commands = [('Channel Info', f'RunPlugin({build_url({"mode": "channel_info", "title": channel["title"]})})')]
        # li.addContextMenuItems(commands)
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=channel['url'], listitem=li, isFolder=False)

    end_of_directory()

def open_search_menu(list_index):
    keyboard = xbmc.Keyboard('', 'Search for channels')
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        query = keyboard.getText()
        # Trigger the search action
        search_url = build_url({'mode': 'search', 'list_index': list_index, 'query': query})
        xbmc.executebuiltin(f'Container.Update({search_url})')

def search_channels(list_index, query):
    if not query:
        xbmcgui.Dialog().notification('Info', 'Search query was empty.', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    m3u_lists = read_m3u_lists()
    if not (0 <= list_index < len(m3u_lists)):
        xbmcgui.Dialog().notification('Error', 'Invalid M3U list.', xbmcgui.NOTIFICATION_ERROR)
        end_of_directory()
        return

    selected_list = m3u_lists[list_index]
    channels = parse_m3u(selected_list['url'])

    if not channels:
        xbmcgui.Dialog().notification('Info', 'No channels found to search in.', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    # Filter channels based on the query (case-insensitive)
    search_results = [
        c for c in channels 
        if query.lower() in c.get('title', '').lower()
    ]

    xbmcplugin.setPluginCategory(ADDON_HANDLE, f"Search results for: {query}")

    if not search_results:
        xbmcgui.Dialog().notification('Info', f'No channels found matching "{query}"', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    for channel in search_results:
        li = xbmcgui.ListItem(clean_title(channel['title']))
        li.setInfo(type='Video', infoLabels={'title': clean_title(channel['title'])})
        li.setProperty('IsPlayable', 'true')
        if channel['tvg_logo']:
            li.setArt({'icon': channel['tvg_logo'], 'thumb': channel['tvg_logo']})
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=channel['url'], listitem=li, isFolder=False)

    end_of_directory()

def get_params():
    """Get the plugin parameters"""
    paramstring = sys.argv[2][1:]
    return dict(parse_qsl(paramstring))

def router(params):
    """Router function"""
    mode = params.get('mode')

    if mode is None:
        # Removed default activation of the first list.
        # Now, it will always list all M3U lists, and the user can select one.
        list_m3u_lists_menu()
    elif mode == 'select_m3u_list':
        select_m3u_list(int(params['list_index']))
    elif mode == 'add_m3u_list':
        add_m3u_list()
    elif mode == 'remove_m3u_list':
        remove_m3u_list()
    elif mode == 'force_refresh_m3u_lists': # NEW
        force_refresh_m3u_lists() # NEW
    elif mode == 'add_to_pvr':
        add_to_pvr(params['url'])
    elif mode == 'list_channels':
        list_channels(int(params['list_index']), params.get('group', 'all'))
    elif mode == 'open_search_menu':
        open_search_menu(int(params['list_index']))
    elif mode == 'search':
        search_channels(int(params['list_index']), params.get('query'))

if __name__ == '__main__':
    router(get_params())
