# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on - SIMKL local sync database
	==============================================
	Espejo de traktsync.py pero con tablas alineadas al shape de la API SIMKL.

	Tablas:
	  - bookmarks         : playbacks pausados (paridad con traktsync.bookmarks)
	  - watched_movies    : películas marcadas como vistas (indicators source)
	  - watched_shows     : shows + episodios vistos
	  - movies_watchlist  : watchlist movies (status=plantowatch)
	  - shows_watchlist   : watchlist shows
	  - anime_watchlist   : watchlist anime
	  - service           : pares clave-valor de meta (last_paused_at, etc.)
	  - cache             : tabla cache (clave hash → valor serializado)
"""

from ast import literal_eval
from hashlib import md5
from re import sub as re_sub
from time import time

from datetime import datetime, timezone
from sqlite3 import dbapi2 as db
from resources.lib.modules import cleandate
from resources.lib.modules.control import existsPath, dataPath, makeFile, simklSyncFile


# ---------------------------------------------------------------------------
# Bookmarks (paused playbacks)
# ---------------------------------------------------------------------------
def fetch_bookmarks(imdb, tmdb='', tvdb='', season=None, episode=None, ret_all=None, ret_type='movies'):
	progress = '0'
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='bookmarks';''').fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS bookmarks (tvshowtitle TEXT, title TEXT, resume_id TEXT, imdb TEXT, tmdb TEXT, tvdb TEXT, season TEXT, episode TEXT, genre TEXT, mpaa TEXT,
								studio TEXT, duration TEXT, percent_played TEXT, paused_at TEXT, UNIQUE(resume_id, imdb, tmdb, tvdb, season, episode));''')
			dbcur.connection.commit()
			return progress
		if ret_all:
			if ret_type == 'movies':
				match = dbcur.execute('''SELECT * FROM bookmarks WHERE (tvshowtitle='')''').fetchall()
				progress = [{'title': i[1], 'resume_id': i[2], 'imdb': i[3], 'tmdb': i[4], 'duration': int(i[11] or 0), 'progress': i[12], 'paused_at': i[13]} for i in match]
			else:
				match = dbcur.execute('''SELECT * FROM bookmarks WHERE NOT (tvshowtitle='')''').fetchall()
				progress = [{'tvshowtitle': i[0], 'title': i[1], 'resume_id': i[2], 'imdb': i[3], 'tmdb': i[4], 'tvdb': i[5],
							'season': int(i[6] or 0), 'episode': int(i[7] or 0), 'genre': i[8], 'mpaa': i[9],
							'studio': i[10], 'duration': int(i[11] or 0), 'progress': i[12], 'paused_at': i[13]} for i in match]
		else:
			if not episode:
				try:
					match = dbcur.execute('''SELECT * FROM bookmarks WHERE (imdb=? AND tmdb=? AND NOT imdb='' AND NOT tmdb='')''', (imdb, tmdb)).fetchone()
					if ret_type == 'resume_info': progress = (match[1], match[2])
					else: progress = match[12]
				except Exception:
					try:
						match = dbcur.execute('''SELECT * FROM bookmarks WHERE (imdb=? AND NOT imdb='')''', (imdb,)).fetchone()
						if ret_type == 'resume_info': progress = (match[1], match[2])
						else: progress = match[12]
					except Exception:
						pass
			else:
				try:
					match = dbcur.execute('''SELECT * FROM bookmarks WHERE (imdb=? AND tvdb=? AND season=? AND episode=? AND NOT imdb='' AND NOT tvdb='')''',
										(imdb, tvdb, str(season), str(episode))).fetchone()
					if ret_type == 'resume_info': progress = (match[0], match[2])
					else: progress = match[12]
				except Exception:
					try:
						match = dbcur.execute('''SELECT * FROM bookmarks WHERE (tvdb=? AND season=? AND episode=? AND NOT tvdb='')''',
											(tvdb, str(season), str(episode))).fetchone()
						if ret_type == 'resume_info': progress = (match[0], match[2])
						else: progress = match[12]
					except Exception:
						pass
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass
	return progress

def insert_bookmarks(items, new_scrobble=False):
	"""Items expected from SIMKL /sync/playback/{movies|episodes}. Each item:
	  movie:    {id, progress, paused_at, movie: {title, ids, runtime, genres,...}}
	  episode:  {id, progress, paused_at, show: {title, ids, runtime,...},
	             episode: {season, number, title, ids}}
	"""
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		dbcur.execute('''CREATE TABLE IF NOT EXISTS bookmarks (tvshowtitle TEXT, title TEXT, resume_id TEXT, imdb TEXT, tmdb TEXT, tvdb TEXT, season TEXT, episode TEXT, genre TEXT, mpaa TEXT,
								studio TEXT, duration TEXT, percent_played TEXT, paused_at TEXT, UNIQUE(resume_id, imdb, tmdb, tvdb, season, episode));''')
		dbcur.execute('''CREATE TABLE IF NOT EXISTS service (setting TEXT, value TEXT, UNIQUE(setting));''')
		if not new_scrobble:
			dbcur.execute('''DELETE FROM bookmarks''')
			dbcur.connection.commit()
			dbcur.execute('''VACUUM''')
		for i in items:
			tvshowtitle = title = imdb = tmdb = tvdb = season = episode = mpaa = studio = ''
			duration = 0
			genre = 'NA'
			try:
				if i.get('episode') and i.get('show'):
					s = i.get('show') or {}
					e = i.get('episode') or {}
					ids = s.get('ids') or {}
					tvshowtitle = s.get('title') or ''
					title       = e.get('title') or ''
					imdb        = str(ids.get('imdb', ''))
					tmdb        = str(ids.get('tmdb', ''))
					tvdb        = str(ids.get('tvdb', ''))
					season      = str(e.get('season') if e.get('season') is not None else '')
					episode     = str(e.get('number', ''))
					mpaa        = s.get('certification') or 'NR'
					studio      = s.get('network') or ''
					duration    = s.get('runtime') or 0
					try: genre = ' / '.join([x.title() for x in (s.get('genres') or [])]) or 'NA'
					except Exception: genre = 'NA'
				else:
					m = i.get('movie') or {}
					ids = m.get('ids') or {}
					title    = m.get('title') or ''
					imdb     = str(ids.get('imdb', ''))
					tmdb     = str(ids.get('tmdb', ''))
					mpaa     = m.get('certification') or 'NR'
					duration = m.get('runtime') or 0
					try: genre = ' / '.join([x.title() for x in (m.get('genres') or [])]) or 'NA'
					except Exception: genre = 'NA'
			except Exception:
				pass
			dbcur.execute('''INSERT OR REPLACE INTO bookmarks Values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
							(tvshowtitle, title, str(i.get('id', '')), imdb, tmdb, tvdb, season, episode, genre, mpaa, studio,
							 str(duration), str(i.get('progress', '')), str(i.get('paused_at', ''))))
		timestamp = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		dbcur.execute('''INSERT OR REPLACE INTO service Values (?, ?)''', ('last_paused_at', timestamp))
		dbcur.connection.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass

def delete_bookmark(items):
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='bookmarks';''').fetchone()
		if not ck_table: return
		for i in items:
			try:
				if i.get('type') == 'episode':
					ids = (i.get('show') or {}).get('ids') or {}
					e   = i.get('episode') or {}
					dbcur.execute('''DELETE FROM bookmarks WHERE (imdb=? AND tvdb=? AND season=? AND episode=?)''',
									(str(ids.get('imdb', '')), str(ids.get('tvdb', '')),
									 str(e.get('season', '')), str(e.get('number', ''))))
				else:
					ids = (i.get('movie') or {}).get('ids') or {}
					dbcur.execute('''DELETE FROM bookmarks WHERE (imdb=? AND NOT imdb='')''', (str(ids.get('imdb', '')),))
			except Exception:
				continue
		dbcur.connection.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass


# ---------------------------------------------------------------------------
# Watchlist tables (movies / shows / anime, status=plantowatch)
# ---------------------------------------------------------------------------
def fetch_watchlist(table):
	dbcon = dbcur = None
	rows = []
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='%s';''' % table).fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (simkl TEXT, imdb TEXT, tmdb TEXT, tvdb TEXT, title TEXT, year TEXT, item TEXT, UNIQUE(simkl, imdb, tmdb, tvdb));''' % table)
			dbcur.connection.commit()
			return rows
		match = dbcur.execute('''SELECT * FROM %s''' % table).fetchall()
		for i in match:
			try:
				meta = literal_eval(i[6]) if i[6] else {}
			except Exception:
				meta = {}
			rows.append(meta)
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass
	return rows

def insert_watchlist(items, table, new_sync=True, media_type='movies'):
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (simkl TEXT, imdb TEXT, tmdb TEXT, tvdb TEXT, title TEXT, year TEXT, item TEXT, UNIQUE(simkl, imdb, tmdb, tvdb));''' % table)
		if new_sync:
			dbcur.execute('''DELETE FROM %s''' % table)
			dbcur.connection.commit()
		for entry in items:
			inner_key = 'movie' if media_type == 'movies' else ('show' if media_type == 'shows' else 'anime')
			it = entry.get(inner_key) or entry
			ids = it.get('ids') or {}
			simkl = str(ids.get('simkl') or ids.get('simkl_id') or '')
			imdb  = str(ids.get('imdb', ''))
			tmdb  = str(ids.get('tmdb', ''))
			tvdb  = str(ids.get('tvdb', ''))
			title = str(it.get('title') or '')
			year  = str(it.get('year') or '')
			dbcur.execute('''INSERT OR REPLACE INTO %s Values (?, ?, ?, ?, ?, ?, ?)''' % table,
							(simkl, imdb, tmdb, tvdb, title, year, repr(it)))
		dbcur.connection.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass


# ---------------------------------------------------------------------------
# Service-meta helpers (last_sync timestamps, etc.)
# ---------------------------------------------------------------------------
def last_sync(setting):
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='service';''').fetchone()
		if not ck_table: return 0
		row = dbcur.execute('''SELECT value FROM service WHERE setting=?''', (setting,)).fetchone()
		if not row: return 0
		try:
			return int(cleandate.iso_2_utc(row[0]))
		except Exception:
			return 0
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return 0
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass


def delete_tables(tables):
	"""tables: dict of {table_name: True} entries to wipe."""
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		for tbl, do_wipe in tables.items():
			if not do_wipe: continue
			try:
				dbcur.execute('''DROP TABLE IF EXISTS %s''' % tbl)
			except Exception:
				continue
		dbcur.connection.commit()
		try: dbcur.execute('''VACUUM''')
		except Exception: pass
		return True
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return False
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass


# ---------------------------------------------------------------------------
# Cache helpers (used by simkl.cachesyncMovies / cachesyncTVShows)
# Mirror of traktsync.get / traktsync.timeout but stored in simklsync.db.
# ---------------------------------------------------------------------------
def _hash_function(function, args):
	name = function.__name__ if hasattr(function, '__name__') else str(function)
	return md5((name + str(args)).encode('utf-8')).hexdigest()

def _cache_get(key):
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		dbcur.execute('''CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, date INTEGER);''')
		row = dbcur.execute('''SELECT value, date FROM cache WHERE key=?''', (key,)).fetchone()
		if not row: return None
		return {'value': row[0], 'date': int(row[1] or 0)}
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return None
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass

def _cache_insert(key, value):
	dbcon = dbcur = None
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		dbcur.execute('''CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, date INTEGER);''')
		dbcur.execute('''INSERT OR REPLACE INTO cache VALUES (?, ?, ?)''', (key, str(value), int(time())))
		dbcur.connection.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass

def _is_cache_valid(cached_time, cache_timeout):
	now = int(time())
	diff = now - cached_time
	return (cache_timeout * 3600) > diff

def get(function, duration, *args):
	"""Same shape as traktsync.get(function, duration, *args)."""
	try:
		key = _hash_function(function, args)
		cache_result = _cache_get(key)
		if cache_result:
			try: result = literal_eval(cache_result['value'])
			except Exception: result = None
			if _is_cache_valid(cache_result['date'], duration): return result
		fresh = repr(function(*args))
		invalid = False
		try:
			if not fresh or fresh in ('None', '', '[]', '{}'): invalid = True
			elif len(fresh) == 0: invalid = True
		except Exception: pass
		if invalid:
			if cache_result: return result
			return None
		_cache_insert(key, fresh)
		return literal_eval(fresh)
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return None

def timeout(function, *args, returnNone=False):
	try:
		key = _hash_function(function, args)
		result = _cache_get(key)
		if not result and returnNone: return None
		return int(result['date']) if result else 0
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return None if returnNone else 0


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def get_connection(setRowFactory=False):
	if not existsPath(dataPath): makeFile(dataPath)
	dbcon = db.connect(simklSyncFile, timeout=60)
	# Same PRAGMA profile as traktsync.py (project standard).
	dbcon.execute('''PRAGMA journal_mode = OFF''')
	dbcon.execute('''PRAGMA synchronous = OFF''')
	dbcon.execute('''PRAGMA temp_store = memory''')
	dbcon.execute('''PRAGMA mmap_size = 268435456''')
	if setRowFactory: dbcon.row_factory = _dict_factory
	return dbcon

def get_connection_cursor(dbcon):
	return dbcon.cursor()

def _dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description): d[col[0]] = row[idx]
	return d
