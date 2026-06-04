# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Bingie-style SECTION HOME (default/fixed ui for Movies & TV).
	Hero on top; horizontal poster rows beneath (one per category "shortcut").
	OK plays the focused title directly (scrape -> index -> source select) via
	the addon's normal play_Item path (bingie=1, in place). Each row paginates
	in blocks of 20 with a trailing "Next page" sentinel. Skin-independent.
"""

from urllib.parse import quote_plus
from json import dumps as jsdumps
from resources.lib.modules import control
from resources.lib.windows.base import BaseDialog

ROW_BASE_ID = 6000
ROW_LABEL_BASE = 6500
MAX_ROWS = 12
ROW_PREVIEW = 20
BACK_ACTIONS = [10, 92]
UP_ACTIONS = [3, 104]
DOWN_ACTIONS = [4, 105]


def _next_url(items):
	try:
		for i in items:
			n = i.get('next')
			if n:
				return n
	except Exception:
		pass
	return None


class BingieSectionHomeXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.back_actions = BACK_ACTIONS
		# Use the base closing_actions (includes ACTION_STOP 13), same as the
		# official 1.0.21 grid. The launcher's reentrancy guard prevents the
		# parent directory from relaunching a fresh section window on stop.
		self.rows = kwargs.get('rows') or []
		self.section_title = kwargs.get('section_title') or control.addonName()
		self.media_type = kwargs.get('media_type') or 'movie'
		self.fetch_fn = kwargs.get('fetch_fn')
		self.selected = (None, None)
		self._paging = False
		self._abort = False
		self._active_row = 0
		self._inited = False
		self._row_rendered = [False for _ in self.rows]
		self._row_state = [{'items': [], 'next': None, 'card_pos': -1,
							'page': 0, 'history': []} for _ in self.rows]
		self._row_loaded = [False for _ in self.rows]
		self.prefer_tmdbArt = control.setting('prefer.tmdbArt') == 'true'
		self.settingFanart = control.setting('fanart') == 'true'
		self._addonPoster = control.addonPoster()
		self._addonFanart = control.addonFanart()
		# 'Next page' card icon: luc_kodi's own next.png (fallback to poster)
		try:
			import os
			self._nextIcon = os.path.join(control.addonPath(control.addonId()),
											'resources', 'media', 'luc_kodi', 'next.png')
			if not os.path.exists(self._nextIcon):
				self._nextIcon = self._addonPoster
		except Exception:
			self._nextIcon = self._addonPoster
		es = False
		try:
			import xbmc
			es = xbmc.getLanguage(xbmc.ENGLISH_NAME).split(' ')[0] == 'Spanish'
		except Exception:
			pass
		self._es = es
		self._lbl_next = 'P\u00e1gina siguiente' if es else 'Next page'

	def _pick_art(self, i):
		g = i.get
		if self.prefer_tmdbArt:
			poster = g('poster3') or g('poster') or g('poster2') or self._addonPoster
			clearlogo = g('tmdblogo') or g('clearlogo', '')
		else:
			poster = g('poster2') or g('poster3') or g('poster') or self._addonPoster
			clearlogo = g('clearlogo') or g('tmdblogo', '')
		if self.settingFanart:
			if self.prefer_tmdbArt: fanart = g('fanart3') or g('fanart') or g('fanart2') or self._addonFanart
			else: fanart = g('fanart2') or g('fanart3') or g('fanart') or self._addonFanart
		else:
			fanart = self._addonFanart
		return poster, fanart, clearlogo

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

	def _make_li(self, i):
		try:
			title = i.get('title') or i.get('tvshowtitle') or i.get('label') or ''
			year = i.get('year', '')
			label = '%s (%s)' % (title, year) if year else title
			li = control.item(label=label, offscreen=True)
			poster, fanart, clearlogo = self._pick_art(i)
			li.setArt({'poster': poster, 'thumb': poster, 'fanart': fanart, 'clearlogo': clearlogo})
			try:
				control.infoTagger(li, {'plot': i.get('plot', ''), 'title': title,
										'mediatype': 'movie' if self.media_type == 'movie' else 'tvshow'})
			except Exception:
				pass
			if str(i.get('playcount', '') or i.get('_watched', '')) in ('1', 'True', 'true') \
					or str(i.get('overlay', '')) == '5':
				li.setProperty('luc_watched', '1')
			prog = i.get('progress')
			if prog:
				try: li.setProperty('luc_progress', str(int(float(prog))))
				except: pass
			return li
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			try:
				li = control.item(label=(i.get('title') or i.get('label') or ''), offscreen=True)
				li.setArt({'poster': self._addonPoster, 'thumb': self._addonPoster})
				return li
			except Exception:
				return None

	def _make_next_card(self):
		try:
			li = control.item(label=self._lbl_next, offscreen=True)
			li.setArt({'poster': self._nextIcon, 'thumb': self._nextIcon})
			li.setProperty('luc_next_card', '1')
			return li
		except Exception:
			return None

	def onInit(self):
		if self._inited:
			# onInit fires again when the window regains focus after playback;
			# don't re-run the whole setup. Just restore focus where we were.
			try:
				self.setFocusId(ROW_BASE_ID + self._active_row)
			except Exception:
				pass
			return
		self._inited = True
		self.setProperty('luc_kodi.section_title', self.section_title)
		for idx, row in enumerate(self.rows):
			if idx >= MAX_ROWS: break
			try: self.setProperty('luc_kodi.row_label.%d' % idx, row.get('label', ''))
			except Exception: pass
			self.setProperty('luc_kodi.row_loading.%d' % idx, '1')
		# Load + render EVERY row synchronously. We're in a RunPlugin (script)
		# context, so a short load here is fine and — unlike a background thread
		# — does NOT make the modal close when playback starts. Synchronous,
		# fully-populated rows also let Kodi's own <onup>/<ondown> move focus
		# (empty containers can't receive focus, which broke lazy loading).
		for idx in range(min(len(self.rows), MAX_ROWS)):
			self._load_row(idx)
			self._render_row(idx)
			self._row_rendered[idx] = True
		if self.rows:
			# If we're coming back from playback (window was recreated), restore
			# the row/page/cursor we saved before launching the player. Otherwise
			# focus the first row as usual.
			if not self._restore_resume_position():
				try:
					if self._row_state and self._row_state[0]['items']:
						self.setFocusId(ROW_BASE_ID)
				except Exception:
					pass
			self._refresh_hero()

	def _restore_resume_position(self):
		"""Return True if a saved position for THIS section was restored."""
		try:
			from resources.lib.modules import control as _control
			hw = _control.homeWindow
			if hw.getProperty('luc_kodi.section_resume.media') != self.media_type:
				return False
			ar = int(hw.getProperty('luc_kodi.section_resume.row') or '0')
			page = int(hw.getProperty('luc_kodi.section_resume.page') or '0')
			pos = int(hw.getProperty('luc_kodi.section_resume.pos') or '0')
			# consume the saved position so it only applies to this reopen
			hw.clearProperty('luc_kodi.section_resume.media')
			hw.clearProperty('luc_kodi.section_resume.row')
			hw.clearProperty('luc_kodi.section_resume.page')
			hw.clearProperty('luc_kodi.section_resume.pos')
			if not (0 <= ar < len(self.rows)):
				return False
			# advance this row forward to the page we were on (pages aren't kept
			# across the window rebuild, so re-fetch them in order like 1.0.21)
			guard = 0
			while int(self._row_state[ar].get('page', 0)) < page and guard < 20:
				before = int(self._row_state[ar].get('page', 0))
				self._load_next_page(ar)
				if int(self._row_state[ar].get('page', 0)) == before:
					break
				guard += 1
			self._active_row = ar
			try:
				self.setFocusId(ROW_BASE_ID + ar)
			except Exception:
				pass
			# place the cursor on the same card
			try:
				st = self._row_state[ar]
				ctrl = self.getControl(ROW_BASE_ID + ar)
				if 0 <= pos < len(st['items']):
					ctrl.selectItem(pos)
			except Exception:
				pass
			return True
		except Exception:
			from resources.lib.modules import log_utils
			log_utils.error()
			return False

	def _ensure_row_rendered(self, idx):
		"""Load+render a row synchronously the first time it's reached (UI thread)."""
		if not (0 <= idx < len(self.rows)):
			return
		if self._row_rendered[idx]:
			return
		if not self._row_loaded[idx]:
			self._load_row(idx)          # synchronous fetch (no thread)
		self._render_row(idx)
		self._row_rendered[idx] = True

	def _load_row(self, idx):
		if idx >= len(self.rows) or self._row_loaded[idx]:
			return
		row = self.rows[idx]
		try:
			items = self.fetch_fn(row['url'], row.get('tmdb', False)) or []
		except Exception:
			from resources.lib.modules import log_utils
			log_utils.error()
			items = []
		st = self._row_state[idx]
		st['items'] = items[:ROW_PREVIEW]
		st['next'] = _next_url(items)
		self._row_loaded[idx] = True

	def _render_row(self, idx):
		try:
			if idx >= MAX_ROWS: return
			st = self._row_state[idx]
			listitems, kept = [], []
			for i in st['items']:
				li = self._make_li(i)
				if li is not None:
					listitems.append(li); kept.append(i)
			st['items'] = kept
			st['card_pos'] = -1
			if st.get('next'):
				card = self._make_next_card()
				if card is not None:
					st['card_pos'] = len(listitems)
					listitems.append(card)
			ctrl = self.getControl(ROW_BASE_ID + idx)
			ctrl.reset()
			if listitems:
				ctrl.addItems(listitems)
			self.clearProperty('luc_kodi.row_loading.%d' % idx)
		except Exception:
			self.clearProperty('luc_kodi.row_loading.%d' % idx)

	def run(self):
		self.doModal()
		self._abort = True
		self.clearProperties()
		return self.selected[0], self.selected[1]

	def _refresh_hero(self):
		try:
			row_idx = self._active_row
			ctrl_id = ROW_BASE_ID + row_idx
			pos = self.get_position(ctrl_id)
			st = self._row_state[row_idx] if row_idx < len(self._row_state) else None
			if not st: return
			if pos == st.get('card_pos'):
				self.setProperty('luc_kodi.meta_line', self._lbl_next)
				for k in ('rating_imdb', 'rating_rt', 'rating_tmdb', 'rating_trakt'):
					self.clearProperty('luc_kodi.%s' % k)
				return
			items = st['items']
			if not (0 <= pos < len(items)):
				return
			i = items[pos]
			self.setProperty('luc_kodi.meta_line', self._meta_line(i))
			rating_str = self._fmt(i.get('rating'))
			self.setProperty('luc_kodi.rating_imdb', rating_str if i.get('imdb') else '')
			self.setProperty('luc_kodi.rating_rt', self._fmt(i.get('rating_rt'), pct=True))
			self.setProperty('luc_kodi.rating_tmdb', rating_str if i.get('tmdb') else '')
			self.setProperty('luc_kodi.rating_trakt', self._fmt(i.get('rating_trakt')))
		except Exception:
			pass

	def onAction(self, action):
		try:
			action_id = action.getId()
			focus = self.getFocusId()
			row_idx = focus - ROW_BASE_ID
			on_row = 0 <= row_idx < len(self.rows)
			if action_id in self.context_actions and on_row:
				try:
					st = self._row_state[row_idx]
					pos = self.get_position(focus)
					if 0 <= pos < len(st['items']) and pos != st.get('card_pos'):
						from resources.lib.modules import bingie_context
						chosen = st['items'][pos]
						if self.media_type == 'movie': bingie_context.show_for_movie(chosen)
						else: bingie_context.show_for_tvshow(chosen)
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
				return
			if action_id in self.closing_actions:
				if action_id in self.back_actions:
					# Robust back via the tracked active row (getFocusId can be
					# transiently 0 right after a page re-render). On page 2+ step
					# back one page WITHIN the same category, like the 1.0.21 grid;
					# only on page 1 do we leave the section.
					ar = self._active_row if 0 <= self._active_row < len(self.rows) else (row_idx if on_row else -1)
					if 0 <= ar < len(self.rows):
						st = self._row_state[ar]
						if st.get('page', 0) > 0:
							if self._load_prev_page(ar):
								return
				self.selected = (None, None)
				return self.close()
			if on_row and action_id in (UP_ACTIONS + DOWN_ACTIONS):
				# XML <onup>/<ondown> moves focus between rows (all rows are
				# populated). We just track which row is active and update hero.
				if action_id in DOWN_ACTIONS and row_idx + 1 < len(self.rows):
					self._active_row = row_idx + 1
				elif action_id in UP_ACTIONS and row_idx > 0:
					self._active_row = row_idx - 1
				else:
					self._active_row = row_idx
				self._refresh_hero()
				return
			if on_row:
				self._active_row = row_idx
				self._refresh_hero()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def onClick(self, controlId):
		row_idx = controlId - ROW_BASE_ID
		if 0 <= row_idx < len(self.rows):
			self._select(row_idx)

	def _select(self, row_idx):
		try:
			if self._paging:
				return
			self._active_row = row_idx
			st = self._row_state[row_idx]
			ctrl_id = ROW_BASE_ID + row_idx
			pos = self.get_position(ctrl_id)
			if pos == st.get('card_pos'):
				self._paging = True
				try:
					self._load_next_page(row_idx)
				finally:
					import xbmc
					xbmc.sleep(150)
					self._paging = False
				return
			items = st['items']
			if not (0 <= pos < len(items)):
				return
			chosen = items[pos]
			if self.media_type == 'movie':
				self._play_movie_inplace(chosen)
			else:
				self._open_seasons_inplace(chosen)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _load_next_page(self, row_idx):
		try:
			st = self._row_state[row_idx]
			nxt = st.get('next')
			if not nxt:
				return
			row = self.rows[row_idx]
			self.setProperty('luc_kodi.row_loading.%d' % row_idx, '1')
			new_items = self.fetch_fn(nxt, row.get('tmdb', False)) or []
			if not new_items:
				st['next'] = None
				self.clearProperty('luc_kodi.row_loading.%d' % row_idx)
				return
			# remember the page we're leaving (items, next, and cursor pos) so
			# Back returns to it exactly where we were, like the 1.0.21 grid.
			try:
				leaving_pos = self.get_position(ROW_BASE_ID + row_idx)
			except Exception:
				leaving_pos = 0
			st['history'].append({'items': st['items'], 'next': st.get('next'), 'pos': leaving_pos})
			st['page'] = st.get('page', 0) + 1
			st['items'] = new_items[:ROW_PREVIEW]
			st['next'] = _next_url(new_items)
			self._render_row(row_idx)
			try:
				self.setFocusId(ROW_BASE_ID + row_idx)
			except Exception:
				pass
			self._active_row = row_idx
			self._refresh_hero()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			self.clearProperty('luc_kodi.row_loading.%d' % row_idx)

	def _load_prev_page(self, row_idx):
		"""Restore the previous page of this row from history. True if it did."""
		try:
			st = self._row_state[row_idx]
			if not st.get('history'):
				return False
			prev = st['history'].pop()
			st['page'] = max(0, st.get('page', 0) - 1)
			st['items'] = prev['items']
			st['next'] = prev.get('next')
			self._render_row(row_idx)
			# restore the cursor to where we were on that page
			try:
				want = int(prev.get('pos', 0))
				ctrl = self.getControl(ROW_BASE_ID + row_idx)
				if 0 <= want < len(st['items']):
					ctrl.selectItem(want)
			except Exception:
				pass
			try:
				self.setFocusId(ROW_BASE_ID + row_idx)
			except Exception:
				pass
			self._active_row = row_idx
			self._refresh_hero()
			return True
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return False

	def _save_resume_position(self):
		"""Persist active row + page + cursor pos to homeWindow properties so the
		section can return to the SAME place after the window is recreated. The
		window is torn down when the player goes full-screen and rebuilt from
		scratch when playback stops (Kodi re-runs the section script), so an
		instance attribute would be lost — homeWindow properties survive."""
		try:
			from resources.lib.modules import control as _control
			hw = _control.homeWindow
			ar = self._active_row if 0 <= self._active_row < len(self.rows) else 0
			try:
				pos = self.get_position(ROW_BASE_ID + ar)
			except Exception:
				pos = 0
			page = 0
			try:
				page = int(self._row_state[ar].get('page', 0))
			except Exception:
				page = 0
			hw.setProperty('luc_kodi.section_resume.media', self.media_type)
			hw.setProperty('luc_kodi.section_resume.row', str(ar))
			hw.setProperty('luc_kodi.section_resume.page', str(page))
			hw.setProperty('luc_kodi.section_resume.pos', str(pos))
		except Exception:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _play_movie_inplace(self, i):
		try:
			self._save_resume_position()
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

	def _open_seasons_inplace(self, i):
		try:
			self._save_resume_position()
			from resources.lib.modules import bingie_launcher
			bingie_launcher.open_seasons_window(i)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
