# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
import time
import random
import string
import xbmc
from json import loads as jsloads
from urllib.parse import quote as _quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# Snowfl.com — magnet metasearch aggregator (limetorrents/1337x/etc).
#
# Reputed hard-to-scrape in the Kodi/scraper community (its own homepage's
# click handler builds the real search URL as
# `"/" + <secret> + "/" + query + "/" + <sessionToken> + "/" + page + "/" +
# sort + "/" + top + "/" + nsfw`, with <secret> looking like a rotating/
# hashed value) — but confirmed live 2026-08-15 (same investigation ported
# from Starfleet's resources/lib/torrent_sources.py search_snowfl(), see
# that function's own docstring for the full story) that <secret> is NOT
# actually computed by any hashing/obfuscation logic at request time: it's
# a literal `var <randomName>="<secret>";` string constant baked directly
# into the plain-text served `b.min.js?v=...` bundle — extractable by a
# plain regex against the freshly-fetched bundle, no JS interpreter ever
# needs to run. <sessionToken> is client-generated and the server accepts
# any 8-char alnum value there (not validated against any prior request).
# The response itself is real, clean JSON — a list of {magnet, age, name,
# size, seeder, leecher, type, site, url, nsfw} — with a ready-to-use
# magnet: URI (real btih hash + tracker list) per item already aggregated
# from multiple trackers.

SNOWFL_BASE = 'https://snowfl.com'
_RE_SNOWFL_JS = re.compile(r'<script[^>]+src="([^"]+\.min\.js\?v=[^"]+)"')
_RE_SNOWFL_SECRET_IDENT = re.compile(r'"/"\s*\+\s*(\w+)\s*\+\s*\(\s*"/"')

_snowfl_secret_cache = {'value': None, 'ts': 0}


def _get_secret():
	now = time.time()
	if _snowfl_secret_cache['value'] and (now - _snowfl_secret_cache['ts']) < 1800:
		return _snowfl_secret_cache['value']
	try:
		home = client.request(SNOWFL_BASE + '/', timeout=10)
		if not home: return None
		m = _RE_SNOWFL_JS.search(home)
		if not m: return None
		js = client.request('%s/%s' % (SNOWFL_BASE, m.group(1)), timeout=10)
		if not js: return None
		m2 = _RE_SNOWFL_SECRET_IDENT.search(js)
		if not m2: return None
		ident = m2.group(1)
		m3 = re.search(re.escape(ident) + r'\s*=\s*"([A-Za-z0-9]{20,60})"', js)
		if not m3: return None
		secret = m3.group(1)
		_snowfl_secret_cache['value'] = secret
		_snowfl_secret_cache['ts'] = now
		return secret
	except:
		source_utils.scraper_error('SNOWFL')
		return None


class source:
	priority = 5
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = SNOWFL_BASE
		self.min_seeders = 0

	def _query(self, query):
		"""One Snowfl API call -> list of raw result dicts (or [] on any
		failure — dead secret, network error, non-JSON response, etc)."""
		secret = _get_secret()
		if not secret: return []
		try:
			token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
			url = '%s/%s/%s/%s/0/NONE/NONE/0' % (self.base_link, secret, _quote(query), token)
			raw = client.request(url, timeout=12)
			if not raw: return []
			items = jsloads(raw)
			return items if isinstance(items, list) else []
		except:
			source_utils.scraper_error('SNOWFL')
			return []

	def sources(self, data, hostDict):
		xbmc.log('[SF-DIAG] SNOWFL.sources() called', xbmc.LOGINFO)
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
			xbmc.log('[SF-DIAG] SNOWFL fetched %d items, title=%r' % (len(items), title), xbmc.LOGINFO)
		except Exception as e:
			xbmc.log('[SF-DIAG] SNOWFL.sources() exception before loop: %s' % e, xbmc.LOGINFO)
			source_utils.scraper_error('SNOWFL')
			return self.sources

		for item in items:
			try:
				raw_name = (item.get('name') or '').strip()
				magnet = item.get('magnet') or ''
				if not raw_name or not magnet or 'btih:' not in magnet.lower(): continue
				m_ih = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.I)
				if not m_ih: continue
				hash = m_ih.group(1).lower()

				name = source_utils.clean_name(raw_name)
				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				if not episode_title: # filter for eps returned in a movie query
					ep_strings = [r'[.-]s\d{2}e\d{2}([.-]?)', r'[.-]s\d{2}([.-]?)', r'[.-]season[.-]?\d{1,2}[.-]?']
					name_lower = name.lower()
					if any(re.search(pat, name_lower) for pat in ep_strings): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				try:
					seeders = int(item.get('seeder') or 0)
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					dsize, isize = source_utils._size(item.get('size') or '')
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)
				self.sources_append({'provider': 'snowfl', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
												'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('SNOWFL')
		xbmc.log('[SF-DIAG] SNOWFL.sources() returning %d results' % len(self.sources), xbmc.LOGINFO)
		return self.sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			season_xx = season.zfill(2)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
			clean_title = re.sub(r'[^A-Za-z0-9\s\.-]+', '', title)
			if search_series:
				queries = [clean_title + ' Season', clean_title + ' Complete']
			else:
				queries = [clean_title + ' S%s' % season_xx, clean_title + ' Season %s' % season]
			items = []
			for q in queries:
				items += self._query(q)
		except:
			source_utils.scraper_error('SNOWFL')
			return self.sources

		for item in items:
			try:
				raw_name = (item.get('name') or '').strip()
				magnet = item.get('magnet') or ''
				if not raw_name or not magnet or 'btih:' not in magnet.lower(): continue
				m_ih = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.I)
				if not m_ih: continue
				hash = m_ih.group(1).lower()
				name = source_utils.clean_name(raw_name)

				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name)
						if not valid: continue
					package = 'season'
				else:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name, total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				try:
					seeders = int(item.get('seeder') or 0)
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					dsize, isize = source_utils._size(item.get('size') or '')
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				pack_item = {'provider': 'snowfl', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True,
					'size': dsize, 'package': package}
				if search_series: pack_item.update({'last_season': last_season})
				elif episode_start: pack_item.update({'episode_start': episode_start, 'episode_end': episode_end})
				self.sources_append(pack_item)
			except:
				source_utils.scraper_error('SNOWFL')
		return self.sources
