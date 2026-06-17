# -*- coding: utf-8 -*-
from apis import tmdb_api
from indexers import dialogs
from indexers.images import Images
from modules import kodi_utils
from modules.episode_tools import EpisodeTools
from modules.meta_lists import movie_genres, networks, tvshow_genres
from modules.sources import Sources
from modules.utils import get_current_timestamp
from windows.base_window import window_manager, window_player


class ActionsMixin:
	"""Button handlers — every ``show_*`` / ``play_*`` / ``movies_play`` /
	``tvshow_browse`` / ``playback_choice`` is dispatched by
	:meth:`Extras.onClick` via the ``button_action_dict`` (see
	:meth:`Extras.assign_buttons`).
	"""

	def show_text_media(self, text, poster=None, current_index=None):
		return self.open_window(
			("windows.extras", "ShowTextMedia"), "textviewer_media.xml", text=text, poster=poster or self.poster, current_index=current_index
		)

	def tvshow_browse(self):
		self.close_all()
		url_params = self.make_tvshow_browse_params()
		self.selected = self.folder_runner(url_params)
		self.close()

	def movies_play(self):
		Sources().playback_prep({"media_type": "movie", "tmdb_id": self.tmdb_id, self.playback_key: self.playback_key})

	def show_plot(self):
		return self.show_text_media(text=self.plot)

	def show_trailers(self):
		if not kodi_utils.addon_installed("plugin.video.youtube") or not kodi_utils.addon_enabled("plugin.video.youtube"):
			return kodi_utils.notification("Youtube Plugin needed for playback")
		self.set_current_params(set_starting_position=False)
		self.window_player_url = self.meta_get("trailer")
		return window_player(self)

	def show_images(self):
		return Images().run({"mode": "tmdb_media_image_results", "media_type": self.media_type, "tmdb_id": self.tmdb_id, "rootname": self.rootname})

	def show_extrainfo(self, meta=None):
		if meta:
			text = "[B]  •  [/B]".join(
				[i for i in (meta.get("year"), str(round(meta.get("rating"), 1)) if meta.get("rating") not in (0, 0.0, None) else None, meta.get("mpaa")) if i]
			) + "[CR][CR]%s" % meta.get("plot")
			poster = meta.get("poster", self.empty_poster)
		else:
			text, poster = dialogs.media_extra_info_choice({"media_type": self.media_type, "meta": self.meta}), self.poster
		return self.show_text_media(text=text, poster=poster)

	def show_genres(self):
		if not self.genre:
			return
		genre_id = dialogs.genres_choice(
			{"genres_list": movie_genres() if self.media_type == "movie" else tvshow_genres(), "genres": self.genre, "poster": self.poster}
		)
		if not genre_id:
			return
		self.close_all()
		mode, action = ("build_movie_list", "tmdb_movies_genres") if self.media_type == "movie" else ("build_tvshow_list", "tmdb_tv_genres")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": genre_id})
		self.close()

	def show_keywords(self):
		keyword_id = dialogs.keywords_choice({"media_type": self.media_type, "meta": self.meta})
		if not keyword_id:
			return
		self.close_all()
		mode, action = ("build_movie_list", "tmdb_movie_keyword_results") if self.media_type == "movie" else ("build_tvshow_list", "tmdb_tv_keyword_results")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": keyword_id})
		self.close()

	def play_nextep(self):
		if self.nextep_season == None:
			return kodi_utils.ok_dialog(text="No Episodes Available")
		Sources().playback_prep(
			{
				"media_type": "episode",
				"tmdb_id": self.tmdb_id,
				"season": self.nextep_season,
				"episode": self.nextep_episode,
				"autoplay": "true",
				self.playback_key: self.playback_key,
			}
		)

	def play_random_episode(self):
		self.close_all()
		function = dialogs.random_choice({"meta": self.meta, "poster": self.poster, "return_choice": "true"})
		if not function:
			return
		exec("EpisodeTools(self.meta).%s()" % function)
		self.close()

	def show_director(self):
		try:
			director = self.meta_get("director", None)[0]
		except:
			return self.notification("No Director Information Available")
		if not director:
			return
		self.set_current_params(set_starting_position=False)
		self.new_params = {"mode": "person_data_dialog", "key_id": director, "is_external": self.is_external, "stacked": "true"}
		window_manager(self)

	def show_options(self):
		params = {
			"content": self.options_media_type,
			"tmdb_id": str(self.tmdb_id),
			"poster": self.poster,
			"is_external": self.is_external,
			"from_extras": "true",
		}
		return dialogs.options_menu_choice(params, self.meta)

	def show_recommended(self):
		self.close_all()
		mode, action = ("build_movie_list", "tmdb_movies_recommendations") if self.media_type == "movie" else ("build_tvshow_list", "tmdb_tv_recommendations")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": self.tmdb_id, "name": "Recommended based on %s" % self.title})
		self.close()

	def show_related(self):
		self.close_all()
		mode, action = ("build_movie_list", "trakt_movies_related") if self.media_type == "movie" else ("build_tvshow_list", "trakt_tv_related")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": self.imdb_id, "name": "Related to %s" % self.title})
		self.close()

	def show_more_like_this(self):
		return self.show_network()
		self.close_all()
		mode = "build_movie_list" if self.media_type == "movie" else "build_tvshow_list"
		self.selected = self.folder_runner(
			{"mode": mode, "action": "imdb_more_like_this", "key_id": self.imdb_id, "name": "More Like This based on %s" % self.title}
		)
		self.close()

	def show_reviews(self):
		if not self.all_reviews:
			return self.notification("No Reviews")
		return self.select_item(self.control_id, self.show_text_media(text=self.all_reviews, current_index=0))

	def show_comments(self):
		if not self.all_comments:
			return self.notification("No Comments")
		return self.select_item(self.control_id, self.show_text_media(text=self.all_comments, current_index=0))

	def show_trivia(self):
		if not self.all_trivia:
			return self.notification("No Trivia")
		return self.select_item(self.control_id, self.show_text_media(text=self.all_trivia, current_index=0))

	def show_blunders(self):
		if not self.all_blunders:
			return self.notification("No Blunders")
		return self.select_item(self.control_id, self.show_text_media(text=self.all_blunders, current_index=0))

	def show_year(self):
		if not self.year:
			return self.notification("Error getting Year")
		self.close_all()
		mode, action = ("build_movie_list", "tmdb_movies_year") if self.media_type == "movie" else ("build_tvshow_list", "tmdb_tv_year")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": self.year, "name": "More from %s" % self.year})
		self.close()

	def show_genre(self):
		try:
			genre_list = ",".join([i["id"] for i in (movie_genres() if self.media_type == "movie" else tvshow_genres()) if i["name"] in self.genre])
			if not genre_list:
				return self.notification("Error getting Genres")
		except:
			return self.notification("Error getting Genres")
		self.close_all()
		mode, action = ("build_movie_list", "tmdb_movies_genres") if self.media_type == "movie" else ("build_tvshow_list", "tmdb_tv_genres")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": genre_list, "name": "More from %s" % ", ".join([i for i in self.genre])})
		self.close()

	def show_network(self):
		try:
			network = self.meta_get("studio")[0]
			network_id = tmdb_api.tmdb_company_id(network)["results"] if self.media_type == "movie" else networks()
			network_id = next(i["id"] for i in network_id if i["name"] == network)
			if not network_id:
				return self.notification("Error getting Network")
		except:
			return self.notification("Error getting Network")
		self.close_all()
		mode, action = ("build_movie_list", "tmdb_movies_companies") if self.media_type == "movie" else ("build_tvshow_list", "tmdb_tv_networks")
		self.selected = self.folder_runner({"mode": mode, "action": action, "key_id": network_id, "name": "More from %s" % network})
		self.close()

	def show_in_trakt_lists(self):
		self.close_all()
		media_type = "movies" if self.media_type == "movie" else "shows"
		self.selected = self.folder_runner(
			{"mode": "trakt.list.in_trakt_lists", "media_type": media_type, "imdb_id": self.imdb_id, "category_name": "%s In Trakt Lists" % self.title}
		)
		self.close()

	def show_trakt_manager(self):
		return dialogs.trakt_manager_choice(
			{"tmdb_id": self.tmdb_id, "imdb_id": self.imdb_id, "tvdb_id": self.meta_get("tvdb_id", "None"), "media_type": self.media_type, "icon": self.poster}
		)

	def show_personallists_manager(self):
		return dialogs.personallists_manager_choice(
			{
				"list_type": self.media_type,
				"tmdb_id": self.tmdb_id,
				"title": self.title,
				"premiered": self.meta_get("premiered"),
				"current_time": get_current_timestamp(),
				"icon": self.poster,
			}
		)

	def show_tmdb_manager(self):
		return dialogs.tmdblists_manager_choice({"media_type": "movie" if self.media_type == "movie" else "tv", "tmdb_id": self.tmdb_id, "icon": self.poster})

	def show_favorites_manager(self):
		return dialogs.favorites_manager_choice({"media_type": self.media_type, "tmdb_id": str(self.tmdb_id), "title": self.title, "refresh": "false"})

	def playback_choice(self):
		params = {"media_type": self.media_type, "meta": self.meta, "season": None, "episode": None}
		dialogs.playback_choice(params)
