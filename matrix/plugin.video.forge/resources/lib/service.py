# -*- coding: utf-8 -*-
import os
from threading import Thread
from time import time

from caches.settings_cache import get_setting, set_setting, sync_settings
from modules import kodi_utils
from modules.migrations import run_migrations
from xbmc import Monitor

pause_services_prop = "forge.pause_services"
firstrun_update_prop = "forge.firstrun_update"
current_skin_prop = "forge.current_skin"
trakt_service_string = "TraktMonitor Service Update %s - %s"
trakt_success_line_dict = {"success": "Trakt Update Performed", "no account": "(Unauthorized) Trakt Update Performed"}
update_string = "Next Update in %s minutes..."


class ClearStaleProperties:
	"""D8: clear non-cache window properties left over from a prior service run.

	`Window(10000)` persists for the entire Kodi session, so any property
	written via `kodi_utils.set_property` outlives the plugin invocation that
	wrote it and outlives a service restart triggered by an addon update
	(only a full Kodi quit clears the bag). Most `forge.*` properties fall
	into one of four buckets:

	- **addon constants** — written by `SetAddonConstants` on every boot,
	  so nothing to clean (they get overwritten).
	- **settings-cache mirrors** (`settings_cache.set_setting` shadows every
	  setting onto `forge.<id>`) — cache, rebuilt lazily. Safe to leave.
	- **cache-like blobs** (e.g. `forge.meta_season_<id>`) — cache. Safe to leave.
	- **latches, UI state, in-flight markers** — these *do* leak across
	  invocations and can poison the next session. Clear them here.

	The trakt refresh latch is gone since E5 (replaced with `threading.Lock`)
	but stays on the list so legacy installs upgrading into this build don't
	inherit a stale `"true"` value that would never get cleared.

	Dynamic-name families (`forge.internal_results.<provider>`,
	`forge.download_status.<name>`, `forge.<download_name>` percent props)
	are lifecycle-managed by their owning code (cleared at session end). The
	only way they leak is a mid-scrape / mid-download crash; covering them
	would need either a registry of in-flight names or a wholesale
	`clearProperties()` of `Window(10000)`, which would also nuke property
	bag entries owned by other addons. Out of scope for D8.
	"""

	# Latches and in-flight markers that should never survive a service restart.
	_LATCH_PROPS = (
		"forge.trakt_refreshing_token",  # E5-obsolete latch; cleared defensively for legacy installs
		"forge.active_queued_downloads",
		"forge.active_downloads",
		"forge.external_scraper.module",
		"forge.widget_reload_pending",  # deferred home-widget reload request; stale if unserviced at shutdown
	)

	# UI state from the previous session's plugin invocations.
	_UI_STATE_PROPS = (
		"forge.window_loaded",
		"forge.window_stack",
		"forge.current_skin",
		"forge.current_font",
		"forge.exit_params",
		"forge.random_episode_history",
		"forge.random_because_you_watched",
		"forge.personal.lists.order",
		"forge.tmdb.lists.order",
		"forge.trakt.lists.order",
	)

	# Service-level flags. `pause_services` gets cleared so a screensaver/sleep
	# flag set in the prior session doesn't strand the new services as paused.
	# `firstrun_update` gets cleared so `UpdateCheck` actually runs once this
	# boot, instead of short-circuiting because the prior boot set it.
	# `fresh_install` (J4) is a per-boot signal `sync_settings` re-sets only when
	# the settings DB is empty; clearing it here stops a stale "true" from an
	# earlier same-session start mislabelling a later service restart.
	_SERVICE_FLAG_PROPS = (
		pause_services_prop,
		firstrun_update_prop,
		"forge.fresh_install",
	)

	def run(self):
		kodi_utils.logger("Forge", "ClearStaleProperties Service Starting")
		for prop in (*self._LATCH_PROPS, *self._UI_STATE_PROPS, *self._SERVICE_FLAG_PROPS):
			kodi_utils.clear_property(prop)
		return kodi_utils.logger("Forge", "ClearStaleProperties Service Finished")


class SetAddonConstants:
	def run(self):
		kodi_utils.logger("Forge", "SetAddonConstants Service Starting")
		import random

		addon_items = [
			("forge.playback_key", str(random.randint(1000, 10000))),
			("forge.addon_version", kodi_utils.addon_info("version")),
			("forge.addon_path", kodi_utils.addon_info("path")),
			("forge.addon_profile", kodi_utils.translate_path(kodi_utils.addon_info("profile"))),
			("forge.addon_icon", kodi_utils.translate_path(kodi_utils.addon_info("icon"))),
			(
				"forge.addon_icon_mini",
				os.path.join(
					kodi_utils.addon_info("path"),
					"resources",
					"media",
					"addon_icons",
					"minis",
					os.path.basename(kodi_utils.translate_path(kodi_utils.addon_info("icon"))),
				),
			),
			("forge.addon_fanart", kodi_utils.addon_fanart()),
		]
		for item in addon_items:
			kodi_utils.set_property(*item)
		return kodi_utils.logger("Forge", "SetAddonConstants Service Finished")


