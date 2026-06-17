# -*- coding: utf-8 -*-
"""Scraper orchestration mixin for ``Sources``.

Discovers active scraper providers, fires concurrent scraper threads, then filters,
sorts, and limits the result list. Drives the in-progress scraper dialog and the
source-select window. Hands the chosen result to the playback side via ``play_source``.

Part of the ``Sources`` class — composed with :class:`PlaybackOrchestrator` in
``modules.sources``. Do not instantiate directly; this mixin assumes ``Sources.__init__``
has already populated ``self``.
"""

import json
import time
from threading import Thread

from caches.settings_cache import get_setting
from modules import debrid, kodi_utils, metadata, settings, source_utils
from modules.source_utils import get_cache_expiry, make_alias_dict
from modules.utils import append_module_to_syspath, get_datetime, manual_function_import, string_to_float
from scrapers import external
from windows.base_window import open_window


class ScraperOrchestrator:
	def determine_scrapers_status(self):
		self.active_internal_scrapers = settings.active_internal_scrapers()
		if "external" not in self.active_internal_scrapers and self.disabled_ext_ignored:
			self.active_internal_scrapers.append("external")
		self.active_external = "external" in self.active_internal_scrapers
		if self.active_external:
			self.debrid_enabled = debrid.debrid_enabled()
			if not self.debrid_enabled:
				return self.disable_external(
					"No Debrid Services Enabled" if all(scraper == "external" for scraper in self.active_internal_scrapers) else "EN used only"
				)
			self.ext_folder, self.ext_name = settings.external_scraper_info()
			if not self.ext_folder or not self.ext_name:
				return self.disable_external("Error Importing External Module")

	def get_sources(self):
		if not self.progress_dialog and not self.background:
			self._make_progress_dialog()
		results = []
		if self.prescrape and any(x in self.active_internal_scrapers for x in self.default_internal_scrapers):
			if self.prepare_internal_scrapers():
				results = self.collect_prescrape_results()
				if results:
					results = self.process_results(results)
		if not results:
			self.prescrape = False
			self.prepare_internal_scrapers()
			if self.active_external:
				self.activate_external_providers()
			elif not self.active_internal_scrapers:
				self._kill_progress_dialog()
			self.orig_results = self.collect_results()
			if not self.orig_results and not self.active_external:
				self._kill_progress_dialog()
			results = self.process_results(self.orig_results)
		if not results:
			return self._process_post_results()
		if self.autoscrape:
			return results
		else:
			return self.play_source(results)

	def collect_results(self):
		self.sources.extend(self.prescrape_sources)
		threads_append = self.threads.append
		if self.active_folders:
			self.append_folder_scrapers(self.providers)
		self.providers.extend(self.internal_sources())
		if self.providers:
			for i in self.providers:
				threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], False), name=i[2]))
			[i.start() for i in self.threads]
		if self.active_external or self.background:
			if self.active_external:
				self.external_args = (
					self.meta,
					self.external_providers,
					self.debrid_enabled,
					self.external_cache_check,
					self.internal_scraper_names,
					self.prescrape_sources,
					self.progress_dialog,
					self.disabled_ext_ignored,
				)
				self.activate_providers("external", external, False)
			if self.background:
				[i.join() for i in self.threads]
		elif self.active_internal_scrapers:
			self.scrapers_dialog()
		return self.sources

	def collect_prescrape_results(self):
		threads_append = self.prescrape_threads.append
		if self.active_folders:
			if settings.check_prescrape_sources("folders", self.media_type):
				self.append_folder_scrapers(self.prescrape_scrapers)
				self.remove_scrapers.append("folders")
		self.prescrape_scrapers.extend(self.internal_sources(True))
		if not self.prescrape_scrapers:
			return []
		for i in self.prescrape_scrapers:
			threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], True), name=i[2]))
		[i.start() for i in self.prescrape_threads]
		self.remove_scrapers.extend(i[2] for i in self.prescrape_scrapers)
		if self.background:
			[i.join() for i in self.prescrape_threads]
		else:
			self.scrapers_dialog()
		return self.prescrape_sources

	def process_results(self, results):
		results = self.sort_results(results)
		min_seeders = settings.uncached_min_seeders()
		all_uncached_results = [i for i in results if "Uncached" in i.get("cache_provider", "")]
		self.uncached_results = [i for i in all_uncached_results if int(i.get("seeders", "0")) >= min_seeders]
		results = [i for i in results if i not in all_uncached_results]
		if self.ignore_scrape_filters:
			self.filters_ignored = True
		else:
			results = self.filter_results(results)
			results = self.filter_audio(results)
			for file_type in self.filter_keys:
				results = self.special_filter(results, file_type)
		results = self.sort_preferred_filters(results)
		if self.prescrape:
			self.all_scrapers = self.active_internal_scrapers
			autoplay_results = [
				i for i in results if i["scrape_provider"] in self.active_internal_scrapers and settings.autoplay_prescrape(i["scrape_provider"])
			]
			if autoplay_results:
				self.autoplay = True
				results = autoplay_results
		else:
			self.all_scrapers = list(set(self.active_internal_scrapers + self.remove_scrapers))
			kodi_utils.clear_property("fs_filterless_search")
		results = self.sort_first(results)
		if self.ignore_scrape_filters:
			return results
		results = self.limit_quality_numbers(results)
		results = self.limit_quality_total(results)
		return results

	def sort_results(self, results):
		results = [
			dict(
				i,
				**{
					"provider_rank": self._get_provider_rank(i["debrid"].lower()),
					"quality_rank": self._get_quality_rank(i.get("quality", "SD")),
					"size_rank": self._get_size_rank(i),
				},
			)
			for i in results
		]
		results.sort(key=self.sort_function)
		results = self._sort_uncached_results(results)
		return results

	def filter_results(self, results):
		if self.folders_ignore_filters:
			folder_results = [i for i in results if i["scrape_provider"] == "folders"]
			results = [i for i in results if i not in folder_results]
		else:
			folder_results = []
		results = [i for i in results if i["quality"] in self.quality_filter]
		if self.filter_size_method:
			min_size = string_to_float(get_setting("forge.results.%s_size_min" % self.media_type, "0"), "0") / 1000
			if min_size == 0.0 and not self.include_unknown_size:
				min_size = 0.02
			if self.filter_size_method == 1:
				duration = self.meta["duration"] or (5400 if self.media_type == "movie" else 2400)
				max_size = ((0.125 * (0.90 * string_to_float(get_setting("results.line_speed", "25"), "25"))) * duration) / 1000
			elif self.filter_size_method == 2:
				max_size = string_to_float(get_setting("forge.results.%s_size_max" % self.media_type, "10000"), "10000") / 1000
			results = [i for i in results if i["scrape_provider"] == "folders" or min_size <= i["size"] <= max_size]
		results += folder_results
		return results

	def filter_audio(self, results):
		a_filters = settings.audio_filters()
		return [i for i in results if not any(x in i["extraInfo"] for x in a_filters)]

	def special_filter(self, results, file_type):
		enable_setting, key = settings.filter_status(file_type), self.filter_keys[file_type]
		if key == "HEVC" and enable_setting == 0:
			hevc_max_quality = self._get_quality_rank(get_setting("forge.filter.hevc.%s" % ("max_autoplay_quality" if self.autoplay else "max_quality"), "4K"))
			results = [i for i in results if key not in i["extraInfo"] or i["quality_rank"] >= hevc_max_quality]
		if enable_setting == 1:
			if key in ("D/VISION", "HDR"):
				if not settings.filter_status({"D/VISION": "hdr", "HDR": "dv"}[key]) == 0:
					results = [i for i in results if key not in i["extraInfo"]]
				else:
					results = [i for i in results if not (key in i["extraInfo"] and "HYBRID" not in i["extraInfo"])]
			else:
				results = [i for i in results if key not in i["extraInfo"]]
		return results

	def sort_preferred_filters(self, results):
		if settings.sort_to_top_filter(self.autoplay):
			try:
				preferences = settings.preferred_filters()
				if not preferences:
					return results
				preferences = [self.filter_keys.get(i.lower(), i) for i in preferences]
				preference_results = [i for i in results if any(x in i["extraInfo"] for x in preferences)]
				if not preference_results:
					return results
				results = [i for i in results if i not in preference_results]
				preference_results = sorted(
					[
						dict(
							item,
							**{
								"pref_includes": sum(
									[
										{0: 100, 1: 50, 2: 20, 3: 10, 4: 5, 5: 2}[preferences.index(x)]
										for x in [i for i in preferences if i in item["extraInfo"]]
									]
								)
							},
						)
						for item in preference_results
					],
					key=lambda k: k["pref_includes"],
					reverse=True,
				)
				return preference_results + results
			except Exception:
				pass
		return results

	def sort_first(self, results):
		try:
			sort_first_scrapers = []
			if "folders" in self.all_scrapers and settings.sort_to_top("folders"):
				sort_first_scrapers.append("folders")
			sort_first_scrapers.extend([i for i in self.all_scrapers if i in ("rd_cloud", "pm_cloud", "ad_cloud", "tb_cloud") and settings.sort_to_top(i)])
			if not sort_first_scrapers:
				return results
			sort_first = [i for i in results if i["scrape_provider"] in sort_first_scrapers]
			sort_first.sort(key=lambda k: (self._sort_folder_to_top(k["scrape_provider"]), k["quality_rank"]))
			sort_last = [i for i in results if i not in sort_first]
			results = sort_first + sort_last
		except Exception:
			pass
		return results

	def limit_quality_numbers(self, results):
		if self.autoplay or self.ignore_scrape_filters:
			return results
		quality_limit = settings.limit_number_quality()
		if not quality_limit:
			return results
		quality_counter_dict, limit_list = {"4K": 0, "1080p": 0, "720p": 0, "SD": 0, "SCR": 0, "CAM": 0, "TELE": 0}, []
		for i in results:
			if quality_counter_dict[i["quality"]] < quality_limit:
				quality_counter_dict[i["quality"]] += 1
				limit_list.append(i)
		return limit_list

	def limit_quality_total(self, results):
		if self.autoplay or self.ignore_scrape_filters:
			return results
		total_limit = settings.limit_number_total()
		if not total_limit:
			return results
		return results[:total_limit]

	def prepare_internal_scrapers(self):
		if self.active_external and len(self.active_internal_scrapers) == 1:
			return
		active_internal_scrapers = [i for i in self.active_internal_scrapers if i not in self.remove_scrapers]
		if self.prescrape and not self.active_external and all([settings.check_prescrape_sources(i, self.media_type) for i in active_internal_scrapers]):
			return False
		if "folders" in active_internal_scrapers:
			folder_info = self.get_folderscraper_info()
			self.folder_info = [i for i in folder_info if settings.source_folders_directory(self.media_type, i[1])]
			if self.folder_info:
				self.active_folders = True
				self.internal_scraper_names = [i for i in active_internal_scrapers if not i == "folders"] + [i[0] for i in self.folder_info]
			else:
				self.internal_scraper_names = [i for i in active_internal_scrapers if not i == "folders"]
		else:
			self.folder_info = []
			self.internal_scraper_names = active_internal_scrapers[:]
		self.active_internal_scrapers = active_internal_scrapers
		if self.clear_properties:
			self._clear_properties()
		return True

	def activate_providers(self, module_type, function, prescrape):
		sources = self._get_module(module_type, function).results(self.search_info)
		if not sources:
			return
		if prescrape:
			self.prescrape_sources.extend(sources)
		else:
			self.sources.extend(sources)

	def activate_external_providers(self):
		self.external_providers = self.external_sources()
		if not self.external_providers:
			self.disable_external("No External Providers Enabled")

	def disable_external(self, line1=""):
		if line1:
			kodi_utils.notification(line1, 2000)
		try:
			self.active_internal_scrapers.remove("external")
		except ValueError:
			pass
		self.active_external, self.external_providers = False, []

	def internal_sources(self, prescrape=False):
		active_sources = [i for i in self.active_internal_scrapers if i in ["easynews", "rd_cloud", "pm_cloud", "ad_cloud", "tb_cloud"]]
		try:
			sourceDict = [
				("internal", manual_function_import("scrapers.%s" % i, "source"), i)
				for i in active_sources
				if not (prescrape and not settings.check_prescrape_sources(i, self.media_type))
			]
		except Exception:
			sourceDict = []
		return sourceDict

	def external_sources(self):
		append_module_to_syspath("special://home/addons/%s/lib" % self.ext_folder)
		try:
			sourceDict = manual_function_import(self.ext_name, "sources")(specified_folders=["torrents"], ret_all=self.disabled_ext_ignored)
		except Exception:
			sourceDict = []
		return sourceDict

	def folder_sources(self):
		def import_info():
			for item in self.folder_info:
				scraper_name = item[0]
				module = manual_function_import("scrapers.folders", "source")
				yield ("folders", (module, (item[1], scraper_name, item[2])), scraper_name)

		sourceDict = list(import_info())
		try:
			sourceDict = list(import_info())
		except Exception:
			sourceDict = []
		return sourceDict

	def play_source(self, results):
		if self.background or self.autoplay:
			return self.play_file(results)
		return self.display_results(results)

	def append_folder_scrapers(self, current_list):
		current_list.extend(self.folder_sources())

	def get_folderscraper_info(self):
		folder_info = [
			(get_setting("forge.%s.display_name" % i), i, settings.source_folders_directory(self.media_type, i))
			for i in ("folder1", "folder2", "folder3", "folder4", "folder5")
		]
		return [i for i in folder_info if i[0] not in (None, "None", "") and i[2]]

	def scrapers_dialog(self):
		def _scraperDialog():
			monitor = kodi_utils.kodi_monitor()
			start_time = time.time()
			while not self.progress_dialog.iscanceled() and not monitor.abortRequested():
				try:
					remaining_providers = [x.getName() for x in _threads if x.is_alive() is True]
					self._process_internal_results()
					current_progress = max((time.time() - start_time), 0)
					line1 = ", ".join(remaining_providers).upper()
					percent = int((current_progress / float(25)) * 100)
					self.progress_dialog.update_scraper(
						self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent
					)
					kodi_utils.sleep(self.sleep_time)
					if len(remaining_providers) == 0:
						break
					if percent >= 100:
						break
				except Exception:
					return self._kill_progress_dialog()

		if self.prescrape:
			scraper_list, _threads = self.prescrape_scrapers, self.prescrape_threads
		else:
			scraper_list, _threads = self.providers, self.threads
		self.internal_scrapers = self._get_active_scraper_names(scraper_list)
		if not self.internal_scrapers:
			return
		_scraperDialog()

	def display_results(self, results):
		window_format, window_number = settings.results_format()
		action, chosen_item = open_window(
			("windows.sources", "SourcesResults"),
			"sources_results.xml",
			window_format=window_format,
			window_id=window_number,
			results=results,
			meta=self.meta,
			episode_group_label=self.episode_group_label,
			scraper_settings=self.scraper_settings,
			prescrape=self.prescrape,
			filters_ignored=self.filters_ignored,
			uncached_results=self.uncached_results,
			external_cache_check=self.external_cache_check,
		)
		if not action:
			self._kill_progress_dialog()
		elif action == "play":
			return self.play_file(results, chosen_item)
		elif self.prescrape and action == "perform_full_search":
			self.prescrape, self.clear_properties = False, False
			return self.get_sources()
		elif action == "cache_change_rescrape":
			self.external_cache_check = chosen_item == "true"
			self.sources, self.orig_results, self.threads = [], [], []
			self.prescrape, self.clear_properties = False, False
			return self.get_sources()

	def _get_active_scraper_names(self, scraper_list):
		return [i[2] for i in scraper_list]

	def _process_post_results(self):
		if not self.retry_actions:
			return self._no_results()
		next_action, next_setting, _order = self.retry_actions.pop(0)
		if next_action == "cache_ignored":
			if (
				next_setting in (1, 2)
				and self.active_external
				and self.orig_results
				and self.external_cache_check
				and debrid.debrid_for_ext_cache_check(self.debrid_enabled)
			):
				if next_setting == 1 or kodi_utils.confirm_dialog(
					heading=self.meta.get("rootname", ""), text="No results.[CR]Retry With Cache Check Disabled?"
				):
					self.threads, self.prescrape, self.external_cache_check = [], False, False
					return self.get_sources()
			self._process_post_results()
		if next_action == "imdb_year":
			if next_setting in (1, 2) and self.active_external and not self.orig_results and not self.meta.get("custom_year"):
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get("rootname", ""), text="No results.[CR]Retry With IMDb Year Data?"):
					from apis.imdb_api import imdb_year_check

					imdb_year = str(imdb_year_check(self.meta.get("imdb_id")))
					if imdb_year != self.get_search_year():
						self.meta["custom_year"] = imdb_year
						self.make_search_info()
						self.threads, self.prescrape = [], False
						return self.get_sources()
			self._process_post_results()
		if next_action == "with_all":
			if next_setting in (1, 2) and self.active_external:
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get("rootname", ""), text="No results.[CR]Retry With All Scrapers?"):
					self.threads, self.disabled_ext_ignored, self.prescrape = [], True, False
					return self.get_sources()
			self._process_post_results()
		if next_action == "episode_group":
			if next_setting in (1, 2) and self.media_type == "episode":
				if next_setting == 1 or kodi_utils.confirm_dialog(
					heading=self.meta.get("rootname", ""), text="No results.[CR]Retry With Custom Episode Group if Possible?"
				):
					if self.episode_group_used:
						self.params.update(
							{
								"custom_season": None,
								"custom_episode": None,
								"episode_group_label": "[B]CUSTOM GROUP: S%02dE%02d[/B]" % (self.season, self.episode),
								"skip_episode_group_check": True,
							}
						)
						self.threads, self.disabled_ext_ignored, self.prescrape = [], True, True, False
						return self.playback_prep()
					if next_setting == 2:
						from indexers.dialogs import episode_groups_choice

						try:
							group_id = episode_groups_choice({"meta": self.meta, "poster": self.meta["poster"]})
						except Exception:
							group_id = None
					else:
						try:
							group_id = metadata.episode_groups(self.tmdb_id)[0]["id"]
						except Exception:
							group_id = None
					if group_id:
						try:
							group_details = metadata.group_episode_data(metadata.group_details(group_id), None, self.season, self.episode)
						except Exception:
							group_details = None
						if group_details:
							season, episode = group_details["season"], group_details["episode"]
							self.params.update(
								{
									"custom_season": season,
									"custom_episode": episode,
									"episode_group_label": "[B]CUSTOM GROUP: S%02dE%02d[/B]" % (season, episode),
								}
							)
							self.threads, self.disabled_ext_ignored, self.prescrape = [], True, True, False
							return self.playback_prep()
			self._process_post_results()
		if next_action == "ignore_filters":
			if next_setting in (1, 2) and self.orig_results and not self.background:
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get("rootname", ""), text="No results. Access Filtered Results?"):
					if self.autoplay:
						kodi_utils.notification("Filters Ignored & Autoplay Disabled")
					self.threads, self.ignore_scrape_filters, self.disabled_ext_ignored, self.autoplay = [], True, True, False
					return self.get_sources()
			self._process_post_results()

	def _no_results(self):
		self._kill_progress_dialog()
		kodi_utils.hide_busy_dialog()
		if self.background:
			return kodi_utils.notification("[B]Next Up:[/B] No Results", 5000)
		kodi_utils.notification("No Results", 2000)

	def get_search_title(self):
		return source_utils.get_search_title(self.meta)

	def get_search_year(self):
		return source_utils.get_search_year(self.meta)

	def get_season(self):
		return source_utils.get_season(self.meta)

	def get_episode(self):
		return source_utils.get_episode(self.meta)

	def get_ep_name(self):
		return source_utils.get_ep_name(self.meta)

	def _process_internal_results(self):
		for i in self.internal_scrapers:
			win_property = kodi_utils.get_property("forge.internal_results.%s" % i)
			if win_property in ("checked", "", None):
				continue
			try:
				sources = json.loads(win_property)
			except json.JSONDecodeError:
				continue
			kodi_utils.set_property("forge.internal_results.%s" % i, "checked")
			self._sources_quality_count(sources)

	def _sources_quality_count(self, sources):
		for item in self.count_tuple:
			setattr(self, item[0], getattr(self, item[0]) + item[2](sources, item[1]))

	def _quality_filter(self):
		setting = "results_quality_%s" % self.media_type if not self.autoplay else "autoplay_quality_%s" % self.media_type
		filter_list = settings.quality_filter(setting)
		if self.include_prerelease_results and "SD" in filter_list:
			filter_list += ["SCR", "CAM", "TELE"]
		return filter_list

	def _get_size_rank(self, item):
		if self.weight_size:
			return item["size"] * 2 if "HEVC" in item["extraInfo"] else item["size"]
		else:
			return item["size"]

	def _get_quality_rank(self, quality):
		return {"4K": 1, "1080p": 2, "720p": 3, "SD": 4, "SCR": 5, "CAM": 5, "TELE": 5}[quality]

	def _get_provider_rank(self, account_type):
		return self.provider_sort_ranks[account_type] or 11

	def _sort_folder_to_top(self, provider):
		if provider == "folders":
			return 0
		else:
			return 1

	def _sort_uncached_results(self, results):
		uncached = [i for i in results if "Uncached" in i.get("cache_provider", "")]
		cached = [i for i in results if i not in uncached]
		return cached + uncached

	def get_meta(self):
		if self.media_type == "movie":
			self.meta = metadata.movie_meta("tmdb_id", self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		else:
			try:
				self.meta = metadata.tvshow_meta("tmdb_id", self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
				episodes_data = metadata.episodes_meta(self.season, self.meta)
				episode_data = [i for i in episodes_data if i["episode"] == self.episode][0]
				ep_thumb = episode_data.get("thumb", None) or self.meta.get("fanart") or ""
				episode_type = episode_data.get("episode_type", "")
				self.meta.update(
					{
						"season": episode_data["season"],
						"episode": episode_data["episode"],
						"premiered": episode_data["premiered"],
						"episode_type": episode_type,
						"ep_name": episode_data["title"],
						"ep_thumb": ep_thumb,
						"plot": episode_data["plot"],
						"tvshow_plot": self.meta["plot"],
						"playcount": self.playcount,
						"watch_count": self.watch_count,
						"custom_season": self.custom_season,
						"custom_episode": self.custom_episode,
					}
				)
			except Exception:
				pass
		self.meta.update({"media_type": self.media_type, "background": self.background, "custom_title": self.custom_title, "custom_year": self.custom_year})

	def make_search_info(self):
		title, year, ep_name = self.get_search_title(), self.get_search_year(), self.get_ep_name()
		aliases = make_alias_dict(self.meta, title)
		expiry_times = get_cache_expiry(self.media_type, self.meta, self.season)
		self.search_info = {
			"media_type": self.media_type,
			"title": title,
			"year": year,
			"tmdb_id": self.tmdb_id,
			"imdb_id": self.meta.get("imdb_id"),
			"aliases": aliases,
			"season": self.get_season(),
			"episode": self.get_episode(),
			"tvdb_id": self.meta.get("tvdb_id"),
			"ep_name": ep_name,
			"expiry_times": expiry_times,
			"total_seasons": self.meta.get("total_seasons", 1),
		}

	def _get_module(self, module_type, function):
		if module_type == "external":
			module = function.source(*self.external_args)
		elif module_type == "folders":
			module = function[0](*function[1])
		else:
			module = function()
		return module

	def _clear_properties(self):
		def_internal = self.default_internal_scrapers
		for item in def_internal:
			kodi_utils.clear_property("forge.internal_results.%s" % item)
		if self.active_folders:
			for item in self.folder_info:
				kodi_utils.clear_property("forge.internal_results.%s" % item[0])

	def _quality_length(self, items, quality):
		return source_utils.quality_length(items, quality)

	def _quality_length_sd(self, items, dummy):
		return source_utils.quality_length_sd(items, dummy)

	def _quality_length_final(self, items, dummy):
		return source_utils.quality_length_final(items, dummy)
