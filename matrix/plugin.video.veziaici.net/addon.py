"""
VeziAici.net Kodi Addon - Refactored
Main entry point and router for the addon.
"""

import sys
import urllib.parse
import re
import time
import xbmc
import xbmcplugin
import xbmcgui

# Initialize addon paths and utils
from resources.lib.utils import (
    ADDON,
    ADDON_NAME,
    ADDON_ICON,
    ADDON_FANART,
    HANDLE,
    BASE_URL_VEZIAICI,
    get_custom_image,
    log,
    log_error,
    parallel_map,
)
from resources.lib.resolvers import (
    resolve_url_wrapper,
    StreamInfo,
    create_listitem_with_stream,
)
from resources.lib.trakt_api import TraktAPI

# Import scrapers
from resources.lib.scrapers import (
    get_veziaici_menu,
    get_veziaici_episodes,
    parse_veziaici_seasons,
    get_veziaici_sources,
    search_veziaici,
    get_veziaici_latest,
    get_terasa_categories,
    get_terasa_series,
    get_terasa_sources,
    get_korean_categories,
    get_years,
    get_blogul_series,
    get_blogul_episodes,
    get_season_episodes,
    get_movie_sources,
    get_serialecoreene_menu,
    get_serialecoreene_series,
    get_new_episodes,
    get_serialecoreene_episodes,
    get_playable_url,
    get_serialero_menu,
    get_serialero_series,
    get_serialero_episodes,
    get_serialero_season_episodes,
    get_serialero_sources,
    get_serialeromanesti_menu,
    get_serialeromanesti_series,
    get_serialeromanesti_sources,
)


def build_url(mode, **kwargs):
    """Build addon URL with parameters."""
    params = {"mode": mode}
    params.update(kwargs)
    return sys.argv[0] + "?" + urllib.parse.urlencode(params)


def add_directory_item(title, url, icon=None, is_folder=True, **listitem_props):
    """Add a directory item to the listing."""
    list_item = xbmcgui.ListItem(title)
    art = {"icon": icon or ADDON_ICON, "thumb": icon or ADDON_ICON}
    if ADDON_FANART:
        art["fanart"] = ADDON_FANART
    list_item.setArt(art)

    for key, value in listitem_props.items():
        if key == "info":
            list_item.setInfo("video", value)
        elif key == "is_playable":
            list_item.setProperty("IsPlayable", "true")
        elif key == "context_menu":
            list_item.addContextMenuItems(value)

    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=url, listitem=list_item, isFolder=is_folder
    )


