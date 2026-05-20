import sys
import re
import unicodedata
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

try:
    import resolveurl
    HAS_RESOLVEURL = True
except ImportError:
    HAS_RESOLVEURL = False

from resources.lib import filmehd_org as api

ADDON    = xbmcaddon.Addon()
HANDLE   = int(sys.argv[1])
BASE_URL = sys.argv[0]

import os as _os
_ADDON_PATH = ADDON.getAddonInfo("path")
ICON   = _os.path.join(_ADDON_PATH, "icon.png")
FANART = _os.path.join(_ADDON_PATH, "fanart.jpg")

_SEARCH_QUERY = xbmcvfs.translatePath("special://temp/filmehd_org_query.txt")
_PLAY_FLAG    = xbmcvfs.translatePath("special://temp/filmehd_org_played.flag")

xbmcplugin.setProperty(HANDLE, "fanart", FANART)

GENRES = [
    ("Acțiune",          "actiune"),
    ("Animație",         "animatie"),
    ("Aventură",         "aventura"),
    ("Biografie",        "biografie"),
    ("Comedie",          "comedie"),
    ("Crimă",            "crima"),
    ("Documentar",       "documentar"),
    ("Dramă",            "drama"),
    ("Familie",          "familie"),
    ("Fantezie",         "fantezie"),
    ("Groază",           "groaza"),
    ("Mister",           "mister"),
    ("Muzică",           "muzica"),
    ("Romantic",         "romantic"),
    ("Sci-Fi",           "sf"),
    ("Sport",            "sport"),
    ("Thriller",         "thriller"),
    ("Western",          "western"),
]


def _url(**kwargs):
    return BASE_URL + "?" + urllib.parse.urlencode(kwargs)


def _add_item(title, plugin_url, is_folder, poster="", plot="", year="", rating="", season=None, episode=None):
    item = xbmcgui.ListItem(label=title)
    thumb = poster or ICON
    item.setArt({"thumb": thumb, "icon": thumb, "poster": poster, "fanart": FANART})
    info = {"title": title, "plot": plot}
    if year:
        info["year"] = int(year) if str(year).isdigit() else year
    if rating:
        try:
            info["rating"] = float(rating)
        except ValueError:
            pass
    if season is not None:
        info["season"] = season
    if episode is not None:
        info["episode"] = episode
    item.setInfo("video", info)
    if not is_folder:
        item.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url, item, is_folder)


