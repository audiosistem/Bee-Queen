# created by Venom for Fenomscrapers
"""
	Fenomscrapers Project
"""

import re
from html import unescape
from urllib.parse import quote_plus, parse_qs, urlparse
from magneto.modules import client
from magneto.modules import source_utils


target_class = r'(?=.*items-start).*'
RE_MAGNET = re.compile(r'href\s*=\s*["\'](magnet:[^"\']+)["\']', re.I)
RE_SIZE = re.compile(r'<i class="[^"]*fa-download[^"]*"></i>\s*<span>\s*([\d.]+\s*[GKM]B)\s*</span>', re.I)
RE_SEEDERS = re.compile(r'fa-arrow-up[^"]*"></i>\s*<span[^>]*>\s*(\d+)\s*</span>\s*<span>seeders</span>', re.I)


class source:
	timeout = 7
	priority = 3
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://bitsearch.eu"
		self.search_link = '/search?limit=100&q=%s'
		self.min_seeders = 0

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		sources_append = sources.append
		try:
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

			if 'timeout' in data: self.timeout = int(data['timeout'])
			results = client.request(url, timeout=self.timeout)
			if not results: return sources
			rows = client.parseDOM(results, 'div', attrs={'class': target_class})
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('BITSEARCH')
			return sources

		for row in rows:
			try:
				magnet_match = RE_MAGNET.search(row)
				if not magnet_match: continue
				magnet_url = unescape(magnet_match.group(1))
				parsed_query = parse_qs(urlparse(magnet_url).query)
				xt_param = parsed_query.get('xt', [''])[-1]
				if not xt_param: continue
				hash = xt_param.split(':')[-1]
				parsed_name = parsed_query.get('dn', ['Unknown'])[-1]
				name = source_utils.clean_name(parsed_name)

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
					seeders = RE_SEEDERS.search(row)
					seeders = int(seeders.group(1)) if seeders else 0
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = RE_SIZE.search(row)
					size = size.group(1).strip() if size else '0 GB'
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				sources_append({'provider': 'bitsearch', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
												'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('BITSEARCH')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.search_series = search_series
			self.total_seasons = total_seasons
			self.bypass_filter = bypass_filter

			self.aliases = source_utils.aliases_to_array(data['aliases'])
			self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			self.imdb = data['imdb']
			self.year = data['year']
			self.season_x = data['season']
			self.season_xx = self.season_x.zfill(2)
			if 'timeout' in data: self.timeout = int(data['timeout'])
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', self.title)
			if search_series:
				queries = [
						self.search_link % quote_plus(query + ' Season'),
						self.search_link % quote_plus(query + ' Complete')]
			else:
				queries = [
						self.search_link % quote_plus(query + ' S%s' % self.season_xx),
						self.search_link % quote_plus(query + ' Season %s' % self.season_x)]
			threads = []
			append = threads.append
			for url in queries:
				link = '%s%s' % (self.base_link, url)
				append(source_utils.Thread(self.get_sources_packs, link))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('BITSEARCH')
			return self.sources

	def get_sources_packs(self, link):
		try:
			results = client.request(link, timeout=self.timeout)
			if not results: return
			rows = client.parseDOM(results, 'div', attrs={'class': target_class})
		except:
			source_utils.scraper_error('BITSEARCH')
			return

		for row in rows:
			try:
				magnet_match = RE_MAGNET.search(row)
				if not magnet_match: continue
				magnet_url = unescape(magnet_match.group(1))
				parsed_query = parse_qs(urlparse(magnet_url).query)
				xt_param = parsed_query.get('xt', [''])[-1]
				if not xt_param: continue
				hash = xt_param.split(':')[-1]
				parsed_name = parsed_query.get('dn', ['Unknown'])[-1]
				name = source_utils.clean_name(parsed_name)

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
					seeders = RE_SEEDERS.search(row)
					seeders = int(seeders.group(1)) if seeders else 0
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = RE_SIZE.search(row)
					size = size.group(1).strip() if size else '0 GB'
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {'provider': 'bitsearch', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info, 'quality': quality,
							'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize, 'package': package}
				if self.search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				self.sources_append(item)
			except:
				source_utils.scraper_error('BITSEARCH')

