import os
import requests
from datetime import timedelta
from caches.main_cache import MainCache
from modules.meta_lists import language_choices
from modules import kodi_utils
# from modules.kodi_utils import logger

ls, get_setting = kodi_utils.local_string, kodi_utils.get_setting
search_url = 'https://sub.wyzie.ru/search'
timeout = 5.05

def _get(url, params=None, stream=False, retry=False):
	response = requests.get(url, params=params, stream=stream, timeout=timeout)
	if retry and response.status_code in (403, 429):
		kodi_utils.notification(32740)
		kodi_utils.sleep(10000)
		return _get(url, params=params, stream=stream)
	return response

def subtitles_download(url):
	response = _get(url, stream=True, retry=True)
	return response if response.ok else response.reason

def subtitles_search(imdb_id, season=None, episode=None):
	cache_name = 'subtitles_wyzie_%s' % imdb_id
	params = {'id': imdb_id, 'format': 'srt'}
	if season:
		cache_name += '_%s_%s' % (season, episode)
		params.update({'season': season, 'episode': episode})
	maincache = MainCache()
	cache = maincache.get(cache_name)
	if cache: return cache
	response = _get(search_url, params=params, retry=True)
	if not response.ok: return []
	response = response.json()
	if response: maincache.set(cache_name, response, expiration=timedelta(hours=24))
	return response

class Subtitles(kodi_utils.xbmc_player):
	def run(self, query, imdb_id, season, episode, poster):
		def _video_file_subs():
			try: available_sub_language = self.getSubtitles()
			except: available_sub_language = ''
			if not available_sub_language == self.language1: return False
			if self.auto_enable == 'true': self.showSubtitles(True)
			kodi_utils.notification(32852, icon=poster)
			return True
		def _downloaded_subs():
			files = kodi_utils.list_dirs(subtitle_path)[1]
			final_match = next((i for i in files if i == search_filename), None)
			if not final_match: return False
			subtitle = '%s%s' % (subtitle_path, final_match)
			kodi_utils.notification(32792, icon=poster)
			return subtitle
		def _searched_subs():
			search_language = kodi_utils.convert_language(self.language1, format='short')
			result = subtitles_search(imdb_id, season, episode)
			if not result: return kodi_utils.notification(32793, icon=poster)
			result.sort(key=lambda k: k['display'], reverse=False)
			result.sort(key=lambda k: k['language'] == search_language, reverse=True)
			if self.subs_action == 'select' and len(result) > 1:
				try: video_path = self.getPlayingFile()
				except: video_path = ''
				if '|' in video_path: video_path = video_path.split('|')[0]
				video_path = os.path.basename(video_path)
				heading = '%s - %s' % (ls(32246).upper(), video_path)
				def _builder():
					for i in result:
						listitem = kodi_utils.make_listitem()
						listitem.setLabel('%s%s' % (i['display'].upper(), ' (SDH)' if i['isHearingImpaired'] else ''))
						listitem.setLabel2('%s - %s[CR]%s' % (i.get('origin') or 'N/A', i['source'].upper(), i.get('release') or i['media']))
						listitem.setArt({'icon': i['flagUrl'].replace('24.png', '64.png')})
						yield listitem
				self.pause()
				chosen_sub = kodi_utils.dialog.select(heading, list(_builder()), useDetails=True)
				self.pause()
			else: chosen_sub = next((i for i, _ in enumerate(result) if _['language'] == search_language), -1)
			if chosen_sub < 0: return kodi_utils.notification(32736, icon=poster)
			chosen_sub = result[chosen_sub]
			try: lang = kodi_utils.convert_language(chosen_sub['language'])
			except: lang = chosen_sub['language']
			final_filename = sub_filename + '_%s.%s' % (lang, chosen_sub['format'])
			final_path = '%s%s' % (subtitle_path, final_filename)
			response = subtitles_download(chosen_sub['url'])
			if isinstance(response, str): return kodi_utils.notification('Subtitles Error: %s' % response)
			try: content = response.text
			except: content = response.content
			with kodi_utils.open_file(final_path, 'w') as file: file.write(content)
			kodi_utils.sleep(1000)
			return final_path
		self.auto_enable = get_setting('subtitles.auto_enable')
		self.language1 = language_choices[get_setting('subtitles.language')]
		self.subs_action = {'0': 'auto', '1': 'select', '2': 'off'}[get_setting('subtitles.subs_action', '2')]
		if not self.subs_action in ('auto', 'select'): return
		kodi_utils.sleep(2500)
		subtitle_path = 'special://temp/'
		sub_filename = 'SALTSSubs_%s_%s_%s' % (imdb_id, season, episode) if season else 'SALTSSubs_%s' % imdb_id
		search_filename = sub_filename + '_%s.srt' % self.language1
		subtitle = _video_file_subs()
		if subtitle: return
		subtitle = _downloaded_subs()
		if subtitle: return self.setSubtitles(subtitle)
		subtitle = _searched_subs()
		if subtitle: return self.setSubtitles(subtitle)

