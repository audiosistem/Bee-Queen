# -*- coding: utf-8 -*-
import re
import json
import codecs
import base64
import xbmc
import requests

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
_STRIP_PATTERNS = ['@$', '^^', '~@', '%?', '*~', '!!', '#&']

_LULU_DOMAINS = ('luluvdoo.com', 'lulustream.com', 'luluvdo.com', 'lulu.st',
                 'luluvid.com', 'streamhihi.com', 'd00ds.site')


def _safe_b64(s):
    s += '=' * (-len(s) % 4)
    return base64.b64decode(s).decode('utf-8', errors='ignore')


def _deobfuscate_voe(raw_json):
    try:
        data = json.loads(raw_json)
        if not data or not isinstance(data, list) or not data[0]:
            return None
        s = codecs.encode(data[0], 'rot_13')
        for p in _STRIP_PATTERNS:
            s = s.replace(p, '')
        s = _safe_b64(s)
        s = ''.join(chr(ord(c) - 3) for c in s)
        s = s[::-1]
        s = _safe_b64(s)
        return json.loads(s) if s.startswith('{') else s
    except Exception:
        return None


def _unpack_lulu(html):
    """Dezpachetează PACKER de pe pagini LuluStream/luluvdoo."""
    km = re.search(r"'([^']{200,})'\.split\('\|'\)", html)
    if not km:
        return None
    keys = km.group(1).split('|')
    pm = re.search(r"\}\('(.*?)',\s*36,\s*\d+,\s*'", html, re.DOTALL)
    if not pm:
        return None

    def _replace(match):
        word = match.group(0)
        try:
            n = int(word, 36)
            return keys[n] if n < len(keys) and keys[n] else word
        except Exception:
            return word

    return re.sub(r'\b[0-9a-z]+\b', _replace, pm.group(1))


def resolve(url):
    """Resolve a VOE.sx embed URL to a direct stream URL. Returns stream_url string or None."""
    try:
        headers = {'User-Agent': _UA, 'Referer': 'https://voe.sx/'}
        r = requests.get(url, headers=headers, timeout=15)
        html = r.text

        m = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)', html, re.I)
        if m:
            redirect_url = m.group(1)
            # Actualizează Referer la host-ul redirect-ului
            host_m = re.match(r'(https?://[^/]+)', redirect_url)
            referer = (host_m.group(1) + '/') if host_m else 'https://voe.sx/'
            headers = {'User-Agent': _UA, 'Referer': referer}
            r = requests.get(redirect_url, headers=headers, timeout=15)
            html = r.text

            # Dacă redirect-ul e luluvdoo — dezpachetează PACKER (token e bound la IP-ul Kodi)
            if any(d in redirect_url for d in _LULU_DOMAINS):
                unpacked = _unpack_lulu(html)
                if unpacked:
                    m2 = re.search(r'sources:\[{file:"([^"]+)"', unpacked)
                    if m2:
                        stream_url = m2.group(1)
                        xbmc.log('[Samus/VOE] luluvdoo stream: {}'.format(stream_url[:80]), xbmc.LOGINFO)
                        return '{}|Referer={}&User-Agent={}'.format(stream_url, referer, _UA)
                xbmc.log('[Samus/VOE] luluvdoo unpack failed pentru {}'.format(redirect_url), xbmc.LOGWARNING)
                return None

        # VOE player standard — dezobfuscare JSON
        for script in re.findall(r'<script type="application/json">(.*?)</script>', html, re.S):
            result = _deobfuscate_voe(script.strip())
            if result and isinstance(result, dict):
                # Preferă m3u8 (source) față de MP4 (direct_access_url)
                stream_url = result.get('source') or result.get('direct_access_url')
                if stream_url:
                    stream_url = re.sub(r'([?&])d=1(&|$)', r'\2', stream_url).rstrip('?&')
                    host_m = re.match(r'(https?://[^/]+)', url)
                    ref = (host_m.group(1) + '/') if host_m else 'https://voe.sx/'
                    xbmc.log('[Samus/VOE] resolved: {}'.format(stream_url[:80]), xbmc.LOGINFO)
                    return '{}|Referer={}&User-Agent={}'.format(stream_url, ref, _UA)
    except Exception as e:
        xbmc.log('[Samus/VOE] eroare: {}'.format(e), xbmc.LOGERROR)
    return None
