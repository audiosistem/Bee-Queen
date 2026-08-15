# -*- coding: utf-8 -*-
"""
	jacksparrowscrapers Project - Newznab scraper (custom Usenet indexer)

	Scraper GENERICO de indexers Newznab. A diferencia de torboxnews.py
	(que usa el buscador INTERNO de TorBox via el proxy AIOStreams), este
	modulo es agnostico al debrid y agnostico al indexer: el usuario aporta
	SU PROPIO indexer Newznab (NZBGeek, DrunkenSlug, NZBFinder, NZBHydra2,
	Prowlarr con endpoint Newznab, o incluso un puente Easynews->Newznab).

	    provider.newznab   -> on/off del scraper (patron estandar del loader)
	    newznab.url        -> URL base del indexer (…/api)   [Setup Wizard]
	    newznab.apikey     -> API key del indexer            [Setup Wizard]
	    newznab.pm_autodelete -> borrar el NZB de la nube tras reproducir
	    newznab.pm_stall_secs -> abandonar si la descarga no avanza (seg.)

	──────────────────────────────────────────────────────────────────────
	SEPARACION DE CAPAS (igual que un tracker torrent tipo Knaben/DMM)
	──────────────────────────────────────────────────────────────────────
	  - CAPA BUSQUEDA (este modulo): consulta la API Newznab y devuelve
	    NZBs. Un NZB es un puntero (lista de Message-IDs de Usenet), NO un
	    stream reproducible. Emitimos items 'source':'usenet' con la URL
	    del .nzb en item['url'] y hash = md5(nzb_url).
	  - CAPA RESOLUCION (debrid): el NZB entra en sources.sourcesResolve(),
	    que lo enruta a Premiumize.resolve_nzb(). Premiumize descarga y
	    reensambla en su nube y devuelve una URL HTTP directa. Sin
	    Premiumize, el NZB es inservible en Kodi.

	v1.0.59: este scraper esta ATADO a Premiumize. Antes se podia elegir
	TorBox, pero esa ruta exige el plan de 10 $/mes de TorBox (Usenet+NNTP
	viene tachado en los planes de 3 $ y 5 $), asi que no aportaba nada
	utilizable para un indexer propio. torboxnews.py sigue usando TorBox:
	es funcionalidad propia de ese servicio y no se toca.

	NO fijamos 'cached_remote': Premiumize no tiene cache-check barato por
	NZB, asi que sources.py presenta todos los items y la resolucion ocurre
	bajo demanda en resolve_nzb() via /transfer/create.

	API Newznab (estandar RSS/XML, soportado por TODOS los indexers; el
	output JSON no es universal):
	  Movie: {base}?t=movie&cat=2000&imdbid=<digits>&apikey=<key>
	  TV:    {base}?t=tvsearch&cat=5000&q=<title>&season=<s>&ep=<e>&apikey=<key>
	  Fallback generico: {base}?t=search&q=<terms>&apikey=<key>
	  NZB:   item/enclosure@url  (o item/link)   -> descarga del .nzb
	         item/newznab:attr[name=size]        -> tamano en bytes
"""

import hashlib
import xml.etree.ElementTree as ET
try:
	from urllib.parse import urlencode, quote_plus
except ImportError:  # Py2 fallback, por si acaso
	from urllib import urlencode, quote_plus

from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting


# Categorias Newznab estandar
_CAT_MOVIE = '2000'
_CAT_TV    = '5000'


