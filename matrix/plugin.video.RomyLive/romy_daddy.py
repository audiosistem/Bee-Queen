# -*- coding: utf-8 -*-
"""DaddyLive resolver: all channel IDs, standard HLS only.

Player variants and public econfig format reviewed against MandraKodi's
daddyCode implementation (ElSupremo and supporters, GPL reference archive).
No imported Mandra UI, Italian allowlist, scripts, or external proxy service.
"""
import base64
import html
import json
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

ORIGINS = ('https://dlive.sx', 'https://dlhd.st', 'https://dlstreams.st', 'https://dlhd.pk')
PLAYERS = ('stream', 'cast', 'watch', 'plus', 'casting', 'player', 'hub')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'


def channel_id(value):
    value = str(value or '').strip()
    if re.fullmatch(r'\d+', value):
        return value
    parsed = urlparse(value)
    candidate = parse_qs(parsed.query).get('id', [''])[0]
    if re.fullmatch(r'\d+', candidate):
        return candidate
    match = re.search(r'/stream-(\d+)\.php', parsed.path)
    return match.group(1) if match else ''


def decode_config(encoded):
    try:
        raw = base64.b64decode(encoded).decode('latin1')
        size = (len(raw) + 3) // 4
        restored = [''] * 4
        for index, position in enumerate((2, 0, 3, 1)):
            part = raw[index * size:(index + 1) * size]
            if len(part) < 4:
                return ''
            restored[position] = base64.b64decode(part[:3] + part[4:]).decode('latin1')
        cfg = json.loads(base64.b64decode(''.join(restored)).decode('utf-8'))
        return cfg.get('stream_url') or cfg.get('stream_url_nop2p') or ''
    except (ValueError, UnicodeError, AttributeError):
        return ''


