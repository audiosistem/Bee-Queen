# -*- coding: utf-8 -*-
"""
	jacksparrowscrapers Project — MediaFusion scraper (v5+ format)

	MediaFusion v5 API:
	  - secret_str token embedded in URL path
	  - Server does IMDB-based matching — no client-side title check needed
	  - Streams return url (streaming_provider proxy) NOT infoHash
	  - Hash extracted from URL path: /playback/Provider/<40-hex-hash>
	  - Description format: '🎨 HDR\\n📺 BluRay\\n📦 52 GB 👤 68\\n🌐 English\\n🔗 Source'
	  - name field: 'MediaFusion | Instance PM 🧲 PM ⚡️ 2160P'
"""

from json import loads as jsloads
import re, queue, os
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting


# Quality keywords in MediaFusion name / description
_QUAL_MAP = [
	('2160', '4K'), ('4k', '4K'), ('uhd', '4K'),
	('1080', '1080p'), ('fhd', '1080p'),
	('720', '720p'), ('hd', '720p'),
	('480', 'SD'), ('sd', 'SD'),
]
_CODEC_MAP = {
	'av1': 'AV1', 'hevc': 'HEVC', 'x265': 'HEVC', 'h265': 'HEVC',
	'x264': 'H264', 'h264': 'H264', 'avc': 'H264',
	'hdr10+': 'HDR10+', 'hdr10': 'HDR', 'hdr': 'HDR',
	'dolby vision': 'DV', 'dovi': 'DV',
	'10bit': '10BIT', '10 bit': '10BIT',
	'atmos': 'ATMOS',
}
_SRC_MAP = {
	'bluray remux': 'REMUX', 'blu-ray remux': 'REMUX',
	'bluray': 'BLURAY', 'blu-ray': 'BLURAY', 'bdrip': 'BLURAY',
	'web-dl': 'WEBDL', 'webdl': 'WEBDL', 'webrip': 'WEBRIP',
	'hdtv': 'HDTV', 'cam': 'CAM', 'scr': 'SCR',
}


def _parse_quality(name_str, desc_str):
	"""Extract quality string from MediaFusion name + description."""
	combined = (name_str + ' ' + desc_str).lower()
	for kw, q in _QUAL_MAP:
		if kw in combined:
			return q
	return 'SD'


def _parse_info_tags(desc_str):
	"""Extract codec/source/HDR tags from MediaFusion description."""
	tags = []
	d = desc_str.lower()
	for kw, tag in _CODEC_MAP.items():
		if kw in d and tag not in tags:
			tags.append(tag)
	for kw, tag in _SRC_MAP.items():
		if kw in d and tag not in tags:
			tags.append(tag)
	return tags


