import json
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


class source:
    def __init__(self):
        self.results = []
        self.domains = ['player.vidlove.cc', 'api.vidlove.cc']
        self.base_link = 'https://player.vidlove.cc'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': self.base_link + '/',
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
                api = 'https://api.vidlove.cc/tv?id=%s&season=%s&episode=%s&mode=json' % (
                    tmdb, data['season'], data['episode'])
            else:
                api = 'https://api.vidlove.cc/movie?id=%s&mode=json' % tmdb
            raw = client.request(api, headers=self.headers, timeout='15')
            if not raw:
                return self.results
            payload = json.loads(raw)
            source = payload.get('source') if isinstance(payload, dict) else None
            link = source.get('url') if isinstance(source, dict) else ''
            if not isinstance(link, str) or not link.startswith('http'):
                return self.results
            play = link + source_utils.append_headers(self.headers)
            item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='VidLove')
            if item.get('url'):
                self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def resolve(self, url):
        return url
