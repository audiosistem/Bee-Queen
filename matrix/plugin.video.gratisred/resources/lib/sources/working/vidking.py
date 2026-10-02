import base64
import json
import time
from six.moves.urllib_parse import parse_qs, urlencode

from resources.lib.modules import client
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils


API = 'https://api.speedracelight.com'
PROVIDERS = (
    ('cdn/sources-with-title', 'Yoru'),
    ('downloader2/sources-with-title', 'Cypher'),
    ('m4uhd/sources-with-title', 'Breach'),
    ('vsrc/sources-with-title', 'Neon'),
    ('hdmovie/sources-with-title', 'Vyse'),
    ('superflix/sources-with-title', 'Raze'),
)
_MIX = 2654435769
_PREFIX = b'mvm1'


def _uint(value):
    return value & 0xffffffff


def _mix(value):
    value = _uint(value)
    value ^= value >> 16
    value = _uint(value * 2246822507)
    value ^= value >> 13
    value = _uint(value * 3266489909)
    return _uint(value ^ (value >> 16))


def _rotate(value, amount):
    value = _uint(value)
    amount &= 31
    return value if not amount else _uint((value << amount) | (value >> (32 - amount)))


def _fnv(value):
    result = 2166136261
    for char in value:
        result = _uint((result ^ ord(char)) * 16777619)
    return _mix(result)


def _keystream(seed, media_id, length):
    state = {}
    accumulator = _mix(_fnv(seed) ^ _mix(_uint(media_id) ^ _MIX))
    for counter in range(8):
        slot = accumulator % 61
        accumulator = _rotate(accumulator + _MIX, 7 + (counter & 7))
        state[slot] = _uint(accumulator ^ _mix(accumulator))
        accumulator = _mix(accumulator + slot)
    accumulator = _mix(accumulator ^ 2779096485)
    output = bytearray()
    for counter in range((length + 3) // 4):
        slot = accumulator % 61
        value = state.get(slot, 0)
        delta = _uint(_MIX * (counter + 1))
        present = -1 if slot in state else 0
        value = _uint((accumulator ^ (value ^ delta)) | (accumulator & present))
        value = _uint(_rotate(value + accumulator, slot & 31) ^ _rotate(accumulator, (slot * 7) & 31))
        accumulator = _mix(value + _MIX)
        state[slot] = accumulator
        output.extend(accumulator.to_bytes(4, 'little'))
    return output[:length]


def _decrypt(payload, seed, media_id):
    encoded = payload.replace('-', '+').replace('_', '/')
    encoded += '=' * ((4 - len(encoded) % 4) % 4)
    encrypted = bytearray(base64.b64decode(encoded))
    stream = _keystream(seed, media_id, len(encrypted))
    decrypted = bytes(value ^ stream[index] for index, value in enumerate(encrypted))
    if not decrypted.startswith(_PREFIX):
        raise ValueError('prefix')
    return json.loads(decrypted[len(_PREFIX):].decode('utf-8'))


class source:
    def __init__(self):
        self.results = []
        self.domains = ['api.speedracelight.com', 'vidking.net']
        self.base_link = 'https://api.speedracelight.com'
        self.headers = {
            'User-Agent': client.UserAgent,
            'Referer': 'https://www.vidking.net/',
            'Origin': 'https://www.vidking.net',
        }


    def movie(self, imdb, tmdb, title, localtitle, aliases, year):
        if not str(tmdb or '').isdigit():
            return
        return urlencode({
            'tmdb': tmdb, 'imdb': imdb or '', 'title': title or localtitle or '',
            'year': year or '', 'media': 'movie',
        })


    def tvshow(self, imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
        if not str(tmdb or '').isdigit():
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
            if not tmdb or not tmdb.isdigit():
                return self.results
            kind = 'tv' if data.get('media') == 'tv' else 'movie'
            if kind == 'tv' and (not data.get('season') or not data.get('episode')):
                return self.results
            seed_raw = client.request('%s/seed?mediaId=%s' % (API, tmdb), headers={'User-Agent': client.UserAgent}, timeout='12')
            if not seed_raw:
                return self.results
            seed = json.loads(seed_raw).get('seed') or ''
            if not seed:
                return self.results
            common = {
                'title': data.get('title') or '',
                'mediaType': kind,
                'year': data.get('year') or '',
                'episodeId': str(data.get('episode') or 1),
                'seasonId': str(data.get('season') or 1),
                'tmdbId': tmdb,
                'imdbId': data.get('imdb') or '',
                'enc': '2',
                'seed': seed,
            }
            for endpoint, name in PROVIDERS:
                self._provider(hostDict, endpoint, name, common, seed, int(tmdb))
            return self.results
        except Exception:
            return self.results


    def _provider(self, hostDict, endpoint, name, common, seed, media_id):
        try:
            query = dict(common)
            query['_t'] = str(time.time_ns() // 1000000)
            raw = client.request('%s/%s?%s' % (API, endpoint, urlencode(query)), headers={
                'User-Agent': client.UserAgent,
                'Cache-Control': 'no-cache',
            }, timeout='15')
            if not raw:
                return
            payload = _decrypt(raw, seed, media_id)
            for row in payload.get('sources') or []:
                if not isinstance(row, dict):
                    continue
                link = row.get('url') or ''
                if not isinstance(link, str) or not link.startswith('http'):
                    continue
                headers = dict(self.headers)
                if isinstance(row.get('headers'), dict):
                    for key, value in row['headers'].items():
                        if isinstance(key, str) and isinstance(value, (str, int, float)):
                            headers[key] = str(value)
                play = link + source_utils.append_headers(headers)
                item = scrape_sources.make_direct_item(hostDict, play, host='Direct', info='VidKing %s' % name)
                if item.get('url') and not scrape_sources.check_host_limit(item['source'], self.results):
                    self.results.append(item)
                    return
        except Exception:
            return


    def resolve(self, url):
        return url
