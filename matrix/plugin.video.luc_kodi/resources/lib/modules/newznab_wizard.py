# -*- coding: utf-8 -*-
"""
	plugin.video.luc_kodi — Newznab Setup Wizard

	Configura un indexer Newznab CUSTOM (NZBGeek, DrunkenSlug, NZBFinder,
	NZBHydra2, Prowlarr, o un puente Easynews->Newznab) sin teclear nada
	largo a mano. Mismo patron que los wizards de Sootio/Comet/Meteor/Torz,
	pero con DOS campos (URL del indexer + API key) en vez de un solo token,
	porque Newznab separa endpoint y credencial.

	  Metodo A) SERVIDOR LOCAL (recomendado, no requiere teclado)
	    Mini HTTP server en 0.0.0.0:port del propio Kodi. El usuario abre
	    http://<ip-kodi>:<port> desde el navegador de cualquier dispositivo
	    con clipboard nativo, pega URL + API key en un formulario grande y
	    pulsa Save. El server valida contra el indexer y se cierra.

	  Metodo B) INTRODUCIR A MANO
	    Dos dialogos input() clasicos (URL, luego API key). Funciona en
	    desktop; en Android es incomodo (de ahi el metodo A).

	Al guardar: newznab.url + newznab.apikey, y se activa provider.newznab.
	Los NZB los resuelve SIEMPRE Premiumize (v1.0.59); el wizard avisa al
	terminar si Premiumize no esta autorizado todavia.

	Invocacion desde settings.xml:
	  action="RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_newznabWizard)"
	  action="RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_newznabTest)"
"""

import socket
import threading
from resources.lib.jacksparrow import control
from resources.lib.jacksparrow.control import setting as getSetting
from resources.lib.jacksparrow.control import setSetting


_LISTEN_PORT  = 48231   # puerto arbitrario poco usado
_HTTP_TIMEOUT = 300     # segundos que el server espera al usuario


# -----------------------------------------------------------------------------
# Helpers compartidos con el scraper
# -----------------------------------------------------------------------------

def _normalize_url(raw):
	"""Reutiliza el normalizador del scraper (…-> '<host>/api')."""
	try:
		from resources.lib.jacksparrow.sourcesdir.torrents.newznab import _normalize_newznab_url
		return _normalize_newznab_url(raw)
	except Exception:
		return (raw or '').strip()


def _test(url, key):
	"""Reutiliza el test del scraper (t=caps). Devuelve (ok, msg)."""
	try:
		from resources.lib.jacksparrow.sourcesdir.torrents.newznab import test_indexer
		return test_indexer(url, key)
	except Exception as e:
		return False, 'Test helper failed: %s' % str(e)


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


def _save(url, key):
	"""Persiste settings y activa el provider. Devuelve True si OK."""
	try:
		norm = _normalize_url(url)
		setSetting('newznab.url', norm)
		setSetting('newznab.apikey', (key or '').strip())
		setSetting('provider.newznab', 'true')
		return True
	except Exception:
		return False


# -----------------------------------------------------------------------------
# Mini servidor HTTP — formulario con DOS campos (URL + API key)
# -----------------------------------------------------------------------------

