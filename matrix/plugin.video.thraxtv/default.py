# -*- coding: utf-8 -*-
import sys
import os
import re as _re
from urllib.parse import urlencode, parse_qs, quote
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmc
import xbmcvfs

from resources.lib import vavoo_resolver
from resources.lib.api import (
    PLAY_URL,
    get_countries,
    get_channels_by_country,
    get_channels_by_country_paged,
    prefetch_channels_page,
    get_categories,
    get_channels_by_category,
    search_channels,
    get_sources,
    resolve_source,
    get_channel_status_cached,
    resolve_ytdlp_local,
    find_working_stream,
    clear_cache,
    get_favorites,
    add_favorite,
    remove_favorite,
    get_channel,
    get_sports_schedule,
    RADIO_STREAM_URL,
    get_radio_countries,
    get_radio_stations,
)
from resources.lib.epg import (
    get_epg_day_schedule,
    get_epg_now_next_ext,
)

# Regex precompilat pentru extragerea codului de țară din URL logo
_FLAG_RE = _re.compile(r"/flags/([a-z]{2})\.png", _re.I)

addon = xbmcaddon.Addon()
addon_handle = int(sys.argv[1])
xbmcplugin.setContent(addon_handle, "videos")

# ─────────────────────────── i18n ───────────────────────────────
# Strings sunt în resources/language/*/strings.po
# Kodi alege automat limba în funcție de setarea de sistem.

_S = {
    "menu_favorites":    32000,
    "menu_countries":    32001,
    "menu_categories":   32002,
    "menu_search":       32003,
    "menu_clear_cache":  32004,
    "menu_radio":        32090,
    "radio_no_stations": 32091,
    "no_favorites":      32005,
    "fav_removed":       32006,
    "fav_added":         32007,
    "fav_remove_cm":     32008,
    "fav_add_cm":        32009,
    "all_channels":      32010,
    "next_page":         32011,
    "search_prompt":     32012,
    "search_no_results": 32013,
    "search_new":        32014,
    "search_results":    32015,
    "search_title":      32003,  # refolosește "Search"
    "epg_unavailable":   32017,
    "epg_now":           32018,
    "epg_now_colon":     32019,
    "epg_next":          32020,
    "epg_next_colon":    32021,
    "epg_cm":            32022,
    "epg_no_program":    32023,
    "epg_schedule":      32024,
    "epg_today":         32025,
    "choose_source":     32026,
    "channel_default":   32027,
    "no_sources":        32028,
    "no_working_stream": 32029,
    "quality_unknown":   32030,
    "status_green":      32031,
    "status_orange":     32032,
    "status_red":        32033,
    "error":             32034,
    "err_get_sources":   32035,
    "err_vavoo_cid":     32036,
    "err_thrax_sig":     32037,
    "err_vavoo_server":  32038,
    "err_resolve":       32039,
    "err_source_unavail":32040,
    "cache_cleared":     32041,
    "menu_sports":       32061,
    "sport_no_events":   32062,
    "wc_no_matches":     32064,
    "wc_no_channels":    32065,
}

_CAT_STR_IDS = {
    "generaliste": 32050, "generale": 32050,
    "stiri":       32051, "știri":    32051,
    "sport":       32052,
    "filme":       32053,
    "divertisment":32054,
    "muzica":      32055, "muzică":   32055,
    "documentare": 32056,
    "copii":       32057,
    "religioase":  32058,
    "locale":      32059,
    "diverse":     32060,
}


_LANG_CACHE = [None]
_PO_CACHE   = {}


def _lang() -> str:
    """Returnează 'ro', 'en' sau 'auto' în funcție de setarea ui_language."""
    if _LANG_CACHE[0] is None:
        val = addon.getSetting("ui_language")   # "Auto" | "Română" | "English"
        if val == "Română":
            _LANG_CACHE[0] = "ro"
        elif val == "English":
            _LANG_CACHE[0] = "en"
        else:
            _LANG_CACHE[0] = "auto"
    return _LANG_CACHE[0]


def _parse_po(lang_folder: str) -> dict:
    """Parsează strings.po și returnează {string_id: text}."""
    import os, re as _re_po
    path = os.path.join(
        addon.getAddonInfo("path"), "resources", "language",
        lang_folder, "strings.po"
    )
    result = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = _re_po.compile(
            r'msgctxt\s+"#(\d+)"\s+msgid\s+"((?:[^"\\]|\\.)*)"\s+msgstr\s+"((?:[^"\\]|\\.)*)"'
        )
        for m in pattern.finditer(content):
            sid = int(m.group(1))
            msgid  = m.group(2).replace("\\n", "\n").replace('\\"', '"')
            msgstr = m.group(3).replace("\\n", "\n").replace('\\"', '"')
            result[sid] = msgstr if msgstr else msgid
    except Exception:
        pass
    return result


def _get_po(lang_folder: str) -> dict:
    if lang_folder not in _PO_CACHE:
        _PO_CACHE[lang_folder] = _parse_po(lang_folder)
    return _PO_CACHE[lang_folder]


def _localized(sid: int) -> str:
    lang = _lang()
    if lang == "ro":
        return _get_po("resource.language.ro_ro").get(sid, "") or addon.getLocalizedString(sid)
    if lang == "en":
        return _get_po("resource.language.en_gb").get(sid, "") or addon.getLocalizedString(sid)
    return addon.getLocalizedString(sid)


def _t(key: str, *args) -> str:
    sid = _S.get(key)
    s = _localized(sid) if sid else key
    return s % args if args else s


def _cat_name(cat: dict) -> str:
    """Returnează numele categoriei tradus, sau numele din API dacă nu există traducere."""
    api_key = (cat.get("key") or cat.get("id") or "").lower()
    sid = _CAT_STR_IDS.get(api_key)
    if sid:
        return _localized(sid)
    return cat.get("name") or api_key

# ─────────── inputstream.adaptive ───────────────────────────────

_HLS_PROVIDERS  = {"primaplay", "sultan", "antenaplay", "peertube", "dinbox", "canale-tv"}

