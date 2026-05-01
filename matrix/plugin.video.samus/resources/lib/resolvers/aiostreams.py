# -*- coding: utf-8 -*-
import re
import requests
import xbmc
import xbmcaddon

_DEFAULT_URL = 'https://aiostreams.stremio.ru'
_LABEL = '[AIO]'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

_Q_MAP = [
    ('4K',    ('2160P', 'UHD', '4K')),
    ('1080p', ('1080P', '1080I', 'FHD')),
    ('720p',  ('720P',)),
    ('480p',  ('480P',)),
]


def _guess_quality(text):
    t = text.upper()
    for q, tokens in _Q_MAP:
        if any(tok in t for tok in tokens):
            return q
    return 'SD'


def _parse_size(size_bytes):
    if not size_bytes:
        return None
    try:
        b = float(size_bytes)
        for unit, div in (('TB', 1024**4), ('GB', 1024**3), ('MB', 1024**2), ('KB', 1024)):
            if b >= div:
                return f'{b / div:.1f} {unit}'
    except Exception:
        pass
    return None


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    addon = xbmcaddon.Addon()
    base_url = (addon.getSetting('aiostreams_url') or _DEFAULT_URL).strip().rstrip('/')
    m_type = 'series' if media_type in ('tv', 'show') else 'movie'

    if m_type == 'series' and season and episode:
        st_id = f'{imdb_id}:{season}:{episode}'
    else:
        st_id = str(imdb_id)

    try:
        r = requests.get(
            f'{base_url}/api/v1/search',
            params={'type': m_type, 'id': st_id},
            headers=_HEADERS, timeout=20, verify=False,
        )
        r.raise_for_status()
        results_raw = r.json().get('data', {}).get('results', [])
    except Exception as e:
        xbmc.log(f'[Samus/AIO] {e}', xbmc.LOGERROR)
        return []

    sources = []
    for item in results_raw:
        try:
            if 'p2p' in str(item.get('type', '')).lower():
                continue
            url = item.get('url', '')
            if not url or not url.startswith('http'):
                continue

            bh = item.get('behaviorHints') or {}
            parsed = item.get('parsedFile') or {}
            title = str(item.get('filename') or bh.get('filename') or parsed.get('filename') or '').strip()
            if not title:
                title = str(item.get('title', '')).split('\n')[0].strip()

            check = (str(parsed.get('resolution', '')) + ' ' + title + ' ' + str(item.get('title', ''))).upper()
            quality = _guess_quality(check)

            size_str = _parse_size(item.get('size') or bh.get('videoSize'))

            sources.append({
                'url': url,
                'provider': _LABEL,
                'quality': quality,
                'title_line': title,
                'size': size_str,
                'direct': True,
            })
        except Exception:
            continue

    xbmc.log(f'[Samus/AIO] {len(sources)} surse pentru {st_id}', xbmc.LOGINFO)
    return sources
