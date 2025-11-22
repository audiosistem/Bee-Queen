import xbmc
import xbmcvfs
import xbmcaddon
from horoscope import get_horoscope, INDEX, BASE_URL

get_setting = xbmcaddon.Addon().getSetting
addon_data = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))

def startup():
    if not get_setting('startup') == 'true':
        return
        
    name = ''
    name2 = ''
    url = ''
    url2 = ''
    
    xbmc.sleep(3000)
    sign = int(get_setting('name'))
    sign2 = int(get_setting('name2'))
    if not sign: return
    if sign:
        names = [_name for _name in INDEX.keys()]
        selected = sign
        name = names[selected] 
        url = f'{BASE_URL}{INDEX[name][0]}'
    if sign2:
        names = [_name for _name in INDEX.keys()]
        selected = sign2
        name2 = names[selected] 
        url2 = f'{BASE_URL}{INDEX[name2][0]}'
        
    get_horoscope(name, url, startup = True, name2=name2, url2=url2)

if __name__ == '__main__':
    if not xbmcvfs.exists(addon_data):
        xbmcvfs.mkdirs(addon_data)
    startup()