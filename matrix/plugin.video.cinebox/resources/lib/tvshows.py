# -*- coding: utf-8 -*-
# Em: resources/lib/tvshows.py

import json
import os
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

# Mantenha apenas o db e utils que são leves e essenciais para as listagens
from .utils import create_video_item_with_library, with_view_mode

# Configurações e funções comuns
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
DEFAULT_ITEMS_PER_PAGE = int(ADDON.getSetting("pages"))
TMDB_API_KEY = ADDON.getSetting("tmdb_api")

ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

PROVIDER_LOGOS = {
    "Amazon Prime Video": "prime_video.png",
    "Netflix": "netflix.png",
    "Max": "hbo_max.png",
    "Disney Plus": "disney_plus.png",
    "Apple TV+": "apple_tv.png",
    "Paramount plus": "paramount_plus.png",
    "Crunchyroll": "crunchyroll.png",
    "Globoplay": "globoplay.png",
    "Looke": "looke.png",
    "Hulu": "hulu.png",
    "Peacock": "peacock.png",
    "Discovery+": "discovery_plus.png",
}



def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"


# --- ✅ NOVAS FUNÇÕES AUXILIARES ---

def _prepare_details_data(item_data):
    """Prepara um dicionário com os dados do item para a URL da tela de detalhes."""
    genres = item_data.get('genres', [])
    genre_str = ', '.join(genres) if isinstance(genres, list) else str(genres)
    providers_list = item_data.get('providers', [])
    return {
        'tmdb_id': item_data.get('tmdb_id'),
        'imdb_id': item_data.get('imdb_id'),
        'title': item_data.get('title'),
        'original_title': item_data.get('original_title', item_data.get('title')),
        'clearlogo': item_data.get('clearlogo'),
        'synopsis': item_data.get('synopsis'),
        'poster': item_data.get('poster'),
        'backdrop': item_data.get('backdrop'),
        'year': item_data.get('year'),
        'rating': item_data.get('rating'),
        'certification': item_data.get('certification'),
        'genre': genre_str,
        'media_type': 'tvshow',
        'providers': json.dumps(providers_list)
    }


def _create_show_tuple(show_data):
    """
    Cria a tupla (url, listitem, is_folder) para séries (TV Shows) usando a função completa.
    """
    li = create_video_item_with_library(show_data, 'tvshow')
    
    if False: # ADDON.getSettingBool("tvshow.enable_details"):
        details_data = _prepare_details_data(show_data)
        url = get_url(action='show_details', data=json.dumps(details_data, ensure_ascii=False))
        is_folder = False
    else:
        url = get_url(action='list_seasons', tvshow_tmdb_id=show_data.get('tmdb_id'))
        is_folder = True

    return (url, li, is_folder)


# --- FUNÇÕES DE NAVEGAÇÃO DE SÉRIES ---

