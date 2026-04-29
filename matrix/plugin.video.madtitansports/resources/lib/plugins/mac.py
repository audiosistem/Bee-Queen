from resources.lib.plugin import Plugin
from resources.lib.plugin import run_hook
import requests, xbmcgui, xbmcaddon, os, math, xbmc, json
from xbmcvfs import translatePath
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import typing

class Server:
    host: str
    mac: str
    username: str
    password: str
    session: requests.Session
    genre_filters: typing.Dict[str, typing.List[str]]
    category_filters: typing.Dict[str, typing.List[str]]

    def __init__(self, host: str, mac: str, username: str = None, password: str = None) -> None:
        self.host = host
        self.mac = mac
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0"
        self.session.headers["Cookie"] = f"mac={mac}; stb_lang=en; timezone=America/Los_Angeles"

    def init(self):
        token = self.api_request("handshake")["token"]
        self.session.headers["Authorization"] = "Bearer " + token
        profile = self.api_request("get_profile")
        del self.session.headers["Authorization"]
        self.username = profile["login"]
        self.password = profile["password"]

    def api_request(self, action: str, type: str = "stb", params={}):
        api_url = self.host + "/c/portal.php"
        login_payload = {"login": self.username, "password": self.password} if self.username != None else None
        r = self.session.request("POST", api_url, params={"type": type, "action": action, "JsHttpRequest": "1-xml", **params}, json=login_payload if type == "itv" else None)
        if len(r.text) != 0:
            return r.json()["js"]
        else:
            return {}