def _normalize_newznab_url(raw):
	"""
	Devuelve la URL base del endpoint Newznab lista para inyectar params.

	Acepta lo que el usuario tenga a mano y lo normaliza a '<host>/api':
	  - 'https://indexer.tld'                 -> 'https://indexer.tld/api'
	  - 'https://indexer.tld/'                -> 'https://indexer.tld/api'
	  - 'https://indexer.tld/api'             -> 'https://indexer.tld/api'
	  - 'https://indexer.tld/api?t=caps&...'  -> 'https://indexer.tld/api'
	  - 'https://indexer.tld/newznab/api'     -> 'https://indexer.tld/newznab/api'
	  - pega el manifest/URL con apikey embebida -> se descarta la query

	Si el usuario NO pone esquema, se asume https://.
	"""
	if not raw:
		return ''
	url = raw.strip().strip('"').strip("'")
	if not url:
		return ''
	# Quitar cualquier query string (?t=...&apikey=...); la reconstruimos.
	url = url.split('?', 1)[0].split('#', 1)[0]
	# Esquema por defecto
	if not url.lower().startswith(('http://', 'https://')):
		url = 'https://' + url
	# Quitar slashes finales
	url = url.rstrip('/ \t\n\r')
	if not url:
		return ''
	# Asegurar que termina en /api (endpoint Newznab). Si el path ya
	# incluye '/api' en cualquier posicion (p.ej. /newznab/api) lo dejamos;
	# si no, lo anadimos.
	lower = url.lower()
	if lower.endswith('/api'):
		return url
	if '/api/' in lower or lower.endswith('/api'):
		return url
	return url + '/api'


def _apikey():
	return (getSetting('newznab.apikey') or '').strip()


def _base_url():
	return _normalize_newznab_url(getSetting('newznab.url') or '')


def _build_query(base, params):
	"""Construye la URL final. Los valores SI van url-encoded (los titulos
	llevan espacios/acentos y Newznab lo exige). El apikey se anade al final."""
	pairs = urlencode(params)
	return '%s?%s' % (base, pairs)


def _localname(tag):
	"""Devuelve el nombre local de un tag ElementTree quitando el namespace
	'{http://...}attr' -> 'attr'."""
	return tag.split('}')[-1] if '}' in tag else tag


def _parse_rfc2822(date_str):
	"""Epoch (int) de una fecha RFC-2822 Newznab ('Wed, 02 Oct 2024 13:00:00
	+0000'). Es el formato de <pubDate> y del attr 'usenetdate'. 0 si falla."""
	if not date_str:
		return 0
	try:
		import email.utils as _eut
		tt = _eut.parsedate_tz(date_str.strip())
		if not tt:
			return 0
		return int(_eut.mktime_tz(tt))
	except Exception:
		return 0


def _age_from_epoch(posted_epoch):
	"""(age_days:int, badge:str) desde un epoch de posteo. Salud en Usenet:
	no hay seeders; la edad indica exposicion a takedowns/retencion. Badge
	compacto para la columna info: '14h' / '3d' / '1.2y'. ('', -1) si no hay
	fecha."""
	if not posted_epoch:
		return -1, ''
	try:
		import time as _t
		secs = max(0, int(_t.time()) - int(posted_epoch))
		hours = secs // 3600
		days = secs // 86400
		if hours < 48:
			return int(days), '%dh' % max(hours, 1)
		if days < 365:
			return int(days), '%dd' % days
		return int(days), '%.1fy' % (days / 365.25)
	except Exception:
		return -1, ''


