"""Vyla — agregator server-side (40+ scrapere prin sidecar Node) via /vyla/sources.

Spre deosebire de resolverele care folosesc get_thrax_sources, propagă și
headerele (User-Agent etc.) în URL, nu doar Referer, fiindcă unele surse
(ex. fsharetv) le cer. Endpoint-ul e lent (agregă zeci de scrapere) → timeout
generos; sursele curg progresiv în UI.
"""
import requests as _req

from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS

_LABEL = '[VYL]'
_PREFIX = 'Vyla · '   # „Vyla · " — sidecar-ul îl pune deja în title; îl scoatem


def _stamp(url, referer, headers):
    """Adaugă Referer + headerele în sintaxa Kodi `url|Cheie=Valoare&...`."""
    if not url or '|' in url:
        return url
    parts = []
    seen = set()
    if referer:
        parts.append(f"Referer={referer}")
        seen.add('referer')
    for k, v in (headers or {}).items():
        if not k or k.lower() in seen or v is None:
            continue
        parts.append(f"{k}={v}")
        seen.add(k.lower())
    return f"{url}|{'&'.join(parts)}" if parts else url


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    params = {'tmdb_id': tmdb_id, 'type': media_type, 'timeout': 9000}
    if season:
        params['season'] = season
    if episode:
        params['episode'] = episode
    try:
        r = _req.get(f"{THRAX_BASE}/vyla/sources", params=params,
                     headers=THRAX_HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    out = []
    for s in data.get('sources', []):
        url = s.get('url')
        if not url:
            continue
        name = (s.get('title') or '').strip()
        if name.startswith(_PREFIX):
            name = name[len(_PREFIX):]
        name = name or s.get('server') or 'Vyla'
        out.append({
            'url':          _stamp(url, s.get('referer', ''), s.get('headers')),
            'provider':     _LABEL,
            'quality':      s.get('quality', ''),
            'title_line':   name,
            'display_name': name,
            'direct':       True,
            'subtitles':    s.get('subtitles', []),
        })
    return out
