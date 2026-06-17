# -*- coding: utf-8 -*-
"""``Sources`` — the scraper + playback orchestrator.

This file is intentionally thin. The behaviour lives in two mixins:

* :class:`modules.scraper_orchestrator.ScraperOrchestrator` — discovers providers,
  fans out scraper threads, filters/sorts/limits, drives the scraper dialog and
  source-select window.
* :class:`modules.playback_orchestrator.PlaybackOrchestrator` — drives the player
  loop, debrid resolution, autoplay-next / autoscrape-next, and the progress /
  resolve / resume / next-episode dialogs.

``Sources`` composes both and owns the shared state (``__init__``). Splitting on
mixins keeps the surface a single class — every existing caller (``router.py``,
``downloader.py``, ``episode_tools.py``, ``kodi_utils.py``, ``windows.extras``,
``indexers.dialogs``) is unchanged.
"""

from modules import settings
from modules.playback_orchestrator import PlaybackOrchestrator
from modules.scraper_orchestrator import ScraperOrchestrator
from modules.source_utils import include_exclude_filters


class Sources(ScraperOrchestrator, PlaybackOrchestrator):
	def __init__(self):
		self.params = {}
		self.prescrape_scrapers, self.prescrape_threads, self.prescrape_sources, self.uncached_results = [], [], [], []
		self.threads, self.providers, self.sources, self.internal_scraper_names, self.remove_scrapers = [], [], [], [], ["external"]
		self.clear_properties, self.filters_ignored, self.active_folders, self.resolve_dialog_made, self.episode_group_used = True, False, False, False, False
		self.sources_total = self.sources_4k = self.sources_1080p = self.sources_720p = self.sources_sd = 0
		self.prescrape, self.disabled_ext_ignored = "true", "false"
		self.ext_name, self.ext_folder = "", ""
		self.progress_dialog, self.progress_thread = None, None
		self.playing_filename = ""
		self.count_tuple = (
			("sources_4k", "4K", self._quality_length),
			("sources_1080p", "1080p", self._quality_length),
			("sources_720p", "720p", self._quality_length),
			("sources_sd", "", self._quality_length_sd),
			("sources_total", "", self._quality_length_final),
		)
		self.filter_keys = include_exclude_filters()
		self.filter_keys.pop("hybrid")
		self.default_internal_scrapers = ("easynews", "rd_cloud", "pm_cloud", "ad_cloud", "tb_cloud", "folders")
		self.debrids = {
			"Real-Debrid": ("apis.real_debrid_api", "RealDebridAPI"),
			"rd_cloud": ("apis.real_debrid_api", "RealDebridAPI"),
			"rd_browse": ("apis.real_debrid_api", "RealDebridAPI"),
			"Premiumize.me": ("apis.premiumize_api", "PremiumizeAPI"),
			"pm_cloud": ("apis.premiumize_api", "PremiumizeAPI"),
			"pm_browse": ("apis.premiumize_api", "PremiumizeAPI"),
			"AllDebrid": ("apis.alldebrid_api", "AllDebridAPI"),
			"ad_cloud": ("apis.alldebrid_api", "AllDebridAPI"),
			"ad_browse": ("apis.alldebrid_api", "AllDebridAPI"),
			"TorBox": ("apis.torbox_api", "TorBoxAPI"),
			"tb_cloud": ("apis.torbox_api", "TorBoxAPI"),
			"tb_browse": ("apis.torbox_api", "TorBoxAPI"),
		}
		self.retry_actions = settings.rescrape_settings()
