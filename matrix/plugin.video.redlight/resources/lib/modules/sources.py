# -*- coding: utf-8 -*-
import json
import time
from threading import Thread, current_thread
from windows.base_window import open_window, create_window
from caches.episode_groups_cache import episode_groups_cache
from caches.settings_cache import get_setting
from scrapers import external, folders
from modules import debrid, kodi_utils, settings, metadata, watched_status
from modules.player import RedLightPlayer
from modules.source_utils import get_cache_expiry, make_alias_dict, include_exclude_filters
from modules.utils import clean_file_name, string_to_float, safe_string, remove_accents, get_datetime, append_module_to_syspath, manual_function_import
# logger = kodi_utils.logger

class Sources():
	def __init__(self):
		self.params = {}
		self.prescrape_scrapers, self.prescrape_threads, self.prescrape_sources, self.uncached_results = [], [], [], []
		self.threads, self.providers, self.sources, self.internal_scraper_names, self.remove_scrapers = [], [], [], [], ['external']
		self.clear_properties, self.filters_ignored, self.active_folders, self.resolve_dialog_made, self.episode_group_used = True, False, False, False, False
		self.sources_total = self.sources_4k = self.sources_1080p = self.sources_720p = self.sources_sd = 0
		self.prescrape, self.disabled_ext_ignored = 'true', 'false'
		self.ext_name, self.ext_folder = '', ''
		self.progress_dialog, self.progress_thread = None, None
		self.playing_filename = ''
		self.count_tuple = (('sources_4k', '4K', self._quality_length), ('sources_1080p', '1080p', self._quality_length), ('sources_720p', '720p', self._quality_length),
							('sources_sd', '', self._quality_length_sd), ('sources_total', '', self._quality_length_final))
		self.filter_keys = include_exclude_filters()
		self.filter_keys.pop('hybrid')
		self.default_internal_scrapers = ('easynews', 'aiostreams', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud', 'folders')
		self.debrids = {'Real-Debrid': ('apis.real_debrid_api', 'RealDebridAPI'), 'rd_cloud': ('apis.real_debrid_api', 'RealDebridAPI'),
		'rd_browse': ('apis.real_debrid_api', 'RealDebridAPI'), 'Premiumize.me': ('apis.premiumize_api', 'PremiumizeAPI'), 'pm_cloud': ('apis.premiumize_api', 'PremiumizeAPI'),
		'pm_browse': ('apis.premiumize_api', 'PremiumizeAPI'), 'AllDebrid': ('apis.alldebrid_api', 'AllDebridAPI'), 'ad_cloud': ('apis.alldebrid_api', 'AllDebridAPI'),
		'ad_browse': ('apis.alldebrid_api', 'AllDebridAPI'), 'TorBox': ('apis.torbox_api', 'TorBoxAPI'), 'tb_cloud': ('apis.torbox_api', 'TorBoxAPI'),
		'tb_browse': ('apis.torbox_api', 'TorBoxAPI')}
		self.retry_actions = settings.rescrape_settings()

	def playback_prep(self, params=None):
		kodi_utils.hide_busy_dialog()
		if params: self.params = params
		params_get = self.params.get
		self.play_type = params_get('play_type', '')
		self.background = params_get('background', 'false') == 'true'
		self.prescrape = params_get('prescrape', self.prescrape) == 'true'
		self.random, self.random_continual = params_get('random', 'false') == 'true', params_get('random_continual', 'false') == 'true'
		if 'external_cache_check' in self.params: self.external_cache_check = params_get('external_cache_check') == 'true'
		else: self.external_cache_check = settings.external_cache_check()
		if self.play_type:
			if self.play_type == 'autoplay_nextep': self.autoplay_nextep, self.autoscrape_nextep = True, False
			elif self.play_type == 'random_continual': self.autoplay_nextep, self.autoscrape_nextep = False, False
			else: self.autoplay_nextep, self.autoscrape_nextep = False, True
		else: self.autoplay_nextep, self.autoscrape_nextep = settings.autoplay_next_episode(), settings.autoscrape_next_episode()
		self.autoscrape = self.autoscrape_nextep and self.background		
		self.ignore_scrape_filters = params_get('ignore_scrape_filters', 'false') == 'true'
		self.nextep_settings, self.disable_autoplay_next_episode = params_get('nextep_settings', {}), params_get('disable_autoplay_next_episode', 'false') == 'true'
		self.disabled_ext_ignored = params_get('disabled_ext_ignored', self.disabled_ext_ignored) == 'true'
		self.folders_ignore_filters = get_setting('redlight.results.folders_ignore_filters', 'false') == 'true'
		self.filter_size_method = int(get_setting('redlight.results.filter_size_method', '0'))
		self.media_type, self.tmdb_id = params_get('media_type'), params_get('tmdb_id')		
		self.custom_title, self.custom_year = params_get('custom_title', None), params_get('custom_year', None)
		self.episode_group_label, self.episode_id = params_get('episode_group_label', ''), params_get('episode_id', None)
		self.playcount, self.watch_count = params_get('playcount', None), params_get('watch_count', 1)
		if self.media_type == 'episode':
			self.season, self.episode = int(params_get('season')), int(params_get('episode'))
			self.custom_season, self.custom_episode = params_get('custom_season', None), params_get('custom_episode', None)
			self.check_episode_group()
		else: self.season, self.episode, self.custom_season, self.custom_episode = '', '', '', ''
		if 'autoplay' in self.params: self.autoplay = params_get('autoplay', 'false') == 'true'
		else: self.autoplay = settings.auto_play(self.media_type)
		self.get_meta()
		self.determine_scrapers_status()
		self.sleep_time, self.provider_sort_ranks, self.scraper_settings = 100, settings.provider_sort_ranks(), settings.scraping_settings()
		self.include_prerelease_results = settings.include_prerelease_results()
		self.limit_resolve = settings.limit_resolve()
		self.weight_size = settings.size_sort_weighted()
		self.sort_function, self.quality_filter = settings.results_sort_order(), self._quality_filter()
		self.include_unknown_size = get_setting('redlight.results.size_unknown', 'false') == 'true'
		self.make_search_info()
		if self.autoscrape: self.autoscrape_nextep_handler()
		else: return self.get_sources()

	def check_episode_group(self):
		try:
			if any([self.custom_season, self.custom_episode]) or 'skip_episode_group_check' in self.params: return
			group_info = episode_groups_cache.get(self.tmdb_id)
			if not group_info: return
			group_details = metadata.group_episode_data(metadata.group_details(group_info['id']), self.episode_id, self.season, self.episode)
			if group_details:
				self.custom_season, self.custom_episode, self.episode_group_used = group_details['season'], group_details['episode'], True
				self.episode_group_label = '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (self.custom_season, self.custom_episode)
		except: self.custom_season, self.custom_episode = None, None

	def determine_scrapers_status(self):
		self.active_internal_scrapers = settings.active_internal_scrapers()
		if not 'external' in self.active_internal_scrapers and self.disabled_ext_ignored: self.active_internal_scrapers.append('external')
		self.active_external = 'external' in self.active_internal_scrapers
		if self.active_external:
			self.debrid_enabled = debrid.debrid_enabled()
			if not self.debrid_enabled:
				return self.disable_external('No Debrid Services Enabled' if all(scraper == 'external' for scraper in self.active_internal_scrapers) else 'EN used only')
			self.ext_folder, self.ext_name = settings.external_scraper_info()
			if not self.ext_folder or not self.ext_name: return self.disable_external('Error Importing External Module')

	def get_sources(self):
		if not self.progress_dialog and not self.background: self._make_progress_dialog()
		results = []
		if self.prescrape and any(x in self.active_internal_scrapers for x in self.default_internal_scrapers):
			if self.prepare_internal_scrapers():
				results = self.collect_prescrape_results()
				if results:
					results = self.process_results(results)
					if not self._should_offer_full_scrape(): self.prescrape = False
		if not results:
			self.prescrape = False
			self.prepare_internal_scrapers()
			if self.active_external: self.activate_external_providers()
			elif not self.active_internal_scrapers: self._kill_progress_dialog()
			self.orig_results = self.collect_results()
			if not self.orig_results and not self.active_external: self._kill_progress_dialog()
			results = self.process_results(self.orig_results)
		if not results:
			if self.uncached_results and self.external_cache_check and self.active_external:
				return self.play_source(self.sort_results(self.uncached_results))
			return self._process_post_results()
		if self.autoscrape: return results
		else: return self.play_source(results)

	def collect_results(self):
		if self.prescrape_sources:
			self.sources.extend(self.prescrape_sources)
		self._quality_poll_scrapers = set()
		self.cloud_scraper_names = []
		threads_append = self.threads.append
		if self.active_external:
			early_cloud = self.internal_sources(cloud_early=True)
			if early_cloud:
				self.cloud_scraper_names = [i[2] for i in early_cloud]
				for i in early_cloud:
					threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], False), name=i[2]))
				self.remove_scrapers.extend(i[2] for i in early_cloud)
		if self.active_folders: self.append_folder_scrapers(self.providers)
		self.providers.extend(self.internal_sources())
		if self.providers:
			for i in self.providers: threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], False), name=i[2]))
		if self.threads:
			[i.start() for i in self.threads]
		if self.active_external or self.background:
			if self.active_external:
				# Cloud scrapers in remove_scrapers run in parallel threads; do not poll their
				# window properties on the external progress bar (was showing TB_CLOUD etc. for the full timeout).
				external_progress_scrapers = [i for i in self.internal_scraper_names if i not in self.remove_scrapers]
				self.external_args = (self.meta, self.external_providers, self.debrid_enabled, self.external_cache_check, external_progress_scrapers,
										self.prescrape_sources, self.progress_dialog, self.disabled_ext_ignored, self.cloud_scraper_names)
				self.activate_providers('external', external, False)
			if self.threads:
				self._wait_for_cloud_threads()
				self._absorb_internal_properties()
		elif self.active_internal_scrapers: self.scrapers_dialog()
		if self.threads:
			self._join_internal_threads(6)
			self._absorb_internal_properties()
		return self.sources

	def collect_prescrape_results(self):
		threads_append = self.prescrape_threads.append
		if self.active_folders:
			if settings.check_prescrape_sources('folders', self.media_type):
				self.append_folder_scrapers(self.prescrape_scrapers)
				self.remove_scrapers.append('folders')
		self.prescrape_scrapers.extend(self.internal_sources(True))
		if not self.prescrape_scrapers: return []
		for i in self.prescrape_scrapers: threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], True), name=i[2]))
		[i.start() for i in self.prescrape_threads]
		self.remove_scrapers.extend(i[2] for i in self.prescrape_scrapers)
		if self.background: [i.join() for i in self.prescrape_threads]
		else: self.scrapers_dialog()
		return self.prescrape_sources

	def process_results(self, results):
		results = self.sort_results(results)
		min_seeders = settings.uncached_min_seeders()
		all_uncached_results = [i for i in results if 'Uncached' in i.get('cache_provider', '')]
		self.uncached_results = [i for i in all_uncached_results if int(i.get('seeders', '0')) >= min_seeders]
		if settings.include_uncached_torbox():
			tb_uncached_in_main = [i for i in self.uncached_results if 'TorBox' in i.get('cache_provider', '')]
			strip_uncached = [i for i in all_uncached_results if i not in tb_uncached_in_main]
			self.uncached_results = [i for i in self.uncached_results if i not in tb_uncached_in_main]
		else:
			strip_uncached = all_uncached_results
		results = [i for i in results if i not in strip_uncached]
		cloud_scrapers = ('rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud')
		cloud_results = [i for i in results if i.get('scrape_provider') in cloud_scrapers]
		if self.ignore_scrape_filters: self.filters_ignored = True
		else:
			scrape_results = [i for i in results if i not in cloud_results]
			scrape_results = self.filter_results(scrape_results)
			scrape_results = self.filter_audio(scrape_results)
			for file_type in self.filter_keys: scrape_results = self.special_filter(scrape_results, file_type)
			results = scrape_results + cloud_results
		results = self.sort_preferred_filters(results)
		if self.prescrape:
			self.all_scrapers = self.active_internal_scrapers
			autoplay_results = [i for i in results if i['scrape_provider'] in self.active_internal_scrapers and settings.autoplay_prescrape(i['scrape_provider'])]
			if autoplay_results:
				self.autoplay = True
				results = autoplay_results
		else:
			self.all_scrapers = list(set(self.active_internal_scrapers + self.remove_scrapers))
			kodi_utils.clear_property('fs_filterless_search')
		results = self.sort_first(results)
		if self.ignore_scrape_filters: return results
		non_cloud = [i for i in results if i.get('scrape_provider') not in cloud_scrapers]
		cloud_in_results = [i for i in results if i.get('scrape_provider') in cloud_scrapers]
		non_cloud = self.limit_quality_numbers(non_cloud)
		non_cloud = self.limit_quality_total(non_cloud)
		combined = non_cloud + cloud_in_results
		if self._pin_scrapers_to_top_enabled():
			return self.sort_first(combined)
		return self.sort_results(combined)

	def sort_results(self, results):
		results = [dict(i, **{
			'provider_rank': self._get_provider_rank(i['debrid'].lower()), 'quality_rank': self._get_quality_rank(i.get('quality', 'SD')),
			'size_rank': self._get_size_rank(i)}) for i in results]
		results.sort(key=self.sort_function)
		results = self._sort_uncached_results(results)
		return results

	def filter_results(self, results):
		if self.folders_ignore_filters:
			folder_results = [i for i in results if i['scrape_provider'] == 'folders']
			results = [i for i in results if not i in folder_results]
		else: folder_results = []
		results = [i for i in results if i['quality'] in self.quality_filter]
		if self.filter_size_method:
			min_size = string_to_float(get_setting('redlight.results.%s_size_min' % self.media_type, '0'), '0') / 1000
			if min_size == 0.0 and not self.include_unknown_size: min_size = 0.02
			if self.filter_size_method == 1:
				duration = self.meta['duration'] or (5400 if self.media_type == 'movie' else 2400)
				max_size = ((0.125 * (0.90 * string_to_float(get_setting('results.line_speed', '25'), '25'))) * duration)/1000
			elif self.filter_size_method == 2:
				max_size = string_to_float(get_setting('redlight.results.%s_size_max' % self.media_type, '10000'), '10000') / 1000
			results = [i for i in results if i['scrape_provider'] == 'folders' or i['scrape_provider'] in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud') or min_size <= i['size'] <= max_size]
		results += folder_results
		return results

	def filter_audio(self, results):
		a_filters = settings.audio_filters()
		return [i for i in results if not any(x in i['extraInfo'] for x in a_filters)]

	def special_filter(self, results, file_type):
		enable_setting, key = settings.filter_status(file_type), self.filter_keys[file_type]
		if key == 'HEVC' and enable_setting == 0:
			hevc_max_quality = self._get_quality_rank(get_setting('redlight.filter.hevc.%s' % ('max_autoplay_quality' if self.autoplay else 'max_quality'), '4K'))
			results = [i for i in results if not key in i['extraInfo'] or i['quality_rank'] >= hevc_max_quality]
		if enable_setting == 1:
			if key in ('D/VISION', 'HDR'):
				if not settings.filter_status({'D/VISION': 'hdr', 'HDR': 'dv'}[key]) == 0: results = [i for i in results if not key in i['extraInfo']]
				else: results = [i for i in results if not (key in i['extraInfo'] and not 'HYBRID' in i['extraInfo'])]
			else: results = [i for i in results if not key in i['extraInfo']]
		return results

	def sort_preferred_filters(self, results):
		if settings.sort_to_top_filter(self.autoplay):
			try:
				preferences = settings.preferred_filters()
				if not preferences: return results
				preferences = [self.filter_keys.get(i.lower(), i) for i in preferences]
				preference_results = [i for i in results if any(x in i['extraInfo'] for x in preferences)]
				if not preference_results: return results
				results = [i for i in results if not i in preference_results]
				preference_results = sorted([dict(item, **{'pref_includes': sum([{0:100, 1:50, 2:20, 3:10, 4:5, 5:2}[preferences.index(x)] \
					for x in [i for i in preferences if i in item['extraInfo']]])}) for item in preference_results], key=lambda k: k['pref_includes'], reverse=True)
				return preference_results + results
			except: pass
		return results

	def _pin_scrapers_to_top_enabled(self):
		if 'folders' in self.all_scrapers and settings.sort_to_top('folders'): return True
		return any(settings.sort_to_top(p) for p in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud') if p in self.all_scrapers)

	def sort_first(self, results):
		try:
			sort_first_scrapers = []
			if 'folders' in self.all_scrapers and settings.sort_to_top('folders'): sort_first_scrapers.append('folders')
			sort_first_scrapers.extend([i for i in self.all_scrapers if i in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud') and settings.sort_to_top(i)])
			if not sort_first_scrapers: return results
			sort_first = [i for i in results if i['scrape_provider'] in sort_first_scrapers]
			sort_first.sort(key=lambda k: (self._sort_folder_to_top(k['scrape_provider']), k['quality_rank']))
			sort_last = [i for i in results if not i in sort_first]
			results = sort_first + sort_last
		except: pass
		return results

	def limit_quality_numbers(self, results):
		if self.autoplay or self.ignore_scrape_filters: return results
		quality_limit = settings.limit_number_quality()
		if not quality_limit: return results
		quality_counter_dict, limit_list = {'4K': 0, '1080p': 0, '720p': 0, 'SD': 0, 'SCR': 0, 'CAM': 0, 'TELE': 0}, []
		for i in results:
			if quality_counter_dict[i['quality']] < quality_limit:
				quality_counter_dict[i['quality']] += 1
				limit_list.append(i)
		return limit_list

	def limit_quality_total(self, results):
		if self.autoplay or self.ignore_scrape_filters: return results
		total_limit = settings.limit_number_total()
		if not total_limit: return results
		return results[:total_limit]

	def prepare_internal_scrapers(self):
		if self.active_external and len(self.active_internal_scrapers) == 1:
			self.internal_scraper_names = [i for i in self.active_internal_scrapers if i != 'external']
			if self.clear_properties: self._clear_properties()
			return True
		active_internal_scrapers = [i for i in self.active_internal_scrapers if not i in self.remove_scrapers]
		if self.prescrape and not self.active_external and all([settings.check_prescrape_sources(i, self.media_type) for i in active_internal_scrapers]): return False
		if 'folders' in active_internal_scrapers:
			folder_info = self.get_folderscraper_info()
			self.folder_info = [i for i in folder_info if settings.source_folders_directory(self.media_type, i[1])]
			if self.folder_info:
				self.active_folders = True
				self.internal_scraper_names = [i for i in active_internal_scrapers if i not in ('folders', 'external')] + [i[0] for i in self.folder_info]
			else: self.internal_scraper_names = [i for i in active_internal_scrapers if i not in ('folders', 'external')]
		else:
			self.folder_info = []
			self.internal_scraper_names = [i for i in active_internal_scrapers if i != 'external']
		self.active_internal_scrapers = active_internal_scrapers
		if self.clear_properties: self._clear_properties()
		return True

	def activate_providers(self, module_type, function, prescrape):
		sources = self._get_module(module_type, function).results(self.search_info)
		if prescrape:
			if sources: self.prescrape_sources.extend(sources)
			return
		# Early cloud scrapers publish via window property only during external scrape.
		if current_thread().name in self.remove_scrapers:
			return
		if sources: self.sources.extend(sources)

	def activate_external_providers(self):
		self.external_providers = self.external_sources()
		if not self.external_providers: self.disable_external('No External Providers Enabled')

	def disable_external(self, line1=''):
		if line1: kodi_utils.notification(line1, 2000)
		try: self.active_internal_scrapers.remove('external')
		except: pass
		self.active_external, self.external_providers = False, []

	def internal_sources(self, prescrape=False, cloud_early=False):
		active_sources = [i for i in self.active_internal_scrapers if i in ['easynews', 'aiostreams', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud'] and i not in self.remove_scrapers]
		if cloud_early:
			active_sources = [i for i in active_sources if settings.cloud_scrape_before_external(i)]
		else:
			active_sources = [i for i in active_sources if not (prescrape and not settings.check_prescrape_sources(i, self.media_type))]
		try: sourceDict = [('internal', manual_function_import('scrapers.%s' % i, 'source'), i) for i in active_sources]
		except: sourceDict = []
		return sourceDict

	def _should_offer_full_scrape(self):
		if settings.rescrape_action_value('full_scrape', '2') == 0: return False
		if self.active_external: return True
		remaining = [i for i in self.active_internal_scrapers if i not in self.remove_scrapers]
		return bool(remaining)

	def external_sources(self):
		append_module_to_syspath('special://home/addons/%s/lib' % self.ext_folder)
		try: sourceDict = manual_function_import(self.ext_name, 'sources')(specified_folders=['torrents'], ret_all=self.disabled_ext_ignored)
		except: sourceDict = []
		return sourceDict

	def folder_sources(self):
		def import_info():
			for item in self.folder_info:
				scraper_name = item[0]
				module = manual_function_import('scrapers.folders', 'source')
				yield ('folders', (module, (item[1], scraper_name, item[2])), scraper_name)
		sourceDict = list(import_info())
		try: sourceDict = list(import_info())
		except: sourceDict = []
		return sourceDict

	def play_source(self, results):
		if self.background or self.autoplay: return self.play_file(results)
		return self.display_results(results)

	def append_folder_scrapers(self, current_list):
		current_list.extend(self.folder_sources())

	def get_folderscraper_info(self):
		folder_info = [(get_setting('redlight.%s.display_name' % i), i, settings.source_folders_directory(self.media_type, i))
						for i in ('folder1', 'folder2', 'folder3', 'folder4', 'folder5')]
		return [i for i in folder_info if not i[0] in (None, 'None', '') and i[2]]

	def _get_active_scraper_names(self, scraper_list):
		return [i[2] for i in scraper_list]

	def scrapers_dialog(self):
		def _scraperDialog():
			monitor = kodi_utils.kodi_monitor()
			start_time = time.time()
			while not self.progress_dialog.iscanceled() and not monitor.abortRequested():
				try:
					remaining_providers = [x.getName() for x in _threads if x.is_alive() is True]
					self._process_internal_results()
					current_progress = max((time.time() - start_time), 0)
					line1 = ', '.join(remaining_providers).upper()
					percent = int((current_progress/float(25))*100)
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
					kodi_utils.sleep(self.sleep_time)
					if len(remaining_providers) == 0: break
					if percent >= 100:
						grace_deadline = time.time() + 8
						while time.time() < grace_deadline and any(x.is_alive() for x in _threads):
							self._process_internal_results()
							kodi_utils.sleep(100)
						for thread in _threads:
							thread.join(timeout=max(0.0, grace_deadline - time.time()))
						self._absorb_internal_properties()
						break
				except:	return self._kill_progress_dialog()
		if self.prescrape: scraper_list, _threads = self.prescrape_scrapers, self.prescrape_threads
		else: scraper_list, _threads = self.providers, self.threads
		self.internal_scrapers = self._get_active_scraper_names(scraper_list)
		if not self.internal_scrapers: return
		_scraperDialog()
		try: del monitor
		except: pass

	def display_results(self, results):
		window_format, window_number = settings.results_format()
		window_result = open_window(('windows.sources', 'SourcesResults'), 'sources_results.xml',
				window_format=window_format, window_id=window_number, results=results, meta=self.meta, episode_group_label=self.episode_group_label,
				scraper_settings=self.scraper_settings, prescrape=self.prescrape, filters_ignored=self.filters_ignored,
				uncached_results=self.uncached_results, external_cache_check=self.external_cache_check)
		if not window_result:
			self._kill_progress_dialog()
			return
		action, chosen_item = window_result
		if not action: self._kill_progress_dialog()
		elif action == 'play':
			play_result = self.play_file(results, chosen_item)
			if isinstance(play_result, tuple) and play_result[0] == 'return_to_sources':
				return self.display_results(play_result[1])
			return play_result
		elif self.prescrape and action == 'perform_full_search':
			if not self._continue_full_scrape(): return self.display_results(results)
			self._reset_scrape_state()
			return self.get_sources()
		elif action == 'cache_change_rescrape':
			self.external_cache_check = chosen_item == 'true'
			self._reset_scrape_state(keep_disabled_ext_ignored=True)
			return self.get_sources()

	def _get_active_scraper_names(self, scraper_list):
		return [i[2] for i in scraper_list]

	def _continue_full_scrape(self):
		full_scrape = settings.rescrape_action_value('full_scrape', '2')
		if full_scrape == 0: return False
		if full_scrape == 2:
			return kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='Run a full source search?[CR][CR]Results limits, filters, and external scraper settings will apply.')
		return True

	def _reset_scrape_state(self, keep_disabled_ext_ignored=False):
		self.prescrape = False
		self.clear_properties = True
		self.filters_ignored = self.ignore_scrape_filters
		self.sources, self.prescrape_sources, self.orig_results = [], [], []
		self.threads, self.providers, self.prescrape_scrapers, self.prescrape_threads = [], [], [], []
		self.remove_scrapers, self.uncached_results = ['external'], []
		self.active_folders, self.folder_info = False, []
		self.internal_scraper_names, self.resolve_dialog_made = [], False
		if 'autoplay' in self.params: self.autoplay = self.params.get('autoplay') == 'true'
		else: self.autoplay = settings.auto_play(self.media_type)
		if not keep_disabled_ext_ignored:
			self.disabled_ext_ignored = self.params.get('disabled_ext_ignored', 'false') == 'true'
		if not self.ignore_scrape_filters: kodi_utils.clear_property('fs_filterless_search')
		self.determine_scrapers_status()

	def _process_post_results(self):
		if not self.retry_actions: return self._no_results()
		next_action, next_setting, order = self.retry_actions.pop(0)
		if next_action == 'cache_ignored':
			if next_setting in (1, 2) and self.active_external and self.orig_results and self.external_cache_check \
																				and debrid.debrid_for_ext_cache_check(self.debrid_enabled):
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With Cache Check Disabled?'):
					self.threads, self.prescrape, self.external_cache_check = [], False, False
					return self.get_sources()
			self._process_post_results()
		if next_action == 'imdb_year':
			if next_setting in (1, 2) and self.active_external and not self.orig_results and not self.meta.get('custom_year'):
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With IMDb Year Data?'):
					from apis.imdb_api import imdb_year_check
					imdb_year = str(imdb_year_check(self.meta.get('imdb_id')))
					if imdb_year != self.get_search_year():
						self.meta['custom_year'] = imdb_year
						self.make_search_info()
						self.threads, self.prescrape = [], False
						return self.get_sources()
			self._process_post_results()
		if next_action == 'with_all':
			if next_setting in (1, 2) and self.active_external:
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With All Scrapers?'):
					self.threads, self.disabled_ext_ignored, self.prescrape = [], True, False
					return self.get_sources()
			self._process_post_results()
		if next_action == 'episode_group':
			if next_setting in (1, 2) and self.media_type == 'episode':
				if next_setting == 1 \
											or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With Custom Episode Group if Possible?'):
					if self.episode_group_used:
						self.params.update({'custom_season': None, 'custom_episode': None, 'episode_group_label': '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (self.season, self.episode),
											'skip_episode_group_check': True})
						self.threads, self.disabled_ext_ignored, self.prescrape = [], True, True, False
						return self.playback_prep()
					if next_setting == 2:
						from indexers.dialogs import episode_groups_choice
						try: group_id = episode_groups_choice({'meta': self.meta, 'poster': self.meta['poster']})
						except: group_id = None
					else:
						try: group_id = metadata.episode_groups(self.tmdb_id)[0]['id']
						except: group_id = None
					if group_id:
						try: group_details = metadata.group_episode_data(metadata.group_details(group_id), None, self.season, self.episode)
						except: group_details = None
						if group_details:
							season, episode = group_details['season'], group_details['episode']
							self.params.update({'custom_season': season, 'custom_episode': episode, 'episode_group_label': '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (season, episode)})
							self.threads, self.disabled_ext_ignored, self.prescrape = [], True, True, False
							return self.playback_prep()
			self._process_post_results()
		if next_action == 'ignore_filters':
			if next_setting in (1, 2) and self.orig_results and not self.background:
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results. Access Filtered Results?'):
					if self.autoplay: kodi_utils.notification('Filters Ignored & Autoplay Disabled')
					self.threads, self.ignore_scrape_filters, self.disabled_ext_ignored, self.autoplay = [], True, True, False
					return self.get_sources()
			self._process_post_results()

	def _no_results(self):
		self._kill_progress_dialog()
		kodi_utils.hide_busy_dialog()
		if self.background: return kodi_utils.notification('[B]Next Up:[/B] No Results', 5000)
		kodi_utils.notification('No Results', 2000)

	def get_search_title(self):
		search_title = self.meta.get('custom_title', None) or self.meta.get('english_title') or self.meta.get('title')
		return search_title

	def get_search_year(self):
		year = self.meta.get('custom_year', None) or self.meta.get('year')
		return year

	def get_season(self):
		season = self.meta.get('custom_season', None) or self.meta.get('season')
		try: season = int(season)
		except: season = None
		return season

	def get_episode(self):
		episode = self.meta.get('custom_episode', None) or self.meta.get('episode')
		try: episode = int(episode)
		except: episode = None
		return episode

	def get_ep_name(self):
		ep_name = None
		if self.meta['media_type'] == 'episode':
			ep_name = self.meta.get('ep_name')
			try: ep_name = safe_string(remove_accents(ep_name))
			except: ep_name = safe_string(ep_name)
		return ep_name

	def _wait_for_cloud_threads(self, timeout=None):
		"""Keep the scraper progress bar alive while parallel cloud threads finish after external."""
		if not self.threads:
			return
		if timeout is None:
			timeout = min(35, max(15, int(get_setting('redlight.results.timeout', '20')) + 10))
		start_time, deadline = time.time(), time.time() + timeout
		while time.time() < deadline:
			alive = [t.getName() for t in self.threads if t.is_alive()]
			self._poll_scraper_quality_counts()
			if self.progress_dialog and alive:
				try:
					elapsed = max(time.time() - start_time, 0)
					percent = min(99, int((elapsed / 25.0) * 100))
					line1 = ', '.join(alive).upper()
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
				except:
					pass
			if not alive:
				break
			self._absorb_internal_properties()
			kodi_utils.sleep(100)
		self._join_internal_threads(max(0, deadline - time.time()))
		self._absorb_internal_properties()
		self._finalize_cloud_scraper_properties()

	def _cloud_scraper_names(self):
		names = set(self.cloud_scraper_names or [])
		names.update(i for i in self.remove_scrapers if i not in ('external',))
		for thread in self.threads:
			name = thread.getName()
			if name in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud'):
				names.add(name)
		return names

	def _finalize_cloud_scraper_properties(self):
		"""Mark cloud scrapers done when the thread exited without publishing a property."""
		for scraper in self._cloud_scraper_names():
			thread = next((t for t in self.threads if t.getName() == scraper), None)
			if thread and thread.is_alive():
				continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None):
				kodi_utils.set_property('redlight.internal_results.%s' % scraper, 'checked')

	def _poll_scraper_quality_counts(self):
		names = list(self.cloud_scraper_names or [])
		for thread in self.threads:
			name = thread.getName()
			if name and name not in names:
				names.append(name)
		for scraper in names:
			if scraper in self._quality_poll_scrapers:
				continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None):
				continue
			try:
				sources = json.loads(win_property)
			except:
				continue
			self._quality_poll_scrapers.add(scraper)
			self._sources_quality_count(sources)

	def _join_internal_threads(self, timeout=30):
		"""Wait for cloud/internal threads; cap wait so a stuck scraper cannot block results forever."""
		deadline = time.time() + timeout
		for thread in self.threads:
			remaining = deadline - time.time()
			if remaining <= 0:
				break
			try:
				thread.join(timeout=remaining)
			except:
				pass

	def _absorb_internal_properties(self):
		"""Merge internal scraper window properties into sources (cloud may finish after external dialog)."""
		scraper_names = set(self.internal_scraper_names)
		scraper_names.update(self._cloud_scraper_names())
		existing = {i.get('id') for i in self.sources if i.get('id')}
		for scraper in scraper_names:
			if scraper in ('external',): continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None): continue
			try: internal_sources = json.loads(win_property)
			except: continue
			kodi_utils.set_property('redlight.internal_results.%s' % scraper, 'checked')
			for item in internal_sources:
				item_id = item.get('id')
				if item_id and item_id in existing: continue
				if item_id: existing.add(item_id)
				self.sources.append(item)

	def _process_internal_results(self):
		for i in self.internal_scrapers:
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % i)
			if win_property in ('checked', '', None): continue
			try: sources = json.loads(win_property)
			except: continue
			kodi_utils.set_property('redlight.internal_results.%s' % i, 'checked')
			self._sources_quality_count(sources)
	
	def _sources_quality_count(self, sources):
		for item in self.count_tuple: setattr(self, item[0], getattr(self, item[0]) + item[2](sources, item[1]))

	def _quality_filter(self):
		setting = 'results_quality_%s' % self.media_type if not self.autoplay else 'autoplay_quality_%s' % self.media_type
		filter_list = settings.quality_filter(setting)
		if self.include_prerelease_results and 'SD' in filter_list: filter_list += ['SCR', 'CAM', 'TELE']
		return filter_list

	def _get_size_rank(self, item):
		if self.weight_size: return item['size'] * 2 if 'HEVC' in item['extraInfo'] else item['size']
		else: return item['size']

	def _get_quality_rank(self, quality):
		return {'4K': 1, '1080p': 2, '720p': 3, 'SD': 4, 'SCR': 5, 'CAM': 5, 'TELE': 5}[quality]

	def _get_provider_rank(self, account_type):
		return self.provider_sort_ranks[account_type] or 11

	def _sort_folder_to_top(self, provider):
		if provider == 'folders': return 0
		else: return 1

	def _sort_uncached_results(self, results):
		if settings.include_uncached_torbox():
			defer_uncached = [i for i in results if 'Uncached' in i.get('cache_provider', '') and 'TorBox' not in i.get('cache_provider', '')]
			return [i for i in results if i not in defer_uncached] + defer_uncached
		uncached = [i for i in results if 'Uncached' in i.get('cache_provider', '')]
		cached = [i for i in results if i not in uncached]
		return cached + uncached

	def get_meta(self):
		if self.media_type == 'movie': self.meta = metadata.movie_meta('tmdb_id', self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		else:
			try:
				self.meta = metadata.tvshow_meta('tmdb_id', self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
				episodes_data = metadata.episodes_meta(self.season, self.meta)
				episode_data = [i for i in episodes_data if i['episode'] == self.episode][0]
				ep_thumb = episode_data.get('thumb', None) or self.meta.get('fanart') or ''
				episode_type = episode_data.get('episode_type', '')
				self.meta.update({'season': episode_data['season'], 'episode': episode_data['episode'], 'premiered': episode_data['premiered'], 'episode_type': episode_type,
								'ep_name': episode_data['title'], 'ep_thumb': ep_thumb, 'plot': episode_data['plot'], 'tvshow_plot': self.meta['plot'],
								'playcount': self.playcount, 'watch_count': self.watch_count, 'custom_season': self.custom_season, 'custom_episode': self.custom_episode})
			except: pass
		self.meta.update({'media_type': self.media_type, 'background': self.background, 'custom_title': self.custom_title, 'custom_year': self.custom_year})

	def make_search_info(self):
		title, year, ep_name = self.get_search_title(), self.get_search_year(), self.get_ep_name()
		aliases = make_alias_dict(self.meta, title)
		expiry_times = get_cache_expiry(self.media_type, self.meta, self.season)
		self.search_info = {'media_type': self.media_type, 'title': title, 'year': year, 'tmdb_id': self.tmdb_id, 'imdb_id': self.meta.get('imdb_id'), 'aliases': aliases,
							'season': self.get_season(), 'episode': self.get_episode(), 'tvdb_id': self.meta.get('tvdb_id'), 'ep_name': ep_name, 'expiry_times': expiry_times,
							'total_seasons': self.meta.get('total_seasons', 1)}

	def _get_module(self, module_type, function):
		if module_type == 'external': module = function.source(*self.external_args)
		elif module_type == 'folders': module = function[0](*function[1])
		else: module = function()
		return module

	def _clear_properties(self):
		def_internal = self.default_internal_scrapers
		for item in def_internal: kodi_utils.clear_property('redlight.internal_results.%s' % item)
		if self.active_folders:
			for item in self.folder_info: kodi_utils.clear_property('redlight.internal_results.%s' % item[0])

	def _make_progress_dialog(self):
		self.progress_dialog = create_window(('windows.sources', 'SourcesPlayback'), 'sources_playback.xml', meta=self.meta)
		self.progress_thread = Thread(target=self.progress_dialog.run)
		self.progress_thread.start()

	def _make_resolve_dialog(self):
		self.resolve_dialog_made = True
		if not self.progress_dialog: self._make_progress_dialog()
		self.progress_dialog.enable_resolver()

	def _make_resume_dialog(self, percent):
		if not self.progress_dialog: self._make_progress_dialog()
		self.progress_dialog.enable_resume(percent)
		return self.progress_dialog.resume_choice

	def _make_nextep_dialog(self, default_action='cancel'):
		try: action = open_window(('windows.playback_notifications', 'NextEpisode'), 'playback_notifications.xml', meta=self.meta, default_action=default_action)
		except: action = 'cancel'
		return action

	def _make_still_watching_dialog(self, check_text):
		try: action = open_window(('windows.playback_notifications', 'StillWatching'), 'playback_notifications.xml', meta=self.meta, check_text=check_text)
		except: action = 'no'
		return action

	def _kill_progress_dialog(self, join_timeout=0.4):
		try:
			if self.progress_dialog:
				self.progress_dialog.close()
		except:
			pass
		try:
			if self.progress_thread:
				self.progress_thread.join(timeout=join_timeout)
		except:
			pass
		self.progress_dialog, self.progress_thread = None, None

	def debridPacks(self, debrid_provider, name, magnet_url, info_hash, download=False):
		from modules.debrid import ExternalPackSource, normalize_debrid_provider
		debrid_provider = normalize_debrid_provider(debrid_provider)
		source = {'url': magnet_url, 'hash': info_hash, 'debrid': debrid_provider, 'cache_provider': debrid_provider, 'name': name}
		pack_result = ExternalPackSource(source).browse_packs(download=download)
		if not pack_result:
			return None
		debrid_info = {'Real-Debrid': 'rd_browse', 'Premiumize.me': 'pm_browse', 'AllDebrid': 'ad_browse', 'TorBox': 'tb_browse'}.get(debrid_provider)
		if download:
			debrid_files, _pack_api = pack_result
			return debrid_files, self.debrid_importer(debrid_info)
		debrid_files = pack_result
		list_items = [{'line1': '%.2f GB | %s' % (float(item['size'])/1073741824, clean_file_name(item['filename']).upper())} for item in debrid_files]
		kwargs = {'items': json.dumps(list_items), 'heading': name, 'enumerate': 'true', 'narrow_window': 'true'}
		chosen_result = kodi_utils.select_dialog(debrid_files, **kwargs)
		if chosen_result is None: return None
		link = self.resolve_internal(debrid_info, chosen_result['link'], '')
		name = chosen_result['filename']
		self._kill_progress_dialog()
		return RedLightPlayer().run(link, 'video')

	def play_file(self, results, source={}):
		self.playback_successful, self.cancel_all_playback = None, False
		self._resolve_user_cancelled = False
		retry_easynews = settings.easynews_playback_method('retry')
		retry_easynews_limit = settings.easynews_playback_method_retries()
		original_results = list(results)
		try:
			kodi_utils.hide_busy_dialog()
			url = None
			playable_results = [i for i in results if 'Uncached' not in i.get('cache_provider', '')]
			if not source: source = playable_results[0]
			items = [source]
			if not self.limit_resolve:
				source_index = playable_results.index(source)
				queue_tail = playable_results[source_index + 1:]
				queue_head = playable_results[:source_index]
				queue_head.reverse()
				items = [source] + queue_tail + queue_head
			processed_items = []
			processed_items_append = processed_items.append
			for count, item in enumerate(items, 1):
				resolve_item = dict(item)
				provider = item['scrape_provider']
				if provider == 'external': provider = item['debrid'].replace('.me', '')
				elif provider == 'folders': provider = item['source']
				provider_text = provider.upper()
				extra_info = '[B]%s[/B] | [B]%s[/B] | %s' %  (item['quality'], item['size_label'], item['extraInfo'])
				display_name = item['display_name'].upper()
				resolve_item['resolve_display'] = '%02d. [B]%s[/B][CR]%s[CR]%s' % (count, provider_text, extra_info, display_name)
				processed_items_append(resolve_item)
				if provider == 'easynews' and retry_easynews:
					for retry in range(1, retry_easynews_limit):
						resolve_item = dict(item)
						resolve_item['resolve_display'] = '%02d. [B]%s (RETRYx%s)[/B][CR]%s[CR]%s' % (count, provider_text, retry, extra_info, display_name)
						processed_items_append(resolve_item)
			items = list(processed_items)
			if not self.continue_resolve_check(): return self._kill_progress_dialog()
			kodi_utils.hide_busy_dialog()
			self.playback_percent = self.get_playback_percent()
			if self.playback_percent == None: return self._kill_progress_dialog()
			if not self.resolve_dialog_made: self._make_resolve_dialog()
			if self.background: kodi_utils.sleep(1000)
			monitor = kodi_utils.kodi_monitor()
			for count, item in enumerate(items, 1):
				try:
					if self._resolve_user_cancelled or self.cancel_all_playback:
						break
					kodi_utils.hide_busy_dialog()
					if not self.progress_dialog: break
					if count > 1:
						prev = items[count - 2]
						if prev.get('scrape_provider') != item.get('scrape_provider'):
							if not self._resolve_user_cancelled:
								self.progress_dialog.reset_is_cancelled()
					elif not self._resolve_user_cancelled:
						self.progress_dialog.reset_is_cancelled()
					self.progress_dialog.update_resolver(text=item['resolve_display'])
					self.progress_dialog.busy_spinner()
					if count > 1:
						kodi_utils.sleep(200)
						try:
							del player
						except Exception:
							pass
					url, self.playback_successful, self.cancel_all_playback = None, None, False
					self.playing_filename = item['name']
					self.playing_item = item
					player = RedLightPlayer()
					try:
						if self.progress_dialog.iscanceled() or monitor.abortRequested():
							self._resolve_user_cancelled = True
							self.cancel_all_playback = True
							break
						url = self.resolve_sources(item)
						if self._resolve_user_cancelled or self.cancel_all_playback:
							break
						if url:
							resolve_percent = 0
							self.progress_dialog.busy_spinner('false')
							self.progress_dialog.update_resolver(percent=resolve_percent)
							kodi_utils.sleep(200)
							player.run(url, self)
						else: continue
						if self.cancel_all_playback or self._resolve_user_cancelled:
							break
						if self.playback_successful: break
					except: pass
				except: pass
		except: self._kill_progress_dialog()
		if self.cancel_all_playback or self._resolve_user_cancelled:
			self.resolve_dialog_made = False
			self._kill_progress_dialog(join_timeout=0.25)
			if not self.background and not self.autoplay:
				return 'return_to_sources', original_results
			return
		if self.playback_successful and url:
			self.resolve_dialog_made = False
			self._kill_progress_dialog(join_timeout=0.25)
			if not self.background and not self.autoplay:
				return self.display_results(original_results)
		if not self.playback_successful or not url: self.playback_failed_action()
		try: del monitor
		except: pass

	def get_playback_percent(self):
		if self.media_type == 'movie': percent = watched_status.get_progress_status_movie(watched_status.get_bookmarks_movie(), str(self.tmdb_id))
		elif any((self.random, self.random_continual)): return 0.0
		else: percent = watched_status.get_progress_status_episode(watched_status.get_bookmarks_episode(self.tmdb_id, self.season), self.episode)
		if not percent: return 0.0
		action = self.get_resume_status(percent)
		if action == 'cancel': return None
		if action == 'start_over':
			watched_status.erase_bookmark(self.media_type, self.tmdb_id, self.season, self.episode)
			return 0.0
		return float(percent)

	def get_resume_status(self, percent):
		if settings.auto_resume(self.media_type, self.autoplay): return float(percent)
		return self._make_resume_dialog(percent)

	def playback_failed_action(self):
		self._kill_progress_dialog()
		if self.prescrape and self.autoplay:
			self.resolve_dialog_made, self.prescrape, self.prescrape_sources = False, False, []
			self.get_sources()

	def still_watching_check(self):
		watching_check = self.nextep_settings.get('watching_check', 0)
		if watching_check == 0: return True
		player = kodi_utils.kodi_player()
		if not player.isPlayingVideo():
			return bool(self.background)
		watch_count = self.meta.get('watch_count')
		if watch_count == watching_check: still_watching, watch_count = self._make_still_watching_dialog('Are you still watching [B]%s[/B]?'), 0
		else: still_watching = True
		watch_count += 1
		self.meta['watch_count'] = watch_count
		return still_watching

	def continue_resolve_check(self):
		try:
			if not self.background or self.autoscrape_nextep: return True
			if self.autoplay_nextep: return self.autoplay_nextep_handler()
			return self.random_continual_handler()
		except: return False

	def random_continual_handler(self):
		kodi_utils.notification('[B]Next Up:[/B] %s S%02dE%02d' % (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
		player = kodi_utils.kodi_player()
		while player.isPlayingVideo(): kodi_utils.sleep(100)
		self._make_resolve_dialog()
		return True

	def autoplay_nextep_handler(self):
		if not self.nextep_settings: return False
		if not self.still_watching_check():
			kodi_utils.notification('Cancel Autoplay', icon=self.meta.get('poster'))
			return False
		use_window = self.nextep_settings['use_window']
		window_time = self.nextep_settings['window_time']
		default_action = self.nextep_settings['default_action']
		player = kodi_utils.kodi_player()
		continue_nextep = False
		if player.isPlayingVideo():
			total_time = player.getTotalTime()
			while player.isPlayingVideo():
				try:
					remaining_time = round(total_time - player.getTime())
					if remaining_time <= window_time:
						continue_nextep = True
						break
					kodi_utils.sleep(1000)
				except: pass
		elif self.background:
			continue_nextep = True
		if not continue_nextep:
			return False
		action = None if use_window else 'close'
		if use_window:
			action = self._make_nextep_dialog(default_action=default_action)
		else:
			kodi_utils.notification('[B]Next Up:[/B] %s S%02dE%02d' \
					% (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
		if not action:
			action = default_action
		if action == 'cancel':
			return False
		if action == 'pause':
			if player.isPlayingVideo():
				player.stop()
			return False
		if action == 'play':
			self._make_resolve_dialog()
			if player.isPlayingVideo():
				player.stop()
			return True
		while player.isPlayingVideo():
			kodi_utils.sleep(100)
		self._make_resolve_dialog()
		return True

	def autoscrape_nextep_handler(self):
		if settings.autoscrape_confirm():
			if not self._make_still_watching_dialog('Autoscrape Next Episode of [B]%s[/B]?'): return kodi_utils.notification('Cancel Autoscrape', icon=self.meta.get('poster'))
		player = kodi_utils.kodi_player()
		if player.isPlayingVideo():
			results = self.get_sources()
			if not results: return kodi_utils.notification(33092, 3000)
			else:
				kodi_utils.notification('[B]Next Episode Ready:[/B] %s S%02dE%02d' \
						% (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
				while player.isPlayingVideo(): kodi_utils.sleep(100)
			self.display_results(results)
		else: return

	def debrid_importer(self, debrid_provider):
		return manual_function_import(*self.debrids[debrid_provider])

	def resolve_sources(self, item, meta=None):
		if meta: self.meta = meta
		url = None
		try:
			if 'cache_provider' in item:
				cache_provider = item['cache_provider']
				if self.meta['media_type'] == 'episode':
					if hasattr(self, 'search_info'):
						title, season, episode, pack = self.search_info['title'], self.search_info['season'], self.search_info['episode'], 'package' in item
					else: title, season, episode, pack = self.get_ep_name(), self.get_season(), self.get_episode(), 'package' in item
				else: title, season, episode, pack = self.get_search_title(), None, None, False
				if cache_provider in ('Real-Debrid', 'Premiumize.me', 'AllDebrid', 'TorBox'):
					url = self.resolve_cached(cache_provider, item['url'], item['hash'], title, season, episode, pack)
			elif item.get('scrape_provider', None) in self.default_internal_scrapers:
				if item.get('scrape_provider') == 'aiostreams':
					from apis.aiostreams_api import resolve_playback_url
					url = resolve_playback_url(item)
				else:
					url = self.resolve_internal(item['scrape_provider'], item['id'], item['url_dl'], item.get('direct_debrid_link', False), item.get('cloud_media_type'))
			else: url = item['url']
		except: pass
		return url

	def resolve_cached(self, debrid_provider, item_url, _hash, title, season, episode, pack):
		debrid_function = self.debrid_importer(debrid_provider)
		store_to_cloud = settings.store_resolved_to_cloud(debrid_provider, pack)
		try: url = debrid_function().resolve_magnet(item_url, _hash, store_to_cloud, title, season, episode)
		except: url = None
		return url

	def resolve_internal(self, scrape_provider, item_id, url_dl, direct_debrid_link=False, cloud_media_type=None):
		url = None
		try:
			if direct_debrid_link or scrape_provider == 'folders': url = url_dl
			elif scrape_provider == 'easynews':
				from indexers.easynews import resolve_easynews
				url = resolve_easynews({'url_dl': url_dl, 'play': 'false'})
			else:
				debrid_function = self.debrid_importer(scrape_provider)
				if scrape_provider == 'tb_cloud':
					tb = debrid_function()
					media_type = cloud_media_type or 'torrent'
					if media_type == 'webdl':
						url = tb.unrestrict_webdl(item_id)
					elif media_type == 'usenet':
						url = tb.unrestrict_usenet(item_id)
					else:
						url = tb.unrestrict_link(item_id)
					url = tb.coerce_play_url(url) or url
				elif any(i in scrape_provider for i in ('rd_', 'ad_', 'tb_')):
					url = debrid_function().unrestrict_link(item_id)
				else:
					if '_cloud' in scrape_provider: item_id = debrid_function().get_item_details(item_id)['link']
					url = debrid_function().add_headers_to_url(item_id)
		except: pass
		return url

	def _quality_length(self, items, quality):
		return len([i for i in items if i['quality'] == quality])

	def _quality_length_sd(self, items, dummy):
		return len([i for i in items if i['quality'] in ('SD', 'CAM', 'TELE', 'SYNC')])

	def _quality_length_final(self, items, dummy):
		return len(items)
