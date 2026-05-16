from ..plugin import Plugin
import json, xbmc, re, urllib.parse

class dailymotion(Plugin):
    name = "dailymotion"
    priority = 100

    def play_video(self, video):
        item = json.loads(video)
        if "link" not in item: return
        link = item["link"]
        if isinstance(link, list) and len(link) > 0: link = link[0]
        r = re.findall(r"dailymotion\.com\/video\/(\S+)", link)
        if len(r) > 0:
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.dailymotion_com/?mode=playVideo&url=%s)' % r[0])
            return True

    # def routes(self, plugin):
    #     @plugin.route("/run_plug<path:url>")
    #     def run_plug(url):
    #         plug_link = url 
    #         this_plug = urllib.parse.unquote_plus(plug_link)
            
    #         if 'dailymotion' in this_plug.lower():
    #             u = 'plugin.video.dailymotion_com' + ',' + this_plug.split('?')[-1]
    #             z = 'plugin://plugin.video.dailymotion_com/?'+ this_plug.split('?')[-1]

    #             xbmc.executebuiltin('RunAddon({})'.format(u))
