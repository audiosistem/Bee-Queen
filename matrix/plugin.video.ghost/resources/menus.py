import time,xbmcplugin,os,json,sys

from resources.modules.public import *
global CLIENT_ID,CLIENT_SECRET

#trakt api keys
CLIENT_ID = "a4e716b4b22b62e59b9e09454435c8710b650b3143dcce553d252b6a66ba60c8"
CLIENT_SECRET = "c6d9aba72214a1ca3c6d45d0351e59f21bbe43df9bbac7c5b740089379f8c5cd"


addonPath = xbmc_tranlate_path(Addon.getAddonInfo("path"))
if Addon.getSetting("theme")=='0':
    art_folder='artwork'
    
elif Addon.getSetting("theme")=='1':
    art_folder='artwork_keshav'
elif Addon.getSetting("theme")=='2':
    art_folder='artwork_shinobi'
elif Addon.getSetting("theme")=='3':
    art_folder='artwork_sonic'
elif Addon.getSetting("theme")=='4':
    art_folder='artwork_bob'
    
BASE_LOGO=os.path.join(addonPath, 'resources', art_folder+'/')
file = open(os.path.join(BASE_LOGO, 'fanart.json'), 'r') 
fans= file.read()
file.close()
fanarts=json.loads(fans)
all_fanarts={}
for items in fanarts:
    if 'http' in fanarts[items]:
        all_fanarts[items]=fanarts[items]
    else:
        all_fanarts[items]=(os.path.join(BASE_LOGO, fanarts[items]))
    


