# -*- coding: utf-8 -*-
"""Stigstream.ru source resolver — protocol v3 (2026-05).

Stigstream rotated their API at the start of May 2026, breaking v1.4.14.
The new protocol (v3 envelope) adds:
  * Required ``X-Api-Key`` header on every request (constant, embedded in
    the site JS bundle ``d7895779bf7f4af6.js``).
  * Optional rolling ``X-Request-Token``: each response includes an
    ``X-Next-Token`` header whose value must be sent as ``X-Request-Token``
    on the *next* request. The TOKEN SENT also participates in the HKDF
    salt for that response's envelope decryption.
  * New envelope fields ``{v:"3", a, b, c, k}``:
      a = 12-byte AES-GCM IV (hex, 24 chars)
      b = 16-byte AES-GCM auth tag (hex, 32 chars)
      c = AES-GCM ciphertext (hex)
      k = 32-byte per-response salt (hex, 64 chars)
  * HKDF salt = (request-token-bytes || k-bytes) when token present, else k.
  * AES-GCM plaintext is JSON ``{x,y,z}`` = (cc_iv, cc_tag, cc_ct) hex.
  * Inner ChaCha20-Poly1305 decrypt yields the final stream JSON.

Master keys (extracted from the site JS):
  * api_key      = 0cb4683fa6eb...4657c2  -> X-Api-Key header
  * encrypt_key  = e249eabfa7abb1...1c337e  -> HKDF master for envelope
  * HKDF info(AES) = b"3b8e1f5c9a2d6f0e4c7b3a8d1f9e5c2a"
  * HKDF info(CC)  = b"9f2c7e4b1d8a3f6c0e5b9d2a7f4c1e8b"
  * HKDF hash      = SHA-512

Endpoints:
  GET  https://api.stigstream.ru/servers
  GET  https://api.stigstream.ru/movie/{server}/{tmdb}
  GET  https://api.stigstream.ru/tv/{server}/{tmdb}/{season}/{episode}
"""
import hashlib
import hmac
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .common import log

API = 'https://api.stigstream.ru'
SITE = 'https://stigstream.ru'
TIMEOUT = 25

API_KEY = '0cb4683fa6eb666bf70712b57e0110adf4a173bd45110869b19c298b724657c2'
_MASTER_HEX = 'e249eabfa7abb1c062c988527e0eedab088ac9c2b495acba8120666a651c337e'
_AES_INFO = b'3b8e1f5c9a2d6f0e4c7b3a8d1f9e5c2a'
_CC_INFO = b'9f2c7e4b1d8a3f6c0e5b9d2a7f4c1e8b'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

_FALLBACK_SERVERS = ('Aqua', 'Nova', 'Vix', 'Nebula', 'Quartz',
                     'Obsidian', 'Onyx', 'Atlas')


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _hkdf_sha512(ikm, salt, info, length=32):
    h = hashlib.sha512
    if not salt:
        salt = b'\x00' * h().digest_size
    prk = hmac.new(salt, ikm, h).digest()
    out = b''
    t = b''
    counter = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), h).digest()
        out += t
        counter += 1
    return out[:length]


def _aesgcm_decrypt(key, iv, ct, tag):
    """Try fast C impls, fall back to embedded pure-Python."""
    try:
        from Crypto.Cipher import AES
        return AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(ct, tag)
    except ImportError:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM(key).decrypt(iv, ct + tag, None)
    except ImportError:
        pass
    from . import purecrypto
    return purecrypto.aes256_gcm_decrypt(key, iv, ct, tag)


def _chacha_decrypt(key, iv, ct, tag):
    try:
        from Crypto.Cipher import ChaCha20_Poly1305
        return ChaCha20_Poly1305.new(key=key, nonce=iv).decrypt_and_verify(ct, tag)
    except ImportError:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        return ChaCha20Poly1305(key).decrypt(iv, ct + tag, None)
    except ImportError:
        pass
    from . import purecrypto
    return purecrypto.chacha20_poly1305_decrypt(key, iv, ct, tag)


def _decrypt_v3(env, req_token):
    if env.get('v') != '3':
        raise ValueError('stigstream: unexpected envelope version: %r' % env.get('v'))
    master = bytes.fromhex(_MASTER_HEX)
    salt = b''
    if req_token:
        try:
            salt += bytes.fromhex(req_token)
        except ValueError:
            pass
    salt += bytes.fromhex(env['k'])
    aes_key = _hkdf_sha512(master, salt, _AES_INFO, 32)
    chacha_key = _hkdf_sha512(master, salt, _CC_INFO, 32)
    outer_pt = _aesgcm_decrypt(aes_key,
                               bytes.fromhex(env['a']),
                               bytes.fromhex(env['c']),
                               bytes.fromhex(env['b']))
    inner = json.loads(outer_pt)
    payload = _chacha_decrypt(chacha_key,
                              bytes.fromhex(inner['x']),
                              bytes.fromhex(inner['z']),
                              bytes.fromhex(inner['y']))
    return json.loads(payload)


