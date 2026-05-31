# -*- coding: utf-8 -*-

import json
import os
import sqlite3
import time
import xbmc
import xbmcvfs
import xbmcaddon

_addon = xbmcaddon.Addon()
_profile = xbmcvfs.translatePath(_addon.getAddonInfo('profile'))
_DB_PATH = os.path.join(_profile, 'samus.db')


def _connect():
    os.makedirs(_profile, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tmdb_id     INTEGER NOT NULL,
        media_type  TEXT NOT NULL,
        title       TEXT DEFAULT '',
        year        TEXT DEFAULT '',
        poster      TEXT DEFAULT '',
        plot        TEXT DEFAULT '',
        added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tmdb_id, media_type)
    )''')
    try:
        conn.execute('ALTER TABLE favorites ADD COLUMN plot TEXT DEFAULT ""')
        conn.commit()
    except Exception:
        pass
    conn.execute('''CREATE TABLE IF NOT EXISTS cache (
        key   TEXT PRIMARY KEY,
        data  TEXT NOT NULL,
        ts    REAL NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tmdb_id     INTEGER NOT NULL,
        media_type  TEXT NOT NULL,
        season      INTEGER NOT NULL DEFAULT -1,
        episode     INTEGER NOT NULL DEFAULT -1,
        title       TEXT DEFAULT '',
        poster      TEXT DEFAULT '',
        plot        TEXT DEFAULT '',
        position    REAL DEFAULT 0,
        duration    REAL DEFAULT 0,
        percent     REAL DEFAULT 0,
        watched     INTEGER DEFAULT 0,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tmdb_id, media_type, season, episode)
    )''')
    try:
        conn.execute('ALTER TABLE history ADD COLUMN plot TEXT DEFAULT ""')
        conn.commit()
    except Exception:
        pass
    # Migrare: deduplichetă rândurile cu NULL (bug SQLite UNIQUE + NULL)
    # și normalizează NULL → -1 pentru season/episode
    try:
        conn.execute('''
            DELETE FROM history WHERE id NOT IN (
                SELECT MAX(id) FROM history
                GROUP BY tmdb_id, media_type,
                         COALESCE(season, -1), COALESCE(episode, -1)
            )
        ''')
        conn.execute('UPDATE history SET season=-1 WHERE season IS NULL')
        conn.execute('UPDATE history SET episode=-1 WHERE episode IS NULL')
        conn.commit()
    except Exception:
        pass
    conn.execute('''CREATE TABLE IF NOT EXISTS provider_success (
        tmdb_id     INTEGER NOT NULL,
        media_type  TEXT NOT NULL,
        provider    TEXT NOT NULL,
        used_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (tmdb_id, media_type)
    )''')
    conn.commit()
    return conn


# ───────────────────────── Provider success memory ─────────────────────────

def provider_success_set(tmdb_id, media_type, provider):
    """Remember which provider worked last for this title."""
    if not provider:
        return
    try:
        conn = _connect()
        conn.execute(
            'INSERT OR REPLACE INTO provider_success (tmdb_id, media_type, provider, used_at) '
            'VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            (tmdb_id, media_type, provider)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"[Samus/DB] provider_success_set: {e}", xbmc.LOGERROR)


def provider_success_get(tmdb_id, media_type):
    """Return last working provider tag for this title, or None."""
    try:
        conn = _connect()
        row = conn.execute(
            'SELECT provider FROM provider_success WHERE tmdb_id=? AND media_type=?',
            (tmdb_id, media_type)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        xbmc.log(f"[Samus/DB] provider_success_get: {e}", xbmc.LOGERROR)
        return None


# ───────────────────────── Favorites ─────────────────────────

def add_favorite(tmdb_id, media_type, title='', year='', poster='', plot=''):
    try:
        conn = _connect()
        conn.execute(
            'INSERT OR IGNORE INTO favorites (tmdb_id, media_type, title, year, poster, plot) VALUES (?,?,?,?,?,?)',
            (tmdb_id, media_type, title, year, poster, plot)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        xbmc.log(f"[Samus/DB] add_favorite: {e}", xbmc.LOGERROR)
        return False


def remove_favorite(tmdb_id, media_type):
    try:
        conn = _connect()
        conn.execute('DELETE FROM favorites WHERE tmdb_id=? AND media_type=?', (tmdb_id, media_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        xbmc.log(f"[Samus/DB] remove_favorite: {e}", xbmc.LOGERROR)
        return False


def is_favorite(tmdb_id, media_type):
    try:
        conn = _connect()
        cur = conn.execute(
            'SELECT 1 FROM favorites WHERE tmdb_id=? AND media_type=?', (tmdb_id, media_type)
        )
        result = cur.fetchone() is not None
        conn.close()
        return result
    except Exception as e:
        xbmc.log(f"[Samus/DB] is_favorite: {e}", xbmc.LOGERROR)
        return False


def get_favorites(media_type=None):
    try:
        conn = _connect()
        if media_type:
            cur = conn.execute(
                'SELECT tmdb_id, media_type, title, year, poster, plot FROM favorites '
                'WHERE media_type=? ORDER BY added_at DESC',
                (media_type,)
            )
        else:
            cur = conn.execute(
                'SELECT tmdb_id, media_type, title, year, poster, plot FROM favorites '
                'ORDER BY added_at DESC'
            )
        rows = cur.fetchall()
        conn.close()
        return [{'tmdb_id': r[0], 'media_type': r[1], 'title': r[2], 'year': r[3], 'poster': r[4], 'plot': r[5] or ''}
                for r in rows]
    except Exception as e:
        xbmc.log(f"[Samus/DB] get_favorites: {e}", xbmc.LOGERROR)
        return []


# ───────────────────────── TMDb Cache ─────────────────────────

def cache_get(key, ttl):
    """Returns cached data if it exists and hasn't expired, otherwise None."""
    try:
        conn = _connect()
        row = conn.execute('SELECT data, ts FROM cache WHERE key=?', (key,)).fetchone()
        conn.close()
        if row is None:
            return None
        data_str, ts = row
        if time.time() - ts > ttl:
            return None
        return json.loads(data_str)
    except Exception as e:
        xbmc.log(f"[Samus/DB] cache_get({key}): {e}", xbmc.LOGERROR)
        return None


def cache_set(key, data):
    try:
        conn = _connect()
        conn.execute(
            'INSERT OR REPLACE INTO cache (key, data, ts) VALUES (?,?,?)',
            (key, json.dumps(data, ensure_ascii=False), time.time())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"[Samus/DB] cache_set({key}): {e}", xbmc.LOGERROR)


def cache_clear():
    try:
        conn = _connect()
        cur = conn.execute('DELETE FROM cache')
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return deleted
    except Exception as e:
        xbmc.log(f"[Samus/DB] cache_clear: {e}", xbmc.LOGERROR)
        return 0


# ───────────────────────── History ─────────────────────────

def history_upsert(tmdb_id, media_type, title, poster, position, duration,
                   season=None, episode=None, plot=''):
    """Save or update playback progress. Marks as watched if position >= 90% of duration."""
    try:
        percent  = (position / duration * 100) if duration > 0 else 0
        watched  = 1 if percent >= 90 else 0
        _season  = season  if season  is not None else -1
        _episode = episode if episode is not None else -1
        conn = _connect()
        conn.execute(
            '''INSERT INTO history
               (tmdb_id, media_type, season, episode, title, poster, plot, position, duration, percent, watched, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
               ON CONFLICT(tmdb_id, media_type, season, episode) DO UPDATE SET
                 title=excluded.title, poster=excluded.poster,
                 plot=excluded.plot,
                 position=excluded.position, duration=excluded.duration,
                 percent=excluded.percent,
                 watched=MAX(watched, excluded.watched),
                 updated_at=CURRENT_TIMESTAMP''',
            (tmdb_id, media_type, _season, _episode, title, poster, plot,
             position, duration, percent, watched)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"[Samus/DB] history_upsert: {e}", xbmc.LOGERROR)


def history_get(tmdb_id, media_type, season=None, episode=None):
    """Returns the history entry for a specific item, or None."""
    try:
        _season  = season  if season  is not None else -1
        _episode = episode if episode is not None else -1
        conn = _connect()
        cur = conn.execute(
            'SELECT position, duration, percent, watched FROM history '
            'WHERE tmdb_id=? AND media_type=? AND season=? AND episode=?',
            (tmdb_id, media_type, _season, _episode)
        )
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return {'position': row[0], 'duration': row[1], 'percent': row[2], 'watched': bool(row[3])}
    except Exception as e:
        xbmc.log(f"[Samus/DB] history_get: {e}", xbmc.LOGERROR)
        return None


def history_get_all(limit=30):
    """Returns the most recently played items (distinct tmdb_id + media_type + season/episode)."""
    try:
        conn = _connect()
        cur = conn.execute(
            '''SELECT tmdb_id, media_type, season, episode, title, poster, plot, position, duration, percent, watched
               FROM history
               WHERE watched=0
               ORDER BY updated_at DESC
               LIMIT ?''',
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                'tmdb_id':    r[0],
                'media_type': r[1],
                'season':     r[2] if r[2] != -1 else None,
                'episode':    r[3] if r[3] != -1 else None,
                'title':      r[4], 'poster': r[5],
                'plot':       r[6] or '',
                'position':   r[7], 'duration': r[8],
                'percent':    r[9], 'watched': bool(r[10]),
            }
            for r in rows
        ]
    except Exception as e:
        xbmc.log(f"[Samus/DB] history_get_all: {e}", xbmc.LOGERROR)
        return []


def history_remove(tmdb_id, media_type):
    try:
        conn = _connect()
        conn.execute('DELETE FROM history WHERE tmdb_id=? AND media_type=?', (tmdb_id, media_type))
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"[Samus/DB] history_remove: {e}", xbmc.LOGERROR)
