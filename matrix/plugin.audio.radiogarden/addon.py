# -*- coding: utf-8 -*-
"""
Radio Garden Kodi Add-on
Listen to radio stations from around the world
"""

import sys
import os
from urllib.parse import urlencode, parse_qs
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Adicionar resources/lib ao path
addon_path = xbmcaddon.Addon().getAddonInfo('path')
lib_path = os.path.join(addon_path, 'resources', 'lib')
sys.path.append(lib_path)

from radiogarden import RadioGardenAPI
from favorites import FavoritesManager


# Obter handle e addon
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')

# Lógica de Tradução Manual
def get_string(string_id):
    """Obter string traduzida respeitando a configuração de idioma"""
    # Se for uma string do sistema (numérica), usar o método padrão do Kodi
    if isinstance(string_id, int) or (isinstance(string_id, str) and string_id.isdigit()):
        return addon.getLocalizedString(int(string_id))
    
    # Mapeamento de strings manuais para os 3 idiomas
    translations = {
        'local_stations': {
            'pt': 'Rádios Locais',
            'en': 'Local Stations',
            'ro': 'Stații Locale'
        },
        'favorites': {
            'pt': 'Meus Favoritos',
            'en': 'My Favorites',
            'ro': 'Favoritele Mele'
        },
        'search_stations': {
            'pt': 'Buscar Estações',
            'en': 'Search Stations',
            'ro': 'Căutare Stații'
        },
        'search_country': {
            'pt': 'Buscar por País',
            'en': 'Search by Country',
            'ro': 'Căutare după Țară'
        },
        'search_city': {
            'pt': 'Buscar por Cidade',
            'en': 'Search by City',
            'ro': 'Căutare după Oraș'
        },
        'search_input': {
            'pt': 'Digite sua busca',
            'en': 'Enter your search',
            'ro': 'Introduceți căutarea'
        },
        'no_results': {
            'pt': 'Nenhum resultado encontrado',
            'en': 'No results found',
            'ro': 'Niciun rezultat găsit'
        },
        'stations': {
            'pt': 'estações',
            'en': 'stations',
            'ro': 'stații'
        },
        'no_stations_in': {
            'pt': 'Nenhuma estação em',
            'en': 'No stations in',
            'ro': 'Nicio stație în'
        },
        'add_fav': {
            'pt': 'Adicionar aos Favoritos',
            'en': 'Add to Favorites',
            'ro': 'Adaugă la Favorite'
        },
        'rem_fav': {
            'pt': 'Remover dos Favoritos',
            'en': 'Remove from Favorites',
            'ro': 'Elimină din Favorite'
        },
        'added_to_fav': {
            'pt': 'adicionado aos favoritos',
            'en': 'added to favorites',
            'ro': 'adăugat la favorite'
        },
        'already_in_fav': {
            'pt': 'Já está nos favoritos',
            'en': 'Already in favorites',
            'ro': 'Deja în favorite'
        },
        'removed_from_fav': {
            'pt': 'Removido dos favoritos',
            'en': 'Removed from favorites',
            'ro': 'Eliminat din favorite'
        },
        'no_fav_added': {
            'pt': 'Nenhum favorito adicionado',
            'en': 'No favorites added',
            'ro': 'Niciun favorit adăugat'
        }
    }
    
    lang_setting = addon.getSetting('language_select')
    # 0: Auto, 1: Português, 2: English, 3: Română
    
    if lang_setting == '1': # Português
        lang_key = 'pt'
    elif lang_setting == '2': # English
        lang_key = 'en'
    elif lang_setting == '3': # Română
        lang_key = 'ro'
    else: # Auto (Detectar do Kodi)
        kodi_lang = xbmc.getLanguage(xbmc.ISO_639_1)
        if kodi_lang == 'pt': lang_key = 'pt'
        elif kodi_lang == 'ro': lang_key = 'ro'
        else: lang_key = 'en'
        
    return translations.get(string_id, {}).get(lang_key, string_id)

