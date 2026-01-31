# -*- coding: utf-8 -*-
# default2.py
from __future__ import annotations

import sys
import re
import os
import urllib.parse
import time
import hashlib
import html as _html

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import datetime
from resources.lib import epg as epgmod  # noqa: E402
from resources.lib.utils import (
    http_resolve_final_url,
    log, http_get_text, addon_path, read_json, epg_key, addon_id,
    profile_path, write_json, write_text,

    get_setting_bool, get_setting_str, get_setting_int,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

ADDON = xbmcaddon.Addon()

def _(sid: int, fallback: str = "") -> str:
    try:
        s = ADDON.getLocalizedString(int(sid))
        return s if s else fallback
    except Exception:
        return fallback

def L_REFRESH_EPG() -> str: return _(30001, "Refresh EPG")
def L_EPG_REFRESHED() -> str: return _(30002, "EPG refreshed")
def L_EPG_REFRESH_FAILED() -> str: return _(30003, "EPG refresh failed")
def L_SETTINGS() -> str: return _(30004, "Settings")

def html_unescape(s):
    try:
        return _html.unescape(s or "")
    except Exception:
        return s or ""

URL = sys.argv[0]
HANDLE = int(sys.argv[1])

BASE_URL = "https://rotv123.com"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"

def build_url(query: dict) -> str:
    return URL + "?" + urllib.parse.urlencode(query)

def abs_url(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE_URL.rstrip("/") + u
    return BASE_URL.rstrip("/") + "/" + u

def get_proxy_image(original_url: str) -> str:
    if not original_url:
        return "DefaultVideo.png"
    u = original_url.split("|")[0].strip()
    if not u:
        return "DefaultVideo.png"
    if "DefaultVideo" in u:
        return u
    clean_url = u.replace("https://", "").replace("http://", "")
    return f"https://images.weserv.nl/?url={clean_url}&format=png&trim=10"

def set_dir_item(label: str, url: str, thumb: str = "", is_folder: bool = True, plot: str = "") -> None:
    li = xbmcgui.ListItem(label=label)
    li.setContentLookup(False)
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb, "poster": thumb})
    try:
        li.setArt({"fanart": addon_path("fanart.jpg")})
    except Exception:
        pass
    if plot:
        try:
            li.setInfo("video", {"plot": plot})
        except Exception:
            pass
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=li, isFolder=is_folder)

def _load_id_tags() -> dict:
    return read_json(addon_path("id_tags.json"), default={})

def format_epg_plot(epg_data: dict | None) -> str:
    if not epg_data:
        return "Ghid TV indisponibil"

    now = epg_data.get("now") if isinstance(epg_data, dict) else None
    nxt = epg_data.get("next") if isinstance(epg_data, dict) else None

    def fmt_line(item: dict | None) -> str:
        if not item:
            return "—"
        try:
            st = item["start"].astimezone().strftime("%H:%M")
            en = item["stop"].astimezone().strftime("%H:%M")
        except Exception:
            st, en = "??:??", "??:??"
        title = (item.get("title") or "").strip()
        return f"{st} - {en}  {title}".strip()

    lines = ["Acum:", fmt_line(now), "", "Urmează:", fmt_line(nxt)]
    return "\n".join(lines)

def _cat_cache_path(category_url: str) -> str:
    key = hashlib.md5(category_url.encode("utf-8", "ignore")).hexdigest()
    return profile_path("cache", f"epg_{key}.json", ensure=True)

def _load_cat_cache(category_url: str, xml_path: str) -> dict:
    try:
        cache_path = _cat_cache_path(category_url)
        data = read_json(cache_path, default={})
        if not isinstance(data, dict) or data.get("epg_mtime") != (int(os.path.getmtime(xml_path)) if xml_path else 0):
            return {}
        
        out = {}
        items = data.get("items") or {}
        for ch_id, slots in items.items():
            if not isinstance(slots, dict): continue
            def conv(it):
                if not isinstance(it, dict): return None
                it = dict(it)
                for k in ("start", "stop"):
                    v = it.get(k)
                    if isinstance(v, str) and v:
                        try: it[k] = datetime.fromisoformat(v)
                        except: pass
                return it
            out[ch_id] = {"now": conv(slots.get("now")), "next": conv(slots.get("next"))}
        return out
    except:
        return {}

