# -*- coding: utf-8 -*-
# Python 3

import sys
import xbmc
import xbmcgui
import os
import time
import concurrent.futures
from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.handler.pluginHandler import cPluginHandler
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, log
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.gui.gui import cGui
from resources.lib.config import cConfig
from resources.lib.tools import logger, cParser, cCache

try:
    import resolveurl as resolver
except ImportError:
    # Resolver Fehlermeldung (bei defekten oder nicht installierten Resolver)
    xbmcgui.Dialog().ok(cConfig().getLocalizedString(30119), cConfig().getLocalizedString(30120))


def viewInfo(params):
    from resources.lib.tmdbinfo import WindowsBoxes
    parms = ParameterHandler()
    sCleanTitle = params.getValue('searchTitle')
    sMeta = parms.getValue('sMeta')
    sYear = parms.getValue('sYear')
    WindowsBoxes(sCleanTitle, sCleanTitle, sMeta, sYear)


def parseUrl():
    if xbmc.getInfoLabel('Container.PluginName') == 'plugin.video.osmosis':
        sys.exit()

    params = ParameterHandler()
    logger.info(params.getAllParameters())

    # If no function is set, we set it to the default "load" function
    if params.exist('function'):
        sFunction = params.getValue('function')
        if sFunction == 'spacer':
            return True
        elif sFunction == 'clearCache':
            cRequestHandler('dummy').clearCache()
            return
        elif sFunction == 'viewInfo':
            viewInfo(params)
            return
        elif sFunction == 'searchAlter':
            searchAlter(params)
            return
        elif sFunction == 'searchTMDB':
            searchTMDB(params)
            return
        elif sFunction == 'devUpdates':
            from resources.lib import updateManager
            updateManager.devUpdates()
            return
        elif sFunction == 'pluginInfo':
            cPluginHandler().pluginInfo()
            return
        elif sFunction == 'vod':
            vodGuiElements(sFunction)
            return
        elif sFunction == 'changelog':
            from resources.lib import tools
            cConfig().setSetting('changelog_version', '')
            tools.changelog()
            return
        elif sFunction == 'devWarning':
            from resources.lib import tools
            tools.devWarning()
            return
            
    elif params.exist('remoteplayurl'):
        try:
            remotePlayUrl = params.getValue('remoteplayurl')
            sLink = resolver.resolve(remotePlayUrl)
            if sLink:
                xbmc.executebuiltin('PlayMedia(' + sLink + ')')
            else:
                log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Could not play remote url %s ' % sLink, LOGNOTICE)
        except resolver.resolver.ResolverError as e:
            log(cConfig().getLocalizedString(30166) + ' -> [xstream]: ResolverError: %s' % e, LOGERROR)
        return
    else:
        sFunction = 'load'

    # Test if we should run a function on a special site
    if not params.exist('site'):
        # As a default if no site was specified, we run the default starting gui with all plugins
        showMainMenu(sFunction)
        return
    sSiteName = params.getValue('site')
    if params.exist('playMode'):
        from resources.lib.gui.hoster import cHosterGui
        url = False
        playMode = params.getValue('playMode')
        isHoster = params.getValue('isHoster')
        url = params.getValue('url')
        manual = params.exist('manual')

        if cConfig().getSetting('hosterSelect') == 'Auto' and playMode != 'jd' and playMode != 'jd2' and playMode != 'pyload' and not manual:
            cHosterGui().streamAuto(playMode, sSiteName, sFunction)
        else:
            cHosterGui().stream(playMode, sSiteName, sFunction, url)
        return

    log(cConfig().getLocalizedString(30166) + " -> [xstream]: Call function '%s' from '%s'" % (sFunction, sSiteName), LOGNOTICE)
    # If the hoster gui is called, run the function on it and return
    if sSiteName == 'cHosterGui':
        showHosterGui(sFunction)
    # If global search is called
    elif sSiteName == 'globalSearch':
        searchterm = False
        if params.exist('searchterm'):
            searchterm = params.getValue('searchterm')
        searchGlobal(searchterm)
    elif sSiteName == 'xStream':
        oGui = cGui()
        oGui.openSettings()
        # resolves strange errors in the logfile
        #oGui.updateDirectory()
        oGui.setEndOfDirectory()
        xbmc.executebuiltin('Action(ParentDir)')
    # Resolver Einstellungen im Hauptmenü
    elif sSiteName == 'resolver':
        oGui = cGui()
        resolver.display_settings()
        # resolves strange errors in the logfile
        oGui.setEndOfDirectory()
        xbmc.executebuiltin('Action(ParentDir)')
    # Manuelles Update im Hauptmenü
    elif sSiteName == 'devUpdates':
        from resources.lib import updateManager
        updateManager.devUpdates()
    # Plugin Infos    
    elif sSiteName == 'pluginInfo':
        cPluginHandler().pluginInfo()
    # Changelog anzeigen    
    elif sSiteName == 'changelog':
        from resources.lib import tools
        tools.changelog()
    # Dev Warnung anzeigen
    elif sSiteName == 'devWarning':
        from resources.lib import tools
        tools.devWarning()
    # VoD Menü Site Name
    elif sSiteName == 'vod':
        vodGuiElements(sFunction)
    # Unterordner der Einstellungen   
    elif sSiteName == 'settings':
        oGui = cGui()
        for folder in settingsGuiElements():
            oGui.addFolder(folder)
        oGui.setEndOfDirectory()
    else:
        # Else load any other site as plugin and run the function
        plugin = __import__(sSiteName, globals(), locals())
        function = getattr(plugin, sFunction)
        function()


