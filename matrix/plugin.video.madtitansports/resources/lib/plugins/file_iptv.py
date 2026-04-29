import re
import requests
import sqlite3
import os
import json
import time
from urllib.parse import urlparse, parse_qs, quote_plus
from threading import Thread

import xbmc
import xbmcgui
import xbmcaddon
from xbmcvfs import translatePath

from ..plugin import Plugin
from ..util.dialogs import link_dialog
from resources.lib.plugin import run_hook

# Addon paths
addon = xbmcaddon.Addon()
USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "file_iptv_config.json")
DB_PATH = os.path.join(USER_DATA_DIR, "file_iptv.db")
RECENT_PATH = os.path.join(USER_DATA_DIR, "file_iptv_recent.json")

if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

# Basic HTTP headers to improve compatibility with some panels
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
        "Gecko/20100101 Firefox/117.0"
    ),
    "Accept": "*/*",
    "Referer": "",
}


M3U_USERNAME = "__M3U__"

# Config
DEFAULT_CONFIG = {
    
    "servers_txt": "http://magnetic.website/MAD_TITAN_SPORTS/Keep_m3u_json/zone1.txt",
    "exclude_groups": ["xxx", "adult", "18+"],
    "total_result_limit": 1000,
    "per_address_limit": 1000,
    # How often to re-validate known good servers (in hours)
    "recheck_hours": 12,
    # Minimum connections required for a server to be accepted
    "min_connections": 2,
    # Max number of servers to validate per update run
    "max_servers_per_update": 50,
    # Whether to test stream URLs during validation
    "stream_check_enabled": True,
    # How many candidate channels to test per server when stream_check_enabled is True
    "stream_check_candidates": 5,
    # Preferred channel name keywords for stream tests
    "test_channel_keywords": [
        "espn",
        "sky sports",
        "tnt",
        "nba",
        "nfl",
        "tsn",
        "fox sports",
        "nbc sports",
    ],
    
    "m3u_sources": [],
    
    "exclude_names": [
        "BR:",
        "ARG:",
        "MEX:"
    ],
    # Proxy behavior: "auto", "jetproxy", or "direct"
    "proxy_mode": "auto",
    # Enable automatic background server updates based on recheck_hours
    "auto_update_enabled": False,
    # Timestamp of the last automatic update (epoch seconds)
    "last_auto_update_ts": 0,
    # Enable extra debug logging for searches, etc.
    "debug_logging": False,
}

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
except Exception:
    config = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


def save_config():
    """Save current config to disk."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        xbmc.log(f"[file_iptv] Failed to save config: {e}", xbmc.LOGERROR)


def should_auto_update_now() -> bool:
    """Determine if enough time has passed to run an automatic update."""
    enabled = bool(config.get("auto_update_enabled", True))
    if not enabled:
        return False

    try:
        recheck_hours = int(config.get("recheck_hours", 12))
    except Exception:
        recheck_hours = 12
    if recheck_hours <= 0:
        # 0 or negative means "no scheduled auto-update"
        return False

    interval = recheck_hours * 3600
    now = int(time.time())
    last_ts = int(config.get("last_auto_update_ts", 0) or 0)
    return (now - last_ts) >= interval

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                address TEXT,
                username TEXT,
                password TEXT,
                last_checked INTEGER DEFAULT 0,
                is_valid INTEGER DEFAULT 0,
                PRIMARY KEY (address, username, password)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                address TEXT,
                username TEXT,
                password TEXT,
                stream_id TEXT,
                name TEXT,
                search TEXT,
                stream_url TEXT,
                PRIMARY KEY (address, username, password, stream_id),
                FOREIGN KEY (address, username, password)
                    REFERENCES servers(address, username, password)
            )
        """)
        # Ensure newer columns exist
        try:
            conn.execute("ALTER TABLE servers ADD COLUMN max_connections INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE channels ADD COLUMN stream_url TEXT")
        except Exception:
            pass
        # Whether this server's channels should appear in search results.
        # Keep it separate from is_valid so a server can stay in the
        # database and keep updating but be hidden from the UI if desired.
        try:
            conn.execute("ALTER TABLE servers ADD COLUMN search_enabled INTEGER DEFAULT 1")
        except Exception:
            pass
        conn.commit()


