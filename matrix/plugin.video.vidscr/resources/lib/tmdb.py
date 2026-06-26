# -*- coding: utf-8 -*-
"""TMDB v3 client. https://developer.themoviedb.org/reference/intro/getting-started"""
import requests

from . import cache
from .common import get_setting, log

API_BASE = 'https://api.themoviedb.org/3'
IMG_BASE = 'https://image.tmdb.org/t/p'

TIMEOUT = 15


def _key():
    return get_setting('tmdb_api_key', 'f15af109700aab95d564acda15bdcd97')


def _lang():
    return get_setting('tmdb_lang', 'en-GB')


def _region():
    return get_setting('tmdb_region', 'GB')


def _get(path, params=None, ttl=21600):
    url = API_BASE + path
    p = {'api_key': _key(), 'language': _lang()}
    if params:
        p.update(params)
    cached = cache.get(url, p, ttl=ttl)
    if cached is not None:
        return cached
    try:
        r = requests.get(url, params=p, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        cache.put(url, p, data)
        return data
    except Exception as e:
        log('TMDB error %s on %s' % (e, path))
        return {}


def poster(path, size='w500'):
    if not path:
        return ''
    return '%s/%s%s' % (IMG_BASE, size, path)


def backdrop(path, size='w1280'):
    if not path:
        return ''
    return '%s/%s%s' % (IMG_BASE, size, path)


# ---------------- Movies -----------------

def movies_now_playing(page=1):
    return _get('/movie/now_playing', {'page': page, 'region': _region()})


def movies_popular(page=1):
    return _get('/movie/popular', {'page': page, 'region': _region()})


def movies_top_rated(page=1):
    return _get('/movie/top_rated', {'page': page, 'region': _region()})


def movies_upcoming(page=1):
    return _get('/movie/upcoming', {'page': page, 'region': _region()})


def discover_movies(params=None, page=1):
    p = {'page': page, 'sort_by': 'popularity.desc', 'include_adult': 'false'}
    if params:
        p.update(params)
    return _get('/discover/movie', p)


def search_movie(query, page=1):
    return _get('/search/movie', {'query': query, 'page': page, 'include_adult': 'false'})


def movie_genres():
    return _get('/genre/movie/list', ttl=86400 * 7).get('genres', [])


def movie_details(tmdb_id):
    return _get('/movie/%s' % tmdb_id, {'append_to_response': 'credits,external_ids,videos,release_dates'}, ttl=86400)


def movie_credits(tmdb_id):
    return _get('/movie/%s/credits' % tmdb_id, ttl=86400)


# Oscar nominees: TMDB has no direct Oscars list, but maintains a curated keyword + lists.
# We use TMDB's "Best Picture nominee" keyword IDs and also list 'awards' via discover with vote_count filter.
# Most reliable approach: use TMDB's certified curated list IDs for Oscar Best Picture nominees.
# We use list_id 28 = "AFI's 100 Years...100 Movies" as a fallback; and the public Oscars Best Picture
# nominee list IDs maintained by TMDB users. We'll prefer keyword 207317 ("oscar award") + sort by vote.
def oscar_nominees(page=1):
    # Best Picture nominees keyword on TMDB is 207317
    return _get('/discover/movie', {
        'with_keywords': '207317',
        'sort_by': 'vote_average.desc',
        'vote_count.gte': '500',
        'page': page,
        'include_adult': 'false',
    })


# ---------------- TV -----------------

def tv_popular(page=1):
    return _get('/tv/popular', {'page': page})


def tv_top_rated(page=1):
    return _get('/tv/top_rated', {'page': page})


def tv_on_the_air(page=1):
    return _get('/tv/on_the_air', {'page': page})


def tv_airing_today(page=1):
    return _get('/tv/airing_today', {'page': page})


def discover_tv(params=None, page=1):
    p = {'page': page, 'sort_by': 'popularity.desc'}
    if params:
        p.update(params)
    return _get('/discover/tv', p)


def search_tv(query, page=1):
    return _get('/search/tv', {'query': query, 'page': page})


def tv_genres():
    return _get('/genre/tv/list', ttl=86400 * 7).get('genres', [])


def tv_networks():
    # TMDB has no public "list all networks" endpoint. Use a curated set of major networks.
    return [
        {'id': 213, 'name': 'Netflix'},
        {'id': 49, 'name': 'HBO'},
        {'id': 1024, 'name': 'Prime Video'},
        {'id': 2739, 'name': 'Disney+'},
        {'id': 2552, 'name': 'Apple TV+'},
        {'id': 453, 'name': 'Hulu'},
        {'id': 4, 'name': 'BBC'},
        {'id': 16, 'name': 'CBS'},
        {'id': 6, 'name': 'NBC'},
        {'id': 2, 'name': 'ABC'},
        {'id': 19, 'name': 'FOX'},
        {'id': 67, 'name': 'Showtime'},
        {'id': 64, 'name': 'Discovery'},
        {'id': 65, 'name': 'History'},
        {'id': 174, 'name': 'AMC'},
        {'id': 318, 'name': 'Starz'},
        {'id': 88, 'name': 'FX'},
        {'id': 56, 'name': 'Cartoon Network'},
        {'id': 13, 'name': 'Comedy Central'},
        {'id': 80, 'name': 'Adult Swim'},
        {'id': 384, 'name': 'HBO Max'},
        {'id': 4330, 'name': 'Paramount+'},
        {'id': 3186, 'name': 'BBC One'},
        {'id': 3290, 'name': 'BBC Two'},
        {'id': 4, 'name': 'BBC'},
        {'id': 214, 'name': 'Sky'},
        {'id': 26, 'name': 'ITV'},
        {'id': 41, 'name': 'Channel 4'},
    ]


def tv_details(tmdb_id):
    return _get('/tv/%s' % tmdb_id, {'append_to_response': 'credits,external_ids,videos'}, ttl=86400)


def tv_season(tmdb_id, season_no):
    return _get('/tv/%s/season/%s' % (tmdb_id, season_no), ttl=86400)


# ---------------- People -----------------

def popular_people(page=1):
    return _get('/person/popular', {'page': page})


def person_details(person_id):
    return _get('/person/%s' % person_id, {'append_to_response': 'combined_credits,external_ids'}, ttl=86400)


def search_person(query, page=1):
    return _get('/search/person', {'query': query, 'page': page})


# ---------------- Multi-search -----------------

def search_multi(query, page=1):
    return _get('/search/multi', {'query': query, 'page': page, 'include_adult': 'false'})


# ---------------- Collections (franchises) -----------------

def search_collection(query):
    return _get('/search/collection', {'query': query}, ttl=86400 * 30)


def collection_details(collection_id):
    return _get('/collection/%s' % collection_id, ttl=86400 * 7)


# ---------------- Trending -----------------

def trending_movies(period='week', page=1):
    # period: 'day' or 'week'
    return _get('/trending/movie/%s' % period, {'page': page})


def trending_tv(period='week', page=1):
    return _get('/trending/tv/%s' % period, {'page': page})
