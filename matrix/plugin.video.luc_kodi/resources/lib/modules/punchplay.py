# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	PunchPlay.tv integration module — FULL in-plugin client.

	Cuarto servicio de tracking del addon, junto a Trakt, SIMKL y MDBList, y
	construido con el mismo principio: totalmente autonomo, sin depender de
	ninguno de los otros tres.

	API: https://docs.punchplay.tv  (Platform API v1 beta + Public API v1)

	  Platform  https://punchplay.tv/api/platform/v1   (Bearer, con scopes)
	  Public    https://punchplay.tv/api/public/v1     (sin auth, solo lectura)

	AUTENTICACION — Device Code (PIN + QR), igual que Trakt/SIMKL/MDBList:
	  POST /auth/device/code   -> user_code, device_code, verification_uri,
	                              verification_uri_complete, verification_uri_qr
	  POST /auth/device/token  -> access_token, refresh_token (polling)
	  POST /auth/refresh       -> renovacion (el refresh ROTA en cada uso)

	El cliente registrado para luc_kodi es PUBLICO: manda client_id y NADA
	mas. La documentacion de PunchPlay lo dice explicitamente — "Do not embed
	client_secret in native apps, browser apps, or sample code intended for
	public distribution" — y un addon de Kodi es exactamente eso. Un cliente
	publico en device flow simplemente omite el secret. Por eso en este modulo
	NO hay, ni debe haber nunca, ningun client_secret.

	TRES DIFERENCIAS con los otros tres servicios que hay que tener presentes:

	  1) ESCALA DEL PROGRESO. En las ESCRITURAS `progress` es una FRACCION
	     0..1 (0.4317 = 43,17%). En las LECTURAS el campo se llama
	     `progressPercent` y viene en PORCENTAJE 0..100. Trakt, SIMKL y
	     MDBList usan porcentaje en ambos sentidos. Copiar su calculo tal cual
	     registraria todo al 1% de lo real. La conversion vive en un unico
	     sitio: _pct_to_fraction() / _fraction_to_pct().

	  2) NOMBRES DE CAMPO. Las PETICIONES van en snake_case (tmdb_id,
	     position_seconds, playback_session_id) y las RESPUESTAS vuelven en
	     camelCase (tmdbId, progressSeconds, durationSeconds). No es un error
	     de la documentacion: es asi en los dos ejemplos del quickstart.

	  3) CICLO DE VIDA COMPLETO. PunchPlay tiene cinco acciones de playback
	     (start/pause/resume/stop/progress) en vez de las tres de Trakt/SIMKL.
	     `progress` es el latido, y pause/resume son eventos REALES del
	     usuario, no un keep-alive. Por eso aqui el latido periodico manda
	     `progress` y NO `pause` como se hace en SIMKL y MDBList: mandar pause
	     cada minuto dejaria la cuenta permanentemente "en pausa".

	TOKENS: el access token dura 1 HORA (mucho menos que Trakt) y el refresh
	ROTA en cada uso — dos renovaciones en paralelo se invalidan mutuamente y
	echan al usuario. De ahi el single-flight con Lock y el refresco proactivo,
	mismo patron que trakt.py.

	PARSERS TOLERANTES: la documentacion publica describe los endpoints y la
	paginacion pero NO el esquema exacto de cada item de /me/lists,
	/playback/in-progress, /me/continue-watching ni /me/history. En vez de
	adivinar, se aceptan varias formas de envoltura y varios alias por campo, y
	se registra la FORMA real (tipos y nombres de clave, nunca contenido) en
	kodi.log de forma incondicional. Es exactamente lo que costo tres builds
	descubrir en MDBList; aqui se parte ya con la red puesta.
