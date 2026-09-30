# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — maintenance.py (v1.0.94)

	LA SONDA DE LIMPIEZA: MEDIR, DECIDIR Y RECOGER LO QUE DEJA EL ADDON.

	El addon esta hecho para verse bien: poster grande, fanart a tamano de
	pantalla, logos. Cada ficha que se hojea deja ese arte en Textures13.db y
	en la carpeta Thumbnails, y Kodi NUNCA lo vacia por su cuenta. Quien vigila
	el almacenamiento lo nota; quien no, se encuentra un dia el aparato lleno.
	La respuesta no es bajar la calidad —esa es una eleccion del usuario y el
	addon esta para sostenerla— sino recoger detras, solo lo que ya no se usa.

	TRES NIVELES, SEGUN LO QUE CUESTA VOLVER A TENERLO:

	  LIGERO (al salir del addon, siempre que el modo no sea Off). Lo que
	  caduca solo o ya no sirve: las listas de fuentes guardadas en window
	  properties (varios MB de JSON por titulo), las filas de providers.db mas
	  viejas que su TTL mas largo (168 h) y los temporales propios. Instantaneo
	  y sin coste al volver.

	  PESADO (cuando la sonda dice que merece la pena). El arte sin mostrarse
	  desde hace N dias, el arte que excede el tope de almacenamiento (se suelta
	  primero lo que hace mas tiempo que no se ve), el mantenimiento mensual de
	  las bases de cache, el VACUUM de las que tienen mucho hueco libre y el log
	  propio si se ha disparado. Nunca se toca lo mostrado en las ultimas dos
	  horas: borrar lo que esta en pantalla solo sirve para volver a bajarlo.

	  NUNCA. traktsync, simklsync, watched, source_ranker, reco_feedback,
	  titlesubs, undesirables y los ajustes. Son estado del usuario, no cache.

	CUANDO. Kodi no avisa de que se sale de un plugin, asi que el servicio lo
	detecta: Container.PluginName deja de ser luc_kodi y sigue asi unos
	segundos, sin reproduccion ni dialogo modal abierto (todas las ventanas
	propias del addon son dialogos). Al cerrar Kodi no se limpia nada —hay
	unos cinco segundos antes de que Kodi mate el servicio, el JSON-RPC ya no
	responde y cortar un VACUUM a medias es mala idea—: solo se deja marcada
	la limpieza como pendiente y se hace en el siguiente arranque, en reposo.

	POR QUE NO FUNCIONABA LA LIMPIEZA DE 1/3/7 DIAS (hasta la 1.0.93).
	poster_rotator.clean_texture_cache() pedia a Textures.GetTextures la
	propiedad 'lastused', que no existe en el nivel de la textura (vive dentro
	de 'sizes'): Kodi rechaza la llamada entera, llega una lista vacia, la
	funcion devolvia un 0 suelto y quien la llamaba desempaquetaba tres
	valores. TypeError tragado por el except, la marca de ultima pasada no se
	escribia nunca y se reintentaba cada minuto sin borrar nada. Aqui se lee
	la fecha de ultimo uso de 'sizes' directamente de Textures13.db en solo
	lectura —como ya hacia el contador de espacio— y se borra SIEMPRE por
	Textures.RemoveTexture, la unica forma segura con Kodi vivo.
