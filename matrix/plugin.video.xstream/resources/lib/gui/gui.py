# -*- coding: utf-8 -*-
# Python 3

import sys
import xbmc
import xbmcgui 
import xbmcplugin

from resources.lib import utils
from resources.lib.config import cConfig
from resources.lib.gui.contextElement import cContextElement
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.handler.ParameterHandler import ParameterHandler
from urllib.parse import quote_plus, urlencode


class cGui:
    # This class "abstracts" a list of xbmc listitems.
    def __init__(self):
        try:
            self.pluginHandle = int(sys.argv[1])
        except:
            self.pluginHandle = 0
        try:
            self.pluginPath = sys.argv[0]
        except:
            self.pluginPath = ''
        self.isMetaOn = cConfig().getSetting('TMDBMETA') == 'true'
        if cConfig().getSetting('metaOverwrite') == 'true':
            self.metaMode = 'replace'
        else:
            self.metaMode = 'add'
        # for globalSearch or alterSearch
        self.globalSearch = False
        self._collectMode = False
        self._isViewSet = False
        self.searchResults = []

    def addFolder(self, oGuiElement, params='', bIsFolder=True, iTotal=0, isHoster=False):
        # add GuiElement to Gui, adds listitem to a list
        # abort xbmc list creation if user requests abort
        if xbmc.Monitor().abortRequested():
            self.setEndOfDirectory(False)
            raise RuntimeError('UserAborted')
        # store result in list if we searched global for other sources
        if self._collectMode:
            import copy
            self.searchResults.append({'guiElement': oGuiElement, 'params': copy.deepcopy(params), 'isFolder': bIsFolder})
            return
        if not oGuiElement._isMetaSet and self.isMetaOn and oGuiElement._mediaType and iTotal < 100:
            tmdbID = params.getValue('tmdbID')
            if tmdbID:
                oGuiElement.getMeta(oGuiElement._mediaType, tmdbID, mode=self.metaMode)
            else:
                oGuiElement.getMeta(oGuiElement._mediaType, mode=self.metaMode)
        sUrl = self.__createItemUrl(oGuiElement, bIsFolder, params)