def main_menu() -> None:
    html = http_get_text(BASE_URL)
    if not html:
        xbmcgui.Dialog().notification("ROTV123", "Nu pot încărca site-ul.", xbmcgui.NOTIFICATION_ERROR, 3000)
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    xbmcplugin.setContent(HANDLE, "genres")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)

    pat = re.compile(
        r'href="(?P<href>[^"]*categoria\.php\?cat=[^"]+)"[^>]*>.*?class="[^"]*(?:category-title|category_name)[^"]*"[^>]*>\s*(?P<title>[^<]+)\s*<',
        re.IGNORECASE | re.DOTALL
    )

    found = []
    for m in pat.finditer(html):
        href = abs_url(m.group("href"))
        title = (m.group("title") or "").strip()
        if href and title:
            found.append((href, title))

    if not found:
        pat2 = re.compile(r'href="(?P<href>[^"]*categoria\.php\?cat=[^"]+)"', re.IGNORECASE)
        for m in pat2.finditer(html):
            href = abs_url(m.group("href"))
            if href and href not in [x for x, _ in found]:
                found.append((href, href.split("cat=")[-1]))

    for href, title in found:
        set_dir_item(label=title, url=build_url({"mode": "category", "url": href}), thumb="DefaultVideoPlaylists.png")

    set_dir_item(label=L_REFRESH_EPG(), url=build_url({"mode": "refresh_epg"}), thumb="DefaultAddonService.png", is_folder=False)
    set_dir_item(label=L_SETTINGS(), url=build_url({"mode": "settings"}), thumb="DefaultAddon.png", is_folder=False)

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=True)

def list_category(category_url: str) -> None:
    """Această funcție păstrează logica de afișare a canalelor din primul fișier."""
    category_url = abs_url(category_url)
    html = http_get_text(category_url)
    if not html:
        xbmcgui.Dialog().notification("ROTV123", "Categoria nu poate fi încărcată.", xbmcgui.NOTIFICATION_ERROR, 3000)
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    xbmcplugin.setContent(HANDLE, "videos")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)

    id_tags = _load_id_tags()
    show_epg = get_setting_bool("show_epg_in_list", True)
    xml_path = epgmod.ensure_epg_cached(addon_id()) if (show_epg and id_tags) else None
    
    blocks = re.findall(r'<a[^>]+class="[^"]*channel-card[^"]*"[^>]*>.*?</a>', html, re.IGNORECASE | re.DOTALL)
    if not blocks:
        blocks = re.findall(r'<div[^>]+class="[^"]*channel-card[^"]*"[^>]*>.*?</div>', html, re.IGNORECASE | re.DOTALL)

    channels = []
    wanted_ids = set()

    for block in blocks:
        name_match = re.search(r'class="[^"]*channel-name[^"]*"[^>]*>\s*([^<]+)\s*<', block, re.IGNORECASE)
        link_match = re.search(r'href="([^"]+)"', block, re.IGNORECASE)
        logo_match = re.search(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)

        if not (name_match and link_match): continue

        channel_name = (name_match.group(1) or "").strip()
        link = abs_url(link_match.group(1))
        logo = get_proxy_image(abs_url(logo_match.group(1))) if logo_match else ""

        epg_id = ""
        if show_epg and xml_path and id_tags:
            tag = epg_key(channel_name)
            epg_id = id_tags.get(tag, "")
            if epg_id: wanted_ids.add(epg_id)

        channels.append({"name": channel_name, "link": link, "logo": logo, "epg_id": epg_id})

    epg_map = {}
    if show_epg and xml_path and wanted_ids:
        epg_map = _load_cat_cache(category_url, xml_path)
        if not epg_map:
            epg_map = epgmod.get_now_next_bulk(xml_path, wanted_ids)

    for ch in channels:
        plot = "Ghid TV indisponibil"
        if show_epg and ch["epg_id"]:
            data = epg_map.get(ch["epg_id"])
            if data: plot = format_epg_plot(data)

        play_url = build_url({"mode": "play", "url": ch["link"], "logo": ch["logo"], "name": ch["name"]})
        li = xbmcgui.ListItem(label=ch["name"])
        li.setProperty("IsPlayable", "true")
        li.setContentLookup(False)
        li.setInfo("video", {"title": ch["name"], "plot": plot, "mediatype": "video"})
        if ch["logo"]:
            li.setArt({"thumb": ch["logo"], "icon": ch["logo"]})
        
        li.addContextMenuItems([
            (L_REFRESH_EPG(), f'RunPlugin({build_url({"mode":"refresh_epg"})})'),
            (L_SETTINGS(), f'RunPlugin({build_url({"mode":"settings"})})'),
        ], replaceItems=False)

        xbmcplugin.addDirectoryItem(HANDLE, play_url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=True)

