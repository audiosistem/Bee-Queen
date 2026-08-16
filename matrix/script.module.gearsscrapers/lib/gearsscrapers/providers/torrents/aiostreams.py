
"""
	gearsscrapers Project
"""

from json import loads as jsloads
import queue
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils


class source:
	timeout = 30
	priority = 3
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_queue = queue.SimpleQueue()
	def __init__(self):
		self.language = ['en']
		# Community-hosted instances of the same open-source project -- any
		# one can go dark or get rate-limited at any time (confirmed live:
		# aiostreamsfortheweak.cloud was already unreachable when checked),
		# so sources()/sources_packs() try each in turn instead of hardcoding
		# a single host.
		self.base_links = [
			"https://aiostreamsfortheweebs.midnightignite.me",
			"https://aiostreamsfortheweebsstable.midnightignite.me",
			"https://aiostreams.stremio.ru",
			"https://aiostreams.viren070.me",
			"https://aiostreams.12312023.xyz",
		]
		self.base_link = self.base_links[0]
		self.movieSearch_link = '/api/v1/search?type=movie&id=%s'
		self.tvSearch_link = '/api/v1/search?type=series&id=%s:%s:%s'
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
			year = data['year']
			imdb = data['imdb']
			if 'tvshowtitle' in data:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				link_tmpl = self.tvSearch_link % (imdb, season, episode)
			else:
				hdlr = year
				link_tmpl = self.movieSearch_link % imdb
			try:
				files = []
				for base in self.base_links:
					try:
						results = client.request(base + link_tmpl, headers=self._headers(), timeout=self.timeout)
						candidate = jsloads(results)['data']['results']
						if candidate:
							files = candidate
							self.base_link = base
							break
						if not files:
							files = candidate  # keep first reachable-but-empty response as fallback
					except:
						continue
			except:
				files = []
				raise
			finally:
				self._queue.put_nowait(files) # if seasons
				self._queue.put_nowait(files) # if shows
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return sources

		for file in files:
			try:
				hash = file['infoHash']
				file_title = file['folderName'] or file['filename']

				name = source_utils.clean_name(file_title)

				if not source_utils.check_title(title, aliases, name.replace('.(Archie.Bunker', ''), hdlr, year): continue
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

				sources_append({
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'aiostreams', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
				})
			except:
				source_utils.scraper_error('AIOSTREAMS')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data: return sources
		sources_append = sources.append
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			# dead code removed: building a per-episode url here always raised
			# KeyError('episode') during season-pack searches (data has no
			# 'episode' key), which silently zeroed sources_packs().
			files = self._queue.get(timeout=self.timeout + 1)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return sources

		for file in files:
			try:
				hash = file['infoHash']
				file_title = file['folderName'] or file['filename']

				name = source_utils.clean_name(file_title)

				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name.replace('.(Archie.Bunker', ''))
						if not valid: continue
					package = 'season'

				elif search_series:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name.replace('.(Archie.Bunker', ''), total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
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
					'provider': 'aiostreams', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders, 'package': package
				}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('AIOSTREAMS')
		return sources

	def _headers(self):
		# Config adds seadex + neko-bt presets (2026-08-11) on top of the
		# existing bitmagnet-only demo config -- both are anime-focused
		# sources with no direct gearsscrapers equivalent (unlike
		# comet/zilean/mediafusion/meteor/torrentsdb/knaben, which duplicate
		# scrapers already run directly elsewhere in this project, so weren't
		# added here). AIOStreams itself decides server-side whether a
		# searched title is anime and only queries these two when it is --
		# fires transparently through the existing sources()/sources_packs()
		# calls above, no new media-type path needed. Kept identical to the
		# same change made in plugin.video.starfleet's torrent_sources.py.
		return {'x-aiostreams-user-data': (
			'eyJzZXJ2aWNlcyI6IFt7ImlkIjogImFsbGRlYnJpZCIsICJlbmFibGVkIjogdHJ1ZSwgImNyZWRlbnRpYWxzIjogeyJhcGlLZXkiOiAic3RhdGljRGVtb0FwaWtleVByZW0ifX1dLCAicHJlc2V0cyI6IFt7InR5cGUiOiAiYml0bWFnbmV0IiwgImluc3RhbmNlSWQiOiAiM2IzIiwgImVuYWJsZWQiOiB0cnVlLCAib3B0aW9ucyI6IHsibmFtZSI6ICJCaXRtYWduZXQiLCAidGltZW91dCI6IDEwMDAwLCAibWVkaWFUeXBlcyI6IFtdfX0sIHsidHlwZSI6ICJzZWFkZXgiLCAiaW5zdGFuY2VJZCI6ICI0N2IiLCAiZW5hYmxlZCI6IHRydWUsICJvcHRpb25zIjogeyJuYW1lIjogIlNlYURleCIsICJ0aW1lb3V0IjogNzAwMCwgIm1lZGlhVHlwZXMiOiBbImFuaW1lIl19fSwgeyJ0eXBlIjogIm5la28tYnQiLCAiaW5zdGFuY2VJZCI6ICI1NmUiLCAiZW5hYmxlZCI6IHRydWUsICJvcHRpb25zIjogeyJuYW1lIjogIm5la29CVCIsICJ0aW1lb3V0IjogNzAwMCwgIm1lZGlhVHlwZXMiOiBbXSwgInNlYXJjaE1vZGUiOiAiYm90aCIsICJ1c2VNdWx0aXBsZUluc3RhbmNlcyI6IGZhbHNlLCAibGVhdmVBdXRvVGl0bGVUYWdzSW5GaWxlbmFtZSI6IGZhbHNlfX1dLCAiZm9ybWF0dGVyIjogeyJpZCI6ICJ0b3JyZW50aW8iLCAiZGVmaW5pdGlvbiI6IHsibmFtZSI6ICIiLCAiZGVzY3JpcHRpb24iOiAiIn19LCAic29ydENyaXRlcmlhIjogeyJnbG9iYWwiOiBbXX19'
		)}
