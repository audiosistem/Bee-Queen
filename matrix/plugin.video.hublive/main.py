import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import requests
from requests.adapters import HTTPAdapter
import random
import re
import os
import json
import time
from urllib.parse import parse_qsl, urlencode, quote_plus
import uuid
import hashlib
import string
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import orjson

    def json_loads(s):
        if hasattr(s, "read"):
            s = s.read()
        return orjson.loads(s)

    def json_dumps(obj, fp=None):
        result = orjson.dumps(obj)
        if fp:
            fp.write(result.decode("utf-8") if isinstance(result, bytes) else result)
            return None
        return result.decode("utf-8") if isinstance(result, bytes) else result
except ImportError:

    def json_loads(s):
        if hasattr(s, "read"):
            s = s.read()
        return json.loads(s)

    def json_dumps(obj, fp=None):
        result = json.dumps(obj)
        if fp:
            fp.write(result)
            return None
        return result


from epg import EpgManager, format_epg_tooltip

RE_STREAM_ID = re.compile(r"stream=(\d+)")
RE_MACPH_TOKENPH = re.compile(r"MACPH|TOKENPH")
RE_BOX_CHARS = re.compile(r"[\u2500-\u259F\u2500-\u257F]")
RE_CATEGORY_PREFIX = re.compile(r"^[\|\-\s]+ro[\|\s\:\-\[\(]?", re.IGNORECASE)
RE_EXTINF = re.compile(r"#EXTINF:", re.IGNORECASE)
RE_GROUP_TITLE = re.compile(r'group-title="?([^",]*)"?', re.IGNORECASE)
RE_TVG_LOGO = re.compile(r'tvg-logo=["\']([^"\']*)["\']', re.IGNORECASE)

_session = None

TIMEOUTS = {
    "handshake": 5,
    "categories": 10,
    "channels": 20,
    "epg": 15,
    "playlink": 8,
}

_portal_response_cache = {}
_PORTAL_CACHE_TTL = 300  # 5 minutes


def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=20, pool_maxsize=30, max_retries=3, pool_block=False
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        _session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                "X-User-Agent": "Model: MAG250; Link: WiFi",
                "Connection": "keep-alive",
                "Accept-Encoding": "gzip, deflate",
            }
        )
    return _session


def get_cached_response(key):
    """Get cached API response if still valid."""
    if key in _portal_response_cache:
        cached = _portal_response_cache[key]
        if time.time() - cached["timestamp"] < _PORTAL_CACHE_TTL:
            return cached["data"]
    return None


def set_cached_response(key, data):
    """Cache API response."""
    _portal_response_cache[key] = {"timestamp": time.time(), "data": data}


# Plugin version
PLUGIN_VERSION = "1.0.4"
MIN_KODI_VERSION = "19.0"
MIN_PYTHON_VERSION = (3, 6)


def check_version_compatibility():
    """Check if the plugin is compatible with the current environment."""
    import platform

    checks_passed = True
    errors = []

    # Check Python version
    current_python = sys.version_info[:2]
    if current_python < MIN_PYTHON_VERSION:
        checks_passed = False
        errors.append(
            f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required, found {current_python[0]}.{current_python[1]}"
        )

    # Check Kodi version
    try:
        kodi_version = xbmc.getInfoLabel("System.BuildVersion")
        kodi_major = int(kodi_version.split(".")[0]) if kodi_version else 0
        min_kodi_major = int(MIN_KODI_VERSION.split(".")[0])
        if kodi_major < min_kodi_major:
            checks_passed = False
            errors.append(f"Kodi {MIN_KODI_VERSION}+ required, found {kodi_version}")
    except Exception as e:
        xbmc.log(
            f"[Version] Could not determine Kodi version: {e}", level=xbmc.LOGWARNING
        )

    # Check required modules
    required_modules = ["requests"]
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            checks_passed = False
            errors.append(f"Required module '{module}' not found")

    if not checks_passed:
        error_msg = " | ".join(errors)
        xbmc.log(
            f"[Version] Compatibility checks FAILED: {error_msg}", level=xbmc.LOGERROR
        )
        xbmcgui.Dialog().notification(
            "Version Error",
            f"Plugin may not work correctly: {error_msg}",
            xbmcgui.NOTIFICATION_ERROR,
            5000,
        )
        return False

    xbmc.log(
        f"[Version] Compatibility checks PASSED (Python {'.'.join(map(str, current_python))}, Kodi {kodi_version})",
        level=xbmc.LOGINFO,
    )
    return True


# EPG data store
epg_data = {}

# EPG Cache management
EPG_CACHE_FILE = None
EPG_CACHE_TTL = 1800  # 30 minutes in seconds


def get_epg_cache_file():
    """Get the EPG cache file path."""
    global EPG_CACHE_FILE
    if EPG_CACHE_FILE is None:
        # Get Kodi's special path and translate it to real filesystem path
        addon_profile_path = xbmcaddon.Addon().getAddonInfo("profile")
        # Use xbmcvfs.translatePath (or xbmc.translatePath for older Kodi versions)
        try:
            addon_path = xbmcvfs.translatePath(addon_profile_path)
        except:
            # Fallback for older Kodi versions
            addon_path = xbmc.translatePath(addon_profile_path)

        if not os.path.exists(addon_path):
            os.makedirs(addon_path)
        EPG_CACHE_FILE = os.path.join(addon_path, "epg_cache.json")
    return EPG_CACHE_FILE


def load_epg_cache():
    """Load EPG data from cache file."""
    cache_file = get_epg_cache_file()
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json_loads(f)
                current_time = time.time()

                # Load only non-expired entries
                for stream_id, cache_entry in cache_data.items():
                    timestamp = cache_entry.get("timestamp", 0)
                    if current_time - timestamp < EPG_CACHE_TTL:
                        # Convert datetime strings back to datetime objects
                        items = cache_entry.get("items", [])
                        for item in items:
                            if item.get("start_dt"):
                                from datetime import datetime

                                item["start_dt"] = datetime.fromisoformat(
                                    item["start_dt"]
                                )
                            if item.get("end_dt"):
                                from datetime import datetime

                                item["end_dt"] = datetime.fromisoformat(item["end_dt"])
                        epg_data[stream_id] = items

                xbmc.log(
                    f"[EPG] Loaded {len(epg_data)} channels from cache",
                    level=xbmc.LOGDEBUG,
                )
    except Exception as e:
        xbmc.log(f"[EPG] Failed to load cache: {e}", level=xbmc.LOGWARNING)


