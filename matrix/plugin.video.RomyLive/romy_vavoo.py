# -*- coding: utf-8 -*-
"""Session-scoped VaVoo resolution, auth refresh and explicit playback errors."""
import os
import time
from urllib.parse import urlparse, urljoin, urlencode, parse_qs


def stream_candidates(data):
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        target = item.get('url') or item.get('streamUrl') or ''
        if urlparse(target.split('|', 1)[0]).scheme in ('http', 'https'):
            yield target, item.get('headers') if isinstance(item.get('headers'), dict) else {}


def kodi_stream(target, headers):
    base, _, tail = target.partition('|')
    existing = {key: values[-1] for key, values in parse_qs(tail).items()}
    for key, value in headers.items():
        if key.lower() not in [name.lower() for name in existing]:
            existing[key] = str(value)
    if 'user-agent' not in [key.lower() for key in existing]:
        existing['User-Agent'] = 'VAVOO/2.6'
    for key, value in [('Referer', 'https://vavoo.to/'), ('Origin', 'https://vavoo.to')]:
        if key.lower() not in [name.lower() for name in existing]:
            existing[key] = value
    return base + '|' + urlencode(existing)


def configure_item(item, stream):
    # VaVoo supplies ordinary live HLS. Use Kodi's native demuxer rather
    # than forcing ISA, which failed OpenInputStream on the user's build.
    item.setContentLookup(False)
    base = stream.split('|', 1)[0]
    if '.m3u8' in urlparse(base).path.lower():
        item.setMimeType('application/vnd.apple.mpegurl')
    item.setProperty('IsPlayable', 'true')


class Client:
    def __init__(self, session, ns, log=lambda message: None, cancelled=lambda: False,
                 budget=60, clock=time.monotonic):
        self.session, self.ns, self.log = session, ns, log
        self.cancelled, self.clock = cancelled, clock
        self.deadline = clock() + budget
        self.signature = ''
        self.reason = ''

    def available(self):
        if self.cancelled():
            self.reason = 'Operatie VaVoo anulata.'
            return False
        if self.clock() >= self.deadline:
            self.reason = self.reason or 'Timpul de verificare VaVoo a expirat.'
            return False
        return True

    def timeout(self):
        remaining = max(0.1, self.deadline - self.clock())
        return min(4, remaining / 2), min(7, remaining / 2)

    def probe(self, stream, depth=0):
        """Check HTTP and media content before handing a signed URL to Kodi.

        A successful probe is not a playback guarantee: a live CDN may fail
        again after the check. Never log paths/tokens or dump error bodies.
        """
        if not self.available():
            return False
        base, _, tail = stream.partition('|')
        headers = {key: values[-1] for key, values in parse_qs(tail).items()}
        response = None
        host = urlparse(base).hostname
        try:
            response = self.session.get(base, headers=headers, timeout=self.timeout(), stream=True)
            if response.status_code != 200:
                self.reason = 'Serverul video VaVoo raspunde HTTP %s.' % response.status_code
                self.log('Verificare stream %s: HTTP %s.' % (host, response.status_code))
                return False
            media_type = response.headers.get('Content-Type', '').lower()
            is_hls = '.m3u8' in urlparse(base).path.lower() or 'mpegurl' in media_type
            limit = 65536 if is_hls else 1024
            content = bytearray()
            for chunk in response.iter_content(chunk_size=1024):
                if not self.available():
                    return False
                content.extend(chunk[:limit - len(content)])
                if len(content) >= limit:
                    break
            raw = bytes(content)
            if raw.lstrip(b'\xef\xbb\xbf \r\n').startswith(b'#EXTM3U'):
                lines = raw.decode('utf-8-sig', 'replace').strip().splitlines()
                if any(line.startswith('#EXTINF:') for line in lines) and any(
                        line.strip() and not line.startswith('#') for line in lines):
                    self.log('Verificare stream %s: playlist media HTTP 200.' % host)
                    self.reason = ''
                    return True
                if depth < 2:
                    for index, line in enumerate(lines):
                        if line.startswith('#EXT-X-STREAM-INF:'):
                            child = next((value.strip() for value in lines[index + 1:]
                                          if value.strip() and not value.startswith('#')), '')
                            target = urljoin(response.url or base, child)
                            if child and urlparse(target).scheme in ('http', 'https'):
                                return self.probe(kodi_stream(target, headers), depth + 1)
                self.reason = 'Serverul VaVoo nu a returnat un playlist media valid.'
            elif len(raw) >= 564 and all(raw[offset] == 0x47 for offset in (0, 188, 376)):
                self.log('Verificare stream %s: MPEG-TS HTTP 200.' % host)
                self.reason = ''
                return True
            else:
                self.reason = 'Serverul VaVoo a returnat continut non-video sau gol.'
            self.log('Verificare stream %s: continut media invalid.' % host)
        except Exception as exc:
            kind = type(exc).__name__
            self.reason = 'Verificarea serverului video VaVoo a esuat: %s.' % kind
            self.log('Verificare stream %s: %s.' % (host, kind))
        finally:
            if response is not None:
                response.close()
        return False

    def auth(self, refresh=False):
        if self.signature and not refresh:
            return self.signature
        self.signature = ''
        for endpoint in self.ns['vavoo_ping_urls']:
            if not self.available():
                return ''
            try:
                response = self.session.post(endpoint, json=self.ns['vavoo_ping_payload'](),
                    headers={'User-Agent': 'electron-fetch/1.0 electron', 'Accept': 'application/json'}, timeout=self.timeout())
                if response.status_code == 200:
                    self.signature = response.json().get('addonSig') or ''
                    if self.signature:
                        return self.signature
                self.log('Autorizare %s: HTTP %s, semnatura absenta.' %
                         (urlparse(endpoint).hostname, response.status_code))
            except Exception as exc:
                self.log('Autorizare: %s' % type(exc).__name__)
        self.reason = 'Autorizarea VaVoo nu a returnat o semnatura.'
        return ''

    def resolve(self, channel):
        source = channel.get('url') or ''
        if not source:
            self.reason = 'Canalul nu are URL de rezolvare in catalog.'
            return ''
        for attempt in range(2):
            if not self.available():
                break
            if attempt:
                self.log('Reincercare cu autorizare si rezolvare noi; incercarea anterioara a esuat.')
            signature = self.auth(refresh=bool(attempt))
            if not signature:
                break
            for base in self.ns['vavoo_base_sites']:
                if not self.available():
                    break
                try:
                    response = self.session.post(base.rstrip('/') + '/mediahubmx-resolve.json',
                        headers=self.ns['vavoo_catalog_headers'](signature),
                        json={'language': 'de', 'region': 'AT', 'url': source, 'clientVersion': '3.0.2'}, timeout=self.timeout())
                    if response.status_code != 200:
                        self.log('Resolve %s: HTTP %s' % (urlparse(base).hostname, response.status_code))
                        continue
                    had_candidate = False
                    for target, headers in stream_candidates(response.json()):
                        had_candidate = True
                        stream = kodi_stream(target, headers)
                        if self.probe(stream):
                            return stream
                        if not self.available():
                            break
                    if not had_candidate:
                        self.log('Resolve: raspuns fara URL video.')
                except Exception as exc:
                    self.log('Resolve: %s' % type(exc).__name__)
        self.reason = self.reason or 'API VaVoo nu a returnat un stream accesibil.'
        return ''