# HLS care merge doar prin demuxerul ffmpeg, nu prin inputstream.adaptive: la
# tvzonehd nici manifestul („.htm"), nici segmentele n-au extensie recunoscută,
# iar ISA nu poate deduce containerul („Cannot detect container type from media
# url" → fallback TS greșit). ffmpeg citește conținutul, deci se descurcă — are
# nevoie doar de mimetype, fiindcă altfel Kodi ghicește după extensie.
_HLS_MIME_ONLY  = {"tvzonehd"}
_DASH_PROVIDERS = {"ytdlp"}          # MPEG-DASH MPD generat server-side

def _apply_inputstream_for_provider(li, url, provider=""):
    prov = (provider or "").lower()

    if prov in _HLS_PROVIDERS:
        try:
            li.setProperty("inputstream", "inputstream.adaptive")
            li.setProperty("inputstream.adaptive.manifest_type", "hls")
            li.setMimeType("application/x-mpegURL")
            li.setContentLookup(False)
            # isa nu interpretează sufixul |key=val din path — trebuie URL curat
            # și headerele transmise explicit via proprietăți
            if "|" in url:
                clean_url, header_str = url.split("|", 1)
                li.setPath(clean_url)
                li.setProperty("inputstream.adaptive.manifest_headers", header_str)
                li.setProperty("inputstream.adaptive.stream_headers", header_str)
        except Exception:
            pass

    elif prov in _HLS_MIME_ONLY:
        try:
            li.setMimeType("application/x-mpegURL")
            # Lăsăm Kodi să citească tipul real de la server: fluxul e HEVC în TS,
            # iar din URL nu se poate deduce nici containerul, nici codecul.
            li.setContentLookup(True)
        except Exception:
            pass

    elif prov in _DASH_PROVIDERS and "/livetv/ydash/" in url:
        try:
            # URL-ul de la server este un MPD DASH generat din metadatele yt-dlp
            clean_url = url.split("|")[0]
            li.setProperty("inputstream", "inputstream.adaptive")
            li.setProperty("inputstream.adaptive.manifest_type", "mpd")
            li.setMimeType("application/dash+xml")
            li.setPath(clean_url)
            li.setContentLookup(False)
        except Exception:
            pass


# ─────────────────────────── Helpers ───────────────────────────

