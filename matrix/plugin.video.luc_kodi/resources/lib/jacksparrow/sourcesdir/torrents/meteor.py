
"""
	jacksparrowscrapers Project - Meteor scraper (v2, custom)

	Meteor es un Stremio addon propietario de @midnightignite, instancia
	unica: meteorfortheweebs.midnightignite.me. Sin forks ni mirrors.

	CAMBIO DE CONTRATO (Meteor 2.0.0, detectado junio 2026):
	Meteor ya NO expone /stream/<type>/<id>.json en la raiz sin auth.
	Desde v2 requiere configuracion POR USUARIO (proveedor debrid -
	TorBox / Real-Debrid - o Torrent, idiomas, orden de resultados) en:
	    https://meteorfortheweebs.midnightignite.me/stremio/configure
	El manifest configurado que genera esa pagina lleva el blob de config
	embebido en el path, p. ej.:
	    https://.../stremio/<config>/manifest.json
	y los streams cuelgan de esa misma base:
	    https://.../stremio/<config>/stream/movie/<imdb>.json
	    https://.../stremio/<config>/stream/series/<imdb>:<s>:<e>.json

	ENTRADA SIMPLIFICADA (v1.0.31):
	En lugar de pegar la URL completa (>800 chars, impractical en
	Android TV), el wizard guarda solo el config blob base64 en
	meteor.config_token. Este scraper construye la URL completa
	automaticamente desde ese token.

	Compatibilidad hacia atras: si el usuario pego la URL completa
	en la setting antigua, _base_from_token() la detecta y la
	normaliza igual.

	DETECCION DEBRID:
	El blob base64 decodifica a JSON con "debridService" + "debridApiKey".
	_detect_debrid_from_token() extrae el proveedor y lo muestra en
	meteor.debrid.detected (readonly en settings, igual que Sootio).
	El usuario NO necesita autorizar ese proveedor de nuevo en luc_kodi.

	POLITICA DEFAULT: provider.meteor = false. Sin token configurado
	el scraper se auto-desactiva silenciosamente (cero peticiones, cero
	latencia anadida).
"""

from json import loads as jsloads
import base64, re, queue
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow import log_utils

METEOR_HOST = 'https://meteorfortheweebs.midnightignite.me'
METEOR_PATH_PREFIX = '/'   # La URL real es /blob/manifest.json — sin /stremio/

# Debrid service names as returned in the JSON blob → display label
_DEBRID_LABELS = {
	'realdebrid':   'Real-Debrid',
	'alldebrid':    'AllDebrid',
	'premiumize':   'Premiumize',
	'torbox':       'TorBox',
	'debridlink':   'Debrid-Link',
	'offcloud':     'Offcloud',
}


def _extract_blob(raw):
	"""
	Extrae el config blob base64 de cualquier forma de entrada:
	  - URL con host y /stremio/:  https://meteor.../stremio/<BLOB>/manifest.json
	  - URL con host sin /stremio/: https://meteor.../<BLOB>/manifest.json  ← formato actual
	  - stremio:// (ambos formatos)
	  - Path relativo:             <BLOB>/manifest.json
	  - Solo el blob base64 puro
	Devuelve el blob limpio o '' si nada util.
	"""
	url = (raw or '').strip()
	if not url:
		return ''
	if url.startswith('stremio://'):
		url = 'https://' + url[len('stremio://'):]

	# Caso 1a: URL con /stremio/<blob> explícito (formato legacy)
	m = re.search(r'/stremio/([A-Za-z0-9+/=_-]{20,})(?:/(?:manifest|stream|configure).*)?$', url)
	if m:
		return m.group(1)

	# Caso 1b: URL con host — último segmento largo antes de /manifest|/stream|/configure
	# Cubre el formato actual: https://meteor.../<BLOB>/manifest.json
	if url.startswith('http'):
		m = re.search(r'/([A-Za-z0-9+/=_-]{20,})(?:/(?:manifest|stream|configure).*)?$', url)
		if m and '.' not in m.group(1):
			return m.group(1)

	# Caso 2: path relativo <blob>/manifest.json sin host
	if url.endswith('/manifest.json') and not url.startswith('http'):
		blob = url[:-len('/manifest.json')]
		blob = re.sub(r'^/?stremio/', '', blob)
		if blob:
			return blob

	# Caso 3: blob puro sin separadores URL
	if '/' not in url and '.' not in url.split('?')[0]:
		return url

	# Caso 4: string largo de chars base64 válidos
	if re.match(r'^[A-Za-z0-9+/=_-]{50,}$', url):
		return url

	return ''


def _detect_debrid_from_token(raw):
	"""
	Decodifica el blob base64 y extrae el nombre del proveedor debrid.
	Devuelve etiqueta legible (ej. 'Real-Debrid') o '' si no hay debrid.
	"""
	blob = _extract_blob(raw) or raw.strip()
	if not blob:
		return ''
	try:
		# base64 puede necesitar padding
		padded = blob + '=' * (-len(blob) % 4)
		cfg = jsloads(base64.b64decode(padded).decode('utf-8', errors='replace'))
		svc = cfg.get('debridService', '')
		key = cfg.get('debridApiKey', '')
		if svc and key:
			return _DEBRID_LABELS.get(svc.lower(), svc)
	except Exception:
		pass
	return ''


