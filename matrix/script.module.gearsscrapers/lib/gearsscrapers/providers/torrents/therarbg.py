# ported from Starfleet's torrent_sources.py for gearsscrapers
# therarbg.com is an actively-run unofficial revival of the RARBG branding
# (original RARBG shut down in 2023) -- fully open, no Cloudflare wall, magnet
# link is inline on the detail page with no token dance needed.
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

_CAT = {'movie': 'Movies', 'tv': 'TV'}
_RE_ROW = re.compile(r'href="(/post-detail/[a-z0-9]+/[^"]+)"\s+style="font-weight: 700"\s*>([^<]+)</a>', re.IGNORECASE)
_RE_SIZE = re.compile(r'sizeCell"[^>]*>([^<]+)</td>')
_RE_SEEDS = re.compile(r'color:\s*green">(\d+)</td>')
_RE_MAGNET = re.compile(r'href="(magnet:\?xt=urn:btih:([0-9a-fA-F]{40})[^"]*)"')


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://therarbg.com'
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
				cat = _CAT['tv']
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
				cat = _CAT['movie']
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (re.sub(r'\s+', ' ', self.title).strip(), self.hdlr)
			url = '%s/get-posts/keywords:%s:category:%s/' % (self.base_link, quote_plus(query.strip()), cat)
			html = client.request(url, timeout=10)
			if not html: return self.sources

			matches = list(_RE_ROW.finditer(html))
			candidates = []
			for i, m in enumerate(matches):
				if len(candidates) >= 8: break
				name = source_utils.clean_name(m.group(2).strip())
				if not name: continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				start = m.end()
				end = matches[i + 1].start() if i + 1 < len(matches) else start + 1200
				block = html[start:end]
				seeds_m = _RE_SEEDS.search(block)
				candidates.append({'path': m.group(1), 'name': name, 'seeds': int(seeds_m.group(1)) if seeds_m else 0})

			threads = []
			for c in candidates:
				threads.append(workers.Thread(self.get_sources, c))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('THERARBG')
			return self.sources

	def get_sources(self, c):
		try:
			html = client.request(self.base_link + c['path'], timeout=8)
			if not html: return
			m = _RE_MAGNET.search(html)
			if not m: return
			magnet = m.group(1).replace('&amp;', '&')
			hash = m.group(2).lower()

			name = c['name']
			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			quality, info = source_utils.get_release_quality(name_info, magnet)
			info = ' | '.join(info)
			self.sources_append({'provider': 'therarbg', 'source': 'torrent', 'seeders': c['seeds'], 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('THERARBG')