class DatabaseMaintenance:
	def run(self):
		kodi_utils.logger("Forge", "DatabaseMaintenance Service Starting")
		from caches.base_cache import check_databases_integrity

		check_databases_integrity(silent=True)
		return kodi_utils.logger("Forge", "DatabaseMaintenance Service Finished")


class SyncSettings:
	def run(self):
		kodi_utils.logger("Forge", "SyncSettings Service Starting")
		sync_settings()
		return kodi_utils.logger("Forge", "SyncSettings Service Finished")


def _migrate_rename_mixed_root():
	"""0.2.1: rename the persisted root-menu 'Mixed' entry to 'Mixed Movies & TV'.

	The root menu is persisted per-install in navigator_db; editing
	NavigatorCache.root_list only affects fresh installs. rebuild_database()
	refreshes the 'default' row; a customised 'edited' row is patched in place.
	Idempotent — a re-run is a no-op once the entry is renamed.
	"""
	from caches.navigator_cache import navigator_cache

	navigator_cache.rebuild_database()
	edited = navigator_cache.get_list("RootList", "edited")
	if not edited:
		return
	changed = False
	for entry in edited:
		if entry.get("mode") == "navigator.mixed" and entry.get("name") == "Mixed":
			entry["name"] = "Mixed Movies & TV"
			changed = True
	if changed:
		navigator_cache.set_list("RootList", "edited", edited)


def _migrate_add_play_trailer_to_cm():
	"""0.2.1: splice 'play_trailer' into a customised context-menu order/enabled
	list so users who personalised their menu before the Play Trailer feature still
	see the new entry. Fresh/never-customised installs already carry it via the
	schema defaults, so those lists contain it and are skipped. Idempotent."""
	for sid in ("context_menu.order", "context_menu.enabled"):
		raw = get_setting("forge.%s" % sid, "")
		items = raw.split(",") if raw else []
		if not items or "play_trailer" in items:
			continue
		if "extras" in items:
			items.insert(items.index("extras") + 1, "play_trailer")
		else:
			items.append("play_trailer")
		set_setting(sid, ",".join(items))


def _migrate_add_quick_add_to_cm():
	"""0.2.6: splice 'quick_add' into a customised context-menu order/enabled list
	so users who personalised their menu before the Quick Add feature still see the
	new entry. Fresh/never-customised installs already carry it via the schema
	defaults, so those lists contain it and are skipped. Idempotent."""
	for sid in ("context_menu.order", "context_menu.enabled"):
		raw = get_setting("forge.%s" % sid, "")
		items = raw.split(",") if raw else []
		if not items or "quick_add" in items:
			continue
		if "favorites_manager" in items:
			items.insert(items.index("favorites_manager") + 1, "quick_add")
		else:
			items.append("quick_add")
		set_setting(sid, ",".join(items))


# Ordered migration registry (J4). Append new migrations at the bottom, keyed by
# the addon version that first ships them, and bump addon.xml to match (a
# migration keyed above the shipped version never runs). Migrations MUST be
# idempotent; no settings_schema flag is needed. See modules/migrations.py.
MIGRATIONS = (
	("0.2.1", _migrate_rename_mixed_root),
	("0.2.1", _migrate_add_play_trailer_to_cm),
	("0.2.6", _migrate_add_quick_add_to_cm),
)


class OnUpdateChanges:
	def run(self):
		kodi_utils.logger("Forge", "OnUpdateChanges Service Starting")
		try:
			run_migrations(
				MIGRATIONS,
				current_version=kodi_utils.addon_version(),
				stored_version=get_setting("forge.migration_version", ""),
				is_fresh_install=get_setting("forge.fresh_install", "") == "true",
				stamp=self._stamp,
				run=lambda fn: fn(),
				log=lambda msg: kodi_utils.logger("Forge", "OnUpdateChanges %s" % msg),
			)
		except Exception as e:
			kodi_utils.logger("Forge", "OnUpdateChanges dispatch failed: %s" % e)
		return kodi_utils.logger("Forge", "OnUpdateChanges Service Finished")

	def _stamp(self, version):
		try:
			set_setting("migration_version", version)
		except Exception as e:
			kodi_utils.logger("Forge", "OnUpdateChanges could not stamp %s: %s" % (version, e))


