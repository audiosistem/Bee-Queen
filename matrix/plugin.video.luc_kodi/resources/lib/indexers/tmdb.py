# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from resources.lib.modules import app_keys
from datetime import datetime
from time import time
import re
import requests
from requests.adapters import HTTPAdapter
from threading import Thread, Semaphore
from urllib3.util.retry import Retry
from resources.lib.database import cache, metacache, fanarttv_cache
from resources.lib.indexers.fanarttv import FanartTv
from resources.lib.modules.control import setting as getSetting, notification, sleep, apiLanguage, mpaCountry, trailer as control_trailer, yesnoDialog

base_link = "https://api.themoviedb.org/3/"
image_path = "https://image.tmdb.org/t/p/%s"
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
session.mount('https://api.themoviedb.org', HTTPAdapter(max_retries=retries, pool_maxsize=100))

# v1.0.80 — Tope de peticiones de meta en vuelo cuando una lista se pide desde
# un MENÚ o un WIDGET (el precache pasa su propio semáforo global). Antes cada
# lista lanzaba un hilo por título SIN tope: 20 descargas simultáneas de detalle
# TMDb compitiendo por sockets y CPU en la Shield. El número total de peticiones
# no cambia; solo deja de dispararse todo a la vez.
LIST_MAX_WORKERS = 10

# ─────────────────────────────────────────────────────────────────────────────
# v1.0.80 — Logos de plataformas de Movies > Streaming, dentro del add-on
#
# Vivían en postimg.cc: alojamiento gratuito de imágenes, sin edge garantizado,
# con throttling de hotlinking y con los ficheros ORIGINALES sin redimensionar
# (PNG de MB para pintar un logo de 300 px). Eso era lo que hacía lento el
# primer pintado del menú y de los widgets construidos sobre él.
#
# Ahora se sirven de resources/media/<tema>/logos/: cero red, cero dependencia
# de terceros, y funcionan sin internet. La tabla curada conserva la URL
# antigua como respaldo, así que una plataforma que todavía no tenga su PNG
# local sigue pintándose como hasta ahora — basta con dejar el fichero en la
# carpeta con el nombre que devuelve logo_slug() para que pase a ser local.
#
# Las cadenas de TV shows > Networks se quedan como estaban (remotas): son
# muchas más y pesan poco.
# ─────────────────────────────────────────────────────────────────────────────
LOGO_FOLDER = 'logos'
_local_logos_session = None


def logo_slug(name):
	"""Nombre visible -> nombre de fichero. El '+' de las marcas se escribe
	'plus' para que 'AMC+' y 'AMC' (o 'Apple TV+' y 'Apple TV') no colisionen en
	el mismo fichero."""
	try:
		name = str(name).lower().replace('+', ' plus ')
		return re.sub(r'[^a-z0-9]+', '-', name).strip('-')
	except Exception: return ''


def _local_logos():
	"""Ficheros presentes en la carpeta de logos. Un solo listdir por sesión
	(el módulo sobrevive entre invocaciones con reuselanguageinvoker)."""
	global _local_logos_session
	if _local_logos_session is not None: return _local_logos_session
	try:
		from os import listdir
		from resources.lib.modules.control import artPath, joinPath
		_local_logos_session = set(listdir(joinPath(artPath(), LOGO_FOLDER)))
	except Exception:
		_local_logos_session = set()
	return _local_logos_session


# v1.0.96 — Misma marca con otro nombre en otro menu: usa el logo que ya
# lleva el add-on en la carpeta logos.
LOGO_ALIASES = {
	'Peacock': 'Peacock Premium',      # Networks -> logo de Streaming
	'AMC': 'AMC+',                     # Networks (AMC y AMC+) -> logo de Streaming
	'Amazon': 'Amazon Prime Video',    # Originals -> logo de Streaming
}


def local_logo(name, fallback):
	"""Ruta RELATIVA a artPath si el logo está incluido en el add-on; si no, la
	URL de respaldo. addDirectory() ya distingue las dos: lo que no empieza por
	'http' lo une a artPath."""
	try:
		for candidate in (name, LOGO_ALIASES.get(name)):
			if not candidate: continue
			filename = '%s.png' % logo_slug(candidate)
			if filename in _local_logos():
				from resources.lib.modules.control import joinPath
				return joinPath(LOGO_FOLDER, filename)
	except Exception: pass
	return fallback


# v1.0.94 — TV Shows > Networks: 29 cadenas elegidas con la herramienta Tools >
# Test TV networks (25-sep-2026). De 105 entradas, 14 no emitían nada desde
# hacía dos años y 55 tenían menos de cinco series activas con público.
# Criterio: series en activo con al menos 50 votos en TMDb, que es lo que está
# indexado y cacheado en los debrid. Los canales renombrados se unen con "|"
# para no perder su catálogo antiguo. Fuera los que inflaban la cuenta con
# lucha libre o realities (USA, Syfy, Spike, Bravo, MTV, VH1) y las
# plataformas españolas (Movistar Plus+, Atresplayer): probadas en la tablet
# de Lucian, ya con el IMDb resuelto y los descartes contados, sus series no
# dan fuentes reproducibles (enlaces vacíos, doblajes a otros idiomas o un
# XviD HDTV antiguo).
NETWORKS = (
	# Streaming
	('Netflix', '213', 'https://i.postimg.cc/c4vHp9wV/netflix.png'),
	('Prime Video', '1024', 'logos/amazon-prime-video.png'),
	('Apple TV+', '2552', 'https://i.imgur.com/fAQMVNp.png'),
	('Disney+', '2739', 'https://i.postimg.cc/zBNHHbKZ/disney.png'),
	('Hulu', '453', 'https://i.imgur.com/cLVo7NH.png'),
	('HBO', '49', 'https://i.imgur.com/Hyu8ZGq.png'),
	('HBO Max', '3186|6783|8304', 'https://i.postimg.cc/pLdCcdGt/hbo-max.png'),  # HBO Max (2020), Max (2023) y HBO Max otra vez (2025): tres networks en TMDb
	('Paramount+', '4330|1709', 'logos/paramount-plus.png'),  # con CBS All Access, su nombre hasta 2021
	('Peacock', '3353', 'https://i.postimg.cc/76m4v7VW/NBCUniversal-Peacock-Logo.png'),
	('Starz', '318', 'https://i.imgur.com/Z0ep2Ru.png'),
	('MGM+', '6219|922', 'logos/mgm-plus.png'),  # con Epix, su nombre hasta 2023
	('Showtime', '67', 'https://i.imgur.com/SawAYkO.png'),  # poco estreno ya, pero su catalogo (Dexter, Homeland, Billions) sigue siendo de lo mas buscado
	# Cadenas de EE. UU.
	('ABC', '2', 'logos/abc.png'),
	('CBS', '16', 'https://i.imgur.com/8OT8igR.png'),
	('NBC', '6', 'https://i.imgur.com/yPRirQZ.png'),
	('FOX', '19', 'https://i.imgur.com/6vc0Iov.png'),
	('The CW', '71', 'https://i.imgur.com/Q8tooeM.png'),
	('FX', '88', 'https://i.imgur.com/aQc1AIZ.png'),
	('AMC', '174|4661', 'https://i.imgur.com/ndorJxi.png'),  # con AMC+
	('Adult Swim', '80', 'https://i.imgur.com/jCqbRcS.png'),
	('Paramount Network', '2076', 'https://i.postimg.cc/fL9YCz5R/paramount-network.png'),
	('History Channel', '65', 'https://i.imgur.com/LEMgy6n.png'),
	('Cartoon Network', '56', 'https://i.imgur.com/zmOLbbI.png'),
	# Reino Unido
	('BBC One', '4', 'https://i.imgur.com/u8x26te.png'),
	('BBC Two', '332', 'https://i.imgur.com/SKeGH1a.png'),
	('ITV', '9', 'https://i.imgur.com/5Hxp5eA.png'),
	('Channel 4', '26', 'https://i.imgur.com/6ZA9UHR.png'),
	('Sky Atlantic', '1063', 'https://i.imgur.com/9u6M0ef.png'),
	# Anime
	('AT-X', '173', 'https://i.imgur.com/JshJYGN.png'),  # donde TMDb pone el anime de temporada (Re:ZERO, Classroom of the Elite)
)


# v1.0.96 — Platforms of Movies > Streaming left out of TV Shows > Streaming
# because their catalog is films only.
WATCHPROVIDERS_FILM_ONLY = ('MUBI', 'TCM')


def canonical_network_ids(saved):
	"""Ids guardados (p. ej. la seleccion del precache) -> ids de la lista actual.
	Un id viejo suelto ('3186', '922') se lleva a la entrada que ahora lo une
	('3186|6783|8304', '6219|922'); lo que ya no esta en la lista se descarta."""
	out = []
	for raw in saved or []:
		parts = set(str(raw).split('|'))
		for _name, nid, _logo in NETWORKS:
			if parts & set(nid.split('|')):
				if nid not in out: out.append(nid)
				break
	return out


class TMDb:
	def __init__(self):
		self.API_key = getSetting('tmdb.api.key')
		if not self.API_key: self.API_key = app_keys.get('tmdb')
		self.set_resolutions()
		self.lang = apiLanguage()['tmdb']
		self.mpa_country = mpaCountry()
		self.enable_fanarttv = getSetting('enable.fanarttv') == 'true'
		self.prefer_en_titles = getSetting('title.lang.en') == 'true'
		self.art_lang = 'en' if self.prefer_en_titles else self.lang # orientación única para pósters/logos/poster3

	def get_request(self, url):
		try:
			try: response = session.get(url, timeout=20)
			except requests.exceptions.SSLError:
				response = session.get(url, timeout=20)
		except requests.exceptions.ConnectionError:
			notification(message=32024)
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			if response.status_code in (200, 201): return response.json()
			elif response.status_code == 404:
				if getSetting('debug.level') == '1':
					from resources.lib.modules import log_utils
					log_utils.log('TMDb get_request() failed: (404:NOT FOUND) - URL: %s' % url, level=log_utils.LOGDEBUG)
				return '404:NOT FOUND'
			elif 'Retry-After' in response.headers: # API REQUESTS ARE BEING THROTTLED, INTRODUCE WAIT TIME (TMDb removed rate-limit on 12-6-20)
				throttleTime = response.headers['Retry-After']
				notification(message='TMDb Throttling Applied, Sleeping for %s seconds' % throttleTime)
				sleep((int(throttleTime) + 1) * 1000)
				return self.get_request(url)
			else:
				if getSetting('debug.level') == '1':
					from resources.lib.modules import log_utils
					log_utils.log('TMDb get_request() failed: URL: %s\n                       msg : TMDB Response: %s' % (url, response.text), __name__, log_utils.LOGDEBUG)
				return None
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None

	def userlists(self, url):
		try:
			result = self.get_request(url % self.API_key)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
			next = '' ; list = []
		except: return
		try: # This is actually wrong but may not be used so look into 
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			media_type = item.get('list_type')
			name = item.get('name')
			list_id =  item.get('id')
			url = 'https://api.themoviedb.org/4/list/%s?api_key=%s&sort_by=%s&page=1' % (list_id, self.API_key, self.tmdb_sort())
			item = {'media_type': media_type, 'name': name, 'list_id': list_id, 'url': url, 'context': url, 'next': next}
			list.append(item)
		return list

	def popular_people(self):
		url = '%s%s' % (base_link, 'person/popular?api_key=%s&language=en-US&page=1' % self.API_key)
		item = self.get_request(url)
		return item

	def tmdb_sort(self):
		sort = int(getSetting('sort.movies.type'))
		tmdbSort = 'original_order'
		if sort == 1: tmdbSort = 'title'
		if sort in (2, 3): tmdbSort = 'vote_average'
		if sort in (4, 5, 6): tmdbSort = 'release_date' # primary_release_date
		tmdb_sort_order = '.asc' if int(getSetting('sort.movies.order')) == 0 else '.desc'
		sort_string = tmdbSort + tmdb_sort_order
		return sort_string

	def set_resolutions(self):
		# v1.0.72 — toda la decision vive en resolve_sizes(), que evita
		# despertar al detector de pantalla cuando el tope de cacheo ya
		# determina el resultado. Ver el bloque largo mas abajo.
		resolutions = resolve_sizes()
		self.poster_path  = image_path % resolutions['poster']
		self.fanart_path  = image_path % resolutions['fanart']
		self.still_path   = image_path % resolutions['still']
		self.profile_path = image_path % resolutions['profile']

