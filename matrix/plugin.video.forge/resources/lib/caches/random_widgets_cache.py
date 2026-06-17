# -*- coding: utf-8 -*-
from caches.base_cache import BaseCache

# from modules.kodi_utils import logger


class RandomWidgets(BaseCache):
	def __init__(self):
		BaseCache.__init__(self, "random_widgets_db", "random_widgets")


random_widgets_cache = RandomWidgets()
