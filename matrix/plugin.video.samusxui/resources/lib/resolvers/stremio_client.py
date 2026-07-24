# -*- coding: utf-8 -*-
"""Generic Stremio addon client — calls /stream/{type}/{id}.json on any endpoint."""
import re
import requests
import xbmc

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Encoding': 'gzip, deflate',
}

_Q_TOKENS = [
    ('4K',    ('2160p', '4k', 'uhd')),
    ('1080p', ('1080p', '1080i', 'fhd')),
    ('720p',  ('720p',)),
    ('480p',  ('480p', 'sd')),
]


def _guess_quality(text):
    t = text.lower()
    for q, tokens in _Q_TOKENS:
        if any(tok in t for tok in tokens):
            return q
    return ''


def _parse_meta(text):
    seeds = None
    size = None
    m = re.search(r'👤\s*(\d+)', text)
    if m:
        seeds = int(m.group(1))
    m = re.search(r'💾\s*([\d.]+\s*\S+)', text)
    if m:
        size = m.group(1).strip()
    return seeds, size


def _parse_streams(streams, label):
    results = []
    for s in streams:
        info_hash = s.get('infoHash')
        if not info_hash:
            continue
        trackers = [src for src in s.get('sources', []) if src.startswith('tracker:')]
        name_raw  = s.get('name', '').strip()
        title_raw = s.get('title', '').strip()
        title_line = title_raw.split('\n')[0] if title_raw else ''
        seeds, size = _parse_meta(title_raw)
        quality = _guess_quality(title_line)
        results.append({
            'infoHash':     info_hash.lower(),
            'fileIdx':      s.get('fileIdx', 0),
            'trackers':     trackers,
            'provider':     label,
            'quality':      quality,
            'title_line':   title_line,
            'display_name': name_raw or title_line,
            'seeds':        seeds,
            'size':         size,
        })
    return results


def _is_expired_signed_url(url):
    """Returnează True dacă URL-ul conține un token AWS pre-semnat expirat."""
    if 'X-Amz-Expires' not in url:
        return False
    try:
        from urllib.parse import urlparse, parse_qs
        from datetime import datetime, timezone
        params = parse_qs(urlparse(url).query)
        date_str = (params.get('X-Amz-Date') or [None])[0]
        expires_s = (params.get('X-Amz-Expires') or [None])[0]
        if not date_str or not expires_s:
            return False
        sign_time = datetime.strptime(date_str, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        expiry = sign_time.timestamp() + int(expires_s)
        return expiry < datetime.now(timezone.utc).timestamp()
    except Exception:
        return False


_EMBED_HOSTS = (
    'filemoon.sx', 'streamwish.', 'wishembed.', 'streamtape.',
    'doodstream.', 'upstream.to', 'mixdrop.', 'supervideo.',
    'voe.sx', 'streamlare.', 'embedgram.', 'vidmoly.',
    'uqload.', 'vtbe.', 'vidhide.', 'vidoza.',
)


def _is_embed(url):
    u = url.lower()
    return any(h in u for h in _EMBED_HOSTS)


def _parse_direct_streams(streams, label):
    import traceback
    results = []
    for s in streams:
        try:
            url = s.get('url')
            if not url or not url.startswith('http'):
                continue
            if _is_expired_signed_url(url):
                continue
            # Skip pure torrent streams (infoHash without a direct HTTP URL)
            if s.get('infoHash') and not url.startswith('http'):
                continue

            # Support both standard 'title' and HDHub-style 'name'+'description'
            name_raw  = ' | '.join(p.strip() for p in (s.get('name') or '').split('\n') if p.strip())
            title_raw = (s.get('title') or name_raw).strip()
            desc_raw  = (s.get('description') or '').strip()
            title_line = title_raw.split('\n')[0] if title_raw else desc_raw.split('\n')[0] if desc_raw else ''

            # Skip unconfigured addon placeholders (e.g. Jackettio/Elfhosted)
            if 'configure' in title_line.lower() or 'configure' in name_raw.lower():
                continue

            quality = _guess_quality(name_raw + ' ' + title_raw + ' ' + desc_raw)

            size = None
            try:
                hints = s.get('behaviorHints') or {}
                size_bytes = hints.get('videoSize') if isinstance(hints, dict) else None
                if isinstance(size_bytes, (int, float)) and size_bytes > 0:
                    for unit, div in (('GB', 1024**3), ('MB', 1024**2), ('KB', 1024)):
                        if size_bytes >= div:
                            size = '{:.1f} {}'.format(size_bytes / div, unit)
                            break
            except Exception:
                pass
            if not size:
                m = re.search(r'([\d.]+\s*(?:GB|MB|KB))', desc_raw or title_raw, re.IGNORECASE)
                if m:
                    size = m.group(1).strip()

            # Append required request headers (e.g. User-Agent from proxyHeaders)
            try:
                hints = s.get('behaviorHints') or {}
                if isinstance(hints, dict):
                    req_hdrs = (hints.get('proxyHeaders') or {}).get('request') or {}
                    if isinstance(req_hdrs, dict) and req_hdrs:
                        hdr_str = '&'.join('{}={}'.format(k, v) for k, v in req_hdrs.items())
                        url = '{}|{}'.format(url, hdr_str)
            except Exception:
                pass

            entry = {
                'url':          url,
                'provider':     label,
                'quality':      quality,
                'title_line':   title_line,
                'display_name': name_raw or title_line,
                'size':         size,
                'direct':       not _is_embed(url),
            }
            subs = s.get('subtitles')
            if isinstance(subs, list):
                sub_urls = [sub['url'] for sub in subs if isinstance(sub, dict) and sub.get('url')]
                if sub_urls:
                    entry['subtitles'] = sub_urls
            results.append(entry)
        except Exception:
            xbmc.log('[Samus/{}] _parse_direct_streams stream err:\n{}'.format(label, traceback.format_exc()), xbmc.LOGERROR)
    return results


def get_movie_sources(base_url, imdb_id, label='Stremio', direct=False):
    url = f"{base_url.rstrip('/')}/stream/movie/{imdb_id}.json"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        streams = r.json().get('streams', [])
        parser = _parse_direct_streams if direct else _parse_streams
        return parser(streams, label)
    except Exception as e:
        xbmc.log(f'[Samus/{label}] film {imdb_id}: {e}', xbmc.LOGERROR)
        return []


def get_tv_sources(base_url, imdb_id, season, episode, label='Stremio', direct=False):
    url = f"{base_url.rstrip('/')}/stream/series/{imdb_id}:{season}:{episode}.json"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        streams = r.json().get('streams', [])
        parser = _parse_direct_streams if direct else _parse_streams
        return parser(streams, label)
    except Exception as e:
        xbmc.log(f'[Samus/{label}] serial {imdb_id} S{season}E{episode}: {e}', xbmc.LOGERROR)
        return []
