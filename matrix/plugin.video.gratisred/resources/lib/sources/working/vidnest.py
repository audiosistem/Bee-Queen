import json
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


API = 'https://new.vidnest.fun'
SITE = 'https://vidnest.fun'
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


def _unwrap(env):
    if not isinstance(env, dict) or not env.get('encrypted'):
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
                self._provider(hostDict, '%s/%s/%s' % (API, slug, tail), label, kind)
            return self.results
        except Exception:
            return self.results


    def _provider(self, hostDict, url, label, kind):
        try:
            raw = client.request(url, headers=self.headers, timeout='12')
            if not raw:
                return
            data = _unwrap(json.loads(raw))
            if not isinstance(data, dict):
                return
            links = []
            if kind in ('sources', 'sources_named'):
                for row in data.get('sources') or []:
                    link = row.get('url') if isinstance(row, dict) else ''
                    if _playable(link):
                        links.append(link)
            elif kind == 'streams_lang':
                for row in data.get('streams') or []:
                    link = row.get('url') if isinstance(row, dict) else ''
                    if _playable(link):
                        links.append(link)
            elif kind == 'url_only':
                link = data.get('url')
                if _playable(link):
                    links.append(link)
            elif kind == 'vidlink':
                stream = (data.get('data') or {}).get('stream') or {}
                link = stream.get('playlist') if isinstance(stream, dict) else ''
                if _playable(link):
                    links.append(link)
            for link in links:
                play = link + source_utils.append_headers(self.headers)
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Vidnest %s' % label)
                if item.get('url') and not scrape_sources.check_host_limit(item['source'], self.results):
                    self.results.append(item)
        except Exception:
            return


    def resolve(self, url):
        return url
