"""
	luc_kodi Add-on
"""


from base64 import b64encode
import re
import requests
from urllib.parse import quote, quote_plus
from resources.lib.modules import control
from resources.lib.modules import string_tools

getLS = control.lang
getSetting = control.setting
en_icon = control.joinPath(control.artPath(), 'easynews.png')
addonFanart = control.addonFanart()

SORT = {'s1': 'relevance', 's1d': '-', 's2': 'dsize', 's2d': '-', 's3': 'dtime', 's3d': '-'}
# v1.0.52: alineado con la implementacion de referencia vigente (AIOStreams,
# builtins/easynews-search). El endpoint /advanced con st='adv' es el modo
# antiguo; hoy la webapp usa la raiz solr-search/ con st='basic', fly=2
# (respuesta JSON) y vv=1 (metadatos de video: codecs y resolucion real).
SEARCH_PARAMS = {'st': 'basic', 'fly': 2, 'sb': 1, 'chxu': 1, 'chxgx': 1, 'vv': 1,
				 'fex': 'm4v,3gp,mov,divx,xvid,wmv,avi,mpg,mpeg,mp4,mkv,avc,flv,webm',
				 'fty[]': 'VIDEO', 'spamf': 1, 'u': '1', 'gx': 1, 'pno': 1, 'sS': 3}
SEARCH_PARAMS.update(SORT)