def list_main_menu():
    """Display the main menu."""
    add_directory_item(
        "Mega Cauta", build_url("mega_search"), icon="https://i.imgur.com/dvqhLCI.png"
    )
    add_directory_item(
        "VeziAici", build_url("list_veziaici_menu"), icon=ADDON_ICON
    )
    add_directory_item(
        "SerialeRo",
        build_url("list_serialero_menu"),
        icon="https://serialero.net/img/test2.jpg"
    )
    add_directory_item(
        "SerialeRomanesti",
        build_url("list_serialeromanesti_menu"),
        icon="https://serialeromanesti.net/wp-content/uploads/2025/12/logo2.png"
    )
    add_directory_item(
        "BlogAtanase", build_url("list_blogatanase_menu"), icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg"
    )
    add_directory_item(
        "TerasacuCarti",
        build_url("list_turkish_series_categories"),
        icon="https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg",
    )
    add_directory_item(
        "SerialeCoreene",
        build_url("list_serialecoreene_main"),
        icon="https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png",
    )

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def mega_search(query=None):
    """Mega Search functionality across all supported sites."""
    if not query:
        keyboard = xbmcgui.Dialog().input("Mega Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    # Show busy dialog as this might take a few seconds
    xbmc.executebuiltin("ActivateWindow(busydialog)")

    # Define all search tasks
    from resources.lib.scrapers.veziaici import search as search_veziaici_scraper
    from resources.lib.scrapers.serialero import search as search_serialero_scraper
    from resources.lib.scrapers.blogul_atanase import search as search_blogatanase_scraper
    from resources.lib.scrapers.terasacucartii import search as search_terasa_scraper
    from resources.lib.scrapers.serialecoreene import search as search_serialecoreene_scraper
    from resources.lib.scrapers.serialeromanesti import search as search_serialeromanesti_scraper

    search_tasks = [
        ("VeziAici", search_veziaici_scraper),
        ("SerialeRo", search_serialero_scraper),
        ("BlogAtanase", search_blogatanase_scraper),
        ("TerasaCuCarti", search_terasa_scraper),
        ("SerialeCoreene", search_serialecoreene_scraper),
        ("SerialeRomanesti", search_serialeromanesti_scraper),
    ]

    def run_search(task):
        name, func = task
        try:
            res = func(query)
            # Standardize return format (some return (res, next_page), some just res)
            if isinstance(res, tuple):
                return name, res[0]
            return name, res
        except Exception as e:
            log_error(f"Mega Search failed for {name}: {e}")
            return name, []

    # Run in parallel
    results_map = parallel_map(run_search, search_tasks)
    
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    query_words = [w.lower() for w in query.split() if len(w) > 2]

    for site_name, results in results_map:
        if not results:
            continue
            
        for item in results:
            title = item.get("title", "")
            url = item.get("url", "")
            thumb = item.get("thumb", ADDON_ICON)
            
            # Post-filter: Ensure the title has some relevance to the query
            # (Checks if any significant word of the query is in the title)
            if query_words:
                title_lower = title.lower()
                if not any(word in title_lower for word in query_words):
                    continue

            display_title = f"[{site_name}] {title}"
            
            # Decide mode based on site
            is_playable = False
            is_folder = True
            
            if site_name == "VeziAici":
                keywords = ["episod", "sezon", "season", "ep."]
                if any(kw in title.lower() for kw in keywords):
                    mode = "list_sources"
                else:
                    mode = "list_episodes"
            elif site_name == "SerialeRo":
                if item.get("is_movie"):
                    mode = "play_serialero"
                    is_playable = True
                    is_folder = False
                else:
                    mode = "list_serialero_episodes"
            elif site_name == "BlogAtanase":
                keywords = ["serial", "sezon", "episod", "episoade"]
                if any(kw in title.lower() for kw in keywords):
                    mode = "list_korean_episodes"
                else:
                    mode = "list_movie_sources"
            elif site_name == "TerasaCuCarti":
                # For Turkish series, search usually returns episodes
                # Let's check sources if we want to be smart, but for mega search
                # we'll just go to sources list for safety
                mode = "list_turkish_sources"
            elif site_name == "SerialeCoreene":
                mode = "list_serialecoreene_episodes"
            elif site_name == "SerialeRomanesti":
                is_cat = "/category/" in url
                mode = "list_serialeromanesti_series" if is_cat else "play_serialeromanesti"
                is_folder = is_cat
                is_playable = not is_cat
            else:
                mode = "play_source"

            add_directory_item(
                display_title,
                build_url(mode, url=url, name=title, title=title),
                icon=thumb,
                is_folder=is_folder,
                is_playable=is_playable
            )

    xbmcplugin.endOfDirectory(HANDLE)


def list_veziaici_menu():
    """Display the VeziAici menu."""
    add_directory_item(
        "Cauta", build_url("search"), icon="https://i.imgur.com/dvqhLCI.png"
    )
    
    categories = get_veziaici_menu()
    for category in categories:
        title = category["title"]
        icon = ADDON_ICON

        if "emisiuni" in title.lower():
            icon = get_custom_image("asia express")
            url = build_url(
                "list_show_categories",
                shows=urllib.parse.quote(str(category["shows"])),
                name=title,
                latest_url="https://veziaici.net/category/a-emisiuni-romanesti/",
            )
            add_directory_item(title, url, icon=icon)
        elif "seriale" in title.lower():
            icon = get_custom_image("las fierbinti")
            url = build_url(
                "list_show_categories",
                shows=urllib.parse.quote(str(category["shows"])),
                name=title,
                latest_url="https://veziaici.net/category/c-seriale-romanesti/",
            )
            add_directory_item(title, url, icon=icon)

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def list_blogatanase_menu():
    """Display the BlogAtanase menu."""
    add_directory_item(
        "Cauta", build_url("search_blogatanase"), icon="https://i.imgur.com/dvqhLCI.png"
    )
    add_directory_item(
        "Seriale Coreene",
        build_url("list_korean_series_categories"),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )
    add_directory_item(
        "Seriale Chinezesti",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/serialefilme-chinezesti/",
            name="Seriale Chinezesti",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )
    add_directory_item(
        "Seriale Japoneze",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/seriale-japoneze/",
            name="Seriale Japoneze",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )
    add_directory_item(
        "Seriale Thailandeze",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/seriale-thailandeze/",
            name="Seriale Thailandeze",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )
    add_directory_item(
        "Seriale Taiwan",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/serialefilme-taiwanezethailandeze/",
            name="Seriale Taiwan",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )
    add_directory_item(
        "Filme",
        build_url("list_movies_categories"),
        icon="https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg",
    )

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def search_blogatanase(query=None, page="1"):
    """Search functionality for blogul-lui-atanase.ro."""
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    # Use the scraper search method
    from resources.lib.scrapers.blogul_atanase import search as scraper_search_blogatanase
    series, next_page = scraper_search_blogatanase(query, page)

    for item in series:
        title = item.get("title", "")
        series_url = item.get("url", "")
        thumb = item.get("thumb", ADDON_ICON)
        description = item.get("description", "")

        # Intelligent routing - similar to movies category
        keywords = ["serial", "sezon", "episod", "episoade"]
        is_series = any(
            kw in title.lower() or kw in description.lower() for kw in keywords
        )

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title, "plot": description})

        # Most search results on the blog are series/movies container pages
        mode = "list_korean_episodes" if is_series else "list_movie_sources"

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url(mode, url=series_url, name=title),
            listitem=list_item,
            isFolder=True,
        )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("search_blogatanase", query=query, page=next_page),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialero_menu():
    """Display the SerialeRo menu."""
    add_directory_item(
        "Cauta", build_url("search_serialero"), icon="https://i.imgur.com/dvqhLCI.png"
    )
    
    items = get_serialero_menu()
    for item in items:
        add_directory_item(
            item["title"],
            build_url("list_serialero_series", url=item["url"], name=item["title"])
        )
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def search_serialero(query=None, page="1"):
    """Search functionality for serialero.net."""
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    # Reuse get_series_list logic through the search wrapper
    from resources.lib.scrapers.serialero import search as scraper_search_serialero
    series, next_page = scraper_search_serialero(query, page)

    for item in series:
        if item.get("is_movie"):
            add_directory_item(
                item["title"],
                build_url("play_serialero", url=item["url"], title=item["title"]),
                icon=item.get("thumb"),
                is_folder=False,
                is_playable=True,
                info={"plot": item.get("description", "")}
            )
        else:
            add_directory_item(
                item["title"],
                build_url("list_serialero_episodes", url=item["url"], name=item["title"]),
                icon=item.get("thumb"),
                info={"plot": item.get("description", "")}
            )
            
    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("search_serialero", query=query, page=next_page),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialero_series(url, name, page="1"):
    """List series from serialero.net."""
    series, next_page = get_serialero_series(url, page)
    for item in series:
        if item.get("is_movie"):
            add_directory_item(
                item["title"],
                build_url("play_serialero", url=item["url"], title=item["title"]),
                icon=item.get("thumb"),
                is_folder=False,
                is_playable=True,
                info={"plot": item.get("description", "")}
            )
        else:
            add_directory_item(
                item["title"],
                build_url("list_serialero_episodes", url=item["url"], name=item["title"]),
                icon=item.get("thumb"),
                info={"plot": item.get("description", "")}
            )
    
    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("list_serialero_series", url=url, name=name, page=next_page)
        )
    xbmcplugin.endOfDirectory(HANDLE)


