"""
	jacksparrowscrapers Project - AIOStreams scraper (auto stream endpoint)

	Flujo:
	  1. Al primer scrape, llama a GET /api/v1/user con HTTP Basic Auth
	     (Authorization: Basic base64(uuid:password)) que devuelve
	     encryptedPassword (contrasena cifrada con la SECRET_KEY de la
	     instancia). La cacheamos en Window(10000) para no repetir la
	     llamada en cada busqueda.
	     [v2.30 (abril 2026): el endpoint ya no acepta uuid/password como
	     query params; obliga al header Basic. Mantenemos el fallback a
	     query params para compatibilidad con instancias <v2.30.]
	  2. Con uuid + encryptedPassword construimos el stream endpoint:
	     /<uuid>/<encryptedPassword>/stream/<type>/<id>.json
	     Este endpoint resuelve el Debrid en el lado de AIOStreams y devuelve
	     URLs directas reproducibles (https://).
	  3. Si el usuario tiene Debrid configurado en AIOStreams (PM/RD/AD/TB):
	     -> direct=True, debridonly=False  (luc_kodi reproduce sin resolver)
	  4. Si AIOStreams devuelve solo infoHash (sin Debrid en su lado):
	     -> direct=False, debridonly=True  (luc_kodi usa su propio Debrid)

	Setup (usuario) - igual que antes, sin campos nuevos:
	  1. Ve a tu instancia AIOStreams /configure
	  2. Crea usuario, configura Debrid (PM/RD/AD/TB) en Services
	  3. En luc_kodi -> Ajustes -> Proveedores -> AIOStreams:
	       Instancia / UUID / Password
"""

import json
import re
import base64
import threading
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow import client

try:
	import xbmcgui
	_window = xbmcgui.Window(10000)
except Exception:
	_window = None

_INSTANCES = {
	'0': 'https://aiostreamsfortheweebsstable.midnightignite.me',
	'1': 'https://aiostreams.stremio.ru',
	'2': 'https://aiostreams.viren070.me',
	'3': 'https://aiostreamsfortheweak.cloud',
	'4': 'https://aiostreams.12312023.xyz',
}

_SERVICE_PATTERNS = [
	('premiumize', 'PM'), ('realdebrid', 'RD'), ('real-debrid', 'RD'),
	('alldebrid', 'AD'), ('all-debrid', 'AD'), ('torbox', 'TB'),
	('debridlink', 'DL'), ('offcloud', 'OC'), ('pikpak', 'PP'),
	('easynews', 'EN'),
]
_CACHED_MARKS   = ('+', 'cached', 'cache', 'instant')
_UNCACHED_MARKS = ('~', 'uncached', 'download')

_CACHE_KEY_PREFIX = 'aiostreams.enc_pwd.'


def _parse_service_and_cache(name_str):
	text = (name_str or '').lower()
	svc_label = ''
	for keyword, label in _SERVICE_PATTERNS:
		if keyword in text:
			svc_label = label
			break
	is_cached = None
	for mark in _CACHED_MARKS:
		if mark in text:
			is_cached = True
			break
	if is_cached is None:
		for mark in _UNCACHED_MARKS:
			if mark in text:
				is_cached = False
				break
	return svc_label, is_cached


def _parse_size(desc):
	if not desc:
		return 0
	try:
		m = re.findall(
			r'((?:\d+[,\.]\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))',
			desc, re.IGNORECASE)
		if m:
			dsize, _ = source_utils._size(m[0])
			return dsize
	except Exception:
		pass
	return 0


def _parse_seeders(desc):
	if not desc:
		return 0
	try:
		m = re.search(r'(?:\U0001f465|\bseeders?\b[:\s]*)(\d+)', desc, re.IGNORECASE)
		if m:
			return int(m.group(1))
	except Exception:
		pass
	return 0


