import re
import json
import base64
import os
import requests
import urllib.parse
from urllib.parse import urlparse

BASE = "https://filmehd.org"
AJAX = f"{BASE}/ajax/ajax.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
}


def _get(url, referer=None):
    h = dict(HEADERS)
    if referer:
        h["Referer"] = referer
    return requests.get(url, headers=h, timeout=15).text


def _parse_cards(html):
    items = []
    for block in re.split(r'<div class="film-inner">', html)[1:]:
        href_m  = re.search(r'href="(https://filmehd\.org/(?:film|serial)/[^"]+)"', block)
        img_m   = re.search(r'<img[^>]+src="([^"]+)"', block)
        title_m = re.search(r'class="film-name"[^>]*>([^<]+)</a>', block)
        year_m  = re.search(r'<span class="dot">(\d{4})</span>', block)
        if not (href_m and title_m):
            continue
        href = href_m.group(1)
        items.append({
            "url":       href,
            "title":     title_m.group(1).strip(),
            "poster":    img_m.group(1) if img_m else "",
            "year":      year_m.group(1) if year_m else "",
            "is_serial": "/serial/" in href,
        })
    return items


def _next_page_url(html, current_url):
    active_m = re.search(r'page-item active[^>]*>.*?/page/(\d+)/', html, re.DOTALL)
    if not active_m:
        return None
    cur = int(active_m.group(1))
    last_m = re.search(r'title="Last Page".*?/page/(\d+)/', html, re.DOTALL)
    if not last_m or cur >= int(last_m.group(1)):
        return None
    return re.sub(r'/page/\d+/', f'/page/{cur + 1}/', current_url)


def list_items(url):
    html = _get(url)
    return _parse_cards(html), _next_page_url(html, url)


def search(query):
    url = f"{BASE}/search?keyword={urllib.parse.quote_plus(query)}"
    html = _get(url)
    return _parse_cards(html)


def _extract_json_ld(html, schema_type):
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(\{[^<]+\})</script>', html):
        try:
            d = json.loads(m.group(1))
            if d.get("@type") == schema_type:
                return d
        except Exception:
            pass
    return {}


def _parse_duration(iso):
    m = re.match(r"PT(\d+)M", iso or "")
    return int(m.group(1)) * 60 if m else None


def get_film_details(url):
    html = _get(url)
    playY_m = re.search(r"const playY = '([^']+)'", html)
    meta = (_extract_json_ld(html, "Movie")
            or _extract_json_ld(html, "TVEpisode")
            or {})
    return {
        "title":    meta.get("name", ""),
        "plot":     meta.get("description", ""),
        "poster":   meta.get("image", ""),
        "year":     (meta.get("datePublished") or "")[:4],
        "rating":   str((meta.get("aggregateRating") or {}).get("ratingValue", "")),
        "duration": _parse_duration(meta.get("duration")),
        "genres":   meta.get("genre", []),
        "playY":    playY_m.group(1) if playY_m else None,
    }


def get_serial_info(url):
    html = _get(url)
    meta = _extract_json_ld(html, "TVSeries") or {}
    # Each season has data-ss="N" data-id="TOKEN" in the season dropdown
    season_re = re.compile(r'data-ss="(\d+)"[^>]+data-id="([^"]+)"', re.DOTALL)
    seasons_by_num = {
        int(snum): f"{AJAX}?episode={token}"
        for snum, token in season_re.findall(html)
    }
    # Fallback: current_url for single-season serials without dropdown
    if not seasons_by_num:
        ep_url_m = re.search(
            r"const current_url = '(https://filmehd\.org/ajax/ajax\.php\?episode=[^']+)'",
            html
        )
        if ep_url_m:
            seasons_by_num = {1: ep_url_m.group(1)}
    return {
        "seasons_by_num": seasons_by_num,
        "n_seasons":      int(meta.get("numberOfSeasons") or len(seasons_by_num) or 1),
        "poster":         meta.get("image", ""),
        "plot":           meta.get("description", ""),
        "title":          meta.get("name", ""),
    }


def get_episodes(episode_url, serial_url=None):
    html = _get(episode_url, referer=serial_url)
    episodes = []
    for block in re.split(r'class="episode-item', html)[1:]:
        href_m   = re.search(r'href="([^"]+)"', block)
        season_m = re.search(r'data-season="(\d+)"', block)
        ep_m     = re.search(r'data-episode="(\d+)"', block)
        img_m    = re.search(r'<img[^>]+src="([^"]+)"', block)
        title_m  = re.search(r'<h3>([^<]+)</h3>', block)
        plot_m   = re.search(r'<p>([^<]+)</p>', block)
        if not (href_m and season_m and ep_m):
            continue
        href = href_m.group(1)
        if href.startswith("/"):
            href = BASE + href
        episodes.append({
            "url":     href,
            "season":  int(season_m.group(1)),
            "episode": int(ep_m.group(1)),
            "title":   title_m.group(1).strip() if title_m else "",
            "thumb":   img_m.group(1) if img_m else "",
            "plot":    plot_m.group(1).strip() if plot_m else "",
        })
    return episodes


