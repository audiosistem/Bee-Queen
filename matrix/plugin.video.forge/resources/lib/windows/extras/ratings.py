# -*- coding: utf-8 -*-
from apis import omdb_api
from modules import settings
from modules.utils import adjust_premiered_date


class RatingsMixin:
	"""``make_ratings`` + the two infoline label painters.

	``make_ratings`` owns label 2001 — it paints the cached TMDb rating first so
	the infoline never blocks on OMDB, then upgrades the same label in-place
	once OMDB returns. This is the I2 fix from Phase 3: ``set_infoline1`` is
	*not* a parallel task on ``self.tasks`` any more, it's a helper this mixin
	calls.
	"""

	def make_ratings(self, win_prop=4000):
		self.set_infoline1()
		data, current_settings = self.get_omdb_ratings()
		final_ratings = []
		if not current_settings:
			return
		if len(data) == 1:
			return
		if len(current_settings) == 1:
			try:
				data = data[next((i[1] for i in self.meta_ratings_values if i[0] == current_settings[0]))]
				rating = data["rating"]
				if rating in ("", "%"):
					return
				if data["rating"] in ("", "%"):
					return
				return self.set_infoline1(rating_data=data)
			except:
				return
		elif win_prop == 4000:
			self.set_infoline1(remove_rating=True)
		for check, prop, _id in self.meta_ratings_values:
			try:
				if check not in current_settings:
					continue
				rating = data[prop]["rating"]
				if rating in ("", "%"):
					continue
				final_ratings.append({"prop": prop, "_id": _id, "rating": rating, "icon": data[prop]["icon"]})
			except:
				pass
		if not final_ratings:
			return
		if len(final_ratings) == 1:
			return self.set_infoline1(rating_data=final_ratings[0])
		for item in final_ratings:
			self.setProperty("%s_rating" % item["prop"], "true")
			self.set_label(win_prop + item["_id"], item["rating"])
			self.set_image(win_prop + 100 + item["_id"], "forge_flags/ratings/%s" % item["icon"])

	def get_omdb_ratings(self):
		if not self.display_extra_ratings:
			return None, None
		current_settings = settings.extras_enabled_ratings()
		if not current_settings:
			return None, None
		data = self.meta_get("extra_ratings", None) or omdb_api.fetch_ratings_info(self.meta, self.omdb_api)
		if not data:
			return None, None
		if data["tmdb"]["rating"] == "" and self.rating is not None:
			data["tmdb"]["rating"] = self.rating
		return data, current_settings

	def set_infoline1(self, rating_data=None, remove_rating=False):
		if remove_rating:
			rating = None
			self.set_image(203, "")
		else:
			data = rating_data or self.single_rating_data
			rating, image = data["rating"], "forge_flags/ratings/%s" % data["icon"]
			if rating:
				self.set_image(203, image)
		self.set_label(
			2001, "[B]  •  [/B]".join([i for i in (rating, self.year, self.mpaa, self.get_duration(), self.stinger_dialog, self.status_infoline_value) if i])
		)

	def make_status_infoline(self):
		status_str = self.status
		if self.media_type == "tvshow" and self.status == "Returning":
			try:
				next_aired_date = self.extra_info_get("next_episode_to_air")["air_date"]
			except:
				next_aired_date = None
			if next_aired_date:
				status_str = "%s %s" % (self.status, adjust_premiered_date(next_aired_date, settings.date_offset())[0].strftime("%d %B %Y"))
		return status_str

	def make_stinger_dialog(self):
		stinger_dialog = ""
		if self.media_type == "movie":
			stinger_keys = self.meta_get("stinger_keys", None)
			if not stinger_keys:
				try:
					keywords = self.meta_get("keywords", [])
					stinger_keys = [i["name"] for i in keywords["keywords"] if i["name"] in ("duringcreditsstinger", "aftercreditsstinger")]
				except:
					pass
			if stinger_keys:
				stinger_names = tuple(sorted([{"duringcreditsstinger": "During", "aftercreditsstinger": "After"}[i] for i in stinger_keys], reverse=True))
				stinger_dialog = {1: "%s Credits Stinger", 2: "%s & %s Credits Stinger"}[len(stinger_names)] % stinger_names
		return stinger_dialog
