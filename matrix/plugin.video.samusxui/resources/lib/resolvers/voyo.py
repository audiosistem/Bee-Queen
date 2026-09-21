# -*- coding: utf-8 -*-
"""Voyo (ProTV Plus) — sursă premium prin predare către plugin.video.voyo.ro.

Nu redăm noi nimic: găsim titlul în catalogul Voyo și dăm mai departe
`plugin://plugin.video.voyo.ro/play_video/<id>`. Autentificarea, regiunea și
Widevine rămân treaba addonului Voyo, care e logat cu contul utilizatorului.

Capcane găsite la explorarea API-ului:
  * `origTitle` chiar e titlul original, dar e gol la ~40% din titluri
    (mai ales producții românești), deci nu ne putem baza doar pe el;
  * căutarea Voyo indexează titlul original chiar dacă afișează doar pe cel
    românesc — de aceea căutăm cu ambele;
  * `releaseDateLabel` înseamnă două lucruri diferite: în rezultatele căutării
    e data publicării pe Voyo (Hancock, film din 2008, apare cu 2026), iar în
    endpointul de detalii e anul real de producție. Folosim doar pe al doilea.
"""
import difflib
import re
import unicodedata

import requests
import xbmc
import xbmcvfs

from resources.lib import db

_LABEL = '[VOYO]'
_ADDON_ID = 'plugin.video.voyo.ro'
_TOKEN_FILE = 'special://profile/addon_data/plugin.video.voyo.ro/token.txt'
_BASE = 'https://apivoyo.cms.protvplus.ro/api/v1/'
_PLAY = 'plugin://plugin.video.voyo.ro/play_video/{0}'

_TTL_HIT = 14 * 24 * 3600     # id-urile Voyo nu se schimbă
_TTL_MISS = 24 * 3600         # catalogul se mai completează
_PRAG = 80

_PREFIX = re.compile(r'^\([A-Z]{2,3}\)\s*')      # "(HU) Spre punctul G"
_ARTICOL = re.compile(r'^(the|a|an|le|la|les|el|los|il|der|die|das)\s+')

_SESS = requests.Session()


# ── Utilitare ────────────────────────────────────────────────────────────────

