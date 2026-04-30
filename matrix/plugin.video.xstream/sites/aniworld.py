# -*- coding: utf-8 -*-
# Python 3

#Always pay attention to the translations in the menu!
# Sprachauswahl für Hoster enthalten.
# Ajax Suchfunktion enthalten.
# HTML LangzeitCache hinzugefügt
# showValue:     24 Stunden
# showAllSeries: 24 Stunden
# showEpisodes:   4 Stunden
# SSsearch:      24 Stunden
    
# 2022-12-06 Heptamer - Suchfunktion überarbeitet

import xbmcgui

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'aniworld'
SITE_NAME = 'AniWorld'
SITE_ICON = 'aniworld.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN
# URL_MAIN = 'https://aniworld.to'
URL_SERIES = URL_MAIN + '/animes'
URL_POPULAR = URL_MAIN + '/beliebte-animes'
URL_NEW_EPISODES = URL_MAIN + '/neue-episoden'
URL_LOGIN = URL_MAIN + '/login'
REFERER = 'https://' + DOMAIN

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    username = cConfig().getSetting('aniworld.user')    # Username
    password = cConfig().getSetting('aniworld.pass')    # Password
    if username == '' or password == '':                # If no username and password were set, close the plugin!
        xbmcgui.Dialog().ok(cConfig().getLocalizedString(30241), cConfig().getLocalizedString(30263))   # Info Dialog!
    else:
        params.setParam('sUrl', URL_SERIES)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30518), SITE_IDENTIFIER, 'showAllSeries'), params)    # All Series
        params.setParam('sUrl', URL_NEW_EPISODES)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30516), SITE_IDENTIFIER, 'showNewEpisodes'), params)  # New Episodes
        params.setParam('sUrl', URL_POPULAR)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30519), SITE_IDENTIFIER, 'showEntries'), params)    # Popular Series
        params.setParam('sUrl', URL_MAIN)
        params.setParam('sCont', 'catalogNav')
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30517), SITE_IDENTIFIER, 'showValue'), params)    # From A-Z
        params.setParam('sCont', 'homeContentGenresList')
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)    # Genre
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
        cGui().setEndOfDirectory()


