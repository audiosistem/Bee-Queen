import xbmcgui
import xbmcaddon

ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
ADDON_PATH = xbmcaddon.Addon(id=ADDON_ID).getAddonInfo('path')
DONATION_IMAGE = f"{ADDON_PATH}/resources/medias/icons/donate.jpg"

class DonationDialog(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.getControl(100).setImage(DONATION_IMAGE)
        self.getControl(101).setLabel('[COLOR red]Muito obrigado pelo seu apoio![/COLOR]')

    def onAction(self, action):
        if action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()