# -*- coding: utf-8 -*-
"""One-tap "Quick Add" context-menu shortcut.

A single context-menu item toggles the current movie/show in/out of **one
pre-configured list target** with no intermediate dialog. The target is stored
as a compact token (see ``encode_target``/``parse_target``); when unset it falls
back to the Trakt watchlist (if Trakt is connected) or the local Forge
favorites. Each supported provider/list is one entry in ``REGISTRY`` — adding a
future integration means adding one descriptor plus its thin adapter fns here.

Kept import-light on purpose: only the token codec and the registry metadata load
at import time (provider modules are imported lazily inside the adapters), so the
pure logic stays unit-testable without a running Kodi.
"""

import importlib
from urllib.parse import quote, unquote

# Static target kinds carry no extra fields; dynamic kinds (personal/custom
# lists) carry the identifiers needed to address one specific list.
STATIC_KINDS = ("trakt_watchlist", "tmdb_watchlist", "tmdb_favorites", "forge_favorites")
_UNSET = (None, "", "empty_setting")


# --------------------------------------------------------------------------- #
# Token codec (pure)
# --------------------------------------------------------------------------- #
def encode_target(kind, **fields):
	if kind in STATIC_KINDS:
		return kind
	if kind == "trakt_list":
		return "trakt_list:%s:%s" % (quote(str(fields["user"]), safe=""), quote(str(fields["slug"]), safe=""))
	if kind == "tmdb_list":
		return "tmdb_list:%s" % quote(str(fields["list_id"]), safe="")
	if kind == "forge_list":
		return "forge_list:%s:%s" % (quote(str(fields["name"]), safe=""), quote(str(fields["author"]), safe=""))
	raise ValueError("unknown quick-add kind: %s" % kind)


def parse_target(token):
	"""Decode a stored token to ``(kind, fields)``; ``(None, {})`` if unset/invalid."""
	if token in _UNSET:
		return (None, {})
	if token in STATIC_KINDS:
		return (token, {})
	head, _, rest = token.partition(":")
	if head == "tmdb_list" and rest:
		return ("tmdb_list", {"list_id": unquote(rest)})
	if head == "trakt_list":
		user, _, slug = rest.partition(":")
		if user and slug:
			return ("trakt_list", {"user": unquote(user), "slug": unquote(slug)})
	if head == "forge_list":
		name, _, author = rest.partition(":")
		if name and author:
			return ("forge_list", {"name": unquote(name), "author": unquote(author)})
	return (None, {})


def resolve_target(token):
	"""Decode ``token``, substituting the fallback target when it's unset/invalid.

	Fallback: Trakt watchlist when Trakt is connected, otherwise the always-local
	Forge favorites. This is the single source of truth for "what does Quick Add
	act on" — both the engine and the context-menu label use it.
	"""
	kind, fields = parse_target(token)
	if kind is None:
		if _resolve("modules.settings.trakt_user_active")():
			return ("trakt_watchlist", {})
		return ("forge_favorites", {})
	return (kind, fields)


# --------------------------------------------------------------------------- #
# Lazy resolution helpers
# --------------------------------------------------------------------------- #
def _resolve(dotted_path):
	module_path, attr = dotted_path.rsplit(".", 1)
	return getattr(importlib.import_module(module_path), attr)


def _notify(message, time=3000):
	from modules import kodi_utils

	return kodi_utils.notification(message, time)


def _provider_name(kind):
	if kind.startswith("trakt"):
		return "Trakt"
	if kind.startswith("tmdb"):
		return "TMDb"
	return "Forge"


