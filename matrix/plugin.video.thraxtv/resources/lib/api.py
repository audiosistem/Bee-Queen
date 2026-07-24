# -*- coding: utf-8 -*-
"""
ThraxTV Kodi Add-on – LiveTV API client (derzis)
"""

from __future__ import annotations

import json
import os
import sqlite3 as _sqlite3
import time
import requests
from typing import Any, Dict, List, Optional

BASE_URL          = "https://api.derzis.xyz/livetv"
CATALOG_URL       = "https://api.derzis.xyz/livetv/catalog"
ROOT_URL          = "https://api.derzis.xyz"
PLAY_URL          = "https://api.derzis.xyz/livetv/play"
RADIO_STREAM_URL  = "https://api.derzis.xyz/radio/stream"
TIMEOUT           = 15
STREAM_TIMEOUT    = 25
STREAM_TEST_TIMEOUT = 6   # timeout test HTTP per sursă (fallback)
MAX_PAGES         = 200
TTL_RADIO         = 24 * 3600    # 24 ore

_THRAX_KEY        = "7d9f4987bcd1a2026e6a422931bd7dbff0060977d189f37fa5727d9288b4abbb"
_API_HEADERS      = {"X-Thrax-Key": _THRAX_KEY}

# TTL cache pe disc
TTL_CATEGORIES = 7 * 24 * 3600   # 7 zile
TTL_CHANNELS   = 24 * 3600       # 24 ore

_MEM: Dict[str, tuple] = {}
_MEM_TTL = 300  # 5 minute


# ───────────────────────── Logging ─────────────────────────

try:
    import xbmc
    import xbmcaddon
    import xbmcvfs

    def _profile_path() -> str:
        return xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))

    _DEBUG_CACHE = [None]  # list pentru a permite mutarea din closure

    def _is_debug() -> bool:
        if _DEBUG_CACHE[0] is None:
            try:
                _DEBUG_CACHE[0] = xbmcaddon.Addon().getSettingBool("debug_http")
            except Exception:
                _DEBUG_CACHE[0] = False
        return _DEBUG_CACHE[0]

    def _logd(msg: str) -> None:
        if _is_debug():
            xbmc.log(f"[ThraxTV][api] {msg}", xbmc.LOGDEBUG)

    def _logw(msg: str) -> None:
        xbmc.log(f"[ThraxTV][api] {msg}", xbmc.LOGINFO)

    def _loge(msg: str) -> None:
        xbmc.log(f"[ThraxTV][api][ERR] {msg}", xbmc.LOGERROR)

except Exception:
    def _profile_path() -> str:
        return "/tmp/thraxtvUI"

    def _is_debug() -> bool:
        return False

    def _logd(msg: str) -> None:
        pass

    def _logw(msg: str) -> None:
        pass

    def _loge(msg: str) -> None:
        pass


def _addon_path() -> str:
    try:
        return xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("path"))
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _category_icon(key: str) -> str:
    return os.path.join(_addon_path(), "resources", "icons", "logo", f"{key}.png")


def _category_poster(key: str) -> str:
    return os.path.join(_addon_path(), "resources", "icons", "poster", f"{key}.png")


# ───────────────────────── Cache pe disc (SQLite) ─────────────────────────

_DB: Optional[_sqlite3.Connection] = None


def _db_path() -> str:
    return os.path.join(_profile_path(), "cache.db")


def _get_db() -> _sqlite3.Connection:
    global _DB
    if _DB is not None:
        return _DB
    profile = _profile_path()
    try:
        if not os.path.exists(profile):
            os.makedirs(profile)
    except Exception:
        pass
    conn = _sqlite3.connect(_db_path(), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, data TEXT, ts REAL)"
    )
    conn.commit()
    _DB = conn
    return conn


