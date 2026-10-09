from datetime import datetime, timedelta
from caches import BaseCache, debridcache_db
# from modules.kodi_utils import logger

GET_MANY = 'SELECT * FROM debrid_data WHERE hash in (%s)'
SET_MANY = 'INSERT INTO debrid_data VALUES (?, ?, ?, ?)'
REMOVE_MANY = 'DELETE FROM debrid_data WHERE hash = ?'
SINGLE_DELETE = 'DELETE FROM debrid_data WHERE debrid = ?'
FULL_DELETE = 'DELETE FROM debrid_data'

class DebridCache(BaseCache):
	db_file = debridcache_db

	def get_many(self, hash_list):
		result = None
		try:
			current_time = self._get_timestamp(datetime.now())
			joined_list = ', '.join('?' for _ in hash_list)
			with self: cache_data = self.dbcur.execute(GET_MANY % joined_list, hash_list).fetchall()
			if cache_data and cache_data[0][3] > current_time: result = cache_data
			elif cached_data: self.remove_many(cache_data)
		except: pass
		return result

	def set_many(self, hash_list, debrid):
		expires = self._get_timestamp(datetime.now() + timedelta(hours=24))
		insert_list = [(i[0], debrid, i[1], expires) for i in hash_list]
		with self: self.dbcur.executemany(SET_MANY, insert_list)

	def remove_many(self, cached_data):
		cached_data = [(str(i[0]),) for i in cached_data]
		with self: self.dbcur.executemany(REMOVE_MANY, cached_data)

	def delete_cache_single(self, debrid):
		with self: self.dbcur.execute(SINGLE_DELETE, (debrid,))
		return True

	def clear_cache(self):
		with self:
			self.dbcur.execute(FULL_DELETE)
			self.dbcur.execute("""VACUUM""")
		return True

