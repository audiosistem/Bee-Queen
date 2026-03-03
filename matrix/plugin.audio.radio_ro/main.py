import os
import sys
import json
import random
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import urllib.request
import urllib.parse

# Get the plugin handle
_handle = int(sys.argv[1])
_base_url = sys.argv[0]
_addon = xbmcaddon.Addon()

API_BASE = "https://all.api.radio-browser.info"


def make_api_request(url_path):
    """
    Make API request to radio-browser.info
    """
    url = API_BASE + url_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=15)
        data = response.read()
        response.close()
        return json.loads(data)
    except Exception as e:
        xbmc.log(f"RadioRO API Error: {str(e)}", xbmc.LOGERROR)
        return []


def get_stations(
    offset=0,
    limit=20,
    order="clickcount",
    name=None,
    by_uuid=None,
    tag=None,
    override_country=None,
):
    """
    Fetches the radio station data from the Radio Browser API
    """
    try:
        country_code = (
            override_country if override_country else _addon.getSetting("country_code")
        )

        if by_uuid:
            url_path = f"/json/stations/byuuid/{by_uuid}"
        else:
            reverse = "true" if order == "clickcount" else "false"
            params = {
                "countrycode": country_code,
                "hidebroken": "true",
                "order": order,
                "reverse": reverse,
                "offset": offset,
                "limit": limit,
            }
            if name:
                params["name"] = name
            if tag:
                params["tag"] = tag

            query_string = urllib.parse.urlencode(params)
            url_path = f"/json/stations/search?{query_string}"

        return make_api_request(url_path)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", str(e))
        return []


def list_stations(stations, page=1, action="all"):
    """
    Lists the given stations with enhanced visual quality info
    """
    xbmcplugin.setContent(_handle, "audio")
    default_icon = _addon.getAddonInfo("icon")

    # 4. Set dynamic title for feedback
    title_prefix = "Radio"
    if "search" in action:
        title_prefix = "Results"
    elif "by_genre" in action:
        title_prefix = "Genre"
    elif "by_city" in action:
        title_prefix = "Local"

    if stations:
        xbmcplugin.setPluginCategory(
            _handle, f"{title_prefix} ({len(stations)} stations found)"
        )

    for station in stations:
        # 2. Enhanced label with dimmed quality info
        label = station["name"]
        quality_info = []
        if station.get("codec"):
            quality_info.append(station["codec"].lower())
        if station.get("bitrate") and station["bitrate"] > 0:
            quality_info.append(f"{station['bitrate']}k")

        if quality_info:
            label = f"{label} [COLOR gray][{' '.join(quality_info)}][/COLOR]"

        list_item = xbmcgui.ListItem(label=label)
        list_item.setInfo(
            "music",
            {
                "title": station["name"],
                "genre": station.get("tags", ""),
                "plot": f"Language: {station.get('language', '')}\nCountry: {station.get('country', '')}\nTags: {station.get('tags', '')}",
                "website": station.get("homepage", ""),
                "album": station.get("country", ""),
                "comment": station.get("language", ""),
                "bitrate": station.get("bitrate", 0),
                "codec": station.get("codec", ""),
            },
        )

        thumb = station.get("favicon")
        if not thumb or not thumb.startswith("http"):
            thumb = default_icon

        list_item.setArt(
            {"thumb": thumb, "icon": thumb, "fanart": _addon.getAddonInfo("fanart")}
        )
        list_item.setProperty("IsPlayable", "true")
        list_item.setProperty("IsLive", "true")
        url = f"{_base_url}?action=play&station_uuid={station['stationuuid']}"
        commands = []
        commands.append(
            (
                "Add to Favorites",
                f"RunPlugin({_base_url}?action=add_favorite&station_uuid={station['stationuuid']})",
            )
        )
        commands.append(
            (
                "Export to Library (.strm)",
                f"RunPlugin({_base_url}?action=export_strm&station_uuid={station['stationuuid']})",
            )
        )
        commands.append(
            (
                "Play Next",
                f"RunPlugin({_base_url}?action=queue&station_uuid={station['stationuuid']}&next=1)",
            )
        )
        commands.append(
            (
                "Add to Queue",
                f"RunPlugin({_base_url}?action=queue&station_uuid={station['stationuuid']}&next=0)",
            )
        )
        list_item.addContextMenuItems(commands)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, isFolder=False)

    # Pagination with colors
    if action != "search" and action != "favorites":
        if len(stations) == 20:
            li_next = xbmcgui.ListItem("[COLOR lightblue]Next Page >>[/COLOR]")
            li_next.setArt({"icon": "DefaultFolder.png", "thumb": "DefaultFolder.png"})
            xbmcplugin.addDirectoryItem(
                _handle,
                _base_url + f"?action={action}&page={page + 1}",
                li_next,
                isFolder=True,
            )
        if page > 1:
            li_prev = xbmcgui.ListItem("[COLOR lightblue]<< Previous Page[/COLOR]")
            li_prev.setArt({"icon": "DefaultFolder.png", "thumb": "DefaultFolder.png"})
            xbmcplugin.addDirectoryItem(
                _handle,
                _base_url + f"?action={action}&page={page - 1}",
                li_prev,
                isFolder=True,
            )

    xbmcplugin.endOfDirectory(_handle)


