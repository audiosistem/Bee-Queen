# -*- coding: utf-8 -*-
import xbmc
import requests

BASE_URL = 'https://media-proxy.vynx.workers.dev/flixer/extract-all'
HEADERS  = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}

_QUALITY_MAP = {'auto': '', '4k': '4K', '2160p': '4K', '1080p': '1080p', '720p': '720p', '480p': '480p'}


def _normalize_quality(q):
    return _QUALITY_MAP.get((q or '').lower(), q or '')


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    params = {'tmdbId': str(tmdb_id), 'type': 'tv' if media_type == 'tv' else 'movie'}
    if media_type == 'tv':
        if season is None or episode is None:
            return []
        params['season'] = str(season)
        params['episode'] = str(episode)
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data.get('success'):
            return []
        results = []
        for s in data.get('sources', []):
            url = s.get('url')
            if not url:
                continue
            referer = s.get('referer', '')
            if referer:
                url = '{}|Referer={}&User-Agent={}'.format(url, referer, HEADERS['User-Agent'])
            results.append({
                'url': url,
                'quality': _normalize_quality(s.get('quality')),
                'title_line': s.get('title', 'Flixer'),
                'size': None,
                'direct': True,
            })
        return results
    except Exception as e:
        xbmc.log('[Samus/Flixer] {}'.format(e), xbmc.LOGERROR)
        return []
