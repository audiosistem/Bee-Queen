# -*- coding: utf-8 -*-
"""Collections, watchlists, user lists, list-selection UI, list likes."""

import json
from urllib.parse import unquote

from caches import trakt_cache
from caches.main_cache import cache_object
from modules import kodi_utils, settings
from modules.utils import get_datetime, sort_for_article, sort_list
from modules.utils import jsondate_to_datetime as js2date

from .core import call_trakt, get_trakt
from .sync import trakt_sync_activities

__all__ = [
	"add_to_collection",
	"add_to_list",
	"add_to_watchlist",
	"delete_trakt_list",
	"get_trakt_list_contents",
	"get_trakt_list_selection",
	"hide_unhide_progress_items",
	"make_new_trakt_list",
	"remove_from_collection",
	"remove_from_list",
	"remove_from_watchlist",
	"trakt_collection",
	"trakt_collection_lists",
	"trakt_favorites",
	"trakt_fetch_collection_watchlist",
	"trakt_get_lists",
	"trakt_like_a_list",
	"trakt_lists_with_media",
	"trakt_search_lists",
	"trakt_unlike_a_list",
	"trakt_watchlist",
	"trakt_watchlist_lists",
]


def trakt_collection_lists(media_type, list_type=None):
	data = trakt_fetch_collection_watchlist("collection", media_type)
	if list_type == "recent":
		data.sort(key=lambda k: k["collected_at"], reverse=True)
		data = data[:20]
	return data


def trakt_watchlist_lists(media_type, list_type=None):
	data = trakt_fetch_collection_watchlist("watchlist", media_type)
	if list_type == "recent":
		data.sort(key=lambda k: k["collected_at"], reverse=True)
		data = data[:20]
	return data


def trakt_collection(media_type, dummy_arg):
	data = trakt_fetch_collection_watchlist("collection", media_type)
	sort_order = settings.lists_sort_order("collection")
	if sort_order == 0:
		data = sort_for_article(data, "title", settings.ignore_articles())
	elif sort_order == 1:
		data.sort(key=lambda k: k["collected_at"], reverse=True)
	else:
		data.sort(key=lambda k: k["released"], reverse=True)
	return data


def trakt_watchlist(media_type, dummy_arg):
	data = trakt_fetch_collection_watchlist("watchlist", media_type)
	if not settings.show_unaired_watchlist():
		current_date = get_datetime()
		str_format = "%Y-%m-%d" if media_type in ("movie", "movies") else "%Y-%m-%dT%H:%M:%S.%fZ"
		data = [i for i in data if i.get("released", None) and js2date(i.get("released"), str_format, remove_time=True) <= current_date]
	sort_order = settings.lists_sort_order("watchlist")
	if sort_order == 0:
		data = sort_for_article(data, "title", settings.ignore_articles())
	elif sort_order == 1:
		data.sort(key=lambda k: k["collected_at"], reverse=True)
	else:
		data.sort(key=lambda k: k.get("released"), reverse=True)
	return data


def trakt_fetch_collection_watchlist(list_type, media_type):
	def _process(params):
		data = get_trakt(params)
		if list_type == "watchlist":
			data = [i for i in data if i["type"] == key]
		return [
			{
				"media_ids": {"tmdb": i[key]["ids"].get("tmdb", ""), "imdb": i[key]["ids"].get("imdb", ""), "tvdb": i[key]["ids"].get("tvdb", "")},
				"title": i[key]["title"],
				"collected_at": i.get(collected_at),
				"released": i[key].get(r_key) if i[key].get(r_key) else ("2050-01-01" if media_type == "movie" else "2050-01-01T01:00:00.000Z"),
			}
			for i in data
		]

	if media_type in ("movie", "movies"):
		media_type, url_type = ("movie", "movies")
	if media_type in ("show", "shows", "tvshow"):
		media_type, url_type = ("show", "shows")
	key, r_key, string_insert = ("movie", "released", "movie") if media_type == "movie" else ("show", "first_aired", "tvshow")
	collected_at = "listed_at" if list_type == "watchlist" else "collected_at" if media_type == "movie" else "last_collected_at"
	string = "trakt_%s_%s" % (list_type, string_insert)
	path = "sync/%s/%s?extended=full"
	params = {"path": path, "path_insert": (list_type, url_type), "params": {"limit": 999}, "with_auth": True, "pagination": False}
	return trakt_cache.cache_trakt_object(_process, string, params)