def list_serialero_episodes(url, name):
    """List episodes for a serialero.net series."""
    seasons, episodes = get_serialero_episodes(url)
    
    if seasons:
        for season in seasons:
            add_directory_item(
                season["title"],
                build_url("list_serialero_season_episodes", url=url, season_id=season["id"], name=name)
            )
        xbmcplugin.endOfDirectory(HANDLE)
        return
        
    for ep in episodes:
        add_directory_item(
            f"{name} - {ep['title']}",
            build_url("play_serialero", url=ep["url"], title=f"{name} - {ep['title']}"),
            is_folder=False,
            is_playable=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def list_serialero_season_episodes(url, season_id, name):
    """List episodes for a specific season of serialero.net."""
    if season_id.startswith("http"):
        # For explicit season links, we just call get_seasons_and_episodes on the season URL
        # which will extract the JS array episodes for that specific season page
        _, episodes = get_serialero_episodes(season_id, force_episodes=True)
    else:
        episodes = get_serialero_season_episodes(url, season_id)
        
    for ep in episodes:
        add_directory_item(
            f"{name} - {ep['title']}",
            build_url("play_serialero", url=ep["url"], title=f"{name} - {ep['title']}"),
            is_folder=False,
            is_playable=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def play_serialero(url, title):
    """Play a source from serialero.net."""
    sources = get_serialero_sources(url)
    if not sources:
        xbmcgui.Dialog().notification("Error", "No sources found", xbmcgui.NOTIFICATION_ERROR)
        return

    # If multiple sources, let user choose
    if len(sources) > 1:
        labels = [s["domain"] for s in sources]
        selected = xbmcgui.Dialog().select("Select Source", labels)
        if selected == -1:
            return
        source = sources[selected]
    else:
        source = sources[0]

    # Resolve and play using the referer
    result = resolve_url_wrapper(source["url"], referer=source.get("referer"))
    if result:
        list_item = create_listitem_with_stream(result, title)
        xbmcplugin.setResolvedUrl(HANDLE, True, list_item)
    else:
        xbmcgui.Dialog().notification("Error", "Failed to resolve URL", xbmcgui.NOTIFICATION_ERROR)


def list_show_categories(shows_str, name, latest_url):
    """List shows in a category."""
    import ast

    # Add "Latest" item
    add_directory_item(
        "Ultimile adaugate",
        build_url("list_latest", url=latest_url, name="Ultimile adaugate"),
    )

    try:
        shows = ast.literal_eval(urllib.parse.unquote(shows_str))
    except Exception:
        shows = []

    for show in shows:
        title = show.get("title", "")
        url = show.get("url", "")
        if title and url:
            icon = get_custom_image(title)
            add_directory_item(
                title, build_url("list_episodes", url=url, name=title), icon=icon
            )

    xbmcplugin.endOfDirectory(HANDLE)


def list_shows(shows_str, name):
    """List shows without 'Latest' option."""
    import ast

    try:
        shows = ast.literal_eval(urllib.parse.unquote(shows_str))
    except Exception:
        shows = []

    for show in shows:
        title = show.get("title", "")
        url = show.get("url", "")
        if title and url:
            icon = get_custom_image(title)
            add_directory_item(
                title, build_url("list_episodes", url=url, name=title), icon=icon
            )

    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes(url, name):
    """List episodes for a show, grouped by season."""
    import json

    episodes = get_veziaici_episodes(url, cache_file=name)
    seasons, no_season = parse_veziaici_seasons(episodes, name)

    # If only one season and no ungrouped episodes, show directly
    if len(seasons) == 1 and not no_season:
        season_num = list(seasons.keys())[0]
        list_episodes_for_season(json.dumps(seasons[season_num]), season_num, name)
        return

    # Show season folders
    for season_num in sorted(seasons.keys(), reverse=True):
        icon = get_custom_image(name)
        add_directory_item(
            f"Sezonul {season_num}",
            build_url(
                "list_episodes_for_season",
                episodes=json.dumps(seasons[season_num]),
                season=season_num,
                name=name,
            ),
            icon=icon,
        )

    if no_season:
        add_directory_item(
            "Fara Sezon",
            build_url(
                "list_episodes_for_season",
                episodes=json.dumps(no_season),
                season="0",
                name=name,
            ),
            icon=ADDON_ICON,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes_for_season(episodes_json, season, name):
    """List episodes for a specific season."""
    import json

    episodes = json.loads(episodes_json)
    icon = get_custom_image(name)

    for episode in episodes:
        title = episode.get("title", "")
        url = episode.get("url", "")

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": icon, "icon": icon, "fanart": ADDON_FANART})
        list_item.setInfo("video", {"title": title})

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("list_sources", url=url, name=title),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_sources(url, name):
    """List video sources for an episode."""
    sources = get_veziaici_sources(url)

    for source in sources:
        domain = source.get("domain", "Unknown")
        video_url = source.get("url", "")

        list_item = xbmcgui.ListItem(f"Sursa: {domain}")
        list_item.setInfo("video", {"title": f"Sursa: {domain}"})
        list_item.setProperty("IsPlayable", "true")

        # Context menu for download
        context_menu = [
            ("Download", f"RunPlugin({build_url('download_source', url=video_url)})")
        ]
        list_item.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_source", url=video_url, title=name, referer=url),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def play_source(url, title, referer=None):
    """Play a video from URL with optimized handling."""
    start_time = time.time()

    # Handle resolving
    resolved = resolve_url_wrapper(url, referer=referer)

    if not resolved:
        xbmcgui.Dialog().ok(ADDON_NAME, "Could not resolve video URL.")
        return

    resolve_time = time.time() - start_time
    log(f"[play_source] Resolved in {resolve_time:.2f}s")

    # If resolved is a simple string, wrap it in a StreamInfo for uniform handling
    if not isinstance(resolved, StreamInfo):
        log("[play_source] Wrapping legacy URL string into StreamInfo")
        manifest_type = "hls" if ".m3u8" in str(resolved) else ("dash" if ".mpd" in str(resolved) else "mp4")
        resolved = StreamInfo(str(resolved), manifest_type=manifest_type)

    # Use centralized factory to create the list item with all necessary properties
    list_item = create_listitem_with_stream(resolved, title or "Video")

    # Set title property for Trakt scrobbling
    if title:
        xbmcgui.Window(10000).setProperty("VeziAici_Title", title)
    else:
        xbmcgui.Window(10000).clearProperty("VeziAici_Title")

    xbmcplugin.setResolvedUrl(HANDLE, True, list_item)


def download_source(url):
    """Download a video source."""
    resolved = resolve_url_wrapper(url)
    if resolved:
        # Handle StreamInfo or string URL
        if isinstance(resolved, StreamInfo):
            download_url = resolved.url
        else:
            download_url = str(resolved)
        xbmc.executebuiltin(f'Download("{download_url}")')
    else:
        xbmcgui.Dialog().ok(ADDON_NAME, "Could not resolve video URL for download.")


def search(query=None, url=None):
    """Search functionality with pagination."""
    if not query and not url:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    results, next_url = search_veziaici(query, url=url)

    for item in results:
        title = item.get("title", "")
        item_url = item.get("url", "")
        icon = get_custom_image(title)

        # Intelligently decide if this is a series or a specific episode
        keywords = ["episod", "sezon", "season", "ep."]
        is_direct_episode = any(kw in title.lower() for kw in keywords)
        
        if is_direct_episode:
            mode = "list_sources"
        else:
            mode = "list_episodes"

        add_directory_item(
            title, build_url(mode, url=item_url, name=title), icon=icon
        )

    if next_url:
        add_directory_item(
            "Next Page >>", 
            build_url("search", query=query, url=next_url),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_latest(url, name):
    """List latest episodes."""
    items, next_url = get_veziaici_latest(url, max_pages=3)

    for item in items:
        title = item.get("title", "")
        item_url = item.get("url", "")
        icon = get_custom_image(title)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": icon, "icon": icon})
        list_item.setInfo("video", {"title": title})

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("list_sources", url=item_url),
            listitem=list_item,
            isFolder=True,
        )

    if next_url:
        add_directory_item(
            "Next Page >>", build_url("list_latest", url=next_url, name=name)
        )

    xbmcplugin.endOfDirectory(HANDLE)


# Turkish series (terasacucartii.net)
def list_turkish_series_categories():
    """List Turkish series categories."""
    add_directory_item(
        "Cauta", build_url("search_terasa"), icon="https://i.imgur.com/dvqhLCI.png"
    )

    categories = get_terasa_categories()

    for cat in categories:
        add_directory_item(
            cat.get("title", ""),
            build_url("list_turkish_series", url=cat.get("url", "")),
            icon=ADDON_ICON,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def search_terasa(query=None, page="1"):
    """Search functionality for terasacucartii.net."""
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    from resources.lib.scrapers.terasacucartii import search as scraper_search_terasa
    episodes, next_page = scraper_search_terasa(query, page)

    # Pre-fetch sources in parallel to decide if it's a folder or direct play
    log(f"[turkish] Pre-fetching sources for {len(episodes)} search results...")
    episode_sources = parallel_map(lambda ep: get_terasa_sources(ep["url"]), episodes)

    for ep, sources in zip(episodes, episode_sources):
        title = ep.get("title", "")
        ep_url = ep.get("url", "")
        thumb = ep.get("thumb", ADDON_ICON)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title})

        # If only one source, allow direct playback from this menu
        if len(sources) == 1:
            video_url = sources[0].get("url")
            referer = sources[0].get("referer")
            list_item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("play_source", url=video_url, title=title, referer=referer),
                listitem=list_item,
                isFolder=False,
            )
        else:
            # Multiple sources or none yet, show sub-menu
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("list_turkish_sources", url=ep_url, name=title),
                listitem=list_item,
                isFolder=True,
            )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("search_terasa", query=query, page=next_page),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_series(url, page="1"):
    """List Turkish series episodes with direct playback optimization."""
    episodes, next_page = get_terasa_series(url, page)

    # Pre-fetch sources in parallel to decide if it's a folder or direct play
    log(f"[turkish] Pre-fetching sources for {len(episodes)} episodes...")
    episode_sources = parallel_map(lambda ep: get_terasa_sources(ep["url"]), episodes)

    for ep, sources in zip(episodes, episode_sources):
        title = ep.get("title", "")
        ep_url = ep.get("url", "")
        thumb = ep.get("thumb", ADDON_ICON)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title})

        # If only one source, allow direct playback from this menu
        if len(sources) == 1:
            video_url = sources[0].get("url")
            list_item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("play_source", url=video_url, title=title),
                listitem=list_item,
                isFolder=False,
            )
        elif len(sources) > 1:
            # Multiple sources, show sub-menu
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("list_turkish_sources", url=ep_url, name=title),
                listitem=list_item,
                isFolder=True,
            )
        else:
            # No sources found yet or extraction failed
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("list_turkish_sources", url=ep_url, name=title),
                listitem=list_item,
                isFolder=True,
            )

    if next_page:
        add_directory_item(
            "Next Page >>", build_url("list_turkish_series", url=url, page=next_page)
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_sources(url, name):
    """List sources for Turkish episode."""
    sources = get_terasa_sources(url)

    for idx, source in enumerate(sources):
        domain = source.get("domain", f"Source {idx + 1}")
        video_url = source.get("url", "")

        list_item = xbmcgui.ListItem(f"Sursa {idx + 1}: {domain}")
        list_item.setInfo("video", {"title": f"Sursa {idx + 1}: {domain}"})
        list_item.setProperty("IsPlayable", "true")

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_source", url=video_url, title=name),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


# Korean/Asian series (blogul-lui-atanase.ro)
def list_korean_series_categories():
    """List Korean series categories."""
    icon = "https://kdrama.ro/wp-content/uploads/2023/06/image7-1016x1024.jpg"

    # Add "By Year" category
    add_directory_item("Dupa Ani", build_url("list_korean_series_years"), icon=icon)

    # Add other categories
    categories = get_korean_categories()
    for cat in categories:
        if "url" in cat:
            add_directory_item(
                cat.get("title", ""),
                build_url(
                    "list_korean_series", url=cat.get("url"), name=cat.get("title", "")
                ),
                icon=icon,
            )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_series_years():
    """List Korean series by year."""
    years = get_years()

    for year in years:
        add_directory_item(
            year.get("title", ""),
            build_url(
                "list_korean_series", url=year.get("url"), name=year.get("title", "")
            ),
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_series(url, name, page="1"):
    """List Korean series from category."""
    series, next_page = get_blogul_series(url, page)

    for item in series:
        title = item.get("title", "")
        series_url = item.get("url", "")
        thumb = item.get("thumb", ADDON_ICON)
        description = item.get("description", "")

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title, "plot": description})

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("list_korean_episodes", url=series_url, name=title),
            listitem=list_item,
            isFolder=True,
        )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("list_korean_series", url=url, name=name, page=next_page),
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_episodes(url, name):
    """List episodes for a Korean series with direct playback optimization."""
    seasons, episodes = get_blogul_episodes(url, name)

    # If seasons exist, show season folders
    if seasons:
        for season in seasons:
            add_directory_item(
                season.get("title", ""),
                build_url(
                    "list_korean_season_episodes",
                    url=url,
                    season_title=season.get("title", ""),
                    name=name,
                ),
            )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Pre-fetch sources in parallel for episodes without seasons
    log(f"[korean] Pre-fetching sources for {len(episodes)} episodes...")
    episode_sources = parallel_map(lambda ep: get_movie_sources(ep["url"]), episodes)

    for ep, sources in zip(episodes, episode_sources):
        title = ep.get("title", "")
        ep_url = ep.get("url", "")
        full_title = f"{name} - {title}"

        list_item = xbmcgui.ListItem(title)
        list_item.setInfo("video", {"title": title})

        if len(sources) == 1:
            video_url = sources[0].get("url")
            list_item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("play_source", url=video_url, title=full_title),
                listitem=list_item,
                isFolder=False,
            )
        else:
            # Multiple sources or zero, show sources list
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("play_source", url=ep_url, title=full_title) if len(sources) == 0 else build_url("list_movie_sources", url=ep_url, name=full_title),
                listitem=list_item,
                isFolder=True if len(sources) > 1 else False,
            )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_season_episodes(url, season_title, name):
    """List episodes for a specific season with direct playback optimization."""
    episodes = get_season_episodes(url, season_title, name)

    # Pre-fetch sources in parallel
    log(f"[korean] Pre-fetching sources for season {season_title} ({len(episodes)} episodes)...")
    episode_sources = parallel_map(lambda ep: get_movie_sources(ep["url"]), episodes)

    for ep, sources in zip(episodes, episode_sources):
        title = ep.get("title", "")
        ep_url = ep.get("url", "")
        full_title = f"{name} - {title}"

        list_item = xbmcgui.ListItem(title)
        list_item.setInfo("video", {"title": title})

        if len(sources) == 1:
            video_url = sources[0].get("url")
            list_item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("play_source", url=video_url, title=full_title),
                listitem=list_item,
                isFolder=False,
            )
        else:
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=build_url("list_movie_sources", url=ep_url, name=full_title),
                listitem=list_item,
                isFolder=True,
            )

    xbmcplugin.endOfDirectory(HANDLE)


