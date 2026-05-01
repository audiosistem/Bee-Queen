# -*- coding: utf-8 -*-
"""MultiEmbed / SuperEmbed resolver — multiembed.mov"""
import re
import requests
import xbmc

_LABEL   = '[MEB]'
_BASE    = 'https://multiembed.mov'
_UA      = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Referer':         _BASE + '/',
    'Accept':          'text/html,application/xhtml+xml,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
}


def _embed_url(tmdb_id, media_type, season=None, episode=None):
    if media_type == 'tv':
        return f'{_BASE}/?video_id={tmdb_id}&tmdb=1&s={season}&e={episode}'
    return f'{_BASE}/?video_id={tmdb_id}&tmdb=1'


def _extract_stream(html, referer):
    """Extrage URL m3u8/mp4 din pagina JWPlayer sau din configurație JSON."""
    # JWPlayer setup: file: "https://..."
    m = re.search(r'"?file"?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
    if m:
        return m.group(1)
    # Fallback: orice m3u8 în HTML
    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
    if m:
        return m.group(1)
    # MP4 fallback
    m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
    if m:
        return m.group(1)
    return None


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        url = _embed_url(tmdb_id, media_type, season, episode)
        r = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        r.raise_for_status()
        stream_url = _extract_stream(r.text, url)
        if not stream_url:
            xbmc.log(f'{_LABEL} stream negăsit pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []
        full_url = f'{stream_url}|User-Agent={_UA}&Referer={url}'
        xbmc.log(f'{_LABEL} 1 sursă pentru tmdb={tmdb_id}', xbmc.LOGINFO)
        return [{
            'url':        full_url,
            'provider':   _LABEL,
            'quality':    'Auto',
            'title_line': 'MultiEmbed',
            'direct':     True,
        }]
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []
