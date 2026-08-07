# ported from Starfleet's torrent_sources.py for gearsscrapers
# Distinct from this addon's existing torrentdownload.py (torrentdownload.info) --
# this targets torrentdownloads.pro's RSS search feed, which returns info_hash
# directly with no per-item detail-page fetch needed.
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

_RE_ITEM = re.compile(
	r'<info_hash>([a-fA-F0-9]{40})</info_hash>.*?'
	r'<title>(.+?)</title>.*?'
	r'<size>(\d+)</size>.*?'
	r'<seeders>(\d+)</seeders>',
	re.IGNORECASE | re.DOTALL)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://www.torrentdownloads.pro'
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
				cat = '8'
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
				cat = '4'
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (self.title, self.hdlr)
			url = '%s/rss.xml?new=1&type=search&cid=%s&search=%s' % (self.base_link, cat, quote(query))
			html = client.request(url, timeout=10)
			if not html: return self.sources

			for m in _RE_ITEM.finditer(html):
				hash, name, size_b, seeders = m.group(1).lower(), m.group(2).strip(), int(m.group(3)), int(m.group(4))
				name = source_utils.clean_name(name)
				if not name: continue

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue
				if self.min_seeders > seeders: continue

				url_magnet = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url_magnet)
				try:
					dsize, isize = source_utils._size('%.1f GB' % (size_b / 1_073_741_824)) if size_b >= 1_073_741_824 else source_utils._size('%d MB' % (size_b // 1_048_576))
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				self.sources_append({'provider': 'torrentdownloads', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url_magnet, 'info': info,
					'direct': False, 'debridonly': True, 'size': dsize})
			return self.sources
		except:
			source_utils.scraper_error('TORRENTDOWNLOADS')
			return self.sources
