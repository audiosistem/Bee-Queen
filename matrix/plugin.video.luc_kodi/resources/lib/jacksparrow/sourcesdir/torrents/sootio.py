# -*- coding: utf-8 -*-
"""
	jacksparrowscrapers Project - Sootio scraper

	Sootio (https://github.com/sooti/sootio-stremio-addon) es un Stremio
	addon multi-fuente, fork original de stremio-addon-debrid-search
	(MrMonkey42). Empezo siendo solo un buscador de torrents cached en
	Debrid, pero a partir de la v1.8.x se amplio a:

	  - 14 scrapers torrent (Jackett, Zilean, Torrentio, Comet, StremThru,
	    Bitmagnet, Snowfl, 1337x, BTDigg, MagnetDL, TorrentGalaxy,
	    Torrent9, Wolfmax4K, BluDV). Cada hit se verifica contra los
	    Debrid del usuario.
	  - 7 servicios Debrid (RealDebrid, AllDebrid, TorBox, Premiumize,
	    OffCloud, Debrid-Link, Debrider.app).
	  - Usenet (Newznab indexers + SABnzbd con progressive streaming).
	  - HTTP streaming providers (4KHDHub, UHDMovies, con resolucion
	    PixelDrain / Google Drive).
	  - Personal Cloud — integracion con Plex/Jellyfin caseros via
	    fuzzy matching por IMDB ID.
	  - AI Semantic Matching opcional (Ollama / OpenAI) para filtrar
	    junk y parsear titulos ambiguos en el servidor.

	Todas estas fuentes se devuelven en el contrato Stremio estandar
	{streams: [{url, infoHash, name, description, behaviorHints,...}]}.
	Para el scraper de luc_kodi son indistinguibles a nivel de parsing.

	Endpoint Stremio:
	  /{base64_config}/stream/movie/{imdb}.json
	  /{base64_config}/stream/series/{imdb}:{season}:{episode}.json

	El parametro {base64_config} contiene un JSON URL-safe-base64 encoded
	con DebridServices[{provider,apiKey},...], Scrapers[...], Languages,
	minSize, maxSize, ShowCatalog, etc.

	El usuario genera ese token en https://sooti.info/configure y lo pega
	integro en el setting 'sootio.config'. Para aprovechar las fuentes
	nuevas (Usenet, HTTP streamers, Personal Cloud) debe regenerarlo si
	su token actual es anterior a v1.8.

	Respuesta por stream (igual forma que MediaFusion/AIOStreams):
	  - url pre-resuelta http(s) (Debrid resolve / SABnzbd / HTTP
	    streamer / Personal Cloud) -> direct=True, debridonly=False
	    (luc_kodi la reproduce sin volver a resolver).
	  - solo infoHash -> magnet, direct=False, debridonly=True
	    (luc_kodi resuelve con su propio Debrid configurado).

	IMDB filter: Sootio hace match servidor usando el IMDB ID; ademas,
	a partir de v1.8.x aplica AI Semantic Matching opcional para
	desambiguar. Por tanto no aplicamos check_title al recibir streams.
"""

from json import loads as jsloads
import re
import queue
import os
try:
	from urllib.parse import quote as _url_quote
except ImportError:  # Python 2 fallback, by si acaso
	from urllib import quote as _url_quote
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow import log_utils
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow.control import setSetting


