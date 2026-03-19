# -*- coding: utf-8 -*-
"""
OnTV
"""
import json
import os
import threading
import xbmcvfs

GIST_URL    = 'https://gist.githubusercontent.com/nnllv0id/a8bca35c256e0fcc73f41a58a125c044/raw/servers.json'
_CACHE_FILE = xbmcvfs.translatePath('special://temp/ontv_servers.json')
_GIST_TS    = xbmcvfs.translatePath('special://temp/ontv_gist_ts.flag')


def _carregar_cache():
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _fetch_gist():
    import time
    from urllib.request import urlopen, Request
    url = GIST_URL + '?t=' + str(int(time.time()))
    req = Request(url, headers={
        'User-Agent':    'Kodi/OnTV-Addon',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma':        'no-cache',
        'Expires':       '0',
    })
    resp = urlopen(req, timeout=10)
    return json.loads(resp.read().decode('utf-8'))


def _ja_foi_ao_gist_hoje():
    """Verifica se já foi ao Gist nos últimos 30 minutos."""
    import time
    try:
        if os.path.exists(_GIST_TS):
            with open(_GIST_TS, 'r') as f:
                ts = float(f.read().strip())
            if time.time() - ts < 1800:  # 30 minutos
                return True
    except Exception:
        pass
    return False


def _marcar_gist_visitado():
    import time
    try:
        with open(_GIST_TS, 'w') as f:
            f.write(str(time.time()))
    except Exception:
        pass


def carregar_servidores():
    import xbmc
    # Se já foi ao Gist nos últimos 30 minutos, usar cache
    if _ja_foi_ao_gist_hoje():
        servidores = _carregar_cache()
        if servidores:
            xbmc.log('[OnTV] Servidores do cache ({})'.format(len(servidores)), xbmc.LOGINFO)
            return servidores

    # Ir ao Gist
    try:
        servidores = _fetch_gist()
        with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(servidores, f)
        _marcar_gist_visitado()
        xbmc.log('[OnTV] Servidores carregados do Gist ({})'.format(len(servidores)), xbmc.LOGINFO)
        return servidores
    except Exception as e:
        xbmc.log('[OnTV] Gist indisponível — a usar cache: ' + str(e), xbmc.LOGWARNING)
        servidores = _carregar_cache()
        if servidores:
            return servidores
        xbmc.log('[OnTV] Sem servidores disponíveis', xbmc.LOGERROR)
        return []


SERVIDORES = carregar_servidores()
