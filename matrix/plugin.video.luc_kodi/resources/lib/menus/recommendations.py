# -*- coding: utf-8 -*-
"""
luc_kodi - Recommendations menus
"""

from urllib.parse import quote_plus
from resources.lib.modules import control
from resources.lib.modules import trakt
from resources.lib.reco import engine

getLS = control.lang


class Recommendations:
	def __init__(self):
		self.highlight_color = control.getHighlightColor()

	# ── internal helpers ──────────────────────────────────────────────────────

	def _inject_feedback_meta(self, items, media_type):
		"""
		Attach feedback routing info to each item so movieDirectory /
		tvshowDirectory can build the 👍👎 context menu entries without
		knowing about the reco system.
		  _fb_tmdb       : tmdb_id string
		  _fb_media_type : 'movie' or 'tv'
		  _fb_genres     : comma-separated genre string
		"""
		# Lazily build a TMDb genre map only when needed (TMDb-source items)
		_genre_map_cache = {}

		def _resolve_genre_map():
			if _genre_map_cache:
				return _genre_map_cache
			try:
				from resources.lib.reco.engine import _tmdb_genre_map
				from resources.lib.indexers.tmdb import TMDb
				gm = _tmdb_genre_map(media_type, TMDb()) or {}
				_genre_map_cache.update(gm)
			except Exception:
				pass
			return _genre_map_cache

		for it in (items or []):
			tmdb = str(it.get('tmdb') or '')
			if not tmdb:
				continue

			# Priority 1: Trakt genres (already name strings)
			genres_raw = it.get('_trakt_genres') or []

			# Priority 2: TMDb genre IDs → resolve to names
			if not genres_raw:
				gids = it.get('_tmdb_genre_ids') or []
				if gids:
					gm = _resolve_genre_map()
					genres_raw = [str(gm.get(int(gid), '')) for gid in gids if gm.get(int(gid))]

			# Priority 3: generic 'genre' string field (post-worker)
			if not genres_raw:
				g_str = it.get('genre') or ''
				genres_raw = [g.strip() for g in g_str.split(',') if g.strip()]

			genres_str = ','.join(str(g).lower() for g in genres_raw if g)
			it['_fb_tmdb']       = tmdb
			it['_fb_media_type'] = media_type
			it['_fb_genres']     = genres_str

	def _inject_reason_into_plot(self, items):
		"""Prepend reco_reason + score to the plot field for skin display."""
		for it in (items or []):
			reason = it.get('reco_reason') or ''
			score  = it.get('reco_score')
			if reason:
				prefix = '[COLOR %s][B]%s[/B][/COLOR]' % (self.highlight_color, reason)
				if score is not None:
					prefix += '  [I]Score: %s[/I]' % score
				plot = it.get('plot') or ''
				it['plot'] = prefix + ('\n\n' + plot if plot else '')

	# ── public entry points ───────────────────────────────────────────────────

	def movies(self):
		if not trakt.getTraktCredentialsInfo():
			control.notification(title='luc_kodi', message='Trakt not authorized')
			from resources.lib.menus import navigator
			return navigator.Navigator().movies()

		from resources.lib.menus import movies as movies_menu
		items = engine.get_recommendations('movie', limit=50) or []
		m = movies_menu.Movies(notifications=False)
		m.list = items
		m.worker()
		self._inject_feedback_meta(m.list, 'movie')
		self._inject_reason_into_plot(m.list)
		m.movieDirectory(m.list or [], next=False)

	def tvshows(self):
		if not trakt.getTraktCredentialsInfo():
			control.notification(title='luc_kodi', message='Trakt not authorized')
			from resources.lib.menus import navigator
			return navigator.Navigator().tvshows()

		from resources.lib.menus import tvshows as tv_menu
		items = engine.get_recommendations('tv', limit=50) or []
		t = tv_menu.TVshows(notifications=False)
		try:
			t.list = items
			t.worker()
			self._inject_feedback_meta(t.list, 'tv')
			self._inject_reason_into_plot(t.list)
			t.tvshowDirectory(t.list or [], next=False)
		except Exception:
			control.notification(title='luc_kodi', message='Reco TV error')
