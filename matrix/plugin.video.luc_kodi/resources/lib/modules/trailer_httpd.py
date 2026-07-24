# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — trailer_httpd.py (v1.0.49)

	Micro-servidor HTTP en 127.0.0.1 que sirve el manifest DASH de los
	tráilers a inputstream.adaptive. Necesario porque el descargador de ISA
	(pila CURL) no entiende rutas special:// ni archivos locales — es la
	misma razón por la que el addon oficial de YouTube y SlyGuy sirven sus
	MPD vía servidor local (log del 03-07: "CURLOpen failed ...
	special://temp/luc_kodi_trailer.mpd").

	Diseño:
	- El contenido del MPD vive en una window property de home
	  (luc_kodi.trailer_mpd) — cero disco, cero traducción de rutas, y
	  accesible entre invokers (yt_resolver lo escribe desde el invoker del
	  tráiler, este servidor lo lee desde el proceso del service).
	- Solo se sirve GET /trailer.mpd; todo lo demás es 404. Bind exclusivo a
	  127.0.0.1. Sin logging por petición.
	- Puerto: primero libre del rango 48996-49005; el elegido se publica en
	  la property luc_kodi.trailer_httpd_port para que yt_resolver construya
	  la URL. ISA solo necesita UNA petición (el manifest); los segmentos
	  van directos a googlevideo con sus BaseURL absolutas.
	- Arranca desde service.py (hilo daemon). Kodi reinicia el service al
	  actualizar el addon, así que el servidor está vivo tras el update.
	  yt_resolver tiene además un arranque efímero de emergencia por si la
	  property del puerto no existiera.
"""

import threading
import http.server
import socketserver

from resources.lib.modules import control
from resources.lib.modules import log_utils

LOGINFO = log_utils.LOGINFO

PROP_CONTENT = 'luc_kodi.trailer_mpd'
PROP_PORT = 'luc_kodi.trailer_httpd_port'
PORT_RANGE = range(48996, 49006)

_started_lock = threading.Lock()
_started = [False]


class _Handler(http.server.BaseHTTPRequestHandler):
	protocol_version = 'HTTP/1.1'

	def do_GET(self):
		if self.path.split('?')[0] != '/trailer.mpd':
			self.send_response(404)
			self.send_header('Content-Length', '0')
			self.end_headers()
			return
		try: content = control.homeWindow.getProperty(PROP_CONTENT) or ''
		except Exception: content = ''
		data = content.encode('utf-8')
		if not data:
			self.send_response(404)
			self.send_header('Content-Length', '0')
			self.end_headers()
			return
		self.send_response(200)
		self.send_header('Content-Type', 'application/dash+xml')
		self.send_header('Content-Length', str(len(data)))
		self.end_headers()
		try: self.wfile.write(data)
		except Exception: pass

	def log_message(self, *args):
		pass  # sin ruido en el log de Kodi


class _Server(socketserver.ThreadingTCPServer):
	allow_reuse_address = True
	daemon_threads = True


def start():
	"""Arranca el servidor en un hilo daemon. Idempotente dentro del mismo
	proceso; entre procesos, el bind exclusivo del puerto hace de guardia
	(el segundo proceso simplemente prueba el siguiente puerto del rango,
	pero el efímero solo se lanza si la property del puerto no existe)."""
	with _started_lock:
		if _started[0]: return
		_started[0] = True
	worker = threading.Thread(target=_serve)
	worker.daemon = True
	worker.start()


def _serve():
	for port in PORT_RANGE:
		try:
			server = _Server(('127.0.0.1', port), _Handler)
		except OSError:
			continue
		try:
			control.homeWindow.setProperty(PROP_PORT, str(port))
			control.log('[ luc_kodi ] trailer_httpd: serving on 127.0.0.1:%s' % port, LOGINFO)
			server.serve_forever(poll_interval=1.0)
		except Exception:
			log_utils.error()
		finally:
			try: server.server_close()
			except Exception: pass
		return
	control.log('[ luc_kodi ] trailer_httpd: no free port in %s-%s' % (PORT_RANGE.start, PORT_RANGE.stop - 1), LOGINFO)
	with _started_lock:
		_started[0] = False