def sources(page, base):
    values = []
    for encoded in re.findall(r'window\._econfig\s*=\s*["\']([^"\']+)', page, re.I):
        values.append(decode_config(encoded))
    for encoded in re.findall(r'(?:window\.)?atob\(\s*["\']([A-Za-z0-9+/=_-]+)["\']\s*\)', page):
        try:
            values.append(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8'))
        except (ValueError, UnicodeError):
            pass
    values.extend(re.findall(r'(?:const|let|var)\s+SRC\s*=\s*["\']([^"\']+)', page))
    values.extend(re.findall(r'https?://[^\s\'"<>\\]+\.m3u8[^\s\'"<>\\]*', page.replace('\\/', '/')))
    seen = set()
    for value in values:
        value = html.unescape(value).replace('\\/', '/').strip()
        if not value:
            continue
        value = urljoin(base, value)
        if urlparse(value).scheme in ('https', 'http') and '.m3u8' in value and value not in seen:
            seen.add(value)
            yield value


def unsupported_playlist(body):
    low = body[:16000].lower()
    return any(word in low for word in ('hackerman', 'null367', 'tiktokcdn')) or bool(
        re.search(r'^\s*[^#\s][^\r\n]*\.png(?:[?\r\n]|$)', low, re.M))


class Resolver:
    def __init__(self, session, log=lambda message: None, cancelled=lambda: False, budget=90):
        self.session, self.log, self.cancelled = session, log, cancelled
        self.deadline = time.monotonic() + budget
        self.reason = ''

    def get(self, url, referer):
        if self.cancelled() or time.monotonic() >= self.deadline:
            return None
        origin = urlparse(referer)
        try:
            response = self.session.get(url, headers={'User-Agent': UA, 'Accept': '*/*',
                'Referer': referer, 'Origin': origin.scheme + '://' + origin.netloc},
                timeout=min(6, max(0.1, self.deadline - time.monotonic())))
            if response.status_code == 200:
                return response
            self.log('HTTP %s: %s' % (response.status_code, urlparse(url).hostname))
        except Exception as exc:
            self.log('Cerere %s: %s' % (urlparse(url).hostname, type(exc).__name__))
        return None

    def validate(self, target, referer, depth=0):
        response = self.get(target, referer)
        if response is None:
            return False
        body = response.text
        if not body.lstrip('﻿ \r\n').startswith('#EXTM3U'):
            return False
        if unsupported_playlist(body):
            self.reason = 'Playlist PNG-HLS incompatibil cu playerul Kodi standard.'
            return False
        # Master may be clean while its media playlist contains PNG wrappers.
        if '#EXT-X-STREAM-INF' in body:
            if depth >= 2:
                return False
            variants = re.findall(r'#EXT-X-STREAM-INF[^\r\n]*\r?\n\s*([^#\s][^\r\n]*)', body)
            return bool(variants) and all(self.validate(urljoin(response.url, item.strip()), referer, depth + 1)
                                          for item in variants[:8])
        return bool(re.search(r'#EXTINF|#EXT-X-PART:', body))

    def resolve_page(self, url, referer, depth=0, seen=None):
        seen = seen if seen is not None else set()
        if depth > 3 or url in seen:
            return ''
        seen.add(url)
        response = self.get(url, referer)
        if response is None:
            return ''
        page_url = response.url
        parsed = urlparse(page_url)
        context = parsed.scheme + '://' + parsed.netloc + '/'
        for candidate in sources(response.text, page_url):
            if self.validate(candidate, context):
                headers = {'User-Agent': UA, 'Referer': context, 'Origin': context.rstrip('/')}
                try:
                    import requests
                    cookie = self.session.prepare_request(requests.Request('GET', candidate)).headers.get('Cookie')
                    if cookie:
                        headers['Cookie'] = cookie
                except Exception:
                    pass
                return candidate + '|' + urlencode(headers)
        for frame in re.findall(r'<iframe\b[^>]*\bsrc\s*=\s*["\']([^"\']+)', response.text, re.I):
            target = urljoin(page_url, html.unescape(frame))
            if urlparse(target).scheme not in ('https', 'http') or 'adbanner' in target.lower():
                continue
            stream = self.resolve_page(target, page_url, depth + 1, seen)
            if stream:
                return stream
        return ''

    def resolve(self, value):
        cid = channel_id(value)
        if not cid:
            self.reason = 'ID DaddyLive invalid.'
            return ''
        for origin in ORIGINS:
            for player in PLAYERS:
                if self.cancelled() or time.monotonic() >= self.deadline:
                    self.reason = self.reason or 'Rezolvare anulata sau timpul de conectare a expirat.'
                    return ''
                stream = self.resolve_page('%s/%s/stream-%s.php' % (origin, player, cid), origin + '/')
                if stream:
                    self.log('Canal %s: player %s, origine %s; playlist HLS verificat.' % (cid, player, origin))
                    return stream
        self.reason = self.reason or 'Nu am gasit un playlist HLS accesibil pentru acest canal.'
        return ''


def install(ns):
    import requests
    import xbmc
    import xbmcgui
    import xbmcplugin

    def log(message):
        xbmc.log('[RomyLive DaddyLive] ' + message, xbmc.LOGINFO)

    def resolve(value):
        with requests.Session() as session:
            monitor = xbmc.Monitor()
            resolver = Resolver(session, log, monitor.abortRequested)
            stream = resolver.resolve(value)
            if not stream:
                log(resolver.reason)
            return stream

    def play(name, value, iconimage=None, description=None, subtitle=None):
        stream = resolve(value)
        item = xbmcgui.ListItem(label=name or 'DaddyLive', path=stream)
        if not stream:
            ns['notify']('[COLOR red]Stream DaddyLive indisponibil. Vezi kodi.log.[/COLOR]')
            xbmcplugin.setResolvedUrl(ns['addon_handle'], False, item)
            return
        item.setArt({'thumb': iconimage or ns.get('thumb_daddylive', '')})
        item.setProperty('IsPlayable', 'true')
        item.setContentLookup(False)
        item.setMimeType('application/vnd.apple.mpegurl')
        item.setProperty('inputstream', 'inputstream.adaptive')
        headers = stream.split('|', 1)[1]
        item.setProperty('inputstream.adaptive.manifest_headers', headers)
        item.setProperty('inputstream.adaptive.stream_headers', headers)
        if subtitle:
            item.setSubtitles([subtitle])
        from romy_audio import mark_playback
        mark_playback(stream, name or 'DaddyLive')
        xbmcplugin.setResolvedUrl(ns['addon_handle'], True, item)

    ns['daddylive_resolve_stream'] = resolve
    ns['daddylive_play'] = play
    log('Resolver activ pentru toate ID-urile; fara restrictie de tara.')