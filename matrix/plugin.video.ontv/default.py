# -*- coding: utf-8 -*-
import sys, os, xbmcaddon
ADDON = xbmcaddon.Addon()
sys.path.insert(0, os.path.join(ADDON.getAddonInfo('path'), 'resources', 'lib'))
from navigator import run
if __name__ == '__main__':
    run()
