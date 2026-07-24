# -*- coding: utf-8 -*-
"""
	jacksparrowscrapers Project - Torz scraper (v2, dual-mode)

	Torz es el addon de torrents de StremThru (https://github.com/MunifTanjim/stremthru),
	self-hostable, con varias instancias publicas. Indexa una base de datos
	crowdsourced de hashes + hashlists publicas (Debrid Media Manager) y
	soporta Multi-Store (RealDebrid, AllDebrid, TorBox, Premiumize, OffCloud,
	Debrid-Link, EasyDebrid, Debrider, PikPak) en una sola instalacion.

	──────────────────────────────────────────────────────────────────────
	DOS MODOS DE FUNCIONAMIENTO
	──────────────────────────────────────────────────────────────────────

	MODO A — PUBLICO (legacy, comportamiento histv1.0.34 y anterior)
	    Pide a la REST API cruda de StremThru:
	        {base}/v0/torrents?sid=<imdb>
	        {base}/v0/torrents?sid=<imdb>:<s>:<e>
	    Devuelve solo hashes de torrents (sin resolver). luc_kodi construye
	    el magnet y lo resuelve con SU PROPIO debrid configurado. Es el modo
	    por defecto para no romper a los usuarios actuales que no tengan un
	    config token.

	MODO B — CUSTOM (nuevo, patron Sootio/Meteor)
	    El usuario configura su(s) debrid en la pagina web de StremThru
	    (.../stremio/torz/configure), pulsa Install y copia el "Manifest URL".
	    Ese manifest lleva un blob de config base64 url-safe embebido en el
	    path con las credenciales del store/debrid:
	        {base}/stremio/torz/<CONFIG>/manifest.json
	    y los streams cuelgan de:
	        {base}/stremio/torz/<CONFIG>/stream/movie/<imdb>.json
	        {base}/stremio/torz/<CONFIG>/stream/series/<imdb>:<s>:<e>.json

	    Como el config lleva las credenciales del debrid, StremThru resuelve
	    por su cuenta y devuelve URLs http(s) YA reproducibles (direct=True,
	    debrid='Custom'). luc_kodi solo sigue el redirect /resolve/ via
	    resolve(); NO vuelve a tocar RD/AD/PM/etc.

	    El usuario guarda solo el config token (o la URL completa, el
	    normalizer la limpia) en 'torz.config'. Hay un Setup Wizard que
	    levanta un mini-servidor LAN para no tener que teclear el blob a mano
	    en Android TV (igual que Sootio/Meteor).

	──────────────────────────────────────────────────────────────────────
	SELECCION DE MODO
	──────────────────────────────────────────────────────────────────────
	  - Si 'torz.config' tiene un token valido -> MODO B (custom).
	  - Si no -> MODO A (publico, instancia de 'torz.url').

	Respuesta por stream en MODO B (igual forma que Sootio/MediaFusion):
	  - url pre-resuelta http(s) -> direct=True, debridonly=False, debrid='Custom'
	  - solo infoHash            -> magnet, direct=False, debridonly=True
	    (StremThru en modo P2P / sin store cacheado: resuelve luc_kodi)
"""

from json import loads as jsloads
import base64
import queue
import re
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow import log_utils
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow.control import setSetting


# Instancias publicas conocidas. El indice se elige con 'torz.url'.
# El host es el mismo para REST API (/v0/...) y para el addon Stremio
# (/stremio/torz/...). Sirve para ambos modos.
_INSTANCES = (
	"https://stremthru.elfhosted.com",
	"https://stremthru.stremio.ru",
	"https://stremthru.13377001.xyz",
	"https://stremthrufortheweebs.midnightignite.me",
)

