# -*- coding: utf-8 -*-
"""Webtor ca motor de redare pentru torrente (api.webtor.io/v1).

Spre deosebire de `webtor.py`, care e clientul pentru descoperirea de surse prin
addonul Stremio de pe serverul Thrax, aici pornim de la un infohash pe care l-am
găsit noi (Torrentio, TorrentDB, FileList…) și cerem un URL redabil — rolul pe
care îl joacă TorrServer și libtorrent, doar că munca o face serverul lor.

Lanțul: POST /resource (magnet) → GET /resource/{id}/list → GET .../export/{id}.

Capcane găsite la explorarea API-ului (2026-08-09):
  * `POST /resource` cere **`Content-Type: text/plain`**; cu tipul implicit al
    unui client HTTP obișnuit răspunde `400 "the body must be a .torrent file
    or a magnet uri"`, ceea ce sună a magnet stricat, dar nu e;
  * răspunsul lui `/export` are două forme de URL: `download` e fișierul brut,
    cu `Accept-Ranges` (deci seek în Kodi), iar `stream` e HLS transcodat în
    segmente de 2 s. Folosim `download`, ca să nu ardem cotă pe transcodare;
  * URL-urile de export sunt **de scurtă durată și poartă propria autorizare**
    (JWT în query). Documentația lor cere explicit să nu fie stocate, deci
    exportul se face la redare, nu când construim lista de surse — care oricum
    e cache-uită 10 minute;
  * tokenul conține `remoteAddress` și `rate` (20 Mbps pe tier-ul bronze).
    Legarea de IP n-a putut fi verificată (toate mașinile de test ies prin
    același IP public), dar dacă e reală, exportul trebuie făcut de pe
    dispozitivul care redă — motiv în plus să stea aici, nu pe server.
"""
import json
import os
import time
import urllib.parse

import requests
import xbmc

BASE = 'https://api.webtor.io/v1'
_LABEL = '[Samus/Webtor]'

# Extensiile pe care le acceptăm ca fișier de redat — aceeași grijă ca la
# celelalte motoare: un torrent poate conține un .exe cu nume de film.
_VIDEO_EXT = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts', '.webm', '.flv',
              '.mpg', '.mpeg', '.wmv', '.m2ts'}


class WebtorError(Exception):
    """Eroare de la API, cu mesajul lor păstrat pentru afișare."""


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'{_LABEL} {msg}', level)


def _headers(api_key):
    return {'Authorization': f'Bearer {api_key}'}


def _check(r, what):
    if r.status_code == 401:
        raise WebtorError('cheie API invalidă')
    if r.status_code == 402:
        raise WebtorError('abonament necesar pentru această operație')
    if r.status_code == 429:
        raise WebtorError(f'prea multe cereri, reia peste {r.headers.get("Retry-After", "?")}s')
    if r.status_code == 408:
        raise WebtorError('magnetul nu s-a rezolvat la timp (torrent fără seederi?)')
    if not r.ok:
        try:
            msg = r.json().get('error', {}).get('message') or r.text[:120]
        except ValueError:
            msg = r.text[:120]
        raise WebtorError(f'{what}: HTTP {r.status_code} — {msg}')
    return r


def store_resource(api_key, magnet, timeout=180):
    """Pune torrentul în store și întoarce infohash-ul.

    Nu adaugă nimic în biblioteca utilizatorului — asta ar cere `POST /library`.
    """
    r = requests.post(
        f'{BASE}/resource',
        headers={**_headers(api_key), 'Content-Type': 'text/plain'},
        data=magnet.encode('utf-8'),
        timeout=timeout,
    )
    _check(r, 'store resource')
    return r.json()['id']


def list_files(api_key, resource_id, timeout=60):
    r = requests.get(
        f'{BASE}/resource/{resource_id}/list',
        headers=_headers(api_key),
        params={'output': 'list', 'limit': 500},
        timeout=timeout,
    )
    _check(r, 'list')
    return [it for it in (r.json().get('items') or []) if it.get('type') == 'file']


def pick_video(files, file_idx=None, file_name=None):
    """Alege fișierul de redat.

    `file_idx` vine din sursa noastră și se referă la ordinea naturală din
    torrent, care nu e neapărat ordinea întoarsă de `/list` — de aceea ne bazăm
    întâi pe nume, apoi pe indice, și abia la urmă pe „cel mai mare video".
    """
    videos = [f for f in files
              if os.path.splitext(f.get('name') or f.get('path') or '')[-1].lower() in _VIDEO_EXT]
    if not videos:
        return None
    if file_name:
        target = os.path.basename(file_name).lower()
        for f in videos:
            if os.path.basename(f.get('name') or f.get('path') or '').lower() == target:
                return f
    if file_idx is not None and 0 <= file_idx < len(files):
        candidate = files[file_idx]
        if candidate in videos:
            return candidate
    return max(videos, key=lambda f: f.get('size') or 0)


def export_url(api_key, resource_id, content_id, imdb_id=None, kind='download', timeout=90):
    """Întoarce (url, subtitrări). URL-ul e de scurtă durată — cere-l la redare.

    `kind='download'` dă fișierul brut, cu `Accept-Ranges`; `kind='stream'` dă
    HLS transcodat, util doar dacă playerul nu digeră containerul original.
    """
    params = {}
    if imdb_id:
        params['imdb-id'] = imdb_id
    r = requests.get(
        f'{BASE}/resource/{resource_id}/export/{content_id}',
        headers=_headers(api_key), params=params, timeout=timeout,
    )
    _check(r, 'export')
    exports = r.json().get('exports') or {}
    entry = exports.get(kind) or exports.get('download') or exports.get('stream')
    if not entry or not entry.get('url'):
        raise WebtorError('exportul nu conține niciun URL redabil')
    subs = exports.get('subtitles') or {}
    return entry['url'], (subs.get('url') if isinstance(subs, dict) else None)


def warm_up(url, want_bytes=512 * 1024, timeout=180, progress_cb=None):
    """Cere primii octeți înainte să dăm URL-ul playerului. Întoarce True dacă
    au venit date.

    Webtor începe să tragă piesele de la peers abia la prima cerere, iar până
    atunci ține conexiunea deschisă fără să livreze nimic. Kodi renunță după
    20 s (`CCurlFile::CReadState::FillBuffer - Failed: Timeout was reached(28)`),
    deci un torrent pornit la rece eșua chiar cu URL bun. Măsurat pe un torrent
    neatins: primul octet la 6,6 s prima dată, apoi 0,2 s — deci e de ajuns să
    plătim noi așteptarea, o singură dată, cu un mesaj pe ecran.
    """
    start = time.time()
    try:
        r = requests.get(url, headers={'Range': f'bytes=0-{want_bytes - 1}'},
                         timeout=timeout, stream=True)
        if r.status_code not in (200, 206):
            r.close()
            _log(f'încălzire: HTTP {r.status_code}', xbmc.LOGWARNING)
            return False
        got = 0
        for chunk in r.iter_content(65536):
            got += len(chunk)
            if progress_cb and got:
                progress_cb(got, time.time() - start)
            if got >= want_bytes:
                break
        r.close()
        _log(f'încălzire: {got} octeți în {time.time() - start:.1f}s')
        return got > 0
    except Exception as e:
        _log(f'încălzire eșuată după {time.time() - start:.1f}s: {e}', xbmc.LOGWARNING)
        return False


def build_magnet(info_hash, trackers=None):
    tr = ''.join(f'&tr={urllib.parse.quote(t, safe="")}' for t in (trackers or []))
    return f'magnet:?xt=urn:btih:{info_hash}{tr}'
