# -*- coding: utf-8 -*-
import requests
import xbmc

_LABEL    = '[SMY]'
_ENC_URL  = 'https://enc-dec.app/api/enc-vidstack'
_DEC_URL  = 'https://enc-dec.app/api/dec-vidstack'
_API_BASE = 'https://api.smashystream.top/api/v1/videosmashyi'
_UA       = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
_HEADERS  = {'User-Agent': _UA, 'Referer': 'https://smashyplayer.top'}


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    if not imdb_id:
        return []
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        enc_r = requests.get(_ENC_URL, timeout=10)
        enc_r.raise_for_status()
        enc_result = enc_r.json().get('result', {})
        token   = enc_result.get('token', '')
        user_id = enc_result.get('user_id', '')
        if not token:
            xbmc.log(f'{_LABEL} token lipsă', xbmc.LOGWARNING)
            return []

        if media_type == 'tv':
            url = f'{_API_BASE}/{imdb_id}/{season}/{episode}?token={token}&user_id={user_id}'
        else:
            url = f'{_API_BASE}/{imdb_id}?token={token}&user_id={user_id}'

        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data_str = r.json().get('data', '')
        if not data_str:
            xbmc.log(f'{_LABEL} data lipsă pentru imdb={imdb_id}', xbmc.LOGWARNING)
            return []

        parts = data_str.split('/#')
        if len(parts) < 2:
            xbmc.log(f'{_LABEL} format data neașteptat: {data_str[:80]}', xbmc.LOGWARNING)
            return []

        host, vid_id = parts[0], parts[1]
        enc_video = requests.get(f'{host}/api/v1/video?id={vid_id}', headers=_HEADERS, timeout=15).text

        dec = requests.post(_DEC_URL, json={'text': enc_video, 'type': '1'}, timeout=15)
        dec.raise_for_status()
        result = dec.json().get('result', {})
        m3u8 = result.get('source', '')
        if not m3u8:
            xbmc.log(f'{_LABEL} sursă lipsă după decriptare pentru imdb={imdb_id}', xbmc.LOGWARNING)
            return []
    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGWARNING)
        return []

    sources = [{
        'url':        f'{m3u8}|User-Agent={_UA}&Referer=https://smashyplayer.top',
        'provider':   _LABEL,
        'quality':    '1080p',
        'title_line': 'SmashyStream',
        'direct':     True,
    }]
    xbmc.log(f'{_LABEL} {len(sources)} surse pentru imdb={imdb_id}', xbmc.LOGINFO)
    return sources
