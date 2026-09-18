import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from resources.lib.sites import api

_ADDON = xbmcaddon.Addon()
_ICONS_SITES   = xbmcvfs.translatePath('special://home/addons/plugin.video.sarmis/resources/icons/sites/')
_ICON_SEARCH   = xbmcvfs.translatePath('special://home/addons/plugin.video.sarmis/resources/icons/search.png')

_handle    = int(sys.argv[1])
PLUGIN_URL = sys.argv[0]


def _url(**kwargs):
    from urllib.parse import urlencode, quote
    parts = []
    for k, v in kwargs.items():
        if v is not None:
            parts.append(f"{k}={quote(str(v), safe='')}")
    return PLUGIN_URL + "?" + "&".join(parts)


def _li(title, poster="", fanart="", plot="", year="", rating=0, mediatype="video"):
    li = xbmcgui.ListItem(label=title)
    li.setArt({"thumb": poster, "icon": poster, "poster": poster,
                "fanart": fanart or poster})
    tag = li.getVideoInfoTag()
    tag.setTitle(title)
    if plot:
        tag.setPlot(plot)
    if year:
        try:
            tag.setYear(int(year))
        except Exception:
            pass
    if rating:
        tag.setRating(float(rating))
    tag.setMediaType(mediatype)
    return li


def show_site_menu(site, site_name):
    xbmcplugin.setPluginCategory(_handle, site_name)
    site_icon = _ICONS_SITES + f'{site}.png'
    cats = api.categories(site)
    for cat in cats:
        li = xbmcgui.ListItem(label=cat["name"])
        li.setArt({'icon': site_icon, 'thumb': site_icon})
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_browse", site=site, url=cat["url"], page=1, site_name=site_name),
            li, isFolder=True
        )
    li_s = xbmcgui.ListItem(label="[Caută]")
    li_s.setArt({'icon': _ICON_SEARCH, 'thumb': _ICON_SEARCH})
    xbmcplugin.addDirectoryItem(
        _handle,
        _url(action="site_search", site=site, site_name=site_name),
        li_s, isFolder=True
    )
    xbmcplugin.endOfDirectory(_handle)


def show_browse(site, url, page, site_name):
    xbmcplugin.setPluginCategory(_handle, site_name)
    xbmcplugin.setContent(_handle, "movies")
    data = api.browse(site, url, page)
    if not data:
        xbmcplugin.endOfDirectory(_handle)
        return
    for it in data.get("items", []):
        _add_item_entry(site, it, site_name)
    if data.get("has_next"):
        li = xbmcgui.ListItem(label=f"Pagina {page + 1} »")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_browse", site=site, url=url, page=page + 1, site_name=site_name),
            li, isFolder=True
        )
    xbmcplugin.endOfDirectory(_handle)


def show_search_all(enabled_sites):
    stored_q = _ADDON.getSetting("sq_all")
    if stored_q:
        _show_search_all_results(enabled_sites, stored_q)
        return
    query = xbmcgui.Dialog().input("Caută pe toate site-urile", type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    _ADDON.setSetting("sq_all", query)
    _show_search_all_results(enabled_sites, query)


def _show_search_all_results(enabled_sites, query):
    xbmcplugin.setPluginCategory(_handle, f"Toate – {query}")
    xbmcplugin.setContent(_handle, "movies")
    li_new = xbmcgui.ListItem(label="[Caută din nou]")
    li_new.setArt({'icon': _ICON_SEARCH, 'thumb': _ICON_SEARCH})
    xbmcplugin.addDirectoryItem(
        _handle, _url(action="search_all_new"),
        li_new, isFolder=True
    )
    data = api.search_all(query, enabled_sites)
    for it in (data.get("items") or []):
        site      = it.get("site", "")
        site_name = it.get("site_name", site)
        label_suffix = f"  [{site_name}]"
        orig_label = it.get("title", "")
        it_display = dict(it, title=orig_label + label_suffix)
        _add_item_entry(site, it_display, site_name)
    xbmcplugin.endOfDirectory(_handle, succeeded=True, cacheToDisc=False)


def show_search_all_new(enabled_sites):
    _ADDON.setSetting("sq_all", "")
    query = xbmcgui.Dialog().input("Caută pe toate site-urile", type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    _ADDON.setSetting("sq_all", query)
    _show_search_all_results(enabled_sites, query)


def show_search(site, site_name):
    # Container.Update e blocat de Kodi cu "updating in progress" atât timp cât plugin-ul
    # curent e în stare "loading" (chiar și fără endOfDirectory). Soluție: stocăm ultima
    # interogare în addon settings și afișăm rezultatele direct în handle-ul curent.
    # Astfel când Kodi re-rulează plugin-ul la navigare înapoi (din stream), nu redeschide
    # dialogul — arată direct ultimele rezultate.
    stored_q = _ADDON.getSetting(f"sq_{site}")
    if stored_q:
        _show_search_results(site, site_name, stored_q, page=1)
        return
    _search_dialog(site, site_name)


def _search_dialog(site, site_name):
    query = xbmcgui.Dialog().input(f"Caută pe {site_name}", type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    _ADDON.setSetting(f"sq_{site}", query)
    _show_search_results(site, site_name, query, page=1)


def _show_search_results(site, site_name, query, page):
    xbmcplugin.setPluginCategory(_handle, f"{site_name} – {query}")
    xbmcplugin.setContent(_handle, "movies")
    li_new = xbmcgui.ListItem(label=f"[Caută din nou pe {site_name}]")
    xbmcplugin.addDirectoryItem(
        _handle, _url(action="site_search_new", site=site, site_name=site_name),
        li_new, isFolder=True
    )
    data = api.search(site, query, page)
    for it in (data.get("items") if data else []):
        _add_item_entry(site, it, site_name)
    if data and data.get("has_next"):
        li = xbmcgui.ListItem(label=f"Pagina {page + 1} »")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_search_page", site=site, q=query, page=page + 1, site_name=site_name),
            li, isFolder=True
        )
    xbmcplugin.endOfDirectory(_handle, succeeded=True, cacheToDisc=False)


def show_search_new(site, site_name):
    """Șterge interogarea stocată și deschide dialogul pentru o căutare nouă."""
    _ADDON.setSetting(f"sq_{site}", "")
    _search_dialog(site, site_name)


def show_search_page(site, query, page, site_name):
    xbmcplugin.setPluginCategory(_handle, f"{site_name} – {query}")
    xbmcplugin.setContent(_handle, "movies")
    data = api.search(site, query, page)
    for it in (data.get("items") if data else []):
        _add_item_entry(site, it, site_name)
    if data and data.get("has_next"):
        li = xbmcgui.ListItem(label=f"Pagina {page + 1} »")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_search_page", site=site, q=query, page=page + 1, site_name=site_name),
            li, isFolder=True
        )
    xbmcplugin.endOfDirectory(_handle)


def _add_item_entry(site, it, site_name):
    title  = it.get("title", "")
    poster = it.get("poster", "")
    year   = it.get("year", "")
    itype  = it.get("type", "movie")
    url    = it.get("url", "")

    if itype == "folder":
        # Unele site-uri dau poster și pentru foldere (serial/sezon); când nu dau,
        # punem iconița site-ului ca să nu rămână intrarea fără artă.
        art = poster or (_ICONS_SITES + f"{site}.png")
        li = xbmcgui.ListItem(label=title)
        li.setArt({"icon": art, "thumb": art, "poster": poster or art})
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_browse", site=site, url=url, page=1, site_name=site_name),
            li, isFolder=True
        )
    elif itype == "serial":
        li = _li(title, poster=poster, year=year, mediatype="tvshow")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_item_serial", site=site, url=url,
                 title=title, poster=poster, site_name=site_name),
            li, isFolder=True
        )
    elif itype == "episode":
        li = _li(title, poster=poster, year=year, mediatype="episode")
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_play", site=site, url=url, title=title),
            li, isFolder=False
        )
    else:
        li = _li(title, poster=poster, year=year, mediatype="movie")
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_play", site=site, url=url, title=title),
            li, isFolder=False
        )


