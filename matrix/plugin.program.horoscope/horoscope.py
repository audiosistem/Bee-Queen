import xbmcvfs
import xbmcplugin
import xbmcgui
import xbmcaddon
import sys
import requests
from urllib.parse import parse_qsl
from bs4 import BeautifulSoup
from plugin import m

BASE_URL= 'https://www.horoscope.com/us/horoscopes/general/horoscope-general-daily-today.aspx?sign='
TEMP_FILE = m.temp_file

INDEX = {
    'None':  [0, ''],
    'Aries': [1, 'https://blog.prepscholar.com/hubfs/body-aries-ram-zodiac.jpg'],
    'Taurus': [2, 'https://static.toiimg.com/thumb/msid-88128028,width-400,resizemode-4/88128028.jpg'],
    'Gemini': [3, 'https://cdn.cdnparenting.com/articles/2020/06/05131126/1444434599.jpg'],
    'Cancer': [4, 'https://t4.ftcdn.net/jpg/02/93/21/41/360_F_293214101_gClgXR0FYvDXwa8e8ljix6HHP6Y8QiUw.jpg'],
    'Leo': [5, 'https://wallpaperaccess.com/full/1840957.jpg'],
    'Virgo': [6, 'https://cdn.shopify.com/s/files/1/1325/0879/articles/headers-zodiac-sign-astrology-personality-positives-negatives-cheat-sheet-virgo_1024x1024.png'],
    'Libra': [7, 'https://cdn.shopify.com/s/files/1/1325/0879/articles/headers-zodiac-sign-astrology-personality-positives-negatives-cheat-sheet-libra_1024x1024.png'],
    'Scorpio': [8, 'https://blog.prepscholar.com/hubfs/zodiac-sign-4374412_1920.jpg'],
    'Sagittarius': [9, 'https://cdn.shopify.com/s/files/1/1325/0879/articles/headers-zodiac-sign-astrology-personality-positives-negatives-cheat-sheet-sagittarius_1024x1024.png'],
    'Capricorn': [10, 'https://nypost.com/wp-content/uploads/sites/2/2021/11/astrology-capricorn-1-copy.jpg'],
    'Aquarius': [11, 'https://askastrology.com/wp-content/uploads/2020/07/aquarius_astrology_sign.jpg'],
    'Pisces': [12, 'https://nypost.com/wp-content/uploads/sites/2/2021/12/astrology-pisces-explained-1-copy.jpg?quality=75&strip=all']
}


def main():
    m.add_dir(m.color_text('deepskyblue', '*****CHOOSE YOUR SIGN*****'), '', '', m.addon_icon, m.addon_fanart, '', isFolder=False)
    for x in INDEX.keys():
       if x != 'None':
           m.add_dir(m.color_text('snow', x), f'{BASE_URL}{INDEX[x][0]}', 'horoscope', INDEX[x][1], INDEX[x][1], x, isFolder=False)

def horoscope(url: str) -> str:
    response = requests.get(url, m.headers).text
    soup = BeautifulSoup(response, 'html.parser')
    return soup.p.text

KEY_NAV_BACK = 92
TEXTBOX = 300
CLOSEBUTTON = 302
NAME = 303

def get_horoscope(name: str, url: str, startup: bool = False, name2: str = '', url2: str = '') -> None:
    message = horoscope(url)
    if url2:
        message = f'{name}:\n{message}\n\n{name2}:\n{horoscope(url2)}'
        name = f'{name}/{name2}'
    
    class Notify(xbmcgui.WindowXMLDialog):
        
        def onInit(self):
            self.getControl(TEXTBOX).setText(message)
            self.getControl(NAME).setText(name)
            
        def onAction(self, action):
            if action.getId() == KEY_NAV_BACK:
                self.Close()
    
        def onClick(self, controlId):
            if controlId == CLOSEBUTTON:
                self.Close()

        def Close(self):
            self.close()
    
    if startup:
        if xbmcvfs.exists(TEMP_FILE):
            old = m.open_textfile(TEMP_FILE)
            if old == message:
                return
    d = Notify('notify.xml', xbmcaddon.Addon().getAddonInfo('path'), 'Default', '720p')
    d.doModal()
    del d
    if startup:
        m.write_textfile(TEMP_FILE, message)

def router(paramstring):
    if not xbmcvfs.exists(m.addon_data):
        xbmcvfs.mkdirs(m.addon_data)
    p = dict(parse_qsl(paramstring))
    name = p.get('name', '')
    url = p.get('url', '')
    mode = p.get('mode')
    
    if mode is None:
        main()
    elif mode == 'horoscope':
        get_horoscope(name, url)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))