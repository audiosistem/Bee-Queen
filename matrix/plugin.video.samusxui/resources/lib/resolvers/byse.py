"""Resolver Byse local, cu fluxul real al frontendului /e.

Tokenurile SprintCDN sunt legate de IP și User-Agent, deci rezolvarea trebuie
făcută pe același device care redă. Folosim primitivele ResolveURL pentru
ECDSA, PoW și AES-GCM, dar nu pluginul Byse upstream: acesta folosește contextul
HTTP vechi și profilul public TX6s/Chrome 137, detectat acum de anti-bot.
"""
import json
import os
import re
import threading
import time
import urllib.parse
from hashlib import sha256
from random import random

import requests
import xbmcaddon
import xbmcvfs
from resolveurl.lib import helpers
from resolveurl.lib.ecdsa import SigningKey, NIST256p
from resolveurl.plugins.byse import ByseResolver


UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) HeadlessChrome/148.0.0.0 Safari/537.36")
_CACHE_FILE = os.path.join(
    xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('profile')),
    'byse_cache.json',
)
_CACHE_LOCK = threading.Lock()
_CACHE_MAX_AGE = 900.0


def _cache_load():
    try:
        with open(_CACHE_FILE, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cache_get(key):
    now = time.time()
    with _CACHE_LOCK:
        entry = _cache_load().get(key) or {}
    if entry.get('url') and now < float(entry.get('expires', 0)):
        return entry['url']
    return None


def _stream_expiry(stream_url):
    """CDN-ul folosește s=issued-at și e=durată; păstrăm maximum 15 minute."""
    now = time.time()
    try:
        base = stream_url.partition('|')[0]
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(base).query)
        signed_expiry = float(query['s'][0]) + float(query['e'][0])
        return min(signed_expiry - 30.0, now + _CACHE_MAX_AGE)
    except Exception:
        return now + 600.0


def _cache_put(key, stream_url):
    now = time.time()
    with _CACHE_LOCK:
        data = {
            k: v for k, v in _cache_load().items()
            if isinstance(v, dict) and float(v.get('expires', 0)) > now
        }
        data[key] = {'url': stream_url, 'expires': _stream_expiry(stream_url)}
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        temporary = _CACHE_FILE + '.tmp'
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, separators=(',', ':'))
        os.replace(temporary, _CACHE_FILE)


def _b64(data):
    return helpers.b64urlencode(data, strip=True)


def _hash(value):
    return _b64(sha256(str(value).encode("ascii")).digest())


def _attestation(challenge):
    key = SigningKey.generate(curve=NIST256p, hashfunc=sha256)
    public = key.verifying_key.to_string()
    signature = key.sign(challenge["nonce"].encode(), hashfunc=sha256)
    return {
        "viewer_id": "", "device_id": "",
        "challenge_id": challenge["challenge_id"],
        "nonce": challenge["nonce"], "signature": _b64(signature),
        "public_key": {
            "crv": "P-256", "ext": True, "key_ops": ["verify"], "kty": "EC",
            "x": _b64(public[:32]), "y": _b64(public[32:]),
        },
        "client": {
            "user_agent": UA, "architecture": "x86", "bitness": "64",
            "platform": "Linux", "platform_version": "", "model": "",
            "ua_full_version": "148.0.7778.96",
            "brand_full_versions": [
                {"brand": "Not/A)Brand", "version": "99.0.0.0"},
                {"brand": "Chromium", "version": "148.0.7778.96"},
            ],
            "pixel_ratio": 1, "screen_width": 800, "screen_height": 600,
            "color_depth": 24, "languages": ["en-US"], "timezone": "Europe/Vienna",
            "hardware_concurrency": 8, "device_memory": 16, "touch_points": 0,
            "webgl_vendor": "Google Inc. (Google)",
            "webgl_renderer": ("ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device "
                               "(Subzero) (0x0000C0DE)), SwiftShader driver)"),
            "canvas_hash": _hash(random()), "audio_hash": _hash(random() + 1),
            "webgl_params_hash": _hash(random() + 2),
            "fonts_hash": _hash(random() + 3), "codecs_hash": _hash(random() + 4),
            "media_devices": "ai1ao1vi1", "pointer_type": "fine,hover",
            "extra": {"vendor": "Google Inc.",
                      "appVersion": UA.removeprefix("Mozilla/")},
        },
        "storage": {}, "attributes": {"entropy": "high"},
    }


