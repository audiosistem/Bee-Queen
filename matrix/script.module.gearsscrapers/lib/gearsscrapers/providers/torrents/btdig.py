# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# btdig.com -- a DHT-crawler search engine: indexes files actually seen live
# on the DHT swarm rather than scraping a tracker site's own upload database,
# so it turns up torrents pure tracker-scrapers miss. No live seeder count is
# exposed (a DHT crawler only tracks "last seen" + the file listing, not
# ongoing swarm health) and relevance can be loose (full-text match against
# files INSIDE a torrent, not just its own name) -- source_utils.check_title
# below is what actually filters out the wrong matches this site returns.
# Magnet links are already inline on the search results page itself, no
# per-item detail-page fetch needed (unlike torlock.py).

_RE_NAME   = re.compile(r'class="torrent_name"[^>]*><a[^>]*>([^<]+)</a>', re.IGNORECASE)
_RE_MAGNET = re.compile(r'href="(magnet:\?[^"]+)"', re.IGNORECASE)


class source:
	priority = 8
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://btdig.com'
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

			query = quote('%s %s' % (self.title, self.hdlr))
			url = '%s/search?q=%s' % (self.base_link, query)
			html = client.request(url, timeout=10)
			if not html: return self.sources
		except:
			source_utils.scraper_error('BTDIG')
			return self.sources

		for block in html.split('class="one_result"')[1:]:
			try:
				name_m = _RE_NAME.search(block)
				magnet_m = _RE_MAGNET.search(block)
				if not (name_m and magnet_m): continue
				ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet_m.group(1), re.IGNORECASE)
				if not ih_m: continue
				hash = ih_m.group(1).lower()
				magnet = magnet_m.group(1).replace('&amp;', '&')
				raw_name = name_m.group(1)
				name = source_utils.clean_name(raw_name)

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				quality, info = source_utils.get_release_quality(name_info, magnet)
				info = ' | '.join(info)
				self.sources_append({'provider': 'btdig', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
					'direct': False, 'debridonly': True, 'size': 0})
			except:
				source_utils.scraper_error('BTDIG')
		return self.sources
