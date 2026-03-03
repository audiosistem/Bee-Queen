"""Video URL resolvers for various hosting platforms."""

import re
import json
import urllib.parse
import requests
import resolveurl
from resources.lib.utils import (
    get_html_content,
    log,
    log_debug,
    log_error,
    log_warning,
    HEADERS,
)

# Import optimized resolvers
from resources.lib.resolvers.optimized import (
    StreamInfo,
    extract_ok_ru_url_optimized,
    extract_vk_url_optimized,
    create_listitem_with_stream,
)


def resolve_url_wrapper(url):
    """
    Main URL resolver wrapper that tries direct extraction first, then ResolveURL.
    Returns StreamInfo object for optimized playback of ok.ru and vk.com,
    or string URL for other platforms.
    """
    log(f"Resolving URL: {url.split('/')[2]}")

    is_ok_ru = any(domain in url for domain in ["ok.ru", "odnoklassniki.ru"])
    is_vk = any(domain in url for domain in ["vk.com", "vkvideo.ru", "vkontakte.ru"])
    is_vidmoly = "vidmoly" in url
    is_filemoon = "filemoon" in url

    # Try OPTIMIZED extraction for ok.ru and vk.com (returns StreamInfo)
    if is_ok_ru:
        try:
            result = extract_ok_ru_url_optimized(url)
            if result:
                log(f"[ok.ru] Optimized extraction success: {result.manifest_type}")
                return result
        except Exception as e:
            log_warning(f"[ok.ru] Optimized extraction failed: {e}")
            import traceback

            log_debug(f"[ok.ru] Traceback: {traceback.format_exc()}")

        # Fallback to legacy extractor
        try:
            result = extract_ok_ru_url(url)
            if result:
                log(f"[ok.ru] Legacy extraction success")
                return StreamInfo(
                    result, manifest_type="hls" if ".m3u8" in result else "mp4"
                )
        except Exception as e:
            log_warning(f"[ok.ru] Legacy extraction failed: {e}")

    if is_vk:
        try:
            result = extract_vk_url_optimized(url)
            if result:
                log(f"[vk.com] Optimized extraction success: {result.manifest_type}")
                return result
        except Exception as e:
            log_warning(f"[vk.com] Optimized extraction failed: {e}")
            import traceback

            log_debug(f"[vk.com] Traceback: {traceback.format_exc()}")

        # Fallback to legacy extractor
        try:
            result = extract_vk_url(url)
            if result:
                log(f"[vk.com] Legacy extraction success")
                return StreamInfo(
                    result, manifest_type="hls" if ".m3u8" in result else "mp4"
                )
        except Exception as e:
            log_warning(f"[vk.com] Legacy extraction failed: {e}")

    if is_vidmoly:
        try:
            result = extract_vidmoly_url(url)
            if result:
                return result
        except Exception as e:
            log_error(f"vidmoly extraction failed: {e}")

    if is_filemoon:
        try:
            result = extract_filemoon_url(url)
            if result:
                return result
        except Exception as e:
            log_error(f"filemoon extraction failed: {e}")

    # For other domains, try ResolveURL
    try:
        log(f"Trying ResolveURL for {url.split('/')[2]}")
        if resolveurl.HostedMediaFile(url=url).valid_url():
            resolved = resolveurl.resolve(url)
            if resolved:
                log(f"ResolveURL success: {resolved[:150]}...")
                # Return as StreamInfo
                manifest_type = (
                    "hls"
                    if ".m3u8" in resolved
                    else ("dash" if ".mpd" in resolved else "mp4")
                )
                return StreamInfo(resolved, manifest_type=manifest_type)
            else:
                log_warning("ResolveURL returned None")
    except Exception as e:
        log_error(f"ResolveURL Error: {e}")

    # Fallback for direct video URLs
    if url.endswith(".m3u8"):
        log("Returning HLS URL as fallback")
        return StreamInfo(url, manifest_type="hls")
    elif url.endswith(".mpd"):
        log("Returning DASH URL as fallback")
        return StreamInfo(url, manifest_type="dash")
    elif url.endswith(".mp4"):
        log("Returning MP4 URL as fallback")
        return StreamInfo(url, manifest_type="mp4")

    return None


