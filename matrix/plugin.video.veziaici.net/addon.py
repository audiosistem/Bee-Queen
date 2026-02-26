import xbmc
import sys
import xbmcvfs
import xbmcaddon
import xbmcgui
import xbmcplugin
import urllib.parse
import requests
import resolveurl
import json
import re
import os
import time
import base64
from bs4 import BeautifulSoup

# Add resources/lib to sys.path for importing bundled modules
addon = xbmcaddon.Addon()
addon_path = addon.getAddonInfo("path")
lib_path = os.path.join(addon_path, "resources", "lib")
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from resources.lib.trakt_api import TraktAPI

# Get the addon ID
ADDON_ID = addon.getAddonInfo("id")
ADDON = addon
HANDLE = int(sys.argv[1])
BASE_URL = "https://veziaici.net/"
CACHE_DIR = xbmcvfs.translatePath(
    os.path.join(xbmcaddon.Addon().getAddonInfo("profile"), "cache")
)
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": BASE_URL,
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
}


def _get_html_content(url):
    headers = HEADERS.copy()
    # Update Referer to match the domain we're requesting
    if "terasacucartii.net" in url:
        headers["Referer"] = "https://terasacucartii.net/"
    elif "terasacucarti" in url:
        headers["Referer"] = "https://www.terasacucarti.com/"
    return requests.get(url, headers=headers)


# Dictionary for custom show images
CUSTOM_IMAGES = {
    "insula iubirii": "https://www.fanatik.ro/wp-content/uploads/2024/08/insula-iubirii-2025.jpg",
    "las fierbinti": "https://upload.wikimedia.org/wikipedia/en/0/0d/Las_Fierbin%C8%9Bi_logo.png",
    "asia express": "https://cdn.adh.reperio.news/image-e/e410c82f-f849-4953-94fa-ed9ee2ba49bf/index.jpeg",
    "masterchef": "https://static4.libertatea.ro/wp-content/uploads/2024/02/masterchef-romania-revine-la-pro-tv.jpg",
    "the ticket": "https://static4.libertatea.ro/wp-content/uploads/2025/07/the-ticket.jpg",
    "vocea romaniei": "https://upload.wikimedia.org/wikipedia/ro/thumb/8/83/Vocea_Rom%C3%A2niei_-_compila%C8%9Bie.jpg/250px-Vocea_Rom%C3%A2niei_-_compila%C8%9Bie.jpg",
    "ana mi-ai fost scrisa in adn": "https://static4.libertatea.ro/wp-content/uploads/2024/11/ana-mi-ai-fost-scrisa-in-adn-serial-antena-1.jpg",
    "camera 609": "https://static.cinemagia.ro/img/resize/db/movie/33/10/231/lasa-ma-imi-place-camera-609-729239l-600x0-w-09e9e09b.jpg",
    "clanul": "https://cmero-ott-images-svod.ssl.cdn.cra.cz/r800x1160n/ad802c4a-901f-4700-9948-39361f41a677",
    "seriale": "https://upload.wikimedia.org/wikipedia/en/0/0d/Las_Fierbin%C8%9Bi_logo.png",
    "iubire cu": "https://dcasting.ro/wp-content/uploads/2025/02/Iubire-cu-parfum-de-lavanda.jpg",
    "sotia sotului": "https://onemagia.com/upload/images/e7mDxkP6Qgbo735USy5telMF1wF.jpg",
    "scara b": "https://static4.libertatea.ro/wp-content/uploads/2024/08/scara-b-scaled.jpg",
    "tatutu": "https://image.stirileprotv.ro/media/images/1920x1080/Jun2025/62556367.jpg",
}


def get_main_menu_items():
    try:
        response = _get_html_content(BASE_URL)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch main page: {e}"
        )
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    categories = []

    for top_li in soup.select("ul#main-menu > li.menu-item-has-children"):
        category_title_element = top_li.find("span")
        if not category_title_element:
            continue

        category_title = category_title_element.text.strip()
        sub_menu = top_li.find("ul", class_="sub-menu")

        if category_title and sub_menu:
            shows = []
            for sub_li in sub_menu.find_all("li"):
                link = sub_li.find("a")
                if link and "href" in link.attrs:
                    title = link.text.strip()
                    url = link["href"]
                    if title and url:
                        shows.append({"title": title, "url": url})
            if shows:
                categories.append({"title": category_title, "shows": shows})

    return categories


def list_main_menu():
    # Add a static search item
    list_item = xbmcgui.ListItem("Cauta")
    search_icon = "https://i.imgur.com/dvqhLCI.png"
    list_item.setArt({"icon": search_icon, "thumb": search_icon})
    url = sys.argv[0] + "?" + urllib.parse.urlencode({"mode": "search"})
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=url, listitem=list_item, isFolder=True
    )

    categories = get_main_menu_items()
    for category in categories:
        list_item = xbmcgui.ListItem(category["title"])
        category_icon = ADDON.getAddonInfo("icon")  # Initialize with default

        if "emisiuni" in category["title"].lower():
            category_icon = CUSTOM_IMAGES.get("asia express", category_icon)
            url = (
                sys.argv[0]
                + "?"
                + urllib.parse.urlencode(
                    {
                        "mode": "list_show_categories",
                        "shows": json.dumps(category["shows"]),
                        "name": category["title"],
                        "latest_url": "https://veziaici.net/category/a-emisiuni-romanesti/",
                    }
                )
            )
        elif "seriale" in category["title"].lower():
            category_icon = CUSTOM_IMAGES.get("las fierbinti", category_icon)
            url = (
                sys.argv[0]
                + "?"
                + urllib.parse.urlencode(
                    {
                        "mode": "list_show_categories",
                        "shows": json.dumps(category["shows"]),
                        "name": category["title"],
                        "latest_url": "https://veziaici.net/category/c-seriale-romanesti/",
                    }
                )
            )
        else:
            url = (
                sys.argv[0]
                + "?"
                + urllib.parse.urlencode(
                    {
                        "mode": "list_shows",
                        "shows": json.dumps(category["shows"]),
                        "name": category["title"],
                    }
                )
            )

        list_item.setArt({"icon": category_icon, "thumb": category_icon})
        xbmcplugin.addDirectoryItem(
            handle=HANDLE, url=url, listitem=list_item, isFolder=True
        )

    # Add a static folder for Seriale Turcesti
    list_item = xbmcgui.ListItem("Seriale Turcesti")
    turk_icon = "https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg"
    list_item.setArt({"icon": turk_icon, "thumb": turk_icon})
    url = (
        sys.argv[0]
        + "?"
        + urllib.parse.urlencode({"mode": "list_turkish_series_categories"})
    )
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=url, listitem=list_item, isFolder=True
    )

    # Add a static folder for Seriale Coreene
    list_item = xbmcgui.ListItem("Seriale Coreene")
    korean_icon = "https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg"
    list_item.setArt({"icon": korean_icon, "thumb": korean_icon})
    url = (
        sys.argv[0]
        + "?"
        + urllib.parse.urlencode({"mode": "list_korean_series_categories"})
    )
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=url, listitem=list_item, isFolder=True
    )

    # Add a static folder for Seriale Chinezesti
    list_item = xbmcgui.ListItem("Seriale Chinezesti")
    list_item.setArt({"icon": korean_icon, "thumb": korean_icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/serialefilme-chinezesti/",
        "name": "Seriale Chinezesti",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Add a static folder for Seriale Japoneze
    list_item = xbmcgui.ListItem("Seriale Japoneze")
    list_item.setArt({"icon": korean_icon, "thumb": korean_icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/seriale-japoneze/",
        "name": "Seriale Japoneze",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Add a static folder for Seriale Thailandeze
    list_item = xbmcgui.ListItem("Seriale Thailandeze")
    list_item.setArt({"icon": korean_icon, "thumb": korean_icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/seriale-thailandeze/",
        "name": "Seriale Thailandeze",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Add a static folder for Seriale Taiwan
    list_item = xbmcgui.ListItem("Seriale Taiwan")
    list_item.setArt({"icon": korean_icon, "thumb": korean_icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/serialefilme-taiwanezethailandeze/",
        "name": "Seriale Taiwan",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Add a static folder for SerialeCoreene.org
    list_item = xbmcgui.ListItem("SerialeCoreene.org")
    serialecoreene_icon = (
        "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
    )
    list_item.setArt({"icon": serialecoreene_icon, "thumb": serialecoreene_icon})
    url = (
        sys.argv[0] + "?" + urllib.parse.urlencode({"mode": "list_serialecoreene_main"})
    )
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=url, listitem=list_item, isFolder=True
    )

    # Add a static folder for Filme
    list_item = xbmcgui.ListItem("Filme")
    filme_icon = "https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg"
    list_item.setArt({"icon": filme_icon, "thumb": filme_icon})
    url = sys.argv[0] + "?" + urllib.parse.urlencode({"mode": "list_movies_categories"})
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=url, listitem=list_item, isFolder=True
    )

    xbmcplugin.endOfDirectory(HANDLE)


def list_show_categories(shows_json, name, latest_url):
    # Add "Ultimile adaugate" item
    list_item = xbmcgui.ListItem("Ultimile adaugate")
    url_params = {"mode": "list_latest", "url": latest_url, "name": "Ultimile adaugate"}
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Add the rest of the shows
    shows = json.loads(shows_json)
    for show in shows:
        list_item = xbmcgui.ListItem(show["title"])

        # Default icon
        show_icon = ADDON.getAddonInfo("icon")
        # Check for custom image
        for keyword, image_url in CUSTOM_IMAGES.items():
            if keyword in show["title"].lower():
                show_icon = image_url
                break

        list_item.setArt({"icon": show_icon, "thumb": show_icon})
        url = (
            sys.argv[0]
            + "?"
            + urllib.parse.urlencode(
                {"mode": "list_episodes", "url": show["url"], "name": show["title"]}
            )
        )
        xbmcplugin.addDirectoryItem(
            handle=HANDLE, url=url, listitem=list_item, isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def list_shows(shows_json):
    shows = json.loads(shows_json)
    for show in shows:
        list_item = xbmcgui.ListItem(show["title"])

        # Default icon
        show_icon = ADDON.getAddonInfo("icon")
        # Check for custom image
        for keyword, image_url in CUSTOM_IMAGES.items():
            if keyword in show["title"].lower():
                show_icon = image_url
                break

        list_item.setArt({"icon": show_icon, "thumb": show_icon})
        url = (
            sys.argv[0]
            + "?"
            + urllib.parse.urlencode(
                {"mode": "list_episodes", "url": show["url"], "name": show["title"]}
            )
        )
        xbmcplugin.addDirectoryItem(
            handle=HANDLE, url=url, listitem=list_item, isFolder=True
        )
    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes(url, name=""):
    cache_file = os.path.join(CACHE_DIR, name.replace(" ", "_") + ".json")
    cache_expiry = 24 * 3600  # 24 hours

    all_episodes = []

    # Try to load from cache first
    # Force refresh to clear potentially bad cache
    if (
        False
        and os.path.exists(cache_file)
        and (time.time() - os.path.getmtime(cache_file)) < cache_expiry
    ):
        with open(cache_file, "r") as f:
            all_episodes = json.load(f)
    else:
        # If cache is invalid or missing, scrape all pages
        current_url = url
        while current_url:
            try:
                response = _get_html_content(current_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except requests.exceptions.RequestException:
                break

            for title_element in soup.find_all(["h3", "h2"], class_="entry-title"):
                if title_element.find("a"):
                    link_element = title_element.find("a")
                    item_url = link_element.get("href")
                    title = link_element.text.strip()
                    if item_url and title:
                        all_episodes.append(
                            {"title": title, "url": item_url, "name": name}
                        )

            next_page_link = soup.find("a", class_="next page-numbers")
            if next_page_link and next_page_link.has_attr("href"):
                current_url = next_page_link["href"]
            else:
                current_url = None

        # Save to cache
        with open(cache_file, "w") as f:
            json.dump(all_episodes, f)

    # --- The rest of the function remains the same, processing 'all_episodes' ---

    # Extract seasons from episode titles
    seasons = {}
    no_season_episodes = []
    for episode in all_episodes:
        match = re.search(r"sez(?:onul|on|\.)\s*(\d+)", episode["title"], re.IGNORECASE)
        if match:
            season_num = int(match.group(1))
            if season_num not in seasons:
                seasons[season_num] = []
            seasons[season_num].append(episode)
        else:
            no_season_episodes.append(episode)

    # If only one season is found and no episodes without a season, list them directly
    if len(seasons) == 1 and not no_season_episodes:
        season_num = list(seasons.keys())[0]
        list_episodes_for_season(json.dumps(seasons[season_num]), season_num, name)
        return

    # Create folders for each season
    for season_num in sorted(seasons.keys(), reverse=True):
        list_item = xbmcgui.ListItem(f"Sezonul {season_num}")
        season_icon = ADDON.getAddonInfo("icon")
        for keyword, image_url in CUSTOM_IMAGES.items():
            if keyword in name.lower():
                season_icon = image_url
                break
        list_item.setArt({"icon": season_icon, "thumb": season_icon})
        url_params = {
            "mode": "list_episodes_for_season",
            "episodes": json.dumps(seasons[season_num]),
            "season": season_num,
            "name": name,
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    if no_season_episodes:
        list_item = xbmcgui.ListItem("Fara Sezon")
        list_item.setArt(
            {"icon": ADDON.getAddonInfo("icon"), "thumb": ADDON.getAddonInfo("icon")}
        )
        url_params = {
            "mode": "list_episodes_for_season",
            "episodes": json.dumps(no_season_episodes),
            "season": "0",
            "name": name,
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes_for_season(episodes_json, season, name=""):
    episodes = json.loads(episodes_json)
    custom_image_found = None
    for keyword, image_url in CUSTOM_IMAGES.items():
        if keyword in name.lower():
            custom_image_found = image_url
            break

    for episode in episodes:
        list_item = xbmcgui.ListItem(episode["title"])
        image_to_use = (
            custom_image_found if custom_image_found else ADDON.getAddonInfo("icon")
        )
        list_item.setArt(
            {
                "thumb": image_to_use,
                "icon": image_to_use,
                "fanart": ADDON.getAddonInfo("fanart"),
            }
        )
        list_item.setInfo("video", {"title": episode["title"]})
        url_params = {"mode": "list_sources", "url": episode["url"]}
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(HANDLE)


def list_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch source page: {e}"
        )
        return

    iframes = soup.find_all("iframe", attrs={"data-lazy-src": True})
    for iframe in iframes:
        video_url = iframe["data-lazy-src"]

        if "player3.funny-cats.org" in video_url:
            continue

        if video_url.startswith("//"):
            video_url = "https:" + video_url

        domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")

        list_item = xbmcgui.ListItem(f"Sursa: {domain}")
        list_item.setInfo("video", {"title": f"Sursa: {domain}"})
        list_item.setProperty("IsPlayable", "true")

        # Pass the real title (name) to play_source
        url_params = {"mode": "play_source", "url": video_url, "title": name}

        context_menu_items = [
            (
                "Download",
                f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})",
            )
        ]
        list_item.addContextMenuItems(context_menu_items)
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def resolve_url_wrapper(url):
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Resolving URL: {url.split('/')[2]}",
        xbmc.LOGINFO,
    )

    # Check if URL is from a domain that requires special handling
    is_ok_ru = any(domain in url for domain in ["ok.ru", "odnoklassniki.ru"])
    is_vk = any(domain in url for domain in ["vk.com", "vkvideo.ru", "vkontakte.ru"])

    # For ok.ru and vk.com, skip ResolveURL and use direct extraction
    # ResolveURL returns token URLs that don't work in Kodi
    if is_ok_ru or is_vk:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Using direct extraction for {url.split('/')[2]}",
            xbmc.LOGINFO,
        )

        if is_ok_ru:
            try:
                result = _extract_ok_ru_url(url)
                if result:
                    xbmc.log(
                        f"[{ADDON.getAddonInfo('name')}] ok.ru extraction success: {result[:150]}...",
                        xbmc.LOGINFO,
                    )
                    return result
            except Exception as e:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] ok.ru extraction failed: {e}",
                    xbmc.LOGWARNING,
                )

        if is_vk:
            try:
                result = _extract_vk_url(url)
                if result:
                    xbmc.log(
                        f"[{ADDON.getAddonInfo('name')}] vk extraction success: {result[:150]}...",
                        xbmc.LOGINFO,
                    )
                    return result
            except Exception as e:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] vk extraction failed: {e}",
                    xbmc.LOGWARNING,
                )

    # For other domains, try ResolveURL
    try:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Trying ResolveURL for {url.split('/')[2]}",
            xbmc.LOGINFO,
        )
        if resolveurl.HostedMediaFile(url=url).valid_url():
            resolved = resolveurl.resolve(url)
            if resolved:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] ResolveURL success: {resolved[:150]}...",
                    xbmc.LOGINFO,
                )
                return resolved
            else:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] ResolveURL returned None",
                    xbmc.LOGWARNING,
                )
    except Exception as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] ResolveURL Error: {e}", xbmc.LOGERROR)

    # If we get here and it's an ok.ru/vk.com URL, the direct extraction already failed
    # and resolveurl also failed - nothing more we can do
    if url.endswith(".mp4") or url.endswith(".m3u8"):
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Returning direct URL as fallback",
            xbmc.LOGINFO,
        )
        return url

    return None


