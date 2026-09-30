# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — provider_test.py (v1.0.64)

	Test de proveedores. Inspirado en speedtest.py de plugin.video.pov, pero
	midiendo TRES cosas por separado en vez de una.

	pov cuenta cuantos resultados devuelve cada proveedor y ordena por tiempo.
	El problema es que un 0 ahi no dice nada: no sabes si al proveedor le falta
	el token, si el host esta caido, o si esa pelicula simplemente no esta.
	Aqui se separan:

	  CONFIGURADO  ¿hay credenciales? — se lee el ajuste de token del proveedor.
	  ALCANZABLE   ¿responde el host? — peticion corta, independiente del titulo.
	  PRODUCTIVO   ¿devuelve resultados? — sources() contra un IMDb fijo.

	Un proveedor CONFIGURADO + ALCANZABLE + 0 resultados es un catalogo sin esa
	peli. CONFIGURADO + NO alcanzable es una instancia caida. NO configurado es
	cosa del usuario. Son tres arreglos distintos y por eso son tres columnas.

	El tiempo por proveedor va aparte, y es lo que habria cantado a la cara que
	AIOStreams tardaba de mas en las pasadas de packs.

	v1.0.63 — se anaden dos medidas mas, porque el numero de resultados a secas
	responde "cuanto" pero no "para que sirve":

	  RESOLUCION   cuantos de esos ficheros son 4K, 1080p, 720p o SD. Un
	               proveedor que devuelve 200 archivos de los que tres son 4K y
	               otro que devuelve 40 con veinte en 4K salen igual de bien en
	               la columna de resultados, y no son lo mismo en absoluto.

	  EXCLUSIVOS   cuantos de sus hashes no los ofrece ningun otro proveedor de
	               la tanda. Es la medida que de verdad decide si merece la pena
	               tenerlo activado: seis caminos distintos llegan a Torrentio y
	               a los hashes de Zilean/DMM, asi que hay proveedores cuyo
	               volumen es alto y cuya aportacion propia es casi cero.

	v1.0.64 — las dos medidas de arriba se calculaban bien desde el primer dia y
	casi nunca se veian. El area de detalle de DialogSelect pinta DOS lineas por
	fila y corta la tercera sin avisar, y con las etiquetas largas la linea de
	estado ya se comia las dos. Salia solo en las filas que por casualidad
	quedaban cortas —DMM, peerflix— y de ahi la impresion de que unos
	proveedores informaban y otros no. Etiquetas abreviadas: una linea de
	estado, una linea de desglose, y entran todas.

	v1.0.67 — el informe se saca de DialogSelect y pasa a la ventana de texto
	propia del addon. Hasta aqui el formato lo decidia el skin activo, porque
	DialogSelect.xml es suyo: en Estuary y Nimbus se veia entero, en Arctic
	Fuse 3 el area de detalle se pintaba encima de la columna de nombres, y en
	AeonNox la vineta '●' salia como cuadro de glifo ausente porque su fuente
	no trae ese bloque Unicode. Mismo codigo, cuatro resultados. Con
	textviewer.xml la maqueta viaja dentro del paquete y es la misma en los
	cuatro; la vineta pasa a ser una palabra ASCII, que ninguna fuente puede
	fallar; y el textbox ajusta linea y hace scroll, asi que el limite de dos
	lineas que en 1.0.64 obligo a abreviar etiquetas deja de existir.

	La resolucion NO se vuelve a parsear aqui: se lee la clave 'quality' que ya
	pone cada scraper via source_utils.get_release_quality(), que es la misma que
	luego usa el ranker. Si se calculara aparte, el test podria decir una cosa y
	la lista de fuentes otra, y entonces el test no valdria para nada.
