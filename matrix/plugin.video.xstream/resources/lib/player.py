# -*- coding: utf-8 -*-
# Python 3

import xbmc
from resources.lib.gui.gui import cGui
from resources.lib.config import cConfig
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, log

class XstreamPlayer(xbmc.Player):
    def __init__(self, *args, **kwargs):
        xbmc.Player.__init__(self, *args, **kwargs)
        self.streamFinished = False
        self.streamSuccess = True
        self.playedTime = 0
        self.totalTime = 999999
        log(cConfig().getLocalizedString(30166) + ' -> [player]: player instance created', LOGNOTICE)

    def onPlayBackStarted(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: starting Playback', LOGNOTICE)
        self.totalTime = self.getTotalTime()

    def onPlayBackStopped(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: Playback stopped', LOGNOTICE)
        if self.playedTime == 0 and self.totalTime == 999999:
            self.streamSuccess = False
            log(cConfig().getLocalizedString(30166) + ' -> [player]: Kodi failed to open stream', LOGERROR)
        self.streamFinished = True

    def onPlayBackEnded(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: Playback completed', LOGNOTICE)
        self.onPlayBackStopped()


class cPlayer:
    def clearPlayList(self):
        oPlaylist = self.__getPlayList()
        oPlaylist.clear()

    def __getPlayList(self):
        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def addItemToPlaylist(self, oGuiElement):
        oListItem = cGui().createListItem(oGuiElement)
        self.__addItemToPlaylist(oGuiElement, oListItem)

    def __addItemToPlaylist(self, oGuiElement, oListItem):
        oPlaylist = self.__getPlayList()
        oPlaylist.add(oGuiElement.getMediaUrl(), oListItem)

    def startPlayer(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: start player', LOGNOTICE)
        xbmcPlayer = XstreamPlayer()
        monitor = xbmc.Monitor()
        while (not monitor.abortRequested()) & (not xbmcPlayer.streamFinished):
            if xbmcPlayer.isPlayingVideo():
                xbmcPlayer.playedTime = xbmcPlayer.getTime()
            monitor.waitForAbort(10)
        return xbmcPlayer.streamSuccess
