import json
from resources.lib.plugin import run_hook
from resources.lib.util.dialogs import link_dialog
from ..plugin import Plugin
import xbmcgui, requests
from .mac import Server

class mac_server(Plugin):
    name = "mac_server"
    priority = 100

    def process_item(self, item):
        if self.name in item:
            link = item.get(self.name, "")
            if link.startswith("dialog:"):
                path = "search_dialog"
                item["is_dir"] = False
                link = link.replace("dialog:", "")
            else:
                path = "search"
                item["is_dir"] = True
            if "," in link:
                split = link.split(",")
                item["link"] = f"{self.name}/{path}/{split[0]}?query={split[1]}"
            else:
                item["link"] = f"{self.name}/{path}/{link}"
            item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
            return item

    def search_query(self, country, query=None):
        if query == None:
            query = xbmcgui.Dialog().input("Search query")
            if not query:
                return None
        r = requests.get(f"https://magnetic.website/jet/Mac/{country}.json").json()
        jen_list = []
        for channel in r:
            if query.lower() in channel["name"].lower():
                if "localhost" in channel["link"]:
                    jen_data = {
                        "title": channel["name"],
                        "mac": {
                            "address": channel["server"],
                            "mac": channel["mac"],
                            "username": channel["username"],
                            "password": channel["password"],
                            "action": "play",
                            "link": channel["link"],
                            "title": channel["name"]
                        },
                        "thumbnail": channel["logo"],
                        "fanart": channel["logo"],
                        "summary": channel["server"],
                        "type": "item"
                    }
                else:
                    jen_data = {
                        "title": channel["name"],
                        "link": channel["link"],
                        "thumbnail": channel["logo"],
                        "fanart": channel["logo"],
                        "summary": channel["server"],
                        "type": "item"
                    }
                jen_list.append(jen_data)
        return jen_list
    
    def routes(self, plugin):
        @plugin.route(f"/{self.name}/search/<country>")
        def search(country):
            jen_list = self.search_query(country, plugin.args["query"][0] if "query" in plugin.args else None)
            if not jen_list:
                return
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
        
        @plugin.route(f"/{self.name}/search_dialog/<country>")
        def search_dialog(country):
            jen_list = self.search_query(country, plugin.args["query"][0] if "query" in plugin.args else None)
            if not jen_list:
                return
            idx = link_dialog([res["title"] for res in jen_list], return_idx=True, hide_links=False)
            if idx == None:
                return True
            item = jen_list[idx]
            if "mac" in item:
                item = run_hook("process_item", item)
                mac = item["mac"]
                server = Server(mac["address"], mac["mac"], mac["username"], mac["password"])
                link_req = server.api_request("create_link", "itv", {"cmd": mac["link"]})
                link = link_req["cmd"].replace("ffmpeg ", "").replace("extension=ts", "extension=m3u8")
                item["link"] = link
                del item["list_item"]
            run_hook("play_video", json.dumps(item))
