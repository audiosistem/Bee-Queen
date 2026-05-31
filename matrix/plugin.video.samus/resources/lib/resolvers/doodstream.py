# -*- coding: utf-8 -*-
import re
import time
import random
import logging
from string import ascii_letters, digits
from urllib.parse import urlsplit
import xbmc
import requests

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

log = logging.getLogger(__name__)


def resolve(url):
    """Returns stream_url string with headers or None."""
    try:
        parsed = urlsplit(url)
        domain = '{}://{}'.format(parsed.scheme, parsed.netloc)
        headers = {'User-Agent': _UA, 'Referer': domain + '/'}

        r = requests.get(url, headers=headers, timeout=10, verify=False)
        m = re.search(r'/pass_md5/[\w-]+/(?P<token>[\w-]+)', r.text)
        if not m:
            xbmc.log('[Samus/DoodStream] no pass_md5 found for {}'.format(url), xbmc.LOGWARNING)
            return None

        pass_md5_path = m.group(0)
        token = m.group('token')

        r2 = requests.get('{}{}'.format(domain, pass_md5_path), headers=headers, verify=False, timeout=10)
        base_url = r2.text.strip()
        rand = ''.join(random.choices(ascii_letters + digits, k=10))
        expiry = int(time.time() * 1000)
        stream_url = '{}{}?token={}&expiry={}'.format(base_url, rand, token, expiry)

        xbmc.log('[Samus/DoodStream] resolved: {}'.format(stream_url[:80]), xbmc.LOGINFO)
        return '{}|Referer={}&User-Agent={}'.format(stream_url, domain + '/', _UA)
    except Exception as e:
        xbmc.log('[Samus/DoodStream] eroare: {}'.format(e), xbmc.LOGERROR)
        return None
