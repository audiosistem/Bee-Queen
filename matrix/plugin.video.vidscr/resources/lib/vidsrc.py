# -*- coding: utf-8 -*-
"""Vidsrc resolver — vidsrcme.ru -> cloudnestra rcp -> prorcp -> hls/mp4 sources.

This resolver returns a *list* of candidate streams (one per server / quality
variant) so the addon can present a link/quality picker to the user.

v1.4.6 — fixes "No streams available" caused by:
  * Cloudnestra page format changes (iframe injected via JS, no longer in static
    HTML). We now try ~10 different next-hop patterns instead of 4.
  * Direct m3u8/mp4 URLs are now extracted from BOTH the rcp page and the
    next-hop body (whichever has them) — no more dead-end when the prorcp page
    doesn't expose `file:`.
  * Secondary fallback no longer requires ResolveURL — we scrape iframe bodies
    directly for m3u8/mp4 URLs first, only falling back to ResolveURL if that
    fails.
  * Cloudflare-challenged rcp pages now retry with browser-like Sec-Fetch
    headers (sometimes lets the request through).
  * XOR-decode of any `data-h` + `data-i` pair on the rcp page (older
    vidsrc.stream / new cloudnestra variant).
"""
import re
import requests

from .common import get_setting, get_setting_bool, log

DEFAULT_HOST = 'vidsrcme.ru'
TIMEOUT = 20
PROBE_TIMEOUT = 8

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# Known Cloudnestra CDN hostnames used with {vN} placeholders (fallback pool).
# Order matters — most reliable first.
CDN_POOL = [
    'shadowlandschronicles.com',
    'cdn-centaurus.com',
    'cdn-fnc.com',
    'shadowlands-cdn.com',
    'nestra-cdn.com',
    'cloudnestra.com',
    'tmstr-cdn.com',
]

# Quality buckets (height, label) - used to bucket master.m3u8 variants.
QUALITY_BUCKETS = [
    (2160, '4K'),
    (1440, '1440p'),
    (1080, '1080p'),
    (720, '720p'),
    (480, '480p'),
    (360, '360p'),
    (240, '240p'),
]

# Preferred order for auto-play (matches user's request: 4K → 1080 → 720 → 480 → 360)
QUALITY_ORDER = ['4K', '1440p', '1080p', '720p', '480p', '360p', '240p', 'HLS', 'MP4', 'AUTO']


def _host():
    h = (get_setting('vidsrc_host', DEFAULT_HOST) or DEFAULT_HOST).strip().rstrip('/')
    if h.startswith('http'):
        h = re.sub(r'^https?://', '', h)
    return h or DEFAULT_HOST


def _session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': UA,
        'Accept-Language': 'en-GB,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        # v1.4.12 — see _BROWSER_HEADERS comment: never advertise brotli.
        'Accept-Encoding': 'gzip, deflate',
    })
    return s


def _build_embed_url(media_type, tmdb_id, season=None, episode=None, imdb_id=None):
    host = _host()
    ident = imdb_id or tmdb_id
    if media_type == 'movie':
        return 'https://%s/embed/movie/%s' % (host, ident)
    parts = ['https://%s/embed/tv/%s' % (host, ident)]
    if season is not None:
        parts.append(str(season))
    if episode is not None:
        parts.append(str(episode))
    return '/'.join(parts)


def _extract_servers(html):
    """Find every cloudnestra rcp source on the embed page."""
    servers = []
    seen = set()

    def _add(url, name='Cloudnestra'):
        if url and url not in seen:
            seen.add(url)
            servers.append({'type': 'cloudnestra', 'url': url, 'name': name})

    for m in re.finditer(r'src=["\'](//cloudnestra\.com/rcp/[^"\']+)["\']', html):
        _add('https:' + m.group(1))
    for m in re.finditer(r'src=["\'](https?://cloudnestra\.com/rcp/[^"\']+)["\']', html):
        _add(m.group(1))
    # Server picker UI: <ul ... data-server data-hash=...>
    for m in re.finditer(r'data-hash=["\']([^"\']+)["\'][^>]*data-i=["\'](\d+)["\']', html):
        _add('https://cloudnestra.com/rcp/' + m.group(1), 'Cloudnestra #%s' % m.group(2))
    for m in re.finditer(r'data-hash=["\']([^"\']+)["\']', html):
        h = m.group(1)
        # Hashes can contain base64 padding (=), keep them
        if len(h) > 20:
            _add('https://cloudnestra.com/rcp/' + h)

    log('Vidsrc: found %d server(s) in embed page' % len(servers))
    return servers


