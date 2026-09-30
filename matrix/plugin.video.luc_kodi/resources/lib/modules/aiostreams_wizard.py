# -*- coding: utf-8 -*-
"""
	plugin.video.luc_kodi — AIOStreams Setup Wizard (v1.0.91)

	Mismo patron que los asistentes de Torz/Comet/Sootio/Meteor: dos metodos
	de entrada para sortear el teclado interno de Kodi, que en Android TV no
	tiene boton de pegar.

		Metodo A) SERVIDOR LOCAL (recomendado)
		Mini HTTP server en el propio Kodi. Desde el navegador de otro aparato
		se elige la instancia y se pega la direccion / el manifest, el UUID y
		el password. Se valida contra la instancia ANTES de guardar.

		Metodo B) TECLADO DE KODI (reserva)

	Por que ahora si (el 19-ago-2026 se decidio no hacerlo): con la opcion
	'Custom URL' de esta misma version el usuario de una instancia de pago pega un
	manifest de ~150 caracteres, con el encryptedPassword dentro. Con mando es
	inviable.

	DEBRID DETECTED — corrige el hallazgo F7 de la auditoria, que lo daba por
	imposible. GET /api/v1/user con Basic uuid:password (la llamada que el
	scraper ya hace) devuelve, ademas del encryptedPassword, la configuracion
	del usuario en data.userData, y dentro la lista `services`
	({id, enabled, credentials}). De ahi salen los nombres de los debrid. Las
	credenciales de esos servicios se miran solo para saber si estan
	rellenas: nunca se guardan, se loguean ni se devuelven.
	Con SOLO el manifest no se puede: el password va cifrado y ese endpoint
	rechaza el cifrado (allowEncrypted: false en el servidor).

	Nada de este modulo escribe credenciales en el log.
"""

import json
import base64
import socket
import threading
from resources.lib.jacksparrow import control
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow.control import setSetting

from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote


_LISTEN_PORT  = 48290   # fuera de 48219-48279 (Sootio, Meteor, MDBList, Torz, Newznab, Comet, Badges)
_HTTP_TIMEOUT = 300     # segundos que el servidor espera al usuario
_NET_TIMEOUT  = 20

_TITLE = 'AIOStreams Setup'

# Nombres legibles de los ids de servicio de AIOStreams
# (packages/core/src/utils/constants.ts, SERVICES).
_SERVICE_NAMES = {
	'realdebrid': 'Real-Debrid', 'premiumize': 'Premiumize', 'alldebrid': 'AllDebrid',
	'torbox': 'TorBox', 'debridlink': 'Debrid-Link', 'easydebrid': 'EasyDebrid',
	'debrider': 'Debrider', 'putio': 'put.io', 'pikpak': 'PikPak', 'offcloud': 'OffCloud',
	'seedr': 'Seedr', 'easynews': 'Easynews', 'nzbdav': 'NzbDAV', 'altmount': 'AltMount',
	'stremio_nntp': 'Stremio NNTP', 'stremthru_newz': 'StremThru Newz', 'torrin': 'Torrin',
}

LABEL_NOT_CONFIGURED = 'not configured'
LABEL_MANIFEST_ONLY  = 'unknown (manifest URL only - add UUID and password to see it)'
LABEL_NONE           = 'none in your AIOStreams config'
LABEL_API_LOCKED     = 'unknown (this instance does not let apps read the account)'


# -----------------------------------------------------------------------------
# Instancias (reutiliza la tabla y el normalizador del scraper)
# -----------------------------------------------------------------------------

def _aio():
	from resources.lib.jacksparrow.sourcesdir.torrents import aiostreams
	return aiostreams


def _instance_choices():
	"""[(indice_enum, etiqueta)] en el mismo orden que el enum de settings.xml."""
	aio = _aio()
	out = [(k, aio._INSTANCES[k]) for k in sorted(aio._INSTANCES, key=int)]
	out.append((aio._CUSTOM_IDX, 'Custom URL (your own instance, e.g. paid ElfHosted)'))
	return out


def _resolve_target(idx, custom_url):
	"""Devuelve (base, prefix) para el indice y la URL dados."""
	aio = _aio()
	if idx == aio._CUSTOM_IDX:
		base, prefix, _q = aio._parse_instance_url(custom_url)
		return base, prefix
	return aio._INSTANCES.get(idx, aio._INSTANCES['0']), None


