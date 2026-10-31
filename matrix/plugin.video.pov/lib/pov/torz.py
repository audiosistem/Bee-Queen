# created by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

from threading import Lock
from json import loads as jsloads
from pov.modules import client, source_utils
from pov.modules.control import setting as getSetting


class source(source_utils.SourceRegistry):
	timeout = 7
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_lock = Lock()
	_cache = {}
	def __init__(self):
		self.language = ['en']
		self.base_link = (
			"https://stremthru.13377001.xyz",
			"https://stremthru.stremio.ru",
			"https://stremthrufortheweebs.midnightignite.me"
		)[int(getSetting('torz.url', '0'))]
		self.movieSearch_link = '/v0/torrents?sid=%s'
		self.tvSearch_link = '/v0/torrents?sid=%s:%s:%s'
		self.min_seeders = 0

	def _make_item(self, file, name, name_info, seeders):
		hash = file['hash']
		url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

		quality, info = source_utils.get_release_quality(name_info, url)
		try:
			size = float(file['size'])
			dsize, isize = source_utils.convert_size(size)
			info.insert(0, isize)
		except: dsize = 0
		info = ' | '.join(info)

		return {
			'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
			'provider': 'torz', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
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
				url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, episode))
			else:
				hdlr = year
				url = '%s%s' % (self.base_link, self.movieSearch_link % imdb)

			if 'timeout' in data: self.timeout = int(data['timeout'])
			results = client.session.request('get', url, timeout=self.timeout).text
			files = jsloads(results)['data']['items']
			if not future.done(): future.set_result(files)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			if not future.done(): future.set_result([])
			source_utils.scraper_error('TORZ')
			return sources

		for file in files:
			try:
				try:
					seeders = int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				name = source_utils.clean_name(file['name'])

				if not source_utils.check_title(title, aliases, name, hdlr, year, years): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				item = self._make_item(file, name, name_info, seeders)
				sources_append(item)
			except:
				source_utils.scraper_error('TORZ')
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
			url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, data['episode']))

			if 'timeout' in data: self.timeout = int(data['timeout'])
			files = self.get_future(str(data)).result(timeout=self.timeout + 1)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('TORZ')
			return sources

		for file in files:
			try:
				try:
					seeders = int(file['seeders'])
					if self.min_seeders > seeders: continue
				except: seeders = 0

				name = source_utils.clean_name(file['name'])

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

				item = self._make_item(file, name, name_info, seeders)
				item['package'] = package
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('TORZ')
		return sources

