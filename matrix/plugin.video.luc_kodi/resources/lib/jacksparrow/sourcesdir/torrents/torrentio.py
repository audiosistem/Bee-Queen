# -*- coding: utf-8 -*-
# created by luc_kodi for jacksparrowscrapers
"""
	jacksparrowscrapers Project
"""

from json import loads as jsloads
import re
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting

SERVER_ERROR = ('521 Origin Down', 'No results returned', 'Connection Time-out', 'Database maintenance')

# Torrentio instances
_INSTANCES = [
	'https://torrentio.strem.fun',
	'https://strem.space'
]

# Active providers
# 2026-05: rarbg vuelve a estar activo en torrentio (+); lo reincorporamos
# al default ya que es la fuente con mas seeders 4K BluRay del listado.
# Anime providers (horriblesubs, nyaasi, tokyotosho, anidex, nekobt) no se
# incluyen aqui por ahora — pendiente settings toggle en v1.1.0.
_PROVIDERS = 'yts,eztv,rarbg,1337x,thepiratebay,kickasstorrents,torrentgalaxy,magnetdl,rutor,rutracker,torrent9'


class source:
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.language = ['en']
		try:
			instance_idx = int(getSetting('torrentio.url') or '0')
		except Exception:
			instance_idx = 0
		self.base_link = _INSTANCES[instance_idx] if instance_idx < len(_INSTANCES) else _INSTANCES[0]
		self.movieSearch_link = '/providers=%s/stream/movie/%%s.json' % _PROVIDERS
		self.tvSearch_link    = '/providers=%s/stream/series/%%s:%%s:%%s.json' % _PROVIDERS
		try:
			self.min_seeders = int(getSetting('torrentio.min.seeders') or '0')
		except Exception:
			self.min_seeders = 0

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------
	@staticmethod
	def _extract_tracker(lines):
		"""Return tracker name from the gear-emoji line, or empty string."""
		for line in lines[1:]:
			if '\u2699' in line:  # ⚙️
				parts = line.split('\u2699')
				tracker = parts[-1].strip().lstrip('\ufe0f').strip()
				if tracker:
					return tracker
		return ''

	def _parse_stream(self, file, title, aliases, hdlr, year, episode_title):
		"""Parse a single Torrentio stream dict; returns result dict or None."""
		try:
			hash_val = file.get('infoHash', '')
			if not hash_val:
				return None
			lines = file.get('title', '').split('\n')
			if not lines:
				return None
			name = source_utils.clean_name(lines[0])
			if not source_utils.check_title(
				title, aliases, name.replace('.(Archie.Bunker', ''), hdlr, year
			):
				return None
			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				return None
			undesirables = source_utils.get_undesirables()
			if undesirables and source_utils.remove_undesirables(name_info, undesirables):
				return None
			# Seeders — scan all lines for the 👤 emoji
			seeders = 0
			for line in lines[1:]:
				if '\U0001f465' in line:
					m = re.search(r'(\d+)', line)
					if m:
						seeders = int(m.group(1))
					break
			if self.min_seeders and seeders < self.min_seeders:
				return None
			tracker = self._extract_tracker(lines)
			url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash_val, name)
			quality, info = source_utils.get_release_quality(name_info, url)
			info += [t for t in source_utils.get_extra_tags(name) if t not in info]
			dsize = 0
			for line in lines[1:]:
				m = re.search(
					r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', line
				)
				if m:
					dsize, isize = source_utils._size(m.group(0))
					info.insert(0, isize)
					break
			info_str = ' | '.join(info)
			provider = ('torrentio-%s' % tracker) if tracker else 'torrentio'
			return {
				'provider': provider,
				'source': 'torrent',
				'seeders': seeders,
				'hash': hash_val,
				'name': name,
				'name_info': name_info,
				'quality': quality,
				'language': 'en',
				'url': url,
				'info': info_str,
				'direct': False,
				'debridonly': True,
				'size': dsize,
			}
		except Exception:
			source_utils.scraper_error('TORRENTIO')
			return None

	def _fetch(self, url):
		"""Request Torrentio and return list of stream dicts, or []."""
		try:
			results = client.request(url, timeout=15)
			if not results or any(e in results for e in SERVER_ERROR):
				return []
			return jsloads(results).get('streams', [])
		except Exception:
			source_utils.scraper_error('TORRENTIO')
			return []

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------
	def sources(self, data, hostDict):
		sources = []
		if not data:
			return sources
		try:
			is_episode = 'tvshowtitle' in data
			title = data['tvshowtitle'] if is_episode else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title'] if is_episode else None
			year = data['year']
			imdb = data['imdb']
			if is_episode:
				season  = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, episode))
			else:
				hdlr = year
				url = '%s%s' % (self.base_link, self.movieSearch_link % imdb)
		except Exception:
			source_utils.scraper_error('TORRENTIO')
			return sources
		for file in self._fetch(url):
			result = self._parse_stream(file, title, aliases, hdlr, year, episode_title)
			if result:
				sources.append(result)
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data:
			return sources
		try:
			title  = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			imdb   = data['imdb']
			year   = data['year']
			season = data['season']
			url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, data['episode']))
		except Exception:
			source_utils.scraper_error('TORRENTIO')
			return sources
		undesirables = source_utils.get_undesirables()
		check_foreign_audio = source_utils.check_foreign_audio()
		for file in self._fetch(url):
			try:
				hash_val = file.get('infoHash', '')
				if not hash_val:
					continue
				lines = file.get('title', '').split('\n')
				name  = source_utils.clean_name(lines[0])
				episode_start = episode_end = 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(
							title, aliases, year, season, name.replace('.(Archie.Bunker', '')
						)
						if not valid:
							continue
					package = 'season'
				else:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(
							title, aliases, imdb, year, season,
							name.replace('.(Archie.Bunker', ''), total_seasons
						)
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
				# Seeders
				seeders = 0
				for line in lines[1:]:
					if '\U0001f465' in line:
						m = re.search(r'(\d+)', line)
						if m:
							seeders = int(m.group(1))
						break
				if self.min_seeders and seeders < self.min_seeders:
					continue
				tracker = self._extract_tracker(lines)
				url_mag = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash_val, name)
				quality, info = source_utils.get_release_quality(name_info, url_mag)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				dsize = 0
				for line in lines[1:]:
					m = re.search(
						r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', line
					)
					if m:
						dsize, isize = source_utils._size(m.group(0))
						info.insert(0, isize)
						break
				info_str = ' | '.join(info)
				provider = ('torrentio-%s' % tracker) if tracker else 'torrentio'
				item = {
					'provider': provider,
					'source': 'torrent',
					'seeders': seeders,
					'hash': hash_val,
					'name': name,
					'name_info': name_info,
					'quality': quality,
					'language': 'en',
					'url': url_mag,
					'info': info_str,
					'direct': False,
					'debridonly': True,
					'size': dsize,
					'package': package,
				}
				if search_series:
					item['last_season'] = last_season
				elif episode_start:
					item['episode_start'] = episode_start
					item['episode_end']   = episode_end
				sources.append(item)
			except Exception:
				source_utils.scraper_error('TORRENTIO')
		return sources