def list_genres():
    """
    Lists the most popular tags/genres with bold formatting
    """
    try:
        url_path = (
            "/json/tags/?order=stationcount&reverse=true&hidebroken=true&limit=50"
        )
        tags = make_api_request(url_path)

        xbmcplugin.setContent(_handle, "files")
        xbmcplugin.setPluginCategory(_handle, "Browse by Genre")
        for tag in tags:
            tag_name = tag.get("name", "").capitalize()
            if not tag_name:
                continue
            # 3. Bold genres
            list_item = xbmcgui.ListItem(
                label=f"[B]{tag_name}[/B] [COLOR gray]({tag.get('stationcount', 0)})[/COLOR]"
            )
            list_item.setArt(
                {"icon": "DefaultMusicGenres.png", "thumb": "DefaultMusicGenres.png"}
            )
            url_action = f"{_base_url}?action=by_genre&tag={urllib.parse.quote(tag['name'])}&page=1"
            xbmcplugin.addDirectoryItem(_handle, url_action, list_item, isFolder=True)
        xbmcplugin.endOfDirectory(_handle)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", str(e))


def create_menu_item(label, url_action, icon_name):
    li = xbmcgui.ListItem(label)
    li.setArt({"icon": icon_name, "thumb": icon_name})
    xbmcplugin.addDirectoryItem(_handle, _base_url + url_action, li, isFolder=True)


def main_menu():
    """
    Creates the main menu with colors and default icons
    """
    create_menu_item(
        "[COLOR yellow]Search[/COLOR]", "?action=search", "DefaultAddonsSearch.png"
    )

    favorites = get_favorites()
    if len(favorites) > 0:
        create_menu_item(
            "[COLOR gold]Favorites[/COLOR]", "?action=favorites", "DefaultTags.png"
        )

    create_menu_item(
        "[COLOR lightblue]Most Popular[/COLOR]",
        "?action=popular&page=1",
        "DefaultMusicTop100.png",
    )
    create_menu_item(
        "[COLOR white]All Stations[/COLOR]",
        "?action=all&page=1",
        "DefaultMusicSongs.png",
    )
    create_menu_item(
        "[COLOR pink]Genres / Tags[/COLOR]", "?action=genres", "DefaultMusicGenres.png"
    )
    create_menu_item(
        "[COLOR green]Local Radios (RO)[/COLOR]",
        "?action=local_radios",
        "DefaultNetwork.png",
    )
    create_menu_item(
        "[COLOR orange]Change Country[/COLOR]",
        "?action=countries",
        "DefaultCountry.png",
    )
    create_menu_item(
        "[COLOR gray]Settings[/COLOR]", "?action=settings", "DefaultAddonService.png"
    )

    xbmcplugin.endOfDirectory(_handle)


