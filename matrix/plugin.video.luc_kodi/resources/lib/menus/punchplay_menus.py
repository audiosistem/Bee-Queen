# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	PunchPlay menus — Continue Watching, watchlist, user lists, history.

	Los dos ayudantes de mas peso (_seed_bookmarks, que siembra el punto de
	resume en traktsync.db y bookmarks.db, y _close_empty_directory, la red de
	seguridad de reuselanguageinvoker) se IMPORTAN de mdblist_menus en vez de
	copiarse. No son especificos de MDBList: trabajan sobre la forma de item
	comun del addon (progress/duration/imdb/tmdb/season/episode), que es la
	misma que produce punchplay.py. Duplicarlos significaria mantener dos
	copias del mismo SQL y arreglar cada fallo dos veces.

	REGLA que se respeta en TODAS las ramas de este fichero: nunca se sale de
	un constructor de directorio con un `return` sin haber cargado el
	directorio. Si se hace, con reuselanguageinvoker la CGUIMediaWindow se
	queda en "updating in progress" y Kodi se cierra en nativo al retroceder
	en Android. Costo una build entera descubrirlo en MDBList.
"""

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.database import cache
from resources.lib.menus.mdblist_menus import _seed_bookmarks, _close_empty_directory

getSetting = control.setting
getLS = control.lang


def _ensure_fresh():
	"""Invalida las cachés de PunchPlay si el addon ha cambiado de version.

	Va AQUI, en la capa de menus, y no dentro de las funciones de datos: esas
	viven por debajo de cache.get(), asi que en un acierto de cache no se
	ejecutan — que es precisamente cuando hace falta invalidar. Es el fallo del
	19-sep: con la 1.0.94 ya instalada, Community Lists seguia pintando la
	clasificacion de la 1.0.93 y en el log no habia ni una peticion."""
	try:
		from resources.lib.modules.punchplay import bust_caches_on_version_change
		bust_caches_on_version_change()
	except Exception:
		pass


def _build_list_directory(lists, action):
	"""Pinta un directorio de LISTAS (no de titulos)."""
	from sys import argv
	highlight_color = control.getHighlightColor()
	art_path = control.artPath()
	icon_path = control.joinPath(art_path, 'punchplay.png') if art_path else 'DefaultVideoPlaylists.png'
	for lst in (lists or []):
		try:
			list_id = lst.get('id', '')
			if list_id in (None, '', 0, '0'):
				continue
			label = lst.get('name', '?')
			if lst.get('dynamic'):
				label = '[I]%s[/I]' % label
			owner = lst.get('owner', '')
			if owner:
				label = '%s — [COLOR %s]%s[/COLOR]' % (label, highlight_color, owner)
			url = 'plugin://plugin.video.luc_kodi/?action=%s&list_id=%s' % (action, list_id)
			item = control.item(label=label, offscreen=True)
			item.setArt({'icon': icon_path, 'thumb': icon_path,
						 'poster': icon_path, 'fanart': control.addonFanart()})
			bits = ['%s items' % lst.get('items', 0)]
			if lst.get('dynamic'):
				bits.append('auto-updated')
			# externalSource no nulo = gestionada fuera y de solo lectura. Se
			# marca en el plot para que el usuario sepa por que el menu
			# contextual no le deja tocarla.
			if lst.get('external'):
				bits.append('read-only (%s)' % lst['external'])
			if lst.get('public'):
				bits.append('public')
			plot = '%s  •  %s' % (lst.get('name', ''), '  •  '.join(bits))
			try:
				item.getVideoInfoTag().setPlot(plot)
			except Exception:
				item.setInfo('video', {'plot': plot})
			control.addItem(handle=int(argv[1]), url=url, listitem=item, isFolder=True)
		except Exception:
			log_utils.error()
	control.content(int(argv[1]), '')
	control.directory(int(argv[1]), cacheToDisc=True)


def _enrich_episodes(ep, raw, tag):
	"""Enriquece episodios por el camino de Trakt con items ya cargados.

	Si el enriquecimiento devuelve vacio teniendo items de entrada, se AVISA.
	Antes se caia en los items crudos en silencio y el menu salia poblado pero
	sin caratulas ni datos — el sintoma de los "3x06 . Lioness" pelados del
	19-sep, que costo una build localizar precisamente porque no fallaba nada
	a la vista."""
	from resources.lib.modules.punchplay import _hard_log
	enriched = cache.get(
		ep.trakt_episodes_list, 0,
		ep.traktunfinished_link, ep.trakt_user, ep.lang, raw)
	if raw and not enriched:
		_hard_log('%s: %d episodios SIN enriquecer (se pintan pelados). '
				  'Revisar tipos de season/episode y los ids.' % (tag, len(raw)), 3)
	return enriched or raw


def _seed_resume_properties(items, episodes=False):
	"""Siembra el punto de resume en window properties, como hace MDBList, para
	que player.onAVStarted pueda buscar sin depender del dialogo de Bookmarks."""
	for item in (items or []):
		try:
			pct = float(item.get('progress', 0) or 0)
			dur = float(item.get('duration', 0) or 0)
			if pct <= 0 or dur <= 0:
				continue
			resume_sec = str((pct / 100) * dur)
			if episodes:
				key = 'punchplay.resume.%s.%s.%s' % (
					item.get('imdb') or item.get('tmdb') or '',
					item.get('season', '0') or '0',
					item.get('episode', '0') or '0')
			else:
				key = 'punchplay.resume.%s.0.0' % (item.get('imdb') or item.get('tmdb') or '')
			control.homeWindow.setProperty(key, resume_sec)
		except Exception:
			pass


def _open_list_by_url(media_type):
	"""Abre cualquier lista publica pegando su URL o su numero.

	La API publica solo expone las listas DESTACADAS del mes, asi que esta es
	la via para las otras noventa y tantas de punchplay.tv/discover/lists. El
	patron es el mismo que Import by URL de MDBList, y lo usa tambien Red Light
	por la misma razon: no hay busqueda de listas por nombre en esta API."""
	try:
		k = control.keyboard('https://punchplay.tv/lists/', getLS(46027))
		k.doModal()
		text = k.getText().strip() if k.isConfirmed() else ''
		if not text:
			return control.closeAll()
		from resources.lib.modules.punchplay import listIdFromUrl, getListItems
		list_id = listIdFromUrl(text)
		if not list_id:
			control.notification(title='PunchPlay', message=getLS(46028))
			return control.closeAll()
		items = getListItems(list_id, media_type)
		if media_type == 'show':
			from resources.lib.menus.tvshows import TVshows
			tv = TVshows()
			tv.list = items or []
			if tv.list:
				tv.worker()
			control.hide()
			tv.tvshowDirectory(tv.list)
		else:
			from resources.lib.menus.movies import Movies
			mv = Movies()
			mv.list = items or []
			if mv.list:
				mv.worker()
			control.hide()
			mv.movieDirectory(mv.list)
	except Exception:
		log_utils.error()
		_close_empty_directory()


# ============================================================
# CONTINUE WATCHING — MOVIES   (/playback/in-progress)
# ============================================================
class PunchPlayContinueMovies:
	def __init__(self):
		from resources.lib.menus.movies import Movies
		self._movies = Movies()

	def get(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getMoviesProgress
			raw = cache.get(getMoviesProgress, 1)
			if not raw:
				# Directorio vacio cargado igualmente. Sin notificar aqui:
				# movieDirectory ya lanza su propio aviso y saldrian dos
				# popups encadenados.
				control.hide()
				self._movies.movieDirectory([], unfinished=True, next=False)
				return
			self._movies.list = raw
			self._movies.worker()
			self._movies.list = sorted(
				self._movies.list, key=lambda k: k.get('paused_at', ''), reverse=True)
			_seed_resume_properties(self._movies.list)
			_seed_bookmarks(self._movies.list)
			self._movies.movieDirectory(self._movies.list, unfinished=True, next=False)
		except Exception:
			log_utils.error()
			_close_empty_directory()


# ============================================================
# CONTINUE WATCHING — EPISODES   (/playback/in-progress)
# ============================================================
class PunchPlayContinueEpisodes:
	def __init__(self):
		from resources.lib.menus.episodes import Episodes
		self._ep = Episodes()

	def get(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getEpisodesProgress
			raw = cache.get(getEpisodesProgress, 1)
			if not raw:
				control.hide()
				self._ep.episodeDirectory([], unfinished=True, next=False)
				return
			# Enriquecido por el MISMO camino que usan Trakt y MDBList para
			# sus episodios a medias: trakt_episodes_list con items ya
			# cargados, que se salta la llamada a la API de Trakt.
			self._ep.list = []
			self._ep.list = _enrich_episodes(self._ep, raw, 'continueEpisodes')
			self._ep.list = sorted(
				self._ep.list, key=lambda k: k.get('paused_at', ''), reverse=True)
			_seed_resume_properties(self._ep.list, episodes=True)
			_seed_bookmarks(self._ep.list)
			self._ep.episodeDirectory(self._ep.list, unfinished=True, next=False)
		except Exception:
			log_utils.error()
			_close_empty_directory()


# ============================================================
# NEXT EPISODE PER SHOW   (/me/continue-watching)
# ============================================================
class PunchPlayProgress:
	"""Distinto de Continue Watching: /me/continue-watching resume el estado
	por SERIE (siguiente episodio pendiente), no la posicion exacta dentro de
	un fichero. Es el equivalente al "Mi Progreso" de SIMKL."""

	def episodes(self):
		try:
			_ensure_fresh()
			from resources.lib.menus.episodes import Episodes
			from resources.lib.modules.punchplay import getWatchingShows
			ep = Episodes()
			raw = cache.get(getWatchingShows, 1)
			if not raw:
				control.hide()
				ep.episodeDirectory([], next=False)
				return
			ep.list = _enrich_episodes(ep, raw, 'nextEpisodes')
			ep.episodeDirectory(ep.list, next=False)
		except Exception:
			log_utils.error()
			_close_empty_directory()


class PunchPlayCalendar:
	"""Calendario personal: proximas emisiones de las series que sigue."""

	def episodes(self):
		try:
			_ensure_fresh()
			from resources.lib.menus.episodes import Episodes
			from resources.lib.modules.punchplay import getCalendarEpisodes
			ep = Episodes()
			raw = cache.get(getCalendarEpisodes, 6)
			if not raw:
				control.hide()
				ep.episodeDirectory([], next=False)
				return
			# Mismo camino de enriquecimiento que el calendario de MDBList:
			# trakt_episodes_list con los items ya cargados, que NO llama a la
			# API de Trakt. Episodes no tiene worker() propio.
			ep.list = _enrich_episodes(ep, raw, 'calendar')
			# Los hilos del enriquecimiento pierden el orden: reordenar por fecha.
			ep.list = sorted(ep.list, key=lambda k: k.get('premiered', ''))
			ep.episodeDirectory(ep.list, unfinished=False, next=False)
		except Exception:
			log_utils.error()
			_close_empty_directory()


# ============================================================
# WATCHLIST & LISTS — MOVIES
# ============================================================
class PunchPlayMovies:
	def __init__(self):
		from resources.lib.menus.movies import Movies
		self._movies = Movies()

	def _render(self, items):
		self._movies.list = items or []
		if self._movies.list:
			self._movies.worker()
		control.hide()
		self._movies.movieDirectory(self._movies.list)

	def watchlist(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getWatchlistId, getListItems
			list_id = cache.get(getWatchlistId, 12)
			if not list_id:
				# Sin watchlist identificable no se abandona sin cargar: se
				# pinta vacio y queda la traza del porque en kodi.log.
				from resources.lib.modules.punchplay import _hard_log
				_hard_log('watchlist: ninguna lista de /me/lists viene marcada como watchlist', 3)
				self._render([])
				return
			self._render(cache.get(getListItems, 1, list_id, 'movie'))
		except Exception:
			log_utils.error()
			_close_empty_directory()

	def userLists(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getUserListsFor
			_build_list_directory(cache.get(getUserListsFor, 6, 'movie') or [],
								  'punchplay_movieListItems')
		except Exception:
			log_utils.error()
			_close_empty_directory(notify=False)

	def listItems(self, list_id):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getListItems
			self._render(cache.get(getListItems, 6, list_id, 'movie'))
		except Exception:
			log_utils.error()
			_close_empty_directory()

	def communityLists(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getCommunityListsFor
			_build_list_directory(cache.get(getCommunityListsFor, 6, 'movie') or [],
								  'punchplay_movieListItems')
		except Exception:
			log_utils.error()
			_close_empty_directory(notify=False)

	def openByUrl(self):
		_open_list_by_url('movie')

	def _library(self, fn_name, ttl):
		"""v1.0.94 — Collection, Favourites y My Ratings (movie)."""
		try:
			_ensure_fresh()
			from resources.lib.modules import punchplay
			self._render(cache.get(getattr(punchplay, fn_name), ttl, 'movie'))
		except Exception:
			log_utils.error()
			_close_empty_directory()

	def collection(self):
		self._library('getCollectionFor', 6)

	def favourites(self):
		self._library('getFavouritesFor', 1)

	def ratings(self):
		self._library('getRatingsFor', 1)

	def history(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getHistory, _ids_of, _media_kind, _year_of, _first
			raw = cache.get(getHistory, 1)
			items = []
			for r in (raw or []):
				try:
					node = r.get('title') if isinstance(r.get('title'), dict) else r
					if _media_kind(node) == 'show':
						continue
					imdb, tmdb, tvdb = _ids_of(node)
					if not (tmdb or imdb):
						continue
					name = str(_first(node, 'title', 'name') or '')
					items.append({'next': '', 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb,
								  'title': name, 'originaltitle': name,
								  'year': _year_of(node), 'metacache': False})
				except Exception:
					pass
			self._render(items)
		except Exception:
			log_utils.error()
			_close_empty_directory()


# ============================================================
# WATCHLIST & LISTS — TV SHOWS
# ============================================================
class PunchPlayShows:
	def __init__(self):
		from resources.lib.menus.tvshows import TVshows
		self._tv = TVshows()

	def _render(self, items):
		self._tv.list = items or []
		if self._tv.list:
			self._tv.worker()
		control.hide()
		self._tv.tvshowDirectory(self._tv.list)

	def watchlist(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getWatchlistId, getListItems
			list_id = cache.get(getWatchlistId, 12)
			if not list_id:
				from resources.lib.modules.punchplay import _hard_log
				_hard_log('watchlist: ninguna lista de /me/lists viene marcada como watchlist', 3)
				self._render([])
				return
			self._render(cache.get(getListItems, 1, list_id, 'show'))
		except Exception:
			log_utils.error()
			_close_empty_directory()

	def userLists(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getUserListsFor
			_build_list_directory(cache.get(getUserListsFor, 6, 'show') or [],
								  'punchplay_showListItems')
		except Exception:
			log_utils.error()
			_close_empty_directory(notify=False)

	def listItems(self, list_id):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getListItems
			self._render(cache.get(getListItems, 6, list_id, 'show'))
		except Exception:
			log_utils.error()
			_close_empty_directory()

	def communityLists(self):
		try:
			_ensure_fresh()
			from resources.lib.modules.punchplay import getCommunityListsFor
			_build_list_directory(cache.get(getCommunityListsFor, 6, 'show') or [],
								  'punchplay_showListItems')
		except Exception:
			log_utils.error()
			_close_empty_directory(notify=False)

	def openByUrl(self):
		_open_list_by_url('show')

	def _library(self, fn_name, ttl):
		"""v1.0.94 — Collection, Favourites y My Ratings (show)."""
		try:
			_ensure_fresh()
			from resources.lib.modules import punchplay
			self._render(cache.get(getattr(punchplay, fn_name), ttl, 'show'))
		except Exception:
			log_utils.error()
			_close_empty_directory()

	def collection(self):
		self._library('getCollectionFor', 6)

	def favourites(self):
		self._library('getFavouritesFor', 1)

	def ratings(self):
		self._library('getRatingsFor', 1)
