from magneto.modules.client import randomagent
from modules import kodi_utils
from session import session, HTTPAdapter, Retry
# logger = kodi_utils.logger

base_url = 'https://app.real-debrid.com'
timeout, check_timeout = 10, (3.05, 6.05)
retry = Retry(total=None, status=1, status_forcelist=(429,), backoff_factor=1)
session.mount(base_url, HTTPAdapter(max_retries=retry))
user_agent = randomagent()

def tio_check_cache(unchecked_hashes_chunk, imdb, season, episode, collector):
	import re, secrets
	pattern = re.compile(r'\b\w{40}\b')
	headers = {'User-Agent': user_agent}
	path = 'realdebrid=%s' % str.upper(secrets.token_urlsafe(39)[:52])
	if str(season).isdigit(): params = 'series/%s:%s:%s.json' % (imdb, season, episode)
	else: params = 'movie/%s.json' % (imdb)
	url = 'https://torrentio.strem.fun/debridoptions=nodownloadlinks,nocatalog|%s/stream/%s' % (path, params)
	try:
		response = session.request('get', url, headers=headers, timeout=check_timeout)
		if not response.ok: raise Exception(response.reason)
		files = response.json()['streams']
		collector.extend(pattern.findall(file['url'])[-1] for file in files if '+' in file['name'] and 'url' in file)
	except Exception as e: kodi_utils.logger('tio error', str(e))

def dmm_check_cache(unchecked_hashes_chunk, imdb, season, episode, collector):
	""" DMM API allows max 100 hashes per request, do not thread multiple calls, 100 sample size should be enough """
	unchecked_hashes_chunk = [i for i in unchecked_hashes_chunk if len(i) == 40]
	if len(unchecked_hashes_chunk) > 100:
		unchecked_hashes_chunk = __import__('random').sample(unchecked_hashes_chunk, 100)
	data = {'hashes': unchecked_hashes_chunk, 'imdbId': imdb}
	headers = {'User-Agent': user_agent}
	headers['Referer'] = '%s/%s/%s' % ('https://debridmediamanager.com', 'show' if season else 'movie', imdb)
	url = 'https://debridmediamanager.com/api/challenge', 'https://debridmediamanager.com/api/availability/check'
	try:
		get_secret = session.request('get', url[0], headers=headers, timeout=check_timeout[0]).json()
		data['dmmProblemKey'], data['solution'] = get_secret['token'], get_secret['hash']
		response = session.request('post', url[1], json=data, headers=headers, timeout=check_timeout)
		if not response.ok: raise Exception(response.reason)
		files = response.json()['available']
		collector.extend(file['hash'] for file in files if 'hash' in file)
	except Exception as e: kodi_utils.logger('dmm error', str(e))

