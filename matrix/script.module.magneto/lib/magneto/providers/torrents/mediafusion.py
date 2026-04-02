# created by kodifitzwell for Fenomscrapers
"""
	Fenomscrapers Project
"""

from json import loads as jsloads
import re, queue
from magneto.modules import client
from magneto.modules import source_utils
from magneto.modules.control import setting as getSetting


class source:
	timeout = 10
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_queue = queue.SimpleQueue()
	def __init__(self):
		self.language = ['en']
		self.base_link = (
			"https://mediafusion.stremio.ru",
			"https://mediafusionfortheweebs.midnightignite.me"
		)[int(getSetting('mediafusion.url', '0'))]
		self.movieSearch_link = '/stream/movie/%s.json'
		self.tvSearch_link = '/stream/series/%s:%s:%s.json'
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
				url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, episode))
			else:
				hdlr = year
				url = '%s%s' % (self.base_link, self.movieSearch_link % imdb)
			# log_utils.log('url = %s' % url)
			try:
				results = client.request(url, headers=self._headers(), timeout=self.timeout)
				files = jsloads(results)['streams']
			except:
				files = []
				raise
			finally:
				self._queue.put_nowait(files) # if seasons
				self._queue.put_nowait(files) # if shows
			_INFO = re.compile(r'💾.*')
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('MEDIAFUSION')
			return sources

		for file in files:
			try:
				if 'url' in file: hash = re.search(r'\b\w{40}\b', file['url']).group()
				else: hash = file['infoHash']
				file_title = file['description'].replace('┈➤', '\n').split('\n')
				file_info = [x for x in file_title if _INFO.search(x)][0]

				name = source_utils.clean_name(file['behaviorHints']['filename'])

				if not source_utils.check_title(title, aliases, name.replace('.(Archie.Bunker', ''), hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

				try:
					seeders = int(re.search(r'👤\s*(\d+)', file_info).group(1))
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = float(file['behaviorHints']['videoSize'])
					dsize, isize = source_utils.convert_size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				sources_append({
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'mediafusion', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
				})
			except:
				source_utils.scraper_error('MEDIAFUSION')
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
			url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, data['episode']))
			files = self._queue.get(timeout=self.timeout + 1)
			_INFO = re.compile(r'💾.*')
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('MEDIAFUSION')
			return sources

		for file in files:
			try:
				if 'url' in file: hash = re.search(r'\b\w{40}\b', file['url']).group()
				else: hash = file['infoHash']
				file_title = file['description'].replace('┈➤', '\n').split('\n')
				file_info = [x for x in file_title if _INFO.search(x)][0]

				name = source_utils.clean_name(file['behaviorHints']['filename'])

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
					seeders = int(re.search(r'👤\s*(\d+)', file_info).group(1))
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				try:
					size = float(file['behaviorHints']['videoSize'])
					dsize, isize = source_utils.convert_size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'mediafusion', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders, 'package': package
				}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('MEDIAFUSION')
		return sources

	def _headers(self):
		return {'encoded_user_data': (
			'ewogICJzZWxlY3RlZF9jYXRhbG9ncyI6IFtdLAogICJzZWxlY3RlZF9yZXNvbHV0aW9ucyI6IFsK'
			'ICAgICI0ayIsICAgICIyMTYwcCIsICIxMDgwcCIsICI3MjBwIiwgICI1NzZwIiwgICI0ODBwIiwg'
			'ICIzNjBwIiwgICIyNDBwIiwgIjE0NDBwIiwgbnVsbAogIF0sCiAgImVuYWJsZV9jYXRhbG9ncyI6'
			'IGZhbHNlLAogICJlbmFibGVfaW1kYl9tZXRhZGF0YSI6IGZhbHNlLAogICJtYXhfc2l6ZSI6ICJp'
			'bmYiLAogICJtaW5fc2l6ZSI6IDAsCiAgIm1heF9zdHJlYW1zX3Blcl9yZXNvbHV0aW9uIjogMjAs'
			'CiAgIm51ZGl0eV9maWx0ZXIiOiBbIkRpc2FibGUiXSwKICAiY2VydGlmaWNhdGlvbl9maWx0ZXIi'
			'OiBbIkRpc2FibGUiXSwKICAibGFuZ3VhZ2Vfc29ydGluZyI6IFsKICAgICJFbmdsaXNoIiwgICAg'
			'IlRhbWlsIiwgICAgICAiSGluZGkiLCAgICAgICJNYWxheWFsYW0iLCAgIkthbm5hZGEiLAogICAg'
			'IlRlbHVndSIsICAgICAiQ2hpbmVzZSIsICAgICJSdXNzaWFuIiwgICAgIkFyYWJpYyIsICAgICAi'
			'SmFwYW5lc2UiLAogICAgIktvcmVhbiIsICAgICAiVGFpd2FuZXNlIiwgICJMYXRpbm8iLCAgICAg'
			'IkZyZW5jaCIsICAgICAiU3BhbmlzaCIsCiAgICAiUG9ydHVndWVzZSIsICJJdGFsaWFuIiwgICAg'
			'Ikdlcm1hbiIsICAgICAiVWtyYWluaWFuIiwgICJQb2xpc2giLAogICAgIkN6ZWNoIiwgICAgICAi'
			'VGhhaSIsICAgICAgICJJbmRvbmVzaWFuIiwgIlZpZXRuYW1lc2UiLCAiRHV0Y2giLAogICAgIkJl'
			'bmdhbGkiLCAgICAiVHVya2lzaCIsICAgICJHcmVlayIsICAgICAgIlN3ZWRpc2giLCAgICAiUm9t'
			'YW5pYW4iLAogICAgIkh1bmdhcmlhbiIsICAiRmlubmlzaCIsICAgICJOb3J3ZWdpYW4iLCAgIkRh'
			'bmlzaCIsICAgICAiSGVicmV3IiwKICAgICJMaXRodWFuaWFuIiwgIlB1bmphYmkiLCAgICAiTWFy'
			'YXRoaSIsICAgICJHdWphcmF0aSIsICAgIkJob2pwdXJpIiwKICAgICJOZXBhbGkiLCAgICAgIlVy'
			'ZHUiLCAgICAgICAiVGFnYWxvZyIsICAgICJGaWxpcGlubyIsICAgIk1hbGF5IiwKICAgICJNb25n'
			'b2xpYW4iLCAgIkFybWVuaWFuIiwgICAiR2VvcmdpYW4iLCAgIG51bGwKICBdLAogICJxdWFsaXR5'
			'X2ZpbHRlciI6IFsKICAgICJCbHVSYXkvVUhEIiwgICAiV0VCL0hEIiwgICAgICAgIkRWRC9UVi9T'
			'QVQiLCAgICJDQU0vU2NyZWVuZXIiLAogICAgIlVua25vd24iCiAgXSwKICAiaGRyX2ZpbHRlciI6'
			'IFsiSERSMTAiLCAiSERSMTArIiwgIkRvbGJ5IFZpc2lvbiIsICJITEciLCAiU0RSIiwgIlVua25v'
			'd24iXSwKICAibGl2ZV9zZWFyY2hfc3RyZWFtcyI6IGZhbHNlLAogICJpbmNsdWRlX2FuaW1lIjog'
			'dHJ1ZSwKICAiZW5hYmxlX3VzZW5ldF9zdHJlYW1zIjogZmFsc2UsCiAgInByZWZlcl91c2VuZXRf'
			'b3Zlcl90b3JyZW50IjogZmFsc2UsCiAgImVuYWJsZV90ZWxlZ3JhbV9zdHJlYW1zIjogZmFsc2Us'
			'CiAgImVuYWJsZV9hY2VzdHJlYW1fc3RyZWFtcyI6IGZhbHNlLAogICJtYXhfc3RyZWFtcyI6IDEw'
			'MCwKICAic3RyZWFtX3R5cGVfZ3JvdXBpbmciOiAic2VwYXJhdGUiLAogICJzdHJlYW1fdHlwZV9v'
			'cmRlciI6IFsKICAgICJ0b3JyZW50IiwgICAidXNlbmV0IiwgICAgInRlbGVncmFtIiwgICJodHRw'
			'IiwgICAgICAiYWNlc3RyZWFtIiwgInlvdXR1YmUiCiAgXSwKICAicHJvdmlkZXJfZ3JvdXBpbmci'
			'OiAibWl4ZWQiLAogICJzdHJlYW1fbmFtZV9maWx0ZXJfbW9kZSI6ICJkaXNhYmxlZCIsCiAgInN0'
			'cmVhbV9uYW1lX2ZpbHRlcl9wYXR0ZXJucyI6IFtdLAogICJzdHJlYW1fbmFtZV9maWx0ZXJfdXNl'
			'X3JlZ2V4IjogZmFsc2UsCiAgInRvcnJlbnRfc29ydGluZ19wcmlvcml0eSI6IFsKICAgIHsia2V5'
			'IjogImNhY2hlZCIsICAgICAiZGlyZWN0aW9uIjogImRlc2MifSwKICAgIHsia2V5IjogInJlc29s'
			'dXRpb24iLCAiZGlyZWN0aW9uIjogImRlc2MifSwKICAgIHsia2V5IjogInF1YWxpdHkiLCAgICAi'
			'ZGlyZWN0aW9uIjogImRlc2MifSwKICAgIHsia2V5IjogImxhbmd1YWdlIiwgICAiZGlyZWN0aW9u'
			'IjogImRlc2MifSwKICAgIHsia2V5IjogInNpemUiLCAgICAgICAiZGlyZWN0aW9uIjogImRlc2Mi'
			'fSwKICAgIHsia2V5IjogInNlZWRlcnMiLCAgICAiZGlyZWN0aW9uIjogImRlc2MifSwKICAgIHsi'
			'a2V5IjogImNyZWF0ZWRfYXQiLCAiZGlyZWN0aW9uIjogImRlc2MifQogIF0sCiAgInN0cmVhbV90'
			'ZW1wbGF0ZSI6IHsKICAgICJ0aXRsZSI6ICJ7aWYgc3RyZWFtLnR5cGUgPSB0b3JyZW50fVvwn6ey'
			'e3NlcnZpY2Uuc2hvcnROYW1lfXtpZiBzZXJ2aWNlLmNhY2hlZH3imqF7L2lmfV17ZWxpZiBzdHJl'
			'YW0udHlwZSA9IHVzZW5ldH1b8J+TsHtzZXJ2aWNlLnNob3J0TmFtZX1de2Vsc2V9W/CflJddey9p'
			'Zn0ge2FkZG9uLm5hbWV9IHtpZiBzdHJlYW0ucmVzb2x1dGlvbn17c3RyZWFtLnJlc29sdXRpb259'
			'ey9pZn0iLAogICAgImRlc2NyaXB0aW9uIjogIntpZiBzdHJlYW0ucXVhbGl0eX17c3RyZWFtLnF1'
			'YWxpdHl9IHsvaWZ9e2lmIHN0cmVhbS5jb2RlY317c3RyZWFtLmNvZGVjfSB7L2lmfXtpZiBzdHJl'
			'YW0uaGRyX2Zvcm1hdHN9e3N0cmVhbS5oZHJfZm9ybWF0c3xqb2luKCcgJyl9IHsvaWZ9XG57aWYg'
			'c3RyZWFtLnNpemUgPiAwffCfkr4ge3N0cmVhbS5zaXplfGJ5dGVzfSB7L2lmfXtpZiBzdHJlYW0u'
			'c2VlZGVycyA+IDB98J+RpCB7c3RyZWFtLnNlZWRlcnN9ey9pZn1cbntpZiBzdHJlYW0ubGFuZ3Vh'
			'Z2VfZmxhZ3N9e3N0cmVhbS5sYW5ndWFnZV9mbGFnc3xqb2luKCcgJyl9ey9pZn1cbuKame+4jyB7'
			'c3RyZWFtLnNvdXJjZX0iCiAgfSwKICAiaW5kZXhlcl9jb25maWciOiB7CiAgICAicHJvd2xhcnIi'
			'ICAgICAgICAgOiB7ImVuYWJsZWQiOiBmYWxzZSwgInVzZV9nbG9iYWwiOiBmYWxzZX0sCiAgICAi'
			'amFja2V0dCIgICAgICAgICAgOiB7ImVuYWJsZWQiOiBmYWxzZSwgInVzZV9nbG9iYWwiOiB0cnVl'
			'fSwKICAgICJ0b3J6bmFiX2VuZHBvaW50cyI6IFtdLAogICAgIm5ld3puYWJfaW5kZXhlcnMiIDog'
			'W10KICB9LAogICJ0ZWxlZ3JhbV9jb25maWciOiBudWxsCn0='
		)}