def save_epg_cache():
    """Save EPG data to cache file."""
    cache_file = get_epg_cache_file()
    try:
        cache_data = {}
        current_time = time.time()

        for stream_id, items in epg_data.items():
            # Convert datetime objects to ISO format strings for JSON
            serializable_items = []
            for item in items:
                serializable_item = item.copy()
                if item.get("start_dt"):
                    serializable_item["start_dt"] = item["start_dt"].isoformat()
                if item.get("end_dt"):
                    serializable_item["end_dt"] = item["end_dt"].isoformat()
                serializable_items.append(serializable_item)

            cache_data[stream_id] = {
                "timestamp": current_time,
                "items": serializable_items,
            }

        with open(cache_file, "w", encoding="utf-8") as f:
            json_dumps(cache_data, f)

        xbmc.log(f"[EPG] Saved {len(cache_data)} channels to cache", level=xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[EPG] Failed to save cache: {e}", level=xbmc.LOGWARNING)


def get_current_program(epg_items):
    """Extract the current program name from EPG items."""
    if not epg_items:
        return None

    from datetime import datetime

    now = datetime.now()

    for item in epg_items:
        start_dt = item.get("start_dt")
        end_dt = item.get("end_dt")

        if start_dt and end_dt:
            if start_dt <= now < end_dt:
                # Current program
                name = item.get("name") or item.get("title") or ""
                return name.strip()

    # If no current program, return the next upcoming one
    for item in epg_items:
        start_dt = item.get("start_dt")
        if start_dt and now < start_dt:
            name = item.get("name") or item.get("title") or ""
            return f"Next: {name.strip()}"

    return None


def epg_callback(channel_key, items):
    xbmc.log(
        f"[DEBUG] EPG callback for channel {channel_key} with {len(items)} items. Data: {items}",
        level=xbmc.LOGDEBUG,
    )
    epg_data[channel_key] = items


# Plugin specific variables
_ADDON = xbmcaddon.Addon()
_HANDLE = int(sys.argv[1])
_BASE_URL = sys.argv[0]


# Check if EPG is enabled
def is_epg_enabled():
    """Check if EPG is enabled in settings."""
    return _ADDON.getSetting("epg_enabled") == "true"


# Category mapping and sorting
CATEGORY_MAPPING = {
    # Server 1
    "RO| CANALE DE CINEMA": "Filme",
    "RO| CANALE DE DIVERTISMENT": "Divertisment",
    "RO| CANALE DE SPORT": "Sport",
    "RO| CANALE DOCUMENTARE": "Documentare",
    "RO| CANALE GENERALE": "Generale",
    "RO| CANALE MUZICALE": "Muzica",
    "RO| CANALE PENTRU COPII": "Pentru Copii",
    "RO| FOCUS SAT VIP": "Focus Sat",
    # Server 2
    "RO : ROMAINE": "Generale",
    "RO : COPİİ": "Pentru Copii",
    "RO : DOCU & REALITATE": "Documentare",
    "RO : MUZICÄ": "Muzica",
    "RO : SPORT": "Sport",
    "RO : FILM": "Filme",
}

# Custom sort order for categories
CATEGORY_ORDER = [
    "Generale",
    "Divertisment",
    "Sport",
    "Filme",
    "Documentare",
    "Muzica",
    "Pentru Copii",
    "Focus Sat",
]

# Category icons (using Kodi's built-in icons)
CATEGORY_ICONS = {
    "Generale": "DefaultTVShows.png",
    "Divertisment": "DefaultMusicVideos.png",
    "Sport": "DefaultAddonGame.png",
    "Filme": "DefaultMovies.png",
    "Documentare": "DefaultAddonPVRClient.png",
    "Muzica": "DefaultMusicAlbums.png",
    "Pentru Copii": "DefaultAddonGame.png",
    "Focus Sat": "DefaultAddonService.png",
}


def map_category_name(original_name):
    """Map original category name to display name."""
    return CATEGORY_MAPPING.get(original_name, original_name)


def get_category_icon(category_name):
    """Get icon for a category."""
    return CATEGORY_ICONS.get(category_name, "DefaultFolder.png")


def get_category_sort_key(category_name):
    """Get sort key for a category. Returns index in CATEGORY_ORDER or 999 for unmapped."""
    try:
        return CATEGORY_ORDER.index(category_name)
    except ValueError:
        return 999  # Put unmapped categories at the end


# JSON Server Configuration
_servers_config = None


def load_servers_config():
    """Load server configuration from remote URL or local file."""
    global _servers_config

    if _servers_config is not None:
        return _servers_config

    return _load_servers_config_internal()


def reload_servers_config():
    """Force reload server configuration (clears cache)."""
    global _servers_config
    _servers_config = None
    return _load_servers_config_internal()


def _load_servers_config_internal():
    """Internal function to actually load the config."""
    global _servers_config

    _servers_config = {"servers": []}

    # Try remote URL first
    json_url = _ADDON.getSetting("servers_json_url")
    if json_url and json_url.strip():
        try:
            xbmc.log(
                f"[Config] Fetching servers.json from URL: {json_url}",
                level=xbmc.LOGINFO,
            )
            response = get_session().get(json_url.strip(), timeout=15)
            response.raise_for_status()
            _servers_config = response.json()
            xbmc.log(
                f"[Config] Loaded servers.json from remote URL", level=xbmc.LOGINFO
            )
            return _servers_config
        except Exception as e:
            xbmc.log(f"[Config] Failed to load from URL: {e}", level=xbmc.LOGWARNING)
            # Continue to try local file

    # Try local file
    addon_path = _ADDON.getAddonInfo("path")
    servers_file = os.path.join(addon_path, "servers.json")

    try:
        with open(servers_file, "r", encoding="utf-8") as f:
            _servers_config = json_loads(f)
        xbmc.log(f"[Config] Loaded servers.json from local file", level=xbmc.LOGINFO)
        return _servers_config
    except FileNotFoundError:
        xbmc.log(
            f"[Config] servers.json not found at {servers_file}", level=xbmc.LOGWARNING
        )
        return _servers_config
    except json.JSONDecodeError as e:
        xbmc.log(f"[Config] Invalid JSON in servers.json: {e}", level=xbmc.LOGERROR)
        return _servers_config
    except Exception as e:
        xbmc.log(f"[Config] Error loading servers.json: {e}", level=xbmc.LOGERROR)
        return _servers_config
        return _servers_config


@lru_cache(maxsize=8)
def get_server_config(server_id):
    """Get configuration for a specific server."""
    config = load_servers_config()
    for server in config.get("servers", []):
        if server.get("id") == server_id:
            return server
    return None


@lru_cache(maxsize=8)
def get_portal_url_for_server(server_id):
    """Get portal URL for a server from JSON config."""
    server = get_server_config(server_id)
    if server and server.get("portal_url"):
        return server["portal_url"]
    return None


@lru_cache(maxsize=8)
def get_macs_for_server(server_id):
    """Get MAC addresses for a server from JSON config."""
    server = get_server_config(server_id)
    if server and server.get("macs"):
        return server["macs"]
    return None


@lru_cache(maxsize=8)
def get_server_type(server_id):
    """Get server type for customization from JSON config."""
    server = get_server_config(server_id)
    if server:
        return server.get("type", "stalker")
    return "stalker"


# MAC list cache
_mac_list_cache = {}
_MAC_CACHE_TTL = 7200  # 2 hours in seconds


def get_random_mac_from_file(server="server1"):
    """Get a random MAC address from JSON config only"""
    global _mac_list_cache

    current_time = time.time()

    # Check if we have a valid cached MAC list
    if (
        server in _mac_list_cache
        and (current_time - _mac_list_cache[server]["timestamp"]) < _MAC_CACHE_TTL
    ):
        return random.choice(_mac_list_cache[server]["macs"])

    # JSON config only
    json_macs = get_macs_for_server(server)
    if json_macs and len(json_macs) > 0:
        if server not in _mac_list_cache:
            _mac_list_cache[server] = {"macs": [], "timestamp": 0}
        _mac_list_cache[server]["macs"] = json_macs
        _mac_list_cache[server]["timestamp"] = current_time
        return random.choice(json_macs)

    # No MACs found in JSON
    xbmcgui.Dialog().notification(
        "Error",
        f"No MAC addresses found for {server} in servers.json",
        xbmcgui.NOTIFICATION_ERROR,
    )
    return None


def handshake(portal_url, mac, server="server1"):
    """Perform handshake with Stalker portal to get a session token."""
    session = get_session()
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    cookies = {"mac": mac}

    url = (
        f"{portal_url}/portal.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
    )

    try:
        response = get_session().get(
            url, headers=headers, cookies=cookies, timeout=TIMEOUTS["handshake"]
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            js_data = data.get("js", {})
            if isinstance(js_data, dict):
                token = js_data.get("token")
                if token:
                    return token
                else:
                    xbmc.log(
                        f"[Handshake] No token in response. js data: {js_data}",
                        level=xbmc.LOGWARNING,
                    )
                    return None
            elif isinstance(js_data, list):
                xbmc.log(
                    f"[Handshake] Server returned error list: {js_data}",
                    level=xbmc.LOGWARNING,
                )
                return None
            else:
                xbmc.log(
                    f"[Handshake] Unexpected js data type: {type(js_data)}",
                    level=xbmc.LOGWARNING,
                )
                return None
        elif isinstance(data, list):
            xbmc.log(
                f"[Handshake] Server returned error list at root level: {data}",
                level=xbmc.LOGWARNING,
            )
            return None

        xbmc.log(
            f"[Handshake] Unexpected response format: {type(data)}",
            level=xbmc.LOGWARNING,
        )
        return None
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[Handshake] Request failed: {e}", level=xbmc.LOGERROR)
        return None
    except Exception as e:
        xbmc.log(f"[Handshake] Error: {e}", level=xbmc.LOGERROR)
        return None


# Token cache to avoid handshake for every channel
_token_cache = {"token": None, "mac": None, "timestamp": 0}
_TOKEN_TTL = 600  # 10 minutes

# Current server for EPG operations
_epg_current_server = "server1"

# Category cache (in-memory)
_categories_cache = {}
_CATEGORIES_CACHE_TTL = 604800  # 7 days


def get_server_cache_folder():
    """Get the server cache folder path."""
    addon_profile_path = xbmcaddon.Addon().getAddonInfo("profile")
    try:
        addon_path = xbmcvfs.translatePath(addon_profile_path)
    except:
        addon_path = xbmc.translatePath(addon_profile_path)

    cache_folder = os.path.join(addon_path, "server_cache")
    if not os.path.exists(cache_folder):
        os.makedirs(cache_folder)
    return cache_folder


def get_server_cache_file(server_id):
    """Get the cache file path for a specific server."""
    return os.path.join(get_server_cache_folder(), f"{server_id}_cache.json")


def get_categories_cache_file(server_id):
    """Get the categories cache file path for a specific server."""
    return os.path.join(get_server_cache_folder(), f"{server_id}_categories.json")


def get_channels_cache_file(server_id):
    """Get the channels cache file path for a specific server."""
    return os.path.join(get_server_cache_folder(), f"{server_id}_channels.json")


def load_categories_cache(server_id):
    """Load categories cache from file."""
    cache_file = get_categories_cache_file(server_id)
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                content = f.read()
                if not content:
                    xbmc.log(
                        f"[ServerCache] Categories cache file empty for {server_id}",
                        level=xbmc.LOGDEBUG,
                    )
                    return None
                data = json_loads(content)
            xbmc.log(
                f"[ServerCache] Loaded categories for {server_id}", level=xbmc.LOGDEBUG
            )
            return data
    except Exception as e:
        xbmc.log(
            f"[ServerCache] Failed to load categories for {server_id}: {e}",
            level=xbmc.LOGWARNING,
        )
    return None


def save_categories_cache(server_id, categories):
    """Save categories cache to file."""
    cache_file = get_categories_cache_file(server_id)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json_dumps({"categories": categories, "timestamp": time.time()}, f)
        xbmc.log(f"[ServerCache] Saved categories for {server_id}", level=xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(
            f"[ServerCache] Failed to save categories for {server_id}: {e}",
            level=xbmc.LOGWARNING,
        )


def clear_all_cache(server="server1"):
    """Clear all cache files for a server (categories and channels)."""
    try:
        categories_file = get_categories_cache_file(server)
        channels_file = get_channels_cache_file(server)

        deleted_count = 0

        if categories_file and os.path.exists(categories_file):
            os.remove(categories_file)
            deleted_count += 1
            xbmc.log(f"[Cache] Deleted categories cache: {categories_file}")

        if channels_file and os.path.exists(channels_file):
            os.remove(channels_file)
            deleted_count += 1
            xbmc.log(f"[Cache] Deleted channels cache: {channels_file}")

        if deleted_count > 0:
            xbmcgui.Dialog().notification(
                "Succes",
                f"Cache șters: {deleted_count} fișiere",
                xbmcgui.NOTIFICATION_INFO,
            )
        else:
            xbmcgui.Dialog().notification(
                "Info",
                "Nu există cache de șters",
                xbmcgui.NOTIFICATION_INFO,
            )
    except Exception as e:
        xbmc.log(f"[Cache] Error clearing cache: {e}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "Eroare",
            f"Nu s-a putut șterge cache-ul: {e}",
            xbmcgui.NOTIFICATION_ERROR,
        )


def clear_all_cache_for_all_servers():
    """Clear all cache files for all servers."""
    xbmc.log("[Cache] Starting clear_all_cache_for_all_servers", level=xbmc.LOGINFO)
    try:
        servers_config = reload_servers_config()
        available_servers = servers_config.get("servers", [])
        xbmc.log(f"[Cache] Found {len(available_servers)} servers", level=xbmc.LOGINFO)

        if not available_servers:
            xbmcgui.Dialog().notification(
                "Info",
                "Nu s-au găsit servere",
                xbmcgui.NOTIFICATION_INFO,
            )
            return

        dp = xbmcgui.DialogProgress()
        dp.create("Se șterge cache-ul...", "Se pregătește...")

        total_deleted = 0
        total_servers = len(available_servers)

        for idx, srv in enumerate(available_servers):
            srv_id = srv.get("id")
            srv_name = srv.get("name", srv_id)

            if dp.iscanceled():
                break

            dp.update(
                int((idx / total_servers) * 100),
                f"Se șterge cache pentru {srv_name}...",
            )

            if not srv_id:
                continue

            categories_file = get_categories_cache_file(srv_id)
            channels_file = get_channels_cache_file(srv_id)

            xbmc.log(
                f"[Cache] Checking cache for {srv_id}: categories={categories_file}, channels={channels_file}",
                level=xbmc.LOGDEBUG,
            )

            if categories_file and os.path.exists(categories_file):
                os.remove(categories_file)
                total_deleted += 1
                xbmc.log(f"[Cache] Deleted categories cache for {srv_id}")

            if channels_file and os.path.exists(channels_file):
                os.remove(channels_file)
                total_deleted += 1
                xbmc.log(f"[Cache] Deleted channels cache for {srv_id}")

        dp.close()

        if total_deleted > 0:
            xbmcgui.Dialog().notification(
                "Succes",
                f"Cache șters: {total_deleted} fișiere",
                xbmcgui.NOTIFICATION_INFO,
            )
        else:
            xbmcgui.Dialog().notification(
                "Info",
                "Nu există cache de șters",
                xbmcgui.NOTIFICATION_INFO,
            )
    except Exception as e:
        xbmc.log(f"[Cache] Error clearing all cache: {e}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "Eroare",
            f"Nu s-a putut șterge cache-ul: {e}",
            xbmcgui.NOTIFICATION_ERROR,
        )


def load_channels_cache(server_id):
    """Load channels cache from file."""
    cache_file = get_channels_cache_file(server_id)
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json_loads(f)
            xbmc.log(
                f"[ServerCache] Loaded channels for {server_id}", level=xbmc.LOGDEBUG
            )
            return data
    except Exception as e:
        xbmc.log(
            f"[ServerCache] Failed to load channels for {server_id}: {e}",
            level=xbmc.LOGWARNING,
        )
    return None


def save_channels_cache(server_id, channels):
    """Save channels cache to file."""
    cache_file = get_channels_cache_file(server_id)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json_dumps({"channels": channels, "timestamp": time.time()}, f)
        xbmc.log(
            f"[ServerCache] Saved {len(channels)} channels for {server_id}",
            level=xbmc.LOGDEBUG,
        )
    except Exception as e:
        xbmc.log(
            f"[ServerCache] Failed to save channels for {server_id}: {e}",
            level=xbmc.LOGWARNING,
        )


def load_server_data_cache(server_id):
    """Load server data (categories and channels) from cache file for specific server."""
    cache_file = get_server_cache_file(server_id)
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json_loads(f)
            xbmc.log(f"[ServerCache] Loaded cache for {server_id}", level=xbmc.LOGDEBUG)
            return cache_data
    except Exception as e:
        xbmc.log(
            f"[ServerCache] Failed to load cache for {server_id}: {e}",
            level=xbmc.LOGWARNING,
        )
    return {}


def save_server_data_cache(server_id, cache_data):
    """Save server data (categories and channels) to cache file for specific server."""
    cache_file = get_server_cache_file(server_id)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json_dumps(cache_data, f)
        xbmc.log(f"[ServerCache] Saved cache for {server_id}", level=xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(
            f"[ServerCache] Failed to save cache for {server_id}: {e}",
            level=xbmc.LOGWARNING,
        )


def get_server_auth(server="server1"):
    """Get authentication credentials (MAC and token) for server."""
    portal_url = get_portal_url_for_server(server)
    if not portal_url:
        return None, None, None, portal_url

    mac = get_random_mac_from_file(server)
    if not mac:
        return None, None, None, portal_url

    token = handshake(portal_url, mac, server)
    if not token:
        return None, None, None, portal_url

    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    cookies = {"mac": mac, "token": token}

    return token, headers, cookies, portal_url


def fetch_server_categories(server="server1", force_refresh=False):
    """Fetch categories directly from STB server with file caching."""
    global _categories_cache

    current_time = time.time()
    cache_key = f"categories_{server}"
    session = get_session()

    # Try to load from file cache first
    if not _categories_cache.get(cache_key):
        file_cache = load_categories_cache(server)
        if file_cache and file_cache.get("categories"):
            _categories_cache[cache_key] = file_cache["categories"]
            _categories_cache[f"timestamp_{server}"] = file_cache.get("timestamp", 0)
            xbmc.log(
                f"[Categories] Loaded categories from file cache: {len(_categories_cache[cache_key])}",
                level=xbmc.LOGDEBUG,
            )

    # Return from memory cache if valid
    if (
        not force_refresh
        and cache_key in _categories_cache
        and _categories_cache[cache_key]
        and (current_time - _categories_cache.get(f"timestamp_{server}", 0))
        < _CATEGORIES_CACHE_TTL
    ):
        xbmc.log(
            f"[Categories] Using cached categories for {server}: {len(_categories_cache[cache_key])}",
            level=xbmc.LOGINFO,
        )
        return _categories_cache[cache_key]

    # Need to fetch fresh data
    token, headers, cookies, portal_url = get_server_auth(server)
    if not token or not portal_url:
        xbmc.log("[Categories] Failed to get authentication", level=xbmc.LOGERROR)
        return _categories_cache.get(cache_key)

    url = f"{portal_url}/portal.php?type=itv&action=get_genres&JsHttpRequest=1-xml"

    try:
        response = get_session().get(
            url, headers=headers, cookies=cookies, timeout=TIMEOUTS["categories"]
        )
        response.raise_for_status()
        data = response.json()

        categories = []

        if isinstance(data, dict):
            js_data = data.get("js", {})
            if isinstance(js_data, list):
                for item in js_data:
                    cat_id = item.get("id")
                    cat_title = item.get("title", "")
                    if cat_id and cat_title:
                        categories.append(
                            {
                                "id": cat_id,
                                "title": cat_title.strip(),
                                "original_title": cat_title.strip(),
                            }
                        )
            elif isinstance(js_data, dict):
                genres = js_data.get("genres") or js_data.get("data") or []
                if isinstance(genres, list):
                    for item in genres:
                        cat_id = item.get("id")
                        cat_title = item.get("title") or item.get("name", "")
                        if cat_id and cat_title:
                            categories.append(
                                {
                                    "id": cat_id,
                                    "title": cat_title.strip(),
                                    "original_title": cat_title.strip(),
                                }
                            )

        if categories:
            _categories_cache[cache_key] = categories
            _categories_cache[f"timestamp_{server}"] = current_time

            # Save to file cache (separate file)
            save_categories_cache(server, categories)

            xbmc.log(
                f"[Categories] Fetched {len(categories)} categories from server {server}",
                level=xbmc.LOGINFO,
            )
            return categories

    except Exception as e:
        xbmc.log(f"[Categories] Failed to fetch categories: {e}", level=xbmc.LOGERROR)

    # Return cached if available
    return _categories_cache.get(cache_key)


def clean_category_title(title):
    """Remove Unicode box drawing characters and clean up category title."""
    if not title:
        return ""

    cleaned = RE_BOX_CHARS.sub("", str(title))
    cleaned = cleaned.strip(r"|-[]:() ")
    return cleaned.strip()


def get_romanian_categories(server_categories):
    """Filter categories that are Romanian (must START with RO, Romania, Roumanie, etc.)"""
    if not server_categories:
        return []

    romanian_prefixes = [
        "ro",
        "ro|",
        "ro :",
        "ro-",
        "ro ",
        "ro\u2503",
        "ro\u2502",
        "ro\u2551",
        "ro\u2550",
        "ro\u2588",
        "\u2503ro",
        "\u2502ro",
        "\u2551ro",
        "\u2550ro",
        "\u2588ro",
        "ro[",
        "ro]",
        "[ro]",
        "[ro[",
        "ro(",
        "ro)",
        "ro:",
        "romania",
        "roumanie",
        "romanie",
    ]

    romanian_cats = []
    prefixes_lower = [p.lower() for p in romanian_prefixes]

    for cat in server_categories:
        title = cat["title"].strip()
        title_lower = title.lower()

        is_romanian = False
        for prefix in prefixes_lower:
            if title_lower.startswith(prefix):
                is_romanian = True
                break

        if not is_romanian:
            if RE_CATEGORY_PREFIX.match(title_lower):
                is_romanian = True
                break

        if not is_romanian and title_lower.startswith("ro"):
            if len(title_lower) == 2 or title_lower[2] in " |:-":
                is_romanian = True

        if is_romanian:
            romanian_cats.append(cat)
            xbmc.log(
                f"[Categories] Matched Romanian category: {cat['title']}",
                level=xbmc.LOGDEBUG,
            )

    xbmc.log(
        f"[Categories] Found {len(romanian_cats)} Romanian categories",
        level=xbmc.LOGINFO,
    )
    return romanian_cats


def fetch_channels_by_category_from_server(category_id, server="server1"):
    """Fetch channels for a specific category from server with file caching."""
    current_time = time.time()

    # Try to load from file cache first
    file_cache = load_channels_cache(server)
    channels = None

    if file_cache and file_cache.get("channels"):
        if (current_time - file_cache.get("timestamp", 0)) < _CATEGORIES_CACHE_TTL:
            channels = file_cache["channels"]
            xbmc.log(
                f"[Categories] Loaded {len(channels)} channels from file cache",
                level=xbmc.LOGDEBUG,
            )

    # If not in cache, fetch from server
    if not channels:
        xbmc.log(
            f"[Categories] Fetching all channels from server {server}",
            level=xbmc.LOGINFO,
        )

        token, headers, cookies, portal_url = get_server_auth(server)

        if not token or not portal_url:
            xbmc.log("[Categories] No token or portal URL", level=xbmc.LOGERROR)
            return []

        url = f"{portal_url}/portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml"

        try:
            response = get_session().get(
                url, headers=headers, cookies=cookies, timeout=TIMEOUTS["channels"]
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                js_data = data.get("js", {})
                if isinstance(js_data, list):
                    channels = js_data
                elif isinstance(js_data, dict):
                    channels = js_data.get("data") or js_data.get("channels") or []
                else:
                    return []
            elif isinstance(data, list):
                channels = data
            else:
                return []

            if channels:
                essential_channels = []
                for ch in channels:
                    logo = ch.get("logo") or ""
                    if logo and RE_BOX_CHARS.search(logo):
                        logo = ""

                    essential_channels.append(
                        {
                            "id": ch.get("id"),
                            "name": clean_category_title(ch.get("name")),
                            "cmd": ch.get("cmd"),
                            "logo": logo,
                            "tv_genre_id": ch.get("tv_genre_id"),
                        }
                    )

                # Save to file cache (separate file)
                save_channels_cache(server, essential_channels)
                xbmc.log(
                    f"[Categories] Fetched and cached {len(essential_channels)} channels",
                    level=xbmc.LOGINFO,
                )

        except Exception as e:
            xbmc.log(f"[Categories] Failed to fetch channels: {e}", level=xbmc.LOGERROR)
            return []

    if not channels:
        return []

    # If no category_id specified, return all channels
    if category_id is None:
        xbmc.log(
            f"[Categories] Returning all {len(channels)} channels (no filter)",
            level=xbmc.LOGINFO,
        )
        return channels

    # Filter by category - use tv_genre_id field
    filtered = []
    for ch in channels:
        ch_genre_id = ch.get("tv_genre_id")
        if ch_genre_id is None:
            continue
        if str(ch_genre_id) == str(category_id):
            filtered.append(ch)

    xbmc.log(
        f"[Categories] Filtered {len(filtered)} channels for cat_id={category_id}",
        level=xbmc.LOGINFO,
    )
    return filtered


# Token provider for EPG Manager with caching
def epg_token_provider(server=None):
    """Provide token, headers, and cookies for EPG requests with caching."""
    global _token_cache, _epg_current_server

    # Use current server context if not specified
    if server is None:
        server = _epg_current_server

    portal_url = get_portal_url_for_server(server)
    current_time = time.time()

    # Check if we have a valid cached token
    if (
        _token_cache["token"]
        and _token_cache["mac"]
        and (current_time - _token_cache["timestamp"]) < _TOKEN_TTL
    ):
        xbmc.log(
            f"[EPG] Using cached token (age: {int(current_time - _token_cache['timestamp'])}s)",
            level=xbmc.LOGINFO,
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
            "X-User-Agent": "Model: MAG250; Link: WiFi",
        }

        cookies = {"mac": _token_cache["mac"], "token": _token_cache["token"]}

        return _token_cache["token"], headers, cookies

    # Need fresh token
    xbmc.log("[EPG] Fetching fresh token", level=xbmc.LOGINFO)
    mac = get_random_mac_from_file()

    if not mac:
        xbmc.log("[EPG] Failed to get MAC address", level=xbmc.LOGWARNING)
        return None, {}, {}

    token = handshake(portal_url, mac)

    if not token:
        xbmc.log("[EPG] Failed to get token from handshake", level=xbmc.LOGWARNING)
        return None, {}, {}

    # Cache the token
    _token_cache["token"] = token
    _token_cache["mac"] = mac
    _token_cache["timestamp"] = current_time

    xbmc.log(f"[EPG] Cached new token: {token[:10]}...", level=xbmc.LOGINFO)

    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }

    cookies = {"mac": mac, "token": token}

    return token, headers, cookies


# Initialize EPG Manager AFTER defining token provider (only if enabled)
# Optimized settings for faster EPG fetching with parallel workers
epg_manager = None
if is_epg_enabled():
    epg_portal_url = get_portal_url_for_server("server1")
    epg_manager = EpgManager(
        mode="stalker",
        base_url=epg_portal_url,
        callback=epg_callback,
        token_provider=epg_token_provider,
        connect_timeout=10.0,  # Increased timeout for connection
        read_timeout=30.0,  # Increased timeout for reading
        max_retries=3,  # Retry 3 times on failure
        backoff_factor=1.0,  # More aggressive backoff
        cache_ttl=1800.0,  # 30 minutes cache
        max_items_default=10,
        num_workers=10,  # Process 10 channels in parallel
    )


# Favorites file
FAVORITES_FILE = os.path.join(
    xbmcvfs.translatePath(_ADDON.getAddonInfo("profile")), "favorites_{server}.json"
)


def list_favorites(server="server1"):
    """List favorite channels."""
    # Add "Change MAC" button at the top
    change_mac_button = xbmcgui.ListItem(
        label="[COLOR orange]Change MAC Address[/COLOR]"
    )
    change_mac_button.setArt(
        {"icon": "DefaultIconInfo.png", "thumb": "DefaultIconInfo.png"}
    )
    change_mac_url = f"{_BASE_URL}?mode=change_mac&category=favorites&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE, url=change_mac_url, listitem=change_mac_button, isFolder=False
    )

    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, "r", encoding="utf-8") as f:
            favorites = json_loads(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []

    if not favorites:
        li = xbmcgui.ListItem(label="[COLOR yellow]No favorite channels.[/COLOR]")
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url="", listitem=li, isFolder=False)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    for fav in favorites:
        li = xbmcgui.ListItem(label=fav["name"])
        li.setArt({"thumb": fav.get("logo", ""), "icon": fav.get("logo", "")})
        li.setProperty("IsPlayable", "true")

        url = f"{_BASE_URL}?mode=play&stream_id={fav['stream_id']}&name={quote_plus(fav['name'])}&server={server}"
        if server == "server2" and fav.get("url_template"):
            url += f"&url_template={quote_plus(fav['url_template'])}"

        # Context menu to remove from favorites
        li.addContextMenuItems(
            [
                (
                    "Remove from Favorites",
                    f"RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={fav['stream_id']}&server={server})",
                )
            ]
        )

        xbmcplugin.addDirectoryItem(
            handle=_HANDLE, url=url, listitem=li, isFolder=False
        )

    xbmcplugin.endOfDirectory(_HANDLE)


def add_to_favorites(stream_id, name, logo, server="server1", url_template=None):
    """Add a channel to favorites."""
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, "r", encoding="utf-8") as f:
            favorites = json_loads(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []

    favorite_ids = {fav["stream_id"] for fav in favorites}
    if stream_id not in favorite_ids:
        favorites.append(
            {
                "stream_id": stream_id,
                "name": name,
                "logo": logo,
                "url_template": url_template,
            }
        )
        with open(favorites_file, "w", encoding="utf-8") as f:
            json_dumps(favorites, f)
        xbmcgui.Dialog().notification(
            "Favorites", f"{name} added to favorites", xbmcgui.NOTIFICATION_INFO, 2000
        )
    else:
        xbmcgui.Dialog().notification(
            "Favorites",
            f"{name} is already in favorites",
            xbmcgui.NOTIFICATION_INFO,
            2000,
        )


def remove_from_favorites(stream_id, server="server1"):
    """Remove a channel from favorites."""
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, "r", encoding="utf-8") as f:
            favorites = json_loads(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    favorites = [fav for fav in favorites if fav["stream_id"] != stream_id]

    with open(favorites_file, "w", encoding="utf-8") as f:
        json_dumps(favorites, f)
    xbmcgui.Dialog().notification(
        "Favorites", "Channel removed from favorites", xbmcgui.NOTIFICATION_INFO, 2000
    )
    xbmc.executebuiltin("Container.Refresh")


def get_params():
    """Get the plugin parameters"""
    paramstring = sys.argv[2][1:]
    return dict(parse_qsl(paramstring))


def parse_m3u_channels(m3u_file, server="server1"):
    """
    Parse M3U file and return list of channel dictionaries.
    Centralized M3U parsing to avoid code duplication.

    Args:
        m3u_file: Path to the M3U file
        server: 'server1' or 'server2'

    Returns:
        List of channel dicts with keys: name, group, logo, stream_id, url
    """
    channels = []

    try:
        with open(m3u_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        xbmc.log(f"[M3U] Failed to read {m3u_file}: {e}", level=xbmc.LOGERROR)
        return []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("#EXTINF:") or RE_EXTINF.search(line):
            group_title_match = RE_GROUP_TITLE.search(line)
            tvg_logo_match = RE_TVG_LOGO.search(line)

            last_comma_pos = line.rfind(",")
            if last_comma_pos != -1:
                channel_name = line[last_comma_pos + 1 :].strip()
            else:
                channel_name = "Unknown Channel"

            group_title = (
                group_title_match.group(1).strip()
                if group_title_match
                else "Uncategorized"
            )
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
            group_title = map_category_name(group_title)

            if i + 1 < len(lines):
                url_line = lines[i + 1].strip()
                if url_line and not url_line.startswith("#"):
                    if RE_MACPH_TOKENPH.search(url_line):
                        stream_id = f"s2_{len(channels)}"
                        channels.append(
                            {
                                "name": channel_name,
                                "group": group_title,
                                "logo": tvg_logo,
                                "stream_id": stream_id,
                                "url": url_line,
                            }
                        )
                    else:
                        stream_id_match = RE_STREAM_ID.search(url_line)
                        if stream_id_match:
                            stream_id = stream_id_match.group(1)
                            channels.append(
                                {
                                    "name": channel_name,
                                    "group": group_title,
                                    "logo": tvg_logo,
                                    "stream_id": stream_id,
                                    "url": url_line,
                                }
                            )

        i += 1

    xbmc.log(
        f"[M3U] Parsed {len(channels)} channels from {os.path.basename(m3u_file)}",
        level=xbmc.LOGINFO,
    )
    return channels


def list_channels(server="server1", category=None, category_id=None, from_server=False):
    """List channel categories from server."""
    # Check if portal URL exists
    portal_url = get_portal_url_for_server(server)
    if not portal_url:
        xbmc.log(f"[List] No portal URL configured for {server}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "Error",
            f"No portal URL configured for {server}",
            xbmcgui.NOTIFICATION_ERROR,
        )
        return

    # Get params for backward compatibility
    params = get_params()
    if category is None:
        category = params.get("category")
    if category_id is None:
        category_id = params.get("cat_id")
    if not from_server:
        from_server = params.get("from_server") == "true"

    # If a category is selected, list channels in that category
    if category:
        list_channels_in_category(
            [],
            category,
            server=server,
            category_id=category_id,
            from_server=from_server,
        )
    else:
        # List all available categories
        list_categories([], server=server)


def list_categories(channels, server="server1"):
    """List all available channel categories with Get Full EPG button."""
    # Add "Search" button at the top
    search_button = xbmcgui.ListItem(label="[COLOR yellow]Cauta[/COLOR]")
    search_button.setArt(
        {"icon": "DefaultAddonsSearch.png", "thumb": "DefaultAddonsSearch.png"}
    )
    search_button_url = f"{_BASE_URL}?mode=search&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE, url=search_button_url, listitem=search_button, isFolder=True
    )

    # Add "Favorites" button at the top
    favorites_button = xbmcgui.ListItem(label="[COLOR gold]Favorite[/COLOR]")
    favorites_button.setArt(
        {"icon": "DefaultFavourites.png", "thumb": "DefaultFavourites.png"}
    )
    favorites_button_url = f"{_BASE_URL}?mode=favorites&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE,
        url=favorites_button_url,
        listitem=favorites_button,
        isFolder=True,
    )

    # Get server type
    server_type = get_server_type(server)

    # Add "Get Full EPG" button (only if EPG is enabled and server type supports it)
    if is_epg_enabled() and server_type in ["stalker", "stalker_v2"]:
        epg_button = xbmcgui.ListItem(label="[COLOR yellow]Get Full EPG[/COLOR]")
        epg_button.setArt(
            {"icon": "DefaultAddonPVRClient.png", "thumb": "DefaultAddonPVRClient.png"}
        )
        epg_button_url = f"{_BASE_URL}?mode=get_full_epg&server={server}"
        xbmcplugin.addDirectoryItem(
            handle=_HANDLE, url=epg_button_url, listitem=epg_button, isFolder=True
        )

    # Always use server categories (mandatory with JSON config)
    server_cat_list = []

    # Try to fetch categories from server (works for stalker, stalker_v2 types)
    if server_type in ["stalker", "stalker_v2"]:
        all_server_cats = fetch_server_categories(server)
        if all_server_cats:
            server_cat_list = get_romanian_categories(all_server_cats)
            xbmc.log(
                f"[Categories] Using server categories for {server}: {len(server_cat_list)} found",
                level=xbmc.LOGINFO,
            )

    # Determine which categories to display
    if server_cat_list:
        # If only one category, show channels directly
        if len(server_cat_list) == 1:
            cat = server_cat_list[0]
            xbmc.log(
                f"[Categories] Single category detected: {cat['title']}, showing channels directly",
                level=xbmc.LOGINFO,
            )
            list_channels_in_category(
                [],
                cat["title"],
                server=server,
                category_id=cat["id"],
                from_server=True,
            )
            return

        # Multiple categories - show the list
        categories_to_show = []
        for cat in server_cat_list:
            display_name = clean_category_title(cat["title"])
            # Map to our display format if possible
            mapped = map_category_name(display_name)
            categories_to_show.append(
                {"display": mapped, "original": display_name, "id": cat["id"]}
            )

        # Sort by custom order
        categories_to_show.sort(key=lambda x: get_category_sort_key(x["display"]))

        for cat_info in categories_to_show:
            li = xbmcgui.ListItem(label=cat_info["display"])
            icon = get_category_icon(cat_info["display"])
            li.setArt({"icon": icon, "thumb": icon})

            # Use original category name for server query
            category_url = f"{_BASE_URL}?category={quote_plus(cat_info['original'])}&server={server}&cat_id={cat_info['id']}&from_server=true"

            xbmcplugin.addDirectoryItem(
                handle=_HANDLE, url=category_url, listitem=li, isFolder=True
            )
    else:
        # No categories from server - show error
        xbmc.log(f"[Categories] No categories found for {server}", level=xbmc.LOGERROR)
        li = xbmcgui.ListItem(label="[COLOR red]Error: Cannot load categories[/COLOR]")
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url="", listitem=li, isFolder=False)

        li2 = xbmcgui.ListItem(
            label="[COLOR yellow]Check server URL or internet connection[/COLOR]"
        )
        xbmcplugin.addDirectoryItem(
            handle=_HANDLE, url="", listitem=li2, isFolder=False
        )

    # Add Settings folder at the end
    settings_folder = xbmcgui.ListItem(label="[COLOR cyan]Setari[/COLOR]")
    settings_folder.setArt(
        {"icon": "DefaultAddonService.png", "thumb": "DefaultAddonService.png"}
    )
    settings_folder_url = f"{_BASE_URL}?mode=settings_menu&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE, url=settings_folder_url, listitem=settings_folder, isFolder=True
    )

    xbmcplugin.endOfDirectory(_HANDLE)


