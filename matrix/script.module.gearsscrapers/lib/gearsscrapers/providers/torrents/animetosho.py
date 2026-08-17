# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import json
from urllib.parse import urlencode
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# feed.animetosho.org/json -- documented, keyless JSON search endpoint for
# anime releases, no scraping needed. Its own 'magnet_uri' field uses a
# base32 BTIH (incompatible with this addon's hex-based hash handling), but
# it also returns a separate plain hex 'info_hash' field directly, so that's
# used instead and a normal magnet URL is built from it like every other
# provider here.

API_BASE = 'https://feed.animetosho.org/json'


class source:
	priority = 5
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://animetosho.org'
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			if 'tvshowtitle' in data:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = data['title']
				self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = data['year']
			self.aliases = data['aliases']
			self.year = data['year']
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (self.title, self.hdlr)
			url = '%s?%s' % (API_BASE, urlencode({'q': query}))
			raw = client.request(url, timeout=8)
			if not raw: return self.sources
			payload = json.loads(raw)
		except:
			source_utils.scraper_error('ANIMETOSHO')
			return self.sources

		for item in payload:
			try:
				hash = (item.get('info_hash') or '').lower()
				raw_name = item.get('torrent_name') or item.get('title') or ''
				if not hash or not raw_name: continue
				name = source_utils.clean_name(raw_name)

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size_bytes = float(item.get('total_size') or 0)
					dsize, isize = source_utils._size('%.2f GB' % (size_bytes / 1073741824))
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				seeders = item.get('seeders', 0) or 0
				if self.min_seeders > seeders: continue

				self.sources_append({'provider': 'animetosho', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
					'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('ANIMETOSHO')
		return self.sources
