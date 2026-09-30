# -*- coding: utf-8 -*-
"""
    luc_kodi Add-on — gui_resolution.py

    Detecta la resolución GUI de Kodi y escribe dos window properties
    en homeWindow:

        luc_kodi.is_4k_display   'true' | 'false'
            Consumida por los menús (movies, tvshows, seasons, episodes,
            collections) para auto-activar FanartTV en pantallas 4K.

            OJO, cambió en la v1.0.72 y la cabecera decía lo contrario hasta
            la v1.0.74: este flag YA NO elige el tamaño del artwork. Los
            tamaños los decide el tope de cacheo de Kodi (<imageres> /
            <fanartres>) desde tmdb.auto_sizes(), porque pedir por encima del
            tope no conserva un píxel más. La pantalla solo vuelve a mandar en
            el sentido de que el test propone el tope A PARTIR del panel.

        luc_kodi.gui_resolution   '2160' | '1080'
            Resolución detectada, disponible para cualquier módulo
            que la necesite.

    Si la opción 'gui.resolution.enabled' está activa también cambia
    la resolución GUI de Kodi al valor configurado como target.

    Arquitectura — fast path síncrono + fallback en hilo:
        · run() intenta una sonda síncrona inmediata: si System.ScreenHeight
          ya devuelve un valor válido (caso normal — desktop, Android tibio,
          etc.) el flag se escribe SIN delay y los consumidores ven el valor
          correcto desde el primer instante.
        · Solo cuando la sonda devuelve 0 (Android Shield arrancando en frío,
          driver de pantalla todavía inicializando) se lanza el hilo daemon
          que reintenta cada 50 ms hasta _INIT_DELAY_MS.
        · is_4k_display(wait_ms) es la API pública que deben usar los
          consumidores: bloquea brevemente esperando al flag con timeout,
          de forma que el primer menú tras un boot de Android tampoco se
          quede sin artwork de alta calidad.
"""

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.modules import notif_queue

LOGINFO = log_utils.LOGINFO

# Guardia de sesión — una sola ejecución de la fase de cambio de resolución
_SESSION_FLAG  = 'luc_kodi.gui_resolution.done'

# Flag de calidad consumido por tmdb.py y los menús
DISPLAY_4K_FLAG = 'luc_kodi.is_4k_display'

# Flag de resolución detectada (string '2160' | '1080')
DISPLAY_RES_FLAG = 'luc_kodi.gui_resolution'

# v1.0.63 — por dónde salió la detección y cuánto tardó. Hasta ahora esto solo
# existía en el log, así que el caso que de verdad duele (el driver de Android
# tarda en responder y el primer menú se construye sin artwork bueno) no se
# podía ver desde el addon. display_test.py los lee.
DISPLAY_PATH_FLAG = 'luc_kodi.gui_resolution.path'   # 'sync' | 'thread' | 'late'
DISPLAY_MS_FLAG = 'luc_kodi.gui_resolution.ms'

# Umbral de altura para considerar pantalla 4K
_4K_HEIGHT_THRESHOLD = 2000

# Espera total máxima (ms) hasta que System.ScreenHeight devuelva un valor
# válido en arranques en frío de Android. Polling cada _POLL_MS.
_INIT_DELAY_MS = 600
_POLL_MS = 50

# Timeout por defecto (ms) que usan los consumidores en is_4k_display()
# para esperar a que el flag esté escrito. Generoso pero acotado.
_DEFAULT_WAIT_MS = 1500


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

