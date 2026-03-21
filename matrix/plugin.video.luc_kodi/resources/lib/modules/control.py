# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from json import dumps as jsdumps, loads as jsloads
import os.path
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import xml.etree.ElementTree as ET

addon = xbmcaddon.Addon
AddonID = xbmcaddon.Addon().getAddonInfo('id')
addonInfo = xbmcaddon.Addon().getAddonInfo
addonName = addonInfo('name')
addonVersion = addonInfo('version')
getLangString = xbmcaddon.Addon().getLocalizedString

dialog = xbmcgui.Dialog()
numeric_input = xbmcgui.INPUT_NUMERIC
getCurrentDialogId = xbmcgui.getCurrentWindowDialogId()
getCurrentWindowId = xbmcgui.getCurrentWindowId()
homeWindow = xbmcgui.Window(10000)
playerWindow = xbmcgui.Window(12005)
item = xbmcgui.ListItem
progressDialog = xbmcgui.DialogProgress()
progressDialogBG = xbmcgui.DialogProgressBG()

addItem = xbmcplugin.addDirectoryItem
content = xbmcplugin.setContent
directory = xbmcplugin.endOfDirectory
property = xbmcplugin.setProperty
resolve_url = xbmcplugin.setResolvedUrl

def resolve(handle, succeeded, listitem, meta=None):
	"""Wrapper around xbmcplugin.setResolvedUrl.

	meta is accepted for backwards compatibility but is not used.
	"""
	return resolve_url(handle, succeeded, listitem)

sortMethod = xbmcplugin.addSortMethod

condVisibility = xbmc.getCondVisibility
execute = xbmc.executebuiltin
infoLabel = xbmc.getInfoLabel
jsonrpc = xbmc.executeJSONRPC
keyboard = xbmc.Keyboard
log = xbmc.log
monitor_class = xbmc.Monitor
monitor = monitor_class()
player = xbmc.Player()
player2 = xbmc.Player
playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
skin = xbmc.getSkinDir()

deleteDir = xbmcvfs.rmdir
deleteFile = xbmcvfs.delete
existsPath = xbmcvfs.exists
legalFilename = xbmcvfs.makeLegalFilename
listDir = xbmcvfs.listdir
makeFile = xbmcvfs.mkdir
makeDirs = xbmcvfs.mkdirs
openFile = xbmcvfs.File
transPath = xbmcvfs.translatePath

joinPath = os.path.join
isfilePath = os.path.isfile
absPath = os.path.abspath

SETTINGS_PATH = transPath(joinPath(addonInfo('path'), 'resources', 'settings.xml'))
try: dataPath = transPath(addonInfo('profile')).decode('utf-8')
except: dataPath = transPath(addonInfo('profile'))
settingsFile = joinPath(dataPath, 'settings.xml')
viewsFile = joinPath(dataPath, 'views.db')
bookmarksFile = joinPath(dataPath, 'bookmarks.db')
providercacheFile = joinPath(dataPath, 'providers.db')
metacacheFile = joinPath(dataPath, 'metadata.db')
searchFile = joinPath(dataPath, 'search.db')
libcacheFile = joinPath(dataPath, 'library.db')
cacheFile = joinPath(dataPath, 'cache.db')
traktSyncFile = joinPath(dataPath, 'traktsync.db')
fanarttvCacheFile = joinPath(dataPath, 'fanarttv.db')
watchedcacheFile = joinPath(dataPath, 'watched.db')
subsFile         = joinPath(dataPath, 'substitute.db')
subtitlesPath    = joinPath(dataPath, 'subtitles')
trailer = 'plugin://plugin.video.youtube/play/?video_id=%s'
KODI_VERSION = int(xbmc.getInfoLabel("System.BuildVersion")[:2])

def getKodiVersion(full=False):
	if full: return xbmc.getInfoLabel("System.BuildVersion")
	else: return int(xbmc.getInfoLabel("System.BuildVersion")[:2])

