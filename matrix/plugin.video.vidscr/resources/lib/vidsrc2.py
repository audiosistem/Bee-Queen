# -*- coding: utf-8 -*-
"""Secondary provider — iframe-scraping fallbacks across multiple mirrors.

v1.4.9:
  * The v1.4.8 attempt to add JSON-API resolvers (vidsrc.icu, vidlink.pro,
    vidjoy.pro) was based on outdated public docs — those endpoints all return
    404. Removed.
  * Fixed the v1.4.8 regression where ``sources.py`` overrode
    ``secondary_source_host`` on a fresh ``xbmcaddon.Addon()`` instance, but
    ``vidsrc2._host()`` reads from the module-level ``common.ADDON`` singleton
    (different cached instance) — meaning every host in the auto-fallback chain
    was actually hitting whatever was saved under that setting (e.g. vidsrc.to)
    instead of the host requested. ``resolve_all`` now accepts an explicit
    ``host`` parameter that bypasses the setting entirely.
  * Added inner-iframe scraping for ``vidsrc.icu`` — its ``/embed/movie/{id}``
    page contains an iframe pointing at ``vidsrcme.vidsrc.icu`` which IS scrape-
    able with the existing cloudnestra resolver.

NOTE — Most public free streaming proxies have moved to JavaScript-based
player loaders + Cloudflare challenges in 2026, which static HTTP scrapers
cannot defeat. Streams may still fail to resolve regardless of how clever
the upstream URL detection is. See the README in this addon for a list of
realistic alternatives (Real-Debrid integration, self-hosted resolver, etc.).
"""
import re
import requests

from .common import log

TIMEOUT = 20
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# Hosts the user can choose from in settings (and that the auto-fallback /
# multi-link aggregator iterates through).
KNOWN_HOSTS = (
    'vidsrc.xyz', 'vidsrc.to', 'vidsrc.net',
    'vidsrc.icu',
    '2embed.cc', '2embed.skin',
    'multiembed.mov', 'moviesapi.club',
)


def _session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': UA,
        'Accept-Language': 'en-GB,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        # v1.4.12 — DO NOT advertise Brotli (Kodi's Python on Android can't
        # decode it). gzip+deflate are handled natively.
        'Accept-Encoding': 'gzip, deflate',
    })
    return s


def _build_embed_url(host, media_type, tmdb_id, season=None, episode=None, imdb_id=None):
    ident = imdb_id or tmdb_id
    s, e = season or 1, episode or 1

    # vidsrc.xyz / vidsrc.to / vidsrc.net — share routing scheme.
    if host in ('vidsrc.xyz', 'vidsrc.to', 'vidsrc.net'):
        if media_type == 'movie':
            return 'https://%s/embed/movie/%s' % (host, ident)
        url = 'https://%s/embed/tv/%s' % (host, ident)
        if season is not None:
            url += '/%s' % season
        if episode is not None:
            url += '-%s' % episode
        return url

    # vidsrc.icu — wraps an inner vidsrcme.vidsrc.icu iframe that yields
    # cloudnestra rcp URLs. Uses both tmdb and imdb args.
    if host == 'vidsrc.icu':
        if media_type == 'movie':
            return 'https://vidsrc.icu/embed/movie/%s' % ident
        return 'https://vidsrc.icu/embed/tv/%s/%s/%s' % (ident, s, e)

    # multiembed.mov — query-string style, accepts both IMDb and TMDB.
    if 'multiembed' in host:
        tmdb_flag = '&tmdb=1' if (not imdb_id and tmdb_id) else ''
        if media_type == 'movie':
            return 'https://%s/?video_id=%s%s' % (host, ident, tmdb_flag)
        return 'https://%s/?video_id=%s&s=%s&e=%s%s' % (host, ident, s, e, tmdb_flag)

    # moviesapi.club — TMDB-only, hyphenated TV path.
    if 'moviesapi' in host:
        mid = tmdb_id or ident
        if media_type == 'movie':
            return 'https://%s/movie/%s' % (host, mid)
        return 'https://%s/tv/%s-%s-%s' % (host, mid, s, e)

    # 2embed.cc / 2embed.skin (generic fallback)
    if media_type == 'movie':
        return 'https://%s/embed/%s' % (host, ident)
    return 'https://%s/embedtv/%s&s=%s&e=%s' % (host, ident, s, e)


def _extract_iframes(html):
    urls = []
    for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I):
        u = m.group(1)
        if u.startswith('//'):
            u = 'https:' + u
        if u and u not in urls:
            urls.append(u)
    # Also: hashes embedded via data-hash for 2embed-style server lists.
    for m in re.finditer(r'data-hash=["\']([^"\']+)["\']', html):
        urls.append('https://2embed.cc/embed/' + m.group(1))
    return urls


