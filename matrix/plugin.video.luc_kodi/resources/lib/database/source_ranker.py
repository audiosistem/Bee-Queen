# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Personalized Source Ranker

	Aprende qué fuentes prefiere el usuario y ajusta el orden de autoplay
	en consecuencia. Modelo: log-odds suavizados con prior Laplace por feature.

	Schema
	──────
	source_features(feature_key, feature_type, feature_value,
	                pos_count, neg_count, exp_count, last_ts)
		feature_key   : tipo:valor  (e.g. 'quality:4K', 'provider:torrentio',
		                'host:cdn2-ovh-fra.energycdn.com')
		pos_count     : veces que el usuario eligió una fuente con esta feature
		                Y la reproducción arrancó bien
		neg_count     : veces que la fuente FALLÓ de verdad — enlace muerto o
		                ancho de banda insuficiente para su bitrate (v1.0.65)
		exp_count     : veces que se mostró (elegida, saltada o fallida)

	net_stats(key, num, cnt, last_ts)                            (v1.0.65)
		Medidas agregadas de red. Hoy solo 'line_mbps': EWMA del throughput
		real medido por preflight.py en cada reproducción.

	Modelo
	──────
	Para cada feature F de una fuente, contribución:
		log( (pos[F] + α) / (skipped[F] + (W-1)·neg[F] + α) )
	donde skipped = exp - pos y W = _NEG_WEIGHT. α=1.0 (prior Laplace).

	Un fallo real pesa W veces más que un simple "no lo elegiste": que una
	fuente no se escoja es ruido, que no se pueda reproducir es señal.

	El total se suma a _smart_score multiplicado por el peso del setting.
	Sin datos → contribución 0 → comportamiento idéntico al ranker estático.
