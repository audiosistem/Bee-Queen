"""Optimized video URL resolvers for various hosting platforms."""

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

# Simple cache for resolved URLs: {url_key: (timestamp, stream_info)}
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


def extract_ok_ru_url_optimized(url, referer=None):
    """
    Optimized extractor for ok.ru videos utilizing mobile headers.
    This approach bypasses complex desktop protections and retrieves streams directly.
    """
    # Fix missing '?' before query parameters (e.g. nochat=1)
    if ("nochat=" in url or "autoplay=" in url) and "?" not in url:
        url = re.sub(r'(\d+)(nochat=\d+|autoplay=\d+)', r'\1?\2', url)
    
    log(f"[ok.ru] Extracting from (Mobile API): {url}")

    # Check cache
    global _RESOLVER_CACHE
    now = time.time()
    cache_key = f"okru_mob_{url}_{referer}"
    if cache_key in _RESOLVER_CACHE:
        timestamp, cached = _RESOLVER_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            return cached

    # Crucial: Use a mobile User-Agent to force simple JSON response
    mobile_ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': mobile_ua,
        'Referer': referer or 'https://ok.ru/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    })

    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        webpage = response.text

        # Using regex to find player data
        player_match = re.search(
            r'data-options=(?P<quote>["\'])(?P<player>{.+?})(?P=quote)',
            webpage,
            re.DOTALL,
        )

        if not player_match:
            return None

        player_data = json.loads(player_match.group("player").replace("&quot;", '"'))
        flashvars = player_data.get("flashvars", {})
        metadata = flashvars.get("metadata")
        
        if metadata and isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = None

        if not metadata or "movie" not in metadata:
            # Try metadataUrl (POST)
            metadata_url = flashvars.get("metadataUrl")
            if metadata_url:
                metadata_url = urllib.parse.unquote(metadata_url)
                post_data = {"st.location": flashvars.get("location", "")}
                meta_resp = session.post(metadata_url, data=post_data, timeout=15)
                if meta_resp.status_code == 200:
                    metadata = meta_resp.json()

        if not metadata or "movie" not in metadata:
            return None

        movie = metadata["movie"]
        
        # VK Embed Handoff (Hybrid links)
        vk_movie = metadata.get("vkMovie")
        provider = metadata.get("provider", "")
        vk_url = None
        
        if vk_movie and isinstance(vk_movie, (dict, str)):
            if isinstance(vk_movie, dict):
                oid = vk_movie.get("oid") or vk_movie.get("owner_id")
                vid = vk_movie.get("vid") or vk_movie.get("video_id")
                vh = vk_movie.get("hash", "")
                if oid and vid:
                    vk_url = f"https://vk.com/video_ext.php?oid={oid}&id={vid}" + (f"&hash={vh}" if vh else "")
            elif isinstance(vk_movie, str) and "vk.com" in vk_movie:
                vk_url = vk_movie
        
        if not vk_url and provider in ["USER_VK", "UPLOADED_ODKL"]:
            content_id = movie.get("contentId")
            if content_id and content_id.isdigit() and len(content_id) > 10:
                vk_url = f"https://vk.com/video{content_id}"

        if vk_url:
            log(f"[ok.ru] Routing to VK: {vk_url}")
            return extract_vk_url_optimized(vk_url, referer=referer)

        # Extraction logic for native OK streams
        formats = []
        # Check HLS
        hls_url = metadata.get("hlsManifestUrl") or movie.get("hlsManifestUrl") or metadata.get("hlsMasterPlaylistUrl")
        if hls_url:
            formats.append({"url": hls_url.replace("\\/", "/"), "type": "hls", "priority": 100})
            
        # Check MP4s
        videos = metadata.get("videos") or movie.get("videos") or []
        for v in videos:
            v_url = v.get("url")
            if v_url:
                name = v.get("name", "unknown")
                priority = 80 if name == "hd" else (70 if name == "sd" else 50)
                formats.append({"url": v_url.replace("\\/", "/"), "type": "mp4", "priority": priority})

        if not formats:
            return None

        formats.sort(key=lambda x: x["priority"], reverse=True)
        best = formats[0]
        
        result = StreamInfo(
            url=best["url"],
            headers={"User-Agent": mobile_ua, "Referer": referer or "https://ok.ru/", "Origin": "https://ok.ru"},
            cookies=session.cookies.get_dict(),
            manifest_type=best["type"]
        )
        _RESOLVER_CACHE[cache_key] = (now, result)
        return result

    except Exception as e:
        log_error(f"[ok.ru] Error: {e}")
        return None


