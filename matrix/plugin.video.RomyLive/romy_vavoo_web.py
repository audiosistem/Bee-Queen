# -*- coding: utf-8 -*-
"""Independent adapter for the public API used by vavoo.to/#/channels.

Observed endpoints: /live/catalog/live/channels.json and /live/resolve.
No third-party signature service, local device token or static signed URL.
"""
import re
from urllib.parse import urlparse, urljoin, urlencode, parse_qs

BASE = 'https://vavoo.to'
CATALOG = BASE + '/live/catalog/live/channels.json'
RESOLVE = BASE + '/live/resolve'
USER_AGENT = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36')
API_HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'application/json',
               'Referer': BASE + '/', 'Accept-Encoding': 'gzip, deflate'}


def numeric_id(value):
    value = str(value or '').strip()
    if re.fullmatch(r'\d{1,10}', value):
        return value
    # The legacy catalog ID is the numeric web ID + a 12-hex suffix.
    # Preserve old favorites, but do not accept arbitrary mixed IDs/URLs.
    match = re.fullmatch(r'(\d{1,10})[a-fA-F0-9]{12}', value)
    return match.group(1) if match else ''


def kodi_url(target, api_headers=None):
    base, _, tail = target.partition('|')
    headers = {key: values[-1] for key, values in parse_qs(tail).items()}
    for key, value in (api_headers or {}).items():
        if value is not None and key.lower() not in {name.lower() for name in headers}:
            headers[key] = str(value)
    for key, value in [('User-Agent', USER_AGENT), ('Referer', BASE + '/')]:
        if key.lower() not in {name.lower() for name in headers}:
            headers[key] = value
    return base + '|' + urlencode(headers)


def configure_web_item(item):
    item.setContentLookup(False)
    item.setProperty('IsPlayable', 'true')
    # Website provides ordinary HLS; keep the native player used in Kodi.


def map_channel(item):
    cid = str(item.get('id') or '')
    if not re.fullmatch(r'\d{1,10}', cid) or item.get('type') != 'live':
        return None
    expected = BASE + '/live/play/' + cid
    if item.get('url') != expected:
        return None
    tags = item.get('tags') or []
    images = item.get('images') if isinstance(item.get('images'), dict) else {}
    logo = images.get('logo') or ''
    return {'id': cid, 'url': expected, 'name': item.get('name') or 'VaVooTV',
        'country': tags[0] if isinstance(tags, list) and tags else 'default',
        'logo': urljoin(BASE, logo) if logo else '', 'p': 0}


class WebClient:
    def __init__(self, session, log=lambda message: None, cancelled=lambda: False):
        self.session, self.log, self.cancelled = session, log, cancelled
        self.reason = ''

    def get_json(self, endpoint, params):
        if self.cancelled():
            self.reason = 'Operatie VaVoo anulata.'
            return None
        response = None
        try:
            response = self.session.get(endpoint, params=params, headers=API_HEADERS, timeout=(5, 12))
            if response.status_code != 200:
                self.reason = 'API web VaVoo raspunde HTTP %s.' % response.status_code
                self.log(self.reason)
                return None
            data = response.json()
            if not isinstance(data, dict):
                self.reason = 'Raspuns API web VaVoo invalid.'
                return None
            return data
        except Exception as exc:
            self.reason = 'API web VaVoo: %s.' % type(exc).__name__
            self.log(self.reason)
            return None
        finally:
            if response is not None:
                response.close()

    def catalog(self):
        channels, seen_ids, seen_cursors = [], set(), set()
        cursor = None
        for _ in range(100):
            params = {'region': 'US', 'language': 'en', 'sort': 'name'}
            if cursor is not None:
                params['cursor'] = cursor
            data = self.get_json(CATALOG, params)
            if data is None:
                return []  # Never cache a truncated catalog as complete.
            if not isinstance(data.get('items'), list):
                self.reason = 'Catalogul web VaVoo nu contine lista de canale.'
                return []
            for item in data['items']:
                mapped = map_channel(item) if isinstance(item, dict) else None
                if mapped and mapped['id'] not in seen_ids:
                    channels.append(mapped)
                    seen_ids.add(mapped['id'])
            cursor = data.get('nextCursor')
            if cursor is None or cursor == '':
                self.log('Catalog web VaVoo: %s canale, ID-uri numerice.' % len(channels))
                self.reason = ''
                return channels
            cursor = str(cursor)
            if cursor in seen_cursors:
                self.reason = 'Catalog VaVoo: cursor repetat.'
                return []
            seen_cursors.add(cursor)
        self.reason = 'Catalog VaVoo: limita de pagini depasita.'
        return []

    def resolve(self, value):
        cid = numeric_id(value)
        if not cid:
            self.reason = 'ID web VaVoo invalid.'
            return ''
        if str(value) != cid:
            self.log('ID favorit vechi convertit la ID numeric web: %s.' % cid)
        data = self.get_json(RESOLVE, {'region': 'US', 'language': 'en',
            'url': BASE + '/live/play/' + cid})
        if data is None:
            return ''
        target = data.get('url')
        if not isinstance(target, str) or urlparse(target.split('|', 1)[0]).scheme not in ('http', 'https'):
            self.reason = 'API web VaVoo nu a returnat URL video.'
            return ''
        headers = data.get('headers') if isinstance(data.get('headers'), dict) else {}
        self.reason = ''
        self.log('Resolve web VaVoo HTTP 200; host %s; pornirea nu este confirmata.' %
                 urlparse(target.split('|', 1)[0]).hostname)
        return kodi_url(target, headers)