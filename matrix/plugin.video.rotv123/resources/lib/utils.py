# -*- coding: utf-8 -*-
# utils.py
from __future__ import annotations

import os
import re
import json
import time
import urllib.request
import urllib.error
import http.cookiejar

import xbmc
import xbmcaddon
import xbmcvfs

def log(msg: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[rotv123] {msg}", level)

def addon() -> xbmcaddon.Addon:
    return xbmcaddon.Addon()

def addon_id() -> str:
    return addon().getAddonInfo("id")


def get_setting_bool(key: str, default: bool = False) -> bool:
    try:
        v = addon().getSettingBool(key)
        return bool(v)
    except Exception:
        try:
            s = addon().getSetting(key)
            return (s or "").lower() in ("1","true","yes","on")
        except Exception:
            return default

def get_setting_int(key: str, default: int = 0) -> int:
    try:
        return int(addon().getSettingInt(key))
    except Exception:
        try:
            return int(addon().getSetting(key) or default)
        except Exception:
            return default

def get_setting_str(key: str, default: str = "") -> str:
    try:
        v = addon().getSettingString(key)
        return v if v is not None and v != "" else default
    except Exception:
        try:
            v = addon().getSetting(key)
            return v if v is not None and v != "" else default
        except Exception:
            return default

def log_debug(msg: str) -> None:
    if get_setting_bool("enable_debug_log", False):
        log(msg, xbmc.LOGDEBUG)

def addon_path(*parts: str) -> str:
    base = addon().getAddonInfo("path")
    return os.path.join(base, *parts)

def profile_path(*parts: str, ensure: bool = True) -> str:
    base = xbmcvfs.translatePath(f"special://profile/addon_data/{addon_id()}/")
    if ensure and not xbmcvfs.exists(base):
        xbmcvfs.mkdirs(base)
    return os.path.join(base, *parts)

def read_text(path: str, default: str = "") -> str:
    try:
        if not xbmcvfs.exists(path):
            return default
        f = xbmcvfs.File(path)
        try:
            return f.read() or default
        finally:
            f.close()
    except Exception as e:
        log(f"read_text failed for {path}: {e}", xbmc.LOGWARNING)
        return default

def write_text(path: str, text: str) -> bool:
    try:
        parent = os.path.dirname(path)
        if parent and not xbmcvfs.exists(parent):
            xbmcvfs.mkdirs(parent)

        f = xbmcvfs.File(path, "w")
        try:
            f.write(text)
        finally:
            f.close()
        return True
    except Exception as e:
        log(f"write_text failed for {path}: {e}", xbmc.LOGWARNING)
        return False

def read_json(path: str, default: dict | list | None = None):
    default = {} if default is None else default
    raw = read_text(path, default="")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception as e:
        log(f"read_json invalid json in {path}: {e}", xbmc.LOGWARNING)
        return default

def write_json(path: str, obj) -> bool:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
        return write_text(path, text)
    except Exception as e:
        log(f"write_json failed for {path}: {e}", xbmc.LOGWARNING)
        return False

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
    "Gecko/20100101 Firefox/115.0"
)

_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_COOKIE_JAR))



def http_open(
    url: str,
    timeout: int = 20,
    headers: dict | None = None,
    ua: str = DEFAULT_UA,
):

    headers = headers or {}
    req = urllib.request.Request(url)
    req.add_header("User-Agent", ua)
    for k, v in headers.items():
        req.add_header(str(k), str(v))
    return _OPENER.open(req, timeout=timeout)

def http_get(
    url: str,
    timeout: int = 20,
    headers: dict | None = None,
    ua: str = DEFAULT_UA,
) -> bytes | None:
    try:
        with http_open(url, timeout=timeout, headers=headers, ua=ua) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        log(f"http_get HTTPError {e.code} for {url}", xbmc.LOGWARNING)
        return None
    except Exception as e:
        log(f"http_get failed for {url}: {e}", xbmc.LOGWARNING)
        return None

def http_resolve_final_url(
    url: str,
    timeout: int = 20,
    headers: dict | None = None,
    ua: str = DEFAULT_UA,
) -> str | None:

    try:
        with http_open(url, timeout=timeout, headers=headers, ua=ua) as r:
            _ = r.read(256)
            return r.geturl()
    except Exception as e:
        log(f"http_resolve_final_url failed for {url}: {e}", xbmc.LOGWARNING)
        return None


def http_get_text(
    url: str,
    timeout: int = 20,
    headers: dict | None = None,
    ua: str = DEFAULT_UA,
    encoding: str = "utf-8",
) -> str | None:
    data = http_get(url, timeout=timeout, headers=headers, ua=ua)
    if data is None:
        return None
    return data.decode(encoding, errors="ignore")

_DIACRITICS_MAP = str.maketrans({
    "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
    "Ă": "a", "Â": "a", "Î": "i", "Ș": "s", "Ş": "s", "Ț": "t", "Ţ": "t",
})

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

def epg_key(name: str) -> str:
    if not name:
        return ""
    s = name.strip().translate(_DIACRITICS_MAP).lower()
    s = _NON_ALNUM_RE.sub("", s)
    return s

def is_fresh(path: str, ttl_seconds: int) -> bool:
    try:
        if not xbmcvfs.exists(path):
            return False
        st = xbmcvfs.Stat(path)
        mtime = int(st.st_mtime())
        return (int(time.time()) - mtime) < int(ttl_seconds)
    except Exception:
        return False
