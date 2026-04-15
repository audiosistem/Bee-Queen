import sys
import time
import xbmcgui
import xbmcplugin
import re
import xbmcaddon
import os
import xbmc, xbmcvfs
import urllib.request
import urllib.error
import json
from urllib.parse import parse_qsl, urlencode
import requests
import zlib
import base64

# Addon specific information
ADDON = xbmcaddon.Addon('plugin.video.hub')
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = 'plugin://plugin.video.hub/'
PROFILE_DIR = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')), 'edemplayer')
if not xbmcvfs.exists(PROFILE_DIR):
    xbmcvfs.mkdirs(PROFILE_DIR)
SCRIPT_DIR = os.path.dirname(__file__)

MENU_ICONS = {
    'list_profiles': 'DefaultNetwork.png',
    'search': 'DefaultAddonsSearch.png',
    'switch_profile': 'DefaultNetwork.png',
    'force_refresh_edem_profiles': 'DefaultAddonUpdates.png',
    'show_channels': 'DefaultTVShows.png',
}

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

EDEM_PASTEBIN_PROFILES_URL = get_pastebin_url()
EDEM_PASTEBIN_CACHE_FILE = os.path.join(PROFILE_DIR, 'edem_pastebin_profiles_cache.json')
EDEM_PASTEBIN_CACHE_DURATION = 3600 # 1 hour in seconds

def encode_data(data):
    json_data = json.dumps(data, indent=4)
    compressed_data = zlib.compress(json_data.encode('utf-8'))
    encoded_data = base64.b64encode(compressed_data)
    return encoded_data[::-1]

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

def decode_data(encoded_data):
    reversed_data = encoded_data[::-1]
    decoded_data = base64.b64decode(reversed_data)
    decompressed_data = zlib.decompress(decoded_data)
    return json.loads(decompressed_data.decode('utf-8'))

# --- Profile/Account Management ---
PROFILES_FILE = os.path.join(PROFILE_DIR, 'edem_profiles.json')

def read_profiles():
    # Try to read from cache first
    if xbmcvfs.exists(EDEM_PASTEBIN_CACHE_FILE):
        try:
            cache_mod_time = os.path.getmtime(EDEM_PASTEBIN_CACHE_FILE)
            if (time.time() - cache_mod_time) < EDEM_PASTEBIN_CACHE_DURATION:
                with xbmcvfs.File(EDEM_PASTEBIN_CACHE_FILE, 'rb') as f:
                    encoded_data = f.read()
                    return decode_data(encoded_data)
        except (IOError, ValueError, OSError, zlib.error):
            pass # Cache invalid or corrupted, proceed to fetch

    # Fetch from pastebin
    try:
        # Use a requests session if available, otherwise direct call
        try:
            session = requests.Session()
            response = session.get(EDEM_PASTEBIN_PROFILES_URL, timeout=10)
        except NameError: # requests.Session might not be defined if not imported globally
            response = requests.get(EDEM_PASTEBIN_PROFILES_URL, timeout=10)

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
        edem_count = 1
        
        # Use regex to find all Edem entries
        # Pattern: "EDEM " followed by the unique string
        edem_pattern = r"EDEM\s+([0-9A-Za-z]+)"
        
        for match in re.finditer(edem_pattern, content):
            unique_string = match.group(1) # Captured unique string
            
            profile_name = f"EDEM {edem_count}"
            edem_count += 1

            profiles.append({
                "name": profile_name,
                "unique_string": unique_string
            })
        
        # Cache the fetched profiles
        try:
            with xbmcvfs.File(EDEM_PASTEBIN_CACHE_FILE, 'wb') as f:
                encoded_data = encode_data(profiles)
                f.write(encoded_data)
        except (IOError, ValueError) as e:
            xbmcgui.Dialog().notification('Error', f'Failed to cache Edem profiles: {e}', xbmcgui.NOTIFICATION_ERROR)

        return profiles
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification('Error', f"Failed to fetch Edem profiles from pastebin: {e}", xbmcgui.NOTIFICATION_ERROR)
        return []


def write_profiles(profiles):
    # This function is no longer used for writing profiles, as they come from pastebin.
    # It will be kept as a placeholder or removed if not needed elsewhere.
    # For now, it will just return False to prevent any writes.
    xbmcgui.Dialog().notification('Info', 'Edem Profile writing is disabled.', xbmcgui.NOTIFICATION_INFO)
    return False