_HTML_FORM = u"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Newznab Setup</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif;
         background:#141414; color:#eee; margin:0; padding:24px; }
  h1 { color:#00fa9a; margin:0 0 8px 0; font-size:22px; }
  p  { color:#aaa; line-height:1.5; margin:8px 0; }
  code { color:#fdb515; }
  label { display:block; margin:16px 0 6px 0; color:#ccc; font-weight:bold; }
  input { width:100%; box-sizing:border-box; background:#1e1e1e; color:#fff;
          border:1px solid #333; border-radius:8px; padding:12px;
          font-family:monospace; font-size:14px; }
  button { background:#00fa9a; color:#000; border:0; border-radius:8px;
           padding:14px 28px; font-size:16px; font-weight:bold;
           margin-top:18px; cursor:pointer; width:100%; }
  .hint { color:#666; font-size:12px; margin-top:4px; }
</style></head>
<body>
<h1>Newznab &mdash; indexer details</h1>
<p>Enter your Usenet indexer's base URL and API key. Works with NZBGeek,
DrunkenSlug, NZBFinder, NZBHydra2, Prowlarr, or any Newznab endpoint. The
URL usually looks like <code>https://your-indexer.tld/api</code>. Find the
API key on your indexer's profile / settings page.</p>
<form method="post" action="/">
  <label for="u">Indexer URL</label>
  <input id="u" name="url" autofocus placeholder="https://your-indexer.tld/api">
  <div class="hint">You can paste the site root; Kodi will append /api if needed.</div>
  <label for="k">API Key</label>
  <input id="k" name="apikey" placeholder="your api key">
  <div class="hint">Tip: on mobile, long-press inside a box and choose Paste.</div>
  <label style="font-weight:normal;display:flex;align-items:center;gap:8px;margin-top:16px;">
    <input type="checkbox" name="skipverify" value="1" style="width:auto;">
    Save without verifying (use if the test fails but you know the details are right)
  </label>
  <button type="submit">Save to Kodi</button>
</form>
</body></html>
"""

_HTML_OK = u"""<!doctype html>
<html><head><meta charset="utf-8"><title>Newznab saved</title>
<style>body{font-family:system-ui;background:#141414;color:#00fa9a;
text-align:center;padding:60px 20px;}h1{font-size:28px}p{color:#aaa}</style>
</head><body><h1>&check; Saved</h1><p>%s</p>
<p>You can close this page and go back to Kodi.</p></body></html>
"""

_HTML_BAD = u"""<!doctype html>
<html><head><meta charset="utf-8"><title>Newznab error</title>
<style>body{font-family:system-ui;background:#141414;color:#ff6666;
text-align:center;padding:60px 20px;}h1{font-size:28px}p{color:#aaa}
a{color:#00fa9a}</style></head><body>
<h1>Could not verify that indexer</h1>
<p>%s</p>
<p><a href="/">Try again</a></p></body></html>
"""


class _WizardServer(object):
	"""Servidor TCP sin dependencias. Atiende GET (form, con reintentos) y
	termina cuando recibe un POST valido (URL+key verificados) o al expirar."""

	def __init__(self, port):
		self.port    = port
		self.result  = None   # (url, key, msg) cuando exito
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
			url_raw, key_raw, skip = '', '', False
			for kv in body.decode('utf-8', errors='replace').split('&'):
				if kv.startswith('url='):
					url_raw = unquote_plus(kv[4:])
				elif kv.startswith('apikey='):
					key_raw = unquote_plus(kv[7:])
				elif kv.startswith('skipverify='):
					skip = unquote_plus(kv[11:]).strip() in ('1', 'on', 'true')
			url_raw = url_raw.strip()
			key_raw = key_raw.strip()
			if not url_raw or not key_raw:
				self._send(conn, 400, 'Bad Request', _HTML_BAD % 'URL and API key are both required.')
				return
			if skip:
				# El usuario asume el riesgo: guardar sin verificar.
				self.result = (url_raw, key_raw, 'Saved without verifying.')
				self._send(conn, 200, 'OK', _HTML_OK % 'Saved without verifying.')
				return
			ok, msg = _test(url_raw, key_raw)
			if not ok:
				# No verificado: NO bloqueamos definitivamente; mostramos el error
				# y ofrecemos guardar igualmente marcando la casilla.
				self._send(conn, 400, 'Bad Request', _HTML_BAD % (
					msg + '<br><br>If you are sure the details are correct, '
					'tick <b>"Save without verifying"</b> and submit again.'))
				return
			self.result = (url_raw, key_raw, msg)
			self._send(conn, 200, 'OK', _HTML_OK % msg)
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
			'Newznab Setup — error',
			'Could not open a local port for the setup server.\n'
			'Try the manual entry method instead.',
		)
		return False

	srv = _WizardServer(port)
	try:
		srv.start()
	except Exception as e:
		control.dialog.ok(
			'Newznab Setup — error',
			'Could not start local server:\n%s\n\n'
			'Try the manual entry method instead.' % str(e),
		)
		return False

	ip = _get_local_ip()
	url = 'http://%s:%d' % (ip, port)
	_copy2clip_safe(url)

	control.dialog.ok(
		'Newznab Setup — open this URL',
		'On the same Wi-Fi, open in a browser:\n\n'
		'[COLOR fffdb515]%s[/COLOR]\n\n'
		'Enter your indexer URL + API key there and press [B]Save[/B]. '
		'Then press OK here and wait — Kodi confirms when done.\n\n'
		'(Server open for %d min.)' % (url, _HTTP_TIMEOUT // 60),
	)

	pd = xbmcgui.DialogProgressBG()
	pd.create('Newznab Setup', 'Waiting for details from browser...')

	t0 = time.time()
	while srv.is_alive() and srv.result is None:
		elapsed = int(time.time() - t0)
		remaining = _HTTP_TIMEOUT - elapsed
		if remaining <= 0:
			break
		pct = int(elapsed * 100 / _HTTP_TIMEOUT)
		pd.update(min(pct, 99), 'Newznab Setup', 'Waiting... (%ds remaining)' % remaining)
		time.sleep(0.5)

	pd.close()
	srv.stop()

	if srv.result is None:
		control.dialog.ok(
			'Newznab Setup — cancelled',
			'No details were received (timeout or server error).\n'
			'You can try again or use the manual entry method.',
		)
		return False

	url_raw, key_raw, msg = srv.result
	if not _save(url_raw, key_raw):
		control.dialog.ok('Newznab Setup — error', 'Could not write settings. Check addon permissions.')
		return False

	_done_dialog(msg)
	return True


# -----------------------------------------------------------------------------
# Metodo B: entrada manual (fallback)
# -----------------------------------------------------------------------------

def _method_manual_paste():
	prior_url = getSetting('newznab.url') or ''
	url_in = control.dialog.input(heading='Indexer URL (e.g. https://your-indexer/api)', defaultt=prior_url, type=0)
	if not url_in:
		return False
	prior_key = getSetting('newznab.apikey') or ''
	key_in = control.dialog.input(heading='Indexer API Key', defaultt=prior_key, type=0)
	if not key_in:
		return False

	url_in, key_in = url_in.strip(), key_in.strip()
	ok, msg = _test(url_in, key_in)
	if not ok:
		if not control.dialog.yesno(
			'Newznab Setup — verification failed',
			'The indexer did not verify:\n[COLOR ffff6666]%s[/COLOR]\n\n'
			'Save these details anyway?' % msg,
			nolabel='Cancel', yeslabel='Save anyway',
		):
			return False

	if not _save(url_in, key_in):
		control.dialog.ok('Newznab Setup — error', 'Could not write settings.')
		return False

	_done_dialog(msg if ok else 'Saved (unverified).')
	return True


def _done_dialog(msg):
	# v1.0.59: el scraper Newznab resuelve SOLO con Premiumize. Ya no hay
	# eleccion de debrid, asi que el recordatorio se limita a avisar si
	# Premiumize no esta autorizado todavia.
	pm_ok = getSetting('premiumize.enable') == 'true' and bool(getSetting('premiumize.token'))
	who = ('Premiumize' if pm_ok else
		'[COLOR ffff6666]Premiumize — NOT authorized yet! '
		'Set it up under My Accounts or your NZB results will not appear.[/COLOR]')
	control.dialog.ok(
		'Newznab Setup — done',
		'[COLOR ff00fa9a]Newznab indexer configured and enabled.[/COLOR]\n\n'
		'%s\n\n'
		'NZB results are resolved by: [COLOR fffdb515]%s[/COLOR]' % (msg, who),
	)


# -----------------------------------------------------------------------------
# Entry points
# -----------------------------------------------------------------------------

def run():
	intro = (
		'Newznab lets you plug in YOUR OWN Usenet indexer (NZBGeek, '
		'DrunkenSlug, NZBFinder, NZBHydra2, Prowlarr, or an Easynews->Newznab '
		'bridge). It only SEARCHES for NZBs — a debrid (TorBox or Premiumize) '
		'downloads and streams them.\n\n'
		'You will need your indexer URL and API key.'
	)
	if not control.dialog.yesno(
		'Newznab Setup (1/2)', intro, nolabel='Cancel', yeslabel='Continue',
	):
		return

	choice = control.dialog.select(
		'Newznab Setup (2/2) — entry method',
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


def test():
	"""Prueba la conexion con los settings ya guardados, sin re-ejecutar el
	wizard. Util tras editar la URL/API key a mano."""
	url = getSetting('newznab.url') or ''
	key = getSetting('newznab.apikey') or ''
	if not url or not key:
		control.dialog.ok(
			'Newznab — test',
			'No indexer configured yet.\n\n'
			'Run the Newznab Setup Wizard first, or fill in the URL and API '
			'key fields.',
		)
		return
	ok, msg = _test(url, key)
	if ok:
		control.dialog.ok('Newznab — test OK', '[COLOR ff00fa9a]%s[/COLOR]' % msg)
	else:
		control.dialog.ok('Newznab — test failed', '[COLOR ffff6666]%s[/COLOR]' % msg)
