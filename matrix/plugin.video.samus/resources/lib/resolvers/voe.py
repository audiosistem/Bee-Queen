# -*- coding: utf-8 -*-
import re
import json
import codecs
import base64
import xbmc
import requests

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
_REFERER = 'https://voe.sx/'
_STRIP_PATTERNS = ['@$', '^^', '~@', '%?', '*~', '!!', '#&']


def _safe_b64(s):
    s += '=' * (-len(s) % 4)
    return base64.b64decode(s).decode('utf-8', errors='ignore')


def _deobfuscate(raw_json):
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


def resolve(url):
    """Resolve a VOE.sx embed URL to a direct stream URL. Returns stream_url string or None."""
    headers = {'User-Agent': _UA, 'Referer': _REFERER}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        html = r.text

        m = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)', html, re.I)
        if m:
            r = requests.get(m.group(1), headers=headers, timeout=15)
            html = r.text

        for script in re.findall(r'<script type="application/json">(.*?)</script>', html, re.S):
            result = _deobfuscate(script.strip())
            if result and isinstance(result, dict):
                stream_url = result.get('direct_access_url') or result.get('source')
                if stream_url:
                    stream_url = re.sub(r'([?&])d=1(&|$)', r'\2', stream_url).rstrip('?&')
                    xbmc.log('[Samus/VOE] resolved: {}'.format(stream_url[:80]), xbmc.LOGINFO)
                    return '{}|Referer={}&User-Agent={}'.format(stream_url, _REFERER, _UA)
    except Exception as e:
        xbmc.log('[Samus/VOE] eroare: {}'.format(e), xbmc.LOGERROR)
    return None
