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

log = xbmc.log
condVisibility = xbmc.getCondVisibility
infoLabel = xbmc.getInfoLabel
execute = xbmc.executebuiltin
jsonrpc = xbmc.executeJSONRPC
monitor_class = xbmc.Monitor

deleteFile = xbmcvfs.delete
existsPath = xbmcvfs.exists
listDir = xbmcvfs.listdir
openFile = xbmcvfs.File
makeFile = xbmcvfs.mkdir
makeDirs = xbmcvfs.mkdirs
renameFile = xbmcvfs.rename
transPath = xbmcvfs.translatePath
joinPath = os.path.join

dialog = xbmcgui.Dialog
progressDialog = xbmcgui.DialogProgress
progress_line = '%s[CR]%s[CR]%s'

def homeWindow():
	return xbmcgui.Window(10000)

def addon(addon_id='script.module.magneto'):
	return xbmcaddon.Addon(addon_id)

SETTINGS_PATH = transPath(joinPath(addon().getAddonInfo('path'), 'resources', 'settings.xml'))
dataPath = transPath(addon().getAddonInfo('profile'))
cacheFile = joinPath(dataPath, 'cache.db')
undesirablescacheFile = joinPath(dataPath, 'undesirables.db')
settingsFile = joinPath(dataPath, 'settings.xml')

def getProviderDefaults():
	from pov.modules.control import getProviderDefaults
	return getProviderDefaults()

def getKodiVersion(full=False):
	if full: return xbmc.getInfoLabel("System.BuildVersion")
	else: return int(xbmc.getInfoLabel("System.BuildVersion")[:2])

def setting(id, fallback=None):
	value = addon().getSetting(id)
	if not fallback is None and not value: value = fallback
	return value

def settings_fallback(id):
	return {id: addon().getSetting(id)}

def setSetting(id, value):
	return addon().setSetting(id, value)

def sleep(time): # Modified `sleep` command that honors a user exit request
	monitor = monitor_class()
	while time > 0 and not monitor.abortRequested():
		xbmc.sleep(min(100, time))
		time = time - 100

def isVersionUpdate():
	addon_folder = transPath('special://profile/addon_data/script.module.magneto/')
	versionFile = joinPath(dataPath, 'installed.version')
	curVersion = addon('script.module.magneto').getAddonInfo('version')
	try:
		if not xbmcvfs.exists(addon_folder):
			LOGINFO = 1 # (LOGNOTICE(2) deprecated in 19, use LOGINFO(1))
			xbmc.log('Magneto Addon Data Path Does not Exist. Creating Folder....', LOGINFO)
			xbmcvfs.mkdirs(addon_folder)
		with open(versionFile, 'a+') as fh:
			fh.seek(0)
			try: oldVersion = fh.read().strip()
			except: oldVersion = '0'
			if oldVersion == curVersion: return False
			fh.seek(0)
			fh.truncate(0)
			fh.write(curVersion)
		checkPackages()
		return True
	except:
		from magneto.modules import log_utils
		log_utils.error()
		return False

def checkPackages():
	packages = transPath('special://home/addons/packages/')
	files = listDir(packages)[1]
	for item in files:
		if '.magneto' in item and item.endswith('zip'):
			try: deleteFile(packages + item)
			except: pass

def clean_settings():
	addon_ids, addon_name = addonInfo('id'), addonInfo('name')
	default_xml = 'special://home/addons/%s/resources/settings.xml' % addon_ids
	profile_xml = 'special://profile/addon_data/%s/settings.xml' % addon_ids
	try:
		removed_settings = []
		removed_append = removed_settings.append
		with openFile(default_xml) as xml_file: root = ET.fromstring(xml_file.read())
		active_settings = [item.get('id') for item in root.iter('setting') if item.get('id')]
		with openFile(profile_xml) as xml_file: root = ET.fromstring(xml_file.read())
		for item in root.iter('setting'):
			if item.get('id') in active_settings: continue
			removed_append(item)
		for item in removed_settings: root.remove(item)
		with openFile(profile_xml, 'w') as xml_file: xml_file.write(ET.tostring(root))
		notification(title=addon_name, message='%s Obsolete Settings Entries Removed' % len(removed_settings))
	except:
		from magneto.modules import log_utils
		log_utils.error()
		notification(title=addon_name, message='Error Cleaning Settings.xml. Old settings.xml files Restored.')

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

def addonEnabled(addon_id):
	return condVisibility('System.AddonIsEnabled(%s)' % addon_id)

def addonInstalled(addon_id):
	return condVisibility('System.HasAddon(%s)' % addon_id)

def openSettings(query=None, id=addonInfo('id')):
	try:
		hide()
		execute('Addon.OpenSettings(%s)' % id)
		if not query: return
		c, f = query.split('.')
		execute('SetFocus(%i)' % (int(c) - 100))
		execute('SetFocus(%i)' % (int(f) - 80))
	except:
		return

def hide():
	execute('Dialog.Close(busydialog)')
	execute('Dialog.Close(busydialognocancel)')

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
	if icon in (None, '', 'default'): icon = joinPath(addonInfo('path'), 'resources', 'magneto_small.png')
	elif icon == 'INFO': icon = xbmcgui.NOTIFICATION_INFO
	elif icon == 'WARNING': icon = xbmcgui.NOTIFICATION_WARNING
	elif icon == 'ERROR': icon = xbmcgui.NOTIFICATION_ERROR
	dialog().notification(heading, body, icon, time, sound=sound)
