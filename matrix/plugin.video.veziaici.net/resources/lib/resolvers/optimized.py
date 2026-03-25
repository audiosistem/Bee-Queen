"""Optimized video URL resolvers for ok.ru and vk.com."""

import re
import json
import urllib.parse
import time
import requests
import xbmcgui
from resources.lib.utils import log, log_debug, log_error, log_warning, HEADERS

# Simple cache for resolved URLs: {url: (timestamp, stream_info)}
_RESOLVER_CACHE = {}
_CACHE_TTL = 300  # Cache URLs for 5 minutes


class StreamInfo:
    """Class to hold stream information including URL, headers, and cookies."""

    def __init__(self, url, headers=None, cookies=None, manifest_type=None):
        self.url = url
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.manifest_type = manifest_type  # 'hls', 'dash', 'mp4'

    def is_hls(self):
        return self.manifest_type == "hls" or ".m3u8" in self.url

    def is_dash(self):
        return self.manifest_type == "dash" or ".mpd" in self.url

    def is_mp4(self):
        return self.manifest_type == "mp4" or ".mp4" in self.url


def extract_ok_ru_url_optimized(url):
    """
    Optimized extractor for ok.ru videos.
    Returns StreamInfo object with proper headers and cookies.
    """
    log(f"[ok.ru] Extracting from: {url}")

    # Check cache first
    global _RESOLVER_CACHE
    now = time.time()
    cache_key = f"okru_{url}"
    if cache_key in _RESOLVER_CACHE:
        timestamp, cached = _RESOLVER_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            log("[ok.ru] Using cached result")
            return cached

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Step 1: Get the embed page with cookies
        response = session.get(url, timeout=20)
        response.raise_for_status()
        webpage = response.text

        # Check for errors
        if "vp_video_stub_txt" in webpage:
            error = re.search(r'class="vp_video_stub_txt"[^>]*>([^<]+)<', webpage)
            if error:
                log_error(f"[ok.ru] Video error: {error.group(1)}")
                return None

        # Step 2: Extract player data
        player_match = re.search(
            r'data-options=(?P<quote>["\'])(?P<player>{.+?})(?P=quote)',
            webpage,
            re.DOTALL,
        )

        if not player_match:
            log_warning("[ok.ru] No player data found")
            return None

        player_data = json.loads(player_match.group("player").replace("&quot;", '"'))
        flashvars = player_data.get("flashvars", {})

        # Step 3: Get metadata
        metadata = flashvars.get("metadata")
        if metadata and isinstance(metadata, str):
            metadata = json.loads(metadata)
        elif not metadata:
            # Fetch from metadataUrl
            metadata_url = flashvars.get("metadataUrl")
            if metadata_url:
                metadata_url = urllib.parse.unquote(metadata_url)
                data = {}
                if flashvars.get("location"):
                    data["st.location"] = flashvars["location"]

                meta_response = session.post(
                    metadata_url, data=urllib.parse.urlencode(data), timeout=15
                )
                metadata = meta_response.json()

        if not metadata or "movie" not in metadata:
            log_warning("[ok.ru] No metadata found")
            return None

        movie = metadata["movie"]

        # Debug: log available metadata keys
        log_debug(f"[ok.ru] Metadata keys: {list(metadata.keys())}")
        log_debug(
            f"[ok.ru] Movie keys: {list(movie.keys()) if isinstance(movie, dict) else 'N/A'}"
        )

        # Check if HLS is in movie object instead
        if isinstance(movie, dict):
            for field in ["hlsManifestUrl", "ondemandHls", "hls", "hlsManifest"]:
                if field in movie and movie[field]:
                    log_debug(f"[ok.ru] Found HLS in movie.{field}")

        # Handle YouTube embeds
        if metadata.get("provider") == "USER_YOUTUBE":
            youtube_url = movie.get("contentId")
            if youtube_url:
                return StreamInfo(youtube_url, manifest_type="mp4")
            return None

        # Step 4: Collect all available formats
        formats = []

        # HLS manifest - try ALL possible field names (preferred for streaming)
        hls_fields = [
            "hlsManifestUrl",
            "ondemandHls",
            "hls",
            "hlsManifest",
            "masterHls",
            "playlistHls",
        ]
        hls_url = None
        for field in hls_fields:
            if field in metadata and metadata[field]:
                hls_url = metadata[field]
                log_debug(f"[ok.ru] Found HLS in field '{field}': {hls_url[:60]}...")
                break

        if hls_url:
            formats.append(
                {
                    "url": hls_url,
                    "format_id": "hls",
                    "priority": 100,  # Highest priority
                    "manifest_type": "hls",
                }
            )

        # DASH manifest
        dash_fields = ["ondemandDash", "metadataWebmUrl", "dash", "dashManifest", "mpd"]
        dash_url = None
        for field in dash_fields:
            if field in metadata and metadata[field]:
                dash_url = metadata[field]
                log_debug(f"[ok.ru] Found DASH in field '{field}'")
                break

        if dash_url:
            formats.append(
                {
                    "url": dash_url,
                    "format_id": "dash",
                    "priority": 90,
                    "manifest_type": "dash",
                }
            )

        # Live HLS
        live_hls = metadata.get("hlsMasterPlaylistUrl") or metadata.get("liveHls")
        if live_hls:
            formats.append(
                {
                    "url": live_hls,
                    "format_id": "live-hls",
                    "priority": 95,
                    "manifest_type": "hls",
                }
            )

        # DASH manifest
        dash_url = metadata.get("ondemandDash") or metadata.get("metadataWebmUrl")
        if dash_url:
            formats.append(
                {
                    "url": dash_url,
                    "format_id": "dash",
                    "priority": 90,
                    "manifest_type": "dash",
                }
            )

        # Live HLS
        live_hls = metadata.get("hlsMasterPlaylistUrl")
        if live_hls:
            formats.append(
                {
                    "url": live_hls,
                    "format_id": "live-hls",
                    "priority": 95,
                    "manifest_type": "hls",
                }
            )

        # Direct MP4 files (fallback)
        for video in metadata.get("videos", []):
            video_url = video.get("url")
            if video_url:
                quality = video.get("name", "unknown")
                width = video.get("width", 0)
                height = video.get("height", 0)
                # Higher resolution = higher priority within MP4s
                priority = 50 + (width or height or 0) // 100
                formats.append(
                    {
                        "url": video_url,
                        "format_id": f"mp4-{quality}",
                        "priority": priority,
                        "manifest_type": "mp4",
                    }
                )

        if not formats:
            if metadata.get("paymentInfo"):
                log_warning("[ok.ru] Video requires payment")
            else:
                log_warning("[ok.ru] No formats found")
            return None

        # Sort by priority (highest first)
        formats.sort(key=lambda x: x["priority"], reverse=True)
        best_format = formats[0]

        log(f"[ok.ru] Selected format: {best_format['format_id']}")
        log_debug(f"[ok.ru] URL: {best_format['url'][:100]}...")

        # Step 5: Prepare headers and cookies for playback
        # ok.ru requires specific headers for CDN access
        stream_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": "https://ok.ru/",
            "Origin": "https://ok.ru",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
        }

        # Get cookies from session as dict
        cookies_dict = dict(session.cookies)

        result = StreamInfo(
            url=best_format["url"],
            headers=stream_headers,
            cookies=cookies_dict,
            manifest_type=best_format["manifest_type"],
        )

        # Cache the result
        _RESOLVER_CACHE[cache_key] = (now, result)

        return result

    except Exception as e:
        log_error(f"[ok.ru] Extraction error: {e}")
        import traceback

        log_debug(f"[ok.ru] Traceback: {traceback.format_exc()}")
        return None


