# -*- coding: utf-8 -*-
# Python 3

def main():
    from xstream import parseUrl
    from os.path import join
    from sys import path
    import platform

    from resources.lib.config import cConfig
    from xbmc import LOGINFO as LOGNOTICE, log
    from xbmcvfs import translatePath

    _addonPath_ = translatePath(cConfig().getAddonInfo('path'))
    path.append(join(_addonPath_, 'resources', 'lib'))
    path.append(join(_addonPath_, 'resources', 'lib', 'gui'))
    path.append(join(_addonPath_, 'resources', 'lib', 'handler'))
    path.append(join(_addonPath_, 'resources', 'art', 'sites'))
    path.append(join(_addonPath_, 'resources', 'art'))
    path.append(join(_addonPath_, 'sites'))    
    
    LOGMESSAGE = cConfig().getLocalizedString(30166)
    log('-----------------------------------------------------------------------', LOGNOTICE)
    log(LOGMESSAGE + ' -> [default]: Start xStream Log, Version %s ' % cConfig().getAddonInfo('version'), LOGNOTICE)
    log(LOGMESSAGE + ' -> [default]: Python-Version: %s' % platform.python_version(), LOGNOTICE)

    try:
        parseUrl()
    except Exception as e:
        if str(e) == 'UserAborted':
            log(LOGMESSAGE + ' -> [default]: User aborted list creation', LOGNOTICE)
        else:
            import traceback
            import xbmcgui
            log(traceback.format_exc(), LOGNOTICE)
            value = (str(e.__class__.__name__) + ' : ' + str(e), str(traceback.format_exc().splitlines()[-3].split('addons')[-1]))
            dialog = xbmcgui.Dialog().ok(cConfig().getLocalizedString(257), str(value)) # Error

if __name__ == "__main__":
    main()
