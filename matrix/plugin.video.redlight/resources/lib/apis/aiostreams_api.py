# -*- coding: utf-8 -*-
# Set True when AIOStreams integration is ready to ship again.
ENABLED = False

import requests
from urllib.parse import urlencode
from caches.settings_cache import get_setting
from modules import kodi_utils
from modules.kodi_utils import logger

# id, short label, base URL (None = Custom; Custom is last in the picker)
PRESETS = (
	('0', 'Kuu', 'https://aiostreams.stremio.ru'),
	('1', 'ElfHosted', 'https://aiostreams.elfhosted.com'),
	('2', 'Yeb', 'https://aiostreams.fortheweak.cloud'),
	('3', 'Midnight', 'https://aiostreamsfortheweebsstable.midnightignite.me'),
	('4', 'Custom', None),
)

INSTANCE_LABELS = {preset_id: label for preset_id, label, url in PRESETS}
_LEGACY_INSTANCE_MAP = {'1': '4', '2': '1', '3': '2', '4': '3'}
CUSTOM_INSTANCE_ID = '4'

PUBLIC_INSTANCES = tuple(url for _, _, url in PRESETS if url)
_PUBLIC_INDEX = {'0': 0, '1': 1, '2': 2, '3': 3}

def instance_id():
	instance_id = str(get_setting('redlight.aiostreams.instance', '0'))
	if get_setting('redlight.aiostreams.instance_schema', '1') != '2':
		instance_id = _LEGACY_INSTANCE_MAP.get(instance_id, instance_id)
		from caches.settings_cache import set_setting
		set_setting('aiostreams.instance', instance_id)
		set_setting('aiostreams.instance_schema', '2')
	return instance_id

def base_url():
	current = instance_id()
	if current == CUSTOM_INSTANCE_ID:
		url = get_setting('redlight.aiostreams.custom_url', '').strip()
	else:
		index = _PUBLIC_INDEX.get(current, 0)
		url = PUBLIC_INSTANCES[index]
	return url.rstrip('/') if url else ''

def refresh_base_url_property():
	url = base_url()
	kodi_utils.set_property('redlight.aiostreams.base_url', url or '(not set — choose instance or enter Custom URL)')

def sync_instance_display_name():
	label = INSTANCE_LABELS.get(instance_id(), INSTANCE_LABELS['0'])
	kodi_utils.set_property('redlight.aiostreams.instance_name', label)

def refresh_settings_properties():
	kodi_utils.set_property('redlight.aiostreams.available', 'true' if ENABLED else 'false')
	instance_id()
	sync_instance_display_name()
	refresh_base_url_property()

def auth():
	username = get_setting('redlight.aiostreams.username', 'empty_setting')
	password = get_setting('redlight.aiostreams.password', 'empty_setting')
	if username in ('empty_setting', '') or password in ('empty_setting', ''): return None
	return (username, password)

def search(media_type, imdb_id, season=None, episode=None, timeout=30):
	credentials = auth()
	if not credentials or not imdb_id: return [], []
	if media_type == 'movie':
		params = {'type': 'movie', 'id': imdb_id}
	else:
		params = {'type': 'series', 'id': '%s:%s:%s' % (imdb_id, season, episode)}
	search_link = '%s/api/v1/search' % base_url()
	try:
		response = requests.get(search_link, params=params, auth=credentials, timeout=timeout)
		if not response.ok: response.raise_for_status()
		payload = response.json().get('data', {})
		errors = [': '.join(i.values()) for i in payload.get('errors', []) if isinstance(i, dict)]
		return payload.get('results', []) or [], errors
	except requests.exceptions.RequestException as e:
		logger('aiostreams API', '%s\n%s' % (e, getattr(getattr(e, 'request', None), 'url', search_link)))
		return [], []

def resolve_playback_url(item):
	url = item.get('url_dl') or item.get('url')
	headers = item.get('request_headers')
	if not url: return None
	if headers: return '%s|%s' % (url, urlencode(headers))
	return url
