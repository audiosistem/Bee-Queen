# -*- coding: utf-8 -*-
"""
	Umbrella Add-on
"""

import sqlite3 as db
from resources.lib.modules import control

menuFile = control.joinPath(control.dataPath, 'menu.db')

# Tuple format:
# (item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom, condition_key, queue, alt_label)
# label     = string ID used when "Add meta provider labels" is ON  (e.g. "TMDb: Popular")
# alt_label = string ID used when the setting is OFF (e.g. "Popular"); None means same as label

_ROOT_DEFAULTS = [
	('searchMovies',    '33042', 'movieSearch',                            'trakt.png',        'searchmovies.png', 1, 1, 1, 0,  0, None, 0, None),
	('searchTVShows',   '33043', 'tvSearch',                               'trakt.png',        'searchtv.png',     1, 1, 1, 1,  0, None, 0, None),
	('movies',          '33046', 'movieNavigator',                         'movies.png',       'movies.png',       1, 1, 1, 2,  0, None, 0, None),
	('tvshows',         '33047', 'tvNavigator',                            'tvshows.png',      'tvshows.png',      1, 1, 1, 3,  0, None, 0, None),
	('anime',           'Anime', 'anime_Navigator',                        'boxsets.png',      'boxsets.png',      1, 1, 1, 4,  0, None, 0, None),
	('myMovies',        '32003', 'mymovieNavigator',                       'mymovies.png',     'mymovies.png',     1, 1, 1, 5,  0, None, 0, None),
	('myTVShows',       '32004', 'mytvNavigator',                          'mytvshows.png',    'mytvshows.png',    1, 1, 1, 6,  0, None, 0, None),
	('youtube',         'YouTube Videos', 'youtube',                       'youtube.png',      'youtube.png',      1, 1, 1, 7,  0, None, 0, None),
	('search',          '32010', 'tools_searchNavigator',                  'search.png',       'search.png',       1, 1, 1, 8,  0, None, 0, None),
	('tools',           '32008', 'tools_toolNavigator',                    'tools.png',        'tools.png',        1, 1, 1, 9,  0, None, 0, None),
	('downloads',       '32009', 'downloadNavigator',                      'downloads.png',    'downloads.png',    1, 1, 1, 10, 0, None, 0, None),
	('favourites',      '40464', 'favouriteNavigator',                     'highly-rated.png', 'highly-rated.png', 1, 1, 1, 11, 0, None, 0, None),
	('premiumServices', 'Premium Services', 'premiumNavigator',            'premium.png',      'premium.png',      1, 1, 1, 12, 0, None, 0, None),
	('changelog',       '32014', 'tools_ShowChangelog&name=Umbrella',      'changelog.png',    'changelog.png',    0, 1, 0, 13, 0, None, 0, None),
	('fullChangelog',   '40589', 'tools_ShowFullChangelog&name=Umbrella',  'changelog.png',    'changelog.png',    0, 1, 0, 14, 0, None, 0, None),
]

