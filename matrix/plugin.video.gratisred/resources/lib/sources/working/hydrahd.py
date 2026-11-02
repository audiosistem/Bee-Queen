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


STATUS_URL = 'https://hydrahd.info/'
FALLBACK = ('hydrahd.ws', 'hydrahd.io', 'hydrahd.cc', 'hydrahd.me', 'hydrahd.ac')


class source:
    def __init__(self):
        self.results = []
        self.domains = ['hydrahd.ws', 'hydrahd.info', 'hydrahd.io', 'hydrahd.cc']
        self.base_link = 'https://hydrahd.ws'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': self.base_link + '/',
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
            imdb = data.get('imdb') or ''
            if not tmdb:
                return self.results
            media = data.get('media') or 'movie'
            season = data.get('season') if media == 'tv' else None
            episode = data.get('episode') if media == 'tv' else None
            if media == 'tv' and (not season or not episode):
                return self.results
            if not imdb.startswith('tt'):
                return self.results
            params = {'i': imdb, 't': str(tmdb)}
            if media == 'tv':
                params.update(s=str(season), e=str(episode))
            path = '/ajax/%s_0.php?%s' % ('mov' if media == 'movie' else 'tv', urlencode(params))
            html = self._ajax(path)
            meta = {'title': data.get('title') or '', 'year': data.get('year') or '', 'imdb': imdb}
            for embed in self._servers(html)[:12]:
                streams = dulo_players.resolve_embed(embed, meta)
                for link, headers in streams:
                    self._add(hostDict, link, headers, urlparse(embed).hostname or 'HydraHD')
                if len(self.results) >= 10:
                    break
            return self.results
        except Exception:
            return self.results


    def _domains(self):
        hosts = list(FALLBACK)
        try:
            page = client.request(STATUS_URL, headers={'User-Agent': client.UserAgent, 'Referer': STATUS_URL}, timeout='10') or ''
            found = []
            for link in re.findall(r'https://(hydrahd\.[a-z0-9.]+)', page, re.I):
                host = link.lower()
                if host not in ('hydrahd.info', 'hydrahd.ru') and host not in found:
                    found.append(host)
            if found:
                hosts = found
        except Exception:
            pass
        if 'hydrahd.ws' in hosts:
            hosts = ['hydrahd.ws'] + [h for h in hosts if h != 'hydrahd.ws']
        return hosts


    def _ajax(self, path):
        for host in self._domains():
            base = 'https://' + host
            html = client.request(base + path, headers={
                'User-Agent': client.UserAgent,
                'Referer': base + '/',
                'X-Requested-With': 'XMLHttpRequest',
            }, timeout='10')
            if html and 'data-link=' in html:
                return html
        return ''


    def _servers(self, html):
        found = []
        for match in re.finditer(r'<div([^>]*iframe-server-button[^>]*)>', html or '', re.I):
            attrs = match.group(1)
            if re.search(r'\bpremium\b', attrs):
                continue
            link = re.search(r'data-link=["\']([^"\']+)["\']', attrs)
            if not link:
                continue
            url = html_unescape(link.group(1)).strip()
            if url.startswith('http') and url not in found:
                found.append(url)
        if not found:
            for url in re.findall(r'data-link=["\'](https?://[^"\']+)["\']', html or ''):
                url = html_unescape(url).strip()
                if url not in found:
                    found.append(url)
        return found


    def _add(self, hostDict, link, headers, label):
        if not link or not str(link).startswith('http'):
            return
        play = link + source_utils.append_headers(headers or self.headers)
        item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='HydraHD %s' % label)
        if not item.get('url') or item['url'] in [row.get('url') for row in self.results]:
            return
        if scrape_sources.check_host_limit(item['source'], self.results):
            return
        self.results.append(item)


    def resolve(self, url):
        return url
