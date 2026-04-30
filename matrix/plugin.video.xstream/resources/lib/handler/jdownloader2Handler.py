# -*- coding: utf-8 -*-
# Python 3

import re

from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from xbmc import LOGINFO as LOGNOTICE, log
from urllib.request import Request, urlopen
from urllib.parse import urlencode

class cJDownloader2Handler:
    def sendToJDownloader2(self, sUrl):
        if self.__checkConfig() is False:
            cGui().showError(cConfig().getLocalizedString(30076), cConfig().getLocalizedString(30254), 5)
            return False

        if self.__checkConnection() is False:
            cGui().showError(cConfig().getLocalizedString(30076), cConfig().getLocalizedString(30255), 5)
            return False

        if self.__download(sUrl) is True:
            cGui().showInfo(cConfig().getLocalizedString(30076), cConfig().getLocalizedString(30256), 5)
            return True
        return False

    def __client(self, path, params):
        sHost = self.__getHost()
        sPort = self.__getPort()
        ENCODING = 'utf-8'
        url = 'http://{}:{}/{}'.format(sHost, sPort, path)
        if params is not None:
            headers = {'Content-Type': 'application/x-www-form-urlencoded;charset={}'.format(ENCODING), }
            request = Request(url, urlencode(params).encode(ENCODING), headers)
        else:
            request = Request(url)
        return urlopen(request).read().decode(ENCODING).strip()

    def __download(self, sFileUrl):
        log(cConfig().getLocalizedString(30166) + ' -> [jdownloader2Handler]: JD2 Link: ' + str(sFileUrl), LOGNOTICE)
        params = {'passwords': 'myPassword', 'source': 'http://jdownloader.org/spielwiese', 'urls': sFileUrl, 'submit': 'Add Link to JDownloader', }
        if self.__client('flash/add', params).lower() == 'success':
            return True
        else:
            return False

    def __checkConfig(self):
        log(cConfig().getLocalizedString(30166) + ' -> [jdownloader2Handler]: check JD2 Addon settings', LOGNOTICE)
        bEnabled = cConfig().getSetting('jd2_enabled')
        if bEnabled == 'true':
            return True
        return False

    def __getHost(self):
        return cConfig().getSetting('jd2_host')

    def __getPort(self):
        return cConfig().getSetting('jd2_port')

    def __checkConnection(self):
        log(cConfig().getLocalizedString(30166) + ' -> [jdownloader2Handler]: check JD2 Connection', LOGNOTICE)
        try:
            output = self.__client('jdcheck.js', None)
            pattern = re.compile(r'jdownloader\s*=\s*true', re.IGNORECASE)
            if pattern.search(output) != None:
                return True
        except Exception:
            return False
        return False