_MOVIES_DEFAULTS = [
	('mv_tmdb_nowplaying',     '32423', 'tmdbmovies&url=tmdb_nowplaying',                    'tmdb.png',        'in-theaters.png',   1, 1, 1,  0, 0, None,             0, '32422'),
	('mv_trakt_anticipated',   '32425', 'movies&url=traktanticipated',                        'trakt.png',       'in-theaters.png',   1, 1, 1,  1, 0, None,             0, '32424'),
	('mv_tmdb_upcoming',       '32427', 'tmdbmovies&url=tmdb_upcoming',                       'tmdb.png',        'in-theaters.png',   1, 1, 1,  2, 0, None,             0, '32426'),
	('mv_tmdb_disc_released',  '40268', 'tmdbmovies&url=tmdb_discovery_released',             'tmdb.png',        'trending.png',      1, 1, 1,  3, 0, None,             0, '40269'),
	('mv_tmdb_disc_month',     '40410', 'tmdbmovies&url=tmdb_discovery_this_month',           'tmdb.png',        'trending.png',      1, 1, 1,  4, 0, None,             0, '40411'),
	('mv_tmdb_disc_month_rel', '40412', 'tmdbmovies&url=tmdb_discovery_this_month_released',  'tmdb.png',        'trending.png',      1, 1, 1,  5, 0, None,             0, '40413'),
	('mv_dvd_release',         '40474', 'dvdReleaseList',                                     'tmdb.png',        'trending.png',      1, 1, 1,  6, 0, None,             0, '40475'),
	('mv_tmdb_popular',        '32431', 'tmdbmovies&url=tmdb_popular',                        'tmdb.png',        'most-popular.png',  1, 1, 1,  7, 0, None,             0, '32430'),
	('mv_trakt_popular',       '32433', 'movies&url=traktpopular',                            'trakt.png',       'most-popular.png',  1, 1, 1,  8, 0, None,             0, '32430'),
	('mv_tmdb_boxoffice',      '32436', 'tmdbmovies&url=tmdb_boxoffice',                      'tmdb.png',        'box-office.png',    1, 1, 1,  9, 0, None,             0, '32434'),
	('mv_trakt_boxoffice',     '32437', 'movies&url=traktboxoffice',                          'trakt.png',       'box-office.png',    1, 1, 1, 10, 0, None,             0, '32434'),
	('mv_tmdb_toprated',       '32441', 'tmdbmovies&url=tmdb_toprated',                       'tmdb.png',        'most-voted.png',    1, 1, 1, 11, 0, None,             0, '32440'),
	('mv_trakt_trending',      '32443', 'movies&url=trakttrending',                           'trakt.png',       'trending.png',      1, 1, 1, 12, 0, None,             0, '32442'),
	('mv_trakt_trend_recent',  '40388', 'movies&url=trakttrending_recent',                    'trakt.png',       'trending.png',      1, 1, 1, 13, 0, None,             0, '40389'),
	('mv_simkl_today',         '40350', 'simklMovies&url=simkltrendingtoday',                 'simkl.png',       'trending.png',      1, 1, 1, 14, 0, 'simkl_token',    0, '40351'),
	('mv_simkl_week',          '40352', 'simklMovies&url=simkltrendingweek',                  'simkl.png',       'trending.png',      1, 1, 1, 15, 0, 'simkl_token',    0, '40353'),
	('mv_simkl_month',         '40354', 'simklMovies&url=simkltrendingmonth',                 'simkl.png',       'trending.png',      1, 1, 1, 16, 0, 'simkl_token',    0, '40355'),
	('mv_tmdb_trend_day',      '40330', 'movies&url=tmdbrecentday',                           'tmdb.png',        'trending.png',      1, 1, 1, 17, 0, None,             0, '40702'),
	('mv_tmdb_trend_week',     '40331', 'movies&url=tmdbrecentweek',                          'tmdb.png',        'trending.png',      1, 1, 1, 18, 0, None,             0, '40703'),
	('mv_trakt_recommended',   '32445', 'movies&url=traktrecommendations',                    'trakt.png',       'highly-rated.png',  1, 1, 1, 19, 0, None,             0, '32444'),
	('mv_lib_similar',         '40392', 'moviesimilarFromLibrary',                            'most-popular.png','most-popular.png',  1, 1, 1, 20, 0, 'has_lib_movies', 0, None),
	('mv_lib_recommended',     '40393', 'movierecommendedFromLibrary',                        'featured.png',    'featured.png',      1, 1, 1, 21, 0, 'has_lib_movies', 0, None),
	('mv_trakt_recent',        '40255', 'movies&url=traktbasedonrecent',                      'trakt.png',       'years.png',         1, 1, 1, 22, 0, None,             0, '40256'),
	('mv_trakt_similar',       '40260', 'movies&url=traktbasedonsimilar',                     'trakt.png',       'years.png',         1, 1, 1, 23, 0, None,             0, '40261'),
	('mv_oscar_nominees',      '32452', 'movies&url=oscars',                                  'trakt.png',       'oscar-winners.png', 1, 1, 1, 24, 0, None,             0, '32451'),
	('mv_tmdb_genres',         '32486', 'movieGenres&url=tmdb_genre',                         'tmdb.png',        'genres.png',        1, 1, 1, 25, 0, None,             0, '32455'),
	('mv_trakt_genres',        '40493', 'movieGenres&url=trakt_movie_genre',                  'trakt.png',       'genres.png',        1, 1, 1, 26, 0, None,             0, '32455'),
	('mv_tmdb_years',          '32485', 'movieYears&url=tmdb_year',                           'tmdb.png',        'years.png',         1, 1, 1, 27, 0, None,             0, '32457'),
	('mv_tmdb_certs',          '32487', 'movieCertificates&url=tmdb_certification',           'tmdb.png',        'certificates.png',  1, 1, 1, 28, 0, None,             0, '32463'),
	('mv_collections',         '32000', 'collections_Navigator',                              'boxsets.png',     'boxsets.png',       1, 1, 1, 29, 0, None,             0, None),
	('mv_mdb_top_lists',       '40084', 'mdbTopListMovies',                                   'mdblist.png',     'movies.png',        1, 1, 1, 30, 0, 'mdblist_token',  0, None),
	('mv_trakt_pop_lists',     '32417', 'movies_PublicLists&url=trakt_popularLists',          'trakt.png',       'movies.png',        1, 1, 1, 31, 0, None,             0, None),
	('mv_trakt_trend_lists',   '32418', 'movies_PublicLists&url=trakt_trendingLists',         'trakt.png',       'movies.png',        1, 1, 1, 32, 0, None,             0, None),
	('mv_trakt_search_lists',  '32419', 'movies_SearchLists&media_type=movies',               'trakt.png',       'movies.png',        0, 1, 1, 33, 0, None,             0, None),
	('mv_mylists_widget',      '32003', 'mymovieliteNavigator',                               'mymovies.png',    'mymovies.png',      1, 1, 1, 34, 0, 'not_lite',       0, None),
	('mv_fav_movies',          '40465', 'getFavouritesMovies&url=favourites_movies',          'movies.png',      'movies.png',        1, 1, 1, 35, 0, 'favorite_movie', 0, None),
	('mv_person_search',       '33044', 'moviePerson',                                        'imdb.png',        'people-search.png', 0, 1, 1, 36, 0, 'not_lite',       0, None),
	('mv_movie_search',        '33042', 'movieSearch',                                        'trakt.png',       'search.png',        1, 1, 1, 37, 0, 'not_lite',       0, None),
]

