import base64
import hashlib
import json
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


class source:
    def __init__(self):
        self.results = []
        self.domains = ['cinetaro.to', 'cinextream.cc']
        self.base_link = 'https://cinetaro.to'
        self.api_link = 'https://cinextream.cc/api/proxy'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': 'https://cinextream.cc/',
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not tmdb or str(tmdb) in ('0', 'None'):
            return
        return urlencode({'tmdb': tmdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not tmdb or str(tmdb) in ('0', 'None'):
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
            params = {'server': 'Nest', 'tmdb': str(tmdb), 'type': 'movie' if data.get('media') != 'tv' else 'series'}
            if data.get('media') == 'tv':
                if not data.get('season') or not data.get('episode'):
                    return self.results
                params['season'] = data['season']
                params['episode'] = data['episode']
            api = self.api_link + '?' + urlencode(params)
            raw = client.request(api, headers=self.headers, timeout='15')
            if not raw:
                return self.results
            payload = json.loads(raw)
            payload = self._decode(payload, tmdb)
            for link, extra in self._urls(payload.get('data') if isinstance(payload, dict) else None):
                if not self._playable(link):
                    continue
                headers = dict(self.headers)
                if isinstance(extra, dict):
                    for key, value in extra.items():
                        if isinstance(key, str) and isinstance(value, str):
                            headers[key] = value
                play = link + source_utils.append_headers(headers)
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Cinetaro')
                if not item.get('url'):
                    continue
                if scrape_sources.check_host_limit(item['source'], self.results):
                    continue
                self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def _decode(self, data, tmdb):
        if not isinstance(data, dict) or 'enc' not in data:
            return data
        key = hashlib.sha256((str(tmdb) + 'c1n3t4r-0bf5c4t10n-s4lt-v1-2024-09').encode('utf-8')).digest()
        encoded = base64.b64decode(data['enc'])
        decoded = bytes(value ^ key[i % 32] ^ ((i * 7 + 13) & 255) for i, value in enumerate(encoded))
        return json.loads(decoded.decode('utf-8'))


    def _urls(self, value, headers=None):
        if isinstance(value, str):
            if value.startswith(('http://', 'https://')):
                yield value, dict(headers or {})
        elif isinstance(value, dict):
            own = value.get('headers') if isinstance(value.get('headers'), dict) else headers
            for key, item in value.items():
                if key == 'headers':
                    continue
                for found in self._urls(item, own):
                    yield found
        elif isinstance(value, list):
            for item in value:
                for found in self._urls(item, headers):
                    yield found


    def _playable(self, url):
        low = url.lower()
        if any(ext in low for ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.vtt', '.srt')):
            return False
        return True


    def resolve(self, url):
        return url
