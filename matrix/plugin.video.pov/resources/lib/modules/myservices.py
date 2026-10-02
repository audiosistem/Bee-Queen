import time
import urllib3
import urllib.parse
from threading import Thread, Timer
from windows import create_window
from modules import kodi_utils, cache
# logger = kodi_utils.logger

quote, clear_cache = urllib.parse.quote, cache.clear_cache
get_setting, set_setting, sleep = kodi_utils.get_setting, kodi_utils.set_setting, kodi_utils.sleep
notification, confirm_dialog = kodi_utils.notification, kodi_utils.confirm_dialog
qr_str = 'https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1%s'
meta_keys = 'title year poster fanart clearlogo'
code_str, nav2_str, await_str = 'PIN CODE: [B]%s[/B]', 'LOCATION: [B]%s[/B]', 'REMAINING: [B]%02d:%02d[/B]'
auth_str, noauth_str = 'Authorized: Select to Remove', 'Unauthorized: Select to Add'
http = urllib3.PoolManager(retries=False, timeout=urllib3.util.Timeout(connect=3.05, read=6.05))

def user_agent():
	return 'POV/%s.0' % kodi_utils.get_addoninfo('version').split('.')[0]

def watch_indicators(function):
	def wrapper(instance, *args, **kwargs):
		if function(instance, *args, **kwargs): kodi_utils.ok_dialog(text=(
			'At successful activation, watched status and resume progress will be set to [B]%s[/B]. '
			'To change settings after activation, use the addon settings category:[CR]'
			'[B]Features/Watched Indicators/Watched Status Provider[/B]'
		) % instance.__class__.__name__, top_space=False)
	return wrapper

def _make_progress_dialog(**kwargs):
	progress_dialog = create_window(('windows.progress', 'ProgressMedia'), 'progress_media.xml', **kwargs)
	Thread(target=progress_dialog.run).start()
	return progress_dialog

def authorize():
	def _builder():
		for api in services:
			item = kodi_utils.make_listitem()
			item.setLabel('[B]%s[/B]' % api.__name__.upper())
			item.setLabel2(auth_str if api().token else noauth_str)
			item.setArt({'icon': '%s%s' % (icon_path, api.icon)})
			yield item
	services = (Trakt, MDBList, TMDbList, Premiumize, Offcloud, TorBox, RealDebrid, AllDebrid, EasyNews)
	icon_path = kodi_utils.media_path()
	service = kodi_utils.dialog.select('My Services', list(_builder()), useDetails=True)
	if service < 0: return
	try: success = services[service]().set()
	except: kodi_utils.logger('myservices error', f"\n{__import__('traceback').format_exc()}")
	else: return success
	return kodi_utils.notify_error()

class RepeatTimer(Timer):
	def run(self):
		while not self.finished.wait(self.interval):
			self.function(*self.args, **self.kwargs)

