# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Personalized Source Ranker

	Aprende qué fuentes prefiere el usuario y ajusta el orden de autoplay
	en consecuencia. Modelo: log-odds suavizados con prior Laplace por feature.

	Schema
	──────
	source_features(feature_key, feature_type, feature_value,
	                pos_count, neg_count, exp_count, last_ts)
		feature_key   : tipo:valor  (e.g. 'quality:4K', 'provider:torrentio')
		pos_count     : veces que el usuario eligió una fuente con esta feature
		neg_count     : (reservado — fase 2)
		exp_count     : veces que se mostró pero se saltó

	Modelo
	──────
	Para cada feature F de una fuente, contribución:
		log( (pos[F] + α) / (skipped[F] + α) )
	donde skipped = exp - pos. α=1.0 (prior Laplace = shrinkage).

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


def featurize(item):
	"""
	Extrae las features de una fuente. Devuelve lista de claves
	'tipo:valor'. Cualquier dato faltante se omite (no contribuye).

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
	return feats


# ── Lectura del modelo (con caché) ────────────────────────────────────────────

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
		cur.execute('SELECT feature_key, pos_count, exp_count FROM source_features')
		for row in cur.fetchall():
			out[row['feature_key']] = (int(row['pos_count']), int(row['exp_count']))
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
	for k, (pos, _) in feats.items():
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
		if getSetting('personal.ranker.enabled') != 'true':
			return 0.0
		feats = _load_features()
		if not feats:
			return 0.0
		# Guardia anti-overfitting con pocos datos
		total = 0
		for k, (pos, _) in feats.items():
			if k.startswith('quality:'):
				total += pos
		if total < _MIN_TOTAL_PLAYS:
			return 0.0
		item_feats = featurize(item)
		score = 0.0
		for f in item_feats:
			pos, exp = feats.get(f, (0, 0))
			skipped = max(0, exp - pos)
			# Log-odds Laplace-suavizado
			score += log((pos + _ALPHA) / (skipped + _ALPHA))
		return score
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return 0.0


# ── API pública: registro de eventos ──────────────────────────────────────────

def record_choice(chosen_item, all_items=None):
	"""
	Llamado cuando el usuario (o autoplay) confirma una fuente.

	chosen_item : dict de la fuente que se va a reproducir → +1 pos +1 exp
	all_items   : lista de fuentes mostradas/intentadas antes de la elegida
	              → cada una recibe +1 exp (sin pos), señalando "fue saltada".
	              Si es None, solo se registra la elegida.

	No bloqueante en caso de error — nunca debe romper la reproducción.
	"""
	if getSetting('personal.ranker.enabled') != 'true':
		return
	try:
		ts = int(time())
		# Acumular updates por feature_key para hacer un único batch
		updates = {}  # key -> (pos_delta, exp_delta, type, value)

		def _accumulate(item, is_chosen):
			for f in featurize(item):
				ftype, fval = f.split(':', 1)
				p, e = (1, 1) if is_chosen else (0, 1)
				if f in updates:
					op, oe, _, _ = updates[f]
					updates[f] = (op + p, oe + e, ftype, fval)
				else:
					updates[f] = (p, e, ftype, fval)

		_accumulate(chosen_item, True)
		if all_items:
			for it in all_items:
				if it is chosen_item:
					continue
				_accumulate(it, False)

		if not updates:
			return

		con = _connect()
		cur = con.cursor()
		_ensure_table(cur)
		for key, (pd, ed, ftype, fval) in updates.items():
			cur.execute('''
				INSERT INTO source_features
					(feature_key, feature_type, feature_value, pos_count, neg_count, exp_count, last_ts)
				VALUES (?, ?, ?, ?, 0, ?, ?)
				ON CONFLICT(feature_key) DO UPDATE SET
					pos_count = pos_count + ?,
					exp_count = exp_count + ?,
					last_ts   = ?
			''', (key, ftype, fval, pd, ed, ts, pd, ed, ts))
		con.commit()
		_invalidate_cache()
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		try: con.close()
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
		for k, (pos, exp) in feats.items():
			ftype, fval = k.split(':', 1)
			skipped = max(0, exp - pos)
			win_rate = (pos / float(exp)) if exp else 0.0
			lo = log((pos + _ALPHA) / (skipped + _ALPHA))
			out_feats.append({
				'type': ftype, 'value': fval,
				'pos': pos, 'exp': exp,
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
