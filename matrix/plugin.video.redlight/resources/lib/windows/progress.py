# -*- coding: utf-8 -*-
from windows.base_window import BaseDialog
from modules.kodi_utils import addon_icon, kodi_monitor
# from modules.kodi_utils import logger

class Progress(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.is_canceled = False
		self.heading = kwargs.get('heading', '')
		self.icon = kwargs.get('icon', addon_icon())

	def run(self):
		self.doModal()
		# Window is gone (Back, Android pause/close, or progress.close()). Stop any auth poll.
		self.is_canceled = True
		self.clearProperties()

	def close(self):
		self.is_canceled = True
		try: BaseDialog.close(self)
		except: pass

	def onInit(self):
		self.set_controls()

	def iscanceled(self):
		if self.is_canceled: return True
		try:
			if kodi_monitor().abortRequested():
				self.is_canceled = True
				return True
		except: pass
		return False

	def onAction(self, action):
		if action in self.closing_actions:
			self.is_canceled = True
			self.close()

	def set_controls(self):
		if self.icon:
			self.set_image(200, self.icon)
		self.set_label(2000, self.heading)
		self.setProperty('redlight.progress_ready', 'true')

	def update(self, content='', percent=0, icon=None):
		if icon:
			self.icon = icon
		try:
			self.set_text(2001, content)
			self.set_percent(5000, percent)
		except: pass
		if self.icon:
			try: self.set_image(200, self.icon)
			except: pass
