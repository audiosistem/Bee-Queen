from ..plugin import Plugin
import xbmc, xbmcgui, xbmcaddon, xbmcplugin
import json, sys
import inputstreamhelper
import requests
import urllib.parse
session = requests.Session()

try:
    from resources.lib.util.common import *
except ImportError:
    from .resources.lib.util.common import *

addon_id = xbmcaddon.Addon().getAddonInfo('id')
default_icon = xbmcaddon.Addon(addon_id).getAddonInfo('icon')
default_fanart = xbmcaddon.Addon(addon_id).getAddonInfo('fanart')

class mpd_play_video(Plugin):
    name = "mpd video playback"
    priority = 100

    def play_video(self, item):
        if not '"link":' in str(item) : return False
        item = json.loads(item)
        link = item["link"]
        title = item["title"]
        thumbnail = item.get("thumbnail", default_icon)
        liz = xbmcgui.ListItem(title)
        liz.setInfo('video', {'Title': title})
        liz.setArt({'thumb': thumbnail, 'icon': thumbnail})   
        
        liz.setProperty('inputstream', 'inputstream.adaptive')      
        liz.setProperty("IsPlayable", "true")                      
        liz.setContentLookup(False)   
        
        mpd_url = '' 
        auto_headers = '' 
        
        # ok_helper = self.mpd_helper('mpd', 'com.widevine.alpha' )   
        # if ok_helper : do_log(f'{self.name} - ok_helper = ' + str(ok_helper))  
        
        if link :            
            if link.startswith("is_hls://"):
                mpd_url = link.replace("is_hls://", "")
                PROTOCOL = 'hls' 
                DRM = '' 
                MIMETYPE = 'application/vnd.apple.mpegurl' 
                
                liz.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)
                liz.setMimeType(MIMETYPE) 
 
            elif link.startswith("is_msready://"):
                mpd_url = link.replace("is_msready://", "")
                PROTOCOL = 'ism' 
                DRM = '' 
                MIMETYPE = 'application/vnd.ms-sstr+xml' 

                liz.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)
                liz.setMimeType(MIMETYPE) 
                
            #### initial version 
            elif link.startswith("is_mpd://"):
                PROTOCOL = 'mpd' 
                DRM = 'com.widevine.alpha' 
                MIMETYPE = 'application/dash+xml'    
                LICENSE_URL = 'https://widevine-proxy.appspot.com/proxy'
                license_key = ''
                # liz.setContentLookup(False)
                
                try : 
                    mpd_split = link.split("===")
                    mpd_url = mpd_split[0].replace("is_mpd://", "")
                    license_key = str(mpd_split[1]) 
                except :
                    mpd_url = link.replace("is_mpd://", "")                                                       
                    license_key = LICENSE_URL
                                        
                if license_key != '':
                    liz.setProperty('inputstream.adaptive.license_key', license_key + '||R{SSM}|') 
                    
                liz.setProperty('inputstream.adaptive.license_type', DRM)                       
                liz.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)     
                liz.setMimeType(MIMETYPE) 
                                                                     
            if mpd_url :     
                liz.setContentLookup(False)
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, liz)
                xbmc.Player().play(mpd_url, listitem=liz)
                return True
    
        else:
        	return False 
        
    def mpd_helper(self, protocol, drm) :
        import inputstreamhelper
        is_helper = inputstreamhelper.Helper(protocol, drm)
        if not is_helper.check_inputstream():     
            return False
        else :  
            return True 
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
       