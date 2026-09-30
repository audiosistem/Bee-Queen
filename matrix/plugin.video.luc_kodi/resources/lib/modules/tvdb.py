# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	TheTVDB v4 — works alongside TMDb, TVmaze, Fanart.tv and the trackers.

	1. Episode numbering for the scrapers, for every series: release groups
	   and tools like Sonarr number episodes the TheTVDB way. When TMDb groups
	   the seasons differently, the scrapers also search the TheTVDB SxxEyy.
	   For anime they also search the absolute number ("Show - 48").
	2. Missing episode details: when TMDb has no title, plot, air date or
	   still for an episode, TheTVDB fills the gap.
	3. Artwork fallback: series poster and background when TMDb has none.

	Access: the plugin has its own project key (no PIN needed).
	Users with their own key can enter it, plus a subscriber PIN if their key
	needs one, under Settings > Accounts > TheTVDB.
"""

import re
from hashlib import md5
import requests
from resources.lib.database import cache
from resources.lib.modules.control import setting as getSetting
from resources.lib.modules import log_utils
from resources.lib.modules import app_keys

API = 'https://api4.thetvdb.com/v4'
_TIMEOUT = 8
_MAX_PAGES = 20
_LANG3 = {'en': 'eng', 'es': 'spa', 'fr': 'fra', 'de': 'deu', 'it': 'ita', 'pt': 'por', 'ro': 'ron', 'nl': 'nld', 'pl': 'pol',
			'ru': 'rus', 'ja': 'jpn', 'ko': 'kor', 'zh': 'zho', 'sv': 'swe', 'da': 'dan', 'fi': 'fin', 'no': 'nor', 'tr': 'tur',
			'el': 'ell', 'hu': 'hun', 'cs': 'ces', 'he': 'heb', 'ar': 'ara'}
_PLACEHOLDER = re.compile(r'^(?:Episode|Episodio|Épisode|Folge|Episodul)\s*\d+$', re.I)


def _project_key():
	return app_keys.get('tvdb')

def _credentials():
	personal = (getSetting('tvdb.personal_key') or '').strip()
	if personal: return personal, (getSetting('tvdb.pin') or '').strip()
	return _project_key(), ''

def _cred_tag():
	# Cache discriminator: a new personal key or PIN gets a new token and new
	# data, without the key itself ever reaching the cache table.
	key, pin = _credentials()
	return md5(('%s|%s' % (key, pin)).encode('utf-8')).hexdigest()[:12]

def tvdb_login(cred_tag):
	try:
		key, pin = _credentials()
		payload = {'apikey': key}
		if pin: payload['pin'] = pin
		r = requests.post('%s/login' % API, json=payload, timeout=_TIMEOUT)
		if r.status_code != 200:
			log_utils.log('TVDB: login refused (HTTP %s)' % r.status_code, level=log_utils.LOGWARNING)
			return None
		return (r.json().get('data') or {}).get('token') or None
	except:
		log_utils.error('TVDB: login failed')
		return None

def _get(path, params=None):
	tag = _cred_tag()
	for attempt in (1, 2):
		token = cache.get(tvdb_login, 600, tag) # tokens last a month; renewed at 25 days
		if not token: return None
		try:
			r = requests.get('%s%s' % (API, path), params=params, timeout=_TIMEOUT,
								headers={'Authorization': 'Bearer %s' % token, 'Accept': 'application/json'})
		except:
			log_utils.error('TVDB: request failed %s' % path)
			return None
		if r.status_code == 401 and attempt == 1:
			cache.remove(tvdb_login, tag) # token revoked or expired early: log in again once
			continue
		if r.status_code != 200:
			log_utils.log('TVDB: HTTP %s for %s' % (r.status_code, path), level=log_utils.LOGDEBUG)
			return None
		try: return r.json()
		except: return None
	return None

def _episodes(path):
	episodes = []
	for page in range(_MAX_PAGES):
		result = _get(path, {'page': page})
		if not result: return None if page == 0 else episodes
		data = result.get('data') or {}
		batch = data.get('episodes') or []
		episodes.extend(batch)
		if not batch or not (result.get('links') or {}).get('next'): break
	return episodes

def _is_anime(series):
	genres = [str((g or {}).get('name', '')).lower() for g in (series.get('genres') or [])]
	if 'anime' in genres: return True
	return str(series.get('originalLanguage') or '').lower() == 'jpn' and 'animation' in genres

def _se(ep):
	try: return int(ep.get('seasonNumber') or 0), int(ep.get('number') or 0)
	except: return 0, 0

# ---------------------------------------------------------------- ids

def tvdb_remote_imdb(tvdb_id, cred_tag):
	"""v1.0.94 — id de IMDb de una serie segun TheTVDB (remoteIds). Para las
	series que TMDb tiene sin IMDb: los proveedores tipo Stremio (AIOStreams,
	Torrentio, Comet...) solo saben buscar por ese id."""
	result = _get('/series/%s/extended' % tvdb_id, {'short': 'true'})
	data = (result or {}).get('data') or {}
	for rid in data.get('remoteIds') or []:
		ident = str((rid or {}).get('id') or '')
		if str((rid or {}).get('sourceName') or '').lower() == 'imdb' and ident.startswith('tt'):
			return ident
	return None # sin cachear: se reintenta la proxima vez

def imdb_id(tvdb):
	if not tvdb or str(tvdb) in ('0', 'None'): return ''
	try: return cache.get(tvdb_remote_imdb, 720, str(tvdb), _cred_tag()) or ''
	except:
		log_utils.error()
		return ''

# ---------------------------------------------------------------- numbering

def tvdb_series_map(tvdb_id, cred_tag):
	"""TheTVDB default order of one series:
	order = ['s:e', ...] (specials left out), counts = {'season': episodes},
	dates = {'YYYY-MM-DD': 's:e'} for days with a single episode,
	anime flag, and for anime abs = {'s:e': absolute}."""
	try:
		result = _get('/series/%s/extended' % tvdb_id, {'short': 'true'})
		series = (result or {}).get('data')
		if not series: return None
		anime = _is_anime(series)
		default = _episodes('/series/%s/episodes/default' % tvdb_id)
		if not default: return None
		rows = sorted([(_se(ep), ep) for ep in default if _se(ep)[0] > 0 and _se(ep)[1] > 0], key=lambda x: x[0])
		order, counts, dates, seen_dates = [], {}, {}, {}
		for (s, e), ep in rows:
			key = '%d:%d' % (s, e)
			order.append(key)
			counts[str(s)] = counts.get(str(s), 0) + 1
			aired = str(ep.get('aired') or '')[:10]
			if aired:
				seen_dates[aired] = seen_dates.get(aired, 0) + 1
				dates[aired] = key
		dates = dict((d, k) for d, k in dates.items() if seen_dates.get(d) == 1)
		info = {'anime': anime, 'order': order, 'counts': counts, 'dates': dates}
		if anime:
			absolute = _episodes('/series/%s/episodes/absolute' % tvdb_id) or []
			abs_by_id = {}
			for ep in absolute:
				if _se(ep)[0] == 0: continue
				n = ep.get('absoluteNumber') or ep.get('number')
				if ep.get('id') and n: abs_by_id[ep['id']] = int(n)
			abs_map = {}
			for (s, e), ep in rows:
				n = abs_by_id.get(ep.get('id')) or ep.get('absoluteNumber')
				if n: abs_map['%d:%d' % (s, e)] = int(n)
			info['abs'] = abs_map
		return info
	except:
		log_utils.error('TVDB: series map failed for %s' % tvdb_id)
		return None

def _layout_matches(tmdb_counts, tvdb_counts, season):
	try:
		for s in range(1, season):
			if int(tmdb_counts.get(str(s), -1)) != int(tvdb_counts.get(str(s), -2)): return False
		return True
	except: return False

def _cumulative(counts, season, episode):
	try: return sum(int(counts.get(str(s), 0)) for s in range(1, season)) + episode
	except: return None

def _to_tvdb(info, season, episode, counts=None, premiered=None):
	"""TheTVDB (season, episode) for a TMDb (season, episode), or None."""
	order, key = info.get('order') or [], '%d:%d' % (season, episode)
	date = str(premiered or '')[:10]
	if date and date in (info.get('dates') or {}): # same air date: the most reliable match
		return tuple(int(x) for x in info['dates'][date].split(':'))
	if key in order and (not counts or _layout_matches(counts, info.get('counts') or {}, season)):
		return season, episode
	if counts:
		n = _cumulative(counts, season, episode) # TMDb groups the seasons differently: count through
		if n and 0 < n <= len(order): return tuple(int(x) for x in order[n - 1].split(':'))
		return None
	return (season, episode) if key in order else None

def episode_numbering(tvdb, season, episode, counts=None, premiered=None):
	"""Extra keys for the scrapers' data dict, or {} when there is nothing to add.
	alt_hdlr: TheTVDB SxxEyy when it differs from TMDb's (any series);
	absolute_episode: absolute number (anime only)."""
	try:
		if getSetting('tvdb.numbering') == 'false': return {}
		tvdb = str(tvdb or '').strip()
		if not tvdb.isdigit() or tvdb == '0': return {}
		season, episode = int(season), int(episode)
		if season < 1 or episode < 1: return {}
		info = cache.get(tvdb_series_map, 168, tvdb, _cred_tag())
		if not info or not info.get('order'): return {}
		extra = {}
		se = _to_tvdb(info, season, episode, counts, premiered)
		if se and se != (season, episode): extra['alt_hdlr'] = 'S%02dE%02d' % se
		if info.get('anime'):
			n = (info.get('abs') or {}).get('%d:%d' % se) if se else None
			if not n and counts:
				n = _cumulative(counts, season, episode)
				if n and n > len(info['order']): n = None
			if n: extra['absolute_episode'] = int(n)
		if extra: log_utils.log('TVDB: tvdb %s S%02dE%02d -> %s' % (tvdb, season, episode, extra), level=log_utils.LOGDEBUG)
		return extra
	except:
		log_utils.error()
		return {}

# ---------------------------------------------------- missing episode details

def tvdb_episode_info(tvdb_id, lang3, cred_tag):
	"""{'s:e': {'title', 'plot', 'aired', 'thumb'}} plus order/counts, in lang3."""
	try:
		episodes = _episodes('/series/%s/episodes/default/%s' % (tvdb_id, lang3))
		if not episodes: return None
		out, order, counts = {}, [], {}
		for ep in sorted(episodes, key=_se):
			s, e = _se(ep)
			if s < 1 or e < 1: continue
			key = '%d:%d' % (s, e)
			order.append(key)
			counts[str(s)] = counts.get(str(s), 0) + 1
			out[key] = {'title': ep.get('name') or '', 'plot': ep.get('overview') or '',
						'aired': str(ep.get('aired') or '')[:10], 'thumb': ep.get('image') or ''}
		return {'eps': out, 'order': order, 'counts': counts, 'dates': {}}
	except:
		log_utils.error('TVDB: episode info failed for %s' % tvdb_id)
		return None

def _missing(ep):
	title = str(ep.get('title') or '')
	return (not title or _PLACEHOLDER.match(title) or not ep.get('plot') or not ep.get('premiered') or not ep.get('thumb'))

def fill_episodes(tvdb, episodes, counts=None, lang='en'):
	"""Fills, in place, only the empty fields of TMDb episode dicts. Returns how many changed."""
	try:
		if getSetting('tvdb.fill_gaps') == 'false': return 0
		tvdb = str(tvdb or '').strip()
		if not tvdb.isdigit() or tvdb == '0' or not episodes: return 0
		if not any(_missing(ep) for ep in episodes): return 0
		lang3 = _LANG3.get(str(lang or 'en')[:2].lower(), 'eng')
		info = cache.get(tvdb_episode_info, 72, tvdb, lang3, _cred_tag())
		if not info and lang3 != 'eng': info = cache.get(tvdb_episode_info, 72, tvdb, 'eng', _cred_tag())
		if not info: return 0
		changed = 0
		for ep in episodes:
			if not _missing(ep): continue
			try: se = _to_tvdb(info, int(ep.get('season')), int(ep.get('episode')), counts)
			except: se = None
			src = (info.get('eps') or {}).get('%d:%d' % se) if se else None
			if not src: continue
			before = dict(ep)
			if src['title'] and (not ep.get('title') or _PLACEHOLDER.match(str(ep.get('title')))): ep['title'] = src['title']
			if src['plot'] and not ep.get('plot'): ep['plot'] = src['plot']
			if src['aired'] and not ep.get('premiered'): ep['premiered'] = src['aired']
			if src['thumb'] and not ep.get('thumb'): ep['thumb'] = src['thumb']
			if ep != before: changed += 1
		if changed: log_utils.log('TVDB: filled %d episode(s) of tvdb %s' % (changed, tvdb), level=log_utils.LOGDEBUG)
		return changed
	except:
		log_utils.error()
		return 0

# ---------------------------------------------------------- artwork fallback

def tvdb_artwork_types(cred_tag):
	result = _get('/artwork/types')
	types = {}
	for t in (result or {}).get('data') or []:
		if str(t.get('recordType') or '').lower() != 'series': continue
		name = str(t.get('name') or t.get('slug') or '').lower()
		if name.startswith('poster'): types[t.get('id')] = 'poster'
		elif name.startswith('background') or name.startswith('fanart'): types[t.get('id')] = 'fanart'
	return types or None

def tvdb_series_art(tvdb_id, cred_tag):
	try:
		types = cache.get(tvdb_artwork_types, 720, cred_tag) or {2: 'poster', 3: 'fanart'}
		result = _get('/series/%s/artworks' % tvdb_id)
		data = (result or {}).get('data')
		arts = data.get('artworks') if isinstance(data, dict) else data
		best = {}
		for a in arts or []:
			kind = types.get(a.get('type'))
			if not kind or not a.get('image'): continue
			lang = str(a.get('language') or '')
			rank = (lang == 'eng', lang in ('', 'None'), int(a.get('score') or 0))
			if kind not in best or rank > best[kind][0]: best[kind] = (rank, a['image'])
		art = dict((k, v[1]) for k, v in best.items())
		if 'poster' not in art and isinstance(data, dict) and data.get('image'): art['poster'] = data['image']
		return art or {'none': True} # cache the empty answer as well
	except:
		log_utils.error('TVDB: artwork failed for %s' % tvdb_id)
		return None

def series_art(tvdb):
	"""{'poster': url, 'fanart': url} from TheTVDB, or {}."""
	try:
		if getSetting('tvdb.fill_gaps') == 'false': return {}
		tvdb = str(tvdb or '').strip()
		if not tvdb.isdigit() or tvdb == '0': return {}
		art = cache.get(tvdb_series_art, 336, tvdb, _cred_tag()) or {}
		return dict((k, v) for k, v in art.items() if k in ('poster', 'fanart'))
	except:
		log_utils.error()
		return {}
