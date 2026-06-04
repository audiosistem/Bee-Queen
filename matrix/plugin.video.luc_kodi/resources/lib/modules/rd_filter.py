"""
luc_kodi Add-on -- Real-Debrid 2026 keyword-filter compliance module
====================================================================
Around 2026-05-10 Real-Debrid started rejecting playback of cached
torrents whose filename contains certain release-naming keywords
(WEB-DL, WEBRip, AMZN, DSNP, NF, YTS, Erai-raws, CR, [rartv]/[rarbg]/
[eztv], RARBG, ...). The block surfaces as HTTP 451 + error_code: 35
from POST /unrestrict/link. The /torrents listing still reports the
item as 'downloaded' so we cannot detect it from the cache check.

Strategy (mirrors ElfHosted's server-side mitigation for AIOStreams):
  - "Fast pass": baked-in filename regex covering documented patterns.
    Drops the bulk of the May-2026 class before they ever reach the
    user as a clickable item.
  - "Defense in depth": realdebrid.py captures HTTP 451 + code 35
    on unrestrict_link and logs the hit so we can refine the regex.

The filter is enabled/disabled via setting `realdebrid.rd2026_filter`
(default true). Only applied to results that would be resolved via
Real-Debrid -- it does NOT touch TorBox, Premiumize, AllDebrid or
Easynews items, which have no equivalent filter today.
"""

import re

# Version tag for the regex table. Bump whenever the pattern list
# changes so debugging and changelogs can correlate user reports.
RD_FILTER_VERSION = '2026.05.15'

# ---------------------------------------------------------------------
# Pattern table
# ---------------------------------------------------------------------
# Sources for the keyword list (cross-referenced 2026-05-15):
#   * ElfHosted blog / LitterBox "fast pass" regex
#       https://store.elfhosted.com/blog/2026/05/12/real-debrid-filtering-may-2026/
#       https://litterbox.elfhosted.com/
#   * TorrentFreak coverage (RD's own DSM Art.17 / FNEF statement)
#   * Reddit r/debridmediamanager megathread
#
# All patterns are anchored at non-word boundaries to avoid false
# positives inside legitimate title words (e.g. 'CR' inside 'Scream',
# 'NF' inside 'Confidant', 'YTS' inside arbitrary text, etc.).
#
# Case-insensitive; the regex flag (?i) is set at compile time.
# ---------------------------------------------------------------------

_RD_FILTER_PATTERN = (
	# Bracketed release-group tags (literal brackets in the filename)
	r'\[(?:rartv|rarbg|eztv)\]'
	# Source markers -- the bulk of the May-2026 hits
	r'|\bWEB[\.\-_]?DL\b'
	r'|\bWEB[\.\-_]?Rip\b'
	r'|\bAMZN\b'
	r'|\bDSNP\b'
	r'|\bNF\b'
	# Scene release names / group tags
	r'|\bYTS(?:\.(?:MX|AM|LT|AG))?\b'
	r'|\bErai[\.\-_]?raws\b'
	r'|\bRARBG\b'
	# 'CR' is risky (short token) -- require it to appear preceded by
	# a separator AND followed by a separator/end, and exclude any
	# adjacent letters to keep it well-bounded.
	r'|(?<![A-Za-z])CR(?![A-Za-z0-9])'
)

_RD_FILTER_RE = re.compile(_RD_FILTER_PATTERN, re.IGNORECASE)


def is_rd_filtered(name):
	"""
	Return True if `name` (typically the torrent release filename) is
	likely to be rejected by Real-Debrid's May-2026 keyword filter.

	Safe on None / empty / non-str. No exceptions raised.
	"""
	if not name:
		return False
	try:
		return bool(_RD_FILTER_RE.search(name))
	except Exception:
		return False


def filter_enabled():
	"""
	Read the user setting. Cached at module level to avoid hitting
	xbmcaddon on every name check in a tight loop.
	"""
	# Lazy import keeps module importable from non-Kodi contexts (tests)
	try:
		from resources.lib.modules import control
		val = control.setting('realdebrid.rd2026_filter')
		# Default ON: empty string (never set) -> enabled
		return val in ('', 'true')
	except Exception:
		return True


def apply_to_torrent_list(torrent_list):
	"""
	Remove items whose `name` matches the RD-2026 filter. Returns a
	new list (does NOT mutate the input list reference).

	Used inside rd_cache_chk_list() in sources.py. The cached torrents
	dictionary is unaffected; we simply drop entries that we know RD
	will refuse to resolve.

	Returns: (filtered_list, removed_count)
	"""
	if not torrent_list:
		return torrent_list, 0
	if not filter_enabled():
		return torrent_list, 0
	kept = []
	removed = 0
	for it in torrent_list:
		nm = it.get('name', '') if isinstance(it, dict) else ''
		if is_rd_filtered(nm):
			removed += 1
			continue
		kept.append(it)
	return kept, removed


def apply_to_direct_list(direct_list):
	"""
	Filter AIOStreams / MediaFusion direct items already resolved
	through Real-Debrid (item['debrid'] starts with 'RD'). Other
	debrid services are left alone. Items with unknown debrid label
	('Custom') are conservatively kept since we cannot tell which
	service resolved them.

	Returns: (filtered_list, removed_count)
	"""
	if not direct_list:
		return direct_list, 0
	if not filter_enabled():
		return direct_list, 0
	kept = []
	removed = 0
	for it in direct_list:
		if not isinstance(it, dict):
			kept.append(it)
			continue
		debrid_label = (it.get('debrid') or '').strip()
		# Only items resolved through Real-Debrid are at risk
		if debrid_label[:2].upper() != 'RD':
			kept.append(it)
			continue
		nm = it.get('name', '')
		if is_rd_filtered(nm):
			removed += 1
			continue
		kept.append(it)
	return kept, removed


def is_error_code_35(response):
	"""
	Detect Real-Debrid's May-2026 infringing_file response. RD returns
	either:
	  - JSON: {"error": "infringing_file", "error_code": 35} (HTTP 451)
	  - or sometimes WAF-wrapped with the same payload nested

	Accepts a dict (already-parsed JSON) or any object exposing .get().
	Safe on None / unexpected shapes -- always returns a bool.
	"""
	if not response:
		return False
	try:
		if isinstance(response, dict):
			if response.get('error_code') == 35:
				return True
			if response.get('error') == 'infringing_file':
				return True
		# String fallback (in case caller passes raw text)
		s = str(response)
		if '"error_code":35' in s.replace(' ', ''):
			return True
		if 'infringing_file' in s:
			return True
	except Exception:
		pass
	return False