def load_recent_searches(max_items: int = 20):
    """Load recent search history from JSON file."""
    if not os.path.exists(RECENT_PATH):
        return []
    try:
        with open(RECENT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[:max_items]
    except Exception as e:
        xbmc.log(f"[file_iptv] Failed to load recent searches: {e}", xbmc.LOGERROR)
    return []


def save_recent_search(term, country):
    """Append a search to history, de-duplicating on (term,country)."""
    entry = {
        "term": term,
        "country": country or "",
        "time": int(time.time()),
    }
    history = load_recent_searches(max_items=50)
    # Remove existing identical entry
    history = [h for h in history if not (h.get("term") == entry["term"] and h.get("country", "") == entry["country"])]
    history.insert(0, entry)
    # Trim
    if len(history) > 50:
        history = history[:50]
    try:
        with open(RECENT_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        xbmc.log(f"[file_iptv] Failed to save recent searches: {e}", xbmc.LOGERROR)

def clean_string(s: str) -> str:
    s = s.strip()
    # Remove leading country/region codes like "US - ", "UK: ", but
    # do NOT strip normal words like "FOX " or "TNT ". Require a separator.
    s = re.sub(r'^[A-Z]{2,3}[-:]\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\|\s?[A-Z]{2,3}\s?(8K|4K|UHD|FHD|HD|SD|HDR)$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\|\s?(8K|4K|UHD|FHD|HD|SD|HDR)\s?[A-Z]{2,3}$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\|\s?[A-Z]{2,3}$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(8k|4k|uhd|fhd|hd|sd|hdr)\b', '', s, flags=re.IGNORECASE)
    s = s.lower()
    s = s.replace('bally', 'fanduel')  # Do NOT strip 'network'
    s = re.sub(r".*[|\-:\]]\s+(.*)", r"\1", s)
    s = re.sub(r'^\(.*?\)', '', s)
    s = re.sub(r'\(.*?\)$', '', s)
    s = re.sub(r'\[.*?\]$', '', s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s.strip()

def parse_server_url(line: str):
    """Parse one m3u/m3u_plus URL into (address, username, password)."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    try:
        parsed = urlparse(line)
        if parsed.scheme not in ("http", "https"):
            return None

        # Strip userinfo (e.g. "tvappapk@" in tvappapk@tv.zapping.life:8080)
        netloc = parsed.netloc.split("@", 1)[-1]
        address = f"{parsed.scheme}://{netloc}"

        qs = parse_qs(parsed.query)
        username = qs.get("username", [""])[0]
        password = qs.get("password", [""])[0]
        if not (address and username and password):
            return None
        return (address, username, password)
    except Exception as e:
        xbmc.log(f"[file_iptv] Failed to parse server URL '{line}': {e}", xbmc.LOGERROR)
        return None


def load_m3u_sources():
    """Return a list of generic M3U playlist sources from config."""
    sources = config.get("m3u_sources", [])
    if isinstance(sources, str):
        out = [s.strip() for s in sources.split(",") if s.strip()]
    elif isinstance(sources, list):
        out = [str(s).strip() for s in sources if str(s).strip()]
    else:
        out = []
    return out

def load_servers_from_txt():
    """Load up to the needed number of unique (address, username, password) tuples from configured TXT."""
    path = config.get("servers_txt", "").strip()
    if not path:
        return []

    try:
        max_needed = int(config.get("max_servers_per_update", 50) or 50)
        if path.startswith(("http://", "https://")):
            resp = requests.get(path, timeout=10, headers=HTTP_HEADERS)
            resp.raise_for_status()
            lines = resp.text.splitlines()
        else:
            local_path = translatePath(path)
            if not os.path.exists(local_path):
                xbmc.log(f"[file_iptv] TXT file not found: {local_path}", xbmc.LOGWARNING)
                return []
            with open(local_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        servers = []
        seen = set()
        m3u_found = set()
        for line in lines:
            if len(servers) >= max_needed:
                break
            cred = parse_server_url(line)
            if cred and cred not in seen:
                seen.add(cred)
                servers.append(cred)
            else:
                candidate = line.strip()
                if (
                    candidate
                    and not candidate.startswith("#")
                    and candidate.startswith(("http://", "https://"))
                    and ".m3u" in candidate.lower()
                ):
                    m3u_found.add(candidate)

        # If any generic M3U/M3U8 URLs are present in the TXT, merge them
        # into the m3u_sources config so they will be indexed by
        # update_m3u_playlists().
        if m3u_found:
            existing = load_m3u_sources()
            combined = []
            seen_src = set()
            for src in existing + list(m3u_found):
                if src not in seen_src:
                    seen_src.add(src)
                    combined.append(src)
            config["m3u_sources"] = combined
            save_config()

        xbmc.log(
            f"[file_iptv] Loaded {len(servers)} xtream servers from TXT; {len(m3u_found)} M3U sources detected",
            xbmc.LOGINFO,
        )
        return servers
    except Exception as e:
        xbmc.log(f"[file_iptv] Error loading TXT: {e}", xbmc.LOGERROR)
        return []


def update_m3u_playlists():
    """Fetch and index channels from configured M3U playlists."""
    sources = load_m3u_sources()
    if not sources:
        return

    now = int(time.time())

    for src in sources:
        try:
            # Fetch playlist content
            if src.startswith(("http://", "https://")):
                resp = requests.get(src, timeout=15, headers=HTTP_HEADERS)
                resp.raise_for_status()
                text = resp.text
            else:
                local_path = translatePath(src)
                if not os.path.exists(local_path):
                    xbmc.log(f"[file_iptv] M3U file not found: {local_path}", xbmc.LOGWARNING)
                    continue
                with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            channels = []
            current_name = None
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("#EXTINF"):
                    # Standard M3U: name is after the last comma
                    if "," in line:
                        name = line.split(",", 1)[1].strip()
                    else:
                        name = line
                    current_name = name
                elif line.startswith("#"):
                    continue
                else:
                    url = line
                    name = current_name or url
                    channels.append((name, url))
                    current_name = None

            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                # Represent each playlist as a synthetic server keyed by the
                # playlist URL/path and M3U_USERNAME.
                cur.execute(
                    """
                    INSERT OR REPLACE INTO servers
                    (address, username, password, last_checked, is_valid, max_connections)
                    VALUES (?, ?, ?, ?, 1, 0)
                    """,
                    (src, M3U_USERNAME, "", now),
                )

                # Clear any existing channels for this playlist
                cur.execute(
                    """
                    DELETE FROM channels
                    WHERE address = ? AND username = ? AND password = ?
                    """,
                    (src, M3U_USERNAME, ""),
                )

                for idx, (name, url) in enumerate(channels):
                    search = clean_string(name)
                    stream_id = f"m3u_{idx}"
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO channels
                        (address, username, password, stream_id, name, search, stream_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (src, M3U_USERNAME, "", stream_id, name, search, url),
                    )

                conn.commit()

            xbmc.log(
                f"[file_iptv] Indexed {len(channels)} channels from M3U source: {src}",
                xbmc.LOGINFO,
            )
        except Exception as e:
            xbmc.log(f"[file_iptv] Failed to load M3U source {src}: {e}", xbmc.LOGERROR)

def validate_server(server):
    """Validate an IPTV server and get its channels using Xtream API."""
    address, username, password = server
    try:
        params = {"username": username, "password": password}

        user_data = requests.get(
            f"{address}/player_api.php",
            timeout=12,
            params=params,
            headers=HTTP_HEADERS,
        ).json()

        max_conn_raw = user_data.get("user_info", {}).get("max_connections", 0)
        try:
            max_conn = int(max_conn_raw or 0)
        except Exception:
            max_conn = 0

        # Require at least the configured minimum number of connections
        try:
            min_conn_required = int(config.get("min_connections", 2) or 0)
        except Exception:
            min_conn_required = 0
        if min_conn_required < 0:
            min_conn_required = 0

        if max_conn < min_conn_required:
            xbmc.log(
                f"[file_iptv] Server failed: Max connections {max_conn} < required {min_conn_required}",
                xbmc.LOGINFO,
            )
            return False

        status = user_data.get("user_info", {}).get("status", "")
        if status != "Active":
            xbmc.log(f"[file_iptv] Server failed: Status = {status}", xbmc.LOGINFO)
            return False

        panel_data = requests.get(
            f"{address}/panel_api.php",
            timeout=25,
            params=params,
            headers=HTTP_HEADERS,
        ).json()

        if "available_channels" not in panel_data:
            xbmc.log(f"[file_iptv] Server failed: No available_channels", xbmc.LOGINFO)
            return False

        # Optional stream reachability check, controlled by config.
        if config.get("stream_check_enabled", True):
            channels = list(panel_data.get("available_channels", {}).values())
            if not channels:
                xbmc.log(f"[file_iptv] Server failed: available_channels is empty", xbmc.LOGINFO)
                return False

            # Prefer sports-branded test channels if present; otherwise fall
            # back to the first few channels.
            default_keywords = [
                "espn",
                "sky sports",
                "tnt",
                "nba",
                "nfl",
                "tsn",
                "fox sports",
                "nbc sports",
            ]
            cfg_keywords = config.get("test_channel_keywords", default_keywords)
            if isinstance(cfg_keywords, str):
                # Allow comma-separated string in config; normalize to list
                test_keywords = [k.strip().lower() for k in cfg_keywords.split(",") if k.strip()]
            else:
                test_keywords = [str(k).strip().lower() for k in cfg_keywords if str(k).strip()]
            if not test_keywords:
                test_keywords = default_keywords

            def is_preferred_channel(ch):
                name = (ch.get("name") or "").lower()
                return any(k in name for k in test_keywords)

            preferred = [ch for ch in channels if is_preferred_channel(ch)]

            try:
                max_candidates = int(config.get("stream_check_candidates", 5) or 5)
            except Exception:
                max_candidates = 5
            if max_candidates <= 0:
                max_candidates = 1

            candidates = preferred[:max_candidates] if preferred else channels[:max_candidates]

            stream_ok = False
            for ch in candidates:
                stream_id = ch.get("stream_id")
                if not stream_id:
                    continue
                # Some panels use HLS (.m3u8), others TS (.ts). Try both
                # extensions before deciding the stream is unreachable.
                for ext in ("m3u8", "ts"):
                    test_url = f"{address}/live/{username}/{password}/{stream_id}.{ext}"
                    try:
                        with requests.get(test_url, timeout=7, stream=True, headers=HTTP_HEADERS) as resp:
                            if resp.status_code != 200:
                                continue
                            # Try to read a small chunk; if this works the
                            # stream is at least reachable and not immediately 4xx.
                            try:
                                next(resp.iter_content(chunk_size=2048))
                            except StopIteration:
                                pass
                            stream_ok = True
                            break
                    except Exception as e:
                        xbmc.log(f"[file_iptv] Test stream failed {test_url}: {e}", xbmc.LOGDEBUG)
                if stream_ok:
                    break

            if not stream_ok:
                xbmc.log(
                    f"[file_iptv] Server failed: no test channel playable via HTTP",
                    xbmc.LOGINFO,
                )
                return False

        xbmc.log(f"[file_iptv] Server validated: {address} (max_conn={max_conn})", xbmc.LOGINFO)
        return panel_data, max_conn
    except (json.JSONDecodeError, ValueError) as e:
        xbmc.log(f"[file_iptv] Server failed {address}: Invalid JSON (server dead or offline)", xbmc.LOGINFO)
        return False
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[file_iptv] Server validation error {address}: {e}", xbmc.LOGERROR)
        return None
    except Exception as e:
        xbmc.log(f"[file_iptv] Server validation error {address}: {e}", xbmc.LOGERROR)
        return None

def store_server_channels(server, panel_data, max_conn):
    address, username, password = server
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Preserve search_enabled if server already exists
            cur = conn.cursor()
            cur.execute("""
                SELECT search_enabled FROM servers WHERE address = ? AND username = ? AND password = ?
            """, (address, username, password))
            row = cur.fetchone()
            if row is not None:
                search_enabled = row[0]
            else:
                search_enabled = 1
            conn.execute("""
                INSERT OR REPLACE INTO servers (address, username, password, last_checked, is_valid, max_connections, search_enabled)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (address, username, password, int(time.time()), int(max_conn), search_enabled))

            exclude_groups = [g.lower() for g in config.get("exclude_groups", [])]
            exclude_names = [n.lower() for n in config.get("exclude_names", [])]
            for channel in panel_data.get("available_channels", {}).values():
                name = (channel.get("name") or "").strip()
                if not name:
                    continue

                # Skip if name matches any excluded name pattern
                name_l = name.lower()
                if any(ex in name_l for ex in exclude_names):
                    continue

                category = (channel.get("category_name") or "").strip().lower()
                if any(ex in category for ex in exclude_groups):
                    continue

                search = clean_string(name)
                conn.execute("""
                    INSERT OR REPLACE INTO channels
                    (address, username, password, stream_id, name, search)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (address, username, password, channel["stream_id"], name, search))

            conn.commit()

        xbmc.log(f"[file_iptv] Stored channels for: {address}", xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"[file_iptv] Failed to store {address}: {e}", xbmc.LOGERROR)
        return False

def search_channels(term, limit=20, per_address=5, country_filter=None):
    cleaned = clean_string(term)
    # Log the raw and cleaned search terms for debugging (optional)
    if config.get("debug_logging", False):
        xbmc.log(f"[file_iptv] search term='{term}' cleaned='{cleaned}'", xbmc.LOGINFO)
    like_pattern = f"%{cleaned}%"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT c.address, c.username, c.password, c.stream_id, c.name, c.search, c.stream_url, s.max_connections
            FROM channels c
            JOIN servers s ON c.address = s.address
                          AND c.username = s.username
                          AND c.password = s.password
            WHERE s.is_valid = 1
              AND COALESCE(s.search_enabled, 1) = 1
              AND c.search LIKE ?
            ORDER BY LENGTH(c.search) - LENGTH(?)
        """, (like_pattern, cleaned))
        rows = cur.fetchall()
    if config.get("debug_logging", False):
        xbmc.log(f"[file_iptv] total DB matches before filter: {len(rows)}", xbmc.LOGINFO)

    # Optional country filter based on original channel name
    if country_filter:
        cf = country_filter.strip().lower()
        if cf:
            rows = [
                r for r in rows
                if cf in (r["name"] or "").lower()
            ]
            if config.get("debug_logging", False):
                xbmc.log(
                    f"[file_iptv] matches after country filter '{cf}': {len(rows)}",
                    xbmc.LOGINFO,
                )

    # Always log original and cleaned channel names for 'USA Network' search
    if cleaned.replace(" ","") == "usanetwork" or term.strip().lower().replace(" ","") == "usanetwork":
        before_len = len(rows)
        def usa_network_match(name):
            cn = clean_string(name)
            xbmc.log(f"[file_iptv] USA Network debug: original='{name}' cleaned='{cn}'", xbmc.LOGINFO)
            return "usanetwork" in cn
        rows = [
            r for r in rows
            if usa_network_match(r["name"])
        ]
        xbmc.log(f"[file_iptv] USA Network filter: {before_len} -> {len(rows)}", xbmc.LOGINFO)

    # Term-specific exclusion rules: for some very broad base queries like
    # "ESPN" we want to hide certain variants (e.g. PLUS, NCAAB, vs) unless
    # the user explicitly includes those words in the query. This avoids
    # clutter when searching for the main channel while still allowing
    # targeted searches like "ESPN PLUS" or "ESPN NCAAB" to work.
    raw_term = (term or "").strip().lower()
    if raw_term == "espn":
        special_words = ["plus", "vs", "ncaab","play"]
        # Only filter these variants when the user did *not* ask for them
        if not any(w in raw_term for w in special_words):
            before_len = len(rows)
            rows = [
                r for r in rows
                if not any(w in (r["name"] or "").lower() for w in special_words)
            ]
            if config.get("debug_logging", False):
                xbmc.log(
                    f"[file_iptv] ESPN base search: filtered {before_len - len(rows)} variants with special words",
                    xbmc.LOGINFO,
                )

    is_digit = cleaned[-1].isdigit() if cleaned else False
    filtered = [
        r for r in rows
        if is_digit or not re.match(re.escape(cleaned) + r"\d", r["search"], re.IGNORECASE)
    ]
    if config.get("debug_logging", False):
        xbmc.log(f"[file_iptv] matches after digit-filter: {len(filtered)}", xbmc.LOGINFO)

    results = []
    counts = {}
    for r in filtered:
        addr = r["address"]
        counts.setdefault(addr, 0)
        if counts[addr] >= per_address:
            continue
        counts[addr] += 1

        conn_num_val = r["max_connections"] if "max_connections" in r.keys() else 0
        label_num = "-" if not conn_num_val else str(conn_num_val)

        # For Xtream servers, construct the standard live URL. For generic
        # M3U-sourced channels, use the stored stream_url directly.
        if r["stream_url"]:
            base_stream = r["stream_url"]
        else:
            base_stream = f"{r['address']}/live/{r['username']}/{r['password']}/{r['stream_id']}.m3u8"

        # Choose scheme based on proxy_mode and whether we have a known
        # max_connections value: in auto mode, use direct:// when there is
        # no connection count (label "-") and jetproxy:// otherwise.
        proxy_mode = config.get("proxy_mode", "auto")
        if proxy_mode == "jetproxy":
            scheme = "jetproxy"
        elif proxy_mode == "direct":
            scheme = "direct"
        else:
            scheme = "direct" if label_num == "-" else "jetproxy"
        proxied_stream = f"{scheme}://{base_stream}"
        encoded_stream = quote_plus(proxied_stream)

        # Relative route path within this addon for router/url_for_path
        route_path = f"sportjetextractors/play?urls={encoded_stream}"
        # Full plugin URL for direct playback (used by dialog mode)
        plugin_url = f"plugin://plugin.video.madtitansports/{route_path}"

        # For M3U-sourced channels, show a simple label instead of the
        # synthetic username marker.
        if r["username"] == M3U_USERNAME:
            server_label = f"{addr} (M3U)"
        else:
            server_label = f"{addr} ({r['username'][:8]}...)"
        results.append({
            "name": f"[COLORyellow]{label_num}[/COLOR] {r['name']} [{server_label}]",
            "address": plugin_url,
            "path": route_path,
        })

        if len(results) >= limit:
            break

    return results

class FileIPTV(Plugin):
    name = "file_iptv"
    priority = 100

    def __init__(self):
        init_db()
        # Optionally kick off a background auto-update when the addon is
        # opened, based on the configured recheck_hours interval.
        if should_auto_update_now():
            def _worker():
                try:
                    xbmcgui.Dialog().notification(
                        "File IPTV",
                        "Auto-updating IPTV servers in background...",
                        xbmcgui.NOTIFICATION_INFO,
                        5000,
                    )
                except Exception:
                    pass

                try:
                    # Run update silently (no progress dialog/summary) and
                    # then show a small notification with the results.
                    stats = self.update_servers(show_progress=False, show_summary=False)
                    config["last_auto_update_ts"] = int(time.time())
                    save_config()

                    try:
                        if isinstance(stats, dict):
                            checked = int(stats.get("checked", 0) or 0)
                            valid = int(stats.get("validated", 0) or 0)
                            invalid = int(stats.get("invalidated", 0) or 0)
                            msg = f"Auto-update done | Checked: {checked}, Valid: {valid}, Removed: {invalid}"
                        else:
                            msg = "Auto-update complete (no servers needed refresh)."
                        xbmcgui.Dialog().notification(
                            "File IPTV",
                            msg,
                            xbmcgui.NOTIFICATION_INFO,
                            8000,
                        )
                    except Exception:
                        pass
                except Exception as e:
                    xbmc.log(f"[file_iptv] Auto-update error: {e}", xbmc.LOGERROR)

            t = Thread(target=_worker)
            t.daemon = True
            t.start()

    def process_item(self, item):
        # Full-page search variant
        if "full_file_iptv" in item:
            query = item.get("full_file_iptv")

            # If configured with "full_file_iptv": "*" and country "*",
            # prompt for both channel and country, then show a full-page list.
            if query == "*" and item.get("country") == "*":
                item["link"] = f"{self.name}/full_search_prompt_country"
            elif query == "*":
                # Channel-only prompt, full-page list
                item["link"] = f"{self.name}/full_search_prompt"
            else:
                # Fixed term
                item["link"] = f"{self.name}/full_search/{query}"

            # This opens a sub-directory (full page of results)
            item["is_dir"] = True
            item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
            return item

        if self.name in item:
            query = item.get(self.name)

            # Special value to open the Recent searches dialog
            if query == "recent":
                item["link"] = f"{self.name}/recent"
                item["is_dir"] = False
                item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
                return item

            # If configured with "file_iptv": "*", defer to a prompt route
            if query == "*" and item.get("country") == "*":
                # Country + term prompt
                item["link"] = f"{self.name}/search_prompt_country"
            elif query == "*":
                # Term-only prompt
                item["link"] = f"{self.name}/search_prompt"
            else:
                item["link"] = f"{self.name}/search/{query}"

            item["is_dir"] = False
            item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
            return item

    def routes(self, plugin):
        @plugin.route(f"/{self.name}/recent")
        def recent():
            """Show recent searches in a dialog and re-run selection."""
            history = load_recent_searches()
            if not history:
                xbmcgui.Dialog().ok("Recent IPTV", "No recent searches yet.")
                return

            labels = []
            for h in history:
                term = h.get("term", "")
                country = h.get("country", "") or "Any"
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(h.get("time", 0)))
                labels.append(f"[B]{term}[/B]  [COLORyellow]({country})[/COLOR]\n[COLORgrey]{ts}[/COLOR]")

            idx = link_dialog(labels, return_idx=True, hide_links=False)
            if idx is None:
                return

            entry = history[idx]
            country = entry.get("country", "")
            term = entry.get("term", "")
            if not term:
                return

            if country:
                combined = f"{country}:::{term}"
            else:
                combined = term

            # Call the search handler directly instead of redirecting
            # through the router to avoid nested busy dialogs.
            search(combined)

        @plugin.route(f"/{self.name}/recent_entry/<idx>")
        def recent_entry(idx):
            """Re-run a recent search (opens dialog like normal search)."""
            try:
                idx = int(idx)
            except ValueError:
                return

            history = load_recent_searches()
            if idx < 0 or idx >= len(history):
                return

            entry = history[idx]
            country = entry.get("country", "")
            term = entry.get("term", "")
            if not term:
                return

            if country:
                combined = f"{country}:::{term}"
            else:
                combined = term

            # Reuse the main search handler directly
            search(combined)

        @plugin.route(f"/{self.name}/full_search_prompt_country")
        def full_search_prompt_country():
            """Full-page: prompt for channel, then optional country, then show list."""
            dlg = xbmcgui.Dialog()
            term = dlg.input("IPTV Search", type=xbmcgui.INPUT_ALPHANUM)
            if not term:
                return

            country = dlg.input("Country filter (e.g. US, USA)", type=xbmcgui.INPUT_ALPHANUM)
            if not country:
                country = ""

            combined = f"{country}:::{term}"
            plugin.redirect(f"/{self.name}/full_search/{combined}")

        @plugin.route(f"/{self.name}/full_search_prompt")
        def full_search_prompt():
            """Full-page: prompt only for channel, then show list."""
            dlg = xbmcgui.Dialog()
            term = dlg.input("IPTV Search", type=xbmcgui.INPUT_ALPHANUM)
            if not term:
                return

            plugin.redirect(f"/{self.name}/full_search/{term}")

        @plugin.route(f"/{self.name}/full_search/<query>")
        def full_search(query):
            # Decode optional country filter if present
            country_filter = None
            term = query
            if ":::" in query:
                country_filter, term = query.split(":::", 1)

            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM servers WHERE is_valid = 1")
                server_count = cur.fetchone()[0]

            if server_count == 0:
                # Auto-load from TXT once if empty
                self.update_servers()

            results = search_channels(
                term,
                limit=config.get("total_result_limit", 20),
                per_address=config.get("per_address_limit", 5),
                country_filter=country_filter,
            )

            if not results:
                xbmcgui.Dialog().ok("IPTV Search", f"No channels found matching '{term}'")
                return

            # Save to recent history
            save_recent_search(term, country_filter)

            jen_list = []

            proxy_mode = config.get("proxy_mode", "auto")
            debug_on = bool(config.get("debug_logging", False))
            status_label = f"[COLORgrey]Proxy: {proxy_mode} | Debug: {'On' if debug_on else 'Off'}[/COLOR]"
            status_li = xbmcgui.ListItem(status_label)
            status_li.setProperty("IsPlayable", "false")
            jen_list.append({
                "link": "",  # non-clickable header row
                "is_dir": False,
                "list_item": status_li,
            })

            for r in results:
                li = xbmcgui.ListItem(r["name"])
                li.setProperty("IsPlayable", "true")
                jen_list.append({
                    "link": r["path"],
                    "is_dir": False,
                    "list_item": li,
                })

            run_hook("display_list", jen_list)

        @plugin.route(f"/{self.name}/search_prompt_country")
        def search_prompt_country():
            """Prompt for channel, then optional country, then call main search."""
            dlg = xbmcgui.Dialog()
            # 1) Ask for channel/search term first
            term = dlg.input("IPTV Search", type=xbmcgui.INPUT_ALPHANUM)
            if not term:
                return
            # 2) Then ask for country filter (can be left blank to mean no filter)
            country = dlg.input("Country filter (e.g. US, USA)", type=xbmcgui.INPUT_ALPHANUM)
            if not country:
                country = ""
            # Encode both pieces into one path segment, then parse in search()
            combined = f"{country}:::{term}"
            plugin.redirect(f"/{self.name}/search/{combined}")

        @plugin.route(f"/{self.name}/search_prompt")
        def search_prompt():
            """Prompt user for a search term, then reuse the normal search route."""
            dlg = xbmcgui.Dialog()
            query = dlg.input("IPTV Search", type=xbmcgui.INPUT_ALPHANUM)
            if not query:
                return

            plugin.redirect(f"/{self.name}/search/{query}")

        @plugin.route(f"/{self.name}/search/<query>")
        def search(query):
            # Decode optional country filter if present
            country_filter = None
            term = query
            if ":::" in query:
                country_filter, term = query.split(":::", 1)

            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM servers WHERE is_valid = 1")
                server_count = cur.fetchone()[0]

            if server_count == 0:
                # Auto-load from TXT once if empty
                self.update_servers()

            results = search_channels(
                term,
                limit=config.get("total_result_limit", 20),
                per_address=config.get("per_address_limit", 5),
                country_filter=country_filter,
            )

            if not results:
                xbmcgui.Dialog().ok("IPTV Search", f"No channels found matching '{term}'")
                return

            # Save to recent history
            save_recent_search(term, country_filter)

            idx = link_dialog([r["name"] for r in results], return_idx=True, hide_links=False)
            if idx is None:
                return

            stream_url = results[idx]["address"]
            liz = xbmcgui.ListItem(results[idx]["name"])
            liz.setProperty("IsPlayable", "true")
            xbmc.Player().play(stream_url, liz)

        @plugin.route(f"/{self.name}/update")
        def update():
            xbmc.log("[file_iptv] update() called from settings menu", xbmc.LOGERROR)
            init_db()
            self.update_servers()
            xbmc.log("[file_iptv] update_servers() finished", xbmc.LOGERROR)
            # Summary dialog is shown inside update_servers()

        @plugin.route(f"/{self.name}/reset")
        def reset():
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                "IPTV Reset",
                "Delete the database and start fresh? This will remove all servers/channels.",
            ):
                return
            try:
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                    xbmc.log(f"[file_iptv] Deleted database: {DB_PATH}", xbmc.LOGINFO)
                dialog.ok("IPTV Reset", "Database cleared! Run update to rebuild.")
            except Exception as e:
                xbmc.log(f"[file_iptv] Reset error: {e}", xbmc.LOGERROR)
                dialog.ok("IPTV Reset", f"Error: {e}")

        @plugin.route(f"/{self.name}/manage_servers")
        def manage_servers():
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.address,
                           s.username,
                           s.password,
                           s.last_checked,
                           COALESCE(s.search_enabled, 1) AS search_enabled
                    FROM servers s
                    JOIN channels c ON c.address = s.address
                                    AND c.username = s.username
                                    AND c.password = s.password
                    WHERE s.is_valid = 1
                    GROUP BY s.address, s.username, s.password, s.last_checked, search_enabled
                    ORDER BY s.last_checked DESC
                    LIMIT 200
                """)
                # Convert rows to dicts so we can update search_enabled
                # in-memory when the user toggles it.
                servers = [dict(r) for r in cur.fetchall()]

            if not servers:
                xbmcgui.Dialog().ok("Manage Servers", "No servers with channels in database.")
                return

            server_list = []
            for row in servers:
                ts = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(row["last_checked"]),
                ) if row["last_checked"] else "Never"
                visible = "[B][COLORgreen]ON[/COLOR][/B]" if row.get("search_enabled", 1) else "[COLORred]OFF[/COLOR]"
                server_list.append(f"[{visible}] {row['address']} ({row['username'][:8]}...) - {ts}")

            while True:
                idx = link_dialog(server_list, return_idx=True, hide_links=False)
                if idx is None:
                    break

                selected_server = servers[idx]
                addr = selected_server["address"]
                user = selected_server["username"]
                pw = selected_server["password"]

                # Let the user choose to test, update, delete, or toggle visibility.
                action = xbmcgui.Dialog().select(
                    "Server action",
                    [
                        "Test server",
                        "Update server now",
                        "Delete server",
                        "Toggle in search results",
                        "Back",
                    ],
                )
                if action in (-1, 4):
                    continue

                # Test the selected server without modifying the DB
                if action == 0:
                    result = validate_server((addr, user, pw))
                    if isinstance(result, tuple):
                        panel_data, max_conn = result
                        ch_count = len(panel_data.get("available_channels", {}))
                        xbmcgui.Dialog().ok(
                            "Test Server",
                            f"Server OK\nMax connections: {max_conn}\nChannels: {ch_count}",
                        )
                    elif result is False:
                        xbmcgui.Dialog().ok(
                            "Test Server",
                            "Server failed validation.\n(See log for details.)",
                        )
                    else:
                        xbmcgui.Dialog().ok(
                            "Test Server",
                            "Transient error while testing.\n(See log for details.)",
                        )
                    continue

                # Update the selected server and refresh its channels in the DB
                if action == 1:
                    result = validate_server((addr, user, pw))
                    # Valid server: store/refresh channels
                    if isinstance(result, tuple):
                        panel_data, max_conn = result
                        ch_count = len(panel_data.get("available_channels", {}))
                        stored_ok = store_server_channels((addr, user, pw), panel_data, max_conn)
                        if stored_ok:
                            xbmcgui.Dialog().ok(
                                "Update Server",
                                f"Server updated.\nMax connections: {max_conn}\nChannels: {ch_count}",
                            )
                        else:
                            xbmcgui.Dialog().ok(
                                "Update Server",
                                "Server validated but failed to store channels.\n(See log for details.)",
                            )
                    # Definitively invalid: mark as invalid and clear channels
                    elif result is False:
                        try:
                            with sqlite3.connect(DB_PATH) as conn:
                                cur = conn.cursor()
                                cur.execute(
                                    """
                                    UPDATE servers
                                    SET last_checked = ?, is_valid = 0
                                    WHERE address = ? AND username = ? AND password = ?
                                    """,
                                    (int(time.time()), addr, user, pw),
                                )
                                cur.execute(
                                    """
                                    DELETE FROM channels
                                    WHERE address = ? AND username = ? AND password = ?
                                    """,
                                    (addr, user, pw),
                                )
                                conn.commit()
                            xbmcgui.Dialog().ok(
                                "Update Server",
                                "Server failed validation and was marked invalid.\nAll its channels were removed.",
                            )
                        except Exception as e:
                            xbmc.log(f"[file_iptv] Update server invalidate error {addr}: {e}", xbmc.LOGERROR)
                            xbmcgui.Dialog().ok(
                                "Update Server",
                                f"Error while marking server invalid: {e}",
                            )
                    # Transient error
                    else:
                        xbmcgui.Dialog().ok(
                            "Update Server",
                            "Transient error while updating this server.\n(See log for details.)",
                        )
                    continue

                # Delete the selected server and its channels
                if action == 2:
                    confirm_msg = (
                        f"Delete server:\n{addr}\n({user})?\n"
                        "This removes all its channels too."
                    )
                    if not xbmcgui.Dialog().yesno("Delete Server", confirm_msg):
                        continue

                    try:
                        with sqlite3.connect(DB_PATH) as conn:
                            cur = conn.cursor()
                            cur.execute("""
                                DELETE FROM channels
                                WHERE address = ? AND username = ? AND password = ?
                            """, (addr, user, pw))
                            cur.execute("""
                                DELETE FROM servers
                                WHERE address = ? AND username = ? AND password = ?
                            """, (addr, user, pw))
                            conn.commit()

                        xbmc.log(f"[file_iptv] Deleted server: {addr}", xbmc.LOGINFO)
                        del server_list[idx]
                        del servers[idx]
                        xbmcgui.Dialog().ok("Delete Server", f"Deleted {addr} and its channels.")
                        if not server_list:
                            break
                    except Exception as e:
                        xbmc.log(f"[file_iptv] Delete error {addr}: {e}", xbmc.LOGERROR)
                        xbmcgui.Dialog().ok("Delete Server", f"Error: {e}")

                # Toggle whether this server participates in search
                if action == 3:
                    try:
                        with sqlite3.connect(DB_PATH) as conn:
                            cur = conn.cursor()
                            cur.execute(
                                """
                                UPDATE servers
                                SET search_enabled = CASE COALESCE(search_enabled, 1)
                                                        WHEN 1 THEN 0 ELSE 1 END
                                WHERE address = ? AND username = ? AND password = ?
                                """,
                                (addr, user, pw),
                            )
                            conn.commit()

                        # Reflect change in local list/labels
                        current_flag = 1 if selected_server.get("search_enabled", 1) else 0
                        new_flag = 0 if current_flag else 1
                        selected_server["search_enabled"] = new_flag
                        visible = "[COLORgreen]ON[/COLOR]" if new_flag else "[COLORred]OFF[/COLOR]"
                        ts = time.strftime(
                            "%Y-%m-%d %H:%M",
                            time.localtime(selected_server["last_checked"]),
                        ) if selected_server["last_checked"] else "Never"
                        server_list[idx] = f"[{visible}] {addr} ({user[:8]}...) - {ts}"
                    except Exception as e:
                        xbmc.log(f"[file_iptv] Toggle search visibility error {addr}: {e}", xbmc.LOGERROR)
                        xbmcgui.Dialog().ok("Server action", f"Error toggling visibility: {e}")

            xbmcgui.Dialog().ok("Manage Servers", "Done managing servers.")

        @plugin.route(f"/{self.name}/settings")
        def settings():
            """Simple UI to tweak file_iptv settings and clear history."""
            dlg = xbmcgui.Dialog()

            while True:
                total_limit = config.get("total_result_limit", 1000)
                per_addr = config.get("per_address_limit", 1000)
                servers_txt = config.get("servers_txt", "")
                recheck_hours = config.get("recheck_hours", 12)
                min_conn_required = config.get("min_connections", 3)
                max_servers = config.get("max_servers_per_update", 10)
                stream_check_enabled = bool(config.get("stream_check_enabled", True))
                stream_candidates = config.get("stream_check_candidates", 5)
                proxy_mode = config.get("proxy_mode", "auto")
                auto_update_enabled = bool(config.get("auto_update_enabled", False))
                debug_logging = bool(config.get("debug_logging", False))
                tk = config.get("test_channel_keywords", [])
                if isinstance(tk, str):
                    keywords_str = tk
                elif isinstance(tk, list):
                    keywords_str = ", ".join(str(x) for x in tk)
                else:
                    keywords_str = ""

                # Mask the Servers TXT value in the menu so the full URL/path
                # is not exposed; still use the real value when editing.
                if servers_txt:
                    masked_servers_txt = "." * max(8, min(len(servers_txt), 24))
                else:
                    masked_servers_txt = ""
                
                choices = [
                    f"Total results per search: [B][COLORyellow]{total_limit}[/COLOR][/B]",
                    f"Per-server result cap: [B][COLORlime]{per_addr}[/COLOR][/B]",
                    f"Servers TXT: [COLORgrey]{masked_servers_txt}[/COLOR]",
                    "Reset Servers TXT to built-in default",
                    f"Server re-check interval: [B][COLORyellow]{recheck_hours}[/COLOR][/B] hours",
                    f"Minimum connections per server: [B][COLORlime]{min_conn_required}[/COLOR][/B]",
                    f"Servers to validate per update: [B][COLORyellow]{max_servers}[/COLOR][/B]",
                    f"Stream check: [B]{'[COLORgreen]Enabled[/COLOR]' if stream_check_enabled else '[COLORred]Disabled[/COLOR]'}[/B]",
                    f"Stream check candidates: [B][COLORyellow]{stream_candidates}[/COLOR][/B] channels/server",
                    f"Preferred test channel names: [COLORaqua]{keywords_str}[/COLOR]",
                    f"Proxy mode: [B][COLORyellow]{proxy_mode}[/COLOR][/B]",
                    f"Auto-update in background: [B]{'[COLORgreen]Enabled[/COLOR]' if auto_update_enabled else '[COLORred]Disabled[/COLOR]'}[/B]",
                    "Manage M3U sources",
                    f"Debug logging: [B]{'[COLORgreen]On[/COLOR]' if debug_logging else '[COLORred]Off[/COLOR]'}[/B]",
                    "Update file servers now",
                    "Manage file servers",
                    "Reset IPTV database (clear DB file)",
                    "View recent searches",
                    "Clear recent searches",
                    "Close",
                ]

                idx = dlg.select("File IPTV Settings", choices)
                if idx in (-1, len(choices) - 1):
                    break

                # Change total_result_limit
                if idx == 0:
                    val = dlg.input(
                        "Total results per search",
                        defaultt=str(total_limit),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["total_result_limit"] = int(val)
                        save_config()

                # Change per_address_limit
                elif idx == 1:
                    val = dlg.input(
                        "Per-server result cap",
                        defaultt=str(per_addr),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["per_address_limit"] = int(val)
                        save_config()

                # Change servers_txt path/URL
                elif idx == 2:
                    # Do not reveal the existing value; start blank and
                    # treat empty input as "no change". Also hide typed
                    # characters where supported.
                    try:
                        val = dlg.input(
                            "Servers TXT (URL or path)",
                            defaultt="",
                            type=xbmcgui.INPUT_ALPHANUM,
                            option=xbmcgui.ALPHANUM_HIDE_INPUT,
                        )
                    except TypeError:
                        # Fallback for older Kodi without option param
                        val = dlg.input(
                            "Servers TXT (URL or path)",
                            defaultt="",
                            type=xbmcgui.INPUT_ALPHANUM,
                        )

                    if val:
                        config["servers_txt"] = val.strip()
                        save_config()

                # Reset servers_txt back to the built-in default value
                elif idx == 3:
                    default_txt = DEFAULT_CONFIG.get("servers_txt", "").strip()
                    if not default_txt:
                        dlg.ok("Reset Servers TXT", "No built-in default TXT is defined.")
                    else:
                        if dlg.yesno(
                            "Reset Servers TXT",
                            "Reset Servers TXT URL/path to the built-in default?",
                        ):
                            config["servers_txt"] = default_txt
                            save_config()

                # Change recheck interval (hours)
                elif idx == 4:
                    val = dlg.input(
                        "Server re-check interval (hours)",
                        defaultt=str(recheck_hours),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["recheck_hours"] = int(val)
                        save_config()

                # Minimum connections required per server
                elif idx == 5:
                    val = dlg.input(
                        "Minimum connections per server",
                        defaultt=str(min_conn_required),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit():
                        config["min_connections"] = int(val)
                        save_config()

                # Max servers per update run (affects validation LIMIT)
                elif idx == 6:
                    val = dlg.input(
                        "Servers to validate per update",
                        defaultt=str(max_servers),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["max_servers_per_update"] = int(val)
                        save_config()

                # Toggle stream check on/off
                elif idx == 7:
                    config["stream_check_enabled"] = not stream_check_enabled
                    save_config()

                # Number of candidate channels to test per server
                elif idx == 8:
                    val = dlg.input(
                        "Stream check candidates per server",
                        defaultt=str(stream_candidates),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["stream_check_candidates"] = int(val)
                        save_config()

                # Preferred test channel keywords
                elif idx == 9:
                    val = dlg.input(
                        "Preferred test channel names (comma-separated)",
                        defaultt=keywords_str,
                        type=xbmcgui.INPUT_ALPHANUM,
                    )
                    if val:
                        parts = [p.strip() for p in val.split(",") if p.strip()]
                        if parts:
                            config["test_channel_keywords"] = parts
                            save_config()

                # Proxy mode: auto, jetproxy, or direct
                elif idx == 10:
                    options = [
                        "auto (jetproxy for servers, direct for unknown)",
                        "force jetproxy",
                        "force direct",
                    ]
                    current = config.get("proxy_mode", "auto")
                    try:
                        cur_idx = {"auto": 0, "jetproxy": 1, "direct": 2}.get(current, 0)
                    except Exception:
                        cur_idx = 0
                    sel = dlg.select("Proxy mode", options)
                    if sel in (0, 1, 2):
                        config["proxy_mode"] = ["auto", "jetproxy", "direct"][sel]
                        save_config()

                # Toggle background auto-update
                elif idx == 11:
                    config["auto_update_enabled"] = not auto_update_enabled
                    save_config()

                # Manage generic M3U sources list
                elif idx == 12:
                    sources = load_m3u_sources()
                    while True:
                        labels = list(sources) + ["[Add new]", "[Back]"]
                        sel = dlg.select("M3U Sources", labels)
                        if sel in (-1, len(labels) - 1):
                            break
                        # Add new source
                        if sel == len(labels) - 2:
                            val = dlg.input(
                                "Add M3U source URL or path",
                                type=xbmcgui.INPUT_ALPHANUM,
                            )
                            if val:
                                new_src = val.strip()
                                if new_src and new_src not in sources:
                                    sources.append(new_src)
                                    config["m3u_sources"] = sources
                                    save_config()
                            continue
                        # Remove existing source
                        if 0 <= sel < len(sources):
                            to_remove = sources[sel]
                            if dlg.yesno("Remove M3U source", f"Delete:\n{to_remove} ?"):
                                del sources[sel]
                                config["m3u_sources"] = sources
                                save_config()

                # Toggle debug logging
                elif idx == 13:
                    config["debug_logging"] = not debug_logging
                    save_config()

                # Update servers now (same as /file_iptv/update)
                elif idx == 14:
                    update()

                # Manage servers list (same as /file_iptv/manage_servers)
                elif idx == 15:
                    manage_servers()

                # Reset the IPTV database file (same as /file_iptv/reset)
                elif idx == 16:
                    reset()

                # View recent searches (read-only list)
                elif idx == 17:
                    history = load_recent_searches()
                    if not history:
                        dlg.ok("Recent IPTV", "No recent searches yet.")
                    else:
                        labels = []
                        for h in history:
                            term = h.get("term", "")
                            country = h.get("country", "") or "Any"
                            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(h.get("time", 0)))
                            labels.append(f"[B]{term}[/B]  [COLORyellow]({country})[/COLOR]\n[COLORgrey]{ts}[/COLOR]")
                        # Ignore the return value; this is just for
                        # inspection, not for re-running searches.
                        link_dialog(labels, return_idx=False, hide_links=False)

                # Clear recent search history
                elif idx == 18:
                    if dlg.yesno("Recent IPTV", "Clear recent search history?"):
                        try:
                            if os.path.exists(RECENT_PATH):
                                os.remove(RECENT_PATH)
                            dlg.ok("Recent IPTV", "Recent searches cleared.")
                        except Exception as e:
                            xbmc.log(f"[file_iptv] Failed to clear recent: {e}", xbmc.LOGERROR)
                            dlg.ok("Recent IPTV", f"Error clearing history: {e}")

        # Workaround for: No route to path "/https://magnetic.website/MAD_TITAN_SPORTS/TOOLS/tools.json"
        @plugin.route("/https://magnetic.website/MAD_TITAN_SPORTS/TOOLS/tools.json")
        def tools_root_redirect():
            """
            Redirect legacy entry point
            plugin://plugin.video.madtitansports/https://.../TOOLS/tools.json
            to the existing message/ route that the addon already handles.
            """
            # Hand off to the core handler so this request returns proper directory items
            plugin.redirect(
                "/message/https://magnetic.website/MAD_TITAN_SPORTS/TOOLS/tools.json"
            )

    def update_servers(self, show_progress=True, show_summary=True):
        """Load servers from TXT, validate, and update database with a fixed limit, always filling with valid servers. Scans entire TXT if needed."""

        dialog = xbmcgui.DialogProgress() if show_progress else None
        if dialog:
            dialog.create("IPTV Update", "Loading servers from TXT...")

        max_servers = int(config.get("max_servers_per_update", 50) or 50)

        # Get current valid servers
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT address, username, password, is_valid FROM servers WHERE username <> ?", (M3U_USERNAME,))
            db_servers = cur.fetchall()
            valid_servers = [s for s in db_servers if s[3] == 1]
            # Remove excess servers if over the limit
            if len(valid_servers) > max_servers:
                to_remove = valid_servers[max_servers:]
                for s in to_remove:
                    cur.execute("DELETE FROM channels WHERE address = ? AND username = ? AND password = ?", (s[0], s[1], s[2]))
                    cur.execute("DELETE FROM servers WHERE address = ? AND username = ? AND password = ?", (s[0], s[1], s[2]))
                conn.commit()

        validated = len(valid_servers)
        attempted = set((s[0], s[1], s[2]) for s in db_servers)
        servers_added = 0
        servers_removed = 0

        # Re-validate existing valid servers to check if they're still working
        revalidate_list = list(valid_servers)
        for s in revalidate_list:
            server = (s[0], s[1], s[2])
            key = server
            if key in attempted:
                continue
            xbmc.log(f"[file_iptv] Re-validating existing server: {server[0]}", xbmc.LOGINFO)
            result = validate_server(server)
            if isinstance(result, tuple):
                # Still valid, update channels
                panel_data, max_conn = result
                store_server_channels(server, panel_data, max_conn)
                attempted.add(key)
            elif result is False:
                # Server is now invalid, remove it
                attempted.add(key)
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM channels WHERE address = ? AND username = ? AND password = ?", (server[0], server[1], server[2]))
                        cur.execute("DELETE FROM servers WHERE address = ? AND username = ? AND password = ?", (server[0], server[1], server[2]))
                        conn.commit()
                    validated -= 1
                    servers_removed += 1
                    xbmc.log(f"[file_iptv] Removed stale server: {server[0]}", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[file_iptv] Failed to remove stale server: {e}", xbmc.LOGERROR)
            else:
                # Transient error, keep as is for now
                attempted.add(key)

        # Read the entire TXT file for candidates
        all_candidates = []
        path = config.get("servers_txt", "").strip()
        try:
            if path.startswith(("http://", "https://")):
                resp = requests.get(path, timeout=10, headers=HTTP_HEADERS)
                resp.raise_for_status()
                lines = resp.text.splitlines()
            else:
                local_path = translatePath(path)
                if not os.path.exists(local_path):
                    xbmc.log(f"[file_iptv] TXT file not found: {local_path}", xbmc.LOGWARNING)
                    lines = []
                else:
                    with open(local_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
            for line in lines:
                cred = parse_server_url(line)
                if cred and cred not in all_candidates:
                    all_candidates.append(cred)
        except Exception as e:
            xbmc.log(f"[file_iptv] Error loading TXT: {e}", xbmc.LOGERROR)
            all_candidates = []

        xbmc.log(f"[file_iptv] Loaded {len(all_candidates)} candidates from TXT file", xbmc.LOGERROR)
        for i, c in enumerate(all_candidates[:3]):
            xbmc.log(f"[file_iptv] Candidate {i}: {c}", xbmc.LOGERROR)

        idx = 0
        while validated < max_servers and idx < len(all_candidates):
            server = all_candidates[idx]
            idx += 1
            key = (server[0], server[1], server[2])
            if key in attempted:
                continue
            xbmc.log(f"[file_iptv] Validating server candidate: {server[0]} {server[1]}", xbmc.LOGINFO)
            xbmc.log(f"[file_iptv] Validating server candidate: {server[0]} {server[1]}", xbmc.LOGERROR)
            result = validate_server(server)
            if isinstance(result, tuple):
                panel_data, max_conn = result
                store_server_channels(server, panel_data, max_conn)
                validated += 1
                servers_added += 1
                attempted.add(key)
                xbmc.log(f"[file_iptv] Server validated and added: {server[0]} {server[1]}", xbmc.LOGINFO)
                xbmc.log(f"[file_iptv] Server validated and added: {server[0]} {server[1]}", xbmc.LOGERROR)
            elif result is False:
                attempted.add(key)
                xbmc.log(f"[file_iptv] Server invalid: {server[0]} {server[1]}", xbmc.LOGINFO)
                xbmc.log(f"[file_iptv] Server invalid: {server[0]} {server[1]}", xbmc.LOGERROR)
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM channels WHERE address = ? AND username = ? AND password = ?", (server[0], server[1], server[2]))
                        cur.execute("DELETE FROM servers WHERE address = ? AND username = ? AND password = ?", (server[0], server[1], server[2]))
                        conn.commit()
                    xbmc.log(f"[file_iptv] Removed invalid server from database: {server[0]}", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[file_iptv] Failed to remove invalid server: {e}", xbmc.LOGERROR)
                continue
            else:
                xbmc.log(f"[file_iptv] Server transient error: {server[0]} {server[1]}", xbmc.LOGINFO)
                xbmc.log(f"[file_iptv] Server transient error: {server[0]} {server[1]}", xbmc.LOGERROR)
                continue

        if dialog:
            dialog.update(100, "Update complete")
            dialog.close()

        summary = [
            "Update complete!",
            f"Valid servers now: {validated}",
            f"New servers added: {servers_added}",
            f"Servers removed: {servers_removed}"
        ]
        if show_summary:
            xbmcgui.Dialog().ok("IPTV Update", "\n".join(summary))

        return {
            "checked": servers_added,
            "validated": validated,
            "invalidated": len(db_servers) - validated,
        }