def add_to_list(user, slug, data):
	result = call_trakt("/users/%s/lists/%s/items" % (user, slug), data=data)
	if result["existing"]["movies"] + result["existing"]["shows"] > 0:
		return kodi_utils.notification("Already In List", 3000)
	if result["added"]["movies"] + result["added"]["shows"] == 0:
		return kodi_utils.notification("Error", 3000)
	kodi_utils.notification("Success", 3000)
	trakt_sync_activities()
	return result


def remove_from_list(user, slug, data):
	result = call_trakt("/users/%s/lists/%s/items/remove" % (user, slug), data=data)
	if result["deleted"]["movies"] + result["deleted"]["shows"] == 0:
		return kodi_utils.notification("Error", 3000)
	kodi_utils.notification("Success", 3000)
	trakt_sync_activities()
	if kodi_utils.path_check("my_lists") or kodi_utils.external():
		kodi_utils.kodi_refresh()
	return result


def add_to_watchlist(data):
	result = call_trakt("/sync/watchlist", data=data)
	if result["existing"]["movies"] + result["existing"]["shows"] > 0:
		return kodi_utils.notification("Already In List", 3000)
	if result["added"]["movies"] + result["added"]["shows"] == 0:
		return kodi_utils.notification("Error", 3000)
	kodi_utils.notification("Success", 3000)
	trakt_sync_activities()
	return result


def remove_from_watchlist(data):
	result = call_trakt("/sync/watchlist/remove", data=data)
	if result["deleted"]["movies"] + result["deleted"]["shows"] == 0:
		return kodi_utils.notification("Error", 3000)
	kodi_utils.notification("Success", 3000)
	trakt_sync_activities()
	if kodi_utils.path_check("trakt_watchlist") or kodi_utils.external():
		kodi_utils.kodi_refresh()
	return result


def add_to_collection(data):
	result = call_trakt("/sync/collection", data=data)
	if result["existing"]["movies"] + result["existing"]["episodes"] > 0:
		return kodi_utils.notification("Already In List", 3000)
	if result["added"]["movies"] + result["added"]["episodes"] == 0:
		return kodi_utils.notification("Error", 3000)
	kodi_utils.notification("Success", 3000)
	trakt_sync_activities()
	return result


def remove_from_collection(data):
	result = call_trakt("/sync/collection/remove", data=data)
	if result["deleted"]["movies"] + result["deleted"]["episodes"] == 0:
		return kodi_utils.notification("Error", 3000)
	kodi_utils.notification("Success", 3000)
	trakt_sync_activities()
	if kodi_utils.path_check("trakt_collection") or kodi_utils.external():
		kodi_utils.kodi_refresh()
	return result


def hide_unhide_progress_items(params):
	action, media_type, media_id, list_type = params["action"], params["media_type"], params["media_id"], params["section"]
	media_type = "movies" if media_type in ("movie", "movies") else "shows"
	url = "users/hidden/%s" % list_type if action == "drop" else "users/hidden/%s/remove" % list_type
	data = {media_type: [{"ids": {"tmdb": media_id}}]}
	call_trakt(url, data=data)
	trakt_sync_activities()
	kodi_utils.kodi_refresh()


def trakt_search_lists(search_title, page_no):
	def _process(dummy_arg):
		return call_trakt(
			"search",
			params={"type": "list", "fields": "name,description", "query": search_title, "limit": 50},
			with_auth=False,
			pagination=True,
			page_no=page_no,
		)

	string = "trakt_search_lists_%s_%s" % (search_title, page_no)
	return cache_object(_process, string, "dummy_arg", False, 4)


def trakt_favorites(media_type, dummy_arg):
	def _process(params):
		data = get_trakt(params)
		return [
			{
				"media_ids": {
					"tmdb": i[i["type"]]["ids"].get("tmdb", ""),
					"imdb": i[i["type"]]["ids"].get("imdb", ""),
					"tvdb": i[i["type"]]["ids"].get("tvdb", ""),
				}
			}
			for i in data
		]

	media_type = "movies" if media_type in ("movie", "movies") else "shows"
	string = "trakt_favorites_%s" % media_type
	params = {"path": "users/me/favorites/%s/%s", "path_insert": (media_type, "title"), "with_auth": True, "pagination": False}
	return trakt_cache.cache_trakt_object(_process, string, params)


