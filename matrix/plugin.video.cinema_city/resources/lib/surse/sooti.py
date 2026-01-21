# -*- coding: utf-8 -*-
from stremio_processor import Stremio2 
from urllib.parse import quote
import requests

class sources(Stremio2):
    def __init__(self):
        super().__init__()
        self.provider = "sooti"
        self.stremthru_config = '{"DebridServices":[{"provider":"httpstreaming","http4khdhub":true,"httpHDHub4u":true,"httpUHDMovies":true,"httpMoviesDrive":true,"httpMKVCinemas":true}],"Languages":[],"Scrapers":[],"IndexerScrapers":["stremthru"],"minSize":0,"maxSize":200,"ShowCatalog":true,"DebridProvider":"httpstreaming"}'
        
        self.config_part = quote(self.stremthru_config)
        self.base_urls = [
            f"https://sootiofortheweebs.midnightignite.me/{self.config_part}/stream/",
            f"https://sooti.info/{self.config_part}/stream/"
        ]
        self.timeout = 30

    def get_sources(self, imdb_id, media_type, season=None, episode=None):
        if not str(imdb_id).startswith('tt'): imdb_id = f"tt{imdb_id}"
        path = f"series/{imdb_id}:{season}:{episode}.json" if media_type == 'tv' else f"movie/{imdb_id}.json"
        
        sources_list = []

        for base in self.base_urls:
            try:                
                full_url = base + path
                resp = requests.get(full_url, headers={'User-Agent': self.user_agent}, timeout=20)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('streams'):
                        sources_list = self._process_item(data)
                        if sources_list: 
                            self.log(f"Surse găsite pe: {base}")
                            break # Oprim cautarea daca am gasit rezultate pe sursa curenta
            except:
                continue # Trecem silentios la urmatoarea sursa in caz de eroare

        return sources_list
