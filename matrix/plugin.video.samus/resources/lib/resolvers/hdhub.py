# -*- coding: utf-8 -*-
import xbmc
from resources.lib.resolvers.stremio_client import get_movie_sources, get_tv_sources

_BASE_URL = 'https://hdhub.thevolecitor.qzz.io/eyJ0b3Jib3giOiJ1bnNldCIsInF1YWxpdGllcyI6IjIxNjBwLDEwODBwLDcyMHAiLCJzb3J0IjoiZGVzYyJ9'
_LABEL = '[HDB]'


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    try:
        if media_type == 'movie':
            xbmc.log('[Samus/HDHub] film imdb_id={} url={}/stream/movie/{}.json'.format(
                imdb_id, _BASE_URL, imdb_id), xbmc.LOGINFO)
            results = get_movie_sources(_BASE_URL, imdb_id, label=_LABEL, direct=True)
        else:
            if season is None or episode is None:
                return []
            xbmc.log('[Samus/HDHub] serial imdb_id={} S{}E{} url={}/stream/series/{}:{}:{}.json'.format(
                imdb_id, season, episode, _BASE_URL, imdb_id, season, episode), xbmc.LOGINFO)
            results = get_tv_sources(_BASE_URL, imdb_id, season, episode, label=_LABEL, direct=True)
        xbmc.log('[Samus/HDHub] găsite {} surse pentru imdb_id={}'.format(len(results), imdb_id), xbmc.LOGINFO)
        return results
    except Exception as e:
        xbmc.log('[Samus/HDHub] {}'.format(e), xbmc.LOGERROR)
        return []