# poster_path = 'w342', fanart_path = 'w1280', still_path = 'w500', profile_path = 'w185'

# Tamaños de imagen de TMDb por nivel. A nivel de MODULO a proposito: display_test
# necesita saber que va a hacer set_resolutions() sin instanciar la clase ni
# duplicar la tabla. Si el test calculara esto por su cuenta podria decir una
# cosa y los menus hacer otra, y entonces el test no valdria para nada.
#
# v1.0.72 — corregidos tres tamaños que no existen. TMDb publica una lista
# DISTINTA por tipo de imagen en /3/configuration, y la tabla mezclaba las de
# poster con las demas: 'w500' y 'w780' no son tamaños de still (solo hay w92,
# w185, w300 y original) y 'w342' no es de profile (w45, w185, h632, original).
# Hoy el CDN los sirve igualmente, pero son rutas no documentadas que TMDb
# advierte que pueden dejar de existir sin aviso, y no hay razon para depender
# de ellas cuando la lista buena cuesta lo mismo.
# v1.0.72 — corregidos los stills de los niveles fijos. La v1.0.72 quito de
# aqui 'w500' y 'w780' por no estar en la lista de TMDb para stills, lo cual
# era correcto, pero los sustituyo por el escalon inmediato hacia abajo y eso
# dejo los tres niveles PEOR de lo que estaban. Medido contra la tarjeta de
# episodio, que en 4K mide 640x360: High servia un still que cubria la ranura y
# paso a servir uno que se amplia al doble.
#
# El problema de fondo es que TMDb no publica ningun still entre w300 (300x169)
# y original, que para stills arranca en 1280x720. No hay termino medio que
# elegir: o se amplia mucho, o se sirve entero. Asi que High y Original van a
# 'original', que es lo unico que cubre la ranura, y Low y Medium se quedan en
# w300, que es el mayor con nombre y es coherente con lo que esos niveles
# prometen: gastar poco.
IMAGE_LEVELS = (
	{'poster': 'w185', 'fanart': 'w300',  'still': 'w300', 'profile': 'w45'},
	{'poster': 'w342', 'fanart': 'w780',  'still': 'w300', 'profile': 'w185'},
	{'poster': 'w780', 'fanart': 'w1280', 'still': 'original', 'profile': 'h632'},
	{'poster': 'original', 'fanart': 'original', 'still': 'original', 'profile': 'original'},
)

AUTO_LEVEL = 4

# ─────────────────────────────────────────────────────────────────────────────
#  v1.0.82 — el ajuste visible pasa a ser DOS PERFILES y AUTO desaparece de el
#
#  AUTO calculaba bien pero era una maquina invisible: elegia el tamaño mas
#  pequeño de TMDb que llena <imageres>, un numero enterrado en un fichero que
#  casi nadie ha abierto nunca. El resultado era que dos aparatos con la misma
#  pantalla pedian cosas distintas sin que su dueño supiera por que, y que un
#  tope que no coincide con ningun escalon de TMDb obligaba a AUTO a saltar al
#  original: con <imageres>1752</imageres>, w780 mide 1170 y no llena el tope,
#  asi que se bajaba un JPEG de 2000x3000 —un mega— para guardar 300 KB.
#
#  Ahora el usuario elige entre dos perfiles y ninguno mira la pantalla:
#
#    ESTANDAR  posters w500 o w780 (lo elige el)   fanart w1280   stills w300
#    MAXIMA    todo original
#
#  Que no miren la pantalla es deliberado. El 1080i/2160p que lleva el addon
#  son sus juegos de XML propios y su umbral es 2160 de alto, asi que no dicen
#  nada sobre lo que el panel puede dibujar: una tablet a 2800x1752 usa el
#  juego de 1080 y sin embargo dibuja posters de 1752 px. Atar la calidad a esa
#  clasificacion prometeria una correspondencia que no existe —es el mismo
#  error por el que Low, Medium y High salieron de la lista dos veces—. El que
#  tiene una tele 4K y quiere Estandar hace bien si le basta; el que quiere el
#  maximo lo pide y ya.
#
#  El tope de cacheo NO desaparece: sigue leyendose, pero solo para AVISAR en
#  el test de pantalla cuando contradice al perfil elegido. Eso es lo que AUTO
#  hacia por dentro y en silencio, y sacarlo a la luz vale mas que resolverlo
#  a espaldas del usuario.
#
#  Por que w500 de fabrica y no w780: Kodi reescala al guardar con tope en
#  <imageres>, que sin advancedsettings.xml son 720 px. Un w500 mide 750 y cae
#  practicamente clavado; un w780 mide 1170 y se guardaria encogido, tirando
#  mas de la mitad de lo descargado. El que sube el tope sube tambien el
#  poster, y el test se lo dice.
# ─────────────────────────────────────────────────────────────────────────────
STANDARD_LEVEL = 5

# Los tres tamaños elegibles dentro del perfil Estandar.
#
# Cada lista son los dos extremos utiles de lo que TMDb publica para ese tipo:
#
#   poster   w92 w154 w185 w342 w500 w780 original   -> w500 / w780
#   fanart   w300 w780 w1280 original                -> w1280 / original
#   still    w92 w185 w300 original                  -> w300 / original
#
# En fanart y en stills NO hay escalon intermedio: despues de w1280 (1280x720)
# y de w300 (300x169) viene directamente el original. Que no haya termino medio
# no quita que la eleccion sea real —w1280 y original son dos cosas muy
# distintas en pantalla y en disco—, asi que se ofrecen las dos y decide el
# usuario. En posters si hay escalera, y se ofrecen los dos que tienen sentido
# en una pantalla moderna; por debajo de w500 la imagen se amplia y por encima
# de w780 solo queda el original, que ya es el perfil Maxima.
POSTER_SIZE_SETTING = 'tmdb.posterSize'
FANART_SIZE_SETTING = 'tmdb.fanartSize'
STILL_SIZE_SETTING = 'tmdb.stillSize'
_POSTER_CHOICES = ('w500', 'w780')
_FANART_CHOICES = ('w1280', 'original')
_STILL_CHOICES = ('w300', 'original')


def _standard_pick(setting_id, choices):
	"""Opcion elegida, tolerante a COMO la guarde Kodi.

	v1.0.82 — corregido tras verlo fallar en un aparato real. Un `type="enum"`
	con `values="w500|w780"` no guarda siempre el indice: segun la plataforma y
	la version, en el settings.xml de userdata puede acabar el literal ('w780').
	getSetting() devuelve ese texto tal cual —lee el XML de userdata, no
	xbmcaddon— asi que int('w780') reventaba y las TRES opciones caian a su
	valor conservador en silencio: el usuario veia w780 en los ajustes y el
	addon seguia pidiendo w500.

	Ahora se aceptan las dos formas. Primero el literal, que es inequivoco, y
	solo despues el indice.
	"""
	raw = (getSetting(setting_id) or '').strip()
	if raw in choices: return raw
	try:
		index = int(raw)
	except Exception:
		return choices[0]
	# El indice tiene que ser positivo. En Python choices[-1] es valido y
	# devuelve el ULTIMO elemento, asi que un ajuste corrupto con un numero
	# negativo seleccionaria en silencio la opcion mas cara —justo lo contrario
	# de lo que debe hacer una red de seguridad.
	if 0 <= index < len(choices): return choices[index]
	return choices[0]


# ─────────────────────────────────────────────────────────────────────────────
#  v1.0.82 — dos funciones que se llamaban pero NO EXISTIAN
#
#  pyflakes las destapo: `_poster_list` y `_english_title` se invocaban en
#  cuatro sitios y no estaban definidas en ningun fichero del addon. Las dos de
#  `_poster_list` viven dentro de un `try/except: pass`, asi que fallaban en
#  silencio y la rotacion de posters alternativos no ha funcionado nunca —
#  poster_rotator.rotate() nunca recibia 'posters_all' con dos entradas—. Las de
#  `_english_title` no estaban protegidas y reventaban el parseo de la ficha al
#  activar "preferir titulos en ingles" con el idioma en otra cosa.
#
#  Ambas trabajan sobre datos que YA vienen en la respuesta: movie_link y
#  show_link piden append_to_response=...,alternative_titles,images con
#  include_image_language=<lang>,en,null. No hay ni una peticion HTTP de mas.
# ─────────────────────────────────────────────────────────────────────────────
def _poster_list(images, art_lang, poster_path):
	"""URLs completas de los posters alternativos, en orden de preferencia.

	Primero los del idioma de arte pedido y despues los SIN idioma (los que no
	llevan texto encima), y dentro de cada grupo por valoracion. Es el mismo
	criterio que parse_art() usa para elegir uno solo, extendido a la lista
	entera para que la rotacion tenga de donde tirar.
	"""
	if not images: return []
	def _rank(x):
		try: return -float(x.get('vote_average') or 0)
		except Exception: return 0.0
	try:
		same = sorted([i for i in images if i.get('iso_639_1') == art_lang], key=_rank)
		none = sorted([i for i in images if i.get('iso_639_1') in (None, '', 'null')], key=_rank)
		out, seen = [], set()
		for item in same + none:
			path = item.get('file_path')
			if path and path not in seen:
				seen.add(path)
				out.append('%s%s' % (poster_path, path))
		return out
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return []


def _english_title(result, kind):
	"""Titulo en ingles, o '' si no se puede determinar con seguridad.

	Dos vias, en este orden:
	  1. Si el idioma ORIGINAL ya es ingles, el titulo original ES el ingles.
	     Es la via fiable y cubre la mayoria de los casos.
	  2. Si no, se busca en alternative_titles. Ahi TMDb indexa por PAIS, no por
	     idioma, asi que se aceptan solo US y GB, y se descartan las entradas con
	     `type` (titulo de trabajo, titulo de DVD, relanzamiento...), que no son
	     el titulo por el que se conoce la pelicula.

	Nunca inventa: si ninguna via da algo, devuelve '' y el llamante se queda
	con el titulo que ya tenia.
	"""
	try:
		if (result.get('original_language') or '').lower() == 'en':
			original = result.get('original_title') if kind == 'movie' else result.get('original_name')
			if original: return original
		block = result.get('alternative_titles') or {}
		# TMDb llama 'titles' al bloque de peliculas y 'results' al de series.
		items = block.get('titles') if kind == 'movie' else block.get('results')
		if not items: return ''
		for country in ('US', 'GB'):
			for item in items:
				if item.get('iso_3166_1') != country: continue
				if (item.get('type') or '').strip(): continue
				title = (item.get('title') or '').strip()
				if title: return title
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	return ''


def standard_poster():
	"""Tamaño de poster del perfil Estandar. Por defecto w500, que es el que casa
	con el tope de cacheo por defecto de Kodi (720 px)."""
	return _standard_pick(POSTER_SIZE_SETTING, _POSTER_CHOICES)