def list_channels_in_category(
    all_channels,
    selected_category,
    server="server1",
    category_id=None,
    from_server=False,
):
    """List channels within a specific category."""
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, "r", encoding="utf-8") as f:
            favorites = json_loads(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []
    favorite_stream_ids = {fav["stream_id"] for fav in favorites}

    # Handle server categories
    if from_server and category_id:
        # Fetch channels from server by category
        xbmc.log(
            f"[Categories] Fetching channels for category ID: {category_id}",
            level=xbmc.LOGINFO,
        )
        server_channels = fetch_channels_by_category_from_server(category_id, server)

        if server_channels:
            # Convert server channels to our format
            channels_in_category = []
            for idx, ch in enumerate(server_channels):
                name = clean_category_title(
                    ch.get("name") or ch.get("title") or "Unknown"
                )
                cmd = ch.get("cmd") or ch.get("stream_url") or ""
                logo = ch.get("logo") or ""
                if logo and RE_BOX_CHARS.search(logo):
                    logo = ""

                stream_id_match = RE_STREAM_ID.search(cmd)
                stream_id = (
                    stream_id_match.group(1) if stream_id_match else f"server_{idx}"
                )

                channels_in_category.append(
                    {
                        "name": name,
                        "group": selected_category,
                        "logo": logo,
                        "stream_id": stream_id,
                        "url": cmd,
                    }
                )
            xbmc.log(
                f"[Categories] Got {len(channels_in_category)} channels from server",
                level=xbmc.LOGINFO,
            )
        else:
            channels_in_category = []
    else:
        # Filter channels by the selected category from M3U
        channels_in_category = [
            ch for ch in all_channels if ch["group"] == selected_category
        ]

    # Add "Change MAC" button at the top
    change_mac_button = xbmcgui.ListItem(
        label="[COLOR orange]Change MAC Address[/COLOR]"
    )
    change_mac_button.setArt(
        {"icon": "DefaultIconInfo.png", "thumb": "DefaultIconInfo.png"}
    )
    change_mac_url = f"{_BASE_URL}?mode=change_mac&category={quote_plus(selected_category)}&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE, url=change_mac_url, listitem=change_mac_button, isFolder=False
    )

    # Only load and request EPG if enabled
    if is_epg_enabled() and epg_manager:
        # Set current server for EPG operations
        global _epg_current_server
        _epg_current_server = server

        # Reconfigure EPG manager for the current server
        portal_url = get_portal_url_for_server(server)
        if portal_url:
            epg_manager.reconfigure(base_url=portal_url)

        # Load EPG cache first
        load_epg_cache()

        xbmc.log(
            f"[EPG] Category '{selected_category}' has {len(channels_in_category)} channels",
            level=xbmc.LOGINFO,
        )

        # Count how many channels already have EPG from cache
        channels_with_cached_epg = sum(
            1 for ch in channels_in_category if ch["stream_id"] in epg_data
        )
        xbmc.log(
            f"[EPG] {channels_with_cached_epg}/{len(channels_in_category)} channels have cached EPG",
            level=xbmc.LOGINFO,
        )

        # Request EPG data for ALL channels in the category
        for channel in channels_in_category:
            epg_manager.request(channel, size=10)

        # Calculate adaptive timeout based on number of channels and cache coverage
        num_channels = len(channels_in_category)
        cache_coverage = (
            channels_with_cached_epg / num_channels if num_channels > 0 else 0
        )

        if cache_coverage >= 0.8:
            # Good cache, wait less
            max_wait_time = min(10000, num_channels * 200)  # 200ms per channel, max 10s
            xbmc.log(
                f"[EPG] Good cache coverage ({cache_coverage:.0%}), waiting {max_wait_time}ms",
                level=xbmc.LOGINFO,
            )
        else:
            # Need fresh EPG, estimate ~500ms per channel for network fetch
            max_wait_time = min(45000, num_channels * 500)  # 500ms per channel, max 45s
            xbmc.log(
                f"[EPG] Fetching fresh EPG, waiting up to {max_wait_time}ms",
                level=xbmc.LOGINFO,
            )

        wait_interval = 300  # Check every 300ms
        waited = 0
        last_count = channels_with_cached_epg

        while waited < max_wait_time:
            xbmc.sleep(wait_interval)
            waited += wait_interval

            # Check how many channels have EPG data
            channels_with_epg = sum(
                1 for ch in channels_in_category if ch["stream_id"] in epg_data
            )

            # Log progress if changed
            if channels_with_epg != last_count:
                xbmc.log(
                    f"[EPG] Progress: {channels_with_epg}/{num_channels} channels ({waited}ms elapsed)",
                    level=xbmc.LOGDEBUG,
                )
                last_count = channels_with_epg

            # Exit only if no progress for 5 seconds
            if waited >= 5000 and channels_with_epg == channels_with_cached_epg:
                xbmc.log(
                    f"[EPG] No new EPG after 5s, proceeding with {channels_with_epg}/{num_channels}",
                    level=xbmc.LOGDEBUG,
                )
                break

        # Final count
        final_count = sum(
            1 for ch in channels_in_category if ch["stream_id"] in epg_data
        )
        final_coverage = final_count / num_channels if num_channels > 0 else 0
        xbmc.log(
            f"[EPG] Final: {final_count}/{num_channels} channels ({final_coverage:.0%}) have EPG",
            level=xbmc.LOGINFO,
        )

        # Save updated EPG to cache
        save_epg_cache()

    # Create list items with EPG data
    for channel in channels_in_category:
        # Build channel label with current program
        channel_label = channel["name"]

        # Add current program to label if EPG available and enabled
        if is_epg_enabled() and channel["stream_id"] in epg_data:
            epg_items = epg_data[channel["stream_id"]]
            current_prog = get_current_program(epg_items)
            if current_prog:
                channel_label = f"{channel['name']} - {current_prog}"

        li = xbmcgui.ListItem(label=channel_label)

        # Set thumbnail from tvg-logo if available
        if channel["logo"]:
            li.setArt({"thumb": channel["logo"], "icon": channel["logo"]})

        li.setProperty("IsPlayable", "true")

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel["stream_id"] in epg_data:
            epg_items = epg_data[channel["stream_id"]]
            plot = format_epg_tooltip(epg_items)
            li.setInfo("video", {"plot": plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}&server={server}"
        if server == "server2" and channel.get("url"):
            url += f"&url_template={quote_plus(channel['url'])}"

        # Add context menu for favorites
        context_menu = []
        if channel["stream_id"] in favorite_stream_ids:
            context_menu.append(
                (
                    "Remove from Favorites",
                    f"RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={channel['stream_id']}&server={server})",
                )
            )
        else:
            add_fav_url = f"{_BASE_URL}?mode=add_to_favorites&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}&logo={quote_plus(channel['logo'])}&server={server}"
            if server == "server2" and channel.get("url"):
                add_fav_url += f"&url_template={quote_plus(channel['url'])}"
            context_menu.append(("Add to Favorites", f"RunPlugin({add_fav_url})"))
        li.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(
            handle=_HANDLE, url=url, listitem=li, isFolder=False
        )

    xbmcplugin.endOfDirectory(_HANDLE)


def get_full_epg():
    """Fetch EPG for ALL channels from server."""
    if not is_epg_enabled() or not epg_manager:
        xbmcgui.Dialog().notification(
            "EPG Disabled", "Enable EPG in addon settings", xbmcgui.NOTIFICATION_INFO
        )
        return

    # Get server from params
    params = get_params()
    server = params.get("server", "server1")

    # Get all channels from server
    xbmc.log(f"[EPG] Fetching all channels from {server}", level=xbmc.LOGINFO)

    # Fetch all channels from server
    all_channels = []
    server_cats = fetch_server_categories(server)

    if not server_cats:
        xbmcgui.Dialog().notification(
            "EPG", "Could not fetch categories", xbmcgui.NOTIFICATION_WARNING
        )
        return

    # Fetch channels for each category
    for cat in server_cats[:5]:  # Limit to first 5 categories to avoid long loading
        cat_id = cat.get("id")
        channels = fetch_channels_by_category_from_server(cat_id, server)
        all_channels.extend(channels)
        xbmc.log(
            f"[EPG] Got {len(channels)} channels from category {cat.get('title')}",
            level=xbmc.LOGDEBUG,
        )

    if not all_channels:
        xbmcgui.Dialog().notification(
            "EPG", "No channels found", xbmcgui.NOTIFICATION_WARNING
        )
        return

    total_channels = len(all_channels)
    xbmc.log(f"[EPG] Get Full EPG: Found {total_channels} channels", level=xbmc.LOGINFO)

    # Count how many already cached
    load_epg_cache()
    channels_with_cached_epg = sum(
        1
        for ch in all_channels
        if str(ch.get("id")) in epg_data or str(ch.get("tv_genre_id")) in epg_data
    )
    xbmc.log(
        f"[EPG] {channels_with_cached_epg}/{total_channels} channels already have cached EPG",
        level=xbmc.LOGDEBUG,
    )

    # Create progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create(
        "Fetching Full EPG", f"Requesting EPG for {total_channels} channels..."
    )

    # Request EPG for all channels
    for idx, channel in enumerate(all_channels):
        if progress.iscanceled():
            xbmc.log("[EPG] User cancelled full EPG fetch", level=xbmc.LOGDEBUG)
            progress.close()
            return

        epg_manager.request(channel, size=10)

        # Update progress every 10 channels
        if (idx + 1) % 10 == 0:
            percent = int(((idx + 1) / total_channels) * 30)
            progress.update(
                percent, f"Requested EPG for {idx + 1}/{total_channels} channels..."
            )

    progress.update(30, f"Waiting for EPG data from server...")

    # Calculate timeout based on total channels
    max_wait_time = min(300000, total_channels * 400)
    wait_interval = 500  # Check every 500ms
    waited = 0
    last_count = channels_with_cached_epg

    xbmc.log(
        f"[EPG] Waiting up to {max_wait_time}ms for {total_channels} channels",
        level=xbmc.LOGDEBUG,
    )

    while waited < max_wait_time:
        if progress.iscanceled():
            xbmc.log(
                "[EPG] User cancelled full EPG fetch during wait", level=xbmc.LOGDEBUG
            )
            progress.close()
            save_epg_cache()
            return

        xbmc.sleep(wait_interval)
        waited += wait_interval

        # Check progress
        channels_with_epg = sum(1 for ch in channels if ch["stream_id"] in epg_data)

        # Update progress dialog (30% to 95%)
        progress_percent = 30 + int(((channels_with_epg / total_channels) * 65))
        coverage_percent = int((channels_with_epg / total_channels) * 100)
        progress.update(
            progress_percent,
            f"Received EPG for {channels_with_epg}/{total_channels} channels ({coverage_percent}%)\nElapsed: {waited // 1000}s / {max_wait_time // 1000}s",
        )

        # Log progress if changed
        if channels_with_epg != last_count:
            xbmc.log(
                f"[EPG] Full EPG Progress: {channels_with_epg}/{total_channels} ({coverage_percent}%) - {waited}ms elapsed",
                level=xbmc.LOGDEBUG,
            )
            last_count = channels_with_epg

        # Exit only if no progress for 10 seconds
        if waited >= 10000 and channels_with_epg == channels_with_cached_epg:
            xbmc.log(
                f"[EPG] No new EPG after 10s, finishing with {channels_with_epg}/{total_channels}",
                level=xbmc.LOGDEBUG,
            )
            break

    # Final save
    progress.update(95, "Saving EPG to cache...")
    save_epg_cache()

    # Final stats
    final_count = sum(1 for ch in channels if ch["stream_id"] in epg_data)
    final_coverage = int((final_count / total_channels) * 100)

    progress.update(
        100,
        f"Complete! EPG for {final_count}/{total_channels} channels ({final_coverage}%)",
    )
    xbmc.sleep(1500)  # Show final message for 1.5 seconds
    progress.close()

    xbmc.log(
        f"[EPG] Full EPG fetch complete: {final_count}/{total_channels} ({final_coverage}%)",
        level=xbmc.LOGDEBUG,
    )
    xbmcgui.Dialog().notification(
        "EPG Complete",
        f"Got EPG for {final_count}/{total_channels} channels ({final_coverage}%)",
        xbmcgui.NOTIFICATION_INFO,
        3000,
    )


