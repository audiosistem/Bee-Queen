# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from hashlib import md5
from json import dumps as jsdumps, loads as jsloads
from sys import argv, exit as sysexit
from sqlite3 import dbapi2 as database
import threading
import xbmc
from resources.lib.database.cache import clear_local_bookmarks
from resources.lib.database.metacache import fetch as fetch_metacache
from resources.lib.database.traktsync import fetch_bookmarks
from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.modules import playcount
from resources.lib.modules import trakt
from resources.lib.modules import opensubs
from difflib import SequenceMatcher
from resources.lib.modules.source_utils import seas_ep_filter
from urllib.request import urlopen, Request
from urllib.parse import unquote
import fnmatch
import os
LOGINFO = 1
getLS = control.lang
getSetting = control.setting
homeWindow = control.homeWindow
playerWindow = control.playerWindow
KODI_VERSION = control.getKodiVersion()


class Player(xbmc.Player):
	def __init__(self):
		xbmc.Player.__init__(self)
		self.play_next_triggered = False
		self.preScrape_triggered = False
		self.playbackStopped_triggered = False
		self.playback_resumed = False
		self.onPlayBackStopped_ran = False
		self.media_type = None
		self.DBID = None
		self.offset = '0'
		self.media_length = 0
		self.current_time = 0
		self.meta = {}
		self.enable_playnext = getSetting('enable.playnext') == 'true'
		self.playnext_time = int(getSetting('playnext.time')) or 60
		self.traktCredentials = trakt.getTraktCredentialsInfo()
		self.subtitletime = None

	def play_source(self, title, year, season, episode, imdb, tmdb, tvdb, url, meta, debridPackCall=False):
		try:
			from sys import argv # some functions like ActivateWindow() throw invalid handle less this is imported here.
			if not url: raise Exception
			self.media_type = 'movie' if season is None or episode is None else 'episode'
			self.title, self.year = title, str(year)
			if self.media_type == 'movie':
				self.name, self.season, self.episode = '%s (%s)' % (title, self.year), None, None
			elif self.media_type == 'episode':
				self.name, self.season, self.episode = '%s S%02dE%02d' % (title, int(season), int(episode)), '%01d' % int(season), '%01d' % int(episode)
			self.imdb, self.tmdb, self.tvdb = imdb or '', tmdb or '', tvdb or ''

			self.ids = {'imdb': self.imdb, 'tmdb': self.tmdb, 'tvdb': self.tvdb}
## - compare meta received to database and use largest(eventually switch to a request to fetch missing db meta for item)
			self.imdb_user = getSetting('imdb.user').replace('ur', '')
			self.tmdb_key = getSetting('tmdb.api.key')
			if not self.tmdb_key: self.tmdb_key = 'f2e500501d9fa3bd1637bfd00f11583a'
			self.tvdb_key = getSetting('tvdb.api.key')
			if self.media_type == 'episode': self.user = str(self.imdb_user) + str(self.tvdb_key)
			else: self.user = str(self.tmdb_key)
			self.lang = control.apiLanguage()['tvdb']
			meta1 = dict((k, v) for k, v in iter(meta.items()) if v is not None and v != '') if meta else None
			meta2 = fetch_metacache([{'imdb': self.imdb, 'tmdb': self.tmdb, 'tvdb': self.tvdb}], self.lang, self.user)[0]
			if meta2 != self.ids: meta2 = dict((k, v) for k, v in iter(meta2.items()) if v is not None and v != '')
			if meta1 is not None:
				try:
					if len(meta2) > len(meta1):
						meta2.update(meta1)
						meta = meta2
					else: meta = meta1
				except: log_utils.error()
			else: meta = meta2 if meta2 != self.ids else meta1
