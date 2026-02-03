# In: resources/lib/scrapers/session.py
import requests
import xbmc
import traceback

try:
    # --- ✅ CHANGE IS HERE ✅ ---
    # Try to import the specific Kodi module (cloudscraper2)
    # and renames it (alias) to "cloudscraper"
    import cloudscraper2 as cloudscraper
    # --- END OF CHANGE ---
    
    SCRAPER_INSTANCE = cloudscraper.create_scraper()

except ImportError as e:  # Catch the exception
    # If cloudscraper2 is not installed OR a dependency (like js2py) is missing
    SCRAPER_INSTANCE = requests

except Exception as e: # Catches any OTHER errors
    SCRAPER_INSTANCE = requests


# --- Network Constants ---
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# ✅ OPTIMIZATION: Default timeout for scrapers
DEFAULT_TIMEOUT = 5

HTML_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en_US,pt;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',  # ✅ NEW: Compression
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://google.com/'
}