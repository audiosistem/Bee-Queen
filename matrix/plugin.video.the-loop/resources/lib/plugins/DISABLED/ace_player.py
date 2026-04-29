from ..plugin import Plugin
import xbmc, xbmcgui, xbmcaddon, xbmcplugin
import json, sys
# import resolveurl

addon_id = xbmcaddon.Addon().getAddonInfo('id')
default_icon = xbmcaddon.Addon(addon_id).getAddonInfo('icon')
default_fanart = xbmcaddon.Addon(addon_id).getAddonInfo('fanart')


class acestream_play_video(Plugin):
    name = "acestream video playback"
    priority = 110

    def play_video(self, item):
        if not '"link":' in str(item) : return False
        item = json.loads(item)
        link = item["link"]        
        title = item["title"]
        thumbnail = item.get("thumbnail", default_icon)
        liz = xbmcgui.ListItem(title)
        liz.setInfo('video', {'Title': title})
        liz.setArt({'thumb': thumbnail, 'icon': thumbnail})
        if link.startswith("acestream://") :
            
            _id = link.replace("acestream://", "")    
            this_link = f"plugin://script.module.horus/?action=play&id={_id}"           
            # this_link = f"plugin://program.acestreamhandler/play_media?content_id={_id}"
                    
            # going_in = xbmcgui.Dialog().yesno('MicroJen' , f'Play Ace Link \n{this_link}' )
            
            # xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, liz)
            
            xbmc.executebuiltin('RunPlugin({})'.format(this_link))                        
            
            # xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://script.module.horus/?action=play&id={_id}",return)')
            # xbmc.executebuiltin("ActivateWindow(10025, {this_link} , return)")  
            # xbmc.executebuiltin(f'PlayMedia({this_link})')   
            
            return True
        
        
        
        
        
        












# import xbmc
def play_acestream(_id=None, url=None, infohash=None):
    if id is not None:
        return xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://script.module.horus/?action=play&id={_id}",return)')
    elif url is not None:
        return xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://script.module.horus/?action=play&id={_id}",return)')
    elif infohash is not None:
        return xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://script.module.horus/?action=play&id={_id}",return)')
    return None