# Tabla de sinonimos: mapea variantes al nombre canonical
# Previene duplicados como HDR+HDR, ATMOS+ATMOS, DV+DOLBY-VISION+DOLBY VISION
_TAG_SYNONYMS = {
	'DOLBY VISION':  'DOLBY-VISION',
	'DOLBY-VISION':  'DOLBY-VISION',
	'DV':            'DOLBY-VISION',
	'DOLBY ATMOS':   'ATMOS',
	'HDR10PLUS':     'HDR10+',
	'HDR10 PLUS':    'HDR10+',
	'WEBDL':         'WEB-DL',
	'WEB DL':        'WEB-DL',
	'BLU RAY':       'BLURAY',
	'BLU-RAY':       'BLURAY',
	'MULTI LANG':    'MULTI-LANG',
	'MULTILANG':     'MULTI-LANG',
	'MULTI':         'MULTI-LANG',
	'DD PLUS':       'DD+',
	'EAC3':          'DD+',
	'AC3':           'DD',
	'10 BIT':        '10BIT',
	'AVC':           'H264',
	'H.264':         'H264',
	'H.265':         'HEVC',
	'X265':          'HEVC',
	'X264':          'H264',
}

def _norm_tag(t):
	"""Normaliza un tag a su forma canonical para deduplicacion."""
	return _TAG_SYNONYMS.get(t, t)

def _merge_tags(base_tags, *extra_lists):
	"""
	Combina listas de tags con deduplicacion normalizada.
	base_tags se añaden primero; los extras solo si su forma
	normalizada no esta ya presente.
	"""
	seen  = set()
	result = []
	for t in base_tags:
		n = _norm_tag((t or '').upper())
		if n and n not in seen:
			result.append(n)
			seen.add(n)
	for lst in extra_lists:
		for t in lst:
			n = _norm_tag((t or '').upper())
			if n and n not in seen:
				result.append(n)
				seen.add(n)
	return result


