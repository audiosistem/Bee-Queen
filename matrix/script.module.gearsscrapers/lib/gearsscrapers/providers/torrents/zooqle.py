# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote as _quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

_RE_ZOOQLE_RESULT = re.compile(
	r'href="(https://zooqle\.app/movies/[a-z0-9-]+)"[^>]*title="([^"]{2,120})"', re.IGNORECASE)
_RE_ZOOQLE_DL = re.compile(
	r'href="(https://[^"]+/torrent/download/([A-F0-9]{40}))"[\s\S]*?>([^<]{2,120})<', re.IGNORECASE)


class source:
	priority = 5
	pack_capable = False
	hasMovies = True
	hasEpisodes = False
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://zooqle.app"
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
			self.aliases = data['aliases']
			self.year = data['year']
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = re.sub(r'\s+', ' ', self.title).strip()
			html = client.request('%s/?keyword=%s' % (self.base_link, _quote(query)), timeout=12)
			if not html: return self.sources

			def _nc(s):
				return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', s.lower())).strip()
			norm_query = _nc(query)
			seen, candidates = set(), []
			for page_url, name in _RE_ZOOQLE_RESULT.findall(html):
				if page_url in seen: continue
				seen.add(page_url)
				core = _nc(name)
				if not core: continue
				if norm_query in core or core in norm_query:
					candidates.append(page_url)
				if len(candidates) >= 4: break
			if not candidates: return self.sources

			threads = []
			for page_url in candidates:
				threads.append(workers.Thread(self.get_sources, page_url))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('ZOOQLE')
			return self.sources

	def get_sources(self, page_url):
		try:
			html = client.request(page_url, timeout=10)
			if not html: return
		except:
			source_utils.scraper_error('ZOOQLE')
			return
		for dl_url, info_hash, label in _RE_ZOOQLE_DL.findall(html):
			try:
				name = source_utils.clean_name(label.strip())
				if not source_utils.check_title(self.title, self.aliases, name, self.year, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.year)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue
				hash = info_hash.lower()
				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url)
				info = ' | '.join(info)
				self.sources_append({'provider': 'zooqle', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
					'direct': False, 'debridonly': True, 'size': 0})
			except:
				source_utils.scraper_error('ZOOQLE')
