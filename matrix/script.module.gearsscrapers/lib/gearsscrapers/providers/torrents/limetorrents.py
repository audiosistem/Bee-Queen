# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re, time
import xbmc
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

_MIRRORS = ['https://limetorrents.fun', 'https://www.limetorrents.info', 'https://limetorrents.cc', 'https://limetor.com']
_working = {}

_RE_ROW = re.compile(
	r'<div[^>]+class="[^"]*tt-name[^"]*"[^>]*>.*?'
	r'<a[^>]+href="([^"]+/torrent/[^"]+)"[^>]*></a>.*?'
	r'<a[^>]+>([^<]+)</a>.*?'
	r'<td[^>]+class="[^"]*tdseed[^"]*"[^>]*>([,\d]+)<',
	re.IGNORECASE | re.DOTALL)
_RE_HASH = re.compile(r'/torrent/([a-fA-F0-9]{40})/*', re.IGNORECASE)


def _get_base():
	cached = _working.get('url')
	ts = _working.get('ts', 0)
	if cached and (time.time() - ts) < 3600:
		return cached
	for mirror in _MIRRORS:
		try:
			html = client.request(mirror + '/', timeout=7)
			if html and 'torrent' in html.lower():
				_working['url'] = mirror
				_working['ts'] = time.time()
				return mirror
		except Exception:
			continue
	return _MIRRORS[0]


class source:
	priority = 1
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = _get_base()
		self.min_seeders = 0

	def sources(self, data, hostDict):
		xbmc.log('[SF-DIAG] LIMETORRENTS.sources() called', xbmc.LOGINFO)
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.aliases = data['aliases']
			self.year = data['year']
			if 'tvshowtitle' in data:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = data['title']
				self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = re.sub(r'\s+', '-', self.title.lower())
			query = '%s-%s' % (query, self.hdlr)
			url = '%s/search/all/%s/seeds/1/' % (self.base_link, query)
			html = client.request(url, timeout=10)
			if not html: return self.sources

			threads = []
			for row_m in _RE_ROW.finditer(html):
				path, name, seeds = row_m.group(1), row_m.group(2).strip(), row_m.group(3).replace(',', '')
				name = source_utils.clean_name(name)
				if not name: continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				threads.append(workers.Thread(self.get_sources, path, name, int(seeds)))
			[i.start() for i in threads]
			[i.join() for i in threads]
			xbmc.log('[SF-DIAG] LIMETORRENTS.sources() returning %d results' % len(self.sources), xbmc.LOGINFO)
			return self.sources
		except Exception as e:
			xbmc.log('[SF-DIAG] LIMETORRENTS.sources() exception: %s' % e, xbmc.LOGINFO)
			source_utils.scraper_error('LIMETORRENTS')
			return self.sources

	def get_sources(self, path, name, seeders):
		try:
			ih_m = _RE_HASH.search(path)
			if ih_m:
				hash = ih_m.group(1).lower()
			else:
				detail = client.request(self.base_link + path, timeout=7)
				ih_m2 = re.search(r'magnet:.*?btih:([a-fA-F0-9]{40})', detail, re.IGNORECASE) if detail else None
				hash = ih_m2.group(1).lower() if ih_m2 else ''
			if not hash: return

			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
			quality, info = source_utils.get_release_quality(name_info, url)
			info = ' | '.join(info)
			self.sources_append({'provider': 'limetorrents', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('LIMETORRENTS')