def _parse_server_pool(body):
    """Extract a list of CDN hostnames from JS in the prorcp page."""
    pool = []
    for m in re.finditer(r"""(?:servers|cdns|hosts|srv|cdn_list)\s*[:=]\s*\[([^\]]+)\]""", body, re.I):
        for s in re.findall(r"""['"]([a-z0-9.\-]+\.[a-z]{2,})['"]""", m.group(1), re.I):
            if s not in pool:
                pool.append(s)
    for s in re.findall(r'tmstr\d?\.([a-z0-9.\-]+\.[a-z]{2,})', body, re.I):
        if s not in pool:
            pool.append(s)
    for s in re.findall(r'app\d?\.([a-z0-9.\-]+\.[a-z]{2,})', body, re.I):
        if s not in pool:
            pool.append(s)
    log('Vidsrc: parsed %d pool hostnames from page' % len(pool))
    return pool


def _expand_templates(raw_file, page_pool):
    """Given a raw file string with optional {vN} placeholders and ' or '
    separators, return a list of concrete candidate URLs."""
    parts = [p.strip() for p in re.split(r'\s+or\s+', raw_file) if p.strip()]
    pool = list(dict.fromkeys((page_pool or []) + CDN_POOL))

    candidates = []
    for part in parts:
        placeholders = sorted(set(re.findall(r'\{v(\d+)\}', part)))
        if not placeholders:
            if part not in candidates:
                candidates.append(part)
            continue
        for host in pool:
            url = part
            for n in placeholders:
                url = url.replace('{v%s}' % n, host)
            if url not in candidates:
                candidates.append(url)
    log('Vidsrc: expanded to %d candidate URLs' % len(candidates))
    return candidates


def _probe(url, referer, sess):
    try:
        r = sess.get(url, headers={'Referer': referer,
                                   'Origin': 'https://' + referer.split('/')[2]},
                     timeout=PROBE_TIMEOUT, stream=True, allow_redirects=True)
        ok = 200 <= r.status_code < 300
        text = ''
        if ok:
            try:
                text = r.raw.read(8192).decode('utf-8', errors='replace')
            except Exception:
                text = ''
        r.close()
        log('Vidsrc probe %s -> %d' % (url[:90], r.status_code))
        return ok, text
    except Exception as e:
        log('Vidsrc probe failed %s: %s' % (url[:90], e))
        return False, ''


def _parse_master_m3u8(text, base_url):
    """Parse #EXT-X-STREAM-INF lines and return list of (label, url, height, bandwidth)."""
    if '#EXTM3U' not in text or '#EXT-X-STREAM-INF' not in text:
        return []
    variants = []
    lines = text.splitlines()
    base = base_url.rsplit('/', 1)[0] + '/'
    for i, line in enumerate(lines):
        if line.startswith('#EXT-X-STREAM-INF'):
            res_m = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
            bw_m = re.search(r'BANDWIDTH=(\d+)', line)
            height = int(res_m.group(2)) if res_m else 0
            bw = int(bw_m.group(1)) if bw_m else 0
            uri = lines[i + 1].strip() if i + 1 < len(lines) else ''
            if not uri or uri.startswith('#'):
                continue
            if not uri.startswith('http'):
                uri = base + uri
            label = 'AUTO'
            for h, ql in QUALITY_BUCKETS:
                if height >= h:
                    label = ql
                    break
            variants.append({'label': label, 'url': uri, 'height': height, 'bandwidth': bw})
    return variants


_CF_MARKERS = ('Attention Required', 'cf-error-details', 'Just a moment',
               'Enable JavaScript and cookies', 'challenge-platform',
               '__cf_chl_', 'cf-mitigated')


def _looks_like_cf_challenge(body):
    if not body:
        return False
    head = body[:4096]
    return any(m in head for m in _CF_MARKERS)


