### resources/lib/tmdb/tv.py
from .api import tmdb_cached, tmdb_request, TTL_LIST, TTL_DETAILS, TTL_SHORT


def get_popular_tv(page=1):
    return tmdb_cached('tv/popular', {'page': page})

def get_trending_tv(page=1):
    return tmdb_cached('trending/tv/week', {'page': page})

def get_tv_genres():
    return tmdb_cached('genre/tv/list', {}, ttl=TTL_DETAILS)

def get_tv_by_genre(genre_id, page=1):
    return tmdb_cached('discover/tv', {'with_genres': genre_id, 'page': page})

def get_tv_by_year(year, page=1):
    return tmdb_cached('discover/tv', {'first_air_date_year': year, 'page': page})

def get_tv_providers():
    return tmdb_cached('watch/providers/tv', {}, ttl=TTL_DETAILS)

def get_tv_by_provider(provider_id, page=1):
    return tmdb_cached('discover/tv', {'with_watch_providers': provider_id, 'page': page})

def search_tvshows(query):
    return tmdb_request('search/tv', {'query': query})

def get_tv_details(tv_id):
    return tmdb_cached(
        f'tv/{tv_id}',
        {'append_to_response': 'credits,videos,images,external_ids'},
        ttl=TTL_DETAILS,
    )

def get_season(tv_id, season_number, language=None):
    params = {'language': language} if language else {}
    return tmdb_cached(f'tv/{tv_id}/season/{season_number}', params, ttl=TTL_DETAILS)

def get_similar_tv(tv_id, page=1):
    return tmdb_cached(f'tv/{tv_id}/similar', {'page': page}, ttl=TTL_SHORT)

def get_recommended_tv(tv_id, page=1):
    return tmdb_cached(f'tv/{tv_id}/recommendations', {'page': page}, ttl=TTL_SHORT)