def trakt_lists_with_media(media_type, imdb_id):
	def _process(foo):
		data = get_trakt(params)
		result = [i for i in data if i["item_count"] > 0 and i["ids"]["slug"] not in ("", "None", None) and i["privacy"] == "public"]
		return [kodi_utils.remove_keys(i, media_removals) for i in result]

	media_removals = (
		"description",
		"privacy",
		"type",
		"share_link",
		"display_numbers",
		"allow_comments",
		"sort_by",
		"sort_how",
		"created_at",
		"updated_at",
		"comment_count",
	)
	media_type = "movies" if media_type in ("movie", "movies") else "shows"
	string = "trakt_lists_with_media_%s" % imdb_id
	params = {"path": "%s/%s/lists/personal", "path_insert": (media_type, imdb_id), "params": {"limit": 100}, "pagination": False}
	return cache_object(_process, string, "foo", False, 168)


def get_trakt_list_contents(list_type, user, slug, with_auth, list_id=None, sort_by="default", sort_how="default"):
	if sort_by == "skip":
		skip_sort, custom_sort, method = True, False, None
	else:
		skip_sort = False
		custom_sort = sort_by != "default"
		method = None if custom_sort else "sort_by_headers"
	if list_type == "my_lists":
		string = "trakt_list_contents_%s_%s_%s" % (list_type, user, slug)
		params = {
			"path": "users/%s/lists/%s/items",
			"path_insert": (user, slug),
			"params": {"extended": "full", "limit": 999},
			"method": method,
			"with_auth": with_auth,
		}
	elif list_id is not None:
		string = "trakt_list_contents_%s_%s" % (list_type, list_id)
		params = {"path": "users/%s/lists/%s/items", "path_insert": (user, list_id), "params": {"extended": "full", "limit": 999}, "method": method}
	else:
		string = "trakt_list_contents_%s_%s_%s" % (list_type, user, slug)
		if user == "Trakt Official":
			params = {"path": "lists/%s/items", "path_insert": slug, "params": {"extended": "full", "limit": 999}, "method": method}
		else:
			params = {
				"path": "users/%s/lists/%s/items",
				"path_insert": (user, slug),
				"params": {"extended": "full", "limit": 999},
				"method": method,
				"with_auth": with_auth,
			}
	data = trakt_cache.cache_trakt_object(get_trakt, string, params)
	if not skip_sort:
		if not custom_sort:
			sort_by, sort_how = data["sort_by"], data["sort_how"]
			data = data["data"]
		for i in data:
			if i["type"] == "season":
				i["season"]["title"] = "%s - %s" % (i["show"]["title"], i["season"]["title"])
			elif i["type"] == "episode":
				i["episode"]["title"] = "%s - %s" % (i["show"]["title"], i["episode"]["title"])
			else:
				pass
		data = sort_list(sort_by, sort_how, data, settings.ignore_articles())
	results = []
	results_append = results.append
	for c, i in enumerate(data):
		try:
			_type = i["type"]
			if _type in ("movie", "show"):
				r_key = "released" if _type == "movie" else "first_aired"
				data = {"media_ids": i[_type]["ids"], "title": i[_type]["title"], "type": _type, "order": c, "released": i[_type][r_key], "media_type": _type}
			elif _type == "season":
				data = {"tmdb_id": i["show"]["ids"]["tmdb"], "season": i[_type]["number"], "type": _type, "custom_order": c}
			elif _type == "episode":
				data = {
					"media_ids": i["show"]["ids"],
					"title": i["show"]["title"],
					"type": _type,
					"season": i[_type]["season"],
					"episode": i[_type]["number"],
					"custom_order": c,
				}
			results_append(data)
		except (KeyError, TypeError):
			pass
	return results


def trakt_get_lists(list_type, page_no="1"):
	if list_type in ("trending", "popular"):
		string = "trakt_%s_user_lists_%s" % (list_type, page_no)
		params = {"path": "lists/%s", "path_insert": list_type, "params": {"limit": 50}, "page_no": page_no}
		return cache_object(get_trakt, string, params, False)
	else:
		if list_type == "my_lists":
			string, path = "trakt_my_lists", "users/me/lists%s"
		elif list_type == "liked_lists":
			string, path = "trakt_liked_lists", "users/likes/lists%s"
		params = {"path": path, "params": {"limit": 999}, "pagination": False, "with_auth": True}
		return trakt_cache.cache_trakt_object(get_trakt, string, params)


