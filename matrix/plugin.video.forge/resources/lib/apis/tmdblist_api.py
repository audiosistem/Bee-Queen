# -*- coding: utf-8 -*-
from apis._http import TIMEOUT_STANDARD
from caches.settings_cache import get_setting, set_setting
from caches.tmdb_lists import tmdb_lists_cache, tmdb_lists_cache_object
from modules.kodi_utils import confirm_dialog, make_session, notification, progress_dialog, sleep
from modules.settings import max_threads
from modules.utils import TaskPool, copy2clip, launch_browser, make_qrcode

# from modules.kodi_utils import logger

session = make_session("https://api.themoviedb.org")


def _make_tinyurl(url):
	# Local to the TMDb auth flow only — the request_token is a long JWT, so the auth
	# URL is unwieldy on screen. Shorten it via tinyurl; "" on any failure (caller falls
	# back to the full URL).
	import requests

	try:
		response = requests.get("https://tinyurl.com/api-create.php", params={"url": url}, timeout=10)
		if response.status_code == 200:
			return response.text.strip()
	except Exception:
		pass
	return ""


class TMDbListAPI:
	def __init__(self):
		self.base_url = "https://api.themoviedb.org/4"
		self.base_url_v3 = "https://api.themoviedb.org/3"
		self.read_access_token = (
			"eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIzMDJiZmNkYWYwODczOWUyNjUwYWVkMDZiMDNiNWMxOSIsIm5iZiI6MTc3OTk5MzQ1Ni40NDMsInN1YiI6IjZhMTg4YjcwNDI0MzFhYzVjNDY3YTcwNCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ"
			".hURQLwtKKXgOFvwYQ7N_aF7KefwtGjhLYyO_VRzHiQ0"
		)

	def auth(self):
		import requests

		headers = {"accept": "application/json", "content-type": "application/json", "Authorization": "Bearer %s" % self.read_access_token}
		data = requests.post("%s/auth/request_token" % self.base_url, headers=headers, timeout=TIMEOUT_STANDARD).json()
		if not data.get("success") or "request_token" not in data:
			return notification(data.get("status_message") or "Failed to Auth Account")
		request_token = data["request_token"]
		token_url = "https://www.themoviedb.org/auth/access?request_token=%s" % request_token
		short_url = _make_tinyurl(token_url) or token_url
		qr_code = make_qrcode(short_url) or ""
		copy2clip(short_url)
		if confirm_dialog(
			heading="TMDb Account Authorization",
			text="Open the authorization page in your browser now?",
			ok_label="Open Browser",
			cancel_label="Use QR Code",
		):
			launch_browser(token_url)
		p_dialog_insert = "[CR]OR visit: [B]%s[/B] (copied to clipboard)" % short_url
		progressDialog = progress_dialog(heading="TMDb Account Authorization", icon=qr_code)
		count, success = 72, None
		while not progressDialog.iscanceled() and count >= 0 and success == None:
			try:
				count -= 1
				response = requests.post(
					"%s/auth/access_token" % self.base_url, json={"request_token": request_token}, headers=headers, timeout=TIMEOUT_STANDARD
				).json()
				if response.get("success") and response.get("access_token"):
					success = True
				progressDialog.update("Please Scan the QR Code%s[CR]Confirm Access to your TMDb Account" % p_dialog_insert, count)
				sleep(2500)
			except:
				success = False
		progressDialog.close()
		if success:
			success = self.add_tmdb3_to_session(response["access_token"], response["account_id"])
		tmdb_lists_cache.clear_all()
		notification("Success" if success else "Failed")

	def add_tmdb3_to_session(self, access_token, account_id):
		import requests

		headers = {"accept": "application/json", "content-type": "application/json", "Authorization": "Bearer %s" % self.read_access_token}
		response = requests.post(
			"https://api.themoviedb.org/3/authentication/session/convert/4", json={"access_token": access_token}, headers=headers, timeout=TIMEOUT_STANDARD
		).json()
		session_id = response.get("session_id")
		if response.get("success") and session_id:
			success = True
		else:
			success = False
		if success:
			response = requests.get(
				("https://api.themoviedb.org/3/account"), params={"session_id": session_id}, headers=headers, timeout=TIMEOUT_STANDARD
			).json()
			username, account_session_id = response.get("username"), response.get("id")
			if not account_session_id:
				success = False
		if success:
			set_setting("tmdb.token", access_token)
			set_setting("tmdb.account_id", account_id)
			set_setting("tmdb.username", username)
			set_setting("tmdb.session_id", session_id)
			set_setting("tmdb.account_session_id", str(account_session_id))
			return True
		return False

	def revoke(self):
		import requests

		# Best-effort remote delete of the *user's* access token (the v4 endpoint; the v3 path 404s).
		# Wrapped so a network/JSON error can't abort the local cleanup below.
		access_token = get_setting("forge.tmdb.token")
		if access_token and access_token != "empty_setting":
			headers = {"accept": "application/json", "content-type": "application/json", "Authorization": "Bearer %s" % self.read_access_token}
			try:
				requests.delete(
					"https://api.themoviedb.org/4/auth/access_token", json={"access_token": access_token}, headers=headers, timeout=TIMEOUT_STANDARD
				)
			except Exception:
				pass
		# Always clear local auth — the user's intent is to disconnect locally (re-auth / switch account).
		set_setting("tmdb.token", "empty_setting")
		set_setting("tmdb.account_id", "empty_setting")
		set_setting("tmdb.username", "empty_setting")
		set_setting("tmdb.session_id", "empty_setting")
		set_setting("tmdb.account_session_id", "empty_setting")
		tmdb_lists_cache.clear_all()
		return notification("Success! Auth Revoked")

	def get_user_lists(self):
		def _process_multi(page_no):
			try:
				results_extend(self.request_data(url % (self.base_url, account_id, page_no))["results"])
			except:
				pass

		def _process(dummy):
			result = self.request_data(url % (self.base_url, account_id, 1))
			results_extend(result["results"])
			total_pages = result["total_pages"]
			if total_pages > 1:
				threads = TaskPool().tasks(_process_multi, range(2, total_pages + 1), max_threads())
				[i.join() for i in threads]
			return results

		account_id = get_setting("forge.tmdb.account_id")
		string = "get_user_lists"
		url = "%s/account/%s/lists?page=%s"
		results = []
		results_extend = results.extend
		return tmdb_lists_cache_object(_process, string, "dummy")

	def get_watchfavrecs_list_details(self, list_id, media_type):
		def _process_multi(page_no):
			try:
				results_extend(
					[
						dict(i, **{"original_order": c})
						for c, i in enumerate(
							self.request_data(url % (self.base_url, account_id, media_type, list_id, page_no))["results"], (page_no * 20) - 20
						)
					]
				)
			except:
				pass

		def _process(dummy):
			result = self.request_data(url % (self.base_url, account_id, media_type, list_id, 1))
			results_extend([dict(i, **{"original_order": c}) for c, i in enumerate(result["results"])])
			total_pages = result["total_pages"]
			if list_id == "recommendations":
				total_pages = 2
			if total_pages > 1:
				threads = TaskPool().tasks(_process_multi, range(2, total_pages + 1), max_threads())
				[i.join() for i in threads]
			return results

		account_id = get_setting("forge.tmdb.account_id")
		string = "get_watchfavrecs_list_details_%s_%s" % (list_id, media_type)
		url = "%s/account/%s/%s/%s?page=%s"
		if list_id == "recommendations":
			url += "&language=en-US&region=US"
		results = []
		results_extend = results.extend
		return tmdb_lists_cache_object(_process, string, "dummy")

	def get_list_details(self, list_id):
		def _process_multi(page_no):
			try:
				results_extend(
					[
						dict(i, **{"original_order": c})
						for c, i in enumerate(self.request_data(url % (self.base_url, list_id, page_no))["results"], (page_no * 20) - 20)
					]
				)
			except:
				pass

		def _process(dummy):
			result = self.request_data(url % (self.base_url, list_id, 1))
			results_extend([dict(i, **{"original_order": c}) for c, i in enumerate(result["results"])])
			total_pages = result["total_pages"]
			if total_pages > 1:
				threads = TaskPool().tasks(_process_multi, range(2, total_pages + 1), max_threads())
				[i.join() for i in threads]
			return results

		string = "get_list_details_%s" % (list_id)
		url = "%s/list/%s?page=%s"
		results = []
		results_extend = results.extend
		return tmdb_lists_cache_object(_process, string, "dummy")

	def add_remove_from_list(self, list_id, items, action):
		url = "%s/list/%s/items" % (self.base_url, list_id)
		return self.request_data(url, data=items, method=action)

	def add_remove_from_watchfavs(self, media_type, media_id, list_type, status):
		if list_type == "favorites":
			list_type = "favorite"
		account_session_id = get_setting("tmdb.account_session_id")
		session_id = get_setting("tmdb.session_id")
		if "empty_setting" in [account_session_id, session_id]:
			notification("Please Re-Authenticate you TMDB account")
			return {"success": False}
		url = "%s/account/%s/%s" % (self.base_url_v3, account_session_id, list_type)
		return self.request_data(
			url, params={"session_id": session_id}, data={"media_type": media_type, "media_id": str(media_id), list_type: status}, method="post"
		)

	def make_list(self, list_name):
		url = "%s/list" % self.base_url
		return self.request_data(url, data={"description": "", "name": list_name, "iso_3166_1": "US", "iso_639_1": "en", "public": True}, method="post")

	def delete_list(self, list_id):
		url = "%s/list/%s" % (self.base_url, list_id)
		return self.request_data(url, method="delete")

	def rename_list(self, list_id, new_name):
		data = {"description": "", "name": new_name, "iso_3166_1": "US", "iso_639_1": "en", "public": True}
		url = "%s/list/%s" % (self.base_url, list_id)
		return self.request_data(url, data=data, method="put")

	def clear_list(self, list_id):
		url = "%s/list/%s/clear" % (self.base_url, list_id)
		return self.request_data(url)

	def item_status(self, list_id, media_type, media_id):
		url = "%s/list/%s/item_status" % (self.base_url, list_id)
		return self.request_data(url, params={"media_type": media_type, "media_id": int(media_id)})

	def request_data(self, url, params=None, data=None, method="get"):
		headers = {"accept": "application/json", "content-type": "application/json", "Authorization": "Bearer %s" % get_setting("forge.tmdb.token")}
		try:
			result = session.request(method, url, params=params, json=data, headers=headers, timeout=90).json()
		except:
			result = None
		return result


tmdb_list_api = TMDbListAPI()