#kasi
        try:
            if params.exist('trumb'): oGuiElement.setIcon(params.getValue('trumb'))
        except:
            pass

        listitem = self.createListItem(oGuiElement)
        if not bIsFolder and cConfig().getSetting('hosterSelect') == 'List':
            bIsFolder = True
        if isHoster:
            bIsFolder = False
        listitem = self.__createContextMenu(oGuiElement, listitem, bIsFolder, sUrl)
        if not bIsFolder:
            listitem.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(self.pluginHandle, sUrl, listitem, bIsFolder, iTotal)

    def addNextPage(self, site, function, params=''):
        guiElement = cGuiElement(cConfig().getLocalizedString(30279), site, function)
        self.addFolder(guiElement, params)

    def searchNextPage(self, sTitle, site, function, params=''):
        guiElement = cGuiElement(sTitle, site, function)
        self.addFolder(guiElement, params)

    def createListItem(self, oGuiElement):
        itemValues = oGuiElement.getItemValues()
        itemTitle = oGuiElement.getTitle()
        infoString = ''
        if self.globalSearch: # Reihenfolge der zu anzeigenden GUI Elemente
            infoString += ' %s' % oGuiElement.getSiteName()
        if oGuiElement._sLanguage != '':
            infoString += ' (%s)' % oGuiElement._sLanguage
        if oGuiElement._sSubLanguage != '':
            infoString += ' *Sub: %s*' % oGuiElement._sSubLanguage
        if oGuiElement._sQuality != '':
            infoString += ' [%s]' % oGuiElement._sQuality
        if oGuiElement._sInfo != '':
            infoString += ' [%s]' % oGuiElement._sInfo    
        # if self.globalSearch:
        #     infoString += ' %s' % oGuiElement.getSiteName()
        if infoString:
            infoString = '[I]%s[/I]' % infoString
        itemValues['title'] = itemTitle + infoString
        try:
            if not 'plot' in str(itemValues) or itemValues['plot'] == '':
                itemValues['plot'] = ' ' #kasi Alt 255
        except:
            pass
        #listitem = xbmcgui.ListItem(itemTitle + infoString, oGuiElement.getIcon(), oGuiElement.getThumbnail())
        listitem = xbmcgui.ListItem(itemTitle + infoString)
        # Function: setInfo(type, infoLabels)
        # listitem.setInfo('video', { 'genre': 'Comedy' })
        listitem.setInfo(oGuiElement.getType(), itemValues)
        #Wenn Kodi 19, dann ignoriere setinfotagvideo
        kodi_version = xbmc.getInfoLabel('System.BuildVersion')
        if kodi_version[:2]  > '19':
            self.setInfoTagVideo(oGuiElement, listitem)

        listitem.setProperty('fanart_image', oGuiElement.getFanart())
        listitem.setArt({'icon': oGuiElement.getIcon(), 'thumb': oGuiElement.getThumbnail(), 'poster': oGuiElement.getThumbnail(), 'fanart': oGuiElement.getFanart()})
        aProperties = oGuiElement.getItemProperties()
        if len(aProperties) > 0:
            for sPropertyKey in aProperties.keys():
                listitem.setProperty(sPropertyKey, aProperties[sPropertyKey])
        return listitem

    ### ÄNDERUNG ANFANG ###
    def setInfoTagVideo(self, oGuiElement, listitem):
        itemValues = oGuiElement.getItemValues()
        vtag = listitem.getVideoInfoTag()
        
        vtag.setMediaType(oGuiElement.getType())
        
        # Titel ist bereits gesetzt und der Infostring geht hier verloren, wenn man den Titel erneut setzt
        #if 'title' in itemValues:
        #    try:    
        #        vtag.setTitle(itemValues['title'])
        #    except: pass
        if 'plot' in itemValues:
            try:
                vtag.setPlot(itemValues['plot'])
            except: pass
        if 'year' in itemValues:
            try:
                vtag.setYear(int(itemValues['year']))
            except: pass
        if 'season' in itemValues:
            try:
                vtag.setSeason(int(itemValues['season']))
            except: pass
        if 'episode' in itemValues:
            try:
                vtag.setEpisode(int(itemValues['episode']))
            except: pass
        if 'TVShowTitle' in itemValues:
            try:
                vtag.setTvShowTitle(itemValues['TVShowTitle'])
            except: pass
        if 'cast' in itemValues:
            try:
                vtag.setCast([xbmc.Actor(cast[0], cast[1], thumbnail=cast[2]) for cast in itemValues['cast']])
            except: pass
        if 'countries' in itemValues:
            try:
                vtag.setCountries(itemValues['countries'])
            except: pass
        if 'country' in itemValues:
            try:
                vtag.setCountries([itemValues['country']])
            except: pass
        if 'dateadded' in itemValues:
            try:
                vtag.setDateAdded(itemValues['dateadded'])
            except: pass
        if 'directors' in itemValues:
            try:
                vtag.setDirectors(itemValues['directors'])
            except: pass
        if 'duration' in itemValues:
            # minuten in sekunden umrechnen
            try:
                vtag.setDuration(int(itemValues['duration']) * 60)
            except: pass
        if 'rating' in itemValues:
            try:
                vtag.setRating(float(itemValues['rating']))
            except: pass
        if 'genre' in itemValues:
            try:
                vtag.setGenres(itemValues['genres'].split(' / '))
            except: pass
        if 'imdb_id' in itemValues:
            try:
                vtag.setUniqueID(str(itemValues['imdb_id']), 'imdb')
            except: pass
        if 'tmdb_id' in itemValues:
            try:
                vtag.setUniqueID(str(itemValues['tmdb_id']), 'tmdb')
            except: pass
        if 'originaltitle' in itemValues:
            try:
                vtag.setOriginalTitle(itemValues['originaltitle'])
            except: pass
        if 'trailer' in itemValues:
            try:
                vtag.setTrailer(itemValues['trailer'])
            except: pass
        if 'tagline' in itemValues:
            try:
                vtag.setTagLine(itemValues['tagline'])
            except: pass
        # Kodi versucht Bilder er Studios zu finden, was zu Fehlern im Logfile führt
        #if 'studio' in itemValues:
        #    try:
        #        vtag.setStudios(itemValues['studio'].split(' / '))
        #    except: pass
        if 'premiered' in itemValues:
            try:
                vtag.setPremiered(itemValues['premiered'])
            except: pass    
    ### ÄNDERUNG ENDE ###


    def __createContextMenu(self, oGuiElement, listitem, bIsFolder, sUrl):
        contextmenus = []
        if len(oGuiElement.getContextItems()) > 0:
            for contextitem in oGuiElement.getContextItems():
                params = contextitem.getOutputParameterHandler()
                sParams = params.getParameterAsUri()
                sTest = "%s?site=%s&function=%s&%s" % (self.pluginPath, contextitem.getFile(), contextitem.getFunction(), sParams)
                contextmenus += [(contextitem.getTitle(), "RunPlugin(%s)" % (sTest,),)]
        itemValues = oGuiElement.getItemValues()
        contextitem = cContextElement()
        if oGuiElement._mediaType == 'movie' or oGuiElement._mediaType == 'tvshow':
            if cConfig().getSetting('xstream.trailer') == 'true':
                if not xbmc.getCondVisibility('System.HasAddon(%s)' % 'script.module.xstream.trailer'):  # Schauen ob Addon installiert
                    xbmc.executebuiltin('InstallAddon(%s)' % 'script.module.xstream.trailer')  # Addon installieren
                contextitem.setTitle(cConfig().getLocalizedString(30027))  # Trailer Funktion
                contextmenus += [(contextitem.getTitle(), "RunPlugin(plugin://script.module.xstream.trailer/?action=play&name=%s&url=&language=)" % (itemValues['title'],),)]
        if oGuiElement._mediaType == 'movie' or oGuiElement._mediaType == 'tvshow':
            contextitem.setTitle(cConfig().getLocalizedString(30239))   # Erweiterte Info
            searchParams = {'searchTitle': oGuiElement.getTitle(), 'sMeta': oGuiElement._mediaType, 'sYear': oGuiElement._sYear}
            contextmenus += [(contextitem.getTitle(), "RunPlugin(%s?function=viewInfo&%s)" % (self.pluginPath, urlencode(searchParams),),)]
        if oGuiElement._mediaType == 'season' or oGuiElement._mediaType == 'episode':
            contextitem.setTitle(cConfig().getLocalizedString(30241))   # Info
            contextmenus += [(contextitem.getTitle(), cConfig().getLocalizedString(30242),)]    # Action(Info)
        # search for alternative source
        contextitem.setTitle(cConfig().getLocalizedString(30243))   # Weitere Quellen
        searchParams = {'searchTitle': oGuiElement.getTitle()}
        if 'imdb_id' in itemValues:
            searchParams['searchImdbID'] = itemValues['imdb_id']
        contextmenus += [(contextitem.getTitle(), "Container.Update(%s?function=searchAlter&%s)" % (self.pluginPath, urlencode(searchParams),),)]
        if 'imdb_id' in itemValues and 'title' in itemValues:
            metaParams = {}
            if itemValues['title']:
                metaParams['title'] = oGuiElement.getTitle()
            if 'mediaType' in itemValues and itemValues['mediaType']:
                metaParams['mediaType'] = itemValues['mediaType']
            elif 'TVShowTitle' in itemValues and itemValues['TVShowTitle']:
                metaParams['mediaType'] = 'tvshow'
            else:
                metaParams['mediaType'] = 'movie'
            if 'season' in itemValues and itemValues['season'] and int(itemValues['season']) > 0:
                metaParams['season'] = itemValues['season']
                metaParams['mediaType'] = 'season'
            if 'episode' in itemValues and itemValues['episode'] and int(itemValues['episode']) > 0 and 'season' in itemValues and itemValues['season'] and int(itemValues['season']):
                metaParams['episode'] = itemValues['episode']
                metaParams['mediaType'] = 'episode'

        # context options for movies or episodes
        if not bIsFolder:
            contextitem.setTitle(cConfig().getLocalizedString(30244))   # Playlist hinzufügen
            contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=enqueue)" % (sUrl,),)]
            contextitem.setTitle(cConfig().getLocalizedString(30245))   # Download
            contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=download)" % (sUrl,),)]
            if cConfig().getSetting('jd_enabled') == 'true':
                contextitem.setTitle(cConfig().getLocalizedString(30246))   # send JD
                contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=jd)" % (sUrl,),)]
            if cConfig().getSetting('jd2_enabled') == 'true':
                contextitem.setTitle(cConfig().getLocalizedString(30247))   # Send JD2
                contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=jd2)" % (sUrl,),)]
            if cConfig().getSetting('myjd_enabled') == 'true':
                contextitem.setTitle(cConfig().getLocalizedString(30248))   # Send myjd
                contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=myjd)" % (sUrl,),)]
            if cConfig().getSetting('pyload_enabled') == 'true':
                contextitem.setTitle(cConfig().getLocalizedString(30249))   # Send Pyload
                contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=pyload)" % (sUrl,),)]
            if cConfig().getSetting('hosterSelect') == 'Auto':
                contextitem.setTitle(cConfig().getLocalizedString(30149))   # select Hoster
                contextmenus += [(contextitem.getTitle(), "RunPlugin(%s&playMode=play&manual=1)" % (sUrl,),)]
        listitem.addContextMenuItems(contextmenus)
        # listitem.addContextMenuItems(contextmenus, True)
        return listitem

    def setEndOfDirectory(self, success=True):
        # mark the listing as completed, this is mandatory
        if not self._isViewSet:
            self.setView('files')
        xbmcplugin.setPluginCategory(self.pluginHandle, "")
        # add some sort methods, these will be available in all views
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_PROGRAM_COUNT)
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
        xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.endOfDirectory(self.pluginHandle, success)

    def setView(self, content='movies'):
        # set the listing to a certain content, makes special views available
        # sets view to the viewID which is selected in xStream settings
        # see http://mirrors.xbmc.org/docs/python-docs/stable/xbmcplugin.html#-setContent
        # (seasons is also supported but not listed)
        content = content.lower()
        supportedViews = ['files', 'songs', 'artists', 'albums', 'movies', 'tvshows', 'seasons', 'episodes', 'musicvideos']
        if content in supportedViews:
            self._isViewSet = True
            xbmcplugin.setContent(self.pluginHandle, content)
        if cConfig().getSetting('auto-view') == 'true' and content:
            viewId = cConfig().getSetting(content + '-view')
            if viewId:
                xbmc.executebuiltin("Container.SetViewMode(%s)" % viewId)

    def updateDirectory(self):
        # update the current listing
        xbmc.executebuiltin("Container.Refresh")

    def __createItemUrl(self, oGuiElement, bIsFolder, params=''):
        if params == '':
            params = ParameterHandler()
        itemValues = oGuiElement.getItemValues()
        if 'tmdb_id' in itemValues and itemValues['tmdb_id']:
            params.setParam('tmdbID', itemValues['tmdb_id'])
        if 'TVShowTitle' in itemValues and itemValues['TVShowTitle']:
            params.setParam('TVShowTitle', itemValues['TVShowTitle'])
        if 'season' in itemValues and itemValues['season'] and int(itemValues['season']) > 0:
            params.setParam('season', itemValues['season'])
        if 'episode' in itemValues and itemValues['episode'] and float(itemValues['episode']) > 0:
            params.setParam('episode', itemValues['episode'])
        # TODO change this, it can cause bugs it influencec the params for the following listitems
        if not bIsFolder:
            params.setParam('MovieTitle', oGuiElement.getTitle())
            thumbnail = oGuiElement.getThumbnail()
            if thumbnail:
                params.setParam('thumb', thumbnail)
            if oGuiElement._mediaType:
                params.setParam('mediaType', oGuiElement._mediaType)
            elif 'TVShowTitle' in itemValues and itemValues['TVShowTitle']:
                params.setParam('mediaType', 'tvshow')
            if 'season' in itemValues and itemValues['season'] and int(itemValues['season']) > 0:
                params.setParam('mediaType', 'season')
            if 'episode' in itemValues and itemValues['episode'] and float(itemValues['episode']) > 0:
                params.setParam('mediaType', 'episode')
        sParams = params.getParameterAsUri()
        try:
            if params.getValue('sUrl').startswith("plugin://"):
                return  params.getValue('sUrl')
        except: pass
        if len(oGuiElement.getFunction()) == 0:
            sUrl = "%s?site=%s&title=%s&%s" % (self.pluginPath, oGuiElement.getSiteName(), quote_plus(oGuiElement.getTitle()), sParams)
        else:
            #kasi
            sUrl = "%s?site=%s&function=%s&title=%s&trumb=%s&%s" % (self.pluginPath, oGuiElement.getSiteName(), oGuiElement.getFunction(), quote_plus(oGuiElement.getTitle()), oGuiElement.getThumbnail(), sParams)
            if not bIsFolder:
                sUrl += '&playMode=play'
        return sUrl

    @staticmethod
    def showKeyBoard(sDefaultText="", sHeading=""):
        # Create the keyboard object and display it modal
        oKeyboard = xbmc.Keyboard(sDefaultText, sHeading)
        oKeyboard.doModal()
        # If key board is confirmed and there was text entered return the text
        if oKeyboard.isConfirmed():
            sSearchText = oKeyboard.getText()
            if len(sSearchText) > 0:
                return sSearchText
        return False

    @staticmethod
    def showNumpad(defaultNum="", numPadTitle=cConfig().getLocalizedString(30251)):
        defaultNum = str(defaultNum)
        dialog = xbmcgui.Dialog()
        num = dialog.numeric(0, numPadTitle, defaultNum)
        return num

    @staticmethod
    def openSettings():
        cConfig().showSettingsWindow()

    @staticmethod
    def showNofication(sTitle, iSeconds=0):
        if iSeconds == 0:
            iSeconds = 1000
        else:
            iSeconds = iSeconds * 1000
        xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % (cConfig().getLocalizedString(30308), (cConfig().getLocalizedString(30309) % str(sTitle)), iSeconds, cConfig().getAddonInfo('icon')))

    @staticmethod
    def showError(sTitle, sDescription, iSeconds=0):
        if iSeconds == 0:
            iSeconds = 1000
        else:
            iSeconds = iSeconds * 1000
        xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % (str(sTitle), (str(sDescription)), iSeconds, cConfig().getAddonInfo('icon')))

    @staticmethod
    def showInfo(sTitle='xStream', sDescription=cConfig().getLocalizedString(30253), iSeconds=0):
        if iSeconds == 0:
            iSeconds = 1000
        else:
            iSeconds = iSeconds * 1000
        xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % (str(sTitle), (str(sDescription)), iSeconds, cConfig().getAddonInfo('icon')))

    @staticmethod
    def showLanguage(sTitle='xStream', sDescription=cConfig().getLocalizedString(30403), iSeconds=0):
        if iSeconds == 0:
            iSeconds = 1000
        else:
            iSeconds = iSeconds * 1000
        xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % (str(sTitle), (str(sDescription)), iSeconds, cConfig().getAddonInfo('icon')))
