from caches.main_cache import cache_object
from modules import kodi_utils
from session import session, HTTPAdapter, Retry
# logger = kodi_utils.logger

base_url = 'https://www.premiumize.me'
timeout = 10
retry = Retry(total=None, status=1, status_forcelist=(429,), backoff_factor=1)
session.mount(base_url, HTTPAdapter(max_retries=retry))

class PremiumizeAPI:
	icon = 'premiumize.png'
	defaults_to_cloud = False

	def __init__(self):
		self.timeout = int(kodi_utils.get_setting('scrapers_timeout') or 10)
		self.token = kodi_utils.get_setting('pm.token')

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
		from datetime import datetime, timezone
		try:
			account_info = self.account_info()
			expires = datetime.fromtimestamp(account_info['premium_until'], tz=timezone.utc)
			days = (expires - datetime.now(timezone.utc)).days
		except: days = None
		return days

	def account_info(self):
		path = '/api/account/info'
		return self.api('get', path)

	def downloads(self):
		path = '/api/transfer/list'
		return self.api('get', path)

	def user_cloud(self):
		path = '/api/folder/list'
		return self.api('get', path)

	def user_folder(self, folder_id):
		path = '/api/folder/list'
		params = {'id': folder_id}
		return self.api('get', path, params=params)

	def item_listall(self):
		path = '/api/item/listall'
		result = self.api('get', path)
		return result['files']

	def delete_torrent(self, transfer_id):
		return self.delete_object('transfer', transfer_id)

	def unrestrict_link(self, link):
		return link

	def check_cache(self, hashes):
		path = '/api/cache/check'
		data = [('items[]', h) for h in hashes]
		result = self.api('post', path, data=data)
		return [h for h, cached in zip(hashes, result['response']) if cached]

	def instant_transfer(self, magnet):
		path = '/api/transfer/directdl'
		data = {'src': magnet}
		return self.api('post', path, data=data)

	def create_transfer(self, magnet):
		path = '/api/transfer/create'
		data = {'src': magnet, 'folder_id': 0}
		result = self.api('post', path, data=data)
		return result.get('id', '')

	def rename_cache_item(self, file_type, file_id, new_name):
		if file_type == 'folder': path = '/api/folder/rename'
		else: path = '/api/item/rename'
		data = {'id': file_id , 'name': new_name}
		result = self.api('post', path, data=data)
		return True if result is not None and result['status'] == 'success' else False

	def delete_object(self, object_type, object_id):
		path = '/api/%s/delete' % object_type
		data = {'id': object_id}
		result = self.api('post', path, data=data)
		return True if result is not None and result['status'] == 'success' else False

	def get_item_details(self, item_id):
		string = 'pov_pm_item_details_%s' % item_id
		path = '/api/item/details'
		data = {'id': item_id}
		return cache_object(lambda p: self.api('post', p, data=data), string, path, 24)

	def parse_magnet_pack(self, magnet_url, info_hash):
		from modules.source_utils import supported_video_extensions
		try:
			extensions = tuple(supported_video_extensions())
			torrent_files = self.instant_transfer(magnet_url)
			return [
				{'link': item['link'],
				 'size': item['size'],
				 'filename': item['path'].split('/')[-1]}
				for item in torrent_files['content']
				if item['path'].lower().endswith(extensions)
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
				dbcur.execute("""SELECT id FROM maincache WHERE id LIKE ?""", ('pov_pm_user_cloud%',))
				user_cloud_cache = [str(i[0]) for i in dbcur.fetchall()]
				if user_cloud_cache:
					for i in user_cloud_cache: clear_property(i)
					dbcur.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('pov_pm_user_cloud%',))
					dbcon.commit()
				user_cloud_success = True
			except: user_cloud_success = False
			# DOWNLOAD LINKS
			try:
				clear_property('pov_pm_downloads')
				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_pm_downloads',))
				dbcon.commit()
				download_links_success = True
			except: download_links_success = False
			# HOSTERS
			try:
				clear_property('pov_pm_valid_hosts')
				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_pm_valid_hosts',))
				dbcon.commit()
				hoster_links_success = True
			except: hoster_links_success = False
			dbcon.close()
			# HASH CACHED STATUS
			try:
				DebridCache().delete_cache_single('pm')
				hash_cache_status_success = True
			except: hash_cache_status_success = False
		except: return False
		return all((user_cloud_success, download_links_success, hoster_links_success, hash_cache_status_success))

