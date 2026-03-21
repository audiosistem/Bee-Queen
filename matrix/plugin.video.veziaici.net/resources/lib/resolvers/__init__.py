"""Video URL resolvers for various hosting platforms."""

import html
import json
import re
import traceback
import urllib.parse

import requests
import resolveurl

# Import optimized resolvers
from resources.lib.resolvers.optimized import (
    StreamInfo,
    create_listitem_with_stream,
    resolve_url_wrapper as optimized_resolve,
)
from resources.lib.utils import (
    HEADERS,
    get_html_content,
    int_or_none,
    log,
    log_debug,
    log_error,
    log_warning,
)


def resolve_url_wrapper(url, referer=None):
    """
    Main URL resolver wrapper that delegates to optimized resolvers.
    Returns StreamInfo object or None.
    """
    # 1. Try OPTIMIZED extraction first
    try:
        result = optimized_resolve(url, referer=referer)
        if result:
            return result
    except Exception as e:
        log_warning(f"[resolver] Optimized extraction failed for {url.split('/')[2]}: {e}")

    # 2. For other domains, try ResolveURL
    try:
        if resolveurl.HostedMediaFile(url=url).valid_url():
            log(f"Trying ResolveURL for {url.split('/')[2]}")
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
    except Exception as e:
        log_error(f"ResolveURL Error: {e}")

    # 3. Fallback for direct video URLs
    if url.endswith(".m3u8"):
        return StreamInfo(url, manifest_type="hls")
    elif url.endswith(".mpd"):
        return StreamInfo(url, manifest_type="dash")
    elif url.endswith(".mp4"):
        return StreamInfo(url, manifest_type="mp4")

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
                return StreamInfo(matches[0])

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
                return StreamInfo(video_url)

    except Exception as e:
        log_error(f"Vidmoly extraction failed: {e}")

    log_warning("Vidmoly: No video URL found")
    return None
