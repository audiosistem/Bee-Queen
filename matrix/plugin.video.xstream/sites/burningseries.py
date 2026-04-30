# -*- coding: utf-8 -*-
# Python 3

# Always pay attention to the translations in the menu!

# HTML LangzeitCache hinzugefügt
# showValue:     24 Stunden
# showAllSeries: 24 Stunden
# showEpisodes:   24 Stunden
# SSsearch:      24 Stunden


import json
import locale

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from resources.lib.captcha.captcha_helper import solve_recaptcha, extract_recaptcha_sitekey


SITE_IDENTIFIER = 'burningseries'
SITE_NAME = 'BurningSeries'
SITE_ICON = 'burningseries.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

if cConfig().getSetting('2captcha.pass') == '':
    cConfig().setSetting('plugin_burningseries', 'false')
    cConfig().setSetting('global_search_burningseries', 'false')
    cConfig().setSetting('plugin_burningseries_checkDomain', 'false')
    logger.info('-> [SitePlugin]: 2Captcha API Key not set')

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'bs.to') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_LOGIN = ''
URL_MAIN = 'https://' + DOMAIN
REFERER = 'https://' + DOMAIN
URL_SERIES = URL_MAIN + '/andere-serien'
URL_NEW_SERIES = URL_MAIN + '/'
URL_NEW_EPISODES = URL_MAIN + '/'
URL_POPULAR = URL_MAIN + '/vorgeschlagene-serien'
URL_ALPHABET = URL_MAIN + '/serie-alphabet'
URL_GENRES = URL_MAIN + '/serie-genre'

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    params.setParam('sUrl', URL_NEW_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30514), SITE_IDENTIFIER, 'showNewSeries'), params)  # New Series
    params.setParam('sUrl', URL_NEW_EPISODES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30516), SITE_IDENTIFIER, 'showNewEpisodes'), params)  # New Episodes
    # params.setParam('sUrl', URL_POPULAR)
    # cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30519), SITE_IDENTIFIER, 'showEntries'), params)  # Popular Series
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30518), SITE_IDENTIFIER, 'showAllSeries'), params)# All Series
    params.setParam('sUrl', URL_ALPHABET)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30517), SITE_IDENTIFIER, 'showValue'), params)    # From A-Z
    params.setParam('sUrl', URL_GENRES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)    # Genre
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
    cGui().setEndOfDirectory()

