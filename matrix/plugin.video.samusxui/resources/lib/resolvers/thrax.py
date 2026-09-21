# -*- coding: utf-8 -*-
"""Thrax Links API resolver — https://api.derzis.xyz"""
import hashlib
import re
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

_BTIH_RE = re.compile(r'(?i)btih:([a-zA-Z0-9]+)')


def _encode_url(url):
    parsed = urllib.parse.urlsplit(url)
    encoded_path = '/'.join(
        urllib.parse.quote(seg, safe='') for seg in parsed.path.split('/')
    )
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))


def _magnet_info(url):
    """Extrage info_hash + trackere dintr-un magnet: URI. None dacă nu e magnet valid."""
    m = _BTIH_RE.search(url)
    if not m:
        return None
    info_hash = m.group(1).upper()
    query = urllib.parse.urlsplit(url).query
    trackers = [f'tracker:{t}' for t in urllib.parse.parse_qs(query).get('tr', [])]
    return info_hash, trackers


def _bdecode(data, i=0):
    c = data[i:i + 1]
    if c == b'd':
        d = {}
        i += 1
        while data[i:i + 1] != b'e':
            k, i = _bdecode(data, i)
            v, i = _bdecode(data, i)
            d[k] = v
        return d, i + 1
    if c == b'l':
        lst = []
        i += 1
        while data[i:i + 1] != b'e':
            v, i = _bdecode(data, i)
            lst.append(v)
        return lst, i + 1
    if c == b'i':
        j = data.index(b'e', i)
        return int(data[i + 1:j]), j + 1
    j = data.index(b':', i)
    n = int(data[i:j])
    s = data[j + 1:j + 1 + n]
    return s, j + 1 + n


def _bencode(x):
    if isinstance(x, dict):
        out = b'd'
        for k in sorted(x.keys()):
            out += _bencode(k) + _bencode(x[k])
        return out + b'e'
    if isinstance(x, list):
        return b'l' + b''.join(_bencode(v) for v in x) + b'e'
    if isinstance(x, int):
        return b'i' + str(x).encode() + b'e'
    if isinstance(x, bytes):
        return str(len(x)).encode() + b':' + x
    raise TypeError(f'unsupported bencode type: {type(x)}')


def _torrent_url_info(url):
    """Descarcă un .torrent de la un URL direct (ex. yts.gg/torrent/download/HASH) și
    extrage (info_hash, trackers) din bencode — None dacă nu e un .torrent valid."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        decoded, _ = _bdecode(r.content)
        info = decoded[b'info']
        info_hash = hashlib.sha1(_bencode(info)).hexdigest().upper()
        trackers = []
        if b'announce-list' in decoded:
            for tier in decoded[b'announce-list']:
                for t in tier:
                    trackers.append('tracker:' + t.decode('utf-8', 'ignore'))
        elif b'announce' in decoded:
            trackers.append('tracker:' + decoded[b'announce'].decode('utf-8', 'ignore'))
        return info_hash, trackers
    except Exception as e:
        xbmc.log(f'[Samus/Thrax] torrent_url eșuat ({url[:60]}...): {e}', xbmc.LOGWARNING)
        return None


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

        if provider == 'magnet' or url.startswith('magnet:'):
            info = _magnet_info(url)
            if not info:
                continue
            info_hash, trackers = info
            results.append({
                'label':      label,
                'display_name': display,
                'infoHash':   info_hash,
                'fileIdx':    0,
                'trackers':   trackers,
                'quality':    quality,
                'is_torrent': True,
                'subtitles':  subs,
            })
        elif provider == 'torrent':
            info = _torrent_url_info(url)
            if not info:
                continue
            info_hash, trackers = info
            results.append({
                'label':      label,
                'display_name': display,
                'infoHash':   info_hash,
                'fileIdx':    0,
                'trackers':   trackers,
                'quality':    quality,
                'is_torrent': True,
                'subtitles':  subs,
            })
        elif provider == 'direct':
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
                # true = rezolvat server-side (proxy Thrax, pt. surse IP-bound);
                # false/lipsă = rezolvare locală (resolveurl), nu consumă banda serverului
                'thrax_resolved': s.get('resolved', True),
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
