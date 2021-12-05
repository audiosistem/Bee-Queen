# -*- coding: utf-8 -*-
import os
import sys

try:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError


import re
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import plugintools
import unicodedata
import base64
import requests
import shutil
import base64
import time
import six
import random
from datetime import date
from datetime import datetime
from resolveurl.plugins.lib import jsunpack 
from resources.modules import control

if six.PY3:
    unicode = str
#PY3=False
#if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int
addon = xbmcaddon.Addon()
addonname = '[LOWERCASE][CAPITALIZE][COLOR orange]Mac[COLOR orange]VOD[/CAPITALIZE][/LOWERCASE][/COLOR]'
icon = addon.getAddonInfo('icon')
myaddon = xbmcaddon.Addon("plugin.video.macvod")
#px={"http": "http://14.139.189.213:3128"}
px=''
local_file=xbmc.translatePath('special://home/addons/plugin.video.macvod/proxy.dat')

## Fotos
thmb_nada='https://archive.org/download/bee-1/pngegg%20%281%29.png'
thmb_ver_canales='https://archive.org/download/bee-1/channels%20live.png'
thmb_ver_vod='https://archive.org/download/bee-1/vod%20mac.png'
thmb_cambio_servidor='https://archive.org/download/bee-1/server.png'
thmb_cambio_mac='https://archive.org/download/bee-1/MAC.png'
thmb_carga_servidores='https://archive.org/download/bee-1/arrow.png'
thmb_guarda_servidores='https://archive.org/download/bee-1/rack-server_icon-icons.com_52830.png'
thmb_nuevo_servidor='https://archive.org/download/bee-1/office.png'
thmb_guia='https://archive.org/download/bee-1/vector%20tv.png'
fanny="https://i.ytimg.com/vi/_7bFXWNfXTY/maxresdefault.jpg"
fanart_guia="https://archive.org/download/bee-1/watch%20tv.png"
backgr="https://archive.org/download/bee-1/watch%20tv.png"
thmb_ver_set='https://archive.org/download/bee-1/settings.png'
fnrt_ver_set='https://archive.org/download/bee-1/setting.png'
thmb_ver_xc='https://archive.org/download/bee-1/xtream%20codes.png'
thmb_ver_stb='https://archive.org/download/bee-1/mac-iptv.png'
thmb_ver_m3u='https://archive.org/download/bee-1/live-iptv.png'
thmb_about='https://archive.org/download/bee-1/about.png'
thmb_radio='https://archive.org/download/bee-1/radio.png'
fnrt_radio='https://archive.org/download/bee-1/radio1.png'
thmb_help='https://archive.org/download/bee-1/help.png'
fnrt_help='https://archive.org/download/bee-1/Help1.png'
thmb_ace='https://archive.org/download/bee-1/Ace%20Stream.png'
fnrt_ace='https://archive.org/download/bee-1/Ace.png'
thmb_tube='https://archive.org/download/bee-1/Youtube.png'
fnrt_tube='https://archive.org/download/bee-1/You.png'

portal = control.setting('portal')
mac = control.setting('mac')
userp = control.setting('userp')
portalxc = control.setting('portalxc')
usernamexc = control.setting('usernamexc')
passxc = control.setting('passxc')

def keyboard_input(default_text="", title="", hidden=False):

    keyboard = xbmc.Keyboard(default_text,title,hidden)
    keyboard.doModal()
    
    if (keyboard.isConfirmed()):
        tecleado = keyboard.getText()
    else:
        tecleado = ""

    return tecleado

def run():
    #
    
    # Get params
           
    params = plugintools.get_params()
    
    if params.get("action") is None:
        if PY3==False:
            xbmc.executebuiltin('Container.SetViewMode(51)')        
        
        main_list(params)
    else:
       if PY3==False:
           xbmc.executebuiltin('Container.SetViewMode(51)') 
       action = params.get("action")
       url = params.get("url")
       exec (action+"(params)")

    plugintools.close_item_list()
    
def run():
    
    plugintools.log("---> macvod.run <---")
    #plugintools.set_view(plugintools.LIST)
    
    # Get params
    params = plugintools.get_params()
    
    if params.get("action") is None:
        main_list(params)
    else:
       action = params.get("action")
       url = params.get("url")
       exec(action+"(params)")
    plugintools.close_item_list()

def cambia_fondo():

    foto = xbmc.translatePath('special://home/addons/plugin.video.macvod/fondo.png')    
    if not xbmc.getCondVisibility('Skin.String(CustomBackgroundPath)'):      
        xbmc.executebuiltin('Skin.Reset(CustomBackgroundPath)')
        xbmc.executebuiltin('Skin.SetBool(UseCustomBackground,True)')   
        xbmc.executebuiltin('Skin.SetString(CustomBackgroundPath,'+foto+')')
        xbmc.executebuiltin('ReloadSkin()')
    
def main_list(params):
    proxy=params.get('extra')
    import shutil,xbmc  
    try:
        addon_path3 = xbmc.translatePath('special://home/cache').decode('utf-8')
        shutil.rmtree(addon_path3, ignore_errors=True) 
    except:
        pass
    
    cambia_fondo()
        
    plugintools.log("macvod.main_list ")    
    params['title']="[COLOR red]i[COLOR orange]P[COLOR green]TV[COLOR orange] CHaNNeLS[/COLOR]"
    params['thumbnail']=thmb_ver_canales
    params['fanart']="https://i.ytimg.com/vi/_7bFXWNfXTY/maxresdefault.jpg"
    mac=myaddon.getSetting('mac')
    portal=myaddon.getSetting('portal')
	
    plugintools.add_item(title='[COLOR gray]-======== SUPORT =========-[/COLOR]',folder=False, isPlayable=False)   
	
    plugintools.add_item(title='[COLOR dodgerblue]KodiRomania[/COLOR]',folder=False, isPlayable=False)
	
    plugintools.add_item(title='[COLOR dodgerblue]https://t.me/kodiromania[/COLOR]',folder=False, isPlayable=False)
		
    plugintools.add_item(title='[COLOR gray]-=========================-[/COLOR]',folder=False, isPlayable=False) 
	
    plugintools.add_item( action="mac", title="[COLOR orange]STB / MAC[/COLOR]", thumbnail = thmb_ver_stb, fanart= backgr,page="",url="",folder=True )
		
    plugintools.add_item( action="ipkoditv_enigmax", title="[COLOR orange]Xtream Codes[/COLOR]", thumbnail = thmb_ver_xc, fanart= backgr,page="",url="",folder=True )
	
    plugintools.add_item( action="m3u", title="[COLOR orange]Liste M3U[/COLOR]", thumbnail = thmb_ver_m3u, fanart= backgr,page="",url="",folder=True )
    
    plugintools.add_item( action = "radio_pais" , title = "[COLOR orange]Radio[/COLOR]", thumbnail=thmb_radio, fanart= fnrt_radio,  folder = True ) 
    
    plugintools.add_item( action = "acemenu" , title = "[COLOR orange]Acestream[/COLOR]", thumbnail=thmb_ace, fanart= fnrt_ace,  folder = True ) 
    
    plugintools.add_item( action = "youtube" , title = "[COLOR red]Youtube[/COLOR]", thumbnail=thmb_tube, fanart= fnrt_tube,  folder = True ) 
    
    plugintools.add_item( action="help", title="[COLOR orange]Help[/COLOR]", thumbnail = thmb_help, fanart= fnrt_help,page="",url="",folder=True )
	
    plugintools.add_item( action="settings", title="[COLOR orange]Setari[/COLOR]", thumbnail = thmb_ver_set, fanart= fnrt_ver_set,page="",url="",folder=False )

    plugintools.add_item( action="", title="Multumiri: [COLOR red]RED[/COLOR], Cicero Aristotel, iNKuBo ", thumbnail = thmb_about, fanart= backgr,page="",url="",folder=False )

    plugintools.add_item( action="", title="KodiRomania - https://t.me/kodiromania - Grup telegram", thumbnail = thmb_about, fanart= backgr,page="",url="",folder=False )

def help(params):
    plugintools.add_item(action="resolve_resolveurl_youtube", title="Help Video Zona STB / MAC",thumbnail=thmb_ver_stb, fanart="",  url= "S5bQQg8UDGk", folder= False, isPlayable = True )    
    #plugintools.add_item(action="resolve_acestream", title="ace",thumbnail=thmb_ver_stb, fanart="",  url= "0d34dbbd0b311db4f0102bfcf7725f6984df5e28", folder= False, isPlayable = True )    



def settings(params): 
    plugintools.open_settings_dialog()
    xbmc.executebuiltin('Container.Refresh')
	

