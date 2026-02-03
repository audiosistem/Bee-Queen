# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs
import os
import json

def get_config_path():
    """Returns the JSON configuration file path.
    Use the addon ID to ensure the correct path in the profile."""
    try:
        # Attempts to get the ID dynamically, fallback to the default ID if it fails
        import xbmcaddon
        addon_id = xbmcaddon.Addon().getAddonInfo('id')
    except:
        addon_id = 'plugin.video.cinebox'
        
    try:
        profile_path = xbmcvfs.translatePath(f'special://profile/addon_data/{addon_id}/')
    except AttributeError:
        profile_path = xbmc.translatePath(f'special://profile/addon_data/{addon_id}/')
    
    # Create directory if it doesn't exist
    if not os.path.exists(profile_path):
        try:
            os.makedirs(profile_path)
        except:
            pass
    
    return os.path.join(profile_path, 'scraper_config.json')

def load_config():
    """Loads configuration from JSON file."""
    config_path = get_config_path()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                xbmc.log(f"[ConfigManager] Configuration loaded: {config}", xbmc.LOGINFO)
                return config
        except Exception as e:
            xbmc.log(f"[ConfigManager] Error loading config: {e}", xbmc.LOGERROR)
    
    # Return default configuration (Magneto)
    return {'enabled_scraper': 'script.module.magneto'}

def save_config(config):
    """Saves configuration in JSON file."""
    config_path = get_config_path()
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        xbmc.log(f"[ConfigManager] Settings saved: {config}", xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"[ConfigManager] Error saving config: {e}", xbmc.LOGERROR)
        return False

def get_enabled_scraper():
    """Returns the external scraper enabled.
    Always reload from file to avoid caching."""
    config = load_config()
    scraper = config.get('enabled_scraper', 'script.module.magneto')
    xbmc.log(f"[ConfigManager] Enabled scraper returned: {scraper}", xbmc.LOGINFO)
    return scraper

def set_enabled_scraper(scraper_id):
    """Sets the external scraper enabled."""
    config = load_config()
    config['enabled_scraper'] = scraper_id
    return save_config(config)
