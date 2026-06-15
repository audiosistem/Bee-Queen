# -*- coding: utf-8 -*-
"""
	plugin.video.luc_kodi — Sootio Setup Wizard

	Flujo guiado para configurar Sootio sin teclear nada largo a mano.
	Ofrece al usuario DOS metodos de entrada del token, pensados para
	que el problema del "teclado interno de Kodi sin boton de pegar"
	(tipico en Android TV / tablets) no bloquee al usuario:

	  Metodo A) SERVIDOR LOCAL (recomendado, no requiere teclado)
	    - Montamos un mini HTTP server en 0.0.0.0:port del propio Kodi
	    - Le decimos al usuario que URL abrir (http://<ip-kodi>:<port>)
	      desde el navegador de cualquier dispositivo con clipboard nativo
	      (el mismo tablet, el movil, el portatil...)
	    - El usuario pega el link de Install en un formulario grande y
	      pulsa Submit. El server recibe el token, valida y se cierra.
	    - Ventaja: NO usamos el teclado de Kodi en ningun momento.

	  Metodo B) INTRODUCIR A MANO
	    - Dialogo input() clasico. Funciona en desktop (Ctrl+V en el
	      teclado de Kodi suele pegar del portapapeles del SO). En
	      Android es inviable a menos que el usuario haya instalado
	      'Keyboard (Android)' o use Kore desde el movil.

	Ambos caminos comparten el paso final: validar el token con los
	helpers del scraper (_normalize_sootio_token + _detect_debrid_from_token),
	y si todo OK guardar sootio.config + sootio.debrid.detected +
	activar provider.sootio.

	Invocacion desde settings.xml:
	  <setting type="action" label="..."
	           action="RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_sootioWizard)" />
"""

import socket
import threading
from resources.lib.jacksparrow import control
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow.control import setSetting


CONFIGURE_URL = 'https://sooti.info/configure'
_LISTEN_PORT  = 48219   # puerto arbitrario poco usado; si esta ocupado probamos otros
_HTTP_TIMEOUT = 300     # segundos que el server espera al usuario antes de rendirse


# -----------------------------------------------------------------------------
# Helpers compartidos
# -----------------------------------------------------------------------------

def _copy2clip_safe(text):
	try:
		from resources.lib.modules.source_utils import copy2clip
		copy2clip(text)
		return True
	except Exception:
		return False


def _detect_from_token(raw):
	"""Reutiliza normalizer + detector del scraper."""
	try:
		from resources.lib.jacksparrow.sourcesdir.torrents.sootio import (
			_normalize_sootio_token, _detect_debrid_from_token,
		)
		norm = _normalize_sootio_token(raw)
		return norm, (_detect_debrid_from_token(norm) or '')
	except Exception:
		return '', ''


def _get_local_ip():
	"""IP LAN donde los otros dispositivos pueden encontrar a este Kodi.
	Hack clasico: abrir un UDP ficticio hacia Internet para que el SO
	nos diga que interfaz usaria. No envia ningun byte."""
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
	"""Primer puerto libre a partir de _LISTEN_PORT."""
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


def _save_token(raw_token, detected_label):
	"""Persiste settings y activa el provider."""
	try:
		setSetting('sootio.config', raw_token)
		setSetting('sootio.debrid.detected', detected_label or 'not configured')
		setSetting('provider.sootio', 'true')
		return True
	except Exception:
		return False


# -----------------------------------------------------------------------------
# Mini servidor HTTP — un solo request, vida corta
# -----------------------------------------------------------------------------

