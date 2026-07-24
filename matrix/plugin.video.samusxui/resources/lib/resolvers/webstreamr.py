# -*- coding: utf-8 -*-
import xbmc
from resources.lib.resolvers.stremio_client import get_movie_sources, get_tv_sources

_BASE_URL = 'https://87d6a6ef6b58-webstreamrmbg.baby-beamup.club'
_LABEL = '[WSR]'


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    try:
        if media_type == 'movie':
            results = get_movie_sources(_BASE_URL, imdb_id, label=_LABEL, direct=True)
        else:
            if season is None or episode is None:
                return []
            results = get_tv_sources(_BASE_URL, imdb_id, season, episode, label=_LABEL, direct=True)
        xbmc.log(f'[Samus/Webstreamr] {len(results)} surse pentru imdb_id={imdb_id}', xbmc.LOGINFO)
        return results
    except Exception as e:
        xbmc.log(f'[Samus/Webstreamr] {e}', xbmc.LOGERROR)
        return []
