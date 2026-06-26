# -*- coding: utf-8 -*-
"""Goojara file-host scraper (Wootly / Luluvdo / Dood / Vidsrc).

Goojara's site at ``ww1.goojara.to`` is a long-running indexer that lists
several hosters per title — most of which ResolveURL can crack:

    * Wootly (wolfstream / wooly)
    * Luluvdo
    * Doodstream
    * Vidsrc

Flow
----
1. Warm the session with a GET on the homepage so Cloudflare drops
   ``__cf_bm`` and the JS-set cookie (we only need the basic one — the
   challenge cookie comes from a real browser, so on data-centre IPs
   the search xhr returns empty; on a residential / mobile IP it works
   fine).
2. POST ``q=<title>`` to ``/xmre.php`` with the right XHR headers. The
   response is a tiny HTML fragment containing ``<a href="/<slug>"``
   for each match.
3. Fetch the detail page at ``https://ww1.goojara.to/<slug>``.
4. Scrape every ``<a class="bcg" href="...go.php?url=B64">HOST<span>Q</span></a>``
   into a candidate. The go.php URL is the Goojara redirector — we ship
   it as-is and let ResolveURL follow the redirect to the underlying
   filehost (RU has built-in support for Goojara's redirector via the
   ``GoojaraResolver`` plugin in mainline RU; on installs that don't
   have it, the user just gets ``Could not resolve <host>`` — the
   addon won't crash).

This scraper is one of the file-host providers — emits ``needs_resolveurl
=True`` and inherits ``sort_weight=999`` from ``filehosts.py`` so it
sits at the bottom of the picker, never competing with the direct
.m3u8 / .mp4 streams returned by Cloudnestra / Stigstream / Vidnest.
"""
from __future__ import annotations

import re
from typing import List, Dict
from urllib.parse import quote_plus

import requests

from ..common import log
from .. import resolveurl_bridge as RU

SITE = 'Goojara'
BASE = 'https://ww1.goojara.to'
TIMEOUT = 12
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# <li><a href="/<slug>"><div class="im"><strong>Title</strong> (Year) ...</a></li>
_SLUG_RE = re.compile(
    r'<a\s+href="(/[a-zA-Z0-9]{5,12})"[^>]*>\s*'
    r'(?:<div[^>]*>\s*)*<strong>([^<]+)</strong>'
    r'(?:\s*\(?(\d{4})\)?)?',
    re.I | re.S,
)
# <a class="bcg" href="...go.php?url=B64">HostName <span>QUAL</span></a>
_BCG_RE = re.compile(
    r"""<a\s+class=['"]bcg['"]\s+href=['"]([^'"]+)['"][^>]*>\s*([^<\s]+)\s*"""
    r"""(?:<span[^>]*>([^<]+)</span>)?""",
    re.I | re.S,
)


def _session_and_tokens():
    """Warm session and pull the two CSRF-style tokens Goojara wants on
    every search XHR.

    The homepage exposes:
      * ``<div id="res" data-ins="<RANDOM-PER-VISIT-TOKEN>">`` — used as
        the ``z=`` param.
      * an inline ``<script>`` that POSTs ``z=…&x=<STATIC-WEEKLY>&q=…``.
        The ``x`` value rotates roughly weekly so we extract it dynamically
        rather than hard-coding it.

    Returns ``(session, z, x)`` or ``(session, None, None)`` if either
    token is missing (e.g. Cloudflare challenge replaced the page).
    """
    s = requests.Session()
    s.headers.update({
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': BASE + '/',
    })
    try:
        r = s.get(BASE + '/', timeout=TIMEOUT)
        html = r.text
    except Exception as e:
        log('fh.goojara: warm-up failed %s' % e)
        return s, None, None
    m_z = re.search(r'id=["\']res["\'][^>]*data-ins=["\']([^"\']+)["\']', html)
    m_x = re.search(
        r"""['"]?z=['"]?\s*\+\s*\w+\s*\+\s*['"]&x=([a-f0-9]{6,40})&q=""", html)
    z = m_z.group(1) if m_z else None
    x = m_x.group(1) if m_x else None
    if not (z and x):
        log('fh.goojara: missing search tokens (z=%s x=%s)'
            % ('yes' if z else 'no', 'yes' if x else 'no'))
    return s, z, x


