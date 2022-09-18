from ..plugin import Plugin
import xbmcgui, xbmcaddon
import json

try:
    from resources.lib.util.common import *
except ImportError:
    from .resources.lib.util.common import *
from urllib.parse import urlparse
addon_id = xbmcaddon.Addon().getAddonInfo('id')
default_icon = xbmcaddon.Addon(addon_id).getAddonInfo('icon')
default_fanart = xbmcaddon.Addon(addon_id).getAddonInfo('fanart')

class pre_player(Plugin):
    name = "process lists of links"
    priority = 200    
      
    def pre_play(self, item):
        item = json.loads(item)
        link = item["link"]
        play_link= '' 
        do_log(f'{self.name} - processing Item = \n {str(item)} ' )  
        if isinstance(link,list) :
            do_log(f'{self.name} - start link = \n {str(link)} ' )             
            if len(link) > 1:
                labels = []
                counter = 1
                for x in link:
                    host = urlparse(x).netloc
                    if x.strip().endswith(')'):
                        label = x.split('(')[-1].replace(')', '') + ' | ' + '[I]{}[/I]'.format(host)
                    elif x.lower() == 'search':
                        label = 'Search Using Microjen Scrapers'
                    else:
                        label = 'Link ' + str(counter) + ' | ' + '[I]{}[/I]'.format(host)
                    labels.append(label)
                    counter += 1
                dialog = xbmcgui.Dialog()
                ret = dialog.select('Choose a Link', labels)
                if ret == -1:
                    return
                else:
                    if link[ret].strip().endswith(')'):
                        link = link[ret].rsplit('(')[0].strip()     
                        play_link= link                           
                    else:
                        link = link[ret]
                        play_link= link
            else:
                if link[0].strip().endswith(')'):
                    link = link[0].rsplit('(')[0].strip()  
                    play_link= link
                else:
                    link = link[0]
                    play_link= link
        else:
            link = item["link"]
            play_link= link
        
        item["link"]=play_link
        do_log(f'{self.name} - final link = \n {str(link)} ' )  
        return json.dumps(item) 
                
                
                
            