# Caminhos para as artes
FANART = os.path.join(addon_path, 'resources', 'fanart.jpg')
ICON = os.path.join(addon_path, 'resources', 'icon.png')


def build_url(query):
    """Construir URL do plugin"""
    base_url = sys.argv[0]
    return base_url + '?' + urlencode(query)


def add_directory_item(label, mode, is_folder=True, params=None):
    """Auxiliar para adicionar itens ao diretório com o ícone do plugin"""
    if params is None:
        params = {}
    params['mode'] = mode
    url = build_url(params)
    
    list_item = xbmcgui.ListItem(label=label)
    list_item.setArt({
        'icon': ICON,
        'thumb': ICON,
        'fanart': FANART
    })
    
    xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=is_folder)


def show_main_menu():
    """Exibir menu principal simplificado"""
    
    # Opção de rádios locais
    add_directory_item(get_string('local_stations'), 'local_stations', params={})
    
    # Opção de favoritos
    add_directory_item(get_string('favorites'), 'favorites', params={})
    
    # Opção de busca geral
    add_directory_item(get_string('search_stations'), 'search_dialog', params={'type': 'all'})
    
    # Opção de buscar por país
    add_directory_item(get_string('search_country'), 'search_dialog', params={'type': 'country'})
    
    # Opção de buscar por cidade
    add_directory_item(get_string('search_city'), 'search_dialog', params={'type': 'city'})
    
    xbmcplugin.setContent(addon_handle, 'songs')
    xbmcplugin.endOfDirectory(addon_handle)


def search_dialog(search_type='all'):
    """Exibir diálogo de busca"""
    keyboard = xbmcgui.Dialog().input(get_string('search_input'), type=xbmcgui.INPUT_ALPHANUM)
    
    if keyboard:
        execute_search(keyboard, search_type)


def execute_search(query, search_type='all'):
    """Executar a busca e exibir resultados"""
    api = RadioGardenAPI()
    results = api.search(query)
    
    if not results:
        xbmcgui.Dialog().notification(
            'Radio Garden',
            get_string('no_results'),
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return
    
    # Filtrar resultados por tipo se necessário
    if search_type == 'country':
        results = [r for r in results if r['type'] == 'country']
    elif search_type == 'city':
        results = [r for r in results if r['type'] == 'place']
    
    display_results(results)


def display_results(results):
    """Exibir resultados da busca"""
    fav_manager = FavoritesManager()
    
    for result in results:
        result_type = result.get('type', '')
        title = result.get('title', 'Sem título')
        subtitle = result.get('subtitle', '')
        
        if subtitle:
            label = f"{title} - {subtitle}"
        else:
            label = title
        
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
        
        if result_type == 'channel':
            channel_id = result.get('channel_id', '')
            if channel_id:
                list_item.setProperty('IsPlayable', 'true')
                list_item.setInfo('music', {
                    'title': title,
                    'artist': subtitle,
                    'mediatype': 'song'
                })
                
                # Menu de contexto para adicionar/remover favoritos
                is_fav = fav_manager.is_favorite(channel_id)
                context_menu = []
                if is_fav:
                    context_menu.append((get_string('rem_fav'), f'RunPlugin({build_url({"mode": "remove_favorite", "channel_id": channel_id})})'))
                else:
                    context_menu.append((get_string('add_fav'), f'RunPlugin({build_url({"mode": "add_favorite", "channel_id": channel_id, "title": title, "subtitle": subtitle})})'))
                list_item.addContextMenuItems(context_menu)
                
                url = build_url({'mode': 'play', 'channel_id': channel_id, 'title': title})
                xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=False)
        
        elif result_type == 'place':
            place_id = result.get('place_id', '')
            count = result.get('count', 0)
            if place_id:
                list_item.setLabel(f"{label} ({count} {get_string('stations')})")
                url = build_url({'mode': 'place', 'place_id': place_id, 'title': title})
                xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=True)
        
        elif result_type == 'country':
            country_id = result.get('country_id', '')
            if country_id:
                url = build_url({'mode': 'country', 'country_id': country_id, 'title': title})
                xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=True)
    
    xbmcplugin.setContent(addon_handle, 'songs')
    xbmcplugin.endOfDirectory(addon_handle)


def show_country_channels(country_id, title):
    """Exibir canais de um país"""
    api = RadioGardenAPI()
    fav_manager = FavoritesManager()
    channels = api.get_country_channels(country_id)
    
    if not channels:
        xbmcgui.Dialog().notification('Radio Garden', f"{get_string('no_stations_in')} {title}", xbmcgui.NOTIFICATION_INFO, 3000)
        return
    
    for channel in channels:
        channel_id = channel.get('channel_id', '')
        channel_title = channel.get('title', 'Sem título')
        channel_subtitle = channel.get('subtitle', '')
        
        label = f"{channel_title}"
        if channel_subtitle:
            label += f" - {channel_subtitle}"
        
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
        list_item.setProperty('IsPlayable', 'true')
        list_item.setInfo('music', {
            'title': channel_title,
            'artist': channel_subtitle,
            'mediatype': 'song'
        })
        
        # Menu de contexto para favoritos
        is_fav = fav_manager.is_favorite(channel_id)
        context_menu = []
        if is_fav:
            context_menu.append((get_string('rem_fav'), f'RunPlugin({build_url({"mode": "remove_favorite", "channel_id": channel_id})})'))
        else:
            context_menu.append((get_string('add_fav'), f'RunPlugin({build_url({"mode": "add_favorite", "channel_id": channel_id, "title": channel_title, "subtitle": channel_subtitle})})'))
        list_item.addContextMenuItems(context_menu)
        
        url = build_url({'mode': 'play', 'channel_id': channel_id, 'title': channel_title})
        xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=False)
    
    xbmcplugin.setContent(addon_handle, 'songs')
    xbmcplugin.endOfDirectory(addon_handle)


def show_place_channels(place_id, title):
    """Exibir canais de um local"""
    api = RadioGardenAPI()
    fav_manager = FavoritesManager()
    channels = api.get_place_channels(place_id)
    
    if not channels:
        xbmcgui.Dialog().notification('Radio Garden', f"{get_string('no_stations_in')} {title}", xbmcgui.NOTIFICATION_INFO, 3000)
        return
    
    for channel in channels:
        channel_id = channel.get('channel_id', '')
        channel_title = channel.get('title', 'Sem título')
        channel_subtitle = channel.get('subtitle', '')
        
        label = f"{channel_title}"
        if channel_subtitle:
            label += f" - {channel_subtitle}"
        
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
        list_item.setProperty('IsPlayable', 'true')
        list_item.setInfo('music', {
            'title': channel_title,
            'artist': channel_subtitle,
            'mediatype': 'song'
        })
        
        # Menu de contexto para favoritos
        is_fav = fav_manager.is_favorite(channel_id)
        context_menu = []
        if is_fav:
            context_menu.append((get_string('rem_fav'), f'RunPlugin({build_url({"mode": "remove_favorite", "channel_id": channel_id})})'))
        else:
            context_menu.append((get_string('add_fav'), f'RunPlugin({build_url({"mode": "add_favorite", "channel_id": channel_id, "title": channel_title, "subtitle": channel_subtitle})})'))
        list_item.addContextMenuItems(context_menu)
        
        url = build_url({'mode': 'play', 'channel_id': channel_id, 'title': channel_title})
        xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=False)
    
    xbmcplugin.setContent(addon_handle, 'songs')
    xbmcplugin.endOfDirectory(addon_handle)


def play_station(channel_id, title):
    """Reproduzir estação de rádio"""
    api = RadioGardenAPI()
    stream_url = api.get_stream_url(channel_id)
    
    play_item = xbmcgui.ListItem(path=stream_url)
    play_item.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
    play_item.setInfo('music', {'title': title, 'mediatype': 'song'})
    play_item.setProperty('IsPlayable', 'true')
    
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=play_item)