_TVSHOWS_DEFAULTS = [
	('tv_originals',          '40077', 'tvOriginals',                             'tvmaze.png',  'networks.png',     1, 1, 1,  0, 0, None,              0, '40070'),
	('tv_tmdb_popular',       '32431', 'tmdbTvshows&url=tmdb_popular',            'tmdb.png',    'most-popular.png', 1, 1, 1,  1, 0, None,              1, '32430'),
	('tv_trakt_popular',      '32433', 'tvshows&url=traktpopular',                'trakt.png',   'most-popular.png', 1, 1, 1,  2, 0, None,              1, '32430'),
	('tv_tmdb_toprated',      '32441', 'tmdbTvshows&url=tmdb_toprated',           'tmdb.png',    'most-voted.png',   1, 1, 1,  3, 0, None,              0, '32440'),
	('tv_trakt_trending',     '32443', 'tvshows&url=trakttrending',               'trakt.png',   'trending.png',     1, 1, 1,  4, 0, None,              0, '32442'),
	('tv_trakt_trend_recent', '40388', 'tvshows&url=trakttrending_recent',        'trakt.png',   'trending.png',     1, 1, 1,  5, 0, None,              0, '40389'),
	('tv_simkl_today',        '40350', 'simklTvshows&url=simkltrendingtoday',     'simkl.png',   'trending.png',     1, 1, 1,  6, 0, 'simkl_token',     0, '40351'),
	('tv_simkl_week',         '40352', 'simklTvshows&url=simkltrendingweek',      'simkl.png',   'trending.png',     1, 1, 1,  7, 0, 'simkl_token',     0, '40353'),
	('tv_simkl_month',        '40354', 'simklTvshows&url=simkltrendingmonth',     'simkl.png',   'trending.png',     1, 1, 1,  8, 0, 'simkl_token',     0, '40355'),
	('tv_tmdb_trend_day',     '40330', 'tvshows&url=tmdbrecentday',               'tmdb.png',    'trending.png',     1, 1, 1,  9, 0, None,              0, '40702'),
	('tv_tmdb_trend_week',    '40331', 'tvshows&url=tmdbrecentweek',              'tmdb.png',    'trending.png',     1, 1, 1, 10, 0, None,              0, '40703'),
	('tv_trakt_recommended',  '32445', 'tvshows&url=traktrecommendations',        'trakt.png',   'highly-rated.png', 1, 1, 1, 11, 0, None,              1, '32444'),
	('tv_trakt_recent',       '40255', 'tvshows&url=traktbasedonrecent',          'trakt.png',   'years.png',        1, 1, 1, 12, 0, None,              0, '40256'),
	('tv_trakt_similar',      '40260', 'tvshows&url=traktbasedonsimilar',         'trakt.png',   'years.png',        1, 1, 1, 13, 0, None,              0, '40261'),
	('tv_tmdb_genres',        '32486', 'tvGenres&url=tmdb_genre',                 'tmdb.png',    'genres.png',       1, 1, 1, 14, 0, None,              0, '32455'),
	('tv_trakt_genres',       '40493', 'tvGenres&url=trakt_tvshow_genre',         'trakt.png',   'genres.png',       1, 1, 1, 15, 0, None,              0, '32455'),
	('tv_networks',           '32468', 'tvNetworks',                              'tmdb.png',    'networks.png',     1, 1, 1, 16, 0, None,              0, '32469'),
	('tv_tmdb_years',         '32485', 'tvYears&url=tmdb_year',                   'tmdb.png',    'years.png',        1, 1, 1, 17, 0, None,              0, '32457'),
	('tv_tmdb_airing',        '32467', 'tmdbTvshows&url=tmdb_airingtoday',        'tmdb.png',    'airing-today.png', 1, 1, 1, 18, 0, None,              0, '32465'),
	('tv_tmdb_onair',         '32472', 'tmdbTvshows&url=tmdb_ontheair',           'tmdb.png',    'new-tvshows.png',  1, 1, 1, 19, 0, None,              0, '32471'),
	('tv_tmdb_newshows',      '40661', 'tvshows&url=tmdb_newshows',               'tmdb.png',    'new-tvshows.png',  1, 1, 1, 20, 0, None,              0, '32475'),
	('tv_calendar',           '32450', 'calendars',                               'tvmaze.png',  'calendar.png',     1, 1, 1, 21, 0, None,              0, '32027'),
	('tv_mdb_top_lists',      '40084', 'mdbTopListTV',                            'mdblist.png', 'tvshows.png',      1, 1, 1, 22, 0, 'mdblist_token',   0, None),
	('tv_trakt_pop_lists',    '32417', 'tv_PublicLists&url=trakt_popularLists',   'trakt.png',   'tvshows.png',      1, 1, 1, 23, 0, None,              0, None),
	('tv_trakt_trend_lists',  '32418', 'tv_PublicLists&url=trakt_trendingLists',  'trakt.png',   'tvshows.png',      1, 1, 1, 24, 0, None,              0, None),
	('tv_trakt_search_lists', '32419', 'tv_SearchLists&media_type=shows',         'trakt.png',   'tvshows.png',      0, 1, 1, 25, 0, None,              0, None),
	('tv_mylists_widget',     '32004', 'mytvliteNavigator',                       'mytvshows.png','mytvshows.png',   1, 1, 1, 26, 0, 'not_lite',        0, None),
	('tv_fav_tvshows',        '40466', 'getFavouritesTVShows&url=favourites_tvshows','tvshows.png','tvshows.png',    1, 1, 1, 27, 0, 'favorite_tvshows', 0, None),
	('tv_person_search',      '33045', 'tvPerson',                                'imdb.png',    'people-search.png',0, 1, 1, 28, 0, 'not_lite',        0, None),
	('tv_search',             '33043', 'tvSearch',                                'trakt.png',   'search.png',       1, 1, 1, 29, 0, 'not_lite',        0, None),
]

