# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — display_test.py (v1.0.74)

	Diagnostico de pantalla. Hermano del test de proveedores, pero al reves:
	aquel sale a la red y tarda minutos; este no sale a la red. Desde la
	v1.0.72 tampoco es del todo instantaneo, porque abre unas cuantas texturas
	ya cacheadas para medirlas — sigue siendo cosa de un segundo, y el disco
	solo se lee, nunca se escribe.

	POR QUE NO ES UN FOLLETO. La tentacion era escribir "4K detectado, por lo
	tanto suben metadatos, fanart, posters, texto e iconos". Eso seria describir
	la INTENCION del codigo, no comprobarla: si manana la cadena se rompe, el
	folleto seguiria diciendo que todo esta bien, porque lo lleva escrito. Un
	test que no puede fallar no sirve de nada.

	Asi que aqui no se describe: se lee lo que hay y se calcula lo que VAN a
	hacer los consumidores con ello, usando las mismas funciones que usan ellos.
	tmdb.effective_sizes() es literalmente la que decide el tamano de imagen en
	produccion; si se duplicara aqui, el test podria decir una cosa y los menus
	hacer otra, y entonces el test seria peor que no tenerlo.

	QUE COMPRUEBA
	  1. Resolucion GUI de Kodi frente al modo fisico de la pantalla. Una Shield
	     saca 4K con la GUI a 1080p sin avisar a nadie: el addon ve 1080 y sirve
	     artwork pequeno mientras el usuario jura que su tele es 4K.
	  2. Que juego de XML propio se esta usando. El de 2160p NO es el de 1080i
	     estirado: es el mismo diseno con coordenadas, tamanos, bordes y cuerpos
	     de fuente al doble, escritos aparte. Kodi elige carpeta segun la altura
	     de la GUI, asi que con la GUI a 1080p en una tele 4K las ventanas del
	     addon se dibujan con el juego de 1080i y las escala la tele. Los iconos,
	     en cambio, son los MISMOS PNG en ambos casos: lo que cambia es la
	     geometria y el texto, no el arte.
	  3. Nivel efectivo de imagen de TMDb y si FanartTV quedara activo.
	  4. Por donde salio la deteccion (sonda sincrona, hilo de reintentos o
	     tarde) y cuanto tardo. Es el punto donde el primer menu tras un
	     arranque en frio de Android se construye sin artwork bueno.
	  5. v1.0.72 — que tamano se PIDE a TMDb frente al que de verdad queda
	     GUARDADO en la caché de texturas, medido abriendo los ficheros. Los
	     cuatro puntos anteriores leen intenciones; este es el unico que
	     comprueba el otro extremo de la tuberia, que es donde el trabajo se
	     tira. Ver el bloque largo mas abajo.
	  6. v1.0.72 — la relacion de aspecto de la pantalla. Los dos juegos de
	     XML del addon estan dibujados 16:9; en un panel 16:10 encajan igual
	     pero no exactamente igual, y merece decirse antes de que alguien lo
	     reporte como fallo de maquetacion.

	Y CADA HALLAZGO TRAE ARREGLO. Lo que se puede corregir cambiando un ajuste
	del addon se aplica desde el propio dialogo; lo que depende de Kodi o del
	dispositivo se explica con el camino exacto a seguir.
