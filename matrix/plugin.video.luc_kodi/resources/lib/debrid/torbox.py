import requests
from sys import argv, exit as sysexit
from threading import Thread
from urllib.parse import urlencode
from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.modules import string_tools
from resources.lib.modules.source_utils import supported_video_extensions

getLS = control.lang
getSetting = control.setting
base_url = 'https://api.torbox.app/v1/api'
tb_icon = control.joinPath(control.artPath(), 'torbox.png')
addonFanart = control.addonFanart()

session = requests.Session()
session.mount(base_url, requests.adapters.HTTPAdapter(max_retries=1))

class TorBox:
	download = '/torrents/requestdl'
	download_usenet = '/usenet/requestdl'
	remove = '/torrents/controltorrent'
	remove_usenet = '/usenet/controlusenetdownload'
	stats = '/user/me'
	history = '/torrents/mylist'
	history_usenet = '/usenet/mylist'
	explore = '/torrents/mylist?id=%s'
	explore_usenet = '/usenet/mylist?id=%s'
	cache = '/torrents/checkcached'
	cache_usenet = '/usenet/checkcached'
	cloud = '/torrents/createtorrent'
	cloud_usenet = '/usenet/createusenetdownload'

	def __init__(self):
		self.name = 'TorBox'
		self.user_agent = 'Mozilla/5.0'
		self.api_key = getSetting('torbox.token')
		self.sort_priority = getSetting('torbox.priority')
		self.store_to_cloud = getSetting('torbox.saveToCloud') == 'true'
		self.timeout = 28.0

	def _request(self, method, path, params=None, json=None, data=None):
		if not self.api_key: return
		session.headers['Authorization'] = 'Bearer %s' % self.api_key
		full_path = '%s%s' % (base_url, path)
		try:
			response = session.request(method, full_path, params=params, json=json, data=data, timeout=self.timeout)
		except Exception as e:
			log_utils.log('TorBox network error: %s' % e, level=log_utils.LOGWARNING)
			return {}
		# Parse body first so we can read 'success'/'error'/'detail' regardless of status code
		try: result = response.json()
		except: result = {}
		# TorBox 2026: standardised response shape is {success, error, detail, data}.
		# Surface critical error codes user-friendly via 'detail'.
		# Per https://api-docs.torbox.app/ -- COOLDOWN_LIMIT, MONTHLY_LIMIT, ACTIVE_LIMIT,
		# PLAN_RESTRICTED_FEATURE, DOWNLOAD_TOO_LARGE are client-actionable, all others log only.
		if isinstance(result, dict) and result.get('success') is False:
			err = result.get('error') or ''
			detail = result.get('detail') or ''
			if err in ('COOLDOWN_LIMIT', 'MONTHLY_LIMIT', 'ACTIVE_LIMIT', 'PLAN_RESTRICTED_FEATURE', 'DOWNLOAD_TOO_LARGE'):
				# These are limit/plan errors the user can act on -- surface a toast.
				try: control.notification(title='TorBox: %s' % err, message=detail or err, icon=tb_icon)
				except Exception: pass
				log_utils.log('TorBox limit: %s -- %s' % (err, detail), level=log_utils.LOGWARNING)
			elif err in ('BAD_TOKEN', 'AUTH_ERROR', 'NO_AUTH'):
				log_utils.log('TorBox auth error (%s): %s' % (err, detail), level=log_utils.LOGWARNING)
			elif err:
				log_utils.log('TorBox %s: %s [%s %s]' % (err, detail, method.upper(), path), level=log_utils.LOGDEBUG)
		# Defensive raise_for_status (preserves existing behavior for non-2xx that didn't parse)
		try: response.raise_for_status()
		except Exception as e:
			if not (isinstance(result, dict) and 'success' in result):
				log_utils.log('TorBox HTTP error: %s\n%s' % (e, response.text[:500] if hasattr(response, 'text') else ''), level=log_utils.LOGDEBUG)
		return result

	def _GET(self, url, params=None):
		return self._request('get', url, params=params)

	def _POST(self, url, params=None, json=None, data=None):
		return self._request('post', url, params=params, json=json, data=data)

	def add_headers_to_url(self, url):
		return url + '|' + urlencode(self.headers())

	def headers(self):
		return {'User-Agent': self.user_agent}

	@property
	def days_remaining(self):
		import datetime
		try:
			account_info = self.account_info()
			date_string = account_info['data']['premium_expires_at'][:10]
			expires = datetime.datetime.strptime(date_string, '%Y-%m-%d')
			days_remaining = (expires - datetime.datetime.today()).days
		except: days_remaining = None
		return days_remaining

	def account_info(self):
		return self._GET(self.stats)

	def torrent_info(self, request_id=''):
		url = self.explore % request_id
		return self._GET(url)

	def delete_torrent(self, request_id=''):
		data = {'torrent_id': request_id, 'operation': 'delete'}
		return self._POST(self.remove, json=data)

	def delete_usenet(self, request_id=''):
		data = {'usenet_id': request_id, 'operation': 'delete'}
		return self._POST(self.remove_usenet, json=data)

	def unrestrict_link(self, file_id):
		torrent_id, file_id = file_id.split(',')
		params = {'token': self.api_key, 'torrent_id': torrent_id, 'file_id': file_id}
		try: return self._GET(self.download, params=params)['data']
		except: return None

	def unrestrict_usenet(self, file_id):
		usenet_id, file_id = file_id.split(',')
		params = {'token': self.api_key, 'usenet_id': usenet_id, 'file_id': file_id}
		try: return self._GET(self.download_usenet, params=params)['data']
		except: return None

	def check_cache_single(self, hash):
		return self._GET(self.cache, params={'hash': hash, 'format': 'list'})

	def check_cache(self, hashlist):
		data = {'hashes': hashlist}
		return self._POST(self.cache, params={'format': 'list'}, json=data)

	def check_cache_usenet(self, hashlist):
		"""TorBox 2026: cache check for usenet items.
		Hashes are md5(nzb_link) per https://api-docs.torbox.app/.
		Returns set of cached hashes (lowercase) or empty set on error."""
		if not hashlist: return set()
		try:
			data = {'hashes': list(hashlist)}
			response = self._POST(self.cache_usenet, params={'format': 'list'}, json=data)
			if not response or not response.get('success'): return set()
			rows = response.get('data') or []
			return set(i['hash'].lower() for i in rows if i.get('hash'))
		except Exception:
			log_utils.error()
			return set()

	def add_magnet(self, magnet, add_only_if_cached=None):
		"""TorBox 2026: pass add_only_if_cached so uncached magnets don't get
		silently queued against the user's active-download limit."""
		if add_only_if_cached is None:
			add_only_if_cached = getSetting('torbox.add_only_if_cached') in ('', 'true')
		data = {'magnet': magnet, 'seed': 3, 'allow_zip': 'false'}
		if add_only_if_cached:
			data['add_only_if_cached'] = 'true'
		return self._POST(self.cloud, data=data)

	def add_nzb(self, nzb_url, add_only_if_cached=None):
		"""TorBox 2026: add an NZB usenet download. Accepts a link or an NZB file.
		Pro plan required. Honours the same add_only_if_cached setting as magnets."""
		if add_only_if_cached is None:
			add_only_if_cached = getSetting('torbox.add_only_if_cached') in ('', 'true')
		data = {'link': nzb_url}
		if add_only_if_cached:
			data['add_only_if_cached'] = 'true'
		return self._POST(self.cloud_usenet, data=data)

	def resolve_nzb(self, nzb_url, info_hash, season, episode, title):
		"""TorBox 2026: resolve a usenet (NZB) item to a playable URL.

		Mirror of resolve_magnet() but for the /usenet/* endpoints. The picker
		hands us the raw .nzb link (item['url']); we add it, explore the usenet
		download's file list, pick the right video file (season/episode aware,
		extras filtered) and unrestrict it. Without this method usenet items
		fell through sourcesResolve()'s hoster branch (which only knows
		RD/PM/AD) and never produced a URL — i.e. usenet results were
		un-playable despite appearing as 'cached usenet' in the picker.
		"""
		from resources.lib.modules.source_utils import seas_ep_filter, extras_filter
		import time as _t
		usenet_id = None
		try:
			file_url, match = None, False
			extensions = supported_video_extensions()
			title = title or ''
			extras_filtering_list = tuple(i for i in extras_filter() if not i in title.lower())

			# Add the NZB (honours add_only_if_cached). TorBox de-duplicates by
			# hash, so re-adding an already-cached item just returns its id.
			result = self.add_nzb(nzb_url)
			if not result or not result.get('success'):
				log_utils.log('TorBox resolve_nzb: add_nzb failed (%s)' % (result or {}).get('error'),
							  level=log_utils.LOGWARNING)
				return None
			# createusenetdownload devuelve data.usenetdownload_id (igual que POV).
			# Aceptamos también usenet_id/hash por tolerancia de esquema.
			_rdata = result.get('data') or {}
			usenet_id = _rdata.get('usenetdownload_id') or _rdata.get('usenet_id') or _rdata.get('hash')
			if not usenet_id:
				log_utils.log('TorBox resolve_nzb: no usenetdownload_id in add_nzb response (data=%s)' % _rdata,
							  level=log_utils.LOGWARNING)
				return None

			# Poll the usenet item until the file list is populated (cached items
			# resolve almost immediately; uncached may need a moment).
			files = []
			for _attempt in range(5):
				info = self.user_cloud_usenet(usenet_id)
				data = (info or {}).get('data') or {}
				files = data.get('files') or []
				if files:
					break
				_t.sleep(1.5 * (_attempt + 1))
			if not files:
				log_utils.log('TorBox resolve_nzb: no files after polling (usenet_id=%s)' % usenet_id,
							  level=log_utils.LOGWARNING)
				return None

			# Select the correct video file.
			correct_files = []
			if season and episode:
				for f in files:
					name = f.get('short_name') or f.get('name') or ''
					if not name.lower().endswith(tuple(extensions)):
						continue
					if seas_ep_filter(season, episode, name):
						correct_files.append(f)
						match = True
			if not match:
				# Movie (or single-file pack): largest video file wins.
				vids = [f for f in files
						if (f.get('short_name') or f.get('name') or '').lower().endswith(tuple(extensions))]
				if vids:
					vids.sort(key=lambda f: int(f.get('size') or 0), reverse=True)
					correct_files = [vids[0]]
					match = True

			if not match or not correct_files:
				return None

			# Honour extras filtering (sample/featurette/etc.) when a real
			# episode title is known, same as resolve_magnet.
			chosen = None
			for f in correct_files:
				name = (f.get('short_name') or f.get('name') or '').lower()
				if any(x in name for x in extras_filtering_list):
					continue
				chosen = f
				break
			if not chosen:
				chosen = correct_files[0]

			file_id = chosen.get('id')
			if file_id is None:
				return None

			# unrestrict_usenet expects "usenet_id,file_id"
			file_url = self.unrestrict_usenet('%s,%s' % (usenet_id, file_id))
			return file_url
		except Exception:
			log_utils.error()
			return None

	def create_transfer(self, magnet_url):
		result = self.add_magnet(magnet_url)
		if not result['success']: return ''
		return result['data'].get('torrent_id', '')

	def resolve_magnet(self, magnet_url, info_hash, season, episode, title):
		from resources.lib.modules.source_utils import seas_ep_filter, extras_filter
		import time as _t
		# v1.0.17 FIX: initialize torrent_id BEFORE the try block. Previously, if an
		# exception fired between try-entry and the line `torrent_id = torrent['data'][...]`,
		# the except handler's `if torrent_id:` raised NameError, masking the real cause.
		torrent_id = None
		try:
			file_url, match = None, False
			extensions = supported_video_extensions()
			# v1.0.18 FIX: defensive — title can arrive as None when called from the
			# auto-play-next-episode flow (the next_meta in player._show_next_episode_dialog
			# may not carry a title field for the new episode). Other debrid modules don't
			# touch title, but this module does, so coerce to '' to prevent AttributeError.
			title = title or ''
			extras_filtering_list = tuple(i for i in extras_filter() if not i in title.lower())

			# v1.0.17 FIX: cache check with retry+backoff against COOLDOWN_LIMIT and empty
			# responses. TorBox applies aggressive per-account cooldown on /torrents/checkcached
			# and /torrents/createtorrent, which previously caused 2nd-episode auto-play to
			# fail with "no streams" when E01's TorBox calls were still inside the cooldown
			# window.
			check = None
			for _attempt in range(3):
				check = self.check_cache_single(info_hash)
				if isinstance(check, dict) and check.get('success') and isinstance(check.get('data'), list):
					break
				if isinstance(check, dict) and check.get('error') == 'COOLDOWN_LIMIT':
					log_utils.log('TorBox COOLDOWN on check_cache_single, backing off (attempt %d)' % (_attempt + 1),
								  level=log_utils.LOGWARNING)
				_t.sleep(1.5 * (_attempt + 1))
			if not (isinstance(check, dict) and isinstance(check.get('data'), list)):
				return None
			match = info_hash in [i['hash'] for i in check['data']]
			if not match: return None

			# v1.0.17 FIX: add_magnet with retry+backoff against COOLDOWN_LIMIT.
			torrent = None
			for _attempt in range(3):
				torrent = self.add_magnet(magnet_url)
				if isinstance(torrent, dict) and torrent.get('success'):
					break
				if isinstance(torrent, dict) and torrent.get('error') == 'COOLDOWN_LIMIT':
					log_utils.log('TorBox COOLDOWN on add_magnet, backing off (attempt %d)' % (_attempt + 1),
								  level=log_utils.LOGWARNING)
					_t.sleep(2.0 * (_attempt + 1))
					continue
				# Non-recoverable error (auth, plan, monthly limit, bad token, etc.)
				break
			if not (isinstance(torrent, dict) and torrent.get('success')):
				return None
			torrent_id = (torrent.get('data') or {}).get('torrent_id')
			if not torrent_id:
				return None

			torrent_files = self.torrent_info(torrent_id)
			if not (isinstance(torrent_files, dict) and (torrent_files.get('data') or {}).get('files')):
				return None
			selected_files = [
				{'link': '%d,%d' % (torrent_id, i['id']), 'filename': i['short_name'], 'size': i['size']}
				for i in torrent_files['data']['files'] if i['short_name'].lower().endswith(tuple(extensions))
			]
			if not selected_files: return None
			if season:
				selected_files = [i for i in selected_files if seas_ep_filter(season, episode, i['filename'])]
			else:
				if self._m2ts_check(selected_files): raise Exception('_m2ts_check failed')
				selected_files = [i for i in selected_files if not any(x in i['filename'] for x in extras_filtering_list)]
				selected_files.sort(key=lambda k: k['size'], reverse=True)
			if not selected_files: return None
			file_key = selected_files[0]['link']
			file_url = self.unrestrict_link(file_key)
			if not self.store_to_cloud: Thread(target=self.delete_torrent, args=(torrent_id,)).start()
			return file_url
		except Exception as e:
			log_utils.error('TorBox: Error RESOLVE MAGNET "%s" ' % magnet_url)
			if torrent_id: Thread(target=self.delete_torrent, args=(torrent_id,)).start()
			return None

	def display_magnet_pack(self, magnet_url, info_hash):
		try:
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			if not torrent['success']: return None
			torrent_id = torrent['data']['torrent_id']
			torrent_files = self.torrent_info(torrent_id)
			torrent_files = [
				{'link': '%d,%d' % (torrent_id, item['id']), 'filename': item['short_name'], 'size': item['size'] / 1073741824}
				for item in torrent_files['data']['files'] if item['short_name'].lower().endswith(tuple(extensions))
			]
			self.delete_torrent(torrent_id)
			return torrent_files
		except Exception:
			if torrent_id: self.delete_torrent(torrent_id)
			return None

	def add_uncached_torrent(self, magnet_url, pack=False):
		control.busy()
		result = self.create_transfer(magnet_url)
		control.hide()
		if result: control.okDialog(title='default', message=getLS(40017) % 'TorBox')
		else: return control.okDialog(title=getLS(40018), message=getLS(33586))
		return True

	def _m2ts_check(self, folder_items):
		for item in folder_items:
			if item['filename'].endswith('.m2ts'): return True
		return False

	def auth(self):
		"""TorBox OAuth Device Code flow (v1.0.12).
		Mirrors the pattern Umbrella and POV use. Endpoints:
		  GET  /user/auth/device/start?app=luc_kodi -> {device_code, code, verification_url, friendly_verification_url, interval}
		  POST /user/auth/device/token  {device_code} -> {data: {access_token: ...}}
		Falls back to manual API key paste if the user cancels.
		"""
		from urllib.parse import quote_plus
		device_start_url = base_url + '/user/auth/device/start'
		device_token_url = base_url + '/user/auth/device/token'
		try:
			response = requests.get(device_start_url, params={'app': 'luc_kodi'}, timeout=self.timeout)
			response.raise_for_status()
			result = response.json() or {}
			if not result.get('success') or not isinstance(result.get('data'), dict):
				log_utils.log('TorBox auth: device/start did not return success', level=log_utils.LOGWARNING)
				return self._auth_manual_fallback()
		except Exception as e:
			log_utils.log('TorBox auth: device/start error: %s' % e, level=log_utils.LOGWARNING)
			return self._auth_manual_fallback()

		data = result['data']
		device_code = data.get('device_code') or ''
		user_code = str(data.get('code') or '')
		verify_url = data.get('friendly_verification_url') or data.get('verification_url') or 'https://tor.box/link'
		interval = int(data.get('interval') or 5)
		expires_in = 600
		if not device_code or not user_code:
			log_utils.log('TorBox auth: response missing device_code/code', level=log_utils.LOGWARNING)
			return self._auth_manual_fallback()

		# Best-effort QR notification (mirrors RealDebrid's auth flow)
		try:
			qr_icon = 'https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&bgcolor=04bf8a&data=%s' % quote_plus(verify_url)
			control.notification(message=verify_url, icon=qr_icon, time=15000)
		except Exception: pass

		highlight = control.getHighlightColor() if hasattr(control, 'getHighlightColor') else 'FF00FA9A'
		line1 = '[B]LOCATION:[/B] [COLOR %s]%s[/COLOR]' % (highlight, verify_url)
		line2 = '[B]PIN CODE:[/B] [COLOR %s]%s[/COLOR]' % (highlight, user_code)
		line3 = 'Open the link in your browser and enter the PIN'
		body = '%s\n%s\n%s' % (line1, line2, line3)

		progressDialog = control.progressDialog
		progressDialog.create('TorBox Authorization', body)
		progressDialog.update(100, body)

		access_token = None
		time_passed = 0
		try:
			while time_passed < expires_in:
				if progressDialog.iscanceled():
					progressDialog.close()
					return False
				control.sleep(interval * 1000)
				time_passed += interval
				progress_percent = 100 - int(100 * time_passed / expires_in)
				progressDialog.update(progress_percent, body)
				try:
					poll = requests.post(device_token_url, json={'device_code': device_code}, timeout=self.timeout)
					poll_json = poll.json()
				except Exception:
					continue
				# Per POV/Umbrella: success arrives as {success: true, data: {access_token: ...}}
				if isinstance(poll_json, dict) and poll_json.get('success') and isinstance(poll_json.get('data'), dict):
					access_token = poll_json['data'].get('access_token')
					if access_token: break
		finally:
			try: progressDialog.close()
			except Exception: pass

		if not access_token:
			control.notification(title='TorBox', message='Authorization timed out or cancelled', icon=tb_icon)
			return False

		# Persist + lookup customer
		self.api_key = access_token
		try:
			info = self.account_info() or {}
			customer = str((info.get('data') or {}).get('customer') or '')
		except Exception:
			customer = ''
		control.setSetting('torbox.token', access_token)
		control.setSetting('torbox.username', customer)
		try:
			from resources.lib.modules.debrid_state import sync_state
			sync_state()
		except Exception: pass
		control.notification(message='TorBox successfully authorized', icon=tb_icon)
		return True

	def _auth_manual_fallback(self):
		"""If device-code flow fails (network / API change / user preference),
		fall back to the original behavior: paste an API key manually."""
		try:
			if not control.yesnoDialog(
				'TorBox device-code authorization could not start.\n'
				'Would you like to paste an API key manually instead?', '', ''):
				return False
		except Exception:
			pass
		api_key = control.dialog.input('TorBox API Key:')
		if not api_key: return False
		self.api_key = api_key
		try:
			info = self.account_info() or {}
			customer = str((info.get('data') or {}).get('customer') or '')
		except Exception:
			customer = ''
		control.setSetting('torbox.token', api_key)
		control.setSetting('torbox.username', customer)
		control.notification(message='TorBox successfully authorized', icon=tb_icon)
		return True

	def remove_auth(self):
		try:
			self.api_key = ''
			control.setSetting('torbox.token', '')
			control.setSetting('torbox.username', '')
			try:
				from resources.lib.modules.debrid_state import sync_state
				sync_state()
			except Exception:
				pass
			control.notification(title='TorBox', message=40009)
		except: log_utils.error()

	def account_info_to_dialog(self):
		try:
			control.busy()
			# TorBox 2026: plan numbers per https://api-docs.torbox.app/
			# 0 Free / 1 Essential / 2 Pro (Usenet+) / 3 Standard.
			plans = {0: 'Free plan', 1: 'Essential plan', 2: 'Pro plan', 3: 'Standard plan'}
			account_info = self.account_info() or {}
			data = account_info.get('data') or {}
			def _human_bytes(n):
				try: n = float(n)
				except: return str(n)
				for unit in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
					if n < 1024.0: return '%.2f %s' % (n, unit)
					n /= 1024.0
				return '%.2f EB' % n
			plan_id = data.get('plan')
			plan_label = plans.get(plan_id, 'Unknown plan (%s)' % plan_id)
			items = []
			items += ['[B]Email[/B]: %s' % data.get('email', '-')]
			items += ['[B]Customer[/B]: %s' % data.get('customer', '-')]
			items += ['[B]Plan[/B]: %s' % plan_label]
			items += ['[B]Expires[/B]: %s' % data.get('premium_expires_at', '-')]
			td = data.get('total_downloaded')
			if td is not None:
				items += ['[B]Downloaded[/B]: %s' % _human_bytes(td)]
			control.hide()
			return control.selectDialog(items, 'TorBox')
		except: log_utils.error()

	def user_cloud(self, request_id=None):
		url = self.explore % request_id if request_id else self.history
		return self._GET(url)

	def user_cloud_usenet(self, request_id=None):
		url = self.explore_usenet % request_id if request_id else self.history_usenet
		return self._GET(url)

	def user_cloud_clear(self):
		if not control.yesnoDialog(getLS(32056), '', ''): return
		data = {'all': True, 'operation': 'delete'}
		self._POST(self.remove, json=data)
		self._POST(self.remove_usenet, json=data)

	def user_cloud_to_listItem(self):
		sysaddon, syshandle = 'plugin://plugin.video.luc_kodi/', int(argv[1])
		quote_plus = requests.utils.quote
		folder_str, deleteMenu = getLS(40046).upper(), getLS(40050)
		file_str, downloadMenu = getLS(40047).upper(), getLS(40048)
		folders = []
		try: folders += [{**i, 'mediatype': 'torent'} for i in self.user_cloud()['data'] if i['download_finished']]
		except: pass
		try: folders += [{**i, 'mediatype': 'usenet'} for i in self.user_cloud_usenet()['data'] if i['download_finished']]
		except: pass
		folders.sort(key=lambda k: k['updated_at'], reverse=True)
		for count, item in enumerate(folders, 1):
			try:
				cm = []
				folder_name = string_tools.strip_non_ascii_and_unprintable(item['name'])
				status_str = '[COLOR %s]%s[/COLOR]' % (control.getHighlightColor(), item['download_state'].capitalize())
				cm.append((deleteMenu % 'Torrent', 'RunPlugin(%s?action=tb_DeleteUserTorrent&id=%s&mediatype=%s&name=%s)' %
					(sysaddon, item['id'], item['mediatype'], quote_plus(folder_name))))
				label = '%02d | [B]%s[/B] | [B]%s[/B] | [I]%s [/I]' % (count, status_str, folder_str, folder_name)
				url = '%s?action=tb_BrowseUserTorrents&id=%s&mediatype=%s' % (sysaddon, item['id'], item['mediatype'])
				item = control.item(label=label, offscreen=True)
				item.addContextMenuItems(cm)
				item.setArt({'icon': tb_icon, 'poster': tb_icon, 'thumb': tb_icon, 'fanart': addonFanart, 'banner': tb_icon})
				item.setInfo(type='video', infoLabels='')
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except: log_utils.error()
		control.content(syshandle, 'files')
		control.directory(syshandle, cacheToDisc=True)

	def browse_user_torrents(self, folder_id, mediatype):
		sysaddon, syshandle = 'plugin://plugin.video.luc_kodi/', int(argv[1])
		quote_plus = requests.utils.quote
		extensions = supported_video_extensions()
		file_str, downloadMenu = getLS(40047).upper(), getLS(40048)
		files = self.user_cloud_usenet(folder_id) if mediatype == 'usenet' else self.user_cloud(folder_id)
		video_files = [i for i in files['data']['files'] if i['short_name'].lower().endswith(tuple(extensions))]
		for count, item in enumerate(video_files, 1):
			try:
				cm = []
				name = string_tools.strip_non_ascii_and_unprintable(item['short_name'])
				size = item['size']
				display_size = float(int(size)) / 1073741824
				label = '%02d | [B]%s[/B] | %.2f GB | [I]%s [/I]' % (count, file_str, display_size, name)
				item = '%d,%d' % (int(folder_id), item['id'])
				url = '%s?action=play_URL&url=%s&caller=torbox&mediatype=%s&type=unrestrict' % (sysaddon, item, mediatype)
				cm.append((downloadMenu, 'RunPlugin(%s?action=download&name=%s&image=%s&url=%s&caller=torbox&mediatype=%s&type=unrestrict)' %
					(sysaddon, quote_plus(name), quote_plus(tb_icon), item, mediatype)))
				item = control.item(label=label, offscreen=True)
				item.addContextMenuItems(cm)
				item.setArt({'icon': tb_icon, 'poster': tb_icon, 'thumb': tb_icon, 'fanart': addonFanart, 'banner': tb_icon})
				item.setInfo(type='video', infoLabels='')
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			except: log_utils.error()
		control.content(syshandle, 'files')
		control.directory(syshandle, cacheToDisc=True)

	def delete_user_torrent(self, request_id, mediatype, name):
		if not control.yesnoDialog(getLS(40050) % '?\n' + name, '', ''): return
		result = self.delete_usenet(request_id) if mediatype == 'usenet' else self.delete_torrent(request_id)
		if result['success']:
			control.notification(message='TorBox: %s was removed' % name, icon=tb_icon)
			control.refresh()