# StremThru soporta 9 stores/debrids. El nombre del store aparece en el
# JSON de config como 'store_name' (o 's'/'store' en variantes). Mapa a
# etiqueta legible para mostrar en settings (torz.debrid.detected).
_STORE_LABELS = {
	'realdebrid':  'Real-Debrid',
	'real-debrid': 'Real-Debrid',
	'rd':          'Real-Debrid',
	'alldebrid':   'AllDebrid',
	'all-debrid':  'AllDebrid',
	'ad':          'AllDebrid',
	'torbox':      'TorBox',
	'tb':          'TorBox',
	'premiumize':  'Premiumize',
	'pm':          'Premiumize',
	'offcloud':    'OffCloud',
	'oc':          'OffCloud',
	'debridlink':  'Debrid-Link',
	'debrid-link': 'Debrid-Link',
	'dl':          'Debrid-Link',
	'easydebrid':  'EasyDebrid',
	'easy-debrid': 'EasyDebrid',
	'ed':          'EasyDebrid',
	'debrider':    'Debrider',
	'debriderapp': 'Debrider',
	'pikpak':      'PikPak',
	'pp':          'PikPak',
	'p2p':         'P2P (torrent)',
	'torrent':     'P2P (torrent)',
}


def _extract_config(raw):
	"""
	Extrae el blob de config (base64 url-safe) de cualquier forma de entrada:
	  - Manifest URL:  https://host/stremio/torz/<CONFIG>/manifest.json
	  - Stream URL:    https://host/stremio/torz/<CONFIG>/stream/movie/...
	  - stremio://     (ambos formatos)
	  - Path relativo: stremio/torz/<CONFIG>/manifest.json  o  <CONFIG>/manifest.json
	  - Solo el blob base64 puro
	Devuelve el blob limpio o '' si nada util.
	"""
	url = (raw or '').strip().strip('"').strip("'")
	if not url:
		return ''
	if url.startswith('stremio://'):
		url = 'https://' + url[len('stremio://'):]

	# Caso 1: URL/path con /stremio/torz/<CONFIG>/...  (formato oficial)
	# El config es el segmento que sigue a /torz/ y precede a
	# /manifest|/stream|/configure (o final de string). El blob base64
	# url-safe NUNCA contiene '/' ni '.', asi que la clase de chars los
	# excluye para no tragarse '/manifest.json'.
	m = re.search(r'/stremio/torz/([A-Za-z0-9+=_\-%]{16,})(?:/.*)?$', url)
	if m:
		cfg = m.group(1).rstrip('/')
		# Evitar capturar 'configure' como si fuese el config
		if cfg.lower() not in ('configure', 'manifest'):
			return cfg

	# Caso 2: URL con host pero sin el prefijo /stremio/torz explicito:
	# ultimo segmento largo (sin '/' ni '.') antes de /manifest|/stream
	if url.startswith('http'):
		m = re.search(r'/([A-Za-z0-9+=_\-%]{24,})(?:/(?:manifest|stream|configure).*)?$', url)
		if m and not m.group(1).lower().endswith('.json'):
			return m.group(1).rstrip('/')

	# Caso 3: path relativo sin host
	low = url.lower()
	if '/manifest.json' in low and not url.startswith('http'):
		blob = url[:low.rfind('/manifest.json')]
		blob = re.sub(r'^/?stremio/torz/', '', blob)
		blob = blob.strip('/ ')
		if blob and blob.lower() != 'configure':
			return blob

	# Caso 4: blob base64 puro (sin separadores de URL, sin punto de extension)
	if '/' not in url and not url.lower().endswith('.json'):
		# Tolerar el caso de que tenga query (?foo=bar) — quedarse con lo previo
		blob = url.split('?')[0]
		if re.match(r'^[A-Za-z0-9+=_\-%]{16,}$', blob):
			return blob

	# Caso 5: string largo de chars base64 validos
	if re.match(r'^[A-Za-z0-9+=_\-%]{40,}$', url):
		return url

	return ''


def _decode_config_to_json(cfg):
	"""
	Intenta decodificar el blob de config a un dict Python. Devuelve {} si no.

	StremThru codifica el config como JSON -> base64 url-safe (a veces el
	blob viene url-encoded en el path). Algunos despliegues comprimen
	(gzip) antes de base64; eso se intenta tambien.
	"""
	if not cfg:
		return {}

	# El path puede traer el blob url-encoded (%2F, %3D, etc.)
	raw = cfg.strip()
	if '%' in raw:
		try:
			from urllib.parse import unquote as _unq
		except ImportError:
			from urllib import unquote as _unq
		try:
			raw = _unq(raw)
		except Exception:
			pass

	# JSON crudo (poco habitual, pero por si acaso)
	if raw.startswith('{'):
		try:
			return jsloads(raw)
		except Exception:
			pass

	# base64 (standard o url-safe), con padding tolerante
	padded = raw + '=' * (-len(raw) % 4)
	for decoder in (base64.urlsafe_b64decode, base64.b64decode):
		try:
			data = decoder(padded)
		except Exception:
			continue
		# Intento 1: utf-8 directo
		try:
			return jsloads(data.decode('utf-8', errors='strict'))
		except Exception:
			pass
		# Intento 2: gzip -> utf-8
		try:
			import gzip
			import io
			decompressed = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
			return jsloads(decompressed.decode('utf-8', errors='replace'))
		except Exception:
			pass
		# Intento 3: utf-8 con replace (ultimo recurso)
		try:
			return jsloads(data.decode('utf-8', errors='replace'))
		except Exception:
			continue

	return {}


