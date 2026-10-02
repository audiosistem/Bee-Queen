# -*- coding: utf-8 -*-
"""
RomyLive+ - Cinemateca: redare prin proxy local cu cache pe disc.

PROBLEMA
--------
Serverul public care serveste fisierele canalului (tg.i-c-a.su) raspunde in
4-8 secunde pentru FIECARE cerere HTTP: isi rezolva referinta fisierului pe
Telegram de fiecare data. Un player care citeste fluxul in bucati mici - asa
cum face Kodi - ajunge sa astepte 4-8 secunde pentru fiecare bucata: filmul
porneste, se umple bufferul si apoi se blocheaza definitiv.

Masurat: 3 bucati de 2 MB cerute una dupa alta = 0.33 MB/s (2.7 Mbps), desi o
singura cerere lunga merge cu 2.5 MB/s. De aici blocajul dupa ~35 de secunde.
Un film are nevoie de ~0.05 MB/s, deci sursa e de 35 de ori mai rapida decat
consumul: problema e exclusiv intarzierea pe fiecare cerere, nu banda.

SOLUTIA
-------
Pluginul porneste un mic server HTTP local, in propriul proces, care:
  * citeste fisierul de la sursa in fundal, intr-un numar minim de cereri
    lungi, si il scrie intr-un fisier temporar;
  * descarca in PARALEL capul si coada fisierului (coada e obligatorie:
    indexul moov al filmelor MP4 se afla la final);
  * serveste playerului datele instantaneu de pe disc, cu suport complet de
    Range, deci si derularea inainte/inapoi functioneaza.
Playerul crede ca citeste de pe un disc local si nu se mai blocheaza.
"""

import base64
import os
import re
import threading
import time

try:
    import urllib.request as _urlreq
except ImportError:  # Python 2
    import urllib2 as _urlreq

try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
except ImportError:  # Python 2
    from BaseHTTPServer import BaseHTTPRequestHandler
    from SocketServer import ThreadingMixIn, TCPServer

    class ThreadingHTTPServer(ThreadingMixIn, TCPServer):
        daemon_threads = True
        allow_reuse_address = True

try:
    import xbmc
    import xbmcvfs
except ImportError:  # teste in afara Kodi
    class _Dummy(object):
        LOGINFO = 1
        LOGWARNING = 2
        LOGERROR = 3

        def log(self, *a, **k):
            pass

        def sleep(self, ms):
            time.sleep(ms / 1000.0)

        def translatePath(self, p):
            return p

    xbmc = _Dummy()
    xbmcvfs = _Dummy()


USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

HTTP_TIMEOUT = 40                # secunde pentru o cerere catre sursa
BLOCK_SIZE = 512 * 1024          # cat trimitem o data catre player
FETCH_CHUNK = 16 * 1024 * 1024   # cat cerem o data de la sursa
MIN_FETCH = 4 * 1024 * 1024      # minim descarcat cand cineva cere o zona noua
TAIL_MIN = 8 * 1024 * 1024       # coada minima descarcata (acolo e indexul moov)
TAIL_MAX = 48 * 1024 * 1024      # coada maxima descarcata
LEAD_BYTES = 32 * 1024 * 1024    # cat descarcam inaintea playerului
PARALLEL_CHUNK = 16 * 1024 * 1024  # bucata pentru un fir de descarcare
FETCH_WORKERS = 1                # fire care descarca liniar in urma capului
WAIT_TOTAL = 45                  # cat asteptam dimensiunea fisierului
PLAYBACK_START_TIMEOUT = 120     # cat asteptam sa inceapa sa fie citit filmul
PLAYBACK_IDLE_TIMEOUT = 90       # cat asteptam dupa ultima citire inainte de a inchide
PLAYBACK_MAX = 8 * 3600          # durata maxima cat tinem proxy-ul viu
PROXY_PREFIX = 'cinemateca_'


def _log(message, level=1):
    try:
        xbmc.log('[Cinemateca/stream] ' + message, level)
    except Exception:
        pass


