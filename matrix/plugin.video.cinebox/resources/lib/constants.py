# -*- coding: utf-8 -*-

import os
import xbmcaddon

# --- Path Configuration ---
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

MAIN_MENU = [
    {
        'title': 'Movies',
        'action': 'movies_menu',
        'icon': 'pmyCOx7',
        'plot': 'Movies from the TMDB catalog and public Trakt lists.'
    },

    {
        'title': 'TV Shows',
        'action': 'tvshows_menu',
        'icon': 'R3NEEJl',
        'plot': 'TV Shows from TMDB and public lists from Trakt.'
    },
    {
        'title': 'Crunchyroll',
        'action': 'list_animes',
        'icon': os.path.join(ICON_PATH, 'crunchyroll_white.png'),
        'plot': 'Anime and content from Crunchyroll via TMDB.'
    },

    {
        'title': 'Collections',
        'action': 'list_collections',
        'icon': '2OJn9MC',
        'plot': 'Complete film sagas and franchises.'
    },
    {
        'title': 'Search',
        'action': 'search',
        'icon': 'owsADQ4',
        'plot': 'Search movies and series by title.'
    },
    {
        'title': 'My List',
        'action': 'favorites_menu',
        'icon': 'XbEEv9X',
        'plot': 'Your favorites and locally saved items.'
    },
    {
        'title': 'Trakt',
        'action': 'trakt_main_menu',
        'icon': os.path.join(ICON_PATH, 'trakt_red.png'),
        'plot': 'Watchlist, collection, watched and sync with your Trakt account.'
    },

    {
        'title': '[COLOR red]Settings[/COLOR]',
        'action': 'open_settings',
        'icon': os.path.join(ICON_PATH, 'settings_red.png'),
        'plot': 'Addon settings, maintenance and information.'
    },
]


TOOLS_MENU = [
    {'title': 'Settings', 'action': 'open_settings', 'icon': os.path.join(ICON_PATH, 'settings_red.png')},
    {'title': '[COLOR gold]Update Catalog[/COLOR]', 'action': 'update_catalog', 'icon': 'vBwrjLV'},
    {'title': 'Changelog', 'action': 'show_changelog', 'icon': 'XbEEv9X'},
    {'title': 'Donation', 'action': 'show_donation', 'icon': 'XbEEv9X'}
]

