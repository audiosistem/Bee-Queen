# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# torlock2.com (the old domain this provider pointed at) has a history of
# silent breakage as the site's HTML shifted -- confirmed live that the
# current real site is plain www.torlock.com with no Cloudflare wall at
# all, so this points there directly instead. Magnets aren't in the
# listing rows themselves, only on each torrent's own detail page, so a
# handful of candidate detail pages get fetched in parallel (same pattern
# as zooqle.py's own candidate-page fetch).

_CAT = {'movie': 'movie', 'tv': 'television'}
_RE_ROW = re.compile(r'<a class="tl-name" href="(/torrent/\d+/[^"]+)">([^<]+)</a>', re.IGNORECASE)


class source:
	priority = 7
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://www.torlock.com"
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.aliases = data['aliases']
			self.year = data['year']
			if 'tvshowtitle' in data:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
				self.episode_title = data['title']
				self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
				cat = _CAT['tv']
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
				cat = _CAT['movie']
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = quote(re.sub(r'\s+', '-', self.title.strip()))
			url = '%s/%s/torrents/%s.html?sort=seeds&page=1' % (self.base_link, cat, query)
			html = client.request(url, timeout=10)
			if not html: return self.sources

			candidates = []
			seen = set()
			for path, name in _RE_ROW.findall(html):
				if path in seen: continue
				seen.add(path)
				candidates.append((path, name.strip()))
				if len(candidates) >= 15: break
			if not candidates: return self.sources

			threads = []
			for path, name in candidates:
				threads.append(workers.Thread(self.get_sources, path, name))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORLOCK')
			return self.sources

	def get_sources(self, path, raw_name):
		try:
			detail = client.request(self.base_link + path, timeout=8)
			if not detail: return
			m = re.search(r'magnet:\?[^"\'<\s]+', detail)
			if not m: return
			magnet = m.group(0).replace('&amp;', '&')
			ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
			if not ih_m: return
			hash = ih_m.group(1).lower()
			name = source_utils.clean_name(raw_name)

			if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): return
			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			quality, info = source_utils.get_release_quality(name_info, magnet)
			info = ' | '.join(info)
			self.sources_append({'provider': 'torlock', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('TORLOCK')
