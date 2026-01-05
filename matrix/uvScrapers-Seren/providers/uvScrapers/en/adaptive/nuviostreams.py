# -*- coding: utf-8 -*-
from providerModules.uvScrapers.core.uvs import Core


class sources(Core):
    def __init__(self):
        super().__init__()
        self.provider = "nuviostreams"
        self.base_url = "https://nuviostreams.hayd.uk/stream/"