def showMainMenu(sFunction):
    ART = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'art')
    addon_id = cConfig().getAddonInfo('id')
    start_time = time.time()
    # timeout for the startup status check = 60s
    while (startupStatus := cCache().get(addon_id + '_main', -1)) != 'finished' and time.time() - start_time <= 60:
        time.sleep(5)
    
    oGui = cGui()

    # Setzte die globale Suche an erste Stelle
    if cConfig().getSetting('GlobalSearchPosition') == 'true':
        oGui.addFolder(globalSearchGuiElement())

    oPluginHandler = cPluginHandler()
    aPlugins = oPluginHandler.getAvailablePlugins()
    if not aPlugins:
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: No activated Plugins found', LOGNOTICE)
        # Open the settings dialog to choose a plugin that could be enabled
        oGui.openSettings()
        oGui.updateDirectory()
    else:
        # Create a gui element for every plugin found
        for aPlugin in sorted(aPlugins, key=lambda k: k['id']):
            if 'vod_' in aPlugin['id']:
                continue
            oGuiElement = cGuiElement()
            oGuiElement.setTitle(aPlugin['name'])
            oGuiElement.setSiteName(aPlugin['id'])
            oGuiElement.setFunction(sFunction)
            if 'icon' in aPlugin and aPlugin['icon']:
                oGuiElement.setThumbnail(aPlugin['icon'])
            oGui.addFolder(oGuiElement)
        if cConfig().getSetting('GlobalSearchPosition') == 'false':
            oGui.addFolder(globalSearchGuiElement())
    # VoD Ordner im Hauptmenü anzeigen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30412))
    oGuiElement.setSiteName('vod')
    oGuiElement.setFunction(sFunction)
    oGuiElement.setThumbnail(os.path.join(ART, 'vod.png'))
    oGuiElement.setIcon(os.path.join(ART, 'settings.png'))
    oGui.addFolder(oGuiElement)

    if cConfig().getSetting('SettingsFolder') == 'true':
        # Einstellung im Menü mit Untereinstellungen
        oGuiElement = cGuiElement()
        oGuiElement.setTitle(cConfig().getLocalizedString(30041))
        oGuiElement.setSiteName('settings')
        oGuiElement.setFunction('showSettingsFolder')
        oGuiElement.setThumbnail(os.path.join(ART, 'settings.png'))
        oGui.addFolder(oGuiElement)
    else:
        for folder in settingsGuiElements():
            oGui.addFolder(folder)
    oGui.setEndOfDirectory()


def vodGuiElements(sFunction): # Vod Menü
    oGui = cGui()
    oPluginHandler = cPluginHandler()
    aPlugins = oPluginHandler.getAvailablePlugins() # Suche Plugins mit Pluginhandler
    if not aPlugins:
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: No activated Vod Plugins found', LOGNOTICE)
        # Öffne Einstellungen wenn keine VoD SitePlugins vorhanden
        oGui.openSettings()
        oGui.updateDirectory()
    else:
        # Erstelle ein gui element für alle gefundenen Siteplugins
        for aPlugin in sorted(aPlugins, key=lambda k: k['id']):
            #if cConfig().getSetting('indexVoDyes') == 'true': # Wenn VoD Menü True
            oGuiElement = cGuiElement()
            oGuiElement.setTitle(aPlugin['name'])
            oGuiElement.setSiteName(aPlugin['id'])
            if not 'vod_' in aPlugin['id']: continue # Blende alle SitePlugins ohne vod_ am Anfang aus
            oGuiElement.setFunction(sFunction)
            if 'icon' in aPlugin and aPlugin['icon']:
                oGuiElement.setThumbnail(aPlugin['icon'])
            oGui.addFolder(oGuiElement)
    oGui.setEndOfDirectory()

