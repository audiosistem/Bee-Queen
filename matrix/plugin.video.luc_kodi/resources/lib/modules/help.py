# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from resources.lib.modules.control import addonPath, addonId, getluc_kodiVersion, joinPath
from resources.lib.windows.textviewer import TextViewerXML


def get(file):
	luc_kodi_path = addonPath(addonId())
	luc_kodi_version = getluc_kodiVersion()
	helpFile = joinPath(luc_kodi_path, 'resources', 'help', file + '.txt')
	f = open(helpFile, 'r', encoding='utf-8', errors='ignore')
	text = f.read()
	f.close()
	heading = '[B]luc_kodi -  v%s - %s[/B]' % (luc_kodi_version, file)
	windows = TextViewerXML('textviewer.xml', luc_kodi_path, heading=heading, text=text)
	windows.run()
	del windows
