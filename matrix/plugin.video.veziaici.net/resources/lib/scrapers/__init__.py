"""Scrapers package for VeziAici.net addon."""

from resources.lib.scrapers.veziaici import (
    get_main_menu_items as get_veziaici_menu,
    get_episodes as get_veziaici_episodes,
    parse_seasons as parse_veziaici_seasons,
    get_sources as get_veziaici_sources,
    search as search_veziaici,
    get_latest as get_veziaici_latest,
)

from resources.lib.scrapers.terasacucartii import (
    get_categories as get_terasa_categories,
    get_series_list as get_terasa_series,
    get_sources as get_terasa_sources,
    search as search_terasa,
)

from resources.lib.scrapers.blogul_atanase import (
    get_korean_categories,
    get_years,
    get_series_list as get_blogul_series,
    get_episodes_and_sources as get_blogul_episodes,
    get_season_episodes,
    get_movie_sources,
)

from resources.lib.scrapers.serialecoreene import (
    get_main_menu as get_serialecoreene_menu,
    get_series_list as get_serialecoreene_series,
    get_new_episodes,
    get_episodes_and_sources as get_serialecoreene_episodes,
    get_playable_url,
    search as search_serialecoreene,
)

from resources.lib.scrapers.serialero import (
    get_menu as get_serialero_menu,
    get_series_list as get_serialero_series,
    get_seasons_and_episodes as get_serialero_episodes,
    get_season_episodes as get_serialero_season_episodes,
    get_sources as get_serialero_sources,
)

from resources.lib.scrapers.serialeromanesti import (
    get_menu as get_serialeromanesti_menu,
    get_series_list as get_serialeromanesti_series,
    get_sources as get_serialeromanesti_sources,
    search as search_serialeromanesti,
)

__all__ = [
    # Veziaici
    "get_veziaici_menu",
    "get_veziaici_episodes",
    "parse_veziaici_seasons",
    "get_veziaici_sources",
    "search_veziaici",
    "get_veziaici_latest",
    # Terasacucartii
    "get_terasa_categories",
    "get_terasa_series",
    "get_terasa_sources",
    "search_terasa",
    # Blogul Atanase
    "get_korean_categories",
    "get_years",
    "get_blogul_series",
    "get_blogul_episodes",
    "get_season_episodes",
    "get_movie_sources",
    # SerialeCoreene
    "get_serialecoreene_menu",
    "get_serialecoreene_series",
    "get_new_episodes",
    "get_serialecoreene_episodes",
    "get_playable_url",
    "search_serialecoreene",
    # SerialeRo
    "get_serialero_menu",
    "get_serialero_series",
    "get_serialero_episodes",
    "get_serialero_season_episodes",
    "get_serialero_sources",
    # SerialeRomanesti
    "get_serialeromanesti_menu",
    "get_serialeromanesti_series",
    "get_serialeromanesti_sources",
    "search_serialeromanesti",
]
