# -*- coding: utf-8 -*-
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import urllib
import os, os.path
import json, re
import ntpath
import HTMLParser

from glob import addon_log, addon, Downloader, cleanJson, message
from player import player
__addon__ = xbmcaddon.Addon()
__cwd__        = xbmc.translatePath(__addon__.getAddonInfo('path')).decode("utf-8")
__resource__   = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'lib')).decode("utf-8")
sys.path.append (__resource__)
import requests
def listCurrent():
  url = 'http://www.eteatru.ro/play.htm'
  
  temp = os.path.join(addon.getAddonInfo('path'),"play.htm")
  
  try: 
    Downloader(url, temp, addon.getLocalizedString(30000), addon.getLocalizedString(30001))
    f = open(temp)
    playInfoTxt = f.read()
    f.close()
    os.remove(temp)
  except Exception as inst:
    addon_log(inst)
    playInfoTxt = ""
  
  playInfoTxt = cleanJson(playInfoTxt)
  #addon_log(playInfoTxt)
    
  try:
    playInfo = json.loads(playInfoTxt, encoding='iso-8859-2')
    name = playInfo[0][1]
    pars = HTMLParser.HTMLParser()
    name = pars.unescape(name)
    name = name.encode('utf8')
    comment = playInfo[0][2]
    comment = pars.unescape(comment)
    comment = re.sub('<[^<]+?>', '', comment)
    comment = comment.encode('utf8')
    url = playInfo[0][3]
    offset = playInfo[0][6]
  except Exception as inst:
    addon_log(inst)
    return False
  
  plugin=sys.argv[0]
  listitem = xbmcgui.ListItem(name, iconImage="DefaultAudio.png")
  listitem.setInfo('music', {'Title': name, 'Comment':comment})
  u=plugin+"?mode=2"+\
           "&url="+urllib.quote_plus(url)+\
           '&title='+urllib.quote_plus(name)+\
           '&comment='+urllib.quote_plus(comment)
  contextMenuItems = [( addon.getLocalizedString(30010), "XBMC.RunPlugin("+u+")", )]
  listitem.addContextMenuItems(contextMenuItems)
  
  xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=url,listitem=listitem,isFolder=False)
  xbmc.executebuiltin("Container.SetViewMode(51)")
  
#def playCurrent(params):
#  p = player(xbmc.PLAYER_CORE_AUTO, offset=int(playInfo[0][6]))
#  p.play(playInfo[0][3], listitem)
  
def addDir(name, mode, params=None):
  contextMenuItems = []

  plugin=sys.argv[0]

  u = plugin+"?"+"mode="+str(mode)
  if(params!=None):
    for param in params:
      u = u + '&' + param['name'] + '=' + param['value']  
    
  liz = xbmcgui.ListItem(name, iconImage="DefaultFolder.png")
  liz.setInfo( type="Audio", infoLabels={ "Title": name })
  xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=u,listitem=liz,isFolder=True)

def catList():
  addDir(addon.getLocalizedString(30005), 1)
  adaugDir(addon.getLocalizedString(30006), 'http://www.eteatru.ro/program.htm', 5, 'zile')
  adaugDir("Colecții", 'http://www.eteatru.ro/art-index.htm?c=3491', 5)
  addLink("Live", 'http://www.eteatru.ro', 7)
  
  #Downloads
  if(addon.getSetting('download_path')!=''):
    liz = xbmcgui.ListItem(addon.getLocalizedString(30008), iconImage="DefaultFolder.png")
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=addon.getSetting('download_path'), listitem=liz, isFolder=True)
    
  xbmc.executebuiltin("Container.SetViewMode(51)")

def getParams():
  param=[]

  paramstring=sys.argv[2]

  if len(paramstring)>=2:
    params=sys.argv[2]
    cleanedparams=params.replace('?','')
    if (params[len(params)-1]=='/'):
      params=params[0:len(params)-2]
    pairsofparams=cleanedparams.split('&')
    param={}
    for i in range(len(pairsofparams)):
      splitparams={}
      splitparams=pairsofparams[i].split('=')
      if (len(splitparams))==2:
        param[splitparams[0]]=splitparams[1]
  return param

