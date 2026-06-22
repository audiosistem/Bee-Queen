# -*- coding: utf-8 -*-
"""Static lookup data for menus, filters, and discover-style screens.

The bulk of the data lives in `resources/data/*.json` — see that directory for
the canonical schemas. This module is a thin loader: each public function
returns the parsed JSON for its dataset, cached after first load.

The year/decade helpers are computed (they depend on `datetime.now()`) so they
stay in code. `list_display_choices(list_type)` also stays since it dispatches
on its argument.
"""

import json
import os

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
_cache = {}


def _load(name):
	if name not in _cache:
		with open(os.path.join(_DATA_DIR, "%s.json" % name), encoding="utf-8") as f:
			_cache[name] = json.load(f)
	return _cache[name]


def get_years(start_year):
	from datetime import datetime

	current_year = datetime.now().year
	return [{"name": str(year), "id": year} for year in range(current_year, start_year - 1, -1)]


def get_decades(start_decade):
	from datetime import datetime

	current_year = datetime.now().year
	current_decade = (current_year // 10) * 10
	return [{"name": "%ss" % decade, "id": decade} for decade in range(current_decade, start_decade - 1, -10)]


def years_movies():
	return get_years(1900)


def years_tvshows():
	return get_years(1944)


def years_anime():
	return get_years(1961)


def decades_movies():
	return get_decades(1900)


def decades_tvshows():
	return get_decades(1940)


def decades_anime():
	return get_decades(1960)


def oscar_winners():
	return _load("oscar_winners")


def movie_certifications():
	return _load("certifications")["movie"]


def tvshow_certifications():
	return _load("certifications")["tvshow"]


def languages():
	return _load("languages")


def language_choices():
	return _load("language_choices")


def regions():
	return _load("regions")


def movie_genres():
	return _load("genres")["movie"]


def tvshow_genres():
	return _load("genres")["tvshow"]


def anime_genres():
	return _load("genres")["anime"]


def mixed_genres():
	return _load("genres")["mixed"]


def networks():
	return _load("networks")


# Trailing per-storefront suffixes TMDb appends to a brand's channel listings (e.g. "Starz Apple TV
# Channel"). Stripped when folding variants together so the brand collapses to one menu entry.
_STOREFRONT_SUFFIXES = (" amazon channel", " apple tv channel", " roku premium channel")

# Cross-name brands the suffix rule can't unify on its own. TMDb lists MHz Choice's Amazon storefront
# under a "MZ Choice" typo (id 291), separate from the base "Mhz Choice" (id 427); fold them together.
_BRAND_ALIASES = {"mzchoice": "mhzchoice"}

# Display names for brand keys whose auto-picked label isn't ideal (data uses "MGM Plus", "AcornTV
# Amazon Channel", "Mhz Choice"). Cosmetic only — keyed by the normalized brand key.
_BRAND_DISPLAY = {"mgm+": "MGM+", "acorntv": "Acorn TV", "mhzchoice": "MHz Choice"}


def _strip_storefront(name):
	# (stem, had_suffix) — the brand name with a trailing storefront-channel suffix removed.
	stem = name.strip()
	low = stem.lower()
	for suffix in _STOREFRONT_SUFFIXES:
		if low.endswith(suffix):
			return stem[: len(stem) - len(suffix)].strip(), True
	return stem, False


def _brand_key(name):
	# Matching key: drop a storefront suffix, lowercase, unify a spelled-out "Plus" token with "+",
	# strip spaces, then alias. The "plus"→"+" swap is token-bounded (not a substring replace) so a
	# brand whose name merely contains the letters "plus" (e.g. a hypothetical "Surplus TV") isn't
	# mangled into a different brand's key and wrongly folded with it.
	stem = _strip_storefront(name)[0]
	key = "".join("+" if tok == "plus" else tok for tok in stem.lower().split())
	return _BRAND_ALIASES.get(key, key)


def _join_ids(ids):
	# Wire form for a brand's member ids: a plain int for a singleton, else a pipe-joined string the
	# TMDb `with_watch_providers` query ORs (and the menu handler splits back on "|").
	return ids[0] if len(ids) == 1 else "|".join(str(x) for x in ids)


def _brand_groups(rows):
	# Ordered list of (brand_key, group) folding per-storefront channel variants of one streaming brand
	# (e.g. "Starz", "Starz Apple TV Channel", "Starz Roku Premium Channel") into a single group whose
	# `ids` lists every member id (base first) and `id` pipe-joins them, so the TMDb `with_watch_providers`
	# query ORs them and no content is missed. First-seen order is preserved; name/logo come from the
	# brand's base row (one with no storefront suffix) when present, else the cleaned stem of the first
	# variant — so a brand that exists only as a storefront channel is renamed (e.g. "Hallmark+"), never
	# dropped. Shared by the Movie/TV menus and the Mixed Providers intersection.
	groups = {}  # key -> {"order": int, "members": [(id, stem, logo, had_suffix)]}
	for i, row in enumerate(rows):
		stem, had_suffix = _strip_storefront(row["name"])
		g = groups.setdefault(_brand_key(row["name"]), {"order": i, "members": []})
		g["members"].append((row["id"], stem, row.get("logo"), had_suffix))
	out = []
	for key, g in sorted(groups.items(), key=lambda kv: kv[1]["order"]):
		members = g["members"]
		base = next((m for m in members if not m[3]), None)  # base = a row with no storefront suffix
		ordered = [base] + [m for m in members if m is not base] if base else members
		ids = [m[0] for m in ordered]
		out.append(
			(
				key,
				{
					"ids": ids,  # raw member ids, base first — for the Mixed Providers union/icon lookup
					"id": _join_ids(ids),
					"name": _BRAND_DISPLAY.get(key) or (base[1] if base else ordered[0][1]),
					"logo": next((m[2] for m in ordered if m[2]), None),
				},
			)
		)
	return out


def _collapse_variants(rows):
	# Public-menu shape: the folded brands as {id, name, logo} (drops the internal raw-ids list).
	return [{"id": g["id"], "name": g["name"], "logo": g["logo"]} for _, g in _brand_groups(rows)]


def watch_providers_movies():
	return _collapse_variants(_load("watch_providers")["movie"])


def watch_providers_tvshows():
	return _collapse_variants(_load("watch_providers")["tvshow"])


# Mixed-list providers that should render with a crisp local icon instead of TMDb's small h100 logo.
# Keyed by watch-provider id → the matching network name in networks.json: the icon resolves from the
# same PNG the TV Networks / Mixed Channels menus use, so a future art re-cut in networks.json carries
# over automatically with no hash to keep in sync here. Several ids intentionally share a network
# (Netflix Kids reuses Netflix, AMC+ reuses AMC, FXNow reuses FX).
_MIXED_ICON_NETWORK = {
	337: "Disney+",
	8: "Netflix",
	175: "Netflix",
	9: "Amazon",  # Amazon Prime Video; id 10 "Amazon Video" keeps its TMDb logo so the two differ
	350: "Apple TV +",
	15: "Hulu",
	386: "Peacock",
	2303: "Paramount+",
	43: "Starz",
	526: "AMC",
	80: "AMC",
	79: "NBC",
	83: "The CW",
	209: "PBS",
	123: "FX",
	211: "Freeform",
	156: "A&E",
	157: "Lifetime",
	87: "Acorn TV",
	584: "Discovery+",
}

# The two Mixed-list brands with no networks.json entry carry an explicit network_icons basename,
# mirroring the per-brand `icon` override in mixed_brands.json.
_MIXED_ICON_FILE = {
	34: "mgm_plus_logo",  # MGM Plus
	283: "crunchyroll_logo",  # Crunchyroll
}


def _mixed_icon(ids, net_logos):
	# Crisp local network_icons basename for a Mixed-list brand, or None to fall back to its TMDb logo.
	# Scans every member id (base first) so an icon mapped to a storefront-only variant still attaches
	# even when the brand's base id isn't itself in the maps. Network-backed brands resolve through
	# networks.json (by name); the rest use an explicit file.
	for provider_id in ids:
		network = _MIXED_ICON_NETWORK.get(provider_id)
		if network:
			return net_logos.get(network)
		if provider_id in _MIXED_ICON_FILE:
			return _MIXED_ICON_FILE[provider_id]
	return None


def watch_providers_mixed():
	# Brands with content on both movies and TV, folded the same way as the Movie/TV menus: storefront
	# variants collapse into one row whose `id` pipe-joins every movie+TV member id, so clicking it ORs
	# them in the TMDb query (`mixed_providers` fires the same tmdb_*_providers calls) instead of hitting
	# only the base provider and missing variant content. The brand intersection avoids dead buckets where
	# a brand has no movies or no TV; a crisp local `icon` is attached by base id where one exists (None
	# otherwise); the list is sorted alphabetically — which keeps Netflix beside Netflix Kids.
	net_logos = {n["name"]: n.get("logo") for n in _load("networks")}
	movie = dict(_brand_groups(_load("watch_providers")["movie"]))
	tv = dict(_brand_groups(_load("watch_providers")["tvshow"]))
	rows = []
	for key, m in movie.items():
		if key not in tv:
			continue
		ids = m["ids"] + [i for i in tv[key]["ids"] if i not in m["ids"]]  # union, movie/base first
		rows.append(
			{
				"id": _join_ids(ids),
				"name": m["name"],
				"logo": m["logo"] or tv[key]["logo"],
				"icon": _mixed_icon(ids, net_logos),
			}
		)
	rows.sort(key=lambda p: p["name"].strip().lower())
	return rows


def mixed_brands():
	# Curated streaming "brands" for the Mixed Channels list. Each entry pipe-joins TMDb
	# watch-provider ids (movies + TV streamable) and network ids (TV originals); the list
	# handler ORs them per axis.
	#
	# Icon sources, best-quality first (the menu picks the first that resolves):
	#   icon         - optional explicit local network_icons filename in mixed_brands.json, for
	#                  brands with no TMDb network entry (e.g. Crunchyroll, MGM+).
	#   network_logo - the local crisp PNG hash from networks.json (rendered via
	#                  get_icon(..., "network_icons")), matched on the brand's first network id.
	#   logo         - the TMDb watch-provider image path, matched on the first provider id that
	#                  has one (movie preferred over TV). A brand's canonical base provider id may
	#                  be absent from Forge's data subset while a channel-variant id still has a logo.
	# All are None/absent when nothing resolves; the menu then falls back to a generic icon.
	wp = _load("watch_providers")
	logos = {}
	for arr in (wp["movie"], wp["tvshow"]):
		for p in arr:
			logos.setdefault(str(p["id"]), p.get("logo"))
	net_logos = {str(n["id"]): n.get("logo") for n in _load("networks")}
	out = []
	for b in _load("mixed_brands"):
		providers = b.get("providers", "")
		networks = b.get("networks", "")
		logo = next((logos[t] for t in providers.split("|") if logos.get(t)), None)
		network_logo = next((net_logos[t] for t in networks.split("|") if net_logos.get(t)), None)
		out.append({"name": b["name"], "providers": providers, "networks": networks, "icon": b.get("icon"), "logo": logo, "network_logo": network_logo})
	return out


def movie_sorts():
	return _load("sorts")["movie"]


def tvshow_sorts():
	return _load("sorts")["tvshow"]


def discover_items():
	return _load("discover_items")


def color_palette():
	return _load("color_palette")


def list_display_choices(list_type):
	return {
		"tmdb": {
			"choices": [
				("Title", "0"),
				("Date Created (asc)", "1"),
				("Date Created (desc)", "2"),
				("Recently Updated (asc)", "3"),
				("Recently Updated (desc)", "4"),
				("Item Count (asc)", "5"),
				("Item Count (desc)", "6"),
				("Average Rating (asc)", "7"),
				("Average Rating (desc)", "8"),
				("Total Runtime (asc)", "9"),
				("Total Runtime (desc)", "10"),
				("Total Revenue (asc)", "11"),
				("Total Revenue (desc)", "12"),
			],
			"setting": "tmdblist",
		},
		"personal": {
			"choices": [
				("Title", "0"),
				("Author", "1"),
				("Date Created (asc)", "2"),
				("Date Created (desc)", "3"),
				("Recently Updated (asc)", "4"),
				("Recently Updated (desc)", "5"),
				("Item Count (asc)", "6"),
				("Item Count (desc)", "7"),
			],
			"setting": "personal_list",
		},
	}[list_type]
