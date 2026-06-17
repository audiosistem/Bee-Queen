# -*- coding: utf-8 -*-
from apis import imdb_api, tmdb_api, trakt_api
from modules import kodi_utils
from modules.meta_lists import movie_genres, networks, tvshow_genres
from modules.metadata import movie_meta, movieset_meta, tvshow_meta
from modules.utils import batch_replace, make_thread_list_enumerate


class SectionsMixin:
	"""Per-section list builders.

	Each ``make_*`` populates one ``ControlList`` on the Extras window. They
	are launched as parallel daemon threads from :meth:`Extras.onInit` via the
	``self.tasks`` tuple — order in that tuple controls launch order, not paint
	order. Methods early-return when their control ID isn't in
	``self.enabled_lists`` so the user can turn sections off.
	"""

	def make_cast(self):
		if self.cast_id not in self.enabled_lists:
			return

		def builder():
			cast = self.meta_get("cast")
			for item in cast:
				try:
					listitem = self.make_listitem()
					name, role = item["name"], item["role"]
					listitem.setProperty("name", "%s%s" % (name, " as %s" % role if role else ""))
					listitem.setProperty("name_lookup", name)
					listitem.setProperty("thumbnail", item["thumbnail"] or icon)
					listitem.setProperty("info_alert", self.actor_alert)
					yield listitem
				except:
					pass

		try:
			icon = kodi_utils.get_icon("empty_person")
			item_list = list(builder())
			self.setProperty("cast.number", "x%s" % len(item_list))
			self.item_action_dict[self.cast_id] = "name_lookup"
			self.add_items(self.cast_id, item_list)
		except:
			pass

	def make_recommended(self):
		if self.recommended_id not in self.enabled_lists:
			return
		try:
			function = tmdb_api.tmdb_movies_recommendations if self.media_type == "movie" else tmdb_api.tmdb_tv_recommendations
			data = function(self.tmdb_id, 1)["results"]
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty("recommended.number", "x%s" % len(item_list))
			self.item_action_dict[self.recommended_id] = "tmdb_id"
			self.add_items(self.recommended_id, item_list)
		except:
			pass

	def make_related(self):
		if self.related_id not in self.enabled_lists:
			return

		def builder(position, item):
			try:
				details = function("trakt_dict", item, self.tmdb_api_key, self.mpaa_region, self.current_date, current_time=None)
				poster = details["poster"]
				if self.rpdb_api_key and poster:
					try:
						poster = details["rpdb_poster"] % self.rpdb_api_key + self.rpdb_format
					except:
						pass
				elif not poster:
					poster = self.empty_poster
				listitem = self.make_listitem()
				listitem.setProperty("name", details["title"])
				listitem.setProperty("release_date", details["year"])
				listitem.setProperty("vote_average", "%.1f" % details["rating"])
				listitem.setProperty("thumbnail", poster)
				listitem.setProperty("tmdb_id", str(details["tmdb_id"]))
				listitem.setProperty("info_alert", self.media_alert)
				item_list_append((listitem, position))
			except:
				pass

		if self.media_type == "movie":
			data_function, function = trakt_api.trakt_movies_related, movie_meta
		else:
			data_function, function = trakt_api.trakt_tv_related, tvshow_meta
		data = [i["ids"] for i in data_function(self.imdb_id)]
		item_list = []
		item_list_append = item_list.append
		threads = list(make_thread_list_enumerate(builder, data))
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		item_list = [i[0] for i in item_list]
		self.setProperty("related.number", "x%s" % len(item_list))
		self.item_action_dict[self.related_id] = "tmdb_id"
		self.add_items(self.related_id, item_list)

	def make_more_like_this(self):
		if self.more_like_this_id not in self.enabled_lists:
			return

		def builder(position, item):
			try:
				details = function("imdb_id", item, self.tmdb_api_key, self.mpaa_region, self.current_date, current_time=None)
				listitem = self.make_listitem()
				poster = details["poster"]
				if self.rpdb_api_key and poster:
					try:
						poster = details["rpdb_poster"] % self.rpdb_api_key + self.rpdb_format
					except:
						pass
				elif not poster:
					poster = self.empty_poster
				listitem.setProperty("name", details["title"])
				listitem.setProperty("release_date", details["year"])
				listitem.setProperty("vote_average", "%.1f" % details["rating"])
				listitem.setProperty("thumbnail", poster)
				listitem.setProperty("tmdb_id", str(details["tmdb_id"]))
				listitem.setProperty("info_alert", self.media_alert)
				item_list_append((listitem, position))
			except:
				pass

		data = imdb_api.imdb_more_like_this(self.imdb_id)
		function = movie_meta if self.media_type == "movie" else tvshow_meta
		item_list = []
		item_list_append = item_list.append
		threads = list(make_thread_list_enumerate(builder, data))
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		item_list = [i[0] for i in item_list]
		self.setProperty("more_like_this.number", "x%s" % len(item_list))
		self.item_action_dict[self.more_like_this_id] = "tmdb_id"
		self.add_items(self.more_like_this_id, item_list)

	def make_imdb_extras(self):
		imdb_extras = imdb_api.imdb_extras(self.imdb_id)
		self.make_reviews(imdb_extras["reviews"])
		self.make_trivia(imdb_extras["trivia"])
		self.make_blunders(imdb_extras["blunders"])
		self.make_parentsguide(imdb_extras["parentsguide"])

	def make_reviews(self, all_reviews):
		if self.reviews_id not in self.enabled_lists:
			return

		def builder():
			for item in self.all_reviews:
				try:
					listitem = self.make_listitem()
					listitem.setProperty("text", item)
					listitem.setProperty("content_list", "all_reviews")
					yield listitem
				except:
					pass

		try:
			self.all_reviews = all_reviews
			item_list = list(builder())
			self.setProperty("imdb_reviews.number", "x%s" % len(item_list))
			self.item_action_dict[self.reviews_id] = "content_list"
			self.add_items(self.reviews_id, item_list)
		except:
			pass

	def make_comments(self):
		if self.comments_id not in self.enabled_lists:
			return

		def builder():
			for item in self.all_comments:
				try:
					listitem = self.make_listitem()
					listitem.setProperty("text", item)
					listitem.setProperty("content_list", "all_comments")
					yield listitem
				except:
					pass

		try:
			self.all_comments = trakt_api.trakt_comments(self.media_type, self.imdb_id)
			item_list = list(builder())
			self.setProperty("trakt_comments.number", "x%s" % len(item_list))
			self.item_action_dict[self.comments_id] = "content_list"
			self.add_items(self.comments_id, item_list)
		except:
			pass

	def make_in_lists(self):
		if self.in_lists_id not in self.enabled_lists:
			return

		def builder():
			for count, item in enumerate(self.all_in_lists, 1):
				try:
					listitem = self.make_listitem()
					compare = (item["ids"]["slug"], item["user"]["ids"]["slug"])
					if compare in liked_lists:
						liked = "true"
					else:
						liked = "false"
					likes = item.get("likes", "")
					likes_insert = "[CR]%s %s" % (likes, "Likes" if likes > 1 else "Like") if likes else ""
					listitem.setProperty(
						"name",
						template % (count, batch_replace(item["name"].upper(), replacements), likes_insert, item["user"]["ids"]["slug"], item["item_count"]),
					)
					listitem.setProperty("content_list", "all_in_lists")
					listitem.setProperty("thumbnail", icon)
					listitem.setProperty("liked_status", liked)
					listitem.setProperty("info_alert", self.list_alert)
					yield listitem
				except:
					pass

		try:
			icon = kodi_utils.get_icon("trakt")
			liked_lists = trakt_api.trakt_get_lists("liked_lists")
			try:
				liked_lists = [(i["list"]["ids"]["slug"], i["list"]["user"]["ids"]["slug"]) for i in liked_lists]
			except:
				liked_lists = []
			template, replacements = "%02d.[CR][B]%s[/B]%s[CR][CR]by %s[CR](x%02d)", (("-", " "), ("_", " "), (".", " "))
			self.all_in_lists = trakt_api.trakt_lists_with_media(self.media_type, self.imdb_id)
			item_list = list(builder())
			self.setProperty("trakt_in_lists.number", "x%s" % len(item_list))
			self.item_action_dict[self.in_lists_id] = "content_list"
			self.add_items(self.in_lists_id, item_list)
		except:
			pass

	def make_trivia(self, all_trivia):
		if self.trivia_id not in self.enabled_lists:
			return

		def builder():
			for item in self.all_trivia:
				try:
					listitem = self.make_listitem()
					listitem.setProperty("text", item)
					listitem.setProperty("content_list", "all_trivia")
					yield listitem
				except:
					pass

		try:
			self.all_trivia = all_trivia
			item_list = list(builder())
			self.setProperty("imdb_trivia.number", "x%s" % len(item_list))
			self.item_action_dict[self.trivia_id] = "content_list"
			self.add_items(self.trivia_id, item_list)
		except:
			pass

	def make_blunders(self, all_blunders):
		if self.blunders_id not in self.enabled_lists:
			return

		def builder():
			for item in self.all_blunders:
				try:
					listitem = self.make_listitem()
					listitem.setProperty("text", item)
					listitem.setProperty("content_list", "all_blunders")
					yield listitem
				except:
					pass

		try:
			self.all_blunders = all_blunders
			item_list = list(builder())
			self.setProperty("imdb_blunders.number", "x%s" % len(item_list))
			self.item_action_dict[self.blunders_id] = "content_list"
			self.add_items(self.blunders_id, item_list)
		except:
			pass

	def make_parentsguide(self, all_parentsguide):
		if self.parentsguide_id not in self.enabled_lists:
			return

		def builder():
			for item in all_parentsguide:
				try:
					listitem = self.make_listitem()
					name = item["title"]
					ranking = item["ranking"].upper()
					if ranking == "NONE":
						ranking = "NO RANK"
					if item["content"]:
						ranking += " (x%02d)" % item["total_count"]
					icon = self.parentsguide_icons[name]
					listitem.setProperty("name", name)
					listitem.setProperty("ranking", ranking)
					listitem.setProperty("thumbnail", icon)
					listitem.setProperty("content", item["content"])
					yield listitem
				except:
					pass

		try:
			item_list = list(builder())
			self.setProperty("imdb_parentsguide.number", "x%s" % len(item_list))
			self.item_action_dict[self.parentsguide_id] = "content"
			self.add_items(self.parentsguide_id, item_list)
		except:
			pass

	def make_videos(self):
		if self.videos_id not in self.enabled_lists:
			return

		def _sort_trailers(trailers):
			official_trailers = [i for i in trailers if i["official"] and i["type"] == "Trailer" and "official trailer" in i["name"].lower()]
			other_official_trailers = [i for i in trailers if i["official"] and i["type"] == "Trailer" and i not in official_trailers]
			other_trailers = [i for i in trailers if i["type"] == "Trailer" and i not in official_trailers and i not in other_official_trailers]
			teaser_trailers = [i for i in trailers if i["type"] == "Teaser"]
			full_trailers = official_trailers + other_official_trailers + other_trailers + teaser_trailers
			features = [i for i in trailers if i not in full_trailers]
			return full_trailers + features

		def builder():
			for item in all_trailers:
				try:
					listitem = self.make_listitem()
					key = item["key"]
					listitem.setProperty("name", item["name"])
					listitem.setProperty("thumbnail", "https://img.youtube.com/vi/%s/0.jpg" % key)
					listitem.setProperty("key_id", key)
					yield listitem
				except:
					pass

		try:
			all_trailers = _sort_trailers(self.meta_get("all_trailers", []))
			item_list = list(builder())
			self.setProperty("youtube_videos.number", "x%s" % len(item_list))
			self.item_action_dict[self.videos_id] = "key_id"
			self.add_items(self.videos_id, item_list)
		except:
			pass

	def make_year(self):
		if self.year_id not in self.enabled_lists:
			return
		try:
			function = tmdb_api.tmdb_movies_year if self.media_type == "movie" else tmdb_api.tmdb_tv_year
			data = self.remove_current_tmdb_mediaitem(function(self.year, 1)["results"])
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty("more_from_year.number", "x%s" % len(item_list))
			self.item_action_dict[self.year_id] = "tmdb_id"
			self.add_items(self.year_id, item_list)
		except:
			pass

	def make_genres(self):
		if self.genres_id not in self.enabled_lists:
			return
		try:
			function, genre_list = (tmdb_api.tmdb_movies_genres, movie_genres()) if self.media_type == "movie" else (tmdb_api.tmdb_tv_genres, tvshow_genres())
			genre_list = ",".join([i["id"] for i in genre_list if i["name"] in self.genre])
			data = self.remove_current_tmdb_mediaitem(function(genre_list, 1)["results"])
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty("more_from_genres.number", "x%s" % len(item_list))
			self.item_action_dict[self.genres_id] = "tmdb_id"
			self.add_items(self.genres_id, item_list)
		except:
			pass

	def make_network(self):
		if self.networks_id not in self.enabled_lists:
			return
		try:
			network = self.meta_get("studio")[0]
			network_list = tmdb_api.tmdb_company_id(network)["results"] if self.media_type == "movie" else networks()
			network_id = next(i["id"] for i in network_list if i["name"] == network)
			function = tmdb_api.tmdb_movies_companies if self.media_type == "movie" else tmdb_api.tmdb_tv_networks
			data = self.remove_current_tmdb_mediaitem(function(network_id, 1)["results"])
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty("more_from_networks.number", "x%s" % len(item_list))
			self.item_action_dict[self.networks_id] = "tmdb_id"
			self.add_items(self.networks_id, item_list)
		except:
			pass

	def make_collection(self):
		if self.media_type != "movie":
			return
		if self.collection_id not in self.enabled_lists:
			return
		try:
			coll_id = self.extra_info_get("collection_id")
		except:
			return
		if not coll_id:
			return
		try:
			data = movieset_meta(coll_id, self.tmdb_api_key)
			item_list = list(self.make_tmdb_listitems(sorted(data["parts"], key=lambda k: k["release_date"] or "2050")))
			self.setProperty("more_from_collection.name", data["title"])
			self.setProperty("more_from_collection.overview", data["plot"] or data["title"])
			self.setProperty("more_from_collection.poster", data["poster"] or self.empty_poster)
			self.setProperty("more_from_collection.number", "x%s" % len(item_list))
			self.item_action_dict[self.collection_id] = "tmdb_id"
			self.add_items(self.collection_id, item_list)
		except:
			pass
