# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import sfport

# filemood.com -- DHT crawler index. The result page lists name, infohash (in the link), peers seen and size, so no detail
# page is needed. The first number of "683/283" is how many peers the crawler saw recently and stands in for seeders.

RE_ROW = re.compile(
	r'<td class="dn-title">\s*<p class="filedir">\s*'
	r'<a href="(/[^"]+?-([a-fA-F0-9]{40})\.html)"[^>]*>(.*?)</a>\s*</p>\s*</td>\s*'
	r'<td class="dn-status">\s*<p class="text"[^>]*><b>(\d+)/(\d+)</b></p>\s*</td>\s*'
	r'<td class="dn-size">\s*<p class="text"[^>]*><b>([^<]+)</b>', re.I | re.S)


class source(sfport.Provider):
	name = 'filemood'
	log = 'FILEMOOD'
	priority = 5
	pack_capable = True
	title_only = True

	def fetch(self, query):
		html = client.request('https://filemood.com/result?q=%s' % quote(query), timeout=8)
		if not html: return []
		out = []
		for href, hash, raw_title, n1, n2, size in RE_ROW.findall(html):
			name = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', raw_title)).strip()
			out.append({'name': name, 'hash': hash, 'seeders': int(n1), 'size': size.strip()})
		return out
