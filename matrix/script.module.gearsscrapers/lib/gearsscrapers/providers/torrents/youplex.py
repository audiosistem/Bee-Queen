# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import json
from urllib.parse import urlencode
from gearsscrapers.modules import client
from gearsscrapers.modules import sfport

# youplex.cc -- one search that asks several torrent indexes (TPB, YTS, Nyaa, LimeTorrents and others) at once. JSON, real
# infohash and seeders for every row, no auth.


class source(sfport.Provider):
	name = 'youplex'
	log = 'YOUPLEX'
	priority = 3
	pack_capable = True

	def fetch(self, query):
		url = 'https://youplex.cc/api/torrents?%s' % urlencode({'q': query, 'category': 'all', 'limit': '60'})
		raw = client.request(url, headers={'Accept': 'application/json'}, timeout=10)
		if not raw: return []
		out = []
		for item in (json.loads(raw) or {}).get('torrents') or []:
			out.append({'name': item.get('title') or '', 'hash': (item.get('id') or item.get('infoHash') or ''),
						'seeders': item.get('seeders') or 0, 'size': item.get('size') or ''})
		return out
