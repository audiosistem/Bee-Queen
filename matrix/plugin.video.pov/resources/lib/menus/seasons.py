import sys
from threading import Thread
from indexers.metadata import tvshow_meta, season_episodes_meta, all_episodes_meta, tmdb_image_base
from caches.watched_cache import get_watched_info_tv, get_watched_status_season, get_bookmarks, get_resumetime, set_resumetime, get_watched_status_episode
from modules import kodi_utils, settings
from modules.utils import adjust_premiered_date, get_datetime
# from modules.kodi_utils import logger

tv_meta_function, season_meta_function, default_duration = tvshow_meta, season_episodes_meta, 3600
KODI_VERSION, make_cast_list = kodi_utils.get_kodi_version(), kodi_utils.make_cast_list
string, ls, build_url = str, kodi_utils.local_string, kodi_utils.build_url
remove_meta_keys, dict_removals = kodi_utils.remove_meta_keys, kodi_utils.episode_dict_removals
get_art_provider, show_specials = settings.get_art_provider, settings.show_specials
adjust_premiered_date_function, get_datetime_function = adjust_premiered_date, get_datetime
run_plugin, container_refresh, container_update = 'RunPlugin(%s)', 'Container.Refresh(%s)', 'Container.Update(%s)'
fanart_empty = kodi_utils.get_addoninfo('fanart')
poster_empty = kodi_utils.media_path('box_office.png')
watched_str, unwatched_str, extras_str, options_str = ls(32642), ls(32643), ls(32645), ls(32646)
clearprog_str, season_str, unaired_label = ls(32651), ls(32537), '[COLOR cyan]%s[/COLOR]'

