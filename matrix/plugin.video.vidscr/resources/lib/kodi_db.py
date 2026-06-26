# -*- coding: utf-8 -*-
"""Resume / Watched indicators.

Two data sources are merged:
  1. The user's Kodi MyVideos.db (if the item happens to be in the local
     library and the user enabled the toggle).
  2. An addon-local SQLite store at ``profile/watched.db`` so we can mark
     items the user played through Vidscr (and sync from Trakt).
"""
import os
import sqlite3
import glob
import time

import xbmcvfs

from .common import PROFILE_PATH, log, get_setting_bool, get_setting_int


WATCHED_DB = os.path.join(PROFILE_PATH, 'watched.db')


def _conn():
    c = sqlite3.connect(WATCHED_DB, timeout=5)
    c.execute("""CREATE TABLE IF NOT EXISTS movies (
                    imdb TEXT, tmdb TEXT, played_at INT, position INT, total INT,
                    watched INT DEFAULT 0,
                    PRIMARY KEY (imdb, tmdb))""")
    c.execute("""CREATE TABLE IF NOT EXISTS episodes (
                    imdb TEXT, tmdb TEXT, season INT, episode INT,
                    played_at INT, position INT, total INT,
                    watched INT DEFAULT 0,
                    PRIMARY KEY (imdb, tmdb, season, episode))""")
    return c


# ---------- Update from playback ----------

def record_progress(media_type, imdb=None, tmdb=None, season=None, episode=None,
                    position=0, total=0):
    try:
        c = _conn()
        watched = 0
        try:
            pct = (position / total * 100.0) if total else 0
        except Exception:
            pct = 0
        if pct >= get_setting_int('resume_threshold_pct', 90):
            watched = 1
        if media_type == 'movie':
            c.execute("""INSERT OR REPLACE INTO movies
                            (imdb, tmdb, played_at, position, total, watched)
                            VALUES (?,?,?,?,?,?)""",
                      (imdb or '', str(tmdb or ''), int(time.time()),
                       int(position), int(total), watched))
        else:
            c.execute("""INSERT OR REPLACE INTO episodes
                            (imdb, tmdb, season, episode, played_at, position, total, watched)
                            VALUES (?,?,?,?,?,?,?,?)""",
                      (imdb or '', str(tmdb or ''), int(season or 0), int(episode or 0),
                       int(time.time()), int(position), int(total), watched))
        c.commit()
        c.close()
    except Exception as e:
        log('kodi_db record_progress: %s' % e)


def bulk_mark_watched_movies(keys):
    """``keys`` is a set of IMDB ids or 'tmdb:<id>' strings."""
    try:
        c = _conn()
        for k in keys:
            if k.startswith('tmdb:'):
                c.execute("""INSERT OR IGNORE INTO movies (imdb, tmdb, played_at, position, total, watched)
                                VALUES ('', ?, ?, 0, 0, 1)""", (k[5:], int(time.time())))
                c.execute("""UPDATE movies SET watched=1 WHERE tmdb=?""", (k[5:],))
            else:
                c.execute("""INSERT OR IGNORE INTO movies (imdb, tmdb, played_at, position, total, watched)
                                VALUES (?, '', ?, 0, 0, 1)""", (k, int(time.time())))
                c.execute("""UPDATE movies SET watched=1 WHERE imdb=?""", (k,))
        c.commit()
        c.close()
    except Exception as e:
        log('kodi_db bulk movies: %s' % e)


def bulk_mark_watched_episodes(shows):
    """``shows`` is dict { imdb_or_tmdb_key: { season: set(episodes) } }."""
    try:
        c = _conn()
        for key, seasons in shows.items():
            is_tmdb = key.startswith('tmdb:')
            imdb = '' if is_tmdb else key
            tmdb = key[5:] if is_tmdb else ''
            for sn, eps in seasons.items():
                for en in eps:
                    c.execute("""INSERT OR REPLACE INTO episodes
                                    (imdb, tmdb, season, episode, played_at, position, total, watched)
                                    VALUES (?,?,?,?,?,0,0,1)""",
                              (imdb, tmdb, int(sn or 0), int(en or 0), int(time.time())))
        c.commit()
        c.close()
    except Exception as e:
        log('kodi_db bulk episodes: %s' % e)


def export_watched_movies():
    """Return list of watched movies for sync push (Bingebase / future integrations)."""
    out = []
    try:
        c = _conn()
        for row in c.execute(
                """SELECT imdb, tmdb, played_at FROM movies WHERE watched=1"""):
            imdb, tmdb, played_at = row
            iso = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                time.gmtime(int(played_at or 0))) if played_at else ''
            out.append({
                'imdb': imdb or '',
                'tmdb': tmdb or '',
                'playcount': 1,
                'lastplayed': iso,
                'title': '',
                'year': 0,
            })
        c.close()
    except Exception as e:
        log('kodi_db export_watched_movies: %s' % e)
    return out