def clear_cache() -> int:
    """Șterge toate înregistrările din cache și golește memoria.
    Returnează numărul de înregistrări șterse."""
    global _DB
    _MEM.clear()
    try:
        conn = _get_db()
        cur = conn.execute("DELETE FROM cache")
        conn.commit()
        return cur.rowcount
    except Exception:
        # fallback: șterge fișierul DB complet
        try:
            if _DB is not None:
                _DB.close()
                _DB = None
            os.remove(_db_path())
        except Exception:
            pass
        return 0


def _disc_read(key: str, ttl: int) -> Optional[Any]:
    try:
        row = _get_db().execute(
            "SELECT data, ts FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        data_str, ts = row
        if time.time() - ts > ttl:
            _logd(f"Cache EXPIRAT: {key}")
            return None
        _logd(f"Cache HIT: {key}")
        return json.loads(data_str)
    except Exception as e:
        _loge(f"_disc_read({key}) failed: {e!r}")
        return None


def _disc_write(key: str, data: Any) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, ts) VALUES (?, ?, ?)",
            (key, json.dumps(data, ensure_ascii=False), time.time()),
        )
        conn.commit()
        _logd(f"Cache SCRIS: {key}")
    except Exception as e:
        _loge(f"_disc_write({key}) failed: {e!r}")


# ───────────────────────── Cache în memorie ─────────────────────────

def _mem_get(key: str) -> Optional[Any]:
    entry = _MEM.get(key)
    if entry and (time.time() - entry[0]) < _MEM_TTL:
        _logd(f"Mem cache HIT: {key}")
        return entry[1]
    return None


def _mem_set(key: str, data: Any) -> None:
    if len(_MEM) > 100:
        cutoff = time.time() - _MEM_TTL
        expired = [k for k, v in _MEM.items() if v[0] < cutoff]
        for k in expired:
            del _MEM[k]
    _MEM[key] = (time.time(), data)


# ───────────────────────── HTTP helpers ─────────────────────────

def _url(path: str) -> str:
    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")


def _catalog_url(path: str) -> str:
    return CATALOG_URL.rstrip("/") + "/" + path.lstrip("/")


def _get(path: str, params: Optional[dict] = None, timeout: Optional[int] = None, base: str = "livetv") -> Any:
    if base == "root":
        full_url = ROOT_URL.rstrip("/") + "/" + path.lstrip("/")
    elif base == "livetv":
        full_url = _url(path)
    else:
        full_url = _catalog_url(path)
    _logd(f"GET {full_url} params={params}")
    r = requests.get(full_url, params=params, headers=_API_HEADERS, timeout=timeout or TIMEOUT)
    _logd(f"-> {r.status_code} {r.url}")
    r.raise_for_status()
    return r.json()


# ───────────────────────── Countries ─────────────────────────

def get_countries() -> List[dict]:
    cached = _mem_get("countries")
    if cached is not None:
        return cached
    disc = _disc_read("cache_countries.json", TTL_CHANNELS)
    if disc is not None:
        _mem_set("countries", disc)
        return disc
    try:
        data = _get("countries") or {}
        result = data.get("countries", []) or []
        _disc_write("cache_countries.json", result)
        _mem_set("countries", result)
        return result
    except Exception as e:
        _loge(f"get_countries failed: {e!r}")
        return []


# ───────────────────────── Radio ─────────────────────────

def get_radio_countries() -> List[dict]:
    cached = _mem_get("radio_countries")
    if cached is not None:
        return cached
    disc = _disc_read("cache_radio_countries.json", TTL_RADIO)
    if disc is not None:
        _mem_set("radio_countries", disc)
        return disc
    try:
        data = _get("radio/countries", base="root") or {}
        result = data.get("countries", []) or []
        _disc_write("cache_radio_countries.json", result)
        _mem_set("radio_countries", result)
        return result
    except Exception as e:
        _loge(f"get_radio_countries failed: {e!r}")
        return []


