"""
VeziAici.net Kodi Addon - Refactored
Main entry point and router for the addon.
"""

import sys
import urllib.parse
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
    # Search
    add_directory_item(
        "Cauta", build_url("search"), icon="https://i.imgur.com/dvqhLCI.png"
    )

    # Veziaici.net categories
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
        elif "seriale" in title.lower():
            icon = get_custom_image("las fierbinti")
            url = build_url(
                "list_show_categories",
                shows=urllib.parse.quote(str(category["shows"])),
                name=title,
                latest_url="https://veziaici.net/category/c-seriale-romanesti/",
            )
        else:
            url = build_url(
                "list_shows",
                shows=urllib.parse.quote(str(category["shows"])),
                name=title,
            )

        add_directory_item(title, url, icon=icon)

    # Turkish series
    add_directory_item(
        "Seriale Turcesti",
        build_url("list_turkish_series_categories"),
        icon="https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg",
    )

    # Korean series categories
    add_directory_item(
        "Seriale Coreene",
        build_url("list_korean_series_categories"),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )

    # Chinese series
    add_directory_item(
        "Seriale Chinezesti",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/serialefilme-chinezesti/",
            name="Seriale Chinezesti",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )

    # Japanese series
    add_directory_item(
        "Seriale Japoneze",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/seriale-japoneze/",
            name="Seriale Japoneze",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )

    # Thai series
    add_directory_item(
        "Seriale Thailandeze",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/seriale-thailandeze/",
            name="Seriale Thailandeze",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )

    # Taiwan series
    add_directory_item(
        "Seriale Taiwan",
        build_url(
            "list_korean_series",
            url="https://blogul-lui-atanase.ro/categorie/serialefilme-taiwanezethailandeze/",
            name="Seriale Taiwan",
        ),
        icon="https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg",
    )

    # SerialeCoreene.org
    add_directory_item(
        "SerialeCoreene.org",
        build_url("list_serialecoreene_main"),
        icon="https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png",
    )

    # Movies
    add_directory_item(
        "Filme",
        build_url("list_movies_categories"),
        icon="https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg",
    )

    xbmcplugin.endOfDirectory(HANDLE)


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
        list_item.setProperty("IsPlayable", "false")

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
            url=build_url("play_source", url=video_url, title=name),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def play_source(url, title):
    """Play a video from URL with optimized handling for ok.ru and vk.com."""
    import time

    start_time = time.time()

    resolved = resolve_url_wrapper(url)

    if not resolved:
        xbmcgui.Dialog().ok(ADDON_NAME, "Could not resolve video URL.")
        return

    resolve_time = time.time() - start_time
    log(f"[play_source] Resolved in {resolve_time:.2f}s")

    # Handle StreamInfo objects (optimized resolvers)
    if isinstance(resolved, StreamInfo):
        log(f"[play_source] Using optimized StreamInfo: {resolved.manifest_type}")

        # Force HTTPS for CDN URLs
        if "http://" in resolved.url and any(
            domain in resolved.url for domain in ["vkuser.net", "okcdn.ru", "mycdn.me"]
        ):
            resolved.url = resolved.url.replace("http://", "https://")

        # Create properly configured ListItem
        list_item = create_listitem_with_stream(resolved, title or "Video")

        # Add buffer settings for MP4 files (slow loading fix)
        if resolved.is_mp4():
            # These properties help with slow-starting MP4s
            list_item.setProperty("VideoPlayer.UseFastSeek", "true")
            list_item.setProperty("VideoPlayer.OverrideEmbeddedSubtitles", "true")
            # Pre-cache hint
            list_item.setProperty("prefetch", "2")

    else:
        # Legacy string URL handling
        log("[play_source] Using legacy URL string")
        resolved_url = str(resolved)

        # Force HTTPS for CDN URLs
        if "http://" in resolved_url and any(
            domain in resolved_url for domain in ["vkuser.net", "okcdn.ru", "mycdn.me"]
        ):
            resolved_url = resolved_url.replace("http://", "https://")

        is_hls = ".m3u8" in resolved_url
        is_dash = ".mpd" in resolved_url

        list_item = xbmcgui.ListItem()
        list_item.setInfo("video", {"title": title or "Video"})

        if is_hls or is_dash:
            list_item.setProperty("inputstream", "inputstream.adaptive")
            # Don't set deprecated manifest_type - let ISA auto-detect
        else:
            # MP4 optimizations
            list_item.setProperty("VideoPlayer.UseFastSeek", "true")
            list_item.setProperty("prefetch", "2")

        list_item.setPath(resolved_url)

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


