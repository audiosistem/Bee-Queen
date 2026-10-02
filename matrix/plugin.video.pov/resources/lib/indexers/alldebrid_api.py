from modules import kodi_utils
from session import session, HTTPAdapter, Retry
# logger = kodi_utils.logger

base_url = 'https://api.alldebrid.com'
timeout, check_timeout = 10, (3.05, 6.05)
retry = Retry(total=None, status=1, status_forcelist=(429,), backoff_factor=1)
session.mount(base_url, HTTPAdapter(max_retries=retry))

def aio_check_cache(imdb, season, episode):
	headers, url = {'x-aiostreams-user-data': (
		'ewogICJzZXJ2aWNlcyI6IFsKICAgIHsKICAgICAgImlkIjogImFsbGRlYnJpZCIsCiAgICAgICJlbmFi'
		'bGVkIjogdHJ1ZSwKICAgICAgImNyZWRlbnRpYWxzIjogeyJhcGlLZXkiOiAic3RhdGljRGVtb0FwaWtl'
		'eVByZW0ifQogICAgfQogIF0sCiAgInByZXNldHMiOiBbCiAgICB7CiAgICAgICJ0eXBlIjogIm1lZGlh'
		'ZnVzaW9uIiwKICAgICAgImluc3RhbmNlSWQiOiAiNWI4IiwKICAgICAgImVuYWJsZWQiOiB0cnVlLAog'
		'ICAgICAib3B0aW9ucyI6IHsKICAgICAgICAibmFtZSI6ICJNZWRpYUZ1c2lvbiIsCiAgICAgICAgInRp'
		'bWVvdXQiOiA2NTAwLAogICAgICAgICJyZXNvdXJjZXMiOiBbInN0cmVhbSJdLAogICAgICAgICJ1c2VD'
		'YWNoZWRSZXN1bHRzT25seSI6IHRydWUsCiAgICAgICAgImVuYWJsZVdhdGNobGlzdENhdGFsb2dzIjog'
		'ZmFsc2UsCiAgICAgICAgImRvd25sb2FkVmlhQnJvd3NlciI6IGZhbHNlLAogICAgICAgICJjb250cmli'
		'dXRvclN0cmVhbXMiOiBmYWxzZSwKICAgICAgICAiY2VydGlmaWNhdGlvbkxldmVsc0ZpbHRlciI6IFtd'
		'LAogICAgICAgICJudWRpdHlGaWx0ZXIiOiBbXSwKICAgICAgICAibWVkaWFUeXBlcyI6IFtdCiAgICAg'
		'IH0KICAgIH0sCiAgICB7CiAgICAgICJ0eXBlIjogInN0cmVtdGhydVRvcnoiLAogICAgICAiaW5zdGFu'
		'Y2VJZCI6ICI1NDgiLAogICAgICAiZW5hYmxlZCI6IHRydWUsCiAgICAgICJvcHRpb25zIjogewogICAg'
		'ICAgICJuYW1lIjogIlN0cmVtVGhydSBUb3J6IiwKICAgICAgICAidGltZW91dCI6IDY1MDAsCiAgICAg'
		'ICAgInJlc291cmNlcyI6IFsic3RyZWFtIl0sCiAgICAgICAgIm1lZGlhVHlwZXMiOiBbXSwKICAgICAg'
		'ICAiaW5jbHVkZVAyUCI6IGZhbHNlLAogICAgICAgICJ1c2VNdWx0aXBsZUluc3RhbmNlcyI6IGZhbHNl'
		'CiAgICAgIH0KICAgIH0KICBdLAogICJmb3JtYXR0ZXIiOiB7CiAgICAiaWQiOiAidG9ycmVudGlvIiwK'
		'ICAgICJkZWZpbml0aW9uIjogewogICAgICAibmFtZSI6ICIiLAogICAgICAiZGVzY3JpcHRpb24iOiAi'
		'IgogICAgfQogIH0sCiAgInNvcnRDcml0ZXJpYSI6IHsKICAgICJnbG9iYWwiOiBbXQogIH0sCiAgImRl'
		'ZHVwbGljYXRvciI6IHsKICAgICJlbmFibGVkIjogZmFsc2UsCiAgICAia2V5cyI6IFsiaW5mb0hhc2gi'
		'XSwKICAgICJtdWx0aUdyb3VwQmVoYXZpb3VyIjogImFnZ3Jlc3NpdmUiLAogICAgImNhY2hlZCI6ICJz'
		'aW5nbGVfcmVzdWx0IiwKICAgICJ1bmNhY2hlZCI6ICJwZXJfc2VydmljZSIsCiAgICAicDJwIjogInNp'
		'bmdsZV9yZXN1bHQiLAogICAgImV4Y2x1ZGVBZGRvbnMiOiBbXQogIH0sCiAgImV4Y2x1ZGVVbmNhY2hl'
		'ZCI6IHRydWUKfQ=='
	)}, 'https://aiostreams.fortheweak.cloud/api/v1/search'
	if str(season).isdigit(): params = {'type': 'series', 'id': '%s:%s:%s' % (imdb, season, episode)}
	else: params = {'type': 'movie', 'id': '%s' % imdb}
	try:
		response = session.request('get', url, params=params, headers=headers, timeout=check_timeout)
		if not response.ok: raise Exception(response.reason)
		files = response.json()['data']['results']
		return [file['infoHash'] for file in files if file['cached'] and file.get('infoHash')]
	except Exception as e: kodi_utils.logger('aio error', str(e))

