#
#
#    Copyright (C) 2021  Alin Cretu
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
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import logging
import http.cookiejar
import re
from datetime import datetime
from datetime import timedelta
import time
import json
import uuid
import inputstreamhelper
import resources.lib.common.vars as common_vars
import resources.lib.common.functions as common_functions


def init_AddonCookieJar(NAME, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  # File containing the session cookies
  cookies_file = os.path.join(DATA_DIR, common_vars.__voyo_CookiesFilename__)
  common_vars.__logger__.debug('[ Addon cookies file ] cookies_file = ' + str(cookies_file))
  common_vars.__voyo_CookieJar__ = http.cookiejar.MozillaCookieJar(cookies_file)

  # If it doesn't exist already, create a new file where the cookies should be saved
  if not os.path.exists(cookies_file):
    common_vars.__voyo_CookieJar__.save()
    common_vars.__logger__.debug('[ Addon cookiefile ] Created cookiejar file: ' + str(cookies_file))

  # Load any cookies saved from the last run
  common_vars.__voyo_CookieJar__.load()
  common_vars.__logger__.debug('[ Addon cookiejar ] Loaded cookiejar from file: ' + str(cookies_file))


def voyo__check_DefaultUserSettings(NAME):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __ret__ = 0
  common_vars.__logger__.debug('1. __ret__ = ' + str(__ret__))

  if str(common_vars.__config_voyo_Username__) == "__DEFAULT_USER__":
    __ret__ = 1
    common_vars.__logger__.debug('2. __ret__ = ' + str(__ret__))

  if str(common_vars.__config_voyo_Username__) == "":
    __ret__ = 1
    common_vars.__logger__.debug('3. __ret__ = ' + str(__ret__))

  if str(common_vars.__config_voyo_Password__) == "__DEFAULT_PASSWORD__":
    __ret__ = 1
    common_vars.__logger__.debug('4. __ret__ = ' + str(__ret__))

  if str(common_vars.__config_voyo_Password__) == "":
    __ret__ = 1
    common_vars.__logger__.debug('5. __ret__ = ' + str(__ret__))


  common_vars.__logger__.debug(' __ret__ = ' + str(__ret__))
  common_vars.__logger__.debug('Exit function')

  return __ret__


def voyo__write_stateData(STATE_DATA, NAME, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __state_file__ = os.path.join(DATA_DIR, common_vars.__voyo_StateFilename__)
  common_vars.__logger__.debug('Writting to \'' + __state_file__ +'\'')
  _file_ = open(__state_file__, 'w')
  json.dump(STATE_DATA, _file_)
  _file_.close()


def voyo__read_stateData(NAME, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __state_file__ = os.path.join(DATA_DIR, common_vars.__voyo_StateFilename__)

  if not os.path.exists(__state_file__) or os.path.getsize(__state_file__) == 0:
    common_vars.__logger__.debug('\'' + __state_file__ +'\' does not exist or it is empty.')

    _read_data_ = {}
    _read_data_['exit_status'] = 1
    _read_data_['state_data'] = ""
    __ret__ = _read_data_

  else:
    common_vars.__logger__.debug('Reading from \'' + __state_file__ +'\'')
    _file_ = open(__state_file__, 'r')
    _data_ = json.load(_file_)
    _file_.close()

    _read_data_ = {}
    _read_data_['exit_status'] = 0
    _read_data_['state_data'] = _data_
    __ret__ = _read_data_

  common_vars.__logger__.debug('Return data: ' + str(__ret__))
  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__init_stateData(NAME, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  common_vars.__logger__.debug('Initializing stateData...')

  __deviceID__ = str(uuid.uuid4())
  common_vars.__logger__.debug('Generated deviceID: ' + __deviceID__)

  __metadata__ = {}
  __metadata__['version'] = "1"

  __token__ = {}
  __token__['token_type'] = ""
  __token__['access_token'] = ""


  __data__ = {}
  __data__['deviceID'] = __deviceID__
  __data__['token'] = __token__

  __state_data__ = {}
  __state_data__['metadata'] = __metadata__
  __state_data__['data'] = __data__

  voyo__write_stateData(__state_data__, NAME, DATA_DIR)

  common_vars.__logger__.debug('Initialized stateData: ' + str(__state_data__))
  common_vars.__logger__.debug('Exit function')


def voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  # State data not yet initialized or it needs to be re-initialized
  # Device ID not yet initialized or it needs to be re-initialized
  if __rsd__['exit_status'] != 0 or int(__rsd__['state_data']['metadata']['version']) < 1 or __rsd__['state_data']['data']['deviceID'] == "":
    voyo__init_stateData(NAME, DATA_DIR)
    __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

    __new_token__ = voyo__API__auth_sessions(NAME, COOKIEJAR, SESSION, DATA_DIR)
    common_vars.__logger__.debug('__new_token__ = ' + str(__new_token__))

    if 'code' in __new_token__:
      xbmcgui.Dialog().ok('[voyo.ro] => Authentication error (code ' + str(__new_token__['code']) + ' )', __new_token__['message'])
      common_vars.__logger__.debug('[voyo.ro] => Authentication error code: ' + str(__new_token__['code']))
      common_vars.__logger__.debug('[voyo.ro] => Authentication error message: ' + __new_token__['message'])
      common_vars.__logger__.debug('Exit function')
      return

    else:
      __rsd__ = voyo__read_stateData(NAME, DATA_DIR)
      __rsd__['state_data']['data']['token']['token_type'] = 'Bearer'
      __rsd__['state_data']['data']['token']['access_token'] = __new_token__['credentials']['accessToken']
      voyo__write_stateData(__rsd__['state_data'], NAME, DATA_DIR)

  # Token not yet initialized or it needs to be re-initialized
  if __rsd__['state_data']['data']['token']['token_type'] == "" or __rsd__['state_data']['data']['token']['access_token'] == "":
    common_vars.__logger__.debug('Token not yet initialized or it needs to be re-initialized')
    __new_token__ = voyo__API__auth_sessions(NAME, COOKIEJAR, SESSION, DATA_DIR)
    common_vars.__logger__.debug('__new_token__ = ' + str(__new_token__))

    if 'code' in __new_token__:
      xbmcgui.Dialog().ok('[voyo.ro] => Authentication error (code ' + str(__new_token__['code']) + ' )', __new_token__['message'])
      common_vars.__logger__.debug('[voyo.ro] => Authentication error code: ' + str(__new_token__['meta']['error']['code']))
      common_vars.__logger__.debug('[voyo.ro] => Authentication error message: ' + __new_token__['meta']['error']['message'])
      common_vars.__logger__.debug('Exit function')
      return

    else:
      __rsd__ = voyo__read_stateData(NAME, DATA_DIR)
      __rsd__['state_data']['data']['token']['token_type'] = 'Bearer'
      __rsd__['state_data']['data']['token']['access_token'] = __new_token__['credentials']['accessToken']
      voyo__write_stateData(__rsd__['state_data'], NAME, DATA_DIR)

  common_vars.__logger__.debug('Exit function')


def voyo__API__auth_sessions(NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/auth-sessions'

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Content-Type': 'application/json',
    'Accep-Language': 'en-US',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID']    
  }

  # Setup payload for the request
  MyPayloadData = {
      "username": common_vars.__config_voyo_Username__,
      "password": common_vars.__config_voyo_Password__
    }

  MyPayloadData_log = {
      "username": common_vars.__config_voyo_Username__,
      "password": "******************"
    }

  common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
  common_vars.__logger__.debug('URL: ' + __URL__)
  common_vars.__logger__.debug('Method: POST')
  common_vars.__logger__.debug('Payload: ' + str(MyPayloadData_log))

  # Send the POST request
  _request_ = SESSION.post(__URL__, headers=MyHeaders, data=json.dumps(MyPayloadData))

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)

  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__API__overview(CATEGORY_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/overview'

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Content-Type': 'application/json',
    'Accep-Language': 'en-US',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID'],
    'Authorization': __rsd__['state_data']['data']['token']['token_type'] + ' ' + __rsd__['state_data']['data']['token']['access_token']
  }

  common_vars.__logger__.debug('CATEGORY_ID: ' + CATEGORY_ID)
  
  if CATEGORY_ID.upper() == "NONE":
    common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
    common_vars.__logger__.debug('URL: ' + __URL__)
    common_vars.__logger__.debug('Method: GET')

    # Send the GET request
    _request_ = SESSION.get(__URL__, headers=MyHeaders)

  else:
    # Setup payload for the request
    MyParams = {
      "category": CATEGORY_ID
    }

    common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
    common_vars.__logger__.debug('URL: ' + __URL__)
    common_vars.__logger__.debug('Method: GET')
    common_vars.__logger__.debug('Parameters: ' + str(MyParams))

    # Send the GET request
    _request_ = SESSION.get(__URL__, headers=MyHeaders, params=MyParams)

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)
  
  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__API__get_category_content_by_page(CATEGORY_ID, PAGE_NUM, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/content/filter'

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Content-Type': 'application/json',
    'Accep-Language': 'en-US',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID'],
    'Authorization': __rsd__['state_data']['data']['token']['token_type'] + ' ' + __rsd__['state_data']['data']['token']['access_token']
  }

  # Setup payload for the request
  MyParams = {
    'category': CATEGORY_ID,
    'page': PAGE_NUM,
    'sort': 'title-asc'
  }
 
  common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
  common_vars.__logger__.debug('URL: ' + __URL__)
  common_vars.__logger__.debug('Method: GET')
  common_vars.__logger__.debug('Parameters: ' + str(MyParams))

  # Send the GET request
  _request_ = SESSION.get(__URL__, headers=MyHeaders, params=MyParams)

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)
  
  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__API__plays(CHANNEL_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/content/'+ CHANNEL_ID +'/plays'

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Accep-Language': 'en-US',
    'Content-Type': 'application/json',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID'],
    'Authorization': __rsd__['state_data']['data']['token']['token_type'] + ' ' + __rsd__['state_data']['data']['token']['access_token']    
  }

  # Setup payload for the request
  MyParams = {
      'acceptVideo': 'dash,drm-widevine,hls,dai'
    }

  common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
  common_vars.__logger__.debug('URL: ' + __URL__)
  common_vars.__logger__.debug('Method: POST')
  common_vars.__logger__.debug('Parameters: ' + str(MyParams))

  # Send the POST request
  _request_ = SESSION.post(__URL__, headers=MyHeaders, params=MyParams)

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)
  
  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__API__getEPG_by_date(DATE, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/epg/program'

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Content-Type': 'application/json',
    'Accep-Language': 'en-US',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID'],
    'Authorization': __rsd__['state_data']['data']['token']['token_type'] + ' ' + __rsd__['state_data']['data']['token']['access_token']
  }
  
  # Setup payload for the request
  MyParams = {
    "date": DATE
  }

  common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
  common_vars.__logger__.debug('URL: ' + __URL__)
  common_vars.__logger__.debug('Method: GET')
  common_vars.__logger__.debug('Parameters: ' + str(MyParams))

  # Send the GET request
  _request_ = SESSION.get(__URL__, headers=MyHeaders, params=MyParams)

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)
  
  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__API__get_tvshow_details(TVSHOW_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/tvshow/' + TVSHOW_ID

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Content-Type': 'application/json',
    'Accep-Language': 'en-US',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID'],
    'Authorization': __rsd__['state_data']['data']['token']['token_type'] + ' ' + __rsd__['state_data']['data']['token']['access_token']
  }

  common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
  common_vars.__logger__.debug('URL: ' + __URL__)
  common_vars.__logger__.debug('Method: GET')

  # Send the GET request
  _request_ = SESSION.get(__URL__, headers=MyHeaders)

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)
  
  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__API__get_tvshow_season_details(TVSHOW_ID, SEASON_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  __rsd__ = voyo__read_stateData(NAME, DATA_DIR)

  __URL__ = 'https://apivoyo.cms.protvplus.ro/api/v1/tvshow/' + TVSHOW_ID

  # Setup headers for the request
  MyHeaders = {
    'User-Agent': common_vars.__voyo_API_userAgent__,
    'Content-Type': 'application/json',
    'Accep-Language': 'en-US',
    'x-devicetype': common_vars.__voyo_x_devicetype__,
    'x-devicesubtype': common_vars.__voyo_x_devicesubtype__,
    'x-devicemanufacturer': common_vars.__voyo_x_devicemanufacturer__,
    'x-devicemodel': common_vars.__voyo_x_devicemodel__,
    'x-deviceos': common_vars.__voyo_x_deviceos__,
    'x-deviceosversion': common_vars.__voyo_x_deviceosversion__,
    'x-version': common_vars.__voyo_x_version__,
    'x-app_appbuildnumber': common_vars.__voyo_x_app_appbuildnumber__,
    'x-devicename': common_vars.__voyo_x_devicename__,
    'x-device-id': __rsd__['state_data']['data']['deviceID'],
    'Authorization': __rsd__['state_data']['data']['token']['token_type'] + ' ' + __rsd__['state_data']['data']['token']['access_token']
  }

  # Setup payload for the request
  MyParams = {
    "season": SEASON_ID
  }

  common_vars.__logger__.debug('Headers: ' + str(MyHeaders))
  common_vars.__logger__.debug('URL: ' + __URL__)
  common_vars.__logger__.debug('Method: GET')
  common_vars.__logger__.debug('Parameters: ' + str(MyParams))

  # Send the GET request
  _request_ = SESSION.get(__URL__, headers=MyHeaders, params=MyParams)

  # Save cookies for later use.
  #COOKIEJAR.save(ignore_discard=True)
  
  common_vars.__logger__.debug('Received status code: ' + str(_request_.status_code))
  common_vars.__logger__.debug('Received headers: ' + str(_request_.headers))
  common_vars.__logger__.debug('Received data: ' + _request_.content.decode())

  __ret__ = json.loads(_request_.content.decode())

  common_vars.__logger__.debug('Exit function')
  return __ret__


def voyo__listCategories(NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)
  
  __overview__ = voyo__API__overview('None', NAME, COOKIEJAR, SESSION, DATA_DIR)

  for category_data in __overview__['categories']:
    common_vars.__logger__.debug('Category:  id = \'' + category_data['category']['id'] + '\', Name = \'' + category_data['category']['name'] + '\', Title = \'' + category_data['category']['name'] + '\'')

    # Filer out some categories
    # ID: 2     -> Home
    # ID: 243   -> Noutăți
    if category_data['category']['id'] not in ['2', '243']:
      # Create a list item with a text label and a thumbnail image.
      list_item = xbmcgui.ListItem(label=category_data['category']['name'])

      # Set additional info for the list item.
      # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
      # 'mediatype' is needed for a skin to display info for this ListItem correctly.
      list_item.setInfo('video', {'title': category_data['category']['name'],
                                  'genre': category_data['category']['name'],
                                  'mediatype': 'video'})

      # Create a URL for a plugin recursive call.
      # Example: plugin://plugin.video.example/?action=listing&category=filme
      if category_data['category']['type'] == 'live':
        url = common_functions.get_url(account='voyo.ro', action='list_channels', id_category=category_data['category']['id'], category_name=category_data['category']['name'])
      if category_data['category']['type'] == 'page':
        #url = common_functions.get_url(account='voyo.ro', action='list_category_sections', id_category=category_data['category']['id'], category_name=category_data['category']['name'])
        url = common_functions.get_url(account='voyo.ro', action='list_category_content', id_category=category_data['category']['id'], category_name=category_data['category']['name'], category_page=1)

      common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

      # This means that this item opens a sub-list of lower level items.
      is_folder = True

      # Add our item to the Kodi virtual folder listing.
      xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)
    

  # Add a sort method for the virtual folder items (alphabetically, ignore articles)
  # See: https://romanvm.github.io/Kodistubs/_autosummary/xbmcplugin.html
  xbmcplugin.addSortMethod(int(common_vars.__handle__), xbmcplugin.SORT_METHOD_LABEL)

  # Finish creating a virtual folder.
  xbmcplugin.endOfDirectory(int(common_vars.__handle__))

  common_vars.__logger__.debug('Exit function')


