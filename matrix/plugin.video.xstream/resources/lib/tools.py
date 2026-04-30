# -*- coding: utf-8 -*-
# Python 3

import xbmc
import xbmcgui
import hashlib
import re
import os
import time

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib import pyaes
from resources.lib.config import cConfig
from xbmcvfs import translatePath
from urllib.parse import quote, unquote, quote_plus, unquote_plus, urlparse
from html.entities import name2codepoint
from difflib import SequenceMatcher
from functools import lru_cache
from os import path, chdir

# Aufgeführte Plattformen zum Anzeigen der Systemplattform
def platform():
    if xbmc.getCondVisibility('system.platform.android'):
        return 'Android'
    elif xbmc.getCondVisibility('system.platform.linux'):
        return 'Linux'
    elif xbmc.getCondVisibility('system.platform.linux.Raspberrypi'):
        return 'Linux/RPi'
    elif xbmc.getCondVisibility('system.platform.windows'):
        return 'Windows'
    elif xbmc.getCondVisibility('system.platform.uwp'):
        return 'Windows UWP'      
    elif xbmc.getCondVisibility('system.platform.osx'):
        return 'OSX'
    elif xbmc.getCondVisibility('system.platform.atv2'):
        return 'ATV2'
    elif xbmc.getCondVisibility('system.platform.ios'):
        return 'iOS'
    elif xbmc.getCondVisibility('system.platform.darwin'):
        return 'iOS'
    elif xbmc.getCondVisibility('system.platform.xbox'):
        return 'XBOX'
    elif xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)'):
        return 'CoreElec'
    elif xbmc.getCondVisibility('System.HasAddon(service.libreelec.settings)'):
        return 'LibreElec'
    elif xbmc.getCondVisibility('System.HasAddon(service.osmc.settings)'):
        return 'OSMC'


# zeigt nach Update den Changelog als Popup an
def changelog():
    CHANGELOG_PATH = translatePath(os.path.join('special://home/addons/' + cConfig().getAddonInfo('id') + '/', 'changelog.txt'))
    version = cConfig().getAddonInfo('version')
    if cConfig().getSetting('changelog_version') == version or not os.path.isfile(CHANGELOG_PATH):
        return
    cConfig().setSetting('changelog_version', version)
    heading = cConfig().getLocalizedString(30275)
    with open(CHANGELOG_PATH, mode='r', encoding='utf-8') as f:
        cl_lines = f.readlines()
    announce = ''
    for line in cl_lines:
        announce += line
    textBox(heading, announce)


# zeigt die Entwickler Optionen Warnung als Popup an
def devWarning():
    POPUP_PATH = translatePath(os.path.join('special://home/addons/' + cConfig().getAddonInfo('id') + '/resources/popup', 'devWarning.txt'))
    heading = cConfig().getLocalizedString(30322)
    with open(POPUP_PATH, mode='r', encoding='utf-8') as f:
        cl_lines = f.readlines()
    announce = ''
    for line in cl_lines:
        announce += line
    textBox(heading, announce)


# Erstellt eine Textbox
def textBox(heading, announce):
    class TextBox():

        def __init__(self, *args, **kwargs):
            self.WINDOW = 10147
            self.CONTROL_LABEL = 1
            self.CONTROL_TEXTBOX = 5
            xbmc.executebuiltin("ActivateWindow(%d)" % (self.WINDOW, ))
            self.win = xbmcgui.Window(self.WINDOW)
            xbmc.sleep(500)
            self.setControls()

        def setControls(self):
            self.win.getControl(self.CONTROL_LABEL).setLabel(heading)
            try:
                f = open(announce)
                text = f.read()
            except:
                text = announce
            self.win.getControl(self.CONTROL_TEXTBOX).setText(str(text))
            return

    TextBox()
    while xbmc.getCondVisibility('Window.IsVisible(10147)'):
        xbmc.sleep(500)


