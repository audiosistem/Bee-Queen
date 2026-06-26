# -*- coding: utf-8 -*-
"""Vidnest.fun source resolver.

Vidnest is a multi-backend streaming aggregator at https://vidnest.fun. Its
SPA fetches encrypted JSON envelopes from
``https://new.vidnest.fun/<provider>/movie/<tmdb_id>`` (or ``/tv/<tmdb>/<season>/<episode>``)
where ``provider`` is one of:

    moviesapi   purstream   allmovies   catflix   hollymoviehd
    flixhq      vidlink     ophim

Each provider returns a JSON wrapper ``{"data":"<b64>","encrypted":true}``
where ``data`` is encoded with a custom Base64 alphabet. After decoding we
get either:

    sources:    [{url, isM3U8, type}]                # moviesapi / catflix / alfa
    sources:    [{url, name, format}]                # purstream / beta
    sources:    [{file, label, type}]                # hollymoviehd / sigma
    streams:    [{url, language, type, headers}]     # allmovies / lamda / delta
    data.stream.playlist                             # vidlink / hexa
    url:        "https://..."                        # flixhq / gama

This module:
  * Calls every provider in parallel.
  * Decodes the custom-Base64 envelope.
  * Normalises every shape into the addon's canonical stream dict
    (``url``, ``label``, ``quality``, ``host``, ``provider``, ``headers``).
  * Filters non-HLS / non-MP4 entries.

Endpoints can return 502 when a backend dies; we silently skip those.
The custom alphabet was extracted from the site's deobfuscated
``decryptCipherResponse`` function.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .common import log

API = 'https://new.vidnest.fun'
SITE = 'https://vidnest.fun'
TIMEOUT = 12

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# Custom Base64 alphabet (= is the padding sentinel mapping to value 64).
_ALPH = 'RB0fpH8ZEyVLkv7c2i6MAJ5u3IKFDxlS1NTsnGaqmXYdUrtzjwObCgQP94hoeW+/='
_TABLE = {c: i for i, c in enumerate(_ALPH)}

# Provider -> (path-template, kind). kind drives response shape parsing.
# v1.4.19 (2026-05-23): added `ophim` (a.k.a. klikxxi in Vidnest's bundle) -
# one of the four new backends Vidnest added since v1.4.18 was built.
# `moviebox` is also new but needs a proxy config we can't supply (their
# response has empty `servers`/`url` and just echoes headers). `delta` is
# a second AllMovies endpoint - duplicate, skipped.
_PROVIDERS = {
    'moviesapi':    ('moviesapi',    'sources'),
    'purstream':    ('purstream',    'sources_named'),
    'allmovies':    ('allmovies',    'streams_lang'),
    'catflix':      ('catflix',      'sources'),
    'hollymoviehd': ('hollymoviehd', 'sources_file'),
    'flixhq':       ('flixhq',       'url_only'),
    'vidlink':      ('vidlink',      'vidlink'),
    'ophim':        ('klikxxi',      'sources'),
}

# Pretty names shown in the per-source progress dialog.
PROVIDER_LABELS = {
    'moviesapi':    'MoviesAPI',
    'purstream':    'PurStream',
    'allmovies':    'AllMovies',
    'catflix':      'CatFlix',
    'hollymoviehd': 'HollyMovieHD',
    'flixhq':       'FlixHQ',
    'vidlink':      'VidLink',
    'ophim':        'Ophim',
}


def _b64decode(data: str) -> str:
    """Decode the custom-alphabet Base64 string → utf-8 text."""
    out = bytearray()
    for i in range(0, len(data), 4):
        block = data[i:i + 4]
        if len(block) < 4:
            block += '=' * (4 - len(block))
        l = [_TABLE.get(c, 64) for c in block]
        out.append(((l[0] << 2) & 0xFF) | ((l[1] >> 4) & 0xFF))
        if l[2] != 64:
            out.append((((l[1] & 15) << 4) & 0xFF) | ((l[2] >> 2) & 0xFF))
        if l[3] != 64:
            out.append(((l[2] << 6) & 0xFF) | (l[3] & 0xFF))
    return out.decode('utf-8', errors='replace')


def _decode_envelope(env):
    """Take the JSON returned by the API and unwrap it. Returns dict/list."""
    if not isinstance(env, dict):
        return env
    if not env.get('encrypted'):
        return env
    payload = env.get('data')
    if not isinstance(payload, str):
        raise ValueError('Vidnest envelope missing "data"')
    plain = _b64decode(payload)
    try:
        return json.loads(plain)
    except ValueError:
        return plain


def _quality_from_label(label, fallback='auto'):
    """Pull '720p'/'1080p'/'4k' out of a provider-supplied label string."""
    if not label:
        return fallback
    m = re.search(r'(\d{3,4}\s*p|4k|2k|sd|hd)', str(label), re.I)
    return m.group(1).lower().replace(' ', '') if m else label


def _is_playable(url):
    if not url:
        return False
    u = url.lower()
    return ('.m3u8' in u or '.mp4' in u or '/hls/' in u or '/master' in u
            or u.endswith('.txt') or '.mpd' in u or '/playlist' in u
            or '/proxy' in u)


def _fetch_provider(media_type, tmdb_id, season, episode, prov_key, kind):
    """One provider call, returns (provider_key, list_of_streams)."""
    if media_type == 'movie':
        path = '%s/movie/%s' % (prov_key, tmdb_id)
    else:
        path = '%s/tv/%s/%s/%s' % (prov_key, tmdb_id, season or 1, episode or 1)
    url = '%s/%s' % (API, path)
    headers = {
        'User-Agent': UA,
        'Origin': SITE,
        'Referer': SITE + '/',
        'Accept': 'application/json,*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
    except Exception as e:
        log('vidnest: %s network err %s' % (prov_key, e))
        return prov_key, []
    if r.status_code != 200:
        log('vidnest: %s -> HTTP %s' % (prov_key, r.status_code))
        return prov_key, []
    try:
        env = r.json()
    except ValueError:
        log('vidnest: %s -> non-JSON body' % prov_key)
        return prov_key, []
    try:
        data = _decode_envelope(env)
    except Exception as e:
        log('vidnest: %s decode failed %s' % (prov_key, e))
        return prov_key, []
    if not isinstance(data, dict):
        return prov_key, []

    label_pretty = PROVIDER_LABELS.get(prov_key, prov_key)
    streams = []

    if kind in ('sources', 'sources_named'):
        for s in (data.get('sources') or []):
            u = s.get('url')
            if not _is_playable(u):
                continue
            quality = (s.get('quality') or
                       _quality_from_label(s.get('name') or s.get('label')))
            streams.append({
                'url': u,
                'quality': quality or 'auto',
                'label': '[%s] Vidnest • %s' % (quality or 'auto', label_pretty),
                'host': prov_key,
                'server': 'Vidnest %s' % label_pretty,
                'proto': 'HLS' if '.m3u8' in u.lower() or u.lower().endswith('.txt') else 'MP4',
                'headers': {'User-Agent': UA, 'Referer': SITE + '/'},
                'provider': 'vidnest',
                'subtitles': data.get('subtitles') or [],
            })

    elif kind == 'sources_file':
        for s in (data.get('sources') or []):
            u = s.get('file')
            if not _is_playable(u):
                continue
            quality = _quality_from_label(s.get('label'))
            streams.append({
                'url': u,
                'quality': quality or 'auto',
                'label': '[%s] Vidnest • %s' % (quality or 'auto', label_pretty),
                'host': prov_key,
                'server': 'Vidnest %s' % label_pretty,
                'proto': 'HLS' if (s.get('type') == 'hls' or '.m3u8' in u.lower()) else 'MP4',
                'headers': {'User-Agent': UA, 'Referer': SITE + '/'},
                'provider': 'vidnest',
                'subtitles': data.get('subtitles') or [],
            })

    elif kind == 'streams_lang':
        for s in (data.get('streams') or []):
            u = s.get('url')
            if not _is_playable(u):
                continue
            lang = s.get('language') or 'auto'
            extra_h = s.get('headers') or {}
            req_headers = {'User-Agent': UA, 'Referer': SITE + '/'}
            req_headers.update(extra_h)
            streams.append({
                'url': u,
                'quality': 'auto',
                'label': '[%s] Vidnest • %s' % (lang, label_pretty),
                'host': prov_key,
                'server': 'Vidnest %s' % label_pretty,
                'proto': 'HLS',
                'headers': req_headers,
                'provider': 'vidnest',
                'subtitles': data.get('subtitles') or [],
            })

    elif kind == 'url_only':
        u = data.get('url')
        if _is_playable(u):
            streams.append({
                'url': u,
                'quality': 'auto',
                'label': '[auto] Vidnest • %s' % label_pretty,
                'host': prov_key,
                'server': 'Vidnest %s' % label_pretty,
                'proto': 'HLS',
                'headers': {'User-Agent': UA, 'Referer': SITE + '/'},
                'provider': 'vidnest',
                'subtitles': data.get('subtitles') or [],
            })

    elif kind == 'vidlink':
        stream = (data.get('data') or {}).get('stream') or {}
        u = stream.get('playlist')
        if _is_playable(u):
            extra_h = data.get('headers') or {}
            req_headers = {'User-Agent': UA, 'Referer': SITE + '/'}
            # Only forward referer/origin from upstream — drop internal ones.
            for k in ('Referer', 'referer', 'Origin', 'origin'):
                if k in extra_h:
                    req_headers[k.title()] = extra_h[k]
            streams.append({
                'url': u,
                'quality': 'auto',
                'label': '[auto] Vidnest • %s' % label_pretty,
                'host': prov_key,
                'server': 'Vidnest %s' % label_pretty,
                'proto': 'HLS',
                'headers': req_headers,
                'provider': 'vidnest',
                'subtitles': [
                    {'url': c.get('url'), 'lang': c.get('language')}
                    for c in (stream.get('captions') or []) if c.get('url')
                ],
            })

    return prov_key, streams


def resolve_streams(media_type, tmdb_id, season=None, episode=None,
                    progress_cb=None):
    """Resolve all vidnest backends in parallel.

    progress_cb(provider_key, count) is called as each backend completes,
    so the caller can update its progress dialog with per-source counts.
    """
    if not tmdb_id:
        log('vidnest: tmdb_id required')
        return []

    out = []
    with ThreadPoolExecutor(max_workers=len(_PROVIDERS)) as ex:
        futures = {
            ex.submit(_fetch_provider, media_type, tmdb_id, season, episode,
                      key, kind): key
            for key, (_, kind) in _PROVIDERS.items()
        }
        for fut in as_completed(futures, timeout=TIMEOUT + 5):
            try:
                prov_key, streams = fut.result(timeout=1)
            except Exception as e:
                log('vidnest: worker err %s' % e)
                continue
            if streams:
                log('vidnest: %s contributed %d streams'
                    % (prov_key, len(streams)))
                out.extend(streams)
            if progress_cb:
                try:
                    progress_cb(prov_key, len(streams))
                except Exception:
                    pass
    log('vidnest: total %d streams across %d providers'
        % (len(out), len(_PROVIDERS)))
    return out