def mac(params):
    nat=myaddon.getSetting('nat')
    plugintools.add_item(action="tulista", title="[COLOR orange]STB / MAC - Random Server[/COLOR]  [COLOR white]("+nat+" incercari/zi)[/COLOR]",thumbnail=thmb_ver_stb, fanart="https://archive.org/download/bee-1/earth%20varicolor.png",  url= "https://pastebin.com/raw/ktiz5e2M",folder= True )    
    plugintools.add_item( action="macpastebinx", title="[COLOR orange]STB / MAC - Pastebin Server[/COLOR]", thumbnail = thmb_ver_stb, fanart= backgr,page="",url="",folder=True )
    plugintools.add_item( action="macx", title="[COLOR orange]STB / MAC - Your Server[/COLOR]", thumbnail = thmb_ver_stb, fanart= backgr,page="",url="",folder=True )


def macpastebinx(params):
    if userp=="":
        userpast = userpastebin()
        control.setSetting('userp',userpast)
        xbmc.executebuiltin('Container.Refresh')
        cambio_servidor(params)
    else:
        macpastebin(params)
		
def userpastebin():
    kb = xbmc.Keyboard('', 'heading', True)
    kb.setHeading('CONT PASTEBIN')
    kb.setHiddenInput(False)
    kb.doModal()
    if kb.isConfirmed():
        text = kb.getText()
        return text
    else:
        return False
	


def macpastebin(params):
    import shutil,xbmc  
    try:
        addon_path3 = xbmc.translatePath('special://home/cache').decode('utf-8')
        shutil.rmtree(addon_path3, ignore_errors=True) 
    except:
        pass
    
    cambia_fondo()
        
    escogido=myaddon.getSetting('escogido')
    mac=myaddon.getSetting('mac2')
    


    plugintools.log("macvod.macpastebin")    
    plugintools.add_item(action="ver_canales",    title="LISTA CANALE IPTV",thumbnail=thmb_ver_canales,fanart="https://archive.org/download/bee-1/earth%20varicolor.png",folder= True )            
    plugintools.add_item(action="", thumbnail=thmb_nada,title="[COLOR gray]Configuratie actuala--------------------------------------------------------------------------[/COLOR]",folder= False )
    plugintools.add_item(action="cambio_servidor",    title="SERVER Actual:   "+escogido,thumbnail=thmb_cambio_servidor,fanart="https://archive.org/download/bee-1/world%20yellow.png",folder= True )               
    plugintools.add_item(action="cambio_mac",         title="MAC Actual:   "+mac,thumbnail=thmb_cambio_mac,fanart="https://archive.org/download/bee-1/world%20blue.png",folder= True )


def macx(params):
    if portal=="":
        portp = portpopup()
        macn = macpopup()
        control.setSetting('portal',portp)
        control.setSetting('mac',macn)
        xbmc.executebuiltin('Container.Refresh')
        mac2(params)
    else:
        mac2(params)
		
def macpopup():
    kb = xbmc.Keyboard('', 'heading', True)
    kb.setHeading('MAC')
    kb.setHiddenInput(False)
    kb.doModal()
    if kb.isConfirmed():
        text = kb.getText()
        return text
    else:
        return False

def portpopup():
    kb =xbmc.Keyboard ('', 'heading', True)
    kb.setHeading('PORTAL')
    kb.setHiddenInput(False)
    kb.doModal()
    if kb.isConfirmed():
        text = kb.getText()
        return text
    else:
        return False	

def mac2(params):
    plugintools.log("macovd.mac")    
    mac=myaddon.getSetting('mac')
    portal=myaddon.getSetting('portal')
	
    plugintools.add_item( action="tombola", title="[COLOR orange]Canale live[/COLOR]", thumbnail = thmb_ver_canales, fanart= backgr,page=mac,url=portal,folder=True )
    
    plugintools.add_item( action="pelis", title="[COLOR orange]VOD[/COLOR]", thumbnail = thmb_ver_vod, fanart= backgr,page=mac,url=portal,folder=True )


def tombola(params):
    import xbmc, time

    thumbnail = params.get("thumbnail") 
    portal = params.get("url")  
    mac = params.get("page")     
    s=''
    usuario = ''
    def macs(s):
        import requests,re
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain"}
        url=portal+'portal.php?type=stb&action=handshake&JsHttpRequest=1-xml'
        source=requests.get(url, headers=headers).text
 
        return source
    token =macs(s)
    token=re.findall('token":"(.*?)"',token)[0]
    token=str(token)    
    def macs(s):
        import requests,re    
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
        url=portal+'portal.php?type=stb&action=get_profile&JsHttpRequest=1-xml'
        source=requests.get(url, headers=headers).text
        passs=re.findall('login":"","password":"(.*?)"',source )[0]
        typee=re.findall('"stb_type":"(.*?)"',source )[0]
        payload={"login":usuario,"password":passs,"stb_type":typee}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
        url=portal+'portal.php?type=itv&action=get_genres&JsHttpRequest=1-xml'
        s = requests.Session()
        source=s.post(url, headers=headers,data=str(payload)).text
        return source
    source=macs(s)
    data = plugintools.find_multiple_matches(source,'("id":"\d+.*?".*?"title":".*?",")')   
 
 
    for generos in data: 
        patron=plugintools.find_single_match(generos,'"id":"(\d+.*?)".*?"title":"(.*?)"') 
        titulo=patron[1]
        titulo=titulo.replace('\\u2b50','').replace('\\/','/')
        ids=patron[0]
        if  ('romania' in titulo.lower() or 'roumania' in titulo.lower() or 'EU- RO' in titulo):               
            color='lime'
            titulo='[LOWERCASE][CAPITALIZE][COLOR '+color+']'+titulo+'[/CAPITALIZE][/LOWERCASE][/COLOR]'           
        
        else:               
            color='white'
            titulo='[LOWERCASE][CAPITALIZE][COLOR '+color+']'+titulo+'[/CAPITALIZE][/LOWERCASE][/COLOR]'             

        if  ('adultxxxxxxxxx' in titulo.lower()):                        
                 
             titulo=' [LOWERCASE][CAPITALIZE][COLOR fuchsia]'+patron[1]+' seccion x[/CAPITALIZE][/LOWERCASE][/COLOR]'
             dialog = xbmcgui.Dialog()
             ret = dialog.select('[COLOR yellow]CONTIENE CANALES ADULTOS NECESITA CLAVE,¿QUE QUIERES?:[/COLOR]', ['[COLOR lime]METER LA CLAVE Y DISFRUTAR DE ELLOS[/COLOR]', '[COLOR aqua]NO QUIERO  LOS CANALES ADULTOS[/COLOR]'])
             lists = ['si', 'no']
             eleccion = lists[ret]
             if 'no' in eleccion:                 
                           
                 ids='99999999999'  
             if 'si' in eleccion:
                 dialog = xbmcgui.Dialog()
                 d = dialog.input('[B][LOWERCASE][CAPITALIZE][COLOR orange]meter la clave: [COLOR orange]si no la tienes pideta en telegram @tvchopo[/COLOR][/CAPITALIZE][/LOWERCASE][/B]', type=xbmcgui.INPUT_ALPHANUM).replace(" ", "+")
                 if 'x69' in d:
                     ids=ids
                 else:
                     xbmcgui.Dialog().ok('[COLOR orange]LA CLAVE ES INCORRECTA[/COLOR]', '[LOWERCASE][CAPITALIZE][COLOR orange]METE LA CLAVE EN MINUSCULA\nSI NO LO CONSIGUES ESTAMOS EN TELEGRAM [COLOR orange]@TVCHOPO[/COLOR][/CAPITALIZE][/LOWERCASE]')  
        plugintools.add_item( action="lista2", title="[COLOR orange]"+titulo+"[/COLOR]", thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),plot=token,page=mac,extra=portal,url=ids,folder=True )


def lista2(params):
    
    ids = params.get("url")
    portal = params.get("extra")
    mac = params.get("page")
    token = params.get("plot")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
    pb  = xbmcgui.DialogProgress()
    pb.create('Asteapta, se incarca canalele ','')
    count=40;pn=1;data=[]
    while pn <= int(count):
        page=portal+'portal.php?type=itv&action=get_ordered_list&genre='+ids+'&force_ch_link_check=&fav=0&sortby=number&hd=0&p='+str(pn)+'&JsHttpRequest=1-xml'
        try:
            source=requests.get(page, headers=headers).text            
            data +=re.findall('"id":".*?","name":"(.*?)".*?"ch_id":"(.*?)"',source);pn +=1
        except:
            break
            
    i=1
    total=len(data)
    for patron in sorted(data, key=lambda patron: patron[0]):         
        canal=str(patron[1])               
        titulo=str(patron[0]).replace('\u00ed','i').replace('\u00eda','e').replace('\u00f1','ñ').replace('\u00fa','u').replace('\u00f3','o').replace('\u00c1','a').replace('\u00e9','e').replace('\u00e1','a').replace('\\','') 
        #titulo=str(patron[0])
        pb.update(int(100*i/140),str(100*i/total)+'% - Canal '+titulo)         
        plugintools.add_item( action="lista3",extra=str(portal),url=canal,page=mac,plot=params.get("plot"),title="[LOWERCASE][CAPITALIZE][COLOR white]"+colorea(titulo)+"[/CAPITALIZE][/LOWERCASE][/COLOR]", thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),folder=False,  isPlayable = True )         
        i+=1
        
    pb.close()    
    
    
