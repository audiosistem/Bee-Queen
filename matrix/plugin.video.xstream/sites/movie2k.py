# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden


import re

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from json import loads

SITE_IDENTIFIER = 'movie2k'
SITE_NAME = 'Movie2K'
SITE_ICON = 'movie2k.png'

URL_MAIN = 'https://movie2k.ch/data/browse/?lang=%s&type=%s&order_by=%s&page=%s'  # lang=%s 2 = deutsch / 3 = englisch / all = Alles
URL_SEARCH = 'https://movie2k.ch/data/browse/?lang=%s&keyword=%s&page=%s&limit=0'
URL_THUMBNAIL = 'https://image.tmdb.org/t/p/w300%s'
URL_WATCH = 'https://movie2k.ch/data/watch/?_id=%s'
# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'www2.movie2k.ch') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

ORIGIN = 'https://' + DOMAIN + '/'
# ORIGIN = 'https://movie2k.at/'
REFERER = ORIGIN + '/'

#


def load():
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    sLanguage = cConfig().getSetting('prefLanguage')
    # Änderung des Sprachcodes nach voreigestellter Sprache
    if sLanguage == '0':  # prefLang Alle Sprachen
        sLang = 'all'
    if sLanguage == '1':  # prefLang Deutsch
        sLang = '2'
    if sLanguage == '2':  # prefLang Englisch
        sLang = '3'
    elif sLanguage == '3':  # prefLang Japanisch
        sLang = cGui().showLanguage()
        return
    params.setParam('sLanguage', sLang)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showMovieMenu'), params)  # Movies
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showSeriesMenu'), params)  # Series
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)  # Search
    cGui().setEndOfDirectory()


def _cleanTitle(sTitle):
    sTitle = re.sub("[\xE4]", 'ae', sTitle)
    sTitle = re.sub("[\xFC]", 'ue', sTitle)
    sTitle = re.sub("[\xF6]", 'oe', sTitle)
    sTitle = re.sub("[\xC4]", 'Ae', sTitle)
    sTitle = re.sub("[\xDC]", 'Ue', sTitle)
    sTitle = re.sub("[\xD6]", 'Oe', sTitle)
    sTitle = re.sub("[\x00-\x1F\x80-\xFF]", '', sTitle)
    return sTitle


def _getQuality(sQuality):
    isMatch, aResult = cParser.parse(sQuality, '(HDCAM|HD|WEB|BLUERAY|BRRIP|DVD|TS|SD|CAM)', 1, True)
    if isMatch:
        return aResult[0]
    else:
        return sQuality


def showMovieMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'featured', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30530), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'releases', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30531), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'trending', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30532), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'updates', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30533), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'requested', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30534), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'rating', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30535), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'votes', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30536), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'views', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30502) + cConfig().getLocalizedString(30537), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()

def showSeriesMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'releases', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30531), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'trending', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30532), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'updates', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30533), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'requested', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30534), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'rating', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30535), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'votes', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30536), SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'views', '1'))
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511) + cConfig().getLocalizedString(30537), SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    isTvshow = False
    sThumbnail = ''
    sLanguage = params.getValue('sLanguage')
    if not entryUrl: entryUrl = params.getValue('sUrl')
    try:
        oRequest = cRequestHandler(entryUrl)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 6  # HTML Cache Zeit 6 Stunden
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        sJson = oRequest.request()
        aJson = loads(sJson)
    except:
        if not sGui: oGui.showInfo()
        return

    if 'movies' not in aJson or not isinstance(aJson.get('movies'), list) or len(aJson['movies']) == 0:
        if not sGui: oGui.showInfo()
        return

    total = 0
    # ignore movies which does not contain any streams
    for movie in aJson['movies']:
        if '_id' in movie:
            total += 1
    for movie in aJson['movies']:
        if not '_id' in movie:
            continue
        sTitle = str(movie['title'])
        if sSearchText and not cParser.search(sSearchText, sTitle):
            continue
        if 'Staffel' in sTitle or 'Season' in sTitle:
            isTvshow = True
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        if 'poster_path_season' in movie and movie['poster_path_season']:
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path_season'])
        elif 'poster_path' in movie and movie['poster_path']:
            sThumbnail = URL_THUMBNAIL % str(movie['poster_path'])
        elif 'backdrop_path' in movie and movie['backdrop_path']:
            sThumbnail = URL_THUMBNAIL % str(movie['backdrop_path'])
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        if 'storyline' in movie:
            oGuiElement.setDescription(str(movie['storyline']))
        elif 'overview' in movie:
            oGuiElement.setDescription(str(movie['overview']))
        if 'year' in movie and len(str(movie['year'])) == 4:
            oGuiElement.setYear(movie['year'])
        if 'quality' in movie:
            oGuiElement.setQuality(_getQuality(movie['quality']))
        if 'rating' in movie:
            oGuiElement.addItemValue('rating', movie['rating'])
        if 'lang' in movie:
            if (sLanguage != '1' and movie['lang'] == 2):  # Deutsch
                oGuiElement.setLanguage('DE')
            if (sLanguage != '2' and movie['lang'] == 3):  # Englisch
                oGuiElement.setLanguage('EN')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        if 'runtime' in movie:
            isMatch, sRuntime = cParser.parseSingleResult(movie['runtime'], '\d+')
            if isMatch:
                oGuiElement.addItemValue('duration', sRuntime)
        params.setParam('entryUrl', URL_WATCH % str(movie['_id']))
        params.setParam('sName', sTitle)
        params.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, params, isTvshow, total)

    if not sGui and not sSearchText:
        curPage = aJson['pager']['currentPage']
        if curPage < aJson['pager']['totalPages']:
            sNextUrl = entryUrl.replace('page=' + str(curPage), 'page=' + str(curPage + 1))
            params.setParam('sUrl', sNextUrl)
            oGui.addNextPage(SITE_IDENTIFIER, 'showEntries', params)
        oGui.setView('tvshows' if isTvshow else 'movies')
        oGui.setEndOfDirectory()


def showEpisodes():
    aEpisodes = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue("sThumbnail")
    try:
        oRequest = cRequestHandler(sUrl)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 4  # HTML Cache Zeit 4 Stunden
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        sJson = oRequest.request()
        aJson = loads(sJson)
    except:
        cGui().showInfo()
        return

    if 'streams' not in aJson or len(aJson['streams']) == 0:
        cGui().showInfo()
        return

    for stream in aJson['streams']:
        if 'e' in stream:
            aEpisodes.append(int(stream['e']))
    if aEpisodes:
        aEpisodesSorted = set(aEpisodes)
        total = len(aEpisodesSorted)
        for sEpisode in aEpisodesSorted:
            oGuiElement = cGuiElement('Episode ' + str(sEpisode), SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setThumbnail(sThumbnail)
            if 's' in aJson:
                oGuiElement.setSeason(aJson['s'])
            oGuiElement.setTVShowTitle('Episode ' + str(sEpisode))
            oGuiElement.setEpisode(sEpisode)
            oGuiElement.setMediaType('episode')
            cGui().addFolder(oGuiElement, params, False, total)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    params = ParameterHandler()
    sUrl = params.getValue('entryUrl')
    sEpisode = params.getValue('episode')
    try:
        oRequest = cRequestHandler(sUrl, caching=False)
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        sJson = oRequest.request()
    except:
        return hosters
    if sJson:
        aJson = loads(sJson)
        if 'streams' in aJson:
            i = 0
            for stream in aJson['streams']:
                if (('e' not in stream) or (str(sEpisode) == str(stream['e']))):
                    sHoster = str(i) + ':'
                    isMatch, aName = cParser.parse(stream['stream'], '//([^/]+)/')
                    if isMatch:
                        sName = aName[0][:aName[0].rindex('.')]
                        if cConfig().isBlockedHoster(sName)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                        sHoster = sHoster + ' ' + sName
                    if 'release' in stream and str(stream['release']) != '':
                        sHoster = sHoster + ' [I][' + _getQuality(stream['release']) + '][/I]'
                    hoster = {'link': stream['stream'], 'name': sHoster}
                    hosters.append(hoster)
                    i += 1
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
    params = ParameterHandler()
    sLanguage = cConfig().getSetting('prefLanguage')
    if sLanguage == '0':  # prefLang Alle Sprachen
        sLang = 'all'
    if sLanguage == '1':  # prefLang Deutsch
        sLang = '2'
    if sLanguage == '2':  # prefLang Englisch
        sLang = '3'
    showEntries(URL_SEARCH % (sLang, cParser.quotePlus(sSearchText), '1'), oGui, sSearchText)