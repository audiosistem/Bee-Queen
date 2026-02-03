# resources/lib/cinebox_player.py
import xbmc
import xbmcplugin
import xbmcgui # Import if using error dialogs

class CineboxPlayer(xbmc.Player):
    """Custom player that monitors the start of playback and triggers a callback 
    to close the Resolver window."""
    def __init__(self, on_started_callback=None):
        super().__init__()
        self.on_started_callback = on_started_callback
        self.playback_started = False

    def run(self, data, handle):
        """Starts playback by calling setResolvedUrl.
        'data' is the populated xbmcgui.ListItem."""
        # This is the point where Kodi is instructed to launch the player.
        xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=data)
        xbmc.log("[CineboxPlayer] setResolvedUrl called.", xbmc.LOGINFO)

    def onPlayBackStarted(self):
        """Automatically called by Kodi AFTER playback begins and initial buffering has finished."""
        self.playback_started = True
        xbmc.log("[CineboxPlayer] onPlayBackStarted event received.", xbmc.LOGINFO)
        
        # Calls the resolver window callback to close
        if self.on_started_callback:
            self.on_started_callback()
            
    def onPlayBackStopped(self):
        """Automatically called by Kodi when the player is stopped.
        Used to ensure that the window closes even if there is an error."""
        # If playback stopped but never started, there was an error
        # (Ex: broken link, element not found, etc.).
        if not self.playback_started and self.on_started_callback:
            xbmc.log("[CineboxPlayer] Playback stopped before starting. Closing Resolver.", xbmc.LOGWARNING)
            # Triggers the callback to close the window in case of an error.
            self.on_started_callback()