def lista3(params):
    canal = params.get("url")
    portal = params.get("extra")  
    mac = params.get("page")
    titulo1 = params.get("plot")
    headers =headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+titulo1}
    url=portal+'portal.php?type=itv&action=create_link&cmd=http://localhost/ch/'+canal+'_&series=&forced_storage=undefined&disable_ad=0&download=0&JsHttpRequest=1-xml'
    source=requests.get(url, headers=headers).text
    token=re.findall('"cmd":"ffmpeg (.*?)"',source )[0]
    url=token.replace("\\", "")
    url=url
    plugintools.play_resolved_url(url)


def pelis(params):
    import xbmc, time
    portal = params.get("url")
    mac = params.get("page")
    s=''
    usuario = ''
    def macs(s):
        import requests,re
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain"}
        url=portal+'portal.php?type=stb&action=handshake&JsHttpRequest=1-xml'
        source=requests.get(url, headers=headers).text
 
        return source
    token =macs(s)
    token=re.findall('token":"(.*?)"',token)[0]
    token=str(token)    
    def macs(s):
        import requests,re    
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
        url=portal+'portal.php?type=stb&action=get_profile&JsHttpRequest=1-xml'
        source=requests.get(url, headers=headers).text
        passs=re.findall('login":"","password":"(.*?)"',source )[0]
        typee=re.findall('"stb_type":"(.*?)"',source )[0]
        payload={"login":usuario,"password":passs,"stb_type":typee}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
        url=portal+'portal.php?type=vod&action=get_categories&JsHttpRequest=1-xml'
        s = requests.Session()
        source=s.post(url, headers=headers,data=str(payload)).text
        return source
    source=macs(s)
    data = plugintools.find_multiple_matches(source,'("id":"\d+.*?".*?"title":".*?",")')   
 
 
    for generos in data: 
        patron=plugintools.find_single_match(generos,'"id":"(\d+.*?)".*?"title":"(.*?)"') 
        titulo=patron[1]
        titulo=titulo.replace('\\u2b50','')
        ids=patron[0]

        plugintools.add_item( action="pelis2", title="[COLOR orange]"+titulo+"[/COLOR]", thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),plot=token,page=mac,extra=portal,url=ids,folder=True )
def pelis2(params):
    s=''
    ids = params.get("url")
    portal = params.get("extra")
    mac = params.get("page")
    token = params.get("plot")
    headers = '{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="'+mac+'"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "'+token+'}'
    def macs(s):
 
        count=40;pn=1;data=[]
        while pn <= int(count):
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
            page=portal+'portal.php?type=vod&action=get_ordered_list&genre='+ids+'&force_ch_link_check=&fav=0&sortby=number&hd=0&p='+str(pn)+'&JsHttpRequest=1-xml';source=requests.get(page, headers=headers).content.decode('ascii','ignore')
            data +=re.findall('("id":".*?".*?,"name":".*?".*?.*?"description":".*?".*?"year":".*?".*?screenshot_uri":".*?".*?_str":".*?","cmd":".*?")',source);pn +=1
        return data
    
    url=macs(s)
    for generos in url: 
        patron = plugintools.find_single_match(generos,'"id":".*?".*?,"name":"(.*?)".*?.*?"description":"(.*?)".*?"year":"(.*?)".*?screenshot_uri":"(.*?)".*?_str":"(.*?)","cmd":"(.*?)"')
        foto=patron[3].replace("\\", "")
        titulo=patron[0].replace("\\u00f1", "n")
        titulo=titulo.replace('\\/','').replace('\u2b50','')
        texto=patron[1]
        year=patron[2].replace('N\\/A','')
        canal=patron[5]
        plugintools.add_item( action="pelis3",extra=portal,url=canal,page=mac,plot=params.get("plot"),title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+" [COLOR yellow]"+year+"[/CAPITALIZE][/LOWERCASE][/COLOR]", thumbnail = foto, fanart= foto,folder=False,  isPlayable = True ) 
  
def pelis3(params):
    s=''
    canal = params.get("url")
    portal = params.get("extra")
    mac = params.get("page")

    def macs(s):
        import requests,re  
        headers =headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+params.get("plot")}
        url=portal+'portal.php?type=vod&action=create_link&cmd='+canal+'_&forced_storage=undefined&disable_ad=0&download=0&JsHttpRequest=1-xml'
        source=requests.get(url, headers=headers).text
        token=re.findall('"cmd":"ffmpeg (.*?)"',source )[0]
        source= token.replace("\\", "")
        return source
    url=macs(s)
    url=url
    plugintools.play_resolved_url(url)
	
# code xtream
# code xtream
# code xtream

def ipkoditv_enigmax(params):
    if portalxc=="":
        pxc = portalxtream()
        uxc = userxtream()
        passxc = passxtream()
        control.setSetting('portalxc',pxc)
        control.setSetting('usernamexc',uxc)
        control.setSetting('passxc',passxc)
        xbmc.executebuiltin('Container.Refresh')
        ipkoditv_enigma(params)
    else:
        ipkoditv_enigma(params)
		
def portalxtream():
    kb = xbmc.Keyboard('', 'heading', True)
    kb.setHeading('PORTAL XTREAM CODES')
    kb.setHiddenInput(False)
    kb.doModal()
    if kb.isConfirmed():
        text = kb.getText()
        return text
    else:
        return False

def userxtream():
    kb = xbmc.Keyboard('', 'heading', True)
    kb.setHeading('USERNAME')
    kb.setHiddenInput(False)
    kb.doModal()
    if kb.isConfirmed():
        text = kb.getText()
        return text
    else:
        return False
		
def passxtream():
    kb = xbmc.Keyboard('', 'heading', True)
    kb.setHeading('PASSWORD')
    kb.setHiddenInput(False)
    kb.doModal()
    if kb.isConfirmed():
        text = kb.getText()
        return text
    else:
        return False

def ipkoditv_enigma(params): 
    plugintools.log("koditv.ipkoditv")
    thumbnail = params.get("thumbnail")    
    url1=myaddon.getSetting('portalxc')
    username=myaddon.getSetting('usernamexc')
    password=myaddon.getSetting('passxc')   
    url3 = url1+'/enigma2.php?username='+username+'&password='+password
    page='&type=get_live_categories'
    url=url3+page
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'((?s)<title>.*?</title>.*?<description.*?>.*?<.*?CDATA.*?&cat_id=.*?>.*?)')
    for generos in matches:

        url=plugintools.find_single_match(generos,'(&cat_id=.*?)..>.*?')
        description=plugintools.find_single_match(generos,'<description.*?>(.*?)<.*?')
        
        import base64

        description= base64.b64decode(description)
        description = description.decode('utf-8')
        titulo=plugintools.find_single_match(generos,'<title>(.*?)</title>')

        message_bytes = base64.b64decode(titulo)
        titulo = message_bytes.decode('utf-8')
        url=url3+'&type=get_live_streams'+url
        
        
        plugintools.add_item(action="ipkoditv_enigma2", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=True )

def ipkoditv_enigma2(params): 
    plugintools.log("koditv.ipkoditv")
    thumbnail = params.get("thumbnail")    

    url3 = params.get("url")
    
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'((?s)<title>.*?</title>.*?<description.*?>.*?<.*?CDATA..*?..>.*?DATA.*?http.*?.ts)')
    for generos in matches:

        patron=plugintools.find_single_match(generos,'(?s)<title>(.*?)</title>.*?<description.*?>(.*?)<.*?CDATA.(.*?)..>.*?DATA.*?(http.*?.ts)')
       
        url=patron[3]

        titulo=patron[0]
        import base64
        message_bytes = base64.b64decode(titulo)
        titulo = message_bytes.decode('utf-8')

        
        hora = plugintools.find_single_match(titulo,'\[(.*?)\]')
        emision = plugintools.find_single_match(titulo,'(?s) .*?[A-Z].*?[A-Z].*? \[.*?\] ....*?min   (.*)').replace('(','').replace('[','').replace('|','').replace(',','').replace('-','').replace('Live Streams','')
        titulo = plugintools.find_single_match(titulo,'(.*?[A-zZ]: .*?\[|.*?[A-zZ] .*?\[|.*?[A-zZ]: .*?\(|.*?[A-zZ]: .*? .*? |.*?[A-zZ]: [A-zZ].*|.*?[A-Z].*)').replace('(','').replace('[','').replace('|','').replace(',','').replace('-','').replace('Live Streams','')
        
        description=patron[1]
        data=patron[2]
        url = url
        
        plugintools.add_item(action="linkdirecto", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+" [COLOR orange]" +hora+" [COLOR lime]"+emision+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True)
  
		
		
def linkdirecto(params):
    url = params.get("url")    
    plugintools.play_resolved_url(url)   
	
# code m3u
# code m3u
# code m3u	
def m3u(params):
    plugintools.log("macovd.m3u")    
    mac=myaddon.getSetting('mac')
    portal=myaddon.getSetting('portal')
    listam3u=myaddon.getSetting('listam3u')
	
    plugintools.add_item( action="listam3u1", title="[B][COLOR yellow]Lista mea M3U[/COLOR][/B]", thumbnail = thmb_ver_m3u, fanart= backgr,page="",url=listam3u,folder=True )
    plugintools.add_item( action="multilistas", title="Liste Romania",thumbnail="https://archive.org/download/bee-1/romania1.png", fanart="https://archive.org/download/bee-1/national.png",page="",url= "https://www.gratisiptv.com/lists-iptv/",folder= True )
    plugintools.add_item( action="multilistas_mundo", title="Liste pe tari",thumbnail="https://archive.org/download/bee-1/countries.png", fanart="https://archive.org/download/bee-1/earth%20varicolor.png",page="",url= "https://www.gratisiptv.com/lists-iptv/",folder=True ) 	
    plugintools.add_item( action="mundotv", title="GitHub IPTV lists",thumbnail="https://archive.org/download/bee-1/xc%20world%203.png", fanart="https://archive.org/download/bee-1/world%20yellow.png",page="",url="https://github.com/bitsbb01/ez-iptvcat-scraper/tree/master/data/countries",folder=True )
    plugintools.add_item( action="github", title="GitHub IPTV org",thumbnail="https://archive.org/download/bee-1/glob%20green.png", fanart="https://archive.org/download/bee-1/world%20green.png",page="",url="https://github.com/iptv-org/iptv",folder=True )
    plugintools.add_item( action="fluxus", title="Fluxus", thumbnail="https://i.imgur.com/N2r6pj6.jpg", fanart="https://i.imgur.com/N2r6pj6.jpg", page="", url= "https://fluxustvespanol.blogspot.com/p/fluxus-iptv.html", folder=True )    
    plugintools.add_item( action="super_iptv", title="Liste XC World",thumbnail="https://archive.org/download/bee-1/xc%20world.png", fanart="https://archive.org/download/bee-1/world%20red.png",page="",url= "https://usalinksiptv.blogspot.com",folder= True )
    plugintools.add_item( action="super_iptv2", title="Liste XC World2",thumbnail="https://archive.org/download/bee-1/xc%20world%202.png", fanart="https://archive.org/download/bee-1/world%20blue.png",page="",url= "https://telegra.ph/IPTV-playlist-m3u-daily-update-10-31",folder= True )
    plugintools.add_item( action="listam3u1", title="[COLOR orange]M3U List 1[/COLOR]", thumbnail = thmb_ver_m3u, fanart= backgr,page="",url="https://raw.githubusercontent.com/ParrotDevelopers/Parrot-TV-M3U/main/Assets/Channels/RO%20Channels.m3u",folder=True )
    #plugintools.add_item( action="listam3u2", title="[COLOR orange]Radio M3U List[/COLOR]", thumbnail = thmb_ver_m3u, fanart= backgr,page="",url="https://pastebin.com/raw/kDRHz4DB",folder=True )


def mundotv(params): 
    plugintools.log("macvod.mundotv")
    thumbnail = params.get("thumbnail")    
    url3 = params.get("url")    
    s = ''
    def macs(s):
        import requests,re
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0"}
        url=url3
        source=requests.get(url, headers=headers).text
        token=re.findall('(title=".*?.json" data-pjax="#repo-content-pjax-container" href="/bitsbb01/ez-iptvcat-scraper/blob/master/data/countries/.*?")',source ) 
        return token
    url =macs(s)
    for generos in url:
        title=plugintools.find_single_match(generos,'title="(.*?).json') 
        url='https://raw.githubusercontent.com/bitsbb01/ez-iptvcat-scraper/master/data/countries/'+plugintools.find_single_match(generos,'href=".*?blob/master/data/countries/.*?(.*?)"')
        plugintools.add_item(action="mundotv2", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+str(title)+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=True )

def mundotv2(params): 
    plugintools.log("macvod.mundotv")
    thumbnail = params.get("thumbnail")    
    url3 = params.get("url")    
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'("id.+?lastChecked")')

    for generos in matches:
        title=plugintools.find_single_match(generos,'"channel": "(.*?)"') 
        url=plugintools.find_single_match(generos,'link": "(.*?)"') 
        status=plugintools.find_single_match(generos,'status": "(.*?)"') 
        if 'online'in status:
            status='[COLOR lime]'+status
        else:
            status='[COLOR red]'+status
        plugintools.add_item(action="linkdirecto", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+title+" " +status+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True)


def multilistas_mundo(params): 
    plugintools.log("macvod.multilistas_mundo")
    thumbnail = params.get("thumbnail")    
   
    url = params.get("url")
    
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'((?s)menu-item-has-children menu-item-.*?<a href=".*?">.*?<.*?|item-object-category menu-item-.*?href=".*?">.*?<)')
    for generos in matches:
        pais=plugintools.find_single_match(generos,'tem-has-children menu-item-.*?<a href=".*?">(.*?)<.*?|item-object-category menu-item-.*?href=".*?">.*?<')
        url=plugintools.find_single_match(generos,'item-object-category menu-item-.*?href="(.*?)"')
        titulo=plugintools.find_single_match(generos,'(?s)menu-item-has-children menu-item-.*?<a href=".*?">.*?<.*?|item-object-category menu-item-.*?href=".*?">(.*?)<')
        request_headers=[]
        request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
        body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
        url = body.strip().decode('utf-8')
        url=plugintools.find_single_match(url,'(?s)archive-title">Category.*? itemprop="headline"><a href="(.*?)"')        
        plugintools . add_item ( action = "multilistas_mundo2" , title = "[LOWERCASE][CAPITALIZE][COLOR lime]"+pais+" [COLOR orange]"+titulo+"[/CAPITALIZE][/LOWERCASE][/COLOR]", url = url, thumbnail =  thumbnail , fanart=thumbnail, folder=True)


def multilistas_mundo2(params): 
    plugintools.log("macvod.multilistas_mundo")
    thumbnail = params.get("thumbnail")    

       
    url = params.get("url")
    
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'(<a href="https://gratisiptv.com/m3u/.*?">Download .*? IpTV .*?</a>)')
    for generos in matches:

        patron=plugintools.find_single_match(generos,'<a href="(https://gratisiptv.com/m3u/.*?)">Download .*? IpTV (.*?)</a>')
        url=patron[0]
        titulo=patron[1] 
        plugintools . add_item ( action = "multilistas2" , title = "[LOWERCASE][CAPITALIZE] [COLOR orange]"+titulo+"[/CAPITALIZE][/LOWERCASE][/COLOR]", url = url, thumbnail =  thumbnail , fanart=thumbnail, folder=True )
        

def multilistas(params): 
    plugintools.log("macvod.adictos ")
    thumbnail = params.get("thumbnail")    
    url = params.get("url")    
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    url = plugintools.find_single_match(url,'category menu-item-424"><a href="(https://www.gratisiptv.com/.*?roma.*?)">Romanian')    
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    url = plugintools.find_single_match(url,'(?s)Category: Romanian.*?itemprop="headline"><a href="(.*?)">')
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'((?s)<a href="https://gratisiptv.com/m3u/.*?">Download Romania IpTV .*?<)')
    for generos in matches:
        matches = plugintools.find_single_match(generos,'(?s)<a href="(https://gratisiptv.com/m3u/.*?)">Download Romania IpTV (.*?)<')
        url = matches[0]
        titulo = matches[1]
        plugintools . add_item ( action = "multilistas2" , title = "[LOWERCASE][CAPITALIZE][COLOR gold]"+titulo+"[/CAPITALIZE][/LOWERCASE][/COLOR]", url = url, thumbnail =  thumbnail , fanart=thumbnail, folder=True )
   

def multilistas2(params): 
    plugintools.log("macvod.multilistas2")
    thumbnail = params.get("thumbnail")    
    url3 = params.get("url")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'((?i)EXTINF:....*?.*?http.*?#)')

    for generos in matches:
        matches = plugintools.find_single_match(generos,'(?i)EXTINF:....*?(.*?)(http.*?)\s*#')
        url = matches[1]
        titulo = matches[0].replace('|','').replace(',','').replace('-','')    
        server = plugintools.find_single_match(url,'http://(.*?):.*?/')
        import socket
        equipo_remoto = server
        servidor= socket.gethostbyname(equipo_remoto) 
        url=url.replace(server,servidor)     
        plugintools.add_item(action="linkdirecto", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True )

