# -*- coding: utf-8 -*-
import json
from contextlib import nullcontext
from caches.base_cache import open_db, get_timestamp
# from modules.kodi_utils import logger

def _normalize_meta(meta):
	"""Legacy repr rows kept studio as a 1-tuple; InfoTagVideo.setStudios needs a list."""
	if isinstance(meta, dict):
		studio = meta.get('studio')
		if isinstance(studio, tuple):
			meta['studio'] = list(studio)
	return meta

def _loads_meta(raw):
	"""Prefer JSON (current); fall back to legacy repr/eval rows."""
	try:
		meta = json.loads(raw)
	except Exception:
		meta = eval(raw)
	return _normalize_meta(meta)

class MetaCache:
	def get(self, media_type, id_type, media_id, current_time=None, dbcon=None):
		meta = None
		try:
			media_id = str(media_id)
			if not current_time: current_time = get_timestamp()
			context = nullcontext(dbcon) if dbcon else open_db('metacache_db')
			with context as active_dbcon:
				cache_data = active_dbcon.execute('SELECT meta, expires FROM metadata WHERE db_type = ? AND %s = ?' % id_type, (media_type, media_id)).fetchone()
				if cache_data:
					meta, expiry = _loads_meta(cache_data[0]), cache_data[1]
					if expiry <= current_time:
						self.delete(media_type, id_type, media_id, dbcon=active_dbcon)
						meta = None
		except: pass
		return meta

	def get_season(self, prop_string):
		meta = None
		try:
			current_time = get_timestamp()
			with open_db('metacache_db') as dbcon:
				cache_data = dbcon.execute('SELECT meta, expires FROM season_metadata WHERE tmdb_id = ?', (prop_string,)).fetchone()
				if cache_data:
					meta, expiry = _loads_meta(cache_data[0]), cache_data[1]
					if expiry <= current_time:
						self.delete_season(prop_string, dbcon=dbcon)
						meta = None
		except: pass
		return meta

	def set(self, media_type, id_type, meta, expiration=168, current_time=None, dbcon=None):
		try:
			meta_get = meta.get
			if current_time: expires = current_time + (expiration*3600)
			else: expires = get_timestamp(expiration)
			context = nullcontext(dbcon) if dbcon else open_db('metacache_db')
			with context as active_dbcon:
				active_dbcon.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?, ?, ?, ?, ?)',
					(media_type, str(meta_get('tmdb_id')), meta_get('imdb_id'), str(meta_get('tvdb_id')), json.dumps(meta), expires))
		except: return None

	def set_season(self, prop_string, meta, expiration=168):
		try:
			expires = get_timestamp(expiration)
			with open_db('metacache_db') as dbcon:
				dbcon.execute('INSERT OR REPLACE INTO season_metadata VALUES (?, ?, ?)', (prop_string, json.dumps(meta), int(expires)))
		except: return None

	def delete(self, media_type, id_type, media_id, meta=None, dbcon=None):
		try:
			context = nullcontext(dbcon) if dbcon else open_db('metacache_db')
			with context as active_dbcon:
				active_dbcon.execute('DELETE FROM metadata WHERE db_type = ? AND %s = ?' % id_type, (media_type, media_id))
				if media_type == 'tvshow': self.delete_all_seasons(media_id, active_dbcon)
		except: return

	def delete_season(self, prop_string, dbcon=None):
		try:
			context = nullcontext(dbcon) if dbcon else open_db('metacache_db')
			with context as active_dbcon:
				active_dbcon.execute('DELETE FROM season_metadata WHERE tmdb_id = ?', (prop_string,))
		except: return

	def get_function(self, prop_string):
		result = None
		try:
			current_time = get_timestamp()
			with open_db('metacache_db') as dbcon:
				cache_data = dbcon.execute('SELECT string_id, data, expires FROM function_cache WHERE string_id = ?', (prop_string,)).fetchone()
				if cache_data:
					if cache_data[2] >= current_time: result = _loads_meta(cache_data[1])
					else: dbcon.execute('DELETE FROM function_cache WHERE string_id = ?', (prop_string,))
		except: pass
		return result

	def set_function(self, prop_string, result, expiration=24):
		try:
			expires = get_timestamp(expiration)
			with open_db('metacache_db') as dbcon:
				dbcon.execute('INSERT INTO function_cache VALUES (?, ?, ?)', (prop_string, json.dumps(result), expires))
		except: return

	def delete_all_seasons(self, media_id, dbcon=None):
		for item in range(1, 51):
			self.delete_season('%s_%s' % (media_id, str(item)), dbcon=dbcon)

	def delete_all(self):
		try:
			with open_db('metacache_db') as dbcon:
				for i in ('metadata', 'season_metadata', 'function_cache'): dbcon.execute('DELETE FROM %s' % i)
				dbcon.execute('VACUUM')
		except: return

	def clean_database(self):
		try:
			with open_db('metacache_db') as dbcon:
				for table in ('metadata', 'function_cache', 'season_metadata'):
					dbcon.execute('DELETE from %s WHERE CAST(expires AS INT) <= ?' % table, (get_timestamp(),))
				dbcon.execute('VACUUM')
			return True
		except: return False

meta_cache = MetaCache()

def cache_function(function, prop_string, url, expiration=720, json=True):
	data = meta_cache.get_function(prop_string)
	if data: return data
	if json: result = function(url).json()
	else: result = function(url)
	meta_cache.set_function(prop_string, result, expiration=expiration)
	return result

def delete_meta_cache(silent=False):
	from modules.kodi_utils import confirm_dialog
	try:
		if not silent and not confirm_dialog(): return False
		meta_cache.delete_all()
		return True
	except: return False
