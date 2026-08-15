# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	DisplayWelcomeXML — unified notification window used by ALL plugin notifications.
	A module-level lock serializes concurrent notifications so only one
	WindowXMLDialog is ever showing at a time — avoids Kodi window init conflicts.
"""

import threading
import xbmc
import xbmcgui
from resources.lib.modules import log_utils

monitor  = xbmc.Monitor()
_HOME    = xbmcgui.Window(10000)

# Serialization lock — one notification visible at a time
_show_lock = threading.Lock()


class DisplayWelcomeXML(xbmcgui.WindowXMLDialog):

	def __init__(self, *args, **kwargs):
		xbmcgui.WindowXMLDialog.__init__(self, *args)
		self.line1    = kwargs.get('line1', 'luc_kodi')
		self.line2    = kwargs.get('line2', '')
		self.icon     = kwargs.get('icon',  '')
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
			_HOME.clearProperty('luc_kodi.notif.icon')
			_HOME.clearProperty('luc_kodi.notif.line1')
			_HOME.clearProperty('luc_kodi.notif.line2')
		except Exception:
			log_utils.error()

	def onAction(self, action):
		if action.getId() in (9, 10, 13, 92):
			self._user_closed = True
			self.close()

	def show_and_close(self, duration=None):
		"""Acquire the module lock so notifications never overlap."""
		secs = duration or self.duration
		self._user_closed = False
		with _show_lock:
			try:
				self.show()
				elapsed = 0
				while elapsed < secs and not monitor.abortRequested():
					# Si el usuario cierra el dialogo (Back/OK), salir YA: seguir
					# esperando bloqueaba al CPythonInvoker ("waiting on thread")
					# el resto de la duracion y provocaba un segundo close() sobre
					# un dialogo ya cerrado, ampliando la ventana de carrera con
					# la reinicializacion del interprete (reuselanguageinvoker).
					if self._user_closed: break
					monitor.waitForAbort(0.25)
					elapsed += 0.25
				if not self._user_closed: self.close()
			except Exception:
				log_utils.error()
			finally:
				self._clear()
