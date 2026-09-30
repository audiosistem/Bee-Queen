# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Rotación de pósters (TMDb)

	Alterna entre los pósters alternativos que TMDb tiene para cada contenido,
	usando ventanas de tiempo deterministas (3 / 6 / 12 / 24 horas).

	Diseño:
	- 'posters_all' lo rellena el indexer de TMDb (indexers/tmdb.py) a partir de
	  la misma petición de metadatos (append_to_response=images), así que NO hay
	  peticiones HTTP extra: la rotación es solo aritmética local.
	- La selección es determinista: índice = (tmdb_id + ventana_de_tiempo +
	  offset_de_arranque) % N. Con esto todos los widgets/listas/ventanas Bingie
	  muestran el MISMO póster para el mismo título durante toda la ventana, y al
	  expirar la ventana cada título avanza una posición (cambio garantizado si N>=2).
	- Además del tiempo, los pósters cambian al INICIAR Kodi: el servicio fija un
	  offset de arranque pseudoaleatorio (set_boot_offset) que se mezcla en la
	  semilla, así que reiniciar también refresca la parrilla.
	- El offset por tmdb_id evita que todos los títulos "arranquen" en el mismo
	  índice; la parrilla se ve variada desde el primer momento.
	- Si la opción está desactivada, no hay lista o algo falla, se devuelve el
	  póster original sin tocar: la función es 100% inocua.
"""

import time
from resources.lib.modules import control

getSetting = control.setting

_INTERVALS = (3, 6, 12, 24) # horas; índice = setting 'poster.rotation.interval'

# Caché de configuración con TTL corto: control.setting() parsea el JSON completo
# de settings (window property) en CADA llamada. Un directorio de 200 ítems haría
# 400+ parseos. Con este TTL de 5s todo el directorio se resuelve con UNA lectura,
# y un cambio de ajustes se refleja como mucho 5 segundos después (con
# reuseLanguageInvoker el módulo persiste, así que el TTL es imprescindible:
# una caché sin caducidad congelaría el ajuste hasta reiniciar Kodi).
_conf_cache = {'ts': 0.0, 'enabled': False, 'hours': 24}
_CONF_TTL = 5.0

def _conf():
	now = time.time()
	if now - _conf_cache['ts'] > _CONF_TTL:
		try: _conf_cache['enabled'] = getSetting('poster.rotation') == 'true'
		except: _conf_cache['enabled'] = False
		try: _conf_cache['hours'] = _INTERVALS[int(getSetting('poster.rotation.interval') or '3')]
		except: _conf_cache['hours'] = 24
		_conf_cache['ts'] = now
	return _conf_cache


def enabled():
	return _conf()['enabled']


def interval_hours():
	return _conf()['hours']


# Offset de arranque: además de las ventanas de tiempo, queremos que los pósters
# cambien cada vez que se inicia Kodi. Guardamos un valor por sesión en una
# propiedad de la ventana home (homeWindow) y lo mezclamos en la semilla. El
# servicio (service.py) lo fija una vez al arrancar; aquí solo se lee. Si por lo
# que sea no está fijado, se cae a 0 y la rotación sigue funcionando por tiempo.
_BOOT_PROP = 'luc_kodi.poster_boot_offset'


def set_boot_offset():
	"""Llamado UNA vez por el servicio al iniciar Kodi. Avanza la rotación una
	cantidad pseudoaleatoria, así que al abrir el plugin tras reiniciar se ven
	pósters distintos aunque no haya cambiado la ventana de tiempo."""
	try:
		import random
		control.homeWindow.setProperty(_BOOT_PROP, str(random.randint(1, 999999)))
	except: pass


def _boot_offset():
	try: return int(control.homeWindow.getProperty(_BOOT_PROP) or 0)
	except: return 0


def rotate(meta, poster):
	"""Devuelve el póster que corresponde a la ventana de tiempo actual + arranque.
	`meta`: dict con (opcionalmente) 'posters_all' y 'tmdb'.
	`poster`: el póster ya elegido por la lógica normal (fallback)."""
	try:
		if not enabled(): return poster
		plist = meta.get('posters_all')
		if not plist or len(plist) < 2: return poster
		bucket = int(time.time() // (interval_hours() * 3600))
		try: seed = int(meta.get('tmdb') or 0)
		except: seed = 0
		return plist[(seed + bucket + _boot_offset()) % len(plist)] or poster
	except: return poster


# ──────────────────────── limpieza de texturas ────────────────────────────────
# v1.0.94 — la limpieza de texturas ya NO vive aqui: la hace la sonda de
# maintenance.py, junto con el resto de lo que deja el addon. La de este
# modulo no borro nunca nada: pedia a Textures.GetTextures la propiedad
# 'lastused', que Kodi no tiene en ese nivel (esta dentro de 'sizes'), asi que
# rechazaba la llamada entera; llegaba una lista vacia, se devolvia un 0 suelto
# donde el servicio desempaquetaba tres valores, y el TypeError se tragaba en
# silencio cada minuto sin escribir la marca de ultima pasada. Los ajustes de
# dias ('poster.rotation.cleanup.days') y la marca ('poster.rotation.lastclean')
# se conservan con el mismo id y los lee maintenance.py.


def janitor_service():
	"""Al iniciar Kodi: avanzar la rotacion para que se vean posters nuevos.
	Lo que antes era un bucle de limpieza lo lleva ahora maintenance.py."""
	set_boot_offset()
