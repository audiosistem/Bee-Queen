# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from xbmc import executebuiltin
from xbmcgui import WindowXMLDialog, ListItem, ControlProgress


class BaseDialog(WindowXMLDialog):
	def __init__(self, *args):
		WindowXMLDialog.__init__(self, args)
		# Match the official 1.0.21: ACTION_STOP (13) is included. During
		# playback the video player has focus, so the Bingie window underneath
		# never receives STOP; on stop, the player closes and we return to the
		# still-open window. The reentrancy guard in the section launcher
		# prevents any accidental relaunch from the refreshed parent directory.
		self.closing_actions = [9, 10, 13, 92]
		self.selection_actions = [7, 100]
		self.context_actions = [101, 117]
		self.info_actions = [11,]
		# self.updn_actions = [5, 6]

	def make_listitem(self):
		return ListItem()

	def execute_code(self, command):
		return executebuiltin(command)

	def get_position(self, window_id):
		return self.getControl(window_id).getSelectedPosition()

	def getControlProgress(self, control_id):
		control = self.getControl(control_id)
		if not isinstance(control, ControlProgress):
			raise AttributeError("Control with Id {} should be of type ControlProgress".format(control_id))
		return control
