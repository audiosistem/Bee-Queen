# -*- coding: utf-8 -*-
"""HTTP core: `call_trakt`, `get_trakt`, token refresh, and TMDB id resolvers.

`call_trakt` is the load-bearing function — every other Trakt helper funnels
through it. `trakt_refresh_token` lives here too (rather than in `auth`) so the
core HTTP layer never has to upward-import from a feature submodule.
"""

import threading
import time

import requests
from apis._http import TIMEOUT_LONG
from caches import settings_cache
from modules import kodi_utils, settings
from modules.metadata import movie_meta_external_id, tvshow_meta_external_id

__all__ = [
	"call_trakt",
	"get_trakt",
	"get_trakt_movie_id",
	"get_trakt_tvshow_id",
	"make_trakt_slug",
	"no_client_key",
	"no_secret_key",
	"trakt_refresh_token",
]

# E5: serializes the read-expiry / refresh-token dance across plugin and
# service threads. Replaces the previous `forge.trakt_refreshing_token` window
# property latch, which was both racy (the expiry read happened outside the
# latch, so two callers could both observe a lapsed token before either set
# the flag) and prone to leaking "true" across plugin invocations on a crash.
_refresh_lock = threading.Lock()


def no_client_key():
	kodi_utils.notification("Please set a valid Trakt Client ID Key")
	return None


def no_secret_key():
	kodi_utils.notification("Please set a valid Trakt Client Secret Key")
	return None


def get_trakt(params):
	result = call_trakt(
		params["path"] % params.get("path_insert", ""),
		params=params.get("params", {}),
		data=params.get("data"),
		is_delete=params.get("is_delete", False),
		with_auth=params.get("with_auth", False),
		method=params.get("method"),
		pagination=params.get("pagination", True),
		page_no=params.get("page_no"),
	)
	return result[0] if params.get("pagination", True) else result


def call_trakt(path, params=None, data=None, is_delete=False, with_auth=True, method=None, pagination=False, page_no=1):
	# Copy the caller's params (or start fresh) so adding `page` for pagination
	# doesn't mutate the caller's dict or the function default across calls.
	params = dict(params) if params else {}

	def send_query():
		resp = None
		if with_auth:
			# Holding the lock across the expiry read + refresh is what closes
			# the race: a concurrent caller arriving here either waits for an
			# in-flight refresh to finish (and reads the fresh expires_at) or
			# does its own refresh under exclusive ownership. Double-checking
			# expires_at after acquisition avoids a redundant refresh when the
			# previous holder already updated it.
			with _refresh_lock:
				try:
					expires_at = float(settings_cache.get_setting("forge.trakt.expires"))
				except (ValueError, TypeError):
					expires_at = 0.0
				if time.time() > expires_at:
					_refresh_token_locked()
			token = settings_cache.get_setting("forge.trakt.token")
			if token:
				req_headers["Authorization"] = "Bearer " + token
		try:
			# extended=full + large lists can push the items endpoint to 1-2 MB and
			# 5-15 s under Trakt throttling. 10 s was tight enough to surface as
			# "lists not loading" symptoms; 30 s is the comfortable upper bound.
			if method:
				if method == "post":
					resp = requests.post(API_ENDPOINT % path, headers=req_headers, timeout=TIMEOUT_LONG)
				elif method == "delete":
					resp = requests.delete(API_ENDPOINT % path, headers=req_headers, timeout=TIMEOUT_LONG)
				else:
					resp = requests.get(API_ENDPOINT % path, params=params, headers=req_headers, timeout=TIMEOUT_LONG)
			elif data is not None:
				assert not params
				resp = requests.post(API_ENDPOINT % path, json=data, headers=req_headers, timeout=TIMEOUT_LONG)
			elif is_delete:
				resp = requests.delete(API_ENDPOINT % path, headers=req_headers, timeout=TIMEOUT_LONG)
			else:
				resp = requests.get(API_ENDPOINT % path, params=params, headers=req_headers, timeout=TIMEOUT_LONG)
			resp.raise_for_status()
		except requests.RequestException as e:
			kodi_utils.logger("Trakt Error", str(e))
		return resp

	API_ENDPOINT = "https://api.trakt.tv/%s"
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, "empty_setting", ""):
		return no_client_key()
	# Request headers are kept distinct from the response headers below. The
	# closure mutates `req_headers` (Authorization) on every call, so the 429
	# retry must re-send *these* — not the prior response's headers, which lack
	# `trakt-api-key` and would make the retry 401.
	req_headers = {"Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": CLIENT_ID}
	if pagination:
		params["page"] = page_no
	response = send_query()
	if response is None:
		return None
	status_code = response.status_code
	resp_headers = response.headers
	if status_code == 401:
		if with_auth:
			if settings.trakt_user_active():
				trakt_refresh_token()
			else:
				return None
		else:
			return None
	elif status_code == 429:
		if "Retry-After" in resp_headers:
			# Retry-After comes in as a header string; coercing here also makes
			# kodi_utils.sleep happy (it expects milliseconds as int).
			try:
				retry_seconds = int(resp_headers["Retry-After"])
			except (ValueError, TypeError):
				retry_seconds = 1
			kodi_utils.sleep(1000 * retry_seconds)
			response = send_query()
			# The retry can come back None (network error inside send_query);
			# bail rather than dereference it below.
			if response is None:
				return None
			# Re-anchor on the retry response so the content-type branch below
			# decodes the *retry's* body, not the 429's.
			resp_headers = response.headers
	response.encoding = "utf-8"
	result = response.json() if "json" in resp_headers.get("Content-Type", "") else response.text
	if method == "sort_by_headers":
		sort_by, sort_how = resp_headers.get("X-Sort-By", "title"), resp_headers.get("X-Sort-How", "asc")
		result = {"sort_by": sort_by, "sort_how": sort_how, "data": result}
	if pagination:
		return (result, resp_headers.get("X-Pagination-Page-Count", page_no))
	else:
		return result


