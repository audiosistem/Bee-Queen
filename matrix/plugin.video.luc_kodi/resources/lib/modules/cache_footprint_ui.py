# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — cache_footprint_ui.py (v1.0.76)

	La cara visible del contador: un informe de lo que ocupa el addon en el
	aparato y la opcion de soltar cada grupo por separado.

	Se separa del modulo de medida a proposito. Medir y borrar tienen que
	poder probarse sin abrir un dialogo, y el dia que esto sea automatico el
	servicio llamara a cache_footprint directamente sin arrastrar interfaz.

	POR GRUPOS Y NO DE GOLPE. Un boton unico de "borrar todo" invita a
	pulsarlo sin leer, y borrar el arte que estas viendo ahora mismo solo
	sirve para volver a bajarlo. Separado, se ve que el fanart es el que pesa
	—hasta 3 MB por imagen frente a 200 KB de un poster— y casi siempre basta
	con soltar ese.
"""

from resources.lib.modules import cache_footprint as fp
from resources.lib.modules import control
from resources.lib.modules import log_utils


def _report():
	art = fp.measure_artwork()
	dbs = fp.measure_databases()
	art_bytes = sum(g['bytes'] for g in art.values())
	db_bytes = sum(dbs.values())

	lines = ['[B]Artwork on disk[/B]']
	if not art:
		lines.append('  nothing cached yet, or the texture cache could not be read')
	for name in sorted(art, key=lambda k: -art[k]['bytes']):
		g = art[name]
		extra = '  (%d with no file)' % g['missing'] if g['missing'] else ''
		lines.append('  %-16s %6s   %d images%s'
		             % (name, fp.human(g['bytes']), g['count'], extra))
	lines.append('  %-16s [B]%s[/B]' % ('total', fp.human(art_bytes)))

	lines.append('')
	lines.append('[B]This add-on\'s own databases[/B]')
	for name in sorted(dbs, key=lambda k: -dbs[k]):
		lines.append('  %-20s %s' % (name, fp.human(dbs[name])))
	if not dbs:
		lines.append('  none found')
	lines.append('  %-20s [B]%s[/B]' % ('total', fp.human(db_bytes)))

	lines.append('')
	lines.append('Artwork is stored by Kodi and it never clears it by itself. '
	             'Deleting a group here removes it through Kodi\'s own API, so '
	             'the database and the files stay in step. Anything deleted is '
	             'fetched again the next time it is shown.')
	return art, '\n'.join(lines)


def show():
	"""Informe + eleccion de que soltar."""
	try:
		art, text = _report()
	except Exception:
		log_utils.error()
		control.notification(message='Could not read the texture cache')
		return

	control.dialog.textviewer('luc_kodi — cache footprint', text)
	if not art:
		return

	names = sorted(art, key=lambda k: -art[k]['bytes'])
	choices = ['%s  (%s, %d images)' % (n, fp.human(art[n]['bytes']), art[n]['count'])
	           for n in names]
	choices.append('Everything above')
	index = control.dialog.select('Delete which group?', choices)
	if index < 0:
		return

	if index == len(names):
		ids = [tid for n in names for tid in art[n]['ids']]
		label = 'all cached artwork'
	else:
		ids = art[names[index]]['ids']
		label = names[index]

	if not control.dialog.yesno(
			'luc_kodi',
			'Delete %d images (%s)?\n\nThey will be downloaded again the next '
			'time they are shown.' % (len(ids), label)):
		return

	progress = control.progressDialog
	try:
		progress.create('luc_kodi', 'Clearing %s...' % label)
		done, failed = fp.purge(ids, progress=progress)
	finally:
		try:
			progress.close()
		except Exception:
			pass

	if failed:
		control.notification(message='Removed %d, %d could not be removed' % (done, failed))
	else:
		control.notification(message='Removed %d images' % done)
