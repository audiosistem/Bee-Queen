from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils
from resources.lib.modules import twoembed_chain


class source:
    def __init__(self):
        self.results = []
        self.domains = ['2embed.cc', 'www.2embed.cc', '2embed.skin']
        self.base_link = twoembed_chain.BASE


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
            return
        return urlencode({'tmdb': tmdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        return


    def episode(self, url, imdb, tmdb, tvdb, title, premiered, season, episode):
        return


    def sources(self, url, hostDict):
        try:
            if not url:
                return self.results
            data = parse_qs(url)
            data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])
            embed = twoembed_chain.embed_url(data.get('tmdb'))
            if not embed:
                return self.results
            urls, headers = twoembed_chain.resolve_embed(embed)
            for link in urls:
                play = link + source_utils.append_headers(headers) if headers else link
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='2Embed')
                if item.get('url') and item['url'] not in [row.get('url') for row in self.results]:
                    if not scrape_sources.check_host_limit(item['source'], self.results):
                        self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def resolve(self, url):
        return url