def _play_dash_mpd(mpd_content: str, title: str) -> None:
    """Scrie MPD-ul local și lansează redarea cu inputstream.adaptive."""
    import os, tempfile
    fd, mpd_path = tempfile.mkstemp(suffix=".mpd", prefix="thraxtv_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(mpd_content)
    li = xbmcgui.ListItem(path="file://" + mpd_path)
    li.setInfo("video", {"title": title})
    li.setProperty("inputstream", "inputstream.adaptive")
    li.setProperty("inputstream.adaptive.manifest_type", "mpd")
    li.setMimeType("application/dash+xml")
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(addon_handle, True, li)


def build_url(query):
    return sys.argv[0] + "?" + urlencode(query)


def _get_bool(setting_id):
    try:
        return addon.getSettingBool(setting_id)
    except Exception:
        return (addon.getSetting(setting_id) or "").lower() == "true"


def _get_int(setting_id, default=0):
    try:
        return addon.getSettingInt(setting_id)
    except Exception:
        try:
            return int(addon.getSetting(setting_id) or default)
        except Exception:
            return default


def _get_items_per_page():
    return max(1, _get_int("items_per_page", 25))


def _get_max_epg_threads():
    return max(1, _get_int("max_epg_threads", 5))


_PRELOAD_EPG_CACHE = [None]
_AUTO_PLAY_CACHE   = [None]


def _should_preload_epg():
    if _PRELOAD_EPG_CACHE[0] is None:
        _PRELOAD_EPG_CACHE[0] = _get_bool("preload_epg")
    return _PRELOAD_EPG_CACHE[0]


def _get_playback_mode():
    if _AUTO_PLAY_CACHE[0] is None:
        try:
            _AUTO_PLAY_CACHE[0] = addon.getSettingBool("auto_play")
        except Exception:
            _AUTO_PLAY_CACHE[0] = True
    return _AUTO_PLAY_CACHE[0]


# ─────────── Filtrare țări (cu cache în sesiune) ───────────────

_country_filter_cache = None


def _selected_country_codes():
    global _country_filter_cache
    if _country_filter_cache is not None:
        return _country_filter_cache

    selected = set()
    any_toggle_found = False

    try:
        countries = get_countries() or []
    except Exception:
        countries = []

    for c in countries:
        code = (c.get("code") or "").strip().upper()
        if len(code) != 2:
            continue
        sid = "use_%s" % code.lower()
        try:
            raw = addon.getSetting(sid)
        except Exception:
            raw = ""
        if raw != "":
            any_toggle_found = True
        if _get_bool(sid):
            selected.add(code)

    result = selected if (selected or any_toggle_found) else set()
    _country_filter_cache = result
    return result


# Coduri de țară (ISO) folosite de alte surse (ex. radio-browser.info) care nu
# corespund 1:1 cu id-ul de setare existent — mapate la setarea echivalentă.
_COUNTRY_SETTING_ALIAS = {"GB": "UK"}

_radio_country_filter_cache = {}


def _selected_country_codes_for(candidate_codes):
    """Ca _selected_country_codes(), dar pentru o listă arbitrară de coduri
    (ex. țările din catalogul Radio, care nu corespund mereu cu cele din LiveTV).
    Reutilizează aceleași setări use_{cc} — un singur set de bife pentru tot addon-ul."""
    key = tuple(sorted(set(candidate_codes)))
    cached = _radio_country_filter_cache.get(key)
    if cached is not None:
        return cached

    selected = set()
    any_toggle_found = False
    for code in candidate_codes:
        code = (code or "").strip().upper()
        if len(code) != 2:
            continue
        setting_code = _COUNTRY_SETTING_ALIAS.get(code, code)
        sid = "use_%s" % setting_code.lower()
        try:
            raw = addon.getSetting(sid)
        except Exception:
            raw = ""
        if raw != "":
            any_toggle_found = True
        if _get_bool(sid):
            selected.add(code)

    result = selected if (selected or any_toggle_found) else set()
    _radio_country_filter_cache[key] = result
    return result


def _code_from_channel(ch):
    for key in ("country", "country_code", "iso", "iso2", "code"):
        v = ch.get(key)
        if isinstance(v, str) and len(v) == 2:
            return v.upper()
    try:
        icon = ch.get("icon") or ch.get("tvg-logo") or ch.get("tvg_logo") or ch.get("logo") or ""
        m = _FLAG_RE.search(str(icon))
        if m:
            return m.group(1).upper()
    except Exception:
        pass
    name = (ch.get("group-title") or ch.get("group") or ch.get("country_name") or "").strip().lower()
    MAP = {
        "romania": "RO", "românia": "RO",
        "germany": "DE", "germania": "DE",
        "italy": "IT", "italia": "IT",
        "france": "FR", "franța": "FR",
        "spain": "ES", "spania": "ES",
        "albania": "AL",
        "turkey": "TR", "turcia": "TR",
        "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB",
    }
    return MAP.get(name)


def _passes_filter(code, selected):
    if not selected:
        return True
    return bool(code) and code.upper() in selected


def _build_url_with_headers(url: str, src: dict) -> str:
    if not url:
        return ""
    extra = src.get("headers") if isinstance(src.get("headers"), dict) else {}
    ua = src.get("user_agent") or extra.get("User-Agent") or \
         addon.getSetting("manual_user_agent") or \
         "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    ref = src.get("referrer") or src.get("referer") or extra.get("Referer")
    origin = src.get("origin") or extra.get("Origin")

    headers = {}
    if ua:
        headers["User-Agent"] = ua
    if ref:
        headers["Referer"] = ref
    if origin:
        headers["Origin"] = origin
    for k, v in extra.items():
        if v is not None and k not in headers:
            headers[k] = v

    if not headers:
        return url

    parts = [f"{k}={quote(str(v))}" for k, v in headers.items() if v is not None]
    return url + "|" + "&".join(parts)


# ──────────────── EPG Helpers ───────────────────────────────────

def _fetch_epg_threaded(channels):
    def fetch(channel):
        cid = channel["id"]
        cc = (channel.get("country") or channel.get("code") or _code_from_channel(channel) or "RO").lower()
        epg = get_epg_now_next_ext(cid, cc)
        return cid, epg

    epg_data = {}
    with ThreadPoolExecutor(max_workers=_get_max_epg_threads()) as ex:
        futures = {ex.submit(fetch, c): c["id"] for c in channels}
        for fut in as_completed(futures):
            try:
                cid, epg = fut.result()
                epg_data[cid] = epg
            except Exception as e:
                xbmc.log(f"[ThraxTV][EPG] Thread error: {e}", xbmc.LOGWARNING)
    return epg_data


def _add_epg_to_channels(channels):
    if not channels:
        return channels
    epg_data = _fetch_epg_threaded(channels)
    for ch in channels:
        ch["epg"] = epg_data.get(ch["id"])
    return channels


# ──────────────── Nostream Filter ───────────────────────────────

def _is_nostream_channel(channel):
    categories = channel.get("categories", [])
    if not isinstance(categories, list):
        return False
    for category in categories:
        if isinstance(category, str) and category.lower() == "nostream":
            return True
    return False


# ──────────────── Construcție ListItem canal (DRY) ──────────────

_STATUS_DOT = {
    "green":  "[COLOR=lime]|[/COLOR] ",
    "orange": "[COLOR=orange]|[/COLOR] ",
    "red":    "[COLOR=red]|[/COLOR] ",
}
def _status_badge(status: str) -> str:
    colors = {"green": "lime", "orange": "orange", "red": "red"}
    color = colors.get(status, "white")
    return "[COLOR=%s]%s[/COLOR]" % (color, _t("status_" + status))


def _build_channel_listitem(ch, epg=None, is_fav=False):
    cid = ch["id"]
    label = ch.get("title") or ch.get("name") or str(cid)
    logo = ch.get("logo", "")
    country_code = (ch.get("country") or ch.get("code") or _code_from_channel(ch) or "RO").lower()

    status = get_channel_status_cached(cid)
    if status:
        label = _STATUS_DOT[status] + label

    if epg:
        plot = ""
        if epg.get("now_title") and epg.get("now_range"):
            progress_bar = ""
            raw_progress = epg.get("progress", "")
            if raw_progress:
                try:
                    pct = int(str(raw_progress).replace("%", "").strip())
                    filled = round(pct / 10)
                    empty  = 10 - filled
                    progress_bar = "\n[COLOR=orange]%s%s[/COLOR] %s" % ("█" * filled, "░" * empty, raw_progress)
                except Exception:
                    pass
            plot += "[COLOR=red]%s[/COLOR]\n[COLOR=yellow]%s[/COLOR] %s%s\n\n" % (_t("epg_now"), epg["now_range"], epg["now_title"], progress_bar)
        elif epg.get("now_title"):
            plot += "[COLOR=red]%s[/COLOR] %s\n\n" % (_t("epg_now_colon"), epg["now_title"])
        if epg.get("next_title") and epg.get("next_range"):
            plot += "[COLOR=red]%s[/COLOR]\n[COLOR=lightblue]%s[/COLOR] %s" % (_t("epg_next"), epg["next_range"], epg["next_title"])
        elif epg.get("next_title"):
            plot += "[COLOR=red]%s[/COLOR] %s" % (_t("epg_next_colon"), epg["next_title"])
    else:
        plot = "[COLOR=gray]%s[/COLOR]" % _t("epg_unavailable")

    li = xbmcgui.ListItem(label=label)
    li.setArt({"thumb": logo})
    li.setInfo("video", {"title": label, "plot": plot})
    li.setProperty("IsPlayable", "true")

    auto_play = _get_playback_mode()
    if auto_play:
        url = build_url({"action": "play", "id": cid})
    else:
        url = build_url({"action": "choose_source", "id": cid, "title": label})

    fav_label = _t("fav_remove_cm") if is_fav else _t("fav_add_cm")
    cm = [
        (_t("epg_cm"), "RunPlugin(%s)" % build_url({"action": "show_epg", "id": cid, "country": country_code})),
        (fav_label, "RunPlugin(%s)" % build_url({"action": "toggle_favorite", "id": cid, "is_fav": "1" if is_fav else "0"})),
    ]
    li.addContextMenuItems(cm)

    return li, url, False


# ──────────────── Main Menu ─────────────────────────────────────

def main_menu():
    import os as _os
    xbmcplugin.setContent(addon_handle, "addons")
    _path   = addon.getAddonInfo("path")
    _fanart = _os.path.join(_path, "fanart.jpg")
    _MENIU  = _os.path.join(_path, "resources", "icons", "meniu")
    for label, query, is_folder, icon_name in [
        (_t("menu_favorites"),   {"action": "list_favorites"},   True,  "favorite"),
        (_t("menu_countries"),   {"action": "list_countries"},   True,  "tari"),
        (_t("menu_categories"),  {"action": "list_categories"},  True,  "categorii"),
        (_t("menu_sports"),      {"action": "list_sports_menu"}, True,  "sport"),
        (_t("menu_radio"),       {"action": "radio_countries"},  True,  "tari"),
        (_t("menu_search"),      {"action": "search"},           True,  "cautare"),
        (_t("menu_clear_cache"), {"action": "clear_cache"},      False, "sterge_cache"),
    ]:
        _icon = _os.path.join(_MENIU, icon_name + ".png")
        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": _icon, "poster": _icon, "fanart": _fanart})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=build_url(query), listitem=li, isFolder=is_folder)
    xbmcplugin.endOfDirectory(addon_handle)


def clear_cache_action():
    deleted = clear_cache()
    xbmcgui.Dialog().notification(
        "ThraxTV",
        _t("cache_cleared", deleted),
        xbmcgui.NOTIFICATION_INFO,
        3000,
    )


# ──────────────── Favorite ──────────────────────────────────────

def list_favorites():
    xbmcplugin.setContent(addon_handle, "videos")
    fav_ids = get_favorites()
    if not fav_ids:
        xbmcgui.Dialog().notification("ThraxTV", _t("no_favorites"), xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    channels = []
    for cid in fav_ids:
        ch = get_channel(cid)
        if not ch:
            continue
        ch.setdefault("id", cid)
        channels.append(ch)

    epg_results = _fetch_epg_threaded(channels) if _should_preload_epg() else {}

    for ch in channels:
        epg = epg_results.get(ch["id"])
        li, url, is_folder = _build_channel_listitem(ch, epg=epg, is_fav=True)
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(addon_handle)


def toggle_favorite(params):
    cid = params.get("id", "")
    is_fav = params.get("is_fav") == "1"
    if not cid:
        return
    if is_fav:
        remove_favorite(cid)
        xbmcgui.Dialog().notification("ThraxTV", _t("fav_removed"), xbmcgui.NOTIFICATION_INFO, 2000)
    else:
        add_favorite(cid)
        xbmcgui.Dialog().notification("ThraxTV", _t("fav_added"), xbmcgui.NOTIFICATION_INFO, 2000)
    xbmc.executebuiltin("Container.Refresh")


# ──────────────── Countries / Channels ─────────────────────────

def list_countries():
    xbmcplugin.setContent(addon_handle, "addons")
    countries = get_countries() or []
    selected = _selected_country_codes()
    if selected:
        countries = [c for c in countries if c.get("code") and c["code"].upper() in selected]
    for c in countries:
        code = c.get("code", "")
        name = c.get("name", code or "Unknown")
        logo = c.get("logo", "")
        url = build_url({"action": "list_country_categories", "code": code, "name": name, "logo": logo})
        li = xbmcgui.ListItem(label=name)
        li.setArt({
            "thumb":  c.get("thumb") or c.get("icon") or "",
            "poster": c.get("poster") or "",
            "fanart": c.get("fanart") or "",
        })
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)


def list_country_categories(params):
    xbmcplugin.setContent(addon_handle, "addons")
    code = params["code"]
    country_name = params.get("name", code)

    categories = get_categories() or []
    categories = [
        cat for cat in categories
        if cat.get("id", "").lower() != "nostream"
        and cat.get("name", "").lower() != "nostream"
    ]

    ASSETS_BASE = "https://api.derzis.xyz/assets/categories"
    toate_icon   = ASSETS_BASE + "/320x180/toate.png"
    toate_poster = ASSETS_BASE + "/320x450/toate.png"
    all_url = build_url({"action": "list_channels", "code": code})
    li_all = xbmcgui.ListItem(label=_t("all_channels"))
    li_all.setArt({"thumb": toate_icon, "poster": toate_poster})
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=all_url, listitem=li_all, isFolder=True)

    for cat in categories:
        url = build_url({"action": "list_category_channels", "cat": cat["id"], "country": code})
        li = xbmcgui.ListItem(label=_cat_name(cat))
        li.setArt({
            "thumb":  cat.get("icon", ""),
            "poster": cat.get("poster", ""),
        })
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

    xbmcplugin.setPluginCategory(addon_handle, country_name)
    xbmcplugin.endOfDirectory(addon_handle)


