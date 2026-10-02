import base64
import json
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules.aesgcm import aes_gcm_decrypt
from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


_KEY = bytes.fromhex('7f3e9c2a8b5d1f4e6a9c3b7d2e5f8a1c4b6d9e2f5a8c1b4d7e9f2a5c8b1d4e7f')


class source:
    def __init__(self):
        self.results = []
        self.domains = ['vidrock.net']
        self.base_link = 'https://vidrock.net'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': 'https://vidrock.net/',
            'Origin': 'https://vidrock.net',
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
                path = 'tv/%s/%s/%s' % (tmdb, data['season'], data['episode'])
            else:
                path = 'movie/%s' % tmdb
            payload = client.request(self.base_link + '/api/' + path, headers={
                'User-Agent': client.UserAgent,
                'Accept': 'application/json',
            }, timeout='15', output='json')
            if not isinstance(payload, dict):
                return self.results
            for name, entry in payload.items():
                if str(name).strip().lower() in ('astra', 'atlas'):
                    continue
                if not isinstance(entry, dict) or not entry.get('url'):
                    continue
                try:
                    encoded = entry['url'].replace('-', '+').replace('_', '/')
                    encoded += '=' * ((4 - len(encoded) % 4) % 4)
                    blob = base64.b64decode(encoded)
                    link = aes_gcm_decrypt(_KEY, blob[:12], blob[12:])
                    if isinstance(link, bytes):
                        link = link.decode('utf-8')
                except Exception:
                    continue
                if not isinstance(link, str) or not link.startswith('http'):
                    continue
                play = link + source_utils.append_headers(self.headers)
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Vidrock %s' % name)
                if item.get('url') and not scrape_sources.check_host_limit(item['source'], self.results):
                    self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def resolve(self, url):
        return url
