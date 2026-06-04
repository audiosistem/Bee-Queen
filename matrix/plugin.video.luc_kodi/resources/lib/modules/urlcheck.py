# -*- coding: utf-8 -*-
"""luc_kodi URL validity check 

Purpose:
- Reject dead links quickly (403/404/other >=400)
- Reject HTML/text error pages pretending to be video
- Accept HLS playlists (#EXTM3U) even when Content-Type is text/plain
- Support Kodi pipe-header syntax: url|Header=Value&Header2=Value2
"""

import ssl
import urllib.request as urllib2
from urllib.parse import parse_qsl

from resources.lib.database import cache
from resources.lib.modules.client import randomagent
from resources.lib.modules import log_utils


def _default_headers():
    return {'User-Agent': cache.get(randomagent, 12)}


def check_url_validity(url, headers=None, timeout=6):
    try:
        if not url:
            return False

        # Skip non-http playback targets
        low = url.lower()
        if low.startswith(('plugin://', 'special://', 'magnet:', 'rtmp://')):
            return True

        clean_url = url
        hdrs = {}
        hdrs.update(_default_headers())
        if isinstance(headers, dict):
            hdrs.update(headers)

        # Kodi pipe header syntax: url|Header=Value&Header2=Value2
        if '|' in url:
            clean_url, qs = url.split('|', 1)
            try:
                hdrs.update(dict(parse_qsl(qs)))
            except Exception:
                pass

        req = urllib2.Request(clean_url, headers=hdrs)

        ctx = None
        try:
            ctx = ssl._create_unverified_context()
        except Exception:
            ctx = None

        with urllib2.urlopen(req, timeout=timeout, context=ctx) as resp:
            try:
                code = resp.getcode() or 200
            except Exception:
                code = 200

            if int(code) >= 400:
                log_utils.log('[URLCHECK] HTTP %s: %s' % (code, clean_url), level=log_utils.LOGWARNING)
                return False

            try:
                chunk = resp.read(512) or b''
            except Exception:
                chunk = b''

            try:
                content_str = chunk.decode('utf-8', errors='ignore')
            except Exception:
                content_str = ''

            # A) HLS playlist -> allow
            if '#EXTM3U' in content_str:
                return True

            # B) Content-Type indicates video/binary -> allow
            try:
                ctype = (resp.headers.get('Content-Type') or '').lower()
            except Exception:
                ctype = ''

            if ('video' in ctype) or ('application/octet-stream' in ctype) or ('mpegurl' in ctype) or ('m3u8' in ctype):
                return True

            # C) HTML/Text error pages -> reject
            if ('text' in ctype) or ('html' in ctype) or ('<html' in content_str.lower()):
                log_utils.log('[URLCHECK] HTML/Text detected (fake video): %s' % clean_url, level=log_utils.LOGWARNING)
                return False

            # D) Otherwise allow (rare cases)
            return True

    except Exception as e:
        log_utils.log('[URLCHECK] Connection error: %s' % e, level=log_utils.LOGWARNING)
        return False
