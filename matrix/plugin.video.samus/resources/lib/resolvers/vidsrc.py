# -*- coding: utf-8 -*-
import re
import requests
import xbmc

_LABEL = '[VS]'
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent': _UA,
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}

# Fallback CDN hostnames — se actualizează când rotesc
_CDN_VARS = {
    'v1': 'neonhorizonworkshops.com',
    'v2': 'cloudnestra.com',
    'v3': 'neonhorizonworkshops.com',
    'v4': 'neonhorizonworkshops.com',
    'v5': 'cloudnestra.com',
}


def _get(url, referer=None, timeout=12):
    h = dict(_HEADERS)
    if referer:
        h['Referer'] = referer
    try:
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        xbmc.log(f'[Samus/VidSrc] GET {url}: {e}', xbmc.LOGWARNING)
        return None


def _step1_vsembed(media_type, media_id, season=None, episode=None):
    """vidsrc.to → vsembed.ru iframe URL"""
    if media_type == 'tv' and season and episode:
        url = f'https://vidsrc.to/embed/tv/{media_id}/{season}/{episode}'
    else:
        url = f'https://vidsrc.to/embed/movie/{media_id}'

    html = _get(url)
    if not html:
        return None, url

    m = re.search(r'src=["\']([^"\']*vsembed\.ru[^"\']*)["\']', html)
    if not m:
        m = re.search(r'src=["\']([^"\']*embed[^"\']*)["\']', html)
    if not m:
        return None, url

    src = m.group(1)
    if src.startswith('//'):
        src = 'https:' + src
    return src, url


def _step2_rcp_hashes(vsembed_url, referer):
    """vsembed.ru → lista de data-hash"""
    html = _get(vsembed_url, referer=referer)
    if not html:
        return []
    return re.findall(r'data-hash=["\']([A-Za-z0-9+/=_\-]+)["\']', html)


def _step3_prorcp(rcp_hash, referer):
    """cloudnestra.com/rcp/{hash} → prorcp hash"""
    url = f'https://cloudnestra.com/rcp/{rcp_hash}'
    html = _get(url, referer=referer)
    if not html:
        return None
    m = re.search(r"['\"]\/prorcp\/([A-Za-z0-9+/=_\-]+)['\"]", html)
    return m.group(1) if m else None


def _step4_m3u8(prorcp_hash, rcp_url):
    """cloudnestra.com/prorcp/{hash} → URL-uri m3u8"""
    url = f'https://cloudnestra.com/prorcp/{prorcp_hash}'
    html = _get(url, referer=rcp_url)
    if not html:
        return []

    # Extrage URL-urile CDN vars din JS obfuscat dacă e posibil
    cdn_vars = dict(_CDN_VARS)
    js_path = re.search(r"document\.write\([^)]*src='(/[a-f0-9]+\.js\?[^']+)'", html)
    if js_path:
        _try_resolve_cdn_vars(f'https://cloudnestra.com{js_path.group(1)}', cdn_vars)

    file_m = re.search(r'file:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
    if not file_m:
        file_m = re.search(r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
    if not file_m:
        return []

    raw_urls = [u.strip() for u in file_m.group(1).split(' or ')]
    results = []
    seen = set()
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


def _try_resolve_cdn_vars(js_url, cdn_vars):
    """Încearcă să extragă hostname-urile CDN din JS-ul obfuscat (best-effort)."""
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


def _scrape(media_type, media_id, season=None, episode=None):
    vsembed_url, vidsrc_url = _step1_vsembed(media_type, media_id, season, episode)
    if not vsembed_url:
        xbmc.log(f'[Samus/VidSrc] vsembed URL negăsit pentru {media_id}', xbmc.LOGWARNING)
        return []

    hashes = _step2_rcp_hashes(vsembed_url, referer=vidsrc_url)
    if not hashes:
        xbmc.log(f'[Samus/VidSrc] Niciun data-hash găsit pentru {media_id}', xbmc.LOGWARNING)
        return []

    sources = []
    for srv_idx, rcp_hash in enumerate(hashes, start=1):
        prorcp = _step3_prorcp(rcp_hash, referer=vsembed_url)
        if not prorcp:
            continue
        rcp_url = f'https://cloudnestra.com/rcp/{rcp_hash}'
        m3u8_urls = _step4_m3u8(prorcp, rcp_url)
        for url_idx, url in enumerate(m3u8_urls):
            label = f'Server {srv_idx}' if len(m3u8_urls) == 1 else f'Server {srv_idx}.{url_idx + 1}'
            playback_url = f'{url}|User-Agent={_UA}&Referer=https://cloudnestra.com/'
            sources.append({
                'label':      f'{_LABEL} {label}',
                'title_line': label,
                'url':        playback_url,
                'direct':     True,
            })

    return sources


def get_vidsrc_sources(tmdb_id):
    sources = _scrape('movie', str(tmdb_id))
    xbmc.log(f'[Samus/VidSrc] {len(sources)} surse film pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources


def get_vidsrc_tv_sources(tmdb_id, season, episode):
    sources = _scrape('tv', str(tmdb_id), season, episode)
    xbmc.log(f'[Samus/VidSrc] {len(sources)} surse TV pentru tmdb={tmdb_id} S{season}E{episode}', xbmc.LOGINFO)
    return sources