def show_tvshows_menu(menu_structure):
    from .icons import get_icon_url
    """Cria e exibe o menu da seção 'Séries'."""
    xbmcplugin.setPluginCategory(HANDLE, 'Seriale')
    fanart_addon = ADDON.getAddonInfo('fanart')
    for item in menu_structure:
        li = xbmcgui.ListItem(label=item['title'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        icon = item.get('icon')
        if icon:
            # NOVO: Suporta IDs de ícones do IMDb
            if isinstance(icon, str) and len(icon) < 15 and not icon.endswith('.png'):
                # É um ID de ícone, converte para URL
                icon_url = get_icon_url(icon)
                li.setArt({'thumb': icon_url, 'icon': icon_url})
            else:
                # É um caminho local
                li.setArt({'thumb': icon})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_streaming_platforms():
    """Lista as plataformas de streaming para séries."""
    from .constants import STREAMING_PLATFORMS
    xbmcplugin.setPluginCategory(HANDLE, 'Seriale pentru Streaming')
    fanart_addon = ADDON.getAddonInfo('fanart')
    
    for platform in STREAMING_PLATFORMS['tv']:
        li = xbmcgui.ListItem(label=platform['name'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        # Usar logo do TMDB (JustWatch) como no IMDB
        logo = platform.get('logo')
        if logo:
            if logo.endswith('.jpg') or logo.endswith('.png'):
                logo_url = f"https://image.tmdb.org/t/p/w500/{logo}"
                li.setArt({'thumb': logo_url, 'icon': logo_url, 'poster': logo_url})
            else:
                li.setArt({'thumb': logo, 'icon': logo, 'poster': logo})
            
        url = get_url(action='list_tvshows_by_streaming', provider_id=platform['id'], provider_name=platform['name'], region=platform.get('region', 'BR'))
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_tvshows_by_popularity(page=1):
    """Lista séries por popularidade."""
    from .tmdb_api import fetch_popular_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Seriale Populare')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = fetch_popular_tvshows(page=page)
    
    items = []
    for show in shows:
        items.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(shows, page, action='list_tvshows_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_tvshows_top_rated(page=1):
    """Lista séries melhor avaliadas."""
    from .tmdb_api import fetch_top_rated_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Top Rated')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = fetch_top_rated_tvshows(page=page)
    
    items = []
    for show in shows:
        items.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(shows, page, action='list_tvshows_top_rated')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_tvshows_airing_today(page=1):
    """Lista séries que passam hoje."""
    from .tmdb_api import fetch_airing_today_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Lansate Astazi')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = fetch_airing_today_tvshows(page=page)
    
    items = []
    for show in shows:
        items.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(shows, page, action='list_tvshows_airing_today')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_tvshows_on_the_air(page=1):
    """Lista séries que estão no ar."""
    from .tmdb_api import fetch_on_the_air_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'No Ar (Semana)')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = fetch_on_the_air_tvshows(page=page)
    
    items = []
    for show in shows:
        items.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(shows, page, action='list_tvshows_on_the_air')
    xbmcplugin.endOfDirectory(HANDLE)


def add_next_page_item(items_on_current_page, current_page, **kwargs):
    """Adiciona o item 'Próxima Página' a uma lista se houver mais itens."""
    num_items = len(items_on_current_page)
    items_per_page = int(ADDON.getSetting("pages") or 20)
    xbmc.log(f"[Cinebox] Paginação: {num_items} itens na página {current_page}, action={kwargs.get('action', 'unknown')}", xbmc.LOGINFO)
    
    if num_items >= items_per_page:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Pagina Urmatoare")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        li_next.setInfo('video', {'plot': f'Ir para a página {current_page + 1}'})

        next_page_args = kwargs.copy()
        next_page_args['page'] = current_page + 1
        next_page_url = get_url(**next_page_args)
        
        xbmc.log(f"[Cinebox] Adicionando botão Próxima Página: {next_page_url}", xbmc.LOGINFO)
        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, li_next, isFolder=True)
    else:
        xbmc.log(f"[Cinebox] Não há próxima página (apenas {num_items} itens)", xbmc.LOGINFO)

def list_seasons(tvshow_tmdb_id):
    from .tmdb_api import fetch_show_details 
    from .db.db import db_instance as db
    """
    Lista temporadas usando exclusivamente TMDB.
    """
    # 1. Busca dados da SÉRIE no DB local ou TMDB
    show = db.get_tvshow_by_id(tvshow_tmdb_id)
    
    # Se não estiver no DB local, busca no TMDB para garantir que temos os dados básicos
    if not show:
        show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
        if show_details_tmdb:
            show = show_details_tmdb
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return
            
    xbmcplugin.setPluginCategory(HANDLE, show['title'])
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'seasons')

    # 2. Busca temporadas do TMDB (fetch_show_details já retorna seasons_data)
    show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
    if not show_details_tmdb:
        xbmcplugin.endOfDirectory(HANDLE)
        return
        
    seasons_data_list = show_details_tmdb.get('seasons_data', [])
    
    # Forçar ocultação de temporadas especiais (Temporada 0)
    show_specials_enabled = False
        
    if not seasons_data_list:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    for season_data in seasons_data_list:
        season_number = season_data.get('season_number', season_data.get('number', 0))
        
        if season_number == 0 and not show_specials_enabled:
            continue
            
        tmdb_season_name = season_data.get('name', f"Temporada {season_number}")
        air_date = season_data.get('air_date')
        
        if air_date and air_date > current_date:
            # Formata data para o título em vermelho
            air_date_br = air_date
            if air_date and "-" in air_date:
                parts = air_date.split("-")
                air_date_br = "%s/%s/%s" % (parts[2], parts[1], parts[0])
            tmdb_season_name = f"[COLOR red]{tmdb_season_name} ({air_date_br})[/COLOR]"
        
        # Prepara dados para create_video_item
        if 'poster' not in season_data and season_data.get('poster_path'):
             season_data['poster'] = f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}"
        
        season_data['title'] = tmdb_season_name
        season_data['label'] = tmdb_season_name
        
        li = create_video_item_with_library(season_data, 'season', show_data=show)
        
        # Adiciona arte específica da temporada
        season_poster_path = season_data.get('poster_path')
        
        # Pôster: usa o pôster da temporada se disponível, senão usa da série
        if season_poster_path:
            season_poster = f"https://image.tmdb.org/t/p/w500{season_poster_path}"
        else:
            season_poster = show.get('poster')
        
        # Fanart/Background: sempre usa o backdrop da série (formato 16:9/paisagem)
        # TMDB não fornece backdrop específico para temporadas
        season_fanart = show.get('backdrop')
        
        li.setArt({
            'fanart': season_fanart,
            'landscape': season_fanart,
            'poster': season_poster,
            'thumb': season_poster,
            'icon': season_poster
        })
        
        from .sinopse import enriquecer_sinopse_episodio
        # Fallback: se a temporada não tiver sinopse, usa a da série
        season_plot = season_data.get('overview')
        if not season_plot or season_plot.strip() == "":
            season_plot = show.get('synopsis') or show.get('plot') or "Sinopse não disponível."
            
        # Garante que season_data tenha os campos necessários para o enriquecimento
        # fetch_show_details já retorna seasons_data com air_date, episode_count, vote_average
        plot_enriquecido = enriquecer_sinopse_episodio(season_data, season_plot)
        
        li.setInfo('video', {
            'title': tmdb_season_name,
            'plot': plot_enriquecido,
            'rating': season_data.get('vote_average', 0.0),
            'season': season_number,
            'mediatype': 'season'
        })
        
        url = get_url(
            action='list_episodes', 
            tvshow_tmdb_id=tvshow_tmdb_id, 
            season_number=season_number
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes(tvshow_tmdb_id, season_number):
    from .tmdb_api import fetch_show_details
    from .db.db import db_instance as db
    """
    Lista episódios usando exclusivamente TMDB.
    """
    # 1. Obter dados da SÉRIE
    show_data = db.get_tvshow_by_id(tvshow_tmdb_id)
    if not show_data:
        show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
        if show_details_tmdb:
            show_data = show_details_tmdb
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    xbmcplugin.setPluginCategory(HANDLE, f"{show_data.get('title')} - Temporada {season_number}")
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'episodes')

    # 2. Busca episódios do TMDB
    tmdb_episodes = _fetch_tmdb_season_details(tvshow_tmdb_id, season_number)
    
    if not tmdb_episodes:
        xbmcgui.Dialog().ok("Atentie", "Nu sa gasit nici un episod.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # 3. Loop para criar os itens
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    for ep_data_tmdb in tmdb_episodes:
        ep_number = ep_data_tmdb.get('episode_number')
        ep_name = ep_data_tmdb.get('name')
        air_date = ep_data_tmdb.get('air_date')
        
        # Verifica se o episódio já foi lançado
        is_unaired = False
        if not air_date or air_date > current_date:
            is_unaired = True
            
        if is_unaired:
            # Formata data para o título em vermelho
            air_date_br = air_date
            if air_date and "-" in air_date:
                parts = air_date.split("-")
                air_date_br = "%s/%s/%s" % (parts[2], parts[1], parts[0])
            ep_title = f"[COLOR red]Episod.{ep_number} ({air_date_br})[/COLOR]"
        else:
            ep_title = f"Episod.{ep_number}"
        
        episode_poster_url = show_data.get('backdrop') # Fallback
        episode_fanart_url = None
        
        if ep_data_tmdb.get('still_path'):
            episode_poster_url = f"https://image.tmdb.org/t/p/w500{ep_data_tmdb.get('still_path')}"
            episode_fanart_url = f"https://image.tmdb.org/t/p/original{ep_data_tmdb.get('still_path')}"

        item_data_for_scraper = {
            'media_type': 'tvshow', 
            'imdb_id': show_data.get('imdb_id'),
            'tmdb_id': tvshow_tmdb_id,
            'title': show_data.get('title'),
            'original_title': show_data.get('original_title', show_data.get('title')),
            'year': show_data.get('year'),
            'backdrop': show_data.get('backdrop'),
            'poster': show_data.get('poster'),
            'clearlogo': show_data.get('clearlogo'),
            'episode_title': ep_data_tmdb.get('name'),
            'plot': ep_data_tmdb.get('overview'),
            'episode_poster': episode_poster_url,
            'episode_fanart': episode_fanart_url,
            'rating': ep_data_tmdb.get('vote_average'),
            'season': season_number,
            'episode': ep_number,
            'premiered': ep_data_tmdb.get('air_date'),
            'runtime': ep_data_tmdb.get('runtime', 0)
        }
        
        li = xbmcgui.ListItem(label=ep_title)
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        from .sinopse import enriquecer_sinopse_episodio
        plot_enriquecido = enriquecer_sinopse_episodio(ep_data_tmdb, item_data_for_scraper['plot'])
        
        info = {
            'title': ep_title,
            'plot': plot_enriquecido,
            'season': item_data_for_scraper['season'],
            'episode': item_data_for_scraper['episode'],
            'rating': item_data_for_scraper['rating'],
            'aired': item_data_for_scraper['premiered'],
            'duration': (item_data_for_scraper.get('runtime') or 0) * 60,
            'tvshowtitle': item_data_for_scraper['title'],
            'mediatype': 'episode',
            'imdbnumber': show_data.get('imdb_id', '')
        }
        li.setInfo('video', info)
        
        li.setUniqueIDs({
            'imdb': show_data.get('imdb_id', ''),
            'tmdb': str(tvshow_tmdb_id)
        })
        
        li.setProperty('original_title', show_data.get('original_title', ''))
        
        # Prioriza a fanart do episódio (still_path) se disponível
        if item_data_for_scraper.get('episode_fanart'):
            final_fanart = item_data_for_scraper['episode_fanart']
        else:
            final_fanart = show_data.get('backdrop')
        
        art = {
            'thumb': item_data_for_scraper['episode_poster'],
            'icon': item_data_for_scraper['episode_poster'],
            'poster': item_data_for_scraper['poster'],
            'fanart': final_fanart,      # Background do episódio
            'landscape': final_fanart,   # Modo parede/paisagem do episódio
            'tvshow.poster': show_data.get('poster'),
            'tvshow.fanart': show_data.get('backdrop'),
            'tvshow.clearlogo': show_data.get('clearlogo')
        }
        li.setArt(art)
        li.setProperty('IsPlayable', 'true')

        url = get_url(
            action='find_and_play_episode', 
            item_data=json.dumps(item_data_for_scraper)
        )
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)

def _fetch_tmdb_season_details(tmdb_id, season_number):
    from .tmdb_api import get_session, TMDB_LANG
    """Busca os detalhes de uma temporada direto do TMDB."""
    if not TMDB_API_KEY:
        return []
        
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG
    }
    try:
        response = get_session().get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Retorna apenas os episódios (mantendo compatibilidade)
        return data.get('episodes', [])
    except Exception as e:
        xbmc.log(f"[ERRO TMDB] Falha ao buscar temporada {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []


# --- LISTAGENS DE SÉRIES (MENUS) ---

@with_view_mode('genres', is_menu=True)
def list_tvshows_genres():
    from .tmdb_api import get_genres_list
    from .icons import get_genre_icon, get_icon_url
    """Cria e exibe a lista de Gêneros de Séries usando TMDB."""
    xbmcplugin.setPluginCategory(HANDLE, 'Gen Serial')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'genres')
    
    genres = get_genres_list('tv')
    
    for genre in genres:
        li = xbmcgui.ListItem(label=genre['name'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        # NOVO: Adicionar ícone do gênero
        icon_id = get_genre_icon(genre['name'])
        icon_url = get_icon_url(icon_id)
        if icon_url:
            li.setArt({'icon': icon_url})
        url = get_url(action='list_tvshows_by_genre', genre_id=genre['id'], genre_name=genre['name'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('years', is_menu=True)
def list_tvshows_years():
    from .icons import get_year_icon, get_icon_url
    """Cria e exibe a lista de Anos de Séries (TMDB)."""
    xbmcplugin.setPluginCategory(HANDLE, 'Seriale pe Ani')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'years')
    
    import datetime
    current_year = datetime.datetime.now().year
    
    # NOVO: Obter ícone de ano
    year_icon_id = get_year_icon()
    year_icon_url = get_icon_url(year_icon_id)
    
    for year in range(current_year, 1900, -1):
        li = xbmcgui.ListItem(label=str(year))
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        # NOVO: Adicionar ícone de ano
        if year_icon_url:
            li.setArt({'icon': year_icon_url})
        url = get_url(action='list_tvshows_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_year(year, page=1):
    from .tmdb_api import fetch_discover
    year = int(year)
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, f"Serial pe {year}")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_discover('tv', page=page, first_air_date_year=year)
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('files', is_menu=True)
def list_providers():
    xbmcplugin.setPluginCategory(HANDLE, "Provideri")
    fanart_addon = ADDON.getAddonInfo('fanart')

    providers = db.get_all_unique_providers()

    for provider_name in providers:
        li = xbmcgui.ListItem(label=provider_name)
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})

        logo_file = PROVIDER_LOGOS.get(provider_name)
        if logo_file:
            logo_path = os.path.join(
                ADDON_PATH, 'resources', 'logos', logo_file
            )
            li.setArt({
                'thumb': logo_path,
                'icon': logo_path,
                'poster': logo_path
            })

        url = get_url(
            action='list_tvshows_by_provider',
            provider=provider_name
        )

        xbmcplugin.addDirectoryItem(
            HANDLE, url, li, isFolder=True
        )

    xbmcplugin.endOfDirectory(HANDLE)



# --- LISTAGENS DE CONTEÚDO (SÉRIES) ---

@with_view_mode('tvshows')
def list_tvshows_by_genre(genre_id=None, genre_name=None, page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, genre_name or "Gen")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    page = int(page)
    shows = fetch_discover('tv', page=page, with_genres=genre_id)
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_genre', genre_id=genre_id, genre_name=genre_name)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_provider(provider, page=1):
    xbmcplugin.setPluginCategory(HANDLE, provider)
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_provider(provider, page, DEFAULT_ITEMS_PER_PAGE)
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_provider', provider=provider)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_popularity(page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, "Cele Mai Populare")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    page = int(page)
    shows = fetch_discover('tv', page=page, sort_by='popularity.desc')
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
    
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_upcoming_tvshows(page=1):
    from .tmdb_api import fetch_upcoming_tvshows
    """Lista séries que serão lançadas em breve."""
    xbmcplugin.setPluginCategory(HANDLE, "Seriale Nelansate")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    page = int(page)
    shows = fetch_upcoming_tvshows(page=page)
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_upcoming_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


def list_animes():
    """Cria e exibe o menu da seção 'Animes' com submenus do Jactook."""
    xbmcplugin.setPluginCategory(HANDLE, 'Animatie')
    fanart_addon = ADDON.getAddonInfo('fanart')
    
    from .icons import get_icon_url
    menu_items = [
        {'title': 'Cautare', 'action': 'search', 'icon': 'owsADQ4'},
        {'title': 'Populare', 'action': 'list_anime_popular', 'icon': 'ngkznpf'},
        {'title': 'Listate Recent', 'action': 'list_anime_recent', 'icon': 's4krx5q'},
        {'title': 'In Emisie', 'action': 'list_anime_on_the_air', 'icon': 'rVq7so0'},
        {'title': 'Pe Ani', 'action': 'list_anime_years', 'icon': 'fN4GQmO'},  # Ícone de calendário do IMDb
        {'title': 'Gen', 'action': 'list_anime_genres', 'icon': '6QpJbS0'},
        {'title': 'Tendinte (Trakt)', 'action': 'trakt_anime_trending', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
        {'title': 'Cele Mai Vizionate (Trakt)', 'action': 'trakt_anime_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    ]

    for item in menu_items:
        li = xbmcgui.ListItem(label=item['title'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        icon = item['icon']
        # NOVO: Suporta IDs de ícones do IMDb
        if isinstance(icon, str) and len(icon) < 15 and not icon.endswith('.png'):
            # É um ID de ícone, converte para URL
            icon_url = get_icon_url(icon)
            li.setArt({'thumb': icon_url, 'icon': icon_url})
        else:
            # É um caminho local
            icon_file = os.path.join(ICON_PATH, icon)
            li.setArt({'thumb': icon_file, 'icon': icon_file})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)



@with_view_mode('tvshows')
def list_anime_popular(page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, "Animatii Populare")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, sort_by='popularity.desc')
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_popular')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_anime_recent(page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, "Animatii Recente")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, sort_by='first_air_date.desc')
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_recent')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_anime_on_the_air(page=1):
    from .tmdb_api import fetch_anime_discover
    from datetime import datetime, timedelta
    xbmcplugin.setPluginCategory(HANDLE, "Animatii lansate ")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    now = datetime.now()
    future = now + timedelta(days=7)
    air_date_gte = now.strftime('%Y-%m-%d')
    air_date_lte = future.strftime('%Y-%m-%d')
    
    shows = fetch_anime_discover('tv', page=page, **{'air_date.gte': air_date_gte, 'air_date.lte': air_date_lte})
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_on_the_air')
    xbmcplugin.endOfDirectory(HANDLE)

def list_anime_years():
    from .icons import get_year_icon, get_icon_url
    xbmcplugin.setPluginCategory(HANDLE, 'Animatii pe Ani')
    fanart_addon = ADDON.getAddonInfo('fanart')
    import datetime
    current_year = datetime.datetime.now().year
    # NOVO: Obter ícone de ano
    year_icon_id = get_year_icon()
    year_icon_url = get_icon_url(year_icon_id)
    for year in range(current_year, 1960, -1):
        li = xbmcgui.ListItem(label=str(year))
        if fanart_addon: li.setArt({'fanart': fanart_addon})
        # NOVO: Adicionar ícone de ano
        if year_icon_url:
            li.setArt({'icon': year_icon_url})
        url = get_url(action='list_anime_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_anime_by_year(year, page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, f"Animatii din {year}")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, first_air_date_year=year)
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)

def list_anime_genres():
    from .tmdb_api import get_genres_list
    from .icons import get_genre_icon, get_icon_url
    xbmcplugin.setPluginCategory(HANDLE, 'Genuri de Animatie')
    fanart_addon = ADDON.getAddonInfo('fanart')
    genres = get_genres_list('tv')
    for genre in genres:
        li = xbmcgui.ListItem(label=genre['name'])
        if fanart_addon: li.setArt({'fanart': fanart_addon})
        # NOVO: Adicionar ícone do gênero
        icon_id = get_genre_icon(genre['name'])
        icon_url = get_icon_url(icon_id)
        if icon_url:
            li.setArt({'icon': icon_url})
        url = get_url(action='list_anime_by_genre', genre_id=genre['id'], genre_name=genre['name'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_anime_by_genre(genre_id=None, genre_name=None, page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, genre_name or "Gen")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, with_genres=genre_id)
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_by_genre', genre_id=genre_id, genre_name=genre_name)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_kids_tvshows(page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, "Copii")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    page = int(page)
    # Gênero 10762 é Kids no TMDB
    shows = fetch_discover('tv', page=page, with_genres='10762')
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_kids_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_trending_tvshows(page=1):
    """Lista as séries em alta consumindo a API do TMDB."""
    from .tmdb_api import fetch_trending_tvshows
    
    xbmcplugin.setPluginCategory(HANDLE, "Tendinte")
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    page = int(page)
    shows = fetch_trending_tvshows(page)

    items_to_add = []
    for show_data in shows:
        items_to_add.append(_create_show_tuple(show_data))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(shows, page, action='list_trending_tvshows')
    
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_tvshows_by_streaming(provider_id, provider_name, region='BR', page=1):
    """Lista séries de uma plataforma de streaming específica."""
    from .tmdb_api import fetch_discover
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, provider_name)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = fetch_discover('tv', page=page, with_watch_providers=provider_id, watch_region=region)
    
    items = []
    for show in shows:
        items.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(shows, page, action='list_tvshows_by_streaming', provider_id=provider_id, provider_name=provider_name, region=region)
    xbmcplugin.endOfDirectory(HANDLE)
