import re
from modules import kodi_utils
from session import session, HTTPAdapter, Retry
# logger = kodi_utils.logger

base_url = 'https://offcloud.com'
timeout = 10
retry = Retry(total=None, status=1, status_forcelist=(429,), backoff_factor=1)
session.mount(base_url, HTTPAdapter(max_retries=retry))

class OffcloudAPI:
	icon = 'offcloud.png'
	defaults_to_cloud = False

	def __init__(self):
		self.timeout = int(kodi_utils.get_setting('scrapers_timeout') or 10)
		self.token = kodi_utils.get_setting('oc.token')

	def api(self, method, path, **kwargs):
		headers = self.headers()
		try: response = session.request(method, base_url + path, **kwargs, headers=headers, timeout=self.timeout)
		except session.CUSTOM_ERRORS: return kodi_utils.notification('timeout: %s' % __name__)
		if not response.ok: kodi_utils.logger('', f"{__name__}, {response.reason}\n{response.url}")
		if bool(response.content) and 'json' in response.headers.get('Content-Type', ''):
			return response.json()
		return response.text

	def headers(self):
		return {'Authorization': 'Bearer %s' % self.token}

	def days_remaining(self):
		from datetime import date
		try:
			account_info = self.account_info()
			expires = date.fromisoformat(account_info['expiration_date'])
			days = (expires - date.today()).days
		except: days = None
		return days

	def account_info(self):
		path = '/api/account/info'
		return self.api('get', path)

	def user_cloud(self):
		path = '/api/cloud/history'
		return self.api('get', path)

	def user_folder(self, folder_id):
		return self.torrent_info(folder_id)

	def torrent_info(self, request_id):
		path = '/api/cloud/explore/%s' % request_id
		params = {'format': 'detailed'}
		return self.api('get', path, params=params)

	def delete_torrent(self, request_id):
		path = '/api/cloud/remove/%s' % request_id
		result = self.api('get', path)
		return True if result is not None and result['success'] else False

	def unrestrict_link(self, link):
		return link

	def check_cache(self, hashes):
		pattern = re.compile(r'^[a-f0-9]{40}$', re.I)
		hashes = [(i, f"magnet:?xt=urn:btih:{i}") for i in hashes if pattern.match(i)]
		path = '/api/cache/info'
		data = {'urls': [i[1] for i in hashes]}
		result = self.api('post', path, json=data)
		return [h for h, i in zip((i[0] for i in hashes), result) if i['cached']]

	def instant_transfer(self, magnet):
		path = '/api/cache/download'
		data = {'url': magnet}
		return self.api('post', path, json=data)

	def create_transfer(self, magnet):
		path = '/api/cloud'
		data = {'url': magnet}
		result = self.api('post', path, json=data)
		return result.get('requestId', '')

	def parse_magnet_pack(self, magnet_url, info_hash):
		from modules.source_utils import supported_video_extensions
		try:
			extensions = tuple(supported_video_extensions())
			torrent_files = self.instant_transfer(magnet_url)
			return [
				{'link': item['url'],
				 'size': item['size'],
				 'filename': item['filename']}
				for item in torrent_files
				if item['filename'].lower().endswith(extensions)
			]
		except: pass

	def clear_cache(*args):
		from modules.kodi_utils import clear_property, path_exists, database_connect, maincache_db
		try:
			if not path_exists(maincache_db): return True
			from caches.debrid_cache import DebridCache
			dbcon = database_connect(maincache_db)
			dbcur = dbcon.cursor()
			# USER CLOUD
			try:
				dbcur.execute("""SELECT id FROM maincache WHERE id LIKE ?""", ('pov_oc_user_cloud%',))
				user_cloud_cache = [str(i[0]) for i in dbcur.fetchall()]
				if user_cloud_cache:
					for i in user_cloud_cache: clear_property(i)
					dbcur.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('pov_oc_user_cloud%',))
					dbcon.commit()
				user_cloud_success = True
			except: user_cloud_success = False
			dbcon.close()
			# HASH CACHED STATUS
			try:
				DebridCache().delete_cache_single('oc')
				hash_cache_status_success = True
			except: hash_cache_status_success = False
		except: return False
		return all((user_cloud_success, hash_cache_status_success))