MOVIES_MENU = [
    {'title': 'Streaming', 'action': 'list_streaming_platforms_movies', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
    {'title': 'Trends', 'action': 'list_trending_movies', 'icon': 'rVq7so0'},
    {'title': 'Popular', 'action': 'list_movies_by_popularity', 'icon': 'ngkznpf'},
    {'title': 'Top Rated', 'action': 'list_movies_top_rated', 'icon': 'aj02pjQ'},
    {'title': 'In Cinemas', 'action': 'list_movies_now_playing', 'icon': '9660DAY'},
    {'title': 'Upcoming Movies', 'action': 'list_upcoming_movies', 'icon': 's4krx5q'},
    {'title': 'Genres', 'action': 'list_genres', 'icon': '6QpJbS0'},
    {'title': 'Biggest box office', 'action': 'list_movies_by_revenue', 'icon': 'WzYp4H8'},
    {'title': 'Per year', 'action': 'list_years', 'icon': 'fN4GQmO'},  # IMDb calendar icon

    {'title': 'Trends (Trakt)', 'action': 'trakt_movies_trending', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Popular', 'action': 'trakt_movies_popular', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Most Watched', 'action': 'trakt_movies_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Most Collected', 'action': 'trakt_movies_most_collected', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Most Awaited', 'action': 'trakt_movies_most_anticipated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Box office', 'action': 'trakt_movies_box_office', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Top Rated', 'action': 'trakt_movies_top_rated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
]

TVSHOWS_MENU = [
    {'title': 'Streaming', 'action': 'list_streaming_platforms_tvshows', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
    {'title': 'Trends', 'action': 'list_trending_tvshows', 'icon': 'rVq7so0'},
    {'title': 'Popular', 'action': 'list_tvshows_by_popularity', 'icon': 'ngkznpf'},
    {'title': 'Best Rated', 'action': 'list_tvshows_top_rated', 'icon': 'aj02pjQ'},
    {'title': 'Pass Today', 'action': 'list_tvshows_airing_today', 'icon': 'fN4GQmO'},
    {'title': 'In the Air (Week)', 'action': 'list_tvshows_on_the_air', 'icon': 'Ht6HpQO'},
    {'title': 'Upcoming TV Shows', 'action': 'list_upcoming_tvshows', 'icon': 's4krx5q'},
    {'title': 'Genres', 'action': 'list_tvshows_genres', 'icon': '6QpJbS0'},
    {'title': 'Per year', 'action': 'list_tvshows_years', 'icon': 'fN4GQmO'},  # IMDb calendar icon
    {'title': 'Kids', 'action': 'list_kids_tvshows', 'icon': 'cMjxdqe'},
    {'title': 'Trends (Trakt)', 'action': 'trakt_tv_trending', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Popular', 'action': 'trakt_tv_popular', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Most Watched', 'action': 'trakt_tv_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Most Collected', 'action': 'trakt_tv_most_collected', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Most Awaited', 'action': 'trakt_tv_most_anticipated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Best Rated', 'action': 'trakt_tv_top_rated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Recommended', 'action': 'trakt_tv_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
]

# === ✅ TRAKT MENU CORRECTED ===
TRAKT_MENU = [
    {'title': 'Status / Authenticate', 'action': 'trakt_auth', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Watchlist', 'action': 'trakt_watchlist_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Collection', 'action': 'trakt_collection_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Watched', 'action': 'trakt_watched_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'My Lists', 'action': 'trakt_lists_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
]

STREAMING_MENU = [
    {'title': 'Streaming', 'action': 'list_streaming_platforms_movies', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
    {'title': 'Streaming', 'action': 'list_streaming_platforms_tvshows', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
]

LOGO_PATH = os.path.join(ADDON_PATH, 'resources', 'logos')

# ✅ COMBINED IDs FOR FULL CONTENT (US)
# Includes extra channels and variants to ensure maximum catalog
NETFLIX_IDS = "8|1796"
PRIME_IDS = "119|2100"
DISNEY_IDS = "337"
MAX_IDS = "1899|1825|2472"
PARAMOUNT_IDS = "531|1853|2303"
GLOBOPLAY_IDS = "307"
APPLE_IDS = "2|350|2243"
CLARO_IDS = "484"
CRUNCHY_IDS = "283|1968"
MERCADO_IDS = "2302"
TELECINE_IDS = "2156"

STREAMING_PLATFORMS = {
    'movie': [
        {'name': 'Netflix', 'id': NETFLIX_IDS, 'logo': 'pbpMk2JmcoNnQwx5JGpXngfoWtp.jpg', 'region': 'US'},
        {'name': 'Amazon Prime Video', 'id': PRIME_IDS, 'logo': 'pvske1MyAoymrs5bguRfVqYiM9a.jpg', 'region': 'US'},
        {'name': 'Disney Plus', 'id': DISNEY_IDS, 'logo': '97yvRBw1GzX7fXprcF80er19ot.jpg', 'region': 'US'},
        {'name': 'Max', 'id': MAX_IDS, 'logo': 'jbe4gVSfRlbPTdESXhEKpornsfu.jpg', 'region': 'US'},
        {'name': 'Globoplay', 'id': GLOBOPLAY_IDS, 'logo': '7Cg8esVVXOijXAm1f1vrS7jVjcN.jpg', 'region': 'BR'},
        {'name': 'Paramount Plus', 'id': PARAMOUNT_IDS, 'logo': 'h5DcR0J2EESLitnhR8xLG1QymTE.jpg', 'region': 'US'},
        {'name': 'Apple TV', 'id': APPLE_IDS, 'logo': 'mcbz1LgtErU9p4UdbZ0rG6RTWHX.jpg', 'region': 'US'},
        {'name': 'Claro TV+', 'id': CLARO_IDS, 'logo': '7EpFKOCMrlo3bjsyBMrec64c7Wb.jpg', 'region': 'BR'},
        {'name': 'Telecine', 'id': TELECINE_IDS, 'logo': '9kcTsX2laYclN4bFiMH3RuhZel2.jpg', 'region': 'BR'},
        {'name': 'Crunchyroll', 'id': CRUNCHY_IDS, 'logo': 'fzN5Jok5Ig1eJ7gyNGoMhnLSCfh.jpg', 'region': 'US'},
        {'name': 'Play Market', 'id': MERCADO_IDS, 'logo': '60iyHW9xKBKVBf0kxiQixuLqG1f.jpg', 'region': 'BR'},
        {'name': 'MUBI', 'id': 11, 'logo': 'x570VpH2C9EKDf1riP83rYc5dnL.jpg', 'region': 'US'},
    ],
    'tv': [
        {'name': 'Netflix', 'id': NETFLIX_IDS, 'logo': 'pbpMk2JmcoNnQwx5JGpXngfoWtp.jpg', 'region': 'US'},
        {'name': 'Amazon Prime Video', 'id': PRIME_IDS, 'logo': 'pvske1MyAoymrs5bguRfVqYiM9a.jpg', 'region': 'US'},
        {'name': 'Disney Plus', 'id': DISNEY_IDS, 'logo': '97yvRBw1GzX7fXprcF80er19ot.jpg', 'region': 'US'},
        {'name': 'Max', 'id': MAX_IDS, 'logo': 'jbe4gVSfRlbPTdESXhEKpornsfu.jpg', 'region': 'US'},
        {'name': 'Globoplay', 'id': GLOBOPLAY_IDS, 'logo': '7Cg8esVVXOijXAm1f1vrS7jVjcN.jpg', 'region': 'BR'},
        {'name': 'Paramount Plus', 'id': PARAMOUNT_IDS, 'logo': 'h5DcR0J2EESLitnhR8xLG1QymTE.jpg', 'region': 'US'},
        {'name': 'Apple TV', 'id': APPLE_IDS, 'logo': 'mcbz1LgtErU9p4UdbZ0rG6RTWHX.jpg', 'region': 'US'},
        {'name': 'Claro TV+', 'id': CLARO_IDS, 'logo': '7EpFKOCMrlo3bjsyBMrec64c7Wb.jpg', 'region': 'BR'},
        {'name': 'Crunchyroll', 'id': CRUNCHY_IDS, 'logo': 'fzN5Jok5Ig1eJ7gyNGoMhnLSCfh.jpg', 'region': 'US'},
        {'name': 'Play Market', 'id': MERCADO_IDS, 'logo': '60iyHW9xKBKVBf0kxiQixuLqG1f.jpg', 'region': 'BR'},
        {'name': 'MUBI', 'id': 11, 'logo': 'x570VpH2C9EKDf1riP83rYc5dnL.jpg', 'region': 'US'},
    ]
}
