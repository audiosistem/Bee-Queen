from resources.lib.plugin import Plugin
from resources.lib.plugin import run_hook
import requests, xbmcgui, xbmcaddon, os, xbmc
from xbmcvfs import translatePath

class xtream(Plugin):
    name = "xtream"
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
                username = link["username"]
                password = link["password"]
                item["link"] = f"{self.name}/{action}/{address}?username={username}&password={password}"
                if "cat" in link:
                    item["link"] += "&cat=" + link["cat"]
            item["is_dir"] = action in ["category", "categories", "input", "previous"]
            list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
            item["list_item"] = list_item
            return item
    
    def routes(self, plugin):
        @plugin.route(f"/{self.name}/input")
        def dialog_input():
            host = xbmcgui.Dialog().input("Enter host (ex. http://example.com:25461)")
            if not host: return
            username = xbmcgui.Dialog().input("Enter username")
            if not username: return
            password = xbmcgui.Dialog().input("Enter password")
            if not password: return
            link = f"{host};;;{username};;;{password}" + "\n"

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

            categories(host, username, password)
        
        @plugin.route(f"/{self.name}/previous")
        def previous():
            addon = xbmcaddon.Addon()
            USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
            if not os.path.exists(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt")):
                return xbmcgui.Dialog().ok("Error", "No previous Xtream links have been entered.")
            with open(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt"), "r") as f:
                lines = f.readlines()
            links = []
            for line in lines:
                line_split = line.split(";;;")
                links.append(f"{line_split[0]}, {line_split[1]}, {line_split[2]}")
            res = xbmcgui.Dialog().select("Previous links", links)
            if res != None and res >= 0:
                line_split = lines[res].strip().split(";;;")
                categories(line_split[0], line_split[1], line_split[2])
        
        @plugin.route(f"/{self.name}/clear")
        def clear():
            addon = xbmcaddon.Addon()
            USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
            if os.path.exists(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt")):
                os.remove(os.path.join(USER_DATA_DIR, f"{self.name}_previous.txt"))
            xbmcgui.Dialog().ok("Clear", "Previous Xtream links have been cleared.")
            
        @plugin.route(f"/{self.name}/categories/<path:url>")
        def categories(url, username=None, password=None):
            if username == None or password == None:
                username = plugin.args["username"][0]
                password = plugin.args["password"][0]
            r = requests.get(url + f"/panel_api.php?username={username}&password={password}").json()
            jen_list = []
            for key, value in r["categories"].items():
                for cat in value:
                    jen_list.append({
                        "title": f"{key.capitalize()} | {cat['category_name']}",
                        self.name: {
                            "address": url,
                            "username": username,
                            "password": password,
                            "action": "category",
                            "cat": cat["category_id"]
                        },
                        "type": "dir"
                    })
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
        
        @plugin.route(f"/{self.name}/category/<path:url>")
        def category(url):
            username = plugin.args["username"][0]
            password = plugin.args["password"][0]
            category = plugin.args["cat"][0]
            r = requests.get(url + f"/panel_api.php?username={username}&password={password}").json()
            jen_list = []
            for channel_id, channel in r["available_channels"].items():
                if channel["category_id"] != category: continue
                jen_list.append({
                    "title": channel["name"],
                    "icon": channel["stream_icon"],
                    "sportjetextractors": [f"jetproxy://{url}/live/{username}/{password}/{channel_id}.m3u8?&Connection=keep-alive|X-Forwarded-For=24.37.42.200"],
                    "type": "item"
                })
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