##################
			self.poster = meta.get('poster') if meta else ''
			self.fanart = meta.get('fanart') if meta else ''
			self.meta = meta
			poster, thumb, season_poster, fanart, banner, clearart, clearlogo, discart, meta = self.getMeta(meta)
			self.offset = Bookmarks().get(name=self.name, imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season, episode=episode, year=self.year, runtime=meta.get('duration') if meta else 0)

			if self.offset == '-1':
				log_utils.log('User requested playback cancel', level=log_utils.LOGDEBUG)
				control.notification(message=32328)
				return control.cancelPlayback()

						# URL validity check (optional)
			try:
				if getSetting('validate.source.urls') == 'true':
					from resources.lib.modules import urlcheck
					if not urlcheck.check_url_validity(url):
						log_utils.log('Rejected invalid URL (player.play_source): %s' % url, level=log_utils.LOGWARNING)
						return control.cancelPlayback()
			except Exception:
				pass

			item = control.item(path=url)
			if self.media_type == 'episode':
				item.setArt({'tvshow.clearart': clearart, 'tvshow.clearlogo': clearlogo, 'tvshow.discart': discart, 'thumb': thumb, 'tvshow.poster': season_poster, 'season.poster': season_poster, 'tvshow.fanart': fanart})
			else:
				item.setArt({'clearart': clearart, 'clearlogo': clearlogo, 'discart': discart, 'thumb': thumb, 'poster': poster, 'fanart': fanart})
			control.infoTagger(item, self.meta)
			item.setProperty('IsPlayable', 'true')
			# Save playback metadata for SubtitlePlayer BEFORE resolve() — script dies after resolve()
			homeWindow.setProperty('luc_kodi.sub.title', self.title or '')
			homeWindow.setProperty('luc_kodi.sub.year', self.year or '')
			homeWindow.setProperty('luc_kodi.sub.imdb', self.imdb or '')
			homeWindow.setProperty('luc_kodi.sub.season', self.season or '')
			homeWindow.setProperty('luc_kodi.sub.episode', self.episode or '')
			if debridPackCall: control.player.play(url, item) # seems this is only way browseDebrid pack files will play and have meta marked as watched
			else: control.resolve(int(argv[1]), True, item, self.meta)
			homeWindow.setProperty('script.trakt.ids', jsdumps(self.ids))
			self.keepAlive()
			homeWindow.clearProperty('script.trakt.ids')
		except:
			log_utils.error()
			return control.cancelPlayback()

	def getMeta(self, meta):
		try:
			if not meta or ('videodb' in control.infoLabel('ListItem.FolderPath')): raise Exception()
			poster = meta.get('poster3') or meta.get('poster2') or meta.get('poster') #poster2 and poster3 may not be passed anymore
			thumb = meta.get('thumb')
			thumb = thumb or poster or control.addonThumb()
			season_poster = meta.get('season_poster') or poster
			fanart = meta.get('fanart')
			banner = meta.get('banner')
			clearart = meta.get('clearart')
			clearlogo = meta.get('clearlogo')
			discart = meta.get('discart')
			if 'mediatype' not in meta:
				meta.update({'mediatype': 'episode' if self.episode else 'movie'})
				if self.episode: meta.update({'tvshowtitle': self.title, 'season': self.season, 'episode': self.episode})
			return (poster, thumb, season_poster, fanart, banner, clearart, clearlogo, discart, meta)
		except: log_utils.error()
		try:
			def cleanLibArt(art):
				from urllib.parse import unquote
				if not art: return ''
				art = unquote(art.replace('image://', ''))
				if art.endswith('/'): art = art[:-1]
				return art
			def sourcesDirMeta(metadata): # pass player minimal meta needed from lib pull
				if not metadata: return metadata
				allowed = ['mediatype', 'imdb', 'tmdb', 'tvdb', 'poster', 'season_poster', 'fanart', 'banner', 'clearart', 'clearlogo', 'discart', 'thumb', 'title', 'tvshowtitle', 'year', 'premiered', 'rating', 'plot', 'duration', 'mpaa', 'season', 'episode', 'castandrole']
				return {k: v for k, v in iter(metadata.items()) if k in allowed}
			poster, thumb, season_poster, fanart, banner, clearart, clearlogo, discart, meta = '', '', '', '', '', '', '', '', {'title': self.name}
			if self.media_type != 'movie': raise Exception()
			# do not add IMDBNUMBER as tmdb scraper puts their id in the key value
			meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "uniqueid", "year", "premiered", "genre", "studio", "country", "runtime", "rating", "votes", "mpaa", "director", "writer", "cast", "plot", "plotoutline", "tagline", "thumbnail", "art", "file"]}, "id": 1}' % (self.year, str(int(self.year) + 1), str(int(self.year) - 1)))
			meta = jsloads(meta)['result']['movies']
			meta = [i for i in meta if (i.get('uniqueid', []).get('imdb', '') == self.imdb) or (i.get('uniqueid', []).get('unknown', '') == self.imdb)] # scraper now using "unknown"
			if meta: meta = meta[0]
			else: raise Exception()
			if 'mediatype' not in meta: meta.update({'mediatype': 'movie'})
			if 'duration' not in meta: meta.update({'duration': meta.get('runtime')}) # Trakt scrobble resume needs this for lib playback
			if 'castandrole' not in meta: meta.update({'castandrole': [(i['name'], i['role']) for i in meta.get('cast')]})
			thumb = cleanLibArt(meta.get('art').get('thumb', ''))
			poster = cleanLibArt(meta.get('art').get('poster', '')) or self.poster
			fanart = cleanLibArt(meta.get('art').get('fanart', '')) or self.fanart
			banner = cleanLibArt(meta.get('art').get('banner', '')) # not sure this is even used by player
			clearart = cleanLibArt(meta.get('art').get('clearart', ''))
			clearlogo = cleanLibArt(meta.get('art').get('clearlogo', ''))
			discart = cleanLibArt(meta.get('art').get('discart'))
			if 'plugin' not in control.infoLabel('Container.PluginName'):
				self.DBID = meta.get('movieid')
			meta = sourcesDirMeta(meta)
			return (poster, thumb, '', fanart, banner, clearart, clearlogo, discart, meta)
		except: log_utils.error()
		try:
			if self.media_type != 'episode': raise Exception()
			# do not add IMDBNUMBER as tmdb scraper puts their id in the key value
			show_meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "uniqueid", "mpaa", "year", "genre", "runtime", "thumbnail", "file"]}, "id": 1}' % (self.year, str(int(self.year)+1), str(int(self.year)-1)))
			show_meta = jsloads(show_meta)['result']['tvshows']
			show_meta = [i for i in show_meta if i['uniqueid']['imdb'] == self.imdb]
			show_meta = [i for i in show_meta if (i.get('uniqueid', []).get('imdb', '') == self.imdb) or (i.get('uniqueid', []).get('unknown', '') == self.imdb)] # scraper now using "unknown"
			if show_meta: show_meta = show_meta[0]
			else: raise Exception()
			tvshowid = show_meta['tvshowid']
			meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params":{"tvshowid": %d, "filter":{"and": [{"field": "season", "operator": "is", "value": "%s"}, {"field": "episode", "operator": "is", "value": "%s"}]}, "properties": ["showtitle", "title", "season", "episode", "firstaired", "runtime", "rating", "director", "writer", "cast", "plot", "thumbnail", "art", "file"]}, "id": 1}' % (tvshowid, self.season, self.episode))
			meta = jsloads(meta)['result']['episodes']
			if meta: meta = meta[0]
			else: raise Exception()
			if 'mediatype' not in meta: meta.update({'mediatype': 'episode'})
			if 'tvshowtitle' not in meta: meta.update({'tvshowtitle': meta.get('showtitle')})
			if 'castandrole' not in meta: meta.update({'castandrole': [(i['name'], i['role']) for i in meta.get('cast')]})
			if 'genre' not in meta: meta.update({'genre': show_meta.get('genre')})
			if 'duration' not in meta: meta.update({'duration': meta.get('runtime')}) # Trakt scrobble resume needs this for lib playback but Kodi lib returns "0" for shows or episodes
			if 'mpaa' not in meta: meta.update({'mpaa': show_meta.get('mpaa')})
			if 'premiered' not in meta: meta.update({'premiered': meta.get('firstaired')})
			if 'year' not in meta: meta.update({'year': show_meta.get('year')}) # shows year not year episode aired
			thumb = cleanLibArt(meta.get('art').get('thumb', ''))
			season_poster = poster = cleanLibArt(meta.get('art').get('season.poster', '')) or self.poster
			fanart = cleanLibArt(meta.get('art').get('tvshow.fanart', '')) or self.poster
			banner = cleanLibArt(meta.get('art').get('tvshow.banner', '')) # not sure this is even used by player
			clearart = cleanLibArt(meta.get('art').get('tvshow.clearart', ''))
			clearlogo = cleanLibArt(meta.get('art').get('tvshow.clearlogo', ''))
			discart = cleanLibArt(meta.get('art').get('discart'))
			if 'plugin' not in control.infoLabel('Container.PluginName'):
				self.DBID = meta.get('episodeid')
			meta = sourcesDirMeta(meta)
			return (poster, thumb, season_poster, fanart, banner, clearart, clearlogo, discart, meta)
		except:
			log_utils.error()
			return (poster, thumb, season_poster, fanart, banner, clearart, clearlogo, discart, meta)

	def getWatchedPercent(self):
		if self.isPlayback():
			try:
				position = self.getTime()
				if position != 0: self.current_time = position
				total_length = self.getTotalTime()
				if total_length != 0: self.media_length = total_length
			except: pass
		current_position = self.current_time
		total_length = self.media_length
		watched_percent = 0
		if int(total_length) != 0:
			try:
				watched_percent = float(current_position) / float(total_length) * 100
				if watched_percent > 100: watched_percent = 100
			except: log_utils.error()
		return watched_percent

	def getRemainingTime(self):
		remaining_time = 0
		if self.isPlayback():
			try:
				current_position = self.getTime()
				remaining_time = int(self.media_length) - int(current_position)
			except: pass
		return remaining_time

	def keepAlive(self):
		pname = '%s.player.overlay' % control.addonInfo('id')
		homeWindow.clearProperty(pname)
		for i in range(0, 500):
			if self.isPlayback():
				control.closeAll()
				break
			xbmc.sleep(200)

		# ── Subtitles: invoke here because onAVStarted callbacks are unreliable
		# with reuseLanguageInvoker=true on Android (Kodi cannot dispatch callbacks
		# to a thread blocked in xbmc.sleep). Called once, right after the video
		# is confirmed playing — exactly as Umbrella does in its onAVStarted.
		try:
			import xbmcaddon as _xa
			_subs_enabled = _xa.Addon('plugin.video.luc_kodi').getSetting('subtitles')
		except:
			_subs_enabled = getSetting('subtitles')
		control.log('[ luc_kodi ] keepAlive subtitles setting: "%s"' % _subs_enabled, LOGINFO)

		if _subs_enabled == 'true':
			control.log('[ luc_kodi ] keepAlive — calling Subtitles().get()', LOGINFO)

			try:
				Subtitles().get(self.title, self.year, self.imdb, self.season, self.episode)
			except:
				log_utils.error()

		xbmc.sleep(5000)
		playlist_skip = False
		try: running_path = self.getPlayingFile() # original video that playlist playback started with
		except: running_path = ''

		if playerWindow.getProperty('luc_kodi.playlistStart_position'): pass
		else:
			if control.playlist.size() > 1: playerWindow.setProperty('luc_kodi.playlistStart_position', str(control.playlist.getposition()))

		while self.isPlayingVideo() and not control.monitor.abortRequested():
			try:
				if running_path != self.getPlayingFile(): # will not match if user hits "Next" so break from keepAlive()
					playlist_skip = True
					break

				try:
					self.current_time = self.getTime()
					self.media_length = self.getTotalTime()
				except: pass
				watcher = (self.getWatchedPercent() >= 85)
				property = homeWindow.getProperty(pname)

				if self.media_type == 'movie':
					try:
						if watcher and property != '5':
							homeWindow.setProperty(pname, '5')
							playcount.markMovieDuringPlayback(self.imdb, '5')
					except: pass
					xbmc.sleep(2000)

				elif self.media_type == 'episode':
					try:
						if watcher and property != '5':
							homeWindow.setProperty(pname, '5')
							playcount.markEpisodeDuringPlayback(self.imdb, self.tvdb, self.season, self.episode, '5')
						if self.enable_playnext and not self.play_next_triggered:
							if int(control.playlist.size()) > 1:
								if self.preScrape_triggered == False:
									xbmc.executebuiltin('RunPlugin(plugin://plugin.video.luc_kodi/?action=play_preScrapeNext)')
									self.preScrape_triggered = True
								remaining_time = self.getRemainingTime()
								if remaining_time < (self.playnext_time + 1) and remaining_time != 0:
									xbmc.executebuiltin('RunPlugin(plugin://plugin.video.luc_kodi/?action=play_nextWindowXML)')
									self.play_next_triggered = True
					except: log_utils.error()
					xbmc.sleep(1000)

			except:
				log_utils.error()
				xbmc.sleep(1000)
		homeWindow.clearProperty(pname)
		if playlist_skip: pass
		else:
			# # self.onPlayBackEnded() # check, kodi may at times not issue "onPlayBackEnded" callback
			# if self.media_length - self.current_time > 60: # kodi may at times not issue "onPlayBackStopped" callback
			if (int(self.current_time) > 180 and (self.getWatchedPercent() < 85)): # kodi may at times not issue "onPlayBackStopped" callback
				self.playbackStopped_triggered = True
				self.onPlayBackStopped()

	def _queue_next_ep_if_needed(self):
		"""Daisy-chain: add the next episode to the playlist after the current one starts.
		Called once per episode from keepAlive(). This lets PlayNext (popup + prescrape)
		work correctly without interfering with setResolvedUrl for the current episode.

		Logic: only add when we are at the LAST position in the playlist, so we don't
		duplicate items and correctly extend the chain episode by episode.
		"""
		try:
			if not self.enable_playnext or self.media_type != 'episode':
				return
			pos  = control.playlist.getposition()
			size = control.playlist.size()
			# Already has a queued next item → nothing to do
			if size > 0 and pos < (size - 1):
				return
			from json import dumps as jsdumps
			from urllib.parse import quote_plus
			next_ep     = int(self.episode) + 1
			next_season = int(self.season)
			# Build minimal meta for the next episode (show-level info + updated S/E).
			# The accurate episode title / premiered come from the prescrape path;
			# here we only need enough for the PlayNext popup to identify the episode.
			next_meta = dict(self.meta) if self.meta else {}
			next_meta['season']    = str(next_season)
			next_meta['episode']   = str(next_ep)
			next_meta['mediatype'] = 'episode'
			# Remove E01-specific per-episode fields so they don't mislead the popup
			for _k in ('thumb', 'plot', 'premiered', 'title', 'landscape'):
				next_meta.pop(_k, None)
			title_str      = self.title or ''
			systvshowtitle = quote_plus(title_str)
			sysmeta        = quote_plus(jsdumps(next_meta))
			next_url = (
				'plugin://plugin.video.luc_kodi/?action=play_Item'
				'&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s'
				'&season=%s&episode=%s&tvshowtitle=%s&premiered=&meta=%s&select=1'
			) % (
				systvshowtitle, self.year or '',
				self.imdb or '', self.tmdb or '', self.tvdb or '',
				next_season, next_ep, systvshowtitle, sysmeta
			)
			li = control.item(label='%s S%02dE%02d' % (title_str, next_season, next_ep), offscreen=True)
			li.setProperty('IsPlayable', 'true')
			control.playlist.add(url=next_url, listitem=li)
			# Also store URL in playerWindow so PlayNextXML can call it directly
			# (needed because setResolvedUrl playback is NOT playlist-based)
			playerWindow.setProperty('luc_kodi.nextEpisode_playUrl', next_url)
			log_utils.log(
				'[ plugin.video.luc_kodi ] PlayNext: queued S%02dE%02d to playlist (pos=%d size=%d→%d)'
				% (next_season, next_ep, pos, size, control.playlist.size()),
				level=log_utils.LOGDEBUG
			)
		except:
			log_utils.error()

	def isPlayingFile(self):
		try:
			return not self.getPlayingFile().startswith('plugin://')
		except:
			return False

	def isPlayback(self):
		# Kodi often starts playback where isPlaying() is true and isPlayingVideo() is false, since the video loading is still in progress, whereas the play is already started.
		return self.isPlaying() and self.isPlayingVideo() and self.getTime() >= 0

	def libForPlayback(self):
		if self.DBID is None: return
		try:
			if self.media_type == 'movie':
				rpc = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": %s, "playcount": 1 }, "id": 1 }' % str(self.DBID)
			elif self.media_type == 'episode':
				rpc = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": {"episodeid": %s, "playcount": 1 }, "id": 1 }' % str(self.DBID)
			control.jsonrpc(rpc)
		except: log_utils.error()

