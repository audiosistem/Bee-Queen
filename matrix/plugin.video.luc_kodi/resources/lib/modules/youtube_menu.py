# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

import re
from sys import argv
from urllib.request import urlopen, Request
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem


class youtube_menu(object):
	def __init__(self):
		self.agent = 'luc_kodiAddonAgent'
		# v1.0.68: se retira un `self.key_id` con una clave de API de Google real
		# heredada del framework. No la usaba NADA en todo el arbol (la unica
		# aparicion era esta linea), y viajaba dentro de un repositorio publico,
		# donde el escaner de credenciales de Google la encuentra y la revoca.
		# Los menus de YouTube funcionan por scraping del fichero de menu, sin
		# tocar la Data API, asi que no hace falta ninguna clave aqui.

	def openMenuFile(self, menuFile):
		try:
			req = Request(menuFile)
			req.add_header('User-Agent', self.agent)
			response = urlopen(req)
			link = response.read().decode('utf-8')
			response.close()
			return link
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def processMenuFile(self, menuFile):
		try:
			link = self.openMenuFile(menuFile).replace('\n','').replace('\r','')
			match = re.compile(r'name="(.+?)".+?ection="(.+?)".+?earch="(.+?)".+?ubid="(.+?)".+?laylistid="(.+?)".+?hannelid="(.+?)".+?ideoid="(.+?)".+?con="(.+?)".+?anart="(.+?)".+?escription="(.+?)"').findall(link)
			return match
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addMenuItem(self, name, action, subid, iconimage, fanart, description='', isFolder=True):
		try:
			url = 'plugin://plugin.video.luc_kodi/?action=%s&id=%s' % (action, subid)
			liz = ListItem(label=name, offscreen=True)
			liz.setArt({'icon': 'DefaultFolder.png', 'thumb': iconimage, 'fanart': fanart})
			liz.setInfo(type='video', infoLabels={'title': name, 'plot': description})
			addDirectoryItem(handle=int(argv[1]), url=url, listitem=liz, isFolder=isFolder)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addSectionItem(self, name, iconimage, fanart):
		try:
			url = 'plugin://plugin.video.luc_kodi/?action=sectionItem'
			liz = ListItem(label=name, offscreen=True)
			liz.setArt({'icon': 'DefaultFolder.png', 'thumb': iconimage, 'fanart': fanart})
			liz.setInfo(type='video', infoLabels={'title': name})
			addDirectoryItem(handle=int(argv[1]), url=url, listitem=liz, isFolder=False)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addSearchItem(self, name, search_id, icon, fanart):
		try:
			work_url = "plugin://plugin.video.youtube/kodion/search/query/?q=%s" % search_id
			liz = ListItem(name)
			liz.setInfo( type='video', infoLabels={'title': name})
			liz.setArt({'thumb': icon, 'banner': 'DefaultVideo.png', 'fanart': fanart})
			addDirectoryItem(handle=int(argv[1]), url=work_url, listitem=liz, isFolder=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addChannelItem(self, name, channel_id, icon, fanart):
		try:
			work_url = "plugin://plugin.video.youtube/channel/%s/" % channel_id
			liz = ListItem(name)
			liz.setInfo( type='video', infoLabels={'title': name})
			liz.setArt({'thumb': icon, 'banner': 'DefaultVideo.png', 'fanart': fanart})
			addDirectoryItem(handle=int(argv[1]), url=work_url, listitem=liz, isFolder=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addUserItem(self, name, channel_id, icon, fanart):
		try:
			user = channel_id
			work_url = "plugin://plugin.video.youtube/user/%s/" % user
			liz = ListItem(name)
			liz.setInfo( type='video', infoLabels={'title': name})
			liz.setArt({'thumb': icon, 'banner': 'DefaultVideo.png', 'fanart': fanart})
			addDirectoryItem(handle=int(argv[1]), url=work_url, listitem=liz, isFolder=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addPlaylistItem(self, name, playlist_id, icon, fanart):
		try:
			work_url = "plugin://plugin.video.youtube/playlist/%s/" % playlist_id
			liz = ListItem(name)
			liz.setInfo( type='video', infoLabels={'title': name})
			liz.setArt({'thumb': icon, 'banner': 'DefaultVideo.png', 'fanart': fanart})
			addDirectoryItem(handle=int(argv[1]), url=work_url, listitem=liz, isFolder=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def addVideoItem(self, name, video_id, icon, fanart):
		try:
			work_url = "plugin://plugin.video.youtube/play/?video_id=%s" % video_id
			liz = ListItem(name)
			liz.setInfo( type='video', infoLabels={'title': name})
			liz.setArt({'thumb': icon, 'banner': 'DefaultVideo.png', 'fanart': fanart})
			liz.setProperty('IsPlayable', 'true')
			addDirectoryItem(handle=int(argv[1]), url=work_url, listitem=liz, isFolder=False)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
