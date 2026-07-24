# -*- coding: utf-8 -*-
import requests
import xbmc

_BASE = 'https://cine.su'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150 Safari/537.36'
_HEADERS = {
    'User-Agent': _UA,
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': _BASE + '/en/watch',
    'Origin': _BASE,
    'Accept-Encoding': 'gzip, deflate, br',
}


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    if media_type == 'movie':
        url = '{}/v1/stream/master/movie/{}.m3u8'.format(_BASE, tmdb_id)
    else:
        url = '{}/v1/stream/master/tv/{}/{}/{}.m3u8'.format(_BASE, tmdb_id, season, episode)

    try:
        r = requests.head(url, headers=_HEADERS, timeout=8, allow_redirects=True)
        if r.status_code != 200:
            xbmc.log('[Samus/CineSu] HTTP {} pentru {}'.format(r.status_code, url), xbmc.LOGDEBUG)
            return []
    except Exception as e:
        xbmc.log('[Samus/CineSu] HEAD eroare: {}'.format(e), xbmc.LOGDEBUG)
        return []

    header_str = 'User-Agent={}&Referer={}/en/watch&Origin={}'.format(_UA, _BASE, _BASE)
    return [{
        'url': '{}|{}'.format(url, header_str),
        'quality': '1080p',
        'title_line': 'CineSu',
        'direct': True,
    }]
