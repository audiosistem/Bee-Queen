# -*- coding: utf-8 -*-
# Python 3

import myjdapi

from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from xbmc import LOGINFO as LOGNOTICE, log

class cMyJDownloaderHandler:

    def sendToMyJDownloader(self, sUrl, sMovieTitle):
        if self.__checkConfig() == False:
            cGui().showError(cConfig().getLocalizedString(30090), cConfig().getLocalizedString(30254), 5)
            return False

        jd = myjdapi.Myjdapi()
        if jd.connect(self.__getUser(), self.__getPass()) == False:
            cGui().showError(cConfig().getLocalizedString(30090), cConfig().getLocalizedString(30255), 5)
            return False

        if jd.update_devices() == False:
            cGui().showError(cConfig().getLocalizedString(30090), cConfig().getLocalizedString(30256), 5)
            return False

        device = jd.get_device(self.__getDevice())
        if device.linkgrabber.add_links([{"autostart": False, "links": sUrl, "packageName": sMovieTitle}])['id'] > 0:
            cGui().showInfo(cConfig().getLocalizedString(30090), cConfig().getLocalizedString(30256), 5)
            return True
        return False

    def __checkConfig(self):
        log(cConfig().getLocalizedString(30166) + ' -> [myjdownloaderHandler]: check MYJD Addon setings', LOGNOTICE)
        if cConfig().getSetting('myjd_enabled') == 'true':
            return True
        return False

    def __getDevice(self):
        return cConfig().getSetting('myjd_device')

    def __getUser(self):
        return cConfig().getSetting('myjd_user')

    def __getPass(self):
        return cConfig().getSetting('myjd_pass')
