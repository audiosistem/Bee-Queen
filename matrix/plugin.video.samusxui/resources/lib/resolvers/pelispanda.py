# -*- coding: utf-8 -*-
"""PelisPanda.org resolver — torrent magnets + embeds via WP REST API"""
import re
import random
import socket
import struct
import threading
import requests
from urllib.parse import unquote, quote, urlparse
import xbmc

_LABEL = '[PPD]'
_BASE  = 'https://pelispanda.org/wp-json/wpreact/v1'
_UA    = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Accept':          'application/json',
    'Accept-Language': 'en-US,es;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
}


def _get(path, params=None, timeout=20):
    try:
        r = requests.get(f'{_BASE}{path}', params=params, headers=_HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        xbmc.log(f'{_LABEL} HTTP {r.status_code} {path}', xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f'{_LABEL} request eroare {path}: {e}', xbmc.LOGWARNING)
    return None


def _find_slug(title, tmdb_id, original_title=None):
    """Search by title and match by tmdb_id; tries multiple query variations.
    Returns (slug, item_type) or (None, None).
    """
    tmdb_str = str(tmdb_id)

    def _search(query):
        data = _get('/search', params={'query': query, 'posts_per_page': 20})
        if not data:
            return None
        for item in data.get('results', []):
            if item.get('tmdb_id') == tmdb_str:
                return item['slug'], item.get('type', '')
        return None

    # Build a list of query candidates from most-specific to least
    # original_title first (e.g. Spanish title for a Spanish site)
    candidates = []
    if original_title and original_title != title:
        candidates.append(original_title)
    candidates.append(title)

    # Strip subtitle (after ':' or '–')
    for sep in (':', '–', '-'):
        if sep in title:
            candidates.append(title.split(sep)[0].strip())
            break

    # Words longer than 5 chars — most distinctive
    long_words = [w for w in re.split(r'\W+', title) if len(w) > 5]
    if long_words:
        candidates.append(' '.join(long_words[:3]))
    # Last 3 words
    words = title.split()
    if len(words) > 3:
        candidates.append(' '.join(words[-3:]))

    seen = set()
    for q in candidates:
        q = q.strip()
        if not q or q in seen:
            continue
        seen.add(q)
        result = _search(q)
        if result:
            return result

    return None, None


def _parse_magnet(magnet_url):
    """Return (infoHash_upper, trackers_list) from a magnet URI."""
    m = re.search(r'xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})', magnet_url, re.IGNORECASE)
    if not m:
        return None, []
    info_hash = m.group(1).upper()
    trackers = [unquote(t) for t in re.findall(r'tr=([^&]+)', magnet_url)]
    return info_hash, trackers


def _scrape_udp(host, port, info_hash_bytes, timeout=3):
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        addr = (socket.gethostbyname(host), port)

        tid = random.randint(0, 0xFFFFFFFF)
        sock.sendto(struct.pack('>QII', 0x41727101980, 0, tid), addr)
        data = sock.recv(16)
        act, rtid, conn_id = struct.unpack('>IIQ', data)
        if act != 0 or rtid != tid:
            return None

        tid = random.randint(0, 0xFFFFFFFF)
        sock.sendto(struct.pack('>QII', conn_id, 2, tid) + info_hash_bytes, addr)
        data = sock.recv(20)
        act, rtid = struct.unpack('>II', data[:8])
        if act != 2 or rtid != tid:
            return None

        return struct.unpack('>I', data[8:12])[0]
    except Exception:
        return None
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def _fetch_seeders(info_hash_hex, trackers, timeout=2):
    """Query tracker scrape (HTTP + UDP) for seeder count. Returns int or None.
    Tries only the first viable tracker to keep latency low."""
    try:
        raw = bytes.fromhex(info_hash_hex)
    except Exception:
        return None
    ih_urlenc = quote(raw, safe='')

    # Try first HTTP tracker, then first UDP tracker — stop at first success
    http_tried = udp_tried = False
    for tracker in trackers:
        try:
            if not http_tried and tracker.startswith('http'):
                http_tried = True
                scrape_url = re.sub(r'/announce(\?.*)?$', '/scrape', tracker)
                if scrape_url != tracker:
                    r = requests.get(f'{scrape_url}?info_hash={ih_urlenc}',
                                     headers=_HEADERS, timeout=timeout)
                    if r.status_code == 200:
                        m = re.search(rb'8:completei(\d+)e', r.content)
                        if m:
                            return int(m.group(1))
            elif not udp_tried and tracker.startswith('udp://'):
                udp_tried = True
                parsed = urlparse(tracker)
                host = parsed.hostname
                port = parsed.port or 1337
                if host:
                    result = _scrape_udp(host, port, raw, timeout=timeout)
                    if result is not None:
                        return result
        except Exception:
            continue
        if http_tried and udp_tried:
            break
    return None


def _quality_from_str(quality_str):
    """Normalise quality label to 4K/1080p/720p/etc."""
    q = (quality_str or '').lower()
    for res in ('2160p', '4k', '1080p', '720p', '480p', '360p'):
        if res in q:
            return res.upper() if res == '4k' else res
    return quality_str or 'Auto'


def _build_torrent_sources(downloads):
    # Parse all magnets first
    parsed = []
    for dl in downloads:
        magnet = dl.get('download_link', '')
        if not magnet.startswith('magnet:'):
            continue
        info_hash, trackers = _parse_magnet(magnet)
        if not info_hash:
            continue
        parsed.append((info_hash, trackers, dl))

    if not parsed:
        return []

    # Fetch seeders for all torrents in parallel
    seeder_results = [None] * len(parsed)

    def _fetch_one(idx, info_hash, trackers):
        seeder_results[idx] = _fetch_seeders(info_hash, trackers)

    threads = [threading.Thread(target=_fetch_one, args=(i, ih, tr), daemon=True)
               for i, (ih, tr, _) in enumerate(parsed)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)

    sources = []
    for i, (info_hash, trackers, dl) in enumerate(parsed):
        quality_raw = dl.get('quality', '')
        quality = _quality_from_str(quality_raw)
        lang = dl.get('language', '') or ''
        size = dl.get('size', '') or ''
        seeders = seeder_results[i]
        title_line = ' | '.join(filter(None, ['torrent', quality_raw, lang]))
        sources.append({
            'infoHash':   info_hash,
            'fileIdx':    0,
            'trackers':   ['tracker:' + t for t in trackers],
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': title_line,
            'size':       size,
            'seeds':      seeders,
            'is_torrent': True,
        })
    return sources


def _build_embed_sources(embeds):
    sources = []
    for em in embeds:
        url = em.get('url', '')
        if not url:
            continue
        quality_raw = em.get('quality', '') or 'Auto'
        quality = _quality_from_str(quality_raw)
        lang = em.get('lang', '') or ''
        host = urlparse(url).netloc.replace('www.', '')
        title_line = ' | '.join(filter(None, [host, quality_raw, lang]))
        sources.append({
            'url':        url,
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': title_line,
            'direct':     False,
        })
    return sources


def get_sources(tmdb_id, media_type='movie', title=None, year=None, season=None, episode=None, original_title=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    if not title:
        xbmc.log(f'{_LABEL} titlu lipsă pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        return []

    try:
        slug, _ = _find_slug(title, tmdb_id, original_title=original_title)
        if not slug:
            xbmc.log(f'{_LABEL} slug negăsit pentru "{title}" (tmdb={tmdb_id})', xbmc.LOGINFO)
            return []

        if media_type == 'movie':
            data = _get(f'/movie/{slug}/related')
            if not data:
                return []
            downloads = data.get('downloads', [])
            embeds = data.get('embeds', [])
        else:
            data = _get(f'/serie/{slug}/related')
            if not data:
                return []
            all_dl = data.get('downloads', [])
            s_num, e_num = int(season), int(episode)
            downloads = [d for d in all_dl
                         if int(d.get('season', 0)) == s_num and int(d.get('episode', 0)) == e_num]
            all_em = data.get('embeds', [])
            embeds = [e for e in all_em
                      if int(e.get('season', 0)) == s_num and int(e.get('episode', 0)) == e_num]

        sources = _build_torrent_sources(downloads) + _build_embed_sources(embeds)
        xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
        return sources
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []
