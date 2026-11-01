"""
	thin wrapper for plugin.video.pov sources
"""

import sys
import xbmcvfs

pov_path = xbmcvfs.translatePath('special://home/addons/plugin.video.pov/lib/')
if pov_path not in sys.path: sys.path.insert(0, pov_path)

from pov import sources
