# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

import re
import requests
from requests.adapters import HTTPAdapter
from sys import argv, exit as sysexit
from urllib3.util.retry import Retry
from urllib.parse import quote_plus, urlencode
from resources.lib.database import cache
from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.modules import string_tools
from resources.lib.modules.source_utils import supported_video_extensions

getLS = control.lang
getSetting = control.setting
CLIENT_ID = '784560195' # used to auth
BaseUrl = 'https://www.premiumize.me/api'
folder_list_url = '%s/folder/list' % BaseUrl
folder_rename_url = '%s/folder/rename' % BaseUrl
folder_delete_url = '%s/folder/delete' % BaseUrl
item_listall_url = '%s/item/listall' % BaseUrl
item_details_url = '%s/item/details' % BaseUrl
item_delete_url = '%s/item/delete' % BaseUrl
item_rename_url = '%s/item/rename' % BaseUrl
transfer_create_url = '%s/transfer/create' % BaseUrl
transfer_directdl_url = '%s/transfer/directdl' % BaseUrl
transfer_list_url = '%s/transfer/list' % BaseUrl
transfer_clearfinished_url = '%s/transfer/clearfinished' % BaseUrl
transfer_delete_url = '%s/transfer/delete' % BaseUrl
account_info_url = '%s/account/info' % BaseUrl
cache_check_url = '%s/cache/check' % BaseUrl
list_services_path_url = '%s/services/list' % BaseUrl
pm_icon = control.joinPath(control.artPath(), 'premiumize.png')
addonFanart = control.addonFanart()
invalid_extensions = ('.bmp', '.gif', '.jpg', '.nfo', '.part', '.png', '.rar', '.sample.', '.srt', '.txt', '.zip')
from resources.lib.modules.source_utils import is_archive_part  # v1.0.54: partes de archivos multivolumen (.z03, .r00, .001)

session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
session.mount('https://www.premiumize.me', HTTPAdapter(max_retries=retries, pool_maxsize=100))


