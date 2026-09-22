# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re, time, html as _html_mod
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

_MIRRORS = [
	'torrentgalaxy-official.is', 'torrentgalaxy.one', 'torrentgalaxy.info',
	'torrentgalaxy.hair', 'torrentgalaxy.mx', 'torrentgalaxy.to', 'tgx.rs',
]
_working = {}

# TorrentGalaxy moved search off the old /torrents.php?search= listing
# (silently ignores the query now, just shows the recent-uploads feed) to
# /get-posts/keywords:<query>, and no longer inlines a magnet: link on the
# listing page at all -- only a per-result /post-detail/ page link, which
# itself has the real magnet plus total size in static HTML. Ported from
# Starfleet's torrent_sources.py search_torrentgalaxy() rewrite, confirmed
# live 2026-09-11 (the previous "en.<mirror>/movies?keyword=" approach this
# file used doesn't even resolve DNS any more).
_RE_ROW = re.compile(r'href="(/post-detail/[a-f0-9]+/[^"]+)"><span\s+src="torrent"><b>([^<]+)</b>')
_RE_MAGNET = re.compile(r'href="(magnet:[^"]+)"', re.IGNORECASE)
_RE_SIZE_DETAIL = re.compile(r'Total Size:</b></div>\s*<div class="tpcell">([^<]+)</div>')
_RE_SIZE = re.compile(r'(\d+(?:[,.]\d+)?)\s*(GiB|MiB|GB|MB)', re.IGNORECASE)
_RE_SKIP_LANG = re.compile(r'\b(FRENCH|TRUEFRENCH|ITALIAN|Ita|SPANISH|DUBBED|LAT|Dublado)\b', re.IGNORECASE)


def _get_base():
	cached = _working.get('url')
	ts = _working.get('ts', 0)
	if cached and (time.time() - ts) < 3600:
		return cached
	for mirror in _MIRRORS:
		try:
			url = 'https://%s' % mirror
			# torrentgalaxy-official.is (first in the list) is a dead decoy
			# landing page whose own title/description literally say
			# "torrent" repeatedly despite zero real listings -- a loose
			# 'torrent' in html.lower() check locks onto it forever and
			# never falls through to torrentgalaxy.one, which has real
			# results. Requiring an actual magnet: link is a real
			# functional check. Ported from Starfleet's torrent_sources.py
			# fix, confirmed live 2026-09-11.
			html = client.request(url + '/torrents.php', timeout=7)
			if html and 'magnet:' in html:
				_working['url'] = url
				_working['ts'] = time.time()
				return url
		except Exception:
			continue
	return 'https://' + _MIRRORS[0]


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = _get_base()
		self.min_seeders = 0

	def sources(self, data, hostDict):
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

			query = '%s %s' % (self.title, self.hdlr)
			url = '%s/get-posts/keywords:%s' % (self.base_link, quote(query))
			html = client.request(url, timeout=10)
			if not html: return self.sources

			candidates = []
			for href, raw_name in _RE_ROW.findall(html):
				if len(candidates) >= 8: break
				name = source_utils.clean_name(_html_mod.unescape(raw_name).strip())
				if not name or _RE_SKIP_LANG.search(name): continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				detail_url = href if href.startswith('http') else self.base_link + href
				candidates.append((detail_url, name))
			if not candidates: return self.sources

			threads = []
			for detail_url, name in candidates:
				threads.append(workers.Thread(self.get_sources, detail_url, name))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORRENTGALAXY')
			return self.sources

	def get_sources(self, detail_url, name):
		try:
			detail = client.request(detail_url, timeout=10)
			if not detail: return
			mag_m = _RE_MAGNET.search(detail)
			if not mag_m: return
			magnet = _html_mod.unescape(mag_m.group(1))
			ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
			if not ih_m: return
			hash = ih_m.group(1).lower()

			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			quality, info = source_utils.get_release_quality(name_info, magnet)
			dsize = 0
			size_m = _RE_SIZE_DETAIL.search(detail)
			if size_m:
				sz_text = size_m.group(1).replace('\xa0', ' ').strip()
				sz_m = _RE_SIZE.search(sz_text)
				if sz_m:
					try:
						dsize, isize = source_utils._size(sz_m.group(0))
						info.insert(0, isize)
					except: pass
			info = ' | '.join(info)

			# Seed/leech counts are fetched by the site's own page via a
			# separate client-side AJAX call after load, not present in the
			# static detail-page HTML -- not worth a third per-item request
			# just for that, so seeders defaults to 0 same as Starfleet's
			# own port of this same fix.
			self.sources_append({'provider': 'torrentgalaxy', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
				'direct': False, 'debridonly': True, 'size': dsize})
		except:
			source_utils.scraper_error('TORRENTGALAXY')
