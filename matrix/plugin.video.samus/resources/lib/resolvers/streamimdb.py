# -*- coding: utf-8 -*-
"""StreamIMDb resolver — streamimdb.me embed → cloudnestra rcp/prorcp → m3u8"""
import re
import requests
import xbmc

_LABEL   = '[SIMDB]'
_BASE    = 'https://streamimdb.me'
_UA      = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept':          'text/html,application/xhtml+xml,*/*;q=0.8',
}

_CDN_VARS = {
    'v1': 'neonhorizonworkshops.com',
    'v2': 'cloudnestra.com',
    'v3': 'neonhorizonworkshops.com',
    'v4': 'neonhorizonworkshops.com',
    'v5': 'cloudnestra.com',
}


def _get(url, referer=None, timeout=15):
    h = dict(_HEADERS)
    if referer:
        h['Referer'] = referer
    try:
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        xbmc.log(f'{_LABEL} GET {url}: {e}', xbmc.LOGWARNING)
        return None


def _step1_hashes(imdb_id, media_type, season=None, episode=None):
    """streamimdb.me/embed/... → lista de data-hash + embed_url"""
    if media_type == 'tv':
        embed_url = f'{_BASE}/embed/tv/{imdb_id}/{season}/{episode}'
    else:
        embed_url = f'{_BASE}/embed/movie/{imdb_id}'

    html = _get(embed_url)
    if not html:
        return [], embed_url

    hashes = re.findall(r'data-hash=["\']([A-Za-z0-9+/=_\-]+)["\']', html)
    xbmc.log(f'{_LABEL} embed {embed_url} → {len(hashes)} hash-uri', xbmc.LOGDEBUG)
    return hashes, embed_url


def _step2_prorcp(rcp_hash, embed_url):
    """cloudnestra.com/rcp/{hash} → prorcp hash"""
    rcp_url = f'https://cloudnestra.com/rcp/{rcp_hash}'
    html = _get(rcp_url, referer=embed_url)
    if not html:
        return None, rcp_url
    m = re.search(r"['\"]\/prorcp\/([A-Za-z0-9+/=_\-]+)['\"]", html)
    return (m.group(1) if m else None), rcp_url


def _try_resolve_cdn_vars(js_url, cdn_vars):
    try:
        html = _get(js_url, referer='https://cloudnestra.com/')
        if not html:
            return
        hosts = re.findall(r'[a-z0-9\-]{3,}\.[a-z0-9\-]{2,}\.[a-z]{2,6}', html)
        seen = set()
        idx = 1
        for h in hosts:
            if h not in seen and not h.startswith('www.') and idx <= 5:
                cdn_vars[f'v{idx}'] = h
                seen.add(h)
                idx += 1
    except Exception:
        pass


def _step3_m3u8(prorcp_hash, rcp_url):
    """cloudnestra.com/prorcp/{hash} → URL-uri m3u8"""
    url = f'https://cloudnestra.com/prorcp/{prorcp_hash}'
    html = _get(url, referer=rcp_url)
    if not html:
        return []

    cdn_vars = dict(_CDN_VARS)
    js_path = re.search(r"document\.write\([^)]*src='(/[a-f0-9]+\.js\?[^']+)'", html)
    if js_path:
        _try_resolve_cdn_vars(f'https://cloudnestra.com{js_path.group(1)}', cdn_vars)

    file_m = re.search(r'file:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
    if not file_m:
        file_m = re.search(r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
    if not file_m:
        xbmc.log(f'{_LABEL} no m3u8 in prorcp (len={len(html)}) snippet={html[:200]!r}', xbmc.LOGDEBUG)
        return []

    raw_urls = [u.strip() for u in file_m.group(1).split(' or ')]
    results, seen = [], set()
    for raw in raw_urls:
        resolved = raw
        for k, v in cdn_vars.items():
            resolved = resolved.replace('{' + k + '}', v)
        if '{v' in resolved:
            continue
        if resolved not in seen and resolved.startswith('http'):
            seen.add(resolved)
            results.append(resolved)
    return results


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    if not imdb_id:
        return []
    if media_type == 'tv' and (season is None or episode is None):
        return []

    try:
        hashes, embed_url = _step1_hashes(imdb_id, media_type, season, episode)
        if not hashes:
            xbmc.log(f'{_LABEL} no hashes pentru {imdb_id}', xbmc.LOGWARNING)
            return []

        sources = []
        for srv_idx, rcp_hash in enumerate(hashes, start=1):
            prorcp, rcp_url = _step2_prorcp(rcp_hash, embed_url)
            if not prorcp:
                xbmc.log(f'{_LABEL} no prorcp pentru hash {rcp_hash[:12]}', xbmc.LOGDEBUG)
                continue
            m3u8_urls = _step3_m3u8(prorcp, rcp_url)
            for url_idx, url in enumerate(m3u8_urls):
                label = f'Server {srv_idx}' if len(m3u8_urls) == 1 else f'Server {srv_idx}.{url_idx + 1}'
                sources.append({
                    'url':        f'{url}|User-Agent={_UA}&Referer=https://cloudnestra.com/',
                    'provider':   _LABEL,
                    'quality':    '1080p',
                    'title_line': label,
                    'direct':     True,
                })

        xbmc.log(f'{_LABEL} {len(sources)} surse pentru {imdb_id}', xbmc.LOGINFO)
        return sources
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []
