# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from resources.lib.modules import app_keys
from datetime import datetime, timezone
from json import dumps as jsdumps, loads as jsloads
import re
import requests
from requests.adapters import HTTPAdapter
from threading import Thread, Lock
from time import time
from urllib3.util.retry import Retry
from urllib.parse import urljoin, quote_plus
from resources.lib.database import cache, traktsync
from resources.lib.modules import cleandate
from resources.lib.modules import control
from resources.lib.modules import log_utils

getLS = control.lang
getSetting = control.setting
setSetting = control.setSetting
BASE_URL = 'https://api.trakt.tv'

def _app_credentials():
	# v1.0.95: trakt.client_id / trakt.client_secret estaban declarados en
	# settings.xml pero nadie los leia. Override solo si vienen LOS DOS: un id
	# propio con el secreto del plugin (o al reves) no autoriza nada.
	try:
		cid, csec = (getSetting('trakt.client_id') or '').strip(), (getSetting('trakt.client_secret') or '').strip()
		if cid and csec: return cid, csec
	except: pass
	return app_keys.get('trakt_id'), app_keys.get('trakt_secret')

def _user_agent():
	# Trakt (anuncio del 1-dic-2025) pide un User-Agent que identifique la app y
	# su version, y puede bloquear peticiones sin el. requests mandaba el suyo.
	try: return 'luc_kodi/%s (Kodi)' % control.addonInfo('version')
	except: return 'luc_kodi (Kodi)'

V2_API_KEY, CLIENT_SECRET = _app_credentials()
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
USER_AGENT = _user_agent()
headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2', 'User-Agent': USER_AGENT}
session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})
retries = Retry(total=4, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 524, 530])
session.mount('https://api.trakt.tv', HTTPAdapter(max_retries=retries, pool_maxsize=100))
highlight_color = control.getHighlightColor()
server_notification = getSetting('trakt.server.notifications') == 'true'
service_syncInterval = int(getSetting('trakt.service.syncInterval')) if getSetting('trakt.service.syncInterval') else 15

# 2026-08 OAuth hardening.
# Trakt rota el refresh_token en cada renovacion: el token viejo queda invalido
# de inmediato. Con N hilos golpeando la API a la vez, dos 401 simultaneos
# lanzaban dos refresh con el MISMO refresh_token -> el segundo devuelve
# invalid_grant -> la cuenta queda desautorizada. Desde el limite de "1 Community
# App" en cuentas gratuitas (Trakt, 22-07-2026) reconectar ya no es trivial:
# una desautorizacion accidental puede dejar al usuario sin poder volver a
# vincular. De ahi el single-flight + el refresco proactivo.
_refresh_lock = Lock()
# v1.0.95: desde el 20-mar-2025 el access_token de Trakt caduca a las 24 h (antes
# 3 meses) y la respuesta trae expires_in. El addon guardaba siempre ahora+90 dias,
# asi que el refresco proactivo no llegaba nunca y cada dia se vivia del 401. Ahora
# la caducidad sale de expires_in y se renueva cuando quedan menos de 3 h. Con el
# margen viejo de 14 dias y tokens de 24 h se habria renovado en CADA peticion.
_REFRESH_MARGIN = 10800 # 3 h
_DEFAULT_TOKEN_TTL = 86400 # si la respuesta no trae expires_in
_MIN_REFRESH_GAP = 1800 # nunca dos refrescos proactivos en menos de 30 min
_PROP_LAST_REFRESH = 'luc_kodi.trakt.last_refresh'

def _token_expiry(token_response):
	# Caducidad en reloj LOCAL (ahora + expires_in): se compara con time() del
	# aparato, asi que usar created_at del servidor meteria el desfase de reloj.
	try: ttl = int((token_response or {}).get('expires_in') or 0)
	except: ttl = 0
	if ttl <= 0: ttl = _DEFAULT_TOKEN_TTL
	return str(time() + ttl)

# --- Anti-spam de "Please Re-Authorize" -------------------------------------
# Cuando el refresh_token muere (invalid_grant: dispositivo desvinculado por
# inactividad, limite de dispositivos, etc.) CADA llamada a Trakt devuelve 401
# y cada hilo (navegador + service + widgets) reintentaba el refresh y lanzaba
# su propia notificacion 33677 -> rafaga de notificaciones identicas en bucle.
# Solucion: marcar el refresh como "muerto" en una window property (compartida
# entre el invoker del plugin y el service) y:
#   1) no reintentar el refresh durante _DEAD_RETRY_SECS (evita martillear el
#      endpoint /oauth/token con un token ya quemado), y
#   2) mostrar la notificacion como mucho una vez por _NOTICE_EVERY_SECS.
# La marca se limpia sola al primer refresh valido o al reautorizar en auth().
_PROP_REFRESH_DEAD = 'luc_kodi.trakt.refresh_dead'
_PROP_REAUTH_NOTICE = 'luc_kodi.trakt.reauth_notice'
_DEAD_RETRY_SECS = 300    # 5 min entre reintentos de refresh con token muerto
_NOTICE_EVERY_SECS = 3600 # 1 h entre notificaciones de re-autorizacion

def _prop_age(prop):
	# Segundos desde que se escribio la property; None si no existe.
	try:
		val = control.homeWindow.getProperty(prop)
		if not val: return None
		return time() - float(val)
	except: return None

def _refresh_is_dead():
	age = _prop_age(_PROP_REFRESH_DEAD)
	return age is not None and age < _DEAD_RETRY_SECS

def _mark_refresh_dead():
	try:
		control.homeWindow.setProperty(_PROP_REFRESH_DEAD, str(time()))
		age = _prop_age(_PROP_REAUTH_NOTICE)
		if age is None or age >= _NOTICE_EVERY_SECS:
			control.homeWindow.setProperty(_PROP_REAUTH_NOTICE, str(time()))
			control.notification(title=32315, message=33677)
	except: log_utils.error('_mark_refresh_dead Error: ')

def clear_refresh_dead():
	try:
		control.homeWindow.clearProperty(_PROP_REFRESH_DEAD)
		control.homeWindow.clearProperty(_PROP_REAUTH_NOTICE)
	except: pass


# --- Diagnostico incondicional del scrobble ---------------------------------
# v1.0.79. Todo el camino de Trakt registraba, como mucho, un LOGDEBUG a traves
# de log_utils.log(), que aborta en su primera linea cuando debug.enabled esta
# apagado -- el caso de casi cualquier instalacion. Resultado: en un kodi.log
# normal no habia forma de saber si el scrobble llego a enviarse, ni con que
# codigo respondio Trakt. Es la misma ceguera que costo cinco versiones con
# MDBList, y se resuelve igual: xbmc.log directo con etiqueta propia.
_LOG_TAG = '[luc_kodi-trakt]'

def _hard_log(msg, level=1): # 1=LOGINFO, 3=LOGERROR
	try: control.log('%s %s' % (_LOG_TAG, msg), level)
	except Exception: pass


def getTrakt(url, post=None, extended=False, silent=False):
	try:
		if not url.startswith(BASE_URL): url = urljoin(BASE_URL, url)
		if post: post = jsdumps(post)
		used_token = ''
		if getTraktCredentialsInfo():
			ensure_token() # refresco proactivo (single-flight) si esta a punto de caducar
			used_token = getSetting('trakt.token')
			headers['Authorization'] = 'Bearer %s' % used_token # compat: hay llamadas que usan el dict global
		# Copia local: el dict global lo mutan otros hilos, y sin esto una peticion
		# podia salir firmada con el token de otro hilo justo tras una renovacion.
		req_headers = dict(headers)

		if post: response = session.post(url, data=post, headers=req_headers, timeout=20)
		else: response = session.get(url, headers=req_headers, timeout=20)
		status_code = str(response.status_code)

		# if status_code.startswith('5') or '<html' in response: # temp to log html maintenance response
		# 	log_utils.log('status_code=%s' % status_code, __name__)
		# 	log_utils.log('response.headers=%s' % str(response.headers), __name__)
		# 	log_utils.log('response=%s' % response, __name__)
		# 	log_utils.log('response.text=%s' % str(response.text), __name__)
		# 	log_utils.log('response.content=%s' % str(response.content), __name__)

		error_handler(url, response, status_code, silent=silent)

		if response and status_code in ('200', '201'):
			if extended: return response, response.headers
			else: return response
		elif status_code == '401': # Re-Auth token
			# stale_token: si otro hilo ya renovo mientras esperabamos el lock,
			# refresh_token() no vuelve a quemar el refresh_token rotado.
			success = refresh_token(stale_token=used_token)
			# El 'post' ya viene serializado aqui; reenviarlo tal cual haria un
			# doble jsdumps en la llamada recursiva -> lo pasamos deserializado.
			if success: return getTrakt(url, post=jsloads(post) if post else None, extended=extended, silent=silent)
		elif status_code == '429':
			# 2026 Trakt API rate limits: GET 1000 req/5min, POST/PUT/DELETE 1/sec.
			# Replaced unbounded recursion with bounded loop (max 3 reintentos) to
			# avoid RecursionError when many threads hit 429 in parallel.
			if 'Retry-After' in response.headers:
				throttleTime = int(response.headers.get('Retry-After', 60))
				if not silent and server_notification and not control.condVisibility('Player.HasVideo'):
					control.notification(title=32315, message='Trakt Throttling Applied, Sleeping for %s seconds' % throttleTime)
				control.sleep((throttleTime + 1) * 1000)
				for _ in range(3):
					try:
						if post: response = session.post(url, data=post, headers=req_headers, timeout=20)
						else: response = session.get(url, headers=req_headers, timeout=20)
					except: return None
					status_code = str(response.status_code)
					if status_code in ('200', '201'):
						if extended: return response, response.headers
						else: return response
					if status_code != '429': break
					ra = int(response.headers.get('Retry-After', 60))
					control.sleep((ra + 1) * 1000)
				return None
		elif status_code == '410':
			# Device-code flow: code expired (used during oauth/device/token polling).
			log_utils.log('Trakt device code expired (410): %s' % url, level=log_utils.LOGDEBUG)
			return None
		elif status_code == '418':
			# Device-code flow: user explicitly denied authorization.
			log_utils.log('Trakt device authorization denied by user (418): %s' % url, level=log_utils.LOGDEBUG)
			return None
		elif status_code == '420':
			# 2026 VIP Enhanced API: user exceeded account limit (lists, watchlist, ratings, etc.)
			# Trakt returns X-Upgrade-URL pointing the user to the VIP signup page.
			upgrade_url = response.headers.get('X-Upgrade-URL', '')
			log_utils.log('Trakt 420 account limit exceeded: URL=%s X-Upgrade-URL=%s' % (url, upgrade_url), level=log_utils.LOGWARNING)
			if not silent and server_notification:
				msg = 'Trakt account limit exceeded'
				if upgrade_url: msg += ' (VIP upgrade: %s)' % upgrade_url
				control.notification(title=32315, message=msg)
			return None
		else: return None
	except: log_utils.error('getTrakt Error: ')
	return None

def error_handler(url, response, status_code, silent=False):
	if status_code.startswith('5') or (response and isinstance(response, str) and '<html' in response) or not str(response): # covers Maintenance html responses ["Bad Gateway", "We're sorry, but something went wrong (500)"])
		log_utils.log('Temporary Trakt Server Problem: %s:%s' % (status_code, response), level=log_utils.LOGINFO)
		if (not silent) and server_notification: control.notification(title=32315, message=33676)
	elif status_code == '423':
		log_utils.log('Locked User Account - Contact Trakt Support: %s' % str(response.text), level=log_utils.LOGWARNING)
		if (not silent) and server_notification: control.notification(title=32315, message=33675)
	elif status_code == '404':
		log_utils.log('getTrakt() (404:NOT FOUND): URL=(%s): %s' % (url, str(response.text)), level=log_utils.LOGWARNING)

def getTraktAsJson(url, post=None, silent=False):
	try:
		res_headers = {}
		r = getTrakt(url=url, post=post, extended=True, silent=silent)
		if isinstance(r, tuple) and len(r) == 2: r, res_headers = r[0], r[1]
		if not r: return
		r = r.json()
		if 'X-Sort-By' in res_headers and 'X-Sort-How' in res_headers:
			r = sort_list(res_headers['X-Sort-By'], res_headers['X-Sort-How'], r)
		return r
	except: log_utils.error()

def _authed_status(method, path):
	"""Peticion autenticada que solo necesita el codigo HTTP (me gusta a listas,
	borrar un punto de resume). v1.0.95: antes firmaban con el dict global de
	cabeceras sin pasar por ensure_token() ni reintentar tras un 401, asi que con
	el token caducado (cada 24 h) fallaban en silencio."""
	try:
		if not path.startswith(BASE_URL): path = urljoin(BASE_URL, path)
		ensure_token()
		used = getSetting('trakt.token')
		req_headers = dict(headers)
		req_headers['Authorization'] = 'Bearer %s' % used
		r = session.request(method, path, headers=req_headers, timeout=20)
		if r.status_code == 401 and refresh_token(stale_token=used):
			req_headers['Authorization'] = 'Bearer %s' % getSetting('trakt.token')
			r = session.request(method, path, headers=req_headers, timeout=20)
		return r.status_code
	except Exception as exc:
		_hard_log('%s %s FAILED: %s: %s' % (method, path, type(exc).__name__, exc), 3)
		return 0

def getTraktAsJsonPaginated(url, page_size=250, max_pages=40, silent=False, apply_sort=False):
	# 2026 Trakt API: pagination is mandatory on collection, list items and, as of
	# June 30 2026, also on /users/{u}/watched/{type} and /sync/watched/{type}.
	# Max page size is now 250 and Trakt warns the APPLIED limit may be lower than
	# the REQUESTED limit (especially with extended=progress). So we must NOT stop
	# when len(items) < page_size. Robust stop logic per Trakt's guidance:
	#   1. use the X-Pagination-Page-Count header when present
	#   2. otherwise keep looping until an empty [] page
	#   3. if no pagination headers at all -> endpoint is unpaginated, single shot
	# NOTE: this module shadows the builtin `list` with a function at the bottom
	# (def list(id)), so we grab the real type via builtins.
	import builtins
	_list_type = builtins.list
	if page_size > 250: page_size = 250 # 2026 hard cap
	all_items = []
	page = 1
	prev_first = None
	first_headers = None
	sep = '&' if '?' in url else '?'
	while page <= max_pages:
		paged_url = '%s%slimit=%d&page=%d' % (url, sep, page_size, page)
		res_headers = {}
		try:
			r = getTrakt(url=paged_url, extended=True, silent=silent)
			if isinstance(r, tuple) and len(r) == 2: r, res_headers = r[0], r[1]
			if not r:
				return None # request failed: signal error, do NOT persist partial data
			items = r.json()
		except:
			log_utils.error()
			return None # failure mid-pagination: better no data than partial data wiping the db
		if not isinstance(items, _list_type): return None
		if first_headers is None: first_headers = res_headers or {}
		if not items: break # empty [] page = past the last page
		# defensa contra APIs que devuelven la ULTIMA pagina repetida al pedir
		# page > page_count: si la pagina empieza igual que la anterior, hemos
		# terminado (evita crawls descontrolados que agotan el rate limit)
		cur_first = repr(items[0])[:512]
		if cur_first == prev_first: break
		prev_first = cur_first
		all_items.extend(items)
		page_count = res_headers.get('X-Pagination-Page-Count')
		item_count = res_headers.get('X-Pagination-Item-Count')
		if page_count:
			try:
				if page >= int(page_count): break
			except: pass
		elif item_count:
			try:
				if len(all_items) >= int(item_count): break
			except: pass
		elif 'X-Pagination-Page' not in res_headers:
			break # endpoint not paginated, first response is everything
		page += 1
	# v1.0.95: getTraktAsJson ordenaba una lista segun X-Sort-By/X-Sort-How (el
	# orden que el dueno eligio en trakt.tv) y este helper no, asi que al paginar
	# las listas se perdia ese orden. Si Trakt ya las devuelve ordenadas lo dice
	# con X-Applied-Sort-By y no se toca nada.
	if apply_sort and all_items and first_headers:
		try:
			if 'X-Applied-Sort-By' not in first_headers and 'X-Sort-By' in first_headers and 'X-Sort-How' in first_headers:
				sorted_items = sort_list(first_headers['X-Sort-By'], first_headers['X-Sort-How'], all_items)
				if sorted_items: all_items = sorted_items
		except: pass
	return all_items

def _token_expiring_soon():
	# True si falta menos de _REFRESH_MARGIN para caducar (o si no hay fecha).
	try:
		expires = getSetting('trakt.expires')
		if not expires: return False
		return (float(expires) - time()) < _REFRESH_MARGIN
	except: return False

def ensure_token():
	# Refresco proactivo: renueva ANTES de que el token caduque, en vez de
	# esperar al 401. Barato: solo compara un float salvo que toque renovar.
	try:
		if not _token_expiring_soon(): return
		if _refresh_is_dead(): return # invalid_grant reciente: no martillear /oauth/token
		if _recently_refreshed(): return # red de seguridad si Trakt diera tokens muy cortos
		with _refresh_lock:
			if not _token_expiring_soon(): return # otro hilo lo renovo mientras esperabamos
			if _refresh_is_dead() or _recently_refreshed(): return
			_do_refresh_token()
	except: log_utils.error('ensure_token Error: ')

def _recently_refreshed():
	age = _prop_age(_PROP_LAST_REFRESH)
	return age is not None and age < _MIN_REFRESH_GAP

def refresh_token(stale_token=None):
	# Entrada reactiva (401). Single-flight: si mientras esperabamos el lock otro
	# hilo ya renovo, el token guardado habra cambiado -> no relanzamos el refresh
	# (quemaria el refresh_token rotado y provocaria invalid_grant), basta con
	# reintentar la peticion con el token nuevo.
	try:
		if _refresh_is_dead(): return False # invalid_grant reciente: no reintentar aun
		with _refresh_lock:
			if stale_token and getSetting('trakt.token') != stale_token:
				log_utils.log('Trakt token already refreshed by another thread, reusing it', level=log_utils.LOGDEBUG)
				return True
			if _refresh_is_dead(): return False # otro hilo acaba de confirmar el invalid_grant
			return _do_refresh_token()
	except:
		log_utils.error('refresh_token Error: ')
		return False

