"""Optimized video URL resolvers for ok.ru and vk.com."""

import re
import json
import urllib.parse
import time
import html
import requests
import xbmc
import xbmcgui
from resources.lib.utils import (
    HEADERS,
    js_unpack,
    log,
    log_debug,
    log_error,
    log_warning,
)

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
    # Fix missing '?' before query parameters (e.g. nochat=1)
    url = re.sub(r'(\d+)(nochat=\d+|autoplay=\d+)', r'\1?\2', url)
    
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
            try:
                metadata = json.loads(metadata)
            except:
                metadata = None
        
        # If metadata is missing or doesn't have streams, try metadataUrl
        has_inline_streams = False
        if metadata and isinstance(metadata, dict):
            # Check for any HLS/DASH/Videos
            has_inline_streams = any(metadata.get(f) for f in ["hlsManifestUrl", "hlsMasterPlaylistUrl", "hls", "videos"])
            if not has_inline_streams and "movie" in metadata:
                movie = metadata["movie"]
                if isinstance(movie, dict):
                    has_inline_streams = any(movie.get(f) for f in ["hlsManifestUrl", "hlsMasterPlaylistUrl", "hls", "videos"])

        if not metadata or not has_inline_streams:
            # Fetch from metadataUrl
            metadata_url = flashvars.get("metadataUrl")
            if metadata_url:
                log("[ok.ru] Inline metadata insufficient, fetching from metadataUrl...")
                metadata_url = urllib.parse.unquote(metadata_url)
                post_data = {}
                if flashvars.get("location"):
                    post_data["st.location"] = flashvars["location"]

                meta_response = session.post(
                    metadata_url, data=post_data, timeout=15
                )
                if meta_response.status_code == 200:
                    metadata = meta_response.json()
                    log("[ok.ru] MetadataUrl fetch successful")

        if not metadata or "movie" not in metadata:
            log_warning("[ok.ru] No metadata found")
            return None

        movie = metadata["movie"]

        # Debug: log available metadata keys
        log(f"[ok.ru] Metadata keys: {list(metadata.keys())}")
        if isinstance(movie, dict):
            log(f"[ok.ru] Movie keys: {list(movie.keys())}")

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

        # Stream fields to check in both metadata root and 'movie' object
        stream_fields = [
            ("hls", ["hlsManifestUrl", "ondemandHls", "hls", "hlsManifest", "masterHls", "playlistHls", "hlsMasterPlaylistUrl"]),
            ("dash", ["ondemandDash", "metadataWebmUrl", "dash", "dashManifest", "mpd"]),
        ]

        for m_type, fields in stream_fields:
            stream_url = None
            # Check root
            for field in fields:
                if metadata.get(field):
                    stream_url = metadata[field]
                    break
            # Check movie object if not found in root
            if not stream_url and isinstance(movie, dict):
                for field in fields:
                    if movie.get(field):
                        stream_url = movie[field]
                        break
            
            if stream_url:
                stream_url = stream_url.replace("\\/", "/")
                formats.append({
                    "url": stream_url,
                    "format_id": m_type,
                    "priority": 100 if m_type == "hls" else 90,
                    "manifest_type": m_type
                })

        # Embedded DASH
        dash_embedded = metadata.get("metadataEmbedded") or (isinstance(movie, dict) and movie.get("metadataEmbedded"))
        if dash_embedded:
            formats.append({
                "url": dash_embedded,
                "format_id": "dash-embedded",
                "priority": 91,
                "manifest_type": "dash"
            })

        # Direct MP4 files
        videos = metadata.get("videos")
        if not videos and isinstance(movie, dict):
            videos = movie.get("videos")
            
        for video in (videos or []):
            video_url = video.get("url")
            if video_url:
                video_url = video_url.replace("\\/", "/")
                quality = video.get("name", "unknown")
                width = video.get("width", 0)
                height = video.get("height", 0)
                priority = 50 + (width or height or 0) // 100
                formats.append({
                    "url": video_url,
                    "format_id": f"mp4-{quality}",
                    "priority": priority,
                    "manifest_type": "mp4",
                })

        if not formats:
            # Fallback Step: Try mobile site (robust for some restricted videos)
            log("[ok.ru] No formats in desktop metadata, trying mobile site fallback...")
            try:
                video_id = url.split("/")[-1].split("?")[0]
                mobile_url = f"https://m.ok.ru/video/{video_id}"
                m_resp = session.get(mobile_url, timeout=15)
                m_match = re.search(r'data-video="(.+?)"', m_resp.text)
                if m_match:
                    m_data = json.loads(html.unescape(m_match.group(1)))
                    m_video_src = m_data.get("videoSrc")
                    if m_video_src:
                        log("[ok.ru] Found stream via mobile site")
                        # Get redirect URL (direct MP4)
                        direct_resp = session.head(m_video_src, allow_redirects=True, timeout=10)
                        formats.append({
                            "url": direct_resp.url,
                            "format_id": "mobile-mp4",
                            "priority": 85,
                            "manifest_type": "mp4"
                        })
            except Exception as m_e:
                log_warning(f"[ok.ru] Mobile fallback failed: {m_e}")

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
        cookies_dict = session.cookies.get_dict()

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
            cookies=session.cookies.get_dict(),
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


