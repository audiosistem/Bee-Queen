# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import sys
import re
import hashlib
from datetime import datetime

import epg as epgmod
import utils
from utils import (
    log, log_debug, epg_key, addon_path,
    profile_path, read_json, write_json, write_text,
    http_get, get_setting_str,
)

import xbmc
import xbmcvfs

ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB_PATH = os.path.join(ADDON_ROOT, "resources", "lib")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)



BASE_URL = "https://rotv123.com"
DEFAULT_UA = get_setting_str("play_user_agent", "") or (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
)

def abs_url(u: str) -> str:
    if not u:
        return ""
    u = (u or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE_URL.rstrip("/") + u
    return BASE_URL.rstrip("/") + "/" + u

def _cat_cache_path(category_url: str) -> str:
    key = hashlib.md5(category_url.encode("utf-8", "ignore")).hexdigest()
    return profile_path("cache", f"epg_{key}.json", ensure=True)

def _serialize_slots(epg_map: dict) -> dict:
    out = {}
    for ch_id, slots in (epg_map or {}).items():
        if not isinstance(slots, dict):
            continue
        def ser(item):
            if not isinstance(item, dict) or not item:
                return None
            d = dict(item)
            for k in ("start", "stop"):
                v = d.get(k)
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            return d
        out[ch_id] = {"now": ser(slots.get("now")), "next": ser(slots.get("next"))}
    return out

def _fetch_category_channels(category_url: str) -> list[dict]:
    data = http_get(category_url, timeout=20, headers={"Referer": BASE_URL}, ua=DEFAULT_UA)
    if not data:
        return []
    try:
        html = data.decode("utf-8", errors="ignore")
    except Exception:
        html = ""
    blocks = re.findall(r'<a[^>]+class="[^"]*channel-card[^"]*"[^>]*>.*?</a>', html, re.IGNORECASE | re.DOTALL)
    if not blocks:
        blocks = re.findall(r'<div[^>]+class="[^"]*channel-card[^"]*"[^>]*>.*?</div>', html, re.IGNORECASE | re.DOTALL)

    channels = []
    for block in blocks:
        name_match = re.search(r'class="[^"]*channel-name[^"]*"[^>]*>\s*([^<]+)\s*<', block, re.IGNORECASE)
        if not name_match:
            continue
        channel_name = (name_match.group(1) or "").strip()
        channels.append({"name": channel_name})
    return channels

def _warm_category(category_url: str, id_tags: dict, xml_path: str) -> None:
    category_url = abs_url(category_url)
    channels = _fetch_category_channels(category_url)
    if not channels:
        return

    wanted = set()

    for ch in channels:
        tag = epg_key(ch.get("name") or "")
        epg_id = (id_tags.get(tag) or "").strip()
        if epg_id:
            wanted.add(epg_id)

    if not wanted:
        return

    epg_map = epgmod.get_now_next_bulk(xml_path, wanted)
    try:
        mtime = int(os.path.getmtime(xml_path))
    except Exception:
        mtime = 0

    payload = {
        "category_url": category_url,
        "epg_mtime": mtime,
        "generated_at": int(time.time()),
        "items": _serialize_slots(epg_map),
    }
    write_json(_cat_cache_path(category_url), payload)
    log_debug(f"Warm cache written for category ({len(wanted)} ids): {category_url}")

def _run_warmup() -> None:
    xml_path = epgmod.ensure_epg_cached("plugin.video.rotv123")
    if not xml_path:
        log("Warm-up skipped: no EPG cache available", xbmc.LOGWARNING)
        return

    id_tags = read_json(xbmcvfs.translatePath("special://home/addons/plugin.video.rotv123/id_tags.json"), default={})
    if not id_tags:
        try:
            id_tags = read_json(addon_path("id_tags.json"), default={})
        except Exception:
            id_tags = {}
    if not id_tags:
        return

    cats = read_json(profile_path("categories.json", ensure=True), default=[])
    if not isinstance(cats, list) or not cats:
        return

    current = ""
    try:
        current = xbmcvfs.File(profile_path("warmup.current", ensure=True)).read().strip()
    except Exception:
        current = ""

    urls = [abs_url(c.get("url","")) for c in cats if isinstance(c, dict)]
    urls = [u for u in urls if u]
    ordered = [u for u in urls if u != current] + ([current] if current and current in urls else [])

    for u in ordered:
        if xbmc.Monitor().abortRequested():
            return
        try:
            _warm_category(u, id_tags, xml_path)
        except Exception as e:
            log(f"Warm-up error for {u}: {e}", xbmc.LOGWARNING)

def main() -> None:
    mon = xbmc.Monitor()
    trigger_path = profile_path("warmup.trigger", ensure=True)
    last_seen = ""

    log_debug("Warm-up service started (idle until triggered).")

    while not mon.abortRequested():
        try:
            if xbmcvfs.exists(trigger_path):
                f = xbmcvfs.File(trigger_path)
                cur = (f.read() or "").strip()
                f.close()
            else:
                cur = ""
        except Exception:
            cur = ""

        if cur and cur != last_seen:
            last_seen = cur
            log_debug(f"Warm-up triggered ({cur})")
            try:
                _run_warmup()
            except Exception as e:
                log(f"Warm-up run failed: {e}", xbmc.LOGWARNING)

        if mon.waitForAbort(2):
            break

if __name__ == "__main__":
    main()
