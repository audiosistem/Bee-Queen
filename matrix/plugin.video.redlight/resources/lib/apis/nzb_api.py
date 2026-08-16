# -*- coding: utf-8 -*-
"""
NZB Indexer API - Newznab protocol client.

Works with any indexer exposing the standard Newznab API:
NZBGeek, NZBPlanet, DrunkenSlug, NZBHydra2, Prowlarr, etc.

Settings (per slot 1-3, all under the redlight prefix):
	nzb{n}.enabled - "true" / "false"
	nzb{n}.label   - friendly name shown in menus
	nzb{n}.url     - base URL, e.g. "https://api.nzbgeek.info"
	nzb{n}.key     - Newznab API key

Master toggle: provider.nzb
"""
import hashlib
from urllib.parse import quote as urlquote
from caches.settings_cache import get_setting
from modules.kodi_utils import make_session, logger

session = make_session('https://')

def nzb_link_hash(link):
	"""TorBox usenet cache key — MD5 of the NZB download URL."""
	return hashlib.md5(str(link or '').strip().encode('utf-8')).hexdigest()

NZB_SLOT_COUNT = 3
# Newznab movie + TV categories (2000 movies, 5000 tv)
DEFAULT_CATS = '2000,5000'

class NzbIndexerAPI:
	def __init__(self, slot=1):
		self.slot = slot
		prefix = 'redlight.nzb%d' % slot
		self.enabled = get_setting('%s.enabled' % prefix, 'false') == 'true'
		self.label = get_setting('%s.label' % prefix) or 'NZB Indexer %d' % slot
		self.base_url = (get_setting('%s.url' % prefix) or '').replace('empty_setting', '').strip().rstrip('/')
		self.api_key = (get_setting('%s.key' % prefix) or '').replace('empty_setting', '').strip()

	def is_configured(self):
		return bool(self.base_url and self.api_key)

	def is_active(self):
		return self.enabled and self.is_configured()

	def search(self, query, cat=DEFAULT_CATS, expiration=2):
		if not self.is_configured(): return []
		try:
			from caches.main_cache import cache_object
			string = 'NZB_%s_%s_%s' % (self.slot, urlquote(self.base_url, safe=''), urlquote(query, safe=''))
			return cache_object(self._search, string, [query, cat], json=False, expiration=expiration)
		except Exception:
			return self._search(query, cat)

	def capabilities(self):
		"""Fetch indexer caps - used by Test Connection."""
		try:
			params = {'t': 'caps', 'apikey': self.api_key, 'o': 'json'}
			response = session.get('%s/api' % self.base_url, params=params, timeout=15)
			return response.json()
		except Exception as e:
			return {'error': str(e)}

	def _search(self, query, cat=DEFAULT_CATS):
		params = {'t': 'search', 'apikey': self.api_key, 'q': query, 'o': 'json', 'limit': 100}
		if cat: params['cat'] = cat
		try:
			response = session.get('%s/api' % self.base_url, params=params, timeout=20)
			return self._parse_results(response.json())
		except Exception as e:
			logger('Red Light', 'NZB indexer %s search error: %s' % (self.slot, e))
			return []

	@staticmethod
	def _parse_results(data):
		results = []
		try:
			channel = data.get('channel') or {}
			items = channel.get('item') or []
			if isinstance(items, dict): items = [items]
			for item in items:
				try:
					attrs = {}
					raw_attrs = item.get('newznab:attr') or item.get('attr') or []
					if isinstance(raw_attrs, dict): raw_attrs = [raw_attrs]
					for attr in raw_attrs:
						if isinstance(attr, dict):
							inner = attr.get('@attributes', attr)
							attrs[inner.get('@name') or inner.get('name', '')] = inner.get('@value') or inner.get('value', '')
					enclosure = item.get('enclosure') or {}
					if isinstance(enclosure, list): enclosure = enclosure[0] if enclosure else {}
					enclosure_attrs = enclosure.get('@attributes', enclosure) if isinstance(enclosure, dict) else {}
					link = item.get('link', '') or enclosure_attrs.get('@url') or enclosure_attrs.get('url', '')
					try: size = int(attrs.get('size') or enclosure_attrs.get('@length') or enclosure_attrs.get('length') or 0)
					except: size = 0
					result = {'name': item.get('title', ''), 'size': size, 'category': attrs.get('category', ''),
							'group': attrs.get('group', ''), 'age': item.get('pubDate', ''), 'link': link,
							'grabs': int(attrs.get('grabs') or 0)}
					if result['link'] and result['name']: results.append(result)
				except: pass
		except: pass
		return results

def enabled_slots():
	"""All enabled + configured slot APIs."""
	apis = [NzbIndexerAPI(slot) for slot in range(1, NZB_SLOT_COUNT + 1)]
	return [api for api in apis if api.is_active()]

def search_all(query, cat=DEFAULT_CATS, expiration=2):
	"""Search every enabled slot, merge results, dedupe by release name."""
	if get_setting('redlight.provider.nzb', 'false') != 'true': return []
	seen, merged = set(), []
	for api in enabled_slots():
		try:
			for item in api.search(query, cat=cat, expiration=expiration):
				key = item.get('name', '')
				if key and key not in seen:
					seen.add(key)
					item['indexer'] = api.label
					merged.append(item)
		except: pass
	merged.sort(key=lambda i: i.get('size', 0), reverse=True)
	return merged
