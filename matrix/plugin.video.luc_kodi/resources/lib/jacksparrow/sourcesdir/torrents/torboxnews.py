
"""
	jacksparrowscrapers Project
"""

import hashlib, requests
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting


class source:
	timeout = 9
	priority = 3
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.user_agent = 'luc_kodi for Kodi'
		self.token = getSetting('torbox.token')
		self.user_engines_only = getSetting('tb.user_engines_only') == 'true'
		self.language = ['en']
		self.base_link = "https://search-api.torbox.app/usenet"
		self.min_seeders = -2

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		sources_append = sources.append
		try:
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title'] if 'tvshowtitle' in data else None
			total_seasons = data['total_seasons'] if 'tvshowtitle' in data else None
			year = data['year']
			imdb = data['imdb']
			url = '%s/imdb:%s' % (self.base_link, imdb)
			params = {'check_cache': 'true', 'check_owned': 'true', 'search_user_engines': 'true'}
			if 'tvshowtitle' in data:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				params.update({'season': int(season), 'episode': int(episode)})
			else:
				hdlr = year
			# log_utils.log('url = %s' % url)
			if 'timeout' in data: self.timeout = int(data['timeout'])
			headers = {'User-Agent': self.user_agent, 'Authorization': 'Bearer %s' % self.token}
			results = requests.get(url, params=params, headers=headers, timeout=self.timeout)
			files = results.json()['data']['nzbs']
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('TORBOXNEWS')
			return sources

		for file in files:
			try:
				if self.user_engines_only and not file['user_search']: continue
				package, episode_start = None, 0
				hash = file['hash'] or hashlib.md5(file['nzb'].encode('utf-8')).hexdigest()
				file_title = file['raw_title']

				name = source_utils.clean_name(file_title)

				if not source_utils.check_title(title, aliases, name, hdlr, year):
					if total_seasons is None: continue
					valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name, total_seasons)
					if not valid:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name)
						if not valid: continue
						else: package = 'season'
					else: package = 'show'
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = file['nzb']

				try:
					seeders = file['last_known_seeders']
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = f"{float(file['size']) / 1073741824:.2f} GB"
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'usenet', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'torboxnews', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders, 'tracker': file['tracker']
				}
				if package: item['package'] = package
				if package == 'show': item.update({'last_season': last_season})
				if episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('TORBOXNEWS')
		return sources

