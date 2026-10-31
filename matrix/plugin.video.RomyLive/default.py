# -*- coding: utf-8 -*-
# RomyLive+ - Remote loader
# ---------------------------------------------------------------------------
# Acest fisier este intentionat MIC si STABIL: nu contine logica pluginului.
# La fiecare pornire, Kodi ruleaza acest default.py, care descarca versiunea
# curenta a codului real de la REMOTE_URL si o executa pe loc.
#
# Astfel poti actualiza pluginul editand fisierul de pe server
# (https://documentarys.do.am/default.py) - fara sa mai reinstalezi addonul
# in Kodi. Daca nu exista internet sau serverul e indisponibil, se foloseste
# ultima copie descarcata cu succes (cache local), iar daca nici aceea nu
# exista, se foloseste versiunea inclusa in addon (resources/lib/main_fallback.py).
# ---------------------------------------------------------------------------

import os
import sys
import time
import traceback

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

# URL de unde se incarca codul principal al pluginului.
REMOTE_URL = 'https://documentarys.do.am/default.py'
REQUEST_TIMEOUT = 8  # secunde

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')


def _translate(path):
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        return xbmc.translatePath(path)


ADDON_PATH = _translate(ADDON.getAddonInfo('path'))
PROFILE_PATH = _translate(ADDON.getAddonInfo('profile'))

if not xbmcvfs.exists(PROFILE_PATH):
    xbmcvfs.mkdirs(PROFILE_PATH)

CACHE_FILE = os.path.join(PROFILE_PATH, 'default_remote_cache.py')
# __file__ folosit la exec: pastreaza calea acestui loader, ca sa functioneze
# importurile relative din codul remote (ex: `from categorize import ...`),
# care isi calculeaza folderul addon-ului din dirname(__file__).
LOCAL_MAIN_FILE = os.path.join(ADDON_PATH, 'default.py')
FALLBACK_FILE = os.path.join(ADDON_PATH, 'resources', 'lib', 'main_fallback.py')


def _remote_enabled():
    try:
        return ADDON.getSetting('remote_loader_enabled') != 'false'
    except Exception:
        return True


def _remote_url():
    try:
        url = ADDON.getSetting('remote_loader_url')
        return url.strip() if url and url.strip() else REMOTE_URL
    except Exception:
        return REMOTE_URL


def _log(msg, level=xbmc.LOGINFO):
    try:
        xbmc.log('[{0}] {1}'.format(ADDON_ID, msg), level)
    except Exception:
        pass


def _download_remote(url):
    """Descarca sursa curata din URL, cu bypass de cache la nivel de server/proxy."""
    sep = '&' if '?' in url else '?'
    bust_url = '{0}{1}_t={2}'.format(url, sep, int(time.time()))
    headers = {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Kodi RomyLive+ remote-loader)'
    }

    try:
        import requests
        resp = requests.get(bust_url, timeout=REQUEST_TIMEOUT, headers=headers)
        resp.raise_for_status()
        return resp.content.decode('utf-8')
    except Exception as exc:
        _log('Descarcare cu "requests" a esuat: {0}'.format(exc), xbmc.LOGWARNING)

    try:
        if sys.version_info[0] >= 3:
            import urllib.request as urllib_request
        else:
            import urllib2 as urllib_request
        req = urllib_request.Request(bust_url, headers=headers)
        raw = urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT).read()
        return raw.decode('utf-8')
    except Exception as exc:
        _log('Descarcare cu "urllib" a esuat: {0}'.format(exc), xbmc.LOGWARNING)

    return None


def _read_text_vfs(path):
    try:
        if not xbmcvfs.exists(path):
            return None
        f = xbmcvfs.File(path)
        try:
            data = f.readBytes() if hasattr(f, 'readBytes') else f.read()
        finally:
            f.close()
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return data
    except Exception as exc:
        _log('Citire cache a esuat ({0}): {1}'.format(path, exc), xbmc.LOGWARNING)
        return None


def _write_cache(content):
    try:
        f = xbmcvfs.File(CACHE_FILE, 'w')
        try:
            f.write(content.encode('utf-8') if isinstance(content, str) else content)
        finally:
            f.close()
    except Exception as exc:
        _log('Scriere cache a esuat: {0}'.format(exc), xbmc.LOGWARNING)


def _read_fallback():
    try:
        if os.path.isfile(FALLBACK_FILE):
            with open(FALLBACK_FILE, 'rb') as f:
                return f.read().decode('utf-8')
    except Exception as exc:
        _log('Citire fallback local a esuat: {0}'.format(exc), xbmc.LOGWARNING)
    return None


