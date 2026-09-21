# -*- coding: utf-8 -*-
"""Playback Stop remotes: local SQLite is written on the player; HTTP runs here.

The player invoker tears down on Stop, so Trakt/Simkl/MDBList/PunchPlay/WeTrakr
must not run on a daemon thread there (Playing now used to stick). The service
picks JSON jobs from addon_data. No extra UpdateLibrary — Kodi already rebuilds
Home widgets on Stop.
"""
import json
import os
import time
from modules.kodi_utils import (
	addon_profile, make_directories, list_dirs, open_file, delete_file, path_exists,
	logger, service_shutting_down, mark_playback_widget_refresh
)

QUEUE_SUBDIR = 'playback_remote'

def _queue_dir():
	folder = os.path.join(addon_profile(), QUEUE_SUBDIR)
	if not folder.endswith(os.sep) and not folder.endswith('/'):
		folder = folder + os.sep
	make_directories(folder)
	return folder

def enqueue_playback_job(job):
	try:
		if not job: return
		folder = _queue_dir()
		name = '%s_%s.json' % (int(time.time() * 1000), os.getpid())
		path = folder + name
		payload = json.dumps(job, separators=(',', ':'), default=str)
		f = open_file(path, 'w')
		try: f.write(payload)
		finally: f.close()
	except Exception as e:
		try: logger('Red Light', 'playback remote enqueue failed: %s' % e)
		except: pass

def apply_local_watched(params):
	"""Insert watched + drop local resume. No HTTP, no widget UpdateLibrary."""
	from modules import watched_status as ws, settings
	action = params.get('action') or 'mark_as_watched'
	media_type = params.get('media_type') or ('episode' if params.get('season') not in (None, '') else 'movie')
	tmdb_id, title = params.get('tmdb_id'), params.get('title')
	season, episode = params.get('season'), params.get('episode')
	if media_type == 'episode':
		try:
			if int(season) == 0: return None
		except: return None
	watched_indicators = settings.watched_indicators()
	resume_id = ws.progress_resume_id(media_type, tmdb_id, season, episode, watched_indicators)
	ws.watched_status_mark(watched_indicators, media_type, tmdb_id, action, season, episode, title, remote=False)
	ws._arm_provider_list_sync_skip(watched_indicators)
	mark_playback_widget_refresh()
	return resume_id

def apply_local_progress(params):
	"""Write resume locally. No HTTP, no widget UpdateLibrary."""
	from modules import watched_status as ws
	ws.set_bookmark(params, remote=False)
	mark_playback_widget_refresh()

def _iter_job_paths():
	folder = _queue_dir()
	try:
		_dirs, files = list_dirs(folder)
	except:
		return
	for name in sorted(files or []):
		if not name.endswith('.json'): continue
		yield folder + name

def take_jobs():
	jobs = []
	for path in _iter_job_paths():
		raw = None
		try:
			f = open_file(path, 'r')
			try: raw = f.read()
			finally: f.close()
			delete_file(path)
			if not raw: continue
			job = json.loads(raw)
			if isinstance(job, dict): jobs.append(job)
		except Exception as e:
			try: logger('Red Light', 'playback remote job skipped (%s): %s' % (path, e))
			except: pass
			try:
				if path_exists(path): delete_file(path)
			except: pass
	return jobs

def process_pending_jobs(monitor=None, force=False):
	if not force and service_shutting_down(monitor): return
	jobs = take_jobs()
	for job in jobs:
		if not force and service_shutting_down(monitor):
			enqueue_playback_job(job)
			return
		try:
			_process_job(job)
		except Exception as e:
			try: logger('Red Light', 'playback remote job failed: %s' % e)
			except: pass

def _process_job(job):
	op = job.get('op')
	percent = job.get('percent') or 0
	try: percent = float(percent)
	except: percent = 0
	if percent < 1 and job.get('scrobble_stop'): percent = 1
	if job.get('scrobble_stop'):
		_scrobble_stop(job, percent)
	_wetrakr(job)
	if op == 'watched':
		_remote_watched(job)
		_remote_clear_progress(job)
		_remote_undrop(job)
	elif op == 'progress':
		_remote_progress(job)

def _scrobble_stop(job, percent):
	from modules import settings as st
	media_type = job.get('media_type')
	tmdb_id, season, episode = job.get('tmdb_id'), job.get('season'), job.get('episode')
	indicators = st.watched_indicators()
	if indicators == 1 and st.trakt_user_active():
		from apis.trakt_api import trakt_scrobble, trakt_official_status
		if trakt_official_status(media_type):
			trakt_scrobble('stop', media_type, tmdb_id, percent, season, episode)
	elif indicators == 2 and st.simkl_user_active():
		from apis.simkl_api import simkl_scrobble, simkl_official_status
		if simkl_official_status(media_type):
			simkl_scrobble('stop', media_type, tmdb_id, percent, season, episode)
	elif indicators == 4 and st.punchplay_user_active():
		from apis.punchplay_api import punchplay_scrobble, punchplay_official_status
		if punchplay_official_status(media_type):
			punchplay_scrobble('stop', media_type, tmdb_id, percent, season, episode,
				title=job.get('title') or '', year=job.get('year'),
				session_id=job.get('punchplay_session_id'))

