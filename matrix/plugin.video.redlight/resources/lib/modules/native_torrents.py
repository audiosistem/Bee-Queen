# -*- coding: utf-8 -*-
import re
import time
import base64
from urllib.parse import quote_plus
from modules.utils import clean_file_name, normalize
from modules import source_utils

_HASH_HEX = re.compile(r'^[a-f0-9]{40}$')
_BTIH = re.compile(r'btih:([a-zA-Z0-9]+)', re.I)
_SIZE = re.compile(r'((?:\d+,\d+\.\d+|\d+\.\d+|\d+,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', re.I)
_SEEDERS = re.compile(r'(?:👤|seeders?)\s*[:\s]*(\d+)', re.I)
_SXXEXX = re.compile(r's\d{1,2}e\d{1,2}', re.I)
_SEASON_TAG = re.compile(r'(?:s|season)[.\s_-]*(\d{1,2})(?:[^\de]|$)', re.I)
_INFO_LINE = re.compile(r'(💾|👤|⚙️)')
# Named episode ranges (Fenom filter_season_pack equivalents). Season is group 1.
_EPISODE_RANGE = (
	re.compile(r's(\d{1,2})e(\d{1,3})[-.]e(\d{1,3})', re.I),
	re.compile(r's(\d{1,2})e(\d{1,3})[-.](\d{1,3})(?!p|bit|gb)(?!\d{1,3})', re.I),
	re.compile(r's(\d{1,2})[-.]e(\d{1,3})[-.]e(\d{1,3})', re.I),
	re.compile(r'season[.-]?(\d{1,2})[.-]?ep[.-]?(\d{1,3})[-.]ep[.-]?(\d{1,3})', re.I),
	re.compile(r'season[.-]?(\d{1,2})[.-]?episode[.-]?(\d{1,3})[-.]episode[.-]?(\d{1,3})', re.I),
)

NATIVE_INDEXER_SCRAPERS = ('animetosho', 'nyaa', 'piratebay')
NATIVE_SITE_SCRAPERS = ('comet', 'mediafusion', 'torz', 'torrentio', 'zilean')
NATIVE_TORRENT_SCRAPERS = NATIVE_INDEXER_SCRAPERS + NATIVE_SITE_SCRAPERS
NATIVE_SITE_DISPLAY = {
	'animetosho': 'ANIMETOSHO',
	'comet': 'COMET',
	'mediafusion': 'MEDIAFUSION',
	'nyaa': 'NYAA',
	'piratebay': 'PIRATEBAY',
	'torrentio': 'TORRENTIO',
	'torz': 'TORZ',
	'zilean': 'ZILEAN',
}
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

_json_session = None


def json_http():
	global _json_session
	if _json_session is None:
		from modules.kodi_utils import make_session
		_json_session = make_session('https://')
		_json_session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})
	return _json_session


def source_site_label(scrape_provider):
	return 'Indexer' if scrape_provider in NATIVE_INDEXER_SCRAPERS else 'Site'


def normalize_info_hash(value):
	if not value:
		return None
	text = str(value).strip()
	match = _BTIH.search(text)
	if match:
		text = match.group(1)
	text = text.lower()
	if _HASH_HEX.match(text):
		return text
	if len(text) == 32:
		try:
			padded = text.upper() + ('=' * ((8 - (len(text) % 8)) % 8))
			decoded = base64.b32decode(padded)
			if len(decoded) == 20:
				return decoded.hex()
		except Exception:
			return None
	return None


def parse_size_gb(text):
	if not text:
		return 0.0
	match = _SIZE.search(str(text).replace('\xa0', ' '))
	if not match:
		return 0.0
	raw, unit = match.group(1).rsplit(None, 1)
	try:
		value = float(raw.replace(',', ''))
	except Exception:
		return 0.0
	if unit.lower().startswith('m'):
		return round(value / 1024.0, 2)
	return round(value, 2)