def _uuid_from_prefix(prefix):
	"""UUID contenido en un prefix /stremio/<uuid>/<encPwd> (no en un alias)."""
	try:
		rest = prefix.split('/stremio/', 1)[1].split('/')
		if rest[0].lower() != 'u' and len(rest[0]) >= 32:
			return rest[0]
	except Exception:
		pass
	return ''


# -----------------------------------------------------------------------------
# Red — urllib directo para leer codigo y cuerpo tambien en los errores
# (client.request devuelve None o una tupla segun el codigo, y aqui hace falta
# distinguir "password incorrecto" de "instancia caida").
# -----------------------------------------------------------------------------

def _http_get(url, headers=None):
	h = {'User-Agent': 'Mozilla/5.0 (Kodi; luc_kodi)', 'Accept': 'application/json'}
	h.update(headers or {})
	try:
		resp = urlopen(Request(url, headers=h), timeout=_NET_TIMEOUT)
		return resp.getcode(), resp.read().decode('utf-8', 'replace')
	except HTTPError as e:
		try:
			body = e.read().decode('utf-8', 'replace')
		except Exception:
			body = ''
		return e.code, body
	except Exception:
		return None, ''


def _json(body):
	try:
		return json.loads(body)
	except Exception:
		return None


def detect_services(user_data):
	"""Nombres de los servicios activos y con alguna credencial rellena."""
	names = []
	try:
		for svc in (user_data or {}).get('services') or []:
			if not isinstance(svc, dict) or svc.get('enabled') is False:
				continue
			creds = svc.get('credentials') or {}
			if not any(str(v).strip() for v in creds.values()):
				continue
			sid = str(svc.get('id') or '')
			name = _SERVICE_NAMES.get(sid, sid)
			if name and name not in names:
				names.append(name)
	except Exception:
		pass
	return names


def _host(base):
	try:
		return base.split('://', 1)[1].split('/', 1)[0]
	except Exception:
		return base or ''


def _error_text(data):
	"""Mensaje de error de una respuesta AIOStreams, tolerando otras formas
	(error como cadena, o un cuerpo que no es de AIOStreams)."""
	if not isinstance(data, dict):
		return ''
	err = data.get('error')
	if isinstance(err, dict):
		err = err.get('message') or err.get('code') or ''
	return str(err or data.get('detail') or data.get('message') or '')


def _fetch_user(base, uuid, password):
	"""
	GET /api/v1/user. Devuelve (ok, enc_pwd, user_data, error_text, locked).
	Basic primero (v2.30+) y la forma antigua por query solo si la instancia
	no parece entender la nueva — nunca tras un 'password incorrecto'.

	v1.0.92 — locked=True: la instancia pide OTRO login delante de su API. AIOStreams
	no responde 401 en /api/v1/user (un password malo es un 400 con
	"Invalid UUID or password"); un 401/403 sin ese mensaje viene de una capa
	de acceso delante de la instancia — lo visto el 23-sep con una ElfHosted
	de pago (issue #3). Esa capa se queda la cabecera Authorization, asi que
	UUID y password no llegan nunca a AIOStreams. El manifest si es publico:
	es lo que usa Stremio.
	"""
	auth = base64.b64encode(('%s:%s' % (uuid, password)).encode('utf-8')).decode('ascii')
	code, body = _http_get('%s/api/v1/user' % base, {'Authorization': 'Basic %s' % auth})
	data = _json(body) or {}
	if code == 200 and isinstance(data, dict) and data.get('success'):
		d = data.get('data') or {}
		return True, d.get('encryptedPassword') or '', d.get('userData') or {}, '', False
	err = _error_text(data)
	if code is None:
		return False, '', {}, '%s did not answer. Check the address and your connection.' % _host(base), False
	if code in (401, 403) and 'invalid uuid' not in err.lower():
		return False, '', {}, ('%s asks for its own login before its account API (HTTP %s), so the UUID '
								'and password cannot be checked there. Paste the manifest URL from the '
								'Save & Install page of /stremio/configure instead: it works without that login.'
								% (_host(base), code)), True
	if code in (400, 401, 403) and 'invalid' in err.lower():
		# v1.0.91: se nombra el host. En la prueba del 23-sep el formulario
		# se quedo en la primera instancia y el UUID era de stremio.ru; con
		# el host en el mensaje se ve al momento que se pregunto al sitio
		# equivocado.
		return False, '', {}, ('%s rejected that UUID or password. Make sure this is the instance '
								'where you created your configuration.' % _host(base)), False
	# Instancias < v2.30
	code2, body2 = _http_get('%s/api/v1/user?uuid=%s&password=%s'
								% (base, quote(uuid, safe=''), quote(password, safe='')))
	data2 = _json(body2) or {}
	if code2 == 200 and isinstance(data2, dict) and data2.get('success'):
		d = data2.get('data') or {}
		return True, d.get('encryptedPassword') or '', d.get('userData') or {}, '', False
	return False, '', {}, 'The instance answered HTTP %s%s.' % (code, (': ' + err) if err else ''), False


