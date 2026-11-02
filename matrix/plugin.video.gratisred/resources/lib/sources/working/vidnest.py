import base64
import hashlib
import json
import os
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules.aesgcm import aes_gcm_decrypt
from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


API = 'https://new.vidnest.fun'
SITE = 'https://vidnest.fun'
# Current vidnest.fun player (22efd2ae7da60c3f.js). Request query _n, then AES-GCM.
_SECRET = 'F9k2mR8vL4qP7wY1zN0fG3bS6tH5jC8d_x4R7vN2mP9qL1'
_ALPH = 'RB0fpH8ZEyVLkv7c2i6MAJ5u3IKFDxlS1NTsnGaqmXYdUrtzjwObCgQP94hoeW+/='
_TABLE = dict((c, i) for i, c in enumerate(_ALPH))
# slug, label, response shape. Paths match the current vidnest.fun player.
# HollyMovieHD (sigma) is already its own scraper. Delta repeats AllMovies.
_PROVIDERS = (
    ('yflix', 'Catflix', 'url_only'),
    ('rogflix', 'Filxer', 'url_only'),
    ('vidzee', 'Gama', 'streams_lang'),
    ('videasy', 'Alfa', 'url_only'),
    ('klikxxi', 'Ophim', 'sources'),
    ('vidxyz', 'Beta', 'streams_lang'),
    ('vidrock', 'Prime', 'sources'),
    ('allmovies', 'AllMovies', 'streams_lang'),
    ('vidlink', 'VidLink', 'vidlink'),
)


def _b64decode(data):
    out = bytearray()
    for i in range(0, len(data), 4):
        block = data[i:i + 4]
        if len(block) < 4:
            block += '=' * (4 - len(block))
        vals = [_TABLE.get(c, 64) for c in block]
        out.append(((vals[0] << 2) & 0xFF) | ((vals[1] >> 4) & 0xFF))
        if vals[2] != 64:
            out.append((((vals[1] & 15) << 4) & 0xFF) | ((vals[2] >> 2) & 0xFF))
        if vals[3] != 64:
            out.append(((vals[2] << 6) & 0xFF) | (vals[3] & 0xFF))
    return out.decode('utf-8', errors='replace')


def _nonce():
    raw = os.urandom(16)
    return base64.b64encode(raw).decode('ascii').replace('+', '-').replace('/', '_').rstrip('=')


def _b64url(data):
    encoded = (data or '').replace('-', '+').replace('_', '/')
    encoded += '=' * ((4 - len(encoded) % 4) % 4)
    return base64.b64decode(encoded)


def _unwrap_v2(env):
    blob = env.get('d') or ''
    token = env.get('n') or ''
    if not blob:
        return None
    key = hashlib.sha256(('%s|%s' % (token, _SECRET)).encode('utf-8')).digest()
    raw = _b64url(blob)
    if len(raw) < 28:
        return None
    plain = aes_gcm_decrypt(key, raw[:12], raw[12:])
    if isinstance(plain, bytes):
        plain = plain.decode('utf-8')
    return json.loads(plain)


def _unwrap(env):
    if not isinstance(env, dict):
        return env
    if env.get('d'):
        try:
            return _unwrap_v2(env)
        except Exception:
            pass
    if not env.get('encrypted'):
        return env
    plain = _b64decode(env.get('data') or '')
    try:
        return json.loads(plain)
    except Exception:
        return {}


def _playable(url):
    if not url or not str(url).startswith('http'):
        return False
    low = url.lower().split('?', 1)[0]
    return not low.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.vtt', '.srt', '.js', '.css'))


class source:
    def __init__(self):
        self.results = []
        self.domains = ['vidnest.fun', 'new.vidnest.fun']
        self.base_link = SITE
        self.headers = {
            'User-Agent': client.UserAgent,
            'Origin': SITE,
            'Referer': SITE + '/',
            'Accept': 'application/json,*/*',
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not str(tmdb or '').isdigit():
            return
        return urlencode({'tmdb': tmdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not str(tmdb or '').isdigit():
            return
        return urlencode({'tmdb': tmdb, 'media': 'tv'})


    def episode(self, url, imdb, tmdb, tvdb, title, premiered, season, episode):
        if not url:
            return
        url = parse_qs(url)
        url = dict([(i, url[i][0]) if url[i] else (i, '') for i in url])
        url['season'], url['episode'] = season, episode
        return urlencode(url)


    def sources(self, url, hostDict):
        try:
            if not url:
                return self.results
            data = parse_qs(url)
            data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])
            tmdb = data.get('tmdb')
            if not tmdb:
                return self.results
            if data.get('media') == 'tv':
                if not data.get('season') or not data.get('episode'):
                    return self.results
                tail = 'tv/%s/%s/%s' % (tmdb, data['season'], data['episode'])
            else:
                tail = 'movie/%s' % tmdb
            for slug, label, kind in _PROVIDERS:
                self._provider(hostDict, '%s/%s/%s?_n=%s' % (API, slug, tail, _nonce()), label, kind)
            return self.results
        except Exception:
            return self.results


    def _headers_for(self, extra):
        headers = dict(self.headers)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if isinstance(key, str) and isinstance(value, (str, int, float)):
                    headers[key] = str(value)
        return headers


    def _add_link(self, hostDict, link, label, extra_headers=None):
        if not _playable(link):
            return
        play = link + source_utils.append_headers(self._headers_for(extra_headers))
        item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Vidnest %s' % label)
        if item.get('url') and not scrape_sources.check_host_limit(item['source'], self.results):
            self.results.append(item)


    def _provider(self, hostDict, url, label, kind):
        try:
            raw = client.request(url, headers=self.headers, timeout='12')
            if not raw:
                return
            data = _unwrap(json.loads(raw))
            if not isinstance(data, dict):
                return
            if kind in ('sources', 'sources_named'):
                for row in data.get('sources') or []:
                    if isinstance(row, dict):
                        self._add_link(hostDict, row.get('url'), label, row.get('headers'))
            elif kind == 'streams_lang':
                for row in data.get('streams') or []:
                    if isinstance(row, dict):
                        self._add_link(hostDict, row.get('url'), label, row.get('headers'))
            elif kind == 'url_only':
                self._add_link(hostDict, data.get('url'), label, data.get('headers'))
            elif kind == 'vidlink':
                stream = (data.get('data') or {}).get('stream') or {}
                if isinstance(stream, dict):
                    self._add_link(hostDict, stream.get('playlist'), label, stream.get('headers'))
        except Exception:
            return


    def resolve(self, url):
        return url
