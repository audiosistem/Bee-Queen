# -*- coding: utf-8 -*-
import os
import requests
import xbmc

_LABEL   = '[HXA]'
_BASE    = 'https://theemoviedb.hexa.su'
_ENC_URL = 'https://enc-dec.app/api/enc-hexa'
_DEC_URL = 'https://enc-dec.app/api/dec-hexa'
_UA      = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
_FP      = 'e9136c41504646444'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        key = os.urandom(32).hex()

        token_r = requests.get(_ENC_URL, timeout=10)
        token_r.raise_for_status()
        token = token_r.json().get('result', {}).get('token', '')
        if not token:
            xbmc.log(f'{_LABEL} token lipsă', xbmc.LOGWARNING)
            return []

        if media_type == 'tv':
            url = f'{_BASE}/api/tmdb/tv/{tmdb_id}/season/{season}/episode/{episode}/images'
        else:
            url = f'{_BASE}/api/tmdb/movie/{tmdb_id}/images'

        headers = {
            'User-Agent':        _UA,
            'Accept':            'text/plain',
            'X-Api-Key':         key,
            'X-Fingerprint-Lite': _FP,
            'Referer':           'https://hexa.su/',
            'X-Cap-Token':       token,
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()

        dec = requests.post(_DEC_URL, json={'text': r.text, 'key': key},
                            headers={'Content-Type': 'application/json'}, timeout=15)
        dec.raise_for_status()
        raw_sources = dec.json().get('result', {}).get('sources', [])
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []

    sources = []
    seen = set()
    for src in raw_sources:
        m3u8 = src.get('url')
        if not m3u8 or m3u8 in seen:
            continue
        seen.add(m3u8)
        server = (src.get('server') or 'auto').upper()
        sources.append({
            'url':        f'{m3u8}|User-Agent={_UA}&Referer=https://hexa.su/',
            'provider':   _LABEL,
            'quality':    '1080p',
            'title_line': f'Hexa {server}',
            'direct':     True,
        })

    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
