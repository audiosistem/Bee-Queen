
"""
	jacksparrowscrapers Project - easynews (Easynews Global Search / HTTP)

	v1.0.52: Easynews como 5º proveedor premium.

	IMPORTANTE - Easynews NO es un debrid:
	  Es un proveedor de Usenet con buscador propio que devuelve enlaces HTTP
	  DIRECTOS a ficheros ya existentes en sus servidores. No hay magnet, no
	  hay hash de torrent, no hay espera de caché: el enlace es reproducible
	  al instante. Por eso los items salen con direct=True y saltan el
	  pipeline de comprobacion de caché de debrid en sources.py.

	IMPORTANTE - Easynews es de CUOTA MEDIDA:
	  Cada byte reproducido consume el cupo mensual HTTP del usuario
	  (Classic 20 GB, Plus 40 GB, Big Gig 150 GB). Por eso este scraper
	  aplica un tope de tamaño por fichero (easynews.max_size, GB) que por
	  defecto NO es 0. Sin ese tope, un remux 4K se come el plan entero.

	API (verificado contra la implementación de referencia de AIOStreams,
	builtins/easynews-search, julio 2026):
	  V2  GET https://members.easynews.com/2.0/search/solr-search/
	      hasta 250 resultados por página (pby). Endpoint veterano y estable.
	  V3  GET https://members.easynews.com/3.0/api/search
	      ignora pby/dni: siempre 100 por página. Mismos metadatos.
	  Auth: HTTP Basic (usuario:contraseña de Easynews) en cabecera.
	  Respuesta: {'data': [...], 'downURL':, 'dlFarm':, 'dlPort':, 'numPages':}
	  Campos por item: hash/'0', id (sufijo de 4 chars del hash en la URL de
	  descarga), fn/'10' (nombre sin extensión), '11' (extensión), rawSize,
	  '14' (duración), alangs/audio_tracks, slangs, acodec, vcodec,
	  xres, yres, bps, passwd, type, virus.
"""

import re
import requests
from base64 import b64encode
from urllib.parse import quote
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting

BASE_LINK = 'https://members.easynews.com'
SEARCH_V2 = '/2.0/search/solr-search/'
SEARCH_V3 = '/3.0/api/search'

# Extensiones de vídeo aceptadas. Easynews indexa de todo (rar, par2, nfo...).
VIDEO_EXT = (
	'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.mpg', '.mpeg',
	'.divx', '.xvid', '.flv', '.webm', '.avc', '.3gp', '.m2ts', '.ts',
)


