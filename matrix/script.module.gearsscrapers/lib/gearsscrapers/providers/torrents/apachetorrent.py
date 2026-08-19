# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote, unquote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# apachetorrent.com -- Brazilian-Portuguese dubbed/subtitled movie & TV
# torrent site. Real server-rendered WordPress-style search (?s=<query>),
# confirmed live to return genuinely title-filtered results (ported from
# Starfleet's own investigation the same session, see
# resources/lib/torrent_sources.py's search_apachetorrent() docstring for
# the full story on which of a dozen similar-looking PT/ES sites turned out
# to be dead ends instead -- fake non-filtering search backends shared by
# four DonTorrent-mirror clones, a CF-Turnstile wall, an ad-gated
# link-shortener wrapping the actual download, a private tracker requiring
# login). Each listing item needs its own detail-page fetch for the actual
# magnet (never present in the listing itself), resolved in parallel same
# as torlock.py/yourbittorrent.py already do here.
#
# No seed/leech counts anywhere on the site (this is a direct-download
# dubbed-movie catalog, not a tracker-style index) -- min_seeders stays 0
# and seeders is always reported as 0.
#
# NOTE: this whole catalog is Portuguese-dubbed/subtitled by branding
# ("Dublado"/"Legendado" in most release names), so
# source_utils.remove_lang()'s DUBBED/SUBS check -- which fires
# unconditionally, independent of the foreign-audio filter setting -- will
# reject a large fraction of what this scraper finds. That's expected,
# correct behavior for this English-focused module, not a bug in this file.

_RE_ITEM = re.compile(
	r"<h2 class='h6 text-center'><a href='([^']+)'[^>]*>([^<]+?)\s*<br/>\s*\(([^)]*)\)</a></h2>",
	re.IGNORECASE
)
_RE_MAGNET = re.compile(r'(magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\'<>\s]*)', re.IGNORECASE)
_RE_SIZE = re.compile(r"<strong>Tamanho</strong>:\s*([^<]+)<", re.IGNORECASE)


class source:
	priority = 8
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://apachetorrent.com'
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

			html = client.request('%s/?s=%s' % (self.base_link, quote(self.title)), timeout=10)
			if not html: return self.sources

			candidates = []
			for url, name, paren in _RE_ITEM.findall(html):
				yr_m = re.search(r'(19|20)\d{2}', paren or '')
				if yr_m and self.year and yr_m.group(0) != self.year:
					continue
				candidates.append((url, name.strip()))
				if len(candidates) >= 10: break
			if not candidates: return self.sources

			threads = []
			for url, name in candidates:
				threads.append(workers.Thread(self.get_sources, url, name))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('APACHETORRENT')
			return self.sources

	def get_sources(self, page_url, raw_name):
		try:
			detail = client.request(page_url, timeout=8)
			if not detail: return
			mag_m = _RE_MAGNET.search(detail)
			if not mag_m: return
			magnet = mag_m.group(1).replace('&amp;', '&')
			ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
			if not ih_m: return
			hash = ih_m.group(1).lower()

			dn_m = re.search(r'[?&]dn=([^&]+)', magnet)
			if dn_m:
				raw_name = unquote_plus(dn_m.group(1)) or raw_name
			name = source_utils.clean_name(raw_name)

			if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): return
			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
			quality, info = source_utils.get_release_quality(name_info, url)
			sz_m = _RE_SIZE.search(detail)
			if sz_m:
				info.insert(0, sz_m.group(1).strip())
			info = ' | '.join(info)

			self.sources_append({'provider': 'apachetorrent', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('APACHETORRENT')
