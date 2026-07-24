# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on - SIMKL integration
	========================================
	Espejo de trakt.py pero más simple:
	  - PIN flow (sin client_secret, sin redirect_uri)
	  - Tokens de ~5 años, SIN refresh_token (en 401 → reauth manual)
	  - Endpoints: /scrobble/{start,pause,stop,checkin}, /sync/{activities,history,
	    all-items,watched,playback}, /users/settings

	Docs: https://api.simkl.org/  (revamp 2026-05-22)
"""

from datetime import datetime, timezone
from json import dumps as jsdumps
from threading import Lock
from time import time
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin, quote_plus
from urllib3.util.retry import Retry

from resources.lib.database import simklsync
from resources.lib.modules import cleandate
from resources.lib.modules import control
from resources.lib.modules import log_utils

getLS = control.lang
getSetting = control.setting
setSetting = control.setSetting

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = 'https://api.simkl.com'
PIN_VERIFICATION_URL = 'https://simkl.com/pin'

# Public client_id registered for luc_kodi by apoyotech. Same model as
# V2_API_KEY in trakt.py — public credentials embedded in an open-source
# Kodi addon are standard practice (the user has to be able to talk to the
# service without registering their own app).
#
# NOTE on client_secret: SIMKL's PIN flow (the one we use, suitable for
# headless devices like Shield TV) does NOT require client_secret per the
# official docs at https://api.simkl.org/api-reference/pin — only client_id.
# We intentionally do NOT embed the client_secret to minimise attack surface.
# If a future change to OAuth code-flow is added (e.g. for a web companion),
# the secret would need to be stored server-side, never embedded here.
#
# The `simkl.client_id` setting acts as a per-user override (advanced) — if
# set, it takes precedence over this hardcoded value.
SIMKL_CLIENT_ID = getSetting('simkl.client_id') or 'b10535f8971b056595e796e42353d15c341e7b2176183670161335869fb4d336'

# Required URL params on EVERY request (breaking change 2026-04-22).
APP_NAME = 'luc_kodi'
try:
	APP_VERSION = control.addon('plugin.video.luc_kodi').getAddonInfo('version')
except Exception:
	APP_VERSION = '1.0.18'

# Tokens advertise expires_in=157680000 (~5 years). We don't truly need to
# track expiry since there's no refresh, but we store it to help diagnostics.
TOKEN_DEFAULT_TTL = 157680000  # 5 years

# Per-user scrobble throttle. Server rejects with 429 if a 2nd scrobble call
# for the same user lands within 20s. We apply a softer 5s local cooldown
# (across all items) so a rapid play/pause sequence doesn't trip the lock.
_SCROBBLE_THROTTLE_SECONDS = 5.0
_scrobble_lock = Lock()
_last_scrobble_at = {'ts': 0.0}

# ---------------------------------------------------------------------------
# HTTP session with retry pool (same pattern as trakt.py)
# ---------------------------------------------------------------------------
session = requests.Session()
# OJO: NO reintentar 429 aquí. El 429 se gestiona MANUALMENTE en getSimkl()
# respetando Retry-After. Reintentar 429 a nivel urllib3 con backoff corto
# dispara el detector de ráfagas de SIMKL (3+ peticiones/segundo desde la
# misma IP = badge BURST en API Analytics) y puede acabar en bloqueo
# automático del client_id (412 para TODOS los usuarios del addon).
# backoff_factor=1.0: reintentos de 5xx a ~1s, 2s, 4s — nunca en ráfaga.
retries = Retry(total=3, backoff_factor=1.0,
				status_forcelist=[500, 502, 503, 504, 520, 521, 522, 524, 530])
session.mount('https://api.simkl.com', HTTPAdapter(max_retries=retries, pool_maxsize=100))

highlight_color = control.getHighlightColor()
server_notification = getSetting('simkl.server.notifications') == 'true'
service_syncInterval = int(getSetting('simkl.service.syncInterval')) if getSetting('simkl.service.syncInterval') else 15


# ---------------------------------------------------------------------------
# Core request helper
# ---------------------------------------------------------------------------
def _required_params():
	"""URL params required on EVERY simkl.com request since 2026-04-22."""
	return {
		'client_id':   SIMKL_CLIENT_ID,
		'app-name':    APP_NAME,
		'app-version': APP_VERSION,
	}

def _headers(authed=True):
	h = {
		'Content-Type': 'application/json',
		'User-Agent':   '%s/%s' % (APP_NAME, APP_VERSION),
	}
	if authed:
		tok = getSetting('simkl.token')
		if tok: h['Authorization'] = 'Bearer %s' % tok
	return h

def getSimkl(url, post=None, params=None, method=None, silent=False):
	"""
	Generic SIMKL HTTP call. Mirrors trakt.getTrakt() shape:
	  - returns the raw Response object on 2xx, None otherwise
	  - merges _required_params() into the query string automatically
	  - handles 401 (clear creds, notify user — NO refresh dance like Trakt)
	  - handles 429 with Retry-After + bounded reintentos (max 3)
	"""
	try:
		if not url.startswith(BASE_URL):
			url = urljoin(BASE_URL, url)
		body = jsdumps(post) if post is not None else None

		# Merge URL params: caller-provided takes precedence over required ones.
		qp = _required_params()
		if params: qp.update(params)

		headers = _headers(authed=True)

		if method:
			m = method.upper()
		else:
			m = 'POST' if post is not None else 'GET'

		if m == 'GET':
			response = session.get(url, params=qp, headers=headers, timeout=20)
		elif m == 'DELETE':
			response = session.delete(url, params=qp, headers=headers, timeout=20)
		else:
			response = session.post(url, params=qp, data=body, headers=headers, timeout=20)

		status_code = str(response.status_code)
		_error_handler(url, response, status_code, silent=silent)

		if response is not None and status_code in ('200', '201', '204'):
			return response
		elif status_code == '401':
			# Token revoked/expired. SIMKL has NO refresh — but a SINGLE 401
			# could also be a transient server hiccup. We DO NOT auto-clear
			# credentials anymore (would log out a user on every transient
			# blip). Just warn and let the user manually deauth via settings
			# when the situation is persistent.
			if getSetting('simkl.isauthed') == 'true':
				log_utils.log('SIMKL 401 — token may be revoked or this is transient. '
								'Not clearing creds automatically. User can manually deauth if persistent.',
								__name__, log_utils.LOGWARNING)
				if not silent and server_notification and not control.condVisibility('Player.HasVideo'):
					control.notification(title='SIMKL', message='Token rejected — re-auth manually if it persists.')
			return None
		elif status_code == '412':
			# client_id failed — quota / suspension. NEVER silently retry.
			if not silent:
				log_utils.log('SIMKL 412 client_id_failed — quota or suspension active.', __name__, log_utils.LOGWARNING)
			return None
		elif status_code == '429':
			# Per SIMKL docs: respect Retry-After and retry ONCE. If still 429,
			# give up — the next sync tick will retry (15 min default). Avoids
			# (a) hammering a server that explicitly said back off, and
			# (b) blocking the player/service thread for >1 minute on a stuck rate limit.
			ra = int(response.headers.get('Retry-After', 30))
			if not silent and server_notification and not control.condVisibility('Player.HasVideo'):
				control.notification(title='SIMKL', message='Throttling — sleeping %s s' % ra)
			control.sleep((ra + 1) * 1000)
			try:
				if m == 'GET':
					response = session.get(url, params=qp, headers=headers, timeout=20)
				elif m == 'DELETE':
					response = session.delete(url, params=qp, headers=headers, timeout=20)
				else:
					response = session.post(url, params=qp, data=body, headers=headers, timeout=20)
			except Exception:
				return None
			status_code = str(response.status_code)
			if status_code in ('200', '201', '204'): return response
			# Still failing — bail out; next sync tick will retry.
			return None
		else:
			return None
	except Exception:
		log_utils.error()
		return None

def _error_handler(url, response, status_code, silent=False):
	if status_code in ('200', '201', '204', '429', '401', '412'): return
	if not silent and server_notification and not control.condVisibility('Player.HasVideo'):
		# Mirror trakt.error_handler verbosity: only notify on real failures.
		msg = 'SIMKL %s: %s' % (status_code, str(url).split('?')[0])
		log_utils.log(msg, __name__, log_utils.LOGDEBUG)


def getSimklAsJson(url, post=None, params=None, method=None, silent=False):
	r = getSimkl(url, post=post, params=params, method=method, silent=silent)
	if r is None: return None
	try:
		return r.json()
	except Exception:
		log_utils.error()
		return None


# ---------------------------------------------------------------------------
# Credentials helpers
# ---------------------------------------------------------------------------
def getSimklCredentialsInfo():
	username = (getSetting('simkl.username') or '').strip()
	token    = (getSetting('simkl.token') or '').strip()
	return bool(username and token)

def getSimklIndicatorsInfo():
	"""Mirror of trakt.getTraktIndicatorsInfo — used by playcount.py."""
	# Use SIMKL as indicator source only if user opted-in AND auth is valid.
	return bool(getSetting('simkl.indicators') == 'true' and getSimklCredentialsInfo())

def _clear_creds():
	for k in ('simkl.username', 'simkl.token', 'simkl.user_id', 'simkl.expires', 'simkl.isauthed'):
		try: setSetting(k, '' if k != 'simkl.isauthed' else 'false')
		except Exception: pass
	# Invalidate luc_kodi_settings window cache so the next getSetting() picks up
	# the fresh empty values immediately. onSettingsChanged() only fires when
	# the user closes the settings dialog; programmatic setSetting() doesn't
	# trigger it, so without this clearProperty, getSetting() would keep
	# returning the stale cached token.
	try:
		control.homeWindow.clearProperty('luc_kodi_settings')
	except Exception:
		pass


# ---------------------------------------------------------------------------
# PIN flow auth
# ---------------------------------------------------------------------------
def _request_pin():
	"""Step 1 of PIN flow → returns dict with user_code, verification_uri,
	expires_in, interval. SIMKL spec: GET /oauth/pin?client_id=..."""
	r = getSimkl('/oauth/pin', method='GET', silent=True)
	if r is None: return None
	try: return r.json()
	except Exception: return None

def _poll_pin(user_code):
	"""Step 3 of PIN flow → GET /oauth/pin/{USER_CODE}?client_id=..."""
	r = getSimkl('/oauth/pin/%s' % quote_plus(str(user_code)), method='GET', silent=True)
	if r is None: return None
	try: return r.json()
	except Exception: return None

def auth():
	"""Interactive PIN flow with a progress dialog. Mirror of trakt.auth()."""
	pin = _request_pin()
	if not pin or 'user_code' not in pin:
		control.notification(title='SIMKL', message='Failed to obtain PIN code, try again later.')
		return False

	user_code = str(pin['user_code'])
	verification_uri = pin.get('verification_uri') or pin.get('verification_url') or PIN_VERIFICATION_URL
	expires_in = int(pin.get('expires_in', 900))
	interval   = max(int(pin.get('interval', 5)), 5)  # respect server's pacing

	# QR notification (parity with trakt.auth)
	try:
		qr_url  = 'https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&color=f00&data='
		qr_icon = qr_url + quote_plus('%s?pin=%s' % (verification_uri, user_code))
		control.notification(title='SIMKL', message='%s  |  %s' % (verification_uri, user_code),
								icon=qr_icon, time=15000)
	except Exception:
		pass

	# Progress dialog
	progressDialog = control.progressDialog
	progressDialog.create('SIMKL authorization')
	line = '[COLOR %s]Visit:[/COLOR] %s\n[COLOR %s]Enter code:[/COLOR] %s' % (
		highlight_color, verification_uri, highlight_color, user_code)
	progressDialog.update(100, line)

	time_passed = expires_in
	token_resp = None
	while True:
		if progressDialog.iscanceled():
			try: progressDialog.close()
			except Exception: pass
			return False
		if time_passed <= 0:
			try: progressDialog.close()
			except Exception: pass
			control.notification(title='SIMKL', message='PIN expired, please try again.')
			return False

		control.sleep(1000)
		time_passed -= 1
		try: progressDialog.update(int(time_passed / expires_in * 100))
		except Exception: pass

		# Poll only every `interval` seconds.
		if (expires_in - time_passed) % interval != 0:
			continue

		resp = _poll_pin(user_code)
		if not resp:
			continue

		# Docs: {"result":"KO","message":"Authorization pending"} while waiting,
		# {"result":"OK","access_token":"..."} on success. Trap: if we keep
		# polling after success, server falls back to "create new code" and
		# returns a new device_code. Detect that and STOP.
		if 'device_code' in resp and 'user_code' in resp and resp.get('user_code') != user_code:
			log_utils.log('SIMKL: original PIN already consumed; stopping poll.', __name__, log_utils.LOGDEBUG)
			break

		if resp.get('result') == 'OK' and resp.get('access_token'):
			token_resp = resp
			break
		# Otherwise: {"result":"KO", ...} → keep polling

	try: progressDialog.close()
	except Exception: pass

	if not token_resp or not token_resp.get('access_token'):
		control.notification(title='SIMKL', message='Authorization failed.')
		return False

	token = token_resp['access_token']
	setSetting('simkl.token', token)
	setSetting('simkl.expires', str(time() + TOKEN_DEFAULT_TTL))
	# Invalidate window cache so the next getSetting('simkl.token') in _headers()
	# returns the fresh token rather than relying on control.setting()'s
	# self-healing fallback (which only kicks in for empty-string cache entries).
	try:
		control.homeWindow.clearProperty('luc_kodi_settings')
	except Exception:
		pass

	# Pull user identity for the username field. /users/settings is POST per docs.
	control.sleep(500)
	settings = getSimklAsJson('/users/settings', method='POST', silent=True)
	if not settings:
		# Authorized but identity lookup failed — keep token, retry on sync.
		setSetting('simkl.isauthed', 'true')
		setSetting('simkl.username', 'SIMKL user')
		control.notification(title='SIMKL', message='Authorized — user lookup will retry on next sync.')
		return True

	# /users/settings returns {"user":{"name":..., "id":..., "joined_at":...,
	#   "avatar":..., "bio":..., "loc":..., "gender":...}, "account":{"id":...,
	#   "timezone":..., "type":"free"|"vip"}, "connections":{...}}
	try:
		username = settings.get('user', {}).get('name') or 'SIMKL user'
		user_id  = str(settings.get('user', {}).get('id') or '')
	except Exception:
		username, user_id = 'SIMKL user', ''
	setSetting('simkl.username', str(username))
	setSetting('simkl.user_id',  user_id)
	setSetting('simkl.isauthed', 'true')
	# Invalidate cache so the next getSimklCredentialsInfo() / sync tick sees
	# the fresh credentials without waiting for the user to open the settings
	# dialog.
	try:
		control.homeWindow.clearProperty('luc_kodi_settings')
	except Exception:
		pass

	control.notification(title='SIMKL', message='Authorization successful.')

	# Trigger initial sync (silent, no double-confirm).
	while control.condVisibility('Window.IsVisible(addonsettings)'): control.sleep(100)
	control.sleep(100)
	try:
		force_simklSync(silent_confirm=True)
	except Exception:
		log_utils.error()
	return True


def deauth():
	if not getSimklCredentialsInfo():
		control.notification(title='SIMKL', message='SIMKL is not authorized.')
		return False
	if not control.yesnoDialog('Are you sure you want to deauthorize SIMKL?',
								'You will need to re-authorize to use SIMKL features.', '', heading='SIMKL'):
		return False
	try:
		_clear_creds()
		# Wipe sync tables — same idea as trakt deauth.
		try:
			simklsync.delete_tables({'bookmarks': True, 'watched_movies': True, 'watched_shows': True,
									 'movies_watchlist': True, 'shows_watchlist': True,
									 'anime_watchlist': True, 'service': True})
		except Exception:
			pass
		control.notification(title='SIMKL', message='Deauthorization successful.')
		return True
	except Exception:
		log_utils.error()
		control.notification(title='SIMKL', message='Deauthorization failed.')
		return False


def account_info_to_dialog():
	from datetime import timedelta
	try:
		control.busy()
		info = getSimklAsJson('/users/settings', method='POST')
		if not info:
			control.hide()
			control.notification(title='SIMKL', message='Account info unavailable.')
			return
		user    = info.get('user', {}) or {}
		account = info.get('account', {}) or {}

		username = user.get('name') or '—'
		joined_raw = user.get('joined_at') or ''
		try:
			joined = cleandate.datetime_from_string(joined_raw, '%Y-%m-%dT%H:%M:%SZ')
			joined_str = joined.strftime('%Y-%m-%d') if joined else joined_raw
		except Exception:
			joined_str = joined_raw

		plan = (account.get('type') or 'free').upper()
		tz   = account.get('timezone') or '—'
		bio  = (user.get('bio') or '').strip()[:120]

		lines = [
			'[B]SIMKL[/B] account info',
			'',
			'[COLOR %s]Username:[/COLOR] %s' % (highlight_color, username),
			'[COLOR %s]Plan:[/COLOR] %s' % (highlight_color, plan),
			'[COLOR %s]Timezone:[/COLOR] %s' % (highlight_color, tz),
			'[COLOR %s]Joined:[/COLOR] %s' % (highlight_color, joined_str),
		]
		if bio:
			lines += ['', '[COLOR %s]Bio:[/COLOR] %s' % (highlight_color, bio)]

		control.hide()
		control.okDialog('SIMKL Account', '\n'.join(lines))
	except Exception:
		log_utils.error()
		control.hide()


# ---------------------------------------------------------------------------
# Activity API — the cheap "is anything new?" probe
# ---------------------------------------------------------------------------
def getActivity():
	"""
	POST /sync/activities → JSON of last-modified timestamps per bucket.
	Returns the latest activity epoch across ALL buckets (used by service
	loop to decide whether anything synced needs a refresh).
	"""
	try:
		i = getSimklAsJson('/sync/activities', method='POST', silent=True)
		if not i: return 0
		# Walk the response and extract every ISO timestamp we can find.
		activities = []
		def _walk(node):
			if isinstance(node, dict):
				for k, v in node.items():
					if isinstance(v, str) and ('T' in v and ':' in v):
						activities.append(v)
					else:
						_walk(v)
			elif isinstance(node, list):
				for v in node: _walk(v)
		_walk(i)
		if not activities: return 0
		stamps = []
		for ts in activities:
			try: stamps.append(int(cleandate.iso_2_utc(ts)))
			except Exception: pass
		return max(stamps) if stamps else 0
	except Exception:
		log_utils.error()
		return 0


def getMoviesWatchedActivity(activities=None):
	try:
		i = activities or getSimklAsJson('/sync/activities', method='POST', silent=True)
		if not i: return 0
		# tv_shows / anime / movies buckets each carry their own last-modified.
		stamp = i.get('movies', {}).get('all', '') or i.get('movies', {}).get('completed', '')
		if not stamp: return 0
		return int(cleandate.iso_2_utc(stamp))
	except Exception:
		log_utils.error()
		return 0

def getEpisodesWatchedActivity(activities=None):
	try:
		i = activities or getSimklAsJson('/sync/activities', method='POST', silent=True)
		if not i: return 0
		stamps = []
		for key in ('tv_shows', 'anime'):
			s = i.get(key, {}).get('all', '') or i.get(key, {}).get('completed', '')
			if s:
				try: stamps.append(int(cleandate.iso_2_utc(s)))
				except Exception: pass
		return max(stamps) if stamps else 0
	except Exception:
		log_utils.error()
		return 0


def getPausedActivity(activities=None):
	try:
		i = activities or getSimklAsJson('/sync/activities', method='POST', silent=True)
		if not i: return 0
		stamps = []
		# /sync/playback is keyed under each type bucket (post-2025-10-08).
		for key in ('movies', 'tv_shows', 'anime'):
			s = i.get(key, {}).get('playback', '') or i.get(key, {}).get('paused_at', '')
			if s:
				try: stamps.append(int(cleandate.iso_2_utc(s)))
				except Exception: pass
		return max(stamps) if stamps else 0
	except Exception:
		log_utils.error()
		return 0


# ---------------------------------------------------------------------------
# Watched indicators — mirror of trakt.cachesyncMovies / cachesyncTVShows
# ---------------------------------------------------------------------------
def cachesyncMovies(timeout=0):
	indicators = simklsync.get(syncMovies, timeout)
	return indicators

def syncMovies():
	"""Returns list of imdb IDs of movies the user has marked watched."""
	try:
		if not getSimklCredentialsInfo(): return None
		# /sync/all-items/movies/completed returns the user's completed movies.
		items = getSimklAsJson('/sync/all-items/movies/completed', method='GET', silent=True)
		if not items: return None
		movies = items.get('movies', []) if isinstance(items, dict) else []
		out = []
		for m in movies:
			ids = (m.get('movie') or {}).get('ids') or m.get('ids') or {}
			imdb = ids.get('imdb')
			if imdb: out.append(str(imdb))
		return out
	except Exception:
		log_utils.error()
		return None

def timeoutsyncMovies():
	return simklsync.timeout(syncMovies)

def cachesyncTVShows(timeout=0):
	indicators = simklsync.get(syncTVShows, timeout)
	return indicators

def syncTVShows():
	"""Returns parallel structure to trakt.syncTVShows:
	[({'imdb':..., 'tvdb':..., 'tmdb':..., 'simkl':...}, total_eps, [(s,e),(s,e)]), ...]
	"""
	try:
		if not getSimklCredentialsInfo(): return None
		items = getSimklAsJson('/sync/all-items/shows', method='GET', silent=True)
		if not items: return None
		shows = items.get('shows', []) if isinstance(items, dict) else []
		anime = items.get('anime', []) if isinstance(items, dict) else []
		merged = []
		for show in (shows + anime):
			s = show.get('show') or show.get('anime') or {}
			ids = s.get('ids') or {}
			seasons = show.get('seasons') or []
			watched_eps = []
			total = 0
			for sea in seasons:
				snum = sea.get('number')
				for ep in (sea.get('episodes') or []):
					enum = ep.get('number')
					if snum is not None and enum is not None and ep.get('watched_at'):
						watched_eps.append((int(snum), int(enum)))
						total += 1
			merged.append((
				{'imdb': str(ids.get('imdb', '')), 'tvdb': str(ids.get('tvdb', '')),
				 'tmdb': str(ids.get('tmdb', '')), 'simkl': str(ids.get('simkl', ''))},
				total, watched_eps
			))
		return merged
	except Exception:
		log_utils.error()
		return None

def timeoutsyncTVShows():
	return simklsync.timeout(syncTVShows)


# ---------------------------------------------------------------------------
# Mark watched / unwatched — mirrors trakt.markMovieAsWatched API surface
# ---------------------------------------------------------------------------
def markMovieAsWatched(imdb):
	try:
		if not str(imdb).startswith('tt'): imdb = 'tt' + str(imdb)
		body = {'movies': [{'ids': {'imdb': imdb}}]}
		r = getSimkl('/sync/history', post=body)
		return r is not None
	except Exception:
		log_utils.error()
		return False

def markMovieAsNotWatched(imdb):
	try:
		if not str(imdb).startswith('tt'): imdb = 'tt' + str(imdb)
		body = {'movies': [{'ids': {'imdb': imdb}}]}
		r = getSimkl('/sync/history/remove', post=body)
		return r is not None
	except Exception:
		log_utils.error()
		return False

def markEpisodeAsWatched(imdb, tvdb, season, episode):
	try:
		if imdb and not str(imdb).startswith('tt'): imdb = 'tt' + str(imdb)
		body = {'shows': [{
			'ids': {'imdb': imdb, 'tvdb': str(tvdb) if tvdb else ''},
			'seasons': [{'number': int(season), 'episodes': [{'number': int(episode)}]}],
		}]}
		r = getSimkl('/sync/history', post=body)
		return r is not None
	except Exception:
		log_utils.error()
		return False

def markEpisodeAsNotWatched(imdb, tvdb, season, episode):
	try:
		if imdb and not str(imdb).startswith('tt'): imdb = 'tt' + str(imdb)
		body = {'shows': [{
			'ids': {'imdb': imdb, 'tvdb': str(tvdb) if tvdb else ''},
			'seasons': [{'number': int(season), 'episodes': [{'number': int(episode)}]}],
		}]}
		r = getSimkl('/sync/history/remove', post=body)
		return r is not None
	except Exception:
		log_utils.error()
		return False


# ---------------------------------------------------------------------------
# Scrobble — the main integration point with player.py
# ---------------------------------------------------------------------------
def _build_scrobble_body(imdb, tmdb, tvdb, season, episode, progress):
	"""Construct the per-type body for /scrobble/{start,pause,stop}."""
	ids = {}
	if imdb:
		_i = str(imdb)
		if not _i.startswith('tt'): _i = 'tt' + _i
		ids['imdb'] = _i
	if tmdb: ids['tmdb'] = int(str(tmdb)) if str(tmdb).isdigit() else str(tmdb)
	if tvdb: ids['tvdb'] = int(str(tvdb)) if str(tvdb).isdigit() else str(tvdb)

	body = {'progress': float(progress)}
	if not episode:
		body['movie'] = {'ids': ids}
	else:
		body['show']    = {'ids': ids}
		body['episode'] = {'season': int(season), 'number': int(episode)}
	return body

def _scrobble_call(action, imdb, tmdb, tvdb, season, episode, progress):
	"""Internal: dispatch /scrobble/{action} with local cooldown + lock."""
	global _last_scrobble_at
	with _scrobble_lock:
		now = time()
		# Local cooldown: refuse near-duplicate calls (avoids server 20s lock).
		if action != 'stop' and (now - _last_scrobble_at['ts']) < _SCROBBLE_THROTTLE_SECONDS:
			log_utils.log('SIMKL scrobble %s skipped (cooldown).' % action, __name__, log_utils.LOGDEBUG)
			return False
		_last_scrobble_at['ts'] = now

	try:
		body = _build_scrobble_body(imdb, tmdb, tvdb, season, episode, progress)
		r = getSimkl('/scrobble/%s' % action, post=body, silent=True)
		if r is None:
			log_utils.log('SIMKL scrobble/%s failed (imdb=%s tvdb=%s S%sE%s prog=%s)' %
							(action, imdb, tvdb, season, episode, progress),
							__name__, log_utils.LOGDEBUG)
			return False
		if getSetting('simkl.scrobble.notify') == 'true':
			control.notification(title='SIMKL', message='Scrobble %s OK' % action)
		log_utils.log('SIMKL scrobble/%s OK (imdb=%s tvdb=%s S%sE%s prog=%s)' %
						(action, imdb, tvdb, season, episode, progress),
						__name__, log_utils.LOGDEBUG)
		return True
	except Exception:
		log_utils.error()
		return False


def scrobbleStart(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
	if not getSimklCredentialsInfo(): return False
	return _scrobble_call('start', imdb, tmdb, tvdb, season, episode, watched_percent)

def scrobblePause(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
	if not getSimklCredentialsInfo(): return False
	return _scrobble_call('pause', imdb, tmdb, tvdb, season, episode, watched_percent)

def invalidateSectionCaches():
	"""Invalida los caches de las secciones SIMKL (siguiente-no-visto y
	Mi-Progreso) para que se refresquen al instante tras un scrobble/stop.

	Autónomo: solo toca caches de SIMKL. Se llama tras marcar un episodio o
	película como visto al >=80%, para que 'el siguiente episodio' aparezca
	inmediatamente sin esperar al tick del servicio (~15 min).
	"""
	try:
		from resources.lib.database import cache
		from resources.lib.menus.episodes import Episodes
		ep = Episodes(notifications=False)
		try: cache.remove(ep.simkl_progress_list, ep.simklprogress_link)
		except Exception: pass
		try: cache.remove(ep.simkl_playback_list, ep.simklplayback_link)
		except Exception: pass
	except Exception:
		log_utils.error()


def scrobbleStop(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=100):
	"""/scrobble/stop with progress >= 80 auto-marks watched. Mirror of trakt.scrobbleStop.

	Note: we do NOT immediately refresh the watched-indicators cache after a
	successful stop. The reason: cachesyncMovies()/cachesyncTVShows() would
	full-fetch the user's entire library (potentially many items) on the
	player thread, blocking onPlayBackStopped. Instead, the activity timestamp
	on SIMKL's side will move, and the next service-sync tick (gated by
	/sync/activities) will pick up the change within the configured interval
	(default 15 min). Acceptable trade-off: indicator may lag by ~15 min,
	but no perf hit on the player thread.

	BUT: the SIMKL "siguiente episodio no visto" / "Mi Progreso" sections read
	from cheap, section-specific caches. When we mark something watched at
	>=80% we invalidate ONLY those (not the full library sync), so the next
	episode shows up immediately without the ~15 min lag. This is light: it
	just deletes two cache rows, no API call on the player thread.
	"""
	if not getSimklCredentialsInfo(): return False
	ok = _scrobble_call('stop', imdb, tmdb, tvdb, season, episode, watched_percent)
	if ok and float(watched_percent) >= 80:
		try: invalidateSectionCaches()
		except Exception: log_utils.error()
	return ok

def scrobbleCheckin(imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
	"""Fire-and-forget alternative to start/pause/stop. Opt-in via settings."""
	if not getSimklCredentialsInfo(): return False
	if getSetting('simkl.scrobble.checkin') != 'true': return False
	try:
		body = _build_scrobble_body(imdb, tmdb, tvdb, season, episode, 0)
		body.pop('progress', None)  # checkin doesn't need progress
		r = getSimkl('/scrobble/checkin', post=body, silent=True)
		return r is not None
	except Exception:
		log_utils.error()
		return False


# ---------------------------------------------------------------------------
# Playback (cross-device resume) — clears resume points on stop≥80
# ---------------------------------------------------------------------------
def fetchPlaybackSessions(media_type='movies'):
	"""GET /sync/playback/{movies|episodes} → list of saved paused playbacks.

	Used by sync_playbackProgress to repopulate the local bookmarks table.
	"""
	try:
		if media_type not in ('movies', 'episodes'): media_type = 'movies'
		r = getSimkl('/sync/playback/%s' % media_type, method='GET', silent=True)
		if r is None: return []
		try: return r.json() or []
		except Exception: return []
	except Exception:
		log_utils.error()
		return []

def deletePlaybackSession(session_id):
	try:
		r = getSimkl('/sync/playback/%s' % str(session_id), method='DELETE', silent=True)
		return r is not None
	except Exception:
		log_utils.error()
		return False


# ---------------------------------------------------------------------------
# Service sync loop — mirror of trakt_service_sync()
# ---------------------------------------------------------------------------
def _bust_section_caches_on_version_change():
	"""Si la versión del addon cambió desde el último arranque, invalida los
	caches de las secciones SIMKL una sola vez. Evita que un caché viejo (TTL
	hasta 12h, invalidación atada a getEpisodesWatchedActivity) siga tapando
	cambios de código tras una actualización. Idempotente: solo dispara cuando
	la versión guardada difiere de la instalada."""
	try:
		current = control.getluc_kodiVersion()
		stored = getSetting('simkl._cache_bust_version')
		if stored != current:
			invalidateSectionCaches()
			control.setSetting('simkl._cache_bust_version', current)
			log_utils.log('[luc_kodi-SIMKL] section caches busted for version %s' % current, __name__, log_utils.LOGDEBUG)
	except Exception:
		log_utils.error()


def simkl_service_sync():
	"""Background loop. Wakes every service_syncInterval minutes and runs
	activity-gated delta-syncs. Skips when offline or unauthenticated."""
	_bust_section_caches_on_version_change()
	while not control.monitor.abortRequested():
		control.sleep(5000)  # device wake guard
		if control.condVisibility('System.InternetState') and getSimklCredentialsInfo():
			try:
				activities = getSimklAsJson('/sync/activities', method='POST', silent=True)
				sync_watched(activities)
				sync_playbackProgress(activities)
				sync_watchlists(activities)
			except Exception:
				log_utils.error()
		if control.monitor.waitForAbort(60 * service_syncInterval): break


def force_simklSync(silent_confirm=False):
	"""User-triggered full resync. Wipes all sync tables and pulls fresh."""
	if not silent_confirm:
		if not control.yesnoDialog('Force full SIMKL sync now?', '', ''): return
	control.busy()
	try:
		simklsync.delete_tables({'bookmarks': True, 'watched_movies': True, 'watched_shows': True,
								 'movies_watchlist': True, 'shows_watchlist': True,
								 'anime_watchlist': True})
		sync_watched(forced=True)
		sync_playbackProgress(forced=True)
		sync_watchlists(forced=True)
	except Exception:
		log_utils.error()
	control.hide()
	if not silent_confirm:
		control.notification(title='SIMKL', message='Forced SIMKL Sync Complete')


def sync_watched(activities=None, forced=False):
	"""Refresh watched-indicator caches (movies + shows)."""
	try:
		if forced:
			cachesyncMovies()
			log_utils.log('Forced SIMKL Watched Movies Sync Complete', __name__, log_utils.LOGDEBUG)
			cachesyncTVShows()
			log_utils.log('Forced SIMKL Watched Shows Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			movies_activity = getMoviesWatchedActivity(activities)
			if movies_activity > timeoutsyncMovies():
				cachesyncMovies()
			shows_activity = getEpisodesWatchedActivity(activities)
			if shows_activity > timeoutsyncTVShows():
				cachesyncTVShows()
	except Exception:
		log_utils.error()


def sync_playbackProgress(activities=None, forced=False):
	"""Mirror of trakt.sync_playbackProgress. Refreshes the local bookmarks
	table from SIMKL's /sync/playback when the activity timestamp has moved."""
	try:
		if forced:
			items = (fetchPlaybackSessions('movies') or []) + (fetchPlaybackSessions('episodes') or [])
			if items: simklsync.insert_bookmarks(items)
			log_utils.log('Forced SIMKL Playback Progress Sync Complete', __name__, log_utils.LOGDEBUG)
		else:
			db_last_paused = simklsync.last_sync('last_paused_at')
			activity = getPausedActivity(activities)
			if activity - db_last_paused >= 120:
				items = (fetchPlaybackSessions('movies') or []) + (fetchPlaybackSessions('episodes') or [])
				if items: simklsync.insert_bookmarks(items)
	except Exception:
		log_utils.error()


def sync_watchlists(activities=None, forced=False):
	"""Pull the user's three watchlist buckets (movies/shows/anime, status=plantowatch)."""
	try:
		# SIMKL exposes /sync/all-items/{type}/{status}. Status `plantowatch` is
		# the canonical "watchlist" bucket equivalent to Trakt's watch_list.
		for media_type, table in (('movies', 'movies_watchlist'),
								  ('shows',  'shows_watchlist'),
								  ('anime',  'anime_watchlist')):
			data = getSimklAsJson('/sync/all-items/%s/plantowatch' % media_type, method='GET', silent=True)
			if data is None: continue
			items_key = media_type  # response shape: {"movies":[...]} / {"shows":[...]} / {"anime":[...]}
			items = data.get(items_key, []) if isinstance(data, dict) else []
			simklsync.insert_watchlist(items, table, new_sync=True, media_type=media_type)
	except Exception:
		log_utils.error()


# ---------------------------------------------------------------------------
# Public list helpers — feed movies.py / tvshows.py menus
# ---------------------------------------------------------------------------
def simkl_list(url):
	"""
	Fetch a SIMKL public list (trending today/week/month) and normalize it to
	the minimal shape the movies/tvshows worker pipeline expects:
	   [{'next': '', 'tmdb': '...', 'imdb': '', 'tvdb': '', 'title': '...',
	     'year': '...', 'metacache': False}, ...]

	SIMKL trending endpoints respond with `extended=tmdb` items that already
	carry `ids.tmdb`, `title`, and `year`, so we keep those upfront to reduce
	TMDb lookups in worker(). Items without a tmdb id are dropped — the
	pipeline can't resolve them otherwise.
	"""
	if not url: return []
	try:
		# getSimklAsJson auto-merges client_id / app-name / app-version into
		# the query string via _required_params(), so we just hand it the URL.
		items = getSimklAsJson(url, silent=True)
		if not items or not isinstance(items, list):
			return []
	except Exception:
		log_utils.error()
		return []

	out = []
	for item in items:
		try:
			ids = item.get('ids') or {}
			tmdb_id = ids.get('tmdb')
			if not tmdb_id:
				continue  # can't resolve metadata without a tmdb id
			values = {
				'next':       '',
				'tmdb':       str(tmdb_id),
				'imdb':       str(ids.get('imdb', '') or ''),
				'tvdb':       str(ids.get('tvdb', '') or ''),
				'title':      item.get('title', '') or '',
				'originaltitle': item.get('title', '') or '',
				'year':       str(item.get('year', '') or ''),
				'metacache':  False,
			}
			out.append(values)
		except Exception:
			log_utils.error()
	return out


