# -*- coding: utf-8 -*-

import os
import xbmcaddon

# --- Configuração de Caminhos ---
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

MAIN_MENU = [
    {
        'title': 'Filme',
        'action': 'movies_menu',
        'icon': 'pmyCOx7',
        'plot': 'Filme din catalogul TMDB și liste publice de pe Trakt.'
    },

    {
        'title': 'Seriale',
        'action': 'tvshows_menu',
        'icon': 'R3NEEJl',
        'plot': 'Seriale de pe TMDB și liste publice de pe Trakt.'
    },
    {
        'title': 'Crunchyroll',
        'action': 'list_animes',
        'icon': os.path.join(ICON_PATH, 'crunchyroll_white.png'),
        'plot': 'Anime și conținuturi Crunchyroll prin TMDB.'
    },

    {
        'title': 'Colectii',
        'action': 'list_collections',
        'icon': '2OJn9MC',
        'plot': 'Saga si francize complete de filme.'
    },
    {
        'title': 'Cautare',
        'action': 'search',
        'icon': 'owsADQ4',
        'plot': 'Căutați filme și seriale după titlu.'
    },
    {
        'title': 'Lista mea',
        'action': 'favorites_menu',
        'icon': 'XbEEv9X',
        'plot': 'Favoritele mele și articolele salvate local.'
    },
    {
        'title': 'Trakt',
        'action': 'trakt_main_menu',
        'icon': os.path.join(ICON_PATH, 'trakt_red.png'),
        'plot': 'Watchlist, colecție, vizionate și sincronizare cu contul tău Trakt.'
    },

    {
        'title': '[COLOR red]Configurare[/COLOR]',
        'action': 'open_settings',
        'icon': os.path.join(ICON_PATH, 'settings_red.png'),
        'plot': 'Setări, întreținere și informații despre addon.'
    },
]


TOOLS_MENU = [
    {'title': 'Configurare', 'action': 'open_settings', 'icon': os.path.join(ICON_PATH, 'settings_red.png')},
    {'title': '[COLOR gold]Actualizare Catalog[/COLOR]', 'action': 'update_catalog', 'icon': 'vBwrjLV'},
    {'title': 'Changelog', 'action': 'show_changelog', 'icon': 'XbEEv9X'},
    {'title': 'Donatii', 'action': 'show_donation', 'icon': 'XbEEv9X'}
]

