# -*- coding: utf-8 -*-
import os
import time
global progress
progress=''
global global_var,stop_all#global
global_var=[]
stop_all=0
from resources.modules.general import Addon
try:
    import xbmcaddon
    resuaddon=xbmcaddon.Addon('plugin.video.telemedia')
    listen_port=resuaddon.getSetting('port')
except:
    pass
from resources.modules import log
if Addon.getSetting("regex_mode")=='1':
    import regex  as re
else:
    import re
from resources.modules.general import clean_name,check_link,server_data,replaceHTMLCodes,domain_s,all_colors
type=['movie','tv','non_rd']

import urllib,logging,base64,json
color=all_colors[65]

from  resources.modules.client import get_html
from resources.modules.general import tmdb_key
def res_q(quality):
    f_q=' '
    if '4k' in quality.lower():
        quality='2160'
    if '2160' in quality:
      f_q='2160'
    elif '1080' in quality:
      f_q='1080'
    elif '720' in quality:
      f_q='720'
    elif '480' in quality:
      f_q='480'
   
    elif '360' in quality or 'sd' in quality.lower():
      f_q='360'
    elif '240' in quality:
      f_q='240'
    elif 'hd' in quality.lower() or 'hq' in quality.lower():
      f_q='480'
    return f_q
    
def fix_q_links(quality):
    f_q=100
    if '4k' in quality.lower():
        quality='2160'
    if '2160' in quality:
      f_q=1
    if '1080' in quality:
      f_q=2
    elif '720' in quality:
      f_q=3
    elif '480' in quality:
      f_q=4
    
    elif '360' in quality or 'sd' in quality.lower():
      f_q=6
    elif '240' in quality:
      f_q=7
    elif 'hd' in quality.lower() or 'hq' in quality.lower():
      f_q=8
    return f_q
def get_q(name):
    q=res_q(name)
    loc=fix_q_links(q)

    return q,loc
def search(tmdb,type,last_id_pre,search_entered_pre,icon_pre,fan_pre,season,episode,no_subs=0,original_title='',heb_name='',dont_return=True,manual=True):
    import random
    
   
    last_id=last_id_pre.split('$$$')[0]
    last_id_msg=last_id_pre.split('$$$')[1]
   
    
    
    query=search_entered_pre

    query=query.replace('%20',' ').replace('%27',"'").replace('%3a',":")
    
    
    num=random.randint(1,10001)
    all_links=[]
    if type=='all':
        filter_types=['searchMessagesFilterVideo','searchMessagesFilterDocument']
        for filter in filter_types:
        
            data={'type':'td_send',
                 'info':json.dumps({'@type': 'searchMessages', 'query': query,'offset_message_id':last_id,'offset_chat_id':last_id_msg,'filter':{'@type': filter},'limit':100, '@extra': num})
                 }
                 
            event=get_html('http://127.0.0.1:%s/'%listen_port,json=data).json()
        
            if 'messages' not in event:
                time.sleep(0.1)
                num=random.randint(1,10001)
                
                data={'type':'td_send',
                 'info':json.dumps({'@type': 'searchMessages', 'query': query,'offset_message_id':last_id,'offset_chat_id':last_id_msg,'limit':100, '@extra': num})
                 }
                event=get_html('http://127.0.0.1:%s/'%listen_port,json=data).json()
            
            counter_ph=0
            for items in event['messages']:  
     
                
                if 'document' in items['content']:
                    name=items['content']['document']['file_name']
                    if '.mkv' not in name and '.mp4' not in name and '.avi' not in name:
                        continue
                    size=items['content']['document']['document']['size']
                    f_size2=str(round(float(size)/(1024*1024*1024), 2))+' GB'
                    q,loc=get_q(name)
                    link_data={}
                    link_data['id']=str(items['content']['document']['document']['remote']['id'])
                    link_data['m_id']=items['id']
                    link_data['c_id']=items['chat_id']
                    f_lk=json.dumps(link_data)
                    all_links.append((name, f_lk,3,q,loc, icon_pre,fan_pre,f_size2,no_subs,tmdb,season,episode,original_title))
                    #addLink( name, str(items['content']['document']['document']['id']),3,False, icon_pre,fan_pre,f_size2,data=data,no_subs=no_subs,tmdb=tmdb,season=season,episode=episode,original_title=original_title)
                if 'video' in items['content']:
                        
                        name=items['content']['video']['file_name']
                        
                        size=items['content']['video']['video']['size']
                        f_size2=str(round(float(size)/(1024*1024*1024), 2))+' GB'
                      
                        q,loc=get_q(name)
                        link_data={}
                        link_data['id']=str(items['content']['video']['video']['remote']['id'])
                        link_data['m_id']=items['id']
                        link_data['c_id']=items['chat_id']
                        f_lk=json.dumps(link_data)
                        all_links.append(( name, f_lk,3,q,loc, icon_pre,fan_pre,f_size2,no_subs,tmdb,season,episode,original_title))
                        #addLink( name, str(items['content']['video']['video']['id']),3,False, icon_pre,fan_pre,f_size2,tmdb=tmdb,season=season,episode=episode,original_title=original_title)
                if 'caption' in items['content']:
                        txt_lines=items['content']['caption']['text'].split('\n')
                        all_l=[]
                        name=txt_lines[0]
                        rem_lines=[]
                        for lines in txt_lines:
                            if 'upfile' not in lines and 'drive.google' not in lines:
                              rem_lines.append(lines)
                              continue
                            
                                
                            all_l.append(lines)
                        if len(all_l)==0:
                            continue
                        icon=icon_pre
                        fan=fan_pre
                        
                               
                        q,loc=get_q(name)
                        all_links.append(('[COLOR lightgreen]'+ txt_lines[0]+'[/COLOR]' , '$$$'.join(all_l),9,q,loc, icon,fan,('\n'.join(rem_lines)).replace('\n\n','\n'),no_subs,tmdb,season,episode,original_title))
                        #addLink( '[COLOR lightgreen]'+ txt_lines[0]+'[/COLOR]' , '$$$'.join(all_l),9,False, icon,fan,('\n'.join(rem_lines)).replace('\n\n','\n'),no_subs=no_subs,tmdb=tmdb,season=season,episode=episode,original_title=original_title)
                elif 'web_page' in items['content']:
                    name=items['content']['web_page']['title']
                    link=items['content']['web_page']['url']
                    plot=items['content']['web_page']['description']['text']
       
                    if 'upfile' not in link and 'drive.google' not in link:
                          
                          continue
                    icon=icon_pre
                    fan=fan_pre
                    
                
                    q,loc=get_q(name)
                    
                    all_links.append(('[COLOR lightgreen]'+ name+'[/COLOR]', link,9,q,loc, icon,fan,plot.replace('\n\n','\n'),no_subs,tmdb,season,episode,original_title))
                    #addLink( '[COLOR lightgreen]'+ name+'[/COLOR]', link,9,False, icon,fan,plot.replace('\n\n','\n'),no_subs=no_subs,tmdb=tmdb,season=season,episode=episode,original_title=original_title)
                f_id=items['chat_id']

    return all_links
