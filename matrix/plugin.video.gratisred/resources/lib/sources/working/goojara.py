# -*- coding: utf-8 -*-

import re
from six.moves.urllib_parse import parse_qs, quote_plus, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources

_SLUG_RE = re.compile(
    r'<a\s+href="(/[a-zA-Z0-9]{5,12})"[^>]*>\s*(?:<div[^>]*>\s*)*<strong>([^<]+)</strong>'
    r'(?:\s*\(?(\d{4})\)?)?',
    re.I | re.S,
)
_BCG_RE = re.compile(
    r"""<a\s+class=['"]bcg['"]\s+href=['"]([^'"]+)['"][^>]*>\s*([^<\s]+)""",
    re.I | re.S,
)


class source:
    def __init__(self):
        self.results = []
        self.domains = ['ww1.goojara.to', 'goojara.to']
        self.base_link = 'https://ww1.goojara.to'
        self.notes = 'Movies. File-host links. A backup for the same hosts Levidia lists.'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Accept': 'text/html,application/xhtml+xml,*/*',
            'Referer': self.base_link + '/',
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        title = title or localtitle or ''
        if not title:
            return
        return urlencode({'title': title, 'year': year or '', 'media': 'movie'})


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
            title = data.get('title') or ''
            year = data.get('year') or ''
            if not title:
                return self.results
            opened = client.request(self.base_link + '/', headers=self.headers, output='extended', timeout='12')
            if not opened or not opened[0]:
                return self.results
            html, cookie = opened[0], opened[3] or ''
            token_z = re.search(r'id=["\']res["\'][^>]*data-ins=["\']([^"\']+)["\']', html)
            token_x = re.search(r"""['"]?z=['"]?\s*\+\s*\w+\s*\+\s*['"]&x=([a-f0-9]{6,40})&q=""", html)
            if not token_z or not token_x:
                return self.results
            body = 'z=%s&x=%s&q=%s' % (token_z.group(1), token_x.group(1), quote_plus(title))
            search_headers = dict(self.headers)
            search_headers.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            found = client.request(self.base_link + '/xmre.php', post=body, headers=search_headers, cookie=cookie, timeout='12')
            slug = self._slug(found or '', title, year)
            if not slug:
                return self.results
            page = client.request(self.base_link + slug, headers=self.headers, cookie=cookie, timeout='12')
            if not page:
                return self.results
            seen = set()
            for href, _host in _BCG_RE.findall(page)[:8]:
                href = (href or '').strip()
                if href.startswith('/'):
                    href = self.base_link + href
                if not href.startswith('http') or href in seen:
                    continue
                seen.add(href)
                landed = client.request(href, headers=self.headers, cookie=cookie, output='geturl', timeout='8') or href
                for item in scrape_sources.process(hostDict, landed):
                    if item.get('url') and item['url'] not in seen:
                        seen.add(item['url'])
                        self.results.append(item)
            return self.results
        except Exception:
            return self.results


    def _slug(self, html, title, year):
        wanted = title.lower().strip()
        year = str(year or '').strip()
        rows = _SLUG_RE.findall(html or '')
        for slug, label, found_year in rows:
            if wanted == (label or '').lower().strip() and (not year or not found_year or year == found_year):
                return slug
        for slug, label, found_year in rows:
            if wanted in (label or '').lower() and year and found_year == year:
                return slug
        for slug, label, _found_year in rows:
            if wanted == (label or '').lower().strip():
                return slug
        return ''


    def resolve(self, url):
        return url