WARN_NO_STREAMS = ('Your AIOStreams configuration does not offer streams yet (its manifest lists no '
					'"stream" resource), so it will return no sources. Open /stremio/configure on your '
					'instance, add at least one addon, save, and run Re-detect.')


def _has_stream_resource(manifest):
	"""
	v1.0.91: AIOStreams arma `resources` con los addons que consigue cargar
	(skipFailedAddons). Una configuracion sin addons, o con todos caidos,
	sale con resources: [] y no devuelve ni un stream aunque la cuenta sea
	valida — es lo que se vio en la prueba del 23-sep.
	"""
	for r in (manifest or {}).get('resources') or []:
		if r == 'stream' or (isinstance(r, dict) and r.get('name') == 'stream'):
			return True
	return False


def _check_manifest(prefix, query=''):
	"""(ok, error, warning): ok si responde y no pide configuracion; aviso si
	no ofrece streams."""
	url = '%s/manifest.json%s' % (prefix, ('?' + query) if query else '')
	code, body = _http_get(url)
	data = _json(body)
	if not isinstance(data, dict):
		data = {}
	if code == 200 and data.get('id') and not (data.get('behaviorHints') or {}).get('configurationRequired'):
		return True, '', ('' if _has_stream_resource(data) else WARN_NO_STREAMS)
	if code is None:
		return False, 'The instance did not answer. Check the address and your connection.', ''
	if code in (401, 403):
		return False, ('The instance asks for a login even for the manifest (HTTP %s), so no app can '
						'reach it. Check the address, or ask your host to leave /stremio open.' % code), ''
	return False, 'That manifest URL was not accepted by the instance (HTTP %s).' % code, ''


def validate(idx, custom_url, uuid, password):
	"""
	Comprueba la cuenta contra la instancia. Devuelve un dict:
		ok, error, base, prefix, uuid, enc_pwd, detected
	No toca ningun ajuste.
	"""
	aio = _aio()
	res = {'ok': False, 'error': '', 'base': '', 'prefix': None,
			'uuid': uuid or '', 'enc_pwd': '', 'detected': LABEL_NOT_CONFIGURED, 'warning': ''}
	if idx == aio._CUSTOM_IDX and not (custom_url or '').strip():
		res['error'] = 'Custom URL was chosen but no address was entered.'
		return res
	base, prefix = _resolve_target(idx, custom_url)
	if not base:
		res['error'] = 'That address could not be read.'
		return res
	res['base'], res['prefix'] = base, prefix
	if prefix and not res['uuid']:
		res['uuid'] = _uuid_from_prefix(prefix)

	if res['uuid'] and password:
		ok, enc, user_data, err, locked = _fetch_user(base, res['uuid'], password)
		if not ok and locked and prefix:
			# Instancia con login delante de su API pero con el manifest a
			# mano: se enlaza por el manifest y se dice por que no hay debrid.
			query = aio._parse_instance_url(custom_url)[2]
			ok2, err2, res['warning'] = _check_manifest(prefix, query)
			if not ok2:
				res['error'] = err2
				return res
			res['detected'] = LABEL_API_LOCKED
			res['ok'] = True
			return res
		if not ok:
			res['error'] = err
			return res
		res['enc_pwd'] = enc
		names = detect_services(user_data)
		res['detected'] = ', '.join(names) if names else LABEL_NONE
		res['ok'] = True
		if enc:
			_ok, _e, res['warning'] = _check_manifest('%s/stremio/%s/%s' % (base, res['uuid'], enc))
		return res

	if prefix:
		query = aio._parse_instance_url(custom_url)[2]
		ok, err, res['warning'] = _check_manifest(prefix, query)
		if not ok:
			res['error'] = err
			return res
		res['detected'] = LABEL_MANIFEST_ONLY
		res['ok'] = True
		return res

	res['error'] = 'Enter your UUID and password, or paste the manifest URL of your instance.'
	return res


