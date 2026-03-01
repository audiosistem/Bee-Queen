import requests
from modules import kodi_utils
# logger = kodi_utils.logger

ls, get_setting = kodi_utils.local_string, kodi_utils.get_setting
ip_url = 'https://api.ipify.org'
base_url = 'https://easydebrid.com/api/v1/'
timeout = 10.0
session = requests.Session()
session.custom_errors = requests.exceptions.ConnectionError, requests.exceptions.Timeout
session.mount('https://easydebrid.com', requests.adapters.HTTPAdapter(max_retries=1))

class EasyDebridAPI:
	icon = 'easydebrid.png'

	def __init__(self):
		self.token = get_setting('ed.token')
		session.headers.update(self.headers())

	def _request(self, method, path, params=None, json=None, data=None):
		url = base_url + path
		try: response = session.request(method, url, params=params, json=json, data=data, timeout=timeout)
		except session.custom_errors: return kodi_utils.notification('%s timeout' % __name__)
		if not response.ok: kodi_utils.logger(__name__, f"{response.reason}\n{response.url}")
		return response.json() if 'json' in response.headers.get('Content-Type', '') else response

	def _get(self, url, params=None):
		return self._request('get', url, params=params)

	def _post(self, url, params=None, json=None, data=None):
		return self._request('post', url, params=params, json=json, data=data)

	def headers(self):
		return {'Authorization': 'Bearer %s' % self.token}

	def account_info(self):
		url = 'user/details'
		result = self._get(url)
		return result

	def unrestrict_link(self, link):
		return link

	def check_cache(self, hashes):
		url = 'link/lookup'
		data = {'urls': hashes}
		result = self._post(url, json=data)
		return [h for h, cached in zip(hashes, result['cached']) if cached]

	def instant_transfer(self, magnet):
		try: user_ip = requests.get(ip_url, timeout=2.0).text
		except: user_ip = ''
		if user_ip: session.headers['X-Forwarded-For'] = user_ip
		url = 'link/generate'
		data = {'url': magnet}
		result = self._post(url, json=data)
		return result

	def create_transfer(self, magnet):
		data = {'url': magnet}
		url = 'link/request'
		result = self._post(url, json=data)
		return result.get('success', '')

	def parse_magnet_pack(self, magnet_url, info_hash):
		from modules.source_utils import supported_video_extensions
		try:
			extensions = supported_video_extensions()
			torrent_files = self.instant_transfer(magnet_url)
			return [
				{'link': item['url'],
				 'size': item['size'],
				 'filename': item['filename']}
				for item in torrent_files['files']
				if item['filename'].lower().endswith(tuple(extensions))
			]
		except: pass

	def clear_cache(*args):
		from modules.kodi_utils import clear_property, path_exists, database_connect, maincache_db
		try:
#			if not path_exists(maincache_db): return True
			from caches.debrid_cache import DebridCache
#			dbcon = database_connect(maincache_db)
#			dbcur = dbcon.cursor()
			# USER CLOUD
			try:
#				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_ed_user_cloud',))
				clear_property('pov_ed_user_cloud')
#				dbcon.commit()
				user_cloud_success = True
			except: user_cloud_success = False
#			dbcon.close()
			# HASH CACHED STATUS
			try:
				DebridCache().clear_debrid_results('ed')
				hash_cache_status_success = True
			except: hash_cache_status_success = False
		except: return False
		if False in (user_cloud_success, hash_cache_status_success): return False
		return True

