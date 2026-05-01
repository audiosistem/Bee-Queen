# -*- coding: utf-8 -*-
import re
import threading
import requests
import xbmc

_BASE    = 'https://hydrahd.ru'
_LABEL   = '[HHD]'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer':    _BASE + '/',
    'Accept':     'text/html,application/xhtml+xml,*/*;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Hosturi acoperite de resolvere dedicate din Samus — sărim duplicatele din HHD
_SKIP_HOSTS = {
    'vidsrc.cc', 'vidsrc.to', 'vidsrc.in', 'vidsrc.pm', 'vidsrc.su',
    'vidrock.net',
    '2embed.cc',
    'vidfast.pro',
    'vidup.to',
    'vidify.me',
}

_BTN_RE = re.compile(
    r'<div[^>]+class="iframe-server-button([^"]*)"[^>]+data-id="(\d+)"[^>]+data-link="([^"]+)"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_NAME_RE   = re.compile(r'<p[^>]*>([^<]+)</p>',                              re.IGNORECASE)
_SPAN_RE   = re.compile(r'iframe-server-name[^>]*>([^<]+)<',                 re.IGNORECASE)
_QUAL_RE   = re.compile(r'iframe-server-quality[^>]*>([^<]+)<',              re.IGNORECASE)
_Q_NORM    = {'4k': '4K', '2160p': '4K', '1080p': '1080p', '720p': '720p', '480p': '480p', '360p': '360p'}

_STREAM_RE = [
    re.compile(r'["\']?(?:file|src)["\']?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'["\']?(?:file|src)["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',  re.IGNORECASE),
    re.compile(r'source\s+src=["\']([^"\']+\.m3u8[^"\']*)["\']',                   re.IGNORECASE),
    re.compile(r'source\s+src=["\']([^"\']+\.mp4[^"\']*)["\']',                    re.IGNORECASE),
]
_SCRIPT_RE = re.compile(r'<script[^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# Dean Edwards p.a.c.k.e.r unpacker
# Adapted from MammaMia/Src/Utilities/eval.py (MIT) — original by Stefano Sanfilippo
# ---------------------------------------------------------------------------

class _UnpackingError(Exception):
    pass


class _Unbaser:
    _ALPHABET = {
        62: '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
        95: (' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ'
             '[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'),
    }

    def __init__(self, base):
        self.base = base
        if 36 < base < 62:
            self._ALPHABET.setdefault(base, self._ALPHABET[62][:base])
        if 2 <= base <= 36:
            self.unbase = lambda s: int(s, base)
        else:
            try:
                self.dictionary = {c: i for i, c in enumerate(self._ALPHABET[base])}
            except KeyError:
                raise TypeError('Unsupported base encoding.')
            self.unbase = self._dictunbaser

    def __call__(self, string):
        return self.unbase(string)

    def _dictunbaser(self, string):
        ret = 0
        for idx, cipher in enumerate(string[::-1]):
            ret += (self.base ** idx) * self.dictionary[cipher]
        return ret


def _packer_detect(source):
    return 'eval(function(p,a,c,k,e,' in source


def _packer_unpack(source):
    juicers = [
        r"}\('(.*)', *(\d+|\[\]), *(\d+), *'(.*)'\.split\('\|'\), *(\d+), *(.*)\)\)",
        r"}\('(.*)', *(\d+|\[\]), *(\d+), *'(.*)'\.split\('\|'\)",
    ]
    args = None
    for j in juicers:
        args = re.search(j, source, re.DOTALL)
        if args:
            break
    if not args:
        raise _UnpackingError('Could not parse p.a.c.k.e.r data')

    a = list(args.groups())
    if a[1] == '[]':
        a[1] = 62
    try:
        payload, symtab, radix, count = a[0], a[3].split('|'), int(a[1]), int(a[2])
    except ValueError:
        raise _UnpackingError('Corrupted p.a.c.k.e.r data')

    if count != len(symtab):
        raise _UnpackingError('Malformed p.a.c.k.e.r symtab')

    unbase = _Unbaser(radix)
    payload = payload.replace('\\\\', '\\').replace("\\'", "'")

    def lookup(m):
        word = m.group(0)
        return symtab[unbase(word)] or word

    source = re.sub(r'\b\w+\b', lookup, payload)

    # strip string lookup table
    match = re.search(r'var *(_\w+)\=\["(.*?)"\];', source, re.DOTALL)
    if match:
        varname, strings = match.groups()
        lookup_table = strings.split('","')
        variable = '%s[%%d]' % varname
        for index, value in enumerate(lookup_table):
            source = source.replace(variable % index, '"%s"' % value)
        source = source[len(match.group(0)):]

    return source


def _norm_quality(hint):
    if not hint:
        return ''
    h = hint.strip().strip('()').strip()
    return _Q_NORM.get(h.lower(), h)


def _unescape_html(s):
    return s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#039;', "'")


def _fetch(url, referer=None):
    h = dict(_HEADERS)
    if referer:
        h['Referer'] = referer
    try:
        r = requests.get(url, headers=h, timeout=12, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        xbmc.log(f'[Samus/HydraHD] fetch {url}: {e}', xbmc.LOGWARNING)
        return ''


def _parse_mirrors(html):
    sources = []
    for m in _BTN_RE.finditer(html):
        flags  = m.group(1)
        inner  = m.group(4)
        link   = _unescape_html(m.group(3))

        name_m = _NAME_RE.search(inner) or _SPAN_RE.search(inner)
        name   = name_m.group(1).strip() if name_m else f'Server {m.group(2)}'
        qual_m = _QUAL_RE.search(inner)
        quality = _norm_quality(qual_m.group(1) if qual_m else '')

        if not link.startswith('http'):
            if link.startswith('//'):
                link = 'https:' + link
            else:
                continue

        from urllib.parse import urlparse
        host = urlparse(link).netloc.lstrip('www.')
        if any(host == s or host.endswith('.' + s) for s in _SKIP_HOSTS):
            continue

        sources.append({
            'url':        link,
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': name,
            'direct':     False,
            '_premium':   'premium' in flags.lower(),
        })
    return sources


def _unpack_eval(js):
    """Very basic Dean Edwards p,a,c,k unpacker — extracts string constants only."""
    try:
        m = re.search(r"'([^']+)'\.split\('\\|'\)", js)
        if not m:
            return js
        words = m.group(1).split('|')
        result = js
        for i, w in enumerate(reversed(words)):
            if w:
                result = re.sub(r'\b' + re.escape(str(len(words) - 1 - i)) + r'\b', w, result)
        return result
    except Exception:
        return js


def _resolve_primesrc(embed_url):
    """primesrc.me: extrage tmdb_id și folosește lanțul intern vidsrcme→cloudnestra→m3u8."""
    try:
        m = re.search(r'/(movie|tv)[/?].*?tmdb=(\d+)', embed_url)
        if not m:
            return None
        from resources.lib.resolvers.primesrc import _extract
        results = _extract(m.group(1), int(m.group(2)))
        if results:
            return results[0]['url']
    except Exception as e:
        xbmc.log(f'[Samus/HydraHD] primesrc resolve: {e}', xbmc.LOGWARNING)
    return None


def _resolve_xpass(embed_url):
    """xpass.top: try /playlist.json endpoint for direct HLS."""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(embed_url)
        playlist_url = urlunparse(p._replace(path=p.path.rstrip('/') + '/playlist.json'))
        r = requests.get(playlist_url, headers=_HEADERS, timeout=10)
        if r.ok:
            data = r.json()
            sources = data if isinstance(data, list) else data.get('sources', [])
            for s in sources:
                file_url = s.get('file') or s.get('src') or s.get('url')
                if file_url and ('.m3u8' in file_url or '.mp4' in file_url):
                    if file_url.startswith('//'):
                        file_url = 'https:' + file_url
                    return file_url
    except Exception:
        pass
    return None


def _resolve_embed(embed_url):
    """Fetch embed page and try to find a direct m3u8/mp4 URL."""
    try:
        if 'primesrc.me' in embed_url:
            result = _resolve_primesrc(embed_url)
            if result:
                return result

        if 'xpass.top' in embed_url:
            result = _resolve_xpass(embed_url)
            if result:
                return result

        html = _fetch(embed_url, referer=_BASE + '/')
        if not html:
            return None

        # Unpack eval-packed script blocks, then search for stream URLs
        searchable = html
        for script_m in _SCRIPT_RE.finditer(html):
            block = script_m.group(1)
            if _packer_detect(block):
                try:
                    searchable += '\n' + _packer_unpack(block)
                except _UnpackingError:
                    pass

        for pattern in _STREAM_RE:
            for u in pattern.finditer(searchable):
                url = u.group(1)
                if url.startswith('//'):
                    url = 'https:' + url
                if url.startswith('http'):
                    return url
    except Exception as e:
        xbmc.log(f'[Samus/HydraHD] resolve_embed {embed_url}: {e}', xbmc.LOGWARNING)
    return None


def _resolve_all(sources):
    """Resolve embed URLs in parallel."""
    lock = threading.Lock()
    resolved = []

    def _worker(src):
        entry = dict(src)
        direct_url = _resolve_embed(src['url'])
        if direct_url:
            entry['url']    = direct_url
            entry['direct'] = True
        with lock:
            resolved.append(entry)

    threads = [threading.Thread(target=_worker, args=(s,)) for s in sources]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=12)
    return resolved


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    imdb = imdb_id or ''
    tmdb = str(tmdb_id)

    if media_type == 'movie':
        url = f'{_BASE}/ajax/mov_0.php?i={imdb}&t={tmdb}'
    else:
        url = f'{_BASE}/ajax/tv_0.php?i={imdb}&t={tmdb}&s={season}&e={episode}'

    html = _fetch(url)
    if not html:
        return []

    sources = _parse_mirrors(html)
    if not sources:
        xbmc.log(f'[Samus/HydraHD] Fără mirror-uri pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        return []

    resolved = _resolve_all(sources)
    direct_count = sum(1 for s in resolved if s.get('direct'))
    xbmc.log(f'[Samus/HydraHD] {direct_count}/{len(sources)} surse directe pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return resolved
