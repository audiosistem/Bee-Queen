# -*- coding: utf-8 -*-
"""EffedUpMovies scraper — direct HLS for cult / disturbing cinema.

The site at ``www.effedupmovies.com`` is a WordPress film index whose
post pages embed a direct ``.m3u8`` URL on their own CDN
(``sN.vvvv.effedupmovies.com/hls/vN/<slug>/index.m3u8``). No file-host
chain, no ResolveURL needed — these are first-class playable streams.

PORN FILTER
-----------
The site catalogues a lot of disturbing-but-legitimate cult / horror /
exploitation cinema (cult classics, video-nasty tier horror, etc) and we
keep that — these films sit alongside disc releases on legit storefronts.
But it ALSO tags some posts with categories that are pornographic / fetish
content per the user's hard rule "no porn allowed in vidscr". Any post
tagged with ANY of ``_BLOCKED_CATEGORIES`` is discarded entirely before
its m3u8 is even peeked at. The blocklist is the conservative reading
of the site's own taxonomy (see comments below for the case-by-case
reasoning) — if a film is borderline, this scraper drops it.

Sort weight
-----------
Per the user's instruction every new source goes at the BOTTOM of the
picker — ``sort_weight=999`` regardless of whether the stream is
direct or file-host. The existing Cloudnestra / Vidnest / Stigstream
tiers stay on top.
"""
from __future__ import annotations

import re
from typing import List, Dict
from urllib.parse import quote_plus

import requests

from ..common import log

SITE = 'EffedUpMovies'
BASE = 'https://www.effedupmovies.com'
TIMEOUT = 12
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# Pornographic / fetish content categories — strict block. Posts tagged
# with any of these are dropped entirely, never returned to the picker.
# Disturbing-but-not-porn cult cinema categories (gore, slasher, home
# invasion, serial-killers, horror, abduction, satanism, voyeur etc) are
# allowed — they're cult-horror taxonomy not porn.
_BLOCKED_CATEGORIES = {
    'hentai',
    'pornography',
    'porn',
    'adult-film',
    'adult',
    'xxx',
    'erotica',
    'erotic',
    'erotic-thriller',
    'softcore',
    'hardcore',
    'masturbation',
    'sex-scene',
    'sexual-themes',
    'coprophilia',
    'formicophilia',
    'food-play',
    'bdsm',
    'fetish',
    'voyeurism',
    'nudity-explicit',
}

# Title keyword filter as a second line of defence — a title containing
# any of these is dropped even if categories slipped through.
_BLOCKED_TITLE_KEYWORDS = (
    ' porn', ' xxx ', 'hentai', 'erotic', 'softcore', 'hardcore',
    'masturbation',
)

_BOOKMARK_RE = re.compile(
    r'href="(https?://www\.effedupmovies\.com/([a-z0-9-]+)/)"\s+rel="bookmark"',
    re.I,
)
_CATEGORY_RE = re.compile(r'\bcategory-([a-z0-9-]+)\b')
_M3U8_RE = re.compile(
    r'(?:src|href|file)\s*=\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
    re.I,
)


def _http(url, **kw):
    h = kw.pop('headers', {})
    h.setdefault('User-Agent', UA)
    h.setdefault('Referer', BASE + '/')
    return requests.get(url, headers=h, timeout=TIMEOUT, **kw)


def _is_blocked(html: str, title: str = '') -> bool:
    cats = set(_CATEGORY_RE.findall(html))
    if cats & _BLOCKED_CATEGORIES:
        return True
    tl = (title or '').lower()
    return any(kw in tl for kw in _BLOCKED_TITLE_KEYWORDS)


def _find_post(title: str, year=None):
    """Search effedupmovies for a title, return the first bookmark URL
    whose slug looks like a match. Returns None on no match."""
    if not title:
        return None
    try:
        r = _http('%s/?s=%s' % (BASE, quote_plus(title)))
    except Exception as e:
        log('fh.effedupmovies: search err %s' % e)
        return None
    if r.status_code != 200:
        return None

    needle = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    yr = str(year or '').strip()
    matches = _BOOKMARK_RE.findall(r.text)
    if not matches:
        return None

    # Prefer slugs that include both the title needle and the year.
    if yr:
        for url, slug in matches:
            if needle in slug and yr in slug:
                return url
    for url, slug in matches:
        if needle in slug:
            return url
    return None


def _extract_streams(html: str) -> List[str]:
    seen, out = set(), []
    for u in _M3U8_RE.findall(html):
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def resolve(media_type, tmdb_id, imdb_id, title=None, year=None,
            season=None, episode=None) -> List[Dict]:
    # Site is movies-only. TV episodes are not indexed.
    if media_type != 'movie' or not title:
        return []

    post_url = _find_post(title, year=year)
    if not post_url:
        log('fh.effedupmovies: no post match for %r (%s)' % (title, year))
        return []

    try:
        r = _http(post_url)
    except Exception as e:
        log('fh.effedupmovies: detail err %s' % e)
        return []
    if r.status_code != 200:
        log('fh.effedupmovies: detail HTTP %s for %s' % (r.status_code, post_url))
        return []

    if _is_blocked(r.text, title):
        log('fh.effedupmovies: BLOCKED %r (matched porn filter)' % post_url)
        return []

    streams = []
    for m3u8 in _extract_streams(r.text):
        streams.append({
            'url': m3u8,
            'proto': 'DIRECT',
            'needs_resolveurl': False,  # direct HLS — plays without RU
            'source_site': SITE,
            'host_name': 'EUM-CDN',
            'host_origin': 'effedupmovies.com',
            'provider': 'filehost',
            'quality': 'AUTO',
            'sort_weight': 999,  # bottom of picker (user-mandated)
            'headers': {
                'Referer': post_url,
                'User-Agent': UA,
            },
            'label': '[AUTO HLS] EffedUpMovies',
        })
    log('fh.effedupmovies: %d direct stream(s) for %r' % (len(streams), title))
    return streams
