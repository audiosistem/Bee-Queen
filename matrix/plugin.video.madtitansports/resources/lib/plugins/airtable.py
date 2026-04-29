from ..plugin import Plugin
from ..util.dialogs import link_dialog
import xbmc, json, xbmcgui
from resources.lib.external.airtable.airtable import Airtable
from resources.lib.plugin import run_hook
import xml.etree.ElementTree as ET

CACHE_TIME = 0

class airtable(Plugin):
    name = "airtable"

    def process_item(self, item):
        if "jen_airtable" in item:
            table_info = item["jen_airtable"]
            thumbnail = item.get("thumbnail", "")
            fanart = item.get("fanart", "")
            list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")))
            list_item.setArt({"thumb": thumbnail, "fanart": fanart})
            item["list_item"] = list_item
            item["is_dir"] = True
            item["link"] = "airtable/jen/" + table_info
            return item

    def routes(self, plugin):
        @plugin.route("/airtable/jen/<table_info>")
        def airtable_jen(table_info):
            args_split = table_info.split("***")
            table_split = args_split[0].split("|")
            
            table_type = table_split[0]
            table_base = table_split[-3]
            table_id = table_split[-2]
            
            at = Airtable(table_id, table_base, api_key=args_split[1])
            if table_type == "season" or table_type == "show":
                match = at.search('category', table_base + "_" + table_split[-1], view='Grid view')
            elif table_type == "game" or table_type == "show":
                match = at.search('category2', table_base + "_" + table_split[-1], view='Grid view')
            elif table_type == "game2" or table_type == "show":
                match = at.search('category3', table_base + "_" + table_split[-1], view='Grid view')          
            elif table_type == "message":
                match = at.search("name", table_split[-1], view="Grid view")
                fields = match[0]["fields"]
                if "message" in fields:
                    xbmcgui.Dialog().textviewer("Message", fields["message"])
                return
            else:
                match = at.get_all(sort=['name'])
            jen_list = []
            for field in match:
                try:
                    res = field['fields']
                    thumbnail = res.get("thumbnail", "")
                    fanart = res.get("fanart", "")
                    summary = res.get("summary", "")         
                    name = res['name']
                    links = []
                    for key, value in res.items():
                        if key.startswith("link"):
                            link = value
                            if link == "-": continue
                            if "/live/" in link:
                                link = "is_ffmpeg://" + link
                            links.append(link)
                            if link.endswith(".json"): break
                    jen_data = {
                        "title": name,
                        "link": (links if len(links) > 1 else links[0]) if len(links) > 0 else "",
                        "thumbnail": thumbnail,
                        "fanart": fanart,
                        "summary": summary,
                        "type": "dir" if len(links) > 0 and (links[0].endswith(".json") or ("youtube.com" in links[0] and ("playlist" in links[0] or "channel" in links[0]))) else "item"
                    }
                    if len(links) > 0 and links[0].startswith("<"):
                        root = ET.fromstring(links[0])
                        jen_data[root.tag] = root.text
                    
                    jen_list.append(jen_data)
                except Exception as e:
                    continue
            
            if table_type == "game2":
                if len(jen_list) == 0:
                    return
                if type(jen_list[0]["link"]) == list:
                    idx = link_dialog([link for link in jen_list[0]["link"]], return_idx=True, hide_links=True)
                    if idx == None:
                        return True
                    link = jen_list[0]["link"][idx]
                else:
                    link = jen_list[0]["link"]
                if "(" in link and link.endswith(")"):
                    link = link.split("(")[0]
                if link.startswith("plugin://"):
                    xbmc.executebuiltin(f'RunPlugin({link})')
                else:
                    run_hook("play_video", json.dumps({"link": link, "title": table_split[-1]}))
            else:
                jen_list = [run_hook("process_item", item) for item in jen_list]
                jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
                run_hook("display_list", jen_list)