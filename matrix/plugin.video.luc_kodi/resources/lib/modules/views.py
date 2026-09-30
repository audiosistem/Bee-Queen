# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

import os
import re
import time
from json import dumps as jsdumps, loads as jsloads
from sqlite3 import dbapi2 as db

import xbmc

from resources.lib.modules import control


# ──────────────────────────────────────────────────────────────────────────
#  Add-on view styles ("Set Add-on View" en Tools)
#
#  'default'  -> comportamiento de siempre. Los menús de secciones/categorías
#                usan la vista por defecto del skin; el contenido usa el
#                viewDict que pasa cada menú (p.ej. Wall en Estuary).
#
#  'modern'   -> menús (secciones/categorías) en rejilla de iconos (Wall) y
#                contenido (pelis/series) en InfoWall: póster + sinopsis + rating.
#
#  Los IDs son por skin. Aquí solo garantizamos Estuary (skin por defecto de
#  Kodi). Para otros skins el usuario puede guardar su vista con
#  Tools > Views (se almacena por perfil, ver _view_type_key) y, si no hay nada
#  guardado, se respeta la vista por defecto del skin (no se fuerza nada).
#
#  Estuary view IDs:  50 List · 54 InfoWall · 55 WideList · 500 Wall
# ──────────────────────────────────────────────────────────────────────────
_VIEW_DEFAULTS = {
	'default': {
		# vacío a propósito: el perfil clásico delega en el viewDict del menú,
		# por lo que el comportamiento queda EXACTAMENTE igual que antes.
	},
	'modern': {
		'menus':    {'skin.estuary': 500},  # Wall  -> solo iconos
		'movies':   {'skin.estuary': 54},   # InfoWall -> póster + sinopsis + rating
		'tvshows':  {'skin.estuary': 54},   # InfoWall
		'seasons':  {'skin.estuary': 54},   # InfoWall
		'episodes': {'skin.estuary': 55},   # WideList (los episodios se leen mejor)
	},
	'bingie': {
		# Las categorías de pelis/series se abren en la ventana propia
		# (bingie_grid.xml), así que aquí sólo importan los menús de navegación
		# y las vistas de seasons/episodes que siguen siendo directorios Kodi.
		# Los menús (root y submenús: Tools, Trakt, AI Search, listas) van en
		# LISTA, igual que la seccion principal — no en Wall de iconos.
		'menus':    {'skin.estuary': 55},   # WideList -> lista
		'seasons':  {'skin.estuary': 54},   # InfoWall
		'episodes': {'skin.estuary': 55},   # WideList
	},
}


# ──────────────────────────────────────────────────────────────────────────
#  VISTA "WALL" IMPUESTA POR EL PLUGIN (v1.0.81)
#
#  Hasta ahora cada menú pasaba un viewDict con IDs escritos a mano para DOS
#  skins (Estuary y Confluence). En cualquier otro skin no se forzaba nada, así
#  que el contenido salía con la vista por defecto del skin — normalmente una
#  lista. De ahí que el addon se viera distinto en cada skin.
#
#  Ahora Movies, TV shows, Seasons y Episodes se muestran SIEMPRE en rejilla de
#  pósters, y el ID de esa rejilla se AVERIGUA del propio skin en vez de
#  adivinarse: cada vista de un skin declara `<viewtype label="...">tipo</viewtype>`
#  dentro de su control, y `MyVideoNav.xml` declara en `<views>` qué IDs son
#  vistas válidas de vídeo. Con esas dos cosas se puede elegir la rejilla de
#  pósters de CUALQUIER skin sin tener una tabla de cada uno.
#
#  Orden de resolución (ver _resolve_view_id):
#    1. lo que el usuario haya guardado con Tools > Set Add-on View  (manda él)
#    2. tabla curada de skins verificados a mano
#    3. detección automática sobre los XML del skin (se cachea en views.db)
#    4. el viewDict del menú (comportamiento clásico)
#  El skin NUNCA decide: si algo de 1-4 responde, se impone.
# ──────────────────────────────────────────────────────────────────────────
FORCED_CONTENT = ('movies', 'tvshows', 'seasons', 'episodes')

