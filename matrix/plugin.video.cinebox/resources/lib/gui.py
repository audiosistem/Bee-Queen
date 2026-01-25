import xbmcgui
import xbmcaddon



class CustomProgress(xbmcgui.WindowXML):
    # O Kodi chamará o __init__ primeiro
    def __init__(self, *args, **kwargs):
        super(CustomProgress, self).__init__(*args, **kwargs)
        self.canceled = False

    def onInit(self):
        """Chamado automaticamente quando o XML termina de carregar"""
        self.label = self.getControl(2)         # ID definido no XML
        self.progress_bar = self.getControl(3)  # ID definido no XML

    def update(self, percent, message):
        """Método que você chamará de dentro do indexer"""
        try:
            self.label.setLabel(message)
            self.progress_bar.setPercent(int(percent))
        except:
            pass

    def onAction(self, action):
        """Captura teclas do controle remoto"""
        if action.getId() in [92, 10, 13]: # Voltar, Sair ou Stop
            self.canceled = True
            self.close()

    def iscanceled(self):
        return self.canceled