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

SITE_IDENTIFIER = 'hdfilme_1'
SITE_NAME = 'FHD Filme'
SITE_ICON = 'hdfilme_1.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'hdfilme.my') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN
# URL_MAIN = 'https://hdfilme.my'

URL_NEW = URL_MAIN + '/filme1/'
URL_KINO = URL_MAIN + '/kinofilme/'
URL_MOVIES = URL_MAIN
URL_SERIES = URL_MAIN + '/serien/'
URL_SEARCH = URL_MAIN + '/?story=%s&do=search&subaction=search'

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)  # New
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)  # Current films in the cinema
    params.setParam('sUrl', URL_MOVIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries'), params)  # Movies
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Series  
    params.setParam('Value', 'Jahres')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30508), SITE_IDENTIFIER, 'showValue'), params)    # Release Year    
    params.setParam('Value', 'Genre')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)    # Genre
    params.setParam('Value', 'Land')
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30538), SITE_IDENTIFIER, 'showValue'), params)  # Country
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
    cGui().setEndOfDirectory()


def showValue():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48  # 48 Stunden
    sHtmlContent = oRequest.request()
    pattern = '>{0}</(.*?)</a[^<]*</div>'.format(params.getValue('Value'))
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
        for sUrl, sName in aResult:
            if sUrl.startswith('/'):
                sUrl = URL_MAIN + sUrl
            params.setParam('sUrl', sUrl)
            cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    if not isMatch:
        cGui().showInfo()
        return
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    pattern = 'class="item relative mt-3">.*?href="([^"]+).*?title="([^"]+).*?data-src="([^"]+)(.*?)</div></div>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName, sThumbnail, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        isYear, sYear = cParser.parseSingleResult(sDummy, 'mt-1">[^<]*<span>([\d]+)</span>')  # Release Jahr
        isDuration, sDuration = cParser.parseSingleResult(sDummy, '<span>([\d]+)\smin</span>')  # Laufzeit
        if int(sDuration) <= int('70'): # Wenn Laufzeit kleiner oder gleich 70min, dann ist es eine Serie.
            isTvshow = True
        else:
            from resources.lib.tmdb import cTMDB
            oMetaget = cTMDB()
            if not oMetaget:
                isTvshow = False
            else:
                if isYear:
                    meta = oMetaget.search_movie_name(sName, year=sYear)
                else:
                    meta = oMetaget.search_movie_name(sName)
                if meta and 'id' in meta:
                    isTvshow = False
                else:
                    isTvshow = True
        if 'South Park: The End Of Obesity' in sName:
            isTvshow = False
        isQuality, sQuality = cParser.parseSingleResult(sDummy, '">([^<]+)</span>')  # Qualität
        sThumbnail = URL_MAIN + sThumbnail
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        if isYear:
            oGuiElement.setYear(sYear)
        if isDuration:
            oGuiElement.addItemValue('duration', sDuration)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', sUrl)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'nav_ext">.*?next">.*?href="([^"]+)')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="pages">(.*?)<svg')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, '<span>([\d]+)</span>.*?">([\d]+)</a></div>.*?ref="([^"]+)')
            for sPageActive, sPageLast, sNextPage in aResult:
                #sPageName = '[I]Seitensuche starten  >>> [/I] Seite ' + str(sPageActive) + ' von ' + str(sPageLast) + ' Seiten  [I]<<<[/I]'
                sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                params.setParam('sNextPage', sNextPage)
                params.setParam('sPageLast', sPageLast)
                oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
            # End Page Function
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    # Parameter laden
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # HTML Cache Zeit 6 Stunden
    sHtmlContent = oRequest.request()
    pattern = 'class="su-accordion collapse show"(.*?)<br>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, '#se-ac-(\d+)')
        total = len(aResult)
        for sSeason in aResult:
            oGuiElement = cGuiElement('Staffel ' + str(sSeason), SITE_IDENTIFIER, 'showEpisodes')
            oGuiElement.setSeason(sSeason)
            oGuiElement.setMediaType('season')
            oGuiElement.setThumbnail(sThumbnail)
            cGui().addFolder(oGuiElement, params, True, total)
    if not isMatch:
        cGui().showInfo()
        return
    cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    # Parameter laden
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sSeason = params.getValue('season')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
    sHtmlContent = oRequest.request()
    pattern = '#se-ac-%s(.*?)</div></div>' % sSeason
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'Episode\s(\d+)')
        total = len(aResult)
        for sEpisode in aResult:
            oGuiElement = cGuiElement('Episode ' + str(sEpisode), SITE_IDENTIFIER, 'showEpisodeHosters')
            oGuiElement.setThumbnail(sThumbnail)
            oGuiElement.setMediaType('episode')
            params.setParam('entryUrl', entryUrl)
            params.setParam('season', sSeason)
            params.setParam('episode', sEpisode)
            cGui().addFolder(oGuiElement, params, False, total)
    if not isMatch:
        cGui().showInfo()
        return
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showEpisodeHosters():
    hosters = []
    params = ParameterHandler()
    # Parameter laden
    sUrl = params.getValue('entryUrl')
    sSeason = params.getValue('season')
    sEpisode = params.getValue('episode')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    pattern = '#se-ac-%s(.*?)</div></div>' % sSeason
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        pattern = 'x%s\sEpisode(.*?)<br' % sEpisode
        isMatch, sHtmlLink = cParser.parseSingleResult(sHtmlContainer, pattern)
        if isMatch:
            isMatch, aResult = cParser.parse(sHtmlLink, 'href="([^"]+)')
            if isMatch:
                sQuality = '720'
                for sUrl in aResult:
                    if 'youtube' in sUrl:
                        continue
                    elif sUrl.startswith('//'):
                        sUrl = 'https:' + sUrl
                    sName = cParser.urlparse(sUrl).split('.')[0].strip()
                    if cConfig().isBlockedHoster(sName)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                    hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
                    hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def showHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    pattern = '<iframe\sw.*?src="([^"]+)'
    isMatch, hUrl = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        sHtmlContainer = cRequestHandler(hUrl).request()
        isMatch, aResult = cParser.parse(sHtmlContainer, 'data-link="([^"]+)')
        if isMatch:
            sQuality= '720'
            for sUrl in aResult:
                if 'youtube' in sUrl:
                    continue
                elif sUrl.startswith('//'):
                    sUrl = 'https:' + sUrl
                sName = cParser.urlparse(sUrl).split('.')[0].strip()
                if cConfig().isBlockedHoster(sName)[0]: continue # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
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