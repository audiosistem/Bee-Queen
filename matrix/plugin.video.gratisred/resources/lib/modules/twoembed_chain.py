"""2Embed movie player: embed -> streamsrcs swish -> 2vcdn HLS."""

import re
from six.moves.urllib_parse import urljoin, urlparse

from resources.lib.modules import client
from resources.lib.modules import client_utils

try:
    from html import unescape as html_unescape
except ImportError:
    from six.moves.html_parser import HTMLParser
    html_unescape = HTMLParser().unescape


BASE = 'https://www.2embed.cc'
SWISH_HOST = 'streamsrcs.2embed.cc'
CDN_HOST = '2vcdn.skin'
REFERER = 'https://watch.cinewave.qzz.io/'


def _origin(url):
    parsed = urlparse(url)
    return '%s://%s' % (parsed.scheme, parsed.netloc) if parsed.scheme and parsed.netloc else ''


def _page(url, referer):
    return client.request(url, headers={'User-Agent': client.UserAgent, 'Referer': referer}, timeout='12') or ''


def _frames(html):
    found = []
    for match in re.finditer(r'<iframe[^>]+>', html or '', re.I):
        tag = match.group(0)
        src = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', tag, re.I)
        if src:
            found.append(html_unescape(src.group(1)))
    return found


def normalize(url):
    if not url:
        return ''
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower().replace('www.', '')
    if host not in ('2embed.cc', '2embed.skin', '2embed.me'):
        return url
    path = parsed.path.rstrip('/')
    query = parsed.query or ''
    if 'id=' in query:
        ident = re.search(r'(?:^|&)id=([^&]+)', query)
        if ident:
            value = ident.group(1)
            if value.startswith('tt') or '/tv' in path:
                return url
            return '%s://%s/embed/movie/%s' % (parsed.scheme or 'https', parsed.hostname, value)
    match = re.fullmatch(r'/embed/(?:movie/)?(\d+)', path)
    if match:
        return '%s://%s/embed/movie/%s' % (parsed.scheme or 'https', parsed.hostname or 'www.2embed.cc', match.group(1))
    return url


def embed_url(tmdb):
    ident = str(tmdb or '').strip()
    if not ident.isdigit() or ident == '0':
        return ''
    return BASE + '/embed/movie/' + ident


def _player_url(html, page):
    for raw in _frames(html):
        target = urljoin(page, raw)
        parsed = urlparse(target)
        if parsed.hostname == SWISH_HOST and parsed.path == '/swish':
            return target
    return ''


def _host_url(html):
    for raw in _frames(html):
        if re.fullmatch(r'[a-zA-Z0-9]{12}', raw or ''):
            return 'https://%s/e/%s' % (CDN_HOST, raw)
        target = urljoin('https://%s/' % CDN_HOST, raw)
        parsed = urlparse(target)
        if parsed.hostname == CDN_HOST and re.fullmatch(r'/e/[a-zA-Z0-9]{12}/?', parsed.path):
            return target
    return ''


def _media(html):
    texts = [html or '']
    try:
        unpacked = client_utils.unpacked(html) or client_utils.unpacked2(html)
        if unpacked:
            texts.append(unpacked)
    except Exception:
        pass
    seen = []
    for text in texts:
        text = text.replace('\\/', '/').replace('\\u002F', '/')
        for raw in re.findall(r'https?://[^\s"\'<>\\]+', text):
            url = html_unescape(raw).split('\\')[0]
            path = urlparse(url).path.lower()
            if path.endswith(('.m3u8', '.txt')) and url not in seen:
                seen.append(url)
    return seen


def resolve_embed(url):
    """Return (stream urls, headers) for a 2embed.cc movie embed."""
    try:
        url = normalize(url)
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        if not host.endswith('2embed.cc') and not host.endswith('2embed.skin'):
            return [], None
        if not re.fullmatch(r'/embed/movie/\d+', parsed.path.rstrip('/')):
            return [], None
        page = _page(url, REFERER)
        wrapper = _player_url(page, url)
        if not wrapper:
            return [], None
        host_page = _page(wrapper, url)
        video = _host_url(host_page)
        if not video:
            return [], None
        headers = {
            'User-Agent': client.UserAgent,
            'Referer': 'https://%s/' % CDN_HOST,
            'Origin': 'https://%s' % CDN_HOST,
        }
        body = _page(video, wrapper)
        urls = _media(body)[:4]
        return urls, headers
    except Exception:
        return [], None
