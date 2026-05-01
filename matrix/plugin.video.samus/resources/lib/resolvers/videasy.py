# -*- coding: utf-8 -*-
import requests
import xbmc

_LABEL       = '[VDY]'
_DB_BASE     = 'https://db.videasy.net/3'
_DB_API_KEY  = 'ad301b7cc82ffe19273e55e4d4206885'
_CDN_URL     = 'https://api.videasy.net/cdn/sources-with-title'
_DEC_URL     = 'https://enc-dec.app/api/dec-videasy'
_UA          = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
_CDN_HEADERS = {
    'User-Agent': _UA,
    'Origin':     'https://player.videasy.net',
    'Referer':    'https://player.videasy.net/',
}


def _get_meta(tmdb_id, media_type):
    type_path = 'tv' if media_type == 'tv' else 'movie'
    r = requests.get(
        f'{_DB_BASE}/{type_path}/{tmdb_id}',
        params={'append_to_response': 'external_ids', 'language': 'en', 'api_key': _DB_API_KEY},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    title   = data.get('name') or data.get('title') or ''
    date    = data.get('first_air_date') or data.get('release_date') or ''
    year    = int(date[:4]) if date else None
    imdb_id = (data.get('external_ids') or {}).get('imdb_id') or ''
    return title, year, imdb_id


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        title, year, imdb_id = _get_meta(tmdb_id, media_type)
        if not title:
            xbmc.log(f'{_LABEL} titlu lipsă pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        params = {
            'title':     title,
            'mediaType': 'tv' if media_type == 'tv' else 'movie',
            'year':      year or '',
            'episodeId': episode or 1,
            'seasonId':  season or 1,
            'tmdbId':    tmdb_id,
            'imdbId':    imdb_id,
        }
        r = requests.get(_CDN_URL, params=params, headers=_CDN_HEADERS, timeout=15)
        r.raise_for_status()
        encrypted = r.text

        dec = requests.post(_DEC_URL, json={'text': encrypted, 'id': str(tmdb_id)}, timeout=15)
        dec.raise_for_status()
        raw_sources = dec.json().get('result', {}).get('sources', [])
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []

    sources = []
    seen = set()
    for src in raw_sources:
        url = src.get('url')
        if not url or url in seen:
            continue
        seen.add(url)
        quality = src.get('quality') or 'Auto'
        sources.append({
            'url':        f'{url}|User-Agent={_UA}&Referer=https://player.videasy.net/&Origin=https://player.videasy.net',
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': f'Videasy {quality}',
            'direct':     True,
        })

    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
