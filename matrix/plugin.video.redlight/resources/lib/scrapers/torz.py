# -*- coding: utf-8 -*-
from apis import torz_api
from modules import source_utils
from modules.native_torrents import filter_and_build_sources, prepare_site_scrape, scrape_expiry, scrape_timeout
from modules.settings import torz_scrape_active
from modules.kodi_utils import logger


class source:
	def __init__(self):
		self.scrape_provider = 'torz'
		self.sources = []

	def results(self, info):
		try:
			if not torz_scrape_active():
				return source_utils.internal_results(self.scrape_provider, self.sources)
			query = prepare_site_scrape(info, log_name='torz scraper')
			if not query:
				return source_utils.internal_results(self.scrape_provider, self.sources)
			streams = torz_api.search_streams(
				query.get('imdb_id'), query.get('media_type'), query.get('season'), query.get('episode'),
				timeout=scrape_timeout(query), expiration=scrape_expiry(query))
			self.sources = filter_and_build_sources(self.scrape_provider, streams, query)
		except Exception as e:
			logger('torz scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