def _is_available():
    """Stigstream is always usable — pure-Python crypto fallback ships with
    the addon."""
    return True


# ---------------------------------------------------------------------------
# Rolling-token aware HTTP client
# ---------------------------------------------------------------------------

class _StigClient(object):
    """Thread-safe wrapper that maintains the rolling X-Next-Token between
    requests. Each call returns (decrypted_payload, sent_token)."""

    def __init__(self):
        self._sess = requests.Session()
        self._sess.headers.update({
            'User-Agent': UA,
            'Accept': 'application/json',
            'Accept-Language': 'en-GB,en;q=0.9',
            # Avoid Brotli — pure-stdlib gzip/deflate only.
            'Accept-Encoding': 'gzip, deflate',
            'Origin': SITE,
            'Referer': SITE + '/',
            'X-Api-Key': API_KEY,
        })
        self._token = None
        self._lock = threading.Lock()

    def _read_token(self):
        with self._lock:
            return self._token

    def _write_token(self, t):
        with self._lock:
            if t:
                self._token = t

    def call(self, path):
        """GET ``path``, returns (data, status_code) or (None, status)."""
        sent_token = self._read_token()
        headers = {}
        if sent_token:
            headers['X-Request-Token'] = sent_token
        try:
            r = self._sess.get(API + path, headers=headers, timeout=TIMEOUT)
        except Exception as e:
            log('stigstream: GET %s network err: %s' % (path, e))
            return None, 0
        # Capture rotating token
        next_token = r.headers.get('X-Next-Token')
        if next_token:
            self._write_token(next_token)
        if r.status_code != 200:
            return None, r.status_code
        try:
            env = r.json()
        except ValueError:
            log('stigstream: %s -> non-JSON body' % path)
            return None, r.status_code
        try:
            return _decrypt_v3(env, sent_token), 200
        except Exception as e:
            log('stigstream: decrypt %s failed: %s' % (path, e))
            return None, r.status_code


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_servers(client=None):
    client = client or _StigClient()
    data, status = client.call('/servers')
    if not data:
        log('stigstream: /servers -> %s; using fallback list' % status)
        return [{'name': n} for n in _FALLBACK_SERVERS]
    if isinstance(data, dict):
        data = data.get('servers') or data.get('data') or []
    return [s for s in data if isinstance(s, dict) and s.get('status') == 'Working']


def resolve_streams(media_type, tmdb_id, season=None, episode=None):
    if not _is_available():
        return []
    if not tmdb_id:
        log('stigstream: tmdb_id required')
        return []

    client = _StigClient()
    # Initial /servers call seeds the rolling token AND tells us which servers
    # are reachable right now. The rolling token is shared via the client
    # instance below.
    servers = list_servers(client)
    log('stigstream: %d candidate servers' % len(servers))

    if media_type == 'movie':
        path_tmpl = '/movie/{srv}/{tmdb}'
    else:
        path_tmpl = '/tv/{srv}/{tmdb}/{s}/{e}'

    streams = []
    err_streak = {'count': 0}

    def _fetch(srv):
        name = srv.get('name')
        path = path_tmpl.format(srv=name, tmdb=tmdb_id,
                                s=season or 1, e=episode or 1)
        data, status = client.call(path)
        if not data:
            if status == 404:
                return []  # title genuinely not in this server's library
            err_streak['count'] += 1
            return []
        out = []
        for st in (data.get('streams') or []):
            su = st.get('url')
            if not su:
                continue
            label = '[%s] Stigstream • %s%s' % (
                st.get('quality') or 'Auto', name,
                ' (%s)' % srv['description'] if srv.get('description') else '')
            out.append({
                'url': su,
                'headers': {'User-Agent': UA, 'Referer': SITE + '/'},
                'label': label,
                'quality': st.get('quality') or 'Auto',
                'proto': 'HLS', 'host': 'stigstream.ru',
                'server': 'Stigstream %s' % name,
                'height': 0, 'bandwidth': 0,
                'provider': 'stigstream',
                'subtitles': data.get('subtitles') or [],
            })
        return out

    # NB: We cannot actually parallelise the rolling-token chain — every
    # response provides the salt for the next request. So requests must run
    # sequentially. Stigstream is fast (<300 ms per server) so 8 servers
    # complete in ~2 s total.
    for srv in servers:
        try:
            streams.extend(_fetch(srv))
        except Exception as e:
            log('stigstream: server %s err: %s' % (srv.get('name'), e))
        if err_streak['count'] >= 4:
            log('stigstream: aborting after 4 consecutive errors')
            break
    log('stigstream: resolved %d streams across %d servers'
        % (len(streams), len(servers)))
    return streams