def run():
	"""
    Llamado desde router.py (action=None) y GUIResolutionService.

    Estrategia: sonda síncrona inmediata; si falla, fallback en hilo daemon.
    En el 99% de los casos retorna en <1 ms con el flag ya escrito.
    """
	if control.homeWindow.getProperty(_SESSION_FLAG) == 'true':
		return
	control.homeWindow.setProperty(_SESSION_FLAG, 'true')

	# Fast path: sonda inmediata sin sleep
	import time as _time
	_t0 = _time.time()
	height = _read_screen_height()
	if height > 0:
		_mark_path('sync', (_time.time() - _t0) * 1000)
		_write_flags(height)
		# Solo lanzamos hilo si hay que cambiar resolución GUI (operación
		# potencialmente lenta por el JSON-RPC GetSettingOptions en Android)
		if control.setting('gui.resolution.enabled') == 'true':
			_spawn(target=_apply_resolution_change, args=(height,))
		else:
			control.log(
				'[ plugin.video.luc_kodi ]  GUIResolution: sync detected %spx — flag written'
				% height, LOGINFO
			)
		return

	# Slow path: el driver de pantalla todavía no responde — hilo con polling
	_spawn(target=_detect_with_polling)


def is_4k_display(wait_ms=_DEFAULT_WAIT_MS):
	"""
    Helper público para consumidores. Devuelve True si la pantalla GUI es 4K.

    Si el flag ya está escrito (caso normal) retorna inmediatamente.
    Si no — porque el primer menú se abre durante el arranque en frío de
    Android, antes de que la detección haya terminado — bloquea hasta
    `wait_ms` con polling cada _POLL_MS, y solo después devuelve el valor.

    Esto garantiza que el PRIMER menú tras boot también recibe artwork
    de alta calidad y FanartTV auto-activado en pantallas 4K.
    """
	try:
		import xbmc
		hw_get = control.homeWindow.getProperty
		flag = hw_get(DISPLAY_4K_FLAG)
		if flag in ('true', 'false'):
			return flag == 'true'
		# Espera con polling hasta el timeout o hasta que el flag aparezca
		waited = 0
		while waited < wait_ms:
			xbmc.sleep(_POLL_MS)
			waited += _POLL_MS
			flag = hw_get(DISPLAY_4K_FLAG)
			if flag in ('true', 'false'):
				return flag == 'true'
		# Timeout — última oportunidad: sondear directamente. Si tampoco hay
		# respuesta del driver, asumir no-4K (degradación elegante).
		height = _read_screen_height()
		if height > 0:
			_mark_path('late', waited)
			_write_flags(height)
			return height >= _4K_HEIGHT_THRESHOLD
		return False
	except Exception:
		log_utils.error()
		return False


def get_gui_resolution(wait_ms=_DEFAULT_WAIT_MS):
	"""Devuelve '2160' o '1080' según la pantalla GUI detectada."""
	return '2160' if is_4k_display(wait_ms) else '1080'


# ─────────────────────────────────────────────────────────────────────────────
# Internos
# ─────────────────────────────────────────────────────────────────────────────

def _read_screen_height():
	"""Lee System.ScreenHeight como int. Retorna 0 si no disponible."""
	try:
		s = control.infoLabel('System.ScreenHeight') or '0'
		return int(s)
	except (ValueError, TypeError):
		return 0


def _mark_path(path, ms):
	try:
		control.homeWindow.setProperty(DISPLAY_PATH_FLAG, path)
		control.homeWindow.setProperty(DISPLAY_MS_FLAG, str(int(ms)))
	except Exception:
		pass


def _write_flags(height):
	"""Escribe los dos window properties consumidos por el resto del addon.

    Si detectamos 4K por primera vez en la sesión (flag anterior != 'true'),
    programamos una limpieza de metacache en background para que las URLs de
    artwork se reconstruyan con calidad 'original' en lugar de las que pudo
    haber almacenado una detección fallida previa (race condition cold-boot).
    """
	is_4k = height >= _4K_HEIGHT_THRESHOLD
	detected = '2160' if is_4k else '1080'
	prev_flag = control.homeWindow.getProperty(DISPLAY_4K_FLAG)
	control.homeWindow.setProperty(DISPLAY_4K_FLAG,  'true' if is_4k else 'false')
	control.homeWindow.setProperty(DISPLAY_RES_FLAG, detected)
	# Upgrade 4K detectado: metacache puede contener URLs w780/w1280 grabadas
	# durante un arranque en frío donde is_4k_display() aún no tenía el flag.
	# Limpiar caché en background para que el siguiente fetch use 'original'.
	if is_4k and prev_flag != 'true':
		_spawn(target=_clear_metacache_for_4k_upgrade)
	_warn_below_minimum(height)
	return is_4k, detected