def _normalize_sootio_token(raw):
	"""
	Sootio admite tres formatos de config en la URL path:

	  1. Base64 URL-safe     -> 'eyJEZWJyaWRT...d0='
	  2. JSON crudo          -> '{"DebridServices":[...],"Scrapers":[...]}'
	  3. JSON URL-encoded    -> '%7B%22DebridServices%22%3A%5B...%5D%7D'

	Esta funcion devuelve siempre la forma lista para inyectar en el path:
	  - Si ya es (1) o (3), se deja tal cual.
	  - Si es (2), se hace URL-encode preservando cualquier caracter seguro.

	Tambien acepta que el usuario pegue la URL completa
	('stremio://sooti.info/...TOKEN.../manifest.json') y se queda solo
	con el segmento central.
	"""
	if not raw:
		return ''
	token = raw.strip().strip('"').strip("'")

	# Si el usuario pego la URL entera, extraer el path intermedio.
	# Formatos: stremio://host/TOKEN/manifest.json
	#           https://host/TOKEN/manifest.json
	for prefix in ('stremio://', 'https://', 'http://'):
		if token.startswith(prefix):
			rest = token[len(prefix):]
			# Quitar el host (todo hasta la primera barra)
			slash = rest.find('/')
			if slash == -1:
				return ''
			token = rest[slash + 1:]
			break

	# Quitar sufijo /manifest.json si lo copio entero
	lower = token.lower()
	for suffix in ('/manifest.json', '/stream', '/configure'):
		idx = lower.rfind(suffix)
		if idx != -1:
			token = token[:idx]
			lower = token.lower()

	# Quitar slashes sobrantes al principio/final
	token = token.strip('/ \t\n\r')

	if not token:
		return ''

	# Detectar JSON crudo: empieza por '{' sin url-encode
	if token.startswith('{'):
		# URL-encode preservando los caracteres seguros del path.
		# safe='' fuerza encode de todo menos alfanumericos + _.-~
		return _url_quote(token, safe='')

	# Los otros dos formatos (base64 o %7B...) se pueden servir tal cual.
	return token


def _decode_token_to_json(token):
	"""
	Intenta decodificar el token (en cualquiera de sus 3 formatos) de vuelta
	a un dict Python. Devuelve {} si no se consigue.

	Util para extraer metadatos legibles del token sin hablar con Sootio:
	  - Debrid provider configurado
	  - Scrapers activos
	  - Idiomas / filtros
	"""
	if not token:
		return {}
	from json import loads as _jsloads

	try:
		from urllib.parse import unquote as _unq
	except ImportError:
		from urllib import unquote as _unq

	raw = token.strip()

	# Caso 3: url-encoded ('%7B...' o similar)
	if '%' in raw and raw.lstrip('%').startswith(('7B', '7b')):
		try:
			decoded = _unq(raw)
			return _jsloads(decoded)
		except Exception:
			pass
	if raw.startswith('%7B') or raw.startswith('%7b'):
		try:
			return _jsloads(_unq(raw))
		except Exception:
			pass

	# Caso 2: JSON crudo (si alguien lo ha preguardado asi)
	if raw.startswith('{'):
		try:
			return _jsloads(raw)
		except Exception:
			pass

	# Caso 1: base64 (puede ser standard o url-safe)
	import base64
	for decoder in (base64.urlsafe_b64decode, base64.b64decode):
		try:
			# Padding por si acaso
			padded = raw + '=' * (-len(raw) % 4)
			data = decoder(padded).decode('utf-8', errors='replace')
			return _jsloads(data)
		except Exception:
			continue

	return {}


# Nombres largos -> etiqueta corta para UI
_SOOTIO_PROVIDER_FRIENDLY = {
	'realdebrid':  ('Real-Debrid',  'RD'),
	'rd':          ('Real-Debrid',  'RD'),
	'alldebrid':   ('AllDebrid',    'AD'),
	'ad':          ('AllDebrid',    'AD'),
	'torbox':      ('TorBox',       'TB'),
	'tb':          ('TorBox',       'TB'),
	'premiumize':  ('Premiumize',   'PM'),
	'pm':          ('Premiumize',   'PM'),
	'offcloud':    ('OffCloud',     'OC'),
	'oc':          ('OffCloud',     'OC'),
	'debridlink':  ('Debrid-Link',  'DL'),
	'dl':          ('Debrid-Link',  'DL'),
	'debriderapp': ('Debrider.app', 'DA'),
	'debrider':    ('Debrider.app', 'DA'),
	'da':          ('Debrider.app', 'DA'),
}


