# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

from resources.lib.modules import control, log_utils
from resources.lib.modules.catalog_updater import CatalogService
from sys import version_info, platform as sys_platform
from threading import Thread
window = control.homeWindow
pythonVersion = '{}.{}.{}'.format(version_info[0], version_info[1], version_info[2])
plugin = 'plugin://plugin.video.luc_kodi/'
LOGINFO = log_utils.LOGINFO


class TorBoxUsenetMigration:
	"""One-shot migration (v1.0.11+): the torboxnews scraper was gated by
	the dead 'provider.torboxnews' setting which was hidden in the UI by
	a broken visible= condition. For users who have TorBox configured but
	never had a chance to flip the toggle, auto-enable it.

	v1.0.12 hardening: keep firing if provider.torboxnews is still empty AND
	TorBox is properly configured, ignoring the migration marker. This catches
	the corner case where a user installed v1.0.11 but the migration ran
	before TorBox was authorized."""
	MARKER = 'migration.torboxnews_2026'
	def run(self):
		try:
			tb_token = control.setting('torbox.token') or ''
			tb_enabled = control.setting('torbox.enable') in ('', 'true')
			cur_provider = control.setting('provider.torboxnews')
			# Defensive re-run: regardless of marker, if TB is properly configured
			# AND provider.torboxnews is not yet 'true', enable it now.
			if tb_token and tb_enabled and cur_provider != 'true':
				control.setSetting('provider.torboxnews', 'true')
				control.log('[ plugin.video.luc_kodi ]  Migration: provider.torboxnews -> true (was %r)' % cur_provider, LOGINFO)
			# Mark migration as done so the noop path is taken in the future.
			if control.setting(self.MARKER) != 'true':
				control.setSetting(self.MARKER, 'true')
		except Exception:
			log_utils.error()

class DmmReenableMigration:
	"""One-shot migration (v1.0.56): el scraper DMM vuelve a estar ACTIVO.
	La v1.0.54 lo apago leyendo el 429 como un cierre a terceros, pero el
	429 lo devuelve el limitador ANTES de tocar el handler: en el codigo
	publico de DMM /api/torrents esta topado a 1 peticion cada 2 segundos
	por IP (RATE_LIMIT_CONFIGS.torrents), y el scraper pedia las paginas 0
	y 1 en paralelo — la segunda chocaba siempre. Con una sola peticion
	serializada por busqueda el scraper funciona. Esta migracion vuelve a
	encender provider.dmm UNA sola vez en las instalaciones que lo tenian
	apagado por la migracion anterior; a partir de ahi manda el usuario
	(marker one-shot, patron TorBoxUsenetMigration)."""
	MARKER = 'migration.dmm_on_2026'
	def run(self):
		try:
			if control.setting(self.MARKER) != 'true':
				if control.setting('provider.dmm') != 'true':
					control.setSetting('provider.dmm', 'true')
					control.log('[ plugin.video.luc_kodi ]  Migration: provider.dmm -> true (rate-limit handled, see changelog 1.0.56)', LOGINFO)
				control.setSetting(self.MARKER, 'true')
		except Exception:
			log_utils.error()

class CheckSettingsFile:
	def run(self):
		try:
			control.log('[ plugin.video.luc_kodi ]  CheckSettingsFile Service Starting...', LOGINFO)
			window.clearProperty('luc_kodi_settings')
			profile_dir = control.dataPath
			if not control.existsPath(profile_dir):
				success = control.makeDirs(profile_dir)
				if success: control.log('%s : created successfully' % profile_dir, LOGINFO)
			else: control.log('%s : already exists' % profile_dir, LOGINFO)
			settings_xml = control.joinPath(profile_dir, 'settings.xml')
			if not control.existsPath(settings_xml):
				control.setSetting('trakt.message2', '')
				control.log('%s : created successfully' % settings_xml, LOGINFO)
			else: control.log('%s : already exists' % settings_xml, LOGINFO)
			return control.log('[ plugin.video.luc_kodi ]  Finished CheckSettingsFile Service', LOGINFO)
		except:
			log_utils.error()

