# -*- coding: utf-8 -*-
"""Extra discovery features for the Movies / TV submenus.

Implements (all called from default.py):
  * on_deck()               — TV shows with a new episode aired since you
                              last watched.
  * holiday_movies()        — Auto-rotating holiday row for Movies.
  * holiday_tv()            — Auto-rotating holiday row for TV Shows.
  * active_holiday()        — Returns the active holiday config dict or None.
  * ambient_launch()        — Builds a local fanart folder from your last-
                              watched titles and starts Kodi's built-in
                              slideshow over it.
"""
import datetime
import os
import time

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from .common import (HANDLE, ICON, FANART, PROFILE_PATH, build_url, add_dir,
                     end_directory, notify, log)
from . import tmdb as T
from . import kodi_db as KDB
from . import listing as L


# ----------------------------------------------------------------- Holiday

# (month_from, day_from) inclusive to (month_to, day_to) inclusive.
HOLIDAYS = [
    {
        'key': 'halloween',
        'label_movies': 'Halloween Horror',
        'label_tv': 'Halloween Horror',
        'range': ((10, 1), (10, 31)),
        # Horror genre (27) sorted by popularity; works for movie & tv.
        'movie_params': {'with_genres': '27', 'sort_by': 'popularity.desc',
                         'vote_count.gte': '50'},
        'tv_params': {'with_genres': '9648,27', 'sort_by': 'popularity.desc',
                      'vote_count.gte': '30'},
    },
    {
        'key': 'christmas',
        'label_movies': 'Christmas',
        'label_tv': 'Christmas',
        'range': ((11, 15), (12, 31)),
        # TMDB keyword 207317 = "christmas"
        'movie_params': {'with_keywords': '207317', 'sort_by': 'popularity.desc',
                         'vote_count.gte': '20'},
        'tv_params': {'with_keywords': '207317', 'sort_by': 'popularity.desc'},
    },
    {
        'key': 'valentines',
        'label_movies': "Valentine's Romance",
        'label_tv': "Valentine's Romance",
        'range': ((2, 1), (2, 14)),
        # Romance genre id 10749 (movie) / 10749 not valid for TV — use keyword 9799 "romantic".
        'movie_params': {'with_genres': '10749', 'sort_by': 'popularity.desc',
                         'vote_count.gte': '100'},
        'tv_params': {'with_keywords': '9799', 'sort_by': 'popularity.desc'},
    },
]


def _in_range(today, mdfrom, mdto):
    mf, df = mdfrom
    mt, dt = mdto
    start = datetime.date(today.year, mf, df)
    end = datetime.date(today.year, mt, dt)
    return start <= today <= end


def active_holiday():
    today = datetime.date.today()
    for h in HOLIDAYS:
        if _in_range(today, *h['range']):
            return h
    return None


def holiday_movies(page=1):
    h = active_holiday()
    if not h:
        notify('No active seasonal row today')
        end_directory(''); return
    data = T.discover_movies(h['movie_params'], page=page)
    L.list_movies(data, next_action='holiday_movies')


def holiday_tv(page=1):
    h = active_holiday()
    if not h:
        notify('No active seasonal row today')
        end_directory(''); return
    data = T.discover_tv(h['tv_params'], page=page)
    L.list_tv(data, next_action='holiday_tv')


# ----------------------------------------------------------------- On Deck

def on_deck():
    """Shows with a newer episode aired since the last one you watched.

    Heuristic:
      For every show that has any watched/in-progress episode in our store,
      ask TMDB for tv_details and look at `last_episode_to_air`. If that
      episode (s, e) is AFTER the user's last watched episode -> the show is
      "on deck".
    """
    xbmcplugin.setContent(HANDLE, 'tvshows')
    items = _collect_on_deck()
    if not items:
        notify('Nothing on deck — no new episodes since your last watch',
               time=3000)
        end_directory('tvshows'); return
    for it in items:
        show = it['show']
        nep = it['next']
        label = '%s  (new: S%02dE%02d)' % (show.get('name') or '',
                                            nep['s'], nep['e'])
        li = xbmcgui.ListItem(label=label)
        li.setArt({
            'thumb': T.poster(show.get('poster_path')),
            'poster': T.poster(show.get('poster_path')),
            'fanart': T.backdrop(show.get('backdrop_path')) or FANART,
            'icon': T.poster(show.get('poster_path')) or ICON,
        })
        try:
            li.setInfo('video', {
                'title': show.get('name') or '',
                'tvshowtitle': show.get('name') or '',
                'plot': show.get('overview') or '',
                'premiered': show.get('first_air_date', ''),
                'mediatype': 'tvshow',
            })
        except Exception:
            pass
        url = build_url(action='tv_seasons', tmdb_id=show['id'],
                        title=show.get('name', ''))
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    end_directory('tvshows')


