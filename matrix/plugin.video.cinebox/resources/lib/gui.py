import xbmcgui
import xbmcaddon



class CustomProgress(xbmcgui.WindowXML):
    # Kodi will call __init__ first
    def __init__(self, *args, **kwargs):
        super(CustomProgress, self).__init__(*args, **kwargs)
        self.canceled = False

    def onInit(self):
        """Automatically called when XML finishes loading"""
        self.label = self.getControl(2)         # ID defined in XML
        self.progress_bar = self.getControl(3)  # ID defined in XML

    def update(self, percent, message):
        """Method you will call from within the indexer"""
        try:
            self.label.setLabel(message)
            self.progress_bar.setPercent(int(percent))
        except:
            pass

    def onAction(self, action):
        """Capture remote control keys"""
        if action.getId() in [92, 10, 13]: # Back, Exit or Stop
            self.canceled = True
            self.close()

    def iscanceled(self):
        return self.canceled