def show_item_serial(site, url, title, poster, site_name):
    xbmcplugin.setPluginCategory(_handle, title)
    data    = api.item(site, url)
    seasons = (data or {}).get("seasons", [])

    if len(seasons) > 1:
        xbmcplugin.setContent(_handle, "seasons")
        for s in seasons:
            s_url   = s.get("url", url)
            s_label = s.get("label") or f"Sezonul {s.get('number', '')}"
            li = _li(s_label, poster=s.get("poster") or poster, mediatype="season")
            xbmcplugin.addDirectoryItem(
                _handle,
                _url(action="site_episodes", site=site, url=s_url,
                     title=title, poster=poster, site_name=site_name),
                li, isFolder=True
            )
        xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)
    elif seasons:
        show_episodes(site, seasons[0].get("url", url), title, poster, site_name)
    else:
        show_episodes(site, url, title, poster, site_name)


def show_seasons(site, url, title, poster, site_name):
    show_item_serial(site, url, title, poster, site_name)


def show_episodes(site, url, title, poster, site_name, ep_page=1):
    xbmcplugin.setPluginCategory(_handle, title)
    xbmcplugin.setContent(_handle, "episodes")

    raw = api.episodes(site, url, ep_page=ep_page)

    if isinstance(raw, dict):
        eps      = raw.get("items", [])
        has_next = raw.get("has_next", False)
        cur_page = raw.get("page", ep_page)
    else:
        eps      = raw or []
        has_next = False
        cur_page = ep_page

    if not eps:
        data = api.item(site, url)
        eps  = (data or {}).get("episodes", [])
        has_next = False

    for ep in eps:
        n         = ep.get("number", "")
        t         = ep.get("title") or ep.get("label") or f"Episodul {n}"
        ep_url    = ep.get("url", url)
        ep_poster = ep.get("poster") or poster
        li = _li(t, poster=ep_poster, mediatype="episode")
        li.setProperty("IsPlayable", "true")
        tag = li.getVideoInfoTag()
        if n:
            try:
                tag.setEpisode(int(n))
            except (ValueError, TypeError):
                pass
        tag.setTvShowTitle(title)
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_play_ep", site=site, url=ep_url, title=t),
            li, isFolder=False
        )

    if has_next:
        next_p = cur_page + 1
        li = xbmcgui.ListItem(label=f"Pagina {next_p} »")
        xbmcplugin.addDirectoryItem(
            _handle,
            _url(action="site_episodes", site=site, url=url,
                 title=title, poster=poster, site_name=site_name, ep_page=next_p),
            li, isFolder=True
        )

    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def play_item(site, url, title):
    data = api.item(site, url)
    if not data:
        _pick_and_play([], title)
        return
    # Dacă server-ul detectează un serial, anulăm playback și navigăm la sezoane
    if data.get("type") == "serial" and data.get("seasons"):
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        poster = data.get("poster", "")
        nav_url = _url(action="site_item_serial", site=site, url=url,
                       title=title, poster=poster, site_name=site)
        xbmc.executebuiltin(f"Container.Update({nav_url})")
        return
    _pick_and_play(data.get("sources", []), title, page_url=url)


def play_episode(site, url, title):
    sources = api.episode_sources(site, url)
    if not sources:
        data    = api.item(site, url)
        sources = (data or {}).get("sources", [])
    _pick_and_play(sources, title, page_url=url)


