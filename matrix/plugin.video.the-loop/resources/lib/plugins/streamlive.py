from ..plugin import Plugin
from ..DI import DI
from resources.lib.plugin import run_hook
import json, requests, xbmcgui, xbmcvfs, xbmcaddon, os

PATH = xbmcaddon.Addon().getAddonInfo("path")

class streamlive(Plugin):
    name = "Streamlive"
    priority = 100
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'

    def process_item(self, item):
        if "streamlive" in item:
            link = item.get("streamlive", "")
            if link == "channels":
                item["link"] = "streamlive/channels"
                item["is_dir"] = True
                item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")))
                return item

    def routes(self, plugin):
        @plugin.route("/streamlive/channels")
        def get_channels():
            jen_list = []
            channels = json.loads(xbmcvfs.File(os.path.join(PATH, "xml", "LIVETV", "streamlive.json")).read())
            for channel in channels:
                channel_name = next(iter(channel))
                channel_id = next(iter(channel.items()))[1]
                jen_list.append({
                    "type": "item",
                    "title": channel_name,
                    "sportjetextractors": f"https://streamlive.to/channel-player?n={channel_id}"
                })
            
            jen_list = list(sorted(jen_list, key=lambda x: x["title"]))
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