# ---------------------------------------------------------------------------
# Playback progress lists — "Mi Progreso" sections (Movies + Episodes)
# ---------------------------------------------------------------------------
# SIMKL's /sync/playback/{movie|episode} returns temporary pause/resume
# sessions with `progress` as a percentage float 0..100. These power the two
# "Mi Progreso" menus. We only surface genuinely *in-progress* items: at least
# PROGRESS_MIN_PCT watched (so a single accidental tap doesn't clutter the
# list) and strictly below PROGRESS_MAX_PCT (>=85% is effectively "watched"
# and belongs in history, not in-progress).
# PROGRESS_MIN_PCT: 5.0 (antes 15.0). Un 15% ocultaba paradas tempranas
# legítimas: parar un episodio de 49 min al minuto 6 (~11%) es un caso real
# de "lo dejé a medias" y desaparecía de Mi Progreso sin explicación. El 5%
# sigue filtrando el tap accidental (unos segundos) sin comerse medias reales.
PROGRESS_MIN_PCT = 5.0
PROGRESS_MAX_PCT = 85.0


def _playback_in_range(progress):
	try:
		p = float(progress)
	except Exception:
		return False
	return PROGRESS_MIN_PCT <= p < PROGRESS_MAX_PCT


def _get_playback_sessions():
	"""GET /sync/playback → todas las sesiones pausadas (movie + episode).

	Pedimos SIN sufijo de tipo: la doc de SIMKL es inconsistente sobre si el
	filtro es /movie|/episode o /movies|/episodes, así que traemos todo y
	filtramos por el campo `type` de cada sesión en cliente. hide_watched=true
	(default) ya descarta lo que el usuario terminó después de pausar.
	"""
	try:
		if not getSimklCredentialsInfo():
			log_utils.log('SIMKL playback: sin credenciales — sección vacía.', __name__, log_utils.LOGWARNING)
			return []
		sessions = getSimklAsJson('/sync/playback', method='GET', silent=True)
		if sessions is None:
			# None = la petición FALLÓ (401/412/429/red) o el servidor devolvió
			# JSON null (= cero sesiones pausadas). Ver Playback Progress
			# Manager en simkl.com para confirmar el lado servidor.
			log_utils.log('SIMKL playback: respuesta None (fallo de peticion o cero sesiones en el servidor).',
							__name__, log_utils.LOGWARNING)
			return []
		if not isinstance(sessions, list):
			log_utils.log('SIMKL playback: respuesta con forma inesperada (%s) — se descarta.'
							% type(sessions).__name__, __name__, log_utils.LOGWARNING)
			return []
		in_range = len([s for s in sessions if _playback_in_range(s.get('progress'))])
		log_utils.log('SIMKL playback: %d sesiones recibidas, %d dentro del rango %d%%-%d%%.'
						% (len(sessions), in_range, int(PROGRESS_MIN_PCT), int(PROGRESS_MAX_PCT)),
						__name__, log_utils.LOGDEBUG)
		return sessions
	except Exception:
		log_utils.error()
		return []


