"""
	luc_kodi Add-on
"""
from ast import literal_eval

from collections import deque
from datetime import datetime, timedelta
from json import dumps as jsdumps, loads as jsloads
import re
import _strptime # import _strptime to workaround python 2 bug with threads
from sys import argv, exit as sysexit
from threading import Thread
from time import time
from urllib.parse import unquote, quote_plus
from sqlite3 import dbapi2 as database
from resources.lib.database import metacache, providerscache
from resources.lib.modules import cleandate
from resources.lib.modules import control
from resources.lib.modules import debrid
from resources.lib.modules import log_utils
from resources.lib.modules import string_tools
from resources.lib.modules.source_utils import supported_video_extensions, getFileType, aliases_check
from resources.lib.cloud_scrapers import cloudSources
from resources.lib.jacksparrow import sources as fs_sources

homeWindow = control.homeWindow
playerWindow = control.playerWindow
getLS = control.lang
getSetting = control.setting
sourceFile = control.providercacheFile
single_expiry = timedelta(hours=6)
season_expiry = timedelta(hours=48)
show_expiry = timedelta(hours=48)
video_extensions = supported_video_extensions()

class Sources:
	def __init__(self, all_providers=False, custom_query=False, filterless_scrape=False):
		self.sources = []
		self.scraper_sources = deque() # []
		self.uncached_chosen = False
		self.isPrescrape = False
		self.progressDialog = None
		self.all_providers = all_providers
		self.custom_query = custom_query
		self.filterless_scrape = filterless_scrape
		self.time = datetime.now()
		self.getConstants()
		self.enable_playnext = getSetting('enable.playnext') == 'true'
		self.dev_mode = getSetting('dev.mode.enable') == 'true'
		self.dev_disable_single = getSetting('dev.disable.single') == 'true'
		# self.dev_disable_single_filter = getSetting('dev.disable.single.filter') == 'true'
		self.dev_disable_season_packs = getSetting('dev.disable.season.packs') == 'true'
		self.dev_disable_season_filter = getSetting('dev.disable.season.filter') == 'true'
		self.dev_disable_show_packs = getSetting('dev.disable.show.packs') == 'true'
		self.dev_disable_show_filter = getSetting('dev.disable.show.filter') == 'true'
		self.highlight_color = control.getColor(getSetting('scraper.dialog.color'))

	def play(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select, rescrape=None):
		if not self.prem_providers:
			# Bypass the Debrid guard if a custom scraper that handles its own
			# Debrid resolution is active and properly configured.
			# AIOStreams: resolves Debrid on its side -> returns direct URLs.
			# MediaFusion: secret_str URL already encodes Debrid credentials.
			# Sootio:     config token already encodes Debrid credentials.
			_aio_active = (getSetting('provider.aiostreams') == 'true'
			               and getSetting('aiostreams.uuid')
			               and getSetting('aiostreams.password'))
			_mf_active  = (getSetting('provider.mediafusion') == 'true'
			               and getSetting('mediafusion.secret'))
			_sootio_active = (getSetting('provider.sootio') == 'true'
			                  and getSetting('sootio.config'))
			if not (_aio_active or _mf_active or _sootio_active):
				control.sleep(200) ; control.hide()
				homeWindow.clearProperty('luc_kodi.bingie_direct')
				return control.notification(message=33034)
		try:
			control.sleep(200)
			if control.playlist.getposition() == 0 or control.playlist.size() == 1: playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
			preResolved_nextUrl = ''  # preResolved desactivado v0.0.92 — on-demand dialog
			if preResolved_nextUrl != '':
				control.sleep(500)
				playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')
				try: meta = jsloads(unquote(meta.replace('%22', '\\"')))
				except: pass
				log_utils.log('Playing preResolved_nextUrl = %s' % preResolved_nextUrl, level=log_utils.LOGDEBUG)
				from resources.lib.modules import player
				return player.Player().play_source(title, year, season, episode, imdb, tmdb, tvdb, preResolved_nextUrl, meta)
			if title: title = self.getTitle(title)
			if tvshowtitle: tvshowtitle = self.getTitle(tvshowtitle)
			homeWindow.clearProperty(self.metaProperty)
			homeWindow.setProperty(self.metaProperty, meta)
			homeWindow.clearProperty(self.seasonProperty)
			homeWindow.setProperty(self.seasonProperty, season)
			homeWindow.clearProperty(self.episodeProperty)
			homeWindow.setProperty(self.episodeProperty, episode)
			homeWindow.clearProperty(self.titleProperty)
			homeWindow.setProperty(self.titleProperty, title)
			homeWindow.clearProperty(self.imdbProperty)
			homeWindow.setProperty(self.imdbProperty, imdb)
			homeWindow.clearProperty(self.tmdbProperty)
			homeWindow.setProperty(self.tmdbProperty, tmdb)
			homeWindow.clearProperty(self.tvdbProperty)
			homeWindow.setProperty(self.tvdbProperty, tvdb)
			if tvshowtitle is None: p_label = '[COLOR %s]%s (%s)[/COLOR]' % (self.highlight_color, title, year)
			else: p_label = '[COLOR %s]%s (S%02dE%02d)[/COLOR]' % (self.highlight_color, tvshowtitle, int(season), int(episode))
			homeWindow.clearProperty(self.labelProperty)
			homeWindow.setProperty(self.labelProperty, p_label)
			url = None
			self.mediatype = 'movie' if tvshowtitle is None else 'episode'
			try: meta = jsloads(unquote(meta.replace('%22', '\\"')))
			except: pass
			# --- AUTO-PLAYLIST para PlayNext ---
			# Construimos la playlist completa (E01, E02, ...) antes de empezar a reproducir.
			# Esto permite que Kodi avance la playlist nativamente al terminar cada episodio,
			# y que BigSkipForward (Play Now del popup) funcione correctamente.
			# FIX vs v0.0.43: resolvemos H1 con False inmediatamente para evitar el
			# salto a E02 a los 10 segundos que causaba el timeout del handle original.
			# AUTO-PLAYLIST desactivado v0.0.92 — reemplazado por diálogo post-stop on-demand.
			# Causaba: salto a E02 a los 2s + interceptaba 'Elegir Fuente' antes de sourceSelect.
			if False and self.mediatype == 'episode' and self.enable_playnext and int(control.playlist.size()) <= 1:
				try:
					from resources.lib.menus import episodes as episodes_menu
					items_ep = episodes_menu.Episodes().get(tvshowtitle, year, imdb, tmdb, tvdb, meta, season, episode, create_directory=False)
					def _to_int(x):
						try: return int(str(x))
						except: return None
					cur_s = _to_int(season)
					cur_e = _to_int(episode)
					start_idx = 0
					for idx, it in enumerate(items_ep):
						if _to_int(it.get('season')) == cur_s and _to_int(it.get('episode')) == cur_e:
							start_idx = idx
							break
					items_ep = items_ep[start_idx:]
					if items_ep and len(items_ep) > 1:
						control.playlist.clear()
						for it in items_ep:
							title_i = it.get('title') or ''
							year_i = it.get('year') or year
							imdb_i = it.get('imdb') or imdb
							tmdb_i = it.get('tmdb') or tmdb
							tvdb_i = it.get('tvdb') or tvdb
							season_i = it.get('season') or season
							episode_i = it.get('episode') or episode
							tvshowtitle_i = it.get('tvshowtitle') or tvshowtitle
							premiered_i = it.get('premiered') or ''
							systitle_i = quote_plus(title_i)
							systvshowtitle_i = quote_plus(tvshowtitle_i)
							sysmeta_i = quote_plus(jsdumps(it))
							ep_url = (
								'plugin://plugin.video.luc_kodi/?action=play_Item'
								'&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s'
								'&season=%s&episode=%s&tvshowtitle=%s&premiered=%s'
								'&meta=%s&select=1'
							) % (systitle_i, year_i, imdb_i, tmdb_i, tvdb_i, season_i, episode_i, systvshowtitle_i, premiered_i, sysmeta_i)
							li = control.item(label=title_i, offscreen=True)
							li.setProperty('IsPlayable', 'true')
							control.playlist.add(url=ep_url, listitem=li)
						control.player2().play(control.playlist)
						# FIX: cerrar H1 inmediatamente (False) para evitar timeout de 10s que causa salto a E02.
						# La playlist llama al plugin de nuevo para E01 con un handle H2 fresco.
						import xbmcplugin
						xbmcplugin.setResolvedUrl(int(argv[1]), False, control.item())
						return
				except:
					log_utils.error()
			# --- FIN AUTO-PLAYLIST ---
