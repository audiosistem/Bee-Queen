# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — yt_prefs.py (v1.0.62)

	Configura plugin.video.youtube DESDE luc_kodi, para que el usuario no
	tenga que entrar en sus ajustes ni elegir la variante en el OSD en cada
	reproduccion.

	EL PROBLEMA (medido en el codigo del addon, no supuesto). En
	kodion/items/xbmc/xbmc_items.py:

		stream_select = settings.stream_select()
		if not use_mpd and 'list' in stream_select:
			props['inputstream.adaptive.stream_selection_type'] = 'manual-osd'
		elif 'auto' in stream_select:
			props['inputstream.adaptive.stream_selection_type'] = 'adaptive'

	y en kodion/settings/abstract_settings.py:

		_STREAM_SELECT = {1: 'auto', 2: 'list', 3: 'auto+list', 4: 'ask+auto+list'}
		# use_mpd_videos() False  ->  kodion.video.stream.select, default 2

	Como nosotros EXIGIMOS "Use MPEG-DASH for videos" desactivado (es la unica
	via que sortea el muro de los 60 s, ver trailer.py), la rama que manda es
	kodion.video.stream.select, y su default de fabrica es 2 = 'list'. Eso le
	pasa a inputstream.adaptive stream_selection_type = 'manual-osd', o sea:
	ISA no elige nada y el usuario tiene que picar la variante a mano cada vez.

	Ponerlo a 1 ('auto') da stream_selection_type = 'adaptive' y desaparece el
	paso manual.

	LO QUE ESTO NO HACE. Con MPEG-DASH apagado NO hay control de codec de
	audio: los tokens mp4a/opus/vorbis viven en kodion.mpd.stream.features y
	solo aplican a la ruta DASH. En HLS suena el codec que lleve pegada la
	variante que elija ISA (mp4a.40.2 = AAC-LC en las altas, mp4a.40.5 =
	HE-AAC en las bajas). Esto quita el clic manual; no fuerza HE-AAC.
"""

import xbmcaddon
from resources.lib.modules import control
from resources.lib.modules import log_utils

LOGINFO = log_utils.LOGINFO

YT_PLUGIN = 'plugin.video.youtube'

# Marcador propio para no reaplicar el perfil en cada arranque del servicio.
MARKER = 'trailer.yt.configured'

# (id, tipo, valor). EL ORDEN IMPORTA: kodion.video.stream.select solo esta
# activo cuando quality.isa es true Y mpd.videos es false, asi que esos dos
# van primero.
PROFILE = (
	('kodion.video.quality.isa',   'bool', True),   # usar inputstream.adaptive
	('kodion.mpd.videos',          'bool', False),  # MPEG-DASH OFF -> ruta HLS
	('kodion.video.stream.select', 'int',  1),      # 1=auto  (2=list => manual-osd)
	('kodion.video.quality.ask',   'bool', False),  # sin dialogo de calidad
	('kodion.video.quality',       'int',  4),      # tope de esta rama (1080p live / 720p)
)


def _addon():
	"""Instancia del addon de YouTube, o None si falta o esta deshabilitado."""
	try:
		return xbmcaddon.Addon(YT_PLUGIN)
	except Exception:
		return None


def _read(addon, sid):
	try:
		return addon.getSetting(sid)
	except Exception:
		return ''


def _write(addon, sid, kind, value):
	"""Devuelve True si el ajuste existia y quedo con el valor pedido.

	getSetting devuelve '' cuando el id NO existe en esa version del addon
	(un boolean sin tocar devuelve 'false', no ''). Nunca escribimos a ciegas:
	si YouTube renombra un id en una actualizacion preferimos saltarlo y
	dejarlo en el log antes que crear basura en su settings.xml.
	"""
	if _read(addon, sid) == '':
		control.log('[ luc_kodi ] yt_prefs: %s not present in this YouTube version, skipped' % sid, LOGINFO)
		return False
	try:
		if kind == 'bool':
			addon.setSettingBool(sid, bool(value))
		elif kind == 'int':
			addon.setSettingInt(sid, int(value))
		else:
			addon.setSetting(sid, str(value))
	except Exception:
		log_utils.error()
		return False
	# Releemos: si el addon de YouTube esta corriendo con su copia en memoria
	# la escritura puede no cuajar, y prefiero enterarme aqui.
	confirmed = _read(addon, sid)
	control.log('[ luc_kodi ] yt_prefs: %s -> %s (readback %s)' % (sid, value, confirmed), LOGINFO)
	return True


def snapshot():
	"""Vuelca al log los ajustes relevantes del addon de YouTube. Diagnostico
	puro: antes de tocar nada conviene saber de donde partimos."""
	addon = _addon()
	if addon is None:
		control.log('[ luc_kodi ] yt_prefs: %s missing or disabled' % YT_PLUGIN, LOGINFO)
		return {}
	values = dict((sid, _read(addon, sid)) for sid, _k, _v in PROFILE)
	control.log('[ luc_kodi ] yt_prefs snapshot: %s' % values, LOGINFO)
	return values


def apply_profile(silent=False):
	"""Aplica el perfil. silent=True para la via automatica del servicio."""
	addon = _addon()
	if addon is None:
		if not silent:
			control.okDialog(message='The YouTube add-on is not installed or is disabled.')
		control.log('[ luc_kodi ] yt_prefs: %s missing or disabled' % YT_PLUGIN, LOGINFO)
		return False

	if not silent:
		ok = control.yesnoDialog(
			'This changes settings inside the YouTube add-on so trailers start without asking you to pick a stream every time.',
			'', '', heading='Configure the YouTube add-on')
		if not ok:
			return False

	snapshot()
	applied = [sid for sid, kind, value in PROFILE if _write(addon, sid, kind, value)]

	control.setSetting(MARKER, 'true')
	control.log('[ luc_kodi ] yt_prefs: applied %s of %s settings' % (len(applied), len(PROFILE)), LOGINFO)

	if not silent:
		if len(applied) == len(PROFILE):
			control.notification(message='YouTube add-on configured for trailers')
		else:
			control.okDialog(message='Configured %s of %s settings. Check the log for the ones that were skipped.'
			                 % (len(applied), len(PROFILE)))
	return bool(applied)


def ensure_once():
	"""Llamada desde service.py. Solo actua si el usuario lo pidio en ajustes
	(trailer.yt.autoconfig) y si no se hizo ya. Tocar los ajustes de otro addon
	sin permiso explicito no se hace."""
	try:
		if control.setting('trailer.yt.autoconfig') != 'true':
			return
		if control.setting(MARKER) == 'true':
			return
		apply_profile(silent=True)
	except Exception:
		log_utils.error()