_MYMOVIES_DEFAULTS = [
	('mymv_userlists',        '32039', 'movieUserlists',                                   'userlists.png', 'userlists.png', 1, 1, 1,  0, 0, None,                   0, None),
	('mymv_fav_movies',       '40465', 'getFavouritesMovies&url=favourites_movies',        'movies.png',    'movies.png',    1, 1, 1,  1, 0, 'favorite_movie',       0, None),
	('mymv_mdb_userlist',     '40681', 'mdbUserListMovies',                                'mdblist.png',   'mdblist.png',   1, 1, 1,  2, 0, 'mdblist_token',        0, '40699'),
	('mymv_mdb_watchlist',    '40682', 'mdbUserWatchListMovies',                           'mdblist.png',   'mdblist.png',   1, 1, 1,  3, 0, 'mdblist_token',        0, '40700'),
	('mymv_mdb_liked',        '40683', 'mdbLikedListMovies',                               'mdblist.png',   'mdblist.png',   1, 1, 1,  4, 0, 'mdblist_token',        0, '40701'),
	('mymv_mdb_unfinished',   '40686', 'mdblistMoviesUnfinished',                          'mdblist.png',   'mdblist.png',   1, 1, 1,  5, 0, 'mdblist_with_indicators', 1, '35308'),
	('mymv_tmdb_userlists',   'TMDb User Lists', 'tmdbUserListsMovies',                    'tmdb.png',      'tmdb.png',      1, 1, 1,  6, 0, 'tmdb_v4_token',        0, None),
	('mymv_tmdb_watchlist',   '40612', 'tmdbV4WatchlistMovies',                            'tmdb.png',      'tmdb.png',      1, 1, 1,  7, 0, 'tmdb_v4_token',        0, None),
	('mymv_simkl_completed',  '40548', 'movies&url=simklhistory',                          'simkl.png',     'simkl.png',     1, 1, 1,  8, 0, 'simkl_token',          0, None),
	('mymv_simkl_watchlist',  '40550', 'movies&url=simklwatchlist',                        'simkl.png',     'simkl.png',     1, 1, 1,  9, 0, 'simkl_token',          0, None),
	('mymv_simkl_dropped',    'Simkl Dropped', 'movies&url=simkldropped',                 'simkl.png',     'simkl.png',     1, 1, 1, 10, 0, 'simkl_token',          0, None),
	('mymv_trakt_unfinished', '40687', 'moviesUnfinished&url=traktunfinished',             'trakt.png',     'trakt.png',     1, 1, 1, 11, 0, 'trakt_with_indicators', 1, '35308'),
	('mymv_trakt_history',    '40695', 'movies&url=trakthistory',                          'trakt.png',     'trakt.png',     1, 1, 1, 12, 0, 'trakt_with_indicators', 1, '32036'),
	('mymv_trakt_watchlist',  '40696', 'movies&url=traktwatchlist',                        'trakt.png',     'trakt.png',     1, 1, 1, 13, 0, 'trakt_credentials',    0, '40700'),
	('mymv_trakt_collection', '40697', 'movies&url=traktcollection',                       'trakt.png',     'trakt.png',     1, 1, 1, 14, 0, 'trakt_credentials',    0, '32032'),
	('mymv_trakt_liked',      '40698', 'movies_LikedLists',                               'trakt.png',     'trakt.png',     1, 1, 1, 15, 0, 'trakt_credentials',     1, 'My Liked Lists'),
	('mymv_movies_menu',      '32031', 'movieliteNavigator',                               'movies.png',    'movies.png',    1, 1, 1, 16, 0, 'not_lite',             0, None),
	('mymv_person_search',    '33044', 'moviePerson',                                      'imdb.png',      'people-search.png', 0, 1, 1, 17, 0, 'not_lite',         0, None),
	('mymv_movie_search',     '33042', 'movieSearch',                                      'search.png',    'search.png',    1, 1, 1, 18, 0, 'not_lite',             0, None),
]