# --------------------------------------------------------------------------- #
# Trakt adapters
# --------------------------------------------------------------------------- #
def _trakt_payload(ctx):
	"""Return ``(key, media_key, media_id, data)`` exactly as trakt_manager_choice builds it."""
	if ctx["media_type_raw"] == "movie":
		key, media_key, media_id = "movies", "tmdb", int(ctx["tmdb_id"])
	else:
		key = "shows"
		media_ids = [(ctx["tmdb_id"], "tmdb"), (ctx["imdb_id"], "imdb"), (ctx["tvdb_id"], "tvdb")]
		media_id, media_key = next(item for item in media_ids if item[0] not in ("None", None, ""))
		if media_id in (ctx["tmdb_id"], ctx["tvdb_id"]):
			media_id = int(media_id)
	return key, media_key, media_id, {key: [{"ids": {media_key: media_id}}]}


def _trakt_id_in(items, ctx):
	_, media_key, media_id, _ = _trakt_payload(ctx)
	return any(str(i.get("media_ids", {}).get(media_key)) == str(media_id) for i in items)


def _trakt_watchlist_member(ctx):
	from apis.trakt_api import trakt_fetch_collection_watchlist

	media_type = "movie" if ctx["media_type_raw"] == "movie" else "show"
	return _trakt_id_in(trakt_fetch_collection_watchlist("watchlist", media_type), ctx)


def _trakt_watchlist_add(ctx):
	from apis import trakt_api

	return trakt_api.add_to_watchlist(_trakt_payload(ctx)[3])


def _trakt_watchlist_remove(ctx):
	from apis import trakt_api

	return trakt_api.remove_from_watchlist(_trakt_payload(ctx)[3])


def _trakt_list_member(ctx):
	from apis.trakt_api import get_trakt_list_contents

	fields = ctx["token_fields"]
	items = get_trakt_list_contents("my_lists", fields["user"], fields["slug"], True)
	return _trakt_id_in([i for i in items if i.get("type") in ("movie", "show")], ctx)


def _trakt_list_add(ctx):
	from apis import trakt_api

	fields = ctx["token_fields"]
	return trakt_api.add_to_list(fields["user"], fields["slug"], _trakt_payload(ctx)[3])


def _trakt_list_remove(ctx):
	from apis import trakt_api

	fields = ctx["token_fields"]
	return trakt_api.remove_from_list(fields["user"], fields["slug"], _trakt_payload(ctx)[3])


# --------------------------------------------------------------------------- #
# TMDb adapters
# --------------------------------------------------------------------------- #
def _tmdb_watchfav_member(ctx, list_type):
	from indexers.tmdb_lists import check_item_status_watchfav

	return check_item_status_watchfav(list_type, ctx["media_type"], ctx["tmdb_id"])


def _tmdb_watchfav_set(ctx, list_type, status):
	from caches.tmdb_lists import tmdb_lists_cache
	from indexers.tmdb_lists import add_remove_watchfavs

	success = add_remove_watchfavs(ctx["media_type"], ctx["tmdb_id"], list_type, status)
	tmdb_lists_cache.clear_watchfavrecs(list_type, ctx["media_type"])
	return success


def _tmdb_watchlist_member(ctx):
	return _tmdb_watchfav_member(ctx, "watchlist")


def _tmdb_watchlist_add(ctx):
	return _tmdb_watchfav_set(ctx, "watchlist", True)


def _tmdb_watchlist_remove(ctx):
	return _tmdb_watchfav_set(ctx, "watchlist", False)


def _tmdb_favorites_member(ctx):
	return _tmdb_watchfav_member(ctx, "favorites")


def _tmdb_favorites_add(ctx):
	return _tmdb_watchfav_set(ctx, "favorites", True)


def _tmdb_favorites_remove(ctx):
	return _tmdb_watchfav_set(ctx, "favorites", False)


def _tmdb_list_member(ctx):
	from indexers.tmdb_lists import check_item_status

	return check_item_status(ctx["token_fields"]["list_id"], ctx["media_type"], ctx["tmdb_id"])