### Kodi player callback methods ###
	def onAVStarted(self): # Kodi docs suggests "Use onAVStarted() instead of onPlayBackStarted() as of v18"
		for i in range(0, 500):
			if self.isPlayback():
				control.closeAll()
				break
			else: control.sleep(200)
		# MDBList Continue Watching: if Bookmarks().get() returned '0', check our
		# window property for a direct resume override (set by mdblist_menus.py)
		if self.offset == '0':
			try:
				_mdb_key = 'mdblist.resume.%s.%s.%s' % (
					self.imdb or self.tmdb or '',
					self.season or '0',
					self.episode or '0',
				)
				_mdb_sec = homeWindow.getProperty(_mdb_key)
				if _mdb_sec:
					self.offset = str(float(_mdb_sec))
					homeWindow.clearProperty(_mdb_key)
			except: pass
		if self.offset != '0' and self.playback_resumed is False:
			control.sleep(200)
			if getSetting('trakt.scrobble') == 'true' and getSetting('resume.source') == '1': # re-adjust the resume point since dialog is based on meta runtime vs. getTotalTime() and inaccurate
				try:
					total_time = self.getTotalTime()
					progress = float(fetch_bookmarks(self.imdb, self.tmdb, self.tvdb, self.season, self.episode))
					self.offset = (progress / 100) * total_time
				except: pass
			self.seekTime(self.offset)
			self.playback_resumed = True
		
		if self.traktCredentials:
			trakt.scrobbleReset(imdb=self.imdb, tmdb=self.tmdb, tvdb=self.tvdb, season=self.season, episode=self.episode, refresh=False) # refresh issues container.refresh()
		# Double-check via xbmcaddon direct API in case settings cache isn't updated yet
		try:
			import xbmcaddon as _xa
			_subs_enabled = _xa.Addon('plugin.video.luc_kodi').getSetting('subtitles')
		except:
			_subs_enabled = getSetting('subtitles')
		control.log('[ luc_kodi ] subtitles setting value: "%s"' % _subs_enabled, LOGINFO)

		if _subs_enabled == 'true':
			control.log('[ luc_kodi ] subtitles enabled — calling Subtitles().get()', LOGINFO)

			try:
				Subtitles().get(self.title, self.year, self.imdb, self.season, self.episode)
			except:
				log_utils.error()
		xbmc.log('[ plugin.video.luc_kodi ] onAVStarted callback', LOGINFO)
		control.log('[ plugin.video.luc_kodi ] onAVStarted callback', LOGINFO)


	def onPlayBackSeek(self, time, seekOffset):
		seekOffset /= 1000

	def onPlayBackSeekChapter(self, chapter):
		control.log('[ plugin.video.luc_kodi ] onPlayBackSeekChapter callback', LOGINFO)


	def onQueueNextItem(self):
		control.log('[ plugin.video.luc_kodi ] onQueueNextItem callback', LOGINFO)


	def onPlayBackStopped(self):
		try:
			playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
			playerWindow.clearProperty('luc_kodi.playlistStart_position')
			playerWindow.clearProperty('luc_kodi.nextEpisode_playUrl')
			playerWindow.clearProperty('luc_kodi.playnext_showing')
			clear_local_bookmarks() # clear all luc_kodi bookmarks from kodi database

			if not self.onPlayBackStopped_ran or (self.playbackStopped_triggered and not self.onPlayBackStopped_ran): # Kodi callback unreliable and often not issued
				self.onPlayBackStopped_ran = True
				self.playbackStopped_triggered = False
				Bookmarks().reset(self.current_time, self.media_length, self.name, self.year)
				if self.traktCredentials and (getSetting('trakt.scrobble') == 'true'):
					Bookmarks().set_scrobble(self.current_time, self.media_length, self.media_type, self.imdb, self.tmdb, self.tvdb, self.season, self.episode)
				watcher = self.getWatchedPercent()
				seekable = (int(self.current_time) > 180 and (watcher < 85))
				if watcher >= 85: self.libForPlayback() # only write playcount to local lib

				if getSetting('crefresh') == 'true' and seekable:
					control.log('[ plugin.video.luc_kodi ] container.refresh issued', LOGINFO)

					control.refresh() #not all skins refresh after playback stopped
				control.playlist.clear()
				# control.trigger_widget_refresh() # skinshortcuts handles widget refresh
				xbmc.log('[ plugin.video.luc_kodi ] onPlayBackStopped callback', LOGINFO)
				control.log('[ plugin.video.luc_kodi ] onPlayBackStopped callback', LOGINFO)

		except: log_utils.error()

	def onPlayBackEnded(self):
		Bookmarks().reset(self.current_time, self.media_length, self.name, self.year)
		self.libForPlayback()
		playerWindow.clearProperty('luc_kodi.nextEpisode_playUrl')
		playerWindow.clearProperty('luc_kodi.playnext_showing')
		# Only clear playlist when we are genuinely at the last item (not when size==1 from daisy-chain)
		if control.playlist.getposition() == control.playlist.size() and control.playlist.size() > 0:
			control.playlist.clear()
		xbmc.log('[ plugin.video.luc_kodi ] onPlayBackEnded callback', LOGINFO)
		control.log('[ plugin.video.luc_kodi ] onPlayBackEnded callback', LOGINFO)


	def onPlayBackError(self):
		playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
		playerWindow.clearProperty('luc_kodi.playlistStart_position')
		playerWindow.clearProperty('luc_kodi.nextEpisode_playUrl')

		Bookmarks().reset(self.current_time, self.media_length, self.name, self.year)
		log_utils.error()
		xbmc.log('[ plugin.video.luc_kodi ] onPlayBackError callback', LOGINFO)
		control.log('[ plugin.video.luc_kodi ] onPlayBackError callback', LOGINFO)

		sysexit(1)