class CacheMaintenance:
	def run(self):
		kodi_utils.logger("Forge", "CacheMaintenance Service Starting")
		from caches.base_cache import clean_databases_silent

		monitor = kodi_utils.kodi_monitor()
		wait_for_abort = monitor.waitForAbort
		# Stagger the initial sweep so it doesn't compete with startup work.
		wait_for_abort(120)
		while not monitor.abortRequested():
			while kodi_utils.get_property(pause_services_prop) == "true":
				if wait_for_abort(10):
					break
			if monitor.abortRequested():
				break
			try:
				clean_databases_silent()
			except Exception as e:
				kodi_utils.logger("CacheMaintenance", "sweep failed: %s" % e)
			try:
				interval = max(1, int(get_setting("forge.cache.maintenance_interval_hours", "24")))
			except (ValueError, TypeError):
				interval = 24
			wait_for_abort(interval * 3600)
		try:
			del monitor
		except:
			pass
		return kodi_utils.logger("Forge", "CacheMaintenance Service Finished")


class CustomWindowsPrepare:
	def run(self):
		kodi_utils.logger("Forge", "CustomWindowsPrepare Service Starting")
		from windows.base_window import ExtrasUtils, FontUtils

		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		kodi_utils.clear_property(current_skin_prop)
		ExtrasUtils().run()
		font_utils = FontUtils()
		while not monitor.abortRequested():
			font_utils.execute_custom_fonts()
			wait_for_abort(20)
		try:
			del monitor
		except:
			pass
		try:
			del player
		except:
			pass
		return kodi_utils.logger("Forge", "CustomWindowsPrepare Service Finished")


class TraktMonitor:
	def run(self):
		kodi_utils.logger("Forge", "TraktMonitor Service Starting")
		from apis.trakt_api import trakt_sync_activities
		from modules.settings import trakt_sync_interval, trakt_user_active

		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		while not monitor.abortRequested():
			while is_playing() or kodi_utils.get_property(pause_services_prop) == "true":
				wait_for_abort(10)
			wait_time = 1800
			try:
				sync_interval, wait_time = trakt_sync_interval()
				next_update_string = update_string % sync_interval
				if trakt_user_active:
					status = trakt_sync_activities()
				else:
					status = "no_auth"
				if status == "failed":
					kodi_utils.logger("Forge", trakt_service_string % ("Failed. Error from Trakt", next_update_string))
				elif status == "no_auth":
					kodi_utils.logger("Forge", trakt_service_string % ("Not Run. No Current Trakt Account", next_update_string))
				else:
					if status in ("success", "no account"):
						kodi_utils.logger("Forge", trakt_service_string % ("Success. %s" % trakt_success_line_dict[status], next_update_string))
					else:
						kodi_utils.logger("Forge", trakt_service_string % ("Success. No Changes Needed", next_update_string))  # 'not needed'
					if status == "success" and get_setting("forge.trakt.refresh_widgets", "false") == "true":
						kodi_utils.request_widget_reload()
			except Exception as e:
				kodi_utils.logger("Forge", trakt_service_string % ("Failed", "The following Error Occured: %s" % str(e)))
			wait_for_abort(wait_time)
		try:
			del monitor
		except:
			pass
		try:
			del player
		except:
			pass
		return kodi_utils.logger("Forge", "TraktMonitor Service Finished")


class UpdateCheck:
	def run(self):
		if kodi_utils.get_property(firstrun_update_prop) == "true":
			return
		kodi_utils.logger("Forge", "UpdateCheck Service Starting")
		from modules.settings import update_action, update_delay
		from modules.updater import update_check

		end_pause = time() + update_delay()
		monitor, player = kodi_utils.kodi_monitor(), kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		while not monitor.abortRequested():
			while time() < end_pause:
				wait_for_abort(1)
			while kodi_utils.get_property(pause_services_prop) == "true" or is_playing():
				wait_for_abort(1)
			update_check(update_action())
			break
		kodi_utils.set_property(firstrun_update_prop, "true")
		try:
			del monitor
		except:
			pass
		try:
			del player
		except:
			pass
		return kodi_utils.logger("Forge", "UpdateCheck Service Finished")


