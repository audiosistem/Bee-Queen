# -*- coding: utf-8 -*-
"""Playback orchestration mixin for ``Sources``.

Drives the post-scrape playback flow: episode-group resolution, progress / resolve /
resume / next-episode dialogs, link resolution against the active debrid providers,
the player loop in ``play_file``, and the autoplay-next-episode / random-continual /
autoscrape next-episode handlers.

Part of the ``Sources`` class — composed with :class:`ScraperOrchestrator` in
``modules.sources``. Do not instantiate directly.
"""

import json
from threading import Thread

from caches.episode_groups_cache import episode_groups_cache
from caches.settings_cache import get_setting
from modules import kodi_utils, metadata, settings, watched_status
from modules.player import ForgePlayer
from modules.utils import clean_file_name, manual_function_import
from windows.base_window import create_window, open_window


class PlaybackOrchestrator:
	def playback_prep(self, params=None):
		kodi_utils.hide_busy_dialog()
		if params:
			self.params = params
		params_get = self.params.get
		if not kodi_utils.external_playback_check(self.params):
			return
		self.play_type = params_get("play_type", "")
		self.background = params_get("background", "false") == "true"
		self.prescrape = params_get("prescrape", self.prescrape) == "true"
		self.random, self.random_continual = params_get("random", "false") == "true", params_get("random_continual", "false") == "true"
		if "external_cache_check" in self.params:
			self.external_cache_check = params_get("external_cache_check") == "true"
		else:
			self.external_cache_check = settings.external_cache_check()
		if self.play_type:
			if self.play_type == "autoplay_nextep":
				self.autoplay_nextep, self.autoscrape_nextep = True, False
			elif self.play_type == "random_continual":
				self.autoplay_nextep, self.autoscrape_nextep = False, False
			else:
				self.autoplay_nextep, self.autoscrape_nextep = False, True
		else:
			self.autoplay_nextep, self.autoscrape_nextep = settings.autoplay_next_episode(), settings.autoscrape_next_episode()
		self.autoscrape = self.autoscrape_nextep and self.background
		self.ignore_scrape_filters = params_get("ignore_scrape_filters", "false") == "true"
		self.nextep_settings, self.disable_autoplay_next_episode = (
			params_get("nextep_settings", {}),
			params_get("disable_autoplay_next_episode", "false") == "true",
		)
		self.disabled_ext_ignored = params_get("disabled_ext_ignored", self.disabled_ext_ignored) == "true"
		self.folders_ignore_filters = get_setting("forge.results.folders_ignore_filters", "false") == "true"
		self.filter_size_method = int(get_setting("forge.results.filter_size_method", "0"))
		self.media_type, self.tmdb_id = params_get("media_type"), params_get("tmdb_id")
		self.custom_title, self.custom_year = params_get("custom_title", None), params_get("custom_year", None)
		self.episode_group_label, self.episode_id = params_get("episode_group_label", ""), params_get("episode_id", None)
		self.playcount, self.watch_count = params_get("playcount", None), params_get("watch_count", 1)
		if self.media_type == "episode":
			self.season, self.episode = int(params_get("season")), int(params_get("episode"))
			self.custom_season, self.custom_episode = params_get("custom_season", None), params_get("custom_episode", None)
			self.check_episode_group()
		else:
			self.season, self.episode, self.custom_season, self.custom_episode = "", "", "", ""
		if "autoplay" in self.params:
			self.autoplay = params_get("autoplay", "false") == "true"
		else:
			self.autoplay = settings.auto_play(self.media_type)
		self.get_meta()
		self.determine_scrapers_status()
		self.sleep_time, self.provider_sort_ranks, self.scraper_settings = 100, settings.provider_sort_ranks(), settings.scraping_settings()
		self.include_prerelease_results = settings.include_prerelease_results()
		self.limit_resolve = settings.limit_resolve()
		self.weight_size = settings.size_sort_weighted()
		self.sort_function, self.quality_filter = settings.results_sort_order(), self._quality_filter()
		self.include_unknown_size = get_setting("forge.results.size_unknown", "false") == "true"
		self.make_search_info()
		if self.autoscrape:
			self.autoscrape_nextep_handler()
		else:
			return self.get_sources()

	def check_episode_group(self):
		try:
			if any([self.custom_season, self.custom_episode]) or "skip_episode_group_check" in self.params:
				return
			group_info = episode_groups_cache.get(self.tmdb_id)
			if not group_info:
				return
			group_details = metadata.group_episode_data(metadata.group_details(group_info["id"]), self.episode_id, self.season, self.episode)
			if group_details:
				self.custom_season, self.custom_episode, self.episode_group_used = group_details["season"], group_details["episode"], True
				self.episode_group_label = "[B]CUSTOM GROUP: S%02dE%02d[/B]" % (self.custom_season, self.custom_episode)
		except Exception:
			self.custom_season, self.custom_episode = None, None

	def _make_progress_dialog(self):
		self.progress_dialog = create_window(("windows.sources", "SourcesPlayback"), "sources_playback.xml", meta=self.meta)
		self.progress_thread = Thread(target=self.progress_dialog.run)
		self.progress_thread.start()

	def _make_resolve_dialog(self):
		self.resolve_dialog_made = True
		if not self.progress_dialog:
			self._make_progress_dialog()
		self.progress_dialog.enable_resolver()

	def _make_resume_dialog(self, percent):
		if not self.progress_dialog:
			self._make_progress_dialog()
		self.progress_dialog.enable_resume(percent)
		return self.progress_dialog.resume_choice

	def _make_nextep_dialog(self, default_action="cancel"):
		try:
			action = open_window(("windows.playback_notifications", "NextEpisode"), "playback_notifications.xml", meta=self.meta, default_action=default_action)
		except Exception:
			action = "cancel"
		return action

	def _make_still_watching_dialog(self, check_text):
		try:
			action = open_window(("windows.playback_notifications", "StillWatching"), "playback_notifications.xml", meta=self.meta, check_text=check_text)
		except Exception:
			action = "no"
		return action

	def _kill_progress_dialog(self):
		success = 0
		try:
			self.progress_dialog.close()
			success += 1
		except Exception:
			pass
		try:
			self.progress_thread.join()
			success += 1
		except Exception:
			pass
		if not success == 2:
			kodi_utils.close_all_dialog()
		del self.progress_dialog
		del self.progress_thread
		self.progress_dialog, self.progress_thread = None, None

	def debridPacks(self, debrid_provider, name, magnet_url, info_hash, download=False):
		kodi_utils.show_busy_dialog()
		debrid_info = {"Real-Debrid": "rd_browse", "Premiumize.me": "pm_browse", "AllDebrid": "ad_browse", "TorBox": "tb_browse"}[debrid_provider]
		debrid_function = self.debrid_importer(debrid_info)
		try:
			debrid_files = debrid_function().display_magnet_pack(magnet_url, info_hash)
		except Exception:
			debrid_files = None
		kodi_utils.hide_busy_dialog()
		if not debrid_files:
			return kodi_utils.notification("Error")
		debrid_files.sort(key=lambda k: k["filename"].lower())
		if download:
			return debrid_files, debrid_function
		list_items = [{"line1": "%.2f GB | %s" % (float(item["size"]) / 1073741824, clean_file_name(item["filename"]).upper())} for item in debrid_files]
		kwargs = {"items": json.dumps(list_items), "heading": name, "enumerate": "true", "narrow_window": "true"}
		chosen_result = kodi_utils.select_dialog(debrid_files, **kwargs)
		if chosen_result is None:
			return None
		link = self.resolve_internal(debrid_info, chosen_result["link"], "")
		name = chosen_result["filename"]
		self._kill_progress_dialog()
		return ForgePlayer().run(link, "video")

	def play_file(self, results, source={}):
		self.playback_successful, self.cancel_all_playback = None, False
		retry_easynews = settings.easynews_playback_method("retry")
		retry_easynews_limit = settings.easynews_playback_method_retries()
		try:
			kodi_utils.hide_busy_dialog()
			url = None
			results = [i for i in results if "Uncached" not in i.get("cache_provider", "")]
			if not source:
				source = results[0]
			items = [source]
			if not self.limit_resolve:
				source_index = results.index(source)
				results.remove(source)
				items_prev = results[:source_index]
				items_prev.reverse()
				items_next = results[source_index:]
				items = items + items_next + items_prev
			processed_items = []
			processed_items_append = processed_items.append
			for count, item in enumerate(items, 1):
				resolve_item = dict(item)
				provider = item["scrape_provider"]
				if provider == "external":
					provider = item["debrid"].replace(".me", "")
				elif provider == "folders":
					provider = item["source"]
				provider_text = provider.upper()
				extra_info = "[B]%s[/B] | [B]%s[/B] | %s" % (item["quality"], item["size_label"], item["extraInfo"])
				display_name = item["display_name"].upper()
				resolve_item["resolve_display"] = "%02d. [B]%s[/B][CR]%s[CR]%s" % (count, provider_text, extra_info, display_name)
				processed_items_append(resolve_item)
				if provider == "easynews" and retry_easynews:
					for retry in range(1, retry_easynews_limit):
						resolve_item = dict(item)
						resolve_item["resolve_display"] = "%02d. [B]%s (RETRYx%s)[/B][CR]%s[CR]%s" % (count, provider_text, retry, extra_info, display_name)
						processed_items_append(resolve_item)
			items = list(processed_items)
			if not self.continue_resolve_check():
				return self._kill_progress_dialog()
			kodi_utils.hide_busy_dialog()
			self.playback_percent = self.get_playback_percent()
			if self.playback_percent == None:
				return self._kill_progress_dialog()
			if not self.resolve_dialog_made:
				self._make_resolve_dialog()
			if self.background:
				kodi_utils.sleep(1000)
			monitor = kodi_utils.kodi_monitor()
			for count, item in enumerate(items, 1):
				try:
					kodi_utils.hide_busy_dialog()
					if not self.progress_dialog:
						break
					self.progress_dialog.reset_is_cancelled()
					self.progress_dialog.update_resolver(text=item["resolve_display"])
					self.progress_dialog.busy_spinner()
					if count > 1:
						kodi_utils.sleep(200)
					url, self.playback_successful, self.cancel_all_playback = None, None, False
					self.playing_filename = item["name"]
					self.playing_item = item
					player = ForgePlayer()
					try:
						if self.progress_dialog.iscanceled() or monitor.abortRequested():
							break
						url = self.resolve_sources(item)
						if url:
							resolve_percent = 0
							self.progress_dialog.busy_spinner("false")
							self.progress_dialog.update_resolver(percent=resolve_percent)
							kodi_utils.sleep(200)
							player.run(url, self)
						else:
							continue
						if self.cancel_all_playback:
							break
						if self.playback_successful:
							break
						if count == len(items):
							self.cancel_all_playback = True
							player.stop()
							break
					except Exception:
						pass
				except Exception:
					pass
		except Exception:
			self._kill_progress_dialog()
		if self.cancel_all_playback:
			return self._kill_progress_dialog()
		if not self.playback_successful or not url:
			self.playback_failed_action()

	def get_playback_percent(self):
		if self.media_type == "movie":
			percent = watched_status.get_progress_status_movie(watched_status.get_bookmarks_movie(), str(self.tmdb_id))
		elif any((self.random, self.random_continual)):
			return 0.0
		else:
			percent = watched_status.get_progress_status_episode(watched_status.get_bookmarks_episode(self.tmdb_id, self.season), self.episode)
		if not percent:
			return 0.0
		action = self.get_resume_status(percent)
		if action == "cancel":
			return None
		if action == "start_over":
			watched_status.erase_bookmark(self.media_type, self.tmdb_id, self.season, self.episode)
			return 0.0
		return float(percent)

	def get_resume_status(self, percent):
		if settings.auto_resume(self.media_type, self.autoplay):
			return float(percent)
		return self._make_resume_dialog(percent)

	def playback_failed_action(self):
		self._kill_progress_dialog()
		if self.prescrape and self.autoplay:
			self.resolve_dialog_made, self.prescrape, self.prescrape_sources = False, False, []
			self.get_sources()

	def still_watching_check(self):
		watching_check = self.nextep_settings["watching_check"]
		if watching_check == 0:
			return True
		player = kodi_utils.kodi_player()
		if not player.isPlayingVideo():
			return False
		watch_count = self.meta.get("watch_count")
		if watch_count == watching_check:
			still_watching, watch_count = self._make_still_watching_dialog("Are you still watching [B]%s[/B]?"), 0
		else:
			still_watching = True
		watch_count += 1
		self.meta["watch_count"] = watch_count
		return still_watching

	def continue_resolve_check(self):
		try:
			if not self.background or self.autoscrape_nextep:
				return True
			if self.autoplay_nextep:
				return self.autoplay_nextep_handler()
			return self.random_continual_handler()
		except Exception:
			return False

	def random_continual_handler(self):
		kodi_utils.notification(
			"[B]Next Up:[/B] %s S%02dE%02d" % (self.meta.get("title"), self.meta.get("season"), self.meta.get("episode")), 6500, self.meta.get("poster")
		)
		player = kodi_utils.kodi_player()
		while player.isPlayingVideo():
			kodi_utils.sleep(100)
		self._make_resolve_dialog()
		return True

	def autoplay_nextep_handler(self):
		if not self.nextep_settings:
			return False
		if not self.still_watching_check():
			kodi_utils.notification("Cancel Autoplay", icon=self.meta.get("poster"))
			return False
		player = kodi_utils.kodi_player()
		if player.isPlayingVideo():
			total_time = player.getTotalTime()
			use_window, window_time, default_action = (
				self.nextep_settings["use_window"],
				self.nextep_settings["window_time"],
				self.nextep_settings["default_action"],
			)
			action = None if use_window else "close"
			continue_nextep = False
			while player.isPlayingVideo():
				try:
					remaining_time = round(total_time - player.getTime())
					if remaining_time <= window_time:
						continue_nextep = True
						break
					kodi_utils.sleep(1000)
				except Exception:
					pass
			if continue_nextep:
				if use_window:
					action = self._make_nextep_dialog(default_action=default_action)
				else:
					kodi_utils.notification(
						"[B]Next Up:[/B] %s S%02dE%02d" % (self.meta.get("title"), self.meta.get("season"), self.meta.get("episode")),
						6500,
						self.meta.get("poster"),
					)
				if not action:
					action = default_action
				if action == "cancel":
					return False
				elif action == "pause":
					player.stop()
					return False
				elif action == "play":
					self._make_resolve_dialog()
					player.stop()
					return True
				else:
					while player.isPlayingVideo():
						kodi_utils.sleep(100)
					self._make_resolve_dialog()
					return True
			else:
				return False
		else:
			return False

	def autoscrape_nextep_handler(self):
		if settings.autoscrape_confirm():
			if not self._make_still_watching_dialog("Autoscrape Next Episode of [B]%s[/B]?"):
				return kodi_utils.notification("Cancel Autoscrape", icon=self.meta.get("poster"))
		player = kodi_utils.kodi_player()
		if player.isPlayingVideo():
			results = self.get_sources()
			if not results:
				return kodi_utils.notification(33092, 3000)
			else:
				kodi_utils.notification(
					"[B]Next Episode Ready:[/B] %s S%02dE%02d" % (self.meta.get("title"), self.meta.get("season"), self.meta.get("episode")),
					6500,
					self.meta.get("poster"),
				)
				while player.isPlayingVideo():
					kodi_utils.sleep(100)
			self.display_results(results)
		else:
			return

	def debrid_importer(self, debrid_provider):
		return manual_function_import(*self.debrids[debrid_provider])

	def resolve_sources(self, item, meta=None):
		if meta:
			self.meta = meta
		url = None
		try:
			if "cache_provider" in item:
				cache_provider = item["cache_provider"]
				if self.meta["media_type"] == "episode":
					if hasattr(self, "search_info"):
						title, season, episode, pack = self.search_info["title"], self.search_info["season"], self.search_info["episode"], "package" in item
					else:
						title, season, episode, pack = self.get_ep_name(), self.get_season(), self.get_episode(), "package" in item
				else:
					title, season, episode, pack = self.get_search_title(), None, None, False
				if cache_provider in ("Real-Debrid", "Premiumize.me", "AllDebrid", "TorBox"):
					url = self.resolve_cached(cache_provider, item["url"], item["hash"], title, season, episode, pack)
			elif item.get("scrape_provider", None) in self.default_internal_scrapers:
				url = self.resolve_internal(item["scrape_provider"], item["id"], item["url_dl"], item.get("direct_debrid_link", False))
			else:
				url = item["url"]
		except Exception:
			pass
		return url

	def resolve_cached(self, debrid_provider, item_url, _hash, title, season, episode, pack):
		debrid_function = self.debrid_importer(debrid_provider)
		store_to_cloud = settings.store_resolved_to_cloud(debrid_provider, pack)
		try:
			url = debrid_function().resolve_magnet(item_url, _hash, store_to_cloud, title, season, episode)
		except Exception:
			url = None
		return url

	def resolve_internal(self, scrape_provider, item_id, url_dl, direct_debrid_link=False):
		url = None
		try:
			if direct_debrid_link or scrape_provider == "folders":
				url = url_dl
			elif scrape_provider == "easynews":
				from indexers.easynews import resolve_easynews

				url = resolve_easynews({"url_dl": url_dl, "play": "false"})
			else:
				debrid_function = self.debrid_importer(scrape_provider)
				if any(i in scrape_provider for i in ("rd_", "ad_", "tb_")):
					url = debrid_function().unrestrict_link(item_id)
				else:
					if "_cloud" in scrape_provider:
						item_id = debrid_function().get_item_details(item_id)["link"]
					url = debrid_function().add_headers_to_url(item_id)
		except Exception:
			pass
		return url
