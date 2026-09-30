# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — log_export.py (v1.0.63)

	Escribe una copia saneada de kodi.log que se pueda compartir.

	POR QUE HACE FALTA. `client.scrub_url()` solo limpia lo que loguea ESTE
	addon. La linea que de verdad filtra credenciales la escribe KODI:

	  CCurlFile::Open - <https://<instancia>/stremio/torz/<base64>/_/strem/...

	Ese base64 decodifica a {"stores":[{"c":"pm","t":"<apikey del debrid>"}]}.
	Kodi la escribe en cuanto hay debug activo y el addon no puede evitarlo.
	Resultado: cualquier log que un usuario comparta lleva su clave dentro.

	ESTRATEGIA. La regla fuerte no es adivinar formatos, es **redactar por
	valor**: se leen los secretos que el propio addon tiene guardados y se
	tachan alli donde aparezcan, en claro o en base64. Lo que no se conozca
	cae en las reglas genericas, que son la red y no la defensa principal.
"""

import base64
import binascii
import json
import os
import re

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.jacksparrow import client

LOGINFO = log_utils.LOGINFO

# Ajustes cuyo VALOR es un secreto. Se tachan por valor exacto.
#
# v1.0.63 — CINCO de estos ids no existian. Estaban escritos como PREFIJO del
# id real ('mdblist.api' por 'mdblist.apikey', 'tmdb.api' por 'tmdb.api.key',
# 'fanart.api' por 'fanart_tv.api_key', 'omdb.api' por 'omdb.apikey',
# 'orion.api' por 'orion.api_key'), asi que control.setting() devolvia cadena
# vacia, el guard de <8 caracteres la descartaba y no se tachaba nada. La
# ironia es que esos cinco son justo los slots donde el usuario mete SU clave.
#
# Aqui hay dos capas de credenciales y solo una merece tacharse:
#
#   CAPA DEL PLUGIN — los identificadores de aplicacion (client id/secret de
#   Trakt, SIMKL, MDBList, la Api-Key de OpenSubtitles y los defaults de TMDb
#   y Fanart) viajan DENTRO del ZIP. Quien lo descomprima ya los tiene, asi
#   que ocultarlos en un log no protege nada. No entran en esta lista.
#
#   CAPA DEL USUARIO — lo que cada uno asocia con su propia cuenta: tokens de
#   debrid, la key de Gemini, usuario/clave de Easynews y OpenSubtitles, y las
#   sustituciones opcionales de TMDb/Fanart/OMDb. Esto es lo que se tacha.
#
# _check_ids() comprueba en tiempo de ejecucion que cada id de aqui existe de
# verdad en settings.xml, para que este desfase no vuelva a pasar en silencio.
SECRET_SETTINGS = (
	# Debrid y cuentas premium
	'premiumize.token', 'realdebrid.token', 'realdebrid.secret', 'realdebrid.client_id',
	'realdebrid.refresh', 'alldebrid.token', 'torbox.token',
	'easynews.username', 'easynews.password',
	# Proveedores Custom (blobs de configuracion)
	'torz.config', 'comet.config', 'sootio.config', 'meteor.config_token',
	'mediafusion.secret', 'aiostreams.uuid', 'aiostreams.password', 'aiostreams.custom_url',
	# Scrobblers y listas
	'trakt.token', 'trakt.refresh', 'simkl.token', 'simkl.refresh', 'mdblist.token', 'mdblist.apikey',
	# Claves que pone el usuario
	'gemini.api.key', 'gemini.api.key2', 'gemini.api.key3',
	'newznab.apikey', 'orion.api_key', 'tidb.api.key',
	'tmdb.api.key', 'fanart_tv.api_key', 'omdb.apikey',
	# Subtitulos
	'opensubspassword', 'opensubstoken',
)


def _check_ids():
	"""Resuelve cada id de SECRET_SETTINGS contra settings.xml y devuelve los
	que no existen. Un id mal escrito no lanza excepcion: devuelve vacio y
	simula que no hay secreto, que es la peor forma de fallar que hay."""
	try:
		path = os.path.join(control.addonPath('plugin.video.luc_kodi'),
		                    'resources', 'settings.xml')
		with open(path, 'r', encoding='utf-8', errors='ignore') as f:
			blob = f.read()
	except Exception:
		return []
	declared = set(re.findall(r'<setting[^>]*\bid="([^"]+)"', blob))
	if not declared:
		return []
	return [s for s in SECRET_SETTINGS if s not in declared]

# Claves que, dentro de un JSON en base64, marcan el objeto como credencial.
CRED_KEYS = ('t', 'token', 'apikey', 'api_key', 'password', 'secret', 'key')

GENERIC = (
	# UUID en cualquier posicion
	(re.compile(r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'), '<UUID>'),
	# v1.0.88: tokens de SIMKL AUTH V2. Llevan prefijo fijo precisamente para
	# que un escaner los reconozca; aqui se tapan vengan de donde vengan.
	(re.compile(r'\bsimkl_(?:at|rt)_[A-Za-z0-9_\-]{8,}'), '<SIMKL_TOKEN>'),
	# Autorizacion Basic/Bearer. v1.0.63: antes exigia DOS PUNTOS, y Easynews no
	# la manda como cabecera: la pega al final de la URL con un signo igual,
	#   https://...|Authorization=Basic dXNlcjpwYXNz
	# que es como Kodi la escribe con CCurlFile. Ahora vale ':' o '=', y el
	# separador puede venir como espacio o como %20.
	(re.compile(r'(?i)(authorization\s*[:=]\s*(?:basic|bearer)(?:\s|%20)+)[^\s&|<>"\']+'),
	 r'\1<REDACTED>'),
	# Credenciales en el userinfo de la URL (https://usuario:clave@host/...)
	(re.compile(r'(?i)(https?://)[^/\s:@]+:[^/\s@]+@'), r'\1<REDACTED>@'),
	# Parametros de query con pinta de credencial. v1.0.63: se anade 'key' a
	# secas, que es como Gemini pasa la suya (?key=AIza...). El patron cubria
	# api_key y apikey, no key, asi que la unica clave que Google revoca en
	# minutos era la unica que salia entera en el log.
	(re.compile(r'(?i)([?&](?:api_?key|apikey|access_token|refresh_token|token|password|passwd|secret|client_secret|auth|key)=)[^&\s<>"\']+'),
	 r'\1<REDACTED>'),
)

# base64 suelto de al menos 16 chars, que es donde viven los blobs de config.
B64 = re.compile(r'[A-Za-z0-9+/]{16,}={0,2}')


def _looks_credential(blob):
	"""True si el base64 decodifica a JSON con una clave de credencial."""
	try:
		pad = blob + '=' * (-len(blob) % 4)
		raw = base64.b64decode(pad, validate=True)
	except (binascii.Error, ValueError):
		return False
	try:
		obj = json.loads(raw.decode('utf-8', 'strict'))
	except Exception:
		return False

	def walk(node):
		if isinstance(node, dict):
			for k, v in node.items():
				if str(k).lower() in CRED_KEYS and isinstance(v, str) and v:
					return True
				if walk(v):
					return True
		elif isinstance(node, list):
			for v in node:
				if walk(v):
					return True
		return False

	return walk(obj)


def _secrets():
	"""Valores reales a tachar, mas su forma en base64."""
	out = set()
	for sid in SECRET_SETTINGS:
		try:
			val = (control.setting(sid) or '').strip()
		except Exception:
			continue
		# Los muy cortos causarian falsos positivos por todo el log.
		if len(val) < 8:
			continue
		out.add(val)
		try:
			out.add(base64.b64encode(val.encode()).decode())
		except Exception:
			pass
	return sorted(out, key=len, reverse=True)


def _sanitize_line(line, secrets):
	# v1.0.63 — el orden importa y estaba al reves. Tachando primero POR VALOR,
	# un blob que contiene DOS secretos juntos se parte: en el Basic de Easynews,
	# base64('usuario:clave'), solo se reconocia el trozo del usuario y quedaba
	# 'Basic <REDACTED>OlBhc3N3b3Jk...', que es la CLAVE en base64, entera. Y la
	# regla de Authorization ya no podia rematarlo porque el '<' recien insertado
	# corta su patron. Primero las genericas, que tratan el blob como una unidad,
	# y despues el tachado por valor sobre lo que quede.
	for pattern, repl in GENERIC:
		line = pattern.sub(repl, line)
	for sec in secrets:
		if sec in line:
			line = line.replace(sec, '<REDACTED>')
	# base64 que decodifica a algo con pinta de credencial
	def _b64(m):
		blob = m.group(0)
		return '<REDACTED_CONFIG>' if _looks_credential(blob) else blob
	line = B64.sub(_b64, line)
	# Y por ultimo las reglas del addon sobre cualquier URL que quede.
	for url in re.findall(r'https?://[^\s<>"\']+', line):
		try:
			line = line.replace(url, client.scrub_url(url))
		except Exception:
			pass
	return line


def run():
	try:
		# v1.0.71: antes solo se saneaba kodi.log. Pero la actividad de los
		# scrapers va, POR DEFECTO, a jacksparrowscrapers.log — o sea que el
		# boton hecho para poder compartir logs sin filtrar credenciales
		# ignoraba justo el fichero que hace falta para diagnosticar.
		# v1.0.63: si algun id de SECRET_SETTINGS ha dejado de existir (renombrado
		# en settings.xml, por ejemplo), se avisa en el log en vez de fallar en
		# silencio dando por saneado lo que no lo esta.
		bad = _check_ids()
		if bad:
			control.log('[ luc_kodi ] log_export: AVISO, ids inexistentes en '
			            'SECRET_SETTINGS: %s' % ', '.join(bad), LOGINFO)
		secrets = _secrets()
		done, missing = [], []
		for fname in ('kodi.log', 'jacksparrowscrapers.log'):
			log_path = control.transPath('special://logpath/%s' % fname)
			if not os.path.exists(log_path):
				missing.append(fname)
				continue
			out_path = control.transPath(
				'special://logpath/%s-sanitized.log' % fname.replace('.log', ''))
			hits, total = 0, 0
			with open(log_path, 'r', encoding='utf-8', errors='replace') as src, \
			     open(out_path, 'w', encoding='utf-8') as dst:
				for line in src:
					total += 1
					clean = _sanitize_line(line, secrets)
					if clean != line:
						hits += 1
					dst.write(clean)
			control.log('[ luc_kodi ] log_export: %s -> %s/%s lineas saneadas'
			            % (fname, hits, total), LOGINFO)
			done.append((out_path, hits, total))

		if not done:
			control.okDialog(message='No log files were found to sanitize.')
			return
		body = '[COLOR ff00fa9a]Written.[/COLOR]\n\n'
		for out_path, hits, total in done:
			body += '%s\n%d of %d lines had something redacted.\n\n' % (out_path, hits, total)
		if missing:
			body += '[COLOR ff888888]Not present: %s[/COLOR]\n\n' % ', '.join(missing)
		body += ('Check them before sharing: this removes what it recognises, '
		         'not everything that could ever identify you.')
		control.okDialog('Sanitized log', body)
	except Exception:
		log_utils.error()
		control.okDialog(message='The sanitized log could not be written. See the log for details.')
