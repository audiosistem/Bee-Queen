# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

_RE_ROW = re.compile(r'href="(/([a-fA-F0-9]{40})/([^"]+))"', re.IGNORECASE)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://www.magnetdl.hair'
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.aliases = data['aliases']
			self.year = data['year']
			if 'tvshowtitle' in data:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = data['title']
				self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (self.title, self.hdlr)
			slug = re.sub(r'[^\w\s-]', '', query.lower()).strip()
			slug = re.sub(r'[\s_]+', '-', slug)
			first = slug[0] if slug else 'm'
			url = '%s/%s/%s/' % (self.base_link, first, slug)
			html = client.request(url, timeout=10)
			if not html: return self.sources

			seen_hashes = set()
			for m in _RE_ROW.finditer(html):
				hash = m.group(2).lower()
				if hash in seen_hashes: continue
				raw_name = m.group(3)
				name = source_utils.clean_name(re.sub(r'[_+]+', ' ', raw_name).strip())
				if not name: continue

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue
				seen_hashes.add(hash)

				url_magnet = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url_magnet)
				info = ' | '.join(info)

				self.sources_append({'provider': 'magnetdl', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url_magnet, 'info': info,
					'direct': False, 'debridonly': True, 'size': 0})
			return self.sources
		except:
			source_utils.scraper_error('MAGNETDL')
			return self.sources
