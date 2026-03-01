# created by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

import requests
from fenom import source_utils
from fenom.control import setting as getSetting


class source:
	timeout = 7
	priority = 1
	pack_capable = False # packs parsed in sources function
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = (
			"https://aiostreams.stremio.ru",
			"https://aiostreamsfortheweebsstable.midnightignite.me"
		)[int(getSetting('aiostreams.url', '0'))]
		self.movieSearch_link = '/api/v1/search'
		self.tvSearch_link = '/api/v1/search'
		self.min_seeders = 0

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
			if 'tvshowtitle' in data:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				url = '%s%s' % (self.base_link, self.tvSearch_link)
				params = {'type': 'series', 'id': '%s:%s:%s' % (imdb, season, episode)}
			else:
				hdlr = year
				url = '%s%s' % (self.base_link, self.movieSearch_link)
				params = {'type': 'movie', 'id': '%s' % imdb}
			# log_utils.log('url = %s' % url)
			if 'timeout' in data: self.timeout = int(data['timeout'])
			results = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout)
			files = results.json()['data']['results']
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return sources

		for file in files:
			try:
				package, episode_start = None, 0
				hash = file['infoHash']
				file_title = (file['folderName'] or file['filename']).replace('┈➤', '\n').split('\n')

				name = source_utils.clean_name(file_title[0])

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

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

				try:
					seeders = file['seeders']
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = float(file['size'])
					dsize, isize = source_utils.convert_size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'aiostreams', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
				}
				if package: item['package'] = package
				if package == 'show': item.update({'last_season': last_season})
				if episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('AIOSTREAMS')
		return sources

	def _headers(self):
		return {'x-aiostreams-user-data': (
			'ewogICJwcmVzZXRzIjogWwogICAgewogICAgICAidHlwZSI6ICJjb21ldCIsCiAgICAgICJpbnN0YW5j'
			'ZUlkIjogImY3YiIsCiAgICAgICJlbmFibGVkIjogdHJ1ZSwKICAgICAgIm9wdGlvbnMiOiB7CiAgICAg'
			'ICAgIm5hbWUiOiAiQ29tZXQiLAogICAgICAgICJ0aW1lb3V0IjogNjUwMCwKICAgICAgICAicmVzb3Vy'
			'Y2VzIjogWyJzdHJlYW0iXSwKICAgICAgICAiaW5jbHVkZVAyUCI6IHRydWUsCiAgICAgICAgInJlbW92'
			'ZVRyYXNoIjogZmFsc2UKICAgICAgfQogICAgfSwKICAgIHsKICAgICAgInR5cGUiOiAibWVkaWFmdXNp'
			'b24iLAogICAgICAiaW5zdGFuY2VJZCI6ICI0NTAiLAogICAgICAiZW5hYmxlZCI6IHRydWUsCiAgICAg'
			'ICJvcHRpb25zIjogewogICAgICAgICJuYW1lIjogIk1lZGlhRnVzaW9uIiwKICAgICAgICAidGltZW91'
			'dCI6IDY1MDAsCiAgICAgICAgInJlc291cmNlcyI6IFsic3RyZWFtIl0sCiAgICAgICAgInVzZUNhY2hl'
			'ZFJlc3VsdHNPbmx5IjogdHJ1ZSwKICAgICAgICAiZW5hYmxlV2F0Y2hsaXN0Q2F0YWxvZ3MiOiBmYWxz'
			'ZSwKICAgICAgICAiZG93bmxvYWRWaWFCcm93c2VyIjogZmFsc2UsCiAgICAgICAgImNvbnRyaWJ1dG9y'
			'U3RyZWFtcyI6IGZhbHNlLAogICAgICAgICJjZXJ0aWZpY2F0aW9uTGV2ZWxzRmlsdGVyIjogW10sCiAg'
			'ICAgICAgIm51ZGl0eUZpbHRlciI6IFtdCiAgICAgIH0KICAgIH0KICBdLAogICJmb3JtYXR0ZXIiOiB7'
			'CiAgICAiaWQiOiAidG9ycmVudGlvIiwKICAgICJkZWZpbml0aW9uIjogeyJuYW1lIjogIiIsICJkZXNj'
			'cmlwdGlvbiI6ICIifQogIH0sCiAgInNvcnRDcml0ZXJpYSI6IHsiZ2xvYmFsIjogW119LAogICJkZWR1'
			'cGxpY2F0b3IiOiB7CiAgICAiZW5hYmxlZCI6IGZhbHNlLAogICAgImtleXMiOiBbImZpbGVuYW1lIiwg'
			'ImluZm9IYXNoIl0sCiAgICAibXVsdGlHcm91cEJlaGF2aW91ciI6ICJhZ2dyZXNzaXZlIiwKICAgICJj'
			'YWNoZWQiOiAic2luZ2xlX3Jlc3VsdCIsCiAgICAidW5jYWNoZWQiOiAicGVyX3NlcnZpY2UiLAogICAg'
			'InAycCI6ICJzaW5nbGVfcmVzdWx0IiwKICAgICJleGNsdWRlQWRkb25zIjogW10KICB9Cn0='
		)}