def showValue():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')

    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()

    pattern = r'<div class="genre">\s*<span><strong>([^<]+)</strong></span>'
    isMatch, aGenre = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    for sName in aGenre:
        params.setParam('sGenre', sName.strip())
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    sGenre = params.getValue('sGenre')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()

    genre_div_pattern = rf'<div class="genre">\s*<span><strong>{sGenre}</strong></span>\s*<ul>(.*?)</ul>'
    isMatchGenre, aResultGenre = cParser.parseSingleResult(sHtmlContent, genre_div_pattern)
    if not isMatchGenre:
        if not sGui: oGui.showInfo()
        return

    pattern = r'<a[^>]+href="(serie/[^"]+)"[^>]+title="([^"]+)"'
    isMatch, aResult = cParser.parse(aResultGenre, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return
    total = len(aResult)
    sst = sSearchText.lower() if sSearchText else ''
    for sUrl, sName in aResult:
        sNameLow = sName.lower()
        if sSearchText and not sst in sNameLow and not cUtil.isSimilarByToken(sst, sNameLow):
            continue
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        params.setParam('sUrl', URL_MAIN + '/' + sUrl)
        params.setParam('TVShowTitle', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showAllSeries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()

    #logger.info('BurningSeries: showAllSeries: entryUrl request done: %s, sSearchText: %s' % (entryUrl, sSearchText))

    # pattern = '<a[^>]*href="(serie\\/[^"]*)"\\stitle="(.*?)"[^>]*>.*</a>' # Original Pattern funktioniert
    # Optimiertes Pattern: weniger Backtracking, keine unnötigen Gruppen, kein .* am Ende
    # Ursprünglich: pattern = '<a[^>]*href="(serie\/[^"]*)"[^>]*title="([^"]*)"'
    # Optimiert:
    pattern = r'<a[^>]+href="(serie/[^"]+)"[^>]+title="([^"]+)"'

    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    # Sort entries alphabetically by name (second tuple element)
    # A locale aware sorting is used to get better results for e.g. german umlauts
    locale.setlocale(locale.LC_COLLATE, '')  # use system locale settings
    aResult = sorted(aResult, key=lambda x: locale.strxfrm(x[1].lower()))

    total = len(aResult)
    sst = sSearchText.lower() if sSearchText else ''
    for sUrl, sName in aResult:
        sNameLow = sName.lower()
        if sSearchText and not sst in sNameLow and not cUtil.isSimilarByToken(sst, sNameLow):
            continue
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        params.setParam('sUrl', URL_MAIN + '/' + sUrl)
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
    sHtmlContent = oRequest.request()
    sectionPattern = r'<section[^>]*id="newest_episodes"[^>]*>.*?<ul[^>]*>(.*?)</ul>.*?</section>'
    isMatch, aResult = cParser.parseSingleResult(sHtmlContent, sectionPattern)

    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    isEpisodesMatch, aEpisodes = cParser.parse(aResult, r'<li[^>]*>\s*<a href="([^"]+)"[^>]*class="title"[^>]*>([^<]+)</a>\s*<div class="info">([^<]+)<i[^>]*title="([^"]+)"[^>]*></i></div>\s*</li>')

    if not isEpisodesMatch:
        if not sGui: oGui.showInfo()
        return
    total = len(aEpisodes)
    for sUrl, sName, sInfo, sLang in aEpisodes:
        sMovieTitle = sName + ' ' + sInfo + ' (' + sLang + ')'
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        oGuiElement.setTitle(sMovieTitle)
        params.setParam('sUrl', URL_MAIN + '/' + sUrl)
        params.setParam('TVShowTitle', sMovieTitle)

        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showNewSeries(entryUrl=False, sGui=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl:
        entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()

    pattern = r'<section[^>]*id="newest_series"[^>]*>.*?<ul[^>]*>(.*?)</ul>.*?</section>'
    isMatch, aResult = cParser.parseSingleResult(sHtmlContent, pattern)

    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    series_pattern = r'<li><a href="([^"]+)">([^<]+)</a></li>'
    isSeriesMatch, aSeriesResult = cParser.parse(aResult, series_pattern)

    if not isSeriesMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aSeriesResult)
    for sUrl, sName in aSeriesResult:
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        params.setParam('sUrl', URL_MAIN + '/' + sUrl)
        params.setParam('TVShowTitle', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sTVShowTitle = params.getValue('TVShowTitle')
    oRequest = cRequestHandler(sUrl)
    sHtmlContent = oRequest.request()
    pattern = r'<li class="s(\d+)(?:\s+active)?"><a href="([^"]+)">([^<]+)</a></li>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, r'<div id="sp_left">.*?<p>(.*?)</p>')
    isThumbnail, sThumbnail = cParser.parseSingleResult(sHtmlContent, r'<div id="sp_right"[^>]*>.*?<img[^>]*src="([^"]+)"')
    if isThumbnail and sThumbnail.startswith('/'):
        sThumbnail = URL_MAIN + sThumbnail

    total = len(aResult)
    for sNr, sUrl, sName in aResult:
        isMovie = sNr.startswith('0')
        oGuiElement = cGuiElement('Staffel ' + sName, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        if isThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        if not isMovie:
            oGuiElement.setTVShowTitle(sTVShowTitle)
            oGuiElement.setSeason(sNr)
            params.setParam('sSeason', sNr)
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('sUrl', URL_MAIN + '/' + sUrl)
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
        sSeason = '1'
    isMovieList = sUrl.endswith('filme')
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24  # HTML Cache Zeit 24 Stunden
    sHtmlContent = oRequest.request()
    pattern = r'<tr[^>]*>\s*<td><a href="([^"]+)" title="([^"]+)">(\d+)</a></td>\s*<td>.*?<a href="([^"]+)" title="([^"]+)">.*?</td>\s*<td>(.*?)</td>\s*</tr>'
    isMatch, sEpisodes = cParser.parse(sHtmlContent, pattern)

    if not isMatch:
        logger.error('BurningSeries: showEpisodes: No episodes found for URL: %s' % sUrl)
        cGui().showInfo()
        return

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, r'<div id="sp_left">.*?<p>(.*?)</p>')
    total = len(sEpisodes)
    for eLink, eTitle, sNumber, eLink2, eTitle2, eHosterContent in sEpisodes:
        sName = sNumber + ' - ' + eTitle
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')
        oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        if not isMovieList:
            oGuiElement.setSeason(sSeason)
            oGuiElement.setEpisode(int(sNumber))
            oGuiElement.setTVShowTitle(sTVShowTitle)
        params.setParam('sUrl', URL_MAIN + '/' + eLink2)
        params.setParam('entryUrl', sUrl)
        params.setParam('eHosterContent', eHosterContent)
        cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('sUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()

    hosterTabspattern = r'<ul class="hoster-tabs[^"]*"[^>]*>(.*?)</ul>'
    hosterPattern = r'<a[^>]*href="([^"]+)"[^>]*>(?:.*?<i[^>]*></i>)?([^<]+)</a>';
    #languagesPattern = 'itemprop="keywords".content=".*?Season...([^"]+).S.*?' # HD Kennzeichen

    # TODO: Sprachauswahl

    # data-lang-key="1" Deutsch
    # data-lang-key="2" Englisch
    # data-lang-key="3" Englisch mit deutschen Untertitel

    isMatchHosterTabs, rHosterTabs = cParser.parseSingleResult(sHtmlContent, hosterTabspattern)
    if not isMatchHosterTabs:
        cGui().showInfo()
        return
    # isMatchLang, aResult2 = cParser.parseSingleResult(sHtmlContent, languagesPattern)
    isMatch, aResult = cParser.parse(rHosterTabs, hosterPattern)
    sLang = '(DE)'
    sQuality = '720'
    if isMatch:
        for sUrl, sName in aResult:
            if cConfig().isBlockedHoster(sName)[0]: continue # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
            # sLanguage = cConfig().getSetting('prefLanguage')
            sName = sName.strip()

            hoster = {'link': [sUrl, sName], 'name': sName, 'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLang, sQuality), 'quality': sQuality, 'languageCode': sLang} # Language Code für hoster.py Sprache Prio
            hosters.append(hoster)
        if hosters:
            hosters.append('getHosterUrl')
        if not hosters:
            cGui().showLanguage()
        return hosters


def getHosterUrl(hUrl):
    if type(hUrl) == str: hUrl = eval(hUrl)

    Request = cRequestHandler(URL_MAIN + '/' + hUrl[0], caching=False)
    Request.addHeaderEntry('Referer', ParameterHandler().getValue('entryUrl'))
    Request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
    htmlContent = Request.request()
    sitekey = extract_recaptcha_sitekey(htmlContent)
    if not sitekey:
        logger.error('BurningSeries: getHosterUrl: No sitekey found in HTML content.')
        return [{'streamUrl': '', 'resolved': False}]

    sUrl = Request.getRealUrl()

    google_captcha_token = solve_recaptcha(sitekey, sUrl)
    if not google_captcha_token:
        logger.error('BurningSeries: getHosterUrl: Failed to solve captcha.')
        return [{'streamUrl': '', 'resolved': False}]

    lIDMatch, lID = cParser.parseSingleResult(htmlContent, r'data-lid="([^"]+)"')
    securityTokenMatch, securityToken = cParser.parseSingleResult(htmlContent, r'security_token" content="([^"]+)"')

    if not lIDMatch:
        logger.error('BurningSeries: getHosterUrl: No lID found in HTML content.')
        # return None?
        return [{'streamUrl': '', 'resolved': False}]

    if not securityTokenMatch:
        logger.error('BurningSeries: getHosterUrl: No securityToken found in HTML content.')
        # return None?
        return [{'streamUrl': '', 'resolved': False}]

    responseHeader = Request.getResponseHeader()
    if hasattr(responseHeader, 'get_all'):
        setCookieHeaders = responseHeader.get_all('Set-Cookie')
    elif hasattr(responseHeader, 'getheaders'):
        setCookieHeaders = responseHeader.getheaders('Set-Cookie')
    else:
        setCookieHeaders = []

    cookie_string_parts = []

    for header in setCookieHeaders:
        name_value = header.split(";", 1)[0].strip()
        if "=" in name_value:
            cookie_string_parts.append(name_value)

    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'de-DE,de;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': URL_MAIN,
        'priority': 'u=1, i',
        'referer': sUrl,
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
    }

    cookies = {}
    for part in cookie_string_parts:
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()

    data = {
        'token': securityToken,
        'LID': lID,
        'ticket': google_captcha_token
    }

    embedRequest = cRequestHandler(f'{URL_MAIN}/ajax/embed.php', caching=False, method='POST', data=data)
    for k, v in headers.items():
        embedRequest.addHeaderEntry(k, v)
    # Manually set cookies as header if needed
    if cookies:
        cookie_header = '; '.join([f"{k}={v}" for k, v in cookies.items()])
        embedRequest.addHeaderEntry('Cookie', cookie_header)
    response_text = embedRequest.request()

    parsedJson = json.loads(response_text)
    if not parsedJson or 'link' not in parsedJson:
        logger.error('BurningSeries: getHosterUrl: No result from resolve request.')
        # return None?
        return [{'streamUrl': '', 'resolved': False}]

    return [{'streamUrl': parsedJson['link'], 'resolved': False}]


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showAllSeries(URL_SERIES, oGui, sSearchText)
