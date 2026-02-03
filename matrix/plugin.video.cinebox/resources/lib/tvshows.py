# -*- coding: utf-8 -*-
# In: resources/lib/tvshows.py

import json
import os
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

# Keep only the db and utils that are lightweight and essential for the listings
from .utils import create_video_item_with_library, with_view_mode

# Common settings and functions
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
    """Creates a plugin URL for an action."""
    return f"{BASE_URL}?{urlencode(kwargs)}"


# --- ✅ NEW AUXILIARY FUNCTIONS ---

def _prepare_details_data(item_data):
    """Prepares a dictionary with item data for the details screen URL."""
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
    """Creates the tuple (url, listitem, is_folder) for series (TV Shows) using the full function."""
    li = create_video_item_with_library(show_data, 'tvshow')
    
    if False: # ADDON.getSettingBool("tvshow.enable_details"):
        details_data = _prepare_details_data(show_data)
        url = get_url(action='show_details', data=json.dumps(details_data, ensure_ascii=False))
        is_folder = False
    else:
        url = get_url(action='list_seasons', tvshow_tmdb_id=show_data.get('tmdb_id'))
        is_folder = True

    return (url, li, is_folder)


# --- SERIES NAVIGATION FUNCTIONS ---

def show_tvshows_menu(menu_structure):
    from .icons import get_icon_url
    """Creates and displays the menu for the 'TV Shows' section."""
    xbmcplugin.setPluginCategory(HANDLE, 'TV Shows')
    fanart_addon = ADDON.getAddonInfo('fanart')
    for item in menu_structure:
        li = xbmcgui.ListItem(label=item['title'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        icon = item.get('icon')
        if icon:
            # NEW: Supports IMDb icon IDs
            if isinstance(icon, str) and len(icon) < 15 and not icon.endswith('.png'):
                # It's an icon ID, converts to URL
                icon_url = get_icon_url(icon)
                li.setArt({'thumb': icon_url, 'icon': icon_url})
            else:
                # It's a local path
                li.setArt({'thumb': icon})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_streaming_platforms():
    """List streaming platforms for series."""
    from .constants import STREAMING_PLATFORMS
    xbmcplugin.setPluginCategory(HANDLE, 'TV Shows by Streaming')
    fanart_addon = ADDON.getAddonInfo('fanart')
    
    for platform in STREAMING_PLATFORMS['tv']:
        li = xbmcgui.ListItem(label=platform['name'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        # Use TMDB (JustWatch) logo as on IMDB
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
    """List series by popularity."""
    from .tmdb_api import fetch_popular_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Popular TV Shows')
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
    """List top rated series."""
    from .tmdb_api import fetch_top_rated_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Best Rated')
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
    """List series that air today."""
    from .tmdb_api import fetch_airing_today_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'Pass Today')
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
    """List series that are currently on air."""
    from .tmdb_api import fetch_on_the_air_tvshows
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, 'On Air (Week)')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = fetch_on_the_air_tvshows(page=page)
    
    items = []
    for show in shows:
        items.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items)
    add_next_page_item(shows, page, action='list_tvshows_on_the_air')
    xbmcplugin.endOfDirectory(HANDLE)


def add_next_page_item(items_on_current_page, current_page, **kwargs):
    """Adds 'Next Page' item to a list if there are more items."""
    num_items = len(items_on_current_page)
    items_per_page = int(ADDON.getSetting("pages") or 20)
    xbmc.log(f"[Cinebox] Pagination: {num_items} items on the page {current_page}, action={kwargs.get('action', 'unknown')}", xbmc.LOGINFO)
    
    if num_items >= items_per_page:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Next Page")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        li_next.setInfo('video', {'plot': f'Go to page {current_page + 1}'})

        next_page_args = kwargs.copy()
        next_page_args['page'] = current_page + 1
        next_page_url = get_url(**next_page_args)
        
        xbmc.log(f"[Cinebox] Adding Next Page Button: {next_page_url}", xbmc.LOGINFO)
        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, li_next, isFolder=True)
    else:
        xbmc.log(f"[Cinebox] There is no next page (just {num_items} items)", xbmc.LOGINFO)