def super_iptv(params): 
    plugintools.log("koditv.super_iptv")
    thumbnail = params.get("thumbnail")           
    url = params.get("url") 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'(post-body entry-content.*?Older Posts)')
    for generos in matches:    
        matches = plugintools.find_multiple_matches(generos,'(http://.*?/get.php.username=.*?&.*?password=.*?&.*?<br)')
        for generos in matches:
            patron=plugintools.find_single_match(generos,'(?s)http://(.*?)/get.php.username=(.*?)&.*?password=(.*?)&.*?<br')
            url1=patron[0]
            servidores = plugintools.find_single_match(url1,'(.*?):')
            try:
                import socket
                equipo_remoto = servidores
                servidor= socket.gethostbyname(equipo_remoto) 
                url1=url1.replace(servidores,servidor)
            except:
                pass
            username=patron[1]
            password=patron[2]
            url='http://'+url1+'/enigma2.php?username='+username+'&password='+password
        
        
            plugintools.add_item(action="super_iptv_enigma", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+servidores+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=True )    


def super_iptv2(params): 
    plugintools.log("koditv.super_iptv2")
    thumbnail = params.get("thumbnail")           
    url = params.get("url") 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'(<article.*?</article>)')
    for generos in matches:    
        matches = plugintools.find_multiple_matches(generos,'(http\:/\\/.+?\/get.php\?username=.+?\&amp\;password=.+?\&amp\;)')
        for generos in matches:
            patron=plugintools.find_single_match(generos,'(?s)(http\:\/\/.+?\/)get.php\?username=(.+?)\&amp\;password=(.+?)\&amp\;')
            url1=patron[0]
            servidores = plugintools.find_single_match(url1,'\/\/(.*?)\/')
            try:
                import socket
                equipo_remoto = servidores
                servidor= socket.gethostbyname(equipo_remoto) 
                url1=url1.replace(servidores,servidor)
            except:
                pass
            username=patron[1]
            password=patron[2]
            url=url1+'enigma2.php?username='+username+'&password='+password
        
        
            plugintools.add_item(action="super_iptv_enigma", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+servidores+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=True )    



def super_iptv_enigma(params): 
    plugintools.log("koditv.ipkoditv")
    thumbnail = params.get("thumbnail")    
   
    url3 = params.get("url")
    page='&type=get_live_categories'
    url=url3+page
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'((?s)<title>.*?</title>.*?<description.*?>.*?<.*?CDATA.*?&cat_id=.*?>.*?)')
    for generos in matches:

        url=plugintools.find_single_match(generos,'(&cat_id=.*?)..>.*?')
        description=plugintools.find_single_match(generos,'<description.*?>(.*?)<.*?')
        
        import base64

        description= base64.b64decode(description)
        description = description.decode('utf-8')
        titulo=plugintools.find_single_match(generos,'<title>(.*?)</title>')

        message_bytes = base64.b64decode(titulo)
        titulo = message_bytes.decode('utf-8')
        url=url3+'&type=get_live_streams'+url
        
        
        plugintools.add_item(action="ipkoditv_enigma2", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+" "+description+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=True )


def github(params): 
    plugintools.log("github.mundotv")
    thumbnail = params.get("thumbnail")    

    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')

    matches = plugintools.find_multiple_matches(url,'(fallback-src=".+?".+?/g-emoji>.+?</td>.+?<code>.+?</code)') 
    for generos in matches:
        patron=plugintools.find_single_match(generos,'(?s)fallback-src="(.+?)".+?/g-emoji>(.+?)</td>.+?<code>(.+?)</code') 
        title=patron[1]
        url=patron[2]
        icn=patron[0]
        plugintools.add_item(action="listam3u1", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+title+"[/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=icn,fanart=thumbnail,folder=True )


def listam3u1(params): 
    plugintools.log("macvod.listam3u1")
    thumbnail = params.get("thumbnail")    

    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')

    matches = plugintools.find_multiple_matches(url,'(#EXTINF:.+?,.*?[\n\r]+[^\n]+)')
    for generos in matches:  
        patron=plugintools.find_single_match(generos,'(?s)#EXTINF:.+?,(.*?)[\n\r]+([^\n]+)')    
        url=patron[1]
        titulo=patron[0]     
     
        plugintools.add_item(action="radio_play", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+" [/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True )

def listam3u2(params): 
    plugintools.log("macvod.listam3u2")
    thumbnail = params.get("thumbnail")    

    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')

    matches = plugintools.find_multiple_matches(url,'(#EXTINF:.+?,.*?[\n\r]+[^\n]+)')
    for generos in matches:  
        patron=plugintools.find_single_match(generos,'(?s)#EXTINF:.+?,(.*?)[\n\r]+([^\n]+)')    
        url=patron[1]
        titulo=patron[0]     
     
        plugintools.add_item(action="resolve_without_resolveurl", url=url,title="[LOWERCASE][CAPITALIZE][COLOR orange]"+titulo+" [/CAPITALIZE][/LOWERCASE][/COLOR]",thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True )


def radio_play(params):            
    url = params.get("url")
    try:
        plugintools.play_resolved_url( url )    
    except:
        pass
        
        
def fluxus (params):
    thumbnail = params.get("thumbnail")    
    plugintools.log("macvod.fluxus")
    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)large;"><b>(.+?)<.*?URL.*?value="(.+?)"', url, re.DOTALL)

    for title, url in matches:
        plugintools . add_item ( action = "fluxus1" , title = title, url = url , thumbnail = "https://koditips.com/wp-content/uploads/fluxus-tv-kodi.png", fanart="", folder = True )  

def fluxus1 (params):
    thumbnail = params.get("thumbnail")    
    plugintools.log("macvod.fluxus1")
    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)#EXTINF:-1.*?logo="(.+?)".*?,(.+?)\n.*?(.+?)\s', url, re.DOTALL)

    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_without_resolveurl" , title = title , url = url , thumbnail = thumb, fanart="", folder = False , isPlayable = True )  

def resolve_without_resolveurl ( params ) :
    import resolveurl 
    url = (params.get ( "url" ))
    finalurl = url.encode("utf-8", "strict")
    plugintools.play_resolved_url ( finalurl ) 
    
def resolve_resolveurl_youtube ( params ) :
    import resolveurl
    finalurl = resolveurl . resolve ( "https://www.youtube.com/watch?v=" + params . get ( "url" ) ) 
    plugintools . play_resolved_url ( finalurl )  

#code macpastebin
#code macpastebin


def ver_canales(params):
      
    thumbnail = params.get("thumbnail")
    
    mac=myaddon.getSetting('mac2')
    portal=myaddon.getSetting('portal2')
    escogido=myaddon.getSetting('escogido')
    s=''
    usuario = ''
  
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain"}
    url=portal+'portal.php?type=stb&action=handshake&JsHttpRequest=1-xml'
        
    source=''
    
    try:
        source = requests.Session()
        source=requests.get(url, headers=headers).content
    except:
    
        xbmc.executebuiltin('XBMC.Notification( Nu se poate conecta la SERVER: ' + escogido +', '+portal+' '+mac+ ', 8000)')            
    
    if source =='':
        xbmc.executebuiltin('XBMC.Notification( Nu se poate conecta la SERVER: ' + escogido +', '+str(source)+ ', 8000)')  
        #xbmc.log('ERROR conectando al servidor: '+str(source)+' : '+str(url))
        #xbmc.executebuiltin('Action(Back)')
        #return(params)
    
    token=''
    try:
        token=re.findall('token":"(.*?)"', str(source) )[0] 
    except:       
        xbmc.executebuiltin('XBMC.Notification( Nu se poate conecta la SERVER: ' + escogido +', '+str(source)+ ', 8000)')  
        #xbmc.executebuiltin('Action(Back)')
        #return(params)
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+str(mac)+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
    url=portal+'portal.php?type=stb&action=get_profile&JsHttpRequest=1-xml'
    source=""
    
    usuario=''
    
    source = requests.Session()           
    source=requests.get(url, headers=headers).content
    
    try:
        passs=re.findall('login":"","password":"(.*?)"',source )[0]
        typee=re.findall('"stb_type":"(.*?)"',str(source) )[0]
    except:
        passs=''
        usuario=''
        typee=''
            
    payload={"login":usuario,"password":passs,"stb_type":typee}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
    url=portal+'portal.php?type=itv&action=get_genres&JsHttpRequest=1-xml'
        
    source=''
    
    s = requests.Session()                
    source=s.post(url, headers=headers,data=str(payload)).text
    
    if source!='':
        
        data = plugintools.find_multiple_matches(source,'("id":"\d+.*?".*?"title":".*?",")')   
        pr0n=myaddon.getSetting('pr0n')  
        plugintools.add_item(title='[COLOR gray]-=========================-[/COLOR]',folder=False, isPlayable=False)   
        plugintools.add_item(title='[COLOR blue]ACTUAL [ '+escogido+' # '+mac+' ][/COLOR]',folder=False, isPlayable=False)
        plugintools.add_item(title='[COLOR gray]-=========================-[/COLOR]',folder=False, isPlayable=False) 
        for generos in data: 
            
            patron=plugintools.find_single_match(generos,'"id":"(\d+.*?)".*?"title":"(.*?)"') 
            titulo=patron[1]
            ids=patron[0]
                        
            tit=colorea(titulo)
            
            if  not('adult' in titulo.lower() and pr0n=="false"):                            
                #plugintools.add_item(action="paginar_canales", title=tit, thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),plot=token,page=mac,extra=portal,url=ids,folder=True)                         
                plugintools.add_item(action="lista2", title=tit, thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),plot=token,page=mac,extra=portal,url=ids,folder=True)
    else:
        xbmc.executebuiltin('XBMC.Notification([COLOR red]Problema '+'[COLOR orange]'+escogido+'[/COLOR],[COLOR orange]'+portal+' '+mac+'[/COLOR], 10000)')            
        
def cambio_servidor(params):

    server2=myaddon.getSetting('ser')
    escogido=myaddon.getSetting('escogido')
    userp=myaddon.getSetting('userp')
    portal= myaddon.getSetting('portal2')
    mac= myaddon.getSetting('mac2')
    dialog = xbmcgui.Dialog()
    
    
    #lists=myaddon.getSetting('lista').split(',')
    #lista_servidores=myaddon.getSetting('lista_servidores').split(',')
    listaservere = urlopen(Request("https://pastebin.com/u/"+userp)).read().decode('utf-8')
    lists = re.findall('(?s)data-key=".+?".+?href="/(.+?)".+?</div', listaservere) 
    #lists=lista
    lista_servidores= re.findall('(?s)data-key=".+?".+?href=".+?">(.+?)<.+?</div', listaservere)
	
	
    retorno = dialog.select('[COLOR blue]Server ACTUAL: [/COLOR]'+str(escogido), lista_servidores)

        
        #if retorno<>-1:
        #xbmc.executebuiltin('XBMC.Notification(Lista,'+lista_servidores[retorno]+',8000)')
        
    dialog = xbmcgui.Dialog()    
        
    if str(retorno)!='-1':   
        server2=lists[retorno]
        escogido=lista_servidores[retorno]
        if 1==1: #try:     
            
            mac1 = urlopen(Request("https://pastebin.com/raw/"+server2)).read().decode('utf-8')
            
            mac=""
            mac=re.findall('(00:.*?79:.*?........)', mac1)            
            portal=re.findall('portal"(.*?)"', mac1.lower())[0]
            maclista=''
            random.seed()
            
            while maclista == '' or not maclista:
                maclista = random.choice(mac)
        
            mac=maclista                
            myaddon.setSetting('mac2',mac)
            myaddon.setSetting('portal2',portal)
            myaddon.setSetting('ser',server2)
            myaddon.setSetting('escogido',escogido)
        else:
        #except:
            xbmc.executebuiltin('XBMC.Notification( Eroare la deschiderea: ' + str(escogido) +', '+str(portal)+' '+str(mac)+ ', 8000)')               
            xbmc.executebuiltin('Action(Back)')        
    else:
        xbmc.executebuiltin('Action(Back)')        

    xbmc.executebuiltin('Content.refresh')
    ver_canales(params)        


def cambio_mac(params):
       
    try:
        server2 = myaddon.getSetting('ser')
        macant= myaddon.getSetting('mac2')
        escogido= myaddon.getSetting('escogido')
    except:
        server2='pfducjrm'
    if escogido=='Fisier_LOCAL':
        xbmc.executebuiltin('XBMC.Notification(Fisier local, Fisierul LOCAL functioneaza cu un singur MAC. Daca doresti sa schimbi MAC-ul adauga o noua linie in fisierul local. , 8000)')                        
        xbmc.executebuiltin('Content.Refresh')
        xbmc.executebuiltin('Action(Back)')
    
    else:

        try:    
            mac1 = urlopen(Request("https://pastebin.com/raw/"+server2)).read().decode('utf-8')
            mac=""
            mac=re.findall('(00:.*?79:.*?........)', mac1)
            portal=re.findall('portal"(.*?)"', mac1.lower())[0]
            dialog = xbmcgui.Dialog()
            ret = dialog.select('MAC ACTUAL: [ '+str(escogido)+' # '+str(macant)+' ]', ['Schimba MAC', 'Continua cu MAC '+macant])
            lists = ['si','no']
    
            categorias= lists[ret]
                
            if 'si' in categorias:
                newmac=''
            
                selectable="Alege un MAC Random"
                for mc in mac:                                    
                        selectable=selectable+','+str(mc)
                
                lista_macs=selectable.split(",")
                ret=dialog.select('Alege un MAC:',lista_macs)

                if ret==1:
                    random.seed()
                    while newmac == '' or not newmac:
                        newmac = random.choice(mac)                      
                else:
                    if ret==-1:
                        newmac=macant
                    else:
                        newmac=mac[ret-1]

                if newmac!=macant:
                        myaddon.setSetting('mac2',newmac)
                        xbmc.executebuiltin('XBMC.Notification( MAC nou, ' +newmac+ ', 8000)')                        
    
        except:
                xbmc.executebuiltin('XBMC.Notification( Eroare MAC nou, Se continua cu' +macant+ ', 8000)')    
                xbmc.executebuiltin('Action(Back)')        

        xbmc.executebuiltin('Content.refresh')
        ver_canales(params)
        
def colorea(titulo):

    if  'Romania' in titulo.lower() or 'rom' in titulo.lower() or 'EU -RO' in titulo or 'romanian' in titulo.lower() or 'EU- RO' in titulo:               
        color='darkorange'                                             
    else:
        if 'crimexxx' in titulo.lower():
            color='springgreen'
        else:
            if 'axnxxxxxx' in titulo.lower()  or 'accionxxxxxxx' in titulo.lower() or 'estrenosxxxxx'  in titulo.lower() or 'historiaxxxxxxx'  in titulo.lower() or 'odiseaxxxxxxxx'  in titulo.lower() or 'discoveryxxxxxxx'  in titulo.lower():
                    color='deeppink'
            else:        
                if 'adult' in titulo.lower() or 'xxx' in titulo.lower() or 'porn' in titulo.lower():
                    color='red'
                else:
                    color='mintcream'
    
    return '[COLOR '+color+']'+titulo+'[/COLOR]'
    

def tulista(params):
    dhoy=date.today()
    text_today = dhoy.strftime("%Y%m%d")        
    hoy=int(text_today)
    try:
        mac=myaddon.getSetting('cam')      
        server=myaddon.getSetting('revres')
        portal=myaddon.getSetting('latrop')
        userp='AudioSistem'
        nat=int(myaddon.getSetting('nat'))
        fec_texto=myaddon.getSetting('fec')
        fec=int(fec_texto)
    except:
        nat=10
        mac=''
        server=''
        portal=''
        myaddon.setSetting('cam',mac)
        myaddon.setSetting('revres',server)
        myaddon.setSetting('latrop',portal)
        myaddon.setSetting('nat',str(nat))
        myaddon.setSetting('fec',text_today)
        fec = hoy
    
    if fec < hoy:     
        nat=10
    
    maximo=False
    if nat<=0:
        xbmcgui.Dialog().ok('MAXIMUM number of lists reached ', 'You have reached the maximum number of lists to use today. You have to wait until tomorrow to be able to use the list again. We leave you with your last list for today ')
        maximo=True
        #xbmc.executebuiltin('Action(Back)')
        #return
    
    #Guardo el nº de veces = nº de veces-1 y guardo la fecha actual
    
    if fec==hoy and maximo==False:
        dialog = xbmcgui.Dialog()
        ret = dialog.select('Selecciona opcion', ['[COLOR red]CREATE NEW LIST [/COLOR]       [ You have left [COLOR green]'+str(nat)+'[/COLOR] attempt ]', '[COLOR white]Continue with TODAY list[/COLOR]'])
        #ret = dialog.select('Selecciona opcion', ['[COLOR red]CREAR LISTA NUEVA[/COLOR]', '[COLOR white]Seguir com mi lista de HOY[/COLOR]'])
    else:
        if maximo==False:
            ret=0
        else:
            ret=1
           
    if ret==0:
        #Lista de Servidores desde pastebin
        #serv = urlopen(Request("https://pastebin.com/raw/a38wUnQf")).read().decode('utf-8')
        listaservere = urlopen(Request("https://pastebin.com/u/"+userp)).read().decode('utf-8')
        serv = re.findall('(?s)data-key=".+?".+?href="/(.+?)".+?</div', listaservere) 
        data=[]
        intento=1
        while data ==[] and intento<=10:
            servidores=re.findall('(?s)data-key=".+?".+?href="/(.+?)".+?</div', listaservere) 
            server = str(random.choice(servidores))
            
            mac,portal=mac_portal(server) 
            
            data,token=get_canales(mac,portal)
            if data!=[]:                
                nat=nat-1   
                myaddon.setSetting('nat',str(nat))
                myaddon.setSetting('cam',mac)
                myaddon.setSetting('revres',server)
                myaddon.setSetting('latrop',portal)
                myaddon.setSetting('fec',text_today)
                
                i=1
                pb=xbmcgui.DialogProgress()
                pb.create('Se incarca canalele','')
                total=len(data)
                for patron in sorted(data, key=lambda patron: patron[1]):         
                    titulo=str(patron[1]).replace('\\','').replace('\u00ed','i').replace('\u00eda','e').replace('\u00f1','ñ').replace('\u00fa','u').replace('\u00f3','o').replace('\u00c1','a').replace('\u00e9','e').replace('\u00d1','Ñ').replace('\u00e1','a')
                    ids=str(patron[0])
                    plugintools.add_item( action="lista2", title="[COLOR white]"+colorea(titulo)+"[/COLOR]", thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),plot=token,page=mac,extra=portal,url=ids,folder=True ) 
                    pb.update(int(100*i/total),str(100*i/total)+'% - Se incarca canalul '+str(titulo))
                    i+=1
                
                pb.close()
                
            else:
                intento=intento+1
    
        if intento==3 and data==[]:
            xbmcgui.Dialog().ok('MAXIMUM no. of searching attempts reached', 'Looks like no luck with this list, try your luck with another')
            xbmc.executebuiltin('Action.Back()')
            xbmc.executebuiltin('Content.Refresh()')
            return

    if ret==1:
        try:
            data,token=get_canales(mac,portal)
            for patron in sorted(data, key=lambda patron: patron[1]):         
                titulo=patron[1].replace('\u00ed','i').replace('\u00eda','e').replace('\u00f1','ñ').replace('\u00fa','u').replace('\u00f3','o').replace('\u00c1','a').replace('\u00e9','e').replace('\u00d1','Ñ').replace('\u00e1','a').replace('\\','') 
                ids=str(patron[0])
                
                plugintools.add_item( action="lista2", title="[COLOR white]"+colorea(titulo)+"[/COLOR]", thumbnail = params.get("thumbnail"), fanart= params.get("thumbnail"),plot=token,page=mac,extra=str(portal),url=ids,folder=True ) 
        except:
            xbmc.executebuiltin('Notification(Server down, it seems that this server is not operational ,8000')
            xbmc.executebuiltin('Action(Back)')
    
    if ret==-1:
        xbmc.executebuiltin('Action(Back)')

