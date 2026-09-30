# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — trailer.py (v1.0.61)

	Reproducción de tráilers vía plugin.video.youtube. Una sola vía, y con
	motivo: es la única que funciona.

	POR QUÉ SE RETIRÓ EL RESOLVER PROPIO (20-ago-2026). El diagnóstico en
	vivo lo dejó cerrado. Los cuatro clientes de InnerTube
	que usábamos responden lo mismo:

		android_vr       hls=no dash=no sabr=YES  sin_url=0
		android_sdkless  hls=no dash=no sabr=YES  sin_url=26
		android          hls=no dash=no sabr=YES  sin_url=29
		ios              hls=no dash=no sabr=YES  sin_url=0  progressive=0

	YouTube ya no publica manifest de ningún tipo a clientes no oficiales:
	solo `serverAbrStreamingUrl`, o sea SABR, que exige un PO token que
	únicamente pueden generar BotGuard (web) o DroidGuard (Android) y que
	es imposible producir desde Python. Las URLs directas que aún llegan
	(android_vr, ios) sirven ~60-65 s de cada fichero y luego responden 403
	para siempre — el famoso corte al minuto. Y `android`/`android_sdkless`
	ya ni siquiera traen URL en sus formatos.

	Se probó de todo antes de rendirse: proxy de segmentos con ritmo AIMD,
	refresco de firmas en caliente, copiar el cliente ios literal del addon
	de YouTube, y alinear el payload entero (cpn, thirdParty, user, gl,
	cabeceras Accept). Nada cambió una sola línea del diagnóstico.

	Lo que SÍ funciona, medido: plugin.video.youtube con "Use MPEG-DASH for
	videos" DESACTIVADO en sus ajustes. Entrega el HLS variant manifest de
	googlevideo, que no pasa por peticiones de rango a URLs firmadas, así
	que el muro no aplica. Cinco tráilers de cinco, enteros, a 1080p, en
	tres sesiones distintas. NO hace falta cuenta ni login: el cliente que
	entrega el manifest va sin autenticar.

	El id del tráiler sale de meta['trailer'] (TMDb ya lo trae en los menús);
	si no viene, se consulta TMDb /videos en el momento (clave TMDb ya
	incluida en el addon) y, como última bala, Trakt.
