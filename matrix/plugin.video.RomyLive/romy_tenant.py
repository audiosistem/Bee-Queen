# -*- coding: utf-8 -*-
"""Public player API used by the three DeseneFaine tenant domains.

The AES transport format/key/IV are the same public format implemented by
ResolveURL's KinoGer resolver and the players' own downloaded JavaScript.
No DRM keys or login credentials are involved.
"""
import json
import re
from urllib.parse import urlparse, urljoin, urlencode

HOSTS = {'player4me.embed4me.com', 'streamp2p.p2pplay.online',
         'seeksreaming.embedseek.com'}


def decode_payload(text):
    try:
        return json.loads(text)
    except ValueError:
        pass
    from resolveurl.lib import pyaes
    # API response is hex-encoded AES-CBC followed by optional whitespace.
    encoded = re.match(r'^[0-9a-fA-F]+', text.strip())
    if not encoded or len(encoded.group()) % 2:
        raise ValueError('Raspuns API necunoscut')
    binary = bytes.fromhex(encoded.group())
    if not binary or len(binary) % 16:
        raise ValueError('Raspuns API incomplet')
    decrypt = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(
        b'kiemtienmua911ca', b'1234567890oiuytr'))
    plain = decrypt.feed(binary) + decrypt.feed()
    return json.loads(plain.decode('utf-8'))


def media_urls(value, base):
    if isinstance(value, str):
        if not value.strip():
            return []
        value = urljoin(base, value)
        return [value] if value.startswith(('https://', 'http://')) else []
    if isinstance(value, list):
        return [url for item in value for url in media_urls(item, base)]
    if isinstance(value, dict):
        for key in ('url', 'src', 'file'):
            if key in value:
                return media_urls(value[key], base)
    return []


def resolve_tenant(provider, session, referer, ua):
    parsed = urlparse(provider)
    if parsed.hostname not in HOSTS:
        return '', ''
    media_id = parsed.fragment.split('&', 1)[0]
    if not re.fullmatch(r'[A-Za-z0-9]+', media_id):
        raise ValueError('Player fara ID valid dupa #')
    root = 'https://' + parsed.hostname + '/'
    parent = urlparse(referer).hostname or 'desenefaine.com'
    api = root + 'api/v1/video?' + urlencode({
        'id': media_id, 'w': 1920, 'h': 1080, 'r': parent})
    response = session.get(api, headers={'User-Agent': ua, 'Referer': root,
                                       'Origin': root.rstrip('/')}, timeout=(10, 25))
    if response.status_code != 200:
        raise ValueError('API HTTP %s' % response.status_code)
    payload = decode_payload(response.text)
    # Match the player's embedding restriction, rather than bypassing it.
    player = payload.get('player') or {}
    allowed = player.get('restrictEmbed')
    if isinstance(allowed, str):
        try:
            allowed = json.loads(allowed)
        except ValueError:
            allowed = [allowed]
    if allowed and isinstance(allowed, list) and parent not in allowed:
        raise ValueError('Playerul nu permite domeniul paginii de origine')
    # Prefer the standard HLS source, not a browser-only P2P object.
    for key in ('source', 'cfNative', 'cf', 'hlsVideoTiktok', 'hlsVideoGoogle', 'sources'):
        urls = media_urls(payload.get(key), root)
        if not urls:
            continue
        stream = urls[0]
        tokens = payload.get('pk') or {}
        params = ''
        if '/v4/' in stream and isinstance(tokens, dict) and tokens.get('k'):
            params = urlencode({key: tokens[key] for key in ('k', 'kx') if key in tokens})
        return stream, params
    raise ValueError('API nu a furnizat o sursa video HTTP')