def _tmdb_list_set(ctx, add):
	from caches.tmdb_lists import tmdb_lists_cache
	from indexers.tmdb_lists import add_to_tmdb_list, remove_from_tmdb_list

	list_id = ctx["token_fields"]["list_id"]
	items = {"items": [{"media_type": ctx["media_type"], "media_id": ctx["tmdb_id"]}]}
	success = add_to_tmdb_list(list_id, items) if add else remove_from_tmdb_list(list_id, items)
	tmdb_lists_cache.clear_list(list_id)
	tmdb_lists_cache.clear_all_lists()
	return success


def _tmdb_list_add(ctx):
	return _tmdb_list_set(ctx, True)


def _tmdb_list_remove(ctx):
	return _tmdb_list_set(ctx, False)


# --------------------------------------------------------------------------- #
# Forge (local) adapters
# --------------------------------------------------------------------------- #
def _forge_fav_member(ctx):
	from caches.favorites_cache import favorites_cache

	return any(i["tmdb_id"] == str(ctx["tmdb_id"]) for i in favorites_cache.get_favorites(ctx["media_type"]))


def _forge_fav_add(ctx):
	from caches.favorites_cache import favorites_cache

	return favorites_cache.set_favourite(ctx["media_type"], ctx["tmdb_id"], ctx["title"])


def _forge_fav_remove(ctx):
	from caches.favorites_cache import favorites_cache

	return favorites_cache.delete_favourite(ctx["media_type"], ctx["tmdb_id"], ctx["title"])


def _forge_list_member(ctx):
	from caches.personal_lists_cache import personal_lists_cache

	fields = ctx["token_fields"]
	contents = personal_lists_cache.get_list(fields["name"], fields["author"])
	return any(str(i.get("media_id")) == str(ctx["tmdb_id"]) for i in contents)


def _forge_list_add(ctx):
	from caches.personal_lists_cache import personal_lists_cache

	fields = ctx["token_fields"]
	new_contents = {
		"media_id": ctx["tmdb_id"],
		"title": ctx["title"],
		"type": ctx["media_type_raw"],
		"release_date": ctx["premiered"],
		"date_added": ctx["current_time"],
	}
	return personal_lists_cache.add_remove_list_item(fields["name"], fields["author"], "add", new_contents) == "Success"


def _forge_list_remove(ctx):
	from caches.personal_lists_cache import personal_lists_cache

	fields = ctx["token_fields"]
	return personal_lists_cache.add_remove_list_item(fields["name"], fields["author"], "remove", ctx["tmdb_id"]) == "Success"


# --------------------------------------------------------------------------- #
# Membership listings — the full set of tmdb_ids currently in a target, fetched
# once per directory render so the context-menu label can read "Add to" vs
# "Remove from" without an API call per item. Every underlying fetch is cached
# (Trakt object cache / TMDb lists cache) or local (Forge), so this is one
# (usually cached) read per render, not one per item.
# --------------------------------------------------------------------------- #
def _ids_from(items, getter):
	ids = set()
	for item in items or ():
		value = getter(item)
		if value not in (None, "", "None"):
			ids.add(str(value))
	return ids


def _trakt_watchlist_ids(media_type, fields):
	from apis.trakt_api import trakt_fetch_collection_watchlist

	return _ids_from(trakt_fetch_collection_watchlist("watchlist", media_type), lambda i: i.get("media_ids", {}).get("tmdb"))


def _trakt_list_ids(media_type, fields):
	from apis.trakt_api import get_trakt_list_contents

	items = get_trakt_list_contents("my_lists", fields["user"], fields["slug"], True)
	return _ids_from((i for i in items if i.get("type") in ("movie", "show")), lambda i: i.get("media_ids", {}).get("tmdb"))


def _tmdb_watchfav_ids(list_type, media_type):
	from apis.tmdblist_api import tmdb_list_api

	return _ids_from(tmdb_list_api.get_watchfavrecs_list_details(list_type, media_type), lambda i: i.get("id"))


def _tmdb_list_ids(media_type, fields):
	from apis.tmdblist_api import tmdb_list_api

	return _ids_from(tmdb_list_api.get_list_details(fields["list_id"]), lambda i: i.get("id"))


