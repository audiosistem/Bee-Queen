"""
	Fenomscrapers Module
"""

import os.path
import xml.etree.ElementTree as ET
from json import dumps as jsdumps, loads as jsloads
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

condVisibility = xbmc.getCondVisibility
execute = xbmc.executebuiltin
jsonrpc = xbmc.executeJSONRPC
monitor_class = xbmc.Monitor

existsPath = xbmcvfs.exists
openFile = xbmcvfs.File
makeFile = xbmcvfs.mkdir
makeDirs = xbmcvfs.mkdirs
transPath = xbmcvfs.translatePath
joinPath = os.path.join

dialog = xbmcgui.Dialog

def homeWindow():
	return xbmcgui.Window(10000)

def addon(addon_id='plugin.video.pov'):
	return xbmcaddon.Addon(addon_id)

SETTINGS_PATH = transPath(joinPath(addon().getAddonInfo('path'), 'resources', 'settings.xml'))
dataPath = transPath(addon().getAddonInfo('profile'))
cacheFile = joinPath(dataPath, 'fenomcache.db')
undesirablescacheFile = joinPath(dataPath, 'fenomcache.db')
settingsFile = joinPath(dataPath, 'settings.xml')

def getProviderDefaults():
	files = xbmcvfs.listdir('special://home/addons/plugin.video.pov/lib/pov/')[1]
	files = [i.split('.')[0] for i in files if not i.startswith('__') and i.endswith('.py')]
	provider_defaults = {}
	try:
		with openFile(SETTINGS_PATH) as xml_file: root = ET.fromstring(xml_file.read())
		for item in root.findall(r'./category/setting'):
			setting_id, setting_default = item.get('id', ''), item.get('default', '')
			if not setting_id.startswith('provider.') or setting_default is None: continue
			if setting_id.split('provider.')[-1] not in files: continue
			provider_defaults[setting_id] = setting_default or 'false'
	except: pass
	return provider_defaults

class SettingsManager:
	def __init__(self):
		self._cache = {}
		self._last_raw_string = None

	def _sync(self):
		current_raw = homeWindow().getProperty('pov_settings')
		if current_raw == self._last_raw_string: return
		try: self._cache = jsloads(current_raw)
		except Exception: self._cache = make_settings_dict()
		self._last_raw_string = current_raw

	def get(self, key, fallback=None):
		self._sync()
		value = self._cache.get(key, '')
		if value == '' and fallback is not None: return fallback
		return value

manager = SettingsManager()

def setting(id, fallback=None):
	try: value = manager.get(id, fallback)
	except: value = addon().getSetting(id)
	return value

def setSetting(id, value):
	return addon().setSetting(id, value)

def make_settings_dict(): # service runs upon a setting change
	try:
		with openFile(settingsFile) as xml_file: root = ET.fromstring(xml_file.read())
		settings_dict = {}
		for item in root:
			dict_item = {}
			setting_id = item.get('id')
			setting_value = item.text
			if setting_value is None: setting_value = ''
			dict_item = {setting_id: setting_value}
			settings_dict.update(dict_item)
		homeWindow().setProperty('pov_settings', jsdumps(settings_dict))
		return settings_dict
	except:
		return None

def sleep(time): # Modified `sleep` command that honors a user exit request
	monitor = monitor_class()
	while time > 0 and not monitor.abortRequested():
		xbmc.sleep(min(100, time))
		time = time - 100

def lang(language_id):
	return addon().getLocalizedString(language_id)

def addonInfo(info):
	return addon().getAddonInfo(info)

def addonId():
	return addonInfo('id')

def addonName():
	return addonInfo('name')

def addonVersion():
	return addonInfo('version')

def addonIcon():
	return addonInfo('icon')

def addonPath():
	return transPath(addonInfo('path'))

def idle():
	if condVisibility('Window.IsActive(busydialognocancel)'):
		return execute('Dialog.Close(busydialognocancel)')
	else:
		return execute('Dialog.Close(busydialog)')

def yesnoDialog(line, heading=addonInfo('name'), nolabel='', yeslabel=''):
	return dialog().yesno(heading, line, nolabel, yeslabel)

def selectDialog(list, heading=addonInfo('name')):
	return dialog().select(heading, list)

def multiselectDialog(list, preselect=[], heading=addonInfo('name')):
	return dialog().multiselect(heading, list, preselect=preselect)

def notification(title=None, message=None, icon=None, time=3000, sound=False):
	if title == 'default' or title is None: title = addonName()
	if isinstance(title, int): heading = lang(title)
	else: heading = str(title)
	if isinstance(message, int): body = lang(message)
	else: body = str(message)
	if icon is None or icon == '' or icon == 'default': icon = addonIcon()
	elif icon == 'INFO': icon = xbmcgui.NOTIFICATION_INFO
	elif icon == 'WARNING': icon = xbmcgui.NOTIFICATION_WARNING
	elif icon == 'ERROR': icon = xbmcgui.NOTIFICATION_ERROR
	dialog().notification(heading, body, icon, time, sound=sound)

