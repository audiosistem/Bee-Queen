# -*- coding: utf-8 -*-
from xbmc import Monitor
import os
import json
import inspect
from time import time
from threading import Thread
from caches.settings_cache import get_setting, set_setting, sync_settings
from modules import kodi_utils

pause_services_prop = 'redlight.pause_services'
firstrun_update_prop = 'redlight.firstrun_update'
current_skin_prop = 'redlight.current_skin'
trakt_service_string = 'TraktMonitor Service Update %s - %s'
trakt_success_line_dict = {'success': 'Trakt Update Performed', 'no account': '(Unauthorised) Trakt Update Performed'}
update_string = 'Next Update in %s minutes...'

class SetAddonConstants:
	def run(self):
		kodi_utils.logger('Red Light', 'SetAddonConstants Service Starting')
		import random
		new_version = kodi_utils.addon_info('version')
		prev_version = kodi_utils.get_property('redlight.addon_version')
		if prev_version and prev_version != new_version:
			kodi_utils.clear_property('redlight.deferred_service_setup_done')
			kodi_utils.logger('Red Light', 'SetAddonConstants - version %s -> %s' % (prev_version, new_version))
		icon_choice = get_setting('addon_icon_choice', 'resources/media/addon_icons/icon.png')
		addon_path = kodi_utils.addon_info('path')
		icon_path = kodi_utils.translate_path(os.path.join(addon_path, icon_choice))
		icon_mini = os.path.join(addon_path, 'resources', 'media', 'addon_icons', 'minis', os.path.basename(icon_path))
		addon_items = [
			('redlight.playback_key', str(random.randint(1000, 10000))),
			('redlight.addon_version', new_version),
			('redlight.addon_path', addon_path),
			('redlight.addon_profile', kodi_utils.translate_path(kodi_utils.addon_info('profile'))),
			('redlight.addon_icon', icon_path),
			('redlight.addon_icon_mini', icon_mini),
			('redlight.addon_fanart', kodi_utils.addon_fanart())
					]
		for item in addon_items: kodi_utils.set_property(*item)
		kodi_utils.clear_property('redlight.widgets_refresh_scheduled')
		return kodi_utils.logger('Red Light', 'SetAddonConstants Service Finished')

class DatabaseMaintenance:
	def run(self):
		kodi_utils.logger('Red Light', 'DatabaseMaintenance Service Starting')
		from caches.base_cache import check_databases_integrity
		check_databases_integrity(silent=True)
		return kodi_utils.logger('Red Light', 'DatabaseMaintenance Service Finished')

class SyncSettings:
	def run(self):
		kodi_utils.logger('Red Light', 'SyncSettings Service Starting')
		sync_settings({'load_properties': False})
		return kodi_utils.logger('Red Light', 'SyncSettings Service Finished')

class BootstrapSettings:
	def run(self):
		kodi_utils.logger('Red Light', 'BootstrapSettings Service Starting')
		monitor = kodi_utils.kodi_monitor()
		monitor.waitForAbort(2)
		if monitor.abortRequested(): return
		try:
			from caches.settings_cache import bootstrap_settings_properties, refresh_widgets_after_db_migration
			bootstrap_settings_properties()
			refresh_widgets_after_db_migration()
		except Exception as e:
			kodi_utils.logger('BootstrapSettings', str(e))
		return kodi_utils.logger('Red Light', 'BootstrapSettings Service Finished')

_custom_windows_thread_started = False

def start_custom_windows_prepare():
	global _custom_windows_thread_started
	if _custom_windows_thread_started: return
	_custom_windows_thread_started = True
	Thread(target=CustomWindowsPrepare().run, daemon=True).start()

def run_deferred_service_setup():
	global _custom_windows_thread_started
	kodi_utils.logger('Red Light', 'Deferred Service Setup Starting')
	try: kodi_utils.restore_addon_xml_from_settings()
	except Exception as e: kodi_utils.logger('DeferredServiceSetup', 'RestoreAddonXml: %s' % e)
	try: OnUpdateChanges().run()
	except Exception as e: kodi_utils.logger('DeferredServiceSetup', 'OnUpdateChanges: %s' % e)
	try:
		from windows.base_window import ExtrasUtils
		ExtrasUtils().run()
	except Exception as e: kodi_utils.logger('DeferredServiceSetup', 'ExtrasUtils: %s' % e)
	return kodi_utils.logger('Red Light', 'Deferred Service Setup Finished')