_BROWSER_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    # v1.4.12 — DO NOT advertise Brotli ('br'). Kodi's bundled Python on
    # Android does not ship the 'brotli' module, so requests returns the raw
    # compressed bytes when the server picks brotli — which on cloudnestra
    # means the entire prorcp body decodes to ~200 bytes of binary garbage,
    # ``_find_next_hop`` fails to extract the prorcp link, and we end up
    # with "no candidates". gzip+deflate (handled natively by stdlib) work
    # fine and cloudnestra honours them.
    'Accept-Encoding': 'gzip, deflate',
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'iframe',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}


# Cloudnestra mirror hostnames. When DNS resolution for cloudnestra.com
# fails (some ISPs / DNS providers block the domain at NXDOMAIN), the
# fetcher retries the same path against each of these hosts. The list is
# ordered by historical reliability.
_CLOUDNESTRA_MIRRORS = (
    'cloudnestra.com',
    'nestra-cdn.com',
    'tmstr-cdn.com',
    'shadowlandschronicles.com',
    'rcp.streamembed.com',
)


def _fetch(sess, url, referer, allow_cf_retry=True):
    """Fetch a URL with browser-like headers; on Cloudflare challenge, retry once
    with a different UA (mobile) which sometimes bypasses the static block.

    Cloudnestra-specific failover: if the host is ``cloudnestra.com`` and the
    request fails (DNS resolution / connect timeout — both report as a
    ``ConnectionError`` / ``getaddrinfo failed`` to requests), retry the
    same path against each mirror in ``_CLOUDNESTRA_MIRRORS``."""
    hdrs = dict(_BROWSER_HEADERS)
    hdrs['Referer'] = referer

    urls_to_try = [url]
    if 'cloudnestra.com/' in url:
        for mirror in _CLOUDNESTRA_MIRRORS[1:]:
            urls_to_try.append(url.replace('cloudnestra.com', mirror, 1))

    body = ''
    last_err = None
    for try_url in urls_to_try:
        try:
            r = sess.get(try_url, headers=hdrs, timeout=TIMEOUT)
            body = r.text
            if try_url != url:
                log('Vidsrc: mirror %s succeeded for %s'
                    % (try_url.split('/')[2], url.split('/')[2]))
            break
        except Exception as e:
            last_err = e
            # Try the next mirror only on network-level failures (DNS, connect).
            msg = str(e).lower()
            if 'getaddrinfo' not in msg and 'name resolution' not in msg \
               and 'name or service' not in msg \
               and 'connection' not in msg \
               and 'timed out' not in msg:
                break
    if not body and last_err is not None:
        log('Vidsrc fetch failed %s: %s' % (url[:90], last_err))
        return ''
    if allow_cf_retry and _looks_like_cf_challenge(body):
        log('Vidsrc: CF challenge on %s — retrying with mobile UA' % url[:80])
        try:
            mobile_ua = ('Mozilla/5.0 (Linux; Android 13; Pixel 6) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/124.0 Mobile Safari/537.36')
            hdrs2 = dict(hdrs)
            hdrs2['User-Agent'] = mobile_ua
            r2 = sess.get(url, headers=hdrs2, timeout=TIMEOUT)
            body = r2.text
        except Exception as e:
            log('Vidsrc CF retry failed: %s' % e)
    return body


def _xor_decode(encoded_hex, seed):
    """Old-style cloudnestra/vidsrc.stream XOR cipher: bytes.fromhex(encoded)
    XORed against seed string (typically the imdb id)."""
    try:
        buf = bytes.fromhex(encoded_hex)
        seed_b = seed.encode('utf-8') if isinstance(seed, str) else seed
        if not seed_b:
            return ''
        out = bytearray(len(buf))
        for i, b in enumerate(buf):
            out[i] = b ^ seed_b[i % len(seed_b)]
        return out.decode('utf-8', errors='replace')
    except Exception as e:
        log('Vidsrc XOR decode failed: %s' % e)
        return ''


def _extract_data_h(body):
    """Look for the {data-h, data-i} XOR-encoded hidden source pattern."""
    enc = re.search(r'data-h=["\']([0-9a-fA-F]+)["\']', body)
    seed = re.search(r'data-i=["\']([^"\']+)["\']', body)
    if not enc or not seed:
        return None
    decoded = _xor_decode(enc.group(1), seed.group(1))
    if decoded and ('http' in decoded or decoded.startswith('//') or decoded.startswith('/')):
        log('Vidsrc: XOR-decoded hidden source -> %s' % decoded[:120])
        return decoded.strip()
    return None


