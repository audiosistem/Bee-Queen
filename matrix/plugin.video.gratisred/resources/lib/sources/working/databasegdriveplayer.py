import re
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import client_utils
from resources.lib.modules import scrape_sources

DOM = client_utils.parseDOM


class source:
    def __init__(self):
        self.results = []
        self.domains = ['databasegdriveplayer.co', 'database.gdriveplayer.us', 'series.databasegdriveplayer.co']
        self.base_link = 'https://databasegdriveplayer.co'


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not imdb or str(imdb) in ('0', 'None'):
            return
        return urlencode({'imdb': imdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not imdb or str(imdb) in ('0', 'None'):
            return
        return urlencode({'imdb': imdb, 'media': 'tv'})


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
            imdb = data.get('imdb')
            if not imdb or imdb == '0':
                return self.results
            if data.get('media') == 'tv':
                if not data.get('season') or not data.get('episode'):
                    return self.results
                player = '%s/player.php?type=series&imdb=%s&season=%s&episode=%s' % (
                    self.base_link, imdb, data['season'], data['episode'])
            else:
                player = '%s/player.php?imdb=%s' % (self.base_link, imdb)
            html = client.request(player, timeout='15')
            if not html:
                return self.results
            for link in self._servers(html):
                self._add(link, hostDict)
            return self.results
        except Exception:
            return self.results


    def _servers(self, html):
        try:
            servers = DOM(html, 'ul', attrs={'class': 'list-server-items'})
            if servers:
                return DOM(servers[0], 'a', ret='href') or []
        except Exception:
            pass
        return re.findall(r'href=["\'](.*?)["\']', html)


    def _rewrite(self, link):
        if link.startswith('//'):
            link = 'https:' + link
        return (link.replace('vidcloud.icu', 'vidembed.io')
                .replace('vidcloud9.com', 'vidembed.io')
                .replace('vidembed.cc', 'vidembed.io')
                .replace('vidnext.net', 'vidembed.me'))


    def _add(self, link, hostDict):
        if not link or link.startswith('/player.php'):
            return
        link = self._rewrite(link)
        if not link.startswith('http'):
            return
        if 'vidembed' in link:
            html = client.request(link, timeout='15')
            if html:
                for video in DOM(html, 'li', ret='data-video') or []:
                    self._add_host(self._rewrite(video), hostDict)
        self._add_host(link, hostDict)


    def _add_host(self, link, hostDict):
        link = link.split('&title=')[0]
        item = scrape_sources.make_item(hostDict, link, prep=True)
        if not item.get('url'):
            return
        if scrape_sources.check_host_limit(item['source'], self.results):
            return
        if item['url'] in [i.get('url') for i in self.results]:
            return
        self.results.append(item)


    def resolve(self, url):
        return url