def export_watched_episodes():
    """Return list of watched episodes for sync push (Bingebase / future integrations)."""
    out = []
    try:
        c = _conn()
        for row in c.execute(
                """SELECT imdb, tmdb, season, episode, played_at
                   FROM episodes WHERE watched=1"""):
            imdb, tmdb, season, episode, played_at = row
            iso = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                time.gmtime(int(played_at or 0))) if played_at else ''
            out.append({
                'imdb': imdb or '',
                'tmdb': tmdb or '',
                'show_imdb': imdb or '',
                'show_tmdb': tmdb or '',
                'season': int(season or 0),
                'episode': int(episode or 0),
                'playcount': 1,
                'lastplayed': iso,
                'title': '',
                'tvshowtitle': '',
            })
        c.close()
    except Exception as e:
        log('kodi_db export_watched_episodes: %s' % e)
    return out


def clear_all():
    try:
        if os.path.exists(WATCHED_DB):
            os.remove(WATCHED_DB)
    except Exception:
        pass


def bulk_record_resume_movies(items):
    """Import Trakt /sync/playback/movies into local store."""
    try:
        c = _conn()
        for it in items:
            ids = ((it.get('movie') or {}).get('ids')) or {}
            imdb = ids.get('imdb') or ''
            tmdb = str(ids.get('tmdb') or '')
            progress = float(it.get('progress') or 0)
            # Trakt returns progress as percentage. Use 100 minutes as a sane
            # placeholder runtime so the % math works downstream.
            total = 6000
            pos = int((progress / 100.0) * total)
            c.execute("""INSERT OR REPLACE INTO movies
                            (imdb, tmdb, played_at, position, total, watched)
                            VALUES (?,?,?,?,?,0)""",
                      (imdb, tmdb, int(time.time()), pos, total))
        c.commit(); c.close()
    except Exception as e:
        log('kodi_db bulk_record_resume_movies: %s' % e)


def bulk_record_resume_episodes(items):
    """Import Trakt /sync/playback/episodes into local store."""
    try:
        c = _conn()
        for it in items:
            show_ids = ((it.get('show') or {}).get('ids')) or {}
            imdb = show_ids.get('imdb') or ''
            tmdb = str(show_ids.get('tmdb') or '')
            ep = it.get('episode') or {}
            sn = int(ep.get('season') or 0)
            en = int(ep.get('number') or 0)
            progress = float(it.get('progress') or 0)
            total = 6000
            pos = int((progress / 100.0) * total)
            c.execute("""INSERT OR REPLACE INTO episodes
                            (imdb, tmdb, season, episode, played_at, position, total, watched)
                            VALUES (?,?,?,?,?,?,?,0)""",
                      (imdb, tmdb, sn, en, int(time.time()), pos, total))
        c.commit(); c.close()
    except Exception as e:
        log('kodi_db bulk_record_resume_episodes: %s' % e)


def get_continue_watching_movies(limit=30):
    """Movies with resume position but not watched, newest first.

    Returns list of dicts: {'tmdb': str, 'imdb': str, 'position': int,
    'total': int, 'played_at': int}.
    """
    out = []
    try:
        c = _conn()
        rows = c.execute("""SELECT imdb, tmdb, position, total, played_at FROM movies
                              WHERE watched=0 AND position>30
                              ORDER BY played_at DESC LIMIT ?""", (limit,)).fetchall()
        c.close()
        for imdb, tmdb, pos, total, ts in rows:
            out.append({'imdb': imdb, 'tmdb': tmdb, 'position': pos,
                        'total': total, 'played_at': ts})
    except Exception as e:
        log('kodi_db get_continue_watching_movies: %s' % e)
    return out


def get_continue_watching_shows(limit=30):
    """For each show with any progress, return the next episode to watch.

    Algorithm:
      1. Get every episode row for the show.
      2. If there is an episode with a resume position (not watched), pick
         the most recently played one.
      3. Otherwise pick the lowest (season, episode) immediately after the
         highest watched (season, episode).

    Returns list of dicts: {'tmdb': str, 'imdb': str, 'season': int,
    'episode': int, 'position': int, 'total': int, 'played_at': int}.
    """
    out = []
    try:
        c = _conn()
        rows = c.execute("""SELECT imdb, tmdb, season, episode, played_at,
                                   position, total, watched
                              FROM episodes
                              ORDER BY played_at DESC""").fetchall()
        c.close()
        # Group by show key.
        shows = {}
        for imdb, tmdb, sn, en, ts, pos, total, w in rows:
            key = ('imdb:%s' % imdb) if imdb else ('tmdb:%s' % tmdb)
            shows.setdefault(key, {'imdb': imdb, 'tmdb': tmdb, 'rows': []})
            shows[key]['rows'].append((int(sn), int(en), int(ts or 0),
                                        int(pos or 0), int(total or 0), int(w or 0)))
        for key, blob in shows.items():
            in_progress = [r for r in blob['rows'] if r[5] == 0 and r[3] > 30]
            chosen = None
            if in_progress:
                in_progress.sort(key=lambda r: r[2], reverse=True)
                chosen = in_progress[0]
            else:
                watched = sorted([r for r in blob['rows'] if r[5] == 1])
                if watched:
                    last = watched[-1]
                    chosen = (last[0], last[1] + 1, last[2], 0, 0, 0)
            if chosen:
                out.append({
                    'imdb': blob['imdb'], 'tmdb': blob['tmdb'],
                    'season': chosen[0], 'episode': chosen[1],
                    'played_at': chosen[2],
                    'position': chosen[3], 'total': chosen[4],
                })
        out.sort(key=lambda x: x.get('played_at', 0), reverse=True)
        return out[:limit]
    except Exception as e:
        log('kodi_db get_continue_watching_shows: %s' % e)
    return out


