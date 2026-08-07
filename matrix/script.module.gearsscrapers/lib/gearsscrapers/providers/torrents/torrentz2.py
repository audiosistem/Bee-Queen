# created for Fenomscrapers
"""
	Fenomscrapers Project
"""

import re
from urllib.parse import quote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# torrentz2.nz's listing page no longer carries magnets or info-hashes inline
# (confirmed live) -- each result's /torrent/<id> uses an internal Torrentz2
# ID, not the real hash, so the magnet has to be fetched from that torrent's
# own detail page. The magnet href there is HTML-entity-encoded (&#x3D; for
# '=', &amp; for '&'), decoded via client.replaceHTMLCodes().
_RE_TZ2_ROW = re.compile(
	r'<a href="/torrent/([a-f0-9]+)">(.*?)</a>.*?<span class="s">([^<]*)</span>\s*<span class="u">(\d+)</span>',
	re.IGNORECASE | re.DOTALL)
_RE_TZ2_MAGNET = re.compile(r'href="(magnet:[^"]+)"', re.IGNORECASE)


class source:
	priority = 4
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://torrentz2.nz"
		self.search_link = '/search?q=%s'
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
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (re.sub(r'[^A-Za-z0-9\s\.-]+', '', self.title), self.hdlr)
			url = '%s%s' % (self.base_link, self.search_link % quote_plus(query))

			results = client.request(url, timeout=10)
			if not results: return self.sources
			candidates = self._collect_candidates(results)
			if not candidates: return self.sources

			threads = []
			for c in candidates:
				threads.append(workers.Thread(self.get_sources, c['id'], c['name'], c['seeders'], c['size']))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORRENTZ2')
			return self.sources

	def _collect_candidates(self, html):
		candidates = []
		for m in _RE_TZ2_ROW.finditer(html):
			torrent_id, name, size_text, seeders_text = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
			name = source_utils.clean_name(name)
			if not name: continue
			try:
				seeders = int(seeders_text.replace(',', ''))
			except: seeders = 0
			if self.min_seeders > seeders: continue
			if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
			candidates.append({'id': torrent_id, 'name': name, 'seeders': seeders, 'size': size_text})
			if len(candidates) >= 15: break
		return candidates

	def get_sources(self, torrent_id, name, seeders, size_text):
		try:
			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			detail = client.request('%s/torrent/%s' % (self.base_link, torrent_id), timeout=8)
			if not detail: return
			mag_m = _RE_TZ2_MAGNET.search(detail)
			if not mag_m: return
			url = client.replaceHTMLCodes(mag_m.group(1))
			hash_m = re.search(r'btih:([a-fA-F0-9]{40})', url, re.IGNORECASE)
			if not hash_m: return
			hash = hash_m.group(1).lower()

			quality, info = source_utils.get_release_quality(name_info, url)
			try:
				dsize, isize = source_utils._size(size_text)
				info.insert(0, isize)
			except: dsize = 0
			info = ' | '.join(info)

			self.sources_append({'provider': 'torrentz2', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
										'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
		except:
			source_utils.scraper_error('TORRENTZ2')

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.search_series = search_series
			self.total_seasons = total_seasons
			self.bypass_filter = bypass_filter

			self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
			self.aliases = data['aliases']
			self.imdb = data['imdb']
			self.year = data['year']
			self.season_x = data['season']
			self.season_xx = self.season_x.zfill(2)
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', self.title)
			if search_series:
				queries = [query + ' Season', query + ' Complete']
			else:
				queries = [query + ' S%s' % self.season_xx, query + ' Season %s' % self.season_x]

			candidates = []
			for q in queries:
				url = '%s%s' % (self.base_link, self.search_link % quote_plus(q))
				html = client.request(url, timeout=10)
				if not html: continue
				candidates.extend(self._collect_pack_candidates(html))

			threads = []
			for c in candidates:
				threads.append(workers.Thread(self.get_sources_packs, c['id'], c['name'], c['seeders'], c['size']))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORRENTZ2')
			return self.sources

	def _collect_pack_candidates(self, html):
		candidates = []
		seen = set()
		for m in _RE_TZ2_ROW.finditer(html):
			torrent_id, name, size_text, seeders_text = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
			if torrent_id in seen: continue
			seen.add(torrent_id)
			name = source_utils.clean_name(name)
			if not name: continue
			try:
				seeders = int(seeders_text.replace(',', ''))
			except: seeders = 0
			candidates.append({'id': torrent_id, 'name': name, 'seeders': seeders, 'size': size_text})
			if len(candidates) >= 15: break
		return candidates

	def get_sources_packs(self, torrent_id, name, seeders, size_text):
		try:
			episode_start, episode_end = 0, 0
			if not self.search_series:
				if not self.bypass_filter:
					valid, episode_start, episode_end = source_utils.filter_season_pack(self.title, self.aliases, self.year, self.season_x, name)
					if not valid: return
				package = 'season'
			else:
				if not self.bypass_filter:
					valid, last_season = source_utils.filter_show_pack(self.title, self.aliases, self.imdb, self.year, self.season_x, name, self.total_seasons)
					if not valid: return
				else: last_season = self.total_seasons
				package = 'show'

			name_info = source_utils.info_from_name(name, self.title, self.year, season=self.season_x, pack=package)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			detail = client.request('%s/torrent/%s' % (self.base_link, torrent_id), timeout=8)
			if not detail: return
			mag_m = _RE_TZ2_MAGNET.search(detail)
			if not mag_m: return
			url = client.replaceHTMLCodes(mag_m.group(1))
			hash_m = re.search(r'btih:([a-fA-F0-9]{40})', url, re.IGNORECASE)
			if not hash_m: return
			hash = hash_m.group(1).lower()

			quality, info = source_utils.get_release_quality(name_info, url)
			try:
				dsize, isize = source_utils._size(size_text)
				info.insert(0, isize)
			except: dsize = 0
			info = ' | '.join(info)

			item = {'provider': 'torrentz2', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info, 'quality': quality,
						'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize, 'package': package}
			if self.search_series: item.update({'last_season': last_season})
			elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end})
			self.sources_append(item)
		except:
			source_utils.scraper_error('TORRENTZ2')
