# -*- coding: utf-8 -*-
"""
    luc_kodi Add-on
    MDBList integration module — FULL in-plugin client.

    Esta versión absorbe todo lo que antes hacía el servicio externo
    `service.luc_kodi.mdblist`: scrobbling (start/pause/stop/clear), resume
    cross-device (/sync/playback), historial de vistos (/sync/watched),
    "siguiente no visto" (/upnext), watchlist y listas públicas — igual que
    Trakt y SIMKL viven dentro del plugin. Ya NO se lee ninguna BD del
    servicio externo.

    Autenticación (DOS modos, ambos soportados):
      1) OAuth 2.0 Device Flow (RECOMENDADO, sin teclado, con PIN + QR) —
         igual que Trakt/SIMKL. POST /oauth/device-authorization/ devuelve
         user_code + device_code; el usuario abre mdblist.com/oauth/device,
         mete el PIN (o escanea el QR) y aprueba. Se hace polling a
         POST /oauth/token/ hasta recibir access_token. Las llamadas van con
         cabecera Authorization: Bearer <token>. La app aparece en
         "Authorized Apps" del perfil con su nombre e icono (definidos al
         registrar el client_id en mdblist.com).
      2) API key manual (?apikey=KEY) — alternativa/legacy.

    IMPORTANTE: el Device Flow necesita un client_id propio registrado en
    mdblist.com (Preferences -> API Access). Ponlo en el ajuste
    mdblist.client_id. Sin client_id, el plugin cae a modo API key.

    Endpoints reales (api.mdblist.com, OpenAPI 1.0.0):
      POST /oauth/device-authorization/   → user_code, device_code, QR
      POST /oauth/token/                  → access_token, refresh_token
      POST /scrobble/start|pause|stop|clear
      GET  /sync/playback          → sesiones en pausa (resume)
      GET  /sync/watched / POST    → historial de vistos
      GET  /upnext                 → series en curso con próximo episodio
      GET  /user                   → perfil + límites (validación de key)
      GET  /watchlist/items ; POST /watchlist/items/add | /remove
      GET  /lists/top ; GET /lists/search ; GET /lists/{id}/items
      GET  /lists/liked            → listas ajenas marcadas con "like" (NO documentado)
      GET  /sync/last_activities   → marcas de tiempo por seccion (ahorra sync)
      GET  /sync/ratings / POST / POST /sync/ratings/remove
      GET  /sync/collection / POST / POST /sync/collection/remove
      GET  /sync/dropped / POST / POST /sync/dropped/remove
      POST /sync/watched/remove    → desmarcar visto
      GET  /external/lists/user ; /external/lists/{id}[/items]
      GET  /search/{media_type} ; GET /genres ; GET /lists/{id}/changes

    NOTA sobre "Liked Lists" (corregida en v1.0.69): SI existe endpoint,
    GET /lists/liked. Lo que no existe es su documentacion — no aparece ni en
    el OpenAPI 3.0.3 ni en el apiary, exactamente igual que /calendar/events,
    que tambien se dio por inexistente por el mismo motivo y resulto ser real.
    LECCION: en esta API "no esta en el spec" NO significa "no existe"; el spec
    esta incompleto y hay que comprobarlo contra el servidor. Hasta v1.0.68
    este modulo afirmaba lo contrario en dos sitios y costo la funcionalidad.
"""

from resources.lib.modules import app_keys
import time
import requests

from resources.lib.modules import control
from resources.lib.modules import log_utils

BASE_URL = 'https://api.mdblist.com'

# --- OAuth 2.0 Device Flow (PIN + QR) -------------------------------------
# Endpoints verificados contra una implementación funcional.
_OAUTH_DEVICE_URL = 'https://api.mdblist.com/oauth/device-authorization/'
_OAUTH_TOKEN_URL = 'https://api.mdblist.com/oauth/token/'
_OAUTH_GRANT_DEVICE = 'urn:ietf:params:oauth:grant-type:device_code'
# Página donde el usuario mete el PIN (o aterriza el QR).
_OAUTH_VERIFY_URL = 'https://mdblist.com/oauth/device/'

# NO incluir aquí ninguna API key personal: si se rellena, TODAS las llamadas
# /user de un usuario recién instalado (o con el OAuth aún no activo) caerían en
# esta cuenta y mostrarían/guardarían el username del dueño de la key. Cada
# usuario autoriza su propia cuenta vía Device Flow (PIN+QR) o pone su API key.
DEFAULT_APIKEY = ''

# client_id propio de la app luc_kodi registrada en mdblist.com. Viene de
# fábrica para que el Device Flow (PIN+QR) funcione recién instalado y la
# cuenta del usuario aparezca en "Authorized Apps" con el nombre/icono de
# luc_kodi. El usuario puede sobreescribirlo en Ajustes si registra su propia app.
DEFAULT_CLIENT_ID = app_keys.get('mdblist')

# Identificador de la app que MDBList registra en cada scrobble.
APP_NAME = 'luc_kodi'

getSetting = control.setting
setSetting = control.setSetting

# Throttle local para no chocar con el lock de 20s del servidor en scrobbles.
_SCROBBLE_THROTTLE_SECONDS = 5
_last_scrobble_at = {'ts': 0.0}


# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------

def getOAuthToken():
	"""access_token guardado por el Device Flow (vacío si no autorizado)."""
	return (getSetting('mdblist.token') or '').strip()


def getClientID():
	"""client_id de la app en mdblist.com (Device Flow). Usa el del usuario si
    lo ha puesto, si no el de fábrica de luc_kodi."""
	cid = (getSetting('mdblist.client_id') or '').strip()
	if not cid:
		cid = DEFAULT_CLIENT_ID
	return cid


def oauthActive():
	"""True si hay un access_token utilizable (modo OAuth)."""
	tok = getOAuthToken()
	return bool(tok and tok not in ('0', 'empty_setting'))


def getMDBListCredentials():
	"""Devuelve (cred, base_url) donde cred es el access_token OAuth si existe,
    si no la API key del usuario, si no la del plugin. La forma de enviarlo
    (Bearer vs ?apikey=) la decide _auth_headers_params()."""
	url = (getSetting('mdblist.url') or '').strip().rstrip('/')
	if not url:
		url = BASE_URL
	if oauthActive():
		return getOAuthToken(), url
	apikey = (getSetting('mdblist.apikey') or '').strip()
	if not apikey:
		apikey = DEFAULT_APIKEY
	if apikey:
		return apikey, url
	return None, None


def _auth_headers_params():
	"""Devuelve (headers, params) con la credencial colocada según el modo:
    OAuth -> Authorization: Bearer; API key -> ?apikey=."""
	if oauthActive():
		return {'Authorization': 'Bearer %s' % getOAuthToken()}, {}
	apikey, _ = getMDBListCredentials()
	if apikey:
		return {}, {'apikey': apikey}
	return {}, {}


def usingDefaultKey():
	"""True si el usuario aún no ha puesto su propia key NI autorizado OAuth."""
	if oauthActive():
		return False
	return not (getSetting('mdblist.apikey') or '').strip()


def getMDBListCredentialsInfo():
	"""True si hay una credencial utilizable (token OAuth o API key)."""
	cred, _ = getMDBListCredentials()
	return bool(cred)


def getMDBListScrobbleInfo():
	"""True si el usuario ha activado el scrobbling Y hay credencial. Es el
    ÚNICO interruptor visible que controla el scrobbling. Pensado para player.py.
    Requiere además estar autorizado (token OAuth o API key propia): con la key
    por defecto del plugin NO se scrobblea, para no escribir en la cuenta dueña."""
	if getSetting('mdblist.scrobble') != 'true':
		return False
	if usingDefaultKey():
		# Sólo key por defecto del plugin y sin OAuth → no escribir.
		return False
	return getMDBListCredentialsInfo()


# ---------------------------------------------------------------------------
# Request de bajo nivel
# ---------------------------------------------------------------------------

def _shape(data, depth=0):
	"""Descripcion COMPACTA de la forma de una respuesta, para el log.

	Existe porque el 17-ago-2026 el log de un usuario demostro que /upnext y
	/imdb/movie devolvian 200 y JSON valido (cero avisos de fallo) y aun asi
	los calendarios salian vacios: el problema no era la red ni el token sino
	que la ENVOLTURA no era la que el parser esperaba. Sin esto no hay forma
	de saber si la respuesta es una lista, un dict con otra clave, o entradas
	con otros nombres de campo. No vuelca contenido: solo tipos, tamanos y
	nombres de clave, asi que no filtra titulos ni ids a un log compartido."""
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
			s = 'dict{%s}' % ', '.join(keys[:14])
			if len(keys) > 14:
				s += ', +%d' % (len(keys) - 14)
			if depth < 2:
				for k in ('items', 'results', 'data', 'shows', 'movies', 'episodes'):
					if isinstance(data.get(k), list):
						s += ' | %s=%s' % (k, _shape(data[k], depth + 1))
						break
			return s
		return type(data).__name__
	except Exception:
		return '?'


# El diagnostico NO pasa por log_utils.log(): esa funcion aborta en su primera
# linea si `debug.enabled` no esta a true, y ademas con `debug.location=1`
# escribe en luc_kodi.log en vez de en kodi.log. Resultado practico: el
# 17-ago-2026 se entrego la 1.0.60 con instrumentacion y el log del usuario
# volvio SIN una sola linea de MDBList — ni los avisos de fallo de peticion,
# que llevaban ahi desde siempre. Peor: esa ausencia se leyo como "las
# peticiones van bien", cuando en realidad no probaba absolutamente nada.
# Se usa xbmc.log directo e incondicional, el mismo patron que ya emplea
# gemini_api.py con su tag [luc_kodi-gemini] y por la misma razon.
LOG_TAG = '[luc_kodi-mdblist]'


def _hard_log(msg, level=None):
	"""Traza incondicional a kodi.log. No depende de ningun ajuste."""
	try:
		import xbmc
		xbmc.log('%s %s' % (LOG_TAG, msg), 2 if level is None else level)
	except Exception:
		pass


def _log_shape(tag, data, extra=''):
	"""Aviso cuando un parser saca 0 items de una respuesta NO vacia."""
	_hard_log('%s: 0 items parsed from %s %s' % (tag, _shape(data), extra))


def _log_fail(method, endpoint, exc):
	"""Fallo de peticion, SIEMPRE visible, con el codigo HTTP y un extracto.

	Sin el codigo no se distingue un 401 (token) de un 404 (endpoint que no
	existe) de un timeout, que son tres arreglos completamente distintos."""
	status, body = '?', ''
	try:
		r = getattr(exc, 'response', None)
		if r is not None:
			status = r.status_code
			body = (r.text or '')[:200].replace('\n', ' ')
	except Exception:
		pass
	_hard_log('%s %s FAILED: HTTP %s | %s | %s'
			  % (method, endpoint, status, type(exc).__name__, body or exc), 3)


