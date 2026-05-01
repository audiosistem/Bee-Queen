# -*- coding: utf-8 -*-
"""ok.ru resolver — extrage HLS stream + subtitleTracks din metadata embed"""
import json
import re
import requests
import xbmc

_LABEL = '[OKRU]'
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent': _UA,
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}

_QUALITY_ORDER = ('1080p', '720p', 'hd', 'full', 'sd', 'low', 'lowest', 'mobile')


def _video_id(url):
    m = re.search(r'ok\.ru/(?:video(?:embed)?|dk\?cmd=VideoPlayer)/(\d+)', url)
    return m.group(1) if m else None


def _best_video_url(videos):
    """Alege cel mai bun URL din lista videos[] by quality name."""
    by_name = {v.get('name', '').lower(): v.get('url', '') for v in videos if v.get('url')}
    for q in _QUALITY_ORDER:
        if q in by_name:
            return by_name[q]
    return next(iter(by_name.values()), None) if by_name else None


def resolve(url):
    """Returnează {'url': stream_url, 'subtitles': [sub_url, ...]} sau None."""
    video_id = _video_id(url)
    if not video_id:
        xbmc.log(f'{_LABEL} Nu am putut extrage video_id din {url}', xbmc.LOGWARNING)
        return None

    embed_url = f'https://ok.ru/videoembed/{video_id}'
    try:
        r = requests.get(embed_url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        xbmc.log(f'{_LABEL} GET {embed_url}: {e}', xbmc.LOGWARNING)
        return None

    # Extrage data-options (HTML entities decodate de requests/html.parser)
    m = re.search(r'data-options="([^"]+)"', html)
    if not m:
        xbmc.log(f'{_LABEL} data-options negăsit în pagina {embed_url}', xbmc.LOGWARNING)
        return None

    try:
        opts = json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&'))
        metadata = json.loads(opts['flashvars']['metadata'])
    except Exception as e:
        xbmc.log(f'{_LABEL} Eroare parsare metadata: {e}', xbmc.LOGWARNING)
        return None

    # Stream URL — preferăm HLS; fallback la videos[]
    stream_url = metadata.get('ondemandHls') or _best_video_url(metadata.get('videos', []))
    if not stream_url:
        xbmc.log(f'{_LABEL} Niciun stream găsit pentru {video_id}', xbmc.LOGWARNING)
        return None

    # Subtitrări
    sub_tracks = metadata.get('movie', {}).get('subtitleTracks', [])
    subtitles = []
    for track in sub_tracks:
        sub_url = track.get('url', '')
        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url
        if sub_url:
            subtitles.append({
                'url':      sub_url,
                'language': track.get('language', 'und'),
            })

    xbmc.log(f'{_LABEL} {video_id}: stream OK, {len(subtitles)} subtitrări', xbmc.LOGINFO)
    return {'url': stream_url, 'video_id': video_id, 'subtitles': subtitles}
