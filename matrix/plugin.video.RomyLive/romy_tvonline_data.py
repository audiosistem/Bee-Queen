# -*- coding: utf-8 -*-
"""TVOnline123 HTML parsing; site JavaScript is never executed."""
import json
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, parse_qs

SITE = 'https://www.tvonline123.eu'
JS_STRING = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''', re.S | re.X)


def js_unquote(value):
    """Decode JS literal escapes, including the envelope's legacy octal escapes."""
    value = value[1:-1]
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v'}
    pattern = r'\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[0-7]{1,3}|\r?\n|.)'

    def replace(match):
        token = match.group()[1:]
        if token.startswith(('x', 'u')) and len(token) in (3, 5):
            return chr(int(token[1:], 16))
        if re.fullmatch('[0-7]{1,3}', token):
            return chr(int(token, 8))
        if token in ('\n', '\r\n'):
            return ''
        return escapes.get(token, token)
    return re.sub(pattern, replace, value)


def decode_payload(payload):
    """Invert the site's byte permutation, not its arbitrary JS wrapper."""
    if len(payload) < 100 or not re.fullmatch('[0-9a-fA-F]{8}', payload[-8:]):
        raise ValueError('Not a supported HTML envelope')
    step, offset = int(payload[-4:-2], 16), int(payload[-2:], 16)
    if step % 2 != 1:
        raise ValueError('Invalid byte permutation')
    encoded = payload[:-8].replace('X', 'E').replace('x', 'E').replace('Y', 'B').replace('y', 'B')
    encoded = re.sub('[^0-9a-f]', '0', encoded, flags=re.I)
    table = {((offset + index * step) % 256): index for index in range(256)}
    raw = bytes((byte - table[index % 256]) % 256
                for index, byte in enumerate(bytes.fromhex(encoded)))
    return raw.decode('utf-8')


def expanded_html(html):
    """Read nested string literals with strict limits, never eval/exec."""
    if len(html) > 2 * 1024 * 1024:
        raise ValueError('Pagina TVOnline123 este prea mare')
    output = [html]
    queue = [html]
    seen = {html}
    for _ in range(4):
        following = []
        for text in queue:
            for match in JS_STRING.finditer(text):
                if len(match.group()) < 100:
                    continue
                value = js_unquote(match.group())
                if value in seen:
                    continue
                seen.add(value)
                if len(seen) > 300:
                    raise ValueError('Prea multe blocuri in pagina TVOnline123')
                if len(value) > 500 and re.fullmatch('[0-9a-fA-F]{8}', value[-8:]):
                    try:
                        decoded = decode_payload(value)
                        if '<' in decoded and '>' in decoded:
                            output.append(decoded)
                            following.append(decoded)
                            continue
                    except (ValueError, UnicodeError):
                        pass
                if '_CotG' in value or '<script' in value:
                    following.append(value)
        queue = following
        if not queue:
            break
    return '\n'.join(output)


class CatalogParser(HTMLParser):
    def __init__(self, base=SITE, category=''):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.category = category
        self.categories = []
        self.channels = []
        self.anchor = None
        self.heading = False
        self.heading_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h2':
            self.heading = True
            self.heading_text = []
        if tag == 'a':
            href = unescape(attrs.get('href', ''))
            path = urlparse(href).path
            if path.startswith('/categoria/') or path.startswith('/tvlive/'):
                self.anchor = {'href': urljoin(self.base, href), 'title': attrs.get('title', ''),
                               'text': [], 'image': '', 'category': self.category}
        elif tag == 'img' and self.anchor:
            self.anchor['image'] = urljoin(self.base, attrs.get('data-src') or attrs.get('src', ''))

    def handle_data(self, data):
        if self.heading:
            self.heading_text.append(data)
        if self.anchor:
            self.anchor['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'h2' and self.heading:
            label = ' '.join(''.join(self.heading_text).split())
            if label:
                self.category = label
            self.heading = False
        if tag != 'a' or not self.anchor:
            return
        anchor = self.anchor
        self.anchor = None
        path = urlparse(anchor['href']).path
        title = ' '.join((anchor['title'] or ''.join(anchor['text'])).split())
        if path.startswith('/categoria/'):
            title = re.sub(r'^Categoria\s+', '', title, flags=re.I)
            title = re.sub(r'\s+\d+$', '', title)
            if title.lower() == 'vezi toate':
                title = self.category
            if title and not any(c['url'] == anchor['href'] for c in self.categories):
                self.categories.append({'name': title, 'url': anchor['href']})
        else:
            slug = parse_qs(urlparse(anchor['href']).query).get('url', [''])[0]
            if not slug or not re.fullmatch(r'[a-zA-Z0-9_-]+', slug):
                return
            title = re.sub(r'\s+Online(?:\s+.*)?$', '', title, flags=re.I)
            if title and not any(c['slug'] == slug and c['category'] == anchor['category'] for c in self.channels):
                self.channels.append({'name': title, 'slug': slug, 'url': anchor['href'],
                                      'image': anchor['image'], 'category': anchor['category']})


def parse_catalog(html, base=SITE, category=''):
    parser = CatalogParser(base, category)
    parser.feed(html)
    return parser.categories, parser.channels


def parse_sources(html):
    text = expanded_html(html)
    sources = []
    for match in re.finditer(r'\b(?:const|let|var)\s+sources\s*=\s*(\[)', text):
        try:
            values, _ = json.JSONDecoder().raw_decode(text[match.start(1):])
            if isinstance(values, list):
                sources.extend(v for v in values if isinstance(v, dict))
        except ValueError:
            continue
    for match in re.finditer(r'''data-source\s*=\s*(["'])(.*?)\1''', text, re.S):
        try:
            value = json.loads(unescape(match.group(2)))
            if isinstance(value, dict):
                sources.append(value)
        except ValueError:
            continue
    result = []
    for source in sources:
        url = source.get('source_url', '')
        if isinstance(url, str) and urlparse(url).scheme in ('http', 'https'):
            if not any(s['source_url'] == url for s in result):
                result.append(source)
    return sorted(result, key=lambda s: int(s.get('priority') or 0))