def _forge_fav_ids(media_type, fields):
	from caches.favorites_cache import favorites_cache

	return _ids_from(favorites_cache.get_favorites(media_type), lambda i: i.get("tmdb_id"))


def _forge_list_ids(media_type, fields):
	from caches.personal_lists_cache import personal_lists_cache

	return _ids_from(personal_lists_cache.get_list(fields["name"], fields["author"]), lambda i: i.get("media_id"))


# --------------------------------------------------------------------------- #
# Registry — one descriptor per target kind
# --------------------------------------------------------------------------- #
# media_type maps the raw indexer media_type ("movie"/"tvshow") to the term the
# provider expects. auth is a dotted path to a () -> bool check, or None for
# local targets. notifies marks providers whose add/remove fns already emit their
# own Kodi notification (so the engine doesn't double-notify).
REGISTRY = {
	"trakt_watchlist": {
		"friendly": "Trakt Watchlist",
		"media_type": lambda mt: "movie" if mt == "movie" else "show",
		"auth": "modules.settings.trakt_user_active",
		"is_member": _trakt_watchlist_member,
		"add": _trakt_watchlist_add,
		"remove": _trakt_watchlist_remove,
		"member_ids": _trakt_watchlist_ids,
		"notifies": True,
		"needs": ("tmdb_id", "imdb_id", "tvdb_id"),
	},
	"trakt_list": {
		"friendly": "Trakt List",
		"media_type": lambda mt: "movie" if mt == "movie" else "show",
		"auth": "modules.settings.trakt_user_active",
		"is_member": _trakt_list_member,
		"add": _trakt_list_add,
		"remove": _trakt_list_remove,
		"member_ids": _trakt_list_ids,
		"notifies": True,
		"needs": ("tmdb_id", "imdb_id", "tvdb_id"),
	},
	"tmdb_watchlist": {
		"friendly": "TMDb Watchlist",
		"media_type": lambda mt: "movie" if mt == "movie" else "tv",
		"auth": "modules.settings.tmdblist_user_active",
		"is_member": _tmdb_watchlist_member,
		"add": _tmdb_watchlist_add,
		"remove": _tmdb_watchlist_remove,
		"member_ids": lambda mt, fields: _tmdb_watchfav_ids("watchlist", mt),
		"notifies": False,
		"needs": ("tmdb_id",),
	},
	"tmdb_favorites": {
		"friendly": "TMDb Favorites",
		"media_type": lambda mt: "movie" if mt == "movie" else "tv",
		"auth": "modules.settings.tmdblist_user_active",
		"is_member": _tmdb_favorites_member,
		"add": _tmdb_favorites_add,
		"remove": _tmdb_favorites_remove,
		"member_ids": lambda mt, fields: _tmdb_watchfav_ids("favorites", mt),
		"notifies": False,
		"needs": ("tmdb_id",),
	},
	"tmdb_list": {
		"friendly": "TMDb List",
		"media_type": lambda mt: "movie" if mt == "movie" else "tv",
		"auth": "modules.settings.tmdblist_user_active",
		"is_member": _tmdb_list_member,
		"add": _tmdb_list_add,
		"remove": _tmdb_list_remove,
		"member_ids": _tmdb_list_ids,
		"notifies": False,
		"needs": ("tmdb_id",),
	},
	"forge_favorites": {
		"friendly": "Forge Favorites",
		"media_type": lambda mt: mt,
		"auth": None,
		"is_member": _forge_fav_member,
		"add": _forge_fav_add,
		"remove": _forge_fav_remove,
		"member_ids": _forge_fav_ids,
		"notifies": False,
		"needs": ("tmdb_id", "title"),
	},
	"forge_list": {
		"friendly": "Forge List",
		"media_type": lambda mt: mt,
		"auth": None,
		"is_member": _forge_list_member,
		"add": _forge_list_add,
		"remove": _forge_list_remove,
		"member_ids": _forge_list_ids,
		"notifies": False,
		"needs": ("tmdb_id", "title", "premiered", "current_time"),
	},
}


