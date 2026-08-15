# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	OpenSubtitles v1 API integration
	---
	How it works:
	  1. The user registers a FREE account at https://www.opensubtitles.com
	     (free tier = 5 subtitle downloads/day per user account)
	  2. User enters username and password in Settings → Subtitles
	  3. On first use, the addon logs in and stores the JWT token automatically
	  4. From then on the stored JWT is reused (refreshed only when expired)
"""

import re
import requests
from resources.lib.modules import control
from resources.lib.modules import log_utils
import xbmc


base_url = 'https://api.opensubtitles.com/api/v1'
api_key  = 'bpjXX6cIqRZzqQ4gcxHvEcuXrsepl71O'
version  = control.getluc_kodiVersion()


class Opensubs():
	def __init__(self):
		self.username   = control.setting('opensubsusername')
		self.password   = control.setting('opensubspassword')
		self.jwt_token  = control.setting('opensubstoken')
		self.headers = {
			'Content-Type': 'application/json',
			'Api-Key': api_key,
			'User-Agent': 'luc_kodi v' + version
		}
		self.highlight_color = control.setting('highlight.color')

	def auth(self):
		"""
		Authenticate against OpenSubtitles.
		Returns True if auth is valid or successfully refreshed, False otherwise.
		"""
		url = base_url + '/login'
		xbmc.log('[ luc_kodi ] opensubs.auth() — user="%s" has_token=%s' % (self.username, bool(self.jwt_token)), xbmc.LOGINFO)
		if not self.username or not self.password:
			xbmc.log('[ luc_kodi ] opensubs.auth() — ABORT: username or password empty', xbmc.LOGINFO)
			return False
		data = {
			'username': self.username,
			'password': self.password,
		}
		if self.jwt_token:
			# Validate existing token
			url_info = base_url + '/infos/user'
			headers2 = {
				'Content-Type': 'application/json',
				'Api-Key': api_key,
				'Authorization': self.jwt_token,
				'User-Agent': 'luc_kodi v' + version
			}
			response = requests.get(url_info, headers=headers2, timeout=20)
			xbmc.log('[ luc_kodi ] opensubs.auth() token check: status=%s' % response.status_code, xbmc.LOGINFO)
			if response.status_code == 200:
				return True
			else:
				# Token expired – get a new one
				response2 = requests.post(url, headers=self.headers, json=data, timeout=20)
				xbmc.log('[ luc_kodi ] opensubs.auth() re-login: status=%s' % response2.status_code, xbmc.LOGINFO)
				if response2.status_code == 200:
					control.setSetting('opensubstoken', response2.json().get('token'))
					return True
				else:
					return False
		else:
			# First login
			xbmc.log('[ luc_kodi ] opensubs.auth() — first login attempt', xbmc.LOGINFO)
			response = requests.post(url, headers=self.headers, json=data, timeout=20)
			xbmc.log('[ luc_kodi ] opensubs.auth() first login: status=%s' % response.status_code, xbmc.LOGINFO)
			response = response.json()
			token = response.get('token')
			xbmc.log('[ luc_kodi ] opensubs.auth() first login: has_token=%s' % bool(token), xbmc.LOGINFO)
			control.setSetting('opensubstoken', token)
			return True

	def getSubs(self, title, imdb, year, season=None, episode=None, lang_override=None):
		"""
		Search for subtitle files on OpenSubtitles.
		Returns a list of dicts: [{'fileName': str, 'fileID': int}, ...]
		"""
		try:
			if lang_override:
				try: language = xbmc.convertLanguage(lang_override, xbmc.ISO_639_1)
				except: language = lang_override
			else:
				language = xbmc.convertLanguage(control.setting('subtitles.lang.1'), xbmc.ISO_639_1)
			if season:
				url = base_url + '/subtitles?imdb_id=%s&season_number=%s&episode_number=%s&languages=%s' % (imdb, season, episode, language)
			else:
				url = base_url + '/subtitles?imdb_id=%s&languages=%s' % (imdb, language)
			headers = {
				'Content-Type': 'application/json',
				'Api-Key': api_key,
				'Authorization': self.jwt_token,
				'User-Agent': 'luc_kodi v' + version
			}
			xbmc.log('[ luc_kodi ] OpenSubs Searching: IMDB:%s Season:%s Episode:%s Language:%s URL:%s' % (imdb, season, episode, language, url), xbmc.LOGINFO)
			response = requests.get(url, headers=headers, timeout=20)
			xbmc.log('[ luc_kodi ] OpenSubs Search response: status=%s' % response.status_code, xbmc.LOGINFO)
			response = response.json()
			response = response['data']
			results = []
			for count, x in enumerate(response):
				try:
					attrs    = response[count]['attributes']
					fileName = attrs.get('files')[0].get('file_name')
					fileID   = attrs.get('files')[0].get('file_id')
					results.append({
						'fileName':         fileName,
						'fileID':           fileID,
						'downloads':        attrs.get('new_download_count', 0) or 0,
						'ratings':          float(attrs.get('ratings', 0) or 0),
						'votes':            int(attrs.get('votes', 0) or 0),
						'trusted':          bool(attrs.get('from_trusted', False)),
						'ai':               bool(attrs.get('ai_translated', False)),
						'machine':          bool(attrs.get('machine_translated', False)),
						'hi':               bool(attrs.get('hearing_impaired', False)),
						'release':          attrs.get('release', '') or '',
						'fps':              float(attrs.get('fps', 0) or 0),
					})
				except:
					log_utils.error()
			xbmc.log('[ luc_kodi ] OpenSubs getSubs: found %s results for lang=%s' % (len(results), language), xbmc.LOGINFO)
			return results
		except:
			log_utils.error()
			return []

	def downloadSubs(self, fileID, fileName):
		"""
		Request the download link for a subtitle file.
		Returns (download_url, file_name) or (None, None) on failure.
		"""
		try:
			url = base_url + '/download'
			headers = {
				'Content-Type': 'application/json',
				'Api-Key': api_key,
				'Authorization': self.jwt_token,
				'User-Agent': 'luc_kodi v' + version
			}
			data = {'file_id': fileID}
			response = requests.post(url, headers=headers, json=data, timeout=20)
			response = response.json()
			link = response.get('link')
			xbmc.log('[ luc_kodi ] OpenSubs download link: %s  file: %s' % (link, fileName), xbmc.LOGINFO)
			return link, fileName
		except Exception as e:
			xbmc.log('[ luc_kodi ] downloadSubs EXCEPTION: %s' % str(e), xbmc.LOGINFO)
			return None, None

	def getAccountStatus(self):
		"""
		Test credentials and show download quota info in a dialog.
		Called from Settings → Subtitles → Check Account.
		"""
		try:
			url = base_url + '/login'
			if not self.username or not self.password:
				return control.okDialog(title=40503, message='Please enter your OpenSubtitles username and password.')
			data = {
				'username': self.username,
				'password': self.password,
			}
			headers = {
				'Content-Type': 'application/json',
				'Api-Key': api_key,
				'User-Agent': 'luc_kodi v' + version
			}
			response = requests.post(url, headers=headers, json=data, timeout=20)
			response = response.json()
			responseUser  = response.get('user')
			responseToken = response.get('token')
			username      = self.username
			a_downloads   = responseUser.get('allowed_downloads')
			control.setSetting('opensubstoken', responseToken)
			control.openSettings('14.0', 'plugin.video.luc_kodi')
			return control.okDialog(title=40503, message=control.getLangString(40508) % (username, a_downloads))
		except:
			log_utils.error()
			return control.okDialog(title=40503, message='Error checking OpenSubtitles. Please verify your username and password.')

	def revokeAccess(self):
		"""
		Clear stored OpenSubtitles credentials and token.
		Called from Settings → Subtitles → Revoke Token.
		"""
		try:
			control.homeWindow.setProperty('luc_kodi.updateSettings', 'false')
			control.setSetting('opensubsusername', '')
			control.setSetting('opensubspassword', '')
			control.homeWindow.setProperty('luc_kodi.updateSettings', 'true')
			control.setSetting('opensubstoken', '')
			self.jwt_token = ''
			control.openSettings('14.0', 'plugin.video.luc_kodi')
		except:
			log_utils.error()
