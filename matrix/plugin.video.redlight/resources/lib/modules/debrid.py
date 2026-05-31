# -*- coding: utf-8 -*-
import re
from caches.debrid_cache import debrid_cache
from apis.real_debrid_api import RealDebridAPI
from apis.premiumize_api import PremiumizeAPI
from apis.alldebrid_api import AllDebridAPI
from apis.torbox_api import TorBoxAPI
from modules.source_utils import get_external_cache_status
from modules.utils import chunks
from modules.kodi_utils import show_busy_dialog, hide_busy_dialog, notification
from modules.settings import enabled_debrids_check
# from modules.kodi_utils import logger

def debrid_enabled():
	return [
	i[0] for i in [('Real-Debrid', 'rd'), ('Premiumize.me', 'pm'), ('AllDebrid', 'ad'), ('TorBox', 'tb')] if enabled_debrids_check(i[1])]

def debrid_for_ext_cache_check(enabled_debrid=None):
	if not enabled_debrid: enabled_debrid = debrid_enabled()
	return any(i in ['Real-Debrid', 'AllDebrid'] for i in enabled_debrid)

def normalize_debrid_provider(provider):
	if not provider:
		return provider
	if provider.startswith('Uncached '):
		return provider[9:]
	return provider

def downloader_provider_slug(provider):
	provider = normalize_debrid_provider(provider)
	return {
		'Real-Debrid': 'real-debrid',
		'Premiumize.me': 'premiumize.me',
		'AllDebrid': 'alldebrid',
		'TorBox': 'torbox',
	}.get(provider, (provider or '').lower())

def import_pack_api(provider):
	provider = normalize_debrid_provider(provider)
	api_map = {
		'Real-Debrid': RealDebridAPI,
		'Premiumize.me': PremiumizeAPI,
		'AllDebrid': AllDebridAPI,
		'TorBox': TorBoxAPI,
	}
	return api_map.get(provider)()

class ExternalPackSource:
	'''POV-style pack helper: uses source url/hash and debrid API parse_magnet_pack.'''
	def __init__(self, source_dict, meta=None):
		for key, value in source_dict.items():
			setattr(self, key, value)
		self.meta = meta or {}

	def browse_packs(self, download=False):
		provider = normalize_debrid_provider(getattr(self, 'debrid', None) or getattr(self, 'cache_provider', ''))
		api = import_pack_api(provider)
		if not api:
			hide_busy_dialog()
			notification('Unsupported provider for pack download: %s' % (provider or 'Unknown'))
			return None
		show_busy_dialog()
		magnet_fn = getattr(api, 'parse_magnet_pack', None) or api.display_magnet_pack
		pack_choices = magnet_fn(getattr(self, 'url', ''), getattr(self, 'hash', ''))
		hide_busy_dialog()
		if not pack_choices:
			if provider == 'TorBox':
				notification('TorBox: No video files in this pack yet. Try again in a moment.', 4500)
			else:
				notification('Error')
			return None
		pack_choices.sort(key=lambda k: (k.get('filename') or '').lower())
		if download:
			return pack_choices, api
		return pack_choices

def manual_add_magnet_to_cloud(params):
	show_busy_dialog()
	provider = normalize_debrid_provider(params.get('provider', ''))
	debrid_list_modules = [('Real-Debrid', RealDebridAPI), ('Premiumize.me', PremiumizeAPI), ('AllDebrid', AllDebridAPI), ('TorBox', TorBoxAPI)]
	function = [i[1] for i in debrid_list_modules if i[0] == provider][0]
	api = function()
	result = api.create_transfer(params['magnet_url'])
	api.clear_cache()
	hide_busy_dialog()
	if not result or result == 'failed':
		return notification('Failed')
	if provider == 'TorBox':
		label = params.get('display_name') or params.get('name') or ''
		api.monitor_torrent_cloud_ready(result, label)
		return notification('TorBox: Added — you will be notified when it is ready in Cloud', 4500)
	notification('Success')

def query_local_cache(hash_list):
	return debrid_cache.get_many(hash_list) or []

def add_to_local_cache(hash_list, debrid, expires=24):
	debrid_cache.set_many(hash_list, debrid, expires)

def _ad_instant_available(magnet):
	if magnet.get('error'): return False
	for key in ('instant', 'ready'):
		val = magnet.get(key)
		if val is True or val == 1: return True
		if str(val).lower() in ('true', '1', 'yes'): return True
	return False

def _ad_magnet_hash(magnet, fallback=''):
	magnet_hash = (magnet.get('hash') or '').lower()
	if len(magnet_hash) == 40: return magnet_hash
	magnet_uri = magnet.get('magnet') or ''
	match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_uri, re.I)
	if match: return match.group(1).lower()
	match = re.search(r'\b([a-fA-F0-9]{40})\b', magnet_uri)
	if match: return match.group(1).lower()
	fallback = str(fallback).lower()
	return fallback if len(fallback) == 40 else ''

def cached_check(hash_list, cached_hashes, debrid):
	cached_list = [i[0] for i in cached_hashes if i[1] == debrid and i[2] == 'True']
	unchecked_list = [i for i in hash_list if not any([h for h in cached_hashes if h[0] == i and h[1] == debrid and h[2] == 'True'])]
	return cached_list, unchecked_list

def RD_check(hash_list, cached_hashes, data, active_debrid):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'rd')
	if unchecked_hashes:
		results = get_external_cache_status('Real-Debrid', unchecked_hashes, data, active_debrid)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				for h in unchecked_hashes:
					cached = 'False'
					if h in results:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'rd', expires)
	return cached_hashes

def AD_check(hash_list, cached_hashes, data, active_debrid):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'ad')
	if unchecked_hashes:
		cached_results = set()
		api = AllDebridAPI()
		api_responded = False
		for hash_chunk in chunks(unchecked_hashes, 100):
			try:
				response = api.check_cache(hash_chunk)
				if not response or 'magnets' not in response: continue
				api_responded = True
				for idx, magnet in enumerate(response['magnets']):
					if not _ad_instant_available(magnet): continue
					magnet_hash = _ad_magnet_hash(magnet, hash_chunk[idx] if idx < len(hash_chunk) else '')
					if magnet_hash: cached_results.add(magnet_hash)
			except: pass
		if not api_responded:
			cached_hashes.extend(unchecked_hashes)
			return cached_hashes
		remaining = [h for h in unchecked_hashes if h not in cached_results]
		if remaining:
			try:
				fallback = get_external_cache_status('AllDebrid', remaining, data, active_debrid) or []
				cached_results.update(i.lower() for i in fallback)
			except: pass
		cached_append = cached_hashes.append
		process_list = []
		process_append = process_list.append
		for h in unchecked_hashes:
			cached = 'False'
			if h in cached_results:
				cached_append(h)
				cached = 'True'
			process_append((h, cached))
		if not cached_results: expires = 2
		add_to_local_cache(process_list, 'ad', expires)
	return cached_hashes

def PM_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'pm')
	if unchecked_hashes:
		results = PremiumizeAPI().check_cache(unchecked_hashes)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				results = results['response']
				for c, h in enumerate(unchecked_hashes):
					cached = 'False'
					try:
						if results[c] is True:
							cached_append(h)
							cached = 'True'
					except: pass
					process_append((h, cached))
			except:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'pm', expires)
	return cached_hashes

def TB_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'tb')
	if unchecked_hashes:
		results = TorBoxAPI().check_cache(unchecked_hashes)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				data = results['data']
				results = [i['hash'] for i in data]
				for h in unchecked_hashes:
					cached = 'False'
					if h in results:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'tb', expires)
	return cached_hashes
