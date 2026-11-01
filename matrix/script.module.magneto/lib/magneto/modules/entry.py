"""
	Fenomscrapers Module
"""

import traceback
from urllib.parse import parse_qsl, urlparse
import xbmc
from magneto.modules import control

LOGINFO = 1  # (LOGNOTICE(2) deprecated in 19, use LOGINFO(1))


def routing():
	query = urlparse(__import__('sys').argv[2]).query
	params = dict(parse_qsl(query))
	action = params.get('action')
	name = params.get('name')

	if action is None:
		from magneto.player.navigator import Navigator
		Navigator(params).main()

	elif action == 'POVSettings':
		control.openSettings('0.0', 'plugin.video.pov')

	elif action == 'healthCheck':
		from pov.modules.health import health
		health()

	elif action == 'MediaPlay':
		from magneto import player
		player.MagnetoPlayer().source_select(params)

	elif action in ('Movies', 'Series', 'Episodes'):
		from magneto.player import navigator
		if action == 'Episodes': cls = navigator.Episodes()
		elif action == 'Series': cls = navigator.Series()
		else: cls = navigator.Movies()
		cls.run(params)

	elif action == 'ShowReadme':
		from magneto.modules import help
		help.get('aioStreams')

	elif action == 'InstallJson':
		from magneto.player import settings
		settings.install_json()

	elif action == 'ColorPick':
		from magneto.player import settings
		settings.color_pick(params)

	elif action == 'MagnetoSettings':
		control.openSettings('0.0', 'script.module.magneto')

	elif action == 'ShowChangelog':
		from magneto.modules import changelog
		changelog.get()

	elif action == 'ShowHelp':
		from magneto.modules import help
		help.get(name)

	elif action == 'cleanSettings':
		control.clean_settings()

	elif action == 'tools_clearLogFile':
		from magneto.modules import log_utils
		cleared = log_utils.clear_logFile()
		if cleared == 'canceled': pass
		elif cleared: control.notification(message='Magneto Log File Successfully Cleared')
		else: control.notification(message='Error clearing Magneto Log File, see kodi.log for more info')

	elif action == 'tools_viewLogFile':
		from magneto.modules import log_utils
		log_utils.view_LogFile(name)

	elif action == 'tools_uploadLogFile':
		from magneto.modules import log_utils
		log_utils.upload_LogFile()

class ServiceStartUp:
	def __call__(self):
		ver = '%s-%s' % (control.addonInfo('id'), control.addonInfo('version'))
		xbmc.log('[ script.module.magneto ]  Service Started (%s)' % ver, LOGINFO)
		self._check_settings_file()
		control.homeWindow().setProperty('magneto.debug.reversed', control.setting('debug.reversed'))
		self._check_version_update()
		self._check_config()
		xbmc.log('[ script.module.magneto ]  Service Stopped', LOGINFO)

	def _check_settings_file(self):
		xbmc.log('[ script.module.magneto ]  CheckSettingsFile Service Starting...', LOGINFO)
		try:
			profile_dir = control.dataPath
			if not control.existsPath(profile_dir):
				if control.makeDirs(profile_dir):
					xbmc.log(f"{profile_dir} : created successfully", LOGINFO)
			settings_xml = control.settingsFile
			if not control.existsPath(settings_xml):
				control.setSetting('module.provider', 'Magneto')
				xbmc.log(f"{settings_xml} : created successfully", LOGINFO)
			xbmc.log('[ script.module.magneto ]  CheckSettingsFile Service Finished', LOGINFO)
		except Exception:
			traceback.print_exc()

	def _check_config(self):
		if not any(control.condVisibility('System.InternetState') or control.sleep(1000) for i in range(5)): return
		url = 'https://api.themoviedb.org/3/configuration?api_key=%s' % control.addon().getSetting('tmdb_api')
		try: response = __import__('requests').request('get', url, timeout=3.05)
		except Exception: pass

	def _check_version_update(self):
		if not control.isVersionUpdate(): return
		control.execute('RunPlugin(plugin://script.module.magneto/?action=ShowChangelog)')
		control.clean_settings()
		xbmc.log('[ script.module.magneto ]  Settings file cleaned complete', LOGINFO)
