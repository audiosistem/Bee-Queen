# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import hashlib
import re
from urllib.parse import quote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import workers

_RE_ROW = re.compile(
	r'<a[^>]+href="(viewtopic\.php\?t=\d+)"[^>]*>(?:<b>)?([^<]+)(?:</b>)?</a>.*?'
	r'<a href="(download\.php\?id=\d+)"',
	re.IGNORECASE | re.DOTALL)


def _bdecode(data, i=0):
	"""Minimal bencode decoder -- only needs to parse a .torrent file well
	enough to isolate the 'info' dict for hashing, not a general-purpose
	implementation."""
	c = data[i:i + 1]
	if c == b'i':
		end = data.index(b'e', i)
		return int(data[i + 1:end]), end + 1
	if c == b'l':
		i += 1
		items = []
		while data[i:i + 1] != b'e':
			v, i = _bdecode(data, i)
			items.append(v)
		return items, i + 1
	if c == b'd':
		i += 1
		d = {}
		while data[i:i + 1] != b'e':
			k, i = _bdecode(data, i)
			v, i = _bdecode(data, i)
			d[k] = v
		return d, i + 1
	colon = data.index(b':', i)
	length = int(data[i:colon])
	start = colon + 1
	return data[start:start + length], start + length


def _bencode(obj):
	if isinstance(obj, int):
		return b'i' + str(obj).encode() + b'e'
	if isinstance(obj, bytes):
		return str(len(obj)).encode() + b':' + obj
	if isinstance(obj, list):
		return b'l' + b''.join(_bencode(x) for x in obj) + b'e'
	if isinstance(obj, dict):
		out = b'd'
		for k in sorted(obj.keys()):
			out += _bencode(k) + _bencode(obj[k])
		return out + b'e'
	raise TypeError(type(obj))


class source:
	priority = 1
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = 'https://nnmclub.to/forum'
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
			url = '%s/tracker.php?nm=%s' % (self.base_link, quote_plus(query))
			html = client.request(url, timeout=10)
			if not html: return self.sources

			threads = []
			for _topic, name, dl_path in _RE_ROW.findall(html):
				name = source_utils.clean_name(name.strip())
				if not name: continue
				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
				threads.append(workers.Thread(self.get_sources, dl_path, name))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('NNMCLUB')
			return self.sources

	def get_sources(self, dl_path, name):
		"""Search results only link to a download.php redirect (no magnet/hash
		inline), which forwards anonymously (uid=-1, no login required) to a
		real .torrent file. Needs a bencode decode to compute the actual
		info_hash (SHA1 of the bencoded 'info' dict) since the site itself
		never exposes it directly -- one extra fetch per candidate beyond the
		search page itself."""
		try:
			data = client.request('%s/%s' % (self.base_link, dl_path), timeout=10, as_bytes=True)
			if not data: return
			parsed, _pos = _bdecode(data, 0)
			info = parsed.get(b'info')
			if not info: return
			hash = hashlib.sha1(_bencode(info)).hexdigest()

			name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
			if source_utils.remove_lang(name_info, self.check_foreign_audio): return
			if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): return

			url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
			quality, info_str = source_utils.get_release_quality(name_info, url)
			info_str = ' | '.join(info_str)
			self.sources_append({'provider': 'nnmclub', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
				'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info_str,
				'direct': False, 'debridonly': True, 'size': 0})
		except:
			source_utils.scraper_error('NNMCLUB')