def list_channels(params):
    import threading
    xbmcplugin.setContent(addon_handle, "videos")
    code = params["code"]
    page = int(params.get("page", 1))
    per_page = _get_items_per_page()

    channels, total = get_channels_by_country_paged(code, page=page, size=per_page)
    channels = [ch for ch in channels if not _is_nostream_channel(ch)]

    epg_results = {}
    if _should_preload_epg():
        epg_results = _fetch_epg_threaded(channels)

    favs = set(get_favorites())
    for ch in channels:
        epg = epg_results.get(ch["id"]) if _should_preload_epg() else None
        li, url, is_folder = _build_channel_listitem(ch, epg, is_fav=ch["id"] in favs)
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=is_folder)

    has_next = page * per_page < total
    if has_next:
        next_url = build_url({"action": "list_channels", "code": code, "page": page + 1})
        li = xbmcgui.ListItem(label=_t("next_page", page + 1))
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=next_url, listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(addon_handle)

    if has_next:
        threading.Thread(
            target=prefetch_channels_page,
            args=(code, page + 1, per_page),
            daemon=True,
        ).start()


# ──────────────── Radio ─────────────────────────────────────────

_ARTWORK_BASE = "https://raw.githubusercontent.com/derzis/artwork/refs/heads/main"
_RADIO_FALLBACK_LOGO = os.path.join(
    addon.getAddonInfo("path"), "resources", "icons", "radio", "fallback.png"
)


