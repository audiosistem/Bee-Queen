# -*- coding: utf-8 -*-
"""Consumet /meta/tmdb resolver — configurable public instance"""
import requests
import xbmcaddon
import xbmc

_LABEL   = '[CNS]'
_DEFAULT = 'https://api.consumet.org'
_UA      = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Accept':          'application/json',
    'Accept-Encoding': 'gzip, deflate, br',
}


def _base():
    try:
        url = xbmcaddon.Addon().getSetting('consumet_url') or _DEFAULT
        return url.rstrip('/')
    except Exception:
        return _DEFAULT


def _get(path, params=None, timeout=15):
    try:
        r = requests.get(f'{_base()}{path}', params=params,
                         headers=_HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        xbmc.log(f'{_LABEL} HTTP {r.status_code} {path}', xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f'{_LABEL} request eroare {path}: {e}', xbmc.LOGWARNING)
    return None


def _find_episode_id(info, season, episode):
    """Extract episode ID from /info response for a given S/E."""
    # Format 1: top-level episodes list (movies or flat TV)
    for ep in info.get('episodes', []):
        if ep.get('season') == season and ep.get('number') == episode:
            return ep.get('id')
        if ep.get('season') == season and ep.get('episode') == episode:
            return ep.get('id')

    # Format 2: nested seasons → episodes
    for s in info.get('seasons', []):
        if s.get('season') == season:
            for ep in s.get('episodes', []):
                if ep.get('number') == episode or ep.get('episode') == episode:
                    return ep.get('id')

    return None


def _build_sources(watch_data, tmdb_id) -> list:
    if not watch_data:
        return []
    sources = []
    referer = (watch_data.get('headers') or {}).get('Referer', '')
    for src in watch_data.get('sources', []):
        url = src.get('url') or src.get('file')
        if not url:
            continue
        quality = src.get('quality', 'Auto')
        header_str = f'User-Agent={_UA}'
        if referer:
            header_str += f'&Referer={referer}'
        sources.append({
            'url':        f'{url}|{header_str}',
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': f'Consumet ({quality})',
            'direct':     True,
        })
    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    media_param = 'movie' if media_type == 'movie' else 'tv'
    info = _get(f'/meta/tmdb/info/{tmdb_id}', params={'type': media_param})
    if not info:
        return []

    provider_id = info.get('id')
    if not provider_id:
        xbmc.log(f'{_LABEL} provider_id lipsă pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        return []

    if media_type == 'movie':
        # movies: first (and only) episode entry
        episodes = info.get('episodes', [])
        episode_id = episodes[0].get('id') if episodes else str(tmdb_id)
    else:
        episode_id = _find_episode_id(info, season, episode)
        if not episode_id:
            xbmc.log(f'{_LABEL} episod S{season:02d}E{episode:02d} negăsit pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

    watch = _get(f'/meta/tmdb/watch/{episode_id}', params={'id': provider_id})
    return _build_sources(watch, tmdb_id)