# IDs comprobados contra el XML real del skin. Tienen prioridad sobre la
# detección automática porque son los que el addon lleva usando desde siempre.
_WALL_VIEWS = {
	'skin.estuary':          {'movies': 500, 'tvshows': 500, 'seasons': 500, 'episodes': 500},
	'skin.confluence':       {'movies': 500, 'tvshows': 500, 'seasons': 500, 'episodes': 504},
	'skin.aeon.nox.silvo':   {'movies': 503, 'tvshows': 503, 'seasons': 503, 'episodes': 503},
	'skin.estuary.modv2':    {'movies': 500, 'tvshows': 500, 'seasons': 500, 'episodes': 500},
}

# Clave con la que se guarda en views.db el ID detectado para un skin. No choca
# con ningún content-type real de Kodi, así que convive con las vistas que el
# usuario guarde a mano.
_WALL_KEY = '__wall__'

_CTRL_RE = re.compile(r'<control\s+type="(?:list|fixedlist|wraplist|panel|epggrid)"\s+id="(\d+)"', re.I)
_VTYPE_RE = re.compile(r'<viewtype\s+label="([^"]*)"\s*>\s*([^<]*?)\s*</viewtype>', re.I)
_LOCALIZE_RE = re.compile(r'\$LOCALIZE\[(\d+)\]')
_VIEWS_RE = re.compile(r'<views>([^<]+)</views>', re.I)
_RES_RE = re.compile(r'<res\b[^>]*folder="([^"]+)"[^>]*/>', re.I)

# Etiquetas que descartan una vista aunque su tipo sea de rejilla: son rejillas
# de OTRA cosa (banners apaisados, fanart, logos, listas con miniatura).
_WALL_REJECT = ('banner', 'landscape', 'fanart', 'logo', 'list', 'episode', 'song', 'shift', 'info', 'season')
# Puntuación por lo que dice la etiqueta que ve el usuario en el selector de
# vistas del skin. "Wall" exacto es lo que se busca; "Poster/Posters" es la
# misma idea con otro nombre; el resto son aproximaciones aceptables.
_WALL_SCORES = (('poster', 90), ('wall', 80), ('grid', 70), ('thumb', 50), ('icon', 40), ('gallery', 30))

_SCAN_MAX_FILES = 400
_SCAN_MAX_SECONDS = 4.0


def forceWall():
	"""True si el plugin impone su rejilla de pósters. Por defecto SÍ: un ajuste
	vacío (instalación que viene de una versión anterior) cuenta como activado."""
	return control.setting('ui.force.wall') != 'false'


def _skin_string(skin, num):
	# Las etiquetas 31000-31999 son cadenas del propio skin; el resto son del
	# núcleo de Kodi. Se prueban las dos por si el skin reutiliza un id del core.
	try:
		s = control.addon(skin).getLocalizedString(int(num))
		if s: return s
	except Exception: pass
	try: return xbmc.getLocalizedString(int(num))
	except Exception: return ''


def _resolve_viewtype_label(skin, raw):
	raw = (raw or '').strip()
	m = _LOCALIZE_RE.search(raw)
	if m: return _skin_string(skin, m.group(1))
	if raw.isdigit(): return _skin_string(skin, raw)
	return raw


def _is_grid_viewtype(vtype):
	vtype = (vtype or '').strip().lower()
	if not vtype: return False
	# 'icon'/'bigicon' (Estuary, Aeon Nox), 'wrap'/'bigwrap' (Confluence y toda
	# la familia que desciende de él), y los nombres literales.
	return ('icon' in vtype) or ('wrap' in vtype) or vtype in ('poster', 'media', 'thumbnail', 'wall')


def _skin_res_folders(skin_path):
	"""Carpetas de resolución declaradas en el addon.xml del skin, la marcada
	como default la primera."""
	folders = []
	try:
		with open(os.path.join(skin_path, 'addon.xml'), 'r', encoding='utf-8', errors='ignore') as f:
			txt = f.read()
		for m in _RES_RE.finditer(txt):
			if 'default="true"' in m.group(0): folders.insert(0, m.group(1))
			else: folders.append(m.group(1))
	except Exception: pass
	# Nombres habituales por si el addon.xml no se deja leer.
	for guess in ('xml', '16x9', '1080i', '1080p', '720p'):
		if guess not in folders: folders.append(guess)
	return folders


