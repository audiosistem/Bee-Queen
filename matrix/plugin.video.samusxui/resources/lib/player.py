# -*- coding: utf-8 -*-
from __future__ import annotations
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape as _xml_escape
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import resolveurl
import threading
from resources.lib import subtitles, db
from resources.lib.stream_info import StreamInfo
from resources.lib.tmdb_bridge import movies, tv, get_english_title
from resources.lib.resolvers import torrentio, torrentdb, perflix, thrax
from resources.lib.resolvers import velaflow as velaflow_resolver
from resources.lib.resolvers import filelist as filelist_resolver
from resources.lib.resolvers import okru as okru_resolver
from resources.lib.resolvers import flixer, vixsrc as vixsrc_resolver, hdhub, webtor as webtor_resolver
from resources.lib.resolvers import yts as yts_resolver
from resources.lib.resolvers import voe as voe_resolver
from resources.lib.resolvers import doodstream as doodstream_resolver
from resources.lib.resolvers import vidlove as vidlove_resolver
from resources.lib.resolvers import vyla as vyla_resolver
from resources.lib.resolvers import moviesapi as moviesapi_resolver
from resources.lib.resolvers import primesrcme as primesrcme_resolver
from resources.lib.resolvers import vidmoly as vidmoly_resolver
from resources.lib.resolvers import telegram as telegram_resolver
from resources.lib.resolvers import abysscdn as abysscdn_resolver
from resources.lib.resolvers import byse as byse_resolver
from resources.lib.resolvers import vsembed as vsembed_resolver
from resources.lib.resolvers import voyo as voyo_resolver
from resources.lib.resolvers import pelispanda as pelispanda_resolver
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
    'voyo':         7,
    'vsembed':      8,
    'vidlove':      6,
    'moviesapi':    6,
    'vyla':        12,   # agregă 40+ scrapere pe server → generos, curge progresiv
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
    """Resolve synchronously so a timed-out helper thread can never be orphaned.

    ResolveURL's network layer applies its own per-request timeouts. Python has
    no safe way to kill a running thread; the old join(timeout) returned while
    that thread was still alive and could deadlock Kodi's Py_EndInterpreter.
    ``timeout`` is retained as a slow-call warning threshold.
    """
    started = time.monotonic()
    try:
        resolved_url = resolveurl.resolve(url)
    except Exception as e:
        xbmc.log(f"[Samus/resolveurl] Eroare: {e}", xbmc.LOGERROR)
        return None
    elapsed = time.monotonic() - started
    if elapsed > timeout:
        xbmc.log(f"[Samus/resolveurl] Apel lent {elapsed:.1f}s pentru URL: {url}",
                 xbmc.LOGWARNING)
    return resolved_url


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


def resolve_torrent(info_hash, file_idx=0, trackers=None, seeds=None, size=None, quality=None, status_cb=None, stats_cb=None, torrent_file=None, file_name=None, title=None, poster=None, imdb_id=None):
    engine_setting = addon.getSetting('torrent_engine') or 'TorrServer'
    if engine_setting == 'libtorrent':
        return resolve_torrent_libtorrent(info_hash, file_idx, trackers, seeds, status_cb=status_cb, stats_cb=stats_cb, torrent_file=torrent_file)
    if engine_setting == 'Webtor':
        return resolve_torrent_webtor(info_hash, file_idx, trackers, status_cb=status_cb, file_name=file_name, imdb_id=imdb_id)
    return resolve_torrent_torrserver(info_hash, file_idx, trackers, seeds, status_cb=status_cb, stats_cb=stats_cb, torrent_file=torrent_file, file_name=file_name, title=title, poster=poster)