def main_menu():


    
    all_d=[]
   
    if Addon.getSetting('movie_world')=='true':
        aa=addDir3(Addon.getLocalizedString(32024),'www',2,BASE_LOGO+'ghost1.png',all_fanarts['32024'],'Movies')
        all_d.append(aa)
    if Addon.getSetting('tv_world')=='true':
        aa=addDir3(Addon.getLocalizedString(32025),'www',3,BASE_LOGO+'ghost1.png',all_fanarts['32025'],'TV')
        all_d.append(aa)
	#place your Jen playlist here:
    #dulpicate this line with your address
    aa=addDir3('Live TV','https://thechains24.com/PornKing/New%20Live%20tv%20Ghost/Entairt.xml',189,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/fanart.jpg','Live TV')
    all_d.append(aa)
    if Addon.getSetting('trakt_world')=='true':
        aa=addDir3(Addon.getLocalizedString(32026),'www',21,BASE_LOGO+'ghost1.png',all_fanarts['32026'],'No account needed)')
        all_d.append(aa)
    if Addon.getSetting('trakt')=='true':
        aa=addDir3(Addon.getLocalizedString(32027),'www',114,BASE_LOGO+'ghost1.png',all_fanarts['32027'],'TV')
        all_d.append(aa)
    if Addon.getSetting('search')=='true':
        aa=addDir3(Addon.getLocalizedString(32020),'www',5,BASE_LOGO+'ghost1.png',all_fanarts['32020'],'Search')
        all_d.append(aa)
    if Addon.getSetting('search_history')=='true':
        aa=addDir3(Addon.getLocalizedString(32021),'both',143,BASE_LOGO+'ghost1.png',all_fanarts['32021'],'TMDB')
        all_d.append(aa)
    if Addon.getSetting('whats_new')=='true':
        aa=addNolink(Addon.getLocalizedString(32028) , 'www',149,False,fanart=all_fanarts['32028'], iconimage=BASE_LOGO+'ghost1.png',plot='',dont_place=True)
        all_d.append(aa)
    if Addon.getSetting('settings')=='true':
        aa=addNolink( Addon.getLocalizedString(32029), 'www',151,False,fanart=all_fanarts['32029'], iconimage=BASE_LOGO+'ghost1.png',plot='',dont_place=True)
        all_d.append(aa)
    if Addon.getSetting('resume_watching')=='true':		
        aa=addDir3(Addon.getLocalizedString(32030),'both',158,BASE_LOGO+'ghost1.png',all_fanarts['32030'],'TMDB')
        all_d.append(aa)
    if Addon.getSetting('debrid_use_rd')=='true':
        if Addon.getSetting('my_rd_history')=='true':
            aa=addDir3(Addon.getLocalizedString(32031),'1',168,BASE_LOGO+'rd_ghost1.png',all_fanarts['32031'],'TMDB')
            all_d.append(aa)
        if Addon.getSetting('rd_Torrents')=='true':
            aa=addDir3(Addon.getLocalizedString(32032),'1',169,BASE_LOGO+'ghost1.png',all_fanarts['32032'],'TMDB')
            all_d.append(aa)
    if Addon.getSetting('actor')=='true':
        aa=addDir3(Addon.getLocalizedString(32033),'www',72,BASE_LOGO+'ghost1.png',all_fanarts['32033'],'Actor')
        all_d.append(aa)
    if Addon.getSetting('scraper_check')=='true':
        aa=addDir3( Addon.getLocalizedString(32034), 'www',172,BASE_LOGO+'ghost1.png',all_fanarts['32034'],'Test')
        
        all_d.append(aa)
    
    if Addon.getSetting('debug')=='true':
        aa=addDir3( 'Unit tests', 'www',181,'https://lh3.googleusercontent.com/proxy/Ia9aOfcgtzofMb0urCAs8NV-4RRhcIVST-Gqx9GI9RLsx7IJe_5jBqjfdsJcOO3QIV3TT-uiF2nKmyYCX0vj5UPR4iW1iHXgZylE8N8wyNgRLw','https://i.ytimg.com/vi/3wLqsRLvV-c/maxresdefault.jpg','Test')
        
        all_d.append(aa)
    if Addon.getSetting('doodstream')=='true':
        aa=addDir3( "My Doodsteam Files", '1',202,BASE_LOGO+'ghost1.png',all_fanarts['32034'],'Test',id="")
        
        all_d.append(aa)
    found=False
    for i in range(0,10):
        if Addon.getSetting('imdb_user_'+str(i))!='':
            found=True
            break
    if found:
        aa=addDir3(Addon.getLocalizedString(32309),'www',183,BASE_LOGO+'ghost1.png',all_fanarts['32309'],'Imdb')
        all_d.append(aa)
    
    
    if Addon.getSetting("stop_where")=='0':
            xbmcplugin .addDirectoryItems(int(sys.argv[1]),all_d,len(all_d))
    
    
def movie_world():
    all_d=[]
    try:
        from sqlite3 import dbapi2 as database
    except:
        from pysqlite2 import dbapi2 as database
    cacheFile=os.path.join(user_dataDir,'database.db')
    dbcon = database.connect(cacheFile)
    dbcur = dbcon.cursor()
    dbcur.execute("CREATE TABLE IF NOT EXISTS %s ( ""name TEXT, ""url TEXT, ""tv_movie TEXT);" % 'add_cat')
    
   
    dbcon.commit()
    dbcur.execute("SELECT * FROM add_cat")
    match = dbcur.fetchall()
    dbcur.close()
    dbcon.close()
    
    all_s_strings=[]
    for name,url,tv_movie in match:
        
        if (tv_movie=='movie'):
           aa=addDir3('[COLOR lightblue][B]'+name+'[/B][/COLOR]',url,14,BASE_LOGO+'ghost1.png',all_fanarts['32295'],'Tmdb_custom')
           all_d.append(aa)
    #place your Jen playlist here:
    #dulpicate this line with your address
    aa=addDir3('Free','https://thechains24.com/PornKing/New%20Live%20tv%20Ghost/1clicknew.xml',189,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/Builds/fanart.jpg','Free')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32295),f'https://api.themoviedb.org/3/movie/now_playing?api_key={tmdb_key}&language=%s&page=1'%lang,14,BASE_LOGO+'ghost1.png',all_fanarts['32295'],'Tmdb')
    all_d.append(aa)
    'Popular Movies'
    aa=addDir3(Addon.getLocalizedString(32036),f'https://api.themoviedb.org/3/trending/movie/day?api_key={tmdb_key}&language=%s&page=1'%lang,14,BASE_LOGO+'ghost1.png',all_fanarts['32036'],'Tmdb')
    all_d.append(aa)
    'Released Movies'
    aa=addDir3('Released Movies',f'https://api.themoviedb.org/3/movie/popular?api_key={tmdb_key}&language=%s&with_release_type=4&page=1'%lang,14,BASE_LOGO+'ghost1.png',all_fanarts['32036'],'Tmdb')
    all_d.append(aa)
	
    aa=addDir3('Popular Lists','https://thechains24.com/GREENHAT/Popular%20Trakt%20Lists.xml',189,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/fanart.jpg','Popular Lists')
    all_d.append(aa)
    
    #Genre
    aa=addDir3(Addon.getLocalizedString(32038),f'https://api.themoviedb.org/3/genre/movie/list?api_key={tmdb_key}&language=%s&page=1'%lang,18,BASE_LOGO+'ghost1.png',all_fanarts['32038'],'Tmdb')
    all_d.append(aa)
    #Years
    aa=addDir3(Addon.getLocalizedString(32039),'movie_years&page=1',14,BASE_LOGO+'ghost1.png',all_fanarts['32039'],'Tmdb')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32040),'movie_years&page=1',112,BASE_LOGO+'ghost1.png',all_fanarts['32040'],'Tmdb')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32041),'advance_movie',14,BASE_LOGO+'ghost1.png',all_fanarts['32041'],'Advance Content selection')
    all_d.append(aa)
    #Search movie
    aa=addDir3(Addon.getLocalizedString(32042),f'https://api.themoviedb.org/3/search/movie?api_key={tmdb_key}&query=%s&language={lang}&append_to_response=origin_country&page=1'.format(lang),14,BASE_LOGO+'ghost1.png',all_fanarts['32042'],'Tmdb')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32043),'movie',143,BASE_LOGO+'ghost1.png',all_fanarts['32043'],'TMDB')
    all_d.append(aa)
    try:
        from sqlite3 import dbapi2 as database
    except:
        from pysqlite2 import dbapi2 as database
    cacheFile=os.path.join(user_dataDir,'database.db')
    dbcon = database.connect(cacheFile)
    dbcur = dbcon.cursor()
    
    table_name='lastlinkmovie'
    
    dbcur.execute("CREATE TABLE IF NOT EXISTS %s ( ""o_name TEXT,""name TEXT, ""url TEXT, ""iconimage TEXT, ""fanart TEXT,""description TEXT,""data TEXT,""season TEXT,""episode TEXT,""original_title TEXT,""saved_name TEXT,""heb_name TEXT,""show_original_year TEXT,""eng_name TEXT,""isr TEXT,""prev_name TEXT,""id TEXT);"%table_name)
    
    dbcur.execute("SELECT * FROM lastlinkmovie WHERE o_name='f_name'")

    match = dbcur.fetchone()
    dbcon.commit()
    
    dbcur.close()
    dbcon.close()
    
    if match!=None:
       f_name,name,url,iconimage,fanart,description,data,season,episode,original_title,saved_name,heb_name,show_original_year,eng_name,isr,prev_name,id=match
       try:
           if url!=' ':
             if 'http' not  in url:
           
               url=base64.b64decode(url)
              
             aa=addLink('[I]%s[/I]'%Addon.getLocalizedString(32022), url,6,False,iconimage,fanart,description,data=show_original_year,prev_name=name,original_title=original_title,season=season,episode=episode,tmdb=id,year=show_original_year,place_control=True)
             all_d.append(aa)
       except  Exception as e:
         log.warning(e)
         pass
    aa=addDir3(Addon.getLocalizedString(32044),'movie',145,BASE_LOGO+'ghost1.png',all_fanarts['32044'],'History')
    
    aa=addDir3(Addon.getLocalizedString(32313),'0',187,BASE_LOGO+'ghost1.png',all_fanarts['32313'],'keywords')
    
    all_d.append(aa)
    #place your Jen playlist here:
    #dulpicate this line with your address
    #aa=addDir3('Name', 'Your Jen Address',189,'Iconimage','fanart','Description',search_db='Your Search db Address')
    #all_d.append(aa)
    
    xbmcplugin .addDirectoryItems(int(sys.argv[1]),all_d,len(all_d))

