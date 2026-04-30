# -*- coding: utf-8 -*-
# Python 3

import json
import os
import sys
import xbmc

from resources.lib.config import cConfig
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, log
from resources.lib import utils
from resources.lib.handler.requestHandler import cRequestHandler
from urllib.parse import urlparse
from xbmcgui import Dialog
from xbmcvfs import translatePath
from resources.lib.tools import platform, infoDialog, getDNS, getRepofromAddonsDB


ADDON_PATH = translatePath(os.path.join('special://home/addons/', '%s'))

class cPluginHandler:
    def __init__(self):
        self.rootFolder = translatePath(cConfig().getAddonInfo('path'))
        self.settingsFile = os.path.join(self.rootFolder, 'resources', 'settings.xml')
        self.profilePath = translatePath(cConfig().getAddonInfo('profile'))
        self.pluginDBFile = os.path.join(self.profilePath, 'pluginDB')

        log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: profile folder: %s' % self.profilePath, LOGNOTICE)
        log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: root folder: %s' % self.rootFolder, LOGNOTICE)
        self.defaultFolder = os.path.join(self.rootFolder, 'sites')
        log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: default sites folder: %s' % self.defaultFolder, LOGNOTICE)


    def getAvailablePlugins(self):
        global globalSearchStatus
        pluginDB = self.__getPluginDB()
        # default plugins
        update = False
        fileNames = self.__getFileNamesFromFolder(self.defaultFolder)
        for fileName in fileNames:
            plugin = {'name': '', 'identifier': '', 'icon': '', 'domain': '', 'globalsearch': '', 'modified': 0}
            if fileName in pluginDB:
                plugin.update(pluginDB[fileName])
            try:
                modTime = os.path.getmtime(os.path.join(self.defaultFolder, fileName + '.py'))
            except OSError:
                modTime = 0
            try:
                globalSearchStatus = cConfig().getSetting('global_search_' + fileName)
            except Exception:
                pass
            if fileName not in pluginDB or modTime > plugin['modified'] or globalSearchStatus:
                log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: load plugin Informations for ' + str(fileName), LOGNOTICE)
                # try to import plugin
                pluginData = self.__getPluginData(fileName, self.defaultFolder)
                if pluginData:
                    pluginData['globalsearch'] = globalSearchStatus
                    pluginData['modified'] = modTime # Wenn Datei (Zeitstempel) verändert, werden die Daten aktualisiert
                    pluginDB[fileName] = pluginData
                    update = True
        # check pluginDB for obsolete entries
        deletions = []
        for pluginID in pluginDB:
            if pluginID not in fileNames:
                deletions.append(pluginID)
        for id in deletions:
            del pluginDB[id]
        if update or deletions:
        #    self.__updateSettings(pluginDB) ToDo: Routine ist noch nicht fertig, daher deaktiviert
            self.__updatePluginDB(pluginDB) # Aktualisiert PluginDB in Addon_data
            log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: PluginDB informations updated.', LOGNOTICE)
        return self.getAvailablePluginsFromDB()


    def getAvailablePluginsFromDB(self):
        plugins = []
        iconFolder = os.path.join(self.rootFolder, 'resources', 'art', 'sites')
        pluginDB = self.__getPluginDB() # Erstelle PluginDB
        # PluginID = Siteplugin Name
        for pluginID in pluginDB:
            plugin = pluginDB[pluginID] # Aus PluginDB lese PluginID
            pluginSettingsName = 'plugin_%s' % pluginID # Name des Siteplugins
            plugin['id'] = pluginID
            if 'icon' in plugin:
                plugin['icon'] = os.path.join(iconFolder, plugin['icon'])
            else:
                plugin['icon'] = ''
            # existieren zu diesem plugin die an/aus settings
            if cConfig().getSetting(pluginSettingsName) == 'true': # Lese aus settings.xml welche Plugins eingeschaltet sind
                plugins.append(plugin)
        return plugins


    def __updatePluginDB(self, data): # Aktualisiere PluginDB
        if not os.path.exists(self.profilePath):
            os.makedirs(self.profilePath)
        file = open(self.pluginDBFile, 'w')
        json.dump(data, file)
        file.close()


    def __getPluginDB(self): # Erstelle PluginDB
        if not os.path.exists(self.pluginDBFile): # Wenn Datei nicht verfügbar dann erstellen
            return dict()
        file = open(self.pluginDBFile, 'r')
        try:
            data = json.load(file)
        except ValueError:
            log(cConfig().getLocalizedString(30166) + ' -> [pluginHandler]: pluginDB seems corrupt, creating new one', LOGERROR)
            data = dict()
        file.close()
        return data

    def __updateSettings(self, pluginDB):
        """
        Aktualisiert die settings.xml basierend auf den verfügbaren Plugins.
        Entfernt Plugins, die nicht mehr existieren, und behält die saubere Formatierung bei.

        Args:
            pluginDB: Dictionary mit Plugin-Informationen
        """
        import os
        import shutil
        import xml.etree.ElementTree as ET

        if not os.path.exists(self.settingsFile):
            return

        try:
            # Backup der aktuellen settings.xml erstellen
            backup_file = f"{self.settingsFile}.backup"
            shutil.copy2(self.settingsFile, backup_file)

            # XML-Datei mit ElementTree parsen
            tree = ET.parse(self.settingsFile)
            root = tree.getroot()

            # Hauptsektion für xstream Plugin finden
            xstream_section = None
            for section in root.findall('section'):
                if section.get('id') == 'plugin.video.xstream':
                    xstream_section = section
                    break

            if not xstream_section:
                return

            # Liste der verfügbaren Plugins aus pluginDB
            available_plugins = [p for p in pluginDB.keys() if p != 'globalSearch']

            # VoD-Plugins identifizieren
            vod_plugins = [p for p in available_plugins if p.startswith('vod_')]

            # Spezielle Plugins
            special_plugins = ['dokus', 'filmpalast', 'internetarchive', 'kids_tube']
            special_plugins = [p for p in special_plugins if p in available_plugins]

            # Normale Plugins (keine speziellen oder VOD)
            normal_plugins = [p for p in available_plugins
                              if p not in special_plugins
                              and p not in vod_plugins]

            # Sortieren für konsistente Reihenfolge
            normal_plugins.sort()

            # Hälfte für die Verteilung auf die Kategorien
            half_point = len(normal_plugins) // 2

            # Plugin-Listen für jede Kategorie
            indexsite1_plugins = special_plugins + normal_plugins[:half_point]
            indexsite2_plugins = normal_plugins[half_point:]

            # Kategorien finden
            for category in xstream_section.findall('category'):
                category_id = category.get('id')

                if category_id == 'indexsite1':
                    # Verarbeite indexsite1 Kategorie
                    self._update_category_plugins(category, indexsite1_plugins, pluginDB)

                elif category_id == 'indexsite2':
                    # Verarbeite indexsite2 Kategorie
                    self._update_category_plugins(category, indexsite2_plugins, pluginDB)

                elif category_id == 'indexsiteVoD':
                    # Verarbeite indexsiteVoD Kategorie
                    self._update_category_plugins(category, vod_plugins, pluginDB)

            # 1. Korrektur: Entfernen des fehlerhaften '>' in der filmpalast.domain Einstellung
            # XML als String holen
            import io
            xml_string = io.StringIO()
            tree.write(xml_string, encoding='unicode')
            content = xml_string.getvalue()
            content = content.replace('</dependencies>&gt;', '</dependencies>')

            # Schreiben der korrigierten XML-Datei
            with open(self.settingsFile, 'w', encoding='utf-8') as f:
                f.write('<?xml version=\'1.0\' encoding=\'utf-8\'?>\n' + content)

            xbmc.log(f'settings.xml erfolgreich aktualisiert. Plugins entfernt: {self._removed_plugins}', LOGNOTICE)

        except Exception as e:
            # Bei Fehler das Backup wiederherstellen
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, self.settingsFile)
            xbmc.log(f'Fehler beim Aktualisieren der settings.xml: {str(e)}', LOGNOTICE)

    def _update_category_plugins(self, category, plugin_list, pluginDB):
        """
        Aktualisiert die Plugin-Gruppen in einer Kategorie.
        Entfernt Plugins, die nicht in der plugin_list sind.

        Args:
            category: XML-Element der Kategorie
            plugin_list: Liste der verfügbaren Plugins für diese Kategorie
            pluginDB: Dictionary mit Plugin-Informationen
        """
        # Verfolgung entfernter Plugins
        self._removed_plugins = []

        # Vorhandene Plugin-Gruppen prüfen
        groups_to_remove = []
        for group in category.findall('group'):
            group_id = group.get('id')

            # Spezialfall für VoD-Plugins in der VoD-Kategorie
            if category.get('id') == 'indexsiteVoD' and group_id.startswith('plugin_'):
                # Extrahiere Plugin-ID ohne 'plugin_' Präfix
                plugin_id = group_id[7:] if group_id.startswith('plugin_') else group_id
                if plugin_id not in plugin_list:
                    groups_to_remove.append(group)
                    self._removed_plugins.append(plugin_id)
            # Normale Plugins
            elif group_id not in plugin_list:
                groups_to_remove.append(group)
                self._removed_plugins.append(group_id)

        # Entfernen der nicht mehr vorhandenen Plugins
        for group in groups_to_remove:
            category.remove(group)

        # Hinzufügen fehlender Plugins
        existing_group_ids = [g.get('id') for g in category.findall('group')]

        for plugin_id in plugin_list:
            # Spezialfall für VoD-Plugins in der VoD-Kategorie
            if category.get('id') == 'indexsiteVoD':
                group_id = f'plugin_{plugin_id}'
            else:
                group_id = plugin_id

            if group_id not in existing_group_ids:
                # Plugin hinzufügen, falls es noch nicht existiert
                if plugin_id in pluginDB:
                    if plugin_id in ['dokus', 'kids_tube', 'filmpalast', 'internetarchive']:
                        self._add_special_plugin(category, plugin_id, pluginDB[plugin_id])
                    elif category.get('id') == 'indexsiteVoD':
                        self._add_vod_plugin(category, plugin_id)
                    else:
                        self._add_normal_plugin(category, plugin_id, pluginDB[plugin_id])

    def _add_normal_plugin(self, category, plugin_id, plugin_data):
        """
        Fügt ein normales Plugin zur Kategorie hinzu.

        Args:
            category: XML-Element der Kategorie
            plugin_id: ID des Plugins
            plugin_data: Daten des Plugins
        """
        import xml.etree.ElementTree as ET

        # Plugin-Name (Anzeigename)
        plugin_name = plugin_data.get('name', plugin_id)

        # Gruppe erstellen
        group = ET.SubElement(category, 'group', id=plugin_id, label=plugin_name)

        # Plugin aktivieren/deaktivieren
        setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}', type='boolean', label='30050', help='30411')
        level = ET.SubElement(setting, 'level')
        level.text = '0'
        default = ET.SubElement(setting, 'default')
        default.text = 'True'
        control = ET.SubElement(setting, 'control', type='toggle')

        # Globale Suche
        setting = ET.SubElement(group, 'setting', id=f'global_search_{plugin_id}', type='boolean', label='30052')
        level = ET.SubElement(setting, 'level')
        level.text = '0'
        default = ET.SubElement(setting, 'default')
        default.text = 'True'

        dependencies = ET.SubElement(setting, 'dependencies')
        dependency = ET.SubElement(dependencies, 'dependency', type='enable', operator='!is',
                                   setting=f'plugin_{plugin_id}')
        dependency.text = 'False'

        control = ET.SubElement(setting, 'control', type='toggle')

    def _add_special_plugin(self, category, plugin_id, plugin_data):
        """
        Fügt ein spezielles Plugin (dokus, kids_tube, filmpalast, internetarchive) zur Kategorie hinzu.

        Args:
            category: XML-Element der Kategorie
            plugin_id: ID des Plugins
            plugin_data: Daten des Plugins
        """
        import xml.etree.ElementTree as ET

        # Label-Code für das Plugin
        label_codes = {
            'dokus': '30505',
            'filmpalast': '30702',
            'internetarchive': '30712',
            'kids_tube': '30719'
        }

        label = label_codes.get(plugin_id, plugin_data.get('name', plugin_id))

        # Gruppe erstellen
        group = ET.SubElement(category, 'group', id=plugin_id, label=label)

        # Haupteinstellung
        setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}', type='boolean', label='30050', help='30411')
        level = ET.SubElement(setting, 'level')
        level.text = '0'
        default = ET.SubElement(setting, 'default')
        default.text = 'False' if plugin_id in ['dokus', 'internetarchive', 'kids_tube'] else 'True'
        control = ET.SubElement(setting, 'control', type='toggle')

        # Spezifische Einstellungen für bestimmte Plugins
        if plugin_id in ['dokus', 'kids_tube']:
            # YouTube-Einstellungen
            setting = ET.SubElement(group, 'setting', id=f'{plugin_id}.youtube', type='action', label='30431', help='')
            level = ET.SubElement(setting, 'level')
            level.text = '0'
            data = ET.SubElement(setting, 'data')
            data.text = 'Addon.OpenSettings(plugin.video.youtube)'
            control = ET.SubElement(setting, 'control', type='button', format='action')
            close = ET.SubElement(control, 'close')
            close.text = 'true'

            dependencies = ET.SubElement(setting, 'dependencies')
            dependency = ET.SubElement(dependencies, 'dependency', type='visible', setting=f'plugin_{plugin_id}')
            dependency.text = 'true'

        # Globale Suche
        visible = 'False' if plugin_id in ['dokus', 'kids_tube'] else None

        setting = ET.SubElement(group, 'setting', id=f'global_search_{plugin_id}', type='boolean', label='30052')
        level = ET.SubElement(setting, 'level')
        level.text = '0'
        default = ET.SubElement(setting, 'default')
        default.text = 'False' if plugin_id in ['dokus', 'internetarchive', 'kids_tube'] else 'True'

        if visible:
            vis = ET.SubElement(setting, 'visible')
            vis.text = visible

        dependencies = ET.SubElement(setting, 'dependencies')
        dependency = ET.SubElement(dependencies, 'dependency', type='enable', operator='!is',
                                   setting=f'plugin_{plugin_id}')
        dependency.text = 'False'

        control = ET.SubElement(setting, 'control', type='toggle')

        # Spezifische Einstellungen für Filmpalast
        if plugin_id == 'filmpalast':
            # Domain-Überprüfung
            setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}_checkDomain', type='boolean',
                                    label='30277')
            level = ET.SubElement(setting, 'level')
            level.text = '3'
            default = ET.SubElement(setting, 'default')
            default.text = 'True'

            dependencies = ET.SubElement(setting, 'dependencies')
            dependency = ET.SubElement(dependencies, 'dependency', type='enable', operator='!is',
                                       setting=f'plugin_{plugin_id}')
            dependency.text = 'false'
            dependency = ET.SubElement(dependencies, 'dependency', type='visible', operator='!is',
                                       setting=f'plugin_{plugin_id}')
            dependency.text = 'false'

            control = ET.SubElement(setting, 'control', type='toggle')

            # Domain-Einstellung
            setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}.domain', type='string', label='30278',
                                    help='')
            level = ET.SubElement(setting, 'level')
            level.text = '3'
            default = ET.SubElement(setting, 'default')

            constraints = ET.SubElement(setting, 'constraints')
            allowempty = ET.SubElement(constraints, 'allowempty')
            allowempty.text = 'true'

            dependencies = ET.SubElement(setting, 'dependencies')
            dependency = ET.SubElement(dependencies, 'dependency', type='enable', operator='!is',
                                       setting=f'plugin_{plugin_id}')
            dependency.text = 'false'
            dependency = ET.SubElement(dependencies, 'dependency', type='visible', operator='!is',
                                       setting=f'plugin_{plugin_id}')
            dependency.text = 'false'

            control = ET.SubElement(setting, 'control', type='edit', format='string')
            heading = ET.SubElement(control, 'heading')
            heading.text = '30278'

        # Status-Setting für bestimmte Plugins
        if plugin_id in ['filmpalast', 'internetarchive']:
            setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}_status', type='string', label='Dummy',
                                    help='')
            visible = ET.SubElement(setting, 'visible')
            visible.text = 'false'
            default = ET.SubElement(setting, 'default')
            default.text = 'true'
            control = ET.SubElement(setting, 'control', type='toggle')

    def _add_vod_plugin(self, category, plugin_id):
        """
        Fügt ein VoD-Plugin zur VoD-Kategorie hinzu.

        Args:
            category: XML-Element der Kategorie
            plugin_id: ID des Plugins
        """
        import xml.etree.ElementTree as ET

        # Label-Codes für VoD-Plugins
        vod_label_map = {
            'vod_huhu': '30790',
            'vod_kool': '30791',
            'vod_oha': '30792',
            'vod_vavoo': '30793'
        }

        label = vod_label_map.get(plugin_id, plugin_id)

        # Gruppe erstellen
        group = ET.SubElement(category, 'group', id=f'plugin_{plugin_id}', label=label)

        # Haupteinstellung
        setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}', type='boolean', label='30050', help='')
        level = ET.SubElement(setting, 'level')
        level.text = '0'
        default = ET.SubElement(setting, 'default')
        default.text = 'True'
        control = ET.SubElement(setting, 'control', type='toggle')

        # Globale Suche
        setting = ET.SubElement(group, 'setting', id=f'global_search_{plugin_id}', type='boolean', label='30052')
        level = ET.SubElement(setting, 'level')
        level.text = '0'
        default = ET.SubElement(setting, 'default')
        default.text = 'True'

        dependencies = ET.SubElement(setting, 'dependencies')
        dependency = ET.SubElement(dependencies, 'dependency', type='enable', operator='!is',
                                   setting=f'plugin_{plugin_id}')
        dependency.text = 'false'

        control = ET.SubElement(setting, 'control', type='toggle')

        # Status-Setting
        setting = ET.SubElement(group, 'setting', id=f'plugin_{plugin_id}_status', type='string', label='Dummy',
                                help='')
        visible = ET.SubElement(setting, 'visible')
        visible.text = 'false'
        default = ET.SubElement(setting, 'default')
        default.text = 'true'
        control = ET.SubElement(setting, 'control', type='toggle')


    def __getFileNamesFromFolder(self, sFolder): # Hole Namen vom Dateiname.py
        aNameList = []
        items = os.listdir(sFolder)
        for sItemName in items:
            if sItemName.endswith('.py'):
                sItemName = os.path.basename(sItemName[:-3])
                aNameList.append(sItemName)
        return aNameList


    def __getPluginData(self, fileName, defaultFolder): # Hole Plugin Daten aus dem Siteplugin
        pluginData = {}
        if not defaultFolder in sys.path: sys.path.append(defaultFolder)
        try:
            plugin = __import__(fileName, globals(), locals())
            pluginData['name'] = plugin.SITE_NAME
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + " -> [pluginHandler]: Can't import plugin: %s" % fileName, LOGERROR)
            return False
        try:
            pluginData['identifier'] = plugin.SITE_IDENTIFIER
        except Exception:
            pass
        try:
            pluginData['icon'] = plugin.SITE_ICON
        except Exception:
            pass
        try:
            pluginData['domain'] = plugin.DOMAIN
        except Exception:
            pass
        try:
            pluginData['globalsearch'] = plugin.SITE_GLOBAL_SEARCH
        except Exception:
            pluginData['globalsearch'] = True
            pass
        return pluginData


    def __getPluginDataIndex(self, fileName, defaultFolder): # Hole Plugin Daten aus dem Siteplugin
        pluginData = {}
        if not defaultFolder in sys.path: sys.path.append(defaultFolder)
        try:
            plugin = __import__(fileName, globals(), locals())
            pluginData['name'] = plugin.SITE_NAME
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + " -> [pluginHandler]: Can't import plugin: %s" % fileName, LOGERROR)
            return False
        try:
            pluginData['active'] = plugin.ACTIVE
        except Exception:
            pass
        try:
            pluginData['domain'] = plugin.DOMAIN
        except Exception:
            pass
        try:
            pluginData['status'] = plugin.STATUS
            if '403' <= pluginData['status'] <= '503':
                pluginData['status'] = pluginData['status'] + ' - ' + cConfig().getLocalizedString(30429)
            elif '300' <= pluginData['status'] <= '400':
                pluginData['status'] = pluginData['status'] + ' - ' + cConfig().getLocalizedString(30428)
            elif pluginData['status'] == '200':
                pluginData['status'] = pluginData['status'] + ' - ' + cConfig().getLocalizedString(30427)
        except Exception:
            pass
        try:
            pluginData['globalsearch'] = plugin.SITE_GLOBAL_SEARCH
        except Exception:
            pluginData['globalsearch'] = True
            pass
        return pluginData


    def __getPluginDataDomain(self, fileName, defaultFolder): # Hole Plugin Daten für Domains
        pluginDataDomain = {}
        if not defaultFolder in sys.path: sys.path.append(defaultFolder)
        try:
            plugin = __import__(fileName, globals(), locals())
            pluginDataDomain['identifier'] = plugin.SITE_IDENTIFIER
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + " -> [pluginHandler]: Can't import plugin: %s" % fileName, LOGERROR)
            return False
        try:
            pluginDataDomain['domain'] = plugin.DOMAIN
        except Exception:
            pass
        return pluginDataDomain

    # Plugin Support Informationen
    def pluginInfo(self):
        # Erstelle Liste mit den Indexseiten Informationen
        list_of_plugins = []
        fileNames = self.__getFileNamesFromFolder(self.defaultFolder) # Hole Plugins aus xStream
        for fileName in fileNames:
            pluginData = self.__getPluginDataIndex(fileName, self.defaultFolder) # Hole Plugin Daten
            list_of_plugins.append(pluginData)
        result_list = [''.join([f"{key}:  {value}\n" for key, value in dictionary.items()]) for dictionary in list_of_plugins]
        # String Übersetzungen
        result_string = '\n'.join(result_list)
        result_string = result_string.replace('name', cConfig().getLocalizedString(30423))
        result_string = result_string.replace('active', cConfig().getLocalizedString(30430))
        result_string = result_string.replace('domain', cConfig().getLocalizedString(30424))
        result_string = result_string.replace('status', cConfig().getLocalizedString(30425))
        result_string = result_string.replace('globalsearch', cConfig().getLocalizedString(30426))
        result_string = result_string.replace('True', cConfig().getLocalizedString(30418))
        result_string = result_string.replace('False', cConfig().getLocalizedString(30419))
        result_string = result_string.replace('true', cConfig().getLocalizedString(30418))
        result_string = result_string.replace('false', cConfig().getLocalizedString(30419))
        list_of_PluginData = (result_string) # Ergebnis der Liste
        # Settings Abragen
        if cConfig().getSetting('githubUpdateResolver') == 'true':  # Resolver Update An/Aus
            UPDATERU = cConfig().getLocalizedString(30415)  # Aktiv
        else:
            UPDATERU = cConfig().getLocalizedString(30416)  # Inaktiv
        if cConfig().getSetting('bypassDNSlock') == 'true':  # DNS Bypass
            BYPASS = cConfig().getLocalizedString(30418)  # Aktiv
        else:
            BYPASS = cConfig().getLocalizedString(30419)  # Inaktiv
        if os.path.exists(ADDON_PATH % 'repository.resolveurl'):
            RESOLVEURL = cConfig('repository.resolveurl').getAddonInfo('name') + ':  ' + cConfig('repository.resolveurl').getAddonInfo('id') + ' - ' + cConfig('repository.resolveurl').getAddonInfo('version') + '\n'
        else:
            RESOLVEURL = ''

        # Support Informationen anzeigen
        Dialog().textviewer(cConfig().getLocalizedString(30265),
            cConfig().getLocalizedString(30413) + '\n'  # Geräte Informationen
            + 'Kodi Version:  ' + xbmc.getInfoLabel('System.BuildVersion')[:4] + ' (Code Version: ' + xbmc.getInfoLabel('System.BuildVersionCode') + ')' + '\n'  # Kodi Version
            + cConfig().getLocalizedString(30266) + '   {0}'.format(platform().title()) + '\n'  # System Plattform
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30414) + '\n'  # Plugin Informationen
            + cConfig().getAddonInfo('name') + ' Version:  ' + cConfig().getAddonInfo('id') + ' - ' + cConfig().getAddonInfo('version') + '\n'  # xStream ID und Version
            + cConfig('script.module.resolveurl').getAddonInfo('name') + ' Version:  ' + cConfig('script.module.resolveurl').getAddonInfo('id') + ' - ' + cConfig('script.module.resolveurl').getAddonInfo('version') + '\n'  # Resolver ID und Version
            + cConfig('script.module.resolveurl').getAddonInfo('name') + ' Status:  ' + UPDATERU + cConfig().getSettingString('resolver.branch') + '\n'  # Resolver Update Status und Branch
            + cConfig().getLocalizedString(30435) + ' ' + getRepofromAddonsDB(cConfig().getAddonInfo('id')) + '\n' # Repo-Info
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30420) + '\n'  # DNS Informationen
            + cConfig().getLocalizedString(30417) + ' ' + BYPASS + '\n'  # xStream DNS Bypass aktiv/inaktiv
            + cConfig().getLocalizedString(30434) + '1' + ' ' + getDNS('Network.DNS1Address') + '\n' # DNS Nameserver 1
            + cConfig().getLocalizedString(30434) + '2' + ' ' + getDNS('Network.DNS2Address') + '\n' # DNS Nameserver 2
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30421) + '\n'  # Repo Informationen
            + cConfig('repository.xstream').getAddonInfo('name') + ':  ' + cConfig('repository.xstream').getAddonInfo('id') + ' - ' + cConfig('repository.xstream').getAddonInfo('version') + '\n'  # xStream Repository ID und Version
            + RESOLVEURL
            + '\n'  # Absatz
            + cConfig().getLocalizedString(30422) + '\n'  # Indexseiten Informationen
            + list_of_PluginData # Liste mit den Indexseiten Informationen
            )

    # Überprüfung des Domain Namens. Leite um und hole neue URL und schreibe in die settings.xml. Bei nicht erreichen der Seite deaktiviere Globale Suche bis zum nächsten Start und überprüfe erneut.
    def checkDomain(self):
        import threading
        log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: Query status code of the provider', LOGNOTICE)
        fileNames = self.__getFileNamesFromFolder(self.defaultFolder)
        threads = []
        for fileName in fileNames:
            try:
                pluginDataDomain = self.__getPluginDataDomain(fileName, self.defaultFolder)
                provider = pluginDataDomain['identifier']
                if provider == 'api_all': #api_all bei der Überprüfung ignorieren da eh keine saubere Antwort kommt
                    continue
                _domain = pluginDataDomain['domain']
                domain = cConfig().getSetting('plugin_' + provider + '.domain', _domain)
                base_link = 'http://' + domain + '/'  # URL_MAIN
                wrongDomain = 'site-maps.cc', 'www.drei.at', 'notice.cuii.info'
                if domain in wrongDomain:  # Falsche Umleitung ausschliessen
                    cConfig().setSetting('plugin_' + provider + '.domain', '')  # Falls doch dann lösche Settings Eintrag
                    cConfig().setSetting('plugin_' + provider + '_status', '')  # lösche Status Code in den Settings
                    continue
                
                if cConfig().getSetting('plugin_' + provider) == 'false':  # Wenn SitePlugin deaktiviert
                    cConfig().setSetting('global_search_' + provider, 'false')  # setzte Globale Suche auf aus
                    cConfig().setSetting('plugin_' + provider + '_checkdomain', 'false')  # setzte Domain Check auf aus
                    cConfig().setSetting('plugin_' + provider + '.domain', '')  # lösche Settings Eintrag
                    cConfig().setSetting('plugin_' + provider + '_status', '')  # lösche Settings Eintrag
                    
                if cConfig().getSetting('plugin_' + provider + '_checkdomain') == 'true':  # aut. Domainüberprüfung an ist überprüfe Status der Sitplugins
                    t = threading.Thread(target=self._checkdomain, args=(provider, base_link), name=fileName)
                    threads += [t]
                    t.start()
            except Exception:
                pass
        
        for count, t in enumerate(threads):
            t.join()

        log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: Domains for all available Plugins updated', LOGNOTICE)
        infoDialog("Domain-Überprüfung aller Plugins abgeschlossen", sound=False, icon='INFO', time=6000)


    def _checkdomain(self, provider, base_link):
        try:
            oRequest = cRequestHandler(base_link, caching=False, ignoreErrors=True)
            oRequest.request()
            status_code = int(oRequest.getStatus())
            cConfig().setSetting('plugin_' + provider + '_status', str(status_code))  # setzte Status Code in die settings
            log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: Status Code ' + str(status_code) + '  ' + provider + ': - ' + base_link, LOGNOTICE)

            # Status 403 - bedeutet, dass der Zugriff auf eine angeforderte Ressource blockiert ist.
            # Status 404 - Seite nicht gefunden. Diese Meldung zeigt an, dass die Seite oder der Ordner auf dem Server, die aufgerufen werden sollten, nicht unter der angegebenen URL zu finden sind.
            if 403 <= status_code <= 503:  # Domain Interner Server Error und nicht erreichbar
                cConfig().setSetting('global_search_' + provider, 'false')  # deaktiviere Globale Suche
                log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: Internal Server Error for ' + provider + ' (DDOS Guard, HTTP Error, Cloudflare or BlazingFast active)', LOGNOTICE)

            # Status 301 - richtet Ihr auf Eurem Server ein, wenn sich die URL geändert hat, Eure Domain umgezogen ist oder sich ein Inhalt anderweitig verschoben hat.
            elif 300 <= status_code <= 400:  # Domain erreichbar mit Umleitung
                url = oRequest.getRealUrl()
                cConfig().setSetting('plugin_' + provider + '.domain', urlparse(url).hostname)  # setze Domain in die settings.xml
                cConfig().setSetting('global_search_' + provider, 'true')  # aktiviere Globale Suche
                log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: globalSearch for ' + provider + ' is activated.', LOGNOTICE)

            # Status 200 - Dieser Code wird vom Server zurückgegeben, wenn er den Request eines Browsers korrekt zurückgeben kann. Für die Ausgabe des Codes und des Inhalts der Seite muss der Server die Anfrage zunächst akzeptieren.
            elif status_code == 200:  # Domain erreichbar
                cConfig().setSetting('plugin_' + provider + '.domain', urlparse(base_link).hostname)  # setze URL_MAIN in die settings.xml
                cConfig().setSetting('global_search_' + provider, 'true')  # aktiviere Globale Suche
                log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: globalSearch for ' + provider + ' is activated.', LOGNOTICE)
            # Wenn keiner der Status oben greift
            else:
                log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: Error ' + provider + ' not available.', LOGNOTICE)
                cConfig().setSetting('global_search_' + provider, 'false')  # deaktiviere Globale Suche
                cConfig().setSetting('plugin_' + provider + '.domain', '')  # lösche Settings Eintrag
                log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: globalSearch for ' + provider + ' is deactivated.', LOGNOTICE)
        except:
            # Wenn Timeout und die Seite Offline ist
            cConfig().setSetting('global_search_' + provider, 'false')  # deaktiviere Globale Suche
            cConfig().setSetting('plugin_' + provider + '.domain', '')  # lösche Settings Eintrag
            log(cConfig().getLocalizedString(30166) + ' -> [checkDomain]: Error ' + provider + ' not available.', LOGNOTICE)
            pass
