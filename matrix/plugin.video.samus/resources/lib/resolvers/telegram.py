# -*- coding: utf-8 -*-
import requests
import xbmc

_THRAX = 'https://api.derzis.xyz'
_LABEL = '[TG]'


def resolve_via_thrax(url):
    """Rezolvă un URL tg://file_id prin Thrax API și returnează URL streamabil."""
    xbmc.log(f'{_LABEL} resolve_via_thrax: {url}', xbmc.LOGINFO)
    try:
        r = requests.get(
            f'{_THRAX}/telegram/resolve',
            params={'url': url},
            timeout=15,
            headers={'Accept-Encoding': 'gzip, deflate'},
        )
        if not r.ok:
            xbmc.log(f'{_LABEL} Thrax HTTP {r.status_code}', xbmc.LOGWARNING)
            return None
        data = r.json()
        stream_url = data.get('url', '')
        if not stream_url:
            xbmc.log(f'{_LABEL} Thrax: câmpul url lipsă: {data}', xbmc.LOGWARNING)
            return None
        xbmc.log(f'{_LABEL} rezolvat: {stream_url[:80]}', xbmc.LOGINFO)
        return stream_url
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return None
