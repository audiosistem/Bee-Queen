# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!
# HTML LangzeitCache hinzugefügt
# showGenre:     48 Stunden
# showEntries:    6 Stunden
# showSeasons:    6 Stunden
# showEpisodes:   4 Stunden


import base64
import binascii
import hashlib
import re
import json

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from resources.lib import pyaes
from itertools import zip_longest as ziplist

SITE_IDENTIFIER = 'kinoger'
SITE_NAME = 'KinoGer'
SITE_ICON = 'kinoger.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain Abfrage
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain') # Domain Auswahl über die xStream Einstellungen möglich
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Status Code Abfrage der Domain
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Ob Plugin aktiviert ist oder nicht

URL_MAIN = 'https://' + DOMAIN
# URL_MAIN = 'https://kinoger.to'
URL_SERIES = URL_MAIN + '/stream/serie/'

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    params.setParam('sUrl', URL_MAIN)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30500), SITE_IDENTIFIER, 'showEntries'), params)    # New
    params.setParam('sUrl', URL_SERIES)
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30511), SITE_IDENTIFIER, 'showEntries'), params)  # Series
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showGenre'), params)    # Genre
    cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
    cGui().setEndOfDirectory()


def showGenre():
    params = ParameterHandler()
    oRequest = cRequestHandler(URL_MAIN)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 48 # 48 Stunden
    sHtmlContent = oRequest.request()
    pattern = '<li[^>]class="links"><a href="([^"]+).*?/>([^<]+)</a>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        params.setParam('sUrl', URL_MAIN + sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showEntries(entryUrl=False, sGui=False, sSearchText=False, sSearchPageText = False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # 6 Stunden
    if sSearchText:
        oRequest.addParameters('story', sSearchText)
        oRequest.addParameters('do', 'search')
        oRequest.addParameters('subaction', 'search')
        oRequest.addParameters('x', '0')
        oRequest.addParameters('y', '0')
        oRequest.addParameters('titleonly', '3')
        oRequest.addParameters('submit', 'submit')
    else:
        oRequest.addParameters('dlenewssortby', 'date')
        oRequest.addParameters('dledirection', 'desc')
        oRequest.addParameters('set_new_sort', 'dle_sort_main')
        oRequest.addParameters('set_direction_sort', 'dle_direction_main')
    sHtmlContent = oRequest.request()
    pattern = 'class="title".*?href="([^"]+)">([^<]+).*?src="([^"]+)(.*?)</a> </span>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName, sThumbnail, sDummy in aResult:
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        isTvshow = True if 'staffel' in sName.lower() or 'serie' in entryUrl or ';">S0' in sDummy else False
        isYear, sYear = cParser.parse(sName, '(.*?)\s+\((\d+)\)') # Jahr und Name trennen
        if isYear:
            for name, year in sYear:
                sName = name
                sYear = year
                break
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        isDesc, sDesc = cParser.parseSingleResult(sDummy, '(?:</b></div>|</div></b>|</b>)([^<]+)') # Beschreibung
        isDuration, sDuration = cParser.parseSingleResult(sDummy, '(?:Laufzeit|Spielzeit).*?([\d]+)') # Laufzeit
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons' if isTvshow else 'showHosters')
        oGuiElement.setMediaType('tvshow' if isTvshow else 'movie')
        oGuiElement.setThumbnail(sThumbnail)
        if isYear:
            oGuiElement.setYear(sYear)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        if isDuration:
            oGuiElement.addItemValue('duration', sDuration)
        # Parameter übergeben
        params.setParam('sThumbnail', sThumbnail)
        params.setParam('TVShowTitle', sName)
        params.setParam('entryUrl', sUrl)
        oGui.addFolder(oGuiElement, params, isTvshow, total)
    if not sGui and not sSearchText and not sSearchPageText:
        isMatchNextPage, sNextUrl = cParser.parseSingleResult(sHtmlContent, '<a[^>]href="([^"]+)">vorw')
        # Start Page Function
        isMatchSiteSearch, sHtmlContainer = cParser.parseSingleResult(sHtmlContent, 'class="navigation(.*?)</a></div>')
        if isMatchSiteSearch:
            isMatch, aResult = cParser.parse(sHtmlContainer, '<span>([\d]+)</span>.*?nav_ext">.*?">([\d]+).*?href="([^"]+)')
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
        oGui.setView('tvshows' if 'staffel' in sName.lower() else 'movies')
        oGui.setEndOfDirectory()