def _detect_debrid_from_token(token):
	"""
	Lee el token, saca el provider configurado y devuelve algo legible:
	  'Premiumize (PM)'  |  'Real-Debrid (RD)'  |  'not configured'

	Sootio guarda el provider en varios sitios del JSON (compat legacy):
	  - DebridServices[0].provider
	  - DebridProvider
	Se prefieren los de DebridServices (es el formato actual, 1.8+).
	"""
	cfg = _decode_token_to_json(token)
	if not cfg:
		return ''

	providers = []

	# Formato actual
	dbs = cfg.get('DebridServices') or []
	if isinstance(dbs, list):
		for entry in dbs:
			if isinstance(entry, dict):
				p = (entry.get('provider') or '').strip()
				if p: providers.append(p)

	# Fallback legacy
	if not providers:
		legacy = (cfg.get('DebridProvider') or '').strip()
		if legacy: providers.append(legacy)

	if not providers:
		return ''

	labels = []
	for p in providers:
		key = p.lower().replace('-', '').replace('_', '').replace(' ', '').replace('.', '')
		friendly = _SOOTIO_PROVIDER_FRIENDLY.get(key)
		if friendly:
			labels.append('%s (%s)' % friendly)
		else:
			labels.append(p)
	return ' + '.join(labels)


# Quality keywords en nombre / descripcion de Sootio
_QUAL_MAP = [
	('2160', '4K'), ('4k', '4K'), ('uhd', '4K'),
	('1080', '1080p'), ('fhd', '1080p'),
	('720', '720p'), ('hd', '720p'),
	('480', 'SD'), ('sd', 'SD'),
]
_CODEC_MAP = {
	'av1':          'AV1',
	'hevc':         'HEVC',
	'x265':         'HEVC',
	'h265':         'HEVC',
	'x264':         'H264',
	'h264':         'H264',
	'avc':          'H264',
	'hdr10+':       'HDR10+',
	'hdr10':        'HDR',
	'hdr':          'HDR',
	'dolby vision': 'DV',
	'dovi':         'DV',
	'10bit':        '10BIT',
	'10 bit':       '10BIT',
	'atmos':        'ATMOS',
}
_SRC_MAP = {
	'bluray remux':  'REMUX',
	'blu-ray remux': 'REMUX',
	'remux':         'REMUX',
	'bluray':        'BLURAY',
	'blu-ray':       'BLURAY',
	'bdrip':         'BLURAY',
	'web-dl':        'WEBDL',
	'webdl':         'WEBDL',
	'webrip':        'WEBRIP',
	'hdtv':          'HDTV',
	'cam':           'CAM',
	'scr':           'SCR',
}

# Mapeo proveedor Debrid -> etiqueta visual luc_kodi.debrid
# Sootio soporta 7 debrids oficialmente (RD, AD, TB, PM, OC, DL, Debrider.app).
# Los nombres pueden aparecer en distintos formatos en URL y en el campo 'name'.
_SOOTIO_PROVIDER_LABELS = {
	'realdebrid':  'RD',
	'rd':          'RD',
	'alldebrid':   'AD',
	'ad':          'AD',
	'torbox':      'TB',
	'tb':          'TB',
	'premiumize':  'PM',
	'pm':          'PM',
	'offcloud':    'OC',
	'oc':          'OC',
	'debridlink':  'DL',
	'dl':          'DL',
	'debriderapp': 'DA',
	'debrider':    'DA',
	'da':          'DA',
}


def _parse_quality(name_str, desc_str):
	"""Extract quality string from Sootio name + description."""
	combined = (name_str + ' ' + desc_str).lower()
	for kw, q in _QUAL_MAP:
		if kw in combined:
			return q
	return 'SD'


