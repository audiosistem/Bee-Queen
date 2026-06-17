# -*- coding: utf-8 -*-
import json

from caches._codec import decode as _decode
from caches.base_cache import connect_database, enforce_row_cap, get_max_cache_rows, get_timestamp
from modules.kodi_utils import clear_property, get_property, logger, set_property


class MetaCache:
	def get(self, media_type, id_type, media_id, current_time=None):
		meta = None
		try:
			media_id = str(media_id)
			if not current_time:
				current_time = get_timestamp()
			meta = self.get_memory_cache(media_type, id_type, media_id, current_time)
			if meta is None:
				dbcon = connect_database("metacache_db")
				cache_data = dbcon.execute("SELECT meta, expires FROM metadata WHERE db_type = ? AND %s = ?" % id_type, (media_type, media_id)).fetchone()
				if cache_data:
					meta, expiry = _decode(cache_data[0]), cache_data[1]
					if expiry <= current_time:
						self.delete(media_type, id_type, media_id, meta=meta)
						meta = None
					else:
						self.set_memory_cache(media_type, id_type, meta, expiry, media_id)
		except Exception as e:
			logger("MetaCache.get error", str(e))
		return meta

	def get_season(self, prop_string):
		meta = None
		try:
			current_time = get_timestamp()
			meta = self.get_memory_cache_season(prop_string, current_time)
			if meta is None:
				dbcon = connect_database("metacache_db")
				cache_data = dbcon.execute("SELECT meta, expires FROM season_metadata WHERE tmdb_id = ?", (prop_string,)).fetchone()
				if cache_data:
					meta, expiry = _decode(cache_data[0]), cache_data[1]
					if expiry <= current_time:
						self.delete_season(prop_string)
						meta = None
					else:
						self.set_memory_cache_season(prop_string, meta, expiry)
		except Exception as e:
			logger("MetaCache.get_season error", str(e))
		return meta

	def set(self, media_type, id_type, meta, expiration=168, current_time=None):
		try:
			dbcon = connect_database("metacache_db")
			meta_get = meta.get
			if current_time:
				expires = current_time + (expiration * 3600)
			else:
				expires = get_timestamp(expiration)
			media_id = str(meta_get(id_type))
			dbcon.execute(
				"INSERT OR REPLACE INTO metadata VALUES (?, ?, ?, ?, ?, ?)",
				(media_type, str(meta_get("tmdb_id")), meta_get("imdb_id"), str(meta_get("tvdb_id")), json.dumps(meta), expires),
			)
		except Exception as e:
			logger("MetaCache.set error", str(e))
			return None
		self.set_memory_cache(media_type, id_type, meta, expires, media_id)

	def set_season(self, prop_string, meta, expiration=168):
		try:
			dbcon = connect_database("metacache_db")
			expires = get_timestamp(expiration)
			dbcon.execute("INSERT OR REPLACE INTO season_metadata VALUES (?, ?, ?)", (prop_string, json.dumps(meta), int(expires)))
		except Exception as e:
			logger("MetaCache.set_season error", str(e))
			return None
		self.set_memory_cache_season(prop_string, meta, expires)

	def delete(self, media_type, id_type, media_id, meta=None):
		try:
			dbcon = connect_database("metacache_db")
			dbcon.execute("DELETE FROM metadata WHERE db_type = ? AND %s = ?" % id_type, (media_type, media_id))
			for item in ("tmdb_id", "imdb_id", "tvdb_id"):
				self.delete_memory_cache(media_type, item, meta[item])
			if media_type == "tvshow":
				self.delete_all_seasons(media_id)
		except Exception:
			return

	def delete_season(self, prop_string):
		try:
			dbcon = connect_database("metacache_db")
			dbcon.execute("DELETE FROM season_metadata WHERE tmdb_id = ?", (prop_string,))
			self.delete_memory_cache_season(prop_string)
		except Exception:
			return

	def get_memory_cache(self, media_type, id_type, media_id, current_time):
		result = None
		try:
			prop_string = "forge.%s_%s_%s" % (media_type, id_type, media_id)
			cachedata = _decode(get_property(prop_string))
			if cachedata[0] > current_time:
				result = cachedata[1]
		except Exception:
			result = None
		return result

	def get_memory_cache_season(self, prop_string, current_time):
		result = None
		try:
			cachedata = _decode(get_property("forge.meta_season_%s" % prop_string))
			if cachedata[0] > current_time:
				result = cachedata[1]
		except Exception:
			result = None
		return result

	def set_memory_cache(self, media_type, id_type, meta, expires, media_id):
		try:
			cachedata, prop_string = [expires, meta], "forge.%s_%s_%s" % (media_type, id_type, media_id)
			set_property(prop_string, json.dumps(cachedata))
		except Exception:
			pass

	def set_memory_cache_season(self, prop_string, meta, expires):
		try:
			cachedata = [expires, meta]
			set_property("forge.meta_season_%s" % prop_string, json.dumps(cachedata))
		except Exception:
			pass

	def delete_memory_cache(self, media_type, id_type, media_id):
		try:
			clear_property("forge.%s_%s_%s" % (media_type, id_type, media_id))
		except Exception:
			pass

	def delete_memory_cache_season(self, prop_string):
		try:
			clear_property("forge.meta_season_%s" % prop_string)
		except Exception:
			pass

	def get_function(self, prop_string):
		result = None
		try:
			dbcon = connect_database("metacache_db")
			current_time = get_timestamp()
			cache_data = dbcon.execute("SELECT string_id, data, expires FROM function_cache WHERE string_id = ?", (prop_string,)).fetchone()
			if cache_data:
				if cache_data[2] >= current_time:
					result = _decode(cache_data[1])
				else:
					dbcon.execute("DELETE FROM function_cache WHERE string_id = ?", (prop_string,))
		except Exception:
			pass
		return result

	def set_function(self, prop_string, result, expiration=24):
		try:
			dbcon = connect_database("metacache_db")
			expires = get_timestamp(expiration)
			dbcon.execute("INSERT INTO function_cache VALUES (?, ?, ?)", (prop_string, json.dumps(result), expires))
		except Exception:
			return

	def delete_all_seasons(self, media_id):
		for item in range(1, 51):
			self.delete_season("%s_%s" % (media_id, str(item)))

	def delete_all(self):
		try:
			dbcon = connect_database("metacache_db")
			for i in dbcon.execute("SELECT db_type, tmdb_id FROM metadata"):
				try:
					self.delete_memory_cache(str(i[0]), "tmdb_id", str(i[1]))
				except Exception:
					pass
			for i in dbcon.execute("SELECT tmdb_id FROM season_metadata"):
				try:
					self.delete_memory_cache_season(str(i[0]))
				except Exception:
					pass
			for i in ("metadata", "season_metadata", "function_cache"):
				dbcon.execute("DELETE FROM %s" % i)
			dbcon.execute("VACUUM")
		except Exception as e:
			logger("MetaCache.delete_all error", str(e))
			return

	def clean_database(self):
		try:
			dbcon = connect_database("metacache_db")
			max_rows = get_max_cache_rows()
			for table in ("metadata", "function_cache", "season_metadata"):
				dbcon.execute("DELETE from %s WHERE CAST(expires AS INT) <= ?" % table, (get_timestamp(),))
				enforce_row_cap(dbcon, table, max_rows)
			dbcon.execute("VACUUM")
			return True
		except Exception as e:
			logger("MetaCache.clean_database error", str(e))
			return False


meta_cache = MetaCache()


def cache_function(function, prop_string, url, expiration=720, json=True):
	data = meta_cache.get_function(prop_string)
	if data:
		return data
	if json:
		result = function(url).json()
	else:
		result = function(url)
	meta_cache.set_function(prop_string, result, expiration=expiration)
	return result


def delete_meta_cache(silent=False):
	from modules.kodi_utils import confirm_dialog

	try:
		if not silent and not confirm_dialog():
			return False
		meta_cache.delete_all()
		return True
	except Exception:
		return False
