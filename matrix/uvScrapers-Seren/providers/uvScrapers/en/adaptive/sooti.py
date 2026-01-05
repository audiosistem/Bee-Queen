# -*- coding: utf-8 -*-
from providerModules.uvScrapers.core.uvs import Core
from urllib.parse import quote


class sources(Core):
    def __init__(self):
        super().__init__()
        self.provider = "sooti"
        self.stremthru_config = '{"DebridServices":[{"provider":"httpstreaming","http4khdhub":true,"httpHDHub4u":true,"httpUHDMovies":true,"httpMoviesDrive":true,"httpMKVCinemas":true}],"Languages":[],"Scrapers":[],"IndexerScrapers":["stremthru"],"minSize":0,"maxSize":200,"ShowCatalog":true,"DebridProvider":"httpstreaming"}'
        self.base_url = f"https://sooti.info/{quote(self.stremthru_config)}/stream/"