def _find_next_hop(body, current_host):
    """Find the next-hop iframe/redirect URL in a cloudnestra-like page.

    Tries a wide range of patterns so we still resolve when cloudnestra
    renames or obfuscates the /prorcp/ endpoint. Returns an absolute URL or None.
    """
    if not body:
        return None

    # 0. XOR-decoded hidden source (old vidsrc.stream variant, sometimes
    #    re-used by cloudnestra after challenge passes).
    decoded = _extract_data_h(body)
    if decoded:
        return _abs_url(decoded, current_host)

    # 1. Iframe src anywhere in the body. Prefer same-origin / relative URLs.
    iframes = []
    for m in re.finditer(r'<iframe[^>]+src=["\']([^"\'#]+)["\']', body, re.I):
        href = m.group(1).strip()
        if not href or href.startswith('about:') or href.lower() == '#':
            continue
        iframes.append(href)
    iframes.sort(key=lambda h: 0 if h.startswith('/') else 1)
    if iframes:
        return _abs_url(iframes[0], current_host)

    # 2. Classic /prorcp/ style paths plus newer variants
    #    (/prosrc/, /rcp2/, /source/, /embed/player/, /pe/).
    for pat in (
        r"""src\s*[:=]\s*['"]([^'"]*?/prorcp/[^'"]+)['"]""",
        r"""['"](/prorcp/[A-Za-z0-9+/=_\-]+)['"]""",
        r"""(/prorcp/[A-Za-z0-9+/=_\-]{8,})""",
        r"""['"](/(?:prosrc|rcp2|source|embed/player|pe|nrcp)/[A-Za-z0-9+/=_\-]{8,})['"]""",
        r"""window\.location(?:\.href)?\s*=\s*['"]([^'"]+)['"]""",
        r"""location\.replace\(\s*['"]([^'"]+)['"]""",
        # JS-set iframe.src = "...", iframe.setAttribute('src', '...')
        r"""\.src\s*=\s*['"]([^'"]+)['"]""",
        r"""setAttribute\(['"]src['"]\s*,\s*['"]([^'"]+)['"]""",
        # document.write of an <iframe>
        r"""document\.write\([^)]*<iframe[^>]+src=\\?["']([^"'\\]+)""",
        # Atob-decoded prorcp
        r"""atob\(['"]([A-Za-z0-9+/=]{20,})['"]""",
    ):
        m = re.search(pat, body)
        if not m:
            continue
        candidate = m.group(1)
        # If pattern was atob, decode it
        if 'atob' in pat:
            try:
                import base64
                candidate = base64.b64decode(candidate + '==').decode('utf-8', errors='replace')
            except Exception:
                continue
        if candidate.startswith('http') or candidate.startswith('/'):
            return _abs_url(candidate, current_host)

    return None


def _abs_url(href, current_host):
    if href.startswith('//'):
        return 'https:' + href
    if href.startswith('/'):
        return 'https://' + current_host + href
    if href.startswith('http'):
        return href
    return 'https://' + current_host + '/' + href


