# -*- coding: utf-8 -*-
"""
	jacksparrowscrapers Project - MediaFusion scraper (v5+ format)

	MediaFusion v5 API:
	  - secret_str token embedded in URL path
	  - Server does IMDB-based matching - no client-side title check needed
	  - Streams devuelven url (proxy/debrid ya resuelto) O infoHash
	  - Si url es https:// -> direct=True, luc_kodi la reproduce directamente
	  - Si solo hay hash en el path -> magnet, debridonly=True
	  - Hash extraido de URL path: /playback/Provider/<40-hex-hash>
	  - Description format: 'HDR\n BluRay\n 52 GB  68\n English\n Source'
	  - name field: 'MediaFusion | Instance PM PM 2160P'
"""

from json import loads as jsloads
import re
import time
import os
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow import pack_handoff
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow import log_utils


# Etiquetas de origen. La calidad y los tags de codec/HDR ya NO se
# calculan aqui: se delegan en source_utils, igual que en el resto de
# scrapers (v1.0.61).
_SRC_MAP = {
	'bluray remux':  'REMUX',
	'blu-ray remux': 'REMUX',
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

class source:
	timeout = 20
	priority = 2
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.language = ['en']
		try:
			instance_idx = int(getSetting('mediafusion.url') or '0')
		except Exception:
			instance_idx = 0
		_INSTANCES = [
			'https://mediafusionfortheweebs.midnightignite.me',
			'https://mediafusion.elfhosted.com',
		]
		self.base_link  = _INSTANCES[instance_idx] if instance_idx < len(_INSTANCES) else _INSTANCES[0]
		self.secret_str = getSetting('mediafusion.secret') or ''
		self.movieSearch_link = '/stream/movie/%s.json'
		self.tvSearch_link    = '/stream/series/%s:%s:%s.json'
		# Min seeders (v1.0.61: antes estaba fijo a 0 y las ramas de
		# filtrado eran inalcanzables)
		try:
			self.min_seeders = int(getSetting('mediafusion.min.seeders') or '0')
		except Exception:
			self.min_seeders = 0

	# --- URL helpers ----------------------------------------------------------

	def _build_url(self, template, *args):
		endpoint = template % args
		if self.secret_str:
			return '%s/%s%s' % (self.base_link, self.secret_str.strip('/'), endpoint)
		return '%s%s' % (self.base_link, endpoint)

	# --- Fetch ----------------------------------------------------------------

	def _fetch(self, url):
		"""Fetch streams from MediaFusion, paginating to collect all results."""
		# v1.0.66: MediaFusion solo escribia al log dentro de resolve(), asi que
		# en un kodi.log no se distinguia "no encontro nada" de "no llego a correr".
		log_utils.log('MEDIAFUSION: GET %s' % self._mask(url), level=log_utils.LOGINFO)
		all_streams = []
		seen_keys   = set()
		page        = 1

		while True:
			try:
				paged_url = '%s?page=%d' % (url, page) if page > 1 else url
				results   = client.request(paged_url, timeout=self.timeout)
				if not results:
					break
				data    = jsloads(results)
				streams = data.get('streams', [])
				if not streams:
					break

				new_streams = []
				for s in streams:
					url_field   = s.get('url', '')
					# v1.0.19: defensa contra `behaviorHints: null` (no solo
					# campo ausente). s.get('behaviorHints', {}) devuelve None
					# si el campo existe con valor null; usar `or {}` para
					# garantizar que el siguiente .get() no lance AttributeError.
					bh_filename = (s.get('behaviorHints') or {}).get('filename', '')
					m           = re.search(r'/([0-9a-fA-F]{40})', url_field)
					h           = m.group(1) if m else s.get('infoHash', '')
					key         = h or bh_filename
					if key and key not in seen_keys:
						seen_keys.add(key)
						new_streams.append(s)

				if not new_streams:
					break
				all_streams.extend(new_streams)
				if len(streams) < 5 or page >= 10:
					break
				page += 1

			except Exception:
				source_utils.scraper_error('MEDIAFUSION')
				break

		log_utils.log('MEDIAFUSION: parsed %d streams (%d paginas)' % (len(all_streams), page), level=log_utils.LOGINFO)
		return all_streams

	# --- Parse ----------------------------------------------------------------

	def _parse_files(self, files, season=None, pack_mode=False,
			search_series=False, total_seasons=None,
			bypass_filter=False, title=None, aliases=None,
			year=None, imdb=None):
		"""
		Parse MediaFusion v5 stream list.

		Modo de reproduccion por stream:
		  - url_field empieza por https:// -> URL directa pre-resuelta por Debrid
		    -> direct=True, debridonly=False  (luc_kodi la reproduce sin resolver)
		  - solo hash en url_field o campo infoHash -> magnet
		    -> direct=False, debridonly=True  (luc_kodi resuelve con su propio Debrid)

		El title matching se omite: MediaFusion ya filtra por IMDB ID en el servidor.
		El filtro de packs si se aplica en sources_packs.
		"""
		sources = []

		for file in files:
			try:
				url_field   = file.get('url', '')
				# v1.0.19: misma defensa null que en _fetch — vease comentario alli.
				bh_filename = (file.get('behaviorHints') or {}).get('filename', '')
				name_field  = file.get('name', '')
				desc_field  = file.get('description', '')

				# -- 1. URL y modo de reproduccion -----------------------------
				#
				# MediaFusion devuelve urls tipo:
				#   https://mediafusion.elfhosted.com/<secret>/playback/RealDebrid/<hash>/file.mkv
				# Esa URL ya esta autenticada (secret en el path) y es reproducible
				# directamente sin que luc_kodi intervenga con su propio Debrid.
				#
				# Si la url no es http (o esta vacia), intentamos extraer el hash
				# del path para construir un magnet como fallback.

				m        = re.search(r'/([0-9a-fA-F]{40})', url_field)
				hash_val = m.group(1) if m else (file.get('infoHash', '') or '')

				if url_field and url_field.startswith('http'):
					# URL directa pre-resuelta: reproducir sin resolver en luc_kodi
					play_url   = url_field
					is_direct  = True
					debridonly = False
				elif hash_val:
					# Solo hash disponible: luc_kodi gestiona el Debrid
					play_url   = 'magnet:?xt=urn:btih:%s&dn=mediafusion' % hash_val
					is_direct  = False
					debridonly = True
				else:
					continue

				# -- 2. Seeders ------------------------------------------------
				seeders = 0
				try:
					sm = re.search(r'\U0001f465\s*(\d+)', desc_field)
					if sm:
						seeders = int(sm.group(1))
					if self.min_seeders and seeders < self.min_seeders:
						continue
				except Exception:
					pass

				# -- 3. Calidad ------------------------------------------------
				#
				# v1.0.61: se abandona el reglamento propio (_QUAL_MAP) y se
				# pasa por source_utils, igual que los otros veinte proveedores.
				# Motivo: la tabla de sinonimos y la deteccion de badges del
				# addon solo se aplican a lo que sale de get_release_quality()
				# / get_extra_tags(); con mapas propios las filas de MediaFusion
				# se puntuaban en el ranker con otras caracteristicas.
				#
				# MediaFusion suele poner la resolucion y el codec en la
				# DESCRIPCION, no en el nombre de fichero, asi que el termino de
				# busqueda concatena ambos ya normalizados a puntos (que es lo
				# que esperan get_qual y get_extra_tags).
				raw_name = bh_filename
				if not raw_name:
					_dl = [l.strip() for l in desc_field.split('\n') if l.strip()]
					raw_name = _dl[0] if _dl else name_field
				raw_name = re.sub(r'\.(mkv|mp4|avi|ts|m2ts)$', '', raw_name or '', flags=re.IGNORECASE)
				name = source_utils.clean_name(raw_name) or ''

				try:
					_dclean = source_utils.clean_name(desc_field.replace('\n', ' ')) or ''
				except Exception:
					_dclean = ''

				try:
					if title:
						if pack_mode:
							_ni = source_utils.info_from_name(
								name, title, str(year or ''), season=season,
								pack=('show' if search_series else 'season'))
						else:
							_ni = source_utils.info_from_name(name, title, str(year or ''))
					else:
						_ni = '.%s.' % name
				except Exception:
					_ni = '.%s.' % name
				term = ('%s%s.' % (_ni, _dclean)).lower()

				quality, info = source_utils.get_release_quality(term, play_url)
				info = list(info) if info else []

				# -- 4. Info tags (codec, source, HDR) -------------------------
				try:
					for _t in source_utils.get_extra_tags(term):
						if _t not in info:
							info.append(_t)
				except Exception:
					pass
				# Etiquetas de origen (REMUX/BLURAY/WEBDL/HDTV/CAM/SCR): no las
				# cubre get_extra_tags y el nombre de display las usa.
				_low = term
				for _kw, _tag in _SRC_MAP.items():
					if _kw.replace(' ', '.') in _low or _kw in _low:
						if _tag not in info:
							info.append(_tag)

				# -- 5. Tamano -------------------------------------------------
				dsize = 0
				try:
					size_m = re.findall(
						r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))',
						desc_field)
					if size_m:
						dsize, isize = source_utils._size(size_m[0])
						info.insert(0, isize)
				except Exception:
					pass

				# -- 6. Fuente (icono enlace) ----------------------------------
				src_label = ''
				try:
					src_m = re.search(r'\U0001f517\s*(.+)', desc_field)
					if src_m:
						src_label = src_m.group(1).strip()
						if src_label and src_label not in info:
							info.append(src_label)
				except Exception:
					pass

				# -- 7. Etiqueta de proveedor Debrid (solo URLs directas) ------
				# 'debrid' se muestra en luc_kodi.debrid del card (slot SIZE | DEBRID | ...).
				#
				# v1.0.62: se unifica a 'Custom', igual que torz, comet, sootio
				# y meteor. Antes se emitian las abreviaturas RD/AD/TB/PM/... de
				# _MF_PROVIDER_LABELS, que creaban un tercer vocabulario en la
				# misma columna y no coincidian con el nombre canonico que usan
				# los scrapers normales ('Premiumize.me', 'Real-Debrid', ...).
				debrid_key = 'Custom' if is_direct else ''

				info_str = ' | '.join(info)

				# -- 8. Nombre de display --------------------------------------
				_name_tags = [quality]
				for _t in ('HDR10+', 'HDR', 'DV', 'AV1', 'HEVC', 'REMUX', 'BLURAY', 'WEBDL', 'WEBRIP'):
					if _t in info:
						_name_tags.append(_t)
				if src_label:
					_name_tags.append(src_label)
				_synthetic_name = 'MediaFusion ' + ' | '.join(_name_tags)

				if bh_filename:
					_base = os.path.splitext(bh_filename)[0]
					try:
						_base.encode('ascii')
						display_name = _base
					except UnicodeEncodeError:
						if ' / ' in _base:
							_en = _base.split(' / ', 1)[1].strip()
							try:
								_en.encode('ascii')
								display_name = _en
							except UnicodeEncodeError:
								display_name = _synthetic_name
						else:
							display_name = _synthetic_name
				else:
					display_name = _synthetic_name

				# -- 9. Construir item ----------------------------------------
				item = {
					'source':    'torrent',
					'language':  'en',
					'direct':    is_direct,
					'debridonly': debridonly,
					'provider':  'mediafusion',
					'url':       play_url,
					'hash':      hash_val,
					'name':      display_name,
					'name_info': '.%s.' % quality.lower(),
					'quality':   quality,
					'info':      info_str,
					'size':      dsize,
					'seeders':   seeders,
					# v1.0.89: name_info aqui es solo la calidad, asi que el nombre
					# real (sin titulo) viaja aparte para leer los idiomas.
					'lang_name': _ni,
					'lang_hint': source_utils.lang_hint('\n'.join(desc_field.split('\n')[1:])),
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
				source_utils.scraper_error('MEDIAFUSION')

		return sources

	# --- Public API -----------------------------------------------------------

	def sources(self, data, hostDict):
		sources = []
		if not data:
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
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources

		# v1.0.63: ver resources/lib/jacksparrow/pack_handoff.py — la cola por
		# instancia no cruzaba a sources_packs(), que corre en otra instancia.
		_h = pack_handoff.begin('mediafusion', imdb, season, data.get('episode')) if is_episode else None
		files = self._fetch(url)
		pack_handoff.publish(_h, files)
		return self._parse_files(
			files, season=season if is_episode else None,
			title=title, aliases=aliases, year=year, imdb=imdb)

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data:
			return sources
		try:
			title   = data['tvshowtitle']
			aliases = data['aliases']
			imdb    = data['imdb']
			year    = data['year']
			season  = data['season']
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources
		try:
			files = pack_handoff.wait('mediafusion', imdb, season, data.get('episode'), timeout=self.timeout)
			if files is None:
				files = self._fetch(self._build_url(self.tvSearch_link, imdb, season, data.get('episode')))
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources
		return self._parse_files(
			files, season=season, pack_mode=True,
			search_series=search_series, total_seasons=total_seasons,
			bypass_filter=bypass_filter, title=title,
			aliases=aliases, year=year, imdb=imdb)

	# ── Resolucion ──────────────────────────────────────────────────────

	def _mask(self, url):
		"""Enmascara el secret_str en logs para no filtrar credenciales."""
		try:
			if self.secret_str:
				return url.replace(self.secret_str, '<SECRET>')
			return url
		except Exception:
			return '<URL>'

	def resolve(self, url):
		"""
		Resuelve una URL de stream de MediaFusion a un enlace directo.

		El endpoint /playback/<Provider>/<hash>/... responde con un redirect
		302 al CDN del debrid. El secret lleva embebidas las credenciales,
		asi que basta con seguir el redirect: luc_kodi no consulta RD/AD/PM
		directamente.

		Si la URL ya es un archivo directo, se devuelve tal cual.
		"""
		try:
			if not url:
				return None
			lazy_markers = ('/playback/', '/resolve/', '/strem/', '/link/', '/download/')
			if not any(mk in url for mk in lazy_markers):
				return url

			final = client.request(url, output='geturl', redirect=True, timeout=self.timeout)
			# v1.0.67: algunas instancias responden 200 y redirigen a un MP4 de
			# error ("Debrid service is down", "Too many requests"). Devolverlo
			# haria que se reprodujese el video de error en vez de saltar.
			if client.is_error_slate(final):
				# v1.0.68: es transitorio a menudo — el mismo enlace suele resolver
				# unos minutos despues. Se reintenta UNA vez, salvo que el
				# cortafuegos indique que el servicio esta caido de verdad.
				if client.slate_retry_allowed():
					log_utils.log('MEDIAFUSION: video de error, reintentando una vez',
					              level=log_utils.LOGINFO)
					time.sleep(client.SLATE_RETRY_DELAY)
					final = client.request(url, output='geturl', redirect=True, timeout=self.timeout)
				if client.is_error_slate(final):
					client.note_error_slate()
					log_utils.log('MEDIAFUSION: el proveedor sigue devolviendo un video de error, se descarta la fuente',
					              level=log_utils.LOGINFO)
					return None
			if (final and final != url
					and not any(mk in final for mk in lazy_markers)):
				log_utils.log('MEDIAFUSION: resolve() -> %s' % self._mask(final[:90]), level=log_utils.LOGINFO)
				return final

			# Algunos despliegues devuelven el enlace en el cuerpo.
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

			log_utils.log('MEDIAFUSION: resolve() could not resolve %s' % self._mask(url[:90]), level=log_utils.LOGINFO)
			return None
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return None
