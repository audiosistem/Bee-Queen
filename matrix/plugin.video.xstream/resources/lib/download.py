# -*- coding: utf-8 -*-
# Python 3

import os
import time
import xbmcgui

from resources.lib import utils
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from xbmc import LOGINFO as LOGNOTICE, log
from xbmcvfs import translatePath
from urllib.request import Request, urlopen

class cDownload:
    def __createProcessDialog(self, downloadDialogTitle):
        if cConfig().getSetting('backgrounddownload') == 'true':
            oDialog = xbmcgui.DialogProgressBG()
        else:
            oDialog = xbmcgui.DialogProgress()
        oDialog.create(downloadDialogTitle)
        self.__oDialog = oDialog


    def __createDownloadFilename(self, filename):
        filename = filename.replace(' ', '_')
        return filename


    def download(self, url, sTitle, showDialog=True, downloadDialogTitle=cConfig().getLocalizedString(30245)):
        sTitle = '%s' % sTitle
        self.__processIsCanceled = False
        try:
            header = dict([item.split('=') for item in (url.split('|')[1]).split('&')])
        except Exception:
            header = {}
        log(cConfig().getLocalizedString(30166) + ' -> [download]: Header for download: %s' % header, LOGNOTICE)
        url = url.split('|')[0]
        sTitle = self.__createTitle(url, sTitle)
        self.__sTitle = self.__createDownloadFilename(sTitle)
        if showDialog:
            self.__sTitle = cGui().showKeyBoard(self.__sTitle, sHeading=cConfig().getLocalizedString(30290))
            if self.__sTitle != False and len(self.__sTitle) > 0:
                sPath = cConfig().getSetting('download-folder')
                if sPath == '':
                    dialog = xbmcgui.Dialog()
                    sPath = dialog.browse(3, 'Downloadfolder', 'files', '')
                if sPath != '':
                    sDownloadPath = translatePath(sPath + '%s' % (self.__sTitle,))
                    self.__prepareDownload(url, header, sDownloadPath, downloadDialogTitle)
        elif self.__sTitle != False:
            temp_dir = os.path.join(translatePath(cConfig().getAddonInfo('profile')))
            if not os.path.isdir(temp_dir):
                os.makedirs(os.path.join(temp_dir))
            self.__prepareDownload(url, header, os.path.join(temp_dir, sTitle), downloadDialogTitle)
            log(cConfig().getLocalizedString(30166) + ' -> [download]: download completed', LOGNOTICE)


    def __prepareDownload(self, url, header, sDownloadPath, downloadDialogTitle):
        try:
            log(cConfig().getLocalizedString(30166) + ' -> [download]: download file: ' + str(url) + ' to ' + str(sDownloadPath), LOGNOTICE)
            self.__createProcessDialog(downloadDialogTitle)
            request = Request(url, headers=header)
            self.__download(urlopen(request, timeout=240), sDownloadPath)
        except Exception as e:
            log(e)
        self.__oDialog.close()


    def __download(self, oUrlHandler, fpath):
        headers = oUrlHandler.info()
        iTotalSize = -1
        if 'content-length' in headers:
            iTotalSize = (headers['Content-Length'])
        chunk = 4096
        #f = open(r'%s' % fpath, 'wb')
        import xbmcvfs
        f = xbmcvfs.File(fpath, 'w')
        log(cConfig().getLocalizedString(30166) + ' -> [download]: start download', LOGNOTICE)
        try:
            iCount = 0
            self._startTime = time.time()
            while 1:
                iCount = iCount + 1
                data = oUrlHandler.read(chunk)
                if not data or self.__processIsCanceled == True:
                    break
                f.write(data)
                self.__stateCallBackFunction(iCount, chunk, iTotalSize)              
            f.close()
            
        except:
            log(cConfig().getLocalizedString(30166) + '-> [download]: download failed', LOGNOTICE)     
            f.close()


    def __createTitle(self, sUrl, sTitle):
        aTitle = sTitle.rsplit('.')
        if len(aTitle) > 1:
            return sTitle
        aUrl = sUrl.rsplit('.')
        if len(aUrl) > 1:
            sSuffix = aUrl[-1]
            sTitle = sTitle + '.' + sSuffix
        return sTitle


    def __stateCallBackFunction(self, iCount, iBlocksize, iTotalSize):
        timedif = time.time() - self._startTime
        currentLoaded = int(iCount) * iBlocksize
        iPercent = (currentLoaded * 100 // int(iTotalSize))
        if timedif > 0.0:
            avgSpd = (currentLoaded // timedif // 1024.0)
        else:
            avgSpd = 5
        value = self.__sTitle, str('%s/%s@%dKB/s' % (self.__formatFileSize(currentLoaded), self.__formatFileSize(iTotalSize), avgSpd))
        self.__oDialog.update(iPercent, str(value))
        if cConfig().getSetting('backgrounddownload') == 'false' and self.__oDialog.iscanceled():
            self.__processIsCanceled = True
            self.__oDialog.close()


    def __formatFileSize(self, iBytes):
        iBytes = int(iBytes)
        if iBytes == 0:
            return '%.*f %s' % (2, 0, 'MB')
        return '%.*f %s' % (2, int(iBytes) // (1024 * 1024.0), 'MB')
