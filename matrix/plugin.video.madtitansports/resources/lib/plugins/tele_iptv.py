import re, requests, sqlite3, os, json, time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
import xbmc, xbmcgui, xbmcaddon
from xbmcvfs import translatePath
from ..plugin import Plugin
from ..util.dialogs import link_dialog
from resources.lib.plugin import run_hook

# Get addon paths
addon = xbmcaddon.Addon()
USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "tele_iptv_config.json")
DB_PATH = os.path.join(USER_DATA_DIR, "tele_iptv.db")
RECENT_PATH = os.path.join(USER_DATA_DIR, "tele_iptv_recent.json")

# Ensure user data directory exists
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

# Basic HTTP headers to improve compatibility with some panels
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
        "Gecko/20100101 Firefox/117.0"
    ),
}

# Load config with default values
DEFAULT_CONFIG = {
    "tg_message": "https://t.me/YourChannel/1?embed=1",
    "exclude_groups": ["xxx", "adult", "18+"],
    "total_result_limit": 20,
    "per_address_limit": 5,
    "num_posts": 25,
    # Exclude channels whose NAME contains any of these strings (case-insensitive)
    "exclude_names": [
        "BR:",
        "ARG:",
        "MEX:"
    ],
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
    # Enable extra debug logging for searches, etc.
    "debug_logging": False,
}

try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        # Merge with defaults
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
except:
    config = DEFAULT_CONFIG.copy()
    # Save default config
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
    except:
        pass

URL_PATTERN = re.compile(r'https?://\S+')
MAC_PATTERN = re.compile(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})')
EMOJI_PATTERN = re.compile(r"[👤👩]\s+(.+?)\s*[🔐🔑]\s*(.+)")


