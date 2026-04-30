# -*- coding: utf-8 -*-

# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEntries:    6 Stunden
# showEpisodes:   4 Stunden

import re
import xbmcgui
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from json import loads
from datetime import datetime

# Globale Variable für die JSON-Daten
apiJson = None

# Domain Abfrage ###

SITE_NAME = 'API Suchmaschine'
SITE_ICON = 'api.png'
SITE_IDENTIFIER = 'api_all'

DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'kinokiste.eu')
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht
ORIGIN = 'https://' + DOMAIN + '/'
REFERER = ORIGIN + '/'

URL_API = 'https://' + DOMAIN
URL_MAIN = URL_API + '/data/browse/?lang=%s&type=%s&order_by=%s&page=%s'
URL_SEARCH = URL_API + '/data/browse/?lang=%s&order_by=%s&page=%s&limit=0'
URL_THUMBNAIL = 'https://image.tmdb.org/t/p/w300%s'
URL_WATCH = URL_API + '/data/watch/?_id=%s'

URL_GENRE = URL_API + '/data/browse/?lang=%s&type=%s&order_by=%s&genre=%s&page=%s'
URL_CAST = URL_API + '/data/browse/?lang=%s&type=%s&order_by=%s&cast=%s&page=%s'
URL_YEAR = URL_API + '/data/browse/?lang=%s&type=%s&order_by=%s&year=%s&page=%s'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)


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
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30551), SITE_IDENTIFIER, 'showGenreMMenu'), params)  # Movies Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showSeriesMenu'), params)  # Series
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30529), SITE_IDENTIFIER, 'showGenreSMenu'), params)  # Series Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30508), SITE_IDENTIFIER, 'showYearsMenu'), params)  # Years
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30553), SITE_IDENTIFIER, 'showSearchActor'), params)  # Cast
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


def _showGenreMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')
    sType = params.getValue('sType')
    sMenu = params.getValue('sMenu')

    if sLanguage == '2' or sLanguage == 'all':
        genres = {
            'Action': 'Action',
            'Abenteuer': 'Abenteuer',
            'Animation': 'Animation',
            'Biographie': 'Biographie',
            'Dokumentation': 'Dokumentation',
            'Drama': 'Drama',
            'Familie': 'Familie',
            'Fantasy': 'Fantasy',
            'Geschichte': 'Geschichte',
            'Horror': 'Horror',
            'Komödie': 'Komödie',
            'Krieg': 'Krieg',
            'Krimi': 'Krimi',
            'Musik': 'Musik',
            'Mystery': 'Mystery',
            'Romantik': 'Romantik',
            'Reality-TV': 'Reality-TV',
            'Sci-Fi': 'Sci-Fi',
            'Sports': 'Sport',
            'Thriller': 'Thriller',
            'Western': 'Western'
        }
    else:
        genres = {
            'Action': 'Action',
            'Adventure': 'Abenteuer',
            'Animation': 'Animation',
            'Biography': 'Biographie',
            'Comedy': 'Komödie',
            'Crime': 'Krimi',
            'Documentation': 'Dokumentation',
            'Drama': 'Drama',
            'Family': 'Familie',
            'Fantasy': 'Fantasy',
            'History': 'Geschichte',
            'Horror': 'Horror',
            'Music': 'Musik',
            'Mystery': 'Mystery',
            'Romance': 'Romantik',
            'Reality-TV': 'Reality-TV',
            'Sci-Fi': 'Sci-Fi',
            'Sports': 'Sport',
            'Thriller': 'Thriller',
            'War': 'Krieg',
            'Western': 'Western'
        }

    for genre, searchGenre in genres.items():
        params.setParam('sUrl', URL_GENRE % (sLanguage, sType, sMenu, searchGenre, '1'))
        cGui().addFolder(cGuiElement(genre, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showMovieMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'Trending', '1')) ### Trending Filme trending1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30521), SITE_IDENTIFIER, 'showEntries'), params) ### Trending Filme trending1

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'new', '1')) ### neue filme neu1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30541), SITE_IDENTIFIER, 'showEntries'), params) ### neue filme neu1

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'views', '1')) ### Views filme views1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30552), SITE_IDENTIFIER, 'showEntries'), params) ### Views filme views1

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'rating', '1')) ### Rating Filme rating1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30510), SITE_IDENTIFIER, 'showEntries'), params) ### Rating Filme rating1

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'votes', '1')) ### votes filme votes 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30536), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'updates', '1')) ### updates filme updates 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30533), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'name', '1')) ### name filme
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30517), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'featured', '1')) ### featured filme features1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30530), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'requested', '1')) ### requested filme
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30534), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'movies', 'releases', '1')) ### releases filme
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30531), SITE_IDENTIFIER, 'showEntries'), params) ### Filme releases 1
    cGui().setEndOfDirectory()


def showGenreMMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    params.setParam('sType', 'movies')
    params.setParam('sMenu', 'Trending')
    cGui().addFolder(cGuiElement('Genre trending', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Neu')
    cGui().addFolder(cGuiElement('Genre new', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Views')
    cGui().addFolder(cGuiElement('Genre viewed', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Votes')
    cGui().addFolder(cGuiElement('Genre voted', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Updates')
    cGui().addFolder(cGuiElement('Genre updated', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Rating')
    cGui().addFolder(cGuiElement('Genre rated', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Name')
    cGui().addFolder(cGuiElement('Genre named', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'requested')
    cGui().addFolder(cGuiElement('Genre requested', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'featured')
    cGui().addFolder(cGuiElement('Genre featured', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'releases')
    cGui().addFolder(cGuiElement('Genre released', SITE_IDENTIFIER, '_showGenreMenu'), params)
    cGui().setEndOfDirectory()


# Serienmenue
def showSeriesMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'neu', '1')) ### serien neu 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30514), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'views', '1')) ### serien views 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30537), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'votes', '1')) ### serien votes 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30519), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'updates', '1')) ### serien updates 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30533), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'name', '1')) ### serien name 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30517), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'featured', '1')) ###
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30530), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'requested', '1')) ### serien requested
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30534), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'releases', '1')) ### serien releases 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30531), SITE_IDENTIFIER, 'showEntries'), params) ###

    params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'rating', '1')) ### serien rating 1
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30535), SITE_IDENTIFIER, 'showEntries'), params) ###

    #params.setParam('sUrl', URL_MAIN % (sLanguage, 'tvseries', 'Jahr', '1'))  # ##
    #cGui().addFolder(cGuiElement('Jahr', SITE_IDENTIFIER, 'showEntries'), params) ##

    #params.setParam('sCont', 'Jahr') #
    #cGui().addFolder(cGuiElement('Jahr', SITE_IDENTIFIER, 'showValue'), params), params) #
    cGui().setEndOfDirectory()


# show genre serien menue
def showGenreSMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    params.setParam('sType', 'tvseries')
    params.setParam('sMenu', 'Trending')
    cGui().addFolder(cGuiElement('Series genre trending', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Neu')
    cGui().addFolder(cGuiElement('Series genre new', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Views')
    cGui().addFolder(cGuiElement('Series genre viewed', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Votes')
    cGui().addFolder(cGuiElement('Series genre voted', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Updates')
    cGui().addFolder(cGuiElement('Series genre updated', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Rating')
    cGui().addFolder(cGuiElement('Series genre rated', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'Name')
    cGui().addFolder(cGuiElement('Series genre named', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'requested')
    cGui().addFolder(cGuiElement('Series genre requested', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'featured')
    cGui().addFolder(cGuiElement('Series genre featured', SITE_IDENTIFIER, '_showGenreMenu'), params)
    params.setParam('sMenu', 'releases')
    cGui().addFolder(cGuiElement('Series genre releases', SITE_IDENTIFIER, '_showGenreMenu'), params)

    cGui().setEndOfDirectory()


def showYearsMenu():
    params = ParameterHandler()
    sLanguage = params.getValue('sLanguage')

    # Anfangs- und Endjahr für das menü eintragen
    start_jahr = 1931
    end_jahr = datetime.now().year

    # show the current year first
    for jahr in range(end_jahr, start_jahr - 1, -1):
        params.setParam('sUrl', URL_YEAR % (sLanguage, 'movies', 'new', str(jahr), '1'))
        cGui().addFolder(cGuiElement(str(jahr), SITE_IDENTIFIER, 'showEntries'), params)

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
        oRequest = cRequestHandler(sUrl)
        if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
            oRequest.cacheTime = 60 * 60 * 8  # HTML Cache Zeit 8 Stunden
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
#                        sName = cParser.urlparse(sUrl) ### angezeigter hostername api
                        
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


def showSearchActor():
    sName = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30280))
    if not sName: return
    _searchActor(False, sName)
    cGui().setEndOfDirectory()


def _searchActor(oGui, sName):
    params = ParameterHandler()
    sLanguage = cConfig().getSetting('prefLanguage')
    if sLanguage == '0':  # prefLang Alle Sprachen
        sLang = 'all'
    if sLanguage == '1':  # prefLang Deutsch
        sLang = '2'
    if sLanguage == '2':  # prefLang Englisch
        sLang = '3'
    showEntries(URL_CAST % (sLanguage, 'movies', 'new', cParser.quotePlus(sName), '1'), oGui)


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    SSsearch(oGui, sSearchText)

    
def SSsearch(sGui=False, sSearchText=False):
    global apiJson
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    sLanguage = cConfig().getSetting('prefLanguage')
    
    # Falls die Daten noch nicht geladen wurden oder neu geladen werden sollen
    if apiJson is None or 'movies' not in apiJson:
        loadMoviesData()
        
    if 'movies' not in apiJson or not isinstance(apiJson.get('movies'), list) or len(apiJson['movies']) == 0:
        oGui.showInfo()
        return

    sst = sSearchText.lower()

    if not sGui:
        dialog = xbmcgui.DialogProgress()
        dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))

    total = len(apiJson['movies'])
    position = 0
    for movie in apiJson['movies']:
        position += 1
        if not '_id' in movie:
            continue
        if not sGui and position % 128 == 0:  # Update progress every 128 items
            if dialog.iscanceled(): break
            dialog.update(position, str(position) + cConfig().getLocalizedString(30128) + str(total))
        sTitle = movie['title']
        if 'Staffel' in sTitle or 'Season' in sTitle:
            isTvshow = True
            sSearch = sTitle.rsplit('-', 1)[0].replace(' ', '').lower()
        else:
            isTvshow = False
            sSearch = sTitle.lower()
        if not sst in sSearch and not cUtil.isSimilarByToken(sst, sSearch):
            continue
        #logger.info('-> [DEBUG]: %s' % str(movie))
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showEpisodes' if isTvshow else 'showHosters')
        sThumbnail = ''
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
    if not sGui:
        dialog.close()

def loadMoviesData():
    global apiJson
    sLanguage = cConfig().getSetting('prefLanguage')
    if sLanguage == '0':  # prefLang Alle Sprachen
        sLang = 'all'
    if sLanguage == '1':  # prefLang Deutsch
        sLang = '2'
    if sLanguage == '2':  # prefLang Englisch
        sLang = '3'
    
    try:
        oRequest = cRequestHandler(URL_SEARCH % (sLang, 'new', '1'), caching=True)
        oRequest.addHeaderEntry('Referer', REFERER)
        oRequest.addHeaderEntry('Origin', ORIGIN)
        oRequest.cacheTime = 60 * 60 * 48  # HTML Cache Zeit 2 Tage
        sJson = oRequest.request()
        apiJson = loads(sJson)
        logger.info('API-Daten erfolgreich geladen')
    except:
        logger.error('Fehler beim Laden der API-Daten')
        apiJson = {'movies': []}
        

# Daten beim Import des Moduls laden
loadMoviesData()