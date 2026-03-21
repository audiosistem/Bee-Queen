# -*- coding: UTF-8 -*-

import sys, os, xbmc

if sys.version_info[0] >= 3:
    import xbmcvfs

    translatePath = xbmcvfs.translatePath
else:
    translatePath = xbmc.translatePath


addon_id = 'plugin.video.balandro'

install = False

if __name__ == '__main__':
    addonfolder = translatePath(os.path.join('special://home/addons', addon_id))

    if not os.path.exists(addonfolder): install = True
    elif not xbmc.getCondVisibility('System.HasAddon(addon_id)'): install = True

if install: 
    xbmc.executebuiltin('InstallAddon(%s)' % (addon_id))
