# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import sys
import os
import threading

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))

def run_trakt_service(monitor):
    """Run automatic Trakt synchronization in a thread"""
    def _sync():
        try:
            # Wait a while so as not to overload the start
            if monitor.waitForAbort(15): return
            
            from resources.lib.trakt_sync import full_bidirectional_sync, get_trakt_settings
            
            settings = get_trakt_settings()
            if not settings.get('access_token'):
                return
            
            xbmc.log("[Cinebox Trakt Service] Starting boot synchronization...", xbmc.LOGINFO)
            full_bidirectional_sync()
                
        except Exception as e:
            xbmc.log(f"[Cinebox Trakt Service] Error: {e}", xbmc.LOGERROR)

    threading.Thread(target=_sync, name="TraktSyncThread").start()

class CineboxService(xbmc.Monitor):
    def __init__(self):
        xbmc.Monitor.__init__(self)
        xbmc.log("[Cinebox Service] Initializing...", xbmc.LOGINFO)
        
        # Starts AutoUpdater (now based on the IMDB system)
        try:
            from resources.lib.auto_updater import AutoUpdater
            self.updater = AutoUpdater(self)
            self.updater.start()
        except Exception as e:
            xbmc.log(f"[Cinebox Service] Error starting AutoUpdater: {e}", xbmc.LOGERROR)
        
        # Start Trakt Sync (in separate thread)
        if ADDON.getSettingBool('trakt_sync_on_startup'):
            run_trakt_service(self)

    def onSettingsChanged(self):
        # AutoUpdater now checks settings within its own loop
        # but we could force a state update here if necessary
        pass

if __name__ == '__main__':
    service = CineboxService()
    # Keeps the service running until Kodi closes
    service.waitForAbort()
    xbmc.log("[Cinebox Service] Finished", xbmc.LOGINFO)
