# -*- coding: utf-8 -*-

import re
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources

_SRC_RE = re.compile(r"""(?:src|file)\s*[:=]\s*['"](https?://[^'"]+)['"]""", re.I)


class source:
    def __init__(self):
        self.results = []
        self.domains = ['movieseq.com', 'nextgencloudfabric.com']
        self.base_link = 'https://movieseq.com'
        self.notes = 'TMDb embed. The player page is passed to ResolveURL when the host is known.'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': self.base_link + '/',
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
                embed = '%s/embed/tv/%s/%s/%s' % (self.base_link, tmdb, data['season'], data['episode'])
            else:
                embed = '%s/embed/movie/%s' % (self.base_link, tmdb)
            page = client.request(embed, headers=self.headers, timeout='8') or ''
            seen = set()
            links = [embed]
            links.extend(re.findall(r"""<iframe[^>]+src=['"]([^'"]+)['"]""", page, re.I))
            links.extend(_SRC_RE.findall(page))
            for link in links:
                if link.startswith('//'):
                    link = 'https:' + link
                if not link.startswith('http') or link in seen:
                    continue
                if 'histats.com' in link or 'cloudflare.com' in link or link in ('about:blank',):
                    continue
                seen.add(link)
                for item in scrape_sources.process(hostDict, link):
                    if item.get('url'):
                        self.results.append(item)
                if link == embed:
                    continue
                inner = client.request(link, headers=self.headers, timeout='8') or ''
                for raw in _SRC_RE.findall(inner):
                    if raw in seen:
                        continue
                    seen.add(raw)
                    for item in scrape_sources.process(hostDict, raw):
                        if item.get('url'):
                            self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def resolve(self, url):
        return url
