# -*- coding: utf-8 -*-
"""WeTrakr scrobble-only integration (device OAuth + Kodi webhook).

Does not sync watched ticks, resume, or lists into Red Light. Prefer
Watched Status Provider = Red Light (or another provider) for UI state.
"""
import json
import time
import requests
from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils, settings
from modules.utils import copy2clip, make_qrcode, make_tinyurl, \
							device_auth_complete_url, device_auth_site_label, authorise_wait_text

BASE_URL = 'https://api.wetrakr.com'
APP_UA = 'RedLight-WeTrakr/%s' % kodi_utils.addon_version()

WETRAKR_TRAKT_IMPORT_URL = 'https://wetrakr.com/profile/settings/data'

WETRAKR_SCROBBLE_ONLY_TEXT = (
	'[B]WeTrakr is scrobble-only in Red Light.[/B][CR][CR]'
	'Authorise under Meta Accounts, then use [B]Enable Scrobbling[/B] to turn sending '
	'play/finish events on or off without revoking.[CR][CR]'
	'When enabled, Red Light tells WeTrakr when you start and finish watching, '
	'so titles can show in WeTrakr (Now Playing / history).[CR][CR]'
	'It does [B]not[/B] bring watched ticks, resume points, Next Episodes, or lists '
	'back into Red Light.[CR][CR]'
	'Use [B]Import Trakt to WeTrakr[/B] to open WeTrakr\'s official import page (QR or link) '
	'if you want history on WeTrakr itself — that still does not change ticks in Red Light.[CR][CR]'
	'Keep [B]Watched Status Provider[/B] on [B]Red Light[/B] (or MDBList / PunchPlay / Simkl / Trakt) '
	'for ticks and lists in the addon.'
)

def _wetrakr_icon():
	return kodi_utils.get_icon('wetrakr') or kodi_utils.addon_icon()

def _token():
	from caches.settings_cache import live_setting
	return live_setting('wetrakr.token', '0')

def wetrakr_user_active():
	return settings.wetrakr_user_active()

def wetrakr_official_status():
	"""False when script.wetrakr should own scrobbling instead."""
	if kodi_utils.service_scrobbler_defer(
		'script.wetrakr',
		auth_keys=('api_token',),
		scrobble_enable_keys=('track_watched', 'track_playing')):
		return False
	return True

def wetrakr_should_scrobble():
	return (wetrakr_user_active() and settings.wetrakr_scrobble_enabled()
		and wetrakr_official_status())

def _parse_int(value):
	if value in (None, '', 'None', 'empty_setting', 0, '0'): return None
	try:
		result = int(value)
		return result if result > 0 else None
	except: return None

def _ids_dict(tmdb_id=None, imdb_id=None, tvdb_id=None):
	ids = {}
	tmdb = _parse_int(tmdb_id)
	tvdb = _parse_int(tvdb_id)
	imdb = str(imdb_id).strip() if imdb_id not in (None, '', 'None', 'empty_setting') else None
	if imdb and not imdb.startswith('tt'): imdb = None
	if tmdb: ids['tmdb'] = tmdb
	if imdb: ids['imdb'] = imdb
	if tvdb: ids['tvdb'] = tvdb
	return ids

def _build_payload(event, media_type, progress=0, title='', year=None, tmdb_id=None,
		imdb_id=None, tvdb_id=None, season=None, episode=None, show_title=None):
	ids = _ids_dict(tmdb_id, imdb_id, tvdb_id)
	progress = round(float(progress or 0), 1)
	if media_type == 'episode':
		return {
			'event': event,
			'media_type': 'episode',
			'title': title or '',
			'show_title': show_title or title or '',
			'show_ids': ids,
			'season': int(season or 0),
			'episode': int(episode or 0),
			'ids': ids,
			'progress': progress
		}
	payload = {
		'event': event,
		'media_type': 'movie',
		'title': title or '',
		'ids': ids,
		'progress': progress
	}
	year_int = _parse_int(year)
	if year_int: payload['year'] = year_int
	return payload

def _post_webhook(payload):
	token = _token()
	if token in (None, '0', '', 'empty_setting'): return False
	url = '%s/webhooks/kodi/%s' % (BASE_URL.rstrip('/'), token)
	headers = {'Content-Type': 'application/json', 'User-Agent': APP_UA}
	try:
		resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=12)
		if 200 <= resp.status_code < 300: return True
		if resp.status_code in (401, 403):
			kodi_utils.logger('WeTrakr', 'Auth rejected (HTTP %s) — re-authorise under Meta Accounts' % resp.status_code)
		else:
			kodi_utils.logger('WeTrakr', 'HTTP %s webhook' % resp.status_code)
	except Exception as e:
		kodi_utils.logger('WeTrakr Error', str(e))
	return False

def wetrakr_send_event(event, media_type, progress=0, title='', year=None, tmdb_id=None,
		imdb_id=None, tvdb_id=None, season=None, episode=None, show_title=None):
	if not wetrakr_should_scrobble(): return False
	if media_type not in ('movie', 'episode'): return False
	if not _ids_dict(tmdb_id, imdb_id, tvdb_id):
		kodi_utils.logger('WeTrakr', 'Skip %s: no ids for %s' % (event, title or media_type))
		return False
	payload = _build_payload(event, media_type, progress, title, year, tmdb_id, imdb_id, tvdb_id,
		season, episode, show_title)
	return _post_webhook(payload)