class SettingsMonitor(control.monitor_class):
	def __init__ (self):
		control.monitor_class.__init__(self)
		control.refresh_playAction()
		control.refresh_libPath()
		window.setProperty('luc_kodi.debug.reversed', control.setting('debug.reversed'))
		control.log('[ plugin.video.luc_kodi ]  Settings Monitor Service Starting...', LOGINFO)

	def onSettingsChanged(self): # Kodi callback when the addon settings are changed
		window.clearProperty('luc_kodi_settings')
		control.sleep(50)
		refreshed = control.make_settings_dict()
		control.refresh_playAction()
		control.refresh_libPath()
		control.refresh_debugReversed()

	def onNotification(self, sender, method, data):
		"""Intercepta los eventos de Kodi cuando plugin.video.luc_kodi
		es instalado o actualizado y muestra la notificación visual propia."""
		try:
			if method not in ('Addons.OnInstalled', 'Addons.OnUpdated'):
				return
			import json
			info = json.loads(data) if data else {}
			if info.get('id') != 'plugin.video.luc_kodi':
				return
			version = info.get('version') or control.getluc_kodiVersion()
			addon_name = control.addonInfo('name')
			if method == 'Addons.OnInstalled':
				control.notification(title=addon_name, message='v%s  installed successfully' % version, time=5000)
			elif method == 'Addons.OnUpdated':
				control.notification(title=addon_name, message='Updated to v%s' % version, time=5000)
		except:
			log_utils.error()

class ReuseLanguageInvokerCheck:
	def run(self):
		control.log('[ plugin.video.luc_kodi ]  ReuseLanguageInvokerCheck Service Starting...', LOGINFO)
		try:
			import xml.etree.ElementTree as ET
			from resources.lib.modules.language_invoker import gen_file_hash
			addon_xml = control.joinPath(control.addonPath('plugin.video.luc_kodi'), 'addon.xml')
			tree = ET.parse(addon_xml)
			root = tree.getroot()
			current_addon_setting = control.addon('plugin.video.luc_kodi').getSetting('reuse.languageinvoker')
			try: current_xml_setting = [str(i.text) for i in root.iter('reuselanguageinvoker')][0]
			except: return control.log('[ plugin.video.luc_kodi ]  ReuseLanguageInvokerCheck failed to get settings.xml value', LOGINFO)
			if current_addon_setting == '':
				current_addon_setting = 'true'
				control.setSetting('reuse.languageinvoker', current_addon_setting)
			if current_xml_setting == current_addon_setting:
				return control.log('[ plugin.video.luc_kodi ]  ReuseLanguageInvokerCheck Service Finished', LOGINFO)
			control.okDialog(message='%s\n%s' % (control.lang(33023), control.lang(33020)))
			for item in root.iter('reuselanguageinvoker'):
				item.text = current_addon_setting
				hash_start = gen_file_hash(addon_xml)
				tree.write(addon_xml)
				hash_end = gen_file_hash(addon_xml)
				control.log('[ plugin.video.luc_kodi ]  ReuseLanguageInvokerCheck Service Finished', LOGINFO)
				if hash_start != hash_end:
					current_profile = control.infoLabel('system.profilename')
					control.execute('LoadProfile(%s)' % current_profile)
				else: control.okDialog(title='default', message=33022)
			return
		except:
			log_utils.error()

