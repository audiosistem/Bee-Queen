# -*- coding: utf-8 -*-
"""Once-per-session toasts when a Meta Account grant is rejected.

Fire only on token refresh HTTP 401 or OAuth `invalid_grant` (Simkl / TMDb Lists
have no refresh step, so an authorised 401 is the equivalent). Timeouts and 5xx
are ignored. Tokens are not cleared — revoke remains the user's action.
"""
import json
from modules import kodi_utils

_PROP = 'redlight.meta_auth_alerted.%s'
_SERVICES = {
	'trakt': ('Trakt', 'trakt'),
	'simkl': ('Simkl', 'simkl'),
	'mdblist': ('MDBList', 'mdblist'),
	'punchplay': ('PunchPlay', 'punchplay'),
	'tmdb': ('TMDb Lists', 'tmdb'),
}


def _user_active(service_id):
	from caches.settings_cache import get_setting
	from modules import settings
	if service_id == 'trakt': return settings.trakt_user_active()
	if service_id == 'simkl': return settings.simkl_user_active()
	if service_id == 'mdblist': return settings.mdblist_user_active()
	if service_id == 'punchplay': return settings.punchplay_user_active()
	if service_id == 'tmdb':
		return get_setting('redlight.tmdb.username', 'empty_setting') not in (None, '', 'empty_setting')
	return False


def is_dead_grant(status_code, body=None):
	try:
		if int(status_code) == 401: return True
	except (TypeError, ValueError):
		pass
	text = ''
	if isinstance(body, dict):
		text = '%s %s' % (body.get('error') or '', body.get('error_description') or body.get('message') or '')
		try: text = '%s %s' % (text, json.dumps(body))
		except Exception: pass
	elif isinstance(body, bytes):
		text = body.decode('utf-8', 'ignore')
	elif body:
		text = str(body)
	return 'invalid_grant' in text.lower()


def clear_alert(service_id):
	try: kodi_utils.clear_property(_PROP % service_id)
	except Exception: pass


def maybe_notify_refresh_failure(service_id, status_code, body=None):
	if service_id not in _SERVICES: return
	if not is_dead_grant(status_code, body): return
	if not _user_active(service_id): return
	prop = _PROP % service_id
	if kodi_utils.get_property(prop) == 'true': return
	kodi_utils.set_property(prop, 'true')
	name, icon_name = _SERVICES[service_id]
	kodi_utils.notification(
		'%s authorisation failed. Revoke and Authorise again in Meta Accounts.' % name,
		8000, kodi_utils.get_icon(icon_name) or kodi_utils.addon_icon())
