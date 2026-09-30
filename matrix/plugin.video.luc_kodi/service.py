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

class SettingsJanitor:
	"""v1.0.65: retira los ajustes huerfanos al cambiar de version del addon.

	Kodi avisa al arrancar de cada ajuste que sigue en el addon_data del usuario
	pero ya no esta declarado. Medido comparando la 1.0.70 de pruebas con la
	1.0.61 oficial: quedaron SEIS, todos del resolver interno de trailers que se
	retiro — trailer.codec.av1, trailer.codec.vp92, trailer.invidious.instances,
	trailer.max.resolution, trailer.min.resolution y trailer.player.

	clean_settings() ya sabia hacer esto, pero habia que lanzarlo a mano, y un
	mantenimiento que hay que lanzar a mano no se lanza.

	ORDEN IMPORTANTE: el marcador se escribe ANTES de reescribir el fichero. Un
	setSetting posterior pasaria por la copia en memoria de Kodi y volveria a
	volcar el fichero, devolviendo los huerfanos que acabamos de quitar.
	"""
	MARKER = 'settings.cleaned.version'

	def run(self):
		try:
			version = control.addon('plugin.video.luc_kodi').getAddonInfo('version')
			if control.setting(self.MARKER) == version:
				return
			control.setSetting(self.MARKER, version)
			control.sleep(200)
			from resources.lib.modules import clean_settings
			removed = clean_settings.clean_settings(silent=True)
			if removed:
				control.log('[ luc_kodi ] SettingsJanitor: %s ajustes obsoletos retirados en %s'
				            % (len(removed), version), LOGINFO)
		except Exception:
			log_utils.error()