def generate_random_mac():
    """Generate a random MAC address in the format 00:1A:79:XX:XX:XX"""
    # Using the same manufacturer prefix as existing MACs in the file
    prefix = "00:1A:79"
    # Generate 3 random bytes for the last part
    suffix = ":".join([f"{random.randint(0, 255):02X}" for _ in range(3)])
    return f"{prefix}:{suffix}"


def change_mac(category=None, server="server1"):
    """Change to a new random MAC address and clear token cache."""
    global _token_cache

    # Get a new random MAC from file
    new_mac = get_random_mac_from_file(server)
    if not new_mac:
        xbmcgui.Dialog().notification(
            "Error", "Failed to get new MAC address", xbmcgui.NOTIFICATION_ERROR
        )
        return

    # Clear token cache to force new handshake with new MAC
    _token_cache["token"] = None
    _token_cache["mac"] = None
    _token_cache["timestamp"] = 0

    xbmc.log(f"[MAC] Changed to new MAC: {new_mac}", level=xbmc.LOGDEBUG)
    xbmcgui.Dialog().notification(
        "MAC Changed", f"New MAC: {new_mac}", xbmcgui.NOTIFICATION_INFO, 3000
    )

    # Refresh the category view if we came from a category
    if category:
        xbmc.executebuiltin(f"Container.Refresh")