# Altura mínima para la que está pensado el addon. Por debajo de esto no se
# desactiva nada: sigue funcionando entero. Solo se avisa una vez de que el
# artwork, las fichas y las pantallas propias están dibujados para 1080p en
# adelante y ahí abajo no se ven como deberían.
MIN_HEIGHT = 1080
MIN_WIDTH = 1920
_WARNED_SETTING = 'display.belowMinimum.warned'


def _warn_below_minimum(height):
	"""Avisa UNA vez por instalación si la pantalla no llega a 1080p.

    Se guarda en los ajustes, no en una window property, a propósito: una
    property se borra al cerrar Kodi y el aviso volvería en cada arranque, que
    es la forma más rápida de que alguien deje de leer los avisos del addon.
    Quien cambie de pantalla puede volver a verlo borrando ese ajuste.
    """
	try:
		if height <= 0 or height >= MIN_HEIGHT:
			return
		if control.setting(_WARNED_SETTING) == 'true':
			return
		width = 0
		try:
			width = int(float(control.infoLabel('System.ScreenWidth') or 0))
		except (TypeError, ValueError):
			pass
		control.setSetting(_WARNED_SETTING, 'true')
		control.log(
			'[ luc_kodi ] GUIResolution: display %sx%s is below the %sx%s minimum'
			% (width or '?', height, MIN_WIDTH, MIN_HEIGHT), LOGINFO)
		control.okDialog(
			'luc_kodi',
			'Your display is %sx%s.[CR][CR]This add-on is built for %sx%s and '
			'above: its own screens, artwork and information panels are drawn '
			'for that size, and below it they will look cramped and soft.[CR][CR]'
			'Everything still works. For the experience this add-on is meant to '
			'give, use it on a display of at least %sx%s.'
			% (width or '?', height, MIN_WIDTH, MIN_HEIGHT, MIN_WIDTH, MIN_HEIGHT))
	except Exception:
		# Un aviso que impidiera arrancar seria mucho peor que no avisar.
		try:
			log_utils.error()
		except Exception:
			pass


def _clear_metacache_for_4k_upgrade():
	"""
    Limpia metacache cuando se confirma pantalla 4K por primera vez en sesión.

    Motivación (v1.0.74, actualizada): con la lógica actual los tamaños de
    imagen NO dependen de este flag, así que esta limpieza ya no existe para
    corregir URLs pequeñas. Sigue teniendo sentido por lo otro que el flag sí
    decide: FanartTV se auto-activa en 4K, y los metadatos cacheados durante
    el arranque en frío se grabaron sin ese arte adicional (clearlogo,
    clearart, póster/fanart alternativos). Limpiar fuerza un re-fetch que ya
    lo incluye.

    Espera 3 s para no competir con el arranque del skin/menú principal.
    Solo corre UNA vez por sesión gracias a la guardia en _write_flags
    (prev_flag != 'true').
    """
	try:
		import xbmc
		xbmc.sleep(3000)
		from resources.lib.database import metacache
		metacache.cache_clear_meta()
		control.log(
			'[ plugin.video.luc_kodi ]  GUIResolution: metacache cleared — '
			'4K upgrade detected, artwork URLs will refresh to original quality',
			LOGINFO
		)
	except Exception:
		log_utils.error()


def _spawn(target, args=()):
	try:
		from threading import Thread
		t = Thread(target=target, args=args, name='luc_kodi.gui_resolution')
		t.daemon = True
		t.start()
	except Exception:
		log_utils.error()


