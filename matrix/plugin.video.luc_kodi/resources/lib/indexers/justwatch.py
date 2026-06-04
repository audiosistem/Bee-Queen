"""
Minimal JustWatch GraphQL bridge for the Streaming category.

This is an OPTIONAL alternative path to TMDb's discover/watch_providers endpoint,
activated by the 'streaming.use_justwatch' setting. Used because TMDb's watch_providers
data has known title->ID matching issues for some providers (notably Disney+) due to
limitations in the daily JustWatch->TMDb export.

Returns a list of TMDb movie IDs (as strings) that the existing tmdb pipeline can
enrich into full menu items via get_movie_meta().

NOTE: This uses JustWatch's internal GraphQL endpoint, which is unofficial and may
break or be rate-limited at any time. Some IPs (cloud datacenter ranges) are blocked
by JustWatch's anti-scraping. From a normal home/mobile IP this should work fine.
"""

import requests

_JW_GRAPHQL_URL = 'https://apis.justwatch.com/graphql'

# Browser-like headers help avoid 403 from JustWatch's anti-scraping.
_JW_HEADERS = {
	'Accept': 'application/json, text/plain, */*',
	'Accept-Language': 'en-US,en;q=0.5',
	'Content-Type': 'application/json',
	'App-Version': '3.7.1-web-web',
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
	'Referer': 'https://www.justwatch.com/',
	'Origin': 'https://www.justwatch.com',
}

# Maps a TMDb watch_provider ID (used elsewhere in the addon) to JustWatch's 3-letter
# package short_name (used by their GraphQL filter). Mapping is for US region.
# Some codes are confirmed, some are best-guesses based on JustWatch URL slugs.
# If a provider returns empty results, the short_name is likely wrong here.
TMDB_TO_JW_PACKAGE = {
	8:    'nfx',  # Netflix
	9:    'amp',  # Amazon Prime Video
	337:  'dnp',  # Disney+
	1899: 'mxx',  # Max (formerly HBO Max)
	15:   'hlu',  # Hulu
	350:  'atp',  # Apple TV+
	531:  'pmp',  # Paramount+
	386:  'pct',  # Peacock Premium
	37:   'sho',  # Showtime
	43:   'stz',  # Starz
	526:  'amn',  # AMC+
	283:  'cru',  # Crunchyroll
	11:   'mbi',  # MUBI
	99:   'shd',  # Shudder
	151:  'bbx',  # BritBox
	520:  'dnw',  # discovery+
	257:  'fbt',  # fuboTV
	34:   'hmn',  # Hallmark Movies Now
	73:   'tbv',  # Tubi
	300:  'plt',  # Pluto TV
	207:  'rkc',  # The Roku Channel
	87:   'aor',  # Acorn TV
	12:   'crk',  # Crackle
	191:  'kan',  # Kanopy
	538:  'plx',  # Plex
}

# Lean query: only the fields we actually use. Skips offers/scoring/posters/etc that
# the full library fetches, keeping the response small and fast.
_POPULAR_QUERY = """
query GetPopularTitles($country: Country!, $language: Language!, $first: Int!, $filter: TitleFilter!) {
  popularTitles(country: $country, first: $first, filter: $filter, sortBy: POPULAR, sortRandomSeed: 0) {
    edges {
      node {
        content(country: $country, language: $language) {
          externalIds { tmdbId }
        }
      }
    }
  }
}
"""


def popular_movie_tmdb_ids(jw_package_code, country='US', count=60):
	"""Fetch popular movies for a JustWatch package and return their TMDb IDs.

	Returns a list of TMDb movie IDs (strings). Empty list on any error (HTTP 4xx,
	network failure, malformed response). Designed for use with cache.get().
	"""
	if not jw_package_code:
		return []
	payload = {
		'operationName': 'GetPopularTitles',
		'variables': {
			'country': country,
			'language': 'en',
			'first': int(count),
			'filter': {
				'packages': [jw_package_code],
				'objectTypes': ['MOVIE'],
			},
		},
		'query': _POPULAR_QUERY,
	}
	try:
		r = requests.post(_JW_GRAPHQL_URL, json=payload, headers=_JW_HEADERS, timeout=15)
		r.raise_for_status()
		data = r.json()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return []

	try:
		edges = (((data or {}).get('data') or {}).get('popularTitles') or {}).get('edges') or []
	except Exception:
		return []

	tmdb_ids = []
	for edge in edges:
		try:
			content = ((edge or {}).get('node') or {}).get('content') or {}
			ext = content.get('externalIds') or {}
			tid = ext.get('tmdbId')
			if tid:
				tmdb_ids.append(str(tid))
		except Exception:
			continue
	return tmdb_ids
