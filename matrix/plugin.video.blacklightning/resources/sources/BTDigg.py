# -*- coding: utf-8 -*-
import re
import time
from  resources.modules.client import get_html
global global_var,stop_all#global
global_var=[]
stop_all=0

 
from resources.modules.general import clean_name,check_link,server_data,replaceHTMLCodes,domain_s,similar,all_colors,base_header
from  resources.modules import cache
try:
    from resources.modules.general import Addon
except:
  import Addon
type=['movie','tv','torrent']

import urllib,logging,base64,json
from resources.modules import log

def get_links(tv_movie,original_title,season_n,episode_n,season,episode,show_original_year,id):
    global global_var,stop_all

   
    
  
    
    headers = {
        'authority': 'btdig.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'max-age=0',
        'dnt': '1',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    params = {
        'q': 'rampage 2018',
        'p': '0',
        'order': '0',
    }
    all_links=[]
    if (Addon.getSetting('torrents')=='true' and use_debrid==False):
        return  []
    if tv_movie=='movie':
     search_url=[('%s+%s'%(clean_name(original_title,1).replace(' ','+'),show_original_year)).lower()]
     
    else:
     
      if Addon.getSetting('debrid_select')=='0' :
        search_url=[('%s+s%se%s'%(clean_name(original_title,1).replace(' ','+'),season_n,episode_n)).lower(),('%s-s%s'%(clean_name(original_title,1).replace(' ','-'),season_n)).lower(),('%s-season-%s'%(clean_name(original_title,1).replace(' ','-'),season)).lower()]
      else:
        search_url=[('%s+s%se%s'%(clean_name(original_title,1).replace(' ','+'),season_n,episode_n)).lower()]
    
    div=1024*1024*1024
    
    regex='class="torrent_size".+?>(.+?)<.+?"magnet(.+?)"'
    regex1=re.compile(regex,re.DOTALL)
    regex='dn\=(.+?)\&'
    
    regex2=re.compile(regex)
    for itt in search_url:
      for page in range(0,3):
        log.warning('https://btdig.com/search?q=%s&p=%s&order=0'%(itt,page))
                    
        x=get_html('https://btdig.com/search?q=%s&p=%s&order=0'%(itt,page),headers=headers).content()
        log.warning(x)
        regex='class="torrent_size".+?>(.+?)<.+?"magnet(.+?)"'
        
        m=regex1.findall(x)
        log.warning(m)
        for size,link in m:
                     regex='dn\=(.+?)\&'
                     try:
                        title=regex2.findall(link)[0]
                     except:
                        title=clean_name(original_title,1)
                     
                     title=title.replace('+','.')
                    
                     if stop_all==1:
                        break
                     
                    
                     if '4k' in title:
                              res='2160'
                     elif '2160' in title:
                          res='2160'
                     elif '1080' in title:
                          res='1080'
                     elif '720' in title:
                          res='720'
                     elif '480' in title:
                          res='480'
                     elif '360' in title:
                          res='360'
                     else:
                          res='HD'
                    
                    
                   
                     try:
                         o_size=size
                         
                         size=float(o_size.replace('GB','').replace('MB','').replace(",",'').strip())
                         if 'MB' in o_size:
                           size=size/1000
                     except Exception as e:
                        
                        size=0
                     max_size=int(Addon.getSetting("size_limit"))
              
                     if size<max_size:
                  
                       all_links.append((title,'magnet'+link,str(size),res))
                   
                       global_var=all_links
    return global_var
        
    