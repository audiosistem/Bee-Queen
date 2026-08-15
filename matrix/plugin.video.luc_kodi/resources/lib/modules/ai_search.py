# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	AI Search orchestrator.
	Pipeline: user prompt -> Gemini intent -> TMDb Discover URL -> luc_kodi Movies/TVshows pipeline.
	Falls back to TMDb Search + recommendations seeded by example_titles when Discover is too narrow.
"""

from datetime import date
from urllib.parse import quote_plus
from resources.lib.modules import control
from resources.lib.modules import gemini_api
from resources.lib.database import cache

getLS = control.lang
getSetting = control.setting

TMDB_BASE = 'https://api.themoviedb.org/3'
SYSADDON = 'plugin://plugin.video.luc_kodi'

# TMDb genre IDs (canonical English labels -> IDs).
# These are the official TMDb genre IDs; they are stable and rarely change.
MOVIE_GENRES = {
	'action': 28, 'adventure': 12, 'animation': 16, 'comedy': 35, 'crime': 80,
	'documentary': 99, 'drama': 18, 'family': 10751, 'fantasy': 14, 'history': 36,
	'horror': 27, 'music': 10402, 'mystery': 9648, 'romance': 10749,
	'sci-fi': 878, 'science fiction': 878, 'sci fi': 878, 'scifi': 878,
	'tv movie': 10770, 'thriller': 53, 'war': 10752, 'western': 37,
}
TV_GENRES = {
	'action': 10759, 'adventure': 10759, 'action adventure': 10759,
	'animation': 16, 'comedy': 35, 'crime': 80, 'documentary': 99, 'drama': 18,
	'family': 10751, 'kids': 10762, 'mystery': 9648,
	'news': 10763, 'reality': 10764, 'sci-fi': 10765, 'science fiction': 10765,
	'sci fi': 10765, 'scifi': 10765, 'sci-fi & fantasy': 10765, 'fantasy': 10765,
	'soap': 10766, 'talk': 10767, 'war': 10768, 'war & politics': 10768,
	'western': 37, 'horror': 9648, 'thriller': 80, 'romance': 18, 'history': 18,
	'music': 10764,
}


# ──────────────────────────────────────────────────────────────────────
# Public entry points (called from router)
# ──────────────────────────────────────────────────────────────────────

def run():
	"""Auto mode: Gemini decides movie vs TV based on prompt."""
	_run_with_forced_type(forced_type=None)


def run_movies():
	"""Force movie results."""
	_run_with_forced_type(forced_type='movie')


def run_tvshows():
	"""Force TV results."""
	_run_with_forced_type(forced_type='tvshow')


def search_history_term(name, forced_type=None):
	"""Replay an existing prompt from history without re-prompting the user."""
	if not name:
		return control.closeAll()
	_execute_prompt(name, forced_type)


# ──────────────────────────────────────────────────────────────────────
# Core flow
# ──────────────────────────────────────────────────────────────────────

def _run_with_forced_type(forced_type=None):
	if not gemini_api.has_gemini_keys():
		control.notification(message=getLS(40612))  # "Configura al menos una API Key de Gemini"
		return
	k = control.keyboard('', getLS(40611))  # "Describe lo que quieres ver"
	k.doModal()
	prompt = k.getText().strip() if k.isConfirmed() else None
	if not prompt:
		return control.closeAll()
	_save_to_history(prompt, forced_type)
	_execute_prompt(prompt, forced_type)


def _execute_prompt(prompt, forced_type=None):
	control.notification(message=getLS(40614), time=2000)  # "Buscando con Gemini..."
	intent = gemini_api.interpret_prompt(prompt)
	if not intent:
		err = gemini_api.last_error_message() or ''
		msg = getLS(40613)  # "Sin resultados de búsqueda IA"
		if err: msg = '%s: %s' % (msg, err[:100])
		control.notification(message=msg, time=6000)
		# IMPORTANT: we MUST navigate somewhere (even on failure) because this handler
		# was invoked from an isFolder=False directory item. If we just return, Kodi
		# keeps DialogBusy open waiting for a listing that will never come, producing
		# the UI "loop" the user sees. Navigate back to the AI Search history page.
		_navigate_back_to_history(forced_type)
		return
	media_type = forced_type or intent.get('media_type', 'movie')
	url = _build_tmdb_url(media_type, intent, prompt)
	if not url:
		control.notification(message=getLS(40613))
		_navigate_back_to_history(forced_type)
		return
	control.closeAll()
	action = 'tmdbmovies' if media_type == 'movie' else 'tmdbTvshows'
	target = '%s/?action=%s&url=%s' % (SYSADDON, action, quote_plus(url))
	control.execute('ActivateWindow(Videos,%s,return)' % target)


def _navigate_back_to_history(forced_type):
	"""After a failed search, push the user back to the appropriate AI Search
	history listing so Kodi closes DialogBusy and the UI stays responsive."""
	control.closeAll()
	if forced_type == 'movie':
		history_action = 'aiSearchMovies'
	elif forced_type == 'tvshow':
		history_action = 'aiSearchTvshows'
	else:
		history_action = 'aiSearch'
	target = '%s/?action=%s' % (SYSADDON, history_action)
	control.execute('ActivateWindow(Videos,%s,return)' % target)


# ──────────────────────────────────────────────────────────────────────
# TMDb URL construction
# ──────────────────────────────────────────────────────────────────────

def _build_tmdb_url(media_type, intent, prompt):
	"""Try Discover first; fall back to title-search seed."""
	discover_url = _build_discover_url(media_type, intent)
	if discover_url and _discover_has_results(discover_url):
		return discover_url
	# Fallback: search for first example_title — luc_kodi resolves it via TMDb search.
	example_titles = intent.get('example_titles') or []
	title = example_titles[0] if example_titles else prompt
	base = 'movie' if media_type == 'movie' else 'tv'
	# quote_plus produces %XX sequences; escape to %%XX so later `url % API_key` doesn't choke.
	encoded_query = quote_plus(title).replace('%', '%%')
	return '%s/search/%s?api_key=%%s&language=en-US&query=%s&include_adult=false&page=1' % (TMDB_BASE, base, encoded_query)


def _build_discover_url(media_type, intent):
	genre_ids = _resolve_genre_ids(media_type, intent.get('genres', []))
	keyword_ids = _resolve_keyword_ids(_intent_keyword_terms(intent))
	cast_ids = _resolve_cast_ids(media_type, intent.get('people', []))
	if not any((genre_ids, keyword_ids, cast_ids)):
		return None
	base = 'movie' if media_type == 'movie' else 'tv'
	# IMPORTANT: We build the URL by hand (not via urlencode) because luc_kodi's
	# pipeline does `url % API_key` afterwards. Any urlencoded character (%2C, %7C, ...)
	# would be interpreted as a format specifier and crash. TMDb accepts raw `,` and `|`.
	# ALSO IMPORTANT: luc_kodi's tmdb_list() builds the "next page" link via
	# `url.split('&page=', 1)[0] + '&page=N+1'`, which TRUNCATES everything after
	# &page=. So `page=1` MUST be the LAST parameter, or filters get lost on page 2+.
	parts = ['api_key=%s', 'language=en-US', 'sort_by=popularity.desc', 'include_adult=false']
	# Spanish-language preference
	if intent.get('spanish_language_preferred'):
		parts.append('with_original_language=es')
		parts.append('region=ES')
	else:
		parts.append('region=US')
	# Date bounds
	current = str(date.today())
	start_year, end_year = _year_range(intent)
	if media_type == 'movie':
		lte_value = ('%s-12-31' % end_year) if end_year else current
		parts.append('primary_release_date.lte=%s' % lte_value)
		if start_year: parts.append('primary_release_date.gte=%s-01-01' % start_year)
	else:
		parts.append('include_null_first_air_dates=false')
		lte_value = ('%s-12-31' % end_year) if end_year else current
		parts.append('first_air_date.lte=%s' % lte_value)
		if start_year: parts.append('first_air_date.gte=%s-01-01' % start_year)
	if genre_ids:
		# OR (`|`) instead of AND (`,`): broader & far more relevant results.
		# AND made "shark movies" need to be horror AND thriller AND action
		# simultaneously — which excludes Jaws, The Meg, 47 Meters Down, etc.
		# Keywords already provide the tight thematic filter; genres just broaden.
		parts.append('with_genres=%s' % '|'.join(str(i) for i in genre_ids[:4]))
	if keyword_ids:
		parts.append('with_keywords=%s' % '|'.join(str(i) for i in keyword_ids[:5]))  # OR
	if cast_ids:
		key_name = 'with_cast' if media_type == 'movie' else 'with_people'
		parts.append('%s=%s' % (key_name, ','.join(str(i) for i in cast_ids[:3])))
	# page=1 MUST be last — see comment above about luc_kodi pagination.
	parts.append('page=1')
	return '%s/discover/%s?%s' % (TMDB_BASE, base, '&'.join(parts))


# ──────────────────────────────────────────────────────────────────────
# TMDb resolvers (genre, keyword, cast)
# ──────────────────────────────────────────────────────────────────────

def _resolve_genre_ids(media_type, genres):
	lookup = MOVIE_GENRES if media_type == 'movie' else TV_GENRES
	resolved = []
	for genre in genres:
		gid = lookup.get(_normalize(genre))
		if gid and gid not in resolved:
			resolved.append(gid)
	return resolved


def _resolve_keyword_ids(keywords):
	from resources.lib.indexers.tmdb import TMDb
	api = TMDb()
	api_key = api.API_key
	resolved = []
	for kw in keywords:
		kw = (kw or '').strip()
		if not kw: continue
		url = '%s/search/keyword?api_key=%s&query=%s&page=1' % (TMDB_BASE, api_key, quote_plus(kw))
		# Cache 168h: keywords are stable
		data = cache.get(api.get_request, 168, url)
		if not data or not isinstance(data, dict): continue
		results = data.get('results') or []
		if not results: continue
		# Prefer exact case-insensitive match, else first result
		match = None
		nkw = _normalize(kw)
		for r in results:
			if _normalize(r.get('name', '')) == nkw:
				match = r
				break
		if not match:
			match = results[0]
		mid = match.get('id')
		if mid and mid not in resolved:
			resolved.append(mid)
	return resolved


def _resolve_cast_ids(media_type, people):
	from resources.lib.indexers.tmdb import TMDb
	api = TMDb()
	api_key = api.API_key
	resolved = []
	for person in people:
		person = (person or '').strip()
		if not person: continue
		url = '%s/search/person?api_key=%s&query=%s&include_adult=false&page=1' % (TMDB_BASE, api_key, quote_plus(person))
		data = cache.get(api.get_request, 168, url)
		if not data or not isinstance(data, dict): continue
		results = data.get('results') or []
		if not results: continue
		match = None
		nperson = _normalize(person)
		for r in results:
			if _normalize(r.get('name', '')) == nperson:
				match = r
				break
		if not match:
			match = results[0]
		pid = match.get('id')
		if pid and pid not in resolved:
			resolved.append(pid)
	return resolved


def _discover_has_results(discover_url):
	"""Quick probe: does this discover URL return at least one item?"""
	from resources.lib.indexers.tmdb import TMDb
	api = TMDb()
	try:
		filled = discover_url % api.API_key
		data = cache.get(api.get_request, 24, filled)
		if not data or not isinstance(data, dict): return False
		return bool(data.get('results'))
	except Exception:
		return False


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _intent_keyword_terms(intent):
	"""Combine keywords + tone descriptors, but skip terms that are also names.

	The model asked for "gritty Scorsese crime films" will often place
	"Martin Scorsese" in people and a bare "scorsese" in tone_descriptors.
	Whole-string comparison misses that ("scorsese" != "martin scorsese"),
	so the surname slipped through and resolved to a spurious TMDb keyword
	that narrowed the query to nothing. Matching is done on tokens instead:
	a term is dropped when every one of its tokens belongs to some person's
	name. This can misfire on a keyword that happens to be a surname ("bay"
	alongside a request naming Michael Bay) at the cost of one lost keyword,
	which is far cheaper than the empty result set the alternative produces."""
	name_tokens, full_names = set(), set()
	for person in intent.get('people', []):
		normalized = _normalize(person)
		if not normalized: continue
		full_names.add(normalized)
		name_tokens.update(normalized.split())

	def _is_name(term):
		normalized = _normalize(term)
		if not normalized: return True
		if normalized in full_names: return True
		tokens = normalized.split()
		return bool(tokens) and all(token in name_tokens for token in tokens)

	combined = list(intent.get('keywords', [])) + list(intent.get('tone_descriptors', []))
	return [t for t in combined if not _is_name(t)]


def _year_range(intent):
	year_range = intent.get('year_range') or {}
	start = year_range.get('start')
	end = year_range.get('end')
	try: start = int(start) if start else None
	except Exception: start = None
	try: end = int(end) if end else None
	except Exception: end = None
	if all((start, end)) and start > end:
		start, end = end, start
	return start, end


def _normalize(value):
	import re
	value = (value or '').lower().strip()
	value = value.replace('&', ' ')
	value = re.sub(r'[^a-z0-9]+', ' ', value)
	return ' '.join(value.split())


# ──────────────────────────────────────────────────────────────────────
# Search history persistence (own table, mirrors movies/tvshow tables)
# ──────────────────────────────────────────────────────────────────────

def _save_to_history(prompt, forced_type):
	"""Save prompt to dedicated AI search history table."""
	from sqlite3 import dbapi2 as database
	table = _history_table(forced_type)
	try:
		dbcon = database.connect(control.searchFile)
		dbcur = dbcon.cursor()
		dbcur.executescript('CREATE TABLE IF NOT EXISTS %s (ID Integer PRIMARY KEY AUTOINCREMENT, term);' % table)
		dbcur.execute('INSERT INTO %s VALUES (?,?)' % table, (None, prompt))
		dbcon.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass


def _history_table(forced_type):
	if forced_type == 'movie': return 'ai_movies'
	if forced_type == 'tvshow': return 'ai_tvshow'
	return 'ai_auto'


def history(forced_type=None):
	"""Render the AI search history list."""
	from resources.lib.menus import navigator
	from sqlite3 import dbapi2 as database
	import re as _re
	nav = navigator.Navigator()
	highlight_color = control.getHighlightColor()
	# "Buscar nueva..." entry — action depends on forced type
	new_action = 'aiSearchnew' if forced_type is None else ('aiSearchnewMovies' if forced_type == 'movie' else 'aiSearchnewTvshows')
	nav.addDirectoryItem(getLS(32603) % highlight_color, new_action, 'search.png', 'DefaultAddonsSearch.png', isFolder=False)
	table = _history_table(forced_type)
	delete_option = False
	try:
		dbcon = database.connect(control.searchFile)
		dbcur = dbcon.cursor()
		dbcur.executescript('CREATE TABLE IF NOT EXISTS %s (ID Integer PRIMARY KEY AUTOINCREMENT, term);' % table)
		dbcur.execute('SELECT * FROM %s ORDER BY ID DESC' % table)
		dbcon.commit()
		seen = []
		for (_id, term) in sorted(dbcur.fetchall(), key=lambda k: _re.sub(r'(^the |^a |^an |^el |^la |^los |^las |^un |^una )', '', k[1].lower()), reverse=False):
			if term not in seen:
				delete_option = True
				term_action = 'aiSearchterm' if forced_type is None else ('aiSearchtermMovies' if forced_type == 'movie' else 'aiSearchtermTvshows')
				nav.addDirectoryItem(term, '%s&name=%s' % (term_action, quote_plus(term)), 'search.png', 'DefaultAddonsSearch.png', isSearch=True, table=table)
				seen.append(term)
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: dbcur.close()
		except Exception: pass
		try: dbcon.close()
		except Exception: pass
	if delete_option:
		nav.addDirectoryItem(32605, 'cache_clearSearch', 'tools.png', 'DefaultAddonService.png', isFolder=False)
	nav.endDirectory()
