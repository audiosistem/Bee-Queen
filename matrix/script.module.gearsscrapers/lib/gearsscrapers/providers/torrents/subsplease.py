# ported from Starfleet's anime_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import json
from urllib.parse import quote_plus, parse_qs, unquote
from gearsscrapers.modules import client
from gearsscrapers.modules import sfport

# subsplease.org -- weekly anime releases (1080p / 720p / 480p). The search API answers with every episode and its magnets.


class source(sfport.Provider):
	name = 'subsplease'
	log = 'SUBSPLEASE'
	priority = 6
	anime = True
	title_only = True
	pack_capable = False

	def fetch(self, query):
		raw = client.request('https://subsplease.org/api/?f=search&tz=UTC&s=%s' % quote_plus(query), timeout=8)
		if not raw: return []
		data = json.loads(raw)
		out = []
		for rel in (data.values() if isinstance(data, dict) else []):
			for d in rel.get('downloads') or []:
				mg = d.get('magnet') or ''
				qs = parse_qs(mg.split('?', 1)[-1])
				name = unquote((qs.get('dn') or [''])[0]) or '[SubsPlease] %s - %s (%sp)' % (rel.get('show'), rel.get('episode'), d.get('res'))
				xl = (qs.get('xl') or [''])[0]
				hash = (qs.get('xt') or [''])[0].split(':')[-1]
				out.append({'name': name, 'hash': hash, 'seeders': 0, 'size': int(xl) if xl.isdigit() else ''})
		return out
