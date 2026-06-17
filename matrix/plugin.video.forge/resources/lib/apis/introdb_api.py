# -*- coding: utf-8 -*-
"""HTTP client for IntroDB (https://api.introdb.app).

Free, no API key. Keyed on IMDB id + season + episode — exactly the ids Forge
holds at play time — and returns intro/recap/outro segments. Thin HTTP only: no
caching or UI/selection logic (those live in ``caches/intro_outro_cache.py`` and
``modules/skip_markers.py``).

Unlike the older clients (bare ``except:`` returning ``None``), this one catches
the targeted ``requests.RequestException`` per the Forge hard rule, still
returning ``None`` on any failure so callers can short-circuit.
"""

import requests
from apis._http import TIMEOUT_FAST
from modules.kodi_utils import make_session

# from modules.kodi_utils import logger

session = make_session("https://api.introdb.app")

_SEGMENT_TYPES = ("intro", "recap", "outro")


def get_segments(imdb_id, season, episode):
	"""``GET /segments?imdb_id=&season=&episode=`` → parsed JSON dict, or ``None``.

	Returns ``None`` on any network error or non-200 response. The raw payload is
	``{"intro": {...}|null, "recap": {...}|null, "outro": {...}|null, ...}``;
	turning it into normalized segments is ``parse_segments``' job.
	"""
	try:
		response = session.get(
			"https://api.introdb.app/segments",
			params={"imdb_id": imdb_id, "season": season, "episode": episode},
			timeout=TIMEOUT_FAST,
		)
		if response.status_code != 200:
			return None
		return response.json()
	except requests.RequestException:
		return None
	except ValueError:
		# 200 with a non-JSON body — treat as no data rather than crashing.
		return None


def parse_segments(payload):
	"""Pure, unit-testable: turn the ``{intro,recap,outro}`` payload into the
	normalized segment list.

	- Skips ``null``/missing segments.
	- Prefers ``start_sec``/``end_sec``; falls back to ``start_ms``/``end_ms`` / 1000.
	- Drops a segment whose start/end can't be read or where ``end <= start``.
	- Tags ``source: "introdb"``; carries ``confidence`` and ``submission_count``
	  (defaulting to ``0`` when absent) for the threshold step.

	Returns ``[]`` for an empty/``None`` payload.
	"""
	segments = []
	if not payload:
		return segments
	for seg_type in _SEGMENT_TYPES:
		raw = payload.get(seg_type)
		if not raw:
			continue
		start, end = _seconds(raw, "start"), _seconds(raw, "end")
		if start is None or end is None or end <= start:
			continue
		segments.append(
			{
				"type": seg_type,
				"start": start,
				"end": end,
				"source": "introdb",
				"confidence": _as_float(raw.get("confidence"), 0.0),
				"submission_count": _as_int(raw.get("submission_count"), 0),
			}
		)
	return segments


def _seconds(raw, prefix):
	"""Read ``<prefix>_sec`` (preferred) or ``<prefix>_ms`` / 1000 as a float; ``None`` if neither is usable."""
	sec = raw.get("%s_sec" % prefix)
	if sec is not None:
		return _as_float(sec, None)
	ms = _as_float(raw.get("%s_ms" % prefix), None)
	if ms is not None:
		return ms / 1000.0
	return None


def _as_float(value, default):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _as_int(value, default):
	try:
		return int(value)
	except (TypeError, ValueError):
		return default