def _json(response, stage):
    try:
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        body = (response.text or "<empty>").strip().replace("\n", " ")[:240]
        raise RuntimeError(
            "Byse {}: HTTP {} {}: {}".format(
                stage, response.status_code, response.url, body
            )
        ) from exc


def _gr_fast(data):
    """Hash-ul PoW Byse cu rundele expandate (identic cu ResolveURL, mult mai rapid)."""
    mask = 0xFFFFFFFF
    a, b, c, d = 1779033703, 3144134277, 1013904242, 2773480762

    def rounds(a, b, c, d):
        a = (a + b) & mask; x = d ^ a; d = ((x << 16) | (x >> 16)) & mask
        c = (c + d) & mask; x = b ^ c; b = ((x << 12) | (x >> 20)) & mask
        a = (a + b) & mask; x = d ^ a; d = ((x << 8) | (x >> 24)) & mask
        c = (c + d) & mask; x = b ^ c; b = ((x << 7) | (x >> 25)) & mask
        return a, b, c, d

    for value in data:
        a = (a + value) & mask
        a = ((a << 7) | (a >> 25)) & mask
        a, b, c, d = rounds(a, b, c, d)
    for _ in range(8):
        a, b, c, d = rounds(a, b, c, d)

    memory = [0] * 512
    for index in range(512):
        a, b, c, d = rounds(a, b, c, d)
        memory[index] = (a ^ c) & mask
    for _ in range(2):
        for index in range(512):
            current = memory[index]
            value = (current + memory[current & 511]) & mask
            value = ((value << 13) | (value >> 19)) & mask
            value ^= (memory[(index + 1) & 511] * 2654435761) & mask
            memory[index] = value & mask
            a = (a ^ value) & mask
            a, b, c, d = rounds(a, b, c, d)

    result = [0] * 8
    for index in range(8):
        a, b, c, d = rounds(a, b, c, d)
        value = a
        for offset in range(index * 64, index * 64 + 64):
            word = memory[offset]
            value = (value + word) & mask
            value = ((value << 5) | (value >> 27)) & mask
            value ^= (word * 2246822519) & mask
        result[index] = (value ^ c) & mask
    return result


def _leading_zero_bits(words):
    total = 0
    for word in words:
        if word == 0:
            total += 32
        else:
            return total + 32 - word.bit_length()
    return total


def _solve_pow(nonce, difficulty, timeout=45.0):
    import time
    if difficulty <= 0:
        return "0"
    deadline = time.monotonic() + timeout
    prefix = nonce + ":"
    candidate = 0
    while time.monotonic() < deadline:
        if _leading_zero_bits(_gr_fast((prefix + str(candidate)).encode("ascii"))) >= difficulty:
            return str(candidate)
        candidate += 1
    return None


def _solve_pow_remote(nonce, difficulty):
    """Delegă doar calculul PoW; challenge-ul și tokenurile rămân pe device."""
    from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS
    response = requests.get(
        "{}/byse/pow".format(THRAX_BASE),
        params={"nonce": nonce, "difficulty": difficulty},
        headers=THRAX_HEADERS, timeout=35,
    )
    return _json(response, "PoW Thrax").get("solution")


