# -*- coding: utf-8 -*-
from caches.main_cache import main_cache
from modules.native_torrents import instance_base_url, search_stremio_streams, stremio_stream_url

MEDIAFUSION_URLS = (
	'https://mediafusionfortheweebs.midnightignite.me',
	'https://mediafusion.elfhosted.com',
)


def mediafusion_base_url():
	return instance_base_url('mediafusion.url', MEDIAFUSION_URLS, 'mediafusion.custom_url', 2)


def mediafusion_stream_url(imdb_id, media_type, season=None, episode=None):
	return stremio_stream_url(mediafusion_base_url(), imdb_id, media_type, season, episode)


def clear_mediafusion_cache():
	try:
		main_cache.delete_like('MEDIAFUSION_%')
		return True
	except Exception:
		return False


def search_streams(imdb_id, media_type, season=None, episode=None, timeout=15, expiration=24):
	return search_stremio_streams(
		mediafusion_stream_url(imdb_id, media_type, season, episode),
		'MEDIAFUSION', timeout=timeout, expiration=expiration, log_name='mediafusion api')
