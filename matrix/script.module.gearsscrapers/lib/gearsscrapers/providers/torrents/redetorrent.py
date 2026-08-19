# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote, unquote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# redetorrent.com -- same Brazilian-Portuguese dubbed-catalog
# template/content pool as apachetorrent.py's ApacheTorrent (confirmed
# live: identical image-CDN paths and even identical info_hash values for
# the same title on both sites), but with a richer search-result listing
# that also carries a category badge (Filmes/Séries), used here to skip
# fetching detail pages for the wrong media type outright. Search is a
# plain GET to index.php?s=<query> (custom PHP, not WordPress) -- confirmed
# live to genuinely filter (empty result set for a nonsense query). See
# apachetorrent.py's header comment and Starfleet's own
# resources/lib/torrent_sources.py search_redetorrent()/search_apachetorrent()
# docstrings for the full investigation, including the several similar-
# looking PT/ES sites that turned out to be dead ends instead.
#
# No seed/leech counts anywhere on the site -- min_seeders stays 0 and
# seeders is always reported as 0. Same DUBBED/SUBS caveat as
# apachetorrent.py applies here too: source_utils.remove_lang() will reject
# a large fraction of this catalog unconditionally, by design of this
# English-focused module.

_RE_ITEM = re.compile(
	r"class='capa_lista'>\s*<a href='([^']+)'[^>]*>.*?"
	r"<span class='capa_categoria'>([^<]*)</span>\s*"
	r"<span class='capa_qualidade'>([^<]*)</span>.*?"
	r"<h2 itemprop='headline'>([^<]+)</h2>",
	re.IGNORECASE | re.DOTALL
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
		self.base_link = 'https://redetorrent.com'
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.aliases = data['aliases']
			self.year = data['year']
			is_tv_search = 'tvshowtitle' in data
			if is_tv_search:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = data['title']
				self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			html = client.request('%s/index.php?s=%s' % (self.base_link, quote(self.title)), timeout=10)
			if not html: return self.sources

			candidates = []
			for url, category, _quality_badge, headline in _RE_ITEM.findall(html):
				is_tv = 'rie' in (category or '').strip().lower()  # "Séries"/"Series"
				if is_tv != is_tv_search: continue
				yr_m = re.search(r'(19|20)\d{2}', headline)
				if yr_m and self.year and yr_m.group(0) != self.year:
					continue
				name = re.sub(r'\s*\((19|20)\d{2}\)\s*$', '', headline).strip()
				candidates.append((url, name))
				if len(candidates) >= 10: break
			if not candidates: return self.sources

			threads = []
			for url, name in candidates:
				threads.append(workers.Thread(self.get_sources, url, name))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('REDETORRENT')
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

			self.sources_append({'provider': 'redetorrent', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('REDETORRENT')
