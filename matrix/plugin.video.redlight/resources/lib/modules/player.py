# -*- coding: utf-8 -*-
import os
import xbmc
import json
from threading import Thread
from apis.trakt_api import make_trakt_slug
from caches.settings_cache import get_setting
from modules import kodi_utils as ku, settings as st, watched_status as ws
# logger = ku.logger

PROP_RESOLVE_CANCEL = 'redlight.resolve_cancelled'
PROP_PLAY_OPENING = 'redlight.play_opening'
PROP_NEXTEP_PENDING = 'redlight.nextep_pending'

class RedLightPlayer(xbmc.Player):
	def __init__ (self):
		xbmc.Player.__init__(self)

	def _resolve_cancelled(self):
		if not self.is_generic and (self.sources_object._resolve_user_cancelled or self.sources_object.cancel_all_playback):
			return True
		return ku.get_property(PROP_RESOLVE_CANCEL) == 'true'

	def run(self, url=None, obj=None):
		ku.hide_busy_dialog()
		self.clear_playback_properties(clear_navigation=False)
		if not url:
			self.is_generic = obj == 'video'
			return self.run_error('No playable link was returned.')
		try: return self.play_video(url, obj)
		except:
			self.is_generic = obj == 'video'
			return self.run_error()

	def play_video(self, url, obj):
		self.set_constants(url, obj)
		if self.is_generic:
			ku.clear_video_playlist()
		if not self.is_generic and self._resolve_cancelled():
			self.playback_successful = False
			self.cancel_all_playback = True
			self.sources_object.cancel_all_playback = True
			self.sources_object._resolve_user_cancelled = True
			return
		ku.volume_checker()
		ku.set_property(PROP_PLAY_OPENING, 'true')
		self.play(self.url, self.make_listing())
		if self.is_generic:
			self.check_playback_start_generic()
			if self.playback_successful:
				ku.clear_property(PROP_PLAY_OPENING)
			else:
				self.safe_stop()
				return self.run_error()
		else:
			self.check_playback_start()
			if self.playback_successful:
				ku.clear_property(PROP_PLAY_OPENING)
				try:
					if self.sources_object:
						self.sources_object._release_resolve_busy()
				except:
					pass
				self.monitor()
			else:
				self.sources_object.playback_successful = self.playback_successful
				cancelled = self.cancel_all_playback or self.sources_object._resolve_user_cancelled
				if cancelled:
					self.sources_object.cancel_all_playback = True
					self.sources_object._resolve_user_cancelled = True
				else:
					self.sources_object.cancel_all_playback = self.cancel_all_playback
				if cancelled:
					if not self.sources_object._resolve_user_cancelled:
						self.kill_dialog()
				else:
					# Keep the resolver progress UI so play_file can try the next queued source.
					self.run_error()
				self.safe_stop()
		try: del self.kodi_monitor
		except: pass

	def check_playback_start_generic(self):
		resolve_percent = 0
		while self.playback_successful is None:
			ku.hide_busy_dialog()
			if self.kodi_monitor.abortRequested():
				self.playback_successful = False
				break
			elif resolve_percent >= 100:
				self.playback_successful = False
				break
			elif ku.get_visibility('Window.IsTopMost(okdialog)'):
				ku.execute_builtin('SendClick(okdialog, 11)')
				self.playback_successful = False
			elif self.isPlayingVideo():
				try:
					if ku.get_property('redlight.browse_playback') == 'true':
						browse_window = getattr(self, '_browse_results_window', None)
						if browse_window:
							try:
								browse_window.selected = (None, '')
								browse_window.close()
								self._browse_results_window = None
							except:
								pass
					if not ku.get_visibility('Window.IsActive(fullscreenvideo)'):
						ku.execute_builtin('ActivateWindow(fullscreenvideo)', block=False)
					if self.getTotalTime() not in ('0.0', '', 0.0, None):
						self.playback_successful = True
				except:
					pass
			resolve_percent = round(resolve_percent + 0.26, 1)
			ku.sleep(50)

	def check_playback_start(self):
		resolve_percent = 0
		while self.playback_successful is None:
			ku.hide_busy_dialog()
			if self._resolve_cancelled():
				self.sources_object.cancel_all_playback = True
				self.sources_object._resolve_user_cancelled = True
				self.playback_successful = False
				self.safe_stop()
				break
			elif not self.sources_object.progress_dialog:
				if self._resolve_cancelled():
					self.sources_object.cancel_all_playback = True
					self.sources_object._resolve_user_cancelled = True
					self.playback_successful = False
					self.safe_stop()
					break
				elif self.isPlayingVideo():
					try:
						if self.getTotalTime() not in ('0.0', '', 0.0, None) and ku.get_visibility('Window.IsActive(fullscreenvideo)'):
							self.playback_successful = True
					except: pass
			elif self.sources_object.progress_dialog.skip_resolved(): self.playback_successful = False
			elif self.sources_object.progress_dialog.iscanceled() or self.kodi_monitor.abortRequested():
				self.sources_object.cancel_all_playback = True
				self.sources_object._resolve_user_cancelled = True
				self.playback_successful = False
				self.safe_stop()
				break
			elif resolve_percent >= 100:
				self.playback_successful = False
				break
			elif ku.get_visibility('Window.IsTopMost(okdialog)'):
				ku.execute_builtin('SendClick(okdialog, 11)')
				self.playback_successful = False
			elif self.isPlayingVideo():
				if self._resolve_cancelled():
					self.sources_object.cancel_all_playback = True
					self.sources_object._resolve_user_cancelled = True
					self.playback_successful = False
					self.safe_stop()
					break
				try:
					if self.getTotalTime() not in ('0.0', '', 0.0, None) and ku.get_visibility('Window.IsActive(fullscreenvideo)'): self.playback_successful = True
				except: pass
			resolve_percent = round(resolve_percent + 0.26, 1)
			try:
				if self.sources_object.progress_dialog:
					self.sources_object.progress_dialog.update_resolver(percent=resolve_percent)
			except: pass
			ku.sleep(50)

	def playback_close_dialogs(self):
		self.sources_object.playback_successful = True
		self.kill_dialog()
		ku.sleep(200)
		ku.close_all_dialog()

	def monitor(self):
		try:
			ensure_dialog_dead, total_check_time = False, 0
			if self.media_type == 'episode':
				play_random_continual = self.sources_object.random_continual
				play_random = self.sources_object.random
				disable_autoplay_next_episode = self.sources_object.disable_autoplay_next_episode
				if disable_autoplay_next_episode: ku.notification('Scrape with Custom Values - Autoplay Next Episode Cancelled', 4500)
				if any((play_random_continual, play_random, disable_autoplay_next_episode)): self.autoplay_nextep, self.autoscrape_nextep = False, False
				else: self.autoplay_nextep, self.autoscrape_nextep = self.sources_object.autoplay_nextep, self.sources_object.autoscrape_nextep
			else:
				show_stinger, stinger_use_chapters, stingers_percentage_fallback = st.stingers_show(), st.stingers_use_chapters(), st.stingers_percentage()
				play_random_continual, self.autoplay_nextep, self.autoscrape_nextep = False, False, False
			while total_check_time <= 30 and not ku.get_visibility('Window.IsActive(fullscreenvideo)'):
				ku.sleep(100)
				total_check_time += 0.10
			ku.hide_busy_dialog()
			ku.sleep(1000)
			self._simkl_scrobble_start()
			if st.auto_enable_subs() and not st.submaker_enabled(): self.showSubtitles(True)
			while self.isPlayingVideo():
				try:
					if not ensure_dialog_dead:
						ensure_dialog_dead = True
						self.playback_close_dialogs()
					ku.sleep(1000)
					try: self.total_time, self.curr_time = self.getTotalTime(), self.getTime()
					except: ku.sleep(250); continue
					if not self._valid_playback_duration(self.total_time, self.curr_time):
						ku.sleep(250)
						continue
					self.current_point = round(float(self.curr_time/self.total_time * 100), 1)
					if self.current_point >= 90:
						if play_random_continual: self.run_random_continual(); break
						if not self.media_marked: self.media_watched_marker()
					if self.media_type == 'episode':
						if self.autoplay_nextep or self.autoscrape_nextep:
							if not self.nextep_info_gathered: self.info_next_ep()
							if self._should_prep_next_ep(): self._schedule_next_ep(); break
					elif show_stinger and not self.movie_stingers_run: 
						final_chapter = (self.final_chapter(75) or stingers_percentage_fallback) if stinger_use_chapters else stingers_percentage_fallback
						if self.current_point >= final_chapter: self.run_movie_stingers()
				except: pass
				if not self.subs_searched: self.run_subtitles()
			ku.hide_busy_dialog()
			if not self.media_marked: self.media_watched_marker()
			self.clear_playback_properties(clear_navigation=False)
		except:
			ku.hide_busy_dialog()
			self.sources_object.playback_successful = False
			self.sources_object.cancel_all_playback = True
			return self.kill_dialog()

	def make_listing(self):
		listitem = ku.make_listitem()
		listitem.setPath(self.url)
		listitem.setContentLookup(False)
		if self.is_generic:
			info_tag = listitem.getVideoInfoTag(True)
			info_tag.setMediaType('video')
			play_name = ku.get_property('redlight.tb.play_filename') or self.url
			info_tag.setFilenameAndPath(play_name)
			info_tag.setTitle(os.path.basename(play_name) if play_name else '')
			mime = ku.get_property('redlight.tb.play_mime')
			if not mime:
				path_lower = (play_name or self.url or '').lower().split('|')[0].split('?')[0]
				for ext, mt in (
					('.m2ts', 'video/mp2t'), ('.mts', 'video/mp2t'), ('.ts', 'video/mp2t'),
					('.mkv', 'video/x-matroska'), ('.mp4', 'video/mp4'), ('.avi', 'video/x-msvideo'),
					('.mov', 'video/quicktime'), ('.webm', 'video/webm'),
				):
					if path_lower.endswith(ext):
						mime = mt
						break
			if mime:
				try:
					listitem.setMimeType(mime)
				except Exception:
					pass
			self._disable_kodi_url_resume(listitem)
		else:
			self.tmdb_id, self.imdb_id, self.tvdb_id = self.meta_get('tmdb_id', ''), self.meta_get('imdb_id', ''), self.meta_get('tvdb_id', '')
			self.media_type, self.title, self.year = self.meta_get('media_type'), self.meta_get('title'), self.meta_get('year')
			self.season, self.episode = self.meta_get('season', ''), self.meta_get('episode', '')
			poster = self.meta_get('poster') or ku.get_icon('box_office')
			fanart = self.meta_get('fanart') or ku.get_addon_fanart()
			clearlogo = self.meta_get('clearlogo') or ''
			duration, genre, trailer, mpaa = self.meta_get('duration'), self.meta_get('genre', ''), self.meta_get('trailer'), self.meta_get('mpaa')
			rating, votes = self.meta_get('rating'), self.meta_get('votes')
			premiered, studio, tagline = self.meta_get('premiered'), self.meta_get('studio', ''), self.meta_get('tagline')
			director, writer, country = self.meta_get('director', ''), self.meta_get('writer', ''), self.meta_get('country', '')
			cast = self.meta_get('short_cast', []) or self.meta_get('cast', []) or []
			listitem.setLabel(self.title)
			if self.media_type == 'movie':
				plot = self.meta_get('plot')
				listitem.setArt({'poster': poster, 'fanart': fanart, 'icon': poster, 'clearlogo': clearlogo})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setMediaType('movie'), info_tag.setTitle(self.title), info_tag.setOriginalTitle(self.meta_get('original_title')), info_tag.setPlot(plot)
				info_tag.setYear(int(self.year)), info_tag.setRating(rating), info_tag.setVotes(votes), info_tag.setMpaa(mpaa)
				info_tag.setDuration(duration), info_tag.setCountries(country), info_tag.setTrailer(trailer), info_tag.setPremiered(premiered)
				info_tag.setTagLine(tagline), info_tag.setStudios(studio), info_tag.setIMDBNumber(self.imdb_id), info_tag.setGenres(genre)
				info_tag.setWriters(writer), info_tag.setDirectors(director), info_tag.setUniqueIDs({'imdb': self.imdb_id, 'tmdb': str(self.tmdb_id)})
				info_tag.setCast([ku.kodi_actor()(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in cast])
			else:
				if st.avoid_episode_spoilers() and int(self.meta_get('playcount', '0')) == 0: plot = self.meta_get('tvshow_plot') or '* Hidden to Prevent Spoilers *'
				else: plot = self.meta_get('plot') or self.meta_get('tvshow_plot')
				listitem.setArt({'poster': poster, 'fanart': fanart, 'icon': poster, 'clearlogo': clearlogo, 'tvshow.poster': poster, 'tvshow.clearlogo': clearlogo})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setMediaType('episode'), info_tag.setTitle(self.meta_get('ep_name')), info_tag.setOriginalTitle(self.meta_get('original_title'))
				info_tag.setTvShowTitle(self.title), info_tag.setTvShowStatus(self.meta_get('status')), info_tag.setSeason(self.season), info_tag.setEpisode(self.episode)
				info_tag.setPlot(plot), info_tag.setYear(int(self.year)), info_tag.setRating(rating), info_tag.setVotes(votes)
				info_tag.setMpaa(mpaa), info_tag.setDuration(duration), info_tag.setTrailer(trailer), info_tag.setFirstAired(premiered)
				info_tag.setStudios(studio), info_tag.setIMDBNumber(self.imdb_id), info_tag.setGenres(genre), info_tag.setWriters(writer)
				info_tag.setDirectors(director), info_tag.setUniqueIDs({'imdb': self.imdb_id, 'tmdb': str(self.tmdb_id), 'tvdb': str(self.tvdb_id)})
				info_tag.setCast([ku.kodi_actor()(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in cast])
				info_tag.setFilenameAndPath(self.url)
			self.set_resume_point(listitem)
			if self.url and str(self.url).startswith('http'):
				self._disable_kodi_url_resume(listitem, keep_start_percent=True)
			self.set_playback_properties()
		return listitem

	def _simkl_scrobble_start(self):
		if self.is_generic or st.watched_indicators() != 2 or not st.simkl_user_active(): return
		from apis.simkl_api import simkl_scrobble
		percent = self.playback_percent if self.playback_percent else 0
		Thread(target=simkl_scrobble, args=('start', self.media_type, self.tmdb_id, percent, self.season, self.episode)).start()

	def _simkl_scrobble_stop(self, percent):
		if self.is_generic or st.watched_indicators() != 2 or not st.simkl_user_active(): return
		from apis.simkl_api import simkl_scrobble
		Thread(target=simkl_scrobble, args=('stop', self.media_type, self.tmdb_id, percent, self.season, self.episode)).start()

	def media_watched_marker(self, force_watched=False):
		self.media_marked = True
		try:
			if self.current_point >= 90 or force_watched:
				self._simkl_scrobble_stop(100)
				watched_function = ws.mark_movie if self.media_type == 'movie' else ws.mark_episode
				watched_params = {'action': 'mark_as_watched', 'tmdb_id': self.tmdb_id, 'title': self.title, 'year': self.year, 'season': self.season, 'episode': self.episode,
									'tvdb_id': self.tvdb_id, 'from_playback': 'true'}
				Thread(target=self.run_media_progress, args=(watched_function, watched_params)).start()
			else:
				ku.clear_property('redlight.random_episode_history')
				if self.current_point >= 5:
					progress_params = {'media_type': self.media_type, 'tmdb_id': self.tmdb_id, 'curr_time': self.curr_time, 'total_time': self.total_time,
									'title': self.title, 'season': self.season, 'episode': self.episode, 'from_playback': 'true'}
					Thread(target=self.run_media_progress, args=(ws.set_bookmark, progress_params)).start()
		except: pass

	def run_media_progress(self, function, params):
		try: function(params)
		except: pass

	def _valid_playback_duration(self, total_time=None, curr_time=None):
		try:
			total = total_time if total_time is not None else self.getTotalTime()
			curr = curr_time if curr_time is not None else self.getTime()
			if total in (0, 0.0, '0.0', '', None): return False
			if curr in (0, 0.0, '0.0', '', None): return False
			if float(total) < 60: return False
			return float(curr) > 0
		except:
			return False

	def _should_prep_next_ep(self):
		if ku.get_property(PROP_NEXTEP_PENDING) == 'true':
			return False
		if not self._valid_playback_duration(self.total_time, self.curr_time):
			return False
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			return False
		return remaining > 0 and remaining <= self.start_prep

	def _schedule_next_ep(self):
		if ku.get_property(PROP_NEXTEP_PENDING) == 'true':
			return
		ku.set_property(PROP_NEXTEP_PENDING, 'true')
		meta = dict(self.meta)
		nextep_settings = dict(self.nextep_settings)
		player = self
		def _worker():
			try:
				if not player.media_marked:
					player.media_watched_marker(force_watched=True)
				ku.clear_property(PROP_NEXTEP_PENDING)
				from modules.episode_tools import EpisodeTools
				EpisodeTools(meta, nextep_settings).auto_nextep()
			except:
				pass
			finally:
				ku.clear_property(PROP_NEXTEP_PENDING)
		Thread(target=_worker, daemon=True).start()

	def run_next_ep(self):
		from modules.episode_tools import EpisodeTools
		if not self.media_marked: self.media_watched_marker(force_watched=True)
		EpisodeTools(self.meta, self.nextep_settings).auto_nextep()

	def run_random_continual(self):
		from modules.episode_tools import EpisodeTools
		if not self.media_marked: self.media_watched_marker(force_watched=True)
		EpisodeTools(self.meta).play_random_continual(False)

	def run_movie_stingers(self):
		self.movie_stingers_run = True
		stinger_keys = self.meta.get('stinger_keys', None)
		if not stinger_keys:
			try:
				keywords = self.meta.get('keywords', [])
				stinger_keys = [i['name'] for i in keywords['keywords'] if i['name'] in ('duringcreditsstinger', 'aftercreditsstinger')]
				self.meta['stinger_keys'] = stinger_keys
			except: pass
		if stinger_keys:
			from windows.base_window import open_window
			Thread(target=lambda: open_window(('windows.playback_notifications', 'StingersNotification'), 'playback_notifications.xml', meta=self.meta)).start()

	def set_resume_point(self, listitem):
		if self.playback_percent > 0.0: listitem.setProperty('StartPercent', str(self.playback_percent))

	def _disable_kodi_url_resume(self, listitem, keep_start_percent=False):
		# Kodi stores resume by stream URL/filename; debrid links reuse the same name and can reopen near EOF.
		if not keep_start_percent or float(listitem.getProperty('StartPercent') or 0) <= 0:
			listitem.setProperty('StartPercent', '0')
		listitem.setProperty('StartOffset', '0')
		try:
			listitem.getVideoInfoTag(True).setResumePoint(0.0)
		except:
			pass

	def info_next_ep(self):
		self.nextep_info_gathered = True
		play_type = 'autoplay_nextep' if self.autoplay_nextep else 'autoscrape_nextep'
		nextep_settings = st.auto_nextep_settings(play_type)
		watching_check = nextep_settings['watching_check']
		still_watching_check = 15 if self.meta_get('watch_count') == watching_check else 0
		final_chapter = self.final_chapter(90) if nextep_settings['use_chapters'] else None
		percentage = 100 - final_chapter if final_chapter else nextep_settings['window_percentage']
		try:
			window_time = round((percentage/100) * self.total_time) + still_watching_check
		except:
			window_time = nextep_settings['window_percentage'] + still_watching_check
		use_window = nextep_settings['alert_method'] == 0
		default_action = nextep_settings['default_action']
		self.start_prep = nextep_settings['scraper_time'] + window_time
		self.nextep_settings = {'use_window': use_window, 'window_time': window_time, 'default_action': default_action, 'play_type': play_type, 'watching_check': watching_check}

	def final_chapter(self, threshhold):
		try:
			final_chapter = float(ku.get_infolabel('Player.Chapters').split(',')[-1])
			if final_chapter >= threshhold: return final_chapter
		except: pass
		return None

	def kill_dialog(self):
		try:
			self.sources_object._kill_progress_dialog()
		except:
			if not getattr(self.sources_object, '_resolve_user_cancelled', False):
				ku.close_all_dialog()

	def set_constants(self, url, obj):
		self.url = url
		self.sources_object = obj
		self.is_generic = self.sources_object == 'video'
		self.kodi_monitor = ku.kodi_monitor()
		self.playback_successful = None
		self.cancel_all_playback = False
		if not self.is_generic:
			self.meta = self.sources_object.meta
			self.meta_get, self.playback_percent = self.meta.get, self.sources_object.playback_percent or 0.0
			self.playing_filename = self.sources_object.playing_filename
			self.media_marked, self.nextep_info_gathered, self.movie_stingers_run = False, False, False
			self.subs_searched = False
			self.playing_item = self.sources_object.playing_item

	def run_subtitles(self):
		self.subs_searched = True
		if not st.auto_enable_subs(): return
		if not st.submaker_enabled(): return
		if not self.imdb_id: return
		try:
			from indexers.subtitles import Subtitles
			poster = self.meta.get('poster') or ku.get_icon('box_office')
			season = self.season if self.media_type == 'episode' else None
			episode = self.episode if self.media_type == 'episode' else None
			Thread(target=Subtitles().run, args=(self.imdb_id, season, episode, poster)).start()
		except: pass

	def set_playback_properties(self):
		try:
			trakt_ids = {'tmdb': self.tmdb_id, 'imdb': self.imdb_id, 'slug': make_trakt_slug(self.title)}
			if self.media_type == 'episode': trakt_ids['tvdb'] = self.tvdb_id
			ku.set_property('script.trakt.ids', json.dumps(trakt_ids))
			if self.playing_filename: ku.set_property('subs.player_filename', self.playing_filename)
		except: pass

	def safe_stop(self):
		try:
			if ku.get_property(PROP_PLAY_OPENING) == 'true' or (self.isPlaying() and not self.isPlayingVideo()):
				for _ in range(80):
					try:
						if self.isPlayingVideo():
							ku.sleep(300)
							break
					except:
						pass
					ku.sleep(100)
				else:
					ku.sleep(400)
			ku.execute_builtin('PlayerControl(Stop)', block=True)
			stable_idle = 0
			for _ in range(80):
				playing = False
				try:
					playing = self.isPlaying() or self.isPlayingVideo()
				except:
					pass
				if playing:
					stable_idle = 0
					try:
						self.stop()
					except:
						pass
					ku.execute_builtin('PlayerControl(Stop)', block=False)
				else:
					stable_idle += 1
					if stable_idle >= 6:
						ku.sleep(400)
						return
				ku.sleep(100)
		except:
			pass
		finally:
			ku.clear_property(PROP_PLAY_OPENING)

	def clear_playback_properties(self, clear_navigation=True):
		if clear_navigation:
			ku.clear_property('redlight.window_stack')
		ku.clear_property('script.trakt.ids')
		ku.clear_property('subs.player_filename')

	def run_error(self, message=None):
		ku.clear_property(PROP_PLAY_OPENING)
		try:
			if not self.is_generic:
				self.sources_object.playback_successful = False
		except:
			pass
		self.clear_playback_properties(clear_navigation=not self.is_generic)
		if self.is_generic and ku.get_property('redlight.browse_playback') == 'true':
			return ku.notification('Playback Failed', 4000, settle_ms=400)
		# play_file walks the resolve queue and calls playback_failed_action after the last attempt.
		if not self.is_generic and getattr(self, 'sources_object', None):
			return
		text = message or 'This link could not be played. It may be expired, removed, or unsupported on this device.'
		ku.hide_busy_dialog()
		ku.sleep(400)
		try:
			return ku.kodi_dialog().ok('Playback failed', text)
		except Exception:
			try:
				return ku.ok_dialog(heading='Playback failed', text=text)
			except Exception:
				return ku.notification('Playback Failed', 4000, settle_ms=400)