def _dev_log(msg):
	"""Traza por peticion. Solo con dev.mode.enable activo, pero ya sin
	depender de debug.enabled."""
	try:
		if getSetting('dev.mode.enable') == 'true':
			_hard_log(msg, 1)
	except Exception:
		pass


def _get(endpoint, params=None, timeout=15):
	cred, base_url = getMDBListCredentials()
	if not cred:
		return None
	headers, auth_params = _auth_headers_params()
	p = dict(auth_params)
	if params:
		p.update(params)
	try:
		r = requests.get(base_url + endpoint, params=p, headers=headers, timeout=timeout)
		r.raise_for_status()
		data = r.json()
		_dev_log('GET %s -> %s %s' % (endpoint, r.status_code, _shape(data)))
		return data
	except Exception as e:
		_log_fail('GET', endpoint, e)
		return None


def _get_all_pages(endpoint, params=None, page_size=1000, max_pages=20):
	"""GET siguiendo la paginacion por cursor de MDBList.

	MDBList no pagina en el cuerpo: manda `X-Has-More` y `X-Next-Cursor` en las
	CABECERAS, y se continua pasando `cursor`. Cualquier endpoint que se lea de
	un solo tiron se queda con la primera pagina en silencio."""
	cred, base_url = getMDBListCredentials()
	if not cred:
		return None
	headers, auth_params = _auth_headers_params()
	p = dict(auth_params)
	p['limit'] = page_size
	if params:
		p.update(params)
	out, pages = [], 0
	while pages < max_pages:
		try:
			r = requests.get(base_url + endpoint, params=p, headers=headers, timeout=20)
			r.raise_for_status()
			data = r.json()
		except Exception as e:
			_log_fail('GET', endpoint, e)
			return out or None
		pages += 1
		chunk = _unwrap_list(data, ('events', 'items', 'results', 'data'))
		_dev_log('GET %s pagina %d -> %s (%d entradas)'
				 % (endpoint, pages, _shape(data), len(chunk)))
		out.extend(chunk)
		if r.headers.get('X-Has-More') != 'true':
			break
		cursor = r.headers.get('X-Next-Cursor')
		if not cursor:
			break
		p['cursor'] = cursor
	return out


_ITEM_BUCKETS = ('movies', 'shows', 'seasons', 'episodes', 'items')


def _get_all_pages_dict(endpoint, params=None, page_size=1000, max_pages=20):
	"""Como _get_all_pages, pero CONSERVANDO la forma de dict por tipo de medio.

	/lists/{id}/items no responde una lista pelada sino {'movies': [...],
	'shows': [...]}, asi que la version plana no sirve aqui: aplanaria las dos
	cestas en una sola y se perderia el reparto.

	Sin esto, cualquier lista de mas de una pagina se leia truncada EN SILENCIO
	(la peticion va bien, simplemente falta la mitad). Con las listas propias
	rara vez importa; con las ajenas de Liked Lists, que llegan a miles de
	titulos, es la norma. Mismo fallo que ya se corrigio en el calendario.

	Devuelve el dict combinado, o None si falla la PRIMERA pagina (para que el
	llamante distinga "vacio" de "no se pudo leer")."""
	cred, base_url = getMDBListCredentials()
	if not cred:
		return None
	headers, auth_params = _auth_headers_params()
	p = dict(auth_params)
	p['limit'] = page_size
	if params:
		p.update(params)
	out, pages = {}, 0
	while pages < max_pages:
		try:
			r = requests.get(base_url + endpoint, params=p, headers=headers, timeout=20)
			r.raise_for_status()
			data = r.json()
		except Exception as e:
			_log_fail('GET', endpoint, e)
			return out or None
		pages += 1
		if not isinstance(data, dict):
			# Algunos endpoints devuelven la lista pelada; se normaliza a 'items'.
			data = {'items': data if isinstance(data, list) else []}
		for k in _ITEM_BUCKETS:
			v = data.get(k)
			if isinstance(v, list) and v:
				out.setdefault(k, []).extend(v)
		_dev_log('GET %s pagina %d -> %s' % (endpoint, pages, _shape(data)))
		if r.headers.get('X-Has-More') != 'true':
			break
		cursor = r.headers.get('X-Next-Cursor')
		if not cursor:
			break
		p['cursor'] = cursor
	if pages > 1:
		_hard_log('%s leido en %d paginas (%s)'
				  % (endpoint, pages, ', '.join('%s=%d' % (k, len(v)) for k, v in out.items())))
	return out


def _post(endpoint, json_data=None, timeout=15, silent=False):
	cred, base_url = getMDBListCredentials()
	if not cred:
		return None
	headers, auth_params = _auth_headers_params()
	try:
		r = requests.post(base_url + endpoint, params=auth_params, headers=headers,
						  json=json_data or {}, timeout=timeout)
		r.raise_for_status()
		try:
			data = r.json()
		except Exception:
			data = {}
		_dev_log('POST %s -> %s %s' % (endpoint, r.status_code, _shape(data)))
		return data
	except Exception as e:
		# `silent` NO silencia el log: silenciaba justo los dos casos que hacia
		# falta ver (el batch del calendario de peliculas y el scrobble). Solo
		# existe para no molestar al usuario con una notificacion.
		_log_fail('POST', endpoint, e)
		return None


def _delete(endpoint, json_data=None, timeout=15):
	# OJO: la credencial NO siempre es una API key. En modo OAuth,
	# getMDBListCredentials() devuelve el access_token, y mandarlo como
	# ?apikey= daba un 401 garantizado. Se coloca segun el modo activo,
	# igual que _get() y _post().
	cred, base_url = getMDBListCredentials()
	if not cred:
		return None
	headers, auth_params = _auth_headers_params()
	try:
		r = requests.delete(base_url + endpoint, params=auth_params, headers=headers,
						   json=json_data or {}, timeout=timeout)
		r.raise_for_status()
		try:
			return r.json()
		except Exception:
			return {}
	except Exception as e:
		_log_fail('DELETE', endpoint, e)
		return None


# ---------------------------------------------------------------------------
# Scrobbling  (POST /scrobble/{start,pause,stop,clear})
# ---------------------------------------------------------------------------

def _build_scrobble_body(imdb, tmdb, tvdb, season, episode, progress):
	"""Cuerpo para /scrobble/*. OJO: MDBList anida temporada/episodio DENTRO
    del objeto show (show.season.number / show.season.episode.number), no en
    un objeto 'episode' separado como Trakt/SIMKL."""
	ids = {}
	if imdb:
		_i = str(imdb)
		if not _i.startswith('tt'):
			_i = 'tt' + _i
		ids['imdb'] = _i
	if tmdb:
		ids['tmdb'] = int(str(tmdb)) if str(tmdb).isdigit() else str(tmdb)
	if tvdb:
		ids['tvdb'] = int(str(tvdb)) if str(tvdb).isdigit() else str(tvdb)

	# MDBList valida `progress` con un decimal de 5 digitos TOTALES: mandar
	# 5.473972418400796 devuelve HTTP 400 {"progress":["Ensure that there are no
	# more than 5 digits in total."]} y el scrobble se pierde entero. El
	# porcentaje sale de una division en float, asi que practicamente SIEMPRE
	# tenia demasiados digitos: en el log del usuario (17-ago-2026) fallaron
	# todas las pausas seguidas. Dos decimales sobran para un punto de resume
	# (0,01% de un episodio de 50 min son 0,3 s) y 100.00 cabe en 5 digitos.
	try:
		_prog = round(min(max(float(progress), 0.0), 100.0), 2)
	except Exception:
		_prog = 0.0

	body = {
		'progress': _prog,
		'app_version': control.getluc_kodiVersion() if hasattr(control, 'getluc_kodiVersion') else '1.0.0',
		'app_date': time.strftime('%Y-%m-%d'),
	}
	if not episode:
		body['movie'] = {'ids': ids}
	else:
		body['show'] = {
			'ids': ids,
			'season': {'number': int(season), 'episode': {'number': int(episode)}},
		}
	return body


def _scrobble_call(action, imdb, tmdb, tvdb, season, episode, progress):
	"""Despacha /scrobble/{action} con throttle local."""
	global _last_scrobble_at
	now = time.time()
	if action not in ('stop', 'clear') and (now - _last_scrobble_at['ts']) < _SCROBBLE_THROTTLE_SECONDS:
		log_utils.log('MDBList scrobble %s skipped (cooldown).' % action, level=log_utils.LOGDEBUG)
		return False
	_last_scrobble_at['ts'] = now

	# Si es episodio y NO hay NINGÚN id, la llamada fracasará seguro en MDBList
	# (no puede emparejar la serie). Avisar claramente en el log.
	if episode and not (imdb or tmdb or tvdb):
		_hard_log('scrobble/%s ABORTADO: episodio sin ids '
				  '(tvshow=S%sE%s prog=%s). El item de "Continuar viendo" '
				  'no traia imdb/tmdb/tvdb.' % (action, season, episode, progress))
		return False

	try:
		body = _build_scrobble_body(imdb, tmdb, tvdb, season, episode, progress)
		r = _post('/scrobble/%s' % action, json_data=body, silent=True)
		if r is None:
			_hard_log('scrobble/%s FAILED (imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s)' %
					  (action, imdb, tmdb, tvdb, season, episode, progress))
			return False
		# Solo al EMPEZAR. Antes avisaba en cada scrobble, y como la pausa
		# periodica va cada 60 s eso era un popup por minuto durante toda la
		# reproduccion (en el log del 18-ago-2026 salieron cuatro en cinco
		# minutos). Un aviso al arrancar confirma que el tracking esta vivo,
		# que es para lo que sirve el ajuste; el resto es ruido encima del video.
		if action == 'start' and getSetting('mdblist.notify') == 'true':
			control.notification(title='MDBList', message='Scrobble %s OK' % action)
		_dev_log('scrobble/%s OK (imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s)' %
				 (action, imdb, tmdb, tvdb, season, episode, progress))
		return True
	except Exception:
		log_utils.error()
		return False