class AllDebridAPI:
	icon = 'alldebrid.png'
	defaults_to_cloud = True

	@staticmethod
	def flatten_magnet_files(files_list):
		def flatten(items):
			for i in items:
				if not isinstance(i, dict): continue
				if 'e' in i: flatten(i['e'])
				else: files_append(i)
		files = []
		files_append = files.append
		flatten(files_list)
		return files

	def __init__(self):
		self.timeout = int(kodi_utils.get_setting('scrapers_timeout') or 10)
		self.token = kodi_utils.get_setting('ad.token')

	def api(self, method, path, **kwargs):
		headers = self.headers()
		try: response = session.request(method, base_url + path, **kwargs, headers=headers, timeout=self.timeout)
		except session.CUSTOM_ERRORS: return kodi_utils.notification('timeout: %s' % __name__)
		if not response.ok: kodi_utils.logger('', f"{__name__}, {response.reason}\n{response.url}")
		if bool(response.content) and 'json' in response.headers.get('Content-Type', ''):
			return self._parse(response)
		return response.text

	def _parse(self, response):
		response = response.json()
		if 'data' in response and response.get('status') == 'success': return response['data']
		return response

	def headers(self):
		return {'Authorization': 'Bearer %s' % self.token}

	def days_remaining(self):
		from datetime import datetime, timezone
		try:
			account_info = self.account_info()['user']
			expires = datetime.fromtimestamp(account_info['premiumUntil'], tz=timezone.utc)
			days = (expires - datetime.now(timezone.utc)).days
		except: days = None
		return days

	def account_info(self):
		path = '/v4/user'
		return self.api('get', path)

	def downloads(self):
		path = '/v4/user/history'
		return self.api('get', path)

	def user_cloud(self):
		path = '/v4.1/magnet/status'
		return self.api('get', path)

	def user_folder(self, folder_id):
		return self.torrent_info(folder_id)

	def torrent_info(self, transfer_id):
		path = '/v4.1/magnet/status'
		params = {'id': transfer_id}
		result = self.api('get', path, params=params)
		return result['magnets']

	def delete_torrent(self, transfer_id):
		path = '/v4/magnet/delete'
		params = {'id': transfer_id}
		result = self.api('get', path, params=params)
		return True if result is not None and 'error' not in result else False

	def unrestrict_link(self, link):
		path = '/v4/link/unlock'
		params = {'link': link}
		result = self.api('get', path, params=params)
		return result['link']

	def check_cache(self, hashes):
		path = '/v4/magnet/instant'
		data = [('magnets[]', h) for h in hashes]
		return self.api('post', path, data=data)

	def create_transfer(self, magnet):
		path = '/v4/magnet/upload'
		params = {'magnet': magnet}
		result = self.api('get', path, params=params)
		result = result['magnets'][0]
		return result.get('id', '')

	def parse_magnet_pack(self, magnet_url, info_hash, errors=False):
		from modules.source_utils import supported_video_extensions
		try:
			extensions = tuple(supported_video_extensions())
			torrent_id = self.create_transfer(magnet_url)
			for key in ['completionDate'] * 3:
				kodi_utils.sleep(500)
				torrent_info = self.torrent_info(torrent_id)
				if torrent_info[key]: break
			else: raise Exception('alldebrid uncached magnet')
			torrent_info['links'] = self.flatten_magnet_files(torrent_info['files'])
			return [
				{'link': item['l'],
				 'size': item['s'],
				 'torrent_id': torrent_id,
				 'filename': item['n']}
				for item in torrent_info['links']
				if item['n'].lower().endswith(extensions)
			]
		except Exception as e:
			if torrent_id: self.delete_torrent(torrent_id)
			if errors: raise

	def clear_cache(*args):
		from modules.kodi_utils import clear_property, path_exists, database_connect, maincache_db
		try:
			if not path_exists(maincache_db): return True
			from caches.debrid_cache import DebridCache
			dbcon = database_connect(maincache_db)
			dbcur = dbcon.cursor()
			# USER CLOUD
			try:
				dbcur.execute("""SELECT id FROM maincache WHERE id LIKE ?""", ('pov_ad_user_cloud%',))
				user_cloud_cache = [str(i[0]) for i in dbcur.fetchall()]
				if user_cloud_cache:
					for i in user_cloud_cache: clear_property(i)
					dbcur.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('pov_ad_user_cloud%',))
					dbcon.commit()
				user_cloud_success = True
			except: user_cloud_success = False
			# DOWNLOAD LINKS
			try:
				clear_property('pov_ad_downloads')
				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_ad_downloads',))
				dbcon.commit()
				download_links_success = True
			except: download_links_success = False
			# HOSTERS
			try:
				clear_property('pov_ad_valid_hosts')
				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_ad_valid_hosts',))
				dbcon.commit()
				hoster_links_success = True
			except: hoster_links_success = False
			dbcon.close()
			# HASH CACHED STATUS
			try:
				DebridCache().delete_cache_single('ad')
				hash_cache_status_success = True
			except: hash_cache_status_success = False
		except: return False
		return all((user_cloud_success, download_links_success, hoster_links_success, hash_cache_status_success))