def search(query=None):
    """Search functionality."""
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    results = search_veziaici(query)

    for item in results:
        title = item.get("title", "")
        url = item.get("url", "")
        icon = get_custom_image(title)

        add_directory_item(
            title, build_url("list_sources", url=url, name=title), icon=icon
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
    categories = get_terasa_categories()

    for cat in categories:
        add_directory_item(
            cat.get("title", ""),
            build_url("list_turkish_series", url=cat.get("url", "")),
            icon=ADDON_ICON,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_series(url, page="1"):
    """List Turkish series episodes."""
    episodes, next_page = get_terasa_series(url, page)

    for ep in episodes:
        title = ep.get("title", "")
        ep_url = ep.get("url", "")
        thumb = ep.get("thumb", ADDON_ICON)

        list_item = xbmcgui.ListItem(title)
        list_item.setArt({"thumb": thumb, "icon": thumb})
        list_item.setInfo("video", {"title": title})

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
    """List episodes for a Korean series."""
    import json

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

    # Show episodes directly
    for ep in episodes:
        title = ep.get("title", "")
        ep_url = ep.get("url", "")

        list_item = xbmcgui.ListItem(title)
        list_item.setProperty("IsPlayable", "true")
        list_item.setInfo("video", {"title": title})

        full_title = f"{name} - {title}"
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_source", url=ep_url, title=full_title),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_season_episodes(url, season_title, name):
    """List episodes for a specific season."""
    episodes = get_season_episodes(url, season_title, name)

    for ep in episodes:
        title = ep.get("title", "")
        ep_url = ep.get("url", "")

        list_item = xbmcgui.ListItem(title)
        list_item.setProperty("IsPlayable", "true")
        list_item.setInfo("video", {"title": title})

        full_title = f"{name} - {title}"
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=build_url("play_source", url=ep_url, title=full_title),
            listitem=list_item,
            isFolder=False,
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


# SerialeCoreene.org
def list_serialecoreene_main():
    """Main menu for SerialeCoreene.org."""
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
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
    video_url = get_playable_url(url)

    if not video_url:
        xbmcgui.Dialog().ok(ADDON_NAME, "Nu s-a putut extrage sursa video.")
        return

    resolved = resolve_url_wrapper(video_url)

    if not resolved:
        xbmcgui.Dialog().ok(ADDON_NAME, "Could not resolve video URL.")
        return

    # Handle StreamInfo objects
    if isinstance(resolved, StreamInfo):
        list_item = create_listitem_with_stream(resolved, name)
    else:
        resolved_url = str(resolved)
        list_item = xbmcgui.ListItem(path=resolved_url)
        list_item.setInfo("video", {"title": name})

        if ".m3u8" in resolved_url or ".mpd" in resolved_url:
            list_item.setProperty("inputstream", "inputstream.adaptive")
            if ".m3u8" in resolved_url:
                list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            elif ".mpd" in resolved_url:
                list_item.setProperty("inputstream.adaptive.manifest_type", "mpd")

    xbmcgui.Window(10000).setProperty("VeziAici_Title", name)
    xbmcplugin.setResolvedUrl(HANDLE, True, list_item)


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
        search(params.get("query"))

    # Turkish series
    elif mode == "list_turkish_series_categories":
        list_turkish_series_categories()
    elif mode == "list_turkish_series":
        list_turkish_series(params.get("url"), params.get("page", "1"))
    elif mode == "list_turkish_sources":
        list_turkish_sources(params.get("url"), params.get("name"))

    # Korean/Asian series
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
        play_source(params.get("url"), params.get("title"))
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
