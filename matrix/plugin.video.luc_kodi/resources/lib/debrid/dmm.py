import threading, time
import requests


# ─────────────────────────────────────────────────────────────────────────────
# Token de DMM — v1.0.76
#
# Hasta el 31-ago-2026 el par (dmmProblemKey, solution) se calculaba EN EL
# CLIENTE, con un algoritmo y un salt que viajaban dentro del bundle del
# navegador, asi que cualquiera podia acuñarlo sin pedir permiso. Ese dia el
# proyecto lo movio al servidor:
#
#   dd6ff80  fix: sign availability tokens server-side instead of in the browser
#   cc24c36  fix: stop accepting the legacy client-signed availability token
#
# Ahora la firma es un HMAC-SHA256 con DMM_PROBLEM_SECRET, una variable de
# entorno que NUNCA sale del servidor (src/utils/problemToken.ts), y el periodo
# de gracia que aun aceptaba los tokens viejos se cerro el mismo dia. Por eso
# desde entonces TODA peticion del addon recibia 403 "Authentication error": no
# era un bloqueo a terceros ni un problema de red, era un algoritmo que ya no
# existe.
#
# La via soportada es pedir el token: GET /api/challenge devuelve {token, hash}
# y se envian como dmmProblemKey + solution. El propio cliente web hace esto
# (src/utils/token.ts) y cachea el par ~2 min frente a un TTL de servidor de 5,
# para que una peticion lenta nunca llegue con el token recien caducado. Aqui se
# replica ese margen exacto.
#
# El limitador tambien cambio (f2b90c9, 2-sep-2026): cada configuracion tiene ya
# su propio contador, asi que /api/challenge (bucket "default", 5/s por IP) NO
# gasta el presupuesto de /api/torrents (bucket "torrents", 1 cada 2 s). Pedir
# el token sale gratis para el scraper.
# ─────────────────────────────────────────────────────────────────────────────
_CHALLENGE_LINK = 'https://debridmediamanager.com/api/challenge'
_TOKEN_REUSE = 120.0   # el servidor lo acepta 300 s; se reutiliza solo 120
_TOKEN_TIMEOUT = 5.0   # acotado: el scraper tiene 7 s de presupuesto propio

_TOKEN_LOCK = threading.Lock()
_TOKEN = {'key': None, 'solution': None, 'expires': 0.0}


def get_secret():
	"""Devuelve (dmmProblemKey, solution) o (None, None) si no se puede acuñar.

	El candado se sostiene durante la peticion a proposito: es el equivalente al
	"in-flight sharing" del cliente web. Varias comprobaciones de cache arrancan
	a la vez y deben costar UN token, no uno por hilo."""
	from resources.lib.modules import log_utils
	with _TOKEN_LOCK:
		if _TOKEN['key'] and time.time() < _TOKEN['expires']:
			return _TOKEN['key'], _TOKEN['solution']
		try:
			response = requests.get(_CHALLENGE_LINK, headers={'Accept': 'application/json'}, timeout=_TOKEN_TIMEOUT)
		except requests.exceptions.RequestException as e:
			log_utils.log('DMM: no se pudo pedir el token (%s: %s)' % (type(e).__name__, e), __name__, log_utils.LOGDEBUG)
			return None, None
		if response.status_code != 200:
			# 500 = el servidor no tiene DMM_PROBLEM_SECRET configurado y no
			# valida NADA; 429 = se pidieron mas de 5 tokens en un segundo.
			log_utils.log('DMM: /api/challenge devolvio HTTP %s' % response.status_code, __name__, log_utils.LOGWARNING)
			return None, None
		try: payload = response.json()
		except Exception: payload = None
		token = payload.get('token') if isinstance(payload, dict) else None
		solution = payload.get('hash') if isinstance(payload, dict) else None
		if not isinstance(token, str) or not isinstance(solution, str) or not token or not solution:
			log_utils.log('DMM: /api/challenge respondio 200 sin las claves "token"/"hash"', __name__, log_utils.LOGWARNING)
			return None, None
		_TOKEN['key'], _TOKEN['solution'] = token, solution
		_TOKEN['expires'] = time.time() + _TOKEN_REUSE
		return token, solution


