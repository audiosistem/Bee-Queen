# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Bingie-style content grid (modern ui).

	Skin-independent browse window: poster grid on the right, spotlight hero
	(clearlogo + year/runtime/genres + plot + ratings) on the left.
	Selection is returned to the caller, which routes it into the normal
	play_Item / season flow, so no scraping/playback logic is duplicated here.

	Navigation model: PAGED, mirroring the DEFAULT skin's pagination.
	Instead of an ever-growing infinite-scroll list (useless on a D-pad
	remote) or focus-based page buttons (useless on a touchscreen), the
	"next page" is simply an extra CARD at the end of the grid — exactly
	like the default directory's "Next page" item.  Selecting it (tap, OK,
	or click) loads the next page and replaces the grid.  This works
	identically with touch and with a remote, because it is an ordinary
	item selection, not directional-focus navigation.

	Going back a page uses the remote/UI Back action (same as the default
	directory), so no "previous" card is needed.
"""

from urllib.parse import quote_plus
from json import dumps as jsdumps
from resources.lib.modules import control
from resources.lib.modules import poster_rotator
from resources.lib.windows.base import BaseDialog


GRID_ID = 5000
COLS = 5                 # columns in the poster grid (matches the XML layout)
BACK_ACTIONS = [10, 92]  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK


class BingieGridXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.back_actions = BACK_ACTIONS
		first_items = kwargs.get('items') or []         # list of meta dicts (first page)
		self.page_title = kwargs.get('page_title') or control.addonName()
		self.media_type = kwargs.get('media_type') or 'movie'
		self.fetch_page = kwargs.get('fetch_page')      # callable(next_url) -> [items]
		self.last_position = 0
		self.loading_more = False
		self._paging = False        # reentrancy guard: ignore selects during a page change
		self.selected = (None, None)
		self.prefer_tmdbArt = control.setting('prefer.tmdbArt') == 'true'
		self.settingFanart = control.setting('fanart') == 'true'
		self._addonPoster = control.addonPoster()
		self._addonFanart = control.addonFanart()
		try: self._nextIcon = control.addonNext()
		except Exception: self._nextIcon = ''

		# ── paged state ──
		# self.pages[i] = {'items': [...], 'next': str|None}
		# Already-fetched pages are kept in memory so going Back is instant.
		self.pages = [{'items': first_items, 'next': self._next_url(first_items)}]
		self.page_index = 0
		# per-page focus position so returning to a page restores where you were
		self._page_pos = {0: kwargs.get('start_position') or 0}
		# index of the "next page" sentinel card in the current render (-1 = none)
		self._next_card_pos = -1
		# meta dicts aligned 1:1 with the grid's poster cards (set in _render_page)
		self._view_items = []
		# resume directly on a given page if the session cached one
		resume_page = kwargs.get('start_page')
		self._resume_page = resume_page if isinstance(resume_page, int) and resume_page > 0 else 0

		# localized "next page" label (Spanish vs everything-else)
		es = False
		try:
			import xbmc
			es = xbmc.getLanguage(xbmc.ENGLISH_NAME).split(' ')[0] == 'Spanish'
		except Exception:
			pass
		self._es = es
		self._lbl_next = 'P\u00e1gina siguiente' if es else 'Next page'
		self._lbl_page = 'P\u00e1gina' if es else 'Page'

	# ───────────────────────── helpers ─────────────────────────
	@staticmethod
	def _next_url(items):
		try:
			for i in items:
				n = i.get('next')
				if n: return n
			return None
		except Exception:
			return None

	def _cur(self):
		return self.pages[self.page_index]

	def _cur_items(self):
		return self._cur()['items']

	def _has_next(self):
		return bool(self._cur().get('next')) or (self.page_index + 1 < len(self.pages))

	# ───────────────────────── art helpers ─────────────────────────
	def _pick_art(self, i):
		# Replica la lógica de movieDirectory/tvshowDirectory: respeta
		# prefer.tmdbArt y los fallbacks poster/poster2/poster3, etc.
		g = i.get
		if self.prefer_tmdbArt:
			poster = g('poster3') or g('poster') or g('poster2') or self._addonPoster
			clearlogo = g('tmdblogo') or g('clearlogo', '')
		else:
			poster = g('poster2') or g('poster3') or g('poster') or self._addonPoster
			clearlogo = g('clearlogo') or g('tmdblogo', '')
		poster = poster_rotator.rotate(i, poster) # rotación de pósters TMDb (si está activada)
		fanart = ''
		if self.settingFanart:
			if self.prefer_tmdbArt: fanart = g('fanart3') or g('fanart') or g('fanart2') or self._addonFanart
			else: fanart = g('fanart2') or g('fanart3') or g('fanart') or self._addonFanart
		else:
			fanart = self._addonFanart
		return poster, fanart, clearlogo

	# ───────────────────────── build ─────────────────────────
	def _make_li(self, i):
		try:
			title = i.get('title') or i.get('label') or ''
			year = i.get('year', '')
			label = '%s (%s)' % (title, year) if year else title
			li = control.item(label=label, offscreen=True)

			poster, fanart, clearlogo = self._pick_art(i)
			li.setArt({'poster': poster, 'thumb': poster,
						'fanart': fanart, 'clearlogo': clearlogo})

			# plot for the hero textbox (bound via ListItem.Plot).
			# Isolated: a bad meta dict must NOT drop the whole card, otherwise
			# the grid ends up with fewer cells than items and the "Next page"
			# sentinel lands in the wrong slot.
			try:
				control.infoTagger(li, {'plot': i.get('plot', ''), 'title': title,
										'mediatype': 'movie' if self.media_type == 'movie' else 'tvshow'})
			except Exception:
				pass

			# card badges (rating badge removed from poster — shown in hero instead)
			rating_str = self._fmt(i.get('rating'))
			if str(i.get('playcount', '') or i.get('_watched', '')) in ('1', 'True', 'true') \
					or str(i.get('overlay', '')) == '5':
				li.setProperty('luc_watched', '1')
			prog = i.get('progress')
			if prog:
				try: li.setProperty('luc_progress', str(int(float(prog))))
				except: pass

			# hero fields stashed per item; read on focus change
			li.setProperty('luc_meta_line', self._meta_line(i))
			li.setProperty('luc_r_imdb', rating_str if i.get('imdb') else '')
			li.setProperty('luc_r_tmdb', rating_str if i.get('tmdb') else '')
			li.setProperty('luc_r_rt', self._fmt(i.get('rating_rt'), pct=True))
			li.setProperty('luc_r_trakt', self._fmt(i.get('rating_trakt')))
			return li
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			# fall back to a minimal card so the item is NEVER silently dropped
			# (keeping grid index aligned with the metadata list)
			try:
				li = control.item(label=(i.get('title') or i.get('label') or ''), offscreen=True)
				li.setArt({'poster': self._addonPoster, 'thumb': self._addonPoster})
				return li
			except Exception:
				return None

	def _make_next_card(self):
		"""Sentinel 'Next page' card appended at the end of the grid (like default)."""
		try:
			li = control.item(label=self._lbl_next, offscreen=True)
			icon = self._nextIcon or self._addonPoster
			# only a poster/thumb; no fanart/clearlogo so the hero background and
			# logo don't get painted with the arrow when this card is focused.
			li.setArt({'poster': icon, 'thumb': icon, 'fanart': '', 'clearlogo': ''})
			li.setProperty('luc_next_card', '1')
			# hero panel hint when this card is focused
			nxt_no = self.page_index + 2  # the page it will load
			li.setProperty('luc_meta_line', '%s %s' % (self._lbl_page, nxt_no))
			li.setProperty('luc_r_imdb', ''); li.setProperty('luc_r_tmdb', '')
			li.setProperty('luc_r_rt', ''); li.setProperty('luc_r_trakt', '')
			return li
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None

	def _build_listitems(self, items):
		"""Return (listitems, kept_meta) where kept_meta[k] is the meta dict that
		produced listitems[k] — kept in lock-step so grid index == meta index,
		even when some items are skipped (e.g. _make_li returns None)."""
		out = []
		kept = []
		for i in items:
			li = self._make_li(i)
			if li is not None:
				out.append(li)
				kept.append(i)
		return out, kept

	def _fmt(self, val, pct=False):
		if val in (None, '', 0, '0', '0.0'): return ''
		try:
			f = float(val)
			if f <= 0: return ''
			return ('%d%%' % round(f)) if pct else ('%.1f' % f)
		except:
			return str(val)

	def _meta_line(self, i):
		parts = []
		if i.get('year'): parts.append(str(i['year']))
		dur = i.get('duration')
		if dur:
			try:
				m = int(int(dur) / 60)
				parts.append('%dh %02dm' % (m // 60, m % 60) if m >= 60 else '%dm' % m)
			except: pass
		genre = i.get('genre')
		if genre and str(genre) != 'NA':
			if isinstance(genre, (list, tuple)): genre = ' / '.join(genre)
			try:
				from resources.lib.modules import cleangenre
				genre = cleangenre.lang(genre, control.apiLanguage()['trakt'])
			except: pass
			parts.append(str(genre))
		mpaa = i.get('mpaa')
		if mpaa and str(mpaa) != 'NA': parts.append(str(mpaa))
		return '   \u2022   '.join(parts)

	# ───────────────────────── lifecycle ─────────────────────────
	def onInit(self):
		self.setProperty('luc_kodi.page_title', self.page_title)
		# if we have a cached resume page, jump straight to it (fetch as needed)
		if self._resume_page:
			while self.page_index < self._resume_page:
				if not self._fetch_next_into_cache(): break
				self.page_index += 1
		self._render_page(focus_pos=self._page_pos.get(self.page_index, 0))

	def _render_page(self, focus_pos=0):
		"""Replace the grid contents with the current page and refresh chrome."""
		items = self._cur_items()
		listitems, kept = self._build_listitems(items)
		# _view_items is the meta list aligned 1:1 with the grid's poster cards
		self._view_items = kept
		# append the 'Next page' card if there is a following page
		self._next_card_pos = -1
		if self._has_next():
			card = self._make_next_card()
			if card is not None:
				self._next_card_pos = len(listitems)
				listitems.append(card)
		win = self.getControl(GRID_ID)
		win.reset()
		win.addItems(listitems)
		self._update_count()
		self.setFocusId(GRID_ID)
		try:
			if 0 <= focus_pos < len(listitems): win.selectItem(focus_pos)
		except Exception:
			pass
		self._refresh_hero()

	def _update_count(self):
		page_no = self.page_index + 1
		n = len(self._cur_items())
		more = ' +' if self._cur().get('next') else ''
		self.setProperty('luc_kodi.total_items',
						'%s %s  \u00b7  %s items%s' % (self._lbl_page, page_no, n, more))

	def run(self):
		self.doModal()
		self.clearProperties()
		# return: (selected_pos, selected_meta, last_position, first_page_items, next_url, page_index)
		first_page = self.pages[0]['items'] if self.pages else []
		last_next = self.pages[-1].get('next') if self.pages else None
		return (self.selected[0], self.selected[1], self.last_position,
				first_page, last_next, self.page_index)

	def _refresh_hero(self):
		try:
			pos = self.get_position(GRID_ID)
			self.last_position = pos
			# is the focused item the 'next page' sentinel card?
			if pos == self._next_card_pos:
				nxt_no = self.page_index + 2
				self.setProperty('luc_kodi.meta_line', '%s %s' % (self._lbl_page, nxt_no))
				self.setProperty('luc_kodi.rating_imdb', '')
				self.setProperty('luc_kodi.rating_rt', '')
				self.setProperty('luc_kodi.rating_tmdb', '')
				self.setProperty('luc_kodi.rating_trakt', '')
				return
			items = self._view_items
			if not (0 <= pos < len(items)):
				return
			i = items[pos]
			self.setProperty('luc_kodi.meta_line', self._meta_line(i))
			rating_str = self._fmt(i.get('rating'))
			self.setProperty('luc_kodi.rating_imdb', rating_str if i.get('imdb') else '')
			self.setProperty('luc_kodi.rating_rt', self._fmt(i.get('rating_rt'), pct=True))
			self.setProperty('luc_kodi.rating_tmdb', rating_str if i.get('tmdb') else '')
			self.setProperty('luc_kodi.rating_trakt', self._fmt(i.get('rating_trakt')))
		except:
			pass

	# ───────────────────────── paging ─────────────────────────
	def _fetch_next_into_cache(self):
		"""Fetch the page following the last cached page. Returns True on success."""
		if self.loading_more or not self.fetch_page:
			return False
		last = self.pages[-1]
		nxt = last.get('next')
		if not nxt:
			return False
		self.loading_more = True
		try:
			self.setProperty('luc_kodi.loading', '1')
			new_items = self.fetch_page(nxt) or []
			if not new_items:
				last['next'] = None  # exhausted
				return False
			self.pages.append({'items': new_items, 'next': self._next_url(new_items)})
			return True
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return False
		finally:
			self.clearProperty('luc_kodi.loading')
			self.loading_more = False

	def _go_next(self):
		# remember where we were on this page
		try: self._page_pos[self.page_index] = self.get_position(GRID_ID)
		except Exception: pass
		# already cached?
		if self.page_index + 1 < len(self.pages):
			self.page_index += 1
			self._render_page(focus_pos=0)
			return
		# need to fetch
		if self._fetch_next_into_cache():
			self.page_index += 1
			self._page_pos[self.page_index] = 0
			self._render_page(focus_pos=0)

	def _go_prev(self):
		if self.page_index <= 0:
			return False
		self.page_index -= 1
		self._render_page(focus_pos=self._page_pos.get(self.page_index, 0))
		return True

	# ───────────────────────── input ─────────────────────────
	def onAction(self, action):
		try:
			action_id = action.getId()

			# Context menu (long-press / remote context key) — mirror the
			# default skin's per-item context menu inside the Bingie UI.
			if action_id in self.context_actions and self.getFocusId() == GRID_ID:
				try:
					pos = self.get_position(GRID_ID)
					items = self._view_items
					if 0 <= pos < len(items) and pos != self._next_card_pos:
						from resources.lib.modules import bingie_context
						chosen = items[pos]
						if self.media_type == 'movie':
							bingie_context.show_for_movie(chosen)
						else:
							bingie_context.show_for_tvshow(chosen)
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
				return

			if action_id in self.closing_actions:
				# Back: behaves like the default directory.
				#  1) if not on a previous page and not on the top row -> jump to top row
				#  2) if on a later page -> go back one page (like leaving a moviePage dir)
				#  3) otherwise -> close and return to the menu
				if action_id in self.back_actions and self.getFocusId() == GRID_ID:
					pos = self.get_position(GRID_ID)
					if pos >= COLS:
						target = pos % COLS   # misma columna, primera fila
						try: self.getControl(GRID_ID).selectItem(target)
						except: pass
						self._refresh_hero()
						return
					if self.page_index > 0:
						self._go_prev()
						return
				self.selected = (None, None)
				return self.close()

			# Selection (OK / tap) is handled exclusively in onClick(), which
			# Kodi fires for both remote-OK and touch on a panel. Handling it
			# here too caused a double-fire: _select() paginated, then the
			# trailing onClick() re-ran _select() on the NEW page and launched
			# whatever item now sat under the cursor (hence the stray "play
			# movie" + Debrid notification right after paging).

			# any movement while on the grid -> update hero panel
			if self.getFocusId() == GRID_ID:
				self._refresh_hero()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def onClick(self, controlId):
		if controlId == GRID_ID:
			self._select()

	def _select(self):
		try:
			# ignore any selection that arrives while a page change is in flight
			if self._paging:
				return
			pos = self.get_position(GRID_ID)
			# tapped / clicked the 'Next page' sentinel card?
			if pos == self._next_card_pos:
				self._paging = True
				try:
					self._go_next()
				finally:
					# release on the next render's idle; a short sleep swallows
					# any trailing duplicate select event from the same tap/press
					import xbmc
					xbmc.sleep(150)
					self._paging = False
				return
			items = self._view_items
			if 0 <= pos < len(items):
				chosen = items[pos]
				if self.media_type == 'movie':
					# Play in place: fire the playback plugin call but KEEP the
					# grid open, so scraping progress / "no Debrid" notifications
					# happen inside this section instead of dumping the user back
					# to the parent menu.
					self._play_movie_inplace(chosen)
					return
				# TV shows: open the Bingie Seasons+Episodes window NESTED on top
				# of this grid. Back from there returns to this grid, keeping the
				# whole browse experience inside the Bingie UI.
				self._open_seasons_inplace(chosen)
				return
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _open_seasons_inplace(self, i):
		"""Open the Bingie seasons/episodes window without closing this grid."""
		try:
			from resources.lib.modules import bingie_launcher
			bingie_launcher.open_seasons_window(i)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _play_movie_inplace(self, i):
		"""RunPlugin(play_Item) without closing the window (async playback)."""
		try:
			systitle = quote_plus(i.get('title', ''))
			year = i.get('year', '')
			imdb = i.get('imdb', '')
			tmdb = i.get('tmdb', '')
			meta = quote_plus(jsdumps(i))
			cmd = ('RunPlugin(plugin://plugin.video.luc_kodi/?action=play_Item'
					'&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&bingie=1)'
					% (systitle, year, imdb, tmdb, meta))
			control.execute(cmd)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
