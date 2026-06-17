# -*- coding: utf-8 -*-
import sqlite3 as database

from caches.base_cache import BaseCache

# from modules.kodi_utils import logger


class IntroOutroCache(BaseCache):
	"""Per-episode skip-marker cache (intro/recap/outro segments).

	Keyed ``"<imdb_id>_<season>_<episode>"``; stores the *normalized* segment
	list (the common shape produced by ``modules/skip_markers.py``). Misses are
	cached too — an empty list with a short TTL — so an uncovered show doesn't
	re-hit IntroDB on every episode, while fresh crowd data still surfaces within
	a day. The hit/miss TTLs are chosen by the caller via ``set(..., expiration=)``.

	``BaseCache`` supplies ``get``/``set``/``delete`` over the
	``(id, data, expires)`` TTL schema.
	"""

	def __init__(self):
		BaseCache.__init__(self, "intro_outro_db", "intro_outro")

	def delete_all(self):
		try:
			dbcon = self.manual_connect("intro_outro_db")
			dbcon.execute("DELETE FROM intro_outro")
			dbcon.execute("VACUUM")
			return True
		except database.Error:
			return False


intro_outro_cache = IntroOutroCache()
