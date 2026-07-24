# -*- coding: utf-8 -*-
# resources/lib/vavoo_resolver.py
#
# Hibrid resolver Vavoo (2026):
#   1. Semnătura Lokke se obține de la serverul ThraxTV (cached server-side)
#   2. Resolve-ul se face LOCAL din plugin → URL sunshine bound la IP-ul clientului
#   3. Clientul redă direct, fără proxy server
#
from __future__ import annotations

import time
import json
import requests
from typing import Any, Optional
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry

TIMEOUT          = 15
CHANNEL_TIMEOUT  = 12
VAVOO_PLAY_BASE  = "https://vavoo.to/vavoo-iptv/play"
RESOLVE_ENDPOINT = "https://vavoo.to/mediahubmx-resolve.json"
SIG_ENDPOINT     = "https://api.derzis.xyz/livetv/vavoo/sig"
_THRAX_KEY       = "7d9f4987bcd1a2026e6a422931bd7dbff0060977d189f37fa5727d9288b4abbb"


def _log(msg: str) -> None:
    try:
        import xbmc
        xbmc.log(f"[ThraxTV][vavoo] {msg}", xbmc.LOGWARNING)
    except Exception:
        pass


def _build_session():
    s = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=8, pool_maxsize=8)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


SESSION = _build_session()

# Cache local semnătură (TTL primit de la server)
_sig_cache: dict = {"sig": None, "ts": 0.0, "ttl": 240.0}


def get_auth_signature() -> Optional[str]:
    """Obține semnătura Lokke de la serverul ThraxTV (cached local)."""
    now = time.time()
    if _sig_cache["sig"] and (now - _sig_cache["ts"]) < _sig_cache["ttl"]:
        return _sig_cache["sig"]
    try:
        r = SESSION.get(SIG_ENDPOINT, timeout=TIMEOUT, headers={"X-Thrax-Key": _THRAX_KEY})
        r.raise_for_status()
        data = r.json()
        sig = data.get("sig")
        ttl = float(data.get("ttl", 240))
        if sig:
            _sig_cache["sig"] = sig
            _sig_cache["ts"]  = now
            _sig_cache["ttl"] = ttl * 0.9  # margine 10%
            _log(f"semnătură obținută, TTL={ttl}s")
        else:
            _log(f"semnătură lipsă în răspunsul serverului: {data!r}")
        return sig
    except Exception as e:
        _log(f"eroare la obținerea semnăturii de pe {SIG_ENDPOINT}: {e!r}")
        return None


def _post_vavoo(body: dict, sig: str) -> Any:
    """
    POST către RESOLVE_ENDPOINT via http.client (stdlib), ocolind requests/urllib3.
    Requests adaugă automat Accept-Encoding: zstd, iar urllib3 din Kodi 25 / Python 3.14
    are un bug la decompresia zstd. http.client nu trimite Accept-Encoding → server
    returnează JSON necomprimat.
    """
    import http.client
    import ssl
    import urllib.parse

    parsed  = urllib.parse.urlparse(RESOLVE_ENDPOINT)
    payload = json.dumps(body).encode("utf-8")
    hdrs = {
        "User-Agent":            "MediaHubMX/2",
        "Accept":                "application/json",
        "Content-Type":          "application/json; charset=utf-8",
        "Content-Length":        str(len(payload)),
        "mediahubmx-signature":  sig,
    }
    ctx  = ssl.create_default_context()
    conn = http.client.HTTPSConnection(parsed.netloc, timeout=CHANNEL_TIMEOUT, context=ctx)
    try:
        conn.request("POST", parsed.path or "/", body=payload, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        if resp.status >= 400:
            raise IOError(f"HTTP {resp.status} {resp.reason}: {data[:200]!r}")
        return json.loads(data)
    finally:
        conn.close()


def resolve_vavoo(cid: str) -> Optional[str]:
    """
    Rezolvă un canal vavoo după CID.
    Returnează URL-ul HLS sunshine bound la IP-ul clientului.
    """
    sig = get_auth_signature()
    if not sig:
        _log(f"resolve_vavoo({cid}): semnătură indisponibilă — verifică serverul ThraxTV")
        return None

    play_url = f"{VAVOO_PLAY_BASE}/{cid}"
    body = {"language": "de", "region": "AT", "url": play_url, "clientVersion": "3.0.2"}

    try:
        result = _post_vavoo(body, sig)
        _log(f"resolve_vavoo({cid}): răspuns primit")
        if isinstance(result, list) and result:
            url = result[0].get("url")
            if url:
                _log(f"resolve_vavoo({cid}): OK → {url[:60]}...")
                return url
            _log(f"resolve_vavoo({cid}): câmpul 'url' lipsă în rezultat: {result!r}")
        else:
            _log(f"resolve_vavoo({cid}): răspuns neașteptat: {result!r}")
    except Exception as e:
        _log(f"resolve_vavoo({cid}): excepție {e!r}")
    return None