def resolve_torrent_webtor(info_hash, file_idx=0, trackers=None, status_cb=None, file_name=None, imdb_id=None):
    """Redare prin api.webtor.io — descărcarea o face serverul lor, noi primim
    un URL HTTP cu `Accept-Ranges`.

    Spre deosebire de TorrServer și libtorrent, aici nu avem statistici de peers
    (nu rulăm noi torrentul), deci `stats_cb` nu se aplică — bara de progres
    rămâne pe mesajele de stare.
    """
    def _status(msg):
        xbmc.log(f'[Samus/Webtor] {msg}', xbmc.LOGINFO)
        if status_cb:
            status_cb(msg)

    api_key = (addon.getSetting('webtor_api_key') or '').strip()
    if not api_key:
        xbmcgui.Dialog().notification('Samus', 'Cheia API Webtor lipsește din setări',
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        return None

    from resources.lib.resolvers import webtor_api

    tr_list = [t[len('tracker:'):] for t in (trackers or []) if t.startswith('tracker:')]
    if not tr_list:
        tr_list = _FALLBACK_TRACKERS

    try:
        _status('Se trimite torrentul către Webtor...')
        resource_id = webtor_api.store_resource(
            api_key, webtor_api.build_magnet(info_hash, tr_list))

        _status('Se citește conținutul torrentului...')
        files = webtor_api.list_files(api_key, resource_id)
        chosen = webtor_api.pick_video(files, file_idx=file_idx, file_name=file_name)
        if not chosen:
            xbmc.log('[Samus/Webtor] torrentul nu conține niciun fișier video', xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('Samus', 'Torrentul nu conține video',
                                          xbmcgui.NOTIFICATION_WARNING, 5000)
            return None

        _status('Se pregătește stream-ul...')
        url, subs = webtor_api.export_url(api_key, resource_id, chosen['id'], imdb_id=imdb_id)
        xbmc.log(f'[Samus/Webtor] {chosen.get("name")} ({chosen.get("size")} B)', xbmc.LOGINFO)
        if subs:
            xbmc.log(f'[Samus/Webtor] subtitrări disponibile: {subs[:80]}', xbmc.LOGDEBUG)

        # Kodi abandonează deschiderea după 20 s, iar Webtor începe să tragă
        # piesele abia la prima cerere — așteptăm noi, cu mesaj pe ecran.
        _status('Se încarcă bufferul (prima pornire e mai lentă)...')
        if not webtor_api.warm_up(url, progress_cb=lambda n, t: _status(
                f'Se încarcă bufferul... {n // 1024} KB în {t:.0f}s')):
            xbmcgui.Dialog().notification('Samus', 'Webtor nu a livrat date (torrent fără seederi?)',
                                          xbmcgui.NOTIFICATION_WARNING, 6000)
            return None
        return url
    except webtor_api.WebtorError as e:
        xbmc.log(f'[Samus/Webtor] {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Samus', f'Webtor: {e}', xbmcgui.NOTIFICATION_ERROR, 6000)
        return None
    except Exception as e:
        xbmc.log(f'[Samus/Webtor] eroare neașteptată: {e}', xbmc.LOGERROR)
        return None





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
        # Verificare de siguranță: fișierul selectat trebuie să aibă extensie video.
        # Torrentele din surse externe pot fi otrăvite cu executabile/arhive deghizate
        # în filme (ex. "1080p Telesync" care e de fapt un .exe) — nu redăm orbește
        # doar pe baza fileIdx-ului primit de la sursă.
        try:
            for f in e.files():
                if f.get('file_id') == ts_idx:
                    fname = f.get('path') or ''
                    fext = os.path.splitext(fname)[-1].lower()
                    if fext and fext not in _VIDEO_EXT:
                        xbmc.log(f'[Samus/TorrServer] Fișier neașteptat ({fext}): {fname!r} — refuz redarea', xbmc.LOGWARNING)
                        xbmcgui.Dialog().notification('Samus', f'Torrent suspect: fișier {fext} în loc de video', xbmcgui.NOTIFICATION_WARNING, 6000)
                        try:
                            e.rem()
                        except Exception:
                            pass
                        return None
                    break
        except Exception as ex:
            xbmc.log(f'[Samus/TorrServer] Verificare fișier eșuată (ignorată): {ex}', xbmc.LOGDEBUG)
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

        # Verificare de siguranță: fișierul selectat trebuie să aibă extensie video —
        # vezi nota din resolve_torrent_torrserver.
        try:
            for f in engine.get_files(tid):
                if f.index == best_idx:
                    fname = f.name.decode('utf-8', errors='replace') if isinstance(f.name, bytes) else f.name
                    fext = os.path.splitext(fname)[-1].lower()
                    if fext and fext not in _VIDEO_EXT:
                        xbmc.log(f'[Samus/libtorrent] Fișier neașteptat ({fext}): {fname!r} — refuz redarea', xbmc.LOGWARNING)
                        xbmcgui.Dialog().notification('Samus', f'Torrent suspect: fișier {fext} în loc de video', xbmcgui.NOTIFICATION_WARNING, 6000)
                        engine.remove_torrent(tid, delete_files=True)
                        return None
                    break
        except Exception as ex:
            xbmc.log(f'[Samus/libtorrent] Verificare fișier eșuată (ignorată): {ex}', xbmc.LOGDEBUG)

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

# Cheia e numele MODULULUI: threaded_resolver o ia din functie, prin
# __module__.split('.')[-1], nu din aliasul de import. Intrarile scrise
# candva ca 'vsembed_resolver' nu se potriveau niciodata, deci evidenta
# sanatatii era inerta tocmai pentru providerii care dau timeout.
_MODULE_TO_PROVIDER = {
    'cinesu':      '[CSU]',  'comet':       '[CMT]',
    'filelist':    '[FLI]',  'flixer':      '[FLX]',
    'hdhub':       '[HDB]',  'hydrahd':     '[HHD]',
    'mediafusion': '[MF]',   'moviesapi':   '[MAP]',
    'peachify':    '[PCH]',  'pelispanda':  '[PPD]',
    'perflix':     '[PFX]',  'sooti':       '[SOT]',
    'thrax':       '[THX]',  'torrentdb':   '[TDB]',
    'torrentio':   '[TIO]',  'velaflow':    '[VLF]',
    'vidapi':      '[VAP]',  'vidlove':     '[VDL]',
    'vidrock':     '[VDR]',  'vixsrc':      '[VXS]',
    'voyo':        '[VOYO]', 'vsembed':     '[VSE]',
    'vyla':        '[VYL]',
    'yts':         '[YTS]',
    'webstreamr':  '[WSR]',  'webtor':      '[WBT]',
}


def threaded_resolver(target, args=(), result=None, index=0, timeout=None):
    mod = getattr(target, '__module__', '').split('.')[-1]
    provider = _MODULE_TO_PROVIDER.get(mod)
    timed_out = threading.Event()

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
            elapsed = time.time() - t0
            # Un provider care ÎNTOARCE surse e sănătos chiar dacă a fost lent
            # (timed_out e setat de bugetul scurt de 1.5s din _wait_for_resolvers).
            # Fără `data or ...`, providerii lenți-dar-buni (vyla ~9s, voyo, vsembed)
            # adunau fail-uri și erau săriți după 3 fetch-uri în 30 min, deși mergeau.
            if provider and (data or not timed_out.is_set()):
                db.provider_health_ok(provider, latency=elapsed, had_results=bool(data))
            xbmc.log(f"[Samus/timing] {mod}.{target.__name__}: {n} surse în {elapsed:.2f}s", xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f"[Samus] Eroare în {target.__name__}: {e}", xbmc.LOGERROR)
            result[index] = []

    t = threading.Thread(target=wrapper, daemon=True)
    t._resolver_timeout = timeout
    t._provider = provider
    t._result_index = index
    t._timeout_event = timed_out
    t.start()
    return t


_PROVIDER_NAMES = {
    '[V]':     'Vidify',       '[ES]':    'Stremio',      '[Z]':     'VidZee',
    '[2E]':    '2Embed',       '[TIO]':   'Torrentio',    '[TDB]':   'TorrentDB',
    '[YTS]':   'YTS',
    '[MF]':    'MediaFusion',  '[CMT]':   'Comet',        '[PFX]':   'Peerflix',
    '[UDX]':   'UIndex',       '[THX]':   'Thrax',        '[PSC]':   'Vidsrcme.ru',
    '[FLX]':   'Flixer',       '[VXS]':   'VixSrc',       '[HDB]':   'HDHub',
    '[WSR]':   'WebStreamr',   '[VDR]':   'VidRock',      '[STF]':   'Stremify',
    '[NBS]':   'NebulaStreams', '[FNS]':   'FlixNest',     '[PLW]':   'PulpWatch',
    '[FHD]':   'FilmeHD',      '[HHD]':   'HydraHD',      '[YAS]':   'Yastream',
    '[NHD]':   'NHDAPI',       '[PSM]':   'PrimeSrc.me',  '[VDL]':   'VidLink',
    '[VDY]':   'Videasy',      '[VSE]':   'VSEmbed',      '[YFX]':   'YFlix',
    '[VOYO]':  'Voyo',
    '[MEB]':   'MultiEmbed',   '[VBT]':   'VidBinge',     '[MAPI]':  'MoviesAPI',
    '[PPD]':   'PelisPanda',   '[SIMDB]': 'StreamIMDb',   '[SOT]':   'Sooti',
    '[MBX]':   'MovieBox',     '[PPR]':   'Popr',        '[CSU]':   'CineSu',
    '[VLF]':   'VelaFlow',    '[FLI]':   'FileList',
    '[PCH]':   'Peachify',
    '[TLX]':   'Tulnex',    '[VAP]':   'VidAPI',
    '[PDN]':   'Pixeldrain',   '[WBT]':   'Webtor',
    '[VYL]':   'Vyla',
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
                if src.get('is_torrent'):
                    quality = src.get('quality', '')
                    base_title = tmdb_original_title or tmdb_title or ''
                    clean = ''.join(c if c.isalnum() or c in ' -.' else '' for c in base_title)
                    dot_parts = [clean.replace(' ', '.').strip('.')]
                    if tmdb_year:
                        dot_parts.append(tmdb_year)
                    if quality:
                        dot_parts.append(quality)
                    title_line = '.'.join(p for p in dot_parts if p)
                    sources.append({
                        'label':      f"{display_prefix} {src.get('label', '')}".strip(),
                        'title_line': title_line or src.get('label', ''),
                        'provider':   label_prefix,
                        'infoHash':   src['infoHash'],
                        'fileIdx':    src.get('fileIdx', 0),
                        'trackers':   src.get('trackers', []),
                        'quality':    quality,
                        'is_torrent': True,
                    })
                    continue
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
                    'thrax_resolved': src.get('thrax_resolved', True),
                }
                sources.append(entry)
        elif label_prefix in ('[TIO]', '[TDB]', '[MF]', '[CMT]', '[PFX]', '[UDX]', '[PPD]', '[VLF]', '[FLI]', '[YTS]'):
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
        elif label_prefix in ('[FLX]', '[VXS]', '[V]', '[Z]', '[WSR]', '[VDR]', '[STF]', '[NBS]', '[FNS]', '[PLW]', '[YAS]', '[NHD]', '[VSE]', '[YFX]', '[VOYO]', '[SIMDB]', '[SOT]', '[MBX]', '[PPR]', '[CSU]', '[PCH]', '[TLX]'):
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


def _piste_subtitrare(player):
    """Pistele de subtitrare ca (index, nume, cod_limba).

    `getAvailableSubtitleStreams()` întoarce doar denumiri, iar Kodi scoate
    din denumire limba pe care o recunoaște („Romanian.vtt" devine
    „(External)" cu language='rum'). Ne trebuie deci și câmpul `language`, pe
    care doar JSON-RPC îl dă. Dacă acesta nu răspunde, ne întoarcem la nume.
    """
    try:
        activi = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 1,
            'method': 'Player.GetActivePlayers'}))).get('result') or []
        pid = next((p['playerid'] for p in activi if p.get('type') == 'video'),
                   activi[0]['playerid'] if activi else 1)
        raspuns = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetProperties',
            'params': {'playerid': pid, 'properties': ['subtitles']}})))
        piste = raspuns.get('result', {}).get('subtitles') or []
        if piste:
            return [(p.get('index', i), p.get('name') or '', p.get('language') or '')
                    for i, p in enumerate(piste)]
    except Exception as e:
        xbmc.log(f'[Samus/subtitrari] JSON-RPC indisponibil: {e}', xbmc.LOGDEBUG)
    return [(i, nume, '') for i, nume in enumerate(player.getAvailableSubtitleStreams() or [])]


