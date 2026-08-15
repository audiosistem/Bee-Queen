# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from datetime import datetime
import re
import requests
from requests.adapters import HTTPAdapter
from threading import Thread
from urllib3.util.retry import Retry
from resources.lib.database import cache, metacache, fanarttv_cache
from resources.lib.indexers.fanarttv import FanartTv
from resources.lib.modules.control import setting as getSetting, notification, sleep, apiLanguage, mpaCountry, trailer as control_trailer, yesnoDialog

base_link = "https://api.themoviedb.org/3/"
image_path = "https://image.tmdb.org/t/p/%s"
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
session.mount('https://api.themoviedb.org', HTTPAdapter(max_retries=retries, pool_maxsize=100))


def _english_title(result, media='movie'):
	# Título en inglés "si es posible": para originales en inglés, original_title/original_name
	# ES el título inglés (coste cero). Para otros idiomas se intenta el título alternativo
	# oficial de US/GB (descartando los que llevan 'type': working titles, etc.). Si no hay
	# nada fiable devuelve None y se conserva el título localizado — el contenido nativo
	# español mantiene así su título natural.
	try:
		if media == 'movie': orig_key, alt_key = 'original_title', 'titles'
		else: orig_key, alt_key = 'original_name', 'results'
		if result.get('original_language') == 'en' and result.get(orig_key): return result[orig_key]
		alts = result.get('alternative_titles', {}).get(alt_key) or []
		alts = [x.get('title') for x in alts if x.get('iso_3166_1') in ('US', 'GB') and not x.get('type') and x.get('title')]
		if alts: return alts[0]
	except: pass
	return None


def _poster_list(images, lang, path_prefix, limit=10):
	# Devuelve hasta `limit` URLs completas de pósters alternativos.
	# Prioridad de llenado: idioma del usuario > sin idioma (arte limpio) > inglés,
	# cada grupo ordenado por votos. Sin esta prioridad un usuario 'es' recibiría un
	# pool dominado por pósters 'en' (siempre acumulan más votos en TMDb).
	try:
		if not images: return []
		pool = [x for x in images if x.get('file_path')]
		if not pool: return []
		def _prio(x):
			iso = x.get('iso_639_1')
			if iso == lang: return 0
			if iso in (None, '', 'null'): return 1
			return 2
		pool = sorted(pool, key=lambda x: (_prio(x), -float(x.get('vote_average') or 0)))
		return ['%s%s' % (path_prefix, x['file_path']) for x in pool[:limit]]
	except: return []


class TMDb:
	def __init__(self):
		self.API_key = getSetting('tmdb.api.key')
		if not self.API_key: self.API_key = 'f2e500501d9fa3bd1637bfd00f11583a'
		self.set_resolutions()
		self.lang = apiLanguage()['tmdb']
		self.mpa_country = mpaCountry()
		self.enable_fanarttv = getSetting('enable.fanarttv') == 'true'
		self.prefer_en_titles = getSetting('title.lang.en') == 'true'
		self.art_lang = 'en' if self.prefer_en_titles else self.lang # orientación única para pósters/logos/poster3

	def get_request(self, url):
		try:
			try: response = session.get(url, timeout=20)
			except requests.exceptions.SSLError:
				response = session.get(url, timeout=20)
		except requests.exceptions.ConnectionError:
			notification(message=32024)
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			if response.status_code in (200, 201): return response.json()
			elif response.status_code == 404:
				if getSetting('debug.level') == '1':
					from resources.lib.modules import log_utils
					log_utils.log('TMDb get_request() failed: (404:NOT FOUND) - URL: %s' % url, level=log_utils.LOGDEBUG)
				return '404:NOT FOUND'
			elif 'Retry-After' in response.headers: # API REQUESTS ARE BEING THROTTLED, INTRODUCE WAIT TIME (TMDb removed rate-limit on 12-6-20)
				throttleTime = response.headers['Retry-After']
				notification(message='TMDb Throttling Applied, Sleeping for %s seconds' % throttleTime)
				sleep((int(throttleTime) + 1) * 1000)
				return self.get_request(url)
			else:
				if getSetting('debug.level') == '1':
					from resources.lib.modules import log_utils
					log_utils.log('TMDb get_request() failed: URL: %s\n                       msg : TMDB Response: %s' % (url, response.text), __name__, log_utils.LOGDEBUG)
				return None
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None

	def userlists(self, url):
		try:
			result = self.get_request(url % self.API_key)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
			next = '' ; list = []
		except: return
		try: # This is actually wrong but may not be used so look into 
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			media_type = item.get('list_type')
			name = item.get('name')
			list_id =  item.get('id')
			url = 'https://api.themoviedb.org/4/list/%s?api_key=%s&sort_by=%s&page=1' % (list_id, self.API_key, self.tmdb_sort())
			item = {'media_type': media_type, 'name': name, 'list_id': list_id, 'url': url, 'context': url, 'next': next}
			list.append(item)
		return list

	def popular_people(self):
		url = '%s%s' % (base_link, 'person/popular?api_key=%s&language=en-US&page=1' % self.API_key)
		item = self.get_request(url)
		return item

	def tmdb_sort(self):
		sort = int(getSetting('sort.movies.type'))
		tmdbSort = 'original_order'
		if sort == 1: tmdbSort = 'title'
		if sort in (2, 3): tmdbSort = 'vote_average'
		if sort in (4, 5, 6): tmdbSort = 'release_date' # primary_release_date
		tmdb_sort_order = '.asc' if int(getSetting('sort.movies.order')) == 0 else '.desc'
		sort_string = tmdbSort + tmdb_sort_order
		return sort_string

# poster_path = 'w342', fanart_path = 'w1280', still_path = 'w500', profile_path = 'w185'
	def set_resolutions(self):
		paths = (
				{'poster': 'w185', 'fanart': 'w300',  'still': 'w300',     'profile': 'w185'},
				{'poster': 'w342', 'fanart': 'w780',  'still': 'w500',     'profile': 'w342'},
				{'poster': 'w780', 'fanart': 'w1280', 'still': 'w780',     'profile': 'h632'},
				{'poster': 'original', 'fanart': 'original', 'still': 'original', 'profile': 'original'})
		user_level = int(getSetting('tmdb.imageResolutions', '2'))
		# Auto-upgrade a 'original' en pantallas 4K detectadas por gui_resolution.py.
		# Solo cuando el usuario NO ha bajado manualmente la calidad (nivel < 2).
		# is_4k_display() espera al flag con timeout corto — evita la race
		# condition del primer menú tras boot en frío de Android.
		# Nivel 3 = el usuario forzó 'original' manualmente — siempre respetar.
		from resources.lib.modules.gui_resolution import is_4k_display as _is_4k_display
		if user_level >= 3 or (_is_4k_display() and user_level >= 2):
			resolutions = paths[3]  # original — máxima calidad
		else:
			resolutions = paths[user_level]
		self.poster_path  = image_path % resolutions['poster']
		self.fanart_path  = image_path % resolutions['fanart']
		self.still_path   = image_path % resolutions['still']
		self.profile_path = image_path % resolutions['profile']


