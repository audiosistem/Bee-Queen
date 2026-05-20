# -*- coding: utf-8 -*-
import requests
import xbmc
from urllib.parse import urlparse, parse_qs
from resources.lib.resolvers._common import THRAX_HEADERS as _THRAX_HEADERS

_BASE        = 'https://primesrc.me'
_THRAX       = 'https://api.derzis.xyz'
_LABEL       = '[PSM]'
_UA          = 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'
_HEADERS     = {
    'User-Agent': _UA,
    'Referer':    f'{_BASE}/',
    'Accept':     'application/json',
}


def resolve_via_thrax(url, tmdb_id=None):
    """Extrage key-ul din URL și îl rezolvă prin Thrax API (FlareSolverr server-side)."""
    qs = parse_qs(urlparse(url).query)
    key = (qs.get('key') or [''])[0]
    if not key:
        xbmc.log(f'{_LABEL} resolve_via_thrax: key lipsă din {url}', xbmc.LOGWARNING)
        return None
    try:
        params = {'key': key}
        if tmdb_id:
            params['tmdb_id'] = tmdb_id
        r = requests.get(f'{_THRAX}/primesrcme/resolve', params=params, timeout=90,
                         headers={**_THRAX_HEADERS, 'Accept-Encoding': 'gzip, deflate'})
        if not r.ok:
            xbmc.log(f'{_LABEL} Thrax /primesrcme/resolve HTTP {r.status_code}', xbmc.LOGWARNING)
            return None
        data = r.json()
        link = data.get('link', '')
        if not link:
            xbmc.log(f'{_LABEL} Thrax: câmpul link lipsă: {data}', xbmc.LOGWARNING)
            return None
        cached = data.get('cached', False)
        xbmc.log(f'{_LABEL} link rezolvat {"(cache)" if cached else "(FlareSolverr)"}: {link}', xbmc.LOGINFO)
        return {'link': link}
    except Exception as e:
        xbmc.log(f'{_LABEL} resolve_via_thrax eroare: {e}', xbmc.LOGWARNING)
        return None


def _get_servers(media_type, tmdb_id, season=None, episode=None):
    params = {'type': media_type, 'tmdb': tmdb_id}
    if season is not None:
        params['season'] = season
    if episode is not None:
        params['episode'] = episode
    try:
        r = requests.get(f'{_BASE}/api/v1/s', params=params, headers=_HEADERS, timeout=10)
        if r.ok:
            return r.json().get('servers', [])
        if r.status_code == 403 and 'cloudflare' in r.text.lower():
            xbmc.log(f'{_LABEL} /api/v1/s blocat Cloudflare pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        else:
            xbmc.log(f'{_LABEL} /api/v1/s status={r.status_code}', xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f'{_LABEL} get_servers: {e}', xbmc.LOGWARNING)
    return []


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []

    servers = _get_servers(media_type, tmdb_id, season, episode)
    if not servers:
        xbmc.log(f'{_LABEL} niciun server pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
        return []

    sources = []
    seen    = set()

    for srv in servers:
        key  = srv.get('key', '')
        name = srv.get('name', '')
        if not key:
            continue
        api_url = f'{_BASE}/api/v1/l?key={key}'
        if api_url in seen:
            continue
        seen.add(api_url)

        size       = srv.get('file_size') or ''
        quality    = srv.get('quality') or '1080p'
        audio_type = srv.get('audio_type') or ''
        audio_lang = srv.get('audio_language') or ''

        parts = [name, size]
        if audio_type: parts.append(f'[{audio_type.upper()}]')
        if audio_lang: parts.append(f'({audio_lang.upper()})')
        title_line = ' '.join(filter(None, parts)).strip()

        sources.append({
            'url':        api_url,
            'provider':   _LABEL,
            'quality':    quality,
            'title_line': title_line,
            'direct':     False,
            'tmdb_id':    f'{tmdb_id}:{media_type}',
        })

    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
