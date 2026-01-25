# resources/lib/cinebox_player.py
import xbmc
import xbmcplugin
import xbmcgui # Importe se for usar diálogos de erro

class CineboxPlayer(xbmc.Player):
    """
    Player customizado que monitora o início da reprodução e dispara um callback 
    para fechar a janela do Resolvedor.
    """
    def __init__(self, on_started_callback=None):
        super().__init__()
        self.on_started_callback = on_started_callback
        self.playback_started = False

    def run(self, data, handle):
        """
        Inicia a reprodução chamando setResolvedUrl.
        'data' é o xbmcgui.ListItem preenchido.
        """
        # Este é o ponto onde o Kodi é instruído a iniciar o player.
        xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=data)
        xbmc.log("[CineboxPlayer] setResolvedUrl chamado.", xbmc.LOGINFO)

    def onPlayBackStarted(self):
        """
        Chamado automaticamente pelo Kodi APÓS a reprodução começar e o buffer inicial terminar.
        """
        self.playback_started = True
        xbmc.log("[CineboxPlayer] Evento onPlayBackStarted recebido.", xbmc.LOGINFO)
        
        # Chama o callback da janela do resolvedor para fechar
        if self.on_started_callback:
            self.on_started_callback()
            
    def onPlayBackStopped(self):
        """
        Chamado automaticamente pelo Kodi quando o player é parado.
        Usado para garantir que a janela feche mesmo que haja um erro.
        """
        # Se a reprodução parou, mas nunca começou, significa que houve um erro 
        # (Ex: link quebrado, elemento não encontrado, etc.).
        if not self.playback_started and self.on_started_callback:
            xbmc.log("[CineboxPlayer] Playback Stopped antes de iniciar. Fechando Resolvedor.", xbmc.LOGWARNING)
            # Aciona o callback para fechar a janela em caso de erro.
            self.on_started_callback()