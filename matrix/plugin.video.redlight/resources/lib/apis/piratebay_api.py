# -*- coding: utf-8 -*-
from urllib.parse import quote_plus
from caches.main_cache import main_cache
from modules.kodi_utils import logger
from modules.native_torrents import bytes_to_gb, instance_base_url, json_http, normalize_info_hash

PIRATEBAY_URLS = (
	'https://apibay.org',
)


def piratebay_base_url():
	return instance_base_url('piratebay.url', PIRATEBAY_URLS, 'piratebay.custom_url', 1) or PIRATEBAY_URLS[0]


def piratebay_search_url(query):
	base = piratebay_base_url().rstrip('/')
	if not base or not query:
		return None
	if 'q.php' in base:
		if '%s' in base:
			return base % quote_plus(query)
		sep = '&' if '?' in base else '?'
		return '%s%sq=%s' % (base, sep, quote_plus(query))
	return '%s/q.php?q=%s&cat=0' % (base, quote_plus(query))


def clear_piratebay_cache():
	try:
		main_cache.delete_like('PIRATEBAY_%')
		return True
	except Exception:
		return False


def _parse_item(raw):
	name = (raw.get('name') or '').strip()
	if not name or name.lower() == 'no results returned':
		return None
	info_hash = normalize_info_hash(raw.get('info_hash') or raw.get('infoHash') or '')
	if not info_hash or set(info_hash) == {'0'}:
		return None
	try:
		seeders = int(raw.get('seeders') or 0)
	except Exception:
		seeders = 0
	return {
		'hash': info_hash,
		'name': name,
		'size': bytes_to_gb(raw.get('size')),
		'seeders': seeders,
	}


def search(query, timeout=10, expiration=24):
	query = (query or '').strip()
	if not query:
		return []
	url = piratebay_search_url(query)
	if not url:
		return []
	cache_key = 'PIRATEBAY_%s' % url
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	results, seen = [], set()
	try:
		response = json_http().get(url, timeout=max(1, int(timeout)))
		response.raise_for_status()
		payload = response.json()
		if not isinstance(payload, list):
			payload = []
		for raw in payload:
			parsed = _parse_item(raw)
			if not parsed or parsed['hash'] in seen:
				continue
			seen.add(parsed['hash'])
			results.append(parsed)
	except Exception as e:
		logger('piratebay api', '%s (%s)' % (type(e).__name__, query))
		return []
	main_cache.set(cache_key, results, expiration=expiration)
	return results
