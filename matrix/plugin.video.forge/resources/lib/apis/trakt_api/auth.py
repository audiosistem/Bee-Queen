# -*- coding: utf-8 -*-
"""OAuth device-flow + authenticate/revoke."""

import json
import time

import requests
from apis._http import TIMEOUT_STANDARD
from caches import settings_cache
from modules import kodi_utils, settings
from modules.utils import copy2clip, launch_browser, make_qrcode

from .core import call_trakt, no_client_key, no_secret_key

__all__ = [
	"trakt_authenticate",
	"trakt_get_device_code",
	"trakt_get_device_token",
	"trakt_revoke_authentication",
]


def trakt_get_device_code():
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, "empty_setting", ""):
		return no_client_key()
	data = {"client_id": CLIENT_ID}
	return call_trakt("oauth/device/code", data=data, with_auth=False)


def trakt_get_device_token(device_codes):
	API_ENDPOINT = "https://api.trakt.tv/%s"
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, "empty_setting", ""):
		return no_client_key()
	CLIENT_SECRET = settings.trakt_secret()
	if CLIENT_SECRET in (None, "empty_setting", ""):
		return no_secret_key()
	result = None
	progressDialog = None
	try:
		headers = {"Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": CLIENT_ID}
		data = {"code": device_codes["device_code"], "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
		start = time.time()
		expires_in = device_codes["expires_in"]
		sleep_interval = device_codes["interval"]
		user_code = str(device_codes["user_code"])
		auth_url = "https://trakt.tv/activate?code=%s" % str(user_code)
		qr_code = make_qrcode(auth_url) or ""
		copy2clip(auth_url)
		if kodi_utils.confirm_dialog(
			heading="Trakt Authorize",
			text="Open the authorization page in your browser now?",
			ok_label="Open Browser",
			cancel_label="Use QR Code",
		):
			launch_browser(auth_url)
		content = "Enter [B]%s[/B] at [B]%s[/B][CR]OR....[CR]Scan the [B]QR Code[/B]" % (user_code, device_codes["verification_url"])
		progressDialog = kodi_utils.progress_dialog("Trakt Authorize", qr_code)
		progressDialog.update(content, 0)
		try:
			time_passed = 0
			while not progressDialog.iscanceled() and time_passed < expires_in:
				kodi_utils.sleep(max(sleep_interval, 1) * 1000)
				response = requests.post(API_ENDPOINT % "oauth/device/token", data=json.dumps(data), headers=headers, timeout=TIMEOUT_STANDARD)
				status_code = response.status_code
				if status_code == 200:
					result = response.json()
					break
				elif status_code == 400:
					time_passed = time.time() - start
					progress = int(100 * time_passed / expires_in)
					progressDialog.update(content, progress)
				else:
					break
		except requests.RequestException as e:
			kodi_utils.logger("trakt_get_device_token poll", str(e))
		try:
			if progressDialog is not None:
				progressDialog.close()
		except (RuntimeError, AttributeError):
			pass
	except Exception as e:
		kodi_utils.logger("trakt_get_device_token", str(e))
	return result


def trakt_authenticate(dummy=""):
	code = trakt_get_device_code()
	token = trakt_get_device_token(code)
	if token:
		settings_cache.set_setting("trakt.token", token["access_token"])
		settings_cache.set_setting("trakt.refresh", token["refresh_token"])
		settings_cache.set_setting("trakt.expires", str(time.time() + token["expires_in"]))
		settings_cache.set_setting("watched_indicators", "1")
		kodi_utils.sleep(1000)
		try:
			user = call_trakt("/users/me")
			settings_cache.set_setting("trakt.user", str(user["username"]))
		except (KeyError, TypeError) as e:
			kodi_utils.logger("Trakt authenticate /users/me error", str(e))
		kodi_utils.notification("Trakt Account Authorized", 3000)
		# Lazy import to break the auth ↔ sync cycle.
		from .sync import trakt_sync_activities

		trakt_sync_activities(force_update=True)
		return True
	kodi_utils.notification("Trakt Error Authorizing", 3000)
	return False


def trakt_revoke_authentication(dummy=""):
	from caches import trakt_cache

	settings_cache.set_setting("trakt.user", "empty_setting")
	settings_cache.set_setting("trakt.expires", "0")
	settings_cache.set_setting("trakt.token", "0")
	settings_cache.set_setting("trakt.refresh", "0")
	settings_cache.set_setting("trakt.next_daily_clear", "0")
	settings_cache.set_setting("watched_indicators", "0")
	trakt_cache.clear_all_trakt_cache_data(silent=True, refresh=False)
	kodi_utils.notification("Trakt Account Authorization Reset", 3000)
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, "empty_setting", ""):
		return no_client_key()
	CLIENT_SECRET = settings.trakt_secret()
	if CLIENT_SECRET in (None, "empty_setting", ""):
		return no_secret_key()
	data = {"token": settings_cache.get_setting("forge.trakt.token"), "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
	call_trakt("oauth/revoke", data=data, with_auth=False)
