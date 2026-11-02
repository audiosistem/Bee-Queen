"""Resolve Dulo/HydraHD player embeds to direct stream URLs."""

import json
import re
from six.moves.urllib_parse import quote, urlencode, urljoin, urlparse

from resources.lib.modules import client
from resources.lib.modules import twoembed_chain
from resources.lib.modules import vixsrc_chain

try:
    from html import unescape as html_unescape
except ImportError:
    from six.moves.html_parser import HTMLParser
    html_unescape = HTMLParser().unescape


CRYPTO = 'https://enc-dec.app/api/'
SKIP_HOSTS = frozenset((
    'cdn.toffee.bz', 'player.videasy.net', 'player.videasy.to', 'vidsrc-embed.ru',
))
HOSTS = {
    'vidy.st': 'vidy', 'www.vidy.st': 'vidy',
    'vidfast.pro': 'vidfast', 'vidfast.vc': 'vidfast',
    'moviesapi.to': 'moviesapi',
    'player.vidzee.wtf': 'vidzee',
    'vidcore.net': 'vidcore', 'vidcore.io': 'vidcore',
    'vidlink.pro': 'vidlink',
    'player.vidlove.cc': 'vidlove',
    'vixsrc.to': 'vixsrc',
    '2embed.cc': 'twoembed', 'www.2embed.cc': 'twoembed',
}


def _host(url):
    host = (urlparse(url).hostname or '').lower()
    if host.startswith('www.') and host not in HOSTS:
        return host[4:]
    return host


def _headers(page):
    parsed = urlparse(page)
    origin = '%s://%s' % (parsed.scheme, parsed.netloc) if parsed.scheme and parsed.netloc else ''
    return {
        'User-Agent': client.UserAgent,
        'Referer': page if page.endswith('/') or '?' in page or '/embed' in page or '/movie' in page or '/tv' in page else page + '/',
        'Origin': origin,
        'Accept': 'application/json,text/html,*/*',
    }


def _get(url, headers=None, timeout=12, json_out=False, post=None):
    kwargs = {'headers': headers or {}, 'timeout': str(int(timeout))}
    if json_out:
        kwargs['output'] = 'json'
    if post is not None:
        kwargs['post'] = post
    return client.request(url, **kwargs)


def _crypto(operation, text, extra=None):
    headers = {
        'User-Agent': client.UserAgent,
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if operation.startswith('enc-'):
        data = _get(CRYPTO + operation + '?' + urlencode({'text': text}), headers=headers, json_out=True)
    else:
        payload = {'text': text}
        if extra:
            payload.update(extra)
        data = _get(CRYPTO + operation, headers=headers, json_out=True, post=json.dumps(payload))
    if not isinstance(data, dict) or data.get('status') != 200:
        return None
    result = data.get('result')
    if isinstance(result, str) and result[:1] in ('{', '['):
        try:
            result = json.loads(result)
        except Exception:
            pass
    return result


def _http(url):
    if not isinstance(url, str) or not url.startswith('http'):
        return False
    parsed = urlparse(url)
    return bool(parsed.hostname) and parsed.scheme in ('http', 'https')


def _rows(data, headers):
    out = []
    if isinstance(data, str) and _http(data):
        data = {'url': data}
    if isinstance(data, dict):
        rows = data.get('sources') or data.get('streams') or [data]
    else:
        rows = data
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, str):
            row = {'url': row}
        if not isinstance(row, dict):
            continue
        url = row.get('url') or row.get('file') or row.get('playlist')
        if not _http(url):
            continue
        merged = dict(headers)
        supplied = row.get('headers') or (data.get('headers') if isinstance(data, dict) else {})
        if isinstance(supplied, dict):
            for key, value in supplied.items():
                if isinstance(key, str) and isinstance(value, (str, int)):
                    merged[key] = str(value)
        out.append((url, merged))
    return out


def _identity(url):
    path = urlparse(url).path.rstrip('/')
    match = re.search(r'/(movie|tv)/(\d+)(?:/(\d+)/(\d+))?$', path)
    if not match:
        match = re.fullmatch(r'/(tv)/(\d+)-(\d+)-(\d+)', path)
    if not match:
        match = re.search(r'/embed/(movie|tv)/(\d+)(?:/(\d+)/(\d+))?', path)
    if not match:
        match = re.fullmatch(r'/embed/movie/(\d+)', path)
        if match:
            return 'movie', match.group(1), '', ''
        match = re.fullmatch(r'/embed/(\d+)', path)
        if match:
            return 'movie', match.group(1), '', ''
        return None
    media = match.group(1)
    if media == 'tv' and not match.group(3):
        return None
    return media, match.group(2), match.group(3) or '', match.group(4) or ''


