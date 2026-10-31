# thrax_auth.py — tokenul de aparat pentru serverul Thrax (copie identică în
# fiecare addon care vorbește cu api.derzis.xyz; sursa e în
# ~/Projects/kodi-testkit/thrax_auth.py).
#
# Până acum addonurile aveau cheia comună scrisă în cod, deci oricine o putea
# copia. Acum fiecare instalare Kodi își cere un token anonim (POST
# /auth/register, ca aplicația Samus) și îl trimite ca X-Thrax-Token. Tokenul
# e unul singur pe aparat, împărțit de toate addonurile, într-un fișier din
# userdata. O dată pe zi verificăm că serverul încă îl recunoaște; dacă nu
# (401), cerem altul.

import json
import os
import time
import urllib.request
import urllib.error

try:
    import xbmc
    import xbmcvfs
    _DIR = xbmcvfs.translatePath("special://profile/addon_data/thrax.auth/")
except Exception:  # în afara Kodi (teste)
    xbmc = None
    _DIR = os.path.join(os.path.expanduser("~"), ".thrax_auth")

BASE = "https://api.derzis.xyz"
_FISIER = os.path.join(_DIR, "token.json")
_VERIFICARE_S = 86400
_PAUZA_DUPA_ESEC_S = 300

_cache = None


def _log(msg):
    if xbmc is not None:
        xbmc.log("[thrax_auth] " + msg, xbmc.LOGINFO)


def _citeste():
    try:
        with open(_FISIER, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _scrie(d):
    try:
        os.makedirs(_DIR, exist_ok=True)
        tmp = _FISIER + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, _FISIER)
    except Exception as e:
        _log("nu pot salva tokenul: %s" % e)


def _cerere(metoda, cale, corp=None, token=None):
    date = json.dumps(corp).encode() if corp is not None else None
    req = urllib.request.Request(BASE + cale, data=date, method=metoda)
    # Cloudflare respinge User-Agent-ul implicit „Python-urllib" (eroarea 1010).
    req.add_header("User-Agent", "Kodi thrax_auth/1")
    req.add_header("Accept", "application/json")
    if date is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Thrax-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _inregistreaza(d):
    if time.time() - d.get("esec", 0) < _PAUZA_DUPA_ESEC_S:
        return None
    model = ""
    if xbmc is not None:
        try:
            model = xbmc.getInfoLabel("System.FriendlyName") or ""
        except Exception:
            pass
    try:
        cod, text = _cerere("POST", "/auth/register",
                            {"platform": "kodi", "model": model[:60], "version": "kodi"})
        token = json.loads(text).get("token") if cod == 200 else None
    except Exception as e:
        cod, token = str(e), None
    if not token:
        _log("înregistrare eșuată (%s)" % cod)
        d["esec"] = time.time()
        _scrie(d)
        return None
    _log("aparat înregistrat")
    _scrie({"token": token, "verificat": time.time()})
    return token


def token():
    """Tokenul aparatului; îl cere sau îl verifică doar când e nevoie."""
    global _cache
    if _cache:
        return _cache
    d = _citeste()
    tok = d.get("token")
    if not tok:
        tok = _inregistreaza(d)
    elif time.time() - d.get("verificat", 0) > _VERIFICARE_S:
        # /auth/account: 401 = tokenul nu mai există; 200/409 = e bun.
        try:
            cod, _ = _cerere("GET", "/auth/account", token=tok)
        except Exception:
            cod = 0
        if cod == 401:
            _log("tokenul nu mai e recunoscut, cer altul")
            tok = _inregistreaza({})
        elif cod:
            d["verificat"] = time.time()
            _scrie(d)
    _cache = tok
    return tok


def client():
    """„<id addon>/<versiune>": serverul numără cererile pe client."""
    try:
        import xbmcaddon
        a = xbmcaddon.Addon()
        return "%s/%s" % (a.getAddonInfo("id"), a.getAddonInfo("version"))
    except Exception:
        return "kodi"


