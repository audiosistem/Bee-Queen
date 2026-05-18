"""Video URL resolvers for various hosting platforms."""

import html
import json
import re
import traceback
import urllib.parse

import requests

# Patch ResolveURL setting if empty to avoid crash
try:
    import xbmcaddon
    _res_addon = xbmcaddon.Addon('script.module.resolveurl')
    if not _res_addon.getSetting('bp_timeout'):
        _res_addon.setSetting('bp_timeout', '20')
except Exception:
    pass

try:
    import resolveurl
except Exception:
    resolveurl = None

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


def _resolve_vk_720p(url):
    """
    Resolve VK video URL requesting 720p quality specifically.
    720p works internationally while 1080p+ is restricted to Russia.
    """
    import re
    import json
    import requests
    from urllib.parse import urlparse, parse_qs
    from hashlib import md5

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        oid = params.get("oid", [None])[0]
        video_id = params.get("id", [None])[0]

        if not oid or not video_id:
            match = re.search(r"video(-?\d+)_(\d+)", url)
            if match:
                oid, video_id = match.group(1), match.group(2)

        if not oid or not video_id:
            return resolveurl.resolve(url)  # Fallback to default

        host = "vkvideo.ru" if "vkvideo.ru" in url else "vk.com"
        video_id_full = f"{oid}_{video_id}"

        session = requests.Session()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
        session.headers.update({"User-Agent": ua})

        # Get WAF cookie
        resp = session.get(f"https://{host}/", timeout=5, allow_redirects=False)
        if resp.headers.get("x-waf-redirect") == "1":
            hash_cookie = resp.cookies.get("hash429", "")
            if hash_cookie:
                key = md5(hash_cookie.encode("utf-8")).hexdigest()
                loc = resp.headers.get("Location", "")
                if loc:
                    sep = "&" if "?" in loc else "?"
                    session.get(f"{loc}{sep}key={key}", timeout=5)

        # Call API
        post_data = {"act": "show", "al": "1", "video": video_id_full}
        headers = {
            "Referer": f"https://{host}/",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = session.post(f"https://{host}/al_video.php?act=show",
                           data=post_data, headers=headers, timeout=10)

        text = resp.text
        if text.startswith("<!--"):
            text = text[4:]

        js = json.loads(text)
        payload = js.get("payload", [])

        # Find player params
        player_params = None
        for item in payload:
            if isinstance(item, list):
                for sub in item:
                    if isinstance(sub, dict) and "player" in sub:
                        player_params = sub.get("player", {}).get("params", [None])[0]
                        break
                if player_params:
                    break

        if not player_params:
            return resolveurl.resolve(url)

        # Pick 720p or lower
        stream_url = None
        for q in [720, 480, 360, 240]:
            key = f"url{q}"
            if player_params.get(key):
                stream_url = player_params[key]
                log(f"[VK 720p] Using url{q}")
                break

        # Try HLS as alternative (usually works internationally)
        if not stream_url:
            stream_url = player_params.get("hls") or player_params.get("hls_ondemand")
            if stream_url:
                log("[VK 720p] Using HLS stream")

        if not stream_url:
            return resolveurl.resolve(url)

        # Add headers
        header_str = f"User-Agent={ua}&Referer=https://{host}/"
        return f"{stream_url}|{header_str}"

    except Exception as e:
        log_warning(f"[VK 720p] Failed: {e}, falling back to ResolveURL")
        try:
            return resolveurl.resolve(url)
        except Exception:
            return None


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
        if resolveurl and resolveurl.HostedMediaFile(url=url).valid_url():
            log(f"Trying ResolveURL for {url.split('/')[2]}")
            
            # For VK: try to get 720p specifically
            is_vk = any(d in url for d in ["vk.com", "vkvideo.ru", "vkontakte.ru"])
            
            if is_vk:
                resolved = _resolve_vk_720p(url)
            else:
                resolved = resolveurl.resolve(url)
            
            if resolved:
                log(f"ResolveURL success: {resolved[:150]}...")
                # Determine manifest type
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