# Direct media URL extraction patterns — try these on EVERY body we get.
_DIRECT_MEDIA_PATTERNS = (
    r"""file\s*:\s*['"]([^'"]+?\.(?:m3u8|mp4)[^'"]*)['"]""",
    r"""file\s*:\s*['"]([^'"]+?)['"]""",
    r"""sources?\s*:\s*\[\s*\{[^}]*?file\s*:\s*['"]([^'"]+?)['"]""",
    r"""['"](https?://[^'"\s]+?\.m3u8[^'"\s]*)['"]""",
    r"""['"](https?://[^'"\s]+?\.mp4[^'"\s]*)['"]""",
    r"""src\s*:\s*['"](https?://[^'"\s]+?\.(?:m3u8|mp4)[^'"]*)['"]""",
    # NEW v1.4.10 — common newer variants we kept missing
    r"""(?:hls|playlist|playlistUrl|manifest|stream|src|href)\s*:\s*['"](https?://[^'"\s]+?\.m3u8[^'"\s]*)['"]""",
    r"""(?:hls|playlist|stream|src|href)\s*:\s*['"](https?://[^'"\s]+?\.mp4[^'"\s]*)['"]""",
    # JSON.parse(atob('...')) wrapped m3u8 — try every long b64 blob
    r"""atob\(\s*['"]([A-Za-z0-9+/=]{40,})['"]""",
    # URL with unicode-escaped slashes (\u002F\u002F)
    r"""(https?:\\u002[Ff]\\u002[Ff][^"'\s]+\\u002[Ff][^"'\s]+\.m3u8[^"'\s]*)""",
    # JSON manifest URL inside a <script type="application/json">
    r"""<script[^>]+type=["']application/json["'][^>]*>\s*\{[^<]*?["'](?:hls|playlist|manifest|src|file)["']\s*:\s*["']([^"']+?\.m3u8[^"']*)""",
    # Bare URL (no quotes) — last resort, helpful when minified
    r"""(https?://[^\s'"<>(){}]+?\.m3u8[^\s'"<>(){}]*)""",
)