def getMoviesProgress():
	"""Películas pausadas entre 15% y <85% (de /sync/playback, type=movie).

	Returns the minimal shape the movies worker pipeline expects, plus the
	`progress` / `paused_at` fields used for sorting and the progress badge.
	"""
	sessions = _get_playback_sessions()
	out = []
	for s in sessions:
		try:
			if (s.get('type') or '').lower() != 'movie': continue
			if not _playback_in_range(s.get('progress')): continue
			movie = s.get('movie') or {}
			ids = movie.get('ids') or {}
			tmdb_id = ids.get('tmdb')
			imdb_id = ids.get('imdb')
			if not tmdb_id and not imdb_id: continue
			out.append({
				'next':          '',
				'tmdb':          str(tmdb_id or ''),
				'imdb':          str(imdb_id or ''),
				'tvdb':          '',
				'title':         movie.get('title', '') or '',
				'originaltitle': movie.get('title', '') or '',
				'year':          str(movie.get('year', '') or ''),
				'progress':      float(s.get('progress') or 0),
				'paused_at':     s.get('paused_at', '') or '',
				'metacache':     False,
			})
		except Exception:
			log_utils.error()
	return out


def getEpisodesProgress():
	"""Episodios pausados entre 15% y <85% (de /sync/playback, type=episode).

	Returns per-episode dicts with snum/enum + show ids so the episodes worker
	can hydrate full metadata. progress/paused_at kept for sorting + badge.
	"""
	sessions = _get_playback_sessions()
	out = []
	for s in sessions:
		try:
			if (s.get('type') or '').lower() != 'episode': continue
			if not _playback_in_range(s.get('progress')): continue
			ep = s.get('episode') or {}
			show = s.get('show') or {}
			ids = show.get('ids') or {}
			# Prefer TVDB numbering when present (matches our TMDb-based meta),
			# else fall back to SIMKL's season/episode.
			# OJO: SIMKL es inconsistente y el número del episodio viene unas
			# veces como 'number' y otras como 'episode'. Aceptamos ambos, o
			# el item se descartaba (enum=None) y la lista salía vacía.
			snum = ep.get('tvdb_season')
			enum = ep.get('tvdb_number')
			if snum is None: snum = ep.get('season')
			if enum is None: enum = ep.get('number')
			if enum is None: enum = ep.get('episode')
			if snum is None or enum is None: continue
			tmdb_id = ids.get('tmdb')
			imdb_id = ids.get('imdb')
			tvdb_id = ids.get('tvdb')
			if not (tmdb_id or imdb_id or tvdb_id): continue
			title = show.get('title')
			if not title: continue
			out.append({
				'snum':          int(snum),
				'enum':          int(enum),
				'tvshowtitle':   title,
				'year':          show.get('year'),
				'tmdb':          str(tmdb_id or ''),
				'imdb':          str(imdb_id or ''),
				'tvdb':          str(tvdb_id or ''),
				'progress':      float(s.get('progress') or 0),
				'paused_at':     s.get('paused_at', '') or '',
			})
		except Exception:
			log_utils.error()
	return out