# ---------- Lookup ----------

def get_movie_state(imdb=None, tmdb=None):
    """Return (watched_bool, resume_seconds, total_seconds)."""
    try:
        c = _conn()
        row = c.execute("""SELECT watched, position, total FROM movies
                              WHERE (imdb=? AND imdb<>'') OR (tmdb=? AND tmdb<>'') LIMIT 1""",
                        (imdb or '', str(tmdb or ''))).fetchone()
        c.close()
        if row:
            return bool(row[0]), int(row[1] or 0), int(row[2] or 0)
    except Exception as e:
        log('kodi_db get_movie_state: %s' % e)

    if get_setting_bool('use_kodi_library_db', True) and imdb:
        st = _kodi_lib_movie_state(imdb)
        if st:
            return st
    return False, 0, 0


def get_episode_state(imdb=None, tmdb=None, season=None, episode=None):
    try:
        c = _conn()
        row = c.execute("""SELECT watched, position, total FROM episodes
                              WHERE ((imdb=? AND imdb<>'') OR (tmdb=? AND tmdb<>''))
                                AND season=? AND episode=? LIMIT 1""",
                        (imdb or '', str(tmdb or ''),
                         int(season or 0), int(episode or 0))).fetchone()
        c.close()
        if row:
            return bool(row[0]), int(row[1] or 0), int(row[2] or 0)
    except Exception as e:
        log('kodi_db get_episode_state: %s' % e)
    return False, 0, 0


def get_show_progress(imdb=None, tmdb=None):
    """Return dict { season: { episode: (watched, position, total) } }."""
    out = {}
    try:
        c = _conn()
        rows = c.execute("""SELECT season, episode, watched, position, total FROM episodes
                               WHERE (imdb=? AND imdb<>'') OR (tmdb=? AND tmdb<>'')""",
                         (imdb or '', str(tmdb or ''))).fetchall()
        c.close()
        for sn, en, w, p, t in rows:
            out.setdefault(int(sn), {})[int(en)] = (bool(w), int(p or 0), int(t or 0))
    except Exception as e:
        log('kodi_db get_show_progress: %s' % e)
    return out


# ---------- Kodi library DB integration ----------

def _kodi_videos_db_path():
    """Locate the most recent MyVideos*.db under userdata/Database."""
    try:
        base = xbmcvfs.translatePath('special://userdata/Database/')
        cands = sorted(glob.glob(os.path.join(base, 'MyVideos*.db')))
        return cands[-1] if cands else None
    except Exception:
        return None


def _kodi_lib_movie_state(imdb):
    path = _kodi_videos_db_path()
    if not path or not os.path.exists(path):
        return None
    try:
        c = sqlite3.connect(path, timeout=2)
        # uniqueid table holds 'imdb' / 'tmdb' references on Kodi 19+.
        row = c.execute("""SELECT b.timeInSeconds, b.totalTimeInSeconds, m.playCount
                             FROM movie m
                             LEFT JOIN bookmark b ON b.idFile=m.idFile AND b.type=1
                             LEFT JOIN uniqueid u ON u.media_id=m.idMovie AND u.media_type='movie'
                             WHERE u.value=? LIMIT 1""", (imdb,)).fetchone()
        c.close()
        if row:
            pos = int(row[0] or 0)
            total = int(row[1] or 0)
            watched = int(row[2] or 0) > 0
            return watched, pos, total
    except Exception as e:
        log('kodi_lib_movie_state: %s' % e)
    return None


# ---------- Listing helpers ----------

def label_marker(state):
    """Return a Kodi-skin colour marker for a (watched, pos, total) tuple."""
    if not state:
        return ''
    watched, pos, total = state
    if watched:
        return '[COLOR FF45D267]✓[/COLOR] '
    if pos > 30 and total > 0:
        try:
            pct = int(pos / total * 100)
        except Exception:
            pct = 0
        return '[COLOR FFFFA726]▶ %d%%[/COLOR] ' % pct
    if pos > 30:
        return '[COLOR FFFFA726]▶[/COLOR] '
    return ''
