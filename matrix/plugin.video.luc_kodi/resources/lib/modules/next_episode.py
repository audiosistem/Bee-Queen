# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — next_episode.py (v1.0.90)

	Decide cual es de verdad el siguiente episodio despues de uno visto.

	Hasta la 1.0.89 el dialogo de siguiente episodio hacia `episode + 1` en
	la misma temporada sin consultar nada. En un final de temporada ofrecia
	un SxxE11 que no existe (scrape completo para acabar en "no streams") y
	en series en emision ofrecia el episodio de la semana que viene.

	Reglas (las mismas que aplica TMDb Movies, sobre datos que luc_kodi ya
	pide a TMDb):
	  1. Si el episodio siguiente existe en la temporada actual y su fecha de
	     emision ya ha pasado, es ese.
	  2. Si existe pero su fecha es futura o no tiene fecha, NO hay siguiente
	     (todavia no se puede ver).
	  3. Si la temporada se ha acabado, se mira la temporada siguiente,
	     episodio 1, con la misma regla de fecha.
	  4. Si no hay temporada siguiente, se ha acabado la serie.
	Si TMDb no responde (red caida, sin id de TMDb), se conserva el
	comportamiento de siempre (`episode + 1`), para no quitar el dialogo a
	nadie por un fallo de red.

	La temporada se cachea 12 horas en la base `cache` en forma compacta
	(numero de episodio y fecha), no el JSON entero de TMDb.
"""

from datetime import date

from resources.lib.database import cache
from resources.lib.modules import log_utils

LEGACY, AIRED, UNAIRED, ENDED = 'legacy', 'aired', 'unaired', 'ended'


def _season_compact(tmdb, season):
	"""Episodios de la temporada como lista [numero, 'YYYY-MM-DD' o ''].
	Devuelve {'status': 'missing'} si TMDb dice 404 (la temporada no existe)
	y None si no se pudo preguntar (no se cachea)."""
	from resources.lib.indexers import tmdb as tmdb_indexer
	result = tmdb_indexer.TVshows().get_season_request(tmdb, season)
	if result == '404:NOT FOUND':
		return {'status': 'missing', 'episodes': []}
	if not isinstance(result, dict):
		return None
	eps = []
	for ep in result.get('episodes') or []:
		try:
			eps.append([int(ep.get('episode_number')), str(ep.get('air_date') or '')])
		except Exception:
			pass
	if not eps:
		return {'status': 'missing', 'episodes': []}
	return {'status': 'ok', 'episodes': eps}


def _get_season(tmdb, season):
	try:
		return cache.get(_season_compact, 12, str(tmdb), str(season))
	except Exception:
		log_utils.error()
		return None


def _aired(air_date, today):
	try:
		y, m, d = [int(x) for x in str(air_date).split('-')[:3]]
		return date(y, m, d) <= today
	except Exception:
		return False


def _pick(data, number, today):
	"""(estado, encontrado) para el episodio `number` dentro de `data`."""
	for num, air in data.get('episodes') or []:
		if num == number:
			return (AIRED if _aired(air, today) else UNAIRED), True
	return None, False


def resolve(tmdb, season, episode, today=None):
	"""Devuelve (estado, temporada, episodio).
	estado: AIRED (hay siguiente y se puede ver), UNAIRED (existe pero no se
	ha emitido), ENDED (no hay nada mas) o LEGACY (no se pudo comprobar:
	se devuelve episode + 1 como siempre)."""
	try:
		season, episode = int(season), int(episode)
	except Exception:
		return LEGACY, season, episode
	legacy = (LEGACY, season, episode + 1)
	if not tmdb:
		return legacy
	today = today or date.today()
	cur = _get_season(tmdb, season)
	if cur is None:
		return legacy
	state, found = _pick(cur, episode + 1, today)
	if found:
		return state, season, episode + 1
	nxt = _get_season(tmdb, season + 1)
	if nxt is None:
		return legacy
	if nxt.get('status') != 'ok':
		return ENDED, season, episode
	state, found = _pick(nxt, 1, today)
	if found:
		return state, season + 1, 1
	return ENDED, season, episode
