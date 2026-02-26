import sys
import requests
import gzip
import json
import xbmcgui
import xbmcplugin
import xbmc
from urllib.parse import urlencode

_BASE_URL = 'plugin://plugin.video.hub/'
_HANDLE = int(sys.argv[1])

JSON_URL = "https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/all/tv.json.gz"

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

def get_channels():
    try:
        response = requests.get(JSON_URL)
        response.raise_for_status()
        
        # Decompress the gzipped content
        decompressed_data = gzip.decompress(response.content)
        
        # Parse the JSON data
        data = json.loads(decompressed_data)
        
        return data
    except (requests.RequestException, gzip.BadGzipFile, json.JSONDecodeError) as e:
        xbmcgui.Dialog().notification('Error', f'Failed to get channel list: {e}', xbmcgui.NOTIFICATION_ERROR)
        return None

def list_channels(params):
    channels = get_channels()
    if not channels:
        end_of_directory()
        return

    for channel_id, channel_data in channels.items():
        add_item(
            channel_data['name'],
            {
                'action': 'alteliste',
                'mode': 'play',
                'provider': 'world',
                'url': channel_data['mjh_master'],
                'headers': json.dumps(channel_data.get('headers', {}))
            },
            thumb=channel_data['logo'],
            fanart=channel_data['logo']
        )
            
    end_of_directory()

def play_channel(params):
    url = params.get('url')
    headers_str = params.get('headers', '{}')
    
    if url:
        headers = json.loads(headers_str)
        if 'referer' in headers and not headers['referer'].strip():
            del headers['referer']
        if 'seekable' in headers:
            del headers['seekable']
        if 'user-agent' in headers:
            del headers['user-agent']
            
        play_url = url
        if headers:
            play_url += f"|{urlencode(headers)}"

        xbmc.log(f"Playing URL: {play_url}", level=xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=play_url)
        xbmcplugin.setResolvedUrl(_HANDLE, True, li)

def router(params):
    mode = params.get('mode')
    if mode == 'play':
        play_channel(params)
    else:
        list_channels(params)