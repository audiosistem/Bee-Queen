# -*- coding: utf-8 -*-
# Python 3
# Always pay attention to the translations in the menu!

import xbmcgui, sys, xbmc, xbmcvfs
from resources.lib.config import cConfig

######################## Youtube Mod ############################

storedb=xbmcvfs.translatePath('special://home/userdata/addon_data/plugin.video.youtube/api_keys.json')
providerpath=xbmcvfs.translatePath('special://home/addons/plugin.video.youtube/resources/lib/youtube_plugin/youtube/provider.py')
youtubepath=xbmcvfs.translatePath('special://home/addons/plugin.video.youtube/resources/lib/youtube_plugin/youtube/client/youtube.py')

def YT():
    try:
        apikey=cConfig('plugin.video.youtube').getSetting('youtube.api.key')
    except:
        xbmc.executebuiltin('InstallAddon(%s)' % 'plugin.video.youtube')
        sys.exit()

    addon_id='plugin.video.xstream'
    api_key='AIzaSyDnlJ0e_CZlLoZm7CMNnO41xInZgVFyObo'
    client_id='869922081769-d392du3vu6c8cpmtll11rpd7f09deu1n.apps.googleusercontent.com'
    client_secret='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'

    if apikey == '' or apikey == None:
        try:
            with open(providerpath,'r') as f1:
                f1x=f1.read()
                if not 'mr-evil1' in f1x:
                    try:
                        xbmc.sleep(1000)
                        with open(providerpath,'w' ) as f1y:
                            f1y.write('# -*- coding: utf-8 -*-\n#mr-evil1\n'+f1x.replace("""                keys_changed = access_manager.dev_keys_changed(
                    dev_id, dev_keys['key'], dev_keys['id'], dev_keys['secret']
                )""","""                try:
                            keys_changed = access_manager.dev_keys_changed(dev_id, dev_keys['key'], dev_keys['id'], dev_keys['secret'])
                except:
                            keys_changed = access_manager.dev_keys_changed(str(dev_id), str(dev_keys['key']), str(dev_keys['id']), str(dev_keys['secret']))""").replace("""                if self._api_check.changed:
                    context.log_warning('API key set changed: Resetting client'
                                        ' and updating access token')
                    self.reset_client()
                    access_tokens = []
                    refresh_tokens = []
                    access_manager.update_access_token(
                        dev_id, access_tokens, -1, refresh_tokens,
                    )""","""                try:
                    if self._api_check.changed:
                        context.log_warning('API key set changed: Resetting client'
                                            ' and updating access token')
                        self.reset_client()
                        access_tokens = []
                        refresh_tokens = []
                        access_manager.update_access_token(
                            dev_id, access_tokens, -1, refresh_tokens,
                        )
                except:pass"""))
                    except:xbmcgui.Dialog().ok('','FEHLER1')
            with open(youtubepath,'r') as f2:
                f2x=f2.read()
                if not 'mr-evil1' in f2x:
                    try:
                        xbmc.sleep(1000)
                        with open(youtubepath,'w' ) as f2y:
                            f2y.write('# -*- coding: utf-8 -*-\n#mr-evil1\n'+f2x.replace("""log_params['key'] = '...'.join((key[:3], key[-3:]))""","""#log_params['key'] = '...'.join((key[:3], key[-3:]))"""))
                    except:xbmcgui.Dialog().ok('','FEHLER2')
            import youtube_registration
            youtube_registration.register_api_keys(addon_id,api_key,client_id,client_secret)
        except:pass