def target_friendly(token):
	"""Friendly name for the (possibly fallback-resolved) target of ``token``."""
	kind, _ = resolve_target(token)
	return REGISTRY[kind]["friendly"]


def cm_context(media_type_raw):
	"""Resolve the configured target once per directory render.

	Returns ``(name, members)``: ``name`` is the target's display label and
	``members`` is the set of str tmdb_ids currently in that target for this
	media type — which drives the "Add to"/"Remove from" verb. ``members`` is
	``None`` when membership can't be determined (target not authenticated, or
	the listing lookup failed); callers then fall back to the plain "Add to"
	verb. Call this once in the list builder, then ``cm_item_label`` per item.
	"""
	get_setting = _resolve("caches.settings_cache.get_setting")
	token = get_setting("forge.context_menu.quick_add_target", "empty_setting")
	kind, fields = resolve_target(token)
	descriptor = REGISTRY[kind]
	name = get_setting("forge.context_menu.quick_add_target_label", "") or descriptor["friendly"]
	auth = descriptor.get("auth")
	if auth and not _resolve(auth)():
		return name, None
	try:
		members = descriptor["member_ids"](descriptor["media_type"](media_type_raw), fields)
	except Exception:
		members = None
	return name, members


def cm_item_label(name, members, tmdb_id):
	"""Format one item's Quick Add label from the ``(name, members)`` returned by
	``cm_context``. ``members`` of ``None`` is treated as "not a member"."""
	in_list = members is not None and str(tmdb_id) in members
	return "Remove from %s" % name if in_list else "Add to %s" % name


def _refresh_hint(kind, fields):
	return (
		{
			"tmdb_watchlist": "watchlist",
			"tmdb_favorites": "favorites",
			"forge_favorites": "favorites",
		}.get(kind)
		or fields.get("list_id")
		or fields.get("name")
		or ""
	)


# --------------------------------------------------------------------------- #
# Toggle engine
# --------------------------------------------------------------------------- #
def run_toggle(params):
	"""Toggle the item described by ``params`` in/out of the configured target."""
	from modules import kodi_utils

	media_type_raw = params.get("media_type")
	if media_type_raw in ("people", "person"):
		return _notify("Quick Add is not available for people", 3000)
	get_setting = _resolve("caches.settings_cache.get_setting")
	token = get_setting("forge.context_menu.quick_add_target", "empty_setting")
	kind, fields = resolve_target(token)
	descriptor = REGISTRY[kind]
	auth = descriptor.get("auth")
	if auth and not _resolve(auth)():
		return _notify("No Active %s Account" % _provider_name(kind), 3500)
	ctx = {
		"media_type_raw": media_type_raw,
		"media_type": descriptor["media_type"](media_type_raw),
		"tmdb_id": params.get("tmdb_id"),
		"imdb_id": params.get("imdb_id"),
		"tvdb_id": params.get("tvdb_id", "None"),
		"title": params.get("title"),
		"premiered": params.get("premiered"),
		"current_time": params.get("current_time"),
		"token_fields": fields,
	}
	member = descriptor["is_member"](ctx)
	success = descriptor["remove"](ctx) if member else descriptor["add"](ctx)
	if descriptor.get("notifies"):
		# Trakt's own add/remove fns notify and refresh — nothing more to do.
		return
	# Prefer the friendly name captured when the target was picked (e.g. a TMDb list's
	# name rather than its numeric id); fall back to the kind's generic label.
	label = get_setting("forge.context_menu.quick_add_target_label", "")
	display = label or (target_friendly(token) if kind in STATIC_KINDS else descriptor["friendly"])
	if success:
		_notify("%s %s" % ("Removed from" if member else "Added to", display), 3000)
	else:
		_notify("Quick Add Failed", 3000)
	if success and member:
		hint = _refresh_hint(kind, fields)
		kodi_utils.refresh_after_action(hint or None)