_MYTVSHOWS_DEFAULTS = [
	('mytv_userlists',         '32040', 'tvUserlists',                                          'userlists.png', 'userlists.png', 1, 1, 1,  0, 0, None,                    0, None),
	('mytv_fav_tvshows',       '40466', 'getFavouritesTVShows&url=favourites_tvshows',          'tvshows.png',   'tvshows.png',   1, 1, 1,  1, 0, 'favorite_tvshows',      0, None),
	('mytv_fav_episodes',      '40467', 'getFavouritesEpisodes',                                'tvshows.png',   'tvshows.png',   1, 1, 1,  2, 0, 'favorite_episodes',     0, None),
	('mytv_mdb_userlist',      '40681', 'mdbUserListTV',                                        'mdblist.png',   'mdblist.png',   1, 1, 1,  3, 0, 'mdblist_token',         0, '40699'),
	('mytv_mdb_watchlist',     '40682', 'mdbUserWatchListTVShows',                              'mdblist.png',   'mdblist.png',   1, 1, 1,  4, 0, 'mdblist_token',         0, '40700'),
	('mytv_mdb_liked',         '40683', 'mdbLikedListShows',                                    'mdblist.png',   'mdblist.png',   1, 1, 1,  5, 0, 'mdblist_token',         0, '40701'),
	('mytv_mdb_shows_prog',    '40684', 'mdblist_shows_progress&url=mdbprogress',               'mdblist.png',   'mdblist.png',   1, 1, 1,  6, 0, 'mdblist_with_indicators',1, '40401'),
	('mytv_mdb_ep_prog',       '40685', 'mdblist_calendar&url=mdbprogress',                     'mdblist.png',   'mdblist.png',   1, 1, 1,  7, 0, 'mdblist_with_indicators',1, '32037'),
	('mytv_mdb_unfinished',    '40686', 'mdblistEpisodesUnfinished',                            'mdblist.png',   'mdblist.png',   1, 1, 1,  8, 0, 'mdblist_with_indicators',1, '35308'),
	('mytv_local_shows_prog',  '40658', 'local_shows_progress&url=localprogress',               'icon.png',      'icon.png',      1, 1, 1,  9, 0, 'local_scrobble',        1, None),
	('mytv_local_calendar',    '40659', 'local_calendar&url=localprogress',                     'icon.png',      'icon.png',      1, 1, 1, 10, 0, 'local_scrobble',        1, None),
	('mytv_tmdb_userlists',    'TMDb User Lists', 'tmdbUserListsTV',                            'tmdb.png',      'tmdb.png',      1, 1, 1, 11, 0, 'tmdb_v4_token',         0, None),
	('mytv_tmdb_watchlist',    '40612', 'tmdbV4WatchlistTV',                                    'tmdb.png',      'tmdb.png',      1, 1, 1, 12, 0, 'tmdb_v4_token',         0, None),
	('mytv_simkl_ep_prog',     'Simkl Progress Episodes', 'simkl_calendar&url=/sync/all-items/shows/watching', 'simkl.png', 'simkl.png', 1, 1, 1, 13, 0, 'simkl_credentials', 1, None),
	('mytv_simkl_watching',    'Simkl Watching', 'tvshows&url=simklwatching',                  'simkl.png',     'simkl.png',     1, 1, 1, 14, 0, 'simkl_credentials',     1, None),
	('mytv_simkl_watchlist',   'Simkl Plan to Watch', 'tvshows&url=simklwatchlist',             'simkl.png',     'simkl.png',     1, 1, 1, 15, 0, 'simkl_credentials',     0, None),
	('mytv_simkl_onhold',      'Simkl On Hold', 'tvshows&url=simklonhold',                     'simkl.png',     'simkl.png',     1, 1, 1, 16, 0, 'simkl_credentials',     0, None),
	('mytv_simkl_completed',   'Simkl Completed', 'tvshows&url=simklhistory',                  'simkl.png',     'simkl.png',     1, 1, 1, 17, 0, 'simkl_credentials',     0, None),
	('mytv_simkl_dropped',     'Simkl Dropped', 'tvshows&url=simkldropped',                   'simkl.png',     'simkl.png',     1, 1, 1, 18, 0, 'simkl_credentials',     0, None),
	('mytv_trakt_unfinished',  '40687', 'episodesUnfinished&url=traktunfinished',               'trakt.png',     'trakt.png',     1, 1, 1, 19, 0, 'trakt_with_indicators',  1, '35308'),
	('mytv_trakt_ep_prog',     '40688', 'calendar&url=progress',                                'trakt.png',     'trakt.png',     1, 1, 1, 20, 0, 'trakt_with_indicators',  1, '32037'),
	('mytv_trakt_show_prog',   '40689', 'shows_progress&url=progresstv',                       'trakt.png',     'trakt.png',     1, 1, 1, 21, 0, 'trakt_with_indicators',  1, '40401'),
	('mytv_trakt_watched',     '40690', 'shows_watched&url=watchedtv',                         'trakt.png',     'trakt.png',     1, 1, 1, 22, 0, 'trakt_with_indicators',  1, '40433'),
	('mytv_trakt_upcoming',    '40691', 'upcomingProgress&url=progress',                       'trakt.png',     'trakt.png',     1, 1, 1, 23, 0, 'trakt_with_indicators',  1, '32019'),
	('mytv_trakt_cal_recent',  '40692', 'calendar&url=mycalendarRecent',                       'trakt.png',     'trakt.png',     1, 1, 1, 24, 0, 'trakt_with_indicators',  1, '32202'),
	('mytv_trakt_cal_upcoming','40693', 'calendar&url=mycalendarUpcoming',                     'trakt.png',     'trakt.png',     1, 1, 1, 25, 0, 'trakt_with_indicators',  1, '32203'),
	('mytv_trakt_cal_premiers','40694', 'calendar&url=mycalendarPremiers',                     'trakt.png',     'trakt.png',     1, 1, 1, 26, 0, 'trakt_with_indicators',  1, '32204'),
	('mytv_trakt_history',     '40695', 'calendar&url=trakthistory',                           'trakt.png',     'trakt.png',     1, 1, 1, 27, 0, 'trakt_with_indicators',  1, '32036'),
	('mytv_trakt_watchlist',   '40696', 'tvshows&url=traktwatchlist',                          'trakt.png',     'trakt.png',     1, 1, 1, 28, 0, 'trakt_credentials',     0, '40700'),
	('mytv_trakt_collection',  '40697', 'tvshows&url=traktcollection',                         'trakt.png',     'trakt.png',     1, 1, 1, 29, 0, 'trakt_credentials',     0, '32032'),
	('mytv_trakt_liked',       '40698', 'shows_LikedLists',                                    'trakt.png',     'trakt.png',     1, 1, 1, 30, 0, 'trakt_credentials',      1, 'My Liked Lists'),
	('mytv_tv_menu',           '32031', 'tvliteNavigator',                                     'tvshows.png',   'tvshows.png',   1, 1, 1, 31, 0, 'not_lite',              0, None),
	('mytv_person_search',     '33045', 'tvPerson',                                            'imdb.png',      'people-search.png', 0, 1, 1, 32, 0, 'not_lite',          0, None),
	('mytv_tv_search',         '33043', 'tvSearch',                                            'trakt.png',     'search.png',    1, 1, 1, 33, 0, 'not_lite',              0, None),
]

