# -*- coding: utf-8 -*-
import requests
import xbmc

_LABEL    = '[VDL]'
_ENC_URL  = 'https://enc-dec.app/api/enc-vidlink'
_API_BASE = 'https://vidlink.pro/api/b'
_UA       = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
_HEADERS  = {'User-Agent': _UA, 'Referer': 'https://vidlink.pro/', 'Accept': 'application/json'}


def _encode_id(tmdb_id):
    r = requests.get(_ENC_URL, params={'text': str(tmdb_id)}, timeout=10)
    r.raise_for_status()
    return r.json().get('result', '')


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        encoded = _encode_id(tmdb_id)
        if not encoded:
            return []
        if media_type == 'tv':
            url = f'{_API_BASE}/tv/{encoded}/{season}/{episode}?multiLang=0'
        else:
            url = f'{_API_BASE}/movie/{encoded}?multiLang=0'
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []

    stream = data.get('stream', {})
    playlist = stream.get('playlist')
    if not playlist:
        xbmc.log(f'{_LABEL} niciun playlist pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        return []

    sources = [{
        'url':        f'{playlist}|User-Agent={_UA}&Referer=https://vidlink.pro/',
        'provider':   _LABEL,
        'quality':    'Auto',
        'title_line': 'VidLink',
        'direct':     True,
    }]
    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
