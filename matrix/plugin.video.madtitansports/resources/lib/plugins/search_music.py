from ..util.dialogs import link_dialog
from ..plugin import Plugin
from ..DI import DI
import requests, xbmcgui, json, xbmc
from bs4 import BeautifulSoup
from resources.lib.plugin import run_hook
from resources.lib import k
import urllib
from concurrent.futures import ThreadPoolExecutor, as_completed

class SearchJSON(Plugin):
    name = "search_music"
    priority = 100
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'

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

    def routes(self, plugin):
        @plugin.route(f"/{self.name}/<path:dir>")
        def directory(dir):
            jen_list = []
            dir = urllib.parse.unquote_plus(dir)
            query = plugin.args["query"][0] if "query" in plugin.args else None
            if query == None or query == "*":
                query = xbmcgui.Dialog().input("Search").lower()
                if query == "": return
            dialog = plugin.args["dialog"][0] == "true" if "dialog" in plugin.args else False

            # Check if URL ends with .json
            if dir.lower().endswith(('.json', '.enc')):
                # Single JSON file handling
                try:
                    response = requests.get(dir)
                    if response.status_code == 200:
                        if response.content[0] == 0x40:
                            items = json.loads(k.dfzxujsdfzio(response.content).decode("utf-8"))["items"]
                        else:
                            items = response.json()["items"]
                        xbmc.log(str(items), xbmc.LOGINFO)
                        jen_list = list(filter(lambda x: query in x.get("title", x.get("name", "")).lower(), items))
                except:
                    xbmc.log(f"Failed to fetch or parse JSON from {dir}", level=xbmc.LOGERROR)
            else:
                # Directory handling - fetch all JSON files
                if not dir.endswith('/'): dir += '/'
                try:
                    # Get directory listing using requests
                    response = requests.get(dir)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # Find all links that end with .json
                        json_files = [dir + link.get('href') for link in soup.find_all('a')
                                   if link.get('href', '').lower().endswith(('.json', '.enc'))]
                        
                        def process_json_file(json_file):
                            try:
                                response = requests.get(json_file)
                                if response.status_code == 200:
                                    if response.content[0] == 0x40:
                                        items = json.loads(k.dfzxujsdfzio(response.content).decode("utf-8"))["items"]
                                    else:
                                        items = response.json()["items"]
                                    return list(filter(lambda x: query in x.get("title", x.get("name", "")).lower(), items))
                            except:
                                xbmc.log(f"Failed to fetch or parse JSON from {json_file}", level=xbmc.LOGERROR)
                            return []

                        # Process JSON files in parallel using ThreadPoolExecutor
                        with ThreadPoolExecutor(max_workers=10) as executor:
                            future_to_url = {executor.submit(process_json_file, url): url for url in json_files}
                            for future in as_completed(future_to_url):
                                matched_items = future.result()
                                if matched_items:
                                    jen_list.extend(matched_items)
                except:
                    xbmc.log(f"Failed to fetch directory listing from {dir}", level=xbmc.LOGERROR)

            if dialog:
                if not jen_list:
                    xbmcgui.Dialog().notification("Search", "No results found", xbmcgui.NOTIFICATION_INFO)
                    return True
                idx = link_dialog([res["title"] for res in jen_list], return_idx=True, hide_links=False)
                if idx == None:
                    return True
                item = jen_list[idx]
                if isinstance(item.get("link", ""), list):
                    idx = link_dialog([res for res in item["link"]], return_idx=True, hide_links=True)
                    if idx == None:
                        return True
                    item["link"] = item["link"][idx]
                run_hook("play_video", json.dumps(item))
            else:
                jen_list = [run_hook("process_item", item) for item in jen_list]
                jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
                run_hook("display_list", jen_list)



    # {
    #         "type": "dir",
    #         "title": "JSON Search test",
    #         "search_music": "*",
    #         "link": "https://website/jet/newchannels.json"
    #     },

    # {
    #         "type": "dir",
    #         "title": "Search Jet Music Videos",
    #         "search_music": "*",
    #         "link": "https://magnetic.website/MAD_TITAN_SPORTS/RADIO/Music101/"
    #     },
            