class Premiumize:
	name = "Premiumize.me"
	sort_priority = getSetting('premiumize.priority')
	def __init__(self):
		self.hosts = []
		self.patterns = []
		self.token = getSetting('premiumize.token')
		self.headers = {'User-Agent': 'luc_kodi for Kodi', 'Authorization': 'Bearer %s' % self.token}
		self.server_notifications = getSetting('premiumize.server.notifications')
		self.store_to_cloud = getSetting('premiumize.saveToCloud') == 'true'

	def _get(self, url):
		response = None
		try:
			if self.token == '':
				log_utils.log('No Premiumize.me Token Found')
				return None
			response = session.get(url, headers=self.headers, timeout=15).json()
			# if response.status_code in (200, 201): response = response.json() # need status code checking for server maintenance
			if 'status' in response:
				if response.get('status') == 'success': return response
				if response.get('status') == 'error':
					if self.server_notifications: control.notification(message=response.get('message'), icon=pm_icon)
					log_utils.log('Premiumize.me: %s' % response.get('message'), level=log_utils.LOGWARNING)
		except: log_utils.error()
		return response

	def _post(self, url, data={}):
		response = None
		if self.token == '': return None
		try:
			response = session.post(url, data, headers=self.headers, timeout=45).json() # disgusting temp timeout change to fix server response lag
			# if response.status_code in (200, 201): response = response.json() # need status code checking for server maintenance
			if 'status' in response:
				if response.get('status') == 'success': return response
				if response.get('status') == 'error':
					if 'You already have this job added' in response.get('message'): return None
					if self.server_notifications: control.notification(message=response.get('message'), icon=pm_icon)
					log_utils.log('Premiumize.me: %s' % response.get('message'), level=log_utils.LOGWARNING)
		except: log_utils.error()
		return response

	def auth(self):
		data = {'client_id': CLIENT_ID, 'response_type': 'device_code'}
		token = session.post('https://www.premiumize.me/token', data=data, timeout=15).json()
		expiry = float(token['expires_in'])
		token_ttl = token['expires_in']
		verification_url = getLS(32513) % (control.getHighlightColor(), token['verification_uri'])
		user_code = getLS(32514) % (control.getHighlightColor(), token['user_code'])
		poll_again = True
		success = False
		try:
			qr_url = 'https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&data='
			qr_icon = qr_url + quote_plus(token['verification_uri'])
			control.notification(message=token['verification_uri'], icon=qr_icon, time=15000)
		except: pass
		line = '%s\n%s'
		progressDialog = control.progressDialog
		progressDialog.create(getLS(40054))
		progressDialog.update(100, line % (verification_url, user_code))
		while poll_again and not token_ttl <= 0 and not progressDialog.iscanceled():
			control.sleep(1000)
			token_ttl -= 1
			progressDialog.update(int(token_ttl / expiry * 100))
			if not token_ttl % token['interval']: poll_again, success = self.poll_token(token['device_code'])
		progressDialog.close()
		if success:
			control.notification(message=40052, icon=pm_icon)
			log_utils.log('Premiumize.me Successfully Authorized', level=log_utils.LOGDEBUG)
			try:
				from resources.lib.modules.debrid_state import sync_state
				sync_state()
			except Exception:
				pass

	def poll_token(self, device_code):
		data = {'client_id': CLIENT_ID, 'code': device_code, 'grant_type': 'device_code'}
		token = session.post('https://www.premiumize.me/token', data=data, timeout=15).json()
		if 'error' in token:
			if token['error'] == "access_denied":
				control.okDialog(title='default', message=getLS(40020))
				return False, False
			return True, False
		self.token = token['access_token']
		self.headers = {'User-Agent': 'luc_kodi for Kodi', 'Authorization': 'Bearer %s' % self.token}
		control.sleep(500)
		account_info = self.account_info()
		control.setSetting('premiumize.token', token['access_token'])
		control.setSetting('premiumize.username', str(account_info['customer_id']))
		try:
			from resources.lib.modules.debrid_state import sync_state
			sync_state()
		except Exception:
			pass
		return False, True

	def remove_auth(self):
		"""Local deauthorization.

		Premiumize does not provide a universal token revoke endpoint for the device
		code flow that is safe to call here. Clearing the stored token/username is
		sufficient to deauthorize luc_kodi.
		"""
		try:
			control.setSetting('premiumize.token', '')
			control.setSetting('premiumize.username', '')
			control.notification(message='Premiumize: Deauthorized', icon=pm_icon)
			log_utils.log('Premiumize.me Deauthorized (token cleared)', level=log_utils.LOGDEBUG)
			try:
				from resources.lib.modules.debrid_state import sync_state
				sync_state()
			except Exception:
				pass
			return True
		except:
			log_utils.error()
			return False

	def add_headers_to_url(self, url):
		return url + '|' + urlencode(self.headers)

	def account_info(self):
		try:
			accountInfo = self._get(account_info_url)
			return accountInfo
		except: log_utils.error()
		return None

	def account_info_to_dialog(self):
		from datetime import datetime
		import math
		try:
			accountInfo = self.account_info()
			expires = datetime.fromtimestamp(accountInfo['premium_until'])
			days_remaining = (expires - datetime.today()).days
			expires = expires.strftime("%A, %B %d, %Y")
			points_used = int(math.floor(float(accountInfo['space_used']) / 1073741824.0))
			space_used = float(int(accountInfo['space_used'])) / 1073741824
			percentage_used = str(round(float(accountInfo['limit_used']) * 100.0, 1))
			items = []
			items += [getLS(40040) % accountInfo['customer_id']]
			items += [getLS(40041) % expires]
			items += [getLS(40042) % days_remaining]
			items += [getLS(40043) % points_used]
			items += [getLS(40044) % space_used]
			items += [getLS(40045) % percentage_used]
			return control.selectDialog(items, 'Premiumize')
		except: log_utils.error()
		return

	def valid_url(self, host):
		try:
			self.hosts = self.get_hosts()
			if not self.hosts['Premiumize.me']: return False
			if any(host in item for item in self.hosts['Premiumize.me']): return True
			return False
		except: log_utils.error()

	def get_hosts(self):
		hosts_dict = {'Premiumize.me': []}
		hosts = []
		append = hosts.append
		try:
			result = cache.get(self._get, 168, list_services_path_url)
			for x in result['directdl']:
				for alias in result['aliases'][x]: append(alias)
			hosts_dict['Premiumize.me'] = list(set(hosts))
		except: log_utils.error()
		return hosts_dict

	def unrestrict_link(self, link):
		try:
			data = {'src': link}
			response = self._post(transfer_directdl_url, data)
			try: return self.add_headers_to_url(response['content'][0]['link'])
			except: return None
		except: log_utils.error()

	def resolve_magnet(self, magnet_url, info_hash, season, episode, ep_title):
		from resources.lib.modules.source_utils import seas_ep_filter, extras_filter
		try:
			failed_reason, file_url, correct_files = 'Unknown', None, []
			append = correct_files.append
			extensions = supported_video_extensions()
			extras_filtering_list = extras_filter()
			data = {'src': magnet_url}
			response = self._post(transfer_directdl_url, data)
			if not response: return log_utils.log('Premiumize.me: Error RESOLVE MAGNET "%s" : (Server Failed to respond)' % magnet_url, __name__, log_utils.LOGWARNING)
			if not 'status' in response or response['status'] != 'success': raise Exception()
			# valid_results = [i for i in response.get('content') if any(i.get('path').lower().endswith(x) for x in extensions) and not i.get('link', '') == '']
			valid_results = [i for i in response.get('content') if not any(i.get('path').lower().endswith(x) for x in invalid_extensions) and not is_archive_part(i.get('path')) and not i.get('link', '') == '']
			if not valid_results: failed_reason = 'No valid video extension found'
			if season:
				episode_title = re.sub(r'[^A-Za-z0-9-]+', '.', (ep_title or '').replace('\'', '')).lower()
				for item in valid_results:
					if '.m2ts' in str(item.get('path')):
						failed_reason = 'Can not resolve .m2ts season disk episode'
						continue
					if seas_ep_filter(season, episode, item['path'].split('/')[-1]):
						# log_utils.log('item[path].split(/)[-1]=%s' %  item['path'].split('/')[-1])
						append(item)
					else: failed_reason = 'no matching season/episode found'
					if len(correct_files) == 0: continue
					for i in correct_files:
						compare_link = seas_ep_filter(season, episode, i['path'], split=True)
						compare_link = re.sub(episode_title, '', compare_link)
						if not any(x in compare_link for x in extras_filtering_list):
							file_url = i['link']
							break
			else: file_url = max(valid_results, key=lambda x: int(x.get('size'))).get('link', None)
			if file_url:
				if self.store_to_cloud: self.create_transfer(magnet_url)
				return self.add_headers_to_url(file_url)
			else:
				log_utils.log('Premiumize.me: FAILED TO RESOLVE MAGNET "%s" : (%s)' % (magnet_url, failed_reason), __name__, log_utils.LOGWARNING)
		except: log_utils.error('Premiumize.me: Error RESOLVE MAGNET "%s" ' % magnet_url)

	@staticmethod
	def _nzb_name(nzb_bytes):
		"""Extrae el nombre de release de un .nzb (meta name o primer subject).
		Best-effort; devuelve '' si no lo encuentra."""
		try:
			text = nzb_bytes[:16384].decode('utf-8', 'replace')
			m = re.search(r'<meta[^>]*type="name"[^>]*>([^<]+)</meta>', text, re.I)
			if m:
				return m.group(1).strip()
			# primer subject: [1/50] - "Release.Name.part01.rar" yEnc  (quotes escapados o no)
			m = re.search(r'subject="[^"]*?&quot;([^&]+?)&quot;', text, re.I) \
				or re.search(r'subject=\'[^\']*?"([^"]+)"', text, re.I)
			if m:
				return re.sub(r'\.(part\d+|rar|nzb|\d{2,3})$', '', m.group(1).strip(), flags=re.I)
		except:
			pass
		return ''

	def _find_transfer_by_name(self, name):
		"""Localiza en la nube un transfer cuyo nombre case con 'name'
		(para el caso 'already added'). Prefiere finished/seeding."""
		if not name:
			return None
		target = re.sub(r'[^a-z0-9]+', '', name.lower())
		if not target:
			return None
		try:
			info = self.list_transfer()
			fallback = None
			for it in (info.get('transfers', []) if info else []):
				nm = re.sub(r'[^a-z0-9]+', '', (it.get('name', '') or '').lower())
				if nm and (nm == target or target in nm or nm in target):
					if it.get('status') in ('finished', 'seeding'):
						return it.get('id')
					fallback = it.get('id')
			return fallback
		except:
			log_utils.error()
			return None

	@staticmethod
	def cleanup_nzb_transfer():
		"""Auto-borrado: elimina de la nube de PM el ultimo NZB reproducido.
		Lo invoca el Player en onPlayBackStopped/Ended/Error. No-op si no hay
		nada pendiente (p.ej. la reproduccion no era un NZB de Premiumize)."""
		try:
			tid = control.homeWindow.getProperty('luc_kodi.pm_nzb_cleanup')
			if not tid:
				return
			control.homeWindow.clearProperty('luc_kodi.pm_nzb_cleanup')
			Premiumize().delete_transfer(tid)
			log_utils.log('Premiumize.me: auto-deleted NZB transfer %s from cloud' % tid, __name__, log_utils.LOGDEBUG)
		except:
			log_utils.error()

	def _fetch_nzb_bytes(self, nzb_url):
		"""Descarga el fichero .nzb desde el indexer (la URL ya lleva su apikey).
		Devuelve bytes o None. Valida que parezca un NZB y no un HTML de error."""
		try:
			r = session.get(nzb_url, headers={'User-Agent': 'luc_kodi for Kodi'}, timeout=30, allow_redirects=True)
			data = r.content or b''
			if not data:
				return None
			low = data[:2048].lower()
			if low.lstrip().startswith(b'<?xml') or b'<nzb' in low or b'<file' in low:
				return data
			log_utils.log('Premiumize.me: indexer did not return an NZB (first bytes: %r)' % data[:80], __name__, log_utils.LOGWARNING)
			return None
		except:
			log_utils.error()
			return None

	def _collect_folder_videos(self, folder_id, depth=0):
		"""Aplana los videos de una carpeta PM a [{'path','size','link'}]
		(una recursion de subcarpetas)."""
		out = []
		try:
			for it in (self.my_files(folder_id) or []):
				if it.get('type') == 'folder' and depth < 1:
					out += self._collect_folder_videos(it.get('id'), depth + 1)
				elif it.get('link'):
					out.append({'path': it.get('name', ''), 'size': it.get('size', 0), 'link': it.get('link')})
		except:
			log_utils.error()
		return out

	@staticmethod
	def _pm_total_bytes(message):
		"""Premiumize mete el tamano en su campo 'message', con el formato que
		ves en el panel web: "82% of 117894.00 MB. ETA is 0:04:22".
		De ahi sacamos el total para poder calcular velocidad real y ETA."""
		try:
			m = re.search(r'of\s+([\d.,]+)\s*(TB|GB|MB|KB)', message or '', re.I)
			if not m:
				return 0
			val = float(m.group(1).replace(',', ''))
			mult = {'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4}[m.group(2).upper()]
			return int(val * mult)
		except Exception:
			return 0

	@staticmethod
	def _fmt_size(nbytes):
		try:
			nbytes = float(nbytes or 0)
			for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
				if nbytes < 1024 or unit == 'TB':
					return '%.1f %s' % (nbytes, unit) if unit != 'B' else '%d B' % nbytes
				nbytes /= 1024.0
		except Exception:
			return '?'

	@staticmethod
	def _fmt_secs(secs):
		try:
			secs = int(secs)
			if secs < 0 or secs > 86400:
				return '--:--'
			h, rem = divmod(secs, 3600)
			m, sec = divmod(rem, 60)
			return '%d:%02d:%02d' % (h, m, sec) if h else '%d:%02d' % (m, sec)
		except Exception:
			return '--:--'

	def _pick_nzb_entry(self, entries, season, episode, ep_title):
		"""v1.0.62: identico a _pick_nzb_file pero devuelve la ENTRADA completa.
		Necesario para el fallback por nombre, donde /item/listall da id y
		nombre pero NO el link: hay que elegir primero y pedir el enlace
		despues con /item/details."""
		from resources.lib.modules.source_utils import seas_ep_filter, extras_filter
		extras_filtering_list = extras_filter()
		valid = [i for i in entries if (i.get('link') or i.get('id'))
			and not any(str(i.get('path', '')).lower().endswith(x) for x in invalid_extensions) and not is_archive_part(i.get('path', ''))]
		if not valid:
			return None
		if season:
			episode_title = re.sub(r'[^A-Za-z0-9-]+', '.', (ep_title or '').replace('\'', '')).lower()
			correct = []
			for item in valid:
				name = str(item.get('path', '')).split('/')[-1]
				if '.m2ts' in str(item.get('path', '')):
					continue
				if seas_ep_filter(season, episode, name):
					correct.append(item)
			for i in correct:
				compare = seas_ep_filter(season, episode, str(i.get('path', '')), split=True)
				compare = re.sub(episode_title, '', compare)
				if not any(x in compare for x in extras_filtering_list):
					return i
			# v1.0.62: si el filtro de episodio no casa con NINGUNO (nombres de
			# fichero que no repiten el SxxEyy, habitual en Usenet), no nos
			# rendimos: el NZB era de ESE episodio, asi que vale el video mas
			# grande. Antes se devolvia None y la reproduccion moria aqui.
			try:
				return max(valid, key=lambda x: int(x.get('size') or 0))
			except Exception:
				return valid[0]
		try:
			return max(valid, key=lambda x: int(x.get('size') or 0))
		except Exception:
			return valid[0]

	def _cloud_entries_by_name(self, release_name):
		"""v1.0.62: localiza en la nube los ficheros de un release por NOMBRE.
		Ultimo recurso cuando /transfer/list no trae file_id ni folder_id
		utilizables: /item/listall devuelve todo el arbol con id, nombre y
		tamano, y de ahi se saca el enlace con /item/details."""
		out = []
		try:
			target = re.sub(r'[^a-z0-9]+', '', (release_name or '').lower())
			if not target:
				return out
			for f in (self.my_files_all() or []):
				nm = f.get('name') or ''
				path = f.get('path') or nm
				key = re.sub(r'[^a-z0-9]+', '', str(path).lower())
				if not key:
					continue
				if target in key or key in target:
					out.append({'path': path, 'size': f.get('size') or 0,
						'id': f.get('id'), 'link': f.get('link') or ''})
		except Exception:
			log_utils.error()
		return out

	def _link_for_entry(self, entry):
		"""Devuelve el enlace de una entrada, pidiendolo a /item/details si hace
		falta."""
		try:
			if entry.get('link'):
				return entry['link']
			if entry.get('id'):
				details = self._get('%s?id=%s' % (item_details_url, entry['id']))
				if details and details.get('status') == 'success':
					return details.get('link')
		except Exception:
			log_utils.error()
		return None

	def _pick_nzb_file(self, entries, season, episode, ep_title):
		"""Selecciona el fichero correcto (misma logica que resolve_magnet):
		episodio exacto para series, mayor tamano para peliculas."""
		from resources.lib.modules.source_utils import seas_ep_filter, extras_filter
		extras_filtering_list = extras_filter()
		valid = [i for i in entries if i.get('link')
			and not any(str(i.get('path', '')).lower().endswith(x) for x in invalid_extensions) and not is_archive_part(i.get('path', ''))]
		if not valid:
			return None
		if season:
			episode_title = re.sub(r'[^A-Za-z0-9-]+', '.', (ep_title or '').replace('\'', '')).lower()
			correct = []
			for item in valid:
				name = str(item.get('path', '')).split('/')[-1]
				if '.m2ts' in str(item.get('path', '')):
					continue
				if seas_ep_filter(season, episode, name):
					correct.append(item)
			for i in correct:
				compare = seas_ep_filter(season, episode, str(i.get('path', '')), split=True)
				compare = re.sub(episode_title, '', compare)
				if not any(x in compare for x in extras_filtering_list):
					return i.get('link')
			return None
		try:
			return max(valid, key=lambda x: int(x.get('size') or 0)).get('link')
		except:
			return valid[0].get('link')

	def resolve_nzb(self, nzb_url, info_hash, season, episode, ep_title):
		"""Premiumize.me: resuelve un NZB (Usenet) a una URL directa reproducible.

		IMPORTANTE (asimetria con TorBox): la API de Premiumize NO tiene ruta
		instantanea para NZB. /transfer/directdl solo acepta magnets/torrents/
		hosters reconocidos (un NZB da "Unsupported link for direct download").
		El unico camino es /transfer/create SUBIENDO el fichero .nzb (multipart),
		que lo encola y lo descarga de Usenet en la nube de PM; luego se recoge
		el link del fichero. Por eso siempre hay una espera (PM baja de Usenet),
		a diferencia de TorBox que si sirve NZB cacheados al instante.

		Flujo: descargar .nzb del indexer -> POST /transfer/create (file=src)
		-> poll /transfer/list hasta finished/seeding -> item/details o
		folder/list -> seleccionar fichero -> add_headers_to_url(link).
		"""
		try:
			if self.token == '':
				return None

			# ── Concurrency mutex ─────────────────────────────────────────
			# Only ONE Premiumize NZB resolution may run at a time. playItem's
			# neighbour pre-cache and autoplay can otherwise fire many
			# resolve_nzb calls in parallel threads, and since EACH NZB call
			# starts a persistent server-side download (transfer/create), that
			# floods Premiumize's 25-active-transfer cap. Concurrent callers
			# bail immediately WITHOUT creating a transfer.
			if control.homeWindow.getProperty('luc_kodi.pm_nzb_busy') == 'true':
				log_utils.log('Premiumize.me: another NZB resolve is already running; skipping this one (no transfer created)', __name__, log_utils.LOGDEBUG)
				return None
			control.homeWindow.setProperty('luc_kodi.pm_nzb_busy', 'true')

			# 1) Descargar el .nzb del indexer (la URL ya incluye el apikey)
			nzb_bytes = self._fetch_nzb_bytes(nzb_url)
			if not nzb_bytes:
				if self.server_notifications:
					control.notification(message='Newznab: could not download the NZB from the indexer', icon=pm_icon)
				return log_utils.log('Premiumize.me: could not fetch NZB from "%s"' % nzb_url, __name__, log_utils.LOGWARNING)

			# 2) Subir el .nzb a /transfer/create (multipart, campo 'src').
			# El fichero se nombra con el release real (no "release.nzb") para
			# que el panel de PM sea legible y la deteccion "already added" case.
			release_name = self._nzb_name(nzb_bytes)
			_fname = re.sub(r'[^A-Za-z0-9._-]+', '.', (release_name or 'release')).strip('.') or 'release'
			created = None
			try:
				files = {'src': ('%s.nzb' % _fname, nzb_bytes, 'application/x-nzb')}
				_resp = session.post(transfer_create_url, files=files, headers=self.headers, timeout=60)
				# v1.0.60: Premiumize contesta "An unknown error occurred." sin mas
				# detalle cuando rechaza el NZB, y con eso no se puede diagnosticar
				# nada. Volcamos codigo HTTP, cabeceras utiles y cuerpo crudo para
				# que el log diga POR QUE lo rechaza.
				try:
					_body = (_resp.text or '')[:600]
				except Exception:
					_body = '<sin cuerpo>'
				log_utils.log(
					'Premiumize.me: transfer/create (NZB) HTTP %s | nzb=%d bytes | name="%s" | body=%s'
					% (_resp.status_code, len(nzb_bytes), _fname, _body),
					__name__, log_utils.LOGWARNING)
				created = _resp.json()
			except:
				log_utils.error()
				created = None

			transfer_id = None
			if created and created.get('status') == 'success' and created.get('id'):
				transfer_id = created['id']
			else:
				# v1.0.61: ANTES esta rama solo se probaba si el mensaje de error
				# contenia la palabra "already". Premiumize devuelve a menudo un
				# generico "An unknown error occurred." HABIENDO creado la
				# transferencia (o teniendola ya de un intento anterior), asi que
				# la busqueda por nombre no llegaba a ejecutarse: se devolvia None
				# y la transferencia quedaba HUERFANA descargando en la nube del
				# usuario, consumiendo cuota sin que nadie la reclamara.
				# Ahora se busca por nombre ante CUALQUIER fallo de create.
				transfer_id = self._find_transfer_by_name(release_name)
				if transfer_id:
					log_utils.log('Premiumize.me: transfer/create reported "%s" but a matching transfer exists in the cloud; reusing %s ("%s")'
						% ((created or {}).get('message', 'failure'), transfer_id, release_name), __name__, log_utils.LOGDEBUG)
			if not transfer_id:
				msg = (created or {}).get('message', 'server did not accept the NZB')
				if self.server_notifications:
					control.notification(message='Premiumize NZB: %s' % msg, icon=pm_icon)
				return log_utils.log('Premiumize.me: transfer/create (NZB) failed: %s' % msg, __name__, log_utils.LOGWARNING)

			# 3) Poll hasta finished/seeding (PM descarga de Usenet en su nube)
			def _info(tid):
				info = self.list_transfer()
				if info and info.get('status') == 'success':
					for it in info.get('transfers', []):
						if it.get('id') == tid:
							return it
				return {}
			transfer_info = _info(transfer_id)
			line1 = 'Premiumize is fetching the NZB from Usenet...'
			line2 = transfer_info.get('name', created.get('name', ''))
			try:
				control.progressDialog.create('Premiumize.me', '%s\n%s' % (line1, line2))
			except: pass
			cancelled, stalled, interval = False, False, 2
			status = transfer_info.get('status', '')
			import time as _t
			# Give-up guard: if Premiumize does not advance the download for a
			# sustained window, its Usenet backend isn't delivering (the classic
			# "stuck at 0%"). Abort gracefully instead of hanging forever.
			try: _stall_limit = int(getSetting('newznab.pm_stall_secs') or 180)
			except: _stall_limit = 180
			# v1.0.63 -- CUADRO INFORMATIVO REAL
			# Antes solo se veia el porcentaje entero y el texto crudo de
			# Premiumize, asi que un 0% no distinguia "bajando a 40 MB/s pero es
			# un fichero de 60 GB" de "el backend no arranca". Ahora se calcula
			# velocidad real y ETA a partir del avance observado.
			#
			# IMPORTANTE: aqui no se limita NADA. El addon no impone ningun tope
			# de velocidad: la descarga ocurre entre Usenet y la nube de
			# Premiumize, a lo que de su backend y tu plan. Lo unico que hacemos
			# es MEDIRLA y ensenarla. El sondeo cada 2 s no influye en el ritmo
			# de la transferencia, solo en cada cuanto se refresca el cuadro.
			_t0 = _t.time()
			_prog = 0.0            # progreso 0..1 en FLOAT (no el entero)
			_last_prog = -1.0
			_stall_since = _t0
			_samples = []          # (instante, bytes_hechos) para velocidad estable
			_total_bytes = 0
			_speed = 0.0
			while status not in ('finished', 'seeding', 'error'):
				control.sleep(1000 * interval)
				transfer_info = _info(transfer_id)
				status = transfer_info.get('status', '')
				_msg = transfer_info.get('message', '') or ''
				try: _prog = float(transfer_info.get('progress', 0) or 0)
				except: _prog = 0.0
				pct = int(_prog * 100)
				if not _total_bytes:
					_total_bytes = self._pm_total_bytes(_msg)

				# Deteccion de atasco sobre el FLOAT, no sobre el entero.
				# v1.0.63: con el entero, un remux de 60 GB necesita ~600 MB para
				# sumar 1 punto; si la conexion iba justa se superaban los 180 s
				# sin cambiar de numero y se abortaba una descarga que SI
				# avanzaba. Con el float cualquier avance real cuenta.
				if _prog > _last_prog:
					_last_prog = _prog
					_stall_since = _t.time()
				elif _stall_limit > 0 and (_t.time() - _stall_since) > _stall_limit:
					stalled = True
					break

				# Velocidad real sobre una ventana movil de ~20 s (mas estable
				# que dos muestras consecutivas, que dan saltos absurdos).
				_now = _t.time()
				if _total_bytes:
					_samples.append((_now, _prog * _total_bytes))
					_samples = [x for x in _samples if _now - x[0] <= 20]
					if len(_samples) >= 2:
						_dt = _samples[-1][0] - _samples[0][0]
						_db = _samples[-1][1] - _samples[0][1]
						if _dt > 0 and _db >= 0:
							_speed = _db / _dt

				# Linea de detalle: hecho / total, velocidad y tiempo restante.
				if _total_bytes:
					_done = int(_prog * _total_bytes)
					_detail = '%s de %s' % (self._fmt_size(_done), self._fmt_size(_total_bytes))
					if _speed > 0:
						_eta = (_total_bytes - _done) / _speed
						_detail += '  ·  %s/s  ·  quedan %s' % (self._fmt_size(_speed), self._fmt_secs(_eta))
					elif pct == 0:
						_detail += '  ·  esperando a que arranque'
				else:
					_detail = _msg or 'Premiumize aun no informa del tamano'
				_elapsed = 'transcurrido %s' % self._fmt_secs(_now - _t0)
				if _stall_limit > 0:
					_left = _stall_limit - (_now - _stall_since)
					if _left < 60:
						_elapsed += '  ·  sin avance, se abandona en %s' % self._fmt_secs(max(_left, 0))
				try:
					control.progressDialog.update(pct, '%s\n%s\n%s  ·  %s' % (line2, _detail, _elapsed, _msg[:60]))
					if control.progressDialog.iscanceled():
						cancelled = True
						break
				except: pass
				if control.monitor.abortRequested():
					cancelled = True
					break
			try: control.progressDialog.close()
			except: pass

			if cancelled:
				self.delete_transfer(transfer_id)
				return None
			if stalled:
				self.delete_transfer(transfer_id)
				if self.server_notifications:
					control.notification(message='Premiumize did not advance this Usenet download. The release may be incomplete or unavailable on its backend.', icon=pm_icon)
				return log_utils.log('Premiumize.me: NZB transfer stalled at %d%% for >%ds (Usenet backend not delivering); aborted and cleaned up (transfer %s)' % (max(_last_pct, 0), _stall_limit, transfer_id), __name__, log_utils.LOGWARNING)
			if status == 'error':
				self.delete_transfer(transfer_id)
				return log_utils.log('Premiumize.me: NZB transfer error: %s' % transfer_info.get('message', ''), __name__, log_utils.LOGWARNING)

			# 4) Recoger el fichero resultante (single-file: file_id; pack: folder_id)
			file_url = None
			file_id = transfer_info.get('file_id')
			folder_id = transfer_info.get('folder_id')
			if file_id and not season:
				details = self._get('%s?id=%s' % (item_details_url, file_id))
				if details and details.get('status') == 'success':
					file_url = details.get('link')
			if not file_url and folder_id:
				_entry = self._pick_nzb_entry(self._collect_folder_videos(folder_id), season, episode, ep_title)
				if _entry:
					file_url = self._link_for_entry(_entry)
			if not file_url and file_id:
				details = self._get('%s?id=%s' % (item_details_url, file_id))
				if details and details.get('status') == 'success':
					file_url = details.get('link')

			# v1.0.62 -- ULTIMO RECURSO: buscar el release por NOMBRE en la nube.
			# Observado en pruebas reales (5-ago-2026): la descarga terminaba
			# correctamente en ~3 min y aun asi salia "NZB finished but no
			# playable file found", porque /transfer/list no devolvia ni file_id
			# ni folder_id utilizables para ese transfer. El fichero SI estaba en
			# la nube, solo que no habia forma de llegar a el por id. /item/listall
			# da el arbol completo y de ahi se saca el enlace.
			if not file_url:
				_entries = self._cloud_entries_by_name(release_name)
				if _entries:
					_entry = self._pick_nzb_entry(_entries, season, episode, ep_title)
					if _entry:
						file_url = self._link_for_entry(_entry)
						if file_url:
							log_utils.log('Premiumize.me: recovered playable file by name lookup ("%s" -> "%s")'
								% (release_name, _entry.get('path')), __name__, log_utils.LOGDEBUG)

			if file_url:
				# Auto-borrado: dejar el id para que el Player lo elimine al terminar.
				if getSetting('newznab.pm_autodelete') != 'false':
					try: control.homeWindow.setProperty('luc_kodi.pm_nzb_cleanup', str(transfer_id))
					except: pass
				else:
					try: control.homeWindow.clearProperty('luc_kodi.pm_nzb_cleanup')
					except: pass
				return self.add_headers_to_url(file_url)
			# v1.0.62: volcar lo que Premiumize devolvio, para poder diagnosticar
			# en vez de adivinar (fue lo que resolvio el caso de transfer/create).
			try: _dump = {k: transfer_info.get(k) for k in ('id', 'name', 'status', 'file_id', 'folder_id', 'message', 'progress')}
			except Exception: _dump = transfer_info
			return log_utils.log(
				'Premiumize.me: NZB finished but no playable file found (transfer %s) | transfer_info=%s | name lookup returned %d entries'
				% (transfer_id, _dump, len(self._cloud_entries_by_name(release_name) or [])),
				__name__, log_utils.LOGWARNING)
		except:
			log_utils.error('Premiumize.me: Error RESOLVE NZB "%s" ' % nzb_url)
		finally:
			try: control.homeWindow.clearProperty('luc_kodi.pm_nzb_busy')
			except: pass

	def display_magnet_pack(self, magnet_url, info_hash):
		end_results = []
		try:
			append = end_results.append
			extensions = supported_video_extensions()
			data = {'src': magnet_url}
			result = self._post(transfer_directdl_url, data=data)
			if not result: return log_utils.log('Premiumize.me Error display_magnet_pack: %s : Server Failed to respond' % magnet_url)
			if not 'status' in result or result['status'] != 'success': raise Exception()
			for item in result.get('content'):
				if any(item.get('path').lower().endswith(x) for x in extensions) and not item.get('link', '') == '':
					try: path = item['path'].split('/')[-1]
					except: path = item['path']
					append({'link': item['link'], 'filename': path, 'size': float(item['size']) / 1073741824})
			return end_results
		except: log_utils.error('Premiumize.me Error display_magnet_pack: %s' % magnet_url, __name__, log_utils.LOGDEBUG)


	def add_uncached_torrent(self, magnet_url, pack=False):
		def _transfer_info(transfer_id):
			info = self.list_transfer()
			if 'status' in info and info['status'] == 'success':
				for item in info['transfers']:
					if item['id'] == transfer_id: return item
			return {}
		def _return_failed(message=getLS(33586)):
			try: control.progressDialog.close()
			except: pass
			self.delete_transfer(transfer_id)
			control.hide()
			control.sleep(500)
			control.okDialog(title=getLS(40018), message=message)
			return False
		control.busy()
		extensions = supported_video_extensions()
		transfer_id = self.create_transfer(magnet_url)
		if not transfer_id: return control.hide()
		if not transfer_id['status'] == 'success': return _return_failed()
		transfer_id = transfer_id['id']
		transfer_info = _transfer_info(transfer_id)
		if not transfer_info: return _return_failed()
		# if pack:
			# control.hide()
			# control.okDialog(title='default', message=getLS(40017) % getLS(40057))
			# return True
		interval = 5
		line = '%s\n%s\n%s'
		line1 = '%s...' % (getLS(40017) % getLS(40057))
		line2 = transfer_info['name']
		line3 = transfer_info['message']
		control.progressDialog.create(getLS(40018), line % (line1, line2, line3))
		while not transfer_info['status'] == 'seeding':
			control.sleep(1000 * interval)
			transfer_info = _transfer_info(transfer_id)
			line3 = transfer_info['message']
			control.progressDialog.update(int(float(transfer_info['progress']) * 100), line % (line1, line2, line3))
			if control.monitor.abortRequested(): return sysexit()
			try:
				if control.progressDialog.iscanceled():
					if control.yesnoDialog('Delete PM download also?', 'No will continue the download', 'but close dialog'):
						return _return_failed(getLS(40014))
					else:
						control.progressDialog.close()
						control.hide()
						return False
			except: pass
			if transfer_info.get('status') == 'stalled':
				return _return_failed()
		control.sleep(1000 * interval)
		try:
			control.progressDialog.close()
		except: log_utils.error()
		control.hide()
		return True

	def check_cache_item(self, media_id):
		try:
			media_id = media_id.encode('ascii', errors='ignore').decode('ascii', errors='ignore')
			media_id = media_id.replace(' ', '')
			url = '%s?items[]=%s' % (cache_check_url, media_id)
			result = session.get(url, headers=self.headers, timeout=15)
			if any(value in result.text for value in ('500', '502', '504')):
				log_utils.log('Premiumize.me Service Unavailable: %s' % result.text, __name__, log_utils.LOGDEBUG)
			else: result = result.json()
			if 'status' in result:
				if result.get('status') == 'success':
					response = result.get('response', False)
					if isinstance(response, list): return response[0]
				if result.get('status') == 'error':
					if self.server_notifications: control.notification(message=result.get('message'), icon=pm_icon)
					log_utils.log('Premiumize.me: %s' % result.get('message'), __name__, log_utils.LOGDEBUG)
		except: log_utils.error()
		return False

	def check_cache_list(self, hashList):
		try:
			postData = {'items[]': hashList}
			response = session.post(cache_check_url, data=postData, headers=self.headers, timeout=10)
			if any(value in response for value in ('500', '502', '504')):
				log_utils.log('Premiumize.me Service Unavailable: %s' % response, __name__, log_utils.LOGDEBUG)
			else: response = response.json()
			if 'status' in response:
				if response.get('status') == 'success':
					response = response.get('response', False)
					if isinstance(response, list): return response
		except: log_utils.error()
		return False

	def list_transfer(self):
		return self._get(transfer_list_url)

	def create_transfer(self, src,  folder_id=0):
		try:
			data = {'src': src, 'folder_id': folder_id}
			log_utils.log('Premiumize.me: Sending MAGNET to cloud: "%s" ' % src, __name__, log_utils.LOGDEBUG)
			return self._post(transfer_create_url, data)
		except: log_utils.error()

	def clear_finished_transfers(self):
		try:
			response = self._post(transfer_clearfinished_url)
			if not response: return
			if 'status' in response:
				if response.get('status') == 'success':
					log_utils.log('Finished transfers successfully cleared from the Premiumize.me cloud', __name__, log_utils.LOGDEBUG)
					control.refresh()
					return
		except: log_utils.error()
		return

	def delete_transfer(self, media_id, folder_name=None, silent=True):
		try:
			if not silent:
				if not control.yesnoDialog(getLS(40050) % '?\n' + folder_name, '', ''): return
			data = {'id': media_id}
			response = self._post(transfer_delete_url, data)
			if silent: return
			else:
				if response and response.get('status') == 'success':
					if self.server_notifications: control.notification(message='%s successfully deleted from the Premiumize.me cloud' % folder_name, icon=pm_icon)
					log_utils.log('%s successfully deleted from the Premiumize.me cloud' % folder_name, __name__, log_utils.LOGDEBUG)
					control.refresh()
					return
		except: log_utils.error()

	def my_files(self, folder_id=None):
		try:
			if folder_id: url = folder_list_url + '?id=%s' % folder_id
			else: url = folder_list_url
			response = self._get(url)
			if response: return response.get('content')
		except: log_utils.error()

	def my_files_all(self):
		try:
			response = self._get(item_listall_url)
			if response: return response.get('files')
		except: log_utils.error()

	def my_files_to_listItem(self, folder_id=None, folder_name=None):
		try:
			sysaddon, syshandle = 'plugin://plugin.video.luc_kodi/', int(argv[1])
			extensions = supported_video_extensions()
			cloud_files = self.my_files(folder_id)
			if not cloud_files:
				if self.server_notifications: control.notification(message='Request Failure-Empty Content', icon=pm_icon)
				log_utils.log('Premiumize.me: Request Failure-Empty Content', __name__, log_utils.LOGDEBUG)
				return
			cloud_files = [i for i in cloud_files if ('link' in i and i['link'].lower().endswith(tuple(extensions))) or i['type'] == 'folder']
			cloud_files = sorted(cloud_files, key=lambda k: k['name'])
			cloud_files = sorted(cloud_files, key=lambda k: k['type'], reverse=True)
		except: return log_utils.error()
		folder_str, file_str, downloadMenu, renameMenu, deleteMenu = getLS(40046).upper(), getLS(40047).upper(), getLS(40048), getLS(40049), getLS(40050)
		for count, item in enumerate(cloud_files, 1):
			try:
				cm = []
				content_type = item['type']
				name = string_tools.strip_non_ascii_and_unprintable(item['name'])
				if content_type == 'folder':
					isFolder = True
					size = 0
					label = '%02d | [B]%s[/B] | [I]%s [/I]' % (count, folder_str, name)
					url = '%s?action=pm_MyFiles&id=%s&name=%s' % (sysaddon, item['id'], quote_plus(name))
				else:
					isFolder = False
					url_link = item['link']
					if url_link.startswith('/'): url_link = 'https' + url_link
					size = item['size']
					display_size = float(int(size)) / 1073741824
					label = '%02d | [B]%s[/B] | %.2f GB | [I]%s [/I]' % (count, file_str, display_size, name)
					url = '%s?action=play_URL&url=%s' % (sysaddon, url_link)
					cm.append((downloadMenu, 'RunPlugin(%s?action=download&name=%s&image=%s&url=%s&caller=premiumize)' %
								(sysaddon, quote_plus(name), quote_plus(pm_icon), url_link)))
				cm.append((renameMenu % content_type.capitalize(), 'RunPlugin(%s?action=pm_Rename&type=%s&id=%s&name=%s)' %
								(sysaddon, content_type, item['id'], quote_plus(name))))
				cm.append((deleteMenu % content_type.capitalize(), 'RunPlugin(%s?action=pm_Delete&type=%s&id=%s&name=%s)' %
								(sysaddon, content_type, item['id'], quote_plus(name))))
				item = control.item(label=label, offscreen=True)
				item.addContextMenuItems(cm)
				item.setArt({'icon': pm_icon, 'poster': pm_icon, 'thumb': pm_icon, 'fanart': addonFanart, 'banner': pm_icon})
				item.setInfo(type='video', infoLabels='')
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=isFolder)
			except: log_utils.error()
		control.content(syshandle, 'files')
		control.directory(syshandle, cacheToDisc=True)

	def user_transfers(self):
		try:
			response = self._get(transfer_list_url)
			if response: return response.get('transfers')
		except: log_utils.error()

	def user_transfers_to_listItem(self):
		try:
			sysaddon, syshandle = 'plugin://plugin.video.luc_kodi/', int(argv[1])
			extensions = supported_video_extensions()
			transfer_files = self.user_transfers()
			if not transfer_files:
				if self.server_notifications: control.notification(message='Request Failure-Empty Content', icon=pm_icon)
				log_utils.log('Premiumize.me: Request Failure-Empty Content', __name__, log_utils.LOGDEBUG)
				return
		except: return log_utils.error()
		folder_str, file_str, downloadMenu, renameMenu, deleteMenu, clearFinishedMenu = getLS(40046).upper(), getLS(40047).upper(), getLS(40048), getLS(40049), getLS(40050), getLS(40051)
		for count, item in enumerate(transfer_files, 1):
			try:
				cm = []
				content_type = 'folder' if item['file_id'] is None else 'file'
				name = string_tools.strip_non_ascii_and_unprintable(item['name'])
				status = item['status']
				progress = item['progress']
				if status == 'finished': progress = 100
				else:
					try: progress = re.findall(r'(?:\d{0,1}\.{0,1})(\d+)', str(progress))[0][:2]
					except: progress = 'UNKNOWN'
				if content_type == 'folder':
					isFolder = True if status == 'finished' else False
					status_str = '[COLOR %s]%s[/COLOR]' % (control.getHighlightColor(), status.capitalize())
					label = '%02d | [B]%s[/B] - %s | [B]%s[/B] | [I]%s [/I]' % (count, status_str, str(progress) + '%', folder_str, name)
					url = '%s?action=pm_MyFiles&id=%s&name=%s' % (sysaddon, item['folder_id'], quote_plus(name))

					# Till PM addresses issue with item also being removed from public acess if item not accessed for 60 days this option is disabled.
					# cm.append((clearFinishedMenu, 'RunPlugin(%s?action=pm_ClearFinishedTransfers)' % sysaddon))
				else:
					isFolder = False
					details = self.item_details(item['file_id'])
					if not details:
						if self.server_notifications: control.notification(message='Request Failure-Empty Content', icon=pm_icon)
						log_utils.log('Premiumize.me: Request Failure-Empty Content', __name__, log_utils.LOGDEBUG)
						return
					url_link = details['link']
					if url_link.startswith('/'):
						url_link = 'https' + url_link
					size = details['size']
					display_size = float(int(size)) / 1073741824
					label = '%02d | %s%% | [B]%s[/B] | %.2f GB | [I]%s [/I]' % (count, str(progress), file_str, display_size, name)
					url = '%s?action=play_URL&url=%s' % (sysaddon, url_link)
					cm.append((downloadMenu, 'RunPlugin(%s?action=download&name=%s&image=%s&url=%s&caller=premiumize)' %
								(sysaddon, quote_plus(name), quote_plus(pm_icon), url_link)))

				cm.append((deleteMenu % 'Transfer', 'RunPlugin(%s?action=pm_DeleteTransfer&id=%s&name=%s)' %
							(sysaddon, item['id'], quote_plus(name))))
				item = control.item(label=label, offscreen=True)
				item.addContextMenuItems(cm)
				item.setArt({'icon': pm_icon, 'poster': pm_icon, 'thumb': pm_icon, 'fanart': addonFanart, 'banner': pm_icon})
				item.setInfo(type='video', infoLabels='')
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=isFolder)
			except: log_utils.error()
		control.content(syshandle, 'files')
		control.directory(syshandle, cacheToDisc=True)

	def item_details(self, item_id):
		try:
			data = {'id': item_id}
			itemDetails = self._post(item_details_url, data)
			return itemDetails
		except: log_utils.error()
		return None

	def rename(self, type, folder_id=None, folder_name=None):
		try:
			if type == 'folder':
				url = folder_rename_url
				t = getLS(40049) % type
			else:
				if not control.yesnoDialog(getLS(40049) % folder_name + ': [B](YOU MUST ENTER MATCHING FILE EXT.)[/B]', '', ''): return
				url = item_rename_url
				t = getLS(40049) % type + ': [B](YOU MUST ENTER MATCHING FILE EXT.)[/B]'
			k = control.keyboard('', t)
			k.doModal()
			q = k.getText() if k.isConfirmed() else None
			if not q: return
			data = {'id': folder_id, 'name': q}
			response = self._post(url, data=data)
			if not response: return
			if 'status' in response:
				if response.get('status') == 'success': control.refresh()
		except: log_utils.error()

	def delete(self, type, folder_id=None, folder_name=None):
		try:
			if type == 'folder': url = folder_delete_url
			else: url = item_delete_url
			if not control.yesnoDialog(getLS(40050) % folder_name, '', ''): return
			data = {'id': folder_id}
			response = self._post(url, data=data)
			if not response: return
			if 'status' in response:
				if response.get('status') == 'success': control.refresh()
		except: log_utils.error()
