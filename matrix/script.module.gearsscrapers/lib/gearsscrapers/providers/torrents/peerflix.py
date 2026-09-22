
"""
	gearsscrapers Project
"""

from json import loads as jsloads
import re, queue
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# peerflix.mov -- a Stremio-protocol addon (manifest at /manifest.json),
# same stream-list JSON shape as comet.py above but with real numeric
# seed/size fields (file['seed']/file['sizebytes']) instead of only an
# emoji-encoded description line -- ported from Starfleet's own
# torrent_sources.py::search_peerflix(), confirmed live 2026-09-12 with
# real bilingual (ES/EN) results. Season-pack support here is the same
# same-call-reused-via-queue approach as comet.py: Peerflix has no
# separate pack endpoint, so sources_packs() re-filters the same
# per-episode response for season-pack-shaped names.
#
# Re-created 2026-09-13: this file and its provider.peerflix Settings
# toggle both went missing from the installed addon folder at some point
# after first being added (torrent9.py, added around the same session,
# survived) -- cause unconfirmed (not a global addon reinstall, since
# sibling files were untouched). Re-verified the real API is unchanged
# before rewriting this.


class source:
	timeout = 10
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_queue = queue.SimpleQueue()
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://peerflix.mov"
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
			try:
				results = client.request(url, timeout=self.timeout)
				files = jsloads(results)['streams']
			except:
				files = []
				raise
			finally:
				self._queue.put_nowait(files) # if seasons
				self._queue.put_nowait(files) # if shows
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('PEERFLIX')
			return sources

		for file in files:
			try:
				hash = (file.get('infoHash') or '').lower()
				if not hash: continue
				desc = file.get('description') or file.get('name') or ''
				name = source_utils.clean_name(desc.split('\n')[0].strip())
				if not name: continue

				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

				seeders = int(file.get('seed') or 0)
				if self.min_seeders > seeders: continue

				quality, info = source_utils.get_release_quality(name_info, url)
				dsize, isize = source_utils.convert_size(file.get('sizebytes') or 0)
				if isize: info.insert(0, isize)
				info = ' | '.join(info)

				sources_append({
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'peerflix', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
				})
			except:
				source_utils.scraper_error('PEERFLIX')
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
			files = self._queue.get(timeout=self.timeout + 1)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('PEERFLIX')
			return sources

		for file in files:
			try:
				hash = (file.get('infoHash') or '').lower()
				if not hash: continue
				desc = file.get('description') or file.get('name') or ''
				name = source_utils.clean_name(desc.split('\n')[0].strip())
				if not name: continue

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

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				seeders = int(file.get('seed') or 0)
				if self.min_seeders > seeders: continue

				quality, info = source_utils.get_release_quality(name_info, url)
				dsize, isize = source_utils.convert_size(file.get('sizebytes') or 0)
				if isize: info.insert(0, isize)
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'peerflix', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders, 'package': package
				}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end})
				sources_append(item)
			except:
				source_utils.scraper_error('PEERFLIX')
		return sources
