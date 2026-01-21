# -*- coding: utf-8 -*-
import xbmc, xbmcgui, xbmcaddon, requests, re

class Stremio:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.url_list = []
        # Citim setarea din Kodi (trebuie să existe în settings.xml cu id="verify_links")
        self.should_verify = self.addon.getSetting('verify_links') == 'true'

    def log(self, msg):
        xbmc.log(f">>> CinemaCity: {msg}", xbmc.LOGINFO)

    def check_url(self, url):
        # Dacă verificarea este oprită, returnăm tipul bazat pe extensie
        if not self.should_verify:
            return "hls" if ".m3u8" in url.lower() else "direct"
            
        try:
            # Facem o cerere rapidă HEAD pentru a vedea dacă link-ul e activ
            r = requests.head(url, headers={'User-Agent': self.user_agent}, timeout=5, allow_redirects=True)
            if r.status_code >= 400: return False
            
            ct = r.headers.get('Content-Type', '').lower()
            if 'mpegurl' in ct or '.m3u8' in url: return "hls"
            return "direct"
        except: 
            return False

    def get_sources(self, imdb_id, m_type, season, episode):
        simple_info = {"season_number": str(season), "episode_number": str(episode)}
        if m_type.lower() == 'movie':
            return self.movie("", "", imdb_id, simple_info, {})
        else:
            return self.episode(simple_info, {"info": {"tvshow.imdb_id": imdb_id}})

    @staticmethod
    def get_listitem(data):
        url = data.get('url', '')
        list_item = xbmcgui.ListItem(path=url, offscreen=True)
        list_item.setProperty("isPlayable", "true")
        
        if data.get('filetype') == 'hls':
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            list_item.setProperty('inputstream.adaptive.stream_headers', 'User-Agent=Mozilla/5.0')
        
        return list_item