def _parse_newznab_xml(xml_text):
	"""
	Parsea la respuesta RSS/XML de Newznab y devuelve una lista de dicts:
	  {'title':..., 'nzb':..., 'size':int, 'grabs':int, 'guid':...}

	Robusto a namespaces (newznab:attr). Devuelve [] si no parsea.
	"""
	out = []
	if not xml_text:
		return out
	try:
		root = ET.fromstring(xml_text.encode('utf-8') if isinstance(xml_text, str) else xml_text)
	except Exception:
		# Algunos indexers devuelven un <error code=.. description=..>
		return out

	# Buscar todos los <item> sin depender del prefijo de namespace
	for item in root.iter():
		if _localname(item.tag) != 'item':
			continue
		title = ''
		nzb_url = ''
		size = 0
		grabs = 0
		guid = ''
		posted = 0        # epoch de posteo en Usenet (attr usenetdate > pubDate)
		pubdate = 0
		password = False  # release protegido con contrasena -> inservible
		for child in list(item):
			ln = _localname(child.tag)
			if ln == 'title':
				title = (child.text or '').strip()
			elif ln == 'pubDate':
				pubdate = _parse_rfc2822(child.text or '')
			elif ln == 'link' and not nzb_url:
				# link puede ser el .nzb de descarga; enclosure tiene prioridad
				link_txt = (child.text or '').strip()
				if link_txt.lower().startswith('http'):
					nzb_url = link_txt
			elif ln == 'enclosure':
				enc_url = child.attrib.get('url') or ''
				if enc_url.lower().startswith('http'):
					nzb_url = enc_url  # enclosure gana sobre <link>
				try:
					if child.attrib.get('length'):
						size = int(child.attrib.get('length'))
				except Exception:
					pass
			elif ln == 'guid' and not guid:
				guid = (child.text or '').strip()
			elif ln == 'attr':
				name = (child.attrib.get('name') or '').lower()
				val = child.attrib.get('value') or ''
				if name == 'size' and val:
					try: size = int(val)
					except Exception: pass
				elif name == 'grabs' and val:
					try: grabs = int(val)
					except Exception: pass
				elif name == 'usenetdate' and val:
					# Fecha real de posteo en Usenet (mas fiable que pubDate,
					# que en algunos indexers es la fecha de indexacion).
					posted = _parse_rfc2822(val) or posted
				elif name == 'password' and val:
					# '0' = sin password; '1'/'2' = protegido (rar con pass).
					password = val.strip() not in ('', '0')
				elif name == 'guid' and val and not guid:
					guid = val
		if not title or not nzb_url:
			continue
		if not posted:
			posted = pubdate
		out.append({'title': title, 'nzb': nzb_url, 'size': size, 'grabs': grabs,
					'guid': guid, 'posted': posted, 'password': password})
	return out