"""

import re

import xbmc
import xbmcgui

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.modules import gui_resolution

LOGINFO = log_utils.LOGINFO

GREEN = 'ff00fa9a'
RED = 'ffff4444'
# v1.0.63c — el problema no era el TONO, era el BRILLO, y esta medido: sobre
# la fila azul de Kodi el dorado daba 2,2 de contraste y el naranja puro 1,7,
# peor todavia. Ningun naranja de saturacion normal llega a 3:1 ahi, asi que
# buscar "otro naranja" no iba a resolverlo nunca. Solo pasan los tonos MUY
# claros: este melocoton da 3,1 sobre el azul y 12,4 sobre el fondo oscuro.
# Sigue leyendose como aviso y ahora se lee de verdad. La fila seleccionada de
# Kodi es un azul claro, y sobre ella cualquier color de brillo medio se pierde
# porque hay poca diferencia de luminosidad, sea dorado, sea naranja puro. Un
# color solo se lee sobre la fila azul Y sobre el fondo oscuro si es CLARO. De
# ahi que el aviso pase a un naranja palido y el gris de texto se aclare: no se
# ha cambiado de color, se ha subido el brillo. El gris oscuro se queda solo
# para la vineta de un proveedor apagado, que es una forma, no texto.
GREY = 'ffdfe4e7'
DIM = 'ff888888'

# v1.0.63d — reparto definitivo: el DATO va en verde de la casa, la PROSA que
# lo acompana en gris claro. Antes el dato heredaba el gris y quedaba del mismo
# color que la explicacion, con lo que la vista no tenia donde agarrarse. Ahora
# el ojo salta de dato en dato bajando la lista y solo se para a leer el texto
# cuando algo no cuadra.
# v1.0.63b — el aviso vuelve a ser naranja, pero otro naranja. El anterior
# (fdb515) tiraba a dorado, un tono vecino del azul de la fila seleccionada, y
# encima de ella se apagaba. Este es naranja puro: al ser el complementario del
# azul destaca sobre la fila activa y sigue leyendose sobre el fondo oscuro.
# Rojo queda reservado para lo que falla de verdad; naranja es "mira esto".
ATTN = 'ffffe0b2'

_4K = gui_resolution._4K_HEIGHT_THRESHOLD


# v1.0.67 — era la vineta '●' (U+25CF), y la fuente de la ventana la elige el
# SKIN. En AeonNox salia el cuadrado de glifo ausente. Aqui el punto solo hacia
# de separador entre filas, asi que en el informe lo sustituye la sangria: no
# hace falta caracter ninguno para agrupar tres lineas bajo un titulo.
#
# Donde SI hacia falta marca —distinguir la recomendacion que se puede aplicar
# desde aqui de la que hay que arreglar en Kodi— va una palabra ASCII.
TAG_FIX  = 'FIX'
TAG_INFO = 'INFO'


# Misma sangria que el test de proveedores: los dos informes salen por la
# misma ventana y no tendria sentido que se leyeran distinto.
IND = '    '


def _color(text, col):
	return '[COLOR %s]%s[/COLOR]' % (col, text)


def _physical_mode():
	"""Modo real de salida, tal y como lo reporta Kodi. Devuelve (ancho, alto,
	texto crudo). En Android el infolabel suele traer '3840x2160 - Full Screen'
	aunque la GUI este a 1080p, que es justo la discrepancia que buscamos."""
	raw = ''
	try:
		raw = control.infoLabel('System.ScreenResolution') or ''
	except Exception:
		pass
	m = re.search(r'(\d{3,5})\s*[xX]\s*(\d{3,5})', raw)
	if not m:
		return 0, 0, raw.strip()
	return int(m.group(1)), int(m.group(2)), raw.strip()


def _gui_size():
	w = h = 0
	try:
		h = int(float(control.infoLabel('System.ScreenHeight') or 0))
	except Exception:
		h = 0
	try:
		w = int(float(control.infoLabel('System.ScreenWidth') or 0))
	except Exception:
		w = 0
	return w, h


def _skin_set(gui_height):
	"""Carpeta de XML que Kodi resolvera para las ventanas del addon."""
	return '2160p' if gui_height >= _4K else '1080i'


# ─────────────────────────────────────────────────────────────────────────────
#  v1.0.72 — Lo que se PIDE frente a lo que se GUARDA
#
#  Hasta aqui el test leia intenciones: que resolucion tiene la pantalla, que
#  nivel de imagen resuelve effective_level(), que tamano de TMDb va a pedir.
#  Todo eso es lo que el addon PRETENDE. Ninguna linea comprobaba el otro
#  extremo de la tuberia, que es donde se pierde el trabajo: Kodi reescala
#  cada imagen al cachearla, con tope de altura en <imageres> (720 por
#  defecto) y <fanartres> (1080). Pedir 'original' a TMDb y que Kodi lo
#  guarde a 720 de alto significa descargar y decodificar seis megapixeles
#  para conservar medio: se paga entero y se tira casi todo, y ese coste cae
#  justo en el momento de dibujar un grid.
#
#  Asi que esta seccion mide el fichero que hay en disco. No estima, no
#  describe: abre la textura cacheada, lee su cabecera y dice cuanto ocupa de
#  verdad. Es la unica forma de que el hallazgo sobreviva a un cambio de
#  plataforma, porque en Android TV hay ademas un caso reportado en el que
#  <imageres>/<fanartres> se ignoran del todo y el tope queda fijo pase lo
#  que pase en advancedsettings.xml.
#
#  POR QUE NO SE USA EL WIDTH/HEIGHT DE JSON-RPC. Textures.GetTextures los
#  devuelve, y estan mal: los cinco campos del array 'sizes' salen corridos
#  una posicion (size, width, height, usecount, lastused), asi que lo que
#  parece el ancho es un 1 constante y lo que parece la altura es el ancho.
#  Un test que se creyera ese dato diria que todos los posters miden 1 px de
#  ancho. Por eso aqui solo se pide 'cachedurl' y las medidas salen del
#  fichero.
# ─────────────────────────────────────────────────────────────────────────────

# Segmento de tamano de una URL de TMDb: .../t/p/original/ o .../t/p/w780/
_TMDB_SEG = re.compile(r'image\.tmdb\.org/t/p/(original|[whWH]\d+)/')

# Cuantas texturas se abren por cada tamano pedido. El recuento sale de la
# base entera; el I/O se limita a una muestra, que es lo unico caro aqui.
_SAMPLE = 12

# Cuantas entradas se llega a abrir por grupo buscando esas 12 medidas buenas.
# Sin tope, un grupo entero de huerfanos haria cientos de aperturas inutiles.
_MAX_TRIES = 60

# Topes que se ofrecen. Dependen de la calidad elegida, y desde la v1.0.74 son
# dos numeros con un significado claro cada uno:
#
#   AUTO parte de 1080 y sube con el panel. 1080 es el suelo porque es la
#   pantalla para la que esta dibujado el addon entero; por encima manda el
#   panel, asi que una tablet de 1752 recibe 1752 y no se la redondea hacia
#   abajo, y un aparato con panel 4K recibe 2160 aunque su interfaz este capada
#   a 1080p por software. Ese ultimo caso es el que mas gente tiene sin
#   saberlo, y es donde pasar el test se nota de verdad: la interfaz sigue en
#   1080 pero el arte queda cacheado a la altura que el panel puede mostrar.
#
#   ORIGINAL es 2160 fijo, el maximo util. Es lo que llena una pantalla 4K, y
#   es tambien el techo real del fanart de TMDb (3840x2160). Por encima de ahi
#   solo queda margen de poster —el 'original' de un poster ronda 2000x3000—
#   que ninguna ranura de ningun skin puede dibujar, al doble de memoria de
#   video por textura. Original significa "el maximo que se puede ver", no "el
#   maximo que existe en el servidor".
#
# La diferencia entre los dos numeros es lo que hace que la eleccion siga
# siendo una eleccion en cualquier pantalla: en 1080p, Auto da 1080 y Original
# sube a 2160; en 4K los dos coinciden en 2160 porque ahi ya no hay nada mejor
# que ofrecer, y el informe lo dice en vez de vender una mejora inexistente.
_CEILING_FLOOR = 1080
_ORIGINAL_CEILING = 2160

# La ranura del poster mide siempre 0,675 veces la altura de la pantalla, y
# sale igual en los dos juegos de skin: 729/1080 y 1458/2160 son el mismo
# numero. El fanart ocupa la altura entera. Con eso los topes se CALCULAN en
# vez de escribirse a mano, que era el fallo de la version anterior de esta
# recomendacion: ofrecia 1080 y 2160 fijos, asi que en una pantalla 1080p
# proponia subir el tope del fanart a 2160 para mostrarlo en 1080 —32 MB de
# memoria de video por fondo en vez de 8, sin un pixel de ganancia.
_POSTER_SLOT_RATIO = 0.675



def _wanted_ceiling(st):
	"""(imageres, fanartres) que le hacen falta a ESTA pantalla.

	El fanart necesita exactamente la altura de la pantalla. El poster necesita
	su ranura, pero se pide la altura completa igual: da margen para que Kodi
	reduzca desde una fuente mayor, que es lo que deja el fichero con mas
	detalle, y no cuesta un escalon mas porque TMDb no tiene ninguno entre
	medias. En Original manda la eleccion del usuario y se pide el maximo.
	"""
	# v1.0.74 — Original es 2160 y Auto sigue al panel desde un suelo de 1080.
	#
	# La 1.0.73 pedia 3000 en Original porque es el maximo que TMDb tiene. Se
	# baja a 2160 porque ese margen no cabe en ninguna parte: la ranura de
	# poster mas grande del addon mide 1458 px de alto en 2160p, y ni una
	# pantalla 4K puede dibujar un poster mas alto que 2160 ocupandola entera.
	# Lo que si cuesta es real y se paga en cada textura del grid.
	if st.get('user_level') == _ORIGINAL:
		return _ORIGINAL_CEILING, _ORIGINAL_CEILING

	# Auto: la altura REAL de la pantalla, suelo en 1080, sin techo inventado.
	# Se toma la mayor entre interfaz y panel a proposito — en un aparato 4K
	# con la interfaz capada a 1080p manda el panel, porque el fichero cacheado
	# ya queda bien para el dia que se quite la limitacion y volver a bajarlo
	# costaria la descarga entera otra vez.
	height = max(int(st.get('gui_h') or 0), int(st.get('phys_h') or 0))
	if height <= 0:
		height = _CEILING_FLOOR
	ceiling = max(_CEILING_FLOOR, height)
	return ceiling, ceiling

# Altura por debajo de la cual damos por hecho que Kodi ha recortado: un
# 'original' de TMDb ronda los 3000 px de alto, asi que cualquier cosa por
# debajo de esto es el tope de cacheo mordiendo, no la imagen de origen.
_CLAMP_BELOW = 1200

# v1.0.72 — de donde salio la lista de texturas y que fue mal por el camino.
# No se pinta en el informe (al usuario no le importa la fontaneria) pero va
# entero al log, que es donde se diagnostica.
_PROBE = {'source': '', 'notes': [], 'root': None}

# Indice del nivel "Auto" del ajuste. Se lee de tmdb.py y no se escribe aqui
# un 4 suelto: si el enum crece, el numero cambia en un solo sitio.
try:
	from resources.lib.indexers.tmdb import AUTO_LEVEL as _AUTO
	from resources.lib.indexers.tmdb import ORIGINAL_LEVEL as _ORIGINAL
	from resources.lib.indexers.tmdb import STANDARD_LEVEL as _STANDARD
except Exception:
	_AUTO, _ORIGINAL, _STANDARD = 4, 3, 5

# Alto en pixeles de los dos posters elegibles en el perfil Estandar. TMDb
# publica el ANCHO en el nombre y la relacion es 1:1,5.
_STANDARD_POSTER_HEIGHT = {'w500': 750, 'w780': 1170}


def _median(values):
	if not values:
		return 0
	s = sorted(values)
	return s[len(s) // 2]


def _be32(data, at):
	return (data[at] << 24) | (data[at + 1] << 16) | (data[at + 2] << 8) | data[at + 3]


def _dims(data):
	"""(ancho, alto) leidos de la cabecera. PNG por IHDR, JPEG por el marcador
	SOF. Sin dependencias y sin decodificar la imagen: los primeros kilobytes
	bastan y no hay que gastar memoria en el pixel data."""
	try:
		if len(data) < 24:
			return 0, 0
		if data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR':
			return _be32(data, 16), _be32(data, 20)
		if data[:2] == b'\xff\xd8':
			i, n = 2, len(data)
			while i + 9 < n:
				if data[i] != 0xFF:
					i += 1
					continue
				marker = data[i + 1]
				if marker == 0xFF:
					i += 1
					continue
				if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
					i += 2
					continue
				if marker in (0xD9, 0xDA):
					break
				seg = (data[i + 2] << 8) | data[i + 3]
				# SOF0..SOF15 llevan las dimensiones; DHT/JPG/DAC no son SOF
				# aunque caigan dentro del rango.
				if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
					return ((data[i + 7] << 8) | data[i + 8],
					        (data[i + 5] << 8) | data[i + 6])
				if seg < 2:
					break
				i += 2 + seg
	except Exception:
		pass
	return 0, 0


def _thumb_root():
	"""Raiz real de Thumbnails. Kodi la publica como special://thumbnails, pero
	en el log de Android las escribe como special://masterprofile/Thumbnails,
	y si el alias no resolviera aqui todas las medidas saldrian vacias sin que
	nada lo dijera. Se resuelve una vez, probando por orden."""
	if _PROBE['root'] is None:
		_PROBE['root'] = ''
		for root in ('special://thumbnails/', 'special://masterprofile/Thumbnails/',
		             'special://profile/Thumbnails/'):
			try:
				if control.existsPath(root):
					_PROBE['root'] = root
					break
			except Exception:
				pass
	return _PROBE['root']


def _measure(cachedurl):
	"""(ancho, alto, bytes, estado) de una textura cacheada.

	El estado distingue tres cosas que antes se confundian en un (0,0,0):
	'ok', 'missing' (la base la tiene registrada pero el fichero ya no esta) y
	'unreadable'. La diferencia importa: un disco lleno de huerfanos es lo
	normal justo despues de vaciar la carpeta Thumbnails, y decirlo evita que
	parezca que la medicion esta rota.

	v1.0.72 — el tamano se devuelve tal cual lo da Kodi, incluso negativo. En
	Android xbmcvfs.File.size() devuelve -1 para algunos ficheros, y como se
	dividia entre 1024 sin mirar, el informe llego a mostrar "-1 KB".
	"""
	root = _thumb_root()
	if not root:
		# Ninguna de las rutas de Thumbnails existe: la carpeta entera se ha
		# vaciado. Para quien lee el informe eso es exactamente "los ficheros
		# ya no estan", no un fallo de medicion. Si en realidad fuera un
		# problema de rutas, la linea del log lo delata con root=none.
		return 0, 0, 0, 'missing'
	path = root + cachedurl
	try:
		if not control.existsPath(path):
			return 0, 0, 0, 'missing'
	except Exception:
		pass
	fh = None
	try:
		fh = control.openFile(path)
		try:
			size = int(fh.size() or 0)
		except Exception:
			size = 0
		head = fh.readBytes(32768)
		w, h = _dims(bytes(head) if head else b'')
		return w, h, size, ('ok' if w and h else 'unreadable')
	except Exception:
		return 0, 0, 0, 'missing'
	finally:
		try:
			if fh:
				fh.close()
		except Exception:
			pass


def _texture_db():
	"""Ruta del Textures*.db en uso. El numero sube con las versiones de Kodi
	—Textures13 hoy—, asi que se coge el mas alto que haya en la carpeta en vez
	de escribir uno fijo que caduque en la proxima."""
	try:
		best, best_n = '', -1
		_dirs, files = control.listDir('special://database/')
		for name in files:
			match = re.match(r'^Textures(\d+)\.db$', name)
			if match and int(match.group(1)) > best_n:
				best, best_n = name, int(match.group(1))
		if best:
			return control.transPath('special://database/' + best)
	except Exception:
		log_utils.error()
	return ''


def _textures_from_db():
	"""Camino principal: la propia base de texturas, en SOLO LECTURA.

	Es el dato de origen y no depende de que un filtro de JSON-RPC se comporte;
	tampoco arrastra el bug del array 'sizes'. La conexion se abre con
	mode=ro para no poder tocar nada aunque algo fuera mal, y con timeout
	corto: si Kodi la tiene bloqueada escribiendo, se prefiere caer al
	siguiente camino antes que hacer esperar a nadie."""
	path = _texture_db()
	if not path:
		_PROBE['notes'].append('no Textures*.db found')
		return []
	import sqlite3
	conn = None
	try:
		safe = path.replace('?', '%3f').replace('#', '%23')
		try:
			conn = sqlite3.connect('file:%s?mode=ro' % safe, uri=True, timeout=2)
		except Exception:
			conn = sqlite3.connect(path, timeout=2)
		# v1.0.75 — ORDER BY id DESC, y no es cosmetico.
		#
		# Sin orden, SQLite devuelve por rowid: lo mas VIEJO primero. La
		# muestra de audit_artwork() se llena con las primeras 60 filas, asi
		# que justo despues de vaciar la carpeta Thumbnails esas 60 son todas
		# huerfanas y el informe declara el grupo entero no medible aunque
		# detras haya cientos de ficheros buenos. Medido en un aparato el
		# 4-sep-2026: 116 registros muertos por delante de 31 posters recien
		# cacheados a 2000x3000, y el test dijo 'files no longer on disk'.
		#
		# El fallo se comia el test justo en el unico momento en que hace
		# falta —despues de vaciar la cache, comprobando si el tope nuevo se
		# aplica— y respondia lo contrario de la verdad. Ordenando al reves,
		# la muestra es lo ultimo cacheado, que es exactamente lo que se
		# quiere mirar.
		try:
			rows = conn.execute(
				'SELECT url, cachedurl FROM texture WHERE url LIKE ? ORDER BY id DESC',
				('%image.tmdb.org/t/p/%',)).fetchall()
		except Exception:
			# Si un dia el esquema no tuviera 'id', mejor una muestra en mal
			# orden que ningun informe: se cae a la consulta de siempre.
			_PROBE['notes'].append('sqlite: sin columna id, muestra sin ordenar')
			rows = conn.execute(
				'SELECT url, cachedurl FROM texture WHERE url LIKE ?',
				('%image.tmdb.org/t/p/%',)).fetchall()
		return [{'url': row[0], 'cachedurl': row[1]} for row in rows if row[1]]
	except Exception:
		import traceback
		_PROBE['notes'].append('sqlite: %s' % traceback.format_exc(limit=0).strip()[:120])
		return []
	finally:
		try:
			if conn:
				conn.close()
		except Exception:
			pass


def _textures_from_jsonrpc(filtered=True):
	"""Respaldo. El filtro va sin barras a proposito y el recorte fino se hace
	en Python: si el 'contains' de Kodi tropieza con algo de la URL, esto lo
	deja fuera de la ecuacion en vez de devolver cero sin explicar por que."""
	import json
	params = {'properties': ['url', 'cachedurl']}
	if filtered:
		params['filter'] = {'field': 'url', 'operator': 'contains',
		                    'value': 'image.tmdb.org'}
	query = {'jsonrpc': '2.0', 'id': 1,
	         'method': 'Textures.GetTextures', 'params': params}
	raw = ''
	try:
		raw = control.jsonrpc(json.dumps(query)) or ''
		res = json.loads(raw)
		if res.get('error'):
			_PROBE['notes'].append('jsonrpc%s error %s' % (
				'' if filtered else '-nofilter', json.dumps(res['error'])[:160]))
			return []
		found = res.get('result', {}).get('textures') or []
		out = [t for t in found
		       if 'image.tmdb.org/t/p/' in (t.get('url') or '') and t.get('cachedurl')]
		if found and not out:
			_PROBE['notes'].append('jsonrpc returned %d rows, none from TMDb' % len(found))
		return out
	except Exception:
		_PROBE['notes'].append('jsonrpc unreadable: %s' % raw[:160])
		return []


def _tmdb_textures():
	"""Cascada, y se apunta cual gano. Antes esto era una sola llamada que
	devolvia [] tanto si la cache estaba vacia como si la consulta habia
	fallado, y el informe decia lo mismo en los dos casos. Que un diagnostico
	no distinga "no hay nada" de "no he podido mirar" es el peor fallo que
	puede tener, porque el segundo se lee como el primero y se cierra el tema."""
	_PROBE['source'], _PROBE['notes'], _PROBE['root'] = '', [], None

	rows = _textures_from_db()
	if rows:
		_PROBE['source'] = 'sqlite'
		return rows

	rows = _textures_from_jsonrpc(True)
	if rows:
		_PROBE['source'] = 'jsonrpc'
		return rows

	rows = _textures_from_jsonrpc(False)
	_PROBE['source'] = 'jsonrpc-nofilter' if rows else 'empty'
	return rows


def audit_artwork():
	"""Agrupa la caché por el tamano PEDIDO a TMDb y mide lo GUARDADO.

	v1.0.72 — se muestrea hasta conseguir _SAMPLE medidas VALIDAS, no hasta
	agotar _SAMPLE intentos. Antes se cogian los doce primeros de cada grupo y
	si los doce resultaban ser huerfanos —cosa que pasa justo despues de vaciar
	la carpeta Thumbnails, porque la base de texturas conserva los registros—
	el grupo entero se daba por no medible aunque tuviera cientos de ficheros
	buenos detras. El tope de intentos evita recorrer miles de entradas.
	"""
	groups = {}
	for tex in _tmdb_textures():
		match = _TMDB_SEG.search(tex.get('url') or '')
		if not match:
			continue
		seg = match.group(1).lower()
		entry = groups.setdefault(seg, {'count': 0, 'sample': []})
		entry['count'] += 1
		cached = tex.get('cachedurl')
		if cached and len(entry['sample']) < _MAX_TRIES:
			entry['sample'].append(cached)

	out = {}
	for seg, entry in groups.items():
		shots, sizes, missing = [], [], 0
		for cached in entry['sample']:
			if len(shots) >= _SAMPLE:
				break
			w, h, size, state = _measure(cached)
			if state == 'missing':
				missing += 1
				continue
			if w and h:
				shots.append((w, h, size))
			if size > 0:
				sizes.append(size)
		data = {'count': entry['count'], 'measured': len(shots),
		        'kb': _median(sizes) // 1024 if sizes else 0,
		        'missing': missing}
		data.update(_shape_split(shots))
		out[seg] = data
	return out


def _shape_split(shots):
	"""Reparte las medidas por FORMA y da un tamano que existe de verdad.

	v1.0.77 — antes esto era _median(anchos) x _median(altos), dos medianas
	calculadas por separado sobre la misma bolsa. Y esa bolsa mezcla posteres
	(altos) con fanart y stills (anchos), porque TMDb agrupa por el tamano
	PEDIDO —'original'— y no por el tipo de imagen. El resultado es un tamano
	compuesto que no tiene ninguna imagen: en un aparato real salio 1537x1500,
	que no es ni un poster ni un fanart. Antes ponia 1000x1500 y colaba solo
	porque por casualidad coincidia con un poster de verdad.

	El arreglo tiene dos mitades. La primera: el par (ancho, alto) no se
	rompe nunca — se ordena por area y se coge el del medio, asi que lo que
	se informa son las medidas de UNA imagen concreta de la muestra. La
	segunda: se separan las altas de las anchas y se informa de cada forma,
	porque en Original un poster ronda 2000x3000 y un fanart 3840x2160, y
	darlos juntos esconde precisamente el que mas pesa.

	Fanart y still siguen sin poder separarse entre si: los dos son 16:9 y
	nada en la URL dice cual es. Van juntos y con el nombre puesto.
	"""
	tall = sorted([s for s in shots if s[1] > s[0]], key=lambda s: s[0] * s[1])
	wide = sorted([s for s in shots if s[1] <= s[0]], key=lambda s: s[0] * s[1])
	out = {'w': 0, 'h': 0, 'shapes': []}
	for label, group in (('posters', tall), ('fanart/stills', wide)):
		if not group:
			continue
		w, h, _size = group[len(group) // 2]
		out['shapes'].append({'label': label, 'w': w, 'h': h, 'n': len(group)})
	if out['shapes']:
		biggest = max(out['shapes'], key=lambda s: s['n'])
		out['w'], out['h'] = biggest['w'], biggest['h']
	return out


def _cache_limits():
	"""(imageres, fanartres, declarado). v1.0.72 — ya no se lee aqui.

	Esto era una copia de la lectura de advancedsettings.xml, y desde que el
	nivel AUTO decide los tamaños a partir del tope, ese dato ES la entrada de
	la decision. Duplicarlo tendria el mismo defecto que duplicar la tabla de
	niveles: el informe podria decir 720 mientras los menus piden como si
	fueran otros. Se lee de tmdb.py, que es quien lo usa.
	"""
	from resources.lib.indexers import tmdb as tmdb_mod
	try:
		return tmdb_mod.cache_ceiling()
	except Exception:
		log_utils.error()
		return tmdb_mod.DEFAULT_IMAGERES, tmdb_mod.DEFAULT_FANARTRES, False


def _aspect(w, h):
	"""Nombre de la relacion de aspecto y si coincide con la de los XML del
	addon, que estan dibujados 16:9 en las dos carpetas."""
	if not w or not h:
		return '', True
	ratio = float(w) / float(h)
	known = ((16.0 / 9.0, '16:9'), (16.0 / 10.0, '16:10'), (4.0 / 3.0, '4:3'),
	         (3.0 / 2.0, '3:2'), (21.0 / 9.0, '21:9'), (5.0 / 4.0, '5:4'))
	name, best = '%.2f:1' % ratio, 99.0
	for value, label in known:
		diff = abs(ratio - value)
		if diff < best:
			name, best = label, diff
	return name, abs(ratio - 16.0 / 9.0) < 0.03


def gather():
	"""Recoge el estado. Sin efectos secundarios: no cambia ningun ajuste."""
	gui_w, gui_h = _gui_size()
	phys_w, phys_h, phys_raw = _physical_mode()

	# El flag ya escrito por gui_resolution durante el arranque; is_4k_display()
	# espera con timeout corto si todavia no estaba.
	try:
		is_4k = gui_resolution.is_4k_display()
	except Exception:
		is_4k = gui_h >= _4K

	path = control.homeWindow.getProperty(gui_resolution.DISPLAY_PATH_FLAG) or 'unknown'
	took = control.homeWindow.getProperty(gui_resolution.DISPLAY_MS_FLAG) or '?'

	from resources.lib.indexers import tmdb as tmdb_mod
	# v1.0.72 — antes se leia el ajuste a mano aqui. Con el ajuste nuevo eso
	# dejaba fuera la migracion desde el viejo, asi que el informe podia decir
	# Auto mientras los menus servian Original. Se llama a la misma funcion que
	# usa produccion, que es lo unico que garantiza que digan lo mismo.
	try:
		user_level = tmdb_mod._read_image_level()
	except Exception:
		log_utils.error()
		user_level = tmdb_mod.AUTO_LEVEL
	wide = gui_w >= 2400
	imageres, fanartres, res_declared = _cache_limits()
	# effective_sizes() es literalmente la que decide en produccion, y se le
	# pasa el tope ya leido para que el informe y los menus no puedan discrepar
	# ni siquiera por una lectura hecha en dos momentos distintos.
	sizes = tmdb_mod.effective_sizes(user_level, is_4k, wide, (imageres, fanartres))
	eff = tmdb_mod.effective_level(user_level, is_4k, wide)

	aspect_name, aspect_169 = _aspect(gui_w, gui_h)

	try:
		android = bool(xbmc.getCondVisibility('System.Platform.Android'))
	except Exception:
		android = False

	return {
		'gui_w': gui_w, 'gui_h': gui_h,
		'phys_w': phys_w, 'phys_h': phys_h, 'phys_raw': phys_raw,
		'is_4k': is_4k,
		'skin_set': _skin_set(gui_h),
		'path': path, 'took': took,
		'user_level': user_level, 'eff_level': eff, 'sizes': sizes, 'wide': wide,
		'fanarttv': control.setting('enable.fanarttv') == 'true',
		'gui_service': control.setting('gui.resolution.enabled') == 'true',
		'gui_target': control.setting('gui.resolution.target') or '0',
		'aspect': aspect_name, 'aspect_169': aspect_169,
		'imageres': imageres, 'fanartres': fanartres, 'res_declared': res_declared,
		'android': android,
		'art': audit_artwork(),
	}


def _clamped(art, ceiling=None):
	"""Tamanos pedidos cuya altura en disco no llega a lo que la imagen de
	origen daba de si. Devuelve [(segmento, medidas), ...] de mayor a menor
	desperdicio, y solo con muestras suficientes para no acusar a Kodi por
	dos ficheros sueltos.

	v1.0.74 — el grupo 'original' se compara contra el tope EN VIGOR, no contra
	un 1200 fijo. Con el numero fijo, un panel 1080p en Original guardaba el
	fanart a 1920x1080 —que es exactamente lo que ese panel puede mostrar— y el
	informe lo denunciaba como recortado. Ahora solo se acusa lo que de verdad
	se ha quedado por debajo del tope que el usuario tiene puesto, y ademas se
	mira POR FORMA: un poster de 2000x3000 y un fanart de 3840x2160 no se
	recortan al mismo numero, y hasta ahora se juzgaba a los dos por la medida
	compuesta del grupo.
	"""
	out = []
	limit = int(ceiling or _CLAMP_BELOW)
	for seg, data in art.items():
		if data['measured'] < 3 or not data['h']:
			continue
		if seg == 'original':
			shapes = data.get('shapes') or [{'h': data['h'], 'w': data['w'],
			                                 'label': '', 'n': data['measured']}]
			# Se pidio el maximo: si CUALQUIER forma se quedo por debajo del
			# tope actual, es que se cacheo con uno menor.
			if any(s['h'] < limit for s in shapes):
				out.append((seg, data))
		elif seg[0] in 'wh':
			try:
				asked = int(seg[1:])
			except ValueError:
				continue
			# Para wNNN el ancho pedido es explicito: si el guardado se queda
			# corto, el tope ha mordido igual.
			if seg[0] == 'w' and data['w'] and data['w'] < asked * 0.9:
				out.append((seg, data))
	out.sort(key=lambda item: -item[1]['count'])
	return out


# ─────────────────────────────────────────────────────────────────────────────
#  Recomendaciones
#
#  Cada una es (titulo, explicacion, accion). accion=None cuando el arreglo no
#  esta en manos del addon: entonces la explicacion lleva el camino exacto en
#  los ajustes de Kodi, que es mas util que un boton que no puede hacer nada.
# ─────────────────────────────────────────────────────────────────────────────

def recommendations(st):
	out = []

	# 1. Panel 4K con la GUI a 1080p. El caso de soporte mas comun y el mas
	#    invisible: todo "funciona", solo que a media resolucion.
	if st['phys_h'] >= _4K and st['gui_h'] and st['gui_h'] < _4K:
		if not st['gui_service']:
			out.append((
				'Kodi is running its interface at 1080p on a 4K screen',
				'Your display outputs %dx%d but Kodi draws at %dp, so this add-on '
				'uses its 1080p window layout and smaller artwork. Turning on the '
				'GUI resolution service lets the add-on switch Kodi to 2160p on '
				'startup.' % (st['phys_w'], st['phys_h'], st['gui_h']),
				[('gui.resolution.enabled', 'true'), ('gui.resolution.target', '1')]))
		elif st['gui_target'] != '1':
			out.append((
				'GUI resolution service is on but targeting 1080p',
				'Your display is 4K and the service is enabled, but its target is '
				'set to 1080p, so it keeps Kodi at the lower resolution.',
				[('gui.resolution.target', '1')]))
		else:
			out.append((
				'4K display, 1080p interface, service already set correctly',
				'The service is on and targeting 2160p, so Kodi should switch on '
				'the next start. If it does not, Kodi itself is refusing the mode: '
				'check Settings > System > Display > Resolution.',
				None))

	# 2. RETIRADA en la v1.0.72. Sugeria subir la calidad cuando la pantalla
	#    era 4K y el nivel fijo se quedaba corto. Con el ajuste reducido a Auto
	#    y Original ya no puede ocurrir: si el nivel no es Auto solo puede ser
	#    Original, cuyo nivel efectivo es el maximo, asi que la condicion
	#    "se queda corto" no se cumple nunca. Se deja anotado en vez de borrado
	#    a secas para que no vuelva a aparecer pensando que falta.

	# 3. Deteccion tardia: el primer menu pudo construirse antes de tiempo, y
	#    entonces la metacache guarda URLs de artwork pequeno que persisten.
	if st['path'] in ('thread', 'late'):
		out.append((
			'Screen detection did not answer immediately at startup',
			'The display driver took %s ms to report a size, so menus opened during '
			'that window may have cached small artwork URLs. Clearing the metadata '
			'cache rebuilds them: Settings > Cache > Clear metadata cache.'
			% st['took'],
			None))

	# 4. FanartTV en 4K se auto-activa; conviene decirlo, porque el ajuste
	#    seguira mostrandose apagado y parece un fallo.
	if st['is_4k'] and not st['fanarttv']:
		out.append((
			'FanartTV is switched off in settings but active anyway',
			'On a 4K screen the add-on turns FanartTV on by itself to use the extra '
			'high-resolution art. Nothing to fix: the settings toggle just does not '
			'reflect it.',
			None))

	# 5. v1.0.72 — el tope de cacheo. Medido, no supuesto.
	#
	#    v1.0.72 — el arreglo ya no es "baja a High". Auto elige por tipo el
	#    tamaño que sobrevive al tope, y High sigue siendo demasiado para un
	#    poster con tope 720: pide w780, que mide 1170 de alto y se recorta
	#    igual. Recomendar un nivel fijo era arreglar el sintoma con otro
	#    numero equivocado, solo que menos.
	clamped = _clamped(st['art'], st['imageres'])
	if clamped:
		seg, data = clamped[0]
		asked = 'full size' if seg == 'original' else seg
		# v1.0.74 — se citan las MISMAS formas que imprime la fila del
		# informe. La medida compuesta del grupo mezclaba posteres con
		# fanart y podia dar un tamano que no tiene ninguna imagen.
		sizes = ', '.join(
			'%dx%d %s' % (s['w'], s['h'], s['label'])
			for s in (data.get('shapes') or [])) or '%dx%d' % (data['w'], data['h'])
		where = ('Kodi shrinks artwork when it stores it, to %d pixels tall for '
		         'posters and %d for fanart.' % (st['imageres'], st['fanartres']))
		if st['android'] and not st['res_declared']:
			where += (' There is no advancedsettings.xml declaring a ceiling, so '
			          'these are Kodi\'s own defaults.')
		elif st['res_declared']:
			where += ' Those values come from your advancedsettings.xml.'

		# v1.0.72 — antes habia aqui una segunda rama que, si el nivel no era
		# Auto, ofrecia cambiarlo a Auto. Con el ajuste reducido eso significaba
		# proponerle a quien eligio Original justo lo contrario de lo que pidio.
		# Su caso lo cubre ahora la recomendacion 7, que ofrece lo que de verdad
		# hace falta: subir el tope para que Original quepa entero.
		#
		# v1.0.74 — dos correcciones al texto, las dos vistas en un aparato
		# real (Galaxy Tab S8+, 4-sep-2026):
		#
		#   El titular decia 'left over from a LARGER size' y es al reves. Lo
		#   que queda en disco son restos de un tope MAS PEQUENO: el 720 de
		#   fabrica de Kodi, que sobre un poster 2:3 deja exactamente los
		#   480x720 que salieron alli, cacheados antes de que el
		#   advancedsettings.xml existiera.
		#
		#   Y el remedio era el equivocado. La cache de metadatos guarda las
		#   URLs de TMDb, no las imagenes; las texturas viven en Textures13.db
		#   y en la carpeta Thumbnails del userdata, y vaciar la de metadatos
		#   no las toca. Quien seguia el consejo no veia ningun cambio y
		#   concluia que el tope no funcionaba — el consejo confirmaba una
		#   sospecha falsa, que es la peor forma posible de fallar.
		#
		# La coletilla de Android tambien se va: decia que alli el tope 'se
		# ignora', y el log del aparato muestra a Kodi cargando y aplicando el
		# fichero sin problema.
		out.append((
			'Some cached artwork was stored under a smaller ceiling',
			'%d images on disk were requested at %s and measure %s, about '
			'%d KB each. %s These copies were cached before the current ceiling '
			'applied, and Kodi keeps reusing them as they are. They live in '
			'Textures13.db and the Thumbnails folder of your userdata, not in '
			'this add-on, so clearing the metadata cache will NOT rebuild them. '
			'Delete Kodi\'s own texture cache to have them fetched again at the '
			'size in use now.'
			% (data['count'], asked, sizes, data['kb'], where),
			None))

	# 6. v1.0.72 — pantallas que no son 16:9. Las dos carpetas de XML del addon
	#    lo son, asi que aqui no hay nada que arreglar desde los ajustes: es
	#    una explicacion de por que el borde no encaja del todo.
	if st['aspect'] and not st['aspect_169']:
		out.append((
			"Your screen is %s and this add-on's screens are 16:9" % st['aspect'],
			'Kodi fits the add-on\'s own windows to your screen, so you may see a '
			'band at the edges or slightly different spacing than the menus around '
			'them. Nothing is broken and nothing is cut off.',
			None))

	# 8. El escenario "tengo un 4K de verdad, quiero lo mejor".
	#
	#    Se conserva la entrada porque el usuario merece saber en que punto
	#    esta, pero ya NO ofrece cambiar nada: en 4K el tope de Auto y el de
	#    Original son el mismo 2160, Auto pide 'original' a TMDb igual que
	#    Original, y Kodi guarda todo lo que la pantalla puede dibujar. Ofrecer
	#    el cambio seria vender una mejora inexistente; decir "no lo hagas"
	#    seria tratar al usuario como si no supiera elegir. Se le dice lo que
	#    hay.
	# v1.0.82 — los avisos del perfil ESTANDAR.
	#
	#    Los dos perfiles no miran la pantalla a proposito, asi que es AQUI
	#    donde el usuario se entera de si su eleccion le cuadra. Los tres casos
	#    van como INFO y ninguno se aplica solo: no son defectos, son
	#    decisiones suyas con consecuencias que conviene que vea.
	if st['user_level'] == _STANDARD:
		try:
			from resources.lib.indexers.tmdb import standard_poster as _sp
			from resources.lib.indexers.tmdb import standard_fanart as _sf
			poster_name, fanart_name = _sp(), _sf()
		except Exception:
			poster_name, fanart_name = 'w500', 'w1280'
		poster_h = _STANDARD_POSTER_HEIGHT.get(poster_name, 750)

		# Fanart en original con un tope bajo es el mismo desperdicio que en
		# posters, pero por otra puerta: TMDb sirve 3840x2160 y Kodi lo guarda
		# a <fanartres>. Se avisa aparte porque el ajuste es aparte.
		if fanart_name == 'original' and st['fanartres'] < 1400:
			out.append((
				'Fanart is set to original but Kodi keeps it at %d' % st['fanartres'],
				'Original fanart arrives at about 3840x2160 and is shrunk to %d pixels '
				'tall as it is stored, so most of each download is thrown away. Either '
				'raise the fanart limit in your advancedsettings.xml, or set Fanart size '
				'back to w1280, which is 1280x720 and roughly ten times smaller.'
				% st['fanartres'],
				None))

		if st['is_4k']:
			out.append((
				'Your screen is 4K and artwork quality is on Standard',
				'Standard keeps posters at %d pixels tall, which is well under what '
				'a 4K panel draws, so artwork will look soft on the large poster '
				'card and on full-screen fanart. On this screen Maximum is the one '
				'that matches: it requests full-size artwork and keeps it. The files '
				'are much larger, so keep an eye on Tools > Cache Functions.'
				% poster_h,
				None))
		elif poster_h > st['imageres'] * 1.25:
			out.append((
				'Standard is downloading more than Kodi will keep',
				'Posters are requested at %s, about %d pixels tall, but Kodi shrinks '
				'every image to %d as it stores it, so most of each download is '
				'decoded and thrown away while a grid is being drawn. Either raise '
				'the poster limit in your advancedsettings.xml to %d, or drop the '
				'poster size to the smaller option.'
				% (poster_name, poster_h, st['imageres'], poster_h),
				None))
		elif st['imageres'] > poster_h * 1.35:
			bigger = 'w780, about 1170 pixels tall' if poster_name == 'w500' else 'Maximum'
			out.append((
				'Your storage limit allows better artwork than you are asking for',
				'Kodi will keep images up to %d pixels tall, but Standard is only '
				'requesting %s at about %d. Nothing is wasted and nothing is broken, '
				'but there is headroom you are not using: %s would fill it.'
				% (st['imageres'], poster_name, poster_h, bigger),
				None))
		else:
			out.append((
				'Standard fits your screen and your storage limit',
				'Posters come in at %s, about %d pixels tall, and Kodi keeps images '
				'up to %d, so what is downloaded is what is stored and what is drawn. '
				'Maximum is there if you would rather keep artwork beyond what this '
				'panel shows, at the cost of much larger files.'
				% (poster_name, poster_h, st['imageres']),
				None))

	# 7. El tope de Kodi por debajo de lo que las pantallas del addon dibujan.
	#
	#    Este es el unico hallazgo cuyo arreglo NO esta en los ajustes del
	#    addon: el tope vive en advancedsettings.xml, que es de Kodi. Se ofrece
	#    igualmente porque es la diferencia entre dibujar la ficha grande de
	#    poster a media resolucion o entera, y nadie lo va a encontrar solo.
	#
	#    Los numeros no son el maximo a proposito. La ficha grande de poster
	#    mide 972x1458 y el fanart llena la pantalla: 1080 y 2160 los cubren de
	#    sobra. Poner 3000 traeria posters de 2000x3000, casi 23 MB por textura
	#    en memoria de video y mas de 400 en un grid lleno, que es justo el
	#    gasto que Kodi evita por defecto.
	on_original = st['user_level'] == _ORIGINAL
	wanted, wanted_fanart = _wanted_ceiling(st)
	if st['imageres'] < wanted or st['fanartres'] < wanted_fanart:
		if on_original:
			title = 'Original artwork is being cut down to %dx%d' % (
				int(round(st['imageres'] * 2 / 3.0)), st['imageres'])
			# v1.0.74 — se nombran los DOS numeros que se van a escribir. El
			# texto anterior hablaba solo del limite del poster y terminaba con
			# "todo lo que este panel puede dibujar" mientras la accion tocaba
			# tambien el del fanart, y en un panel 1080p esa frase ademas no era
			# exacta: Original pide a proposito por encima de lo que la pantalla
			# muestra hoy.
			body = (
				'Image quality is set to Original, so full-size artwork is being '
				'requested, but Kodi shrinks every image to %d pixels tall for '
				'posters and %d for fanart as it stores it. A full-size poster '
				'arrives at roughly 2000x3000 and is kept at about %dx%d. Raising '
				'both limits to %d is what Original means: artwork kept at 4K size, '
				'which is everything a screen can show today and stays right if you '
				'change screen tomorrow. The files are larger and Kodi never clears '
				'them by itself. Anything already in your advancedsettings.xml is '
				'kept, and it takes effect after a restart.'
				% (st['imageres'], st['fanartres'],
				   int(round(st['imageres'] * 2 / 3.0)), st['imageres'], wanted))
		else:
			title = 'Kodi stores artwork smaller than these screens draw it'
			body = (
				'Kodi shrinks every image as it stores it, currently to %d pixels '
				'tall for posters and %d for fanart. The largest poster panel in '
				'this add-on is 972x1458 and the background fills your whole '
				'screen, so both are drawn from about half the detail they could '
				'have. Raising both limits to %d matches them to your screen '
				'exactly, without going overboard. This writes two lines into '
				'Kodi\'s own advancedsettings.xml, keeps anything already in it, '
				'and takes effect after a restart.'
				% (st['imageres'], st['fanartres'], wanted))
		out.append((title, body,
		            [(_CEILING_ACTION, '%d|%d' % (wanted, wanted_fanart))]))

	return out


def _report_rows(st):
	rows = []

	gui = '%dx%d' % (st['gui_w'], st['gui_h']) if st['gui_h'] else 'not reported'
	phys = st['phys_raw'] or 'not reported'
	mismatch = bool(st['phys_h'] >= _4K and st['gui_h'] and st['gui_h'] < _4K)
	shape = ''
	if st['aspect']:
		shape = '   Shape: %s' % _color(
			st['aspect'], GREEN if st['aspect_169'] else ATTN)
	rows.append((
		'Screen',
		'Kodi interface: %s   Display output: %s%s' % (
			_color(gui, ATTN if mismatch else GREEN), _color(phys, GREEN), shape)))

	rows.append((
		'Detected as',
		'%s   %s' % (
			_color('4K' if st['is_4k'] else '1080p or lower', GREEN),
			_color('(detection path: %s, %s ms)' % (st['path'], st['took']), GREY))))

	# El punto que mas se malinterpreta. La version anterior describia el
	# COMO ("double coordinates, font bodies") en vez del QUE, y encima se
	# cortaba por ancho. Ahora dice que hay dos versiones, cual te ha tocado y
	# por que, que es lo unico que el usuario necesita saber.
	if st['skin_set'] == '2160p':
		layout_text = '%s - %s' % (
			_color('2160p', GREEN),
			_color("you are getting the 4K version of this add-on's own screens. "
			       'Menus, text and spacing are drawn at full size instead of a '
			       '1080p layout blown up to fit.', GREY))
	else:
		layout_text = '%s - %s' % (
			_color('1080i', GREEN),
			_color('this add-on carries two versions of its own screens, one built '
			       'for 1080p and one for 4K, and Kodi picks by the resolution the '
			       'interface runs at. Yours is on the 1080p one.', GREY))
	rows.append(("This add-on's own screens", layout_text))

	# Los tres primeros solo aparecen en una instalacion que aun no haya
	# migrado: desde la v1.0.74 el ajuste solo ofrece Auto y Original.
	# El 5 es STANDARD_LEVEL. Sin el, el informe imprimia 'Setting: ?' para el
	# perfil que usa casi todo el mundo (v1.0.82).
	level_names = {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Maximum', 4: 'Auto', 5: 'Standard'}
	rows.append((
		'Artwork quality',
		'Setting: %s   In use: posters %s, fanart %s, stills %s' % (
			_color(level_names.get(st['user_level'], '?'), GREEN),
			_color(st['sizes']['poster'], GREEN if st['eff_level'] >= 3 else ATTN),
			st['sizes']['fanart'], st['sizes']['still'])))

	# v1.0.72 — la unica fila del informe que no lee un ajuste sino un fichero.
	# Va justo debajo de la calidad de imagen a proposito: arriba esta lo que
	# el addon pide, aqui lo que queda de ello.
	art = st['art']
	if not art:
		if _PROBE['notes']:
			rows.append((
				'Artwork on disk',
				_color('the texture cache could not be read - see the log', ATTN)))
		else:
			rows.append((
				'Artwork on disk',
				_color('nothing cached yet - browse a few titles and run this again',
				       GREY)))
	else:
		clamped = dict(_clamped(art, st['imageres']))
		lines = []
		ordered = sorted(art.items(), key=lambda item: -item[1]['count'])
		for seg, data in ordered[:4]:
			if data['measured']:
				# v1.0.77 — una linea por forma. Un solo numero para un grupo
				# que mezcla posteres y fanart obliga a inventarse una media
				# entre dos cosas que no se parecen, y en Original la
				# diferencia entre 2000x3000 y 3840x2160 es justo el dato que
				# el usuario necesita para decidir.
				parts = []
				for shape in data.get('shapes') or []:
					parts.append('%s %s' % (
						_color('%dx%d' % (shape['w'], shape['h']),
						       ATTN if seg in clamped else GREEN),
						_color('(%s)' % shape['label'], GREY)))
				measured = _color(', ', GREY).join(parts) if parts else _color(
					'%dx%d' % (data['w'], data['h']),
					ATTN if seg in clamped else GREEN)
				if data['kb'] > 0:
					measured += _color('   median %d KB' % data['kb'], GREY)
			elif data.get('missing'):
				# Restos de un vaciado de la carpeta Thumbnails: la base de
				# texturas conserva la fila aunque el fichero ya no exista.
				measured = _color('files no longer on disk', GREY)
			else:
				measured = _color('could not be measured', GREY)
			lines.append('%s   %s' % (
				_color('%s requested, %d cached' % (seg, data['count']), GREY),
				measured))
		rows.append(('Artwork on disk', ('[CR]' + IND).join(lines)))

	rows.append((
		'Storage ceiling',
		'%s   %s' % (
			_color('posters %dpx, fanart %dpx' % (st['imageres'], st['fanartres']),
			       GREEN),
			_color('from your advancedsettings.xml' if st['res_declared']
			       else "Kodi's defaults; no advancedsettings.xml value found",
			       GREY))))

	rows.append((
		'FanartTV',
		_color('on', GREEN) if (st['fanarttv'] or st['is_4k'])
		else _color('off', GREY)))

	return rows


def _report(st, recs):
	"""El informe entero en BBCode, para la ventana propia del addon."""
	lines = []
	add = lines.append

	for title, text in _report_rows(st):
		add('[B]%s[/B]' % title)
		add(IND + text)
		add('')

	applicable = [r for r in recs if r[2]]
	if not recs:
		# v1.0.72 — un test que se calla no distingue entre "esta todo bien" y
		# "no he mirado". Se confirma con los numeros concretos: que la
		# interfaz va a la resolucion del panel, y que el tope de Kodi cubre la
		# ranura donde este addon dibuja el poster, que es 0,675 veces la
		# altura de la pantalla.
		slot = int(round(max(st['gui_h'], st['phys_h']) * _POSTER_SLOT_RATIO))
		add('[B]%s[/B]' % _color('Nothing to change', GREEN))
		same = st['gui_h'] and st['phys_h'] and st['gui_h'] == st['phys_h']
		add(IND + _color(
			'Kodi draws at %sx%s and your display outputs %sx%s%s.'
			% (st['gui_w'], st['gui_h'], st['phys_w'], st['phys_h'],
			   ', the same' if same else ''), GREY))
		add(IND + _color(
			'The poster panel needs %d pixels of height and Kodi keeps %d, so '
			'nothing is being cut down. Artwork quality is on %s.'
			% (slot, st['imageres'],
			   'Maximum' if st['user_level'] == _ORIGINAL else 'Standard'), GREY))
		return '[CR]'.join(lines)

	add('[B]%s[/B]' % _color('What to change', GREEN))
	add('')
	for title, text, action in recs:
		col = ATTN if action else GREY
		# FIX significa \"esto se arregla desde aqui\"; INFO, \"esto depende de
		# Kodi o del aparato y la explicacion trae el camino exacto\". Antes la
		# diferencia era el COLOR de un punto, que es justo lo que no se ve en
		# un skin que pinte el texto a su manera.
		add('%s   [B]%s[/B]' % (_color(TAG_FIX if action else TAG_INFO, col),
		                        _color(title, col)))
		add(IND + _color(text, GREY))
		add('')

	if applicable:
		add(_color('%d of these can be applied from here; you will be asked when '
		           'you close this report. The rest are explained above and left '
		           'alone.' % len(applicable), GREY))
	return '[CR]'.join(lines)


def _show(heading, text):
	"""Ventana propia. v1.0.67: antes era Dialog().select(useDetails=True), que
	es del SKIN. En Arctic Fuse 3 el area de detalle se pintaba sobre la columna
	de titulos y en AeonNox faltaba el glifo de la vineta. Con textviewer.xml la
	maqueta viaja dentro del paquete, es igual en todos los skins, y el textbox
	ajusta linea y hace scroll: las explicaciones largas de las recomendaciones
	ya no se cortan por ancho."""
	try:
		from resources.lib.windows.textviewer import TextViewerXML
		viewer = TextViewerXML('textviewer.xml',
		                       control.addonPath('plugin.video.luc_kodi'),
		                       heading=heading, text=text)
		viewer.run()
		del viewer
		return
	except Exception:
		log_utils.error()
	try:
		xbmcgui.Dialog().textviewer(heading, _plain(text))
	except Exception:
		log_utils.error()


def _plain(text):
	"""Sin BBCode, para el plan B: el visor de Kodi no lo interpreta."""
	out, depth = [], 0
	for ch in text.replace('[CR]', '\n'):
		if ch == '[':
			depth += 1
		elif ch == ']':
			if depth:
				depth -= 1
		elif not depth:
			out.append(ch)
	return ''.join(out)


def run():
	# v1.0.72 — gather() ya no es instantaneo: abre hasta doce texturas por
	# tamano para medirlas. Sigue siendo cosa de un momento, pero lo suficiente
	# para que sin aviso pareciera que la pulsacion no ha hecho nada.
	try:
		control.busy()
		try:
			st = gather()
		finally:
			control.hide()
	except Exception:
		log_utils.error()
		control.okDialog(message='Could not read the display information.')
		return

	recs = recommendations(st)
	art_log = ' '.join(
		'%s=%dx%d/%d' % (seg, data['w'], data['h'], data['count'])
		for seg, data in sorted(st['art'].items())) or 'none'
	control.log('[ luc_kodi ] display_test: gui=%sx%s (%s) phys=%sx%s is_4k=%s skin=%s '
	            'level=%s->%s path=%s ceiling=%s/%s android=%s art[%s] via=%s root=%s recs=%d'
	            % (st['gui_w'], st['gui_h'], st['aspect'], st['phys_w'], st['phys_h'],
	               st['is_4k'], st['skin_set'], st['user_level'], st['eff_level'],
	               st['path'], st['imageres'], st['fanartres'], st['android'],
	               art_log, _PROBE['source'] or '?', _PROBE['root'] or 'none',
	               len(recs)), LOGINFO)
	# Incondicional y en LOGERROR, como el motor de Gemini: si la lectura de la
	# cache falla, el sitio donde hace falta verlo es un log de usuario que no
	# lleva el registro detallado activado.
	for note in _PROBE['notes']:
		control.log('[ luc_kodi ] display_test: %s' % note, log_utils.LOGERROR)

	_show('Display test', _report(st, recs))

	# La pregunta va DESPUES de cerrar el informe, no como primera fila de una
	# lista. Aplicar ajustes era una fila mas entre las filas de datos, y una
	# fila que ademas cambiaba cosas al pulsarla: se podia disparar sin querer
	# navegando. Ahora se lee primero y se decide despues, y para decir que no
	# basta con no hacer nada.
	applicable = [r for r in recs if r[2]]
	if not applicable:
		return
	if control.yesnoDialog(
			'Apply the %d recommended setting%s?[CR][CR]Only this add-on\'s own '
			'settings are touched. Everything explained as INFO is left alone.'
			% (len(applicable), '' if len(applicable) == 1 else 's'),
			'', '', heading='Display test'):
		_apply(applicable)


# Marca que distingue una accion sobre advancedsettings.xml de un ajuste
# normal del addon. Se reconoce por el nombre porque la lista de acciones es
# una lista de pares (id, valor) y no merece cambiar su forma por un caso.
_CEILING_ACTION = '__kodi_advancedsettings__'


def _write_ceiling(imageres, fanartres):
	"""Escribe <imageres> y <fanartres> en el advancedsettings.xml de Kodi.

	Este es el UNICO sitio del addon que toca un fichero de Kodi y no suyo, asi
	que se hace con dos cuidados:

	  1. Se FUSIONA, nunca se sobrescribe. Si el fichero ya existe puede tener
	     ajustes de red, de cache de video o de base de datos que costaron una
	     tarde, y perderlos por subir una resolucion de imagen seria un
	     desastre desproporcionado. Solo se reemplazan esas dos etiquetas, o se
	     insertan si no estaban.
	  2. Si el fichero existe pero no se puede leer o no tiene la etiqueta
	     raiz, no se escribe nada. Preferir no hacer nada a dejar un
	     advancedsettings.xml roto, que impide arrancar bien a Kodi entero.

	Devuelve (ok, mensaje).
	"""
	# v1.0.74 — masterprofile, no profile: es de donde Kodi carga el fichero.
	from resources.lib.indexers import tmdb as _tmdb_mod
	path = control.transPath(_tmdb_mod.ADVANCEDSETTINGS_PATH)
	raw = ''
	try:
		if control.existsPath(path):
			fh = control.openFile(path)
			try:
				raw = fh.read() or ''
			finally:
				fh.close()
			if '<advancedsettings' not in raw:
				return False, ('Your advancedsettings.xml could not be read, so '
				               'nothing was changed. Edit it by hand instead.')
	except Exception:
		log_utils.error()
		return False, 'Your advancedsettings.xml could not be read.'

	if not raw.strip():
		raw = '<advancedsettings version="1.0">\n</advancedsettings>\n'

	# v1.0.74 — el atributo version. Kodi aplica el fichero sin el, pero deja
	# en el log 'warning <CSettingsManager>: missing version attribute', y ese
	# aviso es exactamente lo que mira alguien que sospecha que su tope no se
	# esta aplicando. Se anade tambien a un fichero que ya existiera sin el:
	# es lo que Kodi documenta y no cambia nada mas del contenido.
	if re.search(r'<advancedsettings(?![^>]*\bversion=)', raw):
		raw = re.sub(r'<advancedsettings(?![^>]*\bversion=)',
		             '<advancedsettings version="1.0"', raw, count=1)

	# v1.0.74 — raiz autocerrada. Un fichero escrito como <advancedsettings />
	# no tiene etiqueta de cierre sobre la que insertar, asi que las dos
	# etiquetas no entraban, no se reemplazaba nada, y la funcion devolvia
	# exito igual: se le pedia al usuario que reiniciara Kodi por un cambio que
	# no se habia hecho. Se expande antes de tocar nada.
	raw = re.sub(r'<advancedsettings([^>]*?)/>',
	             r'<advancedsettings\1>\n</advancedsettings>', raw, count=1)

	for tag, value in (('imageres', imageres), ('fanartres', fanartres)):
		pattern = r'<%s>\s*\d+\s*</%s>' % (tag, tag)
		replacement = '<%s>%d</%s>' % (tag, value, tag)
		if re.search(pattern, raw):
			raw = re.sub(pattern, replacement, raw)
		else:
			raw = re.sub(r'</advancedsettings>',
			             '  %s\n</advancedsettings>' % replacement, raw, count=1)

	# Y se comprueba que de verdad estan antes de escribir. Un informe que dice
	# "hecho" sin haber hecho nada es peor que un fallo, porque cierra el tema.
	for tag, value in (('imageres', imageres), ('fanartres', fanartres)):
		if '<%s>%d</%s>' % (tag, value, tag) not in raw:
			return False, ('Your advancedsettings.xml has a shape this add-on '
			               'will not edit safely, so nothing was changed. Add '
			               '<imageres>%d</imageres> and <fanartres>%d</fanartres> '
			               'by hand.' % (imageres, fanartres))

	try:
		fh = control.openFile(path, 'w')
		try:
			fh.write(raw)
		finally:
			fh.close()
	except Exception:
		log_utils.error()
		return False, 'Your advancedsettings.xml could not be written.'

	# La window property guarda el tope leido; sin invalidarla el propio test
	# seguiria informando del valor viejo hasta reiniciar.
	try:
		from resources.lib.indexers import tmdb as tmdb_mod
		control.homeWindow.clearProperty(tmdb_mod._CEILING_PROP)
	except Exception:
		pass
	return True, ''


def _apply(applicable):
	changed, notes = [], []
	for title, _text, action in applicable:
		for sid, value in action:
			if sid == _CEILING_ACTION:
				image, fanart = [int(v) for v in value.split('|')]
				ok, message = _write_ceiling(image, fanart)
				if ok:
					changed.append('advancedsettings.xml')
					notes.append(
						'Kodi will store artwork up to %d pixels tall for posters '
						'and %d for fanart once you RESTART it. Artwork already '
						'cached keeps its old size: it lives in Kodi\'s own texture '
						'cache (Textures13.db and the Thumbnails folder), so delete '
						'that to have it fetched again at the new size.' % (image, fanart))
				else:
					notes.append(message)
				continue
			try:
				control.setSetting(sid, value)
				changed.append(sid)
			except Exception:
				log_utils.error()
	if not changed:
		control.okDialog('Display test',
		                 (' '.join(notes)) or 'Nothing could be changed.')
		return
	control.log('[ luc_kodi ] display_test: applied %s' % ', '.join(changed), LOGINFO)
	# La resolucion GUI solo se toca al arrancar, y el artwork ya cacheado
	# conserva las URLs viejas. Decirlo aqui evita el "no ha hecho nada".
	#
	# v1.0.72 — el argumento era heading=, y control.okDialog() se declara
	# okDialog(title, message). Venia asi desde que existe el fichero y nunca
	# habia saltado porque este es el ultimo paso de la unica rama que solo se
	# recorre cuando alguien ACEPTA una recomendacion, y hasta ahora el test no
	# habia tenido ninguna que mereciera aceptarse.
	body = ('Applied %d change%s.[CR][CR]If the interface resolution changed, '
	        'restart Kodi for it to take effect. Artwork already cached keeps '
	        'its old size until you clear the metadata cache.'
	        % (len(changed), '' if len(changed) == 1 else 's'))
	if notes:
		body += '[CR][CR]' + '[CR][CR]'.join(notes)
	control.okDialog('Display test', body)
