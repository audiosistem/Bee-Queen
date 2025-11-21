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

# Variables for the user preferences stored in the addon configuration
__config_AccountUser__ = ''
__config_AccountPassword__ = ''
__config_DebugEnabled__ = ''
__config_ShowTitleInChannelList__ = ''
__config_DeviceManufacturer__ = ''
__config_DeviceModel__ = ''
__config_AndroidVersion__ = ''



# UserAgent exposed by this addon
__API_userAgent__ = 'okhttp/4.8.1'
__userAgent__ = 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0'

# The IDs used by addon
__AddonID__ = 'plugin.video.DigiOnline.ro'
__ServiceID__ = 'service.plugin.video.DigiOnline.ro'

# File names for the files where the addon and the service will write the log entries
__AddonLogFilename__ = __AddonID__ + '.log'
__ServiceLogFilename__ = __ServiceID__ + '.log'

# The cookiejar used by addon
__AddonCookiesFilename__ = 'cookies.txt'
__AddonCookieJar__ = ''

# File name for storing the state data
__StateFilename__ = 'digionline.ro_state.txt'

# The plugin url in plugin:// notation.
__plugin_url__ = ''

# The plugin handle
__handle__ = ''

__logger__ = ''

# The session used by addon
__AddonSession__ = ''

# The session used by service
__ServiceSession__ = ''


# Constants
__minute__ = (1 * 60)
__day__ = (24 * 60 * 60)

# Directory holding the cached data. 
__cache_dir__ = 'cached_data'

# File containing the local copy of the list of categories read from DigiOnline.ro
__categoriesCachedDataFilename__ = 'categories.json'

__categorieschannelsCachedDataFilename__ = 'categorieschannels.json'
__epgCachedDataFilename__ = 'epg.json'

# Some sane defaults before being overwritten by the user settings
# How much time has to pass before reading again from DigiOnline.ro the list of categories.
__categoriesCachedDataRetentionInterval__ = (30 * __day__)

# How much time has to pass before reading again from DigiOnline.ro the list of channels in a specific category.
__channelsCachedDataRetentionInterval__ = (10 * __day__)

# How much time has to pass before reading again from DigiOnline.ro the EPG data for a channel.
__EPGDataCachedDataRetentionInterval__ = (10 * __minute__)

# How much time has to pass before reading again from source the list of categories.
__CachedDataRetentionInterval__ = (1 * __day__)


### Service variables

## PVR IPTV Simple Client integration 
# Directory where data files are stored
__PVRIPTVSimpleClientIntegration_DataDir__ = 'PVRIPTVSimpleClientIntegration'

# File names for the data files
__PVRIPTVSimpleClientIntegration_m3u_FileName__ = __AddonID__ + '.m3u'
__PVRIPTVSimpleClientIntegration_EPG_FileName__ = __AddonID__ + '.xml' 

# Time of day for refreshing the contents in the data files.
__PVRIPTVSimpleClientIntegration_m3u_FileRefreshTime__ = ''
__PVRIPTVSimpleClientIntegration_EPG_FileRefreshTime__ = ''

# Previous/Old time of day for refreshing the contents in the data files.
__PVRIPTVSimpleClientIntegration_m3u_FileOldRefreshTime__ = ''
__PVRIPTVSimpleClientIntegration_EPG_FileOldRefreshTime__ = ''

# Time since the last update of data files. If this time has passed, the data files will be updated at startup.
__PVRIPTVSimpleClientIntegration_m3u_FileMaxAge__ = (1 * __day__) + (1 * __minute__)
__PVRIPTVSimpleClientIntegration_EPG_FileMaxAge__ = (1 * __day__) + (1 * __minute__)