def _auto_enable_subtitles():
    """Wait for playback to start, then activate the subtitle track matching the preferred language."""
    player = xbmc.Player()
    monitor = xbmc.Monitor()
    for _ in range(40):
        if monitor.abortRequested():
            return
        if player.isPlaying():
            if monitor.waitForAbort(1.5):
                return
            piste = _piste_subtitrare(player)
            chosen = 0
            if piste:
                pref_langs = [l.strip() for l in (addon.getSetting('subs_languages') or 'ro').split(',') if l.strip()]
                # Două treceri per limbă: întâi după codul de limbă, care
                # marchează subtitrarea principală (cea pe care Kodi a
                # recunoscut-o), apoi după nume, pentru variantele „Romanian2".
                gasit = None
                for lang in pref_langs:
                    for dupa_cod in (True, False):
                        for idx, nume, cod in piste:
                            if (subtitles._cod_limba_potrivit(cod, lang) if dupa_cod
                                    else subtitles._lang_matches(nume, lang)):
                                gasit = (idx, nume, cod, lang)
                                break
                        if gasit:
                            break
                    if gasit:
                        break
                if gasit:
                    chosen = gasit[0]
                    xbmc.log(f'[Samus/subtitrari] alesă „{gasit[1] or gasit[2]}" '
                             f'(index {gasit[0]}, limba {gasit[3]})', xbmc.LOGINFO)
                else:
                    xbmc.log('[Samus/subtitrari] nicio pistă în limbile preferate, '
                             'rămân pe prima', xbmc.LOGINFO)
            player.setSubtitleStream(chosen)
            player.showSubtitles(True)
            return
        if monitor.waitForAbort(0.5):
            return


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


def _credit_names(details, department=None, jobs=()):
    """Extract unique crew names from the credits already returned by TMDb."""
    names = []
    for person in ((details.get('credits') or {}).get('crew') or []):
        if department and person.get('department') != department:
            continue
        if jobs and person.get('job') not in jobs:
            continue
        name = person.get('name') or ''
        if name and name not in names:
            names.append(name)
    return names


def _set_video_info_movie(li, title, year, imdb_id, details=None):
    details = details or {}
    tag = li.getVideoInfoTag()
    tag.setTitle(title)
    if year:
        tag.setYear(int(year))
    if imdb_id:
        tag.setIMDBNumber(imdb_id)
    tag.setMediaType('movie')
    tag.setPlot(details.get('overview') or '')
    tag.setTagLine(details.get('tagline') or '')
    tag.setGenres([g.get('name') for g in details.get('genres', []) if g.get('name')])
    tag.setStudios([s.get('name') for s in details.get('production_companies', []) if s.get('name')])
    tag.setCountries([c.get('name') for c in details.get('production_countries', []) if c.get('name')])
    tag.setDirectors(_credit_names(details, jobs=('Director',)))
    writers = _credit_names(details, department='Writing')
    if writers:
        tag.setWriters(writers)
    premiered = details.get('release_date') or ''
    if premiered:
        tag.setPremiered(premiered)
    runtime = int(details.get('runtime') or 0)
    if runtime:
        tag.setDuration(runtime * 60)
    rating = float(details.get('vote_average') or 0)
    if rating:
        tag.setRating(rating, votes=int(details.get('vote_count') or 0), isdefault=True)


def _set_video_info_episode(li, episode_tag, show_title, season, episode, imdb_id,
                            details=None, ep_data=None):
    details = details or {}
    ep_data = ep_data or {}
    tag = li.getVideoInfoTag()
    tag.setTitle(episode_tag)
    tag.setTvShowTitle(show_title)
    tag.setSeason(season)
    tag.setEpisode(episode)
    if imdb_id:
        tag.setIMDBNumber(imdb_id)
    tag.setMediaType('episode')
    tag.setPlot(ep_data.get('overview') or details.get('overview') or '')
    tag.setGenres([g.get('name') for g in details.get('genres', []) if g.get('name')])
    studios = [s.get('name') for s in details.get('production_companies', []) if s.get('name')]
    if not studios:
        studios = [s.get('name') for s in details.get('networks', []) if s.get('name')]
    tag.setStudios(studios)
    directors = []
    for person in ep_data.get('crew', []) or []:
        if person.get('job') == 'Director' and person.get('name') not in directors:
            directors.append(person.get('name'))
    if directors:
        tag.setDirectors(directors)
    premiered = ep_data.get('air_date') or ''
    if premiered:
        tag.setPremiered(premiered)
        tag.setFirstAired(premiered)
    runtime = int(ep_data.get('runtime') or 0)
    if not runtime:
        runtimes = details.get('episode_run_time') or []
        runtime = int(runtimes[0]) if runtimes else 0
    if runtime:
        tag.setDuration(runtime * 60)
    rating = float(ep_data.get('vote_average') or details.get('vote_average') or 0)
    votes = int(ep_data.get('vote_count') or details.get('vote_count') or 0)
    if rating:
        tag.setRating(rating, votes=votes, isdefault=True)


