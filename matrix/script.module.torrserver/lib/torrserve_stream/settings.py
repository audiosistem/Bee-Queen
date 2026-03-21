import xbmcaddon, xbmc

_addon = xbmcaddon.Addon(id='script.module.torrserver')
class Settings(object):
    def __init__(self):
        self.load()

    def load(self):
        self.host = _addon.getSetting('host')
        self.port = int(_addon.getSetting('port'))
        self.save_in_database = _addon.getSetting('save_in_database') == "true"
        
        use_auth = _addon.getSetting('use_auth') == 'true'

        login = _addon.getSetting('login')
        passw = _addon.getSetting('passw')

        self.auth = ( login, passw ) if use_auth else None

if __name__ == '__main__':
    xbmc.log('open settings')
    _addon.openSettings() 