class Movies(TMDb):
	def __init__(self):
		TMDb.__init__(self)
		self.list = []
		self.meta = []
		self.movie_link = base_link + 'movie/%s?api_key=%s&language=%s&append_to_response=credits,release_dates,videos,alternative_titles,images&include_image_language=%s,en,null' % ('%s', self.API_key, self.lang, self.lang)
		###  other "append_to_response" options external_ids,images,translations
		self.art_link = base_link + 'movie/%s/images?api_key=%s' % ('%s', self.API_key)
		self.external_ids = base_link + 'movie/%s/external_ids?api_key=%s' % ('%s', self.API_key)
		# self.user = str(self.imdb_user) + str(self.API_key)
		self.user = str(self.API_key)

	def tmdb_list(self, url, meta_sem=None):
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
		except: return
		self.list = [] ; sortList = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				sortList.append(values['tmdb'])
				values['imdb'] = ''
				values['tvdb'] = ''
				values['metacache'] = False
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			# meta_sem (opcional): semáforo GLOBAL compartido por el precache de
			# arranque para acotar el TOTAL de peticiones de meta concurrentes
			# entre TODAS las listas. Sin él, el comportamiento es el de siempre
			# (un hilo por título, sin tope) — los menús normales no lo pasan.
			if meta_sem is not None: meta_sem.acquire()
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				movie_meta = self.get_movie_meta(tmdb)
				values.update(movie_meta)
				imdb = values['imdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
			finally:
				if meta_sem is not None: meta_sem.release()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		sorted_list = []
		self.list = [i for i in self.list if i.get('tmdb')]
		for i in sortList:
			sorted_list += [item for item in self.list if item['tmdb'] == i] # resort to match TMDb list because threading will lose order.
		return sorted_list

	def tmdb_list_ids(self, url):
		"""Devuelve SOLO los tmdb ids de una lista, sin enriquecer (sin las ~20
		peticiones de meta por título). Lo usa el precache de arranque para saber
		QUÉ títulos invalidar en metacache antes de re-enriquecer (frescura real).
		Reutiliza exactamente la misma clave de caché que tmdb_list, así que no
		añade tráfico: si la lista ya se pidió, sale de caché."""
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return []
			return [str(i['id']) for i in result.get('results', []) if i.get('id')]
		except: return []

	def tmdb_list_visual_refresh(self, url):
		"""v1.0.54 — arranque ligero. Refresca SOLO los campos visuales de la
		parrilla (fanart, rating, votos, plot, fecha y, si no se prefieren
		títulos en inglés, el póster primario) de los títulos que YA están en
		metacache, tomándolos de la propia respuesta de LISTA de TMDb: cero
		peticiones de detalle por título. El detalle completo (reparto, logos,
		posters_all, certificaciones, tráilers) NO se toca aquí — lo renueva el
		ciclo fresh_meta cada meta_hours. Los títulos sin meta previa (o cuya
		meta la política de frescura de metacache da por caducada) se dejan
		intactos: tmdb_list los traerá completos justo después.
		Devuelve el número de metas actualizadas."""
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return 0
			items = result.get('results') or []
			if not items: return 0
		except: return 0
		refs = [{'tmdb': str(i.get('id') or ''), 'imdb': '', 'tvdb': '', 'metacache': False} for i in items]
		try: refs = metacache.fetch(refs, self.lang, self.user)
		except: return 0
		updates = []
		for ref, item in zip(refs, items):
			try:
				if not ref.get('metacache'): continue # sin meta previa o caducada: la traerá completa tmdb_list
				values = dict(ref)
				for k in ('metacache', 'next'): values.pop(k, None)
				if not values.get('tmdb'): values['tmdb'] = str(item.get('id') or '')
				if item.get('backdrop_path'): values['fanart'] = '%s%s' % (self.fanart_path, item['backdrop_path'])
				# El póster de la lista es el primario localizado. Si el usuario
				# prefiere arte en inglés, el póster elegido por el detalle
				# completo (bloque images) puede ser otro: en ese caso no se pisa.
				if item.get('poster_path') and not self.prefer_en_titles:
					values['poster'] = '%s%s' % (self.poster_path, item['poster_path'])
				if item.get('vote_average') is not None: values['rating'] = item.get('vote_average')
				if item.get('vote_count') is not None: values['votes'] = item.get('vote_count')
				if item.get('overview'): values['plot'] = item['overview']
				premiered = item.get('release_date') or ''
				if premiered:
					values['premiered'] = str(premiered)
					values['year'] = str(premiered)[:4]
				updates.append({'imdb': values.get('imdb', ''), 'tmdb': values.get('tmdb', ''), 'tvdb': values.get('tvdb', ''),
						'lang': self.lang, 'user': self.user, 'item': values})
			except: pass
		if updates:
			try: metacache.insert(updates)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return len(updates)

	def jw_list(self, jw_package_code):
		# Alternative to tmdb_list(): sources TMDb IDs from JustWatch's GraphQL API
		# instead of TMDb's discover endpoint. Used by the experimental
		# 'streaming.use_justwatch' toggle. Enrichment pipeline below is a verbatim
		# mirror of tmdb_list()'s metadata thread loop.
		try:
			from resources.lib.indexers.justwatch import popular_movie_tmdb_ids
			tmdb_ids = cache.get(popular_movie_tmdb_ids, 24, jw_package_code)
			if not tmdb_ids: return
		except: return
		self.list = [] ; sortList = []
		for tid in tmdb_ids:
			try:
				values = {'next': '', 'tmdb': str(tid), 'imdb': '', 'tvdb': '', 'metacache': False}
				sortList.append(values['tmdb'])
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				movie_meta = self.get_movie_meta(tmdb)
				values.update(movie_meta)
				imdb = values['imdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '')
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		sorted_list = []
		self.list = [i for i in self.list if i.get('tmdb')]
		for i in sortList:
			sorted_list += [item for item in self.list if item['tmdb'] == i]
		return sorted_list

	def tmdb_collections_list(self, url):
		try:
			result = cache.get(self.get_request, 168, url)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			if '/collection/' in url: items = result['parts']
			elif '/3/' in url: items = result['items']
			else: items = result['results']
		except: return
		self.list = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				media_type = item.get('media_type')
				if media_type == 'tv': continue
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				values['imdb'] = ''
				values['tvdb'] = ''
				values['metacache'] = False 
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				movie_meta = self.get_movie_meta(tmdb)
				values.update(movie_meta)
				imdb = values['imdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		self.list = [i for i in self.list if i.get('tmdb')]
		return self.list

	def tmdb_collections_search(self, url):
		try:
			result = cache.get(self.get_request, 168, url)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
		except: return
		self.list = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				values['media_type'] = 'collection'
				values['fanart'] = '%s%s' % (self.fanart_path, item['backdrop_path']) if item.get('backdrop_path') else ''
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				values['name'] = item.get('name')
				values['plot'] = item.get('overview', '') if item.get('overview') else ''
				values['poster'] = '%s%s' % (self.poster_path, item['poster_path']) if item.get('poster_path') else ''
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return self.list

	def get_movie_request(self, tmdb, imdb=None): # api claims int rq'd.  But imdb_id works for movies but not looking like it does for shows
		if not tmdb and not imdb: return
		try:
			result = None
			if tmdb: result = self.get_request(self.movie_link % tmdb)
			if not result or ('404:NOT FOUND' in result):
				if imdb: result = self.get_request(self.movie_link % imdb)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_movie_meta(self, tmdb, imdb=None):
		if not tmdb and not imdb: return
		try:
			result = self.get_movie_request(tmdb, imdb)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			meta = {}
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			meta['mediatype'] = 'movie'
# adult - not used
			meta['fanart'] = '%s%s' % (self.fanart_path, result['backdrop_path']) if result.get('backdrop_path') else ''

			try:
				_logos = [i for i in result['images']['logos'] if i.get('file_path', '').endswith('png')]
				tmdblogo_path = ([i['file_path'] for i in _logos if i.get('iso_639_1') == self.art_lang] or [i['file_path'] for i in _logos])[0]
			except: tmdblogo_path = ''
			meta['tmdblogo'] = '%s%s' % (self.fanart_path, tmdblogo_path) if tmdblogo_path else ''

			meta['belongs_to_collection'] = result.get('belongs_to_collection', '')
# budget - not used
			meta['genre'] = ' / '.join([x['name'] for x in result.get('genres', {})]) or 'NA'
# homepage - not used
			meta['tmdb'] = str(result.get('id', '')) if result.get('id') else ''
			meta['imdb'] = str(result.get('imdb_id', '')) if result.get('imdb_id') else ''
			meta['imdbnumber'] = meta['imdb']
			meta['original_language'] = result.get('original_language', '')
			meta['originaltitle'] = result.get('original_title', '')
			meta['plot'] = result.get('overview', '') if result.get('overview') else ''
			if self.lang != 'en' and meta['plot'] in ('', None, 'None'): meta['plot'] = self.get_en_overview(tmdb)
			# meta['?'] = result.get('popularity', '')
			meta['poster'] = '%s%s' % (self.poster_path, result['poster_path']) if result.get('poster_path') else ''
			try:
				_alt_posters = _poster_list(result['images']['posters'], self.art_lang, self.poster_path)
				if self.prefer_en_titles and _alt_posters: meta['poster'] = _alt_posters[0] # póster base también en inglés (aunque la rotación esté apagada)
				if len(_alt_posters) > 1: meta['posters_all'] = _alt_posters # solo guardar si hay alternativas reales para rotar
			except: pass
			# production_companies = result.get('production_companies', {})
			# try: meta['studio'] = [x['name'] for x in production_companies if x['logo_path']][0] # Silvo seems to use "studio" icons in place of "thumb" for movies in list view
			# except:
				# try: meta['studio'] = production_companies[0].get('name')
				# except: meta['studio'] = ''
			try: meta['country_codes'] = [i['iso_3166_1'] for i in result['production_countries']]
			except: meta['country_codes'] = ''
			meta['premiered'] = str(result.get('release_date', '')) if result.get('release_date') else ''
			try: meta['year'] = meta['premiered'][:4]
			except: meta['year'] = ''
# revenue
			meta['duration'] = int(result.get('runtime') * 60) if result.get('runtime') else ''
			meta['spoken_languages'] = result.get('spoken_languages')
			meta['status'] = result['status']
			meta['tagline'] = result.get('tagline', '')
			meta['title'] = result.get('title')
			if self.prefer_en_titles and self.lang != 'en':
				meta['title'] = _english_title(result, 'movie') or meta['title']
			meta['rating'] = result.get('vote_average', '')
			meta['votes'] = result.get('vote_count', '')
			crew = result.get('credits', {}).get('crew')
			try: meta['director'] = ', '.join([d['name'] for d in [x for x in crew if x['job'] == 'Director']])
			except: meta['director'] = ''
			try: meta['writer'] = ', '.join([w['name'] for w in [y for y in crew if y['job'] in ('Writer', 'Screenplay', 'Author', 'Novel')]])
			except: meta['writer'] = ''
			meta['castandart'] = []
			for person in result['credits']['cast']:
				try: meta['castandart'].append({'name': person['name'], 'role': person['character'], 'thumbnail': ('%s%s' % (self.profile_path, person['profile_path']) if person.get('profile_path') else '')})
				except: pass
				if len(meta['castandart']) == 150: break
			meta['mpaa'] = ''
			def parse_mpaa(rel_info):
				for cert in rel_info.get('release_dates', {}): # loop thru all keys
					if cert['certification']:
						if cert['type'] not in (3, 4, 5, 6): continue # 1 and 2 are limited releases, ignore
						meta['mpaa'] = cert['certification']
						meta['premiered'] = cert['release_date'].split('T')[0] or meta['premiered'] # use Countries premiered date
						break
			try: parse_mpaa([x for x in result['release_dates']['results'] if x['iso_3166_1'] == self.mpa_country][0])
			except: pass
			if not meta['mpaa'] and self.mpa_country != 'US':
				try: parse_mpaa([x for x in result['release_dates']['results'] if x['iso_3166_1'] == 'US'][0])
				except: pass
			if meta['mpaa']: meta['mpaa'] = getSetting('mpa.prefix') + meta['mpaa']
			try:
				# v1.0.46: prefiere Trailer oficial de mayor resolución; Teaser solo como último recurso
				_vids = [x for x in result['videos']['results'] if x['site'] == 'YouTube' and x['type'] in ('Trailer', 'Teaser')]
				_vids.sort(key=lambda x: (x['type'] != 'Trailer', not x.get('official'), -(x.get('size') or 0)))
				trailer = _vids[0]['key']
				meta['trailer'] = control_trailer % trailer
			except: meta['trailer'] = ''
			# make aliases match what trakt returns in sources module for title checking scrape results
			try: meta['aliases'] = [{'title': x['title'], 'country': x['iso_3166_1'].lower()} for x in result.get('alternative_titles', {}).get('titles') if x.get('iso_3166_1').lower() in ('us', 'uk', 'gb')]
			except: meta['aliases'] = []
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return meta

	def get_art(self, tmdb):
		if not tmdb: return
		url = self.art_link % tmdb
		art3 = self.get_request(url)
		if art3 is None: return
		if '404:NOT FOUND' in art3: return art3
		try:
			poster3 = self.parse_art(art3['posters'])
			poster3 = '%s%s' % (self.poster_path, poster3) if poster3 else ''
		except: poster3 = ''
		try:
			fanart3 = self.parse_art(art3['backdrops'])
			fanart3 = '%s%s' % (self.fanart_path, fanart3) if fanart3 else ''
		except: fanart3 = ''
		extended_art = {'extended': True, 'poster3': poster3, 'fanart3': fanart3}
		return extended_art

	def parse_art(self, img):
		if not img: return None
		try:
			ret_img = [(x['file_path'], x['vote_average']) for x in img if any(value == x.get('iso_639_1') for value in (self.art_lang, 'null', '', None))]
			if not ret_img: ret_img = [(x['file_path'], x['vote_average']) for x in img]
			if not ret_img: return None
			if len(ret_img) >1: ret_img = sorted(ret_img, key=lambda x: int(x[1]), reverse=True)
			ret_img = [x[0] for x in ret_img][0]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		return ret_img

	def get_en_overview(self, tmdb): # fallback for when self.lang != 'en'
		if not tmdb: return None
		overview = None
		try:
			url = '%s%s' % (base_link, 'movie/%s?api_key=%s&language=en,en-US' % (tmdb, self.API_key))
			result = self.get_request(url)
			overview = result.get('overview')
			if overview: overview = 'Translation Not Available:\n' + overview
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return overview

	def get_credits(self, tmdb):
		if not tmdb: return None
		result = None
		try:
			url = base_link + 'movie/%s/credits?api_key=%s' % (tmdb, self.API_key)
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_external_ids(self, tmdb, imdb): # api claims int rq'd.  But imdb_id works for movies but not looking like it does for shows
		if not tmdb and not imdb: return
		try:
			result = None
			if tmdb: result = self.get_request(self.external_ids % tmdb)
			if not result or ('404:NOT FOUND' in result):
				if imdb: result = self.get_request(self.external_ids % imdb)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def IdLookup(self, imdb):
		if not imdb: return
		try:
			result = None
			find_url = base_link + 'find/%s?api_key=%s&external_source=%s'
			if imdb and imdb.startswith('tt'): # trakt has some bad data with url's in ids
				url = find_url % (imdb, self.API_key, 'imdb_id')
				result = self.get_request(url)
				if result is None: return
				if '404:NOT FOUND' in result: return result
				try: result = result['movie_results'][0]
				except: return None
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_watchproviders(self):
		# Curated tuples: (display_name, provider_id, logo_override[, watch_region]).
		# logo_override = "" -> fetch live from TMDb /watch/providers/movie (cached 30 days).
		# Override exists when TVshows.get_networks() already has a curated high-quality
		# logo for the same brand; otherwise we trust JustWatch's logo via TMDb's CDN.
		# provider_id may be pipe-joined ('520|524') to OR multiple TMDb ids (TMDb keeps
		# regional duplicates for some brands). watch_region defaults to 'US'; set the 4th
		# element for providers with no US presence (e.g. SkyShowtime is Europe-only) so
		# both the discover query and the logo lookup use a region where they exist.
		curated = [
			('Netflix',             8,    'https://i.postimg.cc/25VTZBr9/pngwing-com-(2).png'),
			('Amazon Prime Video',  9,    'https://i.postimg.cc/FH4WdKBq/prime-video-(1).png'),
            ('JustWatch TV',        2285, 'https://i.postimg.cc/WbMNhfB1/justwatch-(2).png'),
            ('Vix',                 457,  'https://i.postimg.cc/sXsZqr9z/vix-logo-01.png'),
            ('Paramount+',          2303, 'https://i.postimg.cc/50xnPkV6/paramount-plus.png'),
			('SkyShowtime',         1773, 'https://i.postimg.cc/76GpVGxT/skyshowtime-2022-color.png', 'ES'),
			('The CW',              83,   'https://i.postimg.cc/4NnRNxHk/The-CW-(2006-2024).png'),
			('HBO Max',             1899, 'https://i.postimg.cc/BnD29cZq/HBO-Max-Logo-svg.png'),
			('Hulu',                15,   'https://i.postimg.cc/26tsWfs5/Hulu-svg.png'),
			('Apple TV+',           350,  'https://i.postimg.cc/Bnz3fH66/apple-tv-(1).png'),
			('Peacock Premium',     386,  'https://i.postimg.cc/rpx038J6/peacock-(1).png'),
			('Disney+',             337,  'https://i.postimg.cc/1zGXMvmX/Disney-svg.png'),
            ('Starz',               43,   'https://i.postimg.cc/LXpsYw1B/starz-(1).png'),
			('AMC+',                526,  'https://i.postimg.cc/SxqxRW7Y/AMC.png'),
			('Crunchyroll',         283,  'https://i.postimg.cc/L5GsD8YR/crunchyroll.png'),
			('MUBI',                11,   'https://i.postimg.cc/GtCQRFtZ/Mubi.png'),
			('Shudder',             99,   'https://i.postimg.cc/nhXr6vZb/shudder.png'),
			('Google Play Movies',  3,    'https://i.postimg.cc/nLX7Kwkp/pngwing-com.png'),
			('TCM',                 361,  'https://i.postimg.cc/Wz8hcMnJ/pngwing-com-(1).png'),
			('fuboTV',              257,  'https://i.postimg.cc/d3V9DqRH/Fubo.png'),
			('MGM+',                34,   'https://i.postimg.cc/nzMC4yFT/MGM-logo-svg.png'),
			('Tubi',                73,   'https://i.postimg.cc/mDgJsSHD/Tubi.png'),
			('Pluto TV',            300,  'https://i.postimg.cc/ncgdWJ26/Pluto-TV.png'),
			('The Roku Channel',    207,  'https://i.postimg.cc/ZK6TnyZK/Roku-Channel.png'),
			('Kanopy',              191,  'https://i.postimg.cc/fR46Q6VV/image.jpg'),
			('Plex',                538,  'https://i.postimg.cc/sD003b1H/pngwing-com-(3).png'),
		]
		# Normalize to 4-tuples (name, pid, override, region) with 'US' as default region.
		norm = []
		for entry in curated:
			region = entry[3] if len(entry) > 3 and entry[3] else 'US'
			norm.append((entry[0], entry[1], entry[2], region))
		# Resolve missing logos with one cached call per needed region (30-day TTL;
		# TMDb logo paths are very stable).
		live_logos = {}  # (region, provider_id_int) -> logo url
		need_regions = set(r for _, _, override, r in norm if not override)
		for reg in need_regions:
			try:
				url = base_link + 'watch/providers/movie?api_key=%s&language=en-US&watch_region=%s' % (self.API_key, reg)
				data = cache.get(self.get_request, 720, url)
				if isinstance(data, dict):
					for p in (data.get('results') or []):
						lp = p.get('logo_path')
						if lp:
							live_logos[(reg, p.get('provider_id'))] = 'https://image.tmdb.org/t/p/original' + lp
			except Exception:
				from resources.lib.modules import log_utils
				log_utils.error()
		out = []
		for name, pid, override, region in norm:
			logo = override
			if not logo:
				for part in str(pid).split('|'):
					try: logo = live_logos.get((region, int(part)), '')
					except: logo = ''
					if logo: break
			out.append((name, str(pid), logo, region))
		return out


class TVshows(TMDb):
	def __init__(self):
		TMDb.__init__(self)
		self.list = []
		self.meta = []
		self.show_link = base_link + 'tv/%s?api_key=%s&language=%s&append_to_response=credits,content_ratings,external_ids,alternative_titles,videos,images&include_image_language=%s,en,null' % ('%s', self.API_key, self.lang, self.lang)
		# 'append_to_response=translations, aggregate_credits' (DO NOT USE, response data way to massive and bogs the response time)
		self.art_link = base_link + 'tv/%s/images?api_key=%s' % ('%s', self.API_key)
		self.tvdb_key = getSetting('tvdb.api.key')
		self.imdb_user = getSetting('imdb.user').replace('ur', '')
		self.user = str(self.imdb_user) + str(self.tvdb_key)
		self.date_time = datetime.now()
		self.today_date = (self.date_time).strftime('%Y-%m-%d')

	def tmdb_list(self, url, meta_sem=None):
		if not url: return
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			items = result['results']
		except: return
		self.list = [] ; sortList = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				values['tmdb'] = str(item.get('id')) if item.get('id', '') else ''
				sortList.append(values['tmdb'])
				values['metacache'] = False 
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			if meta_sem is not None: meta_sem.acquire()
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				showSeasons_meta = self.get_showSeasons_meta(tmdb)
				values.update(showSeasons_meta)
				imdb = values['imdb']
				tvdb = values['tvdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_tvshow_art, 336, tvdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
			finally:
				if meta_sem is not None: meta_sem.release()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		sorted_list = []
		self.list = [i for i in self.list if i.get('tmdb')]
		for i in sortList:
			sorted_list += [item for item in self.list if str(item['tmdb']) == str(i)]
		return sorted_list

	def tmdb_list_ids(self, url):
		"""Igual que Movies.tmdb_list_ids: devuelve solo los tmdb ids de la lista
		sin enriquecer. Reutiliza la clave de caché de tmdb_list (no añade tráfico)."""
		if not url: return []
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return []
			return [str(i['id']) for i in result.get('results', []) if i.get('id')]
		except: return []

	def tmdb_list_visual_refresh(self, url):
		"""v1.0.54 — arranque ligero (variante series). Igual que en Movies:
		refresca solo los campos visuales desde la respuesta de LISTA (name,
		first_air_date, vote_average...), sin peticiones de detalle por título.
		El estado de emisión (status / next_episode_to_air) NO se toca: la
		política de frescura de metacache para series en emisión sigue mandando,
		y las metas que dé por caducadas no se tocan aquí (metacache=False) —
		tmdb_list las trae completas justo después.
		Devuelve el número de metas actualizadas."""
		if not url: return 0
		try:
			result = cache.get(self.get_request, 96, url % self.API_key)
			if not result or '404:NOT FOUND' in result: return 0
			items = result.get('results') or []
			if not items: return 0
		except: return 0
		refs = [{'tmdb': str(i.get('id') or ''), 'imdb': '', 'tvdb': '', 'metacache': False} for i in items]
		try: refs = metacache.fetch(refs, self.lang, self.user)
		except: return 0
		updates = []
		for ref, item in zip(refs, items):
			try:
				if not ref.get('metacache'): continue # sin meta previa o caducada: la traerá completa tmdb_list
				values = dict(ref)
				for k in ('metacache', 'next'): values.pop(k, None)
				if not values.get('tmdb'): values['tmdb'] = str(item.get('id') or '')
				if item.get('backdrop_path'): values['fanart'] = '%s%s' % (self.fanart_path, item['backdrop_path'])
				if item.get('poster_path') and not self.prefer_en_titles:
					values['poster'] = '%s%s' % (self.poster_path, item['poster_path'])
				if item.get('vote_average') is not None: values['rating'] = item.get('vote_average')
				if item.get('vote_count') is not None: values['votes'] = item.get('vote_count')
				if item.get('overview'): values['plot'] = item['overview']
				premiered = item.get('first_air_date') or ''
				if premiered:
					values['premiered'] = str(premiered)
					if not values.get('year'): values['year'] = str(premiered)[:4]
				updates.append({'imdb': values.get('imdb', ''), 'tmdb': values.get('tmdb', ''), 'tvdb': values.get('tvdb', ''),
						'lang': self.lang, 'user': self.user, 'item': values})
			except: pass
		if updates:
			try: metacache.insert(updates)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return len(updates)

	def tmdb_collections_list(self, url):
		if not url: return
		try:
			result = self.get_request(url)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			if '/collection/' in url: items = result['parts']
			elif '/3/' in url: items = result['items']
			else: items = result['results']
		except: return
		self.list = []
		try:
			page = int(result['page'])
			total = int(result['total_pages'])
			if page >= total: raise Exception()
			if 'page=' not in url: raise Exception()
			next = '%s&page=%s' % (url.split('&page=', 1)[0], page+1)
		except: next = ''
		for item in items:
			try:
				values = {}
				values['next'] = next 
				media_type = item.get('media_type', '')
				if media_type == 'movie': continue
				values['tmdb'] = str(item.get('id', '')) if item.get('id') else ''
				values['metacache'] = False 
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		def items_list(i):
			if self.list[i]['metacache']: return
			try:
				values = {}
				tmdb = self.list[i].get('tmdb', '')
				showSeasons_meta = cache.get(self.get_showSeasons_meta, 96, tmdb)
				values.update(showSeasons_meta)
				imdb = values['imdb']
				tvdb = values['tvdb']
				if self.enable_fanarttv:
					extended_art = fanarttv_cache.get(FanartTv().get_tvshow_art, 336, tvdb)
					if extended_art: values.update(extended_art)
				values = dict((k,v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
				self.list[i].update(values)
				meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'lang': self.lang, 'user': self.user, 'item': values}
				self.meta.append(meta)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()

		self.list = metacache.fetch(self.list, self.lang, self.user)
		threads = []
		append = threads.append
		for i in range(0, len(self.list)):
			append(Thread(target=items_list, args=(i,)))
		[i.start() for i in threads]
		[i.join() for i in threads]
		if self.meta:
			self.meta = [i for i in self.meta if i.get('tmdb')]
			metacache.insert(self.meta)
		self.list = [i for i in self.list if i.get('tmdb')]
		return self.list

	def get_show_request(self, tmdb):
		if not tmdb: return None
		try:
			result = None
			url = self.show_link % tmdb
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_showSeasons_meta(self, tmdb): # builds seasons meta from show level request
		if not tmdb: return None
		try:
			result = self.get_show_request(tmdb)
			if not result: return
			if '404:NOT FOUND' in result: return result
			meta = {}
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			meta['mediatype'] = 'tvshow'
			meta['fanart'] = '%s%s' % (self.fanart_path, result['backdrop_path']) if result.get('backdrop_path') else ''

			try:
				_logos = [i for i in result['images']['logos'] if i.get('file_path', '').endswith('png')]
				tmdblogo_path = ([i['file_path'] for i in _logos if i.get('iso_639_1') == self.art_lang] or [i['file_path'] for i in _logos])[0]
			except: tmdblogo_path = ''
			meta['tmdblogo'] = '%s%s' % (self.fanart_path, tmdblogo_path) if tmdblogo_path else ''

			try: meta['duration'] = min(result['episode_run_time']) * 60
			except: meta['duration'] = ''
			meta['premiered'] = str(result.get('first_air_date', '')) if result.get('first_air_date') else ''
			try: meta['year'] = meta['premiered'][:4]
			except: meta['year'] = ''
			meta['genre'] = ' / '.join([x['name'] for x in result.get('genres', {})]) or 'NA'
			meta['tmdb'] = tmdb
			meta['in_production'] = result.get('in_production') # do not use for "season_isAiring", this is show wide and "season_isAiring" is season specific for season pack scraping.
			meta['last_air_date'] = result.get('last_air_date', '')
			meta['last_episode_to_air'] = result.get('last_episode_to_air', '')
			meta['next_episode_to_air'] = result.get('next_episode_to_air', '')
			meta['tvshowtitle'] = result.get('name')
			if self.prefer_en_titles and self.lang != 'en':
				meta['tvshowtitle'] = _english_title(result, 'show') or meta['tvshowtitle']
			networks = result.get('networks', {})
			try: meta['studio'] = [x['name'] for x in networks if x['logo_path']][0] # use single studio name that has a logo in hopes skin also has logo 
			except:
				try: meta['studio'] = networks[0].get('name')
				except: meta['studio'] = ''
			# Network logo URL — consumido por source_results 2160p
			try:
				_net_logo_path = [x['logo_path'] for x in networks if x.get('logo_path')][0]
				meta['network_logo'] = (image_path % 'w300') + _net_logo_path
			except:
				meta['network_logo'] = ''
			meta['total_episodes'] = result.get('number_of_episodes') # count includes both aired and unaired eps
			meta['total_seasons'] = result.get('number_of_seasons')
			try: meta['origin_country'] = result.get('origin_country')[0]
			except: meta['origin_country'] = ''
			meta['original_language'] = result.get('original_language')
			meta['originaltitle'] = result.get('original_name')
			meta['plot'] = result.get('overview', '') if result.get('overview') else ''
			if self.lang != 'en' and meta['plot'] in ('', None, 'None'): meta['plot'] = self.get_en_overview(tmdb)
			# meta['?'] = result.get('popularity', '')
			meta['poster'] = '%s%s' % (self.poster_path, result['poster_path']) if result.get('poster_path') else ''
			meta['tvshow_poster'] = meta['poster'] # check that this new dict key is used throughout
			try:
				_alt_posters = _poster_list(result['images']['posters'], self.art_lang, self.poster_path)
				if self.prefer_en_titles and _alt_posters:
					meta['poster'] = _alt_posters[0] # póster base también en inglés (aunque la rotación esté apagada)
					meta['tvshow_poster'] = meta['poster'] # mantener sincronizado (se copió antes del override)
				if len(_alt_posters) > 1: meta['posters_all'] = _alt_posters # solo guardar si hay alternativas reales para rotar
			except: pass
			try: meta['country_codes'] = [i['iso_3166_1'] for i in result['production_countries']]
			except: meta['country_codes'] = ''
			meta['seasons'] = result.get('seasons')
			meta['status'] = result.get('status')
			# meta['counts'] = self.seasonCountParse(meta['seasons']) # check on performance hit
			meta['counts'] = dict(sorted({(str(i['season_number']), i['episode_count']) for i in meta['seasons']}, key=lambda k: int(k[0])))
			if meta['status'].lower in ('ended', 'canceled'):
				meta['total_aired_episodes'] = result.get('number_of_episodes')
			else:
				meta['total_aired_episodes'] = self.airedEpisodesParse(meta['seasons'], meta['last_episode_to_air'])
				# meta['total_aired_episodes'] = sum([i['episode_count'] for i in meta['seasons'] if i['season_number'] < meta['last_episode_to_air']['season_number'] and i['season_number'] != 0]) + meta['last_episode_to_air']['episode_number']
			meta['spoken_languages'] = result.get('spoken_languages')
			meta['tagline'] = result.get('tagline', '')
			meta['type'] = result.get('type')
			meta['rating'] = result.get('vote_average', '')
			meta['votes'] = result.get('vote_count', '')
			crew = result.get('credits', {}).get('crew')
			try: meta['director'] = ', '.join([d['name'] for d in [x for x in crew if x['job'] == 'Director']])
			except: meta['director'] = ''
			try: meta['writer'] = ', '.join([w['name'] for w in [y for y in crew if y['job'] == 'Writer']]) # movies also contains "screenplay", "author", "novel". See if any apply for shows
			except: meta['writer'] = ''
			meta['castandart'] = []
			for person in result['credits']['cast']:
				try: meta['castandart'].append({'name': person['name'], 'role': person['character'], 'thumbnail': ('%s%s' % (self.profile_path, person['profile_path']) if person.get('profile_path') else '')})
				except: pass
				if len(meta['castandart']) == 150: break
			mpaa = []
			mpaa += [x['rating'] for x in result['content_ratings']['results'] if x['iso_3166_1'] == self.mpa_country]
			mpaa += [x['rating'] for x in result['content_ratings']['results'] if x['iso_3166_1'] == 'US']
			try: meta['mpaa'] = mpaa[0]
			except: 
				try: meta['mpaa'] = result['content_ratings'][0]['rating']
				except: meta['mpaa'] = ''
			if meta['mpaa']: meta['mpaa'] = getSetting('mpa.prefix') + meta['mpaa']
			ids = result.get('external_ids', {})
			meta['imdb'] = str(ids.get('imdb_id', '')) if ids.get('imdb_id') else ''
			meta['imdbnumber'] = meta['imdb']
			meta['tvdb'] = str(ids.get('tvdb_id', '')) if ids.get('tvdb_id') else ''
			# make aliases match what trakt returns in sources module for title checking scrape results
			try: meta['aliases'] = [{'title': x['title'], 'country': x['iso_3166_1'].lower()} for x in result.get('alternative_titles', {}).get('results') if x.get('iso_3166_1').lower() in ('us', 'uk', 'gb')]
			except: meta['aliases'] = []
			try:
				# v1.0.46: prefiere Trailer oficial de mayor resolución; Teaser solo como último recurso
				_vids = [x for x in result['videos']['results'] if x['site'] == 'YouTube' and x['type'] in ('Trailer', 'Teaser')]
				_vids.sort(key=lambda x: (x['type'] != 'Trailer', not x.get('official'), -(x.get('size') or 0)))
				meta['trailer'] = _vids[0]['key']
				meta['trailer'] = control_trailer % meta['trailer']
			except: meta['trailer'] = ''
			# meta['banner'] = '' # not available from TMDb
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return meta

	def get_season_request(self, tmdb, season):
		if not tmdb: return None
		try:
			result = None
			url = '%s%s' % (base_link, 'tv/%s/season/%s?api_key=%s&language=%s&append_to_response=credits' % (tmdb, season, self.API_key, self.lang))
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_seasonEpisodes_meta(self, tmdb, season): # builds episodes meta from "/season/?" request
		if not tmdb and not season: return None
		try:
			if not tmdb: return None
			result = self.get_season_request(tmdb, season)
			if result is None: return
			if '404:NOT FOUND' in result: return result
			meta = {}
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		try:
			meta['premiered'] = str(result.get('air_date', '')) if result.get('air_date') else '' # Kodi season level Information gui seems no longer available in 19 unless you use "mediatype = tvshow" for seasons
			episodes = []
			unaired_count = 0
			for episode in result['episodes']:
				episode_meta = {}
				episode_meta['mediatype'] = 'episode'
				episode_meta['premiered'] = str(episode.get('air_date', '')) if episode.get('air_date') else '' # this is season premiered, not series premiered.
				if not episode_meta['premiered']: # access to "status" not available at this level
					unaired_count += 1
					pass
				elif int(re.sub(r'[^0-9]', '', str(episode_meta['premiered']))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
					unaired_count += 1
				# try: meta['year'] = meta['premiered'][:4] # DO NOT USE, this will make the year = season premiered but scrapers want series premiered for year.
				# except: meta['year'] = ''
				episode_meta['episode'] = episode['episode_number']
				crew = episode.get('crew')
				try: episode_meta['director'] = ', '.join([d['name'] for d in [x for x in crew if x['job'] == 'Director']])
				except: episode_meta['director'] = ''
				try: episode_meta['writer'] = ', '.join([w['name'] for w in [y for y in crew if y['job'] == 'Writer']]) # movies also contains "screenplay", "author", "novel". See if any apply for shows
				except: episode_meta['writer'] = ''
				episode_meta['tmdb_epID'] = episode['id']
				episode_meta['title'] = episode['name']
				episode_meta['season'] = episode['season_number']
				episode_meta['plot'] = episode.get('overview', '') if episode.get('overview') else ''
				if self.lang != 'en' and episode_meta['plot'] in ('', None, 'None'): episode_meta['plot'] = self.get_en_overview(tmdb, episode_meta['season'], episode_meta['episode'], 'episode')
				episode_meta['code'] = episode['production_code']
				episode_meta['thumb'] = '%s%s' % (self.still_path, episode['still_path']) if episode.get('still_path') else ''
				episode_meta['rating'] = episode['vote_average']
				episode_meta['votes'] = episode['vote_count']
				episodes.append(episode_meta)
			meta['season_isAiring'] = 'true' if unaired_count > 0 else 'false' # I think this should be in episodes module where it has access to "showSeasons" meta for "status"
			meta['seasoncount'] = len(result.get('episodes')) #seasoncount = number of episodes for given season

			# aired_episodes = int(meta['seasoncount']) - unaired_count
			# from resources.lib.modules import log_utils
			# log_utils.log('aired_episodes=%s: tmdb_id=%s' % (str(aired_episodes), tmdb))

			# meta['tvseasontitle'] = result['name'] # seasontitle ?
			meta['plot'] = result.get('overview', '') if result.get('overview') else '' # Kodi season level Information seems no longer available in 19
			meta['tmdb'] = tmdb
			meta['poster'] = '%s%s' % (self.poster_path, result['poster_path']) if result.get('poster_path') else ''
			meta['season_poster'] = meta['poster']
			meta['season'] = result.get('season_number')
			meta['castandart'] = []
			for person in result['credits']['cast']:
				try: meta['castandart'].append({'name': person['name'], 'role': person['character'], 'thumbnail': ('%s%s' % (self.profile_path, person['profile_path']) if person.get('profile_path') else '')})
				except: pass
				if len(meta['castandart']) == 150: break
			# meta['banner'] = '' # not available from TMDb
			meta['episodes'] = episodes
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return meta

	def get_episodes_request(self, tmdb, season, episode): # Don't think I'll use this at all
		if not tmdb and not season and not episode: return None
		try:
			result = None
			url = '%s%s' % (base_link, 'tv/%s/season/%s/episode/%s?api_key=%s&language=%s&append_to_response=credits' % (tmdb, season, episode, self.API_key, self.lang))
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_art(self, tmdb):
		if not tmdb: return None
		url = self.art_link % tmdb
		art3 = self.get_request(url)
		if art3 is None: return
		if '404:NOT FOUND' in art3: return art3
		try:
			poster3 = self.parse_art(art3['posters'])
			poster3 = '%s%s' % (self.poster_path, poster3) if poster3 else ''
		except: poster3 = ''
		try:
			fanart3 = self.parse_art(art3['backdrops'])
			fanart3 = '%s%s' % (self.fanart_path, fanart3) if fanart3 else ''
		except: fanart3 = ''
		extended_art = {'extended': True, 'poster3': poster3, 'fanart3': fanart3}
		return extended_art

	def parse_art(self, img):
		if not img: return None
		try:
			ret_img = [(x['file_path'], x['vote_average']) for x in img if any(value == x.get('iso_639_1') for value in (self.art_lang, 'null', '', None))]
			if not ret_img: ret_img = [(x['file_path'], x['vote_average']) for x in img]
			if not ret_img: return None
			if len(ret_img) >1: ret_img = sorted(ret_img, key=lambda x: int(x[1]), reverse=True)
			ret_img = [x[0] for x in ret_img][0]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return None
		return ret_img

	def get_en_overview(self, tmdb, season=None, episode=None, level_type='show'): # fallback for when self.lang != 'en'
		if not tmdb: return None
		overview = None
		try:
			if level_type == 'show':
				url = '%s%s' % (base_link, 'tv/%s?api_key=%s&language=en,en-US' % (tmdb, self.API_key))
			else:
				url = '%s%s' % (base_link, 'tv/%s/season/%s/episode/%s?api_key=%s&language=en,en-US' % (tmdb, season, episode, self.API_key))
			result = self.get_request(url)
			overview = result.get('overview')
			if overview: overview = 'Translation Not Available:\n' + overview
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return overview

	def get_credits(self, tmdb):
		if not tmdb: return None
		result = None
		try:
			url = base_link + 'tv/%s/credits?api_key=%s' % (tmdb, self.API_key)
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_external_ids(self, tmdb):
		if not tmdb: return None
		try:
			result = None
			url = base_link + 'tv/%s/external_ids?api_key=%s' % (tmdb, self.API_key)
			result = self.get_request(url)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def IdLookup(self, imdb, tvdb=None):
		if not imdb and not tvdb: return
		try:
			result = None
			find_url = base_link + 'find/%s?api_key=%s&external_source=%s'
			if imdb and imdb.startswith('tt'): # trakt has some bad data with url's in ids
				url = find_url % (imdb, self.API_key, 'imdb_id')
				try: result = self.get_request(url)['tv_results'][0]
				except: pass
			if tvdb and (not result or '404:NOT FOUND' in result):
				url = find_url % (tvdb, self.API_key, 'tvdb_id')
				result = self.get_request(url)
				if result is None: return
				if '404:NOT FOUND' in result: return result
				try: result = result['tv_results'][0]
				except: pass
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		return result

	def get_counts(self, tmdb): ## for show pack scraping pack size calc 
		if not tmdb: return None
		showSeasons = cache.get(self.get_showSeasons_meta, 96, tmdb)
		return self.seasonCountParse(showSeasons.get('seasons'))

	def seasonCountParse(self, seasons):
		if not seasons: return
		counts = {}
		for s in seasons:
			season = str(s.get('season_number'))
			counts[season] = s.get('episode_count')
		return counts

	def airedEpisodesParse(self, seasons, last_aired):
		if not seasons or not last_aired: return
		lastaired_season = last_aired.get('season_number', '')
		total_aired_episodes = 0
		for s in seasons:
			if any(value == s.get('season_number') for value in (0, lastaired_season)): continue
			if s.get('season_number') > lastaired_season: continue
			total_aired_episodes += s.get('episode_count', 0)
		total_aired_episodes += last_aired.get('episode_number', 0)
		return total_aired_episodes

	def get_season_isAiring(self, tmdb, season): # for pack scraping to skip if season is still airing
		if not tmdb or not season: return None
		seasonEpisodes = cache.get(self.get_seasonEpisodes_meta, 96, tmdb, season) # "status" not available this level so must iterate all eps
		unaired_count = 0
		for item in seasonEpisodes['episodes']:
			try:
				premiered = str(item.get('premiered', '')) if item.get('premiered') else ''
				if not premiered: unaired_count += 1
				elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))): unaired_count += 1
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return 'true' if unaired_count > 0 else 'false'

	def get_networks(self):
		# Curated tuples: (display_name, network_id, logo).
		# logo = "" -> resolved live from TMDb /network/{id} (cached 30 days).
		# network_id may be pipe-joined ('4353|5192') to OR duplicate TMDb networks.
		networks = [
			('A&E', '129', 'https://i.imgur.com/xLDfHjH.png'),
			('ABC (US)', '2', 'https://i.imgur.com/qePLxos.png'),
			('ABC (AU)', '18', 'https://i.postimg.cc/K8N5BGVC/abc-australia.png'),
			('ABC Family', '75', 'https://i.postimg.cc/BtfXj3N6/abc-family.png'),
			('Acorn TV', '2697', 'https://i.postimg.cc/0jyYrWJJ/logo.png'),
			('Adult Swim', '80', 'https://i.imgur.com/jCqbRcS.png'),
			('Amazon', '1024', 'https://i.imgur.com/ru9DDlL.png'),
			('AMC', '174', 'https://i.imgur.com/ndorJxi.png'),
			('AHC', '1430', 'https://i.postimg.cc/ydzYKK6Y/ahc.png'),
			('Animal Planet', '91', 'https://i.imgur.com/olKc4RP.png'),
			('Animax', '171', 'https://i.postimg.cc/J4SfvqzR/animax.png'),
			('Apple TV+', '2552', 'https://i.imgur.com/fAQMVNp.png'),
			('AT-X', '173', 'https://i.imgur.com/JshJYGN.png'),
			('Audience', '251', 'https://i.imgur.com/5Q3mo5A.png'),
			('AXN', '2003', 'https://i.postimg.cc/x1T6sNK9/axn.png'),
			('BBC America', '493', 'https://i.imgur.com/TUHDjfl.png'),
			('BBC One', '4', 'https://i.imgur.com/u8x26te.png'),
			('BBC Two', '332', 'https://i.imgur.com/SKeGH1a.png'),
			('BBC Three', '3', 'https://i.imgur.com/SDLeLcn.png'),
			('BBC Four', '100', 'https://i.imgur.com/PNDalgw.png'),
			('BET', '24', 'https://i.imgur.com/ZpGJ5UQ.png'),
			('BET+', '3343', 'https://i.imgur.com/ZpGJ5UQ.png'),
			('Blackpills', '2097', 'https://i.imgur.com/8zzNqqq.png'),
			('Brat', '2451', 'https://i.imgur.com/x2aPEx1.png'),
			('Bravo', '74', 'https://i.imgur.com/TmEO3Tn.png'),
			('Cartoon Network', '56', 'https://i.imgur.com/zmOLbbI.png'),
			('CBC', '23', 'https://i.imgur.com/unQ7WCZ.png'),
			('CBS', '16', 'https://i.imgur.com/8OT8igR.png'),
			('CBS All Access', '1709', 'https://i.postimg.cc/ZRV3k8DY/cbs-all-access.png'),
			('CNBC', '175', 'https://i.postimg.cc/5tmQv5J5/cnbc.png'),
			('Channel 4', '26', 'https://i.imgur.com/6ZA9UHR.png'),
			('Channel 5', '99', 'https://i.imgur.com/5ubnvOh.png'),
			('Cinemax', '359', 'https://i.imgur.com/zWypFNI.png'),
			('City (CA)', '92', 'https://i.postimg.cc/FzBVXNYC/city.png'),
			('Comedy Central', '47', 'https://i.imgur.com/ko6XN77.png'),
			('Crackle', '928', 'https://i.imgur.com/53kqZSY.png'),
			('CTV', '110', 'https://i.imgur.com/qUlyVHz.png'),
			('CuriosityStream', '2349', 'https://i.imgur.com/5wJsQdi.png'),
			('CW', '71', 'https://i.imgur.com/Q8tooeM.png'),
			('CW Seed', '1049', 'https://i.imgur.com/nOdKoEy.png'),
			('DC Universe', '2243', 'https://i.postimg.cc/nM8hNMZc/dc-universe.png'),
			('Discovery Channel', '64', 'https://i.imgur.com/8UrXnAB.png'),
			('Discovery+', '4353|5192', 'https://i.imgur.com/8UrXnAB.png'), # TMDb keeps two duplicate Discovery+ networks; pipe = OR
			('Discovery ID', '244', 'https://i.imgur.com/07w7BER.png'),
			('Disney+', '2739', 'https://i.postimg.cc/zBNHHbKZ/disney.png'),
			('Disney Channel', '54', 'https://i.imgur.com/ZCgEkp6.png'),
			('Disney Junior', '281', 'https://i.postimg.cc/mgGR708M/EqPPq5S.png'),
			('Disney XD', '44', 'https://i.imgur.com/PAJJoqQ.png'),
			('E! Entertainment', '76', 'https://i.imgur.com/3Delf9f.png'),
			('E4', '136', 'https://i.imgur.com/frpunK8.png'),
			('Epix', '922', 'https://i.postimg.cc/3JMv8Q1g/epix.png'),
			# ('Fearnet', '635', 'https://i.imgur.com/CdJ6fZt.png'),
			('FOX', '19', 'https://i.imgur.com/6vc0Iov.png'),
			('Freeform', '1267', 'https://i.imgur.com/f9AqoHE.png'),
			('Fusion', '1769', 'https://i.postimg.cc/kGBMhKbb/NPxic1M.png'),
			('FX', '88', 'https://i.imgur.com/aQc1AIZ.png'),
			('Hallmark', '384', 'https://i.imgur.com/zXS64I8.png'),
			# ('Hallmark Movies & Mysteries', '2300', 'https://static.tvmaze.com/uploads/images/original_untouched/13/34664.jpg'),
			('HBO', '49', 'https://i.imgur.com/Hyu8ZGq.png'),
			('HBO Max', '3186', 'https://i.postimg.cc/pLdCcdGt/hbo-max.png'), # not sure I want this
			('HGTV', '210', 'https://i.imgur.com/INnmgLT.png'),
			('History Channel', '65', 'https://i.imgur.com/LEMgy6n.png'),
			('H2', '849', 'https://i.imgur.com/OvkmoDA.png'),
			('Hulu', '453', 'https://i.imgur.com/cLVo7NH.png'),
			('ITV', '9', 'https://i.imgur.com/5Hxp5eA.png'),
			('Lifetime', '34', 'https://i.imgur.com/tvYbhen.png'),
			('Motor Trend', '2444', 'https://i.postimg.cc/cCDRWZbt/motor-trend.png'),
			('MTV', '33', 'https://i.imgur.com/QM6DpNW.png'),
			('National Geographic', '43', 'https://i.imgur.com/XCGNKVQ.png'),
			('NBC', '6', 'https://i.imgur.com/yPRirQZ.png'),
			('Netflix', '213', 'https://i.postimg.cc/c4vHp9wV/netflix.png'),
			('Nick Junior', '35', 'https://i.imgur.com/leuCWYt.png'),
			('Nickelodeon', '13', 'https://i.imgur.com/OUVoqYc.png'),
			('Nicktoons', '224', 'https://i.imgur.com/890wBrw.png'),
			('Oxygen', '132', 'https://i.imgur.com/uFCQvbR.png'),
			('OWN', '827', 'https://i.postimg.cc/qqFZyk58/own.png'),
			# ('Playboy TV', '225', 'https://i.postimg.cc/sxVWPpL3/playboy-tv.png'),
			('Paramount Network', '2076', 'https://i.postimg.cc/fL9YCz5R/paramount-network.png'),
			('PBS', '14', 'https://i.imgur.com/r9qeDJY.png'),
			('Peacock', '3353', 'https://i.postimg.cc/76m4v7VW/NBCUniversal-Peacock-Logo.png'),
			('Reelz', '367', 'https://i.postimg.cc/7P7byqjF/reelz.png'),
			('Showcase (AU)', '1630', 'https://i.postimg.cc/C5JVs11Q/showcase-ca.png'),
			('Showcase (CA)', '105', 'https://i.postimg.cc/C5JVs11Q/showcase-ca.png'),
			('Showtime', '67', 'https://i.imgur.com/SawAYkO.png'),
			('Sky1', '214', 'https://i.imgur.com/xbgzhPU.png'),
			('Sky Atlantic', '1063', 'https://i.imgur.com/9u6M0ef.png'),
			('SkyShowtime', '5944', 'https://i.postimg.cc/76GpVGxT/skyshowtime-2022-color.png'),
			('Smithsonian', '658', 'https://i.postimg.cc/GtZ5RkNy/smithsonian.png'),
			('Spike', '55', 'https://i.postimg.cc/zGs4WW7f/spike.png'),
			('Stan (AU)', '1255', ''),
			('Starz', '318', 'https://i.imgur.com/Z0ep2Ru.png'),
			('Sundance TV', '270', 'https://i.imgur.com/qldG5p2.png'),
			('Syfy', '77', 'https://i.imgur.com/9yCq37i.png'),
			('TBS', '68', 'https://i.imgur.com/RVCtt4Z.png'),
			('TLC', '84', 'https://i.imgur.com/c24MxaB.png'),
			('TNT', '41', 'https://i.imgur.com/WnzpAGj.png'),
			('Travel Channel', '209', 'https://i.imgur.com/mWXv7SF.png'),
			('TruTV', '364', 'https://i.imgur.com/HnB3zfc.png'),
			('TV Land', '397', 'https://i.imgur.com/1nIeDA5.png'),
			('TV One', '150', 'https://i.imgur.com/gGCTa8s.png'),
			('USA Network', '30', 'https://i.imgur.com/Doccw9E.png'),
			('VH1', '158', 'https://i.imgur.com/IUtHYzA.png'),
			('Viceland', '1339', 'https://i.postimg.cc/0N1Hrv5M/viceland.png'),
			('WB', '21', 'https://i.postimg.cc/kg4PycCn/the-wb.png'),
			('WE TV', '448', 'https://i.postimg.cc/1ztHyxt6/we.png'),
			('WGN America', '202', 'https://i.imgur.com/TL6MzgO.png'),
			('WWE Network', '1025', 'https://i.imgur.com/JjbTbb2.png'),
			('YouTube Premium', '1436', 'https://i.postimg.cc/vHtqdhyt/youtube-premium.png')]
		# Resolve missing logos live from TMDb network details (30-day TTL; logo paths
		# are very stable). One small cached call per network with an empty logo.
		out = []
		for name, nid, logo in networks:
			if not logo:
				try:
					first_id = str(nid).split('|')[0]
					url = base_link + 'network/%s?api_key=%s' % (first_id, self.API_key)
					data = cache.get(self.get_request, 720, url)
					lp = data.get('logo_path') if isinstance(data, dict) else None
					if lp: logo = 'https://image.tmdb.org/t/p/original' + lp
				except Exception:
					from resources.lib.modules import log_utils
					log_utils.error()
			out.append((name, nid, logo))
		return out

	def get_originals(self):
		return [
			('Amazon', '1024', 'https://i.imgur.com/ru9DDlL.png'),
			('Hulu', '453', 'https://i.imgur.com/cLVo7NH.png'),
			('Netflix', '213', 'https://i.postimg.cc/c4vHp9wV/netflix.png')]


class Auth:
	def __init__(self):
		self.auth_base_link = '%s%s' % (base_link, 'authentication')

	def create_session_id(self):
		try:
			from resources.lib.modules.control import setSetting
			if getSetting('tmdb.username') == '' or getSetting('tmdb.password') == '': return notification(message='TMDb Account info missing', icon='ERROR')
			url = self.auth_base_link + '/token/new?api_key=%s' % self.API_key
			result = requests.get(url, timeout=15).json()
			token = result.get('request_token')
			url2 = self.auth_base_link + '/token/validate_with_login?api_key=%s' % self.API_key
			username = getSetting('tmdb.username')
			password = getSetting('tmdb.password')
			post2 = {"username": "%s" % username,
							"password": "%s" % password,
							"request_token": "%s" % token}
			result2 = requests.post(url2, data=post2, timeout=15).json()
			url3 = self.auth_base_link + '/session/new?api_key=%s' % self.API_key
			post3 = {"request_token": "%s" % token}
			result3 = requests.post(url3, data=post3, timeout=15).json()
			if result3.get('success') is True:
				session_id = result3.get('session_id')
				msg = '%s' % ('username =' + username + '[CR]password =' + password + '[CR]token = ' + token + '[CR]confirm?')
				if yesnoDialog(msg, '', ''):
					setSetting('tmdb.session_id', session_id)
					notification(message='TMDb Successfully Authorized')
				else: notification(message='TMDb Authorization Cancelled')
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def revoke_session_id(self):
		try:
			from resources.lib.modules.control import setSetting
			if getSetting('tmdb.session_id') == '': return
			url = self.auth_base_link + '/session?api_key=%s' % self.API_key
			post = {"session_id": "%s" % getSetting('tmdb.session_id')}
			result = requests.delete(url, data=post, timeout=15).json()
			if result.get('success') is True:
				setSetting('tmdb.session_id', '')
				notification(message='TMDb session_id successfully deleted')
			else:
				from resources.lib.modules import log_utils
				log_utils.log('TMDb Revoke session_id FAILED: %s' % result.get('status_message', ''), __name__, log_utils.LOGWARNING)
				if 'id is invalid or not found' in result.get('status_message', ''):
					setSetting('tmdb.session_id', '')
					notification(message=result.get('status_message', ''), icon='ERROR')
				else: notification(message='TMDb session_id deletion FAILED', icon='ERROR')
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
