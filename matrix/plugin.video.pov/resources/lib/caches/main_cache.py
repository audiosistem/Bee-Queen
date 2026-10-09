from datetime import datetime, timedelta
from caches import BaseCache, maincache_db, get_property, set_property, clear_property
# from modules.kodi_utils import logger

BASE_GET = 'SELECT data, expires FROM maincache WHERE id = ? AND expires > ?'
BASE_SET = 'INSERT OR REPLACE INTO maincache VALUES (?, ?, ?)'
BASE_DELETE = 'DELETE FROM maincache WHERE id = ?'
LIKE_SELECT = 'SELECT id FROM maincache WHERE %s'
LIKE_SELECT_ADD = 'id LIKE ?'

class MainCache(BaseCache):
	db_file = maincache_db

	def get(self, string):
		current_time = self._get_timestamp(datetime.now())
		cache_data = self.get_memory_cache(string, current_time)
		if cache_data: return cache_data
		with self: data = self.dbcur.execute(BASE_GET, (string, current_time)).fetchone()
		if not data: return None
		result, expiry = self.jsloads(data[0]), data[1]
		self.set_memory_cache(result, string, expiry)
		return result

	def set(self, string, data, expiration):
		expires = self._get_timestamp(datetime.now() + expiration)
		with self: self.dbcur.execute(BASE_SET, (string, int(expires), self.jsdumps(data)))
		self.set_memory_cache(data, string, int(expires))

	def delete(self, string):
		with self: self.dbcur.execute(BASE_DELETE, (string,))
		self.delete_memory_cache(string)

	def get_memory_cache(self, string, current_time):
		cache_data = get_property(string)
		if not cache_data: return None
		expiry, result = self.jsloads(cache_data)
		if expiry < current_time: return None
		return result

	def set_memory_cache(self, data, string, expires):
		cache_data = (expires, data)
		set_property(string, self.jsdumps(cache_data))

	def delete_memory_cache(self, string):
		clear_property(string)

	def delete_all(self):
		from modules.meta_lists import media_lists
		items = ' OR '.join(LIKE_SELECT_ADD for i in media_lists)
		with self:
			all_entries = self.dbcur.execute(LIKE_SELECT % items, media_lists).fetchall()
			for i in all_entries:
				self.dbcur.execute(BASE_DELETE, (str(i[0]),))
			self.dbcur.execute("""VACUUM""")
		for i in all_entries: self.delete_memory_cache(str(i[0]))

def cache_object(function, string, url, expiration=24, json=False):
	maincache = MainCache()
	cache = maincache.get(string)
	if cache: return cache
	if not isinstance(url, list): url = (url,)
	if json: result = function(*url).json()
	else: result = function(*url)
	if isinstance(expiration, (int, float)): expiration = timedelta(hours=expiration)
	maincache.set(string, result, expiration)
	return result

