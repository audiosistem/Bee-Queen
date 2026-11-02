"""Vixsrc.to playlist API (HydraHD / standalone)."""

import re
from six.moves.urllib_parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from resources.lib.modules import client


SITE = 'https://vixsrc.to'


def _headers(referer):
    parsed = urlparse(referer or SITE)
    origin = '%s://%s' % (parsed.scheme or 'https', parsed.netloc or 'vixsrc.to')
    return {
        'User-Agent': client.UserAgent,
        'Referer': referer or SITE + '/',
        'Origin': origin,
        'Accept': 'application/json,text/html,*/*',
    }


def embed_url(tmdb, media='movie', season=None, episode=None):
    ident = str(tmdb or '').strip()
    if not ident.isdigit() or ident == '0':
        return ''
    if media == 'tv':
        if not season or not episode:
            return ''
        return '%s/tv/%s/%s/%s' % (SITE, ident, season, episode)
    return '%s/movie/%s' % (SITE, ident)


def resolve_url(url):
    """Follow /api{path} -> embed -> window.masterPlaylist. Returns (urls, headers)."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        if host != 'vixsrc.to':
            return [], None
        route = parsed.path.rstrip('/')
        if not re.fullmatch(r'/(?:movie/\d+|tv/\d+/\d+/\d+)', route):
            return [], None
        api = SITE + '/api' + route + '?lang=en'
        payload = client.request(api, headers=_headers(url), timeout='12', output='json')
        src = payload.get('src') if isinstance(payload, dict) else None
        if not isinstance(src, str):
            return [], None
        embed = urljoin(SITE + '/', src)
        if urlparse(embed).hostname != 'vixsrc.to' or not urlparse(embed).path.startswith('/embed/'):
            return [], None
        html = client.request(embed, headers=_headers(SITE + '/'), timeout='12') or ''
        block = re.search(r'window\.masterPlaylist\s*=\s*\{(.*?)\n\s*\}\s*(?:;|(?=window\.))', html, re.S)
        if not block:
            return [], None
        playlist = re.search(r"\burl\s*:\s*['\"]([^'\"]+)['\"]", block.group(1))
        params = dict(re.findall(r"['\"](token|expires|asn)['\"]\s*:\s*['\"]([^'\"]*)['\"]", block.group(1)))
        if not playlist or not params.get('token') or not params.get('expires'):
            return [], None
        target = urlparse(playlist.group(1))
        if target.scheme != 'https' or target.hostname != 'vixsrc.to' or not target.path.startswith('/playlist/'):
            return [], None
        query = dict(parse_qsl(target.query))
        query.update(params)
        query['h'] = '1'
        query['lang'] = 'en'
        play = urlunparse(target._replace(query=urlencode(query)))
        headers = {
            'User-Agent': client.UserAgent,
            'Referer': SITE + '/',
            'Origin': SITE,
        }
        return [play], headers
    except Exception:
        return [], None


def resolve_ident(tmdb, media='movie', season=None, episode=None):
    url = embed_url(tmdb, media, season, episode)
    if not url:
        return [], None
    return resolve_url(url)
