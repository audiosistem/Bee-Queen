# -*- coding: utf-8 -*-
"""
	plugin.video.luc_kodi — Custom Badges Setup Wizard

	Permite instalar un pack de iconos "custom" para los badges de
	Dolby Atmos / HDR / Dolby Vision / etc. de Source Results, sin teclear
	nada a mano en Android TV / tablets. Mismo patron que los wizards de
	Torz/Comet/Sootio/Meteor:

	  Metodo A) SERVIDOR LOCAL (recomendado, no requiere teclado)
	    Mini HTTP server en 0.0.0.0:<port> del propio Kodi. El usuario abre
	    http://<ip-kodi>:<port> desde el navegador de cualquier dispositivo,
	    pega la URL de un badges.json (p.ej. exportado desde Nuvio Badges
	    Studio) y pulsa Save.

	  Metodo B) INTRODUCIR A MANO (fallback)
	    Dialogo input() clasico con la URL.

	Formato del badges.json: compatible con el de Nuvio Badges Studio
	(https://dustincos.github.io/nuvio-badges/) — un objeto con "filters":
	[{pattern, imageURL, isEnabled, ...}]. La descarga/parseo real la hace
	badges_config.install_from_url().

	Invocacion desde settings.xml:
	  <setting type="action" label="..."
	           action="RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_badgesWizard)" />
"""

import socket
import threading

from resources.lib.jacksparrow import control


_LISTEN_PORT  = 48260   # puerto arbitrario poco usado (distinto de Sootio/Meteor/MDBList/Torz/Comet)
_HTTP_TIMEOUT = 300      # segundos que el server espera al usuario


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


def _get_local_ip():
	"""IP LAN de este Kodi."""
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


def _install(url):
	"""Reutiliza el motor de badges_config; nunca lanza excepcion al caller."""
	try:
		from resources.lib.modules import badges_config
		return badges_config.install_from_url(url)
	except Exception as e:
		return False, 'Unexpected error: %s' % str(e)


# -----------------------------------------------------------------------------
# Mini servidor HTTP
# -----------------------------------------------------------------------------

