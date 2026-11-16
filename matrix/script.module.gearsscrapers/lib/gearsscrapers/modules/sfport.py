# ported from Starfleet's torrent_sources.py / anime_sources.py for gearsscrapers
"""
	gearsscrapers Project

	Shared base for the providers that only differ in how they fetch a result list: a provider gives fetch(query) -> a list of
	{'name', 'hash', 'seeders', 'size'} (size as text such as '1.4 GB', or bytes) and this class does the title / season / language
	checks, the quality and size info and the packs, the same way the other providers do.
"""

import re
import base64
from urllib.parse import quote_plus
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers


def _clean_query(title):
	return re.sub(r'\s+', ' ', re.sub(r'[^A-Za-z0-9\s\.-]+', '', title)).strip()


class Provider:
	name = ''                # shown in the source list / used as the provider id
	log = ''                 # tag for scraper_error
	priority = 5
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	title_only = False       # also search the bare title (indexes that do not match the SxxExx part of a query)
	anime = False            # anime releases carry absolute episode numbers: accept "S2 - 05" / " - 05 " as well as S02E05
	min_seeders = 0
	language = ['en']

	def fetch(self, query):
		return []

	def _size(self, size):
		try:
			if isinstance(size, (int, float)):
				size = '%.2f GB' % (float(size) / 1073741824)
			return source_utils._size(size)
		except:
			return 0, ''

	def _make(self, row, name, name_info, package=None, extra=None):
		hash = row['hash']
		url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
		quality, info = source_utils.get_release_quality(name_info, url)
		dsize, isize = self._size(row.get('size'))
		if isize: info.insert(0, isize)
		item = {'provider': self.name, 'source': 'torrent', 'seeders': row.get('seeders') or 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': ' | '.join(info),
				'direct': False, 'debridonly': True, 'size': dsize}
		if package: item['package'] = package
		if extra: item.update(extra)
		return item

	def _rows(self, queries):
		rows, seen = [], set()
		threads = []
		results = {}

		def work(q):
			try: results[q] = self.fetch(q) or []
			except: source_utils.scraper_error(self.log)
		for q in queries:
			threads.append(workers.Thread(work, q))
		[i.start() for i in threads]
		[i.join() for i in threads]
		for q in queries:
			for r in results.get(q, []):
				h = (r.get('hash') or '').strip()
				if len(h) == 32:   # base32 form of an infohash
					try: h = base64.b32decode(h.upper()).hex()
					except: continue
				h = h.lower()
				if len(h) != 40 or not r.get('name') or h in seen: continue
				seen.add(h)
				r['hash'] = h
				rows.append(r)
		return rows

	def sources(self, data, hostDict):
		found = []
		if not data: return found
		try:
			aliases = data['aliases']
			year = data['year']
			if 'tvshowtitle' in data:
				title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
				episode_title = data['title']
				season, episode = int(data['season']), int(data['episode'])
				hdlr = 'S%02dE%02d' % (season, episode)
				queries = ['%s %s' % (_clean_query(title), hdlr)]
				if self.title_only: queries.append(_clean_query(title))
				if self.anime:
					queries.append('%s S%d - %02d' % (_clean_query(title), season, episode))
					queries.append('%s %02d' % (_clean_query(title), episode))
			else:
				title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				episode_title = None
				hdlr = year
				queries = ['%s %s' % (_clean_query(title), hdlr)]
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
			rows = self._rows(queries)
		except:
			source_utils.scraper_error(self.log)
			return found
		for row in rows:
			try:
				name = source_utils.clean_name(row['name'])
				if self.anime and episode_title is not None:
					if not self._anime_ok(name, season, episode, hdlr): continue
					name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				else:
					if not source_utils.check_title(title, aliases, name, hdlr, year): continue
					name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue
				if episode_title is None:   # a movie search can bring back episodes of a show with the same name
					low = name.lower()
					if any(re.search(p, low) for p in (r'[.-]s\d{2}e\d{2}([.-]?)', r'[.-]s\d{2}([.-]?)', r'[.-]season[.-]?\d{1,2}[.-]?')): continue
				if self.min_seeders > (row.get('seeders') or 0): continue
				found.append(self._make(row, name, name_info))
			except:
				source_utils.scraper_error(self.log)
		return found

	@staticmethod
	def _anime_ok(name, season, episode, hdlr):
		if hdlr.lower() in name.lower(): return True
		n = name.lower().replace('.', ' ')
		if re.search(r'\bs0*%d\s*-\s*0*%d\b' % (season, episode), n): return True
		if season == 1 and re.search(r'(?<![\d.])-\s*0*%d(?:v\d)?(?![\d.])(?!\s*(?:bit|fps|kbps))' % episode, n): return True
		return False

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		found = []
		if not data or not self.pack_capable: return found
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season_x = data['season']
			season_xx = season_x.zfill(2)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
			q = _clean_query(title)
			queries = [q + ' Season', q + ' Complete'] if search_series else [q + ' S%s' % season_xx, q + ' Season %s' % season_x]
			rows = self._rows(queries)
		except:
			source_utils.scraper_error(self.log)
			return found
		for row in rows:
			try:
				name = source_utils.clean_name(row['name'])
				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season_x, name)
						if not valid: continue
					package = 'season'
				else:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season_x, name, total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'
				name_info = source_utils.info_from_name(name, title, year, season=season_x, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue
				if self.min_seeders > (row.get('seeders') or 0): continue
				extra = {}
				if search_series: extra['last_season'] = last_season
				elif episode_start: extra.update({'episode_start': episode_start, 'episode_end': episode_end})
				found.append(self._make(row, name, name_info, package, extra))
			except:
				source_utils.scraper_error(self.log)
		return found
