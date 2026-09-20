# modified by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

from json import loads as jsloads
import re
from urllib.parse import quote_plus
from magneto.modules import client
from magneto.modules import source_utils


class source:
	timeout = 7
	priority = 3
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://bitsearch.eu"
		self.search_link = '/api/v1/search?limit=100&q=%s'
		self.min_seeders = 0

	def get_sources(self, url):
		try:
			rjson = client.request(url, timeout=self.timeout)
			if not rjson: return
			files = jsloads(rjson)['results']
			self.results.extend(files)
		except:
			source_utils.scraper_error('BITSEARCH')

	def sources(self, data, hostDict):
		if not data: return []
		self.results = []
		sources = []
		sources_append = sources.append
		try:
			if 'timeout' in data: self.timeout = int(data['timeout'])
			aliases = source_utils.aliases_to_array(data['aliases'])
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			episode_title = data['title'] if 'tvshowtitle' in data else None
			year = data['year']
			hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else year

			query = '%s %s' % (title, hdlr)
			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', query)
			url = self.search_link % quote_plus(query)
			url = '%s%s' % (self.base_link, url)
			# log_utils.log('url = %s' % url)
			self.get_sources(url)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('BITSEARCH')
			return sources

		for file in self.results:
			try:
				hash = file['infohash']
				name = source_utils.clean_name(file['title'])

				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

				if not episode_title: #filter for eps returned in movie query (rare but movie and show exists for Run in 2020)
					ep_strings = [r'[.-]s\d{2}e\d{2}([.-]?)', r'[.-]s\d{2}([.-]?)', r'[.-]season[.-]?\d{1,2}[.-]?']
					name_lower = name.lower()
					if any(re.search(item, name_lower) for item in ep_strings): continue

				try:
					seeders = int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = int(file['size'])
					dsize, isize = source_utils.convert_size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				sources_append({'provider': 'bitsearch', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
									'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('BITSEARCH')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		if not data: return []
		self.results = []
		sources = []
		sources_append = sources.append
		try:
			if 'timeout' in data: self.timeout = int(data['timeout'])
			aliases = source_utils.aliases_to_array(data['aliases'])
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			imdb = data['imdb']
			year = data['year']
			season_x = data['season']
			season_xx = season_x.zfill(2)

			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', title)
			if search_series: urls = [
				self.base_link + self.search_link % quote_plus(query + ' Season'),
				self.base_link + self.search_link % quote_plus(query + ' Complete')]
			else: urls = [
				self.base_link + self.search_link % quote_plus(query + ' S%s' % season_xx),
				self.base_link + self.search_link % quote_plus(query + ' Season %s' % season_x)]
			thread = source_utils.Thread(self.get_sources, urls[0])
			thread.start()
			self.get_sources(urls[1])
			thread.join()
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('BITSEARCH')
			return sources

		for file in self.results:
			try:
				hash = file['infohash']
				name = source_utils.clean_name(file['title'])

				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season_x, name)
						if not valid: continue
					package = 'season'

				elif search_series:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season_x, name, total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season_x, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				try:
					seeders = int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = int(file['size'])
					dsize, isize = source_utils.convert_size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {'provider': 'bitsearch', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
							'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize,
							'package': package}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('BITSEARCH')
		return sources

