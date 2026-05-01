# -*- coding: utf-8 -*-
import requests
import xbmc

_BASE    = 'https://server.nhdapi.xyz'
_LABEL   = '[NHD]'
_SERVERS = ['flixhq', 'hollymoviehd']
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer': 'https://nhdapi.xyz/',
    'Accept': '*/*',
}


def _fetch(server, media_path):
    try:
        r = requests.get(f'{_BASE}/{server}/{media_path}', headers=_HEADERS, timeout=5)
        if not r.ok:
            return None
        url = r.json().get('url')
        return url if url and url.startswith('http') else None
    except Exception as e:
        xbmc.log(f'[Samus/NHDAPI] {server}: {e}', xbmc.LOGWARNING)
        return None


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    if media_type == 'movie':
        media_path = f'movie/{tmdb_id}'
    else:
        media_path = f'tv/{tmdb_id}/season/{season}/episode/{episode}'

    sources = []
    for server in _SERVERS:
        url = _fetch(server, media_path)
        if not url:
            continue
        sources.append({
            'url':        url,
            'provider':   _LABEL,
            'quality':    '',
            'title_line': server,
            'direct':     True,
        })

    xbmc.log(f'[Samus/NHDAPI] {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
