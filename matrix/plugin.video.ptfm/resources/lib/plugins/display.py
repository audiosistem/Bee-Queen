from ..plugin import Plugin
from xbmcplugin import addDirectoryItems, endOfDirectory, setContent
from ..DI import DI
import sys

route_plugin = DI.plugin


class display(Plugin):
    name = "display"

    def display_list(self, jen_list):
        display_list = []
        for item in jen_list:
            link = item["link"]
            is_dir = item["is_dir"]
            list_item = item["list_item"]
            if is_dir is False:
                list_item.setProperty('IsPlayable', 'true')
            #display_item = (route_plugin.url_for_path(link), list_item, is_dir)
            display_list.append((route_plugin.url_for_path(link), list_item, is_dir))
            
            #addDirectoryItem(route_plugin.handle, display_item, list_item)
        addDirectoryItems(route_plugin.handle, display_list, len(display_list))
        setContent(int(sys.argv[1]), 'videos')
        endOfDirectory(route_plugin.handle)
        return True