def extract_ok_ru_url(url):
    """Extract video URL from ok.ru embed page."""
    log(f"Extracting ok.ru URL: {url}")
    session = requests.Session()

    try:
        response = session.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        webpage = response.text
    except requests.exceptions.RequestException as e:
        log_error(f"Failed to fetch ok.ru page: {e}")
        return None

    # Check for errors
    if "vp_video_stub_txt" in webpage:
        error = re.search(r'[^>]+class="vp_video_stub_txt"[^>]*>([^<]+)<', webpage)
        if error:
            log_error(f"ok.ru error: {error.group(1)}")
            return None

    # Extract player data from data-options
    player_match = re.search(
        r'data-options=(?P<quote>["\'])(?P<player>{.+?})(?P=quote)', webpage, re.DOTALL
    )

    if not player_match:
        log_warning("No player data found")
        return None

    try:
        player_data = json.loads(player_match.group("player").replace("&quot;", '"'))
        flashvars = player_data.get("flashvars", {})
        metadata = flashvars.get("metadata")

        if metadata and isinstance(metadata, str):
            metadata = json.loads(metadata)
        elif not metadata:
            metadata_url = flashvars.get("metadataUrl")
            if metadata_url:
                metadata_url = urllib.parse.unquote(metadata_url)
                data = {}
                if flashvars.get("location"):
                    data["st.location"] = flashvars["location"]
                try:
                    meta_response = session.post(
                        metadata_url,
                        data=urllib.parse.urlencode(data),
                        headers=HEADERS,
                        timeout=10,
                    )
                    metadata = meta_response.json()
                except Exception as e:
                    log_warning(f"Failed to fetch metadata: {e}")
                    return None

        if not metadata or "movie" not in metadata:
            log_warning("No movie data in metadata")
            return None

        movie = metadata["movie"]
        provider = metadata.get("provider", "")

        # Handle YouTube embeds
        if provider == "USER_YOUTUBE":
            youtube_url = movie.get("contentId")
            if youtube_url:
                log(f"YouTube embed detected: {youtube_url}")
                return youtube_url

        # Collect all formats
        formats = []

        # Direct video formats
        for video in metadata.get("videos", []):
            video_url = video.get("url")
            if video_url:
                formats.append(
                    {
                        "url": video_url,
                        "format_id": video.get("name", "unknown"),
                        "width": int_or_none(video.get("width")),
                        "height": int_or_none(video.get("height")),
                    }
                )

        # HLS manifest
        hls_url = metadata.get("hlsManifestUrl") or metadata.get("ondemandHls")
        if hls_url:
            formats.append(
                {
                    "url": hls_url,
                    "format_id": "hls",
                    "ext": "mp4",
                    "protocol": "m3u8",
                }
            )

        # DASH manifest
        dash_url = metadata.get("ondemandDash") or metadata.get("metadataWebmUrl")
        if dash_url:
            formats.append({"url": dash_url, "format_id": "dash"})

        # Live HLS
        live_hls = metadata.get("hlsMasterPlaylistUrl")
        if live_hls:
            formats.append({"url": live_hls, "format_id": "live-hls"})

        if not formats:
            if metadata.get("paymentInfo"):
                log_warning("Video is paid")
            else:
                log_warning("No formats found")
            return None

        # Sort formats: prefer HLS over direct URLs, then by quality
        def format_key(fmt):
            fmt_id = fmt.get("format_id", "").lower()
            is_hls = "hls" in fmt_id or ".m3u8" in fmt.get("url", "")
            quality = max(fmt.get("width") or 0, fmt.get("height") or 0)
            return (is_hls, quality)

        formats.sort(key=format_key, reverse=True)
        best_format = formats[0]

        log(f"Total formats: {len(formats)}")
        log(f"Best format: {best_format['format_id']}")

        session.cookies.clear()
        return best_format["url"]

    except Exception as e:
        log_error(f"Failed to extract ok.ru: {e}")
        return None