def parse_seeders(text):
	if not text:
		return 0
	match = _SEEDERS.search(str(text))
	if not match:
		return 0
	try:
		return int(match.group(1))
	except Exception:
		return 0


def bytes_to_gb(size_bytes):
	try:
		value = float(size_bytes or 0)
	except Exception:
		return 0.0
	if value <= 0:
		return 0.0
	return round(value / 1073741824.0, 2)


def magnet_url(info_hash, name):
	display = quote_plus((name or info_hash).replace(' ', '.'))
	return 'magnet:?xt=urn:btih:%s&dn=%s' % (info_hash, display)


def instance_base_url(setting_id, urls, custom_setting_id=None, custom_index=None):
	from caches.settings_cache import get_setting
	try:
		idx = int(get_setting('redlight.%s' % setting_id, '0'))
	except (TypeError, ValueError):
		idx = 0
	if custom_index is not None and idx == custom_index:
		custom = (get_setting('redlight.%s' % custom_setting_id, '') or '').strip().rstrip('/')
		return custom
	if idx < 0 or idx >= len(urls):
		idx = 0
	return urls[idx]


_INVALID_IMDB = ('', 'none', 'null', '0', 'tt0000000', 'tt0', 'empty_setting')
_CINEMETA_CATALOG = 'https://v3-cinemeta.strem.io/catalog/series/top/search=%s.json'
_CINEMETA_META = 'https://v3-cinemeta.strem.io/meta/series/%s.json'


def _valid_imdb(imdb):
	imdb = str(imdb or '').strip()
	if not imdb or imdb.lower() in _INVALID_IMDB or not imdb.lower().startswith('tt'):
		return None
	return imdb


def _video_day(video):
	for key in ('released', 'firstAired', 'airDate'):
		val = str((video or {}).get(key) or '')
		if len(val) >= 10:
			return val[:10]
	return ''


def _cinemeta_get(url, timeout=8):
	try:
		response = json_http().get(url, timeout=max(1, int(timeout)))
		response.raise_for_status()
		return response.json() or {}
	except Exception:
		return {}


def _cinemeta_search_series(title):
	from urllib.parse import quote
	title = (title or '').strip()
	if not title:
		return []
	from caches.main_cache import main_cache
	cache_key = 'CINEMETA_SEARCH_%s' % title.lower()
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	payload = _cinemeta_get(_CINEMETA_CATALOG % quote(title))
	metas = payload.get('metas') or []
	if not isinstance(metas, list):
		metas = []
	main_cache.set(cache_key, metas, expiration=24)
	return metas


def _cinemeta_series_meta(imdb_id):
	from caches.main_cache import main_cache
	cache_key = 'CINEMETA_META_%s' % imdb_id
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	payload = _cinemeta_get(_CINEMETA_META % imdb_id)
	meta = payload.get('meta') or {}
	if not isinstance(meta, dict):
		meta = {}
	main_cache.set(cache_key, meta, expiration=24)
	return meta


def _cinemeta_map_episode(info):
	"""Map a TMDb-only season to the IMDb S/E Stremio addons actually index."""
	premiered = str(info.get('premiered') or '')[:10]
	title = info.get('title') or ''
	if len(premiered) < 10 or not title:
		return None
	try:
		want_ep = int(info.get('episode'))
		season_count = int(info.get('season_episode_count') or 0)
	except Exception:
		return None
	tmdb_id = info.get('tmdb_id') or ''
	tmdb_season = info.get('season')
	from caches.main_cache import main_cache
	map_key = 'CINEMETA_SEASON_MAP_%s_%s' % (tmdb_id, tmdb_season)
	cached = main_cache.get(map_key)
	if cached is not None:
		return cached or None
	mapped = None
	for stub in _cinemeta_search_series(title)[:5]:
		cid = str((stub or {}).get('id') or '')
		if not cid.lower().startswith('tt'):
			continue
		meta = _cinemeta_series_meta(cid)
		videos = [v for v in (meta.get('videos') or []) if isinstance(v, dict)]
		by_season = {}
		for video in videos:
			try:
				season_n = int(video.get('season'))
			except Exception:
				continue
			if season_n <= 0:
				continue
			by_season.setdefault(season_n, []).append(video)
		dated = [s for s, vids in by_season.items() if any(_video_day(v) == premiered for v in vids)]
		if not dated:
			continue
		pick = None
		if season_count:
			pick = next((s for s in dated if len(by_season[s]) == season_count), None)
		if pick is None:
			pick = dated[0]
		try:
			episodes = set(int(v.get('episode')) for v in by_season[pick] if v.get('episode') not in (None, ''))
		except Exception:
			episodes = set()
		if want_ep not in episodes:
			continue
		mapped = {
			'media_id': cid,
			'season': pick,
			'alias': (meta.get('name') or stub.get('name') or '').strip(),
		}
		break
	main_cache.set(map_key, mapped or {}, expiration=168 if mapped else 12)
	return mapped