class Premiumize:
	icon = 'premiumize.png'
	def __init__(self):
		self.client_id = '384733001'
		self.token = get_setting('pm.token')

	def clear(self):
		if not confirm_dialog(): return
		set_setting('pm.account_id', '')
		set_setting('pm.token', '')
		clear_cache('pm_cloud', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		response = conn.request('post', '/token', json=data)
		if not response.status < 400: return
		data.update(response.json())
		self.token = data['access_token']

	def set(self):
		if self.token: return self.clear()

		data = {'client_id': self.client_id, 'response_type': 'device_code'}
		conn = http.connection_from_url('https://www.premiumize.me')
		response = conn.request('post', '/token', json=data)
		result = response.json()
		data = {'client_id': self.client_id, 'code': result['device_code'], 'grant_type': 'device_code'}
		expires_in, expires_at = result['expires_in'], result['expires_in'] + time.monotonic()
		try: qr_icon = qr_str % '&data=%s' % quote(result['verification_uri'])
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['user_code'], nav2_str % result['verification_uri']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(result['interval'], self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.token: return kodi_utils.notify_error()
		sleep(500)
		headers = {'Authorization': 'Bearer %s' % self.token}
		response = conn.request('get', '/api/account/info', headers=headers)
		username = response.json()['customer_id']
		token = str(data['access_token'])
		set_setting('pm.account_id', str(username))
		set_setting('pm.token', token)
		notification('Set %s Authorization' % self.__class__.__name__)
		return True

class Offcloud:
	icon = 'offcloud.png'
	def __init__(self):
		self.grant_type = 'urn:ietf:params:oauth:grant-type:device_code'
		self.token = get_setting('oc.token')

	def clear(self):
		if not confirm_dialog(): return
		set_setting('oc.token', '')
		set_setting('oc.account_id', '')
		clear_cache('oc_cloud', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		response = conn.request('post', '/oauth/token', json=data)
		if not response.status < 400: return
		data.update(response.json())
		self.token = data['access_token']

	def set(self):
		if self.token: return self.clear()

		conn = http.connection_from_url('https://offcloud.com')
		response = conn.request('post', '/oauth/device/code')
		result = response.json()
		data = {'device_code': result['device_code'], 'grant_type': self.grant_type}
		expires_in, expires_at = result['expires_in'], result['expires_in'] + time.monotonic()
		try: qr_icon = qr_str % '&data=%s' % quote(result['verification_uri_complete'])
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['user_code'], nav2_str % result['verification_uri']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(result['interval'], self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.token: return kodi_utils.notify_error()
		params = {'key': self.token}
		response = conn.request('get', '/api/account/info', fields=params)
		result = response.json()
		customer = result['user_id']
		set_setting('oc.account_id', str(customer))
		set_setting('oc.token', self.token)
		notification('Set %s Authorization' % self.__class__.__name__)
		return True

class TorBox:
	icon = 'torbox.png'
	def __init__(self):
		self.token = get_setting('tb.token')

	def clear(self):
		if not confirm_dialog(): return
		set_setting('tb.token', '')
		set_setting('tb.account_id', '')
		clear_cache('tb_cloud', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		response = conn.request('post', '/v1/api/user/auth/device/token', json=data)
		if not response.status < 400: return
		data.update(response.json())
		self.token = data

	def set(self):
		if self.token: return self.clear()

		params = {'app': user_agent()}
		conn = http.connection_from_url('https://api.torbox.app')
		response = conn.request('get', '/v1/api/user/auth/device/start', fields=params)
		result = response.json()['data']
		data = {'device_code': result['device_code']}
		expires_in, expires_at = 600, 600 + time.monotonic()
		try: qr_icon = qr_str % '&bgcolor=04bf8a&data=%s' % quote(result['verification_url'])
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['code'], nav2_str % result['friendly_verification_url']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(result['interval'], self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		self.token = data['data']['access_token']
		headers = {'Authorization': 'Bearer %s' % self.token}
		response = conn.request('get', '/v1/api/user/me', headers=headers)
		result = response.json()
		customer = result['data']['customer']
		set_setting('tb.account_id', str(customer))
		set_setting('tb.token', self.token)
		notification('Set %s Authorization' % self.__class__.__name__)
		return True

class RealDebrid:
	icon = 'realdebrid.png'
	def __init__(self):
		self.grant_type = 'http://oauth.net/grant_type/device/1.0'
		self.client_id = 'X245A4XAIBGVM'
		self.secret = get_setting('rd.secret')
		self.token = get_setting('rd.token')

	def clear(self):
		if not confirm_dialog(): return
		set_setting('rd.username', '')
		set_setting('rd.client_id', '')
		set_setting('rd.token', '')
		set_setting('rd.refresh', '')
		set_setting('rd.secret', '')
		clear_cache('rd_cloud', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		params = {'client_id': self.client_id, 'code': data['code']}
		response = conn.request('get', '/oauth/v2/device/credentials', fields=params)
		if not response.status < 400: return
		data.update(response.json())
		self.secret = data['client_secret']

	def set(self):
		if self.token: return self.clear()

		params = {'client_id': self.client_id, 'new_credentials': 'yes'}
		conn = http.connection_from_url('https://app.real-debrid.com')
		response = conn.request('get', '/oauth/v2/device/code', fields=params)
		result = response.json()
		data = {'code': result['device_code'], 'grant_type': self.grant_type}
		expires_in, expires_at = result['expires_in'], result['expires_in'] + time.monotonic()
		try: qr_icon = qr_str % '&data=%s' % quote(result['direct_verification_url'])
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['user_code'], nav2_str % result['verification_url']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(result['interval'], self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.secret or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.secret: return kodi_utils.notify_error()
		response = conn.request('post', '/oauth/v2/token', fields=data)
		data.update(response.json())
		sleep(500)
		headers = {'Authorization': 'Bearer %s' % data['access_token']}
		response = conn.request('get', '/rest/1.0/user', headers=headers)
		username = response.json()['username']
		client_id, secret = data['client_id'], data['client_secret']
		token, refresh = data['access_token'], data['refresh_token']
		set_setting('rd.username', str(username))
		set_setting('rd.client_id', client_id)
		set_setting('rd.token', token)
		set_setting('rd.refresh', refresh)
		set_setting('rd.secret', secret)
		notification('Set %s Authorization' % self.__class__.__name__)
		return True

class AllDebrid:
	icon = 'alldebrid.png'
	def __init__(self):
		self.token = get_setting('ad.token')

	def clear(self):
		if not confirm_dialog(): return
		set_setting('ad.account_id', '')
		set_setting('ad.token', '')
		clear_cache('ad_cloud', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, url):
		response = conn.request('get', url)
		result = response.json()['data']
		self.token = result.get('apikey', '')

	def set(self):
		if self.token: return self.clear()

		conn = http.connection_from_url('https://api.alldebrid.com')
		response = conn.request('get', '/v4/pin/get')
		result = response.json()['data']
		expires_in, expires_at = result['expires_in'], result['expires_in'] + time.monotonic()
		try: qr_icon = qr_str % '&bgcolor=ffd700&data=%s' % quote(result['user_url'])
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['pin'], nav2_str % result['base_url']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(5, self.poll, args=(conn, result['check_url']))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.token: return kodi_utils.notify_error()
		sleep(500)
		headers = {'Authorization': 'Bearer %s' % self.token}
		response = conn.request('get', '/v4/user', headers=headers)
		result = response.json()['data']
		username = result['user']['username']
		set_setting('ad.account_id', str(username))
		set_setting('ad.token', self.token)
		notification('Set %s Authorization' % self.__class__.__name__)
		return True

class EasyNews:
	icon = 'easynews.png'
	def __init__(self):
		username = get_setting('easynews_user')
		password = get_setting('easynews_password')
		self.token = all((username, password))

	def clear(self):
		if not confirm_dialog(): return
		set_setting('easynews_user', '')
		set_setting('easynews_password', '')
		set_setting('provider.easynews', 'false')
		clear_cache('easynews', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def set(self):
		if self.token: return self.clear()

		username = kodi_utils.dialog.input('EasyNews Username:').strip()
		password = kodi_utils.dialog.input('EasyNews Password:').strip()
		if not all((username, password)): return
#		Account web page strangely blocked for some users, will work with vpn
#		from indexers.easynews_api import EasyNewsAPI
#		api = EasyNewsAPI()
#		api.username, api.password = username, password
#		account_info, usage_info = api.account_info()
#		if not account_info or not usage_info: return kodi_utils.notify_error()
		set_setting('easynews_user', username)
		set_setting('easynews_password', password)
		set_setting('provider.easynews', 'true')
		notification('Set %s Authorization' % self.__class__.__name__)
		return True

class Trakt:
	icon = 'trakt.png'
	def __init__(self):
		self.client_id = get_setting('trakt.client_id')
		self.secret = get_setting('trakt.client_secret')
		self.token = get_setting('trakt.token')

	def clear(self):
		if not confirm_dialog(): return
		data = {'token': self.token, 'client_id': self.client_id, 'client_secret': self.secret}
		conn = http.connection_from_url('https://auth.trakt.tv')
		response = conn.request('post', '/oauth/revoke', json=data)
		set_setting('trakt_user', '')
		set_setting('trakt.token', '')
		set_setting('trakt.refresh', '')
		set_setting('trakt.expires', '')
		set_setting('trakt_indicators_active', 'false')
		set_setting('watched_indicators', '0')
		sleep(500)
		clear_cache('trakt', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		response = conn.request('post', '/oauth/device/token', json=data)
		if not response.status < 400: return
		data.update(response.json())
		self.token = data['access_token']

	@watch_indicators
	def set(self):
		if self.token: return self.clear()

		data = {'client_id': self.client_id, 'client_secret': self.secret}
		conn = http.connection_from_url('https://auth.trakt.tv')
		response = conn.request('post', '/oauth/device/code', json=data)
		result = response.json()
		data['code'] = result['device_code']
		expires_in, expires_at = result['expires_in'], result['expires_in'] + time.monotonic()
		try: qr_icon = qr_str % '&color=f00&data=%s' % quote('%s/%s' % (result['verification_url'], result['user_code']))
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['user_code'], nav2_str % result['verification_url']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(result['interval'], self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.token: return kodi_utils.notify_error()
		sleep(500)
		headers = {'Content-Type': 'application/json', 'trakt-api-key': self.client_id, 'trakt-api-version': '2'}
		headers.update({'Authorization': 'Bearer %s' % self.token})
		response = http.request('get', 'https://api.trakt.tv/users/me', headers=headers)
		username = response.json()['username']
		expires = int(data['created_at']) + int(data['expires_in'])
		refresh, token = data['refresh_token'], data['access_token']
		set_setting('trakt_user', str(username))
		set_setting('trakt.token', token)
		set_setting('trakt.refresh', refresh)
		set_setting('trakt.expires', str(expires))
		set_setting('trakt_indicators_active', 'true')
		set_setting('watched_indicators', '1')
		notification('Set %s Authorization' % self.__class__.__name__)
		sleep(500)
		clear_cache('trakt', silent=True)
		return True

class MDBList:
	icon = 'mdblist.png'
	def __init__(self):
		self.grant_type = 'urn:ietf:params:oauth:grant-type:device_code'
		self.client_id = get_setting('mdblist.client_id')
		self.token = get_setting('mdblist.token')
		self.created_at = time.time()

	def clear(self):
		if not confirm_dialog(): return
		set_setting('mdblist_user', '')
		set_setting('mdblist.token', '')
		set_setting('mdblist.refresh', '')
		set_setting('mdblist.expires', '')
		set_setting('mdbl_indicators_active', 'false')
		set_setting('watched_indicators', '0')
		sleep(500)
		clear_cache('mdblist', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		response = conn.request('post', '/oauth/token/', fields=data, encode_multipart=False)
		if not response.status < 400: return
		data.update(response.json())
		self.token = data['access_token']

	@watch_indicators
	def set(self):
		if self.token: return self.clear()

		data = {'client_id': self.client_id, 'scope': 'write'}
		conn = http.connection_from_url('https://api.mdblist.com')
		response = conn.request('post', '/oauth/device-authorization/', fields=data, encode_multipart=False)
		result = response.json()
		data = {'device_code': result['device_code'], 'client_id': self.client_id, 'grant_type': self.grant_type}
		expires_in, expires_at = result['expires_in'], result['expires_in'] + time.monotonic()
		try: qr_icon = qr_str % '&data=%s' % quote(result['verification_uri_complete'])
		except: qr_icon = ''
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = code_str % result['user_code'], nav2_str % result['verification_uri']
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(result['interval'], self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.token: return kodi_utils.notify_error()
		headers = {'Authorization': 'Bearer %s' % self.token}
		response = conn.request('get', '/user', headers=headers)
		result = response.json()
		user_id, username = result['user_id'], result['username']
		expires = int(self.created_at) + int(data['expires_in'])
		refresh, token = data['refresh_token'], data['access_token']
		set_setting('mdblist_user', str(username))
		set_setting('mdblist.token', token)
		set_setting('mdblist.refresh', refresh)
		set_setting('mdblist.expires', str(expires))
		set_setting('mdbl_indicators_active', 'true')
		set_setting('watched_indicators', '2')
		notification('Set %s Authorization' % self.__class__.__name__)
		sleep(500)
		clear_cache('mdblist', silent=True)
		return True

class TMDbList:
	icon = 'tmdb.png'
	def __init__(self):
		self.read = get_setting('tmdb_read_token')
		self.token = get_setting('tmdb.token')
		self.session_id = get_setting('tmdb.session_id')
		self.headers = {'Authorization': 'Bearer %s' % self.read}

	def clear(self):
		if not confirm_dialog(): return
		data = {'session_id': self.session_id}
		conn = http.connection_from_url('https://api.themoviedb.org', pool_kwargs={'headers': self.headers})
		response = conn.request('delete', '/3/authentication/session', json=data)
		result = response.json()
		if not result['success']: return kodi_utils.notify_error()
		set_setting('tmdb.session_account_id', '')
		set_setting('tmdb.session_id', '')
		set_setting('tmdb.username', '')
		data = {'access_token': self.token}
		response = conn.request('delete', '/4/auth/access_token', json=data)
		result = response.json()
		if not result['success']: return kodi_utils.notify_error()
		set_setting('tmdb.account_id', '')
		set_setting('tmdb.token', '')
		clear_cache('tmdblist', silent=True)
		return notification('Removed %s Authorization' % self.__class__.__name__)

	def poll(self, conn, data):
		response = conn.request('post', '/4/auth/access_token', json=data)
		if not response.status < 400: return
		data.update(response.json())
		self.token = data['access_token']

	def set(self):
		if self.token: return self.clear()

		conn = http.connection_from_url('https://api.themoviedb.org', pool_kwargs={'headers': self.headers})
		response = conn.request('post', '/4/auth/request_token')
		result = response.json()
		if not result['success']: return
		data = {'request_token': result['request_token']}
		expires_in, expires_at = 600, 600 + time.monotonic()
		url = 'https://www.themoviedb.org/auth/access?request_token=%s' % result['request_token']
		try:
			tiny_resp = http.request('get', 'http://tinyurl.com/api-create.php', fields={'url': url})
			tiny_url = tiny_resp.data.decode('utf-8')
		except: tiny_url = url
		qr_icon = qr_str % '&data=%s' % quote(tiny_url)
		kodi_utils.logger('tmdblist', '%s\n%s' % (tiny_url, url))
		meta = {**dict.fromkeys(meta_keys.split(), ''), 'poster': qr_icon}
		detail = nav2_str % tiny_url, ''
		progress_dialog = _make_progress_dialog(meta=meta)
		timer = RepeatTimer(5, self.poll, args=(conn, data))
		timer.start()
		for i in range(1, expires_in + 1):
			if self.token or progress_dialog.iscanceled(): break
			lines = await_str % divmod(expires_at - time.monotonic(), 60), *detail
			progress = 100 - int(100 * i / expires_in)
			progress_dialog.update('[CR]'.join(lines), progress)
			sleep(1000)
		timer.cancel()
		progress_dialog.close()
		if progress_dialog.iscanceled(): return False
		if not self.token: return kodi_utils.notify_error()
		account_id, access_token = str(data['account_id']), str(data['access_token'])
		set_setting('tmdb.account_id', account_id)
		set_setting('tmdb.token', access_token)
		notification('Set %s Authorization' % self.__class__.__name__)
		sleep(500)
		if not self.token and not get_setting('tmdb.token'): return
		access_token = self.token or get_setting('tmdb.token')
		data = {'access_token': access_token}
		response = conn.request('post', '/3/authentication/session/convert/4', json=data)
		result = response.json()
		if not result['success']: return
		session_id = result['session_id']
		params = {'session_id': session_id}
		response = conn.request('get', '/3/account', fields=params)
		result = response.json()
		if 'id' not in result: return
		username, session_account_id = str(result['username']), str(result['id'])
		set_setting('tmdb.username', username)
		set_setting('tmdb.session_id', session_id)
		set_setting('tmdb.session_account_id', session_account_id)
		return True