def _do_refresh_token():
	# Ejecuta la renovacion. SIEMPRE se llama con _refresh_lock adquirido.
	try:
		log_utils.log('Re-Authenticating Trakt Token', level=log_utils.LOGINFO)
		oauth = urljoin(BASE_URL, '/oauth/token')
		opost = {'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET, 'redirect_uri': REDIRECT_URI, 'grant_type': 'refresh_token', 'refresh_token': getSetting('trakt.refresh')}
		auth_headers = dict(headers)
		auth_headers.pop('Authorization', None) # el endpoint de token no lleva Bearer
		response = session.post(url=oauth, data=jsdumps(opost), headers=auth_headers, timeout=20)
		status_code = str(response.status_code)

		error_handler(oauth, response, status_code)

		if status_code not in ('401', '403', '405'):
			try: response = response.json()
			except:
				log_utils.error()
				return False
			if 'error' in response and response['error'] == 'invalid_grant':
				log_utils.log('Please Re-Authorize your Trakt Account: %s : %s' % (status_code, str(response)), __name__, level=log_utils.LOGWARNING)
				_mark_refresh_dead() # notificacion debounced (1/h) + cooldown de reintentos
				return False

			token, refresh = response['access_token'], response['refresh_token']
			expires = _token_expiry(response)
			try: control.homeWindow.setProperty(_PROP_LAST_REFRESH, str(time()))
			except: pass
			setSetting('trakt.isauthed', 'true')
			setSetting('trakt.token', token)
			setSetting('trakt.refresh', refresh)
			setSetting('trakt.expires', expires)
			headers['Authorization'] = 'Bearer %s' % token # llamadas directas a session.* usan el dict global
			clear_refresh_dead() # el token vuelve a estar vivo: reactivar avisos futuros
			log_utils.log('Trakt Token Successfully Re-Authorized: expires on %s' % str(datetime.fromtimestamp(float(expires))), level=log_utils.LOGDEBUG)
			return True
		else:
			log_utils.log('Error while Re-Authorizing Trakt Token: %s : %s' % (status_code, str(response)), level=log_utils.LOGWARNING)
			return False
	except: log_utils.error()

def getTraktCredentialsInfo():
	username, token, refresh = getSetting('trakt.username').strip(), getSetting('trakt.token'), getSetting('trakt.refresh')
	if (username == '' or token == '' or refresh == ''): return False
	return True

def getTraktIndicatorsInfo():
	indicators = getSetting('indicators') if not getTraktCredentialsInfo() else getSetting('indicators.alt')
	indicators = True if indicators == '1' else False
	return indicators

def getTraktAddonMovieInfo():
	try: scrobble = control.addon('script.trakt').getSetting('scrobble_movie')
	except: scrobble = ''
	try: ExcludeHTTP = control.addon('script.trakt').getSetting('ExcludeHTTP')
	except: ExcludeHTTP = ''
	try: authorization = control.addon('script.trakt').getSetting('authorization')
	except: authorization = ''
	if scrobble == 'true' and ExcludeHTTP == 'false' and authorization != '':
		return True
	else: return False

def getTraktAddonEpisodeInfo():
	try: scrobble = control.addon('script.trakt').getSetting('scrobble_episode')
	except: scrobble = ''
	try: ExcludeHTTP = control.addon('script.trakt').getSetting('ExcludeHTTP')
	except: ExcludeHTTP = ''
	try: authorization = control.addon('script.trakt').getSetting('authorization')
	except: authorization = ''
	if scrobble == 'true' and ExcludeHTTP == 'false' and authorization != '':
		return True
	else: return False

def watch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	control.busy()
	success = False
	if content_type == 'movie':
		success = markMovieAsWatched(imdb)
		update_syncMovies(imdb)
	elif content_type == 'tvshow':
		success = markTVShowAsWatched(imdb, tvdb)
		cachesyncTV(imdb, tvdb)
	elif content_type == 'season':
		success = markSeasonAsWatched(imdb, tvdb, season)
		cachesyncTV(imdb, tvdb)
	elif content_type == 'episode':
		success = markEpisodeAsWatched(imdb, tvdb, season, episode)
		cachesyncTV(imdb, tvdb)
	else: success = False
	control.hide()
	if refresh: control.refresh()
	control.trigger_widget_refresh()
	if season and not episode: name = '%s-Season%s...' % (name, season)
	if season and episode: name = '%s-S%sxE%02d...' % (name, season, int(episode))
	if getSetting('trakt.general.notifications') == 'true':
		if success is True: control.notification(title=32315, message=getLS(35502) % ('[COLOR %s]%s[/COLOR]' % (highlight_color, name)))
		else: control.notification(title=32315, message=getLS(35504) % ('[COLOR %s]%s[/COLOR]' % (highlight_color, name)))
	if not success: log_utils.log(getLS(35504) % name + ' : ids={imdb: %s, tvdb: %s}' % (imdb, tvdb), __name__, level=log_utils.LOGDEBUG)

def unwatch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	control.busy()
	success = False
	if content_type == 'movie':
		success = markMovieAsNotWatched(imdb)
		update_syncMovies(imdb, remove_id=True)
	elif content_type == 'tvshow':
		success = markTVShowAsNotWatched(imdb, tvdb)
		cachesyncTV(imdb, tvdb)
	elif content_type == 'season':
		success = markSeasonAsNotWatched(imdb, tvdb, season)
		cachesyncTV(imdb, tvdb)
	elif content_type == 'episode':
		success = markEpisodeAsNotWatched(imdb, tvdb, season, episode)
		cachesyncTV(imdb, tvdb)
	else: success = False
	control.hide()
	if refresh: control.refresh()
	control.trigger_widget_refresh()
	if season and not episode: name = '%s-Season%s...' % (name, season)
	if season and episode: name = '%s-S%sxE%02d...' % (name, season, int(episode))
	if getSetting('trakt.general.notifications') == 'true':
		if success is True: control.notification(title=32315, message=getLS(35503) % ('[COLOR %s]%s[/COLOR]' % (highlight_color, name)))
		else: control.notification(title=32315, message=getLS(35505) % ('[COLOR %s]%s[/COLOR]' % (highlight_color, name)))
	if not success: log_utils.log(getLS(35505) % name + ' : ids={imdb: %s, tvdb: %s}' % (imdb, tvdb), __name__, level=log_utils.LOGDEBUG)

def like_list(list_owner, list_name, list_id):
	try:
		# resp_code = client._basic_request('https://api.trakt.tv/users/%s/lists/%s/like' % (list_owner, list_id), headers=headers, method='POST', ret_code=True)
		resp_code = _authed_status('POST', '/users/%s/lists/%s/like' % (list_owner, list_id))
		if resp_code == 204:
			control.notification(title=32315, message='Successfuly Liked list:  [COLOR %s]%s[/COLOR]' % (highlight_color, list_name))
			sync_liked_lists()
		else: control.notification(title=32315, message='Failed to Like list %s' % list_name)
		control.refresh()
	except: log_utils.error()

def unlike_list(list_owner, list_name, list_id):
	try:
		# resp_code = client._basic_request('https://api.trakt.tv/users/%s/lists/%s/like' % (list_owner, list_id), headers=headers, method='DELETE', ret_code=True)
		resp_code = _authed_status('DELETE', '/users/%s/lists/%s/like' % (list_owner, list_id))
		if resp_code == 204:
			control.notification(title=32315, message='Successfuly Unliked list:  [COLOR %s]%s[/COLOR]' % (highlight_color, list_name))
			traktsync.delete_liked_list(list_id)
		else: control.notification(title=32315, message='Failed to UnLike list %s' % list_name)
		control.refresh()
	except: log_utils.error()

def remove_liked_lists(trakt_ids):
	if not trakt_ids: return
	success = None
	try:
		for id in trakt_ids:
			list_owner = id.get('list_owner')
			list_id = id.get('trakt_id')
			list_name = id.get('list_name')
			# resp_code = client._basic_request('https://api.trakt.tv/users/%s/lists/%s/like' % (list_owner, list_id), headers=headers, method='DELETE', ret_code=True)
			resp_code = _authed_status('DELETE', '/users/%s/lists/%s/like' % (list_owner, list_id))
			if resp_code == 204:
				control.notification(title=32315, message='Successfuly Unliked list:  [COLOR %s]%s[/COLOR]' % (highlight_color, list_name))
				traktsync.delete_liked_list(list_id)
			else: control.notification(title=32315, message='Failed to UnLike list %s' % list_name)
			control.sleep(1000)
		control.refresh()
	except: log_utils.error()

def rate(imdb=None, tvdb=None, season=None, episode=None):
	return _rating(action='rate', imdb=imdb, tvdb=tvdb, season=season, episode=episode)

def unrate(imdb=None, tvdb=None, season=None, episode=None):
	return _rating(action='unrate', imdb=imdb, tvdb=tvdb, season=season, episode=episode)

def rateShow(imdb=None, tvdb=None, season=None, episode=None):
	# v1.0.90: getSetting() devuelve texto; comparar con el entero 1 no se
	# cumplia nunca. Se mantiene por compatibilidad (nadie la llama hoy).
	if str(getSetting('trakt.rating')) == '1':
		rate(imdb=imdb, tvdb=tvdb, season=season, episode=episode)

def _media_payload(imdb=None, tvdb=None, season=None, episode=None, rating=None):
	"""Cuerpo de /sync/ratings[/remove] (y de favoritos/dropped para
	pelicula y serie). Temporada y episodio van ANIDADOS bajo la serie, que
	es la forma que exige Trakt; la pelicula va por IMDb."""
	def _r(d):
		if rating is not None: d['rating'] = int(rating)
		return d
	if tvdb:
		show = {'ids': {'tvdb': int(tvdb)}}
		if imdb and str(imdb).startswith('tt'): show['ids']['imdb'] = imdb
		if season is not None and season != '' and episode is not None and episode != '':
			show['seasons'] = [{'number': int(season), 'episodes': [_r({'number': int(episode)})]}]
		elif season is not None and season != '':
			show['seasons'] = [_r({'number': int(season)})]
		else:
			_r(show)
		return {'shows': [show]}
	if imdb:
		return {'movies': [_r({'ids': {'imdb': imdb}})]}
	return None

def _rating(action, imdb=None, tvdb=None, season=None, episode=None):
	"""v1.0.90: valoracion NATIVA por la API de Trakt.
	Antes esto no hablaba con Trakt: buscaba el addon script.trakt e
	inyectaba la peticion en su cola SQLite, y sin ese addon el usuario solo
	veia "This action requires the Trakt addon to be installed"."""
	try:
		if not getTraktCredentialsInfo():
			return control.notification(title=32315, message=400820)
		rating = None
		if action == 'rate':
			labels = [getLS(400821) % (highlight_color, i) for i in range(10, 0, -1)]
			sel = control.selectDialog(labels, heading=getLS(400822))
			if sel < 0: return
			rating = 10 - sel
		post = _media_payload(imdb=imdb, tvdb=tvdb, season=season, episode=episode, rating=rating)
		if not post: return
		url = '/sync/ratings' if action == 'rate' else '/sync/ratings/remove'
		result = getTrakt(url, post=post)
		if result is not None:
			msg = (getLS(400823) % rating) if action == 'rate' else getLS(400824)
			control.notification(title=32315, message=msg)
		else:
			control.notification(title=32315, message=400825)
	except:
		log_utils.error()

def _simple_toggle(url, ok_msg, imdb=None, tvdb=None):
	"""Favoritos y series abandonadas: misma forma de cuerpo, sin nota."""
	try:
		post = _media_payload(imdb=imdb, tvdb=tvdb)
		if not post: return
		result = getTrakt(url, post=post)
		control.notification(title=32315, message=ok_msg if result is not None else 400825)
	except:
		log_utils.error()

def favourite(imdb=None, tvdb=None, remove=False):
	return _simple_toggle('/sync/favorites/remove' if remove else '/sync/favorites',
						  400827 if remove else 400826, imdb=imdb, tvdb=tvdb)

def dropShow(tvdb=None, imdb=None, undo=False):
	"""Trakt 'dropped': la serie deja de aparecer en progreso y en Up Next.
	Es una seccion oculta propia (/users/hidden/dropped), distinta de
	progress_watched."""
	if not tvdb: return
	_simple_toggle('/users/hidden/dropped/remove' if undo else '/users/hidden/dropped',
						  400829 if undo else 400828, imdb=imdb, tvdb=tvdb)
	# v1.0.95: el progreso local filtra por la tabla de ocultas, que ahora
	# incluye las abandonadas; se pone al dia en el acto.
	sync_hidden_progress(forced=True)
	control.trigger_widget_refresh()

def unHideItems(tvdb_ids):
	if not tvdb_ids: return
	success = None
	try:
		# v1.0.95: el gestor de ocultas lista tambien las abandonadas (dropped),
		# asi que devolverlas al progreso tiene que quitarlas de esa seccion.
		sections = ['progress_watched', 'calendar', 'dropped']
		ids = []
		for id in tvdb_ids: ids.append({"ids": {"tvdb": int(id)}})
		post = {"shows": ids}
		for section in sections:
			result = getTrakt('users/hidden/%s/remove' % section, post=post)
			if section != 'dropped' or result: success = result or success
			control.sleep(1000)
		if success:
			if 'plugin.video.luc_kodi' in control.infoLabel('Container.PluginName'): control.refresh()
			traktsync.delete_hidden_progress(tvdb_ids)
			control.trigger_widget_refresh()
			return True
	except:
		log_utils.error()
		return False

def hideItems(tvdb_ids):
	if not tvdb_ids: return
	success = None
	try:
		sections = ['progress_watched', 'calendar']
		ids = []
		for id in tvdb_ids: ids.append({"ids": {"tvdb": int(id)}})
		post = {"shows": ids}
		for section in sections:
			success = getTrakt('users/hidden/%s' % section, post=post)
			control.sleep(1000)
		if success:
			if 'plugin.video.luc_kodi' in control.infoLabel('Container.PluginName'): control.refresh()
			sync_hidden_progress(forced=True)
			control.trigger_widget_refresh()
			return True
	except:
		log_utils.error()
		return False

def hideItem(name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	success = None
	try:
		sections = ['progress_watched', 'calendar']
		sections_display = [getLS(40072), getLS(40073), getLS(32181)]
		selection = control.selectDialog([i for i in sections_display], heading=control.addonInfo('name') + ' - ' + getLS(40074))
		if selection == -1: return
		control.busy()
		if episode: post = {"shows": [{"ids": {"tvdb": tvdb}}]}
		else: post = {"movies": [{"ids": {"imdb": imdb}}]}
		if selection in (0, 1):
			section = sections[selection]
			success = getTrakt('users/hidden/%s' % section, post=post)
		else:
			for section in sections:
				success = getTrakt('users/hidden/%s' % section, post=post)
				control.sleep(1000)
		if success:
			control.hide()
			sync_hidden_progress(forced=True)
			if refresh: control.refresh()
			control.trigger_widget_refresh()
			if getSetting('trakt.general.notifications') == 'true':
				control.notification(title=32315, message=getLS(33053) % (name, sections_display[selection]))
	except: log_utils.error()

def removeCollectionItems(type, id_list):
	if not id_list: return
	success = None
	try:
		ids = []
		total_items = len(id_list)
		for id in id_list: ids.append({"ids": {"trakt": id}})
		post = {type: ids}
		success = getTrakt('/sync/collection/remove', post=post)
		if success:
			# if 'plugin.video.luc_kodi' in control.infoLabel('Container.PluginName'): control.refresh()
			control.trigger_widget_refresh()
			if type == 'movies': traktsync.delete_collection_items(id_list, 'movies_collection')
			else: traktsync.delete_collection_items(id_list, 'shows_collection')
			if getSetting('trakt.general.notifications') == 'true':
				control.notification(title='Trakt Collection Manager', message='Successfuly Removed %s Item%s' % (total_items, 's' if total_items >1 else ''))
	except: log_utils.error()

def removeWatchlistItems(type, id_list):
	if not id_list: return
	success = None
	try:
		ids = []
		total_items = len(id_list)
		for id in id_list: ids.append({"ids": {"trakt": id}})
		post = {type: ids}
		success = getTrakt('/sync/watchlist/remove', post=post)
		if success:
			# if 'plugin.video.luc_kodi' in control.infoLabel('Container.PluginName'): control.refresh()
			control.trigger_widget_refresh()
			if type == 'movies': traktsync.delete_watchList_items(id_list, 'movies_watchlist')
			else: traktsync.delete_watchList_items(id_list, 'shows_watchlist')
			if getSetting('trakt.general.notifications') == 'true':
				control.notification(title='Trakt Watch List Manager', message='Successfuly Removed %s Item%s' % (total_items, 's' if total_items >1 else ''))
	except: log_utils.error()

def manager(name, imdb=None, tvdb=None, season=None, episode=None, refresh=True, watched=None, unfinished=False):
	lists = []
	try:
		if season: season = int(season)
		if episode: episode = int(episode)
		media_type = 'Show' if tvdb else 'Movie'
		if watched is not None:
			if watched is True:
				items = [(getLS(33652) % highlight_color, 'unwatch')]
			else:
				items = [(getLS(33651) % highlight_color, 'watch')]
		else:
			items = [(getLS(33651) % highlight_color, 'watch')]
			items += [(getLS(33652) % highlight_color, 'unwatch')]
		# v1.0.90: valoracion nativa, ya no depende de script.trakt.
		items += [(getLS(33653) % highlight_color, 'rate')]
		items += [(getLS(33654) % highlight_color, 'unrate')]
		if not season and not episode:
			items += [(getLS(400830) % highlight_color, 'favAdd')]
			items += [(getLS(400831) % highlight_color, 'favRemove')]
		if tvdb and not season and not episode:
			items += [(getLS(400832) % highlight_color, 'dropShow')]
			items += [(getLS(400833) % highlight_color, 'undropShow')]
		if tvdb:
			items += [(getLS(40075) % (highlight_color, media_type), 'hideItem')]
			items += [(getLS(35058) % highlight_color, 'hiddenManager')]
		if unfinished is True:
			if media_type == 'Movie': items += [(getLS(35059) % highlight_color, 'unfinishedMovieManager')]
			elif episode: items += [(getLS(35060) % highlight_color, 'unfinishedEpisodeManager')]
		if getSetting('trakt.scrobble') == 'true' and getSetting('resume.source') == '1':
			if media_type == 'Movie' or episode:
				items += [(getLS(40076) % highlight_color, 'scrobbleReset')]
		if season or episode:
			items += [(getLS(33573) % highlight_color, '/sync/watchlist')]
			items += [(getLS(33574) % highlight_color, '/sync/watchlist/remove')]
		items += [(getLS(33577) % highlight_color, '/sync/watchlist')]
		items += [(getLS(33578) % highlight_color, '/sync/watchlist/remove')]
		items += [(getLS(33575) % highlight_color, '/sync/collection')]
		items += [(getLS(33576) % highlight_color, '/sync/collection/remove')]
		items += [(getLS(33579), '/users/me/lists/%s/items')]

		result = getTraktAsJsonPaginated('/users/me/lists') or [] # v1.0.95: None tumbaba el menu entero
		lists = [(i['name'], i['ids']['slug']) for i in result]
		lists = [lists[i//2] for i in range(len(lists)*2)]

		for i in range(0, len(lists), 2):
			lists[i] = ((getLS(33580) % (highlight_color, lists[i][0])), '/users/me/lists/%s/items' % lists[i][1])
		for i in range(1, len(lists), 2):
			lists[i] = ((getLS(33581) % (highlight_color, lists[i][0])), '/users/me/lists/%s/items/remove' % lists[i][1])
		items += lists

		control.hide()
		select = control.selectDialog([i[0] for i in items], heading=control.addonInfo('name') + ' - ' + getLS(32515))

		if select == -1: return
		if select >= 0:
			if items[select][1] == 'watch':
				watch(control.infoLabel('Container.ListItem.DBTYPE'), name, imdb=imdb, tvdb=tvdb, season=season, episode=episode, refresh=refresh)
			elif items[select][1] == 'unwatch':
				unwatch(control.infoLabel('Container.ListItem.DBTYPE'), name, imdb=imdb, tvdb=tvdb, season=season, episode=episode, refresh=refresh)
			elif items[select][1] == 'rate':
				rate(imdb=imdb, tvdb=tvdb, season=season, episode=episode)
			elif items[select][1] == 'unrate':
				unrate(imdb=imdb, tvdb=tvdb, season=season, episode=episode)
			elif items[select][1] in ('favAdd', 'favRemove'):
				favourite(imdb=imdb, tvdb=None if media_type == 'Movie' else tvdb, remove=items[select][1] == 'favRemove')
			elif items[select][1] in ('dropShow', 'undropShow'):
				dropShow(tvdb=tvdb, imdb=imdb, undo=items[select][1] == 'undropShow')
				if refresh: control.refresh()
			elif items[select][1] == 'hideItem':
				hideItem(name=name, imdb=imdb, tvdb=tvdb, season=season, episode=episode)
			elif items[select][1] == 'hiddenManager':
				control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=shows_traktHiddenManager)')
			elif items[select][1] == 'unfinishedEpisodeManager':
				control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=episodes_traktUnfinishedManager)')
			elif items[select][1] == 'unfinishedMovieManager':
				control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=movies_traktUnfinishedManager)')
			elif items[select][1] == 'scrobbleReset':
				scrobbleReset(imdb=imdb, tmdb='', tvdb=tvdb, season=season, episode=episode, widgetRefresh=True)
			else:
				if not tvdb: post = {"movies": [{"ids": {"imdb": imdb}}]}
				else:
					# v1.0.95: desde Trakt v3 las listas personales (igual que la
					# watchlist) ya no admiten temporadas ni episodios sueltos: se
					# aceptaban y luego no se veian en ningun sitio. Van por la serie.
					_show_only = items[select][1] in ('/sync/watchlist', '/sync/watchlist/remove') or items[select][1].startswith('/users/me/lists/')
					if episode:
						if _show_only:
							post = {"shows": [{"ids": {"tvdb": tvdb}}]}
						else:
							post = {"shows": [{"ids": {"tvdb": tvdb}, "seasons": [{"number": season, "episodes": [{"number": episode}]}]}]}
							name = name + ' - ' + '%sx%02d' % (season, episode)
					elif season:
						if _show_only:
							post = {"shows": [{"ids": {"tvdb": tvdb}}]}
						else:
							post = {"shows": [{"ids": {"tvdb": tvdb}, "seasons": [{"number": season}]}]}
							name = name + ' - ' + 'Season %s' % season
					else: post = {"shows": [{"ids": {"tvdb": tvdb}}]}
				if items[select][1] == '/users/me/lists/%s/items':
					slug = listAdd(successNotification=True)
					if slug: getTrakt(items[select][1] % slug, post=post)
				else: getTrakt(items[select][1], post=post)

				if items[select][1] == '/sync/watchlist': sync_watch_list(forced=True)
				if items[select][1] == '/sync/watchlist/remove':
					if media_type == 'Movie': traktsync.delete_watchList_items([imdb], 'movies_watchlist', 'imdb')
					else: traktsync.delete_watchList_items([tvdb], 'shows_watchlist', 'tvdb')
				if items[select][1] == '/sync/collection':
					sync_collection(forced=True)
				if items[select][1] == '/sync/collection/remove':
					if media_type == 'Movie': traktsync.delete_collection_items([imdb], 'movies_collection', 'imdb')
					else: traktsync.delete_collection_items([tvdb], 'shows_collection', 'tvdb')

				control.hide()
				_m = re.search(r'\[B](.+?)\[/B]', items[select][0]) # 33579 no lleva [B]: antes AttributeError
				label = _m.group(1) if _m else re.sub(r'\[/?[A-Z]+[^\]]*\]', '', items[select][0])
				message = getLS(33583) if 'remove' in items[select][1] else getLS(33582)
				if items[select][0].startswith('Add'): refresh = False
				control.hide()
				if refresh: control.refresh()
				control.trigger_widget_refresh()
				# v1.0.95: aqui se imprimia la funcion list() del modulo en vez del destino
				if getSetting('trakt.general.notifications') == 'true': control.notification(title=name, message=message + ' (%s)' % label)
	except:
		log_utils.error()
		control.hide()

def listAdd(successNotification=True):
	t = getLS(32520)
	k = control.keyboard('', t) ; k.doModal()
	new = k.getText() if k.isConfirmed() else None
	if not new: return
	result = getTrakt('/users/me/lists', post = {"name" : new, "privacy" : "private"})
	try:
		slug = result.json()['ids']['slug']
		if successNotification: control.notification(title=32070, message=33661)
		return slug
	except:
		control.notification(title=32070, message=33584)
		return None

def lists(id=None):
	# El indice (/users/me/lists) es un array paginado; /users/me/lists/<id> devuelve
	# UN objeto -> no se puede paginar, se deja como estaba.
	if not id: return cache.get(getTraktAsJsonPaginated, 48, 'https://api.trakt.tv/users/me/lists')
	return cache.get(getTraktAsJson, 48, 'https://api.trakt.tv/users/me/lists/' + str(id))

def list(id):
	return lists(id=id)

def slug(name):
	name = name.strip()
	name = name.lower()
	name = re.sub(r'[^a-z0-9_]', '-', name) # check apostrophe
	name = re.sub(r'--+', '-', name)
	return name

def _activity_max(activities, keys):
	"""Marca mas reciente (epoch) de un grupo de /sync/last_activities.
	v1.0.95: con el acceso directo i['x']['y'], si Trakt quitaba o renombraba
	una sola clave la funcion devolvia None, y 'None > numero' en Python 3
	lanza TypeError: los menus dejaban de usar su cache y la sync se paraba."""
	values = []
	for section, key in keys:
		try:
			v = (activities.get(section) or {}).get(key)
			if v: values.append(int(cleandate.iso_2_utc(v)))
		except: pass
	return max(values) if values else 0

def getActivity():
	try:
		i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'watched_at'), ('movies', 'collected_at'), ('movies', 'watchlisted_at'), ('movies', 'paused_at'), ('movies', 'hidden_at'), ('episodes', 'watched_at'), ('episodes', 'collected_at'), ('episodes', 'watchlisted_at'), ('episodes', 'paused_at'), ('shows', 'watchlisted_at'), ('shows', 'hidden_at'), ('seasons', 'watchlisted_at'), ('seasons', 'hidden_at'), ('lists', 'liked_at'), ('lists', 'updated_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getHiddenActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'hidden_at'), ('shows', 'hidden_at'), ('seasons', 'hidden_at')]
		for key in ('dropped_at',):
			if (i.get('shows') or {}).get(key): keys.append(('shows', key))
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getWatchedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'watched_at'), ('episodes', 'watched_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getMoviesWatchedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'watched_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getEpisodesWatchedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('episodes', 'watched_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getCollectedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'collected_at'), ('episodes', 'collected_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getWatchListedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'watchlisted_at'), ('episodes', 'watchlisted_at'), ('shows', 'watchlisted_at'), ('seasons', 'watchlisted_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getPausedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('movies', 'paused_at'), ('episodes', 'paused_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getListActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('lists', 'liked_at'), ('lists', 'updated_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getUserListActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('lists', 'updated_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

def getProgressActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getTraktAsJson('/sync/last_activities')
		if not i: return 0
		keys = [('episodes', 'watched_at'), ('shows', 'hidden_at'), ('seasons', 'hidden_at')]
		return _activity_max(i, keys)
	except:
		log_utils.error()
		return 0

_syncMovies_lock = Lock()
def cachesyncMovies(timeout=0):
	# 2026 single-flight: la primera llamada hace el crawl paginado; las demas
	# esperan y releen la cache recien escrita en vez de lanzar crawls duplicados.
	with _syncMovies_lock:
		indicators = traktsync.get(syncMovies, timeout)
	return indicators

def syncMovies():
	try:
		if not getTraktCredentialsInfo(): return
		# 2026-06-30 Trakt API: /watched is paginated (100-item cap without params)
		indicators = getTraktAsJsonPaginated('/users/me/watched/movies', silent=True)
		if not indicators: return None
		indicators = [i['movie']['ids'] for i in indicators]
		indicators = [str(i['imdb']) for i in indicators if 'imdb' in i]
		return indicators
	except: log_utils.error()

def timeoutsyncMovies():
	timeout = traktsync.timeout(syncMovies)
	return timeout

def watchedMovies():
	try:
		if not getTraktCredentialsInfo(): return
		# 2026-06-30 Trakt API: full info is now the default; paginate to get everything
		return getTraktAsJsonPaginated('/users/me/watched/movies', silent=True)
	except: log_utils.error()

def watchedMoviesTime(imdb):
	try:
		imdb = str(imdb)
		items = watchedMovies()
		for item in items:
			if str(item['movie']['ids']['imdb']) == imdb: return item['last_watched_at']
	except: log_utils.error()

def watchedShows():
	try:
		if not getTraktCredentialsInfo(): return
		# 2026-06-30 Trakt API: noseason is the default now; seasons array requires
		# extended=progress. Pages may come back smaller than requested with progress.
		# v1.0.95: extended=progress ya trae ids, titulo, aired_episodes y las
		# temporadas; 'full' solo anadia peso (sinopsis, reparto...) en cada pagina.
		return getTraktAsJsonPaginated('/users/me/watched/shows?extended=progress', silent=True)
	except: log_utils.error()

def watchedShowsTime(tvdb, season, episode):
	try:
		tvdb = str(tvdb)
		season = int(season)
		episode = int(episode)
		items = watchedShows()
		for item in items:
			if str(item['show']['ids']['tvdb']) == tvdb:
				seasons = item['seasons']
				for s in seasons:
					if s['number'] == season:
						episodes = s['episodes']
						for e in episodes:
							if e['number'] == episode:
								return e['last_watched_at']
	except: log_utils.error()

def cachesyncTV(imdb, tvdb): # sync full watched shows then sync imdb_id "season indicators" and "season counts"
	try:
		threads = [Thread(target=cachesyncTVShows), Thread(target=cachesyncSeasons, args=(imdb, tvdb))]
		[i.start() for i in threads]
		[i.join() for i in threads]
		traktsync.insert_syncSeasons_at()
	except: log_utils.error()

_syncTVShows_lock = Lock()
def cachesyncTVShows(timeout=0):
	# 2026 single-flight: idem cachesyncMovies. El crawl de /watched/shows con
	# extended=progress es caro; jamas debe correr duplicado en paralelo.
	with _syncTVShows_lock:
		indicators = traktsync.get(syncTVShows, timeout)
	return indicators

def syncTVShows(): # sync all watched shows ex. [({'imdb': 'tt12571834', 'tvdb': '384435', 'tmdb': '105161', 'trakt': '163639'}, 16, [(1, 16)]), ({'imdb': 'tt11761194', 'tvdb': '377593', 'tmdb': '119845', 'trakt': '158621'}, 2, [(1, 1), (1, 2)])]
	try:
		if not getTraktCredentialsInfo(): return
		# 2026-06-30 Trakt API: extended=progress required for the seasons array
		indicators = getTraktAsJsonPaginated('/users/me/watched/shows?extended=progress', silent=True) # v1.0.95: sin 'full', no se usa
		if not indicators: return None
# /shows/ID/progress/watched  endpoint only accepts imdb or trakt ID so write all ID's
		indicators = [({'imdb': i['show']['ids'].get('imdb'), 'tvdb': str(i['show']['ids'].get('tvdb')), 'tmdb': str(i['show']['ids'].get('tmdb')), 'trakt': str(i['show']['ids'].get('trakt'))}, \
							i['show'].get('aired_episodes') or 0, sum([[(s['number'], e['number']) for e in (s.get('episodes') or [])] for s in (i.get('seasons') or [])], [])) for i in indicators]
		indicators = [(i[0], int(i[1]), i[2]) for i in indicators]
		return indicators
	except: log_utils.error()

def cachesyncSeasons(imdb, tvdb, trakt=None, timeout=0):
	try:
		imdb = imdb or ''
		tvdb = tvdb or ''
		indicators = traktsync.get(syncSeasons, timeout, imdb, tvdb, trakt=trakt) # named var not included in function md5_hash
		return indicators
	except: log_utils.error()

def syncSeasons(imdb, tvdb, trakt=None): # season indicators and counts for watched shows ex. [['1', '2', '3'], {1: {'total': 8, 'watched': 8, 'unwatched': 0}, 2: {'total': 10, 'watched': 10, 'unwatched': 0}}]
	indicators_and_counts = []
	try:
		if all(not value for value in (imdb, tvdb, trakt)): return
		if not getTraktCredentialsInfo(): return
		id = imdb or trakt
		if not id and tvdb:
			log_utils.log('syncSeasons missing imdb_id, pulling trakt id from watched shows database', level=log_utils.LOGDEBUG)
			db_watched = traktsync.cache_existing(syncTVShows) or [] # v1.0.64: devuelve None si Trakt no esta sincronizado
			ids = [i[0] for i in db_watched if i and i[0].get('tvdb') == tvdb]
			# v1.0.64: ids puede venir vacia -> ids[0] daba IndexError
			id = (ids[0].get('trakt', '') if ids else '') or ''
			if not id:
				log_utils.log("syncSeasons FAILED: missing required imdb and trakt ID's for tvdb=%s" % tvdb, level=log_utils.LOGDEBUG)
				return
		if getSetting('tv.specials') == 'true':
			results = getTraktAsJson('/shows/%s/progress/watched?specials=true&hidden=false&count_specials=true' % id, silent=True) # only imdb or trakt ID allowed
		else:
			results = getTraktAsJson('/shows/%s/progress/watched?specials=false&hidden=false' % id, silent=True)
		if not results: return
		seasons = results['seasons']

###--- future-need tmdb_id passed now ---###
		# next_episode = results['next_episode']
		# # log_utils.log('next_episode=%s' % next_episode)
		# db_watched = traktsync.cache_existing(syncTVShows)
		# ids = [i[0] for i in db_watched if (i[0].get('imdb') == imdb or i[0].get('tvdb') == tvdb)]
		# tmdb = str(ids[0].get('tmdb', '')) if ids[0].get('tmdb') else ''
		# trakt = str(ids[0].get('trakt', '')) if ids[0].get('trakt') else ''
		# traktsync.insert_nextEpisode(imdb, tvdb, tmdb, trakt, next_episode)
#######

		indicators = [(i['number'], [x['completed'] for x in i['episodes']]) for i in seasons]
		indicators = ['%01d' % int(i[0]) for i in indicators if False not in i[1]]
		indicators_and_counts.append(indicators)
		counts = {season['number']: {'total': season['aired'], 'watched': season['completed'], 'unwatched': season['aired'] - season['completed']} for season in seasons}
		indicators_and_counts.append(counts)
		return indicators_and_counts
	except:
		log_utils.error()
		return None

def seasonCount(imdb, tvdb): # return counts for all seasons of a show from traktsync.db
	try:
		counts = traktsync.cache_existing(syncSeasons, imdb, tvdb) # this needs trakt ID
		if not counts: return
		return counts[1]
	except:
		log_utils.error()
		return None

def timeoutsyncTVShows():
	timeout = traktsync.timeout(syncTVShows)
	return timeout

def timeoutsyncSeasons(imdb, tvdb):
	try:
		timeout = traktsync.timeout(syncSeasons, imdb, tvdb, returnNone=True) # returnNone must be named arg or will end up considered part of "*args"
		return timeout
	except: log_utils.error()

def update_syncMovies(imdb, remove_id=False):
	try:
		indicators = traktsync.cache_existing(syncMovies)
		# v1.0.64: None cuando aun no hay sync de Trakt -> .remove()/.append() petaban
		if indicators is None:
			if remove_id: return
			indicators = []
		if remove_id:
			if imdb in indicators: indicators.remove(imdb)
			else: return
		elif imdb not in indicators:
			indicators.append(imdb)
		key = traktsync._hash_function(syncMovies, ())
		traktsync.cache_insert(key, repr(indicators))
	except: log_utils.error()

def _show_signature(indicator):
	# (episodios emitidos, episodios vistos) de una serie en syncTVShows: si no
	# cambia, sus contadores por temporada tampoco.
	try: return (int(indicator[1]), tuple(sorted(tuple(x) for x in (indicator[2] or []))))
	except: return None

def service_syncSeasons(previous=None): # season indicators and counts for watched shows ex. [['1', '2', '3'], {1: {'total': 8, 'watched': 8, 'unwatched': 0}, 2: {'total': 10, 'watched': 10, 'unwatched': 0}}]
	"""Contadores por temporada de las series vistas (/shows/{id}/progress/watched).

	v1.0.95: se pedia el progreso de TODAS las series vistas cada vez que
	cambiaba la actividad de episodios, es decir, tras cada episodio. Con 300
	series eran 300 peticiones por episodio visto, y el limite de Trakt es de
	1000 GET cada 5 minutos por usuario. Con `previous` (la lista de
	syncTVShows de antes de refrescarla) solo se piden las series cuyo numero
	de emitidos o de vistos ha cambiado, o que aun no tienen contadores.
	Ademas los hilos ya no se crean uno por serie: 8 trabajadores fijos."""
	try:
		from queue import Queue, Empty
		indicators = traktsync.cache_existing(syncTVShows) # use cached data from service cachesyncTVShows() just written fresh
		if not indicators: return
		prev = {}
		if previous:
			for i in previous:
				try: prev[str(i[0].get('trakt') or i[0].get('tvdb') or i[0].get('imdb'))] = _show_signature(i)
				except: pass
		jobs = Queue()
		queued = 0
		for indicator in indicators:
			imdb = indicator[0].get('imdb', '') if indicator[0].get('imdb') else ''
			tvdb = str(indicator[0].get('tvdb', '')) if indicator[0].get('tvdb') else ''
			trakt_id = str(indicator[0].get('trakt', '')) if indicator[0].get('trakt') else ''
			if previous is not None:
				key = str(indicator[0].get('trakt') or indicator[0].get('tvdb') or indicator[0].get('imdb'))
				if key in prev and prev[key] == _show_signature(indicator) and traktsync.cache_existing(syncSeasons, imdb, tvdb):
					continue
			jobs.put((imdb, tvdb, trakt_id))
			queued += 1
		if previous is not None:
			log_utils.log('Trakt season counts: %s of %s watched shows changed' % (queued, len(indicators)), __name__, log_utils.LOGDEBUG)
		def _worker():
			while True:
				try: imdb, tvdb, trakt_id = jobs.get_nowait()
				except Empty: return
				try: cachesyncSeasons(imdb, tvdb, trakt_id)
				except: pass
		threads = [Thread(target=_worker) for _ in range(min(8, queued))]
		[i.start() for i in threads]
		[i.join() for i in threads]
	except: log_utils.error()

def markMovieAsWatched(imdb):
	try:
		result = getTraktAsJson('/sync/history', {"movies": [{"ids": {"imdb": imdb}}]})
		return result['added']['movies'] != 0
	except: log_utils.error()

def markMovieAsNotWatched(imdb):
	try:
		result = getTraktAsJson('/sync/history/remove', {"movies": [{"ids": {"imdb": imdb}}]})
		return result['deleted']['movies'] != 0
	except: log_utils.error()

def markTVShowAsWatched(imdb, tvdb):
	try:
		result = getTraktAsJson('/sync/history', {"shows": [{"ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['added']['episodes'] == 0 and tvdb: # sometimes trakt fails to mark because of imdb_id issues, check tvdb only as fallback if it fails
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = getTraktAsJson('/sync/history', {"shows": [{"ids": {"tvdb": tvdb}}]})
		return result['added']['episodes'] != 0
	except: log_utils.error()

def markTVShowAsNotWatched(imdb, tvdb):
	try:
		result = getTraktAsJson('/sync/history/remove', {"shows": [{"ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['deleted']['episodes'] == 0 and tvdb: # sometimes trakt fails to mark because of imdb_id issues, check tvdb only as fallback if it fails
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = getTraktAsJson('/sync/history/remove', {"shows": [{"ids": {"tvdb": tvdb}}]})
		return result['deleted']['episodes'] != 0
	except: log_utils.error()

def markSeasonAsWatched(imdb, tvdb, season):
	try:
		season = int('%01d' % int(season))
		result = getTraktAsJson('/sync/history', {"shows": [{"seasons": [{"number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['added']['episodes'] == 0 and tvdb: # sometimes trakt fails to mark because of imdb_id issues, check tvdb only as fallback if it fails
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = getTraktAsJson('/sync/history', {"shows": [{"seasons": [{"number": season}], "ids": {"tvdb": tvdb}}]})
		return result['added']['episodes'] != 0
	except: log_utils.error()

def markSeasonAsNotWatched(imdb, tvdb, season):
	try:
		season = int('%01d' % int(season))
		result = getTraktAsJson('/sync/history/remove', {"shows": [{"seasons": [{"number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['deleted']['episodes'] == 0 and tvdb: # sometimes trakt fails to mark because of imdb_id issues, check tvdb only as fallback if it fails
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = getTraktAsJson('/sync/history/remove', {"shows": [{"seasons": [{"number": season}], "ids": {"tvdb": tvdb}}]})
		return result['deleted']['episodes'] != 0
	except: log_utils.error()

# def markEpisodeAsWatched(imdb, tvdb, season, episode):
	# try:
		# season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		# result = getTraktAsJson('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		# if result['added']['episodes'] == 0 and tvdb: # sometimes trakt fails to mark because of imdb_id issues, check tvdb only as fallback if it fails
			# control.sleep(1000) # POST 1 call per sec rate-limit
			# result = getTraktAsJson('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"tvdb": tvdb}}]})

		# log_utils.log('result=%s' % str(result))

		# return result['added']['episodes'] != 0
	# except: log_utils.error()


def markEpisodeAsWatched(imdb, tvdb, season, episode):
	try:
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		result = getTraktAsJson('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		return result['added']['episodes'] != 0
	except: log_utils.error()



def markEpisodeAsNotWatched(imdb, tvdb, season, episode):
	try:
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		result = getTraktAsJson('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['deleted']['episodes'] == 0 and tvdb: # sometimes trakt fails to mark because of imdb_id issues, check tvdb only as fallback if it fails
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = getTraktAsJson('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"tvdb": tvdb}}]})
		return result['deleted']['episodes'] != 0
	except: log_utils.error()

def getMovieTranslation(id, lang, full=False):
	url = '/movies/%s/translations/%s' % (id, lang)
	try:
		item = cache.get(getTraktAsJson, 96, url)
		if item: item = item[0]
		else: return None
		return item if full else item.get('title')
	except: log_utils.error()

def getTVShowTranslation(id, lang, season=None, episode=None, full=False):
	if season and episode: url = '/shows/%s/seasons/%s/episodes/%s/translations/%s' % (id, season, episode, lang)
	else: url = '/shows/%s/translations/%s' % (id, lang)
	try:
		item = cache.get(getTraktAsJson, 96, url)
		if item: item = item[0]
		else: return None
		return item if full else item.get('title')
	except: log_utils.error()

def getMovieSummary(id, full=True):
	try:
		url = '/movies/%s' % id
		if full: url += '?extended=full'
		return cache.get(getTraktAsJson, 48, url)
	except: log_utils.error()

def getTVShowSummary(id, full=True):
	try:
		url = '/shows/%s' % id
		if full: url += '?extended=full'
		return cache.get(getTraktAsJson, 48, url)
	except: log_utils.error()

def getEpisodeSummary(id, season, episode, full=True):
	try:
		url = '/shows/%s/seasons/%s/episodes/%s' % (id, season, episode)
		if full: url += '?extended=full' # v1.0.95: iba con '&' sin '?' -> 404
		return cache.get(getTraktAsJson, 48, url)
	except: log_utils.error()

def getSeasons(id, full=True):
	try:
		url = '/shows/%s/seasons' % (id)
		if full: url += '?extended=full' # v1.0.95: iba con '&' sin '?' -> 404
		return cache.get(getTraktAsJson, 48, url)
	except: log_utils.error()

def sort_list(sort_key, sort_direction, list_data):
	try:
		reverse = False if sort_direction == 'asc' else True
		if sort_key == 'rank': return sorted(list_data, key=lambda x: x['rank'], reverse=reverse)
		elif sort_key == 'added': return sorted(list_data, key=lambda x: x['listed_at'], reverse=reverse)
		elif sort_key == 'title': return sorted(list_data, key=lambda x: _title_key(x[x['type']].get('title')), reverse=reverse)
		elif sort_key == 'released': return sorted(list_data, key=lambda x: _released_key(x[x['type']]), reverse=reverse)
		elif sort_key == 'runtime': return sorted(list_data, key=lambda x: x[x['type']].get('runtime', 0), reverse=reverse)
		elif sort_key == 'popularity': return sorted(list_data, key=lambda x: x[x['type']].get('votes', 0), reverse=reverse)
		elif sort_key == 'percentage': return sorted(list_data, key=lambda x: x[x['type']].get('rating', 0), reverse=reverse)
		elif sort_key == 'votes': return sorted(list_data, key=lambda x: x[x['type']].get('votes', 0), reverse=reverse)
		else: return list_data
	except: log_utils.error()

def _title_key(title):
	try:
		if not title: title = ''
		articles_en = ['the', 'a', 'an']
		articles_de = ['der', 'die', 'das']
		articles = articles_en + articles_de
		match = re.match(r'^((\w+)\s+)', title.lower())
		if match and match.group(2) in articles: offset = len(match.group(1))
		else: offset = 0
		return title[offset:]
	except: return title

def _released_key(item):
	try:
		if 'released' in item: return item['released'] or '0'
		elif 'first_aired' in item: return item['first_aired'] or '0'
		else: return '0'
	except: log_utils.error()

def getMovieAliases(id):
	try:
		return cache.get(getTraktAsJson, 168, '/movies/%s/aliases' % id)
	except:
		log_utils.error()
		return []

def getTVShowAliases(id):
	try:
		return cache.get(getTraktAsJson, 168, '/shows/%s/aliases' % id)
	except:
		log_utils.error()
		return []

def getPeople(id, content_type, full=True):
	try:
		url = '/%s/%s/people' % (content_type, id)
		if full: url += '?extended=full'
		return cache.get(getTraktAsJson, 96, url)
	except: log_utils.error()

def SearchAll(title, year, full=True):
	try:
		# v1.0.95: 'full' entraba por posicion en el hueco de 'fields' (&fields=True)
		return (SearchMovie(title, year, full=full) or []) + (SearchTVShow(title, year, full=full) or [])
	except:
		log_utils.error()
		return

def SearchMovie(title, year, fields=None, full=True):
	try:
		url = '/search/movie?query=%s' % title
		if year: url += '&year=%s' % year
		if fields: url += '&fields=%s' % fields
		if full: url += '&extended=full'
		return cache.get(getTraktAsJson, 96, url)
	except:
		log_utils.error()
		return

def SearchTVShow(title, year, fields=None, full=True):
	try:
		url = '/search/show?query=%s' % title
		if year: url += '&year=%s' % year
		if fields: url += '&fields=%s' % fields
		if full: url += '&extended=full'
		return cache.get(getTraktAsJson, 96, url)
	except:
		log_utils.error()
		return

def SearchEpisode(title, season, episode, full=True):
	# v1.0.95: /search/<titulo>/seasons/... no existe en la API. La ruta buena es
	# la del episodio de la serie; 'title' debe ser un id o slug de Trakt/IMDb.
	try:
		url = '/shows/%s/seasons/%s/episodes/%s' % (title, season, episode)
		if full: url += '?extended=full'
		return cache.get(getTraktAsJson, 96, url)
	except:
		log_utils.error()
		return

def getGenre(content, type, type_id):
	try:
		url = '/search/%s/%s?type=%s&extended=full' % (type, type_id, content)
		result = cache.get(getTraktAsJson, 168, url)
		if not result: return []
		return result[0].get(content, {}).get('genres', [])
	except:
		log_utils.error()
		return []

def IdLookup(id_type, id, type): # ("id_type" can be trakt, imdb, tmdb, tvdb) (type can be one of "movie , show , episode , person , list")
	try:
		url = '/search/%s/%s?type=%s' % (id_type, id, type)
		result = cache.get(getTraktAsJson, 168, url)
		if not result: return None
		for item in result: # the first result can be of another type (an episode when a show was asked for)
			ids = (item.get(type) or {}).get('ids') if isinstance(item, dict) else None
			if ids: return ids
		return None
	except:
		log_utils.error()
		return None

def _scrobble_body(imdb, tmdb, tvdb, season, episode, watched_percent):
	"""Cuerpo comun de /scrobble/{start,pause,stop}.

	v1.0.79: hasta ahora un episodio se identificaba SOLO por tvdb. El imdb se
	normalizaba justo encima y no se llegaba a usar, asi que una serie sin tvdb
	fallaba en silencio. Trakt acepta imdb/tmdb/tvdb a la vez y resuelve con el
	que reconozca -- exactamente lo que ya hace simkl._build_scrobble_body().
	En pelicula NO se manda tvdb: ahi ese id no significa nada.

	El progreso se acota y se redondea a 2 decimales (0,3 s en un episodio de
	50 min), por el mismo motivo que en MDBList: un float crudo de division es
	ruido que no aporta y que algunas APIs rechazan.

	Devuelve None si no hay ningun id utilizable, para que el llamante pueda
	dejar constancia en vez de mandar un cuerpo vacio que Trakt responderia 404.
	"""
	ids = {}
	if imdb:
		_i = str(imdb)
		if not _i.startswith('tt'): _i = 'tt' + _i
		ids['imdb'] = _i
	if tmdb: ids['tmdb'] = int(str(tmdb)) if str(tmdb).isdigit() else str(tmdb)
	if episode and tvdb: ids['tvdb'] = int(str(tvdb)) if str(tvdb).isdigit() else str(tvdb)
	if not ids: return None
	try: progress = round(min(max(float(watched_percent or 0), 0), 100), 2)
	except Exception: progress = 0.0
	body = {'progress': progress}
	if not episode:
		body['movie'] = {'ids': ids}
	else:
		body['show'] = {'ids': ids}
		body['episode'] = {'season': int('%01d' % int(season)), 'number': int('%01d' % int(episode))}
	return body


def _scrobble_post(action, body):
	"""POST /scrobble/{action} con el codigo HTTP a la vista. Devuelve (ok, code).

	No pasa por getTrakt() a proposito. getTrakt() colapsa cualquier respuesta
	que no sea 200/201 en None, y aqui el codigo ES el diagnostico: un 401 de
	token, un 404 de id que Trakt no reconoce y un timeout son tres arreglos
	distintos y hasta ahora los tres se veian igual (nada en el log).

	Ademas Trakt responde 409 cuando el mismo item se acaba de registrar. Eso
	NO es un fallo: el historial ya tiene la entrada. Tratarlo como fallo
	dejaba sin ejecutar el espejo local de scrobbleStop() -- el borrado del
	marcador y el refresco de indicadores -- y sacaba un aviso de error falso.
	"""
	url = urljoin(BASE_URL, '/scrobble/%s' % action)
	used_token = ''
	try:
		ensure_token()
		used_token = getSetting('trakt.token')
		req_headers = dict(headers)
		req_headers['Authorization'] = 'Bearer %s' % used_token
		response = session.post(url, data=jsdumps(body), headers=req_headers, timeout=20)
		status_code = response.status_code
		if status_code == 401:
			if refresh_token(stale_token=used_token):
				req_headers['Authorization'] = 'Bearer %s' % getSetting('trakt.token')
				response = session.post(url, data=jsdumps(body), headers=req_headers, timeout=20)
				status_code = response.status_code
		if status_code in (200, 201, 409): return True, status_code
		_hard_log('scrobble/%s FAILED: HTTP %s | %s'
					% (action, status_code, (response.text or '')[:200].replace('\n', ' ')), 3)
		return False, status_code
	except Exception as exc:
		_hard_log('scrobble/%s FAILED: %s: %s' % (action, type(exc).__name__, exc), 3)
		return False, 0


def _clear_local_bookmark(imdb, tvdb=None, season=None, episode=None):
	"""Borra el marcador espejo de traktsync.db.

	/scrobble/start elimina el punto de resume EN TRAKT, asi que el espejo
	local tiene que irse con el o queda apuntando a algo que ya no existe.
	"""
	try:
		if imdb and not str(imdb).startswith('tt'): imdb = 'tt' + str(imdb)
		timestamp = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		if not episode:
			items = [{'type': 'movie', 'movie': {'ids': {'imdb': imdb}}, 'paused_at': timestamp}]
		else:
			items = [{'type': 'episode', 'episode': {'season': int('%01d' % int(season)), 'number': int('%01d' % int(episode))},
						'show': {'ids': {'imdb': imdb, 'tvdb': tvdb}}, 'paused_at': timestamp}]
		traktsync.delete_bookmark(items)
	except: pass


def scrobbleStart(imdb, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
	"""POST /scrobble/start -- el estado "viendo ahora" de trakt.tv.

	v1.0.79. Antes NO existia. El addon solo hablaba con Trakt AL PARAR, asi
	que la web no reflejaba en directo nada de lo que se estaba viendo, al
	contrario que SIMKL y MDBList, que si mandan su start en onAVStarted.

	Segun la API el estado de "watching" caduca solo cuando se agota el tiempo
	restante del item, asi que basta UNA llamada al arrancar: Trakt extrapola
	la barra el resto de la reproduccion y no hacen falta pings periodicos.

	Sustituye ademas a scrobbleReset() en onAVStarted: /scrobble/start ya
	elimina por si mismo el punto de resume que hubiera, que es justo lo que
	aquel DELETE /sync/playback/{id} hacia a mano -- con su dialogo de ocupado
	parpadeando al arrancar el video y una peticion de mas.
	"""
	if not getTraktCredentialsInfo(): return False
	try:
		body = _scrobble_body(imdb, tmdb, tvdb, season, episode, watched_percent)
		if not body:
			_hard_log('scrobble/start skipped: sin id utilizable (imdb=%s tmdb=%s tvdb=%s)' % (imdb, tmdb, tvdb), 3)
			return False
		ok, status = _scrobble_post('start', body)
		if ok:
			_clear_local_bookmark(imdb, tvdb, season, episode)
			_hard_log('scrobble/start OK (HTTP %s) imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s'
						% (status, imdb, tmdb, tvdb, season, episode, body.get('progress')))
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(message=32088)
		return ok
	except:
		log_utils.error()
		return False


def _scrobble_pause(imdb, tmdb, tvdb, season, episode, watched_percent, sync=True):
	"""POST /scrobble/pause -- guarda el punto de resume en /sync/playback.

	`sync` controla el tiron de sync_playbackProgress(forced=True) posterior.
	Al parar interesa (el espejo local se pone al dia en el acto); en una pausa
	real del usuario no, porque bajaria la lista entera de pausados cada vez
	que se toca el boton.
	"""
	if not getTraktCredentialsInfo(): return False
	try:
		body = _scrobble_body(imdb, tmdb, tvdb, season, episode, watched_percent)
		if not body:
			_hard_log('scrobble/pause skipped: sin id utilizable (imdb=%s tmdb=%s tvdb=%s)' % (imdb, tmdb, tvdb), 3)
			return False
		ok, status = _scrobble_post('pause', body)
		if ok:
			_hard_log('scrobble/pause OK (HTTP %s) imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s'
						% (status, imdb, tmdb, tvdb, season, episode, body.get('progress')))
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(message=32088)
			if sync:
				control.sleep(1000)
				sync_playbackProgress(forced=True)
		else:
			# v1.0.79: este aviso era INCONDICIONAL mientras el de exito
			# respetaba trakt.scrobble.notify. Con las notificaciones apagadas
			# seguian saliendo popups de fallo encima del video.
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(message=32130)
		return ok
	except:
		log_utils.error()
		return False


def scrobbleMovie(imdb, tmdb, watched_percent):
	return _scrobble_pause(imdb, tmdb, None, None, None, watched_percent, sync=True)

def scrobbleEpisode(imdb, tmdb, tvdb, season, episode, watched_percent):
	return _scrobble_pause(imdb, tmdb, tvdb, season, episode, watched_percent, sync=True)

def scrobblePause(imdb, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
	"""Pausa "en vivo": la que se manda al pausar de verdad o al salir del
	bucle de reproduccion sin un onPlayBackStopped. Sin sync posterior."""
	return _scrobble_pause(imdb, tmdb, tvdb, season, episode, watched_percent, sync=False)


def scrobbleStop(imdb, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=100):
	# /scrobble/stop with progress >= 80 makes Trakt:
	#   1) add the item to /sync/history (action='scrobble') -> watched indicators sync
	#   2) clear the playback resume point automatically
	# Also mirrors the change locally so traktsync.db stays consistent without waiting for next sync tick.
	if not getTraktCredentialsInfo(): return False
	success = False
	try:
		# v1.0.95: exigia imdb aunque _scrobble_body acepta tmdb/tvdb; start y
		# pause ya funcionaban sin el y stop no, asi que esas sesiones quedaban
		# en "viendo ahora" y nunca pasaban al historial.
		body = _scrobble_body(imdb, tmdb, tvdb, season, episode, watched_percent)
		if not body:
			_hard_log('scrobble/stop skipped: sin id utilizable (imdb=%s tmdb=%s tvdb=%s)' % (imdb, tmdb, tvdb), 3)
			return False
		success, status = _scrobble_post('stop', body)
		if success:
			_hard_log('scrobble/stop OK (HTTP %s) imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s'
						% (status, imdb, tmdb, tvdb, season, episode, body.get('progress')))
			# clear local bookmark
			_clear_local_bookmark(imdb, tvdb, season, episode)
			# refresh local watched indicators cache
			_imdb = (imdb if str(imdb).startswith('tt') else 'tt' + str(imdb)) if imdb else ''
			if not episode:
				if _imdb:
					try: update_syncMovies(_imdb)
					except: pass
			else:
				try: cachesyncTV(_imdb, tvdb)
				except: pass
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(message=32088)
		else:
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(message=32130)
	except: log_utils.error()
	return success

def scrobbleReset(imdb, tmdb=None, tvdb=None, season=None, episode=None, refresh=True, widgetRefresh=False):
	if not getTraktCredentialsInfo(): return
	control.busy()
	success = False
	try:
		content_type = 'movie' if not episode else 'episode'
		resume_info = traktsync.fetch_bookmarks(imdb, tmdb, tvdb, season, episode, ret_type='resume_info')
		if resume_info == '0': return control.hide() # returns string "0" if no data in db 
		success = _authed_status('DELETE', '/sync/playback/%s' % resume_info[1]) == 204
		if content_type == 'movie':
			items = [{'type': 'movie', 'movie': {'ids': {'imdb': imdb}}}]
			label_string = resume_info[0]
		else:
			items = [{'type': 'episode', 'episode': {'season': season, 'number': episode}, 'show': {'ids': {'imdb': imdb, 'tvdb': tvdb}}}]
			label_string = resume_info[0] + ' - ' + 'S%02dE%02d' % (int(season), int(episode))
		control.hide()
		if success:
			timestamp = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000Z")
			items[0].update({'paused_at': timestamp})
			traktsync.delete_bookmark(items)
			if refresh: control.refresh()
			if widgetRefresh: control.trigger_widget_refresh() # skinshortcuts handles the widget_refresh when plyback ends, but not a manual clear from Trakt Manager
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(title=32315, message='Successfuly Removed playback progress:  [COLOR %s]%s[/COLOR]' % (highlight_color, label_string))
			log_utils.log('Successfuly Removed Trakt Playback Progress:  %s  with resume_id=%s' % (label_string, str(resume_info[1])), __name__, level=log_utils.LOGDEBUG)
		else:
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(title=32315, message='Failed to Remove playback progress:  [COLOR %s]%s[/COLOR]' % (highlight_color, label_string))
			log_utils.log('Failed to Remove Trakt Playback Progress:  %s  with resume_id=%s' % (label_string, str(resume_info[1])), __name__, level=log_utils.LOGDEBUG)
	except: log_utils.error()

def scrobbleResetItems(imdb_ids, tvdb_dicts=None, refresh=True, widgetRefresh=False):
	control.busy()
	success = False
	try:
		content_type = 'movie' if not tvdb_dicts else 'episode'
		if content_type == 'movie':
			total_items = len(imdb_ids)
			resume_info = traktsync.fetch_bookmarks(imdb='', ret_all=True, ret_type='movies')
			for imdb in imdb_ids:
				try:
					resume_info_index = [resume_info.index(i) for i in resume_info if i['imdb'] == imdb][0]
					resume_dict = resume_info[resume_info_index]
					resume_id = resume_dict['resume_id']
					success = _authed_status('DELETE', '/sync/playback/%s' % resume_id) == 204
					items = [{'type': 'movie', 'movie': {'ids': {'imdb': imdb}}}]
					timestamp = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000Z")
					items[0].update({'paused_at': timestamp})
					if success:
						traktsync.delete_bookmark(items)
						log_utils.log('Successfuly Removed Trakt Playback Progress: movie title=%s  with resume_id=%s' % (resume_dict['title'], str(resume_id)), __name__, level=log_utils.LOGDEBUG)
					control.sleep(1000)
				except: log_utils.log('Failed to Remove Trakt Playback Progress: movie title=%s  with resume_id=%s' % (resume_dict['title'], str(resume_id)), __name__, level=log_utils.LOGDEBUG)
		else:
			total_items = len(tvdb_dicts)
			resume_info = traktsync.fetch_bookmarks(imdb='', ret_all=True, ret_type='episodes')
			for dict in tvdb_dicts:
				try:
					imdb, tvdb = dict.get('imdb'), dict.get('tvdb')
					season, episode = dict.get('season'), dict.get('episode')
					# v1.0.95: casaba solo por tvdb y borraba el primer punto de resume
					# de la serie, no el del episodio elegido
					_same = [i for i in resume_info if str(i.get('tvdb')) == str(tvdb) and str(i.get('season')) == str(season) and str(i.get('episode')) == str(episode)]
					if not _same: _same = [i for i in resume_info if str(i.get('tvdb')) == str(tvdb)]
					resume_info_index = resume_info.index(_same[0])
					resume_dict = resume_info[resume_info_index]
					resume_id = resume_dict['resume_id']
					success = _authed_status('DELETE', '/sync/playback/%s' % resume_id) == 204
					items = [{'type': 'episode', 'episode': {'season': season, 'number': episode}, 'show': {'ids': {'imdb': imdb, 'tvdb': tvdb}}}]
					timestamp = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000Z")
					items[0].update({'paused_at': timestamp})
					if success:
						traktsync.delete_bookmark(items)
						label_string = resume_dict['tvshowtitle'] + ' - ' + 'S%02dE%02d' % (int(season), int(episode))
						log_utils.log('Successfuly Removed Trakt Playback Progress:  tvshowtitle=%s  with resume_id=%s' % (label_string, str(resume_id)), __name__, level=log_utils.LOGDEBUG)
					control.sleep(1000)
				except: log_utils.log('Failed to Remove Trakt Playback Progress:  tvshowtitle=%s  with resume_id=%s' % (label_string, str(resume_id)), __name__, level=log_utils.LOGDEBUG)
		control.hide()
		if success:
			if refresh: control.refresh()
			if widgetRefresh: control.trigger_widget_refresh() # skinshortcuts handles the widget_refresh when plyback ends, but not a manual clear from Trakt Manager
			control.notification(title='Trakt Playback Progress Manager', message='Successfuly Removed %s Item%s' % (total_items, 's' if total_items >1 else ''))
			return True
		else: return False
	except:
		log_utils.error()
		return False


#############    SERVICE SYNC    ######################
def trakt_service_sync():
	while not control.monitor.abortRequested():
		control.sleep(5000) # wait 5sec in case of device wake from sleep
		if control.condVisibility('System.InternetState') and getTraktCredentialsInfo(): # run service in case user auth's trakt later
			activities = getTraktAsJson('/sync/last_activities', silent=True)
			# v1.0.95: si last_activities falla (Trakt caido, 5xx, token muerto)
			# cada sync_* volvia a pedirlo por su cuenta: nueve peticiones mas
			# que fallaban igual. Se salta la vuelta y se reintenta en la siguiente.
			if not activities or not isinstance(activities, dict):
				if control.monitor.waitForAbort(60*service_syncInterval): break
				continue
			if getSetting('bookmarks') == 'true' and getSetting('resume.source') == '1':
				sync_playbackProgress(activities)
			sync_watchedProgress(activities)
			if getSetting('indicators.alt') == '1':
				sync_watched(activities) # writes to traktsync.db as of 1-19-2022
			sync_hidden_progress(activities)
			sync_liked_lists(activities)
			sync_collection(activities)
			sync_watch_list(activities)
			sync_user_lists(activities) # populates user_lists table for Movie Lists / TV Lists menu
#			sync_popular_lists() # commented: each run hits 300+ lists with 2 probes each (~600 reqs); only run on user-triggered Force Sync
#			sync_trending_lists() # idem
		if control.monitor.waitForAbort(60*service_syncInterval): break

def force_traktSync(silent_confirm=False):
#	if not control.yesnoDialog(getLS(32056), '', ''): return
	if not silent_confirm:
		if not control.yesnoDialog('%s?' % (getLS(35066) % 'white'), '', ''): return
	control.busy()

	# wipe all tables and start fresh
	clr_traktSync = {'bookmarks': True, 'hiddenProgress': True, 'liked_lists': True, 'movies_collection': True, 'movies_watchlist': True,
							'public_lists': True, 'shows_collection': True, 'shows_watchlist': True, 'user_lists': True, 'watched': True}
	traktsync.delete_tables(clr_traktSync)

	# 2026 fix: split forced sync in 2 phases to avoid hammering the Trakt rate
	# limit (1000 GET req/5min). Personal data syncs first in parallel; public
	# lists (popular/trending) are deferred to a background thread because each
	# fans out ~600 probes (300 lists * 2 type checks).
	essential_funcs = [sync_playbackProgress, sync_watchedProgress, sync_watched,
						sync_hidden_progress, sync_liked_lists, sync_collection,
						sync_watch_list, sync_user_lists]
	threads = [Thread(target=i, kwargs={'forced': True}) for i in essential_funcs]
	for i in threads: i.start()
	for i in threads: i.join()

	control.hide()
	control.notification(message='Forced Trakt Sync Complete')

	# Public lists run in background, throttled internally with a Semaphore (see
	# sync_popular_lists / sync_trending_lists). UI is no longer blocked.
	def _public_lists_bg():
		try:
			sync_popular_lists(forced=True)
			sync_trending_lists(forced=True)
		except: log_utils.error()
	Thread(target=_public_lists_bg).start()

def sync_playbackProgress(activities=None, forced=False):
	try:
		link = '/sync/playback/?extended=full'
		if forced:
			items = getTraktAsJsonPaginated(link, silent=True)
			if items: traktsync.insert_bookmarks(items)
			log_utils.log('Forced - Trakt Playback Progress Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			db_last_paused = traktsync.last_sync('last_paused_at')
			activity = getPausedActivity(activities)
			if activity - db_last_paused >= 120: # do not sync unless 2 min difference or more
				log_utils.log('Trakt Playback Progress Sync Update...(local db latest "paused_at" = %s, trakt api latest "paused_at" = %s)' % \
									(str(db_last_paused), str(activity)), __name__, log_utils.LOGDEBUG)
				items = getTraktAsJsonPaginated(link, silent=True)
				if items: traktsync.insert_bookmarks(items)
	except: log_utils.error()

def sync_watchedProgress(activities=None, forced=False):
	try:
		from resources.lib.menus import episodes
		trakt_user = getSetting('trakt.username').strip()
		lang = control.apiLanguage()['tmdb']
		direct = getSetting('trakt.directProgress.scrape') == 'true'
		url = 'https://api.trakt.tv/users/me/watched/shows'
		progressActivity = getProgressActivity(activities)
		local_listCache = cache.timeout(episodes.Episodes().trakt_progress_list, url, trakt_user, lang, direct)
		if forced or (progressActivity > local_listCache):
			cache.get(episodes.Episodes().trakt_progress_list, 0, url, trakt_user, lang, direct)
			if forced: log_utils.log('Forced - Trakt Progress List Sync Complete', __name__, log_utils.LOGDEBUG)
			else: log_utils.log('Trakt Progress List Sync Update...(local db latest "list_cached_at" = %s, trakt api latest "progress_activity" = %s)' % \
									(str(local_listCache), str(progressActivity)), __name__, log_utils.LOGDEBUG)
	except: log_utils.error()

def sync_watched(activities=None, forced=False): # writes to traktsync.db as of 1-19-2022
	try:
		if forced:
			cachesyncMovies()
			log_utils.log('Forced - Trakt Watched Movie Sync Complete', __name__, log_utils.LOGDEBUG)
			cachesyncTVShows()
			control.sleep(5000)
			service_syncSeasons() # syncs all watched shows season indicators and counts
			log_utils.log('Forced - Trakt Watched Shows Sync Complete', __name__, log_utils.LOGDEBUG)
			traktsync.insert_syncSeasons_at()
		else:
			moviesWatchedActivity = getMoviesWatchedActivity(activities)
			db_movies_last_watched = timeoutsyncMovies()
			if moviesWatchedActivity - db_movies_last_watched >= 30: # do not sync unless 30secs more to allow for variation between trakt post and local db update.
				log_utils.log('Trakt Watched Movie Sync Update...(local db latest "watched_at" = %s, trakt api latest "watched_at" = %s)' % \
								(str(db_movies_last_watched), str(moviesWatchedActivity)), __name__, log_utils.LOGDEBUG)
				cachesyncMovies()
			episodesWatchedActivity = getEpisodesWatchedActivity(activities)
			db_last_syncTVShows = timeoutsyncTVShows()
			db_last_syncSeasons = traktsync.last_sync('last_syncSeasons_at')
			if any(episodesWatchedActivity > value for value in (db_last_syncTVShows, db_last_syncSeasons)):
				log_utils.log('Trakt Watched Shows Sync Update...(local db latest "watched_at" = %s, trakt api latest "watched_at" = %s)' % \
								(str(min(db_last_syncTVShows, db_last_syncSeasons)), str(episodesWatchedActivity)), __name__, log_utils.LOGDEBUG)
				_previous = traktsync.cache_existing(syncTVShows)
				cachesyncTVShows()
				control.sleep(5000)
				service_syncSeasons(previous=_previous) # only shows whose aired/watched counts changed
				traktsync.insert_syncSeasons_at()
	except: log_utils.error()

def sync_user_lists(activities=None, forced=False):
	try:
		link = '/users/me/lists'
		# 2026 Trakt API: /users/{u}/lists/{id}/items requires pagination since mid-Feb 2026.
		# We only need to know if the list contains movies/shows -> request limit=1 (cheapest).
		list_link = '/users/me/lists/%s/items/%s?limit=1&page=1'
		if forced:
			items = getTraktAsJsonPaginated(link, silent=True)
			if not items: return
			for i in items:
				i['content_type'] = ''
				trakt_id = i['ids']['trakt']
				list_items = getTraktAsJson(list_link % (trakt_id, 'movies'), silent=True)
				if not list_items or list_items == '[]': pass
				else: i['content_type'] = 'movies'
				list_items = getTraktAsJson(list_link % (trakt_id, 'shows'), silent=True)
				if not list_items or list_items == '[]': pass
				else: i['content_type'] = 'mixed' if i['content_type'] == 'movies' else 'shows'
				control.sleep(200)
			traktsync.insert_user_lists(items)
			log_utils.log('Forced - Trakt User Lists Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			db_last_lists_updatedat = traktsync.last_sync('last_lists_updatedat')
			user_listActivity = getUserListActivity(activities)
			if user_listActivity > db_last_lists_updatedat:
				log_utils.log('Trakt User Lists Sync Update...(local db latest "lists_updatedat" = %s, trakt api latest "lists_updatedat" = %s)' % \
									(str(db_last_lists_updatedat), str(user_listActivity)), __name__, log_utils.LOGDEBUG)
				items = getTraktAsJsonPaginated(link, silent=True)
				if not items: return
				for i in items:
					i['content_type'] = ''
					trakt_id = i['ids']['trakt']
					list_items = getTraktAsJson(list_link % (trakt_id, 'movies'), silent=True)
					if not list_items or list_items == '[]': pass
					else: i['content_type'] = 'movies'
					list_items = getTraktAsJson(list_link % (trakt_id, 'shows'), silent=True)
					if not list_items or list_items == '[]': pass
					else: i['content_type'] = 'mixed' if i['content_type'] == 'movies' else 'shows'
					control.sleep(200)
				traktsync.insert_user_lists(items)
	except: log_utils.error()

def sync_liked_lists(activities=None, forced=False):
	try:
		from threading import Semaphore
		# 2026 Trakt API: max 1000 items per page (Trakt silently caps anything higher).
		# Use the paginated helper to fetch every liked list across pages.
		link = '/users/likes/lists'
		# 2026 Trakt API: /users/{u}/lists/{id}/items requires pagination -> limit=1 for content_type probe.
		list_link = '/users/%s/lists/%s/items/%s?limit=1&page=1'
		db_last_liked = traktsync.last_sync('last_liked_at')
		listActivity = getListActivity(activities)
		if (listActivity > db_last_liked) or forced:
			if not forced: log_utils.log('Trakt Liked Lists Sync Update...(local db latest "liked_at" = %s, trakt api latest "liked_at" = %s)' % \
								(str(db_last_liked), str(listActivity)), __name__, log_utils.LOGDEBUG)
			items = getTraktAsJsonPaginated(link, page_size=1000, silent=True)
			if not items: return
			thrd_items = []
			# 2026 fix: throttle concurrent probes to stay under rate limits.
			sem = Semaphore(8)
			def items_list(i):
				with sem:
					list_item = i.get('list', {})
					if any(list_item.get('privacy', '') == value for value in ('private', 'friends')): return
					i['list']['content_type'] = ''
					list_owner_slug = list_item.get('user', {}).get('ids', {}).get('slug', '')
					trakt_id = list_item.get('ids', {}).get('trakt', '')
					list_items = getTraktAsJson(list_link % (list_owner_slug, trakt_id, 'movies'), silent=True)
					if not list_items or list_items == '[]': pass
					else: i['list']['content_type'] = 'movies'
					list_items = getTraktAsJson(list_link % (list_owner_slug, trakt_id, 'shows'), silent=True)
					if not list_items or list_items == '[]': pass
					else: i['list']['content_type'] = 'mixed' if i['list']['content_type'] == 'movies' else 'shows'
					thrd_items.append(i)
			threads = []
			for i in items:
				threads.append(Thread(target=items_list, args=(i,)))
			[i.start() for i in threads]
			[i.join() for i in threads]
			traktsync.insert_liked_lists(thrd_items)
			if forced: log_utils.log('Forced - Trakt Liked Lists Sync Complete', __name__, log_utils.LOGDEBUG)
	except: log_utils.error()

def _fetch_hidden_and_dropped():
	"""Series ocultas del progreso + series abandonadas (dropped).

	v1.0.95: Trakt (anuncio 'Dropped Shows', 24-mar-2025) pide a las apps que
	guarden la lista de series abandonadas y las quiten de su Up Next y de su
	progreso; los calendarios ya las filtra la propia API. El addon solo leia
	progress_watched, asi que una serie abandonada desde trakt.tv seguia
	saliendo en Progress. Las dos secciones estan paginadas (sin parametros
	Trakt devuelve solo la primera pagina corta). Devuelve None si alguna
	falla, para no vaciar la tabla local con datos a medias."""
	hidden = getTraktAsJsonPaginated('/users/hidden/progress_watched?type=show', silent=True)
	if hidden is None: return None
	dropped = getTraktAsJsonPaginated('/users/hidden/dropped', silent=True)
	if dropped is None: return None
	merged, seen = [], set()
	for i in (hidden or []) + (dropped or []):
		try:
			show = i.get('show') or {}
			key = (show.get('ids') or {}).get('trakt') or show.get('title')
			if not key or key in seen: continue
			seen.add(key)
			merged.append(i)
		except: pass
	return merged

def sync_hidden_progress(activities=None, forced=False):
	try:
		if forced:
			items = _fetch_hidden_and_dropped()
			if items is not None: traktsync.insert_hidden_progress(items)
			log_utils.log('Forced - Trakt Hidden Progress Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			db_last_hidden = traktsync.last_sync('last_hiddenProgress_at')
			hiddenActivity = getHiddenActivity(activities)
			if hiddenActivity > db_last_hidden:
				log_utils.log('Trakt Hidden Progress Sync Update...(local db latest "hidden_at" = %s, trakt api latest "hidden_at" = %s)' % \
									(str(db_last_hidden), str(hiddenActivity)), __name__, log_utils.LOGDEBUG)
				# v1.0.95: antes se insertaba aunque la descarga fallara (None) y
				# insert_hidden_progress borra la tabla ANTES del bucle: un corte de
				# red vaciaba las ocultas y reaparecian todas en Progress.
				items = _fetch_hidden_and_dropped()
				if items is not None: traktsync.insert_hidden_progress(items)
	except: log_utils.error()

def sync_collection(activities=None, forced=False):
	try:
		# 2026 Trakt API: /users/{u}/collection requires pagination (mandatory since end of Feb 2026,
		# default cap drops to 10 items by end of March 2026 without explicit limit/page params).
		link = '/users/me/collection/%s?extended=full'
		if forced:
			items = getTraktAsJsonPaginated(link % 'movies', silent=True)
			if items is not None: traktsync.insert_collection(items, 'movies_collection')
			items = getTraktAsJsonPaginated(link % 'shows', silent=True)
			if items is not None: traktsync.insert_collection(items, 'shows_collection')
			log_utils.log('Forced - Trakt Collection Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			db_last_collected = traktsync.last_sync('last_collected_at')
			collectedActivity = getCollectedActivity(activities)
			if collectedActivity > db_last_collected:
				log_utils.log('Trakt Collection Sync Update...(local db latest "collected_at" = %s, trakt api latest "collected_at" = %s)' % \
									(str(db_last_collected), str(collectedActivity)), __name__, log_utils.LOGDEBUG)
				# indicators = cachesyncMovies() # could maybe check watched status here to satisfy sort method
				items = getTraktAsJsonPaginated(link % 'movies', silent=True)
				if items is not None: traktsync.insert_collection(items, 'movies_collection')
				# indicators = cachesyncTVShows() # could maybe check watched status here to satisfy sort method
				items = getTraktAsJsonPaginated(link % 'shows', silent=True)
				if items is not None: traktsync.insert_collection(items, 'shows_collection')
	except: log_utils.error()

def sync_watch_list(activities=None, forced=False):
	try:
		# 2026 Trakt API: watchlist paginated via helper (max limit is 250 as of
		# June 30 2026). insert only when fetch succeeded (None = error) so a
		# transient API failure can never wipe the local watchlist tables.
		link = '/users/me/watchlist/%s?extended=full'
		if forced:
			items = getTraktAsJsonPaginated(link % 'movies', silent=True)
			if items is not None: traktsync.insert_watch_list(items, 'movies_watchlist')
			items = getTraktAsJsonPaginated(link % 'shows', silent=True)
			if items is not None: traktsync.insert_watch_list(items, 'shows_watchlist')
			log_utils.log('Forced - Trakt Watch List Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			db_last_watchList = traktsync.last_sync('last_watchlisted_at')
			watchListActivity = getWatchListedActivity(activities)
			needs_sync = (watchListActivity - db_last_watchList >= 60) # do not sync unless 1 min difference or more
			if not needs_sync and watchListActivity > 0:
				# 2026 self-heal: si Trakt reporta actividad de watchlist pero las
				# tablas locales estan vacias, el marcador quedo envenenado por una
				# sync fallida. Resincroniza aunque el marcador diga lo contrario.
				try:
					if not traktsync.fetch_watch_list('shows_watchlist') and not traktsync.fetch_watch_list('movies_watchlist'):
						needs_sync = True
						log_utils.log('Trakt Watch List Sync self-heal: local tables empty but trakt reports watchlist activity', __name__, log_utils.LOGDEBUG)
				except: pass
			if needs_sync:
				log_utils.log('Trakt Watch List Sync Update...(local db latest "watchlist_at" = %s, trakt api latest "watchlisted_at" = %s)' % \
									(str(db_last_watchList), str(watchListActivity)), __name__, log_utils.LOGDEBUG)
				items = getTraktAsJsonPaginated(link % 'movies', silent=True)
				if items is not None: traktsync.insert_watch_list(items, 'movies_watchlist')
				items = getTraktAsJsonPaginated(link % 'shows', silent=True)
				if items is not None: traktsync.insert_watch_list(items, 'shows_watchlist')
	except: log_utils.error()

def sync_popular_lists(forced=False):
	try:
		from datetime import timedelta
		from threading import Semaphore
		link = '/lists/popular'
		# 2026 Trakt API: split into two limit=1 probes (one per type) - robust against the
		# end-of-March 2026 change that drops the default limit to 10 items.
		list_link = '/users/%s/lists/%s/items/%s?limit=1&page=1'
		db_last_popularList = traktsync.last_sync('last_popularlist_at')
		cache_expiry = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=168)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		cache_expiry = int(cleandate.iso_2_utc(cache_expiry))
		if (cache_expiry > db_last_popularList) or forced:
			if not forced: log_utils.log('Trakt Popular Lists Sync Update...(local db latest "popularlist_at" = %s, cache expiry = %s)' % \
								(str(db_last_popularList), str(cache_expiry)), __name__, log_utils.LOGDEBUG)
			items = getTraktAsJsonPaginated(link, page_size=150, max_pages=2, silent=True)
			if not items: return
			thrd_items = []
			# 2026 fix: cap concurrent probes at 8 to stay under Trakt's per-user
			# rate limit (1000 GET req / 5 min). Without this the function
			# fired ~600 simultaneous probes (300 lists * 2 type checks).
			sem = Semaphore(8)
			def items_list(i):
				with sem:
					list_item = i.get('list', {})
					if any(list_item.get('privacy', '') == value for value in ('private', 'friends')): return
					trakt_id = list_item.get('ids', {}).get('trakt', '')
					exists = traktsync.fetch_public_list(trakt_id)
					if exists:
						local = int(cleandate.iso_2_utc(exists.get('updated_at', '')))
						remote = int(cleandate.iso_2_utc(list_item.get('updated_at', '')))
						if remote > local: pass
						else: return
					i['list']['content_type'] = ''
					list_owner_slug = list_item.get('user', {}).get('ids', {}).get('slug', '')
					movies_probe = getTraktAsJson(list_link % (list_owner_slug, trakt_id, 'movies'), silent=True)
					if movies_probe: i['list']['content_type'] = 'movies'
					shows_probe = getTraktAsJson(list_link % (list_owner_slug, trakt_id, 'shows'), silent=True)
					if shows_probe:
						i['list']['content_type'] = 'mixed' if i['list']['content_type'] == 'movies' else 'shows'
					thrd_items.append(i)
			threads = []
			for i in items:
				threads.append(Thread(target=items_list, args=(i,)))
			[i.start() for i in threads]
			[i.join() for i in threads]
			traktsync.insert_public_lists(thrd_items, service_type='last_popularlist_at', new_sync=False)
			if forced: log_utils.log('Forced - Trakt Popular Lists Sync Complete', __name__, log_utils.LOGDEBUG)
	except: log_utils.error()

def sync_trending_lists(forced=False):
	try:
		from datetime import timedelta
		from threading import Semaphore
		link = '/lists/trending'
		# 2026 Trakt API: split into two limit=1 probes (one per type) - robust against the
		# end-of-March 2026 change that drops the default limit to 10 items.
		list_link = '/users/%s/lists/%s/items/%s?limit=1&page=1'
		db_last_trendingList = traktsync.last_sync('last_trendinglist_at')
		cache_expiry = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		cache_expiry = int(cleandate.iso_2_utc(cache_expiry))
		if (cache_expiry > db_last_trendingList) or forced:
			if not forced: log_utils.log('Trakt Trending Lists Sync Update...(local db latest "trendinglist_at" = %s, cache expiry = %s)' % \
								(str(db_last_trendingList), str(cache_expiry)), __name__, log_utils.LOGDEBUG)
			items = getTraktAsJsonPaginated(link, page_size=150, max_pages=2, silent=True)
			if not items: return
			thrd_items = []
			# 2026 fix: cap concurrent probes at 8 (see sync_popular_lists for rationale).
			sem = Semaphore(8)
			def items_list(i):
				with sem:
					list_item = i.get('list', {})
					if any(list_item.get('privacy', '') == value for value in ('private', 'friends')): return
					trakt_id = list_item.get('ids', {}).get('trakt', '')
					exists = traktsync.fetch_public_list(trakt_id)
					if exists:
						local = int(cleandate.iso_2_utc(exists.get('updated_at', '')))
						remote = int(cleandate.iso_2_utc(list_item.get('updated_at', '')))
						if remote > local: pass
						else: return
					i['list']['content_type'] = ''
					list_owner_slug = list_item.get('user', {}).get('ids', {}).get('slug', '')
					movies_probe = getTraktAsJson(list_link % (list_owner_slug, trakt_id, 'movies'), silent=True)
					if movies_probe: i['list']['content_type'] = 'movies'
					shows_probe = getTraktAsJson(list_link % (list_owner_slug, trakt_id, 'shows'), silent=True)
					if shows_probe:
						i['list']['content_type'] = 'mixed' if i['list']['content_type'] == 'movies' else 'shows'
					thrd_items.append(i)
			threads = []
			for i in items:
				threads.append(Thread(target=items_list, args=(i,)))
			[i.start() for i in threads]
			[i.join() for i in threads]
			traktsync.insert_public_lists(thrd_items, service_type='last_trendinglist_at', new_sync=False)
			if forced: log_utils.log('Forced - Trakt Trending Lists Sync Complete', __name__, log_utils.LOGDEBUG)
	except: log_utils.error()

def auth_loop(device_codes):
	"""Una consulta a /oauth/device/token. Devuelve (token_json, estado) con
	estado 'ok', 'pending', 'slow_down' o 'stop:<HTTP>'.

	v1.0.95: antes pasaba por getTrakt(), que colapsa todo lo que no sea 200
	en None, y el dialogo seguia esperando hasta agotar el codigo aunque Trakt
	ya hubiera dicho que no. Codigos de la API: 400 pendiente, 404 codigo no
	valido, 409 ya usado, 410 caducado, 418 denegado, 429 ir mas despacio.
	Cualquier otro (p. ej. el limite de una Community App en cuentas gratuitas,
	22-jul-2026) corta la espera y se explica al usuario."""
	data = {'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET, 'code': device_codes['device_code']}
	try:
		req_headers = dict(headers)
		req_headers.pop('Authorization', None)
		r = session.post(urljoin(BASE_URL, '/oauth/device/token'), data=jsdumps(data), headers=req_headers, timeout=20)
	except Exception as exc:
		_hard_log('oauth/device/token: %s: %s' % (type(exc).__name__, exc), 3)
		return None, 'pending'
	code = r.status_code
	if code == 200:
		try: return r.json(), 'ok'
		except: return None, 'pending'
	if code == 400: return None, 'pending'
	if code == 429: return None, 'slow_down'
	if code >= 500: return None, 'pending'
	_hard_log('oauth/device/token HTTP %s | %s' % (code, (r.text or '')[:200].replace('\n', ' ')), 3)
	return None, 'stop:%s' % code

def _auth_stop_message(state):
	code = state.split(':', 1)[-1]
	if code == '404': return getLS(400880)
	if code == '409': return getLS(400881)
	if code == '410': return getLS(400882)
	if code == '418': return getLS(400883)
	return getLS(400884) % code

def _revoke_token():
	"""POST /oauth/revoke: libera la conexion en Trakt. Desde el limite de una
	Community App en cuentas gratuitas, desautorizar sin revocar dejaba el
	hueco ocupado y el usuario no podia conectar otra app."""
	token = getSetting('trakt.token')
	if not token: return False
	try:
		req_headers = dict(headers)
		req_headers.pop('Authorization', None)
		post = {'token': token, 'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET}
		r = session.post(urljoin(BASE_URL, '/oauth/revoke'), data=jsdumps(post), headers=req_headers, timeout=20)
		_hard_log('oauth/revoke HTTP %s' % r.status_code)
		return r.status_code == 200
	except Exception as exc:
		_hard_log('oauth/revoke FAILED: %s: %s' % (type(exc).__name__, exc), 3)
		return False

def auth():
	token = ''
	data = {'client_id': V2_API_KEY}
	device_codes = getTraktAsJson('oauth/device/code', post=data)
	# 2026 fix: validate device_codes before dereferencing keys (avoids
	# KeyError if Trakt returns 5xx / network error during initial pairing).
	if not device_codes or 'verification_url' not in device_codes or 'user_code' not in device_codes:
		control.notification(message='Trakt: failed to obtain device code, try again later.')
		return False
	verification_url = getLS(32513) % (highlight_color, str(device_codes['verification_url']))
	user_code = getLS(32514) % (highlight_color, str(device_codes['user_code']))
	try:
		qr_url = 'https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&color=f00&data='
		qr_icon = qr_url + quote_plus(device_codes['verification_url'])
		control.notification(message=device_codes['verification_url'], icon=qr_icon, time=15000)
	except: pass
	line = '%s\n%s'
	progressDialog = control.progressDialog
	progressDialog.create(getLS(32073))
	progressDialog.update(100, line % (verification_url, user_code))
	expires_in = int(device_codes['expires_in'])
	interval = int(device_codes['interval'])
	time_passed = expires_in
	while token == '':
		if progressDialog.iscanceled():
			progressDialog.close()
			return
		# 2026 fix: bail out cleanly when the device code expires instead of
		# polling forever. Python negative modulo would otherwise keep
		# triggering auth_loop() after time_passed reaches 0.
		if time_passed <= 0:
			try: progressDialog.close()
			except: pass
			control.notification(message='Trakt device code expired, please try again.')
			return False
		control.sleep(1000)
		time_passed -= 1
		try: progressDialog.update(int(time_passed / expires_in * 100))
		except: pass
		if not time_passed % interval:
			result, state = auth_loop(device_codes)
			if state == 'ok' and result and result.get('access_token'): token = result
			elif state == 'slow_down': interval += 5
			elif state.startswith('stop'):
				try: progressDialog.close()
				except: pass
				control.okDialog(title=getLS(32315), message=_auth_stop_message(state))
				return False
	try: progressDialog.close()
	except: pass
	if token:
		expires = _token_expiry(token)
		token, refresh = token['access_token'], token['refresh_token']
		clear_refresh_dead() # re-autorizado a mano: resetear anti-spam
		control.sleep(1000)
		headers['Authorization'] = 'Bearer %s' % token
		user = getTraktAsJson('users/me')
		# 2026 fix: validate user response (transient 5xx after auth would
		# otherwise raise TypeError on user['username']).
		if not user or not user.get('username'):
			control.notification(message='Trakt: authorized but user lookup failed, will retry on next sync.')
			control.setSetting('trakt.expires', expires)
			control.setSetting('trakt.refresh', refresh)
			control.setSetting('trakt.token', token)
			control.setSetting('trakt.isauthed', 'true')
			return True
		user = user['username']
		control.setSetting('trakt.username', str(user))
		control.setSetting('trakt.expires', expires)
		control.setSetting('trakt.refresh', refresh)
		control.setSetting('trakt.token', token)
		control.setSetting('trakt.isauthed', 'true')
		control.notification(message='Trakt authorization successful.')
		while control.condVisibility('Window.IsVisible(addonsettings)'): control.sleep(100)
		control.sleep(100)
		# 2026 UX fix: skip the second yes/no dialog right after authorization
		# (we just paired, the user clearly wants the data synced).
		force_traktSync(silent_confirm=True)
		return True
	control.notification(message='Trakt authorization failed.')
	return False

def deauth():
	if not getTraktCredentialsInfo():
		control.notification(message='Trakt is not authorized.')
		return False
	confirm = control.yesnoDialog('Are you sure you want to deauthorize Trakt?', 'You will need to re-authorize to use Trakt features.', '', heading='Trakt')
	if not confirm: return False
	try:
		_revoke_token() # best effort: aunque falle, la desautorizacion local sigue
		setSetting('trakt.username', '')
		setSetting('trakt.token', '')
		setSetting('trakt.refresh', '')
		setSetting('trakt.expires', '')
		setSetting('trakt.isauthed', 'false')
		headers.pop('Authorization', None)
		clr_traktSync = {'bookmarks': True, 'hiddenProgress': True, 'liked_lists': True, 'movies_collection': True, 'movies_watchlist': True,
							'public_lists': True, 'shows_collection': True, 'shows_watchlist': True, 'user_lists': True, 'watched': True}
		try: traktsync.delete_tables(clr_traktSync)
		except: pass
		control.notification(message='Trakt deauthorization successful.')
		return True
	except:
		log_utils.error()
		control.notification(message='Trakt deauthorization failed.')
		return False

def account_info_to_dialog():
	from datetime import timedelta
	try:
		control.busy()
		account_info = getTraktAsJson('users/settings')
		stats = getTraktAsJson('users/%s/stats' % account_info['user']['ids']['slug'])
		username = account_info['user']['username']
		timezone = account_info['account']['timezone']
		joined = cleandate.datetime_from_string(account_info['user']['joined_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
		private = account_info['user']['private']
		vip = account_info['user']['vip']
		if vip: vip = '%s Years' % str(account_info['user']['vip_years'])
		total_given_ratings = stats['ratings']['total']
		movies_collected = stats['movies']['collected']
		movies_watched = stats['movies']['watched']
		movie_minutes = stats['movies']['minutes']
		if movie_minutes == 0: movies_watched_minutes = ['0 days', '0:00:00']
		elif movie_minutes < 1440: movies_watched_minutes = ['0 days', '{:0>8}'.format(str(timedelta(minutes=movie_minutes)))]
		else: movies_watched_minutes = ('{:0>8}'.format(str(timedelta(minutes=movie_minutes)))).split(', ')
		movies_watched_minutes = ('%s %s hours %s minutes' % (movies_watched_minutes[0], movies_watched_minutes[1].split(':')[0], movies_watched_minutes[1].split(':')[1]))
		shows_collected = stats['shows']['collected']
		shows_watched = stats['shows']['watched']
		episodes_watched = stats['episodes']['watched']
		episode_minutes = stats['episodes']['minutes']
		if episode_minutes == 0: episodes_watched_minutes = ['0 days', '0:00:00']
		elif episode_minutes < 1440: episodes_watched_minutes = ['0 days', '{:0>8}'.format(str(timedelta(minutes=episode_minutes)))]
		else: episodes_watched_minutes = ('{:0>8}'.format(str(timedelta(minutes=episode_minutes)))).split(', ')
		episodes_watched_minutes = ('%s %s hours %s minutes' % (episodes_watched_minutes[0], episodes_watched_minutes[1].split(':')[0], episodes_watched_minutes[1].split(':')[1]))
		heading = control.lang(32315)
		items = []
		items += ['[B]Username:[/B] %s' % username]
		items += ['[B]Timezone:[/B] %s' % timezone]
		items += ['[B]Joined:[/B] %s' % joined]
		items += ['[B]Private:[/B] %s' % private]
		items += ['[B]VIP Status:[/B] %s' % vip]
		items += ['[B]Ratings Given:[/B] %s' % str(total_given_ratings)]
		items += ['[B]Movies:[/B] [B]%s[/B] Collected, [B]%s[/B] Watched for [B]%s[/B]' % (movies_collected, movies_watched, movies_watched_minutes)]
		items += ['[B]Shows:[/B] [B]%s[/B] Collected, [B]%s[/B] Watched' % (shows_collected, shows_watched)]
		items += ['[B]Episodes:[/B] [B]%s[/B] Watched for [B]%s[/B]' % (episodes_watched, episodes_watched_minutes)]
		control.hide()
		return control.selectDialog(items, heading)
	except:
		log_utils.error()
		return