def _normalizeaza(s):
    if not s:
        return ''
    s = _PREFIX.sub('', s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('ł', 'l').replace('ø', 'o').replace('đ', 'd').lower()
    s = re.sub(r'&', ' and ', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    s = _ARTICOL.sub('', s)
    return re.sub(r'\s+', ' ', s)


def _an(text):
    if not text:
        return None
    m = re.search(r'(19|20)\d{2}', str(text))
    return int(m.group(0)) if m else None


def _scor_titlu(titluri_tmdb, titluri_voyo):
    cel_mai_bun = 0
    for tv in titluri_voyo:
        n_voyo = _normalizeaza(tv)
        if not n_voyo:
            continue
        for t in titluri_tmdb:
            n = _normalizeaza(t)
            if not n:
                continue
            if n == n_voyo:
                s = 100
            else:
                s = int(difflib.SequenceMatcher(None, n, n_voyo).ratio() * 100)
                # "1917" vs "1917: Speranță și moarte" — subtitlu pus de Voyo
                if n_voyo.startswith(n + ' ') or n.startswith(n_voyo + ' '):
                    s = max(s, 88)
            cel_mai_bun = max(cel_mai_bun, s)
    return cel_mai_bun


def _cu_anul(s, an_tmdb, an_voyo):
    """Anul e confirmare, nu filtru primar — și doar cel din detalii e valid."""
    if not (an_tmdb and an_voyo):
        return s
    d = abs(an_tmdb - an_voyo)
    if d == 0:
        return min(100, s + 6)
    if d == 1:
        return min(100, s + 2)
    if d > 2:
        return max(0, s - 30)
    return s


# ── Acces la Voyo ────────────────────────────────────────────────────────────

def _addon_instalat():
    try:
        import xbmcaddon
        xbmcaddon.Addon(_ADDON_ID)
        return True
    except Exception:
        return False


def _token():
    try:
        if not xbmcvfs.exists(_TOKEN_FILE):
            return ''
        with xbmcvfs.File(_TOKEN_FILE) as fh:
            return fh.read().strip()
    except Exception:
        return ''


def _headers(token):
    return {
        'Authorization': 'Bearer ' + token,
        'X-DeviceType': 'PC', 'X-DeviceOS': 'LINUX', 'X-DeviceOSVersion': '1.0',
        'X-DeviceManufacturer': 'Linux', 'X-DeviceModel': 'Kodi', 'X-DeviceName': 'Kodi',
    }


def _cauta(interogare, headers):
    try:
        r = _SESS.get(_BASE + 'search', params={'query': interogare},
                      headers=headers, timeout=8)
        if not r.ok:
            return []
        out = []
        for rg in r.json().get('resultGroups', []):
            for res in rg.get('results', []):
                c = res.get('content') or {}
                if c.get('id'):
                    out.append({'id': c['id'], 'type': c.get('type'),
                                'title': c.get('title')})
        return out
    except Exception as e:
        xbmc.log(f'{_LABEL} căutare {interogare!r}: {e}', xbmc.LOGWARNING)
        return []


def _detalii(cid, headers):
    cale = 'movie/' if cid.startswith('movie') else 'tvshow/'
    try:
        r = _SESS.get(_BASE + cale + cid, headers=headers, timeout=8)
        if not r.ok:
            return {}
        c = (r.json() or {}).get('content') or {}
        return {'title': c.get('title'), 'origTitle': c.get('origTitle') or '',
                'an': _an(c.get('releaseDateLabel'))}
    except Exception as e:
        xbmc.log(f'{_LABEL} detalii {cid}: {e}', xbmc.LOGWARNING)
        return {}


def _potriveste(titluri, an, tip, headers, verifica=3):
    vazute, candidati = set(), []
    for q in titluri:
        for c in _cauta(q, headers):
            if c['id'] not in vazute:
                vazute.add(c['id'])
                candidati.append(c)

    tipuri = ('movie',) if tip == 'movie' else ('tvshow', 'show')
    candidati = [c for c in candidati if c['type'] in tipuri]
    if not candidati:
        return None

    candidati.sort(key=lambda c: _scor_titlu(titluri, [c['title']]), reverse=True)

    best, best_s = None, 0
    for c in candidati[:verifica]:
        det = _detalii(c['id'], headers)
        s = _cu_anul(_scor_titlu(titluri, [det.get('origTitle'), det.get('title'),
                                           c['title']]), an, det.get('an'))
        if s > best_s:
            best, best_s = {'id': c['id'], 'title': det.get('title') or c['title']}, s
        if best_s >= 100:
            break
    return dict(best, scor=best_s) if best and best_s >= _PRAG else None


# ── API public ───────────────────────────────────────────────────────────────

def get_sources(tmdb_id, media_type='movie', title=None, year=None, original_title=None):
    """Sursă unică Voyo, sau [] dacă titlul nu e în catalog / addonul lipsește.

    Serialele nu sunt încă acoperite: potrivirea episodului cere maparea
    sezon/episod peste numerotarea Voyo, iar un episod greșit e mai rău decât
    nicio sursă.
    """
    if media_type != 'movie':
        return []
    if not _addon_instalat():
        return []

    cheie = f'voyo_match_{media_type}_{tmdb_id}'
    inreg = db.cache_get(cheie, _TTL_HIT)
    if inreg:
        return _ca_sursa(inreg)
    # Ratarea se ține mai scurt decât potrivirea: catalogul se mai completează,
    # dar un id găsit nu se schimbă.
    if inreg == {} and db.cache_get(cheie, _TTL_MISS) == {}:
        return []

    token = _token()
    if not token:
        xbmc.log(f'{_LABEL} addon instalat dar fără token — utilizator nelogat',
                 xbmc.LOGDEBUG)
        return []

    titluri = [t for t in (original_title, title) if t]
    if not titluri:
        return []

    gasit = _potriveste(titluri, _an(year), media_type, _headers(token))
    db.cache_set(cheie, gasit or {})
    if not gasit:
        xbmc.log(f'{_LABEL} {titluri[0]!r}: nu e în catalog', xbmc.LOGDEBUG)
        return []

    xbmc.log(f'{_LABEL} {titluri[0]!r} -> {gasit["id"]} '
             f'({gasit["title"]!r}, scor {gasit["scor"]})', xbmc.LOGINFO)
    return _ca_sursa(gasit)


def _ca_sursa(m):
    # title_line ajunge în eticheta din listă, lângă numele providerului; punem
    # titlul de pe Voyo, care diferă adesea de cel căutat („1917" e acolo
    # „1917: Speranță și moarte") și confirmă vizual că potrivirea e bună.
    return [{
        'url':          _PLAY.format(m['id']),
        'provider':     _LABEL,
        'quality':      '1080p',
        'title_line':   m.get('title') or 'Voyo',
        'display_name': 'Voyo',
        'direct':       True,
        'subtitles':    [],
    }]
