# -*- coding: utf-8 -*-
from stremio_processor import Stremio2

class sources(Stremio2):
    def __init__(self):
        super().__init__()
        self.provider = "nuviostreams"
        self.base_url = "https://nuviostreams.hayd.uk/providers=vidzee,vidsrc,vixsrc,mp4hydra,uhdmovies,4khdhub,hdhub4u/stream/"
        self.timeout = 30
        self.blocked_domains = [
            "https://pub-"
        ]