def wetrakr_scrobble_threshold():
	try: return max(50, min(99, int(get_setting('redlight.wetrakr.scrobble_threshold', '90'))))
	except: return 80

def request_device_code():
	url = '%s/oauth/device/code' % BASE_URL.rstrip('/')
	headers = {'Content-Type': 'application/json', 'User-Agent': APP_UA}
	try:
		resp = requests.post(url, data=b'{}', headers=headers, timeout=15)
		if resp.status_code == 200: return resp.json()
		kodi_utils.logger('WeTrakr', 'device/code HTTP %s' % resp.status_code)
	except Exception as e:
		kodi_utils.logger('WeTrakr Error', str(e))
	return None

def _poll_device_token(device_code):
	url = '%s/oauth/device/token' % BASE_URL.rstrip('/')
	headers = {'Content-Type': 'application/json', 'User-Agent': APP_UA}
	try:
		resp = requests.post(url, data=json.dumps({'device_code': device_code}), headers=headers, timeout=12)
		try: return resp.json()
		except: return {'error': 'http_%s' % resp.status_code}
	except Exception as e:
		kodi_utils.logger('WeTrakr', 'poll error: %s' % e)
		return None

def wetrakr_authenticate(dummy=''):
	if kodi_utils.addon_installed('script.wetrakr') and kodi_utils.addon_enabled('script.wetrakr'):
		try:
			inst = kodi_utils.addon('script.wetrakr')
			ext_token = str(inst.getSetting('api_token') or '').strip()
		except: ext_token = ''
		if ext_token:
			kodi_utils.ok_dialog(heading='WeTrakr',
				text='The official [B]WeTrakr[/B] Kodi add-on is already authorised.[CR][CR]'
				'Red Light will leave scrobbling to that add-on so events are not sent twice.[CR][CR]'
				'Revoke or disable [B]script.wetrakr[/B] if you want Red Light to scrobble instead.')
			return False
	icon = _wetrakr_icon()
	code_data = request_device_code()
	if not code_data or not code_data.get('device_code'):
		return kodi_utils.ok_dialog(heading='WeTrakr',
			text='WeTrakr authorisation failed.[CR]Could not start device authorisation. Try again, or check your connection.')
	user_code = str(code_data.get('user_code') or '')
	device_code = code_data.get('device_code')
	expires_in = int(code_data.get('expires_in') or 600)
	interval = max(int(code_data.get('interval') or 5), 1)
	auth_url = device_auth_complete_url(code_data, user_code, fallback='https://wetrakr.com/activate', style='query')
	qr_code = make_qrcode(auth_url) or icon
	try: copy2clip(auth_url)
	except: pass
	short_url = make_tinyurl(auth_url)
	content = authorise_wait_text(user_code, device_auth_site_label(code_data, 'https://wetrakr.com/activate'), short_url)
	progress = kodi_utils.progress_dialog('WeTrakr Authorise', qr_code)
	progress.update(content, 0)
	expires = time.time() + expires_in
	token, username, canceled = None, None, False
	while time.time() < expires:
		if progress.iscanceled():
			canceled = True
			break
		data = _poll_device_token(device_code)
		if data:
			if data.get('access_token'):
				token = data['access_token']
				username = data.get('username') or 'WeTrakr User'
				break
			error = data.get('error') or ''
			if error == 'expired_token': break
			if error and error not in ('authorization_pending', 'slow_down'):
				kodi_utils.logger('WeTrakr', 'poll: %s' % error)
		progress.update(content, int(100 * (1 - (expires - time.time()) / float(expires_in))))
		if kodi_utils.sleep_while_authorising(progress, interval):
			canceled = True
			break
	try: progress.close()
	except: pass
	if canceled:
		return kodi_utils.notification('WeTrakr Authorisation Canceled', 3000, icon)
	if not token:
		return kodi_utils.notification('WeTrakr Error Authorising', 3000, icon)
	set_setting('wetrakr.token', token)
	set_setting('wetrakr.user', str(username))
	from caches.settings_cache import settings_cache
	settings_cache.clear_db_cache()
	kodi_utils.notification('WeTrakr Account Authorised', 3000, icon)
	try: kodi_utils.container_refresh()
	except: pass
	return True

def wetrakr_revoke_authentication(dummy=''):
	if not kodi_utils.confirm_revoke('WeTrakr'): return
	set_setting('wetrakr.user', 'empty_setting')
	set_setting('wetrakr.token', '0')
	kodi_utils.notification('WeTrakr Authorisation Reset', 3000, _wetrakr_icon())
	try: kodi_utils.container_refresh()
	except: pass
	return True

def wetrakr_about(dummy=''):
	kodi_utils.ok_dialog(heading='WeTrakr (Scrobble Only)', text=WETRAKR_SCROBBLE_ONLY_TEXT, scroll=True)
	return True

def wetrakr_import_trakt(params=None):
	from modules.trakt_import_help import open_official_trakt_import_page
	return open_official_trakt_import_page(
		'WeTrakr', WETRAKR_TRAKT_IMPORT_URL,
		icon=_wetrakr_icon(),
		close_hint='. This does not change watched ticks in Red Light',
		fallback_hint='When finished, watched ticks in Red Light still follow Watched Status Provider — not WeTrakr.')
