#
#
#    Copyright (C) 2020  Alin Cretu
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#

import os
import xbmcaddon
import xbmc
from urllib import urlencode
import requests
import json
import logging
import logging.handlers
from datetime import datetime
from datetime import timedelta
import time
import resources.lib.common.vars as vars
import resources.lib.common.functions as functions
import resources.lib.schedule as schedule
import re

__SystemBuildVersion__ = xbmc.getInfoLabel('System.BuildVersion')
__SystemBuildDate__ = xbmc.getInfoLabel('System.BuildDate')

# Kodi uses the following sys.argv arguments:
# [0] - The base URL for this add-on, e.g. 'plugin://plugin.video.demo1/'.
# [1] - The process handle for this add-on, as a numeric string.
# [2] - The query string passed to this add-on, e.g. '?foo=bar&baz=quux'.

# Get the plugin url in plugin:// notation.
_url = sys.argv[0]

# Get the plugin handle as an integer number.
#_handle = int(sys.argv[1])

MyServiceAddon = xbmcaddon.Addon(id=vars.__AddonID__)

# The version of the runing Addon
__AddonVersion__ = MyServiceAddon.getAddonInfo('version')

# Initialize the Addon data directory
MyServiceAddon_DataDir = xbmc.translatePath(MyServiceAddon.getAddonInfo('profile'))
if not os.path.exists(MyServiceAddon_DataDir):
    os.makedirs(MyServiceAddon_DataDir)

# Read the user preferences stored in the addon configuration
functions.read_AddonSettings(MyServiceAddon)

# Log file name
service_logfile_name = os.path.join(MyServiceAddon_DataDir, vars.__ServiceLogFilename__)

# Configure logging
if vars.__config_DebugEnabled__ == 'true':
  logging.basicConfig(level=logging.DEBUG)
else:
  logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(vars.__ServiceID__)
logger.propagate = False

# Create a rotating file handler
# TODO: Extend the settings.xml to allow the user to choose the values for maxBytes and backupCount
# TODO: Set the values for maxBytes and backupCount to values defined in the addon settings
handler = logging.handlers.RotatingFileHandler(service_logfile_name, mode='a', maxBytes=104857600, backupCount=2, encoding=None, delay=False)
if vars.__config_DebugEnabled__ == 'true':
  handler.setLevel(logging.DEBUG)
else:
  handler.setLevel(logging.INFO)

# Create a logging format to be used
formatter = logging.Formatter('%(asctime)s %(funcName)s %(levelname)s: %(message)s', datefmt='%Y%m%d_%H%M%S')
handler.setFormatter(formatter)

# add the file handler to the logger
logger.addHandler(handler)

logger.debug('[ Addon settings ] MyServiceAddon = ' + str(MyServiceAddon))
logger.debug('[ Addon settings ] MyServiceAddon_DataDir = ' + str(MyServiceAddon_DataDir))
logger.debug('[ Addon settings ] __config_DebugEnabled__ = ' + str(vars.__config_DebugEnabled__))

# Initialize the __AddonCookieJar__ variable
functions.init_AddonCookieJar(vars.__ServiceID__, MyServiceAddon_DataDir)

# Start a new requests session and initialize the cookiejar
vars.__ServiceSession__ = requests.Session()

# Put all session cookeis in the cookiejar
vars.__ServiceSession__.cookies = vars.__AddonCookieJar__

def schedule_jobs():
  logger.debug('Enter function')
  
  # Read the user preferences stored in the addon configuration
  functions.read_AddonSettings(MyServiceAddon)
  
  if vars.__PVRIPTVSimpleClientIntegration_m3u_FileRefreshTime__ != vars.__PVRIPTVSimpleClientIntegration_m3u_FileOldRefreshTime__ or vars.__PVRIPTVSimpleClientIntegration_EPG_FileRefreshTime__ != vars.__PVRIPTVSimpleClientIntegration_EPG_FileOldRefreshTime__:
    logger.debug('__PVRIPTVSimpleClientIntegration_m3u_FileRefreshTime__ = ' + vars.__PVRIPTVSimpleClientIntegration_m3u_FileRefreshTime__)
    logger.debug('__PVRIPTVSimpleClientIntegration_EPG_FileRefreshTime__ = ' + vars.__PVRIPTVSimpleClientIntegration_EPG_FileRefreshTime__)

    schedule.clear('m3u')
    schedule.every().day.at(vars.__PVRIPTVSimpleClientIntegration_m3u_FileRefreshTime__).do(PVRIPTVSimpleClientIntegration_update_m3u_file).tag('m3u')
    
    schedule.clear('EPG')
    schedule.every().day.at(vars.__PVRIPTVSimpleClientIntegration_EPG_FileRefreshTime__).do(PVRIPTVSimpleClientIntegration_update_EPG_file).tag('EPG')

    # Record the new values
    vars.__PVRIPTVSimpleClientIntegration_m3u_FileOldRefreshTime__ = vars.__PVRIPTVSimpleClientIntegration_m3u_FileRefreshTime__
    vars.__PVRIPTVSimpleClientIntegration_EPG_FileOldRefreshTime__ = vars.__PVRIPTVSimpleClientIntegration_EPG_FileRefreshTime__

  else:
    logger.debug('No re-scheduling required !')
    
  # (re)Initialize the files for PVR IPTV Simple Client
  PVRIPTVSimpleClientIntegration_init_m3u_file()
  PVRIPTVSimpleClientIntegration_init_EPG_file()

  logger.debug('Exit function')