def scrobbleStart(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
	if not getMDBListScrobbleInfo():
		return False
	return _scrobble_call('start', imdb, tmdb, tvdb, season, episode, watched_percent)


def scrobblePause(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
	if not getMDBListScrobbleInfo():
		return False
	return _scrobble_call('pause', imdb, tmdb, tvdb, season, episode, watched_percent)


def scrobbleStop(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=100):
	"""/scrobble/stop con progress >= 80 marca como visto en MDBList."""
	if not getMDBListScrobbleInfo():
		return False
	ok = _scrobble_call('stop', imdb, tmdb, tvdb, season, episode, watched_percent)
	if ok and float(watched_percent) >= 80:
		try:
			invalidateSectionCaches()
		except Exception:
			log_utils.error()
	return ok


def scrobbleClear(imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
	"""/scrobble/clear — borra la sesión en pausa (resume) sin marcar visto."""
	if not getMDBListScrobbleInfo():
		return False
	return _scrobble_call('clear', imdb, tmdb, tvdb, season, episode, 0)


def invalidateSectionCaches(account_change=False):
	"""Invalida los caches de las secciones MDBList para que se refresquen al
    instante tras un stop / una (des)autorizacion.

    OJO: "Continue Watching" NO se cachea (getContinueMovies/Episodes piden
    /sync/playback en vivo), asi que aqui no hay nada que tirar por ese lado.
    Lo que SI tiene TTL y por tanto puede tapar un cambio reciente es la
    watchlist (30 min), los items de lista (60 min) y el calendario (1-6 h).
    La version anterior apuntaba a atributos `mdblist_*` de Episodes que NUNCA
    han existido en episodes.py: el getattr lanzaba AttributeError, el except
    interior se lo tragaba y la funcion no invalidaba absolutamente nada."""
	try:
		from resources.lib.database import cache
		# Siempre: lo que depende del progreso de visionado.
		targets = [(getCalendarEpisodes, ('upcoming',)),
				   (getCalendarEpisodes, ('recent',))]
		if account_change:
			# Cambio de cuenta (auth/deauth): ademas todo lo que es "del
			# usuario", que con otra credencial ya no es lo mismo.
			targets += [(getWatchlistMovies, ()), (getWatchlistShows, ()),
						(getUserLists, ()), (getCalendarMovies, ())]
		for fn, args in targets:
			try:
				cache.remove(fn, *args)
			except Exception:
				pass
	except Exception:
		pass


# ---------------------------------------------------------------------------
# Continue Watching  (GET /sync/playback)  — reemplaza la BD del servicio
# ---------------------------------------------------------------------------

def _id_from(ids, *keys):
	"""Primer id no vacío probando varias variantes de clave. MDBList es
    INCONSISTENTE: unos endpoints devuelven 'tmdb', otros 'tmdbid'."""
	if not isinstance(ids, dict):
		return ''
	for k in keys:
		v = ids.get(k)
		if v:
			return str(v)
	return ''


def _tmdb_from(ids):
	return _id_from(ids, 'tmdb', 'tmdbid', 'tmdb_id')


def _imdb_from(ids):
	return _id_from(ids, 'imdb', 'imdbid', 'imdb_id')


def _tvdb_from(ids):
	return _id_from(ids, 'tvdb', 'tvdbid', 'tvdb_id')


def _fetch_server_paused():
	"""GET /sync/playback → (movies_list, episodes_list) normalizados.

    El servidor devuelve una LISTA plana donde cada item tiene type, progress,
    paused_at y un objeto movie/episode/show con ids.{imdbid,tmdbid,tvdbid}
    (¡con sufijo 'id'!)."""
	data = _get('/sync/playback')
	if not data or not isinstance(data, list):
		return [], []

	movies, episodes = [], []

	for it in data:
		try:
			typ = (it.get('type') or '').lower()
			pct = float(it.get('progress') or 0)
			if pct <= 0 or pct >= 85:
				continue
			paused_at = it.get('paused_at', '') or ''

			if typ == 'movie' and it.get('movie'):
				mv = it['movie']
				ids = mv.get('ids') or {}
				movies.append({
					'type': 'movie',
					'imdb': _imdb_from(ids),
					'tmdb': _tmdb_from(ids),
					'tvdb': '',
					'title': mv.get('title', ''),
					'originaltitle': mv.get('title', ''),
					'tvshowtitle': '',
					'year': str(mv.get('year', '')),
					'season': 0,
					'episode': 0,
					'duration': int((mv.get('runtime') or 0)) * 60,
					'progress': str(round(pct, 2)),
					'paused_at': paused_at,
					'next': '',
				})
			elif typ == 'episode' and it.get('show'):
				sh = it['show']
				epd = it.get('episode') or {}
				sids = sh.get('ids') or {}
				eids = epd.get('ids') or {}
				episodes.append({
					'type': 'episode',
					'imdb': _imdb_from(sids) or _imdb_from(eids),
					'tmdb': _tmdb_from(sids),
					'tvdb': _tvdb_from(sids),
					'title': epd.get('title', ''),
					'originaltitle': epd.get('title', ''),
					'tvshowtitle': sh.get('title', ''),
					'year': str(sh.get('year', '')),
					'season': int(epd.get('season') or 0),
					'episode': int(epd.get('number') or 0),
					'duration': int((epd.get('runtime') or sh.get('runtime') or 0)) * 60,
					'progress': str(round(pct, 2)),
					'paused_at': paused_at,
					'next': '',
				})
		except Exception:
			pass

	movies.sort(key=lambda k: k.get('paused_at', ''), reverse=True)
	episodes.sort(key=lambda k: k.get('paused_at', ''), reverse=True)
	return movies, episodes


def getContinueMovies():
	"""Películas en progreso desde el servidor MDBList (/sync/playback)."""
	movies, _ = _fetch_server_paused()
	return movies


def getContinueEpisodes():
	"""Episodios en progreso desde el servidor MDBList (/sync/playback)."""
	_, episodes = _fetch_server_paused()
	return episodes


# ---------------------------------------------------------------------------
# Up Next  (GET /upnext) — siguiente episodio no visto de series en curso
# ---------------------------------------------------------------------------

def _air_date(ne):
	"""Fecha de emision de un next_episode, en YYYY-MM-DD.

	Igual que con el numero de episodio, el nombre del campo no es estable:
	se aceptan las variantes conocidas y se recorta cualquier marca de tiempo
	ISO. Antes solo se leia 'air_date', y una entrada con 'first_aired' se
	descartaba en silencio por 'no tener fecha'."""
	if not isinstance(ne, dict):
		return ''
	for k in ('air_date', 'aired', 'first_aired', 'airdate', 'released',
			  'release_date', 'premiered', 'date'):
		v = ne.get(k)
		if v:
			return str(v)[:10]
	return ''


def _ep_number(ne):
	"""Numero de episodio de un objeto next_episode de /upnext.

    MDBList es INCONSISTENTE con esta clave igual que lo es con los ids: el
    objeto episode de /sync/playback y el cuerpo de /scrobble/* usan 'number',
    mientras que parte de la documentacion de /upnext habla de 'episode'.
    Aceptamos AMBAS: si solo se leia 'episode' y el servidor mandaba 'number',
    el episodio salia como 0 y el Calendar de series quedaba inservible sin
    ningun error visible en el log."""
	if not isinstance(ne, dict):
		return 0
	for k in ('number', 'episode', 'episode_number'):
		v = ne.get(k)
		if v not in (None, ''):
			try:
				return int(v)
			except Exception:
				continue
	return 0


def _ep_season(ne):
	"""Temporada del objeto next_episode. Mismo criterio que _ep_number()."""
	if not isinstance(ne, dict):
		return 0
	for k in ('season', 'season_number', 'number_season'):
		v = ne.get(k)
		if v not in (None, ''):
			try:
				return int(v)
			except Exception:
				continue
	return 0


def getUpNext(hide_unreleased=True, limit=40):
	"""Devuelve lista de episodios "siguiente no visto" normalizada al formato
    que consumen las secciones de episodios."""
	params = {'limit': limit}
	if hide_unreleased:
		params['hide_unreleased'] = 'true'
	data = _get('/upnext', params=params)
	if not data:
		return []
	entries = _unwrap_list(data)
	if not entries:
		_log_shape('upnext', data)
		return []
	out = []
	for it in entries:
		try:
			sh, ne = _upnext_entry(it)
			if sh is None:
				continue
			sids = sh.get('ids') or {}
			out.append({
				'type': 'episode',
				'imdb': str(sids.get('imdb') or sids.get('imdbid') or ''),
				'tmdb': str(sids.get('tmdb') or sids.get('tmdbid') or '') if (sids.get('tmdb') or sids.get('tmdbid')) else '',
				'tvdb': str(sids.get('tvdb') or sids.get('tvdbid') or '') if (sids.get('tvdb') or sids.get('tvdbid')) else '',
				'title': ne.get('title', ''),
				'originaltitle': ne.get('title', ''),
				'tvshowtitle': sh.get('title', ''),
				'year': str(sh.get('year', '')),
				'season': _ep_season(ne),
				'episode': _ep_number(ne),
				'premiered': _air_date(ne),
				'duration': int((ne.get('runtime') or 0)) * 60,
				'last_watched_at': it.get('last_watched_at', ''),
				'next': '',
			})
		except Exception:
			pass
	out.sort(key=lambda k: k.get('last_watched_at', ''), reverse=True)
	return out


# ---------------------------------------------------------------------------
# Calendar — contenido futuro/reciente construido con datos de MDBList
#
# La web de MDBList tiene un "Calendar" propio (mdblist.com/calendar) pero NO
# expone endpoint /calendar en la API publica (verificado contra el OpenAPI
# 1.0.0 y el apiary oficial, ago-2026). Se construye el equivalente con lo que
# la API SI da:
#   - Episodios: GET /upnext SIN hide_unreleased -> siguiente episodio no
#     visto de cada serie en curso, incluidos los aun no emitidos (air_date).
#   - Peliculas: watchlist + Media Info Batch (POST /imdb/movie, hasta 200
#     ids por llamada) -> campos released / released_digital.
# ---------------------------------------------------------------------------

_UPNEXT_WRAPPER_KEYS = ('items', 'results', 'data', 'shows', 'upnext', 'up_next', 'entries')


def _unwrap_list(data, keys=_UPNEXT_WRAPPER_KEYS):
	"""Devuelve la lista de entradas venga como venga.

	MDBList no es consistente con la envoltura entre endpoints: /lists/user
	responde una lista pelada mientras /watchlist/items responde un dict con
	claves por tipo de medio. Asumir una sola forma es lo que dejaba los
	calendarios vacios SIN un solo error en el log, porque la peticion iba
	bien y el parser simplemente no encontraba nada donde miraba."""
	if isinstance(data, list):
		return data
	if isinstance(data, dict):
		for k in keys:
			v = data.get(k)
			if isinstance(v, list):
				return v
		# Ultimo recurso: un unico valor de tipo lista en todo el dict.
		lists = [v for v in data.values() if isinstance(v, list)]
		if len(lists) == 1:
			return lists[0]
	return []


def _upnext_entry(it):
	"""Normaliza UNA entrada de /upnext a (show_dict, next_episode_dict).

	Acepta la forma anidada {show:{...}, next_episode:{...}} y tambien la
	aplanada, donde los campos de la serie y del episodio viven en el mismo
	nivel. Con la anidada como unica opcion, una respuesta plana daba 0."""
	if not isinstance(it, dict):
		return None, None
	sh = it.get('show') if isinstance(it.get('show'), dict) else None
	ne = None
	for k in ('next_episode', 'nextEpisode', 'episode', 'next'):
		if isinstance(it.get(k), dict):
			ne = it[k]
			break
	if sh is None and ne is None:
		# Plana: la propia entrada hace de las dos cosas.
		return it, it
	return (sh or it), (ne or it)


def _upnext_all(limit=100):
	"""Como getUpNext pero SIN ocultar episodios sin emitir: materia prima del
    calendario. air_date llega como YYYY-MM-DD; se convierte al formato UTC de
    Trakt (YYYY-MM-DDT00:00:00.000Z) para reutilizar sin tocar nada las ramas
    calendar_unaired / calendar_recent de episodeDirectory()."""
	data = _get('/upnext', params={'limit': limit})
	if not data:
		_hard_log('upnext: la peticion no devolvio datos (ver la linea FAILED de arriba)')
		return []
	entries = _unwrap_list(data)
	if not entries:
		_log_shape('upnext', data)
		return []
	out = []
	no_air = 0
	for it in entries:
		try:
			sh, ne = _upnext_entry(it)
			if sh is None:
				continue
			sids = sh.get('ids') or {}
			air = _air_date(ne)
			if not air:
				no_air += 1
				continue  # sin fecha no hay calendario
			out.append({
				'type': 'episode',
				'imdb': str(sids.get('imdb') or sids.get('imdbid') or ''),
				'tmdb': str(sids.get('tmdb') or sids.get('tmdbid') or '') if (sids.get('tmdb') or sids.get('tmdbid')) else '',
				'tvdb': str(sids.get('tvdb') or sids.get('tvdbid') or '') if (sids.get('tvdb') or sids.get('tvdbid')) else '',
				'title': ne.get('title', ''),
				'originaltitle': ne.get('title', ''),
				'tvshowtitle': sh.get('title', ''),
				'year': str(sh.get('year', '')),
				'season': _ep_season(ne),
				'episode': _ep_number(ne),
				'premiered': '%sT00:00:00.000Z' % air,
				'sort_date': air,
				'duration': int((ne.get('runtime') or 0)) * 60,
				'next': '',
			})
		except Exception:
			pass
	if not out:
		_log_shape('upnext', data, '(%d entradas, %d sin air_date)' % (len(entries), no_air))
	else:
		_dev_log('upnext: %d entradas -> %d con fecha' % (len(entries), len(out)))
	return out


def _sample_dates(items, n=12):
	"""Fechas de emision que devolvio /upnext, ordenadas. Sin titulos ni ids:
	solo las fechas, que es lo unico que decide si entran en el calendario."""
	try:
		d = sorted(i.get('sort_date', '') for i in items if i.get('sort_date'))
		if not d:
			return '(ninguna)'
		if len(d) <= n:
			return ', '.join(d)
		return '%s ... %s (%d en total)' % (', '.join(d[:n // 2]), ', '.join(d[-n // 2:]), len(d))
	except Exception:
		return '?'


def getCalendarEvents(start=None, end=None):
	"""Emisiones del calendario personal de MDBList — GET /calendar/events.

	ESTE es el endpoint del calendario, y no esta documentado (ni en el OpenAPI
	ni en el apiary). Se localizo el 17-ago-2026 leyendo como lo resuelve el
	addon Red Light, despues de que un log demostrara que /upnext no sirve para
	esto: /upnext devuelve "el siguiente episodio que NO has visto", que con
	atraso acumulado son episodios de hace anios. En el log del usuario salieron
	13 episodios con fechas entre 2000-01-09 y 2026-06-05 y ni uno dentro de la
	ventana del calendario. Su propia web lo separa en dos pestanas distintas:
	"Up Next" (13) y "Upcoming" (2). /upnext es la primera; esta es la segunda.

	Devuelve items ya normalizados al formato que consume episodeDirectory.
	Los eventos traen `show_tmdb`, sin imdb ni tvdb: el enriquecimiento posterior
	resuelve titulo de episodio y arte a partir del tmdb de la serie."""
	# Por defecto el feed devuelve solo emisiones FUTURAS: en el log del usuario
	# (17-ago-2026) llegaron 4 eventos, todos del 21-ago al 4-oct, y "Recently
	# Aired" salia vacio aunque su web SI muestra los episodios ya emitidos del
	# mes. Para la ventana pasada se piden limites de fecha. Los nombres de
	# parametro no estan documentados (el endpoint entero no lo esta), asi que
	# se prueban y, si la peticion falla, se repite SIN limites: mas vale el
	# comportamiento de antes que romper el calendario que ya funciona.
	params = None
	if start or end:
		params = {}
		if start:
			params['start_date'] = start
			params['start'] = start
		if end:
			params['end_date'] = end
			params['end'] = end
	events = _get_all_pages('/calendar/events', params=params) if params else \
		_get_all_pages('/calendar/events')
	if events is None and params:
		_hard_log('calendar/events: fallo con limites de fecha %s; reintento sin ellos' % params)
		events = _get_all_pages('/calendar/events')
	if events is None:
		_hard_log('calendar/events: la peticion fallo (ver la linea FAILED de arriba)')
		return []
	if not events:
		_hard_log('calendar/events: 0 eventos devueltos')
		return []
	out, skipped = [], 0
	for it in events:
		try:
			if not isinstance(it, dict):
				continue
			# Solo episodios: el mismo feed trae estrenos de peliculas.
			# NO se filtra por release_type: MDBList marca 'watched' tambien las
			# emisiones futuras de series que ya estas viendo, que son justo las
			# que interesan.
			itype = it.get('type')
			if itype and itype != 'episode':
				skipped += 1
				continue
			tmdb = it.get('show_tmdb') or it.get('tmdb')
			season = it.get('season_number')
			episode = it.get('episode_number')
			start = it.get('start') or it.get('air_date') or it.get('date')
			if not tmdb or season is None or episode is None or not start:
				skipped += 1
				continue
			season, episode = int(season), int(episode)
			if season < 1:      # especiales fuera del calendario
				skipped += 1
				continue
			air = str(start)[:10]
			out.append({
				'type': 'episode',
				'imdb': str(it.get('show_imdb') or ''),
				'tmdb': str(tmdb),
				'tvdb': str(it.get('show_tvdb') or ''),
				'title': it.get('episode_title') or '',
				'originaltitle': it.get('episode_title') or '',
				'tvshowtitle': it.get('title') or '',
				'year': str(it.get('year') or ''),
				'season': season,
				'episode': episode,
				'premiered': '%sT00:00:00.000Z' % air,
				'sort_date': air,
				'duration': int(it.get('runtime') or 0) * 60,
				'next': '',
			})
		except Exception:
			skipped += 1
	# MDBList repite la misma serie/dia en ocasiones.
	seen, dedup = set(), []
	for i in out:
		k = (i['tmdb'], i['season'], i['episode'], i['sort_date'])
		if k in seen:
			continue
		seen.add(k)
		dedup.append(i)
	_dev_log('calendar/events: %d eventos -> %d episodios (%d descartados, %d duplicados)'
			 % (len(events), len(dedup), skipped, len(out) - len(dedup)))
	return dedup


def getCalendarEpisodes(mode='upcoming', recent_days=30):
	"""Calendario de episodios de las series que sigues en MDBList.
    mode='upcoming': aun sin emitir (hoy incluido), ascendente por fecha.
    mode='recent'  : emitidos y sin ver en los ultimos recent_days, descendente."""
	from datetime import datetime, timedelta, timezone
	_now = datetime.now(timezone.utc)
	today = _now.strftime('%Y-%m-%d')
	# FUENTE: /calendar/events, no /upnext. Ver getCalendarEvents() para por que.
	floor = (_now - timedelta(days=recent_days)).strftime('%Y-%m-%d')
	if mode == 'upcoming':
		items = getCalendarEvents()
	else:
		# El feed por defecto solo trae futuro: para lo ya emitido hay que
		# pedir explicitamente la ventana pasada.
		items = getCalendarEvents(start=floor, end=today)
	raw_n = len(items)
	items_raw = list(items)
	if mode == 'upcoming':
		items = [i for i in items if i['sort_date'] >= today]
		items.sort(key=lambda k: k['sort_date'])
		for i in items:
			i['calendar_unaired'] = True
	else:
		items = [i for i in items if floor <= i['sort_date'] < today]
		items.sort(key=lambda k: k['sort_date'], reverse=True)
		for i in items:
			i['calendar_recent'] = True
	# Etapa que hasta ahora era CIEGA: si /upnext devuelve episodios pero todos
	# caen fuera de la ventana de fechas, el calendario sale vacio sin que se
	# registre absolutamente nada. Es el unico camino que explicaba un log sin
	# una sola linea de MDBList y los tres calendarios en blanco.
	if not items and raw_n:
		_hard_log('calendarEpisodes(%s): %d emisiones de /calendar/events, 0 dentro '
				  'de la ventana [%s .. %s]. Fechas devueltas: %s'
				  % (mode, raw_n, floor, today, _sample_dates(items_raw)))
	else:
		_dev_log('calendarEpisodes(%s): %d de %d dentro de la ventana'
				 % (mode, len(items), raw_n))
	return items


def getCalendarMovies(recent_days=30):
	"""Calendario de peliculas de tu watchlist MDBList: estrenos en cine y en
    digital desde hace recent_days hasta el futuro, ascendente por fecha. Cada
    item lleva mdb_calendar_date (la fecha relevante) y mdb_calendar_kind
    ('theatrical'|'digital') para la etiqueta."""
	from datetime import datetime, timedelta, timezone
	if not getMDBListCredentialsInfo():
		return []
	watchlist = getWatchlistMovies() or []
	ids = [w['imdb'] for w in watchlist if w.get('imdb')]
	if not ids:
		return []
	_now = datetime.now(timezone.utc)
	today = _now.strftime('%Y-%m-%d')
	floor = (_now - timedelta(days=recent_days)).strftime('%Y-%m-%d')
	out = []
	for chunk_start in range(0, len(ids), 200):  # limite documentado del batch
		chunk = ids[chunk_start:chunk_start + 200]
		data = _post('/imdb/movie', json_data={'ids': chunk}, silent=True)
		if not data:
			continue
		# La respuesta del batch puede venir como lista pelada o envuelta en un
		# dict (p.ej. {"movies": [...]}). Solo se aceptaba la lista, y con la
		# otra forma el calendario salia vacio SIN error: _post es silent aqui.
		rows = _unwrap_list(data, ('movies', 'items', 'results', 'data'))
		if not rows and isinstance(data, dict):
			# Ultima variante plausible: dict indexado por id -> {tt123: {...}}
			rows = [v for v in data.values() if isinstance(v, dict)]
		if not rows:
			_log_shape('imdb/movie batch', data)
			continue
		for m in rows:
			try:
				mids = m.get('ids') or {}
				theatrical = (m.get('released') or '')[:10]
				digital = (m.get('released_digital') or '')[:10]
				# fecha "relevante": la digital si aun no ha llegado (o si el
				# estreno en cine ya paso), si no la de cine; siempre dentro
				# de la ventana [floor, futuro)
				cal_date, cal_kind = '', ''
				if theatrical and theatrical >= floor:
					cal_date, cal_kind = theatrical, 'theatrical'
				if digital and digital >= floor:
					if not cal_date or (theatrical < today and digital >= cal_date):
						cal_date, cal_kind = digital, 'digital'
				if not cal_date:
					continue
				out.append({
					'title': m.get('title', ''),
					'originaltitle': m.get('title', ''),
					'year': str(m.get('year', '')),
					'imdb': str(mids.get('imdb') or ''),
					'tmdb': str(mids.get('tmdb') or '') if mids.get('tmdb') else '',
					'tvdb': '',
					'mdb_calendar_date': cal_date,
					'mdb_calendar_kind': cal_kind,
					'next': '',
				})
			except Exception:
				pass
	out.sort(key=lambda k: k['mdb_calendar_date'])
	if not out:
		_hard_log('calendarMovies: %d peliculas en watchlist con imdb, 0 con fecha '
				  'de estreno dentro de [%s .. futuro]' % (len(ids), floor))
	else:
		_dev_log('calendarMovies: %d en watchlist -> %d con fecha en ventana'
				 % (len(ids), len(out)))
	return out


# ---------------------------------------------------------------------------
# Watched history  (GET/POST /sync/watched)
# ---------------------------------------------------------------------------

def addWatched(imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
	"""Marca un título como visto en MDBList vía /sync/watched."""
	if not getMDBListCredentialsInfo():
		return False
	ids = {}
	if imdb:
		_i = str(imdb)
		if not _i.startswith('tt'):
			_i = 'tt' + _i
		ids['imdb'] = _i
	if tmdb and str(tmdb).isdigit():
		ids['tmdb'] = int(tmdb)
	if tvdb and str(tvdb).isdigit():
		ids['tvdb'] = int(tvdb)
	if not episode:
		payload = {'movies': [{'ids': ids}]}
	else:
		payload = {'shows': [{'ids': ids, 'seasons': [
			{'number': int(season), 'episodes': [{'number': int(episode)}]}]}]}
	return _post('/sync/watched', json_data=payload, silent=True) is not None


# ---------------------------------------------------------------------------
# Watchlist  (GET /watchlist/items ; POST /watchlist/items/{add,remove})
# ---------------------------------------------------------------------------

def _build_watchlist_items(data, kind):
	items = []
	for m in (data.get(kind) or []):
		try:
			# str() sobre un None da la CADENA 'None', que es truthy: un
			# imdb_id nulo (pasa con estrenos recientes aun sin ficha IMDb)
			# se colaba como imdb='None', sobrevivia al filtro de worker() y
			# luego rompia la busqueda de metadatos. Igual con release_year.
			items.append({
				'title': m.get('title') or '',
				'year': str(m.get('release_year') or ''),
				'imdb': str(m.get('imdb_id') or ''),
				'tmdb': str(m.get('tmdb_id') or ''),
				'tvdb': str(m.get('tvdb_id') or ''),
				'rank': m.get('rank') or 9999,
			})
		except Exception:
			log_utils.error()
	items.sort(key=lambda x: x.get('rank', 9999))
	raw_n = len(data.get(kind) or []) if isinstance(data, dict) else 0
	dropped = [i for i in items if not (i.get('imdb') or i.get('tmdb') or i.get('tvdb'))]
	if dropped:
		_hard_log('watchlist/%s: %d de %d sin ningun id utilizable '
				  '(se perderan al buscar metadatos)' % (kind, len(dropped), raw_n))
	_dev_log('watchlist/%s: %d en la respuesta -> %d normalizados' % (kind, raw_n, len(items)))
	return items


def getWatchlistMovies():
	data = _get('/watchlist/items')
	return _build_watchlist_items(data, 'movies') if data else []


def getWatchlistShows():
	data = _get('/watchlist/items')
	return _build_watchlist_items(data, 'shows') if data else []


def addToWatchlist(imdb_id, media_type):
	"""media_type: 'movie' | 'show'. Endpoint real: POST /watchlist/items/add."""
	key = 'movies' if media_type == 'movie' else 'shows'
	payload = {key: [{'ids': {'imdb': imdb_id}}]}
	return _post('/watchlist/items/add', json_data=payload) is not None


def removeFromWatchlist(imdb_id, media_type):
	key = 'movies' if media_type == 'movie' else 'shows'
	payload = {key: [{'ids': {'imdb': imdb_id}}]}
	return _post('/watchlist/items/remove', json_data=payload) is not None


# ---------------------------------------------------------------------------
# Listas de usuario y listas públicas
# ---------------------------------------------------------------------------

def getUserLists():
	data = _get('/lists/user')
	return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Edicion de listas estaticas  (POST /lists/<id>/items/<add|remove>)
# ---------------------------------------------------------------------------
# Solo las listas ESTATICAS son editables a mano. Las dinamicas se regeneran
# desde filtros de busqueda, las de IA desde un prompt guardado y las externas
# se parsean de Trakt/IMDb/Letterboxd: meterles un item duraria hasta el
# siguiente refresco, asi que se excluyen del selector.

def _list_is_editable(lst, media_type=None):
	"""True si la lista es estatica, propia y del tipo de medio pedido."""
	try:
		if lst.get('dynamic'):
			return False
		# 'external', 'feed' y 'linked' no siempre traen dynamic=True.
		for flag in ('external', 'feed', 'linked'):
			if lst.get(flag):
				return False
		if media_type:
			mt = str(lst.get('mediatype') or '').lower()
			# '' o 'any' = lista mixta, vale para ambos.
			if mt and mt not in ('any', 'mixed'):
				want = ('show', 'tv', 'tvshow', 'series') if media_type == 'show' else ('movie', 'movies')
				if mt not in want:
					return False
		return True
	except Exception:
		return False


def getEditableLists(media_type=None):
	"""Listas del usuario en las que SI se pueden anadir/quitar items."""
	return [l for l in (getUserLists() or []) if _list_is_editable(l, media_type)]


def _modify_list(list_id, action, imdb_id, media_type):
	"""POST /lists/<id>/items/<add|remove>.

    El cuerpo lleva los ids planos ({'imdb': 'tt...'}), que es la forma que usa
    el cliente oficial contra este endpoint. El de watchlist acepta ademas la
    forma anidada {'ids': {...}}, asi que si la plana no encuentra el titulo se
    reintenta con la anidada antes de darlo por fallido.
    """
	key = 'movies' if media_type == 'movie' else 'shows'
	for payload in ({key: [{'imdb': imdb_id}]}, {key: [{'ids': {'imdb': imdb_id}}]}):
		data = _post('/lists/%s/items/%s' % (list_id, action), json_data=payload)
		if data is None:
			return False
		if _modify_ok(data, action, key):
			return True
	return False


def _modify_ok(data, action, key):
	"""La API responde 200 aunque no encuentre el titulo: hay que mirar los
    contadores added/existing/not_found en vez de fiarse del codigo HTTP."""
	try:
		if not isinstance(data, dict):
			return False
		def n(section):
			blk = data.get(section) or {}
			return int(blk.get(key, 0) or 0) if isinstance(blk, dict) else 0
		if n('not_found') > 0:
			return False
		if action == 'add':
			return (n('added') + n('existing')) > 0
		return (n('removed') + n('deleted')) > 0 or not data.get('not_found')
	except Exception:
		return False


def addToList(list_id, imdb_id, media_type):
	ok = _modify_list(list_id, 'add', imdb_id, media_type)
	if ok:
		invalidateListCaches(list_id)
	return ok


def removeFromList(list_id, imdb_id, media_type):
	ok = _modify_list(list_id, 'remove', imdb_id, media_type)
	if ok:
		invalidateListCaches(list_id)
	return ok


def invalidateListCaches(list_id):
	"""Tira la cache de los items de esa lista y del indice de listas, para que
    el cambio se vea al momento y no tras los 60 min de TTL."""
	try:
		from resources.lib.database import cache
		for args in ((list_id, 'movie'), (list_id, 'show'), (list_id,)):
			try:
				cache.remove(getListItems, *args)
			except Exception:
				pass
		try:
			cache.remove(getUserLists)
		except Exception:
			pass
	except Exception:
		pass


def _build_movie(m):
	return {
		'title': m.get('title', ''),
		'year': str(m.get('release_year', '')),
		'imdb': str(m.get('imdb_id', '')),
		'tmdb': str(m.get('tmdb_id', '')) if m.get('tmdb_id') else '',
		'tvdb': '',
		'rank': m.get('rank', 9999),
	}


def _build_show(s):
	return {
		'title': s.get('title', ''),
		'year': str(s.get('release_year', '')),
		'imdb': str(s.get('imdb_id', '')),
		'tmdb': str(s.get('tmdb_id', '')) if s.get('tmdb_id') else '',
		'tvdb': str(s.get('tvdb_id', '')) if s.get('tvdb_id') else '',
		'rank': s.get('rank', 9999),
	}


def getListItems(list_id, media_type=None):
	# Paginado por cursor: las listas ajenas (Liked / Top) pasan de 1000 items
	# con facilidad y una sola pagina se quedaria a medias sin avisar.
	data = _get_all_pages_dict('/lists/%s/items' % list_id)
	if not data:
		return [], []
	movies = sorted([_build_movie(m) for m in (data.get('movies') or [])], key=lambda x: x['rank'])
	shows = sorted([_build_show(s) for s in (data.get('shows') or [])], key=lambda x: x['rank'])
	if media_type == 'show' and not shows:
		sfm = [_build_show(m) for m in (data.get('movies') or [])
			   if str(m.get('mediatype', '')).lower() in ('show', 'tv', 'tvshow', 'series')]
		if sfm:
			shows = sorted(sfm, key=lambda x: x['rank'])
	if media_type == 'movie':
		return movies, []
	if media_type == 'show':
		return [], shows
	return movies, shows


def getTopLists():
	data = _get('/lists/top')
	return data if isinstance(data, list) else []


def searchLists(query):
	data = _get('/lists/search', params={'query': query})
	if isinstance(data, list):
		return data
	if isinstance(data, dict) and isinstance(data.get('lists'), list):
		return data['lists']
	return []


def getMediaInfo(imdb_id, mediatype='movie'):
	"""v1.0.54: la ruta depende del tipo de medio. Antes siempre se pedia
    '/imdb/movie/...', asi que con una serie MDBList respondia 404 y las
    valoraciones (IMDb/TMDB/Trakt/Letterboxd...) del panel de fuentes se
    quedaban sin rellenar por MDBList — habia que esperar al Tier 2."""
	path = '/imdb/show/%s' if str(mediatype or '').lower() in ('tvshow', 'show', 'episode', 'season', 'tv') else '/imdb/movie/%s'
	return _get(path % imdb_id)


def resolveShowIds(ids_dict):
	if ids_dict.get('tvdb'):
		return ids_dict
	try:
		if ids_dict.get('tmdb'):
			data = _get('/tmdb/show/%s' % ids_dict['tmdb'])
		elif ids_dict.get('imdb'):
			data = _get('/imdb/show/%s' % ids_dict['imdb'])
		else:
			return ids_dict
		if data:
			remote_ids = data.get('ids') or {}
			tvdb = remote_ids.get('tvdb') or remote_ids.get('tvdbid') or data.get('tvdb_id')
			if tvdb:
				ids_dict['tvdb'] = str(tvdb)
			if not ids_dict.get('imdb'):
				imdb = remote_ids.get('imdb') or remote_ids.get('imdbid')
				if imdb:
					ids_dict['imdb'] = str(imdb)
	except Exception as e:
		log_utils.log('MDBList resolveShowIds failed: %s' % e, level=log_utils.LOGWARNING)
	return ids_dict


def getTopMovieLists():
	return [l for l in getTopLists() if l.get('mediatype') in ('movie', 'both', '')]


def getTopShowLists():
	return [l for l in getTopLists() if l.get('mediatype') in ('show', 'both', '')]


def getUserListsByName(username):
	if not username:
		return []
	data = _get('/lists/user/%s' % username.strip())
	return data if isinstance(data, list) else []


def getListItemsFromUrl(mdblist_url):
	import re
	mdblist_url = mdblist_url.strip().rstrip('/')
	m = re.search(r'mdblist\.com/lists/([^/]+)/([^/]+)', mdblist_url)
	if not m:
		return [], []
	username, slug = m.group(1), m.group(2)
	list_id = None
	for lst in getUserListsByName(username):
		if lst.get('slug') == slug:
			list_id = lst.get('id')
			break
	if list_id:
		return getListItems(list_id)
	try:
		r = requests.get('https://mdblist.com/lists/%s/%s/json/' % (username, slug), timeout=15)
		r.raise_for_status()
		data = r.json()

		def _b(item):
			return {
				'title': item.get('title', ''),
				'year': str(item.get('release_year') or item.get('year') or ''),
				'imdb': str(item.get('imdb_id') or item.get('imdb') or ''),
				'tmdb': str(item.get('tmdb_id') or item.get('tmdb') or '') if (item.get('tmdb_id') or item.get('tmdb')) else '',
				'tvdb': str(item.get('tvdb_id') or item.get('tvdb') or '') if (item.get('tvdb_id') or item.get('tvdb')) else '',
				'rank': item.get('rank', 9999),
			}

		if isinstance(data, list):
			movies = sorted([_b(i) for i in data if not i.get('tvdb_id')], key=lambda x: x['rank'])
			shows = sorted([_b(i) for i in data if i.get('tvdb_id')], key=lambda x: x['rank'])
			return movies, shows
		movies = sorted([_b(mm) for mm in (data.get('movies') or [])], key=lambda x: x['rank'])
		shows = sorted([_b(s) for s in (data.get('shows') or [])], key=lambda x: x['rank'])
		return movies, shows
	except Exception as exc:
		log_utils.log('getListItemsFromUrl failed: %s' % exc, level=log_utils.LOGWARNING)
		return [], []


# ---------------------------------------------------------------------------
# Context-menu helper (watchlist add/remove)
# ---------------------------------------------------------------------------

def manager(name, imdb, media_type):
	items = [control.lang(40201), control.lang(40202),
			 control.lang(40206), control.lang(40207)]
	select = control.selectDialog(items, control.lang(40200))
	if select == 0:
		ok = addToWatchlist(imdb, media_type)
		control.notification(title='MDBList', message=control.lang(40203) if ok else control.lang(40205))
		control.refresh()
	elif select == 1:
		ok = removeFromWatchlist(imdb, media_type)
		control.notification(title='MDBList', message=control.lang(40204) if ok else control.lang(40205))
		control.refresh()
	elif select in (2, 3):
		_listManager(imdb, media_type, 'add' if select == 2 else 'remove')


def _listResultMessage(ok, action, list_name):
	"""El texto nunca debe decidir el resultado: si una traduccion pierde el %s
    el formateo falla, y antes eso convertia una escritura correcta en un aviso
    de "accion fallida". Se cae al nombre de la lista a secas."""
	if not ok:
		return control.lang(40205)
	try:
		return control.lang(40209 if action == 'add' else 40240) % list_name
	except Exception:
		return list_name


def _listManager(imdb, media_type, action):
	"""Segundo dialogo: elegir en que lista estatica anadir/quitar el titulo."""
	try:
		control.busy()
		try:
			lists = getEditableLists(media_type)
		finally:
			control.hide()
		if not lists:
			# Sin listas estaticas no hay nada que ofrecer: se explica el porque
			# en vez de mostrar un selector vacio.
			control.okDialog(title='MDBList', message=control.lang(40208))
			return
		labels = []
		for l in lists:
			n_items = l.get('items', 0)
			labels.append('%s  [COLOR %s](%s)[/COLOR]' % (l.get('name', '?'),
														  control.getHighlightColor(), n_items))
		choice = control.selectDialog(labels, control.lang(40206 if action == 'add' else 40207))
		if choice < 0:
			return
		target = lists[choice]
		list_id = target.get('id')
		list_name = target.get('name', '?')
		if action == 'add':
			ok = addToList(list_id, imdb, media_type)
		else:
			ok = removeFromList(list_id, imdb, media_type)
		control.notification(title='MDBList',
							 message=_listResultMessage(ok, action, list_name))
		control.refresh()
	except Exception:
		log_utils.error()
		control.notification(title='MDBList', message=control.lang(40205))


# ---------------------------------------------------------------------------
# Auth / account  (validación de key vía GET /user)
# ---------------------------------------------------------------------------

def getUserInfo(apikey=None, token=None):
	"""GET /user. Prioridad: token OAuth explícito (Bearer) > apikey explícita
    (?apikey=) > credencial configurada (su modo correcto). Devuelve dict o
    None. Sirve para validar credenciales y obtener el username.

    `token` permite obtener la identidad con un access_token recién emitido sin
    depender de que la caché de settings ya esté invalidada (evita caer por
    error en otra credencial y traer un username ajeno)."""
	key = (apikey or '').strip()
	tok = (token or '').strip()
	try:
		if tok:
			r = requests.get(BASE_URL + '/user',
							 headers={'Authorization': 'Bearer %s' % tok}, timeout=15)
		elif key:
			r = requests.get(BASE_URL + '/user', params={'apikey': key}, timeout=15)
		else:
			cred, _ = getMDBListCredentials()
			if not cred:
				return None
			headers, auth_params = _auth_headers_params()
			r = requests.get(BASE_URL + '/user', params=auth_params, headers=headers, timeout=15)
		r.raise_for_status()
		return r.json()
	except Exception as e:
		log_utils.log('MDBList getUserInfo failed: %s' % e, level=log_utils.LOGWARNING)
		return None


def validateAndSaveKey(apikey):
	"""Valida una API key contra /user y, si es buena, la guarda + activa
    MDBList + rellena el username. Devuelve (ok, username|mensaje_error)."""
	apikey = (apikey or '').strip()
	if not apikey:
		return False, 'Empty key'
	info = getUserInfo(apikey)
	if not info or not (info.get('username') or info.get('user_id')):
		return False, 'Invalid key'
	username = info.get('username') or str(info.get('user_id'))
	try:
		setSetting('mdblist.apikey', apikey)
		setSetting('mdblist.username', username)
		setSetting('mdblist.enable', 'true')
		try:
			control.homeWindow.clearProperty('luc_kodi_settings')
		except Exception:
			pass
	except Exception:
		log_utils.error()
		return False, 'Could not write settings'
	return True, username


# ---------------------------------------------------------------------------
# OAuth 2.0 Device Flow  (PIN + QR, sin teclado) — igual que Trakt/SIMKL
# ---------------------------------------------------------------------------

_last_device_error = {'msg': ''}


def getDeviceCode():
	"""POST /oauth/device-authorization/ con el client_id. Devuelve el dict
    (user_code, device_code, verification_uri, interval, expires_in) o None.
    Guarda el motivo del fallo en _last_device_error para mostrarlo."""
	_last_device_error['msg'] = ''
	client_id = getClientID()
	if not client_id:
		_last_device_error['msg'] = 'No client_id'
		return None
	try:
		r = requests.post(_OAUTH_DEVICE_URL,
						  data={'client_id': client_id, 'scope': 'write'}, timeout=20)
		if not r.ok:
			body = ''
			try:
				body = r.text[:300]
			except Exception:
				pass
			_last_device_error['msg'] = 'HTTP %s — %s' % (r.status_code, body)
			log_utils.log('MDBList device-auth HTTP %s: %s' % (r.status_code, body),
						  level=log_utils.LOGWARNING)
			return None
		try:
			return r.json()
		except Exception as e:
			_last_device_error['msg'] = 'Bad JSON: %s' % e
			return None
	except Exception as e:
		_last_device_error['msg'] = 'Network error: %s' % e
		log_utils.log('MDBList getDeviceCode failed: %s' % e, level=log_utils.LOGWARNING)
		return None


def _device_verify_url(device_data):
	base = (device_data.get('verification_uri') or device_data.get('verification_url')
			or _OAUTH_VERIFY_URL).rstrip('/')
	user_code = device_data.get('user_code', '')
	if user_code:
		return '%s?code=%s' % (base, user_code)
	return base


def pollDeviceToken(device_data):
	"""Muestra PIN + QR en un diálogo de progreso y hace polling a
    /oauth/token/ hasta recibir access_token, expiración o cancelación.
    Devuelve el dict del token o None."""
	device_code = device_data.get('device_code')
	user_code = device_data.get('user_code')
	if not device_code or not user_code:
		return None
	client_id = getClientID()
	expires_in = int(device_data.get('expires_in') or 300)
	interval = max(int(device_data.get('interval') or 5), 1)
	verify_base = (device_data.get('verification_uri') or device_data.get('verification_url')
				   or _OAUTH_VERIFY_URL).replace('https://', '').replace('http://', '').rstrip('/')
	verify_full = _device_verify_url(device_data)

	# QR (mismo proveedor que SIMKL/Trakt en este addon) + clipboard.
	qr_icon = ''
	try:
		from urllib.parse import quote_plus
	except ImportError:
		from urllib import quote_plus
	try:
		qr_icon = ('https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&data='
				   + quote_plus(verify_full))
	except Exception:
		qr_icon = ''
	try:
		from resources.lib.modules.source_utils import copy2clip
		copy2clip(verify_full)
	except Exception:
		pass

	try:
		control.notification(title='MDBList', message='%s  |  %s' % (verify_base, user_code),
							 icon=qr_icon, time=15000)
	except Exception:
		pass

	progressDialog = control.progressDialog
	progressDialog.create('MDBList authorization')
	line = ('[B]Visit:[/B] %s\n[B]Enter code:[/B] %s\n'
			'OR scan the QR  ·  link copied to clipboard\n\nWaiting for authorization...'
			% (verify_base, user_code))
	try:
		progressDialog.update(100, line)
	except Exception:
		pass

	time_passed = expires_in
	token_resp = None
	while True:
		if progressDialog.iscanceled():
			break
		if time_passed <= 0:
			try: progressDialog.close()
			except Exception: pass
			control.notification(title='MDBList', message='Code expired, please try again.')
			return None
		control.sleep(1000)
		time_passed -= 1
		try:
			progressDialog.update(int((expires_in - time_passed) / float(expires_in) * 100))
		except Exception:
			pass
		# Poll cada `interval` segundos.
		if (expires_in - time_passed) % interval != 0:
			continue
		try:
			r = requests.post(_OAUTH_TOKEN_URL, data={
				'grant_type': _OAUTH_GRANT_DEVICE,
				'device_code': device_code,
				'client_id': client_id}, timeout=20)
			if r.status_code == 200:
				token_resp = r.json()
				break
			# 400/428 = authorization_pending / slow_down → seguir.
		except Exception:
			pass

	try: progressDialog.close()
	except Exception: pass
	return token_resp


def authenticate():
	"""Flujo completo Device: pide código, muestra PIN+QR, espera token y lo
    guarda. Rellena username vía /user (Bearer). Devuelve True/False."""
	if not getClientID():
		control.dialog.ok('MDBList',
			'Missing [B]client_id[/B].\n\nRegister your app at [B]mdblist.com[/B] '
			'(Preferences > API Access), paste the client_id under Settings > MDBList > '
			'Client ID, and try again.')
		return False
	device_data = getDeviceCode()
	if not device_data or not device_data.get('user_code'):
		reason = _last_device_error.get('msg') or 'unknown'
		control.dialog.ok('MDBList — could not start',
			'Could not get the authorization code.\n\n[B]Reason:[/B] %s\n\n'
			'Endpoint: %s' % (reason, _OAUTH_DEVICE_URL))
		return False
	token_result = pollDeviceToken(device_data)
	if not token_result:
		control.notification(title='MDBList', message='Authorization canceled.')
		return False
	access_token = token_result.get('access_token')
	if not access_token:
		control.notification(title='MDBList', message='Authorization failed.')
		return False
	try:
		setSetting('mdblist.token', access_token)
		setSetting('mdblist.refresh', token_result.get('refresh_token') or '0')
		setSetting('mdblist.enable', 'true')
	except Exception:
		log_utils.error()
		return False
	info = getUserInfo(token=access_token) or {}
	username = info.get('username') or str(info.get('user_id') or 'MDBList User')
	try:
		setSetting('mdblist.username', username)
		control.homeWindow.clearProperty('luc_kodi_settings')
	except Exception:
		pass
	invalidateSectionCaches(account_change=True)
	control.notification(title='MDBList', message='Account authorized: %s' % username)
	return True


def auth():
	"""Autorización por OAuth Device Flow (PIN + QR). Único método."""
	authenticate()


def deauth():
	"""Borra token OAuth + key del usuario, username y desactiva MDBList.
    Sin credencial propia, MDBList queda inactivo (no hay key por defecto)."""
	try:
		setSetting('mdblist.token', '')
		setSetting('mdblist.refresh', '')
		setSetting('mdblist.apikey', '')
		setSetting('mdblist.username', '')
		setSetting('mdblist.enable', 'false')
		setSetting('mdblist.scrobble', 'false')
		try:
			control.homeWindow.clearProperty('luc_kodi_settings')
		except Exception:
			pass
		invalidateSectionCaches(account_change=True)
		control.notification(title='MDBList', message='Deauthorized')
	except Exception:
		log_utils.error()


def account_info_to_dialog():
	"""Muestra perfil + límites + contador de peticiones de la credencial activa."""
	info = getUserInfo()
	if not info:
		control.dialog.ok('MDBList', 'Could not fetch account info. Authorize first (PIN + QR).')
		return
	using_default = usingDefaultKey()
	limits = info.get('limits') or {}
	auth_mode = 'OAuth (Bearer)' if oauthActive() else info.get('auth_method', 'apikey')
	lines = (
		'[B]User:[/B] %s\n'
		'[B]Plan:[/B] %s\n'
		'[B]Requests:[/B] %s / %s   (remaining: %s)\n'
		'[B]Lists:[/B] %s   [B]List items:[/B] %s\n'
		'[B]Auth method:[/B] %s\n'
		'[B]Credential:[/B] %s'
	) % (
		info.get('username', '?'),
		info.get('plan', '?'),
		info.get('api_requests_count', '?'), info.get('api_requests', '?'),
		info.get('rate_limit_remaining', '?'),
		limits.get('lists', '?'), limits.get('lists_items', '?'),
		auth_mode,
		'plugin default (authorize with PIN + QR)' if using_default else 'your own account',
	)
	control.dialog.ok('MDBList account', lines)


# ---------------------------------------------------------------------------
# Listas EXTERNAS  (GET /external/lists/user, /external/lists/{id}[/items])
# ---------------------------------------------------------------------------
# MDBList distingue dos cosas que la web presenta juntas:
#   - "My Lists"      -> /lists/user           (ya implementado: getUserLists)
#   - "External Lists"-> /external/lists/user  (esto)
# Las externas son listas IMPORTADAS de fuera: Trakt, IMDb, Letterboxd...
# NO confundirlas con las "Liked Lists" (listas AJENAS marcadas con like), que
# tienen su propio endpoint /lists/liked y viven en la seccion de mas abajo.

def getExternalLists():
	"""Listas externas (Trakt/IMDb/Letterboxd...) del usuario autenticado."""
	data = _get('/external/lists/user')
	return data if isinstance(data, list) else []


def getExternalListInfo(list_id):
	data = _get('/external/lists/%s' % list_id)
	if isinstance(data, list):
		return data[0] if data else {}
	return data if isinstance(data, dict) else {}


def getExternalListItems(list_id, media_type=None):
	"""Items de una lista externa. Misma forma de respuesta que /lists/{id}/items,
	asi que se reutilizan _build_movie/_build_show y el mismo criterio de reparto."""
	data = _get_all_pages_dict('/external/lists/%s/items' % list_id)
	if not data:
		return [], []
	movies = sorted([_build_movie(m) for m in (data.get('movies') or [])], key=lambda x: x['rank'])
	shows = sorted([_build_show(s) for s in (data.get('shows') or [])], key=lambda x: x['rank'])
	if media_type == 'show' and not shows:
		sfm = [_build_show(m) for m in (data.get('movies') or [])
			   if str(m.get('mediatype', '')).lower() in ('show', 'tv', 'tvshow', 'series')]
		if sfm:
			shows = sorted(sfm, key=lambda x: x['rank'])
	if media_type == 'movie':
		return movies, []
	if media_type == 'show':
		return [], shows
	return movies, shows


def getExternalMovieLists():
	return [l for l in getExternalLists() if (l.get('movies') or 0) > 0]


def getExternalShowLists():
	return [l for l in getExternalLists() if (l.get('shows') or 0) > 0]


# ---------------------------------------------------------------------------
# Liked Lists  (GET /lists/liked)
# ---------------------------------------------------------------------------
# Listas de OTROS usuarios que el usuario ha marcado con "like" en la web
# (mdblist.com/likedlists/). Endpoint real pero SIN documentar: no aparece ni
# en el OpenAPI ni en el apiary, igual que /calendar/events. Hasta v1.0.68 este
# modulo daba por hecho que no existia porque no estaba en el spec.
#
# Los CONTENIDOS se leen con el endpoint normal /lists/{id}/items, no con el de
# listas externas, asi que getListItems() vale tal cual y no hace falta una
# accion propia para los items.

_LIST_WRAPPER_KEYS = ('items', 'lists', 'liked', 'data', 'results')


def _expand_list_ids(lists):
	"""Normaliza filas de catalogo y expande las que traen `ids` en vez de `id`.

	Las listas "unified" de MDBList (una sola lista con peliculas y series)
	responden un ARRAY `ids` y ningun `id`. Sin expandirlas, la fila pasa el
	bucle del menu, se pinta con normalidad y construye una URL con list_id
	vacio: la entrada aparece y al abrirla no trae nada, SIN error en el log."""
	out = []
	for it in lists or []:
		if not isinstance(it, dict):
			continue
		list_id = it.get('id')
		if list_id not in (None, '', 0, '0'):
			out.append(it)
			continue
		ids = it.get('ids')
		if not isinstance(ids, (list, tuple)):
			continue
		for lid in ids:
			if lid in (None, '', 0, '0'):
				continue
			row = dict(it)
			row['id'] = lid
			out.append(row)
	return out


def _list_matches_media_type(lst, media_type):
	"""Reparto de una lista entre los menus de Peliculas y Series.

	PERMISIVO a proposito: las listas ajenas a menudo no declaran `mediatype`,
	y un filtro estricto las esconderia en los dos menus a la vez, que es
	justo el fallo que se quiere evitar. Sin mediatype se miran los contadores;
	sin contadores, se muestra."""
	if not media_type:
		return True
	try:
		mt = str(lst.get('mediatype') or lst.get('media_type') or '').lower()
		if mt and mt not in ('any', 'mixed', 'both'):
			want = ('show', 'shows', 'tv', 'tvshow', 'series') if media_type == 'show' else ('movie', 'movies')
			return mt in want
		mine = lst.get('shows' if media_type == 'show' else 'movies')
		other = lst.get('movies' if media_type == 'show' else 'shows')
		if isinstance(mine, int) or isinstance(other, int):
			# Solo se descarta cuando la lista declara 0 de lo mio y algo de lo otro.
			return bool(mine) or not bool(other)
		return True
	except Exception:
		return True


def getLikedLists():
	"""Catalogo plano de listas marcadas con like. Sin filtrar por tipo."""
	data = _get('/lists/liked')
	if data is None:
		return []
	lists = _expand_list_ids(_unwrap_list(data, _LIST_WRAPPER_KEYS))
	if not lists and data:
		_log_shape('likedLists', data)
	else:
		_hard_log('likedLists: %d listas' % len(lists))
	return lists


def getLikedMovieLists():
	return [l for l in getLikedLists() if _list_matches_media_type(l, 'movie')]


def getLikedShowLists():
	return [l for l in getLikedLists() if _list_matches_media_type(l, 'show')]


# ---------------------------------------------------------------------------
# Last activities  (GET /sync/last_activities)
# ---------------------------------------------------------------------------
# El mismo patron que ya usa Trakt en este plugin: una sola peticion barata
# devuelve las marcas de tiempo de cada seccion, y solo se sincroniza lo que
# haya cambiado. Con el limite de 1000 peticiones/dia de la cuenta gratuita
# esto es la diferencia entre gastarlas y no gastarlas.

_ACTIVITY_KEYS = ('watchlisted_at', 'watched_at', 'season_watched_at', 'episode_watched_at',
				  'rated_at', 'collected_at', 'dropped_at', 'paused_at',
				  'episode_paused_at', 'list_updated_at')


def getLastActivities():
	"""Dict de marcas de tiempo por seccion, o {} si falla."""
	data = _get('/sync/last_activities')
	return data if isinstance(data, dict) else {}


def activityChanged(key, stored_value):
	"""True si la seccion `key` cambio respecto a `stored_value`.

	Ante cualquier duda devuelve True: perder una sincronizacion es peor que
	gastar una peticion de mas, y si la API no responde no se puede afirmar
	que no haya cambios."""
	if key not in _ACTIVITY_KEYS:
		return True
	acts = getLastActivities()
	if not acts:
		return True
	current = acts.get(key)
	if not current:
		return True
	return str(current) != str(stored_value or '')


# ---------------------------------------------------------------------------
# Sync de valoraciones  (GET/POST /sync/ratings, POST /sync/ratings/remove)
# ---------------------------------------------------------------------------

def getRatings(media_type=None, since=None):
	"""Valoraciones del usuario. Devuelve el dict crudo con movies/shows/seasons/episodes.
	`since` acepta una marca ISO para traer solo lo posterior."""
	params = {}
	if since:
		params['since'] = since
	data = _get('/sync/ratings', params=params or None)
	if not isinstance(data, dict):
		return {}
	if media_type in ('movie', 'movies'):
		return {'movies': data.get('movies') or []}
	if media_type in ('show', 'shows'):
		return {'shows': data.get('shows') or []}
	return data


def _rating_ids(imdb=None, tmdb=None, tvdb=None):
	ids = {}
	if imdb:
		ids['imdb'] = str(imdb)
	if tmdb:
		try: ids['tmdb'] = int(tmdb)
		except Exception: pass
	if tvdb:
		try: ids['tvdb'] = int(tvdb)
		except Exception: pass
	return ids


def addRating(rating, imdb=None, tmdb=None, tvdb=None, media_type='movie',
			  season=None, episode=None):
	"""Envia una valoracion (1-10). Para episodio/temporada se anida bajo el show,
	que es la forma que exige el endpoint."""
	try:
		rating = int(rating)
	except Exception:
		return False
	if not 1 <= rating <= 10:
		return False
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	if media_type in ('movie', 'movies'):
		payload = {'movies': [{'ids': ids, 'rating': rating}]}
	else:
		entry = {'ids': ids}
		if season is not None and episode is not None:
			entry['seasons'] = [{'number': int(season),
								 'episodes': [{'number': int(episode), 'rating': rating}]}]
		elif season is not None:
			entry['seasons'] = [{'number': int(season), 'rating': rating}]
		else:
			entry['rating'] = rating
		payload = {'shows': [entry]}
	data = _post('/sync/ratings', json_data=payload)
	return isinstance(data, dict) and bool(data.get('updated'))


def removeRating(imdb=None, tmdb=None, tvdb=None, media_type='movie',
				 season=None, episode=None):
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	if media_type in ('movie', 'movies'):
		payload = {'movies': [{'ids': ids}]}
	else:
		entry = {'ids': ids}
		if season is not None and episode is not None:
			entry['seasons'] = [{'number': int(season),
								 'episodes': [{'number': int(episode)}]}]
		elif season is not None:
			entry['seasons'] = [{'number': int(season)}]
		payload = {'shows': [entry]}
	return _post('/sync/ratings/remove', json_data=payload) is not None


# ---------------------------------------------------------------------------
# Sync de coleccion  (GET/POST /sync/collection, POST /sync/collection/remove)
# ---------------------------------------------------------------------------

def getCollection(media_type=None, since=None):
	params = {}
	if since:
		params['since'] = since
	data = _get('/sync/collection', params=params or None)
	if not isinstance(data, dict):
		return {'movies': [], 'shows': []}
	out = {'movies': data.get('movies') or [], 'shows': data.get('shows') or []}
	if media_type in ('movie', 'movies'):
		return {'movies': out['movies'], 'shows': []}
	if media_type in ('show', 'shows'):
		return {'movies': [], 'shows': out['shows']}
	return out


def addToCollection(imdb=None, tmdb=None, tvdb=None, media_type='movie'):
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	key = 'movies' if media_type in ('movie', 'movies') else 'shows'
	return _post('/sync/collection', json_data={key: [{'ids': ids}]}) is not None


def removeFromCollection(imdb=None, tmdb=None, tvdb=None, media_type='movie'):
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	key = 'movies' if media_type in ('movie', 'movies') else 'shows'
	return _post('/sync/collection/remove', json_data={key: [{'ids': ids}]}) is not None


# ---------------------------------------------------------------------------
# Series abandonadas  (GET/POST /sync/dropped, POST /sync/dropped/remove)
# ---------------------------------------------------------------------------
# Utilidad concreta: una serie marcada como abandonada NO deberia seguir
# apareciendo en Up Next ni en el progreso. Con esto se puede filtrar.

def getDroppedShows(since=None):
	params = {}
	if since:
		params['since'] = since
	data = _get('/sync/dropped', params=params or None)
	if not isinstance(data, dict):
		return []
	return data.get('shows') or []


def getDroppedImdbIds():
	"""Set de IMDb ids abandonados, listo para filtrar Up Next / progreso."""
	out = set()
	for entry in getDroppedShows():
		show = entry.get('show') or {}
		imdb = (show.get('ids') or {}).get('imdb')
		if imdb:
			out.add(str(imdb))
	return out


def addDroppedShow(imdb=None, tmdb=None, tvdb=None):
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	return _post('/sync/dropped', json_data={'shows': [{'ids': ids}]}) is not None


def removeDroppedShow(imdb=None, tmdb=None, tvdb=None):
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	return _post('/sync/dropped/remove', json_data={'shows': [{'ids': ids}]}) is not None


# ---------------------------------------------------------------------------
# Borrado de historial  (POST /sync/watched/remove)
# ---------------------------------------------------------------------------
# Faltaba la contraparte de addWatched(): se podia marcar como visto pero no
# desmarcar, asi que un scrobble erroneo no habia forma de deshacerlo.

def removeWatched(imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
	ids = _rating_ids(imdb, tmdb, tvdb)
	if not ids:
		return False
	if season is not None and episode is not None:
		payload = {'shows': [{'ids': ids, 'seasons': [
			{'number': int(season), 'episodes': [{'number': int(episode)}]}]}]}
	elif tvdb or season is not None:
		payload = {'shows': [{'ids': ids}]}
	else:
		payload = {'movies': [{'ids': ids}]}
	return _post('/sync/watched/remove', json_data=payload) is not None


# ---------------------------------------------------------------------------
# Busqueda de medios y generos  (GET /search/{media_type}, GET /genres)
# ---------------------------------------------------------------------------
# Hasta ahora solo se buscaban LISTAS (searchLists). Esto busca titulos.

def searchMedia(query, media_type='any', year=None, limit=50):
	if not query:
		return []
	if media_type in ('movies',):
		media_type = 'movie'
	elif media_type in ('shows', 'tvshow', 'tv'):
		media_type = 'show'
	elif media_type not in ('movie', 'show', 'any'):
		media_type = 'any'
	params = {'query': query, 'limit': limit}
	if year:
		params['year'] = year
	data = _get('/search/%s' % media_type, params=params)
	return _unwrap_list(data, ('search', 'results', 'items')) or []


def _search_to_item(r):
	ids = r.get('ids') or {}
	return {
		'title': r.get('title', ''),
		'year': str(r.get('year') or ''),
		'imdb': str(ids.get('imdbid') or ''),
		'tmdb': str(ids.get('tmdbid') or '') if ids.get('tmdbid') else '',
		'tvdb': str(ids.get('tvdbid') or '') if ids.get('tvdbid') else '',
		'rank': 9999,
	}


def searchMovies(query, year=None, limit=50):
	return [_search_to_item(r) for r in searchMedia(query, 'movie', year, limit)
			if str(r.get('type', 'movie')).lower() == 'movie']


def searchShows(query, year=None, limit=50):
	return [_search_to_item(r) for r in searchMedia(query, 'show', year, limit)
			if str(r.get('type', 'show')).lower() in ('show', 'tv', 'series')]


def getGenres(anime=False):
	data = _get('/genres', params={'anime': 1 if anime else 0})
	return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Cambios incrementales de una lista  (GET /lists/{id}/changes)
# ---------------------------------------------------------------------------

def getListChanges(list_id):
	"""Trakt ids anadidos/eliminados desde la ultima actualizacion de la lista.
	Permite refrescar una lista grande sin volver a descargarla entera."""
	data = _get('/lists/%s/changes' % list_id)
	if not isinstance(data, dict):
		return {'added': [], 'removed': [], 'updated': ''}
	added, removed = [], []
	for key in ('movie', 'show', 'movies', 'shows'):
		block = data.get(key) or {}
		tids = block.get('trakt_ids') or {}
		added.extend(tids.get('added') or [])
		removed.extend(tids.get('removed') or [])
	return {'added': added, 'removed': removed, 'updated': data.get('updated', '')}
