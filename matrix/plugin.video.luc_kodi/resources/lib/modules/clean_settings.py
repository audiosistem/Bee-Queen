# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

import xml.etree.ElementTree as ET
from resources.lib.modules import control


def clean_settings(silent=False):
	"""Reescribe el settings.xml del usuario dejando SOLO los ids declarados.

	v1.0.65: admite silent=True para la pasada automatica por cambio de version,
	devuelve la lista de ids retirados y los deja en el log.
	"""
	def _make_content(dict_object):
		content = '<settings version="2">'
		for item in dict_object:
			if item['id'] in active_settings:
				if 'default' in item and 'value' in item: content += '\n    <setting id="%s" default="%s">%s</setting>' % (item['id'], item['default'], item['value'])
				elif 'default' in item: content += '\n    <setting id="%s" default="%s"></setting>' % (item['id'], item['default'])
				elif 'value' in item: content += '\n    <setting id="%s">%s</setting>' % (item['id'], item['value'])
				else: content += '\n    <setting id="%s"></setting>' % item['id']
			else: removed_settings.append(item)
		content += '\n</settings>'
		return content

	for addon_id in ['plugin.video.luc_kodi']:
		try:
			removed_settings = []
			active_settings = []
			current_user_settings = []
			addon = control.addon(id=addon_id)
			addon_name = addon.getAddonInfo('name')
			addon_dir = control.transPath(addon.getAddonInfo('path'))
			profile_dir = control.transPath(addon.getAddonInfo('profile'))
			active_settings_xml = control.joinPath(addon_dir, 'resources', 'settings.xml')
			root = ET.parse(active_settings_xml).getroot()
			for item in root.findall('./category/setting'):
				setting_id = item.get('id')
				if setting_id:
					active_settings.append(setting_id)
			if len(active_settings) < 50:
				# 427 declarados en la 1.0.65. Menos de 50 solo puede significar
				# que el settings.xml del addon no se leyo bien, y seguir aqui
				# borraria ajustes VIVOS del usuario. Se aborta.
				from resources.lib.modules import log_utils as _lu
				control.log('[ luc_kodi ] clean_settings: solo %s ids declarados leidos, se aborta por seguridad'
				            % len(active_settings), _lu.LOGINFO)
				return []
			settings_xml = control.joinPath(profile_dir, 'settings.xml')
			root = ET.parse(settings_xml).getroot()
			for item in root:
				dict_item = {}
				setting_id = item.get('id')
				setting_default = item.get('default')
				setting_value = item.text
				dict_item['id'] = setting_id
				if setting_value:
					dict_item['value'] = setting_value
				if setting_default:
					dict_item['default'] = setting_default
				current_user_settings.append(dict_item)
			new_content = _make_content(current_user_settings)
			nfo_file = control.openFile(settings_xml, 'w')
			nfo_file.write(new_content)
			nfo_file.close()
			control.sleep(200)
			from resources.lib.modules import log_utils as _lu
			for _r in removed_settings:
				control.log('[ luc_kodi ] clean_settings: retirado %s' % _r.get('id'), _lu.LOGINFO)
			if not silent:
				control.notification(title=addon_name, message=control.lang(32084).format(str(len(removed_settings))))
			return [_r.get('id') for _r in removed_settings]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			if not silent:
				control.notification(title=addon_name, message=32115)
			return []