def radio_countries():
    xbmcplugin.setContent(addon_handle, "addons")
    countries = get_radio_countries() or []
    selected = _selected_country_codes_for([c.get("country", "") for c in countries])
    if selected:
        countries = [c for c in countries if c.get("country", "").upper() in selected]
    for c in countries:
        code = c.get("country", "")
        count = c.get("count", 0)
        label = "%s (%d)" % (code.upper(), count)
        url = build_url({"action": "radio_stations", "code": code})
        li = xbmcgui.ListItem(label=label)
        cc_lower = code.lower()
        li.setArt({
            "thumb":  f"{_ARTWORK_BASE}/posters/{cc_lower}.png",
            "poster": f"{_ARTWORK_BASE}/posters/{cc_lower}.png",
            "fanart": f"{_ARTWORK_BASE}/fanart/{cc_lower}.jpg",
        })
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)


def radio_stations_list(params):
    xbmcplugin.setContent(addon_handle, "videos")
    code = params["code"]
    page = int(params.get("page", 1))
    size = 100

    items, meta = get_radio_stations(code, page=page, size=size)
    if not items and page == 1:
        xbmcgui.Dialog().notification("ThraxTV", _t("radio_no_stations"), xbmcgui.NOTIFICATION_INFO, 3000)

    for st in items:
        sid = st.get("id", "")
        name = st.get("name") or sid
        logo = st.get("logo", "")
        if not logo or logo.strip().lower() == "null":
            logo = _RADIO_FALLBACK_LOGO
        li = xbmcgui.ListItem(label=name)
        li.setArt({"thumb": logo, "poster": logo})
        li.setInfo("video", {"title": name})
        li.setProperty("IsPlayable", "true")
        url = build_url({"action": "radio_play", "id": sid, "title": name})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=False)

    total = meta.get("total", 0)
    if page * size < total:
        next_url = build_url({"action": "radio_stations", "code": code, "page": page + 1})
        li = xbmcgui.ListItem(label=_t("next_page", page + 1))
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=next_url, listitem=li, isFolder=True)

    xbmcplugin.setPluginCategory(addon_handle, code.upper())
    xbmcplugin.endOfDirectory(addon_handle)


def radio_play(params):
    sid = params.get("id", "")
    title = params.get("title", sid)
    final_url = "%s/%s" % (RADIO_STREAM_URL, sid)

    li = xbmcgui.ListItem(path=final_url)
    li.setInfo("video", {"title": title})
    li.setProperty("IsPlayable", "true")
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(addon_handle, True, li)


# ──────────────── Categories ────────────────────────────────────

def list_categories():
    xbmcplugin.setContent(addon_handle, "addons")
    categories = get_categories() or []
    categories = [
        cat for cat in categories
        if cat.get("id", "").lower() != "nostream"
        and cat.get("name", "").lower() != "nostream"
    ]
    for cat in categories:
        url = build_url({"action": "list_category_channels", "cat": cat["id"]})
        li = xbmcgui.ListItem(label=_cat_name(cat))
        li.setArt({
            "thumb":  cat.get("icon", ""),
            "poster": cat.get("poster", ""),
        })
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)


def list_category_channels(params):
    import threading
    xbmcplugin.setContent(addon_handle, "videos")
    category_id = params["cat"]
    country_filter = params.get("country", "")
    page = int(params.get("page", 1))
    per_page = _get_items_per_page()

    if category_id.lower() == "nostream":
        xbmcplugin.endOfDirectory(addon_handle)
        return

    if country_filter:
        # Server-side pagination prin catalog API (category + country)
        channels, total = get_channels_by_country_paged(
            country_filter, page=page, size=per_page, category=category_id
        )
        channels = [ch for ch in channels if not _is_nostream_channel(ch)]
        has_next = page * per_page < total
    else:
        # Fetch all + client-side pagination (fără country filter)
        all_channels = get_channels_by_category(category_id) or []
        all_channels = [ch for ch in all_channels if not _is_nostream_channel(ch)]
        selected = _selected_country_codes()
        if selected:
            all_channels = [c for c in all_channels if _passes_filter(_code_from_channel(c), selected)]
        total = len(all_channels)
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        channels = all_channels[start:end]
        has_next = end < total

    epg_results = {}
    if _should_preload_epg():
        epg_results = _fetch_epg_threaded(channels)

    favs = set(get_favorites())
    for ch in channels:
        epg = epg_results.get(ch["id"]) if _should_preload_epg() else None
        li, url, is_folder = _build_channel_listitem(ch, epg, is_fav=ch["id"] in favs)
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=is_folder)

    if has_next:
        next_url = build_url({"action": "list_category_channels", "cat": category_id,
                              "country": country_filter, "page": page + 1})
        li = xbmcgui.ListItem(label=_t("next_page", page + 1))
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=next_url, listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(addon_handle)

    if has_next and country_filter:
        threading.Thread(
            target=prefetch_channels_page,
            args=(country_filter, page + 1, per_page),
            kwargs={"category": category_id},
            daemon=True,
        ).start()


# ──────────────── Search ────────────────────────────────────────

def list_search_results(params):
    query = params.get("query", "")
    if not query:
        query = xbmcgui.Dialog().input(_t("search_prompt"), type=xbmcgui.INPUT_ALPHANUM)
        if not query:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
            return

    xbmcplugin.setContent(addon_handle, "videos")
    page = int(params.get("page", 1))
    per_page = _get_items_per_page()

    all_results = search_channels(query) or []
    all_results = [ch for ch in all_results if not _is_nostream_channel(ch)]

    selected = _selected_country_codes()
    if selected:
        all_results = [c for c in all_results if _passes_filter(_code_from_channel(c), selected)]

    if not all_results:
        xbmcgui.Dialog().notification(
            _t("search_title"),
            _t("search_no_results", query),
            xbmcgui.NOTIFICATION_INFO,
        )
        li = xbmcgui.ListItem(label=_t("search_new"))
        xbmcplugin.addDirectoryItem(
            handle=addon_handle,
            url=build_url({"action": "search"}),
            listitem=li,
            isFolder=True,
        )
        xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
        return

    total = len(all_results)
    start = (page - 1) * per_page
    end = min(start + per_page, total)
    results = all_results[start:end]

    if _should_preload_epg():
        results = _add_epg_to_channels(results)

    favs = set(get_favorites())
    for ch in results:
        epg = ch.get("epg") if _should_preload_epg() else None
        li, url, is_folder = _build_channel_listitem(ch, epg, is_fav=ch["id"] in favs)
        if "action=play" in url:
            url = build_url({"action": "play", "id": ch["id"], "query": query})
        elif "action=choose_source" in url:
            label = ch.get("title") or ch.get("name") or str(ch["id"])
            url = build_url({"action": "choose_source", "id": ch["id"], "title": label, "query": query})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=is_folder)

    if end < total:
        next_url = build_url({"action": "list_search_results", "query": query, "page": page + 1})
        li = xbmcgui.ListItem(label=_t("next_page", page + 1))
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=next_url, listitem=li, isFolder=True)

    li = xbmcgui.ListItem(label=_t("search_new"))
    xbmcplugin.addDirectoryItem(
        handle=addon_handle,
        url=build_url({"action": "search"}),
        listitem=li,
        isFolder=False,
    )
    xbmcplugin.setPluginCategory(addon_handle, _t("search_results", query))
    xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)


# ──────────────── EPG ───────────────────────────────────────────

def show_epg(params):
    channel_id = params["id"]
    country = params.get("country", "ro").lower()
    schedule = get_epg_day_schedule(channel_id, country=country, hours=24)

    if not schedule:
        xbmcgui.Dialog().notification("EPG", _t("epg_no_program"), xbmcgui.NOTIFICATION_INFO)
        return

    from datetime import datetime
    text = _t("epg_schedule", channel_id, datetime.now().strftime("%Y-%m-%d")) + "\n\n"
    for item in schedule:
        try:
            start_str = datetime.fromtimestamp(int(item["start"])).strftime("%H:%M")
        except Exception:
            start_str = str(item.get("start", ""))
        try:
            stop_ts = item.get("stop")
            stop_str = (" - " + datetime.fromtimestamp(int(stop_ts)).strftime("%H:%M")) if stop_ts else ""
        except Exception:
            stop_str = ""
        title = item.get("title", "")
        desc  = item.get("desc", "")
        line  = "%s%s  %s" % (start_str, stop_str, title)
        if desc:
            line += "\n    %s" % desc
        text += line + "\n\n"

    xbmcgui.Dialog().textviewer(_t("epg_today"), text.strip())


# ──────────────── Sources Dialog ────────────────────────────────

def choose_source(params):
    channel_id = params["id"]
    title = params.get("title", _t("channel_default", channel_id))
    query = params.get("query", "")
    from_cm = params.get("from_cm") == "true"
    can_navigate_back = query and not from_cm

    try:
        sources = get_sources(channel_id) or []
    except Exception as e:
        xbmcgui.Dialog().notification(_t("error"), _t("err_get_sources", e), xbmcgui.NOTIFICATION_ERROR)
        return

    sources = [s for s in sources if (s.get("status") or "").lower() != "red"]

    if not sources:
        xbmcgui.Dialog().notification(_t("error"), _t("no_sources"), xbmcgui.NOTIFICATION_ERROR)
        return

    def _resolve_and_play(src):
        provider = (src.get("provider") or "").lower()
        if provider == "vavoo":
            cid_str = str(src.get("cid") or "").strip()
            if not cid_str:
                xbmcgui.Dialog().notification(_t("error"), _t("err_vavoo_cid"), xbmcgui.NOTIFICATION_ERROR)
                xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
                return
            final_url = vavoo_resolver.resolve_vavoo(cid_str)
            if not final_url:
                sig_ok = vavoo_resolver.get_auth_signature() is not None
                reason = _t("err_thrax_sig") if not sig_ok else _t("err_vavoo_server")
                xbmcgui.Dialog().notification("Vavoo", reason, xbmcgui.NOTIFICATION_ERROR)
                xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
                return
        elif provider == "ytdlp" and src.get("resolve"):
            source_url = src.get("url") or ""
            local = resolve_ytdlp_local(source_url)
            if local is not None:
                if local.get("mpd"):
                    _play_dash_mpd(local["mpd"], title)
                    return
                src = {**src, "url": local["url"], "headers": local.get("headers") or {}}
            else:
                try:
                    resolved = resolve_source(channel_id, provider=provider, source_cid=src.get("cid"))
                except Exception as e:
                    xbmcgui.Dialog().notification(_t("error"), _t("err_resolve", e), xbmcgui.NOTIFICATION_ERROR)
                    xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
                    return
                if not resolved or not resolved.get("url"):
                    xbmcgui.Dialog().notification(_t("error"), _t("err_source_unavail"), xbmcgui.NOTIFICATION_ERROR)
                    xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
                    return
                src = {**src, "url": resolved["url"], "headers": resolved.get("headers") or src.get("headers") or {}}
            final_url = _build_url_with_headers(src["url"], src)
        elif provider == "rdslive":
            # Token IP-bound pe CDN → server proxiază segmentele; folosim /livetv/play/ nu resolve direct
            cid_str = str(src.get("cid") or "0")
            final_url = "%s/%s?provider=rdslive&source_cid=%s" % (PLAY_URL, channel_id, cid_str)
        elif src.get("resolve"):
            try:
                resolved = resolve_source(channel_id, provider=provider, source_cid=src.get("cid"))
            except Exception as e:
                xbmcgui.Dialog().notification(_t("error"), _t("err_resolve", e), xbmcgui.NOTIFICATION_ERROR)
                xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
                return
            if not resolved or not resolved.get("url"):
                xbmcgui.Dialog().notification(_t("error"), _t("err_source_unavail"), xbmcgui.NOTIFICATION_ERROR)
                xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
                return
            if resolved.get("manifest_type") == "mpd":
                li = xbmcgui.ListItem(path=resolved["url"])
                li.setInfo("video", {"title": title})
                li.setProperty("IsPlayable", "true")
                li.setProperty("inputstream", "inputstream.adaptive")
                li.setProperty("inputstream.adaptive.manifest_type", "mpd")
                li.setMimeType("application/dash+xml")
                li.setContentLookup(False)
                hdrs = resolved.get("headers") if isinstance(resolved.get("headers"), dict) else {}
                if hdrs:
                    hdr_str = "&".join(f"{k}={quote(str(v))}" for k, v in hdrs.items() if v is not None)
                    li.setProperty("inputstream.adaptive.manifest_headers", hdr_str)
                    li.setProperty("inputstream.adaptive.stream_headers", hdr_str)
                xbmcplugin.setResolvedUrl(addon_handle, True, li)
                return
            src = {**src, "url": resolved["url"], "headers": resolved.get("headers") or src.get("headers") or {}}
            final_url = _build_url_with_headers(src["url"], src)
        else:
            final_url = _build_url_with_headers(src["url"], src)

        li = xbmcgui.ListItem(path=final_url)
        li.setInfo("video", {"title": title})
        li.setProperty("IsPlayable", "true")
        li.setContentLookup(False)
        _apply_inputstream_for_provider(li, final_url, provider=provider)
        xbmcplugin.setResolvedUrl(addon_handle, True, li)

    if len(sources) == 1:
        _resolve_and_play(sources[0])
        if can_navigate_back:
            xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")
        return

    options = []
    for src in sources:
        q        = src.get("quality") or _t("quality_unknown")
        provider = src.get("provider") or ""
        status   = (src.get("status") or "").lower()
        badge    = "  " + _status_badge(status) if status in ("green", "orange", "red") else ""
        options.append(f"{q} – {provider}{badge}" if provider else f"{q}{badge}")

    selected_index = xbmcgui.Dialog().select(_t("choose_source", title), options)

    if selected_index < 0:
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        if can_navigate_back:
            xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")
        return

    _resolve_and_play(sources[selected_index])


