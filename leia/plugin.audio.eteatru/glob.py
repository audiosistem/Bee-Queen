import xbmc, xbmcgui, xbmcaddon
import urllib, urllib2
import os, stat
import re

addon = xbmcaddon.Addon('plugin.audio.eteatru')

def addon_log(string):
  DEBUG = addon.getSetting('debug')
  ADDON_VERSION = addon.getAddonInfo('version')
  if DEBUG == 'true':
    if isinstance(string, unicode):
      string = string.encode('utf-8')
    xbmc.log("[plugin.audio.eteatru-%s]: %s" %(ADDON_VERSION, string))


def Downloader(url,dest,description,heading):
  dp = xbmcgui.DialogProgress()
  dp.create(heading,description,url)
  dp.update(0)

  urllib.urlretrieve(url,dest,lambda nb, bs, fs, url=url: _pbhook(nb,bs,fs,dp))
  
def _pbhook(numblocks, blocksize, filesize, dp=None):
  try:
    percent = int((int(numblocks)*int(blocksize)*100)/int(filesize))
    dp.update(percent)
  except:
    percent = 100
    dp.update(percent)
  if dp.iscanceled():
    #raise KeyboardInterrupt
    dp.close()

def cleanJson(string):
  string = re.sub("/\*[\w\W]*?\*/", "", string)
  string = re.sub("\s\/\/[\w\W]*?\n", "\n", string)
  
  string = re.sub(",[ \t\r\n]+}", "}", string)
  string = re.sub(",[ \t\r\n]*\]", "]", string)
  
  string = re.sub("\\\\'", "'", string)
  
  return string

def message(title, message):
  dialog = xbmcgui.Dialog()
  dialog.ok(title, message)