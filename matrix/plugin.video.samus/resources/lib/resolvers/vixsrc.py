# -*- coding: utf-8 -*-
import re
import requests
import xbmc
from urllib.parse import urlparse, urljoin, urlencode, parse_qsl, urlunparse

_BASE_URL = 'https://vixsrc.to'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
_HEADERS = {
    'User-Agent': _UA,
    'Referer': _BASE_URL + '/',
    'Accept-Encoding': 'gzip, deflate, br',  # exclude zstd — broken on this system
}


def _make_session():
    s = requests.Session()
    s.headers.update({'Accept-Encoding': 'gzip, deflate, br'})
    return s


def _merge_url_query(url, query_dict):
    if not query_dict:
        return url
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query))
    params.update(query_dict)
    parts = list(parsed)
    parts[4] = urlencode(params)
    return urlunparse(parts)


def _extract(tmdb_id, media_type, season=None, episode=None):
    if media_type == 'movie':
        page_url = '{}/movie/{}'.format(_BASE_URL, tmdb_id)
    else:
        page_url = '{}/tv/{}/{}/{}'.format(_BASE_URL, tmdb_id, season, episode)

    session = _make_session()

    # Try API endpoint for src redirect
    api_url = page_url.replace('/movie/', '/api/movie/').replace('/tv/', '/api/tv/')
    target_url = page_url
    try:
        r = session.get(api_url, headers=_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'src' in data:
                target_url = urljoin(_BASE_URL, data['src'])
    except Exception:
        pass

    fetch_headers = {'User-Agent': _UA, 'Referer': page_url, 'Accept-Encoding': 'gzip, deflate, br'}
    try:
        r = session.get(target_url, headers=fetch_headers, timeout=10)
    except Exception as e:
        xbmc.log('[Samus/VixSrc] fetch error: {}'.format(e), xbmc.LOGERROR)
        return None
    if r.status_code != 200:
        return None
    try:
        html = r.text
    except Exception as e:
        xbmc.log('[Samus/VixSrc] decompress error: {}'.format(e), xbmc.LOGERROR)
        return None

    tk_m = re.search(r"['\"]token['\"]\s*:\s*['\"](\w+)['\"]", html)
    if not tk_m:
        return _extract_fallback(page_url, html)

    tk = tk_m.group(1)
    url_m = re.search(r"(?:['\"]url['\"]|url)\s*:\s*['\"]([^'\"]+)['\"]", html)
    if not url_m:
        return _extract_fallback(page_url, html)

    raw_url = re.sub(r'\\u([0-9a-fA-F]{4})',
                     lambda m: chr(int(m.group(1), 16)),
                     url_m.group(1).replace('\\/', '/'))
    stream_url = re.sub(r'(/playlist/[^/?]+)(?!\.m3u8)(?=[?#]|$)', r'\1.m3u8', raw_url)

    q = {'token': tk}
    exp_m = re.search(r"['\"]expires['\"]\s*:\s*['\"](\d+)['\"]", html)
    if exp_m:
        q['expires'] = exp_m.group(1)
    if re.search(r'canPlayFHD\s*=\s*true', html):
        q['h'] = '1'

    final_url = _merge_url_query(stream_url, q)
    return '{}|Referer={}&Origin={}&User-Agent={}'.format(final_url, page_url, _BASE_URL, _UA)


def _extract_fallback(referer, html):
    for pattern in (
        r'(https?://[^\s\'"<>\)\]\}\\]+\.m3u8[^\s\'"<>\)\]\}\\]*)',
        r'(https?://[^\s\'"<>\)\]\}\\]+\.mp4[^\s\'"<>\)\]\}\\]*)',
    ):
        for m in re.findall(pattern, html):
            if 'ad' not in m.lower():
                return '{}|Referer={}&User-Agent={}'.format(m, referer, _UA)
    return None


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        url = _extract(tmdb_id, media_type, season, episode)
        if not url:
            return []
        return [{
            'url': url,
            'quality': '1080p',
            'title_line': 'VixSrc',
            'direct': True,
        }]
    except Exception as e:
        xbmc.log('[Samus/VixSrc] {}'.format(e), xbmc.LOGERROR)
        return []