"""

from resources.lib.modules import app_keys
import time
import uuid

import requests
from threading import Lock

from resources.lib.modules import control
from resources.lib.modules import log_utils

BASE_URL = 'https://punchplay.tv'
API = BASE_URL + '/api/platform/v1'
PUBLIC_API = BASE_URL + '/api/public/v1'

_DEVICE_CODE_URL = API + '/auth/device/code'
_DEVICE_TOKEN_URL = API + '/auth/device/token'
_DEVICE_REFRESH_URL = API + '/auth/refresh'
_VERIFY_URL = BASE_URL + '/link'

# client_id de la app luc_kodi registrada en punchplay.tv/developers como
# cliente PUBLICO. Viaja dentro del plugin, oculto pero funcional, igual que
# trakt.client_id y mdblist.client_id: es el puente para que el Device Flow
# (PIN + QR) funcione recien instalado. NO es una credencial de cuenta y no
# lleva secret asociado. El usuario puede sobreescribirlo en Ajustes si
# registra su propia app.
DEFAULT_CLIENT_ID = app_keys.get('punchplay')

# Juego de scopes del cliente nativo completo, tal y como lo recomienda
# docs.punchplay.tv/native-app-api. Se piden TODOS en la autorizacion: pedir
# uno nuevo despues obliga al usuario a volver a aprobar la app y a recibir un
# token nuevo antes de que el endpoint correspondiente responda.
# Fuera quedan `notifications:write` (no escribimos preferencias de aviso) y
# los `/me/push-devices`, reservados a clientes de primera parte.
SCOPES = ('profile:read profile:write playback:read playback:write events:read '
		  'history:read history:write lists:read lists:write ratings:read '
		  'ratings:write collection:read collection:write notifications:read '
		  'trophies:read')

APP_NAME = 'luc_kodi'
LOG_TAG = '[luc_kodi-punchplay]'

getSetting = control.setting
setSetting = control.setSetting

# El access token dura 3600 s. Se renueva con 5 minutos de margen en vez de
# esperar al 401: asi una reproduccion larga no pierde ningun latido.
_REFRESH_MARGIN = 300
_refresh_lock = Lock()

# Propiedad de ventana con el id de sesion de reproduccion en curso. Va en
# window property y no en una global del modulo porque el servicio y el plugin
# corren en invokers distintos y los dos pueden mandar eventos de la misma
# reproduccion; el backend ordena por playback_session_id y descartaria como
# sesion ajena lo que llegase con otro id.
_PROP_SESSION = 'luc_kodi.punchplay.session'
# Titulo y ano de lo que se esta reproduciendo, sembrados por scrobbleStart.
#
# El stop de PunchPlay EXIGE title: sin el devuelve
# 400 "title must be a non-empty string of at most 500 characters".
# El problema es de donde sale la llamada: start, progress, pause y resume los
# dispara player.Player, que tiene self.title a mano, pero el stop sale de
# Bookmarks.set_scrobble(), cuya firma —compartida con Trakt, SIMKL y MDBList—
# solo lleva ids, tiempos y tipo. Resultado en el log del 18-sep: todos los
# start y progress OK y TODOS los stop a 400, o sea cero historial escrito.
# Se siembra aqui en vez de ampliar la firma de set_scrobble para no tocar una
# funcion de la que cuelgan los otros tres servicios.
_PROP_MEDIA = 'luc_kodi.punchplay.media'

# Almacen de tokens en window properties.
#
# POR QUE NO BASTA CON setSetting/getSetting — fallo real cazado en el log del
# 18-sep-2026, y la razon por la que la cuenta se quedaba muerta tras una sola
# renovacion:
#
#   control.setting() NO consulta xbmcaddon: lee un dict cacheado en la window
#   property 'luc_kodi_settings', y control.setSetting() invalida esa property
#   despues de escribir. La siguiente lectura reconstruye el dict con
#   make_settings_dict(), que PARSEA EL settings.xml DE DISCO. Pero Kodi no
#   vuelca settings.xml a disco en el momento de setSetting(): lo hace mas
#   tarde. Resultado: escribimos el token nuevo y acto seguido leemos el VIEJO.
#
#   Con Trakt, SIMKL y MDBList eso no se nota, porque su refresh token NO rota
#   y reutilizar el viejo sigue funcionando. El de PunchPlay ROTA: emitir el
#   nuevo mata el anterior en el acto. El ciclo era — renovar OK (el servidor
#   emite R2 y mata R1) -> releer de disco y obtener todavia A1/R1 -> peticion
#   con A1 -> 401 -> renovar con R1 -> invalid_grant para siempre. Un unico
#   refresco bastaba para dejar la cuenta inservible, y por eso el addon decia
#   "no estas asociado" teniendo una autorizacion valida.
#
# Las window properties son inmediatas y las comparten TODOS los invokers de
# Kodi (servicio y plugin corren en el mismo proceso), que es justo el motivo
# por el que el propio addon usa 'luc_kodi_settings' como cache compartida.
# Mandan ellas mientras Kodi este vivo; los ajustes quedan como copia duradera
# para el siguiente arranque, cuando el settings.xml ya esta volcado.
_PROP_TOKEN = 'luc_kodi.punchplay.tok'
_PROP_REFRESH = 'luc_kodi.punchplay.ref'
_PROP_EXPIRES = 'luc_kodi.punchplay.exp'
# Enfriamiento tras un refresh rechazado: sin el, cada accion del menu volvia a
# intentarlo y el log salia con una linea invalid_grant por pantalla visitada.
_PROP_REFRESH_DEAD = 'luc_kodi.punchplay.refdead'
_REFRESH_DEAD_COOLDOWN = 600

# Marca de "el servicio esta caido".
#
# El 19-sep PunchPlay devolvio 503 "no available server" en las diecisiete
# peticiones de una sesion, publicas y autenticadas por igual, y su propia web
# mostraba lo mismo. El addon lo conto como si la cuenta se hubiera
# desautorizado y ofrecio volver a asociar, que es un consejo INUTIL cuando el
# servidor no esta: la autorizacion tampoco iba a funcionar. Un 5xx o un fallo
# de red no dicen nada sobre el token, asi que se registran aparte y el aviso
# al usuario cambia en consecuencia.
_PROP_OUTAGE = 'luc_kodi.punchplay.outage'
_OUTAGE_WINDOW = 300


def _mark_outage():
	_set_prop(_PROP_OUTAGE, time.time())


def _clear_outage():
	_clear_prop(_PROP_OUTAGE)


def service_is_down():
	"""True si hubo un 5xx o un fallo de red hace menos de cinco minutos."""
	mark = _prop(_PROP_OUTAGE)
	if not mark:
		return False
	try:
		return (time.time() - float(mark)) < _OUTAGE_WINDOW
	except Exception:
		return False


def _prop(name):
	try:
		return control.homeWindow.getProperty(name) or ''
	except Exception:
		return ''


def _set_prop(name, value):
	try:
		control.homeWindow.setProperty(name, str(value))
	except Exception:
		pass


def _clear_prop(name):
	try:
		control.homeWindow.clearProperty(name)
	except Exception:
		pass

# Suelos de "Mi Progreso", los mismos que SIMKL para que las tres secciones se
# comporten igual: por debajo del 5% es un toque accidental, por encima del 85%
# es historial, no algo a medias.
# En Trakt, SIMKL y MDBList hay que filtrar por porcentaje porque su feed de
# playback devuelve de todo, incluidos toques accidentales. PunchPlay NO: el
# endpoint se llama /playback/in-progress y ya es la lista curada de lo que el
# servidor considera reanudable — lo mismo que su web pinta en Continue
# Watching. Copiar el suelo del 5% de SIMKL escondia cosas que PunchPlay SI
# muestra: en el log del 18-sep, "The End of Oak Street" al 3% quedaba fuera
# aqui y aparecia en su perfil. Solo se descarta lo practicamente terminado,
# que es historial y no algo a medias.
PROGRESS_MAX_PCT = 98.0


# ---------------------------------------------------------------------------
# Diagnostico
# ---------------------------------------------------------------------------
# NO pasa por log_utils.log(): esa funcion aborta en su primera linea si
# `debug.enabled` no esta a true y, con debug.location=1, escribe en un fichero
# aparte. En el equipo del usuario eso significa que los avisos de fallo son
# invisibles y que su ausencia no prueba nada. Mismo patron y misma razon que
# gemini_api.py y mdblist.py.

def _hard_log(msg, level=2):
	"""Traza incondicional a kodi.log. No depende de ningun ajuste."""
	try:
		import xbmc
		xbmc.log('%s %s' % (LOG_TAG, msg), level)
	except Exception:
		pass


def _dev_log(msg):
	"""Traza por peticion. Solo con dev.mode.enable activo."""
	try:
		if getSetting('dev.mode.enable') == 'true':
			_hard_log(msg, 1)
	except Exception:
		pass


def _shape(data, depth=0):
	"""Descripcion COMPACTA de la forma de una respuesta, para el log.

	Vuelca tipos, tamanos y NOMBRES DE CLAVE — nunca contenido — asi que no
	filtra titulos ni ids a un log que el usuario comparte. Es lo que permite
	distinguir "la peticion fue mal" de "la peticion fue bien pero la
	envoltura no es la que el parser espera", que es el fallo que costo tres
	builds en MDBList."""
	try:
		if data is None:
			return 'None'
		if isinstance(data, list):
			s = 'list[%d]' % len(data)
			if data and depth < 2:
				s += ' -> ' + _shape(data[0], depth + 1)
			return s
		if isinstance(data, dict):
			keys = sorted(data.keys())
			# 14 claves se quedaron cortas con /playback/in-progress: el '+11'
			# escondia justamente los campos de id que hacian falta.
			s = 'dict{%s}' % ', '.join(keys[:32])
			if len(keys) > 32:
				s += ', +%d' % (len(keys) - 32)
			if depth < 2:
				for k in ('items', 'results', 'data', 'lists', 'history', 'entries'):
					if isinstance(data.get(k), list):
						s += ' | %s=%s' % (k, _shape(data[k], depth + 1))
						break
			return s
		return type(data).__name__
	except Exception:
		return '?'


def _log_shape(tag, data, extra=''):
	"""Aviso cuando un parser saca 0 items de una respuesta NO vacia."""
	_hard_log('%s: 0 items parsed from %s %s' % (tag, _shape(data), extra), 3)


def _log_fail(method, path, status, body='', exc=None):
	"""Fallo de peticion, SIEMPRE visible, con codigo HTTP, request_id y un
	extracto del cuerpo. Sin el codigo no se distingue un 401 de token de un
	404 de endpoint inexistente de un 403 de scope que falta, y son tres
	arreglos distintos. PunchPlay ademas devuelve `request_id` en el cuerpo y
	`X-PunchPlay-Request-Id` en la cabecera: es lo que su soporte pide para
	mirar un fallo concreto, asi que se registra siempre que venga."""
	msg = '%s %s FAILED: HTTP %s' % (method, path, status)
	if exc is not None:
		msg += ' | %s' % type(exc).__name__
	if body:
		msg += ' | %s' % str(body)[:220].replace('\n', ' ')
	_hard_log(msg, 3)


# ---------------------------------------------------------------------------
# Credenciales y tokens
# ---------------------------------------------------------------------------

def _client_id():
	"""client_id de la app. El del usuario si lo ha puesto, si no el del
	plugin. Se lee en CADA llamada, no al importar: con reuselanguageinvoker el
	modulo sobrevive entre invocaciones y un valor izado al import no se
	entera de un cambio en Ajustes hasta reiniciar Kodi (fallo real de SIMKL,
	corregido en la v1.0.59)."""
	cid = (getSetting('punchplay.client_id') or '').strip()
	return cid or DEFAULT_CLIENT_ID


def _access_token():
	# La property manda: puede llevar un token que el settings.xml de disco
	# todavia no refleja. El ajuste es la copia que sobrevive al reinicio.
	return (_prop(_PROP_TOKEN) or getSetting('punchplay.token') or '').strip()


def _refresh_token():
	return (_prop(_PROP_REFRESH) or getSetting('punchplay.refresh') or '').strip()


def getPunchPlayCredentialsInfo():
	"""True si hay un access token utilizable."""
	tok = _access_token()
	return bool(tok and tok not in ('0', 'empty_setting'))


def getPunchPlayScrobbleInfo():
	"""True si el usuario ha activado el scrobbling Y esta autorizado.
	Pensado para player.py, igual que getMDBListScrobbleInfo()."""
	if getSetting('punchplay.scrobble') != 'true':
		return False
	return getPunchPlayCredentialsInfo()


def _device_id():
	"""Identificador estable de este aparato, generado una sola vez. PunchPlay
	lo usa para distinguir sesiones de dispositivos distintos de la misma
	cuenta. No lleva nada identificativo: es un uuid4 local."""
	did = (getSetting('punchplay.device_id') or '').strip()
	if not did:
		did = uuid.uuid4().hex
		try:
			setSetting('punchplay.device_id', did)
		except Exception:
			pass
	return did


def _client_version():
	# control.addonVersion() exige el id del addon como argumento; el helper
	# sin argumentos del proyecto es getluc_kodiVersion().
	try:
		return control.getluc_kodiVersion()
	except Exception:
		return '1.0.0'


def _store_tokens(data):
	"""Guarda el juego de tokens. El refresh ROTA: el viejo deja de valer en
	el instante en que el nuevo se emite, asi que se escriben los dos juntos y
	nunca uno solo."""
	try:
		access = data.get('access_token')
		if not access:
			return False
		refresh = data.get('refresh_token')
		try:
			expires_in = float(data.get('expires_in') or 3600)
		except Exception:
			expires_in = 3600
		expires_at = str(time.time() + expires_in)
		# PRIMERO las properties, que son inmediatas. Si el proceso muriera
		# entre las dos escrituras, es preferible tener el juego nuevo vivo en
		# memoria que solo en un settings.xml todavia sin volcar.
		_set_prop(_PROP_TOKEN, access)
		if refresh:
			_set_prop(_PROP_REFRESH, refresh)
		_set_prop(_PROP_EXPIRES, expires_at)
		_clear_prop(_PROP_REFRESH_DEAD)
		setSetting('punchplay.token', access)
		if refresh:
			setSetting('punchplay.refresh', refresh)
		setSetting('punchplay.expires', expires_at)
		setSetting('punchplay.isauthed', 'true')
		scope = data.get('scope')
		if scope:
			setSetting('punchplay.scopes', scope)
		return True
	except Exception:
		log_utils.error()
		return False


def _token_expired():
	"""True si falta menos de _REFRESH_MARGIN para caducar, o si no hay fecha
	(instalacion vieja o ajuste perdido: mas vale renovar de mas)."""
	expires = (_prop(_PROP_EXPIRES) or getSetting('punchplay.expires') or '').strip()
	if not expires:
		return True
	try:
		return (float(expires) - time.time()) < _REFRESH_MARGIN
	except Exception:
		return True


def _refresh_is_dead():
	"""True si un refresh fue RECHAZADO hace poco.

	Sin esto, con la cadena de refresh rota cada visita a un menu lanzaba otra
	renovacion condenada: en el log del 18-sep salieron nueve invalid_grant en
	un minuto, uno por pantalla abierta. Solo lo levanta una autorizacion nueva,
	que limpia la marca desde _store_tokens()."""
	mark = _prop(_PROP_REFRESH_DEAD)
	if not mark:
		return False
	try:
		return (time.time() - float(mark)) < _REFRESH_DEAD_COOLDOWN
	except Exception:
		return False


def _do_refresh_token():
	"""Renovacion real. SIEMPRE se llama con _refresh_lock adquirido."""
	if _refresh_is_dead():
		return False
	refresh = _refresh_token()
	if not refresh:
		return False
	cid = _client_id()
	if not cid:
		return False
	if service_is_down():
		# Renovar contra un servidor caido solo sirve para ensuciar el log.
		return False
	try:
		r = requests.post(_DEVICE_REFRESH_URL,
						  json={'client_id': cid, 'refresh_token': refresh},
						  timeout=20)
		if r.status_code >= 500:
			_log_fail('POST', '/auth/refresh', r.status_code, 'servicio caido')
			_mark_outage()
			return False
		if r.status_code == 200:
			data = r.json()
			if _store_tokens(data):
				_hard_log('token renovado (expires_in=%s)' % data.get('expires_in'), 1)
				return True
			return False
		body = ''
		try:
			body = r.text or ''
		except Exception:
			pass
		_log_fail('POST', '/auth/refresh', r.status_code, body)
		# Un refresh rechazado es definitivo: el token rotado ya no existe en
		# el servidor. Se marca la cuenta como no autorizada para que el resto
		# del addon deje de intentarlo en bucle y el usuario vea el motivo.
		if r.status_code in (400, 401, 403):
			_set_prop(_PROP_REFRESH_DEAD, time.time())
			_mark_reauth_needed()
		return False
	except Exception as e:
		_log_fail('POST', '/auth/refresh', '?', '', e)
		return False


def ensure_token():
	"""Refresco proactivo single-flight. Si el token esta a punto de caducar,
	lo renueva UNA sola vez aunque varios hilos lleguen a la vez.

	El doble chequeo dentro del lock no es adorno: sin el, dos hilos que
	encuentran el token caducado renovarian los dos, y como el refresh rota,
	el segundo invalidaria el del primero y echaria al usuario. Es el fallo
	que la propia documentacion de PunchPlay avisa en su recuadro de aviso."""
	if not getPunchPlayCredentialsInfo():
		return False
	if not _token_expired():
		return True
	with _refresh_lock:
		if not _token_expired():
			return True
		return _do_refresh_token()


_PROP_REAUTH = 'luc_kodi.punchplay.reauth'


def _mark_reauth_needed():
	"""Aviso de "vuelve a autorizar", como maximo uno por hora.

	Sin el debounce, una sesion con el refresh muerto lanza el aviso en cada
	peticion: es justo la rafaga de "Please Re-Authorize" que hubo que
	apagar en Trakt."""
	try:
		last = control.homeWindow.getProperty(_PROP_REAUTH)
		if last and (time.time() - float(last)) < 3600:
			return
		control.homeWindow.setProperty(_PROP_REAUTH, str(time.time()))
		setSetting('punchplay.isauthed', 'false')
		control.notification(title='PunchPlay',
							 message='Please re-authorize your PunchPlay account.')
	except Exception:
		pass


def _clear_reauth():
	try:
		control.homeWindow.clearProperty(_PROP_REAUTH)
	except Exception:
		pass


# ---------------------------------------------------------------------------
# Transporte
# ---------------------------------------------------------------------------

def _headers():
	return {
		'Authorization': 'Bearer %s' % _access_token(),
		'Accept': 'application/json',
		'Content-Type': 'application/json',
		'User-Agent': '%s/%s' % (APP_NAME, _client_version()),
	}


def _request(method, path, json_data=None, params=None, timeout=15,
			 silent=False, _retry=True):
	"""Peticion a la Platform API con Bearer, renovacion proactiva y un unico
	reintento tras 401.

	Devuelve el JSON parseado, {} si la respuesta no trae cuerpo, o None si
	fallo. Nunca lanza: los llamantes son constructores de directorio y una
	excepcion que suba deja la ventana de Kodi en "updating in progress"."""
	if not getPunchPlayCredentialsInfo():
		return None
	ensure_token()
	url = API + path
	try:
		r = requests.request(method, url, headers=_headers(), json=json_data,
							 params=params, timeout=timeout)
	except Exception as e:
		_log_fail(method, path, '?', '', e)
		_mark_outage()
		return None

	if r.status_code >= 500 or r.status_code == 429:
		# Caida o saturacion del servicio. NO es un problema de credenciales y
		# no debe tocarlas ni provocar un reintento de refresco.
		body = ''
		try:
			body = (r.text or '')[:160]
		except Exception:
			pass
		_log_fail(method, path, r.status_code, body)
		_mark_outage()
		return None

	if r.status_code == 401 and _retry:
		# Token caducado antes de tiempo (revocado, rotado en otro aparato).
		# Se renueva una vez y se reintenta; si vuelve a fallar, se rinde.
		with _refresh_lock:
			ok = _do_refresh_token()
		if ok:
			return _request(method, path, json_data=json_data, params=params,
							timeout=timeout, silent=silent, _retry=False)
		return None

	if r.status_code >= 400:
		body, req_id = '', ''
		try:
			body = r.text or ''
			req_id = r.headers.get('X-PunchPlay-Request-Id') or ''
		except Exception:
			pass
		if req_id:
			body = '%s | request_id=%s' % (body, req_id)
		_log_fail(method, path, r.status_code, body)
		if r.status_code == 403 and 'insufficient_scope' in (body or ''):
			_hard_log('falta un scope: el usuario autorizo antes de que la app '
					  'lo pidiera. Hay que volver a autorizar.', 3)
		return None

	try:
		data = r.json()
	except Exception:
		data = {}
	_clear_outage()
	_dev_log('%s %s -> %s %s' % (method, path, r.status_code, _shape(data)))
	return data


def _get(path, params=None, timeout=15):
	return _request('GET', path, params=params, timeout=timeout)


def _post(path, json_data=None, timeout=15, silent=False):
	return _request('POST', path, json_data=json_data, timeout=timeout, silent=silent)


def _public_get(path, params=None, timeout=15):
	"""Public API: sin auth, sin token, sin scopes."""
	try:
		r = requests.get(PUBLIC_API + path, params=params, timeout=timeout,
						 headers={'Accept': 'application/json',
								  'User-Agent': '%s/%s' % (APP_NAME, _client_version())})
		if r.status_code >= 400:
			_log_fail('GET', '/public' + path, r.status_code, r.text)
			if r.status_code >= 500 or r.status_code == 429:
				_mark_outage()
			return None
		data = r.json()
		_dev_log('GET /public%s -> %s %s' % (path, r.status_code, _shape(data)))
		return data
	except Exception as e:
		_log_fail('GET', '/public' + path, '?', '', e)
		_mark_outage()
		return None


# ---------------------------------------------------------------------------
# Paginacion  —  PunchPlay usa DOS sistemas distintos
# ---------------------------------------------------------------------------
# Por cursor opaco (`nextCursor` en el cuerpo, se devuelve como `cursor`):
#   /me/history, /me/lists, /me/collection, /me/notifications, /lists/{id}/items
# Por numero de pagina (`page`, y responde total/page/pageSize/hasMore):
#   /me/ratings, /me/favourites, /me/watch-status
#
# Leer un endpoint de cursor de un solo tiron devuelve la PRIMERA pagina y
# nada mas, sin error: la documentacion lo avisa expresamente para
# /me/collection y /me/lists, que antes devolvian el juego entero. Es el mismo
# truncado silencioso que se comio las listas grandes de MDBList.
#
# Los cursores son cadenas OPACAS: no se parsean ni se construyen, y el resto
# de parametros de la consulta se mantiene identico entre paginas.

_LIST_KEYS = ('items', 'results', 'data', 'lists', 'history', 'entries')


def _unwrap_list(data, extra_keys=()):
	"""Saca la lista de items de una respuesta, acepte la forma que acepte.

	Acepta lista pelada, o dict bajo cualquiera de las claves conocidas, y
	como ultimo recurso el unico valor de tipo lista que tenga el dict."""
	if data is None:
		return []
	if isinstance(data, list):
		return data
	if not isinstance(data, dict):
		return []
	for k in tuple(extra_keys) + _LIST_KEYS:
		v = data.get(k)
		if isinstance(v, list):
			return v
	lists = [v for v in data.values() if isinstance(v, list)]
	if len(lists) == 1:
		return lists[0]
	return []


def _get_all_pages(path, params=None, limit=None, max_pages=20, extra_keys=()):
	"""GET siguiendo la paginacion por CURSOR hasta agotarla."""
	p = dict(params or {})
	if limit:
		p['limit'] = limit
	out, pages, cursor = [], 0, None
	while pages < max_pages:
		if cursor:
			p['cursor'] = cursor
		data = _get(path, params=p, timeout=20)
		if data is None:
			return out or None
		pages += 1
		chunk = _unwrap_list(data, extra_keys)
		out.extend(chunk)
		cursor = data.get('nextCursor') if isinstance(data, dict) else None
		if not cursor:
			break
	if pages > 1:
		_hard_log('%s leido en %d paginas (%d items)' % (path, pages, len(out)))
	return out


def _get_all_pages_numbered(path, params=None, max_pages=20, extra_keys=()):
	"""GET siguiendo la paginacion por NUMERO DE PAGINA hasta agotarla."""
	p = dict(params or {})
	out, page = [], 1
	while page <= max_pages:
		p['page'] = page
		data = _get(path, params=p, timeout=20)
		if data is None:
			return out or None
		chunk = _unwrap_list(data, extra_keys)
		out.extend(chunk)
		has_more = bool(data.get('hasMore')) if isinstance(data, dict) else False
		if not has_more or not chunk:
			break
		page += 1
	if page > 1:
		_hard_log('%s leido en %d paginas (%d items)' % (path, page, len(out)))
	return out


# ---------------------------------------------------------------------------
# Lectura tolerante de campos
# ---------------------------------------------------------------------------
# Las respuestas vienen en camelCase, pero la documentacion publica no fija el
# esquema de cada item. Cada lector acepta los alias plausibles (camelCase,
# snake_case y la forma anidada `ids{}`) para que un cambio de nombre no deje
# el menu vacio sin explicacion.

def _first(d, *keys):
	"""Primer valor no vacio de entre varias claves."""
	if not isinstance(d, dict):
		return ''
	for k in keys:
		v = d.get(k)
		if v not in (None, '', [], {}):
			return v
	return ''


def _ids_of(raw):
	"""Devuelve (imdb, tmdb, tvdb) como cadenas, mirando tanto en la raiz como
	en un posible sub-dict `ids`. Nunca devuelve la cadena 'None': un null de
	JSON pasado por str() da 'None', que es truthy y revienta la busqueda de
	metadatos aguas abajo. Fallo real encontrado en MDBList."""
	if not isinstance(raw, dict):
		return '', '', ''
	ids = raw.get('ids') if isinstance(raw.get('ids'), dict) else {}
	def pick(*keys):
		v = _first(raw, *keys) or _first(ids, *keys)
		if v in (None, '', 'None', 'null'):
			return ''
		return str(v)
	imdb = pick('imdbId', 'imdb_id', 'imdb')
	# showSourceId PRIMERO. En /playback/in-progress un episodio trae el id de
	# la SERIE en `showSourceId` y el suyo propio en los campos genericos
	# (forma real del log del 19-sep: backdropPath, durationSeconds, episode,
	# episodeTitle, id, mediaSource, nowPlaying, playbackState, posterPath,
	# progressKey, progressPercent, progressSeconds, season, showSourceId...).
	# Los scrapers y el indexador trabajan SIEMPRE con el id de la serie.
	tmdb = pick('showSourceId', 'show_source_id', 'showTmdbId', 'show_tmdb_id',
				'tmdbId', 'tmdb_id', 'tmdb', 'sourceId', 'source_id')
	tvdb = pick('tvdbId', 'tvdb_id', 'tvdb', 'showTvdbId', 'show_tvdb_id')
	return imdb, tmdb, tvdb


def _media_kind(raw):
	"""'movie' | 'show' | '' a partir de kind/type/mediaType."""
	v = str(_first(raw, 'kind', 'type', 'mediaType', 'media_type') or '').lower()
	if v in ('movie', 'movies', 'film'):
		return 'movie'
	if v in ('show', 'shows', 'tv', 'series', 'tvshow', 'episode'):
		return 'show'
	return ''


# Sub-dicts donde PunchPlay puede colgar los numeros de temporada y episodio.
# Si no se encuentran, int(None or 0) los convertia en 0 y el item seguia vivo
# como 0x00: sin metadatos, porque TMDb no tiene esa temporada, y con el punto
# de resume sembrado bajo una clave con ceros, asi que al abrir la serie no
# habia nada que reanudar. Un mismo cero explicaba los dos sintomas del
# 19-sep.
_NESTED_NUMBER_KEYS = ('episode', 'nextEpisode', 'next_episode', 'currentEpisode',
					   'current_episode', 'showProgress', 'show_progress', 'item')


def _nested_dicts(raw):
	"""El propio dict y los sub-dicts donde suelen colgar los numeros."""
	yield raw
	if isinstance(raw, dict):
		for k in _NESTED_NUMBER_KEYS:
			v = raw.get(k)
			if isinstance(v, dict):
				yield v


def _season_of(raw):
	for node in _nested_dicts(raw):
		v = _first(node, 'season', 'seasonNumber', 'season_number')
		try:
			n = int(v)
			if n >= 0:
				return n
		except Exception:
			continue
	return None


def _episode_of(raw):
	for node in _nested_dicts(raw):
		v = _first(node, 'episode', 'episodeNumber', 'episode_number', 'number')
		try:
			n = int(v)
			if n >= 0:
				return n
		except Exception:
			continue
	return None


def _year_of(raw):
	v = _first(raw, 'year', 'releaseYear', 'release_year')
	if not v:
		date = str(_first(raw, 'releaseDate', 'release_date', 'firstAirDate',
						  'first_air_date', 'airDate', 'air_date') or '')
		v = date[:4] if len(date) >= 4 else ''
	return str(v or '')


def _pct_to_fraction(pct):
	"""Porcentaje 0..100 -> fraccion 0..1 acotada, con 4 decimales.

	Los 4 decimales son el paso del quickstart (0.4317) y valen ~0,5 s en una
	pelicula de 140 min. Acotar no es paranoia: un getTotalTime() a 0 durante
	el arranque da una division absurda, y un progress fuera de rango es lo
	que hacia que MDBList devolviera 400 en TODAS las pausas."""
	try:
		f = float(pct) / 100.0
	except Exception:
		return 0.0
	return round(min(max(f, 0.0), 1.0), 4)


def _fraction_to_pct(value):
	"""Progreso de LECTURA -> porcentaje 0..100.

	PunchPlay expone `progressPercent` ya en porcentaje, pero si algun
	endpoint devuelve la fraccion se detecta por el rango: nada por debajo de
	1.0 puede ser un porcentaje util aqui (los suelos de Mi Progreso empiezan
	en 5%), asi que un valor <= 1 se interpreta como fraccion."""
	try:
		v = float(value)
	except Exception:
		return 0.0
	if v <= 1.0:
		v *= 100.0
	return min(max(v, 0.0), 100.0)


# ---------------------------------------------------------------------------
# Device Flow  (PIN + QR)
# ---------------------------------------------------------------------------

_last_device_error = {'msg': ''}


def _qr_local_file(data_uri):
	"""Escribe el PNG del QR que manda PunchPlay (`verification_uri_qr`, un
	data: URI en base64) a un fichero temporal y devuelve su ruta.

	Kodi no pinta un data: URI como icono de notificacion, necesita una ruta.
	Merece la pena frente a pedirselo a qrserver.com como hacen Trakt, SIMKL y
	MDBList: el QR ya viene en la respuesta, asi que no hay peticion extra, no
	hay dependencia de un tercero, y sobre todo el user_code no sale del
	aparato camino de un servidor ajeno."""
	try:
		if not data_uri or not str(data_uri).startswith('data:image'):
			return ''
		import base64
		b64 = str(data_uri).split(',', 1)[1]
		raw = base64.b64decode(b64)
		path = control.transPath('special://temp/punchplay_qr.png')
		with open(path, 'wb') as f:
			f.write(raw)
		return path
	except Exception:
		return ''


def _qr_remote_url(url):
	"""Reserva: QR generado fuera, como en los otros tres servicios. Solo se
	usa si PunchPlay no mandase `verification_uri_qr` o no se pudiera decodificar."""
	try:
		from urllib.parse import quote_plus
	except ImportError:
		from urllib import quote_plus
	try:
		return ('https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&data='
				+ quote_plus(url))
	except Exception:
		return ''


def getDeviceCode():
	"""POST /auth/device/code. Cliente PUBLICO: solo client_id, sin secret."""
	cid = _client_id()
	if not cid:
		_last_device_error['msg'] = 'missing client_id'
		return None
	try:
		r = requests.post(_DEVICE_CODE_URL,
						  json={'client_id': cid, 'scope': SCOPES},
						  timeout=20)
		if r.status_code != 200:
			body = ''
			try:
				body = (r.text or '')[:220]
			except Exception:
				pass
			_last_device_error['msg'] = 'HTTP %s %s' % (r.status_code, body)
			_log_fail('POST', '/auth/device/code', r.status_code, body)
			return None
		data = r.json()
		_hard_log('device code obtenido (expires_in=%s)' % data.get('expires_in'), 1)
		return data
	except Exception as e:
		_last_device_error['msg'] = 'Network error: %s' % e
		_log_fail('POST', '/auth/device/code', '?', '', e)
		return None


def pollDeviceToken(device_data):
	"""Muestra PIN + QR y hace polling a /auth/device/token hasta recibir el
	token, agotarse el codigo o cancelar el usuario."""
	device_code = device_data.get('device_code')
	user_code = device_data.get('user_code')
	if not device_code or not user_code:
		return None
	cid = _client_id()
	try:
		expires_in = int(device_data.get('expires_in') or 600)
	except Exception:
		expires_in = 600
	# La respuesta de PunchPlay no trae `interval`; su guia dice "poll every
	# few seconds" y avisa de 429 si se aprieta. 5 s es el mismo ritmo que ya
	# usan Trakt y MDBList aqui.
	interval = max(int(device_data.get('interval') or 5), 1)

	verify_full = (device_data.get('verification_uri_complete')
				   or device_data.get('verification_uri') or _VERIFY_URL)
	verify_base = (device_data.get('verification_uri') or _VERIFY_URL)
	verify_short = verify_base.replace('https://', '').replace('http://', '').rstrip('/')

	qr_icon = _qr_local_file(device_data.get('verification_uri_qr'))
	if not qr_icon:
		qr_icon = _qr_remote_url(verify_full)

	try:
		from resources.lib.modules.source_utils import copy2clip
		copy2clip(verify_full)
	except Exception:
		pass

	try:
		control.notification(title='PunchPlay',
							 message='%s  |  %s' % (verify_short, user_code),
							 icon=qr_icon, time=15000)
	except Exception:
		pass

	progressDialog = control.progressDialog
	progressDialog.create('PunchPlay authorization')
	line = ('[B]Visit:[/B] %s\n[B]Enter code:[/B] %s\n'
			'OR scan the QR  ·  link copied to clipboard\n\nWaiting for authorization...'
			% (verify_short, user_code))
	try:
		progressDialog.update(100, line)
	except Exception:
		pass

	time_left = expires_in
	token_resp = None
	while True:
		if progressDialog.iscanceled():
			break
		if time_left <= 0:
			try:
				progressDialog.close()
			except Exception:
				pass
			control.notification(title='PunchPlay', message='Code expired, please try again.')
			return None
		control.sleep(1000)
		time_left -= 1
		try:
			progressDialog.update(int((expires_in - time_left) / float(expires_in) * 100))
		except Exception:
			pass
		if (expires_in - time_left) % interval != 0:
			continue
		try:
			r = requests.post(_DEVICE_TOKEN_URL, json={
				'client_id': cid,
				'device_code': device_code,
				'device_name': 'luc_kodi (Kodi)',
				'device_id': _device_id()}, timeout=20)
			if r.status_code == 200:
				token_resp = r.json()
				break
			# 400 con authorization_pending o slow_down es lo normal mientras
			# el usuario no ha aprobado: se sigue esperando. Cualquier otro
			# error si es definitivo y no tiene sentido seguir un minuto mas.
			if r.status_code == 400:
				err = ''
				try:
					err = (r.json() or {}).get('error') or ''
				except Exception:
					pass
				if err in ('authorization_pending', 'slow_down'):
					if err == 'slow_down':
						interval += 5
					continue
				_log_fail('POST', '/auth/device/token', r.status_code, err)
				break
			if r.status_code in (401, 403, 404):
				_log_fail('POST', '/auth/device/token', r.status_code, r.text)
				break
		except Exception:
			pass

	try:
		progressDialog.close()
	except Exception:
		pass
	return token_resp


def authenticate():
	"""Flujo completo: pide codigo, muestra PIN+QR, espera token, lo guarda y
	rellena el nombre de usuario con /me. Devuelve True/False."""
	if not _client_id():
		control.dialog.ok('PunchPlay',
			'Missing [B]client_id[/B].\n\nRegister a [B]public[/B] app at '
			'[B]punchplay.tv/developers[/B], paste the client ID under '
			'Settings > PunchPlay > Client ID, and try again.')
		return False
	device_data = getDeviceCode()
	if not device_data or not device_data.get('user_code'):
		reason = _last_device_error.get('msg') or 'unknown'
		control.dialog.ok('PunchPlay — could not start',
			'Could not get the authorization code.\n\n[B]Reason:[/B] %s\n\n'
			'Endpoint: %s' % (reason, _DEVICE_CODE_URL))
		return False
	token_result = pollDeviceToken(device_data)
	if not token_result:
		control.notification(title='PunchPlay', message='Authorization canceled.')
		return False
	if not _store_tokens(token_result):
		control.notification(title='PunchPlay', message='Authorization failed.')
		return False
	_clear_reauth()
	_clear_prop(_PROP_REFRESH_DEAD)

	username = token_result.get('username') or ''
	info = getUserInfo() or {}
	if not username:
		username = str(_first(info, 'username', 'displayName', 'name') or 'PunchPlay User')
	user_id = str(_first(info, 'id', 'userId', 'user_id') or '')
	try:
		setSetting('punchplay.username', username)
		if user_id:
			setSetting('punchplay.user_id', user_id)
	except Exception:
		pass

	# Comprobacion de scopes: la propia guia de PunchPlay dice que hay que
	# parar y volver a autorizar si falta alguno, en vez de descubrirlo cuando
	# ya esta la pelicula empezada y el stop no puede escribir historial.
	granted = info.get('scopes') or []
	if isinstance(granted, list) and granted:
		missing = [s for s in ('playback:write', 'history:write') if s not in granted]
		if missing:
			_hard_log('scopes concedidos SIN %s — el scrobble no podra marcar visto'
					  % ', '.join(missing), 3)
			control.dialog.ok('PunchPlay',
				'Authorized, but these scopes were not granted:\n\n[B]%s[/B]\n\n'
				'Scrobbling will not be able to write watch history. Check the '
				'app\'s allowed scopes at punchplay.tv/developers and authorize again.'
				% ', '.join(missing))

	invalidateSectionCaches(account_change=True)
	control.notification(title='PunchPlay', message='Account authorized: %s' % username)
	return True


def auth():
	"""Autorizacion por Device Flow (PIN + QR). Unico metodo."""
	authenticate()


def deauth():
	"""Revoca localmente y limpia todo. El device_id se conserva a proposito:
	identifica el aparato, no la cuenta, y regenerarlo en cada logout dejaria
	sesiones huerfanas en el historial de dispositivos del usuario."""
	try:
		setSetting('punchplay.token', '')
		setSetting('punchplay.refresh', '')
		setSetting('punchplay.expires', '')
		setSetting('punchplay.username', '')
		setSetting('punchplay.user_id', '')
		setSetting('punchplay.scopes', '')
		setSetting('punchplay.isauthed', 'false')
		setSetting('punchplay.scrobble', 'false')
		for _p in (_PROP_TOKEN, _PROP_REFRESH, _PROP_EXPIRES, _PROP_REFRESH_DEAD):
			_clear_prop(_p)
		_clear_reauth()
		invalidateSectionCaches(account_change=True)
		control.notification(title='PunchPlay', message='Deauthorized')
	except Exception:
		log_utils.error()


def getUserInfo():
	"""GET /me — perfil e id estable de la cuenta, mas los scopes concedidos."""
	return _get('/me')


def account_info_to_dialog():
	info = getUserInfo()
	if not info:
		# Distinguir los dos casos. Decir "autoriza primero" a quien YA autorizo y
		# se ha quedado sin sesion manda a buscar un fallo que no existe.
		if service_is_down():
			control.dialog.ok('PunchPlay',
				'PunchPlay is not responding right now.\n\n'
				'This is the service being unavailable, not a problem with your '
				'account. Your sign-in is untouched — try again in a while.')
		elif getPunchPlayCredentialsInfo():
			control.dialog.ok('PunchPlay',
				'Your PunchPlay session has expired and could not be renewed.\n\n'
				'Use [B]Authorize[/B] to sign in again (PIN + QR).')
		else:
			control.dialog.ok('PunchPlay', 'Not authorized yet. Use Authorize (PIN + QR).')
		return
	scopes = info.get('scopes') or []
	if isinstance(scopes, list):
		scopes_txt = ', '.join(scopes) if scopes else '?'
	else:
		scopes_txt = str(scopes)
	expires = (_prop(_PROP_EXPIRES) or getSetting('punchplay.expires') or '').strip()
	try:
		mins = max(int((float(expires) - time.time()) / 60), 0)
		expires_txt = '%d min' % mins
	except Exception:
		expires_txt = '?'
	# El contador no cuelga de un sub-dict `stats`: se buscan los nombres
	# plausibles en la raiz y tambien dentro de stats por si algun dia llega
	# anidado. Antes se leia solo de stats y salia siempre "Watched: ?".
	stats = info.get('stats') if isinstance(info.get('stats'), dict) else {}
	watched = (_first(info, 'watchedCount', 'watched_count', 'totalWatched',
					  'episodesWatched', 'watched')
			   or _first(stats, 'watched', 'watchedCount', 'total'))
	lines = (
		'[B]User:[/B] %s\n'
		'[B]User ID:[/B] %s\n'
		'[B]Watched:[/B] %s\n'
		'[B]Access token expires in:[/B] %s\n'
		'[B]Granted scopes:[/B] %s'
	) % (
		_first(info, 'username', 'displayName', 'name') or '?',
		_first(info, 'id', 'userId', 'user_id') or '?',
		watched if watched not in ('', None) else '?',
		expires_txt,
		scopes_txt,
	)
	control.dialog.ok('PunchPlay account', lines)


# ---------------------------------------------------------------------------
# Playback  —  scrobbling en vivo
# ---------------------------------------------------------------------------

def _new_session():
	"""Arranca una sesion de reproduccion nueva y devuelve su id."""
	sid = str(uuid.uuid4())
	try:
		control.homeWindow.setProperty(_PROP_SESSION, sid)
	except Exception:
		pass
	return sid


def _session():
	"""Id de la sesion en curso; si no hay ninguna, crea una.

	Que exista siempre importa: la documentacion dice que un `pause` suelto
	sin sesion activa devuelve 409, y que los eventos viejos que llegan
	despues de un stop se descartan. Sin id estable, cada evento seria una
	sesion distinta y el backend no podria ordenarlos."""
	try:
		sid = control.homeWindow.getProperty(_PROP_SESSION)
		if sid:
			return sid
	except Exception:
		pass
	return _new_session()


def _end_session():
	_clear_prop(_PROP_SESSION)
	_clear_prop(_PROP_MEDIA)


def _remember_media(title, year):
	try:
		if title:
			_set_prop(_PROP_MEDIA, '%s\n%s' % (title, year or ''))
	except Exception:
		pass


def _recall_media():
	"""(title, year) de la reproduccion en curso, o ('', '')."""
	raw = _prop(_PROP_MEDIA)
	if not raw:
		return '', ''
	parts = raw.split('\n')
	return parts[0], (parts[1] if len(parts) > 1 else '')


def _watched_threshold():
	"""Umbral de "visto", en fraccion. Por defecto 0.90, el mismo que usa el
	addon oficial de PunchPlay."""
	try:
		v = int(getSetting('punchplay.watched.threshold') or 90)
	except Exception:
		v = 90
	return round(min(max(v, 50), 100) / 100.0, 2)


def _playback_body(imdb=None, tmdb=None, tvdb=None, season=None, episode=None,
				   watched_percent=0, title=None, year=None,
				   duration=None, position=None):
	"""Cuerpo comun de los cinco eventos de playback.

	Se mandan los TRES ids a la vez cuando existen. En Trakt costo un fallo
	mudo mandar el episodio solo por tvdb: aqui `tmdb_id` es el preferido y
	los otros dos son desempate del lado del servidor."""
	media_type = 'episode' if (season and episode) else 'movie'
	# Si el llamante no trae titulo (el stop viene de Bookmarks.set_scrobble,
	# que no lo tiene), se recupera el que sembro scrobbleStart.
	if not title:
		title, _y = _recall_media()
		if not year:
			year = _y
	body = {
		'event_id': str(uuid.uuid4()),
		'event_created_at': int(time.time() * 1000),
		'media_type': media_type,
		'playback_session_id': _session(),
		'device_id': _device_id(),
		'client_version': _client_version(),
	}
	if title:
		body['title'] = str(title)
	if year:
		try:
			body['year'] = int(str(year)[:4])
		except Exception:
			pass
	if tmdb:
		try:
			body['tmdb_id'] = int(str(tmdb))
		except Exception:
			pass
	if imdb:
		body['imdb_id'] = str(imdb)
	if tvdb:
		try:
			body['tvdb_id'] = int(str(tvdb))
		except Exception:
			pass
	if media_type == 'episode':
		try:
			body['season'] = int(season)
			body['episode'] = int(episode)
		except Exception:
			pass
	# progress SIEMPRE en fraccion 0..1. Es la diferencia numero uno con los
	# otros tres servicios del addon.
	body['progress'] = _pct_to_fraction(watched_percent)
	if duration:
		try:
			body['duration_seconds'] = int(float(duration))
		except Exception:
			pass
	if position is not None:
		try:
			body['position_seconds'] = int(float(position))
		except Exception:
			pass
	elif duration:
		try:
			body['position_seconds'] = int(float(duration) * body['progress'])
		except Exception:
			pass
	return body


def _playback_post(action, body, notify_key=None):
	"""POST /playback/{action}. Devuelve True si el servidor lo acepto."""
	r = _request('POST', '/playback/%s' % action, json_data=body, timeout=20)
	if r is None:
		_hard_log('playback/%s FALLO (%s progress=%s)'
				  % (action, body.get('media_type'), body.get('progress')), 3)
		if service_is_down():
			_queue_add(action, body)
		return False
	_hard_log('playback/%s OK (%s progress=%s)'
			  % (action, body.get('media_type'), body.get('progress')), 1)
	# El aviso solo en `start`. Con latido cada 60 s, avisar en cada evento es
	# un popup por minuto encima del video durante toda la pelicula: es
	# exactamente lo que hubo que apagar en MDBList (v1.0.65) y SIMKL (v1.0.66).
	# Va DENTRO de la rama de exito, asi que el aviso sigue significando que el
	# evento se guardo de verdad.
	if notify_key == 'start' and getSetting('punchplay.scrobble.notify') == 'true':
		try:
			control.notification(title='PunchPlay', message='Scrobble started')
		except Exception:
			pass
	return True


# ---------------------------------------------------------------------------
# Cola de eventos pendientes
# ---------------------------------------------------------------------------
# Durante la caida del 19-sep se perdieron un start, seis progress y un stop de
# una reproduccion entera: el progreso no quedo en ninguna parte y el episodio
# no se pudo reanudar. Es exactamente para esto que el addon OFICIAL de
# PunchPlay para Kodi lleva su propia cola en disco.
#
# QUE SE ENCOLA Y QUE NO: solo `progress` y `stop`, que son los que llevan
# ESTADO (donde te quedaste, y si termino). `start`, `pause` y `resume`
# describen lo que estaba pasando en ese instante; reenviarlos media hora
# despues pondria "viendo ahora" algo que ya no se ve, y el propio servidor
# descarta los eventos viejos de una sesion cerrada. Mas vale perderlos.
#
# Cada evento ya viaja con `event_id` unico y `event_created_at`, asi que el
# reenvio es idempotente y el backend los ordena por su fecha ORIGINAL, no por
# la del reenvio. Por eso no se tocan al guardarlos.

_QUEUE_MAX = 200
_QUEUED_ACTIONS = ('progress', 'stop')


def _queue_path():
	# control.dataPath ya viene traducido, igual que lo usan bookmarksFile y
	# el resto de las bases del addon.
	try:
		path = control.dataPath
		if not control.existsPath(path):
			control.makeFile(path)
		return control.joinPath(path, 'punchplay_queue.json')
	except Exception:
		return ''


def _queue_read():
	try:
		import json
		path = _queue_path()
		if not path or not control.existsPath(path):
			return []
		with open(path, 'r', encoding='utf-8') as f:
			data = json.load(f)
		return data if isinstance(data, list) else []
	except Exception:
		return []


def _queue_write(rows):
	try:
		import json
		path = _queue_path()
		if not path:
			return False
		with open(path, 'w', encoding='utf-8') as f:
			json.dump(rows[-_QUEUE_MAX:], f)
		return True
	except Exception:
		log_utils.error()
		return False


def _queue_add(action, body):
	if action not in _QUEUED_ACTIONS:
		return
	rows = _queue_read()
	# Sin duplicar: el event_id es unico por evento.
	eid = body.get('event_id')
	if any(r.get('body', {}).get('event_id') == eid for r in rows):
		return
	rows.append({'action': action, 'body': body})
	if _queue_write(rows):
		_hard_log('evento %s encolado para reenviar (%d en cola)' % (action, len(rows)), 1)


def flush_queue():
	"""Reenvia lo pendiente, en orden. Se para al primer fallo.

	Pararse es deliberado: si el servicio sigue caido, insistir con los
	doscientos eventos solo alarga el arranque y llena el log."""
	rows = _queue_read()
	if not rows:
		return 0
	if service_is_down() or not getPunchPlayCredentialsInfo():
		return 0
	sent = 0
	for row in list(rows):
		action, body = row.get('action'), row.get('body')
		if action not in _QUEUED_ACTIONS or not isinstance(body, dict):
			rows.remove(row)
			continue
		if _request('POST', '/playback/%s' % action, json_data=body, timeout=20) is None:
			break
		rows.remove(row)
		sent += 1
	_queue_write(rows)
	if sent:
		_hard_log('cola: %d eventos reenviados, %d pendientes' % (sent, len(rows)), 1)
		invalidateSectionCaches()
	return sent


def scrobbleStart(imdb=None, tmdb=None, tvdb=None, season=None, episode=None,
				  watched_percent=0, title=None, year=None, duration=None, position=None):
	"""Arranque de reproduccion. Abre sesion NUEVA: sin esto, un segundo
	episodio reutilizaria el id del anterior y el backend tomaria sus eventos
	por llegadas tardias de una sesion ya cerrada y los descartaria."""
	# Una reproduccion nueva es el mejor momento para vaciar lo pendiente: hay
	# red por definicion y el usuario no esta esperando a un menu.
	try:
		flush_queue()
	except Exception:
		log_utils.error()
	_new_session()
	_remember_media(title, year)
	body = _playback_body(imdb, tmdb, tvdb, season, episode, watched_percent,
						  title, year, duration, position)
	if not body.get('title'):
		# Sin titulo el stop acabara en 400 y no habra historial. Queda dicho
		# ahora, no dentro de dos horas cuando falle el final.
		_hard_log('start SIN titulo: el stop sera rechazado por la API', 3)
	return _playback_post('start', body, notify_key='start')


def scrobbleProgress(imdb=None, tmdb=None, tvdb=None, season=None, episode=None,
					 watched_percent=0, title=None, year=None, duration=None, position=None):
	"""Latido periodico. Es `progress`, NO `pause`.

	SIMKL y MDBList mandan `pause` como keep-alive porque no tienen otra cosa.
	PunchPlay si: `progress` actualiza posicion sin tocar el estado. Mandar
	`pause` cada minuto dejaria la cuenta marcada en pausa toda la pelicula, y
	ademas la documentacion avisa de que un pause sin sesion activa da 409."""
	body = _playback_body(imdb, tmdb, tvdb, season, episode, watched_percent,
						  title, year, duration, position)
	return _playback_post('progress', body)


def scrobblePause(imdb=None, tmdb=None, tvdb=None, season=None, episode=None,
				  watched_percent=0, title=None, year=None, duration=None, position=None):
	"""Pausa REAL del usuario (onPlayBackPaused)."""
	body = _playback_body(imdb, tmdb, tvdb, season, episode, watched_percent,
						  title, year, duration, position)
	return _playback_post('pause', body)


def scrobbleResume(imdb=None, tmdb=None, tvdb=None, season=None, episode=None,
				   watched_percent=0, title=None, year=None, duration=None, position=None):
	"""Reanudacion REAL del usuario (onPlayBackResumed)."""
	body = _playback_body(imdb, tmdb, tvdb, season, episode, watched_percent,
						  title, year, duration, position)
	return _playback_post('resume', body)


def scrobbleStop(imdb=None, tmdb=None, tvdb=None, season=None, episode=None,
				 watched_percent=100, title=None, year=None, duration=None, position=None):
	"""Fin de reproduccion. Es el evento que decide si hay visto o solo
	progreso guardado; por eso se manda `watched_threshold` explicito y, por
	encima de el, tambien `watched: true`.

	Mandar los dos no es redundante: la regla del servidor es "watched=true O
	progress >= watched_threshold", y con un duration_seconds que Kodi no
	siempre da exacto, el booleano evita que un redondeo a la baja deje sin
	marcar algo que el usuario acaba de terminar."""
	body = _playback_body(imdb, tmdb, tvdb, season, episode, watched_percent,
						  title, year, duration, position)
	threshold = _watched_threshold()
	body['watched_threshold'] = threshold
	if body.get('progress', 0) >= threshold:
		body['watched'] = True
	ok = _playback_post('stop', body)
	_end_session()
	invalidateSectionCaches()
	return ok


def getNowPlaying():
	"""GET /playback/now-playing — el estado materializado de la sesion viva.
	Util para comprobar de un vistazo que el scrobble llego."""
	return _get('/playback/now-playing')


# ---------------------------------------------------------------------------
# Progreso / resume  —  "Mi Progreso"
# ---------------------------------------------------------------------------

def getInProgress():
	"""GET /playback/in-progress — items reanudables con posicion EXACTA.

	Es el endpoint correcto para el resume. /me/continue-watching resume el
	estado por SERIE (temporada y episodio actuales) y la propia documentacion
	avisa de que no es un feed de posiciones."""
	data = _get('/playback/in-progress', timeout=20)
	items = _unwrap_list(data, ('inProgress', 'in_progress'))
	if not items and data:
		_log_shape('in-progress', data)
	elif items:
		ep_sample = next((i for i in items if _media_kind(i) == 'show'), None)
		if ep_sample is not None:
			_dev_log('in-progress: forma de un episodio = %s' % _shape(ep_sample))
	return items


def _progress_item(raw, want='movie'):
	"""Normaliza un item de /playback/in-progress a la forma minima que espera
	el pipeline de movies/tvshows worker()."""
	kind = _media_kind(raw)
	season, episode = _season_of(raw), _episode_of(raw)
	if not kind:
		kind = 'show' if (season and episode) else 'movie'
	if want == 'movie' and kind != 'movie':
		return None
	if want == 'show' and kind != 'show':
		return None

	imdb, tmdb, tvdb = _ids_of(raw)
	if not (tmdb or imdb):
		return None

	pct = _fraction_to_pct(_first(raw, 'progressPercent', 'progress_percent', 'progress'))
	if pct >= PROGRESS_MAX_PCT:
		return None

	try:
		duration = float(_first(raw, 'durationSeconds', 'duration_seconds', 'runtime') or 0)
	except Exception:
		duration = 0
	# Para un episodio el titulo de la SERIE viene en `showTitle`, y el del
	# episodio aparte en `episodeTitle` (forma completa vista el 19-sep). Se
	# prefiere showTitle a `title`: hoy `title` trae la serie y funciona, pero
	# depende de que siga significando lo mismo, y aqui hay un campo que lo
	# dice sin ambiguedad.
	if want == 'show':
		title = str(_first(raw, 'showTitle', 'show_title', 'title', 'name') or '')
	else:
		title = str(_first(raw, 'title', 'name') or '')

	values = {
		'next': '',
		'imdb': imdb,
		'tmdb': tmdb,
		'tvdb': tvdb,
		'title': title,
		'originaltitle': title,
		'year': _year_of(raw),
		'progress': pct,
		'duration': duration,
		'paused_at': str(_first(raw, 'updatedAt', 'updated_at', 'pausedAt') or ''),
		'metacache': False,
	}
	if want == 'show':
		if not season or not episode:
			_hard_log('in-progress: episodio SIN temporada/episodio utilizables, '
					  'se descarta. Forma del item = %s' % _shape(raw), 3)
			return None
		values['tvshowtitle'] = title
		values['season'] = int(season)
		values['episode'] = int(episode)
	return values


def _fill_show_ids(items):
	"""Rellena imdb y tvdb de la SERIE preguntando a TMDb.

	PunchPlay identifica todo por TMDb y no publica ni imdb ni tvdb. Trakt los
	trae los tres y MDBList manda show_imdb/show_tvdb, asi que sus episodios
	llegan completos; los de PunchPlay no.

	Por que importa mas de lo que parece: `trakt_episodes_list` marca los items
	con `extended = True`, que SALTA la busqueda posterior de metadatos de
	serie, y la consulta de temporada de TMDb solo devuelve datos del episodio.
	O sea que un episodio de PunchPlay llegaba a reproducirse sin IMDB ID, y la
	mayoria de los scrapers del addon consultan por IMDB ID: salian cero
	fuentes y Kodi decia "no streaming available", mientras la misma serie
	abierta desde Trakt o desde el catalogo si encontraba de todo.

	Una peticion por serie distinta, cacheada 96 h por el propio indexador."""
	if not items:
		return items
	try:
		from resources.lib.indexers.tmdb import TVshows as tmdb_indexer
		from resources.lib.database import cache as _cache
	except Exception:
		return items
	resolved = {}
	for i in items:
		tmdb = i.get('tmdb')
		if not tmdb or (i.get('imdb') and i.get('tvdb')):
			continue
		if tmdb not in resolved:
			try:
				meta = _cache.get(tmdb_indexer().get_showSeasons_meta, 96, tmdb, True) or {}
			except Exception:
				meta = {}
			resolved[tmdb] = (str(meta.get('imdb') or ''), str(meta.get('tvdb') or ''))
		imdb, tvdb = resolved[tmdb]
		if imdb and not i.get('imdb'):
			i['imdb'] = imdb
		if tvdb and not i.get('tvdb'):
			i['tvdb'] = tvdb
	missing = [i for i in items if not i.get('imdb')]
	if missing:
		_hard_log('%d episodios siguen sin IMDB ID tras consultar TMDb; los '
				  'scrapers que buscan por imdb no los encontraran' % len(missing), 3)
	return items


def getMoviesProgress():
	raw = getInProgress()
	if not raw:
		return []
	out = []
	for r in raw:
		try:
			v = _progress_item(r, want='movie')
			if v:
				out.append(v)
		except Exception:
			log_utils.error()
	if raw and not out:
		# Separar los dos motivos. El mensaje viejo decia "0 dentro de la
		# ventana" tambien cuando lo unico que pasaba era que el item era un
		# episodio, y mandaba a mirar el filtro de porcentaje en vez del tipo.
		_hard_log('moviesProgress: %d items de /playback/in-progress, %d de tipo '
				  'pelicula, 0 utilizables (limite superior %s%%)'
				  % (len(raw), sum(1 for r in raw if _media_kind(r) == 'movie'),
					 PROGRESS_MAX_PCT))
	return sorted(out, key=lambda k: k.get('paused_at', ''), reverse=True)


def getEpisodesProgress():
	raw = getInProgress()
	if not raw:
		return []
	out = []
	for r in raw:
		try:
			v = _progress_item(r, want='show')
			if v:
				out.append(v)
		except Exception:
			log_utils.error()
	out = _fill_show_ids(out)
	if raw and not out:
		_hard_log('episodesProgress: %d items de /playback/in-progress, %d de tipo '
				  'serie, 0 utilizables (limite superior %s%%)'
				  % (len(raw), sum(1 for r in raw if _media_kind(r) == 'show'),
					 PROGRESS_MAX_PCT))
	if raw and not any(_media_kind(r) for r in raw):
		_hard_log('in-progress: ningun item declara tipo; forma = %s' % _shape(raw[0]), 3)
	return sorted(out, key=lambda k: k.get('paused_at', ''), reverse=True)


def getWatchingShows():
	"""GET /me/continue-watching — siguiente episodio por serie."""
	data = _get('/me/continue-watching', timeout=20)
	items = _unwrap_list(data, ('shows', 'continueWatching', 'continue_watching'))
	if not items and data:
		_log_shape('continue-watching', data)
		return []
	out = []
	for raw in items:
		try:
			# El siguiente episodio puede venir plano o anidado.
			nxt = raw.get('nextEpisode') or raw.get('next_episode') or raw.get('episode') or {}
			if not isinstance(nxt, dict):
				nxt = {}
			show = raw.get('show') if isinstance(raw.get('show'), dict) else raw
			imdb, tmdb, tvdb = _ids_of(show)
			if not (tmdb or imdb):
				imdb, tmdb, tvdb = _ids_of(raw)
			if not (tmdb or imdb):
				continue
			season = _season_of(nxt) or _season_of(raw)
			episode = _episode_of(nxt) or _episode_of(raw)
			if not (season and episode):
				continue
			title = str(_first(show, 'title', 'name', 'showTitle') or '')
			out.append({
				'next': '',
				'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb,
				'title': title,
				'originaltitle': title,
				'tvshowtitle': title,
				'year': _year_of(show),
				'season': int(season),
				'episode': int(episode),
				'metacache': False,
			})
		except Exception:
			log_utils.error()
	out = _fill_show_ids(out)
	if items and not out:
		_log_shape('continue-watching (parse)', items[0])
	return out


def dismissInProgress(item_id):
	"""DELETE /playback/in-progress/{id} — quitar algo de "seguir viendo"."""
	if not item_id:
		return False
	return _request('DELETE', '/playback/in-progress/%s' % item_id) is not None


# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------

def getHistory(limit=100):
	"""GET /me/history — cursor, 25 por defecto y 100 de tope por pagina."""
	return _get_all_pages('/me/history', limit=min(limit, 100), max_pages=10) or []


def markMovieAsWatched(tmdb=None, imdb=None, title=None, year=None):
	"""POST /title/movie/{id}/history. El id acepta tmdb numerico o un imdb
	prefijado (tt...); PunchPlay resuelve el que le mandes."""
	tid = tmdb or imdb
	if not tid:
		return False
	body = {}
	if title:
		body['title'] = str(title)
	if year:
		try:
			body['year'] = int(str(year)[:4])
		except Exception:
			pass
	body['watchedAt'] = _utc_now()
	return _post('/title/movie/%s/history' % tid, json_data=body) is not None


def markEpisodeAsWatched(tmdb=None, imdb=None, season=None, episode=None,
						 title=None, year=None, allow_rewatch=False):
	"""POST /title/show/{id}/season/{season}/watch — un episodio pasa por el
	endpoint de temporada, con la lista `episodes`."""
	tid = tmdb or imdb
	if not (tid and season and episode):
		return False
	body = {
		'watchedAt': _utc_now(),
		'episodes': [{'episodeNumber': int(episode)}],
	}
	if title:
		body['title'] = str(title)
	if year:
		try:
			body['year'] = int(str(year)[:4])
		except Exception:
			pass
	# allowRewatches solo cuando el usuario lo pide expresamente: sin esa
	# cautela, un re-marcado accidental duplica entradas de historial.
	if allow_rewatch:
		body['allowRewatches'] = True
	return _post('/title/show/%s/season/%s/watch' % (tid, int(season)),
				 json_data=body) is not None


def markMovieAsNotWatched(tmdb=None, imdb=None):
	tid = tmdb or imdb
	if not tid:
		return False
	return _request('DELETE', '/title/movie/%s/history' % tid) is not None


def markEpisodeAsNotWatched(tmdb=None, imdb=None, season=None, episode=None):
	tid = tmdb or imdb
	if not (tid and season):
		return False
	body = {'episodes': [{'episodeNumber': int(episode)}]} if episode else None
	return _request('DELETE', '/title/show/%s/season/%s/watch' % (tid, int(season)),
					json_data=body) is not None


def _utc_now():
	"""Marca de tiempo ISO en UTC. PunchPlay rechaza fechas futuras, asi que
	se usa la hora del sistema tal cual, sin margen."""
	return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())


# ---------------------------------------------------------------------------
# Ratings, favoritos y estado
# ---------------------------------------------------------------------------

def interact(media_type, tid, rating=None, favourite=None, status=None,
			 season=None, episode=None):
	"""PATCH /title/{type}/{id}/interact — puntuacion, favorito y estado en
	UNA sola peticion. type es 'movie' o 'show'."""
	if not tid:
		return False
	body = {}
	if rating is not None:
		body['rating'] = int(rating)
	if favourite is not None:
		body['isFavourite'] = bool(favourite)
	if status:
		body['showStatus'] = str(status).upper()
	if not body:
		return False
	params = {}
	if season:
		params['season'] = int(season)
	if episode:
		params['episode'] = int(episode)
	kind = 'show' if media_type in ('show', 'tvshow', 'tv', 'episode') else 'movie'
	return _request('PATCH', '/title/%s/%s/interact' % (kind, tid),
					json_data=body, params=params or None) is not None


def getRatings():
	"""GET /me/ratings — paginacion por NUMERO DE PAGINA, no por cursor."""
	return _get_all_pages_numbered('/me/ratings') or []


def getFavourites():
	return _get_all_pages_numbered('/me/favourites') or []


# ---------------------------------------------------------------------------
# v1.0.94 — Coleccion, favoritos y puntuaciones como secciones del menu
# ---------------------------------------------------------------------------
# Lo mismo que se ve en punchplay.tv/profile (Collection, Favourites, Ratings)
# por la API documentada (platform v1, beta.5):
#   /me/collection   cursor (`nextCursor`, `limit` hasta 200). Un titulo sale
#                    una vez POR FORMATO y, en series, por temporada: "Silo 4K
#                    BLU-RAY +2" son varias filas del mismo tmdbId.
#   /me/favourites   pagina numerada (`page`, `pageSize` hasta 100, hasMore)
#   /me/ratings      igual, con `scope`: se piden solo las de TITULO; las de
#                    temporada o episodio no son una ficha que abrir.
# Las tres traen `tmdbId` siempre y `kind` movie/show; el anime viene como
# kind show o movie con su categoria aparte, asi que cae en su menu natural.
# NO existe endpoint de listas que te gustan o que sigues: la API solo da las
# listas propias (/me/lists) y las destacadas de la comunidad.

def _library_to_items(rows, media_type, tag):
	"""Filas de biblioteca -> forma minima del worker, sin repetir titulo."""
	want = 'show' if media_type in ('show', 'tvshow', 'tv') else 'movie'
	out, seen = [], set()
	for r in (rows or []):
		try:
			if not isinstance(r, dict):
				continue
			kind = _media_kind(r)
			if kind and kind != want:
				continue
			imdb, tmdb, tvdb = _ids_of(r)
			if str(r.get('mediaSource') or '').lower() == 'tvdb' and r.get('sourceId'):
				tvdb = str(r.get('sourceId'))
			key = tmdb or imdb
			if not key or key in seen:
				continue
			seen.add(key)
			name = str(_first(r, 'title', 'name') or '')
			values = {
				'next': '',
				'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb,
				'title': name,
				'originaltitle': name,
				'year': _year_of(r),
				'metacache': False,
			}
			if want == 'show':
				values['tvshowtitle'] = name
			out.append(values)
		except Exception:
			log_utils.error()
	_hard_log('%s(%s): %d filas, %d titulos' % (tag, want, len(rows or []), len(out)))
	if rows and not out:
		_log_shape(tag, rows[0], 'want=%s' % want)
	return out


def getCollectionFor(media_type):
	return _library_to_items(_get_all_pages('/me/collection', limit=200) or [],
							 media_type, 'collection')


def getFavouritesFor(media_type):
	rows = _get_all_pages_numbered('/me/favourites', params={'pageSize': 100}) or []
	return _library_to_items(rows, media_type, 'favourites')


def getRatingsFor(media_type):
	rows = _get_all_pages_numbered('/me/ratings',
								   params={'pageSize': 100, 'scope': 'title'}) or []
	return _library_to_items(rows, media_type, 'ratings')


# ---------------------------------------------------------------------------
# Listas
# ---------------------------------------------------------------------------

def _list_summary(raw):
	"""Normaliza el resumen de una lista. `externalSource` no nulo significa
	gestionada fuera y de SOLO LECTURA; las dinamicas tampoco admiten cambios
	de items."""
	# RESUELTO el 19-sep. El volcado de forma que pedia la 1.0.88 contesto:
	#   dict{description, externalSource, id, isCollaborative, isDynamicList,
	#        isPublic, isWatchlist, itemCount, name, ownerUsername,
	#        previewPosters}
	# Hay UN solo identificador, `id`, y era el correcto desde el principio.
	# El 404 no venia del id sino de la RUTA: ver getListItems().
	lid = raw.get('id')
	if lid in (None, '', 0, '0'):
		return None
	external = _first(raw, 'externalSource', 'external_source')
	return {
		'id': str(lid),
		'name': str(_first(raw, 'name', 'title') or '?'),
		'description': str(_first(raw, 'description') or ''),
		'items': _first(raw, 'itemCount', 'itemsCount', 'item_count', 'items', 'count') or 0,
		'public': bool(_first(raw, 'isPublic', 'is_public', 'public')),
		'dynamic': bool(_first(raw, 'isDynamicList', 'isDynamic', 'dynamic')),
		'count': _first(raw, 'itemCount', 'itemsCount') or 0,
		'external': str(external or ''),
		'watchlist': _is_watchlist(raw),
		'owner': str(_first(raw, 'ownerUsername', 'ownerName', 'owner') or ''),
		'kind': _media_kind(raw),
	}


def _is_watchlist(raw):
	"""La watchlist es una lista normal salvo en que no se puede renombrar ni
	borrar. La documentacion no fija como viene marcada, asi que se comprueban
	las tres formas plausibles y, como ultimo recurso, el nombre."""
	for k in ('isWatchlist', 'is_watchlist', 'watchlist'):
		if raw.get(k):
			return True
	if str(_first(raw, 'kind', 'type', 'listType') or '').lower() == 'watchlist':
		return True
	return str(_first(raw, 'name', 'title') or '').strip().lower() == 'watchlist'


def getUserLists():
	"""GET /me/lists — resumenes, por cursor (50 por defecto, 100 de tope)."""
	raw = _get_all_pages('/me/lists', limit=100, max_pages=10)
	if raw is None:
		return None
	out = []
	for r in raw:
		try:
			v = _list_summary(r)
			if v:
				out.append(v)
		except Exception:
			log_utils.error()
	if raw and not out:
		_log_shape('userLists', raw[0])
	elif raw:
		# Volcado de NOMBRES DE CLAVE del primer resumen (nunca contenido: ni
		# titulos ni ids reales). Cumplio su funcion el 19-sep —fue lo que
		# revelo que el resumen trae un solo identificador—, asi que baja a
		# modo desarrollador en vez de salir en cada visita al menu. El aviso
		# de 0 items parseados SI sigue siendo incondicional: ese señala un
		# fallo, no una duda.
		_dev_log('userLists: forma del resumen = %s' % _shape(raw[0]))
	_hard_log('userLists: %d listas' % len(out), 1)
	return out


def getWatchlistId():
	"""Id de la watchlist del usuario, o None."""
	lists = getUserLists() or []
	for l in lists:
		if l.get('watchlist'):
			return l['id']
	return None


def _list_matches_media_type(lst, media_type):
	"""PERMISIVO a proposito: una lista sin tipo declarado sale en los DOS
	menus en vez de esconderse de los dos. Copiado de MDBList, donde el
	criterio estricto hacia desaparecer listas perfectamente validas."""
	kind = lst.get('kind') or ''
	if not kind:
		return True
	want = 'show' if media_type in ('show', 'tvshow', 'tv') else 'movie'
	return kind == want


def getUserListsFor(media_type):
	lists = getUserLists()
	if lists is None:
		return None
	return [l for l in lists if _list_matches_media_type(l, media_type)]


def _list_items_paginated(list_id, max_pages=20):
	"""GET /lists/{id}/items — SOLO para listas dinamicas, y pagina por OFFSET.

	Ojo: esta es la unica lectura de PunchPlay que no usa ni cursor ni numero
	de pagina. Manda `offset` y `limit` y responde `nextOffset`. Son ya TRES
	paginaciones distintas en la misma API."""
	items, offset, pages = [], 0, 0
	while pages < max_pages:
		pages += 1
		data = _get('/lists/%s/items' % list_id,
					params={'offset': offset, 'limit': 100}, timeout=20)
		if data is None:
			break
		batch = _unwrap_list(data)
		if not batch:
			break
		items.extend(batch)
		nxt = data.get('nextOffset') if isinstance(data, dict) else None
		if nxt in (None, offset):
			break
		offset = nxt
	return items


def getListItems(list_id, media_type='movie', strict=False):
	"""Items de una lista. Una lista puede llevar peliculas y series mezcladas,
	asi que se reparte por `kind` al leer.

	LA RUTA — esto costo dos builds y lo cerro el codigo de Red Light:
	en una lista NORMAL los items vienen DENTRO de `GET /lists/{id}`, en su
	campo `items`. El endpoint `/lists/{id}/items` existe solo para las listas
	DINAMICAS; pedirselo a una lista normal devuelve 404 not_found, que es
	exactamente lo que salia en el log con la watchlist (id 1360). El id nunca
	estuvo mal."""
	if not list_id:
		return []
	detail = _get('/lists/%s' % list_id, timeout=20)
	raw = []
	if isinstance(detail, dict):
		raw = detail.get('items') if isinstance(detail.get('items'), list) else []
		is_dynamic = bool(detail.get('isDynamicList'))
		try:
			count = int(detail.get('itemCount') or 0)
		except Exception:
			count = 0
		# Una lista dinamica puede traer el detalle recortado: si dice tener
		# mas de los que manda, se completa por el endpoint paginado.
		if is_dynamic and (not raw or count > len(raw)):
			raw = _list_items_paginated(list_id) or raw
	if not raw:
		# Ultimo recurso para formas que no conozcamos.
		raw = _list_items_paginated(list_id)
	if not raw:
		return []
	want = 'show' if media_type in ('show', 'tvshow', 'tv') else 'movie'
	out = []
	for r in raw:
		try:
			# El item puede traer el titulo anidado bajo `title`/`media`.
			node = r
			for k in ('title', 'media', 'item'):
				if isinstance(r.get(k), dict):
					node = r[k]
					break
			kind = _media_kind(node) or _media_kind(r)
			if kind and kind != want:
				continue
			# strict: un item SIN tipo declarado tampoco cuenta.
			#
			# Para las listas propias del usuario conviene ser permisivo: mas
			# vale enseñar una lista de mas que esconderle la suya. Para
			# decidir en que MENU va una lista de la comunidad es al reves —
			# ser permisivo metio "Urban TV Shows" y "MDB_Plan_To_Watch_TV_
			# Shows" dentro de Movies, porque parte de sus entradas no traian
			# `type` y colaban como peliculas.
			if strict and not kind:
				continue
			imdb, tmdb, tvdb = _ids_of(node)
			if not (tmdb or imdb):
				imdb, tmdb, tvdb = _ids_of(r)
			if not (tmdb or imdb):
				continue
			name = str(_first(node, 'title', 'name') or _first(r, 'title', 'name') or '')
			values = {
				'next': '',
				'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb,
				'title': name,
				'originaltitle': name,
				'year': _year_of(node) or _year_of(r),
				'metacache': False,
			}
			if want == 'show':
				values['tvshowtitle'] = name
			out.append(values)
		except Exception:
			log_utils.error()
	if raw and not out:
		_log_shape('listItems(%s)' % list_id, raw[0], 'want=%s' % want)
	return out


def addToList(list_id, media_type, tmdb, title=None):
	"""POST /lists/{id}/items. Las listas externas y dinamicas rechazan
	cambios manuales, asi que el llamante no debe ofrecerlas."""
	if not (list_id and tmdb):
		return False
	kind = 'show' if media_type in ('show', 'tvshow', 'tv') else 'movie'
	body = {'kind': kind, 'sourceId': int(tmdb)}
	if title:
		body['title'] = str(title)
	ok = _post('/lists/%s/items' % list_id, json_data=body) is not None
	if ok:
		invalidateSectionCaches()
	return ok


def removeFromList(list_id, item_id):
	if not (list_id and item_id):
		return False
	ok = _request('DELETE', '/lists/%s/items/%s' % (list_id, item_id)) is not None
	if ok:
		invalidateSectionCaches()
	return ok


def createList(name, description='', public=False):
	if not name:
		return None
	return _post('/lists', json_data={'name': str(name)[:100],
									  'description': str(description)[:500],
									  'isPublic': bool(public)})


# ---------------------------------------------------------------------------
# Catalogo publico  (sin auth)
# ---------------------------------------------------------------------------

def punchplay_list(url):
	"""Lee un endpoint del catalogo PUBLICO y lo normaliza a la forma minima
	que espera el pipeline de movies/tvshows worker().

	`url` llega completo desde movies.py/tvshows.py, igual que con SIMKL, para
	que la cache lo use de clave y el TTL lo decida el llamante."""
	if not url:
		return []
	try:
		path = url.split(PUBLIC_API, 1)[1] if PUBLIC_API in url else url
		params = None
		if '?' in path:
			path, qs = path.split('?', 1)
			params = {}
			for pair in qs.split('&'):
				if '=' in pair:
					k, v = pair.split('=', 1)
					params[k] = v
		data = _public_get(path, params=params)
	except Exception:
		log_utils.error()
		return []
	items = _unwrap_list(data, ('titles', 'catalog'))
	if not items:
		if data:
			_log_shape('punchplay_list', data, url)
		return []
	out = []
	for item in items:
		try:
			imdb, tmdb, tvdb = _ids_of(item)
			if not tmdb:
				# Sin tmdb el pipeline no puede resolver metadatos.
				continue
			name = str(_first(item, 'title', 'name') or '')
			values = {
				'next': '',
				'tmdb': tmdb, 'imdb': imdb, 'tvdb': tvdb,
				'title': name,
				'originaltitle': name,
				'year': _year_of(item),
				'metacache': False,
			}
			if _media_kind(item) == 'show':
				values['tvshowtitle'] = name
			out.append(values)
		except Exception:
			log_utils.error()
	if items and not out:
		_log_shape('punchplay_list (parse)', items[0], url)
	return out


def getCalendarEpisodes(months_back=0, months_ahead=1):
	"""GET /calendar?month=YYYY-MM — emisiones de las series que sigue.

	La respuesta NO es una lista plana: es `days[]`, y cada dia lleva `items[]`.
	Los episodios son los de `kind == 'episode'`, y la temporada/episodio van
	anidados en `nextEpisode{season, episode, airDate}`. Se descartan las
	temporada 0 (especiales) como hace el calendario de MDBList.

	Se piden varios meses porque el endpoint sirve UNO por llamada."""
	out, seen = [], set()
	now = time.localtime()
	y, m = now.tm_year, now.tm_mon
	m -= months_back
	while m <= 0:
		m += 12
		y -= 1
	for _ in range(months_back + months_ahead + 1):
		data = _get('/calendar', params={'month': '%04d-%02d' % (y, m)}, timeout=20)
		days = data.get('days') if isinstance(data, dict) else None
		if not isinstance(days, list):
			if data:
				_log_shape('calendar %04d-%02d' % (y, m), data)
		else:
			for day in days:
				if not isinstance(day, dict):
					continue
				day_date = day.get('date') or ''
				for item in (day.get('items') or []):
					try:
						if not isinstance(item, dict):
							continue
						if str(item.get('kind') or '').lower() != 'episode':
							continue
						nxt = item.get('nextEpisode')
						if not isinstance(nxt, dict):
							continue
						season = nxt.get('season')
						episode = nxt.get('episode')
						if season is None or episode is None or int(season) < 1:
							continue
						imdb, tmdb, tvdb = _ids_of(item)
						if not (tmdb or imdb):
							continue
						key = (tmdb or imdb, int(season), int(episode))
						if key in seen:
							continue
						seen.add(key)
						title = str(item.get('title') or '')
						out.append({
							'next': '',
							'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb,
							'title': title,
							'originaltitle': title,
							'tvshowtitle': title,
							'year': _year_of(item),
							'season': int(season),
							'episode': int(episode),
							'premiered': str(nxt.get('airDate') or day_date),
							'metacache': False,
						})
					except Exception:
						continue
		m += 1
		if m > 12:
			m, y = 1, y + 1
	out = _fill_show_ids(out)
	_hard_log('calendar: %d episodios en %d meses' % (len(out), months_back + months_ahead + 1), 1)
	return sorted(out, key=lambda k: k.get('premiered', ''))


def getCommunityLists():
	"""Listas publicas de la comunidad, SIN autenticacion.

	Salen de GET /api/public/v1/community/overview, campo `topLists`, cuyos
	items son {listId, listName, ownerDisplayName, itemsAddedThisMonth,
	totalItems}. Es el unico endpoint publicado que devuelve identificadores de
	listas ajenas, y con el `listId` ya se pueden leer sus contenidos por
	/lists/{id} como cualquier otra.

	LIMITE que conviene tener presente: esto NO es el catalogo entero de
	punchplay.tv/discover/lists. Aquella pagina ordena por mas gustadas, mas
	nuevas, mas comentadas y mas grandes, y nada de eso existe en la API
	publica — su web lo resuelve por dentro. Aqui salen las destacadas del mes
	y solo esas. Para abrir cualquier otra esta la entrada de ID/URL."""
	data = _public_get('/community/overview', timeout=20)
	if not isinstance(data, dict):
		return []
	node = data.get('topLists')
	items = node.get('items') if isinstance(node, dict) else None
	if not isinstance(items, list):
		if data:
			_log_shape('communityLists', data)
		return []
	out = []
	for raw in items:
		try:
			lid = raw.get('listId')
			if lid in (None, '', 0, '0'):
				continue
			out.append({
				'id': str(lid),
				'name': str(raw.get('listName') or '?'),
				'description': '',
				'items': raw.get('totalItems') or 0,
				'public': True,
				'dynamic': False,
				'external': '',
				'watchlist': False,
				'owner': str(raw.get('ownerDisplayName') or ''),
				'kind': '',
			})
		except Exception:
			log_utils.error()
	_hard_log('communityLists: %d listas destacadas' % len(out), 1)
	return out


def getListKindCounts(list_id):
	"""Cuenta los items de una lista por tipo: (peliculas, series, sin tipo).

	Una sola lectura de la lista para los dos menus, en vez de una por menu."""
	counts = {'movie': 0, 'show': 0, '': 0}
	detail = _get('/lists/%s' % list_id, timeout=20)
	raw = []
	if isinstance(detail, dict):
		raw = detail.get('items') if isinstance(detail.get('items'), list) else []
		if detail.get('isDynamicList') and not raw:
			raw = _list_items_paginated(list_id)
	for r in (raw or []):
		node = r
		for k in ('title', 'media', 'item'):
			if isinstance(r.get(k), dict):
				node = r[k]
				break
		counts[_media_kind(node) or _media_kind(r) or ''] += 1
	return counts


def getCommunityListsFor(media_type):
	"""Listas de la comunidad que pertenecen a ESTE menu.

	POR MAYORIA, no por "tiene al menos uno". Exigir tipo explicito no bastó:
	el 19-sep "Urban TV Shows" (228 items) y "MDB_Plan_To_Watch_TV_Shows"
	seguian saliendo en Movies, asi que algunas de sus entradas SI se declaran
	pelicula — son listas importadas de MDBList y vienen mezcladas.

	Y es que "contiene alguna pelicula" nunca fue el criterio correcto: una
	lista de series con tres peliculas sueltas pertenece a TV Shows, y
	enseñarla en Movies con tres titulos es ruido. Se coloca donde cae la
	mayoria de sus items tipados, y solo sale en los dos menus si esta
	realmente repartida (empate). El recuento por tipo queda en el log, que es
	lo que faltaba para dejar de suponer."""
	want = 'show' if media_type in ('show', 'tvshow', 'tv') else 'movie'
	other = 'movie' if want == 'show' else 'show'
	out = []
	for lst in (getCommunityLists() or []):
		try:
			counts = getListKindCounts(lst['id'])
			_hard_log('communityList %s "%s": %d peliculas, %d series, %d sin tipo'
					  % (lst['id'], lst.get('name', '?'), counts['movie'],
						 counts['show'], counts['']), 1)
			if not counts[want] or counts[want] < counts[other]:
				continue
			entry = dict(lst)
			entry['items'] = counts[want]
			entry['kind'] = want
			out.append(entry)
		except Exception:
			log_utils.error()
	_hard_log('communityLists(%s): %d listas' % (want, len(out)), 1)
	return out


def listIdFromUrl(text):
	"""Saca el id de lista de una URL de punchplay.tv o de un numero suelto."""
	import re
	t = (text or '').strip()
	if not t:
		return ''
	m = re.search(r'punchplay\.tv/lists/(\d+)', t, re.I)
	if m:
		return m.group(1)
	t = t.split('?')[0].split('#')[0].rstrip('/')
	return t if t.isdigit() else ''


def publicProfile(username, history_limit=8):
	"""GET /users/{username} — perfil publico, sin auth. Permite mirar la
	actividad de otro usuario sin pedirle nada."""
	if not username:
		return None
	return _public_get('/users/%s' % username,
					   params={'historyLimit': min(max(int(history_limit), 1), 20)})


# ---------------------------------------------------------------------------
# Cachés
# ---------------------------------------------------------------------------

_CACHE_VERSION_SETTING = 'punchplay._cache_bust_version'


def bust_caches_on_version_change():
	"""Invalida las cachés de PunchPlay cuando cambia la version del addon.

	Motivo concreto: los items de Continue Watching se cachean una hora. Al
	instalar la 1.0.92, que arreglo la lectura de temporada y episodio, el menu
	siguio pintando durante esa hora los items VIEJOS, construidos con ceros
	por la version anterior — y el aviso de "episodios sin enriquecer" seguia
	saliendo aunque el arreglo fuese correcto. Un arreglo que no se ve hasta
	dentro de una hora parece un arreglo que no funciona. SIMKL ya usa este
	mismo patron por la misma razon."""
	try:
		current = _client_version()
		if (getSetting(_CACHE_VERSION_SETTING) or '') == current:
			return
		invalidateSectionCaches(account_change=True)
		setSetting(_CACHE_VERSION_SETTING, current)
		_hard_log('caches invalidadas por cambio de version (%s)' % current, 1)
	except Exception:
		log_utils.error()


def invalidateSectionCaches(account_change=False):
	"""Invalida las cachés de las secciones de PunchPlay.

	Se apunta SOLO a funciones que existen de verdad. En MDBList esto apuntaba
	a dos atributos que no habian existido nunca y el AttributeError se lo
	tragaba un except: no invalidaba nada y nadie se entero durante versiones."""
	try:
		from resources.lib.database import cache
		# La clave de cache es NOMBRE DE FUNCION + md5(argumentos), asi que
		# cache.remove(fn) sin argumentos solo borra la entrada sin argumentos.
		# Las listas se cachean por tipo — cache.get(getCommunityListsFor, 6,
		# 'movie') —, y al no pasar el 'movie' aqui no se borraban nunca: el
		# 19-sep la clasificacion vieja sobrevivio a la actualizacion y en
		# Movies seguian saliendo las listas de series seis horas despues, con
		# el arreglo ya instalado y sin una sola peticion en el log.
		targets = [
			(getMoviesProgress, ()),
			(getEpisodesProgress, ()),
			(getWatchingShows, ()),
			(getCalendarEpisodes, ()),
			(getCommunityListsFor, ('movie',)),
			(getCommunityListsFor, ('show',)),
			(getUserListsFor, ('movie',)),
			(getUserListsFor, ('show',)),
			(getWatchlistId, ()),
			(getCollectionFor, ('movie',)),
			(getCollectionFor, ('show',)),
			(getFavouritesFor, ('movie',)),
			(getFavouritesFor, ('show',)),
			(getRatingsFor, ('movie',)),
			(getRatingsFor, ('show',)),
		]
		if account_change:
			targets += [(getUserLists, ()), (getHistory, ())]
		for fn, args in targets:
			try:
				cache.remove(fn, *args)
			except Exception:
				pass
	except Exception:
		pass


def force_punchplaySync(silent_confirm=False):
	"""Refresco manual desde Ajustes."""
	try:
		if not getPunchPlayCredentialsInfo():
			control.notification(title='PunchPlay', message='Not authorized.')
			return
		invalidateSectionCaches(account_change=True)
		ensure_token()
		pending = flush_queue()
		info = getUserInfo()
		if info is None:
			if service_is_down():
				control.notification(title='PunchPlay',
									 message='PunchPlay is unavailable right now')
			else:
				control.notification(title='PunchPlay', message='Sync failed — see kodi.log')
			return
		if not silent_confirm:
			msg = 'Sync complete'
			if pending:
				msg = 'Sync complete — %d queued events sent' % pending
			control.notification(title='PunchPlay', message=msg)
	except Exception:
		log_utils.error()
