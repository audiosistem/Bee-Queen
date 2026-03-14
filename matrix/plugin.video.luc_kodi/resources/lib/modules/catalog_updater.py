# -*- coding: utf-8 -*-
"""
luc_kodi - TMDB Catalog Precache / Auto Update 

This service prefetches key TMDB endpoints into luc_kodi cache DB so widgets/menus load fast.
"""

from __future__ import absolute_import

import re
import time
from threading import Thread

from resources.lib.modules import control, log_utils

LOGINFO = log_utils.LOGINFO

# Settings IDs (added in resources/settings.xml)
S_ENABLED = 'catalog.auto_update.enabled'
S_ON_START = 'catalog.auto_update.on_start'
S_INTERVAL = 'catalog.auto_update.interval_hours'
S_NOTIFY = 'catalog.auto_update.notify'
S_LASTRUN = 'catalog.auto_update.last_run'  # internal timestamp (seconds)

CHECK_EVERY_SECONDS = 300  # 5 minutes

def _now():
    return int(time.time())

def _get_bool(setting_id, default=False):
    v = control.setting(setting_id)
    if v == '':
        return default
    return v == 'true'

def _get_int(setting_id, default):
    try:
        v = control.setting(setting_id)
        return int(v) if v != '' else default
    except:
        return default

def _get_last_run():
    try:
        v = control.setting(S_LASTRUN)
        return int(v) if v else 0
    except:
        return 0

def _set_last_run(ts):
    try:
        control.setSetting(S_LASTRUN, str(int(ts)))
    except:
        pass

def _is_due(interval_hours):
    last = _get_last_run()
    if last == 0:
        return True
    return (_now() - last) >= (int(interval_hours) * 3600)

def _notify(msg):
    try:
        control.notification(message=msg)
    except:
        pass

def _page_url(url, page):
    # replace page=xxx
    if 'page=' in url:
        return re.sub(r'page=\d+', 'page=%d' % int(page), url)
    sep = '&' if '?' in url else '?'
    return url + ('%spage=%d' % (sep, int(page)))

def _get_tmdb_links():
    """
    Reads the same TMDB links used by menus (movies.py / tvshows.py).
    Those links already contain api_key=%s placeholder and page=1.
    """
    movie_links = []
    tv_links = []
    try:
        from resources.lib.menus.movies import Movies as MoviesMenu
        m = MoviesMenu()
        movie_links = [
            getattr(m, 'tmdb_popular_link', ''),
            getattr(m, 'tmdb_toprated_link', ''),
            getattr(m, 'tmdb_nowplaying_link', ''),
            getattr(m, 'tmdb_boxoffice_link', ''),
            getattr(m, 'tmdb_upcoming_link', ''),
        ]
        movie_links = [i for i in movie_links if i]
    except:
        log_utils.error()

    try:
        # luc_kodi uses class name `TVshows` (not `TVShows`)
        from resources.lib.menus.tvshows import TVshows as TVShowsMenu
        t = TVShowsMenu()
        tv_links = [
            getattr(t, 'tmdb_popular_link', ''),
            getattr(t, 'tmdb_toprated_link', ''),
            getattr(t, 'tmdb_airingtoday_link', ''),
            # tvshows.py uses tmdb_ontheair_link (not tmdb_ontv_link)
            getattr(t, 'tmdb_ontheair_link', ''),
        ]
        tv_links = [i for i in tv_links if i]
    except Exception:
        # TV precache is optional.
        pass

    return movie_links, tv_links

def precache_tmdb_catalog(pages=3, silent=False):
    """
    Fetches TMDB lists to warm luc_kodi cache.
    Returns True/False.
    """
    try:
        if not silent:
            _notify(control.lang(400701))  # "TMDB Catalog: Starting..."

        # IMPORTANT: luc_kodi implements tmdb_list() on Movies/TVshows, not on TMDb base.
        from resources.lib.indexers.tmdb import Movies as TMDbMovies, TVshows as TMDbTVshows

        movies_idx = TMDbMovies()
        tv_idx = TMDbTVshows()

        movie_links, tv_links = _get_tmdb_links()
        if not (movie_links or tv_links):
            if not silent:
                _notify(control.lang(400704))  # "TMDB Catalog: No TMDB links found."
            return False

        log_utils.log('[luc_kodi] TMDB Catalog: precache start (pages=%s)' % pages, level=LOGINFO)

        for url in movie_links:
            for p in range(1, int(pages) + 1):
                movies_idx.tmdb_list(_page_url(url, p))

        for url in tv_links:
            for p in range(1, int(pages) + 1):
                tv_idx.tmdb_list(_page_url(url, p))

        log_utils.log('[luc_kodi] TMDB Catalog: precache finished', level=LOGINFO)

        if not silent:
            _notify(control.lang(400702))  # "TMDB Catalog: Completed."
        return True
    except Exception:
        log_utils.error()
        if not silent:
            _notify(control.lang(400703))  # "TMDB Catalog: Error (see kodi.log)."
        return False

class CatalogService:
    """
    Background thread: update on startup + every X hours.
    """
    def run(self):
        log_utils.log('[ plugin.video.luc_kodi ]  CatalogService Starting...', level=LOGINFO)

        monitor = control.monitor

        # small delay after Kodi starts to avoid competing with other services
        monitor.waitForAbort(10)

        while not monitor.abortRequested():
            try:
                enabled = _get_bool(S_ENABLED, default=False)
                if enabled:
                    on_start = _get_bool(S_ON_START, default=True)
                    notify = _get_bool(S_NOTIFY, default=True)
                    interval = _get_int(S_INTERVAL, default=6)

                    # On startup: only if never ran before
                    if on_start and _get_last_run() == 0:
                        precache_tmdb_catalog(pages=3, silent=not notify)
                        _set_last_run(_now())
                        try:
                            control.trigger_widget_refresh()
                        except:
                            pass

                    # Scheduled run
                    if _is_due(interval):
                        precache_tmdb_catalog(pages=3, silent=not notify)
                        _set_last_run(_now())
                        try:
                            control.trigger_widget_refresh()
                        except:
                            pass
            except:
                log_utils.error()

            # check again every 5 minutes
            monitor.waitForAbort(CHECK_EVERY_SECONDS)

        log_utils.log('[ plugin.video.luc_kodi ]  CatalogService Stopped', level=LOGINFO)