def _load_source():
    if _remote_enabled():
        url = _remote_url()
        content = _download_remote(url)
        if content:
            _write_cache(content)
            _log('Cod incarcat de la ' + url)
            return content, 'remote'
        _log('Nu s-a putut descarca de la ' + url + '; se incearca cache local.', xbmc.LOGWARNING)
    else:
        _log('Incarcarea remote este dezactivata din setari; se foloseste cache/fallback local.')

    content = _read_text_vfs(CACHE_FILE)
    if content:
        _log('Se foloseste ultima copie salvata local (cache).')
        return content, 'cache'

    content = _read_fallback()
    if content:
        _log('Se foloseste versiunea inclusa in addon (fallback).')
        return content, 'fallback'

    return None, None


# Adrese vechi care nu mai exista pe site, inlocuite inainte de executie.
# Se aplica si pe codul remote (care contine aceleasi constante), deci
# corectia ramane valabila chiar daca serverul remote nu se schimba.
URL_FIXES = {
    'https://veziaici.net/category/c-seriale-romanesti/vizionati-las-fierbinti-toate-sezoanele-integrale/':
    'https://veziaici.net/category/c-seriale-romanesti/serialul-romanesc-de-comedie-las-fierbinti-in-reluare/las-fierbinti-sezonul-30-online-in-reluare-integral/',
}


def _apply_url_fixes(source):
    for old, new in URL_FIXES.items():
        source = source.replace(old, new)
    return source


def _apply_reelshort_poster_fix(source):
    # Reel-short now uses hashed names such as poster-<hash>-w480.webp.
    # Accept those, lazy-load attributes and srcset variants as well.
    old = r'''        m_img = re.search(r'src="([^"]+poster\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.IGNORECASE)'''
    new = r'''        m_img = re.search(r'(?:src|data-src|data-lazy-src|data-original)="([^"]*poster[^"]*\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', block, re.IGNORECASE)
        if not m_img:
            m_img = re.search(r'srcset="([^"]*poster[^"]*\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)\s+\d+w', block, re.IGNORECASE)'''
    if old not in source:
        return source
    return source.replace(old, new, 1)


def _exec_source(source, origin):
    # Aplicam corectia LOCALA dupa definitiile remote, inainte de rutare.
    # Altfel serverul ar suprascrie corectia la fiecare pornire a addonului.
    if ADDON_PATH not in sys.path:
        sys.path.insert(0, ADDON_PATH)
    from desenefaine_fix import patch_source
    import romy_youtube
    # Serverul poate livra un invelis base64/zlib. Aplicam corectiile pe
    # sursa reala, nu pe stub-ul exterior (care nu are meniul definit).
    source = romy_youtube.unpack_source(source)
    source = _apply_url_fixes(source)
    source = _apply_reelshort_poster_fix(source)
    source = patch_source(source)
    source = romy_youtube.patch_source(source)
    exec_globals = {'__name__': '__main__', '__file__': LOCAL_MAIN_FILE}
    origin_label = REMOTE_URL if origin == 'remote' else (CACHE_FILE if origin == 'cache' else FALLBACK_FILE)
    code_obj = compile(source, origin_label, 'exec')
    exec(code_obj, exec_globals)


def main():
    # YouTube este complet local: nu asteapta serverul meniului RomyLive.
    if ADDON_PATH not in sys.path:
        sys.path.insert(0, ADDON_PATH)
    import romy_youtube
    if romy_youtube.handles():
        romy_youtube.run()
        return
    source, origin = _load_source()
    if not source:
        xbmcgui.Dialog().notification(
            'RomyLive+',
            'Nu am putut incarca pluginul (fara internet si fara cache).',
            xbmcgui.NOTIFICATION_ERROR, 5000
        )
        return

    try:
        _exec_source(source, origin)
    except SystemExit:
        raise
    except Exception:
        _log('Eroare la executia codului ({0}):\n{1}'.format(origin, traceback.format_exc()), xbmc.LOGERROR)
        if origin != 'fallback':
            fallback_source = _read_fallback()
            if fallback_source:
                try:
                    _exec_source(fallback_source, 'fallback')
                    return
                except SystemExit:
                    raise
                except Exception:
                    _log('Eroare si la executia fallback-ului:\n{0}'.format(traceback.format_exc()), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            'RomyLive+',
            'A aparut o eroare la incarcarea continutului pluginului.',
            xbmcgui.NOTIFICATION_ERROR, 5000
        )


if __name__ == '__main__':
    main()