def get_radio_stations(country_code: str, page: int = 1, size: int = 100, q: str = "") -> tuple:
    """Returnează (items, meta) pentru posturile radio dintr-o țară. Nu e cache-uit
    pe disc (paginare + căutare variabilă) — doar TTL scurt în memorie per pagină."""
    mem_key = f"radio_stations_{country_code}_{page}_{size}_{q}"
    cached = _mem_get(mem_key)
    if cached is not None:
        return cached
    try:
        params = {"page": page, "size": size}
        if q:
            params["q"] = q
        data = _get(f"radio/stations/{country_code.lower()}", params=params, base="root") or {}
        result = (data.get("items", []) or [], data.get("meta", {}) or {})
        _mem_set(mem_key, result)
        return result
    except Exception as e:
        _loge(f"get_radio_stations({country_code}) failed: {e!r}")
        return [], {}


# ───────────────────────── Categories ─────────────────────────

def get_categories() -> List[dict]:
    cached = _mem_get("categories")
    if cached is not None:
        return cached
    disc = _disc_read("cache_categories.json", TTL_CATEGORIES)
    if disc is not None:
        _mem_set("categories", disc)
        return disc
    try:
        data = _get("categories") or {}
        cats = data.get("categories", []) or []
        out: List[dict] = []
        for c in cats:
            if not isinstance(c, dict):
                continue
            key = c.get("key", "")
            local_icon   = _category_icon(key)
            local_poster = _category_poster(key)
            icon   = local_icon   if os.path.exists(local_icon)   else c.get("icon", "")
            poster = local_poster if os.path.exists(local_poster) else c.get("poster", "")
            out.append({
                "id":     key,
                "key":    key,
                "name":   c.get("name", key),
                "icon":   icon,
                "poster": poster,
                "raw":    c,
            })
        _disc_write("cache_categories.json", out)
        _mem_set("categories", out)
        return out
    except Exception as e:
        _loge(f"get_categories failed: {e!r}")
        return []


# ───────────────────────── Catalog channels ─────────────────────────

