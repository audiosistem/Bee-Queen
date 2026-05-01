# -*- coding: utf-8 -*-
import urllib.request as urllib2
import urllib.parse
import json
import re
import gzip
from io import BytesIO
import xbmc

BASE_URL = "https://mediafusion.elfhosted.com"

# Base64 encoded config: enable_catalogs=false, max_streams=99, disable nudity/cert filters
_ENCODED_USER_DATA = (
    'eyJlbmFibGVfY2F0YWxvZ3MiOiBmYWxzZSwgIm1heF9zdHJlYW1zX3Blcl9yZXNvbHV0aW9uIjogOTks'
    'ICJ0b3JyZW50X3NvcnRpbmdfcHJpb3JpdHkiOiBbXSwgImNlcnRpZmljYXRpb25fZmlsdGVyIjogWyJE'
    'aXNhYmxlIl0sICJudWRpdHlfZmlsdGVyIjogWyJEaXNhYmxlIl19'
)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Encoding': 'gzip',
    'encoded_user_data': _ENCODED_USER_DATA,
}


def _fetch(url):
    req = urllib2.Request(url, headers=_HEADERS)
    with urllib2.urlopen(req, timeout=15) as resp:
        raw = resp.read()
        if resp.info().get('Content-Encoding') == 'gzip':
            raw = gzip.GzipFile(fileobj=BytesIO(raw)).read()
        return json.loads(raw.decode('utf-8'))


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


def _parse_streams(streams):
    results = []
    seen = set()
    for s in streams:
        info_hash = s.get('infoHash')
        if not info_hash:
            m = re.search(r'\b([a-fA-F0-9]{40})\b', s.get('url', ''))
            if m:
                info_hash = m.group(1)
        if not info_hash:
            continue
        info_hash = info_hash.lower()
        if info_hash in seen:
            continue
        seen.add(info_hash)

        title_raw = s.get('title', '').strip()
        title_line = title_raw.split('\n')[0] if title_raw else ''

        name_raw = s.get('name', '').strip()
        name_lines = name_raw.split('\n')
        quality = name_lines[1] if len(name_lines) > 1 else ''
        if not quality:
            for q in ('4K', '2160p', '1080p', '720p', '480p'):
                if q.lower() in title_raw.lower() or q.lower() in name_raw.lower():
                    quality = q
                    break

        seeds, size = _parse_meta(title_raw)
        trackers = [src for src in s.get('sources', []) if src.startswith('tracker:')]

        results.append({
            'infoHash': info_hash,
            'fileIdx': s.get('fileIdx', 0),
            'trackers': trackers,
            'provider': 'MediaFusion',
            'quality': quality,
            'title_line': title_line,
            'seeds': seeds,
            'size': size,
        })
    return results


def get_movie_sources(imdb_id):
    url = f"{BASE_URL}/stream/movie/{imdb_id}.json"
    try:
        xbmc.log(f"[MediaFusion] film: {url}", xbmc.LOGINFO)
        return _parse_streams(_fetch(url).get('streams', []))
    except Exception as e:
        xbmc.log(f"[MediaFusion] film {imdb_id}: {e}", xbmc.LOGERROR)
        return []


def get_tv_sources(imdb_id, season, episode):
    url = f"{BASE_URL}/stream/series/{imdb_id}:{season}:{episode}.json"
    try:
        xbmc.log(f"[MediaFusion] serial: {url}", xbmc.LOGINFO)
        return _parse_streams(_fetch(url).get('streams', []))
    except Exception as e:
        xbmc.log(f"[MediaFusion] serial {imdb_id} S{season}E{episode}: {e}", xbmc.LOGERROR)
        return []
