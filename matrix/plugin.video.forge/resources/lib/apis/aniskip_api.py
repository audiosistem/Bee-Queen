# -*- coding: utf-8 -*-
"""HTTP client for AniSkip (https://api.aniskip.com).

Free, no API key. Keyed on **MAL id + episode number** (resolved from Forge's
TMDB/TVDB/IMDB ids by ``apis/anime_mapping_api.py``). AniSkip has far richer
coverage of anime openings/endings than IntroDB, so the resolver prefers it for
anime episodes. Thin HTTP only: no caching or selection logic.

Like the IntroDB client (and unlike the older bare-``except:`` clients), this
catches the targeted ``requests.RequestException`` per the Forge hard rule, still
returning ``None`` on any failure so callers can short-circuit to IntroDB.

The v2 response shape (verified live)::

    {"found": true,
     "results": [{"interval": {"startTime": 0.0, "endTime": 90.0},
                  "skipType": "op", "skipId": "...", "episodeLength": 1440.0}],
     "message": "...", "statusCode": 200}
"""

import requests
from apis._http import TIMEOUT_FAST
from modules.kodi_utils import make_session

# from modules.kodi_utils import logger

session = make_session("https://api.aniskip.com")

# AniSkip skip types → our normalized segment types. "mixed-*" variants are the
# combined op/ed-with-other-content cuts; fold them into the same skip target.
_TYPE_MAP = {
	"op": "intro",
	"mixed-op": "intro",
	"ed": "outro",
	"mixed-ed": "outro",
	"recap": "recap",
}


def get_skip_times(mal_id, episode_number, episode_length_sec):
	"""``GET /v2/skip-times/{malId}/{ep}?types=op&types=ed&types=recap&episodeLength=<sec>``
	→ parsed JSON dict, or ``None`` on any network error / non-200.

	``episode_length_sec`` lets AniSkip scale its stored intervals to the real
	runtime; pass the player's ``getTotalTime()`` when available (Risk #6).
	"""
	try:
		response = session.get(
			"https://api.aniskip.com/v2/skip-times/%s/%s" % (mal_id, episode_number),
			# A list of tuples produces the repeated ``types=op&types=ed&types=recap``
			# the API expects (plain ``types=``, not ``types[]=``).
			params=[("types", "op"), ("types", "ed"), ("types", "recap"), ("episodeLength", int(episode_length_sec or 0))],
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


def parse_skip_times(payload):
	"""Pure, unit-testable: turn the AniSkip v2 payload into the normalized
	segment list (the common shape shared with IntroDB / chapters).

	- ``{"found": false}`` / empty / ``None`` → ``[]``.
	- Maps ``op→intro``, ``ed→outro``, ``recap→recap`` (and the ``mixed-*``
	  variants); skips unknown skip types.
	- Drops a segment whose start/end can't be read or where ``end <= start``.
	- Tags ``source: "aniskip"``. AniSkip has no crowd confidence/submission
	  metrics, so it sets sentinels (confidence ``1.0``, submission_count ``0``);
	  ``skip_markers.apply_threshold`` exempts ``aniskip`` from the gate anyway.
	"""
	segments = []
	if not payload or not payload.get("found"):
		return segments
	for item in payload.get("results") or []:
		seg_type = _TYPE_MAP.get(item.get("skipType"))
		if not seg_type:
			continue
		interval = item.get("interval") or {}
		start, end = _as_float(interval.get("startTime"), None), _as_float(interval.get("endTime"), None)
		if start is None or end is None or end <= start:
			continue
		segments.append(
			{
				"type": seg_type,
				"start": start,
				"end": end,
				"source": "aniskip",
				"confidence": 1.0,
				"submission_count": 0,
			}
		)
	return segments


def _as_float(value, default):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default