class source:
	timeout = 20
	priority = 1
	pack_capable = False  # Easynews indexa ficheros sueltos, no packs
	hasMovies = True
	hasEpisodes = True

	# v1.0.54: tope de items devueltos. La API 2.0 da hasta 250 por pagina y
	# cada item lleva una URL larga; sin tope, el blob repr(sources) que se
	# guarda en rel_src era el mayor del addon con diferencia y disparaba el
	# SystemError del AST al releerlo. 80 sobra para el picker.
	MAX_RESULTS = 80

	def __init__(self):
		self.user_agent = 'luc_kodi for Kodi'
		self.username = getSetting('easynews.username')
		self.password = getSetting('easynews.password')
		self.api_version = getSetting('easynews.api_version') or '2.0'
		self.moderation = 1 if getSetting('easynews.moderation') == 'true' else 0
		try:
			self.max_size = int(getSetting('easynews.max_size') or 20)
		except Exception:
			self.max_size = 20
		self.language = ['en']
		self.auth = self._basic_auth()

	def _basic_auth(self):
		if not self.username or not self.password:
			return None
		try:
			raw = ('%s:%s' % (self.username, self.password)).encode('utf-8')
			return 'Basic %s' % b64encode(raw).decode('utf-8')
		except Exception:
			return None

	def _search_params(self, query, page=1):
		params = {
			'gps': query,          # consulta por palabras clave
			'pno': str(page),      # número de página
			'u': '1',              # dedupe de posts idénticos en servidor
			'safeO': str(self.moderation),
			's1': 'relevance',     # orden primario
			's1d': '-',            # descendente
			'fty[]': 'VIDEO',      # sólo vídeo
		}
		if self.api_version != '3.0':
			# La 3.0 ignora todos los parámetros de tamaño de página.
			params.update({
				'pby': '250',      # tope real de la 2.0
				'fly': '2',        # respuesta JSON
				'sb': '1',
				'st': 'basic',
				'chxu': '1',
				'chxgx': '1',
				'vv': '1',         # metadatos de vídeo (codecs, resolución)
			})
		return params

	def _get(self, query):
		path = SEARCH_V3 if self.api_version == '3.0' else SEARCH_V2
		headers = {'User-Agent': self.user_agent, 'Authorization': self.auth}
		r = requests.get('%s%s' % (BASE_LINK, path), params=self._search_params(query),
						 headers=headers, timeout=self.timeout)
		if r.status_code == 401:
			from resources.lib.jacksparrow import log_utils
			log_utils.log('EASYNEWS: 401 - credenciales inválidas', level=log_utils.LOGWARNING)
			return None
		if r.status_code != 200:
			from resources.lib.jacksparrow import log_utils
			log_utils.log('EASYNEWS: HTTP %s -- %s' % (r.status_code, (r.text or '')[:200]),
						  level=log_utils.LOGWARNING)
			return None
		return r.json()

	@staticmethod
	def _dl_url(item, down_url, dl_farm, dl_port):
		"""Reconstruye la URL de descarga directa.

		Formato: {downURL}/{dlFarm}/{dlPort}/{hash}{ext}/{filename}{ext}
		En el formato antiguo (array) item['0'] ya trae el hash completo con
		su sufijo. En el formato objeto, 'hash' viene pelado y 'id' aporta
		el sufijo de 4 caracteres; hay que concatenarlos.
		"""
		full_hash = item.get('0') or ''
		if not full_hash:
			base_hash = str(item.get('hash') or '')
			sig = item.get('id')
			full_hash = '%s%s' % (base_hash, str(sig) if sig is not None else '')
		if not full_hash:
			return None
		ext = item.get('11') or item.get('ext') or ''
		fn = item.get('10') or item.get('fn') or ''
		if not ext or not fn:
			return None
		return down_url + quote('/%s/%s/%s%s/%s%s' % (dl_farm, dl_port, full_hash, ext, fn, ext))

	@staticmethod
	def _duration_ok(raw):
		"""Descarta samples: menos de 6 minutos fuera."""
		if raw is None:
			return True
		if isinstance(raw, (int, float)):
			return raw >= 360
		raw = str(raw)
		if re.match(r'^\d+s', raw):
			return False
		if re.match(r'^[0-5]m', raw):
			return False
		return True

	def sources(self, data, hostDict):
		sources = []
		if not data:
			return sources
		if not self.auth:
			return sources
		sources_append = sources.append
		from resources.lib.jacksparrow import log_utils
		try:
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title'] if 'tvshowtitle' in data else None
			year = data['year']
			if 'tvshowtitle' in data:
				hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
				query = '%s %s' % (title, hdlr)
			else:
				hdlr = year
				query = '%s %s' % (title, year)
			query = re.sub(r'[^A-Za-z0-9\s\.\-]+', ' ', query)
			if 'timeout' in data:
				self.timeout = int(data['timeout'])

			results = self._get(query)
			if not results:
				return sources
			files = results.get('data') or []
			down_url = results.get('downURL') or ('%s/dl' % BASE_LINK)
			dl_farm = results.get('dlFarm') or 'auto'
			dl_port = results.get('dlPort') or 'auto'
			if not files:
				log_utils.log('EASYNEWS: 0 resultados para "%s"' % query, level=log_utils.LOGDEBUG)
				return sources
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except Exception:
			source_utils.scraper_error('EASYNEWS')
			return sources

		for item in files:
			try:
				if not isinstance(item, dict):
					continue
				# Descartes baratos primero.
				if item.get('type') and str(item.get('type')).upper() != 'VIDEO':
					continue
				if item.get('virus'):
					continue
				if item.get('passwd'):
					continue  # post protegido con contraseña, no reproducible
				ext = item.get('11') or item.get('ext') or ''
				if ext.lower() not in VIDEO_EXT:
					continue
				if not self._duration_ok(item.get('14') or item.get('duration')):
					continue

				fn = item.get('10') or item.get('fn') or ''
				if not fn:
					continue
				name = source_utils.clean_name(fn)
				if not source_utils.check_title(title, aliases, name, hdlr, year):
					continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio):
					continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables):
					continue

				url = self._dl_url(item, down_url, dl_farm, dl_port)
				if not url:
					continue

				# Tamaño y tope de cuota.
				try:
					raw_size = int(item.get('rawSize') or 0)
				except Exception:
					raw_size = 0
				if self.max_size and raw_size and raw_size > (self.max_size * 1073741824):
					continue

				quality, info = source_utils.get_release_quality(name_info, url)
				# Easynews reporta la resolucion real: manda sobre el nombre.
				#
				# v1.0.56: SE MIDE POR ANCHO, no por alto. Una pelicula en
				# 2.39:1 se codifica como 1920x800 (1080p) o 3840x1600 (4K):
				# usando el alto, un 1080p cinematografico caia a "720p" y un
				# 4K a "1080p". El ancho es estable para cada escalon.
				# Solo se pisa el nombre si Easynews da una resolucion creible.
				try:
					xres = int(item.get('xres') or 0)
					yres = int(item.get('yres') or 0)
					if xres >= 3000 or yres >= 2000:
						quality = '4K'
					elif xres >= 1800 or yres >= 1000:
						quality = '1080p'
					elif xres >= 1200 or yres >= 700:
						quality = '720p'
					elif xres > 0 or yres > 0:
						quality = 'SD'
				except Exception:
					pass
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				# Codecs reportados por el propio Easynews.
				vcodec = (item.get('vcodec') or '').upper()
				if vcodec in ('HEVC', 'H265', 'X265') and 'HEVC' not in info:
					info.append('HEVC')
				elif vcodec in ('AV1',) and 'AV1' not in info:
					info.append('AV1')
				acodec = (item.get('acodec') or '').upper()
				if acodec and acodec not in info and acodec in ('EAC3', 'AC3', 'AAC', 'DCA', 'TRUEHD', 'FLAC'):
					info.append(acodec.replace('DCA', 'DTS'))

				dsize = 0
				try:
					size = '%.2f GB' % (float(raw_size) / 1073741824)
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except Exception:
					pass
				info = ' | '.join(info)

				# Idioma de audio reportado por Easynews (alangs / audio_tracks).
				alangs = item.get('audio_tracks') or item.get('alangs') or item.get('alang') or ''
				if isinstance(alangs, list):
					alangs = ','.join([str(x) for x in alangs])

				# v1.0.53: la URL se guarda LIMPIA. La cabecera Basic se añade
				# en resolve(), en el momento de reproducir. Antes se pegaba
				# aquí y acababa en la caché rel_src (repr(sources)), en el log
				# de Kodi y en el menú contextual de descarga: la contraseña
				# del usuario, en base64 reversible, en tres sitios en disco.
				# v1.0.54: source='usenet', NO 'Easynews'. La skin dibuja DOS
				# etiquetas superpuestas cuando source no contiene USENET /
				# TORRENT / DIRECT / LOCAL / CLOUD (source_results.xml linea
				# 735 anade "HOSTER | SCORE" encima de la linea normal). Con
				# 'usenet' solo se pinta una, y ademas los items se agrupan
				# con el resto de usenet en sources.group.sort.
				sources_append({
					'provider': 'easynews', 'source': 'usenet', 'debrid': 'Easynews',
					'seeders': '', 'hash': '', 'name': name, 'name_info': name_info,
					'quality': quality, 'language': 'en', 'url': url, 'info': info,
					'direct': True, 'debridonly': True, 'size': dsize,
					'tracker': 'easynews', 'alangs': alangs,
				})
			except Exception:
				source_utils.scraper_error('EASYNEWS')
		if len(sources) > self.MAX_RESULTS:
			# Los mejores primero: la API ya ordena por relevancia, y dentro
			# de eso preferimos el de mayor calidad/tamano util.
			_rank = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3}
			sources.sort(key=lambda k: (_rank.get(k['quality'], 4), -k.get('size', 0)))
			sources = sources[:self.MAX_RESULTS]
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		return []

	def resolve(self, url):
		"""Adjunta la cabecera Basic justo antes de reproducir.

		Kodi acepta cabeceras HTTP pegadas a la URL con "|". Al hacerlo
		aquí y no en sources(), las credenciales nunca se escriben en la
		caché de fuentes, ni en el log, ni en el item de descarga.
		Idempotente: si la URL ya trae la cabecera, se devuelve tal cual.
		"""
		if not url:
			return None
		if '|Authorization=' in url:
			return url
		if not url.startswith(BASE_LINK):
			# No es un enlace de Easynews: no le pegamos credenciales.
			return url
		auth = self.auth or self._basic_auth()
		if not auth:
			return None
		return '%s|Authorization=%s' % (url, quote(auth))
