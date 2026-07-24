# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — skip_intro.py

	Skip Intro / Recap / Preview usando TheIntroDB (https://theintrodb.org):
	timestamps aportados y verificados por la comunidad, consultados por
	IMDb/TMDb id + season/episode. TMDb/IMDb/TVDb NO publican timestamps de
	intros — aquí solo se usan sus ids para identificar el episodio exacto.

	Cliente HTTP adaptado del addon oficial de TheIntroDB para Kodi
	(https://github.com/TheIntroDB/kodi-addon, GPL-2.0-or-later), compatible
	con la licencia GPL-3.0-or-later de este addon.

	Flujo:
		player.keepAlive() → start(player) → hilo daemon _SkipMonitor:
			1. espera a que el reloj de reproducción avance
			2. fetch_segments() (caché manual en cache.db, TTL 24h/6h)
			3. por cada segmento (intro/recap/preview, orden cronológico):
			   - auto-skip (skipintro.auto) o botón SkipIntroXML
		El hilo muere solo si cambia el archivo en reproducción o se para.

	NOTA settings: los ids nuevos (skipintro.*, tidb.api.key) están declarados
	en settings.xml con default, así control.setting() los resuelve desde el
	caché de settings sin provocar lecturas de disco extra.
"""

import json
import threading
from ast import literal_eval
from time import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import xbmc
from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.database import cache

getSetting = control.setting
LOGINFO = log_utils.LOGINFO

API_BASE = 'https://api.theintrodb.org/v3'
USER_AGENT = 'plugin.video.luc_kodi (TheIntroDB client)'
REQUEST_TIMEOUT = 8

# TTL del caché (horas): resultados con datos vs negativos (404 / sin segmentos).
# Negativo también se cachea (lección aprendida con MDBList) para no martillear
# la API en cada episodio de una serie que no está en la base de datos.
_TTL_HIT_HOURS = 24
_TTL_MISS_HOURS = 6

# Tipos gestionados. 'credits' se excluye a propósito: chocaría con el flujo
# post-stop de siguiente episodio (playnext) que ya gestiona el final.
_SEG_INTRO = 'intro'
_SEG_OPTIONAL = ('recap', 'preview')

_BUTTON_LABELS = {
	'intro': 'Skip Intro',
	'recap': 'Skip Recap',
	'preview': 'Skip Preview',
}

# Guardia anti-duplicados: un solo monitor por archivo en reproducción.
_active_lock = threading.Lock()
_active_path = [None]

# Rate-limit compartido: si la API devuelve 429 no reintentamos hasta que expire.
_rate_limited_until = [0.0]


def enabled():
	return getSetting('skipintro.enabled') == 'true'


def start(player):
	"""Punto de entrada desde player.keepAlive(). No bloquea."""
	if not enabled(): return
	try:
		monitor = _SkipMonitor(player)
		monitor.daemon = True
		monitor.start()
	except:
		log_utils.error()


# ──────────────────────────────────────────────────────────────────────
# Cliente TheIntroDB
# ──────────────────────────────────────────────────────────────────────
def _build_url(imdb, tmdb, season, episode, is_movie, duration_ms=None):
	params = {}
	if tmdb:
		params['tmdb_id'] = str(tmdb)
	elif imdb and str(imdb).startswith('tt'):
		params['imdb_id'] = str(imdb)
	else:
		return None
	if not is_movie:
		try:
			params['season'] = int(season)
			params['episode'] = int(episode)
		except (TypeError, ValueError):
			return None
	if duration_ms:
		try: params['duration_ms'] = int(duration_ms)
		except (TypeError, ValueError): pass
	return '%s/media?%s' % (API_BASE, urlencode(params))


def _do_request(url):
	"""GET a TheIntroDB. Devuelve dict, {} en 404 (no está en la BD), o None
	en error de red/429 (para NO cachear el fallo como negativo)."""
	now = time()
	if now < _rate_limited_until[0]:
		control.log('[ luc_kodi ] skip_intro: rate-limited, skipping request', LOGINFO)
		return None
	req = Request(url)
	req.add_header('Accept', 'application/json')
	req.add_header('User-Agent', USER_AGENT)
	api_key = (getSetting('tidb.api.key') or '').strip()
	if api_key:
		req.add_header('Authorization', 'Bearer %s' % api_key)
	try:
		resp = urlopen(req, timeout=REQUEST_TIMEOUT)
		return json.loads(resp.read().decode('utf-8'))
	except HTTPError as e:
		if e.code == 404:
			return {}
		if e.code == 429:
			retry = 300
			for header in ('X-UsageLimit-Reset', 'X-RateLimit-Reset', 'Retry-After'):
				val = e.headers.get(header)
				if val:
					try: retry = int(val)
					except ValueError: pass
					break
			_rate_limited_until[0] = time() + retry
			control.log('[ luc_kodi ] skip_intro: TheIntroDB 429, backing off %ss' % retry, LOGINFO)
		else:
			control.log('[ luc_kodi ] skip_intro: TheIntroDB HTTP %s' % e.code, LOGINFO)
		return None
	except URLError as e:
		control.log('[ luc_kodi ] skip_intro: network error %s' % getattr(e, 'reason', e), LOGINFO)
		return None
	except Exception:
		log_utils.error()
		return None


def _pick_best(segments):
	"""De la lista de submissions de un tipo, elige la de mejor puntuación
	(confidence + nº de envíos). Devuelve (start_sec, end_sec) o None."""
	best, best_score = None, -1.0
	for seg in segments or []:
		if not isinstance(seg, dict): continue
		start = seg.get('start_ms')
		end = seg.get('end_ms')
		if start is None: start = 0
		if end is None or end <= start: continue
		conf = seg.get('confidence')
		if conf is None: conf = 0.5
		score = float(conf) + seg.get('submission_count', 1) * 0.001
		if score > best_score:
			best_score, best = score, (start / 1000.0, end / 1000.0)
	return best


def fetch_segments(imdb, tmdb, season, episode, is_movie, duration_ms=None):
	"""Devuelve {'intro': (start, end), 'recap': (...), 'preview': (...)}
	en segundos. Caché manual (cache_get/cache_insert con TTL propio) en vez
	de cache.get(): los bare-except de cache.get() ya nos tragaron errores
	con Gemini, aquí queremos control explícito y logging."""
	key = 'tidb_%s_%s_%s' % (tmdb or imdb, season or '0', episode or '0')
	try:
		cached = cache.cache_get(key)
		if cached:
			age_hours = (int(time()) - int(cached['date'])) / 3600.0
			try: value = literal_eval(cached['value'])
			except Exception: value = None
			if isinstance(value, dict):
				ttl = _TTL_HIT_HOURS if value else _TTL_MISS_HOURS
				if age_hours < ttl:
					return value
	except Exception:
		log_utils.error()

	url = _build_url(imdb, tmdb, season, episode, is_movie, duration_ms)
	if not url: return {}
	control.log('[ luc_kodi ] skip_intro: querying TheIntroDB: %s' % url, LOGINFO)
	data = _do_request(url)
	if data is None:
		return {}  # error de red/429: no cachear, reintentará en el próximo episodio

	result = {}
	for seg_type in (_SEG_INTRO,) + _SEG_OPTIONAL:
		best = _pick_best(data.get(seg_type))
		if best: result[seg_type] = best
	try:
		cache.cache_insert(key, repr(result))
	except Exception:
		log_utils.error()
	control.log('[ luc_kodi ] skip_intro: segments found: %s' % (list(result.keys()) or 'none'), LOGINFO)
	return result


# ──────────────────────────────────────────────────────────────────────
# Monitor de reproducción
# ──────────────────────────────────────────────────────────────────────
class _SkipMonitor(threading.Thread):
	def __init__(self, player):
		threading.Thread.__init__(self)
		self.player = player
		self.imdb = getattr(player, 'imdb', '') or ''
		self.tmdb = getattr(player, 'tmdb', '') or ''
		self.season = getattr(player, 'season', None)
		self.episode = getattr(player, 'episode', None)
		self.is_movie = getattr(player, 'media_type', None) == 'movie'
		self.running_path = ''

	def _playing_same_file(self):
		try:
			return (self.player.isPlayingVideo()
				and self.player.getPlayingFile() == self.running_path)
		except Exception:
			return False

	def _wait_for_clock(self):
		"""Espera a que el reloj avance de verdad (mismo problema de arranque
		en frío que el fast-path de gui_resolution en Android/Shield)."""
		previous = None
		deadline = time() + 60
		while not control.monitor.abortRequested() and time() < deadline:
			try:
				if self.player.isPlayingVideo():
					current = self.player.getTime()
					if previous is not None and current > previous + 0.1:
						self.running_path = self.player.getPlayingFile()
						return True
					previous = current
			except Exception:
				previous = None
			if control.monitor.waitForAbort(0.5): return False
		return False

	def run(self):
		try:
			with _active_lock:
				if not self._register(): return
			self._run_inner()
		except Exception:
			log_utils.error()
		finally:
			with _active_lock:
				if _active_path[0] == self.running_path:
					_active_path[0] = None

	def _register(self):
		# running_path aún no está — registro provisional para no lanzar dos
		# monitores desde reintentos rápidos de keepAlive.
		if _active_path[0] == '__starting__': return False
		_active_path[0] = '__starting__'
		return True

	def _run_inner(self):
		if not self._wait_for_clock():
			return
		with _active_lock:
			_active_path[0] = self.running_path

		duration_ms = 0
		try: duration_ms = int(self.player.getTotalTime() * 1000)
		except Exception: pass

		segments = fetch_segments(self.imdb, self.tmdb, self.season, self.episode,
								  self.is_movie, duration_ms or None)
		if not segments: return

		include_extra = getSetting('skipintro.recap') != 'false'
		auto_skip = getSetting('skipintro.auto') == 'true'
		try: offset = float(getSetting('skipintro.offset') or 0)
		except (TypeError, ValueError): offset = 0.0

		queue = []
		for seg_type, (start, end) in segments.items():
			if seg_type in _SEG_OPTIONAL and not include_extra: continue
			queue.append((start, end, seg_type))
		queue.sort()

		for start, end, seg_type in queue:
			if not self._handle_segment(start, end, seg_type, auto_skip, offset):
				return  # reproducción parada o cambio de archivo

	def _handle_segment(self, start, end, seg_type, auto_skip, offset):
		"""Espera a que el playhead entre en el segmento y actúa.
		Devuelve False si hay que abortar el monitor entero."""
		while not control.monitor.abortRequested():
			if not self._playing_same_file(): return False
			try: current = self.player.getTime()
			except Exception: return False
			if current >= end - 3:
				return True  # segmento ya pasado (resume) — al siguiente
			if current >= start:
				break
			# dormir hasta el inicio del segmento, con tope de 1s para
			# reaccionar a seeks del usuario
			if control.monitor.waitForAbort(min(max(start - current, 0.25), 1.0)):
				return False
		else:
			return False

		if auto_skip:
			return self._seek_past(end, offset, seg_type, notify=True)

		# Botón overlay — import perezoso para no cargar xbmcgui en vano
		try:
			from resources.lib.windows.skip_intro import SkipIntroXML
			window = SkipIntroXML('skip_intro.xml', control.addonPath(control.addonId()),
								  label=_BUTTON_LABELS.get(seg_type, 'Skip Intro'),
								  seg_end=end, running_path=self.running_path)
			pressed = window.run()
			del window
		except Exception:
			log_utils.error()
			return True
		if pressed:
			return self._seek_past(end, offset, seg_type, notify=False)
		return True

	def _seek_past(self, end, offset, seg_type, notify):
		if not self._playing_same_file(): return False
		try:
			target = end + offset
			total = self.player.getTotalTime()
			if total and target >= total - 10:
				target = max(total - 10, 0)
			control.log('[ luc_kodi ] skip_intro: skipping %s → %.1fs' % (seg_type, target), LOGINFO)
			self.player.seekTime(target)
			if notify:
				control.notification(message='Skipped %s' % seg_type)
		except Exception:
			log_utils.error()
		return True
