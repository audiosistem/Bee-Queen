# -*- coding: utf-8 -*-
import xbmc
from resources.lib.resolvers._common import get_thrax_sources

_LABEL = '[PGP]'


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    params = {'imdb_id': imdb_id, 'type': media_type}
    if media_type == 'tv':
        if season is None or episode is None:
            return []
        params['season'] = season
        params['episode'] = episode
    results = get_thrax_sources('penguplay/sources', params, _LABEL)
    xbmc.log(f'[Samus/PenguPlay] {len(results)} surse pentru {imdb_id}', xbmc.LOGINFO)
    return results
