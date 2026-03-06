# created by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

import re, requests
from viperscrapers.modules import source_utils

class source:
	timeout = 7
	priority = 1
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		params = '/eyJzdG9yZXMiOlt7ImMiOiJwMnAiLCJ0IjoiIn1dfQ=='
		self.language = ['en']
		self.base_link = "https://stremthru.elfhosted.com/stremio/torz"
		self.movieSearch_link = f"{params}/stream/movie/%s.json"
		self.tvSearch_link = f"{params}/stream/series/%s:%s:%s.json"
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
			imdb = data['imdb']
			if 'tvshowtitle' in data:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, episode))
			else:
				url = '%s%s' % (self.base_link, self.movieSearch_link % imdb)
				hdlr = year
			# log_utils.log('url = %s' % url)
			results = requests.get(url, timeout=self.timeout) # client.request(url, timeout=7)
			files = results.json()['streams'] # jsloads(results)['streams']
			_INFO = re.compile(r'(?:💾|📦).*')
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('TORZ')
			return sources

		for file in files:
			try:
				package, episode_start = None, 0
				hash = file['infoHash']
				file_title = file['description'].splitlines()
				file_info = next((i for i in file_title if _INFO.search(i)), '')

				name = source_utils.clean_name(file_title[-1])

				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = re.findall(r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', file_info)
					package = 'season' if not episode_title is None and len(size) > 1 else None
					size = size[0]
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except:
					size = f"{float(file['behaviorHints']['videoSize']) / 1073741824:.2f} GB"
					package = None
					dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'torz', 'url': url, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': 0
				}
				if package: item['package'] = package
				# if package == 'show': item.update({'last_season': last_season})
				# if episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				append(item)
			except:
				source_utils.scraper_error('TORZ')
		return sources

