# -*- coding: utf-8 -*-
"""moviesfree.cv → ghostplayer.store file-host scraper.

Flow reverse-engineered from live traffic:
  1. ``GET https://moviesfree.cv/?s=<title>`` returns WordPress search HTML
     containing ``<a href="https://moviesfree.cv/<slug>/">`` per result.
  2. The detail page embeds a base64-encoded ``Servers`` global with three
     entries: ``embedru``, ``superembed``, ``vidsrc``. The ``superembed``
     URL points to ``ghostplayer.store/wp-content/plugins/fmovie-core/
     player/player.php?video_id=<imdb_id>``.
  3. That player URL 302-redirects to ``streamingnow.mov/?play=<blob>``
     which is the actual Filemoon / Voe / Mixdrop chain.

As of 2026-02-08 ``streamingnow.mov`` sits behind Cloudflare's interactive
Turnstile challenge — direct curl gets HTTP 403. The scraper returns the
URL anyway, because:

  * It's marked ``needs_resolveurl=True`` so the addon won't try to play
    it via Kodi's HTTP fetcher — it'll go through script.module.resolveurl,
    which on some installs uses cloudscraper + a real JS engine that can
    pass Turnstile.
  * Cloudflare's challenge state can change at any time; users on
    residential IPs / VPNs may get through where data-centre IPs don't.

Strict: this scraper never touches any other source module. It returns
file-host candidates only; existing Cloudnestra / Stigstream / Vidnest
streams keep their direct .m3u8 / .mp4 URLs and never flow through
ResolveURL.
"""
from __future__ import annotations

import base64
import json
import re
from typing import List, Dict

import requests

from ..common import log
from .. import resolveurl_bridge as RU

SITE = 'MoviesFree'
BASE = 'https://moviesfree.cv'
TIMEOUT = 12
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

_SLUG_RE = re.compile(r'href="(https?://moviesfree\.cv/[a-z0-9\-]+)/?"')
_SERVERS_RE = re.compile(
    r"""(?:window\.)?Servers\s*=\s*JSON\.parse\(atob\(\s*['"]([A-Za-z0-9+/=]+)['"]"""
)
_RAW_JSON_RE = re.compile(r"""(?:window\.)?Servers\s*=\s*(\{[^;]+\});""")
# fmovie-core delivers the Servers config via a base64-encoded data: URL on
# a ``<script id="servers-js-extra">`` tag — decoded payload is
# ``var Servers={...};``. This is the current shape for moviesfree.cv.
_SERVERS_DATAURL = re.compile(
    r'id=["\']servers-js[^"\']*["\']\s+src=["\']data:text/javascript;base64,'
    r'([A-Za-z0-9+/=]+)["\']'
)


def _http(url, **kw):
    headers = kw.pop('headers', {})
    headers.setdefault('User-Agent', UA)
    headers.setdefault('Accept-Encoding', 'gzip, deflate')
    headers.setdefault('Referer', BASE + '/')
    return requests.get(url, headers=headers, timeout=TIMEOUT, **kw)


def _find_slug(title, year=None):
    """Search MoviesFree for the title and return the first detail URL."""
    if not title:
        return None
    try:
        r = _http('%s/?s=%s' % (BASE, requests.utils.quote(title)))
    except Exception as e:
        log('fh.moviesfree: search err %s' % e)
        return None
    if r.status_code != 200:
        return None
    candidates = _SLUG_RE.findall(r.text)
    skip = {'category', 'tag', 'page', 'about', 'contact', 'feed', 'dmca',
            'disclaimer', 'privacy-policy', 'top-imdb'}
    needle = title.lower().split()[0] if title else ''
    for c in candidates:
        slug = c.rsplit('/', 1)[-1]
        if any(s in slug.lower() for s in skip):
            continue
        # Prefer slug containing first word of title.
        if needle and needle in slug.lower():
            return c
    # Fallback: first non-skipped candidate.
    for c in candidates:
        slug = c.rsplit('/', 1)[-1]
        if not any(s in slug.lower() for s in skip):
            return c
    return None


def _extract_servers_block(html):
    """Pull and decode the Servers config from a MoviesFree detail page."""
    # 1) Production: Servers config via base64 data: URL on servers-js tag.
    m = _SERVERS_DATAURL.search(html)
    if m:
        try:
            js = base64.b64decode(m.group(1)).decode('utf-8', 'replace')
            obj_m = re.search(r'Servers\s*=\s*(\{.+?\})\s*;?\s*$', js, re.S)
            if obj_m:
                return json.loads(obj_m.group(1))
        except Exception as e:
            log('fh.moviesfree: dataurl decode err %s' % e)
    # 2) Legacy: inline JSON.parse(atob('...')).
    m = _SERVERS_RE.search(html)
    if m:
        try:
            raw = base64.b64decode(m.group(1)).decode('utf-8', 'replace')
            return json.loads(raw)
        except Exception as e:
            log('fh.moviesfree: b64 decode err %s' % e)
    # 3) Legacy: inline JSON literal.
    m = _RAW_JSON_RE.search(html)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


def _candidates_from_servers(servers, source_site, ident):
    """Turn the ghostplayer Servers dict into picker entries.

    Skip ``embedru`` and ``vidsrc`` keys — those are cloudnestra mirrors
    we already cover via vidsrc.py and would just duplicate streams. We
    only keep the ``superembed`` entry which is the actual file-host
    chain (Filemoon-bearing)."""
    streams = []
    if not isinstance(servers, dict):
        return streams
    # Only keep keys that point to a real file-host chain. ``embedru`` and
    # ``vidsrc`` are cloudnestra mirrors covered by vidsrc.py; ``premium``
    # is a raw JSON API (not a hosted file). ``superembed`` is the
    # fmovie-core player.php redirector → Filemoon / Voe / Mixdrop chain.
    for key in ('superembed', 'filemoon', 'voe', 'mixdrop', 'streamtape',
                'streamwish', 'doodstream', 'mixdrp', 'upstream'):
        url = servers.get(key)
        if not isinstance(url, str) or not url.startswith('http'):
            continue
        # superembed redirects; let RU handle the chain. If RU recognises
        # the END host, we keep it; if not, we still ship the wrapper URL
        # so the user gets the option and a clear failure if RU bails.
        host_name = RU.host_label(url) if RU.is_available() else key.capitalize()
        streams.append({
            'url': url,
            'proto': 'HOSTER',
            'needs_resolveurl': True,
            'source_site': source_site,
            'host_name': host_name,
            'host_origin': 'ghostplayer.store',
            'provider': 'filehost',
            'quality': 'auto',
            'label': '[auto] %s via %s' % (host_name, source_site),
        })
    return streams


def resolve(media_type, tmdb_id, imdb_id, title=None, year=None,
            season=None, episode=None) -> List[Dict]:
    if media_type != 'movie':
        return []  # MoviesFree TV-show structure is different; not wired yet.
    if not title:
        return []
    slug_url = _find_slug(title, year=year)
    if not slug_url:
        log('fh.moviesfree: no slug match for %r' % title)
        return []
    try:
        r = _http(slug_url + '/')
    except Exception as e:
        log('fh.moviesfree: detail err %s' % e)
        return []
    if r.status_code != 200:
        log('fh.moviesfree: detail HTTP %s for %s' % (r.status_code, slug_url))
        return []
    servers = _extract_servers_block(r.text)
    if not servers:
        log('fh.moviesfree: no Servers block in %s' % slug_url)
        return []
    return _candidates_from_servers(servers, SITE, slug_url)