def setting(id, fallback=None):
	try: settings_dict = jsloads(homeWindow.getProperty('luc_kodi_settings'))
	except: settings_dict = make_settings_dict()
	if settings_dict is None: settings_dict = settings_fallback(id)
	# Kodi may not write default values into userdata/addon_data/.../settings.xml on some platforms (e.g. iOS).
	# If the key is missing from the parsed settings dict, fall back to xbmcaddon so we still get the default.
	# FIX: also fall back when key exists but has empty value — this covers the case where a version update
	# triggers a settings.xml rewrite that resets credentials (e.g. Trakt token) to their default empty string.
	# Without this, an empty-string value in the cache dict would be returned directly, bypassing Kodi's
	# internal settings store which may still hold the real non-empty value.
	if id in settings_dict:
		value = settings_dict.get(id, '')
		if value == '':
			try:
				api_value = xbmcaddon.Addon().getSetting(id)
				if api_value:
					value = api_value
					settings_dict[id] = value
					homeWindow.setProperty('luc_kodi_settings', jsdumps(settings_dict))
			except: pass
	else:
		try: value = xbmcaddon.Addon().getSetting(id)
		except: value = ''
		try:
			settings_dict[id] = value
			homeWindow.setProperty('luc_kodi_settings', jsdumps(settings_dict))
		except: pass
	if fallback is None: return value
	if value == '': return fallback
	return value
def settings_fallback(id):
	return {id: xbmcaddon.Addon().getSetting(id)}

def setSetting(id, value):
	xbmcaddon.Addon().setSetting(id, value)

def make_settings_dict(): # service runs upon a setting change
	try:
		root = ET.parse(settingsFile).getroot()
		settings_dict = {}
		for item in root:
			dict_item = {}
			setting_id = item.get('id')
			setting_value = item.text
			if setting_value is None: setting_value = ''
			dict_item = {setting_id: setting_value}
			settings_dict.update(dict_item)
		homeWindow.setProperty('luc_kodi_settings', jsdumps(settings_dict))
		refresh_playAction()
		refresh_libPath()
		return settings_dict
	except: return None

def openSettings(query=None, id=addonInfo('id')):
	try:
		hide()
		execute('Addon.OpenSettings(%s)' % id)
		if not query: return
		c, f = query.split('.')
		execute('SetFocus(%i)' % (int(c) - 100))
		execute('SetFocus(%i)' % (int(f) - 80))
	except:
		from resources.lib.modules import log_utils
		log_utils.error()

def lang(language_id):
	return str(getLangString(language_id))

def sleep(time):  # Modified `sleep`(in milli secs) that honors a user exit request
	while time > 0 and not monitor.abortRequested():
		xbmc.sleep(min(100, time))
		time = time - 100

def getCurrentViewId():
	win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
	return str(win.getFocusId())

def getluc_kodiVersion():
	return xbmcaddon.Addon('plugin.video.luc_kodi').getAddonInfo('version')

def addonVersion(addon):
	return xbmcaddon.Addon(addon).getAddonInfo('version')

def addonId():
	return addonInfo('id')

def addonName():
	return addonInfo('name')

def addonPath(addon):
	try: addonID = xbmcaddon.Addon(addon)
	except: addonID = None
	if addonID is None: return ''
	else:
		try: return transPath(addonID.getAddonInfo('path').decode('utf-8'))
		except: return transPath(addonID.getAddonInfo('path'))

def artPath():
	theme = appearance()
	return joinPath(xbmcaddon.Addon('plugin.video.luc_kodi').getAddonInfo('path'), 'resources', 'media', theme)

def genreIconPath():
	return joinPath(xbmcaddon.Addon('plugin.video.luc_kodi').getAddonInfo('path'), 'resources', 'media', 'genre_media', 'icons')

def genrePosterPath():
	return joinPath(xbmcaddon.Addon('plugin.video.luc_kodi').getAddonInfo('path'), 'resources', 'media', 'genre_media', 'posters')

def appearance():
	theme = setting('appearance.1').lower()
	return theme

def addonIcon():
	theme = appearance()
	art = artPath()
	if not (art is None and theme in ('-', '')): return joinPath(art, 'icon.png')
	return addonInfo('icon')

def addonThumb():
	theme = appearance()
	art = artPath()
	if not (art is None and theme in ('-', '')): return joinPath(art, 'poster.png')
	elif theme == '-': return 'DefaultFolder.png'
	return addonInfo('icon')

def addonPoster():
	theme = appearance()
	art = artPath()
	if not (art is None and theme in ('-', '')): return joinPath(art, 'poster.png')
	return 'DefaultVideo.png'

