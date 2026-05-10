# -*- coding: utf-8 -*-
import re
import requests
import xbmc
from resources.lib.resolvers._common import THRAX_HEADERS as _THRAX_HEADERS

_THRAX  = 'https://api.derzis.xyz'
_LABEL  = '[VML]'


def is_vidmoly_url(url):
    return bool(re.search(r'vidmoly\.(me|biz|to|net)', url))


def resolve_via_thrax(url):
    """Rezolvă un URL vidmoly prin Thrax API (Chrome+Xvfb server-side)."""
    xbmc.log(f'{_LABEL} resolve_via_thrax: {url}', xbmc.LOGINFO)
    try:
        r = requests.get(
            f'{_THRAX}/vidmoly/resolve',
            params={'url': url},
            timeout=60,
            headers={**_THRAX_HEADERS, 'Accept-Encoding': 'gzip, deflate'},
        )
        if not r.ok:
            xbmc.log(f'{_LABEL} Thrax HTTP {r.status_code}', xbmc.LOGWARNING)
            return None
        data = r.json()
        m3u8 = data.get('url', '')
        if not m3u8:
            xbmc.log(f'{_LABEL} Thrax: câmpul url lipsă: {data}', xbmc.LOGWARNING)
            return None
        xbmc.log(f'{_LABEL} rezolvat: {m3u8[:80]}', xbmc.LOGINFO)
        return m3u8
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return None