def _declared_video_views(folder):
	"""IDs que el skin declara como vistas válidas en MyVideoNav.xml. Sin esto se
	podría elegir la rejilla de la ventana de música o de imágenes."""
	try:
		with open(os.path.join(folder, 'MyVideoNav.xml'), 'r', encoding='utf-8', errors='ignore') as f:
			m = _VIEWS_RE.search(f.read())
		if not m: return set()
		return set(i.strip() for i in m.group(1).split(',') if i.strip().isdigit())
	except Exception:
		return set()


def _scan_folder_for_wall(skin, folder, allowed, names):
	best = (0, None)
	started = time.time()
	scanned = 0
	for name in names:
		if scanned >= _SCAN_MAX_FILES or (time.time() - started) > _SCAN_MAX_SECONDS: break
		try:
			with open(os.path.join(folder, name), 'r', encoding='utf-8', errors='ignore') as f:
				txt = f.read()
		except Exception:
			continue
		scanned += 1
		if '<viewtype' not in txt: continue
		# Un viewtype pertenece al último control abierto antes que él, así que
		# basta con recorrer ambas marcas en orden de aparición.
		marks = [(m.start(), 0, m.group(1)) for m in _CTRL_RE.finditer(txt)]
		marks += [(m.start(), 1, (m.group(1), m.group(2))) for m in _VTYPE_RE.finditer(txt)]
		marks.sort()
		current = None
		for _pos, kind, val in marks:
			if kind == 0:
				current = val
				continue
			if current is None or current not in allowed: continue
			if not _is_grid_viewtype(val[1]): continue
			label = _resolve_viewtype_label(skin, val[0]).strip().lower()
			if not label: continue
			if any(bad in label for bad in _WALL_REJECT): continue
			score = 100 if label == 'wall' else 0
			for key, pts in _WALL_SCORES:
				if key in label: score = max(score, pts)
			# Una rejilla a pantalla completa sirve, pero solo si no hay otra.
			if 'fullscreen' in label: score -= 45
			if score > best[0]: best = (score, current)
	return best[1] if best[0] else None


def _detect_wall_view(skin):
	"""Averigua el ID de la rejilla de pósters del skin activo leyendo sus XML.
	Devuelve el id como cadena, o None si el skin no declara ninguna."""
	try:
		skin_path = control.addon(skin).getAddonInfo('path')
		skin_path = control.transPath(skin_path)
	except Exception:
		return None
	if not skin_path or not os.path.isdir(skin_path): return None
	for rf in _skin_res_folders(skin):
		folder = os.path.join(skin_path, rf)
		if not os.path.isdir(folder): continue
		allowed = _declared_video_views(folder)
		if not allowed: continue
		try: xmls = [i for i in sorted(os.listdir(folder)) if i.lower().endswith('.xml')]
		except Exception: continue
		# Primera pasada solo por los ficheros que llevan "view" en el nombre:
		# cubre Estuary (View_500_Wall.xml), Aeon Nox (View_503_Wall.xml) y
		# Confluence (ViewsVideoLibrary.xml) sin leer el skin entero.
		likely = [i for i in xmls if 'view' in i.lower()]
		found = _scan_folder_for_wall(skin, folder, allowed, likely)
		if found: return found
		found = _scan_folder_for_wall(skin, folder, allowed, [i for i in xmls if i not in likely])
		if found: return found
	return None


