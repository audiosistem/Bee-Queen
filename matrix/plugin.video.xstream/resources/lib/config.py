# -*- coding: utf-8 -*-
# Python 3

import xbmcaddon
import resolveurl as resolver
import threading

from urllib.parse import urlparse
from xbmc import LOGWARNING, log

class cConfig:
    _instances = {}  # Cache for addon_id -> cConfig instance
    _addon_cache = {}  # Cache for addon_id -> xbmcaddon.Addon instance
    _settings_lock = threading.Lock()

    # singleton implementation
    def __new__(cls, *args, **kwargs):
        addon_id = kwargs.get('addon_id') or (args[0] if args else xbmcaddon.Addon().getAddonInfo('id'))
        if addon_id not in cls._instances:
            instance = super(cConfig, cls).__new__(cls)
            instance._addon_id = addon_id
            if addon_id not in cls._addon_cache:
                cls._addon_cache[addon_id] = xbmcaddon.Addon(addon_id)
            instance.__addon = cls._addon_cache[addon_id]
            instance.__aLanguage = instance.__addon.getLocalizedString
            cls._instances[addon_id] = instance
        return cls._instances[addon_id]
    
    def showSettingsWindow(self):
        self.__addon.openSettings()

    def getSetting(self, sName, default=''):
        result = self.__addon.getSetting(sName)
        if result:
            return result
        else:
            return default
        
    def getSettingString(self, sName, default=''):
        result = self.__addon.getSetting(sName)
        if result:
            return str(result)
        else:
            return default

    def setSetting(self, id, value):
        if id and value:
            with cConfig._settings_lock:
                self.__addon.setSetting(id, value)

    def getAddonInfo(self, sName):
        result = self.__addon.getAddonInfo(sName)
        if result:
            return result
        else:
            return ''

    def getLocalizedString(self, sCode):
        return self.__aLanguage(sCode)
        
    def isBlockedHoster(self, domain, checkResolver=True ):
        domain = urlparse(domain).path if urlparse(domain).hostname == None else urlparse(domain).hostname
        hostblockDict = ['flashx','streamlare','evoload', 'hd-stream', 'vivo']  # permanenter Block
        blockedHoster = cConfig().getSetting('blockedHoster').split(',')  # aus setting.xml blockieren
        if len(blockedHoster) <= 1: blockedHoster = cConfig().getSetting('blockedHoster').split()
        for i in blockedHoster: hostblockDict.append(i.lower())
        for i in hostblockDict:
            if i in domain.lower() or i.split('.')[0] in domain.lower(): return True, domain
        if checkResolver:   # Überprüfung in resolveUrl
            if resolver.relevant_resolvers(domain=domain) == []:
                log('[xStream] -> [isblockedHoster]: In resolveUrl no domain for url: %s' % domain, LOGWARNING)
                return True, domain    # Domain nicht in resolveUrl gefunden
        return False, domain