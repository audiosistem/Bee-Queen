# -*- coding: utf-8 -*-
from __future__ import annotations
import datetime
import json
import os
import sys
import time
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import resolveurl
import threading
from resources.lib import subtitles, db
from resources.lib.tmdb_bridge import movies, tv, get_english_title
from resources.lib.resolvers import primesrc
from resources.lib.resolvers import torrentio, torrentdb, mediafusion, comet, perflix, thrax
from resources.lib.resolvers import velaflow as velaflow_resolver
from resources.lib.resolvers import filelist as filelist_resolver
from resources.lib.resolvers import okru as okru_resolver
from resources.lib.resolvers import flixer, vixsrc as vixsrc_resolver, hdhub, webtor as webtor_resolver
from resources.lib.resolvers import penguplay as penguplay_resolver
from resources.lib.resolvers import voe as voe_resolver
from resources.lib.resolvers import doodstream as doodstream_resolver
from resources.lib.resolvers import webstreamr, vidrock
from resources.lib.resolvers import hydrahd as hydrahd_resolver
from resources.lib.resolvers import primesrcme as primesrcme_resolver
from resources.lib.resolvers import vidmoly as vidmoly_resolver
from resources.lib.resolvers import telegram as telegram_resolver
from resources.lib.resolvers import abysscdn as abysscdn_resolver
from resources.lib.resolvers import vsembed as vsembed_resolver
from resources.lib.resolvers import multiembed as multiembed_resolver
from resources.lib.resolvers import pelispanda as pelispanda_resolver
from resources.lib.resolvers import sooti as sooti_resolver
from resources.lib.resolvers import cinesu as cinesu_resolver
from resources.lib.resolvers import vidapi as vidapi_resolver
from resources.lib.tmdb_bridge import get_external_ids
from resources.lib import dialogs
from resources.lib.dialogs import enrich_source, sort_sources, show_source_dialog, run_resolving_dialog
try:
    from torrent_engine import TorrentEngine, TorrentEngineError, LtStreamStatus
    _LIBTORRENT_AVAILABLE = True
except ImportError:
    _LIBTORRENT_AVAILABLE = False

addon = xbmcaddon.Addon('plugin.video.samusxui')
handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1

profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
subs_path = os.path.join(profile_path, 'subs')
os.makedirs(subs_path, exist_ok=True)
_AUTOPLAY_CACHE_FILE = os.path.join(profile_path, 'autoplay_cache.json')

# Singleton TorrentEngine (libtorrent) — creat la primul torrent, reutilizat
_lt_engine: TorrentEngine | None = None
_lt_engine_lock = threading.Lock()
_lt_cleanup_player = None  # referință persistentă la _TorrentCleanup (evită GC)
_ts_cleanup_player = None  # referință persistentă la _TorrServerCleanup (evită GC)
_ts_local_server = None   # instanță LocalServer (TorrServer incorporat)

# Timeout-uri individuale per resolver (secunde) — None = limitat doar de budget global
_RT = {
    'vsembed':      8,
    'hydrahd':      8,
}

# Trackere publice fallback — adăugate în magnet dacă sursa nu include trackere
_FALLBACK_TRACKERS = [
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:80/announce",
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://exodus.desync.com:6969/announce",
]


def prestart_torrent_engine():
    """Pre-pornește motorul torrent configurat în background — apelat din HomeWindow.onInit."""
    engine = addon.getSetting('torrent_engine') or 'TorrServer'
    if engine == 'TorrServer':
        mode = addon.getSetting('torrserver_mode') or 'Extern'
        if 'Auto' not in mode and 'incorporat' not in mode:
            return  # Extern — rulează pe altă mașină, nu pornim local
        try:
            from torrserve_stream import LocalServer
            global _ts_local_server
            if _ts_local_server is None:
                _ts_local_server = LocalServer()
            _ts_local_server.ensure_running()
            xbmc.log('[Samus/prestart] TorrServer local pornit', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[Samus/prestart] TorrServer eroare: {e}', xbmc.LOGWARNING)
    elif engine == 'libtorrent':
        if not _LIBTORRENT_AVAILABLE:
            return
        try:
            global _lt_engine
            with _lt_engine_lock:
                if _lt_engine is None:
                    save_path = os.path.join(profile_path, 'torrent_cache')
                    os.makedirs(save_path, exist_ok=True)
                    _cleanup_torrent_cache(save_path)
                    _lt_engine = TorrentEngine(save_path)
            xbmc.log('[Samus/prestart] libtorrent engine inițializat', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[Samus/prestart] libtorrent eroare: {e}', xbmc.LOGWARNING)


def resolve_with_timeout(url, timeout=30):
    result = [None]

    def resolver():
        try:
            resolved_url = resolveurl.resolve(url)
            result[0] = resolved_url
        except Exception as e:
            xbmc.log(f"[Samus/resolveurl] Eroare: {e}", xbmc.LOGERROR)

    t = threading.Thread(target=resolver)
    t.start()
    t.join(timeout)
    if t.is_alive():
        xbmc.log(f"[Samus/resolveurl] Timeout {timeout}s pentru URL: {url}", xbmc.LOGERROR)
        return None
    return result[0]


def _quote_http_url_for_kodi(url):
    """Percent-encode HTTP(S) paths so Kodi/libcurl does not reject spaces/brackets."""
    if not url or not isinstance(url, str):
        return url
    base, sep, headers = url.partition('|')
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ('http', 'https'):
        return url
    quoted = urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc,
        urllib.parse.quote(parts.path, safe='/%'),
        urllib.parse.quote(parts.query, safe='=&%:+'),
        urllib.parse.quote(parts.fragment, safe='=&%:+'),
    ))
    return quoted + (sep + headers if sep else '')


def _has_non_latin(text):
    """Returnează True dacă textul conține litere non-latine (ex: chirilice)."""
    return any(ord(c) > 591 and c.isalpha() for c in text)


def _torrent_timeout(seeds):
    """Timeout adaptiv bazat pe numărul de seederi."""
    if seeds is None:
        return 90
    if seeds >= 100:
        return 30
    if seeds >= 20:
        return 60
    return 120  # puțini seederi — așteptăm mai mult


def resolve_torrent(info_hash, file_idx=0, trackers=None, seeds=None, size=None, quality=None, status_cb=None, stats_cb=None, torrent_file=None, file_name=None, title=None, poster=None):
    engine_setting = addon.getSetting('torrent_engine') or 'TorrServer'
    if engine_setting == 'libtorrent':
        return resolve_torrent_libtorrent(info_hash, file_idx, trackers, seeds, status_cb=status_cb, stats_cb=stats_cb, torrent_file=torrent_file)
    return resolve_torrent_torrserver(info_hash, file_idx, trackers, seeds, status_cb=status_cb, stats_cb=stats_cb, torrent_file=torrent_file, file_name=file_name, title=title, poster=poster)





def resolve_torrent_torrserver(info_hash, file_idx=0, trackers=None, seeds=None, status_cb=None, stats_cb=None, torrent_file=None, file_name=None, title=None, poster=None):
    def _status(msg):
        xbmc.log(f'[Samus/TorrServer] {msg}', xbmc.LOGINFO)
        if status_cb:
            status_cb(msg)

    try:
        from torrserve_stream import Engine, LocalServer

        mode = addon.getSetting('torrserver_mode') or 'Extern'
        if 'Auto' in mode or 'incorporat' in mode:
            global _ts_local_server
            if _ts_local_server is None:
                _ts_local_server = LocalServer()
            _status('Se pornește TorrServer local...')
            _ts_local_server.ensure_running()
            host, port, auth, use_https = '127.0.0.1', _ts_local_server.port, None, False
            save_in_db = False
        else:
            from torrserve_stream.settings import Settings
            s = Settings()
            host, port, auth, use_https = s.host, s.port, s.auth, s.use_https
            save_in_db = s.save_in_database

        _status('Se conectează la TorrServer...')
        def _ts_log(msg):
            xbmc.log(f'[Samus/TorrServer/engine] {msg}', xbmc.LOGDEBUG)
        engine_kwargs = dict(host=host, port=port, auth=auth,
                             use_https=use_https, save_in_database=save_in_db,
                             log=_ts_log)
        if torrent_file and os.path.exists(torrent_file):
            e = Engine(path=torrent_file, **engine_kwargs)
        else:
            tr_params = ''.join(f"&tr={t[len('tracker:'):]}" for t in (trackers or []) if t.startswith('tracker:'))
            magnet = f"magnet:?xt=urn:btih:{info_hash}{tr_params}"
            e = Engine(uri=magnet, title=title, poster=poster, **engine_kwargs)
        if not e.success:
            xbmcgui.Dialog().notification('Samus', 'TorrServer indisponibil', xbmcgui.NOTIFICATION_ERROR, 3000)
            return None
        # Dacă avem numele fișierului, folosim get_ts_index pentru a găsi
        # indexul corect în lista TorrServer (care poate sorta diferit față de bencode).
        ts_idx = file_idx
        if file_name:
            found = e.get_ts_index(file_name)
            if found is not None:
                ts_idx = found
                xbmc.log(f'[Samus/TorrServer] get_ts_index({file_name!r}) → {ts_idx}', xbmc.LOGINFO)
            else:
                xbmc.log(f'[Samus/TorrServer] get_ts_index({file_name!r}) → None, folosim fileIdx={file_idx}', xbmc.LOGWARNING)

        _status('Se pornește preîncărcarea...')
        e.start(ts_idx)
        # Așteptăm max 60s ca TorrServer să aibă date disponibile
        # TorrentStatus: 0=idle, 1=hash, 2=preload, 3=working, 4=finished, 5=closed
        READY = {3, 4, 5}
        _STATUS_STR = {0: 'Inactiv', 1: 'Hash', 2: 'Preîncărcare', 3: 'Activ', 4: 'Finalizat', 5: 'Închis'}
        # Mod pornire: Normal=așteaptă status 3, Rapid=iese la pct≥100%, Imediat=iese la status 2
        start_mode  = addon.getSetting('torrserver_start_mode') or 'Normal'
        total_polls = 0
        ready_polls = 0
        last_loaded = 0
        last_speed_dl = 0
        last_seeders = 0
        last_peers = 0
        for _ in range(60):
            try:
                st        = e.stat()
                ts        = st.get('TorrentStatus', 0)
                speed_dl  = st.get('DownloadSpeed', 0)
                speed_ul  = st.get('UploadSpeed', 0)
                seeders   = st.get('ConnectedSeeders', 0)
                peers     = st.get('ActivePeers', 0)
                loaded    = st.get('LoadedSize', 0)
                pre_done  = st.get('PreloadedBytes', 0)
                pre_total = st.get('PreloadSize', 0)
                progress  = int(pre_done * 100 / pre_total) if pre_total > 0 else 0
                last_loaded = loaded; last_speed_dl = speed_dl
                last_seeders = seeders; last_peers = peers
                xbmc.log(f'[Samus/TorrServer] stat: ts={ts} dl={speed_dl:.0f} ul={speed_ul:.0f} '
                         f'seeds={seeders} peers={peers} loaded={loaded} '
                         f'pre={pre_done}/{pre_total} pct={progress}', xbmc.LOGINFO)
                _status(f'Se bufferează... {_STATUS_STR.get(ts, ts)}')
                if stats_cb:
                    stats_cb(speed_dl=speed_dl, speed_ul=speed_ul, seeders=seeders,
                             peers=peers, loaded=loaded, progress=progress)
                has_data = loaded > 0 or speed_dl > 0
                is_ready = ts in READY and has_data
                is_ready |= start_mode == 'Rapid (pct≥100%)' and ts == 2 and progress >= 100
                is_ready |= start_mode == 'Imediat (status=2)' and ts >= 2
                # Fallback după 30s chiar dacă n-am date — TorrServer poate sluji unele formate direct
                is_ready |= ts in READY and total_polls >= 30
                if is_ready:
                    ready_polls += 1
                    extra_needed = 3 if total_polls > 1 else 0
                    if ready_polls > extra_needed:
                        break
                # Dacă după 20s nu avem niciun peer și nicio dată, nu are sens să mai așteptăm
                if total_polls >= 20 and last_loaded == 0 and last_speed_dl == 0 and last_peers == 0:
                    xbmc.log('[Samus/TorrServer] Niciun peer sau date după 20s — abandon', xbmc.LOGWARNING)
                    xbmcgui.Dialog().notification('Samus', 'TorrServer: niciun peer disponibil', xbmcgui.NOTIFICATION_WARNING, 5000)
                    return None
            except Exception as ex:
                xbmc.log(f'[Samus/TorrServer] stat eroare: {ex}', xbmc.LOGWARNING)
            xbmc.sleep(1000)
            total_polls += 1
        # Nu încercăm redarea dacă TorrServer nu a descărcat nimic
        if last_loaded == 0 and last_speed_dl == 0:
            xbmc.log('[Samus/TorrServer] Timeout fără date — niciun peer conectat', xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('Samus', 'TorrServer: niciun peer disponibil', xbmcgui.NOTIFICATION_WARNING, 5000)
            return None
        _status('Se obține adresa de stream...')
        url = e.play_url(ts_idx)
        global _ts_cleanup_player
        _ts_cleanup_player = _TorrServerCleanup(e, save_in_db)
        return url
    except ImportError:
        xbmcgui.Dialog().notification('Samus', 'Modulul torrserver lipsește', xbmcgui.NOTIFICATION_ERROR, 3000)
        return None
    except Exception as ex:
        xbmc.log(f'[Samus/TorrServer] Eroare: {ex}', xbmc.LOGERROR)
        return None


_VIDEO_EXT = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts',
              '.wmv', '.flv', '.m2ts', '.mpg', '.mpeg', '.webm'}
