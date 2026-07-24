# -*- coding: utf-8 -*-
import requests
import xbmc
import xbmcaddon

_API_KEY = '69ef972e0d191aff7ab5b8e396619cb2'
_BASE    = 'https://api.themoviedb.org/3'
_IMG     = 'https://image.tmdb.org/t/p/'
_LANG    = 'ro'  # fallback; suprascris dinamic la fiecare apel

_GENRES_MOVIE = {
    28: 'Acțiune', 12: 'Aventură', 16: 'Animație', 35: 'Comedie',
    80: 'Crimă', 99: 'Documentar', 18: 'Dramă', 10751: 'Familie',
    14: 'Fantezie', 36: 'Istorie', 27: 'Horror', 9648: 'Mister',
    10749: 'Romantism', 878: 'SF', 53: 'Thriller', 10752: 'Război', 37: 'Western',
}
_GENRES_TV = {
    10759: 'Acțiune', 16: 'Animație', 35: 'Comedie', 80: 'Crimă',
    99: 'Documentar', 18: 'Dramă', 10751: 'Familie', 10765: 'SF & Fantasy',
    9648: 'Mister', 10764: 'Reality', 37: 'Western',
}

_SESS = requests.Session()
_SESS.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'


def _get_lang():
    try:
        return xbmcaddon.Addon('plugin.video.samusxui').getSetting('language') or _LANG
    except Exception:
        return _LANG