def _wetrakr(job):
	event = job.get('wetrakr_event')
	if not event: return
	from modules import settings as st
	if not st.wetrakr_user_active(): return
	from apis.wetrakr_api import wetrakr_should_scrobble, wetrakr_send_event
	if not wetrakr_should_scrobble(): return
	kwargs = job.get('wetrakr_kwargs') or {}
	wetrakr_send_event(event, job.get('media_type'), **kwargs)

def _remote_watched(job):
	from modules import settings as st
	action = job.get('action') or 'mark_as_watched'
	media_type = job.get('media_type')
	tmdb_id, title = job.get('tmdb_id'), job.get('title')
	season, episode, tvdb_id = job.get('season'), job.get('episode'), job.get('tvdb_id') or 0
	year = job.get('year')
	indicators = st.watched_indicators()
	if indicators == 1:
		from apis.trakt_api import trakt_watched_status_mark, trakt_official_status
		from caches.trakt_cache import clear_trakt_collection_watchlist_data
		if trakt_official_status(media_type):
			if media_type == 'movie': trakt_watched_status_mark(action, 'movies', tmdb_id)
			else: trakt_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode)
		clear_trakt_collection_watchlist_data('watchlist', 'tvshow' if media_type == 'episode' else media_type)
	elif indicators == 2:
		from apis.simkl_api import simkl_watched_status_mark, simkl_official_status
		if simkl_official_status(media_type):
			if media_type == 'movie': simkl_watched_status_mark(action, 'movie', tmdb_id)
			else: simkl_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode)
	elif indicators == 3:
		from apis.mdblist_api import mdblist_watched_status_mark, mdblist_official_status
		if mdblist_official_status(media_type):
			if media_type == 'movie': mdblist_watched_status_mark(action, 'movie', tmdb_id)
			else: mdblist_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode)
	elif indicators == 4:
		from apis.punchplay_api import punchplay_watched_status_mark, punchplay_official_status
		if punchplay_official_status(media_type):
			if media_type == 'movie':
				punchplay_watched_status_mark(action, 'movie', tmdb_id, title=title, year=year)
			else:
				punchplay_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode, title=title, year=year)

def _remote_clear_progress(job):
	resume_id = job.get('resume_id')
	if resume_id in (None, '', 0, '0'): return
	from modules import settings as st
	media_type, media_id = job.get('media_type'), job.get('tmdb_id')
	season, episode = job.get('season'), job.get('episode')
	indicators = st.watched_indicators()
	try:
		if indicators == 1:
			from apis.trakt_api import trakt_progress
			trakt_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
		elif indicators == 2:
			from apis.simkl_api import simkl_progress
			simkl_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
		elif indicators == 3:
			from apis.mdblist_api import mdblist_progress
			mdblist_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
		elif indicators == 4:
			from apis.punchplay_api import punchplay_progress
			punchplay_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
	except: pass

def _remote_undrop(job):
	if job.get('media_type') != 'episode': return
	from modules import watched_status as ws
	try: ws.update_hidden_progress(job.get('tmdb_id'))
	except: pass

def _remote_progress(job):
	from modules import settings as st
	from apis.trakt_api import trakt_official_status, trakt_progress
	from apis.simkl_api import simkl_official_status, simkl_progress
	from apis.mdblist_api import mdblist_official_status, mdblist_progress
	from apis.punchplay_api import punchplay_official_status, punchplay_progress
	media_type, tmdb_id = job.get('media_type'), job.get('tmdb_id')
	season, episode = job.get('season'), job.get('episode')
	curr_time, total_time = job.get('curr_time'), job.get('total_time')
	try:
		adjusted_current_time = float(curr_time) - 5
		resume_point = round(adjusted_current_time / float(total_time) * 100, 1)
	except:
		return
	indicators = st.watched_indicators()
	if indicators == 1 and trakt_official_status(media_type):
		trakt_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_trakt=False)
	elif indicators == 2 and simkl_official_status(media_type):
		simkl_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_simkl=False)
	elif indicators == 3 and mdblist_official_status(media_type):
		mdblist_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_mdblist=False)
	elif indicators == 4 and punchplay_official_status(media_type):
		punchplay_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_punchplay=False)
