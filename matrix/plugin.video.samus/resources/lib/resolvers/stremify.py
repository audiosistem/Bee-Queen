# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
from resources.lib.resolvers.stremio_client import get_movie_sources, get_tv_sources

_DEFAULT_URL = 'https://stremify.hayd.uk/YnVpbHQtaW4sZnJlbWJlZCxmcmVuY2hjbG91ZCxtZWluZWNsb3VkLGtpbm9raXN0ZSxjaW5laGRwbHVzLHZlcmhkbGluayxldXJvc3RyZWFtaW5nLGd1YXJkYWhkLHZpc2lvbmNpbmUsd2VjaW1hLGFrd2FtLGRyYW1hY29vbCxkcmFtYWNvb2xfY2F0YWxvZw=='
_LABEL = '[STF]'


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    addon = xbmcaddon.Addon()
    raw = (addon.getSetting('stremify_url') or _DEFAULT_URL).strip()
    base_url = raw.removesuffix('/manifest.json').rstrip('/')
    try:
        if media_type == 'movie':
            results = get_movie_sources(base_url, imdb_id, label=_LABEL, direct=True)
        else:
            if season is None or episode is None:
                return []
            results = get_tv_sources(base_url, imdb_id, season, episode, label=_LABEL, direct=True)
        xbmc.log(f'[Samus/Stremify] {len(results)} surse pentru imdb_id={imdb_id}', xbmc.LOGINFO)
        return results
    except Exception as e:
        xbmc.log(f'[Samus/Stremify] {e}', xbmc.LOGERROR)
        return []