def _moviesapi(url):
    page = _get(url, headers=_headers(url), timeout=15) or ''
    parsed = urlparse(url)
    movie = re.fullmatch(r'/movie/(\d+)', parsed.path)
    tv = re.fullmatch(r'/tv/(\d+)[/-](\d+)[/-](\d+)', parsed.path.rstrip('/'))
    if not movie and not tv:
        return []
    route = 'movie/' + movie.group(1) if movie else 'tv/' + '/'.join(tv.groups())
    for src in re.findall(r'''<script\b[^>]*\bsrc=["']([^"']+)''', page, re.I):
        script_url = urljoin(url, html_unescape(src))
        if urlparse(script_url).hostname != parsed.hostname or '/assets/index-' not in script_url:
            continue
        script = _get(script_url, headers=dict(_headers(url), Referer=url), timeout=12) or ''
        variable = re.search(r'''["']x-player-key["']\s*:\s*([A-Za-z_$][\w$]*)''', script)
        if not variable or '/api/vidora' not in script:
            continue
        key = re.search(r'\b' + re.escape(variable.group(1)) + r'''\s*=\s*[`"']([A-Za-z0-9]+)[`"']''', script)
        if not key:
            continue
        endpoint = 'https://moviesapi.to/api/vidora/v1/' + route
        headers = dict(_headers(url), Referer=url, **{
            'x-player-key': key.group(1),
            'Cache-Control': 'no-cache',
            'Accept': 'application/json',
        })
        data = _get(endpoint, headers=headers, timeout=12, json_out=True)
        if not isinstance(data, dict) or not data.get('result'):
            return []
        rows = data.get('sources')
        extra = data.get('headers') if isinstance(data.get('headers'), dict) else {}
        return _rows({'sources': rows, 'headers': extra}, _headers(url))
    return []


def _vidy(url, meta):
    ident = _identity(url)
    if not ident:
        return []
    headers = _headers(url)
    title = (meta or {}).get('title') or ''
    params = {
        'title': quote(title, safe='') if title else '',
        'mediaType': ident[0],
        'tmdbId': ident[1],
        'imdbId': (meta or {}).get('imdb') or '',
        'year': (meta or {}).get('year') or '',
    }
    if ident[0] == 'tv':
        params.update(seasonId=ident[2], episodeId=ident[3])
    out = []
    seed_json = _get('https://api.wecollege.net/seed?' + urlencode({'mediaId': ident[1]}),
                     headers=headers, timeout=10, json_out=True)
    seed = seed_json.get('seed') if isinstance(seed_json, dict) else None
    for provider in ('miami', 'boise', 'denver', 'seattle', 'phoenix', 'atlanta'):
        query = dict(params)
        if seed is not None:
            query['enc'] = '2'
            query['seed'] = seed
        endpoint = 'https://api.wecollege.net/%s/sources?%s' % (provider, urlencode(query))
        data = _get(endpoint, headers=headers, timeout=10, json_out=True)
        if isinstance(data, dict):
            out.extend(_rows(data, headers))
        if len(out) >= 4:
            break
    return out


def _vidzee(url):
    ident = _identity(url)
    if not ident:
        return []
    route = '/'.join(x for x in ident if x)
    headers = _headers(url)
    out = []
    for provider in ('dcloud', 'doppler', 'tik', 'ipcloud', 'v6:English'):
        data = _get('https://core.vidzee.wtf/streams/' + route + '?' + urlencode({'s': provider}),
                    headers=headers, timeout=10, json_out=True)
        out.extend(_rows(data, headers))
        if len(out) >= 6:
            break
    return out