def list_local_radios():
    """
    Lists major Romanian cities for local radios with bold formatting
    """
    cities = [
        "Alba",
        "Arad",
        "Arges",
        "Bacau",
        "Bihor",
        "Bistrita-Nasaud",
        "Botosani",
        "Brasov",
        "Braila",
        "Buzau",
        "Caras-Severin",
        "Calarasi",
        "Cluj",
        "Constanta",
        "Covasna",
        "Dambovita",
        "Dolj",
        "Galati",
        "Giurgiu",
        "Gorj",
        "Harghita",
        "Hunedoara",
        "Ialomita",
        "Iasi",
        "Ilfov",
        "Maramures",
        "Mehedinti",
        "Mures",
        "Neamt",
        "Olt",
        "Prahova",
        "Satu Mare",
        "Salaj",
        "Sibiu",
        "Suceava",
        "Teleorman",
        "Timis",
        "Tulcea",
        "Vaslui",
        "Valcea",
        "Vrancea",
        "Bucuresti",
    ]
    xbmcplugin.setContent(_handle, "files")
    xbmcplugin.setPluginCategory(_handle, "Local Radios by City")
    for city in sorted(cities):
        # 3. Bold cities
        list_item = xbmcgui.ListItem(label=f"[B]{city}[/B]")
        list_item.setArt({"icon": "DefaultNetwork.png", "thumb": "DefaultNetwork.png"})
        url_action = (
            f"{_base_url}?action=by_city&city={urllib.parse.quote(city)}&page=1"
        )
        xbmcplugin.addDirectoryItem(_handle, url_action, list_item, isFolder=True)
    xbmcplugin.endOfDirectory(_handle)


def list_countries():
    """
    Lists countries to choose from
    """
    try:
        url_path = "/json/countries/?order=stationcount&reverse=true&limit=100"
        countries = make_api_request(url_path)

        xbmcplugin.setContent(_handle, "files")
        for country in countries:
            name = country.get("name", "")
            code = country.get("iso_3166_1", "")
            if not name or not code:
                continue

            list_item = xbmcgui.ListItem(
                label=f"{name} ({country.get('stationcount', 0)} stations)"
            )
            list_item.setArt(
                {"icon": "DefaultCountry.png", "thumb": "DefaultCountry.png"}
            )
            url_action = f"{_base_url}?action=set_country&code={urllib.parse.quote(code)}&name={urllib.parse.quote(name)}"
            xbmcplugin.addDirectoryItem(_handle, url_action, list_item, isFolder=False)
        xbmcplugin.endOfDirectory(_handle)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", str(e))


def set_country(code, name):
    """
    Sets the country code in settings
    """
    _addon.setSetting("country_code", code)
    xbmcgui.Dialog().notification("Country Changed", f"Country set to {name}")
    xbmc.executebuiltin("Container.Refresh")


def get_search_history_file():
    profile_dir = xbmcvfs.translatePath(_addon.getAddonInfo("profile"))
    return os.path.join(profile_dir, "search_history.json")


def get_search_history():
    history_file = get_search_history_file()
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []


def add_to_history(query):
    history = get_search_history()
    if query in history:
        history.remove(query)
    history.insert(0, query)
    history = history[:10]  # Keep last 10
    history_file = get_search_history_file()
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)


def search(query=None):
    """
    Searches for a station with history support
    """
    if not query:
        history = get_search_history()
        options = ["-- New Search --"] + history
        if history:
            options.append("-- Clear History --")

        sel = xbmcgui.Dialog().select("Search", options)
        if sel == 0:
            keyboard = xbmc.Keyboard("", "Search for a station")
            keyboard.doModal()
            if keyboard.isConfirmed():
                query = keyboard.getText()
        elif sel > 0 and sel <= len(history):
            query = history[sel - 1]
        elif sel == len(options) - 1 and history:
            try:
                os.remove(get_search_history_file())
            except:
                pass
            return search()
        else:
            return

    if query:
        add_to_history(query)
        stations = get_stations(limit=100, name=query)
        list_stations(stations, action=f"search&query={urllib.parse.quote(query)}")


def get_favorites_file():
    """
    Returns the path to the favorites JSON file
    """
    profile_dir = xbmcvfs.translatePath(_addon.getAddonInfo("profile"))
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    return os.path.join(profile_dir, "favorites.json")


def save_favorites(favorites):
    """
    Saves favorites to the JSON file
    """
    fav_file = get_favorites_file()
    with open(fav_file, "w", encoding="utf-8") as f:
        json.dump(favorites, f, indent=4)


