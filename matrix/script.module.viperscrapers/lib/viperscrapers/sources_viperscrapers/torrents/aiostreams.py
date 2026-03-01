# created by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

#from json import loads as jsloads
import requests
from viperscrapers.modules import source_utils

class source:
	timeout = 7
	priority = 2
	pack_capable = False # packs parsed in sources function
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://aiostreamsfortheweebs.midnightignite.me"
		self.movieSearch_link = f"/api/v1/search"
		self.tvSearch_link = f"/api/v1/search"
		self.min_seeders = 0

	def _headers(self):
		return {'x-aiostreams-user-data': (
			'ewogICJwcmVzZXRzIjogWwogICAgewogICAgICAidHlwZSI6ICJ0b3JyZW50aW8iLAogICAgICAiaW5z'
			'dGFuY2VJZCI6ICJlN2IiLAogICAgICAiZW5hYmxlZCI6IGZhbHNlLAogICAgICAib3B0aW9ucyI6IHsK'
			'ICAgICAgICAibmFtZSI6ICJUb3JyZW50aW8iLAogICAgICAgICJ0aW1lb3V0IjogNjUwMCwKICAgICAg'
			'ICAicmVzb3VyY2VzIjogWwogICAgICAgICAgInN0cmVhbSIsCiAgICAgICAgICAiY2F0YWxvZyIsCiAg'
			'ICAgICAgICAibWV0YSIKICAgICAgICBdLAogICAgICAgICJwcm92aWRlcnMiOiBbXSwKICAgICAgICAi'
			'dXNlTXVsdGlwbGVJbnN0YW5jZXMiOiBmYWxzZQogICAgICB9CiAgICB9LAogICAgewogICAgICAidHlw'
			'ZSI6ICJjb21ldCIsCiAgICAgICJpbnN0YW5jZUlkIjogImY3YiIsCiAgICAgICJlbmFibGVkIjogdHJ1'
			'ZSwKICAgICAgIm9wdGlvbnMiOiB7CiAgICAgICAgIm5hbWUiOiAiQ29tZXQiLAogICAgICAgICJ0aW1l'
			'b3V0IjogNjUwMCwKICAgICAgICAicmVzb3VyY2VzIjogWwogICAgICAgICAgInN0cmVhbSIKICAgICAg'
			'ICBdLAogICAgICAgICJpbmNsdWRlUDJQIjogdHJ1ZSwKICAgICAgICAicmVtb3ZlVHJhc2giOiBmYWxz'
			'ZQogICAgICB9CiAgICB9LAogICAgewogICAgICAidHlwZSI6ICJtZWRpYWZ1c2lvbiIsCiAgICAgICJp'
			'bnN0YW5jZUlkIjogIjQ1MCIsCiAgICAgICJlbmFibGVkIjogdHJ1ZSwKICAgICAgIm9wdGlvbnMiOiB7'
			'CiAgICAgICAgIm5hbWUiOiAiTWVkaWFGdXNpb24iLAogICAgICAgICJ0aW1lb3V0IjogNjUwMCwKICAg'
			'ICAgICAicmVzb3VyY2VzIjogWwogICAgICAgICAgInN0cmVhbSIsCiAgICAgICAgICAiY2F0YWxvZyIs'
			'CiAgICAgICAgICAibWV0YSIKICAgICAgICBdLAogICAgICAgICJ1c2VDYWNoZWRSZXN1bHRzT25seSI6'
			'IHRydWUsCiAgICAgICAgImVuYWJsZVdhdGNobGlzdENhdGFsb2dzIjogZmFsc2UsCiAgICAgICAgImRv'
			'd25sb2FkVmlhQnJvd3NlciI6IGZhbHNlLAogICAgICAgICJjb250cmlidXRvclN0cmVhbXMiOiBmYWxz'
			'ZSwKICAgICAgICAiY2VydGlmaWNhdGlvbkxldmVsc0ZpbHRlciI6IFtdLAogICAgICAgICJudWRpdHlG'
			'aWx0ZXIiOiBbXQogICAgICB9CiAgICB9LAogICAgewogICAgICAidHlwZSI6ICJzdHJlbXRocnVUb3J6'
			'IiwKICAgICAgImluc3RhbmNlSWQiOiAiYWVkIiwKICAgICAgImVuYWJsZWQiOiB0cnVlLAogICAgICAi'
			'b3B0aW9ucyI6IHsKICAgICAgICAibmFtZSI6ICJTdHJlbVRocnUgVG9yeiIsCiAgICAgICAgInRpbWVv'
			'dXQiOiA2NTAwLAogICAgICAgICJyZXNvdXJjZXMiOiBbCiAgICAgICAgICAic3RyZWFtIgogICAgICAg'
			'IF0sCiAgICAgICAgImluY2x1ZGVQMlAiOiBmYWxzZSwKICAgICAgICAidXNlTXVsdGlwbGVJbnN0YW5j'
			'ZXMiOiBmYWxzZQogICAgICB9CiAgICB9LAogICAgewogICAgICAidHlwZSI6ICJ0b3JyZW50cy1kYiIs'
			'CiAgICAgICJpbnN0YW5jZUlkIjogImRkMiIsCiAgICAgICJlbmFibGVkIjogdHJ1ZSwKICAgICAgIm9w'
			'dGlvbnMiOiB7CiAgICAgICAgIm5hbWUiOiAiVG9ycmVudHNEQiIsCiAgICAgICAgInRpbWVvdXQiOiA2'
			'NTAwLAogICAgICAgICJyZXNvdXJjZXMiOiBbCiAgICAgICAgICAic3RyZWFtIiwKICAgICAgICAgICJj'
			'YXRhbG9nIiwKICAgICAgICAgICJtZXRhIgogICAgICAgIF0sCiAgICAgICAgInByb3ZpZGVycyI6IFsK'
			'ICAgICAgICAgICJ5dHMiLAogICAgICAgICAgIjEzMzd4IiwKICAgICAgICAgICJ0b3JyZW50Y3N2IiwK'
			'ICAgICAgICAgICIxbG91IiwKICAgICAgICAgICJueWFhIiwKICAgICAgICAgICJza3RvcnJlbnQiLAog'
			'ICAgICAgICAgIjF0YW1pbGJsYXN0ZXJzIiwKICAgICAgICAgICJsaW1ldG9ycmVudCIsCiAgICAgICAg'
			'ICAiMXRhbWlsbXYiLAogICAgICAgICAgInJhcmdiIiwKICAgICAgICAgICJrbmFiZW4iLAogICAgICAg'
			'ICAgInRoZXBpcmF0ZWJheSIsCiAgICAgICAgICAia2lja2Fzc3RvcnJlbnRzIiwKICAgICAgICAgICJh'
			'bmltZXRvc2hvIiwKICAgICAgICAgICJleHRyZW1seW10b3JyZW50cyIsCiAgICAgICAgICAieWdndG9y'
			'cmVudCIsCiAgICAgICAgICAidG9reW90b3NobyIsCiAgICAgICAgICAicnV0b3IiLAogICAgICAgICAg'
			'InJ1dHJhY2tlciIsCiAgICAgICAgICAidG9ycmVudDkiLAogICAgICAgICAgImlsY29yc2Fyb25lcm8i'
			'LAogICAgICAgICAgIm1hbnVhbCIKICAgICAgICBdLAogICAgICAgICJpbmNsdWRlUDJQIjogZmFsc2Us'
			'CiAgICAgICAgInVzZU11bHRpcGxlSW5zdGFuY2VzIjogZmFsc2UKICAgICAgfQogICAgfQogIF0sCiAg'
			'ImZvcm1hdHRlciI6IHsKICAgICJpZCI6ICJ0b3JyZW50aW8iLAogICAgImRlZmluaXRpb24iOiB7CiAg'
			'ICAgICJuYW1lIjogIiIsCiAgICAgICJkZXNjcmlwdGlvbiI6ICIiCiAgICB9CiAgfSwKICAic29ydENy'
			'aXRlcmlhIjogewogICAgImdsb2JhbCI6IFtdCiAgfQp9'
		)}

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
			results = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout) # client.request(url, timeout=7)
			files = results.json()['data']['results'] # jsloads(results)['streams']
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
					size = f"{float(file['size']) / 1073741824:.2f} GB"
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'aiostreams', 'url': url, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
				}
				if package: item['package'] = package
				if package == 'show': item.update({'last_season': last_season})
				if episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('AIOSTREAMS')
		return sources
