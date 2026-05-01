# -*- coding: utf-8 -*-
import json
import requests
import xbmc
from urllib.parse import quote

_BASE  = 'https://api.pulp.watch/v1'
_LABEL = '[PLW]'
_UA    = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def _direct_url(url, headers):
    ua = headers.get('User-Agent') or _UA
    referer = headers.get('referer') or headers.get('Referer') or ''
    parts = [f'User-Agent={ua}']
    if referer:
        parts.append(f'Referer={referer}')
    return url + '|' + '&'.join(parts)


def _proxy_url(url, headers):
    data = json.dumps({'url': url, 'headers': headers}, separators=(',', ':'))
    return f'{_BASE}/proxy?data={quote(data)}'


def _parse(data):
    sources = []
    for src in data.get('sources', []):
        url = src.get('url')
        if not url:
            continue
        quality = src.get('quality') or 'Unknown'
        if quality == 'unknown':
            quality = 'Unknown'
        provider_name = (src.get('provider') or {}).get('name') or 'Unknown'
        headers = src.get('headers') or {}
        sources.append({
            'url': _direct_url(url, headers),
            '_proxy_url': _proxy_url(url, headers),
            'provider': _LABEL,
            'quality': quality,
            'title_line': provider_name,
            'direct': True,
        })
    return sources


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        if media_type == 'movie':
            endpoint = f'{_BASE}/movies/{tmdb_id}'
        else:
            endpoint = f'{_BASE}/tv/{tmdb_id}/seasons/{season}/episodes/{episode}'
        r = requests.get(endpoint, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        xbmc.log(f'[Samus/PulpWatch] {e}', xbmc.LOGERROR)
        return []
    sources = _parse(data)
    xbmc.log(f'[Samus/PulpWatch] {len(sources)} surse pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return sources