def _fetch_catalog_channels(country_code: str) -> List[dict]:
    out: List[dict] = []
    cc = country_code.lower()
    for page in range(1, MAX_PAGES + 1):
        data = _get(f"{cc}/channels", params={"page": page}, base="catalog") or {}
        items = data.get("items") or []
        _logd(f"/catalog/{cc}/channels page={page} items={len(items)}")
        if not items:
            break
        for ch in items:
            if isinstance(ch, dict):
                if not ch.get("country"):
                    ch["country"] = cc
                out.append(_normalize_channel(ch))
        meta = data.get("meta") or {}
        total = meta.get("total", 0)
        size  = meta.get("size", 50)
        if len(out) >= total or (total > 0 and page >= -(-total // size)):
            break
    return out


def get_channels_by_country(country_code: str) -> List[dict]:
    mem_key = f"channels_{country_code}"
    cached = _mem_get(mem_key)
    if cached is not None:
        return cached

    disc_file = f"cache_channels_{country_code.lower()}.json"
    disc = _disc_read(disc_file, TTL_CHANNELS)
    if disc is not None:
        _mem_set(mem_key, disc)
        return disc

    try:
        result = _fetch_catalog_channels(country_code)
        _disc_write(disc_file, result)
        _mem_set(mem_key, result)
        return result
    except Exception as e:
        _loge(f"get_channels_by_country({country_code}) failed: {e!r}")
        return []


def get_channels_by_country_paged(country_code: str, page: int = 1, size: int = 20,
                                   category: Optional[str] = None) -> tuple:
    """Returnează (channels, total) pentru o singură pagină. Cache pe disc per pagină."""
    cc = country_code.lower()
    page = max(1, page)
    size = max(1, min(100, size))
    cat = (category or "").strip().lower() or None

    cat_suffix = f"_cat_{cat}" if cat else ""
    mem_key = f"channels_paged_{cc}_p{page}_s{size}{cat_suffix}"
    cached = _mem_get(mem_key)
    if cached is not None:
        return cached[0], cached[1]

    disc_file = f"cache_channels_{cc}_p{page}_s{size}{cat_suffix}.json"
    disc = _disc_read(disc_file, TTL_CHANNELS)
    if disc is not None:
        _mem_set(mem_key, disc)
        return disc[0], disc[1]

    try:
        params: Dict[str, Any] = {"page": page, "size": size}
        if cat:
            params["category"] = cat
        data = _get(f"{cc}/channels", params=params, base="catalog") or {}
        items = data.get("items") or []
        meta = data.get("meta") or {}
        total = meta.get("total", 0)

        channels = []
        for ch in items:
            if isinstance(ch, dict):
                if not ch.get("country"):
                    ch["country"] = cc
                channels.append(_normalize_channel(ch))

        result = [channels, total]
        _disc_write(disc_file, result)
        _mem_set(mem_key, result)
        return channels, total
    except Exception as e:
        _loge(f"get_channels_by_country_paged({country_code}, p={page}, s={size}, cat={cat}) failed: {e!r}")
        return [], 0


def prefetch_channels_page(country_code: str, page: int, size: int = 20,
                            category: Optional[str] = None) -> None:
    """Prefetch în background — scrie în disc cache fără să blocheze UI-ul."""
    try:
        get_channels_by_country_paged(country_code, page=page, size=size, category=category)
        _logd(f"prefetch OK: {country_code} p{page} s{size} cat={category}")
    except Exception as e:
        _loge(f"prefetch failed: {country_code} p{page} s{size} cat={category}: {e!r}")


def get_channels_by_category(category_key: str, country: Optional[str] = None) -> List[dict]:
    if not country:
        mem_key = f"channels_cat_{category_key}"
        cached = _mem_get(mem_key)
        if cached is not None:
            return cached
        try:
            out: List[dict] = []
            seen: set = set()
            for page in range(1, MAX_PAGES + 1):
                data = _get("channels", params={"category": category_key, "page": page}) or {}
                items = data.get("items") or []
                if not items:
                    break
                for ch in items:
                    cid = ch.get("id")
                    if cid and cid in seen:
                        continue
                    if cid:
                        seen.add(cid)
                    out.append(_normalize_channel(ch))
            _mem_set(mem_key, out)
            return out
        except Exception as e:
            _loge(f"get_channels_by_category({category_key}) failed: {e!r}")
            return []

    all_channels = get_channels_by_country(country)
    result = [
        ch for ch in all_channels
        if (ch.get("category") or "").lower() == category_key.lower()
    ]
    _logd(f"get_channels_by_category({category_key}, {country}) -> {len(result)} din cache local")
    return result


def search_channels(query: str, country: Optional[str] = None) -> List[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []

    if country:
        all_channels = get_channels_by_country(country)
        if all_channels:
            results = [
                ch for ch in all_channels
                if q in (ch.get("name") or "").lower()
                or q in (ch.get("title") or "").lower()
            ]
            _logw(f"search_channels query={q!r} country={country} -> {len(results)} din cache local")
            return results

    # Fallback: request la API
    params = {"q": q, "size": 100, "page": 1}
    if country:
        params["country"] = country
    try:
        data = _get("channels", params=params) or {}
        items = data.get("items") or []
        out = [_normalize_channel(ch) for ch in items if isinstance(ch, dict)]
        _logw(f"search_channels query={q!r} -> {len(out)} din API")
        return out
    except Exception as e:
        _loge(f"search_channels({q}) failed: {e!r}")
        return []


def _normalize_channel(ch: dict) -> dict:
    name = (ch.get("name") or ch.get("title") or "").strip()
    raw_cats = ch.get("categories") or ch.get("category") or []
    if isinstance(raw_cats, str):
        raw_cats = [raw_cats] if raw_cats else []
    elif not isinstance(raw_cats, list):
        raw_cats = []
    return {
        "id":         ch.get("id", ""),
        "name":       name,
        "title":      name,
        "logo":       ch.get("logo", "") or ch.get("icon", ""),
        "country":    (ch.get("country", "") or "").lower(),
        "category":   ch.get("category", "") or "",
        "categories": raw_cats,
        "providers":  ch.get("providers") if isinstance(ch.get("providers"), list) else [],
        "aliases":    ch.get("aliases") if isinstance(ch.get("aliases"), list) else [],
        "updated_at": ch.get("updated_at"),
        "raw":        ch,
    }


# ───────────────────────── Channel / Sources / Resolve ─────────────────────────

def get_channel(channel_id: str) -> Optional[dict]:
    mem_key = f"channel_{channel_id}"
    cached = _mem_get(mem_key)
    if cached is not None:
        return cached

    import re as _re
    safe_id   = _re.sub(r"[^\w\-]", "_", channel_id)
    disc_file = f"cache_channel_{safe_id}.json"
    disc = _disc_read(disc_file, TTL_CHANNELS)
    if disc is not None:
        _mem_set(mem_key, disc)
        return disc

    try:
        data = _get(f"channel/{channel_id}")
        if data:
            _disc_write(disc_file, data)
            _mem_set(mem_key, data)
        return data
    except Exception as e:
        _loge(f"get_channel({channel_id}) failed: {e!r}")
        return None


def get_sources(channel_id: str) -> List[dict]:
    try:
        data = get_channel(channel_id) or {}
        sources = data.get("sources") or []
        out: List[dict] = []
        for s in sources:
            if not isinstance(s, dict):
                continue
            out.append({
                "provider": s.get("provider") or "unknown",
                "url":      s.get("url") or "",
                "status":   s.get("status") or "",
                "quality":  s.get("quality") or "",
                "headers":  s.get("headers") if isinstance(s.get("headers"), dict) else {},
                "cid":      s.get("cid"),
                "resolve":  bool(s.get("resolve")),
                "raw":      s,
            })
        return out
    except Exception as e:
        _loge(f"get_sources({channel_id}) failed: {e!r}")
        return []


def resolve_source(channel_id: str, provider: str, source_cid: Optional[str] = None, meta: bool = True) -> Optional[dict]:
    try:
        params: Dict[str, Any] = {"provider": provider}
        if source_cid not in (None, "", "null"):
            params["source_cid"] = str(source_cid)
        if meta:
            params["meta"] = "true"
        return _get(f"stream/{channel_id}", params=params, timeout=STREAM_TIMEOUT)
    except Exception as e:
        _loge(f"resolve_source({channel_id}, {provider}, {source_cid}) failed: {e!r}")
        return None



_DEFAULT_TEST_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def _test_url(url: str, headers: Optional[Dict[str, str]] = None) -> bool:
    """Testează rapid dacă un URL stream este accesibil (HTTP 2xx)."""
    merged = {"User-Agent": _DEFAULT_TEST_UA}
    if headers:
        merged.update(headers)
    try:
        r = requests.get(url, timeout=STREAM_TEST_TIMEOUT, headers=merged, stream=True)
        r.close()
        return r.status_code in (200, 206)
    except Exception:
        return False


_STALKER_MAX_RETRIES = 3



def _stalker_get_config(portal_id: str) -> Optional[dict]:
    """Obține config portal (MAC aleatoriu + auth_token) de la server."""
    try:
        r = requests.get(
            f"{ROOT_URL}/livetv/stalker/config",
            params={"portal": portal_id},
            headers=_API_HEADERS,
            timeout=8,
        )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _stalker_resolve_local(portal_id: str, stream_id: str) -> Optional[str]:
    """Obține play_token direct de pe IP-ul Kodi, cu retry pe MAC diferit dacă stream-ul e 458."""
    import http.client as _http

    for attempt in range(_STALKER_MAX_RETRIES):
        cfg = _stalker_get_config(portal_id)
        if not cfg:
            return None

        host       = cfg.get("host", "")
        port       = int(cfg.get("port", 80))
        mac        = cfg.get("mac", "")
        auth_token = cfg.get("auth_token", "")

        try:
            conn = _http.HTTPConnection(host, port, timeout=10)
            conn.request("GET", (
                "/portal.php?action=create_link&type=itv&cmd=&series="
                "&forced_storage=undefined&disable_ad=0&download=0"
                "&force_ch_link_check=0&JsHttpRequest=1-xml"
            ), headers={
                "Cookie": f"mac={mac}; stb_lang=en; timezone=Europe%2FBucharest",
                "Authorization": f"Bearer {auth_token}",
                "X-User-Agent": "Model: MAG254; Link: WiFi",
            })
            data = json.loads(conn.getresponse().read())
            conn.close()
            play_token = data["js"]["cmd"].split("play_token=")[1].split("&")[0]
        except Exception:
            continue

        url = f"http://{host}:{port}/play/live.php?mac={mac}&stream={stream_id}&extension=ts&play_token={play_token}"

        # Testăm stream-ul — dacă e 458 (MAC fără acces), reîncercăm cu alt MAC
        if _test_url(url):
            _logw(f"_stalker_resolve_local: OK mac={mac} attempt={attempt+1}")
            return url
        _logw(f"_stalker_resolve_local: fail mac={mac} attempt={attempt+1}, retry")

    return None


def _try_one_source(channel_id: str, source: dict) -> Optional[dict]:
    """Rezolvă și testează o singură sursă. Returnează dict dacă OK, None dacă eșuează."""
    from resources.lib import vavoo_resolver as _vavoo

    if not isinstance(source, dict):
        return None
    if (source.get("status") or "").lower() == "red":
        return None

    provider      = source.get("provider") or "unknown"
    cid           = source.get("cid")
    resolve_flag  = bool(source.get("resolve"))
    src_headers   = source.get("headers") if isinstance(source.get("headers"), dict) else {}
    manifest_type = ""

    try:
        if provider == "vavoo" and resolve_flag:
            cid_str = str(cid).strip() if cid is not None else ""
            if not cid_str:
                return None
            url = _vavoo.resolve_vavoo(cid_str)
            if not url:
                _logw(f"_try_one_source: vavoo resolve eșuat cid={cid_str}")
                return None
            _logw(f"_try_one_source: vavoo OK cid={cid_str}")
            return {
                "url": url, "headers": {}, "provider": provider,
                "source_cid": cid, "source_quality": source.get("quality"),
                "source_status": source.get("status"),
            }

        elif provider == "daddylive" and resolve_flag:
            cid_str      = str(cid) if cid is not None else ""
            url          = "%s/%s?provider=daddylive&source_cid=%s" % (PLAY_URL, channel_id, cid_str)
            play_headers = {}

        elif provider == "rdslive":
            cid_str      = str(cid) if cid is not None else "0"
            url          = "%s/%s?provider=rdslive&source_cid=%s" % (PLAY_URL, channel_id, cid_str)
            play_headers = {}

        elif provider == "ytdlp" and resolve_flag:
            source_url = source.get("url") or ""
            local = resolve_ytdlp_local(source_url)
            if local is not None:
                play_headers = local.get("headers") or {}
                if local.get("mpd"):
                    _logw(f"_try_one_source: ytdlp local DASH OK cid={cid}")
                    return {
                        "url": None, "mpd": local["mpd"], "headers": play_headers,
                        "provider": provider, "source_cid": cid,
                        "source_quality": source.get("quality"),
                        "source_status": source.get("status"),
                    }
                url = local["url"]
                _logw(f"_try_one_source: ytdlp local HLS OK cid={cid}")
                return {
                    "url": url, "headers": play_headers, "provider": provider,
                    "source_cid": cid, "source_quality": source.get("quality"),
                    "source_status": source.get("status"),
                }
            _logw(f"_try_one_source: ytdlp local eșuat → fallback server cid={cid}")
            resolved = resolve_source(channel_id, provider=provider, source_cid=cid)
            if not isinstance(resolved, dict) or not resolved.get("url"):
                return None
            url          = resolved["url"]
            play_headers = resolved.get("headers") if isinstance(resolved.get("headers"), dict) else src_headers

        elif provider == "stalker" and resolve_flag:
            # Stalker: cheamă create_link direct de pe IP-ul Kodi (play_token IP-bound corect)
            # _stalker_resolve_local testează intern și reîncearcă cu alt MAC dacă e 458
            raw_url   = source.get("url") or ""
            portal_id = raw_url[len("stalker://"):].split("/")[0].strip() if raw_url.startswith("stalker://") else ""
            stream_id = str(cid).strip() if cid is not None else ""
            if not portal_id or not stream_id:
                return None
            url = _stalker_resolve_local(portal_id, stream_id)
            if not url:
                _logw(f"_try_one_source: stalker eșuat portal={portal_id} cid={stream_id} (toate MAC-urile)")
                return None
            _logw(f"_try_one_source: stalker OK portal={portal_id} cid={stream_id}")
            return {
                "url": url, "headers": {}, "provider": provider,
                "source_cid": cid, "source_quality": source.get("quality"),
                "source_status": source.get("status"),
            }

        elif resolve_flag:
            resolved = resolve_source(channel_id, provider=provider, source_cid=cid)
            if not isinstance(resolved, dict) or not resolved.get("url"):
                _logw(f"_try_one_source: resolve eșuat → {provider} cid={cid}")
                return None
            url           = resolved["url"]
            play_headers  = resolved.get("headers") if isinstance(resolved.get("headers"), dict) else src_headers
            manifest_type = resolved.get("manifest_type", "")

        else:
            url = source.get("url") or ""
            if not url:
                return None
            play_headers = src_headers

        if _test_url(url, play_headers):
            _logw(f"_try_one_source: OK → {provider} cid={cid}")
            return {
                "url": url, "headers": play_headers, "provider": provider,
                "manifest_type": manifest_type,
                "source_cid": cid, "source_quality": source.get("quality"),
                "source_status": source.get("status"),
            }
        else:
            _logw(f"_try_one_source: eșuat → {provider} cid={cid}")
            return None

    except Exception as exc:
        _loge(f"_try_one_source: excepție → {provider} cid={cid}: {exc!r}")
        return None


def find_working_stream(channel_id: str) -> Optional[dict]:
    """
    Testează toate sursele unui canal în paralel și returnează prima care răspunde OK.
    - Sursele cu status='red' sunt sărite.
    - Latența totală = timpul celui mai rapid stream funcțional (nu suma secvențială).
    - Thread-urile rămase continuă în background și sunt ignorate după ce câștigătorul e găsit.
    """
    import queue as _queue
    import threading as _threading

    ch      = get_channel(channel_id) or {}
    sources = [s for s in (ch.get("sources") or [])
               if isinstance(s, dict) and (s.get("status") or "").lower() != "red"]

    if not sources:
        _loge(f"find_working_stream: nicio sursă pentru {channel_id}")
        return None

    result_q: _queue.Queue = _queue.Queue()

    def _worker(src):
        try:
            result_q.put(_try_one_source(channel_id, src))
        except Exception as exc:
            _loge(f"find_working_stream worker: {exc!r}")
            result_q.put(None)

    for src in sources:
        _threading.Thread(target=_worker, args=(src,), daemon=True).start()

    for _ in range(len(sources)):
        r = result_q.get()
        if r is not None:
            _logw(f"find_working_stream: câștigător → {r.get('provider')} cid={r.get('source_cid')}")
            return r

    _loge(f"find_working_stream: nicio sursă funcțională pentru {channel_id}")
    return None


# ───────────────────────── Favorite ─────────────────────────

def _favorites_path() -> str:
    return os.path.join(_profile_path(), "favorites.json")


def get_favorites() -> List[str]:
    try:
        with open(_favorites_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def add_favorite(channel_id: str) -> bool:
    favs = get_favorites()
    if channel_id not in favs:
        favs.append(channel_id)
        try:
            with open(_favorites_path(), "w", encoding="utf-8") as f:
                json.dump(favs, f)
        except Exception as e:
            _loge(f"add_favorite({channel_id}) failed: {e!r}")
            return False
        return True
    return False


def remove_favorite(channel_id: str) -> bool:
    favs = get_favorites()
    if channel_id in favs:
        favs.remove(channel_id)
        try:
            with open(_favorites_path(), "w", encoding="utf-8") as f:
                json.dump(favs, f)
        except Exception as e:
            _loge(f"remove_favorite({channel_id}) failed: {e!r}")
            return False
        return True
    return False


def resolve_ytdlp_local(url: str) -> Optional[dict]:
    """
    Rezolvă un URL ytdlp local cu script.module.yt-dlp.
    Returnează None dacă rezolvarea eșuează (fallback la server).
    Rezultat posibil:
      {"url": str, "headers": dict}              — HLS / stream direct
      {"url": None, "mpd": str, "headers": dict} — DASH (video+audio separate)
    """
    try:
        from resources.lib import ytdlp_local
        return ytdlp_local.resolve(url)
    except Exception as e:
        _loge(f"resolve_ytdlp_local({url!r}) failed: {e!r}")
        return None


def get_channel_status_cached(channel_id: str) -> Optional[str]:
    """
    Returnează statusul general al canalului (green/orange/red) exclusiv din cache local.
    Nu face niciun apel API. Returnează None dacă datele nu sunt în cache.

    Logică: cel mai bun status disponibil dintre toate sursele.
      - cel puțin o sursă green  → "green"
      - cel puțin o sursă orange → "orange"
      - toate sursele red        → "red"
    """
    import re as _re_local

    data = _mem_get(f"channel_{channel_id}")
    if data is None:
        safe_id = _re_local.sub(r"[^\w\-]", "_", channel_id)
        data = _disc_read(f"cache_channel_{safe_id}.json", TTL_CHANNELS)
    if not data:
        return None

    sources  = data.get("sources") or []
    statuses = [
        (s.get("status") or "").lower()
        for s in sources
        if isinstance(s, dict) and s.get("status")
    ]
    if not statuses:
        return None
    if "green" in statuses:
        return "green"
    if "orange" in statuses:
        return "orange"
    if all(s == "red" for s in statuses):
        return "red"
    return None



def get_wc2026_schedule(days: int = 3) -> Optional[dict]:
    """Returnează meciurile CM 2026 cu canalele disponibile."""
    from datetime import datetime as _dt
    try:
        tz_offset = round((_dt.now() - _dt.utcnow()).total_seconds() / 3600)
    except Exception:
        tz_offset = 0
    cache_key = f"wc2026:{days}:{tz_offset}"
    cached = _mem_get(cache_key)
    if cached is not None:
        return cached
    try:
        data = _get("/wc2026/schedule", params={"days": days, "tz_offset": tz_offset}, base="root")
        _mem_set(cache_key, data)
        return data
    except Exception as e:
        _loge(f"get_wc2026_schedule: {e}")
        return None


def get_sports_schedule(hours: int = 6, country: Optional[str] = None, limit_per_sport: int = 50) -> Optional[dict]:
    """Returnează evenimentele sportive live/viitoare grupate pe tip de sport."""
    cache_key = f"sports_schedule:{hours}:{country or ''}:{limit_per_sport}"
    cached = _mem_get(cache_key)
    if cached is not None:
        return cached
    try:
        params: dict = {"hours": hours, "limit_per_sport": limit_per_sport}
        if country:
            params["country"] = country
        data = _get("sports/schedule", params=params)
        _mem_set(cache_key, data)
        return data
    except Exception as e:
        _loge(f"get_sports_schedule: {e}")
        return None
