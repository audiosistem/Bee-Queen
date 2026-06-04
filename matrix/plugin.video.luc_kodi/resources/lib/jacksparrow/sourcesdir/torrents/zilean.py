
"""
	jacksparrowscrapers Project - Zilean scraper

	Zilean es un backend C# de iPromKnight (github.com/iPromKnight/zilean)
	que indexa hashlists DebridMediaManager (DMM) usando Lucene/PostgreSQL
	y expone busqueda via dos APIs:

	  1. /dmm/filtered (REST JSON nativo) — usado por este scraper
	  2. /torznab/api  (XML Sonarr/Radarr) — no usado aqui

	El endpoint /dmm/filtered acepta los mismos parametros (ImdbId, Season,
	Episode) y devuelve la misma forma JSON [{info_hash, raw_title, size}]
	en cualquier instancia compatible. Eso significa que multiples hosts
	publicos son intercambiables sin tocar el parser:

	  - zilean.elfhosted.com (ElfHosted Community, hosting profesional,
	    populado con hashlists agregados de la red ElfHosted via
	    Project Zyclops — instancia mas saludable a Mayo 2026)
	  - zileanfortheweebs.midnightignite.me (wrapper Stremio de
	    @midnightignite — antes era el unico endpoint usado por el
	    scraper, ahora funciona como fallback)

	Si la primera instancia devuelve error/timeout/cuerpo vacio, intentamos
	la segunda. Esto elimina la dependencia de un solo operador que tenia
	la version anterior del scraper.
"""

from json import loads as jsloads
import queue
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow.control import setting as getSetting


class source:
	timeout = 10
	priority = 1
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	_queue = queue.SimpleQueue()

	# Lista ordenada de hosts compatibles con el endpoint /dmm/filtered.
	# El scraper intenta en orden y se queda con el primero que devuelva
	# una respuesta JSON valida (lista no vacia o lista valida con cero
	# resultados pero parseable).
	_INSTANCES = (
		"https://zilean.elfhosted.com",
		"https://zileanfortheweebs.midnightignite.me",
	)

	def __init__(self):
		self.language = ['en']
		# Mantenemos base_link como el host primario por compatibilidad
		# con cualquier codigo externo / sources_packs() / logs que lo lea.
		# El fetch real usa _INSTANCES con failover.
		self.base_link = self._INSTANCES[0]
		self.movieSearch_link = '/dmm/filtered?ImdbId=%s'
		self.tvSearch_link = '/dmm/filtered?ImdbId=%s&Season=%s&Episode=%s'
		self.min_seeders = 0

	def _fetch_with_failover(self, path):
		"""Intenta cada host de _INSTANCES en orden. Devuelve la primera
		respuesta JSON parseable como lista. Lanza la ultima excepcion si
		todos fallan."""
		last_exc = None
		for base in self._INSTANCES:
			try:
				body = client.request(base + path, timeout=self.timeout)
				if not body:
					continue
				parsed = jsloads(body)
				if isinstance(parsed, list):
					return parsed
				# Respuesta valida pero no es lista (raro) — intentamos el
				# siguiente host por si la primera instancia esta sirviendo
				# una pagina de error HTML aceptada como JSON.
			except Exception as e:
				last_exc = e
				continue
		if last_exc:
			raise last_exc
		return []

	def sources(self, data, hostDict):
		sources = []
		if not data: return sources
		sources_append = sources.append
		try:
			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			episode_title = data['title'] if 'tvshowtitle' in data else None
			year = data['year']
			imdb = data['imdb']
			if 'tvshowtitle' in data:
				season = data['season']
				episode = data['episode']
				hdlr = 'S%02dE%02d' % (int(season), int(episode))
				path = self.tvSearch_link % (imdb, season, episode)
			else:
				hdlr = year
				path = self.movieSearch_link % imdb
			# log_utils.log('path = %s' % path)
			try:
				files = self._fetch_with_failover(path)
			except:
				files = []
				raise
			finally:
				self._queue.put_nowait(files) # if seasons
				self._queue.put_nowait(files) # if shows
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('ZILEAN')
			return sources

		for file in files:
			try:
				hash = file['info_hash']
				name = source_utils.clean_name(file['raw_title'])

				if not source_utils.check_title(title, aliases, name.replace('.(Archie.Bunker', ''), hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					dsize, isize = source_utils.convert_size(float(file["size"]), to='GB')
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				sources_append({
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'zilean', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': 0
				})
			except:
				source_utils.scraper_error('ZILEAN')
		return sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		sources = []
		if not data: return sources
		sources_append = sources.append
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			url = '%s%s' % (self.base_link, self.tvSearch_link % (imdb, season, data['episode']))
			files = self._queue.get(timeout=self.timeout + 1)
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
		except:
			source_utils.scraper_error('ZILEAN')
			return sources

		for file in files:
			try:
				hash = file['info_hash']
				name = source_utils.clean_name(file['raw_title'])

				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name.replace('.(Archie.Bunker', ''))
						if not valid: continue
					package = 'season'

				elif search_series:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name.replace('.(Archie.Bunker', ''), total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url)
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					dsize, isize = source_utils.convert_size(float(file["size"]), to='GB')
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'zilean', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': 0, 'package': package
				}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				sources_append(item)
			except:
				source_utils.scraper_error('ZILEAN')
		return sources
