# -*- coding: utf-8 -*-
"""
	Fenomscrapers Module
"""

from sys import argv
from urllib.parse import parse_qsl
from viperscrapers import sources_viperscrapers
from viperscrapers.modules import control

params = dict(parse_qsl(argv[2].replace('?', '')))
action = params.get('action')

if action is None:
	control.openSettings('0.0', 'script.module.viperscrapers')

if action == "ViperScrapersSettings":
	control.openSettings('0.0', 'script.module.viperscrapers')

elif action == 'ShowChangelog':
	from viperscrapers.modules import changelog
	changelog.get()

elif action == 'ShowHelp':
	from viperscrapers.help import help
	help.get(params.get('name'))

elif action == "Defaults":
	control.setProviderDefaults()

elif action == "toggleAll":
	sourceList = []
	sourceList = sources_viperscrapers.all_providers
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == "toggleAllHosters":
	sourceList = []
	sourceList = sources_viperscrapers.hoster_providers
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == "toggleAllTorrent":
	sourceList = []
	sourceList = sources_viperscrapers.torrent_providers
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == "toggleAllPackTorrent":
	control.execute('RunPlugin(plugin://script.module.viperscrapers/?action=toggleAllTorrent&amp;setting=false)')
	control.sleep(500)
	sourceList = []
	from viperscrapers import pack_sources
	sourceList = pack_sources()
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == 'cleanSettings':
	control.clean_settings()

elif action == 'undesirablesSelect':
	from viperscrapers.modules.undesirables import undesirablesSelect
	undesirablesSelect()

elif action == 'undesirablesInput':
	from viperscrapers.modules.undesirables import undesirablesInput
	undesirablesInput()

elif action == 'undesirablesUserRemove':
	from viperscrapers.modules.undesirables import undesirablesUserRemove
	undesirablesUserRemove()

elif action == 'undesirablesUserRemoveAll':
	from viperscrapers.modules.undesirables import undesirablesUserRemoveAll
	undesirablesUserRemoveAll()

elif action == 'tools_clearLogFile':
	from viperscrapers.modules import log_utils
	cleared = log_utils.clear_logFile()
	if cleared == 'canceled': pass
	elif cleared: control.notification(message='ViperScrapers Log File Successfully Cleared')
	else: control.notification(message='Error clearing ViperScrapers Log File, see kodi.log for more info')

elif action == 'tools_viewLogFile':
	from viperscrapers.modules import log_utils
	log_utils.view_LogFile(params.get('name'))

elif action == 'tools_viewTorrentStats':
	from viperscrapers.modules import log_utils
	log_utils.view_TorrentStats(params.get('name'))

elif action == 'tools_uploadLogFile':
	from viperscrapers.modules import log_utils
	log_utils.upload_LogFile()

elif action == 'plexAuth':
	from viperscrapers.modules import plex
	plex.Plex().auth()

elif action == 'plexRevoke':
	from viperscrapers.modules import plex
	plex.Plex().revoke()

elif action == 'plexSelectShare':
	from viperscrapers.modules import plex
	plex.Plex().get_plexshare_resource()

elif action == 'plexSeeShare':
	from viperscrapers.modules import plex
	plex.Plex().see_active_shares()

elif action == 'ShowOKDialog':
	control.okDialog(params.get('title', 'default'), int(params.get('message', '')))

elif action == 'TestProwlarrConnection':
	from viperscrapers.modules.prowlarr import Prowlarr
	prowlarr = Prowlarr()
	prowlarr.test()

elif action == 'ProwlarrIndexers':
	from viperscrapers.modules.prowlarr import Prowlarr
	prowlarr = Prowlarr()
	prowlarr.get_indexers()

elif action == 'mediafusionAuth':
	from viperscrapers.modules.mediafusion import MediaFusion
	mediafusion = MediaFusion()
	mediafusion.auth()

elif action == 'mediafusionReset':
	from viperscrapers.modules.mediafusion import MediaFusion
	mediafusion = MediaFusion()
	mediafusion.clear()

elif action == 'healthCheck':
	from viperscrapers.modules.health import Magneto
	Magneto().health_check()