def _parse_streams_from_html(html: str) -> dict:
    streams = {}
    m = re.search(r'const\s+streams\s*=\s*\{(.*?)\}\s*;', html, re.IGNORECASE | re.DOTALL)
    if m:
        body = m.group(1)
        for k, u in re.findall(r'([a-zA-Z0-9_]+)\s*:\s*[\'\"]([^\'\"]+)[\'\"]', body):
            if u.strip().startswith('http'): streams[k] = u.strip()

    if not streams:
        for u in re.findall(r'(https?://[^\s\'\"]+\.(?:m3u8|mpd)(?:\?[^\s\'\"]*)?)', html, re.IGNORECASE):
            streams[f'auto{len(streams)+1}'] = u
    return streams

def play_video(page_url: str, logo: str = "", name: str = "") -> None:
    page_url = abs_url(page_url)
    html = http_get_text(page_url)
    if not html:
        xbmcgui.Dialog().notification("ROTV123", "Eroare pagină redare.", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    streams = _parse_streams_from_html(html)
    if not streams:
        xbmcgui.Dialog().notification("ROTV123", "Nu s-au găsit streamuri.", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    ordered = [("primary", streams["primary"])] if "primary" in streams else []
    ordered.extend([(k, streams[k]) for k in sorted(streams.keys()) if k != "primary"])

    playback_mode = get_setting_int("playback_mode", 0)
    chosen_media = None

    if playback_mode == 1:
        labels = [f"{k}" for (k, _) in ordered]
        idx = xbmcgui.Dialog().select(f"Alege sursa: {name}", labels)
        if idx >= 0:
            chosen_media = ordered[idx][1]
    else:
        chosen_media = ordered[0][1]

    if not chosen_media: return

    ua = get_setting_str("play_user_agent", USER_AGENT) or USER_AGENT
    referer = get_setting_str("play_referer", BASE_URL) or BASE_URL
    header = f"User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(referer)}"

    li = xbmcgui.ListItem(label=name or "Playback")
    li.setProperty("IsPlayable", "true")
    if logo: li.setArt({"thumb": logo, "icon": logo})
    li.setPath(chosen_media + "|" + header)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def router(param_string: str) -> None:
    params = dict(urllib.parse.parse_qsl(param_string))
    mode = params.get("mode")

    if mode == "category": list_category(params.get("url", ""))
    elif mode == "play": play_video(params.get("url", ""), params.get("logo", ""), params.get("name", ""))
    elif mode == "refresh_epg":
        if epgmod.ensure_epg_cached(addon_id(), force=True):
            xbmcgui.Dialog().notification("ROTV123", L_EPG_REFRESHED(), xbmcgui.NOTIFICATION_INFO, 2500)
            xbmc.executebuiltin("Container.Refresh")
    elif mode == "settings": ADDON.openSettings()
    else: main_menu()

if __name__ == "__main__":
    router(sys.argv[2][1:])