def extract_vk_url_optimized(url):
    """
    Optimized extractor for vk.com/vkvideo.ru videos.
    Returns StreamInfo object with proper headers.
    """
    log(f"[vk.com] Extracting from: {url}")

    # Check cache first
    global _RESOLVER_CACHE
    now = time.time()
    cache_key = f"vk_{url}"
    if cache_key in _RESOLVER_CACHE:
        timestamp, cached = _RESOLVER_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            log("[vk.com] Using cached result")
            return cached

    # Extract video ID and hash
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    oid = params.get("oid", [None])[0]
    video_id = params.get("id", [None])[0]
    video_hash = params.get("hash", [None])[0]

    if not oid or not video_id:
        match = re.search(r"video(-?\d+)_(\d+)", url)
        if match:
            oid = match.group(1)
            video_id = match.group(2)

    if not oid or not video_id:
        log_warning("[vk.com] Could not extract video ID")
        return None

    video_id_full = f"{oid}_{video_id}"
    log(f"[vk.com] Video ID: {video_id_full}")
    if video_hash:
        log(f"[vk.com] Hash present: {video_hash[:10]}...")

    # Determine domain
    domain = "vk.com"
    if "vkvideo.ru" in url:
        domain = "vkvideo.ru"

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Step 1: Get main page cookies from correct domain
        session.get(f"https://{domain}/", timeout=20)

        # Step 2: Call VK API
        api_url = f"https://{domain}/al_video.php"
        api_headers = {
            **HEADERS,
            "Referer": f"https://{domain}/",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        post_data = {"act": "show", "al": "1", "video": video_id_full}
        if video_hash:
            post_data["hash"] = video_hash

        response = session.post(
            api_url, data=post_data, headers=api_headers, timeout=25
        )
        response_text = response.text

        log_debug(f"[vk.com] API response length: {len(response_text)}")

        # Step 3: Extract video URLs
        formats = []

        # Try to find HLS URL (highest priority) - expanded patterns
        hls_patterns = [
            r'"hls"\s*:\s*"([^"]+)"',
            r'"hls_ondemand"\s*:\s*"([^"]+)"',
            r'"hls_live"\s*:\s*"([^"]+)"',
            r'"hls_url"\s*:\s*"([^"]+)"',
            r'"url_hls"\s*:\s*"([^"]+)"',
            r'hls\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]

        for pattern in hls_patterns:
            match = re.search(pattern, response_text)
            if match:
                hls_url = match.group(1).replace("\\/", "/")
                log(f"[vk.com] Found HLS URL with pattern: {pattern[:30]}...")
                formats.append(
                    {
                        "url": hls_url,
                        "format_id": "hls",
                        "priority": 100,
                        "manifest_type": "hls",
                    }
                )
                break

        # Try DASH URL
        dash_patterns = [
            r'"dash"\s*:\s*"([^"]+)"',
            r'"dash_ondemand"\s*:\s*"([^"]+)"',
            r'"dash_live"\s*:\s*"([^"]+)"',
        ]

        for pattern in dash_patterns:
            match = re.search(pattern, response_text)
            if match:
                dash_url = match.group(1).replace("\\/", "/")
                formats.append(
                    {
                        "url": dash_url,
                        "format_id": "dash",
                        "priority": 90,
                        "manifest_type": "dash",
                    }
                )
                break

        # Try JSON player params (newer VK API format)
        json_match = re.search(r'\{.*"player".*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if "player" in data and "params" in data["player"]:
                    player_params = data["player"]["params"]
                    if isinstance(player_params, list) and len(player_params) > 0:
                        params = player_params[0]

                        # Check for HLS
                        for key in ["hls", "hls_ondemand", "hls_live"]:
                            if (
                                key in params
                                and params[key]
                                and not any(f["format_id"] == "hls" for f in formats)
                            ):
                                formats.append(
                                    {
                                        "url": params[key],
                                        "format_id": "hls",
                                        "priority": 100,
                                        "manifest_type": "hls",
                                    }
                                )
                                break

                        # Check for DASH
                        for key in ["dash", "dash_ondemand", "dash_live"]:
                            if (
                                key in params
                                and params[key]
                                and not any(f["format_id"] == "dash" for f in formats)
                            ):
                                formats.append(
                                    {
                                        "url": params[key],
                                        "format_id": "dash",
                                        "priority": 90,
                                        "manifest_type": "dash",
                                    }
                                )
                                break

                        # Check for direct MP4 URLs
                        for key, value in params.items():
                            if (
                                key.startswith("url")
                                and isinstance(value, str)
                                and ".mp4" in value
                            ):
                                # Extract quality from key (url240 -> 240)
                                quality_match = re.search(r"url(\d+)", key)
                                quality = (
                                    int(quality_match.group(1)) if quality_match else 0
                                )
                                formats.append(
                                    {
                                        "url": value.replace("\\/", "/"),
                                        "format_id": f"mp4-{quality}p",
                                        "priority": 50 + quality // 10,
                                        "manifest_type": "mp4",
                                    }
                                )
            except Exception as e:
                log_debug(f"[vk.com] JSON parse error: {e}")

        # Fallback 1: Try embed page directly
        if not formats and "video_ext.php" in url:
            log("[vk.com] Trying embed page directly...")
            try:
                embed_response = session.get(url, timeout=15)
                embed_page = embed_response.text

                # Look for player data in embed page
                mp4_matches = re.findall(
                    r'"url(\d+)"\s*:\s*"([^"]+\.mp4[^"]*)"', embed_page
                )
                for quality, video_url in mp4_matches:
                    video_url = video_url.replace("\\/", "/")
                    q = int(quality)
                    formats.append(
                        {
                            "url": video_url,
                            "format_id": f"mp4-{q}p",
                            "priority": 50 + q // 10,
                            "manifest_type": "mp4",
                        }
                    )

                # Look for HLS in embed page
                hls_match = re.search(
                    r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', embed_page
                )
                if hls_match and not any(f["manifest_type"] == "hls" for f in formats):
                    formats.append(
                        {
                            "url": hls_match.group(1),
                            "format_id": "hls-embed",
                            "priority": 98,
                            "manifest_type": "hls",
                        }
                    )

            except Exception as e:
                log_debug(f"[vk.com] Embed page error: {e}")

        # Fallback 2: Try main webpage
        if not formats:
            log("[vk.com] Trying main webpage fallback...")
            direct_url = f"https://{domain}/video{video_id_full}"

            try:
                page_response = session.get(direct_url, timeout=15)
                webpage = page_response.text

                # Find MP4 URLs with quality
                mp4_pattern = r'"url(\d+)"\s*:\s*"([^"]+\.mp4[^"]*)"'
                matches = re.findall(mp4_pattern, webpage)

                for quality, video_url in matches:
                    video_url = video_url.replace("\\/", "/")
                    q = int(quality)
                    formats.append(
                        {
                            "url": video_url,
                            "format_id": f"mp4-{q}p",
                            "priority": 50 + q // 10,
                            "manifest_type": "mp4",
                        }
                    )

                # Try m3u8 in webpage
                if not any(f["manifest_type"] == "hls" for f in formats):
                    m3u8_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', webpage)
                    if m3u8_match:
                        formats.append(
                            {
                                "url": m3u8_match.group(1).replace("\\/", "/"),
                                "format_id": "hls-fallback",
                                "priority": 95,
                                "manifest_type": "hls",
                            }
                        )

            except Exception as e:
                log_debug(f"[vk.com] Webpage fallback error: {e}")

        if not formats:
            log_warning("[vk.com] No formats found")
            return None

        # Sort by priority
        formats.sort(key=lambda x: x["priority"], reverse=True)
        best_format = formats[0]

        log(f"[vk.com] Selected format: {best_format['format_id']}")
        log_debug(f"[vk.com] URL: {best_format['url'][:100]}...")

        # Prepare headers for VK CDN
        stream_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": "https://vk.com/",
            "Origin": "https://vk.com",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        result = StreamInfo(
            url=best_format["url"],
            headers=stream_headers,
            cookies=dict(session.cookies),
            manifest_type=best_format["manifest_type"],
        )

        # Cache the result
        _RESOLVER_CACHE[cache_key] = (now, result)

        return result

    except Exception as e:
        log_error(f"[vk.com] Extraction error: {e}")
        import traceback

        log_debug(f"[vk.com] Traceback: {traceback.format_exc()}")
        return None


def create_listitem_with_stream(stream_info, title="Video"):
    """
    Create a properly configured xbmcgui.ListItem for the stream.
    This handles all the InputStream Adaptive configuration.
    """
    import xbmc

    list_item = xbmcgui.ListItem()
    list_item.setInfo("video", {"title": title})

    # Check if we need InputStream Adaptive
    if stream_info.is_hls() or stream_info.is_dash():
        list_item.setProperty("inputstream", "inputstream.adaptive")

        # IMPORTANT: Don't set deprecated manifest_type - let ISA auto-detect
        # This fixes "Unsupported protocol" errors

        # Build headers string properly
        headers_list = []

        # Add standard headers
        if stream_info.headers:
            for k, v in stream_info.headers.items():
                headers_list.append(f"{k}={urllib.parse.quote(v)}")

        # Add cookies if available
        if stream_info.cookies:
            cookie_string = "; ".join(
                [f"{k}={v}" for k, v in stream_info.cookies.items()]
            )
            headers_list.append(f"Cookie={urllib.parse.quote(cookie_string)}")

        # Set stream headers for segment requests
        if headers_list:
            header_string = "&".join(headers_list)
            list_item.setProperty("inputstream.adaptive.stream_headers", header_string)
            log_debug(f"[stream] Headers set: {header_string[:100]}...")

        # Set manifest headers too (needed for HLS manifest fetching)
        if headers_list:
            header_string = "&".join(headers_list)
            list_item.setProperty(
                "inputstream.adaptive.manifest_headers", header_string
            )

        # Enable automatic stream selection
        list_item.setProperty("inputstream.adaptive.stream_selection_type", "adaptive")

        # IMPORTANT: For HLS, we need to pass the URL differently
        # The URL itself might have special chars that cause "Unsupported protocol"
        # Let's clean it up if needed
        clean_url = stream_info.url
        if clean_url.startswith("https://") or clean_url.startswith("http://"):
            # URL is fine, use as-is
            pass
        else:
            # Try to fix the URL
            clean_url = urllib.parse.unquote(clean_url)

        # Set the path with proper protocol
        list_item.setPath(clean_url)
        log_debug(f"[stream] Final URL: {clean_url[:100]}...")

    else:
        # For direct MP4 files
        # Add cache-busting and better buffering
        list_item.setProperty("VideoPlayer.UseFastSeek", "true")

        if stream_info.headers:
            header_string = "|".join(
                [f"{k}={v}" for k, v in stream_info.headers.items()]
            )
            list_item.setPath(f"{stream_info.url}|{header_string}")
        else:
            list_item.setPath(stream_info.url)

    return list_item


def resolve_url_wrapper(url):
    """
    Main URL resolver wrapper that returns StreamInfo objects for optimized playback.
    Falls back to string URLs for other resolvers.
    Uses caching to avoid re-resolving the same URL.
    """
    global _RESOLVER_CACHE

    log(f"Resolving URL: {url.split('/')[2]}")

    # Check cache first
    now = time.time()
    if url in _RESOLVER_CACHE:
        timestamp, cached_result = _RESOLVER_CACHE[url]
        if now - timestamp < _CACHE_TTL:
            log(f"[resolver] Using cached result for {url.split('/')[2]}")
            return cached_result
        else:
            # Expired, remove from cache
            del _RESOLVER_CACHE[url]

    result = None

    # Check for ok.ru
    if any(domain in url for domain in ["ok.ru", "odnoklassniki.ru"]):
        result = extract_ok_ru_url_optimized(url)
        if result:
            log(f"[ok.ru] Resolved to {result.manifest_type}")
        else:
            log_warning("[ok.ru] Optimized resolver failed")

    # Check for VK
    elif any(domain in url for domain in ["vk.com", "vkvideo.ru", "vkontakte.ru"]):
        result = extract_vk_url_optimized(url)
        if result:
            log(f"[vk.com] Resolved to {result.manifest_type}")
        else:
            log_warning("[vk.com] Optimized resolver failed")

    # For other URLs, try to return a simple StreamInfo
    elif url.endswith(".m3u8"):
        result = StreamInfo(url, manifest_type="hls")
    elif url.endswith(".mpd"):
        result = StreamInfo(url, manifest_type="dash")
    elif url.endswith(".mp4"):
        result = StreamInfo(url, manifest_type="mp4")
    else:
        result = StreamInfo(url)

    # Cache the result
    if result:
        _RESOLVER_CACHE[url] = (now, result)

    return result
