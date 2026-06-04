# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from json import loads as jsloads
from threading import Thread
from urllib.parse import unquote
from resources.lib.modules.control import addonFanart, jsonrpc, setting as getSetting
from resources.lib.windows.base import BaseDialog

class WindowProgress(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.closed = False
		try:
			self.meta = kwargs.get('meta')
		except:
			self.meta = None
		self.imdb = self.meta.get('imdb')
		self.tvdb = self.meta.get('tvdb')
		self.year = self.meta.get('year')
		self.season = self.meta.get('season')
		self.episode = self.meta.get('episode')
		# v1.0.14: 'progress.dialog' enum was reduced to 2 values (0=Foreground, 1=Background).
		# Legacy icon-only (3) and Hidden (4) modes were unreachable code paths and removed.
		# Background mode is handled by sources.py (it never instantiates this dialog).
		self.use_fanart = True  # always show content fanart in progress window
		self.set_controls()

	def run(self):
		self.doModal()
		self.clearProperties()

	def create(self):
		"""Run doModal in a background thread so the caller can continue."""
		t = Thread(target=self.run)
		t.daemon = True
		t.start()

	def onAction(self, action):
		if action in self.closing_actions or action in self.selection_actions:
			self.doClose()

	def doClose(self):
		self.closed = True
		self.close()
		del self

	def iscanceled(self):
		return self.closed

	def set_controls(self):
		if self.meta is None:
			self.meta = self.checkLocalMeta()
		if self.meta:
			if self.meta.get('clearlogo'): self.setProperty('luc_kodi.clearlogo', self.meta.get('clearlogo'))
			# Always use content fanart when available
			self.setProperty('luc_kodi.fanart', self.meta.get('fanart') or addonFanart())
			# v1.0.14: build display title — show "Show Title — Episode Title" for episodes,
			# plain title for movies. Previously 'luc_kodi.tvtitle' was set but never displayed in the XML.
			_title = self.meta.get('title') or ''
			_tvtitle = self.meta.get('tvshowtitle') or ''
			if _tvtitle and _title and _tvtitle != _title:
				display_title = '%s — %s' % (_tvtitle, _title)
			else:
				display_title = _title or _tvtitle
			if display_title: self.setProperty('luc_kodi.title', display_title)
			if self.meta.get('plot'): self.setProperty('luc_kodi.plot', self.meta.get('plot', ''))
		else:
			self.setProperty('luc_kodi.fanart', addonFanart())
		# Initialise live stats to zero so the XML shows 0 immediately
		for _p in ('luc_kodi.src.4k', 'luc_kodi.src.1080', 'luc_kodi.src.720',
		           'luc_kodi.src.sd', 'luc_kodi.src.total', 'luc_kodi.src.elapsed',
		           'luc_kodi.src.providers', 'luc_kodi.src.providers_count'):
			self.setProperty(_p, '0')

	def update(self, percent=0, content=''):
		try:
			self.getControl(2001).setText(content)
			self.setProperty('percent', str(percent))
			#self.getControl(5000).setPercent(percent)
		except: pass

	def checkLocalMeta(self):
		try:
			def cleanLibArt(art):
				if not art: return ''
				art = unquote(art.replace('image://', ''))
				if art.endswith('/'): art = art[:-1]
				return art
			self.media_type = 'movie' if self.season is None or self.episode is None else 'episode'
			if self.media_type == 'movie':
				# do not add IMDBNUMBER as tmdb scraper puts their id in the key value
				meta = jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "uniqueid", "year", "premiered", "genre", "studio", "country", "runtime", "rating", "votes", "mpaa", "director", "writer", "cast", "plot", "plotoutline", "tagline", "thumbnail", "art", "file"]}, "id": 1}' % (self.year, str(int(self.year) + 1), str(int(self.year) - 1)))
				meta = jsloads(meta)['result']['movies']
				meta = [i for i in meta if i.get('uniqueid', []).get('imdb', '') == self.imdb]
				if meta: meta = meta[0]
				else: raise Exception()
				if 'mediatype' not in meta: meta.update({'mediatype': 'movie'})
				fanart = cleanLibArt(meta.get('art').get('fanart', '')) or self.fanart
				clearlogo = cleanLibArt(meta.get('art').get('clearlogo', ''))
				meta.update({'imdb': self.imdb, 'tvdb': self.tvdb, 'fanart': fanart, 'clearlogo': clearlogo})
				return meta
			else:
				if self.media_type != 'episode': raise Exception()
				# do not add IMDBNUMBER as tmdb scraper puts their id in the key value
				show_meta = jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "uniqueid", "mpaa", "year", "genre", "runtime", "thumbnail", "file"]}, "id": 1}' % (self.year, str(int(self.year)+1), str(int(self.year)-1)))
				show_meta = jsloads(show_meta)['result']['tvshows']
				show_meta = [i for i in show_meta if i.get('uniqueid', []).get('imdb', '') == self.imdb]
				if show_meta: show_meta = show_meta[0]
				else: raise Exception()
				tvshowid = show_meta['tvshowid']
				meta = jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params":{"tvshowid": %d, "filter":{"and": [{"field": "season", "operator": "is", "value": "%s"}, {"field": "episode", "operator": "is", "value": "%s"}]}, "properties": ["title", "season", "episode", "showtitle", "firstaired", "runtime", "rating", "director", "writer", "cast", "plot", "thumbnail", "art", "file"]}, "id": 1}' % (tvshowid, self.season, self.episode))
				meta = jsloads(meta)['result']['episodes']
				if meta: meta = meta[0]
				else: raise Exception()
				if 'mediatype' not in meta: meta.update({'mediatype': 'episode'})
				if 'tvshowtitle' not in meta: meta.update({'tvshowtitle': meta.get('showtitle')})
				if 'premiered' not in meta: meta.update({'premiered': meta.get('firstaired')})
				if 'year' not in meta: meta.update({'year': show_meta.get('year')}) # shows year not year episode aired
				fanart = cleanLibArt(meta.get('art').get('tvshow.fanart', '')) or self.poster
				clearlogo = cleanLibArt(meta.get('art').get('tvshow.clearlogo', ''))
				meta.update({'imdb': self.imdb, 'tvdb': self.tvdb, 'fanart': fanart,'clearlogo': clearlogo})
				return meta
		except:
			from resources.lib.modules import log_utils
			log_utils.log('Checking Local Meta Exception', log_utils.LOGDEBUG)
			return None

# Alias used by sources.py
SourceProgressXML = WindowProgress
