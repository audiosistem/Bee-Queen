from ..plugin import Plugin

class Local(Plugin):
    name = "base64"

    def get_list(self, url:str):
        if url.startswith("base64"):
            import base64
            from ..plugin import run_hook
            url = str(base64.b64decode(url + '=' * (-len(url) % 4)))
            return run_hook("get_list", url)