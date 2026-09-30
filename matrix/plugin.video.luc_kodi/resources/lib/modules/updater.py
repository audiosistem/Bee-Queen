# -*- coding: utf-8 -*-
"""
	luc_kodi — canal de actualizacion propio (fase 1, v1.0.77)

	Solo entran compilaciones OFICIALES. Las de prueba siguen yendo a mano: el
	manifiesto tiene UNA entrada y se publica cuando la version se consolida.

	Regla que gobierna todo este fichero: NADA del arbol instalado se toca hasta
	que el reemplazo esta descargado, verificado por sha256, extraido y validado
	en disco. Fen hace `rmtree` del addon ANTES de descomprimir, de modo que un
	unzip fallido deja al usuario sin addon y sin el zip para reinstalarlo. Aqui
	el arbol viejo se aparta con un rename (reversible) y solo se borra cuando el
	nuevo ya esta en su sitio; si algo falla en cualquier peldaño, se devuelve a
	su nombre y el usuario sigue con su version funcionando.
"""

import hashlib, json, os, shutil, time, zipfile
import requests

from resources.lib.modules import control, log_utils

LOGINFO, LOGWARNING = log_utils.LOGINFO, log_utils.LOGWARNING

ADDON_ID = 'plugin.video.luc_kodi'
BASE = 'https://raw.githubusercontent.com/apoyotech/luc_repo/main/'
MANIFEST_URL = BASE + 'luc_kodi_update.json'

S_ENABLED = 'updater.enabled'
S_ON_START = 'updater.on_start'
S_INTERVAL = 'updater.interval_hours'
S_LASTRUN = 'updater.last_run'
S_SKIPPED = 'updater.skipped_version'

_INTERVAL_HOURS = (6, 12, 24, 48)   # debe coincidir con values= en settings.xml

CHECK_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60
CHUNK = 64 * 1024


# ─── utilidades ──────────────────────────────────────────────────────────────
def _now(): return int(time.time())

def _log(msg, level=LOGINFO):
	log_utils.log('[ luc_kodi ] updater: %s' % msg, __name__, level)

def installed_version():
	return control.addonInfo('version')

def parse_version(text):
	"""'1.0.76' -> (1, 0, 76). Comparar cadenas diria que '1.0.9' > '1.0.76'."""
	parts = []
	for chunk in str(text or '').strip().split('.'):
		digits = ''.join(c for c in chunk if c.isdigit())
		parts.append(int(digits) if digits else 0)
	while len(parts) < 3: parts.append(0)
	return tuple(parts[:4])

def is_newer(online, current):
	return parse_version(online) > parse_version(current)

def _get_int(setting_id, default):
	try: return int(control.setting(setting_id) or default)
	except Exception: return default

def _interval_hours():
	"""Kodi devuelve el INDICE de un enum, no el valor. Mismo tropiezo que ya
	costo un arreglo en catalog_updater (v1.0.54): se traduce por tabla, y si
	llega un valor de horas de verdad se acepta tambien."""
	raw = control.setting(S_INTERVAL)
	try: idx = int(raw)
	except Exception: return 24
	if idx in _INTERVAL_HOURS and idx not in range(len(_INTERVAL_HOURS)): return idx
	if 0 <= idx < len(_INTERVAL_HOURS): return _INTERVAL_HOURS[idx]
	return 24

def _is_due():
	last = _get_int(S_LASTRUN, 0)
	if not last: return True
	return (_now() - last) >= (_interval_hours() * 3600)