def resolve(embed_url):
    match = re.search(r"https?://([^/]+)/(?:e|d|download)/([0-9A-Za-z]+)", embed_url)
    if not match:
        raise ValueError("URL Byse necunoscut: {}".format(embed_url))
    host, media_id = match.groups()
    cache_key = '{}:{}'.format(host.lower(), media_id)
    cached = _cache_get(cache_key)
    if cached:
        return cached
    root = "https://{}/".format(host)
    web_url = "{}e/{}".format(root, media_id)
    session = requests.Session()
    headers = {"User-Agent": UA, "Referer": web_url, "X-Embed-Parent": web_url}

    response = session.get(
        "{}api/videos/{}/embed/details".format(root, media_id),
        headers=headers, timeout=15,
    )
    embed = "embed/"
    if response.status_code == 404:
        embed = ""
        response = session.get(
            "{}api/videos/{}/details".format(root, media_id),
            headers=headers, timeout=15,
        )
    details = _json(response, "details")
    frame = details.get("embed_frame_url")
    if frame:
        root = frame[:frame.index("/", 8) + 1]
        headers["Referer"] = frame

    settings = _json(session.get(
        "{}api/videos/{}/{}settings".format(root, media_id, embed),
        headers=headers, timeout=15,
    ), "settings")
    if not settings.get("captcha_required"):
        raise RuntimeError("Byse: flux fără captcha neașteptat")

    access_headers = dict(headers)
    access_headers.pop("X-Embed-Parent", None)
    challenge = _json(session.post(
        "{}api/videos/access/challenge".format(root),
        headers=access_headers, timeout=15,
    ), "challenge")
    attest = _json(session.post(
        "{}api/videos/access/attest".format(root),
        headers=access_headers, json=_attestation(challenge), timeout=20,
    ), "attest")
    fingerprint = {key: attest[key] for key in
                   ("token", "viewer_id", "device_id", "confidence")}
    captcha = _json(session.post(
        "{}api/videos/{}/{}captcha".format(root, media_id, embed),
        headers=headers, json={"fingerprint": fingerprint}, timeout=15,
    ), "captcha")

    pow_resolver = ByseResolver()
    difficulty = int(captcha["pow_difficulty"])
    try:
        solution = _solve_pow_remote(captcha["pow_nonce"], difficulty)
    except Exception:
        # La difficulty 16, fallbackul local a fost măsurat: consumă 45 s și
        # aproape întotdeauna ratează. Nu dublăm timeoutul; încercăm altă sursă.
        if difficulty > 12:
            raise
        solution = _solve_pow(captcha["pow_nonce"], difficulty, timeout=20.0)
    if solution is None:
        raise RuntimeError("Byse: PoW nu a fost rezolvat în 45 s")
    verify = _json(session.post(
        "{}api/videos/{}/{}captcha/verify".format(root, media_id, embed),
        headers=headers,
        json={"pow_token": captcha["pow_token"], "solution": solution,
              "fingerprint": fingerprint}, timeout=15,
    ), "captcha/verify")
    headers["X-Captcha-Token"] = verify["token"]
    playback = _json(session.post(
        "{}api/videos/{}/{}playback".format(root, media_id, embed),
        headers=headers, json={"fingerprint": fingerprint}, timeout=15,
    ), "playback")

    sources = playback.get("sources")
    if not sources and playback.get("playback"):
        encrypted = playback["playback"]
        from resolveurl.lib.aesgcm import python_aesgcm
        iv = pow_resolver.ft(encrypted["iv"])
        key = pow_resolver.xn(encrypted["key_parts"], encrypted.get("version"))
        payload = pow_resolver.ft(encrypted["payload"])
        cipher = python_aesgcm.new(key)
        decoded = cipher.open(iv, payload)
        sources = json.loads(decoded.decode("latin-1")).get("sources")
    if not sources:
        raise RuntimeError("Byse: playback fără surse")

    def quality(source):
        found = re.search(r"(\d{3,4})", str(source.get("label", "")))
        return int(found.group(1)) if found else int(source.get("height", 0) or 0)

    url = max(sources, key=quality).get("url")
    if url.startswith("/"):
        url = root.rstrip("/") + url
    stream_url = "{}|User-Agent={}".format(url, UA)
    _cache_put(cache_key, stream_url)
    return stream_url
