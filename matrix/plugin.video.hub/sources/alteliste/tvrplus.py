import sys
import re
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode
import requests

_BASE_URL = 'plugin://plugin.video.hub/'
_HANDLE = int(sys.argv[1])

CHANNELS = [
    {'name': 'TVR 1', 'url': 'https://www.tvrplus.ro/live/tvr-1', 'logo': 'https://www.tvrplus.ro/logos/tvr-1.jpg'},
    {'name': 'TVR 2', 'url': 'https://www.tvrplus.ro/live/tvr-2', 'logo': 'https://www.tvrplus.ro/logos/tvr-2.jpg'},
    {'name': 'TVR Info', 'url': 'https://www.tvrplus.ro/live/tvr-info', 'logo': 'https://www.tvrplus.ro/logos/tvr-info.jpg'},
    {'name': 'TVR Cultural', 'url': 'https://www.tvrplus.ro/live/tvr-cultural', 'logo': 'https://www.tvrplus.ro/logos/tvr-cultural.jpg'},
    {'name': 'TVR Folclor', 'url': 'https://www.tvrplus.ro/live/tvr-folclor', 'logo': 'https://www.tvrplus.ro/logos/tvr-folclor.jpg'},
    {'name': 'TVR Sport', 'url': 'https://www.tvrplus.ro/live/tvr-sport', 'logo': 'https://www.tvrplus.ro/logos/tvr-sport.jpg'},
    {'name': 'TVR 3', 'url': 'https://www.tvrplus.ro/live/tvr-3', 'logo': 'https://www.tvrplus.ro/logos/tvr-3.jpg'},
    {'name': 'TVR International', 'url': 'https://www.tvrplus.ro/live/tvr-international', 'logo': 'https://www.tvrplus.ro/logos/tvr-international.jpg'},
    {'name': 'TVR Moldova', 'url': 'https://www.tvrplus.ro/live/tvr-moldova', 'logo': 'https://www.tvrplus.ro/logos/tvr-moldova.jpg'},
    {'name': 'TVR Cluj', 'url': 'https://www.tvrplus.ro/live/tvr-cluj', 'logo': 'https://www.tvrplus.ro/logos/tvr-cluj.jpg'},
    {'name': 'TVR Craiova', 'url': 'https://www.tvrplus.ro/live/tvr-craiova', 'logo': 'https://www.tvrplus.ro/logos/tvr-craiova.jpg'},
    {'name': 'TVR Iași', 'url': 'https://www.tvrplus.ro/live/tvr-iasi', 'logo': 'https://www.tvrplus.ro/logos/tvr-iasi.jpg'},
    {'name': 'TVR Timișoara', 'url': 'https://www.tvrplus.ro/live/tvr-timisoara', 'logo': 'https://www.tvrplus.ro/logos/tvr-timisoara.jpg'},
    {'name': 'TVR Târgu-Mureș', 'url': 'https://www.tvrplus.ro/live/tvr-targu-mures', 'logo': 'https://www.tvrplus.ro/logos/tvr-targu-mures.jpg'},
]

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

def list_channels(params):
    """List all TVR+ channels."""
    for channel in CHANNELS:
        add_item(
            channel['name'],
            {
                'action': 'alteliste',
                'mode': 'tvrplus_play',
                'url': channel['url']
            },
            thumb=channel['logo'],
            fanart=channel['logo']
        )
    end_of_directory()

def play_channel(params):
    """Play the selected TVR+ channel."""
    page_url = params.get('url')
    if page_url:
        try:
            response = requests.get(page_url, verify=False)
            response.raise_for_status()
            html_content = response.text
            
            stream_url_match = re.search(r'src:\s*\'([^\']+\.m3u8)\'', html_content)
            if stream_url_match:
                stream_url = stream_url_match.group(1)
                li = xbmcgui.ListItem(path=stream_url)
                xbmcplugin.setResolvedUrl(_HANDLE, True, li)
            else:
                xbmcgui.Dialog().notification('Error', 'Could not find the stream URL.', xbmcgui.NOTIFICATION_ERROR)
        except requests.RequestException as e:
            xbmcgui.Dialog().notification('Error', f'Failed to fetch page: {e}', xbmcgui.NOTIFICATION_ERROR)

def router(params):
    """Router for TVR+."""
    mode = params.get('mode')
    if mode == 'tvrplus_play':
        play_channel(params)
    else:
        list_channels(params)
