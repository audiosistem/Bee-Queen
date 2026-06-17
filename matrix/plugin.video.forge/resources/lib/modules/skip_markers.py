# -*- coding: utf-8 -*-
"""Skip-marker resolver: turn a playing episode's metadata into a small list of
normalized intro/recap/outro segments the player can offer to skip.

Data path: for anime episodes, AniSkip (richer op/ed/recap coverage, keyed on a
MAL id resolved from Forge's TMDB/TVDB/IMDB ids) is tried first; everything else
(and any anime miss) falls through to IntroDB (crowd-sourced, no API key) with an
opt-in Kodi chapter fallback. IntroDB is consumed read-only (no submit-back).

Design notes:
- ``active_segment`` is the hot path — the player's once-per-second monitor loop
  calls it every tick, so it does no I/O and imports nothing.
- ``resolve_segments`` runs once per playback on a background thread; it owns the
  network + cache work.
- Anything that touches Kodi (the Player chapter read) is imported lazily so the
  module stays importable off-device for unit tests.

Normalized segment shape (shared with the API clients and the player)::

    {"type": "intro"|"recap"|"outro", "start": float_sec, "end": float_sec,
     "source": "introdb"|"chapter"|"aniskip", "confidence": float, "submission_count": int}
"""

from apis import introdb_api
from caches.intro_outro_cache import intro_outro_cache
from modules import settings as st
from modules.kodi_utils import logger

# Misses get a short TTL so freshly-submitted crowd data surfaces within a day;
# hits get a long TTL since corrections are rare.
_HIT_TTL_HOURS = 168
_MISS_TTL_HOURS = 24


def resolve_segments(meta, episode_length=None):
	"""Resolve skip segments for ``meta`` (episodes only).

	cache → [AniSkip for anime] → IntroDB → parse → optional chapter fallback →
	cache the *raw* normalized list → threshold + enabled-type filter at read.
	Returns a possibly-empty list and never raises (it runs on a playback-adjacent
	thread).

	The cache stores the **pre-threshold, pre-type-filter** list so the quality
	gate (Min Confidence / Min Submissions) and the intro/recap/outro toggles are
	applied fresh on every read — tuning a setting takes effect immediately instead
	of waiting out the 24h/168h TTL. The filter step is cheap (O(n) over ≤6 dicts).

	``episode_length`` is the player's ``getTotalTime()`` in seconds when known;
	AniSkip uses it to scale its stored intervals (Risk #6). It is unused by the
	IntroDB/chapter paths.
	"""
	try:
		if meta.get("media_type") != "episode":
			return []
		imdb_id, season, episode = meta.get("imdb_id"), meta.get("season"), meta.get("episode")
		if not imdb_id or season in (None, "") or episode in (None, ""):
			return []
		key = "%s_%s_%s" % (imdb_id, season, episode)
		cached = intro_outro_cache.get(key)
		if cached is not None:
			return _filter_enabled(apply_threshold(cached))
		raw, responded = [], False
		# Anime: prefer AniSkip's op/ed/recap data; fall through to IntroDB on a miss.
		if st.skip_markers_aniskip_enabled() and is_anime(meta):
			aniskip_segments = _resolve_aniskip(meta, episode_length)
			if aniskip_segments:
				raw = aniskip_segments
				responded = True
		if not raw:
			payload = introdb_api.get_segments(imdb_id, season, episode)
			responded = responded or payload is not None
			if payload is not None:
				raw = introdb_api.parse_segments(payload)
		if not raw and st.skip_markers_use_chapters():
			raw = chapter_fallback(meta)
		# Cache a *definitive* result only: a source answered (a covered show, possibly
		# an empty "miss" worth a short-TTL cache) or chapters produced candidates. A
		# transient network failure (no source responded) with no chapter data is left
		# uncached so the next play retries instead of going dark for the miss TTL.
		if responded or raw:
			intro_outro_cache.set(key, raw, expiration=_HIT_TTL_HOURS if raw else _MISS_TTL_HOURS)
			logger("Forge.skip_markers", "%s: %s raw segment(s) (responded=%s)" % (key, len(raw), responded))
		return _filter_enabled(apply_threshold(raw))
	except Exception as error:
		logger("Forge.skip_markers", "resolve_segments failed: %s" % error)
		return []


def is_anime(meta):
	"""True when ``meta`` is an anime title, reusing Forge's canonical test
	(``metadata.is_anime_check`` — the TMDB keyword ``210024``). Prefers the
	keywords already on ``meta``; otherwise looks the show up by ``tmdb_id`` in the
	meta cache. Imported lazily so this module stays importable off-device."""
	try:
		from modules.metadata import is_anime_check

		if meta.get("keywords"):
			return is_anime_check(meta)
		return is_anime_check(tmdb_id=meta.get("tmdb_id"))
	except Exception as error:
		logger("Forge.skip_markers", "is_anime failed: %s" % error)
		return False


