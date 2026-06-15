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


# ──────────────────────── limpieza semanal de texturas ────────────────────────
# Cada póster rotado es una URL distinta y Kodi lo cachea como una textura nueva
# (Textures13.db + carpeta Thumbnails). Para que el almacenamiento no crezca sin
# límite, una vez por semana se purgan las texturas de image.tmdb.org que lleven
# más de CLEAN_AFTER_DAYS sin usarse. Las texturas en uso (la "generación" actual
# de la rotación, y cualquier póster que el usuario siga viendo) refrescan su
# 'lastused' continuamente, así que NUNCA se borran: solo cae la generación vieja.
# Al volver a mostrarse un título purgado, Kodi simplemente re-descarga el póster.
# Todo vía JSON-RPC (Textures.GetTextures / Textures.RemoveTexture): sin tocar la
# base de datos a mano, compatible con Android/Shield y cualquier plataforma.

CLEAN_AFTER_DAYS = 7
_LASTCLEAN_SETTING = 'poster.rotation.lastclean'


def cleanup_enabled():
	try: return getSetting('poster.rotation.cleanup') != 'false' # activada por defecto
	except: return True


def clean_texture_cache(days=CLEAN_AFTER_DAYS):
	"""Borra las texturas de image.tmdb.org sin usar desde hace `days` días.
	Devuelve el número de texturas eliminadas."""
	from json import dumps as jsdumps, loads as jsloads
	from datetime import datetime, timedelta
	removed = 0
	try:
		query = {'jsonrpc': '2.0', 'id': 1, 'method': 'Textures.GetTextures',
				'params': {'properties': ['url', 'lastused'],
							'filter': {'field': 'url', 'operator': 'contains', 'value': 'image.tmdb.org/t/p/'}}}
		response = jsloads(control.jsonrpc(jsdumps(query)))
		textures = response.get('result', {}).get('textures', []) or []
		if not textures: return 0
		cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
		monitor = control.monitor
		for texture in textures:
			if monitor.abortRequested(): break # no retrasar el apagado de Kodi
			try:
				lastused = texture.get('lastused') or ''
				if not lastused or lastused >= cutoff: continue # en uso o fecha desconocida: no tocar
				control.jsonrpc(jsdumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Textures.RemoveTexture',
										'params': {'textureid': texture['textureid']}}))
				removed += 1
			except: pass
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
	return removed


def janitor_service():
	"""Bucle de servicio: comprueba cada hora si toca la limpieza semanal.
	No hace nada si la rotación o la limpieza están desactivadas. Nunca corre
	durante la reproducción de vídeo (mismo criterio que catalog_updater)."""
	import time as _time
	import xbmc
	from resources.lib.modules import log_utils
	monitor = control.monitor
	set_boot_offset() # al iniciar Kodi: avanzar la rotación para que se vean pósters nuevos
	while not monitor.abortRequested():
		try:
			if enabled() and cleanup_enabled():
				try: last = float(getSetting(_LASTCLEAN_SETTING) or 0)
				except: last = 0
				if (_time.time() - last) >= CLEAN_AFTER_DAYS * 86400 and not xbmc.Player().isPlayingVideo():
					removed = clean_texture_cache()
					control.setSetting(_LASTCLEAN_SETTING, str(int(_time.time())))
					log_utils.log('[ plugin.video.luc_kodi ]  Poster janitor: %s texturas TMDb antiguas eliminadas' % removed, log_utils.LOGINFO)
		except: log_utils.error()
		if monitor.waitForAbort(3600): break # re-evaluar cada hora
