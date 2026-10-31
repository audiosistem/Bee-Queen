# modified by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

import re
from json import loads as jsloads
from urllib.parse import quote_plus
from pov.modules import client, source_utils


class source:
	priority = 2
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://api.knaben.org"
		self.search_link = '/v2/search?dead&o=date&c=%s&q=%s'
		self.min_seeders = 0

	def _make_item(self, file, name, name_info, seeders):
		hash = file['hash']
		url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

		quality, info = source_utils.get_release_quality(name_info, url)
		try:
			size = file['bytes']
			dsize, isize = source_utils.convert_size(size)
			info.insert(0, isize)
		except: dsize = 0
		info = ' | '.join(info)

		return {
			'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
			'provider': 'knaben', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
			'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
		}

	def get_sources(self, url, collector):
		try:
			results = client.session.request('get', url, timeout=7).text
			if not results: return
			files = jsloads(results)['hits']
			collector.extend(files)
		except:
			source_utils.scraper_error('KNABEN')

	def sources(self, data, hostDict):
		if not data: return []
		files = []
		sources = []
		sources_append = sources.append
		try:
			aliases = source_utils.aliases_to_array(data['aliases'])
			year, years = source_utils._years(data)
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('/', ' ').replace('$', 's')
			episode_title = data['title'] if 'tvshowtitle' in data else None
			hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else year
			category = '2000000' if 'tvshowtitle' in data else '3000000'

			query = '%s %s' % (title, hdlr)
			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', query)
			url = self.search_link % (category, quote_plus(query))
			url = '%s%s' % (self.base_link, url)
			self.get_sources(url, files)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('KNABEN')
			return sources

		for file in files:
			try:
				try:
					seeders = int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				name = source_utils.clean_name(file['title'])

				if not source_utils.check_title(title, aliases, name, hdlr, year, years): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				if not episode_title: #filter for eps returned in movie query (rare but movie and show exists for Run in 2020)
					ep_strings = [r'[.-]s\d{2}e\d{2}([.-]?)', r'[.-]s\d{2}([.-]?)', r'[.-]season[.-]?\d{1,2}[.-]?']
					name_lower = name.lower()
					if any(re.search(item, name_lower) for item in ep_strings): continue

				item = self._make_item(file, name, name_info, seeders)
				sources_append(item)
			except:
				source_utils.scraper_error('KNABEN')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		if not data: return []
		files = []
		sources = []
		sources_append = sources.append
		try:
			aliases = source_utils.aliases_to_array(data['aliases'])
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('/', ' ').replace('$', 's')
			imdb = data['imdb']
			year = data['year']
			season_x = data['season']
			season_xx = season_x.zfill(2)
			category = '2000000'

			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', title)
			if search_series: urls = [
				self.base_link + self.search_link % (category, quote_plus(query + ' Season')),
				self.base_link + self.search_link % (category, quote_plus(query + ' Complete'))]
			else: urls = [
				self.base_link + self.search_link % (category, quote_plus(query + ' S%s' % season_xx)),
				self.base_link + self.search_link % (category, quote_plus(query + ' Season %s' % season_x))]
			thread = source_utils.Thread(self.get_sources, urls[0], files)
			thread.start()
			self.get_sources(urls[1], files)
			thread.join()
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('KNABEN')
			return sources

		for file in files:
			try:
				try:
					seeders = int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

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

				item = self._make_item(file, name, name_info, seeders)
				item['package'] = package
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('KNABEN')
		return sources

