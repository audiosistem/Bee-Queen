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
import queue
import os
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting


# Quality keywords in MediaFusion name / description
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

# Mapeo de proveedor Debrid en path de MediaFusion -> etiqueta visual
_MF_PROVIDER_LABELS = {
	'realdebrid':  'RD',
	'alldebrid':   'AD',
	'torbox':      'TB',
	'premiumize':  'PM',
	'debridlink':  'DL',
	'offcloud':    'OC',
	'pikpak':      'PP',
}


def _parse_quality(name_str, desc_str):
	"""Extract quality string from MediaFusion name + description."""
	combined = (name_str + ' ' + desc_str).lower()
	for kw, q in _QUAL_MAP:
		if kw in combined:
			return q
	return 'SD'


def _parse_info_tags(desc_str):
	"""Extract codec/source/HDR tags from MediaFusion description."""
	tags = []
	d = desc_str.lower()
	for kw, tag in _CODEC_MAP.items():
		if kw in d and tag not in tags:
			tags.append(tag)
	for kw, tag in _SRC_MAP.items():
		if kw in d and tag not in tags:
			tags.append(tag)
	return tags


def _provider_label_from_url(url_str):
	"""
	Try to extract the Debrid provider from a MediaFusion playback URL.
	URLs look like: /playback/RealDebrid/<hash>/... or /playback/TorBox/<hash>/...
	Returns a short label like 'RD', 'TB', or '' if not recognized.
	"""
	m = re.search(r'/playback/([^/]+)/', url_str, re.IGNORECASE)
	if not m:
		return ''
	provider_raw = m.group(1).lower().replace('-', '').replace('_', '')
	# Solo devolver label si reconocemos el proveedor; '' activa fallback 'Custom'
	return _MF_PROVIDER_LABELS.get(provider_raw, '')


class source:
	timeout = 20
	priority = 2
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self._queue  = queue.SimpleQueue()
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
				quality = _parse_quality(name_field, desc_field)

				# -- 4. Info tags (codec, source, HDR) -------------------------
				info = _parse_info_tags(desc_field)

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
				debrid_key = ''
				if is_direct:
					prov_label = _provider_label_from_url(url_field)
					if prov_label:
						debrid_key = prov_label
					else:
						debrid_key = 'Custom'

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

		files = self._fetch(url)
		try:
			self._queue.put_nowait(files)
		except Exception:
			pass
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
			files = self._queue.get(timeout=self.timeout + 1)
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources
		return self._parse_files(
			files, season=season, pack_mode=True,
			search_series=search_series, total_seasons=total_seasons,
			bypass_filter=bypass_filter, title=title,
			aliases=aliases, year=year, imdb=imdb)
