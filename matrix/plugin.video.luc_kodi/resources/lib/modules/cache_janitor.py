# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Mantenimiento mensual de las bases de datos de caché del plugin.

	Las cachés del plugin usan INSERT OR REPLACE: las filas se sobreescriben al
	refrescarse, pero las entradas de títulos que el usuario nunca vuelve a visitar
	se quedan para siempre. Este servicio purga una vez al mes las filas más
	antiguas que el umbral de cada base y ejecuta VACUUM para devolver de verdad
	el espacio al almacenamiento (un DELETE solo deja páginas libres dentro del
	archivo; el archivo no encoge sin VACUUM).

	Todo lo purgado se regenera solo bajo demanda desde las APIs (TMDb, fanart.tv,
	scrapers) la próxima vez que el título se muestre: cero pérdida funcional.

	LÍNEA ROJA — bases que JAMÁS se tocan aquí por contener estado o datos del
	usuario, no caché regenerable:
	  traktsync.db / simklsync.db  -> estado de sincronización
	  watched.db                   -> posiciones de reproducción / progreso
	  source_ranker.db             -> aprendizaje del ranker personal
	  reco_feedback.db             -> likes/dislikes del motor de recomendaciones
	  titlesubs.db, undesirables   -> configuración acumulada del usuario
"""

import time
from resources.lib.modules import control

getSetting = control.setting

RUN_EVERY_DAYS = 30
_LASTRUN_SETTING = 'db.maintenance.lastrun'


def _targets():
	# (ruta, tabla, columna de tiempo, días de antigüedad para purgar)
	# Umbrales muy por encima de cualquier TTL interno de cada caché: una fila
	# más antigua que esto es, por definición, peso muerto que ningún acceso
	# habría servido ya (el TTL habría forzado el refresco).
	return (
		(control.metacacheFile, 'meta', 'time', 90),      # metadatos TMDb (TTL dinámico << 90d)
		(control.cacheFile, 'cache', 'date', 30),         # caché general de funciones (TTLs <= 14d)
		(control.fanarttvCacheFile, 'cache', 'date', 30), # fanart.tv (TTL 336h = 14d)
		(control.providercacheFile, 'cache', 'date', 30), # resultados de scrapers (TTLs cortos, blobs grandes)
	)


def enabled():
	try: return getSetting('db.maintenance') != 'false' # activado por defecto
	except: return True


def prune_databases():
	"""Purga filas antiguas de las cachés regenerables y compacta con VACUUM.
	Devuelve el total de filas eliminadas."""
	from sqlite3 import dbapi2 as db
	from resources.lib.modules import log_utils
	total = 0
	now = int(time.time())
	for path, table, column, days in _targets():
		try:
			if not control.existsPath(path): continue
			dbcon = db.connect(path, timeout=60)
			dbcur = dbcon.cursor()
			cutoff = now - days * 86400
			# CAST cubre metacache, donde el epoch se guarda en columna TEXT
			dbcur.execute('DELETE FROM %s WHERE CAST(%s AS INTEGER) < ?' % (table, column), (cutoff,))
			deleted = dbcur.rowcount if dbcur.rowcount and dbcur.rowcount > 0 else 0
			dbcon.commit()
			if deleted:
				try: dbcur.execute('VACUUM') # fuera de transacción tras el commit; compatible con WAL
				except: pass
			dbcon.close()
			total += deleted
		except:
			log_utils.error()
	return total


def janitor_service():
	"""Bucle de servicio: comprueba cada 6 horas si toca el mantenimiento mensual.
	Nunca corre durante la reproducción de vídeo (mismo criterio que el resto de
	servicios de mantenimiento del addon)."""
	import xbmc
	from resources.lib.modules import log_utils
	monitor = control.monitor
	while not monitor.abortRequested():
		try:
			if enabled():
				try: last = float(getSetting(_LASTRUN_SETTING) or 0)
				except: last = 0
				if (time.time() - last) >= RUN_EVERY_DAYS * 86400 and not xbmc.Player().isPlayingVideo():
					pruned = prune_databases()
					control.setSetting(_LASTRUN_SETTING, str(int(time.time())))
					log_utils.log('[ plugin.video.luc_kodi ]  DB maintenance: %s filas antiguas purgadas y bases compactadas' % pruned, log_utils.LOGINFO)
		except: log_utils.error()
		if monitor.waitForAbort(6 * 3600): break # re-evaluar cada 6 horas
