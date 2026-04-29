
import json
import os
import requests
from ..util.dialogs import link_dialog, remove_name
from ..plugin import Plugin
import xbmcgui
from resources.lib.plugin import run_hook
from resources.lib import k
from xbmcvfs import translatePath
import xbmcaddon
from datetime import datetime, timezone
import urllib
import xbmc

class SearchJSON(Plugin):
    name = "search_json"
    priority = 100
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'


    def get_cache_path(self) -> str:
        user_path = translatePath(xbmcaddon.Addon().getAddonInfo("profile")) or "."
        config_path = os.path.join(user_path, f"{self.name}_cache.json")
        return config_path

    def process_item(self, item):
        if self.name in item:
            query = item.get(self.name, "*")
            thumbnail = item.get("thumbnail", "")
            fanart = item.get("fanart", "")
            dialog = query.startswith("dialog:")
            if dialog:
                query = query.replace("dialog:", "")
                
            item["link"] = f"{self.name}/{item.get('link')}?query={query}&dialog={str(dialog).lower()}"
            item["is_dir"] = not dialog
            item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
            item["list_item"].setArt({"thumb": thumbnail, "fanart": fanart})
            
            return item

    def save_to_cache(self, query, jen_list):
        cache_path = self.get_cache_path()
        if not os.path.exists(cache_path):
            cache = []
        else:
            with open(cache_path, "r+") as f:
                cache = json.load(f)
        entry = {
            "query": query,
            "time": int(datetime.now(timezone.utc).timestamp()),
            "items": jen_list
        }
        cache.insert(0, entry)
        if len(cache) > 10:
            cache.pop()
        with open(cache_path, "w") as f:
            json.dump(cache, f)

    def routes(self, plugin):
        @plugin.route(f"/{self.name}/<path:dir>")
        def directory(dir):
            jen_list = []
            dir = urllib.parse.unquote_plus(dir)
            query = plugin.args["query"][0] if "query" in plugin.args else None
            if query is None or query == "*":
                query = xbmcgui.Dialog().input("Search").lower()
                if query == "":
                    return
            dialog = plugin.args["dialog"][0] == "true" if "dialog" in plugin.args else False

            r = requests.get(dir)
            if r.content[0] == 0x40:
                items = json.loads(k.dfzxujsdfzio(r.content).decode("utf-8"))["items"]
            else:
                items = r.json()["items"]
            
            jen_list = list(filter(lambda x: query in x.get("title", x.get("name", "")).lower(), items))
            if dialog:
                idx = link_dialog([res["title"] for res in jen_list], return_idx=True, hide_links=False)
                if idx is None:
                    return True
                item = jen_list[idx]
                if isinstance(item.get("link", ""), list):
                    idx = link_dialog([res for res in item["link"]], return_idx=True, hide_links=True)
                    if idx is None:
                        return True
                    item["link"] = remove_name(item["link"][idx])
                # For special items (like file_iptv entries) we need to let
                # their plugins (file_iptv, tele_iptv) transform the item
                # into a playable route. For all other items, keep the
                # legacy behavior and send the raw JSON item directly to
                # play_video so existing links (sportjetextractors, etc.)
                # keep working.
                if any(k in item for k in ("file_iptv", "tele_iptv", "iptv_s")):
                    item = run_hook("process_item", item)
                    item = run_hook("get_metadata", item, return_item_on_failure=True)

                    # Strip out non-JSON-serializable fields (like ListItem)
                    # before sending to play_video, which expects a pure
                    # JSON representation.
                    if isinstance(item, dict) and "list_item" in item:
                        item = dict(item)  # shallow copy
                        item.pop("list_item", None)

                run_hook("play_video", json.dumps(item))
            else:
                jen_list = [run_hook("process_item", item) for item in jen_list]
                jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
                run_hook("display_list", jen_list)

        @plugin.route(f"/{self.name}/cache")
        def cache():
            cache_path = self.get_cache_path()
            jen_list = []
            if os.path.exists(cache_path):
                with open(cache_path, "r") as f:
                    items = json.load(f)
                for i, item in enumerate(items):
                    jen_list.append({
                        "title": f"Query:[COLORred] {item['query'].upper()}[/COLOR] [COLORyellow]  ({len(item['items'])} links)[/COLOR]\nTime: {datetime.fromtimestamp(item['time']).strftime('%m/%d %I:%M %p')}",
                        "type": "dir",
                        self.name: f"cache/{i}"
                    })
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)

        @plugin.route(f"/{self.name}/cache/<entry>")
        def cache_entry(entry):
            entry = int(entry)
            cache_path = self.get_cache_path()
            with open(cache_path, "r") as f:
                items = json.load(f)
            jen_list = items[entry]["items"]
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)

        @plugin.route(f"/{self.name}/clear")
        def clear():
            addon = xbmcaddon.Addon()
            USER_DATA_DIR = translatePath(addon.getAddonInfo("profile"))
            if os.path.exists(os.path.join(USER_DATA_DIR, f"{self.name}_cache.json")):
                os.remove(os.path.join(USER_DATA_DIR, f"{self.name}_cache.json"))
            xbmcgui.Dialog().ok("Clear", "You are now [COLORred]clearing[/COLOR] your previous searches.")
            