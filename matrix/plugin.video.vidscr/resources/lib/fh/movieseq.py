# -*- coding: utf-8 -*-
"""movieseq.com scraper — TMDB-keyed embed iframe.

The site at ``movieseq.com`` indexes by TMDB id. Each movie page wraps
an embed at ``/embed/movie/{tmdb_id}`` that pipes through a multi-hop
encrypted player chain (nextgencloudfabric.com → streamdata.vaplayer.ru
api.php with a pako-zipped, AES-wrapped JSON payload).

Reverse-engineering the vaplayer.ru chain to surface the raw .m3u8 is a
multi-hour job and likely to break the next time they rotate keys. So
this scraper takes the pragmatic path: emit the wrapper URL
``https://movieseq.com/embed/movie/{tmdb_id}`` as a HOSTER stream and
let ``script.module.resolveurl`` deal with the player chain at play
time. Many RU forks ship a generic iframe-player plugin that can crack
this layout; on installs that don't, the user gets a clean
``Could not resolve`` notification — the addon does not crash and the
non-hoster streams above it (Cloudnestra / Vidnest / Stigstream /
Goojara / EffedUpMovies) keep working untouched.

This source is at the BOTTOM of the picker (``sort_weight=999``).
"""
from __future__ import annotations

from typing import List, Dict

import requests

from ..common import log

SITE = 'MovieSeq'
BASE = 'https://movieseq.com'
TIMEOUT = 8


def resolve(media_type, tmdb_id, imdb_id, title=None, year=None,
            season=None, episode=None) -> List[Dict]:
    if not tmdb_id:
        return []
    if media_type == 'movie':
        embed = '%s/embed/movie/%s' % (BASE, tmdb_id)
    elif media_type in ('show', 'tv'):
        if not season or not episode:
            return []
        embed = '%s/embed/tv/%s/%s/%s' % (BASE, tmdb_id, season, episode)
    else:
        return []

    # Probe the URL once so a 404 doesn't waste a picker slot. The site
    # responds 200 even when the player will fail to find a stream, but
    # at least we screen out outright misses.
    try:
        r = requests.head(embed, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400:
            log('fh.movieseq: probe HTTP %s for %s' % (r.status_code, embed))
            return []
    except Exception as e:
        log('fh.movieseq: probe err %s' % e)
        # Still ship the URL — head can fail for reasons unrelated to playability.
        pass

    return [{
        'url': embed,
        'proto': 'HOSTER',
        'needs_resolveurl': True,
        'source_site': SITE,
        'host_name': 'MovieSeq Embed',
        'host_origin': 'movieseq.com',
        'provider': 'filehost',
        'quality': 'AUTO',
        'sort_weight': 999,
        'label': '[AUTO] MovieSeq Embed',
    }]