def _parse_info_tags(desc_str, name_str=''):
	"""Extract codec/source/HDR tags from Sootio description + name."""
	tags = []
	d = (desc_str + ' ' + name_str).lower()
	for kw, tag in _CODEC_MAP.items():
		if kw in d and tag not in tags:
			tags.append(tag)
	for kw, tag in _SRC_MAP.items():
		if kw in d and tag not in tags:
			tags.append(tag)
	return tags


def _provider_label_from_stream(url_str, name_str):
	"""
	Intenta extraer el proveedor Debrid del stream.
	Sootio inyecta el nombre del proveedor en 2 sitios posibles:
	  1. En el propio 'name': "Sootio [RD+] 1080p" / "Sootio RealDebrid 4K"
	  2. En la URL: /resolve/RealDebrid/<hash>/ o similar
	Devuelve label corto (RD, AD, TB, PM, OC, DL, DA) o '' si no reconocido.
	"""
	# 1. Buscar en name (patron [XX+] tipo Torrentio o "RealDebrid" explicito)
	if name_str:
		m = re.search(r'\[([A-Z]{2,3})\+?\]', name_str)
		if m:
			key = m.group(1).lower()
			if key in _SOOTIO_PROVIDER_LABELS:
				return _SOOTIO_PROVIDER_LABELS[key]
		n = name_str.lower().replace('-', '').replace('_', '').replace(' ', '')
		for k, v in _SOOTIO_PROVIDER_LABELS.items():
			if k in n:
				return v
	# 2. Fallback: path de la URL
	if url_str:
		m = re.search(r'/(?:resolve|playback|stream)/([^/]+)/', url_str, re.IGNORECASE)
		if m:
			provider_raw = m.group(1).lower().replace('-', '').replace('_', '')
			if provider_raw in _SOOTIO_PROVIDER_LABELS:
				return _SOOTIO_PROVIDER_LABELS[provider_raw]
	return ''


