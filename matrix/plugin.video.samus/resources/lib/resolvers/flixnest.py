# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
from resources.lib.resolvers.stremio_client import get_movie_sources, get_tv_sources

_DEFAULT_URL = 'https://flixnest.app/flix-streams'
_LABEL = '[FNS]'


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    addon = xbmcaddon.Addon()
    base_url = (addon.getSetting('flixnest_url') or _DEFAULT_URL).strip().removesuffix('/manifest.json').rstrip('/')
    try:
        if media_type == 'movie':
            results = get_movie_sources(base_url, imdb_id, label=_LABEL, direct=True)
        else:
            if season is None or episode is None:
                return []
            results = get_tv_sources(base_url, imdb_id, season, episode, label=_LABEL, direct=True)
        xbmc.log(f'[Samus/FlixNest] {len(results)} surse pentru imdb_id={imdb_id}', xbmc.LOGINFO)
        return results
    except Exception as e:
        xbmc.log(f'[Samus/FlixNest] {e}', xbmc.LOGERROR)
        return []
