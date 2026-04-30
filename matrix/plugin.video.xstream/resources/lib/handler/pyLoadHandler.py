# -*- coding: utf-8 -*-
# Python 3

import sys

from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from xbmc import LOGINFO as LOGNOTICE, log
from string import maketrans
from urllib.request import Request, urlopen, build_opener
from urllib.error import HTTPError
from urllib.parse import urlencode, quote_plus

class cPyLoadHandler:
    def __init__(self):
        self.config = cConfig()

    def sendToPyLoad(self, sPackage, sUrl):
        log(cConfig().getLocalizedString(30166) + ' -> [pyLoadHandler]: PyLoad package: ' + str(sPackage) + ', ' + str(sUrl), LOGNOTICE)
        if self.__sendLinkToCore(sPackage, sUrl):
            cGui().showInfo(cConfig().getLocalizedString(30257), cConfig().getLocalizedString(30256), 5)
        else:
            cGui().showInfo(cConfig().getLocalizedString(30257), cConfig().getLocalizedString(30258), 5)

    def __sendLinkToCore(self, sPackage, sUrl):
        log(cConfig().getLocalizedString(30166) + ' -> [pyLoadHandler]: Sending link...', LOGNOTICE)
        try:
            py_host = self.config.getSetting('pyload_host')
            py_port = self.config.getSetting('pyload_port')
            py_user = self.config.getSetting('pyload_user')
            py_passwd = self.config.getSetting('pyload_passwd')
            mydata = [('username', py_user), ('password', py_passwd)]
            mydata = urlencode(mydata)
            # check if host has a leading http://
            if py_host.find('http://') != 0:
                py_host = 'http://' + py_host
            log(cConfig().getLocalizedString(30166) + ' -> [pyLoadHandler]: Attemting to connect to PyLoad at: ' + py_host + ':' + py_port, LOGNOTICE)
            req = Request(py_host + ':' + py_port + '/api/login', mydata)
            req.add_header("Content-type", "application/x-www-form-urlencoded")
            page = urlopen(req).read()
            page = page[1:]
            session = page[:-1]
            opener = build_opener()
            opener.addheaders.append(('Cookie', 'beaker.session.id=' + session))
            sPackage = str(sPackage).decode("utf-8").encode('ascii', 'replace').translate(maketrans('\\/:*?"<>|', '_________'))
            py_url = py_host + ':' + py_port + '/api/addPackage?name="' + quote_plus(sPackage) + '"&links=["' + quote_plus(sUrl) + '"]'
            log(cConfig().getLocalizedString(30166) + ' -> [pyLoadHandler]: PyLoad API call: ' + py_url, LOGNOTICE)
            sock = opener.open(py_url).read()
            sock.close()
            return True
        except HTTPError as e:
            log(cConfig().getLocalizedString(30166) + ' -> [pyLoadHandler]: unable to send link: Error= ' + str(sys.exc_info()[0]), LOGNOTICE)
            log(e.code, LOGNOTICE)
            log(e.read(), LOGNOTICE)
            try:
                sock.close()
            except Exception:
                log(cConfig().getLocalizedString(30166) + ' -> [pyLoadHandler]: unable to close socket...', LOGNOTICE)
            return False