def PVRIPTVSimpleClientIntegration_check_data_file(DATAFILE):
  ####
  #
  # Check the status of data file.
  #
  # Parameters:
  #      DATAFILE: File (full path) to be checked
  #
  # Return:
  #      0 - update of DATAFILE is not required
  #      1 - update of DATAFILE is required
  #
  ####
  logger.debug('Enter function')
  _return_code_ = 0
  logger.debug('Data file ==> ' + DATAFILE)

  if os.path.exists(DATAFILE):
    # The DATAFILE exists.
    logger.debug('\'' + DATAFILE + '\' exists.')

    if os.path.getsize(DATAFILE) != 0:
      # The DATAFILE is not empty.
      logger.debug('\'' + DATAFILE + '\' is not empty.')
    else:
      # The DATAFILE is empty.
      logger.debug('\'' + DATAFILE + '\' is empty.')
      _return_code_ = 1

    # Get the value (seconds since epoch) of the last modification time.
    _last_update_ = os.path.getmtime(DATAFILE)

    if _last_update_ > time.time() - (1 * vars.__day__):
      # File was updated less than 24 hours ago, nothing to do
      logger.debug('\'' + DATAFILE + '\' last update: ' + time.strftime("%Y%m%d_%H%M%S", time.localtime(_last_update_)))
    else:
      # File was updated 24 hours (or more) ago
      logger.debug('\'' + DATAFILE + '\' last update: ' + time.strftime("%Y%m%d_%H%M%S", time.localtime(_last_update_)))
      _return_code_ = 1

  else:
    # The DATAFILE does not exist.
    logger.debug('\'' + DATAFILE + '\' does not exist.')
    _return_code_ = 1

  logger.debug('Exit function')
  return _return_code_


def PVRIPTVSimpleClientIntegration_init_m3u_file():
  logger.debug('Enter function')
  
  # Read the user preferences stored in the addon configuration
  functions.read_AddonSettings(MyServiceAddon)
  
  if not os.path.exists(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__ ):
    os.makedirs(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__)

  _m3u_file_ = os.path.join(MyServiceAddon_DataDir, vars.__PVRIPTVSimpleClientIntegration_DataDir__, vars.__PVRIPTVSimpleClientIntegration_m3u_FileName__)
  logger.debug('m3u file: ' + _m3u_file_)

  _update_required_ = PVRIPTVSimpleClientIntegration_check_data_file(_m3u_file_)
  logger.debug('_update_required_ ==> ' + str(_update_required_))
  
  if _update_required_ == 1:
    PVRIPTVSimpleClientIntegration_update_m3u_file()

  logger.debug('Exit function')


def PVRIPTVSimpleClientIntegration_update_m3u_file():
  logger.debug('Enter function')

  # Read the user preferences stored in the addon configuration
  functions.read_AddonSettings(MyServiceAddon)

  _current_channel_number_ = 1
  
  if not os.path.exists(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__ ):
    os.makedirs(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__)
    
  _m3u_file_ = os.path.join(MyServiceAddon_DataDir, vars.__PVRIPTVSimpleClientIntegration_DataDir__, vars.__PVRIPTVSimpleClientIntegration_m3u_FileName__)
  logger.debug('_m3u_file_ = ' + _m3u_file_)
  
  _tmp_m3u_file_ = os.path.join(MyServiceAddon_DataDir, vars.__PVRIPTVSimpleClientIntegration_DataDir__, vars.__PVRIPTVSimpleClientIntegration_m3u_FileName__ + '.tmp')
  logger.debug('_tmp_m3u_file_ = ' + _tmp_m3u_file_)
  
  if functions.has_accounts_enabled() == 'true':
    logger.debug('Addon has at least one account enabled')
    
    _data_file_ = open(_tmp_m3u_file_, 'w')
    _data_file_.write("#EXTM3U tvg-shift=0" + "\n")
    _data_file_.close()
  
    _current_channel_number_ = functions.digionline__updateM3Ufile(_tmp_m3u_file_, _current_channel_number_, vars.__ServiceID__, vars.__ServiceSession__, MyServiceAddon_DataDir)

    logger.debug('_current_channel_number_ = ' + str(_current_channel_number_))
 
    os.rename(_tmp_m3u_file_, _m3u_file_)

  else:
    logger.debug('Addon has no accounts enabled')

  logger.debug('Exit function')



