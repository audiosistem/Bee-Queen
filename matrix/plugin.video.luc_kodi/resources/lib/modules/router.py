"""
	luc_kodi Add-on
"""

from urllib.parse import quote_plus
from resources.lib.modules import control

def router(params):
	action = params.get('action')
	name = params.get('name')
	title = params.get('title')
	tvshowtitle = params.get('tvshowtitle')
	year = params.get('year')
	imdb = params.get('imdb')
	tmdb = params.get('tmdb')
	tvdb = params.get('tvdb')
	season = params.get('season')
	episode = params.get('episode')
	url = params.get('url')
	query = params.get('query')
	source = params.get('source')

	if action is None:
		from resources.lib.menus import navigator
		isUpdate = control.homeWindow.getProperty('luc_kodi.updated')
		if isUpdate == 'true':
			control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_cleanSettings)')
			control.homeWindow.clearProperty('luc_kodi.updated')
			from resources.lib.modules import changelog
			changelog.get('luc_kodi')
		# ── GUI resolution check — solo al abrir el plugin ───────────────
		try:
			from resources.lib.modules import gui_resolution
			gui_resolution.run()
		except Exception:
			pass
		# ─────────────────────────────────────────────────────────────────
		navigator.Navigator().root()
		return
	####################################################
	#---MOVIES
	####################################################
	# elif action and action.startswith('movies_'):
	elif action == 'movieNavigator':
		from resources.lib.modules import views
		if views.getViewStyle() == 'bingie':
			# Launch the section home in a SEPARATE script context via RunPlugin
			# so its blocking doModal() does NOT stall this GetDirectory handler.
			# Opening doModal() directly here would block endOfDirectory(), and
			# Kodi would think the directory is still loading ("updating in
			# progress") — freezing clicks and preventing re-entry. We then
			# close THIS directory immediately with succeeded=True so the parent
			# stays a valid, stable container (no refresh loop, no kick-out).
			control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=bingie_sectionMovies)')
			try:
				from sys import argv
				import xbmcplugin
				xbmcplugin.endOfDirectory(int(argv[1]), succeeded=True, updateListing=False, cacheToDisc=False)
			except Exception:
				pass
		else:
			from resources.lib.menus import navigator
			navigator.Navigator().movies()
	elif action == 'bingie_sectionMovies':
		from resources.lib.modules import bingie_section_launcher
		bingie_section_launcher.show_movies()
	elif action == 'movieliteNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().movies(lite=True)
	elif action == 'recoMovies':
		from resources.lib.menus import recommendations
		recommendations.Recommendations().movies()
	elif action == 'mymovieNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().mymovies()
	elif action == 'mymovieliteNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().mymovies(lite=True)
	elif action == 'movies':
		from resources.lib.menus import movies
		movies.Movies().get(url)
	elif action == 'bingie_gridMovies':
		from resources.lib.modules import bingie_launcher
		bingie_launcher.show_movies(url, params.get('title'), tmdb=(params.get('tmdb') == '1'))
	elif action == 'bingie_gridTVShows':
		from resources.lib.modules import bingie_launcher
		bingie_launcher.show_tvshows(url, params.get('title'), tmdb=(params.get('tmdb') == '1'))
	elif action == 'moviePage':
		from resources.lib.menus import movies
		movies.Movies().get(url)
	elif action == 'tmdbmovies':
		from resources.lib.menus import movies
		movies.Movies().getTMDb(url)
	elif action == 'tmdbmoviePage':
		from resources.lib.menus import movies
		movies.Movies().getTMDb(url)
	elif action == 'movieSearch':
		from resources.lib.menus import movies
		movies.Movies().search()
	elif action == 'movieSearchnew':
		from resources.lib.menus import movies
		movies.Movies().search_new()
	elif action == 'movieSearchterm':
		from resources.lib.menus import movies
		movies.Movies().search_term(name)
	elif action == 'moviePerson':
		from resources.lib.menus import movies
		movies.Movies().person()
	elif action == 'movieGenres':
		from resources.lib.menus import movies
		movies.Movies().genres(url)
	elif action == 'movieLanguages':
		from resources.lib.menus import movies
		movies.Movies().languages()
	elif action == 'movieCertificates':
		from resources.lib.menus import movies
		movies.Movies().certifications(url)
	elif action == 'movieYears':
		from resources.lib.menus import movies
		movies.Movies().years(url)
	elif action == 'movieProviders':
		from resources.lib.menus import movies
		movies.Movies().watchproviders()
	elif action == 'movieJustWatch':
		from resources.lib.menus import movies
		movies.Movies().getJustWatch(url)
	elif action == 'moviePersons':
		from resources.lib.menus import movies
		movies.Movies().persons(url)
	elif action == 'moviesUnfinished':
		from resources.lib.menus import movies
		movies.Movies().unfinished(url)
	elif action == 'moviesSimklProgress':
		from resources.lib.menus import movies
		movies.Movies().simkl_progress(url)
	elif action == 'movieUserlists':
		from resources.lib.menus import movies
		movies.Movies().userlists()
	elif action == 'movies_PublicLists':
		from resources.lib.menus import movies
		movies.Movies().getTraktPublicLists(url)
	elif action == 'movies_SearchLists':
		from resources.lib.menus import navigator
		navigator.Navigator().traktSearchLists(params.get('media_type'))
	elif action == 'movies_LikedLists':
		from resources.lib.menus import movies
		movies.Movies().traktLikedLists()
	####################################################
	#---MDBLIST MOVIES
	####################################################
	elif action == 'mdblist_movieNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().mdblist_movies()
	elif action == 'mdblist_movieWatchlist':
		from resources.lib.menus.mdblist_menus import MDBListMovies
		MDBListMovies().watchlist()
	elif action == 'mdblist_movieUserLists':
		from resources.lib.menus.mdblist_menus import MDBListMovies
		MDBListMovies().userLists()
	elif action == 'mdblist_movieTopLists':
		from resources.lib.menus.mdblist_menus import MDBListMovies
		MDBListMovies().topLists()
	elif action == 'mdblist_movieSearchLists':
		from resources.lib.menus.mdblist_menus import MDBListMovies
		MDBListMovies().searchLists()
	elif action == 'mdblist_movieListItems':
		from resources.lib.menus.mdblist_menus import MDBListMovies
		MDBListMovies().listItems(params.get('list_id'))
	####################################################
	#---MDBLIST CONTINUE WATCHING + TOP LISTS (MOVIES)
	####################################################
	elif action == 'mdblist_continueMovies':
		from resources.lib.menus.mdblist_menus import MDBListContinueMovies
		MDBListContinueMovies().get()
	elif action == 'movie_calendarNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().movie_calendar()
	elif action == 'tv_calendarNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().tv_calendar()
	elif action == 'mdblist_calendarMovies':
		from resources.lib.menus.mdblist_menus import MDBListCalendar
		MDBListCalendar().movies()
	elif action == 'mdblist_calendarUpcoming':
		from resources.lib.menus.mdblist_menus import MDBListCalendar
		MDBListCalendar().episodes('upcoming')
	elif action == 'mdblist_calendarRecent':
		from resources.lib.menus.mdblist_menus import MDBListCalendar
		MDBListCalendar().episodes('recent')
	elif action == 'mdblist_movieTopListsPublic':
		from resources.lib.menus.mdblist_menus import MDBListTopMovies
		MDBListTopMovies().topLists()
	elif action == 'mdblist_movieSearchListsPublic':
		from resources.lib.menus.mdblist_menus import MDBListTopMovies
		MDBListTopMovies().searchLists()
	elif action == 'mdblist_movieTopListItems':
		from resources.lib.menus.mdblist_menus import MDBListTopMovies
		MDBListTopMovies().listItems(params.get('list_id'))
	####################################################
	elif action == 'movies_traktUnfinishedManager':
		from resources.lib.menus import movies
		movies.Movies().unfinishedManager()
	elif action == 'movies_traktCollectionManager':
		from resources.lib.menus import movies
		movies.Movies().collectionManager()
	elif action == 'movies_traktWatchListManager':
		from resources.lib.menus import movies
		movies.Movies().watchlistManager()

	####################################################
	#---Collections
	####################################################
	elif action and action.startswith('collections'):
		if action == 'collections_Navigator':
			from resources.lib.menus import collections
			collections.Collections().collections_Navigator()
		elif action == 'collections_Boxset':
			from resources.lib.menus import collections
			collections.Collections().collections_Boxset()
		elif action == 'collections_Kids':
			from resources.lib.menus import collections
			collections.Collections().collections_Kids()
		elif action == 'collections_BoxsetKids':
			from resources.lib.menus import collections
			collections.Collections().collections_BoxsetKids()
		elif action == 'collections_Superhero':
			from resources.lib.menus import collections
			collections.Collections().collections_Superhero()
		elif action == 'collections_MartialArts':
			from resources.lib.menus import collections
			collections.Collections().collections_martial_arts()
		elif action == 'collections_MartialArtsActors':
			from resources.lib.menus import collections
			collections.Collections().collections_martial_arts_actors()
		elif action == 'collections_Search':
			from resources.lib.menus import collections
			collections.Collections().search()
		elif action == 'collections_Searchnew':
			from resources.lib.menus import collections
			collections.Collections().search_new()
		elif action == 'collections_Searchterm':
			from resources.lib.menus import collections
			collections.Collections().search_term(name)
		elif action == 'collections':
			from resources.lib.menus import collections
			collections.Collections().get(url)

	####################################################
	# TV Shows
	####################################################
	# if action and action.startswith('tv_'):
	elif action == 'tvNavigator':
		from resources.lib.modules import views
		if views.getViewStyle() == 'bingie':
			control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=bingie_sectionTVShows)')
			try:
				from sys import argv
				import xbmcplugin
				xbmcplugin.endOfDirectory(int(argv[1]), succeeded=True, updateListing=False, cacheToDisc=False)
			except Exception:
				pass
		else:
			from resources.lib.menus import navigator
			navigator.Navigator().tvshows()
	elif action == 'bingie_sectionTVShows':
		from resources.lib.modules import bingie_section_launcher
		bingie_section_launcher.show_tvshows()
	elif action == 'tvliteNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().tvshows(lite=True)
	elif action == 'recoTV':
		from resources.lib.menus import recommendations
		recommendations.Recommendations().tvshows()
	elif action == 'mytvNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().mytvshows()
	elif action == 'mytvliteNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().mytvshows(lite=True)
	elif action == 'tvshows':
		from resources.lib.menus import tvshows
		tvshows.TVshows().get(url)
	elif action == 'tvshowPage':
		from resources.lib.menus import tvshows
		tvshows.TVshows().get(url)
	elif action == 'tmdbTvshows':
		from resources.lib.menus import tvshows
		tvshows.TVshows().getTMDb(url)
	elif action == 'tmdbTvshowPage':
		from resources.lib.menus import tvshows
		tvshows.TVshows().getTMDb(url)
	elif action == 'tvmazeTvshows':
		from resources.lib.menus import tvshows
		tvshows.TVshows().getTVmaze(url)
	elif action == 'tvmazeTvshowPage':
		from resources.lib.menus import tvshows
		tvshows.TVshows().getTVmaze(url)
	elif action == 'tvSearch':
		from resources.lib.menus import tvshows
		tvshows.TVshows().search()
	elif action == 'tvSearchnew':
		from resources.lib.menus import tvshows
		tvshows.TVshows().search_new()
	elif action == 'tvSearchterm':
		from resources.lib.menus import tvshows
		tvshows.TVshows().search_term(name)
	####################################################
	#---AI SEARCH (Gemini)
	####################################################
	elif action == 'aiSearch':
		from resources.lib.modules import ai_search
		ai_search.history(forced_type=None)
	elif action == 'aiSearchMovies':
		from resources.lib.modules import ai_search
		ai_search.history(forced_type='movie')
	elif action == 'aiSearchTvshows':
		from resources.lib.modules import ai_search
		ai_search.history(forced_type='tvshow')
	elif action == 'aiSearchnew':
		from resources.lib.modules import ai_search
		ai_search.run()
	elif action == 'aiSearchnewMovies':
		from resources.lib.modules import ai_search
		ai_search.run_movies()
	elif action == 'aiSearchnewTvshows':
		from resources.lib.modules import ai_search
		ai_search.run_tvshows()
	elif action == 'aiSearchterm':
		from resources.lib.modules import ai_search
		ai_search.search_history_term(name, forced_type=None)
	elif action == 'aiSearchtermMovies':
		from resources.lib.modules import ai_search
		ai_search.search_history_term(name, forced_type='movie')
	elif action == 'aiSearchtermTvshows':
		from resources.lib.modules import ai_search
		ai_search.search_history_term(name, forced_type='tvshow')
	elif action == 'tvPerson':
		from resources.lib.menus import tvshows
		tvshows.TVshows().person()
	elif action == 'tvGenres':
		from resources.lib.menus import tvshows
		tvshows.TVshows().genres(url)
	elif action == 'tvNetworks':
		from resources.lib.menus import tvshows
		tvshows.TVshows().networks()
	elif action == 'tvLanguages':
		from resources.lib.menus import tvshows
		tvshows.TVshows().languages()
	elif action == 'tvCertificates':
		from resources.lib.menus import tvshows
		tvshows.TVshows().certifications()
	elif action == 'tvYears':
		from resources.lib.menus import tvshows
		tvshows.TVshows().years(url)
	elif action == 'tvPersons':
		from resources.lib.menus import tvshows
		tvshows.TVshows().persons(url)
	elif action == 'tvUserlists':
		from resources.lib.menus import tvshows
		tvshows.TVshows().userlists()
	elif action == 'tvOriginals':
		from resources.lib.menus import tvshows
		tvshows.TVshows().originals()
	elif action == 'tv_PublicLists':
		from resources.lib.menus import tvshows
		tvshows.TVshows().getTraktPublicLists(url)
	elif action == 'tv_SearchLists':
		from resources.lib.menus import navigator
		navigator.Navigator().traktSearchLists(params.get('media_type'))
	elif action == 'shows_LikedLists':
		from resources.lib.menus import tvshows
		tvshows.TVshows().traktLikedLists()
	####################################################
	#---MDBLIST TV SHOWS
	####################################################
	elif action == 'mdblist_tvNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().mdblist_tv()
	elif action == 'mdblist_showWatchlist':
		from resources.lib.menus.mdblist_menus import MDBListShows
		MDBListShows().watchlist()
	elif action == 'mdblist_showUserLists':
		from resources.lib.menus.mdblist_menus import MDBListShows
		MDBListShows().userLists()
	elif action == 'mdblist_showTopLists':
		from resources.lib.menus.mdblist_menus import MDBListShows
		MDBListShows().topLists()
	elif action == 'mdblist_showSearchLists':
		from resources.lib.menus.mdblist_menus import MDBListShows
		MDBListShows().searchLists()
	elif action == 'mdblist_showListItems':
		from resources.lib.menus.mdblist_menus import MDBListShows
		MDBListShows().listItems(params.get('list_id'))
	####################################################
	#---MDBLIST CONTINUE WATCHING + TOP LISTS (TV SHOWS)
	####################################################
	elif action == 'mdblist_continueEpisodes':
		from resources.lib.menus.mdblist_menus import MDBListContinueEpisodes
		MDBListContinueEpisodes().get()
	elif action == 'mdblist_showTopListsPublic':
		from resources.lib.menus.mdblist_menus import MDBListTopShows
		MDBListTopShows().topLists()
	elif action == 'mdblist_showSearchListsPublic':
		from resources.lib.menus.mdblist_menus import MDBListTopShows
		MDBListTopShows().searchLists()
	elif action == 'mdblist_showTopListItems':
		from resources.lib.menus.mdblist_menus import MDBListTopShows
		MDBListTopShows().listItems(params.get('list_id'))
	####################################################
	#---MDBLIST CONTEXT MENU
	####################################################
	elif action == 'mdblist_Manager':
		from resources.lib.modules import mdblist as mdblist_mod
		mdblist_mod.manager(name, imdb, params.get('media_type', 'movie'))
	####################################################
	#---MDBLIST BROWSE USER LISTS
	####################################################
	elif action == 'mdblist_browseUser':
		from resources.lib.menus.mdblist_menus import MDBListUserBrowse
		MDBListUserBrowse().browseUser()
	elif action == 'mdblist_importByUrl':
		from resources.lib.menus.mdblist_menus import MDBListUserBrowse
		MDBListUserBrowse().importByUrl(params.get('media_type', 'movie'))
	elif action == 'mdblist_userBrowseListItems':
		from resources.lib.menus.mdblist_menus import MDBListUserBrowse
		_lid = params.get('list_id', '')
		_mt  = 'show' if _lid.endswith('__show') else ('movie' if _lid.endswith('__movie') else 'both')
		_lid = _lid.replace('__show', '').replace('__movie', '')
		MDBListUserBrowse().listItems(_lid, params.get('username', ''), _mt)
	####################################################
	elif action == 'shows_traktHiddenManager':
		from resources.lib.menus import tvshows
		tvshows.TVshows().traktHiddenManager()
	elif action == 'shows_traktCollectionManager':
		from resources.lib.menus import tvshows
		tvshows.TVshows().collectionManager()
	elif action == 'shows_traktWatchListManager':
		from resources.lib.menus import tvshows
		tvshows.TVshows().watchlistManager()

	####################################################
	#---SEASONS
	####################################################
	elif action == 'seasons':
		from resources.lib.menus import seasons
		seasons.Seasons().get(tvshowtitle, year, imdb, tmdb, tvdb, params.get('art'))

	####################################################
	#---EPISODES
	####################################################
	elif action == 'episodes':
		from resources.lib.menus import episodes
		episodes.Episodes().get(tvshowtitle, year, imdb, tmdb, tvdb, params.get('meta'), season, episode)
	elif action == 'calendar':
		from resources.lib.menus import episodes
		episodes.Episodes().calendar(url)
	elif action == 'upcomingProgress':
		from resources.lib.menus import episodes
		episodes.Episodes().upcoming_progress(url)
	elif action == 'episodes_clrProgressCache':
		from resources.lib.menus import episodes
		episodes.Episodes().clr_progress_cache(url)
	elif action == 'calendars':
		from resources.lib.menus import episodes
		episodes.Episodes().calendars()
	elif action == 'episodesUnfinished':
		from resources.lib.menus import episodes
		episodes.Episodes().unfinished(url)
	elif action == 'episodesSimklProgress':
		from resources.lib.menus import episodes
		episodes.Episodes().progress_playback(url)
	elif action == 'episodes_traktUnfinishedManager':
		from resources.lib.menus import episodes
		episodes.Episodes().unfinishedManager()

	####################################################
	#---Premium Services
	####################################################
	elif action == 'premiumNavigator':
		from resources.lib.menus import navigator
		navigator.Navigator().premium_services()

	elif action and action.startswith('ad_'):
		if action == 'ad_ServiceNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().alldebrid_service()
		elif action == 'ad_AccountInfo':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().account_info_to_dialog()
		elif action == 'ad_Authorize':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().auth()
		elif action == 'ad_Deauthorize':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().revoke_auth()
		elif action == 'ad_Transfers':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().user_transfers_to_listItem()
		elif action == 'ad_CloudStorage':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().user_cloud_to_listItem()
		elif action == 'ad_BrowseUserCloud':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().browse_user_cloud(source)
		elif action == 'ad_DeleteTransfer':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().delete_transfer(params.get('id'), name, silent=False)
		elif action == 'ad_RestartTransfer':
			from resources.lib.debrid import alldebrid
			alldebrid.AllDebrid().restart_transfer(params.get('id'), name, silent=False)

	elif action and action.startswith('en_'):
		if action == 'en_ServiceNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().easynews_service()
		elif action == 'en_Search':
			from resources.lib.debrid import easynews
			easynews.EasyNews().search()
		elif action == 'en_Searchnew':
			from resources.lib.debrid import easynews
			easynews.EasyNews().search_new()
		elif action == 'en_searchResults':
			from resources.lib.debrid import easynews
			easynews.EasyNews().query_results_to_dialog(query)
		elif action == 'en_resolve_forPlayback':
			from resources.lib.debrid import easynews
			easynews.EasyNews().resolve_forPlayback(url)
		elif action == 'en_AccountInfo':
			from resources.lib.debrid import easynews
			easynews.EasyNews().account_info_to_dialog()

	elif action and action.startswith('ed_'):
		if action == 'ed_AccountInfo':
			from resources.lib.debrid import easydebrid
			easydebrid.EasyDebrid().account_info_to_dialog()
		elif action == 'ed_Authorize':
			from resources.lib.debrid import easydebrid
			easydebrid.EasyDebrid().auth()
		elif action == 'ed_Deauthorize':
			from resources.lib.debrid import easydebrid
			easydebrid.EasyDebrid().remove_auth()

	elif action and action.startswith('oc_'):
		if action == 'oc_ServiceNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().offcloud_service()
		elif action == 'oc_AccountInfo':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().account_info_to_dialog()
		elif action == 'oc_Authorize':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().auth()
		elif action == 'oc_Deauthorize':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().remove_auth()
		elif action == 'oc_CloudStorage':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().user_cloud_to_listItem()
		elif action == 'oc_BrowseUserTorrents':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().browse_user_torrents(params.get('id'))
		elif action == 'oc_DeleteUserTorrent':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().delete_user_torrent(params.get('id'), name)
		elif action == 'oc_UserCloudClear':
			from resources.lib.debrid import offcloud
			offcloud.Offcloud().user_cloud_clear()

	elif action and action.startswith('pm_'):
		if action == 'pm_ServiceNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().premiumize_service()
		elif action == 'pm_AccountInfo':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().account_info_to_dialog()
		elif action == 'pm_Authorize':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().auth()
		elif action == 'pm_Deauthorize':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().remove_auth()
		elif action == 'pm_MyFiles':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().my_files_to_listItem(params.get('id'), name)
		elif action == 'pm_Transfers':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().user_transfers_to_listItem()
		elif action == 'pm_Rename':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().rename(params.get('type'), params.get('id'), name)
		elif action == 'pm_Delete':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().delete(params.get('type'), params.get('id'), name)
		elif action == 'pm_DeleteTransfer':
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().delete_transfer(params.get('id'), name)
		elif action == 'pm_ClearFinishedTransfers': # disabled for now till PM fixes
			from resources.lib.debrid import premiumize
			premiumize.Premiumize().clear_finished_transfers()

	elif action and action.startswith('rd_'):
		if action == 'rd_ServiceNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().realdebrid_service()
		elif action == 'rd_AccountInfo':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().account_info_to_dialog()
		elif action == 'rd_Authorize':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().auth()
		elif action == 'rd_Deauthorize':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().reset_authorization()
		elif action == 'rd_UserTorrentsToListItem':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().user_torrents_to_listItem()
		elif action == 'rd_MyDownloads':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().my_downloads_to_listItem(int(query))
		elif action == 'rd_BrowseUserTorrents':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().browse_user_torrents(params.get('id'))
		elif action == 'rd_DeleteUserTorrent':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().delete_user_torrent(params.get('id'), name)
		elif action == 'rd_DeleteDownload':
			from resources.lib.debrid import realdebrid
			realdebrid.RealDebrid().delete_download(params.get('id'), name)

	elif action and action.startswith('tb_'):
		if action == 'tb_ServiceNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().torbox_service()
		elif action == 'tb_AccountInfo':
			from resources.lib.debrid import torbox
			torbox.TorBox().account_info_to_dialog()
		elif action == 'tb_Authorize':
			from resources.lib.debrid import torbox
			torbox.TorBox().auth()
		elif action == 'tb_Deauthorize':
			from resources.lib.debrid import torbox
			torbox.TorBox().remove_auth()
		elif action == 'tb_CloudStorage':
			from resources.lib.debrid import torbox
			torbox.TorBox().user_cloud_to_listItem()
		elif action == 'tb_BrowseUserTorrents':
			from resources.lib.debrid import torbox
			torbox.TorBox().browse_user_torrents(params.get('id'), params.get('mediatype'))
		elif action == 'tb_DeleteUserTorrent':
			from resources.lib.debrid import torbox
			torbox.TorBox().delete_user_torrent(params.get('id'), params.get('mediatype'), name)

	elif action and action.startswith('trakt_'):
		if action == 'trakt_Authorize':
			from resources.lib.modules import trakt
			trakt.auth()
		elif action == 'trakt_Deauthorize':
			from resources.lib.modules import trakt
			trakt.deauth()
		elif action == 'trakt_AccountInfo':
			from resources.lib.modules import trakt
			trakt.account_info_to_dialog()
	elif action and action.startswith('simkl_'):
		if action == 'simkl_Authorize':
			from resources.lib.modules import simkl
			simkl.auth()
		elif action == 'simkl_Deauthorize':
			from resources.lib.modules import simkl
			simkl.deauth()
		elif action == 'simkl_AccountInfo':
			from resources.lib.modules import simkl
			simkl.account_info_to_dialog()
		elif action == 'simkl_ForceSync':
			from resources.lib.modules import simkl
			simkl.force_simklSync()
	elif action == 'mdblist_Authorize':
		from resources.lib.modules import mdblist
		mdblist.auth()
	elif action == 'mdblist_Deauthorize':
		from resources.lib.modules import mdblist
		mdblist.deauth()
	elif action == 'mdblist_AccountInfo':
		from resources.lib.modules import mdblist
		mdblist.account_info_to_dialog()
	elif action and action.startswith('tmdb_'):
		if action == 'tmdb_Auth':
			from resources.lib.indexers import tmdb
			tmdb.Auth().create_session_id()
	elif action and action.startswith('undesirables'):
		if action == 'undesirablesInput':
			from resources.lib.database import undesirables_cache
			undesirables_cache.undesirablesInput()
		elif action == 'undesirablesUserRemove':
			from resources.lib.database import undesirables_cache
			undesirables_cache.undesirablesUserRemove()

	####################################################
	#---Anime
	####################################################
	elif action and action.startswith('anime_'):
		if action == 'anime_Navigator':
			from resources.lib.menus import navigator
			navigator.Navigator().anime()
		elif action == 'anime_Movies':
			from resources.lib.menus import movies
			movies.Movies().get(url)
		elif action == 'anime_TVshows':
			from resources.lib.menus import tvshows
			tvshows.TVshows().get(url)

	####################################################
	#---YouTube
	####################################################
	elif action == 'youtube':
		from resources.lib.menus import youtube
		id = params.get('id')
		if id is None: youtube.youtube().root(action)
		else: youtube.youtube().get(action, id)
	elif action == 'sectionItem':
		pass # Placeholder. This is a non-clickable menu item for notes, etc.

	####################################################
	#---Download
	####################################################
	elif action and action.startswith('download'):
		if action == 'downloadNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().downloads()
		elif action == 'download':
			caller = params.get('caller')
			image = params.get('image')
			if caller == 'sources': # future, move to downloader module for pack support
				control.busy()
				try:
					from json import loads as jsloads
					from resources.lib.modules import sources
					from resources.lib.modules import downloader
					downloader.download(name, image, sources.Sources().sourcesResolve(jsloads(source)[0]), title)
				except:
					import traceback
					traceback.print_exc()
			if caller == 'alldebrid':
				control.busy()
				try:
					from resources.lib.modules import downloader
					from resources.lib.debrid import alldebrid
					downloader.download(name, image, alldebrid.AllDebrid().unrestrict_link(url.replace(' ', '%20')))
				except:
					import traceback
					traceback.print_exc()
			if caller == 'easydebrid':
				control.busy()
				try:
					from resources.lib.modules import downloader
					from resources.lib.debrid import easydebrid
					downloader.download(name, image, easydebrid.EasyDebrid().unrestrict_link(url.replace(' ', '%20')))
				except:
					import traceback
					traceback.print_exc()
			if caller == 'easynews':
				control.busy()
				try:
					from resources.lib.modules import downloader
					# v1.0.53: la URL llega limpia; la cabecera Basic se adjunta aqui
					# para que las credenciales no viajen en el menu contextual.
					from resources.lib.jacksparrow.sourcesdir.torrents import easynews as _en_mod
					_dl = _en_mod.source().resolve(url) or url
					downloader.download(name, image, _dl)
				except:
					import traceback
					traceback.print_exc()
			if caller == 'offcloud':
				control.busy()
				try:
					from resources.lib.modules import downloader
					downloader.download(name, image, url.replace(' ', '%20'))
				except:
					import traceback
					traceback.print_exc()
			if caller == 'premiumize':
				control.busy()
				try:
					from resources.lib.modules import downloader
					from resources.lib.debrid import premiumize
					downloader.download(name, image, premiumize.Premiumize().add_headers_to_url(url.replace(' ', '%20')))
				except:
					import traceback
					traceback.print_exc()
			if caller == 'realdebrid':
				control.busy()
				try:
					from resources.lib.modules import downloader
					from resources.lib.debrid import realdebrid
					if params.get('type') == 'unrestrict':
						downloader.download(name, image, realdebrid.RealDebrid().unrestrict_link(url.replace(' ', '%20')))
					else:
						downloader.download(name, image, url.replace(' ', '%20'))
				except:
					import traceback
					traceback.print_exc()
			if caller == 'torbox':
				control.busy()
				try:
					from resources.lib.modules import downloader
					from resources.lib.debrid import torbox
					if params.get('mediatype') == 'usenet': url = torbox.TorBox().unrestrict_usenet(url.replace(' ', '%20'))
					else: url = torbox.TorBox().unrestrict_link(url.replace(' ', '%20'))
					downloader.download(name, image, torbox.TorBox().add_headers_to_url(url))
				except:
					import traceback
					traceback.print_exc()

	####################################################
	#---Tools
	####################################################
	elif action and action.startswith('tools_'):
		if action == 'tools_ShowNews':
			from resources.lib.modules import newsinfo
			newsinfo.news_local()
		elif action == 'tools_ShowChangelog':
			from resources.lib.modules import changelog
			changelog.get(name)
		elif action == 'tools_ShowHelp':
			from resources.lib.modules import help
			help.get(name)
		elif action == 'tools_LanguageInvoker':
			from resources.lib.modules import language_invoker
			language_invoker.set_reuselanguageinvoker()
		elif action == 'tools_toolNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().tools()
		elif action == 'tools_traktToolsNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().traktTools()
		elif action == 'tools_searchNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().search()
		elif action == 'tools_viewsNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().views()
		elif action == 'tools_setAddonView':
			from resources.lib.menus import navigator
			navigator.Navigator().setAddonView()
		elif action == 'tools_loggingNavigator':
			from resources.lib.menus import navigator
			navigator.Navigator().loggingNavigator()
		elif action == 'tools_addView':
			from resources.lib.modules import views
			views.addView(params.get('content'))
		elif action == 'tools_resetViewTypes':
			from resources.lib.modules import views
			views.clearViews()
		elif action == 'tools_updateCatalog':
			from resources.lib.modules import catalog_updater
			# v1.0.54: el botón manual es el refresco COMPLETO garantizado
			# (fresh_meta re-pide el detalle de página 1 y renueva el sello
			# meta_hours; force_refresh re-lee las listas). El arranque diario
			# ya no hace esto: usa el ciclo ligero.
			catalog_updater.precache_tmdb_catalog(pages=5, silent=False, force_refresh=True, fresh_meta=True)
			control.trigger_widget_refresh()
		elif action == 'tools_personalRankerStats':
			from resources.lib.modules import personal_ranker_ui
			personal_ranker_ui.show_stats()
		elif action == 'tools_personalRankerReset':
			from resources.lib.modules import personal_ranker_ui
			personal_ranker_ui.reset_with_confirm()
		elif action == 'tools_cleanSettings':
			from resources.lib.modules import clean_settings
			clean_settings.clean_settings()
		elif action == 'tools_sootioWizard':
			from resources.lib.modules import sootio_wizard
			sootio_wizard.run()
		elif action == 'tools_meteorWizard':
			from resources.lib.modules import meteor_wizard
			meteor_wizard.run()
		elif action == 'tools_torzWizard':
			from resources.lib.modules import torz_wizard
			torz_wizard.run()
		elif action == 'tools_torzDetect':
			from resources.lib.modules import torz_wizard
			torz_wizard.detect()
		elif action == 'tools_newznabWizard':
			from resources.lib.modules import newznab_wizard
			newznab_wizard.run()
		elif action == 'tools_newznabTest':
			from resources.lib.modules import newznab_wizard
			newznab_wizard.test()
		elif action == 'tools_cometWizard':
			from resources.lib.modules import comet_wizard
			comet_wizard.run()
		elif action == 'tools_badgesWizard':
			from resources.lib.modules import badges_wizard
			badges_wizard.run()
		elif action == 'tools_badgesReset':
			from resources.lib.modules import badges_wizard
			badges_wizard.run_reset()
		elif action == 'tools_mdblistWizard':
			from resources.lib.modules import mdblist_wizard
			mdblist_wizard.run()
		elif action == 'tools_cometDetect':
			from resources.lib.modules import comet_wizard
			comet_wizard.detect()
		elif action == 'tools_openSubsTest':
			from resources.lib.modules import opensubs
			opensubs.Opensubs().getAccountStatus()
		elif action == 'tools_openSubsRevoke':
			from resources.lib.modules import opensubs
			opensubs.Opensubs().revokeAccess()
		elif action == 'tools_subsList':
			from resources.lib.modules import sources
			sources.Sources().getSubsList()
		elif action == 'tools_openSettings':
			control.openSettings(query)
		elif action == 'tools_contextluc_kodiSettings':
			control.openSettings('0.0', 'context.luc_kodi')
			control.trigger_widget_refresh()
		elif action == 'tools_jacksparrowscrapersSettings':
			control.openSettings('5.0')
		elif action == 'tools_traktManager':
			from resources.lib.modules import trakt
			watched = (params.get('watched') == 'True') if params.get('watched') else None
			unfinished = (params.get('unfinished') == 'True') if params.get('unfinished') else False
			trakt.manager(name, imdb, tvdb, season, episode, watched=watched, unfinished=unfinished)
		elif action == 'tools_likeList':
			from resources.lib.modules import trakt
			trakt.like_list(params.get('list_owner'), params.get('list_name'), params.get('list_id'))
		elif action == 'tools_unlikeList':
			from resources.lib.modules import trakt
			trakt.unlike_list(params.get('list_owner'), params.get('list_name'), params.get('list_id'))
		elif action == 'tools_forceTraktSync':
			from resources.lib.modules import trakt
			trakt.force_traktSync()
		elif action == 'tools_clearLogFile':
			from resources.lib.modules import log_utils
			cleared = log_utils.clear_logFile()
			if cleared == 'canceled': return
			elif cleared: control.notification(message='luc_kodi Log File Successfully Cleared')
			else: control.notification(message='Error clearing luc_kodi Log File, see kodi.log for more info')
		elif action == 'tools_viewLogFile':
			from resources.lib.modules import log_utils
			log_utils.view_LogFile(name)
		elif action == 'tools_uploadLogFile':
			from resources.lib.modules import log_utils
			log_utils.upload_LogFile(name)
		elif action == 'tools_debridHub':
			from resources.lib.modules import debrid_hub
			debrid_hub.open_hub()
		elif action == 'tools_traktLikedListManager':
			from resources.lib.menus import movies
			movies.Movies().likedListsManager()

	elif action == 'debridHub_Service':
		from resources.lib.modules import debrid_hub
		debrid_hub.service_menu(params.get('service') or '')

	####################################################
	#---Play
	####################################################
	elif action and action.startswith('play_'):
		if action == 'play_Item':
			from resources.lib.modules import sources
			# Bingie UI launches playback via RunPlugin from inside a custom window,
			# so argv[1] is an invalid handle and setResolvedUrl() is a no-op.
			# Flag it so player.play_source() uses control.player.play() instead.
			if params.get('bingie') == '1':
				from resources.lib.modules.control import homeWindow as _hw
				_hw.setProperty('luc_kodi.bingie_direct', 'true')
			sources.Sources(params.get('all_providers')).play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, params.get('premiered'), params.get('meta'), params.get('select'), params.get('rescrape'))
		elif action == "play_preScrapeNext":
			from resources.lib.modules.player import PlayNext
			PlayNext().prescrapeNext()
		elif action == "play_nextWindowXML":
			from resources.lib.modules.player import PlayNext
			play_next = PlayNext()
			play_next.display_xml()
			del play_next
		elif action == 'play_All': # context menu works same as "Play from Here"
			control.player2().play(control.playlist) 
		elif action == 'play_URL':
			caller = params.get('caller')
			if caller == 'realdebrid':
				from resources.lib.debrid import realdebrid
				if params.get('type') == 'unrestrict': control.player.play(realdebrid.RealDebrid().unrestrict_link(url.replace(' ', '%20')))
				else: control.player.play(url.replace(' ', '%20'))
			elif caller == 'alldebrid':
				from resources.lib.debrid import alldebrid
				if params.get('type') == 'unrestrict': control.player.play(alldebrid.AllDebrid().unrestrict_link(url.replace(' ', '%20')))
				else: control.player.play(url.replace(' ', '%20'))
			elif caller == 'torbox':
				from resources.lib.debrid import torbox
				if params.get('type') == 'unrestrict':
					if params.get('mediatype') == 'usenet': control.player.play(torbox.TorBox().unrestrict_usenet(url.replace(' ', '%20')))
					else: control.player.play(torbox.TorBox().unrestrict_link(url.replace(' ', '%20')))
				else: control.player.play(url.replace(' ', '%20'))
			else:
				control.player.play(url.replace(' ', '%20'))
		elif action == 'play_EpisodesList': # global context option
			from json import dumps as jsdumps
			from resources.lib.menus import episodes
			items = episodes.Episodes().get(tvshowtitle, year, imdb, tmdb, tvdb, params.get('meta'), season, episode, create_directory=False)
			control.playlist.clear()
			for i in items:
				title = i['title']
				systitle = quote_plus(title)
				year = i['year']
				imdb = i['imdb']
				tmdb = i['tmdb']
				tvdb = i['tvdb']
				season = i['season']
				episode = i['episode']
				tvshowtitle = i['tvshowtitle']
				systvshowtitle = quote_plus(tvshowtitle)
				premiered = i['premiered']
				sysmeta = quote_plus(jsdumps(i))
				url = 'plugin://plugin.video.luc_kodi/?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s&tvshowtitle=%s&premiered=%s&meta=%s&select=1' % (
										systitle, year, imdb, tmdb, tvdb, season, episode, systvshowtitle, premiered, sysmeta)
				item = control.item(label=title, offscreen=True)
				control.playlist.add(url=url, listitem=item)
			control.player2().play(control.playlist)

		elif action == 'play_Trailer':
			from resources.lib.modules import trailer
			windowedtrailer = params.get('windowedtrailer')
			windowedtrailer = int(windowedtrailer) if windowedtrailer in ("0","1") else 0
			trailer.Trailer().play(params.get('type'), name, year, url, imdb, windowedtrailer, tmdb=params.get('tmdb', ''))
		elif action == 'play_Random':
			rtype = params.get('rtype')
			if rtype == 'movie':
				from resources.lib.menus import movies
				rlist = movies.Movies().get(url, create_directory=False)
				r = 'plugin://plugin.video.luc_kodi/?action=play_Item'
			elif rtype == 'episode':
				from resources.lib.menus import episodes
				rlist = episodes.Episodes().get(tvshowtitle, year, imdb, tmdb, tvdb, params.get('meta'), season, create_directory=False)
				r = 'plugin://plugin.video.luc_kodi/?action=play_Item'
			elif rtype == 'season':
				from resources.lib.menus import seasons
				rlist = seasons.Seasons().get(tvshowtitle, year, imdb, tmdb, tvdb, params.get('art'), create_directory=False)
				r = 'plugin://plugin.video.luc_kodi/?action=play_Random&rtype=episode'
			elif rtype == 'show':
				from resources.lib.menus import tvshows
				rlist = tvshows.TVshows().get(url, create_directory=False)
				r = 'plugin://plugin.video.luc_kodi/?action=play_Random&rtype=season'
			from random import randint
			from json import dumps as jsdumps
			try:
				rand = randint(1,len(rlist))-1
				for p in ('title', 'year', 'imdb', 'tmdb', 'tvdb', 'season', 'episode', 'tvshowtitle', 'premiered', 'select'):
					if rtype == "show" and p == "tvshowtitle":
						try: r += '&' + p + '=' + quote_plus(rlist[rand]['title'])
						except: pass
					else:
						try: r += '&' + p + '=' + quote_plus(str(rlist[rand][p]))
						except: pass
				try: r += '&meta=' + quote_plus(jsdumps(rlist[rand]))
				except: r += '&meta=' + quote_plus("{}")
				if rtype == "movie":
					try: control.notification(title=32536, message='%s (%s)' % (rlist[rand]['title'], rlist[rand]['year']))
					except: pass
				elif rtype == "episode":
					try: control.notification(title=32536, message='%s - %01dx%02d - %s' % (rlist[rand]['tvshowtitle'], int(rlist[rand]['season']), int(rlist[rand]['episode']), rlist[rand]['title']))
					except: pass
				control.execute('RunPlugin(%s)' % r)
			except: control.notification(message=32537)

	elif action == 'play': # for support of old style .strm library files
		from resources.lib.modules import sources
		sources.Sources(params.get('all_providers')).play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, params.get('premiered'), params.get('meta'), params.get('select'), params.get('rescrape'))

	####################################################
	#---Playlist
	####################################################
	elif action and action.startswith('playlist_'):
		if action == 'playlist_Manager':
			from resources.lib.modules import playlist
			playlist.playlistManager(name, url, params.get('meta'), params.get('art'))
		elif action == 'playlist_Show':
			from resources.lib.modules import playlist
			playlist.playlistShow()
		elif action == 'playlist_Clear':
			from resources.lib.modules import playlist
			playlist.playlistClear()
		elif action == 'playlist_QueueItem':
			control.queueItem()
			if name is None: control.notification(title=35515, message=35519)
			else: control.notification(title=name, message=35519)

	####################################################
	#---Playcount
	####################################################
	elif action and action.startswith('playcount_'):
		if action == 'playcount_Movie':
			from resources.lib.modules import playcount
			playcount.movies(name, imdb, query)
		elif action == 'playcount_Episode':
			from resources.lib.modules import playcount
			playcount.episodes(name, imdb, tvdb, season, episode, query)
		elif action == 'playcount_TVShow':
			from resources.lib.modules import playcount
			playcount.tvshows(name, imdb, tvdb, season, query)

	####################################################
	#---Recommendation Feedback
	####################################################
	elif action == 'reco_feedback':
		from resources.lib.database import reco_feedback as rfb
		import xbmc as _xbmc
		signal     = int(params.get('signal') or '0')
		media_type = params.get('media_type') or 'movie'
		genres     = params.get('genres') or ''
		if signal and tmdb:
			rfb.set_signal(tmdb, title or name or '', signal, media_type, genres)
			if signal == 1:
				msg = 'Saved - you will see more like this'
			else:
				msg = 'Hidden from recommendations'
			control.notification(title='For You', message=msg, time=3000)
			control.trigger_widget_refresh()
			# Refresh the open container so the item disappears / re-scores instantly.
			# A short sleep ensures the DB write is flushed before the rebuild reads it.
			_xbmc.sleep(250)
			control.refresh()

	####################################################
	#---Source Actions
	####################################################
	elif action == 'alterSources':
		from resources.lib.modules import sources
		sources.Sources().alterSources(url, params.get('meta'))
	elif action == 'showDebridPack':
		from resources.lib.modules.sources import Sources
		Sources().debridPackDialog(params.get('caller'), name, url, source)
	elif action == 'sourceInfo':
		from resources.lib.modules.sources import Sources
		Sources().sourceInfo(source)
	elif action == 'cacheTorrent':
		caller = params.get('caller')
		pack = True if params.get('type') == 'pack' else False
		if caller == 'RD':
			from resources.lib.debrid.realdebrid import RealDebrid as debrid_function
		elif caller == 'PM':
			from resources.lib.debrid.premiumize import Premiumize as debrid_function
		elif caller == 'AD':
			from resources.lib.debrid.alldebrid import AllDebrid as debrid_function
		elif caller == 'OC':
			from resources.lib.debrid.offcloud import Offcloud as debrid_function
		elif caller == 'ED':
			from resources.lib.debrid.easydebrid import EasyDebrid as debrid_function
		elif caller == 'TB':
			from resources.lib.debrid.torbox import TorBox as debrid_function
		success = debrid_function().add_uncached_torrent(url, pack=pack)
		if success:
			from resources.lib.modules import sources
			sources.Sources().playItem(title, params.get('items'), source, params.get('meta'))

	elif action == 'rescrapeMenu':
		from resources.lib.modules import sources
		premiered = params.get('premiered')
		meta = params.get('meta')
		highlight_color = control.getHighlightColor()
		items = [
			control.lang(32207),
			control.lang(32208),
			control.lang(32209) % highlight_color, 
			control.lang(32210) % highlight_color, 
			control.lang(32216) % highlight_color, 
			control.lang(32217) % highlight_color,
			control.lang(32232) % (highlight_color, highlight_color)]
		select = control.selectDialog(items, heading=control.addonInfo('name') + ' - ' + 'Rescrape Options Menu')
		if select == -1: return control.closeAll()
		if select >= 0:
			if select == 0: sources.Sources().play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='1', rescrape='true')
			elif select == 1: sources.Sources().play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='0', rescrape='true')
			elif select == 2: sources.Sources(all_providers='true').play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='1', rescrape='true')
			elif select == 3: sources.Sources(all_providers='true').play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='0', rescrape='true')
			elif select == 4: sources.Sources(custom_query='true').play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='0', rescrape='true')
			elif select == 5: sources.Sources(all_providers='true', custom_query='true').play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='0', rescrape='true')
			elif select == 6: sources.Sources(all_providers='true', filterless_scrape='true').play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select='0', rescrape='true')

	####################################################
	#---Library Actions
	####################################################
	elif action and action.startswith('library_'):
		if action == 'library_Navigator':
			from resources.lib.menus import navigator
			navigator.Navigator().library()
		elif action == 'library_movieToLibrary':
			from resources.lib.modules import library
			library.libmovies().add(name, title, year, imdb, tmdb)
		elif action == 'library_moviesToLibrary':
			from resources.lib.modules import library
			library.libmovies().range(url, name)
		elif action == 'library_moviesListToLibrary':
			from resources.lib.menus import movies
			movies.Movies().moviesListToLibrary(url)
		elif action == 'library_moviesToLibrarySilent':
			from resources.lib.modules import library
			library.libmovies().silent(url)
		elif action == 'library_tvshowToLibrary':
			from resources.lib.modules import library
			library.libtvshows().add(tvshowtitle, year, imdb, tmdb, tvdb)
		elif action == 'library_tvshowsToLibrary':
			from resources.lib.modules import library
			library.libtvshows().range(url, name)
		elif action == 'library_tvshowsListToLibrary':
			from resources.lib.menus import tvshows
			tvshows.TVshows().tvshowsListToLibrary(url)
		elif action == 'library_tvshowsToLibrarySilent':
			from resources.lib.modules import library
			library.libtvshows().silent(url)
		elif action == 'library_update':
			control.notification(message=32085)
			from resources.lib.modules import library
			library.libepisodes().update()
			library.libmovies().list_update()
			library.libtvshows().list_update()
			while True:
				if control.condVisibility('Library.IsScanningVideo'):
					control.sleep(3000)
					continue
				else: break
			control.sleep(1000)
			control.notification(message=32086)
		elif action == 'library_clean':
			from resources.lib.modules import library
			library.lib_tools().clean()
		elif action == 'library_setup':
			from resources.lib.modules import library
			library.lib_tools().total_setup()

	####################################################
	#---Cache
	####################################################
	elif action and action.startswith('cache_'):
		if action == 'cache_Navigator':
			from resources.lib.menus import navigator
			navigator.Navigator().cf()
		elif action == 'cache_clearAll':
			from resources.lib.menus import navigator
			navigator.Navigator().clearCacheAll()
		elif action == 'cache_clearSources':
			from resources.lib.menus import navigator
			navigator.Navigator().clearCacheProviders()
		elif action == 'cache_clearMeta':
			from resources.lib.menus import navigator
			navigator.Navigator().clearCacheMeta()
		elif action == 'cache_clearCache':
			from resources.lib.menus import navigator
			navigator.Navigator().clearCache()
		elif action == 'cache_clearMetaAndCache':
			from resources.lib.menus import navigator
			navigator.Navigator().clearMetaAndCache()
		elif action == 'cache_clearSearch':
			from resources.lib.menus import navigator
			navigator.Navigator().clearCacheSearch() 
		elif action == 'cache_clearSearchPhrase':
			from resources.lib.menus import navigator
			navigator.Navigator().clearCacheSearchPhrase(source, name)
		elif action == 'cache_clearBookmarks':
			from resources.lib.menus import navigator
			navigator.Navigator().clearBookmarks()
		elif action == 'cache_clearRecoFeedback':
			from resources.lib.menus import navigator
			navigator.Navigator().clearRecoFeedback()
		elif action == 'cache_clearBookmark':
			from resources.lib.menus import navigator
			navigator.Navigator().clearBookmark(name, year)
		elif action == 'cache_clearKodiBookmark': # context.luc_kodi action call only
			from resources.lib.database import cache
			cache.clear_local_bookmark(url)
		elif action == 'tools_resetMetadataKeys':
			control.setSetting('tmdb.api.key', '')
			control.setSetting('fanart_tv.api_key', '')
			control.homeWindow.clearProperty('luc_kodi_settings')
			control.notification(message='TMDb and Fanart keys reset to plugin defaults')