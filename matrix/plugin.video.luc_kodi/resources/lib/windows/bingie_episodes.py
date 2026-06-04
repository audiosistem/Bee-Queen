# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Bingie-style Seasons + Episodes window (modern ui).

	A single skin-independent window that mirrors the Bingie 525 view:
	  · left column  : show clearlogo + details + a vertical SEASONS list
	  · right column : the EPISODES of the focused season, as wide (16:9)
	                    landscape cards with SxE badge, title, plot, duration.

	Reuses Seasons.get()/Episodes.get() with create_directory=False to pull the
	exact same metadata the default directory would build, so no scraping logic
	is duplicated.  Selecting an episode plays it IN PLACE (RunPlugin) without
	closing the window — identical to the movie behaviour in bingie_grid — so
	scraping progress / notifications stay inside the section.

	Navigation:
	  · Left list  (5250) = seasons; moving up/down changes the season and
	    repopulates the right episode list.
	  · Right list (525)  = episodes; OK/tap plays in place.
	  · Back from episodes -> focus seasons; Back from seasons -> close.
"""

from urllib.parse import quote_plus
from json import dumps as jsdumps
from resources.lib.modules import control
from resources.lib.windows.base import BaseDialog


SEASON_ID = 5250
EPISODE_ID = 525
BACK_ACTIONS = [10, 92]   # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK


class BingieEpisodesXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.back_actions = BACK_ACTIONS
		self.tvshowtitle = kwargs.get('tvshowtitle') or ''
		self.year = kwargs.get('year') or ''
		self.imdb = kwargs.get('imdb') or ''
		self.tmdb = kwargs.get('tmdb') or ''
		self.tvdb = kwargs.get('tvdb') or ''
		self.art = kwargs.get('art') or ''       # json string of show art
		self.page_title = kwargs.get('page_title') or self.tvshowtitle or control.addonName()
		self.seasons = kwargs.get('seasons') or []   # list of season meta dicts
		self.episodes_fetch = kwargs.get('episodes_fetch')  # callable(season_meta)->[ep]
		self.start_season_index = kwargs.get('start_season_index') or 0

		self.prefer_tmdbArt = control.setting('prefer.tmdbArt') == 'true'
		self.settingFanart = control.setting('fanart') == 'true'
		self._addonPoster = control.addonPoster()
		self._addonFanart = control.addonFanart()

		self.season_index = 0
		self._cur_episodes = []      # meta dicts aligned 1:1 with episode cards
		self._ep_cache = {}          # season_index -> [episode meta]
		self._loading_eps = False
		self.selected_play = False

	# ───────────────────────── helpers ─────────────────────────
	def _fmt(self, val, pct=False):
		if val in (None, '', 0, '0', '0.0'): return ''
		try:
			f = float(val)
			if f <= 0: return ''
			return ('%d%%' % round(f)) if pct else ('%.1f' % f)
		except:
			return str(val)

	def _dur_mins(self, secs):
		try:
			m = int(int(secs) / 60)
			return '%dm' % m if m else ''
		except:
			return ''

	# ───────────────────────── season list ─────────────────────────
	def _make_season_li(self, s, idx):
		try:
			num = s.get('season')
			title = s.get('season_title') or ('Season %s' % num)
			li = control.item(label=title, offscreen=True)
			total = s.get('total_episodes') or ''
			li.setProperty('luc_season_index', str(idx))
			li.setProperty('luc_season_num', str(num))
			li.setProperty('luc_total_episodes', str(total))
			return li
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None

	# ───────────────────────── episode list ─────────────────────────
	def _ep_art(self, e):
		g = e.get
		thumb = g('thumb') or g('landscape') or g('fanart') or g('poster') or self._addonFanart
		fanart = g('fanart') or g('landscape') or self._addonFanart
		clearlogo = g('clearlogo', '')
		return thumb, fanart, clearlogo

	def _make_episode_li(self, e):
		try:
			season = e.get('season')
			episode = e.get('episode')
			ep_title = e.get('title') or e.get('label') or ''
			if not ep_title or ep_title == '0':
				ep_title = 'Episode %s' % episode
			li = control.item(label=ep_title, offscreen=True)

			thumb, fanart, clearlogo = self._ep_art(e)
			li.setArt({'thumb': thumb, 'poster': thumb, 'landscape': thumb,
						'fanart': fanart, 'clearlogo': clearlogo})

			try:
				control.infoTagger(li, {'plot': e.get('plot', ''), 'title': ep_title,
										'season': season, 'episode': episode,
										'premiered': e.get('premiered', ''),
										'duration': e.get('duration', ''),
										'mediatype': 'episode'})
			except Exception:
				pass

			# SxE badge text
			try: sxe = '%sx%02d' % (season, int(episode))
			except Exception: sxe = '%sx%s' % (season, episode)
			li.setProperty('luc_sxe', sxe)
			li.setProperty('luc_ep_title', ep_title)
			li.setProperty('luc_ep_plot', e.get('plot', '') or '')
			li.setProperty('luc_ep_premiered', e.get('premiered', '') or '')
			li.setProperty('luc_ep_duration', self._dur_mins(e.get('duration')))
			prog = e.get('progress') or e.get('percentplayed')
			if prog:
				try: li.setProperty('luc_progress', str(int(float(prog))))
				except: pass
			if str(e.get('playcount', '') or e.get('overlay', '')) in ('1', '5', 'True', 'true'):
				li.setProperty('luc_watched', '1')
			return li
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			try:
				li = control.item(label=(e.get('title') or ''), offscreen=True)
				li.setArt({'thumb': self._addonFanart})
				return li
			except Exception:
				return None

	# ───────────────────────── lifecycle ─────────────────────────
	def onInit(self):
		try:
			self._onInit()
		except Exception:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _onInit(self):
		self.setProperty('luc_kodi.page_title', self.page_title)
		# show-level clearlogo / fanart for the hero
		try:
			from json import loads as jsloads
			a = jsloads(self.art) if isinstance(self.art, str) and self.art else (self.art or {})
		except Exception:
			a = {}
		self.setProperty('luc_kodi.show_clearlogo', a.get('clearlogo', '') if isinstance(a, dict) else '')
		self.setProperty('luc_kodi.show_fanart', (a.get('fanart', '') if isinstance(a, dict) else '') or self._addonFanart)
		self.setProperty('luc_kodi.show_title', self.tvshowtitle)

		# build seasons list
		win = self.getControl(SEASON_ID)
		li = []
		for idx, s in enumerate(self.seasons):
			item = self._make_season_li(s, idx)
			if item is not None: li.append(item)
		win.reset(); win.addItems(li)

		# focus the requested season and populate episodes
		self.season_index = self.start_season_index if 0 <= self.start_season_index < len(self.seasons) else 0
		try: win.selectItem(self.season_index)
		except Exception: pass
		self._load_episodes(self.season_index)
		# start focus on episodes if available else seasons
		if self._cur_episodes:
			self.setFocusId(EPISODE_ID)
		else:
			self.setFocusId(SEASON_ID)

	def _season_meta_count(self):
		return len(self.seasons)

	def _load_episodes(self, sidx):
		if not (0 <= sidx < len(self.seasons)):
			return
		if getattr(self, '_loading_eps', False):
			return
		self._loading_eps = True
		self.setProperty('luc_kodi.loading', '1')
		try:
			eps = self._ep_cache.get(sidx)
			if eps is None:
				eps = self.episodes_fetch(self.seasons[sidx]) if self.episodes_fetch else []
				eps = eps or []
				self._ep_cache[sidx] = eps
			# build episode list items aligned to kept meta
			win = self.getControl(EPISODE_ID)
			listitems = []
			kept = []
			for e in eps:
				it = self._make_episode_li(e)
				if it is not None:
					listitems.append(it); kept.append(e)
			self._cur_episodes = kept
			win.reset(); win.addItems(listitems)
			self.setProperty('luc_kodi.season_label', self._season_label(sidx))
			self._refresh_ep_hero()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			self.clearProperty('luc_kodi.loading')
			self._loading_eps = False

	def _season_label(self, sidx):
		try:
			s = self.seasons[sidx]
			return s.get('season_title') or ('Season %s' % s.get('season'))
		except Exception:
			return ''

	def _refresh_ep_hero(self):
		try:
			pos = self.get_position(EPISODE_ID)
			if not (0 <= pos < len(self._cur_episodes)):
				return
			e = self._cur_episodes[pos]
			self.setProperty('luc_kodi.ep_title', e.get('title') or e.get('label') or '')
			self.setProperty('luc_kodi.ep_plot', e.get('plot', '') or '')
			self.setProperty('luc_kodi.ep_premiered', e.get('premiered', '') or '')
			self.setProperty('luc_kodi.ep_duration', self._dur_mins(e.get('duration')))
		except Exception:
			pass

	def run(self):
		self.doModal()
		self.clearProperties()
		return self.selected_play

	# ───────────────────────── input ─────────────────────────
	def onAction(self, action):
		try:
			action_id = action.getId()
			focus = self.getFocusId()

			# Context menu (long-press) on a focused episode.
			if action_id in self.context_actions and focus == EPISODE_ID:
				try:
					pos = self.get_position(EPISODE_ID)
					if 0 <= pos < len(self._cur_episodes):
						from resources.lib.modules import bingie_context
						bingie_context.show_for_episode(
							self._cur_episodes[pos],
							tvshowtitle=self.tvshowtitle, imdb=self.imdb,
							tmdb=self.tmdb, tvdb=self.tvdb, year=self.year)
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
				return

			if action_id in self.closing_actions:
				if action_id in self.back_actions:
					# Back from episodes -> jump to seasons; from seasons -> close
					if focus == EPISODE_ID and self._season_meta_count() > 1:
						self.setFocusId(SEASON_ID)
						return
				return self.close()

			# moving within seasons list -> repopulate episodes
			if focus == SEASON_ID:
				newidx = self.get_position(SEASON_ID)
				if newidx != self.season_index:
					self.season_index = newidx
					self._load_episodes(newidx)
				return
			# moving within episodes -> refresh hero details
			if focus == EPISODE_ID:
				self._refresh_ep_hero()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def onClick(self, controlId):
		if controlId == EPISODE_ID:
			self._play_selected_episode()
		elif controlId == SEASON_ID:
			# clicking a season just focuses its episodes
			self.season_index = self.get_position(SEASON_ID)
			self._load_episodes(self.season_index)
			if self._cur_episodes:
				self.setFocusId(EPISODE_ID)

	def _play_selected_episode(self):
		try:
			pos = self.get_position(EPISODE_ID)
			if not (0 <= pos < len(self._cur_episodes)):
				return
			e = self._cur_episodes[pos]
			self.selected_play = True
			systitle = quote_plus(e.get('title', '') or '')
			systvshowtitle = quote_plus(e.get('tvshowtitle') or self.tvshowtitle or '')
			year = e.get('year', '') or self.year
			imdb = e.get('imdb', '') or self.imdb
			tmdb = e.get('tmdb', '') or self.tmdb
			tvdb = e.get('tvdb', '') or self.tvdb
			season = e.get('season')
			episode = e.get('episode')
			premiered = quote_plus(str(e.get('premiered', '') or ''))
			meta = quote_plus(jsdumps(e))
			cmd = ('RunPlugin(plugin://plugin.video.luc_kodi/?action=play_Item'
					'&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s'
					'&tvshowtitle=%s&premiered=%s&meta=%s&bingie=1)'
					% (systitle, year, imdb, tmdb, tvdb, season, episode,
						systvshowtitle, premiered, meta))
			control.execute(cmd)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