def standard_fanart():
	return _standard_pick(FANART_SIZE_SETTING, _FANART_CHOICES)


def standard_still():
	return _standard_pick(STILL_SIZE_SETTING, _STILL_CHOICES)


def standard_sizes():
	"""Los cuatro tamaños del perfil Estandar. El de perfil (actores) no se
	ofrece: w185 cubre cualquier ranura donde el addon dibuja una cara."""
	return {'poster': standard_poster(), 'fanart': standard_fanart(),
			'still': standard_still(), 'profile': 'w185'}

# Indice de 'Original' dentro de IMAGE_LEVELS. Se nombra porque a partir de la
# v1.0.72 el ajuste visible solo ofrece Auto y Original, y ese numero aparece
# en la migracion.
ORIGINAL_LEVEL = 3

# v1.0.74 — el ajuste visible queda en DOS opciones y ahi se queda: Auto y
# Original.
#
# Low, Medium y High vuelven a salir de la interfaz, esta vez con la regla que
# les faltaba a las dos veces anteriores. No son una eleccion de calidad: son
# tres tamaños fijos que no miran ni la pantalla ni el tope de cacheo, asi que
# subir el tope no les hace absolutamente nada —un poster w780 mide 1170 px de
# alto en una tele 4K igual que en una de 1080— y el propio test de pantalla
# acababa ofreciendo a quien los tuviera una mejora que no podia darle. Lo que
# el usuario quiere decidir es OTRA cosa: si le basta lo que su panel puede
# dibujar (Auto) o si quiere el maximo pase lo que pase (Original). Eso son dos
# opciones, no cinco.
#
# IMAGE_LEVELS se conserva entera porque una instalacion sin migrar puede tener
# guardado cualquiera de los cinco indices viejos y hay que seguir sabiendo
# interpretarlo mientras tanto.
#
# POR QUE UN ID NUEVO. El ajuste viejo es un enum, y Kodi guarda el INDICE, no
# el nombre. Recortar la lista renumeraria todo: quien tuviera Auto (4) se
# despertaria con otra cosa, y un 0 guardado seria indistinguible de un 0
# nuevo. Con un id nuevo esa ambiguedad no existe.
IMAGE_SETTING = 'tmdb.imageQuality'
LEGACY_IMAGE_SETTING = 'tmdb.imageResolutions'

# Valores del ajuste NUEVO, en el orden en que aparecen en settings.xml.
# El 0 y el 1 NO se mueven nunca: son los que ya hay escritos en disco.
_CHOICE_AUTO = 0
_CHOICE_ORIGINAL = 1

# Traduccion de la eleccion visible al indice de IMAGE_LEVELS.
#
# v1.0.74 — los indices 2, 3 y 4 del ajuste nuevo ya no existen. Una
# instalacion que los tuviera escritos (los tuvo la 1.0.73) cae a Auto por el
# .get() de _read_image_level(), y ademas se limpia una sola vez desde
# service.py para que Kodi no siga avisando de un valor obsoleto en cada
# arranque.
# v1.0.82 — el 0 deja de ser Auto y pasa a ser Estandar. El indice no se toca a
# proposito: una instalacion con Auto guardado despierta en Estandar, que es
# exactamente la sustitucion que se pretende, y una con Original sigue igual.
_CHOICE_TO_LEVEL = {
	_CHOICE_AUTO: STANDARD_LEVEL,
	_CHOICE_ORIGINAL: ORIGINAL_LEVEL,
}

# Traduccion del ajuste VIEJO (cinco niveles) a la eleccion nueva. Solo
# Original sobrevive como tal; los tres fijos y Auto van a Auto. La usa la
# migracion de service.py, y se declara aqui para que la tabla viva junto a los
# indices que traduce.
LEGACY_TO_CHOICE = {
	0: _CHOICE_AUTO,          # Low
	1: _CHOICE_AUTO,          # Medium
	2: _CHOICE_AUTO,          # High
	ORIGINAL_LEVEL: _CHOICE_ORIGINAL,
	AUTO_LEVEL: _CHOICE_AUTO,
}


# ─────────────────────────────────────────────────────────────────────────────
#  v1.0.72 — el nivel AUTO sigue el TOPE DE ALMACENAMIENTO, no la pantalla
#
#  Hasta aqui AUTO miraba la resolucion de la pantalla y, en 4K, pedia
#  'original' para todo. Medido en un aparato real: 186 posters pedidos a
#  tamaño completo, unos 2000x3000, guardados en disco a 480x720 y 47 KB. El
#  motivo es que Kodi reescala TODA imagen al cachearla, con tope de ALTURA en
#  <imageres> (720 por defecto) y, solo para las 16:9 que lo alcanzan, en
#  <fanartres> (1080). Pedir por encima de ese tope no mejora un pixel: se
#  descarga y se decodifica la imagen entera para tirar el resto, y ese gasto
#  cae justo cuando se esta dibujando un grid.
#
#  Y la pantalla no lo arregla, que es lo contraintuitivo: en una tele 4K el
#  poster se sigue dibujando desde esos 480x720 porque el tope no depende de la
#  resolucion de la GUI. En Android hay ademas un caso reportado en el que
#  <imageres> y <fanartres> se ignoran del todo, asi que ahi el tope es fijo y
#  subir la calidad no puede hacer nada en absoluto.
#
#  Asi que AUTO elige, por cada tipo de imagen, el tamaño mas pequeño de TMDb
#  que LLENA el tope. Ni menos —eso seria dejar calidad sin usar y ampliar una
#  imagen pequeña— ni mas. Cuando el tope esta levantado (alguien puso
#  <imageres>9999</imageres> en un aparato donde eso funciona) ya no hay nada
#  que lo limite y entonces si manda la pantalla, como antes.
# ─────────────────────────────────────────────────────────────────────────────

# Tamaños que TMDb publica en /3/configuration, con su ancho en pixeles. La
# lista es distinta por tipo y no es intercambiable.
_POSTER_STEPS = (
	('w92', 92), ('w154', 154), ('w185', 185),
	('w342', 342), ('w500', 500), ('w780', 780))
_BACKDROP_STEPS = (('w300', 300), ('w780', 780), ('w1280', 1280))
_STILL_STEPS = (('w92', 92), ('w185', 185), ('w300', 300))

# Relaciones de TMDb: el poster es 1:1,5 y fanart y still son 16:9.
_POSTER_RATIO = 1.5
_WIDE_RATIO = 9.0 / 16.0

# Valores por defecto de Kodi cuando no hay advancedsettings.xml.
DEFAULT_IMAGERES = 720
DEFAULT_FANARTRES = 1080

_CEILING_PROP = 'luc_kodi.cache_ceiling'

# Ruta unica del advancedsettings.xml de Kodi, compartida por el lector de
# aqui y por el escritor de display_test.py. Si las dos no fueran la misma, el
# test podria informar de un tope distinto del que acaba de escribir.
ADVANCEDSETTINGS_PATH = 'special://masterprofile/advancedsettings.xml'


def _fit(steps, ratio, ceiling):
	"""Primer paso cuyo ALTO alcanza el tope; 'original' si ninguno llega.

	El tope de Kodi es de altura, de ahi que se compare por altura y no por
	ancho: un w500 de poster mide 750 de alto y con tope 720 sobrevive casi
	entero, mientras que un w1280 de fanart mide 720 y con tope 1080 se queda
	corto, que es justo el motivo de que el fanart si merezca 'original'.
	"""
	for name, width in steps:
		if width * ratio >= ceiling:
			return name
	return 'original'


def cache_ceiling():
	"""(imageres, fanartres, declarado_por_el_usuario).

	Kodi no expone estos dos valores por ningun API, asi que se leen de
	advancedsettings.xml. El resultado se guarda en una window property porque
	set_resolutions() corre en cada instancia de TMDb y esto es un fichero en
	disco: leerlo cada vez seria pagar I/O por un dato que no cambia sin
	reiniciar Kodi.
	"""
	from resources.lib.modules import control as _control
	cached = _control.homeWindow.getProperty(_CEILING_PROP)
	if cached:
		try:
			image, fanart, declared = cached.split('|')
			return int(image), int(fanart), declared == '1'
		except ValueError:
			pass

	imageres, fanartres, declared = DEFAULT_IMAGERES, DEFAULT_FANARTRES, False
	try:
		# v1.0.74 — masterprofile, no profile. Kodi carga advancedsettings.xml
		# del perfil MAESTRO (su propio log de arranque lista
		# special://masterprofile/advancedsettings.xml y dice que
		# special://profile esta mapeado ahi cuando solo hay un perfil). Con un
		# perfil secundario activo las dos rutas dejan de ser la misma, y
		# leyendo por la de perfil el addon informaria de un tope que Kodi no
		# esta aplicando. El escritor de display_test usa la misma constante.
		path = _control.transPath(ADVANCEDSETTINGS_PATH)
		if _control.existsPath(path):
			fh = _control.openFile(path)
			try:
				raw = fh.read() or ''
			finally:
				fh.close()
			found = re.search(r'<imageres>\s*(\d+)\s*</imageres>', raw)
			if found:
				imageres, declared = int(found.group(1)), True
			found = re.search(r'<fanartres>\s*(\d+)\s*</fanartres>', raw)
			if found:
				fanartres, declared = int(found.group(1)), True
	except Exception:
		pass

	_control.homeWindow.setProperty(
		_CEILING_PROP, '%d|%d|%s' % (imageres, fanartres, '1' if declared else '0'))
	return imageres, fanartres, declared


def auto_sizes(imageres, fanartres, is_4k=False, wide=False):
	"""Tamaños que AUTO va a pedir con este tope.

	v1.0.72 — se retira la rama que, con el tope alto, volvia a decidir por la
	pantalla. Existia cuando el tope podia ser un 9999 arbitrario y no decia
	nada del aparato. Ya no: el tope que escribe el test ES la altura del
	panel, asi que _fit() sobre ese numero da la respuesta correcta sin
	consultar nada mas.

	Mantenerla causaba una incoherencia que solo se ve recorriendo el proceso
	entero: en un panel 4K con la interfaz capada a 1080, el tope se subia a
	2160 —por el panel, que es lo correcto— y acto seguido el tamano se
	elegia por la interfaz, que reporta 1080. Resultado: tope de 2160 y
	peticion de w780, que llena 1170. Se subia el techo para no usarlo.

	is_4k y wide se conservan en la firma porque hay llamadas que los pasan,
	pero ya no intervienen.
	"""
	# El fanart y el still solo suben a fanartres si son 16:9 Y lo alcanzan;
	# si no, Kodi los recorta con imageres. Se pide para el caso bueno, que es
	# el que decide si merece la pena 'original'.
	return {
		'poster': _fit(_POSTER_STEPS, _POSTER_RATIO, imageres),
		'fanart': _fit(_BACKDROP_STEPS, _WIDE_RATIO, fanartres),
		'still': _fit(_STILL_STEPS, _WIDE_RATIO, fanartres),
		# El profile es la EXCEPCION al criterio de "el menor que llena el
		# tope", y a proposito. Sus pasos son w45, w185, h632 y original: h632
		# se queda en 632 px de alto, asi que con el tope por defecto de 720 el
		# criterio general saltaria a 'original' y traeria un retrato de
		# 2000x3000 para dibujarlo del tamano de un sello en la ficha de
		# reparto. Los 88 px que faltan hasta 720 no se ven en esa ranura; los
		# seis megapixeles descargados si se notan. Cuando el tope esta
		# levantado esta rama ni se recorre, asi que aqui h632 es siempre la
		# respuesta buena.
		'profile': 'h632',
	}