def quita_favoritos():
    favoritos = xbmc.translatePath('special://home/userdata/favourites.xml')    
    try:
        f = open(favoritos,'rw')
        favoritos1 = f.readlines()
        for line in favoritos1:
            if not 'portal.php?type=' in line:
                f.write(line)
        f.close()
    except:
        pass
        
def mac_portal(server):
    dhoy=date.today()
    text_today = dhoy.strftime("%Y%m%d")        
    hoy=int(text_today)    
    data=urlopen(Request("https://pastebin.com/raw/"+server)).read().decode('utf-8').lower()
    macx=re.findall('(00:1a:79:.*?........)', data)
    portal=str(re.findall('portal"(.*?)"', data)[0])
    mac =str(random.choice(macx))
    myaddon.setSetting('revres',str(server))
    myaddon.setSetting('cam',str(mac))
    myaddon.setSetting('latrop',str(portal))
    myaddon.setSetting('fec',str(text_today))
    return mac,portal

def get_canales(mac,portal):
    usuario = ''
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+str(mac)+"; stb_lang=es; timezone=Europe/spain"}
    url=portal+'portal.php?type=stb&action=handshake&JsHttpRequest=1-xml'
    try:
        token =requests.get(url, headers=headers).text
        token=re.findall('token":"(.*?)"',token)[0]
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
        url=portal+'portal.php?type=stb&action=get_profile&JsHttpRequest=1-xml'
        source=requests.get(url, headers=headers).text
        passs=re.findall('login":"","password":"(.*?)"',source )[0]
        typee=re.findall('"stb_type":"(.*?)"',source )[0]
        payload={"login":usuario,"password":passs,"stb_type":typee}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0","cookie": "mac="+mac+"; stb_lang=es; timezone=Europe/spain","Authorization": "Bearer "+token}
        url=portal+'portal.php?type=itv&action=get_genres&JsHttpRequest=1-xml'
        s = requests.Session()
        source=s.post(url, headers=headers,data=str(payload)).text        
        return plugintools.find_multiple_matches(source,'"id":"(\d+.*?)".*?"title":"(.*?)"'),token 
    except:
        
        return [],[]



        
##Radio code

def radio_pais(params):    
    url = 'https://instant.audio/'
    thumbnail = params.get("thumbnail")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    url = plugintools.find_multiple_matches(url,'(?s)<a href="(.*?)"><img class="flag-img" src="(.*?)" alt="(.*?)"')
    for patron in sorted(url,key=lambda patron: patron[2]): 
        titulo=patron[2]
        url=patron[0]
        foto=patron[1]
        plugintools.add_item(action = "radio_0" , title ="[COLOR white]"+titulo+"[/COLOR]", thumbnail = foto, fanart=foto , url =url, folder=True,  isPlayable = True )     

def radio_0(params):    
    url = params.get("url")
    thumbnail = params.get("thumbnail")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    xbmc.log('URL ' +str(url))
    urlx = plugintools.find_multiple_matches(url,'<ul id="radios"(.*?)<\/ul>')[0]
    xbmc.log('URLX: ' +str(urlx))
    matches = plugintools.find_multiple_matches(urlx,'<li class=".*?"><span.*?<a href="(.*?)" title="(.*?)"><img class="cover" src="(.*?)" alt=".*?" height=".*?" width=".*?"><\/a>')
    xbmc.log('matches: ' +str(matches))
    for patron in sorted(matches,key=lambda patron: patron[1]): 
        titulo=patron[1]
        foto=patron[2]
        url=patron[0]
        plugintools.add_item(action = "radio_1" , title ="[COLOR white]"+titulo+"[/COLOR]", thumbnail =foto, fanart =foto, url =url, folder=True,  isPlayable = True )     

def radio_1(params):  
    
    url = params.get("url")
    thumbnail = params.get("thumbnail")
    foto = params.get("fanart")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    cacho=url.split('/#')[1]
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    patron = plugintools.find_single_match(url,'<link rel="preload" href="(.*?)" as="fetch" type="application/json" crossorigin="anonymous">')
    cacho2 = patron.split('/streams/')[1].split('/')[0]
    url='https://api.webrad.io/data/streams/'+cacho2+'/'+cacho
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'"mediaType":"(.*?)","mime":".*?".*?,"url":"(.*?)"')
    for line in sorted(matches,key=lambda line: line[0]):
        url=str(line[1]).replace('\\','')
        titulo=str(line[0])
        if '.pls' in url or '.m3u' in url[-4:]:
            titulo='[COLOR gray]'+'Nu se poate reda' +' [/COLOR]sursa( '+titulo+' -> '+url+' )'
            plugintools.add_item(action = "radio_play" , title ="[COLOR white]"+titulo+"[/COLOR]", thumbnail = thumbnail,  url =url, folder=True,  isPlayable = False )
        elif titulo !='HTML':
            if ('.m3u8' in url.lower() or 'hls' in titulo.lower() or '.mp3' in url.lower() or 'redirect' in url.lower() or 'stream' in url.lower()) and not 'mp3.m3u' in url.lower() and not '.pls' in url.lower()  :
                titulo='[COLOR red]'+'Play [/COLOR]source( '+titulo+' )'
                plugintools.add_item(action = "radio_play" , title ="[COLOR white]"+titulo+"[/COLOR]", thumbnail = thumbnail,  url =url, folder=False,  isPlayable = True )
            else:    
                titulo=titulo + ' '+str(url)+' [COLOR magenta]Se incearca redarea.[/COLOR]'
                plugintools.add_item(action = "radio_play" , title ="[COLOR white]"+titulo+"[/COLOR]", thumbnail = thumbnail,  url =url, folder=False,  isPlayable = True )
    
            
def radio_play(params):            
    url = params.get("url")
    try:
        plugintools.play_resolved_url( url )    
    except:
        pass

def radio_play2(params):            
    url = params.get("url")
    response = urlopen(url, timeout = 5)
    content = response.read()
    if '.pls' in url[-4:]:
        matches = plugintools.find_multiple_matches(content,'File.*?=(.*?)\n')
    elif '.m3u' in url[-4:]:
        matches=content.split(" ")
    for url in matches:              
        plugintools.add_item(action ="" , title =url, thumbnail = params.get('thumbnail'),  url =url, folder=False,  isPlayable = False )


