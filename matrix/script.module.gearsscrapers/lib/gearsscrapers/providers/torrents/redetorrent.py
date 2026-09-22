# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote, unquote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# redetorrent.com now permanently redirects to redestorrents.com -- a full
# site rebuild confirmed live 2026-09-11 (old 'capa_lista' listing template
# and ?s=<query> search param both gone). Search moved to a CSRF-token-
# gated ?busca=<query>&token=<token> param -- a missing/bogus token
# silently falls back to the generic unfiltered recent-uploads feed instead
# of erroring, so the token fetch below is not optional. The token looks
# single-use (changes on every homepage fetch, no session/cookie binding
# needed) so it's simplest to just fetch a fresh one right before each
# search. Still the same Brazilian-Portuguese dubbed-catalog content pool
# as apachetorrent.py's ApacheTorrent (confirmed live: identical image-CDN
# paths and even identical info_hash values for the same title on both
# sites). See apachetorrent.py's header comment and Starfleet's own
# resources/lib/torrent_sources.py search_redetorrent()/search_apachetorrent()
# docstrings for the full investigation, including the several similar-
# looking PT/ES sites that turned out to be dead ends instead.
#
# No seed/leech counts anywhere on the site -- min_seeders stays 0 and
# seeders is always reported as 0. Same DUBBED/SUBS caveat as
# apachetorrent.py applies here too: source_utils.remove_lang() will reject
# a large fraction of this catalog unconditionally, by design of this
# English-focused module.
#
# The token is also bound to the PHPSESSID cookie the homepage response
# sets -- a stateless second request (no shared cookie) gets silently
# redirected back to the homepage even with a freshly-fetched, otherwise-
# valid token, confirmed live. client.request(..., output='extended')
# returns (html, code, headers, req_headers, cookie) in one call so the
# homepage's cookie can be threaded into the search request's cookie= arg.

_RE_ITEM = re.compile(
	r'<a href="([^"]+)"\s+class="text-decoration-none cover-link"[^>]*>\s*'
	r'<article class="custom-card"\s+data-title="([^"]*)"\s+data-tipo="([^"]*)"'
	r'\s+data-genero="[^"]*"\s+data-desc="([^"]*)"',
	re.IGNORECASE
)
_RE_TOKEN = re.compile(r'name="token"\s+value="([^"]+)"', re.IGNORECASE)
_RE_MAGNET = re.compile(r'(magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\'<>\s]*)', re.IGNORECASE)
_RE_SIZE = re.compile(r"<strong>Tamanho</strong>:\s*([^<]+)<", re.IGNORECASE)
# redestorrents.com's new detail-page template ("Tamanho do Arquivo"
# instead of the old "Tamanho") -- tried as a fallback only.
_RE_SIZE2 = re.compile(r'<small>Tamanho do Arquivo</small>\s*<strong>([^<]+)</strong>', re.IGNORECASE)


class source:
	priority = 8
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://redestorrents.com'
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

			home_result = client.request('%s/' % self.base_link, output='extended', timeout=10)
			if not home_result: return self.sources
			home_html, _code, _resp_headers, _req_headers, home_cookie = home_result
			tok_m = _RE_TOKEN.search(home_html or '')
			if not tok_m: return self.sources
			search_url = '%s/index.php?busca=%s&token=%s&hp_bot_check=' % (
				self.base_link, quote(self.title), tok_m.group(1))
			html = client.request(search_url, cookie=home_cookie, timeout=10)
			if not html: return self.sources

			candidates = []
			for url, name, category, desc in _RE_ITEM.findall(html):
				is_tv = 'rie' in (category or '').strip().lower()  # "Séries"/"Series"
				if is_tv != is_tv_search: continue
				yr_m = re.search(r'(19|20)\d{2}', desc or '')
				if yr_m and self.year and yr_m.group(0) != self.year:
					continue
				name = (name or '').strip()
				if not name: continue
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
			sz_m = _RE_SIZE.search(detail) or _RE_SIZE2.search(detail)
			if sz_m:
				info.insert(0, sz_m.group(1).strip())
			info = ' | '.join(info)

			self.sources_append({'provider': 'redetorrent', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('REDETORRENT')