_HTML_FORM = u"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sootio Setup</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif;
         background:#141414; color:#eee; margin:0; padding:24px; }
  h1 { color:#00fa9a; margin:0 0 8px 0; font-size:22px; }
  p  { color:#aaa; line-height:1.5; margin:8px 0; }
  code { color:#fdb515; }
  form { margin-top:18px; }
  textarea { width:100%; box-sizing:border-box; min-height:140px;
             background:#1e1e1e; color:#fff; border:1px solid #333;
             border-radius:8px; padding:12px; font-family:monospace;
             font-size:13px; word-break:break-all; }
  button { background:#00fa9a; color:#000; border:0; border-radius:8px;
           padding:14px 28px; font-size:16px; font-weight:bold;
           margin-top:14px; cursor:pointer; width:100%; }
  .hint { color:#666; font-size:12px; margin-top:4px; }
</style></head>
<body>
<h1>Sootio &mdash; paste your Install link</h1>
<p>Go to <code>https://sooti.info/configure</code>, configure your Debrid and
scrapers, and copy the full Install link (it ends in <code>/manifest.json</code>).
Paste it below and press Save. You can close this page afterwards.</p>
<form method="post" action="/">
  <textarea name="token" autofocus placeholder="https://sooti.info/.../manifest.json"></textarea>
  <div class="hint">Tip: on mobile, long-press inside the box and choose Paste.</div>
  <button type="submit">Save to Kodi</button>
</form>
</body></html>
"""

_HTML_OK = u"""<!doctype html>
<html><head><meta charset="utf-8"><title>Sootio saved</title>
<style>body{font-family:system-ui;background:#141414;color:#00fa9a;
text-align:center;padding:60px 20px;}h1{font-size:28px}p{color:#aaa}</style>
</head><body><h1>&check; Saved</h1><p>Detected Debrid: <b style="color:#fdb515">%s</b></p>
<p>You can close this page and go back to Kodi.</p></body></html>
"""

_HTML_BAD = u"""<!doctype html>
<html><head><meta charset="utf-8"><title>Sootio error</title>
<style>body{font-family:system-ui;background:#141414;color:#ff6666;
text-align:center;padding:60px 20px;}h1{font-size:28px}p{color:#aaa}
a{color:#00fa9a}</style></head><body>
<h1>Could not parse that link</h1>
<p>Make sure you copy the full URL from sooti.info/configure.</p>
<p><a href="/">Try again</a></p></body></html>
"""


class _WizardServer(object):
	"""Servidor TCP sin dependencias externas. Atiende varios GET (para
	reintentos tras error) y termina cuando recibe un POST con token
	valido, o cuando expira _HTTP_TIMEOUT."""

	def __init__(self, port):
		self.port     = port
		self.result   = None   # (raw_token, detected_label) cuando exito
		self.sock     = None
		self._stop    = False
		self._thread  = None

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
		try: self.sock.close()
		except Exception: pass

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
				try: conn.close()
				except Exception: pass
			if self.result is not None:
				return

	def _handle(self, conn):
		conn.settimeout(5.0)
		data = b''
		while b'\r\n\r\n' not in data and len(data) < 65536:
			chunk = conn.recv(4096)
			if not chunk: break
			data += chunk

		if not data:
			return

		head, _, body = data.partition(b'\r\n\r\n')
		headline = head.split(b'\r\n', 1)[0]

		if headline.startswith(b'POST'):
			clen = 0
			for line in head.split(b'\r\n')[1:]:
				if line.lower().startswith(b'content-length:'):
					try: clen = int(line.split(b':',1)[1].strip())
					except Exception: clen = 0
			while len(body) < clen and len(body) < 1048576:
				chunk = conn.recv(min(65536, clen - len(body)))
				if not chunk: break
				body += chunk

			try:
				from urllib.parse import unquote_plus
			except ImportError:
				from urllib import unquote_plus
			token_raw = ''
			for kv in body.decode('utf-8', errors='replace').split('&'):
				if kv.startswith('token='):
					token_raw = unquote_plus(kv[6:])
					break
			token_raw = token_raw.strip()
			norm, detected = _detect_from_token(token_raw)
			if not norm:
				self._send(conn, 400, 'Bad Request', _HTML_BAD)
				return
			self.result = (token_raw, detected or '')
			self._send(conn, 200, 'OK', _HTML_OK % (detected or 'not configured'))
			return

		self._send(conn, 200, 'OK', _HTML_FORM)

	@staticmethod
	def _send(conn, status, reason, body):
		body_b = body.encode('utf-8')
		resp = (
			'HTTP/1.1 %d %s\r\n'
			'Content-Type: text/html; charset=utf-8\r\n'
			'Content-Length: %d\r\n'
			'Connection: close\r\n\r\n'
		) % (status, reason, len(body_b))
		try:
			conn.sendall(resp.encode('utf-8') + body_b)
		except Exception:
			pass


# -----------------------------------------------------------------------------
# Metodo A: servidor local
# -----------------------------------------------------------------------------

def _method_local_server():
	import time
	import xbmcgui
	port = _find_free_port()
	if port is None:
		control.dialog.ok(
			'Sootio Setup — error',
			'Could not open a local port for the setup server.\n'
			'Try the manual paste method instead.',
		)
		return False

	srv = _WizardServer(port)
	try:
		srv.start()
	except Exception as e:
		control.dialog.ok(
			'Sootio Setup — error',
			'Could not start local server:\n%s\n\n'
			'Try the manual paste method instead.' % str(e),
		)
		return False

	ip = _get_local_ip()
	url = 'http://%s:%d' % (ip, port)
	_copy2clip_safe(url)

	control.dialog.ok(
		'Sootio Setup — open this URL on your phone/PC',
		'On the same Wi-Fi, open this in a browser:\n\n'
		'[COLOR fffdb515]%s[/COLOR]\n\n'
		'Paste the Install link from sooti.info/configure in the form and\n'
		'press [B]Save to Kodi[/B].\n\n'
		'The server stays open for %d minutes. Press OK and wait —\n'
		'Kodi will show a confirmation when the token is received.' % (url, _HTTP_TIMEOUT // 60),
	)

	# Server sigue vivo — progress dialog cancelable mientras esperamos el POST
	pd = xbmcgui.DialogProgressBG()
	pd.create('Sootio Setup', 'Waiting for token from browser...')

	t0 = time.time()
	while srv.is_alive() and srv.result is None:
		elapsed = int(time.time() - t0)
		remaining = _HTTP_TIMEOUT - elapsed
		if remaining <= 0:
			break
		pct = int(elapsed * 100 / _HTTP_TIMEOUT)
		pd.update(min(pct, 99), 'Sootio Setup',
		          'Waiting... (%ds remaining)' % remaining)
		time.sleep(0.5)

	pd.close()
	srv.stop()

	if srv.result is None:
		control.dialog.ok(
			'Sootio Setup — cancelled',
			'No token was received (timeout or server error).\n'
			'You can try again or use the manual paste method.',
		)
		return False

	raw_token, detected = srv.result
	if not _save_token(raw_token, detected):
		control.dialog.ok(
			'Sootio Setup — error',
			'Could not write settings. Check addon permissions.',
		)
		return False

	control.dialog.ok(
		'Sootio Setup — done',
		'[COLOR ff00fa9a]Sootio is configured and enabled.[/COLOR]\n\n'
		'Debrid detected: [COLOR fffdb515]%s[/COLOR]\n\n'
		'No need to authorize the Debrid service separately in the plugin.'
		% (detected or 'not configured'),
	)
	return True


# -----------------------------------------------------------------------------
# Metodo B: paste manual (fallback)
# -----------------------------------------------------------------------------

def _method_manual_paste():
	prior = getSetting('sootio.config') or ''
	pasted = control.dialog.input(
		heading='Paste Sootio Install link',
		defaultt=prior,
		type=0,
	)
	if not pasted:
		return False

	pasted = pasted.strip()
	norm, detected = _detect_from_token(pasted)
	if not norm:
		control.dialog.ok(
			'Sootio Setup — failed',
			'Could not parse that link. Make sure you copied the full URL\n'
			'from sooti.info/configure (ending in /manifest.json).',
		)
		return False

	if not _save_token(pasted, detected):
		control.dialog.ok('Sootio Setup — error', 'Could not write settings.')
		return False

	control.dialog.ok(
		'Sootio Setup — done',
		'[COLOR ff00fa9a]Sootio is configured and enabled.[/COLOR]\n\n'
		'Debrid detected: [COLOR fffdb515]%s[/COLOR]'
		% (detected or 'not configured'),
	)
	return True


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def run():
	intro = (
		'Sootio searches your Debrid cloud for cached torrents. Configure it\n'
		'once on its web page and paste the resulting link — the plugin handles\n'
		'the rest (Debrid auth included, no need to log in again in Kodi).\n\n'
		'[COLOR fffdb515]Configuration URL:[/COLOR]\n%s'
	) % CONFIGURE_URL

	if not control.dialog.yesno(
		'Sootio Setup (1/2) — overview',
		intro,
		nolabel='Cancel',
		yeslabel='Continue',
	):
		return

	choice = control.dialog.select(
		'Sootio Setup (2/2) — how do you want to paste the Install link?',
		[
			'[COLOR ff00fa9a]Use a browser on another device[/COLOR]  (recommended, no keyboard)',
			'Type / paste here using the Kodi keyboard',
		],
	)
	if choice == -1:
		return
	if choice == 0:
		_method_local_server()
	else:
		_method_manual_paste()