# Info Meldung im Kodi
def infoDialog(message, heading=cConfig().getAddonInfo('name'), icon='', time=5000, sound=False):
    if icon == '': icon = cConfig().getAddonInfo('icon')
    elif icon == 'INFO': icon = xbmcgui.NOTIFICATION_INFO
    elif icon == 'WARNING': icon = xbmcgui.NOTIFICATION_WARNING
    elif icon == 'ERROR': icon = xbmcgui.NOTIFICATION_ERROR
    xbmcgui.Dialog().notification(heading, message, icon, time, sound=sound)


class cParser:
    @staticmethod
    def _get_compiled_pattern(pattern, flags=0):
        return re.compile(pattern, flags)
    
    @staticmethod
    def _replaceSpecialCharacters(s):
        try:
            # Umlaute Unicode konvertieren
            for t in (('\\/', '/'), ('&amp;', '&'), ('\\u00c4', 'Ä'), ('\\u00e4', 'ä'),
                ('\\u00d6', 'Ö'), ('\\u00f6', 'ö'), ('\\u00dc', 'Ü'), ('\\u00fc', 'ü'),
                ('\\u00df', 'ß'), ('\\u2013', '-'), ('\\u00b2', '²'), ('\\u00b3', '³'),
                ('\\u00e9', 'é'), ('\\u2018', '‘'), ('\\u201e', '„'), ('\\u201c', '“'),
                ('\\u00c9', 'É'), ('\\u2026', '...'), ('\\u202f', 'h'), ('\\u2019', '’'),
                ('\\u0308', '̈'), ('\\u00e8', 'è'), ('#038;', ''), ('\\u00f8', 'ø'),
                ('／', '/'), ('\\u00e1', 'á'), ('&#8211;', '-'), ('&#8220;', '“'), ('&#8222;', '„'),
                ('&#8217;', '’'), ('&#8230;', '…'), ('\\u00bc', '¼'), ('\\u00bd', '½'), ('\\u00be', '¾'),
                ('\\u2153', '⅓'), ('\\u002A', '*')):
                s = s.replace(*t)

            # Umlaute HTML konvertieren
            for h in (('\\/', '/'), ('&#x26;', '&'), ('&#039;', "'"), ("&#39;", "'"),
                ('&#xC4;', 'Ä'), ('&#xE4;', 'ä'), ('&#xD6;', 'Ö'), ('&#xF6;', 'ö'),
                ('&#xDC;', 'Ü'), ('&#xFC;', 'ü'), ('&#xDF;', 'ß') , ('&#xB2;', '²'),
                ('&#xDC;', '³'), ('&#xBC;', '¼'), ('&#xBD;', '½'), ('&#xBE;', '¾'),
                ('&#8531;', '⅓'), ('&#8727;', '*')):
                s = s.replace(*h)
        except:
            pass
        return s

    @staticmethod
    def parseSingleResult(sHtmlContent, pattern, ignoreCase=False):
        if sHtmlContent:
            flags = re.S | re.M
            if ignoreCase:
                flags |= re.I

            matches = cParser._get_compiled_pattern(pattern, flags).search(sHtmlContent)
            
            if matches:
                # Check if there's at least one capturing group
                if matches.lastindex is not None and matches.lastindex >= 1:
                    return True, cParser._replaceSpecialCharacters(matches.group(1))
                else:
                    # fallback to the entire match if no group was captured
                    return True, cParser._replaceSpecialCharacters(matches.group(0))
        return False, None
    
    @staticmethod
    def parse(sHtmlContent, pattern, iMinFoundValue=1, ignoreCase=False):
        if sHtmlContent:
            flags = re.DOTALL
            if ignoreCase:
                flags |= re.I

            aMatches = cParser._get_compiled_pattern(pattern, flags).findall(sHtmlContent)
            
            if len(aMatches) >= iMinFoundValue:
                # handle both single strings and tuples of matches
                if isinstance(aMatches[0], tuple):
                    # Process each string in tuple
                    aMatches = [tuple(cParser._replaceSpecialCharacters(x) if isinstance(x, str) and x is not None else '' for x in match) for match in aMatches]
                else:
                    # Process single strings
                    aMatches = [cParser._replaceSpecialCharacters(x) if isinstance(x, str) and x is not None else '' for x in aMatches]
                
                return True, aMatches
        return False, None

    @staticmethod
    def replace(pattern, sReplaceString, sValue):
        return cParser._get_compiled_pattern(pattern).sub(sReplaceString, sValue)

    @staticmethod
    def search(pattern, sValue, ignoreCase=True):
        flags = 0
        if ignoreCase:
            flags = re.IGNORECASE
        return cParser._get_compiled_pattern(pattern, flags).search(sValue)

    @staticmethod
    def escape(sValue):
        return re.escape(sValue)

    @staticmethod
    def getNumberFromString(sValue):
        aMatches = re.compile('\d+').findall(sValue)
        if len(aMatches) > 0:
            return int(aMatches[0])
        return 0

    @staticmethod
    def urlparse(sUrl):
        return urlparse(sUrl.replace('www.', '')).netloc.title()

    @staticmethod
    def urlDecode(sUrl):
        return unquote(sUrl)

    @staticmethod
    def urlEncode(sUrl, safe=''):
        return quote(sUrl, safe)

    @staticmethod
    def quote(sUrl):
        return quote(sUrl)

    @staticmethod
    def unquotePlus(sUrl):
        return unquote_plus(sUrl)

    @staticmethod
    def quotePlus(sUrl):
        return quote_plus(sUrl)

    @staticmethod
    def B64decode(text):
        import base64
        return base64.b64decode(text).decode('utf-8')


