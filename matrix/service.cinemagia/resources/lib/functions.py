import os
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
#from os.path import expanduser


addon = xbmcaddon.Addon('service.cinemagia')
path = addon.getAddonInfo('path')
profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
dataPath = os.path.join(profile, 'channels.txt')
__plugin__ = addon.getAddonInfo('name') + ' v. ' + addon.getAddonInfo('version')
TVXML_FILE = 'tvxml.xml'
#HOME = expanduser("~")
HOME = profile
filePath = os.path.join(HOME, TVXML_FILE)
icon = os.path.join(path, 'icon.png')
    

def log(msg):
    loginfo = xbmc.LOGINFO
    try:
        xbmc.log("### [%s]: %s" % (__plugin__,msg,), level=loginfo )
    except UnicodeEncodeError:
        xbmc.log("### [%s]: %s" % (__plugin__,msg.encode("utf-8", "ignore"),), level=loginfo )
    except:
        xbmc.log("### [%s]: %s" % (__plugin__,'ERROR LOG',), level=loginfo )

def showMessage(heading, message, times=5000, forced=True):
    if forced:
        xbmc.executebuiltin('Notification(%s, %s, %s, %s)' % (
            heading.replace('"', "'"), message.replace('"', "'"), times, icon))

def update(force=False):
    if os.path.exists(dataPath):
        lines = []
        final_lines = []
        with open(dataPath) as f:
                lines = f.readlines()
        lines = [line.rstrip() for line in lines]
        
        for line in lines:
            splitted = line.split(',')
            final_lines.append((splitted[0], splitted[1]))
        fileTime = None
        if (os.path.isfile(filePath)):
            fileTime = os.path.getmtime(filePath)
        currentTime = time.time()
        if (fileTime == None or currentTime - fileTime > (3600 * 12)) or force: #older than 12hours
            notify = addon.getSetting('notify') == 'true'
            if notify:
                showMessage('Cinemagia', 'Started EPG extraction...')
            from resources.cinemagia.cinemagia import Cinemagia
            days = int(addon.getSetting('days'))
            # cm.debug = True
            cm = Cinemagia(filePath = filePath, wanted=final_lines, days=days, epg_details = addon.getSetting('epg_details'))
            if addon.getSetting('progress') == 'true':
                pDialog = xbmcgui.DialogProgressBG()
                pDialog.create('Cinemagia', 'Downloading EPG...')
                time.sleep(1)
            else:
                pDialog = None
            cm.execute(dlg = pDialog, notify=notify)
