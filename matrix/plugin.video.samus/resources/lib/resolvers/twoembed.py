import requests
from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS

_LABEL = '[2E]'


def get_twoembed_sources(content_id, season=None, episode=None):
    media_type = 'tv' if (season is not None and episode is not None) else 'movie'
    params = {'tmdb_id': content_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    try:
        r = requests.get(f"{THRAX_BASE}/twoembed/sources", params=params,
                         headers=THRAX_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    results = []
    for s in data.get('sources', []):
        url = s.get('url')
        if not url:
            continue
        results.append({
            'url':        url,
            'provider':   _LABEL,
            'quality':    s.get('quality', ''),
            'title_line': s.get('title', '2Embed'),
            'direct':     False,
        })
    return results
