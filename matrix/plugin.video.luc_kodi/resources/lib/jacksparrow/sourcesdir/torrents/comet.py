# -*- coding: utf-8 -*-
"""
	jacksparrowscrapers Project - Comet scraper (v2, dual-mode)

	Comet (https://github.com/g0ldyy/comet) es el addon de torrents/debrid mas
	rapido de Stremio: agrega metadatos de 15+ scrapers (Torrentio, Zilean,
	MediaFusion, Jackett/Prowlarr, DMM, etc.) y comprueba disponibilidad en
	9+ debrids (RealDebrid, AllDebrid, Premiumize, TorBox, Debrid-Link,
	Debrider, EasyDebrid, OffCloud, PikPak). Self-hostable, con varias
	instancias publicas patrocinadas por ElfHosted y otros.

	──────────────────────────────────────────────────────────────────────
	DOS MODOS DE FUNCIONAMIENTO
	──────────────────────────────────────────────────────────────────────

	MODO A — PUBLICO (legacy, comportamiento hasta v1.0.35 y anterior)
	    Usa un config blob FIJO y publico (debridService="torrent", apiKey
	    vacio) embebido en el path:
	        {base}/<CONFIG_TORRENT>/stream/movie/<imdb>.json
	        {base}/<CONFIG_TORRENT>/stream/series/<imdb>:<s>:<e>.json
	    Comet devuelve solo torrents (infoHash, sin resolver). luc_kodi
	    construye el magnet y lo resuelve con SU PROPIO debrid configurado.
	    Es el modo por defecto para no romper a los usuarios actuales que no
	    tengan un config token.

	MODO B — CUSTOM (nuevo, patron Sootio/Meteor/Torz)
	    El usuario configura su(s) debrid en la pagina web de Comet
	    (.../configure), pulsa Install y copia el "Manifest URL". Ese manifest
	    lleva un blob de config base64 embebido en el path con las credenciales
	    del/los debrid(s):
	        {base}/<CONFIG>/manifest.json
	    y los streams cuelgan de:
	        {base}/<CONFIG>/stream/movie/<imdb>.json
	        {base}/<CONFIG>/stream/series/<imdb>:<s>:<e>.json

	    Como el config lleva las credenciales del debrid, Comet resuelve por
	    su cuenta. Para cada torrent cacheado devuelve un stream con una URL
	    de PLAYBACK ya reproducible:
	        {base}/<CONFIG>/playback/<hash>/<service_idx>/<file_idx>/<s>/<e>/...
	    que responde con un redirect 302 al CDN del debrid (direct=True,
	    debrid='Custom'). luc_kodi solo sigue ese redirect via resolve(); NO
	    vuelve a tocar RD/AD/PM/etc.

	    El usuario guarda solo el config token (o la URL completa, el
	    normalizer la limpia) en 'comet.config'. Hay un Setup Wizard que
	    levanta un mini-servidor LAN para no tener que teclear el blob a mano
	    en Android TV (igual que Sootio/Meteor/Torz).

	──────────────────────────────────────────────────────────────────────
	SELECCION DE MODO
	──────────────────────────────────────────────────────────────────────
	  - Si 'comet.config' tiene un token valido -> MODO B (custom).
	  - Si no -> MODO A (publico, config "torrent" fijo en 'comet.url').

	Respuesta por stream (misma forma en ambos modos, contrato Stremio):
	  - url de playback http(s) -> direct=True, debridonly=False, debrid='Custom'
	  - solo infoHash           -> magnet, direct=False, debridonly=True
	    (Comet en modo torrent / sin debrid cacheado: resuelve luc_kodi)
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


# Instancias publicas conocidas. El indice se elige con 'comet.url'.
# El host es el mismo para todos los endpoints (/<config>/stream/...,
# /<config>/playback/..., /configure). Sirve para ambos modos.
_INSTANCES = (
	"https://comet.stremio.ru",
	"https://cometfortheweebs.midnightignite.me",
	"https://comet.elfhosted.com",
)

# Config blob PUBLICO fijo para MODO A (debridService="torrent", apiKey vacio).
# Es exactamente el mismo JSON que se usaba en _params() en v1.0.35: pide a
# Comet solo torrents (sin resolver), para que luc_kodi resuelva con su debrid.
#   {"maxResultsPerResolution":0,"maxSize":0,"cachedOnly":false,
#    "removeTrash":true,"resultFormat":["title","metadata","size","languages"],
#    "debridService":"torrent","debridApiKey":"","debridStreamProxyPassword":"",
#    "languages":{"required":[],"exclude":[],"preferred":[]},"resolutions":{},
#    "options":{"remove_ranks_under":-10000000000,
#               "allow_english_in_languages":false,
#               "remove_unknown_languages":false}}
_PUBLIC_TORRENT_CONFIG = (
	'eyJtYXhSZXN1bHRzUGVyUmVzb2x1dGlvbiI6MCwibWF4U2l6ZSI6MCwiY2FjaGVkT25seSI6ZmFsc2Us'
	'InJlbW92ZVRyYXNoIjp0cnVlLCJyZXN1bHRGb3JtYXQiOlsidGl0bGUiLCJtZXRhZGF0YSIsInNpemUi'
	'LCJsYW5ndWFnZXMiXSwiZGVicmlkU2VydmljZSI6InRvcnJlbnQiLCJkZWJyaWRBcGlLZXkiOiIiLCJk'
	'ZWJyaWRTdHJlYW1Qcm94eVBhc3N3b3JkIjoiIiwibGFuZ3VhZ2VzIjp7InJlcXVpcmVkIjpbXSwiZXhj'
	'bHVkZSI6W10sInByZWZlcnJlZCI6W119LCJyZXNvbHV0aW9ucyI6e30sIm9wdGlvbnMiOnsicmVtb3Zl'
	'X3JhbmtzX3VuZGVyIjotMTAwMDAwMDAwMDAsImFsbG93X2VuZ2xpc2hfaW5fbGFuZ3VhZ2VzIjpmYWxz'
	'ZSwicmVtb3ZlX3Vua25vd25fbGFuZ3VhZ2VzIjpmYWxzZX19'
)

# Debrids soportados por Comet. La clave en el JSON de config aparece como
# 'service' (dentro de debridServices/_debridEntries) o como 'debridService'
# (legacy single). Mapa a etiqueta legible para 'comet.debrid.detected'.
_STORE_LABELS = {
	'realdebrid':  'Real-Debrid',
	'real-debrid': 'Real-Debrid',
	'rd':          'Real-Debrid',
	'alldebrid':   'AllDebrid',
	'all-debrid':  'AllDebrid',
	'ad':          'AllDebrid',
	'premiumize':  'Premiumize',
	'pm':          'Premiumize',
	'torbox':      'TorBox',
	'tb':          'TorBox',
	'debridlink':  'Debrid-Link',
	'debrid-link': 'Debrid-Link',
	'dl':          'Debrid-Link',
	'debrider':    'Debrider',
	'debriderapp': 'Debrider',
	'db':          'Debrider',
	'easydebrid':  'EasyDebrid',
	'easy-debrid': 'EasyDebrid',
	'ed':          'EasyDebrid',
	'offcloud':    'OffCloud',
	'oc':          'OffCloud',
	'pikpak':      'PikPak',
	'pp':          'PikPak',
	'stremthru':   'StremThru',
	'st':          'StremThru',
	'torrent':     'P2P (torrent)',
	'p2p':         'P2P (torrent)',
}


def _extract_config(raw):
	"""
	Extrae el blob de config (base64, embebido como segmento del path) de
	cualquier forma de entrada:
	  - Manifest URL:  https://host/<CONFIG>/manifest.json
	  - Stream URL:    https://host/<CONFIG>/stream/movie/...
	  - stremio://     (ambos formatos)
	  - Path relativo: <CONFIG>/manifest.json
	  - Solo el blob base64 puro
	Devuelve el blob limpio o '' si nada util.

	NOTA: el config de Comet es base64 estandar (puede llevar '+', '/', '='),
	pero cuando viaja como SEGMENTO de path NO contiene '/' literal sin
	codificar (el separador de path). Aun asi toleramos url-encoding (%2F).
	"""
	url = (raw or '').strip().strip('"').strip("'")
	if not url:
		return ''
	if url.startswith('stremio://'):
		url = 'https://' + url[len('stremio://'):]

	# Caso 1: URL completa con host. El config es el segmento que va justo
	# despues del host y antes de /manifest|/stream|/playback|/configure.
	# Clase de chars: base64 (incl. url-safe y url-encoded), sin '/' ni '.'.
	if url.startswith('http'):
		# Quitar el esquema+host para razonar sobre el path.
		m = re.match(r'^https?://[^/]+/(.+)$', url)
		path = m.group(1) if m else ''
		if path:
			# El primer segmento "largo" del path es el config.
			seg = path.split('/')[0]
			seg = seg.split('?')[0].strip('/ ')
			low = seg.lower()
			if (seg and len(seg) >= 16
					and low not in ('manifest.json', 'manifest', 'configure', 'stream',
					                'playback', 'static', 'assets', 'kodi')
					and not low.endswith('.json')):
				return seg

	# Caso 2: path relativo con /manifest.json o /stream/... (sin host)
	low = url.lower()
	if not url.startswith('http') and ('/manifest.json' in low or '/stream/' in low or '/playback/' in low):
		seg = url.strip('/').split('/')[0]
		seg = seg.split('?')[0]
		if seg and len(seg) >= 16 and seg.lower() not in ('configure', 'manifest'):
			return seg

	# Caso 3: blob base64 puro (sin separadores de URL, sin extension)
	if '/' not in url and not url.lower().endswith('.json'):
		blob = url.split('?')[0]
		if re.match(r'^[A-Za-z0-9+/=_\-%]{16,}$', blob):
			return blob

	# Caso 4: string largo de chars base64 validos (con separadores de path
	# por si el usuario pega "<CONFIG>/manifest.json" pegado sin host).
	first = url.strip('/').split('/')[0].split('?')[0]
	if re.match(r'^[A-Za-z0-9+/=_\-%]{24,}$', first) and first.lower() not in ('configure', 'manifest'):
		return first

	return ''


def _decode_config_to_json(cfg):
	"""
	Intenta decodificar el blob de config a un dict Python. Devuelve {} si no.

	Comet codifica el config como JSON -> base64 (estandar). El blob puede
	venir url-encoded en el path (%2F, %3D, etc.). Algunos despliegues
	comprimen (gzip) antes de base64; se intenta tambien.
	"""
	if not cfg:
		return {}

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

	# base64 (estandar o url-safe), con padding tolerante
	padded = raw + '=' * (-len(raw) % 4)
	for decoder in (base64.b64decode, base64.urlsafe_b64decode):
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
	Comet guarda los debrids configurados en varias formas posibles segun
	version. Recorre todas y va devolviendo nombres de service crudos.

	Formatos observados:
	  - cfg['debridServices'] = [{'service':'realdebrid','apiKey':'...'}, ...]
	    (ACTUAL multi-debrid, forma user-facing que se codifica desde la web)
	  - cfg['_debridEntries']  = [{'service':'realdebrid','apiKey':'...'}, ...]
	    (forma interna normalizada por el servidor; a veces queda embebida)
	  - cfg['debridService'] = 'realdebrid'                  (legacy single)
	  - cfg['service'] / cfg['debrid'] = 'rd'                (compacto)
	"""
	if not isinstance(cfg, dict):
		return
	for list_key in ('debridServices', '_debridEntries', 'debrids', 'services'):
		entries = cfg.get(list_key)
		if isinstance(entries, list) and entries:
			for entry in entries:
				if isinstance(entry, dict):
					for k in ('service', 'name', 'debridService', 'code', 's', 'type'):
						v = entry.get(k)
						if v:
							yield str(v)
							break
				elif isinstance(entry, str) and entry:
					yield entry
			return
	# Single-debrid legacy / compacto
	for k in ('debridService', 'service', 'debrid', 'code', 's'):
		v = cfg.get(k)
		if v:
			yield str(v)
			return


