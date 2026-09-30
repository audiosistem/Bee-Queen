# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Source pre-flight (v1.0.65)

	Comprueba un enlace YA RESUELTO justo antes de entregarlo al reproductor.

	Dos piezas independientes:

	1. FACTIBILIDAD (sin red) — `advisory()`
	   El bitrate que exige un fichero se deduce de su tamano y de la duracion
	   del titulo: required_mbps = size_bytes * 8 / duration_seconds.
	   Comparado con la velocidad de linea aprendida, permite marcar en la
	   lista de fuentes las que casi seguro van a bufferear, ANTES de tocar
	   la red y sin coste alguno.

	2. SONDA (con red) — `evaluate()`
	   Peticion `Range: bytes=0-N` al enlace resuelto. Mide time-to-first-byte
	   y throughput real de ESE CDN, en ESTE momento, desde ESTA conexion.
	   El veredicto decide si se reproduce, se avisa o se salta a la siguiente.

	La velocidad medida alimenta una EWMA persistida en source_ranker.db, que
	es la que usa la pieza 1. O sea: cuanto mas se reproduce, mejor sabe el
	addon lo que la linea del usuario aguanta.

	NINGUNA de las dos rutas puede romper la reproduccion: todo error acaba en
	veredicto 'unknown' y el flujo sigue como si el modulo no existiera.