def show_favorites():
    """Exibir lista de favoritos"""
    fav_manager = FavoritesManager()
    favorites = fav_manager.get_favorites()
    
    if not favorites:
        xbmcgui.Dialog().notification('Radio Garden', get_string('no_fav_added'), xbmcgui.NOTIFICATION_INFO, 3000)
        return
    
    for fav in favorites:
        channel_id = fav.get('channel_id', '')
        channel_title = fav.get('title', 'Sem título')
        channel_subtitle = fav.get('subtitle', '')
        
        label = f"{channel_title}"
        if channel_subtitle:
            label += f" - {channel_subtitle}"
        
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
        list_item.setProperty('IsPlayable', 'true')
        list_item.setInfo('music', {
            'title': channel_title,
            'artist': channel_subtitle,
            'mediatype': 'song'
        })
        
        # Menu de contexto para remover dos favoritos
        context_menu = [(get_string('rem_fav'), f'RunPlugin({build_url({"mode": "remove_favorite", "channel_id": channel_id})})')]
        list_item.addContextMenuItems(context_menu)
        
        url = build_url({'mode': 'play', 'channel_id': channel_id, 'title': channel_title})
        xbmcplugin.addDirectoryItem(addon_handle, url, list_item, isFolder=False)
    
    xbmcplugin.setContent(addon_handle, 'songs')
    xbmcplugin.endOfDirectory(addon_handle)


def show_local_stations():
    """Exibir estações de rádio locais baseadas na geolocalização"""
    api = RadioGardenAPI()
    title, channels = api.get_local_stations()
    
    if not channels:
        xbmcgui.Dialog().notification('Radio Garden', get_string('no_results'), xbmcgui.NOTIFICATION_INFO, 3000)
        return
        
    display_results(channels)


def add_to_favorites(channel_id, title, subtitle=''):
    """Adicionar estação aos favoritos"""
    fav_manager = FavoritesManager()
    if fav_manager.add_favorite(channel_id, title, subtitle):
        xbmcgui.Dialog().notification('Radio Garden', f"{title} {get_string('added_to_fav')}", xbmcgui.NOTIFICATION_INFO, 2000)
    else:
        xbmcgui.Dialog().notification('Radio Garden', get_string('already_in_fav'), xbmcgui.NOTIFICATION_WARNING, 2000)


def remove_from_favorites(channel_id):
    """Remover estação dos favoritos"""
    fav_manager = FavoritesManager()
    if fav_manager.remove_favorite(channel_id):
        xbmcgui.Dialog().notification('Radio Garden', get_string('removed_from_fav'), xbmcgui.NOTIFICATION_INFO, 2000)
    xbmc.executebuiltin('Container.Refresh')


def router(params):
    """Roteador principal"""
    mode = params.get('mode', [None])[0]
    
    if mode is None:
        show_main_menu()
    elif mode == 'favorites':
        show_favorites()
    elif mode == 'add_favorite':
        channel_id = params.get('channel_id', [''])[0]
        title = params.get('title', [''])[0]
        subtitle = params.get('subtitle', [''])[0]
        add_to_favorites(channel_id, title, subtitle)
    elif mode == 'remove_favorite':
        channel_id = params.get('channel_id', [''])[0]
        remove_from_favorites(channel_id)
    elif mode == 'local_stations':
        show_local_stations()
    elif mode == 'search_dialog':
        search_type = params.get('type', ['all'])[0]
        search_dialog(search_type)
    elif mode == 'country':
        country_id = params.get('country_id', [''])[0]
        title = params.get('title', [''])[0]
        show_country_channels(country_id, title)
    elif mode == 'place':
        place_id = params.get('place_id', [''])[0]
        title = params.get('title', [''])[0]
        show_place_channels(place_id, title)
    elif mode == 'play':
        channel_id = params.get('channel_id', [''])[0]
        title = params.get('title', ['Radio Garden'])[0]
        play_station(channel_id, title)


if __name__ == '__main__':
    params = parse_qs(sys.argv[2][1:])
    router(params)
