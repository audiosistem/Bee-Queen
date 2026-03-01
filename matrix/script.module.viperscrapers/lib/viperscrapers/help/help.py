# -*- coding: utf-8 -*-
"""
	Fenomscrapers Module
"""

from viperscrapers.modules.control import addonPath, addonVersion, joinPath
from viperscrapers.windows.textviewer import TextViewerXML


def get(file):
	viperscrapers_path = addonPath()
	viperscrapers_version = addonVersion()
	helpFile = joinPath(viperscrapers_path, 'lib', 'viperscrapers', 'help', file + '.txt')
	r = open(helpFile, 'r', encoding='utf-8', errors='ignore')
	text = r.read()
	r.close()
	heading = '[B]ViperScrapers -  v%s - %s[/B]' % (viperscrapers_version, file)
	windows = TextViewerXML('textviewer.xml', viperscrapers_path, heading=heading, text=text)
	windows.run()
	del windows