def list_seasons(tvshow_tmdb_id):
    from .tmdb_api import fetch_show_details 
    from .db.db import db_instance as db
    """List seasons using TMDB exclusively."""
    # 1. Search SERIES data in local DB or TMDB
    show = db.get_tvshow_by_id(tvshow_tmdb_id)
    
    # If it is not in the local DB, it searches the TMDB to ensure we have the basic data
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

    # 2. Search seasons from TMDB (fetch_show_details already returns seasons_data)
    show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
    if not show_details_tmdb:
        xbmcplugin.endOfDirectory(HANDLE)
        return
        
    seasons_data_list = show_details_tmdb.get('seasons_data', [])
    
    # Force hiding special seasons (Season 0)
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
            
        tmdb_season_name = season_data.get('name', f"Season {season_number}")
        air_date = season_data.get('air_date')
        
        if air_date and air_date > current_date:
            # Format date for title in red
            air_date_br = air_date
            if air_date and "-" in air_date:
                parts = air_date.split("-")
                air_date_br = "%s/%s/%s" % (parts[2], parts[1], parts[0])
            tmdb_season_name = f"[COLOR red]{tmdb_season_name} ({air_date_br})[/COLOR]"
        
        # Prepare data for create_video_item
        if 'poster' not in season_data and season_data.get('poster_path'):
             season_data['poster'] = f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}"
        
        season_data['title'] = tmdb_season_name
        season_data['label'] = tmdb_season_name
        
        li = create_video_item_with_library(season_data, 'season', show_data=show)
        
        # Adds season-specific art
        season_poster_path = season_data.get('poster_path')
        
        # Poster: use the season poster if available, otherwise use the series poster
        if season_poster_path:
            season_poster = f"https://image.tmdb.org/t/p/w500{season_poster_path}"
        else:
            season_poster = show.get('poster')
        
        # Fanart/Background: always uses the series' backdrop (16:9/landscape format)
        # TMDB does not provide specific backdrop for seasons
        season_fanart = show.get('backdrop')
        
        li.setArt({
            'fanart': season_fanart,
            'landscape': season_fanart,
            'poster': season_poster,
            'thumb': season_poster,
            'icon': season_poster
        })
        
        from .sinopse import enriquecer_sinopse_episodio
        # Fallback: if the season doesn't have a synopsis, use the one from the series
        season_plot = season_data.get('overview')
        if not season_plot or season_plot.strip() == "":
            season_plot = show.get('synopsis') or show.get('plot') or "Synopsis not available."
            
        # Ensures season_data has the necessary fields for enrichment
        # fetch_show_details already returns seasons_data with air_date, episode_count, vote_average
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
    """Lists episodes using TMDB exclusively."""
    # 1. Get SERIES data
    show_data = db.get_tvshow_by_id(tvshow_tmdb_id)
    if not show_data:
        show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
        if show_details_tmdb:
            show_data = show_details_tmdb
        else:
            xbmcplugin.endOfDirectory(HANDLE)
            return

    xbmcplugin.setPluginCategory(HANDLE, f"{show_data.get('title')} - Season {season_number}")
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'episodes')

    # 2. Search TMDB episodes
    tmdb_episodes = _fetch_tmdb_season_details(tvshow_tmdb_id, season_number)
    
    if not tmdb_episodes:
        xbmcgui.Dialog().ok("Warning", "No episodes found.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # 3. Loop to create items
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    for ep_data_tmdb in tmdb_episodes:
        ep_number = ep_data_tmdb.get('episode_number')
        ep_name = ep_data_tmdb.get('name')
        air_date = ep_data_tmdb.get('air_date')
        
        # Check if the episode has already been released
        is_unaired = False
        if not air_date or air_date > current_date:
            is_unaired = True
            
        if is_unaired:
            # Format date for title in red
            air_date_br = air_date
            if air_date and "-" in air_date:
                parts = air_date.split("-")
                air_date_br = "%s/%s/%s" % (parts[2], parts[1], parts[0])
            ep_title = f"[COLOR red]Episode.{ep_number} ({air_date_br})[/COLOR]"
        else:
            ep_title = f"Episode.{ep_number}"
        
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
        
        # Prioritize episode fanart (still_path) if available
        if item_data_for_scraper.get('episode_fanart'):
            final_fanart = item_data_for_scraper['episode_fanart']
        else:
            final_fanart = show_data.get('backdrop')
        
        art = {
            'thumb': item_data_for_scraper['episode_poster'],
            'icon': item_data_for_scraper['episode_poster'],
            'poster': item_data_for_scraper['poster'],
            'fanart': final_fanart,      # Episode background
            'landscape': final_fanart,   # Episode wall/landscape mode
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
    """Search for season details directly from TMDB."""
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
        # Returns only episodes (maintaining compatibility)
        return data.get('episodes', [])
    except Exception as e:
        xbmc.log(f"[TMDB ERROR] Failed to fetch Season {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []


# --- SERIES LISTINGS (MENUS) ---

@with_view_mode('genres', is_menu=True)
def list_tvshows_genres():
    from .tmdb_api import get_genres_list
    from .icons import get_genre_icon, get_icon_url
    """Creates and displays the list of TV Shows Genres using TMDB."""
    xbmcplugin.setPluginCategory(HANDLE, 'Genres of TV Shows')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'genres')
    
    genres = get_genres_list('tv')
    
    for genre in genres:
        li = xbmcgui.ListItem(label=genre['name'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        # NEW: Add genre icon
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
    """Creates and displays the list of Years of TV Shows (TMDB)."""
    xbmcplugin.setPluginCategory(HANDLE, 'TV Shows by Year')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'years')
    
    import datetime
    current_year = datetime.datetime.now().year
    
    # NEW: Get year icon
    year_icon_id = get_year_icon()
    year_icon_url = get_icon_url(year_icon_id)
    
    for year in range(current_year, 1900, -1):
        li = xbmcgui.ListItem(label=str(year))
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        # NEW: Add year icon
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
    xbmcplugin.setPluginCategory(HANDLE, f"TV Shows de {year}")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_discover('tv', page=page, first_air_date_year=year)
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('files', is_menu=True)
def list_providers():
    xbmcplugin.setPluginCategory(HANDLE, "Providers")
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



# --- CONTENT LISTINGS (SERIES) ---

@with_view_mode('tvshows')
def list_tvshows_by_genre(genre_id=None, genre_name=None, page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, genre_name or "Gender")
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
    xbmcplugin.setPluginCategory(HANDLE, "Most Popular")
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
    """List series that will be released soon."""
    xbmcplugin.setPluginCategory(HANDLE, "Upcoming TV Shows")
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
    """Creates and displays 'Anime' section menu with Jactook submenus."""
    xbmcplugin.setPluginCategory(HANDLE, 'Anime')
    fanart_addon = ADDON.getAddonInfo('fanart')
    
    from .icons import get_icon_url
    menu_items = [
        {'title': 'Search', 'action': 'search', 'icon': 'owsADQ4'},
        {'title': 'Popular', 'action': 'list_anime_popular', 'icon': 'ngkznpf'},
        {'title': 'Recently Added', 'action': 'list_anime_recent', 'icon': 's4krx5q'},
        {'title': 'In the Air', 'action': 'list_anime_on_the_air', 'icon': 'rVq7so0'},
        {'title': 'Per year', 'action': 'list_anime_years', 'icon': 'fN4GQmO'},  # IMDb calendar icon
        {'title': 'Genres', 'action': 'list_anime_genres', 'icon': '6QpJbS0'},
        {'title': 'Trends (Trakt)', 'action': 'trakt_anime_trending', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
        {'title': 'Most Watched (Trakt)', 'action': 'trakt_anime_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    ]

    for item in menu_items:
        li = xbmcgui.ListItem(label=item['title'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        icon = item['icon']
        # NEW: Supports IMDb icon IDs
        if isinstance(icon, str) and len(icon) < 15 and not icon.endswith('.png'):
            # It's an icon ID, converts to URL
            icon_url = get_icon_url(icon)
            li.setArt({'thumb': icon_url, 'icon': icon_url})
        else:
            # It's a local path
            icon_file = os.path.join(ICON_PATH, icon)
            li.setArt({'thumb': icon_file, 'icon': icon_file})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)



@with_view_mode('tvshows')
def list_anime_popular(page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, "Popular Animes")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, sort_by='popularity.desc')
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_popular')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_anime_recent(page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, "Recent Animes")
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
    xbmcplugin.setPluginCategory(HANDLE, "Animes On Air")
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
    xbmcplugin.setPluginCategory(HANDLE, 'Animes by Year')
    fanart_addon = ADDON.getAddonInfo('fanart')
    import datetime
    current_year = datetime.datetime.now().year
    # NEW: Get year icon
    year_icon_id = get_year_icon()
    year_icon_url = get_icon_url(year_icon_id)
    for year in range(current_year, 1960, -1):
        li = xbmcgui.ListItem(label=str(year))
        if fanart_addon: li.setArt({'fanart': fanart_addon})
        # NEW: Add year icon
        if year_icon_url:
            li.setArt({'icon': year_icon_url})
        url = get_url(action='list_anime_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_anime_by_year(year, page=1):
    from .tmdb_api import fetch_anime_discover
    xbmcplugin.setPluginCategory(HANDLE, f"Animes de {year}")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, first_air_date_year=year)
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)

def list_anime_genres():
    from .tmdb_api import get_genres_list
    from .icons import get_genre_icon, get_icon_url
    xbmcplugin.setPluginCategory(HANDLE, 'Anime Genres')
    fanart_addon = ADDON.getAddonInfo('fanart')
    genres = get_genres_list('tv')
    for genre in genres:
        li = xbmcgui.ListItem(label=genre['name'])
        if fanart_addon: li.setArt({'fanart': fanart_addon})
        # NEW: Add genre icon
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
    xbmcplugin.setPluginCategory(HANDLE, genre_name or "Gender")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = fetch_anime_discover('tv', page=page, with_genres=genre_id)
    items_to_add = [ _create_show_tuple(s) for s in shows ]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_anime_by_genre', genre_id=genre_id, genre_name=genre_name)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_kids_tvshows(page=1):
    from .tmdb_api import fetch_discover
    xbmcplugin.setPluginCategory(HANDLE, "Childrens")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    page = int(page)
    # Genre 10762 is Kids on TMDB
    shows = fetch_discover('tv', page=page, with_genres='10762')
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_kids_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_trending_tvshows(page=1):
    """Lists the trending series consuming the TMDB API."""
    from .tmdb_api import fetch_trending_tvshows
    
    xbmcplugin.setPluginCategory(HANDLE, "Tendencies")
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
    """Lists series from a specific streaming platform."""
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
