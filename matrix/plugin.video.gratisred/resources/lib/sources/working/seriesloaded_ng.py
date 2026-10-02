# -*- coding: utf-8 -*-

import re

from six.moves.urllib_parse import parse_qs, quote_plus, urlencode, urlparse

from resources.lib.modules import cleantitle
from resources.lib.modules import client
from resources.lib.modules import client_utils
from resources.lib.modules import scrape_sources
from resources.lib.modules import log_utils

DOM = client_utils.parseDOM

class source:
    def __init__(self):
        self.results = []
        self.domains = ['seriezloaded.tv', 'seriezloaded.com.ng']
        self.base_link = 'https://seriezloaded.tv'
        self.search_link = '/?s=%s'
        self.headers = client.dnt_headers
        self.notes = 'tough site, lots of custom links and weird grouping.'
        

    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        url = {'imdb': imdb, 'tmdb': tmdb, 'title': title, 'localtitle': localtitle, 'aliases': aliases, 'year': year}
        url = urlencode(url)
        return url


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        url = {'imdb': imdb, 'tmdb': tmdb, 'tvshowtitle': tvshowtitle, 'aliases': aliases, 'year': year}
        url = urlencode(url)
        return url


    def episode(self, url, imdb, tmdb, tvdb, title, premiered, season, episode):
        if not url:
            return
        url = parse_qs(url)
        url = dict([(i, url[i][0]) if url[i] else (i, '') for i in url])
        url['title'], url['premiered'], url['season'], url['episode'] = title, premiered, season, episode
        url = urlencode(url)
        return url

    def getlinks(self, data, aliases, title, season, episode, year, page_link=None):
        if any(domain in page_link for domain in self.domains):
            html = client.request(page_link, headers=self.headers)
            ext_links = DOM(html, 'div', attrs={'class': 'sl-container'})
            if not ext_links:
                return

            onclick_values = DOM(ext_links, 'button', ret='onclick')
            title_elements = DOM(ext_links, 'h2')

            if not onclick_values or not title_elements:
                return

            url = onclick_values[0]
            title = title_elements[0]

            match = re.search(r"https?://[^\s'\"]+", url)  # don't include ending single quote
            link = None
            if match:
                link = match.group()
        else:
            link = page_link

            
        return link

    def sources(self, url, hostDict):
        try:
            if not url:
                return self.results
            data = parse_qs(url)
            data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])
            title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
            season = data.get('season') or ''
            episode = data.get('episode') or ''
            year = data['premiered'].split('-')[0] if 'tvshowtitle' in data and data.get('premiered') else data.get('year') or ''
            slug = cleantitle.geturl(title)
            if not slug:
                return self.results
            html = client.request(self.base_link + self.search_link % quote_plus(title), headers=self.headers, timeout='15')
            if not html:
                return self.results
            page = ''
            seen = set()
            for path in re.findall(r'https://seriezloaded\.tv/([a-z0-9-]+)/', html):
                if path in seen:
                    continue
                seen.add(path)
                if 'tvshowtitle' in data:
                    if slug in path and ('season-%s-episode-%s' % (season, episode)) in path and 'complete' not in path:
                        page = '%s/%s/' % (self.base_link, path)
                        break
                elif path.startswith(slug) and (not year or year in path):
                    page = '%s/%s/' % (self.base_link, path)
                    break
            if not page:
                return self.results
            page_html = client.request(page, headers=self.headers, timeout='15')
            if not page_html:
                return self.results
            buttons = re.findall(r'href="(https://seriezloaded\.tv/sl-download\?link=[^"]+)"', page_html)
            referer = dict(self.headers)
            referer['Referer'] = page
            for button in buttons[:8]:
                hop = client.request(button, headers=referer, timeout='15')
                if not hop:
                    continue
                for link in re.findall(r'href="(https?://[^"]+)"', hop):
                    if 'seriezloaded' in link:
                        continue
                    for source in scrape_sources.process(hostDict, link):
                        if source.get('url') and source['url'] not in [i.get('url') for i in self.results]:
                            self.results.append(source)
            return self.results
        except Exception:
            return self.results



    def resolve(self, url):
        try:
            if 'send' in url:
                url = url.replace('send.cm', 'send.now')  # pull request https://github.com/Gujal00/ResolveURL/pull/1133
                url = url.replace('sendit.cloud', 'send.now')
            elif 'waffi.cloud' in url:
                if url.endswith('?preview'):
                    url = url[:-len('?preview')]
            elif 'loadedfiles' in url:   #  TODO: move to scrape_sources_py
                self.headers.pop("Cookie", None)  # remove the item Cookie, if exists
                self.cookie = client.request(url, headers=self.headers, output='cookie', timeout='10')
                self.headers.update({'Host': 'loadedfiles.org'})
                html = client.request(url, headers=self.headers, cookie=self.cookie)
                match = re.search(r'var\s+downloadUrl\s*=\s*["\']([^"\']+)["\']', html)
                if not match:
                    return
                download_link = match.group(1)
                self.headers.update({'Referer': url,
                                     'Priority': 'u=0, i',
                                     'Te': 'trailers',
                                     })
                html2 = client.request(download_link, headers=self.headers)
                match2 = re.search(r'var\s+downloadUrl\s*=\s*["\']([^"\']+)["\']', html2)
                if not match2:
                    return
                download_link2 = match2.group(1)
                url = client.request(download_link2, headers=None, cookie=self.cookie, output='geturl', timeout='30')
            elif 'pixeldrain' in url:
                return url
            else:
                html = client.request(url, headers=self.headers, timeout=10)
                if not html:
                    return
                if any(msg in html.lower() for msg in ('file not found',
                                                       'no such file=',
                                                       'video you are looking for is not found',
                                                       'video unavailable',
                                                       'need to enable javascript',
                                                       )):
                    return

                link = DOM(html, 'iframe', ret='src')
                if not link:
                    return
                url = link[0] if link else None
                if link == '/e/' or 'javascript' in link:
                    link = None


        except:
            pass

        return url


