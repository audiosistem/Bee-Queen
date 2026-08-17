# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

_TV_TMPL = 'search_results.php?search={q}&cat=41&incldead=0&inclexternal=0&lang=1&sort=seeders&order=desc'
_MOV_TMPL = 'search_results.php?search={q}&cat=1&incldead=0&inclexternal=0&lang=1&sort=size&order=desc'
_RE_NAME = re.compile(r'<a[^>]+title="([^"]+)"', re.IGNORECASE)
_RE_MAG = re.compile(r'href="(magnet:\?[^"]+)"', re.IGNORECASE)
_RE_SIZE = re.compile(r'(\d+(?:[,.]\d+)?)\s*(GiB|MiB|GB|MB)', re.IGNORECASE)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://glodls.club'  # glodls.to now permanently 302-redirects here
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
				tmpl = _TV_TMPL
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
				tmpl = _MOV_TMPL
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (self.title, self.hdlr)
			url = '%s/%s' % (self.base_link, tmpl.format(q=quote(query)))
			html = client.request(url, timeout=10)
			if not html: return self.sources

			for row in html.split('class="t-row"')[1:]:
				try:
					mag_m = _RE_MAG.search(row)
					if not mag_m: continue
					magnet = mag_m.group(1).replace('&amp;', '&').split('&tr')[0]
					ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
					if not ih_m: continue
					hash = ih_m.group(1).lower()
					name_m = _RE_NAME.search(row)
					name = source_utils.clean_name(name_m.group(1)) if name_m else ''
					if not name: continue

					if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
					name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
					if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
					if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

					quality, info = source_utils.get_release_quality(name_info, magnet)
					sz_m = _RE_SIZE.search(row)
					dsize = 0
					if sz_m:
						try:
							dsize, isize = source_utils._size(sz_m.group(0))
							info.insert(0, isize)
						except: pass
					info = ' | '.join(info)

					self.sources_append({'provider': 'glodls', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
						'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
						'direct': False, 'debridonly': True, 'size': dsize})
				except:
					continue
			return self.sources
		except:
			source_utils.scraper_error('GLODLS')
			return self.sources
