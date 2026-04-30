# -*- coding: utf-8 -*-
# Python 3

# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden


from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'xcine'
SITE_NAME = 'xCine'
SITE_ICON = 'xcinetop.png'

if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'xcine.io') 
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status')
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER)

URL_MAIN = 'https://' + DOMAIN + '/'
URL_NEW = URL_MAIN + 'kinofilme-online/'
URL_KINO = URL_MAIN + 'aktuelle-kinofilme-im-kino/'
URL_ANIMATION = URL_MAIN + 'animation/'
URL_SERIES = URL_MAIN + 'serienstream-deutsch/'
URL_SEARCH = URL_MAIN + 'browse?keyword=%s'


def load(): 
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    params.setParam('sUrl', URL_NEW)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_KINO)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30501), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_ANIMATION)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30504), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30524), SITE_IDENTIFIER, 'showYears'), params)
    params.setParam('sUrl', URL_MAIN)
    #cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'), params)    #Suche ausgeblendet da diese auf der Site nicht funktioniert
    #cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'))
    cGui().setEndOfDirectory()


def showGenre(entryUrl=False):
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48
    sHtmlContent = oRequest.request()    
    pattern = 'Genre.*?</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showYears(entryUrl=False):
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48
    sHtmlContent = oRequest.request() 
    pattern = 'Release.*?</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6
    sHtmlContent = oRequest.request()
    pattern = 'item__link.*?href="([^"]+).*?<img src="([^"]+).*?alt="([^"]+).*?(.*?)</span>\s+<span>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sThumbnail, sName, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        sLanguage = cConfig().getSetting('prefLanguage')
        if (sLanguage == '1' and 'English*' in sName):
            continue
        if (sLanguage == '2' and not 'English*' in sName): 
            continue
        elif sLanguage == '3':
            cGui().showLanguage()
            continue
        isQuality, sQuality = cParser.parseSingleResult(sDummy, 'movie-item__label">([^<]+)')
        isInfoEpisode, sInfoEpisode = cParser.parseSingleResult(sDummy, 'ep-num">e.([\d]+)') 
        isYear, sYear = cParser.parseSingleResult(sDummy, 'meta ws-nowrap">\s+<span>([\d]+)')
        isTvshow, aResult = cParser.parse(sName, '\s+-\s+Staffel\s+\d+')
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        if sThumbnail[0] == '/':
            sThumbnail = sThumbnail[1:]
        oGuiElement.setThumbnail(URL_MAIN + sThumbnail)
        if isQuality:
            oGuiElement.setQuality(sQuality)
        if isInfoEpisode:
            oGuiElement.setInfo(sInfoEpisode + ' Episoden')
        if isYear:
            oGuiElement.setYear(sYear)
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        params.setParam('entryUrl', sUrl)
        params.setParam('sName', sName)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'class="pagination.*?<span>[^>]</span>\s<a\shref="([^"]+)')
        if not isMatchNextPage:
            isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'class="pagination.*?<span>[^>][^>]</span>\s<a\shref="([^"]+)')
        if not isMatchNextPage:
            isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, 'class="pagination.*?<span>[^>][^>][^>]</span>\s<a\shref="([^"]+)')
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="pagination(.*?)</main>')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer,'<span>([\d]+)</span>.*?href="([^"]+).*?nav_ext">.*?">([\d]+)')
            for sPageActive, sNextPage, sPageLast in aResult:
                sPageName = cConfig().getLocalizedString(30284) + str(sPageActive) + cConfig().getLocalizedString(30285) + str(sPageLast) + cConfig().getLocalizedString(30286)
                params.setParam('sNextPage', sNextPage)
                params.setParam('sPageLast', sPageLast)
                oGui.searchNextPage(sPageName, SITE_IDENTIFIER, 'showSearchPage', params)
        if isMatchNextPage:
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  
    sHtmlContent = oRequest.request()
    isMatch, aResult = cParser.parse(sHtmlContent, '"><a href="#">([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '"description"[^>]content="([^"]+)')
    total = len(aResult)
    for sName in aResult:
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setThumbnail(URL_MAIN + sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        oGuiElement.setMediaType('episode')
        params.setParam('entryUrl', entryUrl)
        params.setParam('episode', sName)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    if ParameterHandler().exist('episode'):
        episode = ParameterHandler().getValue('episode')
        pattern = '>{0}<.*?</ul></li>'.format(episode)
        isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
    isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+)')
    if isMatch:
        sQuality = '720'
        for sUrl in aResult:
            sName = cParser.urlparse(sUrl).split('.')[0].strip()
            if cConfig().isBlockedHoster(sName)[0]: continue 
            if 'youtube' in sUrl:
                continue
            elif 'vod' in sUrl:
                continue
            elif sUrl.startswith('//'):
                sUrl = 'https:' + sUrl
            hoster = {'link': sUrl, 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality, 'resolveable': True}
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



def showSearchPage(): 
    params = ParameterHandler()
    sNextPage = params.getValue('sNextPage')
    sPageLast = params.getValue('sPageLast')
    sHeading = cConfig().getLocalizedString(30282) + str(sPageLast)
    sSearchPageText = cGui().showKeyBoard(sHeading=sHeading)
    if not sSearchPageText: return
    sNextSearchPage = sNextPage.split('page/')[0].strip() + 'page/' + sSearchPageText + '/'
    showEntries(sNextSearchPage)
    cGui().setEndOfDirectory()