def _extract_ok_ru_url(url):
    """Extract video URL from ok.ru embed page - based on yt-dlp extractor"""
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Extracting ok.ru URL: {url}", xbmc.LOGINFO
    )

    import json

    # Create a session to maintain cookies
    session = requests.Session()

    try:
        # Fetch the embed page
        response = session.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        webpage = response.text
    except requests.exceptions.RequestException as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Failed to fetch ok.ru page: {e}",
            xbmc.LOGERROR,
        )
        return None

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] ok.ru page content length: {len(webpage)}",
        xbmc.LOGDEBUG,
    )

    # Check for errors
    if "vp_video_stub_txt" in webpage:
        error = re.search(r'[^>]+class="vp_video_stub_txt"[^>]*>([^<]+)<', webpage)
        if error:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] ok.ru error: {error.group(1)}",
                xbmc.LOGERROR,
            )
            return None

    # Extract player data from data-options
    player_match = re.search(
        r'data-options=(?P<quote>["\'])(?P<player>{.+?})(?P=quote)', webpage, re.DOTALL
    )

    if not player_match:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] No player data found", xbmc.LOGWARNING
        )
        return None

    try:
        player_data = json.loads(player_match.group("player").replace("&quot;", '"'))
        flashvars = player_data.get("flashvars", {})

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] ok.ru flashvars keys: {list(flashvars.keys())}",
            xbmc.LOGDEBUG,
        )

        # Get metadata
        metadata = flashvars.get("metadata")
        if metadata:
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
        else:
            # Fetch metadata from URL
            metadata_url = flashvars.get("metadataUrl")
            if metadata_url:
                metadata_url = urllib.parse.unquote(metadata_url)
                data = {}
                if flashvars.get("location"):
                    data["st.location"] = flashvars["location"]

                try:
                    meta_response = session.post(
                        metadata_url,
                        data=urllib.parse.urlencode(data),
                        headers=HEADERS,
                        timeout=10,
                    )
                    metadata = meta_response.json()
                except Exception as e:
                    xbmc.log(
                        f"[{ADDON.getAddonInfo('name')}] Failed to fetch metadata: {e}",
                        xbmc.LOGWARNING,
                    )
                    return None

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] ok.ru metadata keys: {list(metadata.keys()) if metadata else 'None'}",
            xbmc.LOGDEBUG,
        )

        if not metadata or "movie" not in metadata:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] No movie data in metadata",
                xbmc.LOGWARNING,
            )
            return None

        movie = metadata["movie"]
        provider = metadata.get("provider", "")

        # Handle YouTube embeds
        if provider == "USER_YOUTUBE":
            youtube_url = movie.get("contentId")
            if youtube_url:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] YouTube embed detected: {youtube_url}",
                    xbmc.LOGINFO,
                )
                return youtube_url

        # Collect all formats
        formats = []

        # Direct video formats
        videos = metadata.get("videos", [])
        for video in videos:
            video_url = video.get("url")
            if video_url:
                formats.append(
                    {
                        "url": video_url,
                        "format_id": video.get("name", "unknown"),
                        "width": int_or_none(video.get("width")),
                        "height": int_or_none(video.get("height")),
                    }
                )

        # HLS manifest - try both keys
        hls_url = metadata.get("hlsManifestUrl") or metadata.get("ondemandHls")
        if hls_url:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] HLS manifest found: {hls_url[:150]}...",
                xbmc.LOGINFO,
            )
            # HLS manifests are preferred for ok.ru
            formats.append(
                {
                    "url": hls_url,
                    "format_id": "hls",
                    "ext": "mp4",
                    "protocol": "m3u8",
                }
            )

        # DASH manifest
        dash_url = metadata.get("ondemandDash") or metadata.get("metadataWebmUrl")
        if dash_url:
            formats.append(
                {
                    "url": dash_url,
                    "format_id": "dash",
                }
            )

        # Live HLS
        live_hls = metadata.get("hlsMasterPlaylistUrl")
        if live_hls:
            formats.append(
                {
                    "url": live_hls,
                    "format_id": "live-hls",
                }
            )

        if not formats:
            # Check if paid
            if metadata.get("paymentInfo"):
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Video is paid", xbmc.LOGWARNING
                )
                return None
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] No formats found", xbmc.LOGWARNING
            )
            return None

        # Sort formats: prefer HLS over direct URLs, then by quality
        def format_key(fmt):
            fmt_id = fmt.get("format_id", "")
            width = fmt.get("width") or 0
            height = fmt.get("height") or 0
            url = fmt.get("url", "")

            # Prefer HLS manifests
            is_hls = "hls" in fmt_id.lower() or ".m3u8" in url
            # Prefer higher quality
            quality = max(width, height)

            return (is_hls, quality)

        formats.sort(key=format_key, reverse=True)
        best_format = formats[0]

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Total formats: {len(formats)}",
            xbmc.LOGINFO,
        )
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Best format: {best_format['format_id']}, URL length: {len(best_format['url'])}",
            xbmc.LOGINFO,
        )

        # Clear cookies for direct download
        session.cookies.clear()

        return best_format["url"]

    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Failed to extract ok.ru: {e}",
            xbmc.LOGERROR,
        )
        import traceback

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Traceback: {traceback.format_exc()}",
            xbmc.LOGERROR,
        )
        return None


