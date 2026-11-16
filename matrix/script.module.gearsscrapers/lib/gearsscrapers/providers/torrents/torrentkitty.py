# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
from urllib.parse import quote
from gearsscrapers.modules import client
from gearsscrapers.modules import sfport

# torrentkitty.tv -- DHT crawler index: every row is a real infohash, but there are no seed counts and no usable sizes.

RE_ROW = re.compile(r'<tr><td class="name">(.*?)</td>.*?href="magnet:\?xt=urn:btih:([0-9A-Fa-f]{40})', re.S)


class source(sfport.Provider):
	name = 'torrentkitty'
	log = 'TORRENTKITTY'
	priority = 7
	pack_capable = True
	title_only = True

	def fetch(self, query):
		html = client.request('https://www.torrentkitty.tv/search/%s/' % quote(query), timeout=8)
		if not html: return []
		out = []
		for raw_title, hash in RE_ROW.findall(html):
			out.append({'name': re.sub(r'<[^>]+>', '', raw_title).strip(), 'hash': hash, 'seeders': 0, 'size': ''})
		return out
