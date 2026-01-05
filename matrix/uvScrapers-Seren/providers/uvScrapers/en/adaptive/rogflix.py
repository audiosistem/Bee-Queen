# -*- coding: utf-8 -*-
from providerModules.uvScrapers.core.uvs import Core


class sources(Core):
    def __init__(self):
        super().__init__()
        self.provider = "rogflix"
        self.base_url = "https://rogflix.vflix.life/stremio/stream/"
