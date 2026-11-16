# ported from Starfleet's anime_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import json
from urllib.parse import quote_plus
from gearsscrapers.modules import client
from gearsscrapers.modules import sfport

# nekobt.to -- anime tracker; its own search API (the one its search page calls) gives title, infohash, seeders and size.


class source(sfport.Provider):
	name = 'nekobt'
	log = 'NEKOBT'
	priority = 6
	anime = True
	title_only = True
	pack_capable = False

	def fetch(self, query):
		raw = client.request('https://nekobt.to/api/v1/torrents/search?query=%s' % quote_plus(query), timeout=8)
		if not raw: return []
		rows = ((json.loads(raw) or {}).get('data') or {}).get('results') or []
		out = []
		for t in rows:
			if t.get('deleted') or t.get('hidden'): continue
			out.append({'name': t.get('title') or '', 'hash': (t.get('infohash') or '').lower(), 'seeders': t.get('seeders') or 0,
						'size': t.get('filesize') or ''})
		return out
