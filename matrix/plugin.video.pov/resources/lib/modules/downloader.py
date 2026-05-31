import json
import os, ssl
from threading import Thread
from urllib.parse import unquote, parse_qsl, urlparse
from urllib.request import Request, urlopen
from indexers.metadata import get_title
from modules import debrid, kodi_utils
from modules.settings import download_directory, get_art_provider
from modules.utils import clean_file_name, clean_title, safe_string, remove_accents
# from modules.kodi_utils import logger

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
levels = ['../../../..', '../../..', '../..', '..']
ls, user_agent = kodi_utils.local_string, kodi_utils.xbmc.getUserAgent()
poster_empty = kodi_utils.media_path('box_office.png')
image_extensions, video_extensions = (
	'jpg', 'jpeg', 'jpe', 'jif', 'jfif', 'jfi', 'bmp', 'dib', 'png', 'gif', 'webp', 'tiff', 'tif',
	'psd', 'raw', 'arw', 'cr2', 'nrw', 'k25', 'jp2', 'j2k', 'jpf', 'jpx', 'jpm', 'mj2'
), (
	'm4v', '3g2', '3gp', 'nsv', 'tp', 'ts', 'ty', 'pls', 'rm', 'rmvb', 'mpd', 'ifo', 'mov', 'qt', 'divx',
	'xvid', 'bivx', 'vob', 'nrg', 'img', 'iso', 'udf', 'pva', 'wmv', 'asf', 'asx', 'ogm', 'm2v', 'avi', 'bin',
	'dat', 'mpg', 'mpeg', 'mp4', 'mkv', 'mk3d', 'avc', 'vp3', 'svq3', 'nuv', 'viv', 'dv', 'fli', 'flv', 'wpl',
	'xspf', 'vdr', 'dvr-ms', 'xsp', 'mts', 'm2t', 'm2ts', 'evo', 'ogv', 'sdp', 'avs', 'rec', 'url', 'pxml',
	'vc1', 'h264', 'rcv', 'rss', 'mpls', 'mpl', 'webm', 'bdmv', 'bdm', 'wtv', 'trp', 'f4v', 'pvr', 'disc'
)

def runner(params):
	action = params.get('action')
	if action == 'image':
		for item in ('thumb_url', 'image_url'):
			image_params = params
			image_params['url'] = params.pop(item)
			image_params['mediatype'] = item
			Downloader(image_params).run()
	elif 'meta' in action:
		from modules.source_utils import find_season_in_release_title
		source, meta = json.loads(params['source']), json.loads(params['meta'])
		pack_choices = debrid.Source(source, meta).browse_packs(download=True)
		if not pack_choices: return kodi_utils.notification(32692)
		if len(pack_choices) > 1:
			heading = clean_file_name(source.get('name'))
			kwargs = {'enumerate': 'true', 'multi_choice': 'true', 'multi_line': 'true'}
			kwargs.update({'items': json.dumps(pack_choices), 'heading': heading, 'highlight': params['highlight']})
			chosen_list = kodi_utils.select_dialog(pack_choices, **kwargs)
		else: chosen_list = next(([i] for i in pack_choices), None)
		if not chosen_list: return
		size_label = sum(i['size'] for i in chosen_list) / (1024 * 1024)
		text = '%s[CR]%s' % (ls(32688) % size_label, ls(32689))
		if not kodi_utils.confirm_dialog(text=text, top_space=True): return
		show_package = source.get('package') == 'show'
		default_name = '%s (%s)' % (clean_file_name(get_title(meta)), meta.get('year'))
		default_foldername = kodi_utils.dialog.input(ls(32228), defaultt=default_name)
		for item in chosen_list:
			item = {**params, 'default_foldername': default_foldername, 'pack_files': item}
			if show_package:
				season = find_season_in_release_title(item['pack_files']['filename'])
				if season: meta.update({'season': season}), item.update({'meta': json.dumps(meta)})
			(Thread(target=Downloader(item).run)).start()
	else: Downloader(params).run()