class YouTubePrefsSetup:
	"""One-shot opt-in (v1.0.62): deja plugin.video.youtube listo para tráilers.

	Con "Use MPEG-DASH for videos" apagado —que es lo que exigimos— el addon de
	YouTube cae en kodion.video.stream.select, cuyo default de fábrica es 2
	('list'), y eso le pasa a inputstream.adaptive stream_selection_type =
	'manual-osd': el usuario tiene que elegir la variante en el OSD en CADA
	reproducción. Poniéndolo a 1 ('auto') el problema desaparece.

	NO se ejecuta salvo que el usuario lo pida (trailer.yt.autoconfig). Tocar
	los ajustes de otro addon sin permiso explícito no se hace: quien tenga su
	YouTube afinado para otras cosas no debe encontrárselo cambiado. El botón
	de la pestaña Trailers es la vía normal; esto es solo para el que prefiera
	que se aplique solo tras instalar."""
	def run(self):
		try:
			from resources.lib.modules import yt_prefs
			yt_prefs.ensure_once()
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
				# v1.0.88: + refresh y scope de AUTH V2. Sin el refresh token en esta
				# lista, una actualizacion que reescribiera settings.xml dejaria al
				# usuario V2 con un access token de 7 dias y nada con que renovarlo.
				_simkl_keys = ('simkl.token', 'simkl.username', 'simkl.user_id', 'simkl.isauthed', 'simkl.expires',
							   'simkl.refresh', 'simkl.scope')
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

				# El username de MDBList sólo es válido si hay credencial propia.
				# Sin token OAuth Y sin API key propia no debe persistir ninguno,
				# o los ajustes muestran una cuenta que ya no está asociada.
				#
				# v1.0.69: aquí vivía además la limpieza de la API key personal del
				# autor, que la 1.0.40 y anteriores llevaban como DEFAULT_APIKEY.
				# Retirada: la comparación obligaba a publicar esa credencial (o su
				# hash) en cada release, y entre la 1.0.41 y hoy han pasado casi
				# treinta versiones, así que ya no queda a quién limpiársela.
				# La condición del username se estrecha a la que el comentario
				# original describía: antes se borraba a todo el que no tuviera
				# OAuth, incluidos los que sí tienen su propia API key.
				try:
					_mdb_token = (_addon_post.getSetting('mdblist.token') or '').strip()
					_mdb_apikey = (_addon_post.getSetting('mdblist.apikey') or '').strip()
					_mdb_has_cred = bool(_mdb_apikey) or (_mdb_token and _mdb_token not in ('0', 'empty_setting'))
					if not _mdb_has_cred and (_addon_post.getSetting('mdblist.username') or '').strip():
						_addon_post.setSetting('mdblist.username', '')
						control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: cleared stale MDBList username (no credential)', LOGINFO)
				except Exception:
					log_utils.error()

				control.log('[ plugin.video.luc_kodi ]  Forced new User Data settings.xml saved', LOGINFO)

				# v1.0.59 MIGRACION: el desplegable de Gemini AI cambia de valores
				# cada vez que Google retira un modelo. La 1.0.58 saco
				# gemini-2.5-pro de `values=`, y antes salieron gemini-2.0-flash,
				# gemini-2.0-flash-lite y los tres *-preview. Un usuario que
				# tuviera uno de esos SELECCIONADO se queda con un valor guardado
				# en su settings.xml que ya no existe en la definicion del ajuste:
				# Kodi lo detecta al cargar los ajustes tras la actualizacion y lo
				# reporta como ajuste obsoleto. gemini_api._legacy_model_map ya lo
				# remapeaba AL LEER, asi que la busqueda funcionaba, pero el valor
				# invalido seguia escrito en disco y el aviso volvia cada vez.
				# Aqui lo normalizamos en el propio settings.xml, una sola vez.
				try:
					_gm = (_addon_post.getSetting('gemini.model') or '').strip()
					if _gm:
						from resources.lib.modules.gemini_api import (
							_legacy_model_map as _gmap, fallback_models as _gchain,
							default_model as _gdef)
						# Valores validos = los que ofrece hoy el desplegable. Se
						# leen de la propia definicion para no duplicar la lista.
						_valid = set(_gchain) | {_gdef}
						try:
							import re as _re
							_sx = _addon_post.getAddonInfo('path')
							_sx = control.joinPath(_sx, 'resources', 'settings.xml')
							with open(_sx, 'r', encoding='utf-8') as _fh:
								_m = _re.search(r'id="gemini\.model"[^>]*values="([^"]+)"', _fh.read())
							if _m:
								_valid = set(_m.group(1).split('|'))
						except Exception:
							pass
						if _gm not in _valid:
							_new = _gmap.get(_gm, _gdef)
							if _new not in _valid:
								_new = _gdef
							_addon_post.setSetting('gemini.model', _new)
							try:
								control.homeWindow.clearProperty('luc_kodi_settings')
							except Exception:
								pass
							control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: '
										'stale gemini.model "%s" migrated to "%s"' % (_gm, _new), LOGINFO)
				except Exception:
					log_utils.error()

				# v1.0.74 MIGRACIÓN de la calidad de imagen. Mismo patrón que la de
				# gemini.model de arriba, y por el mismo motivo: un enum al que se le
				# recortan valores deja escrito en el settings.xml del usuario un
				# índice que ya no existe, y Kodi lo reporta como ajuste obsoleto en
				# cada arranque.
				#
				# Hay DOS orígenes que traducir:
				#   · `tmdb.imageResolutions`, el ajuste viejo de cinco niveles. La
				#     traducción vivía dentro de tmdb._read_image_level() y NUNCA
				#     llegaba a ejecutarse: solo miraba el ajuste viejo cuando el
				#     nuevo estaba vacío, y un enum declarado con default="0" jamás
				#     devuelve vacío — Kodi entrega el default. Así que todo el que
				#     venía de una versión anterior aparecía en Auto en silencio.
				#   · `tmdb.imageQuality` con valor 2, 3 o 4, que es lo que escribió
				#     la 1.0.73 mientras el ajuste tuvo cinco opciones.
				#
				# Aquí sí funciona porque este bloque corre DESPUÉS de la escritura
				# forzada de settings.xml, lee por xbmcaddon (no por el dict
				# cacheado) y puede invalidar ese dict al terminar.
				try:
					from resources.lib.indexers import tmdb as _tmdb_mig
					_iq = (_addon_post.getSetting(_tmdb_mig.IMAGE_SETTING) or '').strip()
					_valid_iq = (str(_tmdb_mig._CHOICE_AUTO), str(_tmdb_mig._CHOICE_ORIGINAL))
					if _iq not in _valid_iq:
						_choice = _tmdb_mig._CHOICE_AUTO
						_from = _iq or 'unset'
						try:
							# Un 2/3/4 en el ajuste NUEVO es Low/Medium/High de la
							# 1.0.73: los tres van a Auto, que es lo que ahora
							# significa "que decida el aparato".
							if _iq != '':
								_choice = _tmdb_mig._CHOICE_AUTO
							else:
								_legacy = (_addon_post.getSetting(
									_tmdb_mig.LEGACY_IMAGE_SETTING) or '').strip()
								_from = 'legacy %s' % (_legacy or 'unset')
								if _legacy != '':
									_choice = _tmdb_mig.LEGACY_TO_CHOICE.get(
										int(_legacy), _tmdb_mig._CHOICE_AUTO)
						except (TypeError, ValueError):
							_choice = _tmdb_mig._CHOICE_AUTO
						_addon_post.setSetting(_tmdb_mig.IMAGE_SETTING, str(_choice))
						try:
							control.homeWindow.clearProperty('luc_kodi_settings')
							control.homeWindow.clearProperty(_tmdb_mig._CEILING_PROP)
						except Exception:
							pass
						control.log('[ plugin.video.luc_kodi ]  VersionIsUpdateCheck: '
									'image quality migrated (%s -> %s)'
									% (_from, 'Original' if _choice == _tmdb_mig._CHOICE_ORIGINAL
									   else 'Auto'), LOGINFO)
				except Exception:
					log_utils.error()

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

	def onPlayBackError(self):
		"""v1.0.90 (F6): failover de trailers. trailer.py deja en la ventana
		Home los ids de repuesto; si el que se entrego a plugin.video.youtube
		falla (geobloqueo, video retirado), se lanza el siguiente. Maximo
		tres, y solo mientras la marca de trailer siga puesta."""
		try:
			import json as _json
			raw = control.homeWindow.getProperty('luc_kodi.trailer.failover')
			if not raw or not control.homeWindow.getProperty('luc_kodi.trailer.playing'):
				# v1.0.91: rollover de fuentes. sources.py deja las siguientes
				# del autoplay; si la elegida no llega a arrancar se prueba otra.
				if control.homeWindow.getProperty('luc_kodi.rollover'):
					control.log('[ luc_kodi ] rollover: onPlayBackError before start, launching play_rollover', LOGINFO)
					control.execute('RunPlugin(plugin://plugin.video.luc_kodi/?action=play_rollover)')
				return
			data = _json.loads(raw)
			ids = data.get('ids') or []
			if not ids:
				control.homeWindow.clearProperty('luc_kodi.trailer.failover')
				return
			nxt, rest = ids[0], ids[1:]
			if rest:
				data['ids'] = rest
				control.homeWindow.setProperty('luc_kodi.trailer.failover', _json.dumps(data))
			else:
				control.homeWindow.clearProperty('luc_kodi.trailer.failover')
			control.log('[ luc_kodi ] trailer failover: playback error, trying %s (%d left)' % (nxt, len(rest)), LOGINFO)
			control.homeWindow.setProperty('luc_kodi.trailer.playing', nxt)
			control.notification(message=400841)
			item = control.item(label=data.get('title') or 'Trailer', offscreen=True)
			try: item.setArt({'icon': data.get('icon') or '', 'thumb': data.get('icon') or ''})
			except Exception: pass
			control.sleep(500)
			self.play('plugin://plugin.video.youtube/play/?video_id=%s' % nxt, item)
		except Exception:
			log_utils.error()

	def onAVStarted(self):
		# v1.0.63: volcado de pistas de audio ANTES del guard de luc_kodi — los
		# trailers se reproducen via plugin.video.youtube, asi que si esto fuese
		# despues del guard no se ejecutaria nunca justo en el caso que interesa.
		# No hace nada salvo que trailer.audio.probe este activo.
		try:
			from resources.lib.modules import trailer_audio
			trailer_audio.probe()
			trailer_audio.apply_preferred_profile()
		except Exception:
			pass
		# v1.0.90: si algo arranco, los candidatos de repuesto del trailer ya
		# no hacen falta.
		try:
			control.homeWindow.clearProperty('luc_kodi.trailer.failover')
			control.homeWindow.clearProperty('luc_kodi.rollover') # v1.0.91: arranco, no hace falta
		except Exception: pass
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
		# v1.0.94: ya solo fija el offset de arranque de la rotacion; la
		# limpieza de texturas la lleva MaintenanceService.
		from resources.lib.modules import poster_rotator
		poster_rotator.janitor_service()