def _iter_store_names(cfg):
	"""
	StremThru guarda los stores configurados en varias formas posibles
	segun version. Recorre todas y va devolviendo nombres de store crudos.

	Formatos observados:
	  - cfg['stores'] = [{'c': 'pm', 't': '...'}, ...]        (ACTUAL ElfHosted/
	    StremThru: 'c'=code del store, 't'=token. ES EL FORMATO REAL.)
	  - cfg['stores'] = [{'name': 'RealDebrid', ...}, ...]   (variante larga)
	  - cfg['stores'] = [{'code': 'rd', ...}, ...]
	  - cfg['stores'] = [{'s': 'rd', 't': '...'}, ...]        (compacto alterno)
	  - cfg['store_name'] / cfg['store'] = 'RealDebrid'       (single, legacy)
	  - cfg['c'] / cfg['s'] = 'rd'                            (compacto single)
	"""
	if not isinstance(cfg, dict):
		return
	stores = cfg.get('stores')
	if isinstance(stores, list):
		for entry in stores:
			if isinstance(entry, dict):
				# 'c' va PRIMERO: es la clave real de StremThru actual.
				for k in ('c', 'code', 'name', 'store_name', 'store', 's', 'n'):
					v = entry.get(k)
					if v:
						yield str(v)
						break
			elif isinstance(entry, str) and entry:
				yield entry
		return
	# Single-store legacy / compacto
	for k in ('c', 'store_name', 'store', 's', 'name', 'code'):
		v = cfg.get(k)
		if v:
			yield str(v)
			return


def _detect_debrid_from_config(cfg_blob):
	"""
	Lee el config, saca los store(s) configurados y devuelve algo legible:
	  'Real-Debrid'  |  'TorBox + Premiumize'  |  'P2P (torrent)'  |  ''
	"""
	cfg = _decode_config_to_json(cfg_blob)
	if not cfg:
		return ''
	labels = []
	for raw_name in _iter_store_names(cfg):
		key = raw_name.lower().replace('-', '').replace('_', '').replace(' ', '').replace('.', '')
		label = _STORE_LABELS.get(key) or _STORE_LABELS.get(raw_name.lower()) or raw_name
		if label not in labels:
			labels.append(label)
	if not labels:
		return ''
	return ' + '.join(labels)


def _normalize_torz_token(raw):
	"""
	Devuelve el blob de config listo para inyectar en el path, o '' si la
	entrada no contiene nada utilizable. Acepta URL completa del manifest,
	stream URL, stremio://, path relativo o el blob puro.
	"""
	return _extract_config(raw)


