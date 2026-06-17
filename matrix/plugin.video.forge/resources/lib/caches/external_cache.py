# -*- coding: utf-8 -*-
import json

from caches._codec import decode as _decode
from caches.base_cache import connect_database, enforce_row_cap, get_max_cache_rows, get_timestamp

# from modules.kodi_utils import logger


class ExternalCache(object):
	def get(self, source, media_type, tmdb_id, title, year, season, episode):
		result = None
		try:
			rows = self._execute(
				"SELECT results, expires FROM results_data WHERE provider = ? AND db_type = ? AND tmdb_id = ? AND title = ? AND year = ? AND season = ? AND episode = ?",
				(source, media_type, tmdb_id, title, year, season, episode),
			)
			cache_data = rows[0] if rows else None
			if cache_data:
				if cache_data[1] > get_timestamp():
					result = _decode(cache_data[0])
				else:
					self.delete(source, media_type, tmdb_id, title, year, season, episode)
		except:
			pass
		return result

	def set(self, source, media_type, tmdb_id, title, year, season, episode, results, expire_time):
		try:
			expires = get_timestamp(expire_time)
			self._execute(
				"INSERT OR REPLACE INTO results_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
				(source, media_type, tmdb_id, title, year, season, episode, json.dumps(results or []), int(expires)),
			)
		except:
			pass

	def delete(self, source, media_type, tmdb_id, title, year, season, episode):
		try:
			self._execute(
				"DELETE FROM results_data WHERE provider = ? AND db_type = ? AND tmdb_id = ? AND title = ? AND year = ? AND season = ? AND episode = ?",
				(source, media_type, tmdb_id, title, year, season, episode),
			)
		except:
			return

	def delete_cache_single(self, media_type, tmdb_id):
		try:
			self._execute("DELETE FROM results_data WHERE db_type=? AND tmdb_id=?", (media_type, tmdb_id))
			self._vacuum()
			return True
		except:
			return False

	def clear_cache(self):
		try:
			self._execute("DELETE FROM results_data", ())
			self._vacuum()
			return True
		except:
			return False

	def _execute(self, command, params):
		# Short-lived connection: open, run, close. The DB is autocommit
		# (isolation_level=None), so writes are durable before we close, and
		# readers get the rows back as a list. Avoids leaking a connection per call.
		dbcon = connect_database("external_db")
		try:
			return dbcon.execute(command, params).fetchall()
		finally:
			dbcon.close()

	def clean_database(self):
		try:
			dbcon = connect_database("external_db")
			dbcon.execute("DELETE from results_data WHERE CAST(expires AS INT) <= ?", (get_timestamp(),))
			enforce_row_cap(dbcon, "results_data", get_max_cache_rows())
			dbcon.close()
			self._vacuum()
			return True
		except:
			return False

	def _vacuum(self):
		dbcon = connect_database("external_db")
		dbcon.execute("VACUUM")
		dbcon.close()


external_cache = ExternalCache()
