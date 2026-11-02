from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils
from resources.lib.modules import vixsrc_chain


class source:
    def __init__(self):
        self.results = []
        self.domains = ['vixsrc.to']
        self.base_link = vixsrc_chain.SITE


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
            media = data.get('media') or 'movie'
            urls, headers = vixsrc_chain.resolve_ident(
                tmdb, media, data.get('season'), data.get('episode'))
            for link in urls:
                play = link + source_utils.append_headers(headers) if headers else link
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Vixsrc')
                if item.get('url') and item['url'] not in [row.get('url') for row in self.results]:
                    if not scrape_sources.check_host_limit(item['source'], self.results):
                        self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def resolve(self, url):
        return url