def trakt_refresh_token():
	# Public entry point: acquires the lock then delegates. `send_query` skips
	# this and calls `_refresh_token_locked` directly because it already owns
	# the lock — re-acquiring a non-reentrant Lock would deadlock.
	with _refresh_lock:
		_refresh_token_locked()


def _refresh_token_locked():
	# Outer catch is intentionally broad: refresh runs on the request path and
	# must never surface an exception to the caller — but we log so a broken
	# refresh stops being invisible.
	try:
		CLIENT_ID = settings.trakt_client()
		if CLIENT_ID in (None, "empty_setting", ""):
			return no_client_key()
		CLIENT_SECRET = settings.trakt_secret()
		if CLIENT_SECRET in (None, "empty_setting", ""):
			return no_secret_key()
		data = {
			"client_id": CLIENT_ID,
			"client_secret": CLIENT_SECRET,
			"redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
			"grant_type": "refresh_token",
			"refresh_token": settings_cache.get_setting("forge.trakt.refresh"),
		}
		response = call_trakt("oauth/token", data=data, with_auth=False)
		if response:
			settings_cache.set_setting("trakt.token", response["access_token"])
			settings_cache.set_setting("trakt.refresh", response["refresh_token"])
			settings_cache.set_setting("trakt.expires", str(time.time() + response["expires_in"]))
	except Exception as e:
		kodi_utils.logger("Trakt refresh_token error", str(e))


def get_trakt_movie_id(item):
	if item["tmdb"]:
		return item["tmdb"]
	tmdb_id = None
	api_key = settings.tmdb_api_key()
	if item["imdb"]:
		try:
			meta = movie_meta_external_id("imdb_id", item["imdb"], api_key)
			tmdb_id = meta["id"]
		except (KeyError, TypeError):
			pass
	return tmdb_id


def get_trakt_tvshow_id(item):
	if item["tmdb"]:
		return item["tmdb"]
	tmdb_id = None
	api_key = settings.tmdb_api_key()
	if item["imdb"]:
		try:
			meta = tvshow_meta_external_id("imdb_id", item["imdb"], api_key)
			tmdb_id = meta["id"]
		except (KeyError, TypeError):
			tmdb_id = None
	if not tmdb_id:
		if item["tvdb"]:
			try:
				meta = tvshow_meta_external_id("tvdb_id", item["tvdb"], api_key)
				tmdb_id = meta["id"]
			except (KeyError, TypeError):
				tmdb_id = None
	return tmdb_id


def make_trakt_slug(name):
	import re

	name = name.strip()
	name = name.lower()
	name = re.sub("[^a-z0-9_]", "-", name)
	name = re.sub("--+", "-", name)
	return name