def _wall_cache(skin, value=None):
	"""Lee/escribe en views.db el ID detectado para este skin. Se cachea también
	el fracaso (cadena vacía) para no volver a escanear el skin en cada listado."""
	dbcon = dbcur = None
	try:
		control.makeFile(control.dataPath)
		dbcon = db.connect(control.viewsFile)
		dbcur = dbcon.cursor()
		dbcur.execute('''CREATE TABLE IF NOT EXISTS views (skin TEXT, view_type TEXT, view_id TEXT, UNIQUE(skin, view_type));''')
		if value is None:
			row = dbcur.execute('''SELECT view_id FROM views WHERE (skin=? AND view_type=?)''', (skin, _WALL_KEY)).fetchone()
			return row[0] if row else None
		dbcur.execute('''DELETE FROM views WHERE (skin=? AND view_type=?)''', (skin, _WALL_KEY))
		dbcur.execute('''INSERT INTO views Values (?, ?, ?)''', (skin, _WALL_KEY, str(value)))
		dbcur.connection.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass
	return None


def wallViewId(skin, content):
	"""ID de la rejilla de pósters para (skin, content). Tabla curada primero,
	detección automática después, y el resultado cacheado en views.db."""
	table = _WALL_VIEWS.get(skin)
	if table:
		vid = table.get(content) or table.get('movies')
		if vid: return str(vid)
	cached = _wall_cache(skin)
	if cached is not None:
		return cached or None  # '' significa "ya se buscó y este skin no tiene"
	found = _detect_wall_view(skin)
	_wall_cache(skin, found or '')
	if found:
		from resources.lib.modules import log_utils
		log_utils.log('[luc_kodi] views: rejilla de posters detectada en %s -> id %s' % (skin, found), level=log_utils.LOGINFO)
	return found


def getViewStyle():
	v = control.setting('ui.viewstyle')
	# 'modern' is retired: any stored value other than 'bingie' is classic default.
	return 'bingie' if v == 'bingie' else 'default'


def setViewStyle(token):
	if token not in ('default', 'bingie'): token = 'default'
	control.setSetting('ui.viewstyle', token)
	# mantener coherente la caché de settings (Window property) para que la
	# siguiente lectura de setting() no devuelva el valor antiguo cacheado.
	try:
		sd = jsloads(control.homeWindow.getProperty('luc_kodi_settings'))
		sd['ui.viewstyle'] = token
		control.homeWindow.setProperty('luc_kodi_settings', jsdumps(sd))
	except Exception:
		pass
	return token


def _view_type_key(content, style):
	# el perfil clásico conserva la clave de siempre (compatibilidad hacia atrás);
	# el resto de perfiles se versionan con sufijo "@perfil".
	return content if style == 'default' else '%s@%s' % (content, style)


def _resolve_view_id(skin, content, style, viewDict, force=None):
	# 1) vista guardada por el usuario para (skin, perfil)
	try:
		dbcon = db.connect(control.viewsFile)
		dbcur = dbcon.cursor()
		dbcur.execute('''CREATE TABLE IF NOT EXISTS views (skin TEXT, view_type TEXT, view_id TEXT, UNIQUE(skin, view_type));''')
		row = dbcur.execute('''SELECT view_id FROM views WHERE (skin=? AND view_type=?)''', (skin, _view_type_key(content, style))).fetchone()
		if row and row[0] not in (None, ''):
			return str(row[0])
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass
	# 2) rejilla de pósters impuesta por el plugin (v1.0.81). Va DESPUÉS de la
	#    vista guardada a propósito: si el usuario eligió su vista con
	#    Tools > Set Add-on View, esa manda — incluso si es la Wall del skin, que
	#    es justo lo que se quiere. Lo que nunca decide es el skin por su cuenta.
	if force is None: force = forceWall()
	if content in FORCED_CONTENT and force:
		wall = wallViewId(skin, content)
		if wall: return str(wall)
	# 3) default del perfil para este skin
	d = _VIEW_DEFAULTS.get(style, {}).get(content, {})
	if skin in d: return str(d[skin])
	# 4) fallback que pasa el menú (comportamiento clásico)
	if viewDict and skin in viewDict: return str(viewDict[skin])
	return None


