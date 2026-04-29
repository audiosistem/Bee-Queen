from ..plugin import Plugin
import xbmc, xbmcgui, xbmcaddon
import json
import resolveurl

try:
    from resources.lib.util.common import *
except ImportError:
    from .resources.lib.util.common import *

addon_id = xbmcaddon.Addon().getAddonInfo('id')
default_icon = xbmcaddon.Addon(addon_id).getAddonInfo('icon')
default_fanart = xbmcaddon.Addon(addon_id).getAddonInfo('fanart')
# addon_id = xbmcaddon.Addon().getAddonInfo('id')
# default_icon = xbmcaddon.Addon(addon_id).getAddonInfo('icon')


class default_play_video(Plugin):
    name = "default video playback"
    priority = 0

    def play_video(self, item):
        item = json.loads(item)
        if "link" not in item: return False
        link = item["link"]        
        title = item["title"]
        
        my_id = item.get("id", "empty")
        
        if my_id == "empty" :                         
            thumbnail = item.get("thumbnail", default_icon)
            fanart = item.get("fanart", default_fanart)                                       
        else :     
            my_thumb, my_art = use_artID(item, int(my_id)) 
            # do_log(f'{self.name} - data returned = \n Thumb = {str(my_thumb)} \n Art = {str(my_art)} ' )  
            if my_thumb.startswith('http') : thumbnail = my_thumb
            else : thumbnail = item.get("thumbnail", default_icon) 
            if my_art.startswith('http') : fanart = my_art   
            else : fanart = item.get("fanart", default_fanart  )                
                      
        # thumbnail = item.get("thumbnail", default_icon)
        liz = xbmcgui.ListItem(title)
        liz.setInfo('video', {'Title': title})
        liz.setArt({'thumb': thumbnail, 'icon': thumbnail})
        
        if resolveurl.HostedMediaFile(link).valid_url():
        	url = resolveurl.HostedMediaFile(link).resolve()
        	return xbmc.Player().play(url,liz)
        else:
        	return xbmc.Player().play(link,liz)
       
    
    def play_video_old(self, item):
        item = json.loads(item)
        link = item.get("link", "")
        if link == "":
            return False
        title = item["title"]
        thumbnail = item.get("thumbnail", default_icon)
        summary = item.get("summary", "")
        liz = xbmcgui.ListItem(title)
        liz.setInfo("video", {"title": title, "plot": summary})
        liz.setArt({"thumb": thumbnail, "icon": thumbnail, "poster": thumbnail})
        if resolveurl.HostedMediaFile(link).valid_url():
            url = resolveurl.HostedMediaFile(link).resolve()
            return xbmc.Player().play(url,liz)
        return xbmc.Player().play(link,liz)