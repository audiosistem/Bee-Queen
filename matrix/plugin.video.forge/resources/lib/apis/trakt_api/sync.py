# -*- coding: utf-8 -*-
"""Watched indicators, playback progress, calendar, and the sync orchestrator.

`trakt_sync_activities` is the biggest function — it decides which other helpers
to call based on the diff between Trakt's last-activity timestamps and our
cached copy. `trakt_official_status` is here because it's the precondition that
the sync engine consults to decide whether the official `script.trakt` addon
would conflict.
"""

import time

from caches import settings_cache, trakt_cache
from modules import kodi_utils, settings
from modules.utils import TaskPool, timedelta
from modules.utils import jsondate_to_datetime as js2date

from .core import (
	call_trakt,
	get_trakt,
	get_trakt_movie_id,
	get_trakt_tvshow_id,
	trakt_refresh_token,
)

__all__ = [
	"trakt_calendar_days",
	"trakt_get_activity",
	"trakt_get_hidden_items",
	"trakt_get_my_calendar",
	"trakt_indicators_movies",
	"trakt_indicators_tv",
	"trakt_official_status",
	"trakt_playback_progress",
	"trakt_progress",
	"trakt_progress_movies",
	"trakt_progress_tv",
	"trakt_sync_activities",
	"trakt_watched_status_mark",
]


def trakt_get_hidden_items(list_type):
	def _get_trakt_ids(item):
		results_append(get_trakt_tvshow_id(item["show"]["ids"]))

	def _process(params):
		data = get_trakt(params)
		threads = TaskPool().tasks(_get_trakt_ids, data, min(len(data), settings.max_threads()))
		[i.join() for i in threads]
		return results

	results = []
	results_append = results.append
	string = "trakt_hidden_items_%s" % list_type
	params = {"path": "users/hidden/%s", "path_insert": list_type, "params": {"limit": 999, "type": "show"}, "with_auth": True, "pagination": False}
	return trakt_cache.cache_trakt_object(_process, string, params)


def trakt_watched_status_mark(action, media, media_id, tvdb_id=0, season=None, episode=None, key="tmdb"):
	if action == "mark_as_watched":
		url, result_key = "sync/history", "added"
	else:
		url, result_key = "sync/history/remove", "deleted"
	if media == "movies":
		success_key = "movies"
		data = {"movies": [{"ids": {key: media_id}}]}
	else:
		success_key = "episodes"
		if media == "episode":
			data = {"shows": [{"seasons": [{"episodes": [{"number": int(episode)}], "number": int(season)}], "ids": {key: media_id}}]}
		elif media == "shows":
			data = {"shows": [{"ids": {key: media_id}}]}
		else:
			data = {"shows": [{"ids": {key: media_id}, "seasons": [{"number": int(season)}]}]}  # season
	result = call_trakt(url, data=data)
	success = result[result_key][success_key] > 0
	if not success:
		if media != "movies" and tvdb_id != 0 and key != "tvdb":
			return trakt_watched_status_mark(action, media, tvdb_id, 0, season, episode, "tvdb")
	return success


def trakt_progress(action, media, media_id, percent, season=None, episode=None, resume_id=None, refresh_trakt=False):
	if action == "clear_progress":
		url = "sync/playback/%s" % resume_id
		call_trakt(url, is_delete=True)
	else:
		url = "scrobble/pause"
		if media in ("movie", "movies"):
			data = {"movie": {"ids": {"tmdb": media_id}}, "progress": float(percent)}
		else:
			data = {"show": {"ids": {"tmdb": media_id}}, "episode": {"season": int(season), "number": int(episode)}, "progress": float(percent)}
		call_trakt(url, data=data)
	if refresh_trakt:
		trakt_sync_activities()


