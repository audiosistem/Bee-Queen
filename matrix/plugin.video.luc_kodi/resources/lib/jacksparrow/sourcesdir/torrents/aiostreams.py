"""
	jacksparrowscrapers Project — AIOStreams scraper (v2 API)

	AIOStreams v2: Basic Auth  →  Authorization: Basic base64(uuid:password)
	Endpoint: GET /api/v1/search?type=movie&id=tt1234567
	Docs: https://github.com/Viren070/AIOStreams/wiki/API-Documentation

	Setup (user):
	  1. Go to your AIOStreams instance /configure
	  2. Create a user → note your UUID + password
	  3. Configure your debrid service + addons there
	  4. In luc_kodi Settings → Providers → Custom → AIOStreams:
	       Instance / UUID / Password
"""

import json
import threading
from base64 import b64encode
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.modules import client

_INSTANCES = {
	'0': 'https://aiostreamsfortheweebs.midnightignite.me',
	'1': 'https://aiostreams.stremio.ru',
	'2': 'https://aiostreams.viren070.me'
}


class source:
	timeout = 20
	priority = 2
	pack_capable = False
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.language = ['en']
		idx = getSetting('aiostreams.url') or '0'
		self.base_link = _INSTANCES.get(idx, _INSTANCES['0'])
		self._uuid = getSetting('aiostreams.uuid') or ''
		self._password = getSetting('aiostreams.password') or ''

	def _auth_header(self):
		if not self._uuid or not self._password:
			return {}
		token = b64encode(('%s:%s' % (self._uuid, self._password)).encode()).decode()
		return {'Authorization': 'Basic %s' % token}

	def _fetch(self, media_type, media_id):
		if not self._uuid or not self._password:
			source_utils.scraper_error('AIOSTREAMS - UUID/Password not configured')
			return []
		url = '%s/api/v1/search?type=%s&id=%s' % (self.base_link, media_type, media_id)
		try:
			resp = client.request(url, headers=self._auth_header(), timeout=str(self.timeout))
			if not resp:
				return []
			data = json.loads(resp)
			if not data.get('success'):
				err = data.get('error') or {}
				source_utils.scraper_error('AIOSTREAMS - %s' % err.get('message', 'unknown error'))
				return []
			return data.get('data', {}).get('results') or []
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return []

	def _parse_result(self, file, title, aliases, hdlr, year, episode_title, total_seasons, season=None):
		try:
			hash_val = file.get('infoHash') or ''
			if not hash_val:
				return None

			raw_name = file.get('folderName') or file.get('filename') or ''
			raw_name = raw_name.replace('┈➤', '\n').split('\n')[0].strip()
			name = source_utils.clean_name(raw_name)

			package = None
			episode_start = 0
			episode_end = 0
			last_season = None

			if not source_utils.check_title(title, aliases, name, hdlr, year):
				if total_seasons is None:
					return None
				valid, last_season = source_utils.filter_show_pack(
					title, aliases, None, year, season, name, total_seasons)
				if not valid:
					valid, episode_start, episode_end = source_utils.filter_season_pack(
						title, aliases, year, season, name)
					if not valid:
						return None
					package = 'season'
				else:
					package = 'show'

			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				return None
			undesirables = source_utils.get_undesirables()
			if undesirables and source_utils.remove_undesirables(name_info, undesirables):
				return None

			url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash_val, name)

			try:
				seeders = int(file.get('seeders') or 0)
			except:
				seeders = 0

			quality, info = source_utils.get_release_quality(name_info, url)

			try:
				size_bytes = float(file.get('size') or 0)
				size_str = '%.2f GB' % (size_bytes / 1073741824)
				dsize, isize = source_utils._size(size_str)
				info.insert(0, isize)
			except:
				dsize = 0

			info = ' | '.join(info)

			item = {
				'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
				'provider': 'aiostreams', 'url': url, 'hash': hash_val,
				'name': name, 'name_info': name_info,
				'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders,
			}
			if package:
				item['package'] = package
			if package == 'show' and last_season:
				item['last_season'] = last_season
			if episode_start:
				item.update({'episode_start': episode_start, 'episode_end': episode_end})
			return item
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return None

	# ─── Public API ──────────────────────────────────────────────────────────

	def sources(self, data, hostDict):
		results = []
		if not data:
			return results

		try:
			is_episode = 'tvshowtitle' in data
			title = data['tvshowtitle'] if is_episode else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title'] if is_episode else None
			total_seasons = data.get('total_seasons') if is_episode else None
			year = data['year']
			imdb = data['imdb']
			season = episode = None

			if is_episode:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				media_id = '%s:%s:%s' % (imdb, season, episode)
				media_type = 'series'
			else:
				hdlr = year
				media_id = imdb
				media_type = 'movie'
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return results

		files = self._fetch(media_type, media_id)
		for file in files:
			item = self._parse_result(
				file, title, aliases, hdlr, year, episode_title, total_seasons, season)
			if item:
				results.append(item)

		return results

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		import queue as _queue
		results = []
		if not data:
			return results

		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title']
			year = data['year']
			imdb = data['imdb']
			season = data['season']
			hdlr = 'S%02d' % int(season)
			media_id = '%s:%s:%s' % (imdb, season, data['episode'])
		except:
			source_utils.scraper_error('AIOSTREAMS')
			return results

		q = _queue.SimpleQueue()

		def _worker():
			files = self._fetch('series', media_id)
			for file in files:
				item = self._parse_result(
					file, title, aliases, hdlr, year, episode_title, total_seasons, season)
				if item and item.get('package'):
					q.put(item)
			q.put(None)

		t = threading.Thread(target=_worker, daemon=True)
		t.start()
		t.join(timeout=self.timeout + 5)

		while True:
			try:
				item = q.get_nowait()
				if item is None:
					break
				results.append(item)
			except:
				break

		return results
