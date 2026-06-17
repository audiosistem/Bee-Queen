# -*- coding: utf-8 -*-
"""IMDB / TVDB / TMDB → MAL id mapping for AniSkip.

AniSkip is keyed on MAL ids, but Forge only ever holds TMDB/TVDB/IMDB ids at
play time. Fribb's ``anime-lists`` project publishes a single JSON that maps all
of those id spaces to MAL; we fetch it once, reduce it to a minimal lookup index,
and cache the **parsed index** long-term so the multi-MB file is never re-fetched
or re-parsed on the playback path (Risk #9).

Each source entry looks like (verified live)::

    {"mal_id": 290, "imdb_id": "tt0286390", "tvdb_id": 72025,
     "themoviedb_id": {"tv": 26209}, "season": {"tvdb": 1, "tmdb": 1}, ...}

so the file carries per-entry season numbers — that lets us key the TMDB/TVDB
indices on ``(id, season)`` and resolve a specific cours rather than guessing
(MAL splits long shows into per-season entries; Risk #4).

Resolution order is **tmdb+season → tvdb+season → imdb (season 1 only)**: Forge's
episode season/episode numbers come from TMDB, so ``themoviedb_id.tv`` +
``season.tmdb`` is the most internally-consistent key, and both season-aware
lookups are tried before the season-blind imdb one. (The original plan said
tvdb-first, written before the file was known to carry ``season.tmdb``.)

Thin HTTP + pure index-building only; no UI logic.
"""

import requests
from apis._http import TIMEOUT_LONG
from caches.main_cache import main_cache
from modules.kodi_utils import make_session

# from modules.kodi_utils import logger

session = make_session("https://raw.githubusercontent.com")

_SOURCE_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
_CACHE_KEY = "anime_id_map"
_CACHE_TTL_HOURS = 168  # weekly; mappings change rarely and the file is heavy.
_FAIL_TTL_HOURS = 3  # negative cache: don't re-pull the multi-MB file every play during an outage.


def get_mal_id(tmdb_id=None, tvdb_id=None, imdb_id=None, season=1):
	"""Resolve a MAL id from the ids Forge holds, or ``None`` if unmapped.

	Tries the two **season-aware** keys first — ``tmdb_id``+season, then
	``tvdb_id``+season — since MAL splits a show into per-cours entries and only a
	season-keyed match lands on the right cours. ``imdb_id`` is consulted **last and
	only for season 1**: the source isn't imdb-season-keyed and Forge holds the
	*series-level* imdb (which Fribb attaches to the first cours), so trusting it for
	a later season would return the wrong cours' MAL id and mistime the skip buttons.

	Returns ``None`` (never raises) when the mapping file can't be fetched/parsed so
	the resolver cleanly falls back to IntroDB.
	"""
	try:
		index = _get_index()
		if not index:
			return None
		season_key = _season_key(season)
		if tmdb_id:
			mal = index["tmdb"].get("%s_%s" % (tmdb_id, season_key))
			if mal:
				return mal
		if tvdb_id:
			mal = index["tvdb"].get("%s_%s" % (tvdb_id, season_key))
			if mal:
				return mal
		if imdb_id and season_key == "1":
			mal = index["imdb"].get(imdb_id)
			if mal:
				return mal
		return None
	except Exception:
		return None


def _get_index():
	"""Return the cached parsed index, fetching + building (and caching) on a miss.

	A failed fetch is negatively cached (an empty ``{}`` under a short TTL) so an
	outage doesn't re-download the multi-MB file on every anime play (Risk #9). A
	real fetch always yields a non-empty index, so a falsy cached value is
	unambiguously the negative-cache sentinel → treat it as "unmapped".
	"""
	cached = main_cache.get(_CACHE_KEY)
	if cached is not None:
		return cached or None
	payload = _fetch()
	if payload is None:
		main_cache.set(_CACHE_KEY, {}, expiration=_FAIL_TTL_HOURS)
		return None
	index = build_index(payload)
	main_cache.set(_CACHE_KEY, index, expiration=_CACHE_TTL_HOURS)
	return index


def _fetch():
	try:
		response = session.get(_SOURCE_URL, timeout=TIMEOUT_LONG)
		if response.status_code != 200:
			return None
		return response.json()
	except requests.RequestException:
		return None
	except ValueError:
		return None


def build_index(entries):
	"""Pure, unit-testable: reduce Fribb's full list to ``{"tmdb": {...}, "tvdb":
	{...}, "imdb": {...}}`` lookup dicts.

	TMDB/TVDB keys are ``"<id>_<season>"`` (season-aware); IMDB is a plain
	``imdb_id`` (the file gives no reliable per-imdb season basis). ``setdefault``
	keeps the **first** entry for a colliding key — a deterministic choice for the
	rare ambiguous case (e.g. multiple MAL cours sharing one imdb_id).
	"""
	tmdb_idx, tvdb_idx, imdb_idx = {}, {}, {}
	for entry in entries or []:
		mal_id = entry.get("mal_id")
		if not mal_id:
			continue
		season = entry.get("season") if isinstance(entry.get("season"), dict) else {}
		tmdb_tv = _tmdb_tv_id(entry.get("themoviedb_id"))
		if tmdb_tv:
			tmdb_idx.setdefault("%s_%s" % (tmdb_tv, _season_key(season.get("tmdb"))), mal_id)
		tvdb_id = entry.get("tvdb_id")
		if isinstance(tvdb_id, int):
			tvdb_idx.setdefault("%s_%s" % (tvdb_id, _season_key(season.get("tvdb"))), mal_id)
		imdb_id = entry.get("imdb_id")
		if imdb_id:
			imdb_idx.setdefault(imdb_id, mal_id)
	return {"tmdb": tmdb_idx, "tvdb": tvdb_idx, "imdb": imdb_idx}


def _tmdb_tv_id(themoviedb_id):
	"""``themoviedb_id`` is ``{"tv": id}`` / ``{"movie": id}`` (or occasionally a
	bare int / list). Pull the TV id; ``None`` for movie-only or missing."""
	if isinstance(themoviedb_id, dict):
		return themoviedb_id.get("tv")
	if isinstance(themoviedb_id, int):
		return themoviedb_id
	return None


def _season_key(value):
	"""Normalize a season value (int, ``"a"`` absolute, ``None``) to a string so
	build-time keys and lookup keys compare consistently. Missing → ``"1"``."""
	if value in (None, ""):
		return "1"
	return str(value)
