# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# damag.net -- DHT-crawl index (67M+ resources), two-step like 1337x above:
# the results listing only carries a short per-item detail-page path (e.g.
# "/53MOpSe") plus a file count and a raw byte size -- no magnet/info_hash
# inline -- so each candidate needs a second GET to its own detail page
# (which does inline a bare `magnet:?xt=urn:btih:...`, no display name or
# trackers of its own) before it's usable. Confirmed live 2026-09-03 (ported
# from Starfleet's own investigation the same session, see
# resources/lib/torrent_sources.py's search_damag() docstring): Origin and
# Referer headers are REQUIRED on every request here -- a request without
# them gets silently 302'd to /nsfw (403) instead of running the actual
# search, regardless of query content (even a plain "ubuntu" hits it) or
# any cookie/token. The hidden "token" field on the search form was
# confirmed live to work fine left blank (not a per-session CSRF value that
# gets validated).

DAMAG_BASE = 'https://damag.net'
_DAMAG_HEADERS = {'Origin': DAMAG_BASE, 'Referer': DAMAG_BASE + '/'}
_RE_ROW = re.compile(
	r'<a href="(/[A-Za-z0-9]+)"\s+target="_blank"\s+id="res\d+">([^<]+)</a>'
	r'.*?<span id="size\d+"[^>]*>(\d+)</span>',
	re.DOTALL
)
_RE_TOKEN = re.compile(r'name="token"\s+value="([^"]*)"')
_RE_MAGNET = re.compile(r'magnet:\?xt=urn:btih:([A-Fa-f0-9]{40})')


class source:
	priority = 8
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = DAMAG_BASE
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		self.items = []
		self.items_append = self.items.append
		try:
			if 'tvshowtitle' in data:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
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

			query = '%s %s' % (re.sub(r'[^A-Za-z0-9\s\.-]+', '', self.title), self.hdlr)
			self.get_items(query)

			threads = []
			append = threads.append
			for i in self.items:
				append(workers.Thread(self.get_sources, i))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('DAMAGNET')
			return self.sources

	def get_items(self, query):
		try:
			home = client.request(self.base_link + '/', headers=_DAMAG_HEADERS, timeout=10)
			tok_m = _RE_TOKEN.search(home or '')
			token = tok_m.group(1) if tok_m else ''
			post = {'token': token, 'q': query, 'wanted': '50'}
			results = client.request(self.base_link + '/', post=post, headers=_DAMAG_HEADERS, timeout=15)
			if not results: return
		except:
			source_utils.scraper_error('DAMAGNET')
			return
		for path, raw_name, size_b in _RE_ROW.findall(results):
			try:
				name = source_utils.clean_name(raw_name.strip())
				if not name: continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				dsize, isize = source_utils.convert_size(int(size_b))
				self.items_append((name, name_info, path, isize, dsize))
			except:
				source_utils.scraper_error('DAMAGNET')

	def get_sources(self, item):
		try:
			name, name_info, path, isize, dsize = item
			quality, info = source_utils.get_release_quality(name_info, path)
			if isize: info.insert(0, isize)
			info = ' | '.join(info)
			detail = client.request(self.base_link + path, headers=_DAMAG_HEADERS, timeout=10)
			m = _RE_MAGNET.search(detail or '')
			if not m: return
			hash = m.group(1).lower()
			url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
			self.sources_append({'provider': 'damagnet', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name, 'name_info': name_info,
				'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
		except:
			source_utils.scraper_error('DAMAGNET')
