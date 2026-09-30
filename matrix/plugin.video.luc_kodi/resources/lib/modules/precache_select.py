# -*- coding: utf-8 -*-
"""
luc_kodi - Selección de plataformas/cadenas a precachear (v1.0.80)

Movies > Streaming y TV shows > Networks son listas discover de TMDb como
cualquier otra, pero hasta la 1.0.79 eran las únicas que NO entraban en el
precache de arranque: abrir uno de esos widgets en frío costaba 1 discover +
~20 fichas de detalle, cada vez.

Precachearlas todas no tiene sentido (25 plataformas y 100+ cadenas), así que
el usuario marca las que de verdad usa y solo esas entran en el ciclo. La
selección se guarda en un setting oculto como lista separada por comas:

    streaming -> 'id:region'  (la región importa: SkyShowtime no existe en US)
    networks  -> 'id'
"""

from __future__ import absolute_import

from resources.lib.modules import control, log_utils
from resources.lib.modules.catalog_updater import (
	S_PRE_STREAM_IDS, S_PRE_NET_IDS, MAX_PRECACHE_PLATFORMS)


def _apply(entries, labels, current_keys, setting_id, heading):
	"""entries: [(key, label)] — key es lo que se guarda, label lo que se ve."""
	preselect = [i for i, (key, _l) in enumerate(entries) if key in current_keys]
	choice = control.multiselectDialog(labels, heading, preselect)
	if choice is None: return  # cancelado: no se toca nada
	if len(choice) > MAX_PRECACHE_PLATFORMS:
		choice = choice[:MAX_PRECACHE_PLATFORMS]
		control.notification(title=32001, message='Only the first %s are precached' % MAX_PRECACHE_PLATFORMS)
	control.setSetting(setting_id, ','.join(entries[i][0] for i in choice))


def streaming():
	try:
		from resources.lib.indexers.tmdb import Movies as TMDbMovies
		curated = TMDbMovies().watchproviders_curated()
		if not curated: return
		entries = [('%s:%s' % (pid, region), name) for name, pid, region in curated]
		current = set((control.setting(S_PRE_STREAM_IDS) or '').split(','))
		_apply(entries, [l for _k, l in entries], current, S_PRE_STREAM_IDS,
			'Streaming platforms to precache (max %s)' % MAX_PRECACHE_PLATFORMS)
	except:
		log_utils.error()


def networks():
	try:
		from resources.lib.indexers.tmdb import TVshows as TMDbTVshows
		curated = TMDbTVshows().get_networks()
		if not curated: return
		entries = [(str(nid), name) for name, nid, _logo in curated]
		from resources.lib.indexers.tmdb import canonical_network_ids
		current = set(canonical_network_ids((control.setting(S_PRE_NET_IDS) or '').split(',')))
		_apply(entries, [l for _k, l in entries], current, S_PRE_NET_IDS,
			'TV networks to precache (max %s)' % MAX_PRECACHE_PLATFORMS)
	except:
		log_utils.error()