# -----------------------------------------------------------------------------
# Guardado
# -----------------------------------------------------------------------------

def _clear_settings_cache():
	try:
		control.homeWindow.clearProperty('luc_kodi_settings')
	except Exception:
		pass


def _save(idx, custom_url, password, res):
	"""Escribe ajustes, activa el proveedor y renueva la cache del encryptedPassword."""
	try:
		aio = _aio()
		setSetting('aiostreams.url', idx)
		if idx == aio._CUSTOM_IDX:
			setSetting('aiostreams.custom_url', (custom_url or '').strip())
		if res.get('uuid'):
			setSetting('aiostreams.uuid', res['uuid'])
		if password:
			setSetting('aiostreams.password', password)
		setSetting('aiostreams.debrid.detected', res.get('detected') or LABEL_NOT_CONFIGURED)
		setSetting('provider.aiostreams', 'true')
		_clear_settings_cache()
		# El encryptedPassword viejo quedaria cacheado toda la sesion si el
		# password cambio con el mismo UUID: se sustituye por el recien obtenido.
		try:
			key = aio.enc_cache_key(res.get('base'), res.get('uuid'))
			if res.get('enc_pwd'):
				control.homeWindow.setProperty(key, res['enc_pwd'])
			else:
				control.homeWindow.clearProperty(key)
		except Exception:
			pass
		return True
	except Exception:
		return False


# -----------------------------------------------------------------------------
# Metodo A: servidor local
# -----------------------------------------------------------------------------

def _esc(s):
	return (str(s or '').replace('&', '&amp;').replace('<', '&lt;')
			.replace('>', '&gt;').replace('"', '&quot;'))