# Amprenta addonului (19 oct 2026): sha256 peste fișierele de cod (.py, .xml),
# cu aceleași excluderi ca arhiva din release.py, care calculează și ea amprenta
# și o urcă pe server. Serverul refuză amprentele necunoscute pentru versiune
# (addon modificat) și versiunile sub minimul acceptat.
_EXT_AMPRENTA = (".py", ".xml")
_amprenta = None


def amprenta_din(fisiere):
    """`fisiere`: perechi (cale relativă cu „/”, octeți). Comună cu release.py."""
    import hashlib
    linii = []
    for rel, date in fisiere:
        parti = rel.split("/")
        if "__pycache__" in parti or ".git" in parti or ".bak" in parti[-1] \
                or rel.endswith((".pyc", ".orig")) or not rel.endswith(_EXT_AMPRENTA):
            continue
        linii.append(rel + "\0" + hashlib.sha256(date).hexdigest())
    return hashlib.sha256("\n".join(sorted(linii)).encode()).hexdigest()[:32]


def _fisiere_addon(radacina):
    for dirpath, dirnames, filenames in os.walk(radacina):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        for nume in filenames:
            if not nume.endswith(_EXT_AMPRENTA):
                continue
            cale = os.path.join(dirpath, nume)
            rel = os.path.relpath(cale, radacina).replace(os.sep, "/")
            try:
                with open(cale, "rb") as f:
                    yield rel, f.read()
            except Exception:
                pass


def amprenta():
    """Amprenta addonului care rulează; o dată pe sesiune Kodi (ținută în
    Window(10000)), ca să nu se recitească fișierele la fiecare cerere."""
    global _amprenta
    if _amprenta:
        return _amprenta
    try:
        import xbmcaddon
        import xbmcgui
        a = xbmcaddon.Addon()
        cheie = "thrax_amprenta_%s_%s" % (a.getAddonInfo("id"), a.getAddonInfo("version"))
        w = xbmcgui.Window(10000)
        _amprenta = w.getProperty(cheie)
        if not _amprenta:
            _amprenta = amprenta_din(_fisiere_addon(a.getAddonInfo("path")))
            w.setProperty(cheie, _amprenta)
    except Exception:
        _amprenta = ""
    return _amprenta


def headers():
    """Antetele de autentificare, de pus lângă celelalte antete ale cererii."""
    tok = token()
    h = {"X-Thrax-Client": client()}
    amp = amprenta()
    if amp:
        h["X-Thrax-Amprenta"] = amp
    if tok:
        h["X-Thrax-Token"] = tok
    return h


def acces_permis():
    """Pentru addonurile care altfel nu cer nimic de la server (Bendis): serverul
    răspunde 503 unei versiuni vechi sau modificate (vezi amprenta). O dată pe
    oră; fără rețea sau cu alt răspuns, addonul merge mai departe."""
    try:
        import xbmcaddon
        import xbmcgui
        a = xbmcaddon.Addon()
        cheie = "thrax_ok_%s_%s" % (a.getAddonInfo("id"), a.getAddonInfo("version"))
        w = xbmcgui.Window(10000)
        v = w.getProperty(cheie)
        if v:
            stare, _, cand = v.partition("|")
            if time.time() - float(cand) < 3600:
                return stare == "1"
    except Exception:
        return True
    h = headers()
    req = urllib.request.Request(BASE + "/auth/account", method="GET")
    req.add_header("User-Agent", "Kodi thrax_auth/1")
    for k, val in h.items():
        req.add_header(k, val)
    try:
        with urllib.request.urlopen(req, timeout=8):
            ok = True
    except urllib.error.HTTPError as e:
        ok = e.code != 503
    except Exception:
        ok = True
    try:
        w.setProperty(cheie, "%s|%s" % ("1" if ok else "0", time.time()))
    except Exception:
        pass
    return ok


def uita():
    """După un 401 de la server: la următoarea cerere se cere un token nou."""
    global _cache
    _cache = None
    _scrie({})