class OnUpdateChanges:
	def run(self):
		kodi_utils.logger('Red Light', 'OnUpdateChanges Service Starting')
		try:
			for method in list(filter(lambda x: x[0] != 'run', inspect.getmembers(OnUpdateChanges, predicate=inspect.isfunction))):
				if not get_setting('redlight.updatechecks.%s' % method[0], 'false') == 'true':
					method[1](self)
					set_setting('updatechecks.%s' % method[0], 'true')
		except: pass
		return kodi_utils.logger('Red Light', 'OnUpdateChanges Service Finished')

	def fix_media_github_username(self):
		stored = get_setting('redlight.update.username', '')
		if stored.replace('-', '').lower() == 'theredwizard' and stored != 'The-Red-Wizard':
			set_setting('update.username', 'The-Red-Wizard')

class CustomWindowsPrepare:
	def run(self):
		kodi_utils.logger('Red Light', 'CustomWindowsPrepare Service Starting')
		from windows.base_window import FontUtils
		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		kodi_utils.clear_property(current_skin_prop)
		font_utils = FontUtils()
		while not monitor.abortRequested():
			font_utils.execute_custom_fonts()
			wait_for_abort(20)
		try: del monitor
		except: pass
		try: del player
		except: pass
		return kodi_utils.logger('Red Light', 'CustomWindowsPrepare Service Finished')

class TraktMonitor:
	def run(self):
		kodi_utils.logger('Red Light', 'TraktMonitor Service Starting')
		from apis.trakt_api import trakt_sync_activities
		from modules.settings import trakt_user_active, trakt_sync_interval
		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(45)
		while not monitor.abortRequested():
			while is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': wait_for_abort(10)
			wait_time = 1800
			try:
				sync_interval, wait_time = trakt_sync_interval()
				next_update_string = update_string % sync_interval
				if trakt_user_active(): status = trakt_sync_activities()
				else: status = 'no_auth'
				if status == 'failed': kodi_utils.logger('Red Light', trakt_service_string % ('Failed. Error from Trakt', next_update_string))
				elif status == 'no_auth': kodi_utils.logger('Red Light', trakt_service_string % ('Not Run. No Current Trakt Account', next_update_string))
				else:
					if status in ('success', 'no account'):
						kodi_utils.logger('Red Light', trakt_service_string % ('Success. %s' % trakt_success_line_dict[status], next_update_string))
					else:
						kodi_utils.logger('Red Light', trakt_service_string % ('Success. No Changes Needed', next_update_string))# 'not needed'
					if status == 'success' and get_setting('redlight.trakt.refresh_widgets', 'false') == 'true':
						kodi_utils.run_plugin({'mode': 'kodi_refresh'})
			except Exception as e: kodi_utils.logger('Red Light', trakt_service_string % ('Failed', 'The following Error Occured: %s' % str(e)))
			wait_for_abort(wait_time)
		try: del monitor
		except: pass
		try: del player
		except: pass
		return kodi_utils.logger('Red Light', 'TraktMonitor Service Finished')

class SimklMonitor:
	def run(self):
		kodi_utils.logger('Red Light', 'SimklMonitor Service Starting')
		from apis.simkl_api import simkl_sync_activities
		from modules.settings import simkl_user_active, simkl_sync_interval
		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(45)
		while not monitor.abortRequested():
			while is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': wait_for_abort(10)
			wait_time = 1800
			try:
				sync_interval, wait_time = simkl_sync_interval()
				next_update_string = 'Simkl Sync finished - Next Sync in %s minutes' % sync_interval
				if simkl_user_active(): status = simkl_sync_activities()
				else: status = 'no_auth'
				if status == 'failed': kodi_utils.logger('Red Light', 'Simkl Sync Failed')
				elif status == 'no_auth': kodi_utils.logger('Red Light', 'Simkl Sync Not Run - No Account')
				else: kodi_utils.logger('Red Light', 'Simkl Sync %s - %s' % ('OK' if status == 'success' else 'No Changes', next_update_string))
				if status == 'success' and get_setting('redlight.simkl.refresh_widgets', 'false') == 'true':
					kodi_utils.run_plugin({'mode': 'kodi_refresh'})
			except Exception as e: kodi_utils.logger('Red Light', 'Simkl Sync Failed: %s' % str(e))
			wait_for_abort(wait_time)
		return kodi_utils.logger('Red Light', 'SimklMonitor Service Finished')

class UpdateCheck:
	def run(self):
		if kodi_utils.get_property(firstrun_update_prop) == 'true': return
		kodi_utils.logger('Red Light', 'UpdateCheck Service Starting')
		from modules.updater import update_check
		from modules.settings import update_action, update_delay
		end_pause = time() + update_delay()
		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		while not monitor.abortRequested():
			while time() < end_pause: wait_for_abort(1)
			while kodi_utils.get_property(pause_services_prop) == 'true' or is_playing(): wait_for_abort(1)
			update_check(update_action())
			break
		kodi_utils.set_property(firstrun_update_prop, 'true')
		try: del monitor
		except: pass
		try: del player
		except: pass
		return kodi_utils.logger('Red Light', 'UpdateCheck Service Finished')

