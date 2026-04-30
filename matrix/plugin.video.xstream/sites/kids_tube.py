# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# Multi Scraper für Kinder Videos


import xbmc
import xbmcgui, sys
import requests
import random

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from resources.lib import youtube_fix

#

SITE_IDENTIFIER = 'kids_tube'
SITE_NAME = 'Kids Tube'
SITE_ICON = 'kids_tube.png'

SITE_GLOBAL_SEARCH = False
cConfig().setSetting('global_search_' + SITE_IDENTIFIER, 'false')
logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

#################### Hauptmenü ####################

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    # Abfrage ob Youtube installiert ist
    if cConfig().getSetting('plugin_' + SITE_IDENTIFIER) == 'true':
        if not xbmc.getCondVisibility('System.HasAddon(%s)' % 'plugin.video.youtube'):
            xbmc.executebuiltin('InstallAddon(%s)' % 'plugin.video.youtube')
    # Menü für Kinderserien
    logger.info('Load %s' % SITE_NAME_1)
    if params.getValue("action") is False:
        font = '[B]%s : [/B]' % SITE_NAME_1

        params.setParam('sUrl', URL_MAIN_1)
        cGui().addFolder(cGuiElement(font + cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries_1'), params)  # Neues
        params.setParam('sUrl', URL_MOVIES_1)
        cGui().addFolder(cGuiElement(font + cConfig().getLocalizedString(30502), SITE_IDENTIFIER, 'showEntries_1'), params)  # Movies
        cGui().addFolder(cGuiElement(font + cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre_1'), params) # Genre
        cGui().addFolder(cGuiElement(font + cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch_1'), params)    # Search
        main_list()
    else:
        action = params.getValue("action")
        if '#' in str(params.getValue("action")):
            action = action.split('#')[1]
            sub_listw(action)
        elif '*' in str(params.getValue("action")):
            action = action.split('*')[1]
            search(action)
        else:
            sub_list(action)
    cGui().setEndOfDirectory()

def loads():
    params = ParameterHandler()
    action = params.getValue("action")
    action2 = params.getValue("action1")
    if '#' in str(params.getValue("action1")):
        action = action2.split('#')[1]
        sub_listw(action)
    elif '*' in str(params.getValue("action1")):
        action = action2.split('*')[1]
        search(action)
    cGui().setEndOfDirectory()


#################### Kinderserien.tv ####################

SITE_NAME_1 = 'Kinderserien.tv'
SITE_ICON_1 = 'kids_tube.png'
URL_MAIN_1 = 'https://kinderserien.tv/'
URL_MOVIES_1 = URL_MAIN_1 + 'serien/kinderfilme/'
URL_SEARCH_1 = URL_MAIN_1 + '?s=%s'

def showGenre_1():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN_1)
    sHtmlContent = oRequest.request()
    pattern = 'Serien</h2>(.*?)</ul>'
    isMatch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, pattern)
    if isMatch:
        isMatch, aResult = cParser.parse(sHtmlContainer, 'href="([^"]+).*?>([^<]+)')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        if sUrl.startswith('/'):
            sUrl = URL_MAIN_1 + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries_1'), params)
    cGui().setEndOfDirectory()

def showEntries_1(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    iPage = int(params.getValue('page'))
    oRequest = cRequestHandler(entryUrl + 'page/' + str(iPage) if iPage > 0 else entryUrl, ignoreErrors=(sGui is not False))
    sHtmlContent = oRequest.request()
    pattern = 'class="item-thumbnail">.*?href="([^"]+).*?title="([^"]+).*?src="([^"]+).*?'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName, sThumbnail in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHosters_1')
        oGuiElement.setThumbnail(sThumbnail)
        params.setParam('entryUrl', sUrl)
        oGui.addFolder(oGuiElement, params, False, total)

    if not sGui and not sSearchText:
        sPageNr = int(params.getValue('page'))
        if sPageNr == 0:
            sPageNr = 2
        else:
            sPageNr += 1
        params.setParam('page', int(sPageNr))
        params.setParam('sUrl', entryUrl)
        oGui.addNextPage(SITE_IDENTIFIER, 'showEntries_1', params)
        oGui.setView('movies')
        oGui.setEndOfDirectory()

def showHosters_1():
    hosters = []
    sUrl = ParameterHandler().getValue('entryUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    isMatch, aResult = cParser.parse(sHtmlContent, 'src="([^"]+)" f')
    if isMatch:
        for sUrl in aResult:
            sUrl = sUrl.split('?')[0].strip()
            hoster = {'link': sUrl, 'name': cParser.urlparse(sUrl)}
            hosters.append(hoster)
    if hosters:
        hosters.append('getHosterUrl_1')
    return hosters

def getHosterUrl_1(sUrl=False):
    return [{'streamUrl': sUrl, 'resolved': False}]

def showSearch_1():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search_1(False, sSearchText)
    cGui().setEndOfDirectory()

def _search_1(oGui, sSearchText):
    showEntries_1(URL_SEARCH_1 % cParser.quotePlus(sSearchText), oGui, sSearchText)

#################### Youtube Kanäle ####################

URL_MAIN = 'http://www.youtube.com'

channellist = [
    ("[B]YouTube:[/B] Kanäle", "Kanäle", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Filme", "Kinder Filme", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Serien", "Kinder Serien", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Klassiker", "Kinder Klassiker", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Märchen", "Kinder Geschichten", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Hörbücher", "Kinder Buch", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Wissen", "Kinder Wissen", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ("[B]YouTube:[/B] Musik", "Kinder Musik", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
]

sublists = {
    'Kanäle': [
        ("[B]KIKA[/B] von ARD & ZDF", "user/meinKiKA", "https://yt3.googleusercontent.com/eVEM7kLayi8-pFKQ2jMVMqWMMf-Sj-LFtPD5oD5d4vctMxwa_MxvYkYQOihpO8YxHO3Fo8qHVA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]KiKANiNCHEN[/B] von ARD & ZDF", "channel/UCv4Pvhg1LY8U9E-XF8hn6WA", "https://yt3.googleusercontent.com/PHGbrL1fSJgdN-1S69zDJ7GUVuw9ypSiq8skG1GAzxcESnwCgRYwv0yhe7sTR_5VS-NwjjIxyA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]ZDFtivi[/B] von ZDF", "user/ZDFtiviKinder", "https://yt3.googleusercontent.com/IgitEsBoWmeD_xSHFMiu8nwOuGvlCSCtOzUQxSm_91VXPa1nzEOnb3lcFfrfZnpe_DWkoWEq6A=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Löwenzahn TV[/B] von ZDF", "channel/UCOPJAVJeBhqWL8k7K9Wx6SQ", "https://yt3.googleusercontent.com/ytc/AIdro_lTKpWSboFuBYXfl3EhkZow8Yot6_lnmZRk3hEnvz32nQ0=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Sesamstrasse[/B] von NDR", "user/SesamstrasseNDR", "https://yt3.googleusercontent.com/TsFEPe9IC45mP5kMx6fLabeF0vO5IGebWSp8E4AokyT3dyZwpy-3FDi8NIWFgLmBwYQkjiYLBg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kindernetz[/B] von SWR", "user/Kindernetz", "https://yt3.googleusercontent.com/vKDz1wZkfM8HNFaYN7QQQciIJq65bmVAmOt6iKDdKhmtTzW5YJ7A-HpnAZhxMC6xfQoEn_5zXw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Die Sendung mit der Maus[/B] von WDR", "channel/UCRWSxXBnz9IRS4SgRhG2wpQ", "https://yt3.ggpht.com/AB02vMc3urTNtF1fs8xC_beAkkB__S8J3cLiJpZ4vdMXLf2GOBlkd6RWkNGVqOdFjNkHmTrLaA=s176-c-k-c0x00ffffff-no-rj-mo"),
        ("[B]Toggolino[/B] von SuperRTL", "user/TOGGOLINOde", "https://yt3.googleusercontent.com/cL_dcEztZBDvVCR5K3JNE3o5K5580xSNaETJonhzE2mK1fN1UdMYsWx5rr1essWmHBbL6a_2OA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Disney Channel[/B] Deutschland", "user/DisneyChannelGermany", "https://yt3.googleusercontent.com/c3_JbPq0s5lc_pfXglSsnNTMv4T-oEK6zvmQDBFqxmAmgmKn1yDm5141NzYqudS2qhzt50fDJw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Disney Junior[/B] Deutschland", "user/DisneyJuniorGermany", "https://yt3.googleusercontent.com/lP2bAzpPZyCY_mEBPCwpCBRwHV6wc6nePDCjCuK2UoXx6uvnUpWeQ5iGxLmOpADOpFYR9jSbSJ4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Nickelodeon[/B] Deutschland", "user/nickelodeonoffiziell", "https://yt3.googleusercontent.com/mr1Sx4O0oKwfhM3kuRWGpKHU5OGIKgalPIx6HL47L_76MZUbPrCmXGxc4VEB-m_CN1X3-ZEy=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Cartoonito[/B] Deutschland", "channel/UChcDNaLm0F8GZY4fRhZEAeQ", "https://yt3.googleusercontent.com/hvStglMjagBU8hzH2Ke4PYTs05Ock_2ryEK7pwZXRNXnok9hy8UaqsqF3JAgSph9SoI7UOFcYA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Cartoon Network[/B] Deutschland", "user/cartoonnetworkde", "https://yt3.googleusercontent.com/ytc/AIdro_nXPNGVJ3K15vK1QeDT_k0_3bGTyN7dhAxNm6o0StPVtCU=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Nanoki[/B] Kinderfilme, Lehrfilme, Lernserien", "channel/UCF2IFFQyO5gbhvOCObh1WTQ", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Karussell[/B] KinderTV", "channel/UCdT-eMkUGKqvVebDkn1KqlQ", "https://yt3.googleusercontent.com/95cCyBJIjuANCB5IDAyHvang2jGlPBt_jbY__nNHOz6gFH5ErboDnmqb879peVqKnWrRX4gJxA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kinderlieder[/B] zum Mitsingen und Bewegen", "channel/UCctbi1Jw2jiVhj2ogdwiFdA", "https://yt3.googleusercontent.com/BGoTUkK-TRjC6fC1fFP700dgrV5cjuHw-O8OcgGnqsHi3RoeU7b0hKm-0eS4dDOg-PWs5lz9Ew=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kinderlieder[/B] von Volker Rosin", "channel/UC7HM-Pm3mLzZBvhJKFnL6oA", "https://yt3.googleusercontent.com/JJrATrwxWPSfcl96xTQqdKCsPoRu-szzn_NTvazvFG9Vx8aAvTHZBT_WuznsbOuiClwdTf0RXw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]KIDFLIX[/B]", "channel/UCBZZcF8BC0kvZL_-zM7yuFg", "https://yt3.googleusercontent.com/ZHa7HKjK0Dj9-bg2AlM9Udts_3bItaKWEe7aEkvmvDAf1kDFpqfcTe9a0e8-GhbkiFQd8dm1IHI=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Ric TV[/B]", "user/RICTVChannel", "https://yt3.googleusercontent.com/ytc/AIdro_llzhDC24z43QbBNVmCWEuNP_1cVflbImhBIw2_7np6Bw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Filme': [
        ("[B]Kinderfilme[/B] von Netzkino", "playlist/PLfEblejE-l3k5xxDsBiKVhdNqWAuCIYRr", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Zeichentrickfilme[/B] von Netzkino", "playlist/PLfEblejE-l3l8AwrdcuMp-p31uwBaJJXl", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Pferdefilme[/B] von Netzkino", "playlist/PLfEblejE-l3k3qM4Q1GlnGdGeRjzlZvRn", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Hundefilme[/B] von Netzkino", "playlist/PLfEblejE-l3nIBgJeAv7KO1DPvC2yN8-5", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Tennie Komödien[/B] von Netzkino", "playlist/PLfEblejE-l3kyX48AXCaOnKFLxxkasxOM", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Familienkino[/B] von Netzkino", "playlist/PLfEblejE-l3nta_dpVmIwGomgE_a3sm6g", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Weihnachtskino[/B] von Netzkino", "playlist/PLfEblejE-l3n9NKla09pwoYVLtnrL2kv3", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Kinderkino[/B] von Netzkino", "channel/UCmZUsl5MLqXIhuSTVP6x-EA", "special://home/addons/plugin.video.xstream/resources/art/sites/netzkino.png"),
        ("[B]Kinderfilme[/B] von Nanoki", "playlist/PLAroxwS0jZuS521YByzaxA6ZO5VO-ppXJ", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Zeichentrickfilme[/B] von Nanoki", "playlist/PLAroxwS0jZuQSy2pjwruhzz44-kQ0YHEh", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tierfilme[/B] von Nanoki", "playlist/PLAroxwS0jZuQQlgJJ3_-imn1abL4A4Zlc", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Hundefilme[/B] von Nanoki", "playlist/PLAroxwS0jZuQC6yoU8LJF3USzgQBlrzx5", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Familienfilme[/B] von Nanoki", "playlist/PLAroxwS0jZuQUBhbxcAUlfh9qeJGV_tom", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Weihnachtsfilme[/B] von Nanoki", "playlist/PLAroxwS0jZuTLDgN-YeW2Yy0trylROSs4", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kinderfilme Klassiker[/B] von Nanoki", "playlist/PLAroxwS0jZuQUke_UTBPvbyCB27G0NtwA", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Serien': [
        ("[B]Feuerwehrman Sam[/B]", "playlist/PLK-pDTpRfGThLNOPhnUn_442Sr3X94ehe", "https://yt3.googleusercontent.com/ofigmXJBP1ws5e5PqlNPpNTHoEjf0CuYa8Wjg4EExWxqsyB_NppwXqSIi34EQGXAiROvzry_=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Bob der Baumeister[/B]", "channel/UC1gSKVovUYLmXoDnsTY039Q", "https://yt3.googleusercontent.com/ytc/AIdro_libsJ_qNx01lsU8cqy4G3bQQJGqPQvtqZwQwWPFF0oeA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Bob der Baumeister DVD[/B]", "playlist/PLiK4BrMh3Fy8z0X2Q1nh9Ts5Uq_XVXoB1", "https://yt3.googleusercontent.com/ytc/AIdro_libsJ_qNx01lsU8cqy4G3bQQJGqPQvtqZwQwWPFF0oeA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Peppa Pig[/B]", "playlist/PLIHhW2rjlyqazX9VsDH3OB_BvXu3y2arK", "https://yt3.googleusercontent.com/ytc/AIdro_lXig6Qp5KuxzRLn4K_hmZOEzB3o9eI9bz-ALdaOP9wAg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Die Fixies[/B]", "playlist/PLMu5a51zMv6zUI7ydYUdLkwHLyAq9mlw5", "https://yt3.googleusercontent.com/bsnnz9N70ntIDrDuRaXY4KNU_WKUu94V-MuaXCdqGgsvz17Ekju_1VZRNLzLLvHwSVYi8ZZBaQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Caillou[/B]", "playlist/PLYbELRCXraUV5CxUx0VFqALe5B2NOnDM-", "https://yt3.googleusercontent.com/ytc/AIdro_l30kpdJm0Ir6rselzA8yAhAidkjxmm89coucfOyagQBw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tom der Abschleppwagen[/B]", "playlist/PLfrJ8rAzdNSWKpsTGcZGNLyjsVDiwyj90", "https://yt3.googleusercontent.com/vMiHUQlNXiHl1eJmx1-tErx29DBt4beiSPJ50e0V4MjA1O0VFPUbvIOKW2HbqiG7RKC30rATHg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Bali[/B]", "playlist/PL73AN-YruC-Ah9yKL8v09fB0nI-Ygt5I4", "https://yt3.googleusercontent.com/ytc/AIdro_kliL7apFXyhzAB7eDHAYELARqUYf0Q1NSIuU1QHJpUvQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Der kleine Nick[/B]", "channel/UCzNZ46g2SGaC66WEjxIMYag", "https://yt3.googleusercontent.com/ytc/AIdro_kMkfp1N13Gecb_TeoNizjvZq_m3qn5GEAtsOsJf3sTZQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Peter Pan[/B] Spannende Abenteuer", "playlist/PLEsSrAkc-N6rXexCXeRYvk3m69rYU6LmT", "https://yt3.googleusercontent.com/ytc/AIdro_kElXO0Ln2cwmXqZECYT3wHnAUun28MduBMkPaFni_cOQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Barbie[/B]", "channel/UCSTlH3dDtCBT94sjO2MTyww", "https://yt3.googleusercontent.com/J5l0pIYLHcZByl5o70xs_fTVx0gqxN7FSl20UKtyne_EKszZlgsYqNrmnt9oAFUhUra70on8RA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Wendy[/B] Pferde sind ihr Leben", "playlist/PLAqP3cngI26r65PV1PZbYoSc5sjMHmt2_", "https://yt3.googleusercontent.com/ytc/AIdro_kk9NKO2oocRNI-ehYC1KtIBaT06bOGBy_0lwxQY-SUVg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Justice League[/B] DC Kids", "playlist/PLWH6DXF9upwP53YyfSKaLD_XbMwwgphuB", "https://yt3.googleusercontent.com/ytc/AIdro_ny-OEqibjYRcfyTNpP0Gr7zBhthcHZRMYNrc116J4a9Q=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Benjamin Blümchen[/B] BenjaminBlümchen.tv", "playlist/PL1SAyTUFBb74hUX32r6aqasGENGL4YShb", "https://yt3.googleusercontent.com/ytc/AIdro_nxryECurSuDeK6loDsbG2inLuGas2vBWi7zMCEYh-rlmo=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Bibi Blocksberg[/B] BibiBlocksberg.tv", "playlist/PLOZg6nrLYB7-EgluZK6CuMBzJtKhvFIAU", "https://yt3.googleusercontent.com/ytc/AIdro_kaXwWIBwqekbuxe6Dhcrgw25Aywv4Ujp824KcTfD0DhxI=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Mister Bean[/B]", "playlist/PLiDbV9ObbZLV_R9ofcSdJSPP4PSrobk3g", "https://yt3.googleusercontent.com/ytc/AIdro_kU_LbBWM7nAscqjTm9cu4cxYE8U0u2nvccYpc2iIrHbg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Pink Panther[/B] 1. Klassik Serie", "playlist/PL546904B9DC923B31", "https://yt3.googleusercontent.com/ytc/AIdro_lEeZP6Urk3JhCp_BnVamf57KSdAv-ZJb2nJqHmW-8ZIuM=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Pink Panther[/B] 2. Die neue Serie", "playlist/PL2MVdpCy9PxFMwC6UaXwNOTZMPUxiU6KB", "https://yt3.googleusercontent.com/ytc/AIdro_lEeZP6Urk3JhCp_BnVamf57KSdAv-ZJb2nJqHmW-8ZIuM=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tom & Jerry[/B] 1. Klassik Serie", "playlist/PLUCHDQsTRtWb1AlJQV0_ojhg5hpLjpdC_", "https://yt3.googleusercontent.com/l3sgu7fdZPWCiwrMak7lttvETa3QwED1ezhicGLc1kI3Q2ZyKe5bb3gP8OTwKx0aMNAIMy4YXw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tom & Jerry[/B] 2. Die neue Serie", "playlist/PL2MVdpCy9PxFf_BZJfjTtNuXTBdyu1ig9", "https://yt3.googleusercontent.com/l3sgu7fdZPWCiwrMak7lttvETa3QwED1ezhicGLc1kI3Q2ZyKe5bb3gP8OTwKx0aMNAIMy4YXw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Wickie und die starken Männer[/B] 1. Klassik Serie", "playlist/PLGP11O3gIZb-CAn5df2AE687pqGLxv2hr", "https://yt3.googleusercontent.com/ytc/AIdro_kx_tPHk_DdII3m8ZTy6o9nCdp6vuGS6lC9zvZBcXrciCI=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Wickie und die starken Männer[/B] 2. Die neue Serie", "playlist/PLGP11O3gIZb8jsxU_InVjehKgJy1Z1Eyj", "https://yt3.googleusercontent.com/ytc/AIdro_kx_tPHk_DdII3m8ZTy6o9nCdp6vuGS6lC9zvZBcXrciCI=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Biene Maja[/B] 1. Klassik Serie", "playlist/PLdHRcaRTf6chVA47IIGwDRJbvgkgBS6Xz", "https://yt3.googleusercontent.com/ytc/AIdro_k_scJq9HnRuToNP--3iIsRfqAAFa27DZG6X9yRS9C8Ctw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Biene Maja[/B] 2. Die neue Serie", "playlist/PLdHRcaRTf6cie56jn0JUsHVGMMSU4AqY-", "https://yt3.googleusercontent.com/ytc/AIdro_k_scJq9HnRuToNP--3iIsRfqAAFa27DZG6X9yRS9C8Ctw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Heidi[/B] 1. Klassik Serie", "playlist/-J_Clayv2_c&list=PLwz9HrBqSQF-WEycaVv_2m5o_4rmxICyn", "https://yt3.googleusercontent.com/ytc/AIdro_k2eKhwRc8WZGXcGEg0LQvZATEqa9IMYrQ039nfznwc15M=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Heidi[/B] 2. Die neue Serie", "playlist/PLwz9HrBqSQF9Y9W6hf-AwwBxTunNYrFvA", "https://yt3.googleusercontent.com/ytc/AIdro_k2eKhwRc8WZGXcGEg0LQvZATEqa9IMYrQ039nfznwc15M=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Das Dschungelbuch[/B] 1. Klassik Serie", "playlist/PLYekapbFEdMmzDN29jkQwATMx3BgznsdM", "https://yt3.googleusercontent.com/ytc/AIdro_mvfRl7am0OpQD3Ctwcsl1ks-Y75vNtISY_z0IOJRhHJQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Das Dschungelbuch[/B] 2. Die neue Serie", "playlist/PL_YOcJJS3cSLJ6-4pXn9SURAkw8Z98FdV", "https://yt3.googleusercontent.com/ytc/AIdro_mvfRl7am0OpQD3Ctwcsl1ks-Y75vNtISY_z0IOJRhHJQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Robin Hood[/B] 1. Klassik Serie", "playlist/PLYekapbFEdMlSWa8pmtr1EEQGI3lEofb3", "https://yt3.googleusercontent.com/qcHBiOPL7Tr5VPT17va19m1756JeJ3ekce-UAno-HervduE-uXffo0KBxpdFKKjp2vM-pkCs=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Robin Hood[/B] 2. Die neue Serie", "playlist/PLM5esjyCBU_qStUbQ_YqpE--k700AWoG5", "https://yt3.googleusercontent.com/qcHBiOPL7Tr5VPT17va19m1756JeJ3ekce-UAno-HervduE-uXffo0KBxpdFKKjp2vM-pkCs=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Die Schlümpfe[/B] 1. Klassik Serie", "playlist/PLe9POcs8knUCprw4_XXxTm8hkGBVw6NHs", "https://yt3.googleusercontent.com/ytc/AIdro_lz1JwV2UcYvO3sU4glwAbVK7jXobyldkMW4I8LCyX_hEk=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Simba der Löwenkönig[/B] 1. Klassik Serie", "playlist/PLYekapbFEdMlAfVPEpc9EQxHP4nCIXd3T", "https://yt3.googleusercontent.com/ytc/AIdro_nT99re9EdPau__EwlwulmRIW4GHKioxyPBsNlh88FBow=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Christoph Columbus[/B] 1. Klassik Serie", "playlist/PLYekapbFEdMnpBAXde80pONK86-k_TPFl", "https://yt3.googleusercontent.com/ytc/AIdro_kwdQSy_A8r3HQ3nlzl8DZUTSPElLpishRBD2oxszbYig=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Meister Eder & sein Pumuckl[/B] 1. Klassik Serie", "playlist/PLpalD7hdQxE3nzQxRxxfmFk9D33EuPPtO", "https://yt3.googleusercontent.com/ytc/AIdro_nXpiXiPR937WSN2duuEAg366vba-YUkAahxAOimfDi6w=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Lucky Luke[/B]", "playlist/PLbfm0-ETt5G6yq5oFYSlAkaNLQXbOSttk", "https://yt3.googleusercontent.com/ytc/AIdro_mcGqztk0W5DB34AR7JL0kcv2jmoJk49Re_SG8ZlH8bZA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Die kleinen Strolche[/B]", "playlist/PLueQL19LT3Kbf6zvCwESHFOS7uPvUeTdr", "https://yt3.googleusercontent.com/ytc/AIdro_kLWdfVshplzUekAptJLhCnd4vZR9tGVptbs1Jeo3X80w=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Grisu der kleine Drache[/B] 1. Klassik Serie", "playlist/PLfbRhPoVa4gNvf3OaRPHcvGpiTv_AJf9U", "https://yt3.googleusercontent.com/IgitEsBoWmeD_xSHFMiu8nwOuGvlCSCtOzUQxSm_91VXPa1nzEOnb3lcFfrfZnpe_DWkoWEq6A=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Alfred J Kwak[/B] 1. Klassik Serie", "playlist/PL58016D15BD79A97F", "https://yt3.googleusercontent.com/ytc/AIdro_kTe98feEy_Gbop5bwCS2BEOU2FyBqpvWL5hDNagEGysg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Scooby Doo[/B] 1. Klassik Serie", "playlist/PLJYf0JdTApCqEYfW77tMTtqN-gA65_LPW", "https://yt3.googleusercontent.com/R297M7jAVBV8_1NIsybn59l5XIvTVygHhrgu8F7iZCblqS-kHRGDWwDlOkR3Lgt13fHpYVvb=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kleo, das fliegende Einhorn[/B] Staffel 1", "playlist/PLx7XyMBfhgopl8zhHyagkK5MZP-CzXZCl", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Jim Knopf[/B] (Zeichentrickserie) Staffel 1-2", "playlist/PL3kvPcxZMm3asH5sX_M4kSvdkHCDwZn3h", "https://yt3.googleusercontent.com/ytc/AIdro_kEiju73Tovm8K3dMsI2Wzhz6j8ZPyHZ6fb20wJDSbejg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Zoes Zauberschrank[/B]", "PLPHcQYsAZvMA4PIV8JYR4ZZpJjZ8i4Jjs", "https://yt3.googleusercontent.com/PHGbrL1fSJgdN-1S69zDJ7GUVuw9ypSiq8skG1GAzxcESnwCgRYwv0yhe7sTR_5VS-NwjjIxyA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Trotro[/B]", "channel/UCAML9huAKtSutHftRbbNmTA", "https://yt3.googleusercontent.com/tHrYXausgAx1JUVDSaQkxoyJ3YA7TXMNSUIZESsKGDJcrcTpHcpke_uLriqZqh3D9IRP2cs4pQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tim & Struppi[/B]", "playlist/PLY25BVSAuho3YVOUhdzCvpE11y2GGz2Nf", "https://yt3.googleusercontent.com/ytc/AIdro_m8aufXYahT6M_Ls2moneQrvHYYgZX-65jKnau6_euSbg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Klassiker': [
        ("[B]Flipper[/B] Staffel 1", "playlist/PLHEDxAYF32QJmHISru7c-MZn_sYt9MpCL", "https://yt3.googleusercontent.com/ytc/AIdro_mHgXhrgT5R7YBXCB6jozpG7ASarqCaiT5qKVi5s2fIWA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Flipper[/B] Staffel 2", "playlist/PLHEDxAYF32QIXWcvfBkxxzmfW6xI-i4Gl", "https://yt3.googleusercontent.com/ytc/AIdro_mHgXhrgT5R7YBXCB6jozpG7ASarqCaiT5qKVi5s2fIWA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Flipper[/B] Staffel 3", "playlist/PLHEDxAYF32QJPtxGimOndyo8VunXLk62Q", "https://yt3.googleusercontent.com/ytc/AIdro_mHgXhrgT5R7YBXCB6jozpG7ASarqCaiT5qKVi5s2fIWA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Pan Tau[/B] Staffel 1-3", "playlist/PLx7XyMBfhgoo-6tYzBcnVJv4BCZC41q_W", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Die rote Zora und ihre Bande[/B] Alle Folgen", "playlist/PLx7XyMBfhgookKfFmo-hE7YfMCRA9YJIw", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Die Strandclique[/B] Staffel 1", "playlist/PLx7XyMBfhgoq2FJuMdl7RNh1TJGzZN7Kj", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Gegen den Wind[/B] Staffel 1", "playlist/PLx7XyMBfhgoqH3sckwgLRpmSI06VTEWUX", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Trickfilm-Klassiker[/B] DEFA", "playlist/PLx7XyMBfhgoq5obBLDvi58-ljZfZb0qzp", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Spielfilmklassiker zu Weihnachten[/B]", "playlist/PLx7XyMBfhgoqJHGE11Dr3oEhWMCDvRFLo", "https://yt3.googleusercontent.com/m9EMpzxqRblZQ9CuD6_b-KZEbXeGs_fYern_BKeANOTlQTZ-YynVvcUTKpoo3I0gVQ3X_0A1qK4=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kinderfilm Klassiker[/B]", "playlist/PLAroxwS0jZuTN6tscgrR_ubgHM4UaFBPv", "https://yt3.googleusercontent.com/OfyylHIKU_TcdZXA8gWLAv2Z7S4BhZtpDhRCDewnzvfgQkTfeSQGkrDeJSPr8CR_8XjlTLSB=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Geschichten': [
        ("[B]Unser Sandmännchen[/B] von RBB", "user/sandmannshop", "https://yt3.googleusercontent.com/4cfX7kHTycQlmmphdCoFqqMcxBSbFmLZ05QdpjCANri0f0YJInrQwNj-MCH_IZl1onT_Wphvfg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]German Fairy Tales[/B]", "playlist/PLYJXC9hVK9ZdUXMrhOTC-kpfIEwJQ2c0u", "https://yt3.googleusercontent.com/ytc/AIdro_m7h0lhnTJCALtmVQpnOTCXLO5ON9OpPIZ3X45mLlmftA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Märchen für Kinder[/B] Gutenachtgeschichten", "playlist/PLRSUQa10y6VFV1kYPPc1hH0kSksmCvGU1", "https://yt3.googleusercontent.com/ytc/AIdro_nLeRvtckO3nepGlumWyHZl8IE2KkUin8Mp3A3YYIHEMQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Gute Nacht Geschichten[/B] DE.BedtimeStory.TV", "playlist/PLSeYZc0WTfTc-eqLP1bZLj0fJ13ZVfzBv", "https://yt3.googleusercontent.com/ytc/AIdro_ljVg3c7DXHAGU3leumLAX6txqgon5D9Re4uGQYzuleFw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Deine Märchenwelt[/B] Märchen, Geschichten, Sagen", "playlist/PLvsVeezf83quto2DL-5J4ZPmm2cYgwaFU", "https://yt3.googleusercontent.com/ytc/AIdro_nQkYXLLccuK_7aLuPMjZHAN4TVoiZkmqbleYIoaQHjxQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Geschichten für Kinder[/B]", "playlist/PLT8zuqWPJkYAJI2jiNa67Q3YaRMOVR-uL", "https://yt3.googleusercontent.com/ytc/AIdro_l_cpO1x5DrRvlYSdq_LaO1q_Epc06e8S5Ofme2kFSdKw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]SimsalaGrimm[/B]", "playlist/PLN5h7nQDQsiNAygibR61TxqtquFrvydt6", "https://yt3.googleusercontent.com/TPSvYLHHLDCNQea0b1viNt6mGEGs1We9vvnZMOeUcoILoektm_BDeVIlpcHNx5S1Gm7LFppZYg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Grimms Märchen[/B] Filme", "playlist/PL9A89EE24241DACF2", "https://yt3.googleusercontent.com/AgKnoiN2B95xJcDsF3wbrIvDaMWNwJ1l4d8VMEOlnMHWLRi2tQfBlLNyPxSjryi6rMhW8NCYug=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Buch': [
        ("[B]Kinder- & Jugend Hörspiele[/B] HoerTalk", "playlist/PL6IcxBEYItDV7PWjFYdnHF9IsvAAGPaRx", "https://yt3.googleusercontent.com/ytc/AIdro_lUNtb8xK82q6O4iYTaNYFxj2syawEI_o-iLsngDA7j0g=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Hörspiel[/B] Guru", "channel/UCCT5k5hwaSIRGoJ5vALZuMg", "https://yt3.googleusercontent.com/65wFWDo8cizVOOLeW5hDP7VLDmka6zrpXObnlobNOo8vlPg40skZwYISCtWj5Scg7_qFsDnXmw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Jugend Hörspiele[/B] Spooks", "playlist/PLBCqvaIr4yUkjmEq5okDt5UAcNhqPgbq6", "https://yt3.googleusercontent.com/3jjA5W1C714Oej9uSA9VcisLgT63t1Kpvssf4cTrflyesf4Du2ZxwjhURMt5QRkbrWf332vE=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Pumuckl Hörspiele 1960-1975[/B] Hörspiel Fabrik", "playlist/PLo-9MW9vCL30fO8QcGDyzusOFW3XLRVXB", "https://yt3.googleusercontent.com/ytc/AIdro_nXpiXiPR937WSN2duuEAg366vba-YUkAahxAOimfDi6w=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tim & Struppi Hörspiele[/B]", "playlist/PLkLkiOLu9xekbDC9aYJDftPBqPs8oCa8D", "https://yt3.googleusercontent.com/65wFWDo8cizVOOLeW5hDP7VLDmka6zrpXObnlobNOo8vlPg40skZwYISCtWj5Scg7_qFsDnXmw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Benjamin Blümchen Hörspiele[/B] BenjaminBlümchen.tv", "playlist/PL1SAyTUFBb762GpJFH19_NvETovF_-NXu", "https://yt3.googleusercontent.com/ytc/AIdro_nxryECurSuDeK6loDsbG2inLuGas2vBWi7zMCEYh-rlmo=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Bibi Blocksberg[/B] BibiBlocksberg.tv", "playlist/PLOZg6nrLYB79IpjmXsBPoq2tuW1DjEb1J", "https://yt3.googleusercontent.com/ytc/AIdro_kaXwWIBwqekbuxe6Dhcrgw25Aywv4Ujp824KcTfD0DhxI=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Barbie Hörspiele[/B] ", "playlist/PLnH8v4sKlmyDprODopPXEZQ3B28MYCkQC", "https://yt3.googleusercontent.com/J5l0pIYLHcZByl5o70xs_fTVx0gqxN7FSl20UKtyne_EKszZlgsYqNrmnt9oAFUhUra70on8RA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Grimm´s Märchen Hörspiele[/B] Märchenwelt", "playlist/PL_7pajp36h-R_VBtOQMaFg7SAmlT02fX8", "https://yt3.googleusercontent.com/lARZK6WQ3oS0BX9U7ExdgAdcHSbazCDTHUvLoFF9FpFhY9tIPkBukcEVF2Ng0zknSHTvnj4q=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Märchen Hörspiele[/B] Hörspiel Fuchs", "playlist/PL49N08rhGF4dp7S5egoLmLT50_MqtTtVD", "https://yt3.googleusercontent.com/ytc/AIdro_mZpPJSHYcsJQ9rVpJ9-qXbsAvQF5rroosKij8JbP08_A=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Klassische Hörspiele[/B] Märchenwelt", "playlist/PL_7pajp36h-QXzz1ncxNJFtg2GZzHV1dL", "https://yt3.googleusercontent.com/lARZK6WQ3oS0BX9U7ExdgAdcHSbazCDTHUvLoFF9FpFhY9tIPkBukcEVF2Ng0zknSHTvnj4q=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Christliche Hörspiele[/B] die Bibel", "channel/UCJSF-0y7Pz7VUNH3cCdqwLw", "https://yt3.googleusercontent.com/ytc/AIdro_m0D75VUeq8rjNhGPl80HH8WMqMhGBHk0p8t61jPzUDWw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Urmel[/B] Hörspiel Serie", "playlist/PLa3cPVZ_c5hhE6mgOvbDAfLzxxiPDWkId", "https://yt3.googleusercontent.com/65wFWDo8cizVOOLeW5hDP7VLDmka6zrpXObnlobNOo8vlPg40skZwYISCtWj5Scg7_qFsDnXmw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Tim und Struppi[/B] Hörspiel", "playlist/PLa3cPVZ_c5hisrwl_5GopM5x57xDPauS7", "https://yt3.googleusercontent.com/65wFWDo8cizVOOLeW5hDP7VLDmka6zrpXObnlobNOo8vlPg40skZwYISCtWj5Scg7_qFsDnXmw=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Wissen': [
        ("[B]KiWi[/B] Schlaue Fragen, schlaue Antworten!", "playlist/PLVWZ8fAnW6IbmOFpTtp6ImFFW-K4T83YN", "https://yt3.googleusercontent.com/ytc/AIdro_nRrCb-aovIu_su17Fed1V8J70QdFKP_f6H_6mc7TOBoJo=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]KiWi[/B] Professor Schlaufuchs", "playlist/PLVWZ8fAnW6IbqKL4j7uaR4RtPsqB6rKc0", "https://yt3.googleusercontent.com/ytc/AIdro_nRrCb-aovIu_su17Fed1V8J70QdFKP_f6H_6mc7TOBoJo=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Planet Schule[/B] von ARD", "playlist/PL93F091E59FDFDDBF", "https://yt3.googleusercontent.com/ytc/AIdro_nkghDj-XHzlJ0CCE1q4BXzL01ufINgm9KUiqfhaWTBjUnZ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Checker Welt[/B] Experimente", "playlist/PLXHkZNhCrU2ZGzKXPeq_8NY8ZF3coQyR9", "https://yt3.googleusercontent.com/lOR8wZvBdSO56a4CXiQm45EPeUoQEUN8ctVFJW75MDgrL_sFJ8SPe5KrW0owlTKQJUcjz1pnQQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]DIY Inspiration Kids Club[/B] Experimente", "playlist/PLjXEwjXTkbzqewdd_3DTgb0GZ_0LhECPJ", "https://yt3.googleusercontent.com/ytc/AIdro_mXiHnjWsyR6OwXG1zncEa08PxvWKnmVdc5Xo8XohfWLFs=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]PAXI[/B] European Space Agency", "playlist/PLbyvawxScNbvwcIVrGQV4p6g6cp9pH0To", "https://yt3.googleusercontent.com/gnGJqh7iQPl66irKn3xdT9BDv2K7LOPMFghqL0MHQKk5XjmK-nD9r7CrdYcIEWFmSC0rlr_a=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],

    'Kinder Musik': [
        ("[B]Sing mit Mir[/B] Kinderlieder", "playlist/PLu791Jb5lWoCOzceiS6SDeGW_u1s7x-0h", "https://yt3.googleusercontent.com/OZ_jeNxvsxe4NG-aefWNxG8NrKJTXoElYRQZ45ISKmXCVhu_RNSboaIMOKRfOWBveo61R9EeCg=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Hurra[/B] Kinderlieder", "playlist/PLz8hTTrU37YTw06tseX2sHpXMbDK9x_Ds", "https://yt3.googleusercontent.com/ytc/AIdro_kcnVO0eY6JzCRVjB2AUx7sndCRWLpdPnITOq2t06NaQQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kinderlieder[/B] zum Mitsingen und Tanzen", "playlist/PLM9BsUcYb5Mn8xN72IX5LUHj25_ssTN5_", "https://yt3.googleusercontent.com/BGoTUkK-TRjC6fC1fFP700dgrV5cjuHw-O8OcgGnqsHi3RoeU7b0hKm-0eS4dDOg-PWs5lz9Ew=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Karaoke[/B] Kinderlieder mit Biene Maja, Wickie und Co.", "playlist/PLCywMP0BLGOk_cTbmLNENN711N3Yw0hRF", "https://yt3.googleusercontent.com/ytc/AIdro_kQAr8CtbgD9MB9WP-U_AQsSDfAOVsQ4KsQliL2Ztc-T-E=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Disney[/B] Titelmusik", "playlist/PL4BrNFx1j7E6a6IKg8N0IgnkoamHlCHWa", "https://yt3.ggpht.com/c3_JbPq0s5lc_pfXglSsnNTMv4T-oEK6zvmQDBFqxmAmgmKn1yDm5141NzYqudS2qhzt50fDJw=s176-c-k-c0x00ffffff-no-rj-mo"),
        ("[B]KinderliederTV.de[/B]", "playlist/PLmMaywx47bx5w5YJ3uLJz73X81srE4wlQ", "https://yt3.googleusercontent.com/puwtJUTPtemz8BDpE2ep4NL3RVqqNrwhQ2jBQ-Utkc32r6XJAbVHSXIJZLMWRMsAZhNHRj6fWR8=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]GiraffenaffenTV[/B]", "channel/UCUWTq9Jq97CNE9j28OarHbQ", "https://yt3.googleusercontent.com/5f81fzOw1sMs0u9zlz8hUqXWrDJ5XWbdsTM3z2VMgoAsPX_cENGCip8_YI8Yx9xsp7BfDjmZyQ=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Liederkiste[/B] Kinderlieder", "channel/UCAOmPP7Xt9YmPYtjettV3oA", "https://yt3.googleusercontent.com/uDGJirtwpri8ClvehxG1GMHIL5AXPDnHquIKQRmituyTdH46HK443mcSzBuUl3UDMNN6vkXfJA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B]Kika TanzAlarm[/B] | Mehr auf KiKA.de", "playlist/PLIFhkWbVDf6wcorvcRTbQvSYvYemSvJoa", "https://yt3.googleusercontent.com/eVEM7kLayi8-pFKQ2jMVMqWMMf-Sj-LFtPD5oD5d4vctMxwa_MxvYkYQOihpO8YxHO3Fo8qHVA=s160-c-k-c0x00ffffff-no-rj"),
        ("[B][I]Weitere[/I][/B]", "Weitere", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
        ("[B][I]Suche[/I][/B]", "Suche", "special://home/addons/plugin.video.xstream/resources/art/sites/kids_tube.png"),
    ],
}

def search_playlists(query, max_results=5):
    search_url = "https://www.googleapis.com/youtube/v3/search"
    my_keys = ['AIzaSyBQ68nE4JxFSlyogirJUo8b4TYF2iGMJms', 'AIzaSyAyvS7LLZsBF6mNWiAmISYvdJWtu_MSvf4']
    key = random.choice(my_keys)
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'playlist',
        'maxResults': max_results,
        'key': key}
    response = requests.get(search_url, params=params)
    if response.status_code == 200:
        data = response.json()
        playlists = data.get('items', [])
        sublists = []

        if not playlists:
            xbmcgui.Dialog().notification('Kids_Tube', 'Not found')
        else:
            for i, item in enumerate(playlists, start=1):
                playlist_title = item['snippet']['title']
                playlist_id = 'playlist/' + item['id']['playlistId']
                playlist_icon = item['snippet']['thumbnails']['default']['url']
                sublists.append({'title': playlist_title, 'id': playlist_id, 'icon': playlist_icon})
        return sublists
    else:
        xbmcgui.Dialog().notification('Kids_Tube', 'Not found')


def sub_list(action):
    youtube_fix.YT()
    params = ParameterHandler()
    action1 = '#' + str(action) + ' deutsch für kinder'
    action2 = '*' + str(action)
    apikey = cConfig('plugin.video.youtube').getSetting('youtube.api.key')
    for List in sublists[str(action)]:
        name = List[0]
        id = List[1]
        icon = List[2]
        if apikey == '' or apikey == None:
            sUrl="plugin://plugin.video.youtube/" + id + "/?addon_id=plugin.video.xstream"
        else:
            sUrl="plugin://plugin.video.youtube/" + id + "/"
        if 'Weitere' in str(id):
            params.setParam('action', action1)
            params.setParam('sUrl', '')
            params.setParam('trumb', icon)
            cGui().addFolder(cGuiElement(name, SITE_IDENTIFIER, 'load'),params,bIsFolder=True)
        elif 'Suche' in str(id):
            params.setParam('action', action2)
            params.setParam('sUrl', '')
            params.setParam('trumb', icon)
            cGui().addFolder(cGuiElement(name, SITE_IDENTIFIER, 'load'),params,bIsFolder=True)
        else:
            params.setParam('trumb', icon)
            params.setParam('sUrl', sUrl)
            cGui().addFolder(cGuiElement(name,SITE_IDENTIFIER,''),params,bIsFolder=True)
    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)


def sub_listw(action):
    youtube_fix.YT()
    params = ParameterHandler()
    sublist2 = search_playlists(action, max_results=50)
    apikey = cConfig('plugin.video.youtube').getSetting('youtube.api.key')
    for List in sublist2:
        name = "[B]%s[/B]" % List['title']
        id = List['id']
        icon = List['icon']
        if apikey == '' or apikey == None:
            sUrl="plugin://plugin.video.youtube/" + id + "/?addon_id=plugin.video.xstream"
        else:
            sUrl="plugin://plugin.video.youtube/" + id + "/"
        params.setParam('trumb', icon)
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(name,SITE_IDENTIFIER,''),params,bIsFolder=True)
    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)


def keyb():
        heading = cConfig().getLocalizedString(30281)
        keyboard = xbmc.Keyboard('default', 'heading', True)
        keyboard.setDefault()
        keyboard.setHeading(heading)
        keyboard.setHiddenInput(False)
        keyboard.doModal()
        if keyboard.isConfirmed() and not keyboard.getText() == '':
            return keyboard.getText()
        else:sys.exit()

def search(action):
    youtube_fix.YT()
    params = ParameterHandler()
    apikey = cConfig('plugin.video.youtube').getSetting('youtube.api.key')
    query= keyb()
    sublist2 = search_playlists(query + ' ' + action + ' deutsch', max_results=50)
    for List in sublist2:
        name = "[B]%s[/B]" % List['title']
        id = List['id']
        icon = List['icon']
        if apikey == '' or apikey == None:
            sUrl="plugin://plugin.video.youtube/" + id + "/?addon_id=plugin.video.xstream"
        else:
            sUrl="plugin://plugin.video.youtube/" + id + "/"
        params.setParam('trumb', icon)
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(name,SITE_IDENTIFIER,''),params,bIsFolder=True)
    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)


def main_list():
    params = ParameterHandler()
    for name, id, icon in channellist:
        params.setParam('action', id)
        params.setParam('trumb', icon)
        cGui().addFolder(cGuiElement(name, SITE_IDENTIFIER, 'load'),params,bIsFolder=True)
    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)

