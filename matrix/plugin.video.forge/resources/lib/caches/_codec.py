# -*- coding: utf-8 -*-
"""Shared cache encode/decode helpers.

Forge's SQLite caches and window-property memory caches were originally
written with `repr()` for encoding and `eval()` for decoding (FenLight
heritage). Phase 3 (E1) migrated `trakt_cache` to JSON; E4 extends the
same pattern to the rest: `meta_cache`, `external_cache`, `navigator_cache`,
`personal_lists_cache`, `episode_groups_cache`, and `base_cache.BaseCache`.

`decode(blob)` prefers `json.loads` (the new wire format) and falls back to
`ast.literal_eval` for legacy rows that haven't been rewritten yet. The
fallback is a permanent compatibility shim for installs where the JSON
rewrite hasn't run — restored backups, copied profiles, plugin-thread reads
racing service startup. `ast.literal_eval` is safe (literals only, no code
execution), unlike the original `eval()`.

Once a row is read and then re-set, it lands in the DB as JSON.
"""

import ast
import json


def decode(blob):
	"""Decode a cache blob, accepting both JSON and legacy repr() rows.

	`blob` is whatever was stored — a `str` for `repr()` rows or a `str` for
	`json.dumps` output. SQLite returns it as a Python str either way.
	"""
	try:
		return json.loads(blob)
	except (ValueError, TypeError):
		return ast.literal_eval(blob)


def encode(data):
	"""Encode a Python object for storage. JSON output, no surprises."""
	return json.dumps(data)