def extract_vk_url(url):
    """Extract video URL from vk.com/vkvideo.ru using VK API."""
    log(f"Extracting vk URL: {url}")

    # Extract video ID from URL
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
        log_warning("Could not extract VK video IDs")
        return None

    video_id_full = f"{oid}_{video_id}"
    log(f"VK video ID: {video_id_full}")

    api_url = "https://vk.com/al_video.php"
    session = requests.Session()

    # Get cookies first
    try:
        session.get("https://vk.com/", headers=HEADERS, timeout=15)
    except Exception:
        pass

    api_headers = HEADERS.copy()
    api_headers["Referer"] = "https://vk.com/"
    api_headers["X-Requested-With"] = "XMLHttpRequest"
    api_headers["Content-Type"] = "application/x-www-form-urlencoded"

    post_data = {"act": "show", "al": "1", "video": video_id_full}

    try:
        response = session.post(
            api_url, data=post_data, headers=api_headers, timeout=15
        )
        response_text = response.text

        # Try to find JSON data with player params
        json_match = re.search(r'\{.*"player".*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if "player" in data and "params" in data["player"]:
                    player_params = data["player"]["params"]
                    if isinstance(player_params, list) and len(player_params) > 0:
                        params = player_params[0]
                        # Look for HLS URL
                        for key in ["hls", "hls_ondemand", "hls_live"]:
                            if key in params and params[key]:
                                log(f"Found HLS URL via API")
                                return params[key]
                        # Look for DASH URL
                        for key in ["dash", "dash_ondemand", "dash_live"]:
                            if key in params and params[key]:
                                log(f"Found DASH URL via API")
                                return params[key]
            except Exception:
                pass

        # Try alternative patterns
        if '"hls"' in response_text:
            hls_match = re.search(r'"hls"\s*:\s*"([^"]+)"', response_text)
            if hls_match:
                return hls_match.group(1).replace("\\/", "/")

        if '"hls_ondemand"' in response_text:
            hls_match = re.search(r'"hls_ondemand"\s*:\s*"([^"]+)"', response_text)
            if hls_match:
                return hls_match.group(1).replace("\\/", "/")

    except Exception as e:
        log_warning(f"VK API error: {e}")

    # Fallback to webpage extraction
    log("Trying fallback extraction from page")
    direct_url = f"https://vk.com/video{video_id_full}"

    try:
        response = requests.get(direct_url, headers=HEADERS, timeout=15)
        webpage = response.text
    except Exception as e:
        log_error(f"Failed to fetch VK page: {e}")
        return None

    # Try patterns to find URLs
    s_pattern = r'"url\d*"\s*:\s*"(.+?)\.(\d+)\.mp4'
    matches = re.findall(s_pattern, webpage)

    if matches:
        url_list = []
        for match in matches:
            base_url = match[0]
            quality = match[1]
            video_url = f"{base_url}.{quality}.mp4"
            url_list.append((quality, video_url))

        url_list.sort(key=lambda x: int(x[0]), reverse=True)
        best_quality, best_url = url_list[0]
        log(f"Best mp4 quality: {best_quality}p")
        return best_url

    log_warning("Could not extract VK URL")
    return None


def extract_vidmoly_url(url):
    """Extract direct video URL from vidmoly embed page."""
    log(f"Extracting vidmoly URL: {url}")

    try:
        parsed = urllib.parse.urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}/"

        headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": url,
            "Sec-Fetch-Dest": "iframe",
        }

        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        page_content = response.text

        # Try to find direct m3u8 or mp4 URLs
        direct_patterns = [
            r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*',
        ]

        for pattern in direct_patterns:
            matches = re.findall(pattern, page_content)
            if matches:
                log(f"Found direct URL with pattern: {pattern}")
                return matches[0]

        # Extract video URL from sources
        patterns = [
            r'sources:\s*\[\{file:\s*"([^"]+)"',
            r"sources:\s*\[\{file:\s*\'([^\']+)\'",
            r'file:\s*"([^"]+\.m3u8[^"]*)"',
            r"file:\s*\'([^\']+\.m3u8[^\']*)\'",
            r'"file"\s*:\s*"([^"]+)"',
            r'file:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_content)
            if match:
                video_url = match.group(1).replace("\\/", "/").strip('"').strip("'")
                if not video_url.startswith("http"):
                    video_url = urllib.parse.urljoin(base_domain, video_url)
                if video_url.startswith("//"):
                    video_url = "https:" + video_url
                log(f"Vidmoly found URL: {video_url[:100]}...")
                return video_url

    except Exception as e:
        log_error(f"Vidmoly extraction failed: {e}")

    log_warning("Vidmoly: No video URL found")
    return None


def extract_filemoon_url(url):
    """Extract direct video URL from filemoon embed page."""
    log(f"Extracting filemoon URL: {url}")

    try:
        headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": url,
        }

        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        page_content = response.text

        # Find iframe
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', page_content)
        if iframe_match:
            iframe_url = iframe_match.group(1)

            if iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url
            elif iframe_url.startswith("/"):
                parsed = urllib.parse.urlparse(url)
                iframe_url = f"{parsed.scheme}://{parsed.netloc}{iframe_url}"

            iframe_headers = {
                "User-Agent": HEADERS["User-Agent"],
                "Referer": url,
            }

            iframe_response = requests.get(
                iframe_url, headers=iframe_headers, timeout=15, allow_redirects=True
            )
            iframe_content = iframe_response.text

            # Extract video URL
            video_match = re.search(r'file:\s*"([^"]+)"', iframe_content)
            if video_match:
                video_url = video_match.group(1)
                if video_url.startswith("//"):
                    video_url = "https:" + video_url
                elif not video_url.startswith("http"):
                    parsed = urllib.parse.urlparse(iframe_url)
                    video_url = f"{parsed.scheme}://{parsed.netloc}/{video_url}"

                log(f"Filemoon found URL: {video_url[:100]}...")
                return video_url

            log_warning("Filemoon: No file URL found in iframe")
        else:
            log_warning("Filemoon: No iframe found")

    except Exception as e:
        log_error(f"Filemoon extraction failed: {e}")

    return None


def int_or_none(value, default=None):
    """Convert value to int or return default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
