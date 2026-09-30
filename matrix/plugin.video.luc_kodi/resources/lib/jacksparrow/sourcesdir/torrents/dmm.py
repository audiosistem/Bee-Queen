
"""
	jacksparrowscrapers Project
"""

import threading, time
import requests
from resources.lib.jacksparrow import client, source_utils
from resources.lib.jacksparrow.control import setting as getSetting


# v1.0.56 — Limitador de DMM (verificado en el codigo publico del proyecto,
# src/services/rateLimit/middlewareRateLimiter.ts):
#     torrents: { rateLimit: 1, windowSeconds: 2 }
# O sea /api/torrents/* admite UNA peticion cada 2 segundos POR IP, y el 429
# se devuelve ANTES de validar el token (withIpRateLimit envuelve al handler),
# por eso el diagnostico de la v1.0.54 nunca llego a ver si la autenticacion
# era valida. No es un cierre a terceros: es una cuota. Este candado serializa
# las peticiones del addon y respeta el hueco minimo + la cabecera Retry-After.
#
# v1.0.57 — el candado ya NO se mantiene tomado durante la peticion HTTP. El
# servidor cuenta la ventana desde que le LLEGA la peticion, asi que reservar
# el hueco antes de salir (y soltar el candado acto seguido) espacia igual de
# bien y evita que un hilo hermano se quede bloqueado hasta 7 s enteros
# esperando a que termine una peticion ajena.
#
# v1.0.76 — el token ya no se calcula aqui. DMM movio la firma al servidor el
# 31-ago-2026 y cerro el mismo dia el periodo de gracia que aun aceptaba los
# tokens acuñados en el cliente, asi que el algoritmo que vivia al final de este
# fichero devolvia 403 en todas las busquedas. Se pide con GET /api/challenge y
# se cachea; toda esa logica esta en resources/lib/debrid/dmm.py, que es la que
# tambien usa la comprobacion de cache de Real-Debrid — asi una busqueda acuña
# un token y no dos. Ese endpoint tiene su PROPIO contador de limite desde el
# 2-sep-2026, de modo que pedir el token no gasta el hueco de /api/torrents.
_RATE_LOCK = threading.Lock()
_NEXT_ALLOWED = [0.0]  # epoch a partir del cual se puede volver a llamar
_MIN_GAP = 2.2         # ventana de 2 s + margen
_MAX_WAIT = 3.0        # tope de espera por reintento (presupuesto del scraper)
_PAGE_ROWS = 50        # filas por tabla y pagina que sirve DMM (offset = page * 50)


