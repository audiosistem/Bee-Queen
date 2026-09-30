# -*- coding: utf-8 -*-

from json import loads as jsloads
from html import unescape as _html_unescape
import re
from urllib.parse import quote
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils

SERVER_ERROR = ('521 Origin Down', 'No results returned', 'Connection Time-out', 'Database maintenance')


class source:
	priority = 2
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://apibay.org"
		self.search_link = '/q.php?q=%s&cat=0'
		self.min_seeders = 0

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		append = sources.append
		try:
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title'] if 'tvshowtitle' in data else None
			year = data['year']
			if 'tvshowtitle' in data: variants = source_utils.episode_variants(data) # TheTVDB SxxEyy when it differs from TMDb; absolute number for anime
			else: variants = [(year, year, None)]

			tagged = []
			for suffix, hdlr, absolute in variants:
				query = '%s %s' % (title, suffix)
				query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', query)
				url = self.search_link % quote(query)
				url = '%s%s' % (self.base_link, url)
				# log_utils.log('url = %s' % url)
				rjson = client.request(url, timeout=5)
				if not rjson or any(value in rjson for value in SERVER_ERROR):
					if absolute or hdlr != variants[0][1]: continue # an extra anime query failing must not drop the main results
					return sources
				tagged.extend((file, hdlr, absolute) for file in jsloads(rjson))
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('PIRATEBAY')
			return sources

		seen = set()
		for file, hdlr, absolute in tagged:
			try:
				hash = file['info_hash']
				if hash.lower() in seen: continue
				# apibay.org devuelve `&quot;` HTML-encoded en lugar de `\"`
				# JSON-escape dentro de algunos `name` (issue qBittorrent #22074).
				# El JSON sigue valido pero el name queda con entidades literales;
				# html.unescape() resuelve todas las entidades comunes.
				name = source_utils.clean_name(_html_unescape(file['name']))

				if not source_utils.check_episode(title, aliases, name, hdlr, year, absolute): continue
				seen.add(hash.lower())
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name) 

				if not episode_title: #filter for eps returned in movie query (rare but movie and show exists for Run in 2020)
					ep_strings = [r'[.-]s\d{2}e\d{2}([.-]?)', r'[.-]s\d{2}([.-]?)', r'[.-]season[.-]?\d{1,2}[.-]?']
					name_lower = name.lower()
					if any(re.search(item, name_lower) for item in ep_strings): continue

				try:
					seeders= int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					dsize, isize = source_utils.convert_size(float(file["size"]), to='GB')
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				append({'provider': 'piratebay', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
							'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('PIRATEBAY')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self._results = []
		if not data: return self._results
		self._results_append = self._results.append
		try:
			self.search_series = search_series
			self.total_seasons = total_seasons
			self.bypass_filter = bypass_filter

			self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			self.aliases = data['aliases']
			self.imdb = data['imdb']
			self.year = data['year']
			self.season_x = data['season']
			self.season_xx = self.season_x.zfill(2)
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', self.title)
			if search_series:
				queries = [
						self.search_link % quote(query + ' Season'),
						self.search_link % quote(query + ' Complete')]
			else:
				queries = [
						self.search_link % quote(query + ' S%s' % self.season_xx),
						self.search_link % quote(query + ' Season %s' % self.season_x)]
			threads = []
			append = threads.append
			for url in queries:
				link = '%s%s' % (self.base_link, url)
				append(source_utils.Thread(self.get_sources_packs, link))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self._results
		except:
			source_utils.scraper_error('PIRATEBAY')
			return self._results

	def get_sources_packs(self, link):
		try:
			rjson = client.request(link, timeout=5)
			if not rjson or any(value in rjson for value in SERVER_ERROR): return
			files = jsloads(rjson)
		except:
			source_utils.scraper_error('PIRATEBAY')
			return

		for file in files:
			try:
				hash = file['info_hash']
				# Mismo fix de &quot; que en sources() — apibay devuelve entidades HTML.
				name = source_utils.clean_name(_html_unescape(file['name']))

				episode_start, episode_end = 0, 0
				if not self.search_series:
					if not self.bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(self.title, self.aliases, self.year, self.season_x, name)
						if not valid: continue
					package = 'season'

				elif self.search_series:
					if not self.bypass_filter:
						valid, last_season = source_utils.filter_show_pack(self.title, self.aliases, self.imdb, self.year, self.season_x, name, self.total_seasons)
						if not valid: continue
					else: last_season = self.total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, self.title, self.year, season=self.season_x, pack=package)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				try:
					seeders= int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					dsize, isize = source_utils.convert_size(float(file["size"]), to='GB')
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {'provider': 'piratebay', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info, 'quality': quality,
							'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize, 'package': package}
				if self.search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				self._results_append(item)
			except:
				source_utils.scraper_error('PIRATEBAY')