def get_trakt_list_selection(included_lists):
	def default_lists():
		return [
			{
				"name": "Movies Collection",
				"display": "[B][I]MOVIES COLLECTION [/I][/B]",
				"user": "Collection",
				"slug": "Collection",
				"list_type": "collection",
				"media_type": "movie",
			},
			{
				"name": "TV Show Collection",
				"display": "[B][I]TV SHOW COLLECTION [/I][/B]",
				"user": "Collection",
				"slug": "Collection",
				"list_type": "collection",
				"media_type": "show",
			},
			{
				"name": "Movies Watchlist",
				"display": "[B][I]MOVIES WATCHLIST [/I][/B]",
				"user": "Watchlist",
				"slug": "Watchlist",
				"list_type": "watchlist",
				"media_type": "movie",
			},
			{
				"name": "TV Show Watchlist",
				"display": "[B][I]TV SHOW WATCHLIST [/I][/B]",
				"user": "Watchlist",
				"slug": "Watchlist",
				"list_type": "watchlist",
				"media_type": "show",
			},
		]

	def personal_lists():
		trakt_my_lists = trakt_get_lists("my_lists")
		_lists = [
			{
				"name": item["name"],
				"display": "[B]PERSONAL:[/B] [I]%s[/I]" % item["name"].upper(),
				"user": item["user"]["ids"]["slug"],
				"slug": item["ids"]["slug"],
				"list_type": "my_lists",
				"list_id": item["ids"]["trakt"],
				"item_count": item["item_count"],
			}
			for item in trakt_my_lists
		]
		_lists.sort(key=lambda k: k["name"])
		return _lists

	def liked_lists():
		trakt_liked_lists = trakt_get_lists("liked_lists")
		_lists = [
			{
				"name": item["list"]["name"],
				"display": "[B]LIKED:[/B] [I]%s[/I]" % item["list"]["name"].upper(),
				"user": item["list"]["user"]["ids"]["slug"],
				"slug": item["list"]["ids"]["slug"],
				"list_type": "liked_lists",
				"list_id": item["list"]["ids"]["trakt"],
				"item_count": item["list"]["item_count"],
			}
			for item in trakt_liked_lists
		]
		_lists.sort(key=lambda k: k["display"])
		return _lists

	list_dict = {"default": default_lists, "personal": personal_lists, "liked": liked_lists}
	used_lists = []
	for list_type in included_lists:
		used_lists.extend(list_dict[list_type]())
	list_items = [{"line1": "%s%s" % (item["display"], " [I](x%02d)[/I]" % item["item_count"] if "item_count" in item else "")} for item in used_lists]
	kwargs = {"items": json.dumps(list_items), "heading": "Select", "narrow_window": "true"}
	selection = kodi_utils.select_dialog(used_lists, **kwargs)
	if selection is None:
		return None
	return selection


def make_new_trakt_list(params):
	list_title = kodi_utils.kodi_dialog().input("")
	if not list_title:
		return
	list_name = unquote(list_title)
	data = {"name": list_name, "privacy": "private", "allow_comments": False}
	call_trakt("users/me/lists", data=data)
	trakt_sync_activities()
	kodi_utils.notification("Success", 3000)
	kodi_utils.kodi_refresh()


def delete_trakt_list(params):
	user = params["user"]
	list_slug = params["list_slug"]
	if not kodi_utils.confirm_dialog():
		return
	url = "users/%s/lists/%s" % (user, list_slug)
	call_trakt(url, is_delete=True)
	trakt_sync_activities()
	kodi_utils.notification("Success", 3000)
	kodi_utils.kodi_refresh()


def trakt_like_a_list(params):
	user, list_slug, list_id = params.get("user"), params.get("list_slug"), params.get("list_id")
	refresh = params.get("refresh", "true") == "true"
	try:
		if list_id is not None:
			call_trakt("/lists/%s/like" % list_id, method="post")
		else:
			call_trakt("/users/%s/lists/%s/like" % (user, list_slug), method="post")
		kodi_utils.notification("Success - Trakt List Liked", 3000)
		trakt_sync_activities()
		if refresh:
			kodi_utils.kodi_refresh()
		return True
	except Exception as e:
		kodi_utils.logger("trakt_like_a_list", str(e))
		kodi_utils.notification("Error", 3000)
		return False


def trakt_unlike_a_list(params):
	user, list_slug, list_id = params.get("user"), params.get("list_slug"), params.get("list_id")
	refresh = params.get("refresh", "true") == "true"
	try:
		if list_id is not None:
			call_trakt("/lists/%s/like" % list_id, method="delete")
		else:
			call_trakt("/users/%s/lists/%s/like" % (user, list_slug), method="delete")
		kodi_utils.notification("Success - Trakt List Unliked", 3000)
		trakt_sync_activities()
		if refresh:
			kodi_utils.kodi_refresh()
		return True
	except Exception as e:
		kodi_utils.logger("trakt_unlike_a_list", str(e))
		kodi_utils.notification("Error", 3000)
		return False
