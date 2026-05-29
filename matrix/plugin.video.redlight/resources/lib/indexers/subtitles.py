# -*- coding: utf-8 -*-
import xbmc
import requests
from modules import kodi_utils as ku, settings as st

timeout = 20.0

def _get(url, stream=False, retry=False):
	response = requests.get(url, stream=stream, timeout=timeout)
	if retry and response.status_code in (403, 429):
		ku.notification('SubMaker rate limited. Retrying in 10 secs...', 3500)
		ku.sleep(10000)
		return _get(url, stream=stream)
	return response

class Subtitles(xbmc.Player):
	def subtitles_download(self, url):
		response = _get(url, stream=True, retry=True)
		return response if response.ok else response.reason

	def subtitles_search(self):
		if self.season: params = 'subtitles/series/%s:%s:%s' % (self.imdb_id, self.season, self.episode)
		else: params = 'subtitles/movie/%s' % self.imdb_id
		try: response = _get(self.manifest.replace('manifest', params), retry=True)
		except requests.RequestException as e: return str(e)
		return response.json().get('subtitles', []) if response.ok else response.reason

	def _video_file_subs(self):
		try: available_sub_language = self.getSubtitles()
		except: available_sub_language = ''
		if not available_sub_language: return False
		if st.auto_enable_subs(): self.showSubtitles(True)
		ku.notification('Local subtitles found', icon=self.poster, settle_ms=150)
		return True

	def _downloaded_subs(self):
		files = ku.list_dirs(self.subtitle_path)[1]
		final_match = next((i for i in files if i == self.search_filename), None)
		if not final_match: return False
		subtitle = '%s%s' % (self.subtitle_path, final_match)
		ku.notification('Downloaded subtitles found', icon=self.poster, settle_ms=150)
		return subtitle

	def _searched_subs(self):
		subs = self.subtitles_search()
		if isinstance(subs, str):
			return ku.notification('SubMaker error: %s' % subs, settle_ms=150)
		if not subs:
			return ku.notification('No subtitles found', icon=self.poster, settle_ms=150)
		choices = (i for i in subs if i.get('lang') == self.language)
		try: chosen_sub = next(choices, None) or next(iter(subs))
		except: return ku.notification('No subtitles found', icon=self.poster, settle_ms=150)
		response = self.subtitles_download(chosen_sub.get('url'))
		if isinstance(response, str):
			return ku.notification('SubMaker error: %s' % response, settle_ms=150)
		final_path = '%s%s' % (self.subtitle_path, self.search_filename)
		try: content = response.text
		except: content = response.content
		with ku.open_file(final_path, 'w') as file: file.write(content)
		ku.sleep(1000)
		return final_path

	def run(self, imdb_id, season, episode, poster):
		self.manifest = st.submaker_manifest()
		if not self.manifest or 'manifest' not in self.manifest: return
		self.imdb_id, self.season, self.episode, self.poster = imdb_id, season, episode, poster
		self.language = st.submaker_language()
		filename_lang = self.language.replace(' ', '_')
		self.subtitle_path = 'special://temp/'
		if season: self.sub_filename = 'RedLightSubs_%s_%s_%s' % (self.imdb_id, self.season, self.episode)
		else: self.sub_filename = 'RedLightSubs_%s' % self.imdb_id
		self.search_filename = self.sub_filename + '_%s.srt' % filename_lang
		ku.sleep(2500)
		if st.submaker_prefer_local():
			subtitle = self._video_file_subs()
			if subtitle: return
		subtitle = self._downloaded_subs()
		if subtitle: return self.setSubtitles(subtitle)
		subtitle = self._searched_subs()
		if subtitle: return self.setSubtitles(subtitle)
