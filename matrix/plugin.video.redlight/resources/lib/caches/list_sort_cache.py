# -*- coding: utf-8 -*-
"""Single home for per-list sort overrides.

Rows exist only when a user has overridden a list. Absence means 'fall through
to the mediatype default'. Cannot live in settings.db: sync_settings() purges
any setting id missing from default_settings().
"""
from caches.base_cache import connect_database

MOVIES, SHOWS = 'movies', 'shows'

_MEDIA_TYPES = {'movie': MOVIES, 'movies': MOVIES, 'show': SHOWS, 'shows': SHOWS, 'tvshow': SHOWS, 'tvshows': SHOWS}


def normalize_media_type(media_type):
	"""'movie'/'movies' -> 'movies'; 'show'/'shows'/'tvshow' -> 'shows'; anything else -> ''."""
	if not media_type: return ''
	return _MEDIA_TYPES.get(str(media_type).lower(), '')


def scope_key(list_key, media_type=None):
	"""Mediatype-split lists get a ':movies'/':shows' suffix. Mixed lists do not."""
	normalized = normalize_media_type(media_type)
	if not normalized: return list_key
	return '%s:%s' % (list_key, normalized)


def get_override(scope):
	try:
		dbcon = connect_database('list_sort_db')
		row = dbcon.execute('SELECT spec FROM list_sort WHERE scope = ?', (scope,)).fetchone()
		if not row: return ''
		return row[0] or ''
	except: return ''


def get_all_overrides():
	try:
		dbcon = connect_database('list_sort_db')
		rows = dbcon.execute('SELECT scope, spec FROM list_sort').fetchall()
		return dict((i[0], i[1] or '') for i in rows)
	except: return {}


def set_override(scope, spec_string):
	try:
		dbcon = connect_database('list_sort_db')
		dbcon.execute('INSERT OR REPLACE INTO list_sort (scope, spec) VALUES (?, ?)', (scope, spec_string))
		return True
	except: return False


def delete_override(scope):
	try:
		dbcon = connect_database('list_sort_db')
		dbcon.execute('DELETE FROM list_sort WHERE scope = ?', (scope,))
		return True
	except: return False
