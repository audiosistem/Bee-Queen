import re
from six.moves.urllib_parse import parse_qs, urlencode, urlparse

from resources.lib.modules import client
from resources.lib.modules import dulo_players
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils

try:
    from html import unescape as html_unescape
except ImportError:
    from six.moves.html_parser import HTMLParser
    html_unescape = HTMLParser().unescape


BASE = 'https://dulo.vg'


class source:
    def __init__(self):
        self.results = []
        self.domains = ['dulo.vg']
        self.base_link = BASE
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': BASE + '/',
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
            return
        return urlencode({
            'tmdb': tmdb, 'imdb': imdb or '', 'title': title or '',
            'year': year or '', 'media': 'movie',
        })


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
            return
        return urlencode({
            'tmdb': tmdb, 'imdb': imdb or '', 'title': tvshowtitle or localtvshowtitle or '',
            'year': year or '', 'media': 'tv',
        })


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
            media = data.get('media') or 'movie'
            if media == 'tv':
                if not data.get('season') or not data.get('episode'):
                    return self.results
                watch = '%s/watch/tv/%s/%s/%s' % (BASE, tmdb, data['season'], data['episode'])
            else:
                watch = '%s/watch/movie/%s' % (BASE, tmdb)
            html = client.request(watch, headers=self.headers, timeout='15') or ''
            meta = {'title': data.get('title') or '', 'year': data.get('year') or '', 'imdb': data.get('imdb') or ''}
            for embed in self._embeds(html):
                streams = dulo_players.resolve_embed(embed, meta)
                host = urlparse(embed).hostname or 'Dulo'
                for link, headers in streams:
                    self._add(hostDict, link, headers, host)
                if len(self.results) >= 10:
                    break
            return self.results
        except Exception:
            return self.results


    def _embeds(self, html):
        found = []
        for raw in re.findall(r'data-embed=["\']([^"\']+)["\']', html or ''):
            url = html_unescape(raw).strip()
            if url.startswith('http') and url not in found:
                found.append(url)
        return found


    def _add(self, hostDict, link, headers, label):
        if not link or not str(link).startswith('http'):
            return
        play = link + source_utils.append_headers(headers or self.headers)
        item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Dulo %s' % label)
        if not item.get('url') or item['url'] in [row.get('url') for row in self.results]:
            return
        if scrape_sources.check_host_limit(item['source'], self.results):
            return
        self.results.append(item)


    def resolve(self, url):
        return url