class Seasons:
	def __init__(self, params):
		self.params = params
		self.items = []
		self.append = self.items.append
		self.current_date = get_datetime_function()
		self.meta_user_info = settings.metadata_user_info()
		self.watched_indicators = settings.watched_indicators()
		self.watched_info = get_watched_info_tv(self.watched_indicators)
		self.watched_title = ('POV', 'Trakt', 'MDBList')[self.watched_indicators]
		self.show_unaired = settings.show_unaired()
		self.is_widget = kodi_utils.external_browse()
		self.fanart_enabled = self.meta_user_info['extra_fanart_enabled']
		self.widget_hide_watched = self.is_widget and self.meta_user_info['widget_hide_watched']
		self.poster_main, self.poster_backup, self.fanart_main, self.fanart_backup = get_art_provider()

	def build_season_list(self, params):
		def _process_season_list():
			use_season_title = settings.use_season_title()
			image_resolution = self.meta_user_info['image_resolution']['poster']
			season_data = meta_get('season_data')
			if season_data:
				if 'season' in params: season_data = [i for i in season_data if i['season_number'] == params['season']]
				if not show_specials(): season_data = [i for i in season_data if not i['season_number'] == 0]
				season_data.sort(key=lambda k: k['season_number'])
			else: season_data = []
			running_ep_count = total_aired_eps
			for item in season_data:
				try:
					props = {}
					cm = []
					cm_append = cm.append
					item_get = item.get
					name, overview, rating = item_get('name'), item_get('overview'), item_get('vote_average')
					season_number, episode_count = item_get('season_number'), item_get('episode_count')
					poster_path, air_date = item_get('poster_path'), item_get('air_date')
					if not poster_path is None: poster = tmdb_image_base % (image_resolution, poster_path)
					else: poster = show_poster
					if season_number == 0: unaired = False
					elif episode_count == 0: unaired = True
					elif season_number != total_seasons: unaired = False
					else:
						episode_airs = adjust_premiered_date_function(air_date, 0)[0]
						if not episode_airs or self.current_date < episode_airs: unaired = True
						else: unaired = False
					if unaired:
						if not self.show_unaired: return
						episode_count = 0
					elif season_number != 0:
						running_ep_count -= episode_count
						if running_ep_count < 0: episode_count = running_ep_count + episode_count
					try: year = air_date.split('-')[0]
					except: year = show_year
					plot = overview or show_plot
					title = name if use_season_title and name else ' '.join([season_str, string(season_number)])
					if 'season' in params: title = '%s: %s' % (show_title, title)
					if unaired: title = '[I]%s[/I]' % (unaired_label % title)
					playcount, overlay, watched, unwatched = get_watched_status_season(self.watched_info, string(tmdb_id), season_number, episode_count)
					if self.widget_hide_watched and watched: continue
					url_params = build_url({'mode': 'build_episode_list', 'tmdb_id': tmdb_id, 'season': season_number})
					extras_params = build_url({'mode': 'extras_menu_choice', 'media_type': 'tvshow', 'tmdb_id': tmdb_id, 'is_widget': self.is_widget})
					options_params = build_url({'mode': 'options_menu_choice', 'content': 'season', 'tmdb_id': tmdb_id, 'is_widget': self.is_widget})
					cm_append((options_str, run_plugin % options_params))
					cm_append((extras_str, run_plugin % extras_params))
					if not playcount: cm_append((watched_str % self.watched_title, run_plugin % build_url({
						'mode': 'mark_as_watched_unwatched_season', 'action': 'mark_as_watched', 'year': show_year,
						'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season_number, 'title': show_title
					})))
					if watched: cm_append((unwatched_str % self.watched_title, run_plugin % build_url({
						'mode': 'mark_as_watched_unwatched_season', 'action': 'mark_as_unwatched', 'year': show_year,
						'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season_number, 'title': show_title
					})))
					props['unwatchedepisodes'] = string(unwatched)
					props['totalepisodes'] = string(episode_count)
					props['pov_sort_order'] = string(params.get('sort', ''))
					listitem = kodi_utils.make_listitem()
					listitem.addContextMenuItems(cm)
					listitem.setProperties(props)
					listitem.setLabel(title)
					listitem.setArt({'poster': poster, 'icon': poster, 'thumb': poster, 'fanart': fanart, 'banner': banner, 'clearart': clearart, 'clearlogo': clearlogo,
									'landscape': landscape, 'tvshow.poster': poster, 'tvshow.clearart': clearart, 'tvshow.clearlogo': clearlogo, 'tvshow.landscape': landscape, 'tvshow.banner': banner})
					if KODI_VERSION < 20:
						listitem.setCast(show_cast)
						listitem.setUniqueIDs({'imdb': imdb_id, 'tmdb': string(tmdb_id), 'tvdb': string(tvdb_id)})
						listitem.setInfo('video', {'mediatype': 'season', 'trailer': trailer, 'title': title, 'size': '0', 'duration': episode_run_time, 'plot': plot,
									'rating': rating, 'premiered': air_date, 'studio': studio, 'year': year, 'genre': genre, 'mpaa': mpaa, 'tvshowtitle': show_title,
									'imdbnumber': imdb_id, 'votes': votes, 'season': season_number, 'playcount': playcount, 'overlay': overlay})
						listitem.setProperty('watchedepisodes', string(watched))
					else:
						if watched > 0: listitem.setProperty('watchedepisodes', string(watched))
						videoinfo = listitem.getVideoInfoTag(offscreen=True)
						videoinfo.setCast(make_cast_list(show_cast))
						videoinfo.setUniqueIDs({'imdb': imdb_id, 'tmdb': string(tmdb_id), 'tvdb': string(tvdb_id)})
						videoinfo.setDuration(episode_run_time)
						videoinfo.setGenres(genre.split(', '))
						videoinfo.setIMDBNumber(imdb_id)
						videoinfo.setMediaType('season')
						videoinfo.setMpaa(mpaa)
						videoinfo.setPlaycount(playcount)
						videoinfo.setPlot(plot)
						videoinfo.setPremiered(air_date)
						videoinfo.setRating(rating)
						videoinfo.setSeason(season_number)
						videoinfo.setStudios((studio,))
						videoinfo.setTitle(title)
						videoinfo.setTrailer(trailer)
						videoinfo.setTvShowStatus(show_status)
						videoinfo.setTvShowTitle(show_title)
						videoinfo.setVotes(votes)
						videoinfo.setYear(int(year))
					self.append((url_params, listitem, True))
				except: pass
		def _process_episode_list():
			thumb_fanart = settings.thumb_fanart()
			adjust_hours = settings.date_offset()
			bookmarks = get_bookmarks(self.watched_indicators, 'episode')
			all_episodes = True if params.get('season') == 'all' else False
			if all_episodes:
				episodes_data = all_episodes_meta(meta, self.meta_user_info, Thread)
				if not show_specials(): episodes_data = [i for i in episodes_data if not i['season'] == 0]
			else: episodes_data = season_meta_function(params['season'], meta, self.meta_user_info)
			for item in episodes_data:
				try:
					props = {}
					cm = []
					cm_append = cm.append
					item_get = item.get
					season, episode, ep_name = item_get('season'), item_get('episode'), item_get('title')
					premiered, cast = item_get('premiered'), show_cast + item_get('guest_stars', [])
					episode_date, premiered = adjust_premiered_date_function(premiered, adjust_hours)
					playcount, overlay = get_watched_status_episode(self.watched_info, string(tmdb_id), season, episode)
					resumetime, progress = get_resumetime(bookmarks, tmdb_id, season, episode)
					thumb = item_get('thumb') or fanart
					background = thumb if thumb_fanart else fanart
					item.update({'trailer': trailer, 'tvshowtitle': show_title, 'premiered': premiered, 'genre': genre, 'duration': episode_run_time, 'mpaa': mpaa, 'studio': studio,
								'playcount': playcount, 'overlay': overlay})
					extras_params = build_url({'mode': 'extras_menu_choice', 'media_type': 'tvshow', 'tmdb_id': tmdb_id, 'is_widget': self.is_widget})
					options_params = build_url({'mode': 'options_menu_choice', 'content': 'episode', 'tmdb_id': tmdb_id, 'season': season, 'episode': episode, 'is_widget': self.is_widget})
					url_params = build_url({'mode': 'play_media', 'media_type': 'episode', 'tmdb_id': tmdb_id, 'season': season, 'episode': episode})
					display = ep_name
					unaired = False
					if not episode_date or self.current_date < episode_date:
						if not self.show_unaired: continue
						if season != 0:
							unaired = True
							display = '[I]%s[/I]' % (unaired_label % ep_name)
							item['title'] = display
					if self.widget_hide_watched and playcount and not unaired: continue
					try: year = premiered.split('-')[0]
					except: year = show_year
					cm_append((options_str, run_plugin % options_params))
					cm_append((extras_str, run_plugin % extras_params))
					clearprog_params, unwatched_params, watched_params = '', '', ''
					if not unaired:
						if progress != '0' or resumetime != '0': cm_append((clearprog_str, run_plugin % build_url({
							'mode': 'watched_unwatched_erase_bookmark', 'media_type': 'episode',
							'tmdb_id': tmdb_id, 'season': season, 'episode': episode, 'refresh': 'true'
						})))
						if playcount: cm_append((unwatched_str % self.watched_title, run_plugin % build_url({
							'mode': 'mark_as_watched_unwatched_episode', 'action': 'mark_as_unwatched', 'year': show_year,
							'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': episode, 'title': show_title
						})))
						else: cm_append((watched_str % self.watched_title, run_plugin % build_url({
							'mode': 'mark_as_watched_unwatched_episode', 'action': 'mark_as_watched', 'year': show_year,
							'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': episode, 'title': show_title
						})))
					props['episode_type'] = item_get('episode_type')
					listitem = kodi_utils.make_listitem()
					listitem.addContextMenuItems(cm)
					listitem.setProperties(props)
					listitem.setLabel(display)
					listitem.setArt({'poster': show_poster, 'fanart': background, 'thumb': thumb, 'icon': thumb, 'banner': banner, 'clearart': clearart, 'clearlogo': clearlogo,
									'landscape': thumb, 'tvshow.poster': show_poster, 'tvshow.clearart': clearart, 'tvshow.clearlogo': clearlogo, 'tvshow.landscape': thumb, 'tvshow.banner': banner})
					if KODI_VERSION < 20:
						listitem.setCast(cast)
						listitem.setUniqueIDs({'imdb': imdb_id, 'tmdb': string(tmdb_id), 'tvdb': string(tvdb_id)})
						listitem.setInfo('video', remove_meta_keys(item, dict_removals))
						listitem.setProperty('resumetime', resumetime)
					else:
						videoinfo = listitem.getVideoInfoTag(offscreen=True)
						videoinfo.setCast(make_cast_list(cast))
						videoinfo.setUniqueIDs({'imdb': imdb_id, 'tmdb': string(tmdb_id), 'tvdb': string(tvdb_id)})
						videoinfo.setDirectors(item_get('director').split(', '))
						videoinfo.setDuration(int(item_get('duration') or default_duration))
						videoinfo.setEpisode(episode)
						videoinfo.setFirstAired(premiered)
						videoinfo.setGenres(genre.split(', '))
						videoinfo.setIMDBNumber(imdb_id)
						videoinfo.setMediaType('episode')
						videoinfo.setMpaa(mpaa)
						videoinfo.setPlaycount(playcount)
						videoinfo.setPlot(item_get('plot'))
						videoinfo.setRating(item_get('rating'))
						videoinfo.setSeason(season)
						videoinfo.setStudios((studio,))
						videoinfo.setTitle(item_get('title'))
						videoinfo.setTrailer(trailer)
						videoinfo.setTvShowStatus(show_status)
						videoinfo.setTvShowTitle(show_title)
						videoinfo.setVotes(item_get('votes'))
						videoinfo.setWriters(item_get('writer').split(', '))
						videoinfo.setYear(int(year))
						if int(progress):
							listitem.setProperty('watchedprogress', progress)
							videoinfo.setResumePoint(*set_resumetime(resumetime, progress, videoinfo.getDuration()))
					self.append((url_params, listitem, False))
				except: pass
		meta = tv_meta_function('tmdb_id', params['tmdb_id'], self.meta_user_info, self.current_date)
		meta_get = meta.get
		tmdb_id, tvdb_id, imdb_id = meta_get('tmdb_id'), meta_get('tvdb_id'), meta_get('imdb_id')
		rootname, show_status = meta_get('rootname'), meta_get('status')
		show_title, show_year, show_plot = meta_get('title'), meta_get('year'), meta_get('plot')
		show_poster = meta_get(self.poster_main) or meta_get(self.poster_backup) or poster_empty
		fanart = meta_get(self.fanart_main) or meta_get(self.fanart_backup) or fanart_empty
		clearlogo = meta_get('clearlogo') or meta_get('tmdblogo') or ''
		if self.fanart_enabled: banner, clearart, landscape = meta_get('banner'), meta_get('clearart'), meta_get('landscape')
		else: banner, clearart, landscape = '', '', ''
		show_cast, mpaa, votes = meta_get('cast', []), meta_get('mpaa'), meta_get('votes')
		trailer, genre, studio = string(meta_get('trailer')), meta_get('genre'), meta_get('studio')
		episode_run_time, rating, premiered = meta_get('duration'), meta_get('rating'), meta_get('premiered')
		total_seasons, total_aired_eps = meta_get('total_seasons'), meta_get('total_aired_eps')
		mode = self.params.get('mode', 'build_season_list')
		if 'episode' in mode: _process_episode_list()
		else: _process_season_list()
		self.params['show_title'] = show_title
		return self.items

	def run(self):
		__handle__, is_widget = int(sys.argv[1]), kodi_utils.external_browse()
		mode = self.params.get('mode', 'build_season_list')
		if 'episode' in mode: content_type, view_type = 'episodes', 'view.episodes'
		else: content_type, view_type = 'seasons', 'view.seasons'
		kodi_utils.add_items(__handle__, self.build_season_list(self.params))
		kodi_utils.set_category(__handle__, self.params.get('show_title'))
		kodi_utils.set_sort_method(__handle__, content_type)
		kodi_utils.set_content(__handle__, content_type)
		kodi_utils.end_directory(__handle__, False if is_widget else None)
		kodi_utils.set_view_mode(view_type, content_type)

