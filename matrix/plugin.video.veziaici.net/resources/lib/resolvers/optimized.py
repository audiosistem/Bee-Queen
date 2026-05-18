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


def extract_vidmoly_url(url):
    """
    Optimized extractor for vidmoly.net/vidmoly.me videos.
    Extracts the direct m3u8 stream URL from the embed page.
    """
    try:
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}/"
        
        headers = {
            'Referer': domain,
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            log_warning(f"[vidmoly] HTTP {response.status_code}")
            return None
        
        html = response.text
        
        # Extract video URL from: file: 'https://...m3u8...'
        match = re.search(r"file:\s*['\"]([^'\"]+)['\"]", html)
        if not match:
            log_warning("[vidmoly] Could not find file: pattern in page")
            return None
        
        video_url = match.group(1)
        log(f"[vidmoly] Extracted: {video_url[:100]}")
        
        # Build the stream URL with required headers
        stream_headers = f"Referer={domain}&User-Agent={headers['User-Agent']}"
        full_url = f"{video_url}|{stream_headers}"
        
        # Determine manifest type
        if '.m3u8' in video_url:
            return StreamInfo(full_url, manifest_type="hls")
        elif '.mp4' in video_url:
            return StreamInfo(full_url, manifest_type="mp4")
        else:
            return StreamInfo(full_url, manifest_type="hls")
    
    except Exception as e:
        log_warning(f"[vidmoly] Error: {e}")
        return None


def extract_filemoon_url(url):
    """
    Optimized extractor for Filemoon-based hosts (filemoon.sx, byselapuix.com, etc).
    Uses API + AES-GCM decryption to extract the stream URL.
    Credits: https://github.com/Gujal00/ResolveURL
    """
    try:
        import json
        import base64
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        headers = {
            'Accept': '*/*',
            'Referer': domain,
            'X-Embed-Parent': url,
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Mobile Safari/537.36',
        }
        
        def b64_url_decode(v):
            v = v.replace('-', '+').replace('_', '/')
            return base64.b64decode(v + '=' * (-len(v) % 4))
        
        # Extract video code from URL
        code_match = re.search(r'/e/([^/]+)', url)
        if not code_match:
            # Try alternate pattern
            code_match = re.search(r'/([a-z0-9]{12})', url)
        if not code_match:
            log_warning("[filemoon] Could not extract video code from URL")
            return None
        
        code = code_match.group(1)
        log(f"[filemoon] Video code: {code}")
        
        # Step 1: Get embed details to find the actual domain
        try:
            details_resp = requests.get(
                f'{domain}/api/videos/{code}/embed/details',
                headers=headers, timeout=15
            ).json()
            
            embed_url = details_resp.get('embed_frame_url', '')
            if embed_url:
                embed_parsed = urlparse(embed_url)
                domain = f'https://{embed_parsed.netloc}'
                log(f"[filemoon] Embed domain: {domain}")
        except Exception as e:
            log(f"[filemoon] Details API failed ({e}), using original domain")
        
        # Step 2: Get encrypted playback data
        playback_resp = requests.get(
            f'{domain}/api/videos/{code}/embed/playback',
            headers=headers, timeout=15
        ).json()
        
        encryption_info = playback_resp.get('playback')
        if not encryption_info:
            log_warning("[filemoon] No playback data in response")
            return None
        
        ciphertext_b64 = encryption_info.get('payload')
        key_parts = encryption_info.get('key_parts')
        iv_b64 = encryption_info.get('iv')
        
        if not all([ciphertext_b64, key_parts, iv_b64]):
            log_warning("[filemoon] Missing encryption parameters")
            return None
        
        # Step 3: Decrypt with AES-GCM
        try:
            from Crypto.Cipher import AES
        except ImportError:
            try:
                from Cryptodome.Cipher import AES
            except ImportError:
                log_warning("[filemoon] PyCryptodome not available, cannot decrypt")
                return None
        
        ciphertext = b64_url_decode(ciphertext_b64)
        key = b''.join(b64_url_decode(p) for p in key_parts)
        iv = b64_url_decode(iv_b64)
        
        # Split ciphertext and auth tag (last 16 bytes)
        ciphertext_data = ciphertext[:-16]
        tag = ciphertext[-16:]
        
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt_and_verify(ciphertext_data, tag)
        
        # Step 4: Parse decrypted JSON to get sources
        streaming_info = json.loads(plaintext)
        sources = streaming_info.get('sources', [])
        
        if not sources:
            log_warning("[filemoon] No sources in decrypted data")
            return None
        
        video_url = sources[0].get('url', '')
        if not video_url:
            log_warning("[filemoon] Empty URL in sources")
            return None
        
        log(f"[filemoon] Decrypted stream: {video_url[:100]}")
        
        # Build stream with headers
        stream_headers = f"Referer={domain}/&User-Agent={headers['User-Agent']}"
        full_url = f"{video_url}|{stream_headers}"
        
        if '.m3u8' in video_url:
            return StreamInfo(full_url, manifest_type="hls")
        elif '.mp4' in video_url:
            return StreamInfo(full_url, manifest_type="mp4")
        else:
            return StreamInfo(full_url, manifest_type="hls")
    
    except Exception as e:
        log_warning(f"[filemoon] Error: {e}")
        return None


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
    Based on Streamlink's VK plugin - handles WAF cookie protection.
    Returns StreamInfo object with proper headers.
    """
    log(f"[vk.com] Extracting from: {url}")
    from hashlib import md5
    from urllib.parse import urlparse, parse_qs, urlencode

    # Extract video ID
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    oid = params.get("oid", [None])[0]
    video_id = params.get("id", [None])[0]

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

    # Determine host
    host = "vk.com"
    if "vkvideo.ru" in url:
        host = "vkvideo.ru"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        # Step 1: Get WAF cookie (Streamlink approach)
        base_url = f"https://{host}/"
        log(f"[vk.com] Getting WAF cookie from {base_url}")

        resp = session.get(base_url, timeout=15, allow_redirects=False)

        # Handle WAF redirect if present
        if resp.headers.get("x-waf-redirect") == "1":
            hash_cookie = resp.cookies.get("hash429", "")
            if hash_cookie:
                key = md5(hash_cookie.encode("utf-8")).hexdigest()
                redirect_url = resp.headers.get("Location", "")
                if redirect_url:
                    separator = "&" if "?" in redirect_url else "?"
                    redirect_url = f"{redirect_url}{separator}key={key}"
                    log(f"[vk.com] Following WAF redirect with key")
                    session.get(redirect_url, timeout=15)
        elif resp.status_code in (301, 302):
            session.get(resp.headers.get("Location", base_url), timeout=15)

        # Step 2: POST to al_video.php (same as Streamlink)
        api_url = f"https://{host}/al_video.php?act=show"
        post_headers = {
            "Referer": f"https://{host}/",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        post_data = {
            "act": "show",
            "al": "1",
            "video": video_id_full,
        }

        log(f"[vk.com] Calling API: {api_url}")
        response = session.post(api_url, data=post_data, headers=post_headers, timeout=20)
        response_text = response.text

        # Step 3: Parse response (Streamlink payload format)
        if response_text.startswith("<!--"):
            response_text = response_text[4:]

        try:
            js_data = json.loads(response_text)
        except json.JSONDecodeError:
            log_warning("[vk.com] Invalid JSON response")
            return None

        # Navigate payload structure: payload[-1][-1] -> player.params[0]
        payload = js_data.get("payload", [])
        player_params = None

        # Try Streamlink's approach: payload[-1][-1]
        try:
            last_payload = payload[-1]
            if isinstance(last_payload, list):
                last_item = last_payload[-1]
                if isinstance(last_item, dict):
                    player_params = last_item.get("player", {}).get("params", [None])[0]
                elif isinstance(last_item, str):
                    log_warning("[vk.com] Video is inaccessible (string response)")
                    return None
        except (IndexError, TypeError):
            pass

        # Fallback: search through all payload items
        if not player_params:
            for item in payload:
                if isinstance(item, list):
                    for sub_item in item:
                        if isinstance(sub_item, dict) and "player" in sub_item:
                            player_params = sub_item.get("player", {}).get("params", [None])[0]
                            if player_params:
                                break
                    if player_params:
                        break

        if not player_params:
            log_warning("[vk.com] Could not find player params in payload")
            return None

        # Step 4: Extract stream URL (priority: HLS > DASH > MP4)
        # NOTE: Restrict to 720p max for international access (1080p+ blocked outside Russia)
        stream_url = None
        manifest_type = None

        # HLS (best for Kodi) - 720p should work internationally
        for key in ["hls_live", "hls_ondemand", "hls"]:
            if player_params.get(key):
                stream_url = player_params[key]
                manifest_type = "hls"
                log(f"[vk.com] Found HLS: {key}")
                break

        # DASH
        if not stream_url:
            for key in ["dash_live", "dash_ondemand"]:
                if player_params.get(key):
                    stream_url = player_params[key]
                    manifest_type = "dash"
                    log(f"[vk.com] Found DASH: {key}")
                    break

        # Direct MP4 (fallback - pick 720p or lower for international access)
        if not stream_url:
            mp4_urls = {}
            for key, value in player_params.items():
                if key.startswith("url") and isinstance(value, str) and value:
                    try:
                        quality = int(key[3:])
                        mp4_urls[quality] = value
                    except ValueError:
                        continue

            if mp4_urls:
                # Pick 720p or the highest available under 720p
                preferred_qualities = [720, 480, 360, 240]
                chosen_quality = None
                for q in preferred_qualities:
                    if q in mp4_urls:
                        chosen_quality = q
                        break
                
                if not chosen_quality:
                    # If no preferred quality, pick lowest available
                    chosen_quality = min(mp4_urls.keys())
                
                stream_url = mp4_urls[chosen_quality]
                manifest_type = "mp4"
                log(f"[vk.com] Found MP4 {chosen_quality}p (restricted to 720p max for international)")

        if not stream_url:
            log_warning("[vk.com] No stream URL found in player params")
            return None

        # Step 5: Build result with headers
        stream_headers = {
            "User-Agent": session.headers["User-Agent"],
            "Referer": f"https://{host}/",
            "Origin": f"https://{host}",
        }

        # Append headers in pipe format for Kodi
        header_str = "&".join(f"{k}={v}" for k, v in stream_headers.items())
        full_url = f"{stream_url}|{header_str}"

        result = StreamInfo(
            url=full_url,
            headers=stream_headers,
            cookies=dict(session.cookies),
            manifest_type=manifest_type,
        )

        log(f"[vk.com] Success: {manifest_type} stream resolved")
        return result

    except requests.exceptions.ConnectionError as e:
        log_error(f"[vk.com] Connection error (VK may be blocking your IP): {e}")
        return None
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


def resolve_url_wrapper(url, referer=None):
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

    # Check for VidMoly
    elif any(domain in url for domain in ["vidmoly.net", "vidmoly.me", "vidmoly.to"]):
        result = extract_vidmoly_url(url)
        if result:
            log(f"[vidmoly] Resolved to {result.manifest_type}")
        else:
            log_warning("[vidmoly] Optimized resolver failed")

    # Check for Filemoon-based hosts
    elif any(domain in url for domain in ["filemoon.sx", "filemoon.to", "filemoon.in",
                                           "byselapuix.com", "kerapoxy.cc", "moonmov.to"]):
        result = extract_filemoon_url(url)
        if result:
            log(f"[filemoon] Resolved to {result.manifest_type}")
        else:
            log_warning("[filemoon] Optimized resolver failed")

    # VK resolver - using Streamlink-based approach with WAF cookie handling
    # Check for VK
    elif any(domain in url for domain in ["vk.com", "vkvideo.ru", "vkontakte.ru"]):
        result = extract_vk_url_optimized(url)
        if result:
            log(f"[vk.com] Resolved to {result.manifest_type}")
        else:
            log_warning("[vk.com] Optimized resolver failed")

    # For other URLs, try to return a simple StreamInfo only for direct video URLs
    elif url.endswith(".m3u8"):
        result = StreamInfo(url, manifest_type="hls")
    elif url.endswith(".mpd"):
        result = StreamInfo(url, manifest_type="dash")
    elif url.endswith(".mp4"):
        result = StreamInfo(url, manifest_type="mp4")
    else:
        # Unknown domain - return None so __init__.py can try ResolveURL
        result = None

    # Cache the result
    if result:
        _RESOLVER_CACHE[url] = (now, result)

    return result
