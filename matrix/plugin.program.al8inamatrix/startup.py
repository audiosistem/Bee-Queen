################################################################################
#      Copyright (C) 2019 drinfernoo                                           #
#      Modified for Al8inA Matrix Wizard - Auto Install PVR IPTV Simple               #
################################################################################

import xbmc
import xbmcgui
import time
import os
import sys
import json

from resources.libs.common.config import CONFIG
from resources.libs import clear
from resources.libs import check
from resources.libs import db
from resources.libs.gui import window
from resources.libs.common import logging
from resources.libs.common import tools
from resources.libs import skin
from resources.libs import update

# --- FUNCTIE NOUA: INSTALARE AUTOMATA PVR ---
def install_pvr_simple():
    addon_id = 'pvr.iptvsimple'
    # Verificam daca addon-ul este deja instalat in sistem
    if not xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id):
        logging.log("[PVR Auto-Install] Addon-ul %s nu a fost gasit. Pornesc instalarea..." % addon_id, level=xbmc.LOGINFO)
        
        # Comanda Kodi pentru instalare din repo-ul oficial
        xbmc.executebuiltin('InstallAddon(%s)' % addon_id)
        
        # Asteptam putin pentru ca procesul de instalare sa inceapa
        xbmc.sleep(2000)
        
        # Fortam activarea addon-ului (uneori ramane Disabled dupa instalare)
        cmd = '{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","params":{"addonid":"%s","enabled":true},"id":1}' % addon_id
        xbmc.executeJSONRPC(cmd)
        logging.log("[PVR Auto-Install] Comanda de activare a fost trimisa.", level=xbmc.LOGINFO)
    else:
        logging.log("[PVR Auto-Install] Addon-ul %s este deja instalat.", level=xbmc.LOGINFO)

# --- FUNCTII EXISTENTE (MODIFICATE MINIM PENTRU COMPATIBILITATE) ---

def auto_install_repo():
    if not os.path.exists(os.path.join(CONFIG.ADDONS, CONFIG.REPOID)):
        response = tools.open_url(CONFIG.REPOADDONXML)
        if response:
            from xml.etree import ElementTree
            root = ElementTree.fromstring(response.text)
            repoaddon = root.findall('addon')
            repoversion = [tag.get('version') for tag in repoaddon if tag.get('id') == CONFIG.REPOID]
            if repoversion:
                installzip = '{0}-{1}.zip'.format(CONFIG.REPOID, repoversion[0])
                url = CONFIG.REPOZIPURL + installzip
                repo_response = tools.open_url(url, check=True)
                if repo_response:
                    progress_dialog = xbmcgui.DialogProgress()
                    progress_dialog.create(CONFIG.ADDONTITLE, 'Downloading Repo...' + '\n' + 'Please Wait')
                    tools.ensure_folders(CONFIG.PACKAGES)
                    lib = os.path.join(CONFIG.PACKAGES, installzip)
                    tools.remove_file(lib)
                    from resources.libs.downloader import Downloader
                    from resources.libs import extract
                    Downloader().download(url, lib)
                    extract.all(lib, CONFIG.ADDONS)
                    try:
                        repoxml = os.path.join(CONFIG.ADDONS, CONFIG.REPOID, 'addon.xml')
                        root = ElementTree.parse(repoxml).getroot()
                        reponame = root.get('name')
                        logging.log_notify("{1}".format(CONFIG.COLOR1, reponame), "[COLOR {0}]Add-on updated[/COLOR]".format(CONFIG.COLOR2), icon=os.path.join(CONFIG.ADDONS, CONFIG.REPOID, 'icon.png'))
                    except Exception as e:
                        logging.log(str(e), level=xbmc.LOGERROR)
                    db.addon_database(CONFIG.REPOID, 1)
                    progress_dialog.close()
                    xbmc.sleep(500)
    elif not CONFIG.AUTOINSTALL == 'Yes': pass

def installed_build_check():
    # Logica de verificare dupa extract (Ramane neschimbata)
    if CONFIG.get_setting('installed') == 'true':
        if CONFIG.get_setting('keeptrakt') == 'true':
            from resources.libs import traktit
            traktit.trakt_it('restore', 'all')
        CONFIG.clear_setting('install')

def check_for_video():
    while xbmc.Player().isPlayingVideo():
        xbmc.sleep(1000)

# --- LOGICA DE STARTUP A WIZARD-ULUI ---

check_for_video()
tools.ensure_folders()
check.check_paths()

# 1. VERIFICARE PRIMA INSTALARE
if CONFIG.get_setting('first_install') == 'true':
    window.show_save_data_settings()

# 2. PROMPT INSTALARE BUILD (Daca nu e instalat)
if tools.open_url(CONFIG.BUILDFILE, check=True) and CONFIG.get_setting('installed') == 'false':
    window.show_build_prompt()

# 3. VERIFICARE UPDATE BUILD
if CONFIG.get_setting('buildname'):
    buildcheck = CONFIG.get_setting('nextbuildcheck')
    if time.time() >= time.mktime(time.strptime(buildcheck, "%Y-%m-%d %H:%M:%S")):
        check.check_build_update()

# 4. INSTALARE AUTOMATA REPO
if CONFIG.AUTOINSTALL == 'Yes':
    auto_install_repo()

# 5. RESTAURARE BINARE (Daca exista fisierul)
binarytxt = os.path.join(CONFIG.USERDATA, 'build_binaries.txt')
if os.path.exists(binarytxt):
    from resources.libs import restore
    restore.restore('binaries')

# 6. VERIFICARE STATUS BUILD INSTALAT SI LANSARE PVR
if CONFIG.get_setting('installed') == 'true':
    logging.log("[Build Status] Build-ul este activat. Verific PVR...", level=xbmc.LOGINFO)
    installed_build_check()
    
    # --- AICI SE EXECUTA COMANDA CERUTA ---
    install_pvr_simple()

#