# -*- coding: utf-8 -*-
"""Verificări la pornire, comune addonurilor (copie identică în fiecare; sursa
e în ~/Projects/kodi-testkit/garda.py).

1. Linkurile de redare poartă `g=`, o semnătură cu cheia aparatului, ținută
   lângă tokenul Thrax și comună addonurilor noastre (thraxsearch semnează
   linkurile către sarmis). Fără ea, acțiunile din _PAZITE sunt refuzate.
2. Pe unele aparate addonurile nu rulează (c1).

Refuzurile sunt silențioase: fără dialog, notificare sau jurnal.
"""

import hashlib
import hmac
import json
import os
import secrets
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

_DIR = xbmcvfs.translatePath('special://profile/addon_data/thrax.auth/')
_FISIER = os.path.join(_DIR, 'garda.key')
_PROP_C1 = 'thrax_c1'
_NUME = bytes(b ^ 0x2a for b in b'KFHCDK').decode()
_VERIFICARE_S = 600

# addon → (acțiunile păzite, parametrii care identifică titlul, în ordine)
_PAZITE = {
    'plugin.video.samusxui': (('play_movie', 'play_episode', 'play_asa', 'show_info'),
                              ('tmdb_id', 'tv_id', 'asa_id')),
    'plugin.video.sarmis': (('site_play', 'site_play_ep', 'site_search_page'), ('url', 'q')),
}

try:
    _ID = xbmcaddon.Addon().getAddonInfo('id')
except Exception:
    _ID = ''
ACTIUNI_PAZITE = _PAZITE.get(_ID, ((), ()))[0]

_cheie = None


def _cheia():
    global _cheie
    if _cheie:
        return _cheie
    try:
        with open(_FISIER, 'r') as f:
            _cheie = f.read().strip()
    except Exception:
        _cheie = ''
    if len(_cheie) < 32:
        _cheie = secrets.token_hex(32)
        try:
            os.makedirs(_DIR, exist_ok=True)
            tmp = _FISIER + '.tmp'
            with open(tmp, 'w') as f:
                f.write(_cheie)
            os.replace(tmp, _FISIER)
        except Exception:
            pass
    return _cheie


def semn(action, ident, addon=None):
    """Semnătura linkului `?action=<action>&…` al titlului `ident`, pentru
    addonul `addon` (implicit cel care rulează)."""
    msg = f'{addon or _ID}|{action}|{ident}'.encode()
    return hmac.new(_cheia().encode(), msg, hashlib.sha256).hexdigest()[:20]


def ident(params, addon=None):
    chei = _PAZITE.get(addon or _ID, ((), ()))[1]
    return str(next((params[k] for k in chei if params.get(k)), ''))


def url_semnat(kwargs, addon=None):
    """Adaugă `g` în parametrii unui link, dacă acțiunea e păzită."""
    a = kwargs.get('action', '')
    if a in _PAZITE.get(addon or _ID, ((), ()))[0]:
        kwargs['g'] = semn(a, ident(kwargs, addon), addon)
    return kwargs


def permis(params):
    action = params.get('action', '')
    if action not in ACTIUNI_PAZITE:
        return True
    g = params.get('g', '')
    return bool(g) and hmac.compare_digest(g, semn(action, ident(params)))


def _c1_acum():
    try:
        r = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddons',
            'params': {'properties': ['name']}})))
        for a in (r.get('result') or {}).get('addons') or []:
            if _NUME in (a.get('addonid', '') + ' ' + a.get('name', '')).lower():
                return True
    except Exception:
        pass
    try:
        dirs = os.listdir(xbmcvfs.translatePath('special://home/addons/'))
        return any(_NUME in d.lower() for d in dirs)
    except Exception:
        return False


def c1():
    """Rezultatul se ține 10 minute în Window(10000)."""
    w = xbmcgui.Window(10000)
    v = w.getProperty(_PROP_C1)
    if v:
        stare, _, cand = v.partition('|')
        try:
            if time.time() - float(cand) < _VERIFICARE_S:
                return stare == '1'
        except ValueError:
            pass
    da = _c1_acum()
    w.setProperty(_PROP_C1, f"{'1' if da else '0'}|{time.time()}")
    return da
