# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from json import dumps as jsdumps, loads as jsloads
from sqlite3 import dbapi2 as db
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


def _resolve_view_id(skin, content, style, viewDict):
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
	# 2) default del perfil para este skin
	d = _VIEW_DEFAULTS.get(style, {}).get(content, {})
	if skin in d: return str(d[skin])
	# 3) fallback que pasa el menú (comportamiento clásico)
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
def setView(content, viewDict=None):
	style = getViewStyle()
	# 'menus' no es un content-type real de Kodi: en los listados de menús el
	# content se fija a 'files' (ver navigator.endDirectory), así que sondeamos
	# sobre 'files' aunque la clave de vista sea 'menus'.
	poll = 'files' if content == 'menus' else content
	for i in range(0, 200):
		if control.condVisibility('Container.Content(%s)' % poll):
			try:
				skin = control.skin
				view = _resolve_view_id(skin, content, style, viewDict)
				if view is None: return
				return control.execute('Container.SetViewMode(%s)' % str(view))
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
