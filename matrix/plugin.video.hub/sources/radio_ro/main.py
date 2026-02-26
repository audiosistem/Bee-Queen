import xbmc
import sys
import json
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.request
from urllib.parse import parse_qsl

# Get the plugin handle
_handle = int(sys.argv[1])
_base_url = 'plugin://plugin.video.hub/'
_addon = xbmcaddon.Addon('plugin.video.hub')

def get_stations(offset=0, limit=20, order='clickcount'):
    """
    Fetches the radio station data from the Radio Browser API
    """
    try:
        country_code = _addon.getSetting('radio_ro_country_code')
        
        api_server = "https://de1.api.radio-browser.info" # Default

        if _addon.getSetting('radio_ro_use_de2_server') == 'true':
            api_server = "https://de2.api.radio-browser.info"
        elif _addon.getSetting('radio_ro_use_fi1_server') == 'true':
            api_server = "https://fi1.api.radio-browser.info"

        reverse = 'true' if order == 'clickcount' else 'false'
        url = f"{api_server}/json/stations/search?countrycode={country_code}&hidebroken=true&order={order}&reverse={reverse}&offset={offset}&limit={limit}"
        response = urllib.request.urlopen(url)
        data = response.read()
        stations = json.loads(data)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", str(e))
        return []
    return stations

def list_stations(stations, page=1, list_type='all'):
    """
    Lists the given stations
    """
    xbmcplugin.setContent(_handle, 'audio')
    for station in stations:
        list_item = xbmcgui.ListItem(label=station['name'])
        list_item.setInfo('music', {
            'title': station['name'],
            'genre': station.get('tags', ''),
            'plot': f"Language: {station.get('language', '')}\nCountry: {station.get('country', '')}\nTags: {station.get('tags', '')}",
            'website': station.get('homepage', ''),
            'album': station.get('country', ''),
            'comment': station.get('language', ''),
            'bitrate': station.get('bitrate', 0),
            'codec': station.get('codec', '')
        })
        list_item.setArt({'thumb': station['favicon'], 'fanart': station['favicon']})
        list_item.setProperty('IsPlayable', 'true')
        url = station['url_resolved']
        commands = []
        commands.append(('Add to Favorites', f'RunPlugin({_base_url}?action=radio_ro&mode=add_favorite&station_uuid={station["stationuuid"]})'))
        list_item.addContextMenuItems(commands)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, isFolder=False)
    
    if list_type == 'all' or list_type == 'popular':
        if len(stations) == 20:
            xbmcplugin.addDirectoryItem(_handle, _base_url + f'?action=radio_ro&mode={list_type}&page={page+1}', xbmcgui.ListItem('Next >>'), isFolder=True)
        if page > 1:
            xbmcplugin.addDirectoryItem(_handle, _base_url + f'?action=radio_ro&mode={list_type}&page={page-1}', xbmcgui.ListItem('<< Previous'), isFolder=True)

    xbmcplugin.endOfDirectory(_handle)

def main_menu():
    """
    Creates the main menu
    """
    xbmcplugin.addDirectoryItem(_handle, _base_url + '?action=radio_ro&mode=popular&page=1', xbmcgui.ListItem('Most Popular'), isFolder=True)
    xbmcplugin.addDirectoryItem(_handle, _base_url + '?action=radio_ro&mode=all&page=1', xbmcgui.ListItem('All Stations'), isFolder=True)
    xbmcplugin.addDirectoryItem(_handle, _base_url + '?action=radio_ro&mode=favorites', xbmcgui.ListItem('Favorites'), isFolder=True)
    xbmcplugin.addDirectoryItem(_handle, _base_url + '?action=radio_ro&mode=search', xbmcgui.ListItem('Search'), isFolder=True)
    xbmcplugin.addDirectoryItem(_handle, _base_url + '?action=radio_ro&mode=settings', xbmcgui.ListItem('Settings'), isFolder=True)
    xbmcplugin.endOfDirectory(_handle)

def search():
    """
    Searches for a station
    """
    keyboard = xbmc.Keyboard('', 'Search for a station')
    keyboard.doModal()
    if keyboard.isConfirmed():
        query = keyboard.getText()
        stations = get_stations(limit=1000)
        search_results = []
        for station in stations:
            if query.lower() in station['name'].lower():
                search_results.append(station)
        list_stations(search_results)

def get_favorites():
    """
    Gets the favorite stations
    """
    favorites_str = _addon.getSetting('radio_ro_favorites')
    if favorites_str:
        return json.loads(favorites_str)
    return []

def add_favorite(station_uuid):
    """
    Adds a station to the favorites
    """
    favorites = get_favorites()
    if station_uuid not in [f['stationuuid'] for f in favorites]:
        stations = get_stations(limit=1000)
        station = next((s for s in stations if s['stationuuid'] == station_uuid), None)
        if station:
            favorites.append(station)
            _addon.setSetting('radio_ro_favorites', json.dumps(favorites))
            xbmcgui.Dialog().notification('Favorites', f'{station["name"]} added to favorites')

def remove_favorite(station_uuid):
    """
    Removes a station from the favorites
    """
    favorites = get_favorites()
    favorites = [f for f in favorites if f['stationuuid'] != station_uuid]
    _addon.setSetting('radio_ro_favorites', json.dumps(favorites))
    xbmcgui.Dialog().notification('Favorites', 'Station removed from favorites')
    xbmc.executebuiltin('Container.Refresh')

def list_favorites():
    """
    Lists the favorite stations
    """
    favorites = get_favorites()
    xbmcplugin.setContent(_handle, 'audio')
    for station in favorites:
        list_item = xbmcgui.ListItem(label=station['name'])
        list_item.setInfo('music', {'title': station['name']})
        list_item.setArt({'thumb': station['favicon'], 'fanart': station['favicon']})
        list_item.setProperty('IsPlayable', 'true')
        url = station['url_resolved']
        commands = []
        commands.append(('Remove from Favorites', f'RunPlugin({_base_url}?action=radio_ro&mode=remove_favorite&station_uuid={station["stationuuid"]})'))
        list_item.addContextMenuItems(commands)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, isFolder=False)
    xbmcplugin.endOfDirectory(_handle)

def router(params):
    """
    Router function
    """
    mode = params.get('mode')
    page = int(params.get('page', 1))
    offset = (page - 1) * 20

    if mode == 'all':
        list_stations(get_stations(offset=offset, limit=20, order='name'), page=page, list_type='all')
    elif mode == 'popular':
        stations = get_stations(offset=offset, limit=20, order='clickcount')
        list_stations(stations, page=page, list_type='popular')
    elif mode == 'search':
        search()
    elif mode == 'favorites':
        list_favorites()
    elif mode == 'add_favorite':
        add_favorite(params['station_uuid'])
    elif mode == 'remove_favorite':
        remove_favorite(params['station_uuid'])
    elif mode == 'settings':
        _addon.openSettings()
    else:
        main_menu()

if __name__ == '__main__':
    router(dict(parse_qsl(sys.argv[2][1:])))