##############################

def _score_subtitle(sub, year):
    """
    Puntúa un candidato de OpenSubtitles para una película (0-100).

    Criterios (de mayor a menor peso):
      1. Popularidad reciente  – new_download_count       (0-40 pts)
      2. Calidad valorada      – ratings × sqrt(votes)    (0-20 pts)
      3. Fuente fiable         – from_trusted             (+15 pts)
      4. Traducción humana     – no ai, no machine        (+15 pts)
      5. Año en el nombre      – coincidencia con year    (+5 pts)
      6. Sin HI                – hearing_impaired=False   (+5 pts)
    """
    score = 0.0

    # 1. Popularidad (normalizada a 40 pts, cap en 50.000 descargas)
    downloads = min(sub.get('downloads', 0), 50000)
    score += (downloads / 50000.0) * 40.0

    # 2. Calidad: ratings (0-10) × sqrt(votes), normalizado a 20 pts
    ratings = sub.get('ratings', 0.0)
    votes   = sub.get('votes', 0)
    if ratings > 0 and votes > 0:
        import math
        quality = ratings * math.sqrt(votes)
        score += min(quality / 25.0, 20.0)   # 25 = 10*sqrt(6.25) ~ umbral razonable

    # 3. Fuente fiable
    if sub.get('trusted'):
        score += 15.0

    # 4. Traducción humana (penalizar IA y machine)
    if not sub.get('ai') and not sub.get('machine'):
        score += 15.0

    # 5. Año coincide en el nombre del fichero
    if year and str(year) in (sub.get('fileName') or ''):
        score += 5.0

    # 6. Sin subtítulos para sordos (leve preferencia)
    if not sub.get('hi'):
        score += 5.0

    return score


