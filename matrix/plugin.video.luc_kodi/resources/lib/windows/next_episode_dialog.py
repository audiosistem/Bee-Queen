# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

import xbmc
from resources.lib.modules.control import addonFanart
from resources.lib.windows.base import BaseDialog

monitor = xbmc.Monitor()

RESULT_CANCEL       = 0
RESULT_AUTOPLAY     = 1
RESULT_CHOOSE_SRC   = 2
_AUTOCLOSE_SECS     = 30

_CTRL_AUTOPLAY      = 3021
_CTRL_NOT_NOW       = 3022
_CTRL_CHOOSE_SRC    = 3023


class NextEpisodeDialog(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.show_title = kwargs.get('show_title', '')
		self.ep_label   = kwargs.get('ep_label', '')
		self.fanart     = kwargs.get('fanart', '') or addonFanart()
		self.clearlogo  = kwargs.get('clearlogo', '')
		self.thumb      = kwargs.get('thumb', '')
		self.result     = RESULT_CANCEL
		self.closed     = False

	def onInit(self):
		self.setProperty('luc_kodi.show_title', self.show_title)
		self.setProperty('luc_kodi.ep_label',   self.ep_label)
		self.setProperty('luc_kodi.fanart',     self.fanart)
		self.setProperty('luc_kodi.clearlogo',  self.clearlogo)
		self.setProperty('luc_kodi.thumb',      self.thumb)
		self._run_countdown()

	def run(self):
		self.doModal()
		self.clearProperties()
		return self.result

	def _doClose(self, result=RESULT_CANCEL):
		if self.closed:
			return
		self.result = result
		self.closed = True
		self.close()

	def onAction(self, action):
		if action in self.closing_actions:
			self._doClose(RESULT_CANCEL)

	def onClick(self, control_id):
		if   control_id == _CTRL_AUTOPLAY:    self._doClose(RESULT_AUTOPLAY)
		elif control_id == _CTRL_NOT_NOW:     self._doClose(RESULT_CANCEL)
		elif control_id == _CTRL_CHOOSE_SRC:  self._doClose(RESULT_CHOOSE_SRC)

	def _run_countdown(self):
		countdown = _AUTOCLOSE_SECS
		while countdown >= 0 and not self.closed and not monitor.abortRequested():
			self.setProperty('luc_kodi.next_ep_countdown', str(countdown))
			xbmc.sleep(1000)
			countdown -= 1
		if not self.closed:
			self._doClose(RESULT_CANCEL)
