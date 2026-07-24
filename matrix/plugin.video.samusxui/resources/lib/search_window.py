# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcaddon

ADDON_PATH = xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('path')

ACTION_NAV_BACK  = 10
ACTION_PREV_MENU = 92


class SearchWindow(xbmcgui.WindowXMLDialog):
    """Picker tip media (Filme/Seriale) — apelat după ce CustomKeyboard a capturat query-ul."""

    def __init__(self, *args, **kwargs):
        self._query_text = ''  # setat de caller înainte de doModal()
        self._media = None

    def onInit(self):
        try:
            q = self._query_text
            self.getControl(100).setLabel(
                f'[COLOR FF9090AA]„[/COLOR]{q}[COLOR FF9090AA]”[/COLOR]')
        except Exception as e:
            xbmc.log(f'[SamusXUI/Search] onInit: {e}', xbmc.LOGWARNING)
        self.setFocusId(110)

    def onAction(self, action):
        if action.getId() in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()

    def onClick(self, controlId):
        if controlId == 110:
            self._media = 'movie'
            self.close()
        elif controlId == 111:
            self._media = 'tv'
            self.close()

    def get_result(self):
        return self._query_text, self._media