class AddonCheckUpdate:
	def run(self):
		control.log('[ plugin.video.luc_kodi ]  Addon checking available updates', LOGINFO)
		try:
			import re
			from resources.lib.modules import client as _client
			repo_url = 'https://raw.githubusercontent.com/apoyotech/luc_repo/main/addons.xml'
			if not repo_url:
				return control.log('[ plugin.video.luc_kodi ]  ReuseLanguageInvokerCheck: repo_url empty, skipping remote version check', LOGINFO)
			repo_xml = _client.request(repo_url, timeout=15)
			if not repo_xml:
				return control.log('[ plugin.video.luc_kodi ]  Could not connect to remote repo XML', LOGINFO)
			repo_version = re.findall(r'<addon id=\"plugin.video.luc_kodi\".+version=\"(\d*.\d*.\d*)\"', repo_xml)[0]
			local_version = control.getluc_kodiVersion()[:5] # 5 char max so pre-releases do try to compare more chars than github version
			def check_version_numbers(current, new): # Compares version numbers and return True if github version is newer
				current = current.split('.')
				new = new.split('.')
				step = 0
				for i in current:
					if int(new[step]) > int(i): return True
					if int(i) > int(new[step]): return False
					if int(i) == int(new[step]):
						step += 1
						continue
				return False
			if check_version_numbers(local_version, repo_version):
				while control.condVisibility('Library.IsScanningVideo'):
					control.sleep(10000)
				control.log('[ plugin.video.luc_kodi ]  A newer version is available. Installed Version: v%s, Repo Version: v%s' % (local_version, repo_version), LOGINFO)
				control.notification(message=control.lang(35523) % repo_version)
			return control.log('[ plugin.video.luc_kodi ]  Addon update check complete', LOGINFO)
		except:
			log_utils.error()

