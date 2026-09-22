# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# torrent9.bid -- French-language torrent index. Confirmed live 2026-09-13:
# torrent9.town (a comparable open-source Stremio scraper's hardcoded
# default) is now a thin WordPress landing shell with no real search of
# its own -- it points readers at "Voir le site complet" -> ww1.fit/torrent9/,
# itself just a wrapper page whose real content is an
# <iframe src="https://www.torrent9.bid">. torrent9.bid is the actual live
# site with real listings/search. Same real magnet-per-detail-page shape
# as torrentgalaxy.py/redetorrent.py elsewhere in this addon.

_RE_ROW = re.compile(
	r'<a href="(/detail/\d+)" title="([^"]+)"[^<]*</a></td>\s*'
	r'<td[^>]*>([^<]+)</td>\s*'
	r'<td[^>]*><span class="seed_ok">(\d+)',
	re.IGNORECASE
)
_RE_MAGNET = re.compile(r'href="(magnet:[^"]+)"', re.IGNORECASE)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['fr']
		self.base_link = 'https://www.torrent9.bid'
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
			html = client.request('%s/recherche/%s' % (self.base_link, quote(query)), timeout=10)
			# A query with no matches returns zero table rows rather than
			# an error -- retry once without the trailing year.
			if not html or 'table-striped' not in html:
				year_stripped = re.sub(r'\s+\d{4}$', '', query).strip()
				if year_stripped and year_stripped != query:
					html = client.request('%s/recherche/%s' % (self.base_link, quote(year_stripped)), timeout=10)
			if not html: return self.sources

			candidates = []
			for path, name, size_text, seeds_text in _RE_ROW.findall(html):
				if len(candidates) >= 8: break
				name = source_utils.clean_name(name.strip())
				if not name: continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				candidates.append((self.base_link + path, name, size_text.strip(), int(seeds_text)))
			if not candidates: return self.sources

			threads = []
			for detail_url, name, size_text, seeds in candidates:
				threads.append(workers.Thread(self.get_sources, detail_url, name, size_text, seeds))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORRENT9')
			return self.sources

	def get_sources(self, detail_url, name, size_text, seeds):
		try:
			detail = client.request(detail_url, timeout=10)
			if not detail: return
			mag_m = _RE_MAGNET.search(detail)
			if not mag_m: return
			magnet = mag_m.group(1)
			ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
			if not ih_m: return
			hash = ih_m.group(1).lower()

			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			seeders = seeds
			if self.min_seeders > seeders: return

			quality, info = source_utils.get_release_quality(name_info, magnet)
			dsize, isize = source_utils._size(size_text)
			if isize: info.insert(0, isize)
			info = ' | '.join(info)

			self.sources_append({'provider': 'torrent9', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'fr', 'url': magnet, 'info': info,
				'direct': False, 'debridonly': True, 'size': dsize})
		except:
			source_utils.scraper_error('TORRENT9')
