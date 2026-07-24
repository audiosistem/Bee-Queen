# -*- coding: utf-8 -*-
"""
ThraxTV EPG client — folosește API-ul propriu /livetv/epg/
"""
import json
import os
import time
import requests
from datetime import datetime

BASE_URL = "https://api.derzis.xyz/livetv/epg"
TIMEOUT = 5

_THRAX_KEY = "7d9f4987bcd1a2026e6a422931bd7dbff0060977d189f37fa5727d9288b4abbb"
# urllib3 din Kodi 25 / Python 3.14 are bug la decompresia zstd via SocketIO
# → forțăm gzip/deflate pentru a evita răspunsuri zstd
_HEADERS = {"Accept-Encoding": "gzip, deflate", "X-Thrax-Key": _THRAX_KEY}

# Cache în memorie pentru EPG now-next (TTL: 60 secunde)
_EPG_CACHE = {}
_EPG_TTL = 60

# Cache pe disc pentru EPG (TTL: 10 minute)
_EPG_DISC_TTL = 600


def _log(msg):
    try:
        import xbmc
        xbmc.log(f"[ThraxTV][EPG] {msg}", xbmc.LOGWARNING)
    except Exception:
        pass


def _profile_path() -> str:
    try:
        import xbmcvfs
        import xbmcaddon
        return xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
    except Exception:
        return "/tmp/thraxtvUI"


def _epg_disc_path(channel_id: str) -> str:
    import re
    safe = re.sub(r"[^\w\-]", "_", channel_id)
    profile = _profile_path()
    try:
        if not os.path.exists(profile):
            os.makedirs(profile)
    except Exception:
        pass
    return os.path.join(profile, f"cache_epg_{safe}.json")


def _epg_disc_read(channel_id: str):
    path = _epg_disc_path(channel_id)
    try:
        if not os.path.exists(path):
            return None, False
        if time.time() - os.path.getmtime(path) > _EPG_DISC_TTL:
            return None, False
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), True
    except Exception:
        return None, False


def _epg_disc_write(channel_id: str, data) -> None:
    path = _epg_disc_path(channel_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _ts_to_hhmm(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%H:%M")
    except Exception:
        return ""


def get_epg_now_next(channel_id, country="ro"):
    result = get_epg_now_next_ext(channel_id, country)
    if not result:
        return None, None
    return result.get("now_title", ""), result.get("next_title", "")


def get_epg_now_next_ext(channel_id, country="ro"):
    now_ts = time.time()

    # Cache memorie
    cached = _EPG_CACHE.get(channel_id)
    if cached and (now_ts - cached[0]) < _EPG_TTL:
        return cached[1]

    # Cache disc
    disc_data, disc_hit = _epg_disc_read(channel_id)
    if disc_hit:
        _EPG_CACHE[channel_id] = (now_ts, disc_data)
        return disc_data

    try:
        r = requests.get(f"{BASE_URL}/{channel_id}/now-next", timeout=TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
        data = r.json()

        now   = data.get("now")  or {}
        next_ = data.get("next") or {}
        progress = data.get("progress")

        now_title  = now.get("title",  "")
        next_title = next_.get("title", "")

        now_range = None
        if now.get("start") and now.get("stop"):
            now_range = "%s - %s" % (_ts_to_hhmm(now["start"]), _ts_to_hhmm(now["stop"]))
        elif now.get("start"):
            now_range = _ts_to_hhmm(now["start"])

        next_range = None
        if next_.get("start") and next_.get("stop"):
            next_range = "%s - %s" % (_ts_to_hhmm(next_["start"]), _ts_to_hhmm(next_["stop"]))
        elif next_.get("start"):
            next_range = _ts_to_hhmm(next_["start"])

        result = {
            "now_title":  now_title,
            "now_range":  now_range,
            "next_title": next_title,
            "next_range": next_range,
            "progress":   progress,
        }
        _EPG_CACHE[channel_id] = (now_ts, result)
        _epg_disc_write(channel_id, result)
        return result

    except Exception as e:
        _log("now-next error for %s: %s" % (channel_id, e))
        _epg_disc_write(channel_id, None)
        return None


def get_epg_day_schedule(channel_id, country="ro", date=None, hours=24):
    try:
        r = requests.get(
            "%s/%s/schedule" % (BASE_URL, channel_id),
            params={"hours": hours},
            timeout=10,
            headers=_HEADERS,
        )
        r.raise_for_status()
        data = r.json()
        programs = data.get("programs", [])
        return sorted(programs, key=lambda p: p.get("start", 0))
    except Exception as e:
        _log("schedule error for %s: %s" % (channel_id, e))
        return []
