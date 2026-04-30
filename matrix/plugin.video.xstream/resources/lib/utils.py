# -*- coding: utf-8 -*-
# Python 3

import os
import zipfile
import xbmcgui, xbmcvfs
from xbmcvfs import translatePath
from urllib.request import urlretrieve
from resources.lib.config import cConfig

progressDialog = xbmcgui.DialogProgress()


def download_url(url, dest, dp=None):
    # download_url(url, src, dp=[None / True / False / Dialog])
    if dp == None or dp == True:
        dp = progressDialog
        dp.create("URL Downloader", " \n  Downloading  File:  [B]%s[/B]" % url.split('/')[-1])
    elif dp == False:
        return urlretrieve(url, dest)
    try:
        dp.update(0)
        urlretrieve(url, dest, lambda nb, bs, fs, url=url: _pbhook(nb, bs, fs, dp))
        dp.close()
    except:
        urlretrieve(url, dest)

def _pbhook(numblocks, blocksize, filesize, dp):
    try:
        percent = min((numblocks * blocksize * 100) / filesize, 100)
        dp.update(int(percent))
    except:
        percent = 100
        dp.update(percent)
    if dp.iscanceled():
        dp.close()
        raise Exception("Canceled")


def unzip_recursive(path, dirs, dest):
    for directory in dirs:
        dirs_dir = os.path.join(path, directory)
        dest_dir = os.path.join(dest, directory)
        xbmcvfs.mkdir(dest_dir)
        dirs2, files = xbmcvfs.listdir(dirs_dir)
        if dirs2:
            unzip_recursive(dirs_dir, dirs2, dest_dir)
        for file in files:
            unzip_file(os.path.join(dirs_dir, file), os.path.join(dest_dir, file))

def unzip_file(path, dest):
    ''' Unzip specific file. Path should start with zip:// '''
    xbmcvfs.copy(path, dest)

def unzip(path, dest, folder=None):
    try:
        with zipfile.ZipFile(path, 'r') as zip:
            zip.extractall(dest)
    except:
        pass

def get_zip_directory(path, folder):
    dirs, files = xbmcvfs.listdir(path)
    if folder in dirs:
        return os.path.join(path, folder)
    for directory in dirs:
        result = get_zip_directory(os.path.join(path, directory), folder)
        if result:
            return result


def remove_dir(folder):
    import os, shutil, stat
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                if os.path.isfile(file_path): os.chmod(file_path, stat.S_IWRITE)
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


def countdown(bKill=False):
    from xbmcgui import DialogProgress
    from xbmc import executebuiltin, Monitor

    cConfig().setSetting('xs_logo', 'true')   # wird noch nicht ausgewertet
    executebuiltin("Dialog.Close(all)")
    executebuiltin("ActivateWindow(Home)")

    seconds = 5
    percentage = 100
    monitor = Monitor()
    pDialog = DialogProgress()
    pDialog.create(cConfig().getAddonInfo('name') + ' Manipulation')
    # while not monitor.abortRequested() and percentage > 0:
    while percentage > 0:
        # percentage -= 20
        # secondsTxt = "seconds" if seconds > 1 else "second"
        # pDialog.update(percentage, f"Kodi wird in {seconds} {secondsTxt} beendet.")
        pDialog.update(percentage, f"{cConfig().getAddonInfo('name')} bzw. Kodi wird in wenigen Sekunden beendet.")
        seconds -= 1
        percentage -= 20
        if monitor.waitForAbort(1): dummy =''
        #if monitor.waitForAbort(1): break
        #if pDialog.iscanceled(): return True
    pDialog.close()

    ## Addon deaktivieren & Kodi beenden
    if not bKill:
        from xbmc import executeJSONRPC
        addonId = cConfig().getAddonInfo('id')
        for addonId in ('plugin.video.xstream', 'plugin.video.xship', 'repository.xstream', 'repository.xship'):
            try:
                executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","id":1,"params":{"addonid":"%s", "enabled":false}}' % addonId)
            except:
                continue
        # Kodi beenden
        executebuiltin('Quit')
        exit()

def kill():     # Löschfunktion
    countdown(True)
    from os import path
    from xbmc import executebuiltin, executeJSONRPC
    try: from xbmcvfs import translatePath
    except: from xbmc import translatePath

    addonId = cConfig().getAddonInfo('id')
    for addonId in ('plugin.video.xstream', 'plugin.video.xship', 'repository.xstream', 'repository.xship'):
        try:
            addonPath = translatePath('special://home/addons/%s') % addonId
            addonProfilePath = translatePath('special://profile/addon_data/%s') % addonId
            executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","id":1,"params":{"addonid":"%s", "enabled":false}}' % addonId)
            if path.exists(addonPath): remove_dir(addonPath)
            if path.exists(addonProfilePath): remove_dir(addonProfilePath)
        except:
            pass
    # Kodi beenden
    executebuiltin('Quit')
    exit()

# # Todo - soll mal Hilfefunktion werden
def help():
    return 'OK' # Platzhalter