def showValue():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, '<ul[^>]*class="%s"[^>]*>(.*?)<\\/ul>' % params.getValue('sCont'))
    if isMatch:
        isMatch, aResult = cParser.parse(sContainer, '<li>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)<\\/a>\s*<\\/li>')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        sUrl = sUrl if sUrl.startswith('http') else URL_MAIN + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showAllSeries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()
    pattern = '<a[^>]*href="(\\/anime\\/[^"]*)"[^>]*>(.*?)</a>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        params.setParam('sUrl', URL_MAIN + sUrl)
        params.setParam('TVShowTitle', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showNewEpisodes(entryUrl=False, sGui=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4 # HTML Cache Zeit 4 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<div[^>]*class="col-md-[^"]*"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>\s*<strong>([^<]+)</strong>\s*<span[^>]*>([^<]+)</span>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName, sInfo in aResult:
        sMovieTitle = sName + ' ' + sInfo
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        oGuiElement.setTitle(sMovieTitle)
        params.setParam('sUrl', URL_MAIN + sUrl)
        params.setParam('TVShowTitle', sMovieTitle)

        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6 # HTML Cache Zeit 6 Stunden
    sHtmlContent = oRequest.request()
    #Aufbau pattern
    #'<div[^>]*class="col-md-[^"]*"[^>]*>.*?'  # start element
    #'<a[^>]*href="([^"]*)"[^>]*>.*?'  # url
    #'<img[^>]*src="([^"]*)"[^>]*>.*?'  # thumbnail
    #'<h3>(.*?)<span[^>]*class="paragraph-end">.*?'  # title
    #'<\\/div>'  # end element
    pattern = '<div[^>]*class="col-md-[^"]*"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*>.*?<h3>(.*?)<span[^>]*class="paragraph-end">.*?</div>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sThumbnail, sName in aResult:
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('tvshow')
        params.setParam('sUrl', URL_MAIN + sUrl)
        params.setParam('TVShowTitle', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        pattern = 'pagination">.*?<a href="([^"]+)">&gt;</a>.*?</a></div>'
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, pattern)
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sTVShowTitle = params.getValue('TVShowTitle')
    oRequest = cRequestHandler(sUrl)
    sHtmlContent = oRequest.request()
    pattern = '<div[^>]*class="hosterSiteDirectNav"[^>]*>.*?<ul>(.*?)</ul>'
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        pattern = '<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>.*?'
        isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '<p[^>]*data-full-description="(.*?)"[^>]*>')
    isThumbnail, sThumbnail = cParser.parseSingleResult(sHtmlContent, '<div[^>]*class="seriesCoverBox"[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*>')
    if isThumbnail:
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail

    total = len(aResult)
    for sUrl, sName, sNr in aResult:
        isMovie = sUrl.endswith('filme')
        if 'Alle Filme' in sName:
            sName = 'Filme'
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season' if not isMovie else 'movie')
        if isThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        if not isMovie:
            oGuiElement.setTVShowTitle(sTVShowTitle)
            oGuiElement.setSeason(sNr)
            params.setParam('sSeason', sNr)
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('sUrl', URL_MAIN + sUrl)
        cGui().addFolder(oGuiElement, params, True, total)
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sTVShowTitle = params.getValue('TVShowTitle')
    sSeason = params.getValue('sSeason')
    sThumbnail = params.getValue('sThumbnail')
    if not sSeason:
        sSeason = '0'
    isMovieList = sUrl.endswith('filme')
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<table[^>]*class="seasonEpisodesList"[^>]*>(.*?)</table>'
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        if isMovieList == True:
            pattern = '<tr[^>]*data-episode-season-id="(\d+).*?<a href="([^"]+)">\s([^<]+).*?<strong>([^<]+)'
            isMatch, aResult = cParser.parse(sContainer, pattern)
            if not isMatch:
                pattern = '<tr[^>]*data-episode-season-id="(\d+).*?<a href="([^"]+)">\s([^<]+).*?<span>([^<]+)'
                isMatch, aResult = cParser.parse(sContainer, pattern)
        else:
            pattern = '<tr[^>]*data-episode-season-id="(\d+).*?<a href="([^"]+).*?(?:<strong>(.*?)</strong>.*?)?(?:<span>(.*?)</span>.*?)?<'
            isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '<p[^>]*data-full-description="(.*?)"[^>]*>')
    total = len(aResult)
    for sID, sUrl2, sNameGer, sNameEng in aResult:
        sName = '%d - ' % int(sID)
        if isMovieList == True:
            sName += sNameGer + '- ' + sNameEng
        else:
            sName += sNameGer if sNameGer else sNameEng
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode' if not isMovieList else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        if not isMovieList:
            oGuiElement.setSeason(sSeason)
            oGuiElement.setEpisode(int(sID))
            oGuiElement.setTVShowTitle(sTVShowTitle)
        params.setParam('sUrl', URL_MAIN + sUrl2)
        params.setParam('entryUrl', sUrl)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes' if not isMovieList else 'movies')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('sUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    if cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain') == 'www.aniworld.info':
        pattern = '<li[^>]*episodeLink([^"]+)"\sdata-lang-key="([^"]+).*?data-link-target="([^"]+).*?<h4>([^<]+)<([^>]+)'
        pattern2 = 'itemprop="keywords".content=".*?Season...([^"]+).S.*?'  # HD Kennzeichen
        # data-lang-key="1" Deutsch
        # data-lang-key="2" Japanisch mit englischen Untertitel
        # data-lang-key="3" Japanisch mit deutschen Untertitel
        isMatch, aResult = cParser.parse(sHtmlContent, pattern)
        aResult2 = cParser.parse(sHtmlContent, pattern2)  # pattern 2 auslesen
        if isMatch:
            for sID, sLang, sUrl, sName, sQuality in aResult:
                # Die Funktion gibt 2 werte zurück!
                # element 1 aus array "[0]" True bzw. False
                # element 2 aus array "[1]" Name von domain / hoster - wird hier nicht gebraucht!
                sUrl = sUrl.replace('/dl/2010', '/redirect/' + sID)
                if cConfig().isBlockedHoster(sName)[0]: continue # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                sLanguage = cConfig().getSetting('prefLanguage')
                if sLanguage == '1':        # Voreingestellte Sprache Deutsch in settings.xml
                    if '2' in sLang:        # data-lang-key="2" Japanisch mit englischen Untertitel
                        continue
                    elif '3' in sLang:        # data-lang-key="3" Japanisch mit deutschen Untertitel
                        continue
                    elif sLang == '1':        # data-lang-key="1" Deutsch
                        sLang = '(DE)'      # Anzeige der Sprache Deutsch
                if sLanguage == '2':        # Voreingestellte Sprache Englisch in settings.xml
                    cGui().showLanguage()   # Kein Eintrag in der ausgewählten Sprache verfügbar
                    continue
                if sLanguage == '3':        # Voreingestellte Sprache Japanisch in settings.xml
                    if '1' in sLang:        # data-lang-key="1" Deutsch
                        continue
                    elif sLang == '3':        # data-lang-key="3" Japanisch mit deutschen Untertitel
                        sLang = '(JPN) Sub: (DE)'  # Anzeige der Sprache Japanisch mit deutschen Untertitel
                    elif sLang == '2':       # data-lang-key="2" Japanisch mit englischen Untertitel
                        sLang = '(JPN) Sub: (EN)'   # Anzeige der Sprache Japanisch mit englischen Untertitel
                if sLanguage == '0':        # Alle Sprachen
                    if sLang == '1':    # data-lang-key="1"
                        sLang = '(DE)'   # Anzeige der Sprache
                    elif sLang == '3':  # data-lang-key="3"
                        sLang = '(JPN) Sub: (DE)'  # Anzeige der Sprache Japanisch mit deutschen Untertitel
                    elif sLang == '2':    # data-lang-key="2"
                        sLang = '(JPN) Sub: (EN)'   # Anzeige der Sprache Japanisch mit englischen Untertitel
                if 'HD' in aResult2[1]:  # Prüfen ob tuple aResult2 das Kennzeichen HD enthält, dann übersteuern
                    sQuality = '720'
                else:
                    sQuality = '480'
                    # Ab hier wird der sName mit abgefragt z.B:
                    # aus dem Log [serienstream]: ['/redirect/12286260', 'VOE']
                    # hier ist die sUrl = '/redirect/12286260' und der sName 'VOE'
                    # hoster.py 194
                hoster = {'link': [sUrl, sName], 'name': sName, 'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLang, sQuality), 'quality': sQuality, 'languageCode': sLang} # Language Code für hoster.py Sprache Prio
                hosters.append(hoster)
            if hosters:
                hosters.append('getHosterUrl')
            if not hosters:
                cGui().showLanguage()
            return hosters
    else:
        pattern = '<li[^>]*data-lang-key="([^"]+).*?data-link-target="([^"]+).*?<h4>([^<]+)<([^>]+)'
        pattern2 = 'itemprop="keywords".content=".*?Season...([^"]+).S.*?'  # HD Kennzeichen
        # data-lang-key="1" Deutsch
        # data-lang-key="2" Japanisch mit englischen Untertitel
        # data-lang-key="3" Japanisch mit deutschen Untertitel
        isMatch, aResult = cParser.parse(sHtmlContent, pattern)
        aResult2 = cParser.parse(sHtmlContent, pattern2)  # pattern 2 auslesen
        if isMatch:
            for sLang, sUrl, sName, sQuality in aResult:
                # Die Funktion gibt 2 werte zurück!
                # element 1 aus array "[0]" True bzw. False
                # element 2 aus array "[1]" Name von domain / hoster - wird hier nicht gebraucht!
                if cConfig().isBlockedHoster(sName)[0]: continue # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                sLanguage = cConfig().getSetting('prefLanguage')
                if sLanguage == '1':  # Voreingestellte Sprache Deutsch in settings.xml
                    if '2' in sLang:  # data-lang-key="2" Japanisch mit englischen Untertitel
                        continue
                    elif '3' in sLang:  # data-lang-key="3" Japanisch mit deutschen Untertitel
                        continue
                    elif sLang == '1':  # data-lang-key="1" Deutsch
                        sLang = '(DE)'  # Anzeige der Sprache Deutsch
                if sLanguage == '2':  # Voreingestellte Sprache Englisch in settings.xml
                    cGui().showLanguage()  # Kein Eintrag in der ausgewählten Sprache verfügbar
                    continue
                if sLanguage == '3':  # Voreingestellte Sprache Japanisch in settings.xml
                    if '1' in sLang:  # data-lang-key="1" Deutsch
                        continue
                    elif sLang == '3':  # data-lang-key="3" Japanisch mit deutschen Untertitel
                        sLang = '(JPN) Sub: (DE)'  # Anzeige der Sprache Japanisch mit deutschen Untertitel
                    elif sLang == '2':  # data-lang-key="2" Japanisch mit englischen Untertitel
                        sLang = '(JPN) Sub: (EN)'  # Anzeige der Sprache Japanisch mit englischen Untertitel
                if sLanguage == '0':  # Alle Sprachen
                    if sLang == '1':  # data-lang-key="1"
                        sLang = '(DE)'  # Anzeige der Sprache
                    elif sLang == '3':  # data-lang-key="3"
                        sLang = '(JPN) Sub: (DE)'  # Anzeige der Sprache Japanisch mit deutschen Untertitel
                    elif sLang == '2':  # data-lang-key="2"
                        sLang = '(JPN) Sub: (EN)'  # Anzeige der Sprache Japanisch mit englischen Untertitel
                if 'HD' in aResult2[1]:  # Prüfen ob tuple aResult2 das Kennzeichen HD enthält, dann übersteuern
                    sQuality = '720'
                else:
                    sQuality = '480'
                    # Ab hier wird der sName mit abgefragt z.B:
                    # aus dem Log [serienstream]: ['/redirect/12286260', 'VOE']
                    # hier ist die sUrl = '/redirect/12286260' und der sName 'VOE'
                    # hoster.py 194
                hoster = {'link': [sUrl, sName], 'name': sName, 'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLang, sQuality), 'quality': sQuality, 'languageCode': sLang} # Language Code für hoster.py Sprache Prio
                hosters.append(hoster)
            if hosters:
                hosters.append('getHosterUrl')
            if not hosters:
                cGui().showLanguage()
            return hosters


def getHosterUrl(hUrl):
    if type(hUrl) == str: hUrl = eval(hUrl)
    username = cConfig().getSetting('aniworld.user')
    password = cConfig().getSetting('aniworld.pass')
    Handler = cRequestHandler(URL_LOGIN, caching=False)
    Handler.addHeaderEntry('Upgrade-Insecure-Requests', '1')
    Handler.addHeaderEntry('Referer', ParameterHandler().getValue('entryUrl'))
    Handler.addParameters('email', username)
    Handler.addParameters('password', password)
    Handler.request()
    Request = cRequestHandler(URL_MAIN + hUrl[0], caching=False)
    Request.addHeaderEntry('Referer', ParameterHandler().getValue('entryUrl'))
    Request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
    Request.request()
    sUrl = Request.getRealUrl()

    if 'voe' in hUrl[1].lower():
        isBlocked, sDomain = cConfig().isBlockedHoster(sUrl)  # Die funktion gibt 2 werte zurück!
        if isBlocked:  # Voe Pseudo sDomain nicht bekannt in resolveUrl
            sUrl = sUrl.replace(sDomain, 'voe.sx')
            return [{'streamUrl': sUrl, 'resolved': False}]

    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    SSsearch(oGui, sSearchText)


def SSsearch(sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    params.getValue('sSearchText')
    oRequest = cRequestHandler(URL_SERIES, caching=True, ignoreErrors=(sGui is not False))
    oRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
    oRequest.addHeaderEntry('Referer', REFERER  + '/animes')
    oRequest.addHeaderEntry('Origin', REFERER)
    oRequest.addHeaderEntry('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
    oRequest.addHeaderEntry('Upgrade-Insecure-Requests', '1')
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24  # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()

    if not sHtmlContent:
            return

    sst = sSearchText.lower()

    pattern = '<li><a data.+?href="([^"]+)".+?">(.*?)\<\/a><\/l' #link - title

    aResult = cParser.parse(sHtmlContent, pattern)

    if not aResult[0]:
        oGui.showInfo()
        return

    total = len(aResult[1])
    for link, title in aResult[1]:
        titleLow = title.lower()
        if not sst in titleLow and not cUtil.isSimilarByToken(sst, titleLow):
            continue
        else:
            #get images thumb / descr pro call. (optional)
            try:
                sThumbnail, sDescription = getMetaInfo(link, title)
                oGuiElement = cGuiElement(title, SITE_IDENTIFIER, 'showSeasons')
                oGuiElement.setThumbnail(URL_MAIN + sThumbnail)
                oGuiElement.setDescription(sDescription)
                oGuiElement.setTVShowTitle(title)
                oGuiElement.setMediaType('tvshow')
                params.setParam('sUrl', URL_MAIN + link)
                params.setParam('sName', title)
                oGui.addFolder(oGuiElement, params, True, total)
            except Exception:
                oGuiElement = cGuiElement(title, SITE_IDENTIFIER, 'showSeasons')
                oGuiElement.setTVShowTitle(title)
                oGuiElement.setMediaType('tvshow')
                params.setParam('sUrl', URL_MAIN + link)
                params.setParam('sName', title)
                oGui.addFolder(oGuiElement, params, True, total)

        if not sGui:
            oGui.setView('tvshows')


def getMetaInfo(link, title):   # Setzen von Metadata in Suche:
    oGui = cGui()
    oRequest = cRequestHandler(URL_MAIN + link, caching=False)
    oRequest.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
    oRequest.addHeaderEntry('Referer', REFERER + '/animes')
    oRequest.addHeaderEntry('Origin', REFERER)

    #GET CONTENT OF HTML
    sHtmlContent = oRequest.request()
    if not sHtmlContent:
        return

    pattern = 'seriesCoverBox">.*?<img src="([^"]+)"\ al.+?data-full-description="([^"]+)"' #img , descr

    aResult = cParser.parse(sHtmlContent, pattern)

    if not aResult[0]:
        return

    for sImg, sDescr in aResult[1]:
        return sImg, sDescr