def cinemeta_ids_when_imdb_missing(info):
	"""Parent IMDb + remapped S/E when TMDb has no IMDb.

	None for movies and for any title that already has a real tt id. Playback meta
	must not be overwritten with this — search/scrapers/subtitles only.
	"""
	if _valid_imdb((info or {}).get('imdb_id')):
		return None
	if (info or {}).get('media_type') != 'episode':
		return None
	mapped = _cinemeta_map_episode(info)
	if not mapped:
		return None
	try:
		episode = int(info.get('episode'))
		season = int(mapped['season'])
	except Exception:
		return None
	return {
		'imdb_id': mapped['media_id'],
		'season': season,
		'episode': episode,
		'alias': (mapped.get('alias') or '').strip(),
	}


def prepare_site_scrape(info, log_name=None):
	"""Copy of info with the Stremio id and S/E Sites should query.

	TMDb sometimes lists an anthology season as its own S01 show with no IMDb. Stremio
	indexes the parent IMDb + that season's number (Monster S04 vs Lizzie Borden S01).
	"""
	from modules.kodi_utils import logger
	info = dict(info or {})
	imdb = _valid_imdb(info.get('imdb_id'))
	if imdb:
		info['imdb_id'] = imdb
		return info
	mapped = cinemeta_ids_when_imdb_missing(info)
	if mapped:
		info['imdb_id'] = mapped['imdb_id']
		info['season'] = mapped['season']
		info['episode'] = mapped['episode']
		alias = mapped.get('alias')
		if alias:
			aliases = list(info.get('aliases') or [])
			existing = set()
			for item in aliases:
				if isinstance(item, dict):
					existing.add((item.get('title') or '').strip().lower())
				else:
					existing.add(str(item).strip().lower())
			if alias.strip().lower() not in existing:
				aliases.append({'title': alias, 'country': ''})
				info['aliases'] = aliases
		if log_name:
			logger(log_name, 'no IMDb id — using %s S%02dE%02d (Cinemeta)' % (
				mapped['imdb_id'], int(mapped['season']), int(mapped['episode'])))
		return info
	tmdb_i = 0
	try:
		tmdb_i = int(info.get('tmdb_id') or 0)
	except Exception:
		tmdb_i = 0
	if tmdb_i > 0:
		info['imdb_id'] = 'tmdb:%s' % tmdb_i
		if log_name:
			logger(log_name, 'no IMDb id — using tmdb:%s' % tmdb_i)
		return info
	if log_name:
		logger(log_name, 'skipped — no IMDb or TMDb id')
	return None


def stremio_search_id(info, log_name=None):
	prepared = prepare_site_scrape(info, log_name=log_name)
	return None if not prepared else prepared.get('imdb_id')


def stremio_stream_url(base, imdb_id, media_type, season=None, episode=None):
	if not base or not imdb_id:
		return None
	imdb_id = str(imdb_id).strip()
	if '/stream/' in base:
		return base
	if media_type == 'movie':
		return '%s/stream/movie/%s.json' % (base, imdb_id)
	return '%s/stream/series/%s:%s:%s.json' % (base, imdb_id, int(season), int(episode))