class VersionIsUpdateCheck:
	def run(self):
		try:
			from resources.lib.database import cache
			isUpdate = False
			oldVersion, isUpdate = cache.update_cache_version()
			if isUpdate:
				window.setProperty('luc_kodi.updated', 'true')
				curVersion = control.getluc_kodiVersion()
				# NOTE: el antiguo borrado de caché por versión (umbral '6.5.6')
				# era HEREDADO del framework jacksparrow y no aplica a la
				# numeración 1.0.x de luc_kodi. Peor aún: en una instalación
				# limpia oldVersion='0' (< 656) disparaba un wipe innecesario de
				# metacache/cache. Queda DESACTIVADO por defecto.
				#
				# Si alguna migración futura necesita forzar un clear puntual,
				# poner aquí una condición ACOTADA a ese salto concreto, p.ej.:
				#   do_cacheClear = (oldVersion == '1.0.41' and curVersion == '1.0.42')
				# y llamar a cache.clrCache_version_update(...) solo en ese caso.
				do_cacheClear = False
				if do_cacheClear:
					cache.clrCache_version_update(clr_providers=False, clr_metacache=True, clr_cache=True, clr_search=False, clr_bookmarks=False)
				# FIX: save Trakt + subtitle credentials BEFORE the settings write that may reset settings.xml to defaults
				import xbmcaddon as _xa
				_addon_pre = _xa.Addon()
				_trakt_keys = ('trakt.token', 'trakt.refresh', 'trakt.username', 'trakt.isauthed', 'trakt.expires')
				_saved_trakt = {k: _addon_pre.getSetting(k) for k in _trakt_keys}
				# v1.0.18 SIMKL: same backup pattern — settings.xml rewrites would otherwise wipe the token.
				_simkl_keys = ('simkl.token', 'simkl.username', 'simkl.user_id', 'simkl.isauthed', 'simkl.expires')
				_saved_simkl = {k: _addon_pre.getSetting(k) for k in _simkl_keys}
				_sub_keys = ('subtitles', 'subtitles.notification', 'opensubsusername', 'opensubspassword', 'subtitles.lang.1', 'subtitles.lang.2')
				_saved_subs = {k: _addon_pre.getSetting(k) for k in _sub_keys}
				control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: Trakt + SIMKL + subtitle settings backed up before settings write', LOGINFO)

				control.setSetting('trakt.message2', '') # force a settings write for any added settings that may have been added in new version

				# FIX: restore Trakt + SIMKL + subtitle credentials if they existed before the write
				control.sleep(200) # small wait for Kodi to finish writing settings.xml
				_addon_post = _xa.Addon()
				if _saved_trakt.get('trakt.token'):
					for _k, _v in _saved_trakt.items():
						if _v:
							_addon_post.setSetting(_k, _v)
					control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: Trakt credentials restored after settings write', LOGINFO)
				if _saved_simkl.get('simkl.token'):
					for _k, _v in _saved_simkl.items():
						if _v:
							_addon_post.setSetting(_k, _v)
					control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: SIMKL credentials restored after settings write', LOGINFO)
				for _k, _v in _saved_subs.items():
					if _v:
						_addon_post.setSetting(_k, _v)
				control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: Subtitle settings restored after settings write', LOGINFO)

				# v1.0.41 FIX: una versión anterior llevaba la API key del autor
				# como fallback (DEFAULT_APIKEY). Cualquier usuario sin OAuth propio
				# quedaba con el username del autor guardado en mdblist.username (y
				# posiblemente su key en mdblist.apikey). Si NO hay token OAuth
				# propio, limpiamos esos restos para que no se muestre una cuenta
				# ajena. A quien autorizó su cuenta (tiene mdblist.token) no se le
				# toca nada.
				try:
					_LEAKED_MDB_APIKEY = 'xma2hxonarl718z4w7adchsef'
					_mdb_token = (_addon_post.getSetting('mdblist.token') or '').strip()
					if not _mdb_token or _mdb_token in ('0', 'empty_setting'):
						_mdb_apikey = (_addon_post.getSetting('mdblist.apikey') or '').strip()
						if _mdb_apikey == _LEAKED_MDB_APIKEY:
							_addon_post.setSetting('mdblist.apikey', '')
						# El username sólo es válido si hay credencial propia; sin
						# OAuth ni key propia no debe persistir ningún username.
						if (_addon_post.getSetting('mdblist.username') or '').strip():
							_addon_post.setSetting('mdblist.username', '')
						control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: cleared leaked MDBList credentials/username (no own OAuth)', LOGINFO)
				except Exception:
					log_utils.error()

				control.log('[ plugin.video.luc_kodi ]  Forced new User Data settings.xml saved', LOGINFO)

				# v1.0.45 MIGRACIÓN (una sola vez, acotada): los cambios de la API de
				# Trakt del 30-jun-2026 hicieron que versiones <=1.0.44 guardaran en
				# traktsync.db un watchlist vacío/truncado (actualizando además el
				# marcador last_watchlisted_at, con lo que el servicio nunca volvía a
				# sincronizar) y cachearan un Progress vacío durante 12h en cache.db.
				# Forzamos un resync completo en segundo plano para autocurar el
				# estado envenenado sin que el usuario tenga que hacer Force Sync.
				try:
					_old_t = tuple(int(x) for x in str(oldVersion).split('.') if x.isdigit())
				except Exception:
					_old_t = (0,)
				if _old_t < (1, 0, 46):
					import time as _time
					from threading import Thread as _Thread
					def _trakt_2026_resync():
						try:
							from resources.lib.modules import trakt as _trakt
							from resources.lib.database import traktsync as _ts
							if not _trakt.getTraktCredentialsInfo(): return
							# Espera 45s: deja que los primeros menus del usuario se
							# construyan sin competir con la migracion por el rate limit.
							if control.monitor.waitForAbort(45): return
							control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: Trakt 2026 API migration resync starting (bg)...', LOGINFO)
							_start = int(_time.time())
							_trakt.sync_watch_list(forced=True) # barato y visible: primero
							_trakt.sync_watchedProgress(forced=True) # refresca cache 12h del Progress
							# watched: lo mas pesado. Si un menu ya disparo el crawl
							# (single-flight) durante la espera, no lo repetimos.
							if _ts.timeout(_trakt.syncMovies) < _start:
								_trakt.cachesyncMovies()
							if _ts.timeout(_trakt.syncTVShows) < _start:
								_trakt.cachesyncTVShows()
							_trakt.service_syncSeasons() # ya throttled con Semaphore(8)
							_ts.insert_syncSeasons_at()
							control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: Trakt 2026 API migration resync complete', LOGINFO)
						except Exception:
							log_utils.error()
					_Thread(target=_trakt_2026_resync).start()

				control.log('[ plugin.video.luc_kodi ]  Plugin updated to v%s' % curVersion, LOGINFO)
		except:
			log_utils.error()