# xStream interner Log
class logger:
    @staticmethod
    def info(sInfo):
        logger.__writeLog(sInfo, cLogLevel=xbmc.LOGINFO)

    @staticmethod
    def debug(sInfo):
        logger.__writeLog(sInfo, cLogLevel=xbmc.LOGDEBUG)

    @staticmethod
    def warning(sInfo):
        logger.__writeLog(sInfo, cLogLevel=xbmc.LOGWARNING)

    @staticmethod
    def error(sInfo):
        logger.__writeLog(sInfo, cLogLevel=xbmc.LOGERROR)

    @staticmethod
    def fatal(sInfo):
        logger.__writeLog(sInfo, cLogLevel=xbmc.LOGFATAL)

    @staticmethod
    def __writeLog(sLog, cLogLevel=xbmc.LOGDEBUG):
        params = ParameterHandler()
        try:
            if params.exist('site'):
                site = params.getValue('site')
                sLog = "[%s] -> [%s]: %s" % (cConfig().getAddonInfo('name'), site, sLog)
            else:
                sLog = "[%s] %s" % (cConfig().getAddonInfo('name'), sLog)
            xbmc.log(sLog, cLogLevel)
        except Exception as e:
            xbmc.log('Logging Failure: %s' % e, cLogLevel)
            pass


