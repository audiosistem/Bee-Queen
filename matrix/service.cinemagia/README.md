# service.cinemagia

Kodi addon module to scrap program guide (epg) from cinemagia.ro and export it to xml file to be used in:
script.tvguide.fullscreen addon
https://github.com/primaeval/script.tvguide.fullscreen
 or any addon that supports loading epg from xml file or url  
 
You can access the xml file from special://userdata/addon_data/service.cinemagia/tvxml.xml  
  or from http://localhost:8063/epg  
  or from http://yourip:8063/epg   
You can choose channels to be scrapped for epg, from settings.  
You can choose number of days to be scrapped ( default to 3 days)  
The file will be created after choosing channels and restart kodi, and will be updated at every startup, if the file is older than 12 hours  
 EPG file can also be updated from settings  -> force EPG update  