def _sub_basename(page_url):
    """Construiește baza numelui de fișier din URL-ul paginii.
    Episod → Show.Title.2026.S01E03
    Film   → Show.Title.2026
    """
    import re as _re

    def _slug_to_title_year(slug):
        parts = slug.split("-")
        title_parts, year = [], ""
        for p in parts:
            if _re.fullmatch(r"\d{4}", p) and 1900 <= int(p) <= 2100:
                year = p
                break
            title_parts.append(p.capitalize())
        return ".".join(title_parts), year

    ep_m = _re.search(r"/([^/]+)/s(\d+)-e(\d+)/?", page_url)
    # gofilme: /episoade/show-title-sezonul-N-episodul-M/
    gf_m = _re.search(r"/episoade/([^/]+)-sezonul-(\d+)-episodul-(\d+)/?", page_url) if not ep_m else None
    if ep_m:
        t, y = _slug_to_title_year(ep_m.group(1))
        tag  = f"S{int(ep_m.group(2)):02d}E{int(ep_m.group(3)):02d}"
        base = f"{t}.{y}.{tag}" if y else f"{t}.{tag}"
    elif gf_m:
        t, y = _slug_to_title_year(gf_m.group(1))
        tag  = f"S{int(gf_m.group(2)):02d}E{int(gf_m.group(3)):02d}"
        base = f"{t}.{y}.{tag}" if y else f"{t}.{tag}"
    else:
        seg_m = _re.search(r"/([^/]+-\d{4}-[^/]+)/", page_url)
        if seg_m:
            t, y = _slug_to_title_year(seg_m.group(1))
            base = f"{t}.{y}" if y else t
        else:
            base = "sarmis"
    return _re.sub(r"\.{2,}", ".", base).strip(".")


def _prepare_subs(sub_info_url, page_url):
    """Descarcă VTT-urile în addon_data/subs/ cu naming Show.Title.Year.SxxExx.Language.vtt.
    Returnează lista de căi locale (sau URL-uri directe ca fallback).
    """
    import re as _re
    import requests as _req
    import xbmcvfs

    try:
        data = _req.get(sub_info_url, timeout=10).json()
        if not isinstance(data, list):
            return []
    except Exception:
        return []

    subs_dir = "special://profile/addon_data/plugin.video.sarmis/subs/"
    xbmcvfs.mkdirs(subs_dir)
    base = _sub_basename(page_url) if page_url else "sarmis"

    default = [s for s in data if s.get("default") and s.get("file")]
    others  = [s for s in data if not s.get("default") and s.get("file")]
    paths   = []
    for sub in default + others:
        vtt_url   = sub["file"]
        label     = _re.sub(r"[^a-zA-Z0-9]", "", sub.get("label", "Unknown"))
        filename  = f"{base}.{label}.vtt"
        real_path = xbmcvfs.translatePath(subs_dir + filename)
        try:
            r = _req.get(vtt_url, timeout=10)
            r.raise_for_status()
            with open(real_path, "wb") as f:
                f.write(r.content)
            paths.append(real_path)
        except Exception:
            paths.append(vtt_url)
    return paths


def _resolve_streamflash(embed_url):
    """Apelează Thrax /streamflash/resolve → (stream_url, sub_url)."""
    try:
        from . import api as _api
        data = _api._get("/streamflash/resolve", url=embed_url)
        if data and data.get("url"):
            xbmc.log(f"[Sarmis] Streamflash resolved: {data['url'][:80]}", xbmc.LOGINFO)
            return data["url"], data.get("sub")
    except Exception as e:
        xbmc.log(f"[Sarmis] Streamflash resolve eroare: {e}", xbmc.LOGWARNING)
    return None, None


def _resolve_vidhide(embed_url):
    """Rezolvă embed-uri VidHide/minochinos: decodifică JS packed → HLS + sub VTT Romanian."""
    import re as _re
    import requests as _req
    try:
        host = _re.search(r"https?://([^/]+)", embed_url).group(1)
        r = _req.get(embed_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133.0.0.0 Safari/537.36",
            "Referer": f"https://{host}/",
        }, timeout=15)
        html = r.text

        # Decodifică JS packer standard: eval(function(p,a,c,k,e,d){...}('...','base',count,'k0|k1|...'))
        pm = _re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{[^}]+\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)\)\)",
            html, _re.DOTALL
        )
        if pm:
            p_str, base, k_list = pm.group(1), int(pm.group(2)), pm.group(4).split("|")
            def _repl(m):
                try:
                    n = int(m.group(0), base)
                except ValueError:
                    return m.group(0)
                return k_list[n] if n < len(k_list) and k_list[n] else m.group(0)
            decoded = _re.sub(r'\b\w+\b', _repl, p_str)
        else:
            decoded = html

        # Extrage HLS: links.hls2 / links.hls4 sau sources:[{file:"..."}]
        hls = None
        for pat in [
            r'"hls\d*"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"',
            r'file\s*:\s*(?:links\.hls\S+\|\|)*links\.(\w+)',
            r'sources\s*:\s*\[\s*\{[^}]*file\s*:\s*(?:links\.\w+\s*\|\|\s*)*links\.(\w+)',
        ]:
            m = _re.search(pat, decoded)
            if m:
                # primul pattern returnează URL direct
                if m.group(1).startswith("http"):
                    hls = m.group(1)
                    break

        # fallback: cauta orice URL m3u8 în decoded
        if not hls:
            m = _re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', decoded)
            if m:
                hls = m.group(1)

        # Extrage subtitle Romanian (kind:captions cu _rum.vtt sau label:Romanian)
        sub = None
        sub_m = _re.search(
            r'\{[^}]*file\s*:\s*"(https?://[^"]+_rum\.vtt[^"]*)"[^}]*kind\s*:\s*"captions"',
            decoded
        )
        if not sub_m:
            sub_m = _re.search(
                r'\{[^}]*file\s*:\s*"(https?://[^"]+\.vtt[^"]*)"[^}]*(?:label\s*:\s*"Romanian"|kind\s*:\s*"captions")',
                decoded
            )
        if sub_m:
            sub = sub_m.group(1)

        if hls:
            xbmc.log(f"[Sarmis] VidHide resolved HLS: {hls[:80]}", xbmc.LOGINFO)
            return hls, sub
    except Exception as e:
        xbmc.log(f"[Sarmis] VidHide resolve eroare: {e}", xbmc.LOGWARNING)
    return None, None


_MEGACLOUD_REFERERS = [
    "https://megacloud.blog/",
    "https://megacloud.tv/",
    "https://megacloud.store/",
    "https://megacloud.co/",
]


def _resolve_byse_cdn(cdn_url, byse_referer):
    """Byse CDN URL (master.m3u8?...&p=0) → fetch master.m3u cu Referer Megacloud → parse variante."""
    import re as _re, requests as _req
    try:
        base_url = cdn_url.split("|")[0] if "|" in cdn_url else cdn_url
        m = _re.match(r'(https?://[^/]+/hls\d+/\d+/\d+/[^/_]+_x/)', base_url)
        if not m:
            return None
        master_url = m.group(1) + "master.m3u"
        xbmc.log(f"[Sarmis] Byse CDN master: {master_url[:80]}", xbmc.LOGINFO)

        # CDN validează Referer: servește master.m3u doar pt Megacloud hosts, nu pt Byse
        # Încerc în ordine: Megacloud hosts → Byse → fără Referer
        referers_to_try = _MEGACLOUD_REFERERS + ([byse_referer] if byse_referer else []) + [None]
        r_ok = None
        used_ref = None
        for ref in referers_to_try:
            hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
            if ref:
                hdrs["Referer"] = ref
            try:
                rr = _req.get(master_url, headers=hdrs, timeout=10)
                if rr.ok:
                    r_ok = rr
                    used_ref = ref
                    xbmc.log(f"[Sarmis] Byse CDN master OK Referer={ref}", xbmc.LOGINFO)
                    break
                else:
                    xbmc.log(f"[Sarmis] Byse CDN master {rr.status_code} Referer={ref}", xbmc.LOGINFO)
            except Exception as _e:
                xbmc.log(f"[Sarmis] Byse CDN master exc Referer={ref}: {_e}", xbmc.LOGWARNING)

        if not r_ok:
            xbmc.log(f"[Sarmis] Byse CDN master.m3u: 404 toate Referer-ele", xbmc.LOGWARNING)
            return None
        r = r_ok
        headers = {"Referer": used_ref} if used_ref else {}
        lines = r.text.splitlines()
        xbmc.log(f"[Sarmis] Byse CDN master ({len(lines)} linii): {r.text[:300].replace(chr(10),'|')}", xbmc.LOGINFO)
        base = master_url.rsplit("/", 1)[0]
        variants = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXT-X-STREAM-INF"):
                bw_m = _re.search(r"BANDWIDTH=(\d+)", line)
                bw = int(bw_m.group(1)) if bw_m else 0
                if i + 1 < len(lines):
                    v = lines[i + 1].strip()
                    if v and not v.startswith("#"):
                        if not v.startswith("http"):
                            v = base + "/" + v
                        variants.append((bw, v))
                i += 2
                continue
            i += 1
        if variants:
            ordered = sorted(variants, key=lambda x: (0 if "&p=0" in x[1] or "?p=0" in x[1] else 1, -x[0]))
            for _, v in ordered:
                try:
                    rh = _req.head(v, headers=headers, timeout=5, allow_redirects=True)
                    status = rh.status_code
                except Exception:
                    status = 200
                xbmc.log(f"[Sarmis] Byse CDN variant {status}: {v[:80]}", xbmc.LOGINFO)
                if status in (200, 206, 302):
                    return f"{v}|Referer={used_ref}" if used_ref else v
    except Exception as e:
        xbmc.log(f"[Sarmis] Byse CDN eroare: {e}", xbmc.LOGWARNING)
    return None


_MEGACLOUD_HOSTS = ("megacloudx.net", "megacloud.blog", "megacloud.tv", "megacloud.store", "megacloud.co")


