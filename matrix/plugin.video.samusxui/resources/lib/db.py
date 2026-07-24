# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import time
import xbmc
import xbmcvfs
import xbmcaddon

_profile = xbmcvfs.translatePath(
    xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('profile'))
_DB_PATH = os.path.join(_profile, 'samus.db')


def _connect():
    os.makedirs(_profile, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
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
    conn.execute('''CREATE TABLE IF NOT EXISTS provider_health (
        provider     TEXT PRIMARY KEY,
        fail_count   INTEGER DEFAULT 0,
        last_fail    REAL DEFAULT 0,
        last_success REAL DEFAULT 0
    )''')
    conn.commit()
    return conn


# ───────────────────────── Favorites ─────────────────────────

def add_favorite(tmdb_id, media_type, title='', year='', poster='', plot=''):
    try:
        conn = _connect()
        conn.execute(
            'INSERT OR IGNORE INTO favorites '
            '(tmdb_id, media_type, title, year, poster, plot) VALUES (?,?,?,?,?,?)',
            (tmdb_id, media_type, title, year, poster, plot)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] add_favorite: {e}', xbmc.LOGERROR)
        return False


def remove_favorite(tmdb_id, media_type):
    try:
        conn = _connect()
        conn.execute('DELETE FROM favorites WHERE tmdb_id=? AND media_type=?',
                     (tmdb_id, media_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] remove_favorite: {e}', xbmc.LOGERROR)
        return False


def get_favorites(media_type=None):
    try:
        conn = _connect()
        if media_type:
            rows = conn.execute(
                'SELECT tmdb_id, media_type, title, year, poster, plot '
                'FROM favorites WHERE media_type=? ORDER BY added_at DESC',
                (media_type,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT tmdb_id, media_type, title, year, poster, plot '
                'FROM favorites ORDER BY added_at DESC'
            ).fetchall()
        conn.close()
        return [{'tmdb_id': r[0], 'media_type': r[1], 'title': r[2],
                 'year': r[3], 'poster': r[4], 'plot': r[5] or ''}
                for r in rows]
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] get_favorites: {e}', xbmc.LOGERROR)
        return []


def get_favorite_ids():
    """Returns a set of (tmdb_id, media_type) tuples."""
    try:
        conn = _connect()
        rows = conn.execute('SELECT tmdb_id, media_type FROM favorites').fetchall()
        conn.close()
        return {(r[0], r[1]) for r in rows}
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] get_favorite_ids: {e}', xbmc.LOGERROR)
        return set()


# ───────────────────────── History ─────────────────────────

def history_upsert(tmdb_id, media_type, title, poster, position, duration,
                   season=None, episode=None, plot=''):
    """Salvează sau actualizează progresul redării. watched=1 dacă >= 90%."""
    try:
        percent  = (position / duration * 100) if duration > 0 else 0
        watched  = 1 if percent >= 90 else 0
        _season  = season  if season  is not None else -1
        _episode = episode if episode is not None else -1
        conn = _connect()
        conn.execute(
            '''INSERT INTO history
               (tmdb_id, media_type, season, episode, title, poster, plot,
                position, duration, percent, watched, updated_at)
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
        xbmc.log(f'[SamusXUI/DB] history_upsert: {e}', xbmc.LOGERROR)


def history_get(tmdb_id, media_type, season=None, episode=None):
    """Returnează intrarea din history pentru un item specific, sau None."""
    try:
        _season  = season  if season  is not None else -1
        _episode = episode if episode is not None else -1
        conn = _connect()
        row = conn.execute(
            'SELECT position, duration, percent, watched FROM history '
            'WHERE tmdb_id=? AND media_type=? AND season=? AND episode=?',
            (tmdb_id, media_type, _season, _episode)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return {'position': row[0], 'duration': row[1],
                'percent': row[2], 'watched': bool(row[3])}
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] history_get: {e}', xbmc.LOGERROR)
        return None


def get_continue_watching(media_type_filter=None):
    """Items unde watched=0 și position >= 300s, ordonate după cel mai recent."""
    try:
        conn  = _connect()
        sql   = ('SELECT tmdb_id, media_type, title, poster, plot, '
                 'season, episode, position, duration '
                 'FROM history WHERE watched=0 AND position >= 300')
        args  = []
        if media_type_filter:
            sql  += ' AND media_type=?'
            args.append(media_type_filter)
        sql += ' ORDER BY updated_at DESC'
        rows  = conn.execute(sql, args).fetchall()
        conn.close()
        return [{
            'tmdb_id':    r[0],
            'media_type': r[1],
            'title':      r[2],
            'poster':     r[3],
            'plot':       r[4] or '',
            'season':     r[5] if r[5] not in (None, -1) else None,
            'episode':    r[6] if r[6] not in (None, -1) else None,
            'position':   r[7] or 0,
            'duration':   r[8] or 0,
        } for r in rows]
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] get_continue_watching: {e}', xbmc.LOGERROR)
        return []


def remove_continue(tmdb_id, media_type):
    try:
        conn = _connect()
        conn.execute('DELETE FROM history WHERE tmdb_id=? AND media_type=?',
                     (tmdb_id, media_type))
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] remove_continue: {e}', xbmc.LOGERROR)


# ───────────────────────── Cache TMDb ─────────────────────────

def cache_get(key, ttl):
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
        xbmc.log(f'[SamusXUI/DB] cache_get({key}): {e}', xbmc.LOGERROR)
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
        xbmc.log(f'[SamusXUI/DB] cache_set({key}): {e}', xbmc.LOGERROR)


def cache_clear():
    try:
        conn = _connect()
        cur = conn.execute('DELETE FROM cache')
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return deleted
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] cache_clear: {e}', xbmc.LOGERROR)
        return 0


# ───────────────────────── Provider health ─────────────────────────

def provider_health_fail(provider, window=1800):
    try:
        conn = _connect()
        now = time.time()
        conn.execute('''
            INSERT INTO provider_health (provider, fail_count, last_fail, last_success)
            VALUES (?, 1, ?, 0)
            ON CONFLICT(provider) DO UPDATE SET
                fail_count = CASE WHEN last_fail >= ? THEN fail_count + 1 ELSE 1 END,
                last_fail  = ?
        ''', (provider, now, now - window, now))
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] provider_health_fail: {e}', xbmc.LOGERROR)


def provider_health_ok(provider):
    try:
        conn = _connect()
        now = time.time()
        conn.execute('''
            INSERT INTO provider_health (provider, fail_count, last_fail, last_success)
            VALUES (?, 0, 0, ?)
            ON CONFLICT(provider) DO UPDATE SET
                fail_count   = 0,
                last_success = ?
        ''', (provider, now, now))
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] provider_health_ok: {e}', xbmc.LOGERROR)


def provider_is_healthy(provider, max_fails=3, window=1800):
    try:
        conn = _connect()
        row = conn.execute(
            'SELECT fail_count, last_fail FROM provider_health WHERE provider=?',
            (provider,)
        ).fetchone()
        conn.close()
        if row is None:
            return True
        fail_count, last_fail = row
        if time.time() - last_fail > window:
            return True
        return fail_count < max_fails
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] provider_is_healthy: {e}', xbmc.LOGERROR)
        return True


def provider_success_set(tmdb_id, media_type, provider):
    if not provider:
        return
    try:
        conn = _connect()
        conn.execute(
            'INSERT OR REPLACE INTO provider_success '
            '(tmdb_id, media_type, provider, used_at) VALUES (?,?,?, CURRENT_TIMESTAMP)',
            (tmdb_id, media_type, provider)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] provider_success_set: {e}', xbmc.LOGERROR)


def provider_success_clear(tmdb_id, media_type):
    try:
        conn = _connect()
        conn.execute('DELETE FROM provider_success WHERE tmdb_id=? AND media_type=?',
                     (tmdb_id, media_type))
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] provider_success_clear: {e}', xbmc.LOGERROR)


def provider_success_get(tmdb_id, media_type):
    try:
        conn = _connect()
        row = conn.execute(
            'SELECT provider FROM provider_success WHERE tmdb_id=? AND media_type=?',
            (tmdb_id, media_type)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        xbmc.log(f'[SamusXUI/DB] provider_success_get: {e}', xbmc.LOGERROR)
        return None
