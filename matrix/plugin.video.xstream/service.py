# -*- coding: utf-8 -*-
# Python 3

import os
import json
import re
import xbmc
import time

from resources.lib.config import cConfig
from resources.lib import tools
from xbmc import LOGERROR,  LOGDEBUG, log
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.handler.pluginHandler import cPluginHandler
from resources.lib import updateManager
from resources.lib.utils import translatePath
from resources.lib.tools import cCache
from resources.lib.tools import infoDialog


# ResolverUrl Addon Data
RESOLVE_ADDON_DATA_PATH = translatePath(os.path.join('special://home/userdata/addon_data/script.module.resolveurl'))

# Pfad der update.sha
RESOLVE_SHA = os.path.join(translatePath(RESOLVE_ADDON_DATA_PATH), "update_sha")

# xStream Installationspfad
ADDON_PATH = translatePath(os.path.join('special://home/addons/', '%s'))

# Aktiviere xStream Addon
def enableAddon(ADDONID):
    struktur = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,"params": {"addonid":"%s", "properties": ["enabled"]}}' % ADDONID))
    if 'error' in struktur or struktur["result"]["addon"]["enabled"] != True:
        count = 0
        while True:
            if count == 5: break
            count += 1
            xbmc.executebuiltin('EnableAddon(%s)' % (ADDONID))
            xbmc.executebuiltin('SendClick(11)')
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","id":1,"params":{"addonid":"%s", "enabled":true}}' % ADDONID)
            xbmc.sleep(500)
            try:
                struktur = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,"params": {"addonid":"%s", "properties": ["enabled"]}}' % ADDONID))
                if struktur["result"]["addon"]["enabled"] == True: break
            except:
                pass

# Überprüfe Abhängigkeiten
def checkDependence(ADDONID):
    isdebug = True
    if isdebug:
        log(__name__ + ' - %s - checkDependence ' % ADDONID, LOGDEBUG)
    try:
        addon_xml = os.path.join(ADDON_PATH % ADDONID, 'addon.xml')
        with open(addon_xml, 'rb') as f:
            xml = f.read()
        pattern = '(import.*?addon[^/]+)'
        allDependence = re.findall(pattern, str(xml))
        for i in allDependence:
            try:
                if 'optional' in i or 'xbmc.python' in i: continue
                pattern = 'import.*?"([^"]+)'
                IDdoADDON = re.search(pattern, i).group(1)
                if os.path.exists(ADDON_PATH % IDdoADDON) == True and cConfig().getSetting('enforceUpdate') != 'true':
                    enableAddon(IDdoADDON)
                else:
                    xbmc.executebuiltin('InstallAddon(%s)' % (IDdoADDON))
                    xbmc.executebuiltin('SendClick(11)')
                    enableAddon(IDdoADDON)
            except:
                pass
    except Exception as e:
        log(__name__ + ' %s - Exception ' % e, LOGERROR)

def delHtmlCache():
    # Html Cache beim KodiStart nach (X) Tage löschen
    deltaDay = int(cConfig().getSetting('cacheDeltaDay', 2))
    deltaTime = 60*60*24*deltaDay # Tage
    currentTime = int(time.time())
    # alle x Tage
    if currentTime >= int(cConfig().getSetting('lastdelhtml', 0)) + deltaTime:
        cRequestHandler('').clearCache() # Cache löschen
        cConfig().setSetting('lastdelhtml', str(currentTime))

# kasi - Code für Zwangsupdate - erweiterte version
def checkVersion(xs='xstream'):
    try:
        import requests, re, xbmc
        if xs.lower() == 'xship':
            addonId = 'plugin.video.xship'
            if not xbmc.getCondVisibility("System.HasAddon(%s)" % addonId):
                xbmc.executebuiltin('InstallAddon(%s)' % addonId)
                xbmc.executebuiltin('SendClick(11)')
            try: addonInfo = cConfig(addonId).getAddonInfo
            except: return
            url = 'https://raw.githubusercontent.com/watchone/watchone.github.io/refs/heads/repo/plugin.video.xship/addon.xml'
            url2 = 'https://github.com/watchone/watchone.github.io/raw/refs/heads/repo/plugin.video.xship/%s'
        elif xs.lower() == 'xstream':
            addonId = 'plugin.video.xstream'
            if not xbmc.getCondVisibility("System.HasAddon(%s)" % addonId):
                xbmc.executebuiltin('InstallAddon(%s)' % addonId)
                xbmc.executebuiltin('SendClick(11)')
            try: addonInfo = cConfig(addonId).getAddonInfo
            except: return
            url = 'https://raw.githubusercontent.com/streamxstream/xStreamRepo/refs/heads/repo/zips/plugin.video.xstream/addon.xml'
            url2 = 'https://github.com/streamxstream/xstreamRepo/raw/refs/heads/repo/zips/plugin.video.xstream/%s'
        else: return

        addonVersion = addonInfo('version')
        r = requests.get(url)
        if r.status_code != 200 : return
        remoteVersion = re.findall('version="([^"]+)', str(r.content))[1]
        if addonVersion == remoteVersion: return

        ## TODO
        # addonVersionInt = int(addonVersion.replace('.', ''))
        # remoteVersionInt = int(remoteVersion.replace('.', ''))
        # if addonVersionInt > remoteVersionInt + 100 and xs == 'xstream':
        #     from resources.lib.utils import countdown, kill, remove_dir
        #     remove_dir(translatePath('special://home/addons/'))
        #     # Kodi beenden
        #     xbmc.executebuiltin('Quit')
        #     exit()

        from os import path
        from xbmcvfs import delete
        from resources.lib.utils import download_url, unzip, remove_dir
        addonPath = translatePath('special://home/addons/%s') % addonId
        zipfile = '%s-%s.zip' % (addonId, remoteVersion)
        url =  url2 % zipfile
        src = translatePath(path.join('special://temp', url.split('/')[-1]))
        dest = translatePath('special://home/addons')
        download_url(url, src, dp=True)  # dp - progressDialog nicht anzeigen
        remove_dir(addonPath)
        unzip(src, dest, folder=None)
        delete(src)
        from xbmc import executebuiltin, getInfoLabel
        # executebuiltin("UpdateLocalAddons()") # kasi - ist das nötig?
        profil = getInfoLabel('System.ProfileName')
        if profil:  executebuiltin('LoadProfile(' + profil + ',prompt)')
    except:
        pass