class cUtil:
    @staticmethod
    def removeHtmlTags(sValue, sReplace=''):
        return re.compile(r'<.*?>').sub(sReplace, sValue)

    @staticmethod
    def unescape(text):
        # edit kasi 2024-11-26 so für py2/py3 oder für nur py3 unichr ersetzen durch chr
        try: unichr
        except NameError: unichr = chr

        def fixup(m):
            text = m.group(0)
            if not text.endswith(';'): text += ';'
            if text[:2] == '&#':
                try:
                    if text[:3] == '&#x':
                        return unichr(int(text[3:-1], 16))
                    else:
                        return unichr(int(text[2:-1]))
                except ValueError:
                    pass
            else:
                try:
                    text = unichr(name2codepoint[text[1:-1]])
                except KeyError:
                    pass
            return text

        if isinstance(text, str):
            try:
                text = text.decode('utf-8')
            except Exception:
                try:
                    text = text.decode('utf-8', 'ignore')
                except Exception:
                    pass
        return re.compile('&(\\w+;|#x?\\d+;?)').sub(fixup, text.strip())

    @staticmethod
    def cleanse_text(text):
        if text is None: text = ''
        text = cUtil.removeHtmlTags(text)
        return text

    @staticmethod
    def evp_decode(cipher_text, passphrase, salt=None):
        if not salt:
            salt = cipher_text[8:16]
            cipher_text = cipher_text[16:]
        key, iv = cUtil.evpKDF(passphrase, salt)
        decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
        plain_text = decrypter.feed(cipher_text)
        plain_text += decrypter.feed()
        return plain_text.decode("utf-8")

    @staticmethod
    def evpKDF(pwd, salt, key_size=32, iv_size=16):
        temp = b''
        fd = temp
        while len(fd) < key_size + iv_size:
            h = hashlib.md5()
            h.update(temp + pwd + salt)
            temp = h.digest()
            fd += temp
        key = fd[0:key_size]
        iv = fd[key_size:key_size + iv_size]
        return key, iv
        
    @staticmethod
    def isSimilar(sSearch, sText, threshold=0.9):
        return (SequenceMatcher(None, sSearch, sText).ratio() >= threshold)

    @staticmethod
    @lru_cache(maxsize=200000)
    def get_seq_match_ratio(token1, token2):
        return SequenceMatcher(None, token1, token2).ratio()
    
    @staticmethod
    def isSimilarByToken(sSearch, sText, threshold=0.9):
        tokens_sSearch = sSearch.split()
        tokens_sText = sText.split()

        if not tokens_sSearch:
            return False

            # get_ratio = lambda a, b: SequenceMatcher(None, a, b).ratio()
        best_ratios = [
            max(cUtil.get_seq_match_ratio(token, token2) for token2 in tokens_sText)
            for token in tokens_sSearch
        ]
        return (sum(best_ratios) / len(best_ratios)) >= threshold

def valid_email(email): #ToDo: Funktion in Settings / Konten aktivieren
    # Überprüfen der EMail-Adresse mit dem Muster
    if re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$').match(email):
        return True
    else:
        return False

def getDNS(dns):
    status = 'Beschäftigt'
    loop = 1
    while status == 'Beschäftigt':
        if loop == 20:
            break
        status = xbmc.getInfoLabel(dns)
        xbmc.sleep(20)
        loop += 1
    return status

def getRepofromAddonsDB(addonID):
    from sqlite3 import dbapi2 as database
    from glob import glob
    chdir(path.join(translatePath('special://database/')))
    addonsDB = path.join(translatePath('special://database/'), sorted(glob("Addons*.db"), reverse=True)[0])
    dbcon = database.connect(addonsDB)
    dbcur = dbcon.cursor()
    select = ("SELECT origin FROM installed WHERE addonID = '%s'") % addonID
    dbcur.execute(select)
    match = dbcur.fetchone()
    dbcon.close()
    if match and len(match) > 0:
         repo = match[0]
    else:
        repo = ''
    return repo


class cCache(object):
    _win = None

    def __init__(self):
        # see https://kodi.wiki/view/Window_IDs
        self._win = xbmcgui.Window(10000)

    def __del__(self):
        del self._win

    def get(self, key, cache_time):
        cachedata = self._win.getProperty(key)

        if cachedata:
            cachedata = eval(cachedata)
            if time.time() - cachedata[0] < cache_time or cache_time < 0:
                return cachedata[1]
            else:
                self._win.clearProperty(key)

        return None
    
    def set(self, key, data):
        self._win.setProperty(key, repr((time.time(), data)))

    def clear(self):
        self._win.clearProperties()