def voyo__listLiveTVChannels(CATEGORY_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)

  __overview__ = voyo__API__overview(CATEGORY_ID, NAME, COOKIEJAR, SESSION, DATA_DIR)
  
  if __overview__['type'] == 'livetv': 
    for channel_data in __overview__['liveTvs']:
      common_vars.__logger__.debug('Channel ID: ' + channel_data['id'])
      common_vars.__logger__.debug('Channel name: ' + channel_data['name'])
      common_vars.__logger__.debug('Channel logo: ' + channel_data['logoTransparent'])

      # Create a list item with a text label and a thumbnail image.
      list_item = xbmcgui.ListItem(label=channel_data['name'])

      # Set additional info for the list item.
      # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
      # 'mediatype' is needed for skin to display info for this ListItem correctly.
      list_item.setInfo('video', {'title': channel_data['name'],
                                  'genre': 'General',
                                  'mediatype': 'video'})

      # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
      list_item.setArt({'thumb': channel_data['logoTransparent']})

      # Set 'IsPlayable' property to 'true'.
      # This is mandatory for playable items!
      list_item.setProperty('IsPlayable', 'true')

      # Create a URL for a plugin recursive call.
      # Example: plugin://plugin.video.example/?action=play&channel_endpoint=/filme/tnt&channel_metadata=...
      url = common_functions.get_url(action='play', account='voyo.ro', channel_name=channel_data['name'], channel_id=channel_data['id'])
      common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

      # This means that this item won't open any sub-list.
      is_folder = False

      # Add our item to the Kodi virtual folder listing.
      xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)


  # Add a sort method for the virtual folder items (alphabetically, ignore articles)
  xbmcplugin.addSortMethod(int(common_vars.__handle__), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

  # Finish creating a virtual folder.
  xbmcplugin.endOfDirectory(int(common_vars.__handle__))

  common_vars.__logger__.debug('Exit function')


def voyo__listCategoryContent(CATEGORY_ID, CATEGORY_NAME, CATEGORY_PAGE, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)
  
  __page_content__ = voyo__API__get_category_content_by_page(CATEGORY_ID, CATEGORY_PAGE, NAME, COOKIEJAR, SESSION, DATA_DIR)
  
  #__all_category_items__ = []

  # Add all elements from list '__page_1_content__['items']' to the end of list '__all_category_items__'
  #__all_category_items__.extend(__page_1_content__['items'])

  for listing_modifier in __page_content__['availableListingModifiers']:
    if listing_modifier['type'] == 'listing-modifier-page':
      __num_pages__ = len(listing_modifier['options'])
      common_vars.__logger__.debug('Number of pages: ' + str(__num_pages__))

  for item in __page_content__['items']:
    common_vars.__logger__.debug('Item ID: ' + item['id'])
    common_vars.__logger__.debug('Item name: ' + item['title'])
    common_vars.__logger__.debug('Item logo: ' + item['image'])
    common_vars.__logger__.debug('Item type: ' + item['type'])

    if item['type'] in ['movie', 'episode']:

      # Create a list item with a text label and a thumbnail image.
      list_item = xbmcgui.ListItem(label=item['title'])

      # Set additional info for the list item.
      # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
      # 'mediatype' is needed for skin to display info for this ListItem correctly.
      list_item.setInfo('video', {'title': item['title'],
                                  'genre': 'General',
                                  'mediatype': 'video'})

      # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
      list_item.setArt({'thumb': item['image']})

      # Set 'IsPlayable' property to 'true'.
      # This is mandatory for playable items!
      list_item.setProperty('IsPlayable', 'true')

      # Create a URL for a plugin recursive call.
      # Example: plugin://plugin.video.example/?action=play&channel_endpoint=/filme/tnt&channel_metadata=...
      url = common_functions.get_url(action='play', account='voyo.ro', channel_name=item['title'], channel_id=item['id'])
      common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

      # This means that this item won't open any sub-list.
      is_folder = False

      # Add our item to the Kodi virtual folder listing.
      xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)
            

    if item['type'] == 'tvshow':
            
      # Create a list item with a text label and a thumbnail image.
      list_item = xbmcgui.ListItem(label=item['title'])

      # Set additional info for the list item.
      # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
      # 'mediatype' is needed for skin to display info for this ListItem correctly.
      list_item.setInfo('video', {'title': item['title'],
                                  'genre': 'General',
                                  'mediatype': 'video'})

      # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
      list_item.setArt({'thumb': item['image']})
            

      # Create a URL for a plugin recursive call.
      # Example: plugin://plugin.video.example/?action=listing&category=filme
      url = common_functions.get_url(account='voyo.ro', action='list_tvshow_content', tvshow_id=item['id'], tvshow_name=item['title'])
      common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

      # This means that this item opens a sub-list of lower level items.
      is_folder = True

      # Add our item to the Kodi virtual folder listing.
      xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)


  if int(CATEGORY_PAGE) < int(__num_pages__):

    # Create a list item with a text label and a thumbnail image.
    list_item = xbmcgui.ListItem(label='Next Page >>>')

    # Set additional info for the list item.
    # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
    # 'mediatype' is needed for skin to display info for this ListItem correctly.
    list_item.setInfo('video', {'title': 'Next Page >>>',
                                'genre': 'General',
                                'mediatype': 'video'})

    # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
    #list_item.setArt({'thumb': item['image']})

    # Create a URL for a plugin recursive call.
    # Example: plugin://plugin.video.example/?action=listing&category=filme
    url = common_functions.get_url(account='voyo.ro', action='list_category_content', id_category=CATEGORY_ID, category_name=CATEGORY_NAME, category_page=(int(CATEGORY_PAGE) + 1))
    common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

    # This means that this item opens a sub-list of lower level items.
    is_folder = True

    # Add our item to the Kodi virtual folder listing.
    xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)


  # Add a sort method for the virtual folder items (alphabetically, ignore articles)
  # See: https://romanvm.github.io/Kodistubs/_autosummary/xbmcplugin.html
  #xbmcplugin.addSortMethod(int(common_vars.__handle__), xbmcplugin.SORT_METHOD_LABEL)

  # Finish creating a virtual folder.
  xbmcplugin.endOfDirectory(int(common_vars.__handle__))

  common_vars.__logger__.debug('Exit function')