class SyncTraktCollection:
	def run(self):
		control.log('[ plugin.video.luc_kodi ]  Trakt Collection Sync Starting...', LOGINFO)
		control.execute('RunPlugin(%s?action=library_tvshowsToLibrarySilent&url=traktcollection)' % plugin)
		control.execute('RunPlugin(%s?action=library_moviesToLibrarySilent&url=traktcollection)' % plugin)
		control.log('[ plugin.video.luc_kodi ]  Trakt Collection Sync Complete', LOGINFO)

class LibraryService:
	def run(self):
		control.log('[ plugin.video.luc_kodi ]  Library Update Service Starting (Update check every 6hrs)...', LOGINFO)
		from resources.lib.modules import library
		library.lib_tools().service() # method contains control.monitor().waitForAbort() while loop every 6hrs

class GUIResolutionService:
	"""
	Delega en gui_resolution.run() — toda la lógica (detección, cambio,
	notificación) vive en resources/lib/modules/gui_resolution.py.
	run() es no-bloqueante: lanza un hilo daemon y retorna de inmediato.
	"""
	def run(self):
		try:
			from resources.lib.modules import gui_resolution
			gui_resolution.run()
		except Exception:
			log_utils.error()

class SyncTraktService:
	def run(self):
		service_syncInterval = control.setting('trakt.service.syncInterval') or '15'
		control.log('[ plugin.video.luc_kodi ]  Trakt Sync Service Starting (sync check every %s minutes)...' % service_syncInterval, LOGINFO)
		from resources.lib.modules import trakt
		trakt.trakt_service_sync() # method contains "control.monitor().waitForAbort()" while loop every "service_syncInterval" minutes

class SyncSimklService:
	"""v1.0.18: background SIMKL sync loop, parallel to Trakt. Idle when the
	user isn't authorized — re-checks on every interval tick."""
	def run(self):
		service_syncInterval = control.setting('simkl.service.syncInterval') or '15'
		control.log('[ plugin.video.luc_kodi ]  SIMKL Sync Service Starting (sync check every %s minutes)...' % service_syncInterval, LOGINFO)
		from resources.lib.modules import simkl
		simkl.simkl_service_sync()  # contains "control.monitor().waitForAbort()" loop

try:
	kodiVersion = control.getKodiVersion(full=True)
	addonVersion = control.addon('plugin.video.luc_kodi').getAddonInfo('version')
#	repoVersion = control.addon('repository.luc_repo').getAddonInfo('version')
#	fsVersion = control.addon('script.module.jacksparrowscrapers').getAddonInfo('version')
	log_utils.log('########   CURRENT luc_kodi VERSIONS REPORT   ########', level=LOGINFO)
#	log_utils.log('##   Platform: %s' % str(sys_platform), level=LOGINFO)
	log_utils.log('##   Kodi Version: %s' % str(kodiVersion), level=LOGINFO)
	log_utils.log('##   python Version: %s' % pythonVersion, level=LOGINFO)
	log_utils.log('##   plugin.video.luc_kodi Version: %s' % str(addonVersion), level=LOGINFO)
#	log_utils.log('##   repository.luc_kodi Version: %s' % str(repoVersion), level=LOGINFO)
#	log_utils.log('##   script.module.jacksparrowscrapers Version: %s' % str(fsVersion), level=LOGINFO)
	log_utils.log('######   luc_kodi SERVICE ENTERING KEEP ALIVE   #####', level=LOGINFO)
except:
	log_utils.log('## ERROR GETTING luc_kodi VERSION - Missing Repo or failed Install ', level=LOGINFO)


class CheckUndesirablesDatabase:
	def run(self):
		from resources.lib.jacksparrow.undesirables import Undesirables, add_new_default_keywords
		try:
			control.log('[ plugin.video.luc_kodi ]  CheckUndesirablesDatabase Service Starting', LOGINFO)
			old_database = Undesirables().check_database()
			if old_database: add_new_default_keywords()
			control.log('[ plugin.video.luc_kodi ]  CheckUndesirablesDatabase Service Finished', LOGINFO)
		except:
			log_utils.error()

def getTraktCredentialsInfo():
	username = control.setting('trakt.username').strip()
	token = control.setting('trakt.token')
	refresh = control.setting('trakt.refresh')
	if (username == '' or token == '' or refresh == ''): return False
	return True


