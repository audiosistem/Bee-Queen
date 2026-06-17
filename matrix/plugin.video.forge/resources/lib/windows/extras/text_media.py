# -*- coding: utf-8 -*-
from windows.base_window import BaseDialog


class ShowTextMedia(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.text = kwargs.get("text")
		self.position = kwargs.get("current_index", None)
		self.text_is_list = isinstance(self.text, list)
		self.len_text = len(self.text) if self.text_is_list else None
		self.window_id = 2099
		self.setProperty("poster", kwargs.get("poster"))

	def run(self):
		self.doModal()
		return self.position

	def onInit(self):
		self.update_text()
		self.setFocusId(self.window_id)

	def onAction(self, action):
		if action in self.closing_actions:
			return self.close()
		if self.text_is_list:
			if action == self.left_action:
				return self.update_text("previous")
			if action == self.right_action:
				return self.update_text("next")

	def update_text(self, direction=None):
		if direction == "previous":
			self.position = self.position - 1 if self.position > 0 else self.len_text - 1
		elif direction == "next":
			self.position = 0 if self.position == self.len_text - 1 else self.position + 1
		self.set_text(2001, self.text[self.position] if self.text_is_list else self.text)
		if self.text_is_list:
			if self.position == 0:
				self.setProperty("previous_display", "false")
			else:
				self.setProperty("previous_display", "true")
			if self.position == self.len_text - 1:
				self.setProperty("next_display", "false")
			else:
				self.setProperty("next_display", "true")
		else:
			self.setProperty("previous_display", "false"), self.setProperty("next_display", "false")
