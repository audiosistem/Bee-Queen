import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler
from resources.lib.bottle import Bottle, ServerAdapter, response, redirect, abort, request, static_file
from resources.lib.functions import filePath, HOME, TVXML_FILE, log, addon


class HTTP:
    def epg(self):
        response.headers['Content-Type'] = 'xml/application'
        return static_file(TVXML_FILE, HOME)

class Server:
    def __init__(self):
        self.server = None
        self.http = HTTP()
        threading.Thread(target=self._run).start()
        
    def loop(self):
        pass
    
    def _run(self):
        app = Bottle()
        app.route('/epg', callback=self.http.epg)
        self.server = BottleServer(host='0.0.0.0', port=int(addon.getSetting('web_port')))
        try:
            app.run(server=self.server)
        except Exception as e:
            log(e)
        log('server stopped')
        self.server = None
        
    def get_ip(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def stop(self):
        if self.server:
            self.server.stop()
            while self.server:
                xbmc.sleep(300)

class QuietHandler(WSGIRequestHandler):
    def log_request(*args, **kwargs):
        pass

class BottleServer(ServerAdapter):
    server = None

    def run(self, handler):
        if self.quiet:
            self.options['handler_class'] = QuietHandler
        self.server = make_server(self.host, self.port, handler, **self.options)
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()