MENU_DEFAULTS = {
	'root':      _ROOT_DEFAULTS,
	'movies':    _MOVIES_DEFAULTS,
	'tvshows':   _TVSHOWS_DEFAULTS,
	'mymovies':  _MYMOVIES_DEFAULTS,
	'mytvshows': _MYTVSHOWS_DEFAULTS,
}

# item_id -> alt_label for migrating existing DB rows
_ALT_LABEL_MAP = {
	row[0]: row[12]
	for defaults in MENU_DEFAULTS.values()
	for row in defaults
	if row[12] is not None
}


def _get_connection():
	if not control.existsPath(control.dataPath):
		control.makeFile(control.dataPath)
	dbcon = db.connect(menuFile, timeout=60)
	dbcon.execute('PRAGMA journal_mode = WAL')
	dbcon.execute('PRAGMA synchronous = NORMAL')
	dbcon.execute('PRAGMA temp_store = memory')
	dbcon.row_factory = lambda c, r: {col[0]: r[i] for i, col in enumerate(c.description)}
	return dbcon


def _populate_defaults(dbcon, menu_name):
	defaults = MENU_DEFAULTS.get(menu_name, [])
	dbcon.executemany(
		'INSERT OR IGNORE INTO menu_items '
		'(menu_name, item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom, condition_key, queue, alt_label) '
		'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
		[(menu_name,) + row for row in defaults]
	)
	dbcon.commit()


