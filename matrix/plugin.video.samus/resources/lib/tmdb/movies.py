### resources/lib/tmdb/movies.py
from .api import tmdb_cached, tmdb_request, TTL_LIST, TTL_DETAILS, TTL_SHORT


def get_popular_movies(page=1):
    return tmdb_cached('movie/popular', {'page': page})

def get_trending_movies(page=1):
    return tmdb_cached('trending/movie/week', {'page': page})

def get_movie_genres():
    return tmdb_cached('genre/movie/list', {}, ttl=TTL_DETAILS)

def get_movies_by_genre(genre_id, page=1):
    return tmdb_cached('discover/movie', {'with_genres': genre_id, 'page': page})

def get_movies_by_year(year, page=1):
    return tmdb_cached('discover/movie', {'primary_release_year': year, 'page': page})

def get_movie_providers():
    return tmdb_cached('watch/providers/movie', {}, ttl=TTL_DETAILS)

def get_movies_by_provider(provider_id, page=1):
    return tmdb_cached('discover/movie', {'with_watch_providers': provider_id, 'page': page})

def search_movies(query):
    # Căutările nu se cacheează (query-urile sunt diverse și scurte)
    return tmdb_request('search/movie', {'query': query})

def get_movie_details(tmdb_id):
    return tmdb_cached(
        f'movie/{tmdb_id}',
        {'append_to_response': 'credits,videos,external_ids,images'},
        ttl=TTL_DETAILS,
    )

def get_similar_movies(tmdb_id, page=1):
    return tmdb_cached(f'movie/{tmdb_id}/similar', {'page': page}, ttl=TTL_SHORT)

def get_recommended_movies(tmdb_id, page=1):
    return tmdb_cached(f'movie/{tmdb_id}/recommendations', {'page': page}, ttl=TTL_SHORT)

def get_movie_collection(collection_id):
    return tmdb_cached(f'collection/{collection_id}', {}, ttl=TTL_DETAILS)