class source:
	timeout = 25
	priority = 2
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_queue = queue.SimpleQueue()

	def __init__(self):
		self.language = ['en']
		try:
			instance_idx = int(getSetting('mediafusion.url') or '0')
		except Exception:
			instance_idx = 0
		_INSTANCES = [
			'https://mediafusionfortheweebs.midnightignite.me',
			'https://mediafusion.elfhosted.com',
		]
		self.base_link  = _INSTANCES[instance_idx] if instance_idx < len(_INSTANCES) else _INSTANCES[0]
		self.secret_str = getSetting('mediafusion.secret') or ''
		self.movieSearch_link = '/stream/movie/%s.json'
		self.tvSearch_link    = '/stream/series/%s:%s:%s.json'
		self.min_seeders = 0

	def _build_url(self, template, *args):
		endpoint = template % args
		if self.secret_str:
			return '%s/%s%s' % (self.base_link, self.secret_str.strip('/'), endpoint)
		return '%s%s' % (self.base_link, endpoint)

	def _fetch(self, url):
		"""Fetch streams from MediaFusion, automatically paginating to get all results."""
		all_streams = []
		seen_hashes = set()
		page = 1
		while True:
			try:
				paged_url = '%s?page=%d' % (url, page) if page > 1 else url
				results = client.request(paged_url, timeout=self.timeout)
				if not results:
					break
				data = jsloads(results)
				streams = data.get('streams', [])
				if not streams:
					break
				# Deduplicate by hash
				new_streams = []
				for s in streams:
					url_field = s.get('url', '')
					bh_file = s.get('behaviorHints', {}).get('filename', '')
					m = re.search(r'/([0-9a-fA-F]{40})', url_field)
					h = m.group(1) if m else s.get('infoHash', '')
					key = h or bh_file
					if key and key not in seen_hashes:
						seen_hashes.add(key)
						new_streams.append(s)
				if not new_streams:
					break  # No new results — stop paginating
				all_streams.extend(new_streams)
				# Stop if this page returned fewer than expected (last page)
				if len(streams) < 5 or page >= 10:
					break
				page += 1
			except Exception:
				source_utils.scraper_error('MEDIAFUSION')
				break
		return all_streams

	def _parse_files(self, files, season=None, pack_mode=False,
	                 search_series=False, total_seasons=None,
	                 bypass_filter=False, title=None, aliases=None,
	                 year=None, imdb=None):
		"""
		Parse MediaFusion v5 stream list.
		Title matching is skipped — MediaFusion already matched by IMDB ID.
		Pack filtering still applied for sources_packs.
		"""
		sources = []

		for file in files:
			try:
				# --- Hash: extract from URL path /playback/Provider/<hash> ---
				url_field = file.get('url', '')
				m = re.search(r'/([0-9a-fA-F]{40})', url_field)
				if not m:
					# fallback: infoHash field (future-proofing)
					hash_val = file.get('infoHash', '')
				else:
					hash_val = m.group(1)
				if not hash_val:
					continue

				name_field = file.get('name', '')    # e.g. "MediaFusion | Midnight PM ⚡️ 2160P"
				desc_field = file.get('description', '')  # e.g. "🎨 HDR10+\n📺 BluRay\n📦 52 GB 👤 68\n🌐 English\n🔗 Knaben"
				# Real torrent filename from behaviorHints (e.g. "Sinners.2025.2160p.UHD.4KBluRay.Remux.HEVC.mkv")
				bh_filename = file.get('behaviorHints', {}).get('filename', '')

				# --- Seeders from description 👤 ---
				seeders = 0
				try:
					seeders = int(re.search(r'👤\s*(\d+)', desc_field).group(1))
					if self.min_seeders and seeders < self.min_seeders:
						continue
				except Exception:
					pass

				# --- Quality ---
				quality = _parse_quality(name_field, desc_field)

				# --- Info tags (codec, source, HDR) ---
				info = _parse_info_tags(desc_field)

				# --- Size from 📦 ---
				dsize = 0
				try:
					size_m = re.findall(
						r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))',
						desc_field
					)
					if size_m:
						dsize, isize = source_utils._size(size_m[0])
						info.insert(0, isize)
				except Exception:
					pass

				# --- Source label from 🔗 ---
				src_label = ''
				try:
					src_m = re.search(r'🔗\s*(.+)', desc_field)
					if src_m:
						src_label = src_m.group(1).strip()
						if src_label and src_label not in info:
							info.append(src_label)
				except Exception:
					pass

				info_str = ' | '.join(info)

				magnet = 'magnet:?xt=urn:btih:%s&dn=mediafusion' % hash_val

				# Build a richer display name: quality + key codec/source tags
				_name_tags = [quality]
				for _t in ('HDR10+', 'HDR', 'DV', 'AV1', 'HEVC', 'REMUX', 'BLURAY', 'WEBDL', 'WEBRIP'):
					if _t in info: _name_tags.append(_t)
				if src_label: _name_tags.append(src_label)
				_synthetic_name = 'MediaFusion ' + ' | '.join(_name_tags)

				# Use the real torrent filename if available (strip extension), else synthetic.
				# If filename contains non-ASCII chars (Cyrillic, etc.) try to extract
				# the English part after a " / " separator, else fall back to synthetic.
				if bh_filename:
					_base = os.path.splitext(bh_filename)[0]
					try:
						_base.encode('ascii')
						display_name = _base  # Pure ASCII, use as-is
					except UnicodeEncodeError:
						# Non-ASCII: look for "Russian / English" pattern
						if ' / ' in _base:
							_en = _base.split(' / ', 1)[1].strip()
							try:
								_en.encode('ascii')
								display_name = _en
							except UnicodeEncodeError:
								display_name = _synthetic_name
						else:
							display_name = _synthetic_name
				else:
					display_name = _synthetic_name

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'mediafusion', 'url': magnet, 'hash': hash_val,
					'name': display_name, 'name_info': '.%s.' % quality.lower(),
					'quality': quality, 'info': info_str, 'size': dsize, 'seeders': seeders,
				}

				# Pack fields for sources_packs
				if pack_mode:
					item['package'] = 'show' if search_series else 'season'
					if search_series and total_seasons:
						item['last_season'] = total_seasons

				sources.append(item)
			except Exception:
				source_utils.scraper_error('MEDIAFUSION')

		return sources

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		try:
			is_episode = 'tvshowtitle' in data
			imdb    = data['imdb']
			year    = data['year']
			title   = data['tvshowtitle'] if is_episode else data['title']
			aliases = data['aliases']
			if is_episode:
				season  = data['season']
				episode = data['episode']
				url = self._build_url(self.tvSearch_link, imdb, season, episode)
			else:
				season = None
				url = self._build_url(self.movieSearch_link, imdb)
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources
		files = self._fetch(url)
		try:
			self._queue.put_nowait(files)
			self._queue.put_nowait(files)
		except Exception:
			pass
		return self._parse_files(files, season=season if is_episode else None,
		                         title=title, aliases=aliases, year=year, imdb=imdb)

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data: return sources
		try:
			title   = data['tvshowtitle']
			aliases = data['aliases']
			imdb    = data['imdb']
			year    = data['year']
			season  = data['season']
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources
		try:
			files = self._queue.get(timeout=self.timeout + 1)
		except Exception:
			source_utils.scraper_error('MEDIAFUSION')
			return sources
		return self._parse_files(files, season=season, pack_mode=True,
		                         search_series=search_series, total_seasons=total_seasons,
		                         bypass_filter=bypass_filter, title=title,
		                         aliases=aliases, year=year, imdb=imdb)
