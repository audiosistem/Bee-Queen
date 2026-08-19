# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
import json
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# torseek.org -- Next.js 15 App-Router site, fully client-rendered (its own
# RSC payload for /search confirmed live to carry no server-fetched torrent
# data at all). There's no REST search endpoint -- the compiled page JS
# instead calls createServerReference("<40-hex id>", ..., "search"),
# Next.js' React Server Actions machinery, which at runtime becomes a POST
# to the CURRENT page URL carrying a `Next-Action: <id>` header, with the
# call's arguments JSON-encoded as the raw body (`[query, page]`).
# Confirmed live (ported from Starfleet's own investigation the same
# session, see resources/lib/torrent_sources.py's search_torseek()
# docstring) this is reproducible with a plain POST + those two headers, no
# browser/JS execution needed at all -- and the backend is itself a Jackett
# meta-search aggregator (each hit's own `jackettindexer` field names the
# real underlying indexer, e.g. TheRarBG/The Pirate Bay), returning genuine
# magnets with real btih hashes, human release names and live seeder
# counts.
# CAVEAT: that action id is Next.js build output tied to this one specific
# deployment -- it WILL silently change whenever Torseek redeploys, at
# which point this provider degrades to routine POST failures (caught
# below, same as any other dead source) until the id is refreshed by hand.

TORSEEK_BASE = 'https://www.torseek.org'
TORSEEK_SEARCH_ACTION = '60024254f6afa5cc0a7878404013b88cf799b21f57'
_RE_HASH = re.compile(r'btih:([a-fA-F0-9]{40})', re.IGNORECASE)


class source:
	priority = 5
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = TORSEEK_BASE
		self.min_seeders = 0

	def _query(self, query):
		try:
			url = '%s/search?q=%s' % (self.base_link, quote(query))
			headers = {
				'Accept':       'text/x-component',
				'Next-Action':  TORSEEK_SEARCH_ACTION,
				'Content-Type': 'text/plain;charset=UTF-8',
				'Origin':       self.base_link,
				'Referer':      url,
			}
			body = json.dumps([query, 1])
			raw = client.request(url, post=body, headers=headers, timeout=12)
			if not raw: return []
			data = None
			for line in raw.split('\n'):
				if line.startswith('1:') and not line.startswith('1:E'):
					try: data = json.loads(line[2:])
					except: data = None
					break
			if not data or not isinstance(data, dict): return []
			items = data.get('results', [])
			return items if isinstance(items, list) else []
		except:
			source_utils.scraper_error('TORSEEK')
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
			query = '%s %s' % (re.sub(r'[^A-Za-z0-9\s\.-]+', '', title), hdlr)
			items = self._query(query)
		except:
			source_utils.scraper_error('TORSEEK')
			return self.sources

		for item in items:
			try:
				raw_name = (item.get('title') or '').strip()
				magnet = item.get('magnetLink') or item.get('guid') or ''
				ih_m = _RE_HASH.search(magnet)
				if not raw_name or not ih_m: continue
				hash = ih_m.group(1).lower()

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

				self.sources_append({'provider': 'torseek', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('TORSEEK')
		return self.sources