_DIRECT_MEDIA_PATTERNS = (
    r"""file\s*:\s*['"]([^'"]+?\.(?:m3u8|mp4)[^'"]*)['"]""",
    r"""sources?\s*:\s*\[\s*\{[^}]*?file\s*:\s*['"]([^'"]+?)['"]""",
    r"""['"](https?://[^'"\s]+?\.m3u8[^'"\s]*)['"]""",
    r"""['"](https?://[^'"\s]+?\.mp4[^'"\s]*)['"]""",
    r"""(https?://[^\s'"<>(){}]+?\.m3u8[^\s'"<>(){}]*)""",
)


def _scrape_media(body):
    if not body:
        return []
    seen = set()
    out = []
    for pat in _DIRECT_MEDIA_PATTERNS:
        for m in re.finditer(pat, body):
            u = m.group(1).strip()
            if u.startswith('//'):
                u = 'https:' + u
            if not u.startswith('http'):
                continue
            if not re.search(r'\.(?:m3u8|mp4|ts|mkv)(?:\?|$)', u, re.I):
                continue
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
    return out


def _try_resolveurl(url):
    try:
        import resolveurl  # type: ignore
    except ImportError:
        return None
    try:
        hmf = resolveurl.HostedMediaFile(url=url, include_disabled=False, include_universal=True)
        if not hmf.valid_url():
            return None
        resolved = hmf.resolve()
        return resolved or None
    except Exception as e:
        log('vidsrc2: ResolveURL failed for %s: %s' % (url[:90], e))
        return None


