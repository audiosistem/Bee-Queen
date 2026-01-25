# -*- coding: utf-8 -*-
# Em: resources/lib/movies.py - VERSÃO OTIMIZADA E FUNCIONAL

import json
import xbmc
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

from .utils import create_video_item_with_library, with_view_mode


# --- Configurações gerais ---
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

# --- Cache e Detecção de Dispositivo ---
_LISTITEM_CACHE = {}
_MAX_CACHE_SIZE = 30

def is_slow_device():
    """Detecta dispositivos de baixo desempenho (MXQ, TCL P8M, etc)"""
    model = xbmc.getInfoLabel('System.Model').lower()
    slow_models = ['mxq', 'p8m', 'x96', 'h96', 'tanix', 'tx3', 't95', 'beelink', 'mecool']
    return any(dev in model for dev in slow_models)

def get_items_per_page():
    """Retorna número de itens por página baseado no dispositivo"""
    base_pages = int(ADDON.getSetting("pages"))
    if is_slow_device():
        return min(base_pages, 20)  # Máximo 20 em dispositivos fracos
    return base_pages

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

def _create_movie_item_tuple(movie):
    """Cria a tupla padrão para todos os dispositivos usando a função completa"""
    # li já vem com os IDs corretos no setInfo se você atualizou o utils.py
    li = create_video_item_with_library(movie, media_type='movie')
    
    # Lógica do Dialog de Detalhes (Desativado por padrão)
    if False: # ADDON.getSettingBool("movie.enable_details"):
        item_data = {
            "title": movie.get('title', ''),
            "original_title": movie.get('original_title', ''), # ADICIONADO
            "clearlogo": movie.get('clearlogo', ''),
            "poster": movie.get('poster', ''),
            "synopsis": movie.get('synopsis', ''),
            "backdrop": movie.get('backdrop', ''),
            "year": movie.get('year', 0),
            "runtime": movie.get('runtime', 0),
            "collection": movie.get('collection', ''),
            "rating": float(movie.get('rating', 0)),
            "genre": ', '.join(movie.get('genres', [])),
            "tmdb_id": movie.get('tmdb_id'),
            "imdb_id": movie.get('imdb_id', ''), # ESSENCIAL
            "media_type": 'movie',
            "providers": json.dumps(movie.get('providers', [])) if movie.get('providers') else '[]',
            "streams": movie.get('streams', []),
            "popularity_updated": movie.get('popularity_updated', '') 
        }
        # Separadores compactos para economizar memória na URL
        url = get_url(action='show_details', data=json.dumps(item_data, separators=(',', ':')))
    else:
        # Play direto
        url = get_url(
            action='find_sources',
            tmdb_id=str(movie.get('tmdb_id', '')),
            imdb_id=movie.get('imdb_id', ''),
            media_type='movie',
            title=movie.get('title', ''),
            year=movie.get('year', ''),
            original_title=movie.get('original_title', ''),
            clearlogo=movie.get('clearlogo', ''),
            fanart=movie.get('fanart', ''),
            backdrop=movie.get('backdrop', ''),
            poster=movie.get('poster', '')
        )
    
    return (url, li, False)


def _get_cached_listitem(movie):
    """Retorna um ListItem com todas as propriedades necessárias, garantindo strings."""
    cache_key = f"{movie.get('tmdb_id', '')}_{movie.get('year', '')}"
    
    if cache_key in _LISTITEM_CACHE:
        return _LISTITEM_CACHE[cache_key]
    
    li = xbmcgui.ListItem(label=movie.get('title', ''))
    if fanart_addon:
        li.setArt({'fanart': fanart_addon})

    # Artes
    li.setArt({
        'thumb': movie.get('poster', '') or '',
        'fanart': movie.get('fanart', movie.get('backdrop', '')) or '',
        'clearlogo': movie.get('clearlogo', '') or '',
        'poster': movie.get('poster', '') or '',
        'backdrop': movie.get('backdrop', '') or ''
    })
    
    # Propriedades internas — todas convertidas para str
    li.setProperty('tmdb_id', str(movie.get('tmdb_id', '')))
    li.setProperty('imdb_id', str(movie.get('imdb_id', '')))
    li.setProperty('media_type', str(movie.get('media_type', 'movie')))
    li.setProperty('title', str(movie.get('title', '')))
    li.setProperty('original_title', str(movie.get('original_title', '')))
    li.setProperty('clearlogo', str(movie.get('clearlogo', '')))
    li.setProperty('fanart', str(movie.get('fanart', movie.get('backdrop', ''))))
    li.setProperty('backdrop', str(movie.get('backdrop', '')))
    li.setProperty('poster', str(movie.get('poster', '')))
    li.setProperty('synopsis', str(movie.get('synopsis', '')))
    li.setProperty('year', str(movie.get('year', '0000')))
    li.setProperty('rating', str(movie.get('rating', 0.0)))
    li.setProperty('runtime', str(movie.get('runtime', 0)))
    li.setProperty('genres', ",".join(map(str, movie.get('genres', []))))
    li.setProperty('providers', ",".join(map(str, movie.get('providers', []))))
    li.setProperty('popularity_updated', str(movie.get('popularity_updated', '')))

    # Salva no cache
    if len(_LISTITEM_CACHE) < _MAX_CACHE_SIZE:
        _LISTITEM_CACHE[cache_key] = li
    
    return li

