# -*- coding: utf-8 -*-
# Dispatches watched-tracking operations to the active provider selected by
# settings.tracking_provider():
#   'builtin' -> local watched-status only, no external sync
#   'trakt'   -> apis.trakt_api
#   'simkl'   -> apis.simkl_api
from modules import settings
# from modules.kodi_utils import logger

def provider():
	return settings.tracking_provider()

def is_external():
	return provider() in ('trakt', 'simkl')

#=========================== READ / SYNC ===========================#
def sync_activities(force_update=False):
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_sync_activities
		return trakt_sync_activities(force_update)
	if p == 'simkl':
		from apis.simkl_api import simkl_sync_activities
		return simkl_sync_activities(force_update)
	return 'no account'

def indicators_movies():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_indicators_movies
		return trakt_indicators_movies()
	if p == 'simkl':
		from apis.simkl_api import simkl_indicators_movies
		return simkl_indicators_movies()

def indicators_tv():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_indicators_tv
		return trakt_indicators_tv()
	if p == 'simkl':
		from apis.simkl_api import simkl_indicators_tv
		return simkl_indicators_tv()

def playback_progress():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_playback_progress
		return trakt_playback_progress()
	if p == 'simkl':
		from apis.simkl_api import simkl_playback_progress
		return simkl_playback_progress()
	return []

#=========================== WRITE ===========================#
def mark_watched(action, media, media_id, tvdb_id=0, season=None, episode=None, key='tmdb'):
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_watched_status_mark
		return trakt_watched_status_mark(action, media, media_id, tvdb_id, season, episode, key)
	if p == 'simkl':
		from apis.simkl_api import simkl_mark_watched
		return simkl_mark_watched(action, media, media_id, tvdb_id, season, episode, key)
	return True

def scrobble(action, media, media_id, percent, season=None, episode=None, resume_id=None, refresh_tracker=False):
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_progress
		return trakt_progress(action, media, media_id, percent, season, episode, resume_id, refresh_tracker)
	if p == 'simkl':
		from apis.simkl_api import simkl_progress
		return simkl_progress(action, media, media_id, percent, season, episode, resume_id, refresh_tracker)

# alias kept for readability at older call sites
progress = scrobble

def official_status(media_type):
	# True == FenLight should perform its own scrobble/mark; False == an external scrobbler owns it.
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_official_status
		return trakt_official_status(media_type)
	if p == 'simkl':
		from apis.simkl_api import simkl_official_status
		return simkl_official_status(media_type)
	return True

def clear_watchlist_data(list_type, media_type):
	p = provider()
	if p == 'trakt':
		from caches.trakt_cache import clear_trakt_collection_watchlist_data
		return clear_trakt_collection_watchlist_data(list_type, media_type)
	if p == 'simkl':
		from caches.simkl_cache import clear_simkl_status_data
		return clear_simkl_status_data()

def get_hidden_items(list_type):
	if provider() == 'trakt':
		from apis.trakt_api import trakt_get_hidden_items
		return trakt_get_hidden_items(list_type)
	return None

def get_my_calendar(recently_aired, current_date):
	if provider() == 'simkl':
		from apis.simkl_api import simkl_get_my_calendar
		return simkl_get_my_calendar(recently_aired, current_date)
	from apis.trakt_api import trakt_get_my_calendar
	return trakt_get_my_calendar(recently_aired, current_date)

def watchlist_shows():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_watchlist
		return trakt_watchlist('watchlist', 'tvshow')
	if p == 'simkl':
		from apis.simkl_api import simkl_status_list
		return simkl_status_list('plantowatch', 'tvshow')
	return []
