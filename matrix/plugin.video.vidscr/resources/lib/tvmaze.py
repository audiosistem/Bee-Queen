# -*- coding: utf-8 -*-
"""TVmaze client — used for the 7-day premiering calendar."""
import datetime
import requests

from . import cache
from .common import log

API_BASE = 'https://api.tvmaze.com'
TIMEOUT = 15


def _get(path, params=None, ttl=3600):
    url = API_BASE + path
    cached = cache.get(url, params, ttl=ttl)
    if cached is not None:
        return cached
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        cache.put(url, params, data)
        return data
    except Exception as e:
        log('TVmaze error %s on %s' % (e, path))
        return []


def schedule(country='US', date=None):
    """Episodes airing on a given date in a country (ISO 3166-1 e.g. US, GB)."""
    p = {'country': country}
    if date:
        p['date'] = date
    return _get('/schedule', p, ttl=1800) or []


def upcoming_premieres(countries=('US', 'GB'), days=7):
    """Returns a flat list of episodes premiering within `days` days across the given countries."""
    today = datetime.date.today()
    seen_ids = set()
    out = []
    for d in range(days):
        dt = (today + datetime.timedelta(days=d)).isoformat()
        for c in countries:
            for ep in schedule(c, dt) or []:
                ep_id = ep.get('id')
                if ep_id in seen_ids:
                    continue
                seen_ids.add(ep_id)
                ep['_country'] = c
                ep['_airdate'] = dt
                out.append(ep)
    # Sort by airdate then airtime
    out.sort(key=lambda e: (e.get('_airdate', ''), e.get('airtime', '')))
    return out


def show_external_ids(show):
    """Pull TMDB/IMDB ids out of a TVmaze show object."""
    ext = (show or {}).get('externals') or {}
    return {
        'imdb': ext.get('imdb'),
        'tvdb': ext.get('thetvdb'),
        'tvrage': ext.get('tvrage'),
    }