def _set_playback_art(li, item_data, is_episode=False):
    """Attach TMDb artwork to the playable item exposed through Player.Art()."""
    poster = item_data.get('poster') or ''
    fanart = item_data.get('fanart') or ''
    logo = item_data.get('logo') or ''
    still = item_data.get('still') or ''
    art = {}
    if poster:
        art['poster'] = poster
    art.update({'thumb': still or poster, 'icon': still or poster})
    if still:
        art['landscape'] = still
    if fanart:
        art['fanart'] = fanart
    if logo:
        art['clearlogo'] = logo
        # Aeon Nox Thrax prioritizes the parent-show logo for episodes.
        if is_episode:
            art['tvshow.clearlogo'] = logo
        li.setProperty('logo', logo)
    if is_episode:
        if poster:
            art['tvshow.poster'] = poster
        if fanart:
            art['tvshow.fanart'] = fanart
    if art:
        li.setArt(art)


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
                timeout_event = getattr(t, '_timeout_event', None)
                if timeout_event:
                    timeout_event.set()
                db.provider_health_fail(provider)
            # Succesul și latența sunt înregistrate în wrapper; aici tratăm
            # numai firele care au depășit bugetul comun.


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
            if monitor.waitForAbort(0.5):
                return
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
            # waitForAbort trezește firul imediat la Quit; xbmc.sleep(10000)
            # ținea subinterpretorul viu până la zece secunde după shutdown.
            if monitor.waitForAbort(10):
                return

        # Scrobble stop — Trakt marks as watched if progress > 80%
        if last_duration > 0 and not monitor.abortRequested():
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
            imdb_id=item_data.get('imdb_id') or selected.get('imdb_id'),
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
        if selected.get('thrax_resolved', True):
            _st('Se rezolvă AbyssCDN (Thrax)...')
            stream_url = abysscdn_resolver.resolve_via_thrax(url)
            if not stream_url:
                xbmc.log(f'[ABYSS] Thrax nu a returnat URL pentru {url}', xbmc.LOGWARNING)
                return None, []
            url = stream_url
            is_direct = True
        else:
            # thrax_resolved=false — nu are nevoie de proxy server-side (nu e
            # IP-bound), rezolvăm local (proxy HTTP local propriu, reface
            # schema de chunking sora) ca să nu consumăm banda serverului Thrax
            _st('Se rezolvă AbyssCDN (local)...')
            xbmc.log(f'[ABYSS] thrax_resolved=false — rezolvare locală: {url}', xbmc.LOGINFO)
            try:
                from resources.lib.resolvers import abysscdn_local
                stream_url = abysscdn_local.resolve(url)
            except Exception as e:
                xbmc.log(f'[ABYSS] rezolvare locală eșuată: {e}', xbmc.LOGERROR)
                stream_url = None
            if not stream_url:
                xbmc.log(f'[ABYSS] rezolvare locală nu a returnat URL pentru {url}', xbmc.LOGWARNING)
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
    if not is_direct and 'vixsrc.to/' in url:
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
        _BYSE_DOMAINS = ('bysejikuar.com', 'bysesayeveum.com', 'bysetayico.com',
                         'bysevepoin.com', 'bysezejataos.com', 'bysekoze.com',
                         'bysesukior.com', 'bysefujedu.com', 'bysedikamoum.com',
                         'bysebuho.com', 'bysewihe.com', 'byselapuix.com')
        _is_byse = any(d in url for d in _BYSE_DOMAINS)
        _st('Se rezolvă Byse...' if _is_byse else 'Se rezolvă Filemoon...')
        try:
            if _is_byse:
                # Tokenul SprintCDN este IP-bound: trebuie emis local, nu pe
                # Thrax, dacă serverul și Kodi au egress-uri diferite.
                _byse_started = time.monotonic()
                url = byse_resolver.resolve(url)
                xbmc.log('[Byse] rezolvat în {:.3f}s'.format(
                    time.monotonic() - _byse_started), xbmc.LOGINFO)
                is_direct = True
            else:
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
                    xbmc.log(f'[Filemoon] Thrax error {_r.status_code}: {_r.text[:200]}',
                             xbmc.LOGWARNING)
                    return None, []
        except Exception as _ex:
            xbmc.log(f'[{"Byse" if _is_byse else "Filemoon"}] eroare: {_ex}',
                     xbmc.LOGERROR)
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
        # Proxy-ul local există pentru TorrServer (rădăcina lui servește și
        # FileBrowser-ul pentru subtitrări). Webtor întoarce un HTTPS obișnuit,
        # cu Accept-Ranges, deci un hop de redirect în plus n-ar aduce nimic.
        if (addon.getSetting('torrent_engine') or '') == 'Webtor':
            li.setPath(url)
        else:
            try:
                proxy_url = _start_torr_proxy(url)
                li.setPath(proxy_url)
            except Exception as _pe:
                xbmc.log(f'[Samus/TorrProxy] Pornire eșuată ({_pe}), folosesc URL direct', xbmc.LOGWARNING)
                li.setPath(url)
    else:
        StreamInfo.parse(url).apply(li)

    # Keep dialog visible until fullscreen video is active — covers Kodi's VideoPlayer loading spinner.
    # Exit as soon as AV actually starts (onAVStarted) so we don't block subsequent plugin invocations
    # (e.g. subtitle browse from OSD, which Kodi serializes per-addon).
    av_started = [False]
    playback_failed = [False]

    class _Player(xbmc.Player):
        def onAVStarted(self):
            av_started[0] = True
        def onPlayBackError(self):
            playback_failed[0] = True

    # Instanța trebuie să existe înainte de play(). Pentru invocările fără
    # plugin handle, fluxurile rapide pot emite onAVStarted înainte ca play()
    # să revină; creată după apel, instanța rata evenimentul și raporta fals
    # sursa drept eșuată, deși Kodi o reda deja.
    player = _Player()
    dlg.set_status('Se pornește redarea...')
    if handle == -1:
        player.play(li.getPath(), li)
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

    monitor = xbmc.Monitor()
    fullscreen_hit = False
    for _ in range(150):
        if monitor.abortRequested() or av_started[0] or playback_failed[0]:
            break
        if xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'):
            fullscreen_hit = True
            break
        xbmc.sleep(200)

    # Torrent/proxy streams (TorrServer local proxy) take noticeably longer between
    # OpenFile and the first decoded frame than direct HTTP/CDN sources — the GUI
    # reaches fullscreenvideo (with Kodi's own loading spinner) well before onAVStarted
    # fires. Give those extra grace instead of declaring the source failed the instant
    # our own dialog would have been dismissed (fullscreenvideo stays active across
    # retries too, so we can't just trust it as a success signal on its own).
    if selected.get('is_torrent') and fullscreen_hit and not av_started[0] and not playback_failed[0]:
        for _ in range(100):
            if monitor.abortRequested() or av_started[0] or playback_failed[0]:
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
        results = [None] * 50
        threads = []

        if addon.getSettingBool('use_torrentio') and imdb_id:
            threads.append(threaded_resolver(torrentio.get_movie_sources, (imdb_id,), results, 4))
        if addon.getSettingBool('use_torrentdb') and imdb_id:
            threads.append(threaded_resolver(torrentdb.get_movie_sources, (imdb_id,), results, 5))
        if addon.getSettingBool('use_perflix') and imdb_id:
            threads.append(threaded_resolver(perflix.get_movie_sources, (imdb_id,), results, 8))
        if addon.getSettingBool('use_thrax'):
            threads.append(threaded_resolver(thrax.get_movie_sources, (tmdb_id,), results, 10))
        if addon.getSettingBool('use_flixer'):
            threads.append(threaded_resolver(flixer.get_sources, (tmdb_id, 'movie'), results, 12))
        if addon.getSettingBool('use_hdhub') and imdb_id:
            threads.append(threaded_resolver(hdhub.get_sources, (imdb_id, 'movie'), results, 14))
        if addon.getSettingBool('use_vidlove'):
            threads.append(threaded_resolver(vidlove_resolver.get_sources, (tmdb_id, 'movie'), results, 17, timeout=_RT['vidlove']))
        if addon.getSettingBool('use_moviesapi'):
            threads.append(threaded_resolver(moviesapi_resolver.get_sources, (tmdb_id, 'movie'), results, 18, timeout=_RT['moviesapi']))
        if addon.getSettingBool('use_primesrcme'):
            threads.append(threaded_resolver(primesrcme_resolver.get_sources, (tmdb_id, 'movie'), results, 25))
        if addon.getSettingBool('use_vsembed'):
            threads.append(threaded_resolver(vsembed_resolver.get_sources, (tmdb_id, 'movie'), results, 28, timeout=_RT['vsembed']))
        if addon.getSettingBool('use_voyo'):
            threads.append(threaded_resolver(voyo_resolver.get_sources, (tmdb_id, 'movie', title, year, original_title), results, 29, timeout=_RT['voyo']))
        if addon.getSetting('use_pelispanda') != 'false':
            threads.append(threaded_resolver(pelispanda_resolver.get_sources, (tmdb_id, 'movie', title, year, None, None, original_title), results, 33))
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
        # Slot NOU (48), nu unul liber din cele vechi: pozițiile eliberate de
        # provideri scoși păstrează prefixul lor în lista de mai jos, iar sursa
        # ar apărea sub eticheta altcuiva — exact bug-ul de la Voyo.
        if addon.getSettingBool('use_yts') and imdb_id:
            threads.append(threaded_resolver(yts_resolver.get_sources, (imdb_id, 'movie'), results, 48))
        if addon.getSettingBool('use_vyla'):
            threads.append(threaded_resolver(vyla_resolver.get_sources, (tmdb_id, 'movie'), results, 49, timeout=_RT['vyla']))
        # Wait briefly so the fastest resolvers (THX, vidzee, primesrc) can finish first
        _wait_for_resolvers(threads, budget=1.5, results=results)

        prefixes = ['[V]', '[ES]', '[Z]', '[2E]', '[TIO]', '[TDB]', '[MF]', '[CMT]', '[PFX]', '[UDX]', '[THX]', '[PSC]', '[FLX]', '[VXS]', '[HDB]', '[WSR]', '[VDR]', '[VDL]', '[MAP]', '[FNS]', '[PLW]', '[FHD]', '[HHD]', '[YAS]', '[NHD]', '[PSM]', '[VDL]', '[VDY]', '[VSE]', '[VOYO]', '[MEB]', '[VBT]', '[MAPI]', '[PPD]', '[SIMDB]', '[SOT]', '[MBX]', '[PPR]', '[CSU]', '[VLF]', '[FLI]', '[PCH]', '[TLX]', '[VAP]', '[PDN]', '[WBT]', '[PMV]', '[PGP]', '[YTS]', '[VYL]']
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
    # Subtitrările venite de la sursă (unele aduc 10+ limbi) treceau peste tot
    # lanțul și opreau traducerea: primeai engleză și atât. Acum intră și ele
    # în cascadă, deci orice sursă cu engleză produce română.
    vidzee_subs = selected.get('subtitles', [])
    if not selected.get('is_torrent') and addon.getSettingBool('subs_enabled'):
        toate = list(vidzee_subs) + subtitles.search_vdrk(tmdb_id)
        _subs_to_set = subtitles.asigura_romana(
            toate, subs_path, eticheta=f'movie_{tmdb_id}',
            nota=f'Film: {title} ({year})' if title else '',
            ident={'tmdb_id': tmdb_id, 'type': 'movie', 'imdb_id': imdb_id})
    elif vidzee_subs:
        _subs_to_set = [s.get('url') if isinstance(s, dict) else s
                        for s in vidzee_subs if s]

    # Single dialog for all retries — no flicker between sources.
    _auto_was_selected = _saved_provider is not None

    def _movie_resolver(dlg):
        nonlocal selected
        first = _auto_was_selected
        while selected is not None:
            li = xbmcgui.ListItem(path=selected.get('url', ''))
            li.setProperty('IsPlayable', 'true')
            _set_video_info_movie(li, title, year, imdb_id, details=details)
            _set_playback_art(li, item_data)
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
            return (season, ep_num, ep.get('name', ''), ep.get('overview', ''),
                    ep.get('still_path', ''))

        next_season_data = tv.get_season(tv_id, season + 1)
        for ep in sorted(next_season_data.get('episodes', []), key=lambda e: e.get('episode_number', 0)):
            ep_num = ep.get('episode_number', 0)
            if not _is_aired(ep):
                return None
            return (season + 1, ep_num, ep.get('name', ''), ep.get('overview', ''),
                    ep.get('still_path', ''))
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
        self._still_url  = kwargs.get('still_url', '')
        self._logo_url   = kwargs.get('logo_url', '')
        overview         = kwargs.get('overview', '')
        self._overview   = overview[:220] + '…' if len(overview) > 220 else overview
        self._closed     = False
        self._stop_countdown = threading.Event()
        self._countdown_thread = None
        self._playback_player = None
        self.result      = self.PLAY  # default: play on countdown expiry

    def onInit(self):
        owner = self

        class _OverlayPlayer(xbmc.Player):
            def onPlayBackStopped(self):
                # Stop apăsat de utilizator în ultimele 30 s oprește lanțul.
                owner.result = owner.CANCEL
                owner._closed = True
                owner._stop_countdown.set()
                owner.close()

            def onPlayBackEnded(self):
                # Finalul natural nu trebuie să aștepte ultima secundă rămasă.
                owner.result = owner.PLAY
                owner._closed = True
                owner._stop_countdown.set()
                owner.close()

        self._playback_player = _OverlayPlayer()
        win = xbmcgui.Window(10000)
        win.setProperty('samus.next_show', self._show_name)
        win.setProperty('samus.next_ep', self._ep_label)
        win.setProperty('samus.next_poster', self._poster_url)
        win.setProperty('samus.next_still', self._still_url)
        win.setProperty('samus.next_logo', self._logo_url)
        win.setProperty('samus.next_overview', self._overview)
        win.setProperty('samus.countdown_text', f'Se pornește în {self._total}s')
        xbmc.log(f'[Samus] Countdown autoplay pornit la {self._total}s', xbmc.LOGINFO)
        try:
            self.getControl(5010).setWidth(1920)
            self.setFocus(self.getControl(5001))
        except Exception:
            pass
        self._countdown_thread = threading.Thread(
            target=self._countdown, name='samus-autoplay-countdown'
        )
        self._countdown_thread.start()

    def _countdown(self):
        try:
            bar = self.getControl(5010)
        except Exception:
            bar = None
        win = xbmcgui.Window(10000)
        monitor = xbmc.Monitor()
        for remaining in range(self._total, 0, -1):
            if self._closed or self._stop_countdown.is_set() or monitor.abortRequested():
                return
            win.setProperty('samus.countdown_text', f'Se pornește în {remaining}s')
            if bar:
                try:
                    bar.setWidth(int(1920 * remaining / self._total))
                except Exception:
                    pass
            if self._stop_countdown.wait(1) or monitor.abortRequested():
                return
        if not self._closed:
            self._closed = True
            self.result = self.PLAY
            self.close()

    def onClick(self, control_id):
        self.result = self.PLAY if control_id == 5001 else self.CANCEL
        self._closed = True
        self._stop_countdown.set()
        self.close()

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 110):  # Back / Escape
            self.result = self.CANCEL
            self._closed = True
            self._stop_countdown.set()
            self.close()

    def join_countdown(self):
        self._stop_countdown.set()
        if self._countdown_thread and self._countdown_thread.is_alive():
            self._countdown_thread.join()


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
    if addon.getSettingBool('use_perflix') and imdb_id:
        threads.append(threaded_resolver(perflix.get_tv_sources, (imdb_id, season, episode), results, 8))
    if addon.getSettingBool('use_thrax'):
        threads.append(threaded_resolver(thrax.get_tv_sources, (tv_id, season, episode), results, 10))
    if addon.getSettingBool('use_flixer'):
        threads.append(threaded_resolver(flixer.get_sources, (tv_id, 'tv', season, episode), results, 12))
    if addon.getSettingBool('use_hdhub') and imdb_id:
        threads.append(threaded_resolver(hdhub.get_sources, (imdb_id, 'tv', season, episode), results, 14))
    if addon.getSettingBool('use_vidlove'):
        threads.append(threaded_resolver(vidlove_resolver.get_sources, (tv_id, 'tv', season, episode), results, 17, timeout=_RT['vidlove']))
    if addon.getSettingBool('use_moviesapi'):
        threads.append(threaded_resolver(moviesapi_resolver.get_sources, (tv_id, 'tv', season, episode), results, 18, timeout=_RT['moviesapi']))
    if addon.getSettingBool('use_primesrcme'):
        threads.append(threaded_resolver(primesrcme_resolver.get_sources, (tv_id, 'tv', season, episode), results, 25))
    if addon.getSettingBool('use_vsembed'):
        threads.append(threaded_resolver(vsembed_resolver.get_sources, (tv_id, 'tv', season, episode), results, 28, timeout=_RT['vsembed']))
    if addon.getSetting('use_pelispanda') != 'false':
        threads.append(threaded_resolver(pelispanda_resolver.get_sources, (tv_id, 'tv', details.get('name', ''), None, season, episode, original_name), results, 33))
    if addon.getSettingBool('use_velaflow') and imdb_id:
        threads.append(threaded_resolver(velaflow_resolver.get_tv_sources, (imdb_id, season, episode), results, 39))
    if addon.getSettingBool('use_filelist') and imdb_id:
        threads.append(threaded_resolver(filelist_resolver.get_tv_sources, (imdb_id, season, episode), results, 40))
    if addon.getSettingBool('use_vidapi'):
        threads.append(threaded_resolver(vidapi_resolver.get_sources, (tv_id, 'tv', season, episode), results, 43))
    if addon.getSettingBool('use_webtor') and imdb_id:
        threads.append(threaded_resolver(webtor_resolver.get_sources, (imdb_id, 'tv', season, episode), results, 44))
    if addon.getSettingBool('use_vyla'):
        threads.append(threaded_resolver(vyla_resolver.get_sources, (tv_id, 'tv', season, episode), results, 46, timeout=_RT['vyla']))
    _wait_for_resolvers(threads, results=results)
    prefixes = ['[V]', '[ES]', '[Z]', '[2E]', '[TIO]', '[TDB]', '[MF]', '[CMT]', '[PFX]', '[UDX]', '[THX]', '[PSC]', '[FLX]', '[VXS]', '[HDB]', '[WSR]', '[VDR]', '[VDL]', '[MAP]', '[FNS]', '[PLW]', '[FHD]', '[HHD]', '[YAS]', '[NHD]', '[PSM]', '[VDL]', '[VDY]', '[VSE]', '[YFX]', '[MEB]', '[VBT]', '[MAPI]', '[PPD]', '[SIMDB]', '[SOT]', '[MBX]', '[PPR]', '[CSU]', '[VLF]', '[FLI]', '[PCH]', '[TLX]', '[VAP]', '[WBT]', '[PGP]', '[VYL]']
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