class source:
	timeout = 20
	priority = 3
	pack_capable = True
	hasMovies = True
	hasEpisodes = True

	def __init__(self):
		self.user_agent = 'luc_kodi for Kodi'
		self.base = _base_url()
		self.key = _apikey()
		self.language = ['en']
		self.min_seeders = -2
		# Etiqueta legible del indexer (host) para la columna 'tracker'
		try:
			host = self.base.split('://', 1)[-1].split('/', 1)[0]
			self.indexer_label = host or 'newznab'
		except Exception:
			self.indexer_label = 'newznab'

	# --- Fetch ---------------------------------------------------------------

	def _fetch(self, params):
		"""Ejecuta una consulta Newznab y devuelve la lista de dicts parseados.
		Enmascara el apikey en el log."""
		if not self.base or not self.key:
			return []
		params = dict(params)
		params['apikey'] = self.key
		url = _build_query(self.base, params)
		from resources.lib.jacksparrow import log_utils
		try:
			masked = url.replace(self.key, '<APIKEY>') if self.key else url
			log_utils.log('NEWZNAB: GET %s' % masked, level=log_utils.LOGDEBUG)
		except Exception:
			pass
		try:
			body = client.request(url, timeout=self.timeout)
			if not body:
				return []
			return _parse_newznab_xml(body)
		except Exception:
			source_utils.scraper_error('NEWZNAB')
			return []

	# --- Item builder --------------------------------------------------------

	@staticmethod
	def _episodes_only():
		"""v1.0.61: descartar packs de temporada/serie en las busquedas de un
		solo episodio.

		Con TORRENTS un pack no molesta: el debrid ya lo tiene cacheado y
		extrae el fichero al momento. Con NZB es al reves: Premiumize tiene
		que DESCARGAR el pack entero de Usenet a su nube antes de darte nada.
		Medido en pruebas reales: un pack de temporada en 2160p son ~113 GB y
		~29 minutos, frente a 2-8 GB de un episodio suelto. Ademas confunde,
		porque en la lista el pack no se distingue a simple vista del episodio.

		Por defecto ACTIVADO. Se desactiva en Providers -> Custom Usenet (NZB).
		"""
		return getSetting('newznab.episodes_only') in ('', 'true')

	def _make_item(self, entry, title, aliases, hdlr, year, imdb,
			episode_title, total_seasons, season, pack_mode,
			undesirables, check_foreign_audio):
		"""Convierte un dict Newznab en un item de luc_kodi (o None si se
		descarta). Mismo contrato que torboxnews.py: source='usenet'."""
		nzb_url = entry.get('nzb') or ''
		file_title = entry.get('title') or ''
		if not nzb_url or not file_title:
			return None
		# Releases con password (attr password != 0) son inservibles para
		# streaming: el debrid no puede extraer el rar. Fuera directamente.
		if entry.get('password'):
			return None
		# hash = md5 del enlace nzb (igual que TorBox check_cache_usenet)
		hash_val = hashlib.md5(nzb_url.encode('utf-8')).hexdigest()
		name = source_utils.clean_name(file_title)

		package, episode_start, episode_end, last_season = None, 0, 0, None

		if pack_mode:
			# En modo pack aplicamos los filtros de temporada/serie completa.
			valid = False
			if total_seasons is not None:
				valid, last_season = source_utils.filter_show_pack(
					title, aliases, imdb, year, season, name, total_seasons)
				if valid:
					package = 'show'
			if not package:
				valid, episode_start, episode_end = source_utils.filter_season_pack(
					title, aliases, year, season, name)
				if not valid:
					return None
				package = 'season'
		else:
			if not source_utils.check_title(title, aliases, name, hdlr, year):
				# El titulo no casa con este episodio concreto. Podria ser un
				# pack que lo contenga; con NZB eso significa bajar la temporada
				# entera, asi que por defecto se descarta.
				if self._episodes_only():
					return None
				# Puede ser un pack que cubra este episodio (single-file season)
				if total_seasons is None:
					return None
				valid, last_season = source_utils.filter_show_pack(
					title, aliases, imdb, year, season, name, total_seasons)
				if not valid:
					valid, episode_start, episode_end = source_utils.filter_season_pack(
						title, aliases, year, season, name)
					if not valid:
						return None
					package = 'season'
				else:
					package = 'show'

		name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
		if source_utils.remove_lang(name_info, check_foreign_audio):
			return None
		if undesirables and source_utils.remove_undesirables(name_info, undesirables):
			return None

		try:
			seeders = int(entry.get('grabs') or 0)
			if self.min_seeders > seeders:
				return None
		except Exception:
			seeders = 0

		quality, info = source_utils.get_release_quality(name_info, nzb_url)
		info = list(info) if info else []
		info += [t for t in source_utils.get_extra_tags(name) if t not in info]
		try:
			size = '%.2f GB' % (float(entry.get('size') or 0) / 1073741824)
			dsize, isize = source_utils._size(size)
			if isize:
				info.insert(0, isize)
		except Exception:
			dsize = 0
		# Salud Usenet: edad del posteo (proxy de retencion/takedowns) como
		# badge compacto justo despues del tamano, p.ej. "4.2 GB | AGE 3d".
		age_days, age_badge = _age_from_epoch(entry.get('posted') or 0)
		if age_badge:
			info.insert(1 if info else 0, 'AGE %s' % age_badge)
		info = ' | '.join(info)

		item = {
			'source': 'usenet', 'language': 'en', 'direct': False, 'debridonly': True,
			'provider': 'newznab', 'hash': hash_val, 'url': nzb_url,
			'name': name, 'name_info': name_info,
			'quality': quality, 'info': info, 'size': dsize, 'seeders': seeders,
			'age_days': age_days,
			'tracker': self.indexer_label,
		}
		if package:
			item['package'] = package
		if package == 'show':
			# v1.0.60 FIX: antes era `if package == 'show' and last_season:`.
			# Cuando filter_show_pack() validaba el pack pero devolvia
			# last_season = 0 o None, el item salia con package='show' pero SIN
			# la clave 'last_season'. sources.py hace entonces
			#   i.get('last_season') >= int(season)
			# -> TypeError: '>=' not supported between NoneType and int,
			# y TODOS los resultados de show-pack del indexer se perdian (el
			# except los tragaba en silencio). Ademas quedaban cacheados en
			# rel_src, asi que el fallo se repetia en cada busqueda posterior.
			# Se replica lo que hace torrentio: la clave se fija SIEMPRE, con
			# total_seasons como respaldo.
			item['last_season'] = last_season or total_seasons or 0
		if episode_start:
			item['episode_start'] = episode_start
			item['episode_end'] = episode_end
		return item

	# --- Public API ----------------------------------------------------------

	def sources(self, data, hostDict):
		sources = []
		if not data:
			return sources
		if not self.base or not self.key:
			from resources.lib.jacksparrow import log_utils
			log_utils.log('NEWZNAB: url/apikey not configured; skipped', level=log_utils.LOGDEBUG)
			return sources
		try:
			is_episode = 'tvshowtitle' in data
			title = data['tvshowtitle'] if is_episode else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			year = data['year']
			imdb = data['imdb']
			imdb_digits = (imdb or '').replace('tt', '')
			episode_title = data['title'] if is_episode else None
			total_seasons = data['total_seasons'] if is_episode else None
			if 'timeout' in data:
				self.timeout = int(data['timeout'])

			if is_episode:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				# Primaria: tvsearch por titulo + temporada/episodio
				entries = self._fetch({
					't': 'tvsearch', 'cat': _CAT_TV,
					'q': title, 'season': str(int(season)), 'ep': str(int(episode)),
				})
				if not entries:
					# Fallback: search generico "titulo SxxExx"
					entries = self._fetch({
						't': 'search', 'cat': _CAT_TV,
						'q': '%s %s' % (title, hdlr),
					})
			else:
				season = None
				hdlr = year
				# Primaria: movie por imdbid (lo mas fiable cuando el indexer lo soporta)
				entries = []
				if imdb_digits:
					entries = self._fetch({
						't': 'movie', 'cat': _CAT_MOVIE, 'imdbid': imdb_digits,
					})
				if not entries:
					# Fallback: search generico "titulo year"
					entries = self._fetch({
						't': 'search', 'cat': _CAT_MOVIE,
						'q': '%s %s' % (title, year),
					})

			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except Exception:
			source_utils.scraper_error('NEWZNAB')
			return sources

		seen = set()
		for entry in entries:
			try:
				h = entry.get('nzb') or ''
				if h in seen:
					continue
				seen.add(h)
				item = self._make_item(
					entry, title, aliases, hdlr, year, imdb, episode_title,
					total_seasons, season, False, undesirables, check_foreign_audio)
				if item:
					sources.append(item)
			except Exception:
				source_utils.scraper_error('NEWZNAB')
		# Salud: mas grabs primero (unico proxy real de que el NZB sigue
		# completo en Usenet). sort estable: empates conservan orden indexer.
		try: sources.sort(key=lambda i: int(i.get('seeders') or 0), reverse=True)
		except Exception: pass
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		# v1.0.61: con 'solo episodios' activo no se buscan packs en absoluto.
		# Ademas de evitar los packs en la lista, ahorra 2-3 consultas al
		# indexer por cada busqueda de serie (las de season-pack y show-pack).
		if self._episodes_only():
			from resources.lib.jacksparrow import log_utils
			log_utils.log('NEWZNAB: pack search skipped (episodes-only mode)', level=log_utils.LOGDEBUG)
			return sources
		if not data:
			return sources
		if not self.base or not self.key:
			return sources
		try:
			title = data['tvshowtitle']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			year = data['year']
			imdb = data['imdb']
			season = data['season']
			hdlr = 'S%02d' % int(season)

			if search_series:
				# Serie completa: buscar por titulo (sin temporada) + "complete"
				entries = self._fetch({
					't': 'search', 'cat': _CAT_TV,
					'q': '%s complete' % title,
				})
				if not entries:
					entries = self._fetch({'t': 'tvsearch', 'cat': _CAT_TV, 'q': title})
			else:
				# Pack de temporada: tvsearch por temporada (sin episodio)
				entries = self._fetch({
					't': 'tvsearch', 'cat': _CAT_TV,
					'q': title, 'season': str(int(season)),
				})
				if not entries:
					entries = self._fetch({
						't': 'search', 'cat': _CAT_TV,
						'q': '%s Season %s' % (title, int(season)),
					})

			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except Exception:
			source_utils.scraper_error('NEWZNAB')
			return sources

		seen = set()
		for entry in entries:
			try:
				h = entry.get('nzb') or ''
				if h in seen:
					continue
				seen.add(h)
				item = self._make_item(
					entry, title, aliases, hdlr, year, imdb, None,
					total_seasons, season, True, undesirables, check_foreign_audio)
				if item:
					sources.append(item)
			except Exception:
				source_utils.scraper_error('NEWZNAB')
		# Salud: mas grabs primero (mismo criterio que sources()).
		try: sources.sort(key=lambda i: int(i.get('seeders') or 0), reverse=True)
		except Exception: pass
		return sources