def get_favorites():
    """
    Gets the favorite stations from file or migrates old ones from settings
    """
    fav_file = get_favorites_file()
    if os.path.exists(fav_file):
        try:
            with open(fav_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass

    # Fallback to old settings method and migrate
    favorites_str = _addon.getSetting("favorites")
    if favorites_str:
        try:
            favs = json.loads(favorites_str)
            save_favorites(favs)
            _addon.setSetting("favorites", "")  # Clear to prevent bloat
            return favs
        except:
            pass

    return []


def add_favorite(station_uuid):
    """
    Adds a station to the favorites
    """
    favorites = get_favorites()
    if station_uuid not in [f["stationuuid"] for f in favorites]:
        stations = get_stations(by_uuid=station_uuid)
        if stations and len(stations) > 0:
            station = stations[0]
            favorites.append(station)
            save_favorites(favorites)
            xbmcgui.Dialog().notification(
                "Favorites", f"{station['name']} added to favorites"
            )


def remove_favorite(station_uuid):
    """
    Removes a station from the favorites
    """
    favorites = get_favorites()
    favorites = [f for f in favorites if f["stationuuid"] != station_uuid]
    save_favorites(favorites)
    xbmcgui.Dialog().notification("Favorites", "Station removed from favorites")
    xbmc.executebuiltin("Container.Refresh")


def list_favorites():
    """
    Lists the favorite stations
    """
    favorites = get_favorites()
    xbmcplugin.setContent(_handle, "audio")
    default_icon = _addon.getAddonInfo("icon")

    for station in favorites:
        # Quality info for favorites
        label = station["name"]
        quality_info = []
        if station.get("codec"):
            quality_info.append(station["codec"])
        if station.get("bitrate") and station["bitrate"] > 0:
            quality_info.append(f"{station['bitrate']}kbps")
        if quality_info:
            label = f"{label} [{' '.join(quality_info)}]"

        list_item = xbmcgui.ListItem(label=label)
        list_item.setInfo("music", {"title": station["name"]})

        # Fallback icon for favorites
        thumb = station.get("favicon")
        if not thumb or not thumb.startswith("http"):
            thumb = default_icon

        list_item.setArt(
            {"thumb": thumb, "icon": thumb, "fanart": _addon.getAddonInfo("fanart")}
        )
        list_item.setProperty("IsPlayable", "true")
        list_item.setProperty("IsLive", "true")
        url = f"{_base_url}?action=play&station_uuid={station['stationuuid']}"
        commands = []
        commands.append(
            (
                "Remove from Favorites",
                f"RunPlugin({_base_url}?action=remove_favorite&station_uuid={station['stationuuid']})",
            )
        )
        commands.append(
            (
                "Export to Library (.strm)",
                f"RunPlugin({_base_url}?action=export_strm&station_uuid={station['stationuuid']})",
            )
        )
        commands.append(
            (
                "Play Next",
                f"RunPlugin({_base_url}?action=queue&station_uuid={station['stationuuid']}&next=1)",
            )
        )
        commands.append(
            (
                "Add to Queue",
                f"RunPlugin({_base_url}?action=queue&station_uuid={station['stationuuid']}&next=0)",
            )
        )
        list_item.addContextMenuItems(commands)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, isFolder=False)
    xbmcplugin.endOfDirectory(_handle)


def check_url_alive(url):
    try:
        headers = {"User-Agent": "RadioRO-Kodi-Addon/1.2 (Kodi Media Center)"}
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=5)
        response.close()
        return True
    except:
        return False


def play_station(station_uuid):
    stations = get_stations(by_uuid=station_uuid)
    if stations:
        station = stations[0]
        url = station.get("url_resolved")
        if url:
            if check_url_alive(url):
                li = xbmcgui.ListItem(path=url)
                li.setProperty("IsLive", "true")

                # Smart Metadata Mapping & ICY Prep
                li.setInfo(
                    "music",
                    {
                        "title": "Live Broadcast",
                        "artist": station["name"],
                        "album": station.get("country", "Radio"),
                    },
                )

                # Fullscreen Dynamic Fanart
                thumb = station.get("favicon")
                if not thumb or not thumb.startswith("http"):
                    thumb = _addon.getAddonInfo("icon")

                li.setArt(
                    {
                        "thumb": thumb,
                        "icon": thumb,
                        "fanart": _addon.getAddonInfo("fanart"),
                        "clearart": thumb,
                        "clearlogo": thumb,
                    }
                )

                # Trimite stream-ul catre Kodi
                xbmcplugin.setResolvedUrl(_handle, True, li)

                # Afiseaza notificarea
                xbmcgui.Dialog().notification(
                    "Radio RO", f"Playing: {station['name']}", sound=False
                )

                # Daca optiunea e activa, folosim un AlarmClock nativ pentru a schimba fereastra
                # dupa 2 secunde, oferind timp plugin-ului sa se inchida si sa elibereze interfata
                if _addon.getSetting("auto_fullscreen") == "true":
                    xbmc.executebuiltin(
                        "AlarmClock(AutoFS,ActivateWindow(visualisation),00:02,silent)"
                    )

                return

    xbmcgui.Dialog().notification(
        "Stream Offline",
        "This radio station is currently unreachable.",
        xbmcgui.NOTIFICATION_ERROR,
    )
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())