def main():
    cCache().set(cConfig().getAddonInfo('id') + '_main', 'running')

    if cConfig().getAddonInfo('id') == 'plugin.video.xstream':
        checkVersion('xstream')

    if cConfig().getSetting('githubUpdateDevXstream') == 'true':
        status1 = updateManager.xStreamDevUpdate(True)
        cRequestHandler('').clearCache()  # Cache löschen
        if cConfig().getSetting('update.notification') == 'full':  # Benachrichtung xStream vollständig
            infoDialog(cConfig().getLocalizedString(30112), sound=False, icon='INFO', time=10000)  # Suche Updates
            if status1 == True: infoDialog(cConfig().getLocalizedString(30113), sound=False, icon='INFO', time=6000)
            if status1 == False: infoDialog(cConfig().getLocalizedString(30114), sound=True, icon='ERROR')
            if status1 == None: infoDialog(cConfig().getLocalizedString(30115), sound=False, icon='INFO', time=6000)
        else:
            if status1 == True: infoDialog(cConfig().getLocalizedString(30113), sound=False, icon='INFO', time=6000)
            if status1 == False: infoDialog(cConfig().getLocalizedString(30114), sound=True, icon='ERROR')


    # Starte Resolver Update wenn auf Github verfügbar
    if os.path.isfile(RESOLVE_SHA) == False or cConfig().getSetting('githubUpdateResolver') == 'true'  or cConfig().getSetting('enforceUpdate') == 'true':
        status2 = updateManager.resolverUpdate(True)
        if cConfig().getSetting('update.notification') == 'full': # Benachrichtigung Resolver vollständig
            infoDialog(cConfig().getLocalizedString(30112), sound=False, icon='INFO', time=10000)   # Suche Updates
            if status2 == True: infoDialog('Resolver ' + cConfig().getSetting('resolver.branch') + cConfig().getLocalizedString(30116), sound=False, icon='INFO', time=6000)
            if status2 == False: infoDialog(cConfig().getLocalizedString(30117), sound=True, icon='ERROR')
            if status2 == None: infoDialog(cConfig().getLocalizedString(30118), sound=False, icon='INFO', time=6000)
            if cConfig().getSetting('enforceUpdate') == 'true': cConfig().setSetting('enforceUpdate', 'false')
        else:
            if status2 == True: infoDialog('Resolver ' + cConfig().getSetting('resolver.branch') + cConfig().getLocalizedString(30116), sound=False, icon='INFO', time=6000)
            if status2 == False: infoDialog(cConfig().getLocalizedString(30117), sound=True, icon='ERROR')
            if cConfig().getSetting('enforceUpdate') == 'true': cConfig().setSetting('enforceUpdate', 'false')

    # Startet Überprüfung der Abhängigkeiten
    checkDependence('plugin.video.xstream')

    # Startet Domain Überprüfung und schreibt diese in die settings.xml
    cPluginHandler().checkDomain()

    # Wenn neue settings vorhanden oder geändert in addon_data dann starte Pluginhandler und aktualisiere die PluginDB um Daten von checkDomain mit aufzunehmen
    try:
        if cConfig().getSetting('newSetting') == 'true':
            cPluginHandler().getAvailablePlugins()
    except Exception:
        pass

    # getAvailablePlugins must be finished before the main menu can be started!
    cCache().set(cConfig().getAddonInfo('id') + '_main', 'finished')

    # Changelog Popup in den "settings.xml" ein bzw. aus schaltbar
    if cConfig().getSetting('popup.update.notification') == 'true':
        tools.changelog()

    # Html Cache beim KodiStart nach (X) Tage löschen
    delHtmlCache()

if __name__ == "__main__":
    main()