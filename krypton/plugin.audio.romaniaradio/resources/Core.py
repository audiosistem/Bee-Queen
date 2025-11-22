# -*- coding: utf-8 -*-
from .functions import *
try:
    from urlparse import urljoin
except:
    from urllib.parse import urljoin
from xbmcplugin import SORT_METHOD_ALBUM, SORT_METHOD_UNSORTED, SORT_METHOD_GENRE

class Core:
    __plugin__ = sys.modules["__main__"].__plugin__
    __settings__ = sys.modules["__main__"].__settings__
    __scriptname__ = __settings__.getAddonInfo('name')
    ROOT = sys.modules["__main__"].__root__
    base_url = 'http://www.romaniaradio.ro/'

    def sectionMenu(self):
        
        self.drawItem('[COLOR lime]Toate[/COLOR]', 'getStations', {'url' : urljoin(self.base_url, 'Radio-Romania.html')}, image=search_icon)
        self.drawItem('[COLOR lime]După regiune[/COLOR]', 'getRegions', {}, image=search_icon)
        self.drawItem('[COLOR lime]După format[/COLOR]', 'getFormat', {}, image=search_icon)
        self.drawItem('[COLOR lime]După popularitate[/COLOR]', 'getPopular', {}, image=search_icon)

        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)
    
    
    def getStations(self, params={}):
        reg_body = '''<tbody>(.+?)</tbody>'''
        reg_radio = '''<tr(.+?)</tr>'''
        reg_info = '''<td(?:>|.*?>)(.*?)</td>'''
        link = fetchData(unquote(params.get('url')))
        #log(str(params))
        try:
            body = re.findall(reg_body, link, re.DOTALL)[0]
            radios = re.findall(reg_radio, body, re.DOTALL)
            for radio in radios:
                if not re.search('OFF-LINE', radio):
                    info_one = re.findall(reg_info, radio, re.DOTALL)
                    nume = re.search('<b>(.+)</b', info_one[0])
                    try:
                        more_url = re.findall('href="(.+?)">(\d+)?<', info_one[4])
                    except: pass
                    url = None
                    if nume:
                        nume = nume.group(1)
                        localizare = info_one[1]
                        try: url = re.search('url=(.+?)\)', info_one[2]).group(1)
                        except: 
                            try: 
                                url = more_url[0][0]
                            except: pass
                    if url:
                        try: genre = striphtml(info_one[5])
                        except:
                            genre = None
                            #genre = None
                        channel = striphtml(info_one[1])
                        url = re.sub('\'|;', '',  url)
                        info = {'title': nume, 'genre': genre, 'album': '%s - %s - %s' % (nume, genre, channel), 'comment': '%s - %s - %s' % (nume, genre, channel)}
                        self.drawItem(nume, 'playRadio', {'link': url, 'nume': nume, 'info': info}, isFolder=False)
                    #log(nume + ': ' + localizare + ' : ' + url)
        except:
            get = params.get
            nume = unquote(get('nume'))
            url = re.findall('iframe src="(.+?)"', link, re.DOTALL)[0]
            url = re.search('url=(.+?);', url).group(1)
            self.playRadio({'link': url, 'nume': nume, 'info': str({'title': nume})})
        xbmcplugin.setContent(int(sys.argv[1]), 'songs')
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)
        
    def getRegions(self, params={}):
        link = fetchData(self.base_url)
        urls = re.findall('dupa regiune(.+?)</table', link, re.IGNORECASE | re.DOTALL)
        for radio in re.findall('li>.+?href="(.+?)".+?title="(.+?)">(.+?)<', urls[0]):
            url = urljoin(self.base_url, radio[0])
            titlu = radio[1]
            nume = radio[2]
            self.drawItem(nume, 'getStations', {'url': url, 'nume': nume, 'comment': titlu}, isFolder=True)
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)
    
    def getFormat(self, params={}):
        link = fetchData(self.base_url)
        urls = re.findall('dupa format(.+?)popularitate', link, re.IGNORECASE | re.DOTALL)
        content = re.findall('(?:<b>(.+?)</b>.+?)?li>.+?href="(.+?)".+?title="(.+?)">(.+?)<', urls[0], re.DOTALL)
        for categorie, url, titlu, nume in content:
            url = urljoin(self.base_url, url)
            info = {'title': nume, 'comment': '%s - %s' % (titlu, nume)}
            self.drawItem('[COLOR lime]%s[/COLOR]' % striphtml(categorie), 'nothing', 'urltr', isFolder=False, fileSize=2) if categorie else ''
            self.drawItem(nume, 'getStations', {'url': url, 'nume': nume, 'info': info}, isFolder=True)
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)
    
    def getPopular(self, params={}):
        link = fetchData(self.base_url)
        urls = re.findall('dupa popularitate(.+?)</table', link, re.IGNORECASE | re.DOTALL)
        content = re.findall('(?:<b>(.+?)</b>.+?)?li>.+?href="(.+?)".+?title="(.+?)">(.+?)<', urls[0], re.DOTALL)
        for categorie, url, titlu, nume in content:
            #self.categorie = categorie if categorie else self.categorie
            url = urljoin(self.base_url, url)
            info = {'title': nume, 'comment': '%s - %s' % (titlu, nume)}
            self.drawItem(nume, 'playRadio', {'link': url, 'nume': nume, 'info': info}, isFolder=False)
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]), succeeded=True)
    
    def playRadio(self, params={}):
        get = params.get
        url = unquote(get('link'))
        nume = unquote(get('nume'))
        genre = unquote(get('genre'))
        info = unquote(get('info'))
        if url.endswith('.pls'):
            data = fetchData(url)
            url = re.findall('File1=(.*?)\n', data)[0]
        elif url.endswith('.shtml'):
            url = re.findall('iframe src="(.+?)"', fetchData(url), re.DOTALL)[0]
            #log(str(url))
            url = re.search('url=(.+?)(?:;|$)', url).group(1)
        liz = xbmcgui.ListItem(nume)
        liz.setInfo('Music', infoLabels=eval(info))
        xbmc.Player().play(url, liz, False)
    
    def drawItem(self, title, action, link='', image='', isFolder=True, contextMenu=None, replaceMenu=True, action2='', fileSize=0):
        
        if isinstance(link, dict):
            link_url = ''
            if link.get('categorie'):
                link_url = '%s&%s=%s' % (link_url, 'categorie', link.get('categorie'))
            else:
                for key in link.keys():
                    if link.get(key):
                        if isinstance(link.get(key), dict):
                            link_url = '%s&%s=%s' % (link_url, key, quote(json.dumps(link.get(key), ensure_ascii=False)))
                        else:
                            link_url = '%s&%s=%s' % (link_url, key, quote(link.get(key)))
                            if key == 'switch' and link.get(key) == 'play': isFolder = False
            info = link.get('info')
            if info:
                if isinstance(info, str):
                    info  = eval(info)
                if isinstance(info, dict):
                    image = info.get('Poster')
            url = '%s?action=%s' % (sys.argv[0], action) + link_url
        else:
            info = {"Title": title, "comment": title}
            url = '%s?action=%s&url=%s' % (sys.argv[0], action, quote(link))
        if action2:
            url = url + '&url2=%s' % quote(ensure_str(action2))
        listitem = xbmcgui.ListItem(title)
        images = {'icon':image, 'thumb':image}
        images = {'icon': image, 'thumb': image,
                  'poster': image, 'banner': image,
                  }
        listitem.setArt(images)
        if isFolder:
            listitem.setProperty("Folder", "true")
            listitem.setInfo(type='Audio', infoLabels=info)
        else:
            #listitem.setProperty('isPlayable', 'true')
            listitem.setInfo(type='Music', infoLabels=info)
            listitem.setArt({'thumb': image})
        if contextMenu:
            listitem.addContextMenuItems(contextMenu, replaceItems=replaceMenu)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=isFolder)
        if not isFolder and fileSize == 0:
            xbmcplugin.addSortMethod(int(sys.argv[1]), SORT_METHOD_GENRE)
            xbmcplugin.addSortMethod(int(sys.argv[1]), SORT_METHOD_UNSORTED)
            #xbmcplugin.addSortMethod(int(sys.argv[1]), SORT_METHOD_ALBUM)

    def getParameters(self, parameterString):
        commands = {}
        splitCommands = parameterString[parameterString.find('?') + 1:].split('&')
        for command in splitCommands:
            if (len(command) > 0):
                splitCommand = command.split('=')
                if (len(splitCommand) > 1):
                    name = splitCommand[0]
                    value = splitCommand[1]
                    commands[name] = value
        return commands

    def executeAction(self, params={}):
        get = params.get
        if hasattr(self, get("action")):
            getattr(self, get("action"))(params)
        else:
            self.sectionMenu()

    def localize(self, string):
        #try:
            #return Localization.localize(string)
        #except:
        return string
