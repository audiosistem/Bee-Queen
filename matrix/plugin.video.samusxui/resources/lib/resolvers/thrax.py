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
        server_name = s.get('server_name', '')
        if provider == 'primesrcme' and not server_name:
            from urllib.parse import urlparse
            host = urlparse(url).hostname or ''
            server_name = {
                'bysejikuar.com': 'Filemoon', 'filemoon.sx': 'Filemoon',
                'streamwish.to': 'Streamwish', 'wishembed.online': 'Streamwish',
                'dood.watch': 'Dood', 'doodstream.com': 'Dood',
                'voe.sx': 'Voe', 'voe-unblock.net': 'Voe',
                'streamta.site': 'Streamtape', 'streamtape.com': 'Streamtape',
                'vidmoly.me': 'Vidmoly', 'vidmoly.biz': 'Vidmoly',
                'mixdrop.ag': 'Mixdrop', 'mixdrop.co': 'Mixdrop',
                'filelions.to': 'Filelions', 'savefiles.com': 'Savefiles',
                'luluvdoo.com': 'Luluvdoo', 'vinovo.to': 'Vinovo',
                'vids.st': 'VidsST', 'streamplay.to': 'Streamplay',
                'vidara.so': 'Vidara', 'upzur.com': 'UpZur', 'vidnest.io': 'VidNest',
            }.get(host, '')
        display = server_name if (provider == 'primesrcme' and server_name) else provider
        label = f"{quality} ({display})" if quality else display
        subs = s.get('subtitles') or []
        if isinstance(subs, str):
            subs = [subs]

        if provider == 'direct':
            url = _encode_url(url)
            results.append({
                'label':        label,
                'display_name': display,
                'url':          url,
                'provider':     provider,
                'direct':       True,
                'quality':      quality,
                'subtitles':    subs,
            })
        else:
            results.append({
                'label':        label,
                'display_name': display,
                'url':          url,
                'provider':     provider,
                'direct':       False,
                'quality':      quality,
                'subtitles':    subs,
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
