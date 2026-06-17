# -*- coding: utf-8 -*-
"""Shared helpers for the Mixed menu surfaces.

Kept Kodi-free so the test suite can import it directly.
"""

from itertools import zip_longest


def interleave_buckets(*buckets):
	"""Round-robin merge two or more buckets, dropping `None` placeholders.

	Bucket 0 contributes first within each round, then bucket 1, etc. Empty
	buckets are tolerated transparently — passing an empty anime bucket yields
	the plain `[M, S, M, S, ...]` pattern used when the anime setting is off.
	"""
	out = []
	for tup in zip_longest(*buckets):
		for item in tup:
			if item is not None:
				out.append(item)
	return out


def dedupe_by_id(items):
	"""Drop repeated TMDb result dicts by their ``id``, preserving first-seen order.

	Used by the Mixed Channels TV bucket, which unions two separate /discover/tv
	queries (network originals + streamable providers) — TMDb ANDs different
	filter params, so an OR across the two axes means merging two responses and
	removing the titles that appear in both. Items with no ``id`` are skipped.
	"""
	seen, out = set(), []
	for it in items:
		i = it.get("id")
		if i is None or i in seen:
			continue
		seen.add(i)
		out.append(it)
	return out


MIXED_LIST_SOURCES = {
	"trakt_trending": {
		"api": "trakt",
		"movie": ("apis.trakt_api", "trakt_movies_trending"),
		"tv": ("apis.trakt_api", "trakt_tv_trending"),
		"anime": ("apis.trakt_api", "trakt_anime_trending"),
	},
	"trakt_trending_recent": {
		"api": "trakt",
		"movie": ("apis.trakt_api", "trakt_movies_trending_recent"),
		"tv": ("apis.trakt_api", "trakt_tv_trending_recent"),
		"anime": ("apis.trakt_api", "trakt_anime_trending_recent"),
	},
	"trakt_most_watched": {
		"api": "trakt",
		"movie": ("apis.trakt_api", "trakt_movies_most_watched"),
		"tv": ("apis.trakt_api", "trakt_tv_most_watched"),
		"anime": ("apis.trakt_api", "trakt_anime_most_watched"),
	},
	"trakt_most_favorited": {
		"api": "trakt",
		"movie": ("apis.trakt_api", "trakt_movies_most_favorited"),
		"tv": ("apis.trakt_api", "trakt_tv_most_favorited"),
		"anime": ("apis.trakt_api", "trakt_anime_most_favorited"),
	},
	"tmdb_popular": {
		"api": "tmdb",
		"movie": ("apis.tmdb_api", "tmdb_movies_popular"),
		"tv": ("apis.tmdb_api", "tmdb_tv_popular"),
		"anime": ("apis.tmdb_api", "tmdb_anime_popular"),
	},
	"tmdb_popular_today": {
		"api": "tmdb",
		"movie": ("apis.tmdb_api", "tmdb_movies_popular_today"),
		"tv": ("apis.tmdb_api", "tmdb_tv_popular_today"),
		# TMDb's anime side ships popular_recent, not popular_today — closest existing pair.
		"anime": ("apis.tmdb_api", "tmdb_anime_popular_recent"),
	},
	"tmdb_premieres": {
		"api": "tmdb",
		"movie": ("apis.tmdb_api", "tmdb_movies_premieres"),
		"tv": ("apis.tmdb_api", "tmdb_tv_premieres"),
		"anime": ("apis.tmdb_api", "tmdb_anime_premieres"),
	},
	"tmdb_upcoming": {
		"api": "tmdb",
		"movie": ("apis.tmdb_api", "tmdb_movies_upcoming"),
		"tv": ("apis.tmdb_api", "tmdb_tv_upcoming"),
		"anime": ("apis.tmdb_api", "tmdb_anime_upcoming"),
	},
}


# Keyed sources for Navigator.mixed_keyed_list — the functions take (key_id, page_no).
# Used by Mixed Genres (movie/tv genre ids differ) and Mixed Providers (shared id).
# TMDb-only, so no "api" discriminator is needed.
MIXED_KEYED_SOURCES = {
	"mixed_genres": {
		"movie": ("apis.tmdb_api", "tmdb_movies_genres"),
		"tv": ("apis.tmdb_api", "tmdb_tv_genres"),
		"anime": ("apis.tmdb_api", "tmdb_anime_genres"),
	},
	"mixed_providers": {
		"movie": ("apis.tmdb_api", "tmdb_movies_providers"),
		"tv": ("apis.tmdb_api", "tmdb_tv_providers"),
		"anime": ("apis.tmdb_api", "tmdb_anime_providers"),
	},
}


MIXED_LIST_MENU = (
	("Mixed Trending", "trakt_trending", "trending"),
	("Mixed Trending Recent", "trakt_trending_recent", "trending"),
	("Mixed Most Watched", "trakt_most_watched", "most_watched"),
	("Mixed Most Favorited", "trakt_most_favorited", "favorites"),
	("Mixed Popular", "tmdb_popular", "popular"),
	("Mixed Popular Today", "tmdb_popular_today", "popular_today"),
	("Mixed Premieres", "tmdb_premieres", "fresh"),
	("Mixed Upcoming", "tmdb_upcoming", "lists"),
)


def trakt_ids(item, list_key):
	"""Extract the canonical Trakt id dict from a list response item.

	Trakt list endpoints wrap entries as ``{"movie": {"ids": {...}}}`` or
	``{"show": {"ids": {...}}}``; some endpoints return the ids dict at the
	top level. This collapses both shapes.
	"""
	try:
		return item[list_key]["ids"]
	except (KeyError, TypeError):
		return item.get("ids")