def _find_direct_media(body):
    """Scan a body for any direct m3u8/mp4 URLs — returns list of unique URLs."""
    if not body:
        return []
    out = []
    seen = set()
    for pat in _DIRECT_MEDIA_PATTERNS:
        for m in re.finditer(pat, body):
            u = m.group(1).strip()
            # Skip obvious non-media (empty, hash placeholders, ad domains)
            if not u or '{v' in u or len(u) < 10:
                continue
            # If the match is a base64 blob (atob pattern), decode and re-scan
            if re.fullmatch(r'[A-Za-z0-9+/=]{40,}', u):
                try:
                    import base64
                    decoded = base64.b64decode(u + '===').decode('utf-8', errors='replace')
                    nm = re.search(r'(https?://[^\s\'"<>]+?\.m3u8[^\s\'"<>]*)', decoded)
                    if nm:
                        u = nm.group(1)
                    else:
                        continue
                except Exception:
                    continue
            # Decode unicode-escaped slashes
            if '\\u002' in u.lower():
                u = u.replace('\\u002F', '/').replace('\\u002f', '/')
            if not (u.startswith('http') or u.startswith('//')):
                continue
            if u.startswith('//'):
                u = 'https:' + u
            # Heuristic: must look like a media URL or contain a known stream ext
            if not re.search(r'\.(?:m3u8|mp4|ts|mkv)(?:\?|$)', u, re.I):
                # Allow templated raw_file lines that contain {vN} or " or "
                if ' or ' not in u and '{v' not in u:
                    continue
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def _resolve_cloudnestra(rcp_url, sess, referer, server_name='Cloudnestra'):
    """Return a list of stream candidates from a cloudnestra rcp link."""
    body = _fetch(sess, rcp_url, referer)
    if not body:
        return _resolveurl_single(rcp_url, referer, server_name)

    rcp_host = re.sub(r'^https?://', '', rcp_url).split('/')[0]

    if _looks_like_cf_challenge(body):
        log('cloudnestra: CF challenge on rcp (%d bytes)' % len(body))
        # Try ResolveURL (its cloudnestra plugin can sometimes pass CF).
        rs = _resolveurl_single(rcp_url, referer, server_name)
        if rs:
            return rs
        # Continue on — sometimes the CF page still has data-h embedded.

    # First: maybe the rcp page itself has a direct file: URL
    direct_urls_rcp = _find_direct_media(body)

    next_url = _find_next_hop(body, rcp_host)
    body2 = ''
    if next_url:
        log('cloudnestra: next hop -> %s' % next_url[:120])
        body2 = _fetch(sess, next_url, rcp_url)
        if _looks_like_cf_challenge(body2):
            log('cloudnestra: CF challenge on next-hop')
            rs = _resolveurl_single(rcp_url, referer, server_name)
            if rs:
                return rs

    # Combined search across both bodies
    raw_files = []
    for body_text in (body2, body):
        if not body_text:
            continue
        # Highest-quality match: 'file:"..."' style
        mf = re.search(r"""file\s*:\s*['"]([^'"]+?)['"]""", body_text)
        if mf and mf.group(1) not in raw_files:
            raw_files.append(mf.group(1))
        mf = re.search(r"""sources?\s*:\s*\[\s*\{[^}]*?file\s*:\s*['"]([^'"]+?)['"]""",
                       body_text, re.S)
        if mf and mf.group(1) not in raw_files:
            raw_files.append(mf.group(1))
        # NEW v1.4.10 — also look inside every inline <script> for an m3u8.
        # Many cloudnestra builds split decode logic across multiple script
        # tags and the global regex misses URLs constructed by string
        # concatenation. Reconstruct each tag, run the direct-media scan.
        for sm in re.finditer(r'<script[^>]*>([\s\S]{20,200000}?)</script>',
                              body_text):
            chunk = sm.group(1)
            # Try direct-media patterns on this chunk
            for u in _find_direct_media(chunk):
                if u not in raw_files:
                    raw_files.append(u)
            # Try base64-decoding any long base64 blob in the chunk
            for bm in re.finditer(r"['\"]([A-Za-z0-9+/=]{60,})['\"]", chunk):
                blob = bm.group(1)
                try:
                    import base64
                    decoded = base64.b64decode(blob + '===').decode(
                        'utf-8', errors='replace')
                    if '.m3u8' in decoded or '.mp4' in decoded:
                        for u in _find_direct_media(decoded):
                            if u not in raw_files:
                                raw_files.append(u)
                                log('cloudnestra: found media via b64-script decode')
                except Exception:
                    continue

    pool = _parse_server_pool(body2 or body)
    candidates = []
    for raw_file in raw_files:
        log('Vidsrc raw file: %s' % raw_file[:200])
        for c in _expand_templates(raw_file, pool):
            if '{v' not in c and c not in candidates:
                candidates.append(c)

    # Also append any direct media URLs found in either body.
    for u in _find_direct_media(body2) + direct_urls_rcp:
        if '{v' not in u and u not in candidates:
            candidates.append(u)

    if not candidates:
        # NEW v1.4.10 — dump the offending body to a debug file so the addon
        # owner can inspect what cloudnestra is actually serving and write a
        # decoder for it. v1.4.13: dump filename now includes a hash of the
        # rcp URL so multiple attempts in the same second don't overwrite
        # each other, and we keep a sample with non-empty next_body_len if
        # one is available.
        try:
            import os, time, json, base64, hashlib
            from .common import PROFILE_PATH
            dump_dir = os.path.join(PROFILE_PATH, 'cloudnestra_dumps')
            os.makedirs(dump_dir, exist_ok=True)
            ts = time.strftime('%Y%m%d-%H%M%S')
            url_hash = hashlib.md5(rcp_url.encode('utf-8')).hexdigest()[:8]
            tag = '_NEXTOK' if (body2 and len(body2) > 100) else '_NONEXT'
            # Re-fetch raw bytes for binary-safe inspection
            raw_rcp_b64 = ''
            raw_next_b64 = ''
            try:
                rb = sess.get(rcp_url, timeout=TIMEOUT,
                              headers={'Referer': referer}).content
                raw_rcp_b64 = base64.b64encode(rb).decode('ascii')
            except Exception:
                pass
            if next_url:
                try:
                    nb = sess.get(next_url, timeout=TIMEOUT,
                                  headers={'Referer': rcp_url}).content
                    raw_next_b64 = base64.b64encode(nb).decode('ascii')
                except Exception:
                    pass
            payload = {
                'timestamp': ts,
                'addon_version': '1.4.13',
                'rcp_url': rcp_url,
                'rcp_body_len': len(body),
                'rcp_body': body[:80000],
                'rcp_body_raw_b64': raw_rcp_b64,
                'next_url': next_url,
                'next_body_len': len(body2),
                'next_body': body2[:80000],
                'next_body_raw_b64': raw_next_b64,
            }
            path = os.path.join(
                dump_dir,
                'cloudnestra_dump_%s_%s%s.json' % (ts, url_hash, tag))
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False)
            log('cloudnestra: dumped failed bodies to %s (rcp=%db / next=%db)'
                % (path, len(body), len(body2)))
            # Keep at most 10 dumps total, BUT preferentially keep ones that
            # have a non-empty next_body (those are the useful ones).
            files = sorted(os.listdir(dump_dir))
            if len(files) > 10:
                # Drop _NONEXT ones first
                drops = [f for f in files if '_NONEXT' in f][:-2]
                if not drops:
                    drops = files[:-10]
                for old in drops:
                    try:
                        os.remove(os.path.join(dump_dir, old))
                    except Exception:
                        pass
        except Exception as e:
            log('cloudnestra: dump failed: %s' % e)
        # Also log the FULL prorcp body to the debug log when it's reasonably
        # short — gives us inline visibility without needing the dump round-trip.
        if body2 and len(body2) <= 5000:
            log('cloudnestra: prorcp body (%d chars):\n%s' % (len(body2), body2))
        log('cloudnestra: no candidates extracted — falling back to ResolveURL')
        return _resolveurl_single(rcp_url, referer, server_name)

    headers = {
        'User-Agent': UA,
        'Referer': 'https://cloudnestra.com/',
        'Origin': 'https://cloudnestra.com',
    }

    streams = []
    seen_urls = set()
    probed_ok = 0
    probe_enabled = get_setting_bool('probe_candidates', True)

    for url in candidates[:18]:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        is_hls = '.m3u8' in url.lower()
        is_mp4 = '.mp4' in url.lower()
        proto = 'HLS' if is_hls else ('MP4' if is_mp4 else 'AUTO')

        probed = True
        body_text = ''
        if probe_enabled:
            probed, body_text = _probe(url, 'https://cloudnestra.com/', sess)
        if not probed:
            continue
        probed_ok += 1

        host = re.sub(r'^https?://', '', url).split('/')[0]
        variants = _parse_master_m3u8(body_text, url) if is_hls else []
        if variants:
            for v in variants:
                streams.append({
                    'url': v['url'], 'headers': headers,
                    'label': '[%s] %s • %s' % (v['label'], proto, host),
                    'quality': v['label'], 'proto': proto, 'host': host,
                    'server': server_name, 'height': v['height'],
                    'bandwidth': v['bandwidth'],
                })
            streams.append({
                'url': url, 'headers': headers,
                'label': '[AUTO] %s master • %s' % (proto, host),
                'quality': 'AUTO', 'proto': proto, 'host': host,
                'server': server_name, 'height': 0, 'bandwidth': 0,
            })
        else:
            streams.append({
                'url': url, 'headers': headers,
                'label': '[%s] %s • %s' % (proto, proto, host),
                'quality': proto, 'proto': proto, 'host': host,
                'server': server_name, 'height': 0, 'bandwidth': 0,
            })

        if probed_ok >= 4:
            break

    if not streams:
        # Probing blocked — return raw candidates as-is so the user can still try.
        for url in candidates[:6]:
            host = re.sub(r'^https?://', '', url).split('/')[0]
            is_hls = '.m3u8' in url.lower()
            proto = 'HLS' if is_hls else ('MP4' if '.mp4' in url.lower() else 'AUTO')
            streams.append({
                'url': url, 'headers': headers,
                'label': '[%s] %s • %s (unprobed)' % (proto, proto, host),
                'quality': proto, 'proto': proto, 'host': host,
                'server': server_name, 'height': 0, 'bandwidth': 0,
            })
    return streams