def get_subtitles(embed_url):
    """Fetch subtitle tracks from sub.info param in embed URL. Returns list of {label, url}."""
    m = re.search(r'[?&]sub\.info=([^&]+)', embed_url)
    if not m:
        return []
    sub_info_url = urllib.parse.unquote(m.group(1))
    try:
        resp = requests.get(sub_info_url, headers=HEADERS, timeout=10)
        tracks = resp.json()
        return [{"label": t.get("label", "Sub"), "url": t["file"]}
                for t in tracks if t.get("file")]
    except Exception:
        return []


def get_players(playY, referer):
    param = "players_show" if "/episod/" in referer else "players"
    url = f"{AJAX}?{param}={urllib.parse.quote(playY, safe='')}"
    try:
        resp = requests.get(url, headers={**HEADERS, "Referer": referer}, timeout=15)
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _b64u_decode(s):
    s = s.replace('-', '+').replace('_', '/')
    return base64.b64decode(s + '==')


def _b64u_encode(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


    # ── Pure-Python P-256 ECDSA (fallback when cryptography unavailable) ──────
_P256_P  = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_P256_A  = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC
_P256_B  = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_P256_N  = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_P256_GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
_P256_GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5


def _p256_inv(a, n):
    lm, hm, low, high = 1, 0, a % n, n
    while low > 1:
        r = high // low
        lm, low, hm, high = hm - lm * r, high - low * r, lm, low
    return lm % n


def _p256_add(P1, P2):
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    x1, y1 = P1
    x2, y2 = P2
    if x1 == x2:
        if y1 != y2:
            return None
        m = (3 * x1 * x1 + _P256_A) * _p256_inv(2 * y1, _P256_P) % _P256_P
    else:
        m = (y2 - y1) * _p256_inv(x2 - x1, _P256_P) % _P256_P
    x3 = (m * m - x1 - x2) % _P256_P
    return (x3, (m * (x1 - x3) - y1) % _P256_P)


def _p256_mul(k, P):
    result, addend = None, P
    while k:
        if k & 1:
            result = _p256_add(result, addend)
        addend = _p256_add(addend, addend)
        k >>= 1
    return result


def _p256_sign(msg_bytes):
    """Sign msg_bytes with a fresh P-256 key. Returns (sig_raw_64, jwk_pub)."""
    import hashlib
    G = (_P256_GX, _P256_GY)
    while True:
        d = int.from_bytes(os.urandom(32), "big")
        if 1 <= d < _P256_N:
            break
    Q = _p256_mul(d, G)
    z = int.from_bytes(hashlib.sha256(msg_bytes).digest(), "big")
    while True:
        k = int.from_bytes(os.urandom(32), "big")
        if not (1 <= k < _P256_N):
            continue
        rx = _p256_mul(k, G)[0] % _P256_N
        if rx == 0:
            continue
        s = (_p256_inv(k, _P256_N) * (z + rx * d)) % _P256_N
        if s == 0:
            continue
        break
    sig = rx.to_bytes(32, "big") + s.to_bytes(32, "big")
    jwk = {
        "crv": "P-256", "ext": True, "key_ops": ["verify"], "kty": "EC",
        "x": _b64u_encode(Q[0].to_bytes(32, "big")),
        "y": _b64u_encode(Q[1].to_bytes(32, "big")),
    }
    return sig, jwk


def get_byse_stream(embed_url, film_referer):
    """ECDSA challenge/attest flow → AES-256-GCM decrypt → HLS URL.
    Returns (stream_url, error_msg). stream_url is None on failure."""
    # Try cryptography first; fall back to pure-Python P-256
    _use_crypto = False
    try:
        from cryptography.hazmat.primitives.asymmetric import ec as _ec
        from cryptography.hazmat.primitives import hashes as _hashes
        from cryptography.hazmat.backends import default_backend as _backend
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature as _dss_decode
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
        _use_crypto = True
    except Exception:
        pass
    if not _use_crypto:
        # AES-GCM via resolveurl's pure Python implementation
        try:
            import sys as _sys
            import xbmcaddon as _xa
            _ru_path = _xa.Addon("script.module.resolveurl").getAddonInfo("path")
            if _ru_path not in _sys.path:
                _sys.path.insert(0, _ru_path + "/lib")
            from resolveurl.lib.aesgcm import python_aesgcm as _aesgcm_mod
        except Exception as e:
            return None, f"no crypto backend: {e}"

    m = re.search(r'(https://[^/]+)/e/([^/?#]+)', embed_url)
    if not m:
        return None, "not a byse url"
    byse_base = m.group(1)
    media_id = m.group(2)
    embed_domain = urlparse(film_referer).netloc

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
    session = requests.Session()
    session.headers.update({"User-Agent": ua, "Accept": "*/*", "Accept-Language": "ro-RO,ro;q=0.9"})

    embed_headers = {
        "Referer": embed_url,
        "x-embed-origin": embed_domain,
        "x-embed-parent": embed_url,
        "x-embed-referer": film_referer,
    }

    try:
        session.get(f"{byse_base}/api/videos/{media_id}/embed/details",
                    headers=embed_headers, timeout=15)
    except Exception:
        pass

    try:
        cr = session.post(
            f"{byse_base}/api/videos/access/challenge",
            headers={"Referer": embed_url, "Origin": byse_base, "Content-Length": "0"},
            timeout=15,
        )
        challenge = cr.json()
    except Exception as e:
        return None, f"challenge: {e}"

    challenge_id = challenge.get("challenge_id")
    nonce = challenge.get("nonce")
    viewer_id = challenge.get("viewer_hint") or os.urandom(16).hex()
    if not (challenge_id and nonce):
        return None, f"challenge fields missing: {challenge}"

    device_id = os.urandom(16).hex()

    # Sign nonce with ECDSA P-256
    if _use_crypto:
        private_key = _ec.generate_private_key(_ec.SECP256R1(), _backend())
        sig_der = private_key.sign(nonce.encode("utf-8"), _ec.ECDSA(_hashes.SHA256()))
        r_val, s_val = _dss_decode(sig_der)
        signature = _b64u_encode(r_val.to_bytes(32, "big") + s_val.to_bytes(32, "big"))
        pub_nums = private_key.public_key().public_numbers()
        jwk = {
            "crv": "P-256", "ext": True, "key_ops": ["verify"], "kty": "EC",
            "x": _b64u_encode(pub_nums.x.to_bytes(32, "big")),
            "y": _b64u_encode(pub_nums.y.to_bytes(32, "big")),
        }
    else:
        sig_raw, jwk = _p256_sign(nonce.encode("utf-8"))
        signature = _b64u_encode(sig_raw)

    attest_body = {
        "viewer_id": viewer_id, "device_id": device_id,
        "challenge_id": challenge_id, "nonce": nonce,
        "signature": signature, "public_key": jwk,
        "client": {
            "user_agent": ua, "architecture": "x86", "bitness": "64",
            "platform": "Windows", "platform_version": "10.0.0", "model": "",
            "ua_full_version": "122.0.0.0",
            "brand_full_versions": [
                {"brand": "Chromium", "version": "122.0.0.0"},
                {"brand": "Not.A/Brand", "version": "24.0.0.0"},
            ],
            "pixel_ratio": 1, "screen_width": 1920, "screen_height": 1080,
            "color_depth": 24, "languages": ["ro-RO"], "timezone": "Europe/Bucharest",
            "hardware_concurrency": 8, "device_memory": 8, "touch_points": 0,
            "webgl_vendor": "Google Inc. (NVIDIA)",
            "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "canvas_hash": _b64u_encode(os.urandom(32)),
            "audio_hash": _b64u_encode(os.urandom(32)),
            "pointer_type": "fine,hover",
            "extra": {
                "vendor": "Google Inc.",
                "appVersion": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            },
        },
        "storage": {
            "cookie": viewer_id, "local_storage": viewer_id,
            "indexed_db": f"{viewer_id}:{device_id}",
            "cache_storage": f"{viewer_id}:{device_id}",
        },
        "attributes": {"entropy": "high"},
    }

    try:
        ar = session.post(
            f"{byse_base}/api/videos/access/attest",
            json=attest_body,
            headers={"Referer": embed_url, "Origin": byse_base,
                     "Content-Type": "application/json", "Accept": "*/*"},
            timeout=15,
        )
        attest = ar.json()
    except Exception as e:
        return None, f"attest: {e}"

    token = attest.get("token")
    confidence = attest.get("confidence", 0.6)
    final_viewer_id = attest.get("viewer_id", viewer_id)
    final_device_id = attest.get("device_id", device_id)
    if not token:
        return None, f"attest no token: {attest}"

    pb_body = {
        "fingerprint": {
            "token": token,
            "viewer_id": final_viewer_id,
            "device_id": final_device_id,
            "confidence": confidence,
        }
    }

    try:
        pr = session.post(
            f"{byse_base}/api/videos/{media_id}/embed/playback",
            json=pb_body,
            headers={**embed_headers, "Origin": byse_base, "Content-Type": "application/json"},
            timeout=15,
        )
        pb_data = pr.json()
    except Exception as e:
        return None, f"playback: {e}"

    # Direct sources (unencrypted path)
    sources = pb_data.get("sources", [])
    if sources:
        best = max(sources, key=lambda s: s.get("height", 0))
        return best.get("url") or None, "ok"

    pb = pb_data.get("playback", {})
    if not pb:
        return None, f"no playback/sources: {pb_data}"

    try:
        key = _b64u_decode(pb["key_parts"][0]) + _b64u_decode(pb["key_parts"][1])
        iv = _b64u_decode(pb["iv"])
        payload = _b64u_decode(pb["payload"])
        if _use_crypto:
            plaintext = _AESGCM(key).decrypt(iv, payload, None)
        else:
            cipher = _aesgcm_mod.new(key)
            plaintext = cipher.open(iv, payload)
        sources = json.loads(plaintext).get("sources", [])
        if not sources:
            return None, "no sources after decrypt"
        best = max(sources, key=lambda s: s.get("height", 0))
        return best.get("url") or None, "ok"
    except Exception as e:
        return None, f"decrypt: {e}"
