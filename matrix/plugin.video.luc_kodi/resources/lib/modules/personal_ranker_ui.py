# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Personal Ranker UI

	Renderiza el estado del modelo de ranking personalizado en una ventana
	TextViewer y gestiona la confirmación del reset.

	No contiene lógica del modelo — solo lectura de get_stats() y formato
	para mostrar al usuario.
"""

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.windows.textviewer import TextViewerXML
from resources.lib.database import source_ranker

LOGINFO = log_utils.LOGINFO

# Human-readable labels per feature type
_TYPE_LABELS = {
	'quality':  'Quality',
	'codec':    'Codec',
	'hdr':      'HDR',
	'audio':    'Audio',
	'provider': 'Provider',
	'debrid':   'Debrid',
	'size':     'Size',
	'seeders':  'Seeders',
}


def _format_stats(stats):
	"""Convert stats into BBCode text blocks for the textviewer."""
	total = stats.get('total_plays', 0)
	feats = stats.get('features', [])

	lines = []
	add = lines.append

	add('[B][COLOR ff00fa9a]Personal ranker · summary[/COLOR][/B]')
	add('')
	if total == 0:
		add('[COLOR ffaaaaaa]No data yet. The model learns from the sources '
			'you actually play.[/COLOR]')
		add('')
		add('Once you reach 10 plays it will start influencing the order.')
		return '[CR]'.join(lines)

	add('[COLOR ffaaaaaa]Plays recorded:[/COLOR] [B]%d[/B]' % total)
	if total < 10:
		add('[COLOR ffd25c1d]At least 10 plays are needed before the model '
			'affects ranking. %d to go.[/COLOR]' % (10 - total))
	add('')

	# Group by feature type
	by_type = {}
	for f in feats:
		by_type.setdefault(f['type'], []).append(f)

	# Fixed type order for consistent readability
	type_order = ['quality', 'codec', 'hdr', 'audio', 'provider', 'debrid', 'size', 'seeders']

	for ftype in type_order:
		group = by_type.get(ftype) or []
		if not group:
			continue
		label = _TYPE_LABELS.get(ftype, ftype)
		add('[B][COLOR fffdb515]%s[/COLOR][/B]' % label)
		# Each feature: name, hits/exposures, win-rate, log-odds with color
		for f in group:
			lo = f['log_odds']
			# Green for positive preferences, red for negative, gray for neutral
			if   lo >  0.30: color = 'ff00fa9a'
			elif lo < -0.30: color = 'ffd25c1d'
			else:            color = 'ffaaaaaa'
			sign = '+' if lo >= 0 else ''
			add('  %-12s  picked %3d / shown %3d   '
				'[COLOR %s]%s%.2f[/COLOR]' %
				(f['value'], f['pos'], f['exp'], color, sign, lo))
		add('')

	add('[COLOR ffaaaaaa]How to read this:[/COLOR]')
	add('· [B]picked[/B] = times you chose a source with that feature')
	add('· [B]shown[/B] = times it appeared in the candidate list')
	add('· [B]log-odds[/B] = weight applied to ranking. Green = boosts up, red = pushes down.')
	return '[CR]'.join(lines)


def show_stats():
	"""Show the model state in a TextViewer."""
	try:
		stats = source_ranker.get_stats()
		text = _format_stats(stats)
		viewer = TextViewerXML(
			'textviewer.xml',
			control.addonPath('plugin.video.luc_kodi'),
			heading='Personal ranker',
			text=text,
		)
		viewer.run()
		del viewer
	except Exception:
		log_utils.error()
		try:
			control.notification(
				title='luc_kodi',
				message='Error displaying ranker stats',
				time=4000,
			)
		except Exception:
			pass


def reset_with_confirm():
	"""Ask for confirmation and wipe the model if user accepts."""
	try:
		ok = control.yesnoDialog(
			line1='Reset the personal ranker model?',
			line2='All learned preferences will be lost.',
			line3='This action cannot be undone.',
			heading='luc_kodi · Personal ranker',
			nolabel='Cancel',
			yeslabel='Reset',
		)
		if not ok:
			return
		if source_ranker.reset():
			control.notification(
				title='luc_kodi',
				message='Personal ranker reset',
				time=3000,
			)
			control.log('[ plugin.video.luc_kodi ]  Personal ranker reset by user', LOGINFO)
		else:
			control.notification(
				title='luc_kodi',
				message='Could not reset the ranker',
				time=4000,
			)
	except Exception:
		log_utils.error()
