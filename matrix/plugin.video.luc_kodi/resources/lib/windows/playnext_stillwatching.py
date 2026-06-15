# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from datetime import datetime, timedelta
import xbmc
from resources.lib.modules.control import getSourceHighlightColor, setting as getSetting, playerWindow
from resources.lib.modules import tools
from resources.lib.windows.base import BaseDialog

monitor = xbmc.Monitor()


class StillWatchingXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.window_id = 3011
		self.meta = kwargs.get('meta')
		self.playing_file = self.getPlayingFile()
		self.duration = self.getTotalTime() - self.getTime()
		try: self.default_action = int(getSetting('playnext.default.action') or '0')
		except (ValueError, TypeError): self.default_action = 0
		self.closed = False

	def onInit(self):
		self.set_properties()
		self.background_tasks()

	def run(self):
		self.doModal()
		self.clearProperties()

	def doClose(self):
		self.closed = True
		self.close()

	def onAction(self, action):
		if action in self.closing_actions or action in self.selection_actions:
			self.doClose()

	def onClick(self, control_id):
		if control_id == 3011: # Play Now
			xbmc.executebuiltin('PlayerControl(BigSkipForward)')
			self.doClose()
		if control_id == 3012: # Stop playback
			xbmc.executebuiltin('PlayerControl(Playlist.Clear)')
			xbmc.executebuiltin('PlayerControl(Stop)')
			playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
			self.doClose()
		if control_id == 3013: # Cancel/Close xml dialog
			self.doClose()

	def getTotalTime(self):
		if self.isPlaying():
			return xbmc.Player().getTotalTime()
		else:
			return 0

	def getTime(self):
		if self.isPlaying():
			return xbmc.Player().getTime()
		else:
			return 0

	def isPlaying(self):
		return xbmc.Player().isPlaying()

	def isPlayingVideo(self):
		return xbmc.Player().isPlayingVideo()

	def getPlayingFile(self):
		try:
			return xbmc.Player().getPlayingFile()
		except:
			return ''

	def calculate_percent(self):
		try:
			return ((int(self.getTotalTime()) - int(self.getTime())) / float(self.duration)) * 100
		except:
			return 100

	def background_tasks(self):
		try:
			try: progress_bar = self.getControlProgress(3014)
			except: progress_bar = None

			while (
				int(self.getTotalTime()) - int(self.getTime()) > 2
				and not self.closed
				and self.playing_file == self.getPlayingFile()
				and not monitor.abortRequested()
			):
				xbmc.sleep(500)
				if progress_bar is not None:
					try: progress_bar.setPercent(self.calculate_percent())
					except: pass

			if self.closed: return
			current_file = self.getPlayingFile()
			file_changed = bool(current_file) and (current_file != self.playing_file)
			if not file_changed:
				if self.default_action == 0:
					xbmc.executebuiltin('PlayerControl(BigSkipForward)')
				elif self.default_action == 1:
					xbmc.executebuiltin('PlayerControl(Playlist.Clear)')
					xbmc.executebuiltin('PlayerControl(Stop)')
				elif self.default_action == 2:
					try: xbmc.Player().pause()
					except: pass
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		self.doClose()

	def set_properties(self):
		if self.meta is None: return
		try:
			self.setProperty('luc_kodi.highlight.color', getSourceHighlightColor())
			self.setProperty('luc_kodi.tvshowtitle', self.meta.get('tvshowtitle'))
			self.setProperty('luc_kodi.title', self.meta.get('title'))
			self.setProperty('luc_kodi.year', str(self.meta.get('year', '')))
			new_date = tools.convert_time(stringTime=str(self.meta.get('premiered', '')), formatInput='%Y-%m-%d', formatOutput='%m-%d-%Y', zoneFrom='utc', zoneTo='utc')
			self.setProperty('luc_kodi.premiered', new_date)
			self.setProperty('luc_kodi.season', str(self.meta.get('season', '')))
			self.setProperty('luc_kodi.episode', str(self.meta.get('episode', '')))
			self.setProperty('luc_kodi.rating', str(self.meta.get('rating', '')))
			self.setProperty('luc_kodi.landscape', self.meta.get('landscape', ''))
			self.setProperty('luc_kodi.fanart', self.meta.get('fanart', ''))
			self.setProperty('luc_kodi.thumb', self.meta.get('thumb', ''))
			next_duration = int(self.meta.get('duration')) if self.meta.get('duration') else ''
			self.setProperty('luc_kodi.duration', str(int(next_duration)))
			endtime = (datetime.now() + timedelta(seconds=next_duration)).strftime('%I:%M %p').lstrip('0') if next_duration else ''
			self.setProperty('luc_kodi.endtime', endtime)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