def _extract_vk_url(url):
    """Extract video URL from vk.com/vkvideo.ru using VK API (like streamlink)"""
    xbmc.log(f"[{ADDON.getAddonInfo('name')}] Extracting vk URL: {url}", xbmc.LOGINFO)

    # Extract video ID from URL
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    oid = params.get("oid", [None])[0]
    video_id = params.get("id", [None])[0]

    if not oid or not video_id:
        match = re.search(r"video(-?\d+)_(\d+)", url)
        if match:
            oid = match.group(1)
            video_id = match.group(2)

    if not oid or not video_id:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Could not extract VK video IDs",
            xbmc.LOGWARNING,
        )
        return None

    video_id_full = f"{oid}_{video_id}"
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] VK video ID: {video_id_full}", xbmc.LOGINFO
    )

    # Use VK API like streamlink does
    api_url = "https://vk.com/al_video.php"

    # First, get the page to establish session/cookies
    session = requests.Session()

    # First request to get cookies/WAF token
    try:
        main_page = session.get("https://vk.com/", headers=HEADERS, timeout=15)
    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Failed to get VK main page: {e}",
            xbmc.LOGWARNING,
        )

    # Now make the API request
    api_headers = HEADERS.copy()
    api_headers["Referer"] = "https://vk.com/"
    api_headers["X-Requested-With"] = "XMLHttpRequest"
    api_headers["Content-Type"] = "application/x-www-form-urlencoded"

    post_data = {"act": "show", "al": "1", "video": video_id_full}

    try:
        response = session.post(
            api_url, data=post_data, headers=api_headers, timeout=15
        )
        response_text = response.text

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] API response length: {len(response_text)}",
            xbmc.LOGDEBUG,
        )

        # Parse the response - it's JSON wrapped in some text
        # Look for player params in the response
        import json

        # Try to find JSON data in response
        json_match = re.search(r'\{.*"player".*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if "player" in data and "params" in data["player"]:
                    player_params = data["player"]["params"]
                    if isinstance(player_params, list) and len(player_params) > 0:
                        params = player_params[0]

                        # Look for HLS URL
                        for key in ["hls", "hls_ondemand", "hls_live"]:
                            if key in params and params[key]:
                                hls_url = params[key]
                                xbmc.log(
                                    f"[{ADDON.getAddonInfo('name')}] Found HLS URL: {hls_url[:80]}...",
                                    xbmc.LOGINFO,
                                )
                                return hls_url

                        # Look for DASH URL
                        for key in ["dash", "dash_ondemand", "dash_live"]:
                            if key in params and params[key]:
                                dash_url = params[key]
                                xbmc.log(
                                    f"[{ADDON.getAddonInfo('name')}] Found DASH URL: {dash_url[:80]}...",
                                    xbmc.LOGINFO,
                                )
                                return dash_url
            except Exception as e:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Error parsing API response: {e}",
                    xbmc.LOGDEBUG,
                )

        # Try alternative parsing - look for "hls" key in response
        if '"hls"' in response_text:
            hls_match = re.search(r'"hls"\s*:\s*"([^"]+)"', response_text)
            if hls_match:
                hls_url = hls_match.group(1).replace("\\/", "/")
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Found HLS in response",
                    xbmc.LOGINFO,
                )
                return hls_url

        if '"hls_ondemand"' in response_text:
            hls_match = re.search(r'"hls_ondemand"\s*:\s*"([^"]+)"', response_text)
            if hls_match:
                hls_url = hls_match.group(1).replace("\\/", "/")
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Found HLS ondemand in response",
                    xbmc.LOGINFO,
                )
                return hls_url

    except Exception as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] VK API error: {e}", xbmc.LOGWARNING)

    # Fallback: try to extract from webpage
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Trying fallback extraction from page",
        xbmc.LOGINFO,
    )

    direct_url = f"https://vk.com/video{video_id_full}"

    try:
        response = requests.get(direct_url, headers=HEADERS, timeout=15)
        webpage = response.text
    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Failed to fetch VK page: {e}",
            xbmc.LOGERROR,
        )
        return None

    # Try patterns to find URLs
    sPattern = r'"url\d*"\s*:\s*"(.+?)\.(\d+)\.mp4'
    matches = re.findall(sPattern, webpage)

    if matches:
        url_list = []
        for match in matches:
            base_url = match[0]
            quality = match[1]
            video_url = f"{base_url}.{quality}.mp4"
            url_list.append((quality, video_url))

        url_list.sort(key=lambda x: int(x[0]), reverse=True)
        best_quality, best_url = url_list[0]
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Best mp4 quality: {best_quality}p",
            xbmc.LOGINFO,
        )
        return best_url

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Could not extract VK URL", xbmc.LOGWARNING
    )
    return None

    # Use vStream pattern to extract mp4 URLs
    # Pattern: "url":"base_url.480.mp4" etc.
    sPattern = r'"url\d*"\s*:\s*"(.+?)\.(\d+)\.mp4'

    matches = re.findall(sPattern, webpage)

    if matches:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Found {len(matches)} video URLs",
            xbmc.LOGINFO,
        )

        # Build list of URLs with quality
        url_list = []
        for match in matches:
            base_url = match[0]
            quality = match[1]
            video_url = f"{base_url}.{quality}.mp4"
            url_list.append((quality, video_url))

        # Sort by quality (highest first)
        url_list.sort(key=lambda x: int(x[0]), reverse=True)

        # Return highest quality URL
        best_quality, best_url = url_list[0]
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Best quality: {best_quality}p",
            xbmc.LOGINFO,
        )
        return best_url

    # Try alternative patterns
    alt_patterns = [
        r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"',
        r'"cache\d*"\s*:\s*"([^"]+\.mp4[^"]*)"',
        r'url\d*\s*=\s*["\']([^"\']+\.mp4[^"\']+)["\']',
    ]

    for pattern in alt_patterns:
        matches = re.findall(pattern, webpage)
        if matches:
            video_url = matches[-1].replace("\\/", "/")
            if video_url.startswith("http"):
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Found mp4 URL with alt pattern",
                    xbmc.LOGINFO,
                )
                return video_url

    # Try to find any mp4 URL in the page
    mp4_matches = re.findall(r'https?://[^"\'>\s]+\.mp4', webpage)
    if mp4_matches:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Found {len(mp4_matches)} mp4 URLs",
            xbmc.LOGINFO,
        )
        return mp4_matches[-1]

    # Try to find m3u8 URL
    m3u8_matches = re.findall(r'https?://[^"\'>\s]+\.m3u8[^"\'>\s]*', webpage)
    if m3u8_matches:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Found m3u8 URL", xbmc.LOGINFO)
        return m3u8_matches[0]

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] No video URL found in VK page", xbmc.LOGWARNING
    )
    return None

    # Use vStream pattern to extract mp4 URLs
    # Pattern: "url":"base_url.480.mp4" etc.
    sPattern = r'"url\d*"\s*:\s*"(.+?)\.(\d+)\.mp4'

    matches = re.findall(sPattern, webpage)

    if matches:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Found {len(matches)} video URLs",
            xbmc.LOGINFO,
        )

        # Build list of URLs with quality
        url_list = []
        for match in matches:
            base_url = match[0]
            quality = match[1]
            video_url = f"{base_url}.{quality}.mp4"
            url_list.append((quality, video_url))

        # Sort by quality (highest first)
        url_list.sort(key=lambda x: int(x[0]), reverse=True)

        # Return highest quality URL
        best_quality, best_url = url_list[0]
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Best quality: {best_quality}p",
            xbmc.LOGINFO,
        )
        return best_url

    # Try alternative pattern
    alt_pattern = r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"'
    matches = re.findall(alt_pattern, webpage)
    if matches:
        # Get the last one (usually highest quality)
        video_url = matches[-1].replace("\\/", "/")
        if video_url.startswith("http"):
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Found mp4 URL: {video_url[:80]}...",
                xbmc.LOGINFO,
            )
            return video_url

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] No video URL found in VK page", xbmc.LOGWARNING
    )
    return None

    # Try to get video from the main VK page (not embed)
    video_url = f"https://vk.com/video{oid}_{video_id}"

    try:
        response = requests.get(video_url, headers=HEADERS, timeout=15)
        webpage = response.text

        # Look for video data in the page
        # Try playerParams first
        player_params_match = re.search(
            r"var\s+playerParams\s*=\s*({.+?});", webpage, re.DOTALL
        )
        if player_params_match:
            try:
                player_params = json.loads(player_params_match.group(1))
                if "params" in player_params:
                    params_data = player_params["params"]
                    if isinstance(params_data, list) and len(params_data) > 0:
                        data = params_data[0]
                        # Look for URL fields
                        for key in data:
                            if isinstance(data[key], str):
                                val = data[key]
                                if ".m3u8" in val or ".mp4" in val:
                                    xbmc.log(
                                        f"[{ADDON.getAddonInfo('name')}] Found URL in playerParams: {key}",
                                        xbmc.LOGINFO,
                                    )
                                    return val
            except Exception as e:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Error parsing playerParams: {e}",
                    xbmc.LOGDEBUG,
                )

        # Look for direct URLs in the page
        patterns = [
            r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'"url(\d+)"\s*:\s*"([^"]+\.mp4[^"]*)"',
            r'"cache\d*"\s*:\s*"([^"]+\.mp4[^"]*)"',
        ]

        all_urls = []
        for pattern in patterns:
            matches = re.findall(pattern, webpage)
            for match in matches:
                video_url = match[1] if isinstance(match, tuple) else match
                video_url = video_url.replace("\\/", "/")
                if video_url.startswith("http"):
                    all_urls.append(video_url)

        if all_urls:
            m3u8_urls = [u for u in all_urls if ".m3u8" in u]
            if m3u8_urls:
                return m3u8_urls[0]
            mp4_urls = [u for u in all_urls if ".mp4" in u]
            if mp4_urls:
                return mp4_urls[-1]

    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Error fetching VK page: {e}",
            xbmc.LOGWARNING,
        )

    # If direct extraction failed, try ResolveURL but DON'T return token URL
    # Instead, return None to indicate failure
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Direct extraction failed, skipping ResolveURL",
        xbmc.LOGINFO,
    )
    return None

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] VK: oid={oid}, id={video_id}", xbmc.LOGINFO
    )

    # Try VK API to get video info
    api_url = f"https://vk.com/al_video.php?act=show_inline&al=1&video={oid}_{video_id}"

    try:
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        webpage = response.text

        # Look for playerVars or video data in response
        player_match = re.search(r'"playerVars"\s*:\s*"([^"]+)"', webpage)
        if player_match:
            import base64

            try:
                player_vars = player_match.group(1)
                decoded = base64.b64decode(player_vars).decode("utf-8")
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Found playerVars", xbmc.LOGDEBUG
                )

                # Try to find URL in decoded data
                url_match = re.search(r'"url"\s*:\s*"([^"]+)"', decoded)
                if url_match:
                    video_url = url_match.group(1).replace("\\/", "/")
                    if video_url.startswith("http"):
                        xbmc.log(
                            f"[{ADDON.getAddonInfo('name')}] Found URL in playerVars",
                            xbmc.LOGINFO,
                        )
                        return video_url
            except Exception as e:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Error decoding playerVars: {e}",
                    xbmc.LOGDEBUG,
                )

        # Try to find raw video data
        video_data_match = re.search(r'"video"\s*:\s*(\{[^}]+\})', webpage)
        if video_data_match:
            try:
                video_data = json.loads(video_data_match.group(1))
                # Look for various URL fields
                for key in ["url", "mp4", "m3u8", "src"]:
                    if key in video_data:
                        val = video_data[key]
                        if isinstance(val, str) and val.startswith("http"):
                            xbmc.log(
                                f"[{ADDON.getAddonInfo('name')}] Found URL in video data: {key}",
                                xbmc.LOGINFO,
                            )
                            return val
            except:
                pass

    except Exception as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] VK API error: {e}", xbmc.LOGWARNING)

    # Fallback: try ResolveURL then follow redirects with proper headers
    try:
        from importlib import import_module

        resolveurl = import_module("resolveurl")
        if resolveurl.HostedMediaFile(url=url).valid_url():
            token_url = resolveurl.resolve(url)
            if token_url:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] ResolveURL token: {token_url[:80]}...",
                    xbmc.LOGINFO,
                )

                # Try with VK-specific headers
                session = requests.Session()
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://vk.com/",
                    "Origin": "https://vk.com",
                }

                # Try GET with Range header to get actual content
                resp = session.get(
                    token_url,
                    headers=headers,
                    allow_redirects=True,
                    stream=True,
                    timeout=30,
                )
                final_url = resp.url

                # Check for m3u8 in URL
                if ".m3u8" in final_url:
                    return final_url

                # Check headers for redirect
                if "Location" in resp.headers:
                    loc = resp.headers["Location"]
                    if ".m3u8" in loc:
                        return loc

                # Try reading first bytes to see content type
                resp.close()

                # If still a token URL, return it with special handling in play_source
                # The issue might be that Kodi needs different headers
                return token_url

    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] ResolveURL fallback error: {e}",
            xbmc.LOGDEBUG,
        )

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Could not extract VK URL", xbmc.LOGWARNING
    )
    return None

    # Try to find video URLs in page
    patterns = [
        r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
        r'"url(\d+)"\s*:\s*"([^"]+\.mp4[^"]*)"',
        r'"cache\d*"\s*:\s*"([^"]+\.mp4[^"]*)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, webpage)
        for match in matches:
            video_url = match[1] if isinstance(match, tuple) else match
            video_url = video_url.replace("\\/", "/")
            if video_url.startswith("http"):
                if ".m3u8" in video_url:
                    return video_url
                if ".mp4" in video_url:
                    return video_url

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] No video URL found in VK page", xbmc.LOGWARNING
    )
    return None

    # Try to find video URLs in page
    patterns = [
        r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
        r'"url(\d+)"\s*:\s*"([^"]+\.mp4[^"]*)"',
        r'"cache\d*"\s*:\s*"([^"]+\.mp4[^"]*)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, webpage)
        for match in matches:
            video_url = match[1] if isinstance(match, tuple) else match
            video_url = video_url.replace("\\/", "/")
            if video_url.startswith("http"):
                if ".m3u8" in video_url:
                    return video_url
                if ".mp4" in video_url:
                    # Return mp4, prefer higher quality (usually last)
                    return video_url

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] No video URL found in VK page", xbmc.LOGWARNING
    )
    return None


