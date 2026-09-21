# resources/lib/resolvers/abysscdn.py
import re
import xbmc
from resources.lib.resolvers._common import THRAX_HEADERS as _THRAX_HEADERS

_THRAX = 'https://api.derzis.xyz'
_LABEL = '[ABYSS]'


def is_abysscdn_url(url):
    return bool(re.search(r'abysscdn\.com|abyssplayer\.com|short\.icu/', url or ''))


def resolve_via_thrax(url):
    """Returnează stream-ul de cea mai bună calitate (aleasă server-side).

    Notă: am încercat un manifest HLS multi-calitate (/abysscdn/master.m3u8) ca
    inputstream.adaptive să aleagă/comute automat — dar fișierele Abyss sunt MP4
    întreg (nesegmentat), deci nu există granițe reale de segment la care ABR-ul
    să poată reevalua bandwidth-ul: playerul face o alegere inițială conservatoare
    (cea mai mică calitate) și rămâne blocat acolo pentru tot fișierul. Revenit la
    o singură calitate aleasă server-side (cea mai bună, din codecul dominant —
    Abyss poate amesteca un unic rendition cu codec diferit, ex. un AV1 izolat
    printre variante H.264, care poate rupe redarea)."""
    xbmc.log(f'{_LABEL} resolve_via_thrax: {url}', xbmc.LOGINFO)
    try:
        import requests
        r = requests.get(
            f'{_THRAX}/abysscdn/resolve',
            params={'url': url},
            timeout=60,
            headers={**_THRAX_HEADERS, 'Accept-Encoding': 'gzip, deflate'},
        )
        if not r.ok:
            xbmc.log(f'{_LABEL} Thrax HTTP {r.status_code}', xbmc.LOGWARNING)
            return ''
        data = r.json()
        stream_url = data.get('url', '')
        if not stream_url:
            xbmc.log(f'{_LABEL} Thrax: câmpul url lipsă: {data}', xbmc.LOGWARNING)
            return ''
        xbmc.log(f'{_LABEL} rezolvat: {stream_url[:80]}', xbmc.LOGINFO)
        return stream_url
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGERROR)
        return ''
