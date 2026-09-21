# -*- coding: utf-8 -*-
from caches.main_cache import main_cache
from modules.kodi_utils import logger
from modules.native_torrents import bytes_to_gb, instance_base_url, json_http, normalize_info_hash

ZILEAN_URLS = (
	'https://zilean.stremio.ru',
	'https://zileanfortheweebs.midnightignite.me',
)


def zilean_base_url():
	return instance_base_url('zilean.url', ZILEAN_URLS, 'zilean.custom_url', 2)


def zilean_search_url(imdb_id, media_type, season=None, episode=None):
	base = zilean_base_url()
	if not base or not imdb_id:
		return None
	imdb_id = str(imdb_id).strip()
	if '/dmm/' in base:
		return base
	if media_type == 'movie':
		return '%s/dmm/filtered?ImdbId=%s' % (base, imdb_id)
	return '%s/dmm/filtered?ImdbId=%s&Season=%s&Episode=%s' % (base, imdb_id, int(season), int(episode))


def clear_zilean_cache():
	try:
		main_cache.delete_like('ZILEAN_%')
		return True
	except Exception:
		return False


def _parse_item(raw):
	info_hash = normalize_info_hash(raw.get('info_hash') or raw.get('infoHash') or '')
	name = raw.get('raw_title') or raw.get('filename') or raw.get('name') or ''
	if not info_hash or not name or set(info_hash) == {'0'}:
		return None
	return {
		'hash': info_hash,
		'name': name,
		'size': bytes_to_gb(raw.get('size') or raw.get('filesize')),
		'seeders': 0,
	}


def search_streams(imdb_id, media_type, season=None, episode=None, timeout=15, expiration=24):
	url = zilean_search_url(imdb_id, media_type, season, episode)
	if not url:
		return []
	cache_key = 'ZILEAN_%s' % url
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	items, seen = [], set()
	try:
		response = json_http().get(url, timeout=max(1, int(timeout)))
		response.raise_for_status()
		payload = response.json()
		if not isinstance(payload, list):
			payload = payload.get('files') or payload.get('results') or []
		for raw in payload or []:
			parsed = _parse_item(raw)
			if not parsed or parsed['hash'] in seen:
				continue
			seen.add(parsed['hash'])
			items.append(parsed)
	except Exception as e:
		logger('zilean api', '%s (%s)' % (type(e).__name__, url))
		return []
	main_cache.set(cache_key, items, expiration=expiration)
	return items