def play_stream(stream_id, name, server="server1", url_template=None):
    """Get the token and MAC dynamically and resolve the URL for a single stream."""
    portal_url = get_portal_url_for_server(server)
    if not portal_url:
        xbmcgui.Dialog().notification(
            "Error", "Portal URL is not set in settings.", xbmcgui.NOTIFICATION_ERROR
        )
        return

    # Check if this is a Server 2 stream (stream_id starts with s2_)
    if stream_id.startswith("s2_"):
        xbmc.log(f"--- SERVER 2 PLAYBACK START: {name} ---", level=xbmc.LOGDEBUG)

        url_line = url_template
        # Fallback if url_template was not provided (e.g., from old favorites)
        if not url_line:
            addon_path = _ADDON.getAddonInfo("path")
            m3u_file = os.path.join(addon_path, "mag.txt")
            xbmc.log(
                f"[Server 2] Falling back to read M3U file from {m3u_file}",
                level=xbmc.LOGDEBUG,
            )

            try:
                with open(m3u_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                channel_index = int(stream_id.split("_")[1])
                channel_count = 0

                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.startswith("#EXTINF:") or "#EXTINF:" in line.upper():
                        if i + 1 < len(lines):
                            pot_url = lines[i + 1].strip()
                            if (
                                pot_url
                                and not pot_url.startswith("#")
                                and "MACPH" in pot_url
                                and "TOKENPH" in pot_url
                            ):
                                if channel_count == channel_index:
                                    url_line = pot_url
                                    break
                                channel_count += 1
            except Exception as e:
                xbmcgui.Dialog().notification(
                    "Error", f"Failed to load mag.txt: {e}", xbmcgui.NOTIFICATION_ERROR
                )
                return

        if not url_line:
            xbmcgui.Dialog().notification(
                "Error",
                "Channel not found or URL template missing",
                xbmcgui.NOTIFICATION_ERROR,
            )
            return

        # Found our channel! Extract stream ID from URL
        stream_id_match = RE_STREAM_ID.search(url_line)
        if stream_id_match:
            actual_stream_id = stream_id_match.group(1)

            # Perform handshake to get token
            # Extract portal URL from the URL template
            portal_match = re.match(r"(https?://[^/]+)", url_line)
            if portal_match:
                server2_portal_url = portal_match.group(1)

                # Try up to 3 different MACs with loading dialog
                dp = xbmcgui.DialogProgress()
                dp.create("Se caută stream valid...", "Se testează streamul...")
                dp.update(0)

                for mac_attempt in range(3):
                    if dp.iscanceled():
                        dp.close()
                        return

                    dp.update(
                        int((mac_attempt / 3) * 100), f"Se încearcă conectarea..."
                    )

                    random_mac = get_random_mac_from_file(server)
                    if not random_mac:
                        return

                    # Get session token via handshake
                    session_token = handshake(
                        server2_portal_url, random_mac, server="server2"
                    )
                    if not session_token:
                        continue

                    # Create link to get play token
                    headers = {
                        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                        "X-User-Agent": "Model: MAG250; Link: WiFi",
                    }
                    create_link_url = f"{server2_portal_url}/portal.php?action=create_link&type=itv&cmd={actual_stream_id}&JsHttpRequest=1-xml"
                    cookies = {"mac": random_mac, "token": session_token}

                    try:
                        response = get_session().get(
                            create_link_url,
                            headers=headers,
                            cookies=cookies,
                            timeout=TIMEOUTS["playlink"],
                        )
                        response.raise_for_status()
                        link_data = response.json()

                        js_data = link_data.get("js", {})
                        returned_cmd = js_data.get("cmd")

                        if returned_cmd:
                            play_token_match = re.search(
                                r"play_token=([a-zA-Z0-9]+)", returned_cmd
                            )
                            if play_token_match:
                                play_token = play_token_match.group(1)

                                # Replace placeholders in the original URL from template
                                final_url = url_line.replace(
                                    "MACPH", random_mac
                                ).replace("TOKENPH", play_token)

                                # Add User-Agent to the final URL to prevent 405 errors
                                final_url_with_ua = f"{final_url}|User-Agent={quote_plus(headers['User-Agent'])}"

                                dp.close()
                                play_item = xbmcgui.ListItem(path=final_url_with_ua)
                                xbmcplugin.setResolvedUrl(
                                    _HANDLE, True, listitem=play_item
                                )
                                return  # SUCCESS!
                    except requests.exceptions.RequestException as e:
                        continue  # Try next MAC
                    except Exception as e:
                        continue  # Try next MAC

                # All MAC attempts failed
                dp.close()
                xbmcgui.Dialog().notification(
                    "Eroare",
                    "Niciun stream valid găsit. Încearcă din nou.",
                    xbmcgui.NOTIFICATION_ERROR,
                )
                return
            else:
                xbmcgui.Dialog().notification(
                    "Error",
                    "Could not extract portal URL from template",
                    xbmcgui.NOTIFICATION_ERROR,
                )
                return
        else:
            xbmcgui.Dialog().notification(
                "Error",
                "Could not extract stream ID from URL",
                xbmcgui.NOTIFICATION_ERROR,
            )
            return

    # Server 1: Try up to 3 MACs with loading dialog
    dp = xbmcgui.DialogProgress()
    dp.create("Se caută stream valid...", "Se testează streamul...")
    dp.update(0)

    for mac_attempt in range(3):
        if dp.iscanceled():
            dp.close()
            return

        dp.update(int((mac_attempt / 3) * 100), f"Se încearcă conectarea...")

        random_mac = get_random_mac_from_file(server)
        if not random_mac:
            return

        xbmc.log(
            f"[Server1] Attempt {mac_attempt + 1}/3 with MAC: {random_mac}",
            level=xbmc.LOGINFO,
        )

        # Perform handshake to get a fresh token from the server for each request
        session_token = handshake(portal_url, random_mac, server=server)
        if not session_token:
            xbmc.log(
                f"[Server1] Handshake failed for MAC {random_mac}, trying another...",
                level=xbmc.LOGWARNING,
            )
            continue

        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
            "X-User-Agent": "Model: MAG250; Link: WiFi",
        }
        create_link_url = f"{portal_url}/portal.php?type=itv&action=create_link&cmd={stream_id}&JsHttpRequest=1-xml"
        cookies = {"mac": random_mac, "token": session_token}

        try:
            response = get_session().get(
                create_link_url,
                headers=headers,
                cookies=cookies,
                timeout=TIMEOUTS["playlink"],
            )
            response.raise_for_status()
            link_data = response.json()

            # Check if response is a dict (expected) or list (error)
            if isinstance(link_data, dict):
                js_data = link_data.get("js", {})
                if isinstance(js_data, dict):
                    returned_cmd = js_data.get("cmd")
                elif isinstance(js_data, list):
                    xbmc.log(
                        f"[Server1] MAC {random_mac} rejected (empty list), trying another...",
                        level=xbmc.LOGWARNING,
                    )
                    continue  # Try next MAC
                else:
                    xbmc.log(
                        f"[Server1] Unexpected js data type: {type(js_data)}",
                        level=xbmc.LOGWARNING,
                    )
                    continue  # Try next MAC
            elif isinstance(link_data, list):
                xbmc.log(
                    f"[Server1] MAC {random_mac} rejected (root level list), trying another...",
                    level=xbmc.LOGWARNING,
                )
                continue  # Try next MAC
            else:
                xbmc.log(
                    f"[Server1] Unexpected response type: {type(link_data)}",
                    level=xbmc.LOGWARNING,
                )
                continue  # Try next MAC

            if returned_cmd:
                play_token_match = re.search(r"play_token=([a-zA-Z0-9]+)", returned_cmd)
                if play_token_match:
                    play_token = play_token_match.group(1)
                    final_url = f"{portal_url}/play/live.php?mac={random_mac}&stream={stream_id}&extension=ts&play_token={play_token}"
                    xbmc.log(
                        f"[Server1] Successfully playing with MAC: {random_mac}",
                        level=xbmc.LOGINFO,
                    )
                    dp.close()
                    play_item = xbmcgui.ListItem(path=final_url)
                    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)
                    return  # SUCCESS!
                else:
                    xbmc.log(
                        f"[Server1] No play_token in response, trying another MAC...",
                        level=xbmc.LOGWARNING,
                    )
                    continue  # Try next MAC
            else:
                xbmc.log(
                    f"[Server1] No cmd in response, trying another MAC...",
                    level=xbmc.LOGWARNING,
                )
                continue  # Try next MAC

        except requests.exceptions.RequestException as e:
            xbmc.log(
                f"[Server1] Request failed: {e}, trying another MAC...",
                level=xbmc.LOGWARNING,
            )
            continue  # Try next MAC

    # All MAC attempts failed
    dp.close()
    xbmcgui.Dialog().notification(
        "Eroare",
        "Niciun stream valid găsit. Încearcă din nou.",
        xbmcgui.NOTIFICATION_ERROR,
    )


