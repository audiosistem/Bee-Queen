# -*- coding: utf-8 -*-
"""
luc_kodi - Recommendations menus
"""

from resources.lib.modules import control
from resources.lib.modules import trakt
from resources.lib.reco import engine

getLS = control.lang


class Recommendations:
	def __init__(self):
		self.highlight_color = control.getHighlightColor()

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
		# inject reason + score into plot
		for it in (m.list or []):
			reason = it.get('reco_reason') or ''
			score = it.get('reco_score')
			if reason:
				prefix = f"[COLOR {self.highlight_color}][B]{reason}[/B][/COLOR]"
				if score is not None:
					prefix += f"  [I]Score: {score}[/I]"
				plot = it.get('plot') or ''
				it['plot'] = prefix + ("\n\n" + plot if plot else "")
		m.movieDirectory(m.list or [], next=False)

	def tvshows(self):
		if not trakt.getTraktCredentialsInfo():
			control.notification(title='luc_kodi', message='Trakt not authorized')
			from resources.lib.menus import navigator
			return navigator.Navigator().tvshows()

		from resources.lib.menus import tvshows as tv_menu
		items = engine.get_recommendations('tv', limit=50) or []
		t = tv_menu.TVshows(notifications=False) if hasattr(tv_menu, 'TVshows') else tv_menu.TVshows()
		# Some forks name class TVshows; keep safe
		try:
			t.list = items
			t.worker()
			for it in (t.list or []):
				reason = it.get('reco_reason') or ''
				score = it.get('reco_score')
				if reason:
					prefix = f"[COLOR {self.highlight_color}][B]{reason}[/B][/COLOR]"
					if score is not None:
						prefix += f"  [I]Score: {score}[/I]"
					plot = it.get('plot') or ''
					it['plot'] = prefix + ("\n\n" + plot if plot else "")
			t.tvshowDirectory(t.list or [], next=False)
		except Exception:
			# fallback: call tv_menu.TVshows()
			control.notification(title='luc_kodi', message='Reco TV error')