def parse_stremio_stream(raw):
	info_hash = normalize_info_hash(raw.get('infoHash') or '')
	if not info_hash:
		info_hash = normalize_info_hash(raw.get('url') or '')
	if not info_hash:
		return None
	description = raw.get('description') or raw.get('title') or ''
	description = str(description).replace('┈➤', '\n')
	lines = [i.strip() for i in description.split('\n') if i.strip()]
	hints = raw.get('behaviorHints') or {}
	name = hints.get('filename') or raw.get('behaviorHints', {}).get('filename')
	if not name and lines:
		name = lines[0]
	if not name:
		name = raw.get('name') or info_hash
	info_line = ''
	for line in lines:
		if _INFO_LINE.search(line):
			info_line = line
			break
	if not info_line:
		info_line = description
	size = parse_size_gb(info_line)
	if not size:
		try:
			video_size = float(hints.get('videoSize') or 0)
			if video_size > 1048576:
				size = round(video_size / 1073741824.0, 2)
		except Exception:
			size = 0.0
	return {
		'hash': info_hash,
		'name': name,
		'size': size,
		'seeders': parse_seeders(info_line),
		'description': description,
	}


def search_stremio_streams(url, cache_prefix, timeout=15, expiration=24, log_name='stremio api'):
	from caches.main_cache import main_cache
	from modules.kodi_utils import logger
	if not url:
		return []
	cache_key = '%s_%s' % (cache_prefix, url)
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	streams = []
	try:
		response = json_http().get(url, timeout=max(1, int(timeout)))
		response.raise_for_status()
		payload = response.json() or {}
		for raw in payload.get('streams') or []:
			parsed = parse_stremio_stream(raw)
			if parsed:
				streams.append(parsed)
	except Exception as e:
		logger(log_name, '%s (%s)' % (type(e).__name__, url))
		return []
	main_cache.set(cache_key, streams, expiration=expiration)
	return streams


def scrape_timeout(info, cap=None):
	from caches.settings_cache import get_setting
	try:
		setting = max(1, int(get_setting('redlight.results.timeout', '20')))
	except (TypeError, ValueError):
		setting = 20
	timeout = setting
	info = info or {}
	deadline = info.get('scrape_deadline')
	if deadline:
		timeout = int(deadline - time.time())
	elif 'timeout' in info:
		try:
			timeout = int(info['timeout'])
		except (TypeError, ValueError):
			timeout = setting
	if cap is None:
		cap = setting
	return max(1, min(timeout, cap))


def scrape_expiry(info):
	return int((info.get('expiry_times') or [24])[0] or 24)


def episode_range_from_name(name):
	"""Return (season, start, end) for SxxEaa-Ebb style names, else None."""
	if not name:
		return None
	dotted = normalize(name).lower().replace(' ', '.')
	for regex in _EPISODE_RANGE:
		match = regex.search(dotted)
		if not match:
			continue
		try:
			pack_season, start, end = int(match.group(1)), int(match.group(2)), int(match.group(3))
		except Exception:
			return None
		if start > end:
			start, end = end, start
		return pack_season, start, end
	return None


def pack_type_from_name(name, season=None):
	if not name:
		return None
	release = normalize(name)
	if _SXXEXX.search(release.replace(' ', '.')):
		return None
	dotted = release.lower().replace(' ', '.')
	if any(token in dotted for token in ('.complete.', 'collection', 'all.seasons', 'all.season')):
		return 'show'
	if season in (None, '', 'pack'):
		if re.search(r'season', dotted):
			return 'season'
		return None
	try:
		season_i = int(season)
	except Exception:
		return None
	season_fill = '%02d' % season_i
	match = _SEASON_TAG.search(dotted)
	if match and int(match.group(1)) == season_i:
		return 'season'
	if '.s%s.' % season_fill in '.%s.' % dotted.replace('-', '.'):
		return 'season'
	if 'season.%s' % season_i in dotted or 'season.%s' % season_fill in dotted:
		return 'season'
	return None


