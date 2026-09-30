# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — modules/ratings.py (v1.0.67)

	Una sola cascada de valoraciones para todo el addon.

	El codigo vivia dentro de source_results._fetch_ratings() y solo servia a
	esa ventana. Al querer las mismas notas en la linea del reproductor habia
	dos caminos: copiarlo —y a partir de ahi arreglar cada fallo dos veces, y
	que la ventana y el reproductor acabasen diciendo cifras distintas de la
	misma pelicula— o sacarlo aqui. Esta aqui.

	La cascada no cambia: cada hueco lo llena la mejor fuente disponible.

	  MDBList   si hay clave, va primero y puede llenarlos todos.
	  TMDb      del propio meta, sin configurar nada.
	  Trakt     endpoint publico con la clave del addon, sin login.
	  OMDB      el hueco de IMDb (con caida a Metacritic), y ademas Rotten
	            Tomatoes y Metacritic por su cuenta si siguen vacios.

	live=False
	----------
	El reproductor NO puede permitirse una peticion. La sinopsis se escribe en
	el instante anterior a arrancar el video, asi que una llamada a OMDB que
	tarde ocho segundos son ocho segundos de pantalla negra por un dato
	decorativo. Con live=False solo se lee lo que ya esta en cache y lo que
	falte, falta.

	Y casi nunca falta, que es lo que hace que la idea funcione: la lista de
	fuentes pidio estas mismas notas medio minuto antes, mientras el usuario
	elegia. Cuando llega la reproduccion la cache esta caliente y la linea sale
	gratis. La primera vez de cada titulo puede salir sin notas; la segunda ya
	no.
"""

from resources.lib.modules import control
from resources.lib.modules import log_utils

# Horas de validez. Iguales a las que ya usaba la ventana de fuentes: las
# notas de una pelicula no se mueven en un dia.
TTL_MDBLIST = 24
TTL_TRAKT   = 24
TTL_OMDB    = 48

_EMPTY = {'tmdb': '', 'trakt': '', 'imdb': '', 'imdb_source': '', 'rt': '',
          'metacritic': ''}


def _omdb_fetch(imdb_id, key):
	try:
		import requests
		r = requests.get('https://www.omdbapi.com/',
		                 params={'i': imdb_id, 'apikey': key}, timeout=8)
		if r.status_code == 200:
			return r.json()
	except Exception:
		pass
	return None


def _cached(live, function, duration, *args):
	"""cache.get pide si hace falta; cache_existing no pide nunca."""
	from resources.lib.database import cache
	if live:
		return cache.get(function, duration, *args)
	return cache.cache_existing(function, *args)


def _num(value, fmt='%.1f'):
	try:
		return fmt % float(value)
	except (ValueError, TypeError):
		return ''


def fetch(meta, live=True):
	"""Devuelve el dict de notas. Nunca lanza: un fallo aqui no puede tumbar
	ni la ventana de fuentes ni una reproduccion."""
	out = dict(_EMPTY)
	try:
		meta = meta or {}
		mediatype = meta.get('mediatype', 'movie')
		imdb_id   = meta.get('imdb', '')

		# TMDb sale del meta que ya tenemos en la mano, sin red ni clave.
		out['tmdb'] = _num(meta.get('rating', ''))
		if not imdb_id:
			return out

		# ── MDBList ──────────────────────────────────────────────────────
		# Se envuelve en cache: getMediaInfo() pega a la API en crudo, asi que
		# sin esto la ventana de fuentes gastaba una peticion cada vez que se
		# abria sobre el mismo titulo, y el reproductor no tendria de donde
		# leer en modo live=False.
		try:
			from resources.lib.modules import mdblist
			if mdblist.getMDBListCredentialsInfo():
				data = _cached(live, mdblist.getMediaInfo, TTL_MDBLIST, imdb_id, mediatype)
				score_map = {}
				for r in (data or {}).get('ratings') or []:
					src, val = (r.get('source') or '').lower(), r.get('value')
					if val is not None:
						score_map[src] = val
				if 'tmdb' in score_map:
					out['tmdb'] = _num(score_map['tmdb']) or out['tmdb']
				for key in ('trakt', 'traktus'):
					if key in score_map:
						out['trakt'] = _num(score_map[key])
						break
				if 'imdb' in score_map:
					out['imdb'], out['imdb_source'] = _num(score_map['imdb']), 'imdb'
				else:
					for key in ('metacritic', 'metacritics'):
						if key in score_map:
							out['imdb'], out['imdb_source'] = _num(score_map[key], '%d'), 'metacritic'
							break
				# Rotten Tomatoes con hueco propio, no como suplente del de
				# IMDb. MDBList lo publica como 'tomatoes' (critica) y
				# 'popcorn' (publico); se toma la de critica, que es la que la
				# gente quiere decir cuando dice "el tomate".
				for key in ('tomatoes', 'tomato'):
					if key in score_map:
						pct = _num(score_map[key], '%d')
						if pct:
							out['rt'] = '%s%%' % pct
						break
				# Metacritic con hueco propio, igual que RT. Sigue pudiendo
				# hacer de suplente de IMDb ahi arriba; quien decide si se
				# pinta dos veces es quien lo muestra, no esto.
				for key in ('metacritic', 'metacritics'):
					if key in score_map:
						out['metacritic'] = _num(score_map[key], '%d')
						break
		except Exception:
			log_utils.error()

		# ── Trakt, si el hueco sigue vacio ───────────────────────────────
		if not out['trakt']:
			try:
				from resources.lib.modules.trakt import getTraktAsJson
				if mediatype == 'episode':
					url = '/shows/%s/seasons/%s/episodes/%s/ratings' % (
						imdb_id, meta.get('season', ''), meta.get('episode', ''))
				elif mediatype in ('tvshow', 'season'):
					url = '/shows/%s/ratings' % imdb_id
				else:
					url = '/movies/%s/ratings' % imdb_id
				data = _cached(live, getTraktAsJson, TTL_TRAKT, url)
				if data and data.get('rating'):
					out['trakt'] = _num(data['rating'])
			except Exception:
				log_utils.error()

		# ── OMDB, si el hueco de IMDb sigue vacio ────────────────────────
		if not out['imdb'] or not out['rt'] or not out['metacritic']:
			try:
				key = (control.setting('omdb.apikey') or '').strip()
				if key:
					omdb = _cached(live, _omdb_fetch, TTL_OMDB, imdb_id, key)
					if omdb:
						ratings_list = omdb.get('Ratings') or []
						if not out['imdb']:
							score = omdb.get('imdbRating', '')
							if score and score != 'N/A':
								out['imdb'], out['imdb_source'] = score, 'imdb'
							else:
								mc = next((r['Value'] for r in ratings_list
								           if r.get('Source') == 'Metacritic'), None)
								if mc and mc != 'N/A':
									out['imdb'] = mc.split('/')[0].strip()
									out['imdb_source'] = 'metacritic'
						if not out['rt']:
							rt = next((r['Value'] for r in ratings_list
							           if r.get('Source') == 'Rotten Tomatoes'), None)
							if rt and rt != 'N/A':
								out['rt'] = rt.strip()
						if not out['metacritic']:
							# OMDB lo da como '78/100'. Se guarda la cifra
							# sola: el /100 lo dice ya el nombre de la casa.
							mc = next((r['Value'] for r in ratings_list
							           if r.get('Source') == 'Metacritic'), None)
							if mc and mc != 'N/A':
								out['metacritic'] = mc.split('/')[0].strip()
			except Exception:
				log_utils.error()
	except Exception:
		log_utils.error()
	return out