def show_settings_menu(server="server1"):
    """Show settings submenu."""
    # Setari addon
    settings_item = xbmcgui.ListItem(label="Setari addon")
    settings_item.setArt(
        {"icon": "DefaultAddonService.png", "thumb": "DefaultAddonService.png"}
    )
    settings_url = f"{_BASE_URL}?mode=settings&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE, url=settings_url, listitem=settings_item, isFolder=False
    )

    # Sterge cache (pt. acest server)
    clear_cache_item = xbmcgui.ListItem(label="Sterge cache (pt. acest server)")
    clear_cache_item.setArt(
        {"icon": "DefaultAddonRepository.png", "thumb": "DefaultAddonRepository.png"}
    )
    clear_cache_url = f"{_BASE_URL}?mode=clear_cache&server={server}"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE, url=clear_cache_url, listitem=clear_cache_item, isFolder=False
    )

    # Sterge tot cache
    clear_all_cache_item = xbmcgui.ListItem(label="Sterge tot cache")
    clear_all_cache_item.setArt(
        {"icon": "DefaultAddonRepository.png", "thumb": "DefaultAddonRepository.png"}
    )
    clear_all_cache_url = f"{_BASE_URL}?mode=clear_all_cache"
    xbmcplugin.addDirectoryItem(
        handle=_HANDLE,
        url=clear_all_cache_url,
        listitem=clear_all_cache_item,
        isFolder=False,
    )

    xbmcplugin.endOfDirectory(_HANDLE)