def _collect_on_deck(limit=50):
    out = []
    try:
        progress = _watched_shows_summary()
        # Hard cap on TMDB calls per visit.
        budget = min(len(progress), 30)
        for tmdb_id, last_sw in list(progress.items())[:budget]:
            try:
                show = T.tv_details(tmdb_id)
            except Exception:
                continue
            lea = show.get('last_episode_to_air') or {}
            ls = int(lea.get('season_number') or 0)
            le = int(lea.get('episode_number') or 0)
            if not (ls and le):
                continue
            # Only count if latest aired episode has already aired (not future).
            airdate = lea.get('air_date') or ''
            if airdate:
                try:
                    aired_on = datetime.date.fromisoformat(airdate)
                    if aired_on > datetime.date.today():
                        continue
                except Exception:
                    pass
            if (ls, le) > last_sw:
                out.append({
                    'show': show,
                    'next': {'s': ls, 'e': le},
                    '_aired': airdate,
                })
        out.sort(key=lambda x: x.get('_aired') or '', reverse=True)
    except Exception as e:
        log('on_deck collect failed: %s' % e)
    return out[:limit]


def _watched_shows_summary():
    """Return { tmdb_id_str: (max_watched_season, max_watched_episode) }.

    Uses the addon-local watched store. We only consider rows where the
    episode is fully watched (watched=1).
    """
    import sqlite3
    out = {}
    try:
        c = sqlite3.connect(KDB.WATCHED_DB, timeout=3)
        rows = c.execute("""SELECT tmdb, season, episode FROM episodes
                              WHERE watched=1 AND tmdb<>''""").fetchall()
        c.close()
        for tmdb, sn, en in rows:
            cur = out.get(tmdb)
            key = (int(sn or 0), int(en or 0))
            if not cur or key > cur:
                out[tmdb] = key
    except Exception as e:
        log('watched_shows_summary: %s' % e)
    return out


# ----------------------------------------------------------------- Ambient

AMBIENT_DIR = os.path.join(PROFILE_PATH, 'ambient')


def ambient_launch():
    """Download fanart of the last 30 watched movies/episodes into a local
    folder, then fire Kodi's built-in picture slideshow over it."""
    try:
        xbmcvfs.mkdirs(AMBIENT_DIR)
    except Exception:
        pass
    count = _refresh_ambient_folder()
    if count == 0:
        notify('Watch something first — ambient has no fanart yet', time=4000)
        return
    notify('Ambient Mode: %d backdrops — starting slideshow' % count, time=2500)
    xbmc.sleep(400)
    # Kodi built-in slideshow. random + no pause = continuous loop.
    xbmc.executebuiltin('SlideShow(%s,,notrandom,pause)' % AMBIENT_DIR)


def _refresh_ambient_folder():
    """Populate AMBIENT_DIR with JPEGs. Returns the count present after sync.

    Only re-downloads a file if it does not already exist. Clears anything
    that is no longer in the top-30 recently-played set.
    """
    import requests
    desired = {}
    try:
        # Movies
        for m in KDB.get_continue_watching_movies(limit=15):
            tmdb = m.get('tmdb')
            if not tmdb:
                continue
            try:
                det = T.movie_details(tmdb)
                url = T.backdrop(det.get('backdrop_path'))
            except Exception:
                url = ''
            if url:
                desired['m_%s.jpg' % tmdb] = url
        # TV (use show backdrop — per-episode would thrash the folder)
        for s in KDB.get_continue_watching_shows(limit=15):
            tmdb = s.get('tmdb')
            if not tmdb:
                continue
            try:
                det = T.tv_details(tmdb)
                url = T.backdrop(det.get('backdrop_path'))
            except Exception:
                url = ''
            if url:
                desired['t_%s.jpg' % tmdb] = url
    except Exception as e:
        log('ambient desired build failed: %s' % e)

    existing = set()
    try:
        for n in os.listdir(AMBIENT_DIR):
            existing.add(n)
    except Exception:
        pass

    # Delete stale
    for stale in existing - set(desired.keys()):
        try:
            os.remove(os.path.join(AMBIENT_DIR, stale))
        except Exception:
            pass

    # Download missing
    for name, url in desired.items():
        target = os.path.join(AMBIENT_DIR, name)
        if os.path.exists(target) and os.path.getsize(target) > 1024:
            continue
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and r.content:
                with open(target, 'wb') as f:
                    f.write(r.content)
        except Exception as e:
            log('ambient dl %s failed: %s' % (url, e))

    try:
        return len([n for n in os.listdir(AMBIENT_DIR)
                    if n.lower().endswith('.jpg')])
    except Exception:
        return 0