def _ordered_autoplay_candidates(sources, preferred_provider=None, quality_pref=None):
    """Return non-torrent sources in the order worth pre-resolving.

    Keep the provider used by the current episode first, then prefer matching
    quality and direct links.  A list (rather than a single best source) lets
    the silent pre-resolver move on immediately when a host is dead.
    """
    pref_q = _Q_ORDER.get(quality_pref, 3)

    def _key(s):
        return (
            1 if preferred_provider and s.get('provider') == preferred_provider else 0,
            -abs(_Q_ORDER.get(s.get('quality', ''), 2) - pref_q),
            1 if s.get('direct') else 0,
            min(int(s.get('seeds') or 0), 1000),
        )

    return sorted(
        (s for s in sources if not s.get('is_torrent')),
        key=_key,
        reverse=True,
    )


def _probe_autoplay_url(url):
    """Cheaply verify that a pre-resolved HTTP URL really answers.

    Resolution alone is not enough for providers which happily return an
    expired CDN URL.  Read at most one byte using Kodi's URL headers and close
    the response immediately; no video is downloaded and no player is opened.
    """
    if not url or not url.startswith(('http://', 'https://')):
        return bool(url)
    try:
        import requests
        stream = StreamInfo.parse(url)
        if stream.is_expired():
            return False
        headers = dict(stream.headers)
        headers['Range'] = 'bytes=0-0'
        response = requests.get(
            stream.url, headers=headers, stream=True, allow_redirects=True,
            timeout=(4, 8),
        )
        try:
            if response.status_code not in (200, 206):
                return False
            next(response.iter_content(chunk_size=1), b'')
            return True
        finally:
            response.close()
    except Exception as ex:
        xbmc.log(f'[Samus] Pre-resolve probe eșuat: {ex}', xbmc.LOGDEBUG)
        return False


