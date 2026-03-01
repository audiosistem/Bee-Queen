# -*- coding: utf-8 -*-
"""
	Fenomscrapers Module
"""

from viperscrapers.modules.control import addonPath, addonVersion, joinPath
from viperscrapers.windows.textviewer import TextViewerXML


def get():
	viperscrapers_path = addonPath()
	viperscrapers_version = addonVersion()
	changelogfile = joinPath(viperscrapers_path, 'changelog.txt')
	r = open(changelogfile, 'r', encoding='utf-8', errors='ignore')
	text = r.read()
	r.close()
	heading = '[B]ViperScrapers -  v%s - ChangeLog[/B]' % viperscrapers_version
	windows = TextViewerXML('textviewer.xml', viperscrapers_path, heading=heading, text=text)
	windows.run()
	del windows