def addonFanart():
	theme = appearance()
	art = artPath()
	if not (art is None and theme in ('-', '')): return joinPath(art, 'fanart.jpg')
	return addonInfo('fanart')

def addonBanner():
	theme = appearance()
	art = artPath()
	if not (art is None and theme in ('-', '')): return joinPath(art, 'banner.png')
	return 'DefaultVideo.png'

def addonNext():
	theme = appearance()
	art = artPath()
	if not (art is None and theme in ('-', '')): return joinPath(art, 'next.png')
	return 'DefaultVideo.png'

####################################################
# --- Dialogs
####################################################
def notification(title=None, message=None, icon=None, time=3000, sound=(setting('notification.sound') == 'true')):
	"""
	Unified notification for the entire plugin.
	Renders a custom XML window (bottom-right, colored text, plugin icon) in a
	background thread so the caller is never blocked.
	Falls back to the standard Kodi notification if the XML window fails.

	title   -> Line 1 (green  #ff00fa9a) -- defaults to 'luc_kodi'
	message -> Line 2 (golden #fffdb515)
	icon    -> path, or 'INFO'/'WARNING'/'ERROR' sentinel
	time    -> display duration in ms (converted to seconds for the XML window)
	"""
	# Resolve title / message strings
	if title == 'default' or title is None: title = addonName()
	if isinstance(title, int): heading = lang(title)
	else: heading = str(title)
	if isinstance(message, int): body = lang(message)
	else: body = str(message)

	# Resolve icon -- custom paths are passed through; sentinels fall back to plugin icon
	if not icon or icon == 'default': icon_path = addonIcon()
	elif icon in ('INFO', 'WARNING', 'ERROR'): icon_path = addonIcon()
	else: icon_path = icon

	duration_secs = max(2, int(time) // 1000)
	_orig_icon = icon  # keep original for fallback

	def _show():
		try:
			from resources.lib.windows.display_welcome import DisplayWelcomeXML
			win = DisplayWelcomeXML(
				'display_welcome.xml',
				addonPath('plugin.video.luc_kodi'),
				'Default',
				line1=heading,
				line2=body,
				icon=icon_path,
				duration=duration_secs
			)
			win.show_and_close(duration=duration_secs)
			del win
		except Exception:
			# Fallback: standard Kodi notification
			_fb = _orig_icon
			if not _fb or _fb == 'default': _fb = addonIcon()
			elif _fb == 'INFO':    _fb = xbmcgui.NOTIFICATION_INFO
			elif _fb == 'WARNING': _fb = xbmcgui.NOTIFICATION_WARNING
			elif _fb == 'ERROR':   _fb = xbmcgui.NOTIFICATION_ERROR
			dialog.notification(heading, body, _fb, time, sound)

	import threading
	threading.Thread(target=_show, daemon=True).start()

def yesnoDialog(line1, line2, line3, heading=addonInfo('name'), nolabel='', yeslabel=''):
	message = '%s[CR]%s[CR]%s' % (line1, line2, line3)
	return dialog.yesno(heading, message, nolabel, yeslabel)

def yesnocustomDialog(line1, line2, line3, heading=addonInfo('name'), customlabel='', nolabel='', yeslabel=''):
	message = '%s[CR]%s[CR]%s' % (line1, line2, line3)
	return dialog.yesnocustom(heading, message, customlabel, nolabel, yeslabel)

def selectDialog(list, heading=addonInfo('name')):
	return dialog.select(heading, list)

def okDialog(title=None, message=None):
	if title == 'default' or title is None: title = addonName()
	if isinstance(title, int): heading = lang(title)
	else: heading = str(title)
	if isinstance(message, int): body = lang(message)
	else: body = str(message)
	return dialog.ok(heading, body)

def context(items=None, labels=None):
	if items:
		labels = [i[0] for i in items]
		choice = dialog.contextmenu(labels)
		if choice >= 0: return items[choice][1]()
		else: return False
	else: return dialog.contextmenu(labels)

####################################################
# --- Built-in
####################################################
def busy():
	return execute('ActivateWindow(busydialognocancel)')

def hide():
	execute('Dialog.Close(busydialog)')
	execute('Dialog.Close(busydialognocancel)')

def closeAll():
	return execute('Dialog.Close(all,true)')

def closeOk():
	return execute('Dialog.Close(okdialog,true)')

def refresh():
	return execute('Container.Refresh')

def queueItem():
	return execute('Action(Queue)') # seems broken in 19 for show and season level, works fine in 18

def refreshRepos():
	return execute('UpdateAddonRepos')
########################

def cancelPlayback():
	from sys import argv
	try:
		playlist.clear()
	except:
		pass
	try:
		resolve(int(argv[1]), False, item(offscreen=True))
	except:
		pass
	try:
		closeOk()
	except:
		pass
	return

def apiLanguage(ret_name=None):
	langDict = {'Bulgarian': 'bg', 'Chinese': 'zh', 'Croatian': 'hr', 'Czech': 'cs', 'Danish': 'da', 'Dutch': 'nl', 'English': 'en', 'Finnish': 'fi',
					'French': 'fr', 'German': 'de', 'Greek': 'el', 'Hebrew': 'he', 'Hungarian': 'hu', 'Italian': 'it', 'Japanese': 'ja', 'Korean': 'ko',
					'Norwegian': 'no', 'Polish': 'pl', 'Portuguese': 'pt', 'Romanian': 'ro', 'Russian': 'ru', 'Serbian': 'sr', 'Slovak': 'sk',
					'Slovenian': 'sl', 'Spanish': 'es', 'Swedish': 'sv', 'Thai': 'th', 'Turkish': 'tr', 'Ukrainian': 'uk'}
	trakt = ('bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hr', 'hu', 'it', 'ja', 'ko', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sr', 'sv', 'th', 'tr', 'uk', 'zh')
	tvdb = ('en', 'sv', 'no', 'da', 'fi', 'nl', 'de', 'it', 'es', 'fr', 'pl', 'hu', 'el', 'tr', 'ru', 'he', 'ja', 'pt', 'zh', 'cs', 'sl', 'hr', 'ko')
	youtube = ('gv', 'gu', 'gd', 'ga', 'gn', 'gl', 'ty', 'tw', 'tt', 'tr', 'ts', 'tn', 'to', 'tl', 'tk', 'th', 'ti', 'tg', 'te', 'ta', 'de', 'da', 'dz', 'dv', 'qu', 'zh', 'za', 'zu',
					'wa', 'wo', 'jv', 'ja', 'ch', 'co', 'ca', 'ce', 'cy', 'cs', 'cr', 'cv', 'cu', 'ps', 'pt', 'pa', 'pi', 'pl', 'mg', 'ml', 'mn', 'mi', 'mh', 'mk', 'mt', 'ms',
					'mr', 'my', 've', 'vi', 'is', 'iu', 'it', 'vo', 'ii', 'ik', 'io', 'ia', 'ie', 'id', 'ig', 'fr', 'fy', 'fa', 'ff', 'fi', 'fj', 'fo', 'ss', 'sr', 'sq', 'sw', 'sv', 'su', 'st', 'sk',
					'si', 'so', 'sn', 'sm', 'sl', 'sc', 'sa', 'sg', 'se', 'sd', 'lg', 'lb', 'la', 'ln', 'lo', 'li', 'lv', 'lt', 'lu', 'yi', 'yo', 'el', 'eo', 'en', 'ee', 'eu', 'et', 'es', 'ru',
					'rw', 'rm', 'rn', 'ro', 'be', 'bg', 'ba', 'bm', 'bn', 'bo', 'bh', 'bi', 'br', 'bs', 'om', 'oj', 'oc', 'os', 'or', 'xh', 'hz', 'hy', 'hr', 'ht', 'hu', 'hi', 'ho',
					'ha', 'he', 'uz', 'ur', 'uk', 'ug', 'aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'as', 'ar', 'av', 'ay', 'az', 'nl', 'nn', 'no', 'na', 'nb', 'nd', 'ne', 'ng',
					'ny', 'nr', 'nv', 'ka', 'kg', 'kk', 'kj', 'ki', 'ko', 'kn', 'km', 'kl', 'ks', 'kr', 'kw', 'kv', 'ku', 'ky')
	tmdb = ('bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hr', 'hu', 'it', 'ja', 'ko', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sr', 'sv', 'th', 'tr', 'uk', 'zh')
	name = None
	name = setting('api.language')
	if not name: name = 'AUTO'
	if name[-1].isupper():
		try: name = xbmc.getLanguage(xbmc.ENGLISH_NAME).split(' ')[0]
		except: pass
	try: name = langDict[name]
	except: name = 'en'
	lang = {'trakt': name} if name in trakt else {'trakt': 'en'}
	lang['tvdb'] = name if name in tvdb else 'en'
	lang['youtube'] = name if name in youtube else 'en'
	lang['tmdb'] = name if name in tmdb else 'en'
	if ret_name:
		lang['trakt'] = [i[0] for i in iter(langDict.items()) if i[1] == lang['trakt']][0]
		lang['tvdb'] = [i[0] for i in iter(langDict.items()) if i[1] == lang['tvdb']][0]
		lang['youtube'] = [i[0] for i in iter(langDict.items()) if i[1] == lang['youtube']][0]
		lang['tmdb'] = [i[0] for i in iter(langDict.items()) if i[1] == lang['tmdb']][0]
	return lang

def mpaCountry():
# Countries with Content Rating System
	countryDict = {'Australia': 'AU', 'Austria': 'AT', 'Brazil': 'BR', 'Bulgaria': 'BG', 'Canada': 'CA', 'China': 'CN', 'Denmark': 'DK', 'Estonia': 'EE',
						'Finland': 'FI', 'France': 'FR', 'Germany': 'DE', 'Greece': 'GR', 'Hungary': 'HU', 'Hong Kong SAR China': 'HK', 'India': 'IN',
						'Indonesia': 'ID', 'Ireland': 'IE', 'Italy': 'IT', 'Japan': 'JP', 'Kazakhstan': 'KZ', 'Latvia': 'LV', 'Lithuania': 'LT', 'Malaysia': 'MY',
						'Mexico': 'MX', 'Netherlands': 'NL', 'New Zealand': 'NZ', 'Norway': 'NO', 'Philippines': 'PH', 'Poland': 'PL', 'Portugal': 'PT',
						'Romania': 'RO', 'Russia': 'RU', 'Saudi Arabia': 'SA', 'Singapore': 'SG', 'Slovakia': 'SK', 'South Africa': 'ZA', 'South Korea': 'KR',
						'Spain': 'ES', 'Sweden': 'SE', 'Switzerland': 'CH', 'Taiwan': 'TW', 'Thailand': 'TH', 'Turkey': 'TR', 'Ukraine': 'UA',
						'United Arab Emirates': 'AE', 'United Kingdom': 'GB', 'United States': 'US', 'Vietnam': 'VN'}
	return countryDict[setting('mpa.country')]

def autoTraktSubscription(tvshowtitle, year, imdb, tvdb): #---start adding TMDb to params
	from resources.lib.modules import library
	library.libtvshows().add(tvshowtitle, year, imdb, tvdb)

def getColor(n):
	colorChart = ('cyan', 'darkgoldenrod', 'orange', 'mediumspringgreen', 'magenta', 'deeppink', 'red', 'gold', 'yellow',
						'yellowgreen', 'limegreen', 'lime', 'lawngreen', 'whitesmoke', 'white', 'nocolor')
	if not n: n = '8'
	color = colorChart[int(n)]
	return color

def getHighlightColor():
	return getColor(setting('highlight.color'))

def getSourceHighlightColor():
	return getColor(setting('sources.highlight.color'))


def getDebridHighlightColor(debrid_abv):
	"""Return a HEX color for a Debrid service abbreviation (RD/PM/AD/TB/etc).
	Falls back to the global source highlight color when unknown."""
	colors = {
		'RD': 'FFA43A4B',  # Real-Debrid
		'PM': 'FF7799B4',  # Premiumize
		'AD': 'FFE9B321',  # AllDebrid
		'OC': 'FFFF8800',  # Offcloud
		'ED': 'FFFF4444',  # EasyDebrid
		'TB': 'FF47A54A',  # TorBox
	}
	return colors.get(debrid_abv) or getSourceHighlightColor()
def getMenuEnabled(menu_title):
	is_enabled = setting(menu_title).strip()
	if (is_enabled == '' or is_enabled == 'false'): return False
	return True

def trigger_widget_refresh():
	import time
	timestr = time.strftime("%Y%m%d%H%M%S", time.gmtime())
	homeWindow.setProperty("widgetreload", timestr)
	homeWindow.setProperty('widgetreload-episodes', timestr)
	homeWindow.setProperty('widgetreload-movies', timestr)
	# execute('UpdateLibrary(video,/fake/path/to/force/refresh/on/home)') # make sure this is ok coupled with above

def refresh_playAction(): # for luc_kodi global CM play actions
	autoPlay = 'true' if setting('play.mode') == '1' else ''
	homeWindow.setProperty('luc_kodi.autoPlay.enabled', autoPlay)

def refresh_libPath(): # for luc_kodi global CM library actions
	homeWindow.setProperty('luc_kodi.movieLib.path', transPath(setting('library.movie')))
	homeWindow.setProperty('luc_kodi.tvLib.path', transPath(setting('library.tv')))

def refresh_debugReversed(): # called from service "onSettingsChanged" to clear luc_kodi.log if setting to reverse has been changed
	if homeWindow.getProperty('luc_kodidebug.reversed') != setting('debug.reversed'):
		homeWindow.setProperty('luc_kodi.debug.reversed', setting('debug.reversed'))
#		execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=tools_clearLogFile)')

def metadataClean(metadata):
	if not metadata: return metadata
	allowed = ('genre', 'country', 'year', 'episode', 'season', 'sortepisode', 'sortseason', 'episodeguide', 'showlink',
					'top250', 'setid', 'tracknumber', 'rating', 'userrating', 'watched', 'playcount', 'overlay', 'cast', 'castandrole',
					'director', 'mpaa', 'plot', 'plotoutline', 'title', 'originaltitle', 'sorttitle', 'duration', 'studio', 'tagline', 'writer',
					'tvshowtitle', 'premiered', 'status', 'set', 'setoverview', 'tag', 'imdbnumber', 'code', 'aired', 'credits', 'lastplayed',
					'album', 'artist', 'votes', 'path', 'trailer', 'dateadded', 'mediatype', 'dbid')
	return {k: v for k, v in iter(metadata.items()) if k in allowed}

def infoTagger(item, meta=None):
	if not meta: return
	meta_get = meta.get
	unique_ids = {i: val for i in ('imdb', 'tmdb', 'tvdb') if (val := meta_get(i))}
	if isinstance(votes := meta_get('votes', 0), str):
		votes = int(votes) if (votes := votes.replace(',', '')).isdecimal() else 0
	if KODI_VERSION < 20:
		item.setUniqueIDs(unique_ids)
		item.setCast(meta_get('castandart', []))
		item.setInfo(type='video', infoLabels=metadataClean(meta))
	else:
		infotag_dict = {'country_codes': 'setCountries',
						'duration': 'setDuration',
						'imdbnumber': 'setIMDBNumber',
						'mediatype': 'setMediaType',
						'mpaa': 'setMpaa',
						'originaltitle': 'setOriginalTitle',
						'playcount': 'setPlaycount',
						'plot': 'setPlot',
						'premiered': 'setPremiered',
						'status': 'setTvShowStatus',
						'tag': 'setTags',
						'tagline': 'setTagLine',
						'title': 'setTitle',
						'trailer': 'setTrailer',
						'tvshowtitle': 'setTvShowTitle',
						'episode': 'setEpisode',
						'season': 'setSeason',
						'year': 'setYear',
						'rating': 'setRating',
						'votes': 'setVotes',
						'director': 'setDirectors',
						'genre': 'setGenres',
						'studio': 'setStudios',
						'writer': 'setWriters'}
		infotag = item.getVideoInfoTag()
		infotag.setUniqueIDs(unique_ids)
		infotag.setCast([xbmc.Actor(**actor) for actor in meta_get('castandart', [])])
		for key in infotag_dict:
			if not key in meta or not (arg := meta[key]): continue
			if   key in {'director', 'genre', 'studio', 'writer'}: arg = arg.split(', ')
			elif key in {'episode', 'season', 'year'}: arg = int(arg)
			elif key == 'rating': arg = float(arg)
			elif key == 'votes': arg = votes
			func = getattr(infotag, infotag_dict[key])
			func(arg)