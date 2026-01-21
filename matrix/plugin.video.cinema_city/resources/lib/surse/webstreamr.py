from stremio_processor import Stremio2 

class sources(Stremio2):
    def __init__(self):
        super().__init__()
        self.provider = "webstreamr"
        self.base_url = "https://webstreamr.hayd.uk/stream/"