def load_recent_searches(max_items: int = 20):
    """Load recent TELE search history from JSON file."""
    if not os.path.exists(RECENT_PATH):
        return []
    try:
        with open(RECENT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[:max_items]
    except Exception as e:
        xbmc.log(f"[tele_iptv] Failed to load recent searches: {e}", xbmc.LOGERROR)
    return []


def save_recent_search(term, country):
    """Append a TELE search to history, de-duplicating on (term,country)."""
    entry = {
        "term": term,
        "country": country or "",
        "time": int(time.time()),
    }
    history = load_recent_searches(max_items=50)
    history = [
        h
        for h in history
        if not (h.get("term") == entry["term"] and h.get("country", "") == entry["country"])
    ]
    history.insert(0, entry)
    if len(history) > 50:
        history = history[:50]
    try:
        with open(RECENT_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        xbmc.log(f"[tele_iptv] Failed to save recent searches: {e}", xbmc.LOGERROR)

def init_db():
    """Initialize the database"""
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
                PRIMARY KEY (address, username, password, stream_id),
                FOREIGN KEY (address, username, password) 
                    REFERENCES servers(address, username, password)
            )
        """)
        conn.commit()

def clean_string(s):
    """Clean string for searching"""
    s = s.strip()
    # Remove leading country/region codes like "US - ", "UK: ", but
    # do NOT strip normal words like "FOX " or "TNT ". Require a separator.
    s = re.sub(r'^[A-Z]{2,3}[-:]\s+', '', s, flags=re.IGNORECASE)
    # Remove quality indicators
    s = re.sub(r'\|\s?[A-Z]{2,3}\s?(8K|4K|UHD|FHD|HD|SD|HDR)$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\|\s?(8K|4K|UHD|FHD|HD|SD|HDR)\s?[A-Z]{2,3}$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\|\s?[A-Z]{2,3}$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(8k|4k|uhd|fhd|hd|sd|hdr)\b', '', s, flags=re.IGNORECASE)
    s = s.lower()
    s = s.replace('bally', 'fanduel').replace('network', '')
    # Remove everything before |, -, :, ] followed by space
    s = re.sub(r".*[|\-:\]]\s+(.*)", r"\1", s)
    # Remove parentheses and brackets content at start/end
    s = re.sub(r'^\(.*?\)', '', s)
    s = re.sub(r'\(.*?\)$', '', s)
    s = re.sub(r'\[.*?\]$', '', s)
    # Keep only alphanumeric
    s = re.sub(r"[^a-z0-9]", "", s)
    return s.strip()

def extract_credentials(text):
    """Extract IPTV credentials from Telegram post text"""
    address = ""
    username = []
    password = []
    
    for line in text.splitlines():
        if "https://t.me/" in line or "https://kodi.tv/" in line:
            continue
        if "http" in line:
            match = URL_PATTERN.search(line)
            if match:
                parsed = urlparse(match.group())
                address = f"{parsed.scheme}://{parsed.netloc}"
                query = parse_qs(parsed.query)
                un = query.get("username", "")
                pw = query.get("password", "")
                if un and pw:
                    username.append(un[0])
                    password.append(pw[0])
            continue
        
        emoji_match = EMOJI_PATTERN.findall(line)
        if emoji_match:
            username.append(emoji_match[0][0].strip())
            password.append(emoji_match[0][1].strip())
            continue
        
        line = line.strip()
        lower_line = line.lower()
        
        if "user" in lower_line:
            longest_word = max(line.split(), key=len).replace('username=', '')
            username.append(longest_word)
        elif "pass" in lower_line:
            longest_word = max(line.split(), key=len).replace('password=', '')
            password.append(longest_word)
        elif not username and not password:
            username.append(line)
        elif not password and len(username) == 1:
            password.append(line)
    
    if not address or not username:
        return None
    
    credentials = [
        (address, u, p)
        for u, p in zip(reversed(username), reversed(password))
    ]
    return credentials

def process_telegram_post(url):
    """Process a single Telegram post"""
    try:
        headers = {
            'user-agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/77.0.3865.90 Safari/537.36 TelegramBot (like TwitterBot)'
            )
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if config.get("debug_logging"):
            xbmc.log(f"[tele_iptv] [DEBUG] HTTP status for {url}: {resp.status_code}", xbmc.LOGINFO)
        if 'Please open Telegram to view this post' in resp.text:
            if config.get("debug_logging"):
                xbmc.log(f"[tele_iptv] [DEBUG] Telegram post requires Telegram app: {url}", xbmc.LOGINFO)
            return None
        elif 'tgme_widget_message_error' in resp.text:
            if config.get("debug_logging"):
                xbmc.log(f"[tele_iptv] [DEBUG] Telegram widget error in post: {url}", xbmc.LOGINFO)
            return False
        soup = BeautifulSoup(resp.text, 'html.parser')
        div = soup.find('div', {'class': 'tgme_widget_message_text js-message_text', 'dir': 'auto'})
        if not div:
            if config.get("debug_logging"):
                xbmc.log(f"[tele_iptv] [DEBUG] No message text found in post: {url}", xbmc.LOGINFO)
            return None
        text = div.get_text(separator='\n')
        if config.get("debug_logging"):
            xbmc.log(f"[tele_iptv] [DEBUG] Extracted text from post: {text}", xbmc.LOGINFO)
        return extract_credentials(text) if text else None
    except Exception as e:
        xbmc.log(f"[tele_iptv] Error processing post {url}: {str(e)}", xbmc.LOGERROR)
        if config.get("debug_logging"):
            xbmc.log(f"[tele_iptv] [DEBUG] Exception in process_telegram_post: {str(e)}", xbmc.LOGERROR)
        return None

def scrape_telegram_messages():
    """Scrape Telegram messages for IPTV credentials"""
    if config.get("debug_logging"):
        xbmc.log("[tele_iptv] [DEBUG] Starting Telegram scrape", xbmc.LOGINFO)
    servers = []
    num_posts = config.get("num_posts", 25)
    url = config["tg_message"]
    
    try:
        post_id = int(re.search(r"t\.me\/.+\/(\d+)", url)[1])
    except:
        xbmc.log("[tele_iptv] Invalid Telegram URL in config", xbmc.LOGERROR)
        return []
    
    # Extract base URL pattern - replace only the message ID in the path
    url_base = re.sub(r"(t\.me\/.+\/)(\d+)", r"\1{}", url)
    last_post = post_id
    
    urls = [url_base.format(pid) for pid in range(post_id, post_id + num_posts)]
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_index = {executor.submit(process_telegram_post, link): i for i, link in enumerate(urls)}
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                cred = future.result()
                if config.get("debug_logging"):
                    xbmc.log(f"[tele_iptv] [DEBUG] Telegram post {urls[index]} result: {cred}", xbmc.LOGINFO)
                if cred is not False:
                    last_post = max(last_post, post_id + index)
                if cred:
                    servers.extend(cred)
            except Exception as e:
                if config.get("debug_logging"):
                    xbmc.log(f"[tele_iptv] [DEBUG] Exception in Telegram scrape: {str(e)}", xbmc.LOGERROR)
                pass
    
    # Update config with last post
    config["tg_message"] = url_base.format(last_post + 1)  # Fixed: Use 'url_base' instead of 'url_fmt'
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
    except:
        pass
    
    xbmc.log(f"[tele_iptv] Found {len(servers)} servers from Telegram", xbmc.LOGINFO)
    if not servers:
        # Gather HTTP status codes for debug
        status_debug = []
        for url in urls:
            try:
                resp = requests.get(url, headers={
                    'user-agent': (
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/77.0.3865.90 Safari/537.36 TelegramBot (like TwitterBot)'
                    )
                }, timeout=5)
                status_debug.append(f"{url[-8:]}: {resp.status_code}")
            except Exception as e:
                status_debug.append(f"{url[-8:]}: ERR {str(e)[:30]}")
        msg = "No servers found. Could not connect or parse any Telegram posts.\n" + ", ".join(status_debug[:5])
        xbmcgui.Dialog().ok("Telegram Scrape Failed", msg)
    return servers
# Helper: preferred channel check
def is_preferred_channel(channel):
    """Return True if channel name matches preferred test keywords."""
    name = (channel.get("name") or "").lower()
    keywords = config.get("test_channel_keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    return any(k in name for k in keywords)

def validate_server(server):
    """Validate an IPTV server and get its channels"""
    address, username, password = server
    try:
        params = {"username": username, "password": password}
        
        # Check user info
        user_data = requests.get(
            f"{address}/player_api.php",
            timeout=5,
            params=params,
            headers=HTTP_HEADERS,
        ).json()
        
        max_conn = user_data.get('user_info', {}).get('max_connections', 0)
        if int(max_conn) < 1:
            xbmc.log(f"[tele_iptv] Server failed: Max connections = {max_conn}", xbmc.LOGINFO)
            return None
        
        status = user_data.get('user_info', {}).get('status', '')
        if status != "Active":
            xbmc.log(f"[tele_iptv] Server failed: Status = {status}", xbmc.LOGINFO)
            return None
        
        # Get panel data
        panel_data = requests.get(
            f"{address}/panel_api.php",
            timeout=15,
            params=params,
            headers=HTTP_HEADERS,
        ).json()
        
        if "available_channels" not in panel_data:
            xbmc.log(f"[tele_iptv] Server failed: No available_channels", xbmc.LOGINFO)
            return None

        # Optional stream reachability check, controlled by config.
        if config.get("stream_check_enabled", True):
            channels = list(panel_data.get("available_channels", {}).values())
            if not channels:
                xbmc.log(f"[tele_iptv] Server failed: available_channels is empty", xbmc.LOGINFO)
                return None
            # ...existing code for stream check and validation...
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
                            # stream is at least reachable.
                            try:
                                next(resp.iter_content(chunk_size=2048))
                            except StopIteration:
                                pass
                            stream_ok = True
                            break
                    except Exception as e:
                        xbmc.log(f"[tele_iptv] Test stream failed {test_url}: {e}", xbmc.LOGDEBUG)
                if stream_ok:
                    break

            if not stream_ok:
                xbmc.log(
                    f"[tele_iptv] Server failed: no test channel playable via HTTP",
                    xbmc.LOGINFO,
                )
                return None
        
        xbmc.log(f"[tele_iptv] Server validated: {address}", xbmc.LOGINFO)
        return panel_data
        
    except Exception as e:
        xbmc.log(f"[tele_iptv] Server validation error {address}: {str(e)}", xbmc.LOGERROR)
        return None

def store_server_channels(server, panel_data):
    """Store server and its channels in database"""
    address, username, password = server
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Mark server as valid
            conn.execute("""
                INSERT OR REPLACE INTO servers (address, username, password, last_checked, is_valid)
                VALUES (?, ?, ?, ?, 1)
            """, (address, username, password, int(time.time())))
            
            # Store channels
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
        
        xbmc.log(f"[tele_iptv] Stored channels for: {address}", xbmc.LOGINFO)
        return True
        
    except Exception as e:
        xbmc.log(f"[tele_iptv] Failed to store {address}: {str(e)}", xbmc.LOGERROR)
        return False

def search_channels(term, limit=20, per_address=5, country_filter=None):
    """Search for channels in the database"""
    cleaned = clean_string(term)
    # Log the raw and cleaned search terms for debugging (optional)
    if config.get("debug_logging", False):
        xbmc.log(f"[tele_iptv] search term='{term}' cleaned='{cleaned}'", xbmc.LOGINFO)
    like_pattern = f"%{cleaned}%"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT c.address, c.username, c.password, c.stream_id, c.name, c.search
            FROM channels c
            JOIN servers s ON c.address = s.address 
                          AND c.username = s.username 
                          AND c.password = s.password
            WHERE s.is_valid = 1 AND c.search LIKE ?
            ORDER BY LENGTH(c.search) - LENGTH(?)
        """, (like_pattern, cleaned))

        rows = cur.fetchall()

    if config.get("debug_logging", False):
        xbmc.log(f"[tele_iptv] total DB matches before filter: {len(rows)}", xbmc.LOGINFO)

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
                    f"[tele_iptv] matches after country filter '{cf}': {len(rows)}",
                    xbmc.LOGINFO,
                )

    # Check if query ends with digit
    is_digit = cleaned[-1].isdigit() if cleaned else False

    # Filter rows by digit rule
    filtered = [
        r for r in rows
        if is_digit or not re.match(re.escape(cleaned) + r"\d", r["search"], re.IGNORECASE)
    ]

    if config.get("debug_logging", False):
        xbmc.log(f"[tele_iptv] matches after digit-filter: {len(filtered)}", xbmc.LOGINFO)

    # Limit per address
    results = []
    counts = {}
    for r in filtered:
        addr = r['address']
        counts.setdefault(addr, 0)
        if counts[addr] >= per_address:
            continue
        counts[addr] += 1

        # Base stream WITHOUT Kodi header suffix to keep plugin route clean
        base_stream = f"{r['address']}/live/{r['username']}/{r['password']}/{r['stream_id']}.m3u8"
        jetproxy_stream = f"jetproxy://{base_stream}"
        encoded_stream = quote_plus(jetproxy_stream)

        # sportjetextractors plugin route
        plugin_url = (
            "plugin://plugin.video.madtitansports/"
            f"sportjetextractors/play?urls={encoded_stream}"
        )

        results.append({
            "name": f"{r['name']} [{addr}]",
            "address": plugin_url
        })

        if len(results) >= limit:
            break

    return results

