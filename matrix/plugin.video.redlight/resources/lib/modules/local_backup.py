# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from caches.base_cache import connect_database, make_database
from modules import kodi_utils, settings
from modules.watched_status import get_database

BACKUP_FORMAT = 1
BACKUP_MASK = '.json'
PROGRESS_MIN_PERCENT = 1.0

_EXTERNAL_PROGRESS_PROVIDERS = {1: 'Trakt', 2: 'Simkl'}


def _external_progress_provider_name():
	return _EXTERNAL_PROGRESS_PROVIDERS.get(settings.watched_indicators())


def _progress_not_included_message():
	provider = _external_progress_provider_name()
	if not provider:
		return None
	return 'Progress not included[CR](%s Indicators)' % provider


def _default_backup_dir():
	return settings.import_export_directory()

def _pick_import_file(default_dir):
	path = kodi_utils.browse_file(BACKUP_MASK, default_dir)
	if not path:
		return None
	tpath = kodi_utils.translate_path(path)
	if not os.path.isfile(tpath):
		return None
	if not tpath.lower().endswith('.json'):
		kodi_utils.ok_dialog(heading='Red Light import', text='Please select a Red Light backup (.json) file.')
		return None
	return tpath


def _pick_export_folder(default_dir):
	folder = kodi_utils.browse_directory(default_dir)
	if not folder:
		return None
	tfolder = kodi_utils.translate_path(folder)
	if not os.path.isdir(tfolder):
		return None
	return tfolder


def export_data(params):
	payload, counts = _build_export_payload()
	if not payload:
		return kodi_utils.ok_dialog(heading='Red Light export', text='Nothing to export — no Red Light favorites or in-progress resume data on this device.')
	default_dir = _default_backup_dir()
	folder = _pick_export_folder(default_dir)
	if not folder:
		return
	filename = 'redlight-backup-%s.json' % datetime.now().strftime('%Y%m%d-%H%M%S')
	path = os.path.join(folder, filename)
	preview = _export_preview_text(filename, counts)
	if not kodi_utils.confirm_dialog(heading='Red Light export preview', text=preview, ok_label='Export', cancel_label='Cancel', default_control=10, scroll=True):
		return
	try:
		kodi_utils.make_directory(folder)
		with open(path, 'w', encoding='utf-8') as handle:
			json.dump(payload, handle, indent=2, ensure_ascii=False)
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Red Light export failed', text=str(e))
	summary = _export_summary(counts, filename)
	kodi_utils.ok_dialog(heading='Red Light export complete', text=summary.replace('; ', '[CR]'), scroll=True)
	kodi_utils.notification(summary, 6500)


