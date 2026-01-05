# -*- coding: utf-8 -*-
from providerModules.uvScrapers.core.uvs import UVScrapers


class sources(UVScrapers):
    def __init__(self):
        super().__init__()
        self.provider = "sflix"
        self.base_link = "https://sflix2.to/"
        self.query_link = f"{self.base_link}{self.search_link}"
        self.log(self.query_link)
