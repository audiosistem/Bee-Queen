# -*- coding: utf-8 -*-
"""vidbinge.to resolver — wraps vidora.stream embeds"""
import re
import json
import requests
import xbmc

_LABEL  = '[VBT]'
_BASE   = 'https://vidbinge.to'
_VIDORA = 'https://vidora.stream'
_UA     = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Accept':          'text/html,application/xhtml+xml,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
}


def _page_url(tmdb_id, media_type, season=None, episode=None):
    if media_type == 'tv':
        return f'{_BASE}/tv/{tmdb_id}/{season}/{episode}'
    return f'{_BASE}/movie/{tmdb_id}'


def _extract_vidora_urls(html):
    """Extract vidora.stream embed URLs from the sources JS array."""
    m = re.search(r'var\s+sources\s*=\s*(\[[^\]]+\])', html)
    if m:
        try:
            raw = m.group(1).replace('\\/', '/')
            return json.loads(raw)
        except Exception:
            pass
    # fallback: scan for any vidora embed URLs in the page
    return re.findall(r'https?://vidora\.stream/embed/[A-Za-z0-9]+', html)


def _resolve_vidora(embed_url, page_referer):
    """Resolve a vidora.stream embed URL to an actual stream."""
    # extract embed ID from URL
    m = re.search(r'/embed/([A-Za-z0-9]+)', embed_url)
    if not m:
        return None
    embed_id = m.group(1)

    session = requests.Session()
    session.headers.update(_HEADERS)

    # ── Step 1: fetch embed page to pick up any cookies / tokens ──────────
    try:
        r = session.get(embed_url, headers={'Referer': page_referer}, timeout=15, allow_redirects=True)
        xbmc.log(f'{_LABEL} vidora embed HTTP {r.status_code} for {embed_id}', xbmc.LOGDEBUG)
        html = r.text
        xbmc.log(f'{_LABEL} vidora embed snippet: {html[:400]}', xbmc.LOGDEBUG)

        # ── Inline stream patterns ─────────────────────────────────────────
        for pat in [
            r'"?file"?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
            r'"src"\s*:\s*"(https?://[^"]+)"',
        ]:
            hit = re.search(pat, html)
            if hit:
                xbmc.log(f'{_LABEL} vidora inline stream: {hit.group(1)[:80]}', xbmc.LOGDEBUG)
                return hit.group(1)

        # ── Extract any JS-embedded API token / hash ───────────────────────
        token_m = re.search(r'(?:token|key|hash)\s*[=:]\s*["\']([A-Za-z0-9_\-]{20,})["\']', html)
        token = token_m.group(1) if token_m else None
    except Exception as e:
        xbmc.log(f'{_LABEL} vidora embed fetch eroare: {e}', xbmc.LOGWARNING)
        html = ''
        token = None

    # ── Step 2: try common API patterns ───────────────────────────────────
    api_headers = {
        'User-Agent':      _UA,
        'Accept':          'application/json, */*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer':         embed_url,
        'Origin':          _VIDORA,
        'X-Requested-With': 'XMLHttpRequest',
    }

    # Pattern A: POST /api/source/{id}  (doodstream / streamtape style)
    try:
        payload = {'r': page_referer, 'd': _VIDORA}
        if token:
            payload['token'] = token
        r2 = session.post(f'{_VIDORA}/api/source/{embed_id}', headers=api_headers,
                          data=payload, timeout=12)
        xbmc.log(f'{_LABEL} vidora POST /api/source HTTP {r2.status_code}: {r2.text[:200]}', xbmc.LOGDEBUG)
        if r2.status_code == 200:
            d = r2.json()
            if d.get('success') and d.get('data'):
                for src in d['data']:
                    if src.get('file'):
                        return src['file']
    except Exception as e:
        xbmc.log(f'{_LABEL} vidora POST /api/source eroare: {e}', xbmc.LOGDEBUG)

    # Pattern B: GET /api/v1/video/{id}
    try:
        r3 = session.get(f'{_VIDORA}/api/v1/video/{embed_id}', headers=api_headers, timeout=12)
        xbmc.log(f'{_LABEL} vidora GET /api/v1/video HTTP {r3.status_code}: {r3.text[:200]}', xbmc.LOGDEBUG)
        if r3.status_code == 200:
            d = r3.json()
            for key in ('url', 'file', 'src', 'stream'):
                if d.get(key):
                    return d[key]
            # nested sources list
            for src in d.get('sources', []):
                if isinstance(src, dict) and src.get('file'):
                    return src['file']
                if isinstance(src, str) and ('m3u8' in src or 'mp4' in src):
                    return src
    except Exception as e:
        xbmc.log(f'{_LABEL} vidora GET /api/v1/video eroare: {e}', xbmc.LOGDEBUG)

    # Pattern C: GET /api/stream/{id}
    try:
        r4 = session.get(f'{_VIDORA}/api/stream/{embed_id}', headers=api_headers, timeout=12)
        xbmc.log(f'{_LABEL} vidora GET /api/stream HTTP {r4.status_code}: {r4.text[:200]}', xbmc.LOGDEBUG)
        if r4.status_code == 200:
            d = r4.json()
            for key in ('url', 'file', 'src', 'stream', 'hls'):
                if d.get(key):
                    return d[key]
    except Exception as e:
        xbmc.log(f'{_LABEL} vidora GET /api/stream eroare: {e}', xbmc.LOGDEBUG)

    xbmc.log(f'{_LABEL} vidora: niciun pattern API n-a funcționat pentru {embed_id}', xbmc.LOGWARNING)
    return None


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        page_url = _page_url(tmdb_id, media_type, season, episode)
        r = requests.get(page_url, headers=_HEADERS, timeout=15, allow_redirects=True)
        r.raise_for_status()
        xbmc.log(f'{_LABEL} vidbinge.to HTTP {r.status_code} pentru tmdb={tmdb_id}', xbmc.LOGDEBUG)
        vidora_urls = _extract_vidora_urls(r.text)
        xbmc.log(f'{_LABEL} vidora URLs găsite: {vidora_urls}', xbmc.LOGDEBUG)
        if not vidora_urls:
            xbmc.log(f'{_LABEL} nicio sursă vidora.stream pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []
        sources = []
        for embed_url in vidora_urls[:3]:
            stream_url = _resolve_vidora(embed_url, page_url)
            if stream_url:
                full_url = f'{stream_url}|User-Agent={_UA}&Referer={embed_url}'
                sources.append({
                    'url':        full_url,
                    'provider':   _LABEL,
                    'quality':    'Auto',
                    'title_line': 'VidBinge.to',
                    'direct':     True,
                })
        xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
        return sources
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []
