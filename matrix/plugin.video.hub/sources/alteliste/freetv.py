import sys
import re
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode
import requests

_BASE_URL = 'plugin://plugin.video.hub/'
_HANDLE = int(sys.argv[1])

M3U_URL = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"

def clean_title(title):
    # Remove any characters that are not alphanumeric, underscore, hyphen, or space.
    cleaned_title = re.sub(r'[^\w\-\s]', '', title)
    # Clean up multiple spaces
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def add_dir(name, params, icon=None):
    """Add a directory item."""
    url = f'{_BASE_URL}?{urlencode(params)}'
    list_item = xbmcgui.ListItem(label=clean_title(name))
    if icon:
        list_item.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=True)

def add_item(name, params, thumb=None, fanart=None, plot=None):
    """Add a playable item to the directory."""
    url = f'{_BASE_URL}?{urlencode(params)}'
    list_item = xbmcgui.ListItem(label=clean_title(name))
    info_labels = {'Title': clean_title(name)}
    if plot:
        info_labels['plot'] = plot
    list_item.setInfo(type='Video', infoLabels=info_labels)
    list_item.setProperty('IsPlayable', 'true')
    if thumb:
        list_item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': fanart})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=False)

def end_of_directory():
    """End of directory listing."""
    xbmcplugin.endOfDirectory(_HANDLE)

def get_playlist(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        xbmcgui.Dialog().notification('Error', f'Failed to get playlist: {e}', xbmcgui.NOTIFICATION_ERROR)
        return None

def parse_playlist(playlist_content):
    channels = []
    pattern = re.compile(r'#EXTINF:-1\s*(.*?),(.*?)\n(http.*)')
    
    for match in pattern.finditer(playlist_content):
        attributes_str, title, url = match.groups()
        
        tvg_id_match = re.search(r'tvg-id="([^"]*)"', attributes_str)
        logo_match = re.search(r'tvg-logo="([^"]*)"', attributes_str)
        group_match = re.search(r'group-title="([^"]*)"', attributes_str)

        channels.append({
            'title': title.strip(),
            'logo': logo_match.group(1).strip() if logo_match else '',
            'group': group_match.group(1).strip() if group_match else '',
            'url': url.strip(),
            'tvg_id': tvg_id_match.group(1).strip() if tvg_id_match else ''
        })
        
    return channels

def list_groups(params):
    playlist_content = get_playlist(M3U_URL)
    if not playlist_content:
        end_of_directory()
        return

    channels = parse_playlist(playlist_content)
    if not channels:
        xbmcgui.Dialog().notification('Info', 'No channels found in the playlist.', xbmcgui.NOTIFICATION_INFO)
        end_of_directory()
        return

    groups = sorted(list(set(c['group'] for c in channels)))
    
    for group in groups:
        add_dir(group, {'action': 'alteliste', 'mode': 'freetv_list_channels', 'group': group})
        
    end_of_directory()

def list_channels(params):
    group = params.get('group')
    
    if not group:
        end_of_directory()
        return

    playlist_content = get_playlist(M3U_URL)
    if not playlist_content:
        end_of_directory()
        return

    channels = parse_playlist(playlist_content)
    if not channels:
        end_of_directory()
        return
        
    display_channels = [c for c in channels if c['group'] == group]

    for channel in display_channels:
        add_item(
            channel['title'],
            {'action': 'alteliste', 'mode': 'freetv_play', 'url': channel['url']},
            thumb=channel['logo'],
            fanart=channel['logo']
        )
            
    end_of_directory()

def play_channel(params):
    url = params.get('url')
    if url:
        li = xbmcgui.ListItem(path=url)
        xbmcplugin.setResolvedUrl(_HANDLE, True, li)

def router(params):
    mode = params.get('mode')

    if mode == 'freetv_list_channels':
        list_channels(params)
    elif mode == 'freetv_play':
        play_channel(params)
    else:
        list_groups(params)