def downloadItem(params):
  url = params['url']
  url = urllib.unquote_plus(url)
    
  if(addon.getSetting('download_path')==''):
    message(addon.getLocalizedString(30001), addon.getLocalizedString(30009))
    return False
  
  dest = os.path.join(addon.getSetting('download_path'), ntpath.basename(url))
  
  try: 
    Downloader(url, dest, addon.getLocalizedString(30000), addon.getLocalizedString(30001))
    pass
  except Exception as inst:
    addon_log(inst)
    
  #addon_log(params)
  #ADD ID3
  from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, COMM, TCON
  title = params['title']
  title = urllib.unquote_plus(title)
  comment = params['comment']
  comment = urllib.unquote_plus(comment)
  try: 
    tags = ID3(dest)
  except ID3NoHeaderError:
    tags = ID3()
  tags['TIT2'] = TIT2( encoding=3, text=title.decode('utf8') )
  tags['COMM'] = COMM( encoding=3, desc='', text=comment.decode('utf8') )
  tags['TCON'] = TCON( encoding=3, text=u'teatru')
  tags.save(dest)

def downloadProgram(d=None):
  url = 'http://www.eteatru.ro/program.htm'
  if(d!=None):
    url = url + '?d='+d
   
  temp = os.path.join(addon.getAddonInfo('path'),"program.htm")
  
  try: 
    Downloader(url, temp, addon.getLocalizedString(30000), addon.getLocalizedString(30007))
    f = open(temp)
    programTxt = f.read()
    f.close()
    os.remove(temp)
  except Exception as inst:
    programTxt = ""
  
  programTxt = cleanJson(programTxt)
  addon_log(programTxt)
  
  try:
    program = json.loads(programTxt, encoding='iso-8859-2')
    return program
  except Exception as inst:
    addon_log(inst)
    return False

def listProgram():
  program = downloadProgram()
  
  for item in program:
    if(item[0]=='week'):
      name = item[6]+' '+item[7]
      name = name.encode('utf8')
      addDir(name, 4, [{'name':'d', 'value':item[5]}])
  
  xbmc.executebuiltin("Container.SetViewMode(51)")

def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def listProgramDay(params):
  program = downloadProgram(params['d'])
  
  for item in program:
    if(item[0]=='program'):
      name = item[3]+' '+item[4]
      pars = HTMLParser.HTMLParser()
      name = pars.unescape(name)
      name = name.encode('utf8')
      comment = item[5]
      comment = pars.unescape(comment)
      comment = comment.encode('utf8')
      listitem = xbmcgui.ListItem(name, iconImage="DefaultAudio.png")
      listitem.setInfo('music', {'Title': name, 'Comment':comment})
      xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=None, listitem=listitem, isFolder=False)
  
  xbmc.executebuiltin("Container.SetViewMode(51)")
def play(url, name):
    liz = xbmcgui.ListItem(name)
    liz.setInfo('music', infoLabels={"Title": name})
    xbmc.Player().play(url, liz, False)
    
def play_live(url, name):
    s = requests.Session()
    ua = 'Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:16.0.1) Gecko/20121011 Firefox/16.0.1'
    headers = {'User-Agent': ua}
    html = s.get(url, headers=headers, verify=False)
    content = html.content.replace("\n","").replace("\r","")
    url = re.findall('radio".+?href="(.+?)"', content, re.DOTALL)[0]
    liz = xbmcgui.ListItem(name)
    liz.setInfo('music', infoLabels={"Title": name})
    xbmc.Player().play(url, liz, False)

def adaugDir(name, url, mode, switch=None, descriere=None):
    ok = True
    name = HTMLParser.HTMLParser().unescape(name.decode('utf-8')).encode('utf-8')
    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(name)
    if switch: u += '%s&switch=%s' % (u, urllib.quote_plus(switch))
    liz = xbmcgui.ListItem(name)
    liz.setInfo('music', infoLabels={"Title": name})
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok

def addLink(name, url, mode):
    ok = True
    name = HTMLParser.HTMLParser().unescape(name.decode('utf-8')).encode('utf-8')
    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(name)
    liz = xbmcgui.ListItem(name)
    liz.setInfo(type="Audio", infoLabels={"Title": name})
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=False)
    return ok

def listColections(url, switch=""):
    s = requests.Session()
    ua = 'Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:16.0.1) Gecko/20121011 Firefox/16.0.1'
    headers = {'User-Agent': ua}
    html = s.get(url, headers=headers, verify=False)
    content = html.content.replace("\n","").replace("\r","")
    if switch == "articles":
        match = re.compile('''"articles".+?"(\d+)".+?"(.+?)".+?"(.+?)".+?"(.+?)".+?((?:art-au|source).+?mp3)''', re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(content)
        for nr, grb1, grb2, grb3, audio in match:
            if "source" in audio:
                nr = re.search(r'''src=["'](.+?)$''', audio.replace("\\","")).group(1)
            else:
                nr = 'http://static.srr.ro/audio/articles/%s/%s' % (grb1, audio)
            try: nume = grb3.decode('iso-8859-2').encode('utf8')
            except: nume = grb3
            addLink(nume,nr,6)
    elif switch == "zile":
        match = re.compile('''"week".+?"(\d+)".+?"(.+?)".+?"(.+?)".+?"(.+?)".+?"(.+?)".+?"(.+?)".+?"(.+?)"''', re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(content)
        for week, age, today, display, date, day1, day2 in match:
            if display == "1":
                try: day1 = day1.decode('iso-8859-2').encode('utf8')
                except: day1 = day1
                url = 'http://www.eteatru.ro/program.htm?d=%s' % date
                adaugDir('%s %s' % (day1, day2),url,5,'program')
    elif switch == "program":
        match = re.compile('''"program".*?"(\d{4,9})".+?"".+?"(.+?)",.+?"(.+?)".+?"(.+?)"''', re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(content)
        for nr, ora, nume, autori in match:
            try: nume = cleanhtml(nume.replace("\\","")).decode('iso-8859-2').encode('utf8')
            except: nume = nume.decode('iso-8859-2').encode('utf8')
            try: autori = cleanhtml(autori.replace("\\","")).decode('iso-8859-2').encode('utf8')
            except: autori = autori.decode('iso-8859-2').encode('utf8')
            adaugDir('ora %s - %s' % (ora, nume) ,url,9)
    else:
        match = re.compile('''"subcategory".+?"(\d+)".+?"(.+?)".+?"(.+?)".+?"(.+?)"''', re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(content)
        for nr, grb1, grb2, grb3 in match:
            nr = '%s%s' % ('http://www.eteatru.ro/art-index.htm?c=', nr)
            try: nume = grb2.decode('iso-8859-2').encode('utf8')
            except: nume = grb2
            adaugDir(nume,nr,5,'articles')
    #for one in content:
        
    #with open(xbmc.translatePath(os.path.join('special://temp', 'files.py')), 'wb') as f: f.write(repr(content))
    
#######################################################################################################################
#######################################################################################################################
#######################################################################################################################

#read params
params=getParams()
try: mode=int(params["mode"])
except: mode=None
try: url = urllib.unquote_plus(params["url"])
except: url = None
try: switch = urllib.unquote_plus(params["switch"])
except: switch = None
try: name = urllib.unquote_plus(params["name"])
except: name = None

if mode==None: 
  catList()
elif mode==1:
  listCurrent()
elif mode==2:
  downloadItem(params)
elif mode==3:
  listProgram()
elif mode==4:
  listProgramDay(params)
elif mode==5:
  listColections(url,switch)
elif mode==6:
  play(url,name)
elif mode==7:
    play_live(url, name)
      

xbmcplugin.endOfDirectory(int(sys.argv[1]))
