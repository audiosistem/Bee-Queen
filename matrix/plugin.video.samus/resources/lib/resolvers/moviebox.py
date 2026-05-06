# -*- coding: utf-8 -*-
"""MovieBox — Cloudflare Worker cu stream-uri directe via TMDB ID."""
import re
import requests
import xbmc

_WORKER = 'https://moviebox.s4nch1tt.workers.dev'
_LABEL = '[MBX]'
_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'Nuvio/1.0',
}

_Q_TOKENS = [('4K', ('2160',)), ('1080p', ('1080',)), ('720p', ('720',)), ('480p', ('480',))]


def _guess_quality(res_str):
    for q, tokens in _Q_TOKENS:
        if any(t in res_str for t in tokens):
            return q
    return 'SD'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    m_type = 'tv' if media_type == 'tv' else 'movie'
    url = f'{_WORKER}/streams?tmdb_id={tmdb_id}&type={m_type}&proxy={_WORKER}'
    if media_type == 'tv':
        url += f'&se={season}&ep={episode}'
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        raw_streams = data if isinstance(data, list) else data.get('streams', [])
    except Exception as e:
        xbmc.log(f'[Samus/MovieBox] {e}', xbmc.LOGERROR)
        return []

    sources = []
    for s in raw_streams:
        stream_url = s.get('proxy_url') or s.get('url')
        if not stream_url:
            continue
        quality = _guess_quality(str(s.get('resolution', '')))
        lang_m = re.search(r'\(([^)]+)\)', s.get('name', ''))
        lang = lang_m.group(1) if lang_m else 'Original'
        codec = s.get('codec', '')
        title_parts = [p for p in [lang, codec] if p]
        size_mb = s.get('size_mb')
        try:
            size_str = f'{float(size_mb):.0f} MB' if size_mb and float(size_mb) > 0 else None
        except (TypeError, ValueError):
            size_str = None
        sources.append({
            'url': stream_url,
            'provider': _LABEL,
            'quality': quality,
            'title_line': ' | '.join(title_parts),
            'size': size_str,
            'direct': True,
        })

    xbmc.log(f'[Samus/MovieBox] {len(sources)} surse pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return sources
