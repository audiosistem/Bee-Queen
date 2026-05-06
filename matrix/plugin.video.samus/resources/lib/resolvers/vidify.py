# -*- coding: utf-8 -*-
"""Vidify — pro.vidify.top embed → cloudnestra.com rcp → prorcp → m3u8"""
import re
import base64
import requests
import xbmc
from urllib.parse import urlparse

_LABEL = '[V]'
_BASE  = 'https://pro.vidify.top'
_UA    = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_CDN_DOMAINS = [
    'neonhorizonworkshops.com',
    'wanderlynest.com',
    'orchidpixelgardens.com',
    'cloudnestra.com',
]


def _cdn_name(url):
    h = urlparse(url).netloc
    parts = h.split('.')
    return parts[-2] if len(parts) >= 2 else (h or 'Vidify')


def _infer_quality(url):
    u = url.lower()
    if re.search(r'(2160|4k|uhd)', u):  return '4K'
    if '1080' in u:                      return '1080p'
    if '720'  in u:                      return '720p'
    if '480'  in u:                      return '480p'
    if '360'  in u:                      return '360p'
    return 'auto'


def _session():
    s = requests.Session()
    s.headers.update({'User-Agent': _UA, 'Accept-Language': 'en-US,en;q=0.9'})
    return s


def _resolve_cdn(tmpl):
    seen = set()
    out = []
    for domain in _CDN_DOMAINS:
        url = re.sub(r'\{v\d+\}', domain, tmpl)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _decode_server(b64):
    padded = b64 + '=' * (-len(b64) % 4)
    url = base64.b64decode(padded).decode('utf-8', errors='ignore').strip('\x00')
    # double-encoded uneori
    if url.startswith('aHR0'):
        url = base64.b64decode(url + '=' * (-len(url) % 4)).decode('utf-8', errors='ignore')
    return url if url.startswith('http') else None


def _follow_rcp(sess, rcp_url, referer):
    try:
        r2 = sess.get(rcp_url, headers={'Referer': referer, 'Accept': 'text/html'},
                      timeout=15, verify=False)
        if not r2.ok or len(r2.text) < 100:
            return []
        if 'turnstile' in r2.text.lower():
            xbmc.log(f'{_LABEL} Turnstile pe {rcp_url[:60]}', xbmc.LOGWARNING)
            return []

        src_m = re.search(r"src:\s*['\"](/(?:prorcp|srcrcp)/[^'\"]+)['\"]", r2.text)
        if not src_m:
            return []

        from urllib.parse import urlparse
        base = f"{urlparse(rcp_url).scheme}://{urlparse(rcp_url).netloc}"
        r3 = sess.get(base + src_m.group(1),
                      headers={'Referer': base + '/', 'Accept': '*/*'},
                      timeout=15, verify=False)
        if not r3.ok:
            return []

        file_m = re.search(r'file:\s*["\']([^"\']+)["\']', r3.text)
        if not file_m:
            direct = re.findall(r'["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)["\']?', r3.text)
            return direct[:3]

        raw_urls = [u.strip() for u in file_m.group(1).split(' or ')]
        direct   = [u for u in raw_urls if '{v' not in u and '.m3u8' in u]
        templates = list(dict.fromkeys(u for u in raw_urls if '{v' in u and '.m3u8' in u))

        sources = list(dict.fromkeys(direct))
        for tmpl in templates:
            for resolved in _resolve_cdn(tmpl):
                if resolved not in sources:
                    sources.append(resolved)
        return sources

    except Exception as e:
        xbmc.log(f'{_LABEL} rcp eroare: {e}', xbmc.LOGWARNING)
        return []


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        sess = _session()
        if media_type == 'tv':
            embed_url = f'{_BASE}/embed/tv/{tmdb_id}/{season}/{episode}'
        else:
            embed_url = f'{_BASE}/embed/movie/{tmdb_id}'

        r = sess.get(embed_url, headers={'Accept': 'text/html', 'Referer': _BASE + '/'},
                     timeout=15, verify=False)
        if not r.ok or len(r.text) < 1000:
            xbmc.log(f'{_LABEL} embed fail tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        servers = re.findall(r'data-server=["\']([^"\']+)["\']', r.text)
        if not servers:
            xbmc.log(f'{_LABEL} niciun data-server pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        all_m3u8 = []
        for b64 in servers:
            rcp_url = _decode_server(b64)
            if not rcp_url:
                continue
            for url in _follow_rcp(sess, rcp_url, embed_url):
                if url not in all_m3u8:
                    all_m3u8.append(url)

    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGERROR)
        return []

    sources = [{
        'url':        f'{u}|User-Agent={_UA}&Referer=https://cloudnestra.com/',
        'quality':    '1080p',
        'title_line': _cdn_name(u),
        'direct':     True,
    } for u in all_m3u8]

    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources


# Alias-uri pentru compatibilitate cu player.py
def get_vidify_movie_sources(tmdb_id, imdb_id=None):
    return get_sources(tmdb_id, 'movie')


def get_vidify_tv_episode_sources(tmdb_id, imdb_id=None, season=None, episode=None):
    return get_sources(tmdb_id, 'tv', season, episode)