def router(params):
    """Router function with global error handling"""
    try:
        xbmc.log(f"[Router] params: {params}", level=xbmc.LOGDEBUG)
        server = params.get("server")
        mode = params.get("mode")

        # Handle clear_all_cache mode early (doesn't require server)
        if mode == "clear_all_cache":
            xbmc.log("[Router] Processing clear_all_cache mode", level=xbmc.LOGINFO)
            clear_all_cache_for_all_servers()
            xbmc.executebuiltin("Container.Refresh")
            return

        # Always reload servers from JSON config (fresh on each request)
        servers_config = reload_servers_config()
        available_servers = servers_config.get("servers", [])

        # If no server specified, show server selection from JSON
        if server is None:
            if len(available_servers) > 1:
                # Show server selection
                for idx, srv in enumerate(available_servers):
                    srv_name = srv.get("name", srv.get("id", "Unknown"))
                    srv_id = srv.get("id", "server1")
                    li = xbmcgui.ListItem(label=srv_name)
                    li.setArt(
                        {"icon": "DefaultNetwork.png", "thumb": "DefaultNetwork.png"}
                    )
                    xbmcplugin.addDirectoryItem(
                        handle=_HANDLE,
                        url=f"{_BASE_URL}?server={srv_id}",
                        listitem=li,
                        isFolder=True,
                    )
                xbmcplugin.endOfDirectory(_HANDLE)
                return
            elif len(available_servers) == 1:
                server = available_servers[0].get("id", "server1")
            else:
                # Fallback to default
                server = "server1"

        params["server"] = server

        mode = params.get("mode")

        xbmc.log(f"[Router] params: {params}", level=xbmc.LOGDEBUG)
        xbmc.log(f"[Router] mode: {mode}", level=xbmc.LOGDEBUG)

        if mode in (
            "play",
            "add_to_favorites",
            "remove_from_favorites",
        ):
            if "stream_id" not in params:
                xbmc.log(
                    f"[Router] Missing stream_id for mode: {mode}", level=xbmc.LOGERROR
                )
                xbmcgui.Dialog().notification(
                    "Error", "Missing stream ID", xbmcgui.NOTIFICATION_ERROR
                )
                return

        if mode == "play":
            play_stream(
                params.get("stream_id"),
                params.get("name", "Unknown"),
                server=server,
                url_template=params.get("url_template"),
            )
        elif mode == "add_to_favorites":
            add_to_favorites(
                params.get("stream_id"),
                params.get("name", "Unknown"),
                params.get("logo", ""),
                server=server,
                url_template=params.get("url_template"),
            )
        elif mode == "remove_from_favorites":
            remove_from_favorites(params.get("stream_id"), server=server)

        if server == "both" and mode is None:
            for idx, srv in enumerate(available_servers):
                srv_name = srv.get("name", srv.get("id", "Unknown"))
                srv_id = srv.get("id", "server1")
                li = xbmcgui.ListItem(label=srv_name)
                li.setArt({"icon": "DefaultNetwork.png", "thumb": "DefaultNetwork.png"})
                xbmcplugin.addDirectoryItem(
                    handle=_HANDLE,
                    url=f"{_BASE_URL}?server={srv_id}",
                    listitem=li,
                    isFolder=True,
                )
            xbmcplugin.endOfDirectory(_HANDLE)
            return

        if mode is None:
            list_channels(
                server=server,
                category=params.get("category"),
                category_id=params.get("cat_id"),
                from_server=params.get("from_server") == "true",
            )
        elif mode == "get_full_epg":
            get_full_epg()
        elif mode == "search":
            corrected_search_channels(server=server)
        elif mode == "change_mac":
            change_mac(params.get("category"), server=server)
        elif mode == "settings_menu":
            show_settings_menu(server=server)
        elif mode == "settings":
            _ADDON.openSettings()
            xbmc.executebuiltin("Container.Refresh")
        elif mode == "clear_cache":
            clear_all_cache(server=server)
            xbmc.executebuiltin("Container.Refresh")
        elif mode == "clear_all_cache":
            xbmc.log("[Router] Processing clear_all_cache mode", level=xbmc.LOGINFO)
            clear_all_cache_for_all_servers()
            xbmc.executebuiltin("Container.Refresh")
        elif mode == "favorites":
            list_favorites(server=server)

    except KeyError as e:
        xbmc.log(
            f"[Router] KeyError: {e}, mode: {params.get('mode')}, params: {params}",
            level=xbmc.LOGERROR,
        )
        xbmcgui.Dialog().notification(
            "Error", f"Missing parameter: {e}", xbmcgui.NOTIFICATION_ERROR
        )
    except Exception as e:
        xbmc.log(
            f"[Router] Unexpected error: {type(e).__name__}: {e}", level=xbmc.LOGERROR
        )
        xbmcgui.Dialog().notification(
            "Error",
            f"An unexpected error occurred: {type(e).__name__}",
            xbmcgui.NOTIFICATION_ERROR,
        )
    finally:
        # Only stop epg_manager if it exists
        if epg_manager:
            epg_manager.stop()


