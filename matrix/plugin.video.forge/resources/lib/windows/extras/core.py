# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from threading import Thread

from apis import trakt_api
from indexers import people
from modules import kodi_utils, settings, watched_status
from modules.metadata import episodes_meta
from modules.utils import adjust_premiered_date, get_datetime
from windows.base_window import BaseDialog, window_manager, window_player
from windows.extras.actions import ActionsMixin
from windows.extras.ratings import RatingsMixin
from windows.extras.sections import SectionsMixin


class Extras(SectionsMixin, RatingsMixin, ActionsMixin, BaseDialog):
	button_ids = (10, 11, 12, 13, 14, 15, 16, 17, 2050)
	plot_id, cast_id, recommended_id, related_id, more_like_this_id, reviews_id, comments_id, trivia_id = 2050, 2051, 2052, 2053, 2054, 2056, 2057, 2058
	blunders_id, parentsguide_id, in_lists_id, videos_id, year_id, genres_id, networks_id, collection_id = 2059, 2060, 2061, 2062, 2063, 2064, 2065, 2066
	parentsguide_icons = {
		"Sex & Nudity": kodi_utils.get_icon("sex_nudity"),
		"Violence & Gore": kodi_utils.get_icon("violence"),
		"Profanity": kodi_utils.get_icon("bad_language"),
		"Alcohol, Drugs & Smoking": kodi_utils.get_icon("drugs_alcohol"),
		"Frightening & Intense Scenes": kodi_utils.get_icon("horror"),
	}
	meta_ratings_values = (
		("Meta", "metascore", 1),
		("Tom/Critic", "tomatometer", 2),
		("Tom/User", "tomatousermeter", 3),
		("IMDb", "imdb", 4),
		("TMDb", "tmdb", 5),
	)
	media_alert = "Press Info Button for [B]More Info[/B]"
	actor_alert = "Press Context Button for [B]Search[/B]"
	list_alert = "Press Context Button To [B]Like/Unlike List[/B]"

	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.control_id = None
		self.items_list_ids = (self.recommended_id, self.related_id, self.more_like_this_id, self.year_id, self.genres_id, self.networks_id, self.collection_id)
		self.text_list_ids = (self.reviews_id, self.trivia_id, self.blunders_id, self.parentsguide_id, self.comments_id)
		self.open_folder_list_ids = (self.in_lists_id,)
		self.empty_poster = kodi_utils.get_icon("box_office")
		self.addon_fanart = kodi_utils.addon_fanart()
		self.button_label_values = kodi_utils.extras_button_label_values()
		self.set_starting_constants(kwargs)
		self.set_properties()
		self.tasks = (
			self.set_artwork,
			self.set_infoline2,
			self.make_ratings,
			self.make_cast,
			self.make_recommended,
			self.make_related,
			self.make_more_like_this,
			self.make_imdb_extras,
			self.make_comments,
			self.make_in_lists,
			self.make_videos,
			self.make_year,
			self.make_genres,
			self.make_network,
			self.make_collection,
		)

	def onInit(self):
		self.set_home_property("window_loaded", "true")
		for i in self.tasks:
			Thread(target=i).start()
		self.set_default_focus()
		if self.starting_position:
			try:
				self.set_returning_focus(*self.starting_position)
			except:
				self.set_default_focus()

	def run(self):
		self.doModal()
		self.clearProperties()
		self.clear_home_property("window_theme.extras")
		self.clear_home_property("window_theme.highlight.extras")
		if self.selected:
			self.execute_code(self.selected)

	def onClick(self, controlID):
		self.control_id = None
		if controlID in self.button_ids:
			return exec("self.%s()" % self.button_action_dict[controlID])
		else:
			self.control_id = controlID

	def onAction(self, action):
		if action in self.closing_actions:
			return window_manager(self)
		if action == self.info_action:
			focus_id = self.getFocusId()
			if focus_id not in self.items_list_ids:
				return
			kodi_utils.show_busy_dialog()
			from modules.metadata import movie_meta, tvshow_meta

			chosen_listitem = self.get_listitem(focus_id)
			function = movie_meta if self.media_type == "movie" else tvshow_meta
			meta = function("tmdb_id", chosen_listitem.getProperty("tmdb_id"), self.tmdb_api_key, self.mpaa_region, self.current_date)
			kodi_utils.hide_busy_dialog()
			self.show_extrainfo(meta)
		elif action in self.context_actions:
			focus_id = self.getFocusId()
			if focus_id == self.cast_id:
				person_name = self.get_listitem(focus_id).getProperty(self.item_action_dict[focus_id])
				return people.person_search(person_name)
			elif focus_id == self.in_lists_id:
				kodi_utils.show_busy_dialog()
				try:
					list_item, position = self.get_listitem(focus_id), self.get_position(focus_id)
					chosen = self.get_attribute(self, list_item.getProperty(self.item_action_dict[focus_id]))[self.get_position(focus_id)]
					user, list_slug = chosen["user"]["ids"]["slug"], chosen["ids"]["slug"]
					function, new_value = (
						(trakt_api.trakt_like_a_list, "true") if list_item.getProperty("liked_status") == "false" else (trakt_api.trakt_unlike_a_list, "false")
					)
					new_value = "true" if list_item.getProperty("liked_status") == "false" else "false"
					if function({"user": user, "list_slug": list_slug, "refresh": "false"}):
						list_item.setProperty("liked_status", new_value)
				except:
					return self.notification("Error with Trakt List")
				kodi_utils.hide_busy_dialog()
			else:
				return
		if not self.control_id:
			return
		if action in self.selection_actions:
			try:
				chosen_var = self.get_listitem(self.control_id).getProperty(self.item_action_dict[self.control_id])
			except:
				return
			if not chosen_var:
				return
			position = self.get_position(self.control_id)
			if self.control_id in self.items_list_ids:
				self.set_current_params()
				self.new_params = {
					"mode": "extras_menu_choice",
					"tmdb_id": chosen_var,
					"media_type": self.media_type,
					"is_external": self.is_external,
					"stacked": "true",
				}
				return window_manager(self)
			elif self.control_id == self.cast_id:
				self.set_current_params()
				self.new_params = {
					"mode": "person_data_dialog",
					"key_id": chosen_var,
					"reference_tmdb_id": self.tmdb_id,
					"is_external": self.is_external,
					"stacked": "true",
				}
				return window_manager(self)
			elif self.control_id == self.videos_id:
				self.set_current_params(set_starting_position=False)
				self.window_player_url = "plugin://plugin.video.youtube/play/?video_id=%s" % chosen_var
				return window_player(self)
			elif self.control_id in self.text_list_ids:
				if self.control_id == self.parentsguide_id:
					return self.show_text_media(text=chosen_var)
				else:
					return self.select_item(self.control_id, self.show_text_media(text=self.get_attribute(self, chosen_var), current_index=position))
			elif self.control_id in self.open_folder_list_ids:
				try:
					chosen_var = self.get_listitem(self.control_id).getProperty(self.item_action_dict[self.control_id])
				except:
					return
				if not chosen_var:
					return
				try:
					self.close_all()
					chosen = self.get_attribute(self, chosen_var)[position]
					list_name, user, slug = chosen["name"], chosen["user"]["ids"]["slug"], chosen["ids"]["slug"]
					self.selected = self.folder_runner(
						{"mode": "trakt.list.build_trakt_list", "user": user, "slug": slug, "list_type": "user_lists", "list_name": list_name}
					)
					self.close()
				except:
					return
			else:
				return

	def make_plot_and_tagline(self):
		self.plot = self.meta_get("tvshow_plot", "") or self.meta_get("plot", "") or ""
		if not self.plot:
			return
		self.tagline = self.meta_get("tagline") or ""
		if self.tagline:
			self.plot = "[I]%s[/I][CR][CR]%s" % (self.tagline, self.plot)
		if self.plot_id in self.enabled_lists:
			self.setProperty("plot_enabled", "true")

	def get_release_year(self, release_data):
		try:
			if release_data in ("", None):
				release_data = "N/A"
			else:
				release_data = release_data.split("-")[0]
		except:
			pass
		return release_data

	def get_progress(self, percent_watched):
		return "%s%% Watched" % percent_watched

	def get_finish(self, percent_watched):
		finish_str = "No Finish Time"
		if self.duration_data:
			label = "Finish Rewatching" if percent_watched == "100" else "Finish Watching"
			kodi_clock = self.get_infolabel("System.Time")
			if any(i in kodi_clock for i in ("AM", "PM")):
				_format = "%I:%M %p"
			else:
				_format = "%H:%M"
			if percent_watched in ("0", "100"):
				remaining_time = self.duration_data
			else:
				remaining_time = ((100 - int(percent_watched)) / 100) * self.duration_data
			current_time = datetime.now()
			finish_time = current_time + timedelta(minutes=remaining_time)
			finished = finish_time.strftime(_format)
			finish_str = "%s: %s" % (label, finished)
		return finish_str

	def get_duration(self):
		time_str = ""
		if self.duration_data:
			hour, minute = divmod(self.duration_data, 60)
			if hour:
				time_str += "%dh" % hour
			if minute:
				time_str += "%s%sm" % (" " if hour else "", "%d" % minute if minute < 10 else "%02d" % minute)
		return time_str

	def get_last_aired(self):
		if self.extra_info_get("last_episode_to_air", False):
			last_ep = self.extra_info_get("last_episode_to_air")
			last_aired = "S%.2dE%.2d" % (last_ep["season_number"], last_ep["episode_number"])
		else:
			return ""
		return "Last Aired: %s" % last_aired

	def get_next_aired(self):
		if self.status in ("", "Ended", "Canceled"):
			return ""
		if self.extra_info_get("next_episode_to_air", False):
			next_ep = self.extra_info_get("next_episode_to_air")
			next_aired = "S%.2dE%.2d" % (next_ep["season_number"], next_ep["episode_number"])
		else:
			return ""
		return "Next Aired: %s" % next_aired

	def get_next_episode(self):
		self.nextep_season, self.nextep_episode = None, None
		value, curr_season_data, episode_date = "", [], None
		try:
			try:
				nextep_content = settings.nextep_method()
				ep_list = watched_status.get_next_episodes(nextep_content)
				ep_data = next((i for i in ep_list if i["media_ids"]["tmdb"] == self.tmdb_id), None)
				orig_season, orig_episode = ep_data.get("season"), ep_data.get("episode")
			except:
				orig_season, orig_episode = 1, 0
			season_data = self.meta_get("season_data")
			watched_info = watched_status.watched_info_episode(self.tmdb_id, watched_status.get_database(settings.watched_indicators()))
			nextep_season, nextep_episode = watched_status.get_next(orig_season, orig_episode, watched_info, season_data, nextep_content)
			if not nextep_season:
				return
			episodes_data = episodes_meta(nextep_season, self.meta)
			item = next((i for i in episodes_data if i["episode"] == nextep_episode), None)
			item_get = item.get
			episode_date, _premiered = adjust_premiered_date(item_get("premiered"), settings.date_offset())
			if episode_date and self.current_date >= episode_date:
				self.nextep_season, self.nextep_episode = nextep_season, nextep_episode
				value = "Next Episode: S%.2dE%.2d" % (self.nextep_season, self.nextep_episode)
		except:
			pass
		return value

	def make_tvshow_browse_params(self):
		all_episodes = settings.default_all_episodes()
		if all_episodes:
			if all_episodes == 1 and self.meta_get("total_seasons") > 1:
				url_params = {"mode": "build_season_list", "tmdb_id": self.tmdb_id}
			else:
				url_params = {"mode": "build_episode_list", "tmdb_id": self.tmdb_id, "season": "all"}
		else:
			url_params = {"mode": "build_season_list", "tmdb_id": self.tmdb_id}
		return url_params

	def remove_current_tmdb_mediaitem(self, data):
		return [i for i in data if int(i["id"]) != self.tmdb_id]

	def make_tmdb_listitems(self, data):
		used_ids = []
		append = used_ids.append
		name_key = "title" if self.media_type == "movie" else "name"
		release_key = "release_date" if self.media_type == "movie" else "first_air_date"
		for item in data:
			try:
				tmdb_id = item["id"]
				if tmdb_id in used_ids:
					continue
				listitem = self.make_listitem()
				year = self.get_release_year(item[release_key])
				poster = "https://image.tmdb.org/t/p/%s%s" % ("w300", item["poster_path"]) if item["poster_path"] else ""
				if self.rpdb_api_key and poster:
					media = "movie" if self.media_type == "movie" else "series"
					try:
						poster = (
							"https://api.ratingposterdb.com/%s/tmdb/poster-default/%s-%s.jpg?fallback=true" % (self.rpdb_api_key, media, str(item["id"]))
							+ self.rpdb_format
						)
					except:
						pass
				elif not poster:
					poster = self.empty_poster
				listitem.setProperties(
					{
						"name": item[name_key],
						"release_date": year,
						"vote_average": "%.1f" % item["vote_average"],
						"thumbnail": poster,
						"tmdb_id": str(tmdb_id),
						"info_alert": self.media_alert,
					}
				)
				append(tmdb_id)
				yield listitem
			except:
				pass

	def set_artwork(self):
		self.set_image(202, self.fanart)
		if self.clearlogo:
			self.set_image(201, self.clearlogo)
		else:
			self.setProperty("clearlogo", "false")
		self.set_image(200, self.poster)

	def set_infoline2(self):
		if self.media_type == "movie":
			percent_watched = watched_status.get_progress_status_movie(watched_status.get_bookmarks_movie(), str(self.tmdb_id))
			if not percent_watched:
				try:
					percent_watched = "100" if watched_status.get_watched_status_movie(watched_status.watched_info_movie(), str(self.tmdb_id)) == 1 else "0"
				except:
					percent_watched = "0"
				if not percent_watched:
					percent_watched = 0
			line2 = "[B]  •  [/B]".join([self.get_progress(percent_watched), self.get_finish(percent_watched)])
		else:
			line2 = "[B]  •  [/B]".join([i for i in (self.get_next_episode(), self.get_last_aired(), self.get_next_aired()) if i])
		self.set_label(3001, line2)

	def assign_buttons(self):
		setting_id_base = "forge.extras.%s.button" % self.media_type
		for item in self.button_ids[:-1]:
			setting_id = setting_id_base + str(item)
			try:
				button_action = self.get_setting(setting_id)
				button_label = self.button_label_values[self.media_type][button_action]
			except:
				self.restore_setting_default({"setting_id": setting_id.replace("forge.", ""), "silent": "true"})
				button_action = self.get_setting(setting_id)
				button_label = self.button_label_values[self.media_type][button_action]
			self.setProperty("button%s.label" % item, button_label)
			self.button_action_dict[item] = button_action
		self.button_action_dict[2050] = "show_plot"

	def set_default_focus(self):
		try:
			self.setFocusId(10)
		except:
			self.close_all()
			self.close()

	def set_returning_focus(self, list_id, focus, sleep_time=700):
		try:
			self.sleep(sleep_time)
			self.setFocusId(list_id)
			self.select_item(list_id, focus)
		except:
			self.set_default_focus()

	def set_current_params(self, set_starting_position=True):
		self.current_params = {"mode": "extras_menu_choice", "tmdb_id": self.tmdb_id, "media_type": self.media_type, "is_external": self.is_external}
		if set_starting_position:
			self.current_params["starting_position"] = [self.control_id, self.get_position(self.control_id)]

	def set_starting_constants(self, kwargs):
		self.meta = kwargs.get("meta")
		self.meta_get = self.meta.get
		self.media_type, self.options_media_type = self.meta_get("mediatype"), kwargs.get("options_media_type")
		self.starting_position = kwargs.get("starting_position", None)
		self.is_external = kwargs.get("is_external").lower()
		self.item_action_dict, self.button_action_dict = {}, {}
		self.selected = None
		self.current_date = get_datetime()
		self.playback_key = settings.playback_key()
		self.current_params, self.new_params = {}, {}
		self.extra_info = self.meta_get("extra_info")
		self.extra_info_get = self.extra_info.get
		self.tmdb_id, self.imdb_id = self.meta_get("tmdb_id"), self.meta_get("imdb_id")
		self.folder_runner = kodi_utils.activate_window if self.is_external == "true" else kodi_utils.container_update
		self.enabled_lists, self.enable_scrollbars = settings.extras_enabled(), settings.extras_enable_scrollbars()
		self.tmdb_api_key, self.omdb_api, self.mpaa_region = settings.tmdb_api_key(), settings.omdb_api_key(), settings.mpaa_region()
		self.display_extra_ratings = self.imdb_id and self.omdb_api not in ("empty_setting", "") and settings.extras_enable_extra_ratings()
		self.title, self.year, self.rootname = self.meta_get("title"), str(self.meta_get("year")), self.meta_get("rootname")
		rpdb_info = settings.rpdb_info("extras")
		self.rpdb_api_key, self.rpdb_format = rpdb_info["rpdb_api_key"], rpdb_info["rpdb_format"]
		self.poster = self.meta_get("poster") or self.empty_poster
		self.fanart = self.meta_get("fanart") or self.addon_fanart
		self.clearlogo = self.meta_get("clearlogo") or ""
		self.landscape = self.meta_get("landscape") or ""
		self.rating = str(round(self.meta_get("rating"), 1)) if self.meta_get("rating") not in ("", "%", 0, 0.0, None) else None
		self.mpaa, self.genre, self.network = self.meta_get("mpaa"), self.meta_get("genre"), self.meta_get("studio") or ""
		self.status, self.duration_data = self.extra_info_get("status", "").replace(" Series", ""), int(float(self.meta_get("duration")) / 60)
		self.status_infoline_value = self.make_status_infoline()
		self.stinger_dialog = self.make_stinger_dialog()
		self.single_rating_data = {"rating": self.rating, "icon": "tmdb.png"}
		self.make_plot_and_tagline()

	def set_properties(self):
		self.assign_buttons()
		self.set_home_property("window_theme.extras", self.get_home_property("window_theme"))
		(
			self.setProperty("media_type", self.media_type),
			self.setProperty("title", self.title),
			self.setProperty("year", self.year),
			self.setProperty("plot", self.plot),
		)
		(
			self.setProperty("genre", ", ".join(self.genre)),
			self.setProperty("network", ", ".join(self.network)),
			self.setProperty("enable_scrollbars", self.enable_scrollbars),
		)
		self.setProperty("display_extra_ratings", "true" if self.display_extra_ratings else "false")

	def close_all(self):
		kodi_utils.clear_property("forge.window_stack")
		kodi_utils.close_all_dialog()