def effective_sizes(user_level, is_4k, wide=False, ceiling=None):
	"""Los cuatro tamaños que se van a pedir de verdad.

	Es la funcion que decide en produccion; display_test llama a esta misma
	para que el informe no pueda decir una cosa y los menus hacer otra.
	`ceiling` se acepta como (imageres, fanartres) para poder probarla sin
	tocar el disco.
	"""
	if user_level == STANDARD_LEVEL:
		return standard_sizes()
	# AUTO ya no se puede elegir, pero se sigue resolviendo: display_test lo usa
	# para calcular que HABRIA pedido el tope y poder avisar.
	if user_level == AUTO_LEVEL:
		if ceiling is None:
			imageres, fanartres, _declared = cache_ceiling()
		else:
			imageres, fanartres = ceiling[0], ceiling[1]
		return auto_sizes(imageres, fanartres, is_4k, wide)
	if user_level < 0 or user_level >= len(IMAGE_LEVELS):
		return standard_sizes()
	return IMAGE_LEVELS[user_level]


def resolve_sizes():
	"""Los tamaños a pedir, resolviendo por el camino mas barato posible.

	v1.0.72 — el orden importa y no es cosmetico. is_4k_display() BLOQUEA hasta
	1,5 s cuando el flag de pantalla todavia no esta escrito, que es justo lo
	que pasa en el primer menu tras un arranque en frio de Android, y
	set_resolutions() corre en cada instancia de TMDb. Mientras el tope de
	cacheo muerda, la pantalla no cambia ni un tamaño, asi que preguntar por
	ella antes de saber si hace falta era pagar esa espera para tirar la
	respuesta. Ahora se lee primero el tope, que es una window property, y solo
	se molesta al detector en el caso raro de que el tope este levantado y la
	pantalla vuelva a mandar.
	"""
	# v1.0.82 — los dos perfiles son tablas fijas, asi que no hay que leer el
	# tope ni molestar al detector de pantalla: se resuelve sin tocar disco.
	return effective_sizes(_read_image_level(), False, False)


def _read_image_level():
	"""Nivel efectivo a partir del ajuste. Devuelve AUTO_LEVEL u ORIGINAL_LEVEL.

	v1.0.74 — esta funcion ya NO migra nada, y ese es el arreglo del fallo que
	tenia. Migraba solo cuando el ajuste nuevo no tenia valor propio, pero un
	enum declarado con default="0" NUNCA devuelve vacio: Kodi entrega el
	default, asi que la rama de migracion era inalcanzable y quien venia de una
	version con el ajuste viejo aparecia en Auto en silencio, dijera lo que
	dijera el comentario.

	La migracion se hace ahora una sola vez en VersionIsUpdateCheck
	(service.py), que es donde el proyecto ya migra este tipo de cosas —el
	desplegable de modelos de Gemini se arreglo exactamente asi— y ademas es el
	unico sitio que corre DESPUES de que Kodi haya escrito settings.xml y
	puede limpiar la cache de ajustes al terminar. Aqui solo se lee.

	Un valor fuera de rango (los indices 2, 3 y 4 que la 1.0.73 llego a
	escribir) cae a Auto, para que una instalacion sin migrar todavia nunca
	quede en un estado invalido.
	"""
	raw = getSetting(IMAGE_SETTING, '')
	try:
		return _CHOICE_TO_LEVEL.get(int(raw), STANDARD_LEVEL)
	except (TypeError, ValueError):
		return STANDARD_LEVEL


def effective_level(user_level, is_4k, wide=False):
	"""Indice de IMAGE_LEVELS mas parecido a lo que se va a pedir.

	Se conserva porque el ajuste sigue siendo un enum de cuatro niveles mas
	Auto, pero YA NO decide nada: desde la v1.0.72 AUTO no resuelve a un nivel
	de la tabla sino a una combinacion propia por tipo de imagen, que ningun
	indice puede representar. Quien necesite saber que se va a pedir debe
	llamar a effective_sizes(); esto solo sirve para etiquetar.
	"""
	if user_level in (AUTO_LEVEL, STANDARD_LEVEL):
		sizes = effective_sizes(user_level, is_4k, wide)
		for index, level in enumerate(IMAGE_LEVELS):
			if level == sizes:
				return index
		return 3 if sizes['poster'] == 'original' else 2
	if user_level < 0 or user_level >= len(IMAGE_LEVELS):
		return 2
	return user_level



