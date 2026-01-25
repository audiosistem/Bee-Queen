# -*- coding: utf-8 -*-
import xbmcgui

class ChangelogDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        # O super() já lida com o arquivo XML
        self.heading = kwargs.get("heading", "Changelog")
        self.text = kwargs.get("text", "")
        super(ChangelogDialog, self).__init__(*args)

    def onInit(self):
        self.setProperty("heading", self.heading)
        self.setProperty("text", self.text)
        self.setProperty("font_size", self.font_size)
        
        # Escolhe o ID baseado no tamanho da fonte
        id_para_focar = 2001 if self.font_size == "large" else 2000
        
            
        # FORÇA O FOCO no controle de texto para o scroll funcionar de imediato
        self.setFocusId(id_para_focar)

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.close()