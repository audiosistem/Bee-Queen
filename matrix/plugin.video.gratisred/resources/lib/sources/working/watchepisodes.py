import re

from resources.lib.modules import cleantitle
from resources.lib.modules import client
from resources.lib.modules import scrape_sources


class source:
    def __init__(self):
        self.results = []
        self.domains = ['watchepisodes4.com', 'www.watchepisodes4.com']
        self.base_link = 'https://www.watchepisodes4.com/'


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        return


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        title = tvshowtitle or localtvshowtitle
        if not title:
            return
        return self.base_link + cleantitle.geturl(title)


    def episode(self, url, imdb, tmdb, tvdb, title, premiered, season, episode):
        try:
            if not url:
                return
            html = client.request(url, timeout='15')
            if not html:
                return
            pattern = r'<a title=".+? Season %s Episode %s .+?" href="(.+?)">' % (season, episode)
            matches = re.findall(pattern, html)
            if matches:
                return matches[0]
        except Exception:
            return


    def sources(self, url, hostDict):
        try:
            if not url or not str(url).startswith('http'):
                return self.results
            html = client.request(url, timeout='15')
            if not html:
                return self.results
            for link in re.findall(r'class="watch-button" data-actuallink="(.+?)"', html):
                item = scrape_sources.make_item(hostDict, link, prep=True)
                if not item.get('url'):
                    continue
                if scrape_sources.check_host_limit(item['source'], self.results):
                    continue
                if item['url'] in [i.get('url') for i in self.results]:
                    continue
                self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def resolve(self, url):
        return url
