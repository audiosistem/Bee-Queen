# -*- coding: utf-8 -*-
import os
import time
import threading
from datetime import datetime, timedelta
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

"""Automatic System Update - Cinebox
Version: 3.1.0 (Enhanced)
Improvement: Deep cache cleaning and forced update at startup
Inspired by the architecture of IMDB TrainAgain"""

def get_addon():
    return xbmcaddon.Addon()

def show_notification(title, message, icon=xbmcgui.NOTIFICATION_INFO, duration=5000):
    """Guaranteedly displays a notification"""
    try:
        # Remove color tags for notification title if necessary
        clean_title = title.replace('[COLOR red]', '').replace('[/COLOR]', '').replace('[COLOR yellow]', '')
        xbmcgui.Dialog().notification(clean_title, message, icon, duration, False)
    except:
        pass

class AutoUpdater:
    def __init__(self, monitor):
        self.monitor = monitor
        self.update_lock = threading.Lock()
        
        addon = get_addon()
        self.addon_id = addon.getAddonInfo('id')
        self.addon_name = addon.getAddonInfo('name')
        
        self.refresh_settings()
        self.last_update = self.get_last_update_time()
        self.is_running = False
        
        self.log_info(f"Initialized - Enabled: {self.enabled}, Startup: {self.update_on_startup}, Interval: {self.interval_hours}h")

    def refresh_settings(self):
        try:
            addon = get_addon()
            self.enabled = addon.getSettingBool('auto_update_enabled')
            self.interval_hours = int(addon.getSetting('update_interval') or 5)
            self.update_on_startup = addon.getSettingBool('update_on_startup')
            self.show_notifications = addon.getSettingBool('show_update_notifications')
        except:
            self.enabled = True
            self.interval_hours = 5
            self.update_on_startup = True
            self.show_notifications = True

    def log_info(self, message):
        xbmc.log(f"[{self.addon_name} AutoUpdater] {message}", xbmc.LOGINFO)
    
    def log_error(self, message):
        xbmc.log(f"[{self.addon_name} AutoUpdater] ERROR - {message}", xbmc.LOGERROR)

    def get_last_update_time(self):
        try:
            addon_data_path = xbmcvfs.translatePath(f'special://profile/addon_data/{self.addon_id}/')
            update_file = os.path.join(addon_data_path, '.last_update')
            if os.path.exists(update_file):
                with open(update_file, 'r') as f:
                    return datetime.fromisoformat(f.read().strip())
            
            addon = get_addon()
            val = addon.getSetting('last_update_check')
            return datetime.fromisoformat(val) if val else None
        except:
            return None

    def set_last_update_time(self):
        try:
            now = datetime.now()
            addon_data_path = xbmcvfs.translatePath(f'special://profile/addon_data/{self.addon_id}/')
            os.makedirs(addon_data_path, exist_ok=True)
            with open(os.path.join(addon_data_path, '.last_update'), 'w') as f:
                f.write(now.isoformat())
            get_addon().setSetting('last_update_check', now.isoformat())
            self.last_update = now
        except Exception as e:
            self.log_error(f"Error saving timestamp: {e}")

    def is_update_needed(self):
        self.refresh_settings()
        if not self.enabled: return False
        if self.last_update is None: return True
        return (datetime.now() - self.last_update) >= timedelta(hours=self.interval_hours)

    def clear_deep_cache(self):
        """Clears all possible caches to ensure new content"""
        try:
            self.log_info("Starting deep cache cleaning...")
            
            # 1. Clear memory cache (Window Properties)
            window = xbmcgui.Window(10000)
            keys_to_clear = [
                'cinebox.movies.cache', 'cinebox.tvshows.cache', 'cinebox.trending.cache',
                'cinebox.movies.popular', 'cinebox.tvshows.popular'
            ]
            for key in keys_to_clear:
                window.clearProperty(key)
            
            # 2. Clear Database cache (api_cache)
            try:
                from resources.lib.db.db import db_instance
                conn = db_instance._get_conn()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM api_cache")
                conn.commit()
                db_instance._release_conn(conn)
                # Clears SmartCache in memory as well
                db_instance._cache.clear()
                self.log_info("✓ Database cache cleared")
            except Exception as e:
                self.log_error(f"Error clearing the DB cache: {e}")

            # 3. Clear module cache (main.py)
            try:
                import sys
                if 'main' in sys.modules:
                    main_mod = sys.modules['main']
                    if hasattr(main_mod, '_MODULE_CACHE'):
                        main_mod._MODULE_CACHE.clear()
                    if hasattr(main_mod, '_JSON_CACHE'):
                        main_mod._JSON_CACHE.clear()
                self.log_info("✓ Module cache cleared")
            except:
                pass

            self.log_info("Deep cleaning completed.")
        except Exception as e:
            self.log_error(f"General cache clearing error: {e}")

    def update_content(self, reason="Periodic"):
        if not self.update_lock.acquire(blocking=False):
            self.log_info("Update already underway.")
            return False
        
        try:
            self.refresh_settings()
            if not self.enabled: return False
            
            # If you are watching something, wait for the player to stop (maximum 10 min wait)
            wait_count = 0
            while xbmc.Player().isPlaying() and wait_count < 60:
                if self.monitor.waitForAbort(10): return False
                wait_count += 1
            
            self.log_info(f"Starting update ({reason})")
            
            if self.show_notifications:
                show_notification(self.addon_name, "Updating catalogue...", xbmcgui.NOTIFICATION_INFO)
            
            # Deep cleaning before fetching new data
            self.clear_deep_cache()
            
            success = False
            try:
                from resources.lib.indexer import check_for_updates_silently
                check_for_updates_silently(get_addon())
                success = True
            except Exception as e:
                self.log_error(f"Falha no indexer: {e}")
            
            if success:
                self.set_last_update_time()
                if self.show_notifications:
                    show_notification(self.addon_name, "Catalog updated!", xbmcgui.NOTIFICATION_INFO)
                
                # Force Kodi to update the current listing
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                if self.show_notifications:
                    show_notification(self.addon_name, "Update error", xbmcgui.NOTIFICATION_ERROR)
                return False
        finally:
            self.update_lock.release()

    def worker(self):
        self.log_info("Worker started.")
        
        # --- STARTUP UPDATE ---
        # Wait 15 seconds for Kodi to stabilize the network and services
        if not self.monitor.waitForAbort(15):
            self.refresh_settings()
            if self.update_on_startup and self.enabled:
                self.log_info("Shooting startup update...")
                self.update_content(reason="Startup")
        
        # --- PERIODIC LOOP ---
        while not self.monitor.waitForAbort(300): # Every 5 minutes check if necessary
            if self.is_update_needed():
                self.update_content(reason="Scheduled")
        
        self.log_info("Worker finalizado.")

    def start(self):
        if not self.is_running:
            self.is_running = True
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()

    def stop(self):
        self.is_running = False