####
#Acestream test
def acemenu(params):
    plugintools.add_item(title='[COLOR gray]-======== ACESTREAM =========-[/COLOR]',folder=False, isPlayable=False)   
    plugintools.add_item(title='[COLOR blue]Necesita HORUS instalat si configurat[/COLOR]',folder=False, isPlayable=False)
    plugintools.add_item(title='[COLOR gray]-=========================-[/COLOR]',folder=False, isPlayable=False) 
    plugintools.add_item(action="listaace", title="AceStream Romania",thumbnail=thmb_ver_stb, fanart="",  url= "https://raw.githubusercontent.com/viorel013/acestream/Iptv/CANALE%20ROMANIA%20ace.m3u", folder= True )    
    plugintools.add_item(action="listaace2", title="AceStream World",thumbnail=thmb_ver_stb, fanart="",  url= "http://acetv.org/js/data.json", folder= True )    
    plugintools.add_item(action="playace", title="Play Acestream ID",thumbnail=thmb_ver_stb, fanart="",  url= "", folder= False, isPlayable = True )    

def listaace(params): 
    plugintools.log("macvod.listaace")
    thumbnail = params.get("thumbnail")    

    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')

    matches = plugintools.find_multiple_matches(url,'(#EXTINF:-1,[A-Z\d]+.*?[\n\r]+acestream://[^\n]+)')
    for generos in matches:  
        patron=plugintools.find_single_match(generos,'(?s)#EXTINF:-1,([A-Z\d]+.*?)[\n\r]+acestream://([^\n]+)')    
        url=patron[1].replace('\r','')
        titulo=patron[0]   
     
        plugintools.add_item(action="resolve_acestream",url=url,title=titulo,thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True )

def listaace2(params): 
    plugintools.log("macvod.listaace2")
    thumbnail = params.get("thumbnail")    

    
    url3 = params.get("url")
 
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url3, headers=request_headers)
    url = body.strip().decode('utf-8')

    matches = plugintools.find_multiple_matches(url,'("name":".+?","url":".+?")')
    for generos in matches:  
        patron=plugintools.find_single_match(generos,'(?s)"name":"(.+?)","url":"(.+?)"')    
        url=patron[1].replace('\r','')
        titulo=patron[0]   
     
        plugintools.add_item(action="resolve_acestream",url=url,title=titulo,thumbnail=thumbnail,fanart=thumbnail,folder=False,  isPlayable = True )

def playace(params):
    import resolveurl
    url=keyboard_input("", "Play Acestream ID:", False)
    title=params.get('title')
    thumb=params.get("thumbnail")
    finalurl="plugin://script.module.horus?action=play&id={}&title={}&iconimage={}".format(url,title,thumb)
    plugintools.play_resolved_url(finalurl)   

def resolve_acestream(params):
    import resolveurl
    finalurl="plugin://script.module.horus?action=play&id={}&title={}&iconimage={}".format(params.get('url'),params.get('title'),params.get("thumbnail"))
    plugintools.play_resolved_url(finalurl)    



###########
####Youtube
def log(message):
    xbmc.log(str(message),xbmc.LOGINFO)  
    
def youtube(params): 
    #plugintools.add_item(action="trendig_you",title="[COLOR gold]Trending[/COLOR]",thumbnail="https://i.imgur.com/dzbcKQ9.jpg",url= "https://www.youtube.com/feed/trending",fanart="",folder=True )
    plugintools.add_item(action="Buscar_search",title="[COLOR gold]Cauta YouTube[/COLOR]",thumbnail="https://i.imgur.com/V4gm6sn.jpg",url= "https://www.youtube.com/results?search_query=",fanart="",folder=True )         
    #plugintools.add_item(action="Emisiones_en_Directo_Recientes",title="[COLOR gold]Emisiones en Directo Recientes[/COLOR]",thumbnail="https://i.imgur.com/qE9UeYX.jpg",url= "https://www.youtube.com/watch?v=8nox3KEe6KI&list=PLU12uITxBEPEFpYLxV4XlCnR13q8nwVsv",fanart="",folder=True )    
    #plugintools.add_item(action="Proximas_en_Directo",title="[COLOR gold]Proximas Emisiones en Directo[/COLOR]",thumbnail="https://i.imgur.com/qE9UeYX.jpg",url= "https://www.youtube.com/watch?v=n93zCuT_0ZE&list=PLU12uITxBEPHMNFc5X1tQDy79xL29aV1E",fanart="",folder=True )  
    #plugintools.add_item(action="En_Directo",title="[COLOR gold]En Directo[/COLOR]",thumbnail="https://i.imgur.com/E8eFVJy.jpg",url= "https://www.youtube.com/playlist?list=PLU12uITxBEPFT10z9aLSQpg0YD4su7JDp",fanart="",folder=True )             
    #plugintools.add_item(action="GameYoutube_live",title="[COLOR gold]GameYoutube Live[/COLOR]",thumbnail="https://i.imgur.com/xJCLAyq.jpg",url= "https://www.youtube.com/gaming/games",fanart="",folder=True )   
    #plugintools.add_item(action="Noticias_directos",title="[COLOR gold]YouTube Live[/COLOR]",thumbnail="https://i.imgur.com/4Cw0fuc.jpg",url= "https://www.youtube.com/playlist?list=PLU12uITxBEPFy1nVJaDM-nGeB2q66Z4nP",fanart="",folder=True )     
    plugintools.add_item(action="Deportes_directos",title="[COLOR gold]YouTube Live[/COLOR]",thumbnail="https://i.imgur.com/E8eFVJy.jpg",url= "https://www.youtube.com/watch?v=ogkBwQGvoAs&list=PLU12uITxBEPFy1nVJaDM-nGeB2q66Z4nP",fanart="",folder=True )            
    plugintools.add_item(action="playyt",title="[COLOR gold]Play YouTube Video[/COLOR]",thumbnail="https://i.imgur.com/qE9UeYX.jpg",url= "",fanart="",folder= False, isPlayable = True )               

def trendig_you (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(https://i.ytimg.*?)\?sqp.*?"text":"(.*?)".*?videoId":"(.*?)"', url, re.DOTALL)
    log(url)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, fanart="", folder = False , isPlayable = True ) 

def GameYoutube_live (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)boxArt.*?thumbnails":\[{"url":"([^"]+).*?simpleText":"(.+?)".*?url":"(.+?)"', url, re.DOTALL)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "GameYoutube_live_1" , title = title, url = url , thumbnail = "https:" + thumb, fanart="",  folder = True )

def GameYoutube_live_1 (params):
    url = (  ( "https://www.youtube.com" + params . get("url") + "/live" ) )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(.*?)\?sqp.*?label":"(.*?)".*?"videoId":"(.*?)".*?', url, re.DOTALL)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, folder = False , fanart="",  isPlayable = True) 

def Emisiones_en_Directo_Recientes (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(https://i.ytimg.*?)\?sqp.*?"text":"(.*?)".*?videoId":"(.*?)"', url, re.DOTALL)
    log(matches)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, fanart="",  folder = False , isPlayable = True ) 

def Proximas_en_Directo (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(https://i.ytimg.*?)\?sqp.*?"text":"(.*?)".*?videoId":"(.*?)"', url, re.DOTALL)
    log(matches)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, folder = False , fanart="",  isPlayable = True ) 

def Noticias_directos (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(https://i.ytimg.*?)\?sqp.*?"text":"(.*?)".*?videoId":"(.*?)"', url, re.DOTALL)
    log(matches)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, fanart="", folder = False , isPlayable = True ) 

def Deportes_directos (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(https://i.ytimg.*?)\?sqp.*?"text":"(.*?)".*?videoId":"(.*?)"', url, re.DOTALL)
    log(matches)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, fanart="",  folder = False , isPlayable = True ) 

def Buscar_search (params): 
    url = params . get ( "url" ) + keyboard_input("", "Buscar:", False).replace(" ", "+")
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":202},{"url":"(.+?)".*?title.*?text":"(.+?)"}.*?"videoId":"(.*?)"', url, re.DOTALL)
    log(matches)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, fanart="", folder = False , isPlayable = True ) 

def En_Directo (params):
    url = params . get ( "url" )
    header = [ ]
    header . append ( [ "User-Agent" , "Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0" ] )
    read_url , read_header = plugintools . read_body_and_headers ( url , headers = header )
    url=read_url.strip().decode('utf-8')
 
    matches =  re.findall(r'(?s)height":138},{"url":"(https://i.ytimg.*?)\?sqp.*?"text":"(.*?)".*?videoId":"(.*?)"', url, re.DOTALL)
    log(matches)
    for thumb, title, url in matches:
        plugintools . add_item ( action = "resolve_resolveurl_youtube" , title = title, url = url , thumbnail = thumb, fanart="", folder = False , isPlayable = True ) 


def playyt(params):
    import resolveurl
    url=keyboard_input("", "Play YouTube ID:", False)
    finalurl = resolveurl . resolve ( "https://www.youtube.com/watch?v=" + url ) 
    plugintools . play_resolved_url ( finalurl )  
    log(finalurl)

def resolve_resolveurl_youtube ( params ) :
    import resolveurl
    finalurl = resolveurl . resolve ( "https://www.youtube.com/watch?v=" + params . get ( "url" ) ) 
    plugintools . play_resolved_url ( finalurl )  
    log(finalurl)  

run()