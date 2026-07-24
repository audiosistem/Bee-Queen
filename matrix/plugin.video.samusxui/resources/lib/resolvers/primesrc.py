import requests
from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS

_LABEL = '[PSC]'


def _fetch(params):
    try:
        r = requests.get(f"{THRAX_BASE}/primesrc/sources", params=params,
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
        server = s.get('title', 'PrimeSrc')
        results.append({
            'url':          url,
            'provider':     _LABEL,
            'quality':      s.get('quality', ''),
            'title_line':   server,
            'display_name': server,
            'direct':       True,
        })
    return results


def get_primesrc_sources(tmdb_id):
    return _fetch({'tmdb_id': tmdb_id, 'type': 'movie'})


def get_primesrc_tv_sources(tmdb_id, season, episode):
    return _fetch({'tmdb_id': tmdb_id, 'type': 'tv', 'season': season, 'episode': episode})
