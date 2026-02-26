import sys
import xbmcgui
import xbmcplugin
import requests
import re
from urllib.parse import urlencode

# Addon specific information
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = 'plugin://plugin.video.hub/'

def build_url(query):
    action_param = query.pop('action', 'alteliste')
    query_string = urlencode(query)
    if query_string:
        return f"{BASE_URL}?action={action_param}&{query_string}"
    else:
        return f"{BASE_URL}?action={action_param}"

def add_dir(name, params, icon='DefaultFolder.png', is_folder=True):
    url = build_url(params)
    li = xbmcgui.ListItem(name)
    li.setArt({'icon': icon, 'thumb': icon})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=is_folder)

def add_item(name, params, thumb, fanart, is_folder=False, is_playable=True):
    url = build_url(params)
    li = xbmcgui.ListItem(name)
    li.setArt({'thumb': thumb, 'fanart': fanart})
    li.setProperty('IsPlayable', 'true' if is_playable else 'false')
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=is_folder)

def end_of_directory():
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def get_token():
    try:
        url = "https://token.stb.md/api/Flussonic/stream/NICKELODEON_H264/metadata.json"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"})
        response.raise_for_status()
        data = response.json()
        return data.get('token')
    except (requests.RequestException, ValueError) as e:
        xbmcgui.Dialog().notification('Error', f'Failed to get token: {e}', xbmcgui.NOTIFICATION_ERROR)
        return None

def get_playlist():
    try:
        url = "https://pastebin.com/raw/JGTsG7B1"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"})
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        xbmcgui.Dialog().notification('Error', f'Failed to get playlist: {e}', xbmcgui.NOTIFICATION_ERROR)
        return None

def parse_playlist(playlist_content, token):
    channels = []
    
    # Regex to capture channel info and URL
    pattern = re.compile(r'#EXTINF:-1.*?logo="([^"]*)".*?group-title="([^"]*)".*?,(.*?)\r?\n(http.*?token=)', re.DOTALL)
    
    for match in pattern.finditer(playlist_content):
        logo, group, title, url = match.groups()
        
        channels.append({
            'title': title.strip(),
            'logo': logo.strip(),
            'group': group.strip(),
            'url': url.strip() + token
        })
        
    return channels

def list_channels(params):
    """Lists channels, grouped by category"""
    token = get_token()
    if not token:
        end_of_directory()
        return

    playlist_content = get_playlist()
    if not playlist_content:
        end_of_directory()
        return

    channels = parse_playlist(playlist_content, token)
    if not channels:
        xbmcgui.Dialog().notification('Info', 'No channels found in the playlist.', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    group = params.get('group')

    if group is None:
        # List all groups
        groups = sorted(list(set(c['group'] for c in channels)))
        add_dir("All Channels", {'mode': 'ro-md', 'group': 'all'})
        for g in groups:
            add_dir(g, {'mode': 'ro-md', 'group': g})
    else:
        # List channels in the selected group
        if group == 'all':
            display_channels = channels
        else:
            display_channels = [c for c in channels if c['group'] == group]

        for channel in display_channels:
            add_item(
                channel['title'],
                {'mode': 'play', 'url': channel['url']},
                thumb=channel['logo'],
                fanart=channel['logo']
            )
            
    end_of_directory()

def play_channel(params):
    """Plays the selected channel"""
    url = params.get('url')
    if url:
        li = xbmcgui.ListItem(path=url)
        xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, li)