class source:
	timeout = 15
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self._queue = queue.SimpleQueue()
		self.language = ['en']

		try:
			instance_idx = int(getSetting('torz.url') or '0')
		except Exception:
			instance_idx = 0
		if instance_idx < 0 or instance_idx >= len(_INSTANCES):
			instance_idx = 0
		self.base_link = _INSTANCES[instance_idx]

		# ── Decision de modo ─────────────────────────────────────────────
		# Si hay config token valido -> MODO B (custom). Si no -> MODO A.
		_raw_cfg = getSetting('torz.config') or ''
		self.config = _normalize_torz_token(_raw_cfg)
		self.custom_mode = bool(self.config)

		# Auto-deteccion del debrid embebido en el config, para mostrarlo en
		# ajustes (readonly) sin que el usuario tenga que recordarlo. Solo se
		# escribe a settings.xml si cambio respecto al cacheado (no spamear
		# disco en cada scrape).
		if self.custom_mode:
			try:
				_detected = _detect_debrid_from_config(self.config) or 'not configured'
				if getSetting('torz.debrid.detected') != _detected:
					setSetting('torz.debrid.detected', _detected)
				self.debrid_detected = _detected
			except Exception:
				self.debrid_detected = ''
		else:
			self.debrid_detected = ''

		# Endpoints segun modo
		if self.custom_mode:
			# Addon Stremio configurado
			self.movieSearch_link = '/stremio/torz/%s/stream/movie/%s.json'
			self.tvSearch_link    = '/stremio/torz/%s/stream/series/%s:%s:%s.json'
		else:
			# REST API publica (legacy)
			self.movieSearch_link = '/v0/torrents?sid=%s'
			self.tvSearch_link    = '/v0/torrents?sid=%s:%s:%s'

		self.min_seeders = 0

	# ── URL builders ────────────────────────────────────────────────────

	def _movie_url(self, imdb):
		if self.custom_mode:
			return '%s%s' % (self.base_link, self.movieSearch_link % (self.config, imdb))
		return '%s%s' % (self.base_link, self.movieSearch_link % imdb)

	def _tv_url(self, imdb, season, episode):
		if self.custom_mode:
			return '%s%s' % (self.base_link, self.tvSearch_link % (self.config, imdb, season, episode))
		return '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, episode))

	def _mask(self, url):
		"""Enmascara el config token en logs para no filtrar credenciales."""
		try:
			return re.sub(r'(/stremio/torz/)[^/]+', r'\1<CONFIG>', url)
		except Exception:
			return url

	# ── Fetch ───────────────────────────────────────────────────────────

	def _fetch(self, url):
		"""
		Devuelve la lista de items/streams crudos segun el modo:
		  - MODO A (REST): data['data']['items']  (dicts con hash/name/size/seeders)
		  - MODO B (Stremio): data['streams']     (contrato Stremio estandar)
		"""
		if not url:
			return []
		try:
			log_utils.log('TORZ: GET %s' % self._mask(url), level=log_utils.LOGINFO)
			results = client.request(url, timeout=self.timeout)
			if not results:
				return []
			data = jsloads(results)
			if self.custom_mode:
				files = data.get('streams', []) or []
			else:
				files = (data.get('data') or {}).get('items', []) or []
			log_utils.log('TORZ: parsed %d %s' % (len(files), 'streams' if self.custom_mode else 'items'), level=log_utils.LOGINFO)
			return files
		except Exception:
			source_utils.scraper_error('TORZ')
			return []

	# ── Parse: MODO B (Stremio streams, patron Sootio) ──────────────────

	def _stream_to_item(self, file, title, aliases, year, hdlr, episode_title,
			pack_mode=False, season=None, search_series=False,
			total_seasons=None, bypass_filter=False):
		"""
		Convierte un stream Stremio de StremThru en un item de luc_kodi.
		Devuelve dict o None si no es reproducible / no pasa filtros.
		"""
		url_field   = file.get('url', '') or ''
		bh          = file.get('behaviorHints') or {}
		bh_filename = bh.get('filename', '') or ''
		name_field  = file.get('name', '') or ''
		desc_field  = file.get('description', '') or file.get('title', '') or ''

		# -- 1. Hash y modo de reproduccion --------------------------------
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
			return None

		# -- 2. Nombre del archivo (prioridad: filename real) --------------
		if bh_filename:
			raw_name = bh_filename
		else:
			raw_name = desc_field.split('\n')[0].strip() if desc_field else ''
			if not raw_name:
				lines = name_field.split('\n')
				raw_name = lines[1].strip() if len(lines) > 1 else name_field
		raw_name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts)$', '', raw_name, flags=re.IGNORECASE)
		name = source_utils.clean_name(raw_name)
		if not name:
			return None

		# -- 3. Title / pack matching --------------------------------------
		# StremThru filtra por IMDB ID en el servidor para episodios/peliculas,
		# pero para packs aplicamos los filtros de season/show del plugin.
		if pack_mode:
			if not search_series:
				if not bypass_filter:
					valid, episode_start, episode_end = source_utils.filter_season_pack(
						title, aliases, year, season, name.replace('.(Archie.Bunker', ''))
					if not valid:
						return None
				else:
					episode_start = episode_end = 0
				package = 'season'
			else:
				if not bypass_filter:
					valid, last_season = source_utils.filter_show_pack(
						title, aliases, None, year, season, name.replace('.(Archie.Bunker', ''), total_seasons)
					if not valid:
						return None
				else:
					last_season = total_seasons
				package = 'show'
				episode_start = episode_end = 0
			name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
		else:
			# Pelicula / episodio individual
			if not source_utils.check_title(title, aliases, name.replace('.(Archie.Bunker', ''), hdlr, year):
				return None
			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			package = None
			episode_start = episode_end = 0
			last_season = None

		# -- 4. Idioma / undesirables --------------------------------------
		try:
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				return None
		except Exception:
			pass
		try:
			undesirables = source_utils.get_undesirables()
			if undesirables and source_utils.remove_undesirables(name_info, undesirables):
				return None
		except Exception:
			pass

		# -- 5. Seeders (emoji 👤 en description) ---------------------------
		seeders = 0
		try:
			sm = re.search(r'\U0001f465\s*(\d+)', desc_field)
			if sm:
				seeders = int(sm.group(1))
			if self.min_seeders and seeders < self.min_seeders:
				return None
		except Exception:
			pass

		# -- 6. Calidad + info tags ----------------------------------------
		quality, info = source_utils.get_release_quality(name_info, play_url)
		info = list(info) if info else []
		try:
			extra = source_utils.get_extra_tags(name)
			info += [t for t in extra if t not in info]
		except Exception:
			pass

		# -- 7. Tamano (emoji 💾 o videoSize de behaviorHints) -------------
		dsize = 0
		try:
			video_size = bh.get('videoSize') or 0
			if video_size:
				dsize = int(video_size) / (1024 ** 3)
				isize = '%.2f GB' % dsize if dsize >= 1 else '%.0f MB' % (dsize * 1024)
				info.insert(0, isize)
			else:
				size_m = re.findall(
					r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))',
					desc_field)
				if size_m:
					dsize, isize = source_utils._size(size_m[0])
					if isize:
						info.insert(0, isize)
		except Exception:
			pass

		info_str = ' | '.join(info)

		# -- 8. Construir item ---------------------------------------------
		item = {
			'source':     'torrent',
			'language':   'en',
			'direct':     is_direct,
			'debridonly': debridonly,
			'provider':   'torz',
			'url':        play_url,
			'hash':       hash_val,
			'name':       name,
			'name_info':  name_info,
			'quality':    quality,
			'info':       info_str,
			'size':       dsize,
			'seeders':    seeders,
		}
		# Etiqueta 'Custom' solo en streams ya resueltos por StremThru.
		if is_direct:
			item['debrid'] = 'Custom'
		if pack_mode:
			item['package'] = package
			if search_series and last_season:
				item['last_season'] = last_season
			elif (not search_series) and episode_start:
				item['episode_start'] = episode_start
				item['episode_end']   = episode_end
		return item

	# ── Parse: MODO A (REST items, legacy) ──────────────────────────────

	def _rest_to_item(self, file, title, aliases, year, hdlr, episode_title,
			pack_mode=False, season=None, search_series=False,
			total_seasons=None, bypass_filter=False):
		"""Convierte un item de la REST API /v0/torrents en item luc_kodi."""
		hash = file['hash']
		name = source_utils.clean_name(file['name'])

		if pack_mode:
			if not search_series:
				if not bypass_filter:
					valid, episode_start, episode_end = source_utils.filter_season_pack(
						title, aliases, year, season, name.replace('.(Archie.Bunker', ''))
					if not valid:
						return None
				else:
					episode_start = episode_end = 0
				package = 'season'
			else:
				if not bypass_filter:
					valid, last_season = source_utils.filter_show_pack(
						title, aliases, None, year, season, name.replace('.(Archie.Bunker', ''), total_seasons)
					if not valid:
						return None
				else:
					last_season = total_seasons
				package = 'show'
				episode_start = episode_end = 0
			name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
		else:
			if not source_utils.check_title(title, aliases, name, hdlr, year):
				return None
			name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
			package = None
			episode_start = episode_end = 0
			last_season = None

		try:
			if source_utils.remove_lang(name_info, source_utils.check_foreign_audio()):
				return None
		except Exception:
			pass
		undesirables = source_utils.get_undesirables()
		if undesirables and source_utils.remove_undesirables(name_info, undesirables):
			return None

		url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

		try:
			seeders = file['seeders']
			if self.min_seeders > seeders:
				return None
		except Exception:
			seeders = 0

		quality, info = source_utils.get_release_quality(name_info, url)
		info += [t for t in source_utils.get_extra_tags(name) if t not in info]
		try:
			size = float(file['size'])
			dsize, isize = source_utils.convert_size(size)
			info.insert(0, isize)
		except Exception:
			dsize = 0
		info = ' | '.join(info)

		item = {
			'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
			'provider': 'torz', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
			'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
		}
		if pack_mode:
			item['package'] = package
			if search_series and last_season:
				item['last_season'] = last_season
			elif (not search_series) and episode_start:
				item['episode_start'] = episode_start
				item['episode_end']   = episode_end
		return item

	# ── Public API ──────────────────────────────────────────────────────

	def sources(self, data, hostDict):
		sources = []
		if not data:
			return sources
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
				url = self._tv_url(imdb, season, episode)
			else:
				hdlr = year
				url = self._movie_url(imdb)
		except Exception:
			source_utils.scraper_error('TORZ')
			return sources

		files = self._fetch(url)
		# Encolar para sources_packs (dos veces: seasons + shows)
		try:
			self._queue.put_nowait(files)
			self._queue.put_nowait(files)
		except Exception:
			pass

		convert = self._stream_to_item if self.custom_mode else self._rest_to_item
		for file in files:
			try:
				item = convert(file, title, aliases, year, hdlr, episode_title)
				if item:
					sources_append(item)
			except Exception:
				source_utils.scraper_error('TORZ')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data:
			return sources
		sources_append = sources.append
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			files = self._queue.get(timeout=self.timeout + 1)
		except Exception:
			source_utils.scraper_error('TORZ')
			return sources

		convert = self._stream_to_item if self.custom_mode else self._rest_to_item
		for file in files:
			try:
				item = convert(
					file, title, aliases, year, None, None,
					pack_mode=True, season=season, search_series=search_series,
					total_seasons=total_seasons, bypass_filter=bypass_filter,
				)
				if item:
					sources_append(item)
			except Exception:
				source_utils.scraper_error('TORZ')
		return sources

	# ── Resolve (MODO B): des-restringe URLs lazy /resolve/ ─────────────

	def resolve(self, url):
		"""
		Resuelve una URL de stream de StremThru a un enlace directo reproducible.

		StremThru usa "lazy resolution": muchas URLs son endpoints
		/v0/store/.../link/... o .../strem/... que devuelven el archivo final
		via redirect (302). El config lleva embebidas las credenciales del
		store/debrid, asi que es totalmente autonomo: luc_kodi solo sigue el
		redirect, no consulta RD/AD/PM directamente.

		Si la URL ya es un archivo directo (no contiene un patron de resolucion),
		se devuelve tal cual.
		"""
		try:
			if not url:
				return None
			# Heuristica de "necesita resolucion": StremThru usa varios patrones.
			lazy_markers = ('/v0/store/', '/resolve/', '/strem/', '/playback/', '/link/')
			needs_resolve = any(mk in url for mk in lazy_markers)
			if not needs_resolve:
				return url

			# GET siguiendo redirects -> URL final del archivo.
			final = client.request(url, output='geturl', redirect=True, timeout=self.timeout)
			if (final and final != url
					and not any(mk in final for mk in lazy_markers)):
				log_utils.log('TORZ: resolve() -> %s' % self._mask(final[:90]), level=log_utils.LOGINFO)
				return final

			# Algunos despliegues devuelven el enlace en el cuerpo (texto plano
			# o JSON {"url"/"link"/"location": "..."}).
			body = client.request(url, timeout=self.timeout)
			if body:
				body = body.strip()
				if body.startswith('http'):
					return body.split('\n')[0].strip()
				try:
					j = jsloads(body)
					cand = j.get('url') or j.get('link') or j.get('location')
					if cand and cand.startswith('http'):
						return cand
				except Exception:
					pass

			log_utils.log('TORZ: resolve() could not resolve %s' % self._mask(url[:90]), level=log_utils.LOGINFO)
			return None
		except Exception:
			source_utils.scraper_error('TORZ')
			return None
