# -*- coding: utf-8 -*-
"""MoviesAPI resolver — ww2.moviesapi.to / flixcdn.cyou"""
import json
import re
import requests
import xbmc

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad as _unpad
except ImportError:
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import unpad as _unpad
    except ImportError:
        AES = None

_LABEL   = '[MAPI]'
_BASE    = 'https://ww2.moviesapi.to'
_CDN     = 'https://flixcdn.cyou'
_AES_KEY = bytes.fromhex('6b69656d7469656e6d75613931316361')  # kiemtienmua911ca
_AES_IV  = bytes.fromhex('313233343536373839306f6975797472')  # 1234567890oiuytr
_UA      = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Accept':          'application/json, */*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer':         _BASE + '/',
    'Origin':          _BASE,
}


def _decrypt(raw: bytes):
    if AES is None:
        xbmc.log(f'{_LABEL} pycryptodome lipsă', xbmc.LOGWARNING)
        return None
    try:
        cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
        plaintext = _unpad(cipher.decrypt(bytes.fromhex(raw.decode('utf-8').strip())), AES.block_size)
        return json.loads(plaintext.decode('utf-8'))
    except Exception as e:
        xbmc.log(f'{_LABEL} decrypt eroare: {e}', xbmc.LOGWARNING)
        return None


def _fetch_video_data(embed_id: str):
    try:
        r = requests.get(f'{_CDN}/api/v1/video', params={'id': embed_id},
                         headers=_HEADERS, timeout=12)
        r.raise_for_status()
        return _decrypt(r.content)
    except Exception as e:
        xbmc.log(f'{_LABEL} flixcdn fetch eroare: {e}', xbmc.LOGWARNING)
        return None


def _stream_from_data(data) -> list:
    if not data:
        return []
    sources = []
    for key in ('source', 'hlsVideoTiktok', 'file', 'url', 'src', 'stream', 'hls'):
        val = data.get(key)
        if val and isinstance(val, str) and val.startswith('http'):
            sources.append((val, 'Auto'))
            break
    if not sources:
        for src in data.get('sources', data.get('streams', [])):
            url = src.get('file') or src.get('url') or src.get('src')
            if url:
                quality = src.get('label') or src.get('quality') or 'Auto'
                sources.append((url, quality))
    return sources


def _resolve_video_url(video_url: str) -> list:
    # mov2day CDN uses heavily obfuscated JS — not scrapable without a browser
    if 'mov2day' in video_url:
        xbmc.log(f'{_LABEL} mov2day skip (JS obfuscat)', xbmc.LOGINFO)
        return []

    # flixcdn: https://flixcdn.cyou/#embed_id&subs=...
    fragment = video_url.split('#', 1)[1] if '#' in video_url else ''
    embed_id = fragment.split('&')[0] if fragment else ''
    if not embed_id:
        m = re.search(r'/embed/([A-Za-z0-9_\-]+)', video_url)
        embed_id = m.group(1) if m else ''
    if not embed_id:
        xbmc.log(f'{_LABEL} embed_id negăsit în {video_url}', xbmc.LOGWARNING)
        return []

    data = _fetch_video_data(embed_id)
    return _stream_from_data(data)


def _build_sources(stream_pairs, tmdb_id) -> list:
    sources = []
    for url, quality in stream_pairs:
        full_url = f'{url}|User-Agent={_UA}&Referer={_CDN}/'
        sources.append({
            'url':        full_url,
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': f'MoviesAPI ({quality})',
            'direct':     True,
        })
    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        if media_type == 'movie':
            url = f'{_BASE}/api/movie/{tmdb_id}'
        else:
            url = f'{_BASE}/api/tv/{tmdb_id}/{season}/{episode}'

        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        video_url = data.get('video_url') or data.get('videoUrl') or data.get('url')
        if not video_url:
            xbmc.log(f'{_LABEL} video_url lipsă pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        stream_pairs = _resolve_video_url(video_url)
        return _build_sources(stream_pairs, tmdb_id)
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []
