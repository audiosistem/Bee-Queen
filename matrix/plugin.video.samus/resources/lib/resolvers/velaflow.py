# -*- coding: utf-8 -*-
import re
import requests
import xbmc

_BASE = "https://vela-flow.vercel.app"
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


def _parse_meta(title):
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
        name_lines = s.get('name', 'VelaFlow').strip().split('\n')
        quality = name_lines[0] if name_lines else ''
        title_raw = s.get('title', '').strip()
        title_lines = title_raw.split('\n')
        title_line = title_lines[0] if title_lines else ''
        seeds, size = _parse_meta(title_raw)
        results.append({
            'infoHash':  info_hash,
            'fileIdx':   s.get('fileIdx', 0),
            'trackers':  trackers,
            'provider':  'VelaFlow',
            'quality':   quality,
            'title_line': title_line,
            'seeds':     seeds,
            'size':      size,
            'is_torrent': True,
        })
    return results


def get_movie_sources(imdb_id):
    try:
        r = requests.get(f"{_BASE}/stream/movie/{imdb_id}.json", headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return _parse_streams(r.json().get('streams', []))
    except Exception as e:
        xbmc.log(f"[VelaFlow] film {imdb_id}: {e}", xbmc.LOGERROR)
        return []


def get_tv_sources(imdb_id, season, episode):
    try:
        r = requests.get(f"{_BASE}/stream/series/{imdb_id}:{season}:{episode}.json", headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return _parse_streams(r.json().get('streams', []))
    except Exception as e:
        xbmc.log(f"[VelaFlow] serial {imdb_id} S{season}E{episode}: {e}", xbmc.LOGERROR)
        return []