def _detect_with_polling():
	"""
    Hilo de fallback — solo se ejecuta si la sonda síncrona inicial devolvió 0.
    Sondea cada _POLL_MS hasta _INIT_DELAY_MS o hasta obtener un valor válido.
    """
	try:
		import xbmc
		height = 0
		waited = 0
		while waited < _INIT_DELAY_MS:
			xbmc.sleep(_POLL_MS)
			waited += _POLL_MS
			height = _read_screen_height()
			if height > 0:
				break
		_mark_path('thread', waited)

		is_4k, detected = _write_flags(height)
		control.log(
			'[ plugin.video.luc_kodi ]  GUIResolution: polled detection screen=%spx '
			'detected=%sp 4K=%s (waited=%sms)' % (height, detected, is_4k, waited),
			LOGINFO
		)

		if control.setting('gui.resolution.enabled') == 'true':
			_apply_resolution_change(height)
		else:
			control.log(
				'[ plugin.video.luc_kodi ]  GUIResolution: resolution change disabled'
				' — display flag written (%s)' % ('4K' if is_4k else '1080p'), LOGINFO
			)
	except Exception:
		log_utils.error()


def _apply_resolution_change(current_height):
	"""
    Fase 2 — Cambio de resolución GUI (solo si gui.resolution.enabled='true').
    Compara la altura detectada con el target del usuario y aplica el cambio
    via JSON-RPC si difieren.
    """
	try:
		import json

		is_4k    = current_height >= _4K_HEIGHT_THRESHOLD
		detected = '2160' if is_4k else '1080'
		target_res = '2160' if control.setting('gui.resolution.target') == '1' else '1080'

		control.log(
			'[ plugin.video.luc_kodi ]  GUIResolution: detected=%sp  target=%sp'
			% (detected, target_res), LOGINFO
		)

		# Sin cambio necesario — salir silenciosamente (sin notificación)
		if detected == target_res:
			control.log(
				'[ plugin.video.luc_kodi ]  GUIResolution: already at %sp — OK' % detected,
				LOGINFO
			)
			return

		# GetSettingOptions es costoso en Android — solo cuando hay discrepancia real
		query = json.dumps({
			'jsonrpc': '2.0',
			'method':  'Settings.GetSettingOptions',
			'params':  {'setting': 'videoscreen.resolution'},
			'id': 1
		})
		result  = json.loads(control.jsonrpc(query))
		options = result.get('result', {}).get('options', [])

		target_value = None
		for opt in options:
			label = str(opt.get('label', ''))
			if target_res == '2160' and (
				'2160' in label or '4K' in label.upper() or 'UHD' in label.upper()
			):
				target_value = opt.get('value')
				break
			elif target_res == '1080' and '1080' in label:
				target_value = opt.get('value')
				if 'p' in label.lower():
					break  # preferir "1080p" sobre "1080i"

		if target_value is not None:
			set_query = json.dumps({
				'jsonrpc': '2.0',
				'method':  'Settings.SetSettingValue',
				'params':  {'setting': 'videoscreen.resolution', 'value': target_value},
				'id': 1
			})
			control.jsonrpc(set_query)
			notif_queue.push(
				title   = 'luc_kodi · GUI',
				message = 'Set GUI: %sp' % target_res,
				time    = 4000
			)
			control.log(
				'[ plugin.video.luc_kodi ]  GUIResolution: changed to %sp (value=%s)'
				% (target_res, target_value), LOGINFO
			)
			# Tras el cambio, refrescar flags con la nueva altura. El driver
			# puede tardar — segundo pase corto no bloqueante.
			_spawn(target=_refresh_flags_after_change)
		else:
			notif_queue.push(
				title   = 'luc_kodi · GUI',
				message = 'Set GUI: %sp unavailable' % target_res,
				time    = 4000
			)
			control.log(
				'[ plugin.video.luc_kodi ]  GUIResolution: %sp not available in options'
				% target_res, LOGINFO
			)

	except Exception:
		log_utils.error()


def _refresh_flags_after_change():
	"""Tras un cambio efectivo de resolución GUI, esperar a que el driver
    reporte la nueva altura y reescribir los flags."""
	try:
		import xbmc
		# Pausa generosa para que Kodi termine el switch de modo de vídeo
		xbmc.sleep(1500)
		height = _read_screen_height()
		if height > 0:
			_write_flags(height)
			control.log(
				'[ plugin.video.luc_kodi ]  GUIResolution: flags refreshed after change (%spx)'
				% height, LOGINFO
			)
	except Exception:
		log_utils.error()