class EasyNews:
	def __init__(self):
		self.base_link = 'https://members.easynews.com'
		self.search_link = '/2.0/search/solr-search/'
		self.moderation = 1 if getSetting('easynews.moderation') == 'true' else 0
		self.auth = self._get_auth()
		self.account_link = 'https://account.easynews.com/editinfo.php'
		self.usage_link = 'https://account.easynews.com/usageview.php'
		self.highlight_color = control.getHighlightColor()

	def _get(self, url, params={}):
		try:
			headers = {'Authorization': self.auth}
			response = requests.get(url, params=params, headers=headers, timeout=20)
			if response.status_code in (200, 201):
				try: return response.json()
				except: return response.text
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _get_auth(self):
		auth = None
		try:
			username = getSetting('easynews.username')
			password = getSetting('easynews.password')
			if username == '' or password == '': return auth
			user_info = '%s:%s' % (username, password)
			user_info = user_info.encode('utf-8')
			auth = '%s%s' % ('Basic ', b64encode(user_info).decode('utf-8'))
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return auth

	def search(self):
		from resources.lib.menus import navigator
		navigator.Navigator().addDirectoryItem(getLS(32603) % self.highlight_color, 'en_Searchnew', 'search.png', 'DefaultAddonsSearch.png', isFolder=False)
		from sqlite3 import dbapi2 as database
		try:
			if not control.existsPath(control.dataPath): control.makeFile(control.dataPath)
			dbcon = database.connect(control.searchFile)
			dbcur = dbcon.cursor()
			dbcur.executescript('''CREATE TABLE IF NOT EXISTS easynews (ID Integer PRIMARY KEY AUTOINCREMENT, term);''')
			dbcur.execute('''SELECT * FROM easynews ORDER BY ID DESC''')
			dbcur.connection.commit()
			lst = []
			delete_option = False
			for (id, term) in sorted(dbcur.fetchall(), key=lambda k: re.sub(r'(^the |^a |^an )', '', k[1].lower()), reverse=False):
				if term not in str(lst):
					delete_option = True
					navigator.Navigator().addDirectoryItem(term, 'en_searchResults&query=%s' % term, 'search.png', 'DefaultAddonsSearch.png', isSearch=True, table='easynews')
					lst += [(term)]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			try:
				dbcur.close()
			except Exception:
				pass
			try:
				dbcon.close()
			except Exception:
				pass
		if delete_option:
			navigator.Navigator().addDirectoryItem(32605, 'cache_clearSearch', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		navigator.Navigator().endDirectory()

	def search_new(self):
		k = control.keyboard('', control.lang(32010))
		k.doModal()
		query = k.getText() if k.isConfirmed() else None
		if not query: return control.closeAll()
		from sqlite3 import dbapi2 as database
		try:
			dbcon = database.connect(control.searchFile)
			dbcur = dbcon.cursor()
			dbcur.execute('''INSERT INTO easynews VALUES (?,?)''', (None, query))
			dbcur.connection.commit()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			try:
				dbcur.close()
			except Exception:
				pass
			try:
				dbcon.close()
			except Exception:
				pass
		control.closeAll()
		control.execute('ActivateWindow(Videos,plugin://plugin.video.luc_kodi/?action=en_searchResults&query=%s,return)' % quote_plus(query))

	def query_results_to_dialog(self, query):
		from sys import argv
		try:
			syshandle = int(argv[1])
			downloadMenu = control.lang(40048)
			url = '%s%s' % (self.base_link, self.search_link)
			params = SEARCH_PARAMS
			params['pby'] = 250 # Results per Page (tope real de la API 2.0)
			params['safeO'] = self.moderation # 1 is the moderation (adult filter) ON, 0 is OFF.
			# params['gps'] = params['sbj'] = query # gps stands for "group search" and does so by keywords, sbj=subject and can limit results, use gps only
			params['gps'] = query
			results = self._get(url, params)
			files = self._process_files(results)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

		for count, item in enumerate(files, 1):
			try:
				cm = []
				name = string_tools.strip_non_ascii_and_unprintable(item['name'])
				url_dl = item['url_dl']
				sysurl_dl = quote_plus(url_dl)
				size = str(round(float(int(item['rawSize'])) / 1048576000, 1))
				label = '%02d | [B]%s GB[/B] | [I]%s [/I]' % (count, size, name)
				url = 'plugin://plugin.video.luc_kodi/?action=en_resolve_forPlayback&url=%s' % sysurl_dl
				cm.append((downloadMenu, 'RunPlugin(plugin://plugin.video.luc_kodi/?action=download&name=%s&image=%s&url=%s&caller=easynews)' %
									(quote_plus(name), quote_plus(en_icon), sysurl_dl)))
				item = control.item(label=label, offscreen=True)
				item.addContextMenuItems(cm)
				item.setArt({'icon': en_icon, 'poster': en_icon, 'thumb': en_icon, 'fanart': addonFanart, 'banner': en_icon})
				item.setInfo(type='video', infoLabels='')
				item.setLabel(label)
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		control.content(syshandle, 'files')
		control.directory(syshandle, cacheToDisc=True)

	def _process_files(self, results):
		def _process():
			for item in files:
				try:
					valid_result = True
					size, post_title, ext, duration = item['4'], item['10'], item['11'], item['14']
					# v1.0.52: en el formato objeto 'hash' viene pelado y 'id' aporta el
					# sufijo de 4 caracteres que la URL de descarga necesita. El campo
					# '0' del formato antiguo ya trae el hash completo.
					post_hash = item.get('0') or ''
					if not post_hash:
						_sig = item.get('id')
						post_hash = '%s%s' % (item.get('hash') or '', '' if _sig is None else str(_sig))
					if not post_hash: continue
					if 'alangs' in item and item['alangs']: language = item['alangs']
					else: language = ''
					if 'type' in item and item['type'].upper() != 'VIDEO': valid_result = False
					elif 'virus' in item and item['virus']: valid_result = False
					elif item.get('passwd'): valid_result = False # post protegido con contrasena
					elif re.match(r'^\d+s', duration) or re.match(r'^[0-5]m', duration): valid_result = False
					if not valid_result: continue
					# v1.0.53: URL limpia. La cabecera Basic se adjunta en
					# _with_auth() justo antes de reproducir o descargar, para que
					# la contrasena no acabe en el directorio cacheado en disco
					# (directory(..., cacheToDisc=True)) ni en el menu contextual.
					stream_url = down_url + quote('/%s/%s/%s%s/%s%s' % (dl_farm, dl_port, post_hash, ext, post_title, ext))
					result = {'name': post_title, 'size': size, 'rawSize': item['rawSize'], 'url_dl': stream_url, 'version': 'version2', 'full_item': item, 'language': language}
					yield result
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
		down_url = results.get('downURL') or '%s/dl' % self.base_link
		dl_farm = results.get('dlFarm') or 'auto'
		dl_port = results.get('dlPort') or 'auto'
		files = results.get('data', [])
		sources = list(_process())
		return sources

	def _with_auth(self, url):
		"""Adjunta la cabecera Basic justo antes de usar la URL."""
		if not url: return None
		if '|Authorization=' in url: return url
		if not url.startswith(self.base_link) and '/dl/' not in url: return url
		if not self.auth: return None
		return '%s|Authorization=%s' % (url, quote(self.auth))

	def resolve_forPlayback(self, url):
		from resources.lib.modules import player
		play_url = self._with_auth(url)
		if not play_url:
			return control.notification(message='Easynews: no credentials set', icon=en_icon)
		return player.Player().play(play_url)

	def account(self):
		account_info = usage_info = None
		from resources.lib.modules.dom_parser import parseDOM
		try:
			account_html = self._get(self.account_link)
			if account_html == None or account_html == '': raise Exception()
			account_info = parseDOM(account_html, 'form', attrs={'id': 'accountForm'})
			account_info = parseDOM(account_info, 'td')[0:11][1::3]
			usage_html = self._get(self.usage_link)
			if usage_html == None or usage_html == '': raise Exception()
			usage_info = parseDOM(usage_html, 'div', attrs={'class': 'table-responsive'})
			usage_info = parseDOM(usage_info, 'td')[0:11][1::3]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return account_info, usage_info

	def account_info_to_dialog(self):
		from datetime import datetime
		import time
		from resources.lib.windows.textviewer import TextViewerXML
		try:
			control.busy()
			account_info, usage_info = self.account()
			if not account_info or not usage_info:
				control.hide()
				return control.notification(message=32221, icon=en_icon)
			expires = datetime.fromtimestamp(time.mktime(time.strptime(account_info[2], '%Y-%m-%d'))) # could utilize a new cleandate method
			days_remaining = (expires - datetime.today()).days
			expires = expires.strftime('%Y-%m-%d')
			body = []
			append = body.append
			append(getLS(40036) % account_info[0])  # Username
			append(getLS(40066) % account_info[1])  # Plan
			append(getLS(40037) % account_info[3])  # Status
			append(getLS(40041) % expires)               # Expires
			append(getLS(40042) % days_remaining) # Days Remaining
			append(getLS(32218) % usage_info[2])    # Loyalty
			append(getLS(32219) % usage_info[0].replace('Gigs', 'GB')) # Data Used
			append(getLS(32220) % re.sub(r'[</].+?>', '', usage_info[1].replace('Gigs', 'GB'))) # Data Remaining
			control.hide()
			windows = TextViewerXML('textviewer.xml', control.addonPath(control.addonId()), heading='[B]EasyNews[/B]', text='\n\n'.join(body))
			windows.run()
			del windows
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			control.hide()
