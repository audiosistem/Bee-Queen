# -*- coding: utf-8 -*-
import re
import threading
import requests
import xbmc

_BASE    = 'https://filmehd.one'
_API     = f'{_BASE}/api'
_LABEL   = '[FHD]'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Referer':    _BASE + '/',
}

_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_CENTER_RE = re.compile(r'<center>([^<]+)</center>', re.IGNORECASE)
_EP_RE     = re.compile(r'episodul\s*(\d+)', re.IGNORECASE)
_Q_RE      = re.compile(r'(4k|2160p|1080p|720p|480p|360p)', re.IGNORECASE)
_Q_NORM    = {'4k': '4K', '2160p': '4K', '1080p': '1080p', '720p': '720p', '480p': '480p', '360p': '360p'}

_STREAM_RES = [
    re.compile(r'["\']?(?:file|src)["\']?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'["\']?(?:file|src)["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',  re.IGNORECASE),
    re.compile(r'source\s+src=["\']([^"\']+\.m3u8[^"\']*)["\']',                   re.IGNORECASE),
    re.compile(r'source\s+src=["\']([^"\']+\.mp4[^"\']*)["\']',                    re.IGNORECASE),
]


def _guess_quality(url):
    m = _Q_RE.search(url)
    return _Q_NORM.get(m.group(1).lower(), '') if m else ''


def _clean_url(url):
    if url.startswith('///') or (url.startswith('/') and not url.startswith('//')):
        return None
    if url.startswith('//'):
        url = 'https:' + url
    return url if url.startswith('http') else None


def _url_accessible(url):
    """HEAD check — returns True only if the CDN confirms the URL is live."""
    try:
        r = requests.head(
            url,
            headers={'User-Agent': _HEADERS['User-Agent'], 'Range': 'bytes=0-0'},
            timeout=5,
            allow_redirects=True,
        )
        return r.status_code < 400
    except Exception:
        return False


def _resolve_embed(embed_url):
    """Fetch embed page and extract a live direct m3u8/mp4 URL."""
    try:
        r = requests.get(embed_url, headers=_HEADERS, timeout=10, allow_redirects=True)
        html = r.text
        candidates = []
        for pattern in _STREAM_RES:
            for m in pattern.finditer(html):
                u = m.group(1)
                if u.startswith('//'):
                    u = 'https:' + u
                if u.startswith('http'):
                    candidates.append(u)
        for url in candidates:
            if _url_accessible(url):
                return url
    except Exception as e:
        xbmc.log(f'[Samus/FilmeHD] resolve_embed {embed_url}: {e}', xbmc.LOGWARNING)
    return None


def _resolve_all(sources):
    """Resolve all embed URLs in parallel. Returns only successfully resolved sources."""
    resolved = []
    lock = threading.Lock()

    def _worker(src):
        direct_url = _resolve_embed(src['url'])
        entry = dict(src)
        if direct_url:
            entry['url']    = direct_url
            entry['direct'] = True
            q = _guess_quality(direct_url)
            if q:
                entry['quality'] = q
        # else: keep original embed URL with direct=False → resolveurl fallback
        with lock:
            resolved.append(entry)

    threads = [threading.Thread(target=_worker, args=(s,)) for s in sources]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=12)
    return resolved


def _parse_embed(embed_html):
    centers = _CENTER_RE.findall(embed_html)
    iframes = _IFRAME_RE.findall(embed_html)
    sources = []
    for i, raw_url in enumerate(iframes):
        url = _clean_url(raw_url)
        if not url:
            continue
        label = centers[i].strip() if i < len(centers) else f'Player {i + 1}'
        sources.append({
            'url':        url,
            'provider':   _LABEL,
            'quality':    '',
            'title_line': label,
            'direct':     False,
        })
    return sources


def _parse_players(players, episode):
    """Extract sources for a specific episode from acf.players[] (miniseries)."""
    sources = []
    for player in players:
        player_label = player.get('label', 'Player')
        content      = player.get('content', '')
        centers      = _CENTER_RE.findall(content)
        iframes      = _IFRAME_RE.findall(content)
        for i, raw_url in enumerate(iframes):
            if i >= len(centers):
                continue
            m = _EP_RE.search(centers[i])
            if not m or int(m.group(1)) != episode:
                continue
            url = _clean_url(raw_url)
            if not url:
                continue
            sources.append({
                'url':        url,
                'provider':   _LABEL,
                'quality':    '',
                'title_line': player_label,
                'direct':     False,
            })
    return sources


def _fetch(endpoint):
    try:
        r = requests.get(endpoint, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        xbmc.log(f'[Samus/FilmeHD] {e}', xbmc.LOGERROR)
        return None


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    data = _fetch(f'{_API}/movie/{tmdb_id}')
    if not data:
        return []

    acf     = data.get('acf') or {}
    players = acf.get('players') or []

    if players and media_type == 'tv':
        sources = _parse_players(players, episode)
    else:
        embed_html = acf.get('embed') or data.get('embed') or ''
        sources = _parse_embed(embed_html)

    if not sources:
        xbmc.log(f'[Samus/FilmeHD] Fără surse pentru tmdb_id={tmdb_id}', xbmc.LOGWARNING)
        return []

    resolved = _resolve_all(sources)
    xbmc.log(f'[Samus/FilmeHD] {len(resolved)}/{len(sources)} surse rezolvate pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return resolved