# ──────────────── Playback ──────────────────────────────────────

def play_channel(params):
    channel_id = params["id"]
    query = params.get("query", "")
    from_cm = params.get("from_cm") == "true"
    can_navigate_back = query and not from_cm

    stream = find_working_stream(channel_id)

    if not stream:
        xbmcgui.Dialog().notification("ThraxTV", _t("no_working_stream"), xbmcgui.NOTIFICATION_ERROR)
        if can_navigate_back:
            xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")
        return

    if stream.get("mpd"):
        _play_dash_mpd(stream["mpd"], channel_id)
        if can_navigate_back:
            xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")
        return

    if not stream.get("url"):
        xbmcgui.Dialog().notification("ThraxTV", _t("no_working_stream"), xbmcgui.NOTIFICATION_ERROR)
        if can_navigate_back:
            xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")
        return

    url = stream["url"]

    if stream.get("manifest_type") == "mpd":
        li = xbmcgui.ListItem(path=url)
        li.setInfo("video", {"title": channel_id})
        li.setProperty("inputstream", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "mpd")
        li.setMimeType("application/dash+xml")
        li.setContentLookup(False)
        hdrs = stream.get("headers") if isinstance(stream.get("headers"), dict) else {}
        if hdrs:
            hdr_str = "&".join(f"{k}={quote(str(v))}" for k, v in hdrs.items() if v is not None)
            li.setProperty("inputstream.adaptive.manifest_headers", hdr_str)
            li.setProperty("inputstream.adaptive.stream_headers", hdr_str)
        xbmcplugin.setResolvedUrl(addon_handle, True, li)
        if can_navigate_back:
            xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")
        return

    final_url = _build_url_with_headers(url, stream) if isinstance(stream, dict) else url

    li = xbmcgui.ListItem(path=final_url)
    li.setInfo("video", {"title": channel_id})
    li.setContentLookup(False)
    _apply_inputstream_for_provider(li, final_url, provider=stream.get("provider", ""))

    xbmcplugin.setResolvedUrl(addon_handle, True, li)

    if can_navigate_back:
        xbmc.executebuiltin(f"Container.Update({build_url({'action': 'list_search_results', 'query': query})})")


# ──────────────── Sport Live ────────────────────────────────────

_SPORT_ICON_FILE = {
    "fotbal":      "sport/soccer.png",
    "tenis":       "sport/tennis.png",
    "baschet":     "sport/basketball.png",
    "motorsport":  "sport/motorsport.png",
    "hochei":      "sport/hockey.png",
    "box_mma":     "sport/fights.png",
    "ciclism":     "sport/cycling.png",
    "rugby":       "sport/rugby.png",
    "volei":       "sport/volleyball.png",
    "handbal":     "sport/handball.png",
    "atletism":    "sport/athletics.png",
    "golf":        "sport/golf.png",
    "inot":        "sport/swimming.png",
    "sport_iarna": "sport/winter.png",
    "sport":       "sport/sport.png",
}

_SPORT_ICONS = {
    "fotbal":      "⚽",
    "tenis":       "🎾",
    "baschet":     "🏀",
    "motorsport":  "🏎️",
    "hochei":      "🏒",
    "box_mma":     "🥊",
    "ciclism":     "🚴",
    "volei":       "🏐",
    "handbal":     "🤾",
    "rugby":       "🏉",
    "atletism":    "🏃",
    "golf":        "⛳",
    "inot":        "🏊",
    "sport_iarna": "⛷️",
    "sport":       "🏟️",
}


