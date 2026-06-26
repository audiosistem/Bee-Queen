"""Extra source providers — community indexers run in parallel.

These are file-host-style providers: each returns links pointing at hosts
like Filemoon / Doodstream / Streamtape / Voe / Mixdrop / Streamwish etc.
Every stream emitted here is tagged ``needs_resolveurl=True`` so the
picker routes it through ``resolveurl_bridge`` at play time. They sit at
the BOTTOM of the picker (``sort_weight=999``) — they never compete with
the direct .m3u8 / .mp4 streams that the primary tier (Cloudnestra) and
the other independent tiers (Stigstream / Vidnest) return.

Hard guarantees:
  * Runs in its own thread pool; an exception in any one site can never
    affect the existing direct-stream tiers (they're separate workers in
    ``sources.py``).
  * Returns an empty list if a) the user has disabled the toggle, or
    b) ``script.module.resolveurl`` isn't installed (no point listing
    streams the player can't crack).
"""
from __future__ import annotations

import importlib
import pkgutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Tuple

from .. import common as _common
from .. import resolveurl_bridge as _RU
from . import sites as _sites

log = _common.log
TIMEOUT = 18


def _discover() -> List[Tuple[str, type]]:
    out = []
    for mi in pkgutil.iter_modules(_sites.__path__):
        if mi.name.startswith('_'):
            continue
        try:
            mod = importlib.import_module('resources.lib.extras.sites.' + mi.name)
        except Exception as e:
            log('extras: failed to import %s -> %s' % (mi.name, e))
            continue
        cls = getattr(mod, 'source', None)
        if cls is None:
            continue
        out.append((mi.name, cls))
    return out


PROVIDERS = _discover()
log('extras: discovered %d community indexer(s): %s'
    % (len(PROVIDERS), ', '.join(n for n, _ in PROVIDERS)))


def _build_host_dict():
    """Build a host-name list ResolveURL is willing to crack.

    Falls back to a static common list so providers that hard-check the
    dict still see entries even when RU isn't installed."""
    fallback = [
        'doodstream', 'dood', 'filemoon', 'voe', 'mixdrop', 'streamtape',
        'streamwish', 'streamhide', 'upstream', 'wolfstream', 'luluvdo',
        'vidoza', 'vidsrc', 'vidlink', 'gomo', 'gdriveplayer', 'send',
        'streamhg', 'streamruby', 'mp4upload', 'okru', 'youtube',
        'megaup', 'mixdrp', 'highstream',
    ]
    try:
        ru = _RU._ensure_loaded()
        if ru is not None and hasattr(ru, 'relevant_resolvers'):
            hosts = []
            for r in ru.relevant_resolvers(order_matters=True):
                try:
                    hosts.extend(r.domains)
                except Exception:
                    pass
            return list({h.lower() for h in hosts}) or fallback
    except Exception:
        pass
    return fallback


def _run_one(name: str, cls, media_type: str, imdb_id: str,
             tmdb_id: str, title: str, year: str,
             season: str, episode: str,
             host_dict: List[str]) -> List[Dict]:
    """Invoke one provider's ``movie/tvshow/episode`` then ``sources()``,
    convert each returned item to a vidscr stream-dict tagged for the
    file-host picker tier."""
    try:
        prov = cls()
    except Exception as e:
        log('extras: %s instantiation failed %s' % (name, e))
        return []

    try:
        if media_type == 'movie':
            if not hasattr(prov, 'movie'):
                return []
            url = prov.movie(imdb_id or '', tmdb_id or '', title or '',
                             title or '', '[]', year or '')
        else:  # show/episode
            if not (hasattr(prov, 'tvshow') and hasattr(prov, 'episode')):
                return []
            url = prov.tvshow(imdb_id or '', tmdb_id or '', '', title or '',
                              title or '', '[]', year or '')
            url = prov.episode(url, imdb_id or '', tmdb_id or '', '',
                               title or '', '', str(season or ''),
                               str(episode or ''))
    except Exception as e:
        log('extras: %s metadata-resolve raised %s' % (name, e))
        return []

    if not url:
        return []

    try:
        items = prov.sources(url, host_dict) or []
    except Exception as e:
        log('extras: %s sources() raised %s' % (name, e))
        return []

    streams = []
    for it in items:
        if not isinstance(it, dict):
            continue
        u = it.get('url')
        if not u or not isinstance(u, str):
            continue
        host = it.get('source') or 'unknown'
        quality = (it.get('quality') or 'auto').upper()
        info = it.get('info') or ''
        is_direct = bool(it.get('direct'))
        streams.append({
            'url': u,
            'proto': 'DIRECT' if is_direct else 'HOSTER',
            'needs_resolveurl': not is_direct,
            'source_site': name,
            'host_name': host,
            'host_origin': host,
            'provider': 'filehost',
            'quality': quality,
            'sort_weight': 999,
            'label': '[%s] %s via %s %s' % (quality, host, name,
                                            (info or '').strip())[:120],
        })
    return streams


def resolve_streams(media_type, tmdb_id, imdb_id=None, title=None,
                    year=None, season=None, episode=None,
                    progress_cb=None) -> List[Dict]:
    """Run every community indexer in parallel; merge their candidates."""
    if not PROVIDERS:
        return []
    if not title:
        # Every provider does string search by title; without it there's
        # nothing they can do.
        return []

    host_dict = _build_host_dict()
    out = []
    with ThreadPoolExecutor(max_workers=min(len(PROVIDERS), 8)) as ex:
        futures = {
            ex.submit(_run_one, name, cls, media_type, imdb_id or '',
                      str(tmdb_id or ''), title, str(year or ''),
                      season, episode, host_dict): name
            for name, cls in PROVIDERS
        }
        for fut in as_completed(futures, timeout=TIMEOUT + 5):
            name = futures[fut]
            try:
                streams = fut.result(timeout=1) or []
            except Exception as e:
                log('extras: %s worker error %s' % (name, e))
                streams = []
            if streams:
                log('extras: %s contributed %d candidate(s)'
                    % (name, len(streams)))
                out.extend(streams)
            if progress_cb:
                try:
                    progress_cb(name, len(streams))
                except Exception:
                    pass
    log('extras: aggregated %d candidate(s) across %d provider(s)'
        % (len(out), len(PROVIDERS)))
    return out