# -----------------------------------------------------------------------------
# Helper de test para el Setup Wizard (no lo usa el pipeline de scraping)
# -----------------------------------------------------------------------------

def _as_text(body):
	"""Normaliza la respuesta de client.request a str, venga en bytes o str.
	(client.request puede devolver cualquiera de los dos segun el indexer; si
	no se normaliza, '<x' in body revienta con TypeError sobre bytes.)"""
	if body is None:
		return ''
	if isinstance(body, bytes):
		try:
			return body.decode('utf-8', 'replace')
		except Exception:
			return body.decode('latin-1', 'replace')
	return body


def _looks_like_newznab(text):
	"""True si el cuerpo parece una respuesta Newznab valida (caps o feed)."""
	low = text.lower()
	return any(tag in low for tag in (
		'<caps', '<server', '<categories', '<rss', '<channel',
		'<item', 'newznab:response', '<?xml'))


def _newznab_error(text):
	"""Si el cuerpo es un <error .../> de Newznab, devuelve su descripcion;
	si no, None."""
	low = text.lower()
	if '<error' not in low:
		return None
	try:
		root = ET.fromstring(text.encode('utf-8') if isinstance(text, str) else text)
		return root.attrib.get('description') or 'Indexer returned an error.'
	except Exception:
		# Sacar la descripcion a mano si el XML no parsea limpio
		import re as _re
		m = _re.search(r'description="([^"]+)"', text)
		return m.group(1) if m else 'Indexer returned an error (bad API key or URL).'