def _resolve_byse(embed_url, speculative=False):
    """Byse embed → embed_frame_url via API → Megacloud cu același media_id.

    `speculative=True` când am ajuns aici doar după forma URL-ului (/e/{id}), nu
    după un domeniu Byse cunoscut: atunci nu mai încercăm hosturile Megacloud pe
    ghicite, pentru că 5 încercări costă ~30 de secunde pe un embed care e, de
    fapt, dsvplay/playmogo/listeamed și s-ar rezolva instant prin resolveurl.
    """
    import re as _re, requests as _req
    media_id = None
    looks_byse = False
    try:
        m = _re.search(r'/e/([0-9a-zA-Z]+)', embed_url)
        if not m:
            return None
        media_id = m.group(1)
        host = _re.search(r"https?://([^/]+)", embed_url).group(1)
        ref = f"https://{host}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; TX6s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
            "Referer": ref,
            "Origin": ref.rstrip("/"),
        }
        def _byse_spa_fallback():
            # Byse SPA player pe domenii custom/rotative (ex: gn1r5n.org "Byse Frontend").
            # Fluxul anti-bot (challenge/attest EC P-256 + PoW + AES-GCM) e greu:
            # PoW-ul pur-Python e lent și cu varianță mare pe ARM (10-60s pe box).
            #
            # 1) Încercăm ÎNTÂI serverul (/byse/resolve) — rulează PoW-ul pe x86 (rapid).
            #    Token-ul CDN e IP-bound, deci merge doar dacă device-ul iese pe același IP
            #    public ca serverul (server + box pe aceeași rețea). Întoarce {url, ua};
            #    UA-ul e obligatoriu (token UA-bound) → îl atașăm ca |User-Agent=.
            try:
                data = api._get("/byse/resolve", url=embed_url)
                if data and data.get("url"):
                    su = data["url"]
                    if data.get("ua"):
                        sep = "&" if "|" in su else "|"
                        su = f"{su}{sep}User-Agent={data['ua']}"
                    xbmc.log(f"[Sarmis] Byse server resolve OK: {su[:80]}", xbmc.LOGINFO)
                    return su
            except Exception as _e:
                xbmc.log(f"[Sarmis] Byse server resolve err: {_e}", xbmc.LOGWARNING)
            # 2) Fallback on-device: resolveurl bundle-uie ByseResolver (gujal 2025) cu tot
            #    fluxul; e gated pe o listă fixă de domenii → apelăm get_media_url DIRECT.
            #    Merge pe orice IP, dar PoW-ul rulează pe device (lent pe ARM).
            try:
                from resolveurl.plugins.byse import ByseResolver
                ru_url = ByseResolver().get_media_url(host, media_id)
                if ru_url:
                    xbmc.log(f"[Sarmis] Byse direct resolve OK: {ru_url[:80]}", xbmc.LOGINFO)
                    return ru_url
            except Exception as _re:
                xbmc.log(f"[Sarmis] Byse direct resolve err: {_re}", xbmc.LOGWARNING)
            return None

        for path in (f"api/videos/{media_id}/details", f"api/videos/{media_id}/embed/details"):
            try:
                resp = _req.get(f"{ref}{path}", headers=headers, timeout=10)
                if resp.ok:
                    try:
                        payload = resp.json()
                    except Exception:
                        # 200 cu HTML: multe site-uri (mixdrop, listeamed) răspund
                        # așa la căi necunoscute — nu e un API Byse.
                        xbmc.log(f"[Sarmis] Byse {path}: 200 dar nu e JSON, nu e Byse", xbmc.LOGINFO)
                        break
                    looks_byse = True
                    frame = payload.get("embed_frame_url")
                    if frame:
                        xbmc.log(f"[Sarmis] Byse embed_frame: {frame[:80]}", xbmc.LOGINFO)
                        if any(mc in frame for mc in _MEGACLOUD_HOSTS):
                            result = _resolve_megacloud(frame)
                            if result:
                                return result
                        else:
                            result = _byse_spa_fallback()
                            if result:
                                return result
                    else:
                        xbmc.log(f"[Sarmis] Byse {path}: fără embed_frame_url, încerc SPA fallback", xbmc.LOGINFO)
                        result = _byse_spa_fallback()
                        if result:
                            return result
                    xbmc.log(f"[Sarmis] Byse {path}: fără embed_frame rezolvabil", xbmc.LOGINFO)
                    break
                xbmc.log(f"[Sarmis] Byse {path}: {resp.status_code}", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[Sarmis] Byse {path} exc: {e}", xbmc.LOGWARNING)
                continue
    except Exception as e:
        xbmc.log(f"[Sarmis] Byse API eroare: {e}", xbmc.LOGWARNING)
        return None

    if not media_id:
        return None
    if speculative and not looks_byse:
        xbmc.log("[Sarmis] Byse (shape match): API-ul nu răspunde ca Byse, renunț", xbmc.LOGINFO)
        return None

    # Byse și Megacloud împart același media_id — _resolve_megacloud încarcă
    # pagina embed mai întâi (CDN session), apoi fetch master.m3u → funcționează
    for mc_host in _MEGACLOUD_HOSTS:
        mc_url = f"https://{mc_host}/e/{media_id}"
        xbmc.log(f"[Sarmis] Byse→Megacloud {mc_host}: {media_id}", xbmc.LOGINFO)
        try:
            result = _resolve_megacloud(mc_url)
            if result:
                xbmc.log(f"[Sarmis] Byse→Megacloud OK: {mc_host}", xbmc.LOGINFO)
                return result
        except Exception as _e:
            xbmc.log(f"[Sarmis] Byse→{mc_host} exc: {_e}", xbmc.LOGWARNING)
    return None


def _resolve_megacloud(embed_url):
    """Extrage URL HLS din pagina embed Megacloud: var HLS = '...'"""
    import re as _re
    import requests as _req
    try:
        host = _re.search(r"https?://([^/]+)", embed_url).group(1)
        referer = f"https://{host}/"
        r = _req.get(embed_url, headers={"Referer": referer}, timeout=15)
        m = _re.search(r'var\s+HLS\s*=\s*["\']([^"\']+)["\']', r.text)
        if not m:
            return None
        master_url = m.group(1)
        xbmc.log(f"[Sarmis] Megacloud master: {master_url[:80]}", xbmc.LOGINFO)

        # Descarcă master.m3u, alege varianta cu p=0 (fără ASN-binding)
        try:
            r2 = _req.get(master_url, headers={"Referer": referer}, timeout=10)
            if r2.ok:
                lines = r2.text.splitlines()
                content_log = r2.text[:500].replace('\n', '|').replace('\r', '')
                xbmc.log(f"[Sarmis] Megacloud master ({len(lines)} linii): {content_log}", xbmc.LOGINFO)
                base = master_url.rsplit('/', 1)[0]
                variants = []  # lista (bw, url)
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line.startswith('#EXT-X-STREAM-INF'):
                        bw_m = _re.search(r'BANDWIDTH=(\d+)', line)
                        bw = int(bw_m.group(1)) if bw_m else 0
                        if i + 1 < len(lines):
                            variant = lines[i + 1].strip()
                            if variant and not variant.startswith('#'):
                                if not variant.startswith('http'):
                                    variant = base + '/' + variant
                                variants.append((bw, variant))
                        i += 2
                        continue
                    elif line and not line.startswith('#'):
                        if not line.startswith('http'):
                            line = base + '/' + line
                        variants.append((0, line))
                    i += 1

                if variants:
                    # Preferă varianta cu p=0; altfel testează toate cu HEAD
                    ordered = sorted(variants, key=lambda x: (0 if '&p=0' in x[1] or '?p=0' in x[1] else 1, -x[0]))
                    for _, candidate in ordered:
                        try:
                            r_test = _req.head(candidate, headers={"Referer": referer}, timeout=5, allow_redirects=True)
                            status = r_test.status_code
                        except Exception:
                            status = 200  # nu putem testa, încearcă oricum
                        xbmc.log(f"[Sarmis] Megacloud variant test {status}: {candidate[:80]}", xbmc.LOGINFO)
                        if status in (200, 206, 302):
                            return f"{candidate}|Referer={referer}"
                    xbmc.log("[Sarmis] Megacloud: toate variantele eșuate, skip", xbmc.LOGWARNING)
                    return None
        except Exception as e2:
            xbmc.log(f"[Sarmis] Megacloud variant eroare: {e2}", xbmc.LOGWARNING)

        return f"{master_url}|Referer={referer}"
    except Exception as e:
        xbmc.log(f"[Sarmis] Megacloud resolve eroare: {e}", xbmc.LOGWARNING)
    return None


def _resolve_vk(embed_url, page_url=None):
    """VK embed → HLS M3U8 (rezolvat client-side: URL-ul HLS e IP-bound la IP-ul Kodi)."""
    import re as _re
    try:
        import requests as _req
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
        }
        if page_url:
            headers["Referer"] = page_url
        r = _req.get(embed_url, headers=headers, timeout=15)
        xbmc.log(f"[Sarmis] VK embed HTTP {r.status_code}, len={len(r.text)}", xbmc.LOGINFO)
        for qual in ("hls1080", "hls720", "hls480", "hls"):
            m = _re.search(r'"' + qual + r'":"(https:[^"]+)"', r.text)
            if m:
                return m.group(1).replace("\\/", "/")
        xbmc.log(f"[Sarmis] VK: nicio calitate HLS găsită în răspuns", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[Sarmis] VK resolve eroare: {e}", xbmc.LOGWARNING)
    return None


def _resolve_netu(embed_url, page_url=None):
    """netu.ac/waaw.ac: fetch /e/{id} cu requests, extrage m3u8 din HTML + pasează cookies la ISA.
    Mai rapid decât resolveurl (fără headless Chrome) și evită expirarea token-ului."""
    import re as _re_n
    try:
        import requests as _req
        # /f/{id} → /e/{id} (pagina embed reală cu player-ul)
        url = _re_n.sub(r'/(f)/', '/e/', embed_url, count=1)
        if page_url:
            from urllib.parse import quote as _qn
            sep = '&' if '?' in url else '?'
            url += f'{sep}http_referer={_qn(page_url)}'
        r = _req.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": page_url or embed_url,
        }, timeout=15)
        xbmc.log(f"[Sarmis] netu embed HTTP {r.status_code}, len={len(r.text)}", xbmc.LOGINFO)
        m = _re_n.search(r"src\s*:\s*['\"]([^'\"]+cfglobal[^'\"]+\.m3u8[^'\"]*)['\"]", r.text)
        if not m:
            m = _re_n.search(r"['\"]([^'\"]+cfglobal[^'\"]+\.m3u8[^'\"]*)['\"]", r.text)
        if m:
            m3u8 = m.group(1)
            # Pagina netu conține și un URL demo hardcodat (/secip/1/<token>/<ip>/<expirare>/),
            # cu expirare în 2020 și IP-ul altcuiva. Dacă îl trimitem la player,
            # redarea eșuează iar autoplay-ul nu mai încearcă sursa următoare —
            # deci verificăm întâi termenul de valabilitate din URL.
            exp = _re_n.search(r'/secip/\d+/[^/]+/[^/]+/(\d{9,})/', m3u8)
            if exp:
                import time as _t
                if int(exp.group(1)) < _t.time():
                    xbmc.log("[Sarmis] netu: URL expirat în pagină (demo), ignor", xbmc.LOGWARNING)
                    return None
            cookies = "; ".join(f"{k}={v}" for k, v in r.cookies.items())
            hdr = f"Referer={embed_url}"
            if cookies:
                hdr += f"&Cookie={cookies}"
            return f"{m3u8}|{hdr}"
        xbmc.log("[Sarmis] netu: nicio sursă m3u8 găsită", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[Sarmis] netu resolve eroare: {e}", xbmc.LOGWARNING)
    return None


def _resolve_netu_captcha(embed_url):
    """Fluxul complet netu din resolveurl (WaawResolver), cu captcha de click.

    Domeniile custom (ex. player.filmeonline.uk) nu sunt în lista plugin-ului,
    așa că îl apelăm direct. Cere o interacțiune a utilizatorului — netu chiar
    validează coordonatele click-ului — dar e singura cale reală când pagina nu
    expune un URL valid.
    """
    import re as _re_c
    try:
        m = _re_c.search(r'https?://([^/]+)/(?:e|f)/([^/?#]+)', embed_url)
        if not m:
            return None
        from resolveurl.plugins.waaw import WaawResolver
        url = WaawResolver().get_media_url(m.group(1), m.group(2))
        if url:
            xbmc.log(f"[Sarmis] netu (captcha) OK: {url[:80]}", xbmc.LOGINFO)
        return url
    except Exception as e:
        xbmc.log(f"[Sarmis] netu captcha eroare: {e}", xbmc.LOGWARNING)
    return None


def _resolve_source(src, page_url=None, interactive=True):
    """Rezolvă embed URL → (stream_url, sub_vtt) sau (None, None) dacă eșuează.

    `interactive=False` interzice resolverele care cer o acțiune a utilizatorului
    (netu/waaw validează coordonatele unui click pe captcha): în autoplay vrem să
    trecem tăcut la sursa următoare, nu să blocăm redarea cu un dialog.
    """
    embed_url = src.get("url", "")
    if not embed_url:
        return None, None

    # Extrage subtitrare RO din URL embed (gofilme Byse: c1_file=; Voe: subtitles[]=)
    sub_vtt = None
    try:
        import re as _re2
        from urllib.parse import urlparse as _uparse, parse_qs as _pqs, urlencode as _uenc, urlunparse as _uunp
        _p = _uparse(embed_url)
        _qs = _pqs(_p.query, keep_blank_values=True)
        # Format Byse/filmehd: c1_file=URL (română), c2_file=URL (engleză)
        if "c1_file" in _qs:
            sub_vtt = _qs["c1_file"][0]
        # Format Voe/filmeplayer: subtitles[]=Label;langCode;URL
        elif "subtitles[]" in _qs:
            for _s in _qs["subtitles[]"]:
                _parts = _s.split(";", 2)
                if len(_parts) == 3 and _parts[1].lower() in ("ro", "rum", "ron"):
                    sub_vtt = _parts[2]
                    break
        # Curăță toți parametrii cN_ și subtitles[] din embed URL
        _clean = {k: v for k, v in _qs.items()
                  if not _re2.match(r'c\d+_', k) and k != "subtitles[]"}
        if len(_clean) < len(_qs):
            embed_url = _uunp(_p._replace(query=_uenc(_clean, doseq=True)))
    except Exception:
        pass

    if ".m3u8" in embed_url or embed_url.endswith(".mp4"):
        return embed_url, sub_vtt
    if "megacloud" in embed_url:
        url = _resolve_megacloud(embed_url)
        return (url, sub_vtt) if url else (None, sub_vtt)
    if any(h in embed_url for h in ("sb1254w9megshle.org", "byselapuix.com", "byse")):
        url = _resolve_byse(embed_url)
        return (url, sub_vtt) if url else (None, sub_vtt)
    if "loom.com" in embed_url:
        url = api.resolve_loom(embed_url)
        xbmc.log(f"[Sarmis] Loom resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        return (url, sub_vtt) if url else (None, sub_vtt)
    if "vk.com" in embed_url or "vkvideo.ru" in embed_url:
        url = _resolve_vk(embed_url, page_url=page_url)
        xbmc.log(f"[Sarmis] VK resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        if url:
            return url, sub_vtt
        # Watch page URL (nu embed) — resolveurl poate reuși
    _netu_cookies = ""
    if any(h in embed_url for h in ("netu.ac", "waaw.ac", "netu.to")):
        # Prefetch DDoS Guard cookies — URL-ul real e generat de JS, îl rezolvă resolveurl
        try:
            import requests as _req_n, re as _re_nc
            _nc_url = _re_nc.sub(r'/f/', '/e/', embed_url, count=1).split('?')[0]
            _nc_r = _req_n.get(_nc_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": page_url or embed_url,
            }, timeout=8)
            _netu_cookies = "; ".join(f"{k}={v}" for k, v in _nc_r.cookies.items())
            xbmc.log(f"[Sarmis] netu cookies prefetched ({len(_netu_cookies)}c)", xbmc.LOGINFO)
        except Exception as _nc_e:
            xbmc.log(f"[Sarmis] netu prefetch eroare: {_nc_e}", xbmc.LOGWARNING)
        # fall through la resolveurl
    if "vsembed.ru" in embed_url or "vsembed.su" in embed_url:
        data = api.resolve_vsembed(embed_url)
        url  = (data or {}).get("url")
        ref  = (data or {}).get("referer", "")
        tok_url = (data or {}).get("token_url", "")
        # Tokenul e legat de IP-ul care îl cere, deci se ia aici, din Kodi;
        # unul luat de API pe server ar fi respins cu 403.
        if url and tok_url:
            try:
                import requests as _req_vse
                _h = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"}
                if ref:
                    _h["Referer"] = ref
                _t = _req_vse.get(tok_url, headers=_h, timeout=10)
                _tok = _t.text.strip() if _t.ok else ""
                if _tok:
                    url += ("&" if "?" in url else "?") + "token=" + _tok
                else:
                    xbmc.log("[Sarmis] VSEmbed: token gol", xbmc.LOGWARNING)
            except Exception as _te:
                xbmc.log(f"[Sarmis] VSEmbed token eroare: {_te}", xbmc.LOGWARNING)
        xbmc.log(f"[Sarmis] VSEmbed resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        if url:
            full = f"{url}|Referer={ref}" if ref else url
            return full, sub_vtt
        return None, sub_vtt
    if "streamflash.sx" in embed_url:
        url, svtt = _resolve_streamflash(embed_url)
        return url, svtt or sub_vtt
    if any(h in embed_url for h in ("minochinos.com", "vidhide.com", "ryderjet.com", "ghbrisk.com")):
        url, svtt = _resolve_vidhide(embed_url)
        return url, svtt or sub_vtt
    if "abyssplayer.com" in embed_url or "abysscdn.com" in embed_url or "short.icu" in embed_url:
        data = api._get("/abysscdn/resolve", url=embed_url)
        url  = (data or {}).get("url")
        xbmc.log(f"[Sarmis] AbyssCDN resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        if url:
            return url, sub_vtt
        return None, sub_vtt
    if "ok.ru/videoembed/" in embed_url:
        data = api._get("/okru/resolve", url=embed_url)
        url  = (data or {}).get("url")
        xbmc.log(f"[Sarmis] OK.ru resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        if url:
            ref = (data or {}).get("referer", "")
            return (f"{url}|Referer={ref}" if ref else url), sub_vtt
        return None, sub_vtt
    if "my.mail.ru" in embed_url:
        data = api._get("/mymail/resolve", url=embed_url)
        url  = (data or {}).get("url")
        xbmc.log(f"[Sarmis] Mail.ru resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        if url:
            return f"{url}|Referer=https://my.mail.ru/", sub_vtt
        return None, sub_vtt
    if "player.filmeonline.uk" in embed_url:
        url = _resolve_netu(embed_url, page_url=page_url)
        if not url and interactive:
            url = _resolve_netu_captcha(embed_url)
        xbmc.log(f"[Sarmis] filmeonline player resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        return (url, sub_vtt) if url else (None, sub_vtt)
    if "vidmoly." in embed_url:
        data = api._get("/vidmoly/resolve", url=embed_url)
        url  = (data or {}).get("url")
        xbmc.log(f"[Sarmis] Vidmoly resolve: {url[:80] if url else 'eșuat'}", xbmc.LOGINFO)
        if url:
            return url, sub_vtt
        return None, sub_vtt
    # Byse-family embeds pe domenii custom/rotative (ex: gn1r5n.org "Byse Frontend")
    # nu au un domeniu fix de detectat — recunoaștem după forma URL-ului (/e/{id})
    # și lăsăm _resolve_byse să valideze prin API; eșuează curat dacă nu e Byse.
    import re as _re3
    if _re3.search(r'/e/[0-9a-zA-Z]+/?(?:\?|$)', embed_url):
        url = _resolve_byse(embed_url, speculative=True)
        if url:
            xbmc.log(f"[Sarmis] Byse (shape match) resolve OK: {url[:80]}", xbmc.LOGINFO)
            return url, sub_vtt
    xbmc.log(f"[Sarmis] resolveurl: {embed_url[:100]}", xbmc.LOGINFO)
    try:
        import resolveurl
        url = resolveurl.resolve(embed_url)
        if url and url != embed_url:
            if ".m3u8" in url and any(h in embed_url for h in ("netu.ac", "waaw.ac", "netu.to")):
                # Adaugă cookies DDoS Guard (resolveurl adaugă deja Referer+Origin)
                if _netu_cookies:
                    if "|" in url:
                        url = f"{url}&Cookie={_netu_cookies}"
                    else:
                        import re as _re_h
                        _ne_embed = _re_h.sub(r'/f/', '/e/', embed_url, count=1).split('?')[0]
                        url = f"{url}|Referer={_ne_embed}&Cookie={_netu_cookies}"
            return url, sub_vtt
    except Exception as e:
        xbmc.log(f"[Sarmis] resolveurl eroare: {e}", xbmc.LOGWARNING)
    return None, sub_vtt


def _play_stream(stream_url, title, page_url=None, sub_vtt=None, sub_info_url=None, referer=None):
    """Configurează ListItem și pornește redarea."""
    extra_headers = ""
    if "|" in stream_url and ".m3u" in stream_url:
        stream_url, extra_headers = stream_url.split("|", 1)

    _chrome_ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    li = xbmcgui.ListItem(label=title, path=stream_url)
    li.setProperty("IsPlayable", "true")
    if ".m3u" in stream_url:
        li.setMimeType("application/vnd.apple.mpegurl")
        li.setContentLookup(False)
        li.setProperty("inputstream", "inputstream.adaptive")
        if not extra_headers and referer:
            extra_headers = f"Referer={referer}"
        if extra_headers:
            # Dacă resolverul a setat deja un UA (ex: Byse — token-ul CDN e UA-bound,
            # cu alt UA CDN-ul dă 404), îl PĂSTRĂM. Altfel forțăm UA Chrome 124 Win.
            if "User-Agent=" in extra_headers:
                isa_headers = extra_headers
            else:
                isa_headers = extra_headers + f"&User-Agent={_chrome_ua}"
            li.setProperty("inputstream.adaptive.manifest_headers", isa_headers)
            li.setProperty("inputstream.adaptive.stream_headers", isa_headers)
    elif stream_url.endswith(".mp4") and extra_headers:
        li.setHttpHeader("Referer", extra_headers.replace("Referer=", ""))

    sub_paths = []
    if sub_info_url and page_url:
        sub_paths = _prepare_subs(sub_info_url, page_url)
    elif sub_vtt and page_url:
        try:
            import requests as _req, xbmcvfs
            subs_dir = "special://profile/addon_data/plugin.video.sarmis/subs/"
            xbmcvfs.mkdirs(subs_dir)
            base = _sub_basename(page_url)
            real_path = xbmcvfs.translatePath(subs_dir + base + ".Romanian.vtt")
            r = _req.get(sub_vtt, timeout=10)
            if r.ok:
                with open(real_path, "wb") as f:
                    f.write(r.content)
                sub_paths = [real_path]
        except Exception as e:
            xbmc.log(f"[Sarmis] sub eroare: {e}", xbmc.LOGWARNING)
    if sub_paths:
        li.setSubtitles(sub_paths)

    xbmcplugin.setResolvedUrl(_handle, True, li)


def _autoplay_sources(sources, title, page_url):
    """Încearcă sursele în ordine; redă prima care se rezolvă cu succes."""
    for i, src in enumerate(sources):
        label = src.get("label") or f"Server {i + 1}"
        xbmc.log(f"[Sarmis] Autoplay încearcă: {label}", xbmc.LOGINFO)
        stream_url, sub_vtt = _resolve_source(src, page_url=page_url, interactive=False)
        if stream_url:
            _play_stream(stream_url, title, page_url,
                         sub_vtt=sub_vtt, sub_info_url=src.get("sub_info"))
            return
        xbmc.log(f"[Sarmis] Autoplay: {label} eșuat", xbmc.LOGWARNING)
    xbmcgui.Dialog().notification("Sarmis", "Nicio sursă funcțională.",
                                   xbmcgui.NOTIFICATION_ERROR)
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())


def _manual_pick(sources, title, page_url=None):
    """Dialog de selecție sursă; dacă rezolvarea eșuează, notifică și iese."""
    labels = [s.get("label") or f"Server {i + 1}" for i, s in enumerate(sources)]
    idx = 0 if len(sources) == 1 else xbmcgui.Dialog().select("Alege sursa", labels)
    if idx < 0:
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return
    src = sources[idx]
    stream_url, sub_vtt = _resolve_source(src, page_url=page_url)
    if not stream_url:
        xbmcgui.Dialog().notification("Sarmis", "Sursa nu poate fi redată.",
                                       xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return
    _play_stream(stream_url, title, page_url,
                 sub_vtt=sub_vtt, sub_info_url=src.get("sub_info"))


def _pick_and_play(sources, title, page_url=None):
    if not sources:
        xbmcgui.Dialog().notification("Sarmis", "Nicio sursă găsită.",
                                       xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return
    if _ADDON.getSettingBool("autoplay"):
        _autoplay_sources(sources, title, page_url)
    else:
        _manual_pick(sources, title, page_url)
