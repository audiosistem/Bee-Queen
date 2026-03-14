# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	DisplayWelcomeXML — unified notification window used by ALL plugin notifications.
	Renders bottom-right with:
		- Line 1 (title)   in luc_kodi green  #ff00fa9a
		- Line 2 (message) in gold            #fffdb515
		- Plugin icon (or custom debrid icon)
		- Smooth slide-in / fade-out animation
	Auto-closes after <duration> seconds; user can dismiss with Back/Enter.
"""

import xbmc
import xbmcgui
from resources.lib.modules import log_utils

monitor = xbmc.Monitor()
_HOME = xbmcgui.Window(10000)


class DisplayWelcomeXML(xbmcgui.WindowXMLDialog):

	def __init__(self, *args, **kwargs):
		xbmcgui.WindowXMLDialog.__init__(self, *args)
		self.line1    = kwargs.get('line1', 'luc_kodi')
		self.line2    = kwargs.get('line2', '')
		self.icon     = kwargs.get('icon', '')
		self.duration = kwargs.get('duration', 4)

	def onInit(self):
		try:
			_HOME.setProperty('luc_kodi.notif.icon',  self.icon)
			_HOME.setProperty('luc_kodi.notif.line1', self.line1)
			_HOME.setProperty('luc_kodi.notif.line2', self.line2)
		except Exception:
			log_utils.error()

	def _clear(self):
		try:
			for key in ('luc_kodi.notif.icon', 'luc_kodi.notif.line1', 'luc_kodi.notif.line2'):
				_HOME.clearProperty(key)
		except Exception:
			log_utils.error()

	def show_and_close(self, duration=None):
		secs = duration or self.duration
		try:
			self.show()
			elapsed = 0
			while elapsed < secs and not monitor.abortRequested():
				monitor.waitForAbort(1)
				elapsed += 1
			self.close()
		except Exception:
			log_utils.error()
		finally:
			self._clear()

	def onAction(self, action):
		if action.getId() in (9, 10, 13, 92):
			self.close()