def initialize(menu_name='root'):
	dbcon = _get_connection()
	dbcon.execute('''CREATE TABLE IF NOT EXISTS menu_items (
		id            INTEGER PRIMARY KEY AUTOINCREMENT,
		menu_name     TEXT NOT NULL,
		item_id       TEXT NOT NULL,
		label         TEXT NOT NULL,
		action        TEXT NOT NULL,
		icon          TEXT NOT NULL,
		poster        TEXT NOT NULL,
		is_folder     INTEGER NOT NULL DEFAULT 1,
		is_action     INTEGER NOT NULL DEFAULT 1,
		enabled       INTEGER NOT NULL DEFAULT 1,
		sort_order    INTEGER NOT NULL,
		is_custom     INTEGER NOT NULL DEFAULT 0,
		condition_key TEXT,
		queue         INTEGER NOT NULL DEFAULT 0,
		UNIQUE(menu_name, item_id)
	)''')
	dbcon.commit()
	for col_def in [
		('condition_key', 'TEXT'),
		('queue',         'INTEGER NOT NULL DEFAULT 0'),
		('alt_label',     'TEXT'),
	]:
		try:
			dbcon.execute('ALTER TABLE menu_items ADD COLUMN %s %s' % col_def)
		except db.OperationalError:
			pass
	dbcon.commit()
	# Sync label, icon, poster, alt_label for all non-custom items to match current defaults.
	# This ensures changes to defaults (e.g. new alt_labels, corrected icons) always propagate
	# to existing databases, not just new installs.
	_field_sync = {
		row[0]: (row[1], row[3], row[4], row[12])
		for defaults in MENU_DEFAULTS.values()
		for row in defaults
	}
	for item_id, (label, icon, poster, alt_label) in _field_sync.items():
		dbcon.execute(
			'UPDATE menu_items SET label=?, icon=?, poster=?, alt_label=? WHERE item_id=? AND is_custom=0',
			(label, icon, poster, alt_label, item_id)
		)
	dbcon.commit()
	dbcon.execute('''CREATE TABLE IF NOT EXISTS custom_folders (
		id          INTEGER PRIMARY KEY AUTOINCREMENT,
		folder_id   TEXT NOT NULL UNIQUE,
		folder_name TEXT NOT NULL,
		sort_order  INTEGER NOT NULL DEFAULT 0
	)''')
	dbcon.commit()
	cur = dbcon.cursor()
	cur.execute('SELECT COUNT(*) as cnt FROM menu_items WHERE menu_name=?', (menu_name,))
	cnt = cur.fetchone()['cnt']
	if cnt < len(MENU_DEFAULTS.get(menu_name, [])):
		_populate_defaults(dbcon, menu_name)
	# Insert items added after initial release for existing users (idempotent — OR IGNORE skips duplicates)
	_NEW_DEFAULT_ITEMS = [
		('mymovies',  'mymv_mdb_unfinished', '40686',  'mdblistMoviesUnfinished',   'mdblist.png', 'mdblist.png', 1, 1, 1, 99, 0, 'mdblist_with_indicators', 1, '35308'),
		('mytvshows', 'mytv_mdb_unfinished', '40686',  'mdblistEpisodesUnfinished', 'mdblist.png', 'mdblist.png', 1, 1, 1, 99, 0, 'mdblist_with_indicators', 1, '35308'),
	]
	for row in _NEW_DEFAULT_ITEMS:
		dbcon.execute(
			'INSERT OR IGNORE INTO menu_items '
			'(menu_name, item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom, condition_key, queue, alt_label) '
			'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', row
		)
	dbcon.commit()
	dbcon.close()


def get_menu_items(menu_name='root'):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT * FROM menu_items WHERE menu_name=? AND enabled=1 ORDER BY sort_order', (menu_name,))
	items = cur.fetchall()
	dbcon.close()
	return items


def get_all_menu_items(menu_name='root'):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT * FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	items = cur.fetchall()
	dbcon.close()
	return items


def toggle_item(menu_name, item_id):
	dbcon = _get_connection()
	dbcon.execute(
		'UPDATE menu_items SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE menu_name=? AND item_id=?',
		(menu_name, item_id)
	)
	dbcon.commit()
	dbcon.close()


def move_item_up(menu_name, item_id):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT id, item_id, sort_order FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	rows = cur.fetchall()
	for i, row in enumerate(rows):
		if row['item_id'] == item_id and i > 0:
			prev = rows[i - 1]
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (prev['sort_order'], row['id']))
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (row['sort_order'], prev['id']))
			dbcon.commit()
			break
	dbcon.close()


def move_item_down(menu_name, item_id):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT id, item_id, sort_order FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	rows = cur.fetchall()
	for i, row in enumerate(rows):
		if row['item_id'] == item_id and i < len(rows) - 1:
			nxt = rows[i + 1]
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (nxt['sort_order'], row['id']))
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (row['sort_order'], nxt['id']))
			dbcon.commit()
			break
	dbcon.close()