def _get(path, **params):
    params['api_key'] = _API_KEY
    params.setdefault('language', _get_lang())
    try:
        r = _SESS.get(f'{_BASE}{path}', params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        xbmc.log(f'[SamusXUI/TMDb] {path}: {e}', xbmc.LOGWARNING)
        return {}


def _discover(media, extra_params, page=1):
    params = {'api_key': _API_KEY, 'language': _get_lang(), 'page': page, **extra_params}
    try:
        r = _SESS.get(f'{_BASE}/discover/{media}', params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        xbmc.log(f'[SamusXUI/TMDb] /discover/{media}: {e}', xbmc.LOGWARNING)
        return {}


def popular_by_year(media, year, page=1):
    extra = {'sort_by': 'popularity.desc', 'vote_count.gte': 10}
    if media == 'movie':
        extra['primary_release_year'] = year
    else:
        extra['first_air_date.gte'] = f'{year}-01-01'
        extra['first_air_date.lte'] = f'{year}-12-31'
    return _discover(media, extra, page)


def popular_by_provider(media, provider_id, page=1):
    return _discover(media, {
        'with_watch_providers': provider_id,
        'watch_region': 'RO',
        'sort_by': 'popularity.desc',
    }, page)


def popular(media='movie', genre_id=None, page=1):
    if genre_id:
        return _get(f'/discover/{media}',
                    with_genres=genre_id,
                    sort_by='popularity.desc',
                    page=page)
    return _get(f'/{media}/popular', page=page)


def trending(media='movie', time='week', page=1):
    return _get(f'/trending/{media}/{time}', page=page)


def top_rated(media='movie', page=1):
    return _get(f'/{media}/top_rated', page=page)


def collection(collection_id):
    return _get(f'/collection/{collection_id}')


def now_playing(page=1):
    return _get('/movie/now_playing', page=page)


def upcoming(page=1):
    return _get('/movie/upcoming', page=page)


def on_the_air(page=1):
    return _get('/tv/on_the_air', page=page)


def airing_today(page=1):
    return _get('/tv/airing_today', page=page)


def movie_details(tmdb_id):
    data = _get(f'/movie/{tmdb_id}',
                append_to_response='credits,external_ids,images,videos',
                include_image_language='en,{},null'.format(_get_lang()))
    if not data.get('title') or not data.get('overview'):
        en = _get(f'/movie/{tmdb_id}', language='en')
        for key in ('title', 'overview', 'tagline'):
            if not data.get(key) and en.get(key):
                data[key] = en[key]
    return data


def tv_details(tmdb_id):
    data = _get(f'/tv/{tmdb_id}',
                append_to_response='credits,external_ids,images,videos',
                include_image_language='en,{},null'.format(_get_lang()))
    if not data.get('name') or not data.get('overview'):
        en = _get(f'/tv/{tmdb_id}', language='en')
        for key in ('name', 'overview', 'tagline'):
            if not data.get(key) and en.get(key):
                data[key] = en[key]
    return data


def text_en(tmdb_id, media='movie'):
    """Fetch title/name/overview in English — lightweight, no append_to_response."""
    return _get(f'/{media}/{tmdb_id}', language='en')


def basic_info(tmdb_id, media='movie'):
    """Lightweight fetch — poster_path, backdrop_path, vote_average, vote_count."""
    return _get(f'/{media}/{tmdb_id}')


def videos(tmdb_id, media='movie'):
    return _get(f'/{media}/{tmdb_id}/videos', language='en')


def get_external_ids(tmdb_id, media='movie'):
    data = _get(f'/{media}/{tmdb_id}/external_ids')
    return data.get('imdb_id')


def poster_url(path, size='w342'):
    return f'{_IMG}{size}{path}' if path else ''


def backdrop_url(path, size='w1280'):
    return f'{_IMG}{size}{path}' if path else ''


def logo_url(tmdb_id, media='movie'):
    data = _get(f'/{media}/{tmdb_id}/images', include_image_language='en,{},null'.format(_get_lang()))
    for logo in data.get('logos', []):
        fp = logo.get('file_path', '')
        if fp and fp.lower().endswith('.png'):
            return f'{_IMG}w500{fp}'
    return ''


def _age_cert_from_tmdb(data, media='movie'):
    def norm(value):
        value = (value or '').upper().replace(' ', '')
        if not value:
            return ''
        if any(x in value for x in ('18', 'NC-17', 'R18', 'TV-MA')):
            return '+18'
        if any(x in value for x in ('16', 'R', 'TV-14')):
            return '+16'
        if any(x in value for x in ('12', 'PG-13', 'TV-PG')):
            return '+12'
        if value in ('NR', 'N/A', 'UNRATED', 'NOTRATED'):
            return 'NR'
        return ''

    if media == 'movie':
        results = (data.get('release_dates') or {}).get('results', [])
        countries = [_get_lang().upper(), 'RO', 'US', 'GB']
        for country in countries:
            for entry in results:
                if entry.get('iso_3166_1') != country:
                    continue
                for rel in entry.get('release_dates') or []:
                    cert = norm(rel.get('certification'))
                    if cert:
                        return cert
    else:
        results = (data.get('content_ratings') or {}).get('results', [])
        countries = [_get_lang().upper(), 'RO', 'US', 'GB']
        for country in countries:
            for entry in results:
                if entry.get('iso_3166_1') == country:
                    cert = norm(entry.get('rating'))
                    if cert:
                        return cert
    return 'NR'


def widget_meta(tmdb_id, media='movie'):
    """Lightweight extra metadata for widget hero: logo, runtime, tagline, trailer_key."""
    lang = _get_lang()
    data = _get(f'/{media}/{tmdb_id}',
                append_to_response='images,videos,release_dates,content_ratings',
                include_image_language=f'en,{lang},null')
    logo = ''
    for lg in (data.get('images') or {}).get('logos', []):
        fp = lg.get('file_path', '')
        if fp and fp.lower().endswith('.png'):
            logo = f'{_IMG}w500{fp}'
            break
    runtime = data.get('runtime') or 0
    if not runtime:
        rts = data.get('episode_run_time') or []
        runtime = rts[0] if rts else 0
    tagline = data.get('tagline') or ''
    trailer_key = ''
    videos_data = (data.get('videos') or {}).get('results', [])
    for v in videos_data:
        if v.get('type') == 'Trailer' and v.get('site') == 'YouTube':
            trailer_key = v.get('key', '')
            break

    # TMDb often has no videos localized in Romanian. Match the MyPrime path
    # by retrying in English, then accept any YouTube video as a last resort.
    if not trailer_key:
        videos_data = _get(f'/{media}/{tmdb_id}/videos', language='en-US').get('results', [])
        for v in videos_data:
            if v.get('type') == 'Trailer' and v.get('site') == 'YouTube':
                trailer_key = v.get('key', '')
                break
        if not trailer_key:
            for v in videos_data:
                if v.get('site') == 'YouTube':
                    trailer_key = v.get('key', '')
                    break
    return {'logo': logo, 'runtime': runtime, 'tagline': tagline, 'trailer_key': trailer_key, 'age_cert': _age_cert_from_tmdb(data, media)}


def search(media='movie', query='', page=1):
    endpoint = '/search/movie' if media == 'movie' else '/search/tv'
    include_adult = xbmcaddon.Addon('plugin.video.samusxui').getSetting('use_adult') == 'true'
    return _get(endpoint, query=query, page=page, include_adult=str(include_adult).lower())


def season_details(tv_id, season_number):
    return _get(f'/tv/{tv_id}/season/{season_number}')


def still_url(path, size='w300'):
    return f'{_IMG}{size}{path}' if path else ''


def person_details(person_id):
    return _get(f'/person/{person_id}', append_to_response='combined_credits')


def profile_url(path, size='w342'):
    return f'{_IMG}{size}{path}' if path else ''


def genre_names(genre_ids, media='movie'):
    gmap = _GENRES_MOVIE if media == 'movie' else _GENRES_TV
    names = [gmap[g] for g in (genre_ids or []) if g in gmap]
    return '  •  '.join(names[:3])
