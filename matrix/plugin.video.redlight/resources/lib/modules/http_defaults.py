# -*- coding: utf-8 -*-
"""Shared HTTP defaults for meta account APIs (Trakt, Simkl, MDBList, PunchPlay)."""
from requests.adapters import Retry

# Single request wait for meta sync / list / scrobble calls.
META_API_TIMEOUT = 20

def meta_status_retry():
	"""Retry flaky server responses only — not connect/read failures (airplane/offline)."""
	return Retry(
		total=2,
		connect=0,
		read=0,
		status=2,
		backoff_factor=0.5,
		status_forcelist=(429, 500, 502, 503, 504),
		allowed_methods=frozenset({'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'POST', 'PATCH'}),
	)
