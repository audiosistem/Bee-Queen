"""VidSrc 2026 player chain: vsembed -> vs_src.php -> stellar player -> stream_urls."""

import json
import re
from six.moves.urllib_parse import quote, urljoin, urlparse

from resources.lib.modules.wasm_i32 import decrypt_b64

try:
    from html import unescape as html_unescape
except ImportError:
    from six.moves.html_parser import HTMLParser
    html_unescape = HTMLParser().unescape


HOSTS = (
    'vsembed.ru', 'vsembed.su', 'vidsrc.to',
)
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0'


def _ua():
    try:
        from resources.lib.modules import client
        return client.UserAgent
    except Exception:
        return _UA


def _client_get(url, headers=None, timeout=15, as_bytes=False, json_out=False):
    from resources.lib.modules import client
    kwargs = {'headers': headers or {}, 'timeout': str(int(timeout))}
    if as_bytes:
        kwargs['as_bytes'] = True
    if json_out:
        kwargs['output'] = 'json'
    return client.request(url, **kwargs)


def _origin(url):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return '%s://%s' % (parsed.scheme, parsed.netloc)


def _js_object(html, name):
    if not html:
        return None
    match = re.search(r'window\.%s\s*=\s*\{' % re.escape(name), html)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    in_str = None
    escape = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except Exception:
                    return None
    return None


def _headers(referer, origin=None):
    origin = origin or _origin(referer)
    return {
        'User-Agent': _ua(),
        'Referer': referer if referer.endswith('/') or '?' in referer or '/embed' in referer else referer + '/',
        'Origin': origin,
        'Accept': 'application/json,text/html,*/*',
    }


def _play_headers(player):
    origin = _origin(player)
    return {
        'User-Agent': _ua(),
        'Referer': player,
        'Origin': origin,
    }


def _vs_src_from_embed(embed, html):
    match = re.search(r'data-api=["\']([^"\']+)["\']', html or '', re.I)
    if match:
        return urljoin(embed, html_unescape(match.group(1)))
    parsed = urlparse(embed)
    parts = [p for p in parsed.path.split('/') if p]
    # /embed/movie/278  or  /embed/tv/1396/1/1
    if len(parts) >= 3 and parts[0] == 'embed':
        origin = _origin(embed)
        if parts[1] == 'tv' and len(parts) >= 5:
            return '%s/vs_src.php?type=tv&id=%s&season=%s&episode=%s' % (
                origin, parts[2], parts[3], parts[4])
        return '%s/vs_src.php?type=movie&id=%s' % (origin, parts[2])
    return ''


def _lines_from_payload(payload, get):
    if not isinstance(payload, dict):
        return []
    inner = payload.get('data') if isinstance(payload.get('data'), dict) else payload
    su = inner.get('stream_urls') if isinstance(inner, dict) else None
    if isinstance(su, list):
        return [u for u in su if u]
    if not isinstance(su, str) or not su:
        return []
    if su.startswith('http'):
        return [ln for ln in su.split('\n') if ln]
    vs = payload.get('vs') or {}
    wasm_blob = b''
    wasm_url = vs.get('wasm_url')
    if wasm_url:
        wasm_blob = get(wasm_url, headers={'User-Agent': _ua(), 'Accept': '*/*'}, timeout=15, as_bytes=True) or b''
    elif vs.get('wasm'):
        import base64
        try:
            wasm_blob = base64.b64decode(vs.get('wasm'))
        except Exception:
            wasm_blob = b''
    if not wasm_blob:
        return []
    text = decrypt_b64(wasm_blob, su)
    return [ln.strip() for ln in text.split('\n') if ln.strip()]


def _with_cdn_tokens(urls, get):
    """Some CDNs mint a short IP-bound token at /generate.php."""
    stamped = []
    for target in urls:
        url = target
        try:
            origin = _origin(target)
            if origin:
                raw = get(origin + '/generate.php', headers={
                    'User-Agent': _ua(),
                    'Referer': target,
                    'Origin': origin,
                    'Accept': '*/*',
                }, timeout=8)
                token = (raw or '').strip()
                if token.startswith('{'):
                    value = json.loads(token)
                    token = value.get('token') or value.get('data') or ''
                if token and 8 <= len(token) < 2048 and '<' not in token and '\n' not in token:
                    if '__TOKEN__' in url:
                        url = url.replace('__TOKEN__', quote(token, safe=''))
                    elif 'token=' not in url:
                        url = url + ('&' if '?' in url else '?') + 'token=' + quote(token, safe='')
        except Exception:
            url = target
        stamped.append(url)
    return stamped


def resolve_embed(embed, get=None):
    """Follow the vsembed player chain. Returns (urls, headers)."""
    get = get or _client_get
    try:
        if not embed or not embed.startswith('http'):
            return [], None
        page_headers = _headers(embed)
        html = get(embed, headers=page_headers, timeout=12) or ''
        vs_src = _vs_src_from_embed(embed, html)
        if not vs_src:
            return [], None
        src_headers = _headers(embed)
        src_headers['Accept'] = 'application/json'
        src_json = get(vs_src, headers=src_headers, timeout=12, json_out=True)
        if isinstance(src_json, str):
            try:
                src_json = json.loads(src_json)
            except Exception:
                src_json = None
        src = (src_json or {}).get('src') if isinstance(src_json, dict) else None
        if not src:
            return [], None
        land_headers = _headers(embed, _origin(src))
        land_headers['Referer'] = embed
        landing = get(src, headers=land_headers, timeout=15) or ''
        cfg = _js_object(landing, 'CFG') or {}
        player = cfg.get('playerUrl') or ''
        if player.startswith('/'):
            player = _origin(src) + player
        if not player.startswith('http'):
            return [], None
        play_headers = _headers(src, _origin(player))
        play_headers['Referer'] = src
        player_html = get(player, headers=play_headers, timeout=20) or ''
        pcfg = _js_object(player_html, 'CONFIG') or {}
        api = pcfg.get('api') or ''
        if not api:
            base = pcfg.get('streamBase') or ''
            season = pcfg.get('season')
            episode = pcfg.get('episode')
            if base and season not in (None, '') and episode not in (None, ''):
                api = '%s&season=%s&episode=%s&stream_urls' % (base, season, episode)
        token = pcfg.get('apiToken') or ''
        if not api:
            return [], None
        if token:
            api = api + ('&' if '?' in api else '?') + 'api_token=' + quote(token, safe='')
        api_headers = {
            'User-Agent': _ua(),
            'Accept': 'application/json',
            'Referer': player,
            'Origin': _origin(player),
        }
        payload = get(api, headers=api_headers, timeout=15, json_out=True)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = None
        urls = _lines_from_payload(payload or {}, get)
        urls = [u for u in urls if isinstance(u, str) and u.startswith('http')]
        urls = _with_cdn_tokens(urls, get)
        if not urls:
            return [], None
        return urls, _play_headers(player)
    except Exception:
        return [], None


def resolve_ident(media, ident, season=None, episode=None, get=None, hosts=HOSTS):
    get = get or _client_get
    if not ident:
        return [], None
    for host in hosts:
        if media == 'tv':
            if not season or not episode:
                return [], None
            embed = 'https://%s/embed/tv/%s/%s/%s' % (host, ident, season, episode)
        else:
            embed = 'https://%s/embed/movie/%s' % (host, ident)
        urls, headers = resolve_embed(embed, get=get)
        if urls:
            return urls, headers
    return [], None
