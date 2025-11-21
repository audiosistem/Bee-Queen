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

import sys
from urllib import urlencode
from urlparse import parse_qsl
import xbmcgui
import xbmcplugin
import os
import re
import json
import xbmcaddon
import requests
import logging
import logging.handlers
import inputstreamhelper
import resources.lib.common.vars as vars
import resources.lib.common.functions as functions

# The cookielib module has been renamed to http.cookiejar in Python 3
import cookielib
# import http.cookiejar


__SystemBuildVersion__ = xbmc.getInfoLabel('System.BuildVersion')
__SystemBuildDate__ = xbmc.getInfoLabel('System.BuildDate')

# Kodi uses the following sys.argv arguments:
# [0] - The base URL for this add-on, e.g. 'plugin://plugin.video.demo1/'.
# [1] - The process handle for this add-on, as a numeric string.
# [2] - The query string passed to this add-on, e.g. '?foo=bar&baz=quux'.

# Get the plugin url in plugin:// notation.
vars.__plugin_url__ = sys.argv[0]

# Get the plugin handle as an integer number.
vars.__handle__ = int(sys.argv[1])

MyAddon = xbmcaddon.Addon(id=vars.__AddonID__)

# The version of the runing Addon
__AddonVersion__ = MyAddon.getAddonInfo('version')

# Initialize the Addon data directory
MyAddon_DataDir = xbmc.translatePath(MyAddon.getAddonInfo('profile'))
if not os.path.exists(MyAddon_DataDir):
    os.makedirs(MyAddon_DataDir)

# Read the user preferences stored in the addon configuration
functions.read_AddonSettings(MyAddon)

# Log file name
addon_logfile_name = os.path.join(MyAddon_DataDir, vars.__AddonLogFilename__)

# Configure logging
if vars.__config_DebugEnabled__ == 'true':
  logging.basicConfig(level=logging.DEBUG)
else:
  logging.basicConfig(level=logging.INFO)

#logger = logging.getLogger('plugin.video.DigiOnline.log')
logger = logging.getLogger(vars.__AddonID__)
logger.propagate = False

# Create a rotating file handler
# TODO: Extend the settings.xml to allow the user to choose the values for maxBytes and backupCount
# TODO: Set the values for maxBytes and backupCount to values defined in the addon settings
handler = logging.handlers.RotatingFileHandler(addon_logfile_name, mode='a', maxBytes=104857600, backupCount=2, encoding=None, delay=False)
if vars.__config_DebugEnabled__ == 'true':
  handler.setLevel(logging.DEBUG)
else:
  handler.setLevel(logging.INFO)

# Create a logging format to be used
formatter = logging.Formatter('%(asctime)s %(funcName)s %(levelname)s: %(message)s', datefmt='%Y%m%d_%H%M%S')
handler.setFormatter(formatter)

# add the file handler to the logger
logger.addHandler(handler)

logger.debug('[ Addon settings ] __config_DebugEnabled__ = ' + str(vars.__config_DebugEnabled__))
logger.debug('[ Addon settings ] __config_ShowTitleInChannelList__ = ' + str(vars.__config_ShowTitleInChannelList__))
logger.debug('[ Addon settings ] __categoriesCachedDataRetentionInterval__ = ' + str(vars.__categoriesCachedDataRetentionInterval__))
logger.debug('[ Addon settings ] __channelsCachedDataRetentionInterval__ = ' + str(vars.__channelsCachedDataRetentionInterval__))
logger.debug('[ Addon settings ] __EPGDataCachedDataRetentionInterval__ = ' + str(vars.__EPGDataCachedDataRetentionInterval__))


# Initialize the __AddonCookieJar__ variable
functions.init_AddonCookieJar(vars.__AddonID__, MyAddon_DataDir)

# Start a new requests session and initialize the cookiejar
vars.__AddonSession__ = requests.Session()

# Put all session cookeis in the cookiejar
vars.__AddonSession__.cookies = vars.__AddonCookieJar__


def check_defaults_DigiOnline_account():
  logger.debug('Enter function')

  vars.__config_AccountUser__ = MyAddon.getSetting('AccountUser')
  while vars.__config_AccountUser__ == '__DEFAULT_USER__':
      logger.debug('Default settings found.', 'Please configure the Authentication User to be used with this addon.')
      xbmcgui.Dialog().ok('Default settings found.', 'Please configure the Authentication User to be used with this addon.')
      MyAddon.openSettings()
      vars.__config_AccountUser__ = MyAddon.getSetting('AccountUser')

  vars.__config_AccountPassword__ = MyAddon.getSetting('AccountPassword')
  while vars.__config_AccountPassword__ == '__DEFAULT_PASSWORD__':
      logger.debug('Default settings found', 'Please configure the Authenticatin Password to be used with this addon.')
      xbmcgui.Dialog().ok('Default settings found', 'Please configure the Authenticatin Password to be used with this addon.')
      MyAddon.openSettings()
      vars.__config_AccountPassword__ = MyAddon.getSetting('AccountPassword')

  logger.debug('Exit function')

def router(paramstring):
  ####
  #
  # Router function that calls other functions depending on the provided paramster
  #
  # Parameters:
  #      paramstring: URL encoded plugin paramstring
  #
  ####

  logger.debug('Enter function')

  # Parse a URL-encoded paramstring to the dictionary of {<parameter>: <value>} elements
  params = dict(parse_qsl(paramstring))

  # Check the parameters passed to the plugin
  if params:
      if params['action'] == 'list_channels':
        # Display the list of channels in a provided category.
        functions.digionline__listChannels(params['category_name'], params['channel_list'], vars.__AddonID__, vars.__AddonSession__, MyAddon_DataDir)
      elif params['action'] == 'play':
        # Play a video from the provided URL.
        functions.digionline__playVideo(params['channel_id'], vars.__AddonID__, vars.__AddonSession__, MyAddon_DataDir)
      else:
        # Raise an exception if the provided paramstring does not contain a supported action
        # This helps to catch coding errors,
        raise ValueError('Invalid paramstring: {0}!'.format(paramstring))
  else:
    # If the plugin is called from Kodi UI without any parameters:

    # Get the details of the configured DigiOnline.ro account.
    check_defaults_DigiOnline_account()

    # Display the list of available video categories
    functions.digionline__listCategories(vars.__AddonID__, vars.__AddonSession__, MyAddon_DataDir)

  # TODO: Logout from DigiOnline for this session
  # TODO: do_logout()

  logger.debug('Exit function')


if __name__ == '__main__':
  logger.debug('Enter function')
  logger.debug('=== SYSINFO ===  Addon version: ' + str(__AddonVersion__))
  logger.debug('=== SYSINFO ===  System.BuildVersion: ' + str(__SystemBuildVersion__))
  logger.debug('=== SYSINFO ===  System.BuildDate: ' + str(__SystemBuildDate__))
  
  # Call the router function and pass the plugin call parameters to it.
  router(sys.argv[2][1:])

  logger.debug('Exit function')