class RealDebridAPI:
	icon = 'realdebrid.png'
	defaults_to_cloud = True

	def __init__(self):
		self.timeout = int(kodi_utils.get_setting('scrapers_timeout') or 10)
		self.token = kodi_utils.get_setting('rd.token')

	def api(self, method, path, **kwargs):
		headers = self.headers()
		try: response = session.request(method, base_url + path, **kwargs, headers=headers, timeout=self.timeout)
		except session.CUSTOM_ERRORS: return kodi_utils.notification('timeout: %s' % __name__)
		if response.status_code in (401,) and self.refresh_token() is True:
			response.request.headers['Authorization'] = 'Bearer %s' % self.token
			response = session.send(response.request, timeout=self.timeout)
		if not response.ok: kodi_utils.logger('', f"{__name__}, {response.reason}\n{response.url}")
		if bool(response.content) and 'json' in response.headers.get('Content-Type', ''):
			return response.json()
		return response

	def headers(self):
		return {'Authorization': 'Bearer %s' % self.token}

	def refresh_token(self):
		try:
			data = {'grant_type': 'http://oauth.net/grant_type/device/1.0'}
			data['code'] = kodi_utils.get_setting('rd.refresh')
			data['client_secret'] = kodi_utils.get_setting('rd.secret')
			data['client_id'] = kodi_utils.get_setting('rd.client_id')
			url = 'https://app.real-debrid.com/oauth/v2/token'
			response = session.request('post', url, data=data, timeout=timeout).json()
			token, refresh = response['access_token'], response['refresh_token']
			self.token = token
			kodi_utils.set_setting('rd.token', self.token)
			kodi_utils.set_setting('rd.refresh', refresh)
		except Exception as e: kodi_utils.logger('refresh_token error', str(e))
		else: return True
		return False

	def days_remaining(self):
		from datetime import datetime
		try:
			account_info = self.account_info()
			expires = datetime.fromisoformat(account_info['expiration'].replace('Z', '+00:00'))
			days = (expires.astimezone().date() - datetime.today().date()).days
		except: days = None
		return days

	def account_info(self):
		path = '/rest/1.0/user'
		return self.api('get', path)

	def downloads(self):
		path = '/rest/1.0/downloads?limit=500'
		return self.api('get', path)

	def user_cloud(self):
		path = '/rest/1.0/torrents?limit=500'
		return self.api('get', path)

	def user_folder(self, folder_id):
		return self.torrent_info(folder_id)

	def torrent_info(self, folder_id):
		path = '/rest/1.0/torrents/info/%s' % folder_id
		return self.api('get', path)

	def delete_torrent(self, folder_id):
		path = '/rest/1.0/torrents/delete/%s' % folder_id
		result = self.api('delete', path)
		return True if result is not None and result.ok else False

	def delete_download(self, download_id):
		path = '/rest/1.0/downloads/delete/%s' % download_id
		result = self.api('delete', path)
		return True if result is not None and result.ok else False

	def unrestrict_link(self, link):
		path = '/rest/1.0/unrestrict/link'
		data = {'link': link}
		result = self.api('post', path, data=data)
		if not result or 'download' not in result: return None
		if result['download'].lower().endswith(('.rar','.zip')):
			raise Exception('link error\n%s' % result['download'])
		return result['download']

	def check_cache(self, hashes):
		hash_string = '/'.join(hashes)
		path = '/rest/1.0/torrents/instantAvailability/%s' % hash_string
		return self.api('get', path)

	def create_transfer(self, magnet):
		path = '/rest/1.0/torrents/addMagnet'
		data = {'magnet': magnet}
		result = self.api('post', path, data=data)
		if not result or 'id' not in result: return ''
		self.add_torrent_select(result['id'], 'all')
		return result['id']

	def add_torrent_select(self, torrent_id, file_ids):
		path = '/rest/1.0/torrents/selectFiles/%s' % torrent_id
		data = {'files': file_ids}
		return self.api('post', path, data=data)

	def parse_magnet_pack(self, magnet_url, info_hash, errors=False):
		from modules.source_utils import supported_video_extensions
		try:
			extensions = tuple(supported_video_extensions())
			torrent_id = self.create_transfer(magnet_url)
			if not torrent_id: raise Exception('real debrid null magnet')
			for key in ['ended'] * 3:
				kodi_utils.sleep(500)
				torrent_info = self.torrent_info(torrent_id)
				if key in torrent_info: break
			else: raise Exception('real debrid uncached magnet')
			selected = (i for i in torrent_info['files'] if i['selected'])
			return [
				{'link': link,
				 'size': item['bytes'],
				 'torrent_id': torrent_id,
				 'filename': item['path'].replace('/', '')}
				for item, link in zip(selected, torrent_info['links'])
				if item['path'].lower().endswith(extensions)
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
				dbcur.execute("""SELECT id FROM maincache WHERE id LIKE ?""", ('pov_rd_user_cloud%',))
				user_cloud_cache = [str(i[0]) for i in dbcur.fetchall()]
				if user_cloud_cache:
					for i in user_cloud_cache: clear_property(i)
					dbcur.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('pov_rd_user_cloud%',))
					dbcon.commit()
				user_cloud_success = True
			except: user_cloud_success = False
			# DOWNLOAD LINKS
			try:
				clear_property('pov_rd_downloads')
				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_rd_downloads',))
				dbcon.commit()
				download_links_success = True
			except: download_links_success = False
			# HOSTERS
			try:
				clear_property('pov_rd_valid_hosts')
				dbcur.execute("""DELETE FROM maincache WHERE id = ?""", ('pov_rd_valid_hosts',))
				dbcon.commit()
				hoster_links_success = True
			except: hoster_links_success = False
			dbcon.close()
			# HASH CACHED STATUS
			try:
				DebridCache().delete_cache_single('rd')
				hash_cache_status_success = True
			except: hash_cache_status_success = False
		except: return False
		return all((user_cloud_success, download_links_success, hoster_links_success, hash_cache_status_success))