class source:
	timeout = 7
	priority = 3
	pack_capable = False # packs parsed in sources function
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://debridmediamanager.com"
		self.movieSearch_link = '/api/torrents/movie?imdbId=%s'
		self.tvSearch_link = '/api/torrents/tv?imdbId=%s&seasonNum=%s'
		self.min_seeders = 0
		# v1.0.57: segunda pagina opcional. Cuesta un hueco mas del limitador
		# (~2,2 s de latencia extra) y por eso viene apagada por defecto.
		self.deep_search = getSetting('dmm.deep_search') == 'true'

	def sources(self, data, hostDict):
		self._results = []
		if not data: return self._results
		self._results_append = self._results.append
		try:
			self.title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			self.title = self.title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
			self.aliases = data['aliases']
			self.episode_title = data['title'] if 'tvshowtitle' in data else None
			# v1.0.57: .get() en vez de indexar. Si el host llamaba sin
			# 'total_seasons' el KeyError caia en el except de abajo y se
			# perdia la busqueda ENTERA, no solo la deteccion de packs.
			self.total_seasons = data.get('total_seasons') if 'tvshowtitle' in data else None
			self.year = data['year']
			self.imdb = data['imdb']
			self.season = data['season'] if 'tvshowtitle' in data else None
			self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else self.year
			self.season_x = data['season'] if 'tvshowtitle' in data else None
			self.season_xx = data['season'].zfill(2) if 'tvshowtitle' in data else None
			if 'timeout' in data: self.timeout = int(data['timeout'])
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			# v1.0.56: UNA sola peticion por busqueda, sin hilos. Pedir las
			# paginas 0 y 1 en paralelo garantizaba un 429 en la segunda (1
			# peticion / 2 s por IP). La pagina 0 ya devuelve hasta 50 filas
			# de cada una de las dos tablas del servidor (scrapedTrue +
			# scraped, offset = page * 50), suficiente de sobra para el panel.
			# v1.0.57: con "Busqueda profunda" activada se pide ademas la
			# pagina 1, pero SERIALIZADA detras del mismo candado — nunca en
			# paralelo. Solo tiene sentido si la 0 vino llena: si el servidor
			# devolvio menos filas de las que caben, no hay pagina siguiente.
			if self.season: base = '%s%s' % (self.base_link, self.tvSearch_link % (self.imdb, self.season))
			else: base = '%s%s' % (self.base_link, self.movieSearch_link % self.imdb)

			rows = self.get_sources('%s&page=0' % base)
			if self.deep_search and rows >= _PAGE_ROWS:
				self.get_sources('%s&page=1' % base)
			return self._results
		except:
			source_utils.scraper_error('DMM')
			return self._results

	def api_get(self, url):
		"""Peticion serializada a /api/torrents con un unico reintento ante 429.
		Devuelve la lista de resultados, o None si no hay nada que parsear."""
		from resources.lib.modules import log_utils
		from resources.lib.debrid.dmm import get_secret, invalidate_secret
		headers = {'User-Agent': client.randomagent(), 'Accept-Encoding': 'gzip, deflate, br', 'Accept': '*/*'}
		attempts = 2
		while attempts:
			attempts -= 1
			# v1.0.76: el token se pide FUERA del candado. Antes se generaba
			# dentro porque era una cuenta local de microsegundos; ahora puede
			# costar una peticion de red y bloquearia a los hilos hermanos.
			# Viene cacheado ~2 min, asi que lo normal es que no salga a la red.
			dmmProblemKey, solution = get_secret()
			if not dmmProblemKey:
				log_utils.log('DMM: sin token, se omite la busqueda', __name__, log_utils.LOGDEBUG)
				return None
			# v1.0.57: el hueco siguiente se reserva AQUI, antes de soltar el
			# candado, y la peticion sale ya fuera de la seccion critica.
			with _RATE_LOCK:
				gap = _NEXT_ALLOWED[0] - time.time()
				if gap > 0: time.sleep(min(gap, _MAX_WAIT))
				_NEXT_ALLOWED[0] = time.time() + _MIN_GAP
			params = {'dmmProblemKey': dmmProblemKey, 'solution': solution}
			# v1.0.57: un corte de red o un timeout ya no sube como excepcion
			# hasta el except desnudo de get_sources() — eso volcaba un
			# traceback entero por cada hipo de la conexion.
			try: results = requests.get(url, params=params, headers=headers, timeout=self.timeout)
			except requests.exceptions.RequestException as e:
				log_utils.log('DMM: fallo de red (%s: %s)' % (type(e).__name__, e), __name__, log_utils.LOGDEBUG)
				return None
			status = results.status_code
			if status == 200:
				try: payload = results.json()
				except Exception: payload = None
				files = payload.get('results') if isinstance(payload, dict) else None
				if files is None:
					body = (results.text or '')[:300].replace('\n', ' ').replace('\r', ' ')
					log_utils.log('DMM: 200 sin clave "results" | Content-Type=%s | body[:300]=%r'
							% (results.headers.get('Content-Type', ''), body), __name__, log_utils.LOGWARNING)
				return files
			if status == 204:
				# Titulo aun no indexado: DMM lo acaba de encolar para scrapear.
				# En la siguiente busqueda del mismo titulo ya suele haber datos.
				# v1.0.76: el 204 es hoy mucho mas raro. Ante una primera pagina
				# vacia el servidor rellena la tabla al vuelo desde Debridio
				# antes de rendirse, asi que un titulo nuevo suele devolver ya
				# resultados en la MISMA peticion. La cabecera 'status' dice si
				# quedo encolado ('requested') o si ya lo estaba ('processing').
				log_utils.log('DMM: 204, titulo no indexado todavia (%s) | %s'
						% (results.headers.get('status', 'requested'), client.scrub_url(url)), __name__, log_utils.LOGDEBUG)
				return None
			if status == 429:
				retry_after = 0.0
				try: retry_after = float(results.headers.get('Retry-After') or 0)
				except Exception: pass
				if attempts:
					with _RATE_LOCK:
						_NEXT_ALLOWED[0] = max(_NEXT_ALLOWED[0], time.time() + min(max(retry_after, _MIN_GAP), _MAX_WAIT))
					continue
				log_utils.log('DMM: 429 tras el reintento (limite 1 peticion/2 s por IP)', __name__, log_utils.LOGDEBUG)
				return None
			if status == 403:
				# v1.0.76: el reloj del dispositivo ya no interviene — la marca
				# de tiempo la pone el servidor al acuñar. Un 403 aqui significa
				# token caducado en el filo del TTL de 5 min o secreto rotado
				# bajo nuestros pies, y las dos cosas se arreglan reacuñando.
				if attempts:
					invalidate_secret(dmmProblemKey)
					continue
				try: reason = (results.json() or {}).get('errorMessage') or ''
				except Exception: reason = ''
				log_utils.log('DMM: 403 tras reacuñar el token (%s)' % (reason or 'sin detalle'), __name__, log_utils.LOGWARNING)
				return None
			body = (results.text or '')[:300].replace('\n', ' ').replace('\r', ' ')
			log_utils.log('DMM: HTTP %s | Content-Type=%s | body[:300]=%r'
					% (status, results.headers.get('Content-Type', ''), body), __name__, log_utils.LOGWARNING)
			return None
		return None

	def get_sources(self, url):
		"""Parsea una pagina. Devuelve cuantas filas CRUDAS trajo el servidor
		(no cuantas pasaron el filtro), para decidir si pedir la siguiente."""
		try:
			files = self.api_get(url)
			if not files: return 0
		except:
			source_utils.scraper_error('DMM')
			return 0

		for file in files:
			try:
				package, episode_start = None, 0
				hash = file['hash']
				name = source_utils.clean_name(file['title'])

				if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year):
					if self.total_seasons is None: continue
					valid, episode_start, episode_end = source_utils.filter_season_pack(self.title, self.aliases, self.year, self.season_x, name)
					if not valid:
						valid, last_season = source_utils.filter_show_pack(self.title, self.aliases, self.imdb, self.year, self.season_x, name, self.total_seasons)
						if not valid: continue
						else: package = 'show'
					else: package = 'season'
				name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
				if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
				if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

				quality, info = source_utils.get_release_quality(name_info, url)
				# v1.0.83. Faltaba, y era el unico de los 18 scrapers sin ella.
				# Importa por un motivo concreto: info_from_name() hace
				# re.sub(r'[^a-z0-9]+', '.') sobre el nombre, asi que el '+' de
				# HDR10+ desaparece antes de llegar a getFileType(). Sin esta
				# llamada, que recibe el nombre SIN limpiar, DMM no podia
				# distinguir HDR10+ de HDR10 jamas. Lo mismo con 10BIT.
				info += [t for t in source_utils.get_extra_tags(name) if t not in info]
				try:
					size = f"{float(file['fileSize']) / 1024:.2f} GB"
					dsize, isize = source_utils._size(size)
					info.insert(0, isize)
				except: dsize = 0
				info = ' | '.join(info)

				item = {
					'source': 'torrent', 'language': 'en', 'direct': False, 'debridonly': True,
					'provider': 'dmm', 'hash': hash, 'url': url, 'name': name, 'name_info': name_info,
					'quality': quality, 'info': info, 'size': dsize, 'seeders': 0
				}
				if package: item['package'] = package
				if package == 'show': item.update({'last_season': last_season})
				if episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end}) # for partial season packs
				self._results_append(item)
			except:
				source_utils.scraper_error('DMM')
		return len(files)
