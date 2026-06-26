# -*- coding: utf-8 -*-
"""File-host source aggregator.

This module is a 4th INDEPENDENT top-level source (alongside Cloudnestra
primary, Vidsrc secondary, Stigstream, and Vidnest). It walks every
scraper in ``resources/lib/fh/`` in parallel and returns the union of
all file-host candidates.

Design boundaries (these are PROMISES, not suggestions):
  * Never touches ``vidsrc.py``, ``vidsrc2.py``, ``stigstream.py``,
    ``vidnest.py``, ``sources.py``'s primary/secondary flow. Streams
    returned here are an ADDITIONAL pool merged into ``sources.resolve``'s
    secondary list — existing flow keeps working byte-for-byte.
  * Every stream returned has ``needs_resolveurl=True`` so the picker /
    player code path knows to route it through
    ``resolveurl_bridge.resolve()`` at play time instead of feeding the
    URL straight to Kodi (which would just iframe-error).
  * Sorted to the BOTTOM of the picker (per user's explicit ask) via
    a high ``sort_weight`` value attached to each entry. The picker
    sort order is implemented in ``listing.py`` (sources are otherwise
    untouched).
"""
from __future__ import annotations

import importlib
import pkgutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable, Tuple

from .common import get_setting_bool, log
from . import fh as _fh_pkg

TIMEOUT = 15


def _scrapers() -> List[Tuple[str, Callable]]:
    """Auto-discover every fh/<name>.py module exposing a ``resolve()``."""
    out = []
    for mod_info in pkgutil.iter_modules(_fh_pkg.__path__):
        name = mod_info.name
        if name.startswith('_'):
            continue
        try:
            mod = importlib.import_module('resources.lib.fh.' + name)
        except Exception as e:
            log('filehosts: failed to import fh.%s - %s' % (name, e))
            continue
        if hasattr(mod, 'resolve'):
            pretty = getattr(mod, 'SITE', name.capitalize())
            out.append((pretty, mod.resolve))
    return out


SCRAPERS = _scrapers()
log('filehosts: discovered %d scraper module(s): %s'
    % (len(SCRAPERS), ', '.join(p for p, _ in SCRAPERS)))


def _safe_run(fn, media_type, tmdb_id, imdb_id, title, year, season, episode):
    """Run one fh/*.resolve in isolation — any exception is swallowed and
    logged so a misbehaving scraper can't kill the whole aggregator."""
    try:
        return fn(media_type, tmdb_id, imdb_id, title=title, year=year,
                  season=season, episode=episode) or []
    except Exception as e:
        log('filehosts: scraper raised %s' % e)
        return []


def resolve_streams(media_type, tmdb_id, imdb_id=None, title=None,
                    year=None, season=None, episode=None,
                    progress_cb=None) -> List[Dict]:
    """Run every fh/* scraper in parallel and return merged candidates.

    ``progress_cb(scraper_name, count)`` is invoked as each scraper
    finishes — used by ``sources.py`` to update the live progress dialog
    with per-scraper tallies."""
    if not get_setting_bool('enable_filehost_sources', True):
        log('filehosts: disabled by user setting')
        return []
    if not SCRAPERS:
        return []

    out = []
    with ThreadPoolExecutor(max_workers=min(len(SCRAPERS), 6)) as ex:
        futures = {
            ex.submit(_safe_run, fn, media_type, tmdb_id, imdb_id, title,
                      year, season, episode): pretty
            for pretty, fn in SCRAPERS
        }
        for fut in as_completed(futures, timeout=TIMEOUT + 3):
            pretty = futures[fut]
            try:
                streams = fut.result(timeout=1) or []
            except Exception as e:
                log('filehosts: %s worker error %s' % (pretty, e))
                streams = []
            if streams:
                log('filehosts: %s contributed %d candidate(s)'
                    % (pretty, len(streams)))
                # Tag every entry so the picker sort knows to push it down.
                for s in streams:
                    s['provider'] = 'filehost'
                    s['sort_weight'] = 999
                    s.setdefault('needs_resolveurl', True)
                out.extend(streams)
            if progress_cb:
                try:
                    progress_cb(pretty, len(streams))
                except Exception:
                    pass
    log('filehosts: aggregated %d candidates across %d scraper(s)'
        % (len(out), len(SCRAPERS)))
    return out