def list_profiles():
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Profiles")
    
    # Add force refresh and verify links at the top
    add_dir("[Verify All Profiles]", {'mode': 'verify_all_profiles'}, icon='DefaultAddonUpdates.png')
    add_dir("[Force Refresh Edem Profiles]", {'mode': 'force_refresh_edem_profiles'}, icon='DefaultAddonUpdates.png')

    profiles = read_profiles()
    active_profile_unique_string = ADDON.getSetting('edem_active_profile_unique_string')

    if not profiles:
        xbmcgui.Dialog().notification('Info', 'No Edem profiles found from pastebin.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    # Load validation cache if available
    validation_cache = {}
    valid_cache_path = os.path.join(PROFILE_DIR, 'edem_valid_cache.json')
    if xbmcvfs.exists(valid_cache_path):
        try:
            with xbmcvfs.File(valid_cache_path, 'r') as f:
                validation_cache = json.loads(f.read())
        except Exception:
            pass

    for profile in profiles:
        name = profile.get('name')
        unique_string = profile.get('unique_string')
        display_name = name
        
        # Append validation status from cache
        if unique_string in validation_cache:
            status = validation_cache[unique_string]
            if status == "VALID" or status is True:
                display_name += " [COLOR green][Valid][/COLOR]"
            elif status == "OCCUPIED":
                display_name += " [COLOR orange][Occupied][/COLOR]"
            elif status == "INVALID" or status is False:
                display_name += " [COLOR red][Invalid][/COLOR]"
                
        if unique_string == active_profile_unique_string:
            display_name += " (Active)"
            
        add_dir(display_name, {'mode': 'switch_profile', 'name': name}, icon='DefaultNetwork.png')

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def add_profile():
    xbmcgui.Dialog().notification('Info', 'Adding new Edem profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def remove_profile():
    xbmcgui.Dialog().notification('Info', 'Removing Edem profiles is disabled.', xbmcgui.NOTIFICATION_INFO)
    return

def force_refresh_edem_profiles():
    if xbmcvfs.exists(EDEM_PASTEBIN_CACHE_FILE):
        try:
            xbmcvfs.delete(EDEM_PASTEBIN_CACHE_FILE)
            xbmcgui.Dialog().notification('Success', 'Edem profile cache cleared. Refreshing...', xbmcgui.NOTIFICATION_INFO)
        except Exception as e:
            xbmcgui.Dialog().notification('Error', f'Failed to clear Edem cache: {e}', xbmcgui.NOTIFICATION_ERROR)
    else:
        xbmcgui.Dialog().notification('Info', 'No Edem profile cache found. Refreshing...', xbmcgui.NOTIFICATION_INFO)
    
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=edemplayer)')

def switch_profile(name):
    profiles = read_profiles()
    profile_to_activate = next((p for p in profiles if p.get('name') == name), None)

    if profile_to_activate:
        ADDON.setSetting('edem_active_profile_name', profile_to_activate['name'])
        ADDON.setSetting('edem_active_profile_unique_string', profile_to_activate['unique_string'])
        xbmcgui.Dialog().notification('Profile Switched', f"Activated profile: {name}", xbmcgui.NOTIFICATION_INFO)
        xbmc.executebuiltin('Container.Update(plugin://plugin.video.hub/?action=edemplayer)')
    else:
        xbmcgui.Dialog().notification('Error', 'Could not find profile to activate.', xbmcgui.NOTIFICATION_ERROR)

# --- Domain Checker Functions ---
def check_domain_availability(base_domain):
    active_unique_string = ADDON.getSetting('edem_active_profile_unique_string')
    
    # If no active profile, try to find a fallback unique string from the local m3u8 file
    if not active_unique_string:
        m3u8_file_path = os.path.join(SCRIPT_DIR, 'edem_en.m3u8')
        try:
            with open(m3u8_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'/iptv/([A-Z0-9]+)/', content)
                if match:
                    active_unique_string = match.group(1)
        except Exception:
            pass
            
    if not active_unique_string:
        # Last resort fallback (usually Edem IDs are 14 chars)
        active_unique_string = "B5MWVF2B66GG8B" 

    test_path = f"/iptv/{active_unique_string}/2523/index.m3u8"
    test_url = f"http://{base_domain}{test_path}"
    try:
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            content = response.text
            # For domain checking, we only care if it's an Edem server that responds 
            # with a playlist. Even if it returns /404/ (invalid ID), the server itself is working.
            return "#EXTM3U" in content
        return False
    except Exception:
        return False

def find_working_domain():
    SESSION_TIMEOUT = 300

    last_check_timestamp = float(ADDON.getSetting('edem_last_check_timestamp'))
    last_working_server = ADDON.getSetting('edem_last_working_server')

    if last_working_server and (time.time() - last_check_timestamp) < SESSION_TIMEOUT:
        if check_domain_availability(last_working_server):
            return last_working_server

    dialog = xbmcgui.Dialog()
    dialog.notification("Edem Player", "Checking for a working domain...", xbmcgui.NOTIFICATION_INFO, 5000)

    m3u8_file_path = os.path.join(SCRIPT_DIR, 'edem_en.m3u8')
    domains_file_path = os.path.join(SCRIPT_DIR, 'domenii.txt')

    current_domain = None
    try:
        with open(m3u8_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('http'):
                    match = re.match(r'http[s]?://([^/]+)', line.strip())
                    if match:
                        current_domain = match.group(1)
                        break
    except Exception:
        pass

    if current_domain and check_domain_availability(current_domain):
        dialog.notification("Edem Player", f"Found working domain: {current_domain}", xbmcgui.NOTIFICATION_INFO, 5000)
        ADDON.setSetting('edem_last_working_server', current_domain)
        ADDON.setSetting('edem_last_check_timestamp', str(time.time()))
        return current_domain

    alternative_domains = []
    try:
        with open(domains_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                domain = line.strip()
                if domain and not domain.startswith('#'):
                    alternative_domains.append(domain)
    except (FileNotFoundError, Exception):
        pass

    for alt_domain in alternative_domains:
        domain_to_check = re.sub(r'http[s]?://', '', alt_domain).strip()
        if check_domain_availability(domain_to_check):
            dialog.notification("Edem Player", f"Found working domain: {domain_to_check}", xbmcgui.NOTIFICATION_INFO, 5000)
            ADDON.setSetting('edem_last_working_server', domain_to_check)
            ADDON.setSetting('edem_last_check_timestamp', str(time.time()))
            if current_domain:
                update_m3u8_domain(m3u8_file_path, current_domain, domain_to_check)
            return domain_to_check
    
    dialog.notification("Edem Player", "No working domain found.", xbmcgui.NOTIFICATION_ERROR, 5000)
    return None

def update_m3u8_domain(m3u8_file_path, old_domain, new_domain):
    try:
        with open(m3u8_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        updated_content = content.replace(f'://{old_domain}', f'://{new_domain}')
        
        with open(m3u8_file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
    except Exception:
        pass

def verify_id(unique_string):
    """Checks if an Edem ID is valid across known domains."""
    domains_file_path = os.path.join(SCRIPT_DIR, 'domenii.txt')
    domains = []
    
    # Try to find the current domain from the m3u8 file
    m3u8_file_path = os.path.join(SCRIPT_DIR, 'edem_en.m3u8')
    try:
        with open(m3u8_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('http'):
                    match = re.match(r'http[s]?://([^/]+)', line.strip())
                    if match:
                        domains.append(match.group(1))
                        break
    except Exception:
        pass
        
    # Add domains from domenii.txt
    try:
        with open(domains_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                domain = line.strip()
                if domain and not domain.startswith('#'):
                    domains.append(re.sub(r'http[s]?://', '', domain).strip())
    except Exception:
        pass

    # Deduplicate domains
    unique_domains = []
    for d in domains:
        if d not in unique_domains:
            unique_domains.append(d)
    
    # Limit to top 5 domains for speed
    for domain in unique_domains[:5]:
        test_path = f"/iptv/{unique_string}/2523/index.m3u8"
        test_url = f"http://{domain}{test_path}"
        try:
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                content = response.text
                if "#EXTM3U" in content:
                    if "/404/" in content:
                        return "INVALID", domain
                    elif "/405/" in content:
                        return "OCCUPIED", domain
                    else:
                        return "VALID", domain
        except Exception:
            continue
    return "INVALID", None

def verify_all_profiles():
    """Verifies all profiles from the pastebin and shows results."""
    profiles = read_profiles()
    if not profiles:
        xbmcgui.Dialog().notification('Info', 'No Edem profiles to verify.', xbmcgui.NOTIFICATION_INFO)
        return
    
    progress = xbmcgui.DialogProgress()
    progress.create('Edem Verifier', 'Verifying Edem IDs...')
    
    results = []
    valid_count = 0
    occupied_count = 0
    invalid_count = 0
    validation_cache = {}
    
    for i, profile in enumerate(profiles):
        if progress.iscanceled():
            break
        
        name = profile.get('name')
        unique_string = profile.get('unique_string')
        
        progress.update(int((i / len(profiles)) * 100), f"Checking {name}... (ID: {unique_string})")
        
        status_code, domain = verify_id(unique_string)
        validation_cache[unique_string] = status_code
        
        if status_code == "VALID":
            status = "[COLOR green]Valid[/COLOR]"
            valid_count += 1
        elif status_code == "OCCUPIED":
            status = "[COLOR orange]Occupied[/COLOR]"
            occupied_count += 1
        else:
            status = "[COLOR red]Invalid[/COLOR]"
            invalid_count += 1
            
        results.append(f"{name}: {status} ({unique_string})")
        
    progress.close()
    
    # Save cache
    valid_cache_path = os.path.join(PROFILE_DIR, 'edem_valid_cache.json')
    try:
        with xbmcvfs.File(valid_cache_path, 'w') as f:
            f.write(json.dumps(validation_cache))
    except Exception:
        pass
    
    result_text = f"Total Profiles: {len(profiles)}\nValid: {valid_count} | Occupied: {occupied_count} | Invalid: {invalid_count}\n\n" + "\n".join(results)
    xbmcgui.Dialog().textviewer('Edem Verification Results', result_text)
    
    # Refresh the directory to show the newly added valid/invalid markers
    xbmc.executebuiltin('Container.Refresh()')

# --- Plugin Functions ---
def get_params():
    param_string = sys.argv[2][1:]
    return dict(parse_qsl(param_string))

def get_groups(m3u8_file):
    with open(m3u8_file, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = re.findall(r'group-title="(.*?)"', content)
    return sorted(list(set(matches)))

def get_channels(m3u8_file, group, server):
    unique_string = ADDON.getSetting('edem_active_profile_unique_string')

    with open(m3u8_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    channels = []
    for i in range(len(lines)):
        if lines[i].startswith('#EXTINF') and f'group-title="{group}"' in lines[i]:
            channel_info = lines[i].strip()
            channel_url = lines[i+1].strip()
            
            name_match = re.search(r',(.+)$', channel_info)
            logo_match = re.search(r'tvg-logo="(.*?)"', channel_info)
            
            channel_name = name_match.group(1) if name_match else 'Unknown'
            channel_logo = logo_match.group(1) if logo_match else ''
            
            modified_url = re.sub(r'(http[s]?://)([^/]+)(/iptv/)([^/]+)(/.*)',
                                  lambda m: m.group(1) + server + m.group(3) + unique_string + m.group(5),
                                  channel_url)

            channels.append({
                'name': channel_name,
                'url': modified_url,
                'logo': channel_logo
            })
            
    return channels

def search_channels(m3u8_file, query, server):
    unique_string = ADDON.getSetting('edem_active_profile_unique_string')

    with open(m3u8_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    results = []
    query_lower = query.lower()
    
    for i in range(len(lines)):
        if lines[i].startswith('#EXTINF'):
            channel_info = lines[i].strip()
            channel_url = lines[i+1].strip()
            
            name_match = re.search(r',(.+)$', channel_info)
            logo_match = re.search(r'tvg-logo="(.*?)"', channel_info)
            
            channel_name = name_match.group(1) if name_match else 'Unknown'
            channel_logo = logo_match.group(1) if logo_match else ''
            
            if query_lower in channel_name.lower():
                modified_url = re.sub(r'(http[s]?://)([^/]+)(/iptv/)([^/]+)(/.*)',
                                      lambda m: m.group(1) + server + m.group(3) + unique_string + m.group(5),
                                      channel_url)
                results.append({
                    'name': channel_name,
                    'url': modified_url,
                    'logo': channel_logo
                })
                
    return results

def add_dir(name, params, icon=None):
    # Ensure 'action' is the first parameter
    action_param = params.pop('action', 'edemplayer') # Get action, default to 'edemplayer'
    
    # Encode the rest of the parameters
    query_string = urlencode(params)
    
    # Construct the URL with action first
    if query_string:
        url = f"{BASE_URL}?action={action_param}&{query_string}"
    else:
        url = f"{BASE_URL}?action={action_param}"

    li = xbmcgui.ListItem(name)
    icon = icon or MENU_ICONS.get(params.get('mode'), 'DefaultFolder.png')
    if icon:
        li.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)

def main_menu(server):
    xbmcplugin.setPluginCategory(ADDON_HANDLE, "Main Menu")
    add_dir('Manage Profiles', {'mode': 'list_profiles'}, icon='DefaultNetwork.png')
    add_dir('Search Channels', {'mode': 'search'}, icon='DefaultAddonsSearch.png')

    m3u8_file = os.path.join(SCRIPT_DIR, 'edem_en.m3u8')
    groups = get_groups(m3u8_file)
    
    reordered_groups = []
    if "Romania" in groups:
        reordered_groups.append("Romania")
        groups.remove("Romania")
    if "Moldova" in groups:
        reordered_groups.append("Moldova")
        groups.remove("Moldova")
    
    reordered_groups.extend(sorted(groups))
    
    for group in reordered_groups:
        add_dir(group, {'mode': 'show_channels', 'group': group}, icon='DefaultTVShows.png')
        
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def router(params):
    mode = params.get('mode')

    server = find_working_domain()

    if mode is None:
        if not ADDON.getSetting('edem_active_profile_unique_string'):
            profiles = read_profiles() # Read profiles to check if any exist
            if profiles:
                # Activate the first profile by default if no unique string is set
                switch_profile(profiles[0]['name'])
            else:
                list_profiles() # If no profiles, still show list_profiles (which will show "No profiles found")
        else:
            if server:
                main_menu(server)
            else:
                xbmcgui.Dialog().ok("Error", "No working server found. Please check your internet connection and domenii.txt file.")
                list_profiles()

    elif mode == 'list_profiles':
        list_profiles()
    elif mode == 'add_profile':
        add_profile()
    elif mode == 'remove_profile':
        remove_profile()
    elif mode == 'switch_profile':
        switch_profile(params['name'])
    elif mode == 'verify_all_profiles':
        verify_all_profiles()
    elif mode == 'force_refresh_edem_profiles': # NEW
        force_refresh_edem_profiles() # NEW
    elif mode == 'search':
        if not server:
            xbmcgui.Dialog().ok("Error", "No working server found.")
            return

        keyboard = xbmc.Keyboard('', 'Search for channels')
        keyboard.doModal()
        if keyboard.isConfirmed():
            query = keyboard.getText()
            if query:
                m3u8_file = os.path.join(SCRIPT_DIR, 'edem_en.m3u8')
                results = search_channels(m3u8_file, query, server)
                if results:
                    for channel in results:
                        li = xbmcgui.ListItem(label=channel['name'])
                        icon = channel['logo'] or 'DefaultTVShows.png'
                        li.setArt({'thumb': icon, 'icon': icon})
                        li.setProperty('IsPlayable', 'true')
                        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=channel['url'], listitem=li, isFolder=False)
                else:
                    xbmcgui.Dialog().ok("Search Results", "No channels found matching your query.")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
    elif mode == 'show_channels':
        if not server:
            xbmcgui.Dialog().ok("Error", "No working server found.")
            return

        group = params.get('group')
        m3u8_file = os.path.join(SCRIPT_DIR, 'edem_en.m3u8')
        channels = get_channels(m3u8_file, group, server)
        
        for channel in channels:
            li = xbmcgui.ListItem(label=channel['name'])
            icon = channel['logo'] or 'DefaultTVShows.png'
            li.setArt({'thumb': icon, 'icon': icon})
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=channel['url'], listitem=li, isFolder=False)
            
        xbmcplugin.endOfDirectory(ADDON_HANDLE)

if __name__ == '__main__':
    router(dict(parse_qsl(sys.argv[2][1:])))