class mac(Plugin):
    name = "mac"
    priority = 100
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"

    def process_item(self, item):
        if self.name in item:
            link = item.get(self.name, "")
            action = link["action"]
            if action in ["input", "previous", "clear"]:
                item["link"] = f"{self.name}/{action}"
            else:
                address = link["address"]
                mac = link["mac"]
                if "username" in link:
                    username = link["username"]
                    password = link["password"]
                    item["link"] = f"{self.name}/{action}/{address}?mac={mac}&username={username}&password={password}"
                else:
                    item["link"] = f"{self.name}/{action}/{address}?mac={mac}"
                if "genre" in link:
                    item["link"] += f"&genre=" + link["genre"]
                if "page" in link:
                    item["link"] += f"&page=" + str(link["page"])
                if "link" in link:
                    item["link"] += f"&link=" + link["link"]
                if "title" in link:
                    item["link"] += f"&title=" + link["title"]
            item["is_dir"] = action in ["genre", "genres", "input", "previous"]
            list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
            item["list_item"] = list_item
            return item
    
    def routes(self, plugin):
        @plugin.route(f"/{self.name}/input")
        def dialog_input():
            host = xbmcgui.Dialog().input("Enter host (ex. http://example.com:25461)")
            if not host: return
            mac = xbmcgui.Dialog().input("Enter MAC address")
            if not mac: return

            try:
                server = Server(host, mac)
                server.init()
                username = server.username
                password = server.password
                link = f"{host};;;{mac}\n"
            except:
                dialog = xbmcgui.Dialog()
                dialog.ok("Error", f"Failed to get username and password.\nAddress: {host}\nMAC: {mac}")
                return

            addon = xbmcaddon.Addon()
            USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
            if not os.path.exists(USER_DATA_DIR):
                os.makedirs(USER_DATA_DIR)
            exists = False
            if os.path.exists(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt")):
                with open(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt"), "r") as f:
                    lines = f.readlines()
                    if link in lines:
                        exists = True
            if not exists:
                with open(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt"), "a+") as f:
                    f.write(link)

            genres(host, mac, username, password)
        
        @plugin.route(f"/{self.name}/previous")
        def previous():
            addon = xbmcaddon.Addon()
            USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
            if not os.path.exists(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt")):
                return xbmcgui.Dialog().ok("Error", "No previous Mac links have been entered.")
            with open(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt"), "r") as f:
                lines = f.readlines()
            links = []
            for line in lines:
                line_split = line.split(";;;")
                links.append(f"{line_split[0]}, {line_split[1]}")
            res = xbmcgui.Dialog().select("Previous links", links)
            if res != None and res >= 0:
                line_split = lines[res].strip().split(";;;")
                genres(line_split[0], line_split[1])
        
        @plugin.route(f"/{self.name}/clear")
        def clear():
            addon = xbmcaddon.Addon()
            USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
            if os.path.exists(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt")):
                os.remove(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt"))
            xbmcgui.Dialog().ok("Clear", "Previous Mac links have been cleared.")
            
        @plugin.route(f"/{self.name}/genres/<path:url>")
        def genres(url, mac=None, username=None, password=None):
            server = None
            if mac == None:
                mac = plugin.args["mac"][0]
            if username == None or password == None:
                if "username" in plugin.args:
                    username = plugin.args["username"][0]
                    password = plugin.args["password"][0]
                else:
                    server = Server(url, mac, username, password)
                    server.init()
                    username = server.username
                    password = server.password
            if server is None:
                server = Server(url, mac, username, password)
            genres = server.api_request("get_genres", "itv")
            jen_list = []
            for genre in genres:
                jen_list.append({
                    "title": f"{genre['id']} | {genre['title']}",
                    self.name: {
                        "address": url,
                        "mac": mac,
                        "username": username,
                        "password": password,
                        "action": "genre",
                        "genre": genre["id"],
                    },
                    "type": "dir"
                })
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
        
        @plugin.route(f"/{self.name}/genre/<path:url>")
        def genre(url):
            mac = plugin.args["mac"][0]
            username = "" if "username" not in plugin.args else plugin.args["username"][0]
            password = "" if "password" not in plugin.args else plugin.args["password"][0]
            genre = plugin.args["genre"][0]
            page = 1 if "page" not in plugin.args else int(plugin.args["page"][0])

            server = Server(url, mac, username, password)
            genre_listing = server.api_request("get_ordered_list", "itv", {"genre": genre, "p": page})
            jen_list = []
            for item in genre_listing["data"]:
                link = item["cmd"].replace("ffmpeg ", "")
                if "localhost" in item["cmd"]:
                    jen_list.append({
                        "title": item["name"],
                        "icon": item["logo"],
                        self.name: {
                            "address": url,
                            "mac": mac,
                            "username": username,
                            "password": password,
                            "action": "play",
                            "link": link
                        },
                        "type": "item"
                    })
                else:
                    jen_list.append({
                        "title": item["name"],
                        "icon": item["logo"],
                        "link": link.replace("extension=ts", "extension=m3u8"),
                        "type": "item"
                    })
            pages = math.ceil(genre_listing["total_items"] / genre_listing["max_page_items"])
            if page * genre_listing["max_page_items"] < genre_listing["total_items"]:
                jen_list.append({
                    "title": f"Page {page + 1}/{pages}",
                    self.name: {
                        "address": url,
                        "mac": mac,
                        "username": username,
                        "password": password,
                        "action": "genre",
                        "genre": genre,
                        "page": page + 1
                    },
                    "type": "dir"
                })
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)

        @plugin.route(f"/{self.name}/play/<path:url>")
        def play(url):
            mac = plugin.args["mac"][0]
            username = "" if "username" not in plugin.args else plugin.args["username"][0]
            password = "" if "password" not in plugin.args else plugin.args["password"][0]
            link = plugin.args["link"][0]
            title = "MAC" if "title" not in plugin.args else plugin.args["title"][0]

            server = Server(url, mac, username, password)
            link_req = server.api_request("create_link", "itv", {"cmd": link})
            link = link_req["cmd"].replace("ffmpeg ", "").replace("extension=ts", "extension=m3u8")
            liz = xbmcgui.ListItem(title)
            xbmc.Player().play(link, liz)
            return True

