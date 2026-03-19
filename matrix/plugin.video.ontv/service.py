# -*- coding: utf-8 -*-
"""
OnTV — Serviço de background
"""
import xbmc
import xbmcgui
import xbmcaddon
import json
import os
import time
import xbmcvfs

ADDON       = xbmcaddon.Addon()
STREAM_FILE = xbmcvfs.translatePath('special://temp/ontv_stream.json')
STOP_FILE   = xbmcvfs.translatePath('special://temp/ontv_user_stop.flag')


def log(msg):
    xbmc.log('[OnTV Service] ' + str(msg), xbmc.LOGINFO)


def ler_stream():
    try:
        if os.path.exists(STREAM_FILE):
            with open(STREAM_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def limpar_stream():
    try:
        if os.path.exists(STREAM_FILE):
            os.remove(STREAM_FILE)
    except Exception:
        pass


def _fazer_listitem(url, nome, logo):
    url_lower = url.lower().split('?')[0]
    li = xbmcgui.ListItem(nome, path=url)
    li.setProperty('IsPlayable', 'true')
    if '.m3u8' in url_lower:
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        li.setProperty('mimetype', 'application/x-mpegURL')
    else:
        li.setProperty('inputstream', 'inputstream.ffmpegdirect')
        li.setProperty('inputstream.ffmpegdirect.stream_mode', 'ffmpegdirect')
        li.setProperty('inputstream.ffmpegdirect.open_mode', 'curl')
        li.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        li.setProperty('mimetype', 'video/mp2t')
        li.setProperty('inputstream.ffmpegdirect.read_chunk_size', '131072')
        li.setProperty('network.buffer_factor', '4.0')
    li.setProperty('network.curlcachebytes', '20971520')
    li.setProperty('network.bandwidth', '0')
    li.setProperty('network.readtimeout', '60')
    li.setProperty('network.connecttimeout', '10')
    if logo:
        li.setArt({'thumb': logo, 'icon': logo})
    li.setInfo('video', {'title': nome, 'mediatype': 'video', 'playcount': 0, 'overlay': 0})
    return li


class OnTVPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self._tempo_inicio   = 0
        self._reinicios_init = 0
        self._a_reiniciar    = False

    def onPlayBackStarted(self):
        agora = time.time()
        if agora - self._tempo_inicio > 10:
            self._tempo_inicio   = agora
            self._reinicios_init = 0
        self._a_reiniciar = False
        # Remover stop flag ao iniciar reprodução
        try:
            if os.path.exists(STOP_FILE):
                os.remove(STOP_FILE)
        except Exception:
            pass
        log('Stream iniciado')

    def onPlayBackStopped(self):
        """Utilizador parou manualmente — nunca reiniciar."""
        log('Stream parado pelo utilizador')
        limpar_stream()
        self._reinicios_init = 0
        self._a_reiniciar = False
        # Criar stop flag para evitar reinícios indesejados
        try:
            with open(STOP_FILE, 'w') as f:
                f.write('1')
        except Exception:
            pass

    def onPlayBackEnded(self):
        """EOF — servidor fechou ligação."""
        if os.path.exists(STOP_FILE):
            return
        xbmc.sleep(1500)
        self._reiniciar('EOF')

    def onPlayBackError(self):
        """Erro de rede ou codec."""
        if os.path.exists(STOP_FILE):
            return
        xbmc.sleep(3000)
        self._reiniciar('Erro')

    def _reiniciar(self, motivo):
        if self._a_reiniciar:
            return
        if os.path.exists(STOP_FILE):
            return

        info = ler_stream()
        if not info or not info.get('url', '').startswith('http'):
            return

        duracao = time.time() - self._tempo_inicio

        # Primeiros 10s: máximo 1 reinício
        if duracao < 10:
            if self._reinicios_init >= 1:
                log('{} em {}s — limite inicial atingido'.format(motivo, int(duracao)))
                return
            self._reinicios_init += 1

        log('{} em {}s — a reiniciar'.format(motivo, int(duracao)))
        self._a_reiniciar = True
        url  = info.get('url', '')
        nome = info.get('nome', '')
        logo = info.get('logo', '')
        self.play(url, _fazer_listitem(url, nome, logo))


def run():
    log('Serviço iniciado')
    # Apagar flag do Gist para forçar actualização na próxima abertura do addon
    try:
        gist_flag = xbmcvfs.translatePath('special://temp/ontv_gist_ts.flag')
        if os.path.exists(gist_flag):
            os.remove(gist_flag)
            log('Flag do Gist apagada — servidores serão actualizados')
    except Exception:
        pass
    monitor = xbmc.Monitor()
    player  = OnTVPlayer()

    while not monitor.abortRequested():
        monitor.waitForAbort(5)

    log('Serviço terminado')


if __name__ == '__main__':
    run()
