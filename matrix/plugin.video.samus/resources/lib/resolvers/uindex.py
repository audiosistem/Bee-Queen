# -*- coding: utf-8 -*-
"""UIndex torrent scraper — searches uindex.org by title."""
import re
import urllib.request
import urllib.parse
import xbmc

_BASE = 'https://uindex.org'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Cache-Control': 'no-cache',
}

_Q_TOKENS = [
    ('4K',    ('2160p', '4k', 'uhd')),
    ('1080p', ('1080p', 'fhd')),
    ('720p',  ('720p',)),
    ('480p',  ('480p',)),
]


def _guess_quality(name):
    n = name.lower()
    for q, tokens in _Q_TOKENS:
        if any(t in n for t in tokens):
            return q
    return '720p'


def _search(query):
    import time
    url = f"{_BASE}/search.php?search={urllib.parse.quote_plus(query)}&t={int(time.time())}"
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return ''
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        xbmc.log(f'[Samus/UIndex] eroare fetch {query}: {e}', xbmc.LOGERROR)
        return ''


def _parse(html, seen):
    results = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I)
    for row in rows:
        try:
            magnets = re.findall(r'href=["\'](magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\']*)["\']', row, re.I)
            if not magnets:
                continue
            magnet = urllib.parse.unquote_plus(magnets[0]).replace('&amp;', '&')

            hash_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.I)
            if not hash_m:
                continue
            info_hash = hash_m.group(1).lower()
            if info_hash in seen:
                continue

            name_m = re.search(r'<a[^>]*href=["\']/details\.php\?id=\d+["\'][^>]*>(.*?)</a>', row, re.S | re.I)
            if name_m:
                name = re.sub(r'<[^>]*>', '', name_m.group(1)).strip()
            else:
                dn_m = re.search(r'dn=(.*?)(?:&|$)', magnet)
                name = urllib.parse.unquote_plus(dn_m.group(1)) if dn_m else 'Unknown'

            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
            size = re.sub(r'<[^>]*>', '', cells[2]).strip() if len(cells) > 2 else ''
            seeds_raw = re.sub(r'<[^>]*>', '', cells[3]).strip() if len(cells) > 3 else '0'
            try:
                seeds = int(re.sub(r'\D', '', seeds_raw))
            except ValueError:
                seeds = 0

            trackers = re.findall(r'tr=(tracker:[^&]+)', magnet)

            results.append({
                'infoHash': info_hash,
                'fileIdx': 0,
                'trackers': trackers,
                'provider': '[UDX]',
                'quality': _guess_quality(name),
                'title_line': name,
                'seeds': seeds,
                'size': size,
            })
            seen.add(info_hash)
        except Exception:
            continue
    return results


def _build_queries(title, original_title, media_type, year, season, episode):
    clean = re.sub(r"[^A-Za-z0-9\s.\-]+", ' ', title.replace('&', 'and')).strip()
    queries = []
    if media_type == 'tvshow':
        hdlr = f'S{int(season):02d}E{int(episode):02d}'
        queries.append(f'{clean} {hdlr}')
        if original_title and original_title != title:
            clean_orig = re.sub(r"[^A-Za-z0-9\s.\-]+", ' ', original_title).strip()
            queries.append(f'{clean_orig} {hdlr}')
    else:
        queries.append(f'{clean} {year}' if year else clean)
        if original_title and original_title != title:
            clean_orig = re.sub(r"[^A-Za-z0-9\s.\-]+", ' ', original_title).strip()
            queries.append(f'{clean_orig} {year}' if year else clean_orig)
    return queries


def get_movie_sources(title, year='', original_title=None):
    queries = _build_queries(title, original_title, 'movie', year, None, None)
    seen = set()
    for q in queries:
        html = _search(q)
        results = _parse(html, seen)
        if results:
            xbmc.log(f'[Samus/UIndex] {len(results)} surse pentru "{q}"', xbmc.LOGINFO)
            return results
    return []


def get_tv_sources(title, season, episode, original_title=None):
    queries = _build_queries(title, original_title, 'tvshow', '', season, episode)
    seen = set()
    for q in queries:
        html = _search(q)
        results = _parse(html, seen)
        if results:
            xbmc.log(f'[Samus/UIndex] {len(results)} surse pentru "{q}"', xbmc.LOGINFO)
            return results
    return []
