import re
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils
from resources.lib.modules import vidsrc_chain


HOSTS = vidsrc_chain.HOSTS + (
    '2embed.cc', '2embed.skin', 'multiembed.mov', 'vidsrcme.ru',
)
CDN_POOL = (
    'shadowlandschronicles.com', 'cdn-centaurus.com', 'cdn-fnc.com',
    'shadowlands-cdn.com', 'nestra-cdn.com', 'cloudnestra.com', 'tmstr-cdn.com',
)


def _ok(value):
    text = str(value or '').strip()
    return text if text and text not in ('0', 'None') else ''


class source:
    def __init__(self):
        self.results = []
        self.domains = list(HOSTS) + ['cloudnestra.com']
        self.base_link = 'https://%s' % vidsrc_chain.HOSTS[0]
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': self.base_link + '/',
            'Origin': self.base_link,
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        tmdb, imdb = _ok(tmdb), _ok(imdb)
        if not tmdb and not imdb:
            return
        return urlencode({'tmdb': tmdb, 'imdb': imdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        tmdb, imdb = _ok(tmdb), _ok(imdb)
        if not tmdb and not imdb:
            return
        return urlencode({'tmdb': tmdb, 'imdb': imdb, 'media': 'tv'})


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
            tmdb, imdb = _ok(data.get('tmdb')), _ok(data.get('imdb'))
            idents = []
            for ident in (tmdb, imdb):
                if ident and ident not in idents:
                    idents.append(ident)
            if not idents:
                return self.results
            media = data.get('media') or 'movie'
            season = data.get('season') if media == 'tv' else None
            episode = data.get('episode') if media == 'tv' else None
            if media == 'tv' and (not season or not episode):
                return self.results
            for ident in idents:
                urls, headers = vidsrc_chain.resolve_ident(
                    media, ident, season=season, episode=episode)
                if urls:
                    for link in urls:
                        self._add(hostDict, link, headers)
                    if self.results:
                        return self.results
            self._legacy(hostDict, idents, media, season, episode)
            return self.results
        except Exception:
            return self.results


    def _legacy(self, hostDict, idents, media, season, episode):
        for ident in idents:
            if media == 'tv':
                path = 'embed/tv/%s/%s/%s' % (ident, season, episode)
            else:
                path = 'embed/movie/%s' % ident
            for host in HOSTS:
                if len(self.results) >= 8:
                    return
                embed = 'https://%s/%s' % (host, path)
                html = client.request(embed, headers={'User-Agent': client.UserAgent, 'Referer': embed}, timeout='12')
                if not html:
                    continue
                self._from_body(hostDict, html, embed)
                if self.results:
                    return


    def _from_body(self, hostDict, html, referer):
        for link in self._media(html)[:4]:
            self._add(hostDict, link)
        for rcp in self._servers(html)[:3]:
            body = client.request(rcp, headers={'User-Agent': client.UserAgent, 'Referer': referer}, timeout='12')
            if not body:
                continue
            host = re.sub(r'^https?://', '', rcp).split('/')[0]
            nxt = self._next(body, host)
            body2 = ''
            if nxt:
                body2 = client.request(nxt, headers={'User-Agent': client.UserAgent, 'Referer': rcp}, timeout='12') or ''
            pool = self._pool(body2 or body)
            raws = []
            for text in (body2, body):
                if not text:
                    continue
                found = re.search(r"""file\s*:\s*['"]([^'"]+?)['"]""", text)
                if found:
                    raws.append(found.group(1))
                raws.extend(self._media(text))
            seen = set()
            for raw in raws:
                for link in self._expand(raw, pool):
                    if link in seen or '{v' in link:
                        continue
                    seen.add(link)
                    self._add(hostDict, link)
                    if len(self.results) >= 8:
                        return


    def _servers(self, html):
        found = []
        for match in re.finditer(r'src=["\']((?:https?:)?//cloudnestra\.com/rcp/[^"\']+)["\']', html, re.I):
            url = match.group(1)
            if url.startswith('//'):
                url = 'https:' + url
            if url not in found:
                found.append(url)
        for match in re.finditer(r'data-hash=["\']([^"\']+)["\']', html):
            token = match.group(1)
            if len(token) > 20:
                url = 'https://cloudnestra.com/rcp/' + token
                if url not in found:
                    found.append(url)
        return found


    def _next(self, body, host):
        if not body:
            return ''
        frames = re.findall(r'<iframe[^>]+src=["\']([^"\'#]+)["\']', body, re.I)
        frames.sort(key=lambda href: 0 if href.startswith('/') else 1)
        for href in frames:
            if href.startswith('about:'):
                continue
            if href.startswith('//'):
                return 'https:' + href
            if href.startswith('/'):
                return 'https://%s%s' % (host, href)
            if href.startswith('http'):
                return href
        match = re.search(r"""['"](/prorcp/[A-Za-z0-9+/=_\-]{8,})['"]""", body)
        if match:
            return 'https://%s%s' % (host, match.group(1))
        return ''


    def _media(self, body):
        if not body:
            return []
        out = []
        for match in re.finditer(r'(https?://[^\s\'"<>]+?\.(?:m3u8|mp4)[^\s\'"<>]*)', body, re.I):
            url = match.group(1).replace('\\u002F', '/').replace('\\u002f', '/')
            if url not in out:
                out.append(url)
        return out


    def _pool(self, body):
        pool = []
        for match in re.finditer(r"""(?:servers|cdns|hosts)\s*[:=]\s*\[([^\]]+)\]""", body or '', re.I):
            for host in re.findall(r"""['"]([a-z0-9.\-]+\.[a-z]{2,})['"]""", match.group(1), re.I):
                if host not in pool:
                    pool.append(host)
        for host in CDN_POOL:
            if host not in pool:
                pool.append(host)
        return pool


    def _expand(self, raw, pool):
        parts = [part.strip() for part in re.split(r'\s+or\s+', raw) if part.strip()]
        out = []
        for part in parts:
            slots = sorted(set(re.findall(r'\{v(\d+)\}', part)))
            if not slots:
                out.append(part)
                continue
            for host in pool:
                url = part
                for slot in slots:
                    url = url.replace('{v%s}' % slot, host)
                out.append(url)
        return out


    def _add(self, hostDict, link, headers=None):
        if not link or not link.startswith('http'):
            return
        play_headers = headers or self.headers
        play = link + source_utils.append_headers(play_headers)
        item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Vidsrc')
        if not item.get('url'):
            return
        if item['url'] in [row.get('url') for row in self.results]:
            return
        if scrape_sources.check_host_limit(item['source'], self.results):
            return
        self.results.append(item)


    def resolve(self, url):
        return url
