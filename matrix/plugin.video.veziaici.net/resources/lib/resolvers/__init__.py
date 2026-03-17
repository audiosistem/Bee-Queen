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
    extract_ok_ru_url_optimized,
    extract_vk_url_optimized,
    extract_mail_ru_url_optimized,
    extract_filemoon_url_optimized,
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


def resolve_url_wrapper(url):
    """
    Main URL resolver wrapper that tries direct extraction first, then ResolveURL.
    Returns StreamInfo object for optimized playback of ok.ru and vk.com,
    or string URL for other platforms.
    """
    log(f"Resolving URL: {url.split('/')[2]}")

    is_ok_ru = any(domain in url for domain in ["ok.ru", "odnoklassniki.ru"])
    is_vk = any(domain in url for domain in ["vk.com", "vkvideo.ru", "vkontakte.ru"])
    is_mail_ru = "my.mail.ru" in url
    is_vidmoly = "vidmoly" in url
    is_filemoon = "filemoon" in url

    # Try OPTIMIZED extraction for ok.ru, vk.com, mail.ru (returns StreamInfo)
    if is_ok_ru:
        try:
            result = extract_ok_ru_url_optimized(url)
            if result:
                log(f"[ok.ru] Optimized extraction success: {result.manifest_type}")
                return result
        except Exception as e:
            log_warning(f"[ok.ru] Optimized extraction failed: {e}")

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

    if is_mail_ru:
        try:
            result = extract_mail_ru_url_optimized(url)
            if result:
                log(f"[mail.ru] Optimized extraction success: {result.manifest_type}")
                return result
        except Exception as e:
            log_warning(f"[mail.ru] Optimized extraction failed: {e}")
            log_debug(f"[mail.ru] Traceback: {traceback.format_exc()}")

    if is_vidmoly:
        try:
            result = extract_vidmoly_url(url)
            if result:
                return result
        except Exception as e:
            log_error(f"vidmoly extraction failed: {e}")

    if is_filemoon:
        try:
            result = extract_filemoon_url_optimized(url)
            if result:
                log(f"[filemoon] Optimized extraction success")
                return result
        except Exception as e:
            log_error(f"filemoon optimized extraction failed: {e}")

        # Fallback to legacy
        try:
            result = extract_filemoon_url(url)
            if result:
                log(f"[filemoon] Legacy extraction success")
                return StreamInfo(result, manifest_type="hls")
        except Exception as e:
            log_error(f"filemoon legacy extraction failed: {e}")

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


# Câmpuri scalare care indică prezența unui URL de stream în metadata
_OK_STREAM_FIELDS = [
    "hlsMasterPlaylistUrl",
    "hlsManifestUrl",
    "ondemandHls",
    "hls",
    "hlsManifest",
    "ondemandDash",
    "dash",
    "metadataWebmUrl",
    "metadataEmbedded",
    "mpd",
    # "videos" eliminat intentionat - lista poate fi non-goala dar fara URL-uri reale
]


def _okru_has_streams(meta):
    """Returnează True dacă metadata conține cel puțin un URL de stream real."""
    if not meta or not isinstance(meta, dict):
        return False
    
    # Câmpuri scalare în rădăcină
    if any(meta.get(f) for f in _OK_STREAM_FIELDS):
        return True
        
    # Lista videos în rădăcină
    videos = meta.get("videos")
    if isinstance(videos, list) and any(isinstance(v, dict) and v.get("url") for v in videos):
        return True
        
    # Verificăm în obiectul movie
    movie = meta.get("movie")
    if isinstance(movie, dict):
        if any(movie.get(f) for f in _OK_STREAM_FIELDS):
            return True
        movie_videos = movie.get("videos")
        if isinstance(movie_videos, list) and any(isinstance(v, dict) and v.get("url") for v in movie_videos):
            return True
            
    return False