def extract_filemoon_url_optimized(url):
    """
    Optimized extractor for Filemoon.
    Unpacks JS to find the final video source.
    """
    log(f"[filemoon] Extracting from: {url}")

    # Check cache
    global _RESOLVER_CACHE
    now = time.time()
    cache_key = f"filemoon_{url}"
    if cache_key in _RESOLVER_CACHE:
        timestamp, cached = _RESOLVER_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            log("[filemoon] Using cached result")
            return cached

    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://filemoon.to/',
        })
        
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            log_warning(f"[filemoon] Page fetch failed: {response.status_code}")
            return None
            
        page_content = response.text
        
        # Step 1: Look for packed scripts
        video_url = None
        # Filemoon usually has the source in an eval block
        packed_matches = re.findall(r"(eval\(function\(p,a,c,k,e,.*?\)\s*;?)", page_content, re.DOTALL)
        
        for packed in packed_matches:
            try:
                unpacked = js_unpack(packed)
                # Step 2: Find the file URL in the unpacked content
                file_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', unpacked)
                if file_match:
                    video_url = file_match.group(1)
                    log_debug(f"[filemoon] Found HLS URL in unpacked JS")
                    break
            except Exception as ue:
                log_debug(f"[filemoon] Unpack failed for block: {ue}")

        # Fallback 1: Search directly in page content for .m3u8
        if not video_url:
            file_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', page_content)
            if file_match:
                video_url = file_match.group(1)
                log_debug(f"[filemoon] Found HLS URL directly in page")
        
        # Fallback 2: Check for modern React template but try to find hidden config
        if not video_url and "root" in page_content and "assets" in page_content:
            log("[filemoon] Modern template detected, looking for secondary data...")
            # Sometimes data is in a script tag with id like 'config'
            config_match = re.search(r'id=["\']config["\'][^>]*>(.+?)</script>', page_content)
            if config_match:
                try:
                    config = json.loads(config_match.group(1))
                    video_url = config.get('file') or config.get('url')
                except: pass

        if not video_url:
            log_warning("[filemoon] No video URL found")
            return None

        # Fix slashes
        video_url = video_url.replace("\\/", "/")
        log(f"[filemoon] Found URL: {video_url[:100]}...")

        # Filemoon requires Referer and Origin for playback
        parsed_url = urllib.parse.urlparse(url)
        base_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        result = StreamInfo(
            url=video_url,
            headers={
                "User-Agent": session.headers['User-Agent'],
                "Referer": base_origin + "/",
                "Origin": base_origin
            },
            manifest_type="hls"
        )

        _RESOLVER_CACHE[cache_key] = (now, result)
        return result

    except Exception as e:
        log_error(f"[filemoon] Extraction error: {e}")
        return None