def tail_size(total):
    """Coada de descarcat: indexul moov ocupa cam 1% din fisier."""
    if not total:
        return TAIL_MIN
    return max(TAIL_MIN, min(TAIL_MAX, int(total) // 100))


def tail_zone(total):
    """
    Zona de la finalul fisierului de unde playerul citeste INDEXUL filmului
    (cutia moov), nu filmul in sine. Citirile de acolo nu ne spun cat a
    avansat utilizatorul, deci nu trebuie sa miste limita de descarcare.
    """
    if not total:
        return TAIL_MIN
    return max(TAIL_MIN, int(total) // 50)


# ---------------------------------------------------------------------------
# Fisier temporar
# ---------------------------------------------------------------------------
def temp_dir():
    for special in ('special://temp/', 'special://masterprofile/'):
        try:
            path = xbmcvfs.translatePath(special)
        except AttributeError:
            try:
                path = xbmc.translatePath(special)
            except Exception:
                path = ''
        if path and os.path.isdir(path):
            return path
    return os.environ.get('TEMP') or os.environ.get('TMPDIR') or '/tmp'


def cleanup_stale(max_age=86400):
    """Sterge fisierele ramase de la redari mai vechi."""
    try:
        folder = temp_dir()
        now = time.time()
        for name in os.listdir(folder):
            if not name.startswith(PROXY_PREFIX) or not name.endswith('.mp4'):
                continue
            path = os.path.join(folder, name)
            try:
                if now - os.path.getmtime(path) > max_age:
                    os.remove(path)
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cache-ul local: un fisier pe disc + intervalele deja descarcate
# ---------------------------------------------------------------------------
class MediaCache(object):
    def __init__(self, url, path, total=0):
        self.url = url
        self.path = path
        self.lock = threading.RLock()
        self.cond = threading.Condition(self.lock)
        self.ranges = []          # intervale complete: [(start, end), ...] (end exclusiv)
        self.pending = []         # intervale in curs de descarcare
        self.total = int(total or 0)   # dimensiunea fisierului (0 = necunoscuta)
        self.error = ''
        self.stop = False
        self.play_head = 0        # cel mai mare offset cerut de player
        self.last_serve = 0.0     # cand a fost servita ultima bucata catre player
        self.served_bytes = 0     # cati bytes au plecat catre player
        self._file = None
        self._next_offset = 0
        self._head_done = False

    # ---------------------------------------------------------------- fisier
    def _handle(self):
        if self._file is None:
            self._file = open(self.path, 'r+b')
        return self._file

    def read(self, offset, length):
        with self.lock:
            try:
                handle = self._handle()
                handle.seek(offset)
                return handle.read(length)
            except Exception:
                return b''

    def _write_at(self, offset, data):
        handle = self._handle()
        handle.seek(offset)
        handle.write(data)

    # ------------------------------------------------------------- intervale
    def _covered(self, start, end):
        for a, b in self.ranges:
            if a <= start and end <= b:
                return True
        return False

    def _overlaps_pending(self, start, end):
        for a, b in self.pending:
            if start < b and a < end:
                return True
        return False

    def _add_range(self, start, end):
        merged = []
        for a, b in sorted(self.ranges + [(start, end)]):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        self.ranges = merged

    def contiguous_prefix(self):
        """Cati bytes sunt descarcati fara intrerupere de la inceputul fisierului."""
        end = 0
        for a, b in self.ranges:
            if a > end:
                break
            if b > end:
                end = b
        return end

    def mark_head(self, offset):
        with self.lock:
            if offset > self.play_head:
                self.play_head = offset

    def wait_total(self, timeout=WAIT_TOTAL):
        deadline = time.time() + timeout
        with self.lock:
            while not self.total and not self.error and time.time() < deadline:
                self.cond.wait(0.4)
            return self.total

    # -------------------------------------------------------------- descarcare
    def fetch(self, start, end):
        """Se asigura ca [start, end) exista in fisier. Intoarce True/False."""
        if end <= start:
            return True
        with self.lock:
            if self._covered(start, end):
                return True
            if self._overlaps_pending(start, end):
                deadline = time.time() + HTTP_TIMEOUT * 3
                while time.time() < deadline:
                    if self._covered(start, end):
                        return True
                    if not self.pending:
                        break
                    self.cond.wait(0.5)
                if self._covered(start, end):
                    return True
            self.pending.append((start, end))
        try:
            return self._download(start, end)
        finally:
            with self.lock:
                self.pending = [item for item in self.pending if item != (start, end)]
                self.cond.notify_all()

    def _download(self, start, end):
        headers = {'User-Agent': USER_AGENT,
                   'Accept': '*/*',
                   'Range': 'bytes=%d-%d' % (start, end - 1)}
        try:
            request = _urlreq.Request(self.url, headers=headers)
            response = _urlreq.urlopen(request, timeout=HTTP_TIMEOUT)
        except Exception as exc:
            self.error = 'sursa nu raspunde (%s)' % exc
            _log('Eroare la sursa: %s' % exc, 2)
            return False

        status = getattr(response, 'status', None) or getattr(response, 'code', 200)
        content_range = response.headers.get('Content-Range') if hasattr(response, 'headers') else None
        total = 0
        if content_range:
            match = re.search(r'/(\d+)\s*$', content_range)
            if match:
                total = int(match.group(1))
        if not total:
            length = response.headers.get('Content-Length') if hasattr(response, 'headers') else None
            try:
                if status == 200 and length:
                    total = int(length)
            except Exception:
                total = 0
        if total:
            with self.lock:
                if not self.total:
                    self.total = total
                    _log('Fisier de %d bytes.' % total, 1)
                elif self.total != total:
                    _log('Dimensiune corectata: %d -> %d.' % (self.total, total), 2)
                    self.total = total
                self.cond.notify_all()

        if status == 200 and start > 0:
            # sursa a ignorat Range: nu putem citi aleatoriu
            self.error = 'sursa nu accepta Range'
            _log('Sursa a ignorat cererea Range.', 2)
            try:
                response.close()
            except Exception:
                pass
            return False

        offset = start
        try:
            while offset < end and not self.stop:
                data = response.read(min(BLOCK_SIZE, end - offset))
                if not data:
                    break
                with self.lock:
                    self._write_at(offset, data)
                    self._add_range(offset, offset + len(data))
                    self.cond.notify_all()
                offset += len(data)
        except Exception as exc:
            _log('Descarcare intrerupta la %d: %s' % (offset, exc), 2)
        finally:
            try:
                response.close()
            except Exception:
                pass
        return offset >= end

    # --------------------------------------------------------- ce cere playerul
    def ensure(self, start, length):
        """Se asigura ca bucata ceruta de player e disponibila (o descarca daca nu)."""
        end = start + length
        with self.lock:
            if self._covered(start, end):
                return True
            total = self.total
        fetch_end = start + max(end - start, MIN_FETCH)
        fetch_end = min(fetch_end, start + FETCH_CHUNK)
        if total:
            fetch_end = min(fetch_end, total)
        if self.fetch(start, fetch_end):
            return True
        deadline = time.time() + 15
        while time.time() < deadline:
            with self.lock:
                if self._covered(start, end):
                    return True
            time.sleep(0.3)
        return False

    # ------------------------------------------------------------- prefetch
    def start_prefetch(self):
        thread = threading.Thread(target=self._prefetch)
        thread.daemon = True
        thread.start()

    def _prefetch(self):
        # Capul si coada se descarca in PARALEL: sursa raspunde in 4-8 secunde
        # pentru fiecare cerere, iar limita ei e pe conexiune (masurat: 3 fire
        # simultane dau doar ~8% mai mult debit). Doua cereri pornite in acelasi
        # timp termina in timpul uneia singure secventiale - exact ce conteaza
        # pentru intarzierea de pornire.
        head = threading.Thread(target=self._prefetch_head)
        head.daemon = True
        head.start()

        if not self.total:
            self.wait_total(WAIT_TOTAL)
        total = self.total
        if not total:
            return
        _log('Descarc capul si coada (%d bytes) in paralel.' % total, 0)

        for _ in range(max(1, FETCH_WORKERS)):
            worker = threading.Thread(target=self._worker, args=(total,))
            worker.daemon = True
            worker.start()

        # coada fisierului: acolo e indexul moov al filmelor MP4
        self.fetch(max(0, total - tail_size(total)), total)
        _log('Coada fisierului este disponibila.', 0)

    def _prefetch_head(self):
        try:
            self.fetch(0, min(MIN_FETCH, self.total or MIN_FETCH))
        finally:
            with self.lock:
                self._head_done = True
                self.cond.notify_all()

    def _worker(self, total):
        # nu descarcam de doua ori inceputul: asteptam capul fisierului
        while not self.stop and not self._head_done:
            time.sleep(0.3)
        if self.stop:
            return
        with self.lock:
            self._next_offset = max(self._next_offset, self.contiguous_prefix())
        while not self.stop:
            with self.lock:
                start = self._next_offset
                if start >= total:
                    return
                end = min(start + PARALLEL_CHUNK, total)
                self._next_offset = end
            # nu descarcam prea departe inaintea playerului
            while not self.stop and start > self.play_head + LEAD_BYTES:
                time.sleep(0.4)
            if self.stop:
                return
            if not self.fetch(start, end):
                if self.error:
                    return
                with self.lock:
                    # dam bucata inapoi, ca sa o reincerce altcineva
                    if self._next_offset == end:
                        self._next_offset = start
                time.sleep(1.5)


# ---------------------------------------------------------------------------
# Serverul HTTP local
# ---------------------------------------------------------------------------
def _handler_class(cache):

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'RomyLiveCinemateca'

        def log_message(self, fmt, *args):
            pass

        def do_HEAD(self):
            self._serve(True)

        def do_GET(self):
            self._serve(False)

        def _serve(self, head_only):
            total = cache.wait_total(WAIT_TOTAL)
            if not total:
                try:
                    self.send_error(504, 'Sursa nu raspunde')
                except Exception:
                    pass
                return

            start, end, status = 0, total - 1, 200
            requested_range = None
            raw_range = (self.headers.get('Range') or '').strip()
            _log('Cerere de la player: Range=%r' % (raw_range or '(fara)'), 0)
            match = re.match(r'bytes=(\d*)-(\d*)\s*\Z', raw_range)
            if match:
                requested_range = match
                first, last = match.group(1), match.group(2)
                if first == '' and last:
                    start = max(0, total - int(last))
                    end = total - 1
                else:
                    start = int(first)
                    end = int(last) if last else total - 1
                end = min(end, total - 1)
                if start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', 'bytes */%d' % total)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                status = 206

            length = end - start + 1
            try:
                self.send_response(status)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(length))
                if status == 206:
                    self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, total))
                self.end_headers()
            except Exception:
                return
            if head_only:
                return

            # Cererea deschisa (fara limita de sus) nu inseamna ca playerul vrea
            # tot fisierul deodata: raportam consumul real, bucata cu bucata, ca
            # descarcarea din fundal sa nu o ia inainte degeaba. Citirile din
            # coada (indexul moov) sunt ignorate: acolo sare playerul imediat.
            open_ended = (requested_range is None) or (requested_range.group(2) == '')
            counts = start < total - tail_zone(total)
            if not open_ended and counts:
                cache.mark_head(end + 1)

            position = start
            while position <= end and not cache.stop:
                want = min(BLOCK_SIZE, end - position + 1)
                if not cache.ensure(position, want):
                    break
                data = cache.read(position, want)
                if not data:
                    break
                try:
                    self.wfile.write(data)
                except Exception:
                    return
                position += len(data)
                with cache.lock:
                    cache.last_serve = time.time()
                    cache.served_bytes += len(data)
                if open_ended and counts:
                    cache.mark_head(position)
            try:
                self.wfile.flush()
            except Exception:
                pass

    return Handler