def _okru_extract_flashvars(webpage):
    """
    Extrage flashvars din pagina ok.ru folosind html.unescape() și
    delimitatori de ghilimele în loc de regex nested {.+?}.
    Returnează dict flashvars sau {}.
    """
    # Strategie 1: localizăm exact div-ul cu data-module="OKVideo"
    for marker in ('data-module="OKVideo"', "data-module='OKVideo'"):
        okv_pos = webpage.find(marker)
        if okv_pos == -1:
            continue
        tag_start = webpage.rfind("<", 0, okv_pos)
        if tag_start == -1:
            continue
        chunk = webpage[tag_start : tag_start + 65536]
        opts_match = re.search(r'data-options="([^"]+)"', chunk)
        if not opts_match:
            opts_match = re.search(r"data-options='([^']+)'", chunk)
        if opts_match:
            try:
                player_data = json.loads(html.unescape(opts_match.group(1)))
                fv = player_data.get("flashvars", {})
                if fv:
                    log("[ok.ru] Flashvars găsite (legacy) via data-module OKVideo")
                    return fv
            except Exception as e:
                log_debug(f"[ok.ru] Legacy JSON parse eșuat (strategie 1): {e}")
        break

    # Strategie 2: orice data-options care conține flashvars
    for opts_match in re.finditer(r'data-options="([^"]+)"', webpage):
        try:
            player_data = json.loads(html.unescape(opts_match.group(1)))
            fv = player_data.get("flashvars", {})
            if fv and (fv.get("metadata") or fv.get("metadataUrl")):
                log("[ok.ru] Flashvars găsite (legacy) via fallback data-options")
                return fv
        except Exception:
            continue
    for opts_match in re.finditer(r"data-options='([^']+)'", webpage):
        try:
            player_data = json.loads(html.unescape(opts_match.group(1)))
            fv = player_data.get("flashvars", {})
            if fv and (fv.get("metadata") or fv.get("metadataUrl")):
                return fv
        except Exception:
            continue

    return {}