def resolve_all(media_type, tmdb_id, season=None, episode=None, imdb_id=None):
    """Return a list of stream candidates."""
    sess = _session()
    embed_url = _build_embed_url(media_type, tmdb_id, season, episode, imdb_id)
    log('Vidsrc: fetching %s' % embed_url)

    try:
        r = sess.get(embed_url, timeout=TIMEOUT)
        if r.status_code != 200:
            log('Vidsrc embed status %s' % r.status_code)
            return _try_resolveurl_fallback(embed_url)
        html = r.text
    except Exception as e:
        log('Vidsrc embed fetch failed: %s' % e)
        return _try_resolveurl_fallback(embed_url)

    servers = _extract_servers(html)
    if not servers:
        return _try_resolveurl_fallback(embed_url)

    all_streams = []
    for i, srv in enumerate(servers[:5]):  # cap to 5 servers per title
        log('Vidsrc: trying server %d/%d (%s)' % (i + 1, len(servers), srv.get('name')))
        if srv['type'] == 'cloudnestra':
            all_streams.extend(_resolve_cloudnestra(srv['url'], sess, embed_url,
                                                   server_name=srv.get('name', 'Cloudnestra')))

    if not all_streams:
        # Try ResolveURL on each individual cloudnestra rcp URL.
        for srv in servers:
            if srv.get('type') != 'cloudnestra':
                continue
            rstreams = _resolveurl_single(srv['url'], embed_url,
                                          srv.get('name', 'Cloudnestra'))
            if rstreams:
                all_streams.extend(rstreams)

    if not all_streams:
        ru = _try_resolveurl_fallback(embed_url)
        if ru:
            all_streams.extend(ru)

    # Dedupe by URL
    deduped = []
    seen = set()
    for s in all_streams:
        u = s.get('url')
        if u and u not in seen:
            seen.add(u)
            deduped.append(s)
    all_streams = deduped

    # Sort: preferred quality order, then by bandwidth desc inside same bucket.
    def _rank(s):
        try:
            qi = QUALITY_ORDER.index(s.get('quality', 'AUTO'))
        except ValueError:
            qi = len(QUALITY_ORDER)
        return (qi, -(s.get('bandwidth') or 0), -(s.get('height') or 0))
    all_streams.sort(key=_rank)
    log('Vidsrc: %d total candidates' % len(all_streams))
    return all_streams