# --- MENUS ---

def show_movies_menu(menu_structure):
    from .icons import get_icon_url
    """Cria e exibe o menu da seção 'Filmes'."""
    xbmcplugin.setPluginCategory(HANDLE, 'Filme')
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
    """Lista as plataformas de streaming para filmes."""
    from .constants import STREAMING_PLATFORMS
    xbmcplugin.setPluginCategory(HANDLE, 'Filme pentru Streaming')
    fanart_addon = ADDON.getAddonInfo('fanart')
    
    for platform in STREAMING_PLATFORMS['movie']:
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
            
        url = get_url(action='list_movies_by_streaming', provider_id=platform['id'], provider_name=platform['name'], region=platform.get('region', 'BR'))
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_popularity(page=1):
    """Lista filmes por popularidade."""
    from .tmdb_api import fetch_popular_movies
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Filme Populare')
    xbmcplugin.setContent(HANDLE, 'movies')
    
    movies = fetch_popular_movies(page=page)
    
    items = []
    for movie in movies:
        items.append(_create_movie_item_tuple(movie))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(movies, page, action='list_movies_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_top_rated(page=1):
    """Lista filmes melhor avaliados."""
    from .tmdb_api import fetch_top_rated_movies
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Top Rated')
    xbmcplugin.setContent(HANDLE, 'movies')
    
    movies = fetch_top_rated_movies(page=page)
    
    items = []
    for movie in movies:
        items.append(_create_movie_item_tuple(movie))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(movies, page, action='list_movies_top_rated')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_now_playing(page=1):
    """Lista filmes em exibição nos cinemas."""
    from .tmdb_api import fetch_now_playing_movies
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Acum in Cinema')
    xbmcplugin.setContent(HANDLE, 'movies')
    
    movies = fetch_now_playing_movies(page=page)
    
    items = []
    for movie in movies:
        items.append(_create_movie_item_tuple(movie))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(movies, page, action='list_movies_now_playing')
    xbmcplugin.endOfDirectory(HANDLE)

def add_next_page_item(items_on_current_page, current_page, **kwargs):
    """Adiciona o item 'Próxima Página' a uma lista se houver mais itens."""
    num_items = len(items_on_current_page)
    items_per_page = int(ADDON.getSetting("pages") or 20)
    
    xbmc.log(f"[Cinebox] Paginação: {num_items} itens na página {current_page}, action={kwargs.get('action', 'unknown')}", xbmc.LOGINFO)
    
    # Se o número de itens for igual ou maior que o esperado por página, mostra próxima
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

@with_view_mode('genres', is_menu=True)
def list_genres():
    from .tmdb_api import get_genres_list
    from .icons import get_genre_icon, get_icon_url
    """Cria e exibe a lista de Gêneros de Filmes usando TMDB."""
    xbmcplugin.setPluginCategory(HANDLE, 'Gêneros')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'genres')
    
    genres = get_genres_list('movie')
    
    for genre in genres:
        li = xbmcgui.ListItem(label=genre['name'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        # NOVO: Adicionar ícone do gênero
        icon_id = get_genre_icon(genre['name'])
        icon_url = get_icon_url(icon_id)
        if icon_url:
            li.setArt({'icon': icon_url})
        url = get_url(action='list_movies_by_genre', genre_id=genre['id'], genre_name=genre['name'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('years', is_menu=True)
def list_years():
    from .icons import get_year_icon, get_icon_url
    """Cria e exibe a lista de Anos (TMDB)."""
    xbmcplugin.setPluginCategory(HANDLE, 'Ani')
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
        url = get_url(action='list_movies_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies', is_menu=True)
def list_collections(page=1):
    from .tmdb_api import fetch_popular_collections
    from .db.db import db_instance as db
    
    page = int(page)
    
    # Se for a página 1, limpa o cache de duplicatas no banco de dados
    if page == 1:
        try:
            conn = db._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM collections_meta WHERE collection_name LIKE 'col_shown_%'")
            conn.commit()
        except:
            pass

    xbmcplugin.setPluginCategory(HANDLE, "Colectii")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    # Busca coleções populares diretamente do TMDB
    collections_data = fetch_popular_collections(page)
    
    if not collections_data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items = []
    from .utils import get_image_resolutions, scale_tmdb
    res = get_image_resolutions()
    
    for col in collections_data:
        name = col.get('collection')
        poster = col.get('poster')
        fanart = col.get('backdrop')
        
        li = xbmcgui.ListItem(label=name)
        li.setArt({
            'poster': scale_tmdb(poster, res['poster']),
            'icon': scale_tmdb(poster, res['poster']),
            'thumb': scale_tmdb(poster, res['poster']),
            'fanart': scale_tmdb(fanart, res['backdrop'])
        })
        
        url = get_url(action='list_movies_by_collection', collection=name)
        items.append((url, li, True))

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    # Sempre mostra próxima página para coleções do TMDB
    # CORREÇÃO: items_per_page deve ser 1 para que o botão sempre apareça se houver dados
    add_next_page_item(collections_data, page, action='list_collections', items_per_page=1)
    xbmcplugin.endOfDirectory(HANDLE)

# --- LISTAGENS DE FILMES ---

@with_view_mode('movies')
def list_movies_by_genre(genre_id=None, genre_name=None, page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, genre_name or "Gen")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    page = int(page)
    movies = fetch_discover('movie', page=page, with_genres=genre_id)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_movies_by_genre', genre_id=genre_id, genre_name=genre_name)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_year(year, page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, str(year))
    xbmcplugin.setContent(HANDLE, 'movies')
    
    page = int(page)
    movies = fetch_discover('movie', page=page, primary_release_year=year)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_movies_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_collection(collection_name, page=1):
    from .db.db import db_instance as db
    from .tmdb_api import get_collection_movies
    
    xbmcplugin.setPluginCategory(HANDLE, collection_name)
    xbmcplugin.setContent(HANDLE, 'movies')
    
    # 1. Busca filmes locais
    movies = db.get_movies_by_collection(collection_name)
    
    # 2. Busca a coleção completa no TMDB para garantir que nada falte
    # Como as coleções agora vêm do TMDB, precisamos garantir que todos os filmes daquela coleção existam
    xbmc.log(f"[Cinebox] Sincronizando coleção '{collection_name}' com TMDB...", xbmc.LOGINFO)
    tmdb_movies = get_collection_movies(collection_name)
    
    if tmdb_movies:
        # Adiciona os filmes novos ao banco para futuras consultas (scrapers, etc)
        db.add_movies_bulk(tmdb_movies)
        # Usa a lista do TMDB que é sempre a mais completa e atualizada
        movies = tmdb_movies
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    # Coleções geralmente não têm muitas páginas, mas mantemos por segurança
    add_next_page_item(movies, page, action='list_movies_by_collection', collection=collection_name)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_rating(page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, "Dupa Rating")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    page = int(page)
    movies = fetch_discover('movie', page=page, sort_by='vote_average.desc', **{'vote_count.gte': 500})
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_movies_by_rating')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_popularity(page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, "Cele mai Populare")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    page = int(page)
    movies = fetch_discover('movie', page=page, sort_by='popularity.desc')

    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_movies_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_4k_movies(page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, "Filmes in 4K")
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_4k_movies(page, items_per_page)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_4k_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_upcoming_movies(page=1):
    from .tmdb_api import fetch_upcoming_movies
    """Lista filmes que serão lançados em breve."""
    xbmcplugin.setPluginCategory(HANDLE, "Filme nelansate")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    page = int(page)
    movies = fetch_upcoming_movies(page=page)

    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_upcoming_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_movies_by_revenue(page=1):
    from .tmdb_api import fetch_discover
    """Lista filmes ordenados pelas maiores bilheterias (TMDB)."""
    xbmcplugin.setPluginCategory(HANDLE, "Dupa Incasari")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    page = int(page)
    movies = fetch_discover('movie', page=page, sort_by='revenue.desc')
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_movies_by_revenue')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_provider(provider, page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, f"{provider}")
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'movies')

    items_per_page = get_items_per_page()
    movies = db.get_movies_by_provider(provider, page, items_per_page)

    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    if items_to_add:
        xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    add_next_page_item(movies, page, action='list_movies_by_provider', provider=provider)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_trending_movies(page=1):
    from .db import db
    from .tmdb_api import fetch_trending_movies
    xbmcplugin.setPluginCategory(HANDLE, "Tendinte")
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'movies')
    
    # Busca os dados da API
    movies = fetch_trending_movies(page)

    items_to_add = []
    for m in movies:
        items_to_add.append(_create_movie_item_tuple(m))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_trending_movies')
    xbmcplugin.endOfDirectory(HANDLE)
@with_view_mode('movies')
def list_movies_by_streaming(provider_id, provider_name, region='BR', page=1):
    """Lista filmes de uma plataforma de streaming específica."""
    from .tmdb_api import fetch_discover
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, provider_name)
    xbmcplugin.setContent(HANDLE, 'movies')
    
    movies = fetch_discover('movie', page=page, with_watch_providers=provider_id, watch_region=region)
    
    items = []
    for movie in movies:
        items.append(_create_movie_item_tuple(movie))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(movies, page, action='list_movies_by_streaming', provider_id=provider_id, provider_name=provider_name, region=region)
    xbmcplugin.endOfDirectory(HANDLE)
