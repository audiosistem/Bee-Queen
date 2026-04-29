from ..plugin import Plugin
import xml.etree.ElementTree as ET
import xbmcgui, requests, datetime, time, xbmc
from resources.lib.plugin import run_hook
from unidecode import unidecode


class locast(Plugin):
    name = "locast"
    priority = 100
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'

    def process_item(self, item):
        if self.name in item:
            link = item.get(self.name, "")
            if link.startswith("channels"):
                split = link.split("|")
                if len(split) == 2: item["link"] = f"locast/{split[1]}"
                else: item["link"] = f"locast/{split[1]}|{split[2]}"
                item["is_dir"] = True
                item["list_item"] = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
                return item
    
    def routes(self, plugin):
        @plugin.route("/locast/<path:location>")
        def get_channels(location):
            location_split = location.split("|")
            if len(location_split) == 2:
                latitude = location_split[0]
                longitude = location_split[1]
            else:
                r = requests.get(f"https://api.opencagedata.com/geocode/v1/json?q={location_split[0]}&key=641c51bed8ab490184632ad8526e29ad&no_annotations=1&language=en", headers={"User-Agent": self.user_agent}).json()
                latitude = r["results"][0]["geometry"]["lat"]
                longitude = r["results"][0]["geometry"]["lng"]
            ts = time.time()
            utc_offset = (datetime.datetime.fromtimestamp(ts) - datetime.datetime.utcfromtimestamp(ts)).total_seconds() / 3600
            date = datetime.datetime.now()
            dma = requests.get(f"https://api.locastnet.org/api/watch/dma/{latitude}/{longitude}").json()
            epg = requests.get(f"https://api.locastnet.org/api/watch/epg/{dma['DMA']}?startTime={date.strftime('%Y-%m-%dT%H:00:00')}{'-' if utc_offset < 0 else '+'}{date.replace(hour=abs(int(utc_offset//1)), minute=int((utc_offset % 1) * 60)).strftime('%H:%M')}&hours=6").json()
            jen_list = []
            
            for channel in epg:
                name = f'[COLORred]{channel["callSign"]}[/COLOR] | {channel["name"]}'
                icon = channel["logoUrl"]
                guidedata = []
                for listing in channel["listings"]:
                    listing_img = listing["preferredImage"]
                    guidedata.append({
                        'url': "",
                        'fanart': listing_img,
                        'mediatype': 'show',
                        'genre': listing["genres"].split(", ") if "genres" in listing else [],
                        'starttime': listing["startTime"] // 1000,
                        'duration': listing["duration"], 
                        'label': listing["title"].replace('"', "").replace("'", ""), 
                        'label2': 'HD',
                        'channelname': name, 
                        'art': {
                            'thumb': listing_img,
                            'fanart': listing_img, 
                            'poster': '', 
                            'logo': '', 
                            'clearart': '',
                            'icon': listing_img
                        } 
                    })
                jen_data = {
                    "title": name,
                    "thumbnail": icon,
                    "fanart": icon,
                    "sportjetextractors": [f"https://api.locastnet.org/api/watch/station/{channel['id']}/{latitude}/{longitude}"],
                    "guidedata": guidedata,
                    "type": "item"
                }
                jen_list.append(jen_data)

            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)
            