class UpdaterService:
	def run(self):
		control.monitor.waitForAbort(5)
		from resources.lib.modules import updater
		updater.UpdaterService().run() # contiene bucle "waitForAbort"; no-op si updater.enabled esta a false

class MaintenanceService:
	def run(self):
		# v1.0.94: la sonda de limpieza. Un solo bucle para todo lo que deja el
		# addon (arte, bases de cache, listas en RAM, temporales, log): vigila
		# la salida del addon, hace la pasada diferida del arranque y, al
		# cerrar Kodi, solo deja marcada la pendiente. Sustituye al bucle
		# mensual de cache_janitor y al de texturas de poster_rotator.
		control.log('[ plugin.video.luc_kodi ]  Maintenance Service Starting...', LOGINFO)
		from resources.lib.modules import maintenance
		maintenance.service_loop() # contiene bucle "waitForAbort"


def main():
	# v1.0.78: estos cinco nombres se ligaban DENTRO del while. Si
	# abortRequested() ya es cierto en la primera vuelta —lo que pasa cuando
	# el servicio arranca durante un apagado de Kodi o durante el
	# SetAddonEnabled que hace el updater al recargar el addon— el cuerpo no
	# corre nunca y el bloque de cierre de abajo petaba con
	# UnboundLocalError en 'del catalogService'. Ligados aquí, el cierre
	# siempre encuentra algo, corra el cuerpo o no.
	schedTrakt = None
	libraryService = None
	catalogService = None
	syncTraktService = None
	syncSimklService = None
	while not control.monitor.abortRequested():
		control.log('[ plugin.video.luc_kodi ]  Service Started', LOGINFO)
		CheckSettingsFile().run()
		TorBoxUsenetMigration().run()
		DmmReenableMigration().run()
		SettingsJanitor().run()
		YouTubePrefsSetup().run()
		CheckUndesirablesDatabase().run()
		GUIResolutionService().run()  # non-blocking — lanza hilo daemon
		# v1.0.90: perfil de memoria del aparato (device_profile.py).
		try:
			from resources.lib.modules import device_profile
			_prof, _free, _total = device_profile.detect()
			control.log('[ plugin.video.luc_kodi ]  Device profile: %s (free %s MB, total %s MB)' % (_prof, _free, _total), LOGINFO)
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

		# v1.0.31: offset de arranque de la rotacion de posters (la limpieza pasa a MaintenanceService en la 1.0.94)
		posterJanitorService = Thread(target=PosterJanitorService().run)
		posterJanitorService.start()

		# v1.0.77: canal de autoactualización propio (no-op si updater.enabled está a false)
		updaterService = Thread(target=UpdaterService().run)
		updaterService.start()

		maintenanceService = Thread(target=MaintenanceService().run)
		maintenanceService.start()

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
	if catalogService:
		del catalogService # prob does not kill a running thread
		control.log('[ plugin.video.luc_kodi ]  Catalog Service Stopping...', LOGINFO)
	if syncTraktService:
		del syncTraktService # prob does not kill a running thread
		control.log('[ plugin.video.luc_kodi ]  Trakt Sync Service Stopping...', LOGINFO)
	if syncSimklService:
		del syncSimklService
		control.log('[ plugin.video.luc_kodi ]  SIMKL Sync Service Stopping...', LOGINFO)
	if libraryService:
		del libraryService # prob does not kill a running thread
		control.log('[ plugin.video.luc_kodi ]  Library Update Service Stopping...', LOGINFO)
	if schedTrakt:
		schedTrakt.cancel()
	control.log('[ plugin.video.luc_kodi ]  Service Stopped', LOGINFO)

main()