def movie_prodiction():
    all_d=[]
    if Addon.getSetting("order_networks")=='0':
        order_by='popularity.desc'
    elif Addon.getSetting("order_networks")=='2':
        order_by='vote_average.desc'
    elif Addon.getSetting("order_networks")=='1':
        order_by='first_air_date.desc'
    
    
    aa=addDir3('[COLOR gold]Marvel[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=7505&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Marvel')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]DC Studios[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=9993&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','DC Studios')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Lucasfilm[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=1&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Lucasfilm')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Warner Bros.[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=174&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','SyFy')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Walt Disney Pictures[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=2&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Walt Disney Pictures')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Pixar[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=3&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Pixar')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Paramount[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=4&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Paramount')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Columbia Pictures[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=5&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Columbia Pictures')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]DreamWorks[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=7&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','DreamWorks')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Miramax[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=14&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Miramax')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]20th Century Fox[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=25&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','20th Century Fox')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Sony Pictures[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=34&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Sony Pictures')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Lions Gate Films[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=35&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Lions Gate Films')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Orion Pictures[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=41&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Lions Gate Films')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]MGM[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=21&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','MGM')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]New Line Cinema[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=12&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','New Line Cinema')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Gracie Films[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=18&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Gracie Films')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Imagine Entertainment[/COLOR]',f'https://api.themoviedb.org/3/discover/movie?api_key={tmdb_key}&with_companies=23&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Imagine Entertainment')
    all_d.append(aa)
    xbmcplugin .addDirectoryItems(int(sys.argv[1]),all_d,len(all_d))
