# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from sys import exit as sysexit
from urllib.parse import quote_plus
from resources.lib.modules import control
from resources.lib.modules.trakt import getTraktCredentialsInfo, getTraktIndicatorsInfo
from resources.lib.modules.mdblist import getMDBListCredentialsInfo

getLS = control.lang
getSetting = control.setting
getMenuEnabled = control.getMenuEnabled
KODI_VERSION = control.getKodiVersion()


class Navigator:
	def __init__(self):
		self.artPath = control.artPath()
		self.iconLogos = getSetting('icon.logos') != 'Traditional'
		self.indexLabels = getSetting('index.labels') == 'true'
		self.traktCredentials = getTraktCredentialsInfo()
		self.traktIndicators = getTraktIndicatorsInfo()
		self.imdbCredentials = getSetting('imdb.user') != ''
		self.tmdbSessionID = getSetting('tmdb.session_id') != ''
		self.highlight_color = control.getHighlightColor()
		self.mdblistCredentials = getMDBListCredentialsInfo()

	def root(self):
		self.addDirectoryItem(33046, 'movieNavigator', 'movies.png', 'DefaultMovies.png')
		self.addDirectoryItem(33047, 'tvNavigator', 'tvshows.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.anime'): self.addDirectoryItem('Anime', 'anime_Navigator', 'boxsets.png', 'DefaultFolder.png')
		if getMenuEnabled('mylists.widget'):
			self.addDirectoryItem(32003, 'mymovieNavigator', 'mymovies.png', 'DefaultVideoPlaylists.png')
			self.addDirectoryItem(32004, 'mytvNavigator', 'mytvshows.png', 'DefaultVideoPlaylists.png')
		if getMenuEnabled('navi.youtube'): self.addDirectoryItem('You Tube Videos', 'youtube', 'youtube.png', 'youtube.png')
		self.addDirectoryItem(32010, 'tools_searchNavigator', 'search.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem(32008, 'tools_toolNavigator', 'tools.png', 'tools.png')
		downloads = True if getSetting('downloads') == 'true' and (len(control.listDir(getSetting('movie.download.path'))[0]) > 0 or len(control.listDir(getSetting('tv.download.path'))[0]) > 0) else False
		if downloads: self.addDirectoryItem(32009, 'downloadNavigator', 'downloads.png', 'DefaultFolder.png')
		if getMenuEnabled('navi.prem.services'): self.addDirectoryItem(40000, 'premiumNavigator', 'premium.png', 'DefaultFolder.png')
		if getMenuEnabled('navi.news'): self.addDirectoryItem(32013, 'tools_ShowNews', 'years.png', 'DefaultAddonHelper.png', isFolder=False)
		if getMenuEnabled('navi.changelog'): self.addDirectoryItem(32014, 'tools_ShowChangelog&name=luc_kodi', 'userlists.png', 'DefaultAddonHelper.png', isFolder=False)
		self.endDirectory(is_root=True)

	def movies(self, lite=False):
		# For You (AI recommendations)
		self.addDirectoryItem(40110 if self.indexLabels else 40110, 'recoMovies', 'foryou_icon.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.popular'):
			self.addDirectoryItem(40519 if self.indexLabels else 40519, 'movies&url=traktpopular', 'trakt.png' if self.iconLogos else 'most-popular.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.trending'):
			self.addDirectoryItem(40522 if self.indexLabels else 40522, 'movies&url=trakttrending', 'trakt.png' if self.iconLogos else 'trending.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.watchedweekly'):
			self.addDirectoryItem(40515 if self.indexLabels else 40514, 'movies&url=traktwatchedweekly', 'trakt.png' if self.iconLogos else 'trending.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.watchedmonthly'):
			self.addDirectoryItem(40517 if self.indexLabels else 40516, 'movies&url=traktwatchedmonthly', 'trakt.png' if self.iconLogos else 'trending.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.tmdb.nowplaying'):
			self.addDirectoryItem(40526 if self.indexLabels else 40526, 'tmdbmovies&url=tmdb_nowplaying', 'tmdb.png' if self.iconLogos else 'nowplaying.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.anticipated'):
			self.addDirectoryItem(40525 if self.indexLabels else 40525, 'movies&url=traktanticipated', 'trakt.png' if self.iconLogos else 'in-theaters.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.tmdb.upcoming'):
			self.addDirectoryItem(40527 if self.indexLabels else 40527, 'tmdbmovies&url=tmdb_upcoming', 'tmdb.png' if self.iconLogos else 'upcoming.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.boxoffice'):
			self.addDirectoryItem(40521 if self.indexLabels else 40521, 'movies&url=traktboxoffice', 'trakt.png' if self.iconLogos else 'box-office.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.tmdb.toprated'):
			self.addDirectoryItem(40523 if self.indexLabels else 40523, 'tmdbmovies&url=tmdb_toprated', 'tmdb.png' if self.iconLogos else 'highly-rated.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.recommended'):
			self.addDirectoryItem(40524 if self.indexLabels else 40524, 'movies&url=traktrecommendations', 'trakt.png' if self.iconLogos else 'recommended.png', 'DefaultMovies.png')
		# ── SIMKL public trending lists (no login required, client_id-only) ────
		if getMenuEnabled('navi.movie.simkl.trendingToday'):
			self.addDirectoryItem(45000, 'movies&url=simkltrendingtoday', 'simkl.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.simkl.trendingWeek'):
			self.addDirectoryItem(45001, 'movies&url=simkltrendingweek',  'simkl.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.simkl.trendingMonth'):
			self.addDirectoryItem(45002, 'movies&url=simkltrendingmonth', 'simkl.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.tmdb.genres'):
			self.addDirectoryItem(32486 if self.indexLabels else 32455, 'movieGenres&url=tmdb_genre', 'tmdb.png' if self.iconLogos else 'genres.png', 'DefaultGenre.png')
		if getMenuEnabled('navi.movie.tmdb.years'):
			self.addDirectoryItem(32485 if self.indexLabels else 32457, 'movieYears&url=tmdb_year', 'tmdb.png' if self.iconLogos else 'years.png', 'DefaultYear.png')
		if getMenuEnabled('navi.movie.tmdb.certificates'):
			self.addDirectoryItem(32487 if self.indexLabels else 32463, 'movieCertificates&url=tmdb_certification', 'tmdb.png' if self.iconLogos else 'certificates.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.tmdb.providers'):
			self.addDirectoryItem(40701 if self.indexLabels else 40700, 'movieProviders', 'tmdb.png' if self.iconLogos else 'networks.png', 'DefaultNetwork.png')
		if getMenuEnabled('navi.movie.collections'):
			self.addDirectoryItem(32000, 'collections_Navigator', 'boxsets.png', 'DefaultSets.png')
		if getMenuEnabled('navi.movie.trakt.popularList'):
			self.addDirectoryItem(32417, 'movies_PublicLists&url=trakt_popularLists', 'trakt.png' if self.iconLogos else 'movies.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.trendingList'):
			self.addDirectoryItem(32418, 'movies_PublicLists&url=trakt_trendingLists', 'trakt.png' if self.iconLogos else 'movies.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.movie.trakt.searchList'):
			self.addDirectoryItem(32419, 'movies_SearchLists&media_type=movies', 'trakt.png' if self.iconLogos else 'movies.png', 'DefaultMovies.png', isFolder=False)
		if self.mdblistCredentials:
			if getMenuEnabled('navi.movie.mdblist.continue'):
				self.addDirectoryItem(40231, 'mdblist_continueMovies', 'mdblist.png', 'DefaultVideoPlaylists.png', queue=True)
			if getMenuEnabled('navi.movie.mdblist.topLists'):
				self.addDirectoryItem(40232, 'mdblist_movieTopListsPublic', 'mdblist.png', 'DefaultVideoPlaylists.png')
			if getMenuEnabled('navi.movie.mdblist.searchList'):
				self.addDirectoryItem(40233, 'mdblist_movieSearchListsPublic', 'mdblist.png', 'DefaultAddonsSearch.png', isFolder=False)
		if not lite:
			if getMenuEnabled('mylists.widget'): self.addDirectoryItem(32003, 'mymovieliteNavigator', 'mymovies.png', 'DefaultMovies.png')
			self.addDirectoryItem(33042, 'movieSearch', 'trakt.png' if self.iconLogos else 'search.png', 'DefaultAddonsSearch.png')
		self.endDirectory()

	def mymovies(self, lite=False):
		self.accountCheck()
		self.addDirectoryItem(32039, 'movieUserlists', 'userlists.png', 'DefaultVideoPlaylists.png')
		if self.traktCredentials:
			if self.traktIndicators:
				self.addDirectoryItem(35308, 'moviesUnfinished&url=traktunfinished', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32036, 'movies&url=trakthistory', 'trakt.png', 'trakt.png', queue=True)
			self.addDirectoryItem(32683, 'movies&url=traktwatchlist', 'trakt.png', 'trakt.png', queue=True, context=(32551, 'library_moviesToLibrary&url=traktwatchlist&name=traktwatchlist'))
			self.addDirectoryItem(32032, 'movies&url=traktcollection', 'trakt.png', 'trakt.png', queue=True, context=(32551, 'library_moviesToLibrary&url=traktcollection&name=traktcollection'))
			self.addDirectoryItem('My Liked Lists', 'movies_LikedLists', 'trakt.png', 'trakt.png', queue=True)
		self.endDirectory()

	def tvshows(self, lite=False):
		# For You (AI recommendations)
		self.addDirectoryItem(40111 if self.indexLabels else 40111, 'recoTV', 'foryou_icon.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.tv.trakt.trending'):
			self.addDirectoryItem(40522 if self.indexLabels else 40522, 'tvshows&url=trakttrending', 'trakt.png' if self.iconLogos else 'trending.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.originals'):
			self.addDirectoryItem(40077 if self.indexLabels else 40070, 'tvOriginals', 'tvmaze.png' if self.iconLogos else 'originals.png', 'DefaultNetwork.png')
		if getMenuEnabled('navi.tv.trakt.popular'):
			self.addDirectoryItem(40519 if self.indexLabels else 40519, 'tvshows&url=traktpopular', 'trakt.png' if self.iconLogos else 'most-popular.png', 'DefaultTVShows.png', queue=True)
		if getMenuEnabled('navi.tv.tmdb.toprated'):
			self.addDirectoryItem(40523 if self.indexLabels else 40523, 'tmdbTvshows&url=tmdb_toprated', 'tmdb.png' if self.iconLogos else 'highly-rated.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.tv.trakt.recommended'):
			self.addDirectoryItem(40524 if self.indexLabels else 40524, 'tvshows&url=traktrecommendations', 'trakt.png' if self.iconLogos else 'recommended.png', 'DefaultTVShows.png', queue=True)
		# ── SIMKL public trending lists (no login required, client_id-only) ────
		if getMenuEnabled('navi.tv.simkl.trendingToday'):
			self.addDirectoryItem(45010, 'tvshows&url=simkltrendingtoday', 'simkl.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.tv.simkl.trendingWeek'):
			self.addDirectoryItem(45011, 'tvshows&url=simkltrendingweek',  'simkl.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.tv.simkl.trendingMonth'):
			self.addDirectoryItem(45012, 'tvshows&url=simkltrendingmonth', 'simkl.png', 'DefaultTVShows.png')
		if getMenuEnabled('navi.tv.simkl.progress'):
			try:
				from resources.lib.modules import simkl
				if simkl.getSimklCredentialsInfo():
					self.addDirectoryItem(45013, 'calendar&url=simklprogress', 'simkl.png', 'DefaultTVShows.png', queue=True, context=(32072, 'episodes_clrProgressCache&url=simklprogress'))
			except: pass
		if getMenuEnabled('navi.tv.tmdb.genres'):
			self.addDirectoryItem(32486 if self.indexLabels else 32455, 'tvGenres&url=tmdb_genre', 'tmdb.png' if self.iconLogos else 'genres.png', 'DefaultGenre.png')
		if getMenuEnabled('navi.tv.tvmaze.networks'):
			self.addDirectoryItem(32468 if self.indexLabels else 32469, 'tvNetworks', 'tmdb.png' if self.iconLogos else 'networks.png', 'DefaultNetwork.png')
		# if getMenuEnabled('navi.tv.tmdb.certificates'):
		if getMenuEnabled('navi.tv.tmdb.years'):
			self.addDirectoryItem(32485 if self.indexLabels else 32457, 'tvYears&url=tmdb_year', 'tmdb.png' if self.iconLogos else 'years.png', 'DefaultYear.png')
		if getMenuEnabled('navi.tv.tmdb.airingtoday'):
			self.addDirectoryItem(40528 if self.indexLabels else 40528, 'tmdbTvshows&url=tmdb_airingtoday', 'tmdb.png' if self.iconLogos else 'airing-today.png', 'DefaultRecentlyAddedEpisodes.png')
		if getMenuEnabled('navi.tv.tmdb.ontv'):
			self.addDirectoryItem(40529 if self.indexLabels else 40529, 'tmdbTvshows&url=tmdb_ontheair', 'tmdb.png' if self.iconLogos else 'new-tvshows.png', 'DefaultRecentlyAddedEpisodes.png')
		if getMenuEnabled('navi.tv.tvmaze.calendar'):
			self.addDirectoryItem(32450 if self.indexLabels else 32027, 'calendars', 'tvmaze.png' if self.iconLogos else 'calendar.png', 'DefaultYear.png')
		if getMenuEnabled('navi.tv.trakt.popularList'):
			self.addDirectoryItem(32417, 'tv_PublicLists&url=trakt_popularLists', 'trakt.png' if self.iconLogos else 'tvshows.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.tv.trakt.trendingList'):
			self.addDirectoryItem(32418, 'tv_PublicLists&url=trakt_trendingLists', 'trakt.png' if self.iconLogos else 'tvshows.png', 'DefaultMovies.png')
		if getMenuEnabled('navi.tv.trakt.searchList'):
			self.addDirectoryItem(32419, 'tv_SearchLists&media_type=shows', 'trakt.png' if self.iconLogos else 'tvshows.png', 'DefaultMovies.png', isFolder=False)
		if self.mdblistCredentials:
			if getMenuEnabled('navi.tv.mdblist.continue'):
				self.addDirectoryItem(40234, 'mdblist_continueEpisodes', 'mdblist.png', 'DefaultVideoPlaylists.png', queue=True)
			if getMenuEnabled('navi.tv.mdblist.topLists'):
				self.addDirectoryItem(40235, 'mdblist_showTopListsPublic', 'mdblist.png', 'DefaultVideoPlaylists.png')
			if getMenuEnabled('navi.tv.mdblist.searchList'):
				self.addDirectoryItem(40236, 'mdblist_showSearchListsPublic', 'mdblist.png', 'DefaultAddonsSearch.png', isFolder=False)
		if not lite:
			if getMenuEnabled('mylists.widget'): self.addDirectoryItem(32004, 'mytvliteNavigator', 'mytvshows.png', 'DefaultTVShows.png')
			self.addDirectoryItem(33043, 'tvSearch', 'trakt.png' if self.iconLogos else 'search.png', 'DefaultAddonsSearch.png')
		self.endDirectory()

	def mytvshows(self, lite=False):
		self.accountCheck()
		self.addDirectoryItem(32040, 'tvUserlists', 'userlists.png', 'DefaultVideoPlaylists.png')
		if self.traktCredentials:
			if self.traktIndicators:
				self.addDirectoryItem(35308, 'episodesUnfinished&url=traktunfinished', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32037, 'calendar&url=progress', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32019, 'upcomingProgress&url=progress', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32202, 'calendar&url=mycalendarRecent', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32203, 'calendar&url=mycalendarUpcoming', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32204, 'calendar&url=mycalendarPremiers', 'trakt.png', 'trakt.png', queue=True)
				self.addDirectoryItem(32036, 'calendar&url=trakthistory', 'trakt.png', 'trakt.png', queue=True)
			self.addDirectoryItem(32683, 'tvshows&url=traktwatchlist', 'trakt.png', 'trakt.png', context=(32551, 'library_tvshowsToLibrary&url=traktwatchlist&name=traktwatchlist'))
			self.addDirectoryItem(32032, 'tvshows&url=traktcollection', 'trakt.png', 'trakt.png', context=(32551, 'library_tvshowsToLibrary&url=traktcollection&name=traktcollection'))
			self.addDirectoryItem('My Liked Lists', 'shows_LikedLists', 'trakt.png', 'trakt.png', queue=True)
		self.endDirectory()

	def mdblist_movies(self):
		self.addDirectoryItem(40212, 'mdblist_movieWatchlist', 'mdblist.png', 'DefaultVideoPlaylists.png', queue=True)
		self.addDirectoryItem(40213, 'mdblist_movieUserLists', 'mdblist.png', 'DefaultVideoPlaylists.png')
		self.addDirectoryItem(40214, 'mdblist_movieTopLists', 'mdblist.png', 'DefaultVideoPlaylists.png')
		self.addDirectoryItem(40215, 'mdblist_movieSearchLists', 'mdblist.png', 'DefaultAddonsSearch.png', isFolder=False)
		self.addDirectoryItem(40241, 'mdblist_browseUser', 'mdblist.png', 'DefaultVideoPlaylists.png', isFolder=False)
		self.addDirectoryItem(40243, 'mdblist_importByUrl&media_type=movie', 'mdblist.png', 'DefaultVideoPlaylists.png', isFolder=False)
		self.endDirectory()

	def mdblist_tv(self):
		self.addDirectoryItem(40216, 'mdblist_showWatchlist', 'mdblist.png', 'DefaultVideoPlaylists.png', queue=True)
		self.addDirectoryItem(40217, 'mdblist_showUserLists', 'mdblist.png', 'DefaultVideoPlaylists.png')
		self.addDirectoryItem(40218, 'mdblist_showTopLists', 'mdblist.png', 'DefaultVideoPlaylists.png')
		self.addDirectoryItem(40219, 'mdblist_showSearchLists', 'mdblist.png', 'DefaultAddonsSearch.png', isFolder=False)
		self.addDirectoryItem(40241, 'mdblist_browseUser', 'mdblist.png', 'DefaultVideoPlaylists.png', isFolder=False)
		self.addDirectoryItem(40243, 'mdblist_importByUrl&media_type=show', 'mdblist.png', 'DefaultVideoPlaylists.png', isFolder=False)
		self.endDirectory()

	def anime(self, lite=False):
		self.addDirectoryItem(32001, 'anime_Movies&url=anime', 'movies.png', 'DefaultMovies.png')
		self.addDirectoryItem(32002, 'anime_TVshows&url=anime', 'tvshows.png', 'DefaultTVShows.png')
		self.endDirectory()

	def traktSearchLists(self, media_type):
		k = control.keyboard('', getLS(32010))
		k.doModal()
		q = k.getText() if k.isConfirmed() else None
		if not q: return control.closeAll()
		page_limit = getSetting('page.item.limit')
		url = 'https://api.trakt.tv/search/list?limit=%s&page=1&query=' % page_limit + quote_plus(q)
		control.closeAll()
		if media_type == 'movies': control.execute('ActivateWindow(Videos,plugin://plugin.video.luc_kodi/?action=movies_PublicLists&url=%s,return)' % (quote_plus(url)))
		else: control.execute('ActivateWindow(Videos,plugin://plugin.video.luc_kodi/?action=tv_PublicLists&url=%s,return)' % (quote_plus(url)))

	def tools(self):
		if self.traktCredentials: self.addDirectoryItem(35057, 'tools_traktToolsNavigator', 'tools.png', 'DefaultAddonService.png', isFolder=True)
		self.addDirectoryItem(32510, 'cache_Navigator', 'tools.png', 'DefaultAddonService.png', isFolder=True)
		self.addDirectoryItem(400700, 'tools_updateCatalog', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32523, 'tools_loggingNavigator', 'tools.png', 'DefaultAddonService.png')
		self.addDirectoryItem(32083, 'tools_cleanSettings', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		#self.addDirectoryItem(32506, 'tools_contextluc_kodiSettings', 'icon.png', 'DefaultAddonProgram.png', isFolder=False)
		#-- Providers - 5
		#self.addDirectoryItem(32047, 'tools_openSettings&query=5.0', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		#-- General - 0
		self.addDirectoryItem(32043, 'tools_openSettings&query=0.0', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		#-- Navigation - 1
		#self.addDirectoryItem(32362, 'tools_openSettings&query=1.0', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		#-- Playback - 4
		#self.addDirectoryItem(32045, 'tools_openSettings&query=4.0', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		#-- Accounts - 8
		#self.addDirectoryItem(32044, 'tools_openSettings&query=9.0', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		#-- Downloads - 11
		#self.addDirectoryItem(32048, 'tools_openSettings&query=11.0', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32556, 'library_Navigator', 'tools.png', 'DefaultAddonService.png', isFolder=True)
		self.addDirectoryItem(32049, 'tools_viewsNavigator', 'tools.png', 'DefaultAddonService.png', isFolder=True)
		self.addDirectoryItem(400732, 'tools_setAddonView', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32361, 'tools_resetViewTypes', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def traktTools(self):
		self.addDirectoryItem(35058, 'shows_traktHiddenManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35059, 'movies_traktUnfinishedManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35060, 'episodes_traktUnfinishedManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35061, 'movies_traktWatchListManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35062, 'shows_traktWatchListManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35063, 'movies_traktCollectionManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35064, 'shows_traktCollectionManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35065, 'tools_traktLikedListManager', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(35066, 'tools_forceTraktSync', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def loggingNavigator(self):
		self.addDirectoryItem(32524, 'tools_viewLogFile&name=luc_kodi', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
#		self.addDirectoryItem(32525, 'tools_clearLogFile', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(32526, 'tools_ShowChangelog&name=luc_kodi', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(32527, 'tools_uploadLogFile&name=luc_kodi', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
#		self.addDirectoryItem(32530, 'tools_viewLogFile&name=jacksparrowscrapers', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
#		self.addDirectoryItem(32531, 'tools_ShowChangelog&name=jacksparrowscrapers', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(32532, 'tools_viewLogFile&name=Kodi', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(32198, 'tools_uploadLogFile&name=Kodi', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		self.endDirectory()

	def cf(self):
		self.addDirectoryItem(32610, 'cache_clearAll', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32611, 'cache_clearSources', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32612, 'cache_clearMeta', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32613, 'cache_clearCache', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32614, 'cache_clearSearch', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem(32615, 'cache_clearBookmarks', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.addDirectoryItem('Reset Feedback (For You)', 'cache_clearRecoFeedback', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def library(self): # -- Library - 9
		self.addDirectoryItem(32557, 'tools_openSettings&query=9.0', 'tools.png', 'DefaultAddonProgram.png', isFolder=False)
		self.addDirectoryItem(32558, 'library_update', 'library_update.png', 'DefaultAddonLibrary.png', isFolder=False)
		self.addDirectoryItem(32676, 'library_clean', 'library_update.png', 'DefaultAddonLibrary.png', isFolder=False)
		self.addDirectoryItem(32559, getSetting('library.movie'), 'movies.png', 'DefaultMovies.png', isAction=False)
		self.addDirectoryItem(32560, getSetting('library.tv'), 'tvshows.png', 'DefaultTVShows.png', isAction=False)
		if self.traktCredentials:
			self.addDirectoryItem(32561, 'library_moviesToLibrary&url=traktcollection&name=traktcollection', 'trakt.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem(32562, 'library_moviesToLibrary&url=traktwatchlist&name=traktwatchlist', 'trakt.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem(32672, 'library_moviesListToLibrary&url=traktlists', 'trakt.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem(32673, 'library_moviesListToLibrary&url=traktlikedlists', 'trakt.png', 'DefaultMovies.png', isFolder=False)
		if self.tmdbSessionID:
			self.addDirectoryItem('TMDb: Import Movie Watchlist...', 'library_moviesToLibrary&url=tmdb_watchlist&name=tmdb_watchlist', 'tmdb.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem('TMDb: Import Movie Favorites...', 'library_moviesToLibrary&url=tmdb_favorites&name=tmdb_favorites', 'tmdb.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem('TMDb: Import Movie User list...', 'library_moviesListToLibrary&url=tmdb_userlists', 'tmdb.png', 'DefaultMovies.png', isFolder=False)
		if self.traktCredentials:
			self.addDirectoryItem(32563, 'library_tvshowsToLibrary&url=traktcollection&name=traktcollection', 'trakt.png', 'DefaultTVShows.png', isFolder=False)
			self.addDirectoryItem(32564, 'library_tvshowsToLibrary&url=traktwatchlist&name=traktwatchlist', 'trakt.png', 'DefaultTVShows.png', isFolder=False)
			self.addDirectoryItem(32674, 'library_tvshowsListToLibrary&url=traktlists', 'trakt.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem(32675, 'library_tvshowsListToLibrary&url=traktlikedlists', 'trakt.png', 'DefaultMovies.png', isFolder=False)
		if self.tmdbSessionID:
			self.addDirectoryItem('TMDb: Import TV Watchlist...', 'library_tvshowsToLibrary&url=tmdb_watchlist&name=tmdb_watchlist', 'tmdb.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem('TMDb: Import TV Favorites...', 'library_tvshowsToLibrary&url=tmdb_favorites&name=tmdb_favorites', 'tmdb.png', 'DefaultMovies.png', isFolder=False)
			self.addDirectoryItem('TMDb: Import TV User list...', 'library_tvshowsListToLibrary&url=tmdb_userlists', 'tmdb.png', 'DefaultMovies.png', isFolder=False)
		self.endDirectory()

	def downloads(self):
		movie_downloads = getSetting('movie.download.path')
		tv_downloads = getSetting('tv.download.path')
		if len(control.listDir(movie_downloads)[0]) > 0: self.addDirectoryItem(32001, movie_downloads, 'movies.png', 'DefaultMovies.png', isAction=False)
		if len(control.listDir(tv_downloads)[0]) > 0: self.addDirectoryItem(32002, tv_downloads, 'tvshows.png', 'DefaultTVShows.png', isAction=False)
		self.endDirectory()

	def premium_services(self):
		self.addDirectoryItem('Debrid Hub', 'tools_debridHub', 'premium.png', 'premium.png')
		if getMenuEnabled('navi.realdebrid'): self.addDirectoryItem(40058, 'rd_ServiceNavigator', 'realdebrid.png', 'realdebrid.png')
		if getMenuEnabled('navi.premiumize'): self.addDirectoryItem(40057, 'pm_ServiceNavigator', 'premiumize.png', 'premiumize.png')
		if getMenuEnabled('navi.alldebrid'): self.addDirectoryItem(40059, 'ad_ServiceNavigator', 'alldebrid.png', 'alldebrid.png')
		if getMenuEnabled('navi.torbox'): self.addDirectoryItem(32224, 'tb_ServiceNavigator', 'torbox.png', 'torbox.png')
		if getMenuEnabled('navi.furk'): self.addDirectoryItem('Furk.net', 'furk_ServiceNavigator', 'furk.png', 'furk.png')
		self.endDirectory()

	def alldebrid_service(self):
		if getSetting('alldebrid.token'):
			self.addDirectoryItem('All-Debrid: Cloud Storage', 'ad_CloudStorage', 'alldebrid.png', 'DefaultAddonService.png')
			self.addDirectoryItem('All-Debrid: Transfers', 'ad_Transfers', 'alldebrid.png', 'DefaultAddonService.png')
			self.addDirectoryItem('All-Debrid: Account Info', 'ad_AccountInfo', 'alldebrid.png', 'DefaultAddonService.png', isFolder=False)
		else:
			self.addDirectoryItem('[I]Please visit My Accounts for setup[/I]', 'tools_openSettings&query=7.0', 'alldebrid.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def torbox_service(self):
		if getSetting('torbox.username'):
			self.addDirectoryItem('TorBox: Search', 'en_Search', 'search.png', 'DefaultAddonsSearch.png')
			self.addDirectoryItem('TorBox: Account Info', 'en_AccountInfo', 'torbox.png', 'DefaultAddonService.png', isFolder=False)
		else:
			self.addDirectoryItem('[I]Please visit My Accounts for setup[/I]', 'tools_openSettings&query=7.0', 'torbox.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def furk_service(self):
		if getSetting('furk.api'):
			self.addDirectoryItem('Furk: Search', 'furk_Search', 'search.png', 'DefaultAddonsSearch.png')
			self.addDirectoryItem('Furk: User Files', 'furk_UserFiles', 'furk.png', 'DefaultAddonService.png')
			self.addDirectoryItem('Furk: Account Info', 'furk_AccountInfo', 'furk.png', 'DefaultAddonService.png', isFolder=False)
		else:
			self.addDirectoryItem('[I]Please visit My Accounts for setup[/I]', 'tools_openSettings&query=7.0', 'furk.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def premiumize_service(self):
		if getSetting('premiumize.token'):
			self.addDirectoryItem('Premiumize: My Files', 'pm_MyFiles', 'premiumize.png', 'DefaultAddonService.png')
			self.addDirectoryItem('Premiumize: Transfers', 'pm_Transfers', 'premiumize.png', 'DefaultAddonService.png')
			self.addDirectoryItem('Premiumize: Account Info', 'pm_AccountInfo', 'premiumize.png', 'DefaultAddonService.png', isFolder=False)
		else:
			self.addDirectoryItem('[I]Please visit My Accounts for setup[/I]', 'tools_openSettings&query=7.0', 'premiumize.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def realdebrid_service(self):
		if getSetting('realdebrid.token'):
			self.addDirectoryItem('Real-Debrid: Torrent Transfers', 'rd_UserTorrentsToListItem', 'realdebrid.png', 'DefaultAddonService.png')
			self.addDirectoryItem('Real-Debrid: My Downloads', 'rd_MyDownloads&query=1', 'realdebrid.png', 'DefaultAddonService.png')
			self.addDirectoryItem('Real-Debrid: Account Info', 'rd_AccountInfo', 'realdebrid.png', 'DefaultAddonService.png', isFolder=False )
		else:
			self.addDirectoryItem('[I]Please visit My Accounts for setup[/I]', 'tools_openSettings&query=7.0', 'realdebrid.png', 'DefaultAddonService.png', isFolder=False)
		self.endDirectory()

	def search(self):
		# AI Search (Gemini) — destacado al inicio del menú
		self.addDirectoryItem('[COLOR %s]%s[/COLOR]' % (self.highlight_color, getLS(40610)), 'aiSearch', 'search.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem('[COLOR %s]%s[/COLOR]' % (self.highlight_color, getLS(40615)), 'aiSearchMovies', 'movies.png', 'DefaultMovies.png')
		self.addDirectoryItem('[COLOR %s]%s[/COLOR]' % (self.highlight_color, getLS(40616)), 'aiSearchTvshows', 'tvshows.png', 'DefaultTVShows.png')
		self.addDirectoryItem(33042, 'movieSearch', 'trakt.png' if self.iconLogos else 'search.png', 'DefaultAddonsSearch.png')
		self.addDirectoryItem(33043, 'tvSearch', 'trakt.png' if self.iconLogos else 'search.png', 'DefaultAddonsSearch.png')
		self.endDirectory()

	def views(self):
		try:
			from sys import argv # some functions throw invalid handle -1 unless this is imported here.
			syshandle = int(argv[1])
			control.hide()
			items = [(getLS(32001), 'movies'), (getLS(32002), 'tvshows'), (getLS(32054), 'seasons'), (getLS(32326), 'episodes'), (getLS(400733), 'menus') ]
			select = control.selectDialog([i[0] for i in items], getLS(32049))
			if select == -1: return
			content = items[select][1]
			kodi_content = 'files' if content == 'menus' else content # 'menus' no es un content-type real
			title = getLS(32059)
			url = 'plugin://plugin.video.luc_kodi/?action=tools_addView&content=%s' % content
			poster, banner, fanart = control.addonPoster(), control.addonBanner(), control.addonFanart()
			item = control.item(label=title, offscreen=True)
			item.setInfo(type='video', infoLabels = {'title': title}) if KODI_VERSION < 20 else item.getVideoInfoTag().setTitle(title)
			item.setArt({'icon': poster, 'thumb': poster, 'poster': poster, 'fanart': fanart, 'banner': banner})
			control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			control.content(syshandle, kodi_content)
			control.directory(syshandle, cacheToDisc=True)
			from resources.lib.modules import views
			views.setView(content, {})
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return

	def setAddonView(self):
		# "Set Add-on View": elige el perfil de interfaz del add-on.
		#   Default   -> como siempre.
		#   Modern UI -> secciones/categorías en rejilla de iconos y contenido en
		#                InfoWall (póster + sinopsis + rating).
		#   Bingie    -> menús en rejilla de iconos y contenido en la ventana
		#                propia estilo Bingie (hero + sinopsis + ratings).
		try:
			from resources.lib.modules import views
			control.hide()
			tokens = ['default', 'bingie']
			options = [getLS(400730), 'Bingie UI']
			current = views.getViewStyle()
			pre = tokens.index(current) if current in tokens else 0
			# marcamos el activo con un check para que se vea cuál está puesto
			labels = [('[B]» [/B]' + o) if i == pre else o for i, o in enumerate(options)]
			select = control.selectDialog(labels, getLS(400732))
			if select == -1: return
			token = views.setViewStyle(tokens[select])
			addonName = control.addonName()
			control.notification(title=addonName, message='%s: %s' % (getLS(400732), options[select]))
			control.refresh()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return

	def accountCheck(self):
		if not self.traktCredentials and not self.imdbCredentials:
			control.hide()
			control.notification(message=32042, icon='WARNING')
			sysexit()

	def clearCacheAll(self):
		control.hide()
		if not control.yesnoDialog(getLS(32077), '', ''): return
		try:
			def cache_clear_all():
				try:
					from resources.lib.database import cache, providerscache, metacache, fanarttv_cache
					fanarttv_cache.cache_clear()
					providerscache.cache_clear_providers()
					metacache.cache_clear_meta()
					cache.cache_clear()
					# feedback NOT cleared here — it's persistent user data, not a cache
					return True
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
			if cache_clear_all(): control.notification(message=32089)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearRecoFeedback(self):
		control.hide()
		if not control.yesnoDialog('Reset Feedback', 'All likes and Not Interested signals will be deleted.\nThe engine will learn from scratch.', ''): return
		try:
			from resources.lib.database import reco_feedback
			reco_feedback.clear_all()
			control.notification(title='For You', message='Feedback reset successfully')
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearCacheProviders(self):
		control.hide()
		if not control.yesnoDialog(getLS(32056), '', ''): return
		try:
			from resources.lib.database import providerscache
			if providerscache.cache_clear_providers(): control.notification(message=32090)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearCacheMeta(self):
		control.hide()
		if not control.yesnoDialog(getLS(32076), '', ''): return
		try:
			from resources.lib.database import metacache
			if metacache.cache_clear_meta(): control.notification(message=32091)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearCache(self):
		control.hide()
		if not control.yesnoDialog(getLS(32056), '', ''): return
		try:
			from resources.lib.database import cache
			if cache.cache_clear(): control.notification(message=32092)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearMetaAndCache(self):
		control.hide()
		if not control.yesnoDialog(getLS(35531), '', ''): return
		try:
			def cache_clear_both():
				try:
					from resources.lib.database import cache, metacache
					metacache.cache_clear_meta()
					cache.cache_clear()
					return True
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
			if cache_clear_both(): control.notification(message=35532)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearCacheSearch(self):
		control.hide()
		if not control.yesnoDialog(getLS(32056), '', ''): return
		try:
			from resources.lib.database import cache
			if cache.cache_clear_search(): control.notification(message=32093)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearCacheSearchPhrase(self, table, name):
		control.hide()
		if not control.yesnoDialog(getLS(32056), '', ''): return
		try:
			from resources.lib.database import cache
			if cache.cache_clear_SearchPhrase(table, name): control.notification(message=32094)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearBookmarks(self):
		control.hide()
		if not control.yesnoDialog(getLS(32056), '', ''): return
		try:
			from resources.lib.database import cache
			if cache.cache_clear_bookmarks(): control.notification(message=32100)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def clearBookmark(self, name, year):
		control.hide()
		if not control.yesnoDialog(getLS(32056), '', ''): return
		try:
			from resources.lib.database import cache
			if cache.cache_clear_bookmark(name, year): control.notification(title=name, message=32102)
			else: control.notification(message=33586)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addDirectoryItem(self, name, query, poster, icon, context=None, queue=False, isAction=True, isFolder=True, isPlayable=False, isSearch=False, table=''):
		try:
			from sys import argv # some functions like ActivateWindow() throw invalid handle less this is imported here.
			if isinstance(name, int): name = getLS(name)
			# ── Bingie modern grid: redirige las categorías de contenido a la
			#    ventana propia (sólo en el perfil 'bingie' y sólo para listados
			#    de pelis/series; los menús de navegación quedan intactos). ──
			try:
				from resources.lib.modules import views
				if isAction and views.getViewStyle() == 'bingie':
					_act = query.split('&', 1)[0]
					_rest = ('&' + query.split('&', 1)[1]) if '&' in query else ''
					_nm = quote_plus(name if isinstance(name, str) else str(name))
					if _act in ('movies', 'moviePage'):
						query = 'bingie_gridMovies%s&title=%s' % (_rest, _nm)
						isFolder = False
					elif _act in ('tmdbmovies', 'tmdbmoviePage'):
						query = 'bingie_gridMovies%s&title=%s&tmdb=1' % (_rest, _nm)
						isFolder = False
					elif _act in ('tvshows', 'tvshowPage'):
						query = 'bingie_gridTVShows%s&title=%s' % (_rest, _nm)
						isFolder = False
					elif _act in ('tmdbTvshows', 'tmdbTvshowPage'):
						query = 'bingie_gridTVShows%s&title=%s&tmdb=1' % (_rest, _nm)
						isFolder = False
			except Exception:
				pass
			url = 'plugin://plugin.video.luc_kodi/?action=%s' % query if isAction else query
			poster = control.joinPath(self.artPath, poster) if self.artPath else icon
			if not icon.startswith('Default'): icon = control.joinPath(self.artPath, icon)
			cm = []
			queueMenu = getLS(32065)
			if queue: cm.append((queueMenu, 'RunPlugin(plugin://plugin.video.luc_kodi/?action=playlist_QueueItem)'))
			if context: cm.append((getLS(context[0]), 'RunPlugin(plugin://plugin.video.luc_kodi/?action=%s)' % context[1]))
			if isSearch: cm.append(('Clear Search Phrase', 'RunPlugin(plugin://plugin.video.luc_kodi/?action=cache_clearSearchPhrase&source=%s&name=%s)' % (table, quote_plus(name))))
			cm.append(('[COLOR red]luc_kodi Settings[/COLOR]', 'RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_openSettings)'))
			item = control.item(label=name, offscreen=True)
			item.addContextMenuItems(cm)
			if isPlayable: item.setProperty('IsPlayable', 'true')
			item.setArt({'icon': icon, 'poster': poster, 'thumb': poster, 'fanart': control.addonFanart(), 'banner': poster})
			item.setInfo(type='video', infoLabels={'plot': name}) if KODI_VERSION < 20 else item.getVideoInfoTag().setPlot(name)
			control.addItem(handle=int(argv[1]), url=url, listitem=item, isFolder= isFolder)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def endDirectory(self, is_root=False):
		from sys import argv # some functions throw invalid handle -1 unless this is imported here.
		from resources.lib.modules import views
		syshandle = int(argv[1])
		# The ROOT menu (Movies/Shows/Trakt/Search/Tools/...) always uses the
		# classic skin view — the Bingie UI starts one level deeper, inside the
		# Movies/TV section homes. So we never force the icon grid on root.
		# All folder menus (root sections AND utility submenus like Tools, Trakt,
		# AI Search, Movie/TV Show Lists) use the same list view as the main
		# section when the Bingie UI style is active. The real CONTENT sections
		# (Movies/TV grids) open as their own WindowXMLDialog via RunPlugin and
		# are unaffected by this.
		modern = views.getViewStyle() == 'bingie'
		if control.skin == 'skin.auramod': content = 'addons'
		elif modern: content = 'files' # content estable para poder forzar la vista lista
		else: content = ''
		control.content(syshandle, content) # some skins use their own thumb for things like "genres" when content type is set here
		control.directory(syshandle, cacheToDisc=True)
		if modern and control.skin != 'skin.auramod': views.setMenuView()