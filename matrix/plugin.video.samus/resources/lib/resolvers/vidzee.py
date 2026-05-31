import requests
from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS

_LABEL = '[Z]'
_UA = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    try:
        r = requests.get(f"{THRAX_BASE}/vidzee/sources", params=params,
                         headers=THRAX_HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    results = []
    for s in data.get('sources', []):
        url = s.get('url')
        if not url:
            continue
        referer = s.get('referer', 'https://core.vidzee.wtf/')
        origin = referer.rstrip('/')
        full_url = f"{url}|User-Agent={_UA}&Referer={referer}&Origin={origin}"
        results.append({
            'url':        full_url,
            'provider':   _LABEL,
            'quality':    s.get('quality', '1080p'),
            'title_line': s.get('title', ''),
            'direct':     True,
            'subtitles':  s.get('subtitles', []),
        })
    return results
