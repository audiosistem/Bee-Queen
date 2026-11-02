import hashlib
import hmac
import json
import os
from six.moves.urllib_parse import parse_qs, urlencode, urlparse

from resources.lib.modules.aesgcm import AES, _gctr, _ghash, aes_gcm_decrypt
from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


API_URL = 'https://api.wing.st'
HEADERS = {
    'User-Agent': client.UserAgent,
    'Referer': 'https://cinejoy.pk/',
    'Origin': 'https://cinejoy.pk',
}
SERVERS = ('Nebula', 'Lisbon', 'Athens')
# Public server key from Cinejoy crush.wasm (2026-10-11).
_PUBLIC = bytes.fromhex(
    '045c88a0ae33c683a4872590b04b22f4774a4fe1c6ecf74785c74a919a71207ca94'
    'f9e6b5a7854c3aa3b44ee46bc444fea694b9f23bcd80f864ecbef48c1ef6e14')
_KEY_ID = 2
_PREFIX = b'lumen-gate-v2'
_P = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
_N = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
_G = (0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296,
      0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5)


def _add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x, y = left
    u, v = right
    if x == u and (y + v) % _P == 0:
        return None
    numerator, denominator = ((3 * x * x - 3, 2 * y) if left == right
                              else (v - y, u - x))
    slope = numerator * pow(denominator % _P, _P - 2, _P) % _P
    result_x = (slope * slope - x - u) % _P
    return result_x, (slope * (x - result_x) - y) % _P


def _multiply(scalar, point):
    result = None
    while scalar:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _hkdf(shared, public, direction):
    prk = hmac.new(public, shared, hashlib.sha256).digest()
    return hmac.new(prk, _PREFIX + b'|' + direction + b'\x01', hashlib.sha256).digest()


def _encrypt(key, nonce, plaintext, aad):
    aes = AES(key)
    initial = nonce + b'\x00\x00\x00\x01'
    ciphertext = _gctr(aes, nonce + b'\x00\x00\x00\x02', plaintext)
    tag = _ghash(int.from_bytes(aes.encrypt_block(b'\x00' * 16), 'big'), aad, ciphertext)
    tag = bytes(x ^ y for x, y in zip(tag, aes.encrypt_block(initial)))
    return ciphertext + tag


def _seal(path, payload, entropy=None):
    entropy = os.urandom(44) if entropy is None else entropy
    counter = 0
    while True:
        digest = hashlib.sha256(_PREFIX + b'|ephemeral|' + entropy[:32]
                                + counter.to_bytes(4, 'big')).digest()
        scalar = int.from_bytes(digest, 'big')
        if 0 < scalar < _N:
            break
        counter += 1
    x, y = _multiply(scalar, _G)
    public = b'\x04' + x.to_bytes(32, 'big') + y.to_bytes(32, 'big')
    remote = (int.from_bytes(_PUBLIC[1:33], 'big'), int.from_bytes(_PUBLIC[33:], 'big'))
    shared = _multiply(scalar, remote)[0].to_bytes(32, 'big')
    request_key = _hkdf(shared, public, b'c2s')
    response_key = _hkdf(shared, public, b's2c')
    plaintext = json.dumps({'path': path, 'payload': payload},
                           separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    aad = _PREFIX + bytes((0, 1, _KEY_ID)) + public
    body = bytes((2, _KEY_ID)) + public + entropy[32:] + _encrypt(
        request_key, entropy[32:], plaintext, aad)
    return body, response_key, public


def _request(path, payload):
    body, key, public = _seal(path, payload)
    headers = dict(HEADERS)
    headers['Content-Type'] = 'application/octet-stream'
    encrypted = client.request(API_URL + '/g', post=body, headers=headers, timeout='20', as_bytes=True)
    if not encrypted:
        return None
    aad = _PREFIX + bytes((0, 2, _KEY_ID)) + public
    decoded = aes_gcm_decrypt(key, encrypted[:12], encrypted[12:], aad)
    return json.loads(decoded.decode('utf-8'))


def _media_url(value):
    if not isinstance(value, str) or not value.startswith('http'):
        return False
    try:
        parts = urlparse(value)
        return parts.scheme in ('http', 'https') and bool(parts.hostname)
    except Exception:
        return False


class source:
    def __init__(self):
        self.results = []
        self.domains = ['cinejoy.pk', 'api.wing.st']
        self.base_link = 'https://cinejoy.pk'
        self.headers = dict(HEADERS)


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
            return
        return urlencode({'tmdb': tmdb, 'media': 'movie'})


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not str(tmdb or '').isdigit() or str(tmdb) in ('0', 'None'):
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
            tmdb = str(data.get('tmdb') or '')
            if not tmdb.isdigit():
                return self.results
            media = data.get('media') or 'movie'
            payload = {'tmdb': tmdb}
            if media == 'tv':
                if not data.get('season') or not data.get('episode'):
                    return self.results
                payload['season'] = str(data['season'])
                payload['episode'] = str(data['episode'])
            kind = 'movie' if media != 'tv' else 'series'
            for server in SERVERS:
                self._server(hostDict, server, kind, payload)
            return self.results
        except Exception:
            return self.results


    def _server(self, hostDict, server, kind, payload):
        try:
            data = _request('/%s/%s' % (server, kind), payload)
            if not isinstance(data, dict) or data.get('status') != 200:
                return
            result = data.get('data')
            rows = result.get('stream') if isinstance(result, dict) else None
            if not isinstance(rows, list):
                return
            for row in rows:
                if not isinstance(row, dict):
                    continue
                link = row.get('playlist')
                if row.get('type') == 'file' and isinstance(row.get('qualities'), dict):
                    qualities = row['qualities']
                    ranked = sorted(qualities, key=lambda quality: int(quality) if str(quality).isdigit() else 0, reverse=True)
                    link = next((qualities[quality].get('url') for quality in ranked
                                 if isinstance(qualities.get(quality), dict)
                                 and _media_url(qualities[quality].get('url'))), None)
                if not _media_url(link):
                    continue
                play = link + source_utils.append_headers(self.headers)
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='Cinejoy %s' % server)
                if item.get('url') and item['url'] not in [row.get('url') for row in self.results]:
                    if not scrape_sources.check_host_limit(item['source'], self.results):
                        self.results.append(item)
        except Exception:
            return


    def resolve(self, url):
        return url