class source:
	timeout = 45  # Sootio puede tardar 30+ segundos en la primera busqueda
	               # por cache-warming de los scrapers del lado servidor
	priority = 2
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self._queue  = queue.SimpleQueue()
		self.language = ['en']
		try:
			instance_idx = int(getSetting('sootio.url') or '0')
		except Exception:
			instance_idx = 0
		# Instancias publicas conocidas
		#  - sooti.info       : instancia oficial del desarrollador
		#  - elfhosted: ha sido retirada (2025) redirigiendo a sooti.info
		_INSTANCES = [
			'https://sooti.info',
		]
		if instance_idx >= len(_INSTANCES):
			instance_idx = 0
		self.base_link  = _INSTANCES[instance_idx]
		# Acepta cualquiera de los 3 formatos que genera sooti.info/configure
		# (base64, JSON crudo, JSON url-encoded) e incluso la URL completa.
		_raw_token = getSetting('sootio.config') or ''
		self.config_b64 = _normalize_sootio_token(_raw_token)

		# Auto-deteccion del Debrid embebido en el token, para mostrarlo en
		# los ajustes sin que el usuario tenga que recordar que provider uso
		# al generar el token. Se ejecuta sobre el token YA normalizado para
		# que funcione tambien cuando el usuario pega la URL completa.
		# Solo escribimos al settings.xml si el label cambio respecto al
		# cacheado, para no spammear disco en cada scrape.
		try:
			_detected = _detect_debrid_from_token(self.config_b64) or 'not configured'
			if getSetting('sootio.debrid.detected') != _detected:
				setSetting('sootio.debrid.detected', _detected)
			self.debrid_detected = _detected
		except Exception:
			self.debrid_detected = ''

		self.movieSearch_link = '/stream/movie/%s.json'
		self.tvSearch_link    = '/stream/series/%s:%s:%s.json'
		self.min_seeders = 0

	# --- URL helpers ----------------------------------------------------------

	def _build_url(self, template, *args):
		"""
		Sootio requiere el token (base64 o JSON url-encoded) en el path:
		  {base_link}/{config_token}/stream/...
		Sin token, no se emite peticion (return None).
		"""
		if not self.config_b64:
			return None
		endpoint = template % args
		return '%s/%s%s' % (self.base_link, self.config_b64, endpoint)

	# --- Fetch ----------------------------------------------------------------

	def _fetch(self, url):
		"""Pide streams a Sootio. Respuesta: {'streams': [...]}."""
		if not url:
			log_utils.log('SOOTIO: _fetch called with empty url (config missing?)', level=log_utils.LOGINFO)
			return []
		# Log la URL enmascarando el token para no filtrar la API key en el log
		try:
			_masked = url
			# Patron: sooti.info/<TOKEN>/stream/... -> reemplaza el token por <TOKEN>
			_masked = re.sub(r'(sooti\.info/)[^/]+(/stream)', r'\1<TOKEN>\2', _masked)
			log_utils.log('SOOTIO: GET %s' % _masked, level=log_utils.LOGINFO)
		except Exception:
			pass
		try:
			results = client.request(url, timeout=self.timeout)
			if not results:
				log_utils.log('SOOTIO: empty response body', level=log_utils.LOGINFO)
				return []
			log_utils.log('SOOTIO: received %d bytes' % len(results), level=log_utils.LOGINFO)
			data = jsloads(results)
			streams = data.get('streams', []) or []
			log_utils.log('SOOTIO: parsed %d streams (before dedup)' % len(streams), level=log_utils.LOGINFO)
		except Exception as e:
			log_utils.log('SOOTIO: fetch/parse error: %s' % str(e), level=log_utils.LOGINFO)
			source_utils.scraper_error('SOOTIO')
			return []

		# Dedup interno: la clave de dedup debe tolerar streams que solo
		# traen 'name'/'description' sin hash40 en URL ni infoHash (que es
		# lo que Sootio devuelve cuando el torrent ya esta cacheado en el
		# Debrid y la URL es tipo /resolve/... sin hash embebido).
		# Si no podemos derivar key, NO descartamos — pasamos el stream
		# tal cual a _parse_files, que ya filtra lo que no sirve.
		seen_keys   = set()
		out_streams = []
		dropped     = 0
		for idx, s in enumerate(streams):
			url_field   = s.get('url', '') or ''
			bh          = s.get('behaviorHints') or {}
			bh_filename = bh.get('filename', '') or ''
			name_fld    = s.get('name', '') or ''
			desc_fld    = s.get('description', '') or s.get('title', '') or ''
			m           = re.search(r'/([0-9a-fA-F]{40})', url_field)
			h           = m.group(1) if m else (s.get('infoHash', '') or '')
			# Log del primer stream para ver la forma real de la respuesta
			if idx == 0:
				try:
					log_utils.log(
						'SOOTIO: first stream keys=%s url_head=%s name=%s infoHash=%s bh_keys=%s'
						% (list(s.keys()),
						   url_field[:80],
						   (name_fld[:60].replace('\n', ' | ')),
						   s.get('infoHash', '')[:16],
						   list(bh.keys())),
						level=log_utils.LOGINFO,
					)
				except Exception:
					pass
			# Clave preferida: hash. Alternativas: filename, url, nombre.
			key = (h or bh_filename or url_field or name_fld).lower().strip()
			if not key:
				# Stream sin nada identificable -> no se puede reproducir
				dropped += 1
				continue
			if key in seen_keys:
				dropped += 1
				continue
			seen_keys.add(key)
			out_streams.append(s)
		log_utils.log('SOOTIO: after dedup %d streams (dropped %d)' % (len(out_streams), dropped), level=log_utils.LOGINFO)
		return out_streams

	# --- Parse ----------------------------------------------------------------

	def _parse_files(self, files, season=None, pack_mode=False,
			search_series=False, total_seasons=None,
			bypass_filter=False, title=None, aliases=None,
			year=None, imdb=None):
		"""
		Parse lista de streams de Sootio.

		Pipeline alineado con AIOStreams para obtener la misma presentacion
		en el source_select (filename real + tags estandar del plugin):
		  1. Derivar filename: preferir behaviorHints.filename, fallback a
		     primera linea de description / segunda linea de name.
		  2. Limpiar via source_utils.clean_name (maneja unicode).
		  3. info_from_name + get_release_quality + get_extra_tags.

		Modo de reproduccion por stream:
		  - url pre-resuelta http(s) -> direct=True, debridonly=False
		  - solo hash disponible -> magnet, direct=False, debridonly=True

		El title matching se omite: Sootio ya filtra por IMDB ID en el servidor.
		El filtro de packs si se aplica en sources_packs.
		"""
		sources = []
		dropped_no_playable = 0
		dropped_exception   = 0
		log_utils.log('SOOTIO: _parse_files entering with %d streams' % len(files), level=log_utils.LOGINFO)

		# Construir hdlr para info_from_name (necesita season/episode context)
		is_episode_ctx = pack_mode or (season is not None)
		try:
			hdlr = 'S%02d' % int(season) if is_episode_ctx and season is not None else (year or '')
		except Exception:
			hdlr = year or ''

		for file in files:
			try:
				url_field   = file.get('url', '') or ''
				bh          = file.get('behaviorHints') or {}
				bh_filename = bh.get('filename', '') or ''
				name_field  = file.get('name', '') or ''
				desc_field  = file.get('description', '') or file.get('title', '') or ''

				# -- 1. URL y modo de reproduccion -----------------------------
				m        = re.search(r'/([0-9a-fA-F]{40})', url_field)
				hash_val = m.group(1).lower() if m else (file.get('infoHash', '') or '').lower()

				if url_field and url_field.startswith('http'):
					play_url   = url_field
					is_direct  = True
					debridonly = False
				elif hash_val:
					play_url   = 'magnet:?xt=urn:btih:%s' % hash_val
					is_direct  = False
					debridonly = True
				else:
					dropped_no_playable += 1
					continue

				# -- 2. Nombre del archivo (patron AIOStreams) ----------------
				# Prioridad: filename -> primera linea de description ->
				#            segunda linea de name -> name entero
				if bh_filename:
					raw_name = bh_filename
				else:
					raw_name = desc_field.split('\n')[0].strip() if desc_field else ''
					if not raw_name:
						lines    = name_field.split('\n')
						raw_name = lines[1].strip() if len(lines) > 1 else name_field
				raw_name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts)$', '', raw_name, flags=re.IGNORECASE)
				name     = source_utils.clean_name(raw_name)
				if not name:
					dropped_no_playable += 1
					continue

				# -- 3. Seeders (desde description, emoji 👤) -----------------
				seeders = 0
				try:
					sm = re.search(r'\U0001f465\s*(\d+)', desc_field)
					if sm:
						seeders = int(sm.group(1))
					if self.min_seeders and seeders < self.min_seeders:
						continue
				except Exception:
					pass

				# -- 4. Idioma / undesirables (pipeline estandar) ------------
				if pack_mode:
					_pkg = 'show' if search_series else 'season'
					name_info = source_utils.info_from_name(
						name, title, year, season=season, pack=_pkg
					)
				else:
					name_info = source_utils.info_from_name(
						name, title, year, hdlr
					)
				try:
					if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
						continue
				except Exception:
					pass
				try:
					undesirables = source_utils.get_undesirables()
					if undesirables and source_utils.remove_undesirables(name_info, undesirables):
						continue
				except Exception:
					pass

				# -- 5. Calidad + info tags (pipeline estandar) --------------
				quality, info = source_utils.get_release_quality(name_info, play_url)
				info = list(info) if info else []
				# get_extra_tags requiere el nombre crudo (antes de info_from_name
				# quitar '+' y otros chars necesarios para detectar HDR10+ / AV1)
				try:
					extra = source_utils.get_extra_tags(name)
					info += [t for t in extra if t not in info]
				except Exception:
					pass

				# -- 6. Tamano (emoji 💾 en description) ----------------------
				dsize = 0
				try:
					size_m = re.findall(
						r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))',
						desc_field)
					if size_m:
						dsize, isize = source_utils._size(size_m[0])
						if isize:
							info.insert(0, isize)
				except Exception:
					pass

				# -- 7. Etiqueta Debrid: SIEMPRE 'Custom' -------------------
				# Uniformidad visual con AIOStreams y MediaFusion: los tres
				# resuelven el Debrid por su cuenta (credenciales embebidas
				# en el token), asi que el plugin no tiene relacion directa
				# con RD/AD/PM/etc. El renderer pinta 'CUSTOM' en naranja
				# salmon (ffd39886) via source_results.py line ~240.
				debrid_key = 'Custom' if is_direct else ''

				info_str = ' | '.join(info)

				# -- 8. Construir item ---------------------------------------
				item = {
					'source':     'torrent',
					'language':   'en',
					'direct':     is_direct,
					'debridonly': debridonly,
					'provider':   'sootio',
					'url':        play_url,
					'hash':       hash_val,
					'name':       name,
					'name_info':  name_info,
					'quality':    quality,
					'info':       info_str,
					'size':       dsize,
					'seeders':    seeders,
				}
				if debrid_key:
					item['debrid'] = debrid_key

				# Pack fields para sources_packs
				if pack_mode:
					item['package'] = 'show' if search_series else 'season'
					if search_series and total_seasons:
						item['last_season'] = total_seasons

				sources.append(item)

			except Exception:
				dropped_exception += 1
				source_utils.scraper_error('SOOTIO')

		log_utils.log(
			'SOOTIO: _parse_files built %d items (dropped: %d no-playable, %d exceptions)'
			% (len(sources), dropped_no_playable, dropped_exception),
			level=log_utils.LOGINFO,
		)
		return sources

	# --- Public API -----------------------------------------------------------

	def sources(self, data, hostDict):
		sources = []
		if not data:
			return sources
		# Sin token configurado no tiene sentido hacer ni una sola peticion.
		if not self.config_b64:
			log_utils.log('SOOTIO: sources() called but no config token set', level=log_utils.LOGINFO)
			return sources
		try:
			is_episode = 'tvshowtitle' in data
			imdb       = data['imdb']
			year       = data['year']
			title      = data['tvshowtitle'] if is_episode else data['title']
			aliases    = data['aliases']
			if is_episode:
				season  = data['season']
				episode = data['episode']
				url     = self._build_url(self.tvSearch_link, imdb, season, episode)
			else:
				season  = None
				url     = self._build_url(self.movieSearch_link, imdb)
			log_utils.log('SOOTIO: sources() imdb=%s episode=%s token_len=%d' % (imdb, is_episode, len(self.config_b64)), level=log_utils.LOGINFO)
		except Exception:
			source_utils.scraper_error('SOOTIO')
			return sources

		files = self._fetch(url)
		try:
			self._queue.put_nowait(files)
		except Exception:
			pass
		result = self._parse_files(
			files, season=season if is_episode else None,
			title=title, aliases=aliases, year=year, imdb=imdb)
		log_utils.log('SOOTIO: sources() returning %d parsed items' % len(result), level=log_utils.LOGINFO)
		return result

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data:
			return sources
		if not self.config_b64:
			return sources
		try:
			title   = data['tvshowtitle']
			aliases = data['aliases']
			imdb    = data['imdb']
			year    = data['year']
			season  = data['season']
		except Exception:
			source_utils.scraper_error('SOOTIO')
			return sources
		try:
			files = self._queue.get(timeout=self.timeout + 1)
		except Exception:
			source_utils.scraper_error('SOOTIO')
			return sources
		return self._parse_files(
			files, season=season, pack_mode=True,
			search_series=search_series, total_seasons=total_seasons,
			bypass_filter=bypass_filter, title=title,
			aliases=aliases, year=year, imdb=imdb)
