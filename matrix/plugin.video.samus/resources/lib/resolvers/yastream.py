# -*- coding: utf-8 -*-
import requests
import xbmc

# Config prefix cu toți providerii activi: kisskh, onetouchtv, idrama, kkphim, ophim
_BASE = (
    'https://yastream.tamthai.de'
    '/eyJjYXRhbG9ncyI6WyJraXNza2guc2VyaWVzLktvcmVhbiIsIm9uZXRvdWNodHYuc2VyaWVzLktvce'
    'VhbiIsImtpc3NraC5zZXJpZXMuU2VhcmNoIiwia2lzc2toLm1vdmllLlNlYXJjaCIsIm9uZXRvdWNo'
    'dHYuc2VyaWVzLlNlYXJjaCIsImlkcmFtYS5zZXJpZXMuaURyYW1hIiwiaWRyYW1hLnNlcmllcy5TZW'
    'FyY2giXSwiY2F0YWxvZyI6WyJraXNza2giLCJvbmV0b3VjaHR2Il0sInN0cmVhbSI6WyJraXNza2gi'
    'LCJvbmV0b3VjaHR2IiwiaWRyYW1hIiwia2twaGltIiwib3BoaW0iXSwibnNmdyI6dHJ1ZSwiaW5mbyi'
    '6dHJ1ZX0='
)
_LABEL   = '[YAS]'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}

_Q_MAP = {
    '4k': '4K', '2160p': '4K',
    '1080p': '1080p', 'fhd': '1080p',
    '720p': '720p', 'hd': '720p',
    '480p': '480p', 'sd': '480p',
}


def _parse_quality(name):
    n = (name or '').lower()
    for k, v in _Q_MAP.items():
        if k in n:
            return v
    return ''


def _parse_provider(name):
    for prov in ('kisskh', 'onetouchtv', 'idrama', 'kkphim', 'ophim'):
        if prov in (name or '').lower():
            return prov
    return name.strip() if name else ''


def _fetch_streams(url):
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12)
        r.raise_for_status()
        return r.json().get('streams', [])
    except Exception as e:
        xbmc.log(f'[Samus/Yastream] {e}', xbmc.LOGWARNING)
        return []


def _build(raw_streams):
    sources = []
    for s in raw_streams:
        stream_url = s.get('url') or ''
        if not stream_url.startswith('http'):
            continue
        name     = s.get('name', '')
        quality  = _parse_quality(name)
        provider = _parse_provider(name)
        title    = provider or name.strip()

        extra_headers = (s.get('behaviorHints') or {}).get('proxyHeaders', {}).get('request', {})
        if extra_headers:
            h_str = '&'.join(f'{k}={v}' for k, v in extra_headers.items())
            stream_url = f'{stream_url}|{h_str}'

        sources.append({
            'url':        stream_url,
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': title,
            'direct':     True,
        })
    return sources


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    if not imdb_id:
        xbmc.log(f'[Samus/Yastream] imdb_id lipsă pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        return []

    if media_type == 'tv':
        if season is None or episode is None:
            return []
        sid = f'{imdb_id}:{season}:{episode}'
        url = f'{_BASE}/stream/series/{sid}.json'
    else:
        url = f'{_BASE}/stream/movie/{imdb_id}.json'

    raw = _fetch_streams(url)
    sources = _build(raw)
    xbmc.log(f'[Samus/Yastream] {len(sources)} surse pentru {imdb_id}', xbmc.LOGINFO)
    return sources
