# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import json
from urllib.parse import urlencode
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# TorrentFunk's HTML search.php is genuinely Cloudflare JS-challenge
# protected (confirmed live) -- but the site documents/exposes a free,
# keyless JSON API at /api/search.json with real server-side query search,
# no CF in front of it at all. Ready-to-use magnet + infohash straight in
# the response, no scraping needed.

API_BASE = 'https://www.torrentfunk.com/api/search.json'
_CAT = {'movie': 1, 'tv': 3}


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://www.torrentfunk.com'
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

			query = '%s %s' % (self.title, self.hdlr)
			params = {'q': query[:100], 'limit': 20, 'sort': 'seeds', 'order': 'desc', 'category': cat}
			url = '%s?%s' % (API_BASE, urlencode(params))
			raw = client.request(url, timeout=8)
			if not raw: return self.sources
			payload = json.loads(raw)
			if payload.get('status') != 'ok': return self.sources
		except:
			source_utils.scraper_error('TORRENTFUNK')
			return self.sources

		for item in payload.get('results', []):
			try:
				hash = (item.get('infohash') or '').lower()
				raw_name = item.get('name', '')
				if not hash or not raw_name: continue
				name = source_utils.clean_name(raw_name)

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				magnet = item.get('magnet') or ('magnet:?xt=urn:btih:%s&dn=%s' % (hash, name))
				quality, info = source_utils.get_release_quality(name_info, magnet)
				try:
					dsize, isize = source_utils._size(item.get('size', ''))
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				seeders = item.get('seeds', 0) or 0
				if self.min_seeders > seeders: continue

				self.sources_append({'provider': 'torrentfunk', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
					'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('TORRENTFUNK')
		return self.sources