def trakt_indicators_movies():
	def _process(item):
		try:
			movie = item["movie"]
			tmdb_id = get_trakt_movie_id(movie["ids"])
			if not tmdb_id:
				return
			insert_append(("movie", tmdb_id, "", "", item["last_watched_at"], movie["title"]))
		except (KeyError, TypeError):
			pass

	try:
		insert_list = []
		insert_append = insert_list.append
		params = {"path": "sync/watched/movies%s", "with_auth": True, "pagination": False}
		result = get_trakt(params)
		threads = TaskPool().tasks(_process, result, min(len(result), settings.max_threads()))
		[i.join() for i in threads]
		trakt_cache.trakt_watched_cache.set_bulk_movie_watched(insert_list)
	except Exception as e:
		kodi_utils.logger("Trakt indicators_movies error", str(e))


def trakt_indicators_tv():
	def _process(item):
		try:
			reset_at = item.get("reset_at", None)
			if reset_at:
				reset_at = js2date(reset_at, "%Y-%m-%dT%H:%M:%S.%fZ")
			show = item["show"]
			seasons = item["seasons"]
			title = show["title"]
			tmdb_id = get_trakt_tvshow_id(show["ids"])
			if not tmdb_id:
				return
			for s in seasons:
				season_no, episodes = s["number"], s["episodes"]
				for e in episodes:
					last_watched_at = e["last_watched_at"]
					if reset_at and reset_at > js2date(last_watched_at, "%Y-%m-%dT%H:%M:%S.%fZ"):
						continue
					insert_append(("episode", tmdb_id, season_no, e["number"], last_watched_at, title))
		except (KeyError, TypeError):
			pass

	try:
		insert_list = []
		insert_append = insert_list.append
		params = {"path": "users/me/watched/shows?extended=full%s", "with_auth": True, "pagination": False}
		result = get_trakt(params)
		threads = TaskPool().tasks(_process, result, min(len(result), settings.max_threads()))
		[i.join() for i in threads]
		trakt_cache.trakt_watched_cache.set_bulk_tvshow_watched(insert_list)
	except Exception as e:
		kodi_utils.logger("Trakt indicators_tv error", str(e))


def trakt_playback_progress():
	params = {"path": "sync/playback%s", "with_auth": True, "pagination": False}
	return get_trakt(params)


def trakt_progress_movies(progress_info):
	def _process(item):
		tmdb_id = get_trakt_movie_id(item["movie"]["ids"])
		if not tmdb_id:
			return
		obj = ("movie", str(tmdb_id), "", "", str(round(item["progress"], 1)), 0, item["paused_at"], item["id"], item["movie"]["title"])
		insert_append(obj)

	insert_list = []
	insert_append = insert_list.append
	progress_items = [i for i in progress_info if i["type"] == "movie" and i["progress"] > 1]
	if not progress_items:
		return
	threads = TaskPool().tasks(_process, progress_items, min(len(progress_items), settings.max_threads()))
	[i.join() for i in threads]
	trakt_cache.trakt_watched_cache.set_bulk_movie_progress(insert_list)


def trakt_progress_tv(progress_info):
	def _process_tmdb_ids(item):
		tmdb_id = get_trakt_tvshow_id(item["ids"])
		tmdb_list_append((tmdb_id, item["title"]))

	def _process():
		for item in tmdb_list:
			try:
				tmdb_id = item[0]
				if not tmdb_id:
					continue
				title = item[1]
				for p_item in progress_items:
					if p_item["show"]["title"] == title:
						season = p_item["episode"]["season"]
						if season > 0:
							yield (
								"episode",
								str(tmdb_id),
								season,
								p_item["episode"]["number"],
								str(round(p_item["progress"], 1)),
								0,
								p_item["paused_at"],
								p_item["id"],
								p_item["show"]["title"],
							)
			except (KeyError, TypeError):
				pass

	tmdb_list = []
	tmdb_list_append = tmdb_list.append
	progress_items = [i for i in progress_info if i["type"] == "episode" and i["progress"] > 1]
	if not progress_items:
		return
	all_shows = [i["show"] for i in progress_items]
	all_shows = [i for n, i in enumerate(all_shows) if i not in all_shows[n + 1 :]]  # remove duplicates
	threads = TaskPool().tasks(_process_tmdb_ids, all_shows, min(len(all_shows), settings.max_threads()))
	[i.join() for i in threads]
	insert_list = list(_process())
	trakt_cache.trakt_watched_cache.set_bulk_tvshow_progress(insert_list)