def extract_mail_ru_url_optimized(url):
    """
    Optimized extractor for my.mail.ru videos.
    Prioritizes metadata discovery from page content and handles mangled URLs.
    """
    # Normalize URL - handle mangled URLs (sometimes missing /video/embed/ or ID is outside path)
    if "my.mail.ru" in url and not "/video/embed/" in url:
        id_match = re.search(r'(\d{10,})', url)
        if id_match:
            url = f"https://my.mail.ru/video/embed/{id_match.group(1)}"
            log(f"[mail.ru] Normalized URL to: {url}")

    log(f"[mail.ru] Extracting from: {url}")

    # Check cache first
    global _RESOLVER_CACHE
    now = time.time()
    cache_key = f"mailru_{url}"
    if cache_key in _RESOLVER_CACHE:
        timestamp, cached = _RESOLVER_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            log("[mail.ru] Using cached result")
            return cached

    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        # Step 1: Get the embed page to find the real metadata URL
        log("[mail.ru] Fetching embed page...")
        page_resp = session.get(url, timeout=15)
        if page_resp.status_code != 200:
            log_warning(f"[mail.ru] Failed to fetch embed page: {page_resp.status_code}")
            return None
            
        # Strategy A: Find "metadataUrl" in scripts (most reliable)
        meta_url = None
        meta_match = re.search(r'"metadataUrl"\s*:\s*"([^"]+)"', page_resp.text)
        if not meta_match:
            meta_match = re.search(r'"metaUrl"\s*:\s*"([^"]+)"', page_resp.text)
            
        if meta_match:
            meta_url = meta_match.group(1)
            if meta_url.startswith('//'): meta_url = 'https:' + meta_url
            elif meta_url.startswith('/'): meta_url = 'https://my.mail.ru' + meta_url
            log(f"[mail.ru] Found metadata API via page: {meta_url[:60]}...")
        else:
            # Strategy B: Fallback to ID-based construction
            video_id = None
            id_match = re.search(r"/video/embed/(\d+)", url)
            if id_match:
                video_id = id_match.group(1)
            else:
                id_match = re.search(r'"videoid"\s*:\s*"(\d+)"', page_resp.text)
                if id_match: video_id = id_match.group(1)
            
            if video_id:
                meta_url = f"https://my.mail.ru/+/video/meta/{video_id}"
                log(f"[mail.ru] Constructing API URL from ID: {video_id}")

        if not meta_url:
            log_warning("[mail.ru] Could not discover metadata API URL")
            return None

        # Step 2: Call the Metadata API
        session.headers["Referer"] = url
        response = session.get(meta_url, timeout=15)
        
        if response.status_code != 200:
            log_warning(f"[mail.ru] Meta API failed with status {response.status_code}")
            return None
            
        data = response.json()
        videos = data.get("videos")
        if not videos:
            log_warning("[mail.ru] No video formats found in API response")
            return None

        # Parse formats
        formats = []
        for v in videos:
            v_url = v.get("url")
            if v_url:
                # Priority based on resolution key (e.g. 1080p, 720p)
                priority = 50
                if "1080" in key: priority = 90
                elif "720" in key: priority = 80
                elif "480" in key: priority = 70
                elif "360" in key: priority = 60

                # Detect manifest type from URL
                m_type = "mp4"
                if ".m3u8" in v_url: m_type = "hls"
                elif ".mpd" in v_url or "stream.mpd" in v_url: m_type = "dash"

                formats.append({
                    "url": v_url,
                    "format_id": key,
                    "priority": priority,
                    "manifest_type": m_type
                })

        if not formats:
            return None

        formats.sort(key=lambda x: x["priority"], reverse=True)
        best = formats[0]
        
        log(f"[mail.ru] Selected format: {best['format_id']}")
        
        result = StreamInfo(
            url=best["url"],
            headers={"User-Agent": HEADERS["User-Agent"], "Referer": "https://my.mail.ru/"},
            cookies=session.cookies.get_dict(),
            manifest_type="mp4"
        )

        _RESOLVER_CACHE[cache_key] = (now, result)
        return result

    except Exception as e:
        log_error(f"[mail.ru] Extraction error: {e}")
        return None


def create_listitem_with_stream(stream_info, title="Video"):
    """
    Create a properly configured xbmcgui.ListItem for the stream.
    This handles all the InputStream Adaptive configuration.
    """
    list_item = xbmcgui.ListItem()
    list_item.setInfo("video", {"title": title})

    # Check if we need to bypass InputStream Adaptive
    # We bypass ISA for CDNs that are strict with headers/cookies (OK, VK, Mail.ru, HQQ)
    is_russian_cdn = any(
        domain in stream_info.url for domain in [
            "vkuser.net", 
            "vk.com", "vkvideo.ru", "vk.me", "vk-cdn.net",
            "mail.ru", "imgsmail.ru",
            "hqq.ac", "hqq.to", "netu.tv", "waaw.to", "waaw.ac", "cfglobalcdn.com"
        ]
    )
    
    # Mail.ru DASH manifests (.mpd) with slave[] params REQUIRE inputstream.adaptive
    is_mailru_dash = "mail.ru" in stream_info.url and stream_info.is_dash()
    
    if (stream_info.is_hls() or stream_info.is_dash()) and not is_russian_cdn or is_mailru_dash:
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
        # Optimizations for FFmpeg internal player
        list_item.setProperty("VideoPlayer.UseFastSeek", "true")

        if is_russian_cdn:
            # OK.ru, VK and Mail.ru often contain all auth in query parameters OR require specific headers.
            # Fix missing '?' in URL if it's malformed
            final_url = stream_info.url
            if ("cmd=" in final_url or "slave[]=" in final_url) and not "?" in final_url:
                final_url = re.sub(r'(\.m3u8|\.mp4|\.mpd)(cmd=|nochat=|autoplay=|slave\[\]=)', r'\1?\2', final_url)
            
            # Start building header string for Kodi VFS
            path_parts = []
            
            # 1. User-Agent (Always needed)
            ua = stream_info.headers.get("User-Agent") or HEADERS.get("User-Agent", "Mozilla/5.0")
            path_parts.append(f"User-Agent={urllib.parse.quote(ua)}")
            
            # 2. Referer (Critical for Mail.ru, VK and HQQ)
            referer = stream_info.headers.get("Referer")
            if not referer:
                if "mail.ru" in final_url:
                    referer = "https://my.mail.ru/"
                elif "vk.com" in final_url or "vkvideo.ru" in final_url:
                    referer = "https://vk.com/"
                elif "hqq" in final_url or "netu" in final_url or "waaw" in final_url:
                    referer = "https://hqq.ac/"
                elif "cfglobalcdn.com" in final_url:
                    referer = "https://hqq.ac/"
                
            if referer:
                path_parts.append(f"Referer={urllib.parse.quote(referer)}")

            # 3. Cookies (Critical for Mail.ru MP4s)
            if stream_info.cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in stream_info.cookies.items()])
                path_parts.append(f"Cookie={urllib.parse.quote(cookie_str)}")
            
            header_string = "&".join(path_parts)
            final_path = f"{final_url}|{header_string}"
            list_item.setPath(final_path)
            log_debug(f"[stream] Russian CDN path set: {final_path[:150]}...")

        elif stream_info.headers:
            header_string = "&".join([f"{k}={urllib.parse.quote(v)}" for k, v in stream_info.headers.items()])
            list_item.setPath(f"{stream_info.url}|{header_string}")
        else:
            list_item.setPath(stream_info.url)

    return list_item


