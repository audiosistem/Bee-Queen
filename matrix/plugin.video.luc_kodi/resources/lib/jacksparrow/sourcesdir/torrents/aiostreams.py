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

	v1.0.91 — instancia propia (GitHub issue #3, ElfHosted de pago):
	  La opcion 'Custom URL' del desplegable admite cualquier instancia.
	  Una instancia privada de ElfHosted vive en su propio host
	  (https://<usuario>-aiostreams.elfhosted.com), no en la comunitaria, asi
	  que con la lista fija no habia forma de llegar a ella. El campo acepta:
	    - la URL base de la instancia  -> se usan UUID + Password como siempre
	    - la URL del manifest que da /configure al guardar
	      (/stremio/<uuid>/<encryptedPassword>[/v/<variante>]/manifest.json,
	      o el alias /stremio/u/<alias>/manifest.json) -> ya lleva la config,
	      UUID y Password no hacen falta y no se llama a /api/v1/user
	    - la de /configure y el enlace stremio://, que se normalizan igual
"""

import json
import re
import time
import base64
import hashlib
import threading
from resources.lib.jacksparrow import pack_handoff
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import log_utils

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
	'5': 'https://aiostreams.elfhosted.com',  # instancia comunitaria oficial (ElfHosted); rate-limited y con Torrentio desactivado
}
# Indice del desplegable 'Instance' que activa el campo aiostreams.custom_url.
# Va AL FINAL de la lista: los enum de Kodi guardan el indice, asi que
# insertarlo en medio cambiaria la instancia de quien ya tiene una elegida.
_CUSTOM_IDX = '6'


def enc_cache_key(base_link, uuid):
	"""Clave de Window(10000) donde se cachea el encryptedPassword. Publica
	para que el asistente pueda sustituirla al guardar una cuenta nueva: sin
	eso, quien cambia el password con el mismo UUID seguia usando durante la
	sesion el encryptedPassword viejo."""
	host = hashlib.md5((base_link or '').encode('utf-8')).hexdigest()[:8]
	return '%s%s.%s' % (_CACHE_KEY_PREFIX, host, uuid[:8] if uuid else 'none')


def _parse_instance_url(raw):
	"""
	Normaliza lo que el usuario pegue en aiostreams.custom_url.

	Devuelve (base, prefix, query):
	  base   -> https://host[/subruta], lo que va delante de /stremio
	  prefix -> base + '/stremio/<uuid>/<encPwd>[/v/<sel>]' o
	            base + '/stremio/u/<alias>' cuando la URL YA trae la config;
	            None si es solo la direccion de la instancia
	  query  -> query string original sin '?', que lleva el selector de
	            variante ('v=') y hay que conservar en la peticion de streams
	"""
	u = (raw or '').strip().strip('\'"')
	if not u:
		return '', None, ''
	if u.lower().startswith('stremio://'):
		u = 'https://' + u[len('stremio://'):]
	if not re.match(r'(?i)^https?://', u):
		u = 'https://' + u
	u = u.split('#', 1)[0]
	u, _, query = u.partition('?')
	u = u.rstrip('/')
	u = re.sub(r'(?i)/(?:manifest\.json|configure)$', '', u).rstrip('/')
	m = re.match(r'(?i)^(https?://[^/]+)(.*)$', u)
	if not m:
		return '', None, ''
	host, path = m.group(1), m.group(2)
	idx = path.lower().find('/stremio')
	if idx == -1:
		return (host + path).rstrip('/'), None, query
	base = host + path[:idx]
	rest = path[idx + len('/stremio'):].strip('/')
	if len(rest.split('/')) >= 2:
		return base, '%s/stremio/%s' % (base, rest), query
	return base, None, query

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


def _valid_imdb(imdb):
	return str(imdb or '').startswith('tt')


def _drop(why, reason, name=None):
	"""v1.0.94 — cuenta por que se descarta cada stream (y guarda hasta 3
	nombres de ejemplo de los descartes por titulo e idioma)."""
	if why is None: return
	why[reason] = why.get(reason, 0) + 1
	if name and reason in ('title', 'language'):
		names = why.setdefault('_names_' + reason, [])
		if len(names) < 3: names.append(name[:90])


def _why_text(why):
	parts = ['%s %d' % (k, v) for k, v in sorted(why.items(), key=lambda kv: -kv[1] if not kv[0].startswith('_') else 0)
	         if not k.startswith('_')]
	return (': ' + ', '.join(parts)) if parts else ''


class source:
	timeout = 30
	priority = 2
	# sources_packs() esta implementado mas abajo. sources.py filtra los
	# scrapers de season/show por este flag, asi que con False el metodo
	# nunca llegaba a ejecutarse y se perdian todos los packs.
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.language  = ['en']
		idx            = getSetting('aiostreams.url') or '0'
		self._uuid     = getSetting('aiostreams.uuid')     or ''
		self._password = getSetting('aiostreams.password') or ''
		# v1.0.91: instancia propia (ElfHosted de pago, autoalojada...)
		self._custom  = (idx == _CUSTOM_IDX)
		self._prefix  = None
		self._query   = ''
		if self._custom:
			self.base_link, self._prefix, self._query = _parse_instance_url(
				getSetting('aiostreams.custom_url'))
		else:
			self.base_link = _INSTANCES.get(idx, _INSTANCES['0'])
		# Min seeders (v1.0.61: aiostreams era el unico del grupo Custom
		# que ni siquiera tenia el atributo, asi que no filtraba nunca)
		try:
			self.min_seeders = int(getSetting('aiostreams.min.seeders') or '0')
		except Exception:
			self.min_seeders = 0
		# encryptedPassword se resuelve bajo demanda y se cachea en Window
		self._enc_pwd  = None

	# --- Encrypted password --------------------------------------------------

	def _cache_key(self):
		# v1.0.91: el encryptedPassword lo cifra la SECRET_KEY de CADA instancia,
		# asi que la clave de cache incluye el host. Sin eso, cambiar de la
		# comunitaria a una propia reutilizaba durante la sesion un
		# encryptedPassword que la instancia nueva no sabe descifrar.
		return enc_cache_key(self.base_link, self._uuid)

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
		if self._custom and not self.base_link:
			source_utils.scraper_error('AIOSTREAMS - Custom URL not configured')
			return [], False

		if self._prefix:
			# La URL pegada ya trae uuid + encryptedPassword (o un alias):
			# se piden los streams directamente, sin pasar por /api/v1/user.
			url = '%s/stream/%s/%s.json' % (self._prefix, media_type, media_id)
		else:
			if not self._uuid or not self._password:
				source_utils.scraper_error('AIOSTREAMS - UUID/Password not configured')
				return [], False

			enc_pwd = self._get_encrypted_password()
			if not enc_pwd:
				# Si no se puede obtener encryptedPassword, no hay streams
				# v1.0.92: una instancia propia con login delante de su API (ElfHosted
				# de pago, issue #3) nunca entrega el encryptedPassword; el manifest
				# si funciona, y es lo que hay que decirle al usuario.
				source_utils.scraper_error('AIOSTREAMS - no se pudo obtener encryptedPassword%s' % (
					' (custom instance: paste its manifest URL instead of UUID/password)' if self._custom else ''))
				return [], False

			url = self._stream_url(media_type, media_id, enc_pwd)
		if self._query:
			url = '%s?%s' % (url, self._query)
		try:
			# v1.0.66: aiostreams era el unico proveedor sin NINGUNA linea de log,
			# asi que en un kodi.log no habia forma de saber si habia corrido.
			log_utils.log('AIOSTREAMS: GET %s' % client.scrub_url(url), level=log_utils.LOGINFO)
			resp = client.request(url, timeout=str(self.timeout))
			if not resp:
				log_utils.log('AIOSTREAMS: respuesta vacia', level=log_utils.LOGINFO)
				return [], True
			data = json.loads(resp)
			streams = data.get('streams')
			if streams is None:
				source_utils.scraper_error('AIOSTREAMS stream endpoint - respuesta invalida')
				return [], True
			log_utils.log('AIOSTREAMS: parsed %d streams' % len(streams), level=log_utils.LOGINFO)
			return streams, True
		except Exception:
			source_utils.scraper_error('AIOSTREAMS stream endpoint')
			return [], True

	# --- Parse ---------------------------------------------------------------

	def _parse_stream(self, stream, title, aliases, hdlr, year,
			episode_title, total_seasons, season=None,
			pack_mode=False, search_series=False, why=None):
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
				_drop(why, 'no link')
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
					_drop(why, 'title', name)
					return None
				valid, last_season = source_utils.filter_show_pack(
					title, aliases, None, year, season, name, total_seasons)
				if not valid:
					valid, episode_start, episode_end = source_utils.filter_season_pack(
						title, aliases, year, season, name)
					if not valid:
						_drop(why, 'title', name)
						return None
					package = 'season'
				else:
					package = 'show'

			# -- 4. Idioma / undesirables -------------------------------------
			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				_drop(why, 'language', name)
				return None
			undesirables = source_utils.get_undesirables()
			if undesirables and source_utils.remove_undesirables(name_info, undesirables):
				_drop(why, 'undesirables', name)
				return None

			# -- 5. Seeders ---------------------------------------------------
			seeders = _parse_seeders(desc_field)
			if self.min_seeders and seeders < self.min_seeders:
				_drop(why, 'seeders')
				return None

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
			#
			# v1.0.62: se unifica a 'Custom', igual que el resto del grupo.
			# Antes se emitia el nombre del servicio mas una marca de cache
			# (' +' / ' ~'), que no coincidia ni con lo que ponen los otros
			# cinco Custom ni con el nombre canonico de los scrapers normales.
			# La informacion de cache sigue disponible en _parse_service_and_cache()
			# por si se decide llevarla a los info tags en vez de a este slot.
			debrid_key = 'Custom' if is_direct else ''

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
			# v1.0.70 — BUG DE ORIGEN, anterior a la 1.0.61. `package` solo se
			# rellenaba cuando check_title() FALLABA, y sources_packs() descarta
			# todo lo que no lo lleve (`if item and item.get('package')`).
			# Resultado: un pack bien nombrado ("Show.S03.1080p") PASA
			# check_title contra hdlr='S03', se queda sin `package`, y se tira.
			# O sea que la pasada de packs descartaba justo los packs correctos.
			#
			# Sootio, que va bien, lo hace al reves (sootio.py:744): en pack_mode
			# marca `package` SIEMPRE, y usa search_series para elegir la
			# etiqueta. Aqui se replica ese comportamiento.
			if pack_mode and not package:
				package = 'show' if search_series else 'season'
			if package:
				item['package'] = package
			if package == 'show' and not last_season and total_seasons:
				last_season = total_seasons
			if package == 'show' and last_season:
				item['last_season'] = last_season
			if episode_start:
				item.update({'episode_start': episode_start, 'episode_end': episode_end})
			return item

		except Exception:
			source_utils.scraper_error('AIOSTREAMS')
			_drop(why, 'error')
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
			if not _valid_imdb(imdb):
				# v1.0.94: sin id preguntaba por 'None:1:1' (kodi.log 25-sep).
				log_utils.log('AIOSTREAMS: no IMDb id for "%s", skipped' % title, level=log_utils.LOGINFO)
				return results
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

		# v1.0.71 — MEDIDO en jacksparrowscrapers.log del 23-ago, misma busqueda:
		#   02:14:24  SOOTIO:     GET .../tt9813792:1:1.json      <- UNA
		#   02:14:24  AIOSTREAMS: GET .../tt9813792:1:1.json      <- TRES
		#   02:14:24  AIOSTREAMS: GET .../tt9813792:1:1.json         IDENTICAS,
		#   02:14:24  AIOSTREAMS: GET .../tt9813792:1:1.json         mismo segundo
		#   02:14:26  SOOTIO terminado ..........................  2 s
		#   02:14:39  AIOSTREAMS terminado ......................  15 s
		#
		# Las tres pasadas (episodio, pack de temporada, pack de serie) se
		# descargaban el catalogo entero cada una. AIOStreams era el UNICO de los
		# seis Custom sin pack_handoff: se descarga una vez y se comparte.
		_h = pack_handoff.begin('aiostreams', imdb, season, data.get('episode')) if is_episode else None
		streams, _ = self._fetch(media_type, media_id)
		if _h is not None:
			pack_handoff.publish(_h, streams)
		built = 0
		why = {}
		for stream in streams:
			item = self._parse_stream(
				stream, title, aliases, hdlr, year,
				episode_title, total_seasons, season, why=why)
			if item:
				results.append(item)
				built += 1
		# Instrumentacion al nivel de SOOTIO. Sin esto el log solo decia cuantos
		# streams venian de la API, nunca cuantos sobrevivian al filtrado, y por
		# eso no se podia ver si los packs entraban o no.
		log_utils.log('AIOSTREAMS: sources() built %d items from %d streams (dropped %d%s)'
		              % (built, len(streams), len(streams) - built, _why_text(why)), level=log_utils.LOGINFO)
		# v1.0.94: con que se buscaba y que nombres se tiraron, para ver en el
		# log si falla el titulo (nombre en espanol, titulo en ingles) o el idioma.
		for reason in ('title', 'language'):
			names = why.get('_names_' + reason)
			if names:
				log_utils.log('AIOSTREAMS: dropped by %s, looking for "%s" %s (%d aliases); e.g. %s'
				              % (reason, title, hdlr, len(aliases or []), ' | '.join(names)), level=log_utils.LOGINFO)
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
			if not _valid_imdb(imdb):
				return results
			# En una busqueda de serie completa un pack no se llama "S03", asi
			# que filtrar por esa etiqueta lo descartaria. Sootio hace lo mismo.
			hdlr          = '' if search_series else 'S%02d' % int(season)
			media_id      = '%s:%s:%s' % (imdb, season, data['episode'])
		except Exception:
			source_utils.scraper_error('AIOSTREAMS')
			return results

		shared = None
		try:
			shared = pack_handoff.wait('aiostreams', imdb, season, data.get('episode'),
			                           timeout=self.timeout)
		except Exception:
			shared = None
		if shared is not None:
			built = 0
			for stream in shared:
				item = self._parse_stream(
					stream, title, aliases, hdlr, year,
					episode_title, total_seasons, season,
					pack_mode=True, search_series=search_series)
				if item and item.get('package'):
					results.append(item)
					built += 1
			log_utils.log('AIOSTREAMS: sources_packs(%s) built %d packs from %d shared streams'
			              % ('show' if search_series else 'season', built, len(shared)),
			              level=log_utils.LOGINFO)
			return results

		q = _queue.SimpleQueue()

		def _worker():
			streams, _ = self._fetch('series', media_id)
			for stream in streams:
				item = self._parse_stream(
					stream, title, aliases, hdlr, year,
					episode_title, total_seasons, season,
					pack_mode=True, search_series=search_series)
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
		log_utils.log('AIOSTREAMS: sources_packs(%s) built %d packs (sin handoff, fetch propio)'
		              % ('show' if search_series else 'season', len(results)),
		              level=log_utils.LOGINFO)
		return results

	# --- Resolve --------------------------------------------------------------

	def _mask(self, url):
		"""Enmascara UUID y encryptedPassword antes de loguear."""
		try:
			out = client.scrub_url(url)
			if self._uuid:
				out = out.replace(self._uuid, '<UUID>')
			return out
		except Exception:
			return '<URL>'

	def resolve(self, url):
		"""
		v1.0.63: hasta la 1.0.62 AIOSTREAMS era el UNICO de los seis Custom sin
		resolve(). sources.py lo formalizaba con is_aiostreams_direct y entregaba
		al reproductor la URL CRUDA de stream['url'].

		Medido en kodi.log del 21-ago-2026: esa URL cruda era
		https://stremthrufortheweebs.midnightignite.me/stremio/torz/<CONFIG>/_/strem/...
		— el proxy de una instancia comunitaria de StremThru, no el CDN del
		debrid. Fue directa a CurlFile::Open sin ninguna linea de resolve() por
		delante, o sea que la pelicula ENTERA viajaba por ese servidor
		compartido. Ese es el lag de reproduccion.

		Los otros cinco siguen el 302 hasta el CDN. Esto hace lo mismo, y de paso
		mete a AIOStreams bajo is_error_slate() + reintento, de los que estaba
		descubierto por no tener resolve().

		IMPORTANTE — si no se puede resolver se devuelve la URL CRUDA, no None.
		Los otros scrapers devuelven None ahi porque su URL lazy no es
		reproducible. La de AIOStreams SI lo es (lenta, pero funciona), asi que
		matar la fuente seria una regresion peor que el lag que arreglamos.
		"""
		try:
			if not url:
				return None
			lazy_markers = ('/playback/', '/resolve/', '/strem/', '/link/', '/download/', '/v0/store/')
			if not any(mk in url for mk in lazy_markers):
				return url

			final = client.request(url, output='geturl', redirect=True, timeout=str(self.timeout))
			if client.is_error_slate(final):
				if client.slate_retry_allowed():
					log_utils.log('AIOSTREAMS: video de error, reintentando una vez',
					              level=log_utils.LOGINFO)
					time.sleep(client.SLATE_RETRY_DELAY)
					final = client.request(url, output='geturl', redirect=True, timeout=str(self.timeout))
				if client.is_error_slate(final):
					client.note_error_slate()
					log_utils.log('AIOSTREAMS: el proveedor sigue devolviendo un video de error, se descarta la fuente',
					              level=log_utils.LOGINFO)
					return None

			if (final and final != url
					and not any(mk in final for mk in lazy_markers)):
				log_utils.log('AIOSTREAMS: resolve() -> %s' % self._mask(final[:90]),
				              level=log_utils.LOGINFO)
				return final

			# No se pudo seguir el redirect: la cruda es reproducible, se devuelve.
			log_utils.log('AIOSTREAMS: resolve() sin redirect, se reproduce la URL del proveedor (posible proxy): %s'
			              % self._mask(url[:90]), level=log_utils.LOGINFO)
			return url
		except Exception:
			source_utils.scraper_error('AIOSTREAMS resolve')
			return url