def _save_autoplay_cache(tv_id, season, episode, sources, quality_pref=None,
                         is_torrent_pref=None, preresolves=None):
    try:
        data = {
            'tv_id': tv_id, 'season': season, 'episode': episode,
            'sources': sources,
            'quality_pref': quality_pref,
            'is_torrent_pref': is_torrent_pref,
            'preresolves': preresolves or [],  # până la două {source, url, ts}
            'ts': time.time(),
        }
        with open(_AUTOPLAY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        pre_tag = f' + {len(preresolves or [])} pre-resolve' if preresolves else ''
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
                time.time() - data.get('ts', 0) < 1200):
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
    show_title = details.get('name', 'Unknown')
    original_name = (details.get('original_name') or None)
    ep_data = {}
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
        'still':  'https://image.tmdb.org/t/p/w780' + ep_data['still_path']
                  if ep_data.get('still_path') else '',
    }

    cached = _load_autoplay_cache(tv_id, season, episode)
    _autoplay_invocation = cached is not None
    if cached:
        sources = cached['sources']
        xbmc.log(f'[Samus] Autoplay cache: {len(sources)} surse pre-scraped pentru S{season:02d}E{episode:02d}', xbmc.LOGINFO)

        # Inject pre-resolved source at the front if it's still fresh. Prefetch
        # starts well before the credits, so three minutes was too short for a
        # normal 40-50 minute episode.
        prepared = cached.get('preresolves') or []
        # Compatibilitate cu fișierul scris de beta5/beta6.
        if not prepared and cached.get('preresolve'):
            prepared = [cached['preresolve']]
        cached_preselected = None
        injected = []
        for pr in prepared[:2]:
            if not (pr.get('url') and pr.get('source') and
                    time.time() - pr.get('ts', 0) < 900 and
                    _probe_autoplay_url(pr['url'])):
                continue
            pre_source = dict(pr['source'])
            pre_source['url'] = pr['url']
            pre_source['direct'] = True
            injected.append(pre_source)
        if injected:
            original_urls = {pr.get('source', {}).get('url') for pr in prepared}
            sources = injected + [s for s in sources if s.get('url') not in original_urls]
            cached_preselected = injected[0]
            xbmc.log(f'[Samus] Autoplay: {len(injected)} surse pre-rezolvate injectate',
                     xbmc.LOGINFO)

        selected = cached_preselected or _autoselect_source(
            sources, preferred_provider,
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
    # O tranziție autoplay nu trebuie blocată de dialogul „Continuă?”. Cache-ul
    # efemer identifică fără ambiguitate invocarea lansată de episodul anterior.
    if (not _autoplay_invocation and h and
            h['position'] > 60 and h['percent'] < 85):
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
        _subs_to_set = [s.get('url') if isinstance(s, dict) else s
                        for s in vidzee_subs if s]
    elif not selected.get('is_torrent') and addon.getSettingBool('subs_enabled'):
        # Ca la filme: subtitrările sursei intră şi ele în cascadă, altfel
        # opreau traducerea şi rămâneai cu engleza.
        toate = list(vidzee_subs) + subtitles.search_vdrk(tv_id, season=season, episode=episode)
        _nota_ep = f'Serial, sezonul {season} episodul {episode}'
        _subs_to_set = subtitles.asigura_romana(
            toate, subs_path, eticheta=f'tv_{tv_id}_s{season}e{episode}',
            nota=_nota_ep,
            ident={'tmdb_id': tv_id, 'type': 'tv', 'imdb_id': imdb_id,
                   'season': season, 'episode': episode})
        # Dacă a fost nevoie de traducere aici, cel mai probabil va fi
        # nevoie și la următorul: îl pregătim cât timp se uită la ăsta.
        if not subtitles.are_romana(toate):
            subtitles.pregateste_urmatorul(tv_id, season, episode, _nota_ep)

    # Single dialog for all retries — no flicker between sources.
    remaining = [s for s in sources if s is not selected]
    _play_ok = [False]
    _first_attempt = [True]

    def _tv_resolver(dlg):
        nonlocal selected
        while selected is not None:
            li = xbmcgui.ListItem(path=selected.get('url', ''))
            li.setProperty('IsPlayable', 'true')
            _set_video_info_episode(
                li, episode_tag, show_title, season, episode, imdb_id,
                details=details, ep_data=ep_data,
            )
            _set_playback_art(li, item_data, is_episode=True)
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

    # Sursele sunt rezolvate din timp; overlay-ul trebuie să ocupe numai
    # ultimele 30 s, indiferent de o valoare veche salvată în setări.
    trigger_secs = 30

    next_ep            = None
    next_s = next_e = ep_title = ep_still_path = None
    next_fetched       = False
    overlay_shown      = False
    preferred          = selected.get('provider')
    show_name          = details.get('name', '')
    scrape_result      = {'sources': None, 'preresolves': []}
    scrape_thread      = None
    preresolve_thread  = None
    prefetch_cancel    = threading.Event()

    def _start_prefetch(ns, ne):
        nonlocal scrape_thread, preresolve_thread
        if scrape_thread is not None:
            return  # deja pornit

        def _bg_scrape(r=scrape_result, _ns=ns, _ne=ne):
            try:
                if prefetch_cancel.is_set() or _mon.abortRequested():
                    return
                r['sources'] = _fetch_tv_sources(tv_id, imdb_id, _ns, _ne, details)
                xbmc.log(f'[Samus] BG scrape: {len(r["sources"])} surse S{_ns:02d}E{_ne:02d}', xbmc.LOGINFO)
            except Exception as ex:
                xbmc.log(f'[Samus] BG scrape eroare: {ex}', xbmc.LOGWARNING)

        def _bg_preresolve(r=scrape_result):
            for _ in range(40):
                if r['sources'] is not None:
                    break
                if prefetch_cancel.wait(0.5) or _mon.abortRequested():
                    return
            srcs = r.get('sources') or []
            candidates = _ordered_autoplay_candidates(
                srcs, preferred_provider=preferred,
                quality_pref=selected.get('quality'),
            )
            prepared_providers = set()
            for candidate in candidates:
                if prefetch_cancel.is_set() or _mon.abortRequested():
                    return
                provider_key = candidate.get('provider') or candidate.get('label') or ''
                if provider_key in prepared_providers:
                    continue
                try:
                    xbmc.log(f'[Samus] Pre-resolve încearcă: {candidate.get("label", "")}', xbmc.LOGINFO)
                    pre_url, _ = _resolve_url(candidate)
                    if pre_url and _probe_autoplay_url(pre_url):
                        # A doua rezervă trebuie să fie independentă de prima.
                        prepared_providers.add(provider_key)
                        r['preresolves'].append({
                            'source': candidate, 'url': pre_url, 'ts': time.time(),
                        })
                        xbmc.log(f'[Samus] Pre-resolve verificat OK: {candidate.get("label", "")}', xbmc.LOGINFO)
                        if len(r['preresolves']) >= 2:
                            return
                        continue
                    xbmc.log(f'[Samus] Pre-resolve link nereproductibil: {candidate.get("label", "")}', xbmc.LOGWARNING)
                except Exception as ex:
                    xbmc.log(f'[Samus] Pre-resolve eșuat, încerc următoarea sursă: {ex}', xbmc.LOGWARNING)
            xbmc.log('[Samus] Pre-resolve: nicio sursă HTTP redabilă', xbmc.LOGWARNING)

        # Firele nu sunt daemon: sunt oprite și reunite explicit mai jos, ca
        # subinterpretorul Kodi să nu ajungă la Py_EndInterpreter cu fire vii.
        scrape_thread = threading.Thread(target=_bg_scrape, name='samus-next-scrape')
        scrape_thread.start()
        preresolve_thread = threading.Thread(target=_bg_preresolve, name='samus-next-resolve')
        preresolve_thread.start()

    while _pl.isPlayingVideo() and not _mon.abortRequested():
        try:
            total     = _pl.getTotalTime()
            current   = _pl.getTime()
            remaining = total - current

            # Începe cu cel puțin ~10 minute înainte de final (sau la 65%).
            # Astfel există timp pentru mai multe hosturi, dar URL-ul obținut nu
            # stă inutil de la începutul unui episod lung.
            if (not next_fetched and total > 300 and total > 0 and
                    (current / total >= 0.65 or remaining <= 600)):
                next_fetched = True
                next_ep = _get_next_episode(tv_id, season, episode)
                if next_ep:
                    next_s, next_e, ep_title, ep_overview, ep_still_path = next_ep
                    _start_prefetch(next_s, next_e)
                    xbmc.log(f'[Samus] Prefetch pornit în fundal: S{next_s:02d}E{next_e:02d}', xbmc.LOGINFO)

            # ── Overlay autoplay în ultimele N secunde ───────────────────────
            if not overlay_shown and total > 120 and 0 < remaining <= trigger_secs:
                overlay_shown = True
                if not next_fetched:
                    next_fetched = True
                    next_ep = _get_next_episode(tv_id, season, episode)
                    if next_ep:
                        next_s, next_e, ep_title, ep_overview, ep_still_path = next_ep

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
                        countdown_secs=30,
                        poster_url='https://image.tmdb.org/t/p/w342' + _poster if _poster else '',
                        still_url=('https://image.tmdb.org/t/p/w780' + ep_still_path
                                   if ep_still_path else ''),
                        logo_url=item_data.get('logo', ''),
                        overview=ep_overview,
                    )
                    overlay.doModal()
                    result = overlay.result
                    overlay.join_countdown()
                    del overlay

                    if result == _AutoplayOverlay.PLAY:
                        if scrape_thread:
                            scrape_thread.join(timeout=8)
                        if preresolve_thread:
                            preresolve_thread.join(timeout=5)

                        prepared = scrape_result.get('preresolves') or []
                        valid_prepared = [
                            pr for pr in prepared[:2]
                            if (pr.get('url') and pr.get('source') and
                                time.time() - pr.get('ts', 0) < 900)
                        ]
                        # Pornim întotdeauna o invocare nouă play_episode. Ea
                        # consumă instant URL-urile pregătite, apoi instalează
                        # propriul monitor pentru episodul următor. Pornirea
                        # directă prin Player.play rupea lanțul după o tranziție.
                        bg_sources = scrape_result.get('sources') or []
                        if bg_sources:
                            _save_autoplay_cache(
                                tv_id, next_s, next_e, bg_sources,
                                quality_pref=selected.get('quality'),
                                is_torrent_pref=selected.get('is_torrent', False),
                                preresolves=valid_prepared,
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
                        xbmc.log(f'[Samus] Autoplay lanț → S{next_s:02d}E{next_e:02d} '
                                 f'({len(valid_prepared)} surse pregătite)', xbmc.LOGINFO)
                        # PlayMedia creează o invocare redabilă, cu plugin
                        # handle valid. Noua instanță instalează propriul
                        # monitor și continuă lanțul pentru episodul următor.
                        xbmc.executebuiltin(
                            f'PlayMedia(plugin://plugin.video.samusxui?{qs})'
                        )
                    break
        except Exception as e:
            xbmc.log(f'[Samus] autoplay overlay eroare: {e}', xbmc.LOGWARNING)
        if _mon.waitForAbort(1):
            break

    # Nu lăsăm worker-ele de prefetch vii la ieșirea scriptului. În mod normal
    # ele au terminat cu multe minute înainte; la Stop/Quit semnalăm imediat și
    # așteptăm terminarea lor înainte ca Kodi să distrugă subinterpretorul.
    prefetch_cancel.set()
    for _worker in (preresolve_thread, scrape_thread):
        if _worker and _worker.is_alive():
            _worker.join()


_TRAILER_UA = ('Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36')


def _trailer_header_string(*formats):
    headers = {}
    for fmt in formats:
        for name, value in (fmt.get('http_headers') or {}).items():
            if value is not None and name.casefold() not in (
                    'range', 'content-length', 'accept-encoding',
                    # X-Forwarded-For (fake IP) breaks IP-bound googlevideo URLs (403).
                    'x-forwarded-for'):
                headers.setdefault(str(name), str(value))
    headers.setdefault('User-Agent', _TRAILER_UA)
    return urllib.parse.urlencode(headers)


def _trailer_fetch_range(fmt, start, end):
    headers = dict(fmt.get('http_headers') or {})
    headers.setdefault('User-Agent', _TRAILER_UA)
    headers['Range'] = f'bytes={start}-{end}'
    request = urllib.request.Request(fmt['url'], headers=headers)
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read()


def _trailer_mp4_ranges(fmt):
    """Găsește init/index pentru SegmentBase, după implementarea Bendis."""
    data = _trailer_fetch_range(fmt, 0, 1048575)
    pos = 0
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos:pos + 4], 'big')
        box_type = data[pos + 4:pos + 8]
        header_size = 8
        if size == 1 and pos + 16 <= len(data):
            size = int.from_bytes(data[pos + 8:pos + 16], 'big')
            header_size = 16
        if size < header_size:
            break
        if box_type == b'sidx':
            return (0, pos - 1), (pos, pos + size - 1)
        pos += size
    raise ValueError('indexul MP4 sidx lipsește')


