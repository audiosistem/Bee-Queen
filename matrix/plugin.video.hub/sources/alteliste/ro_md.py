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

def get_token():
    try:
        url = "https://token.stb.md/api/Flussonic/stream/NICKELODEON_H264/metadata.json"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"})
        response.raise_for_status()
        data = response.json()
        variant_url = data.get('variants', [{}])[0].get('url')
        if variant_url:
            token_match = re.search(r'token=(.*)', variant_url)
            if token_match:
                return token_match.group(1)
        xbmcgui.Dialog().notification('Error', 'Could not find token in the response.', xbmcgui.NOTIFICATION_ERROR)
        return None
    except (requests.RequestException, ValueError, IndexError) as e:
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
    for entry in playlist_content.split('#EXTINF:-1')[1:]:
        try:
            logo_match = re.search(r'logo="([^"]*)"', entry)
            group_match = re.search(r'group-title="([^"]*)"', entry)
            title_match = re.search(r',(.*?)\n', entry)
            url_match = re.search(r'\n(http.*?token=)', entry)

            if all([logo_match, group_match, title_match, url_match]):
                logo = logo_match.group(1).strip()
                group = group_match.group(1).strip()
                title = title_match.group(1).strip()
                url = url_match.group(1).strip()

                channels.append({
                    'title': title,
                    'logo': logo,
                    'group': group,
                    'url': url + token
                })
        except Exception as e:
            import xbmc
            xbmc.log(f"Error parsing entry: {entry} - {e}", level=xbmc.LOGERROR)
    return channels

def list_channels(params):
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
        groups = sorted(list(set(c['group'] for c in channels)))
        add_dir("All Channels", {'action': 'alteliste', 'mode': 'ro-md', 'group': 'all'})
        for g in groups:
            add_dir(g, {'action': 'alteliste', 'mode': 'ro-md', 'group': g})
    else:
        if group == 'all':
            display_channels = channels
        else:
            display_channels = [c for c in channels if c['group'] == group]

        for channel in display_channels:
            add_item(
                channel['title'],
                {'action': 'alteliste', 'mode': 'play', 'provider': 'ro_md', 'url': channel['url']},
                thumb=channel['logo'],
                fanart=channel['logo']
            )
            
    end_of_directory()

def play_channel(params):
    url = params.get('url')
    if url:
        li = xbmcgui.ListItem(path=url)
        xbmcplugin.setResolvedUrl(_HANDLE, True, li)