def _find_slug(sess_and_tokens, title, year=None):
    """Search Goojara for the title, return the path slug (e.g. ``/myPGn2``)."""
    if not title:
        return None
    sess, z, x = sess_and_tokens
    if not (z and x):
        return None
    body = 'z=%s&x=%s&q=%s' % (z, x, quote_plus(title))
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': BASE + '/',
    }
    try:
        r = sess.post(BASE + '/xmre.php', data=body, headers=headers,
                      timeout=TIMEOUT)
    except Exception as e:
        log('fh.goojara: search err %s' % e)
        return None
    if r.status_code != 200 or not r.text:
        return None
    tl = title.lower()
    yr = str(year or '').strip()
    candidates = _SLUG_RE.findall(r.text)
    # candidates is a list of (slug, label, year_str) tuples.
    for slug, label, cand_year in candidates:
        lab_lo = (label or '').lower().strip()
        # Year match — prefer titles whose extracted year matches.
        if tl in lab_lo and yr and cand_year and yr == cand_year:
            return slug
    for slug, label, cand_year in candidates:
        lab_lo = (label or '').lower().strip()
        if tl in lab_lo:
            return slug
    return None


def _candidates_from_detail(html: str) -> List[Dict]:
    out = []
    seen_urls = set()
    for href, host, qual in _BCG_RE.findall(html):
        href = (href or '').strip()
        host = (host or '').strip().lower()
        if not href.startswith('http'):
            href = BASE + href if href.startswith('/') else BASE + '/' + href
        if not href or href in seen_urls:
            continue
        seen_urls.add(href)
        # The link itself is the goojara redirector — we let ResolveURL
        # follow it. RU's Goojara plugin (when installed) cracks the b64
        # query and resolves the underlying host.
        host_pretty = {
            'wootly': 'Wootly',
            'dood':   'Doodstream',
            'luluvdo': 'Luluvdo',
            'vidsrc': 'VidSrc',
            'mixdrop': 'Mixdrop',
            'voe':    'Voe',
            'filemoon': 'Filemoon',
            'streamtape': 'Streamtape',
            'streamwish': 'Streamwish',
        }.get(host, host.capitalize() or 'Unknown')
        # Skip Vidsrc — we already cover that via vidsrc.py (direct .m3u8).
        if host_pretty == 'VidSrc':
            continue
        # Probe RU for actual hoster name when available (more accurate).
        if RU.is_available():
            try:
                lbl = RU.host_label(href)
                if lbl and lbl != 'Unknown':
                    host_pretty = lbl
            except Exception:
                pass
        q = (qual or 'AUTO').upper().strip()
        out.append({
            'url': href,
            'proto': 'HOSTER',
            'needs_resolveurl': True,
            'source_site': SITE,
            'host_name': host_pretty,
            'host_origin': 'goojara.to',
            'provider': 'filehost',
            'quality': q,
            'label': '[%s] %s via %s' % (q, host_pretty, SITE),
        })
    return out


def resolve(media_type, tmdb_id, imdb_id, title=None, year=None,
            season=None, episode=None) -> List[Dict]:
    # Goojara hosts both movies AND TV episodes. For TV we'd hit the
    # show slug then /eN-sN sub-page; for now we ship movie support only
    # (TV scraping needs the episode-slug discovery step which uses a
    # separate XHR). PRs welcome.
    if media_type != 'movie':
        return []
    if not title:
        return []
    sess_and_tokens = _session_and_tokens()
    sess = sess_and_tokens[0]
    slug = _find_slug(sess_and_tokens, title, year=year)
    if not slug:
        log('fh.goojara: no slug found for %r (%s)' % (title, year))
        return []
    try:
        r = sess.get(BASE + slug, timeout=TIMEOUT)
    except Exception as e:
        log('fh.goojara: detail err %s' % e)
        return []
    if r.status_code != 200:
        log('fh.goojara: detail HTTP %s for %s' % (r.status_code, slug))
        return []
    cands = _candidates_from_detail(r.text)
    log('fh.goojara: %d candidate(s) for slug %s' % (len(cands), slug))
    return cands