def extract_bysebuho_url(url):
    """
    Extractor for bysebuho.com (used on serialero).
    Unpacks JS to find final video source.
    """
    log(f"[bysebuho] Extracting from: {url}")
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return None
        
        # Look for packed script
        packed_match = re.search(r"(eval\(function\(p,a,c,k,e,.*?\)\s*;?)", response.text, re.DOTALL)
        if packed_match:
            unpacked = js_unpack(packed_match.group(1))
            file_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', unpacked)
            if file_match:
                video_url = file_match.group(1).replace("\\/", "/")
                return StreamInfo(video_url, headers={"Referer": url, "User-Agent": HEADERS["User-Agent"]}, manifest_type="hls")
    except Exception as e:
        log_error(f"[bysebuho] Extraction error: {e}")
    return None


def extract_hqq_url(url):
    """
    Extractor for HQQ.ac / Waaw.to / Netu.tv.
    These use the same system with packed JS.
    """
    log(f"[hqq] Extracting from: {url}")
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return None
        
        # Look for packed script
        packed_match = re.search(r"(eval\(function\(p,a,c,k,e,.*?\)\s*;?)", response.text, re.DOTALL)
        if packed_match:
            unpacked = js_unpack(packed_match.group(1))
            # HQQ usually has a manifest or direct link
            file_match = re.search(r'["\'](https?://[^"\']+\.(m3u8|mp4)[^"\']*)["\']', unpacked)
            if file_match:
                video_url = file_match.group(1).replace("\\/", "/")
                return StreamInfo(video_url, headers={"Referer": url, "User-Agent": HEADERS["User-Agent"]})
        
        # Fallback: search for manifest in raw page
        file_match = re.search(r'["\'](https?://[^"\']+\.(m3u8|mp4)[^"\']*)["\']', response.text)
        if file_match:
            video_url = file_match.group(1).replace("\\/", "/")
            return StreamInfo(video_url, headers={"Referer": url, "User-Agent": HEADERS["User-Agent"]})

    except Exception as e:
        log_error(f"[hqq] Extraction error: {e}")
    return None


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

    # Check for Mail.ru
    elif "my.mail.ru" in url:
        result = extract_mail_ru_url_optimized(url)
        if result:
            log(f"[mail.ru] Resolved to {result.manifest_type}")
        else:
            log_warning("[mail.ru] Optimized resolver failed")

    # Check for hqq
    elif any(domain in url for domain in ["hqq.ac", "hqq.to", "waaw.to", "waaw.ac", "netu.tv", "cfglobalcdn.com"]):
        result = extract_hqq_url(url)
        if result:
            log(f"[hqq] Resolved successfully")

    # Check for bysebuho
    elif "bysebuho.com" in url:
        result = extract_bysebuho_url(url)
        if result:
            log(f"[bysebuho] Resolved successfully")

    # Check for filemoon
    elif "filemoon" in url:
        result = extract_filemoon_url_optimized(url)
        if result:
            log(f"[filemoon] Resolved successfully")

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