def list_categories():
    xbmcplugin.setPluginCategory(HANDLE, "FilmeHD.org")
    cats = [
        ("Filme",    _url(action="list", url=f"{api.BASE}/filme/page/1/")),
        ("Seriale",  _url(action="list", url=f"{api.BASE}/seriale/page/1/")),
        ("Genuri",   _url(action="genres")),
        ("Ani",      _url(action="years")),
        ("TOP IMDb", _url(action="list", url=f"{api.BASE}/top-imdb/")),
        ("Colecții", _url(action="list", url=f"{api.BASE}/colectii/")),
        ("Caută",    _url(action="search")),
    ]
    for title, url in cats:
        _add_item(title, url, is_folder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_genres():
    xbmcplugin.setPluginCategory(HANDLE, "Genuri")
    for name, slug in GENRES:
        _add_item(name, _url(action="list", url=f"{api.BASE}/gen/{slug}/page/1/"), is_folder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_years():
    xbmcplugin.setPluginCategory(HANDLE, "Ani")
    for year in range(2026, 2006, -1):
        _add_item(str(year), _url(action="list", url=f"{api.BASE}/an/{year}/page/1/"), is_folder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_films(url):
    items, next_url = api.list_items(url)
    content = "tvshows" if "/seriale" in url or "/serial" in url else "movies"
    for item in items:
        if item["is_serial"]:
            plugin_url = _url(action="serial", url=item["url"])
            is_folder  = True
        else:
            plugin_url = _url(action="play", url=item["url"])
            is_folder  = False
        _add_item(
            item["title"], plugin_url, is_folder,
            poster=item["poster"], year=item.get("year", ""),
        )
    if next_url:
        _add_item("[Pagina urmatoare »]", _url(action="list", url=next_url), is_folder=True)
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE)


def list_serial(serial_url):
    info = api.get_serial_info(serial_url)
    sbnum = info["seasons_by_num"]
    if not sbnum:
        xbmcgui.Dialog().notification("FilmeHD.org", "Nu s-au găsit episoade", time=3000)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    if len(sbnum) <= 1:
        ep_url = next(iter(sbnum.values()))
        season = next(iter(sbnum.keys()))
        _show_episodes(serial_url, ep_url, season=season, serial_poster=info["poster"])
        return

    xbmcplugin.setPluginCategory(HANDLE, info.get("title", "Sezoane"))
    for snum in sorted(sbnum.keys()):
        _add_item(
            f"Sezonul {snum}",
            _url(action="episodes", url=serial_url,
                 episode_url=sbnum[snum], season=snum, poster=info["poster"]),
            is_folder=True, poster=info["poster"],
        )
    xbmcplugin.endOfDirectory(HANDLE)


def _show_episodes(serial_url, episode_url, season, serial_poster=""):
    episodes = api.get_episodes(episode_url, serial_url)
    season_eps = [e for e in episodes if e["season"] == int(season)]

    for ep in season_eps:
        label = (f"S{ep['season']:02d}E{ep['episode']:02d} – {ep['title']}"
                 if ep["title"]
                 else f"Episodul {ep['episode']}")
        thumb = ep["thumb"] or serial_poster
        _add_item(
            label,
            _url(action="play", url=ep["url"]),
            is_folder=False,
            poster=thumb,
            plot=ep["plot"],
            season=ep["season"],
            episode=ep["episode"],
        )
    xbmcplugin.setContent(HANDLE, "episodes")
    xbmcplugin.endOfDirectory(HANDLE)


def do_search():
    played = _os.path.exists(_PLAY_FLAG)
    saved_query = ""
    try:
        if _os.path.exists(_SEARCH_QUERY):
            with open(_SEARCH_QUERY) as f:
                saved_query = f.read().strip()
    except Exception:
        pass
    if played:
        try:
            _os.remove(_PLAY_FLAG)
        except Exception:
            pass

    if played and saved_query:
        _list_search(saved_query)
        return

    kbd = xbmc.Keyboard("", "Caută pe FilmeHD.org")
    kbd.doModal()
    if not kbd.isConfirmed():
        xbmcplugin.endOfDirectory(HANDLE, False)
        return
    query = kbd.getText().strip()
    if not query:
        xbmcplugin.endOfDirectory(HANDLE, False)
        return
    try:
        with open(_SEARCH_QUERY, 'w') as f:
            f.write(query)
    except Exception:
        pass
    _list_search(query)


def _list_search(query):
    xbmcplugin.setPluginCategory(HANDLE, f"Căutare: {query}")
    items = api.search(query)
    for item in items:
        if item["is_serial"]:
            plugin_url = _url(action="serial", url=item["url"])
            is_folder  = True
        else:
            plugin_url = _url(action="play", url=item["url"])
            is_folder  = False
        _add_item(item["title"], plugin_url, is_folder, poster=item["poster"], year=item.get("year", ""))
    xbmcplugin.endOfDirectory(HANDLE)


def _normalize(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _title_score(candidate, query):
    a, b = _normalize(candidate), _normalize(query)
    if not b:
        return 0.0
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return 0.9
    if b in a or a in b:
        return 0.8
    aw, bw = set(a.split()), set(b.split())
    return len(aw & bw) / len(bw)


def play_tmdb():
    title   = args.get("title", [""])[0]
    year    = args.get("year", [""])[0]
    results = api.search(title)
    movies  = [r for r in results if not r["is_serial"]]
    if not movies:
        xbmcgui.Dialog().notification("FilmeHD.org", f"Nu s-a găsit: {title}", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    scored = sorted(movies, key=lambda r: _title_score(r["title"], title), reverse=True)
    best_score = _title_score(scored[0]["title"], title)
    if best_score >= 0.85:
        _play_item_inner(scored[0]["url"])
    else:
        idx = xbmcgui.Dialog().select(f"Selectează: {title}", [r["title"] for r in scored])
        if idx < 0:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
        _play_item_inner(scored[idx]["url"])


def play_tmdb_ep():
    title   = args.get("title", [""])[0]
    year    = args.get("year", [""])[0]
    season  = int(args.get("season", ["1"])[0] or 1)
    episode = int(args.get("episode", ["1"])[0] or 1)
    results = api.search(title)
    shows   = [r for r in results if r["is_serial"]]
    if not shows:
        xbmcgui.Dialog().notification("FilmeHD.org", f"Nu s-a găsit: {title}", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    scored = sorted(shows, key=lambda r: _title_score(r["title"], title), reverse=True)
    best_score = _title_score(scored[0]["title"], title)
    if best_score < 0.35:
        xbmcgui.Dialog().notification("FilmeHD.org", f"Serialul negăsit: {title}", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    if best_score >= 0.85:
        show = scored[0]
    else:
        idx = xbmcgui.Dialog().select(f"Selectează: {title}", [r["title"] for r in scored])
        if idx < 0:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
        show = scored[idx]
    info = api.get_serial_info(show["url"])
    sbnum = info.get("seasons_by_num", {})
    ep_ajax_url = sbnum.get(season)
    if not ep_ajax_url:
        xbmcgui.Dialog().notification("FilmeHD.org", f"Sezonul {season} negăsit", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    episodes = api.get_episodes(ep_ajax_url, show["url"])
    matching = [e for e in episodes if e["season"] == season and e["episode"] == episode]
    if not matching:
        xbmcgui.Dialog().notification("FilmeHD.org", f"S{season:02d}E{episode:02d} negăsit", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    _play_item_inner(matching[0]["url"])


def play_item(url):
    try:
        open(_PLAY_FLAG, 'w').close()
    except Exception:
        pass
    try:
        _play_item_inner(url)
    except Exception as e:
        xbmc.log(f"[filmehd.org] play_item exception: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("FilmeHD.org", f"Eroare: {e}", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def _play_item_inner(url):
    details = api.get_film_details(url)
    if not details["playY"]:
        xbmcgui.Dialog().notification("FilmeHD.org", "Nu s-a găsit player", time=3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    players = api.get_players(details["playY"], url)
    if not players:
        xbmcgui.Dialog().notification("FilmeHD.org", "Nu s-au găsit servere", time=3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    if len(players) == 1:
        chosen = players[0]
    else:
        names = [p.get("name", f"Server {i+1}") for i, p in enumerate(players)]
        idx = xbmcgui.Dialog().select("Alege server", names)
        if idx < 0:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
        chosen = players[idx]

    embed_url = chosen.get("link", "")
    if not embed_url:
        xbmcgui.Dialog().notification("FilmeHD.org", "Link invalid", time=3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    stream_url = None

    # Try native Byse resolver first (challenge/attest/decrypt)
    if "f16px.com" in embed_url or "byse" in embed_url:
        stream_url, reason = api.get_byse_stream(embed_url, url)
        xbmc.log(f"[filmehd.org] byse: {reason} -> {stream_url[:60] if stream_url else 'None'}", xbmc.LOGINFO)

    # Fall back to resolveurl for other hosts or if byse failed
    if not stream_url and HAS_RESOLVEURL:
        try:
            hmf = resolveurl.HostedMediaFile(url=embed_url)
            if hmf.valid_url():
                stream_url = hmf.resolve()
        except Exception as e:
            xbmc.log(f"[filmehd.org] resolveurl failed: {e}", xbmc.LOGWARNING)

    if not stream_url:
        xbmcgui.Dialog().notification("FilmeHD.org", "Stream indisponibil pe acest server", time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    item = xbmcgui.ListItem(path=stream_url)
    item.setInfo("video", {
        "title":  details["title"],
        "plot":   details["plot"],
        "year":   int(details["year"]) if details["year"].isdigit() else 0,
        "rating": float(details["rating"]) if details["rating"] else 0.0,
    })
    item.setArt({"thumb": details["poster"], "poster": details["poster"]})

    if ".m3u8" in stream_url:
        item.setProperty("inputstream", "inputstream.adaptive")
        item.setProperty("inputstream.adaptive.manifest_type", "hls")
        item.setContentLookup(False)

    subs = api.get_subtitles(embed_url)
    if subs:
        item.setSubtitles([s["url"] for s in subs])

    xbmcplugin.setResolvedUrl(HANDLE, True, item)


# ── Router ──────────────────────────────────────────────────────────────────
args   = urllib.parse.parse_qs(urllib.parse.urlparse(sys.argv[2]).query)
action = args.get("action", [None])[0]

if action is None:
    list_categories()
elif action == "list":
    list_films(args["url"][0])
elif action == "genres":
    list_genres()
elif action == "years":
    list_years()
elif action == "serial":
    list_serial(args["url"][0])
elif action == "episodes":
    _show_episodes(
        args["url"][0],
        args["episode_url"][0],
        args["season"][0],
        args.get("poster", [""])[0],
    )
elif action == "search":
    do_search()
elif action == "play":
    play_item(args["url"][0])
elif action == "play_tmdb":
    play_tmdb()
elif action == "play_tmdb_ep":
    play_tmdb_ep()
