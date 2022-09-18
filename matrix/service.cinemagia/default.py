import re
import sys
from resources.lib.functions import path, update
from resources.cinemagia.cinemagia import headers, main_url, log
import xbmcvfs

if __name__ == '__main__':
    if len(sys.argv) > 1:
        method = sys.argv[1]
    else:
        method = None
    if not method:
        import requests
        req = requests.get(main_url,  headers=headers, verify=False)
        html = req.content.decode()
        regex = '''<li class="station-container">.*?href="{0}(.*?)/".*?>(.*?)<'''.format(main_url)
        channels = re.findall(regex, html, re.DOTALL)
        if channels:
            channels = sorted(channels, key=lambda x: x[0].lower())
            try: addonpath = xbmcvfs.translatePath(path.decode('utf-8'))
            except: addonpath = xbmcvfs.translatePath(path)
            from resources.lib.windows.channel_list import ChannelsXML
            window = ChannelsXML('channel_list.xml', addonpath, 'Default', channels=channels)
            window.run()
            del window
    elif method == 'force_update':
        update(force=True)
