from modules.meta_lists import meta_languages
from modules import kodi_utils
from session import http
# logger = kodi_utils.logger

ls, get_setting = kodi_utils.local_string, kodi_utils.get_setting
subsfound_str, dlfound_str, nosubs_str, ratelimit_str = ls(32792), ls(32793), ls(32794), ls(32791)

def request_get(url, **kwargs):
	try: response = http.request('get', url, **kwargs)
	except Exception as e: return str(e)
	if not response.status < 400: return response.reason
	return response

class SubtitleScraper:
	def __init__(self, player_object, poster):
		self.player = player_object
		self.poster = poster

	def __call__(self):
		if get_setting('subtitles.subs_action', '0') not in ('1',): return
		language_choices = {k: v for k, v in meta_languages.items() if v['long'] and v['short']}
		self.languages = language_choices[get_setting('subtitles.language')]
		self.auto_filter = get_setting('subtitles.auto_filter') == 'true'
		self.auto_enable = get_setting('subtitles.auto_enable') == 'true'
		self.params = {'lang': self.languages['short'], 'format': 'srt', 'limit': 50}
		self.base_url = 'https://api.thesubtitledb.org/v1/by-imdb'
		self.subtitle_path = 'special://temp/'
		sub_filename = 'POVSubs_%s' % self.player.imdb_id
		if self.player.mediatype == 'episode':
			self.path = '/%s/season/%s/episode/%s' % (self.player.imdb_id, self.player.season, self.player.episode)
			sub_filename = '%s_%s_%s' % (sub_filename, self.player.season, self.player.episode)
		else: self.path = '/%s' % self.player.imdb_id
		self.search_filename = '%s_%s.srt' % (sub_filename, self.languages['short'])
		kodi_utils.sleep(2000)
		return self._video_file_subs() or self._downloaded_subs() or self._searched_subs()

	def _video_file_subs(self):
		try: available_sub_language = self.player.getSubtitles()
		except: available_sub_language = ''
		if available_sub_language != self.languages['long']: return False
		if self.auto_enable: self.player.showSubtitles(True)
		kodi_utils.notification(subsfound_str, icon=self.poster)
		return True

	def _downloaded_subs(self):
		files = kodi_utils.list_dirs(self.subtitle_path)[1]
		final_match = next((i for i in files if i == self.search_filename), None)
		if not final_match: return False
		subtitle = '%s%s' % (self.subtitle_path, final_match)
		self.player.setSubtitles(subtitle)
		kodi_utils.notification(dlfound_str, icon=self.poster)
		return True

	def _searched_subs(self):
		response = request_get(self.base_url + self.path, fields=self.params)
		if isinstance(response, str): return kodi_utils.notification('Subtitles Error: %s' % response)
		subs = response.json()['subtitles']['items']
		if not subs: return kodi_utils.notification(nosubs_str, icon=self.poster)
		try: chosen_sub = self._filter_subs(subs)
		except: return kodi_utils.notification(nosubs_str, icon=self.poster)
		final_path = '%s%s' % (self.subtitle_path, self.search_filename)
		response = request_get(chosen_sub['download_url'], preload_content=False)
		if isinstance(response, str): return kodi_utils.notification('Subtitles Error: %s' % response)
		with response, kodi_utils.open_file(final_path, 'w') as file: __import__('shutil').copyfileobj(response, file)
		kodi_utils.notification(chosen_sub['release_name'].strip() or self.search_filename, icon=self.poster)
		self.player.setSubtitles(final_path)
		return kodi_utils.path_exists(final_path)

	def _filter_subs(self, subs):
		try:
			if not self.auto_filter: raise Exception
			from difflib import SequenceMatcher
			import re
			pattern = re.compile(r'\W')
			filename = re.sub(r'\s+', ' ', pattern.sub(' ', self.player.filename.strip().lower()))
			if not filename.strip(): raise Exception
			matcher = SequenceMatcher(None, b=filename)
			for i in subs:
				matcher.set_seq1(re.sub(r'\s+', ' ', pattern.sub(' ', i['release_name'].strip().lower())))
				i['ratio'] = matcher.ratio()
			subs.sort(key=lambda k: k['ratio'], reverse=True)
		except: pass
		return next(i for i in subs if i['cues'] > 1 and i['language'] == self.languages['short'])