def start(url, folder=None, total=0):
    """Porneste serverul local. Intoarce (cache, httpd, port); (None, None, 0) la eroare."""
    folder = folder or temp_dir()
    path = os.path.join(folder, '%s%d.mp4' % (PROXY_PREFIX, int(time.time() * 1000)))
    try:
        open(path, 'wb').close()
    except Exception as exc:
        _log('Nu pot crea fisierul temporar: %s' % exc, 2)
        return None, None, 0

    cache = MediaCache(url, path, total)
    try:
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), _handler_class(cache))
    except Exception as exc:
        _log('Nu pot porni serverul local: %s' % exc, 2)
        try:
            os.remove(path)
        except Exception:
            pass
        return None, None, 0

    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': 0.2})
    thread.daemon = True
    thread.start()
    cache.start_prefetch()
    _log('Proxy local pornit pe portul %d pentru %s (declarat: %s bytes)'
         % (port, url, total or 'necunoscut'), 1)
    return cache, httpd, port


def stop(cache, httpd, delete=True):
    if cache:
        cache.stop = True
    if httpd:
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
    if cache:
        try:
            if cache._file:
                cache._file.close()
                cache._file = None
        except Exception:
            pass
        if delete:
            try:
                os.remove(cache.path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Redarea propriu-zisa (apelata din plugin)
# ---------------------------------------------------------------------------
def play(handle, film_url, name='', total=0, log=None):
    """Rezolva filmul catre proxy-ul local si porneste redarea."""

    import xbmcgui
    import xbmcplugin

    cleanup_stale()

    listitem = xbmcgui.ListItem(name or '')
    try:
        listitem.setPath(film_url)
        listitem.setProperty('IsPlayable', 'true')
    except Exception:
        pass

    cache = httpd = None
    local_url = ''
    try:
        cache, httpd, port = start(film_url, total=total)
        if port:
            local_url = 'http://127.0.0.1:%d/film.mp4' % port
            listitem.setPath(local_url)
    except Exception as exc:
        _log('Proxy indisponibil (%s); redare directa.' % exc, 2)

    xbmcplugin.setResolvedUrl(handle, True, listitem)

    if not local_url:
        return
    try:
        _wait_for_playback(cache)
    except Exception:
        pass
    stop(cache, httpd, True)


def _wait_for_playback(cache, start_timeout=PLAYBACK_START_TIMEOUT,
                       idle_timeout=PLAYBACK_IDLE_TIMEOUT):
    """
    Tine proxy-ul viu cat timp filmul ruleaza.
    Nu ne bazam doar pe xbmc.Player().isPlaying(): daca playerul nu raporteaza
    corect (sau reda din buffer), ne uitam si daca proxy-ul e citit in continuare.
    """
    player = xbmc.Player()
    deadline = time.time() + PLAYBACK_MAX
    started = False
    idle = 0.0
    while time.time() < deadline and not cache.stop:
        playing = False
        try:
            playing = bool(player.isPlaying())
        except Exception:
            playing = False
        with cache.lock:
            served = cache.last_serve
        fresh = bool(served) and (time.time() - served) < 6
        if playing or fresh:
            started = True
            idle = 0.0
        else:
            idle += 2.0
            if started and idle >= idle_timeout:
                _log('Redarea s-a terminat; opresc proxy-ul.', 1)
                break
            if not started and idle >= start_timeout:
                _log('Playerul nu a cerut filmul; opresc proxy-ul.', 2)
                break
        time.sleep(2)
    else:
        if cache.stop:
            return
        _log('Durata maxima de redare atinsa; opresc proxy-ul.', 2)


# ---------------------------------------------------------------------------
# Utilitar: decodarea linkului de redare trimis de modulul Cinemateca
# ---------------------------------------------------------------------------
def decode_payload(payload):
    """base64(url|dimensiune) -> (url, dimensiune). Intoarce ('', 0) la eroare."""
    if not payload:
        return '', 0
    try:
        text = payload
        padding = len(text) % 4
        if padding:
            text += '=' * (4 - padding)
        raw = base64.urlsafe_b64decode(text.encode('ascii'))
        try:
            raw = raw.decode('utf-8')
        except Exception:
            raw = raw.decode('latin-1')
        url, _, size = raw.partition('|')
        try:
            size = int(size or 0)
        except Exception:
            size = 0
        return url, size
    except Exception:
        return '', 0
