# -*- coding: utf-8 -*-
"""Generic FMovie-Core WordPress plugin scraper.

A huge number of free-movie WP sites (moviesfree.cv, ghostplayer.store,
hundreds of mirrors) use a plugin called ``fmovie-core`` whose footprint
on every detail page is identical:

  * URL pattern: ``https://<host>/?s=<title>`` returns search results,
    detail pages live at ``https://<host>/<slug>/``.
  * Detail HTML contains a ``Servers`` global that's either a JSON
    literal or ``JSON.parse(atob('...'))``.
  * Inside Servers: ``superembed`` is the file-host chain, ``embedru``
    and ``vidsrc`` are cloudnestra mirrors (we skip those — already covered).

This scraper is a thin loop: for every host in ``HOSTS``, run the same
search → detail → Servers extraction. Adding a new site is one line in
``HOSTS``.
"""
from __future__ import annotations

import base64
import json
import re
from typing import List, Dict

import requests

from ..common import log
from .. import resolveurl_bridge as RU

TIMEOUT = 10
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# (pretty_name, base_url) — add new fmovie-core mirrors here without
# touching code. Pretty name appears in the picker as ``via <pretty>``.
# Sites confirmed to run the fmovie-core WP plugin and expose the same
# Servers / superembed shape. moviesfree.cv has a dedicated module
# (fh/moviesfree.py) so we don't list it here — duplicate URLs would
# just be de-duped downstream but we save the extra HTTP round-trip.
HOSTS = (
    ('Ghostplayer',  'https://ghostplayer.store'),
)

_SERVERS_B64 = re.compile(
    r"""(?:window\.)?Servers\s*=\s*JSON\.parse\(\s*atob\(\s*['"]([A-Za-z0-9+/=]+)['"]"""
)
_SERVERS_LITERAL = re.compile(r"""(?:window\.)?Servers\s*=\s*(\{[^;]+?\});""")
# fmovie-core mirrors deliver the Servers var via a base64-encoded
# data: URL: ``<script id="servers-js-extra" src="data:text/javascript;
# base64,<B64>">``. The decoded payload is ``var Servers={...};``.
_SERVERS_DATAURL = re.compile(
    r'id=["\']servers-js[^"\']*["\']\s+src=["\']data:text/javascript;base64,'
    r'([A-Za-z0-9+/=]+)["\']'
)


def _http(url, **kw):
    h = kw.pop('headers', {})
    h.setdefault('User-Agent', UA)
    h.setdefault('Accept-Encoding', 'gzip, deflate')
    return requests.get(url, headers=h, timeout=TIMEOUT, **kw)


def _slug(base, title):
    if not title:
        return None
    try:
        r = _http('%s/?s=%s' % (base, requests.utils.quote(title)),
                  headers={'Referer': base + '/'})
    except Exception as e:
        log('fh.fmovie_core[%s]: search err %s' % (base, e))
        return None
    if r.status_code != 200:
        return None
    needle = title.lower().split()[0]
    skip = {'category', 'tag', 'page', 'about', 'contact', 'feed', 'dmca',
            'disclaimer', 'privacy-policy', 'top-imdb'}
    # In WP themes article hrefs are absolute. Find every internal slug.
    host = base.split('://', 1)[-1].rstrip('/')
    pat = re.compile(r'href="(https?://' + re.escape(host) + r'/[a-z0-9\-]+)/?"')
    matches = pat.findall(r.text)
    # Prefer matches whose slug contains the title's first word.
    for m in matches:
        slug = m.rsplit('/', 1)[-1]
        if any(s in slug.lower() for s in skip):
            continue
        if needle in slug.lower():
            return m
    for m in matches:
        slug = m.rsplit('/', 1)[-1]
        if not any(s in slug.lower() for s in skip):
            return m
    return None


def _extract_servers(html):
    # Pattern 3 (current production): Servers config is delivered via a
    # base64-encoded ``data:text/javascript`` script src tag.
    m = _SERVERS_DATAURL.search(html)
    if m:
        try:
            js = base64.b64decode(m.group(1)).decode('utf-8', 'replace')
            # Strip the ``var Servers=`` prefix to leave bare JSON.
            obj_m = re.search(r'Servers\s*=\s*(\{.+?\})\s*;?\s*$', js, re.S)
            if obj_m:
                return json.loads(obj_m.group(1))
        except Exception:
            pass
    m = _SERVERS_B64.search(html)
    if m:
        try:
            return json.loads(base64.b64decode(m.group(1)).decode('utf-8',
                                                                  'replace'))
        except Exception:
            pass
    m = _SERVERS_LITERAL.search(html)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


def _candidates(servers, source_site):
    out = []
    if not isinstance(servers, dict):
        return out
    # Only include keys that point to actual file-host chains:
    #   ``superembed``  -> fmovie-core player.php redirector (Filemoon /
    #                      Voe / Mixdrop chain that ResolveURL can crack).
    # Skip ``embedru`` / ``vidsrc`` (cloudnestra mirrors covered by
    # vidsrc.py) and ``premium`` (raw JSON API, not a file host).
    for key in ('superembed', 'filemoon', 'voe', 'mixdrop', 'streamtape',
                'streamwish', 'doodstream', 'mixdrp', 'upstream'):
        url = servers.get(key)
        if not isinstance(url, str) or not url.startswith('http'):
            continue
        host_name = RU.host_label(url) if RU.is_available() else key.capitalize()
        out.append({
            'url': url,
            'proto': 'HOSTER',
            'needs_resolveurl': True,
            'source_site': source_site,
            'host_name': host_name,
            'host_origin': source_site.lower(),
            'provider': 'filehost',
            'quality': 'auto',
            'label': '[auto] %s via %s' % (host_name, source_site),
        })
    return out


def _site(base, pretty, title):
    slug = _slug(base, title)
    if not slug:
        return []
    try:
        r = _http(slug + '/', headers={'Referer': base + '/'})
    except Exception as e:
        log('fh.fmovie_core[%s]: detail err %s' % (base, e))
        return []
    if r.status_code != 200:
        return []
    servers = _extract_servers(r.text)
    if not servers:
        return []
    return _candidates(servers, pretty)


def resolve(media_type, tmdb_id, imdb_id, title=None, year=None,
            season=None, episode=None) -> List[Dict]:
    if media_type != 'movie' or not title:
        return []
    out = []
    for pretty, base in HOSTS:
        try:
            out.extend(_site(base, pretty, title))
        except Exception as e:
            log('fh.fmovie_core[%s]: unhandled %s' % (base, e))
    return out