# ─── manifiesto ──────────────────────────────────────────────────────────────
def fetch_manifest():
	"""Devuelve el dict del manifiesto o None. Nunca lanza."""
	try:
		response = requests.get(MANIFEST_URL, timeout=CHECK_TIMEOUT,
								headers={'Accept': 'application/json', 'Cache-Control': 'no-cache'})
	except requests.exceptions.RequestException as e:
		_log('no se pudo leer el manifiesto (%s: %s)' % (type(e).__name__, e))
		return None
	if response.status_code != 200:
		_log('el manifiesto devolvio HTTP %s' % response.status_code, LOGWARNING)
		return None
	try: data = response.json()
	except Exception:
		_log('el manifiesto no es json valido', LOGWARNING)
		return None
	if not isinstance(data, dict): return None
	# Un manifiesto de otro addon no se aplica jamas.
	if data.get('addon') not in (None, ADDON_ID):
		_log('el manifiesto es de %s, se ignora' % data.get('addon'), LOGWARNING)
		return None
	if not data.get('version') or not data.get('zip'):
		_log('al manifiesto le faltan "version" o "zip"', LOGWARNING)
		return None
	if not data.get('sha256'):
		# Sin sha256 no hay forma de saber si el zip llego entero. Antes de eso,
		# no se actualiza: el precio de equivocarse aqui es dejar el addon roto.
		_log('el manifiesto no trae sha256; no se actualiza', LOGWARNING)
		return None
	return data


def zip_url(manifest):
	target = str(manifest.get('zip'))
	if target.startswith('http://') or target.startswith('https://'): return target
	return BASE + target.lstrip('/')


def check(manifest=None):
	"""Devuelve el manifiesto si hay version nueva; None si no la hay."""
	manifest = manifest or fetch_manifest()
	if not manifest: return None
	if not is_newer(manifest['version'], installed_version()): return None
	return manifest


# ─── descarga verificada ─────────────────────────────────────────────────────
def _work_dir():
	path = control.joinPath(control.dataPath, 'updater')
	if not control.existsPath(path): control.makeDirs(path)
	return path


def download(manifest, progress=None):
	"""Descarga y verifica. Devuelve la ruta del zip, o None. No toca el addon."""
	url = zip_url(manifest)
	expected = str(manifest['sha256']).lower().strip()
	destination = control.joinPath(_work_dir(), 'luc_kodi-%s.zip' % manifest['version'])
	if control.existsPath(destination):
		try: os.remove(destination)
		except Exception: pass
	digest = hashlib.sha256()
	written = 0
	try:
		response = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
		if response.status_code != 200:
			_log('la descarga devolvio HTTP %s' % response.status_code, LOGWARNING)
			return None
		try: total = int(response.headers.get('content-length') or 0)
		except Exception: total = 0
		with open(destination, 'wb') as handle:
			for chunk in response.iter_content(chunk_size=CHUNK):
				if not chunk: continue
				if progress is not None and progress.iscanceled():
					_log('descarga cancelada por el usuario')
					return None
				handle.write(chunk)
				digest.update(chunk)
				written += len(chunk)
				if progress is not None:
					percent = int(written * 100 / total) if total else 0
					progress.update(min(percent, 99), '%s  %.1f / %.1f MB'
							% (control.lang(40901), written / 1048576.0, (total or written) / 1048576.0))
	except requests.exceptions.RequestException as e:
		_log('fallo de red descargando (%s: %s)' % (type(e).__name__, e), LOGWARNING)
		return None
	except Exception as e:
		_log('fallo escribiendo el zip (%s: %s)' % (type(e).__name__, e), LOGWARNING)
		return None

	declared_size = manifest.get('size')
	if declared_size and int(declared_size) != written:
		_log('tamaño incorrecto: %s declarados, %s recibidos' % (declared_size, written), LOGWARNING)
		return None
	actual = digest.hexdigest()
	if actual != expected:
		# El caso tipico es una descarga cortada, pero tambien es exactamente lo
		# que se veria si alguien sirviera otro fichero desde esa URL.
		_log('sha256 no coincide (esperado %s, obtenido %s)' % (expected, actual), LOGWARNING)
		try: os.remove(destination)
		except Exception: pass
		return None
	_log('zip verificado: %s (%d bytes)' % (manifest['version'], written))
	return destination