class source:
	timeout = 30
	priority = 2
	pack_capable = False
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.language  = ['en']
		idx            = getSetting('aiostreams.url') or '0'
		self.base_link = _INSTANCES.get(idx, _INSTANCES['0'])
		self._uuid     = getSetting('aiostreams.uuid')     or ''
		self._password = getSetting('aiostreams.password') or ''
		# encryptedPassword se resuelve bajo demanda y se cachea en Window
		self._enc_pwd  = None

	# --- Encrypted password --------------------------------------------------

	def _cache_key(self):
		return '%s%s' % (_CACHE_KEY_PREFIX, self._uuid[:8] if self._uuid else 'none')

	def _get_encrypted_password(self):
		"""
		Obtiene encryptedPassword via GET /api/v1/user.

		AIOStreams v2.30+ (abril 2026) obliga HTTP Basic Auth:
		  Authorization: Basic base64(uuid:password)
		Las instancias <v2.30 aceptan tambien uuid/password como query
		params; intentamos primero Basic (forward-compatible) y, si la
		instancia devuelve 4xx/error, hacemos fallback a query params.

		Cachea el resultado en Window(10000) para no repetir la llamada.
		Devuelve string o '' si falla.
		"""
		if self._enc_pwd:
			return self._enc_pwd

		# Intenta leer de la cache Window
		cache_key = self._cache_key()
		if _window:
			try:
				cached = _window.getProperty(cache_key)
				if cached:
					self._enc_pwd = cached
					return self._enc_pwd
			except Exception:
				pass

		if not self._uuid or not self._password:
			return ''

		# Intento principal: HTTP Basic Auth (v2.30+)
		enc_pwd = self._fetch_enc_pwd_basic()
		if not enc_pwd:
			# Fallback para instancias <v2.30
			enc_pwd = self._fetch_enc_pwd_query()

		if enc_pwd and _window:
			try:
				_window.setProperty(cache_key, enc_pwd)
			except Exception:
				pass
		self._enc_pwd = enc_pwd or ''
		return self._enc_pwd

	def _fetch_enc_pwd_basic(self):
		"""GET /api/v1/user con Authorization: Basic <base64(uuid:password)>."""
		try:
			creds = ('%s:%s' % (self._uuid, self._password)).encode('utf-8')
			auth = base64.b64encode(creds).decode('ascii')
			url = '%s/api/v1/user' % self.base_link
			headers = {
				'Authorization': 'Basic %s' % auth,
				'Accept': 'application/json',
			}
			resp = client.request(url, headers=headers, timeout='15')
			if not resp:
				return ''
			data = json.loads(resp)
			if not data.get('success'):
				return ''
			return data.get('data', {}).get('encryptedPassword') or ''
		except Exception:
			return ''

	def _fetch_enc_pwd_query(self):
		"""Fallback legacy: GET /api/v1/user?uuid=...&password=... (<v2.30)."""
		try:
			url = '%s/api/v1/user?uuid=%s&password=%s' % (
				self.base_link, self._uuid, self._password)
			resp = client.request(url, timeout='15')
			if not resp:
				return ''
			data = json.loads(resp)
			if not data.get('success'):
				err = data.get('error') or {}
				source_utils.scraper_error('AIOSTREAMS user API - %s' % err.get('message', 'error'))
				return ''
			return data.get('data', {}).get('encryptedPassword') or ''
		except Exception:
			source_utils.scraper_error('AIOSTREAMS user API')
			return ''

	# --- URL helpers ---------------------------------------------------------

	def _stream_url(self, media_type, media_id, enc_pwd):
		"""
		Stream endpoint Stremio con encryptedPassword en el path:
		  /stremio/<uuid>/<encryptedPassword>/stream/<type>/<id>.json
		"""
		return '%s/stremio/%s/%s/stream/%s/%s.json' % (
			self.base_link.rstrip('/'),
			self._uuid,
			enc_pwd,
			media_type,
			media_id,
		)

	# --- Fetch ---------------------------------------------------------------

	def _fetch(self, media_type, media_id):
		"""
		Resuelve encryptedPassword y llama al stream endpoint.
		Devuelve (streams, is_stream_mode).
		"""
		if not self._uuid or not self._password:
			source_utils.scraper_error('AIOSTREAMS - UUID/Password not configured')
			return [], False

		enc_pwd = self._get_encrypted_password()
		if not enc_pwd:
			# Si no se puede obtener encryptedPassword, no hay streams
			source_utils.scraper_error('AIOSTREAMS - no se pudo obtener encryptedPassword')
			return [], False

		url = self._stream_url(media_type, media_id, enc_pwd)
		try:
			resp = client.request(url, timeout=str(self.timeout))
			if not resp:
				return [], True
			data = json.loads(resp)
			streams = data.get('streams')
			if streams is None:
				source_utils.scraper_error('AIOSTREAMS stream endpoint - respuesta invalida')
				return [], True
			return streams, True
		except Exception:
			source_utils.scraper_error('AIOSTREAMS stream endpoint')
			return [], True

	# --- Parse ---------------------------------------------------------------

	def _parse_stream(self, stream, title, aliases, hdlr, year,
			episode_title, total_seasons, season=None):
		try:
			# -- 1. URL y modo de reproduccion --------------------------------
			direct_url = stream.get('url')      or ''
			hash_val   = stream.get('infoHash') or ''

			if direct_url and direct_url.startswith('http'):
				play_url   = direct_url
				is_direct  = True
				debridonly = False
			elif hash_val:
				play_url   = 'magnet:?xt=urn:btih:%s' % hash_val
				is_direct  = False
				debridonly = True
			else:
				return None

			# -- 2. Nombre del archivo ----------------------------------------
			bh          = stream.get('behaviorHints') or {}
			bh_filename = bh.get('filename') or ''
			name_field  = stream.get('name')        or ''
			desc_field  = stream.get('description') or ''

			if bh_filename:
				raw_name = bh_filename
			else:
				raw_name = desc_field.split('\n')[0].strip() if desc_field else ''
				if not raw_name:
					lines    = name_field.split('\n')
					raw_name = lines[1].strip() if len(lines) > 1 else name_field

			raw_name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts)$', '', raw_name, flags=re.IGNORECASE)
			name     = source_utils.clean_name(raw_name)

			# -- 3. Validacion de titulo / packs ------------------------------
			package       = None
			episode_start = 0
			episode_end   = 0
			last_season   = None

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

			# -- 4. Idioma / undesirables -------------------------------------
			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				return None
			undesirables = source_utils.get_undesirables()
			if undesirables and source_utils.remove_undesirables(name_info, undesirables):
				return None

			# -- 5. Seeders ---------------------------------------------------
			seeders = _parse_seeders(desc_field)

			# -- 6. Calidad ---------------------------------------------------
			quality, _info_tags = source_utils.get_release_quality(name_info, play_url)
			# _merge_tags deduplica con normalizacion de sinonimos:
			# evita HDR+HDR, ATMOS+ATMOS, DV+DOLBY-VISION, etc.
			info = _merge_tags(
				list(_info_tags) if _info_tags else [],
				list(source_utils.get_extra_tags(name)),
			)

			# -- 7. Tamano ----------------------------------------------------
			dsize = _parse_size(desc_field)
			if dsize:
				try:
					_, isize = source_utils._size('%.2f GB' % dsize)
					info.insert(0, isize)
				except Exception:
					pass

			# -- 8. Etiqueta Debrid (solo URLs directas) ----------------------
			# 'debrid' se muestra en luc_kodi.debrid del card (slot SIZE | DEBRID | ...).
			# Servicio reconocido (PM/RD/AD/TB) -> su nombre.
			# URL directa sin servicio identificado -> 'Custom' (AIOStreams lo resolvio).
			debrid_key = ''
			if is_direct:
				svc_label, is_cached = _parse_service_and_cache(name_field)
				if svc_label:
					cache_mark = ' +' if is_cached is True else (' ~' if is_cached is False else '')
					debrid_key = '%s%s' % (svc_label, cache_mark)
				else:
					debrid_key = 'Custom'

			info_str = ' | '.join(info)

			# -- 9. Construir item --------------------------------------------
			item = {
				'source':    'torrent',
				'language':  'en',
				'direct':    is_direct,
				'debridonly': debridonly,
				'provider':  'aiostreams',
				'url':       play_url,
				'hash':      hash_val,
				'name':      name,
				'name_info': name_info,
				'quality':   quality,
				'info':      info_str,
				'size':      dsize,
				'seeders':   seeders,
			}
			if debrid_key:
				item['debrid'] = debrid_key
			if package:
				item['package'] = package
			if package == 'show' and last_season:
				item['last_season'] = last_season
			if episode_start:
				item.update({'episode_start': episode_start, 'episode_end': episode_end})
			return item

		except Exception:
			source_utils.scraper_error('AIOSTREAMS')
			return None

	# --- Public API ----------------------------------------------------------

	def sources(self, data, hostDict):
		results = []
		if not data:
			return results
		try:
			is_episode    = 'tvshowtitle' in data
			title         = data['tvshowtitle'] if is_episode else data['title']
			title         = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases       = data['aliases']
			episode_title = data['title'] if is_episode else None
			total_seasons = data.get('total_seasons') if is_episode else None
			year          = data['year']
			imdb          = data['imdb']
			season        = None
			if is_episode:
				season     = data['season']
				episode    = data['episode']
				hdlr       = 'S%02dE%02d' % (int(season), int(episode))
				media_id   = '%s:%s:%s' % (imdb, season, episode)
				media_type = 'series'
			else:
				hdlr       = year
				media_id   = imdb
				media_type = 'movie'
		except Exception:
			source_utils.scraper_error('AIOSTREAMS')
			return results

		streams, _ = self._fetch(media_type, media_id)
		for stream in streams:
			item = self._parse_stream(
				stream, title, aliases, hdlr, year,
				episode_title, total_seasons, season)
			if item:
				results.append(item)
		return results

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		import queue as _queue
		results = []
		if not data:
			return results
		try:
			title         = data['tvshowtitle'].replace('&', 'and').replace('/', ' ')
			aliases       = data['aliases']
			episode_title = data['title']
			year          = data['year']
			imdb          = data['imdb']
			season        = data['season']
			hdlr          = 'S%02d' % int(season)
			media_id      = '%s:%s:%s' % (imdb, season, data['episode'])
		except Exception:
			source_utils.scraper_error('AIOSTREAMS')
			return results

		q = _queue.SimpleQueue()

		def _worker():
			streams, _ = self._fetch('series', media_id)
			for stream in streams:
				item = self._parse_stream(
					stream, title, aliases, hdlr, year,
					episode_title, total_seasons, season)
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
			except Exception:
				break
		return results