"""

import ssl
import urllib.request as urllib2
from time import time as _now
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlparse

from resources.lib.modules import log_utils
from resources.lib.modules.control import setting as getSetting
from resources.lib.jacksparrow import client as fs_client


# Muestreo en DOS tramos (v1.0.66).
#
# La v1.0.65 media los primeros 512 KB desde el primer byte, y eso NO mide la
# linea: mide el arranque lento de TCP. Evidencia del log del 26-ago: cinco
# ficheros distintos, en cinco nodos distintos del CDN, con bitrates exigidos
# entre 32 y 131 Mbps, dieron 123, 134, 125, 137 y 123 ms para el medio mega.
# Cinco medidas identicas de cinco cosas distintas son una constante, no una
# medida. Con un initcwnd tipico de CDN (~32 segmentos) y unos 40 ms de ida y
# vuelta a Frankfurt, la ventana de congestion tarda justo ese rato en abrirse,
# y el resultado sale clavado a ~33 Mbps sea cual sea la capacidad real.
#
# Ahora se descarta el tramo de arranque SIN cronometrar y se mide solo la
# cola, que ya va a velocidad de crucero.
_WARMUP_BYTES = 768 * 1024      # tramo desechado: la rampa de TCP
_MAX_BYTES    = 2 * 1024 * 1024 # tope normal de descarga por sonda
_MEASURE_MIN  = 256 * 1024      # cola minima para dar la medida por buena
_TIME_BUDGET  = 2.5             # segundos de lectura como maximo

# v1.0.72 — el fallo simetrico al de la rampa.
#
# El log del 26-ago trae: sample=1248KB/3ms, o sea 3.408 Mbps. Eso no es una
# red, es memoria: el CDN habia empujado los dos megas enteros al buffer de
# recepcion del sistema antes de que empezaramos a leer la cola, asi que las
# lecturas volvian al instante y se cronometro un memcpy. Una sola medida asi
# disparo la media aprendida a 701 Mbps y con ella el umbral de aviso, dejando
# la lista practicamente muda.
#
# Remedio en dos pasos: si la cola llega en menos de _MIN_MEASURE_SECS se
# alarga la descarga hasta _MAX_BYTES_STRETCH para forzar tiempo de red real;
# si aun asi no da, la cifra se toma como COTA INFERIOR — vale para decidir
# que la fuente cabe, pero NO entra en la media aprendida.
_MIN_MEASURE_SECS  = 0.05
_MAX_BYTES_STRETCH = 8 * 1024 * 1024
# v1.0.89 — bytes del principio que se conservan para audio_probe.py.
_HEAD_KEEP = 2 * 1024 * 1024
_CONNECT_TIMEOUT = 6            # segundos para conectar / primer byte
_MIN_BYTES_FOR_MEASURE = 64 * 1024   # por debajo, ni con rampa incluida
_MAX_REPORTED_MBPS = 2000.0          # techo de cordura para la cifra medida

# Clave de la EWMA de velocidad de linea dentro de source_ranker.db.
# v1.0.67: la clave cambia de nombre a proposito. Todo lo acumulado hasta la
# 1.0.66 se midio cronometrando la rampa de arranque de TCP, asi que son cifras
# sistematicamente bajas (~33 Mbps en cualquier enlace). Mezclarlas con las
# buenas contaminaria la media durante semanas; con la clave nueva se parte de
# cero y las viejas quedan huerfanas y sin efecto.
# v1.0.72: segundo (y espero que ultimo) cambio de clave. La media guardada
# hasta la 1.0.71 se comio una medida de 3.408 Mbps que era memoria, no red, y
# la dejo en 435 Mbps decayendo despacio. Con ese valor el umbral de aviso se
# iba a 335 Mbps y practicamente nada se marcaba.
_LINE_KEY = 'line_mbps_v3'
# Peso de la muestra nueva en la EWMA. 0.30 = se adapta en ~6-8 reproducciones
# sin que una medida mala tire el valor al suelo.
_EWMA_ALPHA = 0.30

# Esquemas que no son HTTP y no se pueden sondear.
_NON_HTTP = ('plugin://', 'special://', 'magnet:', 'rtmp://', 'rtsp://', 'file://')


# ── helpers ───────────────────────────────────────────────────────────────────

def enabled():
	try:
		return getSetting('preflight.enabled') == 'true'
	except Exception:
		return False


def skip_mode():
	"""True si el usuario quiere que las fuentes lentas se salten, no solo avisar."""
	try:
		# select -> Kodi devuelve el INDICE, no el valor. 0=Warn only, 1=Skip
		return str(getSetting('preflight.mode') or '1') == '1'
	except Exception:
		return True


def manual_action():
	"""
	Que hacer cuando el usuario elige A MANO una fuente que no da la talla.
	0 = notificar (comportamiento hasta la v1.0.70)
	1 = preguntar antes de reproducir  (por defecto desde la v1.0.71)
	2 = no hacer nada

	Motivo del cambio de defecto: el toast salia CUANDO LA REPRODUCCION YA
	HABIA EMPEZADO. En el log del 26-ago eso significo medio minuto de imagen
	congelada y 34.925 errores de decodificador antes de que el usuario
	pudiera reaccionar. Avisar tarde no es avisar.
	"""
	try:
		return int(getSetting('preflight.manual') or '1')
	except Exception:
		return 1


def ask_ratio():
	"""
	Solo se pregunta cuando lo medido queda por debajo de este porcentaje de
	lo que exige el fichero. Por encima, basta con notificar.

	Existe porque no todo 'slow' es igual de grave: en el mismo log, una
	fuente al 87% de lo necesario reprodujo con CERO errores de decodificador,
	y otra al 36% se hundio. Preguntar en el primer caso seria ruido.
	"""
	try:
		v = int(getSetting('preflight.ask.ratio') or '80')
	except Exception:
		v = 80
	return min(100, max(10, v)) / 100.0


def should_ask(result):
	"""True si este veredicto merece un dialogo de confirmacion."""
	try:
		if manual_action() != 1:
			return False
		req = result.get('required_mbps') or 0
		mea = result.get('measured_mbps') or 0
		if not req or not mea:
			return False
		return (mea / float(req)) < ask_ratio()
	except Exception:
		return False


def info_size_gb():
	"""
	A partir de este tamano se muestra SIEMPRE el bitrate en la lista, encaje
	o no en la linea (v1.0.69). 0 desactiva la regla.

	El umbral por linea sola dejaba mudas fuentes que el usuario quiere ver:
	un Fellowship de 131 GB exige 105 Mbps y cabia, asi que no decia nada,
	pero el tamano por si solo ya es informacion que ayuda a decidir.
	"""
	try:
		v = int(getSetting('preflight.list.minsize') or '30')
	except Exception:
		v = 30
	return max(0, v)


def margin():
	"""Holgura exigida sobre el bitrate del fichero, como factor (1.30 = 130%)."""
	try:
		v = int(getSetting('preflight.margin') or '130')
	except Exception:
		v = 130
	if v < 100:
		v = 100
	if v > 250:
		v = 250
	return v / 100.0


def host_of(url):
	"""Host normalizado de una URL. '' si no se puede sacar."""
	try:
		if not url:
			return ''
		u = str(url).split('|', 1)[0]
		net = (urlparse(u).netloc or '').lower()
		if '@' in net:
			net = net.split('@', 1)[-1]
		if ':' in net:
			net = net.split(':', 1)[0]
		if net.startswith('www.'):
			net = net[4:]
		return net
	except Exception:
		return ''


def required_mbps(size_gb, duration_seconds):
	"""
	Bitrate medio que exige el fichero, en Mbps. None si falta algun dato.

	size_gb viene de los scrapers en GiB decimales (luc_kodi ya lo muestra
	como '%.2f GB'); duration_seconds sale de meta['duration'], que tmdb.py
	rellena en SEGUNDOS.
	"""
	try:
		size = float(size_gb or 0)
		dur = float(duration_seconds or 0)
	except (TypeError, ValueError):
		return None
	if size <= 0 or dur <= 0:
		return None
	bits = size * 1024.0 * 1024.0 * 1024.0 * 8.0
	return (bits / dur) / 1000000.0


def _duration_of(meta):
	"""Duracion en segundos desde meta. None si no la hay o no es creible."""
	if not isinstance(meta, dict):
		return None
	for key in ('duration', 'runtime'):
		raw = meta.get(key)
		if raw in (None, '', 'None'):
			continue
		try:
			val = float(raw)
		except (TypeError, ValueError):
			continue
		if val <= 0:
			continue
		# v1.0.66: la unidad se decide por la CLAVE, no por la magnitud.
		# 'duration' lo escribe el propio addon en SEGUNDOS (tmdb.py hace
		# runtime*60); 'runtime' viene de TMDb en MINUTOS. La regla anterior
		# ("menos de 15 min es que son minutos") convertia un episodio corto
		# legitimo de 10 minutos en uno de diez horas, y con el bitrate exigido
		# dividido por sesenta ninguna fuente se marcaba nunca.
		if key == 'duration':
			if val < 60:      # ningun video del catalogo dura menos de un minuto
				val *= 60.0
		else:
			if val <= 1000:   # minutos; por encima solo puede ser segundos
				val *= 60.0
		if 60.0 <= val <= 86400.0:
			return val
	return None


# ── velocidad de linea aprendida ──────────────────────────────────────────────

def line_mbps():
	"""EWMA de la velocidad medida. 0.0 si aun no hay muestras."""
	try:
		from resources.lib.database import source_ranker
		val, cnt = source_ranker.get_net(_LINE_KEY)
		if cnt <= 0:
			return 0.0
		return float(val or 0.0)
	except Exception:
		return 0.0


def line_samples():
	try:
		from resources.lib.database import source_ranker
		_, cnt = source_ranker.get_net(_LINE_KEY)
		return int(cnt or 0)
	except Exception:
		return 0


def remember_speed(mbps):
	"""Incorpora una medida a la EWMA de velocidad de linea."""
	try:
		if not mbps or mbps <= 0:
			return
		from resources.lib.database import source_ranker
		source_ranker.update_net_ewma(_LINE_KEY, float(mbps), _EWMA_ALPHA)
	except Exception:
		pass


# ── pieza 1: factibilidad sin red ─────────────────────────────────────────────


# v1.0.78 — cache de los dos umbrales que advisory() consulta por ITEM.
#
# info_size_gb() y margin() hacen cada una un getSetting, y getSetting parsea
# el blob entero de ajustes (441 claves, ~13,5 KB) en cada llamada. advisory()
# se ejecuta una vez por fuente al construir la lista, asi que con 150 fuentes
# eran hasta 300 parseos del mismo JSON para leer dos numeros que no cambian
# mientras se pinta una lista.
#
# La cache se ata al contador de escrituras de ajustes de control.py, si
# existe, para que un cambio en la pantalla de ajustes la invalide sola. Si no
# existe ese contador, se cachea solo dentro de una misma pasada: reset_cache()
# lo llama el constructor de la lista.
_thresholds = None


def reset_cache():
	"""Olvida los umbrales cacheados. La llama quien empieza a pintar lista."""
	global _thresholds
	_thresholds = None


def _cached_thresholds():
	global _thresholds
	if _thresholds is None:
		_thresholds = (info_size_gb(), margin())
	return _thresholds


def advisory(item, meta, line=None):
	"""
	Veredicto barato para pintar en la lista de fuentes. Sin red.

	Devuelve dict:
		{'verdict': 'ok'|'info'|'heavy'|'unknown', 'required_mbps': float|None}

	  heavy : pide mas de lo que da la linea medida -> aviso en rojo.
	          Solo se emite si HAY velocidad aprendida; sin referencia real,
	          marcar en rojo por tamano seria adivinar.
	  info  : cabe en la linea, pero el fichero pasa de `info_size_gb()`.
	          Se ensena la cifra en tono neutro: no es una advertencia, es un
	          dato para que el usuario juzgue con SU conexion. No necesita
	          velocidad aprendida, asi que funciona desde la instalacion.
	  ok    : ni una cosa ni la otra, no se pinta nada.
	"""
	out = {'verdict': 'unknown', 'required_mbps': None}
	try:
		if not isinstance(item, dict):
			return out
		req = required_mbps(item.get('size'), _duration_of(meta))
		if req is None:
			return out
		out['required_mbps'] = req

		ref = line_mbps() if line is None else line
		thr_size, thr_margin = _cached_thresholds()
		if ref and ref > 0 and req > (ref / thr_margin):
			out['verdict'] = 'heavy'
			return out

		thr = thr_size
		try:
			size = float(item.get('size') or 0)
		except (TypeError, ValueError):
			size = 0.0
		out['verdict'] = 'info' if (thr and size >= thr) else 'ok'
		return out
	except Exception:
		return out


# ── pieza 2: sonda de red ─────────────────────────────────────────────────────

def _open(url, timeout):
	"""
	Abre la URL respetando la sintaxis de cabeceras de Kodi (url|H=V&H2=V2),
	que es como viajan las credenciales Basic de Easynews.
	"""
	clean_url = url
	hdrs = {}
	if '|' in url:
		clean_url, qs = url.split('|', 1)
		try:
			hdrs.update(dict(parse_qsl(qs)))
		except Exception:
			pass
	if 'User-Agent' not in hdrs:
		hdrs['User-Agent'] = 'Mozilla/5.0'
	# Range acota la descarga en los CDN que lo respetan. Los que no, devuelven
	# 200 y el bucle de lectura corta igual por tope de bytes o de tiempo.
	hdrs['Range'] = 'bytes=0-%d' % (_MAX_BYTES_STRETCH - 1)
	req = urllib2.Request(clean_url, headers=hdrs)
	try:
		ctx = ssl._create_unverified_context()
	except Exception:
		ctx = None
	return urllib2.urlopen(req, timeout=timeout, context=ctx)


def probe(url, timeout=_CONNECT_TIMEOUT):
	"""
	Mide un enlace resuelto. NO decide nada — solo informa.

	Devuelve:
		{'alive': bool, 'code': int, 'ttfb': float, 'mbps': float|None,
		 'bytes': int, 'reason': str}
	"""
	out = {'alive': False, 'code': 0, 'ttfb': 0.0, 'mbps': None, 'reliable': False,
	       'bytes': 0, 'measured_bytes': 0, 'measured_secs': 0.0, 'reason': ''}
	resp = None
	try:
		t0 = _now()
		resp = _open(url, timeout)
		try:
			out['code'] = int(resp.getcode() or 200)
		except Exception:
			out['code'] = 200
		if out['code'] >= 400:
			out['reason'] = 'http_%s' % out['code']
			return out

		first = resp.read(32 * 1024) or b''
		t_first = _now()
		out['ttfb'] = round(t_first - t0, 3)
		if not first:
			out['reason'] = 'empty'
			return out

		# Pagina de error disfrazada de video: mismo criterio que urlcheck.
		head = first[:512].decode('utf-8', errors='ignore')
		try:
			ctype = (resp.headers.get('Content-Type') or '').lower()
		except Exception:
			ctype = ''
		if '#EXTM3U' not in head:
			looks_text = ('text' in ctype) or ('html' in ctype) or ('<html' in head.lower())
			if looks_text:
				out['reason'] = 'html'
				return out

		out['alive'] = True
		total = len(first)
		# v1.0.89 — la sonda de audio lee las pistas de la cabecera del
		# fichero, y esa cabecera es exactamente lo que se acaba de pedir. Se
		# guardan los primeros HEAD_KEEP bytes para que no haga falta otra
		# peticion. No toca la medida: los bytes se copian, no se cronometran.
		# Nombre propio: `head` ya es el texto de los primeros 512 bytes.
		head_bytes = bytearray(first[:_HEAD_KEEP])
		# Las listas HLS son de bytes, no de video: medir su descarga no dice
		# nada del ancho de banda del segmento. Se acepta sin medir.
		if '#EXTM3U' in head:
			out['reason'] = 'hls'
			out['bytes'] = total
			return out

		# Se anota el instante en que se cruza el umbral de calentamiento; a
		# partir de ahi empieza la medida de verdad.
		t_warm, warm_bytes = None, 0
		limit = _MAX_BYTES
		while total < limit and (_now() - t_first) < _TIME_BUDGET:
			chunk = resp.read(64 * 1024)
			if not chunk:
				break
			total += len(chunk)
			if len(head_bytes) < _HEAD_KEEP:
				head_bytes += chunk[:_HEAD_KEEP - len(head_bytes)]
			if t_warm is None and total >= _WARMUP_BYTES:
				t_warm, warm_bytes = _now(), total
			# Si la cola esta llegando demasiado rapido para ser red, se estira
			# la descarga en vez de dar por buena una cifra de memoria.
			if (total >= limit and limit < _MAX_BYTES_STRETCH and t_warm is not None
					and (_now() - t_warm) < _MIN_MEASURE_SECS):
				limit = _MAX_BYTES_STRETCH
		t_end = _now()
		out['bytes'] = total
		out['head'] = bytes(head_bytes)

		def _rate(nbytes, secs):
			# Suelo al divisor: en una linea rapida la cola llega en pocos
			# milisegundos y sin suelo la cifra se dispara. El techo mantiene
			# la EWMA en un rango creible; la conclusion ("da de sobra") no
			# cambia en ninguno de los dos casos.
			return min(round((nbytes * 8.0 / max(secs, 0.005)) / 1000000.0, 2),
			           _MAX_REPORTED_MBPS)

		tail = total - warm_bytes
		if t_warm is not None and tail >= _MEASURE_MIN:
			tail_secs = t_end - t_warm
			out['measured_bytes'] = tail
			out['measured_secs'] = round(tail_secs, 3)
			out['mbps'] = _rate(tail, tail_secs)
			if tail_secs < _MIN_MEASURE_SECS:
				# Cota inferior: sirve para el veredicto (si llego asi de rapido
				# la fuente cabe seguro) pero no es un dato de red y no puede
				# entrar en la media aprendida.
				out['reliable'] = False
				out['reason'] = 'buffered'
			else:
				out['reliable'] = True
		elif total >= _MIN_BYTES_FOR_MEASURE:
			# No dio tiempo a pasar del calentamiento dentro del presupuesto:
			# eso solo ocurre cuando la linea ya es lenta de verdad, asi que la
			# medida con rampa incluida sirve (subestima, y hacia el lado
			# prudente). Se marca para poder distinguirla en el log.
			out['measured_bytes'] = total
			out['measured_secs'] = round(t_end - t_first, 3)
			out['mbps'] = _rate(total, t_end - t_first)
			out['reliable'] = True   # subestima, pero es tiempo de red real
			out['reason'] = 'ramp_included'
		else:
			out['reason'] = 'sample_too_small'
		return out
	except HTTPError as e:
		# urllib LANZA en 4xx/5xx en vez de devolver la respuesta, asi que sin
		# esta rama un 404 se registraba como 'error:HTTPError' y se perdia el
		# codigo, que es justo el dato que distingue un enlace caducado de un
		# fallo de red.
		try:
			out['code'] = int(e.code)
		except Exception:
			out['code'] = 0
		out['reason'] = 'http_%s' % (out['code'] or '?')
		return out
	except Exception as e:
		out['reason'] = 'error:%s' % type(e).__name__
		return out
	finally:
		try:
			if resp is not None:
				resp.close()
		except Exception:
			pass


def evaluate(url, item, meta):
	"""
	Sonda + veredicto para un enlace resuelto.

	Devuelve dict:
		{'verdict': 'ok'|'slow'|'dead'|'unknown',
		 'measured_mbps': float|None, 'required_mbps': float|None,
		 'ttfb': float, 'host': str, 'reason': str}

	'unknown' significa "no se ha podido comprobar" y NUNCA debe usarse para
	descartar una fuente.
	"""
	out = {'verdict': 'unknown', 'measured_mbps': None, 'required_mbps': None,
	       'ttfb': 0.0, 'host': host_of(url), 'reason': '', 'reliable': False,
	       'measured_bytes': 0, 'measured_secs': 0.0}
	try:
		if not url:
			out['reason'] = 'no_url'
			return out
		low = str(url).lower()
		if low.startswith(_NON_HTTP):
			out['reason'] = 'not_http'
			return out

		out['required_mbps'] = required_mbps(
			(item or {}).get('size') if isinstance(item, dict) else None,
			_duration_of(meta))

		res = probe(url)
		# v1.0.89: la cabecera viaja al llamador para la sonda de audio. Quien
		# la use debe sacarla del dict con pop() y no guardarlo con ella.
		if res.get('head'):
			out['head'] = res['head']
		out['ttfb'] = res.get('ttfb') or 0.0
		out['reason'] = res.get('reason') or ''
		out['measured_bytes'] = res.get('measured_bytes') or 0
		out['measured_secs'] = res.get('measured_secs') or 0.0
		if not res.get('alive'):
			out['verdict'] = 'dead'
			return out

		mbps = res.get('mbps')
		out['measured_mbps'] = mbps
		out['reliable'] = bool(res.get('reliable'))
		if mbps and out['reliable']:
			remember_speed(mbps)

		req = out['required_mbps']
		if not mbps or not req:
			# Vivo pero no medible (HLS, muestra corta, o falta duracion/tamano).
			out['verdict'] = 'ok'
			return out

		out['verdict'] = 'ok' if mbps >= (req * margin()) else 'slow'
		return out
	except Exception:
		log_utils.error()
		out['verdict'] = 'unknown'
		return out


def describe(result):
	"""Una linea legible para el log. Nunca incluye la URL."""
	try:
		req = result.get('required_mbps')
		mea = result.get('measured_mbps')
		# La muestra (KB y ms) va en la linea a proposito: sin ella no se puede
		# saber si una cifra sale de la cola o de la rampa de TCP, que es lo que
		# invalidaba las medidas de la v1.0.65.
		sample = ''
		if result.get('measured_bytes') and not result.get('reliable'):
			# Marcada para que se vea de un vistazo que NO alimento la media.
			sample = ' sample=%dKB/%sms(bound)' % (
				int(result['measured_bytes'] / 1024),
				int((result.get('measured_secs') or 0) * 1000))
		elif result.get('measured_bytes'):
			sample = ' sample=%dKB/%sms' % (int(result['measured_bytes'] / 1024),
			                               int((result.get('measured_secs') or 0) * 1000))
		try:
			_ln = line_mbps()
			line_txt = (' line=%.0f Mbps/%d' % (_ln, line_samples())) if _ln else ' line=n/a'
		except Exception:
			line_txt = ''
		return '[PREFLIGHT] %s host=%s needs=%s got=%s ttfb=%ss%s%s %s' % (
			(result.get('verdict') or '?').upper(),
			result.get('host') or '?',
			('%.1f Mbps' % req) if req else 'n/a',
			('%.1f Mbps' % mea) if mea else 'n/a',
			result.get('ttfb') or 0,
			sample,
			line_txt,
			('(%s)' % result['reason']) if result.get('reason') else '')
	except Exception:
		return '[PREFLIGHT] (unprintable result)'


def log(result, level=None):
	"""
	Escribe el veredicto. La URL no entra aqui ni saneada: no hace falta.

	v1.0.67: el veredicto 'ok' iba a LOGDEBUG, que esta cortado por
	`debug.enabled`. Consecuencia practica en el log del 26-ago: en cuanto la
	medida se corrigio y todo paso a 'ok', el pre-flight desaparecio del log
	por completo y no habia forma de distinguir "funciona y no avisa" de "no
	se esta ejecutando". Una comprobacion que solo se ve cuando falla no se
	puede auditar, asi que ahora deja SIEMPRE una linea.
	"""
	try:
		if level is None:
			level = log_utils.LOGWARNING if result.get('verdict') in ('dead', 'slow') else log_utils.LOGINFO
		log_utils.log(describe(result), level=level)
	except Exception:
		pass


def scrubbed(url):
	"""Atajo para los llamadores que quieran registrar la URL saneada."""
	try:
		return fs_client.scrub_url(url)
	except Exception:
		return '<URL>'
