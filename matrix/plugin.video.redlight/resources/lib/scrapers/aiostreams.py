# -*- coding: utf-8 -*-
from apis import aiostreams_api
from modules import source_utils
from modules.utils import clean_file_name, normalize
from modules.settings import filter_by_name
from caches.settings_cache import get_setting
# from modules.kodi_utils import logger

class source:
	def __init__(self):
		self.scrape_provider = 'aiostreams'
		self.sources = []

	def results(self, info):
		try:
			if not aiostreams_api.ENABLED: return source_utils.internal_results(self.scrape_provider, self.sources)
			if not aiostreams_api.auth(): return source_utils.internal_results(self.scrape_provider, self.sources)
			filter_title = filter_by_name(self.scrape_provider)
			self.media_type = info.get('media_type')
			title = info.get('title', '')
			self.year = int(info.get('year') or 0)
			self.season, self.episode = info.get('season'), info.get('episode')
			imdb_id = info.get('imdb_id')
			self.aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			timeout = int(get_setting('redlight.results.timeout', '60'))
			if 'timeout' in info: timeout = max(1, int(info['timeout']) - 1)
			scrape_results, self.errors = aiostreams_api.search(self.media_type, imdb_id, self.season, self.episode, timeout=timeout)
			if not scrape_results: return source_utils.internal_results(self.scrape_provider, self.sources)
			extras = source_utils.extras()
			def _process():
				for item in scrape_results:
					try:
						if 'p2p' in (item.get('type') or '').lower(): continue
						parsed = dict(item.get('parsedFile') or {})
						file_name = parsed.get('filename') or parsed.get('name') or item.get('name', '')
						if not file_name: continue
						file_name = normalize(file_name)
						if any(x in file_name.lower() for x in extras): continue
						if filter_title and not source_utils.check_title(title, file_name, self.aliases, self.year, self.season, self.episode): continue
						url = parsed.get('url') or item.get('url')
						if not url: continue
						display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
						size_bytes = parsed.get('size') or item.get('size') or 0
						try: size = round(float(size_bytes) / 1073741824, 2)
						except: size = 0.0
						video_quality, details = source_utils.get_file_info(name_info=source_utils.release_info_format(file_name))
						resolution = parsed.get('resolution') or item.get('resolution')
						if resolution and resolution.upper() in ('4K', '1080P', '720P', 'SD'):
							video_quality = resolution.upper().replace('1080P', '1080p').replace('720P', '720p')
						request_headers = item.get('requestHeaders') or parsed.get('requestHeaders')
						source_item = {'name': file_name, 'display_name': display_name, 'quality': video_quality, 'size': size,
									'size_label': '%.2f GB' % size if size else 'N/A', 'debrid': self.scrape_provider, 'source': self.scrape_provider,
									'extraInfo': details, 'url_dl': url, 'url': url, 'id': url, 'direct': True, 'local': False,
									'scrape_provider': self.scrape_provider, 'request_headers': request_headers}
						yield source_item
					except Exception as e:
						from modules.kodi_utils import logger
						logger('aiostreams scraper yield source error', str(e))
			self.sources = list(_process())
		except Exception as e:
			from modules.kodi_utils import logger
			logger('aiostreams scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