def _vidlink(url):
    ident = _identity(url)
    if not ident:
        return []
    token = _crypto('enc-vidlink', ident[1])
    if not isinstance(token, str) or not token:
        return []
    route = ident[0] + '/' + quote(token, safe='')
    if ident[0] == 'tv':
        route += '/' + ident[2] + '/' + ident[3]
    headers = dict(_headers(url), Referer='https://vidlink.pro/')
    data = _get('https://vidlink.pro/api/b/' + route + '?multiLang=0', headers=headers, timeout=12, json_out=True)
    if isinstance(data, dict) and isinstance(data.get('stream'), dict):
        data = data['stream']
    out = []
    if isinstance(data, dict) and data.get('playlist'):
        row = {'url': data['playlist'], 'headers': data.get('playlistHeaders') or {}}
        out.extend(_rows(row, headers))
    if isinstance(data, dict) and isinstance(data.get('qualities'), dict):
        for key in sorted(data['qualities'], key=lambda k: int(k) if str(k).isdigit() else 0, reverse=True):
            row = data['qualities'][key]
            if isinstance(row, dict):
                out.extend(_rows(row, headers))
    return out


def _catalog(url, provider):
    page = _get(url, headers=dict(_headers(url), Referer='https://dulo.vg/'), timeout=15) or ''
    match = re.search(r'\\"(?:en|token)\\":\\"([^\\"]+)\\"', page)
    if not match:
        match = re.search(r'"(?:en|token)"\s*:\s*"([^"]+)"', page)
    if not match:
        return []
    parts = _crypto('enc-' + provider, match.group(1))
    if not isinstance(parts, dict):
        return []
    parsed = urlparse(url)
    root = '%s://%s' % (parsed.scheme, parsed.netloc)
    allowed = ('vidcore.io', 'vidcore.net') if provider == 'vidcore' else ('vidfast.vc', 'vidfast.pro')
    for field in ('servers', 'stream'):
        if not _http(parts.get(field)) or urlparse(parts[field]).hostname not in allowed:
            return []
    headers = dict(_headers(url), Referer=root + '/', **{
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-Token': str(parts.get('token') or ''),
        'Content-Type': 'application/json',
    })
    encrypted = _get(parts['servers'], headers=headers, timeout=12, post=b'')
    rows = _crypto('dec-' + provider, encrypted or '')
    if not isinstance(rows, list):
        return []
    out = []
    play_headers = dict(_headers(url), Referer=root + '/')
    for row in rows[:4]:
        if not isinstance(row, dict) or not isinstance(row.get('data'), str):
            continue
        blob = _get(parts['stream'].rstrip('/') + '/' + quote(row['data'], safe=''),
                    headers=headers, timeout=12, post=b'')
        result = _crypto('dec-' + provider, blob or '')
        out.extend(_rows(result, play_headers))
    return out


def _vidlove(url):
    ident = _identity(url)
    if not ident:
        return []
    headers = {
        'User-Agent': client.UserAgent,
        'Referer': 'https://player.vidlove.cc/',
        'Accept': 'application/json,*/*',
    }
    if ident[0] == 'tv':
        api = 'https://api.vidlove.cc/tv?id=%s&season=%s&episode=%s&mode=json' % (ident[1], ident[2], ident[3])
    else:
        api = 'https://api.vidlove.cc/movie?id=%s&mode=json' % ident[1]
    payload = _get(api, headers=headers, timeout=12, json_out=True)
    source = payload.get('source') if isinstance(payload, dict) else None
    link = source.get('url') if isinstance(source, dict) else ''
    if _http(link):
        return [(link, headers)]
    return []


def resolve_embed(url, meta=None):
    """Return [(stream_url, headers), ...] for a Dulo/Hydra player page."""
    try:
        if not _http(url):
            return []
        url = html_unescape(url)
        host = _host(url)
        if host in SKIP_HOSTS or host.replace('www.', '') in SKIP_HOSTS:
            return []
        kind = HOSTS.get(host) or HOSTS.get(host.replace('www.', ''))
        if kind == 'vixsrc':
            urls, headers = vixsrc_chain.resolve_url(url.split('?')[0])
            return [(u, headers or {}) for u in urls]
        if kind == 'twoembed':
            urls, headers = twoembed_chain.resolve_embed(url)
            return [(u, headers or {}) for u in urls]
        if kind == 'vidlove':
            return _vidlove(url)
        if kind == 'moviesapi':
            return _moviesapi(url)
        if kind == 'vidy':
            return _vidy(url, meta)
        if kind == 'vidzee':
            return _vidzee(url)
        if kind == 'vidlink':
            return _vidlink(url)
        if kind in ('vidfast', 'vidcore'):
            return _catalog(url, kind)
        return []
    except Exception:
        return []