## - compare meta received to database and use largest(eventually switch to a request to fetch missing db meta for item)
			self.imdb_user = getSetting('imdb.user').replace('ur', '')
			self.tmdb_key = getSetting('tmdb.api.key')
			if not self.tmdb_key: self.tmdb_key = 'f2e500501d9fa3bd1637bfd00f11583a'
			self.tvdb_key = getSetting('tvdb.api.key')
			if self.mediatype == 'episode': self.user = str(self.imdb_user) + str(self.tvdb_key)
			else: self.user = str(self.tmdb_key)
			self.lang = control.apiLanguage()['tvdb']
			ids = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb}
			meta1 = dict((k, v) for k, v in iter(meta.items()) if v is not None and v != '') if meta else None
			meta2 = metacache.fetch([{'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb}], self.lang, self.user)[0]
			if meta2 != ids: meta2 = dict((k, v) for k, v in iter(meta2.items()) if v is not None and v != '')
			if meta1 is not None:
				try:
					if len(meta2) > len(meta1):
						meta2.update(meta1)
						meta = meta2
					else: meta = meta1
				except: log_utils.error()
			else: meta = meta2 if meta2 != ids else meta1
##################
			self.poster = meta.get('poster') if meta else ''
			self.fanart = meta.get('fanart') if meta else ''
			self.meta = meta

			def checkLibMeta(): # check Kodi db for meta for library playback.
				def cleanLibArt(art):
					if not art: return ''
					art = unquote(art.replace('image://', ''))
					if art.endswith('/'): art = art[:-1]
					return art
				try:
					if self.mediatype != 'movie': raise Exception()
					# do not add IMDBNUMBER as tmdb scraper puts their id in the key value
					meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "uniqueid", "year", "premiered", "genre", "studio", "country", "runtime", "rating", "votes", "mpaa", "director", "writer", "cast", "plot", "plotoutline", "tagline", "thumbnail", "art", "file"]}, "id": 1}' % (year, str(int(year) + 1), str(int(year) - 1)))
					meta = jsloads(meta)['result']['movies']
					meta = [i for i in meta if i.get('uniqueid', []).get('imdb', '') == imdb]
					if meta: meta = meta[0]
					else: raise Exception()
					if 'mediatype' not in meta: meta.update({'mediatype': 'movie'})
					if 'duration' not in meta: meta.update({'duration': meta.get('runtime')}) # Trakt scrobble resume needs this for lib playback
					if 'castandrole' not in meta: meta.update({'castandrole': [(i['name'], i['role']) for i in meta.get('cast')]})
					poster = cleanLibArt(meta.get('art').get('poster', '')) or self.poster
					fanart = cleanLibArt(meta.get('art').get('fanart', '')) or self.fanart
					clearart = cleanLibArt(meta.get('art').get('clearart', ''))
					clearlogo = cleanLibArt(meta.get('art').get('clearlogo', ''))
					discart = cleanLibArt(meta.get('art').get('discart'))
					meta.update({'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'poster': poster, 'fanart': fanart, 'clearart': clearart, 'clearlogo': clearlogo, 'discart': discart})
					return meta
				except:
					log_utils.error()
					meta = ''
				try:
					if self.mediatype != 'episode': raise Exception()
					# do not add IMDBNUMBER as tmdb scraper puts their id in the key value
					show_meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "uniqueid", "mpaa", "year", "genre", "runtime", "thumbnail", "file"]}, "id": 1}' % (year, str(int(year)+1), str(int(year)-1)))
					show_meta = jsloads(show_meta)['result']['tvshows']
					show_meta = [i for i in show_meta if i.get('uniqueid', []).get('imdb', '') == imdb]
					if show_meta: show_meta = show_meta[0]
					else: raise Exception()
					tvshowid = show_meta['tvshowid']
					meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params":{"tvshowid": %d, "filter":{"and": [{"field": "season", "operator": "is", "value": "%s"}, {"field": "episode", "operator": "is", "value": "%s"}]}, "properties": ["title", "season", "episode", "showtitle", "firstaired", "runtime", "rating", "director", "writer", "cast", "plot", "thumbnail", "art", "file"]}, "id": 1}' % (tvshowid, season, episode))
					meta = jsloads(meta)['result']['episodes']
					if meta: meta = meta[0]
					else: raise Exception()
					if 'mediatype' not in meta: meta.update({'mediatype': 'episode'})
					if 'tvshowtitle' not in meta: meta.update({'tvshowtitle': meta.get('showtitle')})
					if 'castandrole' not in meta: meta.update({'castandrole': [(i['name'], i['role']) for i in meta.get('cast')]})
					if 'genre' not in meta: meta.update({'genre': show_meta.get('genre')})
					if 'duration' not in meta: meta.update({'duration': meta.get('runtime')}) # Trakt scrobble resume needs this for lib playback but Kodi lib returns "0" for shows or episodes
					if 'mpaa' not in meta: meta.update({'mpaa': show_meta.get('mpaa')})
					if 'premiered' not in meta: meta.update({'premiered': meta.get('firstaired')})
					if 'year' not in meta: meta.update({'year': show_meta.get('year')}) # shows year not year episode aired
					poster = cleanLibArt(meta.get('art').get('season.poster', '')) or self.poster
					fanart = cleanLibArt(meta.get('art').get('tvshow.fanart', '')) or self.poster
					clearart = cleanLibArt(meta.get('art').get('tvshow.clearart', ''))
					clearlogo = cleanLibArt(meta.get('art').get('tvshow.clearlogo', ''))
					discart = cleanLibArt(meta.get('art').get('discart'))
					meta.update({'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'poster': poster, 'fanart': fanart, 'clearart': clearart, 'clearlogo': clearlogo, 'discart': discart})
					return meta
				except:
					log_utils.error()
					meta = ''
			if self.meta is None or 'videodb' in control.infoLabel('ListItem.FolderPath'):
				self.meta = checkLibMeta()
			def sourcesDirMeta(metadata): # pass skin minimal meta needed
				if not metadata: return metadata
				if getSetting('fanart') == 'false': metadata['fanart'] = ''
				if getSetting('prefer.tmdbArt') == 'true': metadata['clearlogo'] = metadata.get('tmdblogo') or metadata.get('clearlogo') or ''
				allowed = ['mediatype', 'imdb', 'tmdb', 'tvdb', 'poster', 'tvshow.poster', 'season_poster', 'season_poster', 'fanart', 'clearart', 'clearlogo', 'discart', 'thumb', 'title', 'tvshowtitle', 'year', 'premiered', 'rating', 'plot', 'duration', 'mpaa', 'season', 'episode', 'castandrole']
				return {k: v for k, v in iter(metadata.items()) if k in allowed}
			self.meta = sourcesDirMeta(self.meta)
			if self.mediatype == 'movie':
				if getSetting('imdb.Moviemeta.check') == 'true': # check IMDB. TMDB and Trakt differ on a ratio of 1 in 20 and year is off by 1, some meta titles mismatch
					title, year = self.imdb_meta_chk(imdb, title, year)
				if title == 'The F**k-It List': title = 'The Fuck-It List'
			if self.mediatype == 'episode':
				if getSetting('imdb.Showmeta.check') == 'true':
					tvshowtitle, year = self.imdb_meta_chk(imdb, tvshowtitle, year)
				if tvshowtitle == 'The End of the F***ing World': tvshowtitle = 'The End of the Fucking World'
				self.total_seasons, self.season_isAiring = self.get_season_info(imdb, tmdb, tvdb, meta, season)
			if rescrape: self.clr_item_providers(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered)
			cache_id = self._build_ramcache_id(imdb, tmdb, tvdb, season, episode, year)
			items = None
			if not rescrape and not self.custom_query and getSetting('sources.ramcache.enabled') == 'true':
				items = self._ramcache_get(cache_id)
			if not items:
				items = providerscache.get(self.getSources, 48, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered)
				if items and not rescrape and not self.custom_query and getSetting('sources.ramcache.enabled') == 'true':
					self._ramcache_set(cache_id, items)
			if not items:
				self.url = url
				return self.errorForSources()
			filter = [] ; uncached_items = []
			if getSetting('torrent.remove.uncached') == 'true':
				uncached_items += [i for i in items if re.match(r'^uncached.*torrent', i['source'])]
				filter += [i for i in items if i not in uncached_items]
				if filter: pass
				elif not filter:
					homeWindow.clearProperty('luc_kodi.source_progress_is_alive')
					if control.yesnoDialog('No cached torrents returned. Would you like to view the uncached torrents to cache yourself?', '', ''):
						control.cancelPlayback()
						select = '0'
						self.uncached_chosen = True
						filter += uncached_items
				items = filter
				if not items:
					self.url = url
					return self.errorForSources()
			else: uncached_items += [i for i in items if re.match(r'^uncached.*torrent', i['source'])]
			if select is None:
				if episode is not None and self.enable_playnext: select = '1'
				else: select = getSetting('play.mode')
			title = tvshowtitle if tvshowtitle is not None else title
			self.imdb = imdb ; self.tmdb = tmdb ; self.tvdb = tvdb ; self.title = title ; self.year = year
			self.season = season ; self.episode = episode
			self.ids = {'imdb': self.imdb, 'tmdb': self.tmdb, 'tvdb': self.tvdb}
			if len(items) > 0:
				if select == '0':
					control.sleep(200)
					return self.sourceSelect(title, items, uncached_items, self.meta)
				else: url = self.sourcesAutoPlay(items)
			if url == 'close://' or url is None:
				self.url = url
				return self.errorForSources()
			from resources.lib.modules import player
			_player_inst = player.Player()
			_player_inst.play_source(title, year, season, episode, imdb, tmdb, tvdb, url, self.meta)
			# FALLBACK_SETRESOLVEDURL: solo si el player NUNCA arrancó (current_time < 5s)
			# Y no estamos en modo next_ep_direct (el ep siguiente ya está buscando).
			try:
				from sys import argv as _argv
				from resources.lib.modules import control as _control
				_control.sleep(800)
				# Si next_ep_direct está activo significa que ya lanzamos el ep siguiente:
				# no volver a invocar el plugin o se abrirá una segunda búsqueda.
				_next_ep_active = homeWindow.getProperty('luc_kodi.next_ep_direct') == 'true'
				_bingie_active = homeWindow.getProperty('luc_kodi.bingie_direct') == 'true'
				_never_played = getattr(_player_inst, 'current_time', 0) < 5
				if _never_played and not _next_ep_active and not _bingie_active and not _control.condVisibility('Player.HasVideo') and url and url.startswith(('http','https')):
					item = _control.item(path=url)
					_control.resolve(int(_argv[1]), True, item)
			except Exception as e:
				pass
		except:
			log_utils.error()
			control.cancelPlayback()

	def sourceSelect(self, title, items, uncached_items, meta):
		try:
			control.hide()
			control.playlist.clear()
			if not items:
				control.sleep(200) ; control.hide() ; sysexit()
			if not self.meta: self.meta = meta
		except: log_utils.error('Error sourceSelect(): ')

		try:
			if getSetting('uncached.seeder.sort') == 'true':
				uncached_items = sorted(uncached_items, key=lambda k: k['seeders'], reverse=True)
				uncached_items = self.sort_byQuality(source_list=uncached_items)
			# Attach smart score for Source Select display
			try:
				for _it in (items or []):
					try: _it['score'] = self._smart_score(_it)
					except: pass
				for _it in (uncached_items or []):
					try: _it['score'] = self._smart_score(_it)
					except: pass
			except:
				pass

			if items == uncached_items:
				from resources.lib.windows.uncached_results import UncachedResultsXML
				window = UncachedResultsXML('uncached_results.xml', control.addonPath(control.addonId()), uncached=uncached_items, meta=self.meta)
			else:
				from resources.lib.windows.source_results import SourceResultsXML
				window = SourceResultsXML('source_results.xml', control.addonPath(control.addonId()), results=items, uncached=uncached_items, meta=self.meta)
			action, chosen_source = window.run()
			del window
			if action == 'play_Item' and self.uncached_chosen != True:
				return self.playItem(title, items, chosen_source.getProperty('luc_kodi.source_dict'), self.meta)
			else:
				try: self.progressDialog.close()
				except: pass
				control.cancelPlayback()
		except:
			log_utils.error('Error sourceSelect(): ')
			control.cancelPlayback()

	def playItem(self, title, items, chosen_source, meta):
		try:
			try: items = jsloads(items)
			except: pass
			try: meta = jsloads(meta)
			except: pass
			try:
				# Robust JSON parsing for items/chosen_source
				try:
					chosen_source = jsloads(chosen_source)
				except:
					chosen_source = chosen_source if isinstance(chosen_source, list) else [chosen_source]
				if isinstance(items, str):
					try: items = jsloads(items)
					except: items = []
				if not isinstance(items, list):
					items = [items] if items else []
				try:
					source_index = items.index(chosen_source[0]) if items and chosen_source else 0
				except:
					source_index = 0
				source_len = len(items)
				next_end = min(source_len, source_index+41)
				sources_next = items[source_index+1:next_end]
				sources_prev = [] if next_end < source_len else items[0:41-(source_len-source_index)]
				resolve_items = [i for i in ( (chosen_source or []) + sources_next + sources_prev )] or items
			except:
				log_utils.error()
				resolve_items = items if isinstance(items, list) else [items] if items else []

			header = homeWindow.getProperty(self.labelProperty) + ': Resolving...'
			try:
				if getSetting('progress.dialog') == '0':
					if not self.progressDialog:
						self.progressDialog = self.getSourceProgress(header, meta)
				else: raise Exception()
			except:
				homeWindow.clearProperty('luc_kodi.source_progress_is_alive')
				self.progressDialog = control.progressDialogBG
				self.progressDialog.create(header, '')
			for i in range(len(resolve_items)):
				try:
					resolve_index = items.index(resolve_items[i])+1
					src_provider = resolve_items[i]['debrid'] if resolve_items[i].get('debrid') else ('%s - %s' % (resolve_items[i]['source'], resolve_items[i]['provider']))
					label = '[B][COLOR %s]%s[CR]%s[CR]%02d.  %s[/COLOR][/B]' % (self.highlight_color, src_provider.upper(), resolve_items[i]['info'][:40], resolve_index, resolve_items[i]['name'][:40]) # using "[CR]" has some weird delay with progressDialog.update() at times
					control.sleep(100)
					try:
						if self.progressDialog == control.progressDialogBG and self.progressDialog.iscanceled(): break
						self.progressDialog.update(int((100 / float(len(resolve_items))) * i), label)
					except: self.progressDialog.update(int((100 / float(len(resolve_items))) * i), '[B][COLOR %s]Resolving...[/COLOR]%s[/B]' % (self.highlight_color, resolve_items[i]['name']))
					w = Thread(target=self.sourcesResolve, args=(resolve_items[i],))
					w.start()
					for x in range(50):
						try:
							if control.monitor.abortRequested(): return sysexit()
							if self.progressDialog == control.progressDialogBG and self.progressDialog.iscanceled():
								control.notification(message=32398)
								control.cancelPlayback()
								self.progressDialog.close()
								del self.progressDialog
								return
						except: pass
						if not w.is_alive(): break
						control.sleep(300)
					if not self.url: continue
					# Optional URL validity check (skip dead links / HTML error pages)
					try:
						if getSetting('validate.source.urls') == 'true':
							from resources.lib.modules import urlcheck
							if not urlcheck.check_url_validity(self.url):
								log_utils.log('Rejected invalid URL (playItem): %s' % self.url, level=log_utils.LOGWARNING)
								self.url = None
								continue
					except Exception:
						pass

					item = resolve_items[i]
					is_aiostreams_direct = item.get('aiostreams_direct') or (item.get('provider') == 'aiostreams' and item.get('direct') is True)
					if (not any(x in self.url.lower() for x in video_extensions) and '/dld/' not in self.url) and not is_aiostreams_direct:
						log_utils.log('Playback not supported for (playItem()): %s' % self.url, level=log_utils.LOGWARNING)
						continue
					log_utils.log('Playing url from playItem(): %s' % self.url, level=log_utils.LOGDEBUG)
					if homeWindow.getProperty('luc_kodi.source_progress_is_alive') != 'true':
						try: self.progressDialog.close()
						except: pass
						del self.progressDialog
					# v1.0.21 SCROBBLE FIX: route manual source selection through
					# player.Player().play_source() instead of doing setResolvedUrl
					# directly. Otherwise no Player instance is created, keepAlive
					# never runs, and onAVStarted/onPlayBackStopped callbacks fire
					# on a dead instance — breaking Trakt/SIMKL scrobble + subtitles.
					# play_source handles the next-ep direct case internally (it
					# uses control.player.play vs control.resolve based on the
					# luc_kodi.next_ep_direct window property).
					# This is exactly what Umbrella does in its playItem (line 511).
					from resources.lib.modules import player as _player_mod
					_player_mod.Player().play_source(
						getattr(self, 'title', title) or title,
						getattr(self, 'year', None),
						getattr(self, 'season', None),
						getattr(self, 'episode', None),
						getattr(self, 'imdb', '') or '',
						getattr(self, 'tmdb', '') or '',
						getattr(self, 'tvdb', '') or '',
						self.url,
						self.meta if isinstance(self.meta, dict) else (meta if isinstance(meta, dict) else {})
					)
					return self.url
				except: log_utils.error()
			try: self.progressDialog.close()
			except: pass
			del self.progressDialog
			self.errorForSources()
		except: log_utils.error('Error playItem: ')

	def getSources(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta=None, preScrape=False):
		if preScrape:
			self.isPrescrape = True
			if tvshowtitle is not None:
				self.mediatype = 'episode'
				self.meta = meta
				self.total_seasons, self.season_isAiring = self.get_season_info(imdb, tmdb, tvdb, meta, season)
			return self.getSources_silent(title, year, imdb, tvdb, season, episode, tvshowtitle, premiered)
		else:
			return self.getSources_dialog(title, year, imdb, tvdb, season, episode, tvshowtitle, premiered)

	def getSources_silent(self, title, year, imdb, tvdb, season, episode, tvshowtitle, premiered, timeout=90):
		try:
			p_label = '[COLOR %s]%s (S%02dE%02d)[/COLOR]' % (self.highlight_color, tvshowtitle, int(season), int(episode))
			homeWindow.clearProperty(self.labelProperty)
			homeWindow.setProperty(self.labelProperty, p_label)
			self.prepareSources()
			sourceDict = self.sourceDict
			sourceDict = [(i[0], i[1], i[1].hasEpisodes) for i in sourceDict]
			sourceDict = [(i[0], i[1]) for i in sourceDict if i[2]]
			aliases = []
			try:
				meta = self.meta
				aliases = meta.get('aliases', [])
			except: pass
			threads = []
			scraperDict = [(i[0], i[1], '') for i in sourceDict]
			if self.season_isAiring == 'false':
				scraperDict.extend([(i[0], i[1], 'season') for i in sourceDict if i[1].pack_capable])
				scraperDict.extend([(i[0], i[1], 'show') for i in sourceDict if i[1].pack_capable])
			trakt_aliases = self.getAliasTitles(imdb, 'episode')
			try: aliases.extend([i for i in trakt_aliases if not i in aliases]) # combine TMDb and Trakt aliases
			except: pass
			try: country_codes = meta.get('country_codes', [])
			except: country_codes = []
			for i in country_codes:
				if i in ('CA', 'US', 'UK', 'GB'):
					if i == 'GB': i = 'UK'
					alias = {'title': tvshowtitle + ' ' + i, 'country': i.lower()}
					if not alias in aliases: aliases.append(alias)
			data = {'title': title, 'year': year, 'imdb': imdb, 'tvdb': tvdb, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'aliases': aliases, 'premiered': premiered, 'total_seasons': self.total_seasons}
			for i in scraperDict:
				name, pack = i[0].upper(), i[2]
				if pack == 'season': name = '%s (season pack)' % name
				elif pack == 'show': name = '%s (show pack)' % name
				threads.append(Thread(target=self.getEpisodeSource, args=(imdb, season, episode, data, i[0], i[1], pack), name=name))
			[i.start() for i in threads]
			end_time = time() + timeout
		except: return log_utils.error()
		while True:
			try:
				if control.monitor.abortRequested(): return sysexit()
				try:
					info = [x.getName() for x in threads if x.is_alive() is True]
					if len(info) == 0: break
					if end_time < time(): break
				except:
					log_utils.error()
					break
				control.sleep(100)
			except: log_utils.error()
		del threads[:] # Make sure any remaining providers are stopped.
		self.sources.extend(self.scraper_sources)
		self.tvshowtitle = tvshowtitle
		self.year = year
		homeWindow.clearProperty('fs_filterless_search')
		if len(self.sources) > 0: self.sourcesFilter()
		return self.sources

	def getSources_dialog(self, title, year, imdb, tvdb, season, episode, tvshowtitle, premiered, timeout=90):
		try:
			content = 'movie' if tvshowtitle is None else 'episode'
			if self.filterless_scrape: homeWindow.setProperty('fs_filterless_search', 'true')
			if self.custom_query == 'true':
				try:
					custom_title = control.dialog.input('[COLOR %s][B]%s[/B][/COLOR]' % (self.highlight_color, getLS(32038)), defaultt=tvshowtitle if tvshowtitle else title)
					if content == 'movie':
						if custom_title: title = custom_title ; self.meta.update({'title': title})
						custom_year = control.dialog.input('[COLOR %s]%s (%s)[/COLOR]' % (self.highlight_color, getLS(32457), getLS(32488)), type=control.numeric_input, defaultt=str(year))
						if custom_year: year = str(custom_year) ; self.meta.update({'year': year})
					else:
						if custom_title: tvshowtitle = custom_title ; self.meta.update({'tvshowtitle': tvshowtitle})
						custom_season = control.dialog.input('[COLOR %s]%s (%s)[/COLOR]' % (self.highlight_color, getLS(32055), getLS(32488)), type=control.numeric_input, defaultt=str(season))
						if custom_season: season = str(custom_season) ; self.meta.update({'season': season})
						custom_episode = control.dialog.input('[COLOR %s]%s (%s)[/COLOR]' % (self.highlight_color, getLS(32325), getLS(32488)), type=control.numeric_input, defaultt=str(episode))
						if custom_episode: episode = str(custom_episode) ; self.meta.update({'episode': episode})
					p_label = '[COLOR %s]%s (%s)[/COLOR]' % (self.highlight_color, title, year) if tvshowtitle is None else '[COLOR %s]%s (S%02dE%02d)[/COLOR]' % (self.highlight_color, tvshowtitle, int(season), int(episode))
					homeWindow.clearProperty(self.labelProperty)
					homeWindow.setProperty(self.labelProperty, p_label)
					homeWindow.clearProperty(self.metaProperty)
					homeWindow.setProperty(self.metaProperty, jsdumps(self.meta))
					homeWindow.clearProperty(self.seasonProperty)
					homeWindow.setProperty(self.seasonProperty, season)
					homeWindow.clearProperty(self.episodeProperty)
					homeWindow.setProperty(self.episodeProperty, episode)
					homeWindow.clearProperty(self.titleProperty)
					homeWindow.setProperty(self.titleProperty, title)
					log_utils.log('Custom query scrape ran using: %s' % p_label, level=log_utils.LOGDEBUG)
				except: log_utils.error()
			header = homeWindow.getProperty(self.labelProperty) + ': Scraping...'
			try:
				if getSetting('progress.dialog') == '0':
					self.progressDialog = self.getSourceProgress(header, self.meta)
				else: raise Exception()
			except:
				homeWindow.clearProperty('luc_kodi.source_progress_is_alive')
				self.progressDialog = control.progressDialogBG
				self.progressDialog.create(header, '')
			self.prepareSources()
			sourceDict = self.sourceDict
			self.progressDialog.update(0, getLS(32600)) # preparing sources
			if content == 'movie': sourceDict = [(i[0], i[1]) for i in sourceDict if i[1].hasMovies]
			else: sourceDict = [(i[0], i[1]) for i in sourceDict if i[1].hasEpisodes]
			if getSetting('cf.disable') == 'true': sourceDict = [(i[0], i[1]) for i in sourceDict if not any(x in i[0] for x in self.sourcecfDict)]
			if getSetting('scrapers.prioritize') == 'true':
				sourceDict = [(i[0], i[1], i[1].priority) for i in sourceDict]
				sourceDict = sorted(sourceDict, key=lambda i: i[2]) # sorted by scraper priority
			try: aliases = self.meta.get('aliases', [])
			except: aliases = []
			threads = [] ; threads_append = threads.append

			if content == 'movie':
				trakt_aliases = self.getAliasTitles(imdb, content) # cached for 7 days in trakt module called
				try: aliases.extend([i for i in trakt_aliases if not i in aliases]) # combine TMDb and Trakt aliases
				except: pass
				data = {'title': title, 'aliases': aliases, 'year': year, 'imdb': imdb}
				for i in sourceDict:
					i = Thread(target=self.getMovieSource, args=(imdb, data, i[0], i[1]), name=i[0].upper())
					threads_append(i)
					i.start()
			else:
				scraperDict = [(i[0], i[1], '') for i in sourceDict] if ((not self.dev_mode) or (not self.dev_disable_single)) else []
				if self.season_isAiring == 'false':
					if (not self.dev_mode) or (not self.dev_disable_season_packs): scraperDict.extend([(i[0], i[1], 'season') for i in sourceDict if i[1].pack_capable])
					if (not self.dev_mode) or (not self.dev_disable_show_packs): scraperDict.extend([(i[0], i[1], 'show') for i in sourceDict if i[1].pack_capable])
				trakt_aliases = self.getAliasTitles(imdb, content) # cached for 7 days in trakt module called
				try: aliases.extend([i for i in trakt_aliases if not i in aliases]) # combine TMDb and Trakt aliases
				except: pass
				try: country_codes = self.meta.get('country_codes', [])
				except: country_codes = []
				for i in country_codes:
					if i in ('CA', 'US', 'UK', 'GB'):
						if i == 'GB': i = 'UK'
						alias = {'title': tvshowtitle + ' ' + i, 'country': i.lower()}
						if not alias in aliases: aliases.append(alias)
				aliases = aliases_check(tvshowtitle, aliases)
				data = {'title': title, 'year': year, 'imdb': imdb, 'tvdb': tvdb, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'aliases': aliases, 'premiered': premiered, 'total_seasons': self.total_seasons}
				for i in scraperDict:
					name, pack = i[0].upper(), i[2]
					if pack == 'season': name = '%s (season pack)' % name
					elif pack == 'show': name = '%s (show pack)' % name
					i = Thread(target=self.getEpisodeSource, args=(imdb, season, episode, data, i[0], i[1], pack), name=name)
					threads_append(i)
					i.start()
#			[i.start() for i in threads]
			sdc = control.getSourceHighlightColor()
			string1 = f"[B]{getLS(32404) % (self.highlight_color, sdc, '%s')}[/B]" # msgid "[COLOR %s]Time elapsed:[/COLOR]  [COLOR %s]%s seconds[/COLOR]"
			string3 = f"[B]{getLS(32406) % (self.highlight_color, sdc, '%s')}[/B]" # msgid "[COLOR %s]Remaining providers:[/COLOR] [COLOR %s]%s[/COLOR]"

			try: timeout = int(getSetting('scrapers.timeout'))
			except: pass
			if self.all_providers == 'true': timeout = 90
			self.start_time = time()
			end_time = self.start_time + timeout
			quality = getSetting('hosts.quality') or '0'
			line1 = line2 = line3 = ""
			terminate_onCloud = getSetting('terminate.onCloud.sources') == 'true'
			pre_emp = getSetting('preemptive.termination') == 'true'
			pre_emp_limit = int(getSetting('preemptive.limit'))
			pre_emp_res = getSetting('preemptive.res') or '0'
			source_4k = source_1080 = source_720 = source_sd = total = 0
			total_format = '[COLOR %s][B]%s[/B][/COLOR]'
			pdiag_format = '[COLOR %s]4K:[/COLOR]  %s  |  [COLOR %s]1080p:[/COLOR]  %s  |  [COLOR %s]720p:[/COLOR]  %s  |  [COLOR %s]SD:[/COLOR]  %s  |  [COLOR %s]TOTAL:[/COLOR]  %s' % (
				self.highlight_color, '%s', self.highlight_color, '%s', self.highlight_color, '%s', self.highlight_color, '%s', self.highlight_color, '%s' )
			control.hide()
		except:
			log_utils.error()
			try: self.progressDialog.close()
			except: pass
			del self.progressDialog
			return

		while True:
			try:
				if control.monitor.abortRequested(): return sysexit()
				try:
					if self.progressDialog.iscanceled(): break
				except: pass

				if terminate_onCloud:
					if len([e for e in self.scraper_sources if e['source'] == 'cloud']) > 0: break
				if pre_emp:
					if pre_emp_res == '0' and source_4k >= pre_emp_limit: break
					elif pre_emp_res == '1' and source_1080 >= pre_emp_limit: break
					elif pre_emp_res == '2' and source_720 >= pre_emp_limit: break
					elif pre_emp_res == '3' and source_sd >= pre_emp_limit: break
				if quality == '0':
					source_4k = len([e for e in self.scraper_sources if e['quality'] == '4K'])
					source_1080 = len([e for e in self.scraper_sources if e['quality'] == '1080p'])
					source_720 = len([e for e in self.scraper_sources if e['quality'] == '720p'])
					source_sd = len([e for e in self.scraper_sources if e['quality'] in ('SD', 'SCR', 'CAM')])
				elif quality == '1':
					source_1080 = len([e for e in self.scraper_sources if e['quality'] == '1080p'])
					source_720 = len([e for e in self.scraper_sources if e['quality'] == '720p'])
					source_sd = len([e for e in self.scraper_sources if e['quality'] in ('SD', 'SCR', 'CAM')])
				elif quality == '2':
					source_720 = len([e for e in self.scraper_sources if e['quality'] == '720p'])
					source_sd = len([e for e in self.scraper_sources if e['quality'] in ('SD', 'SCR', 'CAM')])
				else:
					source_sd = len([e for e in self.scraper_sources if e['quality'] in ('SD', 'SCR', 'CAM')])
				total = source_4k + source_1080 + source_720 + source_sd

				source_4k_label = total_format % ('red', source_4k) if source_4k == 0 else total_format % (sdc, source_4k)
				source_1080_label = total_format % ('red', source_1080) if source_1080 == 0 else total_format % (sdc, source_1080)
				source_720_label = total_format % ('red', source_720) if source_720 == 0 else total_format % (sdc, source_720)
				source_sd_label = total_format % ('red', source_sd) if source_sd == 0 else total_format % (sdc, source_sd)
				source_total_label = total_format % ('red', total) if total == 0 else total_format % (sdc, total)
				try:
					info = [x.getName() for x in threads if x.is_alive() is True]
					line1 = pdiag_format % (source_4k_label, source_1080_label, source_720_label, source_sd_label, source_total_label)
					line2 = string1 % round(time() - self.start_time, 1)
					all_done = len(info) == 0
					if len(info) > 6: line3 = string3 % str(len(info))
					elif len(info) > 0: line3 = string3 % (', '.join(info))
					else: line3 = ''
					current_time = time()
					percent = 100 if all_done else int((len(threads) - len(info)) * 100 / max(1, len(threads)))
					if self.progressDialog != control.progressDialogBG:
						update_line = line1 + '[CR]' + line2 + ('[CR]' + line3 if line3 else '')
						self.progressDialog.update(max(1, percent), update_line)
						try:
							self.progressDialog.setProperty('luc_kodi.src.4k',    str(source_4k))
							self.progressDialog.setProperty('luc_kodi.src.1080',  str(source_1080))
							self.progressDialog.setProperty('luc_kodi.src.720',   str(source_720))
							self.progressDialog.setProperty('luc_kodi.src.sd',    str(source_sd))
							self.progressDialog.setProperty('luc_kodi.src.total', str(total))
							self.progressDialog.setProperty('luc_kodi.src.elapsed', str(round(time() - self.start_time, 1)))
							providers_str = ', '.join(info) if len(info) <= 6 else str(len(info)) + ' providers'
							self.progressDialog.setProperty('luc_kodi.src.providers', providers_str)
							self.progressDialog.setProperty('luc_kodi.src.providers_count', str(len(info)))
						except: pass
					else: self.progressDialog.update(max(1, percent), line3)
					if all_done or end_time < current_time: break
				except:
					log_utils.error()
					break
				control.sleep(25)
			except: log_utils.error()
		del threads[:] # Make sure any remaining providers are stopped, only deletes threads not started yet.
		self.sources.extend(self.scraper_sources)
		self.tvshowtitle = tvshowtitle
		self.year = year
		homeWindow.clearProperty('fs_filterless_search')
		if len(self.sources) > 0: self.sourcesFilter()
		if homeWindow.getProperty('luc_kodi.source_progress_is_alive') != 'true':
			try: self.progressDialog.close()
			except: pass
			self.progressDialog = None
		return self.sources

	def preResolve(self, next_sources, next_meta):
		try:
			if not next_sources: raise Exception()
			homeWindow.setProperty(self.metaProperty, jsdumps(next_meta))
			if getSetting('autoplay.sd') == 'true': next_sources = [i for i in next_sources if not i['quality'] in ('4K', '1080p', '720p')]
			uncached_filter = [i for i in next_sources if re.match(r'^uncached.*torrent', i['source'])]
			next_sources = [i for i in next_sources if i not in uncached_filter]
		except:
			log_utils.error()
			return playerWindow.clearProperty('luc_kodi.preResolved_nextUrl')

		for i in range(len(next_sources)):
			try:
				control.sleep(1000)
				try:
					if control.monitor.abortRequested(): return sysexit()
					url = self.sourcesResolve(next_sources[i])
					if not url:
						log_utils.log('preResolve failed for : next_sources[i]=%s' % str(next_sources[i]), level=log_utils.LOGWARNING)
						continue
					if not any(x in url.lower() for x in video_extensions) and not '/dld/' in url:
						log_utils.log('preResolve Playback not supported for (sourcesAutoPlay()): %s' % url, level=log_utils.LOGWARNING)
						continue
					if url:
						control.sleep(500)
						player_hasVideo = control.condVisibility('Player.HasVideo')
						if player_hasVideo: # do not setPropery if user stops playback quickly because "onPlayBackStopped" is already called and won't be able to clear it.
							playerWindow.setProperty('luc_kodi.preResolved_nextUrl', url)
							log_utils.log('preResolved_nextUrl : %s' % url, level=log_utils.LOGDEBUG)
						else:
							log_utils.log('player_hasVideo = %s : skipping setting preResolved_nextUrl' % player_hasVideo, level=log_utils.LOGWARNING)
						break
				except: pass
			except: log_utils.error()
		control.sleep(200)

	def prepareSources(self):
		try:
			control.makeFile(control.dataPath)
			dbcon = database.connect(sourceFile)
			dbcur = dbcon.cursor()
			dbcur.execute('''CREATE TABLE IF NOT EXISTS rel_src (source TEXT, imdb_id TEXT, season TEXT, episode TEXT, hosts TEXT, added TEXT, UNIQUE(source, imdb_id, season, episode));''')
			dbcur.execute('''CREATE TABLE IF NOT EXISTS rel_aliases (title TEXT, aliases TEXT, UNIQUE(title));''')
			dbcur.connection.commit()
		except: log_utils.error()
		finally:
			try:
				dbcur.close()
			except Exception:
				pass
			try:
				dbcon.close()
			except Exception:
				pass
	def getMovieSource(self, imdb, data, source, call):
		try:
			dbcon = database.connect(sourceFile, timeout=60)
			dbcon.execute('''PRAGMA journal_mode = WAL''')
			dbcon.execute('''PRAGMA synchronous = OFF''')
			dbcon.execute('''PRAGMA temp_store = memory''')
			dbcon.execute('''PRAGMA mmap_size = 268435456''')
			dbcur = dbcon.cursor()
		except: pass
		if not imdb: # Fix to stop items passed with null IMDB_id pulling old unrelated sources from the database
			try:
				dbcur.execute('''DELETE FROM rel_src WHERE (source=? AND imdb_id='' AND season='' AND episode='')''', (source,))
				dbcur.connection.commit()
			except: log_utils.error()
		try:
			sources = []
			db_movie = dbcur.execute('''SELECT * FROM rel_src WHERE (source=? AND imdb_id=? AND season='' AND episode='')''', (source, imdb)).fetchone()
			if db_movie:
				timestamp = cleandate.datetime_from_string(str(db_movie[5]), '%Y-%m-%d %H:%M:%S.%f', False)
				db_movie_valid = abs(self.time - timestamp) < single_expiry
				if db_movie_valid:
					sources = literal_eval(db_movie[4])
					return self.scraper_sources.extend(sources)
		except: log_utils.error()
		try:
			sources = []
			sources = call().sources(data, self.hostprDict)
			if sources:
				self.scraper_sources.extend(sources)
				dbcur.execute('''INSERT OR REPLACE INTO rel_aliases Values (?, ?)''', (data.get('title', ''), repr(data.get('aliases', ''))))
				dbcur.execute('''INSERT OR REPLACE INTO rel_src Values (?, ?, ?, ?, ?, ?)''', (source, imdb, '', '', repr(sources), datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")))
				dbcur.connection.commit()
		except: log_utils.error()

	def getEpisodeSource(self, imdb, season, episode, data, source, call, pack):
		try:
			dbcon = database.connect(sourceFile, timeout=60)
			dbcon.execute('''PRAGMA journal_mode = WAL''')
			dbcon.execute('''PRAGMA synchronous = OFF''')
			dbcon.execute('''PRAGMA temp_store = memory''')
			dbcon.execute('''PRAGMA mmap_size = 268435456''')
			dbcur = dbcon.cursor()
		except: pass
		if not imdb: # Fix to stop items passed with null IMDB_id pulling old unrelated sources from the database
			try:
				dbcur.execute('''DELETE FROM rel_src WHERE (source=? AND imdb_id='' AND season=? AND episode=?)''', (source, season, episode))
				dbcur.execute('''DELETE FROM rel_src WHERE (source=? AND imdb_id='' AND season=? AND episode='')''', (source, season))
				dbcur.execute('''DELETE FROM rel_src WHERE (source=? AND imdb_id='' AND season='' AND episode='')''', (source, ))
				dbcur.connection.commit()
			except: log_utils.error()
		if not pack: # singleEpisodes db check
			try:
				db_singleEpisodes = dbcur.execute('''SELECT * FROM rel_src WHERE (source=? AND imdb_id=? AND season=? AND episode=?)''', (source, imdb, season, episode)).fetchone()
				if db_singleEpisodes:
					timestamp = cleandate.datetime_from_string(str(db_singleEpisodes[5]), '%Y-%m-%d %H:%M:%S.%f', False)
					db_singleEpisodes_valid = abs(self.time - timestamp) < single_expiry
					if db_singleEpisodes_valid:
						sources = literal_eval(db_singleEpisodes[4])
						return self.scraper_sources.extend(sources)
			except: log_utils.error()
		elif pack == 'season': # seasonPacks db check
			try:
				db_seasonPacks = dbcur.execute('''SELECT * FROM rel_src WHERE (source=? AND imdb_id=? AND season=? AND episode='')''', (source, imdb, season)).fetchone()
				if db_seasonPacks:
					timestamp = cleandate.datetime_from_string(str(db_seasonPacks[5]), '%Y-%m-%d %H:%M:%S.%f', False)
					db_seasonPacks_valid = abs(self.time - timestamp) < season_expiry
					if db_seasonPacks_valid:
						sources = literal_eval(db_seasonPacks[4])
						sources = [i for i in sources if not 'episode_start' in i or i['episode_start'] <= int(episode) <= i['episode_end']] # filter out range items that do not apply to current episode for return
						return self.scraper_sources.extend(sources)
			except: log_utils.error()
		elif pack == 'show': # showPacks db check
			try:
				db_showPacks = dbcur.execute('''SELECT * FROM rel_src WHERE (source=? AND imdb_id=? AND season='' AND episode='')''', (source, imdb)).fetchone()
				if db_showPacks:
					timestamp = cleandate.datetime_from_string(str(db_showPacks[5]), '%Y-%m-%d %H:%M:%S.%f', False)
					db_showPacks_valid = abs(self.time - timestamp) < show_expiry
					if db_showPacks_valid:
						sources = literal_eval(db_showPacks[4])
						sources = [i for i in sources if i.get('last_season') >= int(season)] # filter out range items that do not apply to current season for return
						return self.scraper_sources.extend(sources)
			except: log_utils.error()

		try: #dummy write or threads wait till return from scrapers...write for each is needed
			dbcur.execute('''INSERT OR REPLACE INTO rel_src Values (?, ?, ?, ?, ?, ?)''', ('dummy write', '', '', '', '', ''))
			dbcur.connection.commit()
		except: log_utils.error()

		if not pack: # singleEpisodes scraper call
			try:
				sources = []
				sources = call().sources(data, self.hostprDict)
				if sources:
					dbcur.execute('''INSERT OR REPLACE INTO rel_src Values (?, ?, ?, ?, ?, ?)''', (source, imdb, season, episode, repr(sources), datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")))
					dbcur.connection.commit()
					return self.scraper_sources.extend(sources)
				return
			except: return log_utils.error()
		elif pack == 'season': # seasonPacks scraper call
			try:
				sources = []
				sources = call().sources_packs(data, self.hostprDict, bypass_filter=self.dev_disable_season_filter)
				if sources:
					dbcur.execute('''INSERT OR REPLACE INTO rel_src Values (?, ?, ?, ?, ?, ?)''', (source, imdb, season,'', repr(sources), datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")))
					dbcur.connection.commit()
					sources = [i for i in sources if not 'episode_start' in i or i['episode_start'] <= int(episode) <= i['episode_end']] # filter out range items that do not apply to current episode for return
					return self.scraper_sources.extend(sources)
				return
			except: return log_utils.error()
		elif pack == 'show': # showPacks scraper call
			try:
				sources = []
				sources = call().sources_packs(data, self.hostprDict, search_series=True, total_seasons=self.total_seasons, bypass_filter=self.dev_disable_show_filter)
				if sources:
					dbcur.execute('''INSERT OR REPLACE INTO rel_src Values (?, ?, ?, ?, ?, ?)''', (source, imdb, '', '', repr(sources), datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")))
					dbcur.connection.commit()
					sources = [i for i in sources if i.get('last_season') >= int(season)] # filter out range items that do not apply to current season for return
					return self.scraper_sources.extend(sources)
			except: log_utils.error()

	def sourcesFilter(self):
		if not self.isPrescrape: control.busy()
		if getSetting('remove.duplicates') == 'true': self.sources = self.filter_dupes()
		if self.mediatype == 'movie':
			if getSetting('source.enable.msizelimit') == 'true':
				try:
					movie_minSize, movie_maxSize = float(getSetting('source.min.moviesize')), float(getSetting('source.max.moviesize'))
					self.sources = [i for i in self.sources if (i.get('size', 0) >= movie_minSize and i.get('size', 0) <= movie_maxSize)]
				except: log_utils.error()
		else:
			self.sources = [i for i in self.sources if 'movie.collection' not in i.get('name_info', '')] # rare but a few retuned from "complete" show pack scrape returned as "movie.collection"
			if getSetting('source.checkReboots') == 'true':
				try:
					from resources.lib.modules.source_utils import tvshow_reboots
					reboots = tvshow_reboots()
					if self.tvshowtitle in reboots and self.year in reboots.get(self.tvshowtitle, []):
						log_utils.log('tvshowtitle(%s) is a REBOOT, filtering for year match per enabled setting' % self.tvshowtitle, level= log_utils.LOGDEBUG)
						self.sources = [i for i in self.sources if self.year in i.get('name')]
				except: log_utils.error()
			if getSetting('source.enable.esizelimit') == 'true':
				try:
					episode_minSize, episode_maxSize = float(getSetting('source.min.epsize')), float(getSetting('source.max.epsize'))
					self.sources = [i for i in self.sources if (i.get('size', 0) >= episode_minSize and i.get('size', 0) <= episode_maxSize)]
				except: log_utils.error()
			try: self.sources = self.calc_pack_size()
			except: pass
		for i in self.sources:
			try:
				if 'name_info' in i: info_string = getFileType(name_info=i.get('name_info'))
				else: info_string = getFileType(url=i.get('url'))
				i.update({'info': (i.get('info') + ' /' + info_string).lstrip(' ').lstrip('/').rstrip('/')})
			except: log_utils.error()
		if getSetting('remove.hevc') == 'true':
			self.sources = [i for i in self.sources if 'HEVC' not in i.get('info', '')]
		if getSetting('remove.hdr') == 'true':
			self.sources = [i for i in self.sources if ' HDR ' not in i.get('info', '')] # needs space before and aft because of "HDRIP"
		if getSetting('remove.dolby.vision') == 'true':
			self.sources = [i for i in self.sources if ('DOLBY-VISION' not in i.get('info', '')) or ('DOLBY-VISION' in i.get('info', '') and ' HDR ' in i.get('info', ''))]
		if getSetting('remove.cam.sources') == 'true':
			self.sources = [i for i in self.sources if i['quality'] != 'CAM']
		if getSetting('remove.sd.sources') == 'true':
			if any(i for i in self.sources if any(value in i['quality'] for value in ('4K', '1080p', '720p'))): #only remove SD if better quality does exist
				self.sources = [i for i in self.sources if i['quality'] != 'SD']
		if getSetting('remove.3D.sources') == 'true':
			self.sources = [i for i in self.sources if '3D' not in i.get('info', '')]

		local = [i for i in self.sources if 'local' in i and i['local'] is True] # for library and videoscraper (skips cache check)
		self.sources = [i for i in self.sources if not i in local]
		direct = [i for i in self.sources if i['direct'] == True] # acct scrapers (skips cache check)
		self.sources = [i for i in self.sources if not i in direct]
		# ── RD 2026 keyword-filter compliance for direct items ────────────
		# AIOStreams / MediaFusion resolved-via-RD items (debrid label starts
		# with 'RD') will also 451 on playback if filename matches. Strip
		# them here so they never appear in the picker.
		try:
			from resources.lib.modules import rd_filter as _rd_filter
			_before = len(direct)
			direct, _removed = _rd_filter.apply_to_direct_list(direct)
			if _removed:
				log_utils.log(
					'sources: RD2026 filter v%s removed %d of %d direct items '
					'(AIOStreams/MediaFusion via RD)' % (_rd_filter.RD_FILTER_VERSION, _removed, _before),
					level=log_utils.LOGDEBUG)
		except Exception:
			log_utils.error()
		# ── end RD 2026 filter ────────────────────────────────────────────
		from copy import deepcopy
		deepcopy_sources = deepcopy(self.sources)
		deepcopy_sources = [i for i in deepcopy_sources if 'magnet:' in i['url']]
		if deepcopy_sources: hashList = [i['hash'] for i in deepcopy_sources]
		threads = [] ; self.filter = []
		valid_hosters = set([i['source'] for i in self.sources if 'magnet:' not in i['url']])

		def checkStatus(function, debrid_name, valid_hoster):
			try:
				cached = None
				if deepcopy_sources: cached = function(deepcopy_sources, hashList)
				if cached: self.filter += [dict(list(i.items()) + [('debrid', debrid_name)]) for i in cached] # this makes a new instance so no need for deepcopy beyond the one time done now
				if valid_hoster: self.filter += [dict(list(i.items()) + [('debrid', debrid_name)]) for i in self.sources if i['source'] in valid_hoster and 'magnet:' not in i['url']]
			except: log_utils.error()
		for d in self.debrid_resolvers:
			if d.name == 'Real-Debrid' and getSetting('realdebrid.enable') == 'true':
				try:
					valid_hoster = [i for i in valid_hosters if d.valid_url(i)]
					i = Thread(name=d.name.upper(), target=checkStatus, args=(self.rd_cache_chk_list, d.name, valid_hoster))
					threads.append(i)
					i.start()
				except: log_utils.error()
			if d.name == 'Premiumize.me' and getSetting('premiumize.enable') == 'true':
				try:
					valid_hoster = [i for i in valid_hosters if d.valid_url(i)]
					i = Thread(name=d.name.upper(), target=checkStatus, args=(self.pm_cache_chk_list, d.name, valid_hoster))
					threads.append(i)
					i.start()
				except: log_utils.error()
			if d.name == 'AllDebrid' and getSetting('alldebrid.enable') == 'true':
				try:
					valid_hoster = [i for i in valid_hosters if d.valid_url(i)]
					i = Thread(name=d.name.upper(), target=checkStatus, args=(self.ad_cache_chk_list, d.name, valid_hoster))
					threads.append(i)
					i.start()
				except: log_utils.error()
			if d.name == 'Offcloud' and getSetting('offcloud.enable') == 'true':
				try:
					valid_hoster = []
					i = Thread(name=d.name.upper(), target=checkStatus, args=(self.oc_cache_chk_list, d.name, valid_hoster))
					threads.append(i)
					i.start()
				except: log_utils.error()
			if d.name == 'EasyDebrid' and getSetting('easydebrid.enable') == 'true':
				try:
					valid_hoster = []
					i = Thread(name=d.name.upper(), target=checkStatus, args=(self.ed_cache_chk_list, d.name, valid_hoster))
					threads.append(i)
					i.start()
				except: log_utils.error()
			if d.name == 'TorBox' and getSetting('torbox.enable') == 'true':
				try:
					valid_hoster = []
					i = Thread(name=d.name.upper(), target=checkStatus, args=(self.tb_cache_chk_list, d.name, valid_hoster))
					threads.append(i)
					i.start()
				except: log_utils.error()
		if threads:
#			[i.start() for i in threads]
			if self.progressDialog:
				control.hide()
				sdc = control.getSourceHighlightColor()
				string2 = '[B][COLOR %s]Time elapsed[/COLOR]:  [COLOR %s]%s seconds[/COLOR][/B]' % (self.highlight_color, sdc, '%s')
				string3 = '[B][COLOR %s]Remaining debrid[/COLOR]: [COLOR %s]%s[/COLOR][/B]' % (self.highlight_color, sdc, '%s')

				while True:
					try:
						if control.monitor.abortRequested(): return sysexit()
						try:
							if self.progressDialog.iscanceled(): break
						except: pass

						try:
							info = [i.getName() for i in threads if i.is_alive()]
							line1 = '[B][COLOR %s]Checking Debrid...[/COLOR][/B]' % self.highlight_color
							line2 = string2 % round(time() - self.start_time, 1)
							line3 = string3 % (', '.join(info))
							if not info: break
							if self.progressDialog != control.progressDialogBG: self.progressDialog.update(100, f"{line1}[CR]{line2}[CR]{line3}")
							else: self.progressDialog.update(100, line1 + '  ' + line3)
						except:
							log_utils.error()
							break
						control.sleep(25)
					except: log_utils.error()
			[i.join() for i in threads]

		# ── TorBox 2026: usenet integration ───────────────────────────────
		# Usenet items (source == 'usenet') bypass the magnet-only pipeline
		# above. When TorBox is enabled, route them into self.filter so they
		# appear in the picker as proper "cached usenet" results.
		#
		# v1.0.12 strategy (mirrors POV / Umbrella):
		# - Trust the per-item 'cached_remote' field set by the torboxnews
		#   scraper, which comes directly from TorBox's search-api response
		#   (`item['cached']`). One call already; no extra round-trip.
		# - Items WITHOUT cached_remote (other scrapers, legacy paths) fall
		#   back to POST /usenet/checkcached for verification.
		try:
			if getSetting('torbox.enable') == 'true' and getSetting('torbox.token'):
				_usenet_items = [i for i in self.sources if i.get('source') == 'usenet' and i.get('hash')]
				if _usenet_items:
					_cached_only = getSetting('torbox.add_only_if_cached') in ('', 'true')
					_pre_cached_set = set()
					_unknown_items = []
					for _it in _usenet_items:
						if 'cached_remote' in _it:
							if _it['cached_remote']:
								_pre_cached_set.add((_it.get('hash') or '').lower())
						else:
							_unknown_items.append(_it)
					# Network fallback only for items whose cached state we don't yet know
					if _unknown_items:
						from resources.lib.debrid.torbox import TorBox as _TB
						_hashes = [i['hash'] for i in _unknown_items]
						_pre_cached_set |= (_TB().check_cache_usenet(_hashes) or set())
					_added = _dropped = 0
					for _it in _usenet_items:
						_h = (_it.get('hash') or '').lower()
						_is_cached = _h in _pre_cached_set
						if _cached_only and not _is_cached:
							_dropped += 1
							continue
						_new = dict(_it)
						_new['source'] = 'cached usenet' if _is_cached else 'uncached usenet'
						_new['debrid'] = 'TorBox'
						self.filter.append(_new)
						_added += 1
					log_utils.log(
						'TorBox 2026: usenet -- %d items (%d cached, %d trusted from API, %d probed); %d uncached dropped (cached_only=%s)'
						% (_added, len(_pre_cached_set), len(_usenet_items) - len(_unknown_items), len(_unknown_items), _dropped, _cached_only),
						level=log_utils.LOGDEBUG)
		except Exception:
			log_utils.error()
		# ── end TorBox 2026 usenet integration ────────────────────────────

		self.filter += direct # add direct links in to be considered in priority sorting
		try:
			if len(self.prem_providers) > 1: # resort for debrid/direct priorty, when more than 1 account, because of order cache check threads finish
				self.prem_providers.sort(key=lambda k: k[1])
				self.prem_providers = [i[0] for i in self.prem_providers]
				log_utils.log('self.prem_providers sort order=%s' % self.prem_providers, level=log_utils.LOGDEBUG)
				self.filter.sort(key=lambda k: self.prem_providers.index(k['debrid'] if k.get('debrid', '') else k['provider']))
		except: log_utils.error()

		self.filter += local # library and video scraper sources
		self.sources = self.filter

		if getSetting('sources.group.sort') == '1':
			torr_filter = []
			torr_filter += [i for i in self.sources if 'torrent' in i['source'] or 'usenet' in i['source']]  #torrents and usenet first
			if getSetting('sources.size.sort') == 'true': torr_filter.sort(key=lambda k: round(k.get('size', 0)), reverse=True)
			aact_filter = []
			aact_filter += [i for i in self.sources if i['direct'] == True]  #account scrapers and local/library next
			if getSetting('sources.size.sort') == 'true': aact_filter.sort(key=lambda k: round(k.get('size', 0)), reverse=True)
			prem_filter = []
			prem_filter += [i for i in self.sources if 'torrent' not in i['source'] and 'usenet' not in i['source'] and i['debridonly'] is True]  #prem.hosters last
			if getSetting('sources.size.sort') == 'true': prem_filter.sort(key=lambda k: round(k.get('size', 0)), reverse=True)
			self.sources = torr_filter
			self.sources += aact_filter
			self.sources += prem_filter
		elif getSetting('sources.size.sort') == 'true':
			reverse_sort = True if getSetting('sources.sizeSort.reverse') == 'false' else False
			self.sources.sort(key=lambda k: round(k.get('size', 0), 2), reverse=reverse_sort)

		if getSetting('sources.provider.mix') == 'true':
			try: max_per = int(getSetting('sources.provider.mix.max'))
			except: max_per = 12
			try: top_n = int(getSetting('sources.provider.mix.top'))
			except: top_n = 120
			self.sources = self.mix_by_provider(self.sources, top_n=top_n, max_per_provider=max_per)

		if getSetting('source.prioritize.hevc') == 'true': # filter to place HEVC sources first
			filter = []
			filter += [i for i in self.sources if 'HEVC' in i.get('info', '')]
			filter += [i for i in self.sources if i not in filter]
			self.sources = filter

		if getSetting('source.prioritize.hdrdv') == 'true': # filter to place HDR and DOLBY-VISION sources first
			filter = []
			filter += [i for i in self.sources if any(value in i.get('info', '') for value in (' HDR ', 'DOLBY-VISION'))]
			filter += [i for i in self.sources if i not in filter]
			self.sources = filter

		self.sources = self.sort_byQuality(source_list=self.sources)

		filter = [] # filter to place cloud files first
		filter += [i for i in self.sources if i['source'] == 'cloud']
		filter += [i for i in self.sources if i not in filter]
		self.sources = filter

		self.sources = self.sources[:4000]
		control.hide()
		return self.sources

	def filter_dupes(self):
		filter = []
		append = filter.append
		remove = filter.remove
		log_dupes = getSetting('remove.duplicates.logging') == 'false'
		for i in self.sources:
			larger = False
			a = i['url'].lower()
			for sublist in filter:
				try:
					if i['source'] == 'cloud': break
					b = sublist['url'].lower()
					if 'magnet:' in a:
						if i['hash'].lower() in b:
							if sublist['provider'] == 'torrentio' or (len(sublist['name']) > len(i['name']) and i['provider'] != 'torrentio'): # favor "torrentio" or keep matching hash with longer name for possible more info
								larger = True
								break
							remove(sublist)
							if log_dupes: log_utils.log('Removing %s - %s (DUPLICATE TORRENT) ALREADY IN :: %s' % (sublist['provider'], b, i['provider']), level=log_utils.LOGDEBUG)
							break
					elif a == b:
						remove(sublist)
						if log_dupes: log_utils.log('Removing %s - %s (DUPLICATE LINK) ALREADY IN :: %s' % (sublist['source'], i['url'], i['provider']), level=log_utils.LOGDEBUG)
						break
				except: log_utils.error('Error filter_dupes: ')
			if not larger: append(i) # sublist['name'] len() was larger, or "torrentio" so do not append
		item_title = homeWindow.getProperty(self.labelProperty)
#		if self.mediatype == 'movie' or (self.mediatype == 'episode' and not self.enable_playnext):
#			control.notification(title=item_title, message='Removed %s duplicate sources from list' % (len(self.sources) - len(filter)))
		log_utils.log('Removed %s duplicate sources for (%s) from list' % (len(self.sources) - len(filter), item_title), level=log_utils.LOGDEBUG)
		return filter

	def sourcesAutoPlay(self, items):
		# v1.0.17 FIX: TorBox cooldown buffer for auto-play-next-episode.
		# TorBox applies a strict per-account cooldown on /torrents/checkcached and
		# /torrents/createtorrent. When E01 just finished playing and E02 is launched
		# via the next-episode dialog (RunPlugin with next_ep_direct=true), all the
		# TorBox calls from E01's resolve are still within the cooldown window, so
		# E02's resolves would fail and the user saw "no streams". A 2s pre-buffer
		# gives TorBox's rate limiter time to reset.
		try:
			if (homeWindow.getProperty('luc_kodi.next_ep_direct') == 'true'
					and getSetting('torbox.enable') == 'true'
					and getSetting('torbox.token')
					and any((i.get('debrid') == 'TorBox') for i in (items or []))):
				log_utils.log('luc_kodi v1.0.17: TorBox next-ep cooldown buffer (2000ms) before sourcesAutoPlay',
							  level=log_utils.LOGDEBUG)
				control.sleep(2000)
		except Exception:
			pass
		# SMART AUTOPLAY SORTING:
		# A light scoring pass that helps pick the "best" source first.
		# This preserves existing group/quality ordering but nudges higher-quality
		# audio/HDR and better-seeded torrents to the top.
		try:
			items = self._smart_autoplay_sort(items)
		except:
			pass
		if getSetting('autoplay.sd') == 'true': items = [i for i in items if not i['quality'] in ('4K', '1080p', '720p')]
		header = homeWindow.getProperty(self.labelProperty) + ': Resolving...'
		try:
			if getSetting('progress.dialog') == '0':
				self.progressDialog = self.getSourceProgress(header, self.meta)
			else: raise Exception()
		except:
			homeWindow.clearProperty('luc_kodi.source_progress_is_alive')
			self.progressDialog = control.progressDialogBG
			self.progressDialog.create(header, '')
		for i in range(len(items)):
			try:
				src_provider = items[i]['debrid'] if items[i].get('debrid') else ('%s - %s' % (items[i]['source'], items[i]['provider']))
				label = '[B][COLOR %s]%s[CR]%s[CR]%s[/COLOR][/B]' % (self.highlight_color, src_provider.upper(), items[i]['info'][:40], items[i]['name'][:40]) # using "[CR]" has some weird delay with progressDialog.update() at times
				control.sleep(100)
				try:
					if self.progressDialog == control.progressDialogBG and self.progressDialog.iscanceled(): break
					self.progressDialog.update(int((100 / float(len(items))) * i), label)
				except: self.progressDialog.update(int((100 / float(len(items))) * i), '[COLOR %s]Resolving...[/COLOR]%s' % (self.highlight_color, items[i]['name']))
				try:
					if control.monitor.abortRequested(): return sysexit()
					url = self.sourcesResolve(items[i])
					# v1.0.17 FIX: explicit early-continue when resolve returned None.
					# Previously the code fell through to `url.lower()` which raised
					# AttributeError and was silently swallowed by the outer `except: pass`,
					# hiding TorBox cooldown failures from the log.
					if not url:
						continue
					# Optional URL validity check (skip dead links / HTML error pages)
					try:
						if url and getSetting('validate.source.urls') == 'true':
							from resources.lib.modules import urlcheck
							if not urlcheck.check_url_validity(url):
								log_utils.log('Rejected invalid URL (sourcesAutoPlay): %s' % url, level=log_utils.LOGWARNING)
								continue
					except Exception:
						pass

					item = items[i]
					is_aiostreams_direct = item.get('aiostreams_direct') or (item.get('provider') == 'aiostreams' and item.get('direct') is True)
					if (not any(x in url.lower() for x in video_extensions) and '/dld/' not in url) and not is_aiostreams_direct:
						log_utils.log('Playback not supported for (sourcesAutoPlay()): %s' % url, level=log_utils.LOGWARNING)
						continue
					if url:
						log_utils.log('Playing url from (sourcesAutoPlay()): %s' % url, level=log_utils.LOGDEBUG)
						try:
							_q    = items[i].get('quality') or 'SD'
							_deb  = items[i].get('debrid') or ''
							_prov = items[i].get('provider') or items[i].get('source') or ''
							_src_label = ('%s  ·  %s' % (_deb.upper(), _prov.upper())) if _deb else _prov.upper()
							from resources.lib.windows.display_welcome import DisplayWelcomeXML
							from resources.lib.modules.control import addonPath, addonId, addonIcon
							import threading
							def _show_autoplay_notif():
								try:
									win = DisplayWelcomeXML(
										'autoplay_notif.xml',
										addonPath(addonId()),
										'Default',
										line1='Auto-Play  [COLOR FF00FA9A]%s[/COLOR]' % _q,
										line2=_src_label,
										icon=addonIcon(),
										duration=5
									)
									win.show_and_close(duration=5)
									del win
								except: pass
							threading.Thread(target=_show_autoplay_notif, daemon=True).start()
						except: pass
						# ── Personal ranker: registrar la elegida vs. saltadas ──
						# items[0:i] fueron mostradas/intentadas pero descartadas
						# por algún motivo (no resolvieron, etc.) o estaban por
						# debajo de la elegida en el orden de scoring.
						try:
							from resources.lib.database import source_ranker
							source_ranker.record_choice(items[i], all_items=items[:i+1])
						except Exception:
							pass
						break
				except: pass
			except: log_utils.error()
		if homeWindow.getProperty('luc_kodi.source_progress_is_alive') != 'true':
			try: self.progressDialog.close()
			except: pass
			del self.progressDialog
		return url

	
	def _smart_score(self, it):
		"""Compute smart score for a source item (used by autoplay and source select)."""
		try:
			from resources.lib.modules.control import getSetting
		except:
			def getSetting(_k):
				return ''
		try:
			info = (it.get('info') or '').upper()
		except:
			info = ''
		try:
			name = (it.get('name') or '').upper()
		except:
			name = ''

		def qv(q):
			return {'4K': 40, '1080p': 30, '720p': 20, 'SCR': 10, 'SD': 5, 'CAM': 1}.get(q, 0)

		s = qv(it.get('quality')) * 100

		# Prefer cached torrents over uncached
		url = (it.get('url') or '').upper()
		src = (it.get('source') or '').upper()
		if 'MAGNET:' in url:
			if 'UNCACHED' in src:
				s -= 500
			else:
				s += 200

		# HDR / Dolby Vision
		if 'DOLBY-VISION' in info or ' DOVI' in info:
			s += 60
		if ' HDR ' in info or info.startswith('HDR') or 'HDR10' in info:
			s += 50

		# Audio priorities
		if 'ATMOS' in info:
			s += 40
		if 'TRUEHD' in info:
			s += 30
		if 'DTS-HD' in info or 'DTSHD' in info or 'DTSHDMA' in info or 'DTS-HD MA' in info:
			s += 25
		if 'AAC' in info:
			s += 5

		# Prefer HEVC if setting enabled
		if getSetting('source.prioritize.hevc') == 'true':
			if 'HEVC' in info or 'H265' in info or 'H.265' in info or 'X265' in name:
				s += 20

		# Torrent health
		seed = it.get('seeders') or 0
		try:
			seed = int(seed)
		except:
			seed = 0
		s += min(seed, 500)

		# Size sanity: avoid absurdly small "fake" files
		size = it.get('size') or 0
		try:
			size = float(size)
		except:
			size = 0
		if size and size < 0.25:
			s -= 200

		# ── Personalized ranker (learned from user history) ─────────────
		# Devuelve 0 si está desactivado, hay <10 plays, o hay error.
		# El peso del setting controla cuánto puede mover el ranking.
		try:
			weight = int(getSetting('personal.ranker.weight') or '0')
			if weight > 0:
				from resources.lib.database import source_ranker
				adj = source_ranker.score_adjustment(it)
				if adj:
					s += adj * weight
		except Exception:
			pass

		try:
			return int(s)
		except:
			return 0

	def _smart_autoplay_sort(self, items):
		"""Return items sorted for autoplay resolution.

		We keep existing ordering as a base (which already reflects Debrid priority
		and quality grouping from sourcesFilter), but add a scoring component to
		push better candidates earlier.
		"""
		# Stable sort: score desc, then keep original order
		return sorted(list(items), key=lambda it: self._smart_score(it), reverse=True)


	def sourcesResolve(self, item):
		try:
			url = item['url']
			self.url = None
			debrid_provider = item['debrid'] if item.get('debrid') else ''
		except: log_utils.error()
		if 'magnet:' in url:
			if not 'uncached' in item['source']:
				try:
					meta = homeWindow.getProperty(self.metaProperty) # need for CM "download" action
					if meta:
						meta = jsloads(unquote(meta.replace('%22', '\\"')))
						season, episode, title = meta.get('season'), meta.get('episode'), meta.get('title')
					else:
						season = homeWindow.getProperty(self.seasonProperty)
						episode = homeWindow.getProperty(self.episodeProperty)
						title = homeWindow.getProperty(self.titleProperty)
					if debrid_provider == 'Real-Debrid':
						from resources.lib.debrid.realdebrid import RealDebrid as debrid_function
					elif debrid_provider == 'Premiumize.me':
						from resources.lib.debrid.premiumize import Premiumize as debrid_function
					elif debrid_provider == 'AllDebrid':
						from resources.lib.debrid.alldebrid import AllDebrid as debrid_function
					elif debrid_provider == 'Offcloud':
						from resources.lib.debrid.offcloud import Offcloud as debrid_function
					elif debrid_provider == 'EasyDebrid':
						from resources.lib.debrid.easydebrid import EasyDebrid as debrid_function
					elif debrid_provider == 'TorBox':
						from resources.lib.debrid.torbox import TorBox as debrid_function
					else: return
					url = debrid_function().resolve_magnet(url, item['hash'], season, episode, title)
					self.url = url
					return url
				except:
					log_utils.error()
					return
		else:
			try:
				direct = item['direct']
				if direct:
					direct_sources = ('ad_cloud', 'oc_cloud', 'pm_cloud', 'rd_cloud', 'tb_cloud')
					if item['provider'] in direct_sources:
						try:
							call = [i[1] for i in self.sourceDict if i[0] == item['provider']][0]
							url = call().resolve(url)
							self.url = url
							return url
						except: pass
					else:
						self.url = url
						return url
				else: # hosters
					if debrid_provider == 'Real-Debrid':
						from resources.lib.debrid.realdebrid import RealDebrid as debrid_function
					elif debrid_provider == 'Premiumize.me':
						from resources.lib.debrid.premiumize import Premiumize as debrid_function
					elif debrid_provider == 'AllDebrid':
						from resources.lib.debrid.alldebrid import AllDebrid as debrid_function
					url = debrid_function().unrestrict_link(url)
					self.url = url
					return url
			except:
				log_utils.error()
				return

	def debridPackDialog(self, provider, name, magnet_url, info_hash):
		try:
			if provider in ('Real-Debrid', 'RD'):
				from resources.lib.debrid.realdebrid import RealDebrid as debrid_function
			elif provider in ('Premiumize.me', 'PM'):
				from resources.lib.debrid.premiumize import Premiumize as debrid_function
			elif provider in ('AllDebrid', 'AD'):
				from resources.lib.debrid.alldebrid import AllDebrid as debrid_function
			elif provider in ('Offcloud', 'OC'):
				from resources.lib.debrid.offcloud import Offcloud as debrid_function
			elif provider in ('EasyDebrid', 'ED'):
				from resources.lib.debrid.easydebrid import EasyDebrid as debrid_function
			elif provider in ('TorBox', 'TB'):
				from resources.lib.debrid.easydebrid import EasyDebrid as debrid_function
			else: return
			debrid_files = None
			control.busy()
			try: debrid_files = debrid_function().display_magnet_pack(magnet_url, info_hash)
			except: pass
			if not debrid_files:
				control.hide()
				return control.notification(message=32399)
			debrid_files = sorted(debrid_files, key=lambda k: k['filename'].lower())
			display_list = ['%02d | [B]%.2f GB[/B] | [I]%s[/I]' % (count, i['size'], i['filename'].upper()) for count, i in enumerate(debrid_files, 1)]
			control.hide()
			chosen = control.selectDialog(display_list, heading=name)
			if chosen < 0: return None
			if control.condVisibility("Window.IsActive(source_results.xml)"): # close "source_results.xml" here after selection is made and valid
				control.closeAll()
			control.busy()
			chosen_result = debrid_files[chosen]
			if provider in ('Real-Debrid', 'RD'):
				self.url = debrid_function().unrestrict_link(chosen_result['link'])
			elif provider in ('Premiumize.me', 'PM'):
				self.url = debrid_function().add_headers_to_url(chosen_result['link'])
			elif provider in ('AllDebrid', 'AD'):
				self.url = debrid_function().unrestrict_link(chosen_result['link'])
			elif provider in ('Offcloud', 'OC'):
				self.url = chosen_result['link']
			elif provider in ('EasyDebrid', 'ED'):
				self.url = debrid_function().unrestrict_link(chosen_result['link'])
			elif provider in ('TorBox', 'TB'):
				self.url = debrid_function().unrestrict_link(chosen_result['link'])
			from resources.lib.modules import player
			meta = jsloads(unquote(homeWindow.getProperty(self.metaProperty).replace('%22', '\\"'))) # needed for CM "showDebridPack" action
			title = meta['tvshowtitle']
			year = meta['year'] if 'year' in meta else None
			season = meta['season'] if 'season' in meta else None
			episode = meta['episode'] if 'episode' in meta else None
			imdb = meta['imdb'] if 'imdb' in meta else None
			tmdb = meta['tmdb'] if 'tmdb' in meta else None
			tvdb = meta['tvdb'] if 'tvdb' in meta else None
			release_title = chosen_result['filename']
			control.hide()
			from resources.lib.modules import source_utils
			if source_utils.seas_ep_filter(season, episode, release_title):
				return player.Player().play_source(title, year, season, episode, imdb, tmdb, tvdb, self.url, meta, debridPackCall=True) # hack fix for setResolvedUrl issue
			else:
				return player.Player().play(self.url)
		except:
			log_utils.error('Error debridPackDialog: ')
			control.hide()

	def sourceInfo(self, item):
		try:
			from sys import platform as sys_platform
			supported_platform = any(value in sys_platform for value in ('win32', 'linux2'))
			source = jsloads(item)[0]
			list = [('[COLOR %s]url:[/COLOR]  %s' % (self.highlight_color, source.get('url')), source.get('url'))]
			if supported_platform: list += [('[COLOR %s]  -- Copy url To Clipboard[/COLOR]' % self.highlight_color, ' ')] # "&" in magnets causes copy2clip to fail .replace('&', '^&').strip() used in copy2clip() method
			list += [('[COLOR %s]name:[/COLOR]  %s' % (self.highlight_color, source.get('name')), source.get('name'))]
			if supported_platform: list += [('[COLOR %s]  -- Copy name To Clipboard[/COLOR]' % self.highlight_color, ' ')]
			if 'magnet:' in source.get('url'):
				list += [('[COLOR %s]hash:[/COLOR]  %s' % (self.highlight_color, source.get('hash')), source.get('hash'))]
				if supported_platform: list += [('[COLOR %s]  -- Copy hash To Clipboard[/COLOR]' % self.highlight_color, ' ')]
				list += [('[COLOR %s]seeders:[/COLOR]  %s' % (self.highlight_color, source.get('seeders')), ' ')]
			list += [('[COLOR %s]info:[/COLOR]  %s' % (self.highlight_color, source.get('info')), ' ')]
			select = control.selectDialog([i[0] for i in list], 'Source Info')
			if any(x in list[select][0] for x in ('Copy url To Clipboard', 'Copy name To Clipboard', 'Copy hash To Clipboard')):
				from resources.lib.modules.source_utils import copy2clip
				copy2clip(list[select - 1][1])
			return
		except: log_utils.error('Error sourceInfo: ' )

	def alterSources(self, url, meta):
		try:
			if getSetting('play.mode') == '1' or (self.enable_playnext and 'episode' in meta): url += '&select=0'
			else: url += '&select=1'
			control.execute('PlayMedia(%s)' % url)
		except: log_utils.error()

	def errorForSources(self):
		try:
			homeWindow.clearProperty('luc_kodi.source_progress_is_alive')
			control.sleep(200)
			control.hide()
			if self.url == 'close://': control.notification(message=32400)
			else: control.notification(message=32401)
			control.cancelPlayback()
		except: log_utils.error()

	def getAliasTitles(self, imdb, content):
		try:
			if content == 'movie':
				from resources.lib.modules.trakt import getMovieAliases
				t = getMovieAliases(imdb)
			else:
				from resources.lib.modules.trakt import getTVShowAliases
				t = getTVShowAliases(imdb)
			if not t: return []
			t = [i for i in t if i.get('country', '').lower() in ('en', '', 'ca', 'us', 'uk', 'gb')]
			return t
		except:
			log_utils.error()
			return []

	def subTitle(self, tvshowtitle):
		"""
		Comprueba si 'tvshowtitle' tiene una sustitución almacenada y la devuelve.
		Usado durante el scraping para remap de títulos (ej. "Fargo" → "Fargo US").
		"""
		if tvshowtitle:
			try:
				from resources.lib.database import titlesubs
				subtvshowtitle = titlesubs.substitute_get(tvshowtitle)
				if subtvshowtitle:
					tvshowtitle = subtvshowtitle
			except:
				tvshowtitle = tvshowtitle
			return tvshowtitle
		else:
			return None

	def getSubsList(self):
		"""
		Abre el diálogo de gestión de sustituciones de títulos.
		Permite al usuario ver y eliminar sustituciones guardadas.
		"""
		try:
			control.hide()
			from resources.lib.database import titlesubs
			addedSubs = titlesubs.all_substitutes(self)
			items = [{'originalTitle': i['originalTitle'], 'subTitle': i['subTitle']} for i in addedSubs]
			from resources.lib.windows.title_sublist_manager import TitleSublistManagerXML
			window = TitleSublistManagerXML('title_sublist_manager.xml', control.addonPath(control.addonId()), results=items)
			selected_items = window.run()
			if selected_items:
				self.removeSubs(selected_items)
			del window
		except:
			log_utils.error()

	def addNewSub(self):
		"""
		Solicita al usuario un par de títulos (original → sustituto) y lo guarda.
		"""
		original_title = control.dialog.input('[COLOR %s]%s[/COLOR]' % (self.highlight_color, getLS(40245)), type=control.alpha_input)
		if original_title:
			sub_title = control.dialog.input('[COLOR %s]%s[/COLOR]' % (self.highlight_color, getLS(40247)), type=control.alpha_input)
			if sub_title:
				from resources.lib.database import titlesubs
				titlesubs.sub_insert(original_title, sub_title)
				control.notification(message=40248)

	def removeSubs(self, items):
		"""Elimina una lista de sustituciones de la base de datos."""
		try:
			if len(items) > 0:
				for v in items:
					removeitem = str(v.get('originalTitle'))
					from resources.lib.database import titlesubs
					titlesubs.clear_substitute('substitle', removeitem)
		except:
			log_utils.error()

	def getTitle(self, title):
		title = string_tools.normalize(title)
		return title

	def getConstants(self):
		self.metaProperty = 'plugin.video.luc_kodi.container.meta'
		self.seasonProperty = 'plugin.video.luc_kodi.container.season'
		self.episodeProperty = 'plugin.video.luc_kodi.container.episode'
		self.titleProperty = 'plugin.video.luc_kodi.container.title'
		self.imdbProperty = 'plugin.video.luc_kodi.container.imdb'
		self.tmdbProperty = 'plugin.video.luc_kodi.container.tmdb'
		self.tvdbProperty = 'plugin.video.luc_kodi.container.tvdb'
		self.labelProperty = 'plugin.video.luc_kodi.container.label'

		# v1.0.12: just-in-time safety net for the torboxnews scraper. The
		# 'provider.torboxnews' setting was historically hidden by a broken
		# visible= condition (v <= 1.0.10), so existing users may have it stuck
		# at '' / 'false'. If TorBox is properly authorized, flip it to 'true'
		# BEFORE fs_sources() reads the per-provider gate. Without this, the
		# torboxnews scraper (NEWZNAB results) would not be loaded.
		try:
			if (getSetting('torbox.enable') == 'true'
				and getSetting('torbox.token')
				and getSetting('provider.torboxnews') != 'true'):
				control.setSetting('provider.torboxnews', 'true')
				log_utils.log('luc_kodi v1.0.12: just-in-time enabled provider.torboxnews', level=log_utils.LOGDEBUG)
		except Exception:
			pass

		if self.all_providers == 'true':
			self.sourceDict = fs_sources(ret_all=True)
		else:
			self.sourceDict = fs_sources()
			self.sourceDict.extend(cloudSources())

		from resources.lib.debrid import premium_hosters
		self.debrid_resolvers = debrid.debrid_resolvers()

		self.prem_providers = [] # for sorting by debrid and direct source links priority
		if getSetting('easynews.username'): self.prem_providers += [('easynews', int(getSetting('easynews.priority')))]
		self.prem_providers += [(d.name, int(d.sort_priority)) for d in self.debrid_resolvers]

		def cache_prDict():
			try:
				hosts = []
				for d in self.debrid_resolvers: hosts += d.get_hosts()[d.name]
				return list(set(hosts))
			except: return premium_hosters.hostprDict
		self.hostprDict = providerscache.get(cache_prDict, 168)
		self.sourcecfDict = premium_hosters.sourcecfDict

	def calc_pack_size(self):
		seasoncount, counts = None, None
		try:
			if self.meta: seasoncount, counts = self.meta.get('seasoncount', None), self.meta.get('counts', None)
		except: log_utils.error()
		if not seasoncount or not counts: # check metacache, 2nd fallback
			try:
				imdb_user = getSetting('imdb.user').replace('ur', '')
				tvdb_key = getSetting('tvdb.api.key')
				user = str(imdb_user) + str(tvdb_key)
				meta_lang = control.apiLanguage()['tvdb']
				if self.meta: imdb, tmdb, tvdb = self.meta.get('imdb', ''), self.meta.get('tmdb', ''), self.meta.get('tvdb', '')
				else: imdb, tmdb, tvdb = homeWindow.getProperty(self.imdbProperty), homeWindow.getProperty(self.tmdbProperty), homeWindow.getProperty(self.tvdbProperty)
				ids = [{'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb}]
				meta2 = metacache.fetch(ids, meta_lang, user)[0]
				if not seasoncount: seasoncount = meta2.get('seasoncount', None)
				if not counts: counts = meta2.get('counts', None)
			except: log_utils.error()
		if not seasoncount or not counts: # make request, 3rd fallback
			try:
				if self.meta: season = self.meta.get('season')
				else: season = homeWindow.getProperty(self.seasonProperty)
				from resources.lib.indexers import tmdb as tmdb_indexer
				counts = tmdb_indexer.TVshows().get_counts(tmdb)
				seasoncount = counts[str(season)]
			except:
				log_utils.error()
				return self.sources
		for i in self.sources:
			try:
#				if i['provider'] == 'torrentio': continue # torrentio return file size based on episode query already so bypass re-calc
				if i['provider'] in ('torrentio', 'knightcrawler', 'nyaaio', 'mediafusion'): continue
				if 'package' in i:
					dsize = i.get('size')
					if not dsize: continue
					if i['package'] == 'season':
						divider = int(seasoncount)
						if not divider: continue
					else:
						if not counts: continue
						season_count = 1 ; divider = 0
						while season_count <= int(i['last_season']):
							divider += int(counts[str(season_count)])
							season_count += 1
					float_size = float(dsize) / divider
					if round(float_size, 2) == 0: continue
					str_size = '%.2f GB' % float_size
					info = i['info']
					try: info = [i['info'].split(' / ', 1)[1]]
					except: info = []
					info.insert(0, str_size)
					info = ' / '.join(info)
					i.update({'size': float_size, 'info': info})
				else:
					continue
			except: log_utils.error()
		return self.sources

	def ad_cache_chk_list(self, torrent_List, hashList):
		if len(torrent_List) == 0: return
		try:
#			from resources.lib.debrid.alldebrid import AllDebrid
#			cached = AllDebrid().check_cache(hashList)
#			if not cached: return None
#			cached = cached['magnets']
#			count = 0
#			for i in torrent_List:
#				if 'error' in cached[count]: # list index out of range
#					count += 1
#					continue
#				if cached[count]['instant'] is False:
#					if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
#					else: i.update({'source': 'uncached torrent'})
#				else:
#					if 'package' in i: i.update({'source': 'cached (pack) torrent'})
#					else: i.update({'source': 'cached torrent'})
#				count += 1
			[i.update({'source': i.get('source','torrent')}) for i in torrent_List]
			return torrent_List
		except: log_utils.error()

	def pm_cache_chk_list(self, torrent_List, hashList):
		if len(torrent_List) == 0: return
		try:
			from resources.lib.debrid.premiumize import Premiumize
			cached = Premiumize().check_cache_list(hashList)
			if not cached: return None
			count = 0
			for i in torrent_List:
				if cached[count] is False:
					if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
					else: i.update({'source': 'uncached torrent'})
				else:
					if 'package' in i: i.update({'source': 'cached (pack) torrent'})
					else: i.update({'source': 'cached torrent'})
				count += 1
			return torrent_List
		except: log_utils.error()

	def rd_cache_chk_list(self, torrent_List, hashList):
		def _process(_chunk, _id):
			try: cached.update(dmm.check_cache(_chunk, _id))
			except: pass
		if len(torrent_List) == 0: return
		try:
			if getSetting('realdebrid.check_cache') in ('', 'true'):
				from resources.lib.debrid.dmm import DMMCache
				from resources.lib.database import cache as _db_cache
				from hashlib import md5 as _md5
				# ── DMM availability cache (30 min) — skip API on warm repeat plays ──
				_norm = sorted([h.lower() for h in hashList if len(h) == 40])
				_ckey = 'dmm_avail_' + _md5('|'.join(_norm).encode('utf-8')).hexdigest()
				_crow = _db_cache.cache_get(_ckey)
				if _crow and _db_cache._is_cache_valid(_crow['date'], 0.5): # 0.5h = 30 min
					try:
						cached = literal_eval(_crow['value'])
						log_utils.log('rd_cache_chk_list: DMM SQLite cache hit (%d hashes)' % len(_norm), level=log_utils.LOGDEBUG)
					except Exception:
						cached = {}
				else:
					cached = {}
					threads = []
					chunk_size, dmm = 100, DMMCache()
					chunks = (hashList[i:i + chunk_size] for i in range(0, len(hashList), chunk_size))
					for chunk in chunks:
						thread = Thread(target=_process, args=(chunk, self.meta['imdb']))
						threads.append(thread)
						thread.start()
					[i.join() for i in threads]
					if cached:
						try: _db_cache.cache_insert(_ckey, repr(cached))
						except Exception: pass
				# ── end DMM cache ─────────────────────────────────────────────────
				if not cached: return None
				for i in torrent_List:
					if not cached.get(i['hash'].lower(), []): # i['hash'] could still be base32 here and not found due to conversion above
						if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
						else: i.update({'source': 'uncached torrent'})
						continue
					elif len(cached[i['hash'].lower()]) >= 1:
						if 'package' in i: i.update({'source': 'cached (pack) torrent'})
						else: i.update({'source': 'cached torrent'})
					else:
						if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
						else: i.update({'source': 'uncached torrent'})
			else: [i.update({'source': f"unchecked{' (pack)' if 'package' in i else ''}"}) for i in torrent_List]
			# ── RD 2026 keyword-filter compliance (May-2026 infringing_file gate) ──
			# Drop items whose filename matches RD's known keyword filter so the
			# user never clicks a result that will 451 on /unrestrict/link.
			try:
				from resources.lib.modules import rd_filter as _rd_filter
				_before = len(torrent_List)
				torrent_List, _removed = _rd_filter.apply_to_torrent_list(torrent_List)
				if _removed:
					log_utils.log(
						'rd_cache_chk_list: RD2026 filter v%s removed %d of %d torrents '
						'(infringing_file keyword match)' % (_rd_filter.RD_FILTER_VERSION, _removed, _before),
						level=log_utils.LOGDEBUG)
			except Exception:
				log_utils.error()
			# ── end RD 2026 filter ────────────────────────────────────────────
			return torrent_List
		except: log_utils.error()

	def oc_cache_chk_list(self, torrent_List, hashList):
		if len(torrent_List) == 0: return
		try:
			from resources.lib.debrid.offcloud import Offcloud
			cached = Offcloud().check_cache(hashList)
			if not cached: return None
			cached = cached['cachedItems']
			for i in torrent_List:
				if i['hash'].lower() in cached:
					if 'package' in i: i.update({'source': 'cached (pack) torrent'})
					else: i.update({'source': 'cached torrent'})
				else:
					if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
					else: i.update({'source': 'uncached torrent'})
			return torrent_List
		except: log_utils.error()

	def ed_cache_chk_list(self, torrent_List, hashList):
		if len(torrent_List) == 0: return
		try:
			from resources.lib.debrid.easydebrid import EasyDebrid
			cached = EasyDebrid().check_cache(hashList)
			if not cached: return None
			cached = cached['cached']
			for i, is_cached in zip(torrent_List, cached):
				if i['hash'].lower() and is_cached:
					if 'package' in i: i.update({'source': 'cached (pack) torrent'})
					else: i.update({'source': 'cached torrent'})
				else:
					if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
					else: i.update({'source': 'uncached torrent'})
			return torrent_List
		except: log_utils.error()

	def tb_cache_chk_list(self, torrent_List, hashList):
		if len(torrent_List) == 0: return
		try:
			from resources.lib.debrid.torbox import TorBox
			cached = TorBox().check_cache(hashList)
			if not cached: return None
			# v1.0.17 FIX: normalize both sides of the comparison to lowercase. TorBox
			# currently returns lowercase hashes, but defending against a future API
			# change is cheap and the bug would be invisible until it bit us.
			cached = [i['hash'].lower() for i in cached['data'] if i.get('hash')]
			for i in torrent_List:
				if i['hash'].lower() in cached:
					if 'package' in i: i.update({'source': 'cached (pack) torrent'})
					else: i.update({'source': 'cached torrent'})
				else:
					if 'package' in i: i.update({'source': 'uncached (pack) torrent'})
					else: i.update({'source': 'uncached torrent'})
			return torrent_List
		except: log_utils.error()

	def clr_item_providers(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered):
		providerscache.remove(self.getSources, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered) # function cache removal of selected item ONLY
		try:
			dbcon = database.connect(sourceFile)
			dbcur = dbcon.cursor()
			dbcur.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='rel_src';''') # table exists so both will
			if dbcur.fetchone()[0] == 1:
				dbcur.execute('''DELETE FROM rel_src WHERE imdb_id=?''', (imdb,)) # DEL the "rel_src" list of cached links
				dbcur.connection.commit()
		except: log_utils.error()
		finally: dbcur.close() ; dbcon.close()

	def imdb_meta_chk(self, imdb, title, year):
		try:
			if not imdb or imdb == '0': return title, year
			from resources.lib.modules.client import _basic_request
			result = _basic_request('https://v2.sg.media-imdb.com/suggestion/t/{}.json'.format(imdb))
			if not result: return title, year
			result = jsloads(result)['d'][0]
			year_ck = str(result.get('y', ''))
			title_ck = self.getTitle(result['l'])
			if not year_ck or not title_ck: return title, year
			if self.mediatype == 'movie':
				if getSetting('imdb.Movietitle.check') == 'true' and (title != title_ck):
					log_utils.log('IMDb Movie title_ck: (%s) does not match meta Movie title passed: (%s)' % (title_ck, title), __name__, level=log_utils.LOGDEBUG)
					title = title_ck
				if getSetting('imdb.Movieyear.check') == 'true' and (year != year_ck):
					log_utils.log('IMDb Movie year_ck: (%s) does not match meta Movie year passed: (%s) for title: (%s)' % (year_ck, year, title), __name__, level=log_utils.LOGDEBUG)
					year = year_ck
			else:
				if getSetting('imdb.Showtitle.check') == 'true' and (title != title_ck):
					log_utils.log('IMDb Show title_ck: (%s) does not match meta tvshowtitle title passed: (%s)' % (title_ck, title), __name__, level=log_utils.LOGDEBUG)
					title = title_ck
				if getSetting('imdb.Showyear.check') == 'true' and (year != year_ck):
					log_utils.log('IMDb Show year_ck: (%s) does not match meta tvshowtitle year passed: (%s) for title: (%s)' % (year_ck, year, title), __name__, level=log_utils.LOGDEBUG)
					year = year_ck
			return title, year
		except:
			log_utils.error()
			return title, year

	def get_season_info(self, imdb, tmdb, tvdb, meta, season):
		total_seasons = None
		season_isAiring = None
		try:
			total_seasons = meta.get('total_seasons', None)
			season_isAiring = meta.get('season_isAiring', None)
		except: pass
		if not total_seasons or season_isAiring is None: # check metacache, 2nd fallback
			try:
				imdb_user = getSetting('imdb.user').replace('ur', '')
				tvdb_key = getSetting('tvdb.api.key')
				user = str(imdb_user) + str(tvdb_key)
				meta_lang = control.apiLanguage()['tvdb']
				ids = [{'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb}]
				meta2 = metacache.fetch(ids, meta_lang, user)[0]
				if not total_seasons: total_seasons = meta2.get('total_seasons', None)
				if season_isAiring is None: season_isAiring = meta2.get('season_isAiring', None)
			except: log_utils.error()
		if not total_seasons: # make request, 3rd fallback
			try:
				from resources.lib.modules.trakt import getSeasons
				total_seasons = getSeasons(imdb, full=False)
				if total_seasons:
					total_seasons = [i['number'] for i in total_seasons]
					season_special = True if 0 in total_seasons else False
					total_seasons = len(total_seasons)
					if season_special: total_seasons = total_seasons - 1
			except: log_utils.error()
		if season_isAiring is None:
			try:
				from resources.lib.indexers import tmdb as tmdb_indexer
				season_isAiring = tmdb_indexer.TVshows().get_season_isAiring(tmdb, season)
				if not season_isAiring: season_isAiring = 'false'
			except: log_utils.error()
		return total_seasons, season_isAiring

	def mix_by_provider(self, source_list, top_n=120, max_per_provider=12):
		"""Diversify providers in the top of the list so one provider (e.g. torrentio) does not dominate."""
		try:
			if not source_list: return source_list
			top = source_list[:int(top_n)]
			rest = source_list[int(top_n):]
			buckets = {}
			order = []
			for item in top:
				key = item.get('provider') or item.get('debrid') or item.get('source') or ''
				if key not in buckets:
					buckets[key] = []
					order.append(key)
				buckets[key].append(item)
			out = []
			used = {k: 0 for k in buckets}
			while True:
				progressed = False
				for k in order:
					if buckets.get(k) and used.get(k, 0) < int(max_per_provider):
						out.append(buckets[k].pop(0))
						used[k] = used.get(k, 0) + 1
						progressed = True
				if not progressed:
					break
			# append any leftovers (still preserving the original provider order)
			for k in order:
				out.extend(buckets.get(k, []))
			return out + rest
		except:
			return source_list

	def sort_byQuality(self, source_list):
		filter = []
		quality = getSetting('hosts.quality') or '0'
		if quality == '0': filter += [i for i in source_list if i['quality'] == '4K']
		if quality in ('0', '1'): filter += [i for i in source_list if i['quality'] == '1080p']
		if quality in ('0', '1', '2'): filter += [i for i in source_list if i['quality'] == '720p']
		filter += [i for i in source_list if i['quality'] == 'SCR']
		filter += [i for i in source_list if i['quality'] == 'SD']
		filter += [i for i in source_list if i['quality'] == 'CAM']
		quality_min = getSetting('hosts.quality.min') or '0'
		if quality_min == '1':   # min 720p: remove SD/SCR/CAM
			filter = [i for i in filter if i['quality'] not in ('SD', 'SCR', 'CAM')]
		elif quality_min == '2': # min 1080p: remove SD/SCR/CAM + 720p
			filter = [i for i in filter if i['quality'] not in ('SD', 'SCR', 'CAM', '720p')]
		elif quality_min == '3': # min 4K: only 4K
			filter = [i for i in filter if i['quality'] == '4K']
		return filter

	def getSourceProgress(self, header, meta):
		from resources.lib.windows.source_progress import SourceProgressXML
		window = SourceProgressXML('source_progress.xml', control.addonPath(control.addonId()), heading=header, meta=meta)
		window.create()
		return window


	def _ramcache_ttl_seconds(self):
		try:
			# Default raised to 20 min — processed results (post-debrid + post-sort) are
			# stable within a session and expensive to regenerate (DMMCache API call).
			minutes = int(getSetting('sources.ramcache.ttl') or '20')
		except:
			minutes = 20
		if minutes < 1: minutes = 1
		if minutes > 120: minutes = 120
		return minutes * 60

	def _build_ramcache_id(self, imdb, tmdb, tvdb, season, episode, year):
		try:
			parts = [str(imdb or ''), str(tmdb or ''), str(tvdb or ''), str(season or ''), str(episode or ''), str(year or '')]
			return '|'.join(parts)
		except:
			return ''

	def _ramcache_get(self, cache_id):
		try:
			if not cache_id: return None
			data = homeWindow.getProperty('luc_kodi.ramcache.' + cache_id)
			ts = homeWindow.getProperty('luc_kodi.ramcache_ts.' + cache_id)
			if not data or not ts: return None
			if (time() - float(ts)) > self._ramcache_ttl_seconds(): return None
			return jsloads(data)
		except:
			return None

	def _ramcache_set(self, cache_id, items):
		try:
			if not cache_id or not items: return
			# Only cache items that have gone through the debrid check (have 'debrid' key
			# or are direct/cloud sources). Stale pre-check items waste memory and TTL.
			_resolved = [i for i in items if i.get('debrid') or i.get('direct') or i.get('source') == 'cloud']
			if not _resolved: return  # nothing debrid-resolved yet — don't cache
			# Cap at top-200 to avoid bloating Kodi window properties with 4000 dicts.
			_to_cache = items[:200]
			homeWindow.setProperty('luc_kodi.ramcache.' + cache_id, jsdumps(_to_cache))
			homeWindow.setProperty('luc_kodi.ramcache_ts.' + cache_id, str(time()))
		except:
			pass

	def _ramcache_clear(self, cache_id):
		try:
			if not cache_id: return
			homeWindow.clearProperty('luc_kodi.ramcache.' + cache_id)
			homeWindow.clearProperty('luc_kodi.ramcache_ts.' + cache_id)
		except:
			pass