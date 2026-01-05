# -*- coding: utf-8 -*-
from providerModules.ScrapersCinema import common
import xbmcvfs
import os
from resources.lib.modules.globals import g
import json

# FOLOSIM UN NUME UNIC CA SĂ NU SE BATĂ CU UVScrapers
NUME_FISIER_UNIC = 'version_cinema.txt'

# Căile către fișiere
meta_folder = os.path.join(g.ADDON_USERDATA_PATH, 'providerMeta', 'ScrapersCinema')
meta_file_path = os.path.join(meta_folder, 'meta.json')
local_version_file = os.path.join(g.ADDON_USERDATA_PATH, NUME_FISIER_UNIC)

def get_meta_version():
    """Citește versiunea din meta.json-ul specific ScrapersCinema"""
    if xbmcvfs.exists(meta_file_path):
        try:
            with xbmcvfs.File(meta_file_path, 'r') as f:
                meta_data = json.load(f)
                return str(meta_data.get("version", "0.30"))
        except Exception:
            return "0.30"
    return "0.30"

def get_local_version():
    """Citește versiunea din fișierul nostru specific"""
    if xbmcvfs.exists(local_version_file):
        try:
            with xbmcvfs.File(local_version_file, 'r') as f:
                return f.read().strip()
        except Exception:
            return None
    return None

# Ne asigurăm că folderul există
if not xbmcvfs.exists(g.ADDON_USERDATA_PATH):
    xbmcvfs.mkdirs(g.ADDON_USERDATA_PATH)

# Execuție
current_meta_v = get_meta_version()
saved_local_v = get_local_version()

if saved_local_v != current_meta_v:
    try:
        with xbmcvfs.File(local_version_file, 'w') as f:
            f.write(current_meta_v)
        # Logăm în Kodi ca să știm că a funcționat
        common.log(f"ScrapersCinema: Sincronizat local in {NUME_FISIER_UNIC}")
    except Exception:
        pass
