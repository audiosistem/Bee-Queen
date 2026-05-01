# -*- coding: utf-8 -*-
import requests
import xbmc
from resources.lib.resolvers.stremio_client import _parse_direct_streams

_BASE_URL = 'https://rogflix.vflix.life/stremio/stream'
_LABEL = '[RFL]'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Origin': 'https://rogflix.vflix.life',
    'Referer': 'https://rogflix.vflix.life/',
}


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    try:
        if media_type == 'movie':
            url = f'{_BASE_URL}/movie/{imdb_id}.json'
        else:
            if season is None or episode is None:
                return []
            url = f'{_BASE_URL}/series/{imdb_id}:{season}:{episode}.json'
        r = requests.get(url, headers=_HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        streams = r.json().get('streams', [])
        results = _parse_direct_streams(streams, _LABEL)
        xbmc.log(f'[Samus/Rogflix] {len(results)} surse pentru imdb_id={imdb_id}', xbmc.LOGINFO)
        return results
    except Exception as e:
        xbmc.log(f'[Samus/Rogflix] {e}', xbmc.LOGERROR)
        return []