class Subtitles:
	"""
	Gestiona la descarga y aplicación automática de subtítulos desde OpenSubtitles.com.
	Se instancia desde Player.keepAlive() al inicio de la reproducción.
	También calcula el tiempo de PlayNext basándose en la última línea del .srt.
	"""
	def __init__(self):
		self.debuglog        = control.setting('debug.level') == '1'
		self.playnext_method = getSetting('playnext.method')

	def get(self, title, year, imdb, season, episode):
		try:
			import re
		except:
			return log_utils.error()
		try:
			control.log('[ luc_kodi ] Subtitles.get() START — title:%s imdb:%s season:%s ep:%s' % (title, imdb, season, episode), LOGINFO)

			quality = ['bluray', 'hdrip', 'brrip', 'bdrip', 'dvdrip', 'webrip', 'hdtv']
			langs = [getSetting('subtitles.lang.1'), getSetting('subtitles.lang.2')]
			control.log('[ luc_kodi ] Subtitles langs: %s' % langs, LOGINFO)


			# ¿El stream ya tiene el idioma deseado?
			try:    subLang = xbmc.Player().getSubtitles()
			except: subLang = ''
			if subLang == 'gre': subLang = 'ell'
			control.log('[ luc_kodi ] Current stream subLang: "%s"' % subLang, LOGINFO)

			# Solo salir si el idioma coincide Y el fichero de subtítulos existe en disco.
			# Si no existe (ej: reanudación tras salir), hay que volver a descargar.
			if subLang == langs[0]:
				try:
					lang_code = xbmc.convertLanguage(langs[0], xbmc.ISO_639_1)
				except:
					lang_code = langs[0]
				srt_path = control.joinPath(control.subtitlesPath, 'TemporarySubs.%s.srt' % lang_code)
				srt_exists = control.existsPath(srt_path)
				control.log('[ luc_kodi ] Subtitles: srt_exists=%s path=%s' % (srt_exists, srt_path), LOGINFO)
				if srt_exists:
					if getSetting('subtitles.notification') == 'true':
						if Player().isPlayback():
							control.sleep(1000)
							control.notification(message=getLS(32393) % subLang.upper(), time=5000)
					return log_utils.log(getLS(32393) % subLang.upper(), level=log_utils.LOGDEBUG)
				# Fichero no existe → reanudación: continuar con descarga

			# ¿Hay subtítulos embebidos disponibles?
			try:
				subLangs = xbmc.Player().getAvailableSubtitleStreams()
				if 'gre' in subLangs: subLangs[subLangs.index('gre')] = 'ell'
				subLang = [i for i in subLangs if i == langs[0]][0]
			except: subLangs = subLang = ''
			control.log('[ luc_kodi ] Available subtitle streams: %s' % subLangs, LOGINFO)

			if subLangs and subLang == langs[0]:
				control.sleep(1000)
				xbmc.Player().setSubtitleStream(subLangs.index(subLang))
				if getSetting('subtitles.notification') == 'true':
					if Player().isPlayback():
						control.sleep(1000)
						control.notification(message=getLS(32394) % subLang.upper(), time=5000)
				return log_utils.log(getLS(32394) % subLang.upper(), level=log_utils.LOGDEBUG)

			# Autenticar en OpenSubtitles
			control.log('[ luc_kodi ] Attempting OpenSubs auth...', LOGINFO)

			_user = control.setting('opensubsusername')
			_pass = control.setting('opensubspassword')
			control.log('[ luc_kodi ] OpenSubs user: "%s" pass_set: %s' % (_user, bool(_pass)), LOGINFO)

			if opensubs.Opensubs().auth():
				control.log('[ luc_kodi ] OpenSubs auth OK.', LOGINFO)

			else:
				control.log('[ luc_kodi ] OpenSubs auth FAILED.', LOGINFO)

				return control.notification(message=getLS(40509), time=5000)

			# Buscar subtítulos
			if not (season is None or episode is None):
				result = opensubs.Opensubs().getSubs(title, imdb, year, season, episode)
				control.log('[ luc_kodi ] Subtitles.get() episode: results=%s' % len(result), LOGINFO)
				fmt = ['hdtv']
			else:
				result = opensubs.Opensubs().getSubs(title, imdb, year, season, episode)
				control.log('[ luc_kodi ] Subtitles.get() movie: lang1 results=%s' % len(result), LOGINFO)
				if not result:
					# Fallback: try secondary language
					lang2 = getSetting('subtitles.lang.2')
					if lang2:
						control.log('[ luc_kodi ] Subtitles.get() movie: no lang1 results, trying lang2=%s' % lang2, LOGINFO)
						result = opensubs.Opensubs().getSubs(title, imdb, year, season, episode, lang_override=lang2)
						control.log('[ luc_kodi ] Subtitles.get() movie: lang2 results=%s' % len(result), LOGINFO)
				try:    vidPath = xbmc.Player().getPlayingFile()
				except: vidPath = ''
				fmt = re.split(r'\.|\\(|\\)|\\[|\\]|\\s|\\-', vidPath)
				fmt = [i.lower() for i in fmt if i is not None]
				fmt = [i for i in fmt if i in quality]

			# Selección de subtítulo
			try:    vidPath = xbmc.Player().getPlayingFile()
			except: vidPath = ''
			pFileName = unquote(os.path.basename(vidPath))
			pFileName = os.path.splitext(pFileName)[0]
			control.log('[ luc_kodi ] Subtitles pFileName="%s" results=%s' % (pFileName, len(result) if result else 0), LOGINFO)
			matches = []
			if result:
				if season:
					# TV Shows: SequenceMatcher contra nombre de fichero del stream
					for j in result:
						if not j.get('fileName'):
							continue
						if seas_ep_filter(season, episode, j['fileName']):
							seq = SequenceMatcher(None, pFileName.lower(), j['fileName'].lower())
							matches.append({'fileName': j['fileName'], 'fileID': j['fileID'], 'ratio': seq.ratio()})
					matches.sort(key=lambda i: i['ratio'], reverse=True)
				else:
					# Movies: scoring multi-criterio con metadatos de OpenSubtitles
					for j in result:
						if not j.get('fileName'):
							continue
						score = _score_subtitle(j, year)
						matches.append({'fileName': j['fileName'], 'fileID': j['fileID'], 'ratio': score})
						control.log('[ luc_kodi ] Subtitles score=%.1f  file=%s' % (score, j['fileName']), LOGINFO)
					matches.sort(key=lambda i: i['ratio'], reverse=True)
			filter = matches
			if not filter:
				if getSetting('subtitles.notification') == 'true':
					return control.notification(message=getLS(32395))
				return None

			try:    lang = xbmc.convertLanguage(getSetting('subtitles.lang.1'), xbmc.ISO_639_1)
			except: lang = getSetting('subtitles.lang.1')

			filename = filter[0]['fileName']
			control.log('[ luc_kodi ] Subtitles: subtítulo seleccionado="%s" fileID=%s' % (filename, filter[0]['fileID']), LOGINFO)

			try:
				downloadURL, downloadFileName = opensubs.Opensubs().downloadSubs(filter[0]['fileID'], filter[0]['fileName'])
				control.log('[ luc_kodi ] Subtitles: downloadURL=%s' % downloadURL, LOGINFO)
			except Exception as e:
				control.log('[ luc_kodi ] Subtitles: downloadSubs EXCEPTION: %s' % str(e), LOGINFO)
				return

			if not control.existsPath(control.subtitlesPath): control.makeFile(control.subtitlesPath)
			download_path = control.subtitlesPath

			def find(pattern, path):
				result = []
				for root, dirs, files in os.walk(path):
					for name in files:
						if fnmatch.fnmatch(name, pattern):
							result.append(os.path.join(root, name))
				return result

			def download_opensubs(downloadURL, downloadFileName):
				control.log('[ luc_kodi ] Descargando .srt desde OpenSubs.', LOGINFO)

				reqqqq = Request(downloadURL, headers={'User-Agent': 'Magic Browser'})
				http_response = urlopen(reqqqq)
				response = http_response.read().decode('utf-8')
				srtFile = os.path.join(download_path, downloadFileName + '.srt')
				with open(srtFile, 'w') as file:
					file.write(response)

			from resources.lib.modules import tools
			tools.delete_all_subs()
			try:
				download_opensubs(downloadURL, downloadFileName)
			except Exception as e:
				control.log('[ luc_kodi ] Subtitles: download_opensubs EXCEPTION: %s' % str(e), LOGINFO)

			subtitles = find('*.srt', download_path)
			control.log('[ luc_kodi ] Subtitles: srt files found=%s' % len(subtitles), LOGINFO)
			subtitle_matches = []
			if len(subtitles) > 1:
				if season:
					for count, i in enumerate(subtitles):
						sFileName = unquote(os.path.basename(i))
						sFileName = os.path.splitext(sFileName)[0]
						if seas_ep_filter(season, episode, sFileName.lower()):
							seq = SequenceMatcher(None, pFileName.lower(), sFileName.lower())
							subtitle_matches.append({'fullPath': subtitles[count], 'matchRatio': seq.ratio()})
				else:
					for count, i in enumerate(subtitles):
						sFileName = unquote(os.path.basename(i))
						sFileName = os.path.splitext(sFileName)[0]
						seq = SequenceMatcher(None, pFileName.lower(), sFileName.lower())
						subtitle_matches.append({'fullPath': subtitles[count], 'matchRatio': seq.ratio()})
				subtitle_matches.sort(key=lambda i: i['matchRatio'], reverse=True)
				subtitles = subtitle_matches[0]['fullPath']
			else:
				subtitles = subtitles[0]

			xbmc.sleep(1000)
			tempFileName = control.joinPath(download_path, 'TemporarySubs.%s.srt' % lang)
			with open(subtitles, 'r') as f:
				content = f.read()
			with open(tempFileName, 'w') as f1:
				f1.write(content)

			xbmc.Player().setSubtitles(tempFileName)

			if getSetting('subtitles.notification') == 'true':
				if Player().isPlayback():
					control.sleep(500)
					control.notification(title=filename, message=getLS(40506) % lang.upper())

			# Calcular tiempo de PlayNext por subtítulos (método 2)
			if self.playnext_method == '2' and getSetting('enable.playnext') == 'true' and Player().subtitletime is None:
				times = []
				pattern = r'(\d{2}:\d{2}:\d{2},d{3}$)|(\d{2}:\d{2}:\d{2})'
				with control.openFile(subtitles) as file:
					text = file.read()
					times = re.findall(pattern, text)
					times = times[len(times) - 4][-1]
					file.close()
				if len(times) > 0:
					total_time = Player().media_length
					h, m, s = str(times).split(':')
					totalSeconds = int(h) * 3600 + int(m) * 60 + int(s)
					Player().subtitletime = int(total_time) - int(totalSeconds)
				else:
					Player().subtitletime = 'default'
		except:
			log_utils.error()

	def downloadForPlayNext(self, title, year, imdb, season, episode, media_length):
		"""
		Descarga (o reutiliza) el subtítulo para determinar cuándo lanzar el popup
		de PlayNext basándose en la última línea del .srt.
		Devuelve segundos antes del final, 'default', o None.
		"""
		try:
			try:    import re
			except: return log_utils.error()
			try:    lang = xbmc.convertLanguage(getSetting('subtitles.lang.1'), xbmc.ISO_639_1)
			except: lang = getSetting('subtitles.lang.1')
			if not control.existsPath(control.subtitlesPath): control.makeFile(control.subtitlesPath)
			download_path = control.subtitlesPath

			# Primero intentar reutilizar caché
			try:
				tempFileName = control.joinPath(download_path, 'TemporarySubs.%s.srt' % lang)
				if os.path.isfile(tempFileName):
					control.log('[ luc_kodi ] Subtítulo en caché encontrado para PlayNext.', LOGINFO)

					xbmc.sleep(1000)
					times = []
					pattern = r'(\d{2}:\d{2}:\d{2},d{3}$)|(\d{2}:\d{2}:\d{2})'
					with control.openFile(tempFileName) as file:
						text = file.read()
						times = re.findall(pattern, text)
						times = times[len(times) - 4][-1]
						file.close()
					if len(times) > 0:
						h, m, s = str(times).split(':')
						totalSeconds = int(h) * 3600 + int(m) * 60 + int(s)
						return int(media_length) - int(totalSeconds)
					else:
						control.log('[ luc_kodi ] Tiempo de subtítulo no encontrado, devolviendo default.', LOGINFO)

						return 'default'
			except:
				log_utils.error()
				return 'default'

			# Si no hay caché, descargar nuevo
			try:
				if not opensubs.Opensubs().auth():
					control.log('[ luc_kodi ] OpenSubs no autorizado para PlayNext. Devolviendo default.', LOGINFO)

					return 'default'
				if not (season is None or episode is None):
					result = opensubs.Opensubs().getSubs(title, imdb, year, season, episode)
					if not result:
						control.log('[ luc_kodi ] Sin resultados OpenSubs PlayNext: %s S%sE%s' % (title, season, episode), LOGINFO)

						return 'default'
				else:
					result = opensubs.Opensubs().getSubs(title, imdb, year, season, episode)
					if not result: return None

				try:    vidPath = xbmc.Player().getPlayingFile()
				except: vidPath = ''
				pFileName = unquote(os.path.basename(vidPath))
				pFileName = os.path.splitext(pFileName)[0]
				matches = []
				if result:
					for j in result:
						if season:
							if seas_ep_filter(season, episode, j['fileName']):
								seq = SequenceMatcher(None, pFileName.lower(), j['fileName'].lower())
								matches.append({'fileName': j['fileName'], 'fileID': j['fileID'], 'ratio': seq.ratio()})
						else:
							seq = SequenceMatcher(None, pFileName.lower(), j['fileName'].lower())
							matches.append({'fileName': j['fileName'], 'fileID': j['fileID'], 'ratio': seq.ratio()})
				matches.sort(key=lambda i: i['ratio'], reverse=True)
				if not matches: return None

				try:    lang = xbmc.convertLanguage(getSetting('subtitles.lang.1'), xbmc.ISO_639_1)
				except: lang = getSetting('subtitles.lang.1')

				downloadURL, downloadFileName = opensubs.Opensubs().downloadSubs(matches[0]['fileID'], matches[0]['fileName'])

				def find(pattern, path):
					result = []
					for root, dirs, files in os.walk(path):
						for name in files:
							if fnmatch.fnmatch(name, pattern):
								result.append(os.path.join(root, name))
					return result

				def download_opensubs(downloadURL, downloadFileName):
					reqqqq = Request(downloadURL, headers={'User-Agent': 'Magic Browser'})
					response = urlopen(reqqqq).read().decode('utf-8')
					srtFile = os.path.join(download_path, downloadFileName + '.srt')
					with open(srtFile, 'w') as file:
						file.write(response)

				from resources.lib.modules import tools
				tools.delete_all_subs()
				download_opensubs(downloadURL, downloadFileName)

				subtitles = find('*.srt', control.transPath(download_path))
				subtitle_matches = []
				if len(subtitles) > 1:
					if season:
						for count, i in enumerate(subtitles):
							sFileName = os.path.splitext(unquote(os.path.basename(i)))[0]
							if seas_ep_filter(season, episode, sFileName.lower()):
								seq = SequenceMatcher(None, pFileName.lower(), sFileName.lower())
								subtitle_matches.append({'fullPath': subtitles[count], 'matchRatio': seq.ratio()})
					else:
						for count, i in enumerate(subtitles):
							sFileName = os.path.splitext(unquote(os.path.basename(i)))[0]
							seq = SequenceMatcher(None, pFileName.lower(), sFileName.lower())
							subtitle_matches.append({'fullPath': subtitles[count], 'matchRatio': seq.ratio()})
					subtitle_matches.sort(key=lambda i: i['matchRatio'], reverse=True)
					subtitles = subtitle_matches[0]['fullPath']
				else:
					subtitles = subtitles[0]

				xbmc.sleep(1000)
				tempFileName2 = control.joinPath(download_path, 'TemporarySubs2.%s.srt' % lang)
				with open(subtitles, 'r') as f:
					content = f.read()
				with open(tempFileName2, 'a') as f1:
					f1.write(content)
				xbmc.sleep(1000)

				times = []
				pattern = r'(\d{2}:\d{2}:\d{2},d{3}$)|(\d{2}:\d{2}:\d{2})'
				with control.openFile(tempFileName2) as file:
					text = file.read()
					times = re.findall(pattern, text)
					times = times[len(times) - 4][-1]
					file.close()

				if len(times) > 0:
					h, m, s = str(times).split(':')
					totalSeconds = int(h) * 3600 + int(m) * 60 + int(s)
					playnextTime = int(media_length) - int(totalSeconds)
				else:
					playnextTime = 'default'
				control.log('[ luc_kodi ] PlayNext subtítulos: %s seg.' % playnextTime, LOGINFO)

				return playnextTime
			except:
				log_utils.error()
				return 'default'
		except Exception as e:
			control.log('[ luc_kodi ] Subtitles.get() OUTER EXCEPTION: %s' % str(e), LOGINFO)
			return 'default'

