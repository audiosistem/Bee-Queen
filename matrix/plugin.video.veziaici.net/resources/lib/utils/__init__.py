"""Utility functions and constants for VeziAici.net addon."""

import os
import sys
import xbmc
import xbmcvfs
import xbmcaddon

# Addon info
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_ICON = ADDON.getAddonInfo("icon")
ADDON_FANART = ADDON.getAddonInfo("fanart")

# Cache directory
CACHE_DIR = xbmcvfs.translatePath(os.path.join(ADDON.getAddonInfo("profile"), "cache"))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Add lib path
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

# Base URLs
BASE_URL_VEZIAICI = "https://veziaici.net/"
BASE_URL_TERASA = "https://terasacucartii.net"
BASE_URL_BLOGUL = "https://blogul-lui-atanase.ro/"
BASE_URL_SERIALECOREENE = "https://serialecoreene.org/"

# Headers for HTTP requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Dictionary for custom show images
CUSTOM_IMAGES = {
    "insula iubirii": "https://www.fanatik.ro/wp-content/uploads/2024/08/insula-iubirii-2025.jpg",
    "las fierbinti": "https://upload.wikimedia.org/wikipedia/en/0/0d/Las_Fierbin%C8%9Bi_logo.png",
    "asia express": "https://cdn.adh.reperio.news/image-e/e410c82f-f849-4953-94fa-ed9ee2ba49bf/index.jpeg",
    "masterchef": "https://static4.libertatea.ro/wp-content/uploads/2024/02/masterchef-romania-revine-la-pro-tv.jpg",
    "the ticket": "https://static4.libertatea.ro/wp-content/uploads/2025/07/the-ticket.jpg",
    "vocea romaniei": "https://upload.wikimedia.org/wikipedia/ro/thumb/8/83/Vocea_Rom%C3%A2niei_-_compila%C8%9Bie.jpg/250px-Vocea_Rom%C3%A2niei_-_compila%C8%9Bie.jpg",
    "ana mi-ai fost scrisa in adn": "https://static4.libertatea.ro/wp-content/uploads/2024/11/ana-mi-ai-fost-scrisa-in-adn-serial-antena-1.jpg",
    "camera 609": "https://static.cinemagia.ro/img/resize/db/movie/33/10/231/lasa-ma-imi-place-camera-609-729239l-600x0-w-09e9e09b.jpg",
    "clanul": "https://cmero-ott-images-svod.ssl.cdn.cra.cz/r800x1160n/ad802c4a-901f-4700-9948-39361f41a677",
    "seriale": "https://upload.wikimedia.org/wikipedia/en/0/0d/Las_Fierbin%C8%9Bi_logo.png",
    "iubire cu": "https://dcasting.ro/wp-content/uploads/2025/02/Iubire-cu-parfum-de-lavanda.jpg",
    "sotia sotului": "https://onemagia.com/upload/images/e7mDxkP6Qgbo735USy5telMF1wF.jpg",
    "scara b": "https://static4.libertatea.ro/wp-content/uploads/2024/08/scara-b-scaled.jpg",
    "tatutu": "https://image.stirileprotv.ro/media/images/1920x1080/Jun2025/62556367.jpg",
}


class CachedResponse:
    """Mock requests.Response for cached content."""
    def __init__(self, text, status_code=200, url=""):
        self.text = text
        self.content = text.encode("utf-8") if text else b""
        self.status_code = status_code
        self.url = url
        self.headers = {}

    def json(self):
        import json
        return json.loads(self.text)

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP Error: {self.status_code}")
        return None


def get_html_content(url, referer=None, cache_time=3600):
    """Fetch HTML content from URL with proper headers and caching."""
    import hashlib
    import time
    import requests

    # Fix encoding for URLs with special characters (like em-dash in images)
    if " " in url or "–" in url:
        parts = list(urllib.parse.urlparse(url))
        parts[2] = urllib.parse.quote(parts[2])
        url = urllib.parse.urlunparse(parts)

    # Generate cache filename
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"html_{url_hash}.cache")

    # Check cache
    if cache_time > 0 and os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < cache_time:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content:
                        log_debug(f"Using cache for: {url}")
                        return CachedResponse(content, url=url)
            except Exception as e:
                log_debug(f"Cache read error: {e}")

    headers = HEADERS.copy()
    if referer:
        headers["Referer"] = referer
    elif "terasacucartii.net" in url:
        headers["Referer"] = "https://terasacucartii.net/"
    elif "terasacucarti" in url:
        headers["Referer"] = "https://www.terasacucarti.com/"
    else:
        headers["Referer"] = BASE_URL_VEZIAICI
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and cache_time > 0:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(response.text)
            except Exception as e:
                log_debug(f"Cache write error: {e}")
        return response
    except Exception as e:
        log_error(f"HTTP Request error for {url}: {e}")
        return CachedResponse("", status_code=500, url=url)


def parallel_map(func, iterable, threads=5):
    """Execute a function over an iterable in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=threads) as executor:
        return list(executor.map(func, iterable))


def js_unpack(packed):
    """Unpack Dean Edwards packed JavaScript with more robust logic."""
    import re
    
    def unbase(n, base):
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if n < base:
            return alphabet[n]
        else:
            return unbase(n // base, base) + alphabet[n % base]

    # Pattern for p,a,c,k,e,d
    pattern = r"}\s*\('(.*)',\s*(\d+),\s*(\d+),\s*'(.*?)'\.split\('\|'\)"
    match = re.search(pattern, packed, re.DOTALL)
    if not match:
        return packed

    p, a, c, k = match.groups()
    a = int(a)
    c = int(c)
    k = k.split("|")

    # Map words
    words = {}
    for i in range(c):
        b_val = unbase(i, a)
        words[b_val] = k[i] if i < len(k) and k[i] else b_val

    # Replace words
    # Use word boundary to avoid partial matches
    def replace_word(m):
        w = m.group(0)
        return words.get(w, w)

    unpacked = re.sub(r"\b\w+\b", replace_word, p)
    return unpacked


def int_or_none(value, default=None):
    """Convert value to int or return default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def unescape_html(text):
    """Unescape HTML entities."""
    if not text:
        return text
    return (
        text.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("\\/", "/")
    )


def get_custom_image(title):
    """Get custom image URL for a show title."""
    title_lower = title.lower()
    for keyword, image_url in CUSTOM_IMAGES.items():
        if keyword in title_lower:
            return image_url
    return ADDON_ICON


def log(msg, level=xbmc.LOGINFO):
    """Log message with addon prefix."""
    xbmc.log(f"[{ADDON_NAME}] {msg}", level)


def log_debug(msg):
    """Log debug message."""
    log(msg, xbmc.LOGDEBUG)


def log_error(msg):
    """Log error message."""
    log(msg, xbmc.LOGERROR)


def log_warning(msg):
    """Log warning message."""
    log(msg, xbmc.LOGWARNING)