def _base_from_token(raw):
	"""
	Construye la base URL para /stream/ a partir del token o URL que
	el usuario haya guardado en meteor.config_token.
	Devuelve '' si no hay nada utilizable.
	"""
	blob = _extract_blob(raw)
	if not blob:
		return ''
	return '%s%s%s' % (METEOR_HOST, METEOR_PATH_PREFIX, blob)


# Alias para compatibilidad con codigo anterior que llamaba _base_from_manifest
_base_from_manifest = _base_from_token


class source:
	timeout = 10
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_queue = queue.SimpleQueue()
	def __init__(self):
		self.language = ['en']
		# Acepta tanto meteor.config_token (nuevo) como meteor.manifest_url (legacy)
		raw = getSetting('meteor.config_token') or getSetting('meteor.manifest_url') or ''
		self.base_link = _base_from_token(raw)
		log_utils.log('[METEOR] config_token=%s base_link=%s' % (repr(raw[:40]) if raw else 'EMPTY', repr(self.base_link[:60]) if self.base_link else 'EMPTY'), level=log_utils.LOGWARNING)
		self.movieSearch_link = '/stream/movie/%s.json'
		self.tvSearch_link = '/stream/series/%s:%s:%s.json'
		self.min_seeders = 0

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		if not self.base_link:
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
				url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, episode))
			else:
				hdlr = year
				url = '%s%s' % (self.base_link, self.movieSearch_link % imdb)
			try:
				results = client.request(url, timeout=self.timeout)
				files = jsloads(results)['streams']
				log_utils.log('[METEOR] url=%s streams=%d' % (url, len(files)), level=log_utils.LOGWARNING)
			except Exception as e:
				log_utils.log('[METEOR] request failed url=%s err=%s' % (url, str(e)), level=log_utils.LOGWARNING)
				files = []
				raise
			finally:
				self._queue.put_nowait(files) # if seasons
				self._queue.put_nowait(files) # if shows
			_INFO = re.compile(r'💾.*')
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('METEOR')
			return sources

		for file in files:
			try:
				# Meteor+Premiumize/AllDebrid devuelve URL directa ya resuelta (sin infoHash).
				# Meteor+TorBox/RD puede devolver infoHash para resolver en luc_kodi.
				direct_url = file.get('url') or ''
				hash = file.get('infoHash') or ''
				if not direct_url and not hash:
					continue

				hints = file.get('behaviorHints') or {}
				filename = hints.get('filename') or ''
				desc = file.get('title') or file.get('description') or ''
				file_title = desc.split('\n')
				file_info_list = [x for x in file_title if _INFO.match(x)]
				file_info = file_info_list[0] if file_info_list else desc

				# Preferir filename de behaviorHints (limpio, sin emojis)
				name_raw = filename or (file_title[0] if file_title else desc)
				name = source_utils.clean_name(name_raw)
				if not name:
					continue

				if not source_utils.check_title(title, aliases, name.replace('.(Archie.Bunker', ''), hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				if direct_url:
					# URL directa ya resuelta por Premiumize en Meteor
					play_url = direct_url
					is_direct = True
					is_debridonly = False
				else:
					play_url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
					is_direct = False
					is_debridonly = True

				try:
					seeders = int(re.search(r'\U0001f465\s*(\d+)', desc).group(1))
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, name)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					video_size = hints.get('videoSize') or 0
					if video_size:
						dsize = int(video_size) / (1024 ** 3)
						isize = '%.1f GB' % dsize if dsize >= 1 else '%.0f MB' % (dsize * 1024)
						info.insert(0, isize)
					else:
						size_s = re.search(r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', file_info).group(0)
						dsize, isize = source_utils._size(size_s)
						info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': is_direct,
					'debridonly': is_debridonly, 'provider': 'meteor',
					'url': play_url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders
				}
				if hash: item['hash'] = hash
				item['debrid'] = 'Custom'
				sources_append(item)
			except:
				source_utils.scraper_error('METEOR')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data: return sources
		if not self.base_link: return sources
		sources_append = sources.append
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			files = self._queue.get(timeout=self.timeout + 1)
			_INFO = re.compile(r'💾.*')
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('METEOR')
			return sources

		for file in files:
			try:
				hash = file['infoHash']
				desc = file.get('description') or file.get('title') or ''
				file_title = desc.split('\n')
				file_info_list = [x for x in file_title if _INFO.match(x)]
				file_info = file_info_list[0] if file_info_list else desc

				name = source_utils.clean_name(file_title[0])

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
					seeders = int(re.search(r'👤\s*(\d+)', desc).group(1))
					if self.min_seeders > seeders: continue
				except: seeders = 0

				quality, info = source_utils.get_release_quality(name_info, url)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					size = re.search(r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', file_info).group(0)
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True, 'true_size': True,
					'provider': 'meteor', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders, 'package': package
				}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end})
				item['debrid'] = 'Custom'
				sources_append(item)
			except:
				source_utils.scraper_error('METEOR')
		return sources
