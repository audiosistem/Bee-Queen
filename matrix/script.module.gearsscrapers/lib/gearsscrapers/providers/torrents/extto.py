# ported from Starfleet's torrent_sources.py for gearsscrapers
# extto.com ("EXT Torrents") -- magnets aren't in the search-result HTML, each
# torrent needs a per-item HMAC-signed AJAX call (client-side SHA256, the
# "secret" pageToken is embedded in that torrent's own detail-page HTML --
# cosmetic anti-scraping, not real access control, confirmed reproducible).
"""
	gearsscrapers Project
"""

import re, time, hashlib, html as _html_mod, json as jsloads
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

_CAT = {'movie': 1, 'tv': 2}
_RE_ROW_TITLE = re.compile(
	r'<a href="(/[a-z0-9\-]+-(\d+)/)"\s+class="torrent-title-link"[^>]*data-tooltip="([^"]+)"', re.IGNORECASE)
_RE_SEEDS = re.compile(r'file_upload</i>\s*<span[^>]*>(\d+)</span>')
_RE_SIZE = re.compile(r'storage</i>\s*<span>([^<]+)</span>')
_RE_TOKEN = re.compile(r'pageToken\s*=\s*["\']([^"\']+)["\']')
_RE_CSRF = re.compile(r'csrfToken\s*=\s*["\']([^"\']+)["\']')


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://extto.com'
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
				cat = _CAT['tv']
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
				cat = _CAT['movie']
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			query = '%s %s' % (self.title, self.hdlr)
			url = '%s/browse/?q=%s&cat=%d&sort=seeds&order=desc' % (self.base_link, quote(query), cat)
			html = client.request(url, timeout=10)
			if not html: return self.sources

			candidates = []
			for m in _RE_ROW_TITLE.finditer(html):
				if len(candidates) >= 8: break
				path, torrent_id, tooltip = m.group(1), m.group(2), m.group(3)
				name = source_utils.clean_name(re.sub(r'<[^>]+>', '', _html_mod.unescape(tooltip)).strip())
				if not name: continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				start = m.end()
				block = html[start:start + 4500]
				seeds_m = _RE_SEEDS.search(block)
				candidates.append({'path': path, 'id': torrent_id, 'name': name, 'seeds': int(seeds_m.group(1)) if seeds_m else 0})

			threads = []
			for c in candidates:
				threads.append(workers.Thread(self.get_sources, c))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('EXTTO')
			return self.sources

	def get_sources(self, c):
		try:
			# extto's AJAX magnet endpoint requires the PHPSESSID cookie set
			# by the detail page's own GET -- client.request() makes each
			# call statelessly with no shared cookie jar, so the POST below
			# must reuse the SAME requests.Session as the GET or the site
			# rejects it with {"success":false,"error":"Invalid session"}.
			import requests
			sess = requests.Session()
			sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
			detail_resp = sess.get(self.base_link + c['path'], timeout=8)
			detail_html = detail_resp.text
			if not detail_html: return
			tok_m = _RE_TOKEN.search(detail_html)
			csrf_m = _RE_CSRF.search(detail_html)
			if not tok_m or not csrf_m: return
			timestamp = int(time.time())
			hmac_token = hashlib.sha256(('%s|%d|%s' % (c['id'], timestamp, tok_m.group(1))).encode('utf-8')).hexdigest()
			resp_obj = sess.post(
				self.base_link + '/ajax/getTorrentMagnet.php',
				data={'torrent_id': c['id'], 'download_type': 'magnet', 'timestamp': timestamp, 'hmac': hmac_token, 'sessid': csrf_m.group(1)},
				headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': self.base_link + c['path']}, timeout=8)
			resp = resp_obj.text
			if not resp: return
			payload = jsloads.loads(resp)
			if not payload.get('success'): return
			magnet = payload.get('url') or ('magnet:?xt=urn:btih:%s' % payload['hash'] if payload.get('hash') else '')
			if not magnet: return
			ih_m = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
			hash = ih_m.group(1).lower() if ih_m else ''
			if not hash: return

			name = c['name']
			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			quality, info = source_utils.get_release_quality(name_info, magnet)
			info = ' | '.join(info)
			self.sources_append({'provider': 'extto', 'source': 'torrent', 'seeders': c['seeds'], 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': magnet, 'info': info,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('EXTTO')
