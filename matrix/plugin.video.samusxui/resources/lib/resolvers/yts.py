# -*- coding: utf-8 -*-
"""YTS — surse torrent, doar filme. Căutarea o face serverul Thrax.

Întoarce lista BRUTĂ de la server, ca `torrentio.py`, nu prin
`_common.get_thrax_sources`: aceea e scrisă pentru provideri cu URL direct și
sare peste orice sursă fără `url`, aruncând `infoHash`/`trackers`/`seeds` —
adică exact tot ce definește o sursă torrent. Cu ea, YTS raporta „0 surse"
deși endpointul întorcea patru.

YTS nu are seriale, deci pentru `tv` nici nu mai lovim serverul.
"""
import requests
import xbmc

from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    if media_type != 'movie' or not imdb_id:
        return []
    try:
        r = requests.get(f'{THRAX_BASE}/yts/sources',
                         params={'imdb_id': imdb_id, 'type': 'movie'},
                         headers=THRAX_HEADERS, timeout=20)
        r.raise_for_status()
        sources = r.json().get('sources', [])
    except Exception as e:
        xbmc.log(f'[Samus/YTS] {imdb_id}: {e}', xbmc.LOGERROR)
        return []
    xbmc.log(f'[Samus/YTS] {len(sources)} surse pentru {imdb_id}', xbmc.LOGINFO)
    return sources
