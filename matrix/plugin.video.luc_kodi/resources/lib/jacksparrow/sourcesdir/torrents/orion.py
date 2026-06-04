# -*- coding: utf-8 -*-
# created by luc_kodi for jacksparrowscrapers
"""
	jacksparrowscrapers Project
	Orion (orionoid.com) torrent scraper
"""

from json import loads as jsloads
from json import dumps as jsdumps
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting

_API_URL     = 'https://orionoid.com/api'
_API_VERSION = '5.1.5'

# App key pública de cocoscrapers (open-source, licencia beerware — "do whatever you want")
# Usada como fallback si el usuario no registra su propia app key en Orion
_DEFAULT_APP_KEY = '11111111111111111111111111111111'

_SORT_VALUES = ['best', 'seeders', 'filesize', 'videoquality', 'videosize', 'popularity', 'timeadded']


class source:
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.language = ['en']
		self.user_key = getSetting('orion.api_key') or ''
		self.app_key  = _DEFAULT_APP_KEY
		try:
			self.sort = _SORT_VALUES[int(getSetting('orion.sort') or '1')]
		except Exception:
			self.sort = 'seeders'
		try:
			self.limit = int(getSetting('orion.limit') or '20')
		except Exception:
			self.limit = 20
		try:
			self.min_seeders = int(getSetting('orion.min.seeders') or '0')
		except Exception:
			self.min_seeders = 0

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _build_filters(self, imdb, is_movie, season=None, episode=None):
		filters = {
			'type': 'movie' if is_movie else 'show',
			'id':   {'imdb': imdb},
			'limit':    {'count': self.limit},
			'sort':     {'value': self.sort, 'order': 'descending'},
			'stream':   {'type': ['torrent']},
			'protocol': {'torrent': ['magnet']},
			'file':     {'unknown': False},
		}
		if not is_movie and season is not None and episode is not None:
			filters['number'] = {
				'season':  int(season),
				'episode': int(episode),
			}
		return filters

	def _fetch(self, filters):
		"""POST JSON a la API de Orion con keyapp + keyuser."""
		try:
			body = {
				'keyapp':  self.app_key,
				'keyuser': self.user_key,
				'mode':    'stream',
				'action':  'retrieve',
				'version': _API_VERSION,
				'data':    filters,
			}
			raw = client.request(
				_API_URL,
				post=jsdumps(body),
				headers={'Content-Type': 'application/json'},
				timeout=20,
			)
			if not raw:
				return []
			data = jsloads(raw)
			result = data.get('result', {})
			if result.get('status') != 'success':
				source_utils.scraper_error('ORION: %s' % result.get('type', 'unknown'))
				return []
			return data.get('data', {}).get('streams', [])
		except Exception:
			source_utils.scraper_error('ORION')
			return []

	def _magnet(self, item):
		try:
			for link in item.get('stream', {}).get('links', []):
				if link.lower().startswith('magnet:'):
					return link
		except Exception:
			pass
		return None

	def _parse(self, item, title, aliases, hdlr, year, episode_title):
		try:
			file_block   = item.get('file',   {})
			stream_block = item.get('stream', {})

			hash_val = file_block.get('hash', '')
			if not hash_val:
				return None

			name_raw = file_block.get('name') or ''
			if not name_raw:
				return None
			name = source_utils.clean_name(name_raw)

			if not source_utils.check_title(title, aliases, name, hdlr, year):
				return None
			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				return None
			undesirables = source_utils.get_undesirables()
			if undesirables and source_utils.remove_undesirables(name_info, undesirables):
				return None

			try:
				seeders = int(stream_block.get('seeds') or 0)
			except Exception:
				seeders = 0
			if self.min_seeders and seeders < self.min_seeders:
				return None

			magnet = self._magnet(item) or ('magnet:?xt=urn:btih:%s&dn=%s' % (hash_val, name))
			quality, info = source_utils.get_release_quality(name_info, magnet)
			info += [t for t in source_utils.get_extra_tags(name) if t not in info]

			dsize = 0
			try:
				raw_bytes = int(file_block.get('size') or 0)
				if raw_bytes > 0:
					dsize, isize = source_utils._size('%.2f GB' % (raw_bytes / (1024.0 ** 3)))
					info.insert(0, isize)
			except Exception:
				pass

			return {
				'provider': 'orion', 'source': 'torrent', 'language': 'en',
				'direct': False, 'debridonly': True,
				'hash': hash_val, 'url': magnet, 'name': name, 'name_info': name_info,
				'quality': quality, 'info': ' | '.join(info), 'size': dsize, 'seeders': seeders,
			}
		except Exception:
			source_utils.scraper_error('ORION')
			return None

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def sources(self, data, hostDict):
		sources = []
		if not data or not self.user_key:
			return sources
		sources_append = sources.append
		try:
			is_episode    = 'tvshowtitle' in data
			title         = data['tvshowtitle'] if is_episode else data['title']
			title         = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases       = data['aliases']
			episode_title = data['title'] if is_episode else None
			year          = data['year']
			imdb          = data['imdb']
			if is_episode:
				season  = data['season']
				episode = data['episode']
				hdlr    = 'S%02dE%02d' % (int(season), int(episode))
				filters = self._build_filters(imdb, False, season, episode)
			else:
				hdlr    = year
				filters = self._build_filters(imdb, True)
		except Exception:
			source_utils.scraper_error('ORION')
			return sources

		for item in self._fetch(filters):
			result = self._parse(item, title, aliases, hdlr, year, episode_title)
			if result:
				sources_append(result)
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data or not self.user_key:
			return sources
		sources_append = sources.append
		try:
			title   = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			imdb    = data['imdb']
			year    = data['year']
			season  = data['season']
			filters = self._build_filters(imdb, False, season, data['episode'])
		except Exception:
			source_utils.scraper_error('ORION')
			return sources

		undesirables        = source_utils.get_undesirables()
		check_foreign_audio = source_utils.check_foreign_audio()

		for item in self._fetch(filters):
			try:
				file_block   = item.get('file',   {})
				stream_block = item.get('stream', {})
				hash_val = file_block.get('hash', '')
				if not hash_val:
					continue
				name_raw = file_block.get('name') or ''
				if not name_raw:
					continue
				name = source_utils.clean_name(name_raw)

				episode_start = episode_end = 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name)
						if not valid:
							continue
					package = 'season'
				else:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name, total_seasons)
						if not valid:
							continue
					else:
						last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio):
					continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables):
					continue

				try:
					seeders = int(stream_block.get('seeds') or 0)
				except Exception:
					seeders = 0
				if self.min_seeders and seeders < self.min_seeders:
					continue

				magnet = self._magnet(item) or ('magnet:?xt=urn:btih:%s&dn=%s' % (hash_val, name))
				quality, info = source_utils.get_release_quality(name_info, magnet)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]

				dsize = 0
				try:
					raw_bytes = int(file_block.get('size') or 0)
					if raw_bytes > 0:
						dsize, isize = source_utils._size('%.2f GB' % (raw_bytes / (1024.0 ** 3)))
						info.insert(0, isize)
				except Exception:
					pass

				item_out = {
					'provider': 'orion', 'source': 'torrent', 'language': 'en',
					'direct': False, 'debridonly': True,
					'hash': hash_val, 'url': magnet, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': ' | '.join(info), 'size': dsize, 'seeders': seeders,
					'package': package,
				}
				if search_series:
					item_out['last_season'] = last_season
				elif episode_start:
					item_out['episode_start'] = episode_start
					item_out['episode_end']   = episode_end
				sources_append(item_out)
			except Exception:
				source_utils.scraper_error('ORION')
		return sources
