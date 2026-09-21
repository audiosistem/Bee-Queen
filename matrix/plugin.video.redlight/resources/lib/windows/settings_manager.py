# -*- coding: utf-8 -*-
from time import time
from urllib.parse import parse_qsl
from windows.base_window import BaseDialog
from caches.settings_cache import (
	set_boolean, set_from_list, set_numeric, set_path, set_string, restore_setting_default
)
# from modules.kodi_utils import logger

class SettingsManager(BaseDialog):
	settings_list_id = 2100
	cache_modes = {
		'set_boolean': set_boolean,
		'set_from_list': set_from_list,
		'set_numeric': set_numeric,
		'set_path': set_path,
		'set_string': set_string,
		'restore_setting_default': restore_setting_default,
	}
	row_param_keys = (
		'setting_id', 'type', 'media_type', 'list_type', 'setting_slot', 'return_to',
		'direction', 'filter_setting_id', 'multi_choice', 'min_value', 'icon', 'include_none'
	)

	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.control_id = None
		self._last_apply = 0

	def run(self):
		self.doModal()
		self.clearProperties()

	def onClick(self, controlID):
		if controlID == self.settings_list_id:
			self._apply_focused_setting()

	def onAction(self, action):
		if action in self.closing_actions:
			return self.close()
		if action in self.selection_actions and self.getFocusId() == self.settings_list_id:
			self._apply_focused_setting()

	def _list_property(self, item, key):
		value = ''
		if item:
			try: value = item.getProperty(key) or ''
			except: value = ''
		if not value:
			value = self.get_infolabel('Container(%s).ListItem.Property(%s)' % (self.settings_list_id, key)) or ''
		return value

	def _slot_from_setting_id(self, setting_id):
		if not setting_id: return ''
		from re import search
		match = search(r'(?:^|[._])slot(\d+)(?:[._]|$)', setting_id)
		if match: return match.group(1)
		match = search(r'(?:^|[._])nzb(\d+)(?:[._]|$)', setting_id)
		if match: return match.group(1)
		return ''

	def _parse_slot_number(self, raw):
		if raw in (None, ''): return ''
		try: number = int(str(raw).strip())
		except: return ''
		if number < 1: return ''
		return str(number)

	def _resolve_slot(self, params, item):
		from re import search, I
		# Never read ListItem.Property(slot): Kodi treats that name as a built-in and it is often "1".
		for raw in (params.get('setting_slot'), self._slot_from_setting_id(params.get('setting_id', '')), params.get('slot')):
			parsed = self._parse_slot_number(raw)
			if parsed: return parsed
		label = self._list_property(item, 'setting_label')
		match = search(r'(?:slot|indexer)\s*(\d+)', label or '', I)
		if match: return self._parse_slot_number(match.group(1))
		return ''

	def _row_params(self, item):
		params = {}
		query = self._list_property(item, 'setting_query')
		if query:
			params.update(dict(parse_qsl(query, keep_blank_values=True)))
		for key in self.row_param_keys:
			value = self._list_property(item, key)
			if value: params[key] = value
		slot = self._resolve_slot(params, item)
		if slot: params['slot'] = slot
		return params

	def _apply_focused_setting(self):
		now = time()
		if now - self._last_apply < 0.35: return
		try:
			item = self.get_listitem(self.settings_list_id)
			params = self._row_params(item)
			mode = self._list_property(item, 'setting_mode')
			setting_type = self._list_property(item, 'setting_type')
			if setting_type == 'boolean':
				mode = 'set_boolean'
			if not mode: return
			self._last_apply = now
			new_value = self._dispatch(mode, params)
			if mode == 'set_boolean' and new_value:
				self._refresh_boolean_row(item, params.get('setting_id'), new_value)
		except:
			return

	def _dispatch(self, mode, params):
		if mode.startswith('settings_manager.'):
			mode = mode.split('.', 1)[1]
		handler = self.cache_modes.get(mode)
		if handler:
			return handler(params)
		if mode == 'open_external_scraper_settings':
			from modules.kodi_utils import external_scraper_settings
			return external_scraper_settings(params)
		if mode in ('opensubs_check_account', 'opensubs_test_login'):
			from apis.opensubs_api import check_account
			return check_account()
		if mode == 'nzb.test_connection':
			from indexers.nzb import test_connection
			return test_connection(params)
		if mode == 'wetrakr.wetrakr_about':
			from apis.wetrakr_api import wetrakr_about
			return wetrakr_about()
		if mode.endswith('_choice') or mode in ('external_scraper_clear_slot', 'external_scraper_move_slot'):
			from indexers import dialogs
			return getattr(dialogs, mode)(params)
		return None

	def _refresh_boolean_row(self, item, setting_id, new_value):
		try:
			if item: item.setProperty('setting_value', new_value)
		except:
			pass
		try:
			pos = self.get_position(self.settings_list_id)
			if pos < 0: return
			neighbor = pos - 1 if pos > 0 else pos + 1
			self.select_item(self.settings_list_id, neighbor)
			self.select_item(self.settings_list_id, pos)
		except:
			pass

class SettingsManagerFolders(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)

	def run(self):
		self.doModal()
		self.clearProperties()