def clean_names(name):
    all_f=['ללא תרגום','ע"י י ב ג','@isrmovies','@kidsworldglobal','*','+','תרגום מובנה','תרגום מובנ','שליו_סרטים','720p','bdrip','hevc','10bit','hdrisrael','ציקו מדיה','הועלה ע"י','pdtv','hedubbed','ddp','h 264','truee','hevcaac','hdrip','gramovies','קבוצת ים','שלום מדיה','פופקורן טיים','www moridim tv','amsi77','isrteleg','יהודה','עי רוני','4k','mp3','brrip','ripac3','6ch','sub','biuray','hevcaac','ד ס','brripac3','brripaac','2ch','hebdub','smg','יוסי סרטים','עי יוסי','כל המדיה','hd tv','אלי ה ס','נתן ים','dvdrip','Segment 1','Segment 2','ISrTeLeG','עולם הסדרות','הועלה ע"י','שבי מדיה','צפייה ישירה','🎬','איכות',':','🇮🇱','לוי מדיה','#','Amsi77','קינג סרט','קרדיט','כל סרט','ᴴᴰ','סרטים וסדרות בדרייב','איילת השחר','anvip','bluray','web','dl','cam','CAM','h264','NoTime',' ק ס ','ק ס ',' ח ס ','ח ס ','גל שביט',' @cartoon join',' ז מ','ז.מ','xvid','EVO1','EVO2','RIp','נועםם','BDRiP','x265','HeBDub',' DivX',' WS','XViD','(',')','אלירן','WEB','H264',' Br','DVDRiP','HEBDUB',' BRrip','DVDRIP','עי יוסי','נתי מ ','ע"י sagi','BDRIP','נתי ','עי אורי המלך','לולו ','כל סרט ','כ.ס ','כ ס ','נמ ','H 264','HEVC','  ','לעברית','גזלן','מדיה סנטר','סרט']
    
    name=name.replace('dragonmedia','').replace('BluRay','').replace('BLURAY','').replace('הועלה_ע"י_יהודה_בן_גביר','').replace('ע"י_יהודה_בן_גביר','').replace('720_P','').replace('720P','')
    
  
    name=name.replace(' ','.').replace('_','.').replace('-','.').replace('%20',' ').replace('5.1','').replace('AAC','').replace('2CH','').replace('.mp4','').replace('.avi','').replace('.mkv','').replace('מדובב','').replace('גוזלן','').replace('BDRip','').replace('BRRip','')

    name=name.replace('❤','').replace('עולם הסדרות','').replace('טלגרמדיה','').replace('פופקורן טיים','').replace('לוי מדיה','').replace('BluRay','').replace('ח1','').replace('ח2','').replace('נתי.מדיה','').replace('נ.מ.','').replace('..','.').replace('.',' ').replace('WEB-DL','').replace('WEB DL','').replace('נ מדיה','')

    name=name.replace('HDTV','').replace('DVDRip','').replace('WEBRip','')

    name=name.replace('דב סרטים','').replace('לולו סרטים','').replace('דב ס','').replace('()','').replace('חן סרטים','').replace('ק סרטים','').replace('חננאל סרטים','').replace('יוסי סרטים','').replace('נריה סרטים','').replace('HebDub','').replace('NF','').replace('HDCAM','').replace('@yosichen','')

    name=name.replace('BIuRay','').replace('x264','').replace('Hebdub','').replace('XviD','')

    name=name.replace('Silver007','').replace('Etamar','').replace('iSrael','').replace('DVDsot','').replace('אלי ה סרטים','').replace('PCD1','').replace('PCD2','').replace('CD1','').replace('CD2','').replace('CD3','').replace('Gramovies','').replace('BORip','').replace('200P','').replace('מס1','1').replace('מס2','2').replace('מס3','3').replace('מס4','4').replace('מס 3','3').replace('מס 2','2').replace('מס 1','1')

    name=name.replace('900p','').replace('PDTV','').replace('VHSRip','').replace('UPLOAD','').replace('TVRip','').replace('Heb Dub','').replace('MP3','').replace('AC3','').replace('SMG','').replace('Rip','').replace('6CH','').replace('XVID','')

    name=name.replace('HD','').replace('WEBDL','').replace('DVDrip','')
    
    name=name.replace('מצוירים','').replace(' ק ס ','').replace(' ח ס ','').replace('ת מ ','').replace('חננאל ס','').replace('Empire סרטים','').replace('heb dub','')
    name=name.replace('2נתי','2').replace('1נתי','1').replace('זירה מדיה','')
    name=name.replace('עי ליאת','').replace('עי אביאל','').replace('דניבר סרטים','').replace('ANVIP','').replace('מדיה VOD ','').replace('WEBRip_','').replace('@cartoon join','')
    name=name.replace('Madbadger','').replace('cd1','').replace('cd2','').replace('cd3','').replace('cd4','').replace('hdtv','').replace('bdrip','').replace('webrip','').replace('MkvCage','').replace('RickyChannel','')
   
    for items in all_f:
        
       
        name=name.replace(items,'')
    return name