class WidgetRefresher:
	def run(self):
		kodi_utils.logger("Forge", "WidgetRefresher Service Starting")
		from time import time

		monitor = kodi_utils.kodi_monitor()
		wait_for_abort = monitor.waitForAbort
		wait_for_abort(10)
		self.set_next_refresh(time())
		while not monitor.abortRequested():
			try:
				wait_for_abort(10)
				offset = int(get_setting("forge.widget_refresh_timer", "60"))
				if offset != self.offset:
					self.set_next_refresh(time())
					continue
				if not kodi_utils.widgets_refresh_safe():
					continue
				# Safe state reached. Service an explicit reload request first (independent
				# of the periodic timer, so it still fires when the timer is disabled)...
				if kodi_utils.get_property("forge.widget_reload_pending"):
					kodi_utils.logger("Forge", "WidgetRefresher Service - Widgets Reloaded (requested)")
					# Reload first, then clear: if reload_home_widgets() raises (e.g. cache DB
					# locked), the flag survives and the request is retried next safe tick
					# instead of being silently dropped.
					kodi_utils.reload_home_widgets()
					kodi_utils.clear_property("forge.widget_reload_pending")
					self.set_next_refresh(time())
					continue
				# ...then the periodic refresh, when its timer is enabled and due.
				if self.next_refresh is not None and self.next_refresh < time():
					kodi_utils.logger("Forge", "WidgetRefresher Service - Widgets Refreshed")
					kodi_utils.reload_home_widgets()
					self.set_next_refresh(time())
			except:
				pass
		try:
			del monitor
		except:
			pass
		return kodi_utils.logger("Forge", "WidgetRefresher Service Finished")

	def set_next_refresh(self, _time):
		self.offset = int(get_setting("forge.widget_refresh_timer", "60"))
		if self.offset:
			self.next_refresh = _time + (self.offset * 60)
		else:
			self.next_refresh = None


class AutoStart:
	def run(self):
		kodi_utils.logger("Forge", "AutoStart Service Starting")
		from modules.settings import auto_start_forge

		if auto_start_forge():
			kodi_utils.run_addon()
		return kodi_utils.logger("Forge", "AutoStart Service Finished")


class AddonXMLCheck:
	def run(self):
		kodi_utils.logger("Forge", "AddonXMLCheck Service Starting")
		from xml.dom.minidom import parse as mdParse

		self.addon_xml = kodi_utils.translate_path("special://home/addons/plugin.video.forge/addon.xml")
		self.root = mdParse(self.addon_xml)
		self.change_list = []
		self.check_property("reuse_language_invoker", "reuselanguageinvoker")
		self.change_xml_file()
		return kodi_utils.logger("Forge", "AddonXMLCheck Service Finished")

	def check_property(self, setting, tag_name):
		current_addon_setting = get_setting("forge.%s" % setting, None)
		if current_addon_setting is None:
			return
		tag_instance = self.root.getElementsByTagName(tag_name)[0].firstChild
		current_property = tag_instance.data
		if current_property != current_addon_setting:
			tag_instance.data = current_addon_setting
			self.change_list.append(tag_name)

	def change_xml_file(self):
		if not self.change_list:
			return
		kodi_utils.notification("Refreshing Addon XML. Restarting Addons")
		new_xml = str(self.root.toxml()).replace('<?xml version="1.0" ?>', "")
		with open(self.addon_xml, "w") as f:
			f.write(new_xml)
		kodi_utils.logger("Forge", "AddonXMLCheck Service - Change Detected. Restarting Addons")
		kodi_utils.execute_builtin("ActivateWindow(Home)", True)
		kodi_utils.update_local_addons()
		kodi_utils.disable_enable_addon()


class ForgeMonitor(Monitor):
	def __init__(self):
		Monitor.__init__(self)
		self.startServices()

	def startServices(self):
		try:
			ClearStaleProperties().run()
		except Exception as e:
			kodi_utils.logger("ClearStaleProperties", str(e))
		try:
			SetAddonConstants().run()
		except Exception as e:
			kodi_utils.logger("SetAddonConstants", str(e))
		try:
			DatabaseMaintenance().run()
		except Exception as e:
			kodi_utils.logger("DatabaseMaintenance", str(e))
		try:
			SyncSettings().run()
		except Exception as e:
			kodi_utils.logger("SyncSettings", str(e))
		try:
			OnUpdateChanges().run()
		except Exception as e:
			kodi_utils.logger("OnUpdateChanges", str(e))
		try:
			AddonXMLCheck().run()
		except Exception as e:
			kodi_utils.logger("AddonXMLCheck", str(e))
		Thread(target=CustomWindowsPrepare().run).start()
		Thread(target=TraktMonitor().run).start()
		Thread(target=UpdateCheck().run).start()
		Thread(target=WidgetRefresher().run).start()
		Thread(target=CacheMaintenance().run).start()
		try:
			AutoStart().run()
		except Exception as e:
			kodi_utils.logger("AutoStart", str(e))

	def onNotification(self, sender, method, data):
		if method in ("GUI.OnScreensaverActivated", "System.OnSleep"):
			kodi_utils.set_property(pause_services_prop, "true")
			kodi_utils.logger("OnNotificationActions", "PAUSING Forge Services Due to Device Sleep")
		elif method in ("GUI.OnScreensaverDeactivated", "System.OnWake"):
			kodi_utils.clear_property(pause_services_prop)
			kodi_utils.logger("OnNotificationActions", "UNPAUSING Forge Services Due to Device Awake")


kodi_utils.logger("Forge", "Main Monitor Service Starting")
ForgeMonitor().waitForAbort()
kodi_utils.logger("Forge", "Main Monitor Service Finished")
