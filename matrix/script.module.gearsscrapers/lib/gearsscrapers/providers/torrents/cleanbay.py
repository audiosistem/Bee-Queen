# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# cleanbay.netlify.app -- the frontend itself has no API of its own; every
# search actually goes straight from the browser to a separate Render-hosted
# backend, testbay.onrender.com (found by reading the site's own shipped JS
# bundle for the literal API URL). That backend live-queries piratebay/yts/
# eztv/linuxtracker/libgen/nyaa per-request and already returns ready-to-use
# magnet URIs, so no per-item resolve step is needed here. Confirmed live
# 2026-09-03 (ported from Starfleet's own investigation the same session,
# see resources/lib/torrent_sources.py's search_cleanbay() docstring): an
# unfiltered query for a popular title returned 0 results -- piratebay/yts/
# linuxtracker/eztv all appear dead upstream of this backend right now --
# but the same backend still returns real hits (real magnets/seeders) for
# titles nyaa carries. Render's free tier sleeps this backend after
# inactivity -- a cold start alone took ~10s in testing -- so this uses a
# longer-than-usual timeout; a search that catches it asleep just times out
# like any other slow source rather than erroring.

CLEANBAY_API = 'https://testbay.onrender.com/api/v1/search'
_RE_HASH = re.compile(r'btih:([a-fA-F0-9]{40})', re.IGNORECASE)


class source:
	priority = 5
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = CLEANBAY_API
		self.min_seeders = 0

	def _query(self, query):
		try:
			import json
			body = json.dumps({
				'search_term': query,
				'include_categories': [], 'exclude_categories': [],
				'include_sites': [], 'exclude_sites': [],
			})
			headers = {'Content-Type': 'application/json'}
			raw = client.request(self.base_link, post=body, headers=headers, timeout=20)
			if not raw: return []
			import json as _json
			data = _json.loads(raw)
			items = data.get('data') or []
			return items if isinstance(items, list) else []
		except:
			source_utils.scraper_error('CLEANBAY')
			return []

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			if 'tvshowtitle' in data:
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
			source_utils.scraper_error('CLEANBAY')
			return self.sources

		for item in items:
			try:
				raw_name = (item.get('name') or '').strip()
				magnet = item.get('magnet') or ''
				ih_m = _RE_HASH.search(magnet)
				if not raw_name or not ih_m: continue
				hash = ih_m.group(1).lower()

				name = source_utils.clean_name(raw_name)
				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = magnet
				try:
					seeders = int(item.get('seeders') or 0)
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					dsize, isize = source_utils._size(item.get('size') or '0')
					if isize: info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				self.sources_append({'provider': 'cleanbay', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('CLEANBAY')
		return self.sources