# ─── intercambio seguro ──────────────────────────────────────────────────────
def _extract_and_validate(zip_path, version):
	"""Descomprime a un temporal y devuelve la carpeta que contiene el addon ya
	comprobado, o None. Aqui todavia no se ha tocado nada de lo instalado."""
	staging = control.joinPath(_work_dir(), 'staging')
	if os.path.isdir(staging): shutil.rmtree(staging, ignore_errors=True)
	os.makedirs(staging)
	try:
		with zipfile.ZipFile(zip_path, 'r') as archive:
			for name in archive.namelist():
				# Un zip puede traer rutas que se escapan del destino. Kodi no
				# valida esto y zipfile.extractall tampoco lo hacia siempre.
				target = os.path.normpath(os.path.join(staging, name))
				if not target.startswith(os.path.normpath(staging) + os.sep) and target != os.path.normpath(staging):
					_log('ruta sospechosa en el zip: %s' % name, LOGWARNING)
					return None
			archive.extractall(staging)
	except Exception as e:
		_log('el zip no se pudo descomprimir (%s: %s)' % (type(e).__name__, e), LOGWARNING)
		return None

	# La carpeta interna de nuestros zip oficiales lleva ID + version
	# (plugin.video.luc_kodi-1.0.76), no el ID pelado. Copiar el metodo de Fen
	# tal cual dejaria el arbol en addons/plugin.video.luc_kodi-1.0.76/, que
	# Kodi no mira. Se localiza por el addon.xml, no por el nombre.
	candidate = None
	for entry in sorted(os.listdir(staging)):
		full = os.path.join(staging, entry)
		if os.path.isdir(full) and os.path.isfile(os.path.join(full, 'addon.xml')):
			candidate = full
			break
	if not candidate:
		_log('el zip no contiene una carpeta con addon.xml', LOGWARNING)
		return None
	try:
		with open(os.path.join(candidate, 'addon.xml'), 'r', encoding='utf-8') as handle:
			head = handle.read(2000)
	except Exception:
		_log('no se pudo leer el addon.xml extraido', LOGWARNING)
		return None
	if ('id="%s"' % ADDON_ID) not in head:
		_log('el addon.xml extraido no es de %s' % ADDON_ID, LOGWARNING)
		return None
	if ('version="%s"' % version) not in head:
		_log('el addon.xml extraido no declara la version %s del manifiesto' % version, LOGWARNING)
		return None
	if not os.path.isfile(os.path.join(candidate, 'luc_kodi.py')):
		_log('falta luc_kodi.py en el arbol extraido', LOGWARNING)
		return None
	return candidate


def swap(candidate):
	"""Pone el arbol nuevo en su sitio. Devuelve True/False.

	El viejo se APARTA con rename, no se borra: mientras el nuevo no este
	colocado, deshacer es un rename de vuelta."""
	live = control.transPath(control.joinPath('special://home/addons', ADDON_ID))
	backup = live + '.old'
	if os.path.isdir(backup): shutil.rmtree(backup, ignore_errors=True)
	try:
		os.rename(live, backup)
	except Exception as e:
		_log('no se pudo apartar el arbol actual (%s: %s)' % (type(e).__name__, e), LOGWARNING)
		return False
	try:
		shutil.move(candidate, live)
	except Exception as e:
		_log('fallo colocando el arbol nuevo, se deshace (%s: %s)' % (type(e).__name__, e), LOGWARNING)
		try:
			if os.path.isdir(live): shutil.rmtree(live, ignore_errors=True)
			os.rename(backup, live)
			_log('version anterior restaurada')
		except Exception:
			# Si tambien falla el rollback hay que decirlo, no tragarselo.
			_log('NO se pudo restaurar la version anterior; queda en %s' % backup, LOGWARNING)
		return False
	shutil.rmtree(backup, ignore_errors=True)
	return True


def _reload_kodi():
	"""Que Kodi vuelva a leer el addon sin cerrarse."""
	try:
		control.execute('UpdateLocalAddons')
		control.sleep(1500)
		import xbmc
		for enabled in (False, True):
			xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled',
											'params': {'addonid': ADDON_ID, 'enabled': enabled}}))
			control.sleep(500)
	except Exception as e:
		_log('recarga de Kodi incompleta (%s: %s)' % (type(e).__name__, e), LOGWARNING)