# Movies
def list_movies_categories():
    """List movie categories."""
    icon = "https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg"

    categories = [
        {
            "title": "Filme de epoca",
            "url": "https://blogul-lui-atanase.ro/categorie/nostalgia/",
        },
        {
            "title": "Filme de Craciun",
            "url": "https://blogul-lui-atanase.ro/categorie/filme-de-craciun/",
        },
        {
            "title": "Filme Coreene",
            "url": "https://blogul-lui-atanase.ro/categorie/filme-coreene/",
        },
        {
            "title": "Filme Chinezesti",
            "url": "https://blogul-lui-atanase.ro/categorie/filme-chinezesti/",
        },
        {
            "title": "Filme Japoneze",
            "url": "https://blogul-lui-atanase.ro/categorie/serialefilme-japoneze/",
        },
        {
            "title": "Filme Indiene",
            "url": "https://blogul-lui-atanase.ro/categorie/filme-indiene/",
        },
        {
            "title": "Filme Turcesti",
            "url": "https://blogul-lui-atanase.ro/categorie/filme-turcesti/",
        },
    ]

    for cat in categories:
        add_directory_item(
            cat.get("title", ""),
            build_url("list_movies", url=cat.get("url"), name=cat.get("title", "")),
            icon=icon,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_movies(url, name, page="1"):
    """List movies from category."""
    movies, next_page = get_blogul_series(url, page)

    for item in movies:
        title = item.get("title", "")
        movie_url = item.get("url", "")
        thumb = item.get("thumb", ADDON_ICON)
        description = item.get("description", "")

        # Detect if it's a series
        keywords = ["serial", "sezon", "episod", "episoade"]
        is_series = any(
            kw in title.lower() or kw in description.lower() for kw in keywords
        )

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title, "plot": description})

        if is_series:
            mode = "list_korean_episodes"
        else:
            mode = "list_movie_sources"

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url(mode, url=movie_url, name=title),
            listitem=list_item,
            isFolder=True,
        )

    if next_page:
        add_directory_item(
            "Next Page >>", build_url("list_movies", url=url, name=name, page=next_page)
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_movie_sources(url, name):
    """List sources for a movie."""
    sources = get_movie_sources(url)

    for source in sources:
        domain = source.get("domain", "Unknown")
        video_url = source.get("url", "")

        list_item = xbmcgui.ListItem(f"Sursa: {domain}")
        list_item.setInfo("video", {"title": f"Sursa: {domain}"})
        list_item.setProperty("IsPlayable", "true")

        context_menu = [
            ("Download", f"RunPlugin({build_url('download_source', url=video_url)})")
        ]
        list_item.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_source", url=video_url, title=name),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


# SerialeRomanesti (serialeromanesti.net)
def list_serialeromanesti_menu():
    """Display the SerialeRomanesti menu."""
    icon = "https://serialeromanesti.net/wp-content/uploads/2025/12/logo2.png"
    add_directory_item(
        "Cauta", build_url("search_serialeromanesti"), icon="https://i.imgur.com/dvqhLCI.png"
    )
    
    items = get_serialeromanesti_menu()
    for item in items:
        add_directory_item(
            item["title"],
            build_url("list_serialeromanesti_series", url=item["url"], name=item["title"]),
            icon=icon
        )
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def search_serialeromanesti(query=None, page="1"):
    """Search functionality for serialeromanesti.net."""
    icon = "https://serialeromanesti.net/wp-content/uploads/2025/12/logo2.png"
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    from resources.lib.scrapers.serialeromanesti import search as scraper_search_serialeromanesti
    series, next_page = scraper_search_serialeromanesti(query, page)

    for item in series:
        title = item.get("title", "")
        series_url = item.get("url", "")
        thumb = item.get("thumb", icon)
        
        # Intelligent routing: categories are folders, posts are playable
        is_folder = "/category/" in series_url
        mode = "list_serialeromanesti_series" if is_folder else "play_serialeromanesti"

        add_directory_item(
            title, 
            build_url(mode, url=series_url, title=title), 
            icon=thumb,
            is_folder=is_folder,
            is_playable=not is_folder
        )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("search_serialeromanesti", query=query, page=next_page),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialeromanesti_series(url, name, page="1"):
    """List series from serialeromanesti.net."""
    icon = "https://serialeromanesti.net/wp-content/uploads/2025/12/logo2.png"
    series, next_page = get_serialeromanesti_series(url, page)
    
    for item in series:
        title = item.get("title", "")
        item_url = item.get("url", "")
        thumb = item.get("thumb", icon)

        # Intelligent routing: categories are folders, posts are playable
        is_folder = "/category/" in item_url
        mode = "list_serialeromanesti_series" if is_folder else "play_serialeromanesti"

        add_directory_item(
            title, 
            build_url(mode, url=item_url, title=title), 
            icon=thumb,
            is_folder=is_folder,
            is_playable=not is_folder
        )
            
    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("list_serialeromanesti_series", url=url, name=name, page=next_page),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def play_serialeromanesti(url, title):
    """Play an episode from serialeromanesti.net."""
    sources = get_serialeromanesti_sources(url)
    
    if not sources:
        xbmcgui.Dialog().ok(ADDON_NAME, "Nu s-au gasit surse video.")
        return
        
    if len(sources) == 1:
        play_source(sources[0]["url"], title, referer=sources[0].get("referer"))
        return
        
    # Multiple sources, let user select
    source_names = [s.get("domain", "Unknown") for s in sources]
    dialog = xbmcgui.Dialog()
    selected = dialog.select("Selecteaza sursa", source_names)
    
    if selected >= 0:
        play_source(sources[selected]["url"], title, referer=sources[selected].get("referer"))


# SerialeCoreene.org
def list_serialecoreene_main():
    """Main menu for SerialeCoreene.org."""
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
    add_directory_item(
        "Cauta", build_url("search_serialecoreene"), icon="https://i.imgur.com/dvqhLCI.png"
    )
    
    menu = get_serialecoreene_menu()

    for item in menu:
        add_directory_item(
            item.get("title", ""),
            build_url(
                item.get("mode"), url=item.get("url"), name=item.get("title", "")
            ),
            icon=icon,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def search_serialecoreene(query=None, page="1"):
    """Search functionality for serialecoreene.org."""
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    from resources.lib.scrapers.serialecoreene import search as scraper_search_serialecoreene
    series, next_page = scraper_search_serialecoreene(query, page)

    for item in series:
        title = item.get("title", "")
        series_url = item.get("url", "")
        thumb = item.get("thumb", icon)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title})

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("list_serialecoreene_episodes", url=series_url, name=title),
            listitem=list_item,
            isFolder=True,
        )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url("search_serialecoreene", query=query, page=next_page),
            icon="https://i.imgur.com/dvqhLCI.png"
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_all_series(url, name, page="1"):
    """List all series from SerialeCoreene.org."""
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
    series, next_page = get_serialecoreene_series(url, page)

    for item in series:
        title = item.get("title", "")
        series_url = item.get("url", "")
        thumb = item.get("thumb", icon)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title})

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("list_serialecoreene_episodes", url=series_url, name=title),
            listitem=list_item,
            isFolder=True,
        )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url(
                "list_serialecoreene_all_series", url=url, name=name, page=next_page
            ),
            icon=icon,
        )

    xbmcplugin.endOfDirectory(HANDLE)


# Aliases for Korean and Thai series (same function)
list_serialecoreene_korean_series = list_serialecoreene_all_series
list_serialecoreene_thai_series = list_serialecoreene_all_series


def list_serialecoreene_new_episodes(url, name, page="1"):
    """List new episodes from SerialeCoreene.org."""
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
    episodes, next_page = get_new_episodes(url, page)

    for item in episodes:
        title = item.get("title", "")
        ep_url = item.get("url", "")
        thumb = item.get("thumb", icon)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title})
        list_item.setProperty("IsPlayable", "true")

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_serialecoreene_episode", url=ep_url, name=title),
            listitem=list_item,
            isFolder=False,
        )

    if next_page:
        add_directory_item(
            "Next Page >>",
            build_url(
                "list_serialecoreene_new_episodes", url=url, name=name, page=next_page
            ),
            icon=icon,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_episodes(url, name):
    """List episodes for a series from SerialeCoreene.org."""
    episodes = get_serialecoreene_episodes(url)

    for ep in episodes:
        title = ep.get("title", "")
        ep_url = ep.get("url", "")

        list_item = xbmcgui.ListItem(title)
        list_item.setInfo("video", {"title": title})
        list_item.setProperty("IsPlayable", "true")

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_serialecoreene_episode", url=ep_url, name=title),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def play_serialecoreene_episode(url, name):
    """Play episode from SerialeCoreene.org (handles redirects)."""
    res = get_playable_url(url)

    if not res:
        xbmcgui.Dialog().ok(ADDON_NAME, "Nu s-a putut extrage sursa video.")
        return

    video_url = res.get("url")
    referer = res.get("referer")
    
    # Use centralized playback logic
    play_source(video_url, name, referer=referer)


# Trakt integration
def authorize_trakt():
    """Authorize Trakt account."""
    TraktAPI().authorize()


def revoke_trakt():
    """Revoke Trakt authorization."""
    TraktAPI().revoke_auth()


# Router
def router(paramstring):
    """Route to appropriate function based on mode parameter."""
    params = dict(urllib.parse.parse_qsl(paramstring))
    mode = params.get("mode")

    # Main navigation
    if mode is None:
        list_main_menu()
    elif mode == "list_veziaici_menu":
        list_veziaici_menu()
    elif mode == "list_blogatanase_menu":
        list_blogatanase_menu()
    elif mode == "list_serialero_menu":
        list_serialero_menu()
    elif mode == "search_serialero":
        search_serialero(params.get("query"), params.get("page", "1"))
    elif mode == "list_serialero_series":
        list_serialero_series(params.get("url"), params.get("name"), params.get("page", "1"))
    elif mode == "list_serialero_episodes":
        list_serialero_episodes(params.get("url"), params.get("name"))
    elif mode == "list_serialero_season_episodes":
        list_serialero_season_episodes(params.get("url"), params.get("season_id"), params.get("name"))
    elif mode == "play_serialero":
        play_serialero(params.get("url"), params.get("title"))

    # SerialeRomanesti
    elif mode == "list_serialeromanesti_menu":
        list_serialeromanesti_menu()
    elif mode == "search_serialeromanesti":
        search_serialeromanesti(params.get("query"), params.get("page", "1"))
    elif mode == "list_serialeromanesti_series":
        list_serialeromanesti_series(params.get("url"), params.get("name"), params.get("page", "1"))
    elif mode == "play_serialeromanesti":
        play_serialeromanesti(params.get("url"), params.get("title"))

    # Veziaici.net
    elif mode == "list_show_categories":
        list_show_categories(
            params.get("shows"), params.get("name"), params.get("latest_url")
        )
    elif mode == "list_shows":
        list_shows(params.get("shows"), params.get("name"))
    elif mode == "list_latest":
        list_latest(params.get("url"), params.get("name"))
    elif mode == "list_episodes":
        list_episodes(params.get("url"), params.get("name"))
    elif mode == "list_episodes_for_season":
        list_episodes_for_season(
            params.get("episodes"), params.get("season"), params.get("name")
        )
    elif mode == "list_sources":
        list_sources(params.get("url"), params.get("name"))
    elif mode == "search":
        search(params.get("query"), params.get("url"))

    # Turkish series
    elif mode == "search_terasa":
        search_terasa(params.get("query"), params.get("page", "1"))
    elif mode == "list_turkish_series_categories":
        list_turkish_series_categories()
    elif mode == "list_turkish_series":
        list_turkish_series(params.get("url"), params.get("page", "1"))
    elif mode == "list_turkish_sources":
        list_turkish_sources(params.get("url"), params.get("name"))

    # Korean/Asian series
    elif mode == "search_blogatanase":
        search_blogatanase(params.get("query"), params.get("page", "1"))
    elif mode == "list_korean_series_categories":
        list_korean_series_categories()
    elif mode == "list_korean_series_years":
        list_korean_series_years()
    elif mode == "list_korean_series":
        list_korean_series(
            params.get("url"), params.get("name"), params.get("page", "1")
        )
    elif mode == "list_korean_episodes":
        list_korean_episodes(params.get("url"), params.get("name"))
    elif mode == "list_korean_season_episodes":
        list_korean_season_episodes(
            params.get("url"), params.get("season_title"), params.get("name")
        )

    # Movies
    elif mode == "list_movies_categories":
        list_movies_categories()
    elif mode == "list_movies":
        list_movies(params.get("url"), params.get("name"), params.get("page", "1"))
    elif mode == "list_movie_sources":
        list_movie_sources(params.get("url"), params.get("name"))

    # SerialeCoreene.org
    elif mode == "list_serialecoreene_main":
        list_serialecoreene_main()
    elif mode == "search_serialecoreene":
        search_serialecoreene(params.get("query"), params.get("page", "1"))
    elif mode == "list_serialecoreene_all_series":
        list_serialecoreene_all_series(
            params.get("url"), params.get("name"), params.get("page", "1")
        )
    elif mode == "list_serialecoreene_korean_series":
        list_serialecoreene_korean_series(
            params.get("url"), params.get("name"), params.get("page", "1")
        )
    elif mode == "list_serialecoreene_thai_series":
        list_serialecoreene_thai_series(
            params.get("url"), params.get("name"), params.get("page", "1")
        )
    elif mode == "list_serialecoreene_new_episodes":
        list_serialecoreene_new_episodes(
            params.get("url"), params.get("name"), params.get("page", "1")
        )
    elif mode == "list_serialecoreene_episodes":
        list_serialecoreene_episodes(params.get("url"), params.get("name"))

    # Playback
    elif mode == "play_source":
        play_source(params.get("url"), params.get("title"), referer=params.get("referer"))
    elif mode == "mega_search":
        mega_search(params.get("query"))
    elif mode == "play_serialecoreene_episode":
        play_serialecoreene_episode(params.get("url"), params.get("name"))
    elif mode == "download_source":
        download_source(params.get("url"))

    # Trakt
    elif mode == "authorize_trakt":
        authorize_trakt()
    elif mode == "revoke_trakt":
        revoke_trakt()


if __name__ == "__main__":
    router(sys.argv[2][1:])
