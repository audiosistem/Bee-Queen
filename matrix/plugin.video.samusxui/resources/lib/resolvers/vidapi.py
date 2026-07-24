# -*- coding: utf-8 -*-
import urllib.parse

import requests
import xbmc

_API     = 'https://streamdata.vaplayer.ru/api.php'
_UA      = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
_REFERER = 'https://brightpathsignals.com/'
_ORIGIN  = 'https://brightpathsignals.com'
_HEADERS = {
    'User-Agent': _UA,
    'Referer':    _REFERER,
    'Origin':     _ORIGIN,
    'Accept':     '*/*',
}
_HEADER_STR = urllib.parse.urlencode({
    'Referer':    _REFERER,
    'Origin':     _ORIGIN,
    'User-Agent': _UA,
})


def _infer_quality(file_name):
    s = str(file_name or '')
    for marker, label in (('2160', '4K'), ('4K', '4K'), ('4k', '4K'),
                          ('1080', '1080p'), ('720', '720p'),
                          ('480', '480p'), ('360', '360p')):
        if marker in s:
            return label
    return 'HD'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    params = {'tmdb': tmdb_id, 'type': media_type}
    if media_type == 'tv':
        params['season'] = season
        params['episode'] = episode

    try:
        r = requests.get(_API, params=params, headers=_HEADERS, timeout=10)
        if not r.ok:
            xbmc.log(f'[Samus/VidAPI] HTTP {r.status_code}', xbmc.LOGDEBUG)
            return []
        data = r.json()
        if str(data.get('status_code')) != '200' or not data.get('data'):
            xbmc.log(f'[Samus/VidAPI] status={data.get("status_code")}', xbmc.LOGDEBUG)
            return []

        info = data['data']
        quality = _infer_quality(info.get('file_name'))
        server = info.get('file_name') or 'VidAPI'
        sources = []
        for url in (info.get('stream_urls') or []):
            if not url:
                continue
            sources.append({
                'url':          f'{url}|{_HEADER_STR}',
                'quality':      quality,
                'title_line':   server,
                'display_name': server,
                'direct':       True,
            })
        xbmc.log(f'[Samus/VidAPI] {len(sources)} surse', xbmc.LOGINFO)
        return sources
    except Exception as e:
        xbmc.log(f'[Samus/VidAPI] eroare: {e}', xbmc.LOGDEBUG)
        return []