def _trailer_build_mpd(video, audio, duration):
    vinit, vindex = _trailer_mp4_ranges(video)
    ainit, aindex = _trailer_mp4_ranges(audio)
    seconds = max(0, int(float(duration or 0)))
    width = int(video.get('width') or 1920)
    height = int(video.get('height') or 1080)
    fps = int(video.get('fps') or 25)
    vbw = int(float(video.get('tbr') or 4000) * 1000)
    abw = int(float(audio.get('abr') or audio.get('tbr') or 128) * 1000)
    asr = int(audio.get('asr') or 44100)
    vcodec = _xml_escape(video.get('vcodec') or 'avc1.640028')
    acodec = _xml_escape(audio.get('acodec') or 'mp4a.40.2')
    vurl = _xml_escape(video.get('url') or '')
    aurl = _xml_escape(audio.get('url') or '')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static" mediaPresentationDuration="PT{seconds}S" minBufferTime="PT4S">
  <Period>
    <AdaptationSet id="1" contentType="video" sar="1:1" subsegmentAlignment="true" subsegmentStartsWithSAP="1">
      <Representation id="v1" bandwidth="{vbw}" width="{width}" height="{height}" frameRate="{fps}" mimeType="video/mp4" codecs="{vcodec}">
        <BaseURL>{vurl}</BaseURL>
        <SegmentBase indexRange="{vindex[0]}-{vindex[1]}"><Initialization range="{vinit[0]}-{vinit[1]}"/></SegmentBase>
      </Representation>
    </AdaptationSet>
    <AdaptationSet id="2" contentType="audio" mimeType="audio/mp4" codecs="{acodec}" subsegmentAlignment="true" subsegmentStartsWithSAP="1">
      <Representation id="a1" bandwidth="{abw}" audioSamplingRate="{asr}">
        <BaseURL>{aurl}</BaseURL>
        <SegmentBase indexRange="{aindex[0]}-{aindex[1]}"><Initialization range="{ainit[0]}-{ainit[1]}"/></SegmentBase>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>'''


def _trailer_progressive_recipe(info):
    candidates = [fmt for fmt in (info.get('formats') or [])
                  if fmt.get('url') and fmt.get('vcodec') not in (None, 'none')
                  and fmt.get('acodec') not in (None, 'none')
                  and int(fmt.get('height') or 0) <= 720]
    candidates.sort(key=lambda fmt: (
        int(fmt.get('height') or 0), float(fmt.get('tbr') or 0)), reverse=True)
    selected = candidates[0] if candidates else info
    url = selected.get('url') or ''
    if not url:
        return None
    headers = _trailer_header_string(selected, info)
    return {'kind': 'direct', 'path': url + ('|' + headers if headers else '')}


def resolve_trailer_url(video_id):
    """Rezolvă trailerul numai cu script.module.yt-dlp, fără pluginuri externe."""
    try:
        import yt_dlp
        opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'cachedir': False,
            'format': ('bestvideo[height<=1080][ext=mp4][vcodec^=avc1]+'
                       'bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'),
            'http_headers': {'User-Agent': _TRAILER_UA},
            # NU geo_bypass: adaugă un X-Forwarded-For fals în http_headers-ul
            # fiecărui format, iar URL-urile googlevideo sunt semnate pe IP-ul real
            # → 403 (IP mismatch) la redare. Trailerele nu-s region-locked oricum.
            'socket_timeout': 5,
            'retries': 0,
            'extractor_retries': 0,
            'fragment_retries': 0,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f'https://www.youtube.com/watch?v={video_id}', download=False)
        if not info:
            return None
        requested = info.get('requested_formats') or []
        video = next((fmt for fmt in requested
                      if fmt.get('vcodec') not in (None, 'none')), None)
        audio = next((fmt for fmt in requested
                      if fmt.get('acodec') not in (None, 'none')), None)
        if video and audio and video.get('ext') == 'mp4' and audio.get('ext') in ('m4a', 'mp4'):
            try:
                from resources.lib import trailer_manifest
                mpd = _trailer_build_mpd(video, audio, info.get('duration'))
                path = trailer_manifest.write_manifest(mpd, video_id)
                if path:
                    height = int(video.get('height') or 0)
                    xbmc.log(f'[SamusXUI/trailer] yt-dlp DASH {height}p', xbmc.LOGINFO)
                    return {
                        'kind': 'mpd', 'path': path,
                        'headers': _trailer_header_string(video, audio),
                    }
                xbmc.log('[SamusXUI/trailer] serviciul MPD nu rulează; fallback progresiv',
                         xbmc.LOGWARNING)
            except Exception as exc:
                xbmc.log(f'[SamusXUI/trailer] MPD eșuat: {exc}', xbmc.LOGWARNING)
        recipe = _trailer_progressive_recipe(info)
        if recipe:
            xbmc.log('[SamusXUI/trailer] yt-dlp progresiv', xbmc.LOGINFO)
        return recipe
    except Exception as exc:
        xbmc.log(f'[SamusXUI/trailer] yt-dlp failed: {exc}', xbmc.LOGWARNING)
        return None


def trailer_listitem(recipe):
    if not recipe:
        return None
    if isinstance(recipe, str):
        recipe = {'kind': 'direct', 'path': recipe}
    path = recipe.get('path') or ''
    if not path:
        return None
    item = xbmcgui.ListItem(path=path)
    item.setContentLookup(False)
    if recipe.get('kind') == 'mpd':
        item.setMimeType('application/dash+xml')
        item.setProperty('inputstream', 'inputstream.adaptive')
        item.setProperty('inputstream.adaptive.stream_headers', recipe.get('headers') or '')
    return item


def _wait_playing(player, seconds):
    deadline = seconds
    while deadline > 0 and not player.isPlaying():
        xbmc.sleep(200)
        deadline -= 0.2
    return player.isPlaying()


def play_trailer(video_id, stream_url=None, title=None, windowed=False, player=None):
    """Redă prin yt-dlp + manifestul persistent al serviciului SamusXUI."""
    p = player or xbmc.Player()
    if not stream_url:
        stream_url = resolve_trailer_url(video_id)
    if not stream_url:
        xbmc.log('[SamusXUI/trailer] unavailable', xbmc.LOGWARNING)
        return False
    item = trailer_listitem(stream_url)
    if item is None:
        return False
    path = stream_url.get('path') if isinstance(stream_url, dict) else stream_url
    p.play(path, item, windowed=windowed)
    return _wait_playing(p, 15)