def showSeasons():
    params = ParameterHandler()
    # Parameter laden
    entryUrl = params.getValue('entryUrl')
    sThumbnail = params.getValue('sThumbnail')
    sTVShowTitle = params.getValue('TVShowTitle')
    oRequest = cRequestHandler(entryUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 6  # HTML Cache Zeit 6 Stunden
    sHtmlContent = oRequest.request()
    L11 = []
    isMatchsst, sstsContainer = cParser.parseSingleResult(sHtmlContent, 'sst.show.*?</script>')
    if isMatchsst:
        sstsContainer = sstsContainer.replace('[', '<').replace(']', '>')
        isMatchsst, L11 = cParser.parse(sstsContainer, "<'([^>]+)")
        if isMatchsst:
            total = len(L11)
    L22 = []
    isMatchollhd, ollhdsContainer = cParser.parseSingleResult(sHtmlContent, 'ollhd.show.*?</script>')
    if isMatchollhd:
        ollhdsContainer = ollhdsContainer.replace('[', '<').replace(']', '>')
        isMatchollhd, L22 = cParser.parse(ollhdsContainer, "<'([^>]+)")
        if isMatchollhd:
            total = len(L22)
    L33 = []
    isMatchpw, pwsContainer = cParser.parseSingleResult(sHtmlContent, 'pw.show.*?</script>')
    if isMatchpw:
        pwsContainer = pwsContainer.replace('[', '<').replace(']', '>')
        isMatchpw, L33 = cParser.parse(pwsContainer, "<'([^>]+)")
        if isMatchpw:
            total = len(L33)

    L44 = []
    isMatchgo, gosContainer = cParser.parseSingleResult(sHtmlContent, 'go.show.*?</script>')
    if isMatchgo:
        gosContainer = gosContainer.replace('[', '<').replace(']', '>')
        isMatchgo, L44 = cParser.parse(gosContainer, "<'([^>]+)")
        if isMatchgo:
            total = len(L44)

    isDesc, sDesc = cParser.parseSingleResult(sHtmlContent, '</b>([^"]+)<br><br>')
    for i in range(0, total):
        try:
            params.setParam('L11', L11[i])
        except Exception:
            pass
        try:
            params.setParam('L22', L22[i])
        except Exception:
            pass
        try:
            params.setParam('L33', L33[i])
        except Exception:
            pass
        try:
            params.setParam('L44', L44[i])
        except Exception:
            pass
        i = i + 1
        oGuiElement = cGuiElement('Staffel ' + str(i), SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setMediaType('season')
        oGuiElement.setTVShowTitle(sTVShowTitle)
        oGuiElement.setSeason(i)
        oGuiElement.setThumbnail(sThumbnail)
        if isDesc:
            oGuiElement.setDescription(sDesc)
        params.setParam('sDesc', sDesc)
        params.setParam('sSeasonNr', i)
        cGui().addFolder(oGuiElement, params, True, total)
        cGui().setView('seasons')
    cGui().setEndOfDirectory()


def showEpisodes():
    params = ParameterHandler()
    sSeasonNr = params.getValue('sSeasonNr')
    sThumbnail = params.getValue('sThumbnail')
    sTVShowTitle = params.getValue('TVShowTitle')
    sDesc = params.getValue('sDesc')
    L11 = []
    if params.exist('L11'):
        L11 = params.getValue('L11')
        isMatch1, L11 = cParser.parse(L11, "(http[^']+)")
    L22 = []
    if params.exist('L22'):
        L22 = params.getValue('L22')
        isMatch, L22 = cParser.parse(L22, "(http[^']+)")
    L33 = []
    if params.exist('L33'):
        L33 = params.getValue('L33')
        isMatch3, L33 = cParser.parse(L33, "(http[^']+)")
    L44 = []
    if params.exist('L44'):
        L44 = params.getValue('L44')
        isMatch4, L44 = cParser.parse(L44, "(http[^']+)")
    liste = ziplist(L11, L22, L33, L44)
    i = 0
    for sUrl in liste:
        i = i + 1
        oGuiElement = cGuiElement('Episode ' + str(i), SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setTVShowTitle(sTVShowTitle)
        oGuiElement.setSeason(sSeasonNr)
        oGuiElement.setEpisode(i)
        oGuiElement.setMediaType('episode')
        if sDesc:
            oGuiElement.setDescription(sDesc)
        if sThumbnail:
            oGuiElement.setThumbnail(sThumbnail)
        params.setParam('sLinks', sUrl)
        cGui().addFolder(oGuiElement, params, False)
    cGui().setView('episodes')
    cGui().setEndOfDirectory()


def showHosters():
    hosters = []
    headers = '&Accept-Language=de%2Cde-DE%3Bq%3D0.9%2Cen%3Bq%3D0.8%2Cen-GB%3Bq%3D0.7%2Cen-US%3Bq%3D0.6&Accept=%2A%2F%2A&User-Agent=Mozilla%2F5.0+%28Windows+NT+10.0%3B+Win64%3B+x64%3B+rv%3A99.0%29+Gecko%2F20100101+Firefox%2F99.0'
    params = ParameterHandler()
    if params.exist('sLinks'):
        sUrl = params.getValue('sLinks')
        isMatch, aResult = cParser.parse(sUrl, "(http[^']+)")
    else:
        sUrl = params.getValue('entryUrl')
        sHtmlContent = cRequestHandler(sUrl, ignoreErrors=True, caching=False).request()
        pattern = "show[^>]\d,[^>][^>]'([^']+)"
        isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if isMatch:
        for sUrl in aResult:
            try:
                if 'kinoger.ru' in sUrl: continue
                #    oRequest = cRequestHandler(sUrl, caching=False, ignoreErrors=True)
                #    oRequest.addHeaderEntry('Referer', 'https://kinoger.com/')
                #    sHtmlContent = oRequest.request()  # Durchsucht sHtml Content
                #    if isMatch:
                #        decryptHtmlContent = content_decryptor(sHtmlContent, 'H&5+Tx_nQcdK{U,.') # Decrypt Content
                #        isMatch, hUrl = cParser.parseSingleResult(decryptHtmlContent, 'sources.*?file.*?(http[^"]+)')
                #    if isMatch:
                #        hUrl = hUrl.replace('\\', '')
                #        oRequest = cRequestHandler(hUrl, caching=False, ignoreErrors=True)
                #        oRequest.addHeaderEntry('Referer', 'https://kinoger.ru/')
                #        oRequest.addHeaderEntry('Origin', 'https://kinoger.ru')
                #        oRequest.removeNewLines(False)
                #        sHtmlContent = oRequest.request()
                #        if not 'MEDIA:TYPE=AUDIO' in sHtmlContent: # Wenn keine zusätzlichen Audiostreams vorhanden durchsuche m3u8 und filter Links aus
                #            pattern = 'RESOLUTION=.*?x(\d+).*?\n([^\s]+)'
                #            isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                #            if isMatch:
                #                for sQuality, sUrl in aResult:
                #                    sUrl = (hUrl.split('video')[0].strip() + sUrl.strip())
                #                    sUrl = sUrl + '|verifypeer=false&Referer=https%3A%2F%2Fkinoger.ru%2F&Origin=https%3A%2F%2Fkinoger.ru' + headers
                #                    hoster = {'link': sUrl, 'name': 'KinoGer.ru [I][%sp][/I]' % sQuality, 'quality': sQuality, 'resolveable': True}
                #                    hosters.append(hoster)
                #        else: # Wenn Audiostreams enthalten nutze video.m3u8 und lese Content daraus
                #            sUrl = hUrl + '|verifypeer=false&Referer=https%3A%2F%2Fkinoger.ru%2F&Origin=https%3A%2F%2Fkinoger.ru' + headers
                #            hoster = {'link': sUrl, 'name': 'KinoGer.ru [I][Video/Audio auswählbar][/I]', 'resolveable': True}
                #            hosters.append(hoster)

                elif 'kinoger.be' in sUrl:
                    oRequest = cRequestHandler(sUrl, caching=False, ignoreErrors=True)
                    oRequest.addHeaderEntry('Referer', 'https://kinoger.com/')
                    sHtmlContent = oRequest.request()
                    # Wenn Content p.a.c.k.e.d ist dann entpacken
                    isMatch, packed = cParser.parseSingleResult(sHtmlContent, '(eval\s*\(function.*?)</script>')
                    if isMatch:
                        from resources.lib import jsunpacker
                        sHtmlContent = jsunpacker.unpack(packed)
                    isMatch, hUrl = cParser.parseSingleResult(sHtmlContent, 'sources.*?file.*?(http[^"]+)')
                    if isMatch:
                        hUrl = hUrl.replace('\\', '')
                        oRequest = cRequestHandler(hUrl, caching=False, ignoreErrors=True)
                        oRequest.addHeaderEntry('Referer', 'https://kinoger.be/')
                        oRequest.addHeaderEntry('Origin', 'https://kinoger.be')
                        oRequest.removeNewLines(False)
                        sHtmlContent = oRequest.request()
                        if 'CF-DDOS-GUARD aktiv' in sHtmlContent: # Wenn Request eine 403 zurückgibt dann überspringen
                            continue
                        else:
                            pattern = 'RESOLUTION=.*?x(\d+).*?\n(index[^\n]+)'
                            isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                    if isMatch:
                        for sQuality, sUrl in aResult:
                            sUrl = (hUrl.split('video')[0].strip() + sUrl.strip())
                            sUrl = sUrl + '|Origin=https%3A%2F%2Fkinoger.be&Referer=https%3A%2F%2Fkinoger.be%2F' + headers
                            hoster = {'link': sUrl, 'name': 'KinoGer.be [I][%sp][/I]' % sQuality, 'quality': sQuality, 'resolveable': True}
                            hosters.append(hoster)

                elif 'kinoger.pw' in sUrl: # Veev
                    sQuality = '720'
                    hoster = {'link': sUrl + 'DIREKT', 'name': 'Veev.to [I][%sp][/I]'% sQuality, 'quality': sQuality}
                    hosters.append(hoster)

                elif 'kinoger.re' in sUrl:
                    sQuality = '1080'
                    hoster = {'link': sUrl + 'DIREKT', 'name': 'Kinoger.re [I][%sp][/I]'% sQuality, 'quality': sQuality, 'resolveable': True}
                    hosters.append(hoster)

                else: # Alle anderen Hoster wie z.B. Voe
                    sQuality = '720'
                    sName = cParser.urlparse(sUrl)
                    if cConfig().isBlockedHoster(sName)[0]: continue  # Hoster aus settings.xml oder deaktivierten Resolver ausschließen
                    hoster = {'link': sUrl + 'DIREKT', 'name': sName, 'displayedName': '%s [I][%sp][/I]' % (sName, sQuality), 'quality': sQuality}
                    hosters.append(hoster)

            except Exception:
                pass

    if not isMatch:
        return

    if hosters:
        hosters.append('getHosterUrl')
    return hosters


def getHosterUrl(sUrl=False):
    if sUrl.endswith('DIREKT'):
        sUrl = sUrl[:-6]
        Request = cRequestHandler(sUrl, caching=False)
        Request.request()
        sUrl = Request.getRealUrl()  # hole reale URL von der Umleitung

        return [{'streamUrl': sUrl, 'resolved': False}]
    else:
        return [{'streamUrl': sUrl, 'resolved': True}]


def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()


def _search(oGui, sSearchText):
    showEntries(URL_MAIN, oGui, sSearchText)


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


def content_decryptor(html_content,passphrase):
    match = re.compile(r'''JScripts = '(.+?)';''', re.DOTALL).search(html_content)
    if match:
        # Parse the JSON string
        json_obj = json.loads(match.group(1))

        # Extract the salt, iv, and ciphertext from the JSON object
        salt = binascii.unhexlify(json_obj["s"])
        iv = binascii.unhexlify(json_obj["iv"])
        ct = base64.b64decode(json_obj["ct"])

        # Concatenate the passphrase and the salt
        concated_passphrase = passphrase.encode() + salt

        # Compute the MD5 hashes
        md5 = [hashlib.md5(concated_passphrase).digest()]
        result = md5[0]
        i = 1
        while len(result) < 32:
            md5.append(hashlib.md5(md5[i - 1] + concated_passphrase).digest())
            result += md5[i]
            i += 1

        # Extract the key from the result
        key = result[:32]

        # Decrypt the ciphertext using AES-256-CBC
        aes = pyaes.AESModeOfOperationCBC(key, iv)
        decrypter = pyaes.Decrypter(aes)
        plain_text = decrypter.feed(ct)
        plain_text += decrypter.feed()

        # Return the decrypted data as a JSON object
        return json.loads(plain_text.decode())
    else:
        return None