def resolve(media_type, tmdb_id, season=None, episode=None, imdb_id=None):
    """Backwards-compatible single-stream resolver (returns the best candidate)."""
    streams = resolve_all(media_type, tmdb_id, season, episode, imdb_id)
    return streams[0] if streams else None


def _resolveurl_single(url, referer, server_name):
    """Try ResolveURL on a single URL and wrap the result in our stream shape."""
    try:
        import resolveurl  # type: ignore
    except ImportError:
        return []
    try:
        hmf = resolveurl.HostedMediaFile(url=url, include_disabled=False,
                                         include_universal=True)
        if not hmf.valid_url():
            return []
        resolved = hmf.resolve()
        if not resolved:
            return []
        host = re.sub(r'^https?://', '', resolved).split('/')[0]
        is_hls = '.m3u8' in resolved.lower()
        is_mp4 = '.mp4' in resolved.lower()
        proto = 'HLS' if is_hls else ('MP4' if is_mp4 else 'AUTO')
        log('ResolveURL resolved %s -> %s' % (url[:80], resolved[:90]))
        return [{
            'url': resolved,
            'headers': {'User-Agent': UA, 'Referer': referer},
            'label': '[%s] %s via ResolveURL • %s' % (proto, server_name, host),
            'quality': proto, 'proto': proto, 'host': host,
            'server': server_name, 'height': 0, 'bandwidth': 0,
        }]
    except Exception as e:
        log('ResolveURL single failed for %s: %s' % (url[:80], e))
    return []


def _try_resolveurl_fallback(url):
    try:
        import resolveurl  # type: ignore
    except ImportError:
        log('ResolveURL not installed; cannot fallback')
        return []
    try:
        hmf = resolveurl.HostedMediaFile(url=url, include_disabled=False, include_universal=True)
        if not hmf.valid_url():
            log('ResolveURL: URL not valid for any resolver')
            return []
        resolved = hmf.resolve()
        if resolved:
            host = re.sub(r'^https?://', '', resolved).split('/')[0]
            is_hls = '.m3u8' in resolved.lower()
            proto = 'HLS' if is_hls else 'MP4'
            return [{
                'url': resolved, 'headers': {'User-Agent': UA},
                'label': '[%s] ResolveURL • %s' % (proto, host),
                'quality': proto, 'proto': proto, 'host': host,
                'server': 'ResolveURL', 'height': 0, 'bandwidth': 0,
            }]
    except Exception as e:
        log('ResolveURL fallback failed: %s' % e)
    return []


def stream_url_with_headers(stream):
    if not stream:
        return None
    url = stream['url']
    headers = stream.get('headers') or {}
    if not headers:
        return url
    qs = '&'.join('%s=%s' % (k, requests.utils.quote(v, safe='')) for k, v in headers.items())
    return '%s|%s' % (url, qs)