_CACHE_MAX_AGE_DAYS = 7


def _cleanup_torrent_cache(save_path):
    """Șterge fișierele din cache mai vechi de CACHE_MAX_AGE_DAYS zile."""
    try:
        cutoff = time.time() - _CACHE_MAX_AGE_DAYS * 86400
        for entry in os.scandir(save_path):
            if entry.stat().st_mtime < cutoff:
                if entry.is_dir():
                    import shutil
                    shutil.rmtree(entry.path, ignore_errors=True)
                else:
                    os.remove(entry.path)
                xbmc.log(f'[Samus/libtorrent] Cache cleanup: {entry.name}', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[Samus/libtorrent] Cache cleanup eroare: {e}', xbmc.LOGWARNING)


def _pick_best_file(engine, tid):
    """Returnează file_idx al celui mai mare fișier video din torrent."""
    files = engine.get_files(tid)
    best_idx, best_size = 0, -1
    for f in files:
        name = f.name.decode('utf-8', errors='replace') if isinstance(f.name, bytes) else f.name
        ext = os.path.splitext(name)[-1].lower()
        if ext in _VIDEO_EXT and f.size > best_size:
            best_size = f.size
            best_idx = f.index
    return best_idx


class _TorrServerCleanup(xbmc.Player):
    """Monitor playback — elimină torrentul din TorrServer când redarea se termină."""

    def __init__(self, engine, save_in_db):
        super().__init__()
        self._engine   = engine
        self._save_in_db = save_in_db
        self._cleaned  = False

    def _cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        try:
            if self._save_in_db:
                self._engine.drop()
                xbmc.log('[Samus/TorrServer] Torrent drop (păstrat în DB)', xbmc.LOGINFO)
            else:
                self._engine.rem()
                xbmc.log('[Samus/TorrServer] Torrent eliminat după redare', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[Samus/TorrServer] Cleanup eroare: {e}', xbmc.LOGWARNING)

    def onPlayBackStopped(self):  self._cleanup()
    def onPlayBackEnded(self):    self._cleanup()
    def onPlayBackError(self):    self._cleanup()


class _TorrentCleanup(xbmc.Player):
    """Monitor playback — elimină torrentul din engine când redarea se termină."""

    def __init__(self, engine, tid, sid):
        super().__init__()
        self._engine = engine
        self._tid = tid
        self._sid = sid
        self._cleaned = False

    def _cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        try:
            self._engine.stop_stream(self._sid)
            self._engine.remove_torrent(self._tid, delete_files=True)
            xbmc.log(f'[Samus/libtorrent] Torrent {self._tid} eliminat după redare', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[Samus/libtorrent] Cleanup eroare: {e}', xbmc.LOGWARNING)

    def onPlayBackStopped(self):  self._cleanup()
    def onPlayBackEnded(self):    self._cleanup()
    def onPlayBackError(self):    self._cleanup()


def resolve_torrent_libtorrent(info_hash, file_idx=0, trackers=None, seeds=None, status_cb=None, stats_cb=None, torrent_file=None):
    if not _LIBTORRENT_AVAILABLE:
        xbmcgui.Dialog().notification('Samus', 'script.module.libtorrent lipsește', xbmcgui.NOTIFICATION_ERROR, 4000)
        return None

    global _lt_engine

    def _status(msg):
        xbmc.log(f'[Samus/libtorrent] {msg}', xbmc.LOGINFO)
        if status_cb:
            status_cb(msg)

    def _push_torrent_stats(st, progress=None):
        if not stats_cb or not st:
            return
        pct = int((progress if progress is not None else st.progress) * 100)
        stats_cb(speed_dl=st.download_rate, speed_ul=st.upload_rate,
                 seeders=st.num_seeds, peers=st.num_peers,
                 loaded=st.total_done, progress=pct)

    try:
        is_new_engine = False
        with _lt_engine_lock:
            if _lt_engine is None:
                _status('Se inițializează motorul libtorrent...')
                save_path = os.path.join(profile_path, 'torrent_cache')
                os.makedirs(save_path, exist_ok=True)
                _cleanup_torrent_cache(save_path)
                _lt_engine = TorrentEngine(save_path)
                is_new_engine = True

        engine = _lt_engine

        if is_new_engine:
            _status('DHT bootstrap...')
            # Așteptăm până la 5s fără a bloca UI — poll la 200ms
            for _ in range(25):
                xbmc.sleep(200)

        if torrent_file and os.path.exists(torrent_file):
            _status('Se adaugă fișier .torrent...')
            tid = engine.add_torrent_file(torrent_file)
            if tid < 0:
                xbmc.log(f'[Samus/libtorrent] add_torrent_file eșuat: {engine.last_error()}', xbmc.LOGERROR)
                return None
            # metadata e deja în fișier — așteptăm max 5s
            for _ in range(10):
                st = engine.get_status(tid)
                if st and st.has_metadata:
                    break
                xbmc.sleep(500)
            else:
                xbmc.log('[Samus/libtorrent] Timeout metadata din .torrent', xbmc.LOGERROR)
                engine.remove_torrent(tid, delete_files=True)
                return None
        else:
            tr_list = [t[len('tracker:'):] for t in (trackers or []) if t.startswith('tracker:')]
            if not tr_list:
                tr_list = _FALLBACK_TRACKERS
            tr_params = ''.join(f"&tr={t}" for t in tr_list)
            magnet = f"magnet:?xt=urn:btih:{info_hash}{tr_params}"

            _status('Se adaugă magnet...')
            tid = engine.add_magnet(magnet)
            if tid < 0:
                xbmc.log(f'[Samus/libtorrent] add_magnet eșuat: {engine.last_error()}', xbmc.LOGERROR)
                return None

            _status('Se descarcă metadata...')
            deadline = time.time() + 120
            while time.time() < deadline:
                st = engine.get_status(tid)
                if st and st.has_metadata:
                    break
                if st:
                    _status(f'Se descarcă metadata... ({st.num_peers} peers)')
                    _push_torrent_stats(st, progress=0)
                xbmc.sleep(1000)
            else:
                xbmc.log('[Samus/libtorrent] Timeout metadata', xbmc.LOGERROR)
                engine.remove_torrent(tid, delete_files=True)
                return None

        xbmc.log(f'[Samus/libtorrent] Fișier selectat: index {file_idx}', xbmc.LOGINFO)
        best_idx = file_idx

        _status('Se pornește stream-ul...')
        sid = engine.start_stream(tid, best_idx)
        if sid < 0:
            xbmc.log(f'[Samus/libtorrent] start_stream eșuat: {engine.last_error()}', xbmc.LOGERROR)
            engine.remove_torrent(tid, delete_files=True)
            return None

        # Așteptăm max 3s ca HTTP server-ul să fie gata
        deadline = time.time() + 3
        ss = None
        while time.time() < deadline:
            ss = engine.get_stream_status(sid)
            if ss and ss.url and ss.url[0:1] not in (b'', b'\x00'):
                break
            xbmc.sleep(200)

        if not ss or not ss.url:
            xbmc.log('[Samus/libtorrent] URL stream indisponibil', xbmc.LOGERROR)
            engine.stop_stream(sid)
            engine.remove_torrent(tid, delete_files=True)
            return None

        url = ss.url.split(b'\x00')[0].decode('utf-8') if isinstance(ss.url, bytes) else ss.url.rstrip('\x00')
        xbmc.log(f'[Samus/libtorrent] URL stream: {url}', xbmc.LOGINFO)

        # Faza de buffering — poll până stream_state=READY
        # Extra polls pentru stats doar dacă a existat buffering real
        total_lt_polls = 0
        ready_lt_polls = 0
        for _ in range(60):
            ss2 = engine.get_stream_status(sid)
            st2 = engine.get_status(tid)
            if ss2 and st2:
                file_size = ss2.file_size or 0
                read_head = ss2.read_head or 0
                pct = int(read_head * 100 / file_size) if file_size > 0 else 0
                dl = ss2.download_rate or st2.download_rate
                peers = st2.num_peers or ss2.active_peers
                xbmc.log(f'[Samus/libtorrent] stream: state={ss2.stream_state} '
                         f'buf={ss2.buffer_seconds:.1f}s dl={dl} peers={peers} pct={pct}', xbmc.LOGINFO)
                if stats_cb:
                    stats_cb(speed_dl=dl, speed_ul=st2.upload_rate,
                             seeders=st2.num_seeds, peers=peers,
                             loaded=read_head, progress=pct)
                _status(f'Se bufferează... {ss2.buffer_seconds:.1f}s buffer')
                if ss2.stream_state == LtStreamStatus.STREAM_STATE_READY:
                    ready_lt_polls += 1
                    extra_needed = 3 if total_lt_polls > 1 else 0
                    if ready_lt_polls > extra_needed:
                        break
                elif ss2.stream_state == LtStreamStatus.STREAM_STATE_ERROR:
                    xbmc.log('[Samus/libtorrent] Stream error în faza de buffering', xbmc.LOGERROR)
                    break
            xbmc.sleep(1000)
            total_lt_polls += 1

        # Înregistrăm monitorul de cleanup — stocat global ca să nu fie garbage-collected
        global _lt_cleanup_player
        _lt_cleanup_player = _TorrentCleanup(engine, tid, sid)

        return url

    except TorrentEngineError as e:
        xbmcgui.Dialog().notification('Samus', str(e), xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmc.log(f'[Samus/libtorrent] TorrentEngineError: {e}', xbmc.LOGERROR)
        with _lt_engine_lock:
            _lt_engine = None
        return None
    except Exception as e:
        xbmc.log(f'[Samus/libtorrent] Eroare neașteptată: {e}', xbmc.LOGERROR)
        with _lt_engine_lock:
            _lt_engine = None
        return None


_MODULE_TO_PROVIDER = {
    'filelist':      '[FLI]',  'nebulastreams': '[NBS]',
    'stremify':      '[STF]',  'flixnest':      '[FNS]',
    'yastream':      '[YAS]',  'nhdapi':        '[NHD]',
    'sooti':         '[SOT]',  'webstreamr':    '[WSR]',
    'torrentio':     '[TIO]',  'torrentdb':     '[TDB]',
    'mediafusion':   '[MF]',   'comet':         '[CMT]',
    'perflix':       '[PFX]',  'uindex':        '[UDX]',
    'thrax':         '[THX]',  'flixer':        '[FLX]',
    'vixsrc':        '[VXS]',  'hdhub':         '[HDB]',
    'vidrock':       '[VDR]',  'pulpwatch_resolver': '[PLW]',
    'filmehd_resolver': '[FHD]', 'hydrahd_resolver': '[HHD]',
    'videasy_resolver': '[VDY]', 'vsembed_resolver': '[VSE]',
    'yflix_resolver':   '[YFX]', 'pelispanda':   '[PPD]',
    'streamimdb':    '[SIMDB]', 'moviebox':      '[MBX]',
    'popr':          '[PPR]',  'cinesu':        '[CSU]',
    'velaflow':      '[VLF]',  'peachify':      '[PCH]',
    'tulnex':        '[TLX]',  'vidapi':        '[VAP]',
    'goatapi':       '[PDN]',   'webtor':        '[WBT]',
}


def threaded_resolver(target, args=(), result=None, index=0, timeout=None):
    mod = getattr(target, '__module__', '').split('.')[-1]
    provider = _MODULE_TO_PROVIDER.get(mod)

    def wrapper():
        if provider and not db.provider_is_healthy(provider):
            xbmc.log(f'[Samus/health] Skip {provider} (timeout recent)', xbmc.LOGDEBUG)
            result[index] = []
            return
        t0 = time.time()
        try:
            data = target(*args)
            result[index] = data
            n = len(data) if data else 0
            xbmc.log(f"[Samus/timing] {mod}.{target.__name__}: {n} surse în {time.time()-t0:.2f}s", xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f"[Samus] Eroare în {target.__name__}: {e}", xbmc.LOGERROR)
            result[index] = []

    t = threading.Thread(target=wrapper, daemon=True)
    t._resolver_timeout = timeout
    t._provider = provider
    t._result_index = index
    t.start()
    return t


_PROVIDER_NAMES = {
    '[V]':     'Vidify',       '[ES]':    'Stremio',      '[Z]':     'VidZee',
    '[2E]':    '2Embed',       '[TIO]':   'Torrentio',    '[TDB]':   'TorrentDB',
    '[MF]':    'MediaFusion',  '[CMT]':   'Comet',        '[PFX]':   'Peerflix',
    '[UDX]':   'UIndex',       '[THX]':   'Thrax',        '[PSC]':   'Vidsrcme.ru',
    '[FLX]':   'Flixer',       '[VXS]':   'VixSrc',       '[HDB]':   'HDHub',
    '[WSR]':   'WebStreamr',   '[VDR]':   'VidRock',      '[STF]':   'Stremify',
    '[NBS]':   'NebulaStreams', '[FNS]':   'FlixNest',     '[PLW]':   'PulpWatch',
    '[FHD]':   'FilmeHD',      '[HHD]':   'HydraHD',      '[YAS]':   'Yastream',
    '[NHD]':   'NHDAPI',       '[PSM]':   'PrimeSrc.me',  '[VDL]':   'VidLink',
    '[VDY]':   'Videasy',      '[VSE]':   'VSEmbed',      '[YFX]':   'YFlix',
    '[MEB]':   'MultiEmbed',   '[VBT]':   'VidBinge',     '[MAPI]':  'MoviesAPI',
    '[PPD]':   'PelisPanda',   '[SIMDB]': 'StreamIMDb',   '[SOT]':   'Sooti',
    '[MBX]':   'MovieBox',     '[PPR]':   'Popr',        '[CSU]':   'CineSu',
    '[VLF]':   'VelaFlow',    '[FLI]':   'FileList',
    '[PCH]':   'Peachify',
    '[TLX]':   'Tulnex',    '[VAP]':   'VidAPI',
    '[PDN]':   'Pixeldrain',   '[WBT]':   'Webtor',
}


def _build_sources(results, prefixes, tmdb_title=None, tmdb_year=None, tmdb_original_title=None):
    """Convert raw resolver results into a flat sources list."""
    sources = []
    for group, label_prefix in zip(results, prefixes):
        if not group:
            continue
        display_prefix = _PROVIDER_NAMES.get(label_prefix, label_prefix)
        if label_prefix == '[ES]':
            for entry in group.get('sources', []):
                if 'files' in entry:
                    for file in entry['files']:
                        file_url = file.get('file')
                        if not file_url:
                            continue
                        label = file.get('quality', 'Unknown')
                        sources.append({
                            'label': f"{display_prefix} {label}",
                            'url': file_url + "|User-Agent=Mozilla/5.0&Referer=https://embed.su/&Origin=https://embed.su/",
                            'direct': True,
                        })
        elif label_prefix == '[THX]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '')
                # Construim titlul în format release: "Title.Year.Quality" (titlu engleza)
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                entry = {
                    'label':      f"{display_prefix} {src.get('label', '')}".strip(),
                    'title_line': title_line or src.get('label', ''),
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'direct':     src.get('direct', True),
                    'quality':    quality,
                }
                sources.append(entry)
        elif label_prefix in ('[TIO]', '[TDB]', '[MF]', '[CMT]', '[PFX]', '[UDX]', '[PPD]', '[VLF]', '[FLI]'):
            for src in group:
                quality = src.get('quality', '')
                title_line = src.get('title_line', '')
                seeds = src.get('seeds')
                size = src.get('file_size') or src.get('size', '')

                # Dacă titlul conține caractere non-latine, folosim titlul TMDb
                if title_line and _has_non_latin(title_line) and tmdb_title:
                    display_title = tmdb_title
                else:
                    display_title = title_line

                # PPD poate returna și embed-uri (url, direct=False) pe lângă torrente
                if not src.get('is_torrent') and src.get('url'):
                    parts = [p for p in [quality, display_title] if p]
                    label = f"{display_prefix} {' | '.join(parts)}" if parts else display_prefix
                    sources.append({
                        'label': label,
                        'title_line': display_title,
                        'provider': label_prefix,
                        'url': src['url'],
                        'quality': quality,
                        'direct': False,
                    })
                    continue

                parts = [p for p in [quality, display_title] if p]
                meta = []
                if seeds is not None:
                    meta.append(f'👤{seeds}')
                if size:
                    meta.append(f'💾{size}')
                if meta:
                    parts.append(' '.join(meta))

                label = f"{display_prefix} {' | '.join(parts)}" if parts else display_prefix

                _tf = src.get('torrent_file')
                sources.append({
                    'label': label,
                    'title_line': display_title,
                    'provider': label_prefix,
                    'infoHash': src['infoHash'],
                    'fileIdx': src.get('fileIdx', 0),
                    'fileName': src.get('fileName'),
                    'trackers': src.get('trackers', []),
                    'torrent_file': _tf,
                    'seeds': seeds,
                    'size': size,
                    'file_size': size,
                    'is_free': src.get('is_free', ''),
                    'show_freeleech': src.get('show_freeleech', ''),
                    'quality': quality,
                    'is_torrent': True,
                })
        elif label_prefix == '[HDB]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                entry = {
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'size':       src.get('size'),
                    'direct':     True,
                }
                if src.get('subtitles'):
                    entry['subtitles'] = src['subtitles']
                sources.append(entry)
        elif label_prefix == '[WBT]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                entry = {
                    'label':      f"{display_prefix} {title_line or display_name}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     True,
                }
                if src.get('subtitles'):
                    entry['subtitles'] = src['subtitles']
                sources.append(entry)
        elif label_prefix == '[PDN]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                title_line = src.get('title_line', '')
                size = src.get('size', '')
                parts = [p for p in [quality, title_line] if p]
                if size:
                    parts.append(f'💾{size}')
                label = f"{display_prefix} {' | '.join(parts)}" if parts else display_prefix
                sources.append({
                    'label':      label,
                    'title_line': title_line,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'size':       size,
                    'direct':     True,
                })
        elif label_prefix in ('[FLX]', '[VXS]', '[V]', '[Z]', '[WSR]', '[VDR]', '[STF]', '[NBS]', '[FNS]', '[PLW]', '[YAS]', '[NHD]', '[VSE]', '[YFX]', '[SIMDB]', '[SOT]', '[MBX]', '[PPR]', '[CSU]', '[PCH]', '[TLX]'):
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                raw_title = src.get('title_line', '')
                if label_prefix in ('[V]', '[VDR]', '[PLW]') and tmdb_title:
                    title_line = tmdb_title
                    server_name = raw_title
                else:
                    title_line = raw_title
                    server_name = None
                parts = [p for p in [quality, title_line] if p]
                label = f"{display_prefix} {' | '.join(parts)}" if parts else display_prefix
                entry = {
                    'label': label,
                    'title_line': title_line,
                    'provider': label_prefix,
                    'url': url,
                    'quality': quality,
                    'direct': True,
                }
                if server_name:
                    entry['_server_name'] = server_name
                if src.get('subtitles'):
                    entry['subtitles'] = src['subtitles']
                sources.append(entry)
        elif label_prefix in ('[PSC]', '[PSM]'):
            for src in group:
                url = src.get('url') or src.get('link')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                if label_prefix == '[PSC]' and '.m3u8' in url:
                    if '|' not in url:
                        url += "|User-Agent=Mozilla/5.0&Referer=https://cloudnestra.com/"
                    direct = True
                else:
                    direct = src.get('direct', False)
                entry = {
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     direct,
                }
                if src.get('tmdb_id'):
                    entry['tmdb_id'] = src['tmdb_id']
                if src.get('subtitles'):
                    entry['subtitles'] = src['subtitles']
                sources.append(entry)
        elif label_prefix == '[VDY]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                entry = {
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     src.get('direct', True),
                }
                if src.get('subtitles'):
                    entry['subtitles'] = src['subtitles']
                sources.append(entry)
        elif label_prefix == '[VDL]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                sources.append({
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     True,
                })
        elif label_prefix == '[VAP]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                sources.append({
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     True,
                })
        elif label_prefix == '[PFX]':
            for src in group:
                if not src.get('infoHash'):
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                sources.append({
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'infoHash':   src['infoHash'],
                    'fileIdx':    src.get('fileIdx', 0),
                    'trackers':   src.get('trackers', []),
                    'quality':    quality,
                    'seeds':      src.get('seeds'),
                    'size':       src.get('size', ''),
                    'file_size':  src.get('size', ''),
                    'is_torrent': True,
                })
        elif label_prefix == '[MAPI]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                sources.append({
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     True,
                })
        elif label_prefix == '[HHD]':
            for src in group:
                url = src.get('url')
                if not url:
                    continue
                quality = src.get('quality', '')
                display_name = src.get('display_name', '') or src.get('title_line', '')
                base_title = tmdb_original_title or tmdb_title or ''
                clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                dot_parts = [clean.replace(' ', '.').strip('.')]
                if tmdb_year:
                    dot_parts.append(tmdb_year)
                if quality:
                    dot_parts.append(quality)
                title_line = '.'.join(p for p in dot_parts if p)
                entry = {
                    'label':      f"{display_prefix} {src.get('title_line', '')}".strip(),
                    'title_line': title_line or display_name,
                    'tech_line':  display_name,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     src.get('direct', False),
                }
                if src.get('subtitles'):
                    entry['subtitles'] = src['subtitles']
                sources.append(entry)
        else:
            for src in group:
                url = src.get('url') or src.get('link')
                if not url:
                    continue
                quality = src.get('quality', '')
                label = src.get('label') or src.get('title_line') or src.get('host') or url or 'Unknown'
                if label_prefix == '[Z]' and 'vidzee.wtf' in url:
                    if '|' not in url:
                        url += "|User-Agent=Mozilla/5.0&Referer=https://core.vidzee.wtf/&Origin=https://core.vidzee.wtf/"
                    direct = True
                elif label_prefix == '[2E]':
                    if '|' not in url:
                        url += "|User-Agent=Mozilla/5.0&Referer=https://player4u.xyz/embed"
                    direct = False
                elif label_prefix in ('[FHD]', '[PMV]'):
                    direct = src.get('direct', False)
                else:
                    direct = True
                sources.append({
                    'label':      f"{display_prefix} {label}",
                    'title_line': label,
                    'provider':   label_prefix,
                    'url':        url,
                    'quality':    quality,
                    'direct':     direct,
                })
    return sources


