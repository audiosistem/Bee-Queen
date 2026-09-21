# -*- coding: utf-8 -*-
from apis import piratebay_api
from modules import source_utils
from modules.native_torrents import filter_and_build_sources, merge_name_searches, name_search_queries, scrape_expiry, scrape_timeout
from modules.settings import piratebay_scrape_active
from modules.kodi_utils import logger


class source:
	def __init__(self):
		self.scrape_provider = 'piratebay'
		self.sources = []

	def results(self, info):
		try:
			if not piratebay_scrape_active():
				return source_utils.internal_results(self.scrape_provider, self.sources)
			files = merge_name_searches(
				piratebay_api.search, name_search_queries(info), scrape_timeout(info), scrape_expiry(info),
				info.get('scrape_deadline'))
			self.sources = filter_and_build_sources(self.scrape_provider, files, info)
		except Exception as e:
			logger('piratebay scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