class WidgetRefresher:
	def run(self):
		kodi_utils.logger('Red Light', 'WidgetRefresher Service Starting')
		from time import time
		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, self.is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(10)
		self.set_next_refresh(time())
		while not monitor.abortRequested():
			try:
				wait_for_abort(10)
				offset = int(get_setting('redlight.widget_refresh_timer', '60'))
				if offset != self.offset:
					self.set_next_refresh(time())
					continue
				if self.condition_check(): continue
				if self.next_refresh < time():
					kodi_utils.logger('Red Light', 'WidgetRefresher Service - Widgets Refreshed')
					kodi_utils.refresh_widgets()
					self.set_next_refresh(time())
			except: pass
		try: del monitor
		except: pass
		try: del player
		except: pass
		return kodi_utils.logger('Red Light', 'WidgetRefresher Service Finished')

	def condition_check(self):
		if not self.external(): return True

		if self.next_refresh == None or self.is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': return True
		if kodi_utils.get_property('redlight.window_loaded') == 'true': return True 
		try:
			window_stack = json.loads(kodi_utils.get_property('redlight.window_stack'))
			if window_stack or window_stack == []: return True
		except: pass
		return False

	def set_next_refresh(self, _time):
		self.offset = int(get_setting('redlight.widget_refresh_timer', '60'))
		if self.offset: self.next_refresh = _time + (self.offset*60)
		else: self.next_refresh = None

	def external(self):
		return 'plugin' not in kodi_utils.get_infolabel('Container.PluginName')

class AutoStart:
	def run(self):
		kodi_utils.logger('Red Light', 'AutoStart Service Starting')
		from modules.settings import auto_start_redlight
		if auto_start_redlight(): kodi_utils.run_addon()
		return kodi_utils.logger('Red Light', 'AutoStart Service Finished')

class RedLightMonitor(Monitor):
	def __init__ (self):
		Monitor.__init__(self)
		self.startServices()

	def startServices(self):
		try: SetAddonConstants().run()
		except Exception as e: kodi_utils.logger('SetAddonConstants', str(e))
		try: DatabaseMaintenance().run()
		except Exception as e: kodi_utils.logger('DatabaseMaintenance', str(e))
		try: SyncSettings().run()
		except Exception as e: kodi_utils.logger('SyncSettings', str(e))
		try: kodi_utils.restore_addon_xml_from_settings()
		except Exception as e: kodi_utils.logger('RestoreAddonXml', str(e))
		Thread(target=BootstrapSettings().run).start()
		start_custom_windows_prepare()
		Thread(target=TraktMonitor().run).start()
		Thread(target=SimklMonitor().run).start()
		Thread(target=UpdateCheck().run).start()
		Thread(target=WidgetRefresher().run).start()
		try: AutoStart().run()
		except Exception as e: kodi_utils.logger('AutoStart', str(e))

	def onNotification(self, sender, method, data):
		if method in ('GUI.OnScreensaverActivated', 'System.OnSleep'):
			kodi_utils.set_property(pause_services_prop, 'true')
			kodi_utils.logger('OnNotificationActions', 'PAUSING Red Light Services Due to Device Sleep')
		elif method in ('GUI.OnScreensaverDeactivated', 'System.OnWake'):
			kodi_utils.clear_property(pause_services_prop)
			kodi_utils.logger('OnNotificationActions', 'UNPAUSING Red Light Services Due to Device Awake')

if __name__ == '__main__':
	# ----- AM Lite Trakt startup sync patch BEGIN -----
	def wait_for_am_trakt(timeout=120, max_age=180):
		import time
		import xbmc
		import xbmcaddon

		if not xbmc.getCondVisibility('System.HasAddon(script.module.acctmgr)'):
			return False

		waited = 0
		while waited < timeout:
			try:
				am = xbmcaddon.Addon('script.module.acctmgr')
				ready = am.getSetting('am_trakt_ready')
				last_prepare = am.getSetting('am_last_prepare')
				if ready == 'true' and last_prepare:
					age = int(time.time()) - int(last_prepare)
					if 0 <= age <= max_age:
						return True
			except Exception:
				pass
			xbmc.sleep(1000)
			waited += 1
		return False

	def _am_trakt_startup():
		try:
			wait_for_am_trakt()
		except Exception:
			pass

	Thread(target=_am_trakt_startup, daemon=True).start()
	# ----- AM Lite Trakt startup sync patch END -----
	kodi_utils.logger('Red Light', 'Main Monitor Service Starting')
	RedLightMonitor().waitForAbort()
	kodi_utils.logger('Red Light', 'Main Monitor Service Finished')