def invalidate_secret(stale_key=None):
	"""Tira el token cacheado tras un 403.

	Se pasa el token que fallo para no tirar uno recien acuñado por un hilo
	hermano: si dos hilos comen el mismo 403, solo el primero fuerza el
	reacuñado y el segundo se encuentra el nuevo ya puesto."""
	with _TOKEN_LOCK:
		if stale_key and _TOKEN['key'] != stale_key: return False
		_TOKEN['key'], _TOKEN['solution'], _TOKEN['expires'] = None, None, 0.0
		return True


class DMMCache:
	availability_check_link = 'https://debridmediamanager.com/api/availability/check'
	timeout = 6.05

	def check_cache(self, unchecked_hashes_chunk, imdb): # DMM API Allows max 100 hashes per request.
		from resources.lib.modules import log_utils
		hashes = [i for i in unchecked_hashes_chunk if len(i) == 40]
		if not hashes: return {}
		# El servidor exige /^tt\d+$/ y responde 400 con cualquier otra cosa.
		# Mejor no gastar la peticion.
		if not imdb or not str(imdb).startswith('tt') or not str(imdb)[2:].isdigit():
			log_utils.log('DMM availability: imdb id no valido (%r), no se consulta' % imdb, __name__, log_utils.LOGDEBUG)
			return {}
		attempts = 2
		while attempts:
			attempts -= 1
			dmmProblemKey, solution = get_secret()
			if not dmmProblemKey: return {}
			data = {'dmmProblemKey': dmmProblemKey, 'solution': solution, 'imdbId': str(imdb), 'hashes': hashes}
			try: results = requests.post(self.availability_check_link, json=data, timeout=self.timeout)
			except requests.exceptions.RequestException as e:
				log_utils.log('DMM availability: fallo de red (%s: %s)' % (type(e).__name__, e), __name__, log_utils.LOGDEBUG)
				return {}
			status = results.status_code
			if status == 403 and attempts:
				# Token caducado en el filo del TTL, o secreto rotado en el
				# servidor bajo nuestros pies. Se reacuña UNA vez.
				invalidate_secret(dmmProblemKey)
				continue
			try: payload = results.json()
			except Exception: payload = None
			available_hashes = payload.get('available') if isinstance(payload, dict) else None
			if available_hashes is None:
				body = (results.text or '')[:300].replace('\n', ' ').replace('\r', ' ')
				# v1.0.56: el limitador de DMM (1 peticion / 2 s por IP) cubre
				# /api/torrents, NO este endpoint — /api/availability/check
				# sigue sin envoltorio withIpRateLimit en el codigo publico, asi
				# que un 429 aqui vendria de la capa Cloudflare. Se mantiene en
				# DEBUG para no llenar el log de los usuarios de Real-Debrid;
				# cualquier OTRA anomalia sigue en WARNING.
				level = log_utils.LOGDEBUG if status == 429 else log_utils.LOGWARNING
				# v1.0.76: el nivel se pasaba como 2º argumento posicional y la
				# firma real es log(msg, caller=None, level=LOGINFO), asi que
				# acababa en 'caller' y TODO salia a LOGINFO — justo el ruido
				# que el nivel pretendia evitar.
				log_utils.log('DMM availability diagnostic: HTTP %s | Content-Type=%s | body[:300]=%r'
						% (status, results.headers.get('Content-Type', ''), body), __name__, level)
				return {}
			try: return {file['hash']: file['files'] for file in available_hashes if 'hash' in file}
			except Exception:
				log_utils.log('DMM availability: respuesta con forma inesperada en "available"', __name__, log_utils.LOGWARNING)
				return {}
		return {}