def getWatchingShows():
	"""GET /sync/all-items/shows/watching?extended=full → series que el usuario
	sigue, INCLUYENDO los episodios que ha visto EN SIMKL.

	Cada item devuelve `seasons[].episodes[].number` con los episodios vistos
	según el propio histórico de SIMKL (campo añadido por extended=full). Esto
	hace la sección 100% autónoma: no consulta Trakt ni ningún otro servicio.
	Si SIMKL no tiene episodios vistos de una serie, `watched` saldrá vacío y
	el llamador devolverá 1x01 (empezar desde el principio).
	"""
	try:
		if not getSimklCredentialsInfo(): return []
		# SIMKL separa los tipos: una petición a /shows/ NUNCA devuelve anime.
		# Muchas series (no solo japonesas de nicho) están clasificadas como
		# `anime` en SIMKL, así que hay que consultar AMBOS tipos o esas
		# series desaparecen de la sección de progreso.
		result = getSimklAsJson('/sync/all-items/shows/watching', params={'extended': 'full'}, method='GET', silent=True)
		# full_anime_seasons: igual que full pero cada episodio trae un bloque
		# tvdb:{season,episode} con la numeración TVDB/TMDb. Sin esto, SIMKL
		# numera el anime según AniDB (todo "temporada 1") y el cálculo del
		# siguiente episodio contra los metadatos de TMDb sale descuadrado.
		result_anime = getSimklAsJson('/sync/all-items/anime/watching', params={'extended': 'full_anime_seasons'}, method='GET', silent=True)
		# Diagnóstico: "Nothing found" en el menú debe dejar rastro en el log.
		# result=None => la petición falló (401/412/429/red); ver kodi.log y el
		# panel Debug/API Analytics en simkl.com/settings/developer.
		if result is None and result_anime is None:
			log_utils.log('SIMKL getWatchingShows: AMBAS peticiones (/shows y /anime) '
							'devolvieron None — fallo de red/auth/quota, no lista vacía. '
							'Revisa API Analytics en tu panel de developer de SIMKL.',
							__name__, log_utils.LOGWARNING)
			return []
		if not result and not result_anime: return []
	except Exception:
		log_utils.error()
		return []
	out = []
	result = result or {}
	result_anime = result_anime or {}
	shows = result.get('shows') or []
	anime = (result.get('anime') or []) + (result_anime.get('anime') or []) + (result_anime.get('shows') or [])
	for item in (shows + anime):
		try:
			show = item.get('show') or item.get('anime') or {}
			ids = show.get('ids') or {}
			title = show.get('title')
			if not title: continue
			# Episodios vistos según SIMKL: set de (season, episode).
			watched = set()
			for season in (item.get('seasons') or []):
				snum = season.get('number')
				if snum is None: continue
				for ep in (season.get('episodes') or []):
					# Anime (full_anime_seasons): preferir la numeración TVDB
					# del bloque tvdb:{season,episode} para casar con TMDb.
					tvdb_map = ep.get('tvdb') or {}
					e_snum = tvdb_map.get('season', snum)
					enum = tvdb_map.get('episode', ep.get('number'))
					if enum is None: continue
					try: watched.add((int(e_snum), int(enum)))
					except: pass
			out.append({
				'tvshowtitle': title,
				'year':        show.get('year'),
				'imdb':        str(ids.get('imdb') or ''),
				'tmdb':        str(ids.get('tmdb') or ''),
				'tvdb':        str(ids.get('tvdb') or ''),
				'lastplayed':  item.get('last_watched_at') or '',
				'added':       item.get('added_to_watchlist_at') or '',
				'simkl_watched': watched,  # histórico propio de SIMKL
			})
		except Exception:
			log_utils.error()
	log_utils.log('SIMKL getWatchingShows: %d shows(tv) + %d anime -> %d items, %d con historico de episodios'
					% (len(shows), len(anime), len(out), len([i for i in out if i.get('simkl_watched')])),
					__name__, log_utils.LOGDEBUG)
	return out
