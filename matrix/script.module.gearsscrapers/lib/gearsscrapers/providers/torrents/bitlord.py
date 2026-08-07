# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote_plus, unquote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

_RE_MAG = re.compile(r'class="btn btn-default magnet-button[^"]*"[^>]+href="([^"]+)"', re.IGNORECASE)
_RE_SIZE = re.compile(r'<td class="size">(\d+)</td>', re.IGNORECASE)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'http://www.bitlordsearch.com'
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
			html = client.request('%s/search?q=%s' % (self.base_link, quote_plus(query)), timeout=10)
			if not html: return self.sources

			magnets = _RE_MAG.findall(html)
			sizes = _RE_SIZE.findall(html)
			for i, mag in enumerate(magnets):
				mag = mag.replace('&amp;', '&').split('&tr=')[0]
				if 'magnet' not in mag: continue
				dn_m = re.search(r'&dn=([^&]+)', mag)
				name = source_utils.clean_name(unquote(dn_m.group(1)).replace('+', ' ')) if dn_m else ''
				if not name: continue

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				ih_m = re.search(r'btih:([a-fA-F0-9]{40})', mag, re.IGNORECASE)
				hash = ih_m.group(1).lower() if ih_m else ''
				if not hash: continue

				quality, info = source_utils.get_release_quality(name_info, mag)
				dsize = 0
				if i < len(sizes):
					try:
						b = int(sizes[i])
						dsize, isize = source_utils._size('%d MB' % (b // 1_048_576)) if b >= 1_048_576 else (0, '')
						if isize: info.insert(0, isize)
					except: pass
				info = ' | '.join(info)

				self.sources_append({'provider': 'bitlord', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': mag, 'info': info,
					'direct': False, 'debridonly': True, 'size': dsize})
			return self.sources
		except:
			source_utils.scraper_error('BITLORD')
			return self.sources
