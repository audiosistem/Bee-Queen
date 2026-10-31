# created by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

import re
from json import loads as jsloads
from threading import Lock
from pov.modules import client, source_utils


class source(source_utils.SourceRegistry):
	timeout = 7
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_lock = Lock()
	_cache = {}
	_INFO = re.compile(r'💾.*')
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://mediafusionfortheweebs.midnightignite.me"
		self.movieSearch_link = '/%s/stream/movie/%s.json'
		self.tvSearch_link = '/%s/stream/series/%s:%s:%s.json'
		self.min_seeders = 0

	def _make_item(self, file, name, name_info, file_info, seeders):
		hash = file['infoHash']
		url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

		quality, info = source_utils.get_release_quality(name_info, url)
		try:
			size = re.search(r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', file_info).group(0)
			dsize, isize = source_utils._size(size)
			info.insert(0, isize)
		except: dsize = 0
		info = ' | '.join(info)

		return {
			'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
			'provider': 'mediafusion', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
			'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
		}

	def sources(self, data, hostDict):
		if not data: return []
		sources = []
		sources_append = sources.append
		future = self.get_future(str(data))
		try:
			aliases = source_utils.aliases_to_array(data['aliases'])
			year, years = source_utils._years(data)
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
			episode_title = data['title'] if 'tvshowtitle' in data else None
			imdb = data['imdb']
			if 'tvshowtitle' in data:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				url = '%s%s' % (self.base_link, self.tvSearch_link % (self._token(), imdb, season, episode))
			else:
				hdlr = year
				url = '%s%s' % (self.base_link, self.movieSearch_link % (self._token(), imdb))

			if 'timeout' in data: self.timeout = int(data['timeout'])
			results = client.session.request('get', url, timeout=self.timeout).text
			files = jsloads(results)['streams']
			if not future.done(): future.set_result(files)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			if not future.done(): future.set_result([])
			source_utils.scraper_error('MEDIAFUSION')
			return sources

		for file in files:
			try:
				file_title = (file.get('title') or file['description']).split('\n')
				file_info = [x for x in file_title if self._INFO.search(x)][0]

				try:
					seeders = int(re.search(r'👤\s*(\d+)', file_info).group(1))
					if self.min_seeders > seeders: continue
				except: seeders = 0

				name = source_utils.clean_name(file_title[0])

				if not source_utils.check_title(title, aliases, name, hdlr, year, years): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				item = self._make_item(file, name, name_info, file_info, seeders)
				sources_append(item)
			except:
				source_utils.scraper_error('MEDIAFUSION')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		if not data: return []
		sources = []
		sources_append = sources.append
		try:
			aliases = source_utils.aliases_to_array(data['aliases'])
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			url = '%s%s' % (self.base_link, self.tvSearch_link % (self._token(), imdb, season, data['episode']))

			if 'timeout' in data: self.timeout = int(data['timeout'])
			files = self.get_future(str(data)).result(timeout=self.timeout + 1)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('MEDIAFUSION')
			return sources

		for file in files:
			try:
				file_title = (file.get('title') or file['description']).split('\n')
				file_info = [x for x in file_title if self._INFO.search(x)][0]

				try:
					seeders = int(re.search(r'👤\s*(\d+)', file_info).group(1))
					if self.min_seeders > seeders: continue
				except: seeders = 0

				name = source_utils.clean_name(file_title[0])

				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name)
						if not valid: continue
					package = 'season'

				elif search_series:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name, total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				item = self._make_item(file, name, name_info, file_info, seeders)
				item['package'] = package
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('MEDIAFUSION')
		return sources

	def _token(self):
		return (
			'D-h5mpsX35oygOGFiHutl66dLAPiXzjQTODPXKQuKBaQOLjwNBbVkSPi7TJPr0gdykpCFREq8JOh'
			'DHZcvoS_UNZsWpsbjscCAwzgqc9VvP0S3Wt9lz5blcPT8lU6fcHdAHYctp_yde6nWKtSQ1O9Tjeh'
			'GNwajH9TjGZwn6rOybPFmoMpccXfTkB3Xwe9xRhT9O-bKzoYnGnlG8fCDxlNGdzrnlythePc3C7O'
			'phF8b5GyhuSnvBhxD7dTfkI77Dbay8_k_wqS-me9euZQ-oyOJBNTOIsO8HiWQhLGCC8m9rYsqJT6'
			'QF1Xhn-2bNzlukfbSYh_X1kOFdi6Y-YkBeEYokDlQHzzU45qmrj2b1Nz-GALcJHjNDJEMF3h9Eyx'
			'7UcmGWT1qvTpv_tcXjAX37ceqrWH-e_EqwVkvQDjNnmpjOhBWhuUW2R-0KbvxKUn1s5d2jZjLBxC'
			'bMotHIC-G2SrVCLgC_KV0OUainevUHKOKTe0CQmWz1HKV1ju52CFZFZYAWkOAX5cw55qzNnWl_nQ'
			'RnLyngrW_P6aYqghbYyyrAvQ6hCrIbSnVj4GsMFIelcMETvGW4jIXdwZGZA1L8gCzmyCbI9vAqPv'
			'dZxRWb7roc2EnB7gaSYdFtTP9gGoFKKkQ-9aircUEiPXjkP4QWO7lVI4GZri7KKCKjBM7-hWf4nm'
			'ttY7lJS_4Te_H80BeR_qpqeYQ6V0gpVwihARA6cIsZFbWmQXtoYNO16jt1ZqeVztwR6L1IQQnAsH'
			'ANyR5kF7ovGCOnhWlDDxO3nk8fhm3s0k7XewrMisZHy1zNsivTjvJW6KoVwghLn8-QCTf9PEPoPj'
			's6tW5KjciaRvbMg5-mbhpAhYOmPisB4ZyW63vWY6TeU1OBJV0T_fkHtgbvgiTEX5RFoRVDLnhaof'
			'-xHVw2oCc2AdXmBDVROmFjY8x9KEyZ91QfNjHnrTFmGetelcHE'
		)