def _filter_by_quality(sources):
    """Show quality filter dialog. Returns filtered list or None if cancelled."""
    if not addon.getSettingBool('use_quality_filter'):
        return sources

    # Collect unique qualities preserving order
    seen_q = {}
    for s in sources:
        q = s.get('quality') or 'Unknown'
        if q not in seen_q:
            seen_q[q] = 0
        seen_q[q] += 1

    if len(seen_q) <= 1:
        return sources

    order = {'4K': 0, '2160p': 0, '1080p': 1, '720p': 2, '480p': 3, 'Unknown': 99}
    sorted_q = sorted(seen_q.keys(), key=lambda x: order.get(x, 50))
    options = ['Toate calitățile'] + [f"{q}  ({seen_q[q]})" for q in sorted_q]

    idx = xbmcgui.Dialog().select('Filtrează după calitate', options)
    if idx == -1:
        return None  # user cancelled
    if idx == 0:
        return sources

    chosen = sorted_q[idx - 1]
    return [s for s in sources if (s.get('quality') or 'Unknown') == chosen]


def _fmt_time(seconds):
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def _pick_logo(details):
    """Return best logo URL from TMDb images data (already in details via append_to_response)."""
    logos = (details.get('images') or {}).get('logos') or []
    for lang in ('en', None, ''):
        for logo in logos:
            if logo.get('iso_639_1') == lang and logo.get('file_path'):
                return 'https://image.tmdb.org/t/p/w500' + logo['file_path']
    if logos and logos[0].get('file_path'):
        return 'https://image.tmdb.org/t/p/w500' + logos[0]['file_path']
    return ''


def _sub_filename(title, lang, ext='vtt'):
    """Sanitizează titlul pentru nume de fișier subtitrare: 'Show S01E01.ro.vtt'"""
    import re
    name = re.sub(r'[^\w\s.-]', '', title)
    name = re.sub(r'\s+', '.', name.strip())
    return f'{name}.{lang}.{ext}'


