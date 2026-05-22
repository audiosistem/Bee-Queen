import xbmcaddon
try:
    from resources.lib.DI import DI
    from resources.lib.plugin import run_hook, register_routes
except ImportError:
    from .resources.lib.DI import DI
    from .resources.lib.plugin import run_hook, register_routes

try:
    from resources.lib.util.common import *
except ImportError:
    from .resources.lib.util.common import *
    
root_xml_url = ownAddon.getSetting('https://raw.githubusercontent.com/MetalDudesMusic/PTFM/main/main.json') or "https://raw.githubusercontent.com/MetalDudesMusic/PTFM/main/main.json"

#root_xml_url =  "https://raw.githubusercontent.com/MetalDudesMusic/PTFM/main/main.json"

plugin = DI.plugin
short_checker = ([
    'Adf.ly', 
    'Bit.ly', 
    'Chilp.it', 
    'Clck.ru', 
    'Cutt.ly', 
    'Da.gd', 
    'Git.io', 
    'goo.gl', 
    'Is.gd', 
    'NullPointer', 
    'Os.db', 
    'Ow.ly', 
    'Po.st', 
    'Qps.ru', 
    'Short.cm', 
    'Tiny.cc', 
    'TinyURL.com', 
    'Git.io', 
    'Tiny.cc', 
     ])

@plugin.route("/")
def root() -> None:
    get_list(root_xml_url)

@plugin.route("/get_list/<path:url>")
def get_list(url: str) -> None:
    #do_log(f" Reading url at route >  {url}" )
    url = url.replace('.xmll', '.xml')
    _get_list(url)

def _get_list(url):
    #do_log(f" Reading url >  {url}" )
    if any(check.lower() in url.lower() for check in short_checker):
        url = DI.session.get(url).url
    response = run_hook("get_list", url)
    if response:           
        #do_log(f'default - response = \n {str(response)} ' )
        if ownAddon.getSettingBool("use_cache") and not "tmdb/search" in url:
            DI.db.set(url, response)
        jen_list = run_hook("parse_list", url, response) 
        #do_log(f'default - jen list = \n {str(jen_list)} ')
        jen_list = [run_hook("process_item", item) for item in jen_list]
        jen_list = [
        run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list
        ]
        run_hook("display_list", jen_list)
    else:
        run_hook("display_list", [])

@plugin.route("/play_video/<path:video>")
def play_video(video: str):
    _play_video(video)

def _play_video(video):
    import base64
    video_link = '' 
    video = base64.urlsafe_b64decode(video)      
    if '"link":' in str(video) :
        video_link = run_hook("pre_play", video)
        if video_link : 
            run_hook("play_video", video_link)        
    else :
        run_hook("play_video", video)

@plugin.route("/settings")
def settings():
    xbmcaddon.Addon().openSettings()

@plugin.route("/clear_cache")
def clear_cache():
    DI.db.clear_cache()
    import xbmc
    #xbmc.sleep(1000)
    xbmc.executebuiltin("Container.Refresh")

register_routes(plugin)

def main():
    plugin.run()
    return 0

if __name__ == "__main__":
    main()