def main_trakt():
   all_d=[]
   aa=addDir3(Addon.getLocalizedString(32048),'movie?limit=40&page=1',116,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Lists')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32049),'tv?limit=40&page=1',116,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Lists')
   all_d.append(aa)
   import datetime
   current_date = adjusted_datetime()
   start = (current_date - datetime.timedelta(days=14)).strftime('%Y-%m-%d')
   finish = 14
        
   aa=addDir3(Addon.getLocalizedString(32050),'calendars/my/shows/%s/%s?limit=40&page=1'%(start,finish),117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Lists')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32051),'users/me/watched/shows?extended=full&limit=40&page=1',115,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Progress')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32052),'sync/watchlist/episodes?extended=full&limit=40&page=1',115,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Episodes')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32053),'users/me/watchlist/episodes?extended=full&limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Series')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32054),'users/me/collection/shows?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','TV')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32055),'users/me/watchlist/shows?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Shows')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32056),'recommendations/shows?limit=40&ignore_collected=true&page=1',166,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Movies')
   all_d.append(aa)
   
   aa=addDir3(Addon.getLocalizedString(32057),'users/me/watchlist/movies?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Movies')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32058),'recommendations/movies?limit=40&ignore_collected=true&page=1',166,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Movies')
   all_d.append(aa)
   
   aa=addDir3(Addon.getLocalizedString(32059),'users/me/watched/movies?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Watched')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32060),'users/me/watched/shows?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Watched shows')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32061),'users/me/collection/movies?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','collection')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32062),'users/likes/lists?limit=40&page=1',118,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Liked lists')
   all_d.append(aa)
   aa=addDir3(Addon.getLocalizedString(32063),'sync/playback/movies?limit=40&page=1',117,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Liked lists')
   all_d.append(aa)
   
   aa=addDir3(Addon.getLocalizedString(32064),'sync/playback/episodes?limit=40&page=1',164,BASE_LOGO+'ghost1.png','https://thechains24.com/PornKing/fanart.jpg','Liked lists')
   all_d.append(aa)
   
   xbmcplugin .addDirectoryItems(int(sys.argv[1]),all_d,len(all_d))

def tv_show_menu():
    all_d=[]
    try:
        from sqlite3 import dbapi2 as database
    except:
        from pysqlite2 import dbapi2 as database
    cacheFile=os.path.join(user_dataDir,'database.db')
    dbcon = database.connect(cacheFile)
    dbcur = dbcon.cursor()
    dbcur.execute("CREATE TABLE IF NOT EXISTS %s ( ""name TEXT, ""url TEXT, ""tv_movie TEXT);" % 'add_cat')
    
   
    dbcon.commit()
    dbcur.execute("SELECT * FROM add_cat")
    match = dbcur.fetchall()
    dbcur.close()
    dbcon.close()
    
    all_s_strings=[]
    for name,url,tv_movie in match:
        
        if (tv_movie=='tv'):
           aa=addDir3('[COLOR lightblue][B]'+name+'[/B][/COLOR]',url,14,BASE_LOGO+'ghost1.png',all_fanarts['32295'],'Tmdb_custom')
           all_d.append(aa)
    import datetime
    now = datetime.datetime.now()
    aa=addDir3(Addon.getLocalizedString(32023),'tv',145,BASE_LOGO+'ghost1.png',all_fanarts['32023'],'History')
    #Popular
    aa=addDir3(Addon.getLocalizedString(32012),f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&language={lang}&sort_by=popularity.desc&include_null_first_air_dates=false&with_original_language=en&page=1',14,BASE_LOGO+'ghost1.png',all_fanarts['32013'],Addon.getLocalizedString(32012))
    all_d.append(aa)
	
    aa=addDir3(Addon.getLocalizedString(32015),f'https://api.themoviedb.org/3/trending/tv/week?api_key={tmdb_key}&language=%s&page=1'%lang,14,BASE_LOGO+'ghost1.png',all_fanarts['32015'],'TMDB')
    all_d.append(aa)
     
    aa=addDir3(Addon.getLocalizedString(32014),f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&language={lang}&sort_by=popularity.desc&first_air_date_year='+str(now.year)+'&with_original_language=en&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/Builds/fanart.jpg','New Tv shows')
    all_d.append(aa)
	
    #Genre
    aa=addDir3(Addon.getLocalizedString(32016),f'https://api.themoviedb.org/3/genre/tv/list?api_key={tmdb_key}&language=%s&page=1'%lang,18,BASE_LOGO+'ghost1.png',all_fanarts['32016'],'TMDB')
    all_d.append(aa)
    #Years
    aa=addDir3(Addon.getLocalizedString(32017),'tv_years&page=1',14,BASE_LOGO+'ghost1.png',all_fanarts['32017'],'TMDB')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32018),'tv_years&page=1',101,BASE_LOGO+'ghost1.png',all_fanarts['32018'],'TMDB')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32019),'advance_tv',14,BASE_LOGO+'ghost1.png',all_fanarts['32019'],'Advance Content selection')
    
    all_d.append(aa)
    #Search tv
    aa=addDir3(Addon.getLocalizedString(32020),f'https://api.themoviedb.org/3/search/tv?api_key={tmdb_key}&query=%s&language={lang}&page=1'.format(lang),14,BASE_LOGO+'ghost1.png',all_fanarts['32020'],'TMDB')
    all_d.append(aa)
    aa=addDir3(Addon.getLocalizedString(32021),'tv',143,BASE_LOGO+'ghost1.png',all_fanarts['32021'],'TMDB')
    all_d.append(aa)
    
    try:
        from sqlite3 import dbapi2 as database
    except:
        from pysqlite2 import dbapi2 as database
    cacheFile=os.path.join(user_dataDir,'database.db')
    dbcon = database.connect(cacheFile)
    dbcur = dbcon.cursor()
    
    table_name='lastlinktv'
    
    dbcur.execute("CREATE TABLE IF NOT EXISTS %s ( ""o_name TEXT,""name TEXT, ""url TEXT, ""iconimage TEXT, ""fanart TEXT,""description TEXT,""data TEXT,""season TEXT,""episode TEXT,""original_title TEXT,""saved_name TEXT,""heb_name TEXT,""show_original_year TEXT,""eng_name TEXT,""isr TEXT,""prev_name TEXT,""id TEXT);"%table_name)
    
    dbcur.execute("SELECT * FROM lastlinktv WHERE o_name='f_name'")

    match = dbcur.fetchone()
    dbcon.commit()
    
    dbcur.close()
    dbcon.close()
    
    if match!=None:
       f_name,name,url,iconimage,fanart,description,data,season,episode,original_title,saved_name,heb_name,show_original_year,eng_name,isr,prev_name,id=match
       try:
           if url!=' ':
             if 'http' not  in url:
           
               url=base64.b64decode(url)
              
             aa=addLink('[I]%s[/I]'%Addon.getLocalizedString(32022), url,6,False,iconimage,fanart,description,data=show_original_year,original_title=original_title,season=season,episode=episode,tmdb=id,year=show_original_year,place_control=True)
             all_d.append(aa)
       except  Exception as e:
         log.warning(e)
         pass
         
    
    
    
    aa=addDir3(Addon.getLocalizedString(32023),'tv',145,BASE_LOGO+'ghost1.png',all_fanarts['32023'],'History')
    all_d.append(aa)
    
    xbmcplugin .addDirectoryItems(int(sys.argv[1]),all_d,len(all_d))
