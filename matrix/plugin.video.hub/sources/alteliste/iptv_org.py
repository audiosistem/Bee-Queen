import sys
import requests
import re
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

_BASE_URL = 'plugin://plugin.video.hub/'
_HANDLE = int(sys.argv[1])

def add_dir(name, params, icon=None):
    """Add a directory item."""
    url = f'{_BASE_URL}?{urlencode(params)}'
    list_item = xbmcgui.ListItem(label=name)
    if icon:
        list_item.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=True)

def add_item(name, params, thumb=None, fanart=None, plot=None):
    """Add a playable item to the directory."""
    url = f'{_BASE_URL}?{urlencode(params)}'
    list_item = xbmcgui.ListItem(label=name)
    info_labels = {'Title': name}
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

M3U_URL = "https://iptv-org.github.io/iptv/index.category.m3u"

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
    # Regex to capture channel info and URL
    pattern = re.compile(r'#EXTINF:-1.*?tvg-id="([^"]*)".*?tvg-logo="([^"]*)".*?group-title="([^"]*)".*?,(.*?)\n(http.*)')
    
    for match in pattern.finditer(playlist_content):
        tvg_id, logo, group, title, url = match.groups()
        
        channels.append({
            'title': title.strip(),
            'logo': logo.strip(),
            'group': group.strip(),
            'url': url.strip(),
            'tvg_id': tvg_id.strip()
        })
        
    return channels

def list_groups(params):
    group_type = params.get('group_type')
    if group_type == 'category':
        url = "https://iptv-org.github.io/iptv/index.category.m3u"
        title = "Genuri (Genres)"
    elif group_type == 'country':
        url = "https://iptv-org.github.io/iptv/index.country.m3u"
        title = "Tari (Countries)"
    else:
        end_of_directory()
        return

    playlist_content = get_playlist(url)
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
        add_dir(group, {'action': 'alteliste', 'mode': 'iptv-org', 'group_type': group_type, 'group': group})
        
    end_of_directory()

def list_channels(params):
    group = params.get('group')
    group_type = params.get('group_type')
    
    if not group or not group_type:
        end_of_directory()
        return

    if group_type == 'country':
        url = "https://iptv-org.github.io/iptv/index.country.m3u"
    else: # category
        url = "https://iptv-org.github.io/iptv/index.category.m3u"

    playlist_content = get_playlist(url)
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
            {'action': 'alteliste', 'mode': 'play', 'provider': 'iptv_org', 'url': channel['url']},
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
    group = params.get('group')
    group_type = params.get('group_type')

    if group_type is None:
        # Main menu for IPTV-ORG
        add_dir("Tari (Countries)", {'action': 'alteliste', 'mode': 'iptv-org', 'group_type': 'country'})
        add_dir("Genuri (Genres)", {'action': 'alteliste', 'mode': 'iptv-org', 'group_type': 'category'})
        end_of_directory()
    elif group:
        list_channels(params)
    else:
        list_groups(params)