"""

import os
import time

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.modules import cache_footprint as fp

try:
	from json import loads as jsloads, dumps as jsdumps
except ImportError:
	jsloads = jsdumps = None

getSetting = control.setting
homeWindow = control.homeWindow

_MB = 1048576
_HEADING = 'luc_kodi — Maintenance'

# Modo (enum de settings.xml: Kodi guarda el INDICE)
MODE_OFF, MODE_ASK, MODE_AUTO = 0, 1, 2
_MODE_SETTING = 'maint.mode'

# Tope de arte. None = automatico segun el almacenamiento, 0 = sin tope.
_BUDGET_SETTING = 'maint.art.budget'
_BUDGET_MB = (None, 300, 600, 1024, 2048, 0)
_AUTO_SHARE = 0.04                 # 4% del almacenamiento donde vive Thumbnails
_AUTO_MIN = 400 * _MB
_AUTO_MAX = 2048 * _MB
_AUTO_FLOOR_TIGHT = 250 * _MB      # suelo cuando el aparato va justo de espacio

# Dias sin mostrarse (ajuste que ya existia, se conserva el id)
_DAYS_SETTING = 'poster.rotation.cleanup.days'
_DAYS_CHOICES = (1, 3, 7)
_DAYS_DEFAULT = 7

# Marcadores
_LEGACY_TOGGLE = 'poster.rotation.cleanup'   # interruptor viejo, solo para migrar
_MIGRATED_SETTING = 'maint.migrated'
_PENDING_SETTING = 'maint.pending'
_ART_LASTRUN = 'poster.rotation.lastclean'
_DB_LASTRUN = 'db.maintenance.lastrun'

# Estado de la sesion (window properties: no se escriben ajustes por cada cosa)
_DUE_PROP = 'luc_kodi.maint.due'
_BUSY_PROP = 'luc_kodi.maint.busy'
_SNOOZE_PROP = 'luc_kodi.maint.snooze'
_APPROVED_PROP = 'luc_kodi.maint.approved'  # el usuario dijo que si y quedo cola

PROTECT_RECENT_SECONDS = 2 * 3600  # lo visto en las ultimas 2 h no se toca nunca
MAX_PER_PASS = 1500                # tope de texturas por pasada
_YIELD_EVERY = 50                  # cada cuantas borradas se cede un instante
ASK_MIN_BYTES = 50 * _MB           # por debajo no se molesta con una pregunta
AUTO_MIN_BYTES = 1 * _MB
SNOOZE_SECONDS = 12 * 3600         # tras "Later", no se vuelve a preguntar en 12 h
PROVIDERS_MAX_AGE = 7 * 86400      # el TTL mas largo de providers.db es 168 h
LOG_MAX_BYTES = 10 * _MB
VACUUM_MIN_BYTES = 8 * _MB
VACUUM_MIN_RATIO = 0.25
DB_EVERY_SECONDS = 30 * 86400

STARTUP_DELAY = 120                # el precache rapido tarda segundos; 2 min sobra
POLL_SECONDS = 2
LEAVE_TICKS = 4                    # 4 x 2 s fuera del addon = ha salido
REPROBE_SECONDS = 6 * 3600
REUSE_PROBE_SECONDS = 60          # dos sondas seguidas miden lo mismo: se reutiliza

_TEMP_FILES = ('special://temp/punchplay_qr.png',)
_LOG_FILES = ('luc_kodi.log', 'jacksparrowscrapers.log')


# ─────────────────────────────────────────────────────────────────────────────
#  Ajustes
# ─────────────────────────────────────────────────────────────────────────────

def mode():
	raw = (getSetting(_MODE_SETTING) or '').strip()
	try:
		n = int(raw)
	except Exception:
		return MODE_ASK
	return n if n in (MODE_OFF, MODE_ASK, MODE_AUTO) else MODE_ASK


def art_days():
	# Igual que hacia poster_rotator: el enum puede traer el literal ('7') o
	# el indice ('2') segun la plataforma. El literal manda porque es
	# inequivoco; solo si no es un dia valido se lee como indice.
	raw = (getSetting(_DAYS_SETTING) or '').strip()
	try:
		n = int(raw)
	except Exception:
		return _DAYS_DEFAULT
	if n in _DAYS_CHOICES: return n
	if 0 <= n < len(_DAYS_CHOICES): return _DAYS_CHOICES[n]
	return _DAYS_DEFAULT


def _storage(path):
	"""(total, libre) en bytes del volumen de `path`. (0, 0) si no se puede."""
	try:
		st = os.statvfs(path)
		return st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
	except Exception:
		return 0, 0


def art_budget(root=None):
	"""Tope de arte en bytes; 0 = sin tope.

	Automatico: el 4% del volumen, entre 400 MB y 2 GB. Con los numeros
	medidos (mediana de 224 KB por imagen en Original) 1 GB son unas 4.700
	imagenes: de sobra para todo lo que se ve a diario. Si el aparato va
	justo —menos de 2 GB o del 10% libre— el tope se parte por la mitad.
	"""
	try:
		idx = int((getSetting(_BUDGET_SETTING) or '0').strip())
	except Exception:
		idx = 0
	if not 0 <= idx < len(_BUDGET_MB): idx = 0
	fixed = _BUDGET_MB[idx]
	if fixed == 0: return 0
	if fixed: return fixed * _MB
	total, free = _storage(root or fp._thumb_root() or control.transPath('special://profile/'))
	if not total: return 1024 * _MB
	budget = min(max(int(total * _AUTO_SHARE), _AUTO_MIN), _AUTO_MAX)
	if free < max(2048 * _MB, total * 0.10):
		budget = max(_AUTO_FLOOR_TIGHT, budget // 2)
	return budget


def _db_enabled():
	try: return getSetting('db.maintenance') != 'false'
	except Exception: return True


def migrate_once():
	"""El interruptor viejo de limpieza de arte pasa al modo nuevo una sola vez.
	Solo cuenta un 'false' explicito: quien lo apago a mano lo queria apagado."""
	try:
		if getSetting(_MIGRATED_SETTING) == 'done': return
		if getSetting(_LEGACY_TOGGLE) == 'false':
			control.setSetting(_MODE_SETTING, str(MODE_OFF))
		control.setSetting(_MIGRATED_SETTING, 'done')
	except Exception:
		log_utils.error()


# ─────────────────────────────────────────────────────────────────────────────
#  Medir
# ─────────────────────────────────────────────────────────────────────────────

def _epoch(stamp):
	"""'YYYY-MM-DD HH:MM:SS' (hora local, como la guarda Kodi) a epoch. 0 si no se sabe."""
	if not stamp: return 0
	try:
		return int(time.mktime(time.strptime(str(stamp)[:19], '%Y-%m-%d %H:%M:%S')))
	except Exception:
		return 0


def _texture_rows():
	"""[(id, cachedurl, ultimo_uso)] de las texturas de NUESTROS proveedores.

	Solo lectura sobre Textures13.db. La fecha de ultimo uso esta en la tabla
	'sizes' (una fila por tamano cacheado); se toma la mas reciente.
	"""
	path = fp._texture_db()
	if not path: return []
	import sqlite3
	conn = None
	raw = []
	try:
		safe = path.replace('?', '%3f').replace('#', '%23')
		try:
			conn = sqlite3.connect('file:%s?mode=ro' % safe, uri=True, timeout=2)
		except Exception:
			conn = sqlite3.connect(path, timeout=2)
		for like in fp.ART_LIKES:
			try:
				raw += conn.execute(
					'SELECT t.id, t.cachedurl, MAX(s.lastusetime) FROM texture t '
					'LEFT JOIN sizes s ON s.idtexture = t.id '
					'WHERE t.url LIKE ? GROUP BY t.id', (like,)).fetchall()
			except Exception:
				# Esquema sin 'sizes': se cuenta, pero sin fecha no se borra por edad
				try:
					raw += [(r[0], r[1], None) for r in conn.execute(
						'SELECT id, cachedurl FROM texture WHERE url LIKE ?', (like,)).fetchall()]
				except Exception:
					continue
	except Exception:
		log_utils.error()
	finally:
		try:
			if conn: conn.close()
		except Exception:
			pass
	out, seen = [], set()
	for tid, cached, last in raw:
		if not cached or tid in seen: continue
		seen.add(tid)
		out.append((tid, cached, _epoch(last)))
	return out


def _regenerable_dbs():
	return [p for p in (control.metacacheFile, control.cacheFile,
	                    control.fanarttvCacheFile, control.providercacheFile) if p]


def _vacuum_candidates():
	"""[(ruta, bytes_libres)] de las bases de cache con mucho hueco dentro.
	Un DELETE deja paginas libres pero el fichero no encoge sin VACUUM."""
	import sqlite3
	out = []
	for path in _regenerable_dbs():
		conn = None
		try:
			if not os.path.isfile(path): continue
			safe = path.replace('?', '%3f').replace('#', '%23')
			try:
				conn = sqlite3.connect('file:%s?mode=ro' % safe, uri=True, timeout=2)
			except Exception:
				conn = sqlite3.connect(path, timeout=2)
			page = conn.execute('PRAGMA page_size').fetchone()[0]
			pages = conn.execute('PRAGMA page_count').fetchone()[0]
			free = conn.execute('PRAGMA freelist_count').fetchone()[0]
			free_bytes = int(page) * int(free)
			if pages and free_bytes >= VACUUM_MIN_BYTES and float(free) / pages >= VACUUM_MIN_RATIO:
				out.append((path, free_bytes))
		except Exception:
			pass
		finally:
			try:
				if conn: conn.close()
			except Exception:
				pass
	return out


def _db_due():
	if not _db_enabled(): return False
	try: last = float(getSetting(_DB_LASTRUN) or 0)
	except Exception: last = 0
	return (time.time() - last) >= DB_EVERY_SECONDS


def _ram_lists():
	try:
		raw = homeWindow.getProperty('luc_kodi.ramcache_index')
		keys = jsloads(raw) if raw else []
		return keys if isinstance(keys, list) else []
	except Exception:
		return []


def _old_provider_rows():
	import sqlite3
	path = control.providercacheFile
	conn = None
	try:
		if not os.path.isfile(path): return 0
		safe = path.replace('?', '%3f').replace('#', '%23')
		try:
			conn = sqlite3.connect('file:%s?mode=ro' % safe, uri=True, timeout=2)
		except Exception:
			conn = sqlite3.connect(path, timeout=2)
		return int(conn.execute('SELECT COUNT(*) FROM cache WHERE date < ?',
		                        (int(time.time()) - PROVIDERS_MAX_AGE,)).fetchone()[0])
	except Exception:
		return 0
	finally:
		try:
			if conn: conn.close()
		except Exception:
			pass


def _big_logs():
	out = []
	for name in _LOG_FILES:
		try:
			path = os.path.join(control.transPath('special://logpath/'), name)
			if os.path.isfile(path):
				size = os.path.getsize(path)
				if size > LOG_MAX_BYTES: out.append((path, size))
		except Exception:
			continue
	return out


def _temp_files():
	out = []
	for special in _TEMP_FILES:
		try:
			path = control.transPath(special)
			if os.path.isfile(path): out.append(path)
		except Exception:
			continue
	return out


def probe():
	"""Mide lo que ha dejado el addon y decide que sobra. No borra nada."""
	now = time.time()
	root = fp._thumb_root()
	days = art_days()
	items = []
	unknown = 0
	if root:
		for tid, cached, last in _texture_rows():
			try:
				size = os.path.getsize(os.path.join(root, cached.replace('/', os.sep)))
			except OSError:
				continue  # fila sin fichero: no ocupa disco, preguntar por ella encarece la pasada
			if not last: unknown += 1
			items.append((last, tid, size))
	art_bytes = sum(i[2] for i in items)
	budget = art_budget(root)
	known = sorted(i for i in items if i[0])
	cutoff = now - days * 86400
	protect = now - PROTECT_RECENT_SECONDS

	old = [(tid, size) for last, tid, size in known if last < cutoff]
	old_ids = set(tid for tid, _s in old)
	old_bytes = sum(s for _t, s in old)
	over, over_bytes = [], 0
	left = art_bytes - old_bytes
	if budget and left > budget:
		for last, tid, size in known:
			if left <= budget: break
			if tid in old_ids or last >= protect: continue
			over.append((tid, size))
			over_bytes += size
			left -= size

	vacuum = _vacuum_candidates()
	logs = _big_logs()
	rep = {
		'ts': now,
		'days': days,
		'budget': budget,
		'art_count': len(items),
		'art_bytes': art_bytes,
		'art_unknown': unknown,
		'art_old': old,
		'art_old_bytes': old_bytes,
		'art_over': over,
		'art_over_bytes': over_bytes,
		'db_due': _db_due(),
		'db_vacuum': vacuum,
		'logs': logs,
		'ram_lists': len(_ram_lists()),
		'provider_rows': _old_provider_rows(),
		'temp': _temp_files(),
	}
	rep['freeable'] = old_bytes + over_bytes + sum(b for _p, b in vacuum) + sum(b for _p, b in logs)
	rep['heavy'] = bool(old or over or rep['db_due'] or vacuum or logs)
	rep['worth_asking'] = rep['freeable'] >= ASK_MIN_BYTES or rep['db_due']
	rep['light'] = bool(rep['ram_lists'] or rep['provider_rows'] or rep['temp'])
	try: homeWindow.setProperty(_DUE_PROP, 'true' if rep['heavy'] else '')
	except Exception: pass
	log_utils.log('[ plugin.video.luc_kodi ]  Sonda de limpieza: arte %s en %d imagenes (tope %s, %d sin fecha), '
	              '%d sin verse en %d dias (%s), %d sobre el tope (%s), bases %s, %d huecos a compactar, '
	              '%d listas en RAM, %d filas caducadas de providers'
	              % (fp.human(art_bytes), len(items), fp.human(budget) if budget else 'sin tope', unknown,
	                 len(old), days, fp.human(old_bytes), len(over), fp.human(over_bytes),
	                 'vencidas' if rep['db_due'] else 'al dia', len(vacuum), rep['ram_lists'], rep['provider_rows']),
	              __name__, log_utils.LOGINFO)
	return rep


# ─────────────────────────────────────────────────────────────────────────────
#  Limpiar
# ─────────────────────────────────────────────────────────────────────────────

def _inside_addon():
	try:
		return bool(control.condVisibility('String.IsEqual(Container.PluginName,plugin.video.luc_kodi)'))
	except Exception:
		return False


def _playing():
	try:
		return bool(control.condVisibility('Player.HasMedia'))
	except Exception:
		return False


def light_clean():
	"""Nivel ligero: listas de fuentes en RAM, filas caducadas de providers.db y
	temporales. Instantaneo; nada de esto hace falta al volver."""
	out = {'ram_lists': 0, 'provider_rows': 0, 'temp': 0}
	keys = _ram_lists()
	for key in keys:
		try:
			homeWindow.clearProperty('luc_kodi.ramcache.' + key)
			homeWindow.clearProperty('luc_kodi.ramcache_ts.' + key)
		except Exception:
			pass
	try: homeWindow.clearProperty('luc_kodi.ramcache_index')
	except Exception: pass
	out['ram_lists'] = len(keys)

	import sqlite3
	path = control.providercacheFile
	conn = None
	try:
		if os.path.isfile(path):
			conn = sqlite3.connect(path, timeout=10)
			cur = conn.execute('DELETE FROM cache WHERE date < ?', (int(time.time()) - PROVIDERS_MAX_AGE,))
			out['provider_rows'] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
			conn.commit()
	except Exception:
		pass  # tabla aun sin crear, o base ocupada: se hara en la siguiente
	finally:
		try:
			if conn: conn.close()
		except Exception:
			pass

	for path in _temp_files():
		try:
			os.remove(path)
			out['temp'] += 1
		except Exception:
			pass
	return out


def _remove_texture(tid):
	try:
		raw = control.jsonrpc(jsdumps({'jsonrpc': '2.0', 'id': 1,
		                               'method': 'Textures.RemoveTexture',
		                               'params': {'textureid': int(tid)}}))
		return bool(raw) and '"error"' not in raw
	except Exception:
		return False


def _file_size(path):
	try: return os.path.getsize(path)
	except Exception: return 0


def _vacuum(path):
	import sqlite3
	conn = None
	try:
		conn = sqlite3.connect(path, timeout=10)
		conn.execute('VACUUM')
		return True
	except Exception:
		return False  # base en uso: queda para la siguiente
	finally:
		try:
			if conn: conn.close()
		except Exception:
			pass


def heavy_clean(rep, progress=None, foreground=False):
	"""Nivel pesado segun lo que dijo la sonda. `progress` es un objeto con
	update(pct, msg) y cancelled(), o None. `foreground` = lo ha pedido el
	usuario a mano y espera delante: se hace todo sin aplazar. Devuelve el
	resumen."""
	res = {'art_removed': 0, 'art_failed': 0, 'art_bytes': 0,
	       'db_rows': 0, 'db_bytes': 0, 'logs': 0, 'deferred': False}
	targets = (list(rep.get('art_old') or []) + list(rep.get('art_over') or []))[:MAX_PER_PASS]
	total = len(targets)
	for index, (tid, size) in enumerate(targets):
		if control.monitor.abortRequested(): res['deferred'] = True; break
		if not foreground and _playing(): res['deferred'] = True; break  # el usuario manda
		if progress is not None:
			if progress.cancelled(): res['deferred'] = True; break
			progress.update(int(index * 80.0 / max(total, 1)), 'Artwork %d / %d' % (index + 1, total))
		if _remove_texture(tid):
			res['art_removed'] += 1
			res['art_bytes'] += size
		else:
			res['art_failed'] += 1
		if (index + 1) % _YIELD_EVERY == 0:
			control.sleep(50)
	if total:
		control.setSetting(_ART_LASTRUN, str(int(time.time())))
	if len(rep.get('art_old') or []) + len(rep.get('art_over') or []) > MAX_PER_PASS:
		res['deferred'] = True  # cola grande: el resto en la siguiente pasada

	# Las bases solo con el usuario fuera del addon: un VACUUM bloquea la base
	# unos segundos y no debe coincidir con un menu cargandose.
	db_work = rep.get('db_due') or rep.get('db_vacuum')
	if db_work and not foreground and (_inside_addon() or _playing()):
		res['deferred'] = True
	elif db_work and not control.monitor.abortRequested():
		if progress is not None: progress.update(85, 'Cache databases')
		paths = _regenerable_dbs()
		before = sum(_file_size(p) for p in paths)
		vacuumed = set()
		if rep.get('db_due'):
			try:
				from resources.lib.modules import cache_janitor
				res['db_rows'] = cache_janitor.prune_databases()  # purga + VACUUM de lo purgado
				control.setSetting(_DB_LASTRUN, str(int(time.time())))
			except Exception:
				log_utils.error()
		for path, _free in rep.get('db_vacuum') or []:
			if path not in vacuumed and _vacuum(path): vacuumed.add(path)
		res['db_bytes'] = max(0, before - sum(_file_size(p) for p in paths))

	for path, size in rep.get('logs') or []:
		try:
			with open(path, 'r+') as fh:
				fh.truncate(0)
			res['logs'] += size
		except Exception:
			pass
	if progress is not None: progress.update(100, '')
	res['freed'] = res['art_bytes'] + res['db_bytes'] + res['logs']
	log_utils.log('[ plugin.video.luc_kodi ]  Limpieza: %d texturas borradas (%s, %d fallidas), %d filas de cache '
	              'purgadas, %s devueltos por las bases, %s de log%s'
	              % (res['art_removed'], fp.human(res['art_bytes']), res['art_failed'], res['db_rows'],
	                 fp.human(res['db_bytes']), fp.human(res['logs']), ', quedan cosas para la siguiente' if res['deferred'] else ''),
	              __name__, log_utils.LOGINFO)
	return res


# ─────────────────────────────────────────────────────────────────────────────
#  Texto para el usuario
# ─────────────────────────────────────────────────────────────────────────────

def describe(rep, include_light=False):
	lines = []
	limit = fp.human(rep['budget']) if rep['budget'] else 'no limit'
	lines.append('Artwork on this device: [B]%s[/B] in %d images (limit: %s)'
	             % (fp.human(rep['art_bytes']), rep['art_count'], limit))
	if rep['art_old']:
		lines.append('• %d images not shown for %d+ days (%s)'
		             % (len(rep['art_old']), rep['days'], fp.human(rep['art_old_bytes'])))
	if rep['art_over']:
		lines.append('• %d older images above the artwork limit (%s)'
		             % (len(rep['art_over']), fp.human(rep['art_over_bytes'])))
	if rep['db_due']:
		lines.append('• Cache databases: monthly tidy-up')
	vac = sum(b for _p, b in rep['db_vacuum'])
	if vac:
		lines.append('• Cache databases: %s of empty space to give back' % fp.human(vac))
	if rep['logs']:
		lines.append('• Add-on log: %s' % fp.human(sum(b for _p, b in rep['logs'])))
	if include_light:
		if rep['ram_lists']:
			lines.append('• %d source lists kept in memory' % rep['ram_lists'])
		if rep['provider_rows']:
			lines.append('• %d expired source results' % rep['provider_rows'])
		if rep['temp']:
			lines.append('• %d temporary files' % len(rep['temp']))
	return lines


_FOOTER = ('Only what luc_kodi fetches again when it is needed is removed. '
	'Your history, progress, lists and settings are never touched.')


class _FgProgress(object):
	def __init__(self):
		self.dlg = control.progressDialog
		self.dlg.create(_HEADING, 'Cleaning up...')
	def update(self, pct, msg):
		try: self.dlg.update(int(pct), msg or 'Cleaning up...')
		except Exception: pass
	def cancelled(self):
		try: return self.dlg.iscanceled()
		except Exception: return False
	def close(self):
		try: self.dlg.close()
		except Exception: pass


class _BgProgress(object):
	def __init__(self):
		import xbmcgui
		self.dlg = xbmcgui.DialogProgressBG()  # instancia propia: la de control la usan otros
		self.dlg.create(_HEADING, 'Cleaning up...')
	def update(self, pct, msg):
		try: self.dlg.update(int(pct), _HEADING, msg or 'Cleaning up...')
		except Exception: pass
	def cancelled(self):
		return control.monitor.abortRequested() or _playing()
	def close(self):
		try: self.dlg.close()
		except Exception: pass


def _finish(res, pending_left):
	try:
		if pending_left:
			control.setSetting(_PENDING_SETTING, 'true')
		elif getSetting(_PENDING_SETTING) == 'true':
			control.setSetting(_PENDING_SETTING, '')
		homeWindow.setProperty(_DUE_PROP, 'true' if pending_left else '')
	except Exception:
		pass


def _run(rep, progress):
	homeWindow.setProperty(_BUSY_PROP, 'true')
	try:
		light_clean()
		res = heavy_clean(rep, progress, foreground=True)
	finally:
		homeWindow.clearProperty(_BUSY_PROP)
		if progress is not None: progress.close()
	_finish(res, res['deferred'])
	if res['deferred']: homeWindow.setProperty(_APPROVED_PROP, 'true')
	return res


def clean_now():
	"""Tools / Settings > Maintenance > Clean up now. Funciona en cualquier modo."""
	if homeWindow.getProperty(_BUSY_PROP) == 'true':
		control.notification(message='A cleanup is already running')
		return
	control.busy()
	try:
		rep = probe()
	finally:
		control.hide()
	lines = describe(rep, include_light=True)
	if not rep['heavy'] and not rep['light']:
		control.okDialog(_HEADING, '[CR]'.join(lines + ['', 'Nothing to clean up — luc_kodi is tidy.']))
		return
	text = '[CR]'.join(lines + ['', _FOOTER])
	if not control.dialog.yesno(_HEADING, text, nolabel='Cancel', yeslabel='Clean up'):
		return
	res = _run(rep, _FgProgress())
	control.notification(message='Cleanup done — %s freed' % fp.human(res['freed']))


def _ask(rep, pending):
	head = ('A cleanup is pending from your last session. ' if pending else '') + \
	       'luc_kodi can free [B]%s[/B] on this device:' % fp.human(rep['freeable'])
	lines = describe(rep)[1:]
	text = '[CR]'.join([head] + lines + ['', _FOOTER])
	return control.dialog.yesno(_HEADING, text, nolabel='Later', yeslabel='Clean up')


def _snoozed():
	try: return time.time() < float(homeWindow.getProperty(_SNOOZE_PROP) or 0)
	except Exception: return False


def _snooze():
	homeWindow.setProperty(_SNOOZE_PROP, str(time.time() + SNOOZE_SECONDS))


def _background(rep, approved=False):
	bar = _BgProgress() if len(rep['art_old']) + len(rep['art_over']) > 200 else None
	homeWindow.setProperty(_BUSY_PROP, 'true')
	try:
		res = heavy_clean(rep, bar)
	finally:
		homeWindow.clearProperty(_BUSY_PROP)
		if bar is not None: bar.close()
	_finish(res, res['deferred'])
	if res['deferred'] and approved: homeWindow.setProperty(_APPROVED_PROP, 'true')
	else: homeWindow.clearProperty(_APPROVED_PROP)
	if res['freed'] >= 5 * _MB:
		control.notification(message='Cleanup done — %s freed' % fp.human(res['freed']))
	return res


def _handle(rep, m, pending=False, ask_ok=True):
	"""Decide que hacer con una sonda segun el modo."""
	if homeWindow.getProperty(_BUSY_PROP) == 'true': return
	if not rep['heavy']:
		# Nada pesado que hacer: si habia una pendiente, ya no lo esta.
		_finish({'deferred': False}, False)
		homeWindow.clearProperty(_APPROVED_PROP)
		return
	if m != MODE_OFF and homeWindow.getProperty(_APPROVED_PROP) == 'true':
		# Continuacion de una limpieza que el usuario ya aprobo: sin volver a preguntar.
		_background(rep, approved=True)
	elif m == MODE_AUTO:
		if rep['freeable'] >= AUTO_MIN_BYTES or rep['db_due'] or pending:
			_background(rep)
	elif m == MODE_ASK and ask_ok and (rep['worth_asking'] or pending) and not _snoozed():
		if _ask(rep, pending):
			_background(rep, approved=True)
		else:
			_snooze()


# ─────────────────────────────────────────────────────────────────────────────
#  Servicio
# ─────────────────────────────────────────────────────────────────────────────

def service_loop():
	"""Vigila la salida del addon, hace la pasada diferida del arranque y la
	re-evaluacion periodica. Al cerrar Kodi solo deja marcada la pendiente."""
	monitor = control.monitor
	migrate_once()
	boot = time.time()
	inside = False       # dentro de un tramo con el addon (o sus dialogos) delante
	saw_addon = False    # en ese tramo se vio luc_kodi de verdad, no solo un dialogo ajeno
	outside_ticks = 0
	startup_done = False
	last_probe = 0.0
	last_rep = None
	while not monitor.abortRequested():
		try:
			in_addon = _inside_addon()
			busy_screen = in_addon or _playing() or bool(control.condVisibility('System.HasModalDialog'))
			if in_addon: saw_addon = True
			if busy_screen:
				inside = True
				outside_ticks = 0
			elif inside:
				outside_ticks += 1
				if outside_ticks >= LEAVE_TICKS:
					inside = False
					if saw_addon:
						m = mode()
						if m != MODE_OFF:
							light_clean()
							# v1.0.94: en el aparato, la pasada de arranque y la de
							# salida caian con 6 s de diferencia y median lo mismo.
							# Solo se reutiliza una sonda que no encontro nada: si
							# encontro algo, pudo limpiarse ya y habria que medir.
							if last_rep is None or last_rep['heavy'] or time.time() - last_probe > REUSE_PROBE_SECONDS:
								last_rep = probe()
								last_probe = time.time()
							_handle(last_rep, m)
					saw_addon = False
			if not startup_done and not busy_screen and time.time() - boot >= STARTUP_DELAY:
				startup_done = True
				m = mode()
				pending = getSetting(_PENDING_SETTING) == 'true'
				if m == MODE_OFF:
					if pending: control.setSetting(_PENDING_SETTING, '')
				else:
					rep = last_rep = probe()
					last_probe = time.time()
					# En Ask, al arrancar solo se pregunta si quedo algo pendiente
					# de la sesion anterior; lo demas espera a la salida del addon.
					_handle(rep, m, pending=pending, ask_ok=pending)
			elif startup_done and not busy_screen and time.time() - last_probe >= REPROBE_SECONDS:
				m = mode()
				last_probe = time.time()
				if m != MODE_OFF:
					rep = last_rep = probe()
					if m == MODE_AUTO: _handle(rep, m)
		except Exception:
			log_utils.error()
		if monitor.waitForAbort(POLL_SECONDS): break
	# Kodi se cierra: nada de trabajo aqui, solo la marca para el proximo arranque.
	try:
		if homeWindow.getProperty(_DUE_PROP) == 'true' and mode() != MODE_OFF:
			control.setSetting(_PENDING_SETTING, 'true')
	except Exception:
		pass