def export_strm(station_uuid):
    stations = get_stations(by_uuid=station_uuid)
    if stations:
        station = stations[0]
        name = (
            station["name"]
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "")
            .replace("*", "")
            .replace("?", "")
            .replace('"', "")
            .replace("<", "")
            .replace(">", "")
            .replace("|", "")
        )
        profile_dir = xbmcvfs.translatePath(_addon.getAddonInfo("profile"))
        strm_dir = os.path.join(profile_dir, "strm")
        if not os.path.exists(strm_dir):
            os.makedirs(strm_dir)
        strm_path = os.path.join(strm_dir, f"{name}.strm")
        with open(strm_path, "w", encoding="utf-8") as f:
            f.write(station.get("url_resolved", ""))
        xbmcgui.Dialog().notification(
            "Exported", f"Station saved to Addon Data / strm", time=5000
        )


def queue_station(station_uuid, play_next=False):
    stations = get_stations(by_uuid=station_uuid)
    if stations:
        station = stations[0]
        url = f"{_base_url}?action=play&station_uuid={station['stationuuid']}"
        li = xbmcgui.ListItem(label=station["name"])
        li.setInfo("music", {"title": station["name"]})
        li.setArt({"thumb": station.get("favicon", "")})
        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        if play_next:
            pos = playlist.getposition() + 1
            playlist.insert(pos, url, li)
            xbmcgui.Dialog().notification("Queue", "Playing next: " + station["name"])
        else:
            playlist.add(url, li)
            xbmcgui.Dialog().notification("Queue", "Added to queue: " + station["name"])


def router(paramstring):
    """
    Router function
    """
    params = {}
    if len(paramstring) > 1:
        for part in paramstring[1:].split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                params[key] = value

    action = params.get("action")
    page = int(params.get("page", 1))
    offset = (page - 1) * 20

    if action == "all":
        list_stations(
            get_stations(offset=offset, limit=20, order="name"), page=page, action="all"
        )
    elif action == "popular":
        stations = get_stations(offset=offset, limit=20, order="clickcount")
        list_stations(stations, page=page, action="popular")
    elif action == "genres":
        list_genres()
    elif action == "by_genre":
        tag = urllib.parse.unquote(params.get("tag", ""))
        stations = get_stations(offset=offset, limit=20, order="clickcount", tag=tag)
        list_stations(
            stations, page=page, action=f"by_genre&tag={urllib.parse.quote(tag)}"
        )
    elif action == "local_radios":
        list_local_radios()
    elif action == "by_city":
        city = urllib.parse.unquote(params.get("city", ""))
        stations = get_stations(
            offset=offset,
            limit=20,
            order="clickcount",
            name=city,
            override_country="RO",
        )
        list_stations(
            stations, page=page, action=f"by_city&city={urllib.parse.quote(city)}"
        )
    elif action == "countries":
        list_countries()
    elif action == "set_country":
        set_country(
            urllib.parse.unquote(params.get("code", "")),
            urllib.parse.unquote(params.get("name", "")),
        )
    elif action == "search":
        search(params.get("query"))
    elif action == "play":
        play_station(params.get("station_uuid"))
    elif action == "export_strm":
        export_strm(params.get("station_uuid"))
    elif action == "queue":
        queue_station(params.get("station_uuid"), params.get("next") == "1")
    elif action == "favorites":
        list_favorites()
    elif action == "add_favorite":
        add_favorite(params["station_uuid"])
    elif action == "remove_favorite":
        remove_favorite(params["station_uuid"])
    elif action == "settings":
        _addon.openSettings()
    else:
        main_menu()


if __name__ == "__main__":
    router(sys.argv[2])
