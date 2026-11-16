# ported from Starfleet's anime_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import json
from urllib.parse import quote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import sfport

# api.tsukihime.org -- public index of anime releases from Nyaa, nekoBT and TokyoTosho with their infohashes (no seed counts).


class source(sfport.Provider):
	name = 'tsukihime'
	log = 'TSUKIHIME'
	priority = 7
	anime = True
	title_only = True
	pack_capable = False

	def fetch(self, query):
		raw = client.request('https://api.tsukihime.org/v1/search/torrents?q=%s&limit=60' % quote_plus(query), timeout=8)
		if not raw: return []
		out = []
		for t in (json.loads(raw) or {}).get('results') or []:
			out.append({'name': t.get('name') or '', 'hash': (t.get('btih') or '').lower(), 'seeders': 0, 'size': t.get('totalsize') or ''})
		return out