def voyo__list_tvshow_content(TVSHOW_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)

  __tvshow_details__ = voyo__API__get_tvshow_details(TVSHOW_ID, NAME, COOKIEJAR, SESSION, DATA_DIR)
  
  if __tvshow_details__['seasons']:
    for season_data in __tvshow_details__['seasons']:
      common_vars.__logger__.debug('Season ID: ' + season_data['id'])
      common_vars.__logger__.debug('Season name name: ' + season_data['name'])

      # Create a list item with a text label and a thumbnail image.
      list_item = xbmcgui.ListItem(label=season_data['name'])

      # Set additional info for the list item.
      # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
      # 'mediatype' is needed for skin to display info for this ListItem correctly.
      list_item.setInfo('video', {'title': season_data['name'],
                                  'genre': 'General',
                                  'mediatype': 'video'})

      # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
      #list_item.setArt({'thumb': episode_data['image']})

      # Create a URL for a plugin recursive call.
      # Example: plugin://plugin.video.example/?action=play&channel_endpoint=/filme/tnt&channel_metadata=...
      url = common_functions.get_url(action='list_tvshow_season_episodes', account='voyo.ro', tvshow_id=TVSHOW_ID, season_id=season_data['id'])
      common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

      # This means that this item won't open any sub-list.
      is_folder = True

      # Add our item to the Kodi virtual folder listing.
      xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)

  else:
    for section_data in __tvshow_details__['sections']:
      for episode_data in section_data['content']:
        common_vars.__logger__.debug('Episode ID: ' + episode_data['id'])
        common_vars.__logger__.debug('Episode name: ' + episode_data['title'])
        common_vars.__logger__.debug('Episode logo: ' + episode_data['image'])

        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=episode_data['title'])

        # Set additional info for the list item.
        # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
        # 'mediatype' is needed for skin to display info for this ListItem correctly.
        list_item.setInfo('video', {'title': episode_data['title'],
                                    'genre': 'General',
                                    'mediatype': 'video'})

        # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
        list_item.setArt({'thumb': episode_data['image']})

        # Set 'IsPlayable' property to 'true'.
        # This is mandatory for playable items!
        list_item.setProperty('IsPlayable', 'true')

        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=play&channel_endpoint=/filme/tnt&channel_metadata=...
        url = common_functions.get_url(action='play', account='voyo.ro', channel_name=episode_data['title'], channel_id=episode_data['id'])
        common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

        # This means that this item won't open any sub-list.
        is_folder = False

        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)


  # Add a sort method for the virtual folder items (alphabetically, ignore articles)
  xbmcplugin.addSortMethod(int(common_vars.__handle__), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

  # Finish creating a virtual folder.
  xbmcplugin.endOfDirectory(int(common_vars.__handle__))

  common_vars.__logger__.debug('Exit function')


def voyo__list_tvshow_season_episodes(TVSHOW_ID, SEASON_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)

  __tvshow_details__ = voyo__API__get_tvshow_season_details(TVSHOW_ID, SEASON_ID, NAME, COOKIEJAR, SESSION, DATA_DIR)

  for section_data in __tvshow_details__['sections']:
    for episode_data in section_data['content']:
      common_vars.__logger__.debug('Episode ID: ' + episode_data['id'])
      common_vars.__logger__.debug('Episode name: ' + episode_data['title'])
      common_vars.__logger__.debug('Episode logo: ' + episode_data['image'])

      # Create a list item with a text label and a thumbnail image.
      list_item = xbmcgui.ListItem(label=episode_data['title'])

      # Set additional info for the list item.
      # For available properties see https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
      # 'mediatype' is needed for skin to display info for this ListItem correctly.
      list_item.setInfo('video', {'title': episode_data['title'],
                                  'genre': 'General',
                                  'mediatype': 'video'})

      # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
      list_item.setArt({'thumb': episode_data['image']})

      # Set 'IsPlayable' property to 'true'.
      # This is mandatory for playable items!
      list_item.setProperty('IsPlayable', 'true')

      # Create a URL for a plugin recursive call.
      # Example: plugin://plugin.video.example/?action=play&channel_endpoint=/filme/tnt&channel_metadata=...
      url = common_functions.get_url(action='play', account='voyo.ro', channel_name=episode_data['title'], channel_id=episode_data['id'])
      common_vars.__logger__.debug('URL for plugin recursive call: ' + url)

      # This means that this item won't open any sub-list.
      is_folder = False

      # Add our item to the Kodi virtual folder listing.
      xbmcplugin.addDirectoryItem(int(common_vars.__handle__), url, list_item, is_folder)


  # Add a sort method for the virtual folder items (alphabetically, ignore articles)
  xbmcplugin.addSortMethod(int(common_vars.__handle__), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

  # Finish creating a virtual folder.
  xbmcplugin.endOfDirectory(int(common_vars.__handle__))

  common_vars.__logger__.debug('Exit function')


def voyo__playVideo(CHANNEL_ID, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')
  
  common_vars.__logger__.debug('Chanel ID = ' + CHANNEL_ID)
  
  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)
  __stream_details__ = voyo__API__plays(CHANNEL_ID, NAME, COOKIEJAR, SESSION, DATA_DIR)
  
  if 'code' in __stream_details__:
    #common_vars.__logger__.debug('[voyo.ro] => ' + __stream_details__['title'] + '  (code ' + str(__stream_details__['code']) + ' )', __stream_details__['message'])
    xbmcgui.Dialog().ok('[voyo.ro] => ' + __stream_details__['title'] + '  (code ' + str(__stream_details__['code']) + ' )', __stream_details__['message'])
    common_vars.__logger__.debug('Exit function')
    return

  if __stream_details__['videoType'] == 'hls':
    _stream_manifest_url_ = __stream_details__['url']
    common_vars.__logger__.debug('Found _stream_manifest_url_ = ' + _stream_manifest_url_)

    _stream_manifest_host_ = re.findall('//(.+?)/', _stream_manifest_url_, re.IGNORECASE|re.DOTALL)[0]
    common_vars.__logger__.debug('Found _stream_manifest_host_ = ' + _stream_manifest_host_)

    # Set the headers to be used with imputstream.adaptive
    _headers_ = ''
    _headers_ = _headers_ + '&User-Agent=' + common_vars.__voyo_API_userAgent__
    _headers_ = _headers_ + '&Accept-Encoding=gzip'
    _headers_ = _headers_ + '&Host=' + _stream_manifest_host_
    _headers_ = _headers_ + '&Connection=keep-alive'
    common_vars.__logger__.debug('Created: _headers_ = ' + _headers_)

    # Create a playable item with a path to play.
    is_helper = inputstreamhelper.Helper('hls')
    if is_helper.check_inputstream():
      play_item = xbmcgui.ListItem(path=_stream_manifest_url_ + '|' + _headers_)
      play_item.setProperty('inputstream', 'inputstream.adaptive')
      play_item.setProperty('inputstream.adaptive.manifest_headers', _headers_)
      play_item.setProperty('inputstream.adaptive.stream_headers', _headers_)
      play_item.setMimeType('application/vnd.apple.mpegurl')
      play_item.setContentLookup(False)

      # Pass the item to the Kodi player.
      xbmcplugin.setResolvedUrl(int(common_vars.__handle__), True, listitem=play_item)

  if __stream_details__['videoType'] == 'dash':
    _stream_manifest_url_ = __stream_details__['url']
    common_vars.__logger__.debug('Found _stream_manifest_url_ = ' + _stream_manifest_url_)

    _stream_manifest_host_ = re.findall('//(.+?)/', _stream_manifest_url_, re.IGNORECASE|re.DOTALL)[0]
    common_vars.__logger__.debug('Found _stream_manifest_host_ = ' + _stream_manifest_host_)
    
    # Set the headers to be used with imputstream.adaptive
    _headers_ = ''
    _headers_ = _headers_ + 'User-Agent=' + common_vars.__voyo_API_userAgent__
    _headers_ = _headers_ + '&Host=' + _stream_manifest_host_
    _headers_ = _headers_ + '&Connection=Keep-Alive'
    _headers_ = _headers_ + '&verifypeer=false'
    common_vars.__logger__.debug('Created: _headers_ = ' + _headers_)

    # Get the host needed to be set in the headers for the DRM license request
    
    _lic_headers_host_ = re.findall('//(.+?)/', str(__stream_details__['drm']['licenseUrl']), re.IGNORECASE)[0]
    common_vars.__logger__.debug('Found: _lic_headers_host_ = ' + _lic_headers_host_)

    # Set the headers to be used when requesting license key
    _lic_headers_ = ''
    _lic_headers_ = _lic_headers_ + 'User-Agent=' + common_vars.__voyo_API_userAgent__
    _lic_headers_ = _lic_headers_ + '&Connection=keep-alive'
    _lic_headers_ = _lic_headers_ + '&Content-Type=application/octet-stream'
    _lic_headers_ = _lic_headers_ + '&Host=' + _lic_headers_host_
    _lic_headers_ = _lic_headers_ + '&verifypeer=false'
    for licenseRequestHeader in __stream_details__['drm']['licenseRequestHeaders']:
      _lic_headers_ = _lic_headers_ + '&' + licenseRequestHeader['name'] + '=' + licenseRequestHeader['value']

    common_vars.__logger__.debug('Created: _lic_headers_ = ' + _lic_headers_)

    # Create a playable item with a path to play.
    is_helper = inputstreamhelper.Helper('mpd', drm='com.widevine.alpha')
    if is_helper.check_inputstream():
      play_item = xbmcgui.ListItem(path=__stream_details__['url'])
      play_item.setProperty('inputstream', 'inputstream.adaptive')
      play_item.setProperty('inputstream.adaptive.manifest_headers', _headers_)
      play_item.setProperty('inputstream.adaptive.stream_headers', _headers_)
      play_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
      play_item.setProperty('inputstream.adaptive.license_key', __stream_details__['drm']['licenseUrl'] + '|' + _lic_headers_ + '|R{SSM}|')
      play_item.setMimeType('application/dash+xml')

      # Pass the item to the Kodi player.
      xbmcplugin.setResolvedUrl(int(common_vars.__handle__), True, listitem=play_item)

  common_vars.__logger__.debug('Exit function')
 

def voyo__writeM3Ufile_record(M3U_FILE, CH_ID, CH_NAME, CH_LOGO, CH_NO, NAME, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  common_vars.__logger__.debug('    Channel ID => ' + CH_ID + ' Channel name: ' + CH_NAME + ' Channel logo: ' + CH_LOGO)

  
  _line_ = "#EXTINF:0 tvg-id=\"voyo__" + CH_ID + "\" tvg-name=\"" + CH_NAME + "\" tvg-logo=\"" + CH_LOGO + "\" tvg-chno=\"" + CH_NO + "\" group-title=\"Voyo\"," + CH_NAME
    
  _url_ = common_functions.get_url(action='play', account='voyo.ro', channel_name=CH_NAME, channel_id=CH_ID)
  _play_url_ = "plugin://" + common_vars.__AddonID__ + "/" + _url_

  M3U_FILE.write(_line_ + "\n")
  M3U_FILE.write(_play_url_ + "\n")

  common_vars.__logger__.debug('Exit function')


def voyo__PVRIPTVSimpleClientIntegration_update_m3u_file(M3U_FILE, START_NUMBER, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')
  
  common_vars.__logger__.debug('M3U_FILE = ' + M3U_FILE)
  common_vars.__logger__.debug('START_NUMBER = ' + str(START_NUMBER))

  _CHNO_ = START_NUMBER
  _filter_lists_data_ = common_functions.readChannelFilterLists(NAME, DATA_DIR)
  _data_file_ = open(M3U_FILE, 'a', encoding='utf-8')
  
  voyo__checkToken(NAME, COOKIEJAR, SESSION, DATA_DIR)

  __overview__ = voyo__API__overview('None', NAME, COOKIEJAR, SESSION, DATA_DIR)

  for category_data in __overview__['categories']:
    common_vars.__logger__.debug('Category:  id = \'' + category_data['category']['id'] + '\', Name = \'' + category_data['category']['name'] + '\', Title = \'' + category_data['category']['name'] + '\'')

    if category_data['category']['type'] == 'live':
      __category_overview__ = voyo__API__overview(category_data['category']['id'], NAME, COOKIEJAR, SESSION, DATA_DIR)
      for channel_data in __category_overview__['liveTvs']:
        common_vars.__logger__.debug('Channel ID: ' + channel_data['id'])
        common_vars.__logger__.debug('Channel name: ' + channel_data['name'])
        common_vars.__logger__.debug('Channel logo: ' + channel_data['logoTransparent'])

        if common_vars.__PVRIPTVSimpleClientIntegration__ChannelFilter_map__[common_vars.__config_PVRIPTVSimpleClientIntegration_FilterType__] == "None":
          common_vars.__logger__.debug('Configured Filter Type = None')
          voyo__writeM3Ufile_record(_data_file_, channel_data['id'], channel_data['name'], channel_data['logoTransparent'], str(_CHNO_), NAME, COOKIEJAR, SESSION)

        _search_string_ = "voyo__" + channel_data['id']
        

        # Filter Type = Blacklist
        if common_vars.__PVRIPTVSimpleClientIntegration__ChannelFilter_map__[common_vars.__config_PVRIPTVSimpleClientIntegration_FilterType__] == "Blacklist":
          common_vars.__logger__.debug('Configured Filter Type = Blacklist')
          if _search_string_ in _filter_lists_data_['blacklist']:
            common_vars.__logger__.debug('\'' + _search_string_ + '\' is blacklisted')
          else:
            voyo__writeM3Ufile_record(_data_file_, channel_data['id'], channel_data['name'], channel_data['logoTransparent'], str(_CHNO_), NAME, COOKIEJAR, SESSION)

        # Filter Type = Whitelist
        if common_vars.__PVRIPTVSimpleClientIntegration__ChannelFilter_map__[common_vars.__config_PVRIPTVSimpleClientIntegration_FilterType__] == "Whitelist":
          common_vars.__logger__.debug('Configured Filter Type = Whitelist')
          if _search_string_ in _filter_lists_data_['whitelist']:
            voyo__writeM3Ufile_record(_data_file_, channel_data['id'], channel_data['name'], channel_data['logoTransparent'], str(_CHNO_), NAME, COOKIEJAR, SESSION)
          else:
            common_vars.__logger__.debug('\'' + _search_string_ + '\' is NOT whitelisted')
        
      _CHNO_ = _CHNO_ + 1
    
  _data_file_.close()

  common_vars.__logger__.debug('Exit function')
  
  return _CHNO_


def voyo__get_epg_data(NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  _epg_data_ = []

  _today_ = datetime.date(datetime.today())
  common_vars.__logger__.debug('_today_: ' + str(_today_))
  _rcvd_today_ = voyo__API__getEPG_by_date(_today_, NAME, COOKIEJAR, SESSION, DATA_DIR)

  _today_plus_1_ = datetime.date(datetime.today()) + timedelta(days=1)
  common_vars.__logger__.debug('_today_plus_1_: ' + str(_today_plus_1_))
  _rcvd_today_plus_1_ = voyo__API__getEPG_by_date(_today_plus_1_, NAME, COOKIEJAR, SESSION, DATA_DIR)

  _today_plus_2_ = datetime.date(datetime.today()) + timedelta(days=2)
  common_vars.__logger__.debug('_today_plus_2_: ' + str(_today_plus_2_))
  _rcvd_today_plus_2_ = voyo__API__getEPG_by_date(_today_plus_2_, NAME, COOKIEJAR, SESSION, DATA_DIR)

  if _rcvd_today_:
    for _channel_ in _rcvd_today_['availableChannels']:
      _channel_record_ = {}
      _channel_epg_items_ = []
      if _rcvd_today_:
        for _epg_channel_ in _rcvd_today_['program'][0]['channels']:
          common_vars.__logger__.debug('epg_channel[\'id\']: ' + _epg_channel_['id'])
          common_vars.__logger__.debug('_channel_[\'id\']: ' + _channel_['id'])
          if _epg_channel_['id'] == _channel_['id']:
            for _segment_ in _epg_channel_['segments']:
              for _epg_item_ in _segment_['items']:
                _channel_epg_items_.append(_epg_item_);
      if _rcvd_today_plus_1_:
        for _epg_channel_ in _rcvd_today_plus_1_['program'][0]['channels']:
          if _epg_channel_['id'] == _channel_['id']:
            for _segment_ in _epg_channel_['segments']:
              for _epg_item_ in _segment_['items']:
                _channel_epg_items_.append(_epg_item_);
      if _rcvd_today_plus_2_:
        for _epg_channel_ in _rcvd_today_plus_2_['program'][0]['channels']:
          if _epg_channel_['id'] == _channel_['id']:
            for _segment_ in _epg_channel_['segments']:
              for _epg_item_ in _segment_['items']:
                _channel_epg_items_.append(_epg_item_);

      _channel_record_["channel_id"] = _channel_['id']
      _channel_record_["channel_name"] = _channel_['name']
      _channel_record_["channel_epg"] = _channel_epg_items_

      _epg_data_.append(_channel_record_)

  common_vars.__logger__.debug('Exit function')

  return _epg_data_


def voyo__PVRIPTVSimpleClientIntegration_update_EPG_file(XML_FILE, NAME, COOKIEJAR, SESSION, DATA_DIR):
  common_vars.__logger__ = logging.getLogger(NAME)
  common_vars.__logger__.debug('Enter function')

  common_vars.__logger__.debug('XML_FILE = ' + XML_FILE)

  _epg_data_ = voyo__get_epg_data(NAME, COOKIEJAR, SESSION, DATA_DIR)
  common_vars.__logger__.debug('Received epg data = ' + str(_epg_data_))

  _data_file_ = open(XML_FILE, 'a', encoding='utf-8')

  for _record_ in _epg_data_:
    common_vars.__logger__.debug('Channel ID => ' + str(_record_['channel_id']))
    common_vars.__logger__.debug('Channel name: ' + str(_record_['channel_name']))
    common_vars.__logger__.debug('Channel title: ' + str(_record_['channel_name']))

    _line_ = "  <channel id=\"voyo__" + str(_record_['channel_id']) + "\">"
    _data_file_.write(_line_ + "\n")
    _line_ = "    <display-name>" + str(_record_['channel_name']) + "</display-name>"
    _data_file_.write(_line_ + "\n")
    _line_ = "  </channel>"
    _data_file_.write(_line_ + "\n")

    for _program_data_ in _record_['channel_epg']:

      _start_dt_ = datetime.fromisoformat(_program_data_['startAt'])
      _start_timestamp = _start_dt_.timestamp()
      _start_date_time_object_ = datetime.utcfromtimestamp(int(_start_timestamp))

      _stop_dt_ = datetime.fromisoformat(_program_data_['endAt'])
      _stop_timestamp = _stop_dt_.timestamp()
      _stop_date_time_object_ = datetime.utcfromtimestamp(int(_stop_timestamp))

      _line_ = "  <programme start=\"" + str(_start_date_time_object_.strftime("%Y%m%d%H%M%S")) + "\" stop=\"" + str(_stop_date_time_object_.strftime("%Y%m%d%H%M%S")) + "\" channel=\"voyo__" + str(_record_['channel_id']) + "\">"
      _data_file_.write(_line_ + "\n")

      _selected_program_title_ = _program_data_['title']
      if _program_data_['show']:
        _selected_program_title_ = _program_data_['show']['title']

      # Escape special characters in the program name
      #_selected_program_title_ = re.sub('<', '&lt;', _selected_program_title_, flags=re.IGNORECASE)
      #_selected_program_title_ = re.sub('>', '&gt;', _selected_program_title_, flags=re.IGNORECASE)
      #_selected_program_title_ = re.sub('&', '&amp;', _selected_program_title_, flags=re.IGNORECASE)
      _line_ = "    <title>" + _selected_program_title_ + "</title>"
      _data_file_.write(_line_ + "\n")

      # Escape special characters in the program description
      #_program_data_['short_description'] = re.sub('<', '&lt;', _program_data_['short_description'], flags=re.IGNORECASE)
      #_program_data_['short_description'] = re.sub('>', '&gt;', _program_data_['short_description'], flags=re.IGNORECASE)
      #_program_data_['short_description'] = re.sub('&', '&amp;', _program_data_['short_description'], flags=re.IGNORECASE)

      #_program_data_['description'] = re.sub('<', '&lt;', _program_data_['description'], flags=re.IGNORECASE)
      #_program_data_['description'] = re.sub('>', '&gt;', _program_data_['description'], flags=re.IGNORECASE)
      #_program_data_['description'] = re.sub('&', '&amp;', _program_data_['description'], flags=re.IGNORECASE)
      _line_ = "    <desc>" + str(_program_data_['shortDescription']) + "\n\n    " + str(_program_data_['description']) + "\n    </desc>"
      _data_file_.write(_line_ + "\n")

      _line_ = "  </programme>"
      _data_file_.write(_line_ + "\n")

  _data_file_.close

  common_vars.__logger__.debug('Exit function')


