# -*- coding: utf-8 -*-
# epg.py
from __future__ import annotations

import os
import time
import io
import re
import gzip
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import xbmc
import xbmcvfs

try:
    from .utils import log, log_debug, profile_path, get_setting_str, get_setting_int
except ImportError:
    from utils import log, log_debug, profile_path, get_setting_str, get_setting_int


DEFAULT_EPG_SOURCE_GZ = "https://epgshare01.online/epgshare01/epg_ripper_RO1.xml.gz"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
    "Gecko/20100101 Firefox/115.0"
)

def _epg_source_url() -> str:
    return get_setting_str("epg_source_url", DEFAULT_EPG_SOURCE_GZ).strip() or DEFAULT_EPG_SOURCE_GZ

def _ttl_seconds() -> int:
    hours = get_setting_int("epg_cache_ttl_hours", 24)
    if hours <= 0:
        hours = 24
    return int(hours) * 3600

def _timeout() -> int:
    t = get_setting_int("epg_download_timeout", 25)
    if t <= 0:
        t = 25
    return t

def _cache_names_from_url(url: str) -> tuple[str, str]:
    base = os.path.basename(url.split("?")[0].strip("/")) or "epg.xml.gz"
    if base.endswith(".gz"):
        xml_name = base[:-3]
    else:
        xml_name = base
    if not xml_name.endswith(".xml"):
        xml_name = xml_name + ".xml"
    meta_name = xml_name + ".meta"
    return xml_name, meta_name

def _cache_paths(addon_id: str, source_url: str) -> tuple[str, str]:
    xml_name, meta_name = _cache_names_from_url(source_url)
    xml_path = profile_path(xml_name, ensure=True)
    meta_path = profile_path(meta_name, ensure=True)
    return xml_path, meta_path

def _http_get(url: str, timeout: int = 25, ua: str = DEFAULT_UA) -> bytes | None:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", ua)
    req.add_header("Accept-Encoding", "gzip")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            return data
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        log(f"EPG download failed: {e}", xbmc.LOGWARNING)
    except Exception as e:
        log(f"EPG download error: {e}", xbmc.LOGWARNING)
    return None

def _read_meta(meta_path: str) -> dict:
    try:
        if xbmcvfs.exists(meta_path):
            f = xbmcvfs.File(meta_path)
            raw = f.read()
            f.close()
            d = {}
            for line in (raw or "").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.strip()
            return d
    except Exception:
        pass
    return {}

def _write_meta(meta_path: str, **kv) -> None:
    try:
        lines = [f"{k}={v}" for k, v in kv.items()]
        f = xbmcvfs.File(meta_path, "w")
        f.write("\n".join(lines))
        f.close()
    except Exception:
        pass

def ensure_epg_cached(addon_id: str, force: bool = False) -> str | None:
    url = _epg_source_url()
    ttl = _ttl_seconds()
    xml_path, meta_path = _cache_paths(addon_id, url)

    now = int(time.time())
    meta = _read_meta(meta_path)
    last_ts = int(meta.get("ts", "0") or "0")

    if (not force) and xbmcvfs.exists(xml_path) and last_ts and (now - last_ts) < ttl:
        return xml_path

    log_debug(f"EPG cache refresh: force={force} last={last_ts} ttl={ttl} url={url}")
    data = _http_get(url, timeout=_timeout(), ua=get_setting_str("play_user_agent", DEFAULT_UA) or DEFAULT_UA)
    if not data:
        if xbmcvfs.exists(xml_path):
            return xml_path
        return None

    out = data
    if url.lower().endswith(".gz"):
        try:
            out = gzip.decompress(data)
        except Exception:
            out = data

    try:
        f = xbmcvfs.File(xml_path, "w")
        try:
            f.write(out.decode("utf-8", errors="ignore"))
        except Exception:
            f.write(out)
        f.close()
        _write_meta(meta_path, ts=str(now), source=url)
        return xml_path
    except Exception as e:
        log(f"EPG write failed: {e}", xbmc.LOGWARNING)
        return None

def _parse_xmltv_time(ts: str) -> datetime | None:
    if not ts:
        return None
    ts = ts.strip()

    dt_part = ts[:14]
    try:
        base = datetime.strptime(dt_part, "%Y%m%d%H%M%S")
    except Exception:
        return None

    m = re.search(r"([+-])(\d{2})(\d{2})", ts[14:])
    if m:
        sign = 1 if m.group(1) == "+" else -1
        hours = int(m.group(2))
        mins = int(m.group(3))
        tzinfo = timezone(sign * timedelta(hours=hours, minutes=mins))
    else:
        tzinfo = datetime.now().astimezone().tzinfo

    try:
        return base.replace(tzinfo=tzinfo).astimezone()
    except Exception:
        return None


def get_now_next(xml_path: str, channel_id: str) -> dict | None:
    bulk = get_now_next_bulk(xml_path, {channel_id})
    return bulk.get(channel_id)

def get_now_next_bulk(xml_path: str, channel_ids: set[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not xml_path or not channel_ids:
        return result

    wanted = set(str(x) for x in channel_ids if x)
    if not wanted:
        return result

    now_dt = datetime.now().astimezone()

    try:
        context = ET.iterparse(xml_path, events=("start", "end"))
        current_prog = None

        for event, elem in context:
            if event == "start" and elem.tag == "programme":
                ch = elem.attrib.get("channel", "")
                if ch in wanted:
                    current_prog = {"channel": ch, "start": elem.attrib.get("start", ""), "stop": elem.attrib.get("stop", ""),
                                    "title": "", "desc": ""}
                else:
                    current_prog = None

            elif event == "end" and elem.tag == "programme":
                if current_prog:
                    ch = current_prog["channel"]
                    start = _parse_xmltv_time(current_prog.get("start") or "")
                    stop = _parse_xmltv_time(current_prog.get("stop") or "")

                    if start and stop:
                        slot = None
                        if start <= now_dt < stop:
                            slot = "now"
                        elif start > now_dt:
                            slot = "next"

                        if slot:
                            cur = result.get(ch, {"now": None, "next": None})
                            if slot == "now":
                                cur["now"] = {
                                    "title": current_prog.get("title") or "",
                                    "desc": current_prog.get("desc") or "",
                                    "start": start,
                                    "stop": stop,
                                }
                            else:
                                existing = cur.get("next")
                                if not existing:
                                    cur["next"] = {
                                        "title": current_prog.get("title") or "",
                                        "desc": current_prog.get("desc") or "",
                                        "start": start,
                                        "stop": stop,
                                    }
                            result[ch] = cur

                elem.clear()

            elif event == "end" and current_prog and elem.tag in ("title", "desc"):
                try:
                    txt = (elem.text or "").strip()
                except Exception:
                    txt = ""
                if elem.tag == "title":
                    current_prog["title"] = txt
                else:
                    current_prog["desc"] = txt
                elem.clear()

        return result
    except Exception as e:
        log(f"EPG parse error: {e}", xbmc.LOGWARNING)
        return {}