def list_sports_menu():
    xbmcplugin.setContent(addon_handle, "addons")
    choice = xbmcgui.Dialog().select(_t("menu_sports"), ["6 ore", "12 ore", "24 ore"])
    if choice == -1:
        xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        return
    hours = [6, 12, 24][choice]

    data = get_sports_schedule(hours=hours)
    if not data or not data.get("sports"):
        xbmcgui.Dialog().notification("ThraxTV", _t("sport_no_events"), xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    icons_base = xbmcvfs.translatePath("special://home/addons/plugin.video.thraxtv/resources/icons/")

    for sport_key, info in data["sports"].items():
        count = info.get("count", 0)
        if count == 0:
            continue
        label_text = info.get("label", sport_key)
        live_cnt = sum(1 for e in info.get("events", []) if e.get("is_live"))
        emoji = _SPORT_ICONS.get(sport_key, "🏟️")

        if live_cnt:
            label = "%s  [COLOR=lime]%d live[/COLOR]  |  %d total" % (label_text, live_cnt, count)
        else:
            label = "%s  [COLOR=gray]%d events[/COLOR]" % (label_text, count)

        url = build_url({"action": "list_sport_events", "sport": sport_key, "hours": hours})
        li = xbmcgui.ListItem(label=label)

        icon_rel = _SPORT_ICON_FILE.get(sport_key)
        if icon_rel:
            thumb = icons_base + icon_rel
        else:
            thumb = xbmcvfs.translatePath("special://home/addons/plugin.video.thraxtv/icon.png")
        li.setArt({"thumb": thumb, "icon": thumb})

        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

    xbmcplugin.setPluginCategory(addon_handle, _t("menu_sports"))
    xbmcplugin.endOfDirectory(addon_handle)


def list_sport_events(params):
    from datetime import datetime as _dt
    xbmcplugin.setContent(addon_handle, "videos")
    sport_key = params.get("sport", "")
    hours = int(params.get("hours", 6))

    data = get_sports_schedule(hours=hours)
    if not data:
        xbmcgui.Dialog().notification("ThraxTV", _t("sport_no_events"), xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    sport_info = data.get("sports", {}).get(sport_key, {})
    events = sport_info.get("events", [])

    if not events:
        xbmcgui.Dialog().notification("ThraxTV", _t("sport_no_events"), xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    favs = set(get_favorites())

    for ev in events:
        title  = ev.get("title", "")
        ch     = ev.get("channel", {})
        ch_id  = ch.get("id", "")
        ch_name = ch.get("name", "")
        logo   = ch.get("logo", "")
        is_live = ev.get("is_live", False)
        progress = ev.get("progress", "")
        desc   = ev.get("desc", "")

        try:
            ts_s = _dt.fromtimestamp(ev["start"]).strftime("%H:%M")
            ts_e = _dt.fromtimestamp(ev["stop"]).strftime("%H:%M") if ev.get("stop") else ""
            time_range = "%s-%s" % (ts_s, ts_e) if ts_e else ts_s
        except Exception:
            time_range = ""

        if is_live:
            prog_str = ("  [COLOR=orange]%s[/COLOR]" % progress) if progress else ""
            label = "[COLOR=lime]▶ LIVE[/COLOR]%s  [B]%s[/B]  [COLOR=gray]%s[/COLOR]" % (prog_str, title, ch_name)
        else:
            label = "[COLOR=gray]%s[/COLOR]  %s  [COLOR=gray]%s[/COLOR]" % (time_range, title, ch_name)

        plot_parts = []
        if ch_name:
            plot_parts.append("[B]%s[/B]" % ch_name)
        if time_range:
            plot_parts.append(time_range)
        if is_live and progress:
            try:
                pct = int(progress.replace("%", "").strip())
                filled = round(pct / 10)
                bar = "[COLOR=orange]%s%s[/COLOR] %s" % ("█" * filled, "░" * (10 - filled), progress)
                plot_parts.append(bar)
            except Exception:
                pass
        if desc:
            plot_parts.append(desc)
        plot = "\n".join(plot_parts)

        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": logo})
        li.setInfo("video", {"title": title, "plot": plot})
        li.setProperty("IsPlayable", "true")

        is_fav = ch_id in favs
        fav_label = _t("fav_remove_cm") if is_fav else _t("fav_add_cm")
        country_code = (ch.get("country") or "ro").lower()
        cm = [
            (_t("epg_cm"), "RunPlugin(%s)" % build_url({"action": "show_epg", "id": ch_id, "country": country_code})),
            (fav_label, "RunPlugin(%s)" % build_url({"action": "toggle_favorite", "id": ch_id, "is_fav": "1" if is_fav else "0"})),
        ]
        li.addContextMenuItems(cm)

        if _get_playback_mode():
            play_url = build_url({"action": "play", "id": ch_id})
        else:
            play_url = build_url({"action": "choose_source", "id": ch_id, "title": title})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=play_url, listitem=li, isFolder=False)

    sport_label = sport_info.get("label", sport_key)
    xbmcplugin.setPluginCategory(addon_handle, sport_label)
    xbmcplugin.endOfDirectory(addon_handle)


# ──────────────── Campionatul Mondial 2026 ──────────────────────

_WC_STATUS_COLOR = {
    "STATUS_SCHEDULED":    "gray",
    "STATUS_IN_PROGRESS":  "lime",
    "STATUS_FINAL":        "orange",
}

# ──────────────── Dispatcher ────────────────────────────────────

params = dict(parse_qs(sys.argv[2][1:]))
if "action" in params:
    action = params["action"][0]
    flat = {k: v[0] for k, v in params.items()}
    if action == "list_countries":
        list_countries()
    elif action == "list_country_categories":
        list_country_categories(flat)
    elif action == "list_channels":
        list_channels(flat)
    elif action == "list_categories":
        list_categories()
    elif action == "list_category_channels":
        list_category_channels(flat)
    elif action == "radio_countries":
        radio_countries()
    elif action == "radio_stations":
        radio_stations_list(flat)
    elif action == "radio_play":
        radio_play(flat)
    elif action in ("search", "list_search_results"):
        list_search_results(flat)
    elif action == "show_epg":
        show_epg(flat)
    elif action == "choose_source":
        choose_source(flat)
    elif action == "play":
        play_channel(flat)
    elif action == "clear_cache":
        clear_cache_action()
    elif action == "list_favorites":
        list_favorites()
    elif action == "toggle_favorite":
        toggle_favorite(flat)
    elif action == "list_sports_menu":
        list_sports_menu()
    elif action == "list_sport_events":
        list_sport_events(flat)
else:
    main_menu()
