################################################################################
#  Al8inA Matrix Wizard - startup service                                      #
#  Based on OpenWizard (c) 2019 drinfernoo, GPL v2+. See LICENSE.              #
################################################################################

import os
import time

import xbmc
import xbmcgui

from resources.libs.common.config import CONFIG
from resources.libs import check
from resources.libs import clear
from resources.libs import db
from resources.libs.common import logging
from resources.libs.common import tools
from resources.libs.gui import window

PVR_ADDON = 'pvr.iptvsimple'
PVR_MAX_TRIES = 3        # give up after this many failed attempts (so a removed add-on is not forced back forever)
PVR_WAIT_SECONDS = 60    # how long to wait for the install to finish

monitor = None  # created in run-time below and released at the end, so Kodi does not warn about classes left in memory


def wait_for_video():
    """Stay out of the way while a video is playing. Returns False if Kodi is shutting down."""
    while xbmc.Player().isPlayingVideo():
        if monitor.waitForAbort(2):
            return False
    return not monitor.abortRequested()


def install_pvr_simple():
    """Install and enable the IPTV Simple client once the build is active."""
    if xbmc.getCondVisibility('System.HasAddon({0})'.format(PVR_ADDON)):
        CONFIG.set_setting('pvr_tries', '0')
        return

    tries = int(float(CONFIG.get_setting('pvr_tries') or 0))
    if tries >= PVR_MAX_TRIES:
        logging.log("[PVR Auto-Install] Skipped: {0} failed attempts already".format(tries), level=xbmc.LOGINFO)
        return
    CONFIG.set_setting('pvr_tries', str(tries + 1))

    logging.log("[PVR Auto-Install] {0} missing, installing (attempt {1})".format(PVR_ADDON, tries + 1), level=xbmc.LOGINFO)
    xbmc.executebuiltin('InstallAddon({0})'.format(PVR_ADDON))

    # InstallAddon is asynchronous: wait until the add-on really exists before trying to enable it
    waited = 0
    while waited < PVR_WAIT_SECONDS:
        if monitor.waitForAbort(1):
            return
        waited += 1
        if xbmc.getCondVisibility('System.HasAddon({0})'.format(PVR_ADDON)):
            break
    else:
        logging.log("[PVR Auto-Install] Timed out waiting for {0}".format(PVR_ADDON), level=xbmc.LOGWARNING)
        return

    xbmc.executeJSONRPC('{{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled",'
                        '"params":{{"addonid":"{0}","enabled":true}},"id":1}}'.format(PVR_ADDON))
    logging.log("[PVR Auto-Install] {0} installed and enabled".format(PVR_ADDON), level=xbmc.LOGINFO)


def auto_install_repo():
    if os.path.exists(os.path.join(CONFIG.ADDONS, CONFIG.REPOID)):
        return

    response = tools.open_url(CONFIG.REPOADDONXML)
    if not response:
        return

    from xml.etree import ElementTree
    root = ElementTree.fromstring(response.text)
    repoversion = [tag.get('version') for tag in root.findall('addon') if tag.get('id') == CONFIG.REPOID]
    if not repoversion:
        return

    installzip = '{0}-{1}.zip'.format(CONFIG.REPOID, repoversion[0])
    url = CONFIG.REPOZIPURL + installzip
    if not tools.open_url(url, check=True):
        return

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
        reponame = ElementTree.parse(repoxml).getroot().get('name')
        logging.log_notify("{0}".format(reponame), "[COLOR {0}]Add-on updated[/COLOR]".format(CONFIG.COLOR2),
                           icon=os.path.join(CONFIG.ADDONS, CONFIG.REPOID, 'icon.png'))
    except Exception as e:
        logging.log(str(e), level=xbmc.LOGERROR)
    db.addon_database(CONFIG.REPOID, 1)
    progress_dialog.close()
    xbmc.sleep(500)


def installed_build_check():
    if CONFIG.get_setting('installed') == 'true':
        if CONFIG.get_setting('keeptrakt') == 'true':
            from resources.libs import traktit
            traktit.trakt_it('restore', 'all')
        CONFIG.clear_setting('install')


def build_update_due():
    now = time.time()
    try:
        due = time.mktime(time.strptime(CONFIG.get_setting('nextbuildcheck'), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError, OverflowError):
        return True
    # a stored date further away than UPDATECHECK days (e.g. left over from an older setting) must not postpone the check
    due = min(due, now + float(CONFIG.UPDATECHECK) * 86400)
    return now >= due


def run():
    if not wait_for_video():
        return

    tools.ensure_folders()
    check.check_paths()

    # 1. First run: ask what to keep when a build is installed
    if CONFIG.get_setting('first_install') == 'true':
        window.show_save_data_settings()

    build_installed = CONFIG.get_setting('installed')

    # 2. No build installed yet: offer one (network is only touched in this case)
    if build_installed == 'false' and tools.open_url(CONFIG.BUILDFILE, check=True):
        window.show_build_prompt()

    # 3. Build installed: check for a newer version when due (UPDATECHECK days in uservar.py)
    buildname = CONFIG.get_setting('buildname')
    if not buildname:
        logging.log("[Build Update] No build installed through the wizard (setting 'buildname' is empty): nothing to check", level=xbmc.LOGINFO)
    elif build_update_due():
        logging.log("[Build Update] Checking '{0}' (installed v{1})".format(buildname, CONFIG.get_setting('buildversion')), level=xbmc.LOGINFO)
        check.check_build_update()
    else:
        logging.log("[Build Update] Next check: {0}".format(CONFIG.get_setting('nextbuildcheck')), level=xbmc.LOGINFO)

    # 4. Optional repo auto-install
    if CONFIG.AUTOINSTALL == 'Yes':
        auto_install_repo()

    # 5. Restore binaries saved by the build, if any
    if os.path.exists(os.path.join(CONFIG.USERDATA, 'build_binaries.txt')):
        from resources.libs import restore
        restore.restore('binaries')

    # 6. Build is active: restore Trakt data and make sure the PVR client exists
    if CONFIG.get_setting('installed') == 'true':
        installed_build_check()
        install_pvr_simple()

    # 7. Plugin data clean-up (Settings > Maintenance > Clear Plugin Data on Startup; never touches settings.xml)
    clear.startup_plugin_cleanup()

    # 8. Scheduled clean-up (Settings > Maintenance > Auto Clean On Startup)
    clear.auto_clean()


try:
    monitor = xbmc.Monitor()
    run()
except Exception as e:  # a service must never crash Kodi's startup
    logging.log("[Startup] Unexpected error: {0}".format(e), level=xbmc.LOGERROR)
finally:
    monitor = None
