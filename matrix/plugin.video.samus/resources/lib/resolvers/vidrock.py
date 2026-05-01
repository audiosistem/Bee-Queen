# -*- coding: utf-8 -*-
import base64
import requests
import xbmc

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

_BASE    = 'https://vidrock.net'
_PASS    = b'x7k9mPqT2rWvY8zA5bC3nF6hJ2lK4mN9'  # 32 bytes = AES-256 key
_UA      = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
_HEADERS = {'User-Agent': _UA, 'Referer': f'{_BASE}/', 'Origin': _BASE, 'Accept-Encoding': 'gzip, deflate'}
_LABEL   = '[VDR]'

_Q_TOKENS = [('4K', ('2160', '4k', 'uhd')), ('1080p', ('1080',)), ('720p', ('720',)), ('480p', ('480',))]


def _guess_quality(url):
    u = (url or '').lower()
    for q, tokens in _Q_TOKENS:
        if any(t in u for t in tokens):
            return q
    return '1080p'


def _encrypt_id(item_id):
    cipher = AES.new(_PASS, AES.MODE_CBC, _PASS[:16])
    ct = cipher.encrypt(pad(item_id.encode(), AES.block_size))
    return base64.urlsafe_b64encode(ct).decode().rstrip('=')


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if not _CRYPTO_OK:
        xbmc.log('[Samus/VidRock] pycryptodome indisponibil', xbmc.LOGWARNING)
        return []
    if media_type == 'tv' and (season is None or episode is None):
        return []

    item_id = str(tmdb_id) if media_type == 'movie' else f'{tmdb_id}_{season}_{episode}'
    api_type = 'movie' if media_type == 'movie' else 'tv'

    try:
        encoded = _encrypt_id(item_id)
        r = requests.get(f'{_BASE}/api/{api_type}/{encoded}', headers=_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        xbmc.log(f'[Samus/VidRock] {e}', xbmc.LOGERROR)
        return []

    sources = []
    for server_name, src in (data.items() if isinstance(data, dict) else []):
        if not isinstance(src, dict):
            continue
        url = src.get('url')
        if not url:
            continue
        quality = _guess_quality(url)
        lang = src.get('language') or ''
        title_line = f'{server_name} [{lang}]' if lang else server_name
        playback_url = f'{url}|User-Agent={_UA}&Referer={_BASE}/'
        sources.append({
            'url': playback_url,
            'provider': _LABEL,
            'quality': quality,
            'title_line': title_line,
            'size': None,
            'direct': True,
        })

    xbmc.log(f'[Samus/VidRock] {len(sources)} surse pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return sources