def int_or_none(value, default=None):
    """Helper function to convert value to int or return default"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def unescapeHTML(text):
    """Helper function to unescape HTML entities"""
    if not text:
        return text
    return (
        text.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("\\/", "/")
    )


def _extract_vidmoly_url(url):
    """Extract direct video URL from vidmoly embed page"""
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Extracting vidmoly URL: {url}", xbmc.LOGINFO
    )

    try:
        parsed = urllib.parse.urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}/"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Referer": url,
            "Sec-Fetch-Dest": "iframe",
        }

        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Vidmoly page status: {response.status_code}",
            xbmc.LOGINFO,
        )

        page_content = response.text

        # Try to find any m3u8 or mp4 URLs directly
        direct_url_patterns = [
            r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*',
        ]

        for pattern in direct_url_patterns:
            matches = re.findall(pattern, page_content)
            if matches:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Found direct URL with pattern: {pattern}",
                    xbmc.LOGINFO,
                )
                video_url = matches[0]
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Vidmoly found URL: {video_url[:100]}...",
                    xbmc.LOGINFO,
                )
                return video_url

        # Extract video URL - use pattern from the code: sources: [{file:"..."}]
        patterns = [
            r'sources:\s*\[\{file:\s*"([^"]+)"',
            r"sources:\s*\[\{file:\s*\'([^\']+)\'",
            r'file:\s*"([^"]+\.m3u8[^"]*)"',
            r"file:\s*\'([^\']+\.m3u8[^\']*)\'",
            r'"file"\s*:\s*"([^"]+)"',
            r'file:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_content)
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Trying pattern: {pattern[:30]}..., match: {match is not None}",
                xbmc.LOGDEBUG,
            )
            if match:
                video_url = match.group(1)
                # Clean up the URL
                video_url = video_url.replace("\\/", "/").strip('"').strip("'")

                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Matched URL: {video_url[:100]}",
                    xbmc.LOGINFO,
                )

                # Handle relative URLs
                if not video_url.startswith("http"):
                    video_url = urllib.parse.urljoin(base_domain, video_url)

                if video_url.startswith("//"):
                    video_url = "https:" + video_url

                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Vidmoly found URL: {video_url[:100]}...",
                    xbmc.LOGINFO,
                )
                return video_url

    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Vidmoly extraction failed: {e}",
            xbmc.LOGERROR,
        )

    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Vidmoly: No video URL found", xbmc.LOGWARNING
    )
    return None


def _extract_filemoon_url(url):
    """Extract direct video URL from filemoon embed page"""
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Extracting filemoon URL: {url}", xbmc.LOGINFO
    )

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Referer": url,
        }

        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Filemoon page status: {response.status_code}",
            xbmc.LOGINFO,
        )

        page_content = response.text

        # Find iframe
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', page_content)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Found iframe: {iframe_url}",
                xbmc.LOGINFO,
            )

            # Handle relative URLs
            if iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url
            elif iframe_url.startswith("/"):
                parsed = urllib.parse.urlparse(url)
                iframe_url = f"{parsed.scheme}://{parsed.netloc}{iframe_url}"

            # Now fetch the iframe page
            iframe_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                "Referer": url,
            }

            iframe_response = requests.get(
                iframe_url, headers=iframe_headers, timeout=15, allow_redirects=True
            )
            iframe_content = iframe_response.text

            # Extract video URL - look for file:"..." pattern
            video_match = re.search(r'file:\s*"([^"]+)"', iframe_content)
            if video_match:
                video_url = video_match.group(1)
                # Handle relative URLs
                if video_url.startswith("//"):
                    video_url = "https:" + video_url
                elif not video_url.startswith("http"):
                    parsed = urllib.parse.urlparse(iframe_url)
                    video_url = f"{parsed.scheme}://{parsed.netloc}/{video_url}"

                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Filemoon found URL: {video_url[:100]}...",
                    xbmc.LOGINFO,
                )
                return video_url

            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Filemoon: No file URL found in iframe",
                xbmc.LOGWARNING,
            )
        else:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Filemoon: No iframe found",
                xbmc.LOGWARNING,
            )

    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Filemoon extraction failed: {e}",
            xbmc.LOGERROR,
        )

    return None


def play_source(url, title=None):
    resolved_url = resolve_url_wrapper(url)
    if resolved_url:
        # Force HTTPS for ok.ru/vk.com CDN URLs
        if "http://" in resolved_url and (
            "vkuser.net" in resolved_url
            or "okcdn.ru" in resolved_url
            or "mycdn.me" in resolved_url
        ):
            resolved_url = resolved_url.replace("http://", "https://")
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Forced HTTPS: {resolved_url[:150]}...",
                xbmc.LOGINFO,
            )

        # Add headers for ok.ru, vk.com and their CDN URLs
        # Check for both source domains and CDN domains
        requires_headers = (
            "ok.ru" in url  # Original URL domain
            or "ok.ru" in resolved_url  # Resolved URL domain
            or "vk.com" in url
            or "vk.com" in resolved_url
            or "vkvideo.ru" in url
            or "vkvideo.ru" in resolved_url
            or "vkuser.net" in resolved_url  # CDN domains
            or "vkuservideo.net" in resolved_url
            or "okcdn.ru" in resolved_url  # ok.ru CDN
            or "mycdn.me" in resolved_url  # ok.ru CDN
        )

        if requires_headers:
            # Append headers to URL for Kodi
            # Use proper header format for Kodi
            ua = urllib.parse.quote(HEADERS["User-Agent"])
            ref = urllib.parse.quote("https://ok.ru/")
            origin = "https://ok.ru"
            # Add Accept-Encoding to handle gzip responses
            headers = f"User-Agent={ua}&Referer={ref}&Origin={origin}&Accept=*/*&Connection=keep-alive&Accept-Encoding=gzip,deflate"
            resolved_url = f"{resolved_url}|{headers}"
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Playing URL with headers: {resolved_url[:300]}...",
                xbmc.LOGINFO,
            )
        else:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Playing URL: {resolved_url[:200]}...",
                xbmc.LOGINFO,
            )

        list_item = xbmcgui.ListItem(path=resolved_url)
        if title:
            list_item.setInfo("video", {"title": title})
            # Communicate title to service.py via window property
            xbmcgui.Window(10000).setProperty("VeziAici_Title", title)
        else:
            xbmcgui.Window(10000).clearProperty("VeziAici_Title")

        xbmcplugin.setResolvedUrl(HANDLE, True, list_item)
    else:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo("name"), "Could not resolve video URL.")


def list_search_results(url):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch search results: {e}"
        )
        return

    for item in soup.select("div.rb-p20-gutter.rb-col-m12.rb-col-t4"):
        title_element = item.select_one("h3.entry-title a.p-url")
        if title_element:
            title = title_element.get("title")
            item_url = title_element.get("href")

            show_icon = ADDON.getAddonInfo("icon")
            for keyword, image_url in CUSTOM_IMAGES.items():
                if keyword in title.lower():
                    show_icon = image_url
                    break

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": show_icon, "icon": show_icon})

            # We assume search results lead directly to sources
            url_params = {"mode": "list_sources", "url": item_url, "name": title}
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )

    # Handle pagination
    next_page_link = soup.select_one("a.page-numbers")
    if next_page_link:
        next_page_url = next_page_link.get("href")
        if next_page_url:
            list_item = xbmcgui.ListItem("Next Page >>")
            url_params = {"mode": "list_search_results", "url": next_page_url}
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )

    xbmcplugin.endOfDirectory(HANDLE)


def search(query=None):
    if not query:
        keyboard = xbmcgui.Dialog().input("Cauta", type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    search_url = BASE_URL + "?s=" + urllib.parse.quote_plus(query)
    list_search_results(search_url)


def list_latest(url, name=""):
    all_items = []
    current_url = url
    page_count = 0

    while current_url and page_count < 3:
        try:
            response = _get_html_content(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException:
            break

        for title_element in soup.find_all(["h3", "h2"], class_="entry-title"):
            if title_element.find("a"):
                link_element = title_element.find("a")
                item_url = link_element.get("href")
                title = link_element.text.strip()

                show_icon = ADDON.getAddonInfo("icon")
                for keyword, image_url in CUSTOM_IMAGES.items():
                    if keyword in title.lower():
                        show_icon = image_url
                        break

                if item_url and title:
                    all_items.append(
                        {"title": title, "url": item_url, "thumbnail": show_icon}
                    )

        next_page_link = soup.find("a", class_="next page-numbers")
        if next_page_link and next_page_link.has_attr("href"):
            current_url = next_page_link["href"]
        else:
            current_url = None

        page_count += 1

    for item in all_items:
        list_item = xbmcgui.ListItem(item["title"])
        list_item.setArt({"thumb": item["thumbnail"], "icon": item["thumbnail"]})
        list_item.setInfo("video", {"title": item["title"]})
        url_params = {"mode": "list_sources", "url": item["url"]}
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    if current_url:
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {"mode": "list_latest", "url": current_url, "name": name}
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_series(url, mode, page="1"):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch Turkish series: {e}"
        )
        return

    # Parse episodes from article elements - new terasacucartii.net format
    default_icon = ADDON.getAddonInfo("icon")

    for article in soup.find_all("article", class_="item-list"):
        # Find the title link
        title_link = article.find("h2", class_="post-box-title")
        if not title_link:
            title_link = article.find("a", class_="post-box-title")

        if title_link:
            link = title_link.find("a") or title_link
            if link and "href" in link.attrs:
                episode_url = link["href"]
                title = link.get_text(strip=True)

                # Find thumbnail - use default if not available
                thumb_link = article.find("div", class_="post-thumbnail")
                thumb = default_icon
                if thumb_link:
                    img = thumb_link.find("img")
                    if img and "src" in img.attrs:
                        # Use a try-except would be ideal, but we'll set default as fallback
                        thumb = img["src"]

                list_item = xbmcgui.ListItem(title)
                list_item.setArt({"thumb": thumb, "icon": thumb})
                list_item.setInfo("video", {"title": title})
                url_params = {
                    "mode": "list_turkish_sources",
                    "url": episode_url,
                    "name": title,
                }
                xbmcplugin.addDirectoryItem(
                    handle=HANDLE,
                    url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                    listitem=list_item,
                    isFolder=True,
                )

    # Handle pagination
    next_page_link = soup.find("a", class_="page")
    if not next_page_link:
        # Try alternative pagination format
        pagination = soup.find("div", class_="pagination")
        if pagination:
            next_page_link = pagination.find("a", class_="page")

    if next_page_link and "href" in next_page_link.attrs:
        next_page_url = next_page_link["href"]
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {"mode": "list_turkish_series", "url": next_page_url, "page": "1"}
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_episodes(url, name):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch episodes for {name}: {e}"
        )
        return
    for article in soup.find_all("article"):
        thumb_link = article.find("a", class_="post-thumbnail")
        if thumb_link:
            episode_url = thumb_link["href"]
            img = thumb_link.find("img")
            thumb = img["src"] if img and "src" in img.attrs else ""
            title = (
                img["alt"].replace("&#8211;", "-").strip()
                if img and "alt" in img.attrs
                else "Episode"
            )
            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": thumb, "icon": thumb})
            list_item.setInfo("video", {"title": title})
            url_params = {
                "mode": "list_turkish_sources",
                "url": episode_url,
                "name": name,
            }  # Pass name
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )
    # Handle pagination
    next_page_link = soup.find("a", class_="next page-numbers")
    if next_page_link and "href" in next_page_link.attrs:
        next_page_url = next_page_link["href"]
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_turkish_episodes",
            "url": next_page_url,
            "name": name,
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch source page: {e}"
        )
        return

    sources_found = []

    # Method 1: Look for iframes in h1 headers (SURS 1, SURSA 2, etc.)
    h1_headers = soup.find_all("h1")

    for h1 in h1_headers:
        h1_text = h1.get_text()
        if "sursa" in h1_text.lower():
            # Find all iframes after this h1
            next_elem = h1.find_next_sibling()
            while next_elem:
                if next_elem.name == "h1":
                    break
                if next_elem.name == "iframe" and "src" in next_elem.attrs:
                    video_url = next_elem["src"]
                    if video_url.startswith("//"):
                        video_url = "https:" + video_url
                    if video_url and video_url not in sources_found:
                        sources_found.append(video_url)
                elif next_elem.name and next_elem.name not in ["h1", "script", "style"]:
                    iframes = next_elem.find_all("iframe")
                    for iframe in iframes:
                        if "src" in iframe.attrs:
                            video_url = iframe["src"]
                            if video_url.startswith("//"):
                                video_url = "https:" + video_url
                            if video_url and video_url not in sources_found:
                                sources_found.append(video_url)
                next_elem = next_elem.find_next_sibling()

    # Method 2: Find all iframes on the page directly
    if not sources_found:
        all_iframes = soup.find_all("iframe")
        for iframe in all_iframes:
            if "src" in iframe.attrs:
                video_url = iframe["src"]
                if video_url.startswith("//"):
                    video_url = "https:" + video_url
                # Filter out unwanted sources
                if video_url and "player3.funny-cats.org" not in video_url:
                    if video_url not in sources_found:
                        sources_found.append(video_url)

    # Method 3: Look for data-encoded iframes
    if not sources_found:
        iframe_placeholders = soup.find_all("div", class_="iframe-placeholder")
        for placeholder in iframe_placeholders:
            if "data-encoded" in placeholder.attrs:
                encoded_iframe = placeholder["data-encoded"]
                try:
                    decoded_iframe = base64.b64decode(encoded_iframe).decode("utf-8")
                    src_match = re.search(r'src="([^"]+)"', decoded_iframe)
                    if src_match:
                        video_url = src_match.group(1)
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url
                        if video_url and video_url not in sources_found:
                            sources_found.append(video_url)
                except:
                    continue

    # Method 4: Look for videoembed URLs
    if not sources_found:
        videoembed_links = soup.find_all("a", href=lambda x: x and "videoembed" in x)
        for link in videoembed_links:
            video_url = link.get("href")
            if video_url and video_url not in sources_found:
                sources_found.append(video_url)

    if not sources_found:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo("name"), "No playable source found.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Add sources to list - filter out unsupported sources
    unsupported_domains = ["vidmoly", "filemoon", "streamtape", "doodstream"]

    for idx, video_url in enumerate(sources_found):
        domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")

        # Skip unsupported sources
        if any(unsupported in domain.lower() for unsupported in unsupported_domains):
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Skipping unsupported source: {domain}",
                xbmc.LOGDEBUG,
            )
            continue

        list_item = xbmcgui.ListItem(f"Sursa {idx + 1}: {domain}")
        list_item.setInfo("video", {"title": f"Sursa {idx + 1}: {domain}"})
        list_item.setProperty("IsPlayable", "true")

        url_params = {
            "mode": "play_source",
            "url": video_url,
            "title": name,
        }

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=False,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_series_categories():
    icon = "https://kdrama.ro/wp-content/uploads/2023/06/image7-1016x1024.jpg"

    # "Dupa Ani" item
    list_item = xbmcgui.ListItem("Dupa Ani")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {"mode": "list_korean_series_years"}
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # "Seriale Coreene de Familie" item
    list_item = xbmcgui.ListItem("Seriale Coreene de Familie")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/seriale-coreene-de-familie-50-ep/",
        "name": "Seriale Coreene de Familie",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # "Seriale Coreene Contemporane" item
    list_item = xbmcgui.ListItem("Seriale Coreene Contemporane")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/seriale-coreene-contemporane/",
        "name": "Seriale Coreene Contemporane",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # "Seriale Coreene Istorice" item
    list_item = xbmcgui.ListItem("Seriale Coreene Istorice")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/seriale-coreene-istorice/",
        "name": "Seriale Coreene Istorice",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # "Mini-Seriale Coreene" item
    list_item = xbmcgui.ListItem("Mini-Seriale Coreene")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_korean_series",
        "url": "https://blogul-lui-atanase.ro/categorie/miniseriale-coreene/",
        "name": "Mini-Seriale Coreene",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_series_years():
    try:
        response = _get_html_content("https://blogul-lui-atanase.ro/")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch Korean series categories: {e}"
        )
        return

    menu_item = soup.find("li", id="menu-item-15749")
    if menu_item:
        sub_menu = menu_item.find("ul", class_="sub-menu")
        if sub_menu:
            for item in sub_menu.find_all("li"):
                link = item.find("a")
                if link and link.has_attr("href"):
                    title = link.text.strip()
                    url = link["href"]
                    list_item = xbmcgui.ListItem(title)
                    url_params = {
                        "mode": "list_korean_series",
                        "url": url,
                        "name": title,
                    }
                    xbmcplugin.addDirectoryItem(
                        handle=HANDLE,
                        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                        listitem=list_item,
                        isFolder=True,
                    )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_series(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch Korean series for {name}: {e}"
        )
        return

    # Determine the container items
    items = soup.find_all("div", class_="post-col")
    if not items:
        items = soup.find_all("article")

    for item in items:
        title_h2 = None
        thumb_figure = None  # For new layout
        thumb_div = None  # For old layout
        description_div = None

        # Check for New Layout specific element (MagazineNP)
        if item.find("figure", class_="post-featured-image"):
            title_h2 = item.find("h2", class_="entry-title")
            thumb_figure = item.find("figure", class_="post-featured-image")
            description_div = item.find("div", class_="entry-content")
        else:
            # Try old structure
            title_h2 = item.find("h2", class_="post-title")
            thumb_div = item.find("div", class_="post-thumb")
            description_div = item.find("div", class_="entry-content")

            # Try new structure (ColorMag) if old not found
            if not title_h2:
                title_h2 = item.find("h2", class_="cm-entry-title")
            if not thumb_div:
                thumb_div = item.find("div", class_="cm-featured-image")
            if not description_div:
                description_div = item.find("div", class_="cm-entry-summary")

        if title_h2:
            title_link = title_h2.find("a")
            if title_link:
                series_url = title_link["href"]
                # Use text if title attribute is missing
                title = title_link.get("title", title_link.text.strip())

                thumb = ""
                # Handle Image Extraction
                if thumb_figure:  # New Layout
                    a_thumb = thumb_figure.find("a", class_="mnp-post-image")
                    if a_thumb and "style" in a_thumb.attrs:
                        style = a_thumb["style"]
                        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                        if match:
                            thumb = match.group(1)
                elif thumb_div:  # Old Layouts
                    thumb_img = thumb_div.find("img")
                    if thumb_img:
                        thumb = thumb_img.get("data-src", thumb_img.get("src", ""))

                description = description_div.text.strip() if description_div else ""

                list_item = xbmcgui.ListItem(title)
                list_item.setArt({"thumb": thumb, "icon": thumb})
                list_item.setInfo("video", {"title": title, "plot": description})
                url_params = {
                    "mode": "list_korean_episodes_and_sources",
                    "url": series_url,
                    "name": title,
                }  # Pass name
                xbmcplugin.addDirectoryItem(
                    handle=HANDLE,
                    url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                    listitem=list_item,
                    isFolder=True,
                )

    # Pagination - try both methods
    next_page_link = None

    # Old pagination
    pagination = soup.find("div", id="post-navigator")
    if pagination:
        current_page_span = pagination.find("span", class_="current")
        if current_page_span:
            next_page_link = current_page_span.find_next_sibling("a")

    # New/Generic pagination (WordPress default)
    if not next_page_link:
        next_page_link = soup.find("a", class_="next page-numbers")

    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_korean_series",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_movies(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch movies for {name}: {e}"
        )
        return

    # Determine the container items
    items = soup.find_all("div", class_="post-col")
    if not items:
        items = soup.find_all("article")

    for item in items:
        title_h2 = None
        thumb_figure = None  # For new layout
        thumb_div = None  # For old layout
        description_div = None

        # Check for New Layout specific element (MagazineNP)
        if item.find("figure", class_="post-featured-image"):
            title_h2 = item.find("h2", class_="entry-title")
            thumb_figure = item.find("figure", class_="post-featured-image")
            description_div = item.find("div", class_="entry-content")
        else:
            # Try old structure
            title_h2 = item.find("h2", class_="post-title")
            thumb_div = item.find("div", class_="post-thumb")
            description_div = item.find("div", class_="entry-content")

            # Try new structure (ColorMag) if old not found
            if not title_h2:
                title_h2 = item.find("h2", class_="cm-entry-title")
            if not thumb_div:
                thumb_div = item.find("div", class_="cm-featured-image")
            if not description_div:
                description_div = item.find("div", class_="cm-entry-summary")

        if title_h2:
            title_link = title_h2.find("a")
            if title_link:
                series_url = title_link["href"]
                # Use text if title attribute is missing
                title = title_link.get("title", title_link.text.strip())

                thumb = ""
                # Handle Image Extraction
                if thumb_figure:  # New Layout
                    a_thumb = thumb_figure.find("a", class_="mnp-post-image")
                    if a_thumb and "style" in a_thumb.attrs:
                        style = a_thumb["style"]
                        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                        if match:
                            thumb = match.group(1)
                elif thumb_div:  # Old Layouts
                    thumb_img = thumb_div.find("img")
                    if thumb_img:
                        thumb = thumb_img.get("data-src", thumb_img.get("src", ""))

                description = description_div.text.strip() if description_div else ""

                is_series = False
                keywords = ["serial", "sezon", "episod", "episoade"]
                if any(keyword in title.lower() for keyword in keywords) or any(
                    keyword in description.lower() for keyword in keywords
                ):
                    is_series = True

                list_item = xbmcgui.ListItem(title)
                list_item.setArt({"thumb": thumb, "icon": thumb})
                list_item.setInfo("video", {"title": title, "plot": description})

                if is_series:
                    url_params = {
                        "mode": "list_series_episodes",
                        "url": series_url,
                        "name": title,
                    }
                else:
                    url_params = {
                        "mode": "list_movie_sources",
                        "url": series_url,
                        "name": title,
                    }  # Pass name

                xbmcplugin.addDirectoryItem(
                    handle=HANDLE,
                    url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                    listitem=list_item,
                    isFolder=True,
                )

    # Pagination - try both methods
    next_page_link = None

    # Old pagination
    pagination = soup.find("div", id="post-navigator")
    if pagination:
        current_page_span = pagination.find("span", class_="current")
        if current_page_span:
            next_page_link = current_page_span.find_next_sibling("a")

    # New/Generic pagination (WordPress default)
    if not next_page_link:
        next_page_link = soup.find("a", class_="next page-numbers")

    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_movies",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_movie_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch source page: {e}"
        )
        return

    sources_found = False

    # Find sources in <a> tags
    for a_tag in soup.find_all("a", href=True):
        video_url = a_tag["href"]
        if video_url.startswith("//"):
            video_url = "https:" + video_url
        if (
            "netu.ac" in video_url
            or "vidmoly.me" in video_url
            or "waaw.ac" in video_url
            or "streamtape.com" in video_url
            or "ok.ru" in video_url
            or "waaw.to" in video_url
            or "uqload.cx" in video_url
            or "vk.com" in video_url
            or "sibnet.ru" in video_url
            or "my.mail.ru" in video_url
        ):
            domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")
            list_item = xbmcgui.ListItem(f"Sursa: {domain}")
            list_item.setInfo("video", {"title": f"Sursa: {domain}"})
            list_item.setProperty("IsPlayable", "true")

            # Pass title
            url_params = {"mode": "play_source", "url": video_url, "title": name}

            context_menu_items = [
                (
                    "Download",
                    f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})",
                )
            ]
            list_item.addContextMenuItems(context_menu_items)
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=False,
            )
            sources_found = True

    # Find sources in <iframe> tags
    iframes = soup.find_all("iframe")
    for iframe in iframes:
        if iframe.has_attr("src"):
            video_url = iframe["src"]
            if video_url.startswith("//"):
                video_url = "https:" + video_url

            domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")

            list_item = xbmcgui.ListItem(f"Sursa: {domain}")
            list_item.setInfo("video", {"title": f"Sursa: {domain}"})
            list_item.setProperty("IsPlayable", "true")

            # Pass title
            url_params = {"mode": "play_source", "url": video_url, "title": name}

            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=False,
            )
            sources_found = True

    if not sources_found:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), "No sources found on this page."
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_series_episodes(url, name):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch episodes for {name}: {e}"
        )
        return

    content = soup.find("div", class_="entry-content")
    if not content:
        return

    all_elements = content.find_all(["h3", "p"])
    for element in all_elements:
        element_text = element.text.strip()
        if "episodul" in element_text.lower() or "episod" in element_text.lower():
            episode_title = element_text

            # Look for source links in the same element (for Korean-style formatting)
            source_links = element.find_all("a", href=True)
            if source_links:
                for source_link in source_links:
                    source_url = source_link["href"]
                    source_name = source_link.text.strip()
                    if (
                        source_name
                        and "episodul" not in source_name.lower()
                        and "episod" not in source_name.lower()
                    ):
                        display_title = f"{episode_title} - {source_name}"
                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty("IsPlayable", "true")
                        list_item.setInfo("video", {"title": display_title})

                        # Use Name + Episode Title for player title so Trakt can parse it
                        full_player_title = f"{name} - {episode_title}"
                        url_params = {
                            "mode": "play_source",
                            "url": source_url,
                            "title": full_player_title,
                        }

                        context_menu_items = [
                            (
                                "Download",
                                f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})",
                            )
                        ]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(
                            handle=HANDLE,
                            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                            listitem=list_item,
                            isFolder=False,
                        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_episodes_and_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch episode page: {e}"
        )
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("div", class_="cm-entry-summary")
    if not content:
        content = soup.find("article")

    if not content:
        xbmcgui.Dialog().notification(
            ADDON.getAddonInfo("name"),
            "Nu s-a gasit continutul paginii.",
            xbmcgui.NOTIFICATION_ERROR,
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Check for season headers (h2, h3 or h4)
    season_headers = content.find_all(
        ["h2", "h3", "h4"], string=re.compile(r"SEZONUL", re.IGNORECASE)
    )

    if season_headers:
        for i, header in enumerate(season_headers):
            season_title = header.text.strip()
            # Pass the entire content and the start element index to the next function
            url_params = {
                "mode": "list_korean_season_episodes",
                "url": url,  # Pass the page URL
                "season_title": season_title,
                "name": name,  # Pass show name
            }
            list_item = xbmcgui.ListItem(season_title)
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Original logic for pages without seasons or if no season headers were found
    # Try to detect if the page contains direct episode links (e.g., EP.1 VK)
    direct_episode_links_found = False
    all_links = content.find_all("a", href=True)
    for link in all_links:
        link_text = link.text.strip()
        if re.search(r"ep(?:isodul|\.|\s*)?\s*\d+", link_text, re.IGNORECASE):
            direct_episode_links_found = True
            break

    if direct_episode_links_found:
        # Process pages with direct episode links (e.g., "EP.1 VK")
        for link in all_links:
            link_text = link.text.strip()
            if re.search(r"ep(?:isodul|\.|\s*)?\s*\d+", link_text, re.IGNORECASE):
                source_url = link["href"]
                display_title = link_text

                list_item = xbmcgui.ListItem(display_title)
                list_item.setProperty("IsPlayable", "true")
                list_item.setInfo("video", {"title": display_title})

                # Use Show Name + Episode Title
                full_player_title = f"{name} - {display_title}"
                url_params = {
                    "mode": "play_source",
                    "url": source_url,
                    "title": full_player_title,
                }

                context_menu_items = [
                    (
                        "Download",
                        f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})",
                    )
                ]
                list_item.addContextMenuItems(context_menu_items)
                xbmcplugin.addDirectoryItem(
                    handle=HANDLE,
                    url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                    listitem=list_item,
                    isFolder=False,
                )
    else:
        # Universal logic using descendants to handle all structures (nested or sibling)
        current_episode_title = ""

        # Iterate through all descendants to find titles and sources in order
        for node in content.descendants:
            if node.name == "iframe":
                iframe = node
                if current_episode_title:
                    video_url = iframe.get("src")
                    if not video_url or video_url == "about:blank":
                        video_url = iframe.get("data-src")
                    if not video_url or video_url == "about:blank":
                        video_url = iframe.get("data-lazy-src")

                    if video_url and video_url != "about:blank":
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url

                        domain = urllib.parse.urlparse(video_url).netloc.replace(
                            "www.", ""
                        )
                        display_title = f"{current_episode_title} - {domain}"
                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty("IsPlayable", "true")
                        list_item.setInfo("video", {"title": display_title})

                        full_player_title = f"{name} - {current_episode_title}"
                        url_params = {
                            "mode": "play_source",
                            "url": video_url,
                            "title": full_player_title,
                        }

                        context_menu_items = [
                            (
                                "Download",
                                f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})",
                            )
                        ]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(
                            handle=HANDLE,
                            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                            listitem=list_item,
                            isFolder=False,
                        )

            elif node.name == "a" and current_episode_title:
                # Handle <a> tags as sources
                source_url = node.get("href")
                if source_url:
                    source_name = node.text.strip()
                    if (
                        not source_name
                        or "episodul" in source_name.lower()
                        or "episod" in source_name.lower()
                    ):
                        # This might be a link acting as a title, not a source
                        pass
                    else:
                        display_title = f"{current_episode_title} - {source_name}"
                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty("IsPlayable", "true")
                        list_item.setInfo("video", {"title": display_title})

                        full_player_title = f"{name} - {current_episode_title}"
                        url_params = {
                            "mode": "play_source",
                            "url": source_url,
                            "title": full_player_title,
                        }

                        context_menu_items = [
                            (
                                "Download",
                                f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})",
                            )
                        ]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(
                            handle=HANDLE,
                            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                            listitem=list_item,
                            isFolder=False,
                        )

            elif isinstance(node, str):  # NavigableString
                text_val = node.strip()
                if text_val and (
                    "episodul" in text_val.lower() or "episod" in text_val.lower()
                ):
                    # Check for episode title in text nodes
                    # Use basic heuristics to ensure it's a title and not a long sentence
                    if len(text_val) < 50:
                        parts = re.split(r"–|-", text_val)
                        if parts:
                            current_episode_title = parts[0].strip()

    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_season_episodes(url, season_title, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch episode page: {e}"
        )
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("div", class_="cm-entry-summary")
    if not content:
        content = soup.find("article")

    if not content:
        xbmcgui.Dialog().notification(
            ADDON.getAddonInfo("name"),
            "Nu s-a gasit continutul paginii.",
            xbmcgui.NOTIFICATION_ERROR,
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    start_element = content.find(
        ["h2", "h3", "h4"], string=re.compile(season_title, re.IGNORECASE)
    )
    if not start_element:
        return

    current_episode_title = ""

    # Try to detect if the season content contains direct episode links (e.g., EP.1 VK)
    direct_episode_links_found_in_season = False
    season_links = start_element.find_next_siblings("a", href=True)
    for element in start_element.find_next_siblings():
        if element.name in ["h2", "h3", "h4"] and "SEZONUL" in element.text.upper():
            break
        if element.name in ["p", "h3"]:
            for link in element.find_all("a", href=True):
                link_text = link.text.strip()
                if re.search(r"ep(?:isodul|\.|\s*)?\s*\d+", link_text, re.IGNORECASE):
                    direct_episode_links_found_in_season = True
                    break
            if direct_episode_links_found_in_season:
                break

    if direct_episode_links_found_in_season:
        # Process direct episode links within the season
        for element in start_element.find_next_siblings():
            if element.name in ["h2", "h3", "h4"] and "SEZONUL" in element.text.upper():
                break
            if element.name in ["p", "h3"]:
                for link in element.find_all("a", href=True):
                    link_text = link.text.strip()
                    if re.search(
                        r"ep(?:isodul|\.|\s*)?\s*\d+", link_text, re.IGNORECASE
                    ):
                        source_url = link["href"]
                        display_title = link_text

                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty("IsPlayable", "true")
                        list_item.setInfo("video", {"title": display_title})

                        full_player_title = f"{name} - {display_title}"
                        url_params = {
                            "mode": "play_source",
                            "url": source_url,
                            "title": full_player_title,
                        }

                        context_menu_items = [
                            (
                                "Download",
                                f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})",
                            )
                        ]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(
                            handle=HANDLE,
                            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                            listitem=list_item,
                            isFolder=False,
                        )
    else:
        # Universal logic using descendants for season elements
        elements_in_season = []
        for element in start_element.find_next_siblings():
            if element.name in ["h2", "h3", "h4"] and "SEZONUL" in element.text.upper():
                break  # Stop when the next season starts
            elements_in_season.append(element)

        current_episode_title = ""
        for element_container in elements_in_season:
            # iterate descendants of each top-level element in the season block
            for node in element_container.descendants:
                if node.name == "iframe":
                    iframe = node
                    if current_episode_title:
                        video_url = iframe.get("src")
                        if not video_url or video_url == "about:blank":
                            video_url = iframe.get("data-src")
                        if not video_url or video_url == "about:blank":
                            video_url = iframe.get("data-lazy-src")

                        if video_url and video_url != "about:blank":
                            if video_url.startswith("//"):
                                video_url = "https:" + video_url

                            domain = urllib.parse.urlparse(video_url).netloc.replace(
                                "www.", ""
                            )
                            display_title = f"{current_episode_title} - {domain}"
                            list_item = xbmcgui.ListItem(display_title)
                            list_item.setProperty("IsPlayable", "true")
                            list_item.setInfo("video", {"title": display_title})

                            full_player_title = f"{name} - {current_episode_title}"
                            url_params = {
                                "mode": "play_source",
                                "url": video_url,
                                "title": full_player_title,
                            }

                            context_menu_items = [
                                (
                                    "Download",
                                    f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})",
                                )
                            ]
                            list_item.addContextMenuItems(context_menu_items)
                            xbmcplugin.addDirectoryItem(
                                handle=HANDLE,
                                url=sys.argv[0]
                                + "?"
                                + urllib.parse.urlencode(url_params),
                                listitem=list_item,
                                isFolder=False,
                            )

                elif node.name == "a" and current_episode_title:
                    # Handle <a> tags as sources
                    source_url = node.get("href")
                    if source_url:
                        source_name = node.text.strip()
                        if (
                            not source_name
                            or "episodul" in source_name.lower()
                            or "episod" in source_name.lower()
                        ):
                            pass
                        else:
                            display_title = f"{current_episode_title} - {source_name}"
                            list_item = xbmcgui.ListItem(display_title)
                            list_item.setProperty("IsPlayable", "true")
                            list_item.setInfo("video", {"title": display_title})

                            full_player_title = f"{name} - {current_episode_title}"
                            url_params = {
                                "mode": "play_source",
                                "url": source_url,
                                "title": full_player_title,
                            }

                            context_menu_items = [
                                (
                                    "Download",
                                    f"RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})",
                                )
                            ]
                            list_item.addContextMenuItems(context_menu_items)
                            xbmcplugin.addDirectoryItem(
                                handle=HANDLE,
                                url=sys.argv[0]
                                + "?"
                                + urllib.parse.urlencode(url_params),
                                listitem=list_item,
                                isFolder=False,
                            )

                elif isinstance(node, str):  # NavigableString
                    text_val = node.strip()
                    if text_val and (
                        "episodul" in text_val.lower() or "episod" in text_val.lower()
                    ):
                        # Check for episode title in text nodes
                        if len(text_val) < 50:
                            parts = re.split(r"–|-", text_val)
                            if parts:
                                current_episode_title = parts[0].strip()

    xbmcplugin.endOfDirectory(HANDLE)


def list_movies_categories():
    movies_categories = [
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

    for category in movies_categories:
        list_item = xbmcgui.ListItem(category["title"])
        icon = "https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg"
        list_item.setArt({"icon": icon, "thumb": icon})
        url_params = {
            "mode": "list_movies",
            "url": category["url"],
            "name": category["title"],
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_all_series(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch all series for {name}: {e}"
        )
        return

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            series_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": thumb, "icon": thumb})
            list_item.setInfo("video", {"title": title})
            url_params = {
                "mode": "list_serialecoreene_episodes_and_sources",
                "url": series_url,
                "name": title,
            }
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_serialecoreene_all_series",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_all_series(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch all series for {name}: {e}"
        )
        return

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            series_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": thumb, "icon": thumb})
            list_item.setInfo("video", {"title": title})
            url_params = {
                "mode": "list_serialecoreene_episodes_and_sources",
                "url": series_url,
                "name": title,
            }
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_serialecoreene_all_series",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_korean_series(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch Korean series for {name}: {e}"
        )
        return

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            series_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": thumb, "icon": thumb})
            list_item.setInfo("video", {"title": title})
            url_params = {
                "mode": "list_serialecoreene_episodes_and_sources",
                "url": series_url,
                "name": title,
            }
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_serialecoreene_korean_series",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_thai_series(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch Thai series for {name}: {e}"
        )
        return

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            series_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": thumb, "icon": thumb})
            list_item.setInfo("video", {"title": title})
            url_params = {
                "mode": "list_serialecoreene_episodes_and_sources",
                "url": series_url,
                "name": title,
            }
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=True,
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_serialecoreene_thai_series",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_new_episodes(url, name, page="1"):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch new episodes for {name}: {e}"
        )
        return

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            series_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({"thumb": thumb, "icon": thumb})
            list_item.setInfo("video", {"title": title})
            list_item.setProperty("IsPlayable", "true")  # Mark as playable
            url_params = {
                "mode": "play_serialecoreene_episode",
                "url": series_url,
                "name": title,
            }
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=False,
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem("Next Page >>")
        url_params = {
            "mode": "list_serialecoreene_new_episodes",
            "url": url,
            "name": name,
            "page": str(next_page_num),
        }
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
            listitem=list_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_episodes_and_sources(url):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Failed to fetch episode page: {e}"
        )
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    seasons_container = soup.find("div", id="seasons")
    if not seasons_container:
        xbmcgui.Dialog().notification(
            ADDON.getAddonInfo("name"),
            "Nu s-au gasit sezoane pentru acest serial.",
            xbmcgui.NOTIFICATION_ERROR,
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Assuming each .tvseason contains a season and its episodes
    for season_div in seasons_container.find_all("div", class_="tvseason"):
        season_title_element = season_div.find("strong")
        if not season_title_element:
            continue
        season_title = season_title_element.text.strip()

        # Iterate through episode links within the current season
        for episode_link in season_div.find_all("a", href=True):
            episode_url = episode_link["href"]
            episode_name = episode_link.text.strip()

            display_title = f"{season_title} - {episode_name}"

            list_item = xbmcgui.ListItem(display_title)
            list_item.setInfo("video", {"title": display_title})
            list_item.setProperty(
                "IsPlayable", "true"
            )  # Mark as playable, actual playback happens in play_serialecoreene_episode
            url_params = {
                "mode": "play_serialecoreene_episode",
                "url": episode_url,
                "name": display_title,
            }
            xbmcplugin.addDirectoryItem(
                handle=HANDLE,
                url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                listitem=list_item,
                isFolder=False,
            )

    xbmcplugin.endOfDirectory(HANDLE)


def list_serialecoreene_main():
    base_url = "https://serialecoreene.org/"
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"

    # Toate Seriale
    list_item = xbmcgui.ListItem("Toate Seriale")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_serialecoreene_all_series",
        "url": base_url + "series/",
        "name": "Toate Seriale",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Seriale Coreene
    list_item = xbmcgui.ListItem("Seriale Coreene")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_serialecoreene_korean_series",
        "url": base_url + "genre/seriale-coreene/",
        "name": "Seriale Coreene",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Seriale Thailandeze
    list_item = xbmcgui.ListItem("Seriale Thailandeze")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_serialecoreene_thai_series",
        "url": base_url + "genre/thailanda/",
        "name": "Seriale Thailandeze",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    # Episoade Noi
    list_item = xbmcgui.ListItem("Episoade Noi")
    list_item.setArt({"icon": icon, "thumb": icon})
    url_params = {
        "mode": "list_serialecoreene_new_episodes",
        "url": base_url + "episode/",
        "name": "Episoade Noi",
    }
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
        listitem=list_item,
        isFolder=True,
    )

    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_series_categories():
    # Fetch the main page to get categories from select dropdown
    base_url = "https://terasacucartii.net"

    try:
        response = _get_html_content(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the select dropdown with categories
        select = soup.find("select", {"id": "cat"})

        if select:
            for option in select.find_all("option"):
                value = option.get("value")
                label = option.get_text(strip=True)

                if value and value != "-1" and label:
                    # Build category URL
                    category_url = f"{base_url}/?cat={value}"

                    list_item = xbmcgui.ListItem(label)
                    list_item.setArt(
                        {
                            "icon": ADDON.getAddonInfo("icon"),
                            "thumb": ADDON.getAddonInfo("icon"),
                        }
                    )
                    url_params = {
                        "mode": "list_turkish_series",
                        "url": category_url,
                    }
                    xbmcplugin.addDirectoryItem(
                        handle=HANDLE,
                        url=sys.argv[0] + "?" + urllib.parse.urlencode(url_params),
                        listitem=list_item,
                        isFolder=True,
                    )
        else:
            # Fallback: add manual links if select not found
            xbmcgui.Dialog().notification(
                ADDON.getAddonInfo("name"),
                "Categories not found, using fallback",
                xbmcgui.NOTIFICATION_WARNING,
            )

    except Exception as e:
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Error fetching categories: {e}",
            xbmc.LOGERROR,
        )

    xbmcplugin.endOfDirectory(HANDLE)


def _extract_js_redirect_param(html_content, func_name):
    # Search for the function definition with flexible whitespace
    func_pattern = rf'function\s+{re.escape(func_name)}\s*\(\)\s*\{{\s*window\.location\.href\s*=\s*"([^"]+)"\s*;\s*\}}'
    match = re.search(func_pattern, html_content)
    if match:
        return match.group(1)
    return None


def play_serialecoreene_episode(url, name):
    xbmc.log(
        f"[{ADDON.getAddonInfo('name')}] Starting play_serialecoreene_episode for: {url}",
        xbmc.LOGINFO,
    )
    try:
        # Step 1: Fetch the episode page
        response1 = _get_html_content(url)
        response1.raise_for_status()
        soup1 = BeautifulSoup(response1.text, "html.parser")

        # Find the href from #iframeload
        iframe_load_link = soup1.find("a", id="iframeload")
        if not iframe_load_link or "href" not in iframe_load_link.attrs:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] iframeload link not found",
                xbmc.LOGERROR,
            )
            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"), "Nu s-a gasit link-ul iframeload."
            )
            return
        target_div_id = iframe_load_link["href"].lstrip("#")  # e.g., srv1
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Target div ID: {target_div_id}",
            xbmc.LOGINFO,
        )

        # Find the div with the target ID
        target_div = soup1.find("div", id=target_div_id)
        if not target_div:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Target div not found", xbmc.LOGERROR
            )
            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"), "Nu s-a gasit div-ul sursei."
            )
            return

        # Extract onclick function from #buttonx
        button_x = target_div.find("a", id="buttonx")
        if not button_x or "onclick" not in button_x.attrs:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] buttonx not found or no onclick",
                xbmc.LOGERROR,
            )
            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"), "Nu s-a gasit butonul de redare."
            )
            return
        onclick_func = button_x["onclick"].replace("()", "")  # e.g., redirectPage2
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Onclick function: {onclick_func}",
            xbmc.LOGINFO,
        )

        # Extract the redirect parameter from the script
        redirect_param1 = _extract_js_redirect_param(response1.text, onclick_func)
        if not redirect_param1:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Failed to extract redirect param 1. Func: {onclick_func}",
                xbmc.LOGERROR,
            )
            # Log a snippet of the HTML around the expected function for debugging
            # regex search for function name to see what it looks like
            partial_match = re.search(
                rf"function\s+{re.escape(onclick_func)}", response1.text
            )
            if partial_match:
                start = partial_match.start()
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Snippet: {response1.text[start : start + 100]}",
                    xbmc.LOGINFO,
                )
            else:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Function definition not found in HTML",
                    xbmc.LOGINFO,
                )

            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"),
                "Nu s-a putut extrage primul parametru de redirect.",
            )
            return

        # Construct the first redirect URL
        first_redirect_url = urllib.parse.urljoin(url, redirect_param1)
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] First redirect URL: {first_redirect_url}",
            xbmc.LOGINFO,
        )

        # Step 2: Fetch the first redirect page
        response2 = _get_html_content(first_redirect_url)
        response2.raise_for_status()
        soup2 = BeautifulSoup(response2.text, "html.parser")

        # Find the onclick for the second redirect (rdrtnow)
        # The button is often injected via JavaScript, so soup.find might fail.
        # We search for the pattern in the raw text.
        # Looking for: onclick="funcName()" potentially escaped
        rdrtnow_match = re.search(
            r'onclick=\\?["\']([a-zA-Z0-9_]+)\(\)\\?["\']', response2.text
        )

        if not rdrtnow_match:
            # Fallback: try to find the button if it IS in the DOM
            rdrtnow_button = soup2.find("button", onclick=re.compile(r".+"))
            if rdrtnow_button:
                rdrtnow_func = rdrtnow_button["onclick"].replace("()", "")
            else:
                xbmc.log(
                    f"[{ADDON.getAddonInfo('name')}] Second redirect button/function not found in HTML or JS",
                    xbmc.LOGERROR,
                )
                xbmcgui.Dialog().ok(
                    ADDON.getAddonInfo("name"),
                    "Nu s-a gasit butonul de accesare acum (step 2).",
                )
                return
        else:
            rdrtnow_func = rdrtnow_match.group(1)

        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] rdrtnow function: {rdrtnow_func}",
            xbmc.LOGINFO,
        )

        # Extract the second redirect parameter
        redirect_param2 = _extract_js_redirect_param(response2.text, rdrtnow_func)
        if not redirect_param2:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Failed to extract redirect param 2. Func: {rdrtnow_func}",
                xbmc.LOGERROR,
            )
            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"),
                "Nu s-a putut extrage al doilea parametru de redirect.",
            )
            return

        # Construct the second redirect URL
        final_page_url = urllib.parse.urljoin(url, redirect_param2)
        xbmc.log(
            f"[{ADDON.getAddonInfo('name')}] Final page URL: {final_page_url}",
            xbmc.LOGINFO,
        )

        # Step 3: Fetch the final page and find the iframe src
        response3 = _get_html_content(final_page_url)
        response3.raise_for_status()
        soup3 = BeautifulSoup(response3.text, "html.parser")

        final_iframe = soup3.find("iframe", src=True)
        if not final_iframe or "src" not in final_iframe.attrs:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Final iframe not found", xbmc.LOGERROR
            )
            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"), "Nu s-a gasit sursa finala de redare."
            )
            return

        video_url = final_iframe["src"]
        if video_url.startswith("//"):
            video_url = "https:" + video_url

        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Video URL: {video_url}", xbmc.LOGINFO)

        # Step 4: Resolve and play the video
        resolved_url = resolve_url_wrapper(video_url)
        if resolved_url:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Resolved URL: {resolved_url}",
                xbmc.LOGINFO,
            )
            list_item = xbmcgui.ListItem(path=resolved_url)
            list_item.setInfo("video", {"title": name})

            # Communicate title to service
            xbmcgui.Window(10000).setProperty("VeziAici_Title", name)

            xbmcplugin.setResolvedUrl(HANDLE, True, list_item)
        else:
            xbmc.log(
                f"[{ADDON.getAddonInfo('name')}] Could not resolve URL", xbmc.LOGERROR
            )
            xbmcgui.Dialog().ok(
                ADDON.getAddonInfo("name"), "Could not resolve video URL."
            )

    except requests.exceptions.RequestException as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Request Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"Eroare la preluarea paginii: {e}"
        )
    except Exception as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Unexpected Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), f"A aparut o eroare neasteptata: {e}"
        )


def download_source(url):
    resolved_url = resolve_url_wrapper(url)
    if resolved_url:
        # The most reliable way to handle downloads in Kodi for external URLs
        # is to use the Download builtin with the resolved URL
        xbmc.executebuiltin(f'Download("{resolved_url}")')
    else:
        xbmcgui.Dialog().ok(
            ADDON.getAddonInfo("name"), "Could not resolve video URL for download."
        )


def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring))
    mode = params.get("mode")
    name = params.get("name")
    url = params.get("url")
    title = params.get("title")  # Extract title for play_source
    shows = params.get("shows")
    episodes = params.get("episodes")
    season = params.get("season")
    latest_url = params.get("latest_url")
    page = params.get("page", "1")
    season_title = params.get("season_title")

    if mode is None:
        list_main_menu()
    elif mode == "list_show_categories":
        list_show_categories(shows, name, latest_url)
    elif mode == "list_latest":
        list_latest(url, name)
    elif mode == "list_episodes":
        list_episodes(url, name)
    elif mode == "list_episodes_for_season":
        list_episodes_for_season(episodes, season, name)
    elif mode == "list_search_results":
        list_search_results(url)
    elif mode == "list_sources":
        list_sources(url, name)  # Pass name here
    elif mode == "play_source":
        play_source(url, title)  # Pass title here
    elif mode == "search":
        search()
    elif mode == "list_turkish_series_categories":
        list_turkish_series_categories()
    elif mode == "list_turkish_series":
        list_turkish_series(url, mode, page)
    elif mode == "list_turkish_sources":
        list_turkish_sources(url, name)
    elif mode == "list_korean_series_categories":
        list_korean_series_categories()
    elif mode == "list_korean_series_years":
        list_korean_series_years()
    elif mode == "list_korean_series":
        list_korean_series(url, name, page)
    elif mode == "list_korean_episodes_and_sources":
        list_korean_episodes_and_sources(url, name)  # Pass name
    elif mode == "list_korean_season_episodes":
        list_korean_season_episodes(url, season_title, name)  # Pass name too
    elif mode == "list_movies_categories":
        list_movies_categories()
    elif mode == "list_serialecoreene_main":
        list_serialecoreene_main()
    elif mode == "list_serialecoreene_all_series":
        list_serialecoreene_all_series(url, name, page)
    elif mode == "list_serialecoreene_korean_series":
        list_serialecoreene_korean_series(url, name, page)
    elif mode == "list_serialecoreene_thai_series":
        list_serialecoreene_thai_series(url, name, page)
    elif mode == "list_serialecoreene_new_episodes":
        list_serialecoreene_new_episodes(url, name, page)
    elif mode == "list_serialecoreene_episodes_and_sources":
        list_serialecoreene_episodes_and_sources(url)
    elif mode == "list_movies":
        list_movies(url, name, page)
    elif mode == "list_movie_sources":
        list_movie_sources(url, name)  # Pass name
    elif mode == "list_series_episodes":
        list_series_episodes(url, name)
    elif mode == "play_serialecoreene_episode":
        play_serialecoreene_episode(url, name)
    elif mode == "download_source":
        download_source(url)
    elif mode == "authorize_trakt":
        TraktAPI().authorize()
    elif mode == "revoke_trakt":
        TraktAPI().revoke_auth()


if __name__ == "__main__":
    router(sys.argv[2][1:])
