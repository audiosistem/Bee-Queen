# -*- coding: utf-8 -*-
"""ThraxTV VaVoo protocol adapter (reference addon GPL-2.0-only).

Signature from Thrax; stream resolution on the Kodi machine, not a remote
proxy. Default playback is the raw API URL, exactly as in ThraxTV.
"""
import http.client
import json
import re
import ssl
from urllib.parse import urlparse, urlencode, parse_qs

SIG_ENDPOINT = 'https://api.derzis.xyz/livetv/vavoo/sig'
RESOLVE_ENDPOINT = 'https://vavoo.to/mediahubmx-resolve.json'


class ResolveHTTPError(IOError):
    def __init__(self, status):
        self.status = status
        super().__init__('HTTP %s' % status)


def configure_thrax_item(item):
    item.setContentLookup(False)
    item.setProperty('IsPlayable', 'true')
    # Thrax VaVoo path is handled natively: no ISA or forced MIME type.


def channel_id(value):
    value = str(value or '').strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        return value
    return ''


def playback_url(target, headers):
    # Unlike 3.3.12/13, do not invent VAVOO/2.6, Referer or Origin.
    if not headers:
        return target
    base, _, tail = target.partition('|')
    merged = {key: values[-1] for key, values in parse_qs(tail).items()}
    for key, value in headers.items():
        if value is not None and key.lower() not in {name.lower() for name in merged}:
            merged[key] = str(value)
    return base + '|' + urlencode(merged)


def post_resolve(body, signature, timeout=12):
    parsed = urlparse(RESOLVE_ENDPOINT)
    payload = json.dumps(body).encode('utf-8')
    headers = {'User-Agent': 'MediaHubMX/2', 'Accept': 'application/json',
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': str(len(payload)), 'mediahubmx-signature': signature}
    connection = http.client.HTTPSConnection(parsed.netloc, timeout=timeout,
        context=ssl.create_default_context())
    try:
        connection.request('POST', parsed.path, body=payload, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ResolveHTTPError(response.status)
        data = response.read(1048577)
        if len(data) > 1048576:
            raise ValueError('Resolve response too large')
        return json.loads(data)
    finally:
        connection.close()


class ThraxClient:
    def __init__(self, session, device, log=lambda msg: None, post=post_resolve,
                 cancelled=lambda: False):
        self.session, self.device, self.log, self.post = session, device, log, post
        self.cancelled = cancelled
        self.signature, self.reason = '', ''

    def auth(self, refresh=False):
        if self.signature and not refresh:
            return self.signature
        self.signature = ''
        for _ in range(2):
            if self.cancelled():
                self.reason = 'Operatie VaVoo anulata.'
                return ''
            headers = self.device.headers()
            if not headers:
                self.reason = 'Inregistrarea anonima Thrax a esuat.'
                return ''
            response = None
            try:
                response = self.session.get(SIG_ENDPOINT, headers=headers, timeout=(4, 10))
                if response.status_code == 401:
                    self.device.forget()
                    continue
                if response.status_code != 200:
                    self.reason = 'Serviciul de semnatura Thrax raspunde HTTP %s.' % response.status_code
                    self.log(self.reason)
                    return ''
                signature = response.json().get('sig')
                if isinstance(signature, str) and signature:
                    self.signature = signature
                    self.log('Semnatura Thrax obtinuta; rezolvarea video se face LOCAL.')
                    return signature
                self.reason = 'Serviciul Thrax nu a returnat semnatura.'
                return ''
            except Exception as exc:
                self.reason = 'Semnatura Thrax: %s.' % type(exc).__name__
                self.log(self.reason)
                return ''
            finally:
                if response is not None:
                    response.close()
        self.reason = 'Tokenul anonim Thrax nu a fost acceptat.'
        return ''

    def resolve(self, cid):
        cid = channel_id(cid)
        if not cid:
            self.reason = 'ID VaVoo invalid.'
            return ''
        for attempt in range(2):
            signature = self.auth(refresh=bool(attempt))
            if not signature or self.cancelled():
                return ''
            body = {'language': 'de', 'region': 'AT',
                'url': 'https://vavoo.to/vavoo-iptv/play/' + cid, 'clientVersion': '3.0.2'}
            try:
                data = self.post(body, signature)
                from romy_vavoo import stream_candidates
                for target, headers in stream_candidates(data):
                    self.reason = ''
                    self.log('Resolve local HTTP 200; URL predat direct, fara preflight sau antete inventate.')
                    return playback_url(target, headers)
                self.reason = 'API VaVoo nu a returnat URL video.'
            except Exception as exc:
                # Do not include exception bodies/URLs/signatures in logs.
                detail = 'HTTP %s' % exc.status if isinstance(exc, ResolveHTTPError) else type(exc).__name__
                self.reason = 'Resolve VaVoo local: %s.' % detail
                self.log(self.reason)
        return ''