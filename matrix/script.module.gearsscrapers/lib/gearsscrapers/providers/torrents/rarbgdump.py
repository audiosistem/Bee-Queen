# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# rarbgdump.com -- a static archive of RARBG's own database (2.8M+ entries;
# RARBG itself has been dead since 2023). Confirmed live 2026-09-03 (ported
# from Starfleet's own investigation the same session, see
# resources/lib/torrent_sources.py's search_rarbgdump() docstring): real
# JSON API (POST /api/search {"query":...}), no Cloudflare interstitial
# actually in front of it despite the challenge-platform scripts the page
# itself loads. Every hit already carries a real 40-char btih hash plus its
# own seeders/leechers straight in the response -- no per-item resolve step
# needed. Since RARBG is dead, this is a frozen 2023 snapshot, not a live
# crawl -- seeder counts are whatever they were at RARBG's own last update,
# not current -- but the swarms themselves (DHT-level) can still be alive
# years later for anything popular enough. Each hit's own 'cat' field (e.g.
# "movies_x265_4k_hdr", "music_mp3", "games_pc_iso") is real per-source
# metadata, used here to drop non-video categories before they ever reach
# the title/quality filters below.

RARBGDUMP_API = 'https://rarbgdump.com/api/search'


class source:
	priority = 5
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = RARBGDUMP_API
		self.min_seeders = 0

	def _query(self, query):
		try:
			import json
			body = json.dumps({'query': query})
			headers = {'Content-Type': 'application/json'}
			raw = client.request(self.base_link, post=body, headers=headers, timeout=12)
			if not raw: return []
			data = json.loads(raw)
			items = data.get('results') or []
			return items if isinstance(items, list) else []
		except:
			source_utils.scraper_error('RARBGDUMP')
			return []

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			is_tv = 'tvshowtitle' in data
			if is_tv:
				title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
				episode_title = data['title']
				hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
			else:
				title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				episode_title = None
				hdlr = data['year']
			aliases = data['aliases']
			year = data['year']
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', title)
			items = self._query(query)
		except:
			source_utils.scraper_error('RARBGDUMP')
			return self.sources

		for item in items:
			try:
				cat = (item.get('cat') or '').lower()
				if not (cat.startswith('movies') or cat.startswith('tv')): continue

				raw_name = (item.get('title') or '').strip()
				hash = (item.get('hash') or '').lower()
				if not raw_name or len(hash) != 40: continue

				name = source_utils.clean_name(raw_name)
				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				try:
					seeders = int(item.get('seeders') or 0)
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					b = int(item.get('size') or 0)
					if b:
						dsize, isize = source_utils.convert_size(b)
						if isize: info.insert(0, isize)
					else:
						dsize = 0
				except: dsize = 0
				info = ' | '.join(info)

				self.sources_append({'provider': 'rarbgdump', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('RARBGDUMP')
		return self.sources
