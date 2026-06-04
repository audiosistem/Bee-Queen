# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Recommendation Feedback DB
	Stores explicit user signals (👍 / 👎) per title and derives
	genre-level weights so the reco engine learns from every interaction.

	Schema
	──────
	feedback(tmdb_id, media_type, title, signal, genres, ts)
	  signal : +1 = like / -1 = dislike (NOT INTERESTED)
	  genres : comma-separated genre names from Trakt/TMDb
	  UNIQUE  : (tmdb_id, media_type)  — one signal per title
"""

from sqlite3 import dbapi2 as db
from time   import time
from resources.lib.modules.control import makeFile, dataPath, joinPath

_DB_FILE = joinPath(dataPath, 'reco_feedback.db')

# ── helpers ──────────────────────────────────────────────────────────────────

def _connect():
	makeFile(dataPath)
	con = db.connect(_DB_FILE)
	con.row_factory = db.Row
	return con

def _ensure_table(cur):
	cur.execute('''
		CREATE TABLE IF NOT EXISTS feedback (
			tmdb_id    TEXT NOT NULL,
			media_type TEXT NOT NULL,
			title      TEXT DEFAULT '',
			signal     INTEGER NOT NULL,
			genres     TEXT DEFAULT '',
			ts         INTEGER NOT NULL,
			PRIMARY KEY (tmdb_id, media_type)
		)
	''')
	# index for fast genre queries
	cur.execute('''
		CREATE INDEX IF NOT EXISTS idx_feedback_mt
		ON feedback (media_type, signal)
	''')

# ── public API ────────────────────────────────────────────────────────────────

def set_signal(tmdb_id, title, signal, media_type, genres=''):
	"""
	Save or overwrite a feedback signal for a title.
	  signal : +1 (like) | -1 (dislike)
	  genres : comma-separated string  e.g. 'action,thriller'
	"""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute('''
			INSERT INTO feedback (tmdb_id, media_type, title, signal, genres, ts)
			VALUES (?, ?, ?, ?, ?, ?)
			ON CONFLICT(tmdb_id, media_type) DO UPDATE SET
				signal = excluded.signal,
				title  = excluded.title,
				genres = excluded.genres,
				ts     = excluded.ts
		''', (str(tmdb_id), str(media_type), str(title), int(signal), str(genres), int(time())))
		con.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: con.close()
		except Exception: pass

def get_signal(tmdb_id, media_type):
	"""Return +1, -1, or 0 (no feedback) for a specific title."""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		row = cur.execute(
			'SELECT signal FROM feedback WHERE tmdb_id=? AND media_type=?',
			(str(tmdb_id), str(media_type))
		).fetchone()
		return int(row['signal']) if row else 0
	except Exception:
		return 0
	finally:
		try: con.close()
		except Exception: pass

def get_blocked_ids(media_type):
	"""Return set of tmdb_ids the user marked as 'not interested' (signal=-1)."""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		rows = cur.execute(
			'SELECT tmdb_id FROM feedback WHERE media_type=? AND signal=-1',
			(str(media_type),)
		).fetchall()
		return {r['tmdb_id'] for r in rows}
	except Exception:
		return set()
	finally:
		try: con.close()
		except Exception: pass

def get_genre_weights(media_type):
	"""
	Derive genre preference weights from all stored feedback.
	Liked items contribute +1.5 per genre, disliked items -1.0.
	Returns dict {genre_name: weight}.
	"""
	weights = {}
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		rows = cur.execute(
			'SELECT signal, genres FROM feedback WHERE media_type=? AND genres != ""',
			(str(media_type),)
		).fetchall()
		for row in rows:
			w   = 1.5 if row['signal'] == 1 else -1.0
			for g in (row['genres'] or '').split(','):
				g = g.strip().lower()
				if g:
					weights[g] = weights.get(g, 0.0) + w
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: con.close()
		except Exception: pass
	return weights

def get_all(media_type=None):
	"""Return all feedback rows, optionally filtered by media_type. For settings UI."""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		if media_type:
			rows = cur.execute(
				'SELECT * FROM feedback WHERE media_type=? ORDER BY ts DESC',
				(str(media_type),)
			).fetchall()
		else:
			rows = cur.execute('SELECT * FROM feedback ORDER BY ts DESC').fetchall()
		return [dict(r) for r in rows]
	except Exception:
		return []
	finally:
		try: con.close()
		except Exception: pass

def remove_signal(tmdb_id, media_type):
	"""Remove feedback for a specific title (reset to neutral)."""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute(
			'DELETE FROM feedback WHERE tmdb_id=? AND media_type=?',
			(str(tmdb_id), str(media_type))
		)
		con.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: con.close()
		except Exception: pass

def clear_all():
	"""Wipe all feedback. Called from cache clear tools."""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute('DELETE FROM feedback')
		con.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: con.close()
		except Exception: pass
