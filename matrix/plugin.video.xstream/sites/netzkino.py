# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showEntries:      6 Stunden
# showEntriesUnJson:6 Stunden


import json

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui

SITE_IDENTIFIER = 'netzkino'
SITE_NAME = 'NetzKino'
SITE_ICON = 'netzkino.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain', 'www.netzkino.de') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://api.netzkino.de.simplecache.net/capi-2.0a/categories/%s.json?d=www&l=de-DE'
URL_SEARCH = 'https://api.netzkino.de.simplecache.net/capi-2.0a/search?q=%s&d=www&l=de-DE'
URL_START = 'https://' + DOMAIN + '/category/%s'

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    oGui = cGui()
    params = ParameterHandler()
    cGui().addFolder(cGuiElement('Startseite', SITE_IDENTIFIER, 'showStart'), params)  # Startseite
    oGui.addFolder(cGuiElement('Genres', SITE_IDENTIFIER, 'showGenreMenu'))
    params.setParam('sUrl', URL_START % 'themenkino-genre')
    oGui.addFolder(cGuiElement('Themenkino', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    oGui.addFolder(cGuiElement('Suche', SITE_IDENTIFIER, 'showSearch'), params)
    oGui.setEndOfDirectory()


def showStart():
    params = ParameterHandler()
    params.setParam('sUrl', URL_MAIN % 'highlights-frontpage')
    cGui().addFolder(cGuiElement('Highlights', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'neu-frontpage')
    cGui().addFolder(cGuiElement('Neu bei Netzkino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'blockbuster-kultfilme-frontpage')
    params.setParam('sUrl', URL_START % 'actionfilme_frontpage')
    cGui().addFolder(cGuiElement('Actionfilme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'top-rated-imdb_frontpage')
    cGui().addFolder(cGuiElement('Top Rated IMDb', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_MAIN % 'blockbuster-kultfilme-frontpage')
    cGui().addFolder(cGuiElement('Blockbuster & Kultfilme', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_START % 'kriegsfilme-frontpage')
    cGui().addFolder(cGuiElement('Beliebte Kriegsfilme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_MAIN % 'meisgesehene_filme-frontpage')
    cGui().addFolder(cGuiElement('Meistgesehene Filme', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_START % 'top-dokumentationen')
    cGui().addFolder(cGuiElement('Top Dokumentationen', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'horrortime_frontpage')
    cGui().addFolder(cGuiElement('Horrortime', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Thriller-frontpage')
    cGui().addFolder(cGuiElement('Thriller', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_MAIN % 'komodien-frontpage')
    cGui().addFolder(cGuiElement('Komödien', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_START % 'Zombiefilme-frontpage')
    cGui().addFolder(cGuiElement('Zombiefilme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Hollywood-Filme-frontpage')
    cGui().addFolder(cGuiElement('Hollywood Filme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_MAIN % 'beste-bewertung-frontpage')
    cGui().addFolder(cGuiElement('Beste Bewertung', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'mockbuster-frontpage')
    cGui().addFolder(cGuiElement('Mockbuster', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'frontpage-exklusiv-frontpage')
    cGui().addFolder(cGuiElement('Die schönsten Märchen', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'empfehlungen_woche-frontpage')
    cGui().addFolder(cGuiElement('Unsere Empfehlungen der Woche', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'filme_mit_auszeichnungen-frontpage')
    cGui().addFolder(cGuiElement('Filme mit Auszeichnungen', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'top-20-frontpage')
    cGui().addFolder(cGuiElement('Top 20 - Action Classics', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_START % 'science-fiction-fantasy_frontpage')
    cGui().addFolder(cGuiElement('Science Fiction & Fantasy', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Familienfilme-frontpage')
    cGui().addFolder(cGuiElement('Familienfilme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'must-see-frontpage')
    cGui().addFolder(cGuiElement('Must-See', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Deutsche-Filme-frontpage')
    cGui().addFolder(cGuiElement('Deutsche Filme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Drama-frontpage')
    cGui().addFolder(cGuiElement('Die besten Drama-Filme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'western-frontpage')
    cGui().addFolder(cGuiElement('Western', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Independent-Filme-frontpage')
    cGui().addFolder(cGuiElement('Independent-Filme', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'history-dokus-frontpage')
    cGui().addFolder(cGuiElement('History Dokus', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Action-Abenteuer-frontpage')
    cGui().addFolder(cGuiElement('Action & Abenteuer', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % 'Romantic-Comedies-frontpage')
    cGui().addFolder(cGuiElement('Romantic Comedies', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    params.setParam('sUrl', URL_START % '90er-Jahre-frontpage')
    cGui().addFolder(cGuiElement('Die besten Filme der 90er Jahre', SITE_IDENTIFIER, 'showEntriesUnJson'), params)
    cGui().setEndOfDirectory()


def showGenreMenu():
    oGui = cGui()
    params = ParameterHandler()
    params.setParam('sUrl', URL_MAIN % 'actionkino')
    oGui.addFolder(cGuiElement('Actionkino', SITE_IDENTIFIER, 'showEntries'), params)
    #params.setParam('sUrl', URL_MAIN % 'animekino')
    #oGui.addFolder(cGuiElement('Animekino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'arthousekino')
    oGui.addFolder(cGuiElement('Arthousekino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'asiakino')
    oGui.addFolder(cGuiElement('Asiakino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'dramakino')
    oGui.addFolder(cGuiElement('Dramakino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'thrillerkino')
    oGui.addFolder(cGuiElement('Thrillerkino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'liebesfilmkino')
    oGui.addFolder(cGuiElement('Liebesfilmkino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'scifikino')
    oGui.addFolder(cGuiElement('Scifikino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'kinderkino')
    oGui.addFolder(cGuiElement('Kinderkino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'spasskino')
    oGui.addFolder(cGuiElement('Spasskino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'horrorkino')
    oGui.addFolder(cGuiElement('Horrorkino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'thrillerkino')
    oGui.addFolder(cGuiElement('Thrillerkino', SITE_IDENTIFIER, 'showEntries'), params)
    params.setParam('sUrl', URL_MAIN % 'kinoab18')
    oGui.addFolder(cGuiElement('Kino ab 18', SITE_IDENTIFIER, 'showEntries'), params)
    oGui.setEndOfDirectory()

def showEntries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=sGui is not False)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    jSearch = json.loads(oRequest.request())  # Lade JSON aus dem Request der URL
    if not jSearch: return  # # Wenn Suche erfolglos - Abbruch

    if 'posts' not in jSearch or len(jSearch['posts']) == 0:
        if not sGui: oGui.showInfo()
        return

    total = len(jSearch['posts'])
    for item in jSearch['posts']:
        try:
            if sSearchText and not cParser.search(sSearchText, item['title']):
                continue
            oGuiElement = cGuiElement(str(item['title']), SITE_IDENTIFIER, 'showHosters')
            oGuiElement.setThumbnail(str(item['thumbnail']))
            oGuiElement.setDescription(str(item['content']))
            oGuiElement.setFanart(str(item['custom_fields']['featured_img_all'][0]))
            oGuiElement.setYear(str(item['custom_fields']['Jahr'][0]))
            oGuiElement.setQuality(str(item['custom_fields']['Adaptives_Streaming'][0]))
            oGuiElement.setMediaType('movie')
            if 'Duration' in item['custom_fields'] and item['custom_fields']['Duration'][0]:
                oGuiElement.addItemValue('duration', item['custom_fields']['Duration'][0])
            urls = ''
            if 'Streaming' in item['custom_fields'] and item['custom_fields']['Streaming'][0]:                                  
                urls += 'https://pmd.netzkino-seite.netzkino.de/%s.mp4' % item['custom_fields']['Streaming'][0]
            if 'Youtube_Delivery_Id' in item['custom_fields'] and item['custom_fields']['Youtube_Delivery_Id'][0]:
                urls += '#' + 'plugin://plugin.video.youtube/play/?video_id=%s' % item['custom_fields']['Youtube_Delivery_Id'][0]
            params.setParam('entryUrl', urls)
            oGui.addFolder(oGuiElement, params, False, total)
        except:
            continue

    if not sGui:
        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showEntriesUnJson(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    sHtmlContent = oRequest.request()
    #Aufbau pattern
    #'item":.*?'  # Container Start
    #'image.*?(https[^"]+).*?'  # Image
    #'name":\s.*?([^"]+).*?'  # Name
    #'url":\s.*?([^"]+).*?'  # URL
    #'(.*?)}'  # Dummy
    pattern = 'item":.*?image.*?(https[^"]+).*?name":\s.*?([^"]+).*?url":\s.*?([^"]+).*?(.*?)}'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)

    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sThumbnail, sName, sUrl, sDummy in aResult:
        try:
            if sSearchText and not cParser.search(sSearchText, sName):
                continue
            isDuration, sDurationH = cParser.parseSingleResult(sDummy, 'duration":\s"([\d]+).*?')  # Laufzeit Stunden
            isDuration, sDurationM = cParser.parseSingleResult(sDummy, 'H([\d]+).*?')  # Laufzeit Minuten
            oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHostersUnJson')
            oGuiElement.setThumbnail(sThumbnail)
            if isDuration:
                oGuiElement.addItemValue('duration', int(sDurationH) *60 + int(sDurationM))
            oGuiElement.setMediaType('movie')
            params.setParam('entryUrl', sUrl)
            params.setParam('sName', sName)
            params.setParam('sThumbnail', sThumbnail)
            oGui.addFolder(oGuiElement, params, False, total)
        except:
            continue
    if not sGui:
        oGui.setView('movies')
        oGui.setEndOfDirectory()


def showHosters():
    hosters = []
    URL = ParameterHandler().getValue('entryUrl')
    for sUrl in URL.split('#'):
        hoster = {'link': sUrl, 'name': 'Netzkino' if 'netzkino' in sUrl else 'Youtube', 'resolveable': True}
        hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def showHostersUnJson():
    hosters = []
    sHtmlContent = cRequestHandler(ParameterHandler().getValue('entryUrl')).request()
    isMatch, aResult = cParser.parse(sHtmlContent, 'pmdUrl":"([^"]+)')
    if isMatch:
        for sUrl in aResult:
            sName = 'Netzkino'
            sUrl = 'https://pmd.netzkino-seite.netzkino.de/' + sUrl
            hoster = {'link': sUrl, 'name': sName, 'resolveable': True}
            hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': True}]


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30287))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_SEARCH % cParser.quotePlus(sSearchText), oGui, sSearchText)
