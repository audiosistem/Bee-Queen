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


def watch_providers_movies():
	return _load("watch_providers")["movie"]


def watch_providers_tvshows():
	return _load("watch_providers")["tvshow"]


def watch_providers_mixed():
	# Providers common to both movies and TV (ids are identical across types), in movie order.
	# Restricting to the intersection avoids dead buckets where a provider has no movies or no TV.
	data = _load("watch_providers")
	tv_ids = {p["id"] for p in data["tvshow"]}
	return [p for p in data["movie"] if p["id"] in tv_ids]


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
