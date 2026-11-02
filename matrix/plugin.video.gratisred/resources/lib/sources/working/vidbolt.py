import json
import re
from six.moves.urllib_parse import parse_qs, urlencode, urljoin, urlparse

from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


BASE = 'https://vidbolt.xyz'
MOVIE_API = 'https://api.movy.lol'
TV_API = 'https://img.animecurx.tech'
SCRAPER_API = 'https://scraper.vidbolt.xyz'
MOVIE_KEY = '0f461eaa465bb2a7acd037425217f2f209ef540a3171e1ac'
TV_KEY = 'streamrip_secret_2026'


def _playable(url):
    if not url or not str(url).startswith('http'):
        return False
    low = url.lower().split('?', 1)[0]
    return not low.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.vtt', '.srt', '.js', '.css'))


class source:
    def __init__(self):
        self.results = []
        self.domains = ['vidbolt.xyz', 'api.movy.lol', 'scraper.vidbolt.xyz']
        self.base_link = BASE
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': BASE + '/',
            'Origin': BASE,
            'Accept': 'application/json',
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
            return
        return urlencode({'tmdb': tmdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
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
                self._gaiaflix_tv(hostDict, tmdb, data['season'], data['episode'])
                self._scrape(hostDict, 'Quasar', 'tv', tmdb, {
                    'tmdbId': tmdb, 'season': data['season'], 'episode': data['episode']})
            else:
                self._gaiaflix_movie(hostDict, tmdb)
                self._scrape(hostDict, 'Quasar', 'movie', tmdb, {'tmdbId': tmdb})
            return self.results
        except Exception:
            return self.results


    def _candidates(self, payload, base):
        if not isinstance(payload, dict):
            return []
        rows = payload.get('sources')
        rows = rows if isinstance(rows, list) else []
        if not rows and payload.get('m3u8_path'):
            rows = [{'url': payload['m3u8_path'], 'type': 'm3u8'}]
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if re.search(r'\borion\b', str(row.get('name') or ''), re.I):
                continue
            raw = str(row.get('url') or '').strip()
            if not raw:
                continue
            parsed = urlparse(raw)
            if parsed.scheme and parsed.scheme not in ('http', 'https'):
                continue
            link = raw if parsed.scheme else urljoin(base + '/', re.sub(r'^downloads/', '', raw.lstrip('/')))
            if not _playable(link):
                continue
            headers = dict(self.headers)
            extra = row.get('headers')
            if isinstance(extra, dict):
                for key, value in extra.items():
                    if str(key).lower() in ('user-agent', 'referer', 'origin', 'accept') and isinstance(value, str):
                        headers[key] = value
            out.append((link, headers))
        return out


    def _add(self, hostDict, link, headers, label):
        play = link + source_utils.append_headers(headers)
        item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='VidBolt %s' % label)
        if not item.get('url') or item['url'] in [row.get('url') for row in self.results]:
            return
        if scrape_sources.check_host_limit(item['source'], self.results):
            return
        self.results.append(item)


    def _ingest(self, hostDict, payload, base, label):
        for link, headers in self._candidates(payload, base):
            self._add(hostDict, link, headers, label)


    def _gaiaflix_movie(self, hostDict, tmdb):
        endpoint = '%s/api/source/%s?%s' % (MOVIE_API, tmdb, urlencode({'api_key': MOVIE_KEY, 'apikey': MOVIE_KEY}))
        payload = client.request(endpoint, headers=self.headers, timeout='12', output='json')
        self._ingest(hostDict, payload, MOVIE_API, 'Gaiaflix')


    def _gaiaflix_tv(self, hostDict, tmdb, season, episode):
        endpoint = '%s/api/tv/%s/%s/%s?%s' % (
            TV_API, tmdb, season, episode, urlencode({'api_key': TV_KEY, 'apikey': TV_KEY}))
        payload = client.request(endpoint, headers=self.headers, timeout='12', output='json')
        self._ingest(hostDict, payload, TV_API, 'Gaiaflix')


    def _scrape(self, hostDict, name, media, tmdb, params):
        path = '/scrape/%s/%s/tmdb%s?%s' % (name, media, tmdb, urlencode(params))
        endpoint = SCRAPER_API + path
        payload = client.request(endpoint, headers=self.headers, timeout='12', output='json')
        self._ingest(hostDict, payload, SCRAPER_API, name)


    def resolve(self, url):
        return url