_HTML_FORM = u"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>luc_kodi Custom Badges Setup</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif;
         background:#141414; color:#eee; margin:0; padding:24px; }
  h1 { color:#00fa9a; margin:0 0 8px 0; font-size:22px; }
  p  { color:#aaa; line-height:1.5; margin:8px 0; }
  code { color:#fdb515; }
  a { color:#00fa9a; }
  form { margin-top:18px; }
  input[type=text] { width:100%; box-sizing:border-box;
             background:#1e1e1e; color:#fff; border:1px solid #333;
             border-radius:8px; padding:12px; font-family:monospace;
             font-size:13px; }
  button { background:#00fa9a; color:#000; border:0; border-radius:8px;
           padding:14px 28px; font-size:16px; font-weight:bold;
           margin-top:14px; cursor:pointer; width:100%; }
  .hint { color:#666; font-size:12px; margin-top:4px; }
</style></head>
<body>
<h1>Custom Badges &mdash; paste your badges.json URL</h1>
<p>Compatible with <a href="https://dustincos.github.io/nuvio-badges/" target="_blank">Nuvio Badges Studio</a>
exports, or your own hand-made JSON with the same
<code>{"filters":[{"pattern":"...","imageURL":"..."}]}</code> shape.</p>
<form method="post" action="/">
  <input type="text" name="url" autofocus placeholder="https://raw.githubusercontent.com/.../badges.json">
  <div class="hint">Tip: on mobile, long-press inside the box and choose Paste.</div>
  <button type="submit">Install to Kodi</button>
</form>
</body></html>
"""

_HTML_OK = u"""<!doctype html>
<html><head><meta charset="utf-8"><title>Badges installed</title>
<style>body{font-family:system-ui;background:#141414;color:#00fa9a;
text-align:center;padding:60px 20px;}h1{font-size:28px}p{color:#aaa}</style>
</head><body><h1>&check; Installed</h1><p>%s</p>
<p>You can close this page and go back to Kodi.</p></body></html>
"""

_HTML_BAD = u"""<!doctype html>
<html><head><meta charset="utf-8"><title>Badges error</title>
<style>body{font-family:system-ui;background:#141414;color:#ff6666;
text-align:center;padding:60px 20px;}h1{font-size:28px}p{color:#aaa}
a{color:#00fa9a}</style></head><body>
<h1>Could not install that pack</h1>
<p>%s</p>
<p><a href="/">Try again</a></p></body></html>
"""


class _WizardServer(object):
	def __init__(self, port):
		self.port    = port
		self.result  = None   # (ok, message) cuando termina
		self.sock    = None
		self._stop   = False
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
		conn.settimeout(30.0)  # instalar puede tardar unos segundos (descarga de imagenes)
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
					try: clen = int(line.split(b':', 1)[1].strip())
					except Exception: clen = 0
			while len(body) < clen and len(body) < 1048576:
				chunk = conn.recv(min(65536, clen - len(body)))
				if not chunk: break
				body += chunk

			try:
				from urllib.parse import unquote_plus
			except ImportError:
				from urllib import unquote_plus
			url_raw = ''
			for kv in body.decode('utf-8', errors='replace').split('&'):
				if kv.startswith('url='):
					url_raw = unquote_plus(kv[4:])
					break
			url_raw = url_raw.strip()

			ok, msg = _install(url_raw)
			self.result = (ok, msg)
			if ok:
				self._send(conn, 200, 'OK', _HTML_OK % msg)
			else:
				self._send(conn, 400, 'Bad Request', _HTML_BAD % msg)
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
			'Custom Badges Setup — error',
			'Could not open a local port for the setup server.\n'
			'Try the manual paste method instead.',
		)
		return False

	srv = _WizardServer(port)
	try:
		srv.start()
	except Exception as e:
		control.dialog.ok(
			'Custom Badges Setup — error',
			'Could not start local server:\n%s\n\n'
			'Try the manual paste method instead.' % str(e),
		)
		return False

	ip = _get_local_ip()
	url = 'http://%s:%d' % (ip, port)
	_copy2clip_safe(url)

	control.dialog.ok(
		'Custom Badges Setup — open this URL',
		'On the same Wi-Fi, open in a browser:\n\n'
		'[COLOR fffdb515]%s[/COLOR]\n\n'
		'Paste a badges.json URL there and press [B]Install[/B]. '
		'Then press OK here and wait — Kodi confirms when done.\n\n'
		'(Server open for %d min.)' % (url, _HTTP_TIMEOUT // 60),
	)

	pd = xbmcgui.DialogProgressBG()
	pd.create('Custom Badges Setup', 'Waiting for a badges.json URL...')

	t0 = time.time()
	while srv.is_alive() and srv.result is None:
		elapsed = int(time.time() - t0)
		remaining = _HTTP_TIMEOUT - elapsed
		if remaining <= 0:
			break
		pct = int(elapsed * 100 / _HTTP_TIMEOUT)
		pd.update(min(pct, 99), 'Custom Badges Setup',
		          'Waiting... (%ds remaining)' % remaining)
		time.sleep(0.5)

	pd.close()
	srv.stop()

	if srv.result is None:
		control.dialog.ok(
			'Custom Badges Setup — cancelled',
			'No badges.json was received (timeout or server error).\n'
			'You can try again or use the manual paste method.',
		)
		return False

	ok, msg = srv.result
	if ok:
		control.dialog.ok(
			'Custom Badges Setup — done',
			'[COLOR ff00fa9a]Custom badges installed and enabled.[/COLOR]\n\n%s\n\n'
			'Use "Restore default icons" in settings to go back to the built-in set.' % msg,
		)
	else:
		control.dialog.ok('Custom Badges Setup — failed', msg)
	return ok


# -----------------------------------------------------------------------------
# Metodo B: paste manual (fallback)
# -----------------------------------------------------------------------------

def _method_manual_paste():
	pasted = control.dialog.input(
		heading='Paste a badges.json URL',
		defaultt='',
		type=0,
	)
	if not pasted:
		return False

	ok, msg = _install(pasted.strip())
	if ok:
		control.dialog.ok(
			'Custom Badges Setup — done',
			'[COLOR ff00fa9a]Custom badges installed and enabled.[/COLOR]\n\n%s' % msg,
		)
	else:
		control.dialog.ok('Custom Badges Setup — failed', msg)
	return ok


# -----------------------------------------------------------------------------
# Entry points
# -----------------------------------------------------------------------------

def run():
	intro = (
		'Bored of the built-in Dolby Atmos / HDR / Dolby Vision icons?\n\n'
		'Install a custom badge pack — compatible with '
		'[COLOR fffdb515]Nuvio Badges Studio[/COLOR] exports '
		'(dustincos.github.io/nuvio-badges) or your own badges.json.\n\n'
		'Each rule matches part of the release name (regex) and shows its '
		'own icon instead of the default one.'
	)

	if not control.dialog.yesno(
		'Custom Badges Setup (1/2)',
		intro,
		nolabel='Cancel',
		yeslabel='Continue',
	):
		return

	choice = control.dialog.select(
		'Custom Badges Setup (2/2) — paste method',
		[
			'[COLOR ff00fa9a]Use a browser on another device[/COLOR]  (no keyboard)',
			'Type / paste here with the Kodi keyboard',
		],
	)
	if choice == -1:
		return
	if choice == 0:
		_method_local_server()
	else:
		_method_manual_paste()


def run_reset():
	if not control.dialog.yesno(
		'Restore default badges',
		'This will disable the custom badge pack and go back to the '
		'built-in icons.\n\n(The downloaded pack stays on disk, so you can '
		're-enable it later without reinstalling.)',
		nolabel='Cancel',
		yeslabel='Restore defaults',
	):
		return
	from resources.lib.modules import badges_config
	badges_config.reset_to_default()
	control.dialog.ok('Custom Badges', '[COLOR ff00fa9a]Default icons restored.[/COLOR]')