def _auto_enable_subtitles():
    """Wait for playback to start, then activate the subtitle track matching the preferred language."""
    player = xbmc.Player()
    for _ in range(40):
        if player.isPlaying():
            xbmc.sleep(1500)
            streams = player.getAvailableSubtitleStreams()
            chosen = 0
            if streams:
                pref_langs = [l.strip() for l in (addon.getSetting('subs_languages') or 'ro').split(',') if l.strip()]
                for lang in pref_langs:
                    for i, name in enumerate(streams):
                        if subtitles._lang_matches(name, lang):
                            chosen = i
                            break
                    else:
                        continue
                    break
            player.setSubtitleStream(chosen)
            player.showSubtitles(True)
            return
        xbmc.sleep(500)


def _start_torr_proxy(torrserver_url):
    """Start a local HTTP server that shields TorrServer from Kodi's FileBrowser.

    FileBrowser (subtitle browse from OSD) navigates to the "parent directory" of the
    ListItem URL.  If that parent is TorrServer (127.0.0.1:8090), Kodi serialises the
    connection under its "Disabling multi session" flag, stalling the video stream.

    Fix: expose a proxy at http://127.0.0.1:PORT/ whose root is special://home/
    (= ~/.kodi/).  Set the ListItem path to http://127.0.0.1:PORT/play.EXT.

      • /play.EXT         → 302 to TorrServer  (player streams directly from TorrServer)
      • /                 → HTML listing of ~/.kodi/  (FileBrowser shows .kodi folder)
      • /any/path.srt     → serve actual file from ~/.kodi/any/path.srt

    FileBrowser opens at the proxy root, which looks like ~/.kodi/ — useful for
    browsing subtitle files.  TorrServer is never contacted by FileBrowser.
    """
    import os as _os
    import urllib.parse as _urlparse
    from http.server import SimpleHTTPRequestHandler, HTTPServer

    _kodi_home = xbmcvfs.translatePath('special://home/')

    parsed   = _urlparse.urlsplit(torrserver_url)
    ext      = _os.path.splitext(parsed.path)[1] or '.mkv'
    play_path = '/play' + ext

    class _Handler(SimpleHTTPRequestHandler):
        _target    = torrserver_url
        _play      = play_path
        _root      = _kodi_home

        def translate_path(self, path):
            # Map HTTP path → filesystem path inside _root
            p = _urlparse.unquote(path.split('?')[0].split('#')[0])
            p = p.lstrip('/')
            return _os.path.join(self._root, p) if p else self._root

        def do_HEAD(self):
            if self.path.split('?')[0] == self._play:
                self._redirect()
            else:
                super().do_HEAD()

        def do_GET(self):
            if self.path.split('?')[0] == self._play:
                self._redirect()
            else:
                super().do_GET()

        def _redirect(self):
            self.send_response(302)
            self.send_header('Location', self._target)
            self.end_headers()

        def log_message(self, *a): pass

    server = HTTPServer(('127.0.0.1', 0), _Handler)
    port   = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    xbmc.log(f'[Samus/TorrProxy] port={port} root={_kodi_home} → {torrserver_url[:70]}', xbmc.LOGINFO)
    return f'http://127.0.0.1:{port}{play_path}'


def _set_video_info_movie(li, title, year, imdb_id):
    tag = li.getVideoInfoTag()
    tag.setTitle(title)
    if year:
        tag.setYear(int(year))
    if imdb_id:
        tag.setIMDBNumber(imdb_id)
    tag.setMediaType('movie')


def _set_video_info_episode(li, episode_tag, show_title, season, episode, imdb_id):
    tag = li.getVideoInfoTag()
    tag.setTitle(episode_tag)
    tag.setTvShowTitle(show_title)
    tag.setSeason(season)
    tag.setEpisode(episode)
    if imdb_id:
        tag.setIMDBNumber(imdb_id)
    tag.setMediaType('episode')


def _wait_for_resolvers(threads, budget=None, results=None):
    """Wait for resolver threads with a shared time budget and optional per-thread timeouts."""
    try:
        budget = budget or int(addon.getSetting('resolver_timeout') or '10')
    except Exception:
        budget = 10
    deadline = time.time() + budget
    for t in threads:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        individual = getattr(t, '_resolver_timeout', None)
        wait = min(individual, remaining) if individual is not None else remaining
        t.join(wait)

    # Actualizează sănătatea providerilor după join
    if results is not None:
        for t in threads:
            provider = getattr(t, '_provider', None)
            idx      = getattr(t, '_result_index', None)
            if not provider or idx is None:
                continue
            if t.is_alive():
                db.provider_health_fail(provider)
            elif results[idx]:
                db.provider_health_ok(provider)


def _start_history_tracker(tmdb_id, media_type, title, poster, season=None, episode=None, plot=''):
    """Background thread: monitors playback progress, saves to history and scrobbles to Trakt."""
    if not addon.getSettingBool('history_enabled'):
        return

    def _tracker():
        from resources.lib import trakt as trakt_api
        player = xbmc.Player()
        monitor = xbmc.Monitor()
        for _ in range(30):
            if monitor.abortRequested():
                return
            if player.isPlayingVideo():
                break
            xbmc.sleep(500)
        else:
            return  # never started

        # Scrobble start
        trakt_api.scrobble('start', media_type, tmdb_id, 0, season=season, episode=episode)

        last_position = 0
        last_duration = 0
        while not monitor.abortRequested():
            if not player.isPlayingVideo():
                break
            try:
                position = player.getTime()
                duration = player.getTotalTime()
                if duration > 0:
                    last_position = position
                    last_duration = duration
                    db.history_upsert(
                        tmdb_id=tmdb_id,
                        media_type=media_type,
                        title=title,
                        poster=poster,
                        position=position,
                        duration=duration,
                        season=season,
                        episode=episode,
                        plot=plot,
                    )
            except Exception:
                pass
            xbmc.sleep(10000)

        # Scrobble stop — Trakt marks as watched if progress > 80%
        if last_duration > 0:
            progress = min(100.0, last_position / last_duration * 100)
            trakt_api.scrobble('stop', media_type, tmdb_id, progress, season=season, episode=episode)

    t = threading.Thread(target=_tracker, daemon=True)
    t.start()