def apply_pack_size(size, package, season_divider, show_divider):
	try:
		size = float(size or 0)
	except Exception:
		return 0.0
	if package == 'season' and season_divider:
		size = size / float(season_divider)
	elif package == 'show' and show_divider:
		size = size / float(show_divider)
	return round(size, 2)


def build_source(scrape_provider, name, info_hash, size=0.0, seeders=0, package=None, extra_name_info='', episode_start=0, episode_end=0):
	file_name = normalize(name or info_hash)
	display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
	name_info = source_utils.release_info_format(file_name)
	if extra_name_info:
		name_info = '%s.%s' % (name_info, extra_name_info)
	quality, extra_info = source_utils.get_file_info(name_info=name_info)
	item = {
		'name': file_name,
		'display_name': display_name,
		'quality': quality,
		'size': round(float(size or 0), 2),
		'size_label': '%.2f GB' % float(size or 0),
		'hash': info_hash,
		'url': magnet_url(info_hash, file_name),
		'id': info_hash,
		'seeders': int(seeders or 0),
		'source': 'torrent',
		'provider': scrape_provider,
		'scrape_provider': scrape_provider,
		'extraInfo': extra_info,
		'direct': False,
		'debridonly': True,
		'external': False,
		'local': False,
	}
	if package:
		item['package'] = package
	if episode_start:
		item['episode_start'] = episode_start
		item['episode_end'] = episode_end
	return item


def name_search_queries(info):
	from modules.settings import shared_title_require_year
	title = clean_file_name(info.get('title') or '').replace('&', 'and')
	year = int(info.get('year') or 0)
	media_type = info.get('media_type')
	season, episode = info.get('season'), info.get('episode')
	absolute_episode = info.get('absolute_episode')
	aliases = source_utils.get_aliases_titles(info.get('aliases', []))
	queries, seen = [], set()

	def _add(query):
		query = (query or '').strip()
		if not query or query in seen:
			return
		seen.add(query)
		queries.append(query)

	if media_type == 'movie':
		_add('%s %d' % (title, year))
		for alias in aliases:
			name = clean_file_name(alias).replace('&', 'and')
			if name and name != title:
				_add('%s %d' % (name, year))
		return queries
	hdlr = 'S%02dE%02d' % (int(season), int(episode))
	hdlr_alt = 'S%dE%d' % (int(season), int(episode))
	require_year = shared_title_require_year(info, 'indexer')
	_add(source_utils.tv_scrape_query(title, year, season, episode, require_year))
	if hdlr_alt != hdlr and not require_year:
		_add('%s %s' % (title, hdlr_alt))
	if absolute_episode not in (None, '', 0, '0') and not require_year:
		try:
			abs_i = int(absolute_episode)
		except Exception:
			abs_i = None
		if abs_i:
			_add('%s - %s' % (title, abs_i))
			_add('%s %s' % (title, abs_i))
			if abs_i >= 100:
				_add('%s - %03d' % (title, abs_i))
	for alias in aliases[:2]:
		name = clean_file_name(alias).replace('&', 'and')
		if name and name != title:
			_add(source_utils.tv_scrape_query(name, year, season, episode, require_year))
	return queries