def reorder_enabled_items(menu_name, new_item_id_order):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute(
		'SELECT id, item_id, sort_order FROM menu_items WHERE menu_name=? AND enabled=1 ORDER BY sort_order',
		(menu_name,)
	)
	enabled_rows = cur.fetchall()
	old_sort_orders = [r['sort_order'] for r in enabled_rows]
	new_order_map = {item_id: old_sort_orders[i] for i, item_id in enumerate(new_item_id_order)}
	for row in enabled_rows:
		dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (new_order_map[row['item_id']], row['id']))
	dbcon.commit()
	dbcon.close()


def move_item_to(menu_name, item_id, target_index):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT id, item_id FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	rows = cur.fetchall()
	ids = [r['id'] for r in rows]
	moved_id = next((r['id'] for r in rows if r['item_id'] == item_id), None)
	if moved_id is None:
		dbcon.close()
		return
	ids.remove(moved_id)
	ids.insert(target_index, moved_id)
	for i, row_id in enumerate(ids):
		dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (i, row_id))
	dbcon.commit()
	dbcon.close()


def delete_item(menu_name, item_id):
	dbcon = _get_connection()
	dbcon.execute('DELETE FROM menu_items WHERE menu_name=? AND item_id=? AND is_custom=1', (menu_name, item_id))
	dbcon.commit()
	dbcon.close()


def add_custom_item(menu_name, label, action, icon, poster, is_folder=1, is_action=1):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT MAX(sort_order) as mx FROM menu_items WHERE menu_name=?', (menu_name,))
	row = cur.fetchone()
	next_order = (row['mx'] or 0) + 1
	import re
	base_id = 'custom_' + re.sub(r'[^a-z0-9]', '_', label.lower())[:30]
	item_id = base_id
	suffix = 1
	while True:
		cur.execute('SELECT id FROM menu_items WHERE menu_name=? AND item_id=?', (menu_name, item_id))
		if not cur.fetchone():
			break
		item_id = '%s_%d' % (base_id, suffix)
		suffix += 1
	dbcon.execute(
		'INSERT INTO menu_items (menu_name, item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom, condition_key, queue, alt_label) '
		'VALUES (?,?,?,?,?,?,?,?,1,?,1,NULL,0,NULL)',
		(menu_name, item_id, label, action, icon, poster, is_folder, is_action, next_order)
	)
	dbcon.commit()
	dbcon.close()


def update_custom_item(menu_name, item_id, **kwargs):
	allowed = {'label', 'action', 'icon', 'poster', 'is_folder', 'is_action'}
	updates = {k: v for k, v in kwargs.items() if k in allowed}
	if not updates:
		return
	set_clause = ', '.join('%s=?' % k for k in updates)
	values = list(updates.values()) + [menu_name, item_id]
	dbcon = _get_connection()
	dbcon.execute(
		'UPDATE menu_items SET %s WHERE menu_name=? AND item_id=? AND is_custom=1' % set_clause,
		values
	)
	dbcon.commit()
	dbcon.close()


def get_custom_folders():
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT folder_id, folder_name FROM custom_folders ORDER BY sort_order, id')
	rows = cur.fetchall()
	dbcon.close()
	return rows


def create_custom_folder(folder_name):
	import re
	base = 'cf_' + re.sub(r'[^a-z0-9]', '_', folder_name.lower())[:30]
	folder_id = base
	dbcon = _get_connection()
	suffix = 1
	while True:
		cur = dbcon.cursor()
		cur.execute('SELECT id FROM custom_folders WHERE folder_id=?', (folder_id,))
		if not cur.fetchone():
			break
		folder_id = '%s_%d' % (base, suffix)
		suffix += 1
	cur.execute('SELECT MAX(sort_order) as mx FROM custom_folders')
	row = cur.fetchone()
	next_order = (row['mx'] or 0) + 1
	dbcon.execute('INSERT INTO custom_folders (folder_id, folder_name, sort_order) VALUES (?,?,?)',
		(folder_id, folder_name, next_order))
	dbcon.commit()
	dbcon.close()
	return folder_id


def rename_custom_folder(folder_id, new_name):
	dbcon = _get_connection()
	dbcon.execute('UPDATE custom_folders SET folder_name=? WHERE folder_id=?', (new_name, folder_id))
	dbcon.commit()
	dbcon.close()


def delete_custom_folder(folder_id):
	dbcon = _get_connection()
	dbcon.execute('DELETE FROM menu_items WHERE menu_name=?', (folder_id,))
	dbcon.execute('DELETE FROM custom_folders WHERE folder_id=?', (folder_id,))
	dbcon.commit()
	dbcon.close()


def reset_to_defaults(menu_name='root'):
	dbcon = _get_connection()
	dbcon.execute('DELETE FROM menu_items WHERE menu_name=?', (menu_name,))
	dbcon.commit()
	_populate_defaults(dbcon, menu_name)
	dbcon.close()
