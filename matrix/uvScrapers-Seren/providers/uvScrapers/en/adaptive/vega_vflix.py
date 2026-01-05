# -*- coding: utf-8 -*-
from providerModules.uvScrapers.core.uvs import Core


class sources(Core):
    def __init__(self):
        super().__init__()
        self.provider = "vega_vflix"
        self.base_url = "https://vega.vflix.life/stream/"