def get_links(tv_movie,original_title,season_n,episode_n,season,episode,show_original_year,id):
    global global_var,stop_all,progress
    
    if 1:#try:


        tmdbKey='b370b60447737762ca38457bd77579b3'
        if tv_movie=='tv':
      
           url2=f'https://api.themoviedb.org/3/tv/%s?api_key={tmdbKey}&append_to_response=external_ids,alternative_titles&language=he'%(id)
           n_value='name'
        else:
           
           url2=f'https://api.themoviedb.org/3/movie/%s?api_key={tmdbKey}&append_to_response=external_ids,alternative_titles&language=he'%(id)
           n_value='title'
        html=get_html(url2,timeout=10).json()

        try:
            
            
            name=html[n_value]
        except:
            name=original_title
         
        heb_name=name
        
        new_heb_name=''
        
        if 'alternative_titles' in html:
            
            if 'results' in html['alternative_titles']:
                for items in html['alternative_titles']['results']:
                    
                    if items['iso_3166_1']=='IL':
                        
                        new_heb_name=items['title']
            if 'titles' in html['alternative_titles']:
                for items in html['alternative_titles']['titles']:
                    
                    if items['iso_3166_1']=='IL':
                        
                        new_heb_name=items['title']
        if (name==original_title) and new_heb_name!='':
                    heb_name=new_heb_name
        
        o_name=name
        progress='Start'
        f_all_links=[]
        start_time=time.time()
        all_names=[]

        if tv_movie=='movie':
            all_links=[]
        
            all_links=search(id,'all','0$$$0',name,'','',season,episode,no_subs=0,original_title=original_title,dont_return=False,manual=False)
            log.warning(name)
            log.warning(f'Len_result:{len(all_links)}')
            all_links=all_links+search(id,'all','0$$$0',original_title,'','',season,episode,original_title=original_title,dont_return=False,manual=False)
            log.warning(original_title)
            log.warning(f'Len_result:{len(all_links)}')
            all_links=sorted(all_links, key=lambda x: x[4], reverse=False)
           
            for  name, link,mode,q,loc, icon,fan,plot,no_subs,tmdb,season,episode,original_title in all_links:
                if base64.b64encode(name.encode("utf-8")).decode("utf-8") in all_names:
                    continue
                
                all_names.append(base64.b64encode(name.encode("utf-8")).decode("utf-8"))
                if 'upfile' not in link and 'drive.google' not in link:
                    plot=plot
                else:
                    plot=plot
                try:
                     o_size=plot
                     
                     plot=float(o_size.replace('GB','').replace('MB','').replace(",",'').strip())
                     if 'MB' in o_size:
                       plot=plot/1000
                except Exception as e:
                    
                    plot=0
                name=clean_names(name)
                f_all_links.append((name ,'Direct_link$$$TELE%%%'+link,plot,q))
                global_var=f_all_links
        else:
       
            c_original=original_title.replace('%20','.').replace(' ','.').replace('%27',"'").replace("'","").replace('%3a',":")
            options=[heb_name+' ע%s פ%s'%(season,episode),heb_name+' ע%sפ%s'%(season,episode),heb_name+' עונה %s פרק %s'%(season,episode),c_original+'.S%sE%s'%(season_n,episode_n),c_original+'.S%sE%s'%(season,episode),c_original.replace('&','and')+'.S%sE%s'%(season,episode),c_original.replace('&','and')+'.S%sE%s'%(season_n,episode_n)]
            #if 'the' in original_title.lower():
            #    options.append(c_original.replace('The','').replace('the','')+'.S%sE%s'%(season_n,episode_n))
            options2=[' ע%s פ%s'%(season,episode),'ע%s.פ%s'%(season,episode),' ע%sפ%s'%(season,episode),' עונה %s פרק %s'%(season,episode),'.S%sE%s'%(season_n,episode_n),'.S%sE%s'%(season,episode)]
            all_links=[]
   
            try:
                for items in options:
                    
                    all_links=all_links+search(id,'all','0$$$0',items,'','',season,episode,no_subs=1,original_title=original_title,heb_name=name,dont_return=False,manual=False)
            except Exception as e:
                log.warning('Error telemedia:'+str(e))
                pass
            
            exclude=[]
     
            for  name, link,mode,q,loc, icon,fan,plot,no_subs,tmdb,season,episode,original_title in all_links:
                ok=False

 
                if base64.b64encode(name.encode("utf-8")).decode("utf-8") in all_names:
                    continue
                
                all_names.append(base64.b64encode(name.encode("utf-8")).decode("utf-8"))
                for items in options2:
                    t_items=items.replace(' ','.').replace(':','').replace("'","").replace('-','.').replace('[','').replace(']','').replace('..','.').lower()
                    t_name=name.replace('"',"").replace('  ',' ').lower().replace('-','.').replace(' ','.').replace('[','').replace(']','').replace('_','.').replace(':','').replace("'","").replace('..','.')
                    t_items2=c_original.replace(' ','.').replace(':','').replace("'","").replace('-','.').replace('[','').replace(']','').replace('..','.').lower()
         
                    if (t_items+'.'  in t_name+'.') or (t_items+' '  in t_name+' ') or (t_items+'_'  in t_name+'_') or (t_items.replace('.','_')+'_'  in t_name.replace('.','_')+'_') or (t_items.replace('.','-')+'_'  in t_name.replace('.','-')+'_'):
                       if (o_name in name) or (t_items2 in t_name):
                        ok=True
                        break

                if not ok:
                    color='red'
                    exclude.append((name, link,mode,q,loc, icon,fan,plot,no_subs,tmdb,season,episode,original_title))
                else:
                     color='white'
                if 'upfile' not in link and 'drive.google' not in link:
                
                    plot=plot
                else:
                    plot=plot
                try:
                     o_size=plot
                     
                     plot=float(o_size.replace('GB','').replace('MB','').replace(",",'').strip())
                     if 'MB' in o_size:
                       plot=plot/1000
                except Exception as e:
                    
                    plot=0
                
                name=clean_names(name)
                
                f_all_links.append((name ,'Direct_link$$$TELE%%%'+link,plot,q))
                global_var=f_all_links
        elapsed_time = time.time() - start_time
        progress=' Done '+time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
      
        return global_var
        
    
    