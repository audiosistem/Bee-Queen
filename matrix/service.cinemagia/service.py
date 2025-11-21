import xbmc
from resources.lib.functions import  addon, log, update
from resources.lib.server import Server

def main():

    server = Server()
    log('server started')
    server.loop()
    monitor = xbmc.Monitor()

    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
        xbmc.sleep(1000)
    server.stop()

update()

if addon.getSetting('web_server') == 'true':
    main()