"""

from resources.lib.modules import app_keys
import re
from json import loads as jsloads, dumps as jsdumps
from sys import argv
from urllib.parse import parse_qs, urlparse
from resources.lib.modules import client
from resources.lib.modules import control
from resources.lib.modules import log_utils

getSetting = control.setting
LOGINFO = log_utils.LOGINFO

YT_PLUGIN = 'plugin.video.youtube'

# Clave TMDb incluida en el addon (misma fallback que player.py)
TMDB_FALLBACK_KEY = app_keys.get('tmdb')
TMDB_VIDEOS = 'https://api.themoviedb.org/3/%s/%s/videos?api_key=%s'
TMDB_FIND = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=imdb_id'
TMDB_DETAIL = 'https://api.themoviedb.org/3/%s/%s?api_key=%s'
TMDB_SEASON_VIDEOS = 'https://api.themoviedb.org/3/tv/%s/season/%s/videos?api_key=%s&include_video_language=%s'

# v1.0.90: candidatos pendientes para el failover (los lanza service.py).
FAILOVER_PROP = 'luc_kodi.trailer.failover'

_YT_ID_RE = re.compile(r'^[\w-]{11}$')


def _has_addon(addon_id):
	"""Instalado Y HABILITADO. `System.HasAddon()` devuelve verdadero también
	con el addon desactivado, así que un plugin.video.youtube instalado pero
	apagado se quedaría con el tráiler y no caeríamos al resolver interno.
	Se usa JSON-RPC `Addons.GetAddonDetails` con la propiedad `enabled`."""
	try:
		import json as _json
		resp = _json.loads(control.jsonrpc(_json.dumps({
			'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddonDetails',
			'params': {'addonid': addon_id, 'properties': ['enabled']}})))
		return bool(((resp.get('result') or {}).get('addon') or {}).get('enabled'))
	except Exception:
		return False


class Trailer:
	def __init__(self):
		self.youtube_watch = 'https://www.youtube.com/watch?v=%s'

	# ──────────────────────────────────────────────────────────────
	# Entrada desde el router (action=play_Trailer)
	# ──────────────────────────────────────────────────────────────
	def play(self, type='', name='', year='', url='', imdb='', windowedtrailer=0, tmdb=''):
		try:
			# v1.0.90: la temporada del item enfocado permite pedir el trailer
			# de esa temporada antes que el de la serie.
			season = ''
			if type != 'movie':
				season = control.infoLabel('ListItem.Season') or ''
				if not season.isdigit() or int(season) < 1: season = ''
			candidates = self.worker(type, name, year, url, imdb, tmdb, season=season)
			if not candidates:
				control.notification(message='Trailer not found')
				return
			resolved = None
			for idx, video_id in enumerate(candidates):
				resolved = self.resolve(video_id)
				if resolved:
					candidates = candidates[idx + 1:]
					break
				control.log('[ luc_kodi ] trailer: candidate %s failed, trying next' % video_id, LOGINFO)
			if not resolved:
				control.notification(message='Trailer not found')
				return
			title = control.infoLabel('ListItem.Title')
			if not title: title = control.infoLabel('ListItem.Label')
			if not title: title = '%s Trailer' % name if name else 'Trailer'
			icon = control.infoLabel('ListItem.Icon')
			item = self._build_item(title, icon)
			# v1.0.90 (F6): resolve() devuelve la URL del addon de YouTube para
			# CUALQUIER id, asi que el bucle de arriba siempre se quedaba con el
			# primero y la lista de candidatos no servia de nada ante un
			# geobloqueo. Los que quedan se dejan en la ventana Home y el
			# SubtitlePlayer del servicio los lanza si llega onPlayBackError.
			self._arm_failover(candidates[:3], title, icon)
			control.addItem(handle=int(argv[1]), url=resolved['url'], listitem=item, isFolder=False)
			control.refresh()
			control.resolve(handle=int(argv[1]), succeeded=True, listitem=item)
			if windowedtrailer == 1:
				control.sleep(1000)
				while control.player.isPlayingVideo():
					control.sleep(1000)
				import xbmcgui
				control.execute("Dialog.Close(%s, true)" % xbmcgui.getCurrentWindowDialogId())
		except:
			log_utils.error()

	def _build_item(self, title, icon):
		"""v1.0.90: ademas de titulo e icono, la sinopsis y el tagline del item
		enfocado, para que el OSD del skin tenga algo que ensenar."""
		item = control.item(label=title, offscreen=True)
		item.setProperty('IsPlayable', 'true')
		item.setArt({'icon': icon, 'thumb': icon})
		labels = {'title': title}
		try:
			plot = control.infoLabel('ListItem.Plot')
			tagline = control.infoLabel('ListItem.Tagline')
			if plot: labels['plot'] = plot
			if tagline: labels['tagline'] = tagline
		except: pass
		try: item.setInfo(type='video', infoLabels=labels)
		except: pass
		return item

	def _arm_failover(self, rest, title, icon):
		try:
			if rest:
				control.homeWindow.setProperty(FAILOVER_PROP, jsdumps({'ids': rest, 'title': title, 'icon': icon}))
			else:
				control.homeWindow.clearProperty(FAILOVER_PROP)
		except Exception:
			pass

	def worker(self, type, name, year, url, imdb, tmdb='', season=''):
		"""Devuelve una LISTA de video ids candidatos, mejor primero."""
		official_only = getSetting('trailer.official.only') != 'false'
		if official_only and (tmdb or imdb):
			return self.tmdb_trailer(type, tmdb, imdb, official_only=True, season=season)
		candidates = []
		vid = self._extract_id(url)
		if vid: candidates.append(vid)
		for key in self.tmdb_trailer(type, tmdb, imdb, official_only=official_only, season=season):
			if key not in candidates: candidates.append(key)
		tk = self.trakt_trailer(type, name, year, imdb)
		if tk and tk not in candidates: candidates.append(tk)
		return candidates

	def _extract_id(self, url):
		"""Acepta: id pelado de 11 chars, watch?v=, youtu.be/, embed/, y
		URLs plugin:// (video_id=) tanto nuestras como del addon de YouTube."""
		if not url: return None
		url = str(url)
		if _YT_ID_RE.match(url): return url
		try:
			parsed = urlparse(url)
			qs = parse_qs(parsed.query)
			for key in ('video_id', 'videoid', 'v', 'url'):
				vals = qs.get(key)
				if vals and _YT_ID_RE.match(vals[0]): return vals[0]
			# youtu.be/<id> o /embed/<id>
			tail = parsed.path.rstrip('/').split('/')[-1]
			if _YT_ID_RE.match(tail): return tail
		except: pass
		return None

	def tmdb_trailer(self, type, tmdb, imdb, official_only=True, season=''):
		"""Devuelve una LISTA de video ids (hasta 4, mejor primero) desde
		TMDb /videos (cache manual 7 dias). Con official_only, SOLO type
		'Trailer'; se prioriza el idioma elegido, official=true y mayor size.
		v1.0.50: lista en vez de un unico id.
		v1.0.90: se pide en el idioma elegido en «Trailer language» (antes solo
		llegaba el ingles de la API: ningun trailer en castellano), y en series
		con temporada se prueba primero el trailer de esa temporada."""
		try:
			key = getSetting('tmdb.api.key') or TMDB_FALLBACK_KEY
			media = 'movie' if type == 'movie' else 'tv'
			if not tmdb and imdb and str(imdb).startswith('tt'):
				result = client.request(TMDB_FIND % (imdb, key), error=True)
				if result:
					found = jsloads(result).get('%s_results' % ('movie' if media == 'movie' else 'tv'), [])
					if found: tmdb = found[0].get('id')
			if not tmdb: return []
			langs = self._video_langs(media, tmdb, key)
			keys = []
			if media == 'tv' and season:
				keys = self._pick(self._tmdb_videos_cached(media, tmdb, key, langs, season=season), official_only, langs)
			for k in self._pick(self._tmdb_videos_cached(media, tmdb, key, langs), official_only, langs):
				if k not in keys: keys.append(k)
			return keys[:4]
		except:
			log_utils.error()
			return []

	def _pick(self, videos, official_only, langs):
		if not videos: return []
		if official_only:
			videos = [i for i in videos if i.get('type') == 'Trailer']
		else:
			videos = [i for i in videos if i.get('type') in ('Trailer', 'Teaser')]
		order = {l: n for n, l in enumerate(langs)}
		videos.sort(key=lambda i: (order.get(i.get('iso_639_1') or 'null', len(order)), i.get('type') != 'Trailer',
								   not i.get('official'), -(i.get('size') or 0)))
		keys = []
		for i in videos:
			k = i.get('key')
			if k and k not in keys: keys.append(k)
			if len(keys) >= 4: break
		return keys

	def _video_langs(self, media, tmdb, key):
		"""Orden de idiomas para include_video_language. Ajuste
		trailer.language: 0 = idioma de la interfaz de Kodi, 1 = idioma
		original del titulo, 2 = ingles. Siempre se anade en y null detras."""
		first = 'en'
		try:
			mode = getSetting('trailer.language') or '0'
			if mode == '0':
				import xbmc
				first = (xbmc.getLanguage(xbmc.ISO_639_1) or 'en').lower()[:2]
			elif mode == '1':
				first = self._original_language(media, tmdb, key) or 'en'
		except Exception:
			first = 'en'
		out = []
		for l in (first, 'en', 'null'):
			if l and l not in out: out.append(l)
		return out

	def _original_language(self, media, tmdb, key):
		from time import time
		from resources.lib.database import cache
		ck = 'tmdb_origlang_%s_%s' % (media, tmdb)
		try:
			c = cache.cache_get(ck)
			if c and c.get('value') and (int(time()) - int(c['date'])) < 30 * 24 * 3600:
				return c['value']
		except Exception: pass
		try:
			result = client.request(TMDB_DETAIL % (media, tmdb, key), error=True)
			lang = (jsloads(result).get('original_language') or '') if result else ''
			if lang:
				cache.cache_insert(ck, lang)
			return lang
		except Exception:
			return ''

	def _tmdb_videos_cached(self, media, tmdb, key, langs=('en', 'null'), season=''):
		from ast import literal_eval
		from time import time
		from resources.lib.database import cache
		lang_param = ','.join(langs)
		cache_key = 'tmdb_videos_%s_%s_%s_%s' % (media, tmdb, season or 'all', lang_param)
		try:
			cached = cache.cache_get(cache_key)
			if cached and (int(time()) - int(cached['date'])) < 7 * 24 * 3600:
				value = literal_eval(cached['value'])
				if isinstance(value, list): return value
		except Exception: log_utils.error()
		if season:
			url = TMDB_SEASON_VIDEOS % (tmdb, season, key, lang_param)
		else:
			url = TMDB_VIDEOS % (media, tmdb, key) + '&include_video_language=' + lang_param
		result = client.request(url, error=True)
		if not result: return None
		videos = [i for i in jsloads(result).get('results', []) if i.get('site') == 'YouTube']
		try: cache.cache_insert(cache_key, repr(videos))
		except Exception: log_utils.error()
		return videos

	def trakt_trailer(self, type, name, year, imdb):
		try:
			from resources.lib.modules import trakt
			id = (name.lower() + '-' + year) if imdb in ('0', '', None) else imdb
			if type == 'movie': item = trakt.getMovieSummary(id)
			else: item = trakt.getTVShowSummary(id)
			return self._extract_id(item.get('trailer'))
		except:
			log_utils.error()
			return None

	# ──────────────────────────────────────────────────────────────
	# Cadena de resolución (sin API key)
	# ──────────────────────────────────────────────────────────────
	def resolve(self, video_id):
		"""Devuelve {'url': 'plugin://plugin.video.youtube/play/...'} o None."""
		return self._via_youtube_plugin(video_id)

	def _via_youtube_plugin(self, video_id):
		if not _has_addon(YT_PLUGIN):
			# Sin el addon no hay tráilers. Merece un aviso claro en vez de
			# un 'Trailer not found' que haría pensar en un fallo de TMDb.
			control.log('[ luc_kodi ] trailer: plugin.video.youtube missing or disabled', LOGINFO)
			control.notification(message='Trailers need the YouTube add-on installed and enabled')
			return None
		control.log('[ luc_kodi ] trailer: handing off to plugin.video.youtube', LOGINFO)
		# v1.0.64: marca el traspaso. El reproductor recibe una URL de
		# plugin.video.youtube, asi que en onAVStarted no hay forma de saber que
		# el trailer lo lanzamos nosotros: getVideoInfoTag() ya no apunta a
		# luc_kodi. Sin esta marca el selector de HE-AAC actuaria sobre CUALQUIER
		# reproduccion del addon de YouTube, incluida la que el usuario lance por
		# su cuenta, y eso no es cosa nuestra.
		try:
			control.homeWindow.setProperty('luc_kodi.trailer.playing', video_id)
		except Exception:
			pass
		return {'url': 'plugin://%s/play/?video_id=%s' % (YT_PLUGIN, video_id)}
