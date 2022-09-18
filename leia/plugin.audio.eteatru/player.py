import xbmc

from glob import addon_log, addon

class player(xbmc.Player):
  def __init__( self , *args, **kwargs):
    self.offset=kwargs.get('offset')
    self.player_status = None
   
  def play(self, url, listitem):
    self.player_status = 'play';
    super(player, self).play(url, listitem, True)
    self.keep_allive()
    
  def onPlayBackStarted(self):
    self.seekTime(self.offset)
    self.player_status = 'offset';
      
  #def onPlayBackEnded(self):
    #self.player_status = 'end';

  #def onPlayBackStopped(self):
    #self.player_status = 'stop';
    
  def keep_allive(self):
    xbmc.sleep(500)
    while (self.player_status=='play'):
      addon_log('ALLIVE')
      xbmc.sleep(500)