def _resolve_aniskip(meta, episode_length):
	"""Map Forge's ids → MAL id, then fetch + normalize AniSkip skip times. Returns
	``[]`` (never raises) when the title isn't mapped or AniSkip has no coverage, so
	the caller cleanly falls through to IntroDB. AniSkip scales its intervals to the
	episode length, so prefer the real runtime over the (often rounded) meta
	duration (Risk #6)."""
	try:
		from apis import anime_mapping_api, aniskip_api

		mal_id = anime_mapping_api.get_mal_id(
			tmdb_id=meta.get("tmdb_id"),
			tvdb_id=meta.get("tvdb_id"),
			imdb_id=meta.get("imdb_id"),
			season=meta.get("season"),
		)
		if not mal_id:
			return []
		length = episode_length or _to_float(meta.get("duration")) or 0
		payload = aniskip_api.get_skip_times(mal_id, meta.get("episode"), length)
		return aniskip_api.parse_skip_times(payload)
	except Exception as error:
		logger("Forge.skip_markers", "_resolve_aniskip failed: %s" % error)
		return []


def apply_threshold(segments):
	"""Keep a crowd-sourced segment if it clears *either* gate — enough
	submissions **or** high enough confidence (both user-configurable).

	With the default ``min_submissions=1`` every real IntroDB entry passes
	(max coverage, the confirmed product decision); raising it makes the
	confidence gate the escape hatch for sparsely-submitted-but-trusted markers.

	The gate applies **only to IntroDB**. AniSkip (authored op/ed timings) and
	chapter-derived candidates have no crowd confidence/submission metrics, so
	gating on their zeroed values would wrongly drop every one — they are exempt.
	(This matters because all sources now share the cached raw list and pass
	through this step together, rather than chapters being appended afterwards.)
	"""
	min_submissions = st.skip_markers_min_submissions()
	min_confidence = st.skip_markers_min_confidence()
	return [s for s in segments if s.get("source") != "introdb" or s.get("submission_count", 0) >= min_submissions or s.get("confidence", 0) >= min_confidence]


def active_segment(segments, curr_time):
	"""Hot path: return the segment containing ``curr_time`` (start inclusive,
	end exclusive), else ``None``. O(n) over a tiny list, no I/O, no imports."""
	for seg in segments:
		if seg["start"] <= curr_time < seg["end"]:
			return seg
	return None


def chapter_fallback(meta):
	"""Opt-in, deliberately conservative chapter-derived candidates (Risk #2).

	Only runs when IntroDB returned nothing. Kodi exposes chapter *positions* as a
	CSV of playback percentages (not names), so we can only heuristically map
	boundaries to segments: a short early chapter → intro candidate, the final
	credits boundary → outro candidate. Both honour the per-type toggles. Returns
	``[]`` when there's no usable chapter data or no duration to convert
	percentages to seconds.
	"""
	try:
		from modules import kodi_utils as ku

		duration = _to_float(meta.get("duration"))
		if not duration:
			return []
		chapters_csv = ku.get_infolabel("Player.Chapters")
		return _chapter_candidates(chapters_csv, duration, st.skip_markers_types())
	except Exception as error:
		logger("Forge.skip_markers", "chapter_fallback failed: %s" % error)
		return []


def _chapter_candidates(chapters_csv, duration, enabled_types):
	"""Pure: derive conservative intro/outro candidates from a Player.Chapters CSV
	of percentages and the runtime in seconds. Factored out for unit testing."""
	pcts = _chapter_percentages(chapters_csv)
	if len(pcts) < 2:
		return []
	candidates = []
	# Intro: a standalone early chapter — first internal boundary within the first quarter.
	if "intro" in enabled_types:
		early = [p for p in pcts if 0 < p <= 25]
		if early:
			candidates.append(_chapter_segment("intro", 0.0, early[0], duration))
	# Outro: the last chapter boundary in the credits window marks where credits start.
	if "outro" in enabled_types:
		credits = [p for p in pcts if 70 <= p < 100]
		if credits:
			candidates.append(_chapter_segment("outro", credits[-1], 100.0, duration))
	return candidates


def _chapter_percentages(chapters_csv):
	if not chapters_csv:
		return []
	values = []
	for part in chapters_csv.split(","):
		val = _to_float(part.strip())
		if val is not None:
			values.append(val)
	return values


def _chapter_segment(seg_type, start_pct, end_pct, duration):
	return {
		"type": seg_type,
		"start": round(duration * start_pct / 100.0, 1),
		"end": round(duration * end_pct / 100.0, 1),
		"source": "chapter",
		"confidence": 0.0,
		"submission_count": 0,
	}


def _filter_enabled(segments):
	enabled = st.skip_markers_types()
	return [s for s in segments if s["type"] in enabled]


def _to_float(value):
	try:
		return float(value)
	except (TypeError, ValueError):
		return None
