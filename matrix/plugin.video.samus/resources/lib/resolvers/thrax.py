# -*- coding: utf-8 -*-
"""Thrax Links API resolver — https://api.derzis.xyz"""
import urllib.parse
import requests
import xbmc

_BASE = 'https://api.derzis.xyz'
from resources.lib.resolvers._common import THRAX_KEY as _THRAX_KEY
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'X-Thrax-Key': _THRAX_KEY,
}


def _encode_url(url):
    """Percent-encode spaces and special chars in the path, preserving scheme and host."""
    parsed = urllib.parse.urlsplit(url)
    encoded_path = '/'.join(
        urllib.parse.quote(seg, safe='') for seg in parsed.path.split('/')
    )
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))



def _parse(sources):
    results = []
    for s in sources:
        url = s.get('url')
        if not url:
            continue
        provider = s.get('provider', '')
        quality = s.get('quality', '')
        label = f"{quality} ({provider})" if quality else provider
        subs = s.get('subtitles') or []
        if isinstance(subs, str):
            subs = [subs]

        if provider == 'direct':
            url = _encode_url(url)
            results.append({
                'label':     label,
                'url':       url,
                'direct':    True,
                'quality':   quality,
                'subtitles': subs,
            })
        else:
            results.append({
                'label':     label,
                'url':       url,
                'direct':    False,
                'quality':   quality,
                'subtitles': subs,
            })
    return results


def get_movie_sources(tmdb_id):
    url = f"{_BASE}/movie/{tmdb_id}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return _parse(r.json().get('sources', []))
    except Exception as e:
        xbmc.log(f'[Samus/Thrax] film {tmdb_id}: {e}', xbmc.LOGERROR)
        return []


def get_tv_sources(tmdb_id, season, episode):
    url = f"{_BASE}/tv/{tmdb_id}/{season}/{episode}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return _parse(r.json().get('sources', []))
    except Exception as e:
        xbmc.log(f'[Samus/Thrax] serial {tmdb_id} S{season}E{episode}: {e}', xbmc.LOGERROR)
        return []
