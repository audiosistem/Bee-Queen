# -*- coding: utf-8 -*-
import threading
import requests
import xbmc
from resources.lib.resolvers.stremio_client import get_movie_sources, get_tv_sources

_BASE_URL = 'https://nebulastreams.onrender.com'
_LABEL = '[NBS]'
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
_NEEDS_RESOLVE = ('cryptoinsights.site',)


def _resolve_url(url):
    """Follow HTTP redirects to get the final video URL."""
    try:
        r = requests.head(url, headers={'User-Agent': _UA}, timeout=8,
                          allow_redirects=True)
        final = r.url
        ct = r.headers.get('Content-Type', '')
        if 'text/html' in ct:
            return None
        return final
    except Exception as e:
        xbmc.log(f'[Samus/NebulaStreams] redirect {url}: {e}', xbmc.LOGWARNING)
        return None


def _resolve_sources(sources):
    """Follow redirects in parallel for sources that need it."""
    needs = [(i, s) for i, s in enumerate(sources)
             if any(d in s.get('url', '') for d in _NEEDS_RESOLVE)]
    if not needs:
        return sources

    resolved = {}

    def _worker(idx, src):
        final = _resolve_url(src['url'])
        resolved[idx] = final

    threads = [threading.Thread(target=_worker, args=(i, s), daemon=True)
               for i, s in needs]
    for t in threads: t.start()
    for t in threads: t.join(timeout=9)

    result = []
    for i, src in enumerate(sources):
        if i in resolved:
            final_url = resolved[i]
            if not final_url:
                continue
            src = dict(src)
            src['url'] = final_url
        result.append(src)
    return result


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    try:
        if media_type == 'movie':
            results = get_movie_sources(_BASE_URL, imdb_id, label=_LABEL, direct=True)
        else:
            if season is None or episode is None:
                return []
            results = get_tv_sources(_BASE_URL, imdb_id, season, episode, label=_LABEL, direct=True)
        results = _resolve_sources(results)
        xbmc.log(f'[Samus/NebulaStreams] {len(results)} surse pentru imdb_id={imdb_id}', xbmc.LOGINFO)
        return results
    except Exception as e:
        xbmc.log(f'[Samus/NebulaStreams] {e}', xbmc.LOGERROR)
        return []