class SubtitlePlayer(control.player2):
	"""
	Persistent xbmc.Player subclass in service.py.
	Reads metadata directly from getVideoInfoTag() — no inter-process
	window property passing needed.
	"""
	def __init__(self):
		control.player2.__init__(self)
		import threading
		self._sub_lock = threading.Lock()

	def onAVStarted(self):
		# Guard: only act on content launched by plugin.video.luc_kodi.
		# Player.FilenameAndPath returns the original plugin:// path of the playlist
		# item, even after setResolvedUrl has replaced getPlayingFile() with the
		# actual HTTP stream URL. This is reliable across all Kodi processes.
		import xbmc as _xbmc
		_path = _xbmc.getInfoLabel('Player.FilenameAndPath') or ''
		control.log('[ luc_kodi ] SubtitlePlayer.onAVStarted — FilenameAndPath=%s' % _path[:80], LOGINFO)
		if not _path.startswith('plugin://plugin.video.luc_kodi/'):
			return
		try:
			import xbmcaddon as _xa
			subs_on = _xa.Addon('plugin.video.luc_kodi').getSetting('subtitles') == 'true'
		except:
			subs_on = False
		control.log('[ luc_kodi ] SubtitlePlayer.onAVStarted — subs_on=%s' % subs_on, LOGINFO)
		if not subs_on:
			return
		# Guard: prevent simultaneous subtitle lookups (onAVStarted + onPlayBackResumed
		# can fire nearly at the same time causing duplicate notifications)
		if not self._sub_lock.acquire(blocking=False):
			control.log('[ luc_kodi ] SubtitlePlayer.onAVStarted — already running, skipping', LOGINFO)
			return
		try:
			tag     = self.getVideoInfoTag()
			title   = tag.getTitle() or ''
			year    = str(tag.getYear()) if tag.getYear() else ''
			# getIMDBNumber() only works if setIMDBNumber() was called.
			# infoTagger() uses setUniqueIDs({'imdb': ...}), so use getUniqueID('imdb')
			try: imdb = tag.getUniqueID('imdb') or ''
			except: imdb = tag.getIMDBNumber() or ''
			mtype   = tag.getMediaType() or ''
			season  = str(tag.getSeason()) if mtype == 'episode' and tag.getSeason() else None
			episode = str(tag.getEpisode()) if mtype == 'episode' and tag.getEpisode() else None
		except:
			log_utils.error()
			self._sub_lock.release()
			return
		control.log('[ luc_kodi ] SubtitlePlayer: title=%s imdb=%s season=%s ep=%s' % (title, imdb, season, episode), LOGINFO)
		if not title and not imdb:
			control.log('[ luc_kodi ] SubtitlePlayer: no metadata available, skipping', LOGINFO)
			self._sub_lock.release()
			return
		try:
			from resources.lib.modules.player import Subtitles
			Subtitles().get(title, year, imdb, season, episode)
		except:
			log_utils.error()
		finally:
			self._sub_lock.release()

	def onPlayBackResumed(self):
		"""
		Fired when the user resumes a paused/stopped video.
		Only acts on content launched by plugin.video.luc_kodi.
		"""
		import xbmc as _xbmc
		_path = _xbmc.getInfoLabel('Player.FilenameAndPath') or ''
		if not _path.startswith('plugin://plugin.video.luc_kodi/'):
			return
		try:
			from resources.lib.modules import tools
			tools.delete_all_subs()
			control.log('[ luc_kodi ] SubtitlePlayer.onPlayBackResumed — cleared stale subs, re-triggering', LOGINFO)
		except:
			pass
		control.sleep(500)
		self.onAVStarted()

class PosterJanitorService:
	def run(self):
		control.log('[ plugin.video.luc_kodi ]  Poster Texture Janitor Service Starting...', LOGINFO)
		from resources.lib.modules import poster_rotator
		poster_rotator.janitor_service() # contiene bucle "control.monitor.waitForAbort()"; no-op si la rotación está desactivada


