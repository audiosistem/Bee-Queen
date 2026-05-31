import requests
from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS

_LABEL = '[VDL]'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    try:
        r = requests.get(f"{THRAX_BASE}/vidlink/resolve", params=params,
                         headers=THRAX_HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    url = data.get('url')
    if not url:
        return []
    referer = data.get('referer', 'https://vidlink.pro/')
    return [{
        'url':        f"{url}|User-Agent={_UA}&Referer={referer}",
        'provider':   _LABEL,
        'quality':    'Auto',
        'title_line': 'VidLink',
        'direct':     True,
    }]