def settingsGuiElements():
    ART = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'art')

    # GUI Plugin Informationen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30267))
    oGuiElement.setSiteName('pluginInfo')
    oGuiElement.setFunction('pluginInfo')
    oGuiElement.setThumbnail(os.path.join(ART, 'plugin_info.png'))
    PluginInfo = oGuiElement


    # GUI xStream Einstellungen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30042))
    oGuiElement.setSiteName('xStream')
    oGuiElement.setFunction('display_settings')
    oGuiElement.setThumbnail(os.path.join(ART, 'xstream_settings.png'))
    xStreamSettings = oGuiElement

    # GUI Resolver Einstellungen
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30043))
    oGuiElement.setSiteName('resolver')
    oGuiElement.setFunction('display_settings')
    oGuiElement.setThumbnail(os.path.join(ART, 'resolveurl_settings.png'))
    resolveurlSettings = oGuiElement
    
    # GUI Nightly Updatemanager
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30121))
    oGuiElement.setSiteName('devUpdates')
    oGuiElement.setFunction('devUpdates')
    oGuiElement.setThumbnail(os.path.join(ART, 'manuel_update.png'))
    DevUpdateMan = oGuiElement
    return PluginInfo, xStreamSettings, resolveurlSettings, DevUpdateMan


def globalSearchGuiElement():
    ART = os.path.join(cConfig().getAddonInfo('path'), 'resources', 'art')

    # Create a gui element for global search
    oGuiElement = cGuiElement()
    oGuiElement.setTitle(cConfig().getLocalizedString(30040))
    oGuiElement.setSiteName('globalSearch')
    oGuiElement.setFunction('globalSearch')
    oGuiElement.setThumbnail(os.path.join(ART, 'search.png'))
    return oGuiElement


def showHosterGui(sFunction):
    from resources.lib.gui.hoster import cHosterGui
    oHosterGui = cHosterGui()
    function = getattr(oHosterGui, sFunction)
    function()
    return True


