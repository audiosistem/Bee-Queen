import requests
from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS

_LABEL = '[MAPI]'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    try:
        r = requests.get(f"{THRAX_BASE}/moviesapi/sources", params=params,
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
        referer = s.get('referer', 'https://flixcdn.cyou/')
        full_url = f"{url}|User-Agent={_UA}&Referer={referer}" if '|' not in url else url
        results.append({
            'url':        full_url,
            'provider':   _LABEL,
            'quality':    s.get('quality', 'Auto'),
            'title_line': 'MoviesAPI',
            'direct':     True,
        })
    return results
