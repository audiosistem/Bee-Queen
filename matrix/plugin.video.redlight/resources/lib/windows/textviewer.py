# -*- coding: utf-8 -*-
from windows.base_window import BaseDialog
# from modules.kodi_utils import logger

class TextViewer(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.heading = kwargs.get('heading')
		self.text = kwargs.get('text')
		self.font_size = kwargs.get('font_size')
		self.focus_id = 4000
		self.set_properties()
		self.make_menu()

	def onInit(self):
		self.add_items(2000, self.item_list)
		self.setFocusId(self.focus_id)

	def run(self):
		self.doModal()
		self.clearProperties()

	def onAction(self, action):
		if action in self.closing_actions:
			self.close()

	def set_properties(self):
		self.setProperty('heading', self.heading)
		self.setProperty('font_size', self.font_size)

	def make_menu(self):
		def builder():
			for item in self.text:
				listitem = self.make_listitem()
				listitem.setProperty('line1', item)
				yield listitem
		self.item_list = list(builder())
