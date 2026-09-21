# -*- coding: utf-8 -*-
"""Server persistent pentru manifestele DASH ale trailerelor YouTube.

Serverul aparține serviciului SamusXUI, nu invocării pluginului. Astfel
subinterpretorul care rezolvă un trailer nu lasă niciun fir în urmă.
"""
import os
import re
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import xbmc
import xbmcgui
import xbmcvfs


_MPD_DIR = xbmcvfs.translatePath(
    'special://profile/addon_data/plugin.video.samusxui/trailer_mpd/')
_PORT_PROPERTY = 'samusxui.trailer_mpd_port'
_server = None
_thread = None
_process = None


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def setup(self):
        super().setup()
        # Manifestul are câțiva KB; nicio conexiune nu trebuie să poată ține
        # serverul blocat după Stop sau la Quit.
        self.connection.settimeout(3)

    def _manifest(self):
        name = os.path.basename(self.path.split('?', 1)[0])
        path = os.path.join(_MPD_DIR, name)
        if not name.endswith('.mpd') or not os.path.isfile(path):
            return None
        with open(path, 'rb') as handle:
            return handle.read()

    def _headers(self, payload):
        self.send_response(200)
        self.send_header('Content-Type', 'application/dash+xml')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def do_GET(self):
        payload = self._manifest()
        if payload is None:
            self.send_error(404)
            return
        self._headers(payload)
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_HEAD(self):
        payload = self._manifest()
        if payload is None:
            self.send_error(404)
            return
        self._headers(payload)

    def log_message(self, _fmt, *_args):
        pass


def start_service_server():
    global _server, _thread, _process
    if _server is not None:
        return _server.server_port
    if _process is not None and _process.poll() is None:
        return int(xbmcgui.Window(10000).getProperty(_PORT_PROPERTY) or 0)
    os.makedirs(_MPD_DIR, exist_ok=True)
    # Pe desktop serverul rulează într-un proces separat. Kodi 21.3 este legat
    # aici de libpython 3.14; un CCurlFile::Stat inițiat la oprirea trailerului
    # poate aștepta serverul Python intern în timp ce firul GUI ține GIL-ul.
    # Procesul separat elimină complet această dependență. Android nu oferă un
    # interpretor Python de sistem, deci păstrează serverul intern.
    if not xbmc.getCondVisibility('System.Platform.Android') and os.path.isfile('/usr/bin/python3'):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()
        _process = subprocess.Popen(
            ['/usr/bin/python3', '-m', 'http.server', str(port),
             '--bind', '127.0.0.1', '--directory', _MPD_DIR],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                if _process.poll() is not None:
                    raise RuntimeError('serverul MPD extern s-a oprit la pornire')
                time.sleep(0.05)
        else:
            _process.terminate()
            _process.wait(timeout=2)
            _process = None
            raise RuntimeError('serverul MPD extern nu răspunde')
        xbmcgui.Window(10000).setProperty(_PORT_PROPERTY, str(port))
        xbmc.log(f'[SamusXUI/trailer] server MPD extern pornit pe portul {port}', xbmc.LOGINFO)
        return port
    _server = HTTPServer(('127.0.0.1', 0), _Handler)
    _thread = threading.Thread(
        target=_server.serve_forever, name='samus-trailer-mpd', daemon=True)
    _thread.start()
    port = _server.server_port
    xbmcgui.Window(10000).setProperty(_PORT_PROPERTY, str(port))
    xbmc.log(f'[SamusXUI/trailer] server MPD pornit pe portul {port}', xbmc.LOGINFO)
    return port


def stop_service_server():
    global _server, _thread, _process
    server, thread = _server, _thread
    process = _process
    _server = None
    _thread = None
    _process = None
    xbmcgui.Window(10000).clearProperty(_PORT_PROPERTY)
    if process is not None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        xbmc.log('[SamusXUI/trailer] server MPD extern oprit', xbmc.LOGINFO)
    if server is None:
        return
    server.shutdown()
    server.server_close()
    if thread is not None:
        thread.join(timeout=5)
        if thread.is_alive():
            xbmc.log('[SamusXUI/trailer] firul MPD nu s-a oprit', xbmc.LOGWARNING)
    xbmc.log('[SamusXUI/trailer] server MPD oprit', xbmc.LOGINFO)


def write_manifest(payload, video_id):
    """Scrie atomic manifestul și întoarce URL-ul servit local."""
    os.makedirs(_MPD_DIR, exist_ok=True)
    name = re.sub(r'[^A-Za-z0-9_-]', '', video_id or '') or 'current'
    final_path = os.path.join(_MPD_DIR, name + '.mpd')
    temp_path = final_path + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, final_path)
    port = xbmcgui.Window(10000).getProperty(_PORT_PROPERTY)
    if not port:
        # Serverul nu-i gata (ex. trailer cerut imediat după boot, înainte ca
        # serviciul să-l pornească) → îl pornim on-demand ca să folosim DASH,
        # nu fallback-ul progresiv (itag 18 ANDROID_VR, care dă 403 în Kodi).
        try:
            start_service_server()
        except Exception as exc:
            xbmc.log(f'[SamusXUI/trailer] pornire MPD on-demand eșuată: {exc}',
                     xbmc.LOGWARNING)
        port = xbmcgui.Window(10000).getProperty(_PORT_PROPERTY)
    if not port:
        return ''
    return f'http://127.0.0.1:{port}/{name}.mpd'