def corrected_search_channels(server="server1"):
    """Search for channels by name."""
    # Get search term from keyboard
    search_term = xbmcgui.Dialog().input("Cauta canal", type=xbmcgui.INPUT_ALPHANUM)
    if not search_term:
        xbmcplugin.endOfDirectory(_HANDLE, succeeded=False)
        return

    # Get all channels from cache/server
    channels = fetch_channels_by_category_from_server(None, server)
    if not channels:
        xbmcgui.Dialog().notification(
            "Eroare", "Nu s-au putut obtine canalele", xbmcgui.NOTIFICATION_ERROR
        )
        xbmcplugin.endOfDirectory(_HANDLE, succeeded=False)
        return

    # Load favorites for context menu
    favorites_file = FAVORITES_FILE.format(server=server)
    try:
        with open(favorites_file, "r", encoding="utf-8") as f:
            favorites = json_loads(f)
    except (FileNotFoundError, json.JSONDecodeError):
        favorites = []
    favorite_stream_ids = {fav["stream_id"] for fav in favorites}

    # Filter channels based on search term
    search_term_lower = search_term.lower()
    matching_channels = []
    for ch in channels:
        stream_id_match = RE_STREAM_ID.search(ch.get("cmd", ""))
        stream_id = stream_id_match.group(1) if stream_id_match else None
        if stream_id and search_term_lower in ch.get("name", "").lower():
            matching_channels.append(
                {
                    "stream_id": stream_id,
                    "name": ch.get("name"),
                    "logo": ch.get("logo"),
                    "cmd": ch.get("cmd"),
                }
            )

    # Create list items for matching channels
    for channel in matching_channels:
        # Build channel label with current program
        channel_label = channel["name"]

        # Add current program to label if EPG available and enabled
        if is_epg_enabled() and channel["stream_id"] in epg_data:
            epg_items = epg_data[channel["stream_id"]]
            current_prog = get_current_program(epg_items)
            if current_prog:
                channel_label = f"{channel['name']} - {current_prog}"

        li = xbmcgui.ListItem(label=channel_label)

        # Set thumbnail from tvg-logo if available
        if channel["logo"]:
            li.setArt({"thumb": channel["logo"], "icon": channel["logo"]})

        li.setProperty("IsPlayable", "true")

        # Set EPG data if available and enabled
        if is_epg_enabled() and channel["stream_id"] in epg_data:
            epg_items = epg_data[channel["stream_id"]]
            plot = format_epg_tooltip(epg_items)
            li.setInfo("video", {"plot": plot})

        # Create URL to play this specific channel
        url = f"{_BASE_URL}?mode=play&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}&server={server}"
        if server == "server2" and channel.get("url"):
            url += f"&url_template={quote_plus(channel['url'])}"

        # Add context menu for favorites
        context_menu = []
        if channel["stream_id"] in favorite_stream_ids:
            context_menu.append(
                (
                    "Remove from Favorites",
                    f"RunPlugin({_BASE_URL}?mode=remove_from_favorites&stream_id={channel['stream_id']}&server={server})",
                )
            )
        else:
            add_fav_url = f"{_BASE_URL}?mode=add_to_favorites&stream_id={channel['stream_id']}&name={quote_plus(channel['name'])}&logo={quote_plus(channel['logo'])}&server={server}"
            if server == "server2" and channel.get("url"):
                add_fav_url += f"&url_template={quote_plus(channel['url'])}"
            context_menu.append(("Add to Favorites", f"RunPlugin({add_fav_url})"))
        li.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(
            handle=_HANDLE, url=url, listitem=li, isFolder=False
        )

    # Show a message if no results found
    if not matching_channels:
        li = xbmcgui.ListItem(
            label=f'[COLOR red]No channels found for "{search_term}"[/COLOR]'
        )
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(handle=_HANDLE, url="", listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)


if __name__ == "__main__":
    check_version_compatibility()
    router(get_params())