def _follow_iframe(sess, url, referer, depth=2):
    if depth <= 0 or not url:
        return []
    try:
        r = sess.get(url, timeout=TIMEOUT, headers={
            'Referer': referer,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    except Exception as e:
        log('vidsrc2: follow iframe failed %s: %s' % (url[:80], e))
        return []
    body = r.text or ''
    media = _scrape_media(body)
    if media:
        return media
    inner = []
    for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', body, re.I):
        u = m.group(1)
        if u.startswith('//'):
            u = 'https:' + u
        if u.startswith('http') and u != url:
            inner.append(u)
    for inner_url in inner[:3]:
        sub = _follow_iframe(sess, inner_url, url, depth - 1)
        if sub:
            return sub
    return []


def _resolve_via_vidsrc_icu_inner(sess, embed_url):
    """vidsrc.icu wraps an inner vidsrcme.vidsrc.icu iframe whose body contains
    cloudnestra rcp URLs that the primary `vidsrc.py` resolver knows how to
    chase. Hand off to that resolver."""
    try:
        r = sess.get(embed_url, timeout=TIMEOUT,
                     headers={'Referer': 'https://vidsrc.icu/'})
        if r.status_code != 200:
            log('vidsrc2 [vidsrc.icu]: outer status=%s' % r.status_code)
            return []
        # Find the inner vidsrcme iframe
        m = re.search(r'<iframe[^>]+src=["\'](https?:[^"\']+vidsrcme[^"\']+)["\']', r.text)
        if not m:
            log('vidsrc2 [vidsrc.icu]: no inner vidsrcme iframe found')
            return []
        inner = m.group(1).replace('//', 'https://', 1) if m.group(1).startswith('//') else m.group(1)
        log('vidsrc2 [vidsrc.icu]: inner iframe -> %s' % inner[:100])
        body = sess.get(inner, timeout=TIMEOUT,
                        headers={'Referer': embed_url}).text
    except Exception as e:
        log('vidsrc2 [vidsrc.icu]: fetch failed %s' % e)
        return []
    # Extract cloudnestra rcp links and chase them with the primary resolver
    from . import vidsrc as V1
    rcp_urls = []
    # Capture group #1 wraps the alternation (was missing in v1.4.9 → "no such group")
    pat = re.compile(
        r'(?:src=|data-hash=)["\']'
        r'(//cloudnestra\.com/rcp/[^"\']+|[A-Za-z0-9+/=_\-]{40,})'
        r'["\']'
    )
    for mm in pat.finditer(body):
        u = mm.group(1)
        if u.startswith('//'):
            u = 'https:' + u
        elif not u.startswith('http'):
            u = 'https://cloudnestra.com/rcp/' + u
        if u not in rcp_urls:
            rcp_urls.append(u)
    streams = []
    for u in rcp_urls[:3]:
        try:
            sub = V1._resolve_cloudnestra(u, sess, inner, server_name='vidsrc.icu')
            for s in sub:
                s.setdefault('provider', 'vidsrc2')
                s['server'] = 'vidsrc.icu'
            streams.extend(sub)
        except Exception as e:
            log('vidsrc2 [vidsrc.icu]: sub-resolve failed %s' % e)
    return streams


def _scrape_iframe_host(sess, host, media_type, tmdb_id, season, episode, imdb_id):
    embed_url = _build_embed_url(host, media_type, tmdb_id, season, episode, imdb_id)
    log('vidsrc2 [%s]: fetching %s' % (host, embed_url))

    # Special-case vidsrc.icu — wrap the inner iframe via the primary resolver
    if host == 'vidsrc.icu':
        inner_streams = _resolve_via_vidsrc_icu_inner(sess, embed_url)
        if inner_streams:
            return inner_streams
        # else fall through to generic iframe scrape

    try:
        r = sess.get(embed_url, timeout=TIMEOUT,
                     headers={'Referer': 'https://%s/' % host})
        if r.status_code != 200:
            log('vidsrc2 [%s]: status=%s' % (host, r.status_code))
            return []
        html = r.text
    except Exception as e:
        log('vidsrc2 [%s]: fetch failed %s' % (host, e))
        return []

    streams = []
    direct = _scrape_media(html)
    if direct:
        log('vidsrc2 [%s]: direct media on embed page: %d' % (host, len(direct)))
        for i, u in enumerate(direct):
            h = re.sub(r'^https?://', '', u).split('/')[0]
            is_hls = '.m3u8' in u.lower()
            proto = 'HLS' if is_hls else 'MP4'
            streams.append({
                'url': u,
                'headers': {'User-Agent': UA, 'Referer': 'https://%s/' % host},
                'label': '[%s] direct • %s (%s)' % (proto, h, host),
                'quality': proto, 'proto': proto, 'host': h,
                'server': '%s direct #%d' % (host, i + 1),
                'height': 0, 'bandwidth': 0, 'provider': 'vidsrc2',
            })

    iframes = _extract_iframes(html)
    log('vidsrc2 [%s]: found %d iframe candidates' % (host, len(iframes)))

    for i, u in enumerate(iframes[:6]):
        media_urls = _follow_iframe(sess, u, embed_url, depth=2)
        if media_urls:
            for mu in media_urls:
                h = re.sub(r'^https?://', '', mu).split('/')[0]
                is_hls = '.m3u8' in mu.lower()
                proto = 'HLS' if is_hls else 'MP4'
                streams.append({
                    'url': mu,
                    'headers': {'User-Agent': UA, 'Referer': u},
                    'label': '[%s] %s • %s (%s)' % (proto, proto, h, host),
                    'quality': proto, 'proto': proto, 'host': h,
                    'server': '%s scrape #%d' % (host, i + 1),
                    'height': 0, 'bandwidth': 0, 'provider': 'vidsrc2',
                })
            continue

        resolved = _try_resolveurl(u)
        if not resolved:
            continue
        is_hls = '.m3u8' in resolved.lower()
        is_mp4 = '.mp4' in resolved.lower()
        proto = 'HLS' if is_hls else ('MP4' if is_mp4 else 'AUTO')
        h = re.sub(r'^https?://', '', resolved).split('/')[0]
        streams.append({
            'url': resolved,
            'headers': {'User-Agent': UA, 'Referer': 'https://%s/' % host},
            'label': '[%s] %s • %s (%s)' % (proto, proto, h, host),
            'quality': proto, 'proto': proto, 'host': h,
            'server': '%s ResolveURL #%d' % (host, i + 1),
            'height': 0, 'bandwidth': 0, 'provider': 'vidsrc2',
        })

    return streams


def resolve_all(media_type, tmdb_id, season=None, episode=None, imdb_id=None,
                host=None):
    """Resolve via the secondary scrape pipeline.

    ``host`` (str, optional) — if given, forces this specific host without
    touching addon settings (avoids the v1.4.8 regression where the setting
    override on a fresh ``xbmcaddon.Addon()`` instance was invisible to the
    module-level ``common.ADDON`` singleton)."""
    sess = _session()
    if host is None:
        # Fall back to the user's setting, default vidsrc.xyz.
        from .common import get_setting
        host = (get_setting('secondary_source_host', 'vidsrc.xyz')
                or 'vidsrc.xyz').strip().rstrip('/')
        if host.startswith('http'):
            host = re.sub(r'^https?://', '', host)
    return _dedupe(_scrape_iframe_host(sess, host, media_type, tmdb_id,
                                       season, episode, imdb_id))


def _dedupe(streams):
    seen = set()
    out = []
    for s in streams:
        u = s.get('url')
        if u and u not in seen:
            seen.add(u)
            out.append(s)
    log('vidsrc2: resolved %d streams' % len(out))
    return out