def trakt_official_status(media_type):
	if not kodi_utils.addon_installed("script.trakt"):
		return True
	if not kodi_utils.addon_enabled("script.trakt"):
		return True
	trakt_addon = kodi_utils.addon("script.trakt")
	try:
		authorization = trakt_addon.getSetting("authorization")
	except (RuntimeError, AttributeError):
		authorization = ""
	if authorization == "":
		return True
	try:
		exclude_http = trakt_addon.getSetting("ExcludeHTTP")
	except (RuntimeError, AttributeError):
		exclude_http = ""
	if exclude_http in ("true", ""):
		return True
	media_setting = "scrobble_movie" if media_type in ("movie", "movies") else "scrobble_episode"
	try:
		scrobble = trakt_addon.getSetting(media_setting)
	except (RuntimeError, AttributeError):
		scrobble = ""
	if scrobble in ("false", ""):
		return True
	return False


def trakt_get_my_calendar(recently_aired, current_date):
	def _process(dummy):
		data = get_trakt(params)
		data = [
			{
				"sort_title": "%s s%s e%s" % (i["show"]["title"], str(i["episode"]["season"]).zfill(2), str(i["episode"]["number"]).zfill(2)),
				"media_ids": i["show"]["ids"],
				"season": i["episode"]["season"],
				"episode": i["episode"]["number"],
				"first_aired": i["first_aired"],
			}
			for i in data
			if i["episode"]["season"] > 0
		]
		data = [i for n, i in enumerate(data) if i not in data[n + 1 :]]  # remove duplicates
		return data

	start, finish = trakt_calendar_days(recently_aired, current_date)
	string = "trakt_get_my_calendar_%s_%s" % (start, finish)
	params = {"path": "calendars/my/shows/%s/%s", "path_insert": (start, finish), "params": {"limit": 999}, "with_auth": True, "pagination": False}
	return trakt_cache.cache_trakt_object(_process, string, params)


def trakt_calendar_days(recently_aired, current_date):
	if recently_aired:
		start, finish = (current_date - timedelta(days=14)).strftime("%Y-%m-%d"), "14"
	else:
		previous_days = int(settings_cache.get_setting("forge.trakt.calendar_previous_days", "0"))
		future_days = int(settings_cache.get_setting("forge.trakt.calendar_future_days", "7"))
		start = (current_date - timedelta(days=previous_days)).strftime("%Y-%m-%d")
		finish = str(previous_days + future_days)
	return start, finish


def trakt_get_activity():
	params = {"path": "sync/last_activities%s", "with_auth": True, "pagination": False}
	return get_trakt(params)