def clearViews():
	try:
		skin = control.skin
		control.hide()
		if not control.yesnoDialog(control.lang(32056), '', ''): return
		control.makeFile(control.dataPath)
		dbcon = db.connect(control.viewsFile)
		dbcur = dbcon.cursor()
		try:
			dbcur.execute('''DROP TABLE IF EXISTS views''')
			dbcur.execute('''VACUUM''')
			dbcur.execute('''CREATE TABLE IF NOT EXISTS views (skin TEXT, view_type TEXT, view_id TEXT, UNIQUE(skin, view_type));''')
			dbcur.connection.commit()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			try:
				dbcur.close()
			except Exception:
				pass
			try:
				dbcon.close()
			except Exception:
				pass
		try:
			kodiDB = control.transPath('special://home/userdata/Database')
			kodiViewsDB = control.joinPath(kodiDB, 'ViewModes6.db')
			dbcon = db.connect(kodiViewsDB)
			dbcur = dbcon.cursor()
			dbcur.execute('''DELETE FROM view WHERE path LIKE "plugin://plugin.video.luc_kodi/%"''')
			dbcur.connection.commit()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			try:
				dbcur.close()
			except Exception:
				pass
			try:
				dbcon.close()
			except Exception:
				pass
		skinName = control.addon(skin).getAddonInfo('name')
		skinIcon = control.addon(skin).getAddonInfo('icon')
		control.notification(title=skinName, message=32087, icon=skinIcon)
	except:
		from resources.lib.modules import log_utils
		log_utils.error()

def addView(content):
	try:
		skin = control.skin
		content = _view_type_key(content, getViewStyle())
		record = (skin, content, str(control.getCurrentViewId()))
		control.makeFile(control.dataPath)
		dbcon = db.connect(control.viewsFile)
		dbcur = dbcon.cursor()
		dbcur.execute('''CREATE TABLE IF NOT EXISTS views (skin TEXT, view_type TEXT, view_id TEXT, UNIQUE(skin, view_type));''')
		dbcur.execute('''DELETE FROM views WHERE (skin=? AND view_type=?)''', (record[0], record[1]))
		dbcur.execute('''INSERT INTO views Values (?, ?, ?)''', record)
		dbcur.connection.commit()
		viewName = control.infoLabel('Container.Viewmode')
		skinName = control.addon(skin).getAddonInfo('name')
		skinIcon = control.addon(skin).getAddonInfo('icon')
		control.notification(title=skinName, message=viewName, icon=skinIcon)
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try:
			dbcur.close()
		except Exception:
			pass
		try:
			dbcon.close()
		except Exception:
			pass
def setView(content, viewDict=None, force=None):
	"""force=False desactiva la rejilla impuesta para ESTA llamada. Lo usa la
	pantalla de Tools > Set Add-on View: ahi el usuario esta eligiendo su vista,
	asi que tiene que abrirse con la que tiene puesta, no con la que el plugin
	impondria despues."""
	style = getViewStyle()
	# 'menus' no es un content-type real de Kodi: en los listados de menús el
	# content se fija a 'files' (ver navigator.endDirectory), así que sondeamos
	# sobre 'files' aunque la clave de vista sea 'menus'.
	poll = 'files' if content == 'menus' else content
	for i in range(0, 200):
		if control.condVisibility('Container.Content(%s)' % poll):
			try:
				skin = control.skin
				view = _resolve_view_id(skin, content, style, viewDict, force)
				if view is None: return
				control.execute('Container.SetViewMode(%s)' % str(view))
				# Algunos skins aplican su propia vista por defecto unos ms
				# DESPUÉS de que el directorio termine de cargarse, y se comían
				# la orden de arriba. Se comprueba un par de veces y se vuelve a
				# poner; si ya está puesta no se hace nada.
				if content in FORCED_CONTENT and (forceWall() if force is None else force):
					for _r in range(0, 3):
						control.sleep(150)
						try:
							if control.getCurrentViewId() == str(view): break
						except Exception: break
						control.execute('Container.SetViewMode(%s)' % str(view))
				return
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
				return
		control.sleep(100)

def setMenuView():
	# Sólo actúa en el perfil 'bingie'. En 'default' los menús quedan
	# EXACTAMENTE como antes (vista por defecto del skin, interfaz clásica).
	if getViewStyle() != 'bingie': return
	return setView('menus', {})