def install(ns):
    import requests
    import xbmc
    import xbmcgui
    import xbmcplugin
    logo = os.path.join(os.path.dirname(__file__), 'icon.png')
    ns['thumb_vavoo'] = logo

    def log(message):
        xbmc.log('[RomyLive VaVoo] ' + message, xbmc.LOGINFO)

    # Both the remote-inserted menu item and channel fallback art use a local
    # bundled logo, avoiding the unavailable vavoo.to favicon.
    original_add = ns.get('addDir')
    if original_add:
        def add(*args, **kwargs):
            args = list(args)
            if len(args) > 3 and (args[1] == ns.get('url_vavoo_main') or args[3] == 'https://vavoo.to/favicon.ico'):
                args[3] = logo
            return original_add(*args, **kwargs)
        ns['addDir'] = add

    def resolve(cid):
        ns['_romy_vavoo_reason'] = ''
        from romy_vavoo_web import WebClient
        with requests.Session() as session:
            monitor = xbmc.Monitor()
            client = WebClient(session, log, cancelled=monitor.abortRequested)
            stream = client.resolve(cid)
            ns['_romy_vavoo_reason'] = client.reason
            if not stream:
                log(client.reason)
            return stream

    def load_channels():
        cached = ns.get('_romy_vavoo_web_channels')
        if cached is not None:
            return cached
        from romy_vavoo_web import WebClient
        with requests.Session() as session:
            client = WebClient(session, log, cancelled=xbmc.Monitor().abortRequested)
            channels = client.catalog()
            if channels:
                ns['_romy_vavoo_web_channels'] = channels
            elif client.reason:
                log(client.reason)
            return channels

    def play(name, cid, iconimage=None, description=None, subtitle=None):
        stream = resolve(cid)
        item = xbmcgui.ListItem(label=name or 'VaVooTV', path=stream)
        if not stream:
            ns['notify']('[COLOR red]VaVooTV: %s[/COLOR]' %
                         ns.get('_romy_vavoo_reason', 'Canal indisponibil. Vezi kodi.log.'))
            xbmcplugin.setResolvedUrl(ns['addon_handle'], False, item)
            return
        item.setArt({'icon': logo, 'thumb': iconimage or logo})
        from romy_vavoo_web import configure_web_item
        configure_web_item(item)
        if subtitle:
            item.setSubtitles([subtitle])
        from romy_audio import mark_playback
        mark_playback(stream, name or 'VaVooTV')
        log('Predare catre playerul NATIV Kodi, host %s; pornirea nu este confirmata.' %
            urlparse(stream.split('|', 1)[0]).hostname)
        xbmcplugin.setResolvedUrl(ns['addon_handle'], True, item)

    ns['vavoo_stream_url'] = resolve
    ns['vavoo_play'] = play
    ns['vavoo_load_channels'] = load_channels
    log('Corectie activa: API SITE vavoo.to/live, catalog web, ID numeric, FARA Thrax, player NATIV.')