_HTML_HEAD = u"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIOStreams Setup</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; background:#141414; color:#eee; margin:0; padding:24px; }
h1 { color:#00fa9a; margin:0 0 8px 0; font-size:22px; }
p { color:#aaa; line-height:1.5; margin:8px 0; }
code { color:#fdb515; }
label { display:block; margin:16px 0 6px 0; color:#ddd; font-weight:bold; }
select, input, textarea { width:100%; box-sizing:border-box; background:#1e1e1e; color:#fff; border:1px solid #333; border-radius:8px; padding:12px; font-size:14px; }
textarea { min-height:90px; font-family:monospace; font-size:13px; word-break:break-all; }
button { background:#00fa9a; color:#000; border:0; border-radius:8px; padding:14px 28px; font-size:16px; font-weight:bold; margin-top:20px; cursor:pointer; width:100%; }
.hint { color:#777; font-size:12px; margin-top:4px; }
.err { background:#3a1414; color:#ff8a8a; border-radius:8px; padding:12px; margin-top:12px; }
.ok { color:#00fa9a; text-align:center; padding-top:40px; }
</style></head><body>
"""

_HTML_FORM = u"""<h1>AIOStreams &mdash; link your account</h1>
<p>Choose your instance, then enter your <b>UUID</b> and <b>password</b> from its <code>/stremio/configure</code> page.
With your own instance (for example a paid ElfHosted one) choose <b>Custom URL</b> and enter its address,
or paste the <b>manifest URL</b> it gives you after saving: that one already carries your account.</p>
%(error)s
<form method="post" action="/">
<label>Instance</label>
<select name="instance">%(options)s</select>
<label>Address or manifest URL</label>
<textarea name="url" id="url" placeholder="https://your-username-aiostreams.elfhosted.com">%(url)s</textarea>
<div class="hint">Tip: on mobile, long-press inside the box and choose Paste. Whatever you paste here decides the instance. Leave it empty to keep the saved one.</div>
<label>UUID</label>
<input name="uuid" value="%(uuid)s" autocomplete="off" placeholder="not needed with a manifest URL">
<label>Password</label>
<input name="password" type="password" autocomplete="off" placeholder="leave empty to keep the saved one">
<button type="submit">Check and save to Kodi</button>
</form>
<script>
(function () {
var ta = document.getElementById('url'), sel = document.getElementsByName('instance')[0];
var pub = %(publics)s;
function sync() {
var v = (ta.value || '').trim().replace(/[?#].*$/, '').replace(/\\/+$/, '').toLowerCase();
if (!v) return;
if (v.indexOf('://') < 0) v = 'https://' + v;
for (var k in pub) { if (v === pub[k] || v === pub[k] + '/stremio/configure') { sel.value = k; return; } }
sel.value = '%(custom)s';
}
ta.addEventListener('input', sync); ta.addEventListener('change', sync);
})();
</script>
</body></html>
"""

_HTML_OK = u"""<div class="ok"><h1>&check; Saved</h1>
<p>Debrid detected: <b style="color:#fdb515">%s</b></p>%s
<p>You can close this page and go back to Kodi.</p></div>
</body></html>
"""


def _options_html(selected):
	out = []
	for idx, label in _instance_choices():
		out.append('<option value="%s"%s>%s</option>'
					% (idx, ' selected' if idx == selected else '', _esc(label)))
	return ''.join(out)


def _form_page(selected, url='', uuid='', error=''):
	err = ('<div class="err">%s</div>' % _esc(error)) if error else ''
	aio = _aio()
	publics = json.dumps(dict((k, v.lower()) for k, v in aio._INSTANCES.items()))
	return _HTML_HEAD + _HTML_FORM % {'options': _options_html(selected), 'url': _esc(url),
										'uuid': _esc(uuid), 'error': err,
										'publics': publics, 'custom': aio._CUSTOM_IDX}


def _field(form, name):
	try:
		return (form.get(name) or [''])[0].strip()
	except Exception:
		return ''


def _idx_for_url(url):
	"""
	v1.0.91: lo que se pega en el campo de direccion decide la instancia.
	En la prueba del 23-sep se pego un manifest de stremio.ru con el
	desplegable aun en la primera instancia: el campo se ignoraba ("Custom
	URL only") y la cuenta se comprobaba contra otro servidor. Ahora una
	direccion publica sin cuenta dentro selecciona esa instancia, y
	cualquier otra cosa (manifest, alias, host propio) pasa a Custom URL.
	"""
	aio = _aio()
	base, prefix, _q = aio._parse_instance_url(url)
	if base and not prefix:
		for k, v in aio._INSTANCES.items():
			if base.rstrip('/').lower() == v.lower():
				return k
	return aio._CUSTOM_IDX


def handle_submission(form):
	"""
	Procesa un envio del formulario (dict de parse_qs). Los campos vacios
	conservan lo guardado. Devuelve (res, idx, url, password).
	"""
	idx      = _field(form, 'instance') or (getSetting('aiostreams.url') or '0')
	url      = _field(form, 'url') or (getSetting('aiostreams.custom_url') or '')
	uuid     = _field(form, 'uuid') or (getSetting('aiostreams.uuid') or '')
	password = _field(form, 'password') or (getSetting('aiostreams.password') or '')
	aio = _aio()
	if idx not in aio._INSTANCES and idx != aio._CUSTOM_IDX:
		idx = '0'
	if _field(form, 'url'):
		idx = _idx_for_url(url)
	# Un manifest pegado manda sobre el UUID guardado de otra cuenta.
	if idx == aio._CUSTOM_IDX:
		_b, prefix = _resolve_target(idx, url)
		from_url = _uuid_from_prefix(prefix) if prefix else ''
		if from_url and from_url != uuid:
			uuid = from_url
			if not _field(form, 'password'):
				password = ''
	return validate(idx, url, uuid, password), idx, url, password


class _WizardServer(object):
	def __init__(self, port):
		self.port = port
		self.result = None   # (res, idx, url, password)
		self.sock = None
		self._stop = False
		self._thread = None

	def start(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.bind(('', self.port))
		self.sock.listen(2)
		self.sock.settimeout(1.0)
		self._thread = threading.Thread(target=self._serve_loop)
		self._thread.daemon = True
		self._thread.start()

	def stop(self):
		self._stop = True
		try:
			self.sock.close()
		except Exception:
			pass

	def is_alive(self):
		return self._thread is not None and self._thread.is_alive()

	def _serve_loop(self):
		import time
		t0 = time.time()
		while not self._stop:
			if time.time() - t0 > _HTTP_TIMEOUT:
				return
			try:
				conn, _addr = self.sock.accept()
			except socket.timeout:
				continue
			except Exception:
				return
			try:
				self._handle(conn)
			except Exception:
				pass
			finally:
				try:
					conn.close()
				except Exception:
					pass
			if self.result is not None:
				return

	def _handle(self, conn):
		conn.settimeout(5.0)
		data = b''
		while b'\r\n\r\n' not in data and len(data) < 65536:
			chunk = conn.recv(4096)
			if not chunk:
				break
			data += chunk
		if not data:
			return
		head, _, body = data.partition(b'\r\n\r\n')
		headline = head.split(b'\r\n', 1)[0]
		if headline.startswith(b'POST'):
			clen = 0
			for line in head.split(b'\r\n')[1:]:
				if line.lower().startswith(b'content-length:'):
					try:
						clen = int(line.split(b':', 1)[1].strip())
					except Exception:
						clen = 0
			while len(body) < clen and len(body) < 1048576:
				chunk = conn.recv(min(65536, clen - len(body)))
				if not chunk:
					break
				body += chunk
			form = parse_qs(body.decode('utf-8', 'replace'), keep_blank_values=True)
			res, idx, url, password = handle_submission(form)
			if not res['ok']:
				self._send(conn, 200, 'OK', _form_page(idx, _field(form, 'url'),
														_field(form, 'uuid'), res['error']))
				return
			self.result = (res, idx, url, password)
			self._send(conn, 200, 'OK', _HTML_HEAD + _HTML_OK % (
				_esc(res['detected']),
				('<div class="err" style="text-align:left">%s</div>' % _esc(res['warning'])) if res.get('warning') else ''))
			return
		self._send(conn, 200, 'OK', _form_page(getSetting('aiostreams.url') or '0',
												getSetting('aiostreams.custom_url') or ''))

	@staticmethod
	def _send(conn, status, reason, body):
		body_b = body.encode('utf-8')
		resp = ('HTTP/1.1 %d %s\r\n'
				'Content-Type: text/html; charset=utf-8\r\n'
				'Content-Length: %d\r\n'
				'Cache-Control: no-store\r\n'
				'Connection: close\r\n\r\n') % (status, reason, len(body_b))
		try:
			conn.sendall(resp.encode('utf-8') + body_b)
		except Exception:
			pass


def _get_local_ip():
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.settimeout(1.0)
		s.connect(('8.8.8.8', 53))
		ip = s.getsockname()[0]
		s.close()
		return ip
	except Exception:
		return '127.0.0.1'


def _find_free_port():
	for port in range(_LISTEN_PORT, _LISTEN_PORT + 20):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			s.bind(('', port))
			s.close()
			return port
		except Exception:
			continue
	return None


def _copy2clip_safe(text):
	try:
		from resources.lib.modules.source_utils import copy2clip
		copy2clip(text)
	except Exception:
		pass


def _done_dialog(res):
	control.dialog.ok(
		_TITLE + ' — done',
		'[COLOR ff00fa9a]AIOStreams is linked and enabled.[/COLOR]\n\n'
		'Debrid detected: [COLOR fffdb515]%s[/COLOR]%s' % (
			res.get('detected'),
			('\n\n[COLOR ffff6666]%s[/COLOR]' % res['warning']) if res.get('warning') else ''),
	)


def _method_local_server():
	import time
	import xbmcgui
	port = _find_free_port()
	srv = _WizardServer(port) if port else None
	try:
		if not srv:
			raise RuntimeError('no free port')
		srv.start()
	except Exception as e:
		control.dialog.ok(_TITLE + ' — error',
							'Could not start the local setup server (%s).\n'
							'Try the Kodi keyboard method instead.' % str(e))
		return False

	url = 'http://%s:%d' % (_get_local_ip(), port)
	_copy2clip_safe(url)
	control.dialog.ok(
		_TITLE + ' — open this URL',
		'On the same Wi-Fi, open in a browser:\n\n'
		'[COLOR fffdb515]%s[/COLOR]\n\n'
		'Fill in the form and press [B]Check and save[/B]. The account is '
		'checked against your instance before anything is saved. Then press OK '
		'here and wait.\n\n(Server open for %d min.)' % (url, _HTTP_TIMEOUT // 60),
	)
	pd = xbmcgui.DialogProgressBG()
	pd.create(_TITLE, 'Waiting for the browser...')
	t0 = time.time()
	while srv.is_alive() and srv.result is None:
		remaining = _HTTP_TIMEOUT - int(time.time() - t0)
		if remaining <= 0:
			break
		pd.update(min(int((_HTTP_TIMEOUT - remaining) * 100 / _HTTP_TIMEOUT), 99),
					_TITLE, 'Waiting... (%ds remaining)' % remaining)
		time.sleep(0.5)
	pd.close()
	srv.stop()

	if srv.result is None:
		control.dialog.ok(_TITLE + ' — cancelled',
							'Nothing was received (timeout).\n'
							'You can try again or use the Kodi keyboard method.')
		return False
	res, idx, curl, password = srv.result
	if not _save(idx, curl, password, res):
		control.dialog.ok(_TITLE + ' — error', 'Could not write settings.')
		return False
	_done_dialog(res)
	return True


# -----------------------------------------------------------------------------
# Metodo B: teclado de Kodi
# -----------------------------------------------------------------------------

def _method_keyboard():
	aio = _aio()
	choices = _instance_choices()
	cur = getSetting('aiostreams.url') or '0'
	pre = [i for i, (k, _l) in enumerate(choices) if k == cur]
	sel = control.dialog.select(_TITLE + ' — instance', [l for _k, l in choices],
								preselect=pre[0] if pre else 0)
	if sel == -1:
		return False
	idx = choices[sel][0]
	curl = ''
	if idx == aio._CUSTOM_IDX:
		curl = control.dialog.input(heading='Instance address or manifest URL',
									defaultt=getSetting('aiostreams.custom_url') or '', type=0)
		if not curl:
			return False
	prefix = _resolve_target(idx, curl)[1]
	uuid = _uuid_from_prefix(prefix) if prefix else ''
	password = ''
	if not prefix:
		uuid = control.dialog.input(heading='UUID (from /stremio/configure)',
									defaultt=getSetting('aiostreams.uuid') or '', type=0)
		if not uuid:
			return False
		password = control.dialog.input(heading='Password (empty = keep the saved one)',
										type=0, option=2)
		password = password or (getSetting('aiostreams.password') or '')
	elif uuid and uuid == (getSetting('aiostreams.uuid') or ''):
		# Mismo usuario: se aprovecha el password guardado para detectar el debrid.
		password = getSetting('aiostreams.password') or ''

	res = validate(idx, curl, uuid, password)
	if not res['ok']:
		control.dialog.ok(_TITLE + ' — failed', res['error'])
		return False
	if not _save(idx, curl, password, res):
		control.dialog.ok(_TITLE + ' — error', 'Could not write settings.')
		return False
	_done_dialog(res)
	return True


# -----------------------------------------------------------------------------
# Entradas
# -----------------------------------------------------------------------------

def run():
	intro = ('AIOStreams gathers many sources behind one address and plays them '
				'through the debrid services saved in your AIOStreams account, so '
				'there is no separate debrid login here.\n\n'
				'Works with the public instances and with your own, such as a paid '
				'ElfHosted one ([COLOR fffdb515]https://your-username-aiostreams.elfhosted.com[/COLOR]).')
	if not control.dialog.yesno(_TITLE + ' (1/2)', intro, nolabel='Cancel', yeslabel='Continue'):
		return
	choice = control.dialog.select(_TITLE + ' (2/2) — input method', [
		'[COLOR ff00fa9a]Use a browser on another device[/COLOR]  (no keyboard)',
		'Type here with the Kodi keyboard',
	])
	if choice == 0:
		_method_local_server()
	elif choice == 1:
		_method_keyboard()


def detect():
	"""Vuelve a leer los debrid de la cuenta guardada, sin repetir el asistente."""
	idx = getSetting('aiostreams.url') or '0'
	res = validate(idx, getSetting('aiostreams.custom_url') or '',
					getSetting('aiostreams.uuid') or '', getSetting('aiostreams.password') or '')
	if not res['ok']:
		control.dialog.ok('AIOStreams — re-detect', res['error'])
		return
	setSetting('aiostreams.debrid.detected', res['detected'])
	_clear_settings_cache()
	control.dialog.ok('AIOStreams — re-detect',
						'[COLOR ff00fa9a]Done.[/COLOR]\n\n'
						'Debrid detected: [COLOR fffdb515]%s[/COLOR]%s' % (
							res['detected'],
							('\n\n[COLOR ffff6666]%s[/COLOR]' % res['warning']) if res.get('warning') else ''))