def test_indexer(base_url, apikey):
	"""
	Comprueba credenciales contra el indexer. Primero t=caps; si la respuesta
	no es concluyente, hace una busqueda real t=search como segundo sondeo.
	Devuelve (ok:bool, msg:str). Usado por newznab_wizard.

	Robusto a: respuestas en bytes, <error> mal formados, y endpoints que
	restringen t=caps pero si permiten t=search.
	"""
	base = _normalize_newznab_url(base_url)
	key = (apikey or '').strip()
	if not base:
		return False, 'Empty indexer URL.'
	if not key:
		return False, 'Empty API key.'
	host = base.split('://', 1)[-1].split('/', 1)[0]

	def _probe(params):
		url = _build_query(base, params)
		try:
			return _as_text(client.request(url, timeout=15)), None
		except Exception as e:
			return None, str(e)

	# 1) t=caps
	body, err = _probe({'t': 'caps', 'apikey': key})
	if body is not None:
		desc = _newznab_error(body)
		if desc:
			return False, desc  # error explicito (p.ej. API key incorrecta)
		if _looks_like_newznab(body):
			return True, 'Indexer OK (%s).' % host

	# 2) Fallback: busqueda real (algunos endpoints limitan caps)
	body2, err2 = _probe({'t': 'search', 'q': 'a', 'apikey': key})
	if body2 is not None:
		desc = _newznab_error(body2)
		if desc:
			return False, desc
		if _looks_like_newznab(body2):
			return True, 'Indexer OK (%s).' % host

	# Sin exito: diagnostico util
	if body is None and body2 is None:
		return False, 'Could not reach the indexer (network error: %s).' % (err or err2 or 'unknown')
	snippet = (body or body2 or '').strip().replace('\n', ' ')[:120]
	if not snippet:
		return False, 'Empty response from indexer (check the URL host).'
	return False, 'Unexpected response (is this a Newznab /api endpoint?). Got: %s' % snippet
