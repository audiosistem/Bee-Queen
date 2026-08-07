# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

# YourBitTorrent now serves each detail page from a random per-torrent
# subdomain (e.g. http://zuc4p4v.t0r.space/torrent/...) instead of a relative
# path on the search domain -- match the absolute URL directly.
_RE_LINK = re.compile(r'<a[^>]+href="(https?://[^"]+/torrent/[^"]+)"', re.IGNORECASE)
_RE_HASH = re.compile(r'<kbd>([a-fA-F0-9]{40})<', re.IGNORECASE)
_RE_NAME = re.compile(r'<h3 class="card-title">([^<]+)<', re.IGNORECASE)
_RE_SIZE = re.compile(r'File size:</div><div class="col">([^<]+)<', re.IGNORECASE)


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://yourbittorrent2.com'
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
			query_enc = quote_plus(query).replace('+', '-')
			html = client.request('%s?q=%s' % (self.base_link, query_enc), timeout=10)
			if not html: return self.sources

			# each result row repeats the same detail-page href across every
			# column (title, details, magnet, size, added, seed, peers) --
			# dedupe before capping, or the cap just wastes every thread slot
			# re-fetching the same 1-2 torrents.
			seen = []
			for link in _RE_LINK.findall(html):
				if link not in seen:
					seen.append(link)
				if len(seen) >= 10:
					break
			links = seen
			threads = []
			for link in links:
				threads.append(workers.Thread(self.get_sources, link))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('YOURBITTORRENT')
			return self.sources

	def get_sources(self, link):
		try:
			detail = client.request(link, timeout=8)
			if not detail: return
			ih_m = _RE_HASH.search(detail)
			nm_m = _RE_NAME.search(detail)
			if not ih_m or not nm_m: return
			hash = ih_m.group(1).lower()
			name = source_utils.clean_name(nm_m.group(1).strip())

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

			self.sources_append({'provider': 'yourbittorrent', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('YOURBITTORRENT')