class Downloader:
	def __init__(self, params):
		self.params = params
		self.params_get = self.params.get

	def run(self):
		kodi_utils.show_busy_dialog()
		self.download_prep()
		self.get_url_and_headers()
		if self.url in (None, 'None', ''): return self.return_notification(notification=32692)
		self.get_filename()
		self.get_extension()
		self.download_check()
		if not self.confirm_download(): return self.return_notification(notification=32736)
		self.get_download_folder()
		if not self.get_destination_folder(): return self.return_notification(notification=32736)
		self.start_download(self.url, os.path.join(self.final_destination, self.final_name + self.extension))

	def download_prep(self):
		if 'meta' in self.params:
			poster_main, poster_backup = get_art_provider()[:2]
			self.meta = json.loads(self.params_get('meta'))
			self.meta_get = self.meta.get
			self.mediatype = self.meta_get('mediatype')
			self.image = self.meta_get(poster_main) or self.meta_get(poster_backup) or poster_empty
			self.year = self.meta_get('year')
			self.season = self.meta_get('season')
			self.name = self.params_get('name')
			title = get_title(self.meta)
		else:
			self.meta = None
			self.mediatype = self.params_get('mediatype')
			self.image = self.params_get('image')
			self.name = None
			title = self.params_get('name')
		self.title = clean_file_name(title)
		self.provider = self.params_get('provider')
		self.action = self.params_get('action')
		self.source = self.params_get('source')
		self.final_name = None

	def get_url_and_headers(self):
		url = self.params_get('url')
		if url in (None, 'None', ''):
			if 'meta' in self.action:
				link = self.params_get('pack_files')['link']
				debrid_function = debrid.import_debrid(self.provider)
				url = debrid_function.unrestrict_link(link)
		if self.action.startswith('cloud'):
			if 'real-debrid' in self.action:
				from menus.real_debrid import resolve_rd as debrid_function
			elif 'alldebrid' in self.action:
				from menus.alldebrid import resolve_ad as debrid_function
			elif 'torbox' in self.action:
				from menus.torbox import resolve_tb as debrid_function
			elif 'easynews' in self.action:
				from menus.easynews import resolve_easynews as debrid_function
			if '_direct' in self.action: url = self.params_get('url')
			else: url = debrid_function(self.params)
		else: pass
		url, *headers = url.rsplit('|', 1)
		try: headers = dict(parse_qsl(*headers))
		except: headers = dict()
		self.headers = headers
		self.url = url

	def get_download_folder(self):
		self.down_folder = download_directory(self.mediatype)
		if self.mediatype == 'thumb_url':
			self.down_folder = os.path.join(self.down_folder, '.thumbs')
		for level in levels:
			try: kodi_utils.make_directory(os.path.abspath(os.path.join(self.down_folder, level)))
			except: pass

	def get_destination_folder(self):
		if self.action == 'image':
			self.final_destination = self.down_folder
		elif 'meta' in self.action:
			default_name = '%s (%s)' % (self.title, self.year)
			folder_rootname = self.params_get('default_foldername', default_name)
			if not folder_rootname: return False
			if self.mediatype == 'episode':
				inter = os.path.join(self.down_folder, folder_rootname)
				kodi_utils.make_directory(inter)
				self.final_destination = os.path.join(inter, 'Season %02d' %  int(self.season))
			else: self.final_destination = os.path.join(self.down_folder, folder_rootname)
		else: self.final_destination = self.down_folder
		kodi_utils.make_directory(self.final_destination)
		return True

	def get_filename(self):
		if self.final_name: final_name = self.final_name
		elif self.action == 'image':
			final_name = self.title
		elif 'meta' in self.action:
			name = self.params_get('pack_files')['filename']
			final_name = os.path.splitext(urlparse(name).path)[0].split('/')[-1]
		else:
			name_url = self.params_get('name') or unquote(self.url)
			file_name = clean_title(name_url.split('/')[-1])
			if clean_title(self.title).lower() in file_name.lower():
				final_name = os.path.splitext(urlparse(name_url).path)[0].split('/')[-1]
			else:
				try: final_name = self.name.translate(None, r'\/:*?"<>|').strip('.')
				except: final_name = os.path.splitext(urlparse(name_url).path)[0].split('/')[-1]
		self.final_name = safe_string(remove_accents(final_name))

	def get_extension(self):
		if self.action == 'archive':
			ext = '.zip'
		elif self.action == 'image':
			ext = os.path.splitext(urlparse(self.url).path)[1][1:]
			if ext not in image_extensions: ext = 'jpg'
			ext = '.%s' % ext
		elif 'meta' in self.action:
			name = self.params_get('pack_files')['filename']
			ext = os.path.splitext(urlparse(name).path)[1][1:]
			if ext not in video_extensions: ext = 'mp4'
			ext = '.%s' % ext
		else:
			name_url = self.params_get('name') or self.url
			ext = os.path.splitext(urlparse(name_url).path)[1][1:]
			if ext not in video_extensions: ext = 'mp4'
			ext = '.%s' % ext
		self.extension = ext

	def download_check(self):
		self.headers['User-Agent'] = user_agent
		self.resp = self.get_response(self.url, self.headers, 0)
		if not self.resp: self.return_notification(ok_dialog=32575)
		try: self.content = int(self.resp.headers['Content-Length'])
		except: self.content = 0
		try: self.resumable = 'bytes' in self.resp.headers['Accept-Ranges'].lower()
		except: self.resumable = False
		if self.content < 1: self.return_notification(ok_dialog=32575)
		self.size = 1024 * 1024
		self.size_label = self.content / (1024 * 1024)
		if self.content < self.size: self.size = self.content
		kodi_utils.hide_busy_dialog()

	def start_download(self, url, dest):
		if self.action in ('image', 'meta.pack'):
			if self.action == 'meta.pack': kodi_utils.notification(32134, 3000, self.image)
			show_notifications, notification_frequency = False, 0
		else: show_notifications, notification_frequency = True, 25
		notify, total, errors, count, resume, sleep_time  = 25, 0, 0, 0, 0, 0
		f = kodi_utils.open_file(dest, 'w')
		chunk  = None
		chunks = []
		while True:
			downloaded = total
			for c in chunks: downloaded += len(c)
			percent = min(round(float(downloaded)*100 / self.content), 100)
			playing = kodi_utils.player.isPlaying()
			if show_notifications:
				if percent >= notify:
					notify += notification_frequency
					try:
						line1 = '%s - [I]%s[/I]' % (str(percent)+'%', self.final_name)
						if not playing: kodi_utils.notification(line1, 3000, self.image)
					except: pass
			chunk = None
			error = False
			try:
				chunk  = self.resp.read(self.size)
				if not chunk:
					if percent < 99:
						error = True
					else:
						while len(chunks) > 0:
							c = chunks.pop(0)
							f.write(c)
							del c
						f.close()
						try: progressDialog.close()
						except: pass
						return self.finish_download(self.final_name, self.mediatype, True, self.image)
			except Exception as e:
				error = True
				sleep_time = 10
				errno = 0
				if hasattr(e, 'errno'):
					errno = e.errno
				if errno == 10035: # 'A non-blocking socket operation could not be completed immediately'
					pass
				if errno == 10054: # 'An existing connection was forcibly closed by the remote host'
					errors = 10    # force resume
					sleep_time  = 30
				if errno == 11001: # 'getaddrinfo failed'
					errors = 10    # force resume
					sleep_time  = 30
			if chunk:
				errors = 0
				chunks.append(chunk)
				if len(chunks) > 5:
					c = chunks.pop(0)
					f.write(c)
					total += len(c)
					del c
			if error:
				errors += 1
				count  += 1
				kodi_utils.sleep(sleep_time*1000)
			if (self.resumable and errors > 0) or errors >= 10:
				if (not self.resumable and resume >= 50) or resume >= 500:
					try: progressDialog.close()
					except: pass
					return self.finish_download(self.final_name, self.mediatype, False, self.image)
				resume += 1
				errors  = 0
				if self.resumable:
					chunks  = []
					self.resp = self.get_response(url, self.headers, total)
				else: pass

	def get_response(self, url, headers, size):
		try:
			if size > 0: headers['Range'] = 'bytes=%d-' % int(size)
			req = Request(url, headers=headers)
			resp = urlopen(req, context=ctx, timeout=30)
			return resp
		except: return None

	def finish_download(self, title, mediatype, downloaded, image):
		if self.mediatype == 'thumb_url': return
		if self.mediatype == 'image_url':
			text = ls(32576) if downloaded else ls(32691)
			return kodi_utils.notification('%s' % text, 3000, image)
		playing = kodi_utils.player.isPlaying()
		if downloaded: text = '%s %s:[CR]%s' % (ls(32107), ls(32576), title)
		else: text = '%s %s:[CR]%s' % (ls(32107), ls(32575), title)
		if not downloaded or not playing: kodi_utils.ok_dialog(text=text, top_space=True)

	def confirm_download(self):
		if self.action in ('image', 'meta.single', 'meta.pack'): return True
		text = '%s[CR]%s' % (ls(32688) % self.size_label, ls(32689))
		return kodi_utils.confirm_dialog(text=text, top_space=True)

	def return_notification(self, notification=None, ok_dialog=None, top_space=True):
		kodi_utils.hide_busy_dialog()
		if notification: kodi_utils.notification(notification)
		elif ok_dialog: kodi_utils.ok_dialog(text=ok_dialog, top_space=True)
		else: return