def PVRIPTVSimpleClientIntegration_init_EPG_file():
  logger.debug('Enter function')

  # Read the user preferences stored in the addon configuration
  functions.read_AddonSettings(MyServiceAddon)
  
  if not os.path.exists(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__ ):
    os.makedirs(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__)

  _epg_file_ = os.path.join(MyServiceAddon_DataDir, vars.__PVRIPTVSimpleClientIntegration_DataDir__, vars.__PVRIPTVSimpleClientIntegration_EPG_FileName__)
  logger.debug('epg file: ' + _epg_file_)

  _update_required_ = PVRIPTVSimpleClientIntegration_check_data_file(_epg_file_)
  logger.debug('_update_required_ ==> ' + str(_update_required_))
  
  if _update_required_ == 1:
    PVRIPTVSimpleClientIntegration_update_EPG_file()

  logger.debug('Exit function')



def PVRIPTVSimpleClientIntegration_update_EPG_file():
  logger.debug('Enter function')

  # Read the user preferences stored in the addon configuration
  functions.read_AddonSettings(MyServiceAddon)

  if not os.path.exists(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__ ):
    os.makedirs(MyServiceAddon_DataDir + '/' + vars.__PVRIPTVSimpleClientIntegration_DataDir__)
      
  _epg_file_ = os.path.join(MyServiceAddon_DataDir, vars.__PVRIPTVSimpleClientIntegration_DataDir__, vars.__PVRIPTVSimpleClientIntegration_EPG_FileName__)
  logger.debug('_epg_file_ = ' + _epg_file_)

  _tmp_epg_file_ = os.path.join(MyServiceAddon_DataDir, vars.__PVRIPTVSimpleClientIntegration_DataDir__, vars.__PVRIPTVSimpleClientIntegration_EPG_FileName__ + '.tmp')

  logger.debug('_tmp_epg_file_ = ' + _tmp_epg_file_)

  if functions.has_accounts_enabled() == 'true':
    logger.debug('Addon has at least one account enabled')
      
    _data_file_ = open(_tmp_epg_file_, 'w')
    _data_file_.write("<?xml version=\"1.0\" encoding=\"utf-8\" ?>" + "\n")
    _data_file_.write("<tv>" + "\n")
    _data_file_.close()
  
    functions.digionline__updateEPGfile(_tmp_epg_file_, vars.__ServiceID__, vars.__ServiceSession__, MyServiceAddon_DataDir)

    _data_file_ = open(_tmp_epg_file_, 'a')
    _data_file_.write("</tv>" + "\n")
    _data_file_.close()
    os.rename(_tmp_epg_file_, _epg_file_)

  else:
    logger.debug('Addon has no accounts enabled')
    
  logger.debug('Exit function')


if __name__ == '__main__':
  logger.debug('Enter __main__ ')
  logger.debug('=== SYSINFO ===  Addon version: ' + str(__AddonVersion__))
  logger.debug('=== SYSINFO ===  System.BuildVersion: ' + str(__SystemBuildVersion__))
  logger.debug('=== SYSINFO ===  System.BuildDate: ' + str(__SystemBuildDate__))

  # Read the user preferences stored in the addon configuration
  functions.read_AddonSettings(MyServiceAddon)

  logger.debug('Waiting 15 seconds for network to stabilize')
  time.sleep(15)
  logger.debug('Done waiting 15 seconds for network to stabilize')

  schedule_jobs()
  schedule.every().minute.at(":05").do(schedule_jobs)
  
  logger.debug('Finished scheduling jobs')

  monitor = xbmc.Monitor()  
  while not monitor.abortRequested():
    # Sleep/wait for abort for 300 seconds
    if monitor.waitForAbort(1):
      # Abort was requested while waiting. We should exit
      logger.debug('Abort was requested while waiting.')
      break
    schedule.run_pending()
  logger.debug('Exit __main__ ')