def merge_name_searches(search_fn, queries, timeout, expiry, deadline=None):
	files, seen = [], set()
	queries = queries or []
	for index, query in enumerate(queries):
		if deadline:
			remaining = int(deadline - time.time())
		else:
			remaining = int(timeout)
		if remaining <= 0:
			break
		left = len(queries) - index
		per_query = max(1, min(remaining, remaining // left if left else remaining))
		for item in search_fn(query, timeout=per_query, expiration=expiry) or []:
			info_hash = item.get('hash')
			if info_hash and info_hash not in seen:
				seen.add(info_hash)
				files.append(item)
	return files


def filter_and_build_sources(scrape_provider, items, info):
	from modules.settings import scrape_needs_title_filter, filter_by_episode_title, shared_title_require_year, site_strict_filenames
	from modules.kodi_utils import logger
	filter_title = scrape_needs_title_filter(info, scrape_provider)
	allow_episode_title = filter_by_episode_title(scrape_provider)
	strict_filenames = scrape_provider in NATIVE_SITE_SCRAPERS and site_strict_filenames()
	title = info.get('title', '')
	year = int(info.get('year') or 0)
	season, episode = info.get('season'), info.get('episode')
	aliases = source_utils.get_aliases_titles(info.get('aliases', []))
	absolute_episode = info.get('absolute_episode')
	ep_name = info.get('ep_name') or ''
	require_year = shared_title_require_year(info, scrape_provider)
	extras = source_utils.extras()
	season_divider = int(info.get('season_episode_count') or 1) or 1
	show_divider = int(info.get('total_aired_eps') or 1) or 1
	is_episode = info.get('media_type') == 'episode'
	season_i = episode_i = None
	if is_episode:
		try:
			season_i, episode_i = int(season), int(episode)
		except Exception:
			is_episode = False
	sources, seen = [], set()

	def _keep(file_name):
		if any(x in file_name.lower() for x in extras):
			return False, None, 0, 0
		if strict_filenames:
			if not is_episode and year and not source_utils.release_contains_show_year(file_name, year):
				return False, None, 0, 0
			if source_utils.has_junk_release_name(file_name):
				return False, None, 0, 0
		if is_episode:
			ranged = episode_range_from_name(file_name)
			if ranged:
				pack_season, start, end = ranged
				if pack_season != season_i or not (start <= episode_i <= end):
					return False, None, 0, 0
				if filter_title and not source_utils.check_title(title, file_name, aliases, year, pack_season, start, require_year):
					return False, None, 0, 0
				return True, 'season', start, end
			if filter_title:
				if source_utils.check_title_or_absolute(
						title, file_name, aliases, year, season, episode, absolute_episode, ep_name, allow_episode_title, require_year):
					return True, None, 0, 0
				return False, None, 0, 0
			if source_utils.seas_ep_filter(season_i, episode_i, file_name) or source_utils.cloud_episode_matches(
					season_i, episode_i, file_name, absolute_episode):
				return True, None, 0, 0
			return False, None, 0, 0
		if filter_title:
			if source_utils.check_title_or_absolute(
					title, file_name, aliases, year, season, episode, absolute_episode, ep_name, allow_episode_title, require_year):
				return True, None, 0, 0
			package = pack_type_from_name(file_name, season)
			if package and source_utils.check_title(title, file_name, aliases, year, 'pack', episode, require_year):
				return True, package, 0, 0
			return False, None, 0, 0
		package = pack_type_from_name(file_name, season)
		return True, package, 0, 0

	for raw in items or []:
		try:
			info_hash = raw.get('hash')
			if not info_hash or info_hash in seen:
				continue
			file_name = raw.get('name') or ''
			keep, package, episode_start, episode_end = _keep(file_name)
			if not keep:
				continue
			seen.add(info_hash)
			size = apply_pack_size(raw.get('size') or 0, package, season_divider, show_divider)
			item = build_source(
				scrape_provider, file_name, info_hash, size, raw.get('seeders') or 0, package,
				episode_start=episode_start, episode_end=episode_end)
			if is_episode and season_i is not None and episode_i is not None:
				item['resolve_season'] = season_i
				item['resolve_episode'] = episode_i
			sources.append(item)
		except Exception as e:
			logger('%s scraper yield source error' % scrape_provider, str(e))
	logger('%s scraper' % scrape_provider, '%s : %s kept / %s raw / packs=%s' % (
		info.get('title', ''), len(sources), len(items or []), sum(1 for s in sources if s.get('package'))))
	return sources