class TeleIPTV(Plugin):
    name = "tele_iptv"
    priority = 100
    
    def __init__(self):
        init_db()
    
    def process_item(self, item):
        if self.name in item or "iptv_s" in item:
            query = item.get(self.name) or item.get("iptv_s", "")
            country = item.get("country")

            # Special value to open the Recent TELE searches dialog
            if query == "recent":
                item["link"] = f"{self.name}/recent"
                item["is_dir"] = False
                item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
                return item

            # If configured with "iptv_s": "*" and country "*", prompt
            # for both channel and country (like file_iptv).
            if query == "*" and item.get("country") == "*":
                item["link"] = f"{self.name}/search_prompt_country"
            elif query == "*":
                # Channel-only prompt
                item["link"] = f"{self.name}/search_prompt"
            elif country and country != "*":
                # Fixed term with a specific country: encode both so the
                # search route can apply a country_filter.
                combined = f"{country}:::{query}"
                item["link"] = f"{self.name}/search/{combined}"
            else:
                item["link"] = f"{self.name}/search/{query}"

            item["is_dir"] = False
            item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
            return item
        
        # # Optional minimal add: Handle HTTP as playable (prevents "skipping unplayable" on click)
        # link = item.get("link", "")
        # normalized_link = link.lstrip("/")  # allow links like "/https://..."
        # if normalized_link.startswith(("http://", "https://", "message/")):
        #     item["link"] = normalized_link
        #     item["is_dir"] = False
        #     item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
        #     item["list_item"].setProperty('IsPlayable', 'true')
        #     return item
        
        # # Fallback (ensures list_item for folders)
        # item["is_dir"] = True
        # if "list_item" not in item:
        #     item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
        # return item
    
    def routes(self, plugin):
        @plugin.route(f"/{self.name}/recent")
        def recent():
            """Show recent TELE searches in a dialog and re-run selection."""
            history = load_recent_searches()
            if not history:
                xbmcgui.Dialog().ok("Recent TELE IPTV", "No recent searches yet.")
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
            search(combined)

        @plugin.route(f"/{self.name}/search_prompt_country")
        def search_prompt_country():
            """Prompt for channel, then optional country, then call main search."""
            dlg = xbmcgui.Dialog()
            # Ask for channel/search term first
            term = dlg.input("IPTV Search (TELE)", type=xbmcgui.INPUT_ALPHANUM)
            if not term:
                return

            # Then ask for country filter (can be left blank)
            country = dlg.input("Country filter (e.g. US, USA)", type=xbmcgui.INPUT_ALPHANUM)
            if not country:
                country = ""

            combined = f"{country}:::{term}"
            plugin.redirect(f"/{self.name}/search/{combined}")

        @plugin.route(f"/{self.name}/search_prompt")
        def search_prompt():
            """Prompt only for channel, then call main search."""
            dlg = xbmcgui.Dialog()
            term = dlg.input("IPTV Search (TELE)", type=xbmcgui.INPUT_ALPHANUM)
            if not term:
                return

            plugin.redirect(f"/{self.name}/search/{term}")

        @plugin.route(f"/{self.name}/search/<query>")  # Added leading /
        def search(query):
            # Decode optional country filter if present
            country_filter = None
            term = query
            if ":::" in query:
                country_filter, term = query.split(":::", 1)

            # Check if we have any servers in DB
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM servers WHERE is_valid = 1")
                server_count = cur.fetchone()[0]
            
            # If no servers, try to update
            if server_count == 0:
                dialog = xbmcgui.Dialog()
                if dialog.yesno("IPTV Search", "No servers in database. Update from Telegram?"):
                    self.update_servers()
            
            # Search for channels
            results = search_channels(
                term, 
                limit=config.get("total_result_limit", 20),
                per_address=config.get("per_address_limit", 5),
                country_filter=country_filter,
            )
            
            if not results:
                xbmcgui.Dialog().ok("IPTV Search", f"No channels found matching '{query}'")
                return

            # Save to recent history (term + optional country)
            save_recent_search(term, country_filter)
            
            # Show selection dialog
            idx = link_dialog([r["name"] for r in results], return_idx=True, hide_links=False)
            if idx is None:
                return
            
            # Play selected stream
            stream_url = results[idx]["address"]
            liz = xbmcgui.ListItem(results[idx]["name"])
            liz.setProperty('IsPlayable', 'true')
            xbmc.Player().play(stream_url, liz)
        
        @plugin.route(f"/{self.name}/update")  # Added leading /
        def update():
            self.update_servers()
            xbmcgui.Dialog().ok("IPTV Update", "Server update complete")
            
        @plugin.route(f"/{self.name}/reset")  # Added leading /
        def reset():
            """Reset the database and config to start fresh"""
            dialog = xbmcgui.Dialog()
            if not dialog.yesno("IPTV Reset", "Delete the database and start fresh? This will remove all servers/channels."):
                return
            
            try:
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                    xbmc.log(f"[tele_iptv] Deleted database: {DB_PATH}", xbmc.LOGINFO)
                
                dialog.ok("IPTV Reset", "Database cleared! Run update to rebuild.")
            except Exception as e:
                xbmc.log(f"[tele_iptv] Reset error: {str(e)}", xbmc.LOGERROR)
                dialog.ok("IPTV Reset", f"Error: {str(e)}")
        
        @plugin.route(f"/{self.name}/manage_servers")
        def manage_servers():
            """List and delete specific servers from the DB"""
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.address, s.username, s.password, s.last_checked
                    FROM servers s
                    JOIN channels c ON c.address = s.address
                                    AND c.username = s.username
                                    AND c.password = s.password
                    WHERE s.is_valid = 1
                    GROUP BY s.address, s.username, s.password, s.last_checked
                    ORDER BY s.last_checked DESC
                    LIMIT 200
                """)
                servers = cur.fetchall()
            
            if not servers:
                xbmcgui.Dialog().ok("Manage Servers", "No servers with channels in database.")
                return
            
            # Format list for dialog: "address (username) - last_checked"
            server_list = []
            for row in servers:
                ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(row['last_checked'])) if row['last_checked'] else 'Never'
                server_list.append(f"{row['address']} ({row['username'][:8]}...) - {ts}")
            
            # Use link_dialog for selection (no heading=)
            while True:
                idx = link_dialog(server_list, return_idx=True, hide_links=False)
                if idx is None:
                    break  # User canceled
            
                selected_server = servers[idx]
                addr = selected_server['address']
                user = selected_server['username']
                pw = selected_server['password']
            
                # Confirmation
                confirm_msg = f"Delete server:\n{addr}\n({user})?\nThis removes all its channels too."
                if not xbmcgui.Dialog().yesno("Delete Server", confirm_msg):
                    continue
            
                # Delete from channels first, then servers
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
                    
                    xbmc.log(f"[tele_iptv] Deleted server: {addr}", xbmc.LOGINFO)
                    del server_list[idx]
                    del servers[idx]
                    xbmcgui.Dialog().ok("Delete Server", f"Deleted {addr} and its channels.")
                    
                    if not server_list:
                        break
                except Exception as e:
                    xbmc.log(f"[tele_iptv] Delete error {addr}: {str(e)}", xbmc.LOGERROR)
                    xbmcgui.Dialog().ok("Delete Server", f"Error: {str(e)}")
            
            xbmcgui.Dialog().ok("Manage Servers", "Done managing servers.")

        @plugin.route(f"/{self.name}/settings")
        def settings():
            """Simple UI to tweak TELE IPTV settings."""
            dlg = xbmcgui.Dialog()

            while True:
                total_limit = config.get("total_result_limit", 20)
                per_addr = config.get("per_address_limit", 5)
                tg_url = config.get("tg_message", "")
                num_posts = config.get("num_posts", 25)
                stream_check_enabled = bool(config.get("stream_check_enabled", True))
                stream_candidates = config.get("stream_check_candidates", 5)
                tk = config.get("test_channel_keywords", [])
                if isinstance(tk, str):
                    keywords_str = tk
                elif isinstance(tk, list):
                    keywords_str = ", ".join(str(x) for x in tk)
                else:
                    keywords_str = ""

                choices = [
                    f"Total results per search: [B]{total_limit}[/B]",
                    f"Per-server result cap: [B]{per_addr}[/B]",
                    f"Telegram start message URL: [COLORgrey]{tg_url}[/COLOR]",
                    f"Telegram posts to scan: [B]{num_posts}[/B]",
                    f"Stream check: [B]{'Enabled' if stream_check_enabled else 'Disabled'}[/B]",
                    f"Stream check candidates: [B]{stream_candidates}[/B] channels/server",
                    f"Preferred test channel names: [COLORgrey]{keywords_str}[/COLOR]",
                    f"Debug logging: [B]{'On' if bool(config.get('debug_logging', False)) else 'Off'}[/B]",
                    "Update TELE IPTV servers now",
                    "Manage TELE IPTV servers",
                    "Reset TELE IPTV database",
                    "Clear recent searches",
                    "Close",
                ]

                idx = dlg.select("TELE IPTV Settings", choices)
                if idx in (-1, len(choices) - 1):
                    break

                # Total results per search
                if idx == 0:
                    val = dlg.input(
                        "Total results per search",
                        defaultt=str(total_limit),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["total_result_limit"] = int(val)
                        with open(CONFIG_PATH, 'w') as f:
                            json.dump(config, f, indent=4)

                # Per-server result cap
                elif idx == 1:
                    val = dlg.input(
                        "Per-server result cap",
                        defaultt=str(per_addr),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["per_address_limit"] = int(val)
                        with open(CONFIG_PATH, 'w') as f:
                            json.dump(config, f, indent=4)

                # Telegram start message URL
                elif idx == 2:
                    val = dlg.input(
                        "Telegram start message URL",
                        defaultt=tg_url,
                        type=xbmcgui.INPUT_ALPHANUM,
                    )
                    if val:
                        config["tg_message"] = val.strip()
                        with open(CONFIG_PATH, 'w') as f:
                            json.dump(config, f, indent=4)

                # Telegram posts to scan
                elif idx == 3:
                    val = dlg.input(
                        "Telegram posts to scan",
                        defaultt=str(num_posts),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["num_posts"] = int(val)
                        with open(CONFIG_PATH, 'w') as f:
                            json.dump(config, f, indent=4)

                # Toggle stream check on/off
                elif idx == 4:
                    config["stream_check_enabled"] = not stream_check_enabled
                    with open(CONFIG_PATH, 'w') as f:
                        json.dump(config, f, indent=4)

                # Number of candidate channels to test per server
                elif idx == 5:
                    val = dlg.input(
                        "Stream check candidates per server",
                        defaultt=str(stream_candidates),
                        type=xbmcgui.INPUT_NUMERIC,
                    )
                    if val and val.isdigit() and int(val) > 0:
                        config["stream_check_candidates"] = int(val)
                        with open(CONFIG_PATH, 'w') as f:
                            json.dump(config, f, indent=4)

                # Preferred test channel keywords
                elif idx == 6:
                    val = dlg.input(
                        "Preferred test channel names (comma-separated)",
                        defaultt=keywords_str,
                        type=xbmcgui.INPUT_ALPHANUM,
                    )
                    if val:
                        parts = [p.strip() for p in val.split(",") if p.strip()]
                        if parts:
                            config["test_channel_keywords"] = parts
                            with open(CONFIG_PATH, 'w') as f:
                                json.dump(config, f, indent=4)

                # Toggle debug logging
                elif idx == 7:
                    config["debug_logging"] = not bool(config.get("debug_logging", False))
                    with open(CONFIG_PATH, 'w') as f:
                        json.dump(config, f, indent=4)

                # Update servers now
                elif idx == 8:
                    update()

                # Manage servers
                elif idx == 9:
                    manage_servers()

                # Reset database
                elif idx == 10:
                    reset()

                # Clear recent search history
                elif idx == 11:
                    if dlg.yesno("Recent TELE IPTV", "Clear recent search history?"):
                        try:
                            if os.path.exists(RECENT_PATH):
                                os.remove(RECENT_PATH)
                            dlg.ok("Recent TELE IPTV", "Recent searches cleared.")
                        except Exception as e:
                            xbmc.log(f"[tele_iptv] Failed to clear recent: {e}", xbmc.LOGERROR)
                            dlg.ok("Recent TELE IPTV", f"Error clearing history: {e}")
    
    def update_servers(self):
        """Update servers from Telegram"""
        dialog = xbmcgui.DialogProgress()
        dialog.create("IPTV Update", "Scraping Telegram messages...")
        
        # Scrape Telegram
        servers = scrape_telegram_messages()

        # Always proceed to validation, even if no new servers were found
        dialog.update(30, "Validating servers...")

        # Add new servers to DB if any
        if servers:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT address, username, password FROM servers")
                existing = set(cur.fetchall())
                for server in servers:
                    if server not in existing:
                        conn.execute("""
                            INSERT OR IGNORE INTO servers (address, username, password, last_checked, is_valid)
                            VALUES (?, ?, ?, 0, 0)
                        """, server)
                conn.commit()

        # Get unvalidated or stale servers
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT address, username, password 
                FROM servers 
                WHERE is_valid = 0 OR last_checked < ?
                ORDER BY last_checked ASC
                LIMIT 200
            """, (int(time.time()) - 86400,))  # Re-check servers older than 1 day
            to_validate = cur.fetchall()

        if not to_validate:
            dialog.update(100, "No servers to validate.")
            dialog.close()
            xbmcgui.Dialog().ok("IPTV Update", "No new or stale servers to validate.")
            return
        
        total_to_validate = len(to_validate)
        dialog.update(50, f"Validating {total_to_validate} servers...")

        validated = 0
        invalidated = 0
        
        # Validate servers
        validated = 0
        for i, server in enumerate(to_validate):
            if dialog.iscanceled():
                break
            
            dialog.update(50 + int(40 * i / len(to_validate)), 
                        f"Validating server {i+1}/{len(to_validate)}...")
            
            panel_data = validate_server(server)
            if panel_data:
                store_server_channels(server, panel_data)
                validated += 1
            else:
                # FIX: Mark as checked but invalid to avoid re-validation soon
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        UPDATE servers 
                        SET last_checked = ? 
                        WHERE address = ? AND username = ? AND password = ?
                    """, (int(time.time()), *server))
                conn.commit()
                xbmc.log(f"[tele_iptv] Marked invalid: {server[0]}", xbmc.LOGINFO)
        
        dialog.update(100, "Update complete")
        dialog.close()
        summary = [
            "Update complete!",
            f"Checked: {total_to_validate}",
            f"Valid: {validated}",
            f"Invalid/removed: {invalidated}",
        ]
        
        xbmcgui.Dialog().ok("IPTV Update", "\n".join(summary))