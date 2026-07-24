# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — windows/skip_intro.py

	Píldora "Skip Intro" flotante sobre el vídeo (estilo Netflix).
	Modal (doModal) para capturar OK del mando, pero con hilo daemon que la
	cierra sola cuando el playhead pasa el final del segmento, se para la
	reproducción o cambia el archivo — mismo patrón bg-close que usa el
	overlay del addon oficial de TheIntroDB (Kodi no tolera tocar la GUI
	desde hilos, pero close() vía self.close() en este contexto es seguro
	porque WindowXMLDialog lo despacha al hilo principal).

	Control 4501 = botón. XML en 1080i y 2160p (2160p = 1080i ×2, ids iguales).
"""

import threading
import xbmc
from resources.lib.windows.base import BaseDialog

BUTTON_ID = 4501
# Tope de visibilidad: aunque el segmento sea larguísimo, no dejar la píldora
# clavada en pantalla más de este tiempo.
MAX_DISPLAY_SECONDS = 45


class SkipIntroXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.label = kwargs.get('label') or 'Skip Intro'
		self.seg_end = kwargs.get('seg_end')
		self.running_path = kwargs.get('running_path') or ''
		self.player = xbmc.Player()
		self.monitor = xbmc.Monitor()
		self.skip_pressed = False
		self.closed = False

	def onInit(self):
		try: self.getControl(BUTTON_ID).setLabel(self.label)
		except: pass
		try: self.setFocusId(BUTTON_ID)
		except: pass
		worker = threading.Thread(target=self._auto_close)
		worker.daemon = True
		worker.start()

	def run(self):
		self.doModal()
		return self.skip_pressed

	def doClose(self):
		self.closed = True
		try: self.close()
		except: pass

	def onClick(self, control_id):
		if control_id == BUTTON_ID:
			self.skip_pressed = True
			self.doClose()

	def onAction(self, action):
		if action in self.selection_actions:
			try:
				if self.getFocusId() == BUTTON_ID:
					self.skip_pressed = True
			except: pass
			self.doClose()
			return
		if action in self.closing_actions:
			self.doClose()

	def _still_valid(self):
		try:
			if not self.player.isPlayingVideo(): return False
			if self.running_path and self.player.getPlayingFile() != self.running_path:
				return False
			if self.seg_end is not None and self.player.getTime() >= self.seg_end - 0.5:
				return False
			return True
		except Exception:
			return False

	def _auto_close(self):
		remaining = MAX_DISPLAY_SECONDS
		while not self.closed and remaining > 0:
			if self.monitor.waitForAbort(0.5): break
			remaining -= 0.5
			if not self._still_valid(): break
		if not self.closed:
			self.doClose()