def _resolve_url(selected, item_data=None, status_cb=None, stats_cb=None):
    """Resolve a source dict to a final stream URL without touching Kodi player or handle.
    Returns (url_string, extra_subs_list) on success, or (None, []) on failure.
    extra_subs: subtitle paths discovered during resolution (ok.ru only).
    Safe to call from background threads (status_cb may be None).
    """
    item_data = item_data or {}

    def _st(msg):
        if status_cb:
            status_cb(msg)

    if selected.get('is_torrent'):
        url = resolve_torrent(
            selected['infoHash'],
            selected.get('fileIdx', 0),
            trackers=selected.get('trackers'),
            seeds=selected.get('seeds'),
            size=selected.get('size'),
            quality=selected.get('quality'),
            status_cb=_st,
            stats_cb=stats_cb,
            torrent_file=selected.get('torrent_file'),
            file_name=selected.get('fileName'),
            title=item_data.get('title'),
            poster=item_data.get('poster'),
        )
        return (url, []) if url else (None, [])

    url = selected['url']
    is_direct = selected['direct']
    extra_subs = []

    if 'primesrc.me/api/v1/l' in url:
        _st('Se rezolvă PrimeSrc (Cloudflare)...')
        xbmc.log(f'[PSM] FlareSolverr → {url}', xbmc.LOGINFO)
        data = primesrcme_resolver.resolve_via_thrax(url, tmdb_id=selected.get('tmdb_id'))
        embed = data.get('link') if data else None
        if not embed:
            xbmc.log(f'[PSM] FlareSolverr nu a returnat link pentru {url}', xbmc.LOGWARNING)
            return None, []
        xbmc.log(f'[PSM] embed URL: {embed}', xbmc.LOGINFO)
        url = embed

    if not is_direct and (url.startswith('tg://') or 't.me/' in url):
        _st('Se rezolvă Telegram (Thrax)...')
        stream_url = telegram_resolver.resolve_via_thrax(url)
        if not stream_url:
            xbmc.log(f'[TG] Thrax nu a returnat URL pentru {url}', xbmc.LOGWARNING)
            return None, []
        url = stream_url
        is_direct = True

    if not is_direct and vidmoly_resolver.is_vidmoly_url(url):
        _st('Se rezolvă Vidmoly (Thrax)...')
        m3u8 = vidmoly_resolver.resolve_via_thrax(url)
        if not m3u8:
            xbmc.log(f'[VML] Thrax nu a returnat URL pentru {url}', xbmc.LOGWARNING)
            return None, []
        url = m3u8
        is_direct = True

    if not is_direct and abysscdn_resolver.is_abysscdn_url(url):
        _st('Se rezolvă AbyssCDN (Thrax)...')
        stream_url = abysscdn_resolver.resolve_via_thrax(url)
        if not stream_url:
            xbmc.log(f'[ABYSS] Thrax nu a returnat URL pentru {url}', xbmc.LOGWARNING)
            return None, []
        url = stream_url
        is_direct = True

    if not is_direct and 'ok.ru/' in url:
        _st('Se rezolvă ok.ru...')
        okru_result = okru_resolver.resolve(url)
        if okru_result:
            url = okru_result['url']
            is_direct = True
            okru_subs = okru_result.get('subtitles', [])
            if okru_subs:
                base_name = _sub_filename(item_data.get('title', 'okru'), '').rstrip('.')
                for track in okru_subs:
                    lang = track.get('language', 'und')
                    sub_url = track['url']
                    local_path = os.path.join(subs_path, f'{base_name}.{lang}.vtt')
                    if xbmcvfs.copy(sub_url, local_path):
                        extra_subs.append(local_path)
                        xbmc.log(f'[OKRU] Subtitrare {lang} salvată: {local_path}', xbmc.LOGINFO)
                    else:
                        xbmc.log(f'[OKRU] xbmcvfs.copy eșuat, folosesc URL direct', xbmc.LOGWARNING)
                        extra_subs.append(sub_url)
        else:
            xbmc.log(f'[OKRU] Rezolvare eșuată pentru {url}', xbmc.LOGWARNING)
            return None, []

    if not is_direct and 'voe.sx/' in url:
        _st('Se rezolvă VOE...')
        try:
            _resolved = voe_resolver.resolve(url)
            if _resolved:
                url = _resolved
                is_direct = True
            else:
                xbmc.log(f'[VOE] resolver nu a returnat surse pentru {url}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[VOE] eroare resolver: {_ex}', xbmc.LOGERROR)
            return None, []
    _DOOD_DOMAINS = ('dood.watch', 'doodstream.com', 'dood.to', 'dood.so', 'dood.cx',
                     'dood.la', 'dood.ws', 'dood.sh', 'doodstream.co', 'dood.pm',
                     'dood.wf', 'dood.re', 'dood.yt', 'dooood.com', 'dood.stream',
                     'ds2play.com', 'doods.pro', 'd0o0d.com', 'd000d.com', 'dood.li')
    if not is_direct and any(d in url for d in _DOOD_DOMAINS):
        _st('Se rezolvă DoodStream...')
        try:
            _resolved = doodstream_resolver.resolve(url)
            if _resolved:
                url = _resolved
                is_direct = True
            else:
                xbmc.log(f'[DoodStream] resolver nu a returnat surse pentru {url}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[DoodStream] eroare resolver: {_ex}', xbmc.LOGERROR)
            return None, []
    if not is_direct and selected.get('provider') == 'vixsrc' and 'vixsrc.to/' in url:
        _st('Se rezolvă VixSrc...')
        try:
            from urllib.parse import urlparse as _urlparse
            _p = _urlparse(url)
            _parts = [x for x in _p.path.strip('/').split('/') if x]
            _mtype = _parts[0] if _parts else 'movie'
            _tid = _parts[1] if len(_parts) > 1 else ''
            _s = int(_parts[2]) if len(_parts) > 2 else None
            _e = int(_parts[3]) if len(_parts) > 3 else None
            _res = vixsrc_resolver.get_sources(_tid, _mtype, season=_s, episode=_e)
            if _res:
                url = _res[0]['url']
                is_direct = True
            else:
                xbmc.log(f'[VixSrc] resolver nu a returnat surse pentru {url}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[VixSrc] eroare resolver: {_ex}', xbmc.LOGERROR)
            return None, []

    _MIXDROP_DOMAINS = ('mixdrop.ag', 'mixdrop.co', 'mixdrop.to', 'mixdrop.sx',
                        'mixdrop.bz', 'mixdrop.ch', 'mixdrp.co', 'mixdrp.to',
                        'mixdrop.gl', 'mixdrop.vc', 'mixdrop.is', 'mxdrop.to')
    if not is_direct and any(d in url for d in _MIXDROP_DOMAINS):
        _st('Se rezolvă MixDrop...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/mixdrop/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[MixDrop] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[MixDrop] eroare: {_ex}', xbmc.LOGERROR)
            return None, []
    _STREAMWISH_DOMAINS = ('streamwish.to', 'streamwish.com', 'streamwish.site',
                           'streamwish.fun', 'wishembed.pro', 'embedwish.com',
                           'cdnwish.com', 'hlswish.com', 'sfastwish.com',
                           'flaswish.com', 'obeywish.com', 'strwish.com',
                           'playerwish.com', 'swishsrv.com', 'hglink.to')
    if not is_direct and any(d in url for d in _STREAMWISH_DOMAINS):
        _st('Se rezolvă StreamWish...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/streamwish/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[StreamWish] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[StreamWish] eroare: {_ex}', xbmc.LOGERROR)
            return None, []
    _FILEMOON_DOMAINS = ('filemoon.sx', 'filemoon.to', 'filemoon.in', 'filemoon.nl',
                         'filemoon.wf', 'filemoon.eu', 'filemoon.art', 'bysejikuar.com',
                         'bysesayeveum.com', 'bysekoze.com', 'bysesukior.com',
                         'bysefujedu.com', 'bysebuho.com', 'bysewihe.com')
    if not is_direct and any(d in url for d in _FILEMOON_DOMAINS):
        _st('Se rezolvă Filemoon...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/filemoon/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[Filemoon] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[Filemoon] eroare: {_ex}', xbmc.LOGERROR)
            return None, []
    _STREAMTAPE_DOMAINS = ('streamtape.com', 'strtape.cloud', 'streamtape.net',
                           'streamta.pe', 'streamtape.site', 'strcloud.link',
                           'streamtape.to', 'streamta.site', 'streamtape.xyz')
    if not is_direct and any(d in url for d in _STREAMTAPE_DOMAINS):
        _st('Se rezolvă Streamtape...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/streamtape/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[Streamtape] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[Streamtape] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    _CALLISTANISE_DOMAINS = ('filelions.to', 'filelions.com', 'filelions.live',
                              'filelions.online', 'alions.pro', 'filelions.site',
                              'lion.wtf', 'lionstreamz.me', 'lionstreamz.lat')
    if not is_direct and any(d in url for d in _CALLISTANISE_DOMAINS):
        _st('Se rezolvă Callistanise...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/callistanise/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[Callistanise] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[Callistanise] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    if not is_direct and 'sendvid.com/' in url:
        _st('Se rezolvă Sendvid...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/sendvid/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[Sendvid] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[Sendvid] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    if not is_direct and 'video.sibnet.ru/' in url:
        _st('Se rezolvă Sibnet...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/sibnet/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[Sibnet] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[Sibnet] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    _VIDOZA_DOMAINS = ('vidoza.net/', 'videzz.net/')
    if not is_direct and any(d in url for d in _VIDOZA_DOMAINS):
        _st('Se rezolvă Vidoza...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/vidoza/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[Vidoza] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[Vidoza] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    if not is_direct and 'yourupload.com/' in url:
        _st('Se rezolvă YourUpload...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/yourupload/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[YourUpload] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[YourUpload] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    if not is_direct and 'my.mail.ru/' in url:
        _st('Se rezolvă MyMail...')
        try:
            import requests as _req
            from resources.lib.resolvers._common import THRAX_HEADERS
            _r = _req.get(
                'https://api.derzis.xyz/mymail/resolve',
                params={'url': url}, headers=THRAX_HEADERS, timeout=20
            )
            if _r.ok:
                _d = _r.json()
                url = '{}|Referer={}'.format(_d['url'], _d.get('referer', ''))
                is_direct = True
            else:
                xbmc.log(f'[MyMail] Thrax error {_r.status_code}', xbmc.LOGWARNING)
                return None, []
        except Exception as _ex:
            xbmc.log(f'[MyMail] eroare: {_ex}', xbmc.LOGERROR)
            return None, []

    if not is_direct:
        _st('Se rezolvă URL-ul...')
        xbmc.log(f"[Samus/resolveurl] Rezolv URL: {url}", xbmc.LOGINFO)
        try:
            if selected.get('provider') == '[DRO]':
                from resolveurl.hmf import HostedMediaFile
                hmf = HostedMediaFile(url=url, include_popups=True)
                resolved = hmf.resolve(allow_popups=True)
            else:
                resolved = resolve_with_timeout(url, timeout=30)
            if resolved:
                url = resolved
            else:
                xbmc.log(f"[Samus/resolveurl] Nicio rezolvare pentru: {url}", xbmc.LOGWARNING)
                return None, []
        except Exception as e:
            xbmc.log(f'[Samus/resolveurl] Eroare: {e}', xbmc.LOGERROR)
            return None, []

    # Webtor JWT URLs pot redirecționa către fișiere cu extensie falsă (.exe).
    # Urmărim redirect-ul, înlocuim extensia non-video cu .mkv.
    xbmc.log(f'[WBT/dbg] is_direct={is_direct} webtor={("webtor.io/token/" in url)} url={url[:60]}', xbmc.LOGINFO)
    if is_direct and 'webtor.io/token/' in url:
        _NON_VIDEO = ('.exe', '.zip', '.rar', '.iso', '.bin', '.dmg')
        try:
            import requests as _req
            xbmc.log(f'[WBT] HEAD request → {url[:80]}', xbmc.LOGINFO)
            _r = _req.head(url, allow_redirects=True, timeout=15)
            final_url = _r.url
            _path = final_url.split('?')[0].lower()
            if any(_path.endswith(ext) for ext in _NON_VIDEO):
                final_url = final_url[:final_url.lower().rfind('.')] + '.mkv' + \
                            (('?' + final_url.split('?', 1)[1]) if '?' in final_url else '')
                xbmc.log(f'[WBT] extensie falsă → .mkv: {final_url}', xbmc.LOGINFO)
            url = final_url
        except Exception as _e:
            xbmc.log(f'[WBT] HEAD redirect eșuat: {_e}', xbmc.LOGWARNING)

    return url, extra_subs


def _resolve_source(handle, selected, li, item_data, dlg, history_meta=None, resume_position=None):
    """Resolve and start playback for one source. Returns True on success, False on failure.
    Called with an already-open DialogResolving (dlg) so the dialog stays visible across retries.
    """
    url, extra_subs = _resolve_url(selected, item_data=item_data,
                                   status_cb=dlg.set_status,
                                   stats_cb=dlg.set_torrent_stats if selected.get('is_torrent') else None)
    if url is None:
        return False
    url = _quote_http_url_for_kodi(url)

    if extra_subs:
        li.setSubtitles(extra_subs)
        threading.Thread(target=_auto_enable_subtitles, daemon=True).start()

    if selected.get('is_torrent'):
        li.setContentLookup(False)
        try:
            proxy_url = _start_torr_proxy(url)
            li.setPath(proxy_url)
        except Exception as _pe:
            xbmc.log(f'[Samus/TorrProxy] Pornire eșuată ({_pe}), folosesc URL direct', xbmc.LOGWARNING)
            li.setPath(url)
    else:
        stream_url = url.split('|')[0] if '|' in url else url
        if '.m3u8' in stream_url:
            li.setMimeType("application/vnd.apple.mpegurl")
            li.setContentLookup(False)
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            if '|' in url:
                headers_str = url.split('|', 1)[1]
                li.setProperty('inputstream.adaptive.stream_headers', headers_str)
                li.setProperty('inputstream.adaptive.manifest_headers', headers_str)
        li.setPath(stream_url if '.m3u8' in stream_url else url)

    dlg.set_status('Se pornește redarea...')
    if handle == -1:
        xbmc.Player().play(li.getPath(), li)
    else:
        xbmcplugin.setResolvedUrl(handle, True, li)

    if history_meta:
        _start_history_tracker(
            tmdb_id=history_meta.get('tmdb_id'),
            media_type=history_meta.get('media_type'),
            title=history_meta.get('title', ''),
            poster=history_meta.get('poster', ''),
            season=history_meta.get('season'),
            episode=history_meta.get('episode'),
            plot=history_meta.get('plot', ''),
        )

    # Keep dialog visible until fullscreen video is active — covers Kodi's VideoPlayer loading spinner.
    # Exit as soon as AV actually starts (onAVStarted) so we don't block subsequent plugin invocations
    # (e.g. subtitle browse from OSD, which Kodi serializes per-addon).
    av_started = [False]

    class _Player(xbmc.Player):
        def onAVStarted(self):
            av_started[0] = True

    player = _Player()
    monitor = xbmc.Monitor()
    for _ in range(150):
        if monitor.abortRequested():
            break
        if av_started[0]:
            break
        if xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'):
            break
        xbmc.sleep(200)

    if av_started[0] and resume_position and resume_position > 0:
        xbmc.sleep(300)
        xbmc.Player().seekTime(resume_position)

    # For setResolvedUrl path Kodi takes over after the call — report success.
    # For direct play path, report success only if AV actually started.
    return True if handle != -1 else av_started[0]


def _play_source(handle, selected, li, item_data=None, history_meta=None, resume_position=None):
    """Resolve and play a selected source dict. Returns True on success, False on failure."""
    item_data = item_data or {}
    return run_resolving_dialog(
        fanart=item_data.get('fanart', ''),
        title=item_data.get('title', ''),
        resolver_fn=lambda dlg: _resolve_source(handle, selected, li, item_data, dlg,
                                                history_meta=history_meta,
                                                resume_position=resume_position),
    )


def play_movie(handle, tmdb_id, force_dialog=False):
    details = movies.get_movie_details(tmdb_id)
    imdb_id = (details.get('imdb_id')
               or details.get('external_ids', {}).get('imdb_id')
               or get_external_ids(tmdb_id, 'movie'))
    if not imdb_id:
        xbmc.log(f'[Samus] imdb_id indisponibil pentru tmdb_id={tmdb_id}', xbmc.LOGWARNING)
    title = details.get('title', 'Fără titlu')
    original_title = details.get('original_title') or None
    year = details.get('release_date', '')[:4]
    if details.get('original_language', 'en') == 'en':
        english_title = original_title or title
    else:
        en_data = get_english_title(tmdb_id, 'movie')
        english_title = en_data.get('title') or original_title or title
    if dialogs._pending_resolver is not None:
        _fanart = 'https://image.tmdb.org/t/p/original' + (details.get('backdrop_path') or '')
        dialogs._pending_resolver.update_info(fanart=_fanart, title=title)

    _cache_key = f'sources_movie_{tmdb_id}'
    sources = db.cache_get(_cache_key, ttl=600)
    _live_feed = None
    if sources:
        xbmc.log(f'[Samus] Cache surse film: {len(sources)} pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    else:
        results = [None] * 48
        threads = []

        if addon.getSettingBool('use_torrentio') and imdb_id:
            threads.append(threaded_resolver(torrentio.get_movie_sources, (imdb_id,), results, 4))
        if addon.getSettingBool('use_torrentdb') and imdb_id:
            threads.append(threaded_resolver(torrentdb.get_movie_sources, (imdb_id,), results, 5))
        if addon.getSettingBool('use_mediafusion') and imdb_id:
            threads.append(threaded_resolver(mediafusion.get_movie_sources, (imdb_id,), results, 6))
        if addon.getSettingBool('use_comet') and imdb_id:
            threads.append(threaded_resolver(comet.get_movie_sources, (imdb_id,), results, 7))
        if addon.getSettingBool('use_perflix') and imdb_id:
            threads.append(threaded_resolver(perflix.get_movie_sources, (imdb_id,), results, 8))
        if addon.getSettingBool('use_thrax'):
            threads.append(threaded_resolver(thrax.get_movie_sources, (tmdb_id,), results, 10))
        if addon.getSettingBool('use_primesrc'):
            threads.append(threaded_resolver(primesrc.get_primesrc_sources, (tmdb_id,), results, 11))
        if addon.getSettingBool('use_flixer'):
            threads.append(threaded_resolver(flixer.get_sources, (tmdb_id, 'movie'), results, 12))
        if addon.getSettingBool('use_vixsrc'):
            threads.append(threaded_resolver(vixsrc_resolver.get_sources, (tmdb_id, 'movie'), results, 13))
        if addon.getSettingBool('use_hdhub') and imdb_id:
            threads.append(threaded_resolver(hdhub.get_sources, (imdb_id, 'movie'), results, 14))
        if addon.getSettingBool('use_webstreamr') and imdb_id:
            threads.append(threaded_resolver(webstreamr.get_sources, (imdb_id, 'movie'), results, 15))
        if addon.getSettingBool('use_vidrock'):
            threads.append(threaded_resolver(vidrock.get_sources, (tmdb_id, 'movie'), results, 16))
        if addon.getSettingBool('use_hydrahd'):
            threads.append(threaded_resolver(hydrahd_resolver.get_sources, (tmdb_id, 'movie', None, None, imdb_id), results, 22, timeout=_RT['hydrahd']))
        if addon.getSettingBool('use_primesrcme'):
            threads.append(threaded_resolver(primesrcme_resolver.get_sources, (tmdb_id, 'movie'), results, 25))
        if addon.getSettingBool('use_vsembed'):
            threads.append(threaded_resolver(vsembed_resolver.get_sources, (tmdb_id, 'movie'), results, 28, timeout=_RT['vsembed']))
        if addon.getSetting('use_multiembed') != 'false':
            threads.append(threaded_resolver(multiembed_resolver.get_sources, (tmdb_id, 'movie'), results, 30))
        if addon.getSetting('use_pelispanda') != 'false':
            threads.append(threaded_resolver(pelispanda_resolver.get_sources, (tmdb_id, 'movie', title, year, None, None, original_title), results, 33))
        if addon.getSettingBool('use_sooti') and imdb_id:
            threads.append(threaded_resolver(sooti_resolver.get_sources, (imdb_id, 'movie'), results, 35))
        if addon.getSettingBool('use_cinesu'):
            threads.append(threaded_resolver(cinesu_resolver.get_sources, (tmdb_id, 'movie'), results, 38))
        if addon.getSettingBool('use_velaflow') and imdb_id:
            threads.append(threaded_resolver(velaflow_resolver.get_movie_sources, (imdb_id,), results, 39))
        if addon.getSettingBool('use_filelist') and imdb_id:
            threads.append(threaded_resolver(filelist_resolver.get_movie_sources, (imdb_id,), results, 40))
        if addon.getSettingBool('use_vidapi'):
            threads.append(threaded_resolver(vidapi_resolver.get_sources, (tmdb_id, 'movie'), results, 43))
        if addon.getSettingBool('use_webtor') and imdb_id:
            threads.append(threaded_resolver(webtor_resolver.get_sources, (imdb_id, 'movie'), results, 45))
        if addon.getSettingBool('use_adult') and addon.getSettingBool('use_pandamovies'):
            from resources.lib.resolvers import pandamovies as pandamovies_resolver
            threads.append(threaded_resolver(pandamovies_resolver.get_sources, (title, year), results, 46))
        if addon.getSettingBool('use_penguplay') and imdb_id:
            threads.append(threaded_resolver(penguplay_resolver.get_sources, (imdb_id, 'movie'), results, 47))
        # Wait briefly so the fastest resolvers (THX, vidzee, primesrc) can finish first
        _wait_for_resolvers(threads, budget=1.5, results=results)

        prefixes = ['[V]', '[ES]', '[Z]', '[2E]', '[TIO]', '[TDB]', '[MF]', '[CMT]', '[PFX]', '[UDX]', '[THX]', '[PSC]', '[FLX]', '[VXS]', '[HDB]', '[WSR]', '[VDR]', '[STF]', '[NBS]', '[FNS]', '[PLW]', '[FHD]', '[HHD]', '[YAS]', '[NHD]', '[PSM]', '[VDL]', '[VDY]', '[VSE]', '[YFX]', '[MEB]', '[VBT]', '[MAPI]', '[PPD]', '[SIMDB]', '[SOT]', '[MBX]', '[PPR]', '[CSU]', '[VLF]', '[FLI]', '[PCH]', '[TLX]', '[VAP]', '[PDN]', '[WBT]', '[PMV]', '[PGP]']
        _processed = set()

        def _drain_new():
            """Drain unprocessed resolver results; return (new_sources, all_done)."""
            new_srcs = []
            for i, r in enumerate(results):
                if i in _processed or r is None:
                    continue
                _processed.add(i)
                batch = _build_sources([r], [prefixes[i]], tmdb_title=title, tmdb_year=year, tmdb_original_title=english_title)
                for s in batch:
                    enrich_source(s)
                new_srcs.extend(batch)
            all_done = not any(t.is_alive() for t in threads)
            return new_srcs, all_done

        sources, all_done = _drain_new()
        sources = sort_sources(sources)
        if all_done and sources:
            db.cache_set(_cache_key, sources)
        _live_feed = None if all_done else _drain_new

    if not sources and not _live_feed:
        xbmcgui.Dialog().notification('Samus', 'Nicio sursă video găsită.', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    sources = _filter_by_quality(sources)
    if sources is None:
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    IMG_BASE    = 'https://image.tmdb.org/t/p/w500'
    FANART_BASE = 'https://image.tmdb.org/t/p/original'
    item_data = {
        'title':  title,
        'poster': IMG_BASE    + (details.get('poster_path')  or ''),
        'fanart': FANART_BASE + (details.get('backdrop_path') or ''),
        'logo':   _pick_logo(details),
    }

    history_meta = {
        'tmdb_id': tmdb_id, 'media_type': 'movie',
        'title': title, 'poster': details.get('poster_path') or '',
        'plot': details.get('overview') or '',
    }
    resume_pos = None
    h = db.history_get(tmdb_id, 'movie')
    if h and h['position'] > 60 and h['percent'] < 85:
        if xbmcgui.Dialog().yesno(
            'Continuă..',
            f'Ai rămas la [B]{_fmt_time(h["position"])}[/B].',
            nolabel='De la început', yeslabel='Continuă',
        ):
            resume_pos = h['position']

    # Subtitles — fetched once, reused across retries
    _subs_fetched = False
    _subs_to_set = []

    remaining = list(sources)

    # Auto-select last working provider when sources are fully loaded (no live feed).
    _auto_select_enabled = addon.getSettingBool('auto_select_provider') and not force_dialog
    _saved_provider = db.provider_success_get(tmdb_id, 'movie') if (_auto_select_enabled and not _live_feed) else None
    if _saved_provider:
        _pref = [s for s in remaining if s.get('provider') == _saved_provider]
        if _pref:
            selected = _pref[0]
            remaining = [s for s in remaining if s is not selected]
            xbmc.log(f'[Samus] Auto-select provider memorat: {_saved_provider}', xbmc.LOGINFO)
        else:
            _saved_provider = None

    if not _saved_provider:
        # Show dialog once (with live feed on first open)
        selected, remaining = show_source_dialog(remaining, item_data, source_feed=_live_feed)
        if _live_feed and remaining:
            db.cache_set(_cache_key, remaining)
        if selected is None:
            if not remaining:
                xbmcgui.Dialog().notification('Samus', 'Nicio sursă video găsită.', xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return
        remaining = [s for s in remaining if s is not selected]

    # Fetch subtitles once — skip pentru torrenturi (au track-uri embedded în MKV)
    _subs_to_set = []
    vidzee_subs = selected.get('subtitles', [])
    if vidzee_subs:
        _subs_to_set = vidzee_subs
    elif not selected.get('is_torrent') and addon.getSettingBool('subs_enabled'):
        vdrk_urls = subtitles.search_vdrk(tmdb_id)
        if vdrk_urls:
            _subs_to_set = vdrk_urls
        elif imdb_id:
            subs = subtitles.search_subtitles(imdb_id)
            for sub in subs:
                sub_path = subtitles.download_subtitle(sub, subs_path)
                if sub_path:
                    _subs_to_set = [sub_path]
                    break

    # Single dialog for all retries — no flicker between sources.
    _auto_was_selected = _saved_provider is not None

    def _movie_resolver(dlg):
        nonlocal selected
        first = _auto_was_selected
        while selected is not None:
            li = xbmcgui.ListItem(path=selected.get('url', ''))
            li.setProperty('IsPlayable', 'true')
            _set_video_info_movie(li, title, year, imdb_id)
            if _subs_to_set:
                li.setSubtitles(_subs_to_set)

            ok = _resolve_source(handle, selected, li, item_data, dlg,
                                 history_meta=history_meta, resume_position=resume_pos)
            if ok:
                db.provider_success_set(tmdb_id, 'movie', selected.get('provider', ''))
                if _subs_to_set or selected.get('subtitles') or selected.get('is_torrent'):
                    threading.Thread(target=_auto_enable_subtitles, daemon=True).start()
                return True

            xbmc.log(f'[Samus] Sursă eșuată: {selected.get("label", "")}', xbmc.LOGWARNING)
            if first:
                first = False
                db.provider_success_clear(tmdb_id, 'movie')
                if remaining:
                    dlg.set_status('Provider memorat eșuat. Alege o altă sursă...')
                    xbmc.sleep(300)
                    dialogs._pending_resolver = dlg
                    new_sel, new_all = show_source_dialog(remaining, item_data)
                    dialogs._pending_resolver = None
                    if new_sel is None:
                        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
                        return False
                    remaining[:] = [s for s in new_all if s is not new_sel]
                    selected = new_sel
                    continue
                xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
                return False
            if not remaining:
                xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
                return False
            selected = remaining.pop(0)
            provider = selected.get('provider') or selected.get('label') or '?'
            dlg.set_status(f'Sursă eșuată. Se încearcă {provider}…')
        return False

    run_resolving_dialog(
        fanart=item_data.get('fanart', ''),
        title=item_data.get('title', ''),
        resolver_fn=_movie_resolver,
    )


def _get_next_episode(tv_id, season, episode):
    """Returns (next_season, next_episode, episode_title) or None.

    Skips episodes that haven't aired yet (air_date in the future).
    """
    today = datetime.date.today()

    def _is_aired(ep):
        air_date = ep.get('air_date') or ''
        if not air_date:
            return False  # TBA — treat as not yet aired
        try:
            parts = air_date.split('-')
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2])) <= today
        except Exception:
            return False

    try:
        season_data = tv.get_season(tv_id, season)
        for ep in sorted(season_data.get('episodes', []), key=lambda e: e.get('episode_number', 0)):
            ep_num = ep.get('episode_number', 0)
            if ep_num <= episode:
                continue
            if not _is_aired(ep):
                return None
            return (season, ep_num, ep.get('name', ''), ep.get('overview', ''))

        next_season_data = tv.get_season(tv_id, season + 1)
        for ep in sorted(next_season_data.get('episodes', []), key=lambda e: e.get('episode_number', 0)):
            ep_num = ep.get('episode_number', 0)
            if not _is_aired(ep):
                return None
            return (season + 1, ep_num, ep.get('name', ''), ep.get('overview', ''))
    except Exception as e:
        xbmc.log(f'[Samus] _get_next_episode eroare: {e}', xbmc.LOGWARNING)
    return None


class _AutoplayOverlay(xbmcgui.WindowXMLDialog):
    """Netflix-style autoplay overlay — appears in top-right corner during last N seconds."""

    PLAY = 'play'
    CANCEL = 'cancel'

    def __init__(self, *args, **kwargs):
        # WindowXMLDialog C++ binding reads xml/path from positional args at instantiation;
        # calling super().__init__() with them again causes a type error in Python 3.
        # Custom params are passed via kwargs instead.
        self._show_name  = kwargs.get('show_name', '')
        self._ep_label   = kwargs.get('ep_label', '')
        self._total      = max(1, kwargs.get('countdown_secs', 60))
        self._poster_url = kwargs.get('poster_url', '')
        overview         = kwargs.get('overview', '')
        self._overview   = overview[:220] + '…' if len(overview) > 220 else overview
        self._closed     = False
        self.result      = self.PLAY  # default: play on countdown expiry

    def onInit(self):
        win = xbmcgui.Window(10000)
        win.setProperty('samus.next_show', self._show_name)
        win.setProperty('samus.next_ep', self._ep_label)
        win.setProperty('samus.next_poster', self._poster_url)
        win.setProperty('samus.next_overview', self._overview)
        win.setProperty('samus.countdown_text', f'Se pornește în {self._total}s')
        try:
            self.getControl(5010).setWidth(1920)
            self.setFocus(self.getControl(5001))
        except Exception:
            pass
        t = threading.Thread(target=self._countdown, daemon=True)
        t.start()

    def _countdown(self):
        try:
            bar = self.getControl(5010)
        except Exception:
            bar = None
        win = xbmcgui.Window(10000)
        for remaining in range(self._total, 0, -1):
            if self._closed:
                return
            win.setProperty('samus.countdown_text', f'Se pornește în {remaining}s')
            if bar:
                try:
                    bar.setWidth(int(1920 * remaining / self._total))
                except Exception:
                    pass
            xbmc.sleep(1000)
        if not self._closed:
            self._closed = True
            self.result = self.PLAY
            self.close()

    def onClick(self, control_id):
        self.result = self.PLAY if control_id == 5001 else self.CANCEL
        self._closed = True
        self.close()

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 110):  # Back / Escape
            self.result = self.CANCEL
            self._closed = True
            self.close()


def _fetch_tv_sources(tv_id, imdb_id, season, episode, details):
    """Run all enabled resolvers for a TV episode and return enriched+sorted sources."""
    _cache_key = f'sources_tv_{tv_id}_{season}_{episode}'
    cached = db.cache_get(_cache_key, ttl=600)
    if cached:
        xbmc.log(f'[Samus] Cache surse TV: {len(cached)} pentru tv_id={tv_id} S{season:02d}E{episode:02d}', xbmc.LOGINFO)
        return cached

    original_name = details.get('original_name') or None
    if details.get('original_language', 'en') == 'en':
        english_show_name = original_name or details.get('name', '')
    else:
        en_data = get_english_title(tv_id, 'tv')
        english_show_name = en_data.get('name') or original_name or details.get('name', '')
    results = [None] * 47
    threads = []
    if addon.getSettingBool('use_torrentio') and imdb_id:
        threads.append(threaded_resolver(torrentio.get_tv_sources, (imdb_id, season, episode), results, 4))
    if addon.getSettingBool('use_torrentdb') and imdb_id:
        threads.append(threaded_resolver(torrentdb.get_tv_sources, (imdb_id, season, episode), results, 5))
    if addon.getSettingBool('use_mediafusion') and imdb_id:
        threads.append(threaded_resolver(mediafusion.get_tv_sources, (imdb_id, season, episode), results, 6))
    if addon.getSettingBool('use_comet') and imdb_id:
        threads.append(threaded_resolver(comet.get_tv_sources, (imdb_id, season, episode), results, 7))
    if addon.getSettingBool('use_perflix') and imdb_id:
        threads.append(threaded_resolver(perflix.get_tv_sources, (imdb_id, season, episode), results, 8))
    if addon.getSettingBool('use_thrax'):
        threads.append(threaded_resolver(thrax.get_tv_sources, (tv_id, season, episode), results, 10))
    if addon.getSettingBool('use_primesrc'):
        threads.append(threaded_resolver(primesrc.get_primesrc_tv_sources, (tv_id, season, episode), results, 11))
    if addon.getSettingBool('use_flixer'):
        threads.append(threaded_resolver(flixer.get_sources, (tv_id, 'tv', season, episode), results, 12))
    if addon.getSettingBool('use_vixsrc'):
        threads.append(threaded_resolver(vixsrc_resolver.get_sources, (tv_id, 'tv', season, episode), results, 13))
    if addon.getSettingBool('use_hdhub') and imdb_id:
        threads.append(threaded_resolver(hdhub.get_sources, (imdb_id, 'tv', season, episode), results, 14))
    if addon.getSettingBool('use_webstreamr') and imdb_id:
        threads.append(threaded_resolver(webstreamr.get_sources, (imdb_id, 'tv', season, episode), results, 15))
    if addon.getSettingBool('use_vidrock'):
        threads.append(threaded_resolver(vidrock.get_sources, (tv_id, 'tv', season, episode), results, 16))
    if addon.getSettingBool('use_hydrahd'):
        threads.append(threaded_resolver(hydrahd_resolver.get_sources, (tv_id, 'tv', season, episode, imdb_id), results, 22, timeout=_RT['hydrahd']))
    if addon.getSettingBool('use_primesrcme'):
        threads.append(threaded_resolver(primesrcme_resolver.get_sources, (tv_id, 'tv', season, episode), results, 25))
    if addon.getSettingBool('use_vsembed'):
        threads.append(threaded_resolver(vsembed_resolver.get_sources, (tv_id, 'tv', season, episode), results, 28, timeout=_RT['vsembed']))
    if addon.getSetting('use_multiembed') != 'false':
        threads.append(threaded_resolver(multiembed_resolver.get_sources, (tv_id, 'tv', season, episode), results, 30))
    if addon.getSetting('use_pelispanda') != 'false':
        threads.append(threaded_resolver(pelispanda_resolver.get_sources, (tv_id, 'tv', details.get('name', ''), None, season, episode, original_name), results, 33))
    if addon.getSettingBool('use_sooti') and imdb_id:
        threads.append(threaded_resolver(sooti_resolver.get_sources, (imdb_id, 'tv', season, episode), results, 35))
    if addon.getSettingBool('use_cinesu'):
        threads.append(threaded_resolver(cinesu_resolver.get_sources, (tv_id, 'tv', season, episode), results, 38))
    if addon.getSettingBool('use_velaflow') and imdb_id:
        threads.append(threaded_resolver(velaflow_resolver.get_tv_sources, (imdb_id, season, episode), results, 39))
    if addon.getSettingBool('use_filelist') and imdb_id:
        threads.append(threaded_resolver(filelist_resolver.get_tv_sources, (imdb_id, season, episode), results, 40))
    if addon.getSettingBool('use_vidapi'):
        threads.append(threaded_resolver(vidapi_resolver.get_sources, (tv_id, 'tv', season, episode), results, 43))
    if addon.getSettingBool('use_webtor') and imdb_id:
        threads.append(threaded_resolver(webtor_resolver.get_sources, (imdb_id, 'tv', season, episode), results, 44))
    if addon.getSettingBool('use_penguplay') and imdb_id:
        threads.append(threaded_resolver(penguplay_resolver.get_sources, (imdb_id, 'tv', season, episode), results, 45))
    _wait_for_resolvers(threads, results=results)
    prefixes = ['[V]', '[ES]', '[Z]', '[2E]', '[TIO]', '[TDB]', '[MF]', '[CMT]', '[PFX]', '[UDX]', '[THX]', '[PSC]', '[FLX]', '[VXS]', '[HDB]', '[WSR]', '[VDR]', '[STF]', '[NBS]', '[FNS]', '[PLW]', '[FHD]', '[HHD]', '[YAS]', '[NHD]', '[PSM]', '[VDL]', '[VDY]', '[VSE]', '[YFX]', '[MEB]', '[VBT]', '[MAPI]', '[PPD]', '[SIMDB]', '[SOT]', '[MBX]', '[PPR]', '[CSU]', '[VLF]', '[FLI]', '[PCH]', '[TLX]', '[VAP]', '[WBT]', '[PGP]']
    show_label = f"{details.get('name', '')} S{season:02d}E{episode:02d}"
    english_show_label = f"{english_show_name} S{season:02d}E{episode:02d}"
    sources = _build_sources(results, prefixes, tmdb_title=show_label, tmdb_original_title=english_show_label)
    for s in sources:
        enrich_source(s)
    sources = sort_sources(sources)
    if sources:
        db.cache_set(_cache_key, sources)
    return sources


_Q_ORDER = {'4K': 4, '2160p': 4, '1080p': 3, '720p': 2, '480p': 1, 'SD': 1}


def _autoselect_source(sources, preferred_provider=None, quality_pref=None, is_torrent_pref=None):
    """Pick best source: preferred provider first, then score by quality + type."""
    if not sources:
        return None
    if preferred_provider:
        for s in sources:
            if s.get('provider') == preferred_provider:
                return s
    pref_q = _Q_ORDER.get(quality_pref, 3)
    pref_t = bool(is_torrent_pref)

    def _score(s):
        score = 0
        score -= abs(_Q_ORDER.get(s.get('quality', ''), 2) - pref_q) * 10
        if bool(s.get('is_torrent')) == pref_t:
            score += 5
        seeds = s.get('seeds') or 0
        if seeds > 0:
            score += min(seeds // 20, 5)
        return score

    return max(sources, key=_score)


def _save_autoplay_cache(tv_id, season, episode, sources, quality_pref=None,
                         is_torrent_pref=None, preresolve=None):
    try:
        data = {
            'tv_id': tv_id, 'season': season, 'episode': episode,
            'sources': sources,
            'quality_pref': quality_pref,
            'is_torrent_pref': is_torrent_pref,
            'preresolve': preresolve,  # {source, url, ts} sau None
            'ts': time.time(),
        }
        with open(_AUTOPLAY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        pre_tag = ' + pre-resolve' if preresolve else ''
        xbmc.log(f'[Samus] Autoplay cache salvat: {len(sources)} surse{pre_tag} pentru S{season:02d}E{episode:02d}', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[Samus] autoplay cache write eroare: {e}', xbmc.LOGWARNING)


def _load_autoplay_cache(tv_id, season, episode):
    """Return cached data dict if valid, else None. Deletes file after reading."""
    try:
        if not os.path.exists(_AUTOPLAY_CACHE_FILE):
            return None
        with open(_AUTOPLAY_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        os.remove(_AUTOPLAY_CACHE_FILE)
        if (data.get('tv_id') == tv_id and
                data.get('season') == season and
                data.get('episode') == episode and
                time.time() - data.get('ts', 0) < 300):
            return data
    except Exception as e:
        xbmc.log(f'[Samus] autoplay cache read eroare: {e}', xbmc.LOGWARNING)
    return None


def play_tv_episode(handle, tv_id, season, episode, preferred_provider=None, force_dialog=False):
    details = tv.get_tv_details(tv_id)
    imdb_id = (details.get('external_ids', {}).get('imdb_id')
               or get_external_ids(tv_id, 'tv'))
    if not imdb_id:
        xbmc.log(f'[Samus] imdb_id indisponibil pentru tv_id={tv_id}', xbmc.LOGWARNING)
    if dialogs._pending_resolver is not None:
        _fanart = 'https://image.tmdb.org/t/p/original' + (details.get('backdrop_path') or '')
        dialogs._pending_resolver.update_info(fanart=_fanart, title=details.get('name', ''))
    show_title = details.get('name', 'Unknown').replace(' ', '.')
    original_name = (details.get('original_name') or None)
    try:
        season_data = tv.get_season(tv_id, season)
        ep_data = next((e for e in season_data.get('episodes', [])
                        if e.get('episode_number') == episode), {})
        episode_tag = ep_data.get('name', '') or ''
    except Exception:
        episode_tag = ''

    IMG_BASE    = 'https://image.tmdb.org/t/p/w500'
    FANART_BASE = 'https://image.tmdb.org/t/p/original'
    item_data = {
        'title':  f"{show_title}  S{season:02d}E{episode:02d}",
        'poster': IMG_BASE    + (details.get('poster_path')  or ''),
        'fanart': FANART_BASE + (details.get('backdrop_path') or ''),
        'logo':   _pick_logo(details),
    }

    cached = _load_autoplay_cache(tv_id, season, episode)
    if cached:
        sources = cached['sources']
        xbmc.log(f'[Samus] Autoplay cache: {len(sources)} surse pre-scraped pentru S{season:02d}E{episode:02d}', xbmc.LOGINFO)

        # Inject pre-resolved source at the front if it's still fresh (3 min TTL).
        pr = cached.get('preresolve') or {}
        if (pr.get('url') and pr.get('source') and
                time.time() - pr.get('ts', 0) < 180):
            pre_source = dict(pr['source'])
            pre_source['url'] = pr['url']
            pre_source['direct'] = True
            sources = [pre_source] + [s for s in sources if s.get('url') != pr['source'].get('url')]
            xbmc.log(f'[Samus] Autoplay pre-resolve injectat: {pre_source.get("label", "")}', xbmc.LOGINFO)

        selected = _autoselect_source(
            sources,
            preferred_provider,
            quality_pref=cached.get('quality_pref'),
            is_torrent_pref=cached.get('is_torrent_pref'),
        )
        if selected:
            _auto_selected = True
            xbmc.log(f'[Samus] Autoplay auto-select: {selected.get("label", "")}', xbmc.LOGINFO)
        else:
            _auto_selected = False
            selected, sources = show_source_dialog(sources, item_data)
    else:
        sources = _fetch_tv_sources(tv_id, imdb_id, season, episode, details)

        if not sources:
            xbmcgui.Dialog().notification('Samus', 'Nicio sursă video găsită.', xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return

        sources = _filter_by_quality(sources)
        if sources is None:
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return

        _auto_select_enabled = addon.getSettingBool('auto_select_provider') and not force_dialog
        _eff_provider = (preferred_provider or db.provider_success_get(tv_id, 'tv')) if _auto_select_enabled else preferred_provider
        if _eff_provider:
            pref_sources = [s for s in sources if s.get('provider') == _eff_provider]
            if pref_sources:
                selected = pref_sources[0]
                _auto_selected = True
                xbmc.log(f'[Samus] Auto-select provider memorat (TV): {_eff_provider}', xbmc.LOGINFO)
            else:
                _auto_selected = False
                selected, sources = show_source_dialog(sources, item_data)
        else:
            _auto_selected = False
            selected, sources = show_source_dialog(sources, item_data)

    if selected is None:
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    history_meta = {
        'tmdb_id': tv_id, 'media_type': 'tv',
        'title': details.get('name', show_title),
        'poster': details.get('poster_path') or '',
        'plot': details.get('overview') or '',
        'season': season, 'episode': episode,
    }

    resume_pos = None
    h = db.history_get(tv_id, 'tv', season=season, episode=episode)
    if h and h['position'] > 60 and h['percent'] < 85:
        if xbmcgui.Dialog().yesno(
            'Continuă..',
            f'Ai rămas la [B]{_fmt_time(h["position"])}[/B].',
            nolabel='De la început', yeslabel='Continuă',
        ):
            resume_pos = h['position']

    # Fetch subtitles once — skip pentru torrenturi (au track-uri embedded în MKV)
    _subs_to_set = []
    vidzee_subs = selected.get('subtitles', [])
    if vidzee_subs:
        _subs_to_set = vidzee_subs
    elif not selected.get('is_torrent') and addon.getSettingBool('subs_enabled'):
        vdrk_urls = subtitles.search_vdrk(tv_id, season=season, episode=episode)
        if vdrk_urls:
            _subs_to_set = vdrk_urls
        elif imdb_id:
            subs = subtitles.search_subtitles(imdb_id, season=season, episode=episode)
            for sub in subs:
                sub_path = subtitles.download_subtitle(sub, subs_path)
                if sub_path:
                    _subs_to_set = [sub_path]
                    break

    # Single dialog for all retries — no flicker between sources.
    remaining = [s for s in sources if s is not selected]
    _play_ok = [False]
    _first_attempt = [True]

    def _tv_resolver(dlg):
        nonlocal selected
        while selected is not None:
            li = xbmcgui.ListItem(path=selected.get('url', ''))
            li.setProperty('IsPlayable', 'true')
            _set_video_info_episode(li, episode_tag, show_title, season, episode, imdb_id)
            if _subs_to_set:
                li.setSubtitles(_subs_to_set)

            ok = _resolve_source(handle, selected, li, item_data, dlg,
                                 history_meta=history_meta, resume_position=resume_pos)
            if ok:
                if _first_attempt[0]:
                    db.provider_success_set(tv_id, 'tv', selected.get('provider', ''))
                if _subs_to_set or selected.get('subtitles') or selected.get('is_torrent'):
                    threading.Thread(target=_auto_enable_subtitles, daemon=True).start()
                _play_ok[0] = True
                return True

            xbmc.log(f'[Samus] Sursă eșuată: {selected.get("label", "")}', xbmc.LOGWARNING)
            if _first_attempt[0]:
                _first_attempt[0] = False
                if _auto_selected:
                    db.provider_success_clear(tv_id, 'tv')
                    if remaining:
                        dlg.set_status('Provider memorat eșuat. Alege o altă sursă...')
                        xbmc.sleep(300)
                        dialogs._pending_resolver = dlg
                        new_sel, new_all = show_source_dialog(remaining, item_data)
                        dialogs._pending_resolver = None
                        if new_sel is None:
                            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
                            return False
                        remaining[:] = [s for s in new_all if s is not new_sel]
                        selected = new_sel
                        continue
                    xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
                    return False
            if not remaining:
                xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
                return False
            selected = remaining.pop(0)
            provider = selected.get('provider') or selected.get('label') or '?'
            dlg.set_status(f'Sursă eșuată. Se încearcă {provider}…')
        return False

    run_resolving_dialog(
        fanart=item_data.get('fanart', ''),
        title=item_data.get('title', ''),
        resolver_fn=_tv_resolver,
    )
    if not _play_ok[0]:
        return

    if not addon.getSettingBool('autoplay_next'):
        return

    _mon = xbmc.Monitor()
    _pl  = xbmc.Player()

    # Wait up to 15s for playback to actually start
    for _ in range(30):
        if _pl.isPlayingVideo() or _mon.abortRequested():
            break
        xbmc.sleep(500)

    try:
        trigger_secs = int(addon.getSetting('autoplay_countdown') or '60')
    except Exception:
        trigger_secs = 60

    next_ep            = None
    next_s = next_e = ep_title = None
    next_fetched       = False
    overlay_shown      = False
    preferred          = selected.get('provider')
    show_name          = details.get('name', '')
    scrape_result      = {'sources': None, 'preresolve': None}
    scrape_thread      = None
    preresolve_thread  = None

    def _start_prefetch(ns, ne):
        nonlocal scrape_thread, preresolve_thread
        if scrape_thread is not None:
            return  # deja pornit

        def _bg_scrape(r=scrape_result, _ns=ns, _ne=ne):
            try:
                r['sources'] = _fetch_tv_sources(tv_id, imdb_id, _ns, _ne, details)
                xbmc.log(f'[Samus] BG scrape: {len(r["sources"])} surse S{_ns:02d}E{_ne:02d}', xbmc.LOGINFO)
            except Exception as ex:
                xbmc.log(f'[Samus] BG scrape eroare: {ex}', xbmc.LOGWARNING)

        def _bg_preresolve(r=scrape_result):
            for _ in range(40):
                if r['sources'] is not None:
                    break
                xbmc.sleep(500)
            srcs = r.get('sources') or []
            candidates = [s for s in srcs if not s.get('is_torrent')]
            best = _autoselect_source(
                candidates,
                preferred_provider=preferred,
                quality_pref=selected.get('quality'),
                is_torrent_pref=False,
            )
            if not best:
                return
            try:
                pre_url, _ = _resolve_url(best)
                if pre_url:
                    r['preresolve'] = {'source': best, 'url': pre_url, 'ts': time.time()}
                    xbmc.log(f'[Samus] Pre-resolve OK: {best.get("label", "")}', xbmc.LOGINFO)
            except Exception as ex:
                xbmc.log(f'[Samus] Pre-resolve eroare: {ex}', xbmc.LOGWARNING)

        scrape_thread = threading.Thread(target=_bg_scrape, daemon=True)
        scrape_thread.start()
        preresolve_thread = threading.Thread(target=_bg_preresolve, daemon=True)
        preresolve_thread.start()

    while _pl.isPlayingVideo() and not _mon.abortRequested():
        try:
            total     = _pl.getTotalTime()
            current   = _pl.getTime()
            remaining = total - current

            # ── Prefetch episod următor la 80% vizionat (minim 5 min) ──────────
            if not next_fetched and total > 300 and total > 0 and current / total >= 0.80:
                next_fetched = True
                next_ep = _get_next_episode(tv_id, season, episode)
                if next_ep:
                    next_s, next_e, ep_title, ep_overview = next_ep
                    _start_prefetch(next_s, next_e)
                    xbmc.log(f'[Samus] Prefetch pornit la 80%: S{next_s:02d}E{next_e:02d}', xbmc.LOGINFO)

            # ── Overlay autoplay în ultimele N secunde ───────────────────────
            if not overlay_shown and total > 120 and 0 < remaining <= trigger_secs:
                overlay_shown = True
                if not next_fetched:
                    next_fetched = True
                    next_ep = _get_next_episode(tv_id, season, episode)
                    if next_ep:
                        next_s, next_e, ep_title, ep_overview = next_ep

                if next_ep:
                    _start_prefetch(next_s, next_e)  # no-op dacă deja pornit

                    ep_label = f"S{next_s:02d}E{next_e:02d}"
                    if ep_title:
                        ep_label += f'  ·  {ep_title}'
                    _poster = details.get('poster_path', '')
                    overlay = _AutoplayOverlay(
                        'overlay_autoplay.xml',
                        addon.getAddonInfo('path'),
                        'Default', '1080i',
                        show_name=show_name,
                        ep_label=ep_label,
                        countdown_secs=int(remaining),
                        poster_url='https://image.tmdb.org/t/p/w342' + _poster if _poster else '',
                        overview=ep_overview,
                    )
                    overlay.doModal()
                    result = overlay.result
                    del overlay

                    if result == _AutoplayOverlay.PLAY:
                        if scrape_thread:
                            scrape_thread.join(timeout=8)
                        if preresolve_thread:
                            preresolve_thread.join(timeout=5)

                        pr  = scrape_result.get('preresolve') or {}
                        pre_url = pr.get('url')
                        pre_src = pr.get('source')

                        if pre_url and pre_src and time.time() - pr.get('ts', 0) < 180:
                            # Fast path — URL deja rezolvat, redare directă fără nou proces
                            li = xbmcgui.ListItem()
                            li.setProperty('IsPlayable', 'true')
                            _set_video_info_episode(
                                li,
                                f"{show_title}.S{next_s:02d}E{next_e:02d}",
                                show_title, next_s, next_e, imdb_id,
                            )
                            stream_url = pre_url.split('|')[0] if '|' in pre_url else pre_url
                            if '.m3u8' in stream_url:
                                li.setMimeType('application/vnd.apple.mpegurl')
                                li.setContentLookup(False)
                                li.setProperty('inputstream', 'inputstream.adaptive')
                                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                                if '|' in pre_url:
                                    hs = pre_url.split('|', 1)[1]
                                    li.setProperty('inputstream.adaptive.stream_headers', hs)
                                    li.setProperty('inputstream.adaptive.manifest_headers', hs)
                            li.setPath(stream_url if '.m3u8' in stream_url else pre_url)
                            xbmc.Player().play(li.getPath(), li)
                            _start_history_tracker(
                                tmdb_id=tv_id, media_type='tv',
                                title=show_name,
                                poster=details.get('poster_path') or '',
                                season=next_s, episode=next_e, plot='',
                            )
                            xbmc.log(f'[Samus] Autoplay fast-path: {pre_src.get("label", "")}', xbmc.LOGINFO)
                        else:
                            # Fallback — salvăm cache și pornim via RunPlugin
                            bg_sources = scrape_result.get('sources') or []
                            if bg_sources:
                                _save_autoplay_cache(
                                    tv_id, next_s, next_e, bg_sources,
                                    quality_pref=selected.get('quality'),
                                    is_torrent_pref=selected.get('is_torrent', False),
                                    preresolve=pr or None,
                                )
                            kv = [
                                ('action',  'play_episode'),
                                ('tv_id',   str(tv_id)),
                                ('season',  str(next_s)),
                                ('episode', str(next_e)),
                            ]
                            if preferred:
                                kv.append(('preferred_provider', preferred))
                            qs = '&'.join(f'{k}={v}' for k, v in kv)
                            xbmc.executebuiltin(f'RunPlugin(plugin://plugin.video.samusxui?{qs})')
                    break
        except Exception as e:
            xbmc.log(f'[Samus] autoplay overlay eroare: {e}', xbmc.LOGWARNING)
        xbmc.sleep(1000)


def resolve_trailer_url(video_id):
    """Extract direct stream URL for a YouTube video via yt-dlp. Returns URL or None."""
    try:
        import yt_dlp
        opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
            'geo_bypass': True,
            'geo_bypass_country': 'US',
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
            if info:
                stream_url = info.get('url')
                if not stream_url:
                    return None

                # YouTube CDN URLs can be bound to the client headers used by
                # yt-dlp during extraction. Kodi accepts them after a pipe.
                headers = {
                    str(key): str(value)
                    for key, value in (info.get('http_headers') or {}).items()
                    if value and str(key).lower() != 'accept-encoding'
                }
                if headers:
                    xbmc.log(
                        '[SamusXUI/trailer] forwarding headers: '
                        + ', '.join(sorted(headers)),
                        xbmc.LOGINFO,
                    )
                    stream_url += '|' + urllib.parse.urlencode(headers)
                return stream_url
    except Exception as e:
        xbmc.log(f'[SamusXUI/trailer] yt-dlp failed: {e}', xbmc.LOGWARNING)
    return None


def play_trailer(video_id, stream_url=None):
    """Redă trailerul YouTube via URL direct. Returnează True dacă redarea a pornit."""
    if not stream_url:
        stream_url = resolve_trailer_url(video_id)
        xbmc.log(f'[SamusXUI/trailer] yt-dlp url={bool(stream_url)}', xbmc.LOGINFO)

    if not stream_url:
        xbmc.log('[SamusXUI/trailer] unavailable', xbmc.LOGWARNING)
        return False

    li = xbmcgui.ListItem(path=stream_url)
    p = xbmc.Player()
    p.play(stream_url, li)
    deadline = 15
    while deadline > 0 and not p.isPlaying():
        xbmc.sleep(200)
        deadline -= 0.2
    return True