##############################

class PlayNext(xbmc.Player):
	def __init__(self):
		super(PlayNext, self).__init__()
		self.enable_playnext = getSetting('enable.playnext') == 'true'
		self.stillwatching_count = int(getSetting('stillwatching.count'))
		self.playing_file = None

	def display_xml(self):
		# Mutex: prevent the popup from being opened twice simultaneously
		if playerWindow.getProperty('luc_kodi.playnext_showing') == 'true':
			return
		try:
			self.playing_file = self.getPlayingFile()
		except:
			log_utils.error("Kodi did not return a playing file, killing playnext xml's")
			return
		has_playlist = (control.playlist.size() > 0 and control.playlist.getposition() != (control.playlist.size() - 1))
		if not has_playlist:
			return
		if self.isStill_watching(): target = self.show_stillwatching_xml
		elif self.enable_playnext: target = self.show_playnext_xml
		else: return
		if self.playing_file != self.getPlayingFile(): return
		if not self.isPlayingVideo(): return
		if control.getCurrentWindowId != 12005: return
		playerWindow.setProperty('luc_kodi.playnext_showing', 'true')
		try:
			target()
		finally:
			playerWindow.clearProperty('luc_kodi.playnext_showing')

	def isStill_watching(self):
		# still_watching = float(control.playlist.getposition() + 1) / self.stillwatching_count # this does not work if you start playback on a divisible position with "stillwatching_count"
		playlistStart_position = int(playerWindow.getProperty('luc_kodi.playlistStart_position') or 0)
		if playlistStart_position: still_watching = float(control.playlist.getposition() - playlistStart_position + 1) / self.stillwatching_count
		else: still_watching = float(control.playlist.getposition() + 1) / self.stillwatching_count
		if still_watching == 0: return False
		return still_watching.is_integer()

	def getNext_meta(self):
		try:
			from urllib.parse import parse_qsl
			current_position = control.playlist.getposition()
			next_url = control.playlist[current_position + 1].getPath()
			# next_url=videodb://tvshows/titles/16/2/571?season=2&tvshowid=16 # library playback returns this
			params = dict(parse_qsl(next_url.replace('?', '')))
			next_meta = jsloads(params.get('meta')) if params.get('meta') else '' # not available for library playback
			return next_meta
		except:
			log_utils.error()
			return ''

	def show_playnext_xml(self):
		try:
			next_meta = self.getNext_meta()
			if not next_meta: raise Exception()
			from resources.lib.windows.playnext import PlayNextXML
			window = PlayNextXML('playnext.xml', control.addonPath(control.addonId()), meta=next_meta)
			window.run()
			del window
			self.play_next_triggered = True
		except:
			log_utils.error()
			self.play_next_triggered = True

	def show_stillwatching_xml(self):
		try:
			next_meta = self.getNext_meta()
			if not next_meta: raise Exception()
			from resources.lib.windows.playnext_stillwatching import StillWatchingXML
			window = StillWatchingXML('playnext_stillwatching.xml', control.addonPath(control.addonId()), meta=next_meta)
			window.run()
			del window
			self.play_next_triggered = True
		except:
			log_utils.error()
			self.play_next_triggered = True

	def prescrapeNext(self):
		try:
			if control.playlist.size() > 0 and control.playlist.getposition() != (control.playlist.size() - 1):
				from resources.lib.modules import sources
				from resources.lib.database import providerscache
				next_meta=self.getNext_meta()
				if not next_meta: raise Exception()
				title = next_meta.get('title')
				year = next_meta.get('year')
				imdb = next_meta.get('imdb')
				tmdb = next_meta.get('tmdb')
				tvdb = next_meta.get('tvdb')
				season = next_meta.get('season')
				episode = next_meta.get('episode')
				tvshowtitle = next_meta.get('tvshowtitle')
				premiered = next_meta.get('premiered')
				next_sources = providerscache.get(sources.Sources().getSources, 48, title, year, imdb, tmdb, tvdb, str(season), str(episode), tvshowtitle, premiered, next_meta, True)
				if not self.isPlayingVideo():
					return playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
				sources.Sources().preResolve(next_sources, next_meta)
			else:
				playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
		except:
			log_utils.error()
			playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')



