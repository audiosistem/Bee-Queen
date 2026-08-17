# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re, html as _html_mod
from urllib.parse import quote, unquote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

_RE_SIZE = re.compile(r'(\d+(?:\.\d+)?)\s*(GB|MB|GiB|MiB)', re.IGNORECASE)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://bittorrented.com'
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
			url = '%s/search/?q=%s&category=0' % (self.base_link, quote(query))
			html = client.request(url, timeout=10)
			if not html: return self.sources

			text = _html_mod.unescape(html)
			parts = re.split(r'(magnet:\?[^"\'<\s]+)', text)
			i = 1
			while i < len(parts) - 1:
				raw_magnet = parts[i].replace('&amp;', '&')
				before = parts[i - 1][-800:]
				i += 2
				ih_m = re.search(r'btih:([a-fA-F0-9]{40})', raw_magnet, re.IGNORECASE)
				if not ih_m: continue
				hash = ih_m.group(1).lower()
				dn_m = re.search(r'[&?]dn=([^&"\'<\s]+)', raw_magnet)
				name = unquote(dn_m.group(1)).replace('+', ' ').strip() if dn_m else ''
				if not name:
					t_m = re.search(r'<a[^>]+class="[^"]*name[^"]*"[^>]*>([^<]{5,80})<', before, re.IGNORECASE)
					if t_m: name = t_m.group(1).strip()
				if not name: continue
				name = source_utils.clean_name(name)

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				quality, info = source_utils.get_release_quality(name_info, raw_magnet)
				sz_m = _RE_SIZE.search(before[-400:])
				dsize = 0
				if sz_m:
					try:
						dsize, isize = source_utils._size(sz_m.group(0))
						info.insert(0, isize)
					except: pass
				info = ' | '.join(info)
				seeds_m = re.search(r'(\d+)\s*seeder', before[-400:], re.IGNORECASE)
				seeders = int(seeds_m.group(1)) if seeds_m else 0

				self.sources_append({'provider': 'bittorrented', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': raw_magnet, 'info': info,
					'direct': False, 'debridonly': True, 'size': dsize})
			return self.sources
		except:
			source_utils.scraper_error('BITTORRENTED')
			return self.sources