MOVIES_MENU = [
    {'title': 'Streaming', 'action': 'list_streaming_platforms_movies', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
    {'title': 'Tendinte', 'action': 'list_trending_movies', 'icon': 'rVq7so0'},
    {'title': 'Populare', 'action': 'list_movies_by_popularity', 'icon': 'ngkznpf'},
    {'title': 'Top Rated', 'action': 'list_movies_top_rated', 'icon': 'aj02pjQ'},
    {'title': 'In Cinematografe', 'action': 'list_movies_now_playing', 'icon': '9660DAY'},
    {'title': 'Filme Nelansate', 'action': 'list_upcoming_movies', 'icon': 's4krx5q'},
    {'title': 'Gen', 'action': 'list_genres', 'icon': '6QpJbS0'},
    {'title': 'Dupa Incasari', 'action': 'list_movies_by_revenue', 'icon': 'WzYp4H8'},
    {'title': 'Ani', 'action': 'list_years', 'icon': 'fN4GQmO'},  # Ícone de calendário do IMDb

    {'title': 'Tendinte (Trakt)', 'action': 'trakt_movies_trending', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Populare', 'action': 'trakt_movies_popular', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Cele Mai Vizionate', 'action': 'trakt_movies_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Cele Mai Colectionate', 'action': 'trakt_movies_most_collected', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Cele Mai Anticipate', 'action': 'trakt_movies_most_anticipated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'BOX Office', 'action': 'trakt_movies_box_office', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Top Rated', 'action': 'trakt_movies_top_rated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
]

TVSHOWS_MENU = [
    {'title': 'Streaming', 'action': 'list_streaming_platforms_tvshows', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
    {'title': 'Tendinte', 'action': 'list_trending_tvshows', 'icon': 'rVq7so0'},
    {'title': 'Populare', 'action': 'list_tvshows_by_popularity', 'icon': 'ngkznpf'},
    {'title': 'Top Rated', 'action': 'list_tvshows_top_rated', 'icon': 'aj02pjQ'},
    {'title': 'Ruleaza de Azi', 'action': 'list_tvshows_airing_today', 'icon': 'fN4GQmO'},
    {'title': 'Live (Săptămâna)', 'action': 'list_tvshows_on_the_air', 'icon': 'Ht6HpQO'},
    {'title': 'Seriale Nelansate', 'action': 'list_upcoming_tvshows', 'icon': 's4krx5q'},
    {'title': 'Gen', 'action': 'list_tvshows_genres', 'icon': '6QpJbS0'},
    {'title': 'Ani', 'action': 'list_tvshows_years', 'icon': 'fN4GQmO'},  # Ícone de calendário do IMDb
    {'title': 'Pentru Copii', 'action': 'list_kids_tvshows', 'icon': 'cMjxdqe'},
    {'title': 'Tendinte (Trakt)', 'action': 'trakt_tv_trending', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Populare', 'action': 'trakt_tv_popular', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Cele Mai Vizionate', 'action': 'trakt_tv_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Cele Mai Colectionate', 'action': 'trakt_tv_most_collected', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Cele Mai Anticipate', 'action': 'trakt_tv_most_anticipated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Top Rated', 'action': 'trakt_tv_top_rated', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Recomandate', 'action': 'trakt_tv_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
]

# === ✅ MENU TRAKT CORRIGIDO ===
TRAKT_MENU = [
    {'title': 'Status / Autentificare', 'action': 'trakt_auth', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Watchlist', 'action': 'trakt_watchlist_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Colectie', 'action': 'trakt_collection_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Vizionate', 'action': 'trakt_watched_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
    {'title': 'Lista Mea', 'action': 'trakt_lists_menu', 'icon': os.path.join(ICON_PATH, 'trakt_red.png')},
]

STREAMING_MENU = [
    {'title': 'Streaming', 'action': 'list_streaming_platforms_movies', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
    {'title': 'Streaming', 'action': 'list_streaming_platforms_tvshows', 'icon': os.path.join(ICON_PATH, 'tmdb_color.png')},
]

LOGO_PATH = os.path.join(ADDON_PATH, 'resources', 'logos')

# ✅ IDs COMBINADOS PARA CONTEÚDO COMPLETO (BR)
# Inclui canais extras e variantes para garantir catálogo máximo
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
        {'name': 'Netflix', 'id': NETFLIX_IDS, 'logo': 'pbpMk2JmcoNnQwx5JGpXngfoWtp.jpg', 'region': 'BR'},
        {'name': 'Amazon Prime Video', 'id': PRIME_IDS, 'logo': 'pvske1MyAoymrs5bguRfVqYiM9a.jpg', 'region': 'BR'},
        {'name': 'Disney Plus', 'id': DISNEY_IDS, 'logo': '97yvRBw1GzX7fXprcF80er19ot.jpg', 'region': 'BR'},
        {'name': 'Max', 'id': MAX_IDS, 'logo': 'jbe4gVSfRlbPTdESXhEKpornsfu.jpg', 'region': 'BR'},
        {'name': 'Globoplay', 'id': GLOBOPLAY_IDS, 'logo': '7Cg8esVVXOijXAm1f1vrS7jVjcN.jpg', 'region': 'BR'},
        {'name': 'Paramount Plus', 'id': PARAMOUNT_IDS, 'logo': 'h5DcR0J2EESLitnhR8xLG1QymTE.jpg', 'region': 'BR'},
        {'name': 'Apple TV', 'id': APPLE_IDS, 'logo': 'mcbz1LgtErU9p4UdbZ0rG6RTWHX.jpg', 'region': 'BR'},
        {'name': 'Claro TV+', 'id': CLARO_IDS, 'logo': '7EpFKOCMrlo3bjsyBMrec64c7Wb.jpg', 'region': 'BR'},
        {'name': 'Telecine', 'id': TELECINE_IDS, 'logo': '9kcTsX2laYclN4bFiMH3RuhZel2.jpg', 'region': 'BR'},
        {'name': 'Crunchyroll', 'id': CRUNCHY_IDS, 'logo': 'fzN5Jok5Ig1eJ7gyNGoMhnLSCfh.jpg', 'region': 'BR'},
        {'name': 'Mercado Play', 'id': MERCADO_IDS, 'logo': '60iyHW9xKBKVBf0kxiQixuLqG1f.jpg', 'region': 'BR'},
        {'name': 'MUBI', 'id': 11, 'logo': 'x570VpH2C9EKDf1riP83rYc5dnL.jpg', 'region': 'BR'},
    ],
    'tv': [
        {'name': 'Netflix', 'id': NETFLIX_IDS, 'logo': 'pbpMk2JmcoNnQwx5JGpXngfoWtp.jpg', 'region': 'BR'},
        {'name': 'Amazon Prime Video', 'id': PRIME_IDS, 'logo': 'pvske1MyAoymrs5bguRfVqYiM9a.jpg', 'region': 'BR'},
        {'name': 'Disney Plus', 'id': DISNEY_IDS, 'logo': '97yvRBw1GzX7fXprcF80er19ot.jpg', 'region': 'BR'},
        {'name': 'Max', 'id': MAX_IDS, 'logo': 'jbe4gVSfRlbPTdESXhEKpornsfu.jpg', 'region': 'BR'},
        {'name': 'Globoplay', 'id': GLOBOPLAY_IDS, 'logo': '7Cg8esVVXOijXAm1f1vrS7jVjcN.jpg', 'region': 'BR'},
        {'name': 'Paramount Plus', 'id': PARAMOUNT_IDS, 'logo': 'h5DcR0J2EESLitnhR8xLG1QymTE.jpg', 'region': 'BR'},
        {'name': 'Apple TV', 'id': APPLE_IDS, 'logo': 'mcbz1LgtErU9p4UdbZ0rG6RTWHX.jpg', 'region': 'BR'},
        {'name': 'Claro TV+', 'id': CLARO_IDS, 'logo': '7EpFKOCMrlo3bjsyBMrec64c7Wb.jpg', 'region': 'BR'},
        {'name': 'Crunchyroll', 'id': CRUNCHY_IDS, 'logo': 'fzN5Jok5Ig1eJ7gyNGoMhnLSCfh.jpg', 'region': 'BR'},
        {'name': 'Mercado Play', 'id': MERCADO_IDS, 'logo': '60iyHW9xKBKVBf0kxiQixuLqG1f.jpg', 'region': 'BR'},
        {'name': 'MUBI', 'id': 11, 'logo': 'x570VpH2C9EKDf1riP83rYc5dnL.jpg', 'region': 'BR'},
    ]
}