def tv_neworks():
    all_d=[]
    if Addon.getSetting("order_networks")=='0':
        order_by='popularity.desc'
    elif Addon.getSetting("order_networks")=='2':
        order_by='vote_average.desc'
    elif Addon.getSetting("order_networks")=='1':
        order_by='first_air_date.desc'
    aa=addDir3('[COLOR gold]Disney+[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=2739&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Disney')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Apple TV+[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=2552&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','Apple')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]NetFlix[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=213&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','NetFlix')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]HBO[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=49&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','HBO')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]CBS[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=16&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','HBO')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]SyFy[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=77&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','SyFy')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]The CW[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=71&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','The CW')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]ABC[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=2&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','ABC')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]NBC[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=6&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','NBC')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]AMAZON[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=1024&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','AMAZON')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]hulu[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=453&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','hulu')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]Showtime[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=67&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','showtime')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]BBC One[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=4&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','BBC')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]BBC Two[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=332&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','BBC')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]BBC Three[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=3&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','BBC')
    all_d.append(aa)
    aa=addDir3('[COLOR gold]ITV[/COLOR]',f'https://api.themoviedb.org/3/discover/tv?api_key={tmdb_key}&with_networks=9&language={lang}&sort_by={order_by}&timezone=America%2FNew_York&include_null_first_air_dates=false&page=1',14,'https://thechains24.com/PornKing/ghost.png','https://thechains24.com/PornKing/genres.jpg','BBC')
    all_d.append(aa)
    
    xbmcplugin .addDirectoryItems(int(sys.argv[1]),all_d,len(all_d))