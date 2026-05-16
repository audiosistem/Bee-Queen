from resources.lib.plugin import Plugin
from resources.lib.plugin import run_hook
import requests, xbmcgui

class xtream(Plugin):
    name = "xtream"
    priority = 100
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"

    def process_item(self, item):
        if self.name in item:
            link = item.get(self.name, "")
            address = link["address"]
            username = link["username"]
            password = link["password"]
            action = link["action"]
            item["link"] = f"{self.name}/{action}/{address}?username={username}&password={password}"
            if "cat" in link:
                item["link"] += "&cat=" + link["cat"]
            item["is_dir"] = action in ["category", "categories"]
            list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
            item["list_item"] = list_item
            return item
    
    def routes(self, plugin):
        @plugin.route(f"/{self.name}/categories/<path:url>")
        def categories(url):
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
                    "link": f"{url}/live/{username}/{password}/{channel_id}.m3u8",
                    "type": "item"
                })
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