def trakt_sync_activities(force_update=False):
	def refresh_token_check():
		current_time = time.time()
		sync_interval = int(settings_cache.get_setting("forge.trakt.sync_interval", "60")) * 60
		try:
			expires_at = float(settings_cache.get_setting("forge.trakt.expires"))
		except (ValueError, TypeError):
			expires_at = 0.0
		if current_time + sync_interval >= expires_at:
			return True

	def clear_properties(media_type):
		for item in ((True, True), (True, False), (False, True), (False, False)):
			kodi_utils.clear_property("1_%s_%s_%s_watched" % (media_type, item[0], item[1]))

	def _get_timestamp(date_time):
		return int(time.mktime(date_time.timetuple()))

	def _compare(latest, cached):
		try:
			result = _get_timestamp(js2date(latest, "%Y-%m-%dT%H:%M:%S.%fZ")) > _get_timestamp(js2date(cached, "%Y-%m-%dT%H:%M:%S.%fZ"))
		except (ValueError, TypeError):
			result = True
		return result

	def _check_daily_expiry():
		return int(time.time()) >= int(settings_cache.get_setting("forge.trakt.next_daily_clear", "0"))

	if refresh_token_check():
		trakt_refresh_token()
	if force_update:
		trakt_cache.clear_all_trakt_cache_data(silent=True, refresh=False)
	elif _check_daily_expiry():
		trakt_cache.clear_daily_cache()
		settings_cache.set_setting("trakt.next_daily_clear", str(int(time.time()) + (24 * 3600)))
	if not settings.trakt_user_active() and not force_update:
		return "no account"
	try:
		latest = trakt_get_activity()
	except Exception as e:
		kodi_utils.logger("Trakt sync_activities fetch failed", str(e))
		return "failed"
	cached = trakt_cache.reset_activity(latest)
	fallback_date = "2020-01-01T00:00:01.000Z"
	if not _compare(latest["all"], cached["all"]):
		return "not needed"
	lists_actions, refresh_movies_progress, refresh_shows_progress = [], False, False
	cached_movies, latest_movies = cached["movies"], latest["movies"]
	cached_shows, latest_shows = cached["shows"], latest["shows"]
	cached_episodes, latest_episodes = cached["episodes"], latest["episodes"]
	cached_lists, latest_lists = cached["lists"], latest["lists"]
	if _compare(latest["recommendations"], cached.get("recommendations", fallback_date)):
		trakt_cache.clear_trakt_recommendations()
	if _compare(latest["favorites"], cached.get("favorites", fallback_date)):
		trakt_cache.clear_trakt_favorites()
	if _compare(latest_movies["collected_at"], cached_movies.get("collected_at", fallback_date)):
		trakt_cache.clear_trakt_collection_watchlist_data("collection", "movie")
	if _compare(latest_episodes["collected_at"], cached_episodes.get("collected_at", fallback_date)):
		trakt_cache.clear_trakt_collection_watchlist_data("collection", "tvshow")
	if _compare(latest_movies["watchlisted_at"], cached_movies.get("watchlisted_at", fallback_date)):
		trakt_cache.clear_trakt_collection_watchlist_data("watchlist", "movie")
	if _compare(latest_shows["watchlisted_at"], cached_shows.get("watchlisted_at", fallback_date)):
		trakt_cache.clear_trakt_collection_watchlist_data("watchlist", "tvshow")
	if _compare(latest_shows["dropped_at"], cached_shows.get("dropped_at", fallback_date)):
		clear_properties("episode")
		trakt_cache.clear_trakt_hidden_data("dropped")
	if _compare(latest_movies["watched_at"], cached_movies.get("watched_at", fallback_date)):
		clear_properties("movie")
		trakt_indicators_movies()
	if _compare(latest_episodes["watched_at"], cached_episodes.get("watched_at", fallback_date)):
		clear_properties("episode")
		trakt_indicators_tv()
	if _compare(latest_movies["paused_at"], cached_movies.get("paused_at", fallback_date)):
		refresh_movies_progress = True
	if _compare(latest_episodes["paused_at"], cached_episodes.get("paused_at", fallback_date)):
		refresh_shows_progress = True
	if _compare(latest_lists["updated_at"], cached_lists.get("updated_at", fallback_date)):
		lists_actions.append("my_lists")
	if _compare(latest_lists["liked_at"], cached_lists.get("liked_at", fallback_date)):
		lists_actions.append("liked_lists")
	if refresh_movies_progress or refresh_shows_progress:
		progress_info = trakt_playback_progress()
		if refresh_movies_progress:
			clear_properties("movie")
			trakt_progress_movies(progress_info)
		if refresh_shows_progress:
			clear_properties("episode")
			trakt_progress_tv(progress_info)
	if lists_actions:
		for item in lists_actions:
			trakt_cache.clear_trakt_list_data(item)
			trakt_cache.clear_trakt_list_contents_data(item)
	return "success"
