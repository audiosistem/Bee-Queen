# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Launcher for the Bingie-style SECTION HOME (fixed ui for Movies & TV).

	Builds the per-section list of category rows ("shortcuts": each row is the
	live content of a category, browsable and playable in place), opens the
	skin-independent WindowXML, and lets it run. Selecting a poster plays the
	title directly through the addon's normal scrape/source-select flow; rows
	paginate in blocks of 20. Nothing here duplicates scraping/playback.
"""

from resources.lib.modules import control


# Each row: (label, url_token, fetch_kind). Tokens resolve via movies.get()/
# tvshows.get() (getattr(self, token+'_link')) or getTMDb() for tmdb kind.
# Mirrors navigator.movies()/tvshows(); submenu-only entries (Genres, Years,
# Providers, Lists, Search, Collections, Networks, Calendars) are not rows.

_MOVIE_ROWS = [
	('Popular \u00b7 Trakt',      'traktpopular',         'trakt'),
	('Trending \u00b7 Trakt',     'trakttrending',        'trakt'),
	('Now Playing \u00b7 TMDb',   'tmdb_nowplaying',      'tmdb'),
	('Box Office \u00b7 Trakt',   'traktboxoffice',       'trakt'),
	('Top Rated \u00b7 TMDb',     'tmdb_toprated',        'tmdb'),
	('Anticipated \u00b7 Trakt',  'traktanticipated',     'trakt'),
	('Upcoming \u00b7 TMDb',      'tmdb_upcoming',        'tmdb'),
	('Recommended \u00b7 Trakt',  'traktrecommendations', 'trakt'),
	('SIMKL Trending - Today',    'simkltrendingtoday',   'trakt'),
	('SIMKL Trending - Week',     'simkltrendingweek',    'trakt'),
]

_TVSHOW_ROWS = [
	('Trending \u00b7 Trakt',     'trakttrending',        'trakt'),
	('Popular \u00b7 Trakt',      'traktpopular',         'trakt'),
	('Top Rated \u00b7 TMDb',     'tmdb_toprated',        'tmdb'),
	('Airing Today \u00b7 TMDb',  'tmdb_airingtoday',     'tmdb'),
	('On The Air \u00b7 TMDb',    'tmdb_ontheair',        'tmdb'),
	('Recommended \u00b7 Trakt',  'traktrecommendations', 'trakt'),
	('SIMKL Trending - Today',    'simkltrendingtoday',   'trakt'),
	('SIMKL Trending - Week',     'simkltrendingweek',    'trakt'),
]


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


def show_movies():
	_run('movie', _MOVIE_ROWS, control.lang(32001), _fetch_movies)


def show_tvshows():
	_run('tvshow', _TVSHOW_ROWS, control.lang(32002), _fetch_tvshows)


def _run(media_type, row_defs, section_title, fetch_fn):
	rows = [{'label': lbl, 'url': token, 'tmdb': (kind == 'tmdb')}
			for (lbl, token, kind) in row_defs]
	from resources.lib.windows.bingie_section_home import BingieSectionHomeXML
	window = BingieSectionHomeXML('bingie_section_home.xml', control.addonPath(control.addonId()),
									rows=rows, section_title=section_title, media_type=media_type,
									fetch_fn=fetch_fn)
	window.run()
	del window