def import_data(params):
	default_dir = _default_backup_dir()
	path = _pick_import_file(default_dir)
	if not path:
		return
	try:
		with open(path, 'r', encoding='utf-8') as handle:
			payload = json.load(handle)
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Red Light import failed', text='Could not read backup file.[CR][CR]%s' % e)
	file_stats = _payload_stats(payload)
	if not file_stats['favorites'] and not file_stats['progress']:
		return kodi_utils.ok_dialog(heading='Red Light import', text='This backup file contains no Red Light favorites or progress data.')
	local_stats = _local_stats()
	preview = _preview_text(path, payload, file_stats, local_stats)
	if not kodi_utils.confirm_dialog(heading='Red Light import preview', text=preview, ok_label='Continue', cancel_label='Cancel', default_control=10, scroll=True):
		return
	mode_choices = [
		('Merge — combine with this device; furthest watch position wins', 'merge'),
		('Replace — overwrite local favorites and progress with the backup', 'replace'),
	]
	list_items = [{'line1': i[0]} for i in mode_choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Red Light import mode', 'narrow_window': 'true'}
	mode = kodi_utils.select_dialog([i[1] for i in mode_choices], **kwargs)
	if not mode:
		return
	rules = _import_rules_text(mode, file_stats)
	if not kodi_utils.confirm_dialog(heading='Confirm Red Light import (%s)' % mode.capitalize(), text=rules, ok_label='Import', cancel_label='Cancel', default_control=10, scroll=True):
		return
	if mode == 'replace' and (file_stats['favorites'] or file_stats['progress']):
		warn = 'Local Red Light favorites and progress will be replaced by this backup.'
		if not kodi_utils.confirm_dialog(heading='Replace Red Light data?', text=warn, ok_label='Replace', cancel_label='Cancel', default_control=10):
			return
	try:
		make_database('favorites_db')
		make_database('watched_db')
		summary = _apply_import(payload, mode, file_stats)
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Red Light import failed', text=str(e))
	kodi_utils.ok_dialog(heading='Red Light import complete', text=summary.replace('; ', '[CR]'), scroll=True)
	kodi_utils.notification(summary, 6500)
	kodi_utils.kodi_refresh()


def _addon_version():
	try:
		return kodi_utils.addon_info('version') or ''
	except:
		return ''


def _build_export_payload():
	favorites = _export_favorites()
	progress = _export_progress()
	counts = {'favorites': len(favorites), 'progress': len(progress)}
	if not counts['favorites'] and not counts['progress']:
		return None, counts
	payload = {
		'format': BACKUP_FORMAT,
		'addon_version': _addon_version(),
		'exported': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
	}
	if favorites:
		payload['favorites'] = favorites
	if progress:
		payload['progress'] = progress
	return payload, counts


def _export_favorites():
	dbcon = connect_database('favorites_db')
	try:
		rows = dbcon.execute('SELECT db_type, tmdb_id, title FROM favourites ORDER BY db_type, title').fetchall()
	except:
		rows = []
	return [{'db_type': str(i[0]), 'tmdb_id': str(i[1]), 'title': str(i[2])} for i in rows]


def _export_progress():
	if settings.watched_indicators() != 0:
		return []
	dbcon = get_database(0)
	try:
		rows = dbcon.execute(
			'SELECT db_type, media_id, season, episode, resume_point, curr_time, last_played, resume_id, title FROM progress'
		).fetchall()
	except:
		rows = []
	result = []
	for row in rows:
		if float(row[4] or 0) <= PROGRESS_MIN_PERCENT:
			continue
		result.append(_progress_row_to_dict(row))
	return result


def _progress_row_to_dict(row):
	return {
		'db_type': str(row[0]),
		'media_id': str(row[1]),
		'season': row[2],
		'episode': row[3],
		'resume_point': str(row[4]),
		'curr_time': str(row[5]),
		'last_played': str(row[6] or ''),
		'resume_id': int(row[7] or 0),
		'title': str(row[8] or ''),
	}


def _payload_stats(payload):
	if not isinstance(payload, dict):
		return {'favorites': 0, 'progress': 0, 'fav_keys': set(), 'progress_keys': set()}
	favorites = payload.get('favorites') if isinstance(payload.get('favorites'), list) else []
	progress = payload.get('progress') if isinstance(payload.get('progress'), list) else []
	return {
		'favorites': len(favorites),
		'progress': len(progress),
		'fav_keys': {_favorite_key(i) for i in favorites if _favorite_key(i)},
		'progress_keys': {_progress_key(i) for i in progress if _progress_key(i)},
	}


def _local_stats():
	favorites = _export_favorites()
	progress = _export_progress() if settings.watched_indicators() == 0 else []
	return {
		'favorites': len(favorites),
		'progress': len(progress),
		'fav_keys': {_favorite_key(i) for i in favorites},
		'progress_keys': {_progress_key(i) for i in progress},
	}


def _favorite_key(item):
	try:
		return (str(item['db_type']), str(item['tmdb_id']))
	except:
		return None


def _progress_key(item):
	try:
		return (str(item['db_type']), str(item['media_id']), int(item.get('season') or 0), int(item.get('episode') or 0))
	except:
		return None


def _preview_text(path, payload, file_stats, local_stats):
	name = os.path.basename(path)
	lines = [
		'[B]%s[/B]' % name,
		'Red Light %s' % (payload.get('addon_version') or 'unknown'),
		'',
		'Backup: %s favorite(s), %s progress' % (file_stats['favorites'], file_stats['progress']),
		'Device: %s favorite(s), %s progress' % (local_stats['favorites'], local_stats['progress']),
	]
	fav_overlap = len(file_stats['fav_keys'] & local_stats['fav_keys'])
	prog_overlap = len(file_stats['progress_keys'] & local_stats['progress_keys'])
	overlap_parts = []
	if file_stats['favorites'] and local_stats['favorites'] and fav_overlap:
		overlap_parts.append('%s favorite' % fav_overlap)
	if file_stats['progress'] and local_stats['progress'] and prog_overlap:
		overlap_parts.append('%s progress' % prog_overlap)
	if overlap_parts:
		lines.append('Overlap: %s' % ', '.join(overlap_parts))
	if file_stats['progress'] and settings.watched_indicators() != 0:
		lines.append('[COLOR yellow]Progress in backup will not be imported[CR](%s Indicators)[/COLOR]' % _external_progress_provider_name())
	return '[CR]'.join(lines)


def _export_preview_text(filename, counts):
	lines = [
		'[B]%s[/B]' % filename,
		'Red Light %s' % _addon_version(),
		'',
		'Export: %s favorite(s), %s progress' % (counts['favorites'], counts['progress']),
	]
	msg = _progress_not_included_message()
	if msg:
		lines.append('[COLOR yellow]%s[/COLOR]' % msg)
	return '[CR]'.join(lines)


def _export_summary(counts, filename):
	parts = []
	if counts['favorites']:
		parts.append('%s favorite(s)' % counts['favorites'])
	if counts['progress']:
		parts.append('%s progress row(s)' % counts['progress'])
	return 'Exported %s to %s' % (' and '.join(parts), filename)


def _import_rules_text(mode, file_stats):
	lines = []
	if file_stats['favorites']:
		if mode == 'merge':
			lines.extend([
				'[B]Favorites — merge[/B]',
				'• Add or update favorites from the backup.',
				'• Favorites on this device that are not in the backup are kept.',
			])
		else:
			lines.extend([
				'[B]Favorites — replace[/B]',
				'• Remove all local favorites, then import from the backup.',
			])
	if file_stats['progress'] and settings.watched_indicators() == 0:
		if mode == 'merge':
			lines.extend([
				'[B]Progress — merge[/B]',
				'• Add or update progress from the backup.',
				'• For the same title and episode, keep whichever is further along.',
				'• Progress on this device that is not in the backup is kept.',
			])
		else:
			lines.extend([
				'[B]Progress — replace[/B]',
				'• Remove all local progress, then import from the backup.',
			])
	elif file_stats['progress'] and settings.watched_indicators() != 0:
		lines.append('[B]Progress[/B]: not imported[CR](%s Indicators)' % _external_progress_provider_name())
	return '[CR]'.join(lines) if lines else 'Nothing to import.'


def _apply_import(payload, mode, file_stats):
	summary_parts = []
	if file_stats['favorites']:
		summary_parts.append(_import_favorites(payload.get('favorites') or [], mode))
	if file_stats['progress'] and settings.watched_indicators() == 0:
		summary_parts.append(_import_progress(payload.get('progress') or [], mode))
	elif file_stats['progress']:
		summary_parts.append('Progress skipped (%s Indicators)' % _external_progress_provider_name())
	return 'Import complete — %s' % '; '.join([i for i in summary_parts if i])


def _import_favorites(items, mode):
	dbcon = connect_database('favorites_db')
	if mode == 'replace':
		dbcon.execute('DELETE FROM favourites')
	added, updated = 0, 0
	for item in items:
		key = _favorite_key(item)
		if not key:
			continue
		exists = dbcon.execute('SELECT 1 FROM favourites WHERE db_type=? AND tmdb_id=?', key).fetchone()
		dbcon.execute('INSERT OR REPLACE INTO favourites VALUES (?, ?, ?)', (key[0], key[1], str(item.get('title') or '')))
		if exists:
			updated += 1
		else:
			added += 1
	return 'favorites: %s added, %s updated' % (added, updated)


def _import_progress(items, mode):
	dbcon = get_database(0)
	local = {}
	try:
		for row in dbcon.execute('SELECT db_type, media_id, season, episode, resume_point, curr_time, last_played, resume_id, title FROM progress').fetchall():
			key = (str(row[0]), str(row[1]), int(row[2] or 0), int(row[3] or 0))
			local[key] = _progress_row_to_dict(row)
	except:
		pass
	if mode == 'replace':
		dbcon.execute('DELETE FROM progress')
		local = {}
	added, updated, kept = 0, 0, 0
	for item in items:
		key = _progress_key(item)
		if not key:
			continue
		winner = _merge_progress_row(local.get(key), item) if mode == 'merge' and key in local else item
		if key in local and mode == 'merge':
			if winner is local.get(key):
				kept += 1
				continue
			updated += 1
		else:
			added += 1
		dbcon.execute(
			'INSERT OR REPLACE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
			(
				winner['db_type'], winner['media_id'], winner.get('season'), winner.get('episode'),
				str(winner.get('resume_point', '0')), str(winner.get('curr_time', '0')),
				str(winner.get('last_played') or ''), int(winner.get('resume_id') or 0), str(winner.get('title') or ''),
			)
		)
	return 'progress: %s added, %s updated, %s unchanged' % (added, updated, kept)


def _merge_progress_row(local, incoming):
	if not local:
		return incoming
	local_time = float(local.get('curr_time') or 0)
	incoming_time = float(incoming.get('curr_time') or 0)
	if incoming_time > local_time:
		return incoming
	if local_time > incoming_time:
		return local
	local_pct = float(local.get('resume_point') or 0)
	incoming_pct = float(incoming.get('resume_point') or 0)
	if incoming_pct > local_pct:
		return incoming
	if local_pct > incoming_pct:
		return local
	if str(incoming.get('last_played') or '') > str(local.get('last_played') or ''):
		return incoming
	return local