"""

import json
import threading
import time

import xbmc
import xbmcgui

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.jacksparrow import client

LOGINFO = log_utils.LOGINFO

# Pelicula de prueba por defecto. Popular y con anos a la espalda a proposito:
# si un proveedor no la tiene, el problema es del proveedor, no del catalogo.
DEFAULT_TEST = {
	'imdb': 'tt0468569', 'title': 'The Dark Knight', 'year': '2008',
}

# ─────────────────────────────────────────────────────────────────────────────
#  Catalogo de prueba
#
#  Un unico titulo fijo mide un unico caso. Una peli de 2008 muy pirateada dice
#  poco de como se porta un proveedor con un estreno reciente, con un remux de
#  80 GB o con una serie de los ochenta, que son escenarios con catalogos
#  distintos y proveedores distintos detras. Seis categorias, y dentro de cada
#  una un pequeno grupo que ROTA en cada ejecucion: asi dos pasadas seguidas no
#  miden lo mismo y un proveedor no puede parecer bueno por tener un solo
#  titulo popular en cache.
#
#  Para series se manda temporada 1 episodio 1: es el episodio que existe
#  siempre y el que mas probablemente este publicado por todos.
# ─────────────────────────────────────────────────────────────────────────────

def _movie(imdb, title, year):
	return {'imdb': imdb, 'title': title, 'year': str(year),
	        'aliases': [], 'localtitle': ''}


def _show(imdb, title, year):
	return {'imdb': imdb, 'tvshowtitle': title, 'title': 'Episode 1',
	        'year': str(year), 'season': '1', 'episode': '1',
	        'aliases': [], 'localtitle': '', 'premiered': ''}


TEST_CATALOG = (
	('1  Movie — something recent', (
		_movie('tt15239678', 'Dune: Part Two', 2024),
		_movie('tt6263850', 'Deadpool & Wolverine', 2024),
		_movie('tt9218128', 'Gladiator II', 2024),
		_movie('tt1262426', 'Wicked', 2024))),
	('2  TV show — something recent', (
		_show('tt2788316', 'Shogun', 2024),
		_show('tt12637874', 'Fallout', 2024),
		_show('tt13495410', 'The Penguin', 2024),
		_show('tt3581920', 'The Last of Us', 2023))),
	('3  Movie — the best quality out there', (
		_movie('tt1856101', 'Blade Runner 2049', 2017),
		_movie('tt1160419', 'Dune', 2021),
		_movie('tt0816692', 'Interstellar', 2014),
		_movie('tt1392190', 'Mad Max: Fury Road', 2015))),
	('4  TV show — the best quality out there', (
		_show('tt7366338', 'Chernobyl', 2019),
		_show('tt0185906', 'Band of Brothers', 2001),
		_show('tt5491994', 'Planet Earth II', 2016),
		_show('tt0944947', 'Game of Thrones', 2011))),
	('5  Movie — something older', (
		_movie('tt0081505', 'The Shining', 1980),
		_movie('tt0083658', 'Blade Runner', 1982),
		_movie('tt0090605', 'Aliens', 1986),
		_movie('tt0095016', 'Die Hard', 1988))),
	('6  TV show — something older', (
		_show('tt0098936', 'Twin Peaks', 1990),
		_show('tt0106179', 'The X-Files', 1993),
		_show('tt0092455', 'Star Trek: The Next Generation', 1987),
		_show('tt0098904', 'Seinfeld', 1989))),
)

ROTATION_SETTING = 'provider.test.rotation'


def pick_content():
	"""Menu de categorias. Devuelve el dict de datos o None si se cancela."""
	labels = [c[0] for c in TEST_CATALOG] + ['7  Enter an IMDb id myself']
	choice = control.dialog.select('What should the providers be asked for?', labels)
	if choice < 0:
		return None
	if choice == len(TEST_CATALOG):
		imdb = control.dialog.input('IMDb id of a movie to test with', DEFAULT_TEST['imdb'])
		if not imdb:
			return None
		imdb = imdb.strip()
		if imdb != DEFAULT_TEST['imdb']:
			# Titulo desconocido: check_title() descartaria todo. Se avisa en vez
			# de devolver ceros que parecerian fallos de los proveedores.
			control.okDialog(message='Using a custom IMDb id: titles are matched by name, '
			                         'so results may read as 0 unless the title matches. '
			                         'The Configured and Reachable columns stay valid.')
		return {'imdb': imdb, 'title': DEFAULT_TEST['title'],
		        'year': DEFAULT_TEST['year'], 'aliases': [], 'localtitle': ''}

	pool = TEST_CATALOG[choice][1]
	try:
		turn = int(control.setting(ROTATION_SETTING) or '0')
	except ValueError:
		turn = 0
	try:
		control.setSetting(ROTATION_SETTING, str((turn + 1) % 1000))
	except Exception:
		pass
	return dict(pool[turn % len(pool)])

# Ajuste que guarda el token de cada proveedor Custom, para la columna
# CONFIGURADO. Los que no aparecen aqui no llevan credenciales propias.
TOKEN_SETTING = {
	'torz':        'torz.config',
	'comet':       'comet.config',
	'sootio':      'sootio.config',
	'meteor':      'meteor.config_token',
	'mediafusion': 'mediafusion.secret',
	# v1.0.91: con instancia propia puede bastar la URL del manifest
	'aiostreams':  ('aiostreams.uuid', 'aiostreams.custom_url'),
	# v1.0.75 -- torboxnews no es Custom pero SI tiene credencial. Sin esta
	# entrada la columna Cfg salia '--' y el test parecia decir que no la usa.
	'torboxnews':  'torbox.token',
}

# v1.0.69 — el test se estorbaba a si mismo. Medido en el log del 22-ago:
# lanzado dos veces seguidas, la SEGUNDA tanda daba sootio 0 en 90,14 s,
# aiostreams 0 en 30,10 s, mediafusion 0 en 20,11 s y torrentio 0 en 30,07 s,
# cuando minutos antes habian dado 139, 120, 29 y 38. No eran catalogos vacios:
# eran timeouts. Diecinueve proveedores en paralelo, cada uno abriendo sus
# propios hilos, cayendo encima de las conexiones que la ronda anterior todavia
# no habia soltado.
#
# Un test que miente en la columna de resultados es peor que no tener test, asi
# que van tres frenos: tope de concurrencia, cerrojo contra ejecuciones
# solapadas y periodo de reposo entre tandas.
MAX_PARALLEL = 4
COOLDOWN = 60           # segundos de reposo recomendados entre tandas
RUN_FLAG = 'luc_kodi.provider_test.running'
LAST_END = 'luc_kodi.provider_test.lastend'

OK, BAD, NA = '[COLOR ff00fa9a]OK[/COLOR]', '[COLOR ffff4444]NO[/COLOR]', '[COLOR ffdfe4e7]--[/COLOR]'

# Etiquetas que produce source_utils.get_qual(): 4K, 1080p, 720p, SD, CAM, SCR.
# Se muestran las tres de arriba y todo lo demas se agrupa, que es como se mira
# de verdad una lista de fuentes.
QUAL_ORDER = ('4K', '1080p', '720p')

# Marca de estado del proveedor. Dice como fue sin tener que leer la linea de
# datos: OK trajo resultados, EMPTY contesto vacio, FAIL fallo, OFF esta
# desactivado.
#
# v1.0.67 — era una vineta '●' (U+25CF). En Estuary y en Nimbus se pintaba; en
# AeonNox salia el cuadrado de glifo ausente, porque la fuente de la ventana la
# elige el SKIN, no el addon, y no todas las que traen los skins incluyen ese
# bloque Unicode. Un caracter que unas veces es un punto verde y otras un
# cuadro roto no informa de nada. Palabras ASCII: no hay fuente en la que
# falten, y ademas siguen leyendose si el usuario mira la ventana en blanco y
# negro o el skin ignora el color.
TAGS = {
	'ok':    '[COLOR ff00fa9a]OK[/COLOR]',
	'empty': '[COLOR ffdfe4e7]EMPTY[/COLOR]',
	'fail':  '[COLOR ffff4444]FAIL[/COLOR]',
	'off':   '[COLOR ff777777]OFF[/COLOR]',
}

# Separador entre campos. Tres espacios no bastaban: con siete cifras seguidas
# en dos lineas, el ojo no sabe donde acaba un dato y empieza el siguiente. La
# barra va en el gris claro de la prosa, no en el verde de los datos, para que
# ordene sin competir con lo que separa.
SEP = ' [COLOR ffdfe4e7]|[/COLOR] '


def _tag(row):
	if not row['enabled']:
		return TAGS['off']
	if row['results'] is None:
		return TAGS['fail']
	if not row['results']:
		return TAGS['empty']
	return TAGS['ok']


def _quality_breakdown(results):
	"""Cuenta por resolucion sobre lo que devuelve sources()."""
	out = {'4K': 0, '1080p': 0, '720p': 0, 'other': 0}
	for item in results or []:
		try:
			q = (item.get('quality') or '').strip()
		except AttributeError:
			out['other'] += 1
			continue
		if q in out:
			out[q] += 1
		else:
			# SD, CAM, SCR y cualquier etiqueta futura caen aqui.
			out['other'] += 1
	return out


def _hashes(results):
	"""Hashes normalizados, para el recuento de exclusivos. Los proveedores que
	no dan hash (hosters directos) devuelven conjunto vacio y quedan fuera del
	calculo en vez de contarse como 100% exclusivos, que seria mentira."""
	out = set()
	for item in results or []:
		try:
			h = (item.get('hash') or '').strip().lower()
		except AttributeError:
			continue
		if len(h) == 40:
			out.add(h)
	return out


def _configured(name):
	sid = TOKEN_SETTING.get(name)
	if not sid:
		return None  # no aplica: proveedor sin credenciales
	try:
		if isinstance(sid, tuple):
			return any((control.setting(x) or '').strip() for x in sid)
		return bool((control.setting(sid) or '').strip())
	except Exception:
		return False


def _enabled(name):
	try:
		return control.setting('provider.%s' % name) == 'true'
	except Exception:
		return False


def _reachable(module):
	"""Peticion corta al host del proveedor, sin depender del titulo."""
	# Los seis Custom exponen self.base_link; los demas puede que no.
	base = getattr(module, 'base_link', '') or ''
	if not base:
		return None
	try:
		start = time.time()
		# output='headers': si el host responde algo, devuelve un dict; si esta
		# caido o no resuelve, None. No existe un modo 'responsecode' en
		# client.request — comprobado antes de escribir esto.
		# v1.0.67: error=True es imprescindible. Con el valor por defecto,
		# client.request devuelve None ante CUALQUIER codigo de error HTTP, asi
		# que un host que contesta 404 en su raiz —zilean y meteor, medido—
		# salia como "NO alcanzable" mientras devolvia 161 y 99 resultados.
		# Que el host CONTESTE es lo que se mide aqui; que conteste 200 en la
		# raiz no es asunto nuestro. Solo un fallo de DNS o de conexion cuenta.
		resp = client.request(base, timeout='8', output='headers', error=True)
		return (resp is not None, time.time() - start)
	except Exception:
		return (False, 0.0)


def _run_one(entry, data, gate):
	"""gate es un Semaphore: se adquiere ANTES de arrancar el cronometro, para
	que el tiempo medido sea el del proveedor y no el de la espera en la cola."""
	name, module = entry[0], entry[1]
	gate.acquire()
	row = {'name': name, 'configured': _configured(name),
	       'enabled': _enabled(name),
	       'reachable': None, 'reach_time': 0.0,
	       'results': None, 'elapsed': 0.0, 'error': '',
	       'qual': {'4K': 0, '1080p': 0, '720p': 0, 'other': 0},
	       'hashes': set(), 'unique': None}
	try:
		inst = module()
		r = _reachable(inst)
		if r is not None:
			row['reachable'], row['reach_time'] = r
		start = time.time()
		res = inst.sources(dict(data), {})
		row['elapsed'] = time.time() - start
		# None y [] son cosas DISTINTAS: None es fallo del scraper, [] es
		# "no tengo esa peli". Colapsarlos es el fallo de diseno de pov.
		row['results'] = None if res is None else len(res)
		if res:
			row['qual'] = _quality_breakdown(res)
			row['hashes'] = _hashes(res)
	except Exception as e:
		row['error'] = str(e)[:60]
		log_utils.error()
	finally:
		gate.release()
	return row


def _label(row):
	cfg = NA if row['configured'] is None else (OK if row['configured'] else BAD)
	rch = NA if row['reachable'] is None else (OK if row['reachable'] else BAD)
	if row['results'] is None:
		res = '[COLOR ffff4444]FAIL[/COLOR]'
	elif row['results'] == 0:
		# Cero no es un fallo: el proveedor contesto y no tenia nada. Gris,
		# que ya significa "aqui no hay", en vez de un ambar que ni se lee ni
		# distingue "vacio" de "roto".
		res = '[COLOR ffdfe4e7]0[/COLOR]'
	else:
		res = '[COLOR ff00fa9a]%d[/COLOR]' % row['results']
	enb = OK if row['enabled'] else '[COLOR ffdfe4e7]off[/COLOR]'
	# El area de label2 de DialogSelect(useDetails=True) pinta DOS lineas y
	# corta el resto: no hay scroll ni puntos suspensivos, la tercera linea
	# simplemente no existe. Con los nombres largos ('Enabled: OK | Configured:
	# OK | Reachable: OK | Results: 159 | 1.53s') la primera fila ya ocupaba
	# esas dos lineas ella sola, asi que el desglose de resolucion se calculaba
	# y se tiraba a la basura sin llegar a verse. Se veia solo en las filas que
	# por casualidad quedaban cortas —DMM con 'Results: 2', peerflix con dos
	# guiones en Configured y Reachable— y una sola cifra de mas bastaba para
	# perderlo: torrentsdb con 'Results: 26' ya no cabia.
	#
	# Por eso las etiquetas van abreviadas. No es cosmetica: es lo unico que
	# garantiza que la primera fila entre en UNA linea y le deje la segunda al
	# desglose, sea cual sea el proveedor y sean cuales sean sus cifras.
	line2 = SEP.join(['On: %s' % enb, 'Cfg: %s' % cfg,
	                  'Host: %s' % rch, 'Results: %s' % res,
	                  '%.2fs' % row['elapsed']])
	if row['results']:
		q = row['qual']
		# Un cero se pinta en gris: en un desglose lo que se busca es el hueco.
		def _q(label, n):
			color = 'ff00fa9a' if n else 'ffdfe4e7'
			return '%s: [COLOR %s]%d[/COLOR]' % (label, color, n)
		# SD y por debajo se siguen contando dentro de Results, pero no se
		# muestran: en una lista de fuentes nadie baja ahi a proposito, y una
		# columna que siempre se ignora solo gasta sitio.
		parts = [_q(k, q.get(k, 0)) for k in QUAL_ORDER]
		line2 += '[CR]' + SEP.join(parts)
		if row['unique'] is not None:
			# 'only here' no decia de quien hablaba. Con el nombre delante la
			# linea se lee sola: 'only ZILEAN: 60'. El 'from' se cae por lo mismo
			# que las etiquetas de arriba: con MEDIAFUSION delante y las tres
			# cifras de resolucion, cinco caracteres son la diferencia entre
			# caber en la segunda linea o no existir.
			color = 'ff00fa9a' if row['unique'] else 'ffdfe4e7'
			line2 += SEP + 'only %s: [COLOR %s]%d[/COLOR]' % (
				row['name'].upper(), color, row['unique'])
	if row['error']:
		line2 += SEP + '[COLOR ffff4444]%s[/COLOR]' % row['error']
	return line2


# ─────────────────────────────────────────────────────────────────────────────
#  Informe
#
#  v1.0.67 — el resultado se pintaba con Dialog().select(useDetails=True), y
#  esa ventana no es nuestra: la define DialogSelect.xml del skin activo. Cada
#  skin decide cuantas lineas tiene el area de detalle, donde la coloca y con
#  que fuente. Por eso el mismo test se veia bien en Estuary y en Nimbus,
#  solapado en Arctic Fuse 3 —ahi el detalle se pinta sobre la columna de
#  nombres— y sin viñetas en AeonNox. No es un fallo del skin ni del test: es
#  que el formato lo decidia el skin.
#
#  La ventana de texto propia del addon (textviewer.xml, la misma del changelog
#  y del ranker personal) sale del paquete, asi que la maqueta la ponemos
#  nosotros y es identica en los cuatro skins. Y el textbox AJUSTA la linea y
#  hace scroll, con lo que desaparece de raiz el corte a dos lineas que obligo
#  a abreviar las etiquetas en 1.0.64: ya no hay cifra que se pierda por
#  quedarse fuera.
# ─────────────────────────────────────────────────────────────────────────────

# Sangria de las lineas de datos bajo el nombre del proveedor. En un textbox
# que ajusta linea es lo unico que agrupa visualmente las tres lineas de una
# ficha; el skin ya no pone ningun separador por nosotros.
IND = '    '


def _report(rows, data, total_items, total_q, total_hashes):
	"""Informe completo en BBCode, una ficha por proveedor."""
	lines = []
	add = lines.append

	add('[B][COLOR ff00fa9a]TOTAL[/COLOR][/B]')
	add(IND + SEP.join([
		'[COLOR ff00fa9a]%d[/COLOR] files' % total_items,
		'4K: [COLOR ff00fa9a]%d[/COLOR]' % total_q['4K'],
		'1080p: [COLOR ff00fa9a]%d[/COLOR]' % total_q['1080p'],
		'720p: [COLOR ff00fa9a]%d[/COLOR]' % total_q['720p'],
	]))
	add(IND + SEP.join([
		'[COLOR ff00fa9a]%d[/COLOR] providers with results'
		% len([r for r in rows if r['results']]),
		'[COLOR ff00fa9a]%d[/COLOR] distinct torrents' % len(total_hashes),
	]))
	add('')

	for r in rows:
		add('[B]%s[/B]   %s' % (r['name'].upper(), _tag(r)))
		# _label() ya devuelve la linea de estado y la de desglose separadas
		# por [CR]. Se parte y se sangra: el contenido no cambia, cambia donde
		# se pinta.
		for part in _label(r).split('[CR]'):
			add(IND + part)
		add('')

	add('[COLOR ffdfe4e7]How to read this:[/COLOR]')
	add('[B]On[/B] = provider enabled in settings   '
	    '[B]Cfg[/B] = credentials present   '
	    '[B]Host[/B] = the host answered')
	add('[B]Results[/B] = files returned for this title, and how long it took')
	add('[B]only NAME[/B] = hashes no other provider in this run brought. '
	    'That is the number that decides whether it earns its slot.')
	add('[B]--[/B] = not applicable: the provider needs no credentials, or has '
	    'no endpoint to probe on its own.')
	return '[CR]'.join(lines)


def _plain(text):
	"""Quita el BBCode. Solo para el plan B: el visor de texto de Kodi no lo
	interpreta y dejaria los [COLOR ...] a la vista."""
	out, depth = [], 0
	# El salto va primero: despues de quitar los corchetes ya no habria [CR]
	# que reconocer.
	for ch in text.replace('[CR]', '\n'):
		if ch == '[':
			depth += 1
		elif ch == ']':
			if depth:
				depth -= 1
		elif not depth:
			out.append(ch)
	return ''.join(out)


def _show_report(heading, text):
	"""Ventana propia. Si por lo que sea no cargase, el informe se enseña igual
	en el visor de Kodi antes que perderse una tanda de cinco minutos."""
	try:
		from resources.lib.windows.textviewer import TextViewerXML
		viewer = TextViewerXML(
			'textviewer.xml',
			control.addonPath('plugin.video.luc_kodi'),
			heading=heading,
			text=text,
		)
		viewer.run()
		del viewer
		return
	except Exception:
		log_utils.error()
	try:
		xbmcgui.Dialog().textviewer(heading, _plain(text))
	except Exception:
		log_utils.error()


def run():
	try:
		# v1.0.65 fix: era sources_mod.sources(), y la clase se llama Sources.
		# Ademas instanciarla arrastra resolutores de debrid y hosters premium
		# solo para listar modulos. fs_sources() es el enumerador real y es lo
		# unico que hace falta: devuelve [(nombre, clase source), ...].
		from resources.lib.jacksparrow import sources as fs_sources
		from resources.lib.jacksparrow import workers
	except Exception:
		log_utils.error()
		control.okDialog(message='Could not load the source modules.')
		return

	# Cerrojo: una segunda tanda encima de la primera falsea las dos.
	try:
		running = control.homeWindow.getProperty(RUN_FLAG)
		if running and (time.time() - int(running)) < 360:
			control.okDialog('Provider test', 'A test is already running. Let it finish first.')
			return
		last = control.homeWindow.getProperty(LAST_END)
		if last and (time.time() - int(last)) < COOLDOWN:
			wait = COOLDOWN - int(time.time() - int(last))
			if not control.yesnoDialog(
					'The last test finished %d seconds ago. Providers still have connections open, '
					'so running again now will report working providers as timed out.\n\n'
					'Wait about %d more seconds for numbers you can trust.'
					% (int(time.time() - int(last)), wait),
					'', '', heading='Too soon'):
				return
	except Exception:
		pass

	data = pick_content()
	if not data:
		return

	try:
		# ret_all=True: incluye tambien los DESACTIVADOS. En un test de
		# proveedores interesa ver el que esta apagado, no esconderlo.
		entries = [(n, cls) for n, cls in fs_sources(ret_all=True)
		           if getattr(cls, 'hasMovies', False)]
	except Exception:
		log_utils.error()
		control.okDialog(message='Could not enumerate the providers.')
		return
	if not entries:
		control.okDialog(message='No providers were found.')
		return

	progress = xbmcgui.DialogProgress()
	progress.create('Provider test', 'Starting...')
	rows, total = [], len(entries)
	try:
		control.homeWindow.setProperty(RUN_FLAG, str(int(time.time())))
	except Exception:
		pass
	gate = threading.Semaphore(MAX_PARALLEL)
	threads = [workers.Thread(lambda e=e: rows.append(_run_one(e, data, gate))) for e in entries]
	for t in threads:
		t.start()
	# Con la concurrencia limitada la tanda tarda mas de reloj, asi que el tope
	# sube: cortarla antes de tiempo produciria justo los ceros falsos que
	# estamos eliminando.
	deadline = time.time() + 300
	while any(t.is_alive() for t in threads) and time.time() < deadline:
		if progress.iscanceled():
			break
		done = len(rows)
		progress.update(int(done / float(total) * 100),
		                'Testing %d providers, %d at a time...[CR]Finished: %d / %d'
		                % (total, MAX_PARALLEL, done, total))
		xbmc.sleep(200)
	progress.close()
	try:
		control.homeWindow.setProperty(LAST_END, str(int(time.time())))
		control.homeWindow.clearProperty(RUN_FLAG)
	except Exception:
		pass

	# Exclusivos: un hash cuenta como propio si NINGUN otro proveedor lo trajo.
	# Se calcula al final, cuando ya estan todas las tandas, no dentro del hilo.
	for r in rows:
		if not r['hashes']:
			continue
		otros = set()
		for other in rows:
			if other is not r:
				otros |= other['hashes']
		r['unique'] = len(r['hashes'] - otros)

	rows.sort(key=lambda r: (not r['enabled'], r['results'] is None, -(r['results'] or 0), r['elapsed']))

	# Los sets no son serializables y el log tiene que seguir siendo json valido.
	for r in rows:
		loggable = dict(r)
		loggable['hashes'] = len(r['hashes'])
		control.log('[ luc_kodi ] provider_test: %s' % json.dumps(loggable, sort_keys=True), LOGINFO)

	# Fila de totales. El total de resolucion es la suma por proveedor, asi que
	# cuenta repetido el mismo release ofrecido por varios; el de hashes unicos
	# no. Van los dos y la diferencia entre ambos es, precisamente, el solape.
	total_q = {'4K': 0, '1080p': 0, '720p': 0, 'other': 0}
	total_hashes = set()
	for r in rows:
		for k in total_q:
			total_q[k] += r['qual'].get(k, 0)
		total_hashes |= r['hashes']
	total_items = sum(r['results'] or 0 for r in rows)

	heading = data.get('tvshowtitle') or data.get('title') or data['imdb']
	if data.get('tvshowtitle'):
		heading += ' S01E01'

	# La fila TOTAL ya no compite por sitio con nada: encabeza el informe y se
	# lee entera. Se queda en datos y sin la frase sobre el solape, que ademas
	# no era exacta: la diferencia entre ficheros y torrents distintos mezcla
	# releases repetidos por varios proveedores con ficheros distintos del mismo
	# torrent (un pack de temporada es UN hash con doce ficheros dentro). El
	# solape bien medido es el 'only X' de cada ficha.
	text = _report(rows, data, total_items, total_q, total_hashes)
	control.log('[ luc_kodi ] provider_test: report built, %d providers' % len(rows), LOGINFO)
	# Dos puntos y no raya: la raya larga es el mismo caso que la vineta, un
	# caracter fuera de ASCII que depende de la fuente del skin. En el titulo
	# se notaria mas que en ningun otro sitio.
	_show_report('Provider test: %s' % heading, text)
