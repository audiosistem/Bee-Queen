"""
luc_kodi Add-on -- Real-Debrid 2026 keyword-filter compliance module
====================================================================
Around 2026-05-10 Real-Debrid started rejecting playback of cached
torrents whose filename contains certain release-naming keywords
(see the pattern table below; since v1.0.90 it follows the two exact
rules mapped by DMM). The block surfaces as HTTP 451 + error_code: 35
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
RD_FILTER_VERSION = '2026.09.22'

# ---------------------------------------------------------------------
# Pattern table (v1.0.90, 2026.09.22)
# ---------------------------------------------------------------------
# La tabla de mayo (primera lista de ElfHosted) se quedo corta y larga a
# la vez. El mapa completo que publico el desarrollador de DMM el
# 16-may-2026, y que ElfHosted adopto despues en LitterBox, reduce el
# filtro de RD a DOS reglas exactas:
#
#   1) subcadena en cualquier parte del nombre:
#        web-dl | webrip | bdrip | hdrip | dvdrip
#   2) fuente y codec pegados por PUNTO:
#        BluRay.x264 | HDTV.x264 | HDTV.XviD | WEB.x264 | WEB.h264
#
# Todo lo demas PASA en RD, y por eso se retiran de la tabla:
#   - etiquetas de servicio (NF, AMZN, DSNP, ATVP, HMAX, CR, BILI): nunca
#     provocan bloqueo, en ninguna combinacion;
#   - YTS, RARBG, Erai-raws, [rartv]/[eztv]: no estan en el mapa;
#   - WEBDL / WEB.DL (sin guion): pasan; solo bloquea el literal web-dl.
# Asimetrias documentadas que la regla 2 respeta al ser literal:
#   HDTV.h264 pasa (HDTV.x264 no); Blu-Ray.x264 pasa (BluRay.x264 no).
#
# La captura del HTTP 451 + error_code 35 en realdebrid.py sigue siendo
# la segunda linea de defensa: si RD amplia el filtro, el log lo dira.
# ---------------------------------------------------------------------

_RD_FILTER_PATTERN = (
	r'web-dl|webrip|bdrip|hdrip|dvdrip'
	r'|bluray\.x264|hdtv\.x264|hdtv\.xvid|web\.x264|web\.h264'
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
