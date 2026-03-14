# -*- coding: utf-8 -*-
"""
luc_kodi Add-on - Recommendations (Hybrid Trakt + TMDb)

MVP design goals:
- Works with Trakt auth if available; falls back gracefully.
- Uses Trakt history + Trakt recommendations + TMDb similar/recommendations (seeded)
- Keeps requests limited with caching.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from collections import Counter, defaultdict

from resources.lib.modules import control
from resources.lib.modules import trakt
from resources.lib.indexers.tmdb import TMDb
from resources.lib.database import cache

getSetting = control.setting
getLS = control.lang

def _bool_setting(id_: str) -> bool:
	try:
		return str(getSetting(id_) or '').lower() == 'true'
	except Exception:
		return False


def _kids_mode_enabled() -> bool:
	return _bool_setting('kids.mode')


def _kids_level() -> str:
	# 0 = Kids (strict), 1 = Family
	try:
		v = str(getSetting('kids.level') or '1').strip()
		return v if v in ('0', '1') else '1'
	except Exception:
		return '1'


_MOVIE_CERT_ORDER = {'G': 0, 'PG': 1, 'PG-13': 2, 'R': 3, 'NC-17': 4}
_TV_CERT_ORDER = {'TV-Y': 0, 'TV-Y7': 1, 'TV-G': 2, 'TV-PG': 3, 'TV-14': 4, 'TV-MA': 5}


def _get_tmdb_certification(media_type: str, tmdb: TMDb, tmdb_id: str, region: str = 'US') -> str:
	"""Return certification/rating string from TMDb. Cached."""
	def _fetch():
		api_key = tmdb.API_key
		lang = tmdb.lang or 'en-US'
		try:
			if media_type == 'movie':
				url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/release_dates?api_key={api_key}"
				data = _get_tmdb_json(tmdb, url) or {}
				results = data.get('results') or []
				for r in results:
					if (r.get('iso_3166_1') or '').upper() == region.upper():
						for rd in (r.get('release_dates') or []):
							c = (rd.get('certification') or '').strip()
							if c:
								return c
				for r in results:
					for rd in (r.get('release_dates') or []):
						c = (rd.get('certification') or '').strip()
						if c:
							return c
				return ''
			else:
				url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/content_ratings?api_key={api_key}&language={lang}"
				data = _get_tmdb_json(tmdb, url) or {}
				results = data.get('results') or []
				for r in results:
					if (r.get('iso_3166_1') or '').upper() == region.upper():
						return (r.get('rating') or '').strip()
				for r in results:
					c = (r.get('rating') or '').strip()
					if c:
						return c
				return ''
		except Exception:
			return ''
	return cache.get(_fetch, 168, f"tmdb_cert_{media_type}_{region}_{tmdb_id}")


def _kids_filter_pass(media_type: str, tmdb: TMDb, item: dict, genre_map: dict) -> bool:
	"""Return True if item is allowed under Kids/Family mode."""
	if not _kids_mode_enabled():
		return True

	level = _kids_level()
	# genre-based filter (fast)
	banned = {'horror'}
	if level == '0':  # Kids strict
		banned |= {'thriller', 'crime'}

	genres = []
	try:
		genres = [str(x).lower() for x in (item.get('_trakt_genres') or [])]
	except Exception:
		genres = []
	if not genres:
		# best-effort from tmdb genre ids
		try:
			gids = item.get('_tmdb_genre_ids') or []
			for gid in gids:
				name = str((genre_map or {}).get(int(gid), '') or '').lower()
				if name:
					genres.append(name)
		except Exception:
			pass

	for g in genres:
		if g in banned:
			return False

	# certification filter (slower but cached)
	tid = item.get('tmdb') or ''
	if not tid:
		return True
	cert = _get_tmdb_certification(media_type, tmdb, str(tid), region='US')
	if not cert:
		return True  # if unknown, don't block

	if media_type == 'movie':
		max_cert = 'PG' if level == '0' else 'PG-13'
		return _MOVIE_CERT_ORDER.get(cert, 99) <= _MOVIE_CERT_ORDER.get(max_cert, 2)
	else:
		max_cert = 'TV-PG' if level == '0' else 'TV-14'
		return _TV_CERT_ORDER.get(cert, 99) <= _TV_CERT_ORDER.get(max_cert, 4)


def _iso_to_dt(s: str):
	try:
		return datetime.fromisoformat(s.replace('Z', '+00:00'))
	except Exception:
		return None


def _recency_weight(watched_at_iso: str, half_life_days: float = 45.0) -> float:
	dt = _iso_to_dt(watched_at_iso or '')
	if not dt:
		return 0.5
	now = datetime.now(timezone.utc)
	days = max(0.0, (now - dt).total_seconds() / 86400.0)
	return math.exp(-days / half_life_days)


def _completion_weight(progress: float | None) -> float:
	try:
		p = float(progress)
	except Exception:
		return 1.0
	if p >= 0.9:
		return 1.0
	if p >= 0.2:
		return 0.6
	return 0.3


def _get_trakt_json(url: str, silent: bool = True):
	r = trakt.getTrakt(url, silent=silent)
	if not r:
		return None
	try:
		return r.json()
	except Exception:
		return None


def _get_tmdb_json(tmdb: TMDb, url: str):
	# TMDb.get_request expects full URL
	return tmdb.get_request(url)


def _tmdb_genre_map(media_type: str, tmdb: TMDb) -> dict:
	"""
	Cached genre id->name mapping.
	"""
	def _fetch():
		api_key = tmdb.API_key
		lang = tmdb.lang or 'en-US'
		endpoint = 'movie' if media_type == 'movie' else 'tv'
		url = f"https://api.themoviedb.org/3/genre/{endpoint}/list?api_key={api_key}&language={lang}"
		data = _get_tmdb_json(tmdb, url) or {}
		g = data.get('genres') or []
		return {int(x.get('id')): x.get('name') for x in g if x.get('id')}

	return cache.get(_fetch, 168, f"tmdb_genremap_{media_type}")


def _normalize_item_from_trakt(obj: dict, media_type: str) -> dict | None:
	try:
		node = obj.get(media_type) or obj  # sometimes trakt returns {movie:{...}}
		ids = node.get('ids') or {}
		tmdb_id = ids.get('tmdb')
		imdb_id = ids.get('imdb') or ''
		title = node.get('title') or ''
		year = node.get('year') or ''
		if not title or not tmdb_id:
			return None
		return {
			'title': title,
			'year': str(year) if year else '',
			'tmdb': str(tmdb_id),
			'imdb': str(imdb_id) if imdb_id else '',
			'media_type': media_type,
			'_src': 'trakt'
		}
	except Exception:
		return None


def _normalize_item_from_tmdb(node: dict, media_type: str) -> dict | None:
	try:
		tmdb_id = node.get('id')
		title = node.get('title') if media_type == 'movie' else node.get('name')
		date = node.get('release_date') if media_type == 'movie' else node.get('first_air_date')
		year = (date or '')[:4] if date else ''
		if not title or not tmdb_id:
			return None
		return {
			'title': title,
			'year': year,
			'tmdb': str(tmdb_id),
			'imdb': '',
			'media_type': media_type,
			'_src': 'tmdb',
			'_tmdb_genre_ids': node.get('genre_ids') or [],
			'_tmdb_popularity': float(node.get('popularity') or 0.0),
			'_tmdb_vote': float(node.get('vote_average') or 0.0),
		}
	except Exception:
		return None


def _get_seeds(media_type: str, limit: int = 20) -> list[dict]:
	"""
	Seeds from Trakt history. _completion_weight applied:
	a finished movie is a stronger taste signal than one left halfway.
	"""
	if not trakt.getTraktCredentialsInfo():
		return []
	endpoint = 'movies' if media_type == 'movie' else 'shows'
	# Fetch in-progress playback to get completion percentages
	playback_data = _get_trakt_json(f"/sync/playback/{endpoint}?limit=50", silent=True) or []
	playback_progress = {}
	for pb in playback_data:
		node = pb.get(media_type) or {}
		tmdb_id = str((node.get('ids') or {}).get('tmdb') or '')
		if tmdb_id:
			playback_progress[tmdb_id] = float(pb.get('progress') or 0.0) / 100.0
	url = f"/sync/history/{endpoint}?limit={limit}"
	data = _get_trakt_json(url) or []
	seeds = []
	seen_tmdb = set()
	for ev in data:
		item = _normalize_item_from_trakt(ev, media_type)
		if not item:
			continue
		item['_watched_at'] = ev.get('watched_at') or ev.get('last_watched_at') or ''
		tmdb_id = item.get('tmdb') or ''
		progress = playback_progress.get(tmdb_id, 1.0)
		item['_completion_w'] = _completion_weight(progress)
		seeds.append(item)
		seen_tmdb.add(tmdb_id)
	# Also include purely in-progress items not in recent history
	for pb in playback_data:
		node = pb.get(media_type) or {}
		ids = node.get('ids') or {}
		tmdb_id = str(ids.get('tmdb') or '')
		if not tmdb_id or tmdb_id in seen_tmdb:
			continue
		title = node.get('title') or ''
		if not title:
			continue
		progress = float(pb.get('progress') or 0.0) / 100.0
		seeds.append({
			'title': title, 'year': str(node.get('year') or ''),
			'tmdb': tmdb_id, 'imdb': str(ids.get('imdb') or ''),
			'media_type': media_type, '_src': 'trakt',
			'_watched_at': '', '_completion_w': _completion_weight(progress),
		})
	return seeds


def _get_user_profile(media_type: str, tmdb: TMDb) -> dict:
	"""
	Build a lightweight preference profile from Trakt ratings + recency-weighted history.
	Profile outputs:
		- genres: Counter(name->weight)
		- seed_titles: list[str]
	"""
	profile = {'genres': Counter(), 'seed_titles': [], 'liked_titles': []}
	if not trakt.getTraktCredentialsInfo():
		return profile

	endpoint = 'movies' if media_type == 'movie' else 'shows'

	# Ratings (likes)
	ratings = _get_trakt_json(f"/sync/ratings/{endpoint}?limit=80") or []
	for r in ratings:
		try:
			rating = int(r.get('rating') or 0)
		except Exception:
			rating = 0
		if rating < 8:
			continue
		node = r.get(media_type) or {}
		title = node.get('title') or ''
		if title:
			profile['liked_titles'].append(title)

		for g in (node.get('genres') or []):
			profile['genres'][g] += 1.8

	# Recent history (recency)
	history = _get_trakt_json(f"/sync/history/{endpoint}?limit=60") or []
	for ev in history:
		w = _recency_weight(ev.get('watched_at') or '')
		node = ev.get(media_type) or {}
		for g in (node.get('genres') or []):
			profile['genres'][g] += 1.0 * w
		title = node.get('title') or ''
		if title and len(profile['seed_titles']) < 5:
			profile['seed_titles'].append(title)

	return profile


def _get_candidates_from_trakt(media_type: str, limit: int = 60) -> list[dict]:
	"""
	High-precision candidates from Trakt recommendations endpoint.
	"""
	if not trakt.getTraktCredentialsInfo():
		return []
	endpoint = 'movies' if media_type == 'movie' else 'shows'
	data = _get_trakt_json(f"/recommendations/{endpoint}?limit={limit}&extended=full") or []
	out = []
	for obj in data:
		item = _normalize_item_from_trakt(obj, media_type)
		if item:
			# carry genres if present (for scoring/reasons without extra calls)
			node = obj.get(media_type) or obj
			item['_trakt_genres'] = node.get('genres') or []
			out.append(item)
	return out


def _get_candidates_from_tmdb_seeds(media_type: str, tmdb: TMDb, seeds: list[dict], per_seed: int = 12) -> list[dict]:
	"""
	Broaden candidates using TMDb similar/recommendations seeded by recent watched items.
	"""
	api_key = tmdb.API_key
	lang = tmdb.lang or 'en-US'
	endpoint = 'movie' if media_type == 'movie' else 'tv'
	results = []

	for seed in seeds[:5]:
		try:
			tmdb_id = seed.get('tmdb')
			if not tmdb_id:
				continue
			for kind in ('recommendations', 'similar'):
				url = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}/{kind}?api_key={api_key}&language={lang}&page=1"
				data = _get_tmdb_json(tmdb, url) or {}
				for node in (data.get('results') or [])[:per_seed]:
					item = _normalize_item_from_tmdb(node, media_type)
					if item:
						item['_seed'] = seed.get('title') or ''
						item['_src'] = f"tmdb_{kind}"
						results.append(item)
		except Exception:
			continue

	return results


def _get_seen_and_watchlist_tmdb_ids(media_type: str) -> tuple[set, set]:
	"""
	For filtering duplicates: ids already seen (history) and in watchlist.
	"""
	seen, watch = set(), set()
	if not trakt.getTraktCredentialsInfo():
		return seen, watch

	endpoint = 'movies' if media_type == 'movie' else 'shows'
	h = _get_trakt_json(f"/sync/history/{endpoint}?limit=800", silent=True) or []
	for ev in h:
		node = ev.get(media_type) or {}
		tmdb_id = (node.get('ids') or {}).get('tmdb')
		if tmdb_id:
			seen.add(str(tmdb_id))

	w = _get_trakt_json(f"/sync/watchlist/{endpoint}?limit=400", silent=True) or []
	for it in w:
		node = it.get(media_type) or {}
		tmdb_id = (node.get('ids') or {}).get('tmdb')
		if tmdb_id:
			watch.add(str(tmdb_id))

	return seen, watch


def _score_item(item: dict, profile: dict, genre_map: dict) -> tuple[float, str]:
	"""
	Return (score, reason_string).
	Now uses liked_titles, seed_titles and completion_w — previously computed but ignored.
	"""
	score = 0.0
	reasons = []

	src = item.get('_src') or ''
	if src.startswith('trakt'):
		score += 40.0
	elif src.startswith('tmdb_'):
		score += 20.0

	# Genre matching against user profile
	cand_genres = set()
	for g in (item.get('_trakt_genres') or []):
		cand_genres.add(str(g).lower())
	for gid in (item.get('_tmdb_genre_ids') or []):
		name = (genre_map or {}).get(int(gid), '')
		if name:
			cand_genres.add(name.lower())

	top = profile.get('genres', Counter()).most_common(8)
	matched = []
	for gname, w in top:
		if str(gname).lower() in cand_genres:
			score += 6.0 * float(w)
			matched.append(gname)
	if matched:
		reasons.append("Do you like it: " + " • ".join(matched[:3]))

	# Seed reason — weighted by completion (finished = stronger signal)
	seed = item.get('_seed')
	completion_w = float(item.get('_completion_w') or 1.0)
	if seed:
		score += 18.0 * completion_w
		reasons.append(f"Because you saw: {seed}")

	# liked_titles boost — titles the user rated ≥8 on Trakt
	liked = profile.get('liked_titles') or []
	if liked and item.get('title') in liked:
		score += 25.0
		if not reasons:
			reasons.append("In your top rated")

	# seed_titles — appears in recently watched context
	seed_titles = profile.get('seed_titles') or []
	if seed_titles and item.get('title') in seed_titles:
		score += 10.0

	# TMDB quality floor
	try:
		pop = float(item.get('_tmdb_popularity') or 0.0)
		score += 0.3 * math.log(1.0 + pop)
	except Exception:
		pass
	try:
		vote = float(item.get('_tmdb_vote') or 0.0)
		score += 1.2 * vote
	except Exception:
		pass

	reason = " | ".join(reasons[:2]) if reasons else "Recommended for you"
	return score, reason


def _get_tmdb_trending(media_type: str, tmdb: TMDb, limit: int = 50) -> list:
	"""Fallback: TMDB trending when Trakt+seeds yield nothing."""
	api_key = tmdb.API_key
	lang = tmdb.lang or 'en-US'
	endpoint = 'movie' if media_type == 'movie' else 'tv'
	try:
		url = f"https://api.themoviedb.org/3/trending/{endpoint}/week?api_key={api_key}&language={lang}"
		data = _get_tmdb_json(tmdb, url) or {}
		results = []
		for node in (data.get('results') or [])[:limit]:
			item = _normalize_item_from_tmdb(node, media_type)
			if item:
				item['_src'] = 'tmdb_trending'
				results.append(item)
		return results
	except Exception:
		return []


def _build_recommendations(media_type: str) -> list:
	"""
	Core computation — module-level so cache.get(fn, hours, arg) calls fn(arg) correctly.
	Includes: completion_weight on seeds, liked_titles/seed_titles in scoring,
	TMDB trending fallback if no results, and debug logging.
	"""
	from resources.lib.modules import log_utils
	limit = 50
	tmdb = TMDb()
	genre_map = _tmdb_genre_map(media_type, tmdb) or {}
	profile = _get_user_profile(media_type, tmdb)
	seeds = _get_seeds(media_type, limit=25)

	has_trakt = trakt.getTraktCredentialsInfo()
	log_utils.log(f'[luc_reco] media={media_type} has_trakt={bool(has_trakt)} seeds={len(seeds)}', level=log_utils.LOGDEBUG)

	trakt_cands = _get_candidates_from_trakt(media_type, limit=70)
	tmdb_cands = _get_candidates_from_tmdb_seeds(media_type, tmdb, seeds, per_seed=14)
	candidates = trakt_cands + tmdb_cands
	log_utils.log(f'[luc_reco] trakt_cands={len(trakt_cands)} tmdb_cands={len(tmdb_cands)}', level=log_utils.LOGDEBUG)

	# Deduplicate — prefer Trakt; carry completion_w from seed
	seed_completion = {s.get('tmdb'): s.get('_completion_w', 1.0) for s in seeds if s.get('tmdb')}
	by_id = {}
	for it in candidates:
		tid = it.get('tmdb')
		if not tid:
			continue
		if it.get('_seed'):
			seed_tmdb = next((s.get('tmdb') for s in seeds if s.get('title') == it.get('_seed')), None)
			if seed_tmdb:
				it['_completion_w'] = seed_completion.get(seed_tmdb, 1.0)
		if tid not in by_id:
			by_id[tid] = it
		elif (by_id[tid].get('_src') or '').startswith('tmdb') and (it.get('_src') or '').startswith('trakt'):
			by_id[tid] = it

	seen_ids, watch_ids = _get_seen_and_watchlist_tmdb_ids(media_type)
	log_utils.log(f'[luc_reco] unique={len(by_id)} seen={len(seen_ids)} watchlist={len(watch_ids)}', level=log_utils.LOGDEBUG)

	scored = []
	for tid, it in by_id.items():
		if not _kids_filter_pass(media_type, tmdb, it, genre_map):
			continue
		if tid in seen_ids or tid in watch_ids:
			continue
		s, reason = _score_item(it, profile, genre_map)
		it['reco_score'] = round(float(s), 2)
		it['reco_reason'] = reason
		scored.append(it)

	log_utils.log(f'[luc_reco] scored_after_filter={len(scored)}', level=log_utils.LOGDEBUG)

	# Fallback to TMDB trending when engine yields nothing
	if not scored:
		log_utils.log('[luc_reco] No results — falling back to TMDB trending', level=log_utils.LOGWARNING)
		for it in _get_tmdb_trending(media_type, tmdb, limit):
			it['reco_score'] = 0.0
			it['reco_reason'] = 'Trending this week'
			scored.append(it)

	# Diversity cap: max 10 titles per primary genre
	buckets = defaultdict(int)
	final = []
	for it in sorted(scored, key=lambda x: x.get('reco_score', 0), reverse=True):
		prim = None
		if it.get('_trakt_genres'):
			prim = str(it['_trakt_genres'][0]).lower()
		elif it.get('_tmdb_genre_ids'):
			prim = str(it['_tmdb_genre_ids'][0])
		if prim and buckets[prim] >= 10:
			continue
		if prim:
			buckets[prim] += 1
		final.append(it)
		if len(final) >= limit:
			break

	log_utils.log(f'[luc_reco] final={len(final)}', level=log_utils.LOGDEBUG)
	out = []
	for it in final:
		out.append({
			'title': it.get('title'),
			'year': it.get('year'),
			'tmdb': it.get('tmdb'),
			'imdb': it.get('imdb', ''),
			'reco_score': it.get('reco_score', 0),
			'reco_reason': it.get('reco_reason', 'Recommended for you'),
		})
	return out


def get_recommendations(media_type: str, limit: int = 50) -> list[dict]:
	"""
	media_type: 'movie' or 'tv'
	Sin caché — se recalcula en cada visita para mostrar contenido actualizado.
	"""
	if media_type not in ('movie', 'tv'):
		raise ValueError("media_type must be 'movie' or 'tv'")
	return cache.get(_build_recommendations, 0, media_type) or []
