from modules import kodi_utils
from session import session, HTTPAdapter, Retry
# logger = kodi_utils.logger

ip_url = 'https://api.ipify.org'
base_url = 'https://api.torbox.app'
timeout = 10
retry = Retry(total=None, status=1, status_forcelist=(429, 502, 503, 504), backoff_factor=1)
session.mount(base_url, HTTPAdapter(max_retries=retry))

class TorBoxAPI:
	icon = 'torbox.png'
	defaults_to_cloud = True

	def __init__(self):
		self.timeout = int(kodi_utils.get_setting('scrapers_timeout') or 10)
		self.token = kodi_utils.get_setting('tb.token')

	def api(self, method, path, **kwargs):
		headers = self.headers()
		try: response = session.request(method, base_url + path, **kwargs, headers=headers, timeout=self.timeout)
		except session.CUSTOM_ERRORS: return kodi_utils.notification('timeout: %s' % __name__)
		if not response.ok: kodi_utils.logger('', f"{__name__}, {response.reason}\n{response.url}")
		if bool(response.content) and 'json' in response.headers.get('Content-Type', ''):
			return self._parse(response)
		return response.text

	def _parse(self, response):
		is_control = any(x in response.url for x  in ('/control', '/edit'))
		response = response.json()
		if not is_control and 'data' in response and 'success' in response: return response['data']
		return response

	def headers(self):
		return {'Authorization': 'Bearer %s' % self.token}

	def days_remaining(self):
		from datetime import datetime, timezone
		try:
			account_info = self.account_info()
			expires = datetime.fromisoformat(account_info['premium_expires_at'].replace('Z', '+00:00'))
			days = (expires - datetime.now(timezone.utc)).days
		except: days = None
		return days

	def account_info(self):
		path = '/v1/api/user/me'
		return self.api('get', path)

	def user_cloud(self, mediatype):
		path = '/v1/api/%s/mylist' % mediatype
		params = {'bypass_cache': 'true'}
		return self.api('get', path, params=params)

	def user_folder(self, mediatype, request_id):
		path = '/v1/api/%s/mylist' % mediatype
		params = {'id': request_id}
		return self.api('get', path, params=params)

	def torrent_info(self, request_id, path='torrents'):
		path = '/v1/api/usenet/mylist' if 'usenet' in path else '/v1/api/torrents/mylist'
		params = {'id': request_id}
		return self.api('get', path, params=params)

	def toggle_airlock(self, mediatype, request_id, airlock_value):
		if 'usenet' in mediatype: path, key = '/v1/api/usenet/editusenetdownload', 'usenet_download_id'
		elif 'webdl' in mediatype: path, key = '/v1/api/webdl/editwebdownload', 'webdl_id'
		else: path, key = '/v1/api/torrents/edittorrent', 'torrent_id'
		data = {key: request_id, 'airlocked': airlock_value in ('true', True)}
		result = self.api('put', path, json=data)
		return True if result is not None and result['success'] else False

	def delete_torrent(self, request_id):
		if 'usenet' in request_id: path, key = '/v1/api/usenet/controlusenetdownload', 'usenet_id'
		elif 'webdl' in request_id: path, key = '/v1/apiwebdl/controlwebdownload', 'webdl_id'
		else: path, key = '/v1/api/torrents/controltorrent', 'torrent_id'
		ids = request_id.split(',')
		data = {key: int(ids[0]), 'operation': 'delete'}
		result = self.api('post', path, json=data)
		return True if result is not None and result['success'] else False

	def unrestrict_link(self, file_id):
		if 'usenet' in file_id: path, key = '/v1/api/usenet/requestdl', 'usenet_id'
		elif 'webdl' in file_id: path, key = '/v1/api/webdl/requestdl', 'web_id'
		else: path, key = '/v1/api/torrents/requestdl', 'torrent_id'
		ids = file_id.split(',')
		params = {key: ids[0], 'file_id': ids[1], 'token': self.token}
		try: user_ip = session.request('get', ip_url, timeout=2.0).text.strip()
		except: user_ip = ''
		if user_ip: params['user_ip'] = user_ip
		return self.api('get', path, params=params)

	def check_cache(self, hashes):
		path = '/v1/api/torrents/checkcached?format=list'
		data = {'hashes': hashes}
		result = self.api('post', path, json=data)
		return [i['hash'] for i in result]

	def create_transfer(self, link, name=''):
		if link.startswith('magnet'): key, result = 'torrent_id', self.add_magnet(link)
		else: key, result = 'usenetdownload_id', self.add_nzb(link, name)
		return result.get(key, '')

	def add_magnet(self, magnet):
		path = '/v1/api/torrents/createtorrent'
		data = {'magnet': magnet, 'seed': 3, 'allow_zip': 'false'}
		return self.api('post', path, data=data)

	def add_nzb(self, nzb, name=''):
		path = '/v1/api/usenet/createusenetdownload'
		data = {'link': nzb}
		if name: data['name'] = name
		return self.api('post', path, data=data)

	def parse_magnet_pack(self, magnet_url, info_hash):
		from modules.source_utils import supported_video_extensions
		try:
			extensions = tuple(supported_video_extensions())
			path = 'torrents' if magnet_url.startswith('magnet') else 'usenet'
			torrent_id = self.create_transfer(magnet_url)
			torrent_files = self.torrent_info(torrent_id, path)
			return [
				{'link': '%s,%s,%s' % (torrent_id, item['id'], path),
				 'size': item['size'],
				 'torrent_id': '%s,%s' % (torrent_id, path),
				 'filename': item['short_name']}
				for item in torrent_files['files']
				if item['short_name'].lower().endswith(extensions)
			]
		except Exception as e:
			if torrent_id: self.delete_torrent('%s,%s' % (torrent_id, path))

	def clear_cache(*args):
		from modules.kodi_utils import clear_property, path_exists, database_connect, maincache_db
		try:
			if not path_exists(maincache_db): return True
			from caches.debrid_cache import DebridCache
			dbcon = database_connect(maincache_db)
			dbcur = dbcon.cursor()
			# USER CLOUD
			try:
				dbcur.execute("""SELECT id FROM maincache WHERE id LIKE ?""", ('pov_tb_user_cloud%',))
				user_cloud_cache = [str(i[0]) for i in dbcur.fetchall()]
				if user_cloud_cache:
					for i in user_cloud_cache: clear_property(i)
					dbcur.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('pov_tb_user_cloud%',))
					dbcon.commit()
				user_cloud_success = True
			except: user_cloud_success = False
			dbcon.close()
			# HASH CACHED STATUS
			try:
				DebridCache().delete_cache_single('tb')
				hash_cache_status_success = True
			except: hash_cache_status_success = False
		except: return False
		return all((user_cloud_success, hash_cache_status_success))