def _okru_fetch_metadata_url(flashvars, session):
    """
    Fetch metadata de la metadataUrl (POST). Returnează dict sau None.
    """
    metadata_url = flashvars.get("metadataUrl")
    if not metadata_url:
        return None
    try:
        metadata_url = urllib.parse.unquote(metadata_url)
        post_data = {}
        if flashvars.get("location"):
            post_data["st.location"] = flashvars["location"]
        log(f"[ok.ru] POST metadataUrl...")
        resp = session.post(
            metadata_url,
            data=post_data,  # dict → Content-Type corect
            headers=HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        meta = resp.json()
        log(f"[ok.ru] metadataUrl răspuns. Chei: {list(meta.keys())}")
        return meta
    except Exception as e:
        log_warning(f"[ok.ru] Eroare metadataUrl (legacy): {e}")
        return None



def _okru_build_vk_url(vk_movie, movie=None):
    """
    Construieste URL-ul VK din datele vkMovie sau movie.contentId.
    Returneaza URL string sau None.
    """
    if isinstance(vk_movie, dict):
        vk_id = vk_movie.get("id") or vk_movie.get("videoId")
        if vk_id:
            return f"https://vk.com/video{vk_id}"
        oid = vk_movie.get("oid") or vk_movie.get("owner_id")
        vid = vk_movie.get("vid") or vk_movie.get("video_id")
        if oid and vid:
            h = vk_movie.get("hash", "")
            if h:
                return f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash={h}"
            return f"https://vk.com/video{oid}_{vid}"
    elif isinstance(vk_movie, str) and vk_movie.startswith("http"):
        return vk_movie
    # Fallback: movie.contentId in format "-owner_vid"
    if isinstance(movie, dict):
        cid = movie.get("contentId")
        if cid and isinstance(cid, str) and re.match(r"^-?\d+_\d+$", str(cid)):
            return f"https://vk.com/video{cid}"
    return None


def extract_ok_ru_url(url):
    """Extract video URL from ok.ru embed page (legacy resolver)."""
    # Fix missing '?' before query parameters (e.g. nochat=1)
    url = re.sub(r'(\d+)(nochat=\d+|autoplay=\d+)', r'\1?\2', url)

    log(f"Extracting ok.ru URL: {url}")
    session = requests.Session()

    try:
        response = session.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        webpage = response.text
    except requests.exceptions.RequestException as e:
        log_error(f"Failed to fetch ok.ru page: {e}")
        return None

    # Verificăm erori explicite din player (regex fără [^>]+ catastrofic)
    if "vp_video_stub_txt" in webpage:
        error = re.search(
            r'class=["\']vp_video_stub_txt["\'][^>]*>\s*([^<]+?)\s*<', webpage
        )
        if error:
            log_error(f"ok.ru error: {error.group(1)}")
            return None

    # Extragem flashvars cu metoda robustă
    flashvars = _okru_extract_flashvars(webpage)
    if not flashvars:
        log_warning("No player data found")
        return None

    try:
        # Parsăm metadata inline dacă există
        metadata = None
        raw_meta = flashvars.get("metadata")
        if raw_meta and isinstance(raw_meta, str):
            try:
                metadata = json.loads(raw_meta)
                log(f"[ok.ru] Metadata inline (legacy). Chei: {list(metadata.keys())}")
            except Exception as e:
                log_debug(f"[ok.ru] Eroare parsare metadata inline (legacy): {e}")
        elif isinstance(raw_meta, dict):
            metadata = raw_meta

        # Dacă metadata inline nu are stream-uri, încercăm metadataUrl
        if not _okru_has_streams(metadata):
            full_meta = _okru_fetch_metadata_url(flashvars, session)
            if full_meta:
                metadata = full_meta

        if not metadata:
            log_warning("No metadata found")
            return None

        if "movie" not in metadata:
            log_warning("No movie data in metadata")
            return None

        movie = metadata["movie"]
        log(f"[ok.ru] Metadata keys (legacy): {list(metadata.keys())}")
        if isinstance(movie, dict):
            log(f"[ok.ru] Movie keys (legacy): {list(movie.keys())}")
        
        provider = metadata.get("provider", "")
        log(f"[ok.ru] Provider (legacy): {provider!r}")

        vk_movie = metadata.get("vkMovie")
        if vk_movie:
            log(f"[ok.ru] vkMovie (legacy): {str(vk_movie)[:300]}")

        if isinstance(metadata.get("videos"), list):
            vids = metadata["videos"]
            sample = vids[0] if vids else None
            log(f"[ok.ru] videos[0] sample (legacy): {str(sample)[:200]}")

        # Caz: YouTube embed
        if provider == "USER_YOUTUBE":
            youtube_url = movie.get("contentId")
            if youtube_url:
                log(f"YouTube embed detected: {youtube_url}")
                return youtube_url

        # Caz: video embedded de la VK (vkMovie prezent)
        if vk_movie:
            # Log structura vkMovie pentru debugging
            vk_keys = list(vk_movie.keys()) if isinstance(vk_movie, dict) else type(vk_movie).__name__
            log(f"[ok.ru] vkMovie chei disponibile (legacy): {vk_keys}")

            vk_url = _okru_build_vk_url(vk_movie, movie)
            if vk_url:
                log(f"[ok.ru] VK embed (legacy), incerc VK resolver: {vk_url}")
                try:
                    from resources.lib.resolvers.optimized import extract_vk_url_optimized
                    vk_res = extract_vk_url_optimized(vk_url)
                    if vk_res:
                        # Returnam URL-ul din StreamInfo
                        return vk_res.url if hasattr(vk_res, "url") else str(vk_res)
                    log_warning(f"[ok.ru] VK resolver esuat (legacy) pentru: {vk_url} — continui cu ok.ru direct")
                except Exception as vk_e:
                    log_warning(f"[ok.ru] VK resolver exceptie (legacy): {vk_e} — continui cu ok.ru direct")
            else:
                log_warning(f"[ok.ru] Nu am putut construi URL VK (legacy) din: {str(vk_movie)[:200]} — continui cu ok.ru direct")
            # Nu returnam None — cautam stream-uri direct din metadata ok.ru

        # Colectăm toate formatele
        formats = []

        # Stream fields (HLS/DASH)
        stream_fields = [
            ("hls", ["hlsManifestUrl", "ondemandHls", "hls", "hlsManifest", "masterHls", "playlistHls", "hlsMasterPlaylistUrl"]),
            ("dash", ["ondemandDash", "metadataWebmUrl", "dash", "dashManifest", "mpd"]),
        ]
        for m_type, fields in stream_fields:
            s_url = None
            for f in fields:
                if metadata.get(f):
                    s_url = metadata[f]
                    break
            if not s_url and isinstance(movie, dict):
                for f in fields:
                    if movie.get(f):
                        s_url = movie[f]
                        break
            if s_url:
                formats.append({
                    "url": s_url.replace("\\/", "/"),
                    "format_id": m_type,
                    "is_hls": m_type == "hls"
                })

        # Embedded DASH
        dash_embedded = metadata.get("metadataEmbedded") or (isinstance(movie, dict) and movie.get("metadataEmbedded"))
        if dash_embedded:
            formats.append({"url": dash_embedded, "format_id": "dash", "is_hls": False})

        # MP4 videos
        vids = metadata.get("videos") or (isinstance(movie, dict) and movie.get("videos"))
        for video in (vids or []):
            if not isinstance(video, dict): continue
            v_url = video.get("url")
            if v_url:
                formats.append({
                    "url": v_url.replace("\\/", "/"),
                    "format_id": video.get("name", "mp4"),
                    "width": int_or_none(video.get("width")),
                    "height": int_or_none(video.get("height")),
                    "is_hls": False
                })

        if not formats:
            # Fallback mobil (legacy)
            log("[ok.ru] No formats found (legacy), trying mobile fallback...")
            try:
                v_id = url.split("/")[-1].split("?")[0]
                m_res = session.get(f"https://m.ok.ru/video/{v_id}", timeout=10)
                m_match = re.search(r'data-video="(.+?)"', m_res.text)
                if m_match:
                    m_data = json.loads(html.unescape(m_match.group(1)))
                    m_src = m_data.get("videoSrc")
                    if m_src:
                        d_resp = session.head(m_src, allow_redirects=True, timeout=10)
                        formats.append({"url": d_resp.url, "format_id": "mobile", "is_hls": False, "width": 0, "height": 0})
            except: pass

        if not formats:
            if metadata.get("paymentInfo"):
                log_warning("Video is paid")
            else:
                log_warning("No formats found")
            return None

        def format_key(fmt):
            is_hls = fmt.get("is_hls", False) or ".m3u8" in fmt.get("url", "")
            quality = max(fmt.get("width") or 0, fmt.get("height") or 0)
            return (is_hls, quality)

        formats.sort(key=format_key, reverse=True)
        best_format = formats[0]

        log(f"Total formats: {len(formats)}, best: {best_format['format_id']}")
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": url,
        }

        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        page_content = response.text

        # Strategy 1: Find direct m3u8 link in page
        video_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', page_content)
        if video_match:
            video_url = video_match.group(1).replace("\\/", "/")
            log(f"Filemoon found URL (direct): {video_url[:100]}...")
            return video_url

        # Strategy 2: Look for iframe
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', page_content)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            # ... rest of iframe logic ...
            if iframe_url.startswith("//"): iframe_url = "https:" + iframe_url
            
            iframe_response = requests.get(iframe_url, headers=headers, timeout=15)
            # Search for file in iframe content
            file_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', iframe_response.text)
            if file_match:
                return file_match.group(1).replace("\\/", "/")

    except Exception as e:
        log_error(f"Filemoon extraction failed: {e}")

    return None