def _detect_debrid_from_config(cfg_blob):
	"""
	Lee el config, saca el/los debrid(s) configurado(s) y devuelve algo
	legible:
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


def _normalize_comet_token(raw):
	"""
	Devuelve el blob de config listo para inyectar en el path, o '' si la
	entrada no contiene nada utilizable. Acepta URL completa del manifest,
	stream URL, stremio://, path relativo o el blob puro.

	Se rechaza explicitamente el config "torrent" publico (sin debrid): ese
	es el MODO A y no debe activar el modo custom — para custom el usuario
	tiene que haber configurado al menos un debrid real.
	"""
	cfg = _extract_config(raw)
	if not cfg:
		return ''
	# Si el blob decodifica a un config SOLO-torrent (sin debrid real),
	# no lo tratamos como token custom valido.
	detected = _detect_debrid_from_config(cfg)
	if detected and detected.strip().lower() in ('p2p (torrent)', 'torrent', 'p2p'):
		# Solo torrent -> no es un setup de debrid; dejar que use MODO A.
		return ''
	return cfg


class source:
	timeout = 10
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self._queue = queue.SimpleQueue()
		self.language = ['en']

		try:
			instance_idx = int(getSetting('comet.url') or '2')
		except Exception:
			instance_idx = 2
		if instance_idx < 0 or instance_idx >= len(_INSTANCES):
			instance_idx = 2
		self.base_link = _INSTANCES[instance_idx]

		# ── Decision de modo ─────────────────────────────────────────────
		# Si hay config token valido (con debrid real) -> MODO B (custom).
		# Si no -> MODO A (publico, config "torrent" fijo).
		_raw_cfg = getSetting('comet.config') or ''
		self.config = _normalize_comet_token(_raw_cfg)
		self.custom_mode = bool(self.config)

		# Config efectivo que va en el path: el del usuario (custom) o el
		# blob publico "torrent" fijo (legacy).
		self.path_config = self.config if self.custom_mode else _PUBLIC_TORRENT_CONFIG

		# Auto-deteccion del debrid embebido en el config, para mostrarlo en
		# ajustes (readonly) sin que el usuario tenga que recordarlo. Solo se
		# escribe a settings.xml si cambio respecto al cacheado.
		if self.custom_mode:
			try:
				_detected = _detect_debrid_from_config(self.config) or 'not configured'
				if getSetting('comet.debrid.detected') != _detected:
					setSetting('comet.debrid.detected', _detected)
				self.debrid_detected = _detected
			except Exception:
				self.debrid_detected = ''
		else:
			self.debrid_detected = ''

		# Endpoints (mismo path en ambos modos; cambia solo el config blob).
		self.movieSearch_link = '/%s/stream/movie/%s.json'
		self.tvSearch_link    = '/%s/stream/series/%s:%s:%s.json'
		self.min_seeders = 0

	# ── URL builders ────────────────────────────────────────────────────

	def _movie_url(self, imdb):
		return '%s%s' % (self.base_link, self.movieSearch_link % (self.path_config, imdb))

	def _tv_url(self, imdb, season, episode):
		return '%s%s' % (self.base_link, self.tvSearch_link % (self.path_config, imdb, season, episode))

	def _mask(self, url):
		"""Enmascara el config token en logs para no filtrar credenciales."""
		try:
			# Solo enmascarar el config del usuario (no el publico fijo).
			if self.custom_mode and self.config:
				return url.replace(self.config, '<CONFIG>')
			return url
		except Exception:
			return url

	# ── Fetch ───────────────────────────────────────────────────────────

	def _fetch(self, url):
		"""Devuelve la lista de streams crudos (contrato Stremio: data['streams'])."""
		if not url:
			return []
		try:
			log_utils.log('COMET: GET %s' % self._mask(url), level=log_utils.LOGINFO)
			results = client.request(url, timeout=self.timeout)
			if not results:
				return []
			data = jsloads(results)
			files = data.get('streams', []) or []
			log_utils.log('COMET: parsed %d streams (%s mode)' % (
				len(files), 'custom' if self.custom_mode else 'public'), level=log_utils.LOGINFO)
			return files
		except Exception:
			source_utils.scraper_error('COMET')
			return []

	# ── Parse: stream Stremio -> item luc_kodi ──────────────────────────

	def _stream_to_item(self, file, title, aliases, year, hdlr, episode_title,
			pack_mode=False, season=None, search_series=False,
			total_seasons=None, bypass_filter=False):
		"""
		Convierte un stream Stremio de Comet en un item de luc_kodi.
		Devuelve dict o None si no es reproducible / no pasa filtros.

		Comet formatea la 'description' con separadores '┈➤' y una linea de
		metadatos que incluye 💾 (tamano) y 👤 (seeders). El nombre real del
		release esta en la primera linea.
		"""
		url_field = file.get('url', '') or ''
		desc_field = file.get('description', '') or file.get('title', '') or ''
		bh = file.get('behaviorHints') or {}
		bh_filename = bh.get('filename', '') or ''

		# -- 1. Hash y modo de reproduccion --------------------------------
		# En modo custom con debrid, la url es de /playback/<hash>/...; el
		# hash de 40 hex esta en el propio path. En modo torrent, viene
		# infoHash directo.
		m = re.search(r'\b([0-9a-fA-F]{40})\b', url_field)
		hash_val = m.group(1).lower() if m else (file.get('infoHash', '') or '').lower()

		if url_field and url_field.startswith('http'):
			# URL de playback (custom mode con debrid) -> direct, resolve()
			# seguira el redirect 302 al CDN del debrid.
			play_url   = url_field
			is_direct  = True
			debridonly = False
		elif hash_val:
			# Solo torrent (modo publico, o uncached sin debrid) -> magnet.
			play_url   = 'magnet:?xt=urn:btih:%s' % hash_val
			is_direct  = False
			debridonly = True
		else:
			return None

		# -- 2. Nombre del release -----------------------------------------
		# Estructura de la description de Comet: primera linea = nombre del
		# release; lineas siguientes con metadatos. Tolera el separador '┈➤'.
		desc_lines = desc_field.replace('┈➤', '\n').split('\n')
		desc_lines = [l.strip() for l in desc_lines if l.strip()]
		if bh_filename:
			raw_name = bh_filename
		elif desc_lines:
			raw_name = desc_lines[0]
		else:
			raw_name = file.get('name', '') or ''
		raw_name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts)$', '', raw_name, flags=re.IGNORECASE)
		name = source_utils.clean_name(raw_name)
		if not name:
			return None

		# Linea de info (la que lleva 💾 tamano / 👤 seeders), si existe.
		_INFO = re.compile(r'\U0001f4be|\U0001f465|GB|MB|GiB|MiB')
		info_lines = [l for l in desc_lines if _INFO.search(l)]
		info_blob = ' | '.join(info_lines) if info_lines else desc_field

		# -- 3. Title / pack matching --------------------------------------
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

		# -- 5. Seeders (emoji 👤 en la linea de info) ----------------------
		seeders = 0
		try:
			sm = re.search(r'\U0001f465\s*(\d+)', info_blob)
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
					info_blob)
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
			'provider':   'comet',
			'url':        play_url,
			'hash':       hash_val,
			'name':       name,
			'name_info':  name_info,
			'quality':    quality,
			'info':       info_str,
			'size':       dsize,
			'seeders':    seeders,
		}
		# Etiqueta 'Custom' solo en streams ya resueltos por Comet (playback).
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
			source_utils.scraper_error('COMET')
			return sources

		files = self._fetch(url)
		# Encolar para sources_packs (dos veces: seasons + shows)
		try:
			self._queue.put_nowait(files)
			self._queue.put_nowait(files)
		except Exception:
			pass

		for file in files:
			try:
				item = self._stream_to_item(file, title, aliases, year, hdlr, episode_title)
				if item:
					sources_append(item)
			except Exception:
				source_utils.scraper_error('COMET')
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
			source_utils.scraper_error('COMET')
			return sources

		for file in files:
			try:
				item = self._stream_to_item(
					file, title, aliases, year, None, None,
					pack_mode=True, season=season, search_series=search_series,
					total_seasons=total_seasons, bypass_filter=bypass_filter,
				)
				if item:
					sources_append(item)
			except Exception:
				source_utils.scraper_error('COMET')
		return sources

	# ── Resolve (MODO B): sigue el redirect 302 del endpoint /playback/ ──

	def resolve(self, url):
		"""
		Resuelve una URL de stream de Comet a un enlace directo reproducible.

		En modo custom con debrid, la url es del endpoint /playback/<hash>/...
		que responde con un redirect 302 al CDN del debrid (el config lleva
		embebidas las credenciales, asi que es autonomo: luc_kodi solo sigue
		el redirect, no consulta RD/AD/PM directamente).

		Si la URL ya es un archivo directo (no contiene un patron de
		resolucion), se devuelve tal cual.
		"""
		try:
			if not url:
				return None
			# Heuristica de "necesita resolucion": el endpoint de Comet.
			lazy_markers = ('/playback/', '/resolve/', '/strem/', '/link/', '/download/')
			needs_resolve = any(mk in url for mk in lazy_markers)
			if not needs_resolve:
				return url

			# GET siguiendo redirects -> URL final del archivo (CDN debrid).
			final = client.request(url, output='geturl', redirect=True, timeout=self.timeout)
			if (final and final != url
					and not any(mk in final for mk in lazy_markers)):
				log_utils.log('COMET: resolve() -> %s' % self._mask(final[:90]), level=log_utils.LOGINFO)
				return final

			# Algunos despliegues devuelven el enlace en el cuerpo (texto
			# plano o JSON {"url"/"link"/"location": "..."}).
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

			log_utils.log('COMET: resolve() could not resolve %s' % self._mask(url[:90]), level=log_utils.LOGINFO)
			return None
		except Exception:
			source_utils.scraper_error('COMET')
			return None
