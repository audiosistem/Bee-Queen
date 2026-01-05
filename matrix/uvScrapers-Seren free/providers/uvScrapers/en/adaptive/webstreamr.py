# -*- coding: utf-8 -*-
from providerModules.uvScrapers.core.uvs import Core


class sources(Core):
    def __init__(self):
        super().__init__()
        self.provider = "webstreamr"
        self.base_url = "https://webstreamr.hayd.uk/stream/"
