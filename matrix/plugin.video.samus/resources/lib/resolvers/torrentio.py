# -*- coding: utf-8 -*-
import re
import requests
import xbmc

BASE_URL = "https://torrentio.strem.fun"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


def _parse_meta(title):
    """Extrage numărul de seederi și dimensiunea fișierului din câmpul title."""
    seeds = None
    size = None
    m = re.search(r'👤\s*(\d+)', title)
    if m:
        seeds = int(m.group(1))
    m = re.search(r'💾\s*([\d.]+\s*\S+)', title)
    if m:
        size = m.group(1).strip()
    return seeds, size


def _parse_streams(streams):
    results = []
    for s in streams:
        info_hash = s.get('infoHash')
        if not info_hash:
            continue

        trackers = [src for src in s.get('sources', []) if src.startswith('tracker:')]

        name_lines = s.get('name', 'Torrentio').strip().split('\n')
        provider = name_lines[0] if name_lines else 'Torrentio'
        quality = name_lines[1] if len(name_lines) > 1 else ''

        title_raw = s.get('title', '').strip()
        title_lines = title_raw.split('\n')
        title_line = title_lines[0] if title_lines else ''

        seeds, size = _parse_meta(title_raw)

        results.append({
            'infoHash': info_hash,
            'fileIdx': s.get('fileIdx', 0),
            'trackers': trackers,
            'provider': provider,
            'quality': quality,
            'title_line': title_line,
            'seeds': seeds,
            'size': size,
        })
    return results


def get_movie_sources(imdb_id):
    url = f"{BASE_URL}/stream/movie/{imdb_id}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return _parse_streams(r.json().get('streams', []))
    except Exception as e:
        xbmc.log(f"[Torrentio] film {imdb_id}: {e}", xbmc.LOGERROR)
        return []


def get_tv_sources(imdb_id, season, episode):
    url = f"{BASE_URL}/stream/series/{imdb_id}:{season}:{episode}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return _parse_streams(r.json().get('streams', []))
    except Exception as e:
        xbmc.log(f"[Torrentio] serial {imdb_id} S{season}E{episode}: {e}", xbmc.LOGERROR)
        return []
