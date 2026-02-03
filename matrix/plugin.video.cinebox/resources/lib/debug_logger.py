# -*- coding: utf-8 -*-
"""Debug Logger Module for Cinebox
Records detailed logs for diagnosing problems"""

import xbmc
import xbmcaddon
import xbmcvfs
import os
import time
from datetime import datetime
import traceback
import json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

class DebugLogger:
    """Custom logger for detailed debugging"""
    
    def __init__(self):
        self.addon = ADDON
        self._refresh_settings()
        
        # Set log file path
        try:
            profile_dir = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        except AttributeError:
            profile_dir = xbmc.translatePath(self.addon.getAddonInfo('profile'))
        
        if not os.path.exists(profile_dir):
            try:
                os.makedirs(profile_dir)
            except:
                pass
        
        self.log_file = os.path.join(profile_dir, 'cinebox_debug.log')
        
        # Log Levels
        self.levels = {
            'Basic': 1,
            'Medium': 2,
            'Full': 3
        }

    def _refresh_settings(self):
        """Reload the add-on settings"""
        # Force reload of addon settings
        try:
            self.enabled = self.addon.getSettingBool('debug.enabled')
            self.level = self.addon.getSettingString('debug.level')
            self.scrapers_debug = self.addon.getSettingBool('debug.scrapers')
            self.network_debug = self.addon.getSettingBool('debug.network')
            self.save_to_file = self.addon.getSettingBool('debug.save_to_file')
        except:
            # Fallback if the addon is not fully loaded
            self.enabled = True
            self.level = 'Medium'
            self.scrapers_debug = True
            self.network_debug = True
            self.save_to_file = True
        
        levels = {'Basic': 1, 'Medium': 2, 'Full': 3}
        self.current_level = levels.get(self.level, 2)
    
    def _should_log(self, min_level=1):
        """Checks whether to log based on level"""
        # Always log errors and warnings in the Kodi log to facilitate diagnosis
        if min_level <= 1:
            return True
        self._refresh_settings()
        return self.enabled and self.current_level >= min_level
    
    def _format_message(self, category, message, level='INFO'):
        """Format the log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        return f"[{timestamp}] [{ADDON_NAME}] [{category}] [{level}] {message}"
    
    def _write_to_file(self, formatted_message):
        """Write to the log file"""
        if not self.save_to_file:
            return
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(formatted_message + '\n')
        except Exception as e:
            xbmc.log(f"[{ADDON_NAME}] Error writing to the log file: {e}", xbmc.LOGERROR)
    
    def _log(self, category, message, kodi_level, min_level=1):
        """Internal log method"""
        # Force log into Kodi for important categories
        force_kodi = category.startswith('SCRAPER') or category == 'NETWORK' or kodi_level >= xbmc.LOGWARNING
        
        should_log = self._should_log(min_level)
        
        if not should_log and not force_kodi:
            return
        
        level_name = {
            xbmc.LOGDEBUG: 'DEBUG',
            xbmc.LOGINFO: 'INFO',
            xbmc.LOGWARNING: 'WARNING',
            xbmc.LOGERROR: 'ERROR',
            xbmc.LOGFATAL: 'FATAL'
        }.get(kodi_level, 'INFO')
        
        formatted = self._format_message(category, message, level_name)
        
        # Log into Kodi (always if forced or if the level allows it)
        if force_kodi or should_log:
            xbmc.log(formatted, kodi_level)
        
        # Log to file (only if enabled in settings)
        if should_log:
            self._write_to_file(formatted)
    
    def debug(self, category, message, min_level=3):
        """Debug log (Full level only)"""
        self._log(category, message, xbmc.LOGDEBUG, min_level)
    
    def info(self, category, message, min_level=1):
        """Information log (all levels)"""
        self._log(category, message, xbmc.LOGINFO, min_level)
    
    def warning(self, category, message, min_level=1):
        """Warning log (all levels)"""
        self._log(category, message, xbmc.LOGWARNING, min_level)
    
    def error(self, category, message, min_level=1):
        """Error log (all levels)"""
        self._log(category, message, xbmc.LOGERROR, min_level)
    
    def exception(self, category, message):
        """Exception log with full traceback"""
        if not self.enabled:
            return
        
        tb = traceback.format_exc()
        full_message = f"{message}\n{tb}"
        self._log(category, full_message, xbmc.LOGERROR, 1)
    
    def scraper(self, scraper_name, message, min_level=2):
        """Specific log for scrapers"""
        if not self.scrapers_debug:
            return
        self._log(f"SCRAPER:{scraper_name}", message, xbmc.LOGINFO, min_level)
    
    def network(self, url, method='GET', status=None, headers=None, response=None):
        """Specific log for network requests"""
        if not self.network_debug:
            return
        
        message = f"{method} {url}"
        if status:
            message += f" - Status: {status}"
        if headers and self.current_level >= 3:
            message += f"\nHeaders: {json.dumps(headers, indent=2)}"
        if response and self.current_level >= 3:
            # Limit response size
            resp_str = str(response)[:500]
            message += f"\nResponse: {resp_str}..."
        
        self._log("NETWORK", message, xbmc.LOGDEBUG, 2)
    
    def scraper_sources(self, scraper_name, sources_count, sources_sample=None):
        """Log of sources found by scraper"""
        if not self.scrapers_debug:
            return
        
        message = f"{sources_count} sources found"
        
        if sources_sample and self.current_level >= 2:
            message += f"\nSample: {json.dumps(sources_sample[:3], indent=2, ensure_ascii=False)}"
        
        self._log(f"SCRAPER:{scraper_name}", message, xbmc.LOGINFO, 2)
    
    def scraper_error(self, scraper_name, error, url=None):
        """Scraper error log"""
        if not self.scrapers_debug:
            return
        
        message = f"Error: {str(error)}"
        if url:
            message += f"\nURL: {url}"
        if self.current_level >= 3:
            message += f"\n{traceback.format_exc()}"
        
        self._log(f"SCRAPER:{scraper_name}", message, xbmc.LOGERROR, 1)
    
    def clear_log(self):
        """Clears the log file"""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            self.info("DEBUG", "Log file cleared successfully")
            return True
        except Exception as e:
            self.error("DEBUG", f"Error clearing log: {e}")
            return False
    
    def get_log_content(self, lines=100):
        """Returns the last N lines of the log"""
        try:
            if not os.path.exists(self.log_file):
                return "No log available"
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading log: {e}"
    
    def get_log_size(self):
        """Returns the size of the log file"""
        try:
            if os.path.exists(self.log_file):
                size = os.path.getsize(self.log_file)
                # Convert to KB or MB
                if size < 1024:
                    return f"{size} bytes"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.2f} KB"
                else:
                    return f"{size / (1024 * 1024):.2f} MB"
            return "0 bytes"
        except:
            return "Unknown"

# Global instance
logger = DebugLogger()
