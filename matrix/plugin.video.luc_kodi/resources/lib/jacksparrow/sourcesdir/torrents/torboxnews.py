
"""
	jacksparrowscrapers Project - torboxnews (TorBox Usenet/NZB)

	v1.0.32: endpoint cambiado al método que usa POV y que SÍ funciona hoy.
	El endpoint anterior (search-api.torbox.app/usenet) no devolvía resultados.
	Ahora se consulta el proxy AIOStreams de midnightignite con el preset
	'torbox-search' (sources:["usenet"]), igual que POV. La auth va en el
	header x-aiostreams-user-data (JSON base64 con la apiKey de TorBox),
	NO en un Bearer. Respuesta en data.results con campos:
	  filename, nzbUrl, infoHash, cached, indexer, seeders, size.
"""

import hashlib, requests
from base64 import b64encode
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting

# Plantilla del payload x-aiostreams-user-data (preset torbox-search, solo usenet).
# %d=timeout(ms)  %s=onlyShowUserSearchResults('true'/'false')  %s=apiKey
_AIO_USER_DATA = (
	'{"sortCriteria":{"global":[]},"deduplicator":{"enabled":false},"formatte'
	'r":{"id":"torrentio"},"presets":[{"type":"torbox-search","instanceId":"v'
	'0p","enabled":true,"options":{"timeout":%d,"name":"TorBoxSearch","source'
	's":["usenet"],"mediaTypes":[],"useMultipleInstances":false,"userSearchEn'
	'gines":true,"onlyShowUserSearchResults":%s}}],"services":[{"id":"torbox"'
	',"enabled":true,"credentials":{"apiKey":"%s"}}]}'
)
_AIO_URL = 'https://aiostreamsfortheweebsstable.midnightignite.me'


class source:
	timeout = 10
	priority = 3
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.user_agent = 'luc_kodi for Kodi'
		self.token = getSetting('torbox.token')
		self.user_engines_only = getSetting('tb.user_engines_only') == 'true'
		self.language = ['en']
		self.min_seeders = -2

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		sources_append = sources.append
		from resources.lib.jacksparrow import log_utils
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
				params = {'type': 'series', 'id': '%s:%s:%s' % (imdb, season, episode)}
			else:
				hdlr = year
				params = {'type': 'movie', 'id': imdb}
			if 'timeout' in data: self.timeout = int(data['timeout'])
			if not self.token:
				log_utils.log('TORBOXNEWS: no torbox.token set; usenet search skipped', level=log_utils.LOGWARNING)
				return sources

			# ── Búsqueda vía proxy AIOStreams (método POV) ─────────────────────
			user_engines = 'true' if self.user_engines_only else 'false'
			b_str = _AIO_USER_DATA % (self.timeout * 950, user_engines, self.token)
			headers = {
				'User-Agent': self.user_agent,
				'x-aiostreams-user-data': b64encode(b_str.encode()).decode(),
			}
			url = '%s/api/v1/search' % _AIO_URL
			results = requests.get(url, params=params, headers=headers, timeout=self.timeout)

			if results.status_code != 200:
				log_utils.log('TORBOXNEWS: HTTP %s for %s -- %s'
							  % (results.status_code, url, (results.text or '')[:200]),
							  level=log_utils.LOGWARNING)
				return sources
			try:
				payload = results.json()
			except Exception:
				log_utils.log('TORBOXNEWS: non-JSON response -- %s' % (results.text or '')[:200],
							  level=log_utils.LOGWARNING)
				return sources
			# Respuesta POV: payload['data']['results']
			_data = payload.get('data') if isinstance(payload, dict) else None
			if isinstance(_data, dict):
				files = _data.get('results') or _data.get('nzbs') or _data.get('usenet') or []
			elif isinstance(_data, list):
				files = _data
			else:
				files = []
			if not files:
				log_utils.log('TORBOXNEWS: 0 results for %s (success=%s detail=%s)'
							  % (url, payload.get('success') if isinstance(payload, dict) else '?',
								 (payload.get('detail') if isinstance(payload, dict) else '')),
							  level=log_utils.LOGDEBUG)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('TORBOXNEWS')
			return sources

		for file in files:
			try:
				# user_search: en el esquema AIOStreams puede no venir; si filtramos
				# por user_engines_only ya lo hace el servidor (userSearchEngines).
				if self.user_engines_only and file.get('user_search') is False: continue
				package, episode_start = None, 0
				# Campos POV: nzbUrl/filename/infoHash/cached/indexer/seeders/size
				_nzb = file.get('nzbUrl') or file.get('nzb') or file.get('url') or file.get('link') or ''
				if not _nzb: continue
				file_title = file.get('filename') or file.get('raw_title') or file.get('title') or file.get('name') or ''
				if not file_title: continue
				hash = file.get('infoHash') or file.get('hash') or hashlib.md5(_nzb.encode('utf-8')).hexdigest()

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

				url = _nzb

				try:
					seeders = int(file.get('seeders') or file.get('last_known_seeders') or 0)
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					size = f"{float(file.get('size') or 0) / 1073741824:.2f} GB"
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'usenet', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'torboxnews', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders,
					'tracker': file.get('indexer') or file.get('tracker') or 'usenet',
					# Trust the per-item `cached` field (same pattern as POV).
					'cached_remote': bool(file.get('cached')),
				}
				if package: item['package'] = package
				if package == 'show': item.update({'last_season': last_season})
				if episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('TORBOXNEWS')
		return sources

