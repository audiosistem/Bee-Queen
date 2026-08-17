# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re, time, html as _html_mod
from urllib.parse import quote_plus, unquote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

_MIRRORS = [
	'torrentgalaxy-official.is', 'torrentgalaxy.one', 'torrentgalaxy.info',
	'torrentgalaxy.hair', 'torrentgalaxy.mx', 'torrentgalaxy.to', 'tgx.rs',
]
_working = {}

_RE_ROW = re.compile(r'<div[^>]+class="[^"]*tgxtable[^"]*"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
_RE_MAGNET = re.compile(r'a\s+href="(magnet:[^"]+)"', re.IGNORECASE)
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
			html = client.request(url + '/torrents.php', timeout=7)
			if html and 'torrent' in html.lower():
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
			# TorrentGalaxy redesigned -- the old /torrents.php?search= path
			# just serves the homepage now. Real search lives on the "en."
			# subdomain at /movies?keyword=... (confirmed live via its own
			# quick-search form markup).
			search_base = self.base_link.replace('https://', 'https://en.', 1)
			url = '%s/movies?keyword=%s' % (search_base, quote_plus(query))
			html = client.request(url, timeout=10)
			if not html: return self.sources

			for row_m in _RE_ROW.finditer(html):
				row_text = row_m.group(1)
				mag_m = _RE_MAGNET.search(row_text)
				if not mag_m: continue
				magnet = _html_mod.unescape(mag_m.group(1))
				if _RE_SKIP_LANG.search(magnet): continue
				ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
				if not ih_m: continue
				hash = ih_m.group(1).lower()
				dn_m = re.search(r'[&?]dn=([^&]+)', magnet)
				name = source_utils.clean_name(unquote(dn_m.group(1)).replace('+', ' ')) if dn_m else hash

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				seeds_m = re.search(r'<span[^>]+>(\d+)</span>\s*seeders', row_text, re.IGNORECASE)
				seeders = int(seeds_m.group(1)) if seeds_m else 0
				if self.min_seeders > seeders: continue

				quality, info = source_utils.get_release_quality(name_info, magnet)
				sz_m = _RE_SIZE.search(row_text)
				dsize = 0
				if sz_m:
					try:
						dsize, isize = source_utils._size(sz_m.group(0))
						info.insert(0, isize)
					except: pass
				info = ' | '.join(info)

				self.sources_append({'provider': 'torrentgalaxy', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
					'direct': False, 'debridonly': True, 'size': dsize})
			return self.sources
		except:
			source_utils.scraper_error('TORRENTGALAXY')
			return self.sources