class CacheMaintenanceService:
	def run(self):
		control.log('[ plugin.video.luc_kodi ]  Cache DB Maintenance Service Starting...', LOGINFO)
		from resources.lib.modules import cache_janitor
		cache_janitor.janitor_service() # contiene bucle "control.monitor.waitForAbort()"; no-op si está desactivado


def main():
	while not control.monitor.abortRequested():
		control.log('[ plugin.video.luc_kodi ]  Service Started', LOGINFO)
		schedTrakt = None
		libraryService = None
		CheckSettingsFile().run()
		TorBoxUsenetMigration().run()
		DmmReenableMigration().run()
		CheckUndesirablesDatabase().run()
		GUIResolutionService().run()  # non-blocking — lanza hilo daemon
		# v1.0.49: micro-servidor localhost que sirve el MPD de tráilers a
		# inputstream.adaptive (su pila CURL no lee special:// ni archivos).
		try:
			from resources.lib.modules import trailer_httpd
			trailer_httpd.start()  # non-blocking — hilo daemon
		except Exception:
			log_utils.error()
		ReuseLanguageInvokerCheck().run()
		if control.setting('library.service.update') == 'true':
			libraryService = Thread(target=LibraryService().run)
			libraryService.start()
#		if control.setting('general.checkAddonUpdates') == 'true':
#			AddonCheckUpdate().run()
		VersionIsUpdateCheck().run()

		syncTraktService = Thread(target=SyncTraktService().run) # run service in case user auth's trakt later, sync will loop and do nothing without valid auth'd account
		syncTraktService.start()

		# v1.0.18: SIMKL sync runs in parallel to Trakt. Like Trakt, the loop
		# is a no-op until the user authorizes — safe to start unconditionally.
		syncSimklService = Thread(target=SyncSimklService().run)
		syncSimklService.start()

		catalogService = Thread(target=CatalogService().run)
		catalogService.start()

		# v1.0.31: limpieza semanal de texturas de pósters rotados (no-op si está desactivada)
		posterJanitorService = Thread(target=PosterJanitorService().run)
		posterJanitorService.start()

		# v1.0.35: mantenimiento mensual de las bases de caché regenerables (no-op si está desactivado)
		cacheMaintenanceService = Thread(target=CacheMaintenanceService().run)
		cacheMaintenanceService.start()

		_subtitle_player = SubtitlePlayer()  # persistent Player in service process
		control.log('[ luc_kodi ] SubtitlePlayer registered', LOGINFO)


		if getTraktCredentialsInfo():
			if control.setting('autoTraktOnStart') == 'true':
				SyncTraktCollection().run()
			if int(control.setting('schedTraktTime')) > 0:
				import threading
				log_utils.log('#################### STARTING TRAKT SCHEDULING ################', level=LOGINFO)
				log_utils.log('#################### SCHEDULED TIME FRAME '+ control.setting('schedTraktTime')  + ' HOURS ###############', level=LOGINFO)
				timeout = 3600 * int(control.setting('schedTraktTime'))
				schedTrakt = threading.Timer(timeout, SyncTraktCollection().run) # this only runs once at the designated interval time to wait...not repeating
				schedTrakt.start()
		break
	SettingsMonitor().waitForAbort()
	control.log('[ plugin.video.luc_kodi ]  Settings Monitor Service Stopping...', LOGINFO)
	del catalogService # prob does not kill a running thread
	control.log('[ plugin.video.luc_kodi ]  Catalog Service Stopping...', LOGINFO)
	del syncTraktService # prob does not kill a running thread
	control.log('[ plugin.video.luc_kodi ]  Trakt Sync Service Stopping...', LOGINFO)
	try:
		del syncSimklService
		control.log('[ plugin.video.luc_kodi ]  SIMKL Sync Service Stopping...', LOGINFO)
	except Exception:
		pass
	if libraryService:
		del libraryService # prob does not kill a running thread
		control.log('[ plugin.video.luc_kodi ]  Library Update Service Stopping...', LOGINFO)
	if schedTrakt:
		schedTrakt.cancel()
	control.log('[ plugin.video.luc_kodi ]  Service Stopped', LOGINFO)

main()