class Movies(TMDb):
	def __init__(self):
		TMDb.__init__(self)
		self.list = []
		self.meta = []
		self.movie_link = base_link + 'movie/%s?api_key=%s&language=%s&append_to_response=credits,release_dates,videos,alternative_titles,images&include_image_language=%s,en,null' % ('%s', self.API_key, self.lang, self.lang)
		# v1.0.80 — DETALLE LIGERO (primer plano). Idéntico al de arriba menos el
		# bloque `images`, que es el que pesa: con include_image_language=xx,en,null
		# TMDb devuelve TODOS los pósters y backdrops del título (300-500 KB de JSON
		# en una peli popular, frente a ~20 KB sin él). Para pintar una parrilla no
		# hace falta nada de eso: póster y fanart primarios ya vienen en la raíz.
		# Lo que sí se pierde es tmdblogo (clearlogo) y posters_all (rotación), y
		# por eso la meta se marca como ligera y el servicio la completa en segundo
		# plano (ver refresh_meta_full / catalog_updater.upgrade_light_meta).
		self.movie_link_light = base_link + 'movie/%s?api_key=%s&language=%s&append_to_response=credits,release_dates,videos,alternative_titles' % ('%s', self.API_key, self.lang)
		self.light_lists = getSetting('meta.light_lists') != 'false'
		###  other "append_to_response" options external_ids,images,translations
		self.art_link = base_link + 'movie/%s/images?api_key=%s' % ('%s', self.API_key)
		self.external_ids = base_link + 'movie/%s/external_ids?api_key=%s' % ('%s', self.API_key)
		# self.user = str(self.imdb_user) + str(self.API_key)
		self.user = str(self.API_key)

	def tmdb_list(self, url, meta_sem=None, light=None, deadline=None):
		# deadline (v1.0.80): marca de time.time() a partir de la cual se deja de
		# enriquecer. Solo la pasa el servicio de catálogo, para que una pasada en
		# segundo plano nunca se coma más del presupuesto de tiempo configurado.
		# Los menús y widgets NUNCA la pasan: ahí la lista se enriquece entera.
		if light is None: light = self.light_lists
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
		except: return
		self.list = [] ; sortList = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				sortList.append(values['tmdb'])
				values['imdb'] = ''
				values['tvdb'] = ''
				values['metacache'] = False
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		# meta_sem: semáforo GLOBAL compartido por el precache de arranque para
		# acotar el TOTAL de peticiones de meta concurrentes entre TODAS las
		# listas. v1.0.80: cuando no lo hay (menús y widgets) se usa uno local
		# en vez de dejar sueltos ~20 hilos por lista.
		sem = meta_sem if meta_sem is not None else Semaphore(LIST_MAX_WORKERS)

		def items_list(i):
			if self.list[i]['metacache']: return
			if deadline and time() > deadline: return
			sem.acquire()
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				movie_meta = self.get_movie_meta(tmdb, light=light)
				values.update(movie_meta)
				imdb = values['imdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
			finally:
				sem.release()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		sorted_list = []
		self.list = [i for i in self.list if i.get('tmdb')]
		for i in sortList:
			sorted_list += [item for item in self.list if item['tmdb'] == i] # resort to match TMDb list because threading will lose order.
		return sorted_list

	def tmdb_list_ids(self, url):
		"""Devuelve SOLO los tmdb ids de una lista, sin enriquecer (sin las ~20
		peticiones de meta por título). Lo usa el precache de arranque para saber
		QUÉ títulos invalidar en metacache antes de re-enriquecer (frescura real).
		Reutiliza exactamente la misma clave de caché que tmdb_list, así que no
		añade tráfico: si la lista ya se pidió, sale de caché."""
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return []
			return [str(i['id']) for i in result.get('results', []) if i.get('id')]
		except: return []

	def tmdb_list_visual_refresh(self, url):
		"""v1.0.54 — arranque ligero. Refresca SOLO los campos visuales de la
		parrilla (fanart, rating, votos, plot, fecha y, si no se prefieren
		títulos en inglés, el póster primario) de los títulos que YA están en
		metacache, tomándolos de la propia respuesta de LISTA de TMDb: cero
		peticiones de detalle por título. El detalle completo (reparto, logos,
		posters_all, certificaciones, tráilers) NO se toca aquí — lo renueva el
		ciclo fresh_meta cada meta_hours. Los títulos sin meta previa (o cuya
		meta la política de frescura de metacache da por caducada) se dejan
		intactos: tmdb_list los traerá completos justo después.
		Devuelve el número de metas actualizadas."""
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return 0
			items = result.get('results') or []
			if not items: return 0
		except: return 0
		refs = [{'tmdb': str(i.get('id') or ''), 'imdb': '', 'tvdb': '', 'metacache': False} for i in items]
		try: refs = metacache.fetch(refs, self.lang, self.user)
		except: return 0
		updates = []
		for ref, item in zip(refs, items):
			try:
				if not ref.get('metacache'): continue # sin meta previa o caducada: la traerá completa tmdb_list
				values = dict(ref)
				for k in ('metacache', 'next'): values.pop(k, None)
				if not values.get('tmdb'): values['tmdb'] = str(item.get('id') or '')
				if item.get('backdrop_path'): values['fanart'] = '%s%s' % (self.fanart_path, item['backdrop_path'])
				# El póster de la lista es el primario localizado. Si el usuario
				# prefiere arte en inglés, el póster elegido por el detalle
				# completo (bloque images) puede ser otro: en ese caso no se pisa.
				if item.get('poster_path') and not self.prefer_en_titles:
					values['poster'] = '%s%s' % (self.poster_path, item['poster_path'])
				if item.get('vote_average') is not None: values['rating'] = item.get('vote_average')
				if item.get('vote_count') is not None: values['votes'] = item.get('vote_count')
				if item.get('overview'): values['plot'] = item['overview']
				premiered = item.get('release_date') or ''
				if premiered:
					values['premiered'] = str(premiered)
					values['year'] = str(premiered)[:4]
				updates.append({'imdb': values.get('imdb', ''), 'tmdb': values.get('tmdb', ''), 'tvdb': values.get('tvdb', ''),
						'lang': self.lang, 'user': self.user, 'item': values})
			except: pass
		if updates:
			try: metacache.insert(updates)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return len(updates)

	def jw_list(self, jw_package_code):
		# Alternative to tmdb_list(): sources TMDb IDs from JustWatch's GraphQL API
		# instead of TMDb's discover endpoint. Used by the experimental
		# 'streaming.use_justwatch' toggle. Enrichment pipeline below is a verbatim
		# mirror of tmdb_list()'s metadata thread loop.
		try:
			from resources.lib.indexers.justwatch import popular_movie_tmdb_ids
			tmdb_ids = cache.get(popular_movie_tmdb_ids, 24, jw_package_code)
			if not tmdb_ids: return
		except: return
		self.list = [] ; sortList = []
		for tid in tmdb_ids:
			try:
				values = {'next': '', 'tmdb': str(tid), 'imdb': '', 'tvdb': '', 'metacache': False}
				sortList.append(values['tmdb'])
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		sem = Semaphore(LIST_MAX_WORKERS)

		def items_list(i):
			if self.list[i]['metacache']: return
			sem.acquire()
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				movie_meta = self.get_movie_meta(tmdb, light=self.light_lists)
				values.update(movie_meta)
				imdb = values['imdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '')
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
			finally:
				sem.release()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		sorted_list = []
		self.list = [i for i in self.list if i.get('tmdb')]
		for i in sortList:
			sorted_list += [item for item in self.list if item['tmdb'] == i]
		return sorted_list

	def tmdb_collections_list(self, url):
		try:
			result = cache.get(self.get_request, 168, url)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			if '/collection/' in url: items = result['parts']
			elif '/3/' in url: items = result['items']
			else: items = result['results']
		except: return
		self.list = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				media_type = item.get('media_type')
				if media_type == 'tv': continue
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				values['imdb'] = ''
				values['tvdb'] = ''
				values['metacache'] = False 
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				movie_meta = self.get_movie_meta(tmdb)
				values.update(movie_meta)
				imdb = values['imdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		self.list = [i for i in self.list if i.get('tmdb')]
		return self.list

	def tmdb_collections_search(self, url):
		try:
			result = cache.get(self.get_request, 168, url)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
		except: return
		self.list = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				values['media_type'] = 'collection'
				values['fanart'] = '%s%s' % (self.fanart_path, item['backdrop_path']) if item.get('backdrop_path') else ''
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				values['name'] = item.get('name')
				values['plot'] = item.get('overview', '') if item.get('overview') else ''
				values['poster'] = '%s%s' % (self.poster_path, item['poster_path']) if item.get('poster_path') else ''
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return self.list

	def get_movie_request(self, tmdb, imdb=None, light=False): # api claims int rq'd.  But imdb_id works for movies but not looking like it does for shows
		if not tmdb and not imdb: return
		link = self.movie_link_light if light else self.movie_link
		try:
			result = None
			if tmdb: result = self.get_request(link % tmdb)
			if not result or ('404:NOT FOUND' in result):
				if imdb: result = self.get_request(link % imdb)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_movie_meta(self, tmdb, imdb=None, light=False):
		if not tmdb and not imdb: return
		try:
			result = self.get_movie_request(tmdb, imdb, light)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			meta = {}
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			meta['mediatype'] = 'movie'
# adult - not used
			meta['fanart'] = '%s%s' % (self.fanart_path, result['backdrop_path']) if result.get('backdrop_path') else ''

			try:
				_logos = [i for i in result['images']['logos'] if i.get('file_path', '').endswith('png')]
				tmdblogo_path = ([i['file_path'] for i in _logos if i.get('iso_639_1') == self.art_lang] or [i['file_path'] for i in _logos])[0]
			except: tmdblogo_path = ''
			meta['tmdblogo'] = '%s%s' % (self.fanart_path, tmdblogo_path) if tmdblogo_path else ''

			meta['belongs_to_collection'] = result.get('belongs_to_collection', '')
# budget - not used
			meta['genre'] = ' / '.join([x['name'] for x in result.get('genres', {})]) or 'NA'
# homepage - not used
			meta['tmdb'] = str(result.get('id', '')) if result.get('id') else ''
			meta['imdb'] = str(result.get('imdb_id', '')) if result.get('imdb_id') else ''
			meta['imdbnumber'] = meta['imdb']
			meta['original_language'] = result.get('original_language', '')
			meta['originaltitle'] = result.get('original_title', '')
			meta['plot'] = result.get('overview', '') if result.get('overview') else ''
			if self.lang != 'en' and meta['plot'] in ('', None, 'None'): meta['plot'] = self.get_en_overview(tmdb)
			# meta['?'] = result.get('popularity', '')
			meta['poster'] = '%s%s' % (self.poster_path, result['poster_path']) if result.get('poster_path') else ''
			try:
				_alt_posters = _poster_list(result['images']['posters'], self.art_lang, self.poster_path)
				if self.prefer_en_titles and _alt_posters: meta['poster'] = _alt_posters[0] # póster base también en inglés (aunque la rotación esté apagada)
				if len(_alt_posters) > 1: meta['posters_all'] = _alt_posters # solo guardar si hay alternativas reales para rotar
			except: pass
			# production_companies = result.get('production_companies', {})
			# try: meta['studio'] = [x['name'] for x in production_companies if x['logo_path']][0] # Silvo seems to use "studio" icons in place of "thumb" for movies in list view
			# except:
				# try: meta['studio'] = production_companies[0].get('name')
				# except: meta['studio'] = ''
			try: meta['country_codes'] = [i['iso_3166_1'] for i in result['production_countries']]
			except: meta['country_codes'] = ''
			meta['premiered'] = str(result.get('release_date', '')) if result.get('release_date') else ''
			try: meta['year'] = meta['premiered'][:4]
			except: meta['year'] = ''
# revenue
			meta['duration'] = int(result.get('runtime') * 60) if result.get('runtime') else ''
			meta['spoken_languages'] = result.get('spoken_languages')
			meta['status'] = result['status']
			meta['tagline'] = result.get('tagline', '')
			meta['title'] = result.get('title')
			if self.prefer_en_titles and self.lang != 'en':
				meta['title'] = _english_title(result, 'movie') or meta['title']
			meta['rating'] = result.get('vote_average', '')
			meta['votes'] = result.get('vote_count', '')
			crew = result.get('credits', {}).get('crew')
			try: meta['director'] = ', '.join([d['name'] for d in [x for x in crew if x['job'] == 'Director']])
			except: meta['director'] = ''
			try: meta['writer'] = ', '.join([w['name'] for w in [y for y in crew if y['job'] in ('Writer', 'Screenplay', 'Author', 'Novel')]])
			except: meta['writer'] = ''
			meta['castandart'] = []
			for person in result['credits']['cast']:
				try: meta['castandart'].append({'name': person['name'], 'role': person['character'], 'thumbnail': ('%s%s' % (self.profile_path, person['profile_path']) if person.get('profile_path') else '')})
				except: pass
				if len(meta['castandart']) == 150: break
			meta['mpaa'] = ''
			def parse_mpaa(rel_info):
				for cert in rel_info.get('release_dates', {}): # loop thru all keys
					if cert['certification']:
						if cert['type'] not in (3, 4, 5, 6): continue # 1 and 2 are limited releases, ignore
						meta['mpaa'] = cert['certification']
						meta['premiered'] = cert['release_date'].split('T')[0] or meta['premiered'] # use Countries premiered date
						break
			try: parse_mpaa([x for x in result['release_dates']['results'] if x['iso_3166_1'] == self.mpa_country][0])
			except: pass
			if not meta['mpaa'] and self.mpa_country != 'US':
				try: parse_mpaa([x for x in result['release_dates']['results'] if x['iso_3166_1'] == 'US'][0])
				except: pass
			if meta['mpaa']: meta['mpaa'] = getSetting('mpa.prefix') + meta['mpaa']
			try:
				# v1.0.46: prefiere Trailer oficial de mayor resolución; Teaser solo como último recurso
				_vids = [x for x in result['videos']['results'] if x['site'] == 'YouTube' and x['type'] in ('Trailer', 'Teaser')]
				_vids.sort(key=lambda x: (x['type'] != 'Trailer', not x.get('official'), -(x.get('size') or 0)))
				trailer = _vids[0]['key']
				meta['trailer'] = control_trailer % trailer
			except: meta['trailer'] = ''
			# make aliases match what trakt returns in sources module for title checking scrape results
			try: meta['aliases'] = [{'title': x['title'], 'country': x['iso_3166_1'].lower()} for x in result.get('alternative_titles', {}).get('titles') if x.get('iso_3166_1').lower() in ('us', 'uk', 'gb')]
			except: meta['aliases'] = []
			# Marca de meta INCOMPLETA: se pidió sin el bloque images, así que no
			# lleva tmdblogo ni posters_all. El servicio la detecta por esta clave
			# y la completa en segundo plano.
			if light: meta['meta_light'] = True
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return meta

	def refresh_meta_full(self, tmdb, lang=None, user=None):
		"""v1.0.80 — Segundo plano: re-pide el detalle COMPLETO (con images) de un
		título cacheado en modo ligero y REEMPLAZA su fila de metacache, con lo que
		recupera clearlogo (tmdblogo), pósters alternativos y el arte de fanart.tv.
		`lang`/`user` vienen de la propia fila para que el INSERT OR REPLACE caiga
		sobre ella y no cree una nueva. Devuelve True si se actualizó."""
		if not tmdb: return False
		try:
			values = self.get_movie_meta(tmdb)
			if not values or not isinstance(values, dict): return False
			values.pop('meta_light', None)
			imdb = values.get('imdb', '')
			if self.enable_fanarttv:
				extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
				if extended_art: values.update(extended_art)
			values = dict((k, v) for k, v in iter(values.items()) if v is not None and v != '')
			metacache.insert([{'imdb': imdb, 'tmdb': str(tmdb), 'tvdb': '',
				'lang': lang if lang is not None else self.lang,
				'user': user if user is not None else self.user, 'item': values}])
			return True
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return False

	def get_art(self, tmdb):
		if not tmdb: return
		url = self.art_link % tmdb
		art3 = self.get_request(url)
		if art3 is None: return
		if '404:NOT FOUND' in art3: return art3
		try:
			poster3 = self.parse_art(art3['posters'])
			poster3 = '%s%s' % (self.poster_path, poster3) if poster3 else ''
		except: poster3 = ''
		try:
			fanart3 = self.parse_art(art3['backdrops'])
			fanart3 = '%s%s' % (self.fanart_path, fanart3) if fanart3 else ''
		except: fanart3 = ''
		extended_art = {'extended': True, 'poster3': poster3, 'fanart3': fanart3}
		return extended_art

	def parse_art(self, img):
		if not img: return None
		try:
			ret_img = [(x['file_path'], x['vote_average']) for x in img if any(value == x.get('iso_639_1') for value in (self.art_lang, 'null', '', None))]
			if not ret_img: ret_img = [(x['file_path'], x['vote_average']) for x in img]
			if not ret_img: return None
			if len(ret_img) >1: ret_img = sorted(ret_img, key=lambda x: int(x[1]), reverse=True)
			ret_img = [x[0] for x in ret_img][0]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		return ret_img

	def get_en_overview(self, tmdb): # fallback for when self.lang != 'en'
		if not tmdb: return None
		overview = None
		try:
			url = '%s%s' % (base_link, 'movie/%s?api_key=%s&language=en,en-US' % (tmdb, self.API_key))
			result = self.get_request(url)
			overview = result.get('overview')
			if overview: overview = 'Translation Not Available:\n' + overview
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return overview

	def get_credits(self, tmdb):
		if not tmdb: return None
		result = None
		try:
			url = base_link + 'movie/%s/credits?api_key=%s' % (tmdb, self.API_key)
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_external_ids(self, tmdb, imdb): # api claims int rq'd.  But imdb_id works for movies but not looking like it does for shows
		if not tmdb and not imdb: return
		try:
			result = None
			if tmdb: result = self.get_request(self.external_ids % tmdb)
			if not result or ('404:NOT FOUND' in result):
				if imdb: result = self.get_request(self.external_ids % imdb)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def IdLookup(self, imdb):
		if not imdb: return
		try:
			result = None
			find_url = base_link + 'find/%s?api_key=%s&external_source=%s'
			if imdb and imdb.startswith('tt'): # trakt has some bad data with url's in ids
				url = find_url % (imdb, self.API_key, 'imdb_id')
				result = self.get_request(url)
				if result is None: return
				if '404:NOT FOUND' in result: return result
				try: result = result['movie_results'][0]
				except: return None
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_watchproviders(self):
		# Curated tuples: (display_name, provider_id, logo_override[, watch_region]).
		# logo_override = "" -> fetch live from TMDb /watch/providers/movie (cached 30 days).
		# Override exists when TVshows.get_networks() already has a curated high-quality
		# logo for the same brand; otherwise we trust JustWatch's logo via TMDb's CDN.
		# provider_id may be pipe-joined ('520|524') to OR multiple TMDb ids (TMDb keeps
		# regional duplicates for some brands). watch_region defaults to 'US'; set the 4th
		# element for providers with no US presence (e.g. SkyShowtime is Europe-only) so
		# both the discover query and the logo lookup use a region where they exist.
		curated = [
			('Netflix',             8,    'https://i.postimg.cc/25VTZBr9/pngwing-com-(2).png'),
			('Amazon Prime Video',  9,    'https://i.postimg.cc/FH4WdKBq/prime-video-(1).png'),
            ('JustWatch TV',        2285, 'https://i.postimg.cc/WbMNhfB1/justwatch-(2).png'),
            ('Vix',                 457,  'https://i.postimg.cc/sXsZqr9z/vix-logo-01.png'),
            ('Paramount+',          2303, 'https://i.postimg.cc/50xnPkV6/paramount-plus.png'),
			('SkyShowtime',         1773, 'https://i.postimg.cc/76GpVGxT/skyshowtime-2022-color.png', 'ES'),
			('The CW',              83,   'https://i.postimg.cc/4NnRNxHk/The-CW-(2006-2024).png'),
			('HBO Max',             1899, 'https://i.postimg.cc/BnD29cZq/HBO-Max-Logo-svg.png'),
			('Hulu',                15,   'https://i.postimg.cc/26tsWfs5/Hulu-svg.png'),
			('Apple TV+',           350,  'https://i.postimg.cc/Bnz3fH66/apple-tv-(1).png'),
			('Peacock Premium',     386,  'https://i.postimg.cc/rpx038J6/peacock-(1).png'),
			('Disney+',             337,  'https://i.postimg.cc/1zGXMvmX/Disney-svg.png'),
            ('Starz',               43,   'https://i.postimg.cc/LXpsYw1B/starz-(1).png'),
			('AMC+',                526,  'https://i.postimg.cc/SxqxRW7Y/AMC.png'),
			('Crunchyroll',         283,  'https://i.postimg.cc/L5GsD8YR/crunchyroll.png'),
			('OnDemandKorea',       575,  'logos/ondemandkorea.png'),  # v1.0.96: Korean dramas and movies from KBS, SBS, MBC and more; US and Canada catalog
			('MUBI',                11,   'https://i.postimg.cc/GtCQRFtZ/Mubi.png'),
			('Shudder',             99,   'https://i.postimg.cc/nhXr6vZb/shudder.png'),
			('Google Play Movies',  3,    'https://i.postimg.cc/nLX7Kwkp/pngwing-com.png'),
			('TCM',                 361,  'https://i.postimg.cc/Wz8hcMnJ/pngwing-com-(1).png'),
			('fuboTV',              257,  'https://i.postimg.cc/d3V9DqRH/Fubo.png'),
			('MGM+',                34,   'https://i.postimg.cc/nzMC4yFT/MGM-logo-svg.png'),
			('Tubi',                73,   'https://i.postimg.cc/mDgJsSHD/Tubi.png'),
			('Pluto TV',            300,  'https://i.postimg.cc/ncgdWJ26/Pluto-TV.png'),
			('The Roku Channel',    207,  'https://i.postimg.cc/ZK6TnyZK/Roku-Channel.png'),
			('Kanopy',              191,  'https://i.postimg.cc/fR46Q6VV/image.jpg'),
			('Plex',                538,  'https://i.postimg.cc/sD003b1H/pngwing-com-(3).png'),
		]
		# Normalize to 4-tuples (name, pid, override, region) with 'US' as default region.
		norm = []
		for entry in curated:
			region = entry[3] if len(entry) > 3 and entry[3] else 'US'
			norm.append((entry[0], entry[1], entry[2], region))
		# Resolve missing logos with one cached call per needed region (30-day TTL;
		# TMDb logo paths are very stable).
		live_logos = {}  # (region, provider_id_int) -> logo url
		need_regions = set(r for _, _, override, r in norm if not override)
		for reg in need_regions:
			try:
				url = base_link + 'watch/providers/movie?api_key=%s&language=en-US&watch_region=%s' % (self.API_key, reg)
				data = cache.get(self.get_request, 720, url)
				if isinstance(data, dict):
					for p in (data.get('results') or []):
						lp = p.get('logo_path')
						if lp:
							live_logos[(reg, p.get('provider_id'))] = 'https://image.tmdb.org/t/p/original' + lp
			except Exception:
				from resources.lib.modules import log_utils
				log_utils.error()
		out = []
		for name, pid, override, region in norm:
			logo = override
			if not logo:
				for part in str(pid).split('|'):
					try: logo = live_logos.get((region, int(part)), '')
					except: logo = ''
					if logo: break
			out.append((name, str(pid), local_logo(name, logo), region)) # logo inside the add-on first, then the curated URL
		return out

	def watchproviders_curated(self):
		"""v1.0.80 — (nombre, provider_id, region) de la tabla curada, sin resolver
		logos ni tocar la red. Lo usa el diálogo de selección de plataformas a
		precachear (Ajustes) y el propio precache para construir las URLs."""
		out = []
		try:
			for name, pid, _logo, region in self.get_watchproviders():
				out.append((name, str(pid), region or 'US'))
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return out


class TVshows(TMDb):
	def __init__(self):
		TMDb.__init__(self)
		self.list = []
		self.meta = []
		self.show_link = base_link + 'tv/%s?api_key=%s&language=%s&append_to_response=credits,content_ratings,external_ids,alternative_titles,videos,images&include_image_language=%s,en,null' % ('%s', self.API_key, self.lang, self.lang)
		# v1.0.80 — Variante LIGERA (ver el comentario de Movies.movie_link_light):
		# mismo detalle sin el bloque `images`, que es el que dispara el peso de la
		# respuesta. external_ids se mantiene porque de ahí sale el tvdb, que es
		# clave de metacache para series.
		self.show_link_light = base_link + 'tv/%s?api_key=%s&language=%s&append_to_response=credits,content_ratings,external_ids,alternative_titles,videos' % ('%s', self.API_key, self.lang)
		self.light_lists = getSetting('meta.light_lists') != 'false'
		# 'append_to_response=translations, aggregate_credits' (DO NOT USE, response data way to massive and bogs the response time)
		self.art_link = base_link + 'tv/%s/images?api_key=%s' % ('%s', self.API_key)
		self.imdb_user = getSetting('imdb.user').replace('ur', '')
		self.user = str(self.imdb_user)
		self.date_time = datetime.now()
		self.today_date = (self.date_time).strftime('%Y-%m-%d')

	def tmdb_list(self, url, meta_sem=None, light=None, deadline=None):
		if not url: return
		if light is None: light = self.light_lists
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
		except: return
		self.list = [] ; sortList = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				values['tmdb'] = str(item.get('id')) if item.get('id', '') else ''
				sortList.append(values['tmdb'])
				values['metacache'] = False 
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		# Ver Movies.tmdb_list: sin semáforo del precache se usa uno local para no
		# soltar un hilo por título sin tope.
		sem = meta_sem if meta_sem is not None else Semaphore(LIST_MAX_WORKERS)

		def items_list(i):
			if self.list[i]['metacache']: return
			if deadline and time() > deadline: return
			sem.acquire()
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				showSeasons_meta = self.get_showSeasons_meta(tmdb, light=light)
				values.update(showSeasons_meta)
				imdb = values['imdb']
				tvdb = values['tvdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_tvshow_art, 336, tvdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
			finally:
				sem.release()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		sorted_list = []
		self.list = [i for i in self.list if i.get('tmdb')]
		for i in sortList:
			sorted_list += [item for item in self.list if str(item['tmdb']) == str(i)]
		return sorted_list

	def tmdb_list_ids(self, url):
		"""Igual que Movies.tmdb_list_ids: devuelve solo los tmdb ids de la lista
		sin enriquecer. Reutiliza la clave de caché de tmdb_list (no añade tráfico)."""
		if not url: return []
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return []
			return [str(i['id']) for i in result.get('results', []) if i.get('id')]
		except: return []

	def tmdb_list_visual_refresh(self, url):
		"""v1.0.54 — arranque ligero (variante series). Igual que en Movies:
		refresca solo los campos visuales desde la respuesta de LISTA (name,
		first_air_date, vote_average...), sin peticiones de detalle por título.
		El estado de emisión (status / next_episode_to_air) NO se toca: la
		política de frescura de metacache para series en emisión sigue mandando,
		y las metas que dé por caducadas no se tocan aquí (metacache=False) —
		tmdb_list las trae completas justo después.
		Devuelve el número de metas actualizadas."""
		if not url: return 0
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return 0
			items = result.get('results') or []
			if not items: return 0
		except: return 0
		refs = [{'tmdb': str(i.get('id') or ''), 'imdb': '', 'tvdb': '', 'metacache': False} for i in items]
		try: refs = metacache.fetch(refs, self.lang, self.user)
		except: return 0
		updates = []
		for ref, item in zip(refs, items):
			try:
				if not ref.get('metacache'): continue # sin meta previa o caducada: la traerá completa tmdb_list
				values = dict(ref)
				for k in ('metacache', 'next'): values.pop(k, None)
				if not values.get('tmdb'): values['tmdb'] = str(item.get('id') or '')
				if item.get('backdrop_path'): values['fanart'] = '%s%s' % (self.fanart_path, item['backdrop_path'])
				if item.get('poster_path') and not self.prefer_en_titles:
					values['poster'] = '%s%s' % (self.poster_path, item['poster_path'])
				if item.get('vote_average') is not None: values['rating'] = item.get('vote_average')
				if item.get('vote_count') is not None: values['votes'] = item.get('vote_count')
				if item.get('overview'): values['plot'] = item['overview']
				premiered = item.get('first_air_date') or ''
				if premiered:
					values['premiered'] = str(premiered)
					if not values.get('year'): values['year'] = str(premiered)[:4]
				updates.append({'imdb': values.get('imdb', ''), 'tmdb': values.get('tmdb', ''), 'tvdb': values.get('tvdb', ''),
						'lang': self.lang, 'user': self.user, 'item': values})
			except: pass
		if updates:
			try: metacache.insert(updates)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return len(updates)

	def tmdb_collections_list(self, url):
		if not url: return
		try:
			result = self.get_request(url)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			if '/collection/' in url: items = result['parts']
			elif '/3/' in url: items = result['items']
			else: items = result['results']
		except: return
		self.list = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				media_type = item.get('media_type', '')
				if media_type == 'movie': continue
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				values['metacache'] = False 
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				showSeasons_meta = cache.get(self.get_showSeasons_meta, 96, tmdb)
				values.update(showSeasons_meta)
				imdb = values['imdb']
				tvdb = values['tvdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_tvshow_art, 336, tvdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		self.list = [i for i in self.list if i.get('tmdb')]
		return self.list

	def get_show_request(self, tmdb, light=False):
		if not tmdb: return None
		try:
			result = None
			url = (self.show_link_light if light else self.show_link) % tmdb
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_showSeasons_meta(self, tmdb, light=False): # builds seasons meta from show level request
		if not tmdb: return None
		try:
			result = self.get_show_request(tmdb, light)
			if not result: return
			if '404:NOT FOUND' in result: return result
			meta = {}
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			meta['mediatype'] = 'tvshow'
			meta['fanart'] = '%s%s' % (self.fanart_path, result['backdrop_path']) if result.get('backdrop_path') else ''

			try:
				_logos = [i for i in result['images']['logos'] if i.get('file_path', '').endswith('png')]
				tmdblogo_path = ([i['file_path'] for i in _logos if i.get('iso_639_1') == self.art_lang] or [i['file_path'] for i in _logos])[0]
			except: tmdblogo_path = ''
			meta['tmdblogo'] = '%s%s' % (self.fanart_path, tmdblogo_path) if tmdblogo_path else ''

			try: meta['duration'] = min(result['episode_run_time']) * 60
			except: meta['duration'] = ''
			meta['premiered'] = str(result.get('first_air_date', '')) if result.get('first_air_date') else ''
			try: meta['year'] = meta['premiered'][:4]
			except: meta['year'] = ''
			meta['genre'] = ' / '.join([x['name'] for x in result.get('genres', {})]) or 'NA'
			meta['tmdb'] = tmdb
			meta['in_production'] = result.get('in_production') # do not use for "season_isAiring", this is show wide and "season_isAiring" is season specific for season pack scraping.
			meta['last_air_date'] = result.get('last_air_date', '')
			meta['last_episode_to_air'] = result.get('last_episode_to_air', '')
			meta['next_episode_to_air'] = result.get('next_episode_to_air', '')
			meta['tvshowtitle'] = result.get('name')
			if self.prefer_en_titles and self.lang != 'en':
				meta['tvshowtitle'] = _english_title(result, 'show') or meta['tvshowtitle']
			networks = result.get('networks', {})
			try: meta['studio'] = [x['name'] for x in networks if x['logo_path']][0] # use single studio name that has a logo in hopes skin also has logo 
			except:
				try: meta['studio'] = networks[0].get('name')
				except: meta['studio'] = ''
			# Network logo URL — consumido por source_results 2160p
			try:
				_net_logo_path = [x['logo_path'] for x in networks if x.get('logo_path')][0]
				meta['network_logo'] = (image_path % 'w300') + _net_logo_path
			except:
				meta['network_logo'] = ''
			meta['total_episodes'] = result.get('number_of_episodes') # count includes both aired and unaired eps
			meta['total_seasons'] = result.get('number_of_seasons')
			try: meta['origin_country'] = result.get('origin_country')[0]
			except: meta['origin_country'] = ''
			meta['original_language'] = result.get('original_language')
			meta['originaltitle'] = result.get('original_name')
			meta['plot'] = result.get('overview', '') if result.get('overview') else ''
			if self.lang != 'en' and meta['plot'] in ('', None, 'None'): meta['plot'] = self.get_en_overview(tmdb)
			# meta['?'] = result.get('popularity', '')
			meta['poster'] = '%s%s' % (self.poster_path, result['poster_path']) if result.get('poster_path') else ''
			meta['tvshow_poster'] = meta['poster'] # check that this new dict key is used throughout
			try:
				_alt_posters = _poster_list(result['images']['posters'], self.art_lang, self.poster_path)
				if self.prefer_en_titles and _alt_posters:
					meta['poster'] = _alt_posters[0] # póster base también en inglés (aunque la rotación esté apagada)
					meta['tvshow_poster'] = meta['poster'] # mantener sincronizado (se copió antes del override)
				if len(_alt_posters) > 1: meta['posters_all'] = _alt_posters # solo guardar si hay alternativas reales para rotar
			except: pass
			try: meta['country_codes'] = [i['iso_3166_1'] for i in result['production_countries']]
			except: meta['country_codes'] = ''
			meta['seasons'] = result.get('seasons')
			meta['status'] = result.get('status')
			# meta['counts'] = self.seasonCountParse(meta['seasons']) # check on performance hit
			meta['counts'] = dict(sorted({(str(i['season_number']), i['episode_count']) for i in meta['seasons']}, key=lambda k: int(k[0])))
			if meta['status'].lower in ('ended', 'canceled'):
				meta['total_aired_episodes'] = result.get('number_of_episodes')
			else:
				meta['total_aired_episodes'] = self.airedEpisodesParse(meta['seasons'], meta['last_episode_to_air'])
				# meta['total_aired_episodes'] = sum([i['episode_count'] for i in meta['seasons'] if i['season_number'] < meta['last_episode_to_air']['season_number'] and i['season_number'] != 0]) + meta['last_episode_to_air']['episode_number']
			meta['spoken_languages'] = result.get('spoken_languages')
			meta['tagline'] = result.get('tagline', '')
			meta['type'] = result.get('type')
			meta['rating'] = result.get('vote_average', '')
			meta['votes'] = result.get('vote_count', '')
			crew = result.get('credits', {}).get('crew')
			try: meta['director'] = ', '.join([d['name'] for d in [x for x in crew if x['job'] == 'Director']])
			except: meta['director'] = ''
			try: meta['writer'] = ', '.join([w['name'] for w in [y for y in crew if y['job'] == 'Writer']]) # movies also contains "screenplay", "author", "novel". See if any apply for shows
			except: meta['writer'] = ''
			meta['castandart'] = []
			for person in result['credits']['cast']:
				try: meta['castandart'].append({'name': person['name'], 'role': person['character'], 'thumbnail': ('%s%s' % (self.profile_path, person['profile_path']) if person.get('profile_path') else '')})
				except: pass
				if len(meta['castandart']) == 150: break
			mpaa = []
			mpaa += [x['rating'] for x in result['content_ratings']['results'] if x['iso_3166_1'] == self.mpa_country]
			mpaa += [x['rating'] for x in result['content_ratings']['results'] if x['iso_3166_1'] == 'US']
			try: meta['mpaa'] = mpaa[0]
			except: 
				try: meta['mpaa'] = result['content_ratings'][0]['rating']
				except: meta['mpaa'] = ''
			if meta['mpaa']: meta['mpaa'] = getSetting('mpa.prefix') + meta['mpaa']
			ids = result.get('external_ids', {})
			meta['imdb'] = str(ids.get('imdb_id', '')) if ids.get('imdb_id') else ''
			meta['imdbnumber'] = meta['imdb']
			meta['tvdb'] = str(ids.get('tvdb_id', '')) if ids.get('tvdb_id') else ''
			# make aliases match what trakt returns in sources module for title checking scrape results
			try: meta['aliases'] = [{'title': x['title'], 'country': x['iso_3166_1'].lower()} for x in result.get('alternative_titles', {}).get('results') if x.get('iso_3166_1').lower() in ('us', 'uk', 'gb')]
			except: meta['aliases'] = []
			try:
				# v1.0.46: prefiere Trailer oficial de mayor resolución; Teaser solo como último recurso
				_vids = [x for x in result['videos']['results'] if x['site'] == 'YouTube' and x['type'] in ('Trailer', 'Teaser')]
				_vids.sort(key=lambda x: (x['type'] != 'Trailer', not x.get('official'), -(x.get('size') or 0)))
				meta['trailer'] = _vids[0]['key']
				meta['trailer'] = control_trailer % meta['trailer']
			except: meta['trailer'] = ''
			# meta['banner'] = '' # not available from TMDb
			if (not meta.get('poster') or not meta.get('fanart')) and meta.get('tvdb'): # artwork fallback: TheTVDB when TMDb has none (Fanart.tv still overrides later)
				try:
					from resources.lib.modules import tvdb as tvdb_api
					tvdb_art = tvdb_api.series_art(meta['tvdb'])
					if not meta.get('poster') and tvdb_art.get('poster'): meta['poster'] = meta['tvshow_poster'] = tvdb_art['poster']
					if not meta.get('fanart') and tvdb_art.get('fanart'): meta['fanart'] = tvdb_art['fanart']
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
			# Marca de meta INCOMPLETA (sin bloque images): la completa el servicio.
			if light: meta['meta_light'] = True
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return meta

	def refresh_meta_full(self, tmdb, lang=None, user=None):
		"""v1.0.80 — Variante series de Movies.refresh_meta_full: re-pide el detalle
		completo (con images) de una serie cacheada en modo ligero y reemplaza su
		fila de metacache, recuperando clearlogo y el arte extendido."""
		if not tmdb: return False
		try:
			values = self.get_showSeasons_meta(tmdb)
			if not values or not isinstance(values, dict): return False
			values.pop('meta_light', None)
			imdb = values.get('imdb', '')
			tvdb = values.get('tvdb', '')
			if self.enable_fanarttv:
				extended_art = fanarttv_cache.get(FanartTv().get_tvshow_art, 336, tvdb)
				if extended_art: values.update(extended_art)
			values = dict((k, v) for k, v in iter(values.items()) if v is not None and v != '')
			metacache.insert([{'imdb': imdb, 'tmdb': str(tmdb), 'tvdb': tvdb,
				'lang': lang if lang is not None else self.lang,
				'user': user if user is not None else self.user, 'item': values}])
			return True
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return False

	def get_season_request(self, tmdb, season):
		if not tmdb: return None
		try:
			result = None
			url = '%s%s' % (base_link, 'tv/%s/season/%s?api_key=%s&language=%s&append_to_response=credits' % (tmdb, season, self.API_key, self.lang))
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_seasonEpisodes_meta(self, tmdb, season): # builds episodes meta from "/season/?" request
		if not tmdb and not season: return None
		try:
			if not tmdb: return None
			result = self.get_season_request(tmdb, season)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			meta = {}
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			meta['premiered'] = str(result.get('air_date', '')) if result.get('air_date') else '' # Kodi season level Information gui seems no longer available in 19 unless you use "mediatype = tvshow" for seasons
			episodes = []
			unaired_count = 0
			for episode in result['episodes']:
				episode_meta = {}
				episode_meta['mediatype'] = 'episode'
				episode_meta['premiered'] = str(episode.get('air_date', '')) if episode.get('air_date') else '' # this is season premiered, not series premiered.
				if not episode_meta['premiered']: # access to "status" not available at this level
					unaired_count += 1
					pass
				elif int(re.sub(r'[^0-9]', '', str(episode_meta['premiered']))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
					unaired_count += 1
				# try: meta['year'] = meta['premiered'][:4] # DO NOT USE, this will make the year = season premiered but scrapers want series premiered for year.
				# except: meta['year'] = ''
				episode_meta['episode'] = episode['episode_number']
				crew = episode.get('crew')
				try: episode_meta['director'] = ', '.join([d['name'] for d in [x for x in crew if x['job'] == 'Director']])
				except: episode_meta['director'] = ''
				try: episode_meta['writer'] = ', '.join([w['name'] for w in [y for y in crew if y['job'] == 'Writer']]) # movies also contains "screenplay", "author", "novel". See if any apply for shows
				except: episode_meta['writer'] = ''
				episode_meta['tmdb_epID'] = episode['id']
				episode_meta['title'] = episode['name']
				episode_meta['season'] = episode['season_number']
				episode_meta['plot'] = episode.get('overview', '') if episode.get('overview') else ''
				if self.lang != 'en' and episode_meta['plot'] in ('', None, 'None'): episode_meta['plot'] = self.get_en_overview(tmdb, episode_meta['season'], episode_meta['episode'], 'episode')
				episode_meta['code'] = episode['production_code']
				episode_meta['thumb'] = '%s%s' % (self.still_path, episode['still_path']) if episode.get('still_path') else ''
				episode_meta['rating'] = episode['vote_average']
				episode_meta['votes'] = episode['vote_count']
				# v1.0.68: duración POR EPISODIO, en segundos.
				# El nivel de serie usa min(episode_run_time), pero TMDb ha
				# dejado ese array vacío en muchas series (Silo, entre otras),
				# y entonces el episodio se queda sin duración: se comprobó en
				# un log real que la meta de un episodio llega con 41 claves y
				# ninguna es la duración. El endpoint de temporada sí trae
				# 'runtime' en cada episodio, y además es más exacto que la
				# media de la serie.
				try:
					_ep_runtime = episode.get('runtime')
					if _ep_runtime: episode_meta['duration'] = int(_ep_runtime) * 60
				except Exception: pass
				episodes.append(episode_meta)
			self._tvdb_fill_episodes(tmdb, episodes) # missing title, plot, air date or still: TheTVDB fills the gap
			meta['season_isAiring'] = 'true' if unaired_count > 0 else 'false' # I think this should be in episodes module where it has access to "showSeasons" meta for "status"
			meta['seasoncount'] = len(result.get('episodes')) #seasoncount = number of episodes for given season

			# aired_episodes = int(meta['seasoncount']) - unaired_count
			# from resources.lib.modules import log_utils
			# log_utils.log('aired_episodes=%s: tmdb_id=%s' % (str(aired_episodes), tmdb))

			# meta['tvseasontitle'] = result['name'] # seasontitle ?
			meta['plot'] = result.get('overview', '') if result.get('overview') else '' # Kodi season level Information seems no longer available in 19
			meta['tmdb'] = tmdb
			meta['poster'] = '%s%s' % (self.poster_path, result['poster_path']) if result.get('poster_path') else ''
			meta['season_poster'] = meta['poster']
			meta['season'] = result.get('season_number')
			meta['castandart'] = []
			for person in result['credits']['cast']:
				try: meta['castandart'].append({'name': person['name'], 'role': person['character'], 'thumbnail': ('%s%s' % (self.profile_path, person['profile_path']) if person.get('profile_path') else '')})
				except: pass
				if len(meta['castandart']) == 150: break
			# meta['banner'] = '' # not available from TMDb
			meta['episodes'] = episodes
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return meta

	def _tvdb_context(self, tmdb):
		# TheTVDB id and TMDb season sizes, from the light show request (no images block)
		result = self.get_show_request(tmdb, light=True)
		if not result or '404:NOT FOUND' in result: return None
		tvdb = (result.get('external_ids') or {}).get('tvdb_id')
		if not tvdb: return {'tvdb': ''}
		counts = dict((str(i.get('season_number')), i.get('episode_count')) for i in (result.get('seasons') or []))
		return {'tvdb': str(tvdb), 'counts': counts}

	def _tvdb_fill_episodes(self, tmdb, episodes):
		try:
			if getSetting('tvdb.fill_gaps') == 'false' or not episodes: return
			from resources.lib.modules import tvdb as tvdb_api
			if not any(tvdb_api._missing(ep) for ep in episodes): return
			from resources.lib.database import cache
			ctx = cache.get(self._tvdb_context, 168, tmdb)
			if not ctx or not ctx.get('tvdb'): return
			tvdb_api.fill_episodes(ctx['tvdb'], episodes, ctx.get('counts'), self.lang)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def get_episodes_request(self, tmdb, season, episode): # Don't think I'll use this at all
		if not tmdb and not season and not episode: return None
		try:
			result = None
			url = '%s%s' % (base_link, 'tv/%s/season/%s/episode/%s?api_key=%s&language=%s&append_to_response=credits' % (tmdb, season, episode, self.API_key, self.lang))
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_art(self, tmdb):
		if not tmdb: return None
		url = self.art_link % tmdb
		art3 = self.get_request(url)
		if art3 is None: return
		if '404:NOT FOUND' in art3: return art3
		try:
			poster3 = self.parse_art(art3['posters'])
			poster3 = '%s%s' % (self.poster_path, poster3) if poster3 else ''
		except: poster3 = ''
		try:
			fanart3 = self.parse_art(art3['backdrops'])
			fanart3 = '%s%s' % (self.fanart_path, fanart3) if fanart3 else ''
		except: fanart3 = ''
		extended_art = {'extended': True, 'poster3': poster3, 'fanart3': fanart3}
		return extended_art

	def parse_art(self, img):
		if not img: return None
		try:
			ret_img = [(x['file_path'], x['vote_average']) for x in img if any(value == x.get('iso_639_1') for value in (self.art_lang, 'null', '', None))]
			if not ret_img: ret_img = [(x['file_path'], x['vote_average']) for x in img]
			if not ret_img: return None
			if len(ret_img) >1: ret_img = sorted(ret_img, key=lambda x: int(x[1]), reverse=True)
			ret_img = [x[0] for x in ret_img][0]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		return ret_img

	def get_en_overview(self, tmdb, season=None, episode=None, level_type='show'): # fallback for when self.lang != 'en'
		if not tmdb: return None
		overview = None
		try:
			if level_type == 'show':
				url = '%s%s' % (base_link, 'tv/%s?api_key=%s&language=en,en-US' % (tmdb, self.API_key))
			else:
				url = '%s%s' % (base_link, 'tv/%s/season/%s/episode/%s?api_key=%s&language=en,en-US' % (tmdb, season, episode, self.API_key))
			result = self.get_request(url)
			overview = result.get('overview')
			if overview: overview = 'Translation Not Available:\n' + overview
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return overview

	def get_credits(self, tmdb):
		if not tmdb: return None
		result = None
		try:
			url = base_link + 'tv/%s/credits?api_key=%s' % (tmdb, self.API_key)
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_external_ids(self, tmdb):
		if not tmdb: return None
		try:
			result = None
			url = base_link + 'tv/%s/external_ids?api_key=%s' % (tmdb, self.API_key)
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def IdLookup(self, imdb, tvdb=None):
		if not imdb and not tvdb: return
		try:
			result = None
			find_url = base_link + 'find/%s?api_key=%s&external_source=%s'
			if imdb and imdb.startswith('tt'): # trakt has some bad data with url's in ids
				url = find_url % (imdb, self.API_key, 'imdb_id')
				try: result = self.get_request(url)['tv_results'][0]
				except: pass
			if tvdb and (not result or '404:NOT FOUND' in result):
				url = find_url % (tvdb, self.API_key, 'tvdb_id')
				result = self.get_request(url)
				if result is None: return
				if '404:NOT FOUND' in result: return result
				try: result = result['tv_results'][0]
				except: pass
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_counts(self, tmdb): ## for show pack scraping pack size calc 
		if not tmdb: return None
		showSeasons = cache.get(self.get_showSeasons_meta, 96, tmdb)
		return self.seasonCountParse(showSeasons.get('seasons'))

	def seasonCountParse(self, seasons):
		if not seasons: return
		counts = {}
		for s in seasons:
			season = str(s.get('season_number'))
			counts[season] = s.get('episode_count')
		return counts

	def airedEpisodesParse(self, seasons, last_aired):
		if not seasons or not last_aired: return
		lastaired_season = last_aired.get('season_number', '')
		total_aired_episodes = 0
		for s in seasons:
			if any(value == s.get('season_number') for value in (0, lastaired_season)): continue
			if s.get('season_number') > lastaired_season: continue
			total_aired_episodes += s.get('episode_count', 0)
		total_aired_episodes += last_aired.get('episode_number', 0)
		return total_aired_episodes

	def get_season_isAiring(self, tmdb, season): # for pack scraping to skip if season is still airing
		if not tmdb or not season: return None
		seasonEpisodes = cache.get(self.get_seasonEpisodes_meta, 96, tmdb, season) # "status" not available this level so must iterate all eps
		unaired_count = 0
		for item in seasonEpisodes['episodes']:
			try:
				premiered = str(item.get('premiered', '')) if item.get('premiered') else ''
				if not premiered: unaired_count += 1
				elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))): unaired_count += 1
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return 'true' if unaired_count > 0 else 'false'

	def get_networks(self):
		# Curated tuples: (display_name, network_id, logo).
		# logo = "" -> resolved live from TMDb /network/{id} (cached 30 days).
		# network_id may be pipe-joined to OR several TMDb networks.
		networks = list(NETWORKS)
		# Resolve missing logos live from TMDb network details (30-day TTL; logo paths
		# are very stable). One small cached call per network with an empty logo.
		out = []
		for name, nid, logo in networks:
			if not logo:
				try:
					first_id = str(nid).split('|')[0]
					url = base_link + 'network/%s?api_key=%s' % (first_id, self.API_key)
					data = cache.get(self.get_request, 720, url)
					lp = data.get('logo_path') if isinstance(data, dict) else None
					if lp: logo = 'https://image.tmdb.org/t/p/original' + lp
				except Exception:
					from resources.lib.modules import log_utils
					log_utils.error()
			out.append((name, nid, local_logo(name, logo))) # logo inside the add-on first, then the URL of the entry
		return out

	def get_originals(self):
		# v1.0.96: logo incluido en el add-on primero, como en Networks y Streaming
		return [(i[0], i[1], local_logo(i[0], i[2])) for i in [
			('Amazon', '1024', 'https://i.imgur.com/ru9DDlL.png'),
			('Hulu', '453', 'https://i.imgur.com/cLVo7NH.png'),
			('Netflix', '213', 'https://i.postimg.cc/c4vHp9wV/netflix.png')]]


class Auth:
	def __init__(self):
		self.auth_base_link = '%s%s' % (base_link, 'authentication')

	def create_session_id(self):
		try:
			from resources.lib.modules.control import setSetting
			if getSetting('tmdb.username') == '' or getSetting('tmdb.password') == '': return notification(message='TMDb Account info missing', icon='ERROR')
			url = self.auth_base_link + '/token/new?api_key=%s' % self.API_key
			result = requests.get(url, timeout=15).json()
			token = result.get('request_token')
			url2 = self.auth_base_link + '/token/validate_with_login?api_key=%s' % self.API_key
			username = getSetting('tmdb.username')
			password = getSetting('tmdb.password')
			post2 = {"username": "%s" % username,
							"password": "%s" % password,
							"request_token": "%s" % token}
			result2 = requests.post(url2, data=post2, timeout=15).json()
			url3 = self.auth_base_link + '/session/new?api_key=%s' % self.API_key
			post3 = {"request_token": "%s" % token}
			result3 = requests.post(url3, data=post3, timeout=15).json()
			if result3.get('success') is True:
				session_id = result3.get('session_id')
				# v1.0.78: el mensaje llevaba la contrasena del usuario en claro en
				# pantalla. Confirmar la cuenta no necesita ver la clave.
				msg = '%s' % ('username = ' + username + '[CR]confirm?')
				if yesnoDialog(msg, '', ''):
					setSetting('tmdb.session_id', session_id)
					notification(message='TMDb Successfully Authorized')
				else: notification(message='TMDb Authorization Cancelled')
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def revoke_session_id(self):
		try:
			from resources.lib.modules.control import setSetting
			if getSetting('tmdb.session_id') == '': return
			url = self.auth_base_link + '/session?api_key=%s' % self.API_key
			post = {"session_id": "%s" % getSetting('tmdb.session_id')}
			result = requests.delete(url, data=post, timeout=15).json()
			if result.get('success') is True:
				setSetting('tmdb.session_id', '')
				notification(message='TMDb session_id successfully deleted')
			else:
				from resources.lib.modules import log_utils
				log_utils.log('TMDb Revoke session_id FAILED: %s' % result.get('status_message', ''), __name__, log_utils.LOGWARNING)
				if 'id is invalid or not found' in result.get('status_message', ''):
					setSetting('tmdb.session_id', '')
					notification(message=result.get('status_message', ''), icon='ERROR')
				else: notification(message='TMDb session_id deletion FAILED', icon='ERROR')
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
