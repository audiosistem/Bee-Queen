from ..plugin import Plugin, run_hook
from resources.lib import k

class E(Plugin):
    name = "e"
    priority = 1000

    def get_list(self, url:str):
        if url.startswith("@"):
            url = k.ufghjxcgfzxc(url)
            return run_hook("get_list", url)
    