class Bookmarks:
	def get(self, name, imdb=None, tmdb=None, tvdb=None, season=None, episode=None, year='0', runtime=None, ck=False):
		offset = '0'
		scrobbble = 'Local Bookmark'
		if getSetting('bookmarks') != 'true': return offset
		if getSetting('trakt.scrobble') == 'true' and getSetting('resume.source') == '1':
			scrobbble = 'Trakt Scrobble'
			try:
				if not runtime or runtime == 'None': return offset # TMDB sometimes return None as string. duration pulled from kodi library if missing from meta
				progress = float(fetch_bookmarks(imdb, tmdb, tvdb, season, episode))
				offset = (progress / 100) * runtime # runtime vs. media_length can differ resulting in 10-30sec difference using Trakt scrobble, meta providers report runtime in full minutes
				seekable = (2 <= progress <= 85)
				if not seekable: return '0'
			except:
				log_utils.error()
				return '0'
		else:
			try:
				dbcon = database.connect(control.bookmarksFile)
				dbcur = dbcon.cursor()
				dbcur.execute('''CREATE TABLE IF NOT EXISTS bookmark (idFile TEXT, timeInSeconds TEXT, Name TEXT, year TEXT, UNIQUE(idFile));''')
				if not year or year == 'None': return offset
				years = [str(year), str(int(year)+1), str(int(year)-1)]
				match = dbcur.execute('''SELECT * FROM bookmark WHERE Name="%s" AND year IN (%s)''' % (name, ','.join(i for i in years))).fetchone() # helps fix random cases where trakt and imdb, or tvdb, differ by a year for eps
			except:
				log_utils.error()
				return offset
			finally:
				try:
					dbcur.close()
				except Exception:
					pass
				try:
					dbcon.close()
				except Exception:
					pass
			if not match: return offset
			offset = str(match[1])
		if ck: return offset
		minutes, seconds = divmod(float(offset), 60)
		hours, minutes = divmod(minutes, 60)
		label = '%02d:%02d:%02d' % (hours, minutes, seconds)
		label = getLS(32502) % label
		if getSetting('bookmarks.auto') == 'false':
			select = control.yesnocustomDialog(label, scrobbble, '', str(name), 'Cancel Playback', getLS(32503), getLS(32501))
			if select == 1: offset = '0'
			elif select == -1 or select == 2: offset = '-1'
		return offset

	def reset(self, current_time, media_length, name, year='0'):
		try:
			clear_local_bookmarks() # clear all luc_kodi bookmarks from kodi database
			if getSetting('bookmarks') != 'true' or media_length == 0 or current_time == 0: return
			timeInSeconds = str(current_time)
			seekable = (int(current_time) > 180 and (current_time / media_length) < .85)
			idFile = md5()
			try: [idFile.update(str(i)) for i in name]
			except: [idFile.update(str(i).encode('utf-8')) for i in name]
			try: [idFile.update(str(i)) for i in year]
			except: [idFile.update(str(i).encode('utf-8')) for i in year]
			idFile = str(idFile.hexdigest())
			control.makeFile(control.dataPath)
			dbcon = database.connect(control.bookmarksFile)
			dbcur = dbcon.cursor()
			dbcur.execute('''CREATE TABLE IF NOT EXISTS bookmark (idFile TEXT, timeInSeconds TEXT, Name TEXT, year TEXT, UNIQUE(idFile));''')
			years = [str(year), str(int(year) + 1), str(int(year) - 1)]
			dbcur.execute('''DELETE FROM bookmark WHERE Name="%s" AND year IN (%s)''' % (name, ','.join(i for i in years))) #helps fix random cases where trakt and imdb, or tvdb, differ by a year for eps
			if seekable:
				dbcur.execute('''INSERT INTO bookmark Values (?, ?, ?, ?)''', (idFile, timeInSeconds, name, year))
				minutes, seconds = divmod(float(timeInSeconds), 60)
				hours, minutes = divmod(minutes, 60)
				label = ('%02d:%02d:%02d' % (hours, minutes, seconds))
				message = getLS(32660)
				control.notification(title=name, message=message + '(' + label + ')')
			dbcur.connection.commit()
			try: dbcur.close ; dbcon.close()
			except: pass
		except:
			log_utils.error()

	def set_scrobble(self, current_time, media_length, media_type, imdb='', tmdb='', tvdb='', season='', episode=''):
		try:
			if media_length == 0: return
			percent = float((current_time / media_length)) * 100
			seekable = (int(current_time) > 180 and (percent < 85))
			if seekable: trakt.scrobbleMovie(imdb, tmdb, percent) if media_type == 'movie' else trakt.scrobbleEpisode(imdb, tmdb, tvdb, season, episode, percent)
			if percent >= 85: trakt.scrobbleReset(imdb, tmdb, tvdb, season, episode, refresh=False)
		except:
			log_utils.error()