"""

from sqlite3 import dbapi2 as db
from time import time
from math import log
from resources.lib.modules.control import makeFile, dataPath, joinPath, setting as getSetting

_DB_FILE = joinPath(dataPath, 'source_ranker.db')

# Prior Laplace (también shrinkage hacia 0). Más alto = modelo más conservador,
# necesita más datos para mover el ranking. 1.0 es estándar.
_ALPHA = 1.0

# Plays mínimos antes de aplicar ajustes. Evita sesgos de los 5 primeros plays.
_MIN_TOTAL_PLAYS = 10

# Cuánto pesa un FALLO frente a un simple "saltada" (v1.0.65). 3.0 = un enlace
# muerto o demasiado pesado para la línea cuenta como tres no-elecciones.
_NEG_WEIGHT = 3.0

# Segundos niveles que no son dominio registrable (para no cortar 'x.co.uk'
# en 'co.uk', que agruparía medio Reino Unido bajo la misma feature).
_SLD_UNDER_CCTLD = ('co', 'com', 'net', 'org', 'gov', 'edu', 'ac')

# Caché en memoria de las features. Se invalida al escribir.
_features_cache = None
_features_cache_ts = 0


# ── helpers DB ────────────────────────────────────────────────────────────────

def _connect():
	makeFile(dataPath)
	con = db.connect(_DB_FILE)
	con.row_factory = db.Row
	return con


def _ensure_table(cur):
	cur.execute('''
		CREATE TABLE IF NOT EXISTS source_features (
			feature_key   TEXT PRIMARY KEY,
			feature_type  TEXT NOT NULL,
			feature_value TEXT NOT NULL,
			pos_count     INTEGER DEFAULT 0,
			neg_count     INTEGER DEFAULT 0,
			exp_count     INTEGER DEFAULT 0,
			last_ts       INTEGER NOT NULL
		)
	''')
	cur.execute('''
		CREATE INDEX IF NOT EXISTS idx_features_type
		ON source_features (feature_type)
	''')
	# v1.0.65 — medidas de red agregadas (EWMA de velocidad de línea).
	cur.execute('''
		CREATE TABLE IF NOT EXISTS net_stats (
			key      TEXT PRIMARY KEY,
			num      REAL    DEFAULT 0,
			cnt      INTEGER DEFAULT 0,
			last_ts  INTEGER NOT NULL
		)
	''')


def _invalidate_cache():
	global _features_cache, _features_cache_ts
	_features_cache = None
	_features_cache_ts = 0


# ── Featurización ─────────────────────────────────────────────────────────────

def _size_bucket(size_gb):
	"""Discretiza el tamaño en buckets significativos para video."""
	try:
		s = float(size_gb or 0)
	except (ValueError, TypeError):
		return 'unknown'
	if s <= 0:           return 'unknown'
	if s < 1.5:          return 'tiny'      # SD / muy comprimido
	if s < 4:            return 'small'     # 1080p web-dl ligero
	if s < 10:           return 'medium'    # 1080p bluray / 4K bajo
	if s < 25:           return 'large'     # 4K web-dl / bluray
	if s < 50:           return 'xlarge'    # 4K REMUX
	return 'huge'                            # REMUX raros, packs


def _seeders_bucket(seeders):
	"""Discretiza seeders. Refleja salud del torrent."""
	try:
		n = int(seeders or 0)
	except (ValueError, TypeError):
		return 'unknown'
	if n <= 0:    return 'dead'
	if n < 5:     return 'low'
	if n < 30:    return 'medium'
	if n < 100:   return 'high'
	return 'very_high'


def normalize_host(url_or_host):
	"""
	Host normalizado para usar como valor de feature.

	Se reduce al dominio registrable (dos labels, tres cuando el TLD es un
	ccTLD de dos letras tras un SLD tipo .co.uk). Motivo: los CDN de debrid
	reparten por nodo y el identificador va DENTRO del primer label
	('3-cdn2-ovh-fra.energycdn.com', '7-cdn5-ovh-fra.energycdn.com'), así que
	recortar labels no agrupa nada. Aprender nodo a nodo tampoco sirve: el
	usuario casi nunca vuelve a caer en el mismo. Lo que se repite y predice
	el rendimiento es el CDN, y eso es 'energycdn.com'.
	"""
	try:
		if not url_or_host:
			return ''
		s = str(url_or_host).strip().split('|', 1)[0]
		if '://' in s:
			from urllib.parse import urlparse
			s = urlparse(s).netloc or ''
		s = s.lower()
		if '@' in s:
			s = s.split('@', 1)[-1]
		if ':' in s:
			s = s.split(':', 1)[0]
		if s.startswith('www.'):
			s = s[4:]
		if not s or '.' not in s:
			return s
		parts = [p for p in s.split('.') if p]
		# Una IP no tiene dominio registrable: recortarla daria '0.1' y juntaria
		# hosts sin ninguna relacion bajo la misma feature.
		if len(parts) == 4 and all(p.isdigit() for p in parts):
			return s
		if len(parts) <= 2:
			return '.'.join(parts)
		if len(parts[-1]) == 2 and parts[-2] in _SLD_UNDER_CCTLD:
			return '.'.join(parts[-3:])
		return '.'.join(parts[-2:])
	except Exception:
		return ''


def featurize(item, resolved_url=None):
	"""
	Extrae las features de una fuente. Devuelve lista de claves
	'tipo:valor'. Cualquier dato faltante se omite (no contribuye).

	`resolved_url` (v1.0.65) solo existe DESPUÉS de resolve(), así que la
	feature 'host:' se aprende al registrar el resultado pero no puede
	usarse al puntuar una lista sin resolver. Esa asimetría es deliberada:
	el host entra en el modelo por `record_choice`/`record_failure` y se
	consulta aparte con `host_health()` cuando ya se conoce.

	El campo `info` de luc_kodi está pre-tokenizado con ' | ' como
	separador (e.g. '5.2 GB | HEVC | HDR | ATMOS'). Lo parseamos por
	tokens en vez de por substring para alinear con get_extra_tags
	y evitar falsos positivos (e.g. 'DV' dentro de palabras).
	"""
	if not isinstance(item, dict):
		return []
	feats = []
	info_raw = item.get('info') or ''
	tokens = set(t.strip().upper() for t in info_raw.split('|') if t.strip())
	# Quality (siempre presente)
	q = item.get('quality')
	if q: feats.append('quality:%s' % q)
	# Codec — uno solo (jerarquía AV1 > HEVC > H264)
	if 'AV1' in tokens:
		feats.append('codec:AV1')
	elif 'HEVC' in tokens or 'H265' in tokens or 'X265' in tokens:
		feats.append('codec:HEVC')
	elif 'H264' in tokens or 'X264' in tokens or 'AVC' in tokens:
		feats.append('codec:H264')
	# HDR — uno solo, jerarquía: DV > HDR10+ > HDR > SDR
	if 'DV' in tokens or 'DOLBY-VISION' in tokens or 'DOLBYVISION' in tokens:
		feats.append('hdr:DV')
	elif 'HDR10+' in tokens or 'HDR10PLUS' in tokens:
		feats.append('hdr:HDR10+')
	elif 'HDR' in tokens or 'HDR10' in tokens:
		feats.append('hdr:HDR')
	else:
		feats.append('hdr:SDR')
	# Audio — uno solo, jerarquía
	if 'ATMOS' in tokens:
		feats.append('audio:ATMOS')
	elif 'TRUEHD' in tokens or 'DOLBY-TRUEHD' in tokens:
		feats.append('audio:TRUEHD')
	elif any(t in tokens for t in ('DTS-HD', 'DTSHD', 'DTS-HD MA', 'DTS-X')):
		feats.append('audio:DTS-HD')
	elif 'DD+' in tokens or 'DDP' in tokens or 'EAC3' in tokens:
		feats.append('audio:DDPLUS')
	elif 'AAC' in tokens:
		feats.append('audio:AAC')
	# Provider y debrid
	prov = item.get('provider') or ''
	if prov: feats.append('provider:%s' % prov.lower())
	deb = item.get('debrid') or 'none'
	feats.append('debrid:%s' % str(deb).lower().replace(' ', '').replace('-', '').replace('.', ''))
	# Size + seeders en buckets
	feats.append('size:%s' % _size_bucket(item.get('size')))
	feats.append('seeders:%s' % _seeders_bucket(item.get('seeders')))
	# Host del CDN que sirvió el fichero (v1.0.65). Solo disponible tras resolve().
	if resolved_url:
		h = normalize_host(resolved_url)
		if h:
			feats.append('host:%s' % h)
	return feats


# ── Lectura del modelo (con caché) ────────────────────────────────────────────

_plays_guard = None


def _load_features():
	"""Carga todas las features a un dict. Cacheado para evitar I/O repetida."""
	global _features_cache, _features_cache_ts
	# Caché válido durante toda la sesión de ranking (se invalida en escrituras)
	if _features_cache is not None:
		return _features_cache
	out = {}
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute('SELECT feature_key, pos_count, exp_count, neg_count FROM source_features')
		for row in cur.fetchall():
			out[row['feature_key']] = (int(row['pos_count']), int(row['exp_count']), int(row['neg_count'] or 0))
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: con.close()
		except Exception: pass
	_features_cache = out
	_features_cache_ts = int(time())
	return out


def _total_plays():
	"""Suma de pos_count en la feature quality:* — proxy de "plays totales"."""
	feats = _load_features()
	total = 0
	for k, (pos, _e, _n) in feats.items():
		if k.startswith('quality:'):
			total += pos
	return total


# ── API pública: scoring ──────────────────────────────────────────────────────

def score_adjustment(item):
	"""
	Devuelve el ajuste personalizado para una fuente. 0.0 si:
		· ranker desactivado en settings
		· menos de _MIN_TOTAL_PLAYS plays acumulados
		· cualquier error
	El llamador debe multiplicar por el peso del setting antes de sumar a _smart_score.
	"""
	try:
		# v1.0.78 — el ajuste y la guardia de plays se resuelven UNA vez por
		# sesion de ranking, no una por fuente.
		#
		# score_adjustment() se llama desde _smart_score, o sea una vez por
		# cada fuente de la lista. Cada llamada hacia un getSetting —que
		# parsea el JSON entero de ajustes, 13,5 KB— y ademas recorria todas
		# las features solo para recalcular el mismo total. Con 150 fuentes
		# eran 150 parseos y 150 barridos identicos.
		#
		# El total se ata a la caché de features: _load_features() ya se
		# invalida al escribir, asi que colgar el contador de la misma
		# identidad de objeto lo invalida a la vez y no hay forma de que se
		# queden desparejados.
		global _plays_guard
		feats = _load_features()
		if not feats:
			return 0.0
		guard = globals().get('_plays_guard')
		if guard is None or guard[0] is not feats:
			total = 0
			for k, (pos, _e, _n) in feats.items():
				if k.startswith('quality:'):
					total += pos
			_plays_guard = (feats, total,
			                getSetting('personal.ranker.enabled') == 'true')
			guard = _plays_guard
		_feats_id, total, enabled = guard
		if not enabled:
			return 0.0
		if total < _MIN_TOTAL_PLAYS:
			return 0.0
		item_feats = featurize(item)
		score = 0.0
		for f in item_feats:
			pos, exp, neg = feats.get(f, (0, 0, 0))
			skipped = max(0, exp - pos)
			# Log-odds Laplace-suavizado, con los fallos reales pesando _NEG_WEIGHT
			score += log((pos + _ALPHA) / (skipped + (_NEG_WEIGHT - 1.0) * neg + _ALPHA))
		return score
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return 0.0


# ── API pública: registro de eventos ──────────────────────────────────────────

def _apply_updates(updates):
	"""Escribe un lote {feature_key: (pos, neg, exp, type, value)}."""
	if not updates:
		return
	ts = int(time())
	con = None
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		for key, (pd, nd, ed, ftype, fval) in updates.items():
			cur.execute('''
				INSERT INTO source_features
					(feature_key, feature_type, feature_value, pos_count, neg_count, exp_count, last_ts)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT(feature_key) DO UPDATE SET
					pos_count = pos_count + ?,
					neg_count = neg_count + ?,
					exp_count = exp_count + ?,
					last_ts   = ?
			''', (key, ftype, fval, pd, nd, ed, ts, pd, nd, ed, ts))
		con.commit()
		_invalidate_cache()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try:
			if con is not None: con.close()
		except Exception: pass


def _collect(updates, item, pos_d, neg_d, exp_d, resolved_url=None):
	for f in featurize(item, resolved_url=resolved_url):
		ftype, fval = f.split(':', 1)
		if f in updates:
			op, on, oe, _, _ = updates[f]
			updates[f] = (op + pos_d, on + neg_d, oe + exp_d, ftype, fval)
		else:
			updates[f] = (pos_d, neg_d, exp_d, ftype, fval)


def record_choice(chosen_item, all_items=None, resolved_url=None):
	"""
	Llamado cuando el usuario (o autoplay) confirma una fuente.

	chosen_item  : dict de la fuente que se va a reproducir → +1 pos +1 exp
	all_items    : lista de fuentes mostradas/intentadas antes de la elegida
	               → cada una recibe +1 exp (sin pos), señalando "fue saltada".
	               Si es None, solo se registra la elegida.
	resolved_url : URL final tras resolve() (v1.0.65). Solo se usa para
	               aprender la feature 'host:' de la fuente ELEGIDA — de las
	               saltadas no se conoce el host y sería falsearlo.

	No bloqueante en caso de error — nunca debe romper la reproducción.
	"""
	if getSetting('personal.ranker.enabled') != 'true':
		return
	try:
		updates = {}
		_collect(updates, chosen_item, 1, 0, 1, resolved_url=resolved_url)
		if all_items:
			for it in all_items:
				if it is chosen_item:
					continue
				_collect(updates, it, 0, 0, 1)
		_apply_updates(updates)
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()


def record_failure(item, resolved_url=None, reason=''):
	"""
	Llamado cuando una fuente FALLÓ de verdad (v1.0.65): enlace muerto,
	vídeo de error, o ancho de banda por debajo de lo que exige su bitrate.

	Suma +1 neg +1 exp (sin pos) a todas sus features, host incluido cuando
	se conoce. Un fallo pesa _NEG_WEIGHT veces más que una simple no-elección.

	Distinguir esto de "no la elegiste" es justo lo que permite que el modelo
	aprenda qué CDN funciona en esta conexión y no solo qué le gusta al usuario.
	"""
	if getSetting('personal.ranker.enabled') != 'true':
		return
	try:
		if not isinstance(item, dict):
			return
		updates = {}
		_collect(updates, item, 0, 1, 1, resolved_url=resolved_url)
		_apply_updates(updates)
		if reason:
			try:
				from resources.lib.modules import log_utils
				log_utils.log('[RANKER] failure recorded (%s) host=%s provider=%s' % (
					reason, normalize_host(resolved_url) or '-',
					item.get('provider') or '-'), level=log_utils.LOGDEBUG)
			except Exception:
				pass
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()


def record_host(resolved_url, ok=True):
	"""
	Registra SOLO la feature 'host:' de un enlace ya resuelto (v1.0.65).

	Existe para la reproducción manual: `source_results` ya llama a
	`record_choice()` en el momento de la selección, cuando el host todavía
	no se conoce. Volver a llamar allí duplicaría el conteo de todas las
	demás features, así que aquí se toca únicamente el host.
	"""
	if getSetting('personal.ranker.enabled') != 'true':
		return
	try:
		h = normalize_host(resolved_url)
		if not h:
			return
		key = 'host:%s' % h
		_apply_updates({key: ((1 if ok else 0), (0 if ok else 1), 1, 'host', h)})
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()


def host_health(url_or_host):
	"""
	Historial de un host ya resuelto (v1.0.65).

	Devuelve {'host','pos','neg','exp','log_odds','samples'}. Un host sin
	historial devuelve log_odds 0.0 — neutro, nunca penalizado por nuevo.
	"""
	out = {'host': '', 'pos': 0, 'neg': 0, 'exp': 0, 'log_odds': 0.0, 'samples': 0}
	try:
		h = normalize_host(url_or_host)
		if not h:
			return out
		out['host'] = h
		pos, exp, neg = _load_features().get('host:%s' % h, (0, 0, 0))
		skipped = max(0, exp - pos)
		out.update({'pos': pos, 'neg': neg, 'exp': exp, 'samples': exp,
		            'log_odds': round(log((pos + _ALPHA) / (skipped + (_NEG_WEIGHT - 1.0) * neg + _ALPHA)), 3)})
		return out
	except Exception:
		return out


# ── API pública: medidas de red agregadas (v1.0.65) ───────────────────────────

def get_net(key):
	"""Devuelve (valor, muestras) de net_stats. (0.0, 0) si no existe."""
	con = None
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute('SELECT num, cnt FROM net_stats WHERE key = ?', (key,))
		row = cur.fetchone()
		if not row:
			return (0.0, 0)
		return (float(row['num'] or 0.0), int(row['cnt'] or 0))
	except Exception:
		return (0.0, 0)
	finally:
		try:
			if con is not None: con.close()
		except Exception: pass


def update_net_ewma(key, value, alpha=0.30):
	"""
	Incorpora una medida a la media exponencial de `key`.

	La primera muestra se toma tal cual; a partir de ahí
	nuevo = alpha·medida + (1-alpha)·anterior.
	"""
	con = None
	try:
		value = float(value)
		if value <= 0:
			return
		prev, cnt = get_net(key)
		new = value if cnt <= 0 else (alpha * value + (1.0 - alpha) * prev)
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute('''
			INSERT INTO net_stats (key, num, cnt, last_ts) VALUES (?, ?, 1, ?)
			ON CONFLICT(key) DO UPDATE SET num = ?, cnt = cnt + 1, last_ts = ?
		''', (key, new, int(time()), new, int(time())))
		con.commit()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try:
			if con is not None: con.close()
		except Exception: pass


# ── API pública: introspección y mantenimiento ────────────────────────────────

def get_stats():
	"""
	Devuelve resumen del modelo para mostrar al usuario.

	Returns:
		{
			'total_plays': N,
			'features': [
				{'type': 'quality', 'value': '4K', 'pos': 12, 'exp': 30,
				 'win_rate': 0.40, 'log_odds': 0.32},
				...
			]
		}
	"""
	try:
		feats = _load_features()
		out_feats = []
		for k, (pos, exp, neg) in feats.items():
			ftype, fval = k.split(':', 1)
			skipped = max(0, exp - pos)
			win_rate = (pos / float(exp)) if exp else 0.0
			lo = log((pos + _ALPHA) / (skipped + (_NEG_WEIGHT - 1.0) * neg + _ALPHA))
			out_feats.append({
				'type': ftype, 'value': fval,
				'pos': pos, 'exp': exp, 'neg': neg,
				'win_rate': round(win_rate, 3),
				'log_odds': round(lo, 3),
			})
		# Ordenar por log_odds desc para que las más preferidas salgan arriba
		out_feats.sort(key=lambda x: (-x['log_odds'], -x['exp']))
		return {'total_plays': _total_plays(), 'features': out_feats}
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return {'total_plays': 0, 'features': []}


def reset():
	"""Borra todo el modelo. Acción destructiva — confirmar antes de llamar."""
	try:
		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		cur.execute('DELETE FROM source_features')
		cur.execute('DELETE FROM net_stats')
		con.commit()
		_invalidate_cache()
		return True
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return False
	finally:
		try: con.close()
		except Exception: pass
