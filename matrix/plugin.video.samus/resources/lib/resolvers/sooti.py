# -*- coding: utf-8 -*-
"""Sooti — Stremio addon agregator (VixSrc, HDHub4u, UHDMovies etc.) cu fallback la mirror-uri."""
import json
import requests
import xbmc
from urllib.parse import quote
from resources.lib.resolvers import stremio_client

_LABEL = '[SOT]'

_CONFIG = {
    "DebridServices": [{"provider": "httpstreaming", "http4khdhub": True, "httpHDHub4u": True,
                        "httpUHDMovies": True, "httpMoviesDrive": True, "httpMKVCinemas": True,
                        "httpMalluMv": True, "httpCineDoze": True, "httpVixSrc": True}],
    "Languages": [], "Scrapers": [], "IndexerScrapers": [],
    "minSize": 0, "maxSize": 200, "ShowCatalog": False, "DebridProvider": "httpstreaming",
}
_ENC = quote(json.dumps(_CONFIG, separators=(',', ':')))

_MIRRORS = [
    f'https://sooti.click/{_ENC}',
    f'https://sooti.info/{_ENC}',
    f'https://sootiofortheweebs.midnightignite.me/{_ENC}',
]

# Accept-Encoding: identity evită conflictul zstandard/gzip din Python-ul Kodi
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Encoding': 'identity',
}


def _fetch(url):
    r = requests.get(url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json().get('streams', [])


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    for base_url in _MIRRORS:
        base = base_url.rstrip('/')
        if media_type == 'movie':
            api_url = f'{base}/stream/movie/{imdb_id}.json'
        else:
            api_url = f'{base}/stream/series/{imdb_id}:{season}:{episode}.json'
        try:
            streams = _fetch(api_url)
            if not streams:
                continue
            results = stremio_client._parse_direct_streams(streams, _LABEL)
            if results:
                xbmc.log(f'[Samus/Sooti] {len(results)} surse pentru {imdb_id}', xbmc.LOGINFO)
                return results
        except Exception as e:
            xbmc.log(f'[Samus/Sooti] mirror eșuat ({api_url[:40]}...): {e}', xbmc.LOGWARNING)
    xbmc.log(f'[Samus/Sooti] nicio sursă pentru {imdb_id}', xbmc.LOGINFO)
    return []
