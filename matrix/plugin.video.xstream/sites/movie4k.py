# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showValue:     48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden


from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'movie4k'
SITE_NAME = 'Movie4k'
SITE_ICON = 'movie4k.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'www.movie4k.food') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN + '/'
# URL_MAIN = 'https://www.movie4k.support/'
URL_KINO = URL_MAIN + 'aktuelle-kinofilme-im-kino'
URL_MOVIES = URL_MAIN + 'kinofilme-online'
URL_SERIES = URL_MAIN + 'serienstream-deutsch'
URL_SEARCH = URL_MAIN + 'index.php?do=search&subaction=search&search_start=0&full_search=0&result_from=1&story=%s'

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Current films in the cinema  
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries'), params)  # Movies
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Series
    params.setParam('sCont', 'Jahr')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30508), SITE_IDENTIFIER, 'showValue'), params)    # Release Year  
    params.setParam('sCont', 'Land')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30402), SITE_IDENTIFIER, 'showValue'), params)    # Countries
    params.setParam('sCont', 'Genre')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)    # Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
    cGui().setEndOfDirectory()


def showValue():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48 # 48 Stunden
    sHtmlContent = oRequest.request()    
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, '%s<.*?</ul>' % params.getValue('sCont'))
    if isMatch:
        pattern = 'href="([^"]+).*?true">([^"]+)</a>'
        isMatch, aResult = cParser.parse(sContainer, pattern)
    if not isMatch: return
    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        if 'ino' in sName or 'erien' in sName: continue
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<article.*?(.*?)<a.*?href="([^"]+).*?<h3>([^<]+).*?(.*?)</article>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sInfo, sUrl, sName, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName): continue
        # Abfrage der voreingestellten Sprache
        sLanguage = cConfig().getSetting('prefLanguage')
        if (sLanguage == '1' and 'English*' in sName):   # Deutsch
            continue
        if (sLanguage == '2' and not 'English*' in sName):   # English
            continue
        elif sLanguage == '3':    # Japanisch
            cGui().showLanguage()
            continue
        isInfoEpisode, sInfo = cParser.parseSingleResult(sInfo, '</span>([\d]+)')  # Episodenanzahl
        isThumbnail, sThumbnail = cParser.parseSingleResult(sDummy, 'data-src="([^"]+)')  # Thumbnail
        isQuality, sQuality = cParser.parseSingleResult(sDummy, '<li>([^<]+)')  # Qualität
        isYear, sYear = cParser.parseSingleResult(sDummy, 'class="white">([\d]+)')  # Release Jahr
        isTvshow = True if 'taffel' in sName else False
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if isThumbnail:
            sThumbnail = URL_MAIN + sThumbnail
            oGuiElement.setThumbnail(sThumbnail)
        if isYear:
            oGuiElement.setYear(sYear)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        if isInfoEpisode:
            oGuiElement.setInfo(sInfo + ' Episoden')
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'Nächste[^>]Seite">[^>]*<a[^>]href="([^"]+)')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="row page_numbers">(.*?)</div></div></div>')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, '<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+)</a>.*?"page_next".*?href="([^"]+)')
            for sPageActive, sPageLast, sNextPage in aResult:
                # sPageName = '[I]Seitensuche starten  >>> [/I] Seite ' + str(sPageActive) + ' von ' + str(sPageLast) + ' Seiten  [I]<<<[/I]'
                sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                params.setParam('sNextPage', sNextPage)
                params.setParam('sPageLast', sPageLast)
                oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
            # End Page Function
        if isMatchNextPage:
            if '/xfsearch/' not in entryUrl:
                params.setParam('sUrl', sNextUrl)
                oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if 'taffel' in sName else 'movies')
        oGui.setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    sThumbnail = params.getValue('sThumbnail')
    entryUrl = params.getValue('entryUrl')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
    sHtmlContent = oRequest.request()    
    pattern = 'id="serie-(\d+)[^>](\d+).*?href="#">([^<]+)'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch: return
    isTvshow, sTVShowTitle = cParser.parseSingleResult(sHtmlContent, '<title>([^-]+)')
    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, 'name="description" content="([^"]+)')
    total = len(aResult)
    for sSeasonNr, sEpisodeNr, sName in aResult:
        oGuiElement = cGuiElement('Episode ' + sEpisodeNr, SITE_IDENTIFIER, 'showHosters')
        if isTvshow:
            oGuiElement.setTVShowTitle(sTVShowTitle.strip())
        oGuiElement.setSeason(sSeasonNr)
        oGuiElement.setEpisode(sEpisodeNr)
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('episode')
        if isDesc:
            oGuiElement.setDescription(sDesc)
        params.setParam('sEpisodeNr', sName)
        params.setParam('entryUrl', entryUrl)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    sHtmlContent = cRequestHandler(ParameterHandler().getValue('entryUrl'), caching=False).request()
    if ParameterHandler().getValue('sEpisodeNr'):
        pass
        pattern = '%s<.*?</ul>' % ParameterHandler().getValue('sEpisodeNr')
        isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
    isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+)">([^<]+)')
    if isMatch:
        sQuality = '720p'
        for sUrl, sName in aResult:
            if 'youtube' in sUrl:
                continue
            elif sUrl.startswith('//'):
                sUrl = 'https:' + sUrl
            sName = cParser.urlparse(sUrl).split('.')[0].strip()
            if cConfig().isBlockedHoster(sName)[0]: continue # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
            hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%s][/I]' % (sName, sQuality), 'quality': sQuality}
            hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)


def showSearchPage(): # Suche für die Page Funktion
    params = ParameterHandler()
    sNextPage = params.getValue('sNextPage') # URL mit nächster Seite
    sPageLast = params.getValue('sPageLast') # Anzahl gefundener Seiten
    #sHeading = 'Bitte eine Zahl zwischen 1 und ' + str(sPageLast) + ' wählen.'
    sHeading = cConfig().getLocalizedString(30282) + str(sPageLast)
    sSearchPageText = cGui().showKeyBoard(sHeading=sHeading)
    if not sSearchPageText: return
    sNextSearchPage = sNextPage.split('page/')[0].strip() + 'page/' + sSearchPageText + '/'
    showEntries(sNextSearchPage)
    cGui().setEndOfDirectory()