def extract_vk_url_optimized(url, referer=None):
    """Optimized extractor for VK videos."""
    log(f"[vk.com] Extracting from: {url}")
    
    global _RESOLVER_CACHE
    now = time.time()
    cache_key = f"vk_{url}_{referer}"
    if cache_key in _RESOLVER_CACHE:
        timestamp, cached = _RESOLVER_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            return cached

    # Basic ID extraction
    id_match = re.search(r'video(-?\d+_\d+|\d{10,})', url)
    video_id = id_match.group(1) if id_match else None
    
    if video_id and video_id.isdigit() and len(video_id) == 14:
        # Hybrid OK/VK IDs (14 digits) often need to be split
        video_id = f"{video_id[:9]}_{video_id[9:]}"
        log(f"[vk.com] Normalized naked ID to: {video_id}")

    if not video_id:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        oid = params.get("oid", [None])[0]
        vid = params.get("id", [None])[0]
        if oid and vid: video_id = f"{oid}_{vid}"

    if not video_id:
        return None

    domain = "vkvideo.ru" if "vkvideo.ru" in url else "vk.com"
    session = requests.Session()
    session.headers.update(HEADERS)
    if referer: session.headers["Referer"] = referer

    try:
        api_url = f"https://{domain}/al_video.php"
        post_data = {"act": "show", "al": "1", "video": video_id}
        # Add hash if present in URL
        h_match = re.search(r'hash=([a-z0-9]+)', url)
        if h_match: post_data["hash"] = h_match.group(1)

        resp = session.post(api_url, data=post_data, timeout=20)
        text = resp.text

        formats = []
        # Find HLS
        hls_match = re.search(r'["\'](https?://[^\s"\'<>!]+?\.m3u8[^\s"\'<>!]*?)["\']', text)
        if hls_match:
            formats.append({"url": hls_match.group(1).replace("\\/", "/"), "type": "hls", "priority": 100})
            
        # Find MP4s
        mp4_matches = re.findall(r'"url(\d+)"\s*:\s*"([^"]+)"', text)
        for quality, v_url in mp4_matches:
            q = int(quality)
            formats.append({"url": v_url.replace("\\/", "/"), "type": "mp4", "priority": q // 10})

        if not formats:
            # Try embed page direct search as fallback
            embed_url = None
            if "video_ext.php" not in url:
                if "_" in video_id:
                    oid, vid = video_id.split('_')
                    embed_url = f"https://{domain}/video_ext.php?oid={oid}&id={vid}"
                    if h_match: embed_url += f"&hash={h_match.group(1)}"
            else:
                embed_url = url
            
            if embed_url:
                log(f"[vk.com] Falling back to embed page: {embed_url}")
                e_resp = session.get(embed_url, timeout=15)
                hls_match = re.search(r'["\'](https?://[^\s"\'<>!]+?\.m3u8[^\s"\'<>!]*?)["\']', e_resp.text)
                if hls_match:
                    formats.append({"url": hls_match.group(1).replace("\\/", "/"), "type": "hls", "priority": 100})

        if not formats:
            return None

        formats.sort(key=lambda x: x["priority"], reverse=True)
        best = formats[0]
        
        result = StreamInfo(
            url=best["url"],
            headers={"User-Agent": HEADERS["User-Agent"], "Referer": f"https://{domain}/", "Origin": f"https://{domain}"},
            cookies=session.cookies.get_dict(),
            manifest_type=best["type"]
        )
        _RESOLVER_CACHE[cache_key] = (now, result)
        return result
    except Exception as e:
        log_error(f"[vk.com] Error: {e}")
        return None


def extract_mail_ru_url_optimized(url, referer=None):
    """Optimized extractor for my.mail.ru."""
    log(f"[mail.ru] Extracting from: {url}")
    session = requests.Session()
    session.headers.update(HEADERS)
    if referer: session.headers["Referer"] = referer
    
    try:
        resp = session.get(url, timeout=15)
        meta_match = re.search(r'"metadataUrl"\s*:\s*"([^"]+)"', resp.text)
        if meta_match:
            meta_url = meta_match.group(1)
            if meta_url.startswith('//'): meta_url = 'https:' + meta_url
            meta_resp = session.get(meta_url, timeout=10)
            data = meta_resp.json()
            videos = data.get("videos", [])
            formats = []
            for v in videos:
                v_url = v.get("url")
                if v_url:
                    key = v.get("key", "0")
                    priority = int(key.replace("p", "")) if key.replace("p", "").isdigit() else 0
                    formats.append({"url": v_url, "type": "mp4", "priority": priority})
            
            if formats:
                formats.sort(key=lambda x: x["priority"], reverse=True)
                return StreamInfo(formats[0]["url"], headers={"User-Agent": HEADERS["User-Agent"], "Referer": "https://my.mail.ru/"})
    except: pass
    return None


def extract_filemoon_url_optimized(url, referer=None):
    """Optimized extractor for Filemoon."""
    try:
        resp = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": referer or "https://filemoon.to/"}, timeout=15)
        packed = re.search(r"(eval\(function\(p,a,c,k,e,.*?\)\s*;?)", resp.text, re.DOTALL)
        if packed:
            unpacked = js_unpack(packed.group(1))
            file_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', unpacked)
            if file_match:
                video_url = file_match.group(1).replace("\\/", "/")
                parsed = urllib.parse.urlparse(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                return StreamInfo(video_url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": origin + "/", "Origin": origin}, manifest_type="hls")
    except: pass
    return None


def extract_bysebuho_url(url, referer=None):
    """Extractor for Bysebuho."""
    try:
        resp = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": referer or "https://bysebuho.com/"}, timeout=15)
        packed = re.search(r"(eval\(function\(p,a,c,k,e,.*?\)\s*;?)", resp.text, re.DOTALL)
        if packed:
            unpacked = js_unpack(packed.group(1))
            file_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', unpacked)
            if file_match:
                return StreamInfo(file_match.group(1).replace("\\/", "/"), headers={"User-Agent": HEADERS["User-Agent"], "Referer": url}, manifest_type="hls")
    except: pass
    return None


def extract_hqq_url(url, referer=None):
    """Extractor for HQQ/Netu/Waaw/TVPenet."""
    try:
        resp = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": referer or "https://hqq.ac/"}, timeout=15)
        # Look for direct HLS or packed
        match = re.search(r'["\'](https?://[^\s"\'<>!]+?\.m3u8[^\s"\'<>!]*?)["\']', resp.text)
        if match:
            return StreamInfo(match.group(1).replace("\\/", "/"), headers={"User-Agent": HEADERS["User-Agent"], "Referer": url}, manifest_type="hls")
    except: pass
    return None


def extract_rumble_url(url):
    """Extractor for Rumble."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        cdn_match = re.search(r'["\'](https?://[^\s"\'<>!]+?(?:1a-1791\.com|rumble\.com)/video/[^\s"\'<>!]+?\.(?:m3u8|mp4|tarr)[^\s"\'<>!]*?)["\']', resp.text)
        if cdn_match:
            video_url = cdn_match.group(1).replace("\\/", "/")
            m_type = "hls" if ".m3u8" in video_url or "tarr" in video_url else "mp4"
            return StreamInfo(video_url, manifest_type=m_type)
    except: pass
    return None


def create_listitem_with_stream(stream_info, title=None):
    """Creates Kodi ListItem with correct headers, preventing duplication."""
    if not stream_info: return None
    
    list_item = xbmcgui.ListItem(title or "Video")
    list_item.setInfo("video", {"title": title or "Video"})

    base_url = stream_info.url
    url_headers = {}

    # 1. Cleanly separate base URL from any existing pipe-appended headers
    if "|" in base_url:
        parts = base_url.split("|", 1)
        base_url = parts[0]
        header_str = parts[1]
        for param in header_str.split("&"):
            if "=" in param:
                k, v = param.split("=", 1)
                url_headers[urllib.parse.unquote(k)] = urllib.parse.unquote(v)

    # 2. Unquote the base URL if necessary
    if not (base_url.startswith("https://") or base_url.startswith("http://")):
        base_url = urllib.parse.unquote(base_url)

    # 3. Determine if we use InputStream Adaptive
    is_strict_cdn = any(domain in base_url for domain in ["vk.com", "vkvideo.ru", "vkuser.net", "ok.ru", "okcdn.ru", "mail.ru", "hqq", "netu", "waaw", "tvpenet", "cfglobalcdn.com", "rumble.com", "1a-1791.com"])
    
    import xbmcaddon
    addon = xbmcaddon.Addon()
    use_isa = addon.getSetting("player_method") == "1"
    force_isa = use_isa and is_strict_cdn

    # 4. Merge headers from stream_info
    if stream_info.headers:
        for k, v in stream_info.headers.items():
            url_headers[k] = v

    if (stream_info.is_hls() or stream_info.is_dash()) and not is_strict_cdn or force_isa:
        list_item.setProperty("inputstream", "inputstream.adaptive")
        if not stream_info.is_mp4():
             list_item.setProperty("inputstream.adaptive.manifest_type", stream_info.manifest_type)
             
        if any(x in base_url for x in ["vkuser.net", "okcdn.ru", "cfglobalcdn.com"]) and base_url.startswith("https://"):
             base_url = base_url.replace("https://", "http://", 1)

        if "cfglobalcdn.com" in base_url and "/secip/" in base_url and "/silverlight/" not in base_url:
             base_url = base_url.replace("/secip/", "/silverlight/secip/", 1)

        if url_headers:
            for k, v in url_headers.items():
                list_item.setProperty(f"inputstream.adaptive.stream_headers", f"{k}={urllib.parse.quote(v)}")
        
        headers_keys = [k.lower() for k in url_headers.keys()]
        if is_strict_cdn and "referer" not in headers_keys:
             ref = "https://ok.ru/" if any(x in base_url for x in ["ok.ru", "okcdn.ru"]) else "https://vk.com/"
             if "hqq" in base_url or "tvpenet" in base_url or "cfglobalcdn.com" in base_url:
                 ref = "https://hqq.ac/"
             list_item.setProperty(f"inputstream.adaptive.stream_headers", f"Referer={urllib.parse.quote(ref)}")

        list_item.setPath(base_url)
        log_debug(f"[stream] ISA path set: {base_url[:100]}...")

    else:
        # Internal FFmpeg player with headers
        list_item.setProperty("VideoPlayer.UseFastSeek", "true")
        
        if any(x in base_url for x in ["vkuser.net", "okcdn.ru", "cfglobalcdn.com"]) and base_url.startswith("https://"):
             base_url = base_url.replace("https://", "http://", 1)
             
        if "cfglobalcdn.com" in base_url and "/secip/" in base_url and "/silverlight/" not in base_url:
             base_url = base_url.replace("/secip/", "/silverlight/secip/", 1)
        
        if "?" not in base_url and any(x in base_url for x in ["expires=", "cmd=", "slave[]=", "nochat=", "autoplay=", "id="]):
             base_url = re.sub(r'(\.[a-z]{2,4}/)(expires=|cmd=|nochat=|autoplay=|slave\[\]=|id=)', r'\1?\2', base_url)

        if "?" in base_url:
            base_url += "&timeout=30000000&rw_timeout=30000000"
        else:
            base_url += "?timeout=30000000&rw_timeout=30000000"

        if not url_headers.get("User-Agent"): url_headers["User-Agent"] = HEADERS["User-Agent"]
        
        if is_strict_cdn and not url_headers.get("Referer"):
            if any(x in base_url for x in ["vkuser.net", "vk.com", "vkvideo.ru"]):
                url_headers["Referer"] = "https://vk.com/"
            elif any(x in base_url for x in ["ok.ru", "okcdn.ru"]):
                url_headers["Referer"] = "https://ok.ru/"
            elif any(x in base_url for x in ["hqq", "tvpenet", "cfglobalcdn.com"]):
                url_headers["Referer"] = "https://hqq.ac/"

        header_str = urllib.parse.urlencode(url_headers)
        final_path = f"{base_url}|{header_str}"
        
        if stream_info.cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in stream_info.cookies.items()])
            final_path += "&Cookie=" + urllib.parse.quote(cookie_str)
            
        list_item.setPath(final_path)
        log_debug(f"[stream] FFmpeg path set: {final_path[:150]}...")

    return list_item


def resolve_url_wrapper(url, referer=None):
    """Main entry point for optimized resolution."""
    log(f"Resolving: {url.split('/')[2]}")
    
    if "ok.ru" in url or "odnoklassniki.ru" in url:
        return extract_ok_ru_url_optimized(url, referer=referer)
    if any(x in url for x in ["vk.com", "vkvideo.ru", "vk.me"]):
        return extract_vk_url_optimized(url, referer=referer)
    if "my.mail.ru" in url:
        return extract_mail_ru_url_optimized(url, referer=referer)
    if "filemoon" in url:
        return extract_filemoon_url_optimized(url, referer=referer)
    if "bysebuho" in url:
        return extract_bysebuho_url(url, referer=referer)
    if any(x in url for x in ["hqq", "netu", "waaw", "tvpenet", "cfglobalcdn.com"]):
        return extract_hqq_url(url, referer=referer)
    if "rumble.com" in url:
        return extract_rumble_url(url)
        
    m_type = "hls" if ".m3u8" in url else ("dash" if ".mpd" in url else "mp4")
    return StreamInfo(url, manifest_type=m_type)
