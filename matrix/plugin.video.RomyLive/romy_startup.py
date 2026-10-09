# -*- coding: utf-8 -*-
"""Elapsed connection counter and audio selection on the actual video player."""
import json
import threading
import time


class Counter:
    def __init__(self):
        import xbmcgui
        self.stop = threading.Event()
        self.started = time.monotonic()
        self.dialog = xbmcgui.DialogProgressBG()
        self.dialog.create('1', '')
        self.thread = threading.Thread(target=self.run, name='RomyLiveCounter', daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.wait(0.5):
            seconds = max(1, int(time.monotonic() - self.started) + 1)
            try:
                self.dialog.update(0, str(seconds), '')
            except Exception:
                return

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        self.dialog.close()


def on_started(counter, stream, timeout=60, resolve_callback=None):
    """Keep the plugin interpreter alive until AV starts; don't rely on URL equality.

CDNs redirect the resolved URL, making a strict pending-file match unreliable.
Use an AV-start callback plus Kodi's actual stream list in this invocation.
"""
    import xbmc
    import xbmcaddon
    from romy_audio import choose_romanian
    event = threading.Event()

    class Player(xbmc.Player):
        def onAVStarted(self):
            event.set()
        def onPlayBackError(self):
            self.failed = True
            event.set()
        failed = False

    player = Player()
    monitor = xbmc.Monitor()
    deadline = time.monotonic() + timeout
    prefer = xbmcaddon.Addon('plugin.video.RomyLive').getSetting('audio_prefer_romanian') != 'false'
    try:
        if resolve_callback is not None:
            resolve_callback()
        while time.monotonic() < deadline and not monitor.abortRequested():
            # Some Kodi builds do not deliver callbacks to every Player instance.
            if player.failed:
                return False
            if event.is_set() or player.isPlayingVideo():
                counter.close()
                counter = None
                if not prefer:
                    return True
                audio_deadline = time.monotonic() + 15
                while time.monotonic() < audio_deadline and not monitor.abortRequested():
                    if not player.isPlayingVideo():
                        return False
                    message = {'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetProperties',
                               'params': {'playerid': 1, 'properties': ['audiostreams', 'currentaudiostream']}}
                    try:
                        props = json.loads(xbmc.executeJSONRPC(json.dumps(message))).get('result') or {}
                        tracks = props.get('audiostreams') or []
                        current = (props.get('currentaudiostream') or {}).get('index')
                        selected = choose_romanian(tracks, current)
                        if selected is not None:
                            player.setAudioStream(selected)
                            xbmc.log('[RomyLive Audio] Selectie la pornirea AV: pista %s' % selected, xbmc.LOGINFO)
                            return True
                    except Exception:
                        pass
                    monitor.waitForAbort(0.5)
                xbmc.log('[RomyLive Audio] Pista romana nu a fost expusa de Kodi la pornire.', xbmc.LOGWARNING)
                return True
            monitor.waitForAbort(0.25)
        return False
    finally:
        if counter is not None:
            counter.close()


def wait_and_select(counter, stream, resolve_callback):
    return on_started(counter, stream, resolve_callback=resolve_callback)