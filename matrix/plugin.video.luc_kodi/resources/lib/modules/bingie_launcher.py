# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Launcher for the Bingie-style content grid (modern ui).

	Fetches the same item list the normal directory would build, shows it in the
	skin-independent grid window, and routes the chosen item back into the
	existing play / seasons flow.  No scraping or playback logic is duplicated.

	Session cache: keeps the loaded items + scroll position per category url, so
	that returning to a category (e.g. after viewing a show's seasons) reopens
	the grid where the user left off instead of starting over.
"""

from urllib.parse import quote_plus
from json import dumps as jsdumps
from resources.lib.modules import control


# module-level session cache: {cache_key: {'first_page':[...], 'pos':int, 'page':int}}
_SESSION = {}


# ──────────────────────── fetch helpers ────────────────────────
def _fetch_movies(url, tmdb=False):
	from resources.lib.menus import movies
	m = movies.Movies()
	items = (m.getTMDb(url, create_directory=False) if tmdb
			 else m.get(url, create_directory=False)) or []
	return [i for i in items if (i.get('tmdb') or i.get('imdb')) and i.get('title')]


def _fetch_tvshows(url, tmdb=False):
	from resources.lib.menus import tvshows
	t = tvshows.TVshows()
	items = (t.getTMDb(url, create_directory=False) if tmdb
			 else t.get(url, create_directory=False)) or []
	return [i for i in items if (i.get('tmdb') or i.get('imdb')) and (i.get('tvshowtitle') or i.get('title'))]


def _key(media_type, url):
	return '%s::%s' % (media_type, url or '')


# ──────────────────────── public entrypoints ────────────────────────
def show_movies(url, page_title=None, tmdb=False):
	_run('movie', url, tmdb, page_title or control.lang(32001), _fetch_movies)


def show_tvshows(url, page_title=None, tmdb=False):
	_run('tvshow', url, tmdb, page_title or control.lang(32002), _fetch_tvshows)


def _run(media_type, url, tmdb, page_title, fetch_fn):
	key = _key(media_type, url)
	cached = _SESSION.get(key)
	if cached and cached.get('first_page'):
		# resume: reuse the first page's items (cheap) and let the window
		# re-fetch forward to the page the user had reached.
		items = cached['first_page']; start_pos = cached.get('pos', 0)
		start_page = cached.get('page', 0)
	else:
		items = fetch_fn(url, tmdb)
		if not items:
			control.notification(title=(32001 if media_type == 'movie' else 32002), message=33049); return
		start_pos = 0; start_page = 0

	def fetch_page(next_url):
		return fetch_fn(next_url, tmdb)

	from resources.lib.windows.bingie_grid import BingieGridXML
	window = BingieGridXML('bingie_grid.xml', control.addonPath(control.addonId()),
							items=items, page_title=page_title, media_type=media_type,
							fetch_page=fetch_page, start_position=start_pos,
							start_page=start_page)
	pos, chosen, last_pos, first_page, last_next, last_page = window.run()
	del window

	# persist session so re-entry resumes on the same page / position.
	# we only need the FIRST page's items to rebuild; later pages are re-fetched.
	_SESSION[key] = {'first_page': first_page, 'pos': last_pos, 'page': last_page}
	# keep only the most recent few categories cached
	if len(_SESSION) > 6:
		for k in list(_SESSION.keys())[:-6]:
			_SESSION.pop(k, None)

	if chosen is None:
		return
	if media_type == 'movie': _play_movie(chosen)
	else: _open_seasons(chosen)


# ──────────────────────── routing of selection ────────────────────────
def _play_movie(i):
	systitle = quote_plus(i.get('title', ''))
	year = i.get('year', '')
	imdb = i.get('imdb', '')
	tmdb = i.get('tmdb', '')
	meta = quote_plus(jsdumps(i))
	cmd = ('RunPlugin(plugin://plugin.video.luc_kodi/?action=play_Item'
			'&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&bingie=1)'
			% (systitle, year, imdb, tmdb, meta))
	control.execute(cmd)


def open_seasons_window(i):
	"""Public entrypoint used by the grid to open seasons in place."""
	_open_seasons(i)


def _open_seasons(i):
	"""Open the Bingie-style Seasons+Episodes window for the chosen show."""
	from resources.lib.modules import log_utils
	try:
		tvshowtitle = i.get('tvshowtitle') or i.get('title', '')
		year = i.get('year', '')
		imdb = i.get('imdb', '')
		tmdb = i.get('tmdb', '')
		tvdb = i.get('tvdb', '')

		# Build the FULL art dict exactly like tvshowDirectory does. seasons.tmdb_list
		# reads art['icon'], art['thumb'], art['banner'], art['clearlogo'] etc. with
		# hard keys, so a partial dict makes every season raise KeyError -> empty list
		# -> "Nothing Was Found". We therefore resolve ALL keys here with fallbacks.
		prefer_tmdb = control.setting('prefer.tmdbArt') == 'true'
		use_fanart = control.setting('fanart') == 'true'
		g = i.get
		_addonPoster = control.addonPoster()
		_addonFanart = control.addonFanart()
		try: _addonBanner = control.addonBanner()
		except Exception: _addonBanner = ''
		if prefer_tmdb:
			poster = g('poster3') or g('poster') or g('poster2') or _addonPoster
			clearlogo = g('tmdblogo') or g('clearlogo', '') or ''
		else:
			poster = g('poster2') or g('poster3') or g('poster') or _addonPoster
			clearlogo = g('clearlogo') or g('tmdblogo', '') or ''
		if use_fanart:
			if prefer_tmdb: fanart = g('fanart3') or g('fanart') or g('fanart2') or _addonFanart
			else: fanart = g('fanart2') or g('fanart3') or g('fanart') or _addonFanart
		else:
			fanart = _addonFanart
		banner = g('banner3') or g('banner2') or g('banner') or _addonBanner or ''
		thumb = g('thumb') or poster
		icon = g('icon') or poster
		landscape = g('landscape') or fanart
		clearart = g('clearart', '') or ''
		existing = i.get('art')
		art = existing if isinstance(existing, dict) and existing.get('icon') and existing.get('thumb') else {}
		if not art:
			art = {'poster': poster, 'tvshow.poster': poster, 'fanart': fanart,
					'icon': icon, 'thumb': thumb, 'banner': banner,
					'clearlogo': clearlogo, 'tvshow.clearlogo': clearlogo,
					'clearart': clearart, 'tvshow.clearart': clearart,
					'landscape': landscape}
		art_json = jsdumps(art) if not isinstance(art, str) else art

		from resources.lib.menus import seasons as seasons_menu
		from resources.lib.menus import episodes as episodes_menu

		# pull seasons (same metadata the default directory builds)
		try:
			s = seasons_menu.Seasons()
			season_list = s.get(tvshowtitle, year, imdb, tmdb, tvdb, art_json,
								idx=True, create_directory=False) or []
		except Exception:
			log_utils.error()
			season_list = []
		if not season_list:
			control.notification(title=tvshowtitle or 32002, message=33049)
			return

		def episodes_fetch(season_meta):
			try:
				snum = season_meta.get('season')
				meta = jsdumps(season_meta)
				ep = episodes_menu.Episodes()
				return ep.get(tvshowtitle, year, imdb, tmdb, tvdb, meta,
								season=snum, create_directory=False) or []
			except Exception:
				log_utils.error()
				return []

		from resources.lib.windows.bingie_episodes import BingieEpisodesXML
		window = BingieEpisodesXML('bingie_episodes.xml', control.addonPath(control.addonId()),
									tvshowtitle=tvshowtitle, year=year, imdb=imdb, tmdb=tmdb,
									tvdb=tvdb, art=art_json, page_title=tvshowtitle,
									seasons=season_list, episodes_fetch=episodes_fetch,
									start_season_index=0)
		window.run()
		del window
	except Exception:
		log_utils.error()