# ─── flujo completo ──────────────────────────────────────────────────────────
def install(manifest):
	progress = control.progressDialog
	progress.create(control.addonInfo('name'), control.lang(40901))
	try:
		zip_path = download(manifest, progress)
		if not zip_path:
			progress.close()
			control.okDialog(control.addonInfo('name'), control.lang(40902))
			return False
		progress.update(99, control.lang(40903))
		candidate = _extract_and_validate(zip_path, manifest['version'])
		if not candidate:
			progress.close()
			control.okDialog(control.addonInfo('name'), control.lang(40902))
			return False
		ok = swap(candidate)
	finally:
		try: progress.close()
		except Exception: pass
	shutil.rmtree(_work_dir(), ignore_errors=True)
	if not ok:
		control.okDialog(control.addonInfo('name'), control.lang(40904))
		return False
	control.setSetting(S_SKIPPED, '')
	_reload_kodi()
	_log('actualizado a %s' % manifest['version'])
	# Un texto traducido al que le falte el %s no puede tumbar una actualizacion
	# que ya ha ido bien: el fallo llegaria DESPUES del punto de no retorno.
	done = control.lang(40905)
	try: done = done % manifest['version']
	except Exception: done = '%s (%s)' % (done, manifest['version'])
	control.okDialog(control.addonInfo('name'), done)
	return True


def prompt(manifest):
	"""Ventana de 'hay version nueva'. Devuelve True si se instalo."""
	body = '%s  [B]%s[/B]  ->  [B]%s[/B]' % (control.lang(40906), installed_version(), manifest['version'])
	choice = control.yesnocustomDialog(
		body, manifest.get('published', ''), control.lang(40907),
		heading=control.addonInfo('name'),
		customlabel=control.lang(40908), nolabel=control.lang(40909), yeslabel=control.lang(40910))
	if choice == 2:   # ver changelog
		changes = manifest.get('changelog') or control.lang(40911)
		control.dialog.textviewer('%s %s' % (control.addonInfo('name'), manifest['version']), changes)
		return prompt(manifest)
	if choice == 1:
		return install(manifest)
	if choice == 0:
		# "Ahora no" recuerda la version rechazada para no repetir el aviso en
		# cada arranque; una version posterior vuelve a preguntar.
		control.setSetting(S_SKIPPED, manifest['version'])
	return False


def run_manual():
	"""Boton 'Buscar actualizaciones' de los ajustes."""
	control.setSetting(S_LASTRUN, str(_now()))
	manifest = fetch_manifest()
	if not manifest:
		control.okDialog(control.addonInfo('name'), control.lang(40912))
		return
	if not is_newer(manifest['version'], installed_version()):
		control.okDialog(control.addonInfo('name'), '%s [B]%s[/B]' % (control.lang(40913), installed_version()))
		return
	control.setSetting(S_SKIPPED, '')   # a mano siempre se pregunta
	prompt(manifest)


def run_auto():
	"""Comprobacion silenciosa del servicio. Solo habla si hay novedad."""
	control.setSetting(S_LASTRUN, str(_now()))
	manifest = check()
	if not manifest: return
	if control.setting(S_SKIPPED) == manifest['version']:
		_log('version %s ya rechazada por el usuario' % manifest['version'])
		return
	prompt(manifest)


class UpdaterService:
	"""Mismo patron de agenda que CatalogService."""
	def run(self):
		monitor = control.monitor
		monitor.waitForAbort(30)   # que el arranque respire antes de nada
		did_startup = False
		while not monitor.abortRequested():
			try:
				if control.setting(S_ENABLED) != 'true':
					if monitor.waitForAbort(300): break
					continue
				on_start = control.setting(S_ON_START) == 'true'
				if (not did_startup and on_start) or _is_due():
					did_startup = True
					try: run_auto()
					except Exception:
						log_utils.error()
				did_startup = True
			except Exception:
				log_utils.error()
			if monitor.waitForAbort(600): break