def searchGlobal(sSearchText=False):
	oGui = cGui()
	oGui.globalSearch = True
	oGui._collectMode = True

	if not sSearchText:
		sSearchText = oGui.showKeyBoard(sHeading=cConfig().getLocalizedString(30280))  # Bitte Suchbegriff eingeben
	if not sSearchText:
		oGui.setEndOfDirectory()
		return True

	aPlugins = cPluginHandler().getAvailablePlugins()
	dialog = xbmcgui.DialogProgress()
	dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))

	numPlugins = len(aPlugins)
	searchablePlugins = [pluginEntry for pluginEntry in aPlugins if pluginEntry['globalsearch'] not in ['false', '']]

	def worker(pluginEntry):
		log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Searching for %s at %s' % (sSearchText, pluginEntry['id']),LOGNOTICE)
		_pluginSearch(pluginEntry, sSearchText, oGui)
		return pluginEntry['name']

	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		future_to_plugin = {executor.submit(worker, pluginEntry): pluginEntry for pluginEntry in searchablePlugins}

		for count, future in enumerate(concurrent.futures.as_completed(future_to_plugin)):
			pluginEntry = future_to_plugin[future]
			if dialog.iscanceled():
				oGui.setEndOfDirectory()
				return
			try: pluginName = future.result()
			except Exception as e:
				pluginName = pluginEntry['name']
				log(f"Fehler bei Plugin {pluginName}: {str(e)}", LOGERROR)
			progress = (count + 1) * 50 // len(searchablePlugins)
			dialog.update(progress, pluginName + cConfig().getLocalizedString(30125))
	dialog.close()

	# Ergebnisse anzeigen
	oGui._collectMode = False
	total = len(oGui.searchResults)
	dialog = xbmcgui.DialogProgress()
	dialog.create(cConfig().getLocalizedString(30126), cConfig().getLocalizedString(30127))

	for count, result in enumerate(sorted(oGui.searchResults, key=lambda k: k['guiElement'].getSiteName()), 1):
		if dialog.iscanceled():
			oGui.setEndOfDirectory()
			return
		oGui.addFolder(result['guiElement'], result['params'], bIsFolder=result['isFolder'], iTotal=total)
		dialog.update(count * 100 // total, str(count) + cConfig().getLocalizedString(30128) + str(total) + ': ' + result['guiElement'].getTitle())

	dialog.close()
	oGui.setView()
	oGui.setEndOfDirectory()
	return True

def searchAlter(params):
    searchTitle = params.getValue('searchTitle')
    searchImdbId = params.getValue('searchImdbID')
    searchYear = params.getValue('searchYear')

    # Jahr aus dem Titel extrahieren
    if ' (19' in searchTitle or ' (20' in searchTitle:
        isMatch, aYear = cParser.parse(searchTitle, '(.*?) \((\d{4})\)')
        if isMatch:
            searchTitle = aYear[0][0]
            if not searchYear:
                searchYear = str(aYear[0][1])

    # Staffel oder Episodenkennung abschneiden
    for token in [' S0', ' E0', ' - Staffel', ' Staffel']:
        if token in searchTitle:
            searchTitle = searchTitle.split(token)[0].strip()
            break

    oGui = cGui()
    oGui.globalSearch = True
    oGui._collectMode = True
    aPlugins = cPluginHandler().getAvailablePlugins()

    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))

    searchablePlugins = [
        pluginEntry for pluginEntry in aPlugins
        if pluginEntry['globalsearch'] not in ['false', '']
    ]

    def worker(pluginEntry):
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Searching for ' + searchTitle + pluginEntry['id'], LOGNOTICE)
        _pluginSearch(pluginEntry, searchTitle, oGui)
        return pluginEntry['name']

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_plugin = {executor.submit(worker, plugin): plugin for plugin in searchablePlugins}

        for count, future in enumerate(concurrent.futures.as_completed(future_to_plugin)):
            plugin = future_to_plugin[future]
            if dialog.iscanceled():
                oGui.setEndOfDirectory()
                return
            try:
                name = future.result()
            except Exception as e:
                name = plugin['name']
                log(f"Fehler bei Plugin {name}: {str(e)}", LOGERROR)
            dialog.update((count + 1) * 50 // len(searchablePlugins) + 50, name + cConfig().getLocalizedString(30125))

    dialog.close()

    # Ergebnisse filtern
    filteredResults = []
    for result in oGui.searchResults:
        guiElement = result['guiElement']
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Site: %s Titel: %s' % (guiElement.getSiteName(), guiElement.getTitle()), LOGNOTICE)
        if searchTitle not in guiElement.getTitle():
            continue
        if guiElement._sYear and searchYear and guiElement._sYear != searchYear:
            continue
        if searchImdbId and guiElement.getItemProperties().get('imdbID') != searchImdbId:
            continue
        filteredResults.append(result)

    oGui._collectMode = False
    total = len(filteredResults)
    for result in sorted(filteredResults, key=lambda k: k['guiElement'].getSiteName()):
        oGui.addFolder(result['guiElement'], result['params'], bIsFolder=result['isFolder'], iTotal=total)

    oGui.setView()
    oGui.setEndOfDirectory()
    xbmc.executebuiltin('Container.Update')
    return True

def searchTMDB(params):
    sSearchText = params.getValue('searchTitle')
    oGui = cGui()
    oGui.globalSearch = True
    oGui._collectMode = True

    if not sSearchText:
        oGui.setEndOfDirectory()
        return True

    aPlugins = cPluginHandler().getAvailablePlugins()

    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30122), cConfig().getLocalizedString(30123))

    searchablePlugins = [
        pluginEntry for pluginEntry in aPlugins
        if pluginEntry['globalsearch'] != 'false'
    ]

    def worker(pluginEntry):
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: Searching for %s at %s' % (sSearchText, pluginEntry['id']), LOGNOTICE)
        _pluginSearch(pluginEntry, sSearchText, oGui)
        return pluginEntry['name']

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_plugin = {executor.submit(worker, plugin): plugin for plugin in searchablePlugins}

        for count, future in enumerate(concurrent.futures.as_completed(future_to_plugin)):
            plugin = future_to_plugin[future]
            if dialog.iscanceled():
                oGui.setEndOfDirectory()
                return
            try:
                name = future.result()
            except Exception as e:
                name = plugin['name']
                log(f"Fehler bei Plugin {name}: {str(e)}", LOGERROR)
            dialog.update((count + 1) * 50 // len(searchablePlugins) + 50, name + cConfig().getLocalizedString(30125))

    dialog.close()

    oGui._collectMode = False
    total = len(oGui.searchResults)

    dialog = xbmcgui.DialogProgress()
    dialog.create(cConfig().getLocalizedString(30126), cConfig().getLocalizedString(30127))

    for count, result in enumerate(sorted(oGui.searchResults, key=lambda k: k['guiElement'].getSiteName()), 1):
        if dialog.iscanceled():
            oGui.setEndOfDirectory()
            return
        oGui.addFolder(result['guiElement'], result['params'], bIsFolder=result['isFolder'], iTotal=total)
        dialog.update(count * 100 // total, str(count) + cConfig().getLocalizedString(30128) + str(total) + ': ' + result['guiElement'].getTitle())

    dialog.close()
    oGui.setView()
    oGui.setEndOfDirectory()
    return True


def _pluginSearch(pluginEntry, sSearchText, oGui):
    try:
        plugin = __import__(pluginEntry['id'], globals(), locals())
        function = getattr(plugin, '_search')
        function(oGui, sSearchText)
    except Exception:
        log(cConfig().getLocalizedString(30166) + ' -> [xstream]: ' + pluginEntry['name'] + ': search failed', LOGERROR)
        import traceback
        log(traceback.format_exc())