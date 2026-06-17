# -*- coding: utf-8 -*-
from windows.base_window import BaseDialog

# from modules.kodi_utils import logger


class SkipSegment(BaseDialog):
	"""Netflix-style Skip button overlay shown during an intro/recap/outro.

	A focusable modal (``doModal``) with a single Skip button, launched in a
	Thread by ``ForgePlayer`` — the same proven pattern as ``NextEpisode``. It
	auto-dismisses after ``duration`` seconds if the user doesn't act. ``run``
	returns ``"skip"`` (button pressed) or ``"dismiss"`` (timed out / closed); the
	player does the actual ``seekTime``/next-episode work so seeks stay off this
	short-lived dialog thread where it matters.

	A modeless overlay that coexists with the video OSD is a Phase 4 spike
	(Risk #1) — Phase 1 ships the proven modal.
	"""

	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.label = kwargs.get("label", "Skip")
		self.duration = int(kwargs.get("duration", 8))
		self.selected = "dismiss"
		self.closed = False
		self.set_properties()

	def onInit(self):
		self.setFocusId(10)
		self.monitor()

	def run(self):
		self.doModal()
		self.clearProperties()
		self.clear_modals()
		return self.selected

	def onAction(self, action):
		if action in self.closing_actions:
			self.closed = True
			self.close()

	def onClick(self, controlID):
		if controlID == 10:
			self.selected = "skip"
		self.closed = True
		self.close()

	def set_properties(self):
		self.setProperty("skip.label", self.label)

	def monitor(self):
		remaining = self.duration
		while self.player.isPlaying() and remaining > 0:
			if self.closed:
				